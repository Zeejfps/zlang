"""Compiles a ctxlang program to a native executable through ctxc's C backend.

    python tools/ctxc.py PROGRAM [-o EXE] [--c FILE.c] [--run [args...]]

PROGRAM is a .ctx file or a directory, as for ctxi. The pipeline: ctxi checks the program and
dumps its IR, a native ctxc (bootstrapped into build/ctxc on first use) writes C, and gcc (or zig
cc, with CTX_CC=zig) builds it with ctxc/rt/ctxrt.c. Builds are cached in build/cbackend.
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi import cbackend  # noqa: E402
from ctxi.__main__ import fmt_pos, load_sources, read_program  # noqa: E402
from ctxi.lexer import CompileError  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog='ctxc', description='compile a ctxlang program to native code')
    ap.add_argument('program')
    ap.add_argument('-o', dest='out', help='where to put the executable')
    ap.add_argument('--c', dest='c', help='also copy the generated C here')
    ap.add_argument('--run', nargs=argparse.REMAINDER, help='run it, with these arguments')
    a = ap.parse_args(argv)
    try:
        checker = load_sources(read_program(a.program))
    except CompileError as e:
        print(f'{fmt_pos(a.program, e.pos)}: error: {e.msg}', file=sys.stderr)
        return 1
    exe = cbackend.build(checker, name=a.program)
    if a.c:
        shutil.copyfile(os.path.splitext(exe)[0] + '.c', a.c)
    if a.out:
        shutil.copy(exe, a.out)
        exe = a.out
    if a.run is not None:
        return subprocess.run([exe, *a.run]).returncode
    if not a.out:
        print(exe)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
