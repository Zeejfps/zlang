"""Name resolution, type checking and the static rules of the spec.

Generic bodies are checked once, with their type parameters as opaque TParams.
The checker annotates the AST in place; the compiler reads those annotations.
"""

from . import ast as A
from .lexer import CompileError
from .parser import parse_type
from .types import (
    Prim, PRIMS, I32, USIZE, F64, BOOL, U8, Ptr, Arr, Opt, StructT, UnionT, FnT, Cap,
    VOID, NULL, TParam, TVar, prune, subst, tstr, is_int, is_float, is_num, unify,
    fn_accepts, widens, contains_bound_fn, free_vars, struct_fields, variants_of, qualname,
)


class Namespace:
    def __init__(self, name, parent):
        self.name, self.parent = name, parent
        self.paths = {}
        self.values = {}


class NativeFn:
    """A runtime-provided function, declared into a std namespace.

    Field and return types are ctxlang type source, resolved in that namespace.
    """

    def __init__(self, path, name, fields, ret, impl):
        self.path, self.name = path, name
        self.field_src = fields    # [(name, mut, type source)]
        self.ret_src = ret         # type source or None
        self.tparams, self.tparam_objs = [], []
        self.impl = impl
        self.pos = None


class VarInfo:
    """A local, context field, match binding or narrowed view of one of those."""

    def __init__(self, name, ty, kind, mutable, pos):
        self.name, self.ty, self.kind, self.mutable, self.pos = name, ty, kind, mutable, pos
        self.indirect = False     # the slot holds a pointer to the place (mut field, &binding)
        self.narrow_of = None     # for kind == 'narrow'
        self.tracked = False      # declared without a value: definite-assignment tracked
        self.depth = 0
        self.loop_depth = 0
        self.held = set()         # places held by a &fn local (§3.1.3)
        self.derived = set()      # locals whose addresses this value may hold (§14)

    def root(self):
        v = self
        while v.narrow_of is not None:
            v = v.narrow_of
        return v

    def __repr__(self):
        return f'VarInfo({self.name})'


class State:
    __slots__ = ('defs', 'maybe', 'dead')

    def __init__(self, defs, maybe, dead):
        self.defs, self.maybe, self.dead = defs, maybe, dead


def has_zero(t):
    t = prune(t)
    if isinstance(t, (Prim, Opt)):
        return True
    if isinstance(t, Arr):
        return has_zero(t.elem)
    if isinstance(t, StructT):
        return all(has_zero(ft) for _, ft in struct_fields(t))
    return False


def contains_ptr(t, seen=None):
    t = prune(t)
    if isinstance(t, (Ptr, TParam)):
        return True
    if isinstance(t, (Opt, Arr)):
        return contains_ptr(t.elem, seen)
    if isinstance(t, (StructT, UnionT)):
        seen = seen or set()
        if id(t.decl) in seen:
            return False
        seen = seen | {id(t.decl)}
        if isinstance(t, StructT):
            return any(contains_ptr(ft, seen) for _, ft in struct_fields(t))
        return any(contains_ptr(ft, seen) for _, fs in variants_of(t) if fs for _, ft in fs)
    return False


def overlap(p, q):
    if p[0] is not q[0]:
        return False
    return all(a == b for a, b in zip(p[1], q[1]))


def place_str(p):
    s = p[0].name
    for st in p[1]:
        s += '.' + st[1] if st[0] == 'f' else '[_]'
    return s


# Children to visit when scanning an arm body for forbidden accesses.
CHILDREN = {
    A.Block: ('stmts',), A.Let: ('init',), A.Assign: ('lhs', 'rhs'),
    A.If: ('cond', 'then', 'els'), A.While: ('cond', 'body'), A.Match: ('scrut', 'arms'),
    A.Arm: ('body',), A.Return: ('expr',), A.ExprStmt: ('expr',), A.Unary: ('expr',),
    A.AddrOf: ('expr',), A.Binary: ('lhs', 'rhs'), A.ArrayLit: ('elems',),
    A.ArrayRep: ('elem',), A.Builtin: ('args',), A.Coerce: ('expr',),
}


