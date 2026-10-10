"""Counts how often the enhanced view's shadows change abruptly, from a `--log shadows` run.

    python kotor/tools/py/shadow_flips.py LOG [--max-mode N] [--max-pops N]

A mode flip is a frame whose shadows switch between the shadow maps and the original's stencil volumes (the whole
view's shadows change softness, direction and darkness at once). A pop is a frame where a light's map appears or
goes at a weight above 0.25 (a shadow that comes or goes in one frame instead of fading), or the overhead fallback
jumps by more than 0.25. Exits 1 when either count is above its limit (default: no limit).
"""
import re
import sys

LINE = re.compile(r"^\[(\d+) [^\]]*\] shadows: maps (\w+) volumes (\w+) sun (\w+) fallback ([-\d.e]+) lights (\d+)(.*)$")
LIGHT = re.compile(r"\(([-\d.e]+) ([-\d.e]+) ([-\d.e]+) w ([-\d.e]+)\)")


def key(x, y, z):
    return (round(float(x) * 4), round(float(y) * 4), round(float(z) * 4))


def main():
    args = sys.argv[1:]
    max_mode = max_pops = None
    if "--max-mode" in args:
        i = args.index("--max-mode")
        max_mode = int(args[i + 1])
        del args[i:i + 2]
    if "--max-pops" in args:
        i = args.index("--max-pops")
        max_pops = int(args[i + 1])
        del args[i:i + 2]
    prev = None
    frames = mode = pops = 0
    examples = []
    for line in open(args[0], encoding="utf-8", errors="replace"):
        m = LINE.match(line.strip())
        if not m:
            continue
        frames += 1
        frame = int(m.group(1))
        state = {
            "mode": "volumes" if m.group(3) == "true" else ("maps" if m.group(2) == "true" else "none"),
            "fallback": float(m.group(5)),
            "lights": {key(*l[:3]): float(l[3]) for l in LIGHT.findall(m.group(7))},
        }
        if prev is not None:
            if state["mode"] != prev["mode"] and "none" not in (state["mode"], prev["mode"]):
                mode += 1
                examples.append(f"{frame}: {prev['mode']} -> {state['mode']}")
            for k in set(prev["lights"]) | set(state["lights"]):
                a = prev["lights"].get(k, 0.0)
                b = state["lights"].get(k, 0.0)
                if abs(a - b) > 0.25:
                    pops += 1
                    examples.append(f"{frame}: light {k[0]/4:.1f},{k[1]/4:.1f},{k[2]/4:.1f} {a:.2f} -> {b:.2f}")
            if abs(state["fallback"] - prev["fallback"]) > 0.25:
                pops += 1
                examples.append(f"{frame}: fallback {prev['fallback']:.2f} -> {state['fallback']:.2f}")
        prev = state
    print(f"{frames} frames: {mode} mode flips (maps <-> volumes), {pops} shadow pops")
    for e in examples[:12]:
        print("  " + e)
    bad = (max_mode is not None and mode > max_mode) or (max_pops is not None and pops > max_pops)
    print("FAIL" if bad else "PASS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
