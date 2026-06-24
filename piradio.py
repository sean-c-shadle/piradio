#!/usr/bin/env python3

from gpiozero import Button
from signal import pause
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from evdev import InputDevice, categorize, ecodes, list_devices
import subprocess
import textwrap
import threading
import time


# ----------------------------
# Bluetooth configuration
# ----------------------------

# replace name with relevant bluetooth device found with evtest
BT_INPUT_NAME_MATCH = "EDIFIER"

# ----------------------------
# Button configuration
# ----------------------------

PLAY_PAUSE_GPIO = 23
NEXT_GPIO = 24
POWER_GPIO = 5

# ----------------------------
# Display configuration
# ----------------------------

WIDTH = 240
HEIGHT = 240
FRAMEBUFFER = "/dev/fb0"
OUT_IMAGE = "/tmp/piradio_now_playing.jpg"

# Set this to True if you only want the station name before the first colon.
# Example:
#   "Groove Salad: Artist - Track"
# becomes:
#   "Groove Salad"
SHOW_STATION_ONLY = False

# If your user MPD runs on a different port, change this.
# Example:
#   MPC_COMMAND = ["mpc", "-p", "6601"]
MPC_COMMAND = ["mpc"]


# hard-coded station names here (need to add name if new station added)
STATION_NAMES = {
    1: "NTS Radio 1",
    2: "KUAA",
    3: "NTS Metal",
    4: "KUER (NPR)",
    5: "BBC",
    6: "NTS Radio 2",
    7: "NTS Ambient"
}


# ----------------------------
# GPIO buttons
# ----------------------------

play_pause_button = Button(
    PLAY_PAUSE_GPIO,
    pull_up=True,
    bounce_time=0.08
)

next_button = Button(
    NEXT_GPIO,
    pull_up=True,
    bounce_time=0.08
)

# Requires momentary switch installed to GPIO
power_button = Button(
    POWER_GPIO,
    pull_up=True,
    bounce_time=0.08,
    hold_time=1.0
)

# ----------------------------
# State
# ----------------------------

last_displayed_text = None
display_lock = threading.Lock()

def log(message):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"{now}  {message}", flush=True)


def run_command(command):
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False
    )


def run_mpc_command(*args):
    result = run_command([*MPC_COMMAND, *args])

    if result.stdout.strip():
        first_line = result.stdout.strip().splitlines()[0]
        log(first_line)

    if result.returncode != 0:
        log(f"mpc error: {result.stderr.strip()}")

    return result


def get_playback_state():
    result = run_command([*MPC_COMMAND])

    if result.returncode != 0:
        log(f"mpc status error: {result.stderr.strip()}")
        return "unknown"

    output = result.stdout.lower()

    if "[playing]" in output:
        return "playing"

    if "[paused]" in output:
        return "paused"

    return "stopped"

def start_playback():
    log("Starting playback")
    run_mpc_command("play")
    time.sleep(0.5)

    # Fallback in case MPD has a queue but no selected item
    if get_playback_state() != "playing":
        log("mpc play did not start; trying mpc play 1")
        run_mpc_command("play", "1")
        time.sleep(0.5)

    update_display(force=True)

def stop_playback():
    log("Stopping playback")
    run_mpc_command("stop")
    time.sleep(0.3)
    update_display(force=True)

def toggle_play_pause():
    state = get_playback_state()

    log(f"GPIO 23 pressed: state is {state}")

    if state == "playing":
        stop_playback()
    else:
        start_playback()

def get_current_text():
    state = get_playback_state()

    if state == "stopped":
        return "Stopped"

    if state == "paused":
        return "Paused"

    station_number = get_station_number()

    if station_number in STATION_NAMES:
        return STATION_NAMES[station_number]

    result = run_command([*MPC_COMMAND, "current"])

    if result.returncode != 0:
        return f"mpc error: {result.stderr.strip()}"

    text = result.stdout.strip()

    if not text:
        return "Nothing playing"
    update_display(force=True)

    if SHOW_STATION_ONLY and ":" in text:
        text = text.split(":", 1)[0].strip()

    return text

def load_font(size, bold=False):
    if bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass

    return ImageFont.load_default()


def wrap_text_to_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        test_width = bbox[2] - bbox[0]

        if test_width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def make_display_image(text):
    img = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(img)

    title_font = load_font(16, bold=False)
    main_font = load_font(26, bold=True)
    small_font = load_font(14, bold=False)

    # Header
    draw.text((10, 8), "Pi Radio", fill="white", font=title_font)
    draw.line((10, 32, WIDTH - 10, 32), fill="white")

    # Status text
    state = get_playback_state()
    position = get_station_position()

    if state == "playing" and position:
        status_label = f"Now Playing - Station {position}"
    elif state == "paused" and position:
        status_label = f"Paused - Station {position}"
    elif state == "stopped" and position:
        status_label = f"Stopped - Station {position}"
    else:
        status_label = state.capitalize()

    draw.text((10, 40), status_label, fill="white", font=small_font)

    # Main current text
    max_text_width = WIDTH - 20
    lines = wrap_text_to_width(draw, text, main_font, max_text_width)

    # Keep only as many lines as fit
    line_spacing = 6
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        line_heights.append(bbox[3] - bbox[1])

    max_area_height = 150
    visible_lines = []
    used_height = 0

    for line, height in zip(lines, line_heights):
        next_height = used_height + height + line_spacing
        if next_height > max_area_height:
            break
        visible_lines.append(line)
        used_height = next_height

    if len(visible_lines) < len(lines) and visible_lines:
        visible_lines[-1] = visible_lines[-1].rstrip(".") + "..."

    total_height = 0
    measured = []

    for line in visible_lines:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        measured.append((line, width, height))
        total_height += height + line_spacing

    y = 82
    for line, line_width, line_height in measured:
        x = int((WIDTH - line_width) / 2)
        draw.text((x, y), line, fill="yellow", font=main_font)
        y += line_height + line_spacing

    # Footer button hints
    draw.line((10, HEIGHT - 32, WIDTH - 10, HEIGHT - 32), fill="white")
    draw.text((10, HEIGHT - 24), "23: Play/Stop", fill="white", font=small_font)
    draw.text((130, HEIGHT - 24), "24: Next", fill="white", font=small_font)

    return img


