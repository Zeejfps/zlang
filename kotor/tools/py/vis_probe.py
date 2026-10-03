"""Check every VIS (room visibility) resource in the install against docs/formats/vis.md.

    python kotor/tools/py/vis_probe.py

Parses each VIS copy (Game.every_entry('vis')) with the grammar in the doc, and checks every room
it names against the rooms of the LYT with the same resref. Prints the variations it saw (case,
indentation, line endings, counts that disagree, self-listing, symmetry). Exit status 1 if a file
does not parse.
"""

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402
import lyt_probe  # noqa: E402


def parse_vis(data, quirks=None):
    """[(room, [visible rooms])] in file order, or raise ValueError. Names keep their case.

    Structure comes from indentation, as docs/formats/vis.md decides: an unindented line starts
    an entry ("room count"), an indented line adds one visible room to the current entry. The
    count is advisory: when it disagrees with the indented lines that follow, or is missing,
    a note goes to `quirks` (a list) and the indented lines win."""
    text = data.decode('ascii')
    out = []
    declared = []
    for n, raw in enumerate(text.replace('\r\n', '\n').split('\n'), 1):
        words = raw.split()
        if not words:
            continue
        if raw[0] in ' \t':
            if len(words) != 1:
                raise ValueError(f'line {n}: expected one indented room name, got {raw!r}')
            if not out:
                raise ValueError(f'line {n}: indented name before the first entry')
            out[-1][1].append(words[0])
            continue
        if len(words) == 1:
            count = None
        elif len(words) == 2:
            count = int(words[1])
            if count < 0:
                raise ValueError(f'line {n}: negative count')
        else:
            raise ValueError(f'line {n}: expected "room count", got {raw!r}')
        out.append((words[0], []))
        declared.append((n, count))
    if quirks is not None:
        for (n, count), (room, seen) in zip(declared, out):
            if count is None:
                quirks.append(f'line {n}: {room} has no count ({len(seen)} names follow)')
            elif count != len(seen):
                quirks.append(f'line {n}: {room} declares {count}, {len(seen)} names follow')
    return out


def main(argv):
    g = kres.Game()
    es = g.every_entry('vis')
    lyts = {e.resref: lyt_probe.parse_lyt(kres.read_entry(e)) for e in g.every_entry('lyt')}
    areas = {e.resref for e in g.every_entry('are')}
    fails = []
    quirks = []
    unknown = {}            # vis resref -> names that are not rooms of its LYT
    stats = Counter()
    endings = Counter()
    indents = Counter()
    case = Counter()
    no_lyt = []
    unlisted_rooms = {}
    asym_examples = []
    for e in es:
        d = kres.read_entry(e)
        name = f'{e.resref}.vis'
        notes = []
        try:
            vis = parse_vis(d, notes)
        except (ValueError, UnicodeDecodeError) as ex:
            fails.append(f'{name}: {ex}')
            continue
        quirks.extend(f'{name} {q}' for q in notes)
        stats['files'] += 1
        crlf = d.count(b'\r\n')
        lf = d.count(b'\n') - crlf
        endings['CRLF' if lf == 0 else 'LF' if crlf == 0 else 'mixed'] += 1
        endings['ends with newline' if d.endswith(b'\n') else 'no final newline'] += 1
        if lf and crlf == 0:
            quirks.append(f'{name}: LF line endings')
        for ln in d.decode('ascii').splitlines():
            m = re.match(r'^([ \t]*)\S', ln)
            if m:
                indents[repr(m.group(1))] += 1
            elif ln.strip() == '':
                stats['blank lines'] += 1
        stats['entries'] += len(vis)
        stats['visible names'] += sum(len(v) for _, v in vis)
        for room, seen in vis:
            for nm in [room] + seen:
                case['all lower' if nm == nm.lower() else 'has upper case'] += 1
            low = [s.lower() for s in seen]
            if room.lower() in low:
                stats['entries listing themselves'] += 1
            else:
                stats['entries not listing themselves'] += 1
            if len(set(low)) != len(low):
                stats['entries with a duplicate name'] += 1
            if not seen:
                stats['entries with no names'] += 1
        heads = [r.lower() for r, _ in vis]
        if len(set(heads)) != len(heads):
            stats['files with a room as head twice'] += 1
        graph = {}
        for r, seen in vis:
            graph.setdefault(r.lower(), set()).update(s.lower() for s in seen)
        pairs = [(a, b) for a, bs in graph.items() for b in bs if a != b]
        asym = [(a, b) for a, b in pairs if a not in graph.get(b, ()) and b in graph]
        stats['visibility pairs'] += len(pairs)
        stats['pairs whose reverse is missing'] += len(asym)
        if asym and len(asym_examples) < 5:
            asym_examples.append(f'{e.resref}: {asym[0][0]} sees {asym[0][1]}, not back')
        lay = lyts.get(e.resref)
        if lay is None:
            no_lyt.append(e.resref)
            continue
        rooms = {r[0].lower() for r in lay.rooms}
        bad = sorted({nm for r, seen in vis for nm in [r] + seen if nm.lower() not in rooms},
                     key=str.lower)
        if bad:
            unknown[e.resref] = bad
        missing = rooms - set(graph) - {'****'}
        if missing:
            unlisted_rooms[e.resref] = sorted(missing)
    print(f'VIS copies: {len(es)}, parsed: {stats.pop("files", 0)}, failures: {len(fails)}')
    for f in fails:
        print('  FAIL', f)
    print('stats:', dict(stats))
    print('line endings:', dict(endings))
    print('indentation of non-blank lines:', dict(indents))
    print('room name case:', dict(case))
    print(f'quirks ({len(quirks)}):')
    for q in quirks:
        print('  ', q)
    print('VIS names that are not rooms of the same-resref LYT:')
    for r, bad in sorted(unknown.items()):
        used = 'area used by a module' if r in areas else 'no module uses this area'
        print(f'   {r} ({used}): {len(bad)} names: {" ".join(bad)}')
    print('VIS with no LYT of the same resref:', no_lyt)
    print('LYT with no VIS of the same resref:', sorted(set(lyts) - {e.resref for e in es}))
    print('areas (ARE) with no VIS:', sorted(areas - {e.resref for e in es}))
    print(f'VIS files where some LYT room has no entry of its own: {len(unlisted_rooms)}')
    for r, ms in sorted(unlisted_rooms.items()):
        print(f'   {r}{"" if r in areas else " (unused area)"}: {" ".join(ms)}')
    print('asymmetry examples:', asym_examples)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
