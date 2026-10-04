"""Tabulates a gait log (kotor/tools/gait/run.sh, --log gait): per creature, the frames it walked or ran, with the
speed the engine used, the speed the position really changed at, the animation, the playback rate, the
leader's speed and the distance to it.

  python kotor/tools/py/gait_check.py LOG [FROM TO] [STEP] [TAG...]

Prints one row per STEP frames (default 6) for the frames FROM..TO, then a summary per creature: the frames spent
in each animation, the extremes of the rate, and how far the feet's cycles a second were from the ground's
(true speed / the cycle's distance; the log's `ground` column uses the engine's speed). A cycle rate far from 1
at a steady speed, or a feet column that differs from `true` by more than ~10 %, is a visible slide."""
import re
import sys

LINE = re.compile(
    r"^\[(\d+) [0-9.]+\] gait (\S*) anim (\d+) speed (\S+) rate (\S+) cycle (\S+) s feet (\S+) ground (\S+) cycles/s"
    r" at (\S+) (\S+) lead (\S+) m/s (\S+) m(?: smooth (\S+))?")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    path = args.pop(0)
    lo, hi, step = 0, 10 ** 9, 6
    tags = []
    nums = []
    for a in args:
        if re.fullmatch(r"\d+", a):
            nums.append(int(a))
        else:
            tags.append(a)
    if len(nums) >= 2:
        lo, hi = nums[0], nums[1]
    if len(nums) >= 3:
        step = nums[2]
    rows = {}
    for line in open(path, encoding="latin1"):
        m = LINE.match(line)
        if not m:
            continue
        f = int(m.group(1))
        tag = m.group(2) or "(player)"
        rows.setdefault(tag, []).append(
            dict(frame=f, anim=int(m.group(3)), speed=float(m.group(4)), rate=float(m.group(5)), cycle=float(m.group(6)),
                 feet=float(m.group(7)), ground=float(m.group(8)), x=float(m.group(9)), y=float(m.group(10)),
                 lead=float(m.group(11)), dist=float(m.group(12)), smooth=float(m.group(13) or 0)))
    for tag, rs in rows.items():
        if tags and tag not in tags:
            continue
        # The true speed: the distance between this line and the previous one a frame earlier, at 30 frames a second.
        for i, r in enumerate(rs):
            r["true"] = 0.0
            if i > 0 and rs[i - 1]["frame"] == r["frame"] - 1:
                r["true"] = ((r["x"] - rs[i - 1]["x"]) ** 2 + (r["y"] - rs[i - 1]["y"]) ** 2) ** 0.5 * 30.0
        print("== %s" % tag)
        print("frame  anim   speed   true   rate  feet/s  lead   dist  smooth")
        for r in rs:
            if lo <= r["frame"] <= hi and (r["frame"] - lo) % step == 0:
                print("%5d %5d %7.2f %6.2f %6.2f %7.2f %5.2f %6.2f %6.2f" % (
                    r["frame"], r["anim"], r["speed"], r["true"], r["rate"], r["feet"], r["lead"], r["dist"], r["smooth"]))
        walk = [r for r in rs if r["anim"] == 10002]
        run = [r for r in rs if r["anim"] == 10004]
        print("-- %s: %d walk frames, %d run frames" % (tag, len(walk), len(run)))
        for name, sel in (("walk", walk), ("run", run)):
            if sel:
                rates = [r["rate"] for r in sel]
                print("   %s: rate %.2f..%.2f, speed %.2f..%.2f" % (
                    name, min(rates), max(rates), min(r["speed"] for r in sel), max(r["speed"] for r in sel)))
        # Frames where the feet's pace and the ground's true pace disagree by more than 15 % at a speed over 1 m/s.
        bad = 0
        for r in rs:
            if r["true"] > 1.0 and r["cycle"] > 0:
                dist_per_cycle = r["speed"] / r["ground"] if r["ground"] > 0 else 0
                if dist_per_cycle > 0 and r["feet"] > 0:
                    ground_cycles = r["true"] / dist_per_cycle
                    if abs(r["feet"] - ground_cycles) > 0.15 * ground_cycles:
                        bad += 1
        print("   frames with the feet more than 15 %% off the ground: %d" % bad)


main()
