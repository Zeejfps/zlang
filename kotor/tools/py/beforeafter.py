"""Stacks two sets of screenshots of the same frames, before above after (exploration only).

    python kotor/tools/py/beforeafter.py OUT.png CELL_WIDTH BEFORE_PREFIX AFTER_PREFIX FRAME [FRAME ...]

BEFORE_PREFIX and AFTER_PREFIX are the run names of kotor/out/pt (b1 for b1_1080.png). Each row is
the frames of one set, a label at the left says which.
"""

import sys

from PIL import Image, ImageDraw


def row(prefix, frames, cell_w):
    tiles = []
    for f in frames:
        im = Image.open(f"kotor/out/pt/{prefix}_{f}.png").convert("RGB")
        h = max(1, im.height * cell_w // im.width)
        im = im.resize((cell_w, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 8 * len(str(f)) + 6, 14], fill=(0, 0, 0))
        d.text((3, 2), str(f), fill=(255, 255, 0))
        tiles.append(im)
    return tiles


def main(argv):
    out, cell_w, before, after = argv[1], int(argv[2]), argv[3], argv[4]
    frames = argv[5:]
    per = 4
    rows = []
    for i in range(0, len(frames), per):
        chunk = frames[i:i + per]
        for name, prefix in (("BEFORE", before), ("AFTER", after)):
            tiles = row(prefix, chunk, cell_w)
            strip = Image.new("RGB", (cell_w * per, tiles[0].height), (20, 20, 20))
            for k, t in enumerate(tiles):
                strip.paste(t, (k * cell_w, 0))
            d = ImageDraw.Draw(strip)
            d.rectangle([cell_w * per - 60, 0, cell_w * per, 14], fill=(0, 0, 0))
            d.text((cell_w * per - 56, 2), name, fill=(120, 255, 120) if name == "AFTER" else (255, 120, 120))
            rows.append(strip)
    sheet = Image.new("RGB", (cell_w * per, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main(sys.argv)
