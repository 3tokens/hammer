from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
import ST7789
import threading
import queue
import textwrap
import time
import subprocess
import tempfile
import os
import requests
import signal
import sys

DISCO_VOICE_URL = "https://www.ddisco.com/sonic/hammer/send-voice?token=4bea0fd0218de9f99f19929ef61e16841ff938eee60604d166c05a17353c9844&owner=+14802866666"
CONTACTS = {
    'KEY1': {'name': 'Contact 1', 'number': '+14802866666'},
    'KEY2': {'name': 'Wife', 'number': '+15098608223'},
}
MIC_DEVICE = 'plughw:Device'


app = Flask(__name__)

font_big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)

disp = ST7789.ST7789()
disp.Init()
disp.bl_DutyCycle(100)

messages = []
display_queue = queue.Queue()
scroll_offset = 0
MAX_MESSAGES = 20
MAX_VISIBLE_LINES = 7

# Recording state
recording_proc = None
recording_tmpfile = None
recording_key = None
recording_lock = threading.Lock()
uploading = False
status_msg = None
last_sender = None


def build_lines():
    lines = []
    for msg in reversed(messages):
        lines.append((msg['sender'][:22], (100, 255, 100)))
        for t in textwrap.wrap(msg['text'], width=22):
            lines.append((t, (255, 255, 255)))
        lines.append(('', (0, 0, 0)))
    return lines

def set_status(msg):
    global status_msg
    status_msg = msg
    display_queue.put(True)

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

def start_recording(key):
    global recording_proc, recording_tmpfile, recording_key
    tmpfile = tempfile.mktemp(suffix='.wav')
    proc = subprocess.Popen(['arecord', '-D', MIC_DEVICE, '-f', 'S16_LE', '-r', '16000', tmpfile])
    recording_proc = proc
    recording_tmpfile = tmpfile
    recording_key = key
    if key == 'JOYSTICK':
        name = last_sender or 'last sender'
        set_status(f"Reply to:\n{name[:20]}\nPress joystick")
    else:
        contact = CONTACTS.get(key, {})
        set_status(f"Recording...\nTo: {contact.get('name','?')}\nPress again to send")

def stop_and_send():
    global recording_proc, recording_tmpfile, recording_key, uploading
    with recording_lock:
        proc = recording_proc
        tmpfile = recording_tmpfile
        key = recording_key
        recording_proc = None
        recording_tmpfile = None
        recording_key = None
        uploading = True

    if proc:
        proc.terminate()
        proc.wait()

    if not tmpfile or not os.path.exists(tmpfile):
        set_status("No audio recorded")
        time.sleep(2)
        set_status(None)
        with recording_lock:
            uploading = False
        return

    if key == 'JOYSTICK':
        number = last_sender or ''
    else:
        contact = CONTACTS.get(key, {})
        number = contact.get('number', '')

    set_status("Transcribing...")
    ok, transcript = send_audio(number, tmpfile)
    if os.path.exists(tmpfile):
        os.unlink(tmpfile)
    if ok:
        set_status(f"Sent:\n{transcript[:60]}")
    else:
        set_status("Send failed!")
        print("Background send failed", flush=True)
    time.sleep(3)
    set_status(None)
    with recording_lock:
        uploading = False

def send_audio(number, filepath):
    try:
        with open(filepath, 'rb') as f:
            resp = requests.post(
                DISCO_VOICE_URL,
                data={'to': number},
                files={'audio': (os.path.basename(filepath), f, 'audio/wav')},
                timeout=(10, 60)
            )
        print(f"Disco: {resp.status_code} {resp.text[:120]}", flush=True)
        if resp.ok:
            transcript = resp.json().get('transcript', '')
            return True, transcript
        return False, ''
    except Exception as e:
        print(f"Send error: {e}", flush=True)
        return False, ''

def on_key(key):
    with recording_lock:
        is_recording = recording_proc is not None
        is_uploading = uploading
    if is_uploading:
        return
    if is_recording:
        threading.Thread(target=stop_and_send, daemon=True).start()
    else:
        start_recording(key)

def joystick_poller():
    prev_up = prev_down = prev_press = 0
    while True:
        up    = disp.GPIO_KEY_UP_PIN.value
        down  = disp.GPIO_KEY_DOWN_PIN.value
        press = disp.GPIO_KEY_PRESS_PIN.value
        if up    and not prev_up:    scroll_up(None)
        if down  and not prev_down:  scroll_down(None)
        if press and not prev_press:
            on_key('JOYSTICK')
        prev_up, prev_down, prev_press = up, down, press
        time.sleep(0.05)

def key_poller():
    prev1 = prev2 = 0
    while True:
        k1 = disp.GPIO_KEY1_PIN.value
        k2 = disp.GPIO_KEY2_PIN.value
        if k1 and not prev1:
            on_key('KEY1')
        if k2 and not prev2:
            on_key('KEY2')
        prev1, prev2 = k1, k2
        time.sleep(0.05)

def cleanup(signum, frame):
    disp.module_exit()
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

threading.Thread(target=joystick_poller, daemon=True).start()
threading.Thread(target=key_poller, daemon=True).start()

def update_screen():
    img = Image.new('RGB', (240, 240), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((50, 10), "HAMMER", font=font_big, fill=(255, 255, 255))
    draw.line((0, 50, 240, 50), fill=(50, 50, 50), width=1)
    if status_msg:
        y = 80
        for line in status_msg.split('\n'):
            draw.text((10, y), line, font=font_small, fill=(255, 200, 0))
            y += 24
    elif not messages:
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
        global scroll_offset, last_sender
        messages.append({'sender': sender, 'text': text})
        if len(messages) > MAX_MESSAGES:
            messages.pop(0)
        if sender != 'Me':
            last_sender = sender
        scroll_offset = 0
        display_queue.put(True)

    return 'ok'

threading.Thread(target=display_worker, daemon=True).start()
app.run(host='0.0.0.0', port=5000, threaded=True)
