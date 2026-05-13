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
import uuid

BB_URL = "https://movies-nottingham-era-teaching.trycloudflare.com"
BB_PASSWORD = "Nishan123"
CONTACTS = {
    'KEY1': {'name': 'Contact 1', 'number': '+14802866666'},
}
MIC_DEVICE = 'plughw:3,0'

def get_bt_speaker():
    try:
        result = subprocess.run(['aplay', '-L'], capture_output=True, text=True, timeout=3)
        if 'bluealsa' in result.stdout:
            return 'bluealsa'
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
MAX_MESSAGES = 20
MAX_VISIBLE_LINES = 7

# Recording state
recording_proc = None
recording_tmpfile = None
recording_key = None
recording_lock = threading.Lock()
status_msg = None

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
    set_status("Recording...\nPress KEY1 to send")

def stop_and_send():
    global recording_proc, recording_tmpfile, recording_key
    with recording_lock:
        proc = recording_proc
        tmpfile = recording_tmpfile
        key = recording_key
        recording_proc = None
        recording_tmpfile = None
        recording_key = None

    if proc:
        proc.terminate()
        proc.wait()

    if not tmpfile or not os.path.exists(tmpfile):
        set_status("No audio recorded")
        time.sleep(2)
        set_status(None)
        return

    contact = CONTACTS.get(key, {})
    number = contact.get('number', '')

    set_status("Converting...")
    m4a_file = tmpfile.replace('.wav', '.m4a')
    r = subprocess.run(['ffmpeg', '-y', '-i', tmpfile, '-c:a', 'aac', m4a_file], capture_output=True)
    print(f"ffmpeg exit={r.returncode} exists={os.path.exists(m4a_file)}", flush=True)
    os.unlink(tmpfile)

    if not os.path.exists(m4a_file):
        set_status("Convert failed!")
        time.sleep(2)
        set_status(None)
        return

    def upload():
        ok = send_audio(number, m4a_file)
        if os.path.exists(m4a_file):
            os.unlink(m4a_file)
        if not ok:
            print("Background send failed", flush=True)

    threading.Thread(target=upload, daemon=True).start()
    set_status("Sent!")
    speak("Audio message sent.")
    time.sleep(2)
    set_status(None)

def send_audio(number, filepath):
    try:
        with open(filepath, 'rb') as f:
            resp = requests.post(
                f"{BB_URL}/api/v1/message/attachment",
                params={'password': BB_PASSWORD},
                data={'chatGuid': f'iMessage;-;{number}', 'name': os.path.basename(filepath), 'tempGuid': str(uuid.uuid4())},
                files={'attachment': (os.path.basename(filepath), f, 'audio/mp4')},
                timeout=(10, 120)
            )
        print(f"BlueBubbles: {resp.status_code} {resp.text}", flush=True)
        return resp.ok
    except Exception as e:
        print(f"Send error: {e}", flush=True)
        return False

def on_key1():
    with recording_lock:
        is_recording = recording_proc is not None
    if is_recording:
        threading.Thread(target=stop_and_send, daemon=True).start()
    else:
        start_recording('KEY1')

def joystick_poller():
    prev_up = prev_down = 0
    while True:
        up   = disp.GPIO_KEY_UP_PIN.value
        down = disp.GPIO_KEY_DOWN_PIN.value
        if up   and not prev_up:   scroll_up(None)
        if down and not prev_down: scroll_down(None)
        prev_up, prev_down = up, down
        time.sleep(0.05)

def key_poller():
    prev1 = 0
    while True:
        k1 = disp.GPIO_KEY1_PIN.value
        if k1 and not prev1:
            on_key1()
        prev1 = k1
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
