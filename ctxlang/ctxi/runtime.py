"""Closure compiler and flat-memory runtime.

Every local, context field and heap byte lives in one bytearray. Scalars
(integers, floats, bool, pointers, function values) are Python numbers at
runtime; aggregates (structs, unions, optionals, arrays) are `bytes` holding
their exact memory image, so copies, @cast and byte-level allocators work.

Each generic instantiation is compiled lazily, on its first call, into a tree
of Python closures that take the frame pointer.
"""

import io
import math
import struct

from . import ast as A
from .lexer import CompileError
from .checker import NativeFn
from .types import (
    Prim, Ptr, SliceT, Arr, Opt, StructT, UnionT, EnumT, FnT, Cap, VOID, USIZE, prune, subst, tkey, tstr,
    qualname,
    struct_fields, variants_of,
)

GUARD = 64            # addresses below this are never valid
PAGE = 4096           # mem::pages hands out memory in multiples of this
TAG = struct.Struct('<I')
U64 = struct.Struct('<Q')
SLICE = struct.Struct('<QQ')     # a slice's memory image: ptr, len
F32 = struct.Struct('<f')
RET_NONE = (None,)
# Statement closures return None to fall through, a 1-tuple to return, or one of these.
BREAK = object()
CONTINUE = object()


class Jump:
    """The signal of a labeled break or continue that leaves or repeats an outer loop."""
    __slots__ = ('loop', 'repeat')

    def __init__(self, loop, repeat):
        self.loop, self.repeat = loop, repeat


class Value:
    """The signal a value block's last expression returns: the block's value."""
    __slots__ = ('v',)

    def __init__(self, v):
        self.v = v


class Tail:
    """Stands in for a value block's last statement: the expression that gives its value."""

    def __init__(self, expr):
        self.expr = expr


class Escape(Exception):
    """A branch of an `if` or `match` expression left through return, break or continue.

    Expression closures return values, not control signals, so the signal travels as an
    exception to the enclosing statement, which returns it as usual.
    """

    def __init__(self, signal):
        self.signal = signal

FMT = {'i8': 'b', 'u8': 'B', 'i16': 'h', 'u16': 'H', 'i32': 'i', 'u32': 'I',
       'i64': 'q', 'u64': 'Q', 'usize': 'Q', 'f32': 'f', 'f64': 'd', 'bool': '?'}
CODECS = {k: struct.Struct('<' + v) for k, v in FMT.items()}


