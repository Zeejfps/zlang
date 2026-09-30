"""Differential test of ctxc's parser against ctxi's (stage 5).

    python tools/parsetest.py [CORPUS] [--interp] [-k SUBSTRING] [-v] [--fuzz N]

Parses every file of every program in the corpus (tools/corpus.py), plus std/ and ctxc/, with
both parsers and compares syntax-tree dumps (ctxc/dump.ctx describes the format). Where ctxi
parses a file, ctxc's dump must match it byte for byte and ctxc must report nothing. Where ctxi
stops at an error, ctxc's first diagnostic must have the same position and message.

With --fuzz N, it compares N damaged copies of each file instead, under build/parsefuzz: with a
token deleted, duplicated or replaced, or cut short at a token boundary. Damage that ctxi's lexer
rejects is compared the same way, by the first diagnostic.

ctxc runs natively (ctxi/cbackend.py builds it), or under ctxi with --interp.
"""

import os
import random
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from ctxi import ast as A  # noqa: E402
from ctxi.lexer import CompileError, lex  # noqa: E402
from ctxi.parser import Parser  # noqa: E402
from lextest import BATCH, diff, escape, files, first_error, run_ctxc  # noqa: E402


class Dumper:
    """ctxi's syntax tree as text: one node per line, children indented by two spaces. A line
    starts with the node's position, except for `-` (an absent optional child) and `else`."""

    def __init__(self):
        self.out = []
        self.depth = 0

    def line(self, pos, text):
        at = f'{pos[0]}:{pos[1]} ' if pos is not None else ''
        self.out.append('  ' * self.depth + at + text + '\n')

    def none(self):
        self.out.append('  ' * self.depth + '-\n')

    def kids(self, f, *xs):
        self.depth += 1
        for x in xs:
            f(x)
        self.depth -= 1

    @staticmethod
    def generics(names):
        return f'({",".join(names)})' if names else ''

    # ---- declarations

    def decl(self, d):
        g = self.generics(getattr(d, 'tparams', []))
        if isinstance(d, A.FnDecl):
            self.line(d.pos, f'fn {d.name}{g}')
            self.depth += 1
            for f in d.fields:
                self.param(f)
            self.opt_type(d.ret)
            self.block(d.body)
            self.depth -= 1
        elif isinstance(d, A.StructDecl):
            self.line(d.pos, f'struct {d.name}{g}')
            self.kids(self.field, *d.fields)
        elif isinstance(d, A.UnionDecl):
            self.line(d.pos, f'union {d.name}{g}')
            self.kids(self.variant, *d.variants)
        elif isinstance(d, A.EnumDecl):
            self.line(d.pos, f'enum {d.name}')
            self.depth += 1
            self.type(d.base)
            for name, value, pos in d.variants:
                self.line(pos, f'variant {name}')
                if value is not None:
                    self.kids(self.expr, value)
            self.depth -= 1
        elif isinstance(d, A.TypeDecl):
            self.line(d.pos, f'type {d.name}{g}')
            self.kids(self.type, d.texpr)
        elif isinstance(d, A.ConstDecl):
            self.line(d.pos, f'const {d.name}')
            self.depth += 1
            self.type(d.texpr)
            self.expr(d.expr)
            self.depth -= 1
        elif isinstance(d, A.NamespaceDecl):
            self.line(d.pos, f'namespace {d.name}')
            self.kids(self.decl, *d.decls)
        else:
            raise TypeError(d)

    def param(self, f):
        self.line(f.pos, f'field {"mut " if f.mut else ""}{f.name}')
        self.kids(self.type, f.texpr)

    def field(self, f):
        name, texpr, pos = f
        self.line(pos, f'field {name}')
        self.kids(self.type, texpr)

    def variant(self, v):
        self.line(v.pos, f'variant {v.name}{"{}" if v.fields is not None else ""}')
        self.kids(self.field, *(v.fields or []))

    # ---- types

    def opt_type(self, t):
        if t is None:
            self.none()
        else:
            self.type(t)

    def type(self, t):
        if isinstance(t, A.TPath):
            self.line(t.pos, 'tpath')
            self.kids(self.seg, *t.segs)
        elif isinstance(t, A.TPtr):
            self.line(t.pos, 'tptr mut' if t.mut else 'tptr')
            self.kids(self.type, t.elem)
        elif isinstance(t, A.TOpt):
            self.line(t.pos, 'topt')
            self.kids(self.type, t.elem)
        elif isinstance(t, A.TSlice):
            self.line(t.pos, 'tslice mut' if t.mut else 'tslice')
            self.kids(self.type, t.elem)
        elif isinstance(t, A.TArr):
            self.line(t.pos, 'tarray')
            self.depth += 1
            self.expr(t.n)
            self.type(t.elem)
            self.depth -= 1
        elif isinstance(t, A.TFn):
            self.line(t.pos, 'tfn bound' if t.bound else 'tfn')
            self.depth += 1
            for f in t.fields:
                self.param(f)
            self.opt_type(t.ret)
            self.depth -= 1
        else:
            raise TypeError(t)

    def seg(self, s):
        self.line(s.pos, f'seg {s.name}{"()" if s.targs is not None else ""}')
        self.kids(self.type, *(s.targs or []))

    # ---- statements

    def block(self, b):
        self.line(b.pos, 'block')
        self.kids(self.stmt, *b.stmts)

    def opt_expr(self, e):
        if e is None:
            self.none()
        else:
            self.expr(e)

    def binders(self, bs):
        for field, amp, pos, local in bs:
            self.line(pos, f'bind {"&" if amp else ""}{field}{"" if local == field else " = " + local}')

    def stmt(self, s):
        if isinstance(s, A.Let):
            self.line(s.pos, f'let {"mut " if s.mut else ""}{s.name}')
            self.depth += 1
            self.opt_type(s.texpr)
            self.opt_expr(s.init)
            self.depth -= 1
        elif isinstance(s, A.LetElse):
            self.line(s.pos, f'letelse {s.variant}')
            self.depth += 1
            self.binders(s.binders)
            self.expr(s.init)
            self.line(None, 'else' + ('' if s.els_variant is None else ' ' + s.els_variant))
            self.depth += 1
            self.binders(s.els_binders)
            self.depth -= 1
            self.block(s.els)
            self.depth -= 1
        elif isinstance(s, A.Assign):
            self.line(s.pos, 'assign')
            self.kids(self.expr, s.lhs, s.rhs)
        elif isinstance(s, A.ExprStmt):
            self.line(s.pos, 'discard' if s.discard else 'do')
            self.kids(self.expr, s.expr)
        elif isinstance(s, A.If):
            self.if_(s)
        elif isinstance(s, A.While):
            label = '' if s.label is None else f' {s.label[0]} {s.label[1][0]}:{s.label[1][1]}'
            self.line(s.pos, 'while' + label)
            self.depth += 1
            self.expr(s.cond)
            self.block(s.body)
            self.depth -= 1
        elif isinstance(s, A.Match):
            self.match(s)
        elif isinstance(s, A.Return):
            self.line(s.pos, 'return')
            if s.expr is not None:
                self.kids(self.expr, s.expr)
        elif isinstance(s, A.Break):
            self.line(s.pos, 'break' + ('' if s.label is None else ' ' + s.label))
        elif isinstance(s, A.Continue):
            self.line(s.pos, 'continue' + ('' if s.label is None else ' ' + s.label))
        elif isinstance(s, A.Defer):
            self.line(s.pos, 'defer')
            self.kids(self.block, s.body)
        else:
            raise TypeError(s)

    def if_(self, s):
        self.line(s.pos, 'if')
        self.depth += 1
        self.expr(s.cond)
        self.block(s.then)
        if s.els is None:
            self.none()
        else:
            self.block(s.els)
        self.depth -= 1

    def match(self, s):
        self.line(s.pos, 'match')
        self.depth += 1
        self.expr(s.scrut)
        for arm in s.arms:
            self.line(arm.pos, 'arm')
            self.depth += 1
            for variant, binders, pos in arm.pats:
                self.line(pos, f'pat {variant}')
                self.depth += 1
                self.binders(binders)
                self.depth -= 1
            self.block(arm.body)
            self.depth -= 1
        self.depth -= 1

    # ---- expressions

    def expr(self, e):
        if isinstance(e, A.IntLit):
            self.line(e.pos, f'int {e.val if abs(e.val) < 1 << 64 else ("-" if e.val < 0 else "") + "toobig"}')
        elif isinstance(e, A.FloatLit):
            self.line(e.pos, f'float {e.val!r}')
        elif isinstance(e, A.StrLit):
            self.line(e.pos, 'str "' + ''.join(chr(b) if 32 <= b < 127 and b not in b'"\\' else f'\\x{b:02x}'
                                               for b in e.val) + '"')
        elif isinstance(e, A.BoolLit):
            self.line(e.pos, 'true' if e.val else 'false')
        elif isinstance(e, A.NullLit):
            self.line(e.pos, 'null')
        elif isinstance(e, A.Path):
            self.line(e.pos, 'path')
            self.kids(self.seg, *e.segs)
        elif isinstance(e, A.Field):
            self.line(e.pos, f'dot {e.name}')
            self.kids(self.expr, e.base)
        elif isinstance(e, A.Deref):
            self.line(e.pos, 'deref')
            self.kids(self.expr, e.base)
        elif isinstance(e, A.Index):
            self.line(e.pos, 'index')
            self.kids(self.expr, e.base, e.index)
        elif isinstance(e, A.Range):
            self.line(e.pos, 'range')
            self.kids(self.opt_expr, e.base, e.lo, e.hi)
        elif isinstance(e, A.Braced):
            self.line(e.pos, 'braced' + (' ..' if e.forward else '') + (' _' if e.bind else ''))
            self.depth += 1
            self.expr(e.callee)
            for item in e.items:
                self.line(item.pos, f'item {item.name}')
                self.kids(self.expr, item.expr)
            self.depth -= 1
        elif isinstance(e, A.Unary):
            self.line(e.pos, 'neg' if e.op == '-' else 'not')
            self.kids(self.expr, e.expr)
        elif isinstance(e, A.AddrOf):
            self.line(e.pos, 'addr')
            self.kids(self.expr, e.expr)
        elif isinstance(e, A.Binary):
            self.line(e.pos, f'binary {e.op}')
            self.kids(self.expr, e.lhs, e.rhs)
        elif isinstance(e, A.ArrayLit):
            self.line(e.pos, 'array')
            self.kids(self.expr, *e.elems)
        elif isinstance(e, A.ArrayRep):
            self.line(e.pos, 'repeat')
            self.kids(self.expr, e.elem, e.count)
        elif isinstance(e, A.Builtin):
            self.line(e.pos, f'@{e.name}')
            self.depth += 1
            if e.targ is not None:
                self.type(e.targ)
            for a in e.args:
                self.expr(a)
            self.depth -= 1
        elif isinstance(e, A.If):
            self.if_(e)
        elif isinstance(e, A.Match):
            self.match(e)
        else:
            raise TypeError(e)


