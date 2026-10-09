"""Counts spark-yellow pixels in screenshots (dev tooling for kotor/tools/gfx/duel_sparks.sh).

    python kotor/tools/py/spark_pixels.py MAX PNG...

A spark pixel is yellowish white: green above 110, green over blue by more than 30 and red within 45 of
green (the Endar Spire's walls are grey, its panels pink, neither passes). Counted over the middle of the
picture (rows 120 to 600, columns 150 to 1130 of a 1280x720 shot: the HUD's corners are outside), less
the door's amber light at columns 520 to 590, rows 350 to 395. Prints the count of each picture and says
FAIL for one over MAX; exit status 1 if any does. The clash sparks that flew through the closed duel door
(gravity along the effect's facing) counted 130 in one shot; the fixed build 7 or less.
"""
import sys

from PIL import Image


def count(path):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()
    n = 0
    for y in range(120, min(600, h)):
        for x in range(150, min(1130, w)):
            r, g, b = px[x, y]
            if g > 110 and g - b > 30 and abs(r - g) < 45 and not (520 < x < 590 and 350 < y < 395):
                n += 1
    return n


def main(argv):
    limit = int(argv[1])
    bad = 0
    for path in argv[2:]:
        try:
            n = count(path)
        except OSError as e:
            print(f'FAIL {path}: {e}')
            bad = 1
            continue
        verdict = 'FAIL' if n > limit else 'ok  '
        if n > limit:
            bad = 1
        print(f'{verdict} {path}: {n} spark pixels (at most {limit})')
    return bad


if __name__ == '__main__':
    sys.exit(main(sys.argv))
