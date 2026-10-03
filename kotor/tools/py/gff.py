"""GFF V3.2 reader and writer, for exploration and probes (not used by the game).

    python kotor/tools/py/gff.py dump FILE|RESREF.EXT     print a GFF as an indented tree
    python kotor/tools/py/gff.py roundtrip FILE|RESREF.EXT  write it back and compare

As a library:

    import gff
    g = gff.read(data)                    # Gff(tag, root); raises GffError on malformed data
    g.root.get('Tag')                     # value of a field by label (None if absent)
    data = gff.write(g)                   # the engine's save layout (see docs/formats/gff.md)
    data = gff.write(g, order='keep', fi='struct')   # reproduce a toolset-built file

A read tree is a Struct (id, fields) whose fields are Field(label, type, value). Values: ints for
the integer types, float for FLOAT/DOUBLE, bytes for CExoString/ResRef/VOID, LocString, Struct for
STRUCT, list of Struct for LIST, tuples of floats for ORIENTATION (4) and VECTOR (3). Every struct
and field remembers its position in the file (`index`) so `order='keep'` can rebuild the original
creation order.

Writer options (all three together decide the bytes; the reasons are in gff.md):
    order  'dfs'           structs and fields created depth-first, a list's elements created and
                           filled one after another (most files, and the engine's saves)
           'elements'      depth-first, but all of a list's element structs are created before the
                           first is filled (the ITP palettes)
           'keep'          the order the file was read in (index of every struct and field)
    fi     'second'        a struct's field-indices block is placed when it gets its 2nd field and
                           grows in place (the engine's saves)
           'struct'        blocks in struct-array order (most toolset-built files)
           'move'          placed at the 2nd field, moved to the end when it must grow and is not
                           last, the old copy left behind as dead bytes
    li     'field'         a list's block is placed when the list field is created and grows in place
           'move'          as fi='move', for list blocks
"""

import os
import struct
import sys

BYTE, CHAR, WORD, SHORT, DWORD, INT, DWORD64, INT64, FLOAT, DOUBLE = range(10)
CEXOSTRING, RESREF, LOCSTRING, VOID, STRUCT, LIST, ORIENTATION, VECTOR = range(10, 18)

TYPE_NAMES = ['BYTE', 'CHAR', 'WORD', 'SHORT', 'DWORD', 'INT', 'DWORD64', 'INT64', 'FLOAT',
              'DOUBLE', 'CExoString', 'CResRef', 'CExoLocString', 'VOID', 'Struct', 'List',
              'Orientation', 'Vector']

HEADER_SIZE = 56
NO_FIELDS = 0xFFFFFFFF      # DataOrDataOffset of a struct with no fields
TOP_STRUCT_ID = 0xFFFFFFFF

_FIXED = {DWORD64: '<Q', INT64: '<q', DOUBLE: '<d', ORIENTATION: '<4f', VECTOR: '<3f'}


class GffError(ValueError):
    pass


class LocString:
    """A CExoLocString: a dialog.tlk StrRef (-1 for none) and (string_id, bytes) substrings, where
    string_id = language * 2 + gender."""
    __slots__ = ('strref', 'strings')

    def __init__(self, strref=-1, strings=None):
        self.strref = strref
        self.strings = list(strings or [])

    def __eq__(self, other):
        return isinstance(other, LocString) and (self.strref, self.strings) == (other.strref, other.strings)

    def __repr__(self):
        return f'LocString({self.strref}, {self.strings!r})'


class Field:
    __slots__ = ('label', 'type', 'value', 'index')

    def __init__(self, label, type, value, index=None):
        self.label, self.type, self.value, self.index = label, type, value, index

    def __repr__(self):
        return f'Field({self.label!r}, {TYPE_NAMES[self.type]}, {self.value!r})'


class Struct:
    __slots__ = ('id', 'fields', 'index')

    def __init__(self, id=0, fields=None, index=None):
        self.id, self.fields, self.index = id, list(fields or []), index

    def field(self, label):
        for f in self.fields:
            if f.label == label:
                return f
        return None

    def get(self, label, default=None):
        f = self.field(label)
        return default if f is None else f.value

    def __repr__(self):
        return f'Struct({self.id}, {len(self.fields)} fields)'


class Gff:
    __slots__ = ('tag', 'root')

    def __init__(self, tag, root):
        self.tag, self.root = tag, root


# ---------------------------------------------------------------------------------------------
# Reading

