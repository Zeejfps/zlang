"""Corpus probes for KOTOR's table formats: 2DA, TLK, SSF, LTR (exploration only, not the game).

    python kotor/tools/py/tables_probe.py 2da [--list] [-v]    check every 2DA copy in the install
    python kotor/tools/py/tables_probe.py show NAME [N]        print 2DA NAME (copy N of every_entry)
    python kotor/tools/py/tables_probe.py tlk [PATH] [-v]      check dialog.tlk (or PATH)
    python kotor/tools/py/tables_probe.py ssf [-v]             check every SSF copy
    python kotor/tools/py/tables_probe.py ltr [--names N]      check every LTR copy, optionally
                                                               generate N names per file
    python kotor/tools/py/tables_probe.py all                  2da, tlk, ssf and ltr

Each check prints what it read, the quirks it counted, and every failure; the exit status is 1
when anything failed. The formats are described in kotor/docs/formats/{2da,tlk,ssf,ltr}.md; the
readers here follow those docs (and the engine's own parsing rules recorded there), not another
implementation.
"""

import os
import random
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402


def where(g, e):
    return os.path.relpath(e.container, g.dir).replace(os.sep, '/')


# --------------------------------------------------------------------------------------------
# 2DA

class TwoDAError(ValueError):
    pass


class TwoDA:
    """A parsed binary 2DA. `cells` is row-major: cells[r * ncols + c] is a byte string."""

    def __init__(self):
        self.columns = []
        self.labels = []
        self.offsets = []
        self.data_size = 0
        self.pool = b''
        self.cells = []
        self.column_seps = b''   # the byte that ended each column name (TAB, or NUL in rims/)
        self.label_seps = b''
        self.pool_at = 0

    def cell(self, row, col):
        return self.cells[row * len(self.columns) + col]

    def column_index(self, name):
        """Column by name, ignoring ASCII case, first match wins (as the engine does)."""
        low = name.lower()
        for i, c in enumerate(self.columns):
            if c.lower() == low:
                return i
        return -1


def parse_2da(data):
    """Parse a "2DA V2.b" file the way the engine walks it (see 2da.md, "Reading it")."""
    if len(data) < 9 or data[:8] != b'2DA V2.b':
        raise TwoDAError(f'bad magic {data[:8]!r}')
    if data[8:9] != b'\n':
        raise TwoDAError(f'byte 8 is {data[8:9]!r}, not a newline')
    t = TwoDA()
    p = 9
    seps = bytearray()
    while True:
        if p >= len(data):
            raise TwoDAError('column names run off the end')
        if data[p] == 0:          # an empty name ends the list: "\t\0" (or "\0\0")
            p += 1
            break
        q = p
        while q < len(data) and data[q] not in (9, 0):
            q += 1
        if q >= len(data):
            raise TwoDAError('column name runs off the end')
        t.columns.append(data[p:q].decode('latin-1'))
        seps.append(data[q])
        p = q + 1
    t.column_seps = bytes(seps)
    if not t.columns:
        raise TwoDAError('no columns')
    if p + 4 > len(data):
        raise TwoDAError('no row count')
    nrows, = struct.unpack_from('<I', data, p)
    p += 4
    seps = bytearray()
    for i in range(nrows):
        q = p
        while q < len(data) and data[q] not in (9, 0):
            q += 1
        if q >= len(data):
            raise TwoDAError(f'row label {i} runs off the end')
        t.labels.append(data[p:q].decode('latin-1'))
        seps.append(data[q])
        p = q + 1
    t.label_seps = bytes(seps)
    ncells = nrows * len(t.columns)
    if p + 2 * ncells + 2 > len(data):
        raise TwoDAError(f'offset table ({ncells} cells) runs off the end')
    t.offsets = list(struct.unpack_from(f'<{ncells}H', data, p))
    p += 2 * ncells
    t.data_size, = struct.unpack_from('<H', data, p)
    p += 2
    t.pool_at = p
    t.pool = data[p:]
    for i, o in enumerate(t.offsets):
        if o >= len(t.pool):
            raise TwoDAError(f'cell {i} offset {o} outside the {len(t.pool)}-byte pool')
        z = t.pool.find(b'\0', o)
        if z < 0:
            raise TwoDAError(f'cell {i} at {o} has no NUL before the end')
        t.cells.append(t.pool[o:z])
    return t


