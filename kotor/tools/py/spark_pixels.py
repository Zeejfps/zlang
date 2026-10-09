"""Counts spark-yellow pixels in screenshots (dev tooling for kotor/tools/gfx/duel_sparks.sh).

    python kotor/tools/py/spark_pixels.py MAX PNG...
    python kotor/tools/py/spark_pixels.py --at-least MIN PNG...

A spark pixel is yellowish white: green above 110, green over blue by more than 30 and red within 45 of
green (the Endar Spire's walls are grey, its panels pink, neither passes). Counted over the middle of the
picture (rows 120 to 600, columns 150 to 1130 of a 1280x720 shot: the HUD's corners are outside), less
the door's amber light at columns 520 to 590, rows 350 to 395. Prints the count of each picture and says
FAIL for one over MAX; exit status 1 if any does. The clash sparks that flew through the closed duel door
(gravity along the effect's facing) counted 130 in one shot; the fixed build 7 or less.

--at-least proves the sparks draw at all: it counts only the sparks' bright cores (green above 230, green
over blue by more than 25, red within 30 of green), which the Jedi's beige robe (green 206 at most) and the
grey walls never reach, and says FAIL for a picture with fewer than MIN. Beside the duel a clash's shot has
190 to 490 of them, a shot between clashes none.
"""
import sys

from PIL import Image


def is_spark(r, g, b):
    return g > 110 and g - b > 30 and abs(r - g) < 45


def is_bright_spark(r, g, b):
    return g > 230 and g - b > 25 and abs(r - g) < 30


def count(path, test):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()
    n = 0
    for y in range(120, min(600, h)):
        for x in range(150, min(1130, w)):
            r, g, b = px[x, y]
            if test(r, g, b) and not (520 < x < 590 and 350 < y < 395):
                n += 1
    return n


def main(argv):
    at_least = argv[1] == '--at-least'
    if at_least:
        argv = argv[1:]
    limit = int(argv[1])
    bad = 0
    for path in argv[2:]:
        try:
            n = count(path, is_bright_spark if at_least else is_spark)
        except OSError as e:
            print(f'FAIL {path}: {e}')
            bad = 1
            continue
        failed = n < limit if at_least else n > limit
        if failed:
            bad = 1
        bound = f'at least {limit} bright' if at_least else f'at most {limit}'
        print(f"{'FAIL' if failed else 'ok  '} {path}: {n} spark pixels ({bound})")
    return bad


if __name__ == '__main__':
    sys.exit(main(sys.argv))
