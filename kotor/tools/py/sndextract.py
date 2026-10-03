"""Copy every WAV resource out of the install's containers (chitin.key's BIFs, rims/, modules/,
patch.erf, ...) into kotor/extract/audio/<container>/<resref>.wav, so that tools/sndcheck can
decode them before the resource manager (lib/res) exists. Loose files (streamwaves/,
streamsounds/, streammusic/) are read where they are and not copied.

    python kotor/tools/py/sndextract.py [OUT_DIR]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    out = argv[1] if len(argv) > 1 else os.path.join(here, '..', '..', 'extract', 'audio')
    g = kres.Game()
    n = 0
    for e in g.every_entry('wav'):
        where = os.path.relpath(e.container, g.dir).replace(os.sep, '_').replace('/', '_')
        d = os.path.join(out, where)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, e.resref + '.wav'), 'wb') as f:
            f.write(kres.read_entry(e))
        n += 1
    print(f'{n} WAV resources into {os.path.normpath(out)}')


if __name__ == '__main__':
    main(sys.argv)
