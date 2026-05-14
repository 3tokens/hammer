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
sudo apt install -y python3-pip python3-lgpio git ffmpeg arecord
pip3 install flask pillow requests
```

Enable SPI (required for the display):
```bash
sudo raspi-config nonint do_spi 0
```

## 4. Waveshare 1.3" LCD HAT Code

```bash
cd /home/pi
git clone https://github.com/waveshare/1.3inch_LCD_HAT.git 1.3inch_LCD_HAT_code
```

## 5. Clone Hammer Repo

```bash
cd /home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python
git clone https://github.com/nishantsingh/hammer.git .
# (copies server.py into the same dir as ST7789.py and config.py)
```

## 6. Check Mic Device

Plug in USB mic, then:
```bash
arecord -l
```
Note the card number for your USB mic. Update `MIC_DEVICE` in server.py if it's not `plughw:3,0`.

## 7. Systemd Service

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

## 8. BlueBubbles Webhook

In BlueBubbles on Mac, add webhook:
- URL: `http://<PI_IP>:5000/message`
- Events: New Messages

Get Pi IP:
```bash
hostname -I
```

## 9. Verify

```bash
sudo journalctl -u hammer -f
```

Should see Flask running on 0.0.0.0:5000. Send yourself an iMessage with "dd" prefix — it should appear on the screen.

## Notes

- Mic card number may differ on each setup — always check with `arecord -l`
- BB_PASSWORD and DISCO_VOICE_URL token are hardcoded in server.py — pull latest from git
- Deploy updates: `git pull && sudo systemctl restart hammer`
