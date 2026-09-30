"""Builds and runs ctxlang programs with the native ctxc: the harness for the tests and tools.

    ctxc = native_ctxc()                          ctxc for the current source, built if needed
    exe = build_sources([(src, 'user.ctx')])      an executable, or CompileError
    run_source(src, out=..., args=[...])          builds and runs; raises Panic or CompileError

native_ctxc() compiles bootstrap/ctxc.c, the C of a recent ctxc, and has that ctxc compile ctxc's
current source. Both are cached under build/ctxc, by a hash of their inputs. A program's C goes
to build/progs and its executable to build/cbackend, cached by a hash of the C. Everything runs
through the C compiler: gcc, or zig cc with CTX_CC=zig.

A program's files are written to build/progs/HASH/, each under the name its positions use when
that is a relative path, and positions are mapped back to the names given: a file with no name is
written as mainN.ctx, and its positions have no file (None).
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTXC = os.path.join(ROOT, 'ctxc')
RT = os.path.join(CTXC, 'rt')
BOOT = os.path.join(ROOT, 'bootstrap', 'ctxc.c')
CACHE = os.path.join(ROOT, 'build', 'cbackend')
PROGS = os.path.join(ROOT, 'build', 'progs')
NATIVE = os.path.join(ROOT, 'build', 'ctxc')
STACK = 256 << 20         # reserved; ctxrt.c checks against CTX_STACK, at most 200 MiB
CTXC_STACK = str(200 << 20)
# No sibling calls: clang makes them at -O1, and a call must take a frame for unbounded
# recursion to overflow the stack rather than loop forever.
CFLAGS = ['-std=gnu11', '-O1', '-w', '-fwrapv', '-fno-optimize-sibling-calls']
EXE = '.exe' if os.name == 'nt' else ''

_lock = threading.Lock()
_native = None            # path of the native ctxc, once built or found


class CompileError(Exception):
    """ctxc's first error. pos is (line, column, file), file None for a file with no name. text
    is everything ctxc printed: every error."""

    def __init__(self, msg, pos=None, text=''):
        super().__init__(msg)
        self.msg, self.pos, self.text = msg, pos, text


class Panic(Exception):
    """A panic in a program, at (line, column, file), or at no position."""

    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg, self.pos = msg, pos


# ---- ctxc itself

def std_files():
    """std's files, relative to ROOT, as the names positions in them use."""
    return sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(ROOT, 'std', '*.ctx')))


def ctxc_files():
    return sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(CTXC, '*.ctx')))


def digest(paths, extra=b''):
    h = hashlib.sha256(extra)
    for path in paths:
        with open(os.path.join(ROOT, path), 'rb') as f:
            h.update(path.encode() + b'\0' + f.read())
    return h.hexdigest()


def runtime_hash():
    """What every executable depends on besides its C: the runtime and how it is compiled."""
    rt = sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(RT, '*')))
    return digest(rt, repr((CFLAGS, stack_flags(), os.environ.get('CTX_CC'))).encode())


def compiler():
    """The C compiler command, and the environment to run it in."""
    env = dict(os.environ)
    if os.environ.get('CTX_CC') == 'zig':
        return ['zig', 'cc'], env
    for name in ('gcc', 'cc', 'clang'):
        cc = shutil.which(name)
        if cc is not None:
            break
    else:
        raise RuntimeError('no C compiler: install gcc or clang, or set CTX_CC=zig')
    # Its own directory first, so MinGW's cc1 finds its DLLs before any other MinGW's (Git Bash's).
    env['PATH'] = os.path.dirname(cc) + os.pathsep + env.get('PATH', '')
    return [cc], env


def stack_flags():
    """Linker flags that reserve STACK bytes for the main thread."""
    if os.name == 'nt':
        return [f'-Wl,--stack,{STACK}']
    if sys.platform == 'darwin':
        return [f'-Wl,-stack_size,{STACK:#x}']
    return []


def program_args(files, cwd):
    """`STD... -- FILE...`, with std's files relative to cwd."""
    std = [os.path.relpath(os.path.join(ROOT, p), cwd).replace(os.sep, '/') for p in std_files()]
    return [*std, '--', *files]


