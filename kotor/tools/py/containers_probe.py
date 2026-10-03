"""Check every container in the install against docs/formats/{key-bif,erf,rim}.md.

    python kotor/tools/py/containers_probe.py [--verbose]

Parses chitin.key, every BIF it names, every ERF/MOD/SAV/HAK (TexturePacks, lips, modules, rims,
patch.erf, saves and the module saves nested in SAVEGAME.sav) and every RIM, with independent code
(not kres.py), and checks each header field, table and data region for the properties the docs
claim. Prints what it saw and every violation; exits 1 if any check failed.
"""

import os
import struct
import sys
from collections import Counter, defaultdict

GAME = os.environ.get('KOTOR_DIR', r'F:\Steam\steamapps\common\swkotor')
VERBOSE = '--verbose' in sys.argv

fails = []
notes = defaultdict(Counter)   # topic -> Counter of observations


def fail(where, msg):
    fails.append(f'{where}: {msg}')


def note(topic, what, n=1):
    notes[topic][what] += n


def resref_check(where, raw, topic):
    """raw is the 16-byte field. Record charset/length/padding facts."""
    name, nul, rest = raw.partition(b'\0')
    if not nul:
        note(topic, 'resref fills all 16 bytes (no NUL)')
    elif any(rest):
        note(topic, 'resref has non-zero bytes after the NUL')
        fail(where, f'garbage after resref NUL: {raw!r}')
    s = name.decode('latin-1')
    if s != s.lower():
        note(topic, 'resref has upper case')
    if s != s.upper() and s != s.lower():
        note(topic, 'resref mixed case')
    if not s:
        fail(where, 'empty resref')
    bad = [c for c in s if not (c.isalnum() or c in '_-')]
    if bad:
        note(topic, f'resref chars outside [A-Za-z0-9_-]: {"".join(sorted(set(bad)))!r}')
    note(topic + ' resref length', len(name))
    return s


def check_layout(where, regions, file_size, topic):
    """regions: list of (start, size, label). Report overlap, gaps, alignment, trailing bytes."""
    rs = sorted((s, z, l) for s, z, l in regions if z > 0)
    end = 0
    for s, z, l in rs:
        if s < end:
            fail(where, f'{l} at {s} overlaps previous region ending {end}')
        elif s > end:
            note(topic, f'gap before {l.split()[0]}')
            note(topic + ' gap sizes', s - end)
        end = max(end, s + z)
    if end > file_size:
        fail(where, f'regions end at {end} beyond file size {file_size}')
    elif end < file_size:
        note(topic, 'trailing bytes after last region')
        note(topic + ' trailing sizes', file_size - end)


# ---------------------------------------------------------------- KEY / BIF

