"""Compiles a ctxlang program to a native executable, and runs it.

    python tools/ctxc.py PROGRAM [-o EXE] [--c FILE.c] [--run [args...]]

PROGRAM is a .ctx file or a directory of them. A directory with a build.ctx is built as its build
program says (spec §19): -o, --c and --run then apply to the first executable it names. A native ctxc (tools/toolchain.py builds it from
this platform's bootstrap on first use) checks the program and writes C with `ctxc build`, and gcc or
clang (or zig cc, with CTX_CC=zig) builds it with ctxc/rt/ctxrt.c. Builds are cached in
build/cbackend. Errors are printed as `PATH:LINE:COL: error: MESSAGE`.

Without Python, ctxc does the same itself (ctxc/drive.ctx), with the bootstrap's compiler:

    ctxc run PROGRAM [-- args...]
    ctxc exe PROGRAM -o EXE

This script stays for development: it uses the current source's ctxc and caches builds.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import toolchain  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog='ctxc', description='compile a ctxlang program to native code')
    ap.add_argument('program')
    ap.add_argument('-o', dest='out', help='where to put the executable')
    ap.add_argument('--c', dest='c', help='also copy the generated C here')
    ap.add_argument('--run', nargs=argparse.REMAINDER, help='run it, with these arguments')
    a = ap.parse_args(argv)
    try:
        if os.path.isfile(os.path.join(a.program, 'build.ctx')):
            built = toolchain.build_project(a.program)
            if not built:
                print(f'{a.program}: error: build.ctx names no executable', file=sys.stderr)
                return 1
        else:
            if os.path.isdir(a.program):
                files = sorted(glob.glob(os.path.join(a.program, '*.ctx')))
                if not files:
                    print(f'{a.program}: error: no .ctx files in directory', file=sys.stderr)
                    return 1
            else:
                files = [a.program]
            built = [(a.program, toolchain.build_files(files, cwd=os.getcwd(), name=a.program))]
    except toolchain.CompileError as e:
        sys.stderr.write(e.text or f'{a.program}: error: {e.msg}\n')
        return 1
    except (toolchain.Panic, RuntimeError) as e:
        print(f'{a.program}: error: {e}', file=sys.stderr)
        return 1
    exe = built[0][1]
    if a.c:
        shutil.copyfile(os.path.splitext(exe)[0] + '.c', a.c)
    if a.out:
        shutil.copy(exe, a.out)
        exe = a.out
    if a.run is not None:
        return subprocess.run([exe, *a.run]).returncode
    if not a.out:
        for _, path in built:
            print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
