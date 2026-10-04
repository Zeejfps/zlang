"""Runs one Force-power test from the HUD's real input path and prints the lines that matter (dev tooling).

    python kotor/tools/py/force_run.py --powers 46 --target g_sithtroop01 --count 2 --frames 300 --shots 70,100

Builds an input script (kotor/out/frc/NAME.txt): the leader becomes a Jedi Consular of the given level
who knows the given spells.2da rows only, creatures are spawned in front of it, the first is targeted and
key 2 (the target block's middle slot) casts the one power, exactly as a player's key does. Arrows are
clicked with `ui fclick` when --pick N says which entry of the slot to choose first. Then it runs
kotor_frc.exe headless and prints the log lines about the leader and the spawned creatures.

Options: --powers ROWS (comma list, 'all')  --class N (3 guardian, 4 consular, 5 sentinel)  --level N
--wis N --cha N --fp N  --target TEMPLATE  --count N  --dist M  --extra TEMPLATE:N  --cast-at FRAME
--frames N  --shots F1,F2  --log LIST  --module M  --name NAME  --seed N  --keep (print everything)
--pre 'LINE;LINE'  extra input lines  --post 'FRAME ui ...;FRAME ...'  --armor TEMPLATE (a worn item)
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(KOTOR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--powers', default='all')
    ap.add_argument('--class', dest='cls', type=int, default=4)
    ap.add_argument('--level', type=int, default=10)
    ap.add_argument('--wis', type=int, default=18)
    ap.add_argument('--cha', type=int, default=14)
    ap.add_argument('--fp', type=int, default=0)
    ap.add_argument('--dark', action='store_true')
    ap.add_argument('--target', default='g_sithtroop01')
    ap.add_argument('--count', type=int, default=1)
    ap.add_argument('--dist', type=float, default=7.0)
    ap.add_argument('--extra', default='')
    ap.add_argument('--angles', default='', help='degrees left of the leader facing for each spawned creature')
    ap.add_argument('--cast-at', type=int, default=60)
    ap.add_argument('--frames', type=int, default=240)
    ap.add_argument('--shots', default='')
    ap.add_argument('--log', default='combat,actions')
    ap.add_argument('--module', default='tar_m02ab')
    ap.add_argument('--name', default='')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--pick', type=int, default=0)
    ap.add_argument('--key', default='2')
    ap.add_argument('--watch', default='', help='FRAME[:TAG],... ui rules lines (no tag: the leader)')
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--pre', default='')
    ap.add_argument('--post', default='')
    ap.add_argument('--hp', type=int, default=0)
    ap.add_argument('--speed', type=int, default=8)
    ap.add_argument('--exe', default=os.path.join(KOTOR, 'out', 'kotor_frc.exe'))
    a = ap.parse_args()

    name = a.name or ('pw_' + re.sub(r'[^0-9a-z]+', '_', a.powers.lower()))
    out = os.path.join(KOTOR, 'out', 'frc')
    os.makedirs(out, exist_ok=True)
    lines = []

    def at(frame, text):
        lines.append((frame, text))

    at(3, 'ui stat wis %d' % a.wis)
    at(3, 'ui stat cha %d' % a.cha)
    at(4, 'ui jedi %d %d %s' % (a.cls, a.level, 'dark' if a.dark else 'light'))
    if a.hp > 0:
        at(4, 'ui stat hpmax %d' % a.hp)
        at(4, 'ui stat hp %d' % a.hp)
    if a.powers != 'keep':
        at(5, 'ui powers %s' % a.powers)
    if a.fp > 0:
        at(5, 'ui fp %d' % a.fp)
    at(6, 'ui rules')
    angles = [float(x) for x in a.angles.split(',')] if a.angles else []
    for i in range(a.count):
        deg = angles[i] if i < len(angles) else 0
        step = 0 if angles else 1.5 * i
        at(7 + i, 'ui fspawn %s t%d %g %g' % (a.target, i + 1, a.dist + step, deg))
    n = a.count
    if a.extra:
        for part in a.extra.split(','):
            tpl, _, cnt = part.partition(':')
            for i in range(int(cnt or 1)):
                n += 1
                at(7 + n, 'ui fspawn %s t%d %g' % (tpl, n, a.dist + 1.5 * (n - 1)))
    if a.pre:
        for k, part in enumerate(a.pre.split(';')):
            f, _, rest = part.strip().partition(' ')
            at(int(f), rest)
    at(a.cast_at - 20, 'ui target t1')
    for k in range(a.pick):
        at(a.cast_at - 10 + k, 'ui fclick BTN_TARGETDOWN1')
    at(a.cast_at, 'ui key %s' % a.key)
    for part in [x for x in a.watch.split(',') if x]:
        f, _, tag = part.partition(':')
        at(int(f), ('ui rules ' + tag).strip())
    if a.post:
        for part in a.post.split(';'):
            f, _, rest = part.strip().partition(' ')
            at(int(f), rest)
    lines.sort(key=lambda x: x[0])
    path = os.path.join(out, name + '.txt')
    with open(path, 'w') as fh:
        for f, t in lines:
            fh.write('%d %s\n' % (f, t))
    shots = []
    for s in [x for x in a.shots.split(',') if x]:
        shots += ['--screenshot-at', '%s:%s' % (s, os.path.join(out, '%s_%s.png' % (name, s)))]
    saves = os.path.join(out, 'saves_' + name)
    os.makedirs(saves, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = '/g/Dev/msys64/mingw64/bin;C:/msys64/mingw64/bin;' + env.get('PATH', '')
    cmd = [a.exe, '--module', a.module, '--no-render', '--speed', str(a.speed), '--mute', '--frames', str(a.frames),
           '--input', path, '--log', a.log, '--saves', saves, '--seed', str(a.seed)] + shots
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT, timeout=600)
    text = res.stdout + res.stderr
    with open(os.path.join(out, name + '.log'), 'w') as fh:
        fh.write(text)
    ids = {'2147483647'}
    for m in re.finditer(r'spawn: \S+ as (\d+)', text):
        ids.add(m.group(1))
    keep = re.compile(r'\b(' + '|'.join(ids) + r')\b')
    spam = re.compile(r'action \d+ queued on|action \d+ on \d+: ')
    for ln in text.splitlines():
        if a.keep:
            print(ln)
            continue
        m = re.match(r'\[(\d+) ', ln)
        if m and int(m.group(1)) < 8:
            continue
        if ln.startswith(('rules', 'spawn', 'fclick', 'frame ', '  state')):
            print(ln)
        elif m and keep.search(ln):
            print(ln)
        elif not m and ln.startswith(('kotor:', 'ui:', 'run:')):
            print(ln)


if __name__ == '__main__':
    main()
