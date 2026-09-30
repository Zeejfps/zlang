"""Differential test of ctxc's IR against ctxi's (stage 6, sub-step 6).

    python tools/irdiff.py [CORPUS] [-k SUBSTRING] [-v] [-j JOBS]

For every program in the corpus (tools/corpus.py) that compiles, lowers it with both front ends
and compares the IR text (ctxi/irdump.py describes it) byte for byte: ctxi's from
`python -m ctxi PROGRAM --ir`, ctxc's from `ctxc ir STD... -- FILE...`. A file's name in the
IR's `(files [...])` is the name its positions use, so ctxc's paths are mapped to ctxi's names
there, as checktest does for diagnostics.

ctxc runs natively (ctxi/cbackend.py builds it), one process per program, JOBS at a time.
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from checktest import STD, diff  # noqa: E402
from ctxi.__main__ import load_sources  # noqa: E402
from ctxi.irdump import quote, verify  # noqa: E402


def cases(corpus, k):
    """(label, [(name, path)]) for each program that compiles."""
    out = []
    for name in sorted(os.listdir(corpus)):
        d = os.path.join(corpus, name)
        with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
            meta = json.load(f)
        if meta['outcome']['kind'] == 'error':
            continue
        files = [(f or '', os.path.relpath(os.path.join(d, local), ROOT)) for f, local in meta['files']]
        label = f'{name} ({os.path.basename(files[0][0]) or "<string>"})'
        if k in label:
            out.append((label, files))
    return out


def run_ctxc(exe, files):
    """ctxc's IR, with each file's path in (files [...]) replaced by the name ctxi uses."""
    r = subprocess.run([exe, 'ir', *STD, '--', *(p for _, p in files)], cwd=ROOT, capture_output=True,
                       env=dict(os.environ, CTX_STACK=str(200 << 20)))
    text = r.stdout.decode('utf-8', 'replace')
    if r.returncode != 0:
        return None, (text + r.stderr.decode(errors='replace')).strip()
    head, sep, rest = text.partition('\n(files [')
    line, nl, tail = rest.partition('\n')
    for name, p in files:
        line = line.replace(quote(p.encode()), quote(name.encode()))
    return head + sep + line + nl + tail, None


def main(argv):
    sys.stdout.reconfigure(errors='backslashreplace')
    verbose = '-v' in argv
    opts = {}
    for name in ('-k', '-j'):
        if name in argv:
            i = argv.index(name)
            opts[name] = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    rest = [a for a in argv if not a.startswith('-')]
    corpus = rest[0] if rest else os.path.join(ROOT, 'build', 'corpus')
    todo = cases(corpus, opts.get('-k', ''))
    from ctxi.cbackend import native_ctxc
    exe = native_ctxc()
    start = time.time()
    with ThreadPoolExecutor(int(opts.get('-j', os.cpu_count() or 4))) as pool:
        got = list(pool.map(lambda c: run_ctxc(exe, c[1]), todo))
    failed = 0
    for (label, files), (have, problem) in zip(todo, got):
        if have is None:
            failed += 1
            print(f'{label}: ctxc failed: {problem[:400]}')
            continue
        srcs = []
        for name, p in files:
            with open(os.path.join(ROOT, p), encoding='utf-8', newline='') as f:
                srcs.append((f.read(), name or None))
        want = verify(load_sources(srcs))
        if have != want:
            failed += 1
            print(f'{label}: {diff(want, have)}')
        elif verbose:
            print(f'{label}: ok')
    print(f'{len(todo) - failed}/{len(todo)} programs agree in {time.time() - start:.1f}s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.setrecursionlimit(1_000_000)
    import threading
    threading.stack_size(250 << 20)
    result = [1]
    t = threading.Thread(target=lambda: result.__setitem__(0, main(sys.argv[1:])))
    t.start()
    t.join()
    sys.exit(result[0])
