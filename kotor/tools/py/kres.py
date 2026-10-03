"""Read-only access to KOTOR's resources, for exploration and probes (not used by the game).

    python kotor/tools/py/kres.py ls [PATTERN] [--type EXT]      list resources (glob on resref)
    python kotor/tools/py/kres.py get RESREF.EXT [-o OUT]       extract one (first in search order)
    python kotor/tools/py/kres.py types                         count resources by type
    python kotor/tools/py/kres.py containers                    list every container file

As a library:

    import kres
    g = kres.Game()                       # KOTOR_DIR or the default install
    data = g.get('p_bastilla', 'utc')     # bytes or None, first match in search order
    for e in g.entries(ext='mdl'): ...    # Entry(resref, ext, container, offset, size)
    kres.read_container(path)             # entries of one ERF/MOD/SAV/RIM file

Search order here (lowest priority first): chitin.key's BIFs, TexturePacks (tpa), then every
module RIM/MOD and lips MOD as separate containers, then Override. This is NOT the engine's order
(see kotor/docs/formats/resources.md); a probe that wants a specific module should use
read_container on its files.

Corpus probes that must see every copy of every resource (all texture packs, patch.erf, rims/,
saves and the module ERFs nested inside SAVEGAME.sav, loose save files) use
`Game.every_entry(ext)` instead: it does not deduplicate and has no priority order.
"""

import fnmatch
import os
import struct
import sys
from collections import Counter, namedtuple

DEFAULT_DIR = r'F:\Steam\steamapps\common\swkotor'

# Resource type ids (Aurora / Odyssey). Unknown ids show as their number.
TYPES = {
    0: 'res', 1: 'bmp', 2: 'mve', 3: 'tga', 4: 'wav', 6: 'plt', 7: 'ini', 8: 'mp3', 9: 'mpg',
    10: 'txt', 11: 'wma', 12: 'wmv', 13: 'xmv', 14: 'log', 2000: 'plh', 2001: 'tex', 2002: 'mdl',
    2003: 'thg', 2005: 'fnt', 2007: 'lua', 2008: 'slt', 2009: 'nss', 2010: 'ncs', 2011: 'mod',
    2012: 'are', 2013: 'set', 2014: 'ifo', 2015: 'bic', 2016: 'wok', 2017: '2da', 2018: 'tlk',
    2022: 'txi', 2023: 'git', 2024: 'bti', 2025: 'uti', 2026: 'btc', 2027: 'utc', 2029: 'dlg',
    2030: 'itp', 2031: 'btt', 2032: 'utt', 2033: 'dds', 2034: 'bts', 2035: 'uts', 2036: 'ltr',
    2037: 'gff', 2038: 'fac', 2039: 'bte', 2040: 'ute', 2041: 'btd', 2042: 'utd', 2043: 'btp',
    2044: 'utp', 2045: 'dft', 2046: 'gic', 2047: 'gui', 2048: 'css', 2049: 'ccs', 2050: 'btm',
    2051: 'utm', 2052: 'dwk', 2053: 'pwk', 2054: 'btg', 2055: 'utg', 2056: 'jrl', 2057: 'sav',
    2058: 'utw', 2059: '4pc', 2060: 'ssf', 2061: 'hak', 2062: 'nwm', 2063: 'bik', 2064: 'ndb',
    2065: 'ptm', 2066: 'ptt', 2067: 'bak', 3000: 'lyt', 3001: 'vis', 3002: 'rim', 3003: 'pth',
    3004: 'lip', 3005: 'bwm', 3006: 'txb', 3007: 'tpc', 3008: 'mdx', 3009: 'rsv', 3010: 'sig',
    3011: 'xbx', 9997: 'erf', 9998: 'bif', 9999: 'key',
}
EXTS = {v: k for k, v in TYPES.items()}

Entry = namedtuple('Entry', 'resref ext container offset size')


def type_name(t):
    return TYPES.get(t, str(t))


def _resref(raw):
    return raw.split(b'\0', 1)[0].decode('latin-1').lower()


