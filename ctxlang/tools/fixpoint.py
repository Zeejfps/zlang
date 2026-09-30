"""The self-hosting fixpoint (stage 7).

    python tools/fixpoint.py [--keep]

ctxc1 is the native ctxc that ctxi/cbackend.py bootstraps from ctxi's front end. Each stage then
compiles ctxc's source with `ctxc build`, ctxc's own front end and backend in one process:

    ctxc1 build -> ctxc2.c -> cc -> ctxc2
    ctxc2 build -> ctxc3.c -> cc -> ctxc3

ctxc2.c and ctxc3.c must be byte-identical, and so must ctxc2.c and the C that ctxc1's backend
writes from ctxi's IR (`python -m ctxi ctxc --ir`), since both front ends lower ctxc to the same
IR. Files are named as ctxi names them, so the C's file tables agree. Everything goes in
build/fixpoint; --keep leaves it there, else only the executables are kept.
"""

import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi import cbackend  # noqa: E402

OUT = os.path.join(ROOT, 'build', 'fixpoint')
STD = sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(ROOT, 'std', '*.ctx')))
SRC = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, 'ctxc', '*.ctx')))
ENV = dict(os.environ, CTX_STACK=str(200 << 20))


def build(ctxc, c):
    """Runs `ctxc build` on ctxc's source. Returns the seconds it took."""
    start = time.perf_counter()
    r = subprocess.run([ctxc, 'build', c, *STD, '--', *SRC], cwd=ROOT, capture_output=True, env=ENV)
    took = time.perf_counter() - start
    if r.returncode != 0:
        sys.exit(f'{os.path.basename(ctxc)} build failed ({r.returncode}):\n'
                 + (r.stdout + r.stderr).decode(errors='replace')[:2000])
    return took


def cc(c, exe):
    """Compiles c with the runtime, as cbackend links ctxc. Returns the seconds it took."""
    start = time.perf_counter()
    comp, env = cbackend.compiler()
    cmd = comp + cbackend.CFLAGS + ['-I', cbackend.RT, '-DCTX_PROGRAM_NAME="ctxc"', c,
                                    cbackend.runtime_object(comp, env), '-o', exe, '-lm']
    r = subprocess.run(cmd + cbackend.stack_flags(), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f'C compiler failed on {c}:\n{r.stderr[:2000]}')
    return time.perf_counter() - start


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def first_difference(a, b):
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    line = a.count(b'\n', 0, i) + 1
    return f'first difference at byte {i}, line {line}'


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    path = lambda name: os.path.join(OUT, name)
    ctxc1 = cbackend.native_ctxc()
    print(f'ctxc1: {os.path.relpath(ctxc1, ROOT)} (bootstrapped by ctxi)')

    # The reference: ctxc1's backend on ctxi's IR.
    ir = subprocess.run([sys.executable, '-m', 'ctxi', 'ctxc', '--ir'], cwd=ROOT, capture_output=True,
                        check=True).stdout
    with open(path('ctxi.ir'), 'wb') as f:
        f.write(ir)
    r = subprocess.run([ctxc1, 'c', path('ctxi.ir'), path('ctxc1.c')], capture_output=True, env=ENV)
    if r.returncode != 0:
        sys.exit(f'ctxc1 c failed: {r.stderr.decode(errors="replace")}')

    exe = cbackend.EXE
    t2 = build(ctxc1, path('ctxc2.c'))
    c2 = cc(path('ctxc2.c'), path('ctxc2' + exe))
    print(f'ctxc2: ctxc1 build {t2 * 1000:.0f} ms, cc {c2:.1f} s')
    t3 = build(path('ctxc2' + exe), path('ctxc3.c'))
    c3 = cc(path('ctxc3.c'), path('ctxc3' + exe))
    print(f'ctxc3: ctxc2 build {t3 * 1000:.0f} ms, cc {c3:.1f} s')

    ok = True
    ref, two, three = read(path('ctxc1.c')), read(path('ctxc2.c')), read(path('ctxc3.c'))
    for label, a, b in (('ctxc2.c == ctxc3.c', two, three), ('ctxc1.c == ctxc2.c', ref, two)):
        if a == b:
            print(f'{label}: yes ({len(a):,} bytes)')
        else:
            ok = False
            print(f'{label}: NO, {first_difference(a, b)}')
    if '--keep' not in argv:
        for name in ('ctxi.ir', 'ctxc1.c', 'ctxc2.c', 'ctxc3.c'):
            os.remove(path(name))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