def dump(src):
    """ctxi's dump of src: the tree, or just the error line if it doesn't lex or parse."""
    try:
        decls = Parser(lex(src)).program()
    except CompileError as e:
        return f'{e.pos[0]}:{e.pos[1]} error {escape(e.msg)}\n'
    d = Dumper()
    for x in decls:
        d.decl(x)
    return ''.join(d.out)


def fuzz(todo, n):
    """(label, path) for n damaged copies of each file, written under build/parsefuzz. Damage
    is at the level of tokens: ctxi's lexer finds their boundaries."""
    rng = random.Random(5)
    out_dir = os.path.join(ROOT, 'build', 'parsefuzz')
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    out = []
    for label, p in todo:
        with open(p, encoding='utf-8', newline='') as f:
            src = f.read()
        try:
            toks = lex(src)
        except CompileError:
            continue
        # Each token's start and end as string indices.
        starts = line_offsets(src)
        spans = [(starts[t.line - 1] + t.col - 1, starts[t.line - 1] + t.col - 1 + t.width) for t in toks]
        for k in range(n):
            j = rng.randrange(len(toks))
            a, b = spans[j]
            how = rng.randrange(4)
            if how == 0:
                bad = src[:a]
            elif how == 1:
                bad = src[:a] + src[b:]
            elif how == 2:
                bad = src[:a] + src[a:b] + ' ' + src[a:]
            else:
                c, d = spans[rng.randrange(len(toks))]
                bad = src[:a] + src[c:d] + src[b:]
            path = os.path.join(out_dir, f'{len(out):06d}.ctx')
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(bad)
            out.append((f'{label}~{k}', path))
    return out


