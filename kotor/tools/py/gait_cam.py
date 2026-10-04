"""Adds a camera that follows one creature to a gait script: gait_cam.py LOG TAG FROM TO STEP SCRIPT OUT

LOG is the gait log of an earlier run of SCRIPT (kotor/tools/gait/run.sh); the creature TAG's place at each
frame in FROM..TO gives a `FRAME cam at EYE LOOK` line every STEP frames, the eye 4 m above and 1.4 m south of
it looking at its waist, so the legs show (the ceilings of interiors are one-sided: seen from above they are
not there). The run is not changed by the camera, so the places stay right. OUT is SCRIPT plus those lines."""
import re
import sys

log, tag, lo, hi, step, script, out = sys.argv[1:8]
lo, hi, step = int(lo), int(hi), int(step)
pat = re.compile(r"^\[(\d+) [0-9.]+\] gait (\S*) anim \d+ .* at (\S+) (\S+) lead")
at = {}
for line in open(log, encoding="latin1"):
    m = pat.match(line)
    if m and (m.group(2) or "(player)") == tag:
        at[int(m.group(1))] = (float(m.group(3)), float(m.group(4)))
lines = open(script).read().rstrip("\n").split("\n")
last = None
for f in range(lo, hi + 1, step):
    p = at.get(f) or last
    if p is None:
        continue
    last = p
    lines.append("%d cam at %.2f,%.2f,4.0 %.2f,%.2f,0.8" % (f, p[0], p[1] - 1.4, p[0], p[1]))

def frame_of(line):
    word = line.split(" ", 1)[0]
    return int(word) if word.isdigit() else -1


lines.sort(key=frame_of)  # stable: the comments stay first
open(out, "w").write("\n".join(lines) + "\n")