def read_key(game_dir):
    """Entries of chitin.key, resolved to offsets inside their BIFs."""
    path = os.path.join(game_dir, 'chitin.key')
    with open(path, 'rb') as f:
        d = f.read()
    if d[:8] != b'KEY V1  ':
        raise ValueError(f'{path}: not a KEY V1 file')
    bif_count, key_count, off_files, off_keys = struct.unpack_from('<4I', d, 8)
    bifs = []
    for i in range(bif_count):
        size, name_off, name_len, drives = struct.unpack_from('<IIHH', d, off_files + 12 * i)
        name = d[name_off:name_off + name_len].split(b'\0', 1)[0].decode('latin-1').replace('\\', os.sep)
        bifs.append(os.path.join(game_dir, name))
    tables = {}
    out = []
    for i in range(key_count):
        o = off_keys + 22 * i
        resref = _resref(d[o:o + 16])
        rtype, res_id = struct.unpack_from('<HI', d, o + 16)
        bif = bifs[res_id >> 20]
        if bif not in tables:
            tables[bif] = _bif_table(bif)
        table = tables[bif]
        idx = res_id & 0xFFFFF
        if idx >= len(table):
            continue
        off, size = table[idx]
        out.append(Entry(resref, type_name(rtype), bif, off, size))
    return out


def _bif_table(path):
    with open(path, 'rb') as f:
        head = f.read(20)
        if head[:8] != b'BIFFV1  ':
            raise ValueError(f'{path}: not a BIFF V1 file')
        var_count, fixed_count, off_var = struct.unpack_from('<3I', head, 8)
        f.seek(off_var)
        raw = f.read(16 * var_count)
    table = []
    for i in range(var_count):
        _id, off, size, _t = struct.unpack_from('<4I', raw, 16 * i)
        table.append((off, size))
    return table


def read_container(path, base=0):
    """Entries of an ERF/MOD/SAV (V1.0) or RIM (V1.0) file, or of one nested in another file at
    byte offset `base` (a save's module .sav inside SAVEGAME.sav). Offsets are absolute in `path`."""
    with open(path, 'rb') as f:
        f.seek(base)
        head = f.read(160)
        magic = head[:8]
        out = []
        if magic[4:] == b'V1.0' and magic[:4] in (b'ERF ', b'MOD ', b'SAV ', b'HAK '):
            _lang, _locsize, count, _off_loc, off_keys, off_res = struct.unpack_from('<6I', head, 8)
            f.seek(base + off_keys)
            keys = f.read(24 * count)
            f.seek(base + off_res)
            res = f.read(8 * count)
            for i in range(count):
                resref = _resref(keys[24 * i:24 * i + 16])
                _rid, rtype = struct.unpack_from('<IH', keys, 24 * i + 16)
                off, size = struct.unpack_from('<II', res, 8 * i)
                out.append(Entry(resref, type_name(rtype), path, base + off, size))
        elif magic == b'RIM V1.0':
            _res, count, off_keys = struct.unpack_from('<3I', head, 8)
            f.seek(base + off_keys)
            keys = f.read(32 * count)
            for i in range(count):
                resref = _resref(keys[32 * i:32 * i + 16])
                rtype, _rid, off, size = struct.unpack_from('<4I', keys, 32 * i + 16)
                out.append(Entry(resref, type_name(rtype), path, base + off, size))
        else:
            raise ValueError(f'{path}: unknown container {magic!r}')
    return out


def read_entry(e):
    with open(e.container, 'rb') as f:
        f.seek(e.offset)
        return f.read(e.size)


