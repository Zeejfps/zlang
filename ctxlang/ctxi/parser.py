"""Recursive-descent parser for ctxlang."""

from .lexer import CompileError, lex
from . import ast as A

CMP_OPS = ('==', '!=', '<', '<=', '>', '>=')
# Binary operator levels between comparison and prefix, loosest first. All are left to right.
BIN_LEVELS = (('|',), ('^',), ('&',), ('<<', '>>'), ('+', '-'), ('*', '/', '%'))
# Every builtin's signature (spec §13): (type arguments, value arguments, usage).
# Type arguments always come first, so the name alone says how to parse each argument.
# A (min, max) pair of value arguments means the trailing ones are optional.
BUILTINS = {
    'size_of':  (1, 0, '@size_of(T)'),
    'align_of': (1, 0, '@align_of(T)'),
    'as':       (1, 1, '@as(T, x)'),
    'trunc':    (1, 1, '@trunc(T, x)'),
    'cast':     (1, 1, '@cast(*U, q)'),
    'addr':     (0, 1, '@addr(q)'),
    'wrap_add': (0, 2, '@wrap_add(a, b)'),
    'wrap_sub': (0, 2, '@wrap_sub(a, b)'),
    'wrap_mul': (0, 2, '@wrap_mul(a, b)'),
    'panic':     (0, (0, 1), '@panic() or @panic("reason")'),
}


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.in_cond = False    # parsing a condition or scrutinee, outside any brackets

    # ---- token helpers ----

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        tok = self.t[self.i]
        if tok.kind != 'eof':
            self.i += 1
        return tok

    def err(self, msg, tok=None):
        tok = tok or self.peek()
        raise CompileError(msg, tok.pos)

    def is_op(self, v, k=0):
        tok = self.peek(k)
        return tok.kind == 'op' and tok.val == v

    def is_kw(self, v, k=0):
        tok = self.peek(k)
        return tok.kind == 'kw' and tok.val == v

    def accept_op(self, v):
        if self.is_op(v):
            self.i += 1
            return True
        return False

    def expect_op(self, v):
        if not self.accept_op(v):
            self.err(f"expected '{v}', found {self.describe(self.peek())}")

    def accept_kw(self, v):
        if self.is_kw(v):
            self.i += 1
            return True
        return False

    def expect_kw(self, v):
        if not self.accept_kw(v):
            self.err(f"expected '{v}', found {self.describe(self.peek())}")

    def ident(self):
        tok = self.peek()
        if tok.kind != 'id':
            self.err(f'expected a name, found {self.describe(tok)}')
        self.i += 1
        return tok.val

    @staticmethod
    def describe(tok):
        if tok.kind == 'eof':
            return 'end of file'
        return f"'{tok.val}'"

    def skip_semis(self):
        while self.accept_op(';'):
            pass

    # ---- declarations ----

    def program(self):
        decls = []
        self.skip_semis()
        while self.peek().kind != 'eof':
            decls.append(self.decl())
            self.skip_semis()
        return decls

    def decl(self):
        tok = self.peek()
        if tok.kind == 'kw':
            if tok.val == 'fn':
                return self.fn_decl()
            if tok.val == 'struct':
                return self.struct_decl()
            if tok.val == 'union':
                return self.union_decl()
            if tok.val == 'type':
                return self.type_decl()
            if tok.val == 'const':
                return self.const_decl()
            if tok.val == 'namespace':
                return self.namespace_decl()
        self.err(f'expected a declaration, found {self.describe(tok)}')

    def tparams(self):
        if not self.is_op('('):
            return []
        self.next()
        names = [self.ident()]
        while self.accept_op(','):
            names.append(self.ident())
        self.expect_op(')')
        return names

    def ctx_fields(self):
        self.expect_op('{')
        fields = []
        while not self.is_op('}'):
            pos = self.peek().pos
            mut = self.accept_kw('mut')
            name = self.ident()
            self.expect_op(':')
            fields.append(A.CtxField(name, mut, self.type(), pos))
            if not self.accept_op(','):
                break
        self.expect_op('}')
        return fields

    def fn_decl(self):
        pos = self.next().pos
        name = self.ident()
        tps = self.tparams()
        fields = self.ctx_fields()
        ret = self.type() if self.accept_op('->') else None
        body = self.block()
        return A.FnDecl(name, tps, fields, ret, body, pos)

    def plain_fields(self):
        self.expect_op('{')
        fields = []
        while not self.is_op('}'):
            pos = self.peek().pos
            name = self.ident()
            self.expect_op(':')
            fields.append((name, self.type(), pos))
            if not self.accept_op(','):
                break
        self.expect_op('}')
        return fields

    def struct_decl(self):
        pos = self.next().pos
        name = self.ident()
        tps = self.tparams()
        return A.StructDecl(name, tps, self.plain_fields(), pos)

    def union_decl(self):
        pos = self.next().pos
        name = self.ident()
        tps = self.tparams()
        self.expect_op('{')
        variants = []
        while not self.is_op('}'):
            vpos = self.peek().pos
            vname = self.ident()
            fields = self.plain_fields() if self.is_op('{') else None
            variants.append(A.Variant(vname, fields, vpos))
            if not self.accept_op(','):
                break
        self.expect_op('}')
        return A.UnionDecl(name, tps, variants, pos)

    def type_decl(self):
        pos = self.next().pos
        name = self.ident()
        tps = self.tparams()
        self.expect_op('=')
        return A.TypeDecl(name, tps, self.type(), pos)

    def const_decl(self):
        pos = self.next().pos
        name = self.ident()
        self.expect_op(':')
        texpr = self.type()
        self.expect_op('=')
        return A.ConstDecl(name, texpr, self.expr(), pos)

    def namespace_decl(self):
        pos = self.next().pos
        name = self.ident()
        self.expect_op('{')
        decls = []
        self.skip_semis()
        while not self.is_op('}'):
            if self.peek().kind == 'eof':
                self.err("expected '}' to close namespace")
            decls.append(self.decl())
            self.skip_semis()
        self.expect_op('}')
        return A.NamespaceDecl(name, decls, pos)

    # ---- types ----

    def type(self):
        tok = self.peek()
        pos = tok.pos
        if self.accept_op('*'):
            return A.TPtr(self.type(), pos)
        if self.accept_op('?'):
            return A.TOpt(self.type(), pos)
        if self.accept_op('['):
            n = self.expr()
            self.expect_op(']')
            return A.TArr(n, self.type(), pos)
        if self.is_kw('fn') or (self.is_op('&') and self.is_kw('fn', 1)):
            bound = self.accept_op('&')
            self.next()
            fields = self.ctx_fields()
            ret = self.type() if self.accept_op('->') else None
            return A.TFn(fields, ret, bound, pos)
        if tok.kind == 'id':
            segs = [self.type_seg()]
            while self.accept_op('::'):
                segs.append(self.type_seg())
            return A.TPath(segs, pos)
        self.err(f'expected a type, found {self.describe(tok)}')

    def type_seg(self):
        pos = self.peek().pos
        name = self.ident()
        targs = None
        if self.is_op('(') and not self.peek().nl:
            targs = self.type_list()
        return A.TSeg(name, targs, pos)

    def type_list(self):
        self.expect_op('(')
        ts = []
        while not self.is_op(')'):
            ts.append(self.type())
            if not self.accept_op(','):
                break
        self.expect_op(')')
        return ts

    # ---- statements ----

    def block(self):
        pos = self.peek().pos
        self.expect_op('{')
        stmts = []
        self.skip_semis()
        while not self.is_op('}'):
            if self.peek().kind == 'eof':
                self.err("expected '}' to close block")
            stmts.append(self.stmt())
            tok = self.peek()
            if not (tok.nl or self.is_op(';') or self.is_op('}')):
                self.err(f'expected a newline or \';\' after statement, found {self.describe(tok)}')
            self.skip_semis()
        self.expect_op('}')
        return A.Block(stmts, pos)

    def stmt(self):
        tok = self.peek()
        pos = tok.pos
        if tok.kind == 'kw':
            if tok.val == 'let':
                self.next()
                mut = self.accept_kw('mut')
                if not mut and self.is_kw('null'):
                    return self.let_else(pos, *self.pattern())
                name = self.ident()
                if name == '_':
                    self.err('`_` is not a name: `_ = e` discards a value without declaring anything', tok)
                if not mut and self.is_op('{'):
                    return self.let_else(pos, name, self.binders())
                texpr = self.type() if self.accept_op(':') else None
                init = self.expr() if self.accept_op('=') else None
                if texpr is None and init is None:
                    self.err(f'`let {name}` needs a type or an initializer', tok)
                if init is not None and texpr is None and not mut and self.is_kw('else'):
                    return self.let_else_tail(pos, name, [], init)      # `let variant = e else`
                return A.Let(name, mut, texpr, init, pos)
            if tok.val == 'if':
                return self.if_stmt()
            if tok.val == 'while':
                self.next()
                cond = self.cond_expr()
                return A.While(cond, self.block(), pos)
            if tok.val == 'match':
                return self.match_stmt()
            if tok.val == 'break':
                self.next()
                return A.Break(pos)
            if tok.val == 'continue':
                self.next()
                return A.Continue(pos)
            if tok.val == 'defer':
                self.next()
                if self.is_op('{'):
                    return A.Defer(self.block(), pos)
                inner = self.stmt()
                if not isinstance(inner, (A.ExprStmt, A.Assign)):
                    self.err('`defer` takes a call, an assignment, `_ = e` or a block', tok)
                return A.Defer(A.Block([inner], inner.pos), pos)
            if tok.val == 'return':
                self.next()
                nxt = self.peek()
                if nxt.nl or self.is_op('}') or self.is_op(';'):
                    return A.Return(None, pos)
                return A.Return(self.expr(), pos)
        e = self.expr()
        if self.is_op('='):
            self.next()
            if isinstance(e, A.Path) and len(e.segs) == 1 and e.segs[0].name == '_' and e.segs[0].targs is None:
                return A.ExprStmt(self.expr(), pos, discard=True)
            return A.Assign(e, self.expr(), pos)
        return A.ExprStmt(e, pos)

    def let_else(self, pos, variant, binders):
        """`let variant{ binders } = init else ...`, after the pattern."""
        self.expect_op('=')
        init = self.expr()
        if not self.is_kw('else'):
            self.err("a `let` with a pattern needs an `else`")
        return self.let_else_tail(pos, variant, binders, init)

    def let_else_tail(self, pos, variant, binders, init):
        """From the `else`: an optional pattern for the other variant, then the block."""
        self.expect_kw('else')
        els_variant, els_binders = None, []
        if not self.is_op('{'):
            # `else v { ... }` binds nothing; `else v{ ... } { ... }` has bindings, then the block.
            els_variant = 'null' if self.accept_kw('null') else self.ident()
            if self.braces_then_brace():
                els_binders = self.binders()
        return A.LetElse(variant, binders, init, els_variant, els_binders, self.block(), pos)

    def braces_then_brace(self):
        """Whether the `{ ... }` starting here is followed by another `{`."""
        if not self.is_op('{'):
            return False
        depth, k = 0, 0
        while self.peek(k).kind != 'eof':
            if self.is_op('{', k):
                depth += 1
            elif self.is_op('}', k):
                depth -= 1
                if depth == 0:
                    return self.is_op('{', k + 1)
            k += 1
        return False

    def pattern(self):
        """`variant` or `variant{ binders }`, where variant may be `null`."""
        variant = 'null' if self.accept_kw('null') else self.ident()
        return variant, self.binders() if self.is_op('{') else []

    def binders(self):
        """`{ f, &g, h = x, &k = y }`: the payload fields a pattern binds, as (field, amp, pos, local)."""
        self.expect_op('{')
        binders = []
        while not self.is_op('}'):
            bpos = self.peek().pos
            amp = self.accept_op('&')
            field = self.ident()
            local = self.ident() if self.accept_op('=') else field
            binders.append((field, amp, bpos, local))
            if not self.accept_op(','):
                break
        self.expect_op('}')
        return binders

    def cond_expr(self):
        """The condition of an `if` or `while`, or a match scrutinee: an expression that ends
        where its block's `{` begins (brace_is_call)."""
        saved, self.in_cond = self.in_cond, True
        try:
            return self.or_expr()
        finally:
            self.in_cond = saved

    def brace_is_call(self):
        """In a condition, whether the `{` here begins a call or literal rather than the block:
        whether the token after its matching `}` is on the same line and could continue an
        expression."""
        depth, k = 0, 0
        while self.peek(k).kind != 'eof':
            if self.is_op('{', k):
                depth += 1
            elif self.is_op('}', k):
                depth -= 1
                if depth == 0:
                    after = self.peek(k + 1)
                    if after.nl or after.kind == 'eof' or self.is_kw('else', k + 1):
                        return False
                    return not (after.kind == 'op' and after.val in (';', '}', ',', ')', ']'))
            k += 1
        return False

    def if_stmt(self):
        pos = self.next().pos
        cond = self.cond_expr()
        then = self.block()
        els = None
        if self.accept_kw('else'):
            if self.is_kw('if'):
                ipos = self.peek().pos
                els = A.Block([self.if_stmt()], ipos)
            else:
                els = self.block()
        return A.If(cond, then, els, pos)

    def if_expr(self):
        """An `if` in expression position. `else` is required; `else if` nests another one."""
        tok = self.next()
        cond = self.cond_expr()
        then = self.block()
        if not self.accept_kw('else'):
            self.err("an `if` expression needs an `else`", tok)
        if self.is_kw('if'):
            ipos = self.peek().pos
            els = A.Block([A.ExprStmt(self.if_expr(), ipos)], ipos)
        else:
            els = self.block()
        return A.If(cond, then, els, tok.pos)

    def match_stmt(self):
        pos = self.next().pos
        scrut = self.cond_expr()
        self.expect_op('{')
        arms = []
        self.skip_semis()
        while not self.is_op('}'):
            apos = self.peek().pos
            pats = []
            if not self.accept_kw('else'):
                pats.append((*self.pattern(), apos))
                while self.accept_op('|'):
                    ppos = self.peek().pos
                    pats.append((*self.pattern(), ppos))
            self.expect_op('=>')
            arms.append(A.Arm(pats, self.block(), apos))
            self.accept_op(',')
            self.skip_semis()
        self.expect_op('}')
        return A.Match(scrut, arms, pos)

    # ---- expressions ----

    def expr(self):
        saved, self.in_cond = self.in_cond, False
        try:
            return self.or_expr()
        finally:
            self.in_cond = saved

    def or_expr(self):
        e = self.and_expr()
        while self.is_kw('or'):
            pos = self.next().pos
            e = A.Binary('or', e, self.and_expr(), pos)
        return e

    def and_expr(self):
        e = self.cmp_expr()
        while self.is_kw('and'):
            pos = self.next().pos
            e = A.Binary('and', e, self.cmp_expr(), pos)
        return e

    def cmp_expr(self):
        e = self.bin_expr(0)
        tok = self.peek()
        if tok.kind == 'op' and tok.val in CMP_OPS:
            self.next()
            e = A.Binary(tok.val, e, self.bin_expr(0), tok.pos)
            nxt = self.peek()
            if nxt.kind == 'op' and nxt.val in CMP_OPS:
                self.err('comparisons do not chain', nxt)
        return e

    def bin_expr(self, level):
        """The operators of BIN_LEVELS[level] and tighter."""
        if level == len(BIN_LEVELS):
            return self.prefix()
        ops = BIN_LEVELS[level]
        e = self.bin_expr(level + 1)
        while True:
            tok = self.peek()
            if tok.kind == 'op' and tok.val in ops:
                self.next()
                e = A.Binary(tok.val, e, self.bin_expr(level + 1), tok.pos)
            else:
                return e

    def prefix(self):
        tok = self.peek()
        if self.accept_op('&'):
            return A.AddrOf(self.prefix(), tok.pos)
        if self.accept_op('-'):
            inner = self.prefix()
            if isinstance(inner, (A.IntLit, A.FloatLit)) and not getattr(inner, 'neg', False):
                inner.val = -inner.val
                inner.neg = True
                inner.pos = tok.pos
                return inner
            return A.Unary('-', inner, tok.pos)
        if self.accept_kw('not'):
            return A.Unary('not', self.prefix(), tok.pos)
        return self.postfix()

    def postfix(self):
        e = self.primary()
        if isinstance(e, (A.If, A.Match)):
            return e        # `if` and `match` expressions end at their closing `}`
        while True:
            tok = self.peek()
            if tok.kind != 'op':
                return e
            v = tok.val
            if v == '.':
                self.next()
                if self.accept_op('*'):
                    e = A.Deref(e, tok.pos)
                else:
                    e = A.Field(e, self.ident(), tok.pos)
            elif v == '::' and isinstance(e, A.Path):
                self.next()
                npos = self.peek().pos
                e.segs.append(A.Seg(self.ident(), None, npos))
            elif v == '(' and not tok.nl and isinstance(e, A.Path) and e.segs[-1].targs is None:
                e.segs[-1].targs = self.type_list()
            elif v == '[' and not tok.nl:
                self.next()
                idx = self.expr()
                self.expect_op(']')
                e = A.Index(e, idx, tok.pos)
            elif v == '{' and not tok.nl:
                if self.in_cond and not self.brace_is_call():
                    return e
                e = self.braced(e)
            else:
                return e

    def braced(self, callee):
        pos = self.next().pos
        items = []
        forward = bind = False
        while not self.is_op('}'):
            tok = self.peek()
            if forward or bind:
                self.err(f"'{'..' if forward else '_'}' must be the last item", tok)
            if self.accept_op('..'):
                forward = True
            elif tok.kind == 'id' and tok.val == '_':
                self.next()
                bind = True
            elif self.accept_op('&'):
                name = self.ident()
                items.append(A.Item(name, A.AddrOf(A.Path([A.Seg(name, None, tok.pos)], tok.pos), tok.pos), tok.pos))
            else:
                name = self.ident()
                if self.accept_op('='):
                    items.append(A.Item(name, self.expr(), tok.pos))
                else:
                    items.append(A.Item(name, A.Path([A.Seg(name, None, tok.pos)], tok.pos), tok.pos))
            if not self.accept_op(','):
                break
        self.expect_op('}')
        return A.Braced(callee, items, forward, bind, pos)

    def primary(self):
        tok = self.peek()
        pos = tok.pos
        k = tok.kind
        if k == 'int':
            self.next()
            return A.IntLit(tok.val, pos)
        if k == 'float':
            self.next()
            return A.FloatLit(tok.val, pos)
        if k == 'char':
            self.next()
            return A.IntLit(tok.val, pos)
        if k == 'str':
            self.next()
            return A.StrLit(tok.val, pos)
        if k == 'id':
            self.next()
            return A.Path([A.Seg(tok.val, None, pos)], pos)
        if k == 'kw':
            if tok.val in ('true', 'false'):
                self.next()
                return A.BoolLit(tok.val == 'true', pos)
            if tok.val == 'null':
                self.next()
                return A.NullLit(pos)
            if tok.val == 'if':
                return self.if_expr()
            if tok.val == 'match':
                return self.match_stmt()
        if k == 'builtin':
            return self.builtin()
        if self.accept_op('('):
            e = self.expr()
            self.expect_op(')')
            return e
        if self.accept_op('['):
            if self.is_op(']'):
                self.next()
                return A.ArrayLit([], pos)
            first = self.expr()
            if self.accept_op(';'):
                count = self.expr()
                self.expect_op(']')
                return A.ArrayRep(first, count, pos)
            elems = [first]
            while self.accept_op(','):
                if self.is_op(']'):
                    break
                elems.append(self.expr())
            self.expect_op(']')
            return A.ArrayLit(elems, pos)
        self.err(f'expected an expression, found {self.describe(tok)}')

    def builtin(self):
        tok = self.next()
        name = tok.val
        if name not in BUILTINS:
            self.err(f'unknown builtin `@{name}`', tok)
        ntypes, nvalues, usage = BUILTINS[name]
        lo, hi = nvalues if isinstance(nvalues, tuple) else (nvalues, nvalues)
        if not self.is_op('('):
            self.err(f"expected '(' after @{name}: {usage}")
        self.next()
        parts = []
        while len(parts) < ntypes + hi and not self.is_op(')'):
            parts.append(self.type() if len(parts) < ntypes else self.expr())
            if not self.accept_op(','):
                break
        if len(parts) < ntypes + lo or not self.is_op(')'):
            self.err(f'wrong number of arguments: {usage}')
        self.next()
        targ = parts[0] if ntypes else None
        return A.Builtin(name, targ, parts[ntypes:], tok.pos)


def parse(src, file=None):
    return Parser(lex(src, file)).program()


def parse_type(src):
    p = Parser(lex(src))
    t = p.type()
    if p.peek().kind != 'eof':
        p.err('unexpected text after type')
    return t
