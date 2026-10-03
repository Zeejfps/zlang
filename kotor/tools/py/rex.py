"""Query and maintain the reverse-engineering exports of swkotor.exe (dev tooling, not the game).

The exports live in kotor/re/export/ (git-ignored, derived from the binary). This tool reads them
and drives Ghidra headless for the parts that need the project. Addresses are hex, with or
without 0x; a NAME works wherever an ADDR does (exact, else a unique case-insensitive substring).

Reading the exports (instant):
    rex.py fn ADDR|NAME [--head N]   decompiled C with header: callers, callees, strings, globals
    rex.py find REGEX                functions whose name matches
    rex.py grep REGEX [-i] [-l] [--max N]  search all decompiled functions
    rex.py callers ADDR|NAME         who calls (or takes the address of) a function
    rex.py callees ADDR|NAME         what a function calls
    rex.py strings REGEX [-i]        strings with their address and referencing functions
    rex.py xrefs ADDR                everything that refers to an address (code, data, tables)
    rex.py class NAME                a class: its functions, vtables, strings naming it
    rex.py imports [REGEX]           imported functions and the functions that call them
    rex.py tables [REGEX] [--min N] [--all]  pointer tables in data (fn/string/record tables)
    rex.py vtables [REGEX]           vtable candidates with their slots
    rex.py globals REGEX             referenced globals and their readers/writers
    rex.py routine N|NAME            an NWScript engine routine: number, name, handler
    rex.py dword ADDR [N]            raw little-endian dwords from the unpacked image
    rex.py bytes ADDR [N]            raw bytes (hex dump) from the unpacked image
    rex.py stats                     counts of everything exported
    rex.py map [--step HEX]          per .text range: named classes and DLLs called there

The names database (kotor/docs/re/names.tsv, ours, committed):
    rex.py name ADDR NAME [--proto 'C prototype'] [--comment TEXT]   add or update a row
    rex.py names [REGEX]             list rows
    rex.py apply [--all]             apply new/changed rows to the project, re-export affected
    rex.py autoname [--write]        propose names from "Class::Method" log strings
    rex.py merge FILE... [--overwrite]  merge proposal files (same format) into names.tsv

Driving Ghidra (each run pays ~10 s of Ghidra start-up; runs are serialised by a lock):
    rex.py decompile ADDR|NAME...    re-decompile functions after manual changes
    rex.py asm ADDR|NAME...          disassembly listing of functions
    rex.py export [--tables]         re-export everything (~80 s) or everything but the C (~15 s)
    rex.py setup [--force]           from scratch: copy and unpack the exe, import, analyze,
                                     fix up, apply names, export (~7 min)
    rex.py install                   download Ghidra, a JDK and Steamless into kotor/re/tools
"""

import argparse
import bisect
import csv
import glob
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
GAME_EXE = r'F:\Steam\steamapps\common\swkotor\swkotor.exe'

GHIDRA_URL = ('https://github.com/NationalSecurityAgency/ghidra/releases/download/'
              'Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip')
JDK_URL = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse'
STEAMLESS_URL = ('https://github.com/atom0s/Steamless/releases/download/v3.1.0.5/'
                 'Steamless.v3.1.0.5.-.by.atom0s.zip')


def find_re_dir(use_env=True):
    """kotor/re of this checkout, else of the main checkout (a worktree has no ignored files).
    KOTOR_RE overrides it (e.g. to rebuild the pipeline elsewhere as a test)."""
    env = os.environ.get('KOTOR_RE') if use_env else None
    if env:
        return env
    own = os.path.join(KOTOR, 're')
    if os.path.isdir(os.path.join(own, 'export')) or os.path.isdir(os.path.join(own, 'ghidra')):
        return own
    try:
        common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                cwd=KOTOR, capture_output=True, text=True).stdout.strip()
        if common:
            main = os.path.join(os.path.dirname(common), 'kotor', 're')
            if os.path.isdir(main):
                return main
    except OSError:
        pass
    return own


RE = find_re_dir()
# Ghidra, the JDK and Steamless stay in the main kotor/re/tools even when KOTOR_RE points elsewhere.
TOOLS = os.environ.get('KOTOR_RE_TOOLS') or os.path.join(find_re_dir(use_env=False), 'tools')
EXPORT = os.path.join(RE, 'export')
FUNCS = os.path.join(EXPORT, 'functions')
PROJECT_DIR = os.path.join(RE, 'ghidra')
PROJECT = 'swkotor'
PROGRAM = 'swkotor_unpacked.exe'
BIN = os.path.join(RE, 'bin')
UNPACKED = os.path.join(BIN, PROGRAM)
NAMES = os.path.join(KOTOR, 'docs', 're', 'names.tsv')
NAMES_STATE = os.path.join(PROJECT_DIR, 'names_applied.tsv')
SCRIPTS = os.path.join(KOTOR, 'tools', 're')
ROUTINES = os.path.join(EXPORT, 'nwscript_routines.tsv')

