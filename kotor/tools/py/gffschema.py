"""Field inventory of every GFF in the install (and the one save), for docs/formats/gff-*.md.

    python kotor/tools/py/gffschema.py scan [--save DIR]     parse everything, print a summary,
                                                             write extract/gff-inventory.json
    python kotor/tools/py/gffschema.py tables                refresh the generated tables in
                                                             docs/formats/gff-*.md from the json

Every resource whose first 8 bytes are "XXXXV3.2" is parsed with gffpy (all copies in all
containers: BIFs, module RIMs, lips MODs, Override). Files are counted by distinct content, so a
template that appears in both a BIF and a module RIM unchanged counts once.

Paths name a field by where it sits: "ItemList/InventoryRes" is the InventoryRes field of the
structs in the top-level ItemList list; "Struct.Field" for a field inside a struct-valued field.

The md tables sit between `<!-- gff-table KEY -->` and `<!-- /gff-table -->`; a regeneration keeps
the Meaning column of rows whose path still exists (the meanings are written by hand).
"""

import fnmatch
import glob
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gffpy  # noqa: E402
import kres  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
INVENTORY = os.path.join(ROOT, 'extract', 'gff-inventory.json')
DOCS = os.path.join(ROOT, 'docs', 'formats')
SAVE_DIR = os.path.join(kres.DEFAULT_DIR, 'Saves')

MAX_DISTINCT = 40


class Stat:
    """What one field path looks like across a corpus of files."""

    def __init__(self):
        self.types = set()
        self.files = set()
        self.count = 0
        self.values = {}          # value -> count, until it overflows
        self.overflow = False
        self.lo = None
        self.hi = None
        self.empty = 0
        self.struct_ids = {}
        self.list_lens = [None, None]
        self.sizes = set()
        self.loc = [0, 0, set()]  # with strref, with substrings, substring ids
        self.elems = 0            # list elements seen, how many have struct id == index
        self.elems_index = 0
        self.elem_ids = set()

    def note(self, f, fid):
        self.types.add(f.type)
        self.files.add(fid)
        self.count += 1
        v = f.value
        t = f.type
        key = None
        if t in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 18):
            key = v
            if self.lo is None or v < self.lo:
                self.lo = v
            if self.hi is None or v > self.hi:
                self.hi = v
        elif t in (10, 11):
            key = v
            if v == '':
                self.empty += 1
        elif t == 12:
            if v.strref != -1:
                self.loc[0] += 1
            if v.strings:
                self.loc[1] += 1
                self.loc[2].update(v.strings)
            key = None if v.strings else v.strref
            if v.strref == -1 and not v.strings:
                self.empty += 1
        elif t == 13:
            self.sizes.add(len(v))
        elif t == 14:
            self.struct_ids[v.type] = self.struct_ids.get(v.type, 0) + 1
        elif t == 15:
            n = len(v)
            for i, e in enumerate(v):
                self.elems += 1
                self.elems_index += e.type == i
                if len(self.elem_ids) < 64:
                    self.elem_ids.add(e.type)
            lo, hi = self.list_lens
            self.list_lens = [n if lo is None else min(lo, n), n if hi is None else max(hi, n)]
        elif t in (16, 17):
            key = tuple(round(x, 4) for x in v)
        if key is not None and not self.overflow:
            self.values[key] = self.values.get(key, 0) + 1
            if len(self.values) > MAX_DISTINCT:
                self.overflow = True

    def to_json(self):
        vals = sorted(self.values.items(), key=lambda kv: -kv[1])
        return {
            'types': sorted(self.types), 'files': len(self.files), 'count': self.count,
            'distinct': None if self.overflow else len(self.values),
            'values': [[_jsonable(k), n] for k, n in vals[:MAX_DISTINCT]],
            'lo': _jsonable(self.lo), 'hi': _jsonable(self.hi), 'empty': self.empty,
            'struct_ids': {str(k): n for k, n in sorted(self.struct_ids.items())},
            'list_lens': self.list_lens, 'sizes': sorted(self.sizes)[:20],
            'loc': [self.loc[0], self.loc[1], sorted(self.loc[2])],
            'elems': self.elems, 'elems_index': self.elems_index,
            'elem_ids': sorted(self.elem_ids),
        }


