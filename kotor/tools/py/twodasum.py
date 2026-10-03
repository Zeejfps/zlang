"""The 2DA content sum fmtcheck prints ("content sum"), computed independently with twodapy.py:
the sum over every 2DA copy in the install of the CRC-32 of its columns, row labels and cells
(each followed by a NUL, in order), as a hex number mod 2**64.

    python kotor/tools/py/twodasum.py
"""

import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402
import twodapy  # noqa: E402


def main():
    total = 0
    n = 0
    for e in kres.Game().every_entry('2da'):
        t = twodapy.parse(kres.read_entry(e))
        crc = 0
        for c in t.columns:
            crc = zlib.crc32(c.encode('latin-1') + b'\0', crc)
        for r in t.row_labels:
            crc = zlib.crc32(r.encode('latin-1') + b'\0', crc)
        for row in t.rows:
            for cell in row:
                crc = zlib.crc32(cell.encode('latin-1') + b'\0', crc)
        total = (total + crc) % (1 << 64)
        n += 1
    print(f'{n} copies, content sum {total:x}')


if __name__ == '__main__':
    main()
