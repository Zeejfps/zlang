"""A contact sheet of pictures, 3 to a row, each labelled with its file name: contact_sheet.py OUT.png IMG...
(dev tooling for the playthrough sweeps)."""
import sys
from PIL import Image, ImageDraw

out = sys.argv[1]
names = sys.argv[2:]
w, h = 640, 360
cols = 3
rows = (len(names) + cols - 1) // cols
sheet = Image.new('RGB', (w * cols, h * rows))
draw = ImageDraw.Draw(sheet)
for k, n in enumerate(names):
    try:
        im = Image.open(n).convert('RGB').resize((w, h))
    except Exception:
        continue
    x, y = (k % cols) * w, (k // cols) * h
    sheet.paste(im, (x, y))
    label = n.rsplit('/', 1)[-1].replace('sweep_', '').replace('_shot.png', '')
    draw.rectangle((x, y, x + 150, y + 14), fill=(0, 0, 0))
    draw.text((x + 3, y + 1), label, fill=(255, 255, 0))
sheet.save(out)
