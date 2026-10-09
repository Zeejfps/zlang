"""Listen-free checks of a recording of the game's sound output.

    python kotor/tools/py/sndscan.py OUT.raw [--rate 44100] [--wav OUT.wav] [--list N]

OUT.raw is what SDL's disk audio driver wrote (SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=OUT.raw with
`kotor --headless --sound-device`): 16-bit stereo at the device's rate. Reports

- dropouts: runs of digital silence (every sample 0, >= 2 ms) with sound on both sides: the queue
  ran dry (an underrun) or a sound was cut and another started;
- clicks: a step between neighbouring samples far larger than the signal's local motion
  (a sound started or ended away from zero, a stolen voice);
- clipping: samples at full scale.

Dev tooling only (AGENTS.md rule 8).
"""
import argparse
import sys

import numpy as np


def runs(mask):
    """Start/end indices of the True runs of a boolean array."""
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--rate", type=int, default=44100)
    ap.add_argument("--wav", help="also write the recording as a WAV file")
    ap.add_argument("--list", type=int, default=8, help="list this many of each finding")
    a = ap.parse_args()
    x = np.fromfile(a.raw, dtype="<i2")
    x = x[: len(x) // 2 * 2].reshape(-1, 2).astype(np.int32)
    rate = a.rate
    n = len(x)
    print(f"{a.raw}: {n / rate:.1f} s")
    if a.wav:
        import wave
        with wave.open(a.wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(x.astype("<i2").tobytes())

    # Dropouts: silence with sound on both sides (10 ms of RMS > 30 before and after).
    silent = (x[:, 0] == 0) & (x[:, 1] == 0)
    s, e = runs(silent)
    keep = (e - s) >= int(0.002 * rate)
    s, e = s[keep], e[keep]
    win = int(0.010 * rate)
    drop = []
    for a0, a1 in zip(s, e):
        if a0 < win or a1 + win > n:
            continue
        before = np.sqrt(np.mean(x[a0 - win:a0].astype(np.float64) ** 2))
        after = np.sqrt(np.mean(x[a1:a1 + win].astype(np.float64) ** 2))
        if before > 30 and after > 30:
            drop.append((a0, a1))
    total = sum(a1 - a0 for a0, a1 in drop) / rate
    late = sum(1 for a0, _ in drop if a0 > rate)
    print(f"dropouts: {len(drop)}, {total * 1000:.0f} ms of silence in all; {late} after the first second")
    for a0, a1 in drop[: a.list]:
        print(f"  at {a0 / rate:8.3f} s: {(a1 - a0) / rate * 1000:6.1f} ms")

    # Clicks: |x[n] - x[n-1]| over 3000 and over 8 times the median step of the 2 ms around it.
    d = np.abs(np.diff(x, axis=0)).max(axis=1)
    k = int(0.002 * rate)
    cand = np.flatnonzero(d > 3000)
    clicks = []
    last = -rate
    for i in cand:
        lo, hi = max(0, i - k), min(len(d), i + k)
        local = np.median(d[lo:hi])
        if d[i] > 8 * max(local, 1) and i - last > k:
            clicks.append((i, int(d[i]), float(local)))
            last = i
    print(f"clicks: {len(clicks)}")
    for i, step, local in clicks[: a.list]:
        print(f"  at {i / rate:8.3f} s: step {step} (local {local:.0f})")

    clip = int(np.count_nonzero((x >= 32767) | (x <= -32768)))
    peak = int(np.abs(x).max()) if n else 0
    print(f"clipped samples: {clip}, peak {peak}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
