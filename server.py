from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
import ST7789
import threading
import queue
import textwrap
import RPi.GPIO as GPIO

KEY_UP   = 6
KEY_DOWN = 19

app = Flask(__name__)

font_big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)

disp = ST7789.ST7789()
disp.Init()
disp.bl_DutyCycle(100)

messages = []
display_queue = queue.Queue()
scroll_offset = 0

MAX_VISIBLE_LINES = 7  # (230 - 82) // 20

def get_current_lines():
    if not messages:
        return [], []
    msg = messages[-1]
    sender_lines = [msg['sender']]
    text_lines = textwrap.wrap(msg['text'], width=22)
    return sender_lines, text_lines

def scroll_up(channel):
    global scroll_offset
    if scroll_offset > 0:
        scroll_offset -= 1
        display_queue.put(True)

def scroll_down(channel):
    global scroll_offset
    _, text_lines = get_current_lines()
    if scroll_offset < max(0, len(text_lines) - MAX_VISIBLE_LINES):
        scroll_offset += 1
        display_queue.put(True)

GPIO.setmode(GPIO.BCM)
GPIO.setup(KEY_UP,   GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(KEY_UP,   GPIO.FALLING, callback=scroll_up,   bouncetime=200)
GPIO.add_event_detect(KEY_DOWN, GPIO.FALLING, callback=scroll_down, bouncetime=200)

def update_screen():
    disp.bl_DutyCycle(100)
    img = Image.new('RGB', (240, 240), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((50, 10), "HAMMER", font=font_big, fill=(255, 255, 255))
    draw.line((0, 50, 240, 50), fill=(50, 50, 50), width=1)
    if not messages:
        draw.text((10, 100), "No messages", font=font_small, fill=(80, 80, 80))
    else:
        sender_lines, text_lines = get_current_lines()
        y = 60
        draw.text((10, y), sender_lines[0][:22], font=font_small, fill=(100, 255, 100))
        y += 22
        visible = text_lines[scroll_offset: scroll_offset + MAX_VISIBLE_LINES]
        for line in visible:
            draw.text((10, y), line, font=font_small, fill=(255, 255, 255))
            y += 20
        if scroll_offset + MAX_VISIBLE_LINES < len(text_lines):
            draw.text((10, 228), "v more", font=font_small, fill=(80, 80, 80))
    disp.ShowImage(img)

def display_worker():
    update_screen()
    while True:
        try:
            display_queue.get(timeout=10)
        except:
            pass
        update_screen()

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
        scroll_offset = 0
        display_queue.put(True)

    return 'ok'

threading.Thread(target=display_worker, daemon=True).start()
app.run(host='0.0.0.0', port=5000, threaded=True)