def _jsonable(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, tuple):
        return list(v)
    return v


class Corpus:
    def __init__(self):
        self.stats = defaultdict(lambda: defaultdict(Stat))   # kind -> path -> Stat
        self.files = defaultdict(set)                          # kind -> file ids
        self.entries = defaultdict(int)
        self.struct_ids = defaultdict(lambda: defaultdict(set))  # kind -> list path -> ids
        self.index_ids = defaultdict(lambda: defaultdict(int))    # list path: id == index?
        self.top_ids = defaultdict(set)
        self.failures = []

    def add(self, kind, data, name):
        self.entries[kind] += 1
        fid = hashlib.sha1(data).hexdigest()
        if fid in self.files[kind]:
            return
        try:
            root = gffpy.read(data)
        except gffpy.GffError as ex:
            self.failures.append((kind, name, str(ex)))
            return
        self.files[kind].add(fid)
        self.top_ids[kind].add(root.type)
        self.walk(kind, root, '', fid)

    def walk(self, kind, s, prefix, fid):
        st = self.stats[kind]
        for f in s.fields:
            path = prefix + f.label
            st[path].note(f, fid)
            if f.type == 14:
                self.walk(kind, f.value, path + '.', fid)
            elif f.type == 15:
                for i, e in enumerate(f.value):
                    if e.type == i:
                        self.index_ids[kind][path] += 1
                    self.struct_ids[kind][path].add(e.type)
                    self.walk(kind, e, path + '/', fid)

    def to_json(self):
        out = {}
        for kind in sorted(self.stats):
            out[kind] = {
                'files': len(self.files[kind]), 'entries': self.entries[kind],
                'top_ids': sorted(self.top_ids[kind]),
                'list_ids': {p: {'ids': sorted(ids)[:20], 'nids': len(ids),
                                 'index_like': self.index_ids[kind][p]}
                             for p, ids in self.struct_ids[kind].items()},
                'fields': {p: s.to_json() for p, s in self.stats[kind].items()},
            }
        return {'kinds': out, 'failures': self.failures}


def all_entries(g):
    """kres's entries plus patch.erf, which kres.Game does not load but the game does (it holds
    7 GUI files that replace gui.bif's)."""
    out = list(g.entries())
    patch = os.path.join(g.dir, 'patch.erf')
    if os.path.isfile(patch) and patch not in g.containers():
        out.extend(kres.read_container(patch))
    return out


def scan(save_root):
    g = kres.Game()
    c = Corpus()
    for e in all_entries(g):
        if e.size < 56:
            continue
        with open(e.container, 'rb') as f:
            f.seek(e.offset)
            data = f.read(e.size)
        if data[4:8] != b'V3.2':
            continue
        c.add(data[:4].decode('latin-1').strip(), data,
              f'{e.resref}.{e.ext} in {os.path.relpath(e.container, g.dir)}')
    # The saves: loose GFFs, SAVEGAME.sav (an ERF) and the module states nested inside it.
    for sdir in sorted(glob.glob(os.path.join(save_root, '*'))):
        if not os.path.isdir(sdir):
            continue
        for n in sorted(os.listdir(sdir)):
            p = os.path.join(sdir, n)
            if n.lower().endswith('.res'):
                with open(p, 'rb') as f:
                    data = f.read()
                c.add('save:' + data[:4].decode('latin-1').strip(), data, p)
            elif n.lower().endswith('.sav'):
                scan_sav(c, p, 'save:')
    return c


def scan_sav(c, path, prefix):
    for e in kres.read_container(path):
        data = kres.read_entry(e)
        if data[4:8] == b'V3.2':
            c.add(prefix + data[:4].decode('latin-1').strip(), data, f'{e.resref}.{e.ext} in {path}')
        elif data[:8] == b'MOD V1.0':
            tmp = os.path.join(ROOT, 'extract', 'save-' + e.resref + '.sav')
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            with open(tmp, 'wb') as f:
                f.write(data)
            scan_sav(c, tmp, 'savemod:')


