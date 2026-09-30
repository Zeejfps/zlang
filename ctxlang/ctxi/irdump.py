"""Typed IR for ctxc: the checked program, monomorphized, in a canonical text form.

    python -m ctxi PROGRAM --ir            prints it

The IR is the contract between a front end (this module, later ctxc's own checker) and ctxc's
backend. Everything the checker left implicit is explicit here: widening, T to ?T, function
value conversions, narrowed locals, `..` forwarding, `mut` fields as pointers, generic
instances, layouts and constant values. ctxc/ir.ctx reads it back and ctxc/ir_print.ctx prints
it; the two printers must agree byte for byte.

Text
----
Atoms: decimal integers (negative only in `int`); symbols ([a-z_][a-z0-9_]*); strings in double quotes, where
bytes 0x20..0x7e other than `"` and `\\` stand for themselves and every other byte is \\xHH
(lowercase hex); floats as the shortest text that reads back as the value (f64: Python's repr,
f32: the shortest f32 digits), always with a `.` or `e`. `_` marks an absent optional element.

(tag x y ...) is a node, [x y ...] a list, (x y ...) with no tag a tuple. Separators are single
spaces. A block is `{`, then each statement on its own line indented two spaces deeper than the
enclosing line, then for a value block `=> EXPR` on its own line, then `}` on its own line at
the enclosing indent. An empty block is `{}`. Top-level items are one per line:

    ctxir 4
    (files [STR...])                     file names, in the order positions first use them; ""
                                         is a program read from a string
    (type ID TYPE)...                                       in id order
    (native ID NAME [PARAM...] RET)...                      functions, in id order
    (fn ID NAME [PARAM...] RET [LOCAL...] BLOCK)...
    (main ID)

    PARAM  = (STR MUT TYPEID)            MUT is 0 or 1; a `mut` param is passed as a pointer
    LOCAL  = (STR TYPEID)                slot i is LOCAL i; params come first, a `mut` param's
                                         slot and a `&x` binding's hold a pointer (*T)
    POS    = LINE COL FILE               three integers; FILE indexes (files)

Types (ids are assigned in the order the dumper first meets them):
    (prim NAME)                          i8..i64, u8..u64, usize, f32, f64, bool
    (ptr T)  (arr N T)  (cap NAME)  (void)
    (struct NAME SIZE ALIGN [(STR T OFFSET)...])      also a slice []T: fields ptr (*T) and len
    (union NAME SIZE ALIGN PAYOFF [VARIANT...])        also ?T; tag u32 at 0, null is tag 0
        VARIANT = (STR _) | (STR [(STR T OFFSET)...])     offsets from the start of the union
    (fn BOUND [(STR MUT T)...] RET)      fields sorted by name

Statements:
    (let SLOT E)  (zero SLOT)  (set PLACE E)  (do E)  (break)  (continue)  (return E|_)
    (if E BLOCK BLOCK|_)  (while E BLOCK)  (defer BLOCK)  (panic POS STR)
    (match E THROUGH [ARM...])           THROUGH 1: E is a pointer to the union
        ARM = ([PAT...]|_ BLOCK)                          `_` is the else arm
        PAT = (VARIANT [BIND...])                         every PAT binds the same slots
        BIND = (SLOT FIELD BYREF)        BYREF 1: the slot gets the field's address
    (letelse E VARIANT [BIND...] VARIANT|_ [BIND...] BLOCK)

Expressions; each has its type T first:
    (int T N)  (float T F)  (bool T 0|1)  (str T STR)  (null T)
    (sbytes T STR)                       a []u8 viewing static read-only bytes STR
    (local T SLOT)  (deref T E POS)  (field T E INDEX)  (index T E E POS)
    (payload T E VARIANT FIELD)          the field of a union known to hold VARIANT
    (sindex T E E POS)                   element of slice E, bounds-checked; a place
    (ssub T E LO HI|_ POS)               E[LO..HI], HI defaulting to E's length
    (addr T PLACE)                       PLACE is local, deref, sindex, field/index/payload of a place
    (seq T E E)                          evaluates the first, then gives the second
    (neg T E POS)  (not T E)  (and T E E)  (or T E E)
    (arith T OP E E POS)                 OP: add sub mul div rem; operands have type T
    (bits T OP E E)                      OP: and or xor; operands have integer type T
    (shift T OP E E POS)                 OP: shl shr; the first operand has type T, the count
                                         any integer type
    (cmp T OP E E)                       OP: eq ne lt le gt ge; operands have one type
    (ptradd T E E)  (isnull T E)  (notnull T E)
    (widen T E)  (some T E)  (fnconv T E)
    (call T FN [ARG...])  (bind T FN [ARG...])          ARG = (INDEX E), in evaluation order;
    (dcall T E [ARG...])  (dbind T E [ARG...])          INDEX: the callee's param (call, bind)
    (fnref T FN)                                        or its fn type's field (dcall, dbind)
    (struct T [ARG...])  (variant T VARIANT [ARG...])  (array T [E...])  (repeat T E)
    (ifx T E BLOCK BLOCK)  (matchx T E THROUGH [ARM...])  value blocks; without `=>` a branch
                                                        always leaves
    (as T E POS)  (trunc T E)  (wrap T OP E E)  (cast T E)  (ptraddr T E)
"""

