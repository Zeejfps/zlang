"""AST node definitions. The checker annotates nodes in place (ty, ref, call, ...)."""


class Node:
    pos = None

    def __repr__(self):
        fields = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items()
                           if k != 'pos' and not k.startswith('_'))
        return f'{type(self).__name__}({fields})'


# ---- declarations ----

class CtxField(Node):
    def __init__(self, name, mut, texpr, pos):
        self.name, self.mut, self.texpr, self.pos = name, mut, texpr, pos


class FnDecl(Node):
    def __init__(self, name, tparams, fields, ret, body, pos):
        self.name, self.tparams, self.fields, self.ret, self.body, self.pos = \
            name, tparams, fields, ret, body, pos


class StructDecl(Node):
    def __init__(self, name, tparams, fields, pos):
        # fields: list of (name, texpr, pos)
        self.name, self.tparams, self.fields, self.pos = name, tparams, fields, pos


class Variant(Node):
    def __init__(self, name, fields, pos):
        # fields: list of (name, texpr, pos), or None for no payload
        self.name, self.fields, self.pos = name, fields, pos


class UnionDecl(Node):
    def __init__(self, name, tparams, variants, pos):
        self.name, self.tparams, self.variants, self.pos = name, tparams, variants, pos


class EnumDecl(Node):
    def __init__(self, name, base, variants, pos):
        # base: the type expression after `:`; variants: list of (name, value expr or None, pos)
        self.name, self.base, self.variants, self.pos = name, base, variants, pos
        self.tparams = []


class TypeDecl(Node):
    def __init__(self, name, tparams, texpr, pos):
        self.name, self.tparams, self.texpr, self.pos = name, tparams, texpr, pos


class ConstDecl(Node):
    def __init__(self, name, texpr, expr, pos):
        self.name, self.texpr, self.expr, self.pos = name, texpr, expr, pos


class NamespaceDecl(Node):
    def __init__(self, name, decls, pos):
        self.name, self.decls, self.pos = name, decls, pos


# ---- type expressions ----

class TSeg(Node):
    def __init__(self, name, targs, pos):
        self.name, self.targs, self.pos = name, targs, pos


class TPath(Node):
    def __init__(self, segs, pos):
        self.segs, self.pos = segs, pos


class TPtr(Node):
    def __init__(self, elem, mut, pos):
        self.elem, self.mut, self.pos = elem, mut, pos


class TSlice(Node):
    def __init__(self, elem, mut, pos):
        self.elem, self.mut, self.pos = elem, mut, pos


class TOpt(Node):
    def __init__(self, elem, pos):
        self.elem, self.pos = elem, pos


class TArr(Node):
    def __init__(self, n, elem, pos):
        self.n, self.elem, self.pos = n, elem, pos


class TFn(Node):
    def __init__(self, fields, ret, bound, pos):
        self.fields, self.ret, self.bound, self.pos = fields, ret, bound, pos


# ---- statements ----

class Block(Node):
    def __init__(self, stmts, pos):
        self.stmts, self.pos = stmts, pos


class Let(Node):
    def __init__(self, name, mut, texpr, init, pos):
        self.name, self.mut, self.texpr, self.init, self.pos = name, mut, texpr, init, pos


class LetElse(Node):
    """`let variant{ binders } = init else variant{ binders } { els }`. The else pattern is optional
    (els_variant is None without one); binders are as in Arm."""

    def __init__(self, variant, binders, init, els_variant, els_binders, els, pos):
        self.variant, self.binders, self.init, self.pos = variant, binders, init, pos
        self.els_variant, self.els_binders, self.els = els_variant, els_binders, els


class Assign(Node):
    def __init__(self, lhs, rhs, pos):
        self.lhs, self.rhs, self.pos = lhs, rhs, pos


class If(Node):
    def __init__(self, cond, then, els, pos):
        self.cond, self.then, self.els, self.pos = cond, then, els, pos


class While(Node):
    def __init__(self, cond, body, pos, label=None):
        self.cond, self.body, self.pos, self.label = cond, body, pos, label
        self.label_id = None      # set by the checker if a jump from an inner loop targets it


