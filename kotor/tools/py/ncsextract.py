"""Dump every unique NCS script in the install to kotor/extract/ncs/, for the ctxlang script
tools (ncsdis, ncsrun) until the resource manager reads the install itself. Exploration only.

    python kotor/tools/py/ncsextract.py [OUT_DIR]

Every copy (kres.Game().every_entry('ncs'): BIFs, module RIMs/MODs, rims/, Override, saves) is
read and deduplicated by content (SHA-1). Each unique content is written once, as RESREF.ncs for
the first content met under that resref and RESREF@SHA8.ncs for any other content sharing it.
index.tsv lists file, resref, sha1, size, copies and the first container holding it.
"""

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import kres  # noqa: E402
from ncsdis import read_entries  # noqa: E402


def main(argv):
    out = argv[0] if argv else os.path.join(KOTOR, 'extract', 'ncs')
    os.makedirs(out, exist_ok=True)
    g = kres.Game()
    by_hash = {}            # sha1 -> [file, resref, size, copies, container]
    used = set()            # file names taken
    copies = 0
    for e, data in read_entries(g.every_entry('ncs')):
        copies += 1
        h = hashlib.sha1(data).hexdigest()
        if h in by_hash:
            by_hash[h][3] += 1
            continue
        name = f'{e.resref}.ncs'
        if name in used:
            name = f'{e.resref}@{h[:8]}.ncs'
        used.add(name)
        with open(os.path.join(out, name), 'wb') as f:
            f.write(data)
        by_hash[h] = [name, e.resref, len(data), 1, os.path.relpath(e.container, g.dir)]
    rows = sorted(by_hash.items(), key=lambda kv: kv[1][0])
    with open(os.path.join(out, 'index.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('file\tresref\tsha1\tsize\tcopies\tfirst_container\n')
        for h, (name, resref, size, n, cont) in rows:
            f.write(f'{name}\t{resref}\t{h}\t{size}\t{n}\t{cont}\n')
    print(f'{copies} NCS copies, {len(by_hash)} unique contents written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
