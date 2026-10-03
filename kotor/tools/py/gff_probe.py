"""Parse every GFF in the install with gff.py, write each back and compare bytes.

    python kotor/tools/py/gff_probe.py              summary: parse failures, layout classes
    python kotor/tools/py/gff_probe.py --files      also list every file that is not in the
                                                    engine's save layout, with its class
    python kotor/tools/py/gff_probe.py --census     per file-type tag: how many files, which
                                                    resource types, and the top-level labels

"Every GFF" is every copy of every resource (kres.Game().every_entry(): BIFs, all texture packs,
modules, lips, rims, patch.erf, Override, the save and the module saves nested in it) whose bytes
4..8 are "V3.2", whatever its extension.

For each file the probe:
  1. reads it (gff.read), counting failures;
  2. writes the tree in the engine's save layout (order=dfs, fi=second, li=field) and reads that
     back: the trees must be equal (a semantic round trip, whatever the bytes);
  3. finds the first writer setting that gives the original bytes: orders dfs, elements, keep, each
     with fi second/struct/move and li field/move. Files no setting reproduces are 'unexplained',
     with the first section that differs.
"""

import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gff  # noqa: E402
import kres  # noqa: E402

ORDERS = ('dfs', 'elements', 'keep')
FI = ('second', 'struct', 'move')
LI = ('field', 'move')


def load_gffs(game):
    """(entry, bytes) for every resource whose header says GFF V3.2, plus the extensions of
    GFF-typed resources that lack the magic."""
    by_container = defaultdict(list)
    for e in game.every_entry():
        by_container[e.container].append(e)
    out = []
    for c, entries in by_container.items():
        with open(c, 'rb') as f:
            for e in entries:
                f.seek(e.offset)
                head = f.read(8)
                if len(head) == 8 and head[4:8] == b'V3.2':
                    f.seek(e.offset)
                    out.append((e, f.read(e.size)))
    return out


def same_tree(a, b):
    if a.id != b.id or len(a.fields) != len(b.fields):
        return False
    for x, y in zip(a.fields, b.fields):
        if x.label != y.label or x.type != y.type:
            return False
        if x.type == gff.STRUCT:
            if not same_tree(x.value, y.value):
                return False
        elif x.type == gff.LIST:
            if len(x.value) != len(y.value) or not all(same_tree(p, q) for p, q in zip(x.value, y.value)):
                return False
        elif x.value != y.value:
            return False
    return True


def first_difference(a, b):
    """Name of the first header field or section where two GFF files differ."""
    import struct as st
    if len(a) < 56 or len(b) < 56:
        return 'size'
    ha = st.unpack_from('<12I', a, 8)
    hb = st.unpack_from('<12I', b, 8)
    names = ('struct', 'field', 'label', 'field data', 'field indices', 'list indices')
    for k, name in enumerate(names):
        oa, na = ha[2 * k], ha[2 * k + 1]
        ob, nb = hb[2 * k], hb[2 * k + 1]
        if na != nb:
            return f'{name} count'
        size = {0: 12, 1: 12, 2: 16}.get(k, 1) * na
        if a[oa:oa + size] != b[ob:ob + size]:
            return f'{name} bytes'
    return 'header'


def classify(g, data):
    """(order, fi, li) of the first setting that reproduces data, or None."""
    for order in ORDERS:
        plan = gff.plan_layout(g, order)
        for fi in FI:
            for li in LI:
                if gff.serialize(g, plan, fi, li) == data:
                    return order, fi, li
    return None