def read(data):
    """Parse GFF V3.2 bytes into a Gff tree. Follows offsets only, so dead bytes left by
    incremental writers are ignored. Raises GffError on anything malformed."""
    if len(data) < HEADER_SIZE:
        raise GffError('shorter than the 56-byte header')
    tag, version = data[0:4], data[4:8]
    if version != b'V3.2':
        raise GffError(f'version {version!r}, expected V3.2')
    h = struct.unpack_from('<12I', data, 8)
    so, sc, fo, fc, lo, lc, do, dc, fio, fic, lio, lic = h
    for name, off, size in (('struct', so, 12 * sc), ('field', fo, 12 * fc), ('label', lo, 16 * lc),
                            ('field data', do, dc), ('field indices', fio, fic),
                            ('list indices', lio, lic)):
        if off + size > len(data):
            raise GffError(f'{name} section [{off}, +{size}) runs past the end ({len(data)})')
    if sc < 1:
        raise GffError('no top-level struct')
    if fic % 4 or lic % 4:
        raise GffError('field/list indices size not a multiple of 4')
    structs = [struct.unpack_from('<3I', data, so + 12 * i) for i in range(sc)]
    fields = [struct.unpack_from('<3I', data, fo + 12 * i) for i in range(fc)]
    labels = []
    for i in range(lc):
        raw = data[lo + 16 * i:lo + 16 * i + 16]
        labels.append(raw.split(b'\0', 1)[0].decode('latin-1'))
    fdata = data[do:do + dc]
    findices = data[fio:fio + fic]
    lindices = data[lio:lio + lic]

    seen_structs = set()
    seen_fields = set()

    def u32(buf, off, what):
        if off + 4 > len(buf):
            raise GffError(f'{what} at {off} out of bounds')
        return struct.unpack_from('<I', buf, off)[0]

    def take(off, n, what):
        if off + n > len(fdata):
            raise GffError(f'{what} at field data {off}+{n} out of bounds ({len(fdata)})')
        return fdata[off:off + n]

    def read_field(fi):
        if fi >= fc:
            raise GffError(f'field index {fi} out of range ({fc})')
        if fi in seen_fields:
            raise GffError(f'field {fi} referenced twice')
        seen_fields.add(fi)
        t, li, dd = fields[fi]
        if li >= lc:
            raise GffError(f'label index {li} out of range ({lc})')
        label = labels[li]
        if t == BYTE:
            v = dd & 0xFF
        elif t == CHAR:
            v = (dd & 0xFF) - ((dd & 0x80) << 1)
        elif t == WORD:
            v = dd & 0xFFFF
        elif t == SHORT:
            v = (dd & 0xFFFF) - ((dd & 0x8000) << 1)
        elif t == DWORD:
            v = dd
        elif t == INT:
            v = dd - ((dd & 0x80000000) << 1)
        elif t == FLOAT:
            v = struct.unpack('<f', struct.pack('<I', dd))[0]
        elif t in _FIXED:
            fmt = _FIXED[t]
            v = struct.unpack(fmt, take(dd, struct.calcsize(fmt), TYPE_NAMES[t]))
            v = v[0] if len(v) == 1 else v
        elif t in (CEXOSTRING, VOID):
            n = u32(fdata, dd, TYPE_NAMES[t])
            v = take(dd + 4, n, TYPE_NAMES[t])
        elif t == RESREF:
            n = take(dd, 1, 'ResRef')[0]
            v = take(dd + 1, n, 'ResRef')
        elif t == LOCSTRING:
            total = u32(fdata, dd, 'LocString size')
            body = take(dd + 4, total, 'LocString')
            if total < 8:
                raise GffError('LocString shorter than its StrRef and count')
            strref, count = struct.unpack_from('<iI', body, 0)
            p, strings = 8, []
            for _ in range(count):
                if p + 8 > total:
                    raise GffError('LocString substring header out of bounds')
                sid, n = struct.unpack_from('<iI', body, p)
                if p + 8 + n > total:
                    raise GffError('LocString substring out of bounds')
                strings.append((sid, body[p + 8:p + 8 + n]))
                p += 8 + n
            if p != total:
                raise GffError(f'LocString size {total} but substrings end at {p}')
            v = LocString(strref, strings)
        elif t == STRUCT:
            v = read_struct(dd)
        elif t == LIST:
            if dd % 4:
                raise GffError(f'list offset {dd} not a multiple of 4')
            n = u32(lindices, dd, 'list size')
            if dd + 4 + 4 * n > len(lindices):
                raise GffError(f'list at {dd} with {n} elements out of bounds')
            v = [read_struct(s) for s in struct.unpack_from(f'<{n}I', lindices, dd + 4)]
        else:
            raise GffError(f'field {fi} ({label}) has unknown type {t}')
        return Field(label, t, v, fi)

    def read_struct(si):
        if si >= sc:
            raise GffError(f'struct index {si} out of range ({sc})')
        if si in seen_structs:
            raise GffError(f'struct {si} referenced twice (shared or cyclic)')
        seen_structs.add(si)
        sid, dd, n = structs[si]
        if n == 0:
            ids = []
        elif n == 1:
            ids = [dd]
        else:
            if dd % 4 or dd + 4 * n > len(findices):
                raise GffError(f'struct {si}: field indices at {dd} x{n} out of bounds')
            ids = struct.unpack_from(f'<{n}I', findices, dd)
        return Struct(sid, [read_field(fi) for fi in ids], si)

    try:
        root = read_struct(0)
    except RecursionError:
        raise GffError('structs nested too deeply') from None
    return Gff(tag.decode('latin-1'), root)


