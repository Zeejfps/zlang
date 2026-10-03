"""Minimal TLK V3.0 reader for probes (resolving strrefs; not used by the game).

    python kotor/tools/py/tlkpy.py STRREF...        print strings from the install's dialog.tlk

As a library:

    import tlkpy
    t = tlkpy.load()               # the install's dialog.tlk (KOTOR_DIR or the default install)
    t.text(42)                     # str, '' when the entry has no text, None when out of range
    t.sound(42)                    # sound resref or ''
    len(t)

Layout: "TLK V3.0", u32 language, u32 string count, u32 offset of the string data; then 40 bytes
per string: u32 flags, 16-byte sound resref, u32 volume variance, u32 pitch variance, u32 offset
(relative to the string data), u32 length, f32 sound length.
"""

import os
import struct
import sys


class TLK:
    def __init__(self, data):
        if data[:8] != b'TLK V3.0':
            raise ValueError(f'not a TLK V3.0: {data[:8]!r}')
        self.data = data
        self.language, self.count, self.strings_at = struct.unpack_from('<3I', data, 8)

    def __len__(self):
        return self.count

    def _entry(self, i):
        return struct.unpack_from('<I16sIIIIf', self.data, 20 + 40 * i)

    def text(self, i):
        if i < 0 or i >= self.count:
            return None
        flags, _snd, _vv, _pv, off, size, _len = self._entry(i)
        if not flags & 1:
            return ''
        a = self.strings_at + off
        return self.data[a:a + size].decode('cp1252', 'replace')

    def sound(self, i):
        if i < 0 or i >= self.count:
            return None
        flags, snd, *_ = self._entry(i)
        return snd.split(b'\0', 1)[0].decode('latin-1') if flags & 2 else ''


def load(game_dir=None):
    d = game_dir or os.environ.get('KOTOR_DIR', r'F:\Steam\steamapps\common\swkotor')
    with open(os.path.join(d, 'dialog.tlk'), 'rb') as f:
        return TLK(f.read())


if __name__ == '__main__':
    t = load()
    for a in sys.argv[1:]:
        print(f'{a}\t{t.text(int(a))!r}')
