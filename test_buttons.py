#!/usr/bin/env python3

from gpiozero import Button
from signal import pause
from datetime import datetime

# Adafruit Mini PiTFT buttons are commonly wired active-low:
# pressed = GPIO pulled to GND
#button_a = Button(23, pull_up=True, bounce_time=0.05)
#button_b = Button(24, pull_up=True, bounce_time=0.05)
button_c = Button(5, pull_up=True, bounce_time=0.05)

def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def make_handler(name, action):
    def handler():
        print(f"{timestamp()}  {name} {action}", flush=True)
    return handler

#button_a.when_pressed = make_handler("GPIO 23", "PRESSED")
#button_a.when_released = make_handler("GPIO 23", "RELEASED")

#button_b.when_pressed = make_handler("GPIO 24", "PRESSED")
#button_b.when_released = make_handler("GPIO 24", "RELEASED")

button_c.when_pressed = make_handler("GPIO 5", "PRESSED")
button_c.when_released = make_handler("GPIO 5", "RELEASED")

print("Testing buttons on GPIO 23 and GPIO 24 and GPIO 5.")
print("Press buttons now. Use Ctrl+C to quit.")

pause()
