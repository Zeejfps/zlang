"""Jitter in the chase camera, from a run's `camtrace` lines (input script line `FRAME cam trace`):

    python kotor/tools/py/camtrace.py LOG [JUMP_M]

Each line is the frame, the leader's x y, the eye's offset from the look-at point (x y z), the camera's yaw and its
horizontal distance. Per step the script takes the change of the offset (the leader's own walking does not count: the
camera follows it), lists the steps where it moved more than JUMP_M (default 0.25 m) and counts the reversals: a
distance that grows then shrinks then grows again within five steps, which is what a camera caught between a wall
and its easing back out looks like.
"""
import math
import sys

rows = []
for line in open(sys.argv[1], encoding='utf8', errors='replace'):
    if line.startswith('camtrace '):
        p = line.split()
        rows.append([int(p[1])] + [float(x) for x in p[2:]])
jump = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
print(len(rows), 'steps')
if len(rows) < 3:
    sys.exit(0)

big = []
dists = []
for i, r in enumerate(rows):
    dists.append(math.hypot(r[3], r[4]))
for i in range(1, len(rows)):
    a, b = rows[i - 1], rows[i]
    d = math.dist((a[3], a[4], a[5]), (b[3], b[4], b[5]))
    if d > jump:
        big.append((b[0], round(d, 3), round(dists[i - 1], 2), round(dists[i], 2)))
print(len(big), 'steps moved the eye by more than', jump, 'm (frame, change, distance before, after)')
for x in big[:25]:
    print('  ', x)

# Reversals of the distance: signs of the change over steps that moved it by more than a millimetre.
flips = 0
last = 0
trail = []
for i in range(1, len(dists)):
    dd = dists[i] - dists[i - 1]
    if abs(dd) < 0.001:
        continue
    s = 1 if dd > 0 else -1
    if last != 0 and s != last:
        trail.append(rows[i][0])
        flips += 1
    last = s
# A burst of reversals close together is a jitter; a single turnaround is not.
bursts = 0
for i in range(2, len(trail)):
    if trail[i] - trail[i - 2] <= 5:
        bursts += 1
print(flips, 'reversals of the distance,', bursts, 'of them in bursts of three within five steps')
print('distance: min %.2f max %.2f' % (min(dists), max(dists)))
