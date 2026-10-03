"""Check every LYT (area layout) resource in the install against docs/formats/lyt.md.

    python kotor/tools/py/lyt_probe.py [--verbose]

Parses each LYT copy (Game.every_entry('lyt')) with the grammar in the doc, checks the section
counts, that every room, track and obstacle model exists as an MDL (and MDX) resource somewhere in
the install, whether rooms have a WOK walkmesh, and that door hooks name a room of the layout.
Cross-checks door hooks against the doors of the area's GIT (position, and yaw read from the
quaternion as w x y z), and room placement: whether a room model's mesh nodes land on its WOK with
or without the LYT position added. Prints what varies (indentation, line endings, placeholders, text after
donelayout). Exit status 1 on any failure.
"""

import math
import os
import re
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

SECTIONS = ('roomcount', 'trackcount', 'obstaclecount', 'doorhookcount')


class Layout:
    def __init__(self):
        self.comments = []      # lines starting with '#'
        self.dependency = None  # filedependancy argument
        self.rooms = []         # (model, x, y, z)
        self.tracks = []        # (model, x, y, z)
        self.obstacles = []     # (model, x, y, z)
        self.doorhooks = []     # (room, door, flag, x, y, z, qw, qx, qy, qz)
        self.trailing = ''      # text after donelayout, which the reader ignores


def parse_lyt(data):
    """Layout, or raise ValueError naming the line. Follows docs/formats/lyt.md."""
    text = data.decode('ascii')
    lay = Layout()
    state = 'head'
    target = None
    remaining = 0
    for n, raw in enumerate(text.replace('\r\n', '\n').split('\n'), 1):
        words = raw.split()
        if not words:
            continue
        if state == 'done':
            lay.trailing += raw
            continue
        if words[0].startswith('#'):
            lay.comments.append(raw.strip())
            continue
        key = words[0].lower()
        if state == 'head':
            if key == 'filedependancy':
                lay.dependency = ' '.join(words[1:])
            elif key == 'beginlayout':
                state = 'body'
            else:
                raise ValueError(f'line {n}: {raw!r} before beginlayout')
            continue
        if remaining:
            if target == 'doorhookcount':
                if len(words) != 10:
                    raise ValueError(f'line {n}: door hook needs 10 fields, has {len(words)}')
                lay.doorhooks.append((words[0], words[1], int(words[2]))
                                     + tuple(float(w) for w in words[3:]))
            else:
                if len(words) != 4:
                    raise ValueError(f'line {n}: {target} entry needs 4 fields, has {len(words)}')
                entry = (words[0],) + tuple(float(w) for w in words[1:])
                {'roomcount': lay.rooms, 'trackcount': lay.tracks,
                 'obstaclecount': lay.obstacles}[target].append(entry)
            remaining -= 1
            continue
        if key in SECTIONS:
            if len(words) != 2:
                raise ValueError(f'line {n}: {raw!r}')
            target = key
            remaining = int(words[1])
            if remaining < 0:
                raise ValueError(f'line {n}: negative count')
        elif key == 'donelayout':
            state = 'done'
        else:
            raise ValueError(f'line {n}: unknown keyword {words[0]!r}')
    if remaining:
        raise ValueError(f'file ends {remaining} entries short in {target}')
    if state != 'done':
        raise ValueError('no donelayout')
    return lay


def git_doors(g):
    """area resref -> [(x, y, z, bearing)] from the GIT in each module RIM, or {} without gffpy."""
    try:
        import gffpy
    except ImportError:
        return {}
    out = {}
    for e in g.every_entry('git'):
        if e.resref in out or not e.container.lower().endswith('.rim'):
            continue
        try:
            root = gffpy.read(kres.read_entry(e))
            out[e.resref] = [(d['X'], d['Y'], d['Z'], d['Bearing'])
                             for d in root.get('Door List', [])]
        except Exception:
            continue
    return out


