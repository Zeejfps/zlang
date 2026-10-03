"""Measure how the install's resource sources overlap (evidence for docs/formats/resources.md).

    python kotor/tools/py/resources_probe.py [--verbose]

Groups every copy of every resource by source class (chitin BIFs, texture packs, rims/,
patch.erf, Override, each module's X.rim / X_s.rim / lips X_loc.mod, lips/localization.mod) and
reports, for each pair of classes, how many resref+type pairs occur in both and whether the bytes
are identical. Also reports same-resref texture pairs across types (tpc/tga/txi), resref lengths
and case. Exits 1 if a resource name breaks the rules the doc states (length > 16, characters
outside the set the doc lists, same name differing only by case within one source).
"""

import os
import re
import sys
import zlib
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

VERBOSE = '--verbose' in sys.argv
G = kres.DEFAULT_DIR


def klass(e):
    c = os.path.relpath(e.container, G).replace('\\', '/').lower()
    if c.startswith('data/'):
        return 'chitin'
    if c.startswith('texturepacks/'):
        return c.split('/')[1][:-4]          # swpc_tex_tpa ...
    if c.startswith('rims/'):
        return 'rims/' + c.split('/')[1]
    if c.startswith('modules/'):
        return 'module _s.rim' if c.endswith('_s.rim') else 'module .rim'
    if c.startswith('lips/'):
        return 'lips/localization.mod' if c.endswith('localization.mod') else 'lips _loc.mod'
    if c.startswith('saves/'):
        return 'save'
    return c


def module_of(e):
    b = os.path.basename(e.container).lower()
    for suf in ('_s.rim', '_loc.mod', '.rim'):
        if b.endswith(suf):
            return b[:-len(suf)]
    return None


def main():
    g = kres.Game()
    es = [e for e in g.every_entry() if klass(e) != 'save']
    fails = []
    # name rules
    lens = Counter()
    chars = Counter()
    for e in es:
        lens[len(e.resref)] += 1
        for ch in e.resref:
            if not re.match(r'[a-z0-9_]', ch):
                chars[ch] += 1
        if len(e.resref) > 16:
            fails.append(f'resref longer than 16: {e.resref}')
    print('resref lengths:', dict(sorted(lens.items())))
    print('characters outside [a-z0-9_] (after lower-casing):', dict(chars))
    odd = sorted({(e.resref, e.ext, klass(e)) for e in es if re.search(r'[^a-z0-9_]', e.resref)})
    for r in odd:
        print('   ', r)

    # crc per entry, grouped by (resref, ext) and class
    crc = {}
    groups = defaultdict(list)
    for e in es:
        crc[e] = zlib.crc32(kres.read_entry(e))
        groups[(e.resref, e.ext)].append(e)

    # within-module: same name in a module's .rim and _s.rim / loc
    pair = Counter()
    pair_diff = Counter()
    examples = defaultdict(list)
    for key, lst in groups.items():
        classes = sorted({klass(e) for e in lst})
        if len(classes) < 2:
            continue
        for i, a in enumerate(classes):
            for b in classes[i + 1:]:
                ca = {crc[e] for e in lst if klass(e) == a}
                cb = {crc[e] for e in lst if klass(e) == b}
                pair[(a, b)] += 1
                if ca != cb:
                    pair_diff[(a, b)] += 1
                    if len(examples[(a, b)]) < 4:
                        examples[(a, b)].append(f'{key[0]}.{key[1]}')
    print('\nresref+type pairs present in two source classes (same bytes / different bytes):')
    for (a, b), n in sorted(pair.items(), key=lambda kv: -kv[1]):
        d = pair_diff[(a, b)]
        ex = ', '.join(examples[(a, b)])
        print(f'  {a:24s} & {b:24s} {n:6d}  same {n - d:6d}  differ {d:5d}  {ex}')

    # how many modules share a name in their _s.rim with different bytes
    per_mod = defaultdict(set)
    for key, lst in groups.items():
        ms = [e for e in lst if klass(e) == 'module _s.rim']
        if len({module_of(e) for e in ms}) > 1:
            per_mod[len({crc[e] for e in ms}) > 1].add(key)
    print(f'\nnames in more than one module _s.rim: {len(per_mod[False]) + len(per_mod[True])} '
          f'(identical everywhere {len(per_mod[False])}, differing between modules {len(per_mod[True])})')
    if VERBOSE:
        print('  differing e.g.', sorted(per_mod[True])[:20])

    # duplicates inside one container
    inside = Counter()
    for key, lst in groups.items():
        cs = Counter(e.container for e in lst)
        for c, n in cs.items():
            if n > 1:
                inside[os.path.basename(c)] += 1
    print('\nsame resref+type twice inside one container:', dict(inside) or 'none')

    # case-insensitive collisions are impossible after lower-casing; check raw names per source
    # (kres lower-cases, so read raw where needed): ERF/RIM names keep case in the file.
    # texture names across types
    by_name = defaultdict(set)
    for e in es:
        if e.ext in ('tpc', 'tga', 'txi', 'dds'):
            by_name[e.resref].add((e.ext, klass(e)))
    combos = Counter(tuple(sorted(v)) for v in by_name.values())
    print('\ntexture resrefs by the set of (type, source) they occur in:')
    for k, n in combos.most_common(25):
        print(f'  {n:6d}  {k}')

    # pack coverage: tpa/tpb/tpc hold the same names?
    packs = {p: {e.resref for e in es if klass(e) == p and e.ext == 'tpc'}
             for p in ('swpc_tex_tpa', 'swpc_tex_tpb', 'swpc_tex_tpc', 'swpc_tex_gui')}
    print('\npack name sets: ' + ', '.join(f'{p} {len(s)}' for p, s in packs.items()))
    print('  tpa == tpb == tpc names:', packs['swpc_tex_tpa'] == packs['swpc_tex_tpb'] == packs['swpc_tex_tpc'])
    print('  gui & tpa overlap:', len(packs['swpc_tex_gui'] & packs['swpc_tex_tpa']))

    # streamwaves/<area>/<conv>/<resref>.wav: area = resref[1:6], conv = resref[6:12]
    sw = os.path.join(G, 'streamwaves')
    good = top = 0
    for area in os.listdir(sw):
        ap = os.path.join(sw, area)
        if not os.path.isdir(ap):
            top += 1
            continue
        for conv in os.listdir(ap):
            for f in os.listdir(os.path.join(ap, conv)):
                stem = os.path.splitext(f)[0].lower()
                if len(stem) == 16 and stem[1:6] == area.lower() and stem[6:12] == conv.lower():
                    good += 1
                else:
                    fails.append(f'streamwaves path rule broken: {area}/{conv}/{f}')
    print(f'\nstreamwaves: {good} files in subfolders follow the path rule, {top} files at top level')

    print(f'\n{len(es)} resources checked, {len(fails)} rule failures')
    for f in fails[:20]:
        print('  FAIL', f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