# ---------------------------------------------------------------------------------------------
# Writing

def write(g, order='dfs', fi='second', li='field'):
    """Serialize a Gff tree. The defaults give the layout the engine uses for its save files."""
    plan = plan_layout(g, order)
    return serialize(g, plan, fi, li)


class Plan:
    """Creation order: structs and fields in array order, plus the merged event timeline that the
    'move' layouts replay (('F', field_index) and ('S', struct_index) in creation order)."""
    __slots__ = ('structs', 'fields', 'owner', 'parent_list', 'events')


def plan_layout(g, order='dfs'):
    if order == 'keep':
        return _plan_keep(g)
    if order not in ('dfs', 'elements'):
        raise ValueError(f'unknown order {order!r}')
    p = Plan()
    p.structs, p.fields, p.owner, p.parent_list, p.events = [], [], [], [], []

    def new_struct(s, parent_list):
        p.events.append(('S', len(p.structs)))
        p.structs.append(s)
        p.parent_list.append(parent_list)

    def visit(s, si):
        for f in s.fields:
            fi = len(p.fields)
            p.events.append(('F', fi))
            p.fields.append(f)
            p.owner.append(si)
            if f.type == STRUCT:
                ci = len(p.structs)
                new_struct(f.value, None)
                visit(f.value, ci)
            elif f.type == LIST:
                if order == 'elements':
                    first = len(p.structs)
                    for el in f.value:
                        new_struct(el, fi)
                    for k, el in enumerate(f.value):
                        visit(el, first + k)
                else:
                    for el in f.value:
                        ci = len(p.structs)
                        new_struct(el, fi)
                        visit(el, ci)

    new_struct(g.root, None)
    visit(g.root, 0)
    return p


def _plan_keep(g):
    """Rebuild the creation order from the indices remembered by read()."""
    structs, fields = {}, {}
    owner, parent_list = {}, {}

    def walk(s, plist):
        if s.index is None or s.index in structs:
            raise ValueError("order='keep' needs a tree fresh from read()")
        structs[s.index] = s
        parent_list[s.index] = plist
        for f in s.fields:
            if f.index is None or f.index in fields:
                raise ValueError("order='keep' needs a tree fresh from read()")
            fields[f.index] = f
            owner[f.index] = s.index
            if f.type == STRUCT:
                walk(f.value, None)
            elif f.type == LIST:
                for el in f.value:
                    walk(el, f.index)

    walk(g.root, None)
    s_order = sorted(structs)
    f_order = sorted(fields)
    s_pos = {old: new for new, old in enumerate(s_order)}
    f_pos = {old: new for new, old in enumerate(f_order)}
    p = Plan()
    p.structs = [structs[i] for i in s_order]
    p.fields = [fields[i] for i in f_order]
    p.owner = [s_pos[owner[i]] for i in f_order]
    p.parent_list = [None if parent_list[i] is None else f_pos[parent_list[i]] for i in s_order]
    # A struct is created before its first field, and no later than the struct created after it.
    first = {}
    for fi, si in enumerate(p.owner):
        first.setdefault(si, fi)
    times, nxt = [0.0] * len(p.structs), float('inf')
    for si in range(len(p.structs) - 1, 0, -1):
        t = min(first.get(si, nxt) - 0.5, nxt) if si in first else nxt
        times[si], nxt = t, t
    times[0] = -1.0
    ev = [(fi, 0, fi, 'F') for fi in range(len(p.fields))]
    ev += [(times[si], 1, si, 'S') for si in range(len(p.structs))]
    ev.sort()
    p.events = [(kind, i) for _t, _k, i, kind in ev]
    return p