NAMES_HEADER = ('# Names for swkotor.exe (Steam, unpacked), ours to commit. One row per address:\n'
                '# addr<TAB>name<TAB>prototype<TAB>comment. Name may be Class::Method. Prototype is\n'
                '# a C declaration (for __thiscall leave out `this`) or, for data, a type. Apply with\n'
                '# `python kotor/tools/py/rex.py apply`. See kotor/docs/re/README.md.\n'
                'addr\tname\tprototype\tcomment\n')


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def need_exports():
    if not os.path.exists(os.path.join(EXPORT, 'functions.tsv')):
        die(f'no exports in {EXPORT}: run `python kotor/tools/py/rex.py setup` first')


def read_tsv(name):
    path = os.path.join(EXPORT, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        head = next(r, None)
        return [dict(zip(head, row)) for row in r]


def parse_addr(s):
    s = s.strip().lower()
    if s.startswith('0x'):
        s = s[2:]
    if not re.fullmatch(r'[0-9a-f]{1,8}', s):
        return None
    return int(s, 16)


def hx(a):
    return f'0x{a:08x}'


class Index:
    """functions.tsv, sorted by address."""

    def __init__(self):
        need_exports()
        self.rows = read_tsv('functions.tsv')
        for r in self.rows:
            r['a'] = int(r['addr'], 16)
            r['n'] = int(r['size'])
        self.rows.sort(key=lambda r: r['a'])
        self.starts = [r['a'] for r in self.rows]
        self.by_addr = {r['a']: r for r in self.rows}

    def name(self, a):
        r = self.by_addr.get(a)
        return r['name'] if r else ''

    def containing(self, a):
        i = bisect.bisect_right(self.starts, a) - 1
        if i < 0:
            return None
        r = self.rows[i]
        return r if a < r['a'] + max(r['n'], 1) else None

    def resolve(self, spec, strict=True):
        """A function row from an address (any address inside it) or a name."""
        a = parse_addr(spec)
        if a is not None and a >= 0x400000:
            r = self.containing(a)
            if r is None:
                i = bisect.bisect_right(self.starts, a) - 1
                r = self.rows[i] if i >= 0 else None
                if r and strict:
                    print(f'note: {hx(a)} is past the end of {r["addr"]} {r["name"]}; using it',
                          file=sys.stderr)
            return r
        exact = [r for r in self.rows if r['name'] == spec]
        if exact:
            return exact[0]
        base = [r for r in self.rows if r['name'].rsplit('::', 1)[-1] == spec]
        if len(base) == 1:
            return base[0]
        low = spec.lower()
        subs = [r for r in self.rows if low in r['name'].lower()]
        if len(subs) == 1:
            return subs[0]
        if not subs:
            die(f'no function named like {spec!r}')
        die(f'{spec!r} is ambiguous: ' + ', '.join(f'{r["addr"]} {r["name"]}' for r in subs[:20])
            + (' ...' if len(subs) > 20 else ''))


def fn_file(addr):
    hits = glob.glob(os.path.join(FUNCS, f'{addr:08x}_*.c'))
    return hits[0] if hits else None


# ------------------------------------------------------------------ read-only queries

def cmd_fn(args):
    idx = Index()
    r = idx.resolve(args.what)
    if r is None:
        die('no function there')
    path = fn_file(r['a'])
    if not path:
        die(f'{r["addr"]} {r["name"]}: no decompiled file (try `rex.py decompile {r["addr"]}`)')
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    if args.head:
        lines = lines[:args.head]
    print(f'// file: {os.path.relpath(path, KOTOR) if path.startswith(KOTOR) else path}')
    print('\n'.join(lines))


def cmd_find(args):
    idx = Index()
    rx = re.compile(args.regex, re.I)
    for r in idx.rows:
        if rx.search(r['name']) or (r['class'] and rx.search(r['class'])):
            print(f'{r["addr"]}  {r["name"]:<48} size={r["size"]:<6} callers={r["n_callers"]:<4}'
                  f' {r["signature"]}')


def cmd_grep(args):
    need_exports()
    rx = re.compile(args.regex, re.I if args.i else 0)
    files = sorted(os.listdir(FUNCS))
    shown = 0
    for name in files:
        if not name.endswith('.c'):
            continue
        with open(os.path.join(FUNCS, name), encoding='utf-8', errors='replace') as f:
            text = f.read()
        if not rx.search(text):
            continue
        body = text.split('\n\n', 1)
        if args.l:
            print(name)
            shown += 1
        else:
            # Search the code, not the header lists, so hits are uses, not mentions.
            code = body[1] if len(body) > 1 and not args.headers else text
            hit = False
            for ln, line in enumerate(code.splitlines(), 1):
                if rx.search(line):
                    if not hit:
                        print(f'== {name}')
                        hit = True
                    print(f'  {ln}: {line.strip()[:200]}')
                    shown += 1
                    if shown >= args.max:
                        break
        if shown >= args.max:
            print(f'... stopped at {args.max} (use --max)')
            break


def load_calls():
    return read_tsv('calls.tsv')


def cmd_callers(args):
    idx = Index()
    r = idx.resolve(args.what)
    a = r['a']
    seen = {}
    for c in load_calls():
        if int(c['callee'], 16) == a:
            ca = int(c['caller'], 16)
            seen.setdefault((ca, c['kind']), []).append(c['site'])
    print(f'{r["addr"]} {r["name"]}: {len({k[0] for k in seen})} calling functions')
    for (ca, kind), sites in sorted(seen.items()):
        print(f'  {hx(ca)}  {idx.name(ca):<48} {kind:<4} at {",".join(sites[:6])}'
              + (' ...' if len(sites) > 6 else ''))
    # Data references (vtables, tables) to the entry.
    for t in read_tsv('vtables.tsv'):
        if r['addr'] in t['entries']:
            ents = t['entries'].split(',')
            slot = next(i for i, e in enumerate(ents) if e.split('=')[0] == r['addr'])
            print(f'  vtable {t["addr"]} {t["name"]} slot {slot} (+0x{4 * slot:x})')


def cmd_callees(args):
    idx = Index()
    r = idx.resolve(args.what)
    a = r['a']
    out = {}
    for c in load_calls():
        if int(c['caller'], 16) == a:
            out.setdefault((int(c['callee'], 16), c['kind']), []).append(c['site'])
    print(f'{r["addr"]} {r["name"]}: {len(out)} callees')
    for (ce, kind), sites in sorted(out.items()):
        print(f'  {hx(ce)}  {idx.name(ce):<48} {kind:<4} at {",".join(sites[:6])}')
    imps = [i for i in read_tsv('imports.tsv') if r['addr'] in i['callers']]
    for i in imps:
        print(f'  import {i["dll"]}!{i["function"]}')


def names_of(idx, addrs):
    out = []
    for s in addrs.split(','):
        if s and s != '...':
            out.append(f'{s} {idx.name(int(s, 16))}'.strip())
    return out


def cmd_strings(args):
    idx = Index()
    rx = re.compile(args.regex, re.I if args.i else 0)
    n = 0
    for s in read_tsv('strings.tsv'):
        if rx.search(s['text']):
            refs = names_of(idx, s['ref_functions'])
            data = s['ref_data']
            print(f'{s["addr"]}  "{s["text"][:160]}"')
            for x in refs[:12]:
                print(f'      <- {x}')
            if len(refs) > 12:
                print(f'      <- ... +{len(refs) - 12} more')
            if data:
                print(f'      <- data {data[:120]}')
            n += 1
    print(f'{n} strings')


def cmd_xrefs(args):
    idx = Index()
    a = parse_addr(args.addr)
    if a is None:
        r = idx.resolve(args.addr)
        a = r['a']
    h = hx(a)
    print(f'references to {h}:')
    for c in load_calls():
        if int(c['callee'], 16) == a:
            ca = int(c['caller'], 16)
            print(f'  {c["kind"]:<5} from {c["site"]} in {hx(ca)} {idx.name(ca)}')
    for s in read_tsv('strings.tsv'):
        if s['addr'] == h:
            print(f'  string "{s["text"][:100]}"')
            for x in names_of(idx, s['ref_functions']):
                print(f'  used by {x}')
            if s['ref_data']:
                print(f'  pointed to from data {s["ref_data"]}')
    for g in read_tsv('globals.tsv'):
        if g['addr'] == h:
            print(f'  global {g["name"]} {g["type"]} ({g["section"]}), {g["n_ref_functions"]} '
                  f'functions:')
            for x in names_of(idx, g['ref_functions']):
                print(f'    {x}')
    for t in read_tsv('tables.tsv'):
        start = int(t['addr'], 16)
        if start <= a < start + 4 * int(t['dwords']):
            print(f'  inside pointer table {t["addr"]} (+0x{a - start:x}) pattern {t["pattern"]}')
    for t in read_tsv('vtables.tsv'):
        if h in t['entries']:
            print(f'  slot in vtable {t["addr"]} {t["name"]}')
    for i in read_tsv('imports.tsv'):
        if h in i['iat'].split(','):
            print(f'  IAT slot of {i["dll"]}!{i["function"]}')


def cmd_class(args):
    idx = Index()
    name = args.name
    rows = [r for r in idx.rows if r['class'] == name or r['name'].startswith(name + '::')]
    print(f'class {name}: {len(rows)} functions')
    for r in rows:
        print(f'  {r["addr"]}  {r["name"]:<56} size={r["size"]} {r["signature"]}')
    vts = [t for t in read_tsv('vtables.tsv') if t['name'].startswith(name + '::')
           or t['name'] == name]
    for t in vts:
        print(f'  vtable {t["addr"]} {t["name"]} {t["slots"]} slots, used by '
              f'{", ".join(names_of(idx, t["ref_functions"]))}')
        for i, e in enumerate(t['entries'].split(',')):
            fa = e.split('=')[0]
            print(f'    [{i:3}] +0x{4 * i:03x} {fa} {idx.name(int(fa, 16))}')
    strs = [s for s in read_tsv('strings.tsv') if name + '::' in s['text']]
    if strs:
        print(f'  strings naming {name}:')
        for s in strs[:40]:
            print(f'    {s["addr"]} "{s["text"][:100]}" <- {", ".join(names_of(idx, s["ref_functions"]))}')


def cmd_imports(args):
    idx = Index()
    rx = re.compile(args.regex or '.', re.I)
    for i in read_tsv('imports.tsv'):
        if rx.search(i['dll'] + '!' + i['function']):
            print(f'{i["dll"]}!{i["function"]}  ({i["n_callers"]} callers)')
            if args.regex:
                for x in names_of(idx, i['callers']):
                    print(f'    {x}')


def cmd_tables(args):
    rx = re.compile(args.regex, re.I) if args.regex else None
    rows = read_tsv('tables.tsv')
    rows.sort(key=lambda t: -int(t['dwords']))
    print('addr\tdwords\tperiod\tpattern\tkind\tn_fn\tn_str\tn_data\tref_functions\tpreview')
    for t in rows:
        if int(t['dwords']) < args.min or (t.get('kind') == 'eh_unwind' and not args.all):
            continue
        line = '\t'.join(t.get(k, '') for k in ('addr', 'dwords', 'period', 'pattern', 'kind',
                                                'n_fn', 'n_str', 'n_data', 'ref_functions',
                                                'preview'))
        if rx and not rx.search(line):
            continue
        print(line[:400])


def cmd_vtables(args):
    idx = Index()
    rx = re.compile(args.regex, re.I) if args.regex else None
    for t in read_tsv('vtables.tsv'):
        line = f'{t["addr"]}  {t["name"] or "-":<32} slots={t["slots"]:<4} used by ' + \
            ', '.join(names_of(idx, t['ref_functions']))
        if rx and not (rx.search(line) or rx.search(t['entries'])):
            continue
        print(line)


def cmd_globals(args):
    idx = Index()
    rx = re.compile(args.regex, re.I)
    for g in read_tsv('globals.tsv'):
        line = f'{g["addr"]}  {g["name"]:<32} {g["type"]:<16} {g["section"]:<6} ' \
               f'{g["n_ref_functions"]} fns'
        if rx.search(line) or rx.search(g['ref_functions']):
            print(line)
            if args.v:
                for x in names_of(idx, g['ref_functions']):
                    print(f'    {x}')


class Image:
    """The unpacked exe mapped by section, for raw reads."""

    def __init__(self):
        with open(UNPACKED, 'rb') as f:
            self.d = f.read()
        pe = struct.unpack_from('<I', self.d, 0x3c)[0]
        nsec = struct.unpack_from('<H', self.d, pe + 6)[0]
        optsz = struct.unpack_from('<H', self.d, pe + 20)[0]
        self.base = struct.unpack_from('<I', self.d, pe + 24 + 28)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 24 + optsz + 40 * i
            name = self.d[o:o + 8].rstrip(b'\0').decode()
            vsize, va, rsize, raw = struct.unpack_from('<IIII', self.d, o + 8)
            self.secs.append((name, self.base + va, vsize, raw, rsize))

    def read(self, a, n):
        for name, va, vsize, raw, rsize in self.secs:
            if va <= a < va + vsize:
                off = a - va
                chunk = self.d[raw + off:raw + min(off + n, rsize)]
                return chunk + b'\0' * (n - len(chunk))   # bss reads as zero
        die(f'{hx(a)} is not in any section')


def cmd_dword(args):
    a = parse_addr(args.addr)
    img = Image()
    b = img.read(a, 4 * args.n)
    idx = Index() if os.path.exists(os.path.join(EXPORT, 'functions.tsv')) else None
    for i in range(args.n):
        v = struct.unpack_from('<I', b, 4 * i)[0]
        note = idx.name(v) if idx else ''
        print(f'{hx(a + 4 * i)}  {hx(v)}  {v:<11d} {note}')


def cmd_bytes(args):
    a = parse_addr(args.addr)
    b = Image().read(a, args.n)
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        txt = ''.join(chr(c) if 32 <= c < 127 else '.' for c in row)
        print(f'{hx(a + i)}  {row.hex(" "):<48}  {txt}')


def cmd_map(args):
    """What lives where in .text: per address range, the named classes and the DLLs called.

    MSVC lays out functions in object-file order, so a source file's functions sit together;
    named functions and imports show which subsystem a range belongs to."""
    idx = Index()
    step = int(args.step, 16)
    imports_by_fn = {}
    for i in read_tsv('imports.tsv'):
        for c in i['callers'].split(','):
            if c:
                imports_by_fn.setdefault(int(c, 16), set()).add(i['dll'].lower().replace('.dll', ''))
    chunks = {}
    for r in idx.rows:
        if r['a'] < 0x401000 or r['a'] >= 0x73d000:
            continue
        c = chunks.setdefault(r['a'] // step * step, {'n': 0, 'named': 0, 'cls': {}, 'dll': {}})
        c['n'] += 1
        name = r['name']
        if r['source'] == 'USER_DEFINED' and not name.startswith('FoldedStub_'):
            c['named'] += 1
            key = name.rsplit('::', 1)[0] if '::' in name else name
            c['cls'][key] = c['cls'].get(key, 0) + 1
        for d in imports_by_fn.get(r['a'], ()):
            c['dll'][d] = c['dll'].get(d, 0) + 1
    for start in sorted(chunks):
        c = chunks[start]
        cls = ', '.join(f'{k}({v})' for k, v in sorted(c['cls'].items(), key=lambda kv: -kv[1])[:5])
        dll = ', '.join(f'{k}({v})' for k, v in sorted(c['dll'].items(), key=lambda kv: -kv[1])[:4])
        print(f'{hx(start)}-{hx(start + step - 1)}  fns={c["n"]:<4} named={c["named"]:<4} '
              f'{cls}' + (f'  | calls {dll}' if dll else ''))


def cmd_stats(args):
    need_exports()
    for name in sorted(os.listdir(EXPORT)):
        p = os.path.join(EXPORT, name)
        if name.endswith('.tsv'):
            with open(p, encoding='utf-8') as f:
                n = sum(1 for _ in f) - 1
            print(f'{name:<24} {n:>8} rows  {os.path.getsize(p) / 1e6:7.1f} MB')
    files = os.listdir(FUNCS)
    size = sum(os.path.getsize(os.path.join(FUNCS, f)) for f in files)
    print(f'{"functions/":<24} {len(files):>8} files {size / 1e6:7.1f} MB')
    rows = read_tsv('functions.tsv')
    by = {}
    for r in rows:
        by[r['source']] = by.get(r['source'], 0) + 1
    st = {}
    for r in rows:
        st[r['decomp']] = st.get(r['decomp'], 0) + 1
    print('name sources:', by)
    print('decompile status:', st)


# ------------------------------------------------------------------ NWScript routines

def load_routines():
    rows = read_tsv('nwscript_routines.tsv')
    if not rows:
        die(f'{ROUTINES} missing: run `python kotor/tools/py/nwscript_table.py` to build it')
    return rows


def cmd_routine(args):
    rows = load_routines()
    s = args.what
    if s.isdigit():
        hits = [r for r in rows if r['number'] == s]
    else:
        rx = re.compile(s, re.I)
        hits = [r for r in rows if rx.search(r['name'])]
    idx = Index()
    for r in hits:
        h = int(r['handler'], 16) if r['handler'] else 0
        shared = f'  (shared with {r["shared_with"]})' if r['shared_with'] else ''
        print(f'{r["number"]:>4}  {r["signature"]}')
        print(f'      handler {r["handler"]} {idx.name(h)}{shared}')


# ------------------------------------------------------------------ names database

def read_names():
    rows = []
    if not os.path.exists(NAMES):
        return rows
    with open(NAMES, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#') or line.startswith('addr\t'):
                continue
            c = line.split('\t')
            c += [''] * (4 - len(c))
            rows.append(c[:4])
    return rows


def write_names(rows):
    os.makedirs(os.path.dirname(NAMES), exist_ok=True)
    rows.sort(key=lambda c: int(c[0], 16))
    with open(NAMES, 'w', encoding='utf-8', newline='\n') as f:
        f.write(NAMES_HEADER)
        for c in rows:
            f.write('\t'.join(x.replace('\t', ' ') for x in c) + '\n')


def upsert_names(new_rows, overwrite=True):
    """Merge rows (addr, name, proto, comment) into names.tsv; returns how many changed."""
    rows = read_names()
    by = {int(c[0], 16): c for c in rows}
    changed = 0
    for c in new_rows:
        a = int(c[0], 16)
        c = [hx(a)] + list(c[1:])
        old = by.get(a)
        if old is None:
            by[a] = c
            changed += 1
        elif overwrite:
            merged = [hx(a)] + [n if n else o for n, o in zip(c[1:], old[1:])]
            if merged != old:
                by[a] = merged
                changed += 1
    write_names(list(by.values()))
    return changed


def cmd_name(args):
    a = parse_addr(args.addr)
    if a is None:
        a = Index().resolve(args.addr)['a']
    n = upsert_names([(hx(a), args.name, args.proto or '', args.comment or '')])
    print(f'{NAMES}: {"updated" if n else "unchanged"} {hx(a)} {args.name}; '
          f'run `rex.py apply` to put it in the project')


def cmd_names(args):
    rx = re.compile(args.regex, re.I) if args.regex else None
    for c in read_names():
        line = '\t'.join(c)
        if not rx or rx.search(line):
            print(line)


def cmd_merge(args):
    """Merge proposal files (names.tsv format) into names.tsv, checking each address."""
    idx = Index()
    segs = [(int(s['start'], 16), int(s['end'], 16)) for s in read_tsv('segments.tsv')]
    current = {int(c[0], 16): c for c in read_names()}
    take, conflicts, bad = [], [], []
    for path in args.files:
        with open(path, encoding='utf-8') as f:
            for ln, line in enumerate(f, 1):
                line = line.rstrip('\r\n')
                if not line.strip() or line.startswith('#') or line.startswith('addr\t'):
                    continue
                c = (line.split('\t') + [''] * 4)[:4]
                a = parse_addr(c[0])
                if a is None or not any(lo <= a <= hi for lo, hi in segs):
                    bad.append(f'{path}:{ln}: bad address {c[0]!r}')
                    continue
                fn = idx.by_addr.get(a)
                inside = idx.containing(a)
                if fn is None and inside is not None:
                    bad.append(f'{path}:{ln}: {hx(a)} is inside {inside["addr"]} '
                               f'{inside["name"]}, not at a function start')
                    continue
                old = current.get(a)
                if old and old[1] and c[1] and old[1] != c[1] and not args.overwrite:
                    conflicts.append(f'{path}:{ln}: {hx(a)} is {old[1]} in names.tsv, '
                                     f'proposal says {c[1]} (kept; --overwrite to replace)')
                    c[1] = ''
                take.append([hx(a)] + [x.strip() for x in c[1:]])
    for m in bad + conflicts:
        print(m)
    n = upsert_names(take, overwrite=True)
    print(f'{len(take)} rows read, {n} added or changed, {len(bad)} rejected, '
          f'{len(conflicts)} name conflicts; run `rex.py apply` next')


AUTONAME_RX = re.compile(r'^(C[A-Za-z0-9_]+)::(~?[A-Za-z_][A-Za-z0-9_]*)\b')


def cmd_autoname(args):
    """Name functions after the Class::Method their own log/assert strings announce."""
    idx = Index()
    claims = {}
    for s in read_tsv('strings.tsv'):
        m = AUTONAME_RX.match(s['text'])
        if not m:
            continue
        qual = f'{m.group(1)}::{m.group(2)}'
        for f in s['ref_functions'].split(','):
            if f:
                claims.setdefault(int(f, 16), set()).add((qual, s['addr']))
    existing = {int(c[0], 16) for c in read_names()}
    proposals = []
    taken = {}
    for a, qs in claims.items():
        names = {q for q, _ in qs}
        r = idx.by_addr.get(a)
        if len(names) != 1 or r is None:
            continue
        qual = names.pop()
        taken.setdefault(qual, []).append(a)
    for qual, addrs in sorted(taken.items()):
        if len(addrs) != 1:
            continue   # the same Class::Method string in several functions: inlined, skip
        a = addrs[0]
        r = idx.by_addr[a]
        if not r['name'].startswith(('FUN_', 'thunk_FUN_')) or a in existing:
            continue
        sa = sorted(s for q, s in claims[a])[0]
        proposals.append((hx(a), qual, '', f'auto: named by its string at {sa}'))
    for p in proposals:
        print('\t'.join(p))
    print(f'{len(proposals)} proposals', file=sys.stderr)
    if args.write:
        n = upsert_names(proposals, overwrite=False)
        print(f'{n} rows added to {NAMES}', file=sys.stderr)


# ------------------------------------------------------------------ Ghidra

def ghidra_home():
    hits = sorted(glob.glob(os.path.join(TOOLS, 'ghidra_*_PUBLIC')))
    if not hits:
        die(f'no Ghidra under {TOOLS}: run `rex.py install`')
    return hits[-1]


def jdk_home():
    hits = sorted(glob.glob(os.path.join(TOOLS, 'jdk-21*')))
    if not hits:
        die(f'no JDK 21 under {TOOLS}: run `rex.py install`')
    return hits[-1]


class Lock:
    """One Ghidra process at a time per project (Ghidra locks the project; we wait instead)."""

    def __init__(self, timeout=3600):
        self.path = os.path.join(PROJECT_DIR, '.rex.lock')
        self.timeout = timeout

    def __enter__(self):
        os.makedirs(PROJECT_DIR, exist_ok=True)
        t0 = time.time()
        warned = False
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f'{os.getpid()} {time.time()}'.encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(self.path)
                except OSError:
                    continue
                if age > 7200:   # a crashed run: take it over
                    os.remove(self.path)
                    continue
                if not warned:
                    print('waiting for another Ghidra run to finish ...', file=sys.stderr)
                    warned = True
                if time.time() - t0 > self.timeout:
                    die(f'gave up waiting for {self.path}')
                time.sleep(2)

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass


def run_headless(extra, write=False, log_name='last_run.log'):
    """Run analyzeHeadless on the project; prints the KOTOR: lines and errors."""
    gh = ghidra_home()
    bat = os.path.join(gh, 'support', 'analyzeHeadless.bat' if os.name == 'nt' else 'analyzeHeadless')
    env = dict(os.environ)
    env['JAVA_HOME'] = jdk_home()
    env.setdefault('GHIDRA_HEADLESS_MAXMEM', '16G')
    cmd = [bat, PROJECT_DIR, PROJECT] + extra
    log = os.path.join(PROJECT_DIR, log_name)
    t0 = time.time()
    with Lock():
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, errors='replace')
    out = p.stdout + p.stderr
    with open(log, 'w', encoding='utf-8') as f:
        f.write(out)
    bad = False
    for line in out.splitlines():
        if 'KOTOR:' in line:
            print(line.split('KOTOR:', 1)[1].strip())
        elif re.search(r'\bERROR\b|Exception|\.java:\d+', line) and 'SLF4J' not in line:
            print(line)
            bad = True
    print(f'(ghidra {time.time() - t0:.0f} s, log {log})')
    if p.returncode != 0 or bad:
        print('Ghidra reported problems; see the log', file=sys.stderr)
    return p.returncode == 0


def script_run(args, write=False):
    extra = ['-process', PROGRAM, '-noanalysis', '-scriptPath', SCRIPTS,
             '-postScript', 'KotorRE.java'] + args
    if not write:
        extra.insert(3, '-readOnly')
    return run_headless(extra, write=write)


def addrs_of(specs):
    idx = Index()
    out = []
    for s in specs:
        r = idx.resolve(s)
        if r:
            out.append(r['addr'])
    return out


def cmd_decompile(args):
    script_run(['decompile', EXPORT] + addrs_of(args.what))
    for a in addrs_of(args.what):
        p = fn_file(int(a, 16))
        if p:
            print(f'  {os.path.relpath(p, os.path.dirname(KOTOR))}')


def cmd_asm(args):
    script_run(['asm', EXPORT] + addrs_of(args.what))
    for a in addrs_of(args.what):
        hits = glob.glob(os.path.join(EXPORT, 'asm', f'{int(a, 16):08x}_*.s'))
        if hits:
            with open(hits[0], encoding='utf-8') as f:
                sys.stdout.write(f.read())


def cmd_apply(args):
    if not os.path.exists(NAMES):
        write_names([])
    script_run(['apply-names', EXPORT, NAMES, NAMES_STATE] + (['all'] if args.all else []),
               write=True)


def cmd_export(args):
    script_run(['export-tables' if args.tables else 'export-all', EXPORT])


def download(url, dest):
    if os.path.exists(dest):
        return
    print(f'downloading {url}')
    tmp = dest + '.part'
    with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(tmp, dest)


def cmd_install(args):
    tools = TOOLS
    os.makedirs(tools, exist_ok=True)
    if not glob.glob(os.path.join(tools, 'ghidra_*_PUBLIC')):
        z = os.path.join(tools, 'ghidra.zip')
        download(GHIDRA_URL, z)
        zipfile.ZipFile(z).extractall(tools)
        os.remove(z)
    if not glob.glob(os.path.join(tools, 'jdk-21*')):
        z = os.path.join(tools, 'jdk21.zip')
        download(JDK_URL, z)
        zipfile.ZipFile(z).extractall(tools)
        os.remove(z)
    sl = os.path.join(tools, 'steamless')
    if not os.path.exists(os.path.join(sl, 'Steamless.CLI.exe')):
        z = os.path.join(tools, 'steamless.zip')
        download(STEAMLESS_URL, z)
        zipfile.ZipFile(z).extractall(sl)
        os.remove(z)
    # Point Ghidra at our JDK so it never asks.
    props = os.path.join(ghidra_home(), 'support', 'launch.properties')
    with open(props, encoding='utf-8') as f:
        text = f.read()
    jdk = jdk_home().replace('\\', '/')
    text = re.sub(r'(?m)^JAVA_HOME_OVERRIDE=.*$', f'JAVA_HOME_OVERRIDE={jdk}', text)
    with open(props, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'Ghidra {ghidra_home()}\nJDK {jdk}\nSteamless {sl}')


def cmd_setup(args):
    os.makedirs(BIN, exist_ok=True)
    packed = os.path.join(BIN, 'swkotor.exe')
    if not os.path.exists(packed):
        shutil.copy2(GAME_EXE, packed)
    if not os.path.exists(UNPACKED):
        # The Steam exe is wrapped in SteamStub 2.1 (.bind section, encrypted .text).
        cli = os.path.join(TOOLS, 'steamless', 'Steamless.CLI.exe')
        subprocess.run([cli, packed], cwd=BIN, check=True, capture_output=True)
        os.replace(packed + '.unpacked.exe', UNPACKED)
    if os.path.exists(os.path.join(PROJECT_DIR, PROJECT + '.gpr')):
        if not args.force:
            die(f'{PROJECT_DIR} already has the project; pass --force to rebuild it')
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    os.makedirs(EXPORT, exist_ok=True)
    t0 = time.time()
    print('importing and analyzing (~4 min) ...')
    run_headless(['-import', UNPACKED, '-scriptPath', SCRIPTS, '-preScript',
                  'SetAnalysisOptions.java', '-analysisTimeoutPerFile', '14400'],
                 log_name='import.log')
    print('fixing up (functions behind pointers, short strings) ...')
    script_run(['fixup', EXPORT], write=True)
    print('applying names.tsv ...')
    if os.path.exists(NAMES):
        script_run(['apply-names', EXPORT, NAMES, NAMES_STATE, 'all'], write=True)
    print('exporting (~80 s) ...')
    script_run(['export-all', EXPORT])
    print('mapping NWScript routines ...')
    subprocess.run([sys.executable, os.path.join(HERE, 'nwscript_table.py')], check=True,
                   env=dict(os.environ, KOTOR_RE=RE))
    print(f'setup done in {(time.time() - t0) / 60:.1f} min')


# ------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(prog='rex.py', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def add(name, fn, *params):
        sp = sub.add_parser(name)
        for args, kw in params:
            sp.add_argument(*args, **kw)
        sp.set_defaults(fn=fn)
        return sp

    A = lambda *a, **k: (a, k)   # noqa: E731
    add('fn', cmd_fn, A('what'), A('--head', type=int, default=0))
    add('find', cmd_find, A('regex'))
    add('grep', cmd_grep, A('regex'), A('-i', action='store_true'), A('-l', action='store_true'),
        A('--headers', action='store_true', help='also search the header lists'),
        A('--max', type=int, default=200))
    add('callers', cmd_callers, A('what'))
    add('callees', cmd_callees, A('what'))
    add('strings', cmd_strings, A('regex'), A('-i', action='store_true'))
    add('xrefs', cmd_xrefs, A('addr'))
    add('class', cmd_class, A('name'))
    add('imports', cmd_imports, A('regex', nargs='?'))
    add('tables', cmd_tables, A('regex', nargs='?'), A('--min', type=int, default=0),
        A('--all', action='store_true', help='include compiler exception-unwind tables'))
    add('vtables', cmd_vtables, A('regex', nargs='?'))
    add('globals', cmd_globals, A('regex'), A('-v', action='store_true'))
    add('routine', cmd_routine, A('what'))
    add('dword', cmd_dword, A('addr'), A('n', type=int, nargs='?', default=1))
    add('bytes', cmd_bytes, A('addr'), A('n', type=int, nargs='?', default=64))
    add('stats', cmd_stats)
    add('map', cmd_map, A('--step', default='10000'))
    add('name', cmd_name, A('addr'), A('name'), A('--proto'), A('--comment'))
    add('names', cmd_names, A('regex', nargs='?'))
    add('apply', cmd_apply, A('--all', action='store_true'))
    add('autoname', cmd_autoname, A('--write', action='store_true'))
    add('merge', cmd_merge, A('files', nargs='+'), A('--overwrite', action='store_true'))
    add('decompile', cmd_decompile, A('what', nargs='+'))
    add('asm', cmd_asm, A('what', nargs='+'))
    add('export', cmd_export, A('--tables', action='store_true'))
    add('setup', cmd_setup, A('--force', action='store_true'))
    add('install', cmd_install)
    args = p.parse_args()
    try:
        args.fn(args)
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        # The reader (head, a pager) went away: stop quietly.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass


if __name__ == '__main__':
    sys.stdout.reconfigure(errors='replace')
    main()
