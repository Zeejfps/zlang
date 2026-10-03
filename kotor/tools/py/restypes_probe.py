"""Check that every resource type id in the install holds what docs/formats/resource-types.md says.

    python kotor/tools/py/restypes_probe.py [--verbose]

For every copy of every resource (kres.Game().every_entry(): chitin, all texture packs, modules,
lips, rims, patch.erf, saves incl. nested module saves), classify the content by its leading bytes
and check it against the format expected for the type id. Prints, per type id: count, the
containers it lives in, and the content signatures seen. Exits 1 on any mismatch.
"""

import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

GFF_TYPES = {0, 2012, 2014, 2015, 2023, 2024, 2025, 2026, 2027, 2029, 2030, 2031, 2032, 2034,
             2035, 2037, 2038, 2039, 2040, 2041, 2042, 2043, 2044, 2045, 2046, 2047, 2051, 2056,
             2058, 3003}

# type id -> predicate on the first bytes (and size), naming the expected content.
def expect(t, d):
    if t in GFF_TYPES:
        return d[4:8] == b'V3.2' and d[:4].isascii(), 'GFF V3.2'
    if t == 3:
        # TGA: no magic; image type 2 (truecolour), 3 (grey) or 10 (RLE truecolour).
        return len(d) >= 18 and d[2] in (2, 3, 10) and d[1] == 0, 'TGA header'
    if t == 4:
        return d[:4] == b'RIFF' or d[:3] == b'ID3' or d[:2] in (b'\xff\xfb', b'\xff\xf3'), 'RIFF/MP3'
    if t == 2002:
        return len(d) >= 12 and struct.unpack_from('<I', d, 0)[0] == 0, 'binary MDL (u32 0 first)'
    if t == 3008:
        return True, 'MDX vertex data (no magic)'
    if t == 2009:
        # cp1252 text: a few scripts carry a (c) sign or a curly apostrophe in comments.
        return all(c in b'\t\r\n' or c >= 32 for c in d), 'NSS text (cp1252)'
    if t == 2010:
        return d[:8] == b'NCS V1.0', 'NCS V1.0'
    if t in (2016, 2052, 2053):
        return d[:8] == b'BWM V1.0', 'BWM V1.0'
    if t == 2017:
        return d[:8] == b'2DA V2.b', '2DA V2.b'
    if t == 2018:
        return d[:8] == b'TLK V3.0', 'TLK V3.0'
    if t == 2022:
        return all(c in b'\t\r\n\0' or 32 <= c < 127 for c in d), 'TXI text'
    if t == 2036:
        return d[:8] == b'LTR V1.0', 'LTR V1.0'
    if t == 2057:
        return d[:8] in (b'MOD V1.0', b'SAV V1.0'), 'ERF-family'
    if t == 2060:
        return d[:8] == b'SSF V1.1', 'SSF V1.1'
    if t == 3000:
        return d.lstrip()[:11].lower() == b'beginlayout' or d[:1] == b'#', 'LYT text'
    if t == 3001:
        return all(c in b'\t\r\n ' or 32 <= c < 127 for c in d), 'VIS text'
    if t == 3004:
        return d[:8] == b'LIP V1.0', 'LIP V1.0'
    if t == 3007:
        return len(d) >= 128, 'TPC (128-byte header, no magic)'
    return False, 'no expectation'


def signature(d):
    head = d[:8]
    if len(head) == 8 and all(32 <= c < 127 for c in head):
        return head.decode()
    if head[:4] == b'RIFF':
        return 'RIFF'
    if head[:3] == b'ID3' or head[:2] in (b'\xff\xfb', b'\xff\xf3'):
        return 'MP3'
    return 'binary'


def container_class(e):
    c = os.path.relpath(e.container, kres.DEFAULT_DIR).replace('\\', '/').lower()
    if c.startswith('data/'):
        return 'chitin(BIF)'
    if c.startswith('saves/'):
        return 'saves'
    if c.startswith('modules/'):
        return 'modules/*_s.rim' if c.endswith('_s.rim') else 'modules/*.rim'
    if c.startswith('lips/'):
        return 'lips/*.mod'
    if c.startswith('texturepacks/'):
        return c.split('/')[1]
    return c


