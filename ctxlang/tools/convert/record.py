"""Records what the Python suite does, to write the case files from (LLM-FIRST 5.2).

    python tools/convert/record.py OUT.jsonl [unittest names...]

Runs tests/ with hooks in toolchain.py's entry points, in subprocess, and in unittest's
assertions: one JSON line for each event of each test, in order. Nothing here reads ctxlang.
"""

import base64
import contextlib
import functools
import inspect
import json
import os
import subprocess
import sys
import threading
import traceback
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import toolchain  # noqa: E402

OUT = None
LOCK = threading.Lock()
STATE = threading.local()
CURRENT = {'test': None, 'sub': [], 'seq': 0, 'dirs': []}


def b64(data):
    if data is None:
        return None
    if isinstance(data, str):
        data = data.encode('utf-8', 'surrogateescape')
    return base64.b64encode(data).decode()


def emit(kind, **fields):
    with LOCK:
        CURRENT['seq'] += 1
        rec = {'test': CURRENT['test'], 'sub': list(CURRENT['sub']), 'seq': CURRENT['seq'], 'kind': kind, **fields}
        OUT.write(json.dumps(rec, default=repr) + '\n')
        OUT.flush()


def depth():
    return getattr(STATE, 'depth', 0)


@contextlib.contextmanager
def inside():
    STATE.depth = depth() + 1
    try:
        yield
    finally:
        STATE.depth -= 1


def exc_fields(e):
    if e is None:
        return {'exc': None}
    out = {'exc': type(e).__name__, 'exc_str': str(e)[:20000]}
    if isinstance(e, toolchain.CompileError):
        out.update(msg=e.msg, pos=e.pos, text=e.text)
    elif isinstance(e, toolchain.Panic):
        out.update(msg=e.msg, pos=e.pos, thread=e.thread)
    return out


# ---- toolchain

real = {name: getattr(toolchain, name) for name in (
    'run_sources', 'run_exe', 'build_sources', 'build_files', 'build_project', 'ir_sources', 'ctxc_build',
    'write_program', 'read_program', 'execute', 'log', 'diff')}


def execute(exe, stdin, stack_size=None, args=(), timeout=None, env=None, cwd=None):
    r = real['execute'](exe, stdin, stack_size, args, timeout, env, cwd)
    STATE.execs = getattr(STATE, 'execs', []) + [r]
    return r


def log(status, reason, detail=''):
    STATE.diffs = getattr(STATE, 'diffs', []) + [(status, reason)]
    return real['log'](status, reason, detail)


def snapshot(path, limit=200):
    """{relative name: base64} for the files under path (a directory), or of a file."""
    out = {}
    if os.path.isfile(path):
        with open(path, 'rb') as f:
            out[os.path.basename(path)] = b64(f.read(1 << 20))
        return out
    for base, dirs, files in os.walk(path):
        for name in sorted(dirs):
            out[os.path.relpath(os.path.join(base, name), path).replace(os.sep, '/') + '/'] = ''
        for name in sorted(files):
            p = os.path.join(base, name)
            if len(out) >= limit:
                return out
            try:
                if os.path.getsize(p) > (1 << 20):
                    out[os.path.relpath(p, path).replace(os.sep, '/')] = None
                    continue
                with open(p, 'rb') as f:
                    out[os.path.relpath(p, path).replace(os.sep, '/')] = b64(f.read())
            except OSError:
                pass
    return out


def run_sources(sources, out=None, err=None, inp=None, stack_size=16 << 20, args=(), timeout=None):
    if depth():
        return real['run_sources'](sources, out, err, inp, stack_size, args, timeout)
    data = None
    if inp is not None:
        data = inp.read()
        data = data.encode() if isinstance(data, str) else data
        import io
        inp = io.BytesIO(data)
    STATE.execs, STATE.diffs = [], []
    exc, code = None, None
    arg_snaps = {a: snapshot(a) for a in args if isinstance(a, str) and os.path.isabs(a) and os.path.exists(a)}
    dirs = dirs_now()
    try:
        with inside():
            code = real['run_sources'](sources, out, err, inp, stack_size, args, timeout)
        return code
    except BaseException as e:
        exc = e
        raise
    finally:
        r = STATE.execs[0] if STATE.execs else None
        emit('run_sources', sources=[[s, f] for s, f in sources], stdin=b64(data), args=list(args),
             stack_size=stack_size, timeout=timeout, code=code, out_given=out is not None, err_given=err is not None,
             raw_code=None if r is None else r.returncode, stdout=None if r is None else b64(r.stdout),
             stderr=None if r is None else b64(r.stderr), diffs=STATE.diffs, ctx_diff=os.environ.get('CTX_DIFF'),
             arg_snaps=arg_snaps, dirs=dirs, dirs_after=dirs_now(), environ=environ_delta(), **exc_fields(exc))


