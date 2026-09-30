"""The checked declarations of a program as text, for diffing ctxc's checker against ctxi's
(tools/checktest.py) before the checker produces IR.

    python -m ctxi PROGRAM --decls         prints it

The dump covers namespaces, the resolved types of struct fields, union payloads, aliases, consts
and signatures, enum values, layouts, const initializers, function bodies and `main`. It walks
std's files, then the program's, each in declaration order and into namespaces, then the
natives. One line per item, children indented by two spaces:

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
      value V                               its value, which the checker computed
    fn NAME(G) { FIELD: T, mut FIELD: T } [-> R]
      STMT                                  its body, one line per statement
    native NAME { ... } [-> R]
    main

NAME is qualified with its namespaces, and types are written as in messages (types.tstr). A
layout that can't be computed (infinite size) is `?`.

An expression is a line `KIND T`, with T its type once the body is checked (`none` if it has
none), and its children indented under it: `int`, `float`, `str`, `bool`, `null`, `path`,
`field NAME` (its base), `deref`, `index` (base, index), `range LO..HI` (base, then lo and hi if
given), `addr`, `array`, `repeat` (its element), `braced` (the values of its items, then those
`..` supplies), `neg`, `not`, `binary OP`, `@NAME` (its arguments; for `@fmt`, then `fmt PUSH`
for each piece, the utf8 function it pushes with or `call`), `if` (condition, `then` and `else`
blocks) and `match` (scrutinee, arms). Around a node that converts is `some T` (to ?T) or
`slice T`.

A statement is `let [mut ]NAME: T` (its initializer), `letelse VARIANT` (the value, a `bind`
per binding, then `else [VARIANT]` with its bindings and block), `assign` (place, value),
`eval`, `discard`, `if`, `while [LABEL]` (condition, `do` block), `match`, `return`,
`break [LABEL]`, `continue [LABEL]` or `defer` (its block). A match arm is `arm PATS` (the
variants, `|`-separated, or `else`), then `bind [&]NAME: T` for each binding of its first
pattern, then its block. A branch of an `if` or `match` expression ends in `value` over the
expression that gives its value, if it has one.

A const's value V is written `N:T` for an integer or float of type T, `true` or `false`,
`null`, `"BYTES"` for a [N]u8 and `view "BYTES"` for a view (bytes as in the IR's strings),
`{V, ...}` for a struct's fields, `I{V, ...}` for variant I's, `[V, ...]` for an array's elements
and `[V; N]` for N copies.

If the checker stops at an error, the dump is only the error: `error FILE:LINE:COL MSG`.
"""

from . import ast as A
from .checker import Checker
from .lexer import CompileError
from .parser import parse
from .runtime import Runtime
from .irdump import quote
from .natives import _float_text, _shortest_f32
from .types import StructT, UnionT, FnT, VOID, tstr, qualname, zonk, prune


def dump_sources(sources, std, natives):
    """The dump of a program of (source, file) pairs, given std's parsed decls and the natives."""
    try:
        decls = []
        for src, file in sources:
            decls += parse(src, file)
        c = Checker(decls, std, natives)
        c.check_decls()
        c.check_bodies()
    except CompileError as e:
        return error_line(e)
    return Dumper(c).run(std + decls)


def value_text(v):
    kind = v[0]
    if kind in ('int', 'float'):
        if kind == 'int':
            n = str(v[2])
        else:
            n = _float_text(_shortest_f32(v[2]) if prune(v[1]).name == 'f32' else repr(float(v[2])))
        return f'{n}:{tstr(v[1])}'
    if kind == 'bool':
        return 'true' if v[2] else 'false'
    if kind == 'null':
        return 'null'
    if kind == 'str':
        return quote(v[2])
    if kind == 'sbytes':
        return 'view ' + quote(v[2])
    if kind == 'struct':
        return '{' + ', '.join(value_text(x) for x in v[2]) + '}'
    if kind == 'variant':
        return f'{v[2]}{{' + ', '.join(value_text(x) for x in v[3]) + '}'
    if kind == 'array':
        return '[' + ', '.join(value_text(x) for x in v[2]) + ']'
    return f'[{value_text(v[2])}; {prune(v[1]).n}]'


