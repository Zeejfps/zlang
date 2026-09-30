"""Differential test of the C backend over the corpus (tools/corpus.py).

    python tools/ctest.py [CORPUS] [-j N] [-k SUBSTRING] [--same-c | --ctxc EXE]

Runs every program in the corpus that compiles through ctxc's C backend (ctxi/cbackend.py),
with its recorded arguments and input, and compares standard output, the exit code and any
panic's message with what ctxi did. Expected divergences are listed in DIVERGENCES and reported
separately.

With --same-c it instead checks the bootstrap: for every program, and for ctxc itself, the
native ctxc must write the same C, byte for byte, as ctxc running under ctxi.

With --ctxc EXE, ctxi takes no part: EXE compiles each program from source with `ctxc build`,
its own front end and backend, and the programs that don't compile are tested too. The first
error ctxc reports must be the one ctxi stopped at, with the same position. tools/fixpoint.py
leaves the ctxc it builds from ctxc's own source in build/fixpoint.
"""

import argparse
import functools
import glob
import hashlib
import io
import json
import multiprocessing
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Panics ctxi reports that the C backend doesn't, or reports differently (the plan's list).
DIVERGENCES = (
    'invalid memory access',          # a bad pointer is undefined behaviour in C
    'stack overflow',                 # frames differ in size, so the depth differs
)


def load_case(d):
    with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
        meta = json.load(f)
    sources = []
    for file, local in meta['files']:
        with open(os.path.join(d, local), encoding='utf-8', newline='') as f:
            sources.append((f.read(), file))
    return meta, sources


def ctxc_build(ctxc, d, meta):
    """Compiles a case with `ctxc build`. Returns (executable, None), or (None, the first line
    ctxc wrote to stderr) if the program has errors."""
    from ctxi import cbackend
    std = sorted(glob.glob(os.path.join(ROOT, 'std', '*.ctx')))
    paths = [os.path.join(d, local) for _, local in meta['files']]
    os.makedirs(cbackend.CACHE, exist_ok=True)
    tmp_c = os.path.join(cbackend.CACHE, f'ctxc-{os.path.basename(d)}-{os.getpid()}.c')
    r = subprocess.run([ctxc, 'build', tmp_c, *std, '--', *paths], capture_output=True,
                       env=dict(os.environ, CTX_STACK=str(200 << 20)))
    if r.returncode == 1 and not os.path.exists(tmp_c):
        return None, r.stderr.decode('utf-8', 'replace').splitlines()[0]
    if r.returncode != 0:
        raise RuntimeError(f'ctxc build exited with {r.returncode}: {r.stderr.decode(errors="replace")[:400]}')
    with open(tmp_c, 'rb') as f:
        key = hashlib.sha256(cbackend.tree_hash().encode() + b'\0' + f.read()).hexdigest()[:24]
    exe = os.path.join(cbackend.CACHE, 'ctxc-' + key + cbackend.EXE)
    if os.path.exists(exe):
        os.remove(tmp_c)
    else:
        cbackend.link(tmp_c, os.path.join(cbackend.CACHE, 'ctxc-' + key + '.c'), exe, 'program')
    return exe, None


def check(d, ctxc=None):
    """(name, status, detail): status is ok, diverges or fail."""
    from ctxi.__main__ import load_sources
    from ctxi import cbackend
    from ctxi.runtime import Panic
    name = os.path.basename(d)
    meta, sources = load_case(d)
    gone = [a for a in meta['args'] if os.sep in a and not os.path.isdir(os.path.dirname(a))]
    if gone:
        return name, 'skipped', f'needs {gone[0]}, which the test suite deleted'
    want = meta['outcome']
    out, err = io.BytesIO(), io.BytesIO()
    got = {'kind': 'exit'}
    try:
        if ctxc is None:
            exe = cbackend.build(load_sources(sources))
        else:
            exe, error = ctxc_build(ctxc, d, meta)
            if want['kind'] == 'error' or error is not None:
                return (name, *compile_error(d, meta, error))
        got['code'] = cbackend.run_exe(exe, out=out, err=err,
                                       inp=io.BytesIO(bytes.fromhex(meta['stdin'])), args=meta['args'],
                                       timeout=60)
    except Panic as e:
        got = {'kind': 'panic', 'msg': e.msg}
    except Exception as e:
        return name, 'fail', f'{type(e).__name__}: {e}'
    stdout = out.getvalue().hex()
    problems = []
    if got['kind'] != want['kind']:
        problems.append(f"{want['kind']} {want.get('msg', want.get('code'))!r} became "
                        f"{got['kind']} {got.get('msg', got.get('code'))!r}")
    elif got['kind'] == 'exit' and got['code'] != want['code']:
        problems.append(f"exit code {want['code']} became {got['code']}")
    elif got['kind'] == 'panic' and got['msg'] != want['msg']:
        problems.append(f"panic {want['msg']!r} became {got['msg']!r}")
    if stdout != want['stdout']:
        a, b = bytes.fromhex(want['stdout']), bytes.fromhex(stdout)
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        problems.append(f'stdout differs at byte {i}: {a[max(0, i - 20):i + 20]!r} vs {b[max(0, i - 20):i + 20]!r}')
    if not problems:
        return name, 'ok', ''
    if want['kind'] == 'panic' and any(m in want['msg'] for m in DIVERGENCES):
        return name, 'diverges', problems[0]
    return name, 'fail', '; '.join(problems)