def wrap(name, describe):
    fn = real[name]

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if depth():
            return fn(*a, **kw)
        STATE.execs = []
        exc, ret = None, None
        dirs = dirs_now()
        try:
            with inside():
                ret = fn(*a, **kw)
            return ret
        except BaseException as e:
            exc = e
            raise
        finally:
            try:
                fields = describe(a, kw, ret)
            except Exception:
                fields = {'describe_failed': traceback.format_exc()}
            execs = [{'code': r.returncode, 'stdout': b64(r.stdout), 'stderr': b64(r.stderr)} for r in STATE.execs]
            emit(name, execs=execs, dirs=dirs, dirs_after=dirs_now(), environ=environ_delta(), **fields, **exc_fields(exc))
    return wrapper


def bind(fn, a, kw):
    return inspect.signature(fn).bind(*a, **kw).arguments


def d_run_exe(a, kw, ret):
    b = dict(bind(real['run_exe'], a, kw))
    inp = b.pop('inp', None)
    b.pop('out', None), b.pop('err', None)
    return {'call': b, 'ret': ret, 'had_inp': inp is not None}


def d_build_sources(a, kw, ret):
    b = bind(real['build_sources'], a, kw)
    return {'sources': [[s, f] for s, f in b['sources']], 'name': b.get('name', 'program'), 'ret': ret}


def d_build_files(a, kw, ret):
    return {'call': dict(bind(real['build_files'], a, kw)), 'ret': ret}


def d_build_project(a, kw, ret):
    b = bind(real['build_project'], a, kw)
    return {'dir': b['directory'], 'snap': snapshot(b['directory']), 'ret': ret}


def d_ir_sources(a, kw, ret):
    b = bind(real['ir_sources'], a, kw)
    return {'sources': [[s, f] for s, f in b['sources']], 'ret': ret}


def d_ctxc_build(a, kw, ret):
    b = dict(bind(real['ctxc_build'], a, kw))
    return {'call': b, 'ret': ret, 'snap': snapshot(b.get('cwd', toolchain.ROOT)) if b.get('cwd') else None}


def d_write_program(a, kw, ret):
    b = bind(real['write_program'], a, kw)
    return {'sources': [[s, f] for s, f in b['sources']], 'ret': ret}


def d_read_program(a, kw, ret):
    return {'path': a[0] if a else kw.get('path')}


toolchain.execute = execute
toolchain.log = log
toolchain.run_sources = run_sources
for _name, _d in [('run_exe', d_run_exe), ('build_sources', d_build_sources), ('build_files', d_build_files),
                  ('build_project', d_build_project), ('ir_sources', d_ir_sources), ('ctxc_build', d_ctxc_build),
                  ('write_program', d_write_program), ('read_program', d_read_program)]:
    setattr(toolchain, _name, wrap(_name, _d))


# ---- the directories a test makes (tempfile.mkdtemp), as they are at each event

import tempfile  # noqa: E402

real_mkdtemp = tempfile.mkdtemp


def mkdtemp(*a, **kw):
    d = real_mkdtemp(*a, **kw)
    if CURRENT['test'] is not None:
        CURRENT['dirs'].append(d)
    return d


tempfile.mkdtemp = mkdtemp


def dirs_now():
    return {d: snapshot(d) for d in CURRENT['dirs'] if os.path.isdir(d)}


# ---- subprocess, called by a test itself

real_run, real_popen = subprocess.run, subprocess.Popen


def env_delta(env):
    if env is None:
        return None
    return {'set': {k: v for k, v in env.items() if os.environ.get(k) != v},
            'unset': [k for k in os.environ if k not in env]}


def paths_of(argv, cwd):
    out = {}
    for p in ([cwd] if cwd else []) + [a for a in argv if isinstance(a, str)]:
        if isinstance(p, str) and os.path.isabs(p) and os.path.exists(p) and not p.lower().endswith(('.exe', '.o', '.a')):
            if os.path.isdir(p) and os.path.normcase(os.path.abspath(p)) in (os.path.normcase(ROOT), os.path.normcase(os.path.join(ROOT, 'build'))):
                continue
            if os.path.isfile(p) and os.path.getsize(p) > (1 << 20):
                continue
            out[p] = snapshot(p)
    return out


