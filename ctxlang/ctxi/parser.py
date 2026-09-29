"""Recursive-descent parser for ctxlang."""

from .lexer import CompileError, lex
from . import ast as A

CMP_OPS = ('==', '!=', '<', '<=', '>', '>=')
# Every builtin's signature (spec §13): (type arguments, value arguments, usage).
# Type arguments always come first, so the name alone says how to parse each argument.
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
    'trap':     (0, 0, '@trap()'),
}


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

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
        if self.is_op('(') and not self.peek().ws:
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
                name = self.ident()
                texpr = self.type() if self.accept_op(':') else None
                init = self.expr() if self.accept_op('=') else None
                if texpr is None and init is None:
                    self.err(f'`let {name}` needs a type or an initializer', tok)
                return A.Let(name, mut, texpr, init, pos)
            if tok.val == 'if':
                return self.if_stmt()
            if tok.val == 'while':
                self.next()
                cond = self.paren_expr()
                return A.While(cond, self.block(), pos)
            if tok.val == 'match':
                return self.match_stmt()
            if tok.val == 'break':
                self.next()
                return A.Break(pos)
            if tok.val == 'continue':
                self.next()
                return A.Continue(pos)
            if tok.val == 'return':
                self.next()
                nxt = self.peek()
                if nxt.nl or self.is_op('}') or self.is_op(';'):
                    return A.Return(None, pos)
                return A.Return(self.expr(), pos)
        e = self.expr()
        if self.is_op('='):
            self.next()
            return A.Assign(e, self.expr(), pos)
        return A.ExprStmt(e, pos)

    def paren_expr(self):
        self.expect_op('(')
        e = self.expr()
        self.expect_op(')')
        return e

    def if_stmt(self):
        pos = self.next().pos
        cond = self.paren_expr()
        then = self.block()
        els = None
        if self.accept_kw('else'):
            if self.is_kw('if'):
                ipos = self.peek().pos
                els = A.Block([self.if_stmt()], ipos)
            else:
                els = self.block()
        return A.If(cond, then, els, pos)

    def match_stmt(self):
        pos = self.next().pos
        scrut = self.paren_expr()
        self.expect_op('{')
        arms = []
        self.skip_semis()
        while not self.is_op('}'):
            apos = self.peek().pos
            if self.accept_kw('else'):
                variant = None
            elif self.accept_kw('null'):
                variant = 'null'
            else:
                variant = self.ident()
            binders = []
            if variant is not None and self.accept_op('{'):
                while not self.is_op('}'):
                    bpos = self.peek().pos
                    amp = self.accept_op('&')
                    binders.append((self.ident(), amp, bpos))
                    if not self.accept_op(','):
                        break
                self.expect_op('}')
            self.expect_op('=>')
            arms.append(A.Arm(variant, binders, self.block(), apos))
            self.accept_op(',')
            self.skip_semis()
        self.expect_op('}')
        return A.Match(scrut, arms, pos)

    # ---- expressions ----

    def expr(self):
        return self.or_expr()

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
        e = self.add_expr()
        tok = self.peek()
        if tok.kind == 'op' and tok.val in CMP_OPS:
            self.next()
            e = A.Binary(tok.val, e, self.add_expr(), tok.pos)
            nxt = self.peek()
            if nxt.kind == 'op' and nxt.val in CMP_OPS:
                self.err('comparisons do not chain', nxt)
        return e

    def add_expr(self):
        e = self.mul_expr()
        while True:
            tok = self.peek()
            if tok.kind == 'op' and tok.val in ('+', '-'):
                self.next()
                e = A.Binary(tok.val, e, self.mul_expr(), tok.pos)
            else:
                return e

    def mul_expr(self):
        e = self.prefix()
        while True:
            tok = self.peek()
            if tok.kind == 'op' and tok.val in ('*', '/', '%'):
                self.next()
                e = A.Binary(tok.val, e, self.prefix(), tok.pos)
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
            elif v == '(' and not tok.ws and isinstance(e, A.Path) and e.segs[-1].targs is None:
                e.segs[-1].targs = self.type_list()
            elif v == '[' and not tok.nl:
                self.next()
                idx = self.expr()
                self.expect_op(']')
                e = A.Index(e, idx, tok.pos)
            elif v == '{' and not tok.nl:
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
        if not self.is_op('('):
            self.err(f"expected '(' after @{name}: {usage}")
        self.next()
        parts = []
        for k in range(ntypes + nvalues):
            if k and not self.accept_op(','):
                self.err(f'wrong number of arguments: {usage}')
            if self.is_op(')'):
                self.err(f'wrong number of arguments: {usage}')
            parts.append(self.type() if k < ntypes else self.expr())
        if parts:
            self.accept_op(',')
        if not self.is_op(')'):
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