def _encode_inline(f):
    t, v = f.type, f.value
    if t == BYTE:
        return v & 0xFF
    if t in (CHAR, SHORT, INT):
        return v & 0xFFFFFFFF          # sign-extended to 32 bits, as the engine writes them
    if t == WORD:
        return v & 0xFFFF
    if t == DWORD:
        return v & 0xFFFFFFFF
    if t == FLOAT:
        return struct.unpack('<I', struct.pack('<f', v))[0]
    raise AssertionError(t)


def _encode_complex(f):
    t, v = f.type, f.value
    if t in _FIXED:
        return struct.pack(_FIXED[t], *(v if isinstance(v, tuple) else (v,)))
    if t in (CEXOSTRING, VOID):
        return struct.pack('<I', len(v)) + v
    if t == RESREF:
        if len(v) > 16:
            raise GffError(f'ResRef {v!r} longer than 16 characters')
        return bytes([len(v)]) + v
    if t == LOCSTRING:
        body = struct.pack('<iI', v.strref, len(v.strings))
        for sid, s in v.strings:
            body += struct.pack('<iI', sid, len(s)) + s
        return struct.pack('<I', len(body)) + body
    raise AssertionError(t)


def _field_indices(plan, how):
    """Field-indices array and each multi-field struct's byte offset into it."""
    members = [[] for _ in plan.structs]
    for fi, si in enumerate(plan.owner):
        members[si].append(fi)
    if how == 'struct':
        buf, at = [], {}
        for si, m in enumerate(members):
            if len(m) > 1:
                at[si] = 4 * len(buf)
                buf.extend(m)
        return buf, at
    if how == 'second':
        multi = sorted((m[1], si) for si, m in enumerate(members) if len(m) > 1)
        buf, at = [], {}
        for _, si in multi:
            at[si] = 4 * len(buf)
            buf.extend(members[si])
        return buf, at
    if how == 'move':
        buf, blk, count = [], {}, [0] * len(plan.structs)
        first = {}
        for fi, si in enumerate(plan.owner):
            count[si] += 1
            if count[si] == 1:
                first[si] = fi
            elif count[si] == 2:
                blk[si] = (len(buf), 2)
                buf += [first[si], fi]
            else:
                start, n = blk[si]
                if start + n == len(buf):
                    buf.append(fi)
                    blk[si] = (start, n + 1)
                else:
                    old = buf[start:start + n]
                    blk[si] = (len(buf), n + 1)
                    buf += old + [fi]
        return buf, {si: 4 * start for si, (start, n) in blk.items()}
    raise ValueError(f'unknown fi layout {how!r}')


def _list_indices(plan, how, s_index):
    """List-indices array and each list field's byte offset into it."""
    elems = {fi: [s_index[id(el)] for el in f.value]
             for fi, f in enumerate(plan.fields) if f.type == LIST}
    if how == 'field':
        buf, at = [], {}
        for fi in sorted(elems):
            at[fi] = 4 * len(buf)
            buf.append(len(elems[fi]))
            buf.extend(elems[fi])
        return buf, at
    if how == 'move':
        buf, blk = [], {}
        for kind, i in plan.events:
            if kind == 'F':
                if plan.fields[i].type == LIST:
                    blk[i] = len(buf)
                    buf.append(0)
            else:
                lf = plan.parent_list[i]
                if lf is None:
                    continue
                b = blk[lf]
                n = buf[b]
                if b + 1 + n == len(buf):
                    buf.append(i)
                    buf[b] += 1
                else:
                    old = buf[b + 1:b + 1 + n]
                    blk[lf] = len(buf)
                    buf += [n + 1] + old + [i]
        return buf, {fi: 4 * b for fi, b in blk.items()}
    raise ValueError(f'unknown li layout {how!r}')


