"""A minimal GFF V3.2 reader for probes (not used by the game).

    python kotor/tools/py/gffpy.py FILE|RESREF.EXT      dump a GFF as indented text

As a library:

    import gffpy
    root = gffpy.read(data)          # Struct; raises gffpy.GffError on malformed input
    root.type                        # struct id (0xFFFFFFFF for the top-level struct)
    root.fields                      # list of Field(label, type, value)
    root['Tag']                      # value of a field (KeyError if absent)
    root.get('Tag', default)

Values by field type: integers and floats as Python numbers, CExoString as str (latin-1),
ResRef as str, CExoLocString as LocString(strref, {substring id: str}), VOID as bytes,
Struct as Struct, List as [Struct], Orientation as a 4-tuple, Vector as a 3-tuple,
StrRef (type 18) as int.

The layout follows BioWare's published "Generic File Format" document: an 8-byte signature
(file type and "V3.2"), twelve u32s giving offset and count of the struct, field, label,
field-data, field-indices and list-indices arrays, then those arrays.
"""

import struct
import sys
from collections import namedtuple

TYPE_NAMES = {
    0: 'BYTE', 1: 'CHAR', 2: 'WORD', 3: 'SHORT', 4: 'DWORD', 5: 'INT', 6: 'DWORD64', 7: 'INT64',
    8: 'FLOAT', 9: 'DOUBLE', 10: 'CExoString', 11: 'ResRef', 12: 'CExoLocString', 13: 'VOID',
    14: 'Struct', 15: 'List', 16: 'Orientation', 17: 'Vector', 18: 'StrRef',
}

# Simple types keep their value in the field's 4-byte data slot.
_SIMPLE = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i', 8: '<f'}

Field = namedtuple('Field', 'label type value')
LocString = namedtuple('LocString', 'strref strings')


class GffError(ValueError):
    pass


class Struct:
    __slots__ = ('type', 'fields')

    def __init__(self, stype, fields):
        self.type = stype
        self.fields = fields

    def __getitem__(self, label):
        for f in self.fields:
            if f.label == label:
                return f.value
        raise KeyError(label)

    def get(self, label, default=None):
        for f in self.fields:
            if f.label == label:
                return f.value
        return default

    def field(self, label):
        for f in self.fields:
            if f.label == label:
                return f
        return None

    def labels(self):
        return [f.label for f in self.fields]

    def __repr__(self):
        return f'Struct({self.type}, {len(self.fields)} fields)'


def read_header(data):
    if len(data) < 56:
        raise GffError('shorter than the 56-byte header')
    ftype = data[:4].decode('latin-1')
    version = data[4:8].decode('latin-1')
    if version != 'V3.2':
        raise GffError(f'version {version!r}, expected V3.2')
    return ftype, struct.unpack_from('<12I', data, 8)


