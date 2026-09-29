"""Runtime-provided std functions. Everything else in std is ctxlang source in std/."""

import errno
import math
import os
import struct
from fractions import Fraction

from .checker import NativeFn
from .runtime import TAG, f32r, trap


def _write(rt, nf, args):
    stream = TAG.unpack_from(args['to'], 0)[0]
    addr, n = rt.slice_arg(nf, 'bytes', args['bytes'])
    lo, hi = rt.span(addr, n)
    rt.write(stream, bytes(rt.mem[lo:hi]))


def _read(rt, nf, args):
    addr, n = rt.slice_arg(nf, 'into', args['into'])
    if n == 0:
        return 0
    lo, _ = rt.span(addr, n)
    data = rt.read(n)
    rt.mem[lo:lo + len(data)] = data
    return len(data)


def _float_text(s):
    if s in ('inf', '-inf', 'nan') or any(c in s for c in '.e'):
        return s
    return s + '.0'


def _shortest_f32(v):
    if v != v or v in (float('inf'), float('-inf')):
        return repr(v)
    for p in range(1, 10):
        s = f'{v:.{p}g}'
        if f32r(float(s)) == v:
            return s
    return f'{v:.9g}'


def _digits(fmt):
    def impl(rt, nf, args):
        text = _float_text(fmt(args['n'])).encode('ascii')
        addr, n = rt.slice_arg(nf, 'into', args['into'])
        if len(text) > n:
            trap(f'{len(text)} characters do not fit in a buffer of {n}')
        lo, _ = rt.span(addr, len(text))
        rt.mem[lo:lo + len(text)] = text
        return len(text)
    return impl


def _text_arg(rt, nf, args):
    addr, n = rt.slice_arg(nf, 'text', args['text'])
    if n == 0:
        return ''
    lo, hi = rt.span(addr, n)
    return rt.mem[lo:hi].decode('ascii')


def _parse_f64(rt, nf, args):
    return float(_text_arg(rt, nf, args))


def _parse_f32(rt, nf, args):
    """Rounds the decimal text to the nearest f32 directly, not via f64.

    Rounding to f64 first and then to f32 is correct unless the f64 lands exactly halfway between
    two f32s. Then the exact decimal decides which way to go.
    """
    text = _text_arg(rt, nf, args)
    d = float(text)
    f = f32r(d)
    if f == d or math.isinf(f) or math.isnan(d):
        return f
    bits = struct.unpack('<I', struct.pack('<f', f))[0]
    step = 1 if abs(d) > abs(f) else -1
    other = struct.unpack('<f', struct.pack('<I', bits + step))[0]
    if (f + other) / 2 != d:
        return f
    exact, mid = Fraction(text), Fraction(d)
    if exact == mid:
        return f                     # a true tie: f32r already rounded to even
    toward_other = (exact > mid) == (other > d)
    return other if toward_other else f


# ---- fs: every native returns a status. >= 0 is a result (handle, count, size); < 0 an error.

FS_ERRORS = [   # (exception, code); std/fs.ctx maps each code to an fs::Error variant
    (FileNotFoundError, -1), (PermissionError, -2), (IsADirectoryError, -3),
    (FileExistsError, -4), (NotADirectoryError, -5),
]
BAD_FILE = -6
OTHER = -1000      # OTHER - errno, for anything else
OPEN_MODES = {0: 'rb', 1: 'wb', 2: 'ab', 3: 'xb'}   # fs::Mode: read, write, append, create


def _fs(impl):
    def run(rt, nf, args):
        try:
            return impl(rt, nf, args)
        except OSError as e:
            for exc, code in FS_ERRORS:
                if isinstance(e, exc):
                    return code
            return OTHER - (e.errno or 0)
    return run


def _path(rt, nf, args):
    addr, n = rt.slice_arg(nf, 'path', args['path'])
    if n == 0:
        raise FileNotFoundError(errno.ENOENT, 'empty path')
    lo, hi = rt.span(addr, n)
    return os.fsdecode(bytes(rt.mem[lo:hi]))