INT_RE = re.compile(rb'^[+-]?[0-9]+$')
OCTALISH_RE = re.compile(rb'^[+-]?0[0-9]+$')


def probe_2da(argv):
    g = kres.Game()
    entries = g.every_entry('2da')
    verbose = '-v' in argv
    failures = []
    quirks = Counter()
    examples = defaultdict(list)
    by_name = defaultdict(list)
    containers = Counter()

    def note(kind, what):
        quirks[kind] += 1
        if len(examples[kind]) < 6:
            examples[kind].append(what)

    for e in entries:
        loc = where(g, e)
        containers[loc] += 1
        data = kres.read_entry(e)
        tag = f'{e.resref}.2da in {loc}'
        try:
            t = parse_2da(data)
        except TwoDAError as err:
            failures.append(f'{tag}: {err}')
            continue
        by_name[e.resref].append((loc, data, t))
        nc, nr = len(t.columns), len(t.labels)
        if set(t.column_seps) == {0}:
            note('column names separated by NUL, not TAB', tag)
        elif 0 in t.column_seps:
            note('column names separated by a mix of TAB and NUL', tag)
        if 0 in t.label_seps:
            note('row labels separated by NUL', tag)
        if len(t.pool) != t.data_size:
            note('data-size field differs from the bytes after it', f'{tag}: field {t.data_size}, '
                 f'{len(t.pool)} bytes')
        if len(data) > 0xFFFF + t.pool_at:
            note('pool larger than 64K', tag)
        # Pool layout: where strings start, whether every byte is used, whether values repeat.
        starts = set(t.offsets)
        if any(o > 0 and t.pool[o - 1] != 0 for o in starts):
            note('a cell offset points into the middle of a string', tag)
        q, pool_strings = 0, []
        while q < len(t.pool):
            z = t.pool.find(b'\0', q)
            if z < 0:
                note('pool does not end with a NUL', tag)
                break
            pool_strings.append((q, t.pool[q:z]))
            q = z + 1
        if {s for s, _ in pool_strings} - starts:
            note('pool holds strings no cell uses', tag)
        if len({v for _, v in pool_strings}) != len(pool_strings):
            note('pool holds the same string twice', tag)
        firsts = []
        seen = set()
        for o in t.offsets:
            if o not in seen:
                seen.add(o)
                firsts.append(o)
        if firsts != sorted(firsts):
            note('pool order is not first-use order (row-major)', tag)
        # Names and labels.
        low = [c.lower() for c in t.columns]
        if len(set(t.columns)) != nc:
            note('duplicate column name (exact)', f'{tag}: ' + ', '.join(
                sorted(c for c, n in Counter(t.columns).items() if n > 1)))
        elif len(set(low)) != nc:
            note('column names equal ignoring case', f'{tag}: ' + ', '.join(
                sorted(c for c, n in Counter(low).items() if n > 1)))
        for c in t.columns:
            if not re.fullmatch(r'[A-Za-z0-9_]+', c):
                note('column name outside [A-Za-z0-9_]', f'{tag}: {c!r}')
        if any(c != c.lower() for c in t.columns):
            note('column names with upper case', tag)
        bad = [(i, l) for i, l in enumerate(t.labels) if l != str(i)]
        if bad:
            note('row label differs from row index', f'{tag}: ' + ', '.join(
                f'{i}={l!r}' for i, l in bad[:4]) + (f' (+{len(bad) - 4})' if len(bad) > 4 else ''))
        if len(set(t.labels)) != nr:
            note('duplicate row labels', tag)
        if nr == 0:
            note('zero rows', tag)
        # Cell contents.
        if b'****' in t.cells:
            note('literal "****" cell', tag)
        if any(any(b >= 0x80 for b in c) for c in t.cells):
            note('cell bytes >= 0x80', tag)
        if any(any(b < 0x20 for b in c) for c in t.cells):
            note('cell with a control character', tag)
        if any(b' ' in c for c in t.cells):
            note('cell containing a space', tag)
        if any(b'"' in c for c in t.cells):
            note('cell containing a double quote', tag)
        octal = sorted({(t.columns[i % nc], c.decode('latin-1'))
                        for i, c in enumerate(t.cells) if OCTALISH_RE.match(c)})
        if octal:
            note('integer with a leading zero (sscanf %i reads octal)',
                 f'{tag}: ' + ', '.join(f'{col}={v}' for col, v in octal[:5]))
        if any(c.lower().startswith(b'0x') for c in t.cells):
            note('hex cell (0x...)', tag)

    # Copies of the same table.
    diffs = []
    for name, copies in sorted(by_name.items()):
        base = copies[0]
        for loc, data, t in copies[1:]:
            if data == base[1]:
                continue
            same_cells = (t.columns == base[2].columns and t.labels == base[2].labels
                          and t.cells == base[2].cells)
            if same_cells:
                kind = 'same table, different bytes'
            else:
                kind = (f'different table: {len(base[2].labels)}x{len(base[2].columns)} in '
                        f'{base[0]} vs {len(t.labels)}x{len(t.columns)}')
            diffs.append(f'{name}.2da: {loc} vs {base[0]}: {kind}')

    print(f'2DA: {len(entries)} entries ({len(by_name)} names) in {len(containers)} containers')
    for c, n in sorted(containers.items()):
        print(f'  {n:4}  {c}')
    print(f'parsed: {sum(len(v) for v in by_name.values())}, failed: {len(failures)}')
    print('quirks (count of copies):')
    for k, n in quirks.most_common():
        print(f'  {n:4}  {k}')
        for x in examples[k][: (6 if verbose else 2)]:
            print(f'          {x}')
    print(f'copies that differ from the first copy: {len(diffs)}')
    for d in diffs:
        print(f'  {d}')
    for f in failures:
        print(f'FAIL {f}')
    if '--list' in argv:
        print()
        print('| Table | Rows x cols | Copies |')
        print('|---|---|---|')
        for name, copies in sorted(by_name.items()):
            shapes = sorted({(len(t.labels), len(t.columns)) for _, _, t in copies})
            where_ = ', '.join(sorted({short_container(loc) for loc, _, _ in copies}))
            shape = ' / '.join(f'{r}x{c}' for r, c in shapes)
            print(f'| {name} | {shape} | {where_} |')
    return 1 if failures else 0


