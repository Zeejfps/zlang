"""Crops the same box out of several screenshots and lays them out in a grid (exploration only).

    python kotor/tools/py/montage.py OUT.png COLS X0 Y0 X1 Y1 SCALE IN.png [IN.png ...]

Each tile is labelled with the last part of its file name (kotor/out/frc/anim1_72.png -> 72).
"""
import os
import sys

from PIL import Image, ImageDraw

out, cols = sys.argv[1], int(sys.argv[2])
x0, y0, x1, y1 = map(int, sys.argv[3:7])
scale = float(sys.argv[7])
tiles = []
for f in sys.argv[8:]:
    im = Image.open(f).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    label = os.path.splitext(os.path.basename(f))[0].split("_")[-1]
    d.rectangle([0, 0, 8 * len(label) + 6, 14], fill=(0, 0, 0))
    d.text((3, 2), label, fill=(255, 255, 0))
    tiles.append(im)
w, h = tiles[0].size
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * w, (i // cols) * h))
sheet.save(out)
print(out, sheet.size)
