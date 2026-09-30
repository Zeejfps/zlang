"""Runs programs through ctxc's C backend instead of ctxi's interpreter.

    CTX_BACKEND=c python -m unittest discover tests     every test, through the C backend

A checked program goes to IR (irdump), to C (ctxc, running under ctxi), and to an executable
(gcc, or zig cc with CTX_CC=zig). Executables are cached under build/cbackend by a hash of the
IR, ctxc's sources and the runtime, so a rerun only compiles what changed.

run() behaves like ctxi's run_checked: output goes to the given streams, a panic is raised as
Panic, and it returns the exit code.
"""

import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import threading

from .irdump import verify
from .runtime import Panic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTXC = os.path.join(ROOT, 'ctxc')
RT = os.path.join(CTXC, 'rt')
CACHE = os.path.join(ROOT, 'build', 'cbackend')
STACK = 256 << 20         # reserved; ctxrt.c checks against CTX_STACK, at most 200 MiB
CFLAGS = ['-std=gnu11', '-O1', '-w', '-fwrapv']

_lock = threading.Lock()
_ctxc = None              # ctxc, checked once per process
_tree = None              # hash of ctxc's sources and the runtime


def tree_hash():
    global _tree
    if _tree is None:
        h = hashlib.sha256()
        for path in sorted(glob.glob(os.path.join(CTXC, '*.ctx')) + glob.glob(os.path.join(RT, '*'))
                           + glob.glob(os.path.join(ROOT, 'std', '*.ctx'))):
            with open(path, 'rb') as f:
                h.update(path.encode() + b'\0' + f.read())
        h.update(repr(CFLAGS).encode())
        _tree = h.hexdigest()
    return _tree


def compiler():
    """The C compiler command, and the environment to run it in."""
    env = dict(os.environ)
    if os.environ.get('CTX_CC') == 'zig':
        return ['zig', 'cc'], env
    gcc = shutil.which('gcc')
    if gcc is None:
        raise RuntimeError('no C compiler: install gcc, or set CTX_CC=zig')
    # Its own directory first, so cc1 finds its DLLs before any other MinGW's (Git Bash's).
    env['PATH'] = os.path.dirname(gcc) + os.pathsep + env.get('PATH', '')
    return [gcc], env


def ctxc_program():
    global _ctxc
    if _ctxc is None:
        from .__main__ import load_sources, read_program
        _ctxc = load_sources(read_program(CTXC))
    return _ctxc


def run_ctxc(args):
    """Runs ctxc under ctxi with room for deep recursion. Returns (exit code, stderr text)."""
    from .__main__ import interpret
    result, err = [None, None], io.BytesIO()

    def go():
        try:
            result[0] = interpret(ctxc_program(), out=io.BytesIO(), err=err, args=args)
        except BaseException as e:      # a panic in ctxc itself
            result[1] = e
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 1_000_000))
    threading.stack_size(250 << 20)
    t = threading.Thread(target=go)
    t.start()
    t.join()
    threading.stack_size(0)
    if result[1] is not None:
        raise RuntimeError(f'ctxc failed: {result[1]!r}') from result[1]
    return result[0], err.getvalue().decode('utf-8', 'replace')


def build(checker, name='program'):
    """The path of an executable for a checked program, compiling it if it isn't cached."""
    text = verify(checker)
    key = hashlib.sha256((tree_hash() + '\0' + name + '\0' + text).encode()).hexdigest()[:24]
    exe = os.path.join(CACHE, key + ('.exe' if os.name == 'nt' else ''))
    if os.path.exists(exe):
        return exe
    with _lock:
        os.makedirs(CACHE, exist_ok=True)
        # Unique names, renamed into place: other processes may build the same program.
        tag = f'{key}-{os.getpid()}'
        ir, c = os.path.join(CACHE, tag + '.ir'), os.path.join(CACHE, key + '.c')
        tmp_c, tmp_exe = os.path.join(CACHE, tag + '.c'), exe + f'.{os.getpid()}.tmp'
        with open(ir, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        code, err = run_ctxc(['c', ir, tmp_c])
        os.remove(ir)
        if code != 0:
            raise RuntimeError(f'ctxc exited with {code}: {err}')
        cc, env = compiler()
        rt_obj = runtime_object(cc, env)
        name_def = '-DCTX_PROGRAM_NAME="' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'
        cmd = cc + CFLAGS + ['-I', RT, name_def, tmp_c, rt_obj, '-o', tmp_exe, '-lm']
        cmd += [f'-Wl,--stack,{STACK}'] if os.name == 'nt' else []
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        replace(tmp_c, c)
        if r.returncode != 0:
            raise RuntimeError(f'C compiler failed on {c}:\n{r.stderr}')
        replace(tmp_exe, exe)
    return exe


def runtime_object(cc, env):
    obj = os.path.join(CACHE, 'ctxrt-' + tree_hash()[:16] + '.o')
    if not os.path.exists(obj):
        tmp = obj + f'.{os.getpid()}.tmp'
        r = subprocess.run(cc + CFLAGS + ['-c', os.path.join(RT, 'ctxrt.c'), '-o', tmp],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(f'C compiler failed on ctxrt.c:\n{r.stderr}')
        replace(tmp, obj)
    return obj


def replace(src, dst):
    """Renames src to dst. If another process got there first, keeps theirs."""
    try:
        os.replace(src, dst)
    except OSError:
        if os.path.exists(src):
            os.remove(src)


PANIC = re.compile(r'^(.*?)(?::(\d+):(\d+))?: panic: (.*)$')


def run(checker, out=None, err=None, inp=None, stack_size=None, args=(), name='program'):
    """Like ctxi's run_checked, through the C backend."""
    exe = build(checker, name)
    stdin = b''
    if inp is not None:
        data = inp.read()
        stdin = data.encode() if isinstance(data, str) else data
    env = dict(os.environ, CTX_STACK=str(stack_size or (16 << 20)))
    r = subprocess.run([exe, *args], input=stdin, capture_output=True, env=env)
    code = r.returncode
    if code >= 1 << 31:
        code -= 1 << 32
    stderr = r.stderr
    panic = None
    if code == 134:
        lines = stderr.decode('utf-8', 'replace').rstrip('\n').split('\n')
        m = PANIC.match(lines[-1])
        if m:
            panic = m
            stderr = '\n'.join(lines[:-1]).encode()
            if stderr:
                stderr += b'\n'
    write(out if out is not None else sys.stdout, r.stdout)
    write(err if err is not None else sys.stderr, stderr)
    if panic is not None:
        file, line, col, msg = panic.groups()
        pos = (int(line), int(col), None if file == name else file) if line else None
        raise Panic(msg, pos)
    return code


def write(stream, data):
    if not data:
        return
    buf = getattr(stream, 'buffer', None)
    if buf is not None:
        stream.flush()
        buf.write(data)
        buf.flush()
    elif isinstance(stream, io.TextIOBase):
        stream.write(data.decode('utf-8', 'replace'))
    else:
        stream.write(data)