def short_container(loc):
    base = loc.split('/')[-1].lower()
    return {'2da.bif': 'bif', 'global.rim': 'g', 'miniglobal.rim': 'mg', 'patch.erf': 'patch'}.get(
        base, base)


def show_2da(argv):
    g = kres.Game()
    name = argv[0].lower()
    which = int(argv[1]) if len(argv) > 1 else 0
    copies = [e for e in g.every_entry('2da') if e.resref == name]
    if not copies:
        print(f'{name}.2da: not found', file=sys.stderr)
        return 1
    e = copies[which]
    t = parse_2da(kres.read_entry(e))
    print(f'# {name}.2da from {where(g, e)}: {len(t.labels)} rows x {len(t.columns)} columns')
    print('\t'.join(['(label)'] + t.columns))
    for r, label in enumerate(t.labels):
        print('\t'.join([label] + [t.cell(r, c).decode('latin-1') or '****'
                                   for c in range(len(t.columns))]))
    return 0


# --------------------------------------------------------------------------------------------
# TLK

TLK_TEXT, TLK_SOUND, TLK_LENGTH = 1, 2, 4
TOKEN_RE = re.compile(rb'<[^<>\s]{1,32}>')


def probe_tlk(argv):
    g = kres.Game()
    verbose = '-v' in argv
    paths = [a for a in argv if not a.startswith('-')]
    if not paths:
        paths = [os.path.join(g.dir, n) for n in sorted(os.listdir(g.dir))
                 if n.lower().endswith('.tlk')]
        extra = g.every_entry('tlk')
        print(f'TLK files in the install root: {[os.path.basename(p) for p in paths]}; '
              f'tlk resources in containers: {len(extra)}')
    status = 0
    for path in paths:
        with open(path, 'rb') as f:
            data = f.read()
        status |= check_tlk(path, data, verbose)
    return status


