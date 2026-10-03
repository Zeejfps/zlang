"""Every NCS file of a directory through ncsdis.py into one text file, to compare with the ctxlang
disassembler's corpus mode (kotor/tools/ncsdis), which writes the same format.

    python kotor/tools/py/ncsdis_corpus.py [DIR] [-o OUT]
        DIR: kotor/extract/ncs (from ncsextract.py); OUT: kotor/out/ncsdis-py.txt

    kotor/tools/ctxc run kotor/tools/ncsdis -- --corpus kotor/extract/ncs -o kotor/out/ncsdis-ctx.txt
    cmp kotor/out/ncsdis-py.txt kotor/out/ncsdis-ctx.txt

For each *.ncs file, in the byte order of the names' UTF-8: a line `=== NAME`, then
ncsdis.disassemble's text with routine names, or `NAME: MESSAGE` if the file doesn't decode.
UTF-8, with \\n line ends.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOTOR = os.path.dirname(os.path.dirname(HERE))
DEFAULT_DIR = os.path.join(KOTOR, 'extract', 'ncs')
DEFAULT_OUT = os.path.join(KOTOR, 'out', 'ncsdis-py.txt')

sys.path.insert(0, HERE)
import ncsdis  # noqa: E402


def main(argv):
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    out = DEFAULT_OUT
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == '-o' and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    src = rest[0] if rest else DEFAULT_DIR
    names = ncsdis.routine_names()
    if names is None:
        raise SystemExit('ncsdis_corpus: no routine names (nwscript.nss not found in the install)')
    files = sorted((n for n in os.listdir(src) if n.endswith('.ncs')), key=lambda n: n.encode('utf-8'))
    bad = flagged = 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        for n in files:
            with open(os.path.join(src, n), 'rb') as g:
                data = g.read()
            f.write(f'=== {n}\n')
            try:
                text, errs = ncsdis.disassemble(data, names)
            except ncsdis.NcsError as ex:
                f.write(f'{n}: {ex}\n')
                bad += 1
                continue
            f.write(text + '\n')
            if errs:
                flagged += 1
    print(f"ncsdis_corpus: {len(files)} files, {bad} didn't decode, {flagged} with target errors; "
          f"written to {out}")
    return 1 if bad or flagged else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
