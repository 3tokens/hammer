# Hammer Pi Setup Guide

Complete steps to set up a fresh Pi from scratch.

## 1. Flash SD Card

Use Raspberry Pi Imager (https://www.raspberrypi.com/software/):
- OS: Raspberry Pi OS Lite (64-bit)
- Click the gear icon (Advanced Options) before flashing:
  - Enable SSH
  - Set username: `pi`, password: your choice
  - Set WiFi SSID + password
  - Set hostname: `disco`

## 2. First Boot — SSH In

```bash
ssh pi@disco.local
# or find IP via router and ssh pi@<IP>
```

## 3. System Update + Packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-lgpio python3-flask python3-pil git alsa-utils p7zip-full
sudo pip3 install requests --break-system-packages
```

Enable SPI (required for the display):
```bash
sudo raspi-config nonint do_spi 0
```

## 4. Waveshare 1.3" LCD HAT Code

```bash
cd /home/pi
wget https://files.waveshare.com/upload/b/bd/1.3inch_LCD_HAT_code.7z
7z x 1.3inch_LCD_HAT_code.7z -r -o./1.3inch_LCD_HAT_code
sudo chmod 777 -R 1.3inch_LCD_HAT_code
```

## 5. Clone Hammer Repo

```bash
cd /home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python
git init
git remote add origin https://github.com/3tokens/hammer.git
git fetch
git checkout -f main
```

## 7. Check Mic Device

Plug in USB mic, then:
```bash
arecord -l
```
Verify the USB mic shows up. The code uses `plughw:Device` which is stable across reboots and doesn't depend on card number.

## 8. Systemd Service

```bash
sudo nano /etc/systemd/system/hammer.service
```

Paste:
```ini
[Unit]
Description=Hammer iMessage Display
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python/server.py
WorkingDirectory=/home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable hammer
sudo systemctl start hammer
```

## 9. BlueBubbles Webhook

In BlueBubbles on Mac, add webhook:
- URL: `http://<PI_IP>:5000/message`
- Events: New Messages

Get Pi IP:
```bash
hostname -I
```

## 10. Verify

```bash
sudo journalctl -u hammer -f
```

Should see Flask running on 0.0.0.0:5000. Send yourself an iMessage — it should appear on the screen within seconds.

## Notes

- Mic uses `plughw:Device` — stable across reboots, no card number needed. Verify with `arecord -l`
- DISCO_VOICE_URL token is hardcoded in server.py — pull latest from git, don't change manually
- Deploy updates: `git pull && sudo systemctl restart hammer`