def check_tlk(path, data, verbose):
    failures = []
    print(f'{os.path.basename(path)}: {len(data)} bytes')
    if data[:4] != b'TLK ' or data[4:8] != b'V3.0':
        print(f'FAIL magic {data[:8]!r}')
        return 1
    lang, count, strings_at = struct.unpack_from('<3I', data, 8)
    table_end = 20 + 40 * count
    print(f'  language {lang}, {count} strings, string data at {strings_at} '
          f'(entry table ends at {table_end})')
    if strings_at != table_end:
        failures.append(f'string data offset {strings_at} is not the end of the entry table')
    if table_end > len(data):
        failures.append('entry table runs past the end of the file')
        count = (len(data) - 20) // 40
    flags_seen = Counter()
    quirks = Counter()
    examples = defaultdict(list)
    spans = []
    high = Counter()
    tokens = Counter()
    lengths = []

    def note(kind, what):
        quirks[kind] += 1
        if len(examples[kind]) < 5:
            examples[kind].append(what)

    for i in range(count):
        o = 20 + 40 * i
        flags, = struct.unpack_from('<I', data, o)
        sound = data[o + 4:o + 20]
        vol, pitch, off, size = struct.unpack_from('<4I', data, o + 20)
        length, = struct.unpack_from('<f', data, o + 36)
        flags_seen[flags] += 1
        if flags & ~7:
            note('flag bits other than 1/2/4', f'{i}: {flags:#x}')
        resref = sound.split(b'\0', 1)[0]
        if sound[len(resref):].strip(b'\0'):
            note('bytes after the NUL in the sound resref', i)
        if (flags & TLK_SOUND) and not resref:
            note('sound flag set, resref empty', i)
        if not (flags & TLK_SOUND) and resref:
            note('sound resref present, sound flag clear', i)
        if (flags & TLK_LENGTH) and length == 0.0:
            note('length flag set, length 0.0', i)
        if not (flags & TLK_LENGTH) and length != 0.0:
            note('length present, length flag clear', i)
        if length != 0.0 and not (flags & TLK_SOUND):
            note('sound length without a sound', i)
        if length < 0 or length != length:
            note('negative or NaN sound length', i)
        if vol or pitch:
            note('non-zero volume/pitch variance', f'{i}: {vol}, {pitch}')
        if not (flags & TLK_TEXT):
            if size or off:
                note('text flag clear but offset/size set', f'{i}: {off}, {size}')
            continue
        if size == 0:
            note('text flag set, size 0 (empty string)', i)
        start = strings_at + off
        if start + size > len(data):
            failures.append(f'string {i}: {off}+{size} runs past the end of the file')
            continue
        text = data[start:start + size]
        spans.append((off, size, i))
        lengths.append(size)
        if b'\0' in text:
            note('NUL inside a string', i)
        for b in text:
            if b >= 0x80:
                high[b] += 1
        try:
            text.decode('cp1252')
        except UnicodeDecodeError:
            note('bytes undefined in cp1252', i)
        if b'\r\n' in text:
            note('CR LF line break', i)
        elif b'\n' in text:
            note('LF line break', i)
        if b'\r' in text.replace(b'\r\n', b''):
            note('lone CR', i)
        if any(b < 0x20 and b not in (9, 10, 13) for b in text):
            note('control character other than TAB/CR/LF', i)
        for tok in TOKEN_RE.findall(text):
            tokens[tok.decode('cp1252')] += 1

    # Layout of the string data: order, gaps, overlaps, sharing.
    spans.sort()
    shared = Counter((o, s) for o, s, _ in spans)
    if any(n > 1 for n in shared.values()):
        note('entries sharing one offset+size', sum(n - 1 for n in shared.values() if n > 1))
    end = 0
    gaps = overlaps = 0
    for o, s, _ in spans:
        if o > end:
            gaps += 1
        elif o < end and s:
            overlaps += 1
        end = max(end, o + s)
    in_order = all(spans[k][2] < spans[k + 1][2] for k in range(len(spans) - 1))
    tail = len(data) - (strings_at + end)
    print(f'  string data: {len(spans)} strings, {gaps} gaps, {overlaps} overlaps, '
          f'{tail} bytes after the last string, stored in strref order: {in_order}')
    if lengths:
        print(f'  text sizes: max {max(lengths)}, total {sum(lengths)}')
    print('  flags combinations:')
    for fl, n in sorted(flags_seen.items()):
        names = [nm for bit, nm in ((1, 'TEXT'), (2, 'SOUND'), (4, 'LENGTH')) if fl & bit]
        print(f'    {fl:#06x} {"|".join(names) or "none":20} {n}')
    print('  quirks:')
    for k, n in quirks.most_common():
        print(f'    {n:6}  {k}' + (f'  e.g. {examples[k][:5]}' if verbose or n < 50 else
                                    f'  e.g. {examples[k][:3]}'))
    if high:
        print('  bytes >= 0x80 in text: ' + ', '.join(
            f'{b:#04x}={bytes([b]).decode("cp1252", "replace")!r}x{n}'
            for b, n in sorted(high.items())))
    if tokens:
        print(f'  <tokens> in text ({len(tokens)} distinct): ' + ', '.join(
            f'{t}x{n}' for t, n in tokens.most_common(25 if verbose else 12)))
    for f in failures:
        print(f'FAIL {f}')
    return 1 if failures else 0


