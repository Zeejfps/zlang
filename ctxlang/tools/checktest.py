"""Differential test of ctxc's checker against ctxi's (stage 6).

    python tools/checktest.py [CORPUS] [-k SUBSTRING] [-v] [-j JOBS]

Checks every program in the corpus (tools/corpus.py) with both checkers and compares their
dumps of the checked declarations and bodies (ctxi/declsdump.py describes the format). Where
ctxi checks a program, ctxc's dump must match byte for byte and ctxc must report nothing. Where
ctxi stops at an error, ctxc's first diagnostic must have the same file, position and message.

ctxc doesn't make every check of ctxi's yet (PENDING, by PLAN.md's sub-steps of stage 6). Where
ctxi stops at one of those and ctxc's first diagnostic is a different one, the program is
skipped, since ctxi never reached what ctxc reports.

ctxc runs natively (ctxi/cbackend.py builds it), one process per program, JOBS at a time.
"""

import glob
import json
import os
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi.__main__ import std_decls  # noqa: E402
from ctxi.declsdump import dump_sources  # noqa: E402
from ctxi.natives import natives  # noqa: E402

# Fragments of ctxi's messages for the checks ctxc doesn't make yet.
PENDING = (
    # sub-step 4: definite initialization
    'may be read before it is assigned', 'may be assigned more than once', 'in a defer: declare it with',
    # sub-step 5: exclusivity, escape analysis and bound-function scope
    'mut references to', 'overlaps a place held by', 'overlaps the match scrutinee',
    'the address of local', 'outlives local', 'bound function stored in', 'the value of this branch holds',
)

STD = sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(ROOT, 'std', '*.ctx')))


def cases(corpus, k):
    """(label, [(name, path)]) for each program: the name its positions use and its file."""
    out = []
    for name in sorted(os.listdir(corpus)):
        d = os.path.join(corpus, name)
        with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
            meta = json.load(f)
        files = [(f or '', os.path.relpath(os.path.join(d, local), ROOT)) for f, local in meta['files']]
        label = f'{name} ({os.path.basename(files[0][0]) or "<string>"})'
        if k in label:
            out.append((label, files))
    return out


def first_error(text):
    for line in text.splitlines(keepends=True):
        if line.startswith('error '):
            return line
    return None


def run_ctxc(exe, files):
    """ctxc's dump, with each file's path in a diagnostic replaced by the name ctxi uses."""
    r = subprocess.run([exe, 'decls', *STD, '--', *(p for _, p in files)], cwd=ROOT, capture_output=True,
                       env=dict(os.environ, CTX_STACK=str(200 << 20)))
    if r.returncode != 0:
        return None, r.stderr.decode(errors='replace')
    text = r.stdout.decode('utf-8', 'replace')
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith('error '):
            for name, p in files:
                if line.startswith(f'error {p}:'):
                    line = f'error {name}:' + line[len(f'error {p}:'):]
                    break
        lines.append(line)
    return ''.join(lines), None


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
    # ctxi's checker writes into the tree it checks, so each program gets its own copy of std.
    std, nat = pickle.dumps(std_decls()), natives()
    start = time.time()
    with ThreadPoolExecutor(int(opts.get('-j', os.cpu_count() or 4))) as pool:
        got = list(pool.map(lambda c: run_ctxc(exe, c[1]), todo))
    checked = errors = failed = skipped = 0
    for (label, files), (have, crash) in zip(todo, got):
        if have is None:
            failed += 1
            print(f'{label}: ctxc failed: {crash.strip()}')
            continue
        srcs = []
        for name, p in files:
            with open(os.path.join(ROOT, p), encoding='utf-8') as f:
                srcs.append((f.read(), name or None))
        want = dump_sources(srcs, pickle.loads(std), nat)
        first = first_error(have)
        if want.startswith('error ') and first != want and any(p in want for p in PENDING):
            skipped += 1
            if verbose:
                print(f'{label}: skipped: {want.strip()}')
            continue
        if want.startswith('error '):
            errors += 1
            if first != want:
                failed += 1
                print(f'{label}: ctxi {want.strip()!r}, ctxc {(first_error(have) or "no error").strip()!r}')
            elif verbose:
                print(f'{label}: {want.strip()}')
        else:
            checked += 1
            if have != want:
                failed += 1
                print(f'{label}: {diff(want, have)}')
    print(f'{len(todo) - failed - skipped}/{len(todo)} programs agree ({checked} checked, {errors} errors, '
          f'{skipped} skipped) in {time.time() - start:.1f}s')
    return 1 if failed else 0


def diff(want, have):
    w, h = want.splitlines(), have.splitlines()
    for i in range(max(len(w), len(h))):
        a = w[i] if i < len(w) else '<end>'
        b = h[i] if i < len(h) else '<end>'
        if a != b:
            return f'line {i + 1}: ctxi {a!r}, ctxc {b!r}'
    return 'same lines, different bytes'


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