def probe_key_bif():
    path = os.path.join(GAME, 'chitin.key')
    d = open(path, 'rb').read()
    W = 'chitin.key'
    if d[:8] != b'KEY V1  ':
        fail(W, f'magic {d[:8]!r}')
        return
    bif_count, key_count, off_files, off_keys, year, day = struct.unpack_from('<6I', d, 8)
    print(f'KEY: {bif_count} BIFs, {key_count} keys, file table @{off_files}, key table @{off_keys}, '
          f'build {1900 + year} day {day}, size {len(d)}')
    if any(d[32:64]):
        fail(W, 'reserved header bytes not zero')
    if off_files != 64:
        fail(W, f'file table not right after header ({off_files})')
    bifs = []
    names_end = off_files + 12 * bif_count
    for i in range(bif_count):
        size, noff, nlen, drives = struct.unpack_from('<IIHH', d, off_files + 12 * i)
        raw = d[noff:noff + nlen]
        if not raw.endswith(b'\0') or b'\0' in raw[:-1]:
            fail(W, f'bif {i} name not exactly NUL-terminated within its size: {raw!r}')
        name = raw.rstrip(b'\0').decode('latin-1')
        note('KEY', f'drives={drives}')
        if noff != names_end:
            note('KEY', 'BIF names not packed in order')
        names_end = noff + nlen
        bifs.append((name, size))
    if names_end != off_keys:
        note('KEY', f'gap of {off_keys - names_end} between names and keys')
    if off_keys + 22 * key_count != len(d):
        fail(W, f'key table ends at {off_keys + 22 * key_count}, file is {len(d)}')

    # BIFs
    bif_tables = []
    for i, (name, size) in enumerate(bifs):
        p = os.path.join(GAME, name.replace('\\', os.sep))
        if not os.path.isfile(p):
            fail(W, f'BIF {name} missing')
            bif_tables.append(None)
            continue
        real = os.path.getsize(p)
        if real != size:
            fail(W, f'{name}: KEY says {size} bytes, file has {real}')
        with open(p, 'rb') as f:
            h = f.read(20)
            if h[:8] != b'BIFFV1  ':
                fail(name, f'magic {h[:8]!r}')
                bif_tables.append(None)
                continue
            nvar, nfix, off_var = struct.unpack_from('<3I', h, 8)
            if nfix:
                note('BIF', 'fixed resources present')
            if off_var != 20:
                note('BIF', f'variable table at {off_var}')
            f.seek(off_var)
            raw = f.read(16 * nvar + 20 * nfix)
        table = []
        regions = [(0, 20, 'header'), (off_var, 16 * nvar + 20 * nfix, 'tables')]
        for j in range(nvar):
            rid, off, sz, rtype = struct.unpack_from('<4I', raw, 16 * j)
            table.append((rid, off, sz, rtype))
            regions.append((off, sz, f'resource {j}'))
            if off % 4:
                note('BIF', 'resource offset not 4-aligned')
            if rtype > 0xFFFF:
                fail(name, f'resource {j} type {rtype} > 16 bits')
        offs = [t[1] for t in table]
        if offs != sorted(offs):
            note('BIF', 'resource data not in table order')
        check_layout(name, regions, real, 'BIF layout')
        bif_tables.append(table)
        note('BIF', 'files')
        note('BIF variable counts', nvar)

    # keys
    seen = {}
    used = [set() for _ in bifs]
    types = Counter()
    prev = None
    for k in range(key_count):
        o = off_keys + 22 * k
        rr = resref_check(f'{W} key {k}', d[o:o + 16], 'KEY')
        rtype, rid = struct.unpack_from('<HI', d, o + 16)
        types[rtype] += 1
        bi, fixed, var = rid >> 20, (rid >> 14) & 0x3F, rid & 0x3FFF
        if fixed:
            note('KEY', 'ResID has non-zero fixed-index bits (14..19)')
        if bi >= len(bifs):
            fail(W, f'key {rr}.{rtype}: BIF index {bi} out of range')
            continue
        table = bif_tables[bi]
        if table is None:
            continue
        idx = rid & 0xFFFFF
        if idx >= len(table):
            fail(W, f'key {rr}.{rtype}: index {idx} beyond {bifs[bi][0]} ({len(table)})')
            continue
        brid, off, sz, btype = table[idx]
        if btype != rtype:
            fail(W, f'key {rr}: type {rtype} but BIF entry type {btype}')
        if brid == rid:
            note('KEY', 'BIF entry id == full ResID')
        elif brid == idx:
            note('KEY', 'BIF entry id == index only')
        else:
            fail(W, f'key {rr}: BIF entry id {brid:#x} vs ResID {rid:#x}')
        if idx in used[bi]:
            fail(W, f'two keys point at {bifs[bi][0]}[{idx}]')
        used[bi].add(idx)
        key = (rr.lower(), rtype)
        if key in seen:
            note('KEY', 'duplicate resref+type (later key wins?)')
            if VERBOSE:
                print(f'  duplicate key {rr}.{rtype}: {bifs[seen[key]][0]} and {bifs[bi][0]}')
        seen[key] = bi
        order = (bi, idx)
        if prev and order < prev:
            note('KEY', 'keys not sorted by (bif, index)')
        prev = order
    for bi, table in enumerate(bif_tables):
        if table is None:
            continue
        unused = len(table) - len(used[bi])
        if unused:
            note('KEY', f'BIF entries with no key')
            if VERBOSE:
                print(f'  {bifs[bi][0]}: {unused} entries unreferenced')
        for j, t in enumerate(table):
            if t[0] & 0xFFFFF != j:
                note('BIF', 'entry id low 20 bits != its index')
            if t[0] >> 20 != bi:
                note('BIF', 'entry id high 12 bits != KEY bif index')
    return types


# ---------------------------------------------------------------- ERF family