def ctxc_build(ctxc, out_c, files, cwd=ROOT):
    """Runs `ctxc build OUT.c STD... -- FILE...` in cwd. Returns (exit code, stderr text)."""
    r = subprocess.run([ctxc, 'build', out_c, *program_args(files, cwd)], cwd=cwd,
                       capture_output=True, env=dict(os.environ, CTX_STACK=CTXC_STACK))
    return r.returncode, r.stderr.decode('utf-8', 'replace')


def native_ctxc():
    """The path of a native ctxc for ctxc's current source, building it if it isn't cached.

    bootstrap/ctxc.c is compiled to a seed, and the seed compiles the current source. If that
    gives the bootstrap's C again, the seed is the current ctxc."""
    global _native
    if _native is not None:
        return _native
    with _lock:
        if _native is not None:
            return _native
        os.makedirs(NATIVE, exist_ok=True)
        base = runtime_hash()
        seed = os.path.join(NATIVE, 'seed-' + digest(['bootstrap/ctxc.c'], base.encode())[:16] + EXE)
        if not os.path.exists(seed):
            tmp = os.path.join(NATIVE, f'seed-{os.getpid()}.c')
            shutil.copyfile(BOOT, tmp)
            link(tmp, os.path.splitext(seed)[0] + '.c', seed, 'ctxc')
        key = digest(['bootstrap/ctxc.c', *ctxc_files(), *std_files()], base.encode())[:16]
        exe = os.path.join(NATIVE, 'ctxc-' + key + EXE)
        if not os.path.exists(exe):
            tmp = os.path.join(NATIVE, f'ctxc-{os.getpid()}.c')
            code, err = ctxc_build(seed, tmp, ctxc_files())
            if code != 0:
                raise RuntimeError(f"the bootstrap ctxc can't compile ctxc's source:\n{err[:4000]}")
            with open(tmp, 'rb') as f, open(BOOT, 'rb') as g:
                same = f.read() == g.read()
            if same:
                os.remove(tmp)
                shutil.copy2(seed, exe)
            else:
                link(tmp, os.path.splitext(exe)[0] + '.c', exe, 'ctxc')
        _native = exe
    return _native


# ---- building programs

def link(tmp_c, c, exe, name):
    """Compiles tmp_c with the runtime into exe, and moves tmp_c to c."""
    tmp_exe = exe + f'.{os.getpid()}.tmp'
    cc, env = compiler()
    rt_obj = runtime_object(cc, env)
    name_def = '-DCTX_PROGRAM_NAME="' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'
    cmd = cc + CFLAGS + ['-I', RT, name_def, tmp_c, rt_obj, '-o', tmp_exe, '-lm']
    cmd += stack_flags()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    replace(tmp_c, c)
    if r.returncode != 0:
        raise RuntimeError(f'C compiler failed on {c}:\n{r.stderr}')
    replace(tmp_exe, exe)


def runtime_object(cc, env):
    obj = os.path.join(CACHE, 'ctxrt-' + runtime_hash()[:16] + '.o')
    if not os.path.exists(obj):
        os.makedirs(CACHE, exist_ok=True)
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


def names(sources):
    """{name written: name given} for a program's (source, file) pairs, in order. A relative name
    stays as it is; a missing or absolute one, or one that leaves the directory, becomes mainN.ctx
    or fileN/BASENAME."""
    out = {}
    for i, (_, f) in enumerate(sources):
        if not f:
            out[f'main{i}.ctx'] = None
        elif os.path.isabs(f) or '..' in re.split(r'[\\/]', f):
            out[f'file{i}/{os.path.basename(f)}'] = f
        else:
            out[f.replace(os.sep, '/')] = f
    return out


def write_program(sources):
    """Writes a program's files under build/progs. Returns the directory and names(sources)."""
    files = names(sources)
    h = hashlib.sha256(repr(sorted(zip(files, (s for s, _ in sources)))).encode()).hexdigest()[:24]
    d = os.path.join(PROGS, h)
    for (src, _), f in zip(sources, files):
        path = os.path.join(d, f)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as out:
            out.write(src)
    return d, files


def build_sources(sources, name='program'):
    """The path of an executable for a program of (source, file) pairs, and {name written: name
    given} for its files. Raises CompileError."""
    d, files = write_program(sources)
    return build_files(list(files), cwd=d, name=name, given=files), files