def display_image_with_fbi():
    # Kill the previous fbi instance so the image refreshes.
    subprocess.run(
        ["sudo", "killall", "fbi"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False
    )

    subprocess.Popen(
        [
            "sudo", "fbi",
            "-T", "1",
            "-d", FRAMEBUFFER,
            "-noverbose",
            "-a",
            OUT_IMAGE
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def update_display(force=False):
    global last_displayed_text

    with display_lock:
        text = get_current_text()

        if not force and text == last_displayed_text:
            return

        log(f"Display: {text}")

        img = make_display_image(text)
        img.save(OUT_IMAGE)

        display_image_with_fbi()

        last_displayed_text = text

def next_station():
    log("GPIO 24 pressed: next")
    run_mpc_command("next")
    time.sleep(0.5)
    update_display(force=True)


def display_loop():
    while True:
        update_display()
        time.sleep(2)

def get_playback_state():
    result = run_command([*MPC_COMMAND])

    if result.returncode != 0:
        return "unknown"

    output = result.stdout.lower()

    if "[paused]" in output:
        return "paused"
    if "[playing]" in output:
        return "playing"

    return "stopped"

def get_station_position():
    result = run_command([*MPC_COMMAND])

    if result.returncode != 0:
        return ""

    for line in result.stdout.splitlines():
        line = line.strip()

        if "[playing]" in line or "[paused]" in line:
            parts = line.split()

            for part in parts:
                if part.startswith("#") and "/" in part:
                    return part.lstrip("#")

    return ""

def get_station_number():
    result = run_command([*MPC_COMMAND])

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        line = line.strip()

        if "[playing]" in line or "[paused]" in line:
            for part in line.split():
                if part.startswith("#") and "/" in part:
                    # "#6/6" -> 6
                    try:
                        return int(part.lstrip("#").split("/", 1)[0])
                    except ValueError:
                        return None

    return None

def wait_for_mpd(timeout=45):
    log("Waiting for MPD...")

    start = time.time()

    while time.time() - start < timeout:
        result = run_command([*MPC_COMMAND])

        if result.returncode == 0:
            log("MPD is ready")
            return True

        time.sleep(1)

    log("MPD did not become ready in time")
    return False

def power_off():
    log("GPIO 5 held: shutting down")

    try:
        img = make_display_image("Shutting down")
        img.save(OUT_IMAGE)
        display_image_with_fbi()
        time.sleep(1)
    except Exception as e:
        log(f"Could not update display before shutdown: {e}")

    run_mpc_command("stop")

    subprocess.run(
        ["sudo", "shutdown", "-h", "now"],
        check=False
    )

def find_bluetooth_input_device():
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if BT_INPUT_NAME_MATCH.lower() in dev.name.lower():
                return path
        except OSError:
            pass
    return None

def previous_station():
    log("Bluetooth previous")
    run_mpc_command("prev")
    time.sleep(0.5)
    update_display(force=True)

def bluetooth_button_loop():
    path = find_bluetooth_input_device()

    if not path:
        log(f"No Bluetooth input device matching {BT_INPUT_NAME_MATCH!r} found")
        return

    try:
        dev = InputDevice(path)
        log(f"Bluetooth input listening on {path}: {dev.name}")
    except Exception as e:
        log(f"Could not open Bluetooth input device {path}: {e}")
        return

    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue

        # value 1 = key press
        # value 0 = key release
        # We only act on key press to avoid double-triggering.
        if event.value != 1:
            continue

        key = categorize(event)

        keycode = key.keycode
        if isinstance(keycode, list):
            keycode = keycode[0]

        log(f"Bluetooth button: {keycode}")

        if keycode == "KEY_NEXTSONG":
            next_station()

        elif keycode == "KEY_PREVIOUSSONG":
            previous_station()

        elif keycode == "KEY_PLAYCD":
            log("Bluetooth play")
            start_playback()

        elif keycode == "KEY_PAUSECD":
            log("Bluetooth stop")
            stop_playback()


def main():
    play_pause_button.when_pressed = toggle_play_pause
    next_button.when_pressed = next_station
    power_button.when_held = power_off

    log("Starting Pi Radio controller")
    log("GPIO 23 = play/stop")
    log("GPIO 24 = next")
    log("GPIO 5 = hold 1s to power off")

    if not wait_for_mpd():
        time.sleep(5)
    
    # Make next wrap back to station 1 after the final playlist item.
    run_mpc_command("repeat", "on")
    
    run_mpc_command("clear")

    run_mpc_command("load", "my_playlist")

    update_display(force=True)

    threading.Thread(target=display_loop, daemon=True).start()
    threading.Thread(target=bluetooth_button_loop, daemon=True).start()

    pause()


if __name__ == "__main__":
    main()
