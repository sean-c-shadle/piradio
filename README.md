# piradio
python code for running DIY raspberry pi internet radio. Tested on pi zero 2w with Adafruit Mini PiTFT 1.3" - 240x240 TFT Add-on screen add-on.

Note I also added a power button to GPIO5 that can power off the pi if held for 1 second. See layout here: https://pinout.xyz/
If this is desired, a momentary switch needs to be added to GPIO5. This pin apparently cannot power on the pi but makes for a safe poweroff.

Follow guide here to get the 1.3" display to work: https://learn.adafruit.com/adafruit-mini-pitft-135x240-color-tft-add-on-for-raspberry-pi/1-3-240x240-kernel-module-install

I am running Raspbian lite OS based on Debian Trixie 13.5
```
Linux piradio 6.18.34+rpt-rpi-v8 #1 SMP PREEMPT Debian 1:6.18.34-1+rpt1 (2026-06-09) aarch64 GNU/Linux
```

## Install dependencies
```sh
sudo apt update
sudo apt install pulseaudio pulseaudio-module-bluetooth mpd mpc python3-gpiozero
```

## connect bluetooth device
```sh
sudo rfkill unblock bluetooth
sudo rfkill unblock all
sudo systemctl restart bluetooth
```
now run bluetoothctl interactively:
```sh
bluetoothctl
# in prompt
power on
agent on
default-agent
scan on
```
find device MAC
```
XX:XX:XX:XX:XX:XX Example speakers
```
Now pair and add as trusted:
```
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
scan off  
quit
```
test audio:
```
speaker-test -t wav -c 2
```

## Add streams to mpd via mpc
```
mpc add https://stream-relay-geo.ntslive.net/stream  
mpc add https://stream.xmission.com/kuaa  
mpc add https://stream-mixtape-geo.ntslive.net/mixtape34  
mpc add https://kuer.streamguys1.com/high_icy  
mpc add http://stream.live.vc.bbcmedia.co.uk/bbc_world_service  
mpc add https://stream-relay-geo.ntslive.net/stream2  
mpc add https://stream-mixtape-geo.ntslive.net/mixtape

mpc play
mpc off
```
Configure user mpd
```sh
mkdir -p ~/.config/mpd/playlists
mkdir -p ~/.local/share/mpd
cp /etc/mpd.conf ~/.config/mpd/mpd.conf
```
I added these to the confguration file:
```
music_directory     "/home/sean/Music"
playlist_directory  "/home/sean/.config/mpd/playlists"
db_file             "/home/sean/.local/share/mpd/database"
log_file            "/home/sean/.local/share/mpd/log"
pid_file            "/home/sean/.local/share/mpd/pid"
state_file          "/home/sean/.local/share/mpd/state"
sticker_file        "/home/sean/.local/share/mpd/sticker.sql"
music_directory         "/var/lib/mpd/music"
```
and enabled pulse audio in the conf file:
```
audio_output {
        type            "pulse"
        name            "My Pulse Output"
        server          "unix:/run/user/1000/pulse/native"              # optional
#       sink            "remote_server_sink"    # optional
#       media_role      "media_role"            #optional
}
```


# Start as systemd services on boot

Note that this relies on the connect-bluetooth-speaker.sh script. The MAC address for the paired and trusted bluetooth speakers needs to be set in that file first!

~/.config/systemd/user/bluetooth-speaker-connect.service
```
[Unit]
Description=Connect Logitech Bluetooth speakers
After=pulseaudio.service
Wants=pulseaudio.service

[Service]
Type=oneshot
ExecStart=/home/sean/connect-bluetooth-speaker.sh
RemainAfterExit=yes
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```
enable service
```
systemctl --user daemon-reload  
systemctl --user enable bluetooth-speaker-connect.service
systemctl --user start bluetooth-speaker-connect.service
```

~/.config/systemd/user/mpd-user.service
```INI
[Unit]  
Description=User Music Player Daemon  
After=bluetooth-speaker-connect.service  
Requires=bluetooth-speaker-connect.service  
  
[Service]  
ExecStart=/usr/bin/mpd --no-daemon /home/sean/.config/mpd/mpd.conf  
Restart=on-failure  
RestartSec=3  
  
[Install]  
WantedBy=default.target
```

enable
```sh
systemctl --user daemon-reload
systemctl --user enable mpd-user.service
systemctl --user start mpd-user.service
```

~/.config/systemd/user/piradio.service
```INI
[Unit]
Description=PiTFT Radio Buttons and Display
After=mpd-user.service
Requires=mpd-user.service

[Service]
ExecStart=/usr/bin/python3 /home/sean/piradio.py
WorkingDirectory=/home/sean
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

enable
```sh
systemctl --user daemon-reload  
systemctl --user enable piradio.service  
systemctl --user start piradio.service
```

make sure user stays logged in
```
sudo loginctl enable-linger sean
```


# Hard coding station names
Since the streams sometimes fail to resolve the station names correctly (giving unreadable url), I have hardcoded station names into piradio.py.

For example, within piradio.py the STATION_NAMES dictionary needs to be changed if stations are added/deleted:
```python
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
```
