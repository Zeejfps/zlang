"""Casts every Force power once through the HUD's keys and prints a condensed line per power (dev tooling).

    python kotor/tools/py/force_battery.py [ROW ...]         default: all the powers below

Uses force_run.py (one process per power); the output keeps the cast, payment, saves, effects applied,
damage and the first rules lines of each creature. The scenarios are in SCENES.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
RUN = os.path.join(HERE, 'force_run.py')

TROOP = 'g_sithtroop01'
DROID = 'g_wardroid01'

# row: (key, target template, count, extra args)
SCENES = {}
for r in (7, 9, 15, 16, 19, 23, 27, 29, 32, 38, 43, 45, 46, 48, 50):
    SCENES[r] = ('2', TROOP, 1, [])
for r in (11, 25, 26, 30, 31, 35, 44):
    SCENES[r] = ('2', TROOP, 3, [])
for r in (12, 13, 47):
    SCENES[r] = ('2', DROID, 2, [])
for r in (8, 10, 17, 18, 20, 22, 24, 28, 33, 34, 36, 37, 40, 41, 42):
    SCENES[r] = ('4', TROOP, 0, [])
for r in (4, 49):
    SCENES[r] = ('2', TROOP, 1, ['--pre', '5 ui giveitem g_w_lghtsbr01 1 equip'])


def run(row):
    key, tpl, count, extra = SCENES[row]
    watch = '40,75,110,200' if count == 0 else '40:t1,75:t1,110:t1,200:t1'
    cmd = [sys.executable, RUN, '--powers', str(row), '--key', key, '--target', tpl, '--count', str(count),
           '--frames', '260', '--name', 'bat_%d' % row, '--watch', watch, '--dist', '8'] + extra
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout + res.stderr


def main():
    rows = [int(x) for x in sys.argv[1:]] or sorted(SCENES)
    for r in rows:
        print('=== power %d' % r)
        text = run(r)
        keep = []
        for ln in text.splitlines():
            if re.search(r'queued on|action \d+ on|attacks 2147|ends its round|^spawn|^frame|^run:', ln):
                if ln.startswith('run:'):
                    keep.append(ln)
                continue
            keep.append(ln)
        print('\n'.join(keep))


if __name__ == '__main__':
    main()