def _file(rt, args):
    return rt.files.get(args['file'])


@_fs
def _open(rt, nf, args):
    mode = OPEN_MODES.get(args['mode'])
    if mode is None:
        trap(f"invalid open mode {args['mode']}")
    path = _path(rt, nf, args)
    if os.path.isdir(path):
        raise IsADirectoryError(errno.EISDIR, path)   # Windows reports this as PermissionError
    f = open(path, mode, buffering=0)
    h = rt.next_file
    rt.next_file += 1
    rt.files[h] = f
    return h


@_fs
def _fread(rt, nf, args):
    f = _file(rt, args)
    if f is None:
        return BAD_FILE
    addr, n = rt.slice_arg(nf, 'into', args['into'])
    if n == 0:
        return 0
    lo, _ = rt.span(addr, n)
    data = f.read(n)
    rt.mem[lo:lo + len(data)] = data
    return len(data)


@_fs
def _fwrite(rt, nf, args):
    f = _file(rt, args)
    if f is None:
        return BAD_FILE
    addr, n = rt.slice_arg(nf, 'bytes', args['bytes'])
    if n == 0:
        return 0
    lo, hi = rt.span(addr, n)
    return f.write(bytes(rt.mem[lo:hi]))


@_fs
def _close(rt, nf, args):
    f = rt.files.pop(args['file'], None)
    if f is None:
        return BAD_FILE
    f.close()
    return 0


@_fs
def _size(rt, nf, args):
    path = _path(rt, nf, args)
    if os.path.isdir(path):
        raise IsADirectoryError(errno.EISDIR, path)
    return os.stat(path).st_size


@_fs
def _remove(rt, nf, args):
    path = _path(rt, nf, args)
    if os.path.isdir(path):
        raise IsADirectoryError(errno.EISDIR, path)
    os.remove(path)
    return 0


def natives():
    return [
        NativeFn(('io',), 'write',
                 [('io', True, 'Io'), ('to', False, 'Stream'), ('bytes', False, 'slice::Slice(u8)')],
                 None, _write),
        NativeFn(('io',), 'read',
                 [('io', True, 'Io'), ('into', False, 'slice::Slice(u8)')], 'usize', _read),
        NativeFn(('ascii',), 'f64_digits',
                 [('n', False, 'f64'), ('into', False, 'slice::Slice(u8)')], 'usize', _digits(repr)),
        NativeFn(('ascii',), 'f32_digits',
                 [('n', False, 'f32'), ('into', False, 'slice::Slice(u8)')], 'usize',
                 _digits(_shortest_f32)),
        NativeFn(('fs',), 'sys_open',
                 [('fs', True, 'Fs'), ('path', False, 'slice::Slice(u8)'), ('mode', False, 'u8')],
                 'i64', _open),
        NativeFn(('fs',), 'sys_read',
                 [('fs', True, 'Fs'), ('file', False, 'u32'), ('into', False, 'slice::Slice(u8)')],
                 'i64', _fread),
        NativeFn(('fs',), 'sys_write',
                 [('fs', True, 'Fs'), ('file', False, 'u32'), ('bytes', False, 'slice::Slice(u8)')],
                 'i64', _fwrite),
        NativeFn(('fs',), 'sys_close', [('fs', True, 'Fs'), ('file', False, 'u32')], 'i64', _close),
        NativeFn(('fs',), 'sys_size',
                 [('fs', True, 'Fs'), ('path', False, 'slice::Slice(u8)')], 'i64', _size),
        NativeFn(('fs',), 'sys_remove',
                 [('fs', True, 'Fs'), ('path', False, 'slice::Slice(u8)')], 'i64', _remove),
        NativeFn(('ascii',), 'f64_parse', [('text', False, 'slice::Slice(u8)')], 'f64', _parse_f64),
        NativeFn(('ascii',), 'f32_parse', [('text', False, 'slice::Slice(u8)')], 'f32', _parse_f32),
    ]