class Checker:
    def __init__(self, decls, std_decls=(), natives=()):
        self.decls, self.std_decls, self.natives = decls, std_decls, natives
        self.universe = Namespace(None, None)
        for name, t in PRIMS.items():
            self.universe.paths[name] = t
        self.universe.paths['Io'] = Cap('Io')
        # User code sees std names unqualified, and its own declarations shadow them.
        self.std = Namespace(None, self.universe)
        self.root = Namespace(None, self.std)
        self.fns, self.structs, self.unions, self.aliases, self.consts = [], [], [], [], []
        self.alias_stack = []
        self.const_stack = []
        self.main = None
        self.gvars = None

    # ---------------------------------------------------------------- errors

    @staticmethod
    def err(msg, pos):
        raise CompileError(msg, pos)

    # ---------------------------------------------------------------- program

    def check(self):
        self.collect(self.std_decls, self.std)
        self.collect(self.decls, self.root)
        for nf in self.natives:
            ns = self.std
            for part in nf.path:
                ns = ns.paths.get(part)
                if not isinstance(ns, Namespace):
                    raise CompileError(f"native `{'::'.join(nf.path)}::{nf.name}` has no std namespace")
            nf.ns = ns
            self.add_name(ns.values, nf.name, nf, None)
        for d in self.structs + self.unions + self.fns:
            d.tparam_objs = [TParam(n) for n in d.tparams]
            if len(set(d.tparams)) != len(d.tparams):
                self.err(f'duplicate generic parameter in `{d.name}`', d.pos)
        for d in self.structs:
            self.resolve_struct(d)
        for d in self.unions:
            self.resolve_union(d)
        for d in self.aliases:
            if not d.tparams:
                self.decl_type(d, [], d.pos, partial=False, allow_bound=True)
        for d in self.consts:
            d.cty = self.rtype(d.texpr, d.ns, {})
        for d in self.fns:
            self.resolve_sig(d)
        for nf in self.natives:
            nf.sig_fields = [(n, m, self.rtype(parse_type(src), nf.ns, {}, allow_bound=not m))
                             for n, m, src in nf.field_src]
            nf.ret_t = self.rtype(parse_type(nf.ret_src), nf.ns, {}) if nf.ret_src else VOID
        for d in self.consts:
            self.check_const(d)
        for d in self.fns:
            self.check_fn(d)
        self.check_main()

    def collect(self, decls, ns):
        for d in decls:
            d.ns = ns
            if isinstance(d, A.NamespaceDecl):
                child = Namespace(d.name, ns)
                self.add_name(ns.paths, d.name, child, d.pos)
                self.collect(d.decls, child)
            elif isinstance(d, (A.FnDecl, A.ConstDecl)):
                self.add_name(ns.values, d.name, d, d.pos)
                (self.fns if isinstance(d, A.FnDecl) else self.consts).append(d)
            else:
                self.add_name(ns.paths, d.name, d, d.pos)
                if isinstance(d, A.StructDecl):
                    self.structs.append(d)
                elif isinstance(d, A.UnionDecl):
                    self.unions.append(d)
                else:
                    self.aliases.append(d)

    def add_name(self, table, name, d, pos):
        if name in table:
            self.err(f'`{name}` is already declared in this scope', pos)
        table[name] = d

    def check_main(self):
        m = self.root.values.get('main')
        if m is None or not isinstance(m, A.FnDecl):
            self.err('no `fn main` entry point', (1, 1))
        if m.tparams:
            self.err('`main` cannot be generic', m.pos)
        if m.ret_t is not VOID:
            self.err('`main` cannot return a value', m.pos)
        for name, mut, t in m.sig_fields:
            if not isinstance(prune(t), Cap):
                self.err(f'`main` context field `{name}` must have a capability type (Io), got {tstr(t)}', m.pos)
        self.main = m

    # ---------------------------------------------------------------- lookup

    def lookup_path_opt(self, ns, name):
        while ns is not None:
            if name in ns.paths:
                return ns.paths[name]
            ns = ns.parent
        return None

    def lookup_path(self, ns, name, pos):
        d = self.lookup_path_opt(ns, name)
        if d is None:
            self.err(f'unknown type or namespace `{name}`', pos)
        return d

    def lookup_value_global(self, ns, name):
        while ns is not None:
            if name in ns.values:
                return ns.values[name]
            ns = ns.parent
        return None

    # ---------------------------------------------------------------- types

    def rtype(self, te, ns, tps, allow_bound=False):
        if isinstance(te, A.TPtr):
            return Ptr(self.rtype(te.elem, ns, tps))
        if isinstance(te, A.TOpt):
            return Opt(self.rtype(te.elem, ns, tps))
        if isinstance(te, A.TArr):
            n = self.const_int(te.n, ns)
            if n < 0:
                self.err('array length must not be negative', te.pos)
            return Arr(n, self.rtype(te.elem, ns, tps))
        if isinstance(te, A.TFn):
            fields = []
            for f in te.fields:
                if any(f.name == g[0] for g in fields):
                    self.err(f'duplicate context field `{f.name}`', f.pos)
                fields.append((f.name, f.mut, self.rtype(f.texpr, ns, tps, allow_bound=not f.mut)))
            ret = self.rtype(te.ret, ns, tps) if te.ret else VOID
            if te.bound and not allow_bound:
                self.err('`&fn` can only be the type of a local or a read-only context field', te.pos)
            return FnT(fields, ret, te.bound)
        segs = te.segs
        s0 = segs[0]
        if len(segs) == 1 and s0.name in tps:
            if s0.targs is not None:
                self.err(f'generic parameter `{s0.name}` takes no type arguments', s0.pos)
            return tps[s0.name]
        d = self.lookup_path(ns, s0.name, s0.pos)
        for prev, s in zip(segs, segs[1:]):
            if prev.targs is not None or not isinstance(d, Namespace):
                self.err(f'`{prev.name}` is not a namespace', prev.pos)
            if s.name not in d.paths:
                self.err(f'no type or namespace `{s.name}` in `{prev.name}`', s.pos)
            d = d.paths[s.name]
        last = segs[-1]
        args = [self.rtype(a, ns, tps) for a in last.targs] if last.targs is not None else None
        return self.decl_type(d, args, last.pos, partial=False, allow_bound=allow_bound)

    def decl_type(self, d, args, pos, partial, allow_bound=False):
        if isinstance(d, (Prim, Cap)):
            if args:
                self.err(f'`{tstr(d)}` takes no type arguments', pos)
            return d
        if isinstance(d, Namespace):
            self.err(f'namespace `{d.name}` used as a type', pos)
        n = len(d.tparams)
        args = list(args or [])
        if len(args) > n or (len(args) < n and not partial):
            self.err(f'`{d.name}` expects {n} type argument(s), got {len(args)}', pos)
        fresh = []
        while len(args) < n:
            v = TVar('any')
            fresh.append((v, d.tparams[len(args)]))
            args.append(v)
        if isinstance(d, A.StructDecl):
            t = StructT(d, args)
        elif isinstance(d, A.UnionDecl):
            t = UnionT(d, args)
        else:
            if d in self.alias_stack:
                self.err(f'type alias `{d.name}` refers to itself', pos)
            self.alias_stack.append(d)
            t = self.rtype(d.texpr, d.ns, dict(zip(d.tparams, args)), allow_bound)
            self.alias_stack.pop()
        if fresh and self.gvars is not None:
            for v, pname in fresh:
                self.gvars.append((v, f'type parameter `{pname}` of `{d.name}`', pos))
        return t

    def resolve_struct(self, d):
        tps = dict(zip(d.tparams, d.tparam_objs))
        seen = set()
        d.ftypes = []
        for name, te, pos in d.fields:
            if name in seen:
                self.err(f'duplicate field `{name}`', pos)
            seen.add(name)
            d.ftypes.append((name, self.rtype(te, d.ns, tps)))

    def resolve_union(self, d):
        tps = dict(zip(d.tparams, d.tparam_objs))
        seen = set()
        d.vtypes = []
        for v in d.variants:
            if v.name in seen:
                self.err(f'duplicate variant `{v.name}`', v.pos)
            seen.add(v.name)
            if v.fields is None:
                d.vtypes.append((v.name, None))
                continue
            fs, fseen = [], set()
            for name, te, pos in v.fields:
                if name in fseen:
                    self.err(f'duplicate field `{name}`', pos)
                fseen.add(name)
                fs.append((name, self.rtype(te, d.ns, tps)))
            d.vtypes.append((v.name, fs))

    def resolve_sig(self, d):
        tps = dict(zip(d.tparams, d.tparam_objs))
        fields = []
        for f in d.fields:
            if any(f.name == g[0] for g in fields):
                self.err(f'duplicate context field `{f.name}`', f.pos)
            fields.append((f.name, f.mut, self.rtype(f.texpr, d.ns, tps, allow_bound=not f.mut)))
        d.sig_fields = fields
        d.ret_t = self.rtype(d.ret, d.ns, tps) if d.ret else VOID

    def const_int(self, e, ns):
        """Evaluate a compile-time integer (array lengths)."""
        if isinstance(e, A.IntLit):
            return e.val
        if isinstance(e, A.Binary) and e.op in ('+', '-', '*', '/', '%'):
            a, b = self.const_int(e.lhs, ns), self.const_int(e.rhs, ns)
            if e.op in ('/', '%') and b == 0:
                self.err('division by zero in constant', e.pos)
            return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b,
                    '/': lambda: int(a / b), '%': lambda: a - b * int(a / b)}[e.op]()
        if isinstance(e, A.Path):
            d = None
            if len(e.segs) == 1:
                d = self.lookup_value_global(ns, e.segs[0].name)
            else:
                p = self.lookup_path(ns, e.segs[0].name, e.pos)
                for s in e.segs[1:-1]:
                    p = p.paths.get(s.name) if isinstance(p, Namespace) else None
                if isinstance(p, Namespace):
                    d = p.values.get(e.segs[-1].name)
            if isinstance(d, A.ConstDecl):
                if d in self.const_stack:
                    self.err(f'const `{d.name}` refers to itself', e.pos)
                self.const_stack.append(d)
                v = self.const_int(d.expr, d.ns)
                self.const_stack.pop()
                return v
        self.err('array length must be a compile-time integer constant', e.pos)

    # ---------------------------------------------------------------- bodies

    def begin_body(self, ns, tps, ret):
        self.ns, self.tps, self.ret = ns, tps, ret
        self.scopes = [{}]
        self.depth = 0
        self.loop_depth = 0
        self.loops = []
        self.st = State(set(), set(), False)
        self.lits = []
        self.gvars = []

    def check_fn(self, d):
        self.fn = d
        self.begin_body(d.ns, dict(zip(d.tparams, d.tparam_objs)), d.ret_t)
        d.ctx_vars = []
        for (name, mut, t), f in zip(d.sig_fields, d.fields):
            v = VarInfo(name, t, 'ctx', mut, f.pos)
            v.indirect = mut
            self.scopes[0][name] = v
            d.ctx_vars.append(v)
        self.block(d.body)
        if d.ret_t is not VOID and not self.st.dead:
            self.err(f'`{d.name}` must end every path in `return` or `@trap()`', d.pos)
        self.finish()

    def check_const(self, d):
        self.fn = None
        self.begin_body(d.ns, {}, VOID)
        d.expr = self.expect(d.expr, d.cty)
        self.finish()
        self.const_ok(d.expr)

    def const_ok(self, e):
        ok = (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit, A.NullLit, A.Binary, A.Unary, A.ArrayLit,
              A.ArrayRep, A.Coerce, A.Path, A.Builtin, A.Braced)
        if not isinstance(e, ok):
            self.err('a const must be computable at compile time', e.pos)
        if isinstance(e, A.Path) and e.ref[0] not in ('const', 'variant'):
            self.err('a const may only refer to other consts', e.pos)
        if isinstance(e, A.Builtin) and e.name not in ('size_of', 'align_of'):
            self.err(f'@{e.name} is not allowed in a const', e.pos)
        if isinstance(e, A.Braced):
            if not hasattr(e, 'lit'):
                self.err('a const cannot call a function', e.pos)
            for _, _, a in e.args:
                self.const_ok(a)
        for attr in CHILDREN.get(type(e), ()):
            c = getattr(e, attr)
            for x in (c if isinstance(c, list) else [c]):
                if isinstance(x, A.Node):
                    self.const_ok(x)

    def finish(self):
        for lit in self.lits:
            t = prune(lit.ty)
            if isinstance(t, TVar):
                unify(t, I32 if t.kind == 'int' else F64)
        for lit in self.lits:
            t = prune(lit.ty)
            if isinstance(lit, A.IntLit) and not (t.lo <= lit.val <= t.hi):
                self.err(f'literal {lit.val} does not fit in {t.name}', lit.pos)
        for v, desc, pos in self.gvars:
            if free_vars(v, []):
                self.err(f'cannot infer {desc}', pos)
            if contains_bound_fn(v):
                self.err(f'{desc} cannot be a `&fn` type', pos)
        self.gvars = None

    # ---- scopes & flow state

    def push(self):
        self.scopes.append({})
        self.depth += 1

    def pop(self):
        self.scopes.pop()
        self.depth -= 1

    def declare(self, v):
        scope = self.scopes[-1]
        if v.name in scope:
            self.err(f'`{v.name}` is already declared in this scope', v.pos)
        v.depth = self.depth
        v.loop_depth = self.loop_depth
        scope[v.name] = v

    def lookup_local(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def save(self):
        return State(set(self.st.defs), set(self.st.maybe), self.st.dead)

    def merge(self, states):
        live = [s for s in states if not s.dead]
        maybe = set().union(*(s.maybe for s in states))
        if not live:
            return State(set().union(*(s.defs for s in states)), maybe, True)
        defs = set(live[0].defs)
        for s in live[1:]:
            defs &= s.defs
        return State(defs, maybe, False)

    def check_read(self, v, pos):
        v = v.root() if v.kind == 'narrow' else v
        if v.tracked and v not in self.st.defs and not self.st.dead:
            self.err(f'`{v.name}` may be read before it is assigned', pos)

    # ---- statements

    def block(self, b, extra=()):
        self.push()
        for v in extra:
            self.declare(v)
        for s in b.stmts:
            self.stmt(s)
        self.pop()

    def stmt(self, s):
        m = getattr(self, 's_' + type(s).__name__)
        m(s)

    def s_Let(self, s):
        if s.texpr is not None:
            t = self.rtype(s.texpr, self.ns, self.tps, allow_bound=True)
            if s.init is not None:
                s.init = self.expect(s.init, t)
        else:
            t = self.value_type(s.init)
        v = VarInfo(s.name, t, 'local', s.mut, s.pos)
        if s.init is None:
            if not (s.mut and has_zero(t)):
                v.tracked = True
        else:
            v.derived = self.derives(s.init)
            v.held = set(self.held_of(s.init))
        self.declare(v)
        if v.held:
            self.check_bound_scope(v, v.held, s.pos)
        s.var = v

    def value_type(self, e):
        t = self.expr(e)
        if t is NULL:
            self.err('cannot infer the type of `null` here; add a type', e.pos)
        if t is VOID:
            self.err('expression has no value', e.pos)
        return t

    def s_Assign(self, s):
        lhs = s.lhs
        v = None
        if isinstance(lhs, A.Path) and len(lhs.segs) == 1 and lhs.segs[0].targs is None:
            v = self.lookup_local(lhs.segs[0].name)
        if v is not None:
            lhs.ref = ('var', v)
            lhs.ty = v.ty
            if not v.mutable and not v.tracked:
                self.err(f'cannot assign to `{v.name}`: it is read-only', lhs.pos)
            s.rhs = self.expect(s.rhs, v.ty)
            if v.tracked and not v.mutable:
                if v in self.st.maybe and not self.st.dead:
                    self.err(f'`{v.name}` may be assigned more than once', s.pos)
            self.st.defs.add(v)
            self.st.maybe.add(v)
            self.check_store((v, ()), False, s.rhs, s.pos)
            t = prune(v.ty)
            if isinstance(t, FnT) and t.bound:
                held = self.held_of(s.rhs)
                v.held |= set(held)
                self.check_bound_scope(v, held, s.pos)
            return
        lt = self.expr(lhs)
        self.check_mutable(lhs)
        s.rhs = self.expect(s.rhs, lt)
        pp = self.place_path(lhs)
        self.check_store(pp, pp is None, s.rhs, s.pos)

    def check_store(self, pp, through_deref, rhs, pos):
        ds = self.derives(rhs)
        if not ds:
            return
        name = next(iter(ds)).name
        if through_deref:
            self.err(f'cannot store the address of local `{name}` through a pointer', pos)
        root = pp[0]
        if root.indirect:
            self.err(f'cannot store the address of local `{name}` in `{root.name}`, which belongs to the caller', pos)
        for L in ds:
            if root.depth < L.depth:
                self.err(f'`{root.name}` outlives local `{L.name}` whose address it would hold', pos)
        root.derived |= ds

    def check_bound_scope(self, v, held, pos):
        for root, _ in held:
            if v.depth < root.depth:
                self.err(f'bound function stored in `{v.name}` holds `{root.name}`, '
                         f'which does not live as long', pos)

    def s_If(self, s):
        self.check_if(s, None, False)

    def e_If(self, e, exp):
        return self.check_if(e, exp, True)

    def check_if(self, s, exp, value, may_leave=False):
        s.cond = self.expect(s.cond, BOOL)
        nar = self.narrowing(s.cond)
        s0 = self.save()
        body = self.value_block if value else self.branch_block
        t1 = body(s.then, [nar[1]] if nar and nar[0] == '!=' else (), exp)
        s1 = self.st
        self.st = State(set(s0.defs), set(s0.maybe), s0.dead)
        t2 = None
        if s.els is not None:
            t2 = body(s.els, [nar[1]] if nar and nar[0] == '==' else (), exp)
        self.st = self.merge([s1, self.st])
        if value:
            return self.join(s, [(s.then, t1), (s.els, t2)], exp, may_leave)

    def branch_block(self, b, extra, exp):
        self.block(b, extra)

    def value_block(self, b, extra, exp):
        """A branch of an `if` or `match` expression: its last statement gives its value.

        A trailing `if` with an `else`, or `match`, is itself the value, unless every one of its
        branches leaves. Returns the value's type, or None if the branch never finishes (it
        leaves through `return`, `break`, `continue` or `@trap()`).
        """
        entry_dead = self.st.dead
        self.push()
        for v in extra:
            self.declare(v)
        stmts = b.stmts
        last = stmts[-1] if stmts else None
        nested = isinstance(last, A.Match) or (isinstance(last, A.If) and last.els is not None)
        valued = nested or (isinstance(last, A.ExprStmt)
                            and not (isinstance(last.expr, A.Builtin) and last.expr.name == 'trap'))
        for st in (stmts[:-1] if valued else stmts):
            self.stmt(st)
        b.result = None
        t = None
        if nested:
            check = self.check_match if isinstance(last, A.Match) else self.check_if
            t = last.ty = check(last, exp, True, may_leave=True)
            b.result = last
        elif valued:
            e = last.expr
            t = self.expr(e, exp)
            if t is VOID:
                self.err('this branch has no value: its last expression returns nothing', e.pos)
            b.result = e
        if b.result is not None and t is not None:
            e = b.result
            for L in self.derives(e):
                if L.depth == self.depth:
                    self.err(f'the value of this branch holds the address of local `{L.name}`, '
                             f'which ends with the branch', e.pos)
            for root, _ in self.held_of(e):
                if root.depth == self.depth:
                    self.err(f'the value of this branch holds `{root.name}`, which ends with the branch',
                             e.pos)
        elif not self.st.dead:
            self.err('this branch must end in a value, or leave with `return`, `break`, '
                     '`continue` or `@trap()`', b.pos)
        self.pop()
        if self.st.dead and not entry_dead:
            return None
        return t

    def join(self, e, branches, exp, may_leave=False):
        """The type of an `if` or `match` expression, from its (block, type) branches.

        With an expected type that every branch converts to, that type. Otherwise the first
        branch type that every other converts to (widening, `null` and `T` to `?T`).
        """
        live = [(b, t) for b, t in branches if t is not None]
        if not live:
            if may_leave:
                return None
            self.err('no branch of this expression produces a value; use a statement instead', e.pos)
        types = [t for _, t in live]
        target = None
        if exp is not None and all(self.coerce(t, exp) is not None for t in types):
            target = exp
        else:
            has_null = any(prune(t) is NULL for t in types)
            for cand in types:
                c = prune(cand)
                if c is NULL:
                    continue
                if has_null and not isinstance(c, Opt):
                    c = Opt(c)
                if all(self.coerce(t, c) is not None for t in types):
                    target = c
                    break
            if target is None:
                if all(prune(t) is NULL for t in types):
                    return NULL
                a = types[0]
                b = next(t for t in types[1:] if self.coerce(t, a) is None)
                self.err(f'branches have different types: {tstr(a)} and {tstr(b)}', e.pos)
        for b, t in live:
            b.result = self.coerce_node(b.result, t, target)
        return target

    def narrowing(self, cond):
        if not (isinstance(cond, A.Binary) and getattr(cond, 'nullcmp', False)):
            return None
        x = cond.rhs if isinstance(cond.lhs, A.NullLit) else cond.lhs
        if not (isinstance(x, A.Path) and x.ref[0] == 'var'):
            return None
        v = x.ref[1]
        if v.mutable:
            return None
        t = prune(v.ty)
        if not isinstance(t, Opt):
            return None
        nv = VarInfo(v.name, t.elem, 'narrow', False, x.pos)
        nv.narrow_of = v
        nv.derived = v.derived
        return (cond.op, nv)

    def s_While(self, s):
        s.cond = self.expect(s.cond, BOOL)
        s0 = self.save()
        breaks, conts = [], []
        self.loops.append((breaks, conts))
        self.loop_depth += 1
        self.block(s.body)
        self.loop_depth -= 1
        self.loops.pop()
        # A read-only `let x: T` declared outside the loop must not be assigned on a path that
        # can repeat the loop (the end of the body or a `continue`).
        for back in [self.st] + conts:
            if back.dead:
                continue
            for v in back.maybe - s0.maybe:
                if v.tracked and not v.mutable and v.loop_depth <= self.loop_depth:
                    self.err(f'`{v.name}` may be assigned more than once: it is assigned in a loop '
                             f'that can repeat; declare it with `let mut`', s.pos)
        maybe = s0.maybe | self.st.maybe
        for b in breaks + conts:
            maybe |= b.maybe
        if isinstance(s.cond, A.BoolLit) and s.cond.val:
            # `while (true)` exits only through a break; without one it ends the path.
            after = self.merge(breaks) if breaks else State(set(s0.defs), set(), True)
            self.st = State(after.defs, maybe, s0.dead or after.dead)
        else:
            self.st = State(s0.defs, maybe, s0.dead)

    def s_Break(self, s):
        if not self.loops:
            self.err('`break` outside a loop', s.pos)
        self.loops[-1][0].append(self.save())
        self.st.dead = True

    def s_Continue(self, s):
        if not self.loops:
            self.err('`continue` outside a loop', s.pos)
        self.loops[-1][1].append(self.save())
        self.st.dead = True

    def s_Match(self, s):
        self.check_match(s, None, False)

    def e_Match(self, e, exp):
        return self.check_match(e, exp, True)

    def check_match(self, s, exp, value, may_leave=False):
        st = prune(self.expr(s.scrut))
        through = isinstance(st, Ptr)
        ut = prune(st.elem) if through else st
        if not isinstance(ut, (UnionT, Opt)):
            self.err(f'match needs a union or optional value, got {tstr(st)}', s.scrut.pos)
        s.through, s.utype = through, ut
        vs = variants_of(ut)
        names = [n for n, _ in vs]
        forb = None
        if isinstance(s.scrut, A.AddrOf):
            forb = self.place_path(s.scrut.expr)
        scrut_derived = set() if through else self.derives(s.scrut)
        seen, results, has_else = [], [], False
        branches = []
        body = self.value_block if value else self.branch_block
        s0 = self.save()
        for i, arm in enumerate(s.arms):
            arm.bvars = []
            if arm.variant is None:
                if i != len(s.arms) - 1:
                    self.err('`else` must be the last arm', arm.pos)
                if len(seen) == len(names):
                    self.err('`else` is unreachable: every variant is already listed', arm.pos)
                has_else = True
                arm.vindex = None
            else:
                if arm.variant not in names:
                    self.err(f'{tstr(ut)} has no variant `{arm.variant}`', arm.pos)
                if arm.variant in seen:
                    self.err(f'variant `{arm.variant}` appears in more than one arm', arm.pos)
                seen.append(arm.variant)
                arm.vindex = names.index(arm.variant)
                fields = vs[arm.vindex][1]
                if arm.binders and fields is None:
                    self.err(f'variant `{arm.variant}` has no payload', arm.pos)
                fnames = [f for f, _ in fields or []]
                bseen = set()
                for bname, amp, bpos in arm.binders:
                    if bname not in fnames:
                        self.err(f'variant `{arm.variant}` has no field `{bname}`', bpos)
                    if bname in bseen:
                        self.err(f'`{bname}` is bound twice', bpos)
                    bseen.add(bname)
                    if amp and not through:
                        self.err(f'`&{bname}` needs a pointer scrutinee', bpos)
                    fi = fnames.index(bname)
                    v = VarInfo(bname, fields[fi][1], 'bind', amp, bpos)
                    v.indirect = amp
                    v.derived = scrut_derived
                    arm.bvars.append((v, fi))
            self.st = State(set(s0.defs), set(s0.maybe), s0.dead)
            branches.append((arm.body, body(arm.body, [v for v, _ in arm.bvars], exp)))
            results.append(self.st)
            if forb is not None:
                self.scan_forbidden(arm.body, forb, [v.name for v, _ in arm.bvars])
        if not has_else and len(seen) < len(names):
            missing = [n for n in names if n not in seen]
            self.err(f"match isn't exhaustive: missing {', '.join(missing)}", s.pos)
        self.st = self.merge(results)
        if value:
            return self.join(s, branches, exp, may_leave)

    def s_Return(self, s):
        if s.expr is None:
            if self.ret is not VOID:
                self.err('`return` needs a value here', s.pos)
        else:
            if self.ret is VOID:
                self.err('this function has no return type', s.pos)
            s.expr = self.expect(s.expr, self.ret)
            ds = self.derives(s.expr)
            if ds:
                self.err(f'returned value holds the address of local `{next(iter(ds)).name}`', s.pos)
        self.st.dead = True

    def s_ExprStmt(self, s):
        e = s.expr
        if isinstance(e, A.Braced):
            self.expr(e)
            if not hasattr(e, 'call'):
                self.err('an expression statement must be a call', e.pos)
        elif isinstance(e, A.Builtin):
            self.expr(e)
            if e.name == 'trap':
                self.st.dead = True
        else:
            self.err('an expression statement must be a call', e.pos)

    # ---- forbidden accesses inside `match (&p)` arms (§8.6)

    def access_path(self, e):
        if isinstance(e, A.Path):
            r = getattr(e, 'ref', None)
            if r and r[0] == 'var':
                return (r[1].root(), ())
            return None
        if isinstance(e, A.Field):
            if e.kind in ('pfield', 'plen'):
                return self.access_path(e.base)
            ap = self.access_path(e.base)
            if ap and e.kind == 'field':
                return (ap[0], ap[1] + (('f', e.name),))
            return ap
        if isinstance(e, A.Index):
            ap = self.access_path(e.base)
            if ap and e.kind == 'arr':
                return (ap[0], ap[1] + (('i',),))
            return ap
        if isinstance(e, A.Deref):
            return self.access_path(e.base)
        return None

    def scan_forbidden(self, node, forb, bnames):
        if node is None:
            return
        if isinstance(node, list):
            for x in node:
                self.scan_forbidden(x, forb, bnames)
            return
        if isinstance(node, (A.Path, A.Field, A.Index, A.Deref)):
            ap = self.access_path(node)
            if ap and overlap(ap, forb):
                via = ', '.join(f'`{b}`' for b in bnames) or 'the arm bindings'
                self.err(f'{place_str(forb)} overlaps the match scrutinee; access it only through {via}',
                         node.pos)
            n = node
            while isinstance(n, (A.Field, A.Index, A.Deref)):
                if isinstance(n, A.Index):
                    self.scan_forbidden(n.index, forb, bnames)
                n = n.base
            if not isinstance(n, A.Path):
                self.scan_forbidden(n, forb, bnames)
            return
        if isinstance(node, A.Braced):
            if not isinstance(node.callee, A.Path) or node.callee.ref[0] == 'var':
                self.scan_forbidden(node.callee, forb, bnames)
            for _, _, a in node.args:
                self.scan_forbidden(a, forb, bnames)
            return
        for attr in CHILDREN.get(type(node), ()):
            self.scan_forbidden(getattr(node, attr), forb, bnames)

    # ---------------------------------------------------------------- expressions

    def expr(self, e, exp=None):
        t = getattr(self, 'e_' + type(e).__name__)(e, exp)
        e.ty = t
        return t

    def expect(self, e, t):
        at = self.expr(e, t)
        return self.coerce_node(e, at, t)

    def coerce_node(self, e, at, t):
        if at is VOID:
            self.err('expression has no value', e.pos)
        conv = self.coerce(at, t)
        if conv is None:
            self.err(self.mismatch(at, t), e.pos)
        if conv == 'some':
            c = A.Coerce(e, t, e.pos)
            return c
        if conv == 'null':
            e.ty = t
        return e

    def coerce(self, a, e):
        a, e = prune(a), prune(e)
        if a is NULL:
            return 'null' if isinstance(e, Opt) else None
        if isinstance(e, Opt):
            if isinstance(a, Opt) or (isinstance(a, TVar) and a.kind == 'any'):
                return 'id' if unify(a, e) else None
            return 'some' if unify(a, e.elem) or widens(a, e.elem) else None
        if isinstance(e, FnT) and isinstance(a, FnT):
            if a.bound and not e.bound:
                return None
            return 'id' if fn_accepts(a, e) else None
        return 'id' if unify(a, e) or widens(a, e) else None

    def mismatch(self, a, e):
        a, e = prune(a), prune(e)
        if isinstance(a, FnT) and isinstance(e, FnT) and not (a.bound and not e.bound):
            ef = {n: m for n, m, _ in e.fields}
            for n, m, _ in a.fields:
                if n not in ef:
                    return f"function needs `{'mut ' if m else ''}{n}`, which {tstr(e)} doesn't provide"
        return f'expected {tstr(e)}, got {tstr(a)}'

    # ---- literals

    def e_IntLit(self, e, exp):
        self.lits.append(e)
        return TVar('int')

    def e_FloatLit(self, e, exp):
        self.lits.append(e)
        return TVar('float')

    def e_StrLit(self, e, exp):
        return Arr(len(e.val), U8)

    def e_BoolLit(self, e, exp):
        return BOOL

    def e_NullLit(self, e, exp):
        return NULL

    def e_Coerce(self, e, exp):
        return e.ty

    def e_ArrayLit(self, e, exp):
        pe = prune(exp) if exp is not None else None
        et = pe.elem if isinstance(pe, Arr) else None
        if not e.elems:
            if et is None:
                self.err('an empty array literal needs a known type', e.pos)
            return Arr(0, et)
        new = []
        for x in e.elems:
            if et is None:
                et = self.value_type(x)
                new.append(x)
            else:
                new.append(self.expect(x, et))
        e.elems = new
        return Arr(len(new), et)

    def e_ArrayRep(self, e, exp):
        n = self.const_int(e.count, self.ns)
        pe = prune(exp) if exp is not None else None
        if isinstance(pe, Arr):
            e.elem = self.expect(e.elem, pe.elem)
            et = pe.elem
        else:
            et = self.value_type(e.elem)
        e.n = n
        return Arr(n, et)

    # ---- names

    def targs_of(self, seg):
        if seg.targs is None:
            return None
        return [self.rtype(a, self.ns, self.tps) for a in seg.targs]

    def resolve_path(self, e):
        segs = e.segs
        s0 = segs[0]
        if len(segs) == 1:
            v = self.lookup_local(s0.name)
            if v is not None:
                if s0.targs is not None:
                    self.err(f'`{s0.name}` is not generic', s0.pos)
                return ('var', v)
            g = self.lookup_value_global(self.ns, s0.name)
            if g is not None:
                return self.value_ref(g, s0)
            p = self.lookup_path_opt(self.ns, s0.name)
            if p is not None:
                return ('path', p, s0)
            self.err(f'unknown name `{s0.name}`', s0.pos)
        d = self.lookup_path(self.ns, s0.name, s0.pos)
        for i in range(1, len(segs)):
            s, prev, last = segs[i], segs[i - 1], i == len(segs) - 1
            if isinstance(d, Namespace):
                if prev.targs is not None:
                    self.err(f'namespace `{prev.name}` takes no type arguments', prev.pos)
                if last and s.name in d.values:
                    return self.value_ref(d.values[s.name], s)
                if s.name in d.paths:
                    d = d.paths[s.name]
                    continue
                self.err(f'`{s.name}` not found in namespace `{prev.name}`', s.pos)
            t = prune(self.decl_type(d, self.targs_of(prev), prev.pos, partial=True))
            if isinstance(t, UnionT) and last:
                if s.targs is not None:
                    self.err('a variant takes no type arguments', s.pos)
                names = [n for n, _ in variants_of(t)]
                if s.name not in names:
                    self.err(f'{tstr(t)} has no variant `{s.name}`', s.pos)
                return ('variant', t, names.index(s.name))
            self.err(f'`{prev.name}` has no member `{s.name}`', s.pos)
        return ('path', d, segs[-1])

    def value_ref(self, g, seg):
        if isinstance(g, A.ConstDecl):
            if seg.targs is not None:
                self.err(f'const `{g.name}` takes no type arguments', seg.pos)
            return ('const', g)
        explicit = self.targs_of(seg) or []
        n = len(g.tparams)
        if len(explicit) > n:
            self.err(f'`{g.name}` expects at most {n} type argument(s), got {len(explicit)}', seg.pos)
        targs = list(explicit)
        while len(targs) < n:
            v = TVar('any')
            self.gvars.append((v, f'type parameter `{g.tparams[len(targs)]}` of `{g.name}`', seg.pos))
            targs.append(v)
        return ('fn', g, targs)

    def fn_type(self, d, targs):
        m = dict(zip(d.tparam_objs, targs))
        return FnT([(n, mu, subst(t, m)) for n, mu, t in d.sig_fields], subst(d.ret_t, m), False)

    def e_Path(self, e, exp):
        r = self.resolve_path(e)
        e.ref = r
        k = r[0]
        if k == 'var':
            self.check_read(r[1], e.pos)
            return r[1].ty
        if k == 'fn':
            return self.fn_type(r[1], r[2])
        if k == 'const':
            return r[1].cty
        if k == 'variant':
            ut, vi = r[1], r[2]
            name, fields = variants_of(ut)[vi]
            if fields is not None:
                self.err(f'variant `{name}` has a payload; construct it with `{e.text()}{{ ... }}`', e.pos)
            if exp is not None:
                pe = prune(exp)
                if isinstance(pe, UnionT) and pe.decl is ut.decl:
                    unify(ut, pe)
            return ut
        self.err(f'`{e.text()}` is a type, not a value', e.pos)

    # ---- braced: calls, binds, literals

    def e_Braced(self, e, exp):
        c = e.callee
        if isinstance(c, A.Path):
            r = self.resolve_path(c)
            c.ref = r
            if r[0] == 'path':
                return self.struct_lit(e, r[1], r[2], exp)
            if r[0] == 'variant':
                return self.variant_lit(e, r[1], r[2], exp)
            if r[0] == 'fn':
                c.ty = self.fn_type(r[1], r[2])
                e.call = ('static', r[1], r[2])
                return self.call_args(e, c.ty, c.text())
            if r[0] == 'var':
                self.check_read(r[1], c.pos)
                c.ty = r[1].ty
            else:
                c.ty = r[1].cty
            ct = c.ty
            name = c.text()
        else:
            ct = self.expr(c)
            name = 'function'
        ft = prune(ct)
        if not isinstance(ft, FnT):
            self.err(f'`{name}` has type {tstr(ct)} and cannot be called', c.pos)
        e.call = ('dyn',)
        return self.call_args(e, ft, name)

    def supplied(self, e, fmap, what):
        given = {}
        for it in e.items:
            if it.name not in fmap:
                self.err(f'{what} has no field `{it.name}`', it.pos)
            if it.name in given:
                self.err(f'`{it.name}` is supplied more than once', it.pos)
            given[it.name] = it
        return given

    def call_args(self, e, ft, name):
        fmap = {n: (m, t) for n, m, t in ft.fields}
        given = self.supplied(e, fmap, f'`{name}`')
        args = [self.check_arg(it.name, *fmap[it.name], it.expr) for it in e.items]
        if e.forward:
            for n, m, t in ft.fields:
                if n in given:
                    continue
                if self.lookup_local(n) is None:
                    self.err(f'`..` cannot supply `{n}`: no local or context field named `{n}`', e.pos)
                p = A.Path([A.Seg(n, None, e.pos)], e.pos)
                a = A.AddrOf(p, e.pos) if m else p
                args.append(self.check_arg(n, m, t, a))
                given[n] = a
        missing = [f for f in ft.fields if f[0] not in given]
        if missing and not e.bind:
            names = ', '.join(f'`{f[0]}`' for f in missing)
            self.err(f'call to `{name}` is missing {names}', e.pos)
        e.args = args
        refs = self.check_exclusive(args, e.pos)
        if e.bind:
            e.held = [p for p, _ in refs]
            return FnT(missing, ft.ret, True)
        return ft.ret

    def check_arg(self, name, mut, t, a):
        if mut:
            if isinstance(a, A.AddrOf):
                at = self.expr(a)
                self.check_mutable(a.expr)
                a = self.coerce_node(a, at, Ptr(t))
            else:
                a = self.expect(a, Ptr(t))
        else:
            a = self.expect(a, t)
        return (name, mut, a)

    def check_exclusive(self, args, pos):
        refs = []
        for name, mut, a in args:
            if mut and isinstance(a, A.AddrOf):
                pp = self.place_path(a.expr)
                if pp:
                    refs.append((pp, None))
            elif not mut:
                holder = a.segs[0].name if isinstance(a, A.Path) else name
                for pp in self.held_of(a):
                    refs.append((pp, holder))
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                (p, hp), (q, hq) = refs[i], refs[j]
                if overlap(p, q):
                    if hp is None and hq is None:
                        self.err(f'two mut references to `{place_str(p)}` in one call', pos)
                    holder = hq or hp
                    self.err(f'`{place_str(p if hp is None else q)}` overlaps a place held by `{holder}`', pos)
        return refs

    def held_of(self, a):
        if isinstance(a, A.Path) and getattr(a, 'ref', None) and a.ref[0] == 'var':
            return a.ref[1].held
        if isinstance(a, A.Braced) and a.bind:
            return a.held
        if isinstance(a, (A.If, A.Match)):
            out = []
            for b in value_blocks(a):
                if getattr(b, 'result', None) is not None:
                    out += self.held_of(b.result)
            return out
        return ()

    def struct_lit(self, e, d, seg, exp):
        t = prune(self.decl_type(d, self.targs_of(seg), seg.pos, partial=True))
        if not isinstance(t, StructT):
            self.err(f'`{seg.name}` is not a struct', seg.pos)
        if exp is not None:
            pe = prune(exp)
            if isinstance(pe, StructT) and pe.decl is t.decl:
                unify(t, pe)
        return self.fields_lit(e, t, struct_fields(t), f'struct `{t.decl.name}`', ('struct', t))

    def variant_lit(self, e, ut, vi, exp):
        name, fields = variants_of(ut)[vi]
        if fields is None:
            self.err(f'variant `{name}` has no payload; write it without braces', e.pos)
        if exp is not None:
            pe = prune(exp)
            if isinstance(pe, UnionT) and pe.decl is ut.decl:
                unify(ut, pe)
        return self.fields_lit(e, ut, fields, f'variant `{name}`', ('variant', ut, vi))

    def fields_lit(self, e, t, fields, what, lit):
        if e.forward or e.bind:
            self.err(f"`{'..' if e.forward else '_'}` is not allowed in a literal", e.pos)
        fmap = {n: (False, ft) for n, ft in fields}
        given = self.supplied(e, fmap, what)
        missing = [n for n, _ in fields if n not in given]
        if missing:
            self.err(f"{what} is missing {', '.join(f'`{n}`' for n in missing)}", e.pos)
        e.args = [(it.name, False, self.expect(it.expr, fmap[it.name][1])) for it in e.items]
        e.lit = lit
        return t

    # ---- operators

    def e_Unary(self, e, exp):
        if e.op == 'not':
            e.expr = self.expect(e.expr, BOOL)
            return BOOL
        t = self.expr(e.expr, exp)
        if not is_num(t):
            self.err(f'unary `-` needs a number, got {tstr(t)}', e.pos)
        return t

    def e_AddrOf(self, e, exp):
        t = self.expr(e.expr)
        self.check_place(e.expr)
        return Ptr(t)

    def e_Binary(self, e, exp):
        op = e.op
        if op in ('and', 'or'):
            e.lhs = self.expect(e.lhs, BOOL)
            e.rhs = self.expect(e.rhs, BOOL)
            return BOOL
        if op in ('==', '!='):
            ln, rn = isinstance(e.lhs, A.NullLit), isinstance(e.rhs, A.NullLit)
            if ln or rn:
                if ln and rn:
                    self.err('cannot compare null with null', e.pos)
                x = e.rhs if ln else e.lhs
                xt = prune(self.expr(x))
                if not isinstance(xt, Opt):
                    self.err(f'only an optional can be compared with null, got {tstr(xt)}', e.pos)
                (e.lhs if ln else e.rhs).ty = xt
                e.nullcmp = True
                return BOOL
            e.nullcmp = False
            lt = self.expr(e.lhs)
            rt = self.expr(e.rhs, lt)
            t = self.operand_type(lt, rt)
            if t is None:
                self.err(f'cannot compare {tstr(lt)} with {tstr(rt)}', e.pos)
            if not (is_num(t) or t is BOOL or isinstance(t, Ptr)):
                self.err(f'{tstr(t)} has no built-in equality', e.pos)
            return BOOL
        if op in ('<', '<=', '>', '>='):
            lt = self.expr(e.lhs)
            rt = self.expr(e.rhs, lt)
            t = self.operand_type(lt, rt)
            if t is None:
                self.err(f'cannot compare {tstr(lt)} with {tstr(rt)}', e.pos)
            if not is_num(t):
                self.err(f'`{op}` needs numbers, got {tstr(t)}', e.pos)
            return BOOL
        lt = self.expr(e.lhs, exp)
        plt = prune(lt)
        if isinstance(plt, Ptr):
            if op != '+':
                self.err(f'`{op}` is not defined on pointers', e.pos)
            e.rhs = self.expect(e.rhs, USIZE)
            e.ptrarith = True
            return plt
        e.ptrarith = False
        rt = self.expr(e.rhs, lt)
        t = self.operand_type(lt, rt)
        if t is None:
            self.err(f'operands of `{op}` have incompatible types: {tstr(lt)} and {tstr(rt)}; '
                     f'convert one with @as', e.pos)
        if not is_num(t):
            self.err(f'`{op}` needs numbers, got {tstr(t)}', e.pos)
        return t

    @staticmethod
    def operand_type(lt, rt):
        """The common type of two operands: equal types, or the one the other widens to."""
        if unify(lt, rt):
            return prune(lt)
        if widens(rt, lt):
            return prune(lt)
        if widens(lt, rt):
            return prune(rt)
        return None

    # ---- postfix

    def e_Field(self, e, exp):
        bt = prune(self.expr(e.base))
        if isinstance(bt, Ptr):
            inner = prune(bt.elem)
            if isinstance(inner, StructT):
                e.kind = 'pfield'
                return self.field_type(inner, e)
            if isinstance(inner, Arr) and e.name == 'len':
                e.kind = 'plen'
                return USIZE
        elif isinstance(bt, StructT):
            e.kind = 'field'
            return self.field_type(bt, e)
        elif isinstance(bt, Arr) and e.name == 'len':
            e.kind = 'len'
            return USIZE
        elif isinstance(bt, TVar):
            self.err(f'the type of this expression must be known before `.{e.name}`', e.pos)
        self.err(f'{tstr(bt)} has no field `{e.name}`', e.pos)

    def field_type(self, st, e):
        for n, ft in struct_fields(st):
            if n == e.name:
                return ft
        self.err(f'{tstr(st)} has no field `{e.name}`', e.pos)

    def e_Deref(self, e, exp):
        bt = prune(self.expr(e.base))
        if not isinstance(bt, Ptr):
            self.err(f'`.*` needs a pointer, got {tstr(bt)}', e.pos)
        return bt.elem

    def e_Index(self, e, exp):
        bt = prune(self.expr(e.base))
        e.index = self.expect(e.index, USIZE)
        if isinstance(bt, Arr):
            e.kind = 'arr'
            return bt.elem
        if isinstance(bt, Ptr):
            inner = prune(bt.elem)
            if isinstance(inner, Arr):
                e.kind = 'parr'
                return inner.elem
            e.kind = 'ptr'
            return bt.elem
        self.err(f'cannot index {tstr(bt)}', e.pos)

    # ---- builtins

    def e_Builtin(self, e, exp):
        n, args = e.name, e.args     # the parser checked the name and the argument count
        if e.targ is not None:
            e.targ_t = self.rtype(e.targ, self.ns, self.tps)
        if n in ('size_of', 'align_of'):
            return USIZE
        if n == 'trap':
            return VOID
        if n == 'as':
            if not is_num(e.targ_t):
                self.err(f'@as needs a numeric target type, got {tstr(e.targ_t)}', e.pos)
            if not is_num(self.expr(args[0])):
                self.err('@as converts numbers only', args[0].pos)
            return e.targ_t
        if n == 'trunc':
            if not is_int(e.targ_t):
                self.err(f'@trunc needs an integer target type, got {tstr(e.targ_t)}', e.pos)
            if not is_int(self.expr(args[0])):
                self.err('@trunc converts integers only', args[0].pos)
            return e.targ_t
        if n == 'cast':
            if not isinstance(prune(e.targ_t), Ptr):
                self.err(f'@cast needs a pointer target type, got {tstr(e.targ_t)}', e.pos)
            if not isinstance(prune(self.expr(args[0])), Ptr):
                self.err('@cast needs a pointer argument', args[0].pos)
            return e.targ_t
        if n == 'addr':
            if not isinstance(prune(self.expr(args[0])), Ptr):
                self.err('@addr needs a pointer argument', args[0].pos)
            return USIZE
        lt = self.expr(args[0], exp)
        rt = self.expr(args[1], lt)
        if not unify(lt, rt) or not is_int(lt):
            self.err(f'@{n} needs two integers of the same type', e.pos)
        return lt

    # ---------------------------------------------------------------- places

    def check_place(self, e):
        if isinstance(e, A.Path):
            k = e.ref[0]
            if k == 'var':
                return
            if k == 'const':
                self.err(f'`{e.text()}` is a const, not a place', e.pos)
            self.err(f'`{e.text()}` is not a place', e.pos)
        if isinstance(e, A.Field):
            if e.kind == 'field':
                return self.check_place(e.base)
            if e.kind == 'pfield':
                return
            self.err('`.len` is not a place', e.pos)
        if isinstance(e, A.Index):
            if e.kind == 'arr':
                return self.check_place(e.base)
            return
        if isinstance(e, A.Deref):
            return
        self.err('expression is not a place', e.pos)

    def check_mutable(self, e):
        self.check_place(e)
        if isinstance(e, A.Path):
            v = e.ref[1]
            if not v.mutable:
                self.err(f'`{v.name}` is not a mutable place', e.pos)
        elif isinstance(e, A.Field) and e.kind == 'field':
            self.check_mutable(e.base)
        elif isinstance(e, A.Index) and e.kind == 'arr':
            self.check_mutable(e.base)

    def place_path(self, e):
        """(root VarInfo, steps) for a place that doesn't go through a deref (§3.1.1)."""
        if isinstance(e, A.Path):
            r = getattr(e, 'ref', None)
            if r and r[0] == 'var':
                return (r[1].root(), ())
            return None
        if isinstance(e, A.Field) and e.kind == 'field':
            p = self.place_path(e.base)
            return p and (p[0], p[1] + (('f', e.name),))
        if isinstance(e, A.Index) and e.kind == 'arr':
            p = self.place_path(e.base)
            return p and (p[0], p[1] + (('i',),))
        return None

    # ---------------------------------------------------------------- escape analysis (§14)

    def derives(self, e):
        if not contains_ptr(e.ty):
            return set()
        return self._derives(e)

    def _derives(self, e):
        if isinstance(e, A.AddrOf):
            p = self.place_path(e.expr)
            if p is not None:
                root = p[0]
                return set() if root.indirect else {root}
            b = e.expr
            while isinstance(b, (A.Field, A.Index)) and getattr(b, 'kind', None) in ('field', 'arr'):
                b = b.base
            if isinstance(b, (A.Field, A.Index, A.Deref)):
                return self._derives(b.base)
            return set()
        if isinstance(e, A.Path):
            r = getattr(e, 'ref', None)
            if r and r[0] == 'var':
                return set(r[1].derived)
            return set()
        if isinstance(e, A.Coerce):
            return self._derives(e.expr)
        if isinstance(e, A.Braced):
            if hasattr(e, 'lit'):
                out = set()
                for _, _, a in e.args:
                    out |= self.derives(a)
                return out
            if e.bind:
                return set()
            out = set()
            for _, mut, a in e.args:
                if not mut:
                    out |= self.derives(a)
            return out
        if isinstance(e, A.Binary) and getattr(e, 'ptrarith', False):
            return self._derives(e.lhs)
        if isinstance(e, A.Builtin) and e.name == 'cast':
            return self._derives(e.args[0])
        if isinstance(e, (A.Field, A.Index)) and e.kind in ('field', 'arr'):
            return self._derives(e.base)
        if isinstance(e, A.ArrayLit):
            out = set()
            for x in e.elems:
                out |= self.derives(x)
            return out
        if isinstance(e, A.ArrayRep):
            return self.derives(e.elem)
        if isinstance(e, (A.If, A.Match)):
            out = set()
            for b in value_blocks(e):
                if getattr(b, 'result', None) is not None:
                    out |= self.derives(b.result)
            return out
        return set()


def value_blocks(e):
    """The branch blocks of an `if` or `match` expression."""
    if isinstance(e, A.If):
        return [e.then, e.els]
    return [arm.body for arm in e.arms]


def check(decls, std_decls=(), natives=()):
    c = Checker(decls, std_decls, natives)
    c.check()
    return c
