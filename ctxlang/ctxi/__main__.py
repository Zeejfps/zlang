"""ctxi: interpreter for ctxlang.

    python -m ctxi program.ctx [--check] [--stack BYTES] [args...] [-- args...]
"""

import argparse
import glob
import os
import sys
import threading

from .lexer import CompileError
from .parser import parse
from .checker import check
from .natives import natives
from .runtime import Runtime, Trap
from .types import struct_fields

STD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'std')


def std_decls():
    decls = []
    for path in sorted(glob.glob(os.path.join(STD_DIR, '*.ctx'))):
        with open(path, encoding='utf-8') as f:
            decls += parse(f.read(), os.path.relpath(path, os.path.dirname(STD_DIR)).replace(os.sep, '/'))
    return decls


def load(src, file=None):
    """Parse and check a program together with std. Raises CompileError."""
    return check(parse(src, file), std_decls(), natives())


def run_source(src, file=None, out=None, err=None, inp=None, stack_size=16 << 20, args=()):
    """Runs a program. Returns its exit code: what main returns, or 0."""
    c = load(src, file)
    rt = Runtime(c, stack_size=stack_size, out=out, err=err, inp=inp)
    main = c.main
    cap = rt.push_bytes(bytes(16), 16)
    fields = {}
    for name, mut, t in main.sig_fields:
        if mut:
            fields[name] = cap
        elif name == 'args':
            fields[name] = main_args(rt, t, args)
        else:
            fields[name] = b''
    try:
        code = rt.get_callable(main, []).call(fields)
    finally:
        rt.flush()
        rt.close_files()
    return code or 0


def main_args(rt, t, args):
    """Places the command-line arguments in memory and returns main's `args` slice."""
    elem = struct_fields(t)[0][1].elem.elem          # Slice(u8), from Slice(Slice(u8)).ptr: ?*T
    size = rt.layout(elem).size
    views = []
    for a in args:
        data = os.fsencode(a)
        views.append(rt.make_slice(elem, rt.push_bytes(data) if data else 0, len(data)))
    base = rt.push_bytes(b''.join(views), 8) if views else 0
    assert all(len(v) == size for v in views)
    return rt.make_slice(t, base, len(views))


def fmt_pos(path, pos):
    if pos is None:
        return path
    if len(pos) > 2 and pos[2]:
        path = pos[2]
    return f'{path}:{pos[0]}:{pos[1]}'


def main(argv=None):
    ap = argparse.ArgumentParser(prog='ctxi', description='ctxlang interpreter')
    ap.add_argument('file')
    ap.add_argument('--check', action='store_true', help='only parse and type-check')
    ap.add_argument('--stack', type=int, default=16 << 20, help='stack size in bytes')
    ap.add_argument('args', nargs='*', help="the program's arguments, in main's `args`; "
                                            "put any that start with '-' after --")
    argv = sys.argv[1:] if argv is None else list(argv)
    rest = []
    if '--' in argv:
        i = argv.index('--')
        argv, rest = argv[:i], argv[i + 1:]
    a = ap.parse_args(argv)
    a.args += rest
    with open(a.file, encoding='utf-8') as f:
        src = f.read()

    result = [0]

    def go():
        try:
            if a.check:
                load(src, a.file)
            else:
                result[0] = run_source(src, a.file, stack_size=a.stack, args=a.args)
        except CompileError as e:
            sys.stdout.flush()
            print(f'{fmt_pos(a.file, e.pos)}: error: {e.msg}', file=sys.stderr)
            result[0] = 1
        except Trap as e:
            sys.stdout.flush()
            print(f'{fmt_pos(a.file, e.pos)}: trap: {e.msg}', file=sys.stderr)
            for name in e.frames:
                print(f'    in {name}', file=sys.stderr)
            result[0] = 134
        except RecursionError:
            sys.stdout.flush()
            print(f'{a.file}: trap: stack overflow', file=sys.stderr)
            result[0] = 134

    sys.setrecursionlimit(1_000_000)
    threading.stack_size(250 << 20)
    t = threading.Thread(target=go)
    t.start()
    t.join()
    sys.stdout.flush()
    return result[0]


if __name__ == '__main__':
    sys.exit(main())
