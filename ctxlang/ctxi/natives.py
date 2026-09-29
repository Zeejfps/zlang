"""Runtime-provided std functions. Everything else in std is ctxlang source in std/."""

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
    ]
