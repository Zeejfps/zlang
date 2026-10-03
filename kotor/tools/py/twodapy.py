"""Minimal 2DA reader for probes (not used by the game).

    python kotor/tools/py/twodapy.py NAME [--rows A:B] [--cols c1,c2]   print a table from the install
    python kotor/tools/py/twodapy.py --file PATH ...                    print a table from a file

As a library:

    import twodapy
    t = twodapy.parse(data)        # bytes of a "2DA V2.b" (binary) or "2DA V2.0" (text) file
    t.columns                      # column labels, as stored (case kept)
    t.row_labels                   # one label per row (normally "0", "1", ...)
    t.rows                         # list of lists of str; "" for an empty cell or "****"
    t.get(row, 'column')           # one cell by row index and column label (case-insensitive)
    t.column('column')             # every cell of one column

Binary layout (V2.b), as KOTOR ships it:

    "2DA V2.b\\n"
    column labels, each ended by a tab, the list ended by a NUL
    u32 row count
    row labels, each ended by a tab
    u16 offset per cell, row-major (rows x columns), into the data block
    u16 size of the data block
    data block: NUL-terminated strings; equal strings share one offset

Some copies in rims/global.rim and rims/miniglobal.rim end every column and row label with a NUL
instead of a tab (so the label list ends with two NULs). The cells are the same. `parse` accepts
both and records which it saw in `t.label_sep` ('\\t' or '\\0').
"""

import struct
import sys


class TwoDAError(ValueError):
    pass


class TwoDA:
    def __init__(self, version, columns, row_labels, rows, label_sep='\t', data_size=None,
                 distinct_cells=None):
        self.version = version
        self.columns = columns
        self.row_labels = row_labels
        self.rows = rows
        self.label_sep = label_sep
        self.data_size = data_size
        self.distinct_cells = distinct_cells
        self._index = {c.lower(): i for i, c in enumerate(columns)}

    def col_index(self, name):
        return self._index[name.lower()]

    def has(self, name):
        return name.lower() in self._index

    def get(self, row, name):
        return self.rows[row][self._index[name.lower()]]

    def column(self, name):
        i = self._index[name.lower()]
        return [r[i] for r in self.rows]


def _empty(s):
    return '' if s == '****' else s


def parse(data):
    if data.startswith(b'2DA V2.b'):
        return _parse_binary(data)
    if data.startswith(b'2DA V2.0') or data.startswith(b'2DA\tV2.0'):
        return _parse_text(data)
    raise TwoDAError(f'not a 2DA: {data[:16]!r}')


def _parse_binary(d):
    pos = 8
    if d[pos:pos + 1] != b'\n':
        raise TwoDAError('no newline after "2DA V2.b"')
    pos += 1
    # Column labels. A label ends with a tab (BIF copies) or a NUL (some RIM copies); a NUL at
    # the start of a label ends the list.
    columns = []
    seps = set()
    while True:
        if pos >= len(d):
            raise TwoDAError('column labels run past the end')
        if d[pos] == 0:
            pos += 1
            break
        end = pos
        while end < len(d) and d[end] not in (9, 0):
            end += 1
        if end >= len(d):
            raise TwoDAError('unterminated column label')
        columns.append(d[pos:end].decode('latin-1'))
        seps.add(d[end])
        pos = end + 1
    if len(seps) > 1:
        raise TwoDAError('column labels mix tab and NUL terminators')
    if not columns:
        raise TwoDAError('no columns')
    label_sep = '\0' if seps == {0} else '\t'
    if pos + 4 > len(d):
        raise TwoDAError('truncated row count')
    (nrows,) = struct.unpack_from('<I', d, pos)
    pos += 4
    row_labels = []
    for _ in range(nrows):
        end = pos
        while end < len(d) and d[end] not in (9, 0):
            end += 1
        if end >= len(d):
            raise TwoDAError('unterminated row label')
        if (d[end] == 0) != (label_sep == '\0'):
            raise TwoDAError('row label terminator differs from column label terminator')
        row_labels.append(d[pos:end].decode('latin-1'))
        pos = end + 1
    ncells = nrows * len(columns)
    if pos + 2 * ncells + 2 > len(d):
        raise TwoDAError('truncated cell offsets')
    offsets = struct.unpack_from(f'<{ncells}H', d, pos)
    pos += 2 * ncells
    (data_size,) = struct.unpack_from('<H', d, pos)
    pos += 2
    block = d[pos:]
    if len(block) != data_size:
        raise TwoDAError(f'data block is {len(block)} bytes, header says {data_size}')
    cache = {}
    rows = []
    for r in range(nrows):
        row = []
        for c in range(len(columns)):
            off = offsets[r * len(columns) + c]
            s = cache.get(off)
            if s is None:
                if off >= len(block):
                    raise TwoDAError(f'cell ({r},{c}) offset {off} past data block ({len(block)})')
                end = block.find(b'\0', off)
                if end < 0:
                    raise TwoDAError(f'cell ({r},{c}) string not NUL-terminated')
                s = _empty(block[off:end].decode('latin-1'))
                cache[off] = s
            row.append(s)
        rows.append(row)
    return TwoDA('V2.b', columns, row_labels, rows, label_sep, data_size, len(cache))


def _split_text_line(line):
    out = []
    i = 0
    n = len(line)
    while i < n:
        while i < n and line[i] in ' \t':
            i += 1
        if i >= n:
            break
        if line[i] == '"':
            j = line.find('"', i + 1)
            if j < 0:
                j = n
            out.append(line[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and line[j] not in ' \t':
                j += 1
            out.append(line[i:j])
            i = j
    return out


def _parse_text(d):
    lines = d.decode('latin-1').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 1
    default = None
    # Line 2 is blank or "DEFAULT: value"; the column line is the first non-blank line after it.
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip().upper().startswith('DEFAULT:'):
        default = lines[i].split(':', 1)[1].strip()
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    if i >= len(lines):
        raise TwoDAError('no column line')
    columns = _split_text_line(lines[i])
    i += 1
    row_labels = []
    rows = []
    for line in lines[i:]:
        if not line.strip():
            continue
        f = _split_text_line(line)
        row_labels.append(f[0])
        cells = [_empty(x) for x in f[1:1 + len(columns)]]
        cells += [_empty(default or '')] * (len(columns) - len(cells))
        rows.append(cells)
    t = TwoDA('V2.0', columns, row_labels, rows)
    t.default = default
    return t


def _main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if argv[0] == '--file':
        with open(argv[1], 'rb') as f:
            data = f.read()
        rest = argv[2:]
    else:
        import kres
        data = kres.Game().get(argv[0], '2da')
        if data is None:
            print(f'{argv[0]}.2da: not found', file=sys.stderr)
            return 1
        rest = argv[1:]
    t = parse(data)
    lo, hi = 0, len(t.rows)
    if '--rows' in rest:
        a, _, b = rest[rest.index('--rows') + 1].partition(':')
        lo, hi = int(a or 0), int(b or len(t.rows))
    cols = list(range(len(t.columns)))
    if '--cols' in rest:
        cols = [t.col_index(c) for c in rest[rest.index('--cols') + 1].split(',')]
    print('\t'.join(['#'] + [t.columns[c] for c in cols]))
    for r in range(lo, min(hi, len(t.rows))):
        print('\t'.join([t.row_labels[r]] + [t.rows[r][c] or '****' for c in cols]))
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