def mesh_node_positions(d):
    """Positions, summed down the node tree, of the mesh nodes of a binary MDL (geometry header
    after the 12-byte file header; root node offset at +40; node position at +16; children at
    +44/+48; type flag 0x20 = mesh). Just enough MDL for the placement check."""
    base = 12

    def u32(o):
        return struct.unpack_from('<I', d, base + o)[0]

    out = []
    stack = [(u32(40), (0.0, 0.0, 0.0), 0)]
    while stack:
        node, acc, depth = stack.pop()
        if depth > 64 or base + node + 52 > len(d):
            continue
        typ = struct.unpack_from('<H', d, base + node)[0]
        pos = struct.unpack_from('<3f', d, base + node + 16)
        here = tuple(a + b for a, b in zip(acc, pos))
        if typ & 0x20:
            out.append(here)
        kids, n = u32(node + 44), u32(node + 48)
        stack.extend((u32(kids + 4 * i), here, depth + 1) for i in range(n))
    return out


def room_placement(wok, mdl, x, y):
    """Which reading puts the room model's mesh nodes on its walkmesh (BWM V1.0: vertex count and
    offset at 72 and 76): the model translated by the LYT position, or the model as stored?"""
    if wok[:8] != b'BWM V1.0' or len(wok) < 80:
        return 'WOK is not BWM V1.0'
    n, off = struct.unpack_from('<II', wok, 72)
    if n == 0 or off + 12 * n > len(wok):
        return 'WOK has no vertices'
    vs = [struct.unpack_from('<2f', wok, off + 12 * i) for i in range(n)]
    x0, x1 = min(v[0] for v in vs) - 10, max(v[0] for v in vs) + 10
    y0, y1 = min(v[1] for v in vs) - 10, max(v[1] for v in vs) + 10
    nodes = mesh_node_positions(mdl)
    if not nodes:
        return 'model has no mesh nodes'
    if x == 0 and y == 0:
        return 'LYT position is the origin (cannot tell)'
    moved = sum(1 for p in nodes if x0 <= p[0] + x <= x1 and y0 <= p[1] + y <= y1)
    still = sum(1 for p in nodes if x0 <= p[0] <= x1 and y0 <= p[1] <= y1)
    if moved > still:
        return 'model + LYT position lands on the WOK (WOK in area coordinates)'
    if still > moved:
        return 'model as stored lands on the WOK'
    return 'tie'


