"""Checks the log of kotor/tools/playthrough/13_trask_entry.txt: when Trask's first conversation plays
(frame 700), he stands in the bunk room within 2.5 m of the player, in the same room, and faces the
player; and at frame 548 (the end of the dream cutscene) he is still outside, the other side of the door.

  sh kotor/tools/playthrough/run.sh trask kotor/tools/playthrough/13_trask_entry.txt 760
  python kotor/tools/py/check_trask_entry.py kotor/out/pt/trask.log
"""
import math, re, sys

wheres = []
pos = None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = re.match(r'where \d+ k2 end_trask at (\S+) (\S+) (\S+) hp \S+ facing (\S+) (\S+)', line)
    if m:
        wheres.append(tuple(float(v) for v in m.groups()))
    m = re.match(r'pos (\S+) (\S+) (\S+) hp \S+ talking \S+ pc \S+ leader \S+ player \S+ facing (\S+) (\S+)', line)
    if m:
        pos = tuple(float(v) for v in m.groups())

bad = 0
if len(wheres) < 3 or pos is None:
    print('FAIL: the log has no positions (run the script with the new ui where/pos)')
    sys.exit(1)
first, last = wheres[0], wheres[-1]
px, py = pos[0], pos[1]
print('Trask at the end of the cutscene: %.1f %.1f; the player %.1f %.1f' % (first[0], first[1], px, py))
if first[0] < 20.0:
    print('FAIL: Trask starts inside the bunk room (he should wait outside the door at x ~ 22.9)')
    bad += 1
d = math.hypot(last[0] - px, last[1] - py)
print('Trask when he speaks: %.1f %.1f, %.2f m from the player' % (last[0], last[1], d))
if d > 2.5:
    print('FAIL: Trask is not next to the player when he speaks')
    bad += 1
# facing: the angle between his facing and the direction to the player
to = (px - last[0], py - last[1])
n = math.hypot(*to) or 1.0
cos = (last[3] * to[0] + last[4] * to[1]) / (n * (math.hypot(last[3], last[4]) or 1.0))
print('Trask faces the player at %.0f degrees off' % math.degrees(math.acos(max(-1.0, min(1.0, cos)))))
if cos < 0.5:
    print('FAIL: Trask does not face the player')
    bad += 1
print('FAIL' if bad else 'ok: Trask opens the door, walks in and faces the player')
sys.exit(1 if bad else 0)
