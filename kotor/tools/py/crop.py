"""Crops the same box out of several screenshots and stacks them (exploration only).

    python kotor/tools/py/crop.py OUT.png X0 Y0 X1 Y1 SCALE IN.png [IN.png ...]
"""
import os
import sys

from PIL import Image, ImageDraw

out, x0, y0, x1, y1, scale = sys.argv[1], *map(int, sys.argv[2:6]), float(sys.argv[6])
tiles = []
for f in sys.argv[7:]:
    im = Image.open(f).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    label = os.path.splitext(os.path.basename(f))[0].split("_")[-1]
    d.rectangle([0, 0, 8 * len(label) + 6, 14], fill=(0, 0, 0))
    d.text((3, 2), label, fill=(255, 255, 0))
    tiles.append(im)
sheet = Image.new("RGB", (tiles[0].width, sum(t.height for t in tiles)))
y = 0
for t in tiles:
    sheet.paste(t, (0, y))
    y += t.height
sheet.save(out)
print(out, sheet.size)
