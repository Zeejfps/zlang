"""Builds the differential-testing corpus: every program the test suite runs, with its outcome.

    python tools/corpus.py [OUT]            OUT defaults to build/corpus

Runs tests/test_ctxi.py with ctxi's run_sources wrapped, so each program is recorded with its
arguments and standard input, and with what ctxi made of it: output, exit code, panic or compile
error. std/ and examples/ are added as programs of their own. Each case is a directory:

    OUT/0001/case.json          {"files": [...], "args": [...], "stdin": hex, "outcome": {...}}
    OUT/0001/<file>             each source file, under the name its positions use

A program that appears more than once (same files, args and input) is recorded once.
"""

import glob
import hashlib
import io
import json
import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ctxi.__main__ as M  # noqa: E402
from ctxi.lexer import CompileError  # noqa: E402
from ctxi.runtime import Panic  # noqa: E402

cases = {}
original = M.run_sources


def pos_json(pos):
    if pos is None:
        return None
    return [pos[0], pos[1], pos[2] if len(pos) > 2 else None]


def recording(sources, out=None, err=None, inp=None, stack_size=16 << 20, args=()):
    """run_sources, recording the program and its outcome. Behaves exactly like the original."""
    stdin = b''
    if inp is not None:
        stdin = inp.read()
        inp = io.BytesIO(stdin)
    o, e = io.BytesIO(), io.BytesIO()
    case = {
        'files': [[f, src] for src, f in sources],
        'args': list(args),
        'stdin': stdin.hex(),
        'stack': stack_size,
        'outcome': {'kind': 'crash'},
    }
    try:
        code = original(sources, out=o, err=e, inp=inp, stack_size=stack_size, args=args)
        case['outcome'] = {'kind': 'exit', 'code': code}
        return code
    except CompileError as ex:
        case['outcome'] = {'kind': 'error', 'msg': ex.msg, 'pos': pos_json(ex.pos)}
        raise
    except Panic as ex:
        case['outcome'] = {'kind': 'panic', 'msg': ex.msg, 'pos': pos_json(ex.pos)}
        raise
    except RecursionError:
        case['outcome'] = {'kind': 'panic', 'msg': 'stack overflow', 'pos': None}
        raise
    finally:
        case['outcome']['stdout'] = o.getvalue().hex()
        case['outcome']['stderr'] = e.getvalue().hex()
        write_back(o.getvalue(), out)
        write_back(e.getvalue(), err)
        key = hashlib.sha256(json.dumps([case['files'], case['args'], case['stdin']]).encode()).hexdigest()
        cases.setdefault(key, case)


def write_back(data, stream):
    """Hands a run's output to the stream the test passed, as run_sources would have."""
    if stream is None or not data:
        return
    if isinstance(stream, io.TextIOBase):
        stream.write(data.decode('utf-8', 'replace'))
    else:
        stream.write(data)


def std_and_examples():
    """std alone (with a trivial main) and each example, run with no input."""
    progs = [[('fn main {}', None)]]
    for path in sorted(glob.glob(os.path.join(ROOT, 'examples', '*'))):
        if os.path.isdir(path):
            files = sorted(glob.glob(os.path.join(path, '*.ctx')))
        elif path.endswith('.ctx'):
            files = [path]
        else:
            continue
        srcs = []
        for f in files:
            with open(f, encoding='utf-8') as h:
                srcs.append((h.read(), os.path.relpath(f, ROOT).replace(os.sep, '/')))
        progs.append(srcs)
    for srcs in progs:
        try:
            recording(srcs, out=io.StringIO(), err=io.StringIO(), inp=io.BytesIO(b''))
        except (CompileError, Panic, RecursionError):
            pass


def main(argv):
    out_dir = argv[0] if argv else os.path.join(ROOT, 'build', 'corpus')
    M.run_sources = recording
    sys.modules.pop('test_ctxi', None)
    sys.path.insert(0, os.path.join(ROOT, 'tests'))
    import test_ctxi  # noqa: E402  (binds the wrapped run_sources)
    old = os.getcwd()
    os.chdir(ROOT)                     # tests read examples/ by relative path in places
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_ctxi)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        std_and_examples()
    finally:
        os.chdir(old)
    if not result.wasSuccessful():
        print(f'warning: {len(result.failures)} failures, {len(result.errors)} errors in the suite',
              file=sys.stderr)
    shutil.rmtree(out_dir, ignore_errors=True)
    for n, key in enumerate(sorted(cases, key=lambda k: json.dumps(cases[k]['files'])), 1):
        case = cases[key]
        d = os.path.join(out_dir, f'{n:04d}')
        os.makedirs(d)
        names = []
        for i, (f, src) in enumerate(case['files']):
            name = f if f else f'main{i}.ctx'
            names.append(name)
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='') as h:
                h.write(src)
        meta = dict(case, files=[[f, name] for (f, _), name in zip(case['files'], names)])
        with open(os.path.join(d, 'case.json'), 'w', encoding='utf-8') as h:
            json.dump(meta, h, indent=1)
    kinds = {}
    for c in cases.values():
        kinds[c['outcome']['kind']] = kinds.get(c['outcome']['kind'], 0) + 1
    print(f'{len(cases)} programs in {out_dir}: ' + ', '.join(f'{v} {k}' for k, v in sorted(kinds.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