def line_offsets(src):
    starts = [0]
    for i, c in enumerate(src):
        if c == '\n':
            starts.append(i + 1)
    return starts


def main(argv):
    sys.stdout.reconfigure(errors='backslashreplace')
    interp = '--interp' in argv
    verbose = '-v' in argv
    opts = {}
    for name in ('-k', '--fuzz'):
        if name in argv:
            i = argv.index(name)
            opts[name] = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    rest = [a for a in argv if not a.startswith('-')]
    corpus = rest[0] if rest else os.path.join(ROOT, 'build', 'corpus')
    todo = files(corpus, opts.get('-k', ''))
    if '--fuzz' in opts:
        todo = fuzz(todo, int(opts['--fuzz']))
    start = time.time()
    got = {}
    for i in range(0, len(todo), BATCH):
        got.update(run_ctxc([p for _, p in todo[i:i + BATCH]], interp, command='syntax'))
    parsed = errors = failed = 0
    for label, p in todo:
        have = got.get(p)
        if have is None:
            failed += 1
            print(f'{label}: no output from ctxc')
            continue
        with open(p, encoding='utf-8', newline='') as f:
            want = dump(f.read())
        if ' error ' in want and first_error(want) == want:
            errors += 1
            if first_error(have) != want:
                failed += 1
                print(f'{label}: ctxi {want.strip()!r}, ctxc {(first_error(have) or "no error").strip()!r}')
            elif verbose:
                print(f'{label}: {want.strip()}')
        else:
            parsed += 1
            if have != want:
                failed += 1
                print(f'{label}: {diff(want, have)}')
    print(f'{len(todo) - failed}/{len(todo)} files agree ({parsed} parsed, {errors} errors) '
          f'in {time.time() - start:.1f}s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