def cmd_scan(argv):
    save_root = argv[argv.index('--save') + 1] if '--save' in argv else SAVE_DIR
    c = scan(save_root)
    j = c.to_json()
    os.makedirs(os.path.dirname(INVENTORY), exist_ok=True)
    with open(INVENTORY, 'w') as f:
        json.dump(j, f, indent=1)
    for kind, k in j['kinds'].items():
        mixed = [p for p, s in k['fields'].items() if len(s['types']) > 1]
        print(f"{kind:12} files={k['files']:5} entries={k['entries']:5} paths={len(k['fields']):4}"
              f" top_ids={k['top_ids']} mixed_types={mixed}")
    print(f"failures: {len(j['failures'])}")
    for x in j['failures']:
        print('  ', x)
    return 0 if not j['failures'] else 1


# ---- md tables ---------------------------------------------------------------------------

TABLE_RE = re.compile(r'<!-- gff-table (\S+?)(?: ([^\n]*?))? -->\n(.*?)<!-- /gff-table -->', re.S)


def short(v, n=24):
    s = str(v)
    s = s.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    return s if len(s) <= n else s[:n - 1] + '\u2026'


def describe(s, nfiles):
    t = s['types'][0]
    tn = gffpy.TYPE_NAMES.get(t, str(t))
    vals = s['values']
    if t in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 18):
        if s['distinct'] is not None and s['distinct'] <= 6:
            r = ', '.join(short(_num(v)) for v, _ in sorted(vals, key=lambda x: x[0]))
        else:
            r = f"{_num(s['lo'])}..{_num(s['hi'])}"
            if s['distinct'] is not None:
                r += f" ({s['distinct']} values)"
    elif t in (10, 11):
        nonempty = [v for v, _ in vals if v != '']
        if s['distinct'] is not None and s['distinct'] <= 1 and not nonempty:
            r = 'always empty'
        else:
            ex = ', '.join(f'`{short(v, 18)}`' for v in nonempty[:3])
            r = (f"{s['empty']} empty; " if s['empty'] else '') + (f'e.g. {ex}' if ex else '')
    elif t == 12:
        withref, withstr, ids = s['loc']
        parts = []
        if withref:
            parts.append(f'strref in {withref}')
        if withstr:
            parts.append(f'inline text in {withstr} (ids {",".join(map(str, ids))})')
        if s['empty']:
            parts.append(f"{s['empty']} empty")
        r = '; '.join(parts)
    elif t == 13:
        r = 'sizes ' + ', '.join(map(str, s['sizes'][:6]))
    elif t == 14:
        r = 'struct id ' + ', '.join(s['struct_ids'])
    elif t == 15:
        lo, hi = s['list_lens']
        r = f'{lo}..{hi} entries' if lo != hi else f'{lo} entries'
        ids = s['elem_ids']
        if s['elems']:
            if s['elems_index'] == s['elems'] and len(ids) > 1:
                r += '; struct id = index'
            elif len(ids) == 1:
                r += f'; struct id {ids[0]}'
            elif len(ids) <= 6:
                r += '; struct ids ' + ', '.join(map(str, ids))
            else:
                r += f"; struct ids vary ({s['elems_index']}/{s['elems']} = index)"
    elif t in (16, 17):
        if s['distinct'] is not None and s['distinct'] <= 3:
            r = '; '.join(short(tuple(_num(x) for x in v), 40) for v, _ in vals)
        else:
            r = 'varies'
    else:
        r = ''
    if len(s['types']) > 1:
        tn = '/'.join(gffpy.TYPE_NAMES[x] for x in s['types'])
    return tn, r


def _num(v):
    if isinstance(v, float):
        return f'{v:g}'
    return v


def render_table(kinds, kind, filt, old):
    kind_json = kinds[kind]
    nfiles = kind_json['files']
    rows = ['| Field | Type | Files | Values | Meaning |', '|---|---|---|---|---|']
    for path in sorted(kind_json['fields'], key=lambda p: _sort_key(kind_json, p)):
        if filt and not _passes(kinds, path, filt):
            continue
        s = kind_json['fields'][path]
        tn, r = describe(s, nfiles)
        files = s['files']
        fc = 'all' if files == nfiles else str(files)
        meaning = old.get(path, '')
        rows.append(f'| `{path}` | {tn} | {fc} | {r} | {meaning} |')
    return '\n'.join(rows) + '\n'


