"""Finds cuts and one-frame blips in a run of consecutive screenshots (exploration only).

    python kotor/tools/py/framediff.py DIR [THRESHOLD]

DIR holds fNNNNN.png from `kotor.exe --screenshot-range FROM:TO:DIR`. Prints every frame step whose
mean difference is over THRESHOLD (default 12, on a 0..255 scale, at 80x45) and marks a *blip*: a frame
that differs from both neighbours while those two resemble each other (an odd frame between two equal
ones), and a *flash*: the same over up to 4 frames.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

d = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
files = sorted(glob.glob(os.path.join(d, "f*.png")))
nums = [int(os.path.basename(f)[1:6]) for f in files]
imgs = [np.asarray(Image.open(f).convert("RGB").resize((80, 45), Image.BILINEAR), dtype=np.float32) for f in files]


def diff(a, b):
    return float(np.abs(imgs[a] - imgs[b]).mean())


step = [diff(i, i + 1) for i in range(len(imgs) - 1)]
print("frames", nums[0], "to", nums[-1], "count", len(imgs))
for i, s in enumerate(step):
    if s < thr:
        continue
    tags = []
    # a blip: i+1 differs from i and from i+2, while i and i+2 resemble each other
    if i + 2 < len(imgs) and diff(i, i + 2) < thr / 2:
        tags.append("BLIP at %d" % nums[i + 1])
    else:
        for n in (2, 3, 4):
            if i + 1 + n < len(imgs) and diff(i, i + 1 + n) < thr / 2:
                tags.append("FLASH %d frames %d..%d" % (n, nums[i + 1], nums[i + n]))
                break
    print("%5d -> %5d  diff %6.1f  %s" % (nums[i], nums[i + 1], s, "; ".join(tags)))