def serialize(g, plan, fi='second', li='field'):
    tag = g.tag.encode('latin-1')
    if len(tag) != 4:
        raise GffError(f'file type {g.tag!r} is not 4 characters')
    s_index = {id(s): i for i, s in enumerate(plan.structs)}
    labels, label_index = [], {}
    fdata = bytearray()
    findices, fi_at = _field_indices(plan, fi)
    lindices, li_at = _list_indices(plan, li, s_index)
    field_recs = bytearray()
    for i, f in enumerate(plan.fields):
        lab = f.label.encode('latin-1')
        if len(lab) > 16:
            raise GffError(f'label {f.label!r} longer than 16 characters')
        if lab not in label_index:
            label_index[lab] = len(labels)
            labels.append(lab)
        t = f.type
        if t <= INT or t == FLOAT:
            dd = _encode_inline(f)
        elif t == STRUCT:
            dd = s_index[id(f.value)]
        elif t == LIST:
            dd = li_at[i]
        else:
            dd = len(fdata)
            fdata += _encode_complex(f)
        field_recs += struct.pack('<3I', t, label_index[lab], dd)
    struct_recs = bytearray()
    counts = [0] * len(plan.structs)
    first = [None] * len(plan.structs)
    for i, si in enumerate(plan.owner):
        counts[si] += 1
        if first[si] is None:
            first[si] = i
    for si, s in enumerate(plan.structs):
        n = counts[si]
        dd = NO_FIELDS if n == 0 else first[si] if n == 1 else fi_at[si]
        struct_recs += struct.pack('<3I', s.id & 0xFFFFFFFF, dd, n)
    label_recs = b''.join(lab.ljust(16, b'\0') for lab in labels)
    fi_bytes = struct.pack(f'<{len(findices)}I', *findices)
    li_bytes = struct.pack(f'<{len(lindices)}I', *lindices)
    so = HEADER_SIZE
    fo = so + len(struct_recs)
    lo = fo + len(field_recs)
    do = lo + len(label_recs)
    fio = do + len(fdata)
    lio = fio + len(fi_bytes)
    head = tag + b'V3.2' + struct.pack(
        '<12I', so, len(plan.structs), fo, len(plan.fields), lo, len(labels),
        do, len(fdata), fio, len(fi_bytes), lio, len(li_bytes))
    return head + bytes(struct_recs) + bytes(field_recs) + label_recs + bytes(fdata) + fi_bytes + li_bytes


# ---------------------------------------------------------------------------------------------
# Debug output

def _fmt_value(f):
    v = f.value
    if f.type in (CEXOSTRING, RESREF):
        return repr(v.decode('cp1252', 'replace'))
    if f.type == VOID:
        return f'<{len(v)} bytes> {v[:16].hex()}{"..." if len(v) > 16 else ""}'
    if f.type == LOCSTRING:
        subs = ', '.join(f'{sid}:{s.decode("cp1252", "replace")!r}' for sid, s in v.strings)
        return f'strref={v.strref} [{subs}]'
    return repr(v)


def dump_tree(g, out=sys.stdout):
    def walk(s, depth):
        pad = '  ' * depth
        for f in s.fields:
            name = TYPE_NAMES[f.type]
            if f.type == STRUCT:
                print(f'{pad}{f.label}: Struct id={f.value.id}', file=out)
                walk(f.value, depth + 1)
            elif f.type == LIST:
                print(f'{pad}{f.label}: List[{len(f.value)}]', file=out)
                for k, el in enumerate(f.value):
                    print(f'{pad}  [{k}] id={el.id}', file=out)
                    walk(el, depth + 2)
            else:
                print(f'{pad}{f.label}: {name} = {_fmt_value(f)}', file=out)
    print(f'{g.tag!r} id={g.root.id:#x}', file=out)
    walk(g.root, 1)


def _load(arg):
    if os.path.isfile(arg):
        with open(arg, 'rb') as fh:
            return fh.read()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kres
    resref, _, ext = arg.rpartition('.')
    data = kres.Game().get(resref, ext.lower())
    if data is None:
        raise SystemExit(f'{arg}: not found')
    return data


def main(argv):
    if len(argv) < 2 or argv[0] not in ('dump', 'roundtrip'):
        print(__doc__)
        return 2
    data = _load(argv[1])
    g = read(data)
    if argv[0] == 'dump':
        dump_tree(g)
        return 0
    for order in ('dfs', 'elements', 'keep'):
        for fi in ('second', 'struct', 'move'):
            for li in ('field', 'move'):
                if write(g, order, fi, li) == data:
                    print(f'identical with order={order} fi={fi} li={li}')
                    return 0
    print('no layout reproduces the file byte for byte')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
