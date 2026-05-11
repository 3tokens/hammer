from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
import ST7789
import threading
import queue

app = Flask(__name__)

font_big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)

disp = ST7789.ST7789()
disp.Init()
disp.bl_DutyCycle(100)

messages = []
display_queue = queue.Queue()

def update_screen():
    disp.bl_DutyCycle(100)
    img = Image.new('RGB', (240, 240), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((50, 10), "HAMMER", font=font_big, fill=(255, 255, 255))
    draw.line((0, 50, 240, 50), fill=(50, 50, 50), width=1)
    if not messages:
        draw.text((10, 100), "No messages", font=font_small, fill=(80, 80, 80))
    else:
        y = 60
        for msg in messages[-4:]:
            draw.text((10, y), msg['sender'], font=font_small, fill=(100, 255, 100))
            draw.text((10, y+20), msg['text'][:25], font=font_small, fill=(255, 255, 255))
            y += 50
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
        messages.append({'sender': sender, 'text': text})
        display_queue.put(True)

    return 'ok'

threading.Thread(target=display_worker, daemon=True).start()
app.run(host='0.0.0.0', port=5000, threaded=True)