def probe_erf(path, base=0, label=None):
    W = label or os.path.relpath(path, GAME)
    with open(path, 'rb') as f:
        f.seek(base)
        h = f.read(160)
        magic, ver = h[:4], h[4:8]
        (nlang, locsize, count, off_loc, off_keys, off_res, year, day, desc) = struct.unpack_from('<9I', h, 8)
        topic = 'ERF'
        note('ERF magic', f'{magic.decode()!r} {os.path.splitext(path)[1].lower() if not base else "(nested)"}')
        if ver != b'V1.0':
            fail(W, f'version {ver!r}')
        if any(h[44:160]):
            note(topic, 'reserved bytes 44..159 not zero')
            if VERBOSE:
                print(f'  {W}: reserved {h[44:160].rstrip(bytes(1))!r}')
        note('ERF build', f'{1900 + year if year else 0}/{day}')
        note('ERF desc strref', f'{desc:#x}' if desc not in (0, 0xFFFFFFFF) else str(desc if desc == 0 else -1))
        note('ERF offsets', f'loc@{off_loc} keys@{off_keys} res@{off_res}' if off_loc == 160 else 'loc not at 160')
        size = (os.path.getsize(path) - base) if not base else None
        # localized strings
        f.seek(base + off_loc)
        loc = f.read(locsize)
        p = 0
        for i in range(nlang):
            lang, sl = struct.unpack_from('<2I', loc, p)
            s = loc[p + 8:p + 8 + sl]
            note('ERF locstrings', f'lang {lang}: {s.decode("cp1252")!r}')
            p += 8 + sl
        if p != locsize:
            fail(W, f'localized strings use {p} of declared {locsize} bytes')
        if off_keys != off_loc + locsize:
            note(topic, f'gap between loc strings and keys')
        if off_res != off_keys + 24 * count:
            note(topic, 'resource list not right after key list')
        f.seek(base + off_keys)
        keys = f.read(24 * count)
        f.seek(base + off_res)
        res = f.read(8 * count)
        regions = [(0, 160, 'header'), (off_loc, locsize, 'locstrings'),
                   (off_keys, 24 * count, 'keys'), (off_res, 8 * count, 'reslist')]
        seen = set()
        entries = []
        prev_off = -1
        for i in range(count):
            rr = resref_check(f'{W} key {i}', keys[24 * i:24 * i + 16], 'ERF')
            rid, rtype, unused = struct.unpack_from('<IHH', keys, 24 * i + 16)
            if rid != i:
                note(topic, 'ResID != entry index')
            if unused:
                note(topic, f'key unused field = {unused}')
            off, sz = struct.unpack_from('<II', res, 8 * i)
            regions.append((off, sz, f'resource {i}'))
            if off < prev_off:
                note(topic, 'data not in key order')
            prev_off = off
            if off % 4:
                note(topic, 'resource offset not 4-aligned')
            k = (rr.lower(), rtype)
            if k in seen:
                note(topic, 'duplicate resref+type in one file')
                if VERBOSE:
                    print(f'  {W}: duplicate {rr}.{rtype}')
            seen.add(k)
            if sz == 0:
                note(topic, 'zero-size resource')
            entries.append((rr, rtype, off, sz))
        if base == 0:
            check_layout(W, regions, os.path.getsize(path), 'ERF layout')
        else:
            last = max((o + s for o, s, _ in regions), default=0)
            note('ERF layout', f'nested: regions end at {last}')
        # sort order of keys
        names = [(e[0].lower(), e[1]) for e in entries]
        if names == sorted(names):
            note('ERF key order', f'{magic.decode()} sorted by resref')
        else:
            note('ERF key order', f'{magic.decode()} not sorted')
        return entries


# ---------------------------------------------------------------- RIM

