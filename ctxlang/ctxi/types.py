"""Semantic types, unification and substitution."""

import itertools


class Type:
    def __repr__(self):
        return tstr(self)


class Prim(Type):
    def __init__(self, name, kind, bits, signed):
        self.name, self.kind, self.bits, self.signed = name, kind, bits, signed
        if kind == 'int':
            if signed:
                self.lo, self.hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
            else:
                self.lo, self.hi = 0, (1 << bits) - 1


PRIMS = {}
for _b in (8, 16, 32, 64):
    PRIMS[f'i{_b}'] = Prim(f'i{_b}', 'int', _b, True)
    PRIMS[f'u{_b}'] = Prim(f'u{_b}', 'int', _b, False)
PRIMS['usize'] = Prim('usize', 'int', 64, False)
PRIMS['f32'] = Prim('f32', 'float', 32, True)
PRIMS['f64'] = Prim('f64', 'float', 64, True)
PRIMS['bool'] = Prim('bool', 'bool', 8, False)
I32, USIZE, F64, BOOL, U8 = PRIMS['i32'], PRIMS['usize'], PRIMS['f64'], PRIMS['bool'], PRIMS['u8']


class Ptr(Type):
    def __init__(self, elem):
        self.elem = elem


class Arr(Type):
    def __init__(self, n, elem):
        self.n, self.elem = n, elem


class Opt(Type):
    def __init__(self, elem):
        self.elem = elem


class StructT(Type):
    def __init__(self, decl, args):
        self.decl, self.args = decl, tuple(args)


class UnionT(Type):
    def __init__(self, decl, args):
        self.decl, self.args = decl, tuple(args)


class FnT(Type):
    def __init__(self, fields, ret, bound):
        self.fields = tuple(fields)   # (name, mut, type)
        self.ret, self.bound = ret, bound


class Cap(Type):
    def __init__(self, name):
        self.name = name


class _Void(Type):
    pass


class _Null(Type):
    pass


VOID = _Void()
NULL = _Null()

_uid = itertools.count(1)


class TParam(Type):
    """A generic parameter, rigid inside the body that declares it."""

    def __init__(self, name):
        self.name, self.uid = name, next(_uid)


class TVar(Type):
    """An inference variable. kind: 'any' (generic arg), 'int' or 'float' (literal)."""

    def __init__(self, kind, hint=None):
        self.kind, self.ref, self.hint = kind, None, hint
        self.uid = next(_uid)


def prune(t):
    while isinstance(t, TVar) and t.ref is not None:
        t = t.ref
    return t


def zonk(t):
    t = prune(t)
    if isinstance(t, Ptr):
        return Ptr(zonk(t.elem))
    if isinstance(t, Opt):
        return Opt(zonk(t.elem))
    if isinstance(t, Arr):
        return Arr(t.n, zonk(t.elem))
    if isinstance(t, StructT):
        return StructT(t.decl, [zonk(a) for a in t.args])
    if isinstance(t, UnionT):
        return UnionT(t.decl, [zonk(a) for a in t.args])
    if isinstance(t, FnT):
        return FnT([(n, m, zonk(ft)) for n, m, ft in t.fields], zonk(t.ret), t.bound)
    return t


def subst(t, m):
    """Replace TParams per mapping m. Also prunes TVars."""
    if not m:
        return zonk(t)
    t = prune(t)
    if isinstance(t, TParam):
        return m.get(t, t)
    if isinstance(t, Ptr):
        return Ptr(subst(t.elem, m))
    if isinstance(t, Opt):
        return Opt(subst(t.elem, m))
    if isinstance(t, Arr):
        return Arr(t.n, subst(t.elem, m))
    if isinstance(t, StructT):
        return StructT(t.decl, [subst(a, m) for a in t.args])
    if isinstance(t, UnionT):
        return UnionT(t.decl, [subst(a, m) for a in t.args])
    if isinstance(t, FnT):
        return FnT([(n, mu, subst(ft, m)) for n, mu, ft in t.fields], subst(t.ret, m), t.bound)
    return t


