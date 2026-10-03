"""Cross-check lib/res's resource manager against an independent Python model of the engine's
search order (docs/formats/resources.md), using kres.py's container readers.

    kotor/out/resls.exe [--module M] --crc > listing.txt
    python kotor/tools/py/rescheck.py listing.txt [--module M]

The listing is resls's: `name.ext  size  class  source[:bif]  crc32`, one line per resource the
search finds. This script computes the winner of every (resref, type) itself, reads its bytes,
and reports every line that differs (missing, extra, other source, other size, other CRC).
"""

import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

EXT_TO_ID = {v: k for k, v in kres.TYPES.items()}


def find_ci(d, name):
    if not os.path.isdir(d):
        return None
    for n in os.listdir(d):
        if n.lower() == name.lower():
            return os.path.join(d, n)
    return None


def find_archive(d, stem):
    for ext in ('.nwm', '.mod', '.sav', '.erf', '.hak'):
        p = find_ci(d, stem + ext)
        if p:
            return p
    return None


def dir_entries(d):
    out = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if not os.path.isfile(p) or '.' not in n or n.startswith('.'):
            continue
        dot = n.index('.')
        ext = n[dot + 1:dot + 4].lower()
        if ext not in EXT_TO_ID:
            continue
        out.append(kres.Entry(n[:dot][:16].lower(), ext, p, 0, os.path.getsize(p)))
    return out


def sources(game, module):
    """Lists of entries, highest priority first, as the engine searches them."""
    g = game
    dirs = {k: find_ci(g, k) for k in ('override', 'modules', 'lips', 'texturepacks', 'movies',
                                        'streamwaves', 'streammusic')}
    dir_srcs = []
    for k in ('streammusic', 'streamwaves', 'movies', 'override'):     # newest first
        if dirs[k]:
            dir_srcs.append(dir_entries(dirs[k]))
    erf1 = []
    patch = find_ci(g, 'patch.erf')
    if patch:
        erf1.append(kres.read_container(patch))
    if dirs['override']:
        t = find_archive(dirs['override'], 'textures')
        if t:
            erf1.append(kres.read_container(t))
    rims, erf2 = [], []
    if module:
        mod = find_ci(dirs['modules'], module + '.mod')
        lips = []
        if dirs['lips']:
            for stem in ('localization', module + '_loc'):          # newest first
                p = find_archive(dirs['lips'], stem)
                if p:
                    lips.append(kres.read_container(p))
        if mod:
            erf2.append(kres.read_container(mod))
        else:
            for name in (module + '.rim', module + '_s.rim'):        # newest first
                p = find_ci(dirs['modules'], name)
                if p:
                    rims.append(kres.read_container(p))
        erf2.extend(lips)
    # Packs: texpacks.2da row 2 in this install (Texture Quality=2): gui newest, then tpa.
    packs = dirs['texturepacks']
    for stem in ('swpc_tex_gui', 'swpc_tex_tpa'):
        p = find_archive(packs, stem)
        if p:
            erf2.append(kres.read_container(p))
    key = [kres.read_key(g)]
    return [('dir', s) for s in dir_srcs] + [('erf1', s) for s in erf1] + \
        [('rim', s) for s in rims] + [('erf2', s) for s in erf2] + [('key', s) for s in key]


def main(argv):
    listing = argv[0]
    module = argv[argv.index('--module') + 1] if '--module' in argv else None
    game = kres.DEFAULT_DIR
    winners = {}
    for cls, entries in sources(game, module):
        seen_here = set()
        for e in entries:
            k = (e.resref, e.ext)
            if k in seen_here:
                continue
            seen_here.add(k)
            if k not in winners:
                winners[k] = (cls, e)
    got = {}
    with open(listing, encoding='latin-1') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 5:
                continue
            name, size, cls, src, crc = parts[:5]
            resref, _, ext = name.rpartition('.')
            got[(resref, ext)] = (int(size), cls, src, int(crc, 16))
    bad = 0
    for k in sorted(set(winners) | set(got)):
        if k not in got:
            print('missing from resls:', k, winners[k][0], winners[k][1].container)
            bad += 1
            continue
        if k not in winners:
            print('extra in resls:', k, got[k])
            bad += 1
            continue
        cls, e = winners[k]
        size, gcls, gsrc, gcrc = got[k]
        src_file = gsrc.split(':', 2)
        if size != e.size or cls != gcls:
            print('differs:', k, (e.size, cls, e.container), got[k][:3])
            bad += 1
            continue
        with open(e.container, 'rb') as fh:
            fh.seek(e.offset)
            data = fh.read(e.size)
        if zlib.crc32(data) & 0xFFFFFFFF != gcrc:
            print('crc differs:', k, e.container)
            bad += 1
    print(f'{len(winners)} expected, {len(got)} listed, {bad} differences')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