# --------------------------------------------------------------------------------------------
# SSF

SSF_SLOTS = [
    'battlecry 1', 'battlecry 2', 'battlecry 3', 'battlecry 4', 'battlecry 5', 'battlecry 6',
    'select 1', 'select 2', 'select 3', 'attack grunt 1', 'attack grunt 2', 'attack grunt 3',
    'pain grunt 1', 'pain grunt 2', 'low health', 'dead', 'critical hit', 'target immune',
    'lay mine', 'disarm mine', 'begin stealth', 'begin search', 'begin unlock', 'unlock failed',
    'unlock success', 'separated from party', 'rejoined party', 'poisoned',
]
# Suffixes of the voice-over resrefs dialog.tlk gives the strrefs in each slot (see ssf.md).
SSF_SUFFIX = ['bat'] * 6 + ['slct'] * 3 + ['atk'] * 3 + ['hit'] * 2 + [
    'low', 'dead', 'crit', 'tia', 'lmin', 'dmin', 'stlh', 'srch', 'block', 'flock', 'slock',
    'sprty', 'rprty', 'pois']


def load_tlk_index(g):
    with open(os.path.join(g.dir, 'dialog.tlk'), 'rb') as f:
        data = f.read()
    _lang, count, strings_at = struct.unpack_from('<3I', data, 8)

    def entry(i):
        o = 20 + 40 * i
        flags, = struct.unpack_from('<I', data, o)
        sound = data[o + 4:o + 20].split(b'\0', 1)[0].decode('latin-1').lower()
        off, size = struct.unpack_from('<II', data, o + 28)
        text = data[strings_at + off:strings_at + off + size].decode('cp1252') if flags & 1 else ''
        return sound, text
    return count, entry


