"""Compiles a ctxlang program to a native executable through ctxc's C backend.

    python tools/ctxc.py PROGRAM [-o EXE] [--c FILE.c] [--run [args...]]

PROGRAM is a .ctx file or a directory, as for ctxi. The pipeline: a native ctxc (bootstrapped
into build/ctxc on first use) checks the program and writes C with `ctxc build`, and gcc (or zig
cc, with CTX_CC=zig) builds it with ctxc/rt/ctxrt.c. Builds are cached in build/cbackend.
"""

import argparse
import glob
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi import cbackend  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog='ctxc', description='compile a ctxlang program to native code')
    ap.add_argument('program')
    ap.add_argument('-o', dest='out', help='where to put the executable')
    ap.add_argument('--c', dest='c', help='also copy the generated C here')
    ap.add_argument('--run', nargs=argparse.REMAINDER, help='run it, with these arguments')
    a = ap.parse_args(argv)
    exe = build(a.program)
    if exe is None:
        return 1
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


def build(program):
    """The path of an executable for program, or None if ctxc reported errors."""
    if os.path.isdir(program):
        files = sorted(glob.glob(os.path.join(program, '*.ctx')))
        if not files:
            print(f'{program}: error: no .ctx files in directory', file=sys.stderr)
            return None
    else:
        files = [program]
    std = sorted(glob.glob(os.path.join(ROOT, 'std', '*.ctx')))
    os.makedirs(cbackend.CACHE, exist_ok=True)
    tmp_c = os.path.join(cbackend.CACHE, f'build-{os.getpid()}.c')
    r = subprocess.run([cbackend.native_ctxc(), 'build', tmp_c, *std, '--', *files],
                       env=dict(os.environ, CTX_STACK=str(200 << 20)))
    if r.returncode != 0:
        return None
    with open(tmp_c, 'rb') as f:
        text = f.read()
    key = hashlib.sha256(cbackend.tree_hash().encode() + b'\0' + program.encode() + b'\0' + text).hexdigest()[:24]
    exe = os.path.join(cbackend.CACHE, key + cbackend.EXE)
    if os.path.exists(exe):
        os.remove(tmp_c)
    else:
        cbackend.link(tmp_c, os.path.join(cbackend.CACHE, key + '.c'), exe, program)
    return exe


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