def main(argv):
    verbose = '--verbose' in argv
    g = kres.Game()
    es = g.every_entry('lyt')
    every = g.every_entry()
    mdls = {e.resref for e in every if e.ext == 'mdl'}
    first_mdl = {}
    for e in every:
        if e.ext == 'mdl':
            first_mdl.setdefault(e.resref, e)
    mdxs = {e.resref for e in every if e.ext == 'mdx'}
    woks = {}
    for e in every:
        if e.ext == 'wok':
            woks.setdefault(e.resref, e)
    wok_vs_lyt = Counter()
    doors = git_doors(g)
    fails = []
    stats = Counter()
    indents = Counter()
    endings = Counter()
    flags = Counter()
    quat_kinds = Counter()
    vs_git = Counter()
    first_lines = Counter()
    deps = Counter()
    room_no_wok = []
    trailing = []
    blank = Counter()
    blank_files = set()
    hook_orphans = []
    for e in es:
        d = kres.read_entry(e)
        name = f'{e.resref}.lyt'
        try:
            lay = parse_lyt(d)
        except (ValueError, UnicodeDecodeError) as ex:
            fails.append(f'{name}: {ex}')
            continue
        stats['files'] += 1
        crlf = d.count(b'\r\n')
        lf = d.count(b'\n') - crlf
        endings['CRLF' if lf == 0 else 'LF' if crlf == 0 else 'mixed'] += 1
        endings['ends with newline' if d.endswith(b'\n') else 'no final newline'] += 1
        for ln in d.decode('ascii').splitlines():
            m = re.match(r'^([ \t]*)\S', ln)
            if m:
                indents[repr(m.group(1))] += 1
        first_lines[d.split(b'\r\n')[0].decode()] += 1
        dep = lay.dependency or ''
        deps['matches resref' if dep.lower() == e.resref + '.max' else dep] += 1
        stats['rooms'] += len(lay.rooms)
        stats['tracks'] += len(lay.tracks)
        stats['obstacles'] += len(lay.obstacles)
        stats['doorhooks'] += len(lay.doorhooks)
        if lay.trailing:
            trailing.append(f'{name}: {lay.trailing!r}')
        for kind, items in (('room', lay.rooms), ('track', lay.tracks),
                            ('obstacle', lay.obstacles)):
            for m, *_ in items:
                if m == '****':
                    blank[f'{kind} ****'] += 1
                    blank_files.add(e.resref)
                    continue
                if m.lower() not in mdls:
                    fails.append(f'{name}: {kind} model {m} has no MDL anywhere')
                elif m.lower() not in mdxs:
                    fails.append(f'{name}: {kind} model {m} has no MDX anywhere')
                if kind == 'room' and m.lower() not in woks:
                    room_no_wok.append(f'{e.resref}:{m}')
                elif kind == 'room' and m.lower() in first_mdl:
                    x, y = next((it[1], it[2]) for it in items if it[0] == m)
                    wok_vs_lyt[room_placement(kres.read_entry(woks[m.lower()]),
                                              kres.read_entry(first_mdl[m.lower()]), x, y)] += 1
            if kind != 'room' and items:
                stats[f'files with {kind}s'] += 1
        named = [r[0].lower() for r in lay.rooms if r[0] != '****']
        rooms = set(named)
        if len(rooms) != len(named):
            fails.append(f'{name}: a room is listed twice')
        if any(r[0] != r[0].lower() for r in lay.rooms):
            stats['files with upper-case room names'] += 1
        area_doors = doors.get(e.resref, [])
        for h in lay.doorhooks:
            room, door, flag, x, y, z, qw, qx, qy, qz = h
            flags[flag] += 1
            if room.lower() not in rooms:
                # Only seen where the room was blanked to ****; a quirk, not a parse failure.
                hook_orphans.append(f'{e.resref}:{room}/{door}')
            norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
            if abs(norm - 1) > 1e-3:
                quat_kinds['not unit length'] += 1
            elif abs(qx) < 1e-4 and abs(qy) < 1e-4:
                quat_kinds['unit, 2nd and 3rd ~0 (a pure yaw if the order is w x y z)'] += 1
            else:
                quat_kinds['other'] += 1
                if verbose:
                    print('  quat', name, h)
            if not area_doors:
                continue
            near = min(area_doors, key=lambda dd: (dd[0] - x) ** 2 + (dd[1] - y) ** 2)
            if math.hypot(near[0] - x, near[1] - y) > 0.01 or abs(near[2] - z) > 0.01:
                vs_git['no GIT door at the hook position'] += 1
                continue
            diff = (2 * math.atan2(qz, qw) - near[3] + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) < 0.01:
                vs_git['GIT door at the hook, Bearing == 2*atan2(qz, qw)'] += 1
            elif abs(abs(diff) - math.pi) < 0.01:
                vs_git['GIT door at the hook, Bearing differs by 180 degrees'] += 1
            else:
                vs_git['GIT door at the hook, other Bearing'] += 1
    print(f'LYT copies: {len(es)}, parsed: {stats["files"]}, failures: {len(fails)}')
    for f in fails[:40]:
        print('  FAIL', f)
    print('totals:', {k: v for k, v in stats.items() if k != 'files'})
    print('line endings:', dict(endings))
    print('first lines:', dict(first_lines))
    print('filedependancy:', dict(deps))
    print('indentation of non-blank lines:', dict(indents))
    print('door hook third field values:', dict(flags))
    print('door hook quaternions:', dict(quat_kinds))
    print('door hooks against the area GIT:', dict(vs_git) if doors else '(gffpy not available)')
    print(f'text after donelayout (ignored): {trailing}')
    print(f'**** placeholder models: {dict(blank)} in {sorted(blank_files)}')
    print(f'door hooks naming a room not in the room list: {len(hook_orphans)}', hook_orphans[:6])
    print('room placement (model mesh nodes against the WOK):', dict(wok_vs_lyt))
    print(f'rooms without a WOK of the same name: {len(room_no_wok)}', room_no_wok)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
