"""The self-hosting fixpoint, and the bootstraps' refresh.

    python tools/fixpoint.py [--update] [--keep]

ctxc1 is the native ctxc for the current source (tools/toolchain.py: this platform's bootstrap
compiles it). Then, with `ctxc build` and this platform's std layer (std/os/PLATFORM):

    ctxc1 build -> ctxc2.c -> cc -> ctxc2
    ctxc2 build -> ctxc3.c -> cc -> ctxc3

ctxc2.c and ctxc3.c must be byte-identical. There is a bootstrap per layer,
bootstrap/ctxc.PLATFORM.c: this platform's is ctxc3.c, and each other's is what ctxc2 builds with
that layer's files (ctxc.PLATFORM.c here), since writing C needs no C compiler. A bootstrap that
differs is out of date, and --update replaces it. Refresh them before a change to ctxc's source
needs a feature the bootstraps' ctxc doesn't have, and whenever a change lands: a bootstrap is
what builds ctxc from a fresh checkout. Everything goes in build/fixpoint; --keep leaves the C
there.
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


def build(ctxc, c, platform=toolchain.HOST):
    """Runs `ctxc build` on ctxc's source, with platform's std layer. Returns the seconds it took."""
    start = time.perf_counter()
    code, err = toolchain.ctxc_build(ctxc, c, toolchain.ctxc_files(), platform=platform)
    took = time.perf_counter() - start
    if code != 0:
        sys.exit(f'{os.path.basename(ctxc)} build failed ({code}):\n{err[:2000]}')
    return took


def cc(c, exe):
    """Compiles c with the runtime, as the toolchain links ctxc. Returns the seconds it took."""
    start = time.perf_counter()
    comp, env = toolchain.compiler()
    cmd = comp + toolchain.CFLAGS + ['-I', toolchain.RT, '-DCTX_PROGRAM_NAME="ctxc"', c,
                                     *toolchain.runtime_objects(comp, env, c), '-o', exe, '-lm']
    r = subprocess.run(cmd + toolchain.stack_flags(), capture_output=True, text=True, env=env)
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

    two, three = read(path('ctxc2.c')), read(path('ctxc3.c'))
    ok = two == three
    print(f'ctxc2.c == ctxc3.c: ' + (f'yes ({len(two):,} bytes)' if ok else f'NO, {first_difference(two, three)}'))
    made = ['ctxc2.c', 'ctxc3.c']
    for platform in toolchain.PLATFORMS if ok else ():
        c = path('ctxc3.c')
        if platform != toolchain.HOST:
            c = path(f'ctxc.{platform}.c')
            build(path('ctxc2' + exe), c, platform)
            made.append(os.path.basename(c))
        new, name = read(c), f'bootstrap/ctxc.{platform}.c'
        boot = os.path.join(ROOT, name)
        old = read(boot) if os.path.exists(boot) else b''
        if old == new:
            print(f'{name}: up to date')
        elif '--update' in argv:
            shutil.copyfile(c, boot)
            print(f'{name}: updated')
        else:
            print(f'{name}: out of date ({first_difference(old, new)}); --update refreshes it')
    if '--keep' not in argv:
        for name in made:
            os.remove(path(name))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