def pushes(e):
    """The calls an @fmt stands for, in order: e.fmt is a chain of them joined by `and`."""
    if isinstance(e, A.Binary):
        return pushes(e.lhs) + pushes(e.rhs)
    return [e] if isinstance(e, A.Braced) else []


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
            self.line(1, 'value ' + value_text(d.value))
        elif isinstance(d, A.FnDecl):
            self.out.append(f'fn {name}{g} {self.sig(d.sig_fields, d.ret_t)}\n')
            self.stmts(d.body.stmts, 1)

    def line(self, depth, text):
        self.out.append(f"{'  ' * depth}{text}\n")

    def stmts(self, xs, depth):
        for s in xs:
            self.stmt(s, depth)

    def value_block(self, b, depth):
        """A branch of an `if` or `match` expression: its value, if it has one, is b.result."""
        res = getattr(b, 'result', None)
        if res is None:
            self.stmts(b.stmts, depth)
            return
        self.stmts(b.stmts[:-1], depth)
        self.line(depth, 'value')
        self.expr(res, depth + 1)

    def binds(self, bvars, depth):
        for v, _ in bvars:
            self.line(depth, f"bind {'&' if v.indirect else ''}{v.name}: {tstr(zonk(v.ty))}")

    def stmt(self, s, depth):
        if isinstance(s, A.Let):
            self.line(depth, f"let {'mut ' if s.mut else ''}{s.name}: {tstr(zonk(s.var.ty))}")
            if s.init is not None:
                self.expr(s.init, depth + 1)
        elif isinstance(s, A.LetElse):
            self.line(depth, f'letelse {s.variant}')
            self.expr(s.init, depth + 1)
            self.binds(s.bvars, depth + 1)
            self.line(depth + 1, 'else' + (f' {s.els_variant}' if s.els_variant is not None else ''))
            self.binds(s.els_bvars, depth + 2)
            self.stmts(s.els.stmts, depth + 2)
        elif isinstance(s, A.Assign):
            self.line(depth, 'assign')
            self.expr(s.lhs, depth + 1)
            self.expr(s.rhs, depth + 1)
        elif isinstance(s, A.ExprStmt):
            self.line(depth, 'discard' if s.discard else 'eval')
            self.expr(s.expr, depth + 1)
        elif isinstance(s, A.If):
            self.line(depth, 'if')
            self.if_parts(s, depth + 1, self.stmts_of)
        elif isinstance(s, A.While):
            self.line(depth, 'while' + (f' {s.label[0]}' if s.label is not None else ''))
            self.expr(s.cond, depth + 1)
            self.line(depth + 1, 'do')
            self.stmts(s.body.stmts, depth + 2)
        elif isinstance(s, A.Match):
            self.line(depth, 'match')
            self.match_parts(s, depth + 1, self.stmts_of)
        elif isinstance(s, A.Return):
            self.line(depth, 'return')
            if s.expr is not None:
                self.expr(s.expr, depth + 1)
        elif isinstance(s, (A.Break, A.Continue)):
            word = 'break' if isinstance(s, A.Break) else 'continue'
            self.line(depth, word + (f' {s.label}' if s.label is not None else ''))
        elif isinstance(s, A.Defer):
            self.line(depth, 'defer')
            self.stmts(s.body.stmts, depth + 1)
        else:
            self.line(depth, type(s).__name__)

    def stmts_of(self, b, depth):
        self.stmts(b.stmts, depth)

    def if_parts(self, s, depth, block):
        self.expr(s.cond, depth)
        self.line(depth, 'then')
        block(s.then, depth + 1)
        if s.els is not None:
            self.line(depth, 'else')
            block(s.els, depth + 1)

    def match_parts(self, s, depth, block):
        self.expr(s.scrut, depth)
        for arm in s.arms:
            pats = ' | '.join(p[0] for p in arm.pats) or 'else'
            self.line(depth, f'arm {pats}')
            self.binds(arm.bvars, depth + 1)
            block(arm.body, depth + 1)

    def expr(self, e, depth):
        kids = []
        ty = getattr(e, 'ty', None)
        t = tstr(zonk(ty)) if ty is not None else 'none'
        if isinstance(e, A.If):
            self.line(depth, f'if {t}')
            self.if_parts(e, depth + 1, self.value_block)
            return
        if isinstance(e, A.Match):
            self.line(depth, f'match {t}')
            self.match_parts(e, depth + 1, self.value_block)
            return
        if isinstance(e, A.Coerce):
            head, kids = 'some', [e.expr]
        elif isinstance(e, A.ToSlice):
            head, kids = 'slice', [e.expr]
        elif isinstance(e, A.Field):
            head, kids = f'field {e.name}', [e.base]
        elif isinstance(e, A.Deref):
            head, kids = 'deref', [e.base]
        elif isinstance(e, A.Index):
            head, kids = 'index', [e.base, e.index]
        elif isinstance(e, A.Range):
            lo = 'lo' if e.lo is not None else ''
            hi = 'hi' if e.hi is not None else ''
            head, kids = f'range {lo}..{hi}', [x for x in (e.base, e.lo, e.hi) if x is not None]
        elif isinstance(e, A.AddrOf):
            head, kids = 'addr', [e.expr]
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
        self.line(depth, f'{head} {t}')
        for k in kids:
            self.expr(k, depth + 1)
        if isinstance(e, A.Builtin) and e.name == 'fmt':
            for call in pushes(e.fmt):
                c = call.callee
                self.line(depth + 1, f'fmt {c.segs[-1].name}' if isinstance(c, A.Path) else 'fmt call')

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