class Panic(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg, self.pos = msg, pos
        self.frames = []     # qualified function names, innermost first


def align_up(n, a):
    return (n + a - 1) // a * a


def f32r(x):
    try:
        return F32.unpack(F32.pack(x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


class Layout:
    def __init__(self, size, align):
        self.size, self.align = size, align
        self.offs = {}        # struct: field -> offset
        self.fields = []      # struct: [(name, type, offset)]
        self.variants = []    # union/optional: [(name, [(field, type, absolute offset)] or None)]


class Callable:
    pass


class FnInst(Callable):
    def __init__(self, rt, decl, targs):
        self.rt, self.decl, self.targs = rt, decl, targs
        self.body = None

    def compile(self):
        d = self.decl
        c = Compiler(self.rt, dict(zip(d.tparam_objs, self.targs)))
        params = []
        for v in d.ctx_vars:
            off = c.alloc_var(v)
            st = self.rt.u64_store if v.indirect else self.rt.storer(c.T(v.ty))
            params.append((v.name, off, st))
        self.params = params
        self.body = c.block(d.body)
        self.frame = align_up(c.max, 16)

    def call(self, args):
        if self.body is None:
            self.compile()
        rt = self.rt
        fp = rt.sp
        sp = fp + self.frame
        if sp > rt.stack_end:
            raise Panic('stack overflow')
        rt.sp = sp
        try:
            for name, off, st in self.params:
                st(fp + off, args[name])
            r = self.body(fp)
        except Panic as e:
            e.frames.append(qualname(self.decl))
            raise
        finally:
            rt.sp = fp
        return None if r is None else r[0]


class Closure(Callable):
    def __init__(self, target, captured):
        self.target, self.captured = target, captured

    def call(self, args):
        a = dict(self.captured)
        a.update(args)
        return self.target.call(a)


class NativeCallable(Callable):
    def __init__(self, rt, nf):
        self.rt, self.nf = rt, nf

    def call(self, args):
        return self.nf.impl(self.rt, self.nf, args)


class Runtime:
    def __init__(self, checker, stack_size=16 << 20, out=None, err=None, inp=None):
        import sys
        self.checker = checker
        self.mem = bytearray(GUARD + stack_size)
        self.stack_end = len(self.mem)
        self.end = len(self.mem)  # grows as mem::pages hands out memory above the stack
        self.sp = GUARD
        self.callables = [None]
        self.fn_ids = {}
        self.insts = {}
        self.layouts = {}
        self.layout_busy = set()
        self.consts = {}
        self.const_busy = set()
        self.streams = [out or sys.stdout, err or sys.stderr]
        self.inp = inp if inp is not None else sys.stdin.buffer
        self.files = {}           # handle -> open Python file, for std/fs.ctx
        self.statics = {}         # string literal bytes -> their address, for literal views
        self.next_file = 1
        mem = self.mem
        self.u64_load = lambda a: U64.unpack_from(mem, a)[0]
        self.u64_store = lambda a, v: U64.pack_into(mem, a, v)

    # ---- helpers for natives

    def arg_type(self, nf, name):
        for n, _, t in nf.sig_fields:
            if n == name:
                return t
        raise KeyError(name)

    @staticmethod
    def slice_arg(nf, name, v):
        """(address, length) of a slice argument."""
        return U64.unpack_from(v, 0)[0], U64.unpack_from(v, 8)[0]

    @staticmethod
    def make_slice(addr, n):
        """The memory image of a slice: its pointer, then its length."""
        return SLICE.pack(addr, n)

    def push_bytes(self, data, align=1):
        """Copies data to the bottom of the stack, below main's frame. Returns its address."""
        addr = align_up(self.sp, align)
        self.sp = addr + len(data)
        if self.sp > self.stack_end:
            raise Panic('stack overflow')
        self.mem[addr:self.sp] = data
        return addr

    def grow(self, size):
        """Appends `size` zero bytes at a PAGE-aligned address. Returns it, or 0 if out of memory."""
        addr = align_up(self.end, PAGE)
        try:
            self.mem.extend(bytes(addr + size - self.end))
        except MemoryError:
            return 0
        self.end = len(self.mem)
        return addr

    def static_bytes(self, data):
        """The address of a read-only copy of data, appended above everything else once."""
        addr = self.statics.get(data)
        if addr is None:
            addr = self.end
            self.mem.extend(data)
            self.end = len(self.mem)
            self.statics[data] = addr
        return addr

    def close_files(self):
        for f in self.files.values():
            f.close()
        self.files.clear()

    def span(self, addr, n, pos=None):
        if n and (addr < GUARD or addr + n > self.end):
            panic('invalid memory access', pos)
        return addr, addr + n

    def write(self, stream, data):
        s = self.streams[stream]
        buf = getattr(s, 'buffer', None)
        if buf is not None:
            s.flush()
            buf.write(data)
            if stream == 1:
                buf.flush()
        elif isinstance(s, io.TextIOBase):
            s.write(data.decode('utf-8', 'replace'))
        else:
            s.write(data)

    def read(self, n):
        f = getattr(self.inp, 'read1', None) or self.inp.read
        return f(n) or b''

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
                buf = getattr(s, 'buffer', None)
                if buf is not None:
                    buf.flush()
            except (OSError, ValueError):
                pass

    # ---- layout

    def layout(self, t):
        t = prune(t)
        if isinstance(t, EnumT):
            return self.layout(t.decl.base_t)
        k = tkey(t)
        lay = self.layouts.get(k)
        if lay is not None:
            return lay
        if k in self.layout_busy:
            raise CompileError(f'type {tstr(t)} has infinite size')
        self.layout_busy.add(k)
        if isinstance(t, Prim):
            n = t.bits // 8
            lay = Layout(n, n)
        elif isinstance(t, (Ptr, FnT)):
            lay = Layout(8, 8)
        elif isinstance(t, SliceT):
            lay = Layout(16, 8)
            lay.fields = [('ptr', Ptr(t.elem, t.mut), 0), ('len', USIZE, 8)]
            lay.offs = {'ptr': 0, 'len': 8}
        elif isinstance(t, Cap):
            lay = Layout(0, 1)
        elif isinstance(t, Arr):
            el = self.layout(t.elem)
            lay = Layout(t.n * el.size, el.align)
        elif isinstance(t, StructT):
            off, al, fields = 0, 1, []
            for name, ft in struct_fields(t):
                fl = self.layout(ft)
                off = align_up(off, fl.align)
                fields.append((name, ft, off))
                off += fl.size
                al = max(al, fl.align)
            lay = Layout(align_up(off, al), al)
            lay.fields = fields
            lay.offs = {n: o for n, _, o in fields}
        elif isinstance(t, (UnionT, Opt)):
            vs = variants_of(t)
            pal, psize, rel = 1, 0, []
            for name, fs in vs:
                if fs is None:
                    rel.append((name, None))
                    continue
                off, out = 0, []
                for fname, ft in fs:
                    fl = self.layout(ft)
                    off = align_up(off, fl.align)
                    out.append((fname, ft, off))
                    off += fl.size
                    pal = max(pal, fl.align)
                psize = max(psize, off)
                rel.append((name, out))
            al = max(4, pal)
            pay = align_up(4, pal)
            lay = Layout(align_up(pay + psize, al), al)
            lay.pay_off = pay
            lay.variants = [(n, None if fs is None else [(f, ft, pay + o) for f, ft, o in fs])
                            for n, fs in rel]
        elif t is VOID:
            lay = Layout(0, 1)
        else:
            raise CompileError(f'type {tstr(t)} has no layout')
        self.layout_busy.discard(k)
        self.layouts[k] = lay
        return lay

    # ---- memory access

    def codec(self, t):
        t = prune(t)
        if isinstance(t, EnumT):
            t = t.decl.base_t
        if isinstance(t, Prim):
            return CODECS[t.name]
        if isinstance(t, (Ptr, FnT)):
            return U64
        return None

    def loader(self, t):
        mem = self.mem
        c = self.codec(t)
        if c is not None:
            uf = c.unpack_from
            return lambda a: uf(mem, a)[0]
        n = self.layout(t).size
        return lambda a: bytes(mem[a:a + n])

    def storer(self, t):
        mem = self.mem
        c = self.codec(t)
        if c is not None:
            pi = c.pack_into
            return lambda a, v: pi(mem, a, v)
        n = self.layout(t).size

        def st(a, v):
            mem[a:a + n] = v
        return st

    def decoder(self, t):
        c = self.codec(t)
        if c is not None:
            uf = c.unpack_from
            return lambda buf, off: uf(buf, off)[0]
        n = self.layout(t).size
        return lambda buf, off: bytes(buf[off:off + n])

    def encoder(self, t):
        c = self.codec(t)
        if c is not None:
            return c.pack_into
        n = self.layout(t).size

        def enc(buf, off, v):
            buf[off:off + n] = v
        return enc

    # ---- functions and consts

    def get_callable(self, decl, targs):
        key = (id(decl), tuple(tkey(t) for t in targs))
        c = self.insts.get(key)
        if c is None:
            c = NativeCallable(self, decl) if isinstance(decl, NativeFn) else FnInst(self, decl, targs)
            self.insts[key] = c
        return c

    def fn_value(self, decl, targs):
        key = (id(decl), tuple(tkey(t) for t in targs))
        idx = self.fn_ids.get(key)
        if idx is None:
            idx = self.add_callable(self.get_callable(decl, targs))
            self.fn_ids[key] = idx
        return idx

    def add_callable(self, c):
        self.callables.append(c)
        return len(self.callables) - 1

    def const_value(self, d):
        if d in self.consts:
            return self.consts[d]
        if d in self.const_busy:
            raise CompileError(f'const `{d.name}` refers to itself', d.pos)
        self.const_busy.add(d)
        v = Compiler(self, {}).expr(d.expr)(0)
        self.const_busy.discard(d)
        self.consts[d] = v
        return v


def panic(msg, pos=None):
    raise Panic(msg, pos)


class Compiler:
    def __init__(self, rt, m):
        self.rt, self.m = rt, m
        self.off = 0
        self.max = 0
        self.slots = {}
        self.value_blocks = 0     # how many `if`/`match` expressions have been compiled

    def T(self, t):
        return subst(t, self.m)

    def size(self, t):
        return self.rt.layout(self.T(t)).size

    def alloc(self, size, align):
        off = align_up(self.off, max(align, 1))
        self.off = off + size
        self.max = max(self.max, self.off)
        return off

    def alloc_var(self, v):
        if v.indirect:
            off = self.alloc(8, 8)
        else:
            lay = self.rt.layout(self.T(v.ty))
            off = self.alloc(lay.size, lay.align)
        self.slots[v] = off
        return off

    # ---------------------------------------------------------------- statements

    def block(self, b):
        save = self.off
        run = self.seq(list(b.stmts))
        self.off = save
        return run

    def seq(self, stmts):
        """Closure running stmts in order, returning the first control signal.

        Statements after a `defer` run inside it: the deferred body runs once they finish,
        however they finish, except by a panic.
        """
        fns = []
        for i, s in enumerate(stmts):
            if isinstance(s, A.Defer):
                d = self.block(s.body)
                rest = self.seq(stmts[i + 1:])

                def deferred(fp, rest=rest, d=d):
                    r = rest(fp)
                    d(fp)
                    return r
                fns.append(deferred)
                break
            fns.append(self.stmt(s))
        if not fns:
            return lambda fp: None
        if len(fns) == 1:
            return fns[0]
        fns = tuple(fns)

        def run(fp):
            for f in fns:
                r = f(fp)
                if r is not None:
                    return r
        return run

    def s_Tail(self, s):
        ev = self.expr(s.expr)

        def tail(fp):
            try:
                return Value(ev(fp))
            except Escape as e:      # a branch of a nested expression left
                return e.signal
        return tail

    def stmt(self, s):
        before = self.value_blocks
        f = getattr(self, 's_' + type(s).__name__)(s)
        if self.value_blocks == before:
            return f

        def catch(fp):
            try:
                return f(fp)
            except Escape as e:
                return e.signal
        return catch

    def value_block(self, b):
        """A branch of an `if` or `match` expression: a closure returning its value."""
        self.value_blocks += 1
        save = self.off
        stmts = list(b.stmts)
        if b.result is not None:
            stmts[-1] = Tail(b.result)
        body = self.seq(stmts)
        self.off = save

        def run(fp):
            r = body(fp)
            if type(r) is Value:
                return r.v
            raise Escape(r)
        return run

    def s_Let(self, s):
        ev = self.expr(s.init) if s.init is not None else None
        off = self.alloc_var(s.var)
        if ev is not None:
            st = self.rt.storer(self.T(s.var.ty))

            def let(fp):
                st(fp + off, ev(fp))
            return let
        n = self.size(s.var.ty)
        z = bytes(n)
        mem = self.rt.mem

        def let0(fp):
            mem[fp + off:fp + off + n] = z
        return let0

    def s_Assign(self, s):
        pl = self.place(s.lhs)
        ev = self.expr(s.rhs)
        st = self.rt.storer(self.T(s.lhs.ty))

        def assign(fp):
            v = ev(fp)
            st(pl(fp), v)
        return assign

    def e_If(self, e):
        c = self.expr(e.cond)
        t = self.value_block(e.then)
        f = self.value_block(e.els)
        return lambda fp: t(fp) if c(fp) else f(fp)

    def s_If(self, s):
        c = self.expr(s.cond)
        t = self.block(s.then)
        if s.els is None:
            def if1(fp):
                if c(fp):
                    return t(fp)
            return if1
        e = self.block(s.els)

        def if2(fp):
            if c(fp):
                return t(fp)
            return e(fp)
        return if2

    def s_While(self, s):
        c = self.expr(s.cond)
        body = self.block(s.body)

        def loop(fp):
            while c(fp):
                r = body(fp)
                if r is not None:
                    if r is BREAK:
                        return None
                    if r is CONTINUE:
                        continue
                    if type(r) is Jump and r.loop is s:
                        if r.repeat:
                            continue
                        return None
                    return r
        return loop

    def s_Break(self, s):
        sig = BREAK if s.target is None else Jump(s.target, False)
        return lambda fp: sig

    def s_Continue(self, s):
        sig = CONTINUE if s.target is None else Jump(s.target, True)
        return lambda fp: sig

    def s_Match(self, s):
        return self.match(s, self.block)

    def e_Match(self, e):
        return self.match(e, self.value_block)

    def match(self, s, compile_body):
        if isinstance(s.utype, EnumT):
            return self.enum_match(s, compile_body)
        rt = self.rt
        lay = rt.layout(self.T(s.utype))
        sv = self.expr(s.scrut)
        through = s.through
        size = lay.size
        mem = rt.mem
        table = {}
        other = None
        for arm in s.arms:
            save = self.off
            for v, _ in arm.bvars:
                self.alloc_var(v)
            alts = [(vindex, self.pattern_binds(lay, vindex, bvars, through)) for vindex, bvars in arm.alts]
            body = compile_body(arm.body)
            self.off = save
            if not arm.alts:
                other = ((), body)
            for vindex, binds in alts:
                table[vindex] = (binds, body)
        pos = s.pos
        u64s = rt.u64_store

        def match(fp):
            v = sv(fp)
            if through:
                if v < GUARD or v + size > rt.end:
                    panic('invalid memory access', pos)
                tag = TAG.unpack_from(mem, v)[0]
            else:
                tag = TAG.unpack_from(v, 0)[0]
            binds, body = table.get(tag, other)
            for kind, off, foff, ld, st in binds:
                if kind == 0:
                    u64s(fp + off, v + foff)
                elif kind == 1:
                    st(fp + off, ld(v + foff))
                else:
                    st(fp + off, ld(v, foff))
            return body(fp)
        return match

    def enum_match(self, s, compile_body):
        """A match on an enum: its arms by value, since an enum is its base integer."""
        values = s.utype.decl.values
        sv = self.expr(s.scrut)
        table, other = {}, None
        for arm in s.arms:
            body = compile_body(arm.body)
            if not arm.alts:
                other = body
            for vindex, _ in arm.alts:
                table[values[vindex]] = body

        def match(fp):
            return table.get(sv(fp), other)(fp)
        return match

    def pattern_binds(self, lay, vindex, bvars, through):
        """How to fill a pattern's bindings, which must already have slots: (kind, slot, field
        offset, load, store) for bind_fields."""
        rt = self.rt
        binds = []
        for v, fi in bvars:
            off = self.slots[v]
            _, ft, foff = lay.variants[vindex][1][fi]
            if through and v.indirect:
                binds.append((0, off, foff, None, None))
            elif through:
                binds.append((1, off, foff, rt.loader(ft), rt.storer(ft)))
            else:
                binds.append((2, off, foff, rt.decoder(ft), rt.storer(ft)))
        return tuple(binds)

    def s_LetElse(self, s):
        lay = self.rt.layout(self.T(s.utype))
        sv = self.expr(s.init)
        save = self.off
        for v, _ in s.els_bvars:
            self.alloc_var(v)
        els_binds = self.pattern_binds(lay, s.els_vindex, s.els_bvars, False)
        els = self.block(s.els)
        self.off = save
        for v, _ in s.bvars:                                            # live to the end of the block
            self.alloc_var(v)
        binds = self.pattern_binds(lay, s.vindex, s.bvars, False)
        want = s.vindex

        def let_else(fp):
            v = sv(fp)
            if TAG.unpack_from(v, 0)[0] != want:
                for _, off, foff, ld, st in els_binds:
                    st(fp + off, ld(v, foff))
                return els(fp)           # the checker ensures it leaves
            for _, off, foff, ld, st in binds:
                st(fp + off, ld(v, foff))
        return let_else

    def s_Return(self, s):
        if s.expr is None:
            return lambda fp: RET_NONE
        ev = self.expr(s.expr)
        return lambda fp: (ev(fp),)

    def s_ExprStmt(self, s):
        ev = self.expr(s.expr)

        def es(fp):
            ev(fp)
        return es

    # ---------------------------------------------------------------- places

    def var_place(self, v):
        if v.kind == 'narrow':
            base = self.var_place(v.narrow_of)
            off = self.rt.layout(self.T(v.narrow_of.ty)).variants[1][1][0][2]
            return lambda fp: base(fp) + off
        off = self.slots[v]
        if v.indirect:
            ld = self.rt.u64_load
            return lambda fp: ld(fp + off)
        return lambda fp: fp + off

    def checked(self, f, size, pos):
        rt = self.rt

        def chk(fp):
            a = f(fp)
            if a < GUARD or a + size > rt.end:
                panic('invalid memory access', pos)
            return a
        return chk

    def place(self, e):
        """Closure computing the address of place e, or None if e isn't a place."""
        if isinstance(e, A.Path):
            if e.ref[0] == 'var':
                return self.var_place(e.ref[1])
            return None
        if isinstance(e, A.Field):
            if e.kind == 'field':
                bp = self.place(e.base)
                if bp is None:
                    return None
                off = self.rt.layout(self.T(e.base.ty)).offs[e.name]
                if e.narrow is not None:        # the payload of a narrowed ?T field
                    off += self.rt.layout(self.T(e.narrow)).variants[1][1][0][2]
                return lambda fp: bp(fp) + off
            if e.kind == 'pfield':
                bv = self.expr(e.base)
                off = self.rt.layout(self.T(e.base.ty).elem).offs[e.name]
                return self.checked(lambda fp: bv(fp) + off, self.size(e.ty), e.pos)
            return None
        if isinstance(e, A.Index):
            iv = self.expr(e.index)
            es = self.size(e.ty)
            pos = e.pos
            if e.kind == 'arr':
                bp = self.place(e.base)
                if bp is None:
                    return None
                n = self.T(e.base.ty).n

                def idx(fp):
                    a = bp(fp)
                    i = iv(fp)
                    if i >= n:
                        panic(f'index {i} out of bounds for length {n}', pos)
                    return a + i * es
                return idx
            bv = self.expr(e.base)
            if e.kind == 'slice':
                def sidx(fp):
                    p, n = SLICE.unpack(bv(fp))
                    i = iv(fp)
                    if i >= n:
                        panic(f'index {i} out of bounds for length {n}', pos)
                    return p + i * es
                return self.checked(sidx, es, pos)
            if e.kind == 'parr':
                n = self.T(e.base.ty).elem.n

                def pidx(fp):
                    a = bv(fp)
                    i = iv(fp)
                    if i >= n:
                        panic(f'index {i} out of bounds for length {n}', pos)
                    return a + i * es
                return self.checked(pidx, es, pos)
            return self.checked(lambda fp: bv(fp) + iv(fp) * es, es, pos)
        if isinstance(e, A.Deref):
            return self.checked(self.expr(e.base), self.size(e.ty), e.pos)
        return None

    # ---------------------------------------------------------------- expressions

    def expr(self, e):
        return getattr(self, 'e_' + type(e).__name__)(e)

    def load_place(self, pl, t):
        ld = self.rt.loader(self.T(t))
        return lambda fp: ld(pl(fp))

    def e_IntLit(self, e):
        v = e.val
        return lambda fp: v

    def e_FloatLit(self, e):
        v = e.val
        if prune(e.ty).name == 'f32':
            v = f32r(v)
        return lambda fp: v

    def e_StrLit(self, e):
        if getattr(e, 'view', None) is not None:
            # A []u8, or a utf8::String, whose memory image is the same slice.
            v = SLICE.pack(self.rt.static_bytes(bytes(e.val)), len(e.val))
        else:
            v = e.val
        return lambda fp: v

    def e_BoolLit(self, e):
        v = e.val
        return lambda fp: v

    def e_NullLit(self, e):
        z = bytes(self.size(e.ty))
        return lambda fp: z

    def e_Path(self, e):
        r = e.ref
        k = r[0]
        if k == 'var':
            v = r[1]
            ld = self.rt.loader(self.T(e.ty))
            if v.kind != 'narrow' and not v.indirect:
                off = self.slots[v]
                return lambda fp: ld(fp + off)
            pl = self.var_place(v)
            return lambda fp: ld(pl(fp))
        if k == 'fn':
            idx = self.rt.fn_value(r[1], [self.T(t) for t in r[2]])
            return lambda fp: idx
        if k == 'const':
            val = self.rt.const_value(r[1])
            return lambda fp: val
        if k == 'enumval':
            val = r[1].decl.values[r[2]]
            return lambda fp: val
        lay = self.rt.layout(self.T(e.ty))
        buf = bytearray(lay.size)
        TAG.pack_into(buf, 0, r[2])
        val = bytes(buf)
        return lambda fp: val

    def e_ToSlice(self, e):
        n = self.T(e.expr.ty).elem.n
        p = self.expr(e.expr)
        return lambda fp: SLICE.pack(p(fp), n)

    def e_Range(self, e):
        bv = self.expr(e.base)
        lo = self.expr(e.lo) if e.lo is not None else (lambda fp: 0)
        hi = self.expr(e.hi) if e.hi is not None else None
        es = self.size(self.T(e.ty).elem)
        pos = e.pos

        def rng(fp):
            p, n = SLICE.unpack(bv(fp))
            a = lo(fp)
            b = n if hi is None else hi(fp)
            if a > b or b > n:
                panic(f'range {a}..{b} out of bounds for length {n}', pos)
            return SLICE.pack(p + a * es, b - a)
        return rng

    def e_Coerce(self, e):
        lay = self.rt.layout(self.T(e.ty))
        _, ft, off = lay.variants[1][1][0]
        enc = self.rt.encoder(self.T(ft))
        inner = self.expr(e.expr)
        size = lay.size

        def some(fp):
            buf = bytearray(size)
            buf[0] = 1
            enc(buf, off, inner(fp))
            return bytes(buf)
        return some

    def e_Field(self, e):
        pl = self.place(e)
        if pl is not None:
            return self.load_place(pl, e.ty)
        if e.kind == 'len':
            n = self.T(e.base.ty).n
            bv = self.expr(e.base)
            if isinstance(e.base, A.Path):
                return lambda fp: n
            return lambda fp: (bv(fp), n)[1]
        if e.kind == 'plen':
            n = self.T(e.base.ty).elem.n
            bv = self.expr(e.base)
            return lambda fp: (bv(fp), n)[1]
        bv = self.expr(e.base)
        off = self.rt.layout(self.T(e.base.ty)).offs[e.name]
        dec = self.rt.decoder(self.T(e.ty))
        return lambda fp: dec(bv(fp), off)

    def e_Index(self, e):
        pl = self.place(e)
        if pl is not None:
            return self.load_place(pl, e.ty)
        bv = self.expr(e.base)
        iv = self.expr(e.index)
        n = self.T(e.base.ty).n
        es = self.size(e.ty)
        dec = self.rt.decoder(self.T(e.ty))
        pos = e.pos

        def ridx(fp):
            b = bv(fp)
            i = iv(fp)
            if i >= n:
                panic(f'index {i} out of bounds for length {n}', pos)
            return dec(b, i * es)
        return ridx

    def e_Deref(self, e):
        return self.load_place(self.place(e), e.ty)

    def e_AddrOf(self, e):
        pl = self.place(e.expr)
        assert pl is not None
        return pl

    def e_Unary(self, e):
        f = self.expr(e.expr)
        if e.op == 'not':
            return lambda fp: not f(fp)
        t = self.T(e.ty)
        if t.kind == 'float':
            return lambda fp: -f(fp)
        lo, hi, pos = t.lo, t.hi, e.pos

        def neg(fp):
            r = -f(fp)
            if r < lo or r > hi:
                panic('integer overflow', pos)
            return r
        return neg

    def e_Binary(self, e):
        op = e.op
        pos = e.pos
        if op in ('and', 'or'):
            l, r = self.expr(e.lhs), self.expr(e.rhs)
            if op == 'and':
                return lambda fp: l(fp) and r(fp)
            return lambda fp: l(fp) or r(fp)
        if op in ('==', '!=') and e.nullcmp:
            x = self.expr(e.rhs if isinstance(e.lhs, A.NullLit) else e.lhs)
            if op == '==':
                return lambda fp: TAG.unpack_from(x(fp), 0)[0] == 0
            return lambda fp: TAG.unpack_from(x(fp), 0)[0] != 0
        l, r = self.expr(e.lhs), self.expr(e.rhs)
        if op == '==':
            return lambda fp: l(fp) == r(fp)
        if op == '!=':
            return lambda fp: l(fp) != r(fp)
        if op == '<':
            return lambda fp: l(fp) < r(fp)
        if op == '<=':
            return lambda fp: l(fp) <= r(fp)
        if op == '>':
            return lambda fp: l(fp) > r(fp)
        if op == '>=':
            return lambda fp: l(fp) >= r(fp)
        t = self.T(e.ty)
        if isinstance(t, Ptr):
            es = self.rt.layout(t.elem).size
            return lambda fp: l(fp) + r(fp) * es
        if t.kind == 'float':
            return self.float_op(op, l, r, t.name == 'f32')
        if op in ('&', '|', '^', '<<', '>>'):
            return self.bit_op(op, l, r, t, pos)
        return self.int_op(op, l, r, t.lo, t.hi, pos)

    def bit_op(self, op, l, r, t, pos):
        if op == '&':
            return lambda fp: l(fp) & r(fp)
        if op == '|':
            return lambda fp: l(fp) | r(fp)
        if op == '^':
            return lambda fp: l(fp) ^ r(fp)
        bits = t.bits
        wrap = self.wrapper(t)

        def count(fp):
            n = r(fp)
            if n < 0 or n >= bits:
                panic(f'shift count {n} out of range for a {bits}-bit integer', pos)
            return n
        if op == '<<':
            return lambda fp: wrap(l(fp) << count(fp))
        return lambda fp: l(fp) >> count(fp)

    @staticmethod
    def int_op(op, l, r, lo, hi, pos):
        if op == '+':
            def add(fp):
                v = l(fp) + r(fp)
                if v < lo or v > hi:
                    panic('integer overflow', pos)
                return v
            return add
        if op == '-':
            def sub(fp):
                v = l(fp) - r(fp)
                if v < lo or v > hi:
                    panic('integer overflow', pos)
                return v
            return sub
        if op == '*':
            def mul(fp):
                v = l(fp) * r(fp)
                if v < lo or v > hi:
                    panic('integer overflow', pos)
                return v
            return mul
        if op == '/':
            def div(fp):
                a, b = l(fp), r(fp)
                if b == 0:
                    panic('division by zero', pos)
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                if q < lo or q > hi:
                    panic('integer overflow', pos)
                return q
            return div

        def rem(fp):
            a, b = l(fp), r(fp)
            if b == 0:
                panic('division by zero', pos)
            m = abs(a) % abs(b)
            return -m if a < 0 else m
        return rem

    @staticmethod
    def float_op(op, l, r, is32):
        def fdiv(a, b):
            if b == 0:
                if a == 0 or a != a:
                    return math.nan
                return math.copysign(math.inf, a) * math.copysign(1.0, b)
            return a / b

        def fmod(a, b):
            if b == 0:
                return math.nan
            return math.fmod(a, b)
        fn = {'+': lambda a, b: a + b, '-': lambda a, b: a - b, '*': lambda a, b: a * b,
              '/': fdiv, '%': fmod}[op]
        if is32:
            return lambda fp: f32r(fn(l(fp), r(fp)))
        return lambda fp: fn(l(fp), r(fp))

    def e_Braced(self, e):
        rt = self.rt
        if hasattr(e, 'lit'):
            return self.literal(e)
        args = tuple((name, self.expr(a)) for name, _, a in e.args)
        if e.call[0] == 'static':
            target = rt.get_callable(e.call[1], [self.T(t) for t in e.call[2]])
            if e.bind:
                def bind(fp):
                    return rt.add_callable(Closure(target, {n: f(fp) for n, f in args}))
                return bind
            tcall = target.call

            def call(fp):
                return tcall({n: f(fp) for n, f in args})
            return call
        cv = self.expr(e.callee)
        callables = rt.callables
        if e.bind:
            def dbind(fp):
                target = callables[cv(fp)]
                return rt.add_callable(Closure(target, {n: f(fp) for n, f in args}))
            return dbind

        def dcall(fp):
            target = callables[cv(fp)]
            return target.call({n: f(fp) for n, f in args})
        return dcall

    def literal(self, e):
        rt = self.rt
        t = self.T(e.ty)
        lay = rt.layout(t)
        if e.lit[0] == 'struct':
            offs = {n: (ft, o) for n, ft, o in lay.fields}
            tag = None
        else:
            vi = e.lit[2]
            offs = {n: (ft, o) for n, ft, o in lay.variants[vi][1]}
            tag = vi
        items = tuple((offs[n][1], rt.encoder(offs[n][0]), self.expr(a)) for n, _, a in e.args)
        size = lay.size

        def lit(fp):
            buf = bytearray(size)
            if tag is not None:
                TAG.pack_into(buf, 0, tag)
            for off, enc, f in items:
                enc(buf, off, f(fp))
            return bytes(buf)
        return lit

    def e_ArrayLit(self, e):
        t = self.T(e.ty)
        es = self.rt.layout(t.elem).size
        enc = self.rt.encoder(t.elem)
        fs = tuple(self.expr(x) for x in e.elems)
        size = es * len(fs)

        def arr(fp):
            buf = bytearray(size)
            for i, f in enumerate(fs):
                enc(buf, i * es, f(fp))
            return bytes(buf)
        return arr

    def e_ArrayRep(self, e):
        t = self.T(e.ty)
        es = self.rt.layout(t.elem).size
        enc = self.rt.encoder(t.elem)
        f = self.expr(e.elem)
        n = t.n

        def rep(fp):
            buf = bytearray(es)
            enc(buf, 0, f(fp))
            return bytes(buf) * n
        return rep

    def e_Checked(self, e):
        return self.expr(e.inner)

    def e_Builtin(self, e):
        n = e.name
        pos = e.pos
        if n == 'fmt':
            return self.expr(e.fmt)
        if n in ('size_of', 'align_of'):
            lay = self.rt.layout(self.T(e.targ_t))
            v = lay.size if n == 'size_of' else lay.align
            return lambda fp: v
        if n == 'panic':
            msg = e.args[0].val.decode('ascii', 'backslashreplace') if e.args else '@panic()'

            def tr(fp):
                panic(msg, pos)
            return tr
        if n in ('addr', 'cast'):
            return self.expr(e.args[0])
        if n == 'slice':
            p, c = self.expr(e.args[0]), self.expr(e.args[1])
            return lambda fp: SLICE.pack(p(fp), c(fp))
        if n == 'as':
            src, dst = self.T(e.args[0].ty), self.T(e.targ_t)
            f = self.expr(e.args[0])
            if isinstance(dst, EnumT):
                ok, msg = frozenset(dst.decl.values), f'@as: no variant of {tstr(dst)} has this value'

                def i2e(fp):
                    v = f(fp)
                    if v not in ok:
                        panic(msg, pos)
                    return v
                return i2e
            if isinstance(src, EnumT):
                src = src.decl.base_t
            if dst.kind == 'float':
                if dst.name == 'f32':
                    return lambda fp: f32r(float(f(fp)))
                return lambda fp: float(f(fp))
            lo, hi = dst.lo, dst.hi
            if src.kind == 'float':
                def f2i(fp):
                    v = f(fp)
                    if v != v or v in (math.inf, -math.inf):
                        panic(f'@as: {v} is not representable in {dst.name}', pos)
                    i = int(v)
                    if i < lo or i > hi:
                        panic(f'@as: {v} is not representable in {dst.name}', pos)
                    return i
                return f2i

            def i2i(fp):
                v = f(fp)
                if v < lo or v > hi:
                    panic(f'@as: {v} is not representable in {dst.name}', pos)
                return v
            return i2i
        if n == 'trunc':
            wrap = self.wrapper(self.T(e.targ_t))
            f = self.expr(e.args[0])
            return lambda fp: wrap(f(fp))
        wrap = self.wrapper(self.T(e.ty))
        l, r = self.expr(e.args[0]), self.expr(e.args[1])
        if n == 'wrap_add':
            return lambda fp: wrap(l(fp) + r(fp))
        if n == 'wrap_sub':
            return lambda fp: wrap(l(fp) - r(fp))
        return lambda fp: wrap(l(fp) * r(fp))

    @staticmethod
    def wrapper(t):
        bits = t.bits
        mask = (1 << bits) - 1
        if t.signed:
            half = 1 << (bits - 1)
            full = 1 << bits

            def ws(v):
                v &= mask
                return v - full if v >= half else v
            return ws
        return lambda v: v & mask