class Game:
    def __init__(self, game_dir=None):
        self.dir = game_dir or os.environ.get('KOTOR_DIR', DEFAULT_DIR)
        self._entries = None

    def containers(self):
        out = []
        for sub in ('TexturePacks', 'modules', 'lips', 'rims'):
            d = os.path.join(self.dir, sub)
            if os.path.isdir(d):
                for n in sorted(os.listdir(d)):
                    if n.lower().endswith(('.erf', '.mod', '.rim', '.sav')):
                        out.append(os.path.join(d, n))
        return out

    def entries(self, ext=None):
        if self._entries is None:
            es = read_key(self.dir)
            for c in self.containers():
                # Only the top texture pack quality (tpa) joins the default view.
                base = os.path.basename(c).lower()
                if base.startswith('swpc_tex_tp') and base != 'swpc_tex_tpa.erf':
                    continue
                es.extend(read_container(c))
            ov = os.path.join(self.dir, 'Override')
            if os.path.isdir(ov):
                for n in sorted(os.listdir(ov)):
                    stem, dot, x = n.rpartition('.')
                    if dot:
                        p = os.path.join(ov, n)
                        es.append(Entry(stem.lower(), x.lower(), p, 0, os.path.getsize(p)))
            self._entries = es
        if ext is None:
            return list(self._entries)
        return [e for e in self._entries if e.ext == ext]

    def every_entry(self, ext=None):
        """Every copy of every resource in the install, no priority and no deduplication:
        chitin.key's BIFs, all four texture packs, modules/, lips/, rims/, patch.erf, Override,
        and each save (SAVEGAME.sav, the module .sav files nested in it, and the loose
        GLOBALVARS/PARTYTABLE/savenfo .res and Screen.tga files)."""
        es = read_key(self.dir)
        conts = self.containers()
        patch = os.path.join(self.dir, 'patch.erf')
        if os.path.isfile(patch):
            conts.append(patch)
        for c in conts:
            es.extend(read_container(c))
        ov = os.path.join(self.dir, 'Override')
        if os.path.isdir(ov):
            for n in sorted(os.listdir(ov)):
                stem, dot, x = n.rpartition('.')
                if dot:
                    p = os.path.join(ov, n)
                    es.append(Entry(stem.lower(), x.lower(), p, 0, os.path.getsize(p)))
        saves = os.path.join(self.dir, 'Saves')
        if os.path.isdir(saves):
            for s in sorted(os.listdir(saves)):
                sd = os.path.join(saves, s)
                if not os.path.isdir(sd):
                    continue
                for n in sorted(os.listdir(sd)):
                    p = os.path.join(sd, n)
                    stem, dot, x = n.rpartition('.')
                    if x.lower() == 'sav':
                        inner = read_container(p)
                        es.extend(inner)
                        for e in inner:
                            if e.ext == 'sav':
                                es.extend(read_container(p, e.offset))
                    elif dot:
                        es.append(Entry(stem.lower(), x.lower(), p, 0, os.path.getsize(p)))
        if ext is None:
            return es
        return [e for e in es if e.ext == ext]

    def find(self, resref, ext):
        """Every entry for resref.ext, lowest priority first."""
        resref = resref.lower()
        return [e for e in self.entries() if e.resref == resref and e.ext == ext]

    def get(self, resref, ext):
        found = self.find(resref, ext)
        return read_entry(found[-1]) if found else None


def main(argv):
    g = Game()
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == 'ls':
        pat = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else '*'
        ext = argv[argv.index('--type') + 1] if '--type' in argv else None
        for e in g.entries(ext):
            if fnmatch.fnmatch(e.resref, pat.lower()):
                print(f'{e.resref}.{e.ext}\t{e.size}\t{os.path.relpath(e.container, g.dir)}')
    elif cmd == 'get':
        name = argv[1]
        resref, _, ext = name.rpartition('.')
        data = g.get(resref, ext.lower())
        if data is None:
            print(f'{name}: not found', file=sys.stderr)
            return 1
        out = argv[argv.index('-o') + 1] if '-o' in argv else name
        with open(out, 'wb') as f:
            f.write(data)
    elif cmd == 'types':
        for ext, n in Counter(e.ext for e in g.entries()).most_common():
            print(f'{ext}\t{n}')
    elif cmd == 'containers':
        for c in g.containers():
            print(c)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
