"""Extract every TPC, TGA and standalone TXI in the install to one flat directory.

    python kotor/tools/py/texdump.py [OUT_DIR]       default G:/Dev/zlang/kotor/extract/tex

There is no resource manager in ctxlang yet, so tools/texcheck (and anything else that wants the
textures as plain files) reads this directory. Each copy of each resource gets its own file,
`<container-stem>__<resref>.<ext>`: the three quality packs, the GUI pack, patch.erf and the BIFs
hold the same names, and none may overwrite another. Loose save files (Screen.tga) are named after
their save's directory, `save-<dir>__<resref>.<ext>`, with everything but letters and digits
turned into `_`. Files already there with the right size are left alone, so a rerun is quick.

The directory is git-ignored (kotor/extract): the files are the game's, not ours.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

DEFAULT_OUT = 'G:/Dev/zlang/kotor/extract/tex'


def stem_of(game, e):
    """The container part of an extracted file's name."""
    path = os.path.normpath(e.container)
    saves = os.path.normpath(os.path.join(game.dir, 'Saves'))
    if path.lower().startswith(saves.lower() + os.sep):
        rel = os.path.relpath(path, saves)
        parts = rel.split(os.sep)
        if len(parts) >= 2 and not parts[-1].lower().endswith('.sav'):
            # A loose file in a save directory: the file is its own container.
            return 'save-' + re.sub(r'[^A-Za-z0-9]', '_', parts[0])
    base = os.path.basename(path)
    return os.path.splitext(base)[0].lower()


def main(argv):
    out = argv[0] if argv else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)
    g = kres.Game()
    counts = {}
    written = 0
    seen = set()
    for ext in ('tpc', 'tga', 'txi'):
        for e in g.every_entry(ext):
            name = f'{stem_of(g, e)}__{e.resref}.{ext}'
            if name in seen:
                print(f'texdump: two resources would be {name}', file=sys.stderr)
                return 1
            seen.add(name)
            counts[ext] = counts.get(ext, 0) + 1
            path = os.path.join(out, name)
            if os.path.isfile(path) and os.path.getsize(path) == e.size:
                continue
            data = kres.read_entry(e)
            with open(path, 'wb') as f:
                f.write(data)
            written += 1
    print(f'texdump: {counts.get("tpc", 0)} tpc, {counts.get("tga", 0)} tga, {counts.get("txi", 0)} txi '
          f'in {out} ({written} written)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