def _under(path, prefix):
    return path == prefix or path.startswith(prefix + '/') or path.startswith(prefix + '.')


def _passes(kinds, path, filt):
    """filt is ';'-separated tokens: '+A,B' keeps only paths under A or B; '-A,B' drops paths
    under A or B; '~KIND@PREFIX' drops paths under PREFIX whose rest is a path of KIND (so a
    save's creature table shows only what the UTC template doesn't have); '~KIND' is the same
    with an empty prefix; '~KIND>SUB@PREFIX' compares the rest as SUB/rest (an equipped item
    against the inventory's ItemList entries)."""
    for tok in filt.split(';'):
        tok = tok.strip()
        if not tok:
            continue
        if tok[0] in '+-':
            hit = any(_under(path, n) for n in tok[1:].split(','))
            if hit != (tok[0] == '+'):
                return False
        elif tok[0] == '~':
            other, _, prefix = tok[1:].partition('@')
            other, _, sub = other.partition('>')
            if prefix:
                if not (path.startswith(prefix + '/') or path.startswith(prefix + '.')):
                    continue
                rest = path[len(prefix) + 1:]
            else:
                rest = path
            if sub:
                rest = sub + '/' + rest
            if other in kinds and rest in kinds[other]['fields']:
                return False
    return True


_order_cache = {}


def _sort_key(kind_json, path):
    # Keep a parent's children right after it, in first-seen order of the inventory.
    key = id(kind_json)
    if key not in _order_cache:
        _order_cache[key] = {p: i for i, p in enumerate(kind_json['fields'])}
    order = _order_cache[key]
    parts = re.split(r'[/.]', path)
    out = []
    acc = ''
    rest = path
    for i in range(len(parts)):
        m = re.match(r'[^/.]+', rest)
        acc += m.group(0)
        out.append(order.get(acc, 1 << 30))
        rest = rest[m.end():]
        if rest:
            acc += rest[0]
            rest = rest[1:]
    return out


def parse_old(body):
    """Meanings already written for a table: from its rows, or from lines of the form
    "`path`: meaning" (how a new table is first written). A path containing '*' is a pattern
    (fnmatch) that fills every row without a meaning of its own."""
    old = {}
    for line in body.splitlines():
        m = re.match(r'\| `([^`]+)` \|.*\| ([^|]*?) \|$', line)
        if not m:
            m = re.match(r'`([^`]+)`\s*:\s*(.*?)\s*$', line)
        if m and m.group(2).strip():
            old[m.group(1)] = m.group(2).strip()
    return old


class Meanings(dict):
    def get(self, path, default=''):
        if path in self:
            return self[path]
        for k, v in self.items():
            if '*' in k and fnmatch.fnmatchcase(path, k):
                return v
        return default


def cmd_tables(argv):
    with open(INVENTORY) as f:
        j = json.load(f)
    kinds = j['kinds']
    for md in sorted(glob.glob(os.path.join(DOCS, 'gff-*.md'))):
        with open(md, encoding='utf-8') as f:
            text = f.read()

        def repl(m):
            kind, filt, body = m.group(1), m.group(2), m.group(3)
            if kind not in kinds:
                return m.group(0)
            table = render_table(kinds, kind, filt, Meanings(parse_old(body)))
            blank = [r.split('`')[1] for r in table.splitlines()[2:] if r.endswith('|  |')]
            if blank:
                print(f'{os.path.basename(md)} {kind}: {len(blank)} rows without a meaning:',
                      ', '.join(blank[:12]) + (' ...' if len(blank) > 12 else ''))
            head = f'<!-- gff-table {kind}' + (f' {filt}' if filt else '') + ' -->\n'
            return head + table + '<!-- /gff-table -->'

        new = TABLE_RE.sub(repl, text)
        if new != text:
            with open(md, 'w', encoding='utf-8', newline='\n') as f:
                f.write(new)
            print('updated', os.path.relpath(md, ROOT))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == 'scan':
        return cmd_scan(argv[1:])
    if argv[0] == 'tables':
        return cmd_tables(argv[1:])
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
