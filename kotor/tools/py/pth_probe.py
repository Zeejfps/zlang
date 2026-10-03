"""Check every PTH (area path-finding graph) in the install for internal consistency.

    python kotor/tools/py/pth_probe.py            summary
    python kotor/tools/py/pth_probe.py -v         also one line per file

For each copy of each .pth resource (kres.Game().every_entry('pth')) the probe parses it with gff.py
and checks the schema (labels, types, struct ids), that each point's connection range lies inside
Path_Conections, that ranges are contiguous and in point order, that destinations are valid point
indices, and reports self-links, duplicate links, one-way links, isolated points, connected
components and which creation order (gff_probe's writer settings) the file follows.
"""

import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gff  # noqa: E402
import kres  # noqa: E402

TOP = [('Path_Points', gff.LIST), ('Path_Conections', gff.LIST)]
POINT = [('Conections', gff.DWORD), ('First_Conection', gff.DWORD), ('X', gff.FLOAT), ('Y', gff.FLOAT)]
CONNECTION = [('Destination', gff.DWORD)]


def schema(s):
    return [(f.label, f.type) for f in s.fields]


def components(n, edges):
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in edges:
        parent[find(a)] = find(b)
    return len({find(i) for i in range(n)})


def check(g):
    """(errors, facts) for one PTH tree."""
    errors, facts = [], Counter()
    if g.tag != 'PTH ':
        errors.append(f'file type {g.tag!r}')
    if g.root.id != gff.TOP_STRUCT_ID:
        errors.append(f'top struct id {g.root.id:#x}')
    if schema(g.root) != TOP:
        errors.append(f'top-level fields {schema(g.root)}')
        return errors, facts
    points = g.root.get('Path_Points')
    conns = g.root.get('Path_Conections')
    facts['points'] = len(points)
    facts['connections'] = len(conns)
    for s in points:
        if schema(s) != POINT:
            errors.append(f'point fields {schema(s)}')
            return errors, facts
        if s.id != 2:
            facts[f'point struct id {s.id}'] += 1
    for s in conns:
        if schema(s) != CONNECTION:
            errors.append(f'connection fields {schema(s)}')
            return errors, facts
        if s.id != 3:
            facts[f'connection struct id {s.id}'] += 1
    expect = 0
    edges = set()
    for i, p in enumerate(points):
        n, first = p.get('Conections'), p.get('First_Conection')
        x, y = p.get('X'), p.get('Y')
        if not (math.isfinite(x) and math.isfinite(y)):
            errors.append(f'point {i} has non-finite position')
        if first + n > len(conns):
            errors.append(f'point {i}: connections [{first}, {first + n}) past {len(conns)}')
            continue
        if first != expect:
            facts['ranges not contiguous in point order'] += 1
        expect = first + n
        if n == 0:
            facts['isolated points'] += 1
        dests = [conns[k].get('Destination') for k in range(first, first + n)]
        if len(set(dests)) != len(dests):
            facts['duplicate links'] += 1
        if dests != sorted(dests):
            facts['points whose links are not sorted'] += 1
        for d in dests:
            if d >= len(points):
                errors.append(f'point {i}: destination {d} out of range ({len(points)})')
            elif d == i:
                facts['self links'] += 1
            else:
                edges.add((i, d))
    if expect != len(conns):
        facts['connections not referenced by any point'] += len(conns) - expect
    one_way = sum(1 for a, b in edges if (b, a) not in edges)
    facts['one-way links'] += one_way
    if points:
        facts['components'] = components(len(points), edges)
        lengths = [math.dist((points[a].get('X'), points[a].get('Y')), (points[b].get('X'), points[b].get('Y')))
                   for a, b in edges]
        if lengths:
            facts['max link length x100'] = round(max(lengths) * 100)
            facts['min link length x1000'] = round(min(lengths) * 1000)
    return errors, facts


def creation_order(g, data):
    if not g.root.get('Path_Points') and not g.root.get('Path_Conections'):
        return 'empty' if gff.write(g) == data else 'other'
    plan = gff.plan_layout(g, 'dfs')
    if gff.serialize(g, plan, 'second', 'field') == data:
        return 'dfs'
    if gff.serialize(g, gff.plan_layout(g, 'keep'), 'second', 'field') == data:
        return 'interleaved' if interleaved(g) else 'keep'
    return 'other'


def interleaved(g):
    """True if each point's struct was created, then its connection structs and their Destination
    fields, then the point's own four fields."""
    points = g.root.get('Path_Points')
    conns = g.root.get('Path_Conections')
    s_next, f_next = 1, 2
    for p in points:
        if p.index != s_next:
            return False
        s_next += 1
        first, n = p.get('First_Conection'), p.get('Conections')
        for c in conns[first:first + n]:
            if c.index != s_next or c.fields[0].index != f_next:
                return False
            s_next += 1
            f_next += 1
        if [f.index for f in p.fields] != list(range(f_next, f_next + 4)):
            return False
        f_next += 4
    return True


def main(argv):
    verbose = '-v' in argv
    game = kres.Game()
    entries = game.every_entry('pth')
    total, bad = 0, 0
    sums = Counter()
    orders = Counter()
    worst = Counter()
    for e in entries:
        data = kres.read_entry(e)
        total += 1
        name = f'{e.resref}.pth in {os.path.relpath(e.container, game.dir)}'
        try:
            g = gff.read(data)
        except gff.GffError as err:
            bad += 1
            print(f'{name}: parse error: {err}')
            continue
        errors, facts = check(g)
        order = creation_order(g, data)
        orders[order] += 1
        if errors:
            bad += 1
            print(f'{name}: ' + '; '.join(errors[:5]))
        for k, v in facts.items():
            if k.startswith(('max', 'min')):
                worst[k] = max(worst[k], v) if k.startswith('max') else min(worst.get(k, v), v)
            elif k == 'components':
                sums['files with >1 component'] += v > 1
                sums['components (sum)'] += v
            else:
                sums[k] += v
                if v and k not in ('points', 'connections'):
                    sums[f'files with {k}'] += 1
        if verbose:
            print(f'{name}: {facts["points"]} points, {facts["connections"]} links, '
                  f'{facts.get("components", 0)} components, order {order}')
    print(f'PTH files checked: {total}, failing: {bad}')
    for k in sorted(sums):
        print(f'  {k}: {sums[k]}')
    for k in sorted(worst):
        print(f'  {k}: {worst[k]}')
    print('  creation order: ' + ', '.join(f'{k} {v}' for k, v in orders.most_common()))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
