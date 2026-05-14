# Hammer Project Memory

## Project Overview
Raspberry Pi message display device. Shows iMessages on ST7789 1.3" LCD HAT (240x240).
Receives messages via BlueBubbles webhooks, plays TTS via Bluetooth speaker.

## Key Files
- `/home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python/server.py` — main app (Flask)
- `/home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python/config.py` — Waveshare HAT GPIO setup (uses gpiozero)
- `/home/pi/1.3inch_LCD_HAT_code/1.3inch_LCD_HAT_code/python/ST7789.py` — local display driver (inherits config.RaspberryPi)
- Mac repo: `/Users/nishantsingh/Documents/GitHub/hammer/server.py`

## Deploy Command
```bash
git pull && sudo systemctl restart hammer
```

## GPIO — Waveshare 1.3" LCD HAT
config.py creates gpiozero DigitalInputDevice objects for ALL buttons during ST7789 init.
Access via `disp.GPIO_KEY*_PIN.value` — do NOT use gpiod or gpiozero Button() separately (conflict).
- KEY1: GPIO 21 (`disp.GPIO_KEY1_PIN`)
- KEY2: GPIO 20 (`disp.GPIO_KEY2_PIN`)
- KEY3: GPIO 16 (`disp.GPIO_KEY3_PIN`)
- Joystick UP: GPIO 6 (`disp.GPIO_KEY_UP_PIN`)
- Joystick DOWN: GPIO 19 (`disp.GPIO_KEY_DOWN_PIN`)
- Joystick LEFT: GPIO 5, RIGHT: GPIO 26, PRESS: GPIO 13

## Signal Handler Required
Must call `disp.module_exit()` on SIGTERM/SIGINT to release gpiozero/lgpio pins cleanly.
Without it, rapid restarts leave stale pin handles causing GPIOPinInUse crashes.

## Audio
- USB mic: use `plughw:Device` (not card number — changes across setups), record at 16000Hz S16_LE
- Bluetooth speaker: JBL Flip 5, MAC `20:18:5B:61:8E:B5`, use `bluealsa`
- Playback requires resampling: `sox -v 5 file.wav -r 44100 -c 2 -t alsa bluealsa`
- TTS: espeak-ng piped to aplay -D bluealsa

## BlueBubbles
- URL: `https://bb.produceapp.ai` (CloudFlare tunnel — fixed, not rotating)
- Password: set BB_PASSWORD in server.py
- Local port: 1234
- Send attachment API: `POST /api/v1/message/attachment`
  - Required fields: `chatGuid`, `name`, `tempGuid` (uuid4), file as multipart `attachment`
  - Use `timeout=(10, 120)` — CloudFlare tunnel is slow to respond but upload is fast
  - Use fire-and-forget thread so screen updates immediately

## CloudFlare Tunnel Setup (Mac)
Tunnel name: `bluebubbles`, routes `bb.produceapp.ai` → `http://localhost:1234`
Credentials: `~/.cloudflared/cert.pem` and `~/.cloudflared/<tunnel-uuid>.json`
Config: `~/.cloudflared/config.yml`

### Critical: launchd plist must include explicit paths
The service runs as root so `~` = `/var/root/` — it won't find user credentials automatically.
Plist at `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist` must be:
```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/local/bin/cloudflared</string>
    <string>tunnel</string>
    <string>--origincert</string>
    <string>/Users/nishantsingh/.cloudflared/cert.pem</string>
    <string>--credentials-file</string>
    <string>/Users/nishantsingh/.cloudflared/<tunnel-uuid>.json</string>
    <string>--config</string>
    <string>/Users/nishantsingh/.cloudflared/config.yml</string>
    <string>run</string>
    <string>bluebubbles</string>
</array>
```
Without `--config`, tunnel connects but returns 503 (ignores ingress rules).
Without `--origincert`/`--credentials-file`, tunnel fails with "cannot determine origin cert" and loops.

### Debugging tunnel issues
- `cloudflared tunnel list` — check CONNECTIONS column (empty = not routing)
- `tail -20 /Library/Logs/com.cloudflare.cloudflared.err.log` — see why it's failing
- `curl http://localhost:1234/api/v1/ping?password=...` — test BB locally
- `curl https://bb.produceapp.ai/api/v1/ping?password=...` — test through tunnel
- 530 from Pi = tunnel down; 503 = tunnel up but not routing to BB; 500 = BB internal error

## Voice-to-iMessage Feature
- KEY1/KEY2 toggle: first press starts recording, second press stops + sends
- Joystick PRESS toggle: replies to last received message sender (any contact, no mapping needed)
- Joystick LEFT/RIGHT: reserved for select mode (future — highlight message to reply to)
- KEY3: reserved for AI queries (future)
- Records WAV → POSTs to disco `/sonic/hammer/send-voice` → Groq transcribes → BB sends as text
- No ffmpeg, no attachment API, no Private API needed — text via AppleScript works fine
- CONTACTS dict maps key names to phone numbers
- KEY1 → `+14802866666`, KEY2 → `+15098608223` (Melanie)
- `last_sender` global tracks most recent non-Me sender for joystick reply
- Disco endpoint: `hammer_send_voice` in hypersonic/sonic/views.py
- Screen shows transcript briefly after send

## Why not BB attachment API
- Sending attachments requires SIP disabled + Private API injected
- SIP is enabled on Mac — attachments hang for 20 min then 500 error
- Text messages via AppleScript work without Private API ✓
