"""Compares two pictures pixel for pixel (exploration only): the Original Look check of the enhanced renderer.

    python kotor/tools/py/imgdiff.py A.png B.png [DIFF.png]

Prints how many pixels differ, the largest channel difference and the mean, and with DIFF.png writes the
difference (times 8) to look at.
"""
import sys

import numpy as np
from PIL import Image

a = np.asarray(Image.open(sys.argv[1]).convert("RGB"), dtype=np.int32)
b = np.asarray(Image.open(sys.argv[2]).convert("RGB"), dtype=np.int32)
if a.shape != b.shape:
    print("sizes differ:", a.shape, b.shape)
    sys.exit(2)
d = np.abs(a - b)
px = int((d.max(axis=2) > 0).sum())
print("%d of %d pixels differ, max %d, mean %.4f" % (px, a.shape[0] * a.shape[1], int(d.max()), float(d.mean())))
if len(sys.argv) > 3:
    Image.fromarray(np.clip(d * 8, 0, 255).astype(np.uint8)).save(sys.argv[3])
sys.exit(0 if px == 0 else 1)