def probe_rim(path):
    W = os.path.relpath(path, GAME)
    d = open(path, 'rb').read()
    if d[:8] != b'RIM V1.0':
        fail(W, f'magic {d[:8]!r}')
        return []
    unk, count, off_keys, off_res = struct.unpack_from('<4I', d, 8)
    note('RIM', f'field@8={unk}')
    note('RIM', f'keys@{off_keys}')
    note('RIM', f'field@20={off_res}')
    if any(d[24:120]):
        note('RIM', 'reserved 24..119 not zero')
    regions = [(0, 120, 'header'), (off_keys, 32 * count, 'keys')]
    entries = []
    seen = set()
    prev = -1
    for i in range(count):
        o = off_keys + 32 * i
        rr = resref_check(f'{W} key {i}', d[o:o + 16], 'RIM')
        rtype, rid, off, sz = struct.unpack_from('<4I', d, o + 16)
        if rid != i:
            note('RIM', 'ResID != entry index')
        if rtype > 0xFFFF:
            fail(W, f'type {rtype} > 16 bits')
        regions.append((off, sz, f'resource {i}'))
        if off < prev:
            note('RIM', 'data not in key order')
        prev = off
        if off % 16:
            note('RIM', 'resource offset not 16-aligned')
        k = (rr.lower(), rtype)
        if k in seen:
            note('RIM', 'duplicate resref+type in one file')
        seen.add(k)
        entries.append((rr, rtype, off, sz))
    check_layout(W, regions, len(d), 'RIM layout')
    # padding content
    rs = sorted((o, s) for _, _, o, s in entries)
    end = off_keys + 32 * count
    for o, s in rs:
        if o > end and any(d[end:o]):
            note('RIM', 'non-zero padding')
        end = o + s
    names = [(e[0].lower(), e[1]) for e in entries]
    note('RIM key order', 'sorted' if names == sorted(names) else 'not sorted')
    # placement rules documented in rim.md (observations, not requirements)
    offs = [(o, s) for _, _, o, s in entries]
    if offs:
        kend = off_keys + 32 * count
        a16 = (kend + 15) & ~15
        first_ok = offs[0][0] == (a16 if not off_res else (a16 + 127) & ~127)
        note('RIM placement', f'first resource {"follows" if first_ok else "breaks"} the rule (flag {off_res})')
        for (o1, s1), (o2, _s2) in zip(offs, offs[1:]):
            want = ((o1 + s1 + 3) & ~3) + 16 if not off_res else (o1 + s1 + 16 + 127) & ~127
            note('RIM placement', f'next resource {"follows" if o2 == want else "breaks"} the rule (flag {off_res})')
        note('RIM placement', f'{len(d) - (offs[-1][0] + offs[-1][1])} bytes after the last resource')
    return entries


def main():
    types_by_container = defaultdict(Counter)
    ktypes = probe_key_bif()
    for t, n in (ktypes or {}).items():
        types_by_container['chitin'][t] += n
    n_erf = n_rim = 0
    for sub in ('TexturePacks', 'lips', 'modules', 'rims', '.'):
        dpath = os.path.join(GAME, sub)
        for n in sorted(os.listdir(dpath)):
            p = os.path.join(dpath, n)
            x = os.path.splitext(n)[1].lower()
            if x in ('.erf', '.mod', '.sav', '.hak'):
                for _, t, _, _ in probe_erf(p):
                    types_by_container[sub if sub != '.' else 'root'][t] += 1
                n_erf += 1
            elif x == '.rim':
                for _, t, _, _ in probe_rim(p):
                    types_by_container[sub][t] += 1
                n_rim += 1
    saves = os.path.join(GAME, 'Saves')
    for s in sorted(os.listdir(saves)):
        sd = os.path.join(saves, s)
        if not os.path.isdir(sd):
            continue
        for n in sorted(os.listdir(sd)):
            if n.lower().endswith('.sav'):
                p = os.path.join(sd, n)
                for rr, t, off, sz in probe_erf(p):
                    types_by_container['Saves'][t] += 1
                    if t == 2057:
                        for _, t2, _, _ in probe_erf(p, off, f'{s}/{n}/{rr}.sav'):
                            types_by_container['Saves (nested)'][t2] += 1
                        n_erf += 1
                n_erf += 1
    print(f'ERF-family files: {n_erf}, RIM files: {n_rim}')
    for topic in sorted(notes):
        c = notes[topic]
        print(f'\n[{topic}]')
        for what, n in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))[:40]:
            print(f'  {n:7d}  {what}')
    print('\n[type ids by container]')
    for c, cnt in types_by_container.items():
        print(f'  {c}: ' + ', '.join(f'{t}:{n}' for t, n in sorted(cnt.items())))
    print(f'\n{len(fails)} failures')
    for f_ in fails[:50]:
        print('  FAIL', f_)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
