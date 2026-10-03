"""Extract every MDL/MDX pair and every walkmesh of the install into kotor/extract/, for the
ctxlang corpus tools (mdlcheck, animcheck) until they read the install through lib/res.

    python kotor/tools/py/extract_models.py [--out DIR]

Writes, under DIR (default kotor/extract/models):

    <container>/<resref>.mdl, <container>/<resref>.mdx    every MDL entry with its MDX, paired as
                                                         kmdl.corpus pairs them (an empty .mdx
                                                         when there is none)
    walk/<container>/<resref>.wok|pwk|dwk                 every walkmesh copy (Game.every_entry)
    models.txt     one line per model:    <container>\t<resref>
    walk.txt       one line per walkmesh: <container>\t<resref>\t<ext>

<container> is the container's file name (models.bif, global.rim, patch.erf, ...). Resrefs are
lower case. Nothing here is game code: the game reads the install directly.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kres  # noqa: E402
import kmdl  # noqa: E402


def main(argv):
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', '..', 'extract', 'models')
    out = os.path.normpath(out)
    os.makedirs(out, exist_ok=True)
    g = kres.Game()
    lines = []
    for e, mdl, mdx in kmdl.corpus(g):
        cont = os.path.basename(e.container).lower()
        d = os.path.join(out, cont)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, e.resref + '.mdl'), 'wb') as f:
            f.write(mdl)
        with open(os.path.join(d, e.resref + '.mdx'), 'wb') as f:
            f.write(mdx)
        lines.append(f'{cont}\t{e.resref}\n')
    with open(os.path.join(out, 'models.txt'), 'w', newline='\n') as f:
        f.writelines(lines)
    print(f'{len(lines)} models')
    wl = []
    for ext in ('wok', 'pwk', 'dwk'):
        for e in g.every_entry(ext):
            cont = os.path.basename(e.container).lower()
            d = os.path.join(out, 'walk', cont)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f'{e.resref}.{ext}'), 'wb') as f:
                f.write(kres.read_entry(e))
            wl.append(f'{cont}\t{e.resref}\t{ext}\n')
    with open(os.path.join(out, 'walk.txt'), 'w', newline='\n') as f:
        f.writelines(wl)
    print(f'{len(wl)} walkmeshes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
