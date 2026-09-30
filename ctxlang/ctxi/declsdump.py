"""The checked declarations of a program as text, for diffing ctxc's checker against ctxi's
(tools/checktest.py) before the checker produces IR.

    python -m ctxi PROGRAM --decls         prints it

The dump covers what the checker settles before it looks at any body: namespaces, the resolved
types of struct fields, union payloads, aliases, consts and signatures, enum values, layouts and
`main`. It walks std's files, then the program's, each in declaration order and into namespaces,
then the natives. One line per item, children indented by two spaces:

    namespace NAME
    struct NAME(G) [SIZE ALIGN]             size and alignment if it isn't generic
      FIELD: T [@OFFSET]
    union NAME(G) [SIZE ALIGN PAYOFF]
      VARIANT                               no payload
      VARIANT{ FIELD: T [@OFFSET], ... }
    enum NAME: BASE
      VARIANT = VALUE
    type NAME(G)                            a generic alias is resolved only where it is used
    type NAME = T
    const NAME: T
      KIND T                                its initializer, one line per expression
    fn NAME(G) { FIELD: T, mut FIELD: T } [-> R]
    native NAME { ... } [-> R]
    main

NAME is qualified with its namespaces, and types are written as in messages (types.tstr). A
layout that can't be computed (infinite size) is `?`. A const's initializer has a line per
expression, children indented under it, with its type once the body is checked: `int`,
`float`, `str`, `bool`, `null`, `path`, `array`, `repeat` (its element), `braced` (the values of
its items), `neg`, `not`, `binary OP`, `@NAME` (its arguments), and around a node that converts,
`some T` (to ?T) or `slice T`. If the checker stops at an error in these phases, the dump is
only the error: `error FILE:LINE:COL MSG`.
"""

from . import ast as A
from .checker import Checker
from .lexer import CompileError
from .parser import parse
from .runtime import Runtime
from .types import StructT, UnionT, FnT, VOID, tstr, qualname, zonk


def dump_sources(sources, std, natives):
    """The dump of a program of (source, file) pairs, given std's parsed decls and the natives."""
    try:
        decls = []
        for src, file in sources:
            decls += parse(src, file)
        c = Checker(decls, std, natives)
        c.check_decls()
        for d in c.consts:
            c.check_const(d)
        c.check_main()
    except CompileError as e:
        return error_line(e)
    return Dumper(c).run(std + decls)


def error_line(e):
    pos = e.pos or (0, 0)
    f = pos[2] if len(pos) > 2 and pos[2] else ''
    return f'error {f}:{pos[0]}:{pos[1]} {e.msg.replace(chr(10), chr(92) + "n")}\n'


class Dumper:
    def __init__(self, c):
        self.c = c
        self.rt = Runtime(c, stack_size=0)
        self.out = []

    def run(self, decls):
        for d in decls:
            self.decl(d)
        for nf in self.c.natives:
            self.out.append(f'native {qualname(nf)} {self.sig(nf.sig_fields, nf.ret_t)}\n')
        self.out.append('main\n')
        return ''.join(self.out)

    def decl(self, d):
        name = qualname(d)
        g = f"({', '.join(d.tparams)})" if getattr(d, 'tparams', None) else ''
        if isinstance(d, A.NamespaceDecl):
            self.out.append(f'namespace {name}\n')
            for x in d.decls:
                self.decl(x)
        elif isinstance(d, A.StructDecl):
            lay = self.layout(StructT(d, [])) if not d.tparams else None
            self.out.append(f'struct {name}{g}{self.size(d, lay)}\n')
            offs = dict((n, o) for n, _, o in lay.fields) if lay else {}
            for fname, ft in d.ftypes:
                self.out.append(f'  {fname}: {tstr(ft)}{self.off(offs, fname)}\n')
        elif isinstance(d, A.UnionDecl):
            lay = self.layout(UnionT(d, [])) if not d.tparams else None
            extra = f' {lay.pay_off}' if lay else ''
            self.out.append(f'union {name}{g}{self.size(d, lay)}{extra}\n')
            vlay = dict(lay.variants) if lay else {}
            for vname, fs in d.vtypes:
                if fs is None:
                    self.out.append(f'  {vname}\n')
                    continue
                offs = dict((n, o) for n, _, o in vlay.get(vname) or [])
                inner = ', '.join(f'{f}: {tstr(ft)}{self.off(offs, f)}' for f, ft in fs)
                self.out.append(f'  {vname}{{ {inner} }}\n' if inner else f'  {vname}{{}}\n')
        elif isinstance(d, A.EnumDecl):
            self.out.append(f'enum {name}: {tstr(d.base_t)}\n')
            for (vname, _, _), v in zip(d.variants, d.values):
                self.out.append(f'  {vname} = {v}\n')
        elif isinstance(d, A.TypeDecl):
            if d.tparams:
                self.out.append(f'type {name}{g}\n')
            else:
                t = self.c.decl_type(d, [], d.pos, partial=False, allow_bound=True)
                self.out.append(f'type {name} = {tstr(t)}\n')
        elif isinstance(d, A.ConstDecl):
            self.out.append(f'const {name}: {tstr(d.cty)}\n')
            self.expr(d.expr, 1)
        elif isinstance(d, A.FnDecl):
            self.out.append(f'fn {name}{g} {self.sig(d.sig_fields, d.ret_t)}\n')

    def expr(self, e, depth):
        kids = []
        if isinstance(e, A.Coerce):
            head, kids = 'some', [e.expr]
        elif isinstance(e, A.ToSlice):
            head, kids = 'slice', [e.expr]
        elif isinstance(e, A.IntLit):
            head = 'int'
        elif isinstance(e, A.FloatLit):
            head = 'float'
        elif isinstance(e, A.StrLit):
            head = 'str'
        elif isinstance(e, A.BoolLit):
            head = 'bool'
        elif isinstance(e, A.NullLit):
            head = 'null'
        elif isinstance(e, A.Path):
            head = 'path'
        elif isinstance(e, A.ArrayLit):
            head, kids = 'array', e.elems
        elif isinstance(e, A.ArrayRep):
            head, kids = 'repeat', [e.elem]
        elif isinstance(e, A.Braced):
            head, kids = 'braced', [a for _, _, a in e.args]
        elif isinstance(e, A.Unary):
            head, kids = 'neg' if e.op == '-' else 'not', [e.expr]
        elif isinstance(e, A.Binary):
            head, kids = f'binary {e.op}', [e.lhs, e.rhs]
        elif isinstance(e, A.Builtin):
            head, kids = f'@{e.name}', e.args
        else:
            head = type(e).__name__
        self.out.append(f"{'  ' * depth}{head} {tstr(zonk(e.ty))}\n")
        for k in kids:
            self.expr(k, depth + 1)

    @staticmethod
    def sig(fields, ret):
        s = tstr(FnT(fields, VOID, False))[2:]
        return s + (f' -> {tstr(ret)}' if ret is not VOID else '')

    def layout(self, t):
        try:
            return self.rt.layout(t)
        except CompileError:
            self.rt.layout_busy = set()
            return False

    @staticmethod
    def size(d, lay):
        if d.tparams:
            return ''
        if lay is False:
            return ' ?'
        return f' {lay.size} {lay.align}'

    @staticmethod
    def off(offs, name):
        return f' @{offs[name]}' if name in offs else ''