def read(data):
    """Parse a whole GFF; returns the top-level Struct. Attribute .file_type is not set; use
    read_header for it."""
    _ftype, h = read_header(data)
    (s_off, s_cnt, f_off, f_cnt, l_off, l_cnt,
     fd_off, fd_len, fi_off, fi_len, li_off, li_len) = h
    n = len(data)
    for off, size in ((s_off, 12 * s_cnt), (f_off, 12 * f_cnt), (l_off, 16 * l_cnt),
                      (fd_off, fd_len), (fi_off, fi_len), (li_off, li_len)):
        if off + size > n:
            raise GffError('an array runs past the end of the file')
    if s_cnt == 0:
        raise GffError('no structs')
    labels = [data[l_off + 16 * i:l_off + 16 * i + 16].split(b'\0', 1)[0].decode('latin-1')
              for i in range(l_cnt)]

    def fdata(off, size):
        if off + size > fd_len:
            raise GffError('field data out of range')
        return data[fd_off + off:fd_off + off + size]

    def u32_fd(off):
        return struct.unpack('<I', fdata(off, 4))[0]

    def read_field(i, depth):
        if i >= f_cnt:
            raise GffError(f'field index {i} out of range')
        ftype, lab, slot = struct.unpack_from('<3I', data, f_off + 12 * i)
        if lab >= l_cnt:
            raise GffError(f'label index {lab} out of range')
        raw_slot = data[f_off + 12 * i + 8:f_off + 12 * i + 12]
        if ftype in _SIMPLE:
            v = struct.unpack_from(_SIMPLE[ftype], raw_slot)[0]
        elif ftype == 6:
            v = struct.unpack('<Q', fdata(slot, 8))[0]
        elif ftype == 7:
            v = struct.unpack('<q', fdata(slot, 8))[0]
        elif ftype == 9:
            v = struct.unpack('<d', fdata(slot, 8))[0]
        elif ftype == 10:
            size = u32_fd(slot)
            v = fdata(slot + 4, size).decode('latin-1')
        elif ftype == 11:
            size = fdata(slot, 1)[0]
            v = fdata(slot + 1, size).decode('latin-1')
        elif ftype == 12:
            total = u32_fd(slot)
            strref, count = struct.unpack('<iI', fdata(slot + 4, 8))
            p = slot + 12
            strings = {}
            for _ in range(count):
                sid, size = struct.unpack('<II', fdata(p, 8))
                strings[sid] = fdata(p + 8, size).decode('latin-1')
                p += 8 + size
            if p - slot - 4 != total:
                raise GffError('CExoLocString size disagrees with its substrings')
            v = LocString(strref, strings)
        elif ftype == 13:
            size = u32_fd(slot)
            v = fdata(slot + 4, size)
        elif ftype == 14:
            v = read_struct(slot, depth + 1)
        elif ftype == 15:
            if slot + 4 > li_len:
                raise GffError('list offset out of range')
            count = struct.unpack_from('<I', data, li_off + slot)[0]
            if slot + 4 + 4 * count > li_len:
                raise GffError('list runs past the list indices')
            idx = struct.unpack_from(f'<{count}I', data, li_off + slot + 4)
            v = [read_struct(k, depth + 1) for k in idx]
        elif ftype == 16:
            v = struct.unpack('<4f', fdata(slot, 16))
        elif ftype == 17:
            v = struct.unpack('<3f', fdata(slot, 12))
        elif ftype == 18:
            # StrRef: in TSL-era files a u32 size then the strref; KOTOR 1 never uses it.
            v = struct.unpack('<I', fdata(slot + 4, 4))[0]
        else:
            raise GffError(f'unknown field type {ftype}')
        return Field(labels[lab], ftype, v)

    def read_struct(i, depth):
        if i >= s_cnt:
            raise GffError(f'struct index {i} out of range')
        if depth > 64:
            raise GffError('structs nest too deep (cycle?)')
        stype, slot, count = struct.unpack_from('<3I', data, s_off + 12 * i)
        if count == 0:
            idx = ()
        elif count == 1:
            idx = (slot,)
        else:
            if slot + 4 * count > fi_len:
                raise GffError('struct field indices out of range')
            idx = struct.unpack_from(f'<{count}I', data, fi_off + slot)
        return Struct(stype, [read_field(k, depth) for k in idx])

    return read_struct(0, 0)


def _fmt(v):
    if isinstance(v, LocString):
        return f'strref={v.strref} {dict(v.strings)!r}'
    if isinstance(v, bytes):
        return f'<{len(v)} bytes> {v[:32].hex()}'
    if isinstance(v, float):
        return f'{v:g}'
    return repr(v)


def dump(s, out, indent=0):
    pad = '  ' * indent
    for f in s.fields:
        t = TYPE_NAMES.get(f.type, str(f.type))
        if f.type == 14:
            out.write(f'{pad}{f.label}: Struct id={f.value.type}\n')
            dump(f.value, out, indent + 1)
        elif f.type == 15:
            out.write(f'{pad}{f.label}: List[{len(f.value)}]\n')
            for k, e in enumerate(f.value):
                out.write(f'{pad}  [{k}] id={e.type}\n')
                dump(e, out, indent + 2)
        else:
            out.write(f'{pad}{f.label}: {t} = {_fmt(f.value)}\n')


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    name = argv[0]
    try:
        with open(name, 'rb') as fh:
            data = fh.read()
    except OSError:
        import kres
        resref, _, ext = name.rpartition('.')
        data = kres.Game().get(resref, ext.lower())
        if data is None:
            print(f'{name}: not found', file=sys.stderr)
            return 1
    ftype, _ = read_header(data)
    sys.stdout.write(f'# {ftype.strip()} V3.2\n')
    dump(read(data), sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