def compile_error(d, meta, error):
    """(status, detail) for a program ctxi rejected: ctxc's first error must be ctxi's."""
    want = meta['outcome']
    if want['kind'] != 'error':
        return 'fail', f'ctxc rejected it: {error}'
    if error is None:
        return 'fail', f"ctxc compiled it, but ctxi reported {want['msg']!r}"
    where = ''
    if want.get('pos'):
        line, col, file = want['pos']
        local = next((loc for f, loc in meta['files'] if f == file), meta['files'][0][1])
        where = f'{os.path.join(d, local)}:{line}:{col}'
    expect = f"{where}: error: {want['msg'].split(chr(10))[0]}"
    if error == expect or (not where and error.endswith(expect)):
        return 'ok', ''
    return 'fail', f'expected {expect!r}, got {error!r}'


def same_c(d):
    """(name, status, detail): whether native and interpreted ctxc write the same C."""
    from ctxi.__main__ import load_sources, read_program
    from ctxi import cbackend
    from ctxi.irdump import verify
    if d == 'ctxc':
        name, checker = d, load_sources(read_program(cbackend.CTXC))
    else:
        name, checker = os.path.basename(d), load_sources(load_case(d)[1])
    try:
        text = verify(checker)
        outs = []
        for native in (False, True):
            c = os.path.join(cbackend.NATIVE, f'same-{name}-{os.getpid()}-{native:d}.c')
            cbackend.emit_c(text, c, native=native)
            with open(c, 'rb') as f:
                outs.append(f.read())
            os.remove(c)
    except Exception as e:
        return name, 'fail', f'{type(e).__name__}: {e}'
    if outs[0] == outs[1]:
        return name, 'ok', ''
    a, b = outs
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return name, 'fail', f'C differs at byte {i}: {a[max(0, i - 20):i + 20]!r} vs {b[max(0, i - 20):i + 20]!r}'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('corpus', nargs='?', default=os.path.join(ROOT, 'build', 'corpus'))
    ap.add_argument('-j', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('-k', default='')
    ap.add_argument('--same-c', action='store_true')
    ap.add_argument('--ctxc', help='compile with this ctxc, from source')
    a = ap.parse_args(argv)
    dirs = []
    for name in sorted(os.listdir(a.corpus)):
        d = os.path.join(a.corpus, name)
        meta, _ = load_case(d)
        if (meta['outcome']['kind'] != 'error' or a.ctxc) and a.k in name:
            dirs.append(d)
    if a.same_c and a.k in 'ctxc':
        dirs.insert(0, 'ctxc')
    from ctxi import cbackend
    start = time.time()
    cbackend.native_ctxc()            # once, before the workers all look for it
    print(f'native ctxc: {cbackend.native_ctxc()} ({time.time() - start:.0f}s)', flush=True)
    results = []
    with multiprocessing.Pool(a.j) as pool:
        job = same_c if a.same_c else functools.partial(check, ctxc=a.ctxc and os.path.abspath(a.ctxc))
        for r in pool.imap_unordered(job, dirs):
            results.append(r)
            if r[1] != 'ok':
                print(f'{r[0]}: {r[1]}: {r[2]}', flush=True)
    counts = {}
    for _, status, _ in results:
        counts[status] = counts.get(status, 0) + 1
    print(f"{len(results)} programs in {time.time() - start:.0f}s: "
          + ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))
    return 1 if counts.get('fail') else 0


if __name__ == '__main__':
    import threading
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(250 << 20)
    code = [1]
    t = threading.Thread(target=lambda: code.__setitem__(0, main(sys.argv[1:])))
    t.start()
    t.join()
    sys.exit(code[0])