from . import ast as A
from .checker import NativeFn
from .natives import _float_text, _shortest_f32
from .runtime import Runtime, f32r
from .types import (
    Prim, Ptr, SliceT, Arr, Opt, StructT, UnionT, FnT, Cap, VOID, USIZE, BOOL, U8, prune, subst, tkey, tstr,
    qualname, struct_fields, variants_of, widens,
)

VERSION = 4


class Sym(str):
    """A symbol atom, printed without quotes."""


class Block:
    def __init__(self, stmts, result=None, valued=False):
        self.stmts, self.result, self.valued = stmts, result, valued


NONE = Sym('_')
ARITH = {'+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'rem'}
BITS = {'&': 'and', '|': 'or', '^': 'xor'}
SHIFT = {'<<': 'shl', '>>': 'shr'}
CMP = {'==': 'eq', '!=': 'ne', '<': 'lt', '<=': 'le', '>': 'gt', '>=': 'ge'}
WRAP = {'wrap_add': 'add', 'wrap_sub': 'sub', 'wrap_mul': 'mul'}


def node(tag, *args):
    return (Sym(tag),) + args


class Dumper:
    def __init__(self, checker):
        self.c = checker
        self.rt = Runtime(checker, stack_size=0)
        self.type_ids, self.type_defs = {}, []
        self.fn_ids, self.fn_queue, self.fn_items = {}, [], []
        self.files = {}

    # ---- program

    def dump(self):
        main = self.fn_id(self.c.main, [])
        i = 0
        while i < len(self.fn_queue):
            decl, targs = self.fn_queue[i]
            self.fn_items.append(self.native(i, decl) if isinstance(decl, NativeFn)
                                 else self.function(i, decl, targs))
            i += 1
        lines = [f'ctxir {VERSION}']
        files = sorted(self.files, key=self.files.get)
        lines.append(fmt(node('files', [(f or '').encode() for f in files]), 0))
        for i, d in enumerate(self.type_defs):
            lines.append(fmt(node('type', i, d), 0))
        for item in self.fn_items:
            lines.append(fmt(item, 0))
        lines.append(fmt(node('main', main), 0))
        return '\n'.join(lines) + '\n'

    def fn_id(self, decl, targs):
        key = (id(decl), tuple(tkey(t) for t in targs))
        i = self.fn_ids.get(key)
        if i is None:
            i = self.fn_ids[key] = len(self.fn_queue)
            self.fn_queue.append((decl, targs))
        return i

    def native(self, i, nf):
        params = [(n.encode(), int(m), self.tid(t)) for n, m, t in nf.sig_fields]
        return node('native', i, qualname(nf).encode(), params, self.tid(nf.ret_t))

    def function(self, i, d, targs):
        self.m = dict(zip(d.tparam_objs, targs))
        self.slots, self.locals = {}, []
        self.ret = self.T(d.ret_t)
        name = qualname(d)
        if targs:
            name += '(' + ', '.join(tstr(t) for t in targs) + ')'
        params = []
        for (n, mut, t), v in zip(d.sig_fields, d.ctx_vars):
            params.append((n.encode(), int(mut), self.tid(self.T(t))))
            self.slot(v)
        body = self.block(d.body)
        return node('fn', i, name.encode(), params, self.tid(self.ret), self.locals, body)

    # ---- types

    def T(self, t):
        return subst(t, self.m)

    def tid(self, t):
        t = prune(t)
        k = tkey(t)
        i = self.type_ids.get(k)
        if i is not None:
            return i
        i = self.type_ids[k] = len(self.type_defs)
        self.type_defs.append(None)
        self.type_defs[i] = self.type_def(t)
        return i

    def type_def(self, t):
        if isinstance(t, Prim):
            return node('prim', Sym(t.name))
        if isinstance(t, Ptr):
            return node('ptr', self.tid(t.elem))
        if isinstance(t, Arr):
            return node('arr', t.n, self.tid(t.elem))
        if isinstance(t, Cap):
            return node('cap', t.name.encode())
        if t is VOID:
            return node('void')
        if isinstance(t, FnT):
            fields = sorted(t.fields, key=lambda f: f[0])
            return node('fn', int(t.bound), [(n.encode(), int(m), self.tid(ft)) for n, m, ft in fields],
                        self.tid(t.ret))
        lay = self.rt.layout(t)
        name = tstr(t, muts=False).encode()
        if isinstance(t, (StructT, SliceT)):     # a slice is a struct of ptr and len
            return node('struct', name, lay.size, lay.align,
                        [(n.encode(), self.tid(ft), off) for n, ft, off in lay.fields])
        variants = []
        for vname, fs in lay.variants:
            if fs is None:
                variants.append((vname.encode(), NONE))
            else:
                variants.append((vname.encode(), [(n.encode(), self.tid(ft), off) for n, ft, off in fs]))
        return node('union', name, lay.size, lay.align, lay.pay_off, variants)

    # ---- places and positions

    def slot(self, v):
        s = self.slots.get(v)
        if s is None:
            s = self.slots[v] = len(self.locals)
            t = self.T(v.ty)
            self.locals.append((v.name.encode(), self.tid(Ptr(t) if v.indirect else t)))
        return s

    def pos(self, p):
        line, col = p[0], p[1]
        f = p[2] if len(p) > 2 else None
        if f not in self.files:
            self.files[f] = len(self.files)
        return (line, col, self.files[f])

    # ---- statements

    def block(self, b):
        return Block([s for st in b.stmts for s in self.stmt(st)])

    def stmt(self, s):
        """The IR statements for s: a list, since a statement can become several."""
        return getattr(self, 's_' + type(s).__name__)(s)

    def s_Let(self, s):
        slot = self.slot(s.var)
        if s.init is None:
            return [node('zero', slot)]
        return [node('let', slot, self.conv(s.init, s.var.ty))]

    def s_Assign(self, s):
        return [node('set', self.ex(s.lhs), self.conv(s.rhs, s.lhs.ty))]

    def s_ExprStmt(self, s):
        e = s.expr
        if isinstance(e, A.Builtin) and e.name == 'panic':
            msg = e.args[0].val.decode('ascii', 'backslashreplace') if e.args else '@panic()'
            return [node('panic', *self.pos(e.pos), msg.encode())]
        return [node('do', self.ex(e))]

    def s_If(self, s):
        els = self.block(s.els) if s.els is not None else NONE
        return [node('if', self.ex(s.cond), self.block(s.then), els)]

    def s_While(self, s):
        return [node('while', self.ex(s.cond), self.block(s.body))]

    def s_Break(self, s):
        return [node('break')]

    def s_Continue(self, s):
        return [node('continue')]

    def s_Return(self, s):
        if s.expr is None:
            return [node('return', NONE)]
        return [node('return', self.conv(s.expr, self.ret))]

    def s_Defer(self, s):
        return [node('defer', self.block(s.body))]

    def s_Match(self, s):
        return [node('match', self.ex(s.scrut), int(s.through), self.arms(s, self.block))]

    def s_LetElse(self, s):
        init = self.ex(s.init)
        els_binds = self.binds(s.els_bvars)
        els = self.block(s.els)
        binds = self.binds(s.bvars)
        els_v = NONE if s.els_vindex is None else s.els_vindex
        return [node('letelse', init, s.vindex, binds, els_v, els_binds, els)]

    def arms(self, s, body):
        out = []
        for arm in s.arms:
            pats = [(vindex, self.binds(bvars)) for vindex, bvars in arm.alts] if arm.alts else NONE
            out.append((pats, body(arm.body)))
        return out

    def binds(self, bvars):
        return [(self.slot(v), fi, int(v.indirect)) for v, fi in bvars]

    def value_block(self, b, t):
        """A branch of an `if` or `match` expression of type t."""
        stmts = list(b.stmts)
        r = b.result
        if r is None:
            return Block([x for st in stmts for x in self.stmt(st)], None, True)
        out = [x for st in stmts[:-1] for x in self.stmt(st)]
        if isinstance(r, (A.If, A.Match)) and r.ty is None:
            # A nested `if` or `match` whose every branch leaves: a statement, not a value.
            out.append(self.leaving(r))
            return Block(out, None, True)
        return Block(out, self.conv(r, t), True)

    def leaving(self, e):
        if isinstance(e, A.If):
            return node('if', self.ex(e.cond), self.value_block(e.then, None),
                        self.value_block(e.els, None))
        return node('match', self.ex(e.scrut), int(e.through),
                    self.arms(e, lambda b: self.value_block(b, None)))

    # ---- expressions

    def conv(self, e, to):
        """e's IR, converted to type `to` as the checker allowed implicitly."""
        return self.coerce(self.ex(e), self.T(e.ty), self.T(to))

    def coerce(self, x, frm, to):
        if tkey(frm) == tkey(to):
            return x
        if isinstance(frm, Prim) and isinstance(to, Prim) and widens(frm, to):
            return node('widen', self.tid(to), x)
        if isinstance(frm, FnT) and isinstance(to, FnT):
            return node('fnconv', self.tid(to), x)
        raise AssertionError(f'no implicit conversion from {tstr(frm)} to {tstr(to)}')

    def ex(self, e):
        return getattr(self, 'e_' + type(e).__name__)(e, self.T(e.ty))

    def e_IntLit(self, e, t):
        return node('int', self.tid(t), e.val)

    def e_FloatLit(self, e, t):
        if t.name == 'f32':
            text = _float_text(_shortest_f32(f32r(e.val)))
        else:
            text = _float_text(repr(float(e.val)))
        return node('float', self.tid(t), Sym(text))

    def e_StrLit(self, e, t):
        view = getattr(e, 'view', None)
        if view is None:
            return node('str', self.tid(t), bytes(e.val))
        v = node('sbytes', self.tid(SliceT(U8)), bytes(e.val))
        if view == 'text':
            return node('struct', self.tid(t), [(0, v)])
        return v

    def e_BoolLit(self, e, t):
        return node('bool', self.tid(t), int(e.val))

    def e_NullLit(self, e, t):
        return node('null', self.tid(t))

    def e_Coerce(self, e, t):
        inner = self.coerce(self.ex(e.expr), self.T(e.expr.ty), t.elem)
        return node('some', self.tid(t), inner)

    def e_Path(self, e, t):
        r = e.ref
        k = r[0]
        if k == 'var':
            return self.var(r[1], e.pos)
        if k == 'fn':
            return node('fnref', self.tid(t), self.fn_id(r[1], [self.T(a) for a in r[2]]))
        if k == 'const':
            return self.ex(r[1].expr)
        return node('variant', self.tid(t), r[2], [])

    def var(self, v, pos):
        t = self.T(v.ty)
        if v.kind == 'narrow':
            return node('payload', self.tid(t), self.var(v.narrow_of, pos), 1, 0)
        s = self.slot(v)
        if v.indirect:
            return node('deref', self.tid(t), node('local', self.tid(Ptr(t)), s), *self.pos(pos))
        return node('local', self.tid(t), s)

    def e_Field(self, e, t):
        bt = self.T(e.base.ty)
        if e.kind == 'field':
            if e.narrow is not None:
                f = node('field', self.tid(self.T(e.narrow)), self.ex(e.base), field_index(bt, e.name))
                return node('payload', self.tid(t), f, 1, 0)
            return node('field', self.tid(t), self.ex(e.base), field_index(bt, e.name))
        if e.kind == 'pfield':
            base = node('deref', self.tid(bt.elem), self.ex(e.base), *self.pos(e.pos))
            return node('field', self.tid(t), base, field_index(bt.elem, e.name))
        if e.kind in ('sptr', 'slen'):
            return node('field', self.tid(t), self.ex(e.base), 0 if e.kind == 'sptr' else 1)
        n = bt.n if e.kind == 'len' else bt.elem.n
        lit = node('int', self.tid(USIZE), n)
        if e.kind == 'len' and isinstance(e.base, A.Path):
            return lit
        return node('seq', self.tid(USIZE), self.ex(e.base), lit)

    def e_Index(self, e, t):
        bt = self.T(e.base.ty)
        i = self.conv(e.index, USIZE)
        p = self.pos(e.pos)
        if e.kind == 'arr':
            return node('index', self.tid(t), self.ex(e.base), i, *p)
        if e.kind == 'parr':
            arr = node('deref', self.tid(bt.elem), self.ex(e.base), *p)
            return node('index', self.tid(t), arr, i, *p)
        if e.kind == 'slice':
            return node('sindex', self.tid(t), self.ex(e.base), i, *p)
        return node('deref', self.tid(t), node('ptradd', self.tid(bt), self.ex(e.base), i), *p)

    def e_Range(self, e, t):
        lo = self.conv(e.lo, USIZE) if e.lo is not None else node('int', self.tid(USIZE), 0)
        hi = self.conv(e.hi, USIZE) if e.hi is not None else NONE
        return node('ssub', self.tid(t), self.ex(e.base), lo, hi, *self.pos(e.pos))

    def e_ToSlice(self, e, t):
        at = self.T(e.expr.ty)
        ptr = node('cast', self.tid(Ptr(t.elem)), self.ex(e.expr))
        return node('struct', self.tid(t), [(0, ptr), (1, node('int', self.tid(USIZE), at.elem.n))])

    def e_Deref(self, e, t):
        return node('deref', self.tid(t), self.ex(e.base), *self.pos(e.pos))

    def e_AddrOf(self, e, t):
        return node('addr', self.tid(t), self.ex(e.expr))

    def e_Unary(self, e, t):
        if e.op == 'not':
            return node('not', self.tid(t), self.ex(e.expr))
        return node('neg', self.tid(t), self.ex(e.expr), *self.pos(e.pos))

    def e_Binary(self, e, t):
        op = e.op
        if op in ('and', 'or'):
            return node(op, self.tid(t), self.ex(e.lhs), self.ex(e.rhs))
        if op in ('==', '!=') and e.nullcmp:
            x = e.rhs if isinstance(e.lhs, A.NullLit) else e.lhs
            return node('isnull' if op == '==' else 'notnull', self.tid(t), self.ex(x))
        if op in CMP:
            lt, rt = self.T(e.lhs.ty), self.T(e.rhs.ty)
            common = rt if widens(lt, rt) else lt
            return node('cmp', self.tid(t), Sym(CMP[op]), self.conv(e.lhs, common), self.conv(e.rhs, common))
        if e.ptrarith:
            return node('ptradd', self.tid(t), self.ex(e.lhs), self.conv(e.rhs, USIZE))
        if op in BITS:
            return node('bits', self.tid(t), Sym(BITS[op]), self.conv(e.lhs, t), self.conv(e.rhs, t))
        if op in SHIFT:
            return node('shift', self.tid(t), Sym(SHIFT[op]), self.conv(e.lhs, t), self.ex(e.rhs),
                        *self.pos(e.pos))
        return node('arith', self.tid(t), Sym(ARITH[op]), self.conv(e.lhs, t), self.conv(e.rhs, t),
                    *self.pos(e.pos))

    def e_Braced(self, e, t):
        if hasattr(e, 'lit'):
            if e.lit[0] == 'struct':
                fields = struct_fields(t)
                return node('struct', self.tid(t), self.items(e.args, fields))
            vi = e.lit[2]
            fields = variants_of(t)[vi][1]
            return node('variant', self.tid(t), vi, self.items(e.args, fields))
        if e.call[0] == 'static':
            decl = e.call[1]
            targs = [self.T(a) for a in e.call[2]]
            m = dict(zip(decl.tparam_objs, targs))
            fields = [(n, Ptr(subst(ft, m)) if mut else subst(ft, m)) for n, mut, ft in decl.sig_fields]
            fid = self.fn_id(decl, targs)
            return node('bind' if e.bind else 'call', self.tid(t), fid, self.items(e.args, fields))
        ft = prune(self.T(e.callee.ty))
        fields = [(n, Ptr(t2) if mut else t2) for n, mut, t2 in sorted(ft.fields, key=lambda f: f[0])]
        return node('dbind' if e.bind else 'dcall', self.tid(t), self.ex(e.callee), self.items(e.args, fields))

    def items(self, args, fields):
        """ARGs for (name, mut, expr) args against [(name, type)] fields."""
        names = [n for n, _ in fields]
        out = []
        for name, _, a in args:
            i = names.index(name)
            out.append((i, self.conv(a, fields[i][1])))
        return out

    def e_ArrayLit(self, e, t):
        return node('array', self.tid(t), [self.conv(x, t.elem) for x in e.elems])

    def e_ArrayRep(self, e, t):
        return node('repeat', self.tid(t), self.conv(e.elem, t.elem))

    def e_If(self, e, t):
        return node('ifx', self.tid(t), self.ex(e.cond), self.value_block(e.then, t),
                    self.value_block(e.els, t))

    def e_Match(self, e, t):
        return node('matchx', self.tid(t), self.ex(e.scrut), int(e.through),
                    self.arms(e, lambda b: self.value_block(b, t)))

    def e_Builtin(self, e, t):
        n = e.name
        if n in ('size_of', 'align_of'):
            lay = self.rt.layout(self.T(e.targ_t))
            return node('int', self.tid(t), lay.size if n == 'size_of' else lay.align)
        if n == 'addr':
            return node('ptraddr', self.tid(t), self.ex(e.args[0]))
        if n == 'cast':
            return node('cast', self.tid(t), self.ex(e.args[0]))
        if n == 'slice':
            return node('struct', self.tid(t), [(0, self.ex(e.args[0])), (1, self.conv(e.args[1], USIZE))])
        if n == 'as':
            return node('as', self.tid(t), self.ex(e.args[0]), *self.pos(e.pos))
        if n == 'trunc':
            return node('trunc', self.tid(t), self.ex(e.args[0]))
        if n in WRAP:
            return node('wrap', self.tid(t), Sym(WRAP[n]), self.ex(e.args[0]), self.ex(e.args[1]))
        raise AssertionError(f'@{n} in an expression')


def field_index(st, name):
    return [n for n, _ in struct_fields(st)].index(name)


# ---- canonical text

def fmt(x, depth):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        raise TypeError('bool in IR; use 0 or 1')
    if isinstance(x, int):
        return str(x)
    if isinstance(x, bytes):
        return quote(x)
    if isinstance(x, tuple):
        return '(' + ' '.join(fmt(y, depth) for y in x) + ')'
    if isinstance(x, list):
        return '[' + ' '.join(fmt(y, depth) for y in x) + ']'
    if isinstance(x, Block):
        if not x.stmts and x.result is None:
            return '{}'
        pad = '  ' * (depth + 1)
        out = '{'
        for s in x.stmts:
            out += '\n' + pad + fmt(s, depth + 1)
        if x.result is not None:
            out += '\n' + pad + '=> ' + fmt(x.result, depth + 1)
        return out + '\n' + '  ' * depth + '}'
    raise TypeError(f'cannot format {x!r}')


def quote(b):
    out = ['"']
    for c in b:
        if 0x20 <= c <= 0x7e and c not in (0x22, 0x5c):
            out.append(chr(c))
        else:
            out.append(f'\\x{c:02x}')
    out.append('"')
    return ''.join(out)


def dump(checker):
    """The IR text of a checked program."""
    return Dumper(checker).dump()


# ---- verification

class IRError(Exception):
    pass


class Verifier:
    """Type-checks a dump: every node's operands have the types the module docstring requires.
    Catches a conversion the dumper missed before a backend has to."""

    def __init__(self, d):
        self.types = d.type_defs
        self.sigs = {item[1]: (item[3], item[4]) for item in d.fn_items}     # params, ret
        self.items = d.fn_items
        self.ptrs = {td[1]: i for i, td in enumerate(d.type_defs) if td[0] == 'ptr'}

    def run(self):
        for item in self.items:
            if item[0] != 'fn':
                continue
            self.fn = item[2].decode()
            self.locals = [t for _, t in item[5]]
            self.ret = item[4]
            for i, (_, mut, t) in enumerate(item[3]):
                self.expect(self.locals[i] == (self.ptrs.get(t) if mut else t), f'param {i} slot type')
            self.block(item[6])

    # ---- helpers

    def expect(self, ok, what):
        if not ok:
            raise IRError(f'in {self.fn}: {what}')

    def kind(self, t):
        return self.types[t][0]

    def prim(self, t):
        d = self.types[t]
        return d[1] if d[0] == 'prim' else None

    def is_int(self, t):
        p = self.prim(t)
        return p is not None and p not in ('f32', 'f64', 'bool')

    def is_float(self, t):
        return self.prim(t) in ('f32', 'f64')

    def is_num(self, t):
        return self.is_int(t) or self.is_float(t)

    def is_bool(self, t):
        return self.prim(t) == 'bool'

    def is_usize(self, t):
        return self.prim(t) == 'usize'

    def slice_elem(self, t):
        """The element type of a slice struct (fields ptr: *T, len: usize), else None."""
        d = self.types[t]
        if d[0] != 'struct' or len(d[4]) != 2:
            return None
        (pn, pt, _), (ln, lt, _) = d[4]
        if pn != b'ptr' or ln != b'len' or self.kind(pt) != 'ptr' or not self.is_usize(lt):
            return None
        return self.types[pt][1]

    def is_opt(self, t):
        d = self.types[t]
        return d[0] == 'union' and d[1].startswith(b'?')

    def payload(self, t, v, f):
        d = self.types[t]
        self.expect(d[0] == 'union', f'type {t} is not a union')
        fs = d[5][v][1]
        self.expect(fs != NONE, f'variant {v} of type {t} has no payload')
        return fs[f][1]

    def fn_type(self, t):
        d = self.types[t]
        self.expect(d[0] == 'fn', f'type {t} is not a function type')
        return d

    # ---- statements

    def block(self, b, result_t=None):
        for s in b.stmts:
            self.stmt(s)
        if b.result is not None:
            got = self.ex(b.result)
            self.expect(got == result_t, f'value block gives {got}, wants {result_t}')

    def stmt(self, s):
        tag = s[0]
        if tag == 'let':
            got = self.ex(s[2])
            self.expect(got == self.locals[s[1]], f'let {s[1]}: {got} vs {self.locals[s[1]]}')
        elif tag == 'set':
            self.place(s[1])
            self.expect(self.ex(s[1]) == self.ex(s[2]), 'set with different types')
        elif tag == 'do':
            self.ex(s[1])
        elif tag == 'if':
            self.expect(self.is_bool(self.ex(s[1])), 'if condition')
            self.block(s[2])
            if s[3] != NONE:
                self.block(s[3])
        elif tag == 'while':
            self.expect(self.is_bool(self.ex(s[1])), 'while condition')
            self.block(s[2])
        elif tag == 'return':
            if s[1] == NONE:
                self.expect(self.kind(self.ret) == 'void', 'return without a value')
            else:
                got = self.ex(s[1])
                self.expect(got == self.ret, f'return type {got} vs {self.ret}')
        elif tag == 'defer':
            self.block(s[1])
        elif tag == 'match':
            self.arms(s[1], s[2], s[3], None)
        elif tag == 'letelse':
            t = self.ex(s[1])
            self.binds(t, s[2], s[3], False)
            if s[4] != NONE:
                self.binds(t, s[4], s[5], False)
            self.block(s[6])
        elif tag not in ('zero', 'break', 'continue', 'panic'):
            raise IRError(f'unknown statement {tag}')

    def arms(self, scrut, through, arms, result_t):
        t = self.ex(scrut)
        if through:
            self.expect(self.kind(t) == 'ptr', 'match through a non-pointer')
            t = self.types[t][1]
        self.expect(self.kind(t) == 'union', 'match on a non-union')
        for pats, body in arms:
            if pats != NONE:
                self.expect(len(pats) > 0, 'an arm without patterns')
                for v, binds in pats:
                    self.binds(t, v, binds, through)
                self.expect(len({tuple(sorted(slot for slot, _, _ in binds)) for _, binds in pats}) == 1,
                            "an arm's patterns bind different slots")
            self.block(body, result_t)

    def binds(self, t, v, binds, through):
        for slot, f, byref in binds:
            ft = self.payload(t, v, f)
            self.expect(not byref or through, 'by-reference binding without a pointer')
            self.expect(self.locals[slot] == (self.ptrs.get(ft) if byref else ft), f'binding slot {slot} type')

    # ---- expressions

    def place(self, e):
        tag = e[0]
        if tag in ('field', 'index', 'payload'):
            self.place(e[2])
        elif tag not in ('local', 'deref', 'sindex'):
            raise IRError(f'in {self.fn}: {tag} is not a place')

    def args(self, args, params, what):
        seen = set()
        for i, a in args:
            self.expect(i not in seen, f'{what}: param {i} given twice')
            seen.add(i)
            _, mut, pt = params[i]
            want = self.ptrs.get(pt) if mut else pt
            got = self.ex(a)
            self.expect(got == want, f'{what}: param {i} is {got}, wants {want}')
        return seen

    def ex(self, e):
        tag, t = e[0], e[1]
        k = self.kind(t)
        if tag == 'int':
            self.expect(self.is_int(t), 'int literal type')
        elif tag == 'float':
            self.expect(self.is_float(t), 'float literal type')
        elif tag == 'bool':
            self.expect(self.is_bool(t), 'bool literal type')
        elif tag == 'str':
            d = self.types[t]
            self.expect(d[0] == 'arr' and d[1] == len(e[2]) and self.prim(d[2]) == 'u8', 'string type')
        elif tag == 'sbytes':
            se = self.slice_elem(t)
            self.expect(se is not None and self.prim(se) == 'u8', 'sbytes type')
        elif tag == 'null':
            self.expect(self.is_opt(t), 'null type')
        elif tag == 'local':
            self.expect(self.locals[e[2]] == t, f'local {e[2]} type')
        elif tag == 'deref':
            self.expect(self.types[self.ex(e[2])] == ('ptr', t), 'deref of a non-pointer')
        elif tag == 'field':
            d = self.types[self.ex(e[2])]
            self.expect(d[0] == 'struct' and d[4][e[3]][1] == t, 'field type')
        elif tag == 'index':
            d = self.types[self.ex(e[2])]
            self.expect(d[0] == 'arr' and d[2] == t, 'index of a non-array')
            self.expect(self.is_usize(self.ex(e[3])), 'index is not usize')
        elif tag == 'sindex':
            self.expect(self.slice_elem(self.ex(e[2])) == t, 'sindex of a non-slice')
            self.expect(self.is_usize(self.ex(e[3])), 'index is not usize')
        elif tag == 'ssub':
            self.expect(self.slice_elem(t) is not None and self.ex(e[2]) == t, 'ssub type')
            self.expect(self.is_usize(self.ex(e[3])), 'ssub lo is not usize')
            self.expect(e[4] == NONE or self.is_usize(self.ex(e[4])), 'ssub hi is not usize')
        elif tag == 'payload':
            self.expect(self.payload(self.ex(e[2]), e[3], e[4]) == t, 'payload type')
        elif tag == 'addr':
            self.place(e[2])
            self.expect(self.types[t] == ('ptr', self.ex(e[2])), 'addr type')
        elif tag == 'seq':
            self.ex(e[2])
            self.expect(self.ex(e[3]) == t, 'seq type')
        elif tag == 'neg':
            self.expect(self.is_num(t) and self.ex(e[2]) == t, 'neg')
        elif tag == 'not':
            self.expect(self.is_bool(t) and self.is_bool(self.ex(e[2])), 'not')
        elif tag in ('and', 'or'):
            self.expect(self.is_bool(t) and self.is_bool(self.ex(e[2])) and self.is_bool(self.ex(e[3])), tag)
        elif tag == 'arith':
            a, b = self.ex(e[3]), self.ex(e[4])
            self.expect(self.is_num(t) and a == t and b == t, f'arith operands {a} {b} vs {t}')
        elif tag == 'bits':
            a, b = self.ex(e[3]), self.ex(e[4])
            self.expect(self.is_int(t) and a == t and b == t, f'bits operands {a} {b} vs {t}')
        elif tag == 'shift':
            a, b = self.ex(e[3]), self.ex(e[4])
            self.expect(self.is_int(t) and a == t and self.is_int(b), f'shift operands {a} {b} vs {t}')
        elif tag == 'cmp':
            a, b = self.ex(e[3]), self.ex(e[4])
            self.expect(self.is_bool(t) and a == b, f'cmp operands {a} {b}')
            self.expect(self.prim(a) is not None or self.kind(a) == 'ptr', 'cmp operand type')
            if e[2] not in ('eq', 'ne'):
                self.expect(self.is_num(a), 'ordering on non-numbers')
        elif tag == 'ptradd':
            self.expect(k == 'ptr' and self.ex(e[2]) == t and self.is_usize(self.ex(e[3])), 'ptradd')
        elif tag in ('isnull', 'notnull'):
            self.expect(self.is_bool(t) and self.is_opt(self.ex(e[2])), tag)
        elif tag == 'widen':
            f = self.ex(e[2])
            self.expect(self.prim(f) is not None and self.prim(t) is not None and f != t, 'widen')
        elif tag == 'some':
            got = self.ex(e[2])
            self.expect(self.is_opt(t) and self.payload(t, 1, 0) == got, f'some of {got} into {t}')
        elif tag == 'fnconv':
            self.fn_type(t)
            self.fn_type(self.ex(e[2]))
        elif tag in ('call', 'bind'):
            params, ret = self.sigs[e[2]]
            seen = self.args(e[3], params, f'{tag} {e[2]}')
            if tag == 'call':
                self.expect(len(seen) == len(params) and ret == t, f'call {e[2]}')
            else:
                d = self.fn_type(t)
                missing = sorted((p for i, p in enumerate(params) if i not in seen), key=lambda p: p[0])
                self.expect(d[1] == 1 and list(d[2]) == missing and d[3] == ret, 'bind type')
        elif tag in ('dcall', 'dbind'):
            d = self.fn_type(self.ex(e[2]))
            seen = self.args(e[3], d[2], tag)
            if tag == 'dcall':
                self.expect(len(seen) == len(d[2]) and d[3] == t, 'dcall')
            else:
                r = self.fn_type(t)
                missing = [p for i, p in enumerate(d[2]) if i not in seen]
                self.expect(r[1] == 1 and list(r[2]) == missing and r[3] == d[3], 'dbind type')
        elif tag == 'fnref':
            params, ret = self.sigs[e[2]]
            d = self.fn_type(t)
            self.expect(d[1] == 0 and list(d[2]) == sorted(params, key=lambda p: p[0]) and d[3] == ret,
                        'fnref type')
        elif tag == 'struct':
            fields = [(n, 0, ft) for n, ft, _ in self.types[t][4]]
            self.expect(len(self.args(e[2], fields, 'struct')) == len(fields), 'struct literal misses fields')
        elif tag == 'variant':
            fs = self.types[t][5][e[2]][1]
            fields = [] if fs == NONE else [(n, 0, ft) for n, ft, _ in fs]
            self.expect(len(self.args(e[3], fields, 'variant')) == len(fields), 'variant literal misses fields')
        elif tag == 'array':
            d = self.types[t]
            self.expect(d[0] == 'arr' and d[1] == len(e[2]), 'array length')
            for x in e[2]:
                self.expect(self.ex(x) == d[2], 'array element type')
        elif tag == 'repeat':
            self.expect(self.ex(e[2]) == self.types[t][2], 'repeat element type')
        elif tag == 'ifx':
            self.expect(self.is_bool(self.ex(e[2])), 'ifx condition')
            self.block(e[3], t)
            self.block(e[4], t)
        elif tag == 'matchx':
            self.arms(e[2], e[3], e[4], t)
        elif tag == 'as':
            self.expect(self.is_num(self.ex(e[2])) and self.is_num(t), '@as')
        elif tag == 'trunc':
            self.expect(self.is_int(self.ex(e[2])) and self.is_int(t), '@trunc')
        elif tag == 'wrap':
            self.expect(self.is_int(t) and self.ex(e[3]) == t and self.ex(e[4]) == t, '@wrap')
        elif tag == 'cast':
            self.expect(k == 'ptr' and self.kind(self.ex(e[2])) == 'ptr', '@cast')
        elif tag == 'ptraddr':
            self.expect(self.is_usize(t) and self.kind(self.ex(e[2])) == 'ptr', '@addr')
        else:
            raise IRError(f'unknown expression {tag}')
        return t


def verify(checker):
    """Dumps a checked program and type-checks the result. Returns the IR text."""
    d = Dumper(checker)
    text = d.dump()
    Verifier(d).run()
    return text