def main():
    g = kres.Game()
    by_type = defaultdict(lambda: {'n': 0, 'where': Counter(), 'sig': Counter(), 'bad': []})
    for e in g.every_entry():
        t = kres.EXTS.get(e.ext, None)
        if t is None:
            t = int(e.ext) if e.ext.isdigit() else -1
        if e.container.lower().endswith(('.res',)) and e.offset == 0:
            t = 0   # loose save .res files
        if e.container.lower().endswith('.tga') and e.offset == 0:
            t = 3
        d = kres.read_entry(e)
        r = by_type[t]
        r['n'] += 1
        r['where'][container_class(e)] += 1
        sig = signature(d)
        if t == 2047 or t in GFF_TYPES:
            sig = d[:8].decode('latin-1')
        r['sig'][sig if t not in (3008, 3007, 3, 2002) else 'binary'] += 1
        ok, what = expect(t, d)
        r['what'] = what
        if not ok:
            r['bad'].append(f'{e.resref}.{e.ext} in {os.path.relpath(e.container, g.dir)}: {d[:16]!r}')
    bad_total = 0
    for t in sorted(by_type):
        r = by_type[t]
        print(f'{t:5d} {kres.type_name(t):4s} {r["n"]:6d}  expect {r["what"]}')
        print('       in: ' + ', '.join(f'{k} {v}' for k, v in r['where'].most_common()))
        print('       sig: ' + ', '.join(f'{k!r} {v}' for k, v in r['sig'].most_common(12)))
        if r['bad']:
            bad_total += len(r['bad'])
            print(f'       MISMATCH {len(r["bad"])}')
            for b in r['bad'][:5]:
                print('         ' + b)
    print(f'\n{sum(r["n"] for r in by_type.values())} resources, {len(by_type)} type ids, '
          f'{bad_total} mismatches')
    bad_total += compare_engine_table()
    return 1 if bad_total else 0


def compare_engine_table():
    """Compare kres.TYPES with the id/extension table swkotor.exe builds (0x005e6d20), read from
    the decompiled export when kotor/re has it. Returns the number of disagreements."""
    import glob
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    re_dir = os.path.join(here, '..', '..', 're')
    srcs = glob.glob(os.path.join(re_dir, 'export', 'functions', '005e6d20_*.c'))
    exe = os.path.join(re_dir, 'bin', 'swkotor_unpacked.exe')
    if not srcs or not os.path.isfile(exe):
        print('engine type table: kotor/re export not present, skipped')
        return 0
    import pefile
    src = open(srcs[0], encoding='utf-8', errors='replace').read()
    pe = pefile.PE(exe)
    base, data = pe.OPTIONAL_HEADER.ImageBase, pe.__data__

    def cstr(va):
        o = pe.get_offset_from_rva(va - base)
        return data[o:data.find(b'\0', o)].decode('latin-1')
    ids, names = {}, {}
    for m in re.finditer(r'\*\(undefined2 \*\)(?:\(param_1\[1\] \+ (0x[0-9a-f]+|\d+)\)|param_1\[1\]) = '
                         r'(0x[0-9a-f]+|\d+);', src):
        ids[(int(m.group(1), 0) if m.group(1) else 0) // 2] = int(m.group(2), 0)
    for m in re.finditer(r'FUN_005e5140\(\(void \*\)(?:\(param_1\[2\] \+ (0x[0-9a-f]+|\d+)\)|param_1\[2\]),'
                         r'\s*(?:"([^"]*)"|\(char \*\)&[^)]*?([0-9a-f]{8}))\);', src, re.S):
        off = (int(m.group(1), 0) if m.group(1) else 0) // 8
        names[off] = m.group(2) if m.group(2) is not None else cstr(int(m.group(3), 16))
    engine = {ids[i]: names.get(i) for i in ids if ids[i] != 0xFFFF}
    diff = [(t, kres.TYPES.get(t), engine.get(t)) for t in sorted(set(engine) | set(kres.TYPES))
            if kres.TYPES.get(t) != engine.get(t)]
    print(f'engine type table: {len(engine)} types; differences from kres.TYPES (id, kres, engine): {diff}')
    # kres keeps four NWN ids the engine lacks; anything else is a real disagreement.
    return sum(1 for t, _k, e in diff if not (e is None and t in (2064, 2065, 2066, 2067)))


if __name__ == '__main__':
    sys.exit(main())