def probe_ssf(argv):
    g = kres.Game()
    verbose = '-v' in argv
    count, tlk = load_tlk_index(g)
    entries = g.every_entry('ssf')
    failures = []
    sizes = Counter()
    containers = Counter()
    by_name = defaultdict(list)
    used = Counter()
    suffix_ok = suffix_bad = 0
    mismatches = []
    for e in entries:
        loc = where(g, e)
        containers[loc] += 1
        data = kres.read_entry(e)
        tag = f'{e.resref}.ssf in {loc}'
        if data[:8] != b'SSF V1.1':
            failures.append(f'{tag}: magic {data[:8]!r}')
            continue
        if len(data) < 12:
            failures.append(f'{tag}: no table offset')
            continue
        table, = struct.unpack_from('<I', data, 8)
        if table != 12 or (len(data) - table) % 4:
            failures.append(f'{tag}: table at {table}, {len(data) - table} bytes after it')
            continue
        n = (len(data) - table) // 4
        sizes[n] += 1
        refs = struct.unpack_from(f'<{n}I', data, table)
        by_name[e.resref].append((loc, data))
        for i, r in enumerate(refs):
            if r == 0xFFFFFFFF:
                continue
            used[(n, i)] += 1
            if r >= count:
                failures.append(f'{tag}: slot {i} strref {r} >= {count} strings in dialog.tlk')
                continue
            if n == 40 and i < 28 and 'templates' in loc:
                sound, _text = tlk(r)
                m = re.search(r'_([a-z]+?)\d*$', sound)
                if m and m.group(1) == SSF_SUFFIX[i]:
                    suffix_ok += 1
                else:
                    suffix_bad += 1
                    mismatches.append(f'{e.resref} slot {i} ({SSF_SLOTS[i]}): {r} -> '
                                      f'{sound or "(no sound)"}')
    diffs = [n for n, cs in by_name.items() if len({d for _, d in cs}) > 1]
    print(f'SSF: {len(entries)} entries ({len(by_name)} names)')
    for c, n in sorted(containers.items()):
        print(f'  {n:4}  {c}')
    print('entries per file: ' + ', '.join(f'{k} entries x{n}' for k, n in sorted(sizes.items())))
    print('slots with a strref (entries, slot): count')
    for (n, i), c in sorted(used.items()):
        if n != 40:
            label = 'NWN-layout file'
        else:
            label = SSF_SLOTS[i] if i < len(SSF_SLOTS) else 'never read by the engine'
        print(f'  {n}/{i:2} {label:24} {c}')
    print(f'names whose copies differ: {diffs}')
    # Which SSFs soundset.2da (the table creatures index) names, and which it does not.
    ss = parse_2da(g.get('soundset', '2da'))
    col = ss.column_index('resref')
    listed = {ss.cell(r, col).decode('latin-1').lower() for r in range(len(ss.labels))} - {''}
    print(f'soundset.2da names {len(listed)} SSFs; missing from the install: '
          f'{sorted(listed - set(by_name))}; SSFs it does not name: {sorted(set(by_name) - listed)}')
    print(f'templates.bif slot check against dialog.tlk sound names: {suffix_ok} agree, '
          f'{suffix_bad} do not')
    for m in mismatches[: (len(mismatches) if verbose else 12)]:
        print(f'  {m}')
    for f in failures:
        print(f'FAIL {f}')
    return 1 if failures else 0


# --------------------------------------------------------------------------------------------
# LTR

LTR_ALPHABET = "abcdefghijklmnopqrstuvwxyz'-"


class LTR:
    def __init__(self, data):
        if data[:8] != b'LTR V1.0':
            raise ValueError(f'magic {data[:8]!r}')
        n = data[8]
        self.n = n
        need = 9 + 4 * 3 * n * (1 + n + n * n)
        if len(data) != need:
            raise ValueError(f'{len(data)} bytes, {need} expected for {n} letters')
        floats = struct.unpack_from(f'<{3 * n * (1 + n + n * n)}f', data, 9)
        p = 0

        def block():
            nonlocal p
            b = (floats[p:p + n], floats[p + n:p + 2 * n], floats[p + 2 * n:p + 3 * n])
            p += 3 * n
            return b
        self.singles = block()
        self.doubles = [block() for _ in range(n)]
        self.triples = [[block() for _ in range(n)] for _ in range(n)]

    def blocks(self):
        yield ('singles', self.singles)
        for a in range(self.n):
            yield (LTR_ALPHABET[a], self.doubles[a])
        for a in range(self.n):
            for b in range(self.n):
                yield (LTR_ALPHABET[a] + LTR_ALPHABET[b], self.triples[a][b])