def tstr(t):
    t = prune(t)
    if isinstance(t, Prim):
        return t.name
    if isinstance(t, Ptr):
        return '*' + tstr(t.elem)
    if isinstance(t, Opt):
        return '?' + tstr(t.elem)
    if isinstance(t, Arr):
        return f'[{t.n}]{tstr(t.elem)}'
    if isinstance(t, (StructT, UnionT)):
        name = qualname(t.decl)
        if t.args:
            return f"{name}({', '.join(tstr(a) for a in t.args)})"
        return name
    if isinstance(t, FnT):
        fs = ', '.join(f"{'mut ' if m else ''}{n}: {tstr(ft)}" for n, m, ft in t.fields)
        s = f"{'&' if t.bound else ''}fn{{ {fs} }}" if fs else f"{'&' if t.bound else ''}fn{{}}"
        if t.ret is not VOID:
            s += ' -> ' + tstr(t.ret)
        return s
    if isinstance(t, Cap):
        return t.name
    if t is VOID:
        return 'no value'
    if t is NULL:
        return 'null'
    if isinstance(t, TParam):
        return t.name
    if isinstance(t, TVar):
        if t.kind == 'int':
            return '{integer}'
        if t.kind == 'float':
            return '{float}'
        return '_'
    return '?'


def qualname(decl):
    parts = [decl.name]
    ns = getattr(decl, 'ns', None)
    while ns is not None and ns.name is not None:
        parts.append(ns.name)
        ns = ns.parent
    return '::'.join(reversed(parts))


def is_int(t):
    t = prune(t)
    return (isinstance(t, Prim) and t.kind == 'int') or (isinstance(t, TVar) and t.kind == 'int')


def is_float(t):
    t = prune(t)
    return (isinstance(t, Prim) and t.kind == 'float') or (isinstance(t, TVar) and t.kind == 'float')


def is_num(t):
    return is_int(t) or is_float(t)


def occurs(v, t):
    t = prune(t)
    if t is v:
        return True
    if isinstance(t, (Ptr, Opt, Arr)):
        return occurs(v, t.elem)
    if isinstance(t, (StructT, UnionT)):
        return any(occurs(v, a) for a in t.args)
    if isinstance(t, FnT):
        return occurs(v, t.ret) or any(occurs(v, ft) for _, _, ft in t.fields)
    return False


def _bind(v, t):
    if isinstance(t, TVar):
        if v.kind == 'any':
            v.ref = t
            return True
        if t.kind == 'any' or t.kind == v.kind:
            t.ref = v
            return True
        return False
    if v.kind == 'int' and not (isinstance(t, Prim) and t.kind == 'int'):
        return False
    if v.kind == 'float' and not (isinstance(t, Prim) and t.kind == 'float'):
        return False
    if occurs(v, t):
        return False
    v.ref = t
    return True


def unify(a, b):
    a, b = prune(a), prune(b)
    if a is b:
        return True
    if isinstance(a, TVar):
        return _bind(a, b)
    if isinstance(b, TVar):
        return _bind(b, a)
    if type(a) is not type(b):
        return False
    if isinstance(a, (Ptr, Opt)):
        return unify(a.elem, b.elem)
    if isinstance(a, Arr):
        return a.n == b.n and unify(a.elem, b.elem)
    if isinstance(a, (StructT, UnionT)):
        return a.decl is b.decl and all(unify(x, y) for x, y in zip(a.args, b.args))
    if isinstance(a, FnT):
        if a.bound != b.bound or len(a.fields) != len(b.fields):
            return False
        bf = {n: (m, t) for n, m, t in b.fields}
        for n, m, t in a.fields:
            if n not in bf or bf[n][0] != m or not unify(t, bf[n][1]):
                return False
        return unify(a.ret, b.ret)
    if isinstance(a, Cap):
        return a.name == b.name
    return False  # distinct Prims / TParams


