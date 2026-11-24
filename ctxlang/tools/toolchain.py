"""Builds ctxc for the current source: what tools/recover.py needs of a harness.

    ctxc = native_ctxc()                          ctxc for the current source, built if needed
    std_files()                                   std's files, with this platform's layer

native_ctxc() compiles the bootstrap, the C of a recent ctxc for this platform's std layer
(bootstrap/ctxc.PLATFORM.c), and has that ctxc compile ctxc's current source. Both are cached
under build/ctxc, by a hash of their inputs. Everything runs through the C compiler: gcc, or
zig cc with CTX_CC=zig.

The tests' harness, which was the rest of this file, is tools/suite, in ctxlang
(tests/README.md): it builds ctxc the same way, under build/suite.
"""

import glob
import hashlib
import os
import shutil
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTXC = os.path.join(ROOT, 'ctxc')
RT = os.path.join(CTXC, 'rt')
# std's platform layers (std/os/PLATFORM, spec §17). Linux's and macOS's each have their sys
# beside std/os/posix, which they share.
PLATFORMS = ('linux', 'macos', 'windows')
HOST = 'windows' if os.name == 'nt' else 'macos' if sys.platform == 'darwin' else 'linux'
BOOT = os.path.join(ROOT, 'bootstrap', f'ctxc.{HOST}.c')
CACHE = os.path.join(ROOT, 'build', 'cbackend')
NATIVE = os.path.join(ROOT, 'build', 'ctxc')
STACK = 256 << 20         # reserved; std's rt checks against CTX_STACK, at most 200 MiB
CTXC_STACK = str(200 << 20)
# No sibling calls: clang makes them at -O1, and a call must take a frame for unbounded
# recursion to overflow the stack rather than loop forever. No strict aliasing: @cast reads memory
# as another type than it was written as, and so does a pointer to a capability passed as one it
# includes, which clang's type-based alias analysis (on at -O1) may assume it doesn't.
CFLAGS = ['-std=gnu11', '-O1', '-w', '-fwrapv', '-fno-optimize-sibling-calls', '-fno-strict-aliasing']
EXE = '.exe' if os.name == 'nt' else ''

_lock = threading.Lock()
_native = None            # path of the native ctxc, once built or found


def std_files(platform=HOST):
    """std's files, then its layer's for platform, relative to ROOT, as the names positions in
    them use."""
    def ctx(*d):
        return sorted(os.path.relpath(p, ROOT).replace(os.sep, '/') for p in glob.glob(os.path.join(ROOT, *d, '*.ctx')))
    shared = [] if platform == 'windows' else ctx('std', 'os', 'posix')
    return ctx('std') + shared + ctx('std', 'os', platform)


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


def ctxc_build(ctxc, out_c, files, cwd=ROOT, platform=HOST):
    """Runs `ctxc build OUT.c STD... -- FILE...` in cwd, with std's files for platform. Returns
    (exit code, stderr text)."""
    std = [os.path.relpath(os.path.join(ROOT, p), cwd).replace(os.sep, '/') for p in std_files(platform)]
    r = subprocess.run([ctxc, 'build', out_c, *std, '--', *files], cwd=cwd,
                       capture_output=True, env=dict(os.environ, CTX_STACK=CTXC_STACK))
    return r.returncode, r.stderr.decode('utf-8', 'replace')


def native_ctxc():
    """The path of a native ctxc for ctxc's current source, building it if it isn't cached.

    The bootstrap is compiled to a seed, and the seed compiles the current source. If that
    gives the bootstrap's C again, the seed is the current ctxc."""
    global _native
    if _native is not None:
        return _native
    with _lock:
        if _native is not None:
            return _native
        os.makedirs(NATIVE, exist_ok=True)
        base = runtime_hash()
        boot = os.path.relpath(BOOT, ROOT).replace(os.sep, '/')
        seed = os.path.join(NATIVE, 'seed-' + digest([boot], base.encode())[:16] + EXE)
        if not os.path.exists(seed):
            tmp = os.path.join(NATIVE, f'seed-{os.getpid()}.c')
            shutil.copyfile(BOOT, tmp)
            link(tmp, os.path.splitext(seed)[0] + '.c', seed, 'ctxc')
        key = digest([boot, *ctxc_files(), *std_files()], base.encode())[:16]
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


def link(tmp_c, c, exe, name):
    """Compiles tmp_c with the runtime into exe, and moves tmp_c to c."""
    tmp_exe = exe + f'.{os.getpid()}.tmp'
    cc, env = compiler()
    rt_objs = [runtime_object(cc, env, n) for n in ('ctxrt', 'ctxfloat', 'ctxthread')]
    name_def = '-DCTX_PROGRAM_NAME="' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'
    cmd = cc + CFLAGS + ['-I', RT, name_def, tmp_c, *rt_objs, '-o', tmp_exe, '-lm']
    if sys.platform.startswith('linux'):
        cmd.append('-lpthread')     # glibc before 2.34 keeps threads in a library of their own
    cmd += stack_flags()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    replace(tmp_c, c)
    if r.returncode != 0:
        raise RuntimeError(f'C compiler failed on {c}:\n{r.stderr}')
    replace(tmp_exe, exe)


def runtime_object(cc, env, name='ctxrt'):
    obj = os.path.join(CACHE, f'{name}-' + runtime_hash()[:16] + '.o')
    if not os.path.exists(obj):
        os.makedirs(CACHE, exist_ok=True)
        tmp = obj + f'.{os.getpid()}.tmp'
        r = subprocess.run(cc + CFLAGS + ['-c', os.path.join(RT, name + '.c'), '-o', tmp],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(f'C compiler failed on {name}.c:\n{r.stderr}')
        replace(tmp, obj)
    return obj


def replace(src, dst):
    """Renames src to dst. If another process got there first, keeps theirs."""
    try:
        os.replace(src, dst)
    except OSError:
        if os.path.exists(src):
            os.remove(src)
