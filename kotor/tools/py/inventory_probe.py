"""Census of the install for docs/formats/inventory.md.

    python kotor/tools/py/inventory_probe.py

Counts resources by type and container class, lists the modules with their companion files,
summarizes the loose directories (streammusic, streamsounds, streamwaves, movies, lips, rims,
TexturePacks, Saves) and the WAV encodings in them, and reads the save's container. Read-only.
"""

import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

G = kres.DEFAULT_DIR


def is_mp3(b):
    return b[:3] == b'ID3' or (len(b) > 1 and b[0] == 0xFF and b[1] & 0xE0 == 0xE0)


def wav_kind(d, total):
    """Classify a .wav's leading bytes `d` (file length `total`)."""
    if d[:4] != b'RIFF':
        return 'raw MP3 (no RIFF)' if is_mp3(d) else f'unknown {d[:4]!r}'
    p = 12
    fmt = None
    data = None
    while p + 8 <= len(d):
        cid, size = d[p:p + 4], struct.unpack_from('<I', d, p + 4)[0]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', d, p + 8)
        if cid == b'data':
            data = (p + 8, size)
            break
        p += 8 + size + (size & 1)
    if fmt is None or data is None:
        return 'RIFF without fmt/data'
    tag, ch, rate, _bps, _align, bits = fmt
    o, n = data
    if n == 0 and is_mp3(d[o:o + 4]):
        return f'{o}-byte stub RIFF header (data size 0), then MP3'
    names = {1: 'PCM', 0x11: 'IMA-ADPCM', 0x55: 'MP3'}
    kind = f'{names.get(tag, hex(tag))} {ch}ch {rate}Hz' + (f' {bits}-bit' if tag == 1 else '')
    if o + n < total:
        kind += ', chunks after data'
    return kind


def gff_top_fields(d):
    """Minimal read of a GFF's top-level struct: {label: (type, raw)}; enough for names."""
    (so, sc, fo, fc, lo, lc, fdo, fds, fio, fis, lio, lis) = struct.unpack_from('<12I', d, 8)
    _t, data, count = struct.unpack_from('<3I', d, so)
    idx = [data] if count == 1 else list(struct.unpack_from(f'<{count}I', d, fio + data))
    out = {}
    for i in idx:
        ftype, li, val = struct.unpack_from('<3I', d, fo + 12 * i)
        label = d[lo + 16 * li:lo + 16 * li + 16].split(b'\0')[0].decode()
        out[label] = (ftype, val, fdo)
    return out


def gff_resref(d, f):
    _t, val, fdo = f
    n = d[fdo + val]
    return d[fdo + val + 1:fdo + val + 1 + n].decode('latin-1')


def gff_locstring(d, f, tlk):
    _t, val, fdo = f
    _size, strref, count = struct.unpack_from('<3I', d, fdo + val)
    p = fdo + val + 12
    for _ in range(count):
        _lid, n = struct.unpack_from('<2I', d, p)
        s = d[p + 8:p + 8 + n].decode('cp1252')
        if s:
            return s
        p += 8 + n
    return tlk(strref)


def tlk_reader(path):
    d = open(path, 'rb').read()
    _lang, count, off = struct.unpack_from('<3I', d, 8)

    def get(strref):
        if strref >= count:
            return ''
        _flags, _snd, _v, _p, o, n, _len = struct.unpack_from('<I16sIIIIf', d, 20 + 40 * strref)
        return d[off + o:off + o + n].decode('cp1252')
    return get


