"""Tiles screenshots into one contact sheet (exploration only): a frame strip to look at with Read.

    python kotor/tools/py/sheet.py OUT.png COLUMNS CELL_WIDTH IN.png [IN.png ...]

Each cell is the picture scaled to CELL_WIDTH pixels wide, labelled with its file name (the part
after the last underscore, so b1_1040.png reads 1040).
"""

import os
import sys

from PIL import Image, ImageDraw


def main(argv):
    if len(argv) < 5:
        print(__doc__)
        return 2
    out, cols, cell_w = argv[1], int(argv[2]), int(argv[3])
    files = argv[4:]
    tiles = []
    for f in files:
        im = Image.open(f).convert("RGB")
        h = max(1, im.height * cell_w // im.width)
        tiles.append((os.path.splitext(os.path.basename(f))[0].split("_")[-1], im.resize((cell_w, h), Image.LANCZOS)))
    cell_h = max(t[1].height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 8 * len(label) + 6, y + 14], fill=(0, 0, 0))
        d.text((x + 3, y + 2), label, fill=(255, 255, 0))
    sheet.save(out)
    print(out, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