class Arm(Node):
    def __init__(self, pats, body, pos):
        # pats: the `|`-separated patterns, as (variant, binders, pos); empty for `else`.
        # binders: list of (field, amp, pos, local), where local is the name the field is bound
        # to: the field's own name unless renamed
        self.pats, self.body, self.pos = pats, body, pos


class Match(Node):
    def __init__(self, scrut, arms, pos):
        self.scrut, self.arms, self.pos = scrut, arms, pos


class Return(Node):
    def __init__(self, expr, pos):
        self.expr, self.pos = expr, pos


class Break(Node):
    def __init__(self, pos, label=None):
        self.pos, self.label = pos, label
        self.target = None        # set by the checker: the While it leaves, if not the innermost


class Continue(Node):
    def __init__(self, pos, label=None):
        self.pos, self.label = pos, label
        self.target = None        # as for Break


class Defer(Node):
    """`defer stmt` or `defer { ... }`: body runs when the enclosing block exits."""

    def __init__(self, body, pos):
        self.body, self.pos = body, pos


class ExprStmt(Node):
    """A call statement, or `_ = expr` (discard) that evaluates any expression and drops it."""

    def __init__(self, expr, pos, discard=False):
        self.expr, self.pos, self.discard = expr, pos, discard


# ---- expressions ----

class IntLit(Node):
    def __init__(self, val, pos):
        self.val, self.pos = val, pos


class FloatLit(Node):
    def __init__(self, val, pos):
        self.val, self.pos = val, pos


class StrLit(Node):
    """`"..."`: a `[N]u8` array value."""

    def __init__(self, val, pos):
        self.val, self.pos = val, pos


class BoolLit(Node):
    def __init__(self, val, pos):
        self.val, self.pos = val, pos


class NullLit(Node):
    def __init__(self, pos):
        self.pos = pos


class Seg(Node):
    def __init__(self, name, targs, pos):
        self.name, self.targs, self.pos = name, targs, pos


class Path(Node):
    def __init__(self, segs, pos):
        self.segs, self.pos = segs, pos

    def text(self):
        return '::'.join(s.name for s in self.segs)


class Field(Node):
    def __init__(self, base, name, pos):
        self.base, self.name, self.pos = base, name, pos
        self.narrow = None     # set by the checker: the ?T type of a narrowed field


class Deref(Node):
    def __init__(self, base, pos):
        self.base, self.pos = base, pos


class Index(Node):
    def __init__(self, base, index, pos):
        self.base, self.index, self.pos = base, index, pos


class Range(Node):
    """`base[lo..hi]`; lo and hi may be None. The checker makes base a slice."""

    def __init__(self, base, lo, hi, pos):
        self.base, self.lo, self.hi, self.pos = base, lo, hi, pos


class Item(Node):
    def __init__(self, name, expr, pos):
        self.name, self.expr, self.pos = name, expr, pos


class Braced(Node):
    """`callee{ items }`: a call, bind, struct literal or variant construction."""

    def __init__(self, callee, items, forward, bind, pos):
        self.callee, self.items, self.forward, self.bind, self.pos = \
            callee, items, forward, bind, pos


class Unary(Node):
    def __init__(self, op, expr, pos):
        self.op, self.expr, self.pos = op, expr, pos


class AddrOf(Node):
    def __init__(self, expr, pos):
        self.expr, self.pos = expr, pos


class Binary(Node):
    def __init__(self, op, lhs, rhs, pos):
        self.op, self.lhs, self.rhs, self.pos = op, lhs, rhs, pos


class ArrayLit(Node):
    def __init__(self, elems, pos):
        self.elems, self.pos = elems, pos


class ArrayRep(Node):
    def __init__(self, elem, count, pos):
        self.elem, self.count, self.pos = elem, count, pos


class Builtin(Node):
    def __init__(self, name, targ, args, pos):
        self.name, self.targ, self.args, self.pos = name, targ, args, pos


class Coerce(Node):
    """Inserted by the checker: implicit T -> ?T conversion."""

    def __init__(self, expr, ty, pos):
        self.expr, self.ty, self.pos = expr, ty, pos


class ToSlice(Node):
    """Inserted by the checker: implicit *[N]T -> []T conversion."""

    def __init__(self, expr, ty, pos):
        self.expr, self.ty, self.pos = expr, ty, pos