def append_fields(base, late):
    """Add fields to an already-serialized GFF the way an in-place editor does: field record,
    label and field data appended at the ends of their sections; the owner's field-indices block
    extended if it is last, else copied to the end (the old copy stays as dead bytes).
    late: (owner struct index, Field) in the order they were added."""
    import struct as st
    so, sc, fo, fc, lo, lc, do, dc, fio, fic, lio, lic = st.unpack_from('<12I', base, 8)
    structs = [list(st.unpack_from('<3I', base, so + 12 * i)) for i in range(sc)]
    fields = [base[fo + 12 * i:fo + 12 * i + 12] for i in range(fc)]
    labels = [base[lo + 16 * i:lo + 16 * i + 16] for i in range(lc)]
    fdata = bytearray(base[do:do + dc])
    findices = list(st.unpack_from(f'<{fic // 4}I', base, fio))
    lindices = base[lio:lio + lic]
    for si, f in late:
        lab = f.label.encode('latin-1').ljust(16, b'\0')
        if lab not in labels:
            labels.append(lab)
        if f.type <= gff.INT or f.type == gff.FLOAT:
            dd = gff._encode_inline(f)
        else:
            dd = len(fdata)
            fdata += gff._encode_complex(f)
        fields.append(st.pack('<3I', f.type, labels.index(lab), dd))
        new = len(fields) - 1
        sid, sdd, n = structs[si]
        if n == 0:
            structs[si] = [sid, new, 1]
        elif n == 1:
            structs[si] = [sid, 4 * len(findices), 2]
            findices += [sdd, new]
        elif sdd // 4 + n == len(findices):
            findices.append(new)
            structs[si][2] = n + 1
        else:
            old = findices[sdd // 4:sdd // 4 + n]
            structs[si] = [sid, 4 * len(findices), n + 1]
            findices += old + [new]
    sr = b''.join(st.pack('<3I', *s) for s in structs)
    fr = b''.join(fields)
    lr = b''.join(labels)
    fib = st.pack(f'<{len(findices)}I', *findices)
    so = 56
    fo = so + len(sr)
    lo = fo + len(fr)
    do = lo + len(lr)
    fio = do + len(fdata)
    lio = fio + len(fib)
    head = base[:8] + st.pack('<12I', so, len(structs), fo, len(fields), lo, len(labels),
                              do, len(fdata), fio, len(fib), lio, len(lindices))
    return head + sr + fr + lr + bytes(fdata) + fib + lindices


def classify_appended(data, max_late=64):
    """For files no writer setting explains: is it a built file (order=keep) with its last k
    fields added later by an in-place editor? Returns (k, fi, li) or None."""
    import struct as st
    fc = st.unpack_from('<I', data, 20)[0]
    for k in range(1, min(max_late, fc) + 1):
        g = gff.read(data)
        late, ok = [], True

        def strip(s):
            nonlocal ok
            keep = []
            for f in s.fields:
                if f.index >= fc - k:
                    if f.type in (gff.STRUCT, gff.LIST):
                        ok = False
                    late.append((f.index, s, f))
                else:
                    keep.append(f)
                    if f.type == gff.STRUCT:
                        strip(f.value)
                    elif f.type == gff.LIST:
                        for el in f.value:
                            strip(el)
            s.fields = keep
        strip(g.root)
        if not ok:
            return None
        plan = gff.plan_layout(g, 'keep')
        index_of = {id(s): i for i, s in enumerate(plan.structs)}
        late.sort(key=lambda x: x[0])
        for fi in FI:
            for li in LI:
                base = gff.serialize(g, plan, fi, li)
                if append_fields(base, [(index_of[id(s)], f) for _, s, f in late]) == data:
                    return k, fi, li
    return None


def source(e):
    return 'save' if os.sep + 'Saves' + os.sep in e.container else 'shipped'


def container_kind(e, game_dir):
    """A short name for where a resource sits: a BIF name, rim/_s.rim/mod, patch.erf, ..."""
    rel = os.path.relpath(e.container, game_dir).replace('\\', '/').lower()
    if rel.startswith('data/'):
        return rel[5:]
    if rel.startswith('saves/'):
        return 'save:' + os.path.basename(rel)
    if rel.startswith('modules/'):
        if rel.endswith('_s.rim'):
            return 'modules/*_s.rim'
        return 'modules/*' + os.path.splitext(rel)[1]
    if rel.startswith('override/'):
        return 'override'
    return rel


def count_types(s, types):
    for f in s.fields:
        types[f.type] += 1
        if f.type == gff.STRUCT:
            count_types(f.value, types)
        elif f.type == gff.LIST:
            for el in f.value:
                count_types(el, types)


def main(argv):
    game = kres.Game()
    files = load_gffs(game)
    list_files = '--files' in argv
    census = '--census' in argv

    checked = len(files)
    parse_fail = []
    semantic_fail = []
    engine_identical = 0
    classes = Counter()
    by_tag = defaultdict(Counter)
    unexplained = []
    listing = []
    tags = defaultdict(lambda: [0, Counter(), Counter()])   # files, exts, top-level labels
    types = Counter()                                       # type -> fields
    containers = Counter()

    for e, data in files:
        tag = data[:4].decode('latin-1')
        where = source(e)
        name = f'{e.resref}.{e.ext} in {os.path.relpath(e.container, game.dir)}'
        try:
            g = gff.read(data)
        except gff.GffError as err:
            parse_fail.append(f'{name}: {err}')
            continue
        t = tags[tag]
        t[0] += 1
        t[1][e.ext] += 1
        for f in g.root.fields:
            t[2][f.label] += 1
        out = gff.write(g)
        if not same_tree(g.root, gff.read(out).root):
            semantic_fail.append(name)
        count_types(g.root, types)
        containers[(tag, container_kind(e, game.dir))] += 1
        if out == data:
            engine_identical += 1
            cls = ('dfs', 'second', 'field')
        else:
            cls = classify(g, data)
        if cls is None:
            app = classify_appended(data)
            if app is None:
                unexplained.append(f'{name}: first difference in {first_difference(data, out)}')
                key = 'unexplained'
            else:
                k, fi, li = app
                key = f'keep/{fi}/{li}+{k} appended'
        else:
            key = '/'.join(cls)
        classes[(where, key)] += 1
        by_tag[(where, key)][tag] += 1
        if key != 'dfs/second/field':
            listing.append(f'{key:24} {tag!r} {name}')

    print(f'GFF files checked: {checked}')
    print(f'  parse failures: {len(parse_fail)}')
    for s in parse_fail[:20]:
        print('    ' + s)
    print(f'  semantic round-trip failures (engine layout, re-read): {len(semantic_fail)}')
    for s in semantic_fail[:20]:
        print('    ' + s)
    print(f'  byte-identical in the engine save layout (dfs/second/field): {engine_identical}')
    total_identical = sum(n for (w, k), n in classes.items() if k != 'unexplained')
    print(f'  byte-identical with some writer setting: {total_identical}')
    print(f'  reproduced by no setting: {len(unexplained)}')
    print()
    print('By writer setting (order/fi/li), with file-type tags:')
    for (where, key), n in sorted(classes.items(), key=lambda kv: (kv[0][0], -kv[1])):
        tag_list = ', '.join(f'{t.strip()} {c}' for t, c in by_tag[(where, key)].most_common())
        print(f'  {where:8} {key:24} {n:6}  {tag_list}')
    if unexplained:
        print()
        print('Unexplained:')
        for s in unexplained:
            print('  ' + s)
    if list_files:
        print()
        print('Files not in the engine save layout:')
        for s in sorted(listing):
            print('  ' + s)
    print()
    print('Field types (fields in all files):')
    for t in sorted(types):
        print(f'  {t:2} {gff.TYPE_NAMES[t]:14} {types[t]}')
    print()
    print('Where each tag lives (tag, container kind, copies):')
    for tag in sorted({t for t, _ in containers}):
        row = sorted(((k, n) for (t, k), n in containers.items() if t == tag), key=lambda x: -x[1])
        print(f'  {tag!r}: ' + ', '.join(f'{k} {n}' for k, n in row))
    if census:
        print()
        print('Census: tag, files, resource types, top-level labels (files having each)')
        for tag in sorted(tags):
            n, exts, labels = tags[tag]
            ext_s = ' '.join(f'.{x} {c}' for x, c in exts.most_common())
            print(f'{tag!r} {n} files ({ext_s})')
            print('    ' + ', '.join(f'{lab}' + ('' if c == n else f' ({c})') for lab, c in labels.most_common()))
    return 1 if parse_fail or semantic_fail else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