def sub_run(*a, **kw):
    if depth():
        return real_run(*a, **kw)
    argv = a[0] if a else kw.get('args')
    argv = [argv] if isinstance(argv, str) else list(argv)
    snaps = paths_of(argv, kw.get('cwd'))
    dirs = dirs_now()
    exc, r = None, None
    try:
        with inside():
            r = real_run(*a, **kw)
        return r
    except BaseException as e:
        exc = e
        raise
    finally:
        def data(x):
            return None if x is None else b64(x)
        emit('subprocess.run', argv=argv, cwd=kw.get('cwd'), env=env_delta(kw.get('env')), input=data(kw.get('input')),
             timeout=kw.get('timeout'), code=None if r is None else r.returncode,
             stdout=None if r is None else data(r.stdout), stderr=None if r is None else data(r.stderr),
             before=snaps, after=paths_of(argv, kw.get('cwd')), dirs=dirs, dirs_after=dirs_now(), environ=environ_delta(),
             **exc_fields(exc))


class Popen(real_popen):
    def __init__(self, *a, **kw):
        if not depth():
            argv = a[0] if a else kw.get('args')
            argv = [argv] if isinstance(argv, str) else list(argv)
            emit('subprocess.Popen', argv=argv, cwd=kw.get('cwd'), env=env_delta(kw.get('env')), snaps=paths_of(argv, kw.get('cwd')),
                 dirs=dirs_now(), environ=environ_delta())
        super().__init__(*a, **kw)


subprocess.run = sub_run
subprocess.Popen = Popen


# ---- unittest

def short(x):
    if isinstance(x, bytes):
        return {'bytes': b64(x)}
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, (list, tuple)):
        return [short(v) for v in x]
    if isinstance(x, dict):
        return {str(k): short(v) for k, v in x.items()}
    return repr(x)[:2000]


def wrap_assert(name):
    fn = getattr(unittest.TestCase, name)

    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        if depth():
            return fn(self, *a, **kw)
        with inside():
            try:
                r = fn(self, *a, **kw)
            finally:
                emit('assert', name=name, args=short(a))
        return r
    setattr(unittest.TestCase, name, wrapper)


for _name in ('assertEqual', 'assertNotEqual', 'assertIn', 'assertNotIn', 'assertTrue', 'assertFalse', 'assertRegex',
              'assertNotRegex', 'assertIsNone', 'assertIsNotNone', 'assertGreater', 'assertGreaterEqual', 'assertLess',
              'assertLessEqual', 'assertIs', 'assertIsNot', 'assertIsInstance', 'assertCountEqual', 'assertListEqual',
              'assertAlmostEqual'):
    wrap_assert(_name)

real_test_run = unittest.TestCase.run
real_subtest = unittest.TestCase.subTest


ENVIRON = dict(os.environ)


def environ_delta():
    """What the test changed in os.environ, which every process it starts inherits."""
    return {'set': {k: v for k, v in os.environ.items() if ENVIRON.get(k) != v}, 'unset': [k for k in ENVIRON if k not in os.environ]}


def test_run(self, result=None):
    CURRENT['test'] = self.id()
    CURRENT['sub'] = []
    CURRENT['dirs'] = []
    method = getattr(self, self._testMethodName)
    try:
        src = inspect.getsource(method)
        _, line = inspect.getsourcelines(method)
    except (OSError, TypeError):
        src, line = '', 0
    emit('test', doc=type(self).__doc__, line=line, source=src, native=toolchain.native_ctxc(), python=sys.executable, root=ROOT)
    try:
        return real_test_run(self, result)
    finally:
        emit('end')
        CURRENT['test'] = None


@contextlib.contextmanager
def sub_test(self, msg=unittest.case._subtest_msg_sentinel, **params):
    CURRENT['sub'].append(short(params) if params else short(msg))
    emit('subtest')
    try:
        with real_subtest(self, msg, **params):
            yield
    finally:
        CURRENT['sub'].pop()


unittest.TestCase.run = test_run
unittest.TestCase.subTest = sub_test


class Result(unittest.TextTestResult):
    def addSkip(self, test, reason):
        with LOCK:
            OUT.write(json.dumps({'test': test.id(), 'kind': 'skipped', 'reason': reason}) + '\n')
        super().addSkip(test, reason)

    def addFailure(self, test, err):
        with LOCK:
            OUT.write(json.dumps({'test': test.id(), 'kind': 'failed'}) + '\n')
        super().addFailure(test, err)

    def addError(self, test, err):
        with LOCK:
            OUT.write(json.dumps({'test': test.id(), 'kind': 'errored'}) + '\n')
        super().addError(test, err)


if __name__ == '__main__':
    OUT = open(sys.argv[1], 'w', encoding='utf-8')
    names = sys.argv[2:]
    os.chdir(ROOT)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(names) if names else loader.discover('tests')
    runner = unittest.TextTestRunner(resultclass=Result, verbosity=1)
    res = runner.run(suite)
    OUT.close()
    sys.exit(0 if res.wasSuccessful() else 1)
