"""The self-hosting fixpoint, and the bootstrap's refresh.

    python tools/fixpoint.py [--update] [--keep]

ctxc1 is the native ctxc for the current source (tools/toolchain.py: bootstrap/ctxc.c compiles
it). Then, with `ctxc build`:

    ctxc1 build -> ctxc2.c -> cc -> ctxc2
    ctxc2 build -> ctxc3.c -> cc -> ctxc3

ctxc2.c and ctxc3.c must be byte-identical. If bootstrap/ctxc.c differs from them, it is out of
date, and --update replaces it with ctxc3.c. Refresh it before a change to ctxc's source needs a
feature the bootstrap's ctxc doesn't have, and whenever a change lands: the bootstrap is what
builds ctxc from a fresh checkout. Everything goes in build/fixpoint; --keep leaves the C there.
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import toolchain  # noqa: E402

OUT = os.path.join(ROOT, 'build', 'fixpoint')


def build(ctxc, c):
    """Runs `ctxc build` on ctxc's source. Returns the seconds it took."""
    start = time.perf_counter()
    code, err = toolchain.ctxc_build(ctxc, c, toolchain.ctxc_files())
    took = time.perf_counter() - start
    if code != 0:
        sys.exit(f'{os.path.basename(ctxc)} build failed ({code}):\n{err[:2000]}')
    return took


def cc(c, exe):
    """Compiles c with the runtime, as the toolchain links ctxc. Returns the seconds it took."""
    start = time.perf_counter()
    comp, env = toolchain.compiler()
    cmd = comp + toolchain.CFLAGS + ['-I', toolchain.RT, '-DCTX_PROGRAM_NAME="ctxc"', c,
                                     toolchain.runtime_object(comp, env), '-o', exe, '-lm']
    r = subprocess.run(cmd + toolchain.stack_flags(), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f'C compiler failed on {c}:\n{r.stderr[:2000]}')
    return time.perf_counter() - start


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def first_difference(a, b):
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f'first difference at byte {i}, line {a.count(b"\n", 0, i) + 1}'


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    path = lambda name: os.path.join(OUT, name)
    start = time.perf_counter()
    ctxc1 = toolchain.native_ctxc()
    print(f'ctxc1: {os.path.relpath(ctxc1, ROOT)} ({time.perf_counter() - start:.1f} s)')
    exe = toolchain.EXE
    t2 = build(ctxc1, path('ctxc2.c'))
    c2 = cc(path('ctxc2.c'), path('ctxc2' + exe))
    print(f'ctxc2: ctxc1 build {t2 * 1000:.0f} ms, cc {c2:.1f} s')
    t3 = build(path('ctxc2' + exe), path('ctxc3.c'))
    c3 = cc(path('ctxc3.c'), path('ctxc3' + exe))
    print(f'ctxc3: ctxc2 build {t3 * 1000:.0f} ms, cc {c3:.1f} s')

    two, three, boot = read(path('ctxc2.c')), read(path('ctxc3.c')), read(toolchain.BOOT)
    ok = two == three
    print(f'ctxc2.c == ctxc3.c: ' + (f'yes ({len(two):,} bytes)' if ok else f'NO, {first_difference(two, three)}'))
    if ok and boot == three:
        print('bootstrap/ctxc.c: up to date')
    elif ok and '--update' in argv:
        shutil.copyfile(path('ctxc3.c'), toolchain.BOOT)
        print('bootstrap/ctxc.c: updated')
    elif ok:
        print(f'bootstrap/ctxc.c: out of date ({first_difference(boot, three)}); --update refreshes it')
    if '--keep' not in argv:
        for name in ('ctxc2.c', 'ctxc3.c'):
            os.remove(path(name))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
