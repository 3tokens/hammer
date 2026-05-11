from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
import ST7789
import threading
import queue
import textwrap
import time
import subprocess

def get_bt_speaker():
    """Return ALSA device string for first connected A2DP Bluetooth device."""
    try:
        result = subprocess.run(['aplay', '-L'], capture_output=True, text=True, timeout=3)
        for line in result.stdout.splitlines():
            if line.startswith('bluealsa') and 'a2dp' in line.lower():
                return line.strip()
    except Exception:
        pass
    return None

def speak(text):
    dev = get_bt_speaker()
    if not dev:
        print("No Bluetooth speaker connected, skipping TTS")
        return
    try:
        tts = subprocess.Popen(['espeak-ng', '-a', '200', text, '--stdout'], stdout=subprocess.PIPE)
        subprocess.Popen(['aplay', '-D', dev], stdin=tts.stdout)
        tts.stdout.close()
    except Exception as e:
        print(f"TTS error: {e}")

app = Flask(__name__)

font_big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)

disp = ST7789.ST7789()
disp.Init()
disp.bl_DutyCycle(100)

messages = []
display_queue = queue.Queue()
scroll_offset = 0
MAX_MESSAGES  = 20
MAX_VISIBLE_LINES = 7  # (230 - 82) // 20

def build_lines():
    """Flat list of (text, color) for all messages, newest first."""
    lines = []
    for msg in reversed(messages):
        lines.append((msg['sender'][:22], (100, 255, 100)))
        for t in textwrap.wrap(msg['text'], width=22):
            lines.append((t, (255, 255, 255)))
        lines.append(('', (0, 0, 0)))  # blank separator
    return lines

def scroll_up(channel):
    global scroll_offset
    if scroll_offset > 0:
        scroll_offset -= 1
        display_queue.put(True)

def scroll_down(channel):
    global scroll_offset
    total = len(build_lines())
    if scroll_offset < max(0, total - MAX_VISIBLE_LINES):
        scroll_offset += 1
        display_queue.put(True)

def joystick_poller():
    prev_up = prev_down = 0
    while True:
        up   = disp.GPIO_KEY_UP_PIN.value
        down = disp.GPIO_KEY_DOWN_PIN.value
        if up   and not prev_up:   scroll_up(None)
        if down and not prev_down: scroll_down(None)
        prev_up, prev_down = up, down
        time.sleep(0.05)

threading.Thread(target=joystick_poller, daemon=True).start()

def update_screen():
    img = Image.new('RGB', (240, 240), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((50, 10), "HAMMER", font=font_big, fill=(255, 255, 255))
    draw.line((0, 50, 240, 50), fill=(50, 50, 50), width=1)
    if not messages:
        draw.text((10, 100), "No messages", font=font_small, fill=(80, 80, 80))
    else:
        all_lines = build_lines()
        visible = all_lines[scroll_offset: scroll_offset + MAX_VISIBLE_LINES]
        y = 60
        for text, color in visible:
            if text:
                draw.text((10, y), text, font=font_small, fill=color)
            y += 20
        if scroll_offset + MAX_VISIBLE_LINES < len(all_lines):
            draw.text((10, 228), "v more", font=font_small, fill=(80, 80, 80))
    disp.ShowImage(img)

def display_worker():
    update_screen()
    while True:
        try:
            display_queue.get(timeout=60)
            update_screen()
        except:
            pass

@app.route('/message', methods=['POST'])
def receive_message():
    data = request.json

    # Handle both BlueBubbles format and simple test format
    if 'type' in data and data['type'] == 'new-message':
        msg_data = data['data']
        text = msg_data.get('text', '')
        is_from_me = msg_data.get('isFromMe', False)
        handle = msg_data.get('handle', {})
        sender = handle.get('address', 'Unknown') if handle else 'Me'
        if is_from_me:
            sender = 'Me'
    else:
        sender = data.get('sender', 'Unknown')
        text = data.get('text', '')

    if text:
        global scroll_offset
        messages.append({'sender': sender, 'text': text})
        if len(messages) > MAX_MESSAGES:
            messages.pop(0)
        scroll_offset = 0
        display_queue.put(True)
        threading.Thread(target=speak, args=(f"Message from {sender}. {text}",), daemon=True).start()

    return 'ok'

threading.Thread(target=display_worker, daemon=True).start()
app.run(host='0.0.0.0', port=5000, threaded=True)
