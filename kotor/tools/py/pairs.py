"""Counts picture jumps over a threshold that come in consecutive pairs (a cut that took two frames, or a frame in between):
    python kotor/tools/py/pairs.py DIR [THRESHOLD]   (DIR as for framediff.py; exploration only)"""
import glob
import os
import sys

import numpy as np
from PIL import Image

d = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
files = sorted(glob.glob(os.path.join(d, "f*.png")))
nums = [int(os.path.basename(f)[1:6]) for f in files]
prev = None
steps = []
for f in files:
    im = np.asarray(Image.open(f).convert("RGB").resize((80, 45), Image.BILINEAR), dtype=np.float32)
    steps.append(0.0 if prev is None else float(np.abs(im - prev).mean()))
    prev = im
big = [i for i, s in enumerate(steps) if s >= thr]
pairs = [(nums[i - 1], nums[i], steps[i - 1], steps[i]) for i in big if i - 1 in big]
print("jumps %d, in consecutive pairs %d" % (len(big), len(pairs)))
for p in pairs[:40]:
    print("  %d->%d (%.1f) then ->%d (%.1f)" % (p[0] - 1, p[0], p[2], p[1], p[3]))
