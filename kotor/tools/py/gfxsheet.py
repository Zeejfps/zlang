"""Lays screenshots out side by side with labels, for before/after pictures of an option (dev tooling).

    python kotor/tools/py/gfxsheet.py OUT.png COLS CELL_WIDTH [--crop X0,Y0,X1,Y1] LABEL=IN.png [LABEL=IN.png ...]

--crop takes the same box (in the first picture's pixels, scaled for the others) out of every picture, to
show a detail enlarged instead of the whole frame. Each cell is CELL_WIDTH wide.
"""
import sys

from PIL import Image, ImageDraw


def main(argv):
    out, cols, cell_w = argv[0], int(argv[1]), int(argv[2])
    rest = argv[3:]
    crop = None
    if rest and rest[0] == "--crop":
        crop = tuple(int(v) for v in rest[1].split(","))
        rest = rest[2:]
    tiles = []
    base_w = None
    for item in rest:
        label, path = item.split("=", 1)
        im = Image.open(path).convert("RGB")
        if base_w is None:
            base_w = im.width
        if crop:
            k = im.width / base_w
            im = im.crop(tuple(int(v * k) for v in crop))
        h = max(1, im.height * cell_w // im.width)
        im = im.resize((cell_w, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 8 * len(label) + 8, 16], fill=(0, 0, 0))
        d.text((4, 3), label, fill=(255, 255, 0))
        tiles.append(im)
    rows = (len(tiles) + cols - 1) // cols
    cell_h = max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * cell_w + (cols - 1) * 4, rows * cell_h + (rows - 1) * 4), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (cell_w + 4), (i // cols) * (cell_h + 4)))
    sheet.save(out)
    print(out, sheet.size)


main(sys.argv[1:])
