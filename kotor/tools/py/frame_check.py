"""Fails when a screenshot is mostly black or empty (dev tooling for kotor/tools/camcheck).

    python kotor/tools/py/frame_check.py [--min-mean M] [--min-lit S] [--min-std D] PNG...

For each picture, over its middle (rows 18% to 82%, columns 5% to 95%: the conversation's letterbox
bars, the subtitle and the HUD's corners are outside it):

    mean   the mean luminance, 0..255
    lit    the share of pixels with a luminance of 6 or more (not black)
    std    the standard deviation of the luminance (a flat frame has none)

and says FAIL when the mean is under M (default 10), the lit share under S (default 0.5), or the
deviation under D (default 6). Exit status 1 if any picture fails or cannot be read. The Taris
apartment's black screen (a camera outside the walls, a few far towers in the void) measured mean 7.2,
lit 0.12; the darkest healthy shot, the wake-up cut seen from the bed, measured mean 13.8, lit 0.80.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image


def measure(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img, dtype=np.float32)
    h, w, _ = a.shape
    a = a[int(h * 0.18):int(h * 0.82), int(w * 0.05):int(w * 0.95)]
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return float(luma.mean()), float((luma >= 6.0).mean()), float(luma.std())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-mean", type=float, default=10.0)
    p.add_argument("--min-lit", type=float, default=0.5)
    p.add_argument("--min-std", type=float, default=6.0)
    p.add_argument("pictures", nargs="+")
    args = p.parse_args()
    failed = 0
    for path in args.pictures:
        name = os.path.basename(path)
        if not os.path.exists(path):
            print(f"FAIL {name}: no such picture (the run did not reach the frame)")
            failed += 1
            continue
        try:
            mean, lit, std = measure(path)
        except Exception as e:  # unreadable image
            print(f"FAIL {name}: {e}")
            failed += 1
            continue
        why = []
        if mean < args.min_mean:
            why.append(f"mean {mean:.1f} < {args.min_mean}")
        if lit < args.min_lit:
            why.append(f"lit {lit:.2f} < {args.min_lit}")
        if std < args.min_std:
            why.append(f"std {std:.1f} < {args.min_std}")
        verdict = "FAIL" if why else "ok  "
        print(f"{verdict} {name}: mean {mean:.1f} lit {lit:.2f} std {std:.1f}" + (" (" + ", ".join(why) + ")" if why else ""))
        failed += 1 if why else 0
    print(f"{len(args.pictures) - failed} of {len(args.pictures)} pictures ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
