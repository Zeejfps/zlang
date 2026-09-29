"""ctxi: interpreter for ctxlang.

    python -m ctxi program.ctx [--check] [--stack BYTES]
"""

import argparse
import sys
import threading

from .lexer import CompileError
from .parser import parse
from .checker import check, NativeFn
from .runtime import Runtime, Trap
from .types import PRIMS, VOID, Cap

IO = Cap('Io')


def _printer(ty, fmt=str):
    def impl(rt, args):
        rt.out.write(fmt(args['n']) + '\n')
    return NativeFn('print_' + ty, [('io', True, IO), ('n', False, PRIMS[ty])], VOID, impl)


def _fmt_f32(v):
    return f'{v:.9g}'


def natives():
    out = [_printer(ty) for ty in ('i8', 'i16', 'i32', 'i64', 'u8', 'u16', 'u32', 'u64', 'usize', 'f64')]
    out.append(_printer('f32', _fmt_f32))
    out.append(_printer('bool', lambda v: 'true' if v else 'false'))

    def put_byte(rt, args):
        rt.out.write(chr(args['b']))
    out.append(NativeFn('put_byte', [('io', True, IO), ('b', False, PRIMS['u8'])], VOID, put_byte))
    return out


def load(src):
    """Parse and check a program. Raises CompileError."""
    return check(parse(src), natives())


def run_source(src, out=None, stack_size=16 << 20):
    c = load(src)
    rt = Runtime(c, stack_size=stack_size, out=out)
    main = c.main
    cap = rt.sp
    rt.sp += 16
    args = {name: (cap if mut else b'') for name, mut, _ in main.sig_fields}
    rt.get_callable(main, []).call(args)


def fmt_pos(path, pos):
    if pos is None:
        return path
    return f'{path}:{pos[0]}:{pos[1]}'


def main(argv=None):
    ap = argparse.ArgumentParser(prog='ctxi', description='ctxlang interpreter')
    ap.add_argument('file')
    ap.add_argument('--check', action='store_true', help='only parse and type-check')
    ap.add_argument('--stack', type=int, default=16 << 20, help='stack size in bytes')
    a = ap.parse_args(argv)
    with open(a.file, encoding='utf-8') as f:
        src = f.read()

    result = [0]

    def go():
        try:
            if a.check:
                load(src)
            else:
                run_source(src, stack_size=a.stack)
        except CompileError as e:
            sys.stdout.flush()
            print(f'{fmt_pos(a.file, e.pos)}: error: {e.msg}', file=sys.stderr)
            result[0] = 1
        except Trap as e:
            sys.stdout.flush()
            print(f'{fmt_pos(a.file, e.pos)}: trap: {e.msg}', file=sys.stderr)
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
