"""Checks the typed IR over the corpus (tools/corpus.py).

    python tools/irtest.py [CORPUS] [--roundtrip]

Dumps the IR of every program in the corpus that compiles, into CORPUS/NNNN/program.ir. With
--roundtrip, also runs ctxc's reader and printer on each dump under ctxi (`ctxc roundtrip`) and
checks that it reproduces the dump byte for byte.
"""

import io
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi.__main__ import load_sources, read_program, run_checked  # noqa: E402
from ctxi.irdump import verify as dump  # noqa: E402


def cases(corpus):
    for name in sorted(os.listdir(corpus)):
        d = os.path.join(corpus, name)
        with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
            meta = json.load(f)
        if meta['outcome']['kind'] == 'error':
            continue
        sources = []
        for file, local in meta['files']:
            with open(os.path.join(d, local), encoding='utf-8', newline='') as f:
                sources.append((f.read(), file))
        yield name, d, sources


def main(argv):
    roundtrip = '--roundtrip' in argv
    argv = [a for a in argv if a != '--roundtrip']
    corpus = argv[0] if argv else os.path.join(ROOT, 'build', 'corpus')
    ctxc = load_sources(read_program(os.path.join(ROOT, 'ctxc'))) if roundtrip else None
    failed = total = 0
    start = time.time()
    for name, d, sources in cases(corpus):
        total += 1
        try:
            text = dump(load_sources(sources))
        except Exception:
            failed += 1
            print(f'{name}: dump failed\n{traceback.format_exc()}')
            continue
        path = os.path.join(d, 'program.ir')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        if roundtrip:
            out, err = io.BytesIO(), io.BytesIO()
            code = run_checked(ctxc, out=out, err=err, args=['roundtrip', path])
            got = out.getvalue().decode('utf-8', 'replace')
            if code != 0 or got != text:
                failed += 1
                print(f'{name}: roundtrip differs (exit {code}) {err.getvalue().decode(errors="replace")}')
                with open(os.path.join(d, 'roundtrip.ir'), 'w', encoding='utf-8', newline='') as f:
                    f.write(got)
    print(f'{total - failed}/{total} passed in {time.time() - start:.1f}s')
    return 1 if failed else 0


def in_thread(f, *a):
    """Runs f with room for deep recursion, as ctxi's own main does."""
    import threading
    result = [1]

    def go():
        result[0] = f(*a)
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(250 << 20)
    t = threading.Thread(target=go)
    t.start()
    t.join()
    return result[0]


if __name__ == '__main__':
    sys.exit(in_thread(main, sys.argv[1:]))