def pick(cdf, roll):
    """First letter whose cumulative value is above the roll, or None."""
    for i, v in enumerate(cdf):
        if roll < v:
            return i
    return None


def generate_name(ltr, rng, max_len=0):
    """The engine's name generator as ltr.md describes it (rand() is 15-bit)."""
    def roll():
        return rng.randrange(32768) / 32767.0
    fails = 0
    while fails < 5:
        a = pick(ltr.singles[0], roll())
        if a is None:
            continue
        b = pick(ltr.doubles[a][0], roll())
        if b is None:
            continue
        c = pick(ltr.triples[a][b][0], roll())
        if c is None:
            continue
        name = [a, b, c]
        while True:
            x, y = name[-2], name[-1]
            p = roll()
            if rng.randrange(32768) % 12 <= len(name) or (max_len and len(name) == max_len - 1):
                k = pick(ltr.triples[x][y][2], p)
                if k is None:
                    fails += 1
                    break
                name.append(k)
                s = ''.join(LTR_ALPHABET[i] for i in name)
                return s[0].upper() + s[1:]
            k = pick(ltr.triples[x][y][1], p)
            if k is not None:
                name.append(k)
            elif len(name) <= 3:
                fails += 1
                break
            else:
                name.pop()
    return ''


def probe_ltr(argv):
    g = kres.Game()
    entries = g.every_entry('ltr')
    names = int(argv[argv.index('--names') + 1]) if '--names' in argv else 0
    failures = []
    print(f'LTR: {len(entries)} entries')
    for e in entries:
        tag = f'{e.resref}.ltr in {where(g, e)}'
        data = kres.read_entry(e)
        try:
            ltr = LTR(data)
        except ValueError as err:
            failures.append(f'{tag}: {err}')
            continue
        stats = Counter()
        for label, (start, middle, end) in ltr.blocks():
            for part, cdf in (('start', start), ('middle', middle), ('end', end)):
                vals = list(cdf)
                if any(v < 0 or v > 1.0001 or v != v for v in vals):
                    failures.append(f'{tag}: {label}.{part} has a value outside [0, 1]')
                nz = [v for v in vals if v != 0.0]
                if not nz:
                    stats[f'{part}: all zero'] += 1
                    continue
                stats[f'{part}: used'] += 1
                if nz != sorted(nz):
                    stats[f'{part}: non-zero values not increasing'] += 1
                    if label == 'singles':
                        print(f'  {e.resref} singles.{part} is not cumulative')
                elif abs(nz[-1] - 1.0) > 1e-3:
                    stats[f'{part}: last non-zero value not 1.0'] += 1
                    if label == 'singles':
                        print(f'  {e.resref} singles.{part} ends at {nz[-1]:.4f}')
        print(f'{tag}: {ltr.n} letters, {len(data)} bytes')
        for k, n in sorted(stats.items()):
            print(f'  {n:6}  {k}')
        if names:
            rng = random.Random(1)
            out = [generate_name(ltr, rng) for _ in range(names)]
            print('  sample: ' + ', '.join(out))
    for f in failures:
        print(f'FAIL {f}')
    return 1 if failures else 0


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == '2da':
        return probe_2da(rest)
    if cmd == 'show':
        return show_2da(rest)
    if cmd == 'tlk':
        return probe_tlk(rest)
    if cmd == 'ssf':
        return probe_ssf(rest)
    if cmd == 'ltr':
        return probe_ltr(rest)
    if cmd == 'all':
        status = 0
        for f in (probe_2da, probe_tlk, probe_ssf, probe_ltr):
            status |= f([])
            print()
        return status
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
