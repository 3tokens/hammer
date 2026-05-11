from PIL import Image, ImageDraw, ImageFont
import ST7789

disp = ST7789.ST7789()
disp.Init()
disp.clear()

img = Image.new('RGB', (240, 240), (0, 0, 0))
draw = ImageDraw.Draw(img)

font_big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)

draw.text((50, 30), "HAMMER", font=font_big, fill=(255, 255, 255))
draw.line((0, 70, 240, 70), fill=(50, 50, 50), width=1)
draw.text((10, 90), "From: Melanie", font=font_small, fill=(100, 255, 100))
draw.text((10, 120), "Are you coming home?", font=font_small, fill=(255, 255, 255))
draw.text((10, 200), "No new messages", font=font_small, fill=(80, 80, 80))

disp.ShowImage(img)
print("Done!")