def ir_sources(sources):
    """The typed IR of a program of (source, file) pairs, from `ctxc ir`. Raises CompileError."""
    d, files = write_program(sources)
    r = subprocess.run([native_ctxc(), 'ir', *program_args(list(files), d)], cwd=d,
                       capture_output=True, env=dict(os.environ, CTX_STACK=CTXC_STACK))
    text = r.stdout.decode('utf-8')
    if r.returncode != 0:
        raise CompileError(text.strip())
    return text


def build_files(files, cwd=ROOT, name='program', given=None):
    """The path of an executable for the program of files, relative to cwd. Raises CompileError,
    with its file renamed by given."""
    ctxc = native_ctxc()
    os.makedirs(CACHE, exist_ok=True)
    tmp_c = os.path.join(CACHE, f'tmp-{os.getpid()}-{threading.get_ident()}.c')
    code, err = ctxc_build(ctxc, tmp_c, files, cwd)
    if code == 1 and not os.path.exists(tmp_c):
        raise first_error(err, given)
    if code != 0:
        raise RuntimeError(f'ctxc build exited with {code}:\n{err[:4000]}')
    with open(tmp_c, 'rb') as f:
        key = hashlib.sha256((runtime_hash() + '\0' + name + '\0').encode() + f.read()).hexdigest()[:24]
    exe = os.path.join(CACHE, key + EXE)
    if os.path.exists(exe):
        os.remove(tmp_c)
    else:
        link(tmp_c, os.path.join(CACHE, key + '.c'), exe, name)
    return exe


ERROR = re.compile(r'^(.*):(\d+):(\d+): error: (.*)$')


def first_error(stderr, given=None):
    """The first error of `ctxc build`'s output. A message may run over several lines."""
    lines = stderr.replace('\r\n', '\n').rstrip('\n').split('\n')
    m = ERROR.match(lines[0])
    if not m:
        return CompileError(stderr.strip(), text=stderr)
    file, line, col, msg = m.groups()
    rest = []
    for more in lines[1:]:
        if ERROR.match(more):
            break
        rest.append(more)
    msg = '\n'.join([msg, *rest])
    return CompileError(msg, (int(line), int(col), rename(file, given)), stderr)


def rename(file, given):
    """The name a position's file was given: by given, and std's as std/NAME.ctx."""
    if given and file in given:
        return given[file]
    m = STD_FILE.fullmatch(file)
    return m.group(1) if m else file


STD_FILE = re.compile(r'(?:\.\./)*(std/[^/]+\.ctx)')


# ---- running programs

PANIC = re.compile(r'^(.*?)(?::(\d+):(\d+))?: panic: (.*)$')


def run_source(src, file=None, **kw):
    """Builds and runs a program. Returns its exit code: what main returns, or 0."""
    return run_sources([(src, file)], **kw)


def run_sources(sources, out=None, err=None, inp=None, stack_size=16 << 20, args=(), timeout=None):
    """Like run_source, for a program of several (source, file) pairs."""
    exe, given = build_sources(sources)
    return run_exe(exe, out=out, err=err, inp=inp, stack_size=stack_size, args=args, given=given,
                   timeout=timeout)


def run_exe(exe, out=None, err=None, inp=None, stack_size=None, args=(), name='program',
            given=None, timeout=None):
    """Runs an executable with the given streams. Returns its exit code, or raises Panic.
    Raises subprocess.TimeoutExpired if it runs longer than timeout seconds."""
    stdin = b''
    if inp is not None:
        data = inp.read()
        stdin = data.encode() if isinstance(data, str) else data
    env = dict(os.environ, CTX_STACK=str(stack_size or (16 << 20)))
    r = subprocess.run([exe, *args], input=stdin, capture_output=True, env=env, timeout=timeout)
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
        pos = (int(line), int(col), None if file == name else rename(file, given)) if line else None
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


def read_program(path):
    """The (source, file) pairs of a program: one file, or every .ctx file in a directory. Each
    file is named by its path relative to ROOT."""
    if os.path.isdir(path):
        paths = sorted(glob.glob(os.path.join(path, '*.ctx')))
        if not paths:
            raise CompileError('no .ctx files in directory', (0, 0, path))
    else:
        paths = [path]
    sources = []
    for p in paths:
        with open(p, encoding='utf-8', newline='') as f:
            sources.append((f.read(), os.path.relpath(p, ROOT).replace(os.sep, '/')))
    return sources
