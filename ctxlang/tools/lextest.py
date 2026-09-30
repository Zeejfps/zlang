"""Differential test of ctxc's lexer against ctxi's (stage 4).

    python tools/lextest.py [CORPUS] [--interp] [-k SUBSTRING] [-v] [--fuzz N]

Lexes every file of every program in the corpus (tools/corpus.py), plus std/ and ctxc/, with
both lexers and compares the dumps (ctxc/dump.ctx describes the format). Where ctxi lexes a file,
ctxc's dump must match it byte for byte: tokens with positions and widths, and comments. Where
ctxi stops at a lexer error, ctxc's first diagnostic must have the same position and message.

With --fuzz N, it compares N damaged copies of each file instead, under build/lexfuzz: cut short,
with a range deleted, or with a snippet inserted that tends to break lexing (a quote, a
backslash, `/*`, a non-ASCII character). Copies that aren't valid UTF-8, which ctxi can't read,
only have to lex without a panic and end in an eof token.

ctxc runs natively (ctxi/cbackend.py builds it), or under ctxi with --interp.
"""

import glob
import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi.lexer import CompileError, lex  # noqa: E402

BATCH = 64            # files per ctxc run


def dump(src):
    """ctxi's dump of src: every line, or just the error line if it doesn't lex."""
    comments = []
    try:
        toks = lex(src, None, comments)
    except CompileError as e:
        return f'{e.pos[0]}:{e.pos[1]} error {escape(e.msg)}\n'
    out = []
    for t in toks:
        line = f'{t.line}:{t.col}+{t.width}' + (' nl' if t.nl else '')
        if t.kind == 'eof':
            line += ' eof'
        elif t.kind == 'int':
            line += ' int ' + (str(t.val) if t.val < 1 << 64 else 'toobig')
        elif t.kind == 'float':
            line += ' float ' + repr(t.val)
        elif t.kind == 'char':
            line += f' char {t.val}'
        elif t.kind == 'str':
            line += ' str "' + ''.join(chr(b) if 32 <= b < 127 and b not in b'"\\' else f'\\x{b:02x}'
                                       for b in t.val) + '"'
        else:
            line += f' {t.kind} {t.val}'
        out.append(line + '\n')
    for a, b, c, d in comments:
        out.append(f'{a}:{b}-{c}:{d} comment\n')
    return ''.join(out)


def escape(msg):
    return msg.replace('\n', '\\n')


def first_error(text):
    """The first diagnostic line of a ctxc dump: `L:C error MSG`, as opposed to an error token,
    which has a width (`L:C+W error`)."""
    for line in text.splitlines(keepends=True):
        head, _, rest = line.partition(' ')
        if rest.startswith('error ') and '+' not in head:
            return line
    return None


def files(corpus, k):
    """(label, path) for each file to lex."""
    out = []
    for name in sorted(os.listdir(corpus)):
        d = os.path.join(corpus, name)
        with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
            meta = json.load(f)
        for _, local in meta['files']:
            out.append((f'{name}/{local}', os.path.join(d, local)))
    for sub in ('std', 'ctxc'):
        for p in sorted(glob.glob(os.path.join(ROOT, sub, '*.ctx'))):
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), p))
    return [(label, p) for label, p in out if k in label]


SNIPPETS = [b'"', b"'", b'\\', b'/*', b'*/', b'//', b'@', b'\n', b'0x', b'1e', b'.5', b'#',
            b'\x00', b'\\x', b"'\\", b'"\\x4', b'\xc3\xa9', b'\xe2\x98\x83', b'\xef\xbb\xbf',
            b'\xff', b'\xc3', b'\xed\xa0\x80']


def fuzz(todo, n):
    """(label, path) for n damaged copies of each file, written under build/lexfuzz."""
    import random
    rng = random.Random(4)
    out_dir = os.path.join(ROOT, 'build', 'lexfuzz')
    import shutil
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    out = []
    for label, p in todo:
        with open(p, 'rb') as f:
            src = f.read()
        for k in range(n):
            i = rng.randrange(len(src) + 1)
            how = rng.randrange(3)
            if how == 0:
                bad = src[:i]
            elif how == 1:
                bad = src[:i] + src[i + rng.randrange(1, 40):]
            else:
                bad = src[:i] + rng.choice(SNIPPETS) + src[i:]
            path = os.path.join(out_dir, f'{len(out):06d}.ctx')
            with open(path, 'wb') as f:
                f.write(bad)
            out.append((f'{label}~{k}', path))
    return out


def run_ctxc(paths, interp):
    """{path: dump} from one ctxc run over paths."""
    args = ['tokens', *paths]
    if interp:
        from ctxi.cbackend import ctxc_program
        from ctxi.__main__ import interpret
        out = io.BytesIO()
        code = interpret(ctxc_program(), out=out, err=io.BytesIO(), args=args)
        text = out.getvalue()
    else:
        from ctxi.cbackend import native_ctxc
        r = subprocess.run([native_ctxc(), *args], capture_output=True)
        code, text = r.returncode, r.stdout
        if code != 0:
            raise RuntimeError(f'ctxc exited with {code}: {r.stderr.decode(errors="replace")}')
    got = {}
    path = None
    for line in text.decode('utf-8', 'replace').splitlines(keepends=True):
        if line.startswith('file '):
            path = line[5:].rstrip('\n')
            got[path] = []
        else:
            got[path].append(line)
    return {p: ''.join(lines) for p, lines in got.items()}


def diff(want, got):
    a, b = want.splitlines(), got.splitlines()
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<end>'
        y = b[i] if i < len(b) else '<end>'
        if x != y:
            return f'line {i + 1}: ctxi {x!r}, ctxc {y!r}'
    return 'same lines, different bytes'


def main(argv):
    sys.stdout.reconfigure(errors='backslashreplace')     # messages quote any character
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
        got.update(run_ctxc([p for _, p in todo[i:i + BATCH]], interp))
    lexed = errors = failed = 0
    for label, p in todo:
        have = got.get(p)
        if have is None:
            failed += 1
            print(f'{label}: no output from ctxc')
            continue
        try:
            with open(p, encoding='utf-8', newline='') as f:
                want = dump(f.read())
        except UnicodeDecodeError:
            lines = have.splitlines()
            eof = [line for line in lines if re.fullmatch(r'\d+:\d+\+0( nl)? eof', line)]
            if len(eof) != 1 or not any(line.endswith(' error invalid UTF-8') for line in lines):
                failed += 1
                print(f'{label}: not UTF-8, and ctxc has no single eof or no invalid UTF-8 error')
            continue
        if ' error ' in want and first_error(want) == want:
            errors += 1
            if first_error(have) != want:
                failed += 1
                print(f'{label}: ctxi {want.strip()!r}, ctxc {(first_error(have) or "no error").strip()!r}')
            elif verbose:
                print(f'{label}: {want.strip()}')
        else:
            lexed += 1
            if have != want:
                failed += 1
                print(f'{label}: {diff(want, have)}')
    print(f'{len(todo) - failed}/{len(todo)} files agree ({lexed} lexed, {errors} lexer errors) '
          f'in {time.time() - start:.1f}s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