def widens(a, b):
    """Does a convert implicitly to b? Only when every value of a is a value of b.

    Signed and unsigned integers widen to wider types of their own signedness, unsigned ones
    also to wider signed types. usize is assumed to be 32 to 64 bits: u8..u32 widen to it and
    it widens to u64. f32 widens to f64. Integers never convert to floats implicitly.
    """
    a, b = prune(a), prune(b)
    if not (isinstance(a, Prim) and isinstance(b, Prim)) or a is b:
        return False
    if a.kind == 'float' and b.kind == 'float':
        return a.bits < b.bits
    if a.kind != 'int' or b.kind != 'int':
        return False
    if a.name == 'usize':
        return b.name == 'u64'
    if b.name == 'usize':
        return not a.signed and a.bits <= 32
    if a.signed:
        return b.signed and b.bits > a.bits
    return b.bits > a.bits


def fn_accepts(g, s):
    """§5: can function g be used where s is expected (ignoring bound-ness)?"""
    sf = {n: (m, t) for n, m, t in s.fields}
    for n, m, t in g.fields:
        if n not in sf:
            return False
        sm, st = sf[n]
        if m and not sm:
            return False
        if sm != m:
            return False
        if not unify(t, st):
            return False
    return unify(g.ret, s.ret)


def contains_bound_fn(t):
    t = prune(t)
    if isinstance(t, FnT):
        return t.bound
    if isinstance(t, (Ptr, Opt, Arr)):
        return contains_bound_fn(t.elem)
    if isinstance(t, (StructT, UnionT)):
        return any(contains_bound_fn(a) for a in t.args)
    return False


def free_vars(t, acc):
    t = prune(t)
    if isinstance(t, TVar):
        acc.append(t)
    elif isinstance(t, (Ptr, Opt, Arr)):
        free_vars(t.elem, acc)
    elif isinstance(t, (StructT, UnionT)):
        for a in t.args:
            free_vars(a, acc)
    elif isinstance(t, FnT):
        free_vars(t.ret, acc)
        for _, _, ft in t.fields:
            free_vars(ft, acc)
    return acc


def struct_fields(t):
    """[(name, type)] for a StructT, with generic args substituted."""
    d = t.decl
    m = dict(zip(d.tparam_objs, t.args))
    return [(n, subst(ft, m)) for n, ft in d.ftypes]


def variants_of(t):
    """[(name, [(field, type)] or None)] for a UnionT or Opt."""
    t = prune(t)
    if isinstance(t, Opt):
        return [('null', None), ('some', [('value', t.elem)])]
    d = t.decl
    m = dict(zip(d.tparam_objs, t.args))
    return [(n, None if fs is None else [(fn, subst(ft, m)) for fn, ft in fs]) for n, fs in d.vtypes]


def tkey(t):
    """Hashable key for a concrete type."""
    t = prune(t)
    if isinstance(t, Prim):
        return t.name
    if isinstance(t, Ptr):
        return ('*', tkey(t.elem))
    if isinstance(t, Opt):
        return ('?', tkey(t.elem))
    if isinstance(t, Arr):
        return ('[]', t.n, tkey(t.elem))
    if isinstance(t, StructT):
        return ('s', id(t.decl), tuple(tkey(a) for a in t.args))
    if isinstance(t, UnionT):
        return ('u', id(t.decl), tuple(tkey(a) for a in t.args))
    if isinstance(t, FnT):
        return ('fn', t.bound, tuple(sorted((n, m, tkey(ft)) for n, m, ft in t.fields)), tkey(t.ret))
    if isinstance(t, Cap):
        return ('cap', t.name)
    if t is VOID:
        return 'void'
    raise TypeError(f'type is not concrete: {tstr(t)}')