def main():
    g = kres.Game()
    es = g.every_entry()

    def cls(e):
        c = os.path.relpath(e.container, G).replace('\\', '/')
        lc = c.lower()
        if lc.startswith('data/'):
            return c
        if lc.startswith('modules/'):
            return 'modules/*_s.rim' if lc.endswith('_s.rim') else 'modules/*.rim'
        if lc.startswith('lips/'):
            return 'lips/' + os.path.basename(c) if not lc.endswith('_loc.mod') else 'lips/*_loc.mod'
        if lc.startswith('saves/'):
            return 'Saves'
        return c

    by = defaultdict(Counter)
    for e in es:
        by[cls(e)][e.ext] += 1
    print('== resources by container ==')
    for c in sorted(by):
        tot = sum(by[c].values())
        print(f'{c}: {tot}  ' + ', '.join(f'{k} {v}' for k, v in by[c].most_common()))
    tt = Counter(e.ext for e in es)
    print(f'\n== by type (every copy, {len(es)} total) ==')
    print(', '.join(f'{k} {v}' for k, v in tt.most_common()))
    uniq = {(e.resref, e.ext) for e in es}
    print(f'distinct resref+type: {len(uniq)}')

    print('\n== loose directories ==')
    for sub in ('streammusic', 'streamsounds', 'streamwaves', 'movies', 'lips', 'rims', 'modules',
                'TexturePacks', 'Override', 'data', 'launcher', 'miles', 'utils', 'logs'):
        p = os.path.join(G, sub)
        files = []
        for root, _dirs, fs in os.walk(p):
            for f in fs:
                files.append(os.path.join(root, f))
        size = sum(os.path.getsize(f) for f in files)
        exts = Counter(os.path.splitext(f)[1].lower() for f in files)
        print(f'{sub}/: {len(files)} files, {size / 1e6:.1f} MB, ' + ', '.join(f'{k} {v}' for k, v in exts.most_common()))

    print('\n== WAV encodings ==')
    kinds = defaultdict(Counter)
    for sub in ('streammusic', 'streamsounds', 'streamwaves'):
        for root, _dirs, fs in os.walk(os.path.join(G, sub)):
            for f in fs:
                q = os.path.join(root, f)
                with open(q, 'rb') as fh:
                    d = fh.read(4096)
                kinds[sub][wav_kind(d, os.path.getsize(q))] += 1
    for e in es:
        if e.ext == 'wav':
            kinds['wav resources (BIF/rims)'][wav_kind(kres.read_entry(e)[:4096], e.size)] += 1
    for k, c in kinds.items():
        print(f'{k}:')
        for what, n in c.most_common():
            print(f'   {n:6d}  {what}')

    print('\n== root files ==')
    for n in sorted(os.listdir(G)):
        p = os.path.join(G, n)
        if os.path.isfile(p):
            with open(p, 'rb') as fh:
                head = fh.read(8)
            print(f'{n}: {os.path.getsize(p)} bytes, starts {head!r}')

    print('\n== saves ==')
    sd = os.path.join(G, 'Saves')
    for s in sorted(os.listdir(sd)):
        p = os.path.join(sd, s)
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                q = os.path.join(p, n)
                with open(q, 'rb') as fh:
                    head = fh.read(8)
                print(f'{s}/{n}: {os.path.getsize(q)} bytes, starts {head!r}')
                if n.lower().endswith('.sav'):
                    for e in kres.read_container(q):
                        print(f'    {e.resref}.{e.ext} {e.size}')
                        if e.ext == 'sav':
                            for e2 in kres.read_container(q, e.offset):
                                print(f'        {e2.resref}.{e2.ext} {e2.size}')
        else:
            print(f'{s}: {os.path.getsize(p)} bytes')

    print('\n== modules ==')
    tlk = tlk_reader(os.path.join(G, 'dialog.tlk'))
    md = os.path.join(G, 'modules')
    lips = {n.lower(): n for n in os.listdir(os.path.join(G, 'lips'))}
    sw = {n.lower() for n in os.listdir(os.path.join(G, 'streamwaves'))}
    print('module | area (are/git) | area name (ARE Name) | _s.rim entries | _loc.mod lips | streamwaves/<area>')
    for n in sorted(os.listdir(md), key=str.lower):
        if n.lower().endswith('_s.rim'):
            continue
        m = n[:-4]
        es = kres.read_container(os.path.join(md, n))
        are = next(e for e in es if e.ext == 'are')
        ifo = next(e for e in es if e.ext == 'ifo')
        ad = kres.read_entry(are)
        name = gff_locstring(ad, gff_top_fields(ad)['Name'], tlk)
        idd = kres.read_entry(ifo)
        entry = gff_resref(idd, gff_top_fields(idd)['Mod_Entry_Area'])
        s_ = [x for x in os.listdir(md) if x.lower() == (m + '_s.rim').lower()]
        ns = len(kres.read_container(os.path.join(md, s_[0]))) if s_ else 0
        lp = lips.get((m + '_loc.mod').lower())
        nl = len(kres.read_container(os.path.join(G, 'lips', lp))) if lp else 0
        flag = 'yes' if are.resref in sw else '-'
        if entry != are.resref:
            print(f'  NOTE {m}: Mod_Entry_Area {entry} != area {are.resref}')
        print(f'{m} | {are.resref} | {name} | {ns} | {nl} | {flag}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
