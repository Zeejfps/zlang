"""Census of TXI texture-info text in the install, for docs/formats/txi.md.

    python kotor/tools/py/txi_probe.py [--dump DIR] [--verbose]
    python kotor/tools/py/txi_probe.py --fonts     print glyphs cut out by font coordinates (needs tpcprobe)

TXI lives in two places: standalone .txi resources (Game.every_entry('txi')) and as text
appended after the pixel data of .tpc textures. For every TPC this finds where the pixel data
ends (see tpc_pixel_bytes and txi.md, "TXI inside TPC"), treats the rest as TXI and checks that
it is text. Then it parses every TXI with the grammar in the doc and counts keywords, case,
line endings, numbers and blocks; compares standalone and embedded TXI for the same resref.
--dump writes each distinct TXI text under DIR (e.g. kotor/extract/text/txi).
Exit status 1 if a TPC's trailing bytes are not text or a TXI line does not parse.
"""

import os
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

# Keywords whose argument is a count N, followed by N lines of data (font coordinates: 3 numbers
# per line; channel lists: 1 number per line).
BLOCKS = {'upperleftcoords': 3, 'lowerrightcoords': 3, 'channelscale': 1, 'channeltranslate': 1}

# Every TXI keyword string in swkotor.exe's keyword tables (see txi.md, "Which keywords the
# engine reads"). Used to flag keywords in the data that the engine never looks at.
ENGINE = set('''
lowerrightcoords upperleftcoords spacingb spacingr texturewidth baselineheight fontheight numchars
specularbumpintensity diffusebumpintensity envmapalpha isenvironmentmapped useglobalalpha
temporary bumpintensity cube numy numx specularcolor bumpmapscaling isspecularbumpmap
isdiffusebumpmap alphamean clamp isbumpmap gamma maptexelstopixels filter mipmap downsamplemin
downsamplemax defaultheight defaultwidth filerange proceduretype
channeltranslate0 channeltranslate1 channeltranslate2 channeltranslate3 channelscale0
channelscale1 channelscale2 channelscale3 speed distortionamplitude distortangle distort
channeltranslate channelscale waterheight waterwidth anglecyclespeed forcecyclespeed arturoheight
arturowidth fps blending decal envmaptexture bumpyshinytexture bumpmaptexture wateralpha
renderbmlmtype
'''.split())

NUMBER = re.compile(r'^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$')


def mip_bytes(w, h, enc, compressed):
    if compressed:
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if enc == 2 else 16)
    return w * h * {1: 1, 2: 3, 4: 4}[enc]


def chain_bytes(w, h, enc, compressed, mips):
    total = 0
    for _ in range(mips):
        total += mip_bytes(w, h, enc, compressed)
        w, h = max(1, w // 2), max(1, h // 2)
    return total


def tpc_pixel_bytes(d):
    """(bytes of pixel data after the 128-byte header, kind) for a TPC, as txi.md describes."""
    size, _f, w, h, enc, mips = struct.unpack_from('<IfHHBB', d, 0)
    compressed = size != 0
    if enc not in (1, 2, 4) or (compressed and enc == 1):
        raise ValueError(f'unknown encoding {enc} (data size {size})')
    faces = 6 if h == 6 * w else 1
    std = faces * chain_bytes(w, h // faces, enc, compressed, mips)
    if compressed and size > std:
        # Flipbook: the data size field covers every frame and every frame's mip chain.
        return size, 'flipbook'
    return std, 'cube' if faces == 6 else 'plain'


def parse_txi(text):
    """[(keyword lower-cased, [args], [block lines])], plus notes on what was unusual.
    Raises ValueError on a line it cannot place."""
    out = []
    notes = []
    want = 0            # block lines still expected
    width = 0
    for n, raw in enumerate(re.split(r'\r\n|\n|\r', text), 1):
        words = raw.split()
        if not words:
            continue
        if want:
            if len(words) == width and all(NUMBER.match(w) for w in words):
                out[-1][2].append([float(w) for w in words])
                want -= 1
                continue
            notes.append(f'block {out[-1][0]} ends {want} lines early at line {n}')
            want = 0
        if NUMBER.match(words[0]):
            # A number where a keyword should be: only grassinfo does this.
            notes.append(f'line {n} starts with a number: {raw.strip()!r}')
            out.append(('<numbers>', words, []))
            continue
        key = words[0].lower()
        if words[0] != key:
            notes.append(f'keyword case {words[0]!r}')
        out.append((key, words[1:], []))
        if key in BLOCKS and len(words) == 2 and words[1].isdigit():
            want = int(words[1])
            width = BLOCKS[key]
    if want:
        notes.append(f'file ends {want} lines into block {out[-1][0]}')
    return out, notes


def check_fonts(g, fonts=('dialogfont16x16b', 'fnt_galahad14'), chars='Ag'):
    """Print glyph cells of font TPCs as text, cut out with v read as row / height counted from
    the first stored pixel row (txi.md, "Font keywords"). Rows print top line first in storage
    order, so a correct cut shows the glyph upside down. Uses the texture agent's tpcprobe."""
    try:
        import tpcprobe
    except ImportError as ex:
        print(f'font check skipped: {ex}')
        return
    for font in fonts:
        d = g.get(font, 'tpc')
        n, _kind = tpc_pixel_bytes(d)
        body, _ = parse_txi(d[128 + n:].decode('ascii'))
        blocks = {k: blk for k, _a, blk in body}
        img = tpcprobe.decode(tpcprobe.parse(d), 0, 0).astype(int)
        h, w = img.shape[:2]
        # Glyph sheets are white on transparent, or white on black (then alpha is constant).
        ink = img[..., 3] if img[..., 3].max() != img[..., 3].min() else img[..., 0]
        for ch in chars:
            (u0, v0, _), (u1, v1, _) = (blocks['upperleftcoords'][ord(ch)],
                                        blocks['lowerrightcoords'][ord(ch)])
            print(f'{font} {ch!r}: upper-left ({u0}, {v0}), lower-right ({u1}, {v1}), '
                  f'rows {int(v1 * h)}..{int(v0 * h)} in storage order:')
            for r in range(int(v1 * h), int(v0 * h)):
                print('   |' + ''.join(' .:-=+*#%@'[min(9, int(ink[r, c]) * 10 // 256)]
                                       for c in range(int(u0 * w), int(u1 * w))) + '|')


def main(argv):
    verbose = '--verbose' in argv
    dump = argv[argv.index('--dump') + 1] if '--dump' in argv else None
    g = kres.Game()
    if '--fonts' in argv:
        check_fonts(g)
        return 0
    fails = []
    texts = []                      # (source, resref, text)
    # Standalone .txi resources.
    standalone = g.every_entry('txi')
    for e in standalone:
        d = kres.read_entry(e)
        texts.append(('txi', e.resref, d, os.path.relpath(e.container, g.dir)))
    # TXI appended to TPC.
    tpcs = g.every_entry('tpc')
    kinds = Counter()
    with_txi = Counter()
    flipbook_checks = Counter()
    nul_tail = 0
    for e in tpcs:
        d = kres.read_entry(e)
        where = f'{e.resref}.tpc in {os.path.relpath(e.container, g.dir)}'
        try:
            n, kind = tpc_pixel_bytes(d)
        except ValueError as ex:
            fails.append(f'{where}: {ex}')
            continue
        kinds[kind] += 1
        tail = d[128 + n:]
        if len(d) < 128 + n:
            fails.append(f'{where}: file is {128 + n - len(d)} bytes shorter than its pixel data')
            continue
        if not tail:
            continue
        if tail.rstrip(b'\0') != tail:
            nul_tail += 1
            tail = tail.rstrip(b'\0')
        if not all(b in (9, 10, 13) or 32 <= b < 127 for b in tail):
            fails.append(f'{where}: {len(tail)} trailing bytes are not ASCII text: {tail[:24]!r}')
            continue
        with_txi[kind] += 1
        texts.append(('tpc', e.resref, tail, os.path.relpath(e.container, g.dir)))
        if kind == 'flipbook':
            size, _f, w, h, enc, mips = struct.unpack_from('<IfHHBB', d, 0)
            body, _ = parse_txi(tail.decode('ascii'))
            kv = {k: a for k, a, _ in body}
            try:
                nx, ny = int(kv['numx'][0]), int(kv['numy'][0])
            except (KeyError, IndexError, ValueError):
                flipbook_checks['no numx/numy'] += 1
                continue
            fw, fh = w // nx, h // ny
            full = max(fw, fh).bit_length()
            if size == nx * ny * chain_bytes(fw, fh, enc, True, full):
                flipbook_checks['size == numx*numy frames, each a full mip chain'] += 1
            else:
                flipbook_checks['size does not match frames'] += 1
                if verbose:
                    print('  flipbook mismatch', where, size, w, h, nx, ny)
            if mips != 1:
                flipbook_checks[f'header mip count {mips}'] += 1
    total_tpc_txi = sum(with_txi.values())
    print(f'TPC copies: {len(tpcs)}; layouts: {dict(kinds)}; with trailing TXI: {total_tpc_txi} '
          f'{dict(with_txi)}; trailing NULs stripped in {nul_tail}')
    print('flipbook checks:', dict(flipbook_checks))
    print(f'standalone TXI copies: {len(standalone)}')

    # Parse and count.
    keys = defaultdict(Counter)     # source -> keyword -> count
    files_with = defaultdict(Counter)
    names_with = defaultdict(lambda: defaultdict(set))   # source -> keyword -> resrefs
    values = defaultdict(Counter)   # keyword -> argument string -> count
    endings = defaultdict(Counter)
    notes_all = Counter()
    note_examples = {}
    numbers = Counter()
    distinct = {}
    by_resref = defaultdict(lambda: defaultdict(set))
    for src, resref, raw, cont in texts:
        try:
            text = raw.decode('ascii')
        except UnicodeDecodeError:
            fails.append(f'{resref}.{src}: not ASCII')
            continue
        crlf = text.count('\r\n')
        lf = text.count('\n') - crlf
        cr = text.count('\r') - crlf
        endings[src]['CRLF' if crlf and not lf and not cr else 'LF' if lf and not crlf
                     else 'none (one line)' if not (crlf or lf or cr) else 'mixed'] += 1
        endings[src]['final newline' if text.endswith('\n') else 'no final newline'] += 1
        if text != text.lstrip():
            endings[src]['leading blank/space'] += 1
        if re.search(r'[ \t]+(\r?\n|$)', text):
            endings[src]['trailing spaces on a line'] += 1
        if re.search(r'(\r?\n){2,}', text):
            endings[src]['blank lines'] += 1
        for m in re.finditer(r'#|//|;', text):
            endings[src]['comment-like character'] += 1
            break
        try:
            body, notes = parse_txi(text)
        except ValueError as ex:
            fails.append(f'{resref}.{src}: {ex}')
            continue
        for nt in notes:
            k = re.sub(r'\d+', 'N', nt)
            notes_all[k] += 1
            note_examples.setdefault(k, f'{resref}.{src}: {nt}')
        seen = set()
        for k, args, block in body:
            keys[src][k] += 1
            seen.add(k)
            values[k][' '.join(args)] += 1
            for a in args:
                if NUMBER.match(a):
                    numbers['leading dot' if a.startswith('.') or a.startswith('-.')
                            else 'trailing dot' if a.endswith('.')
                            else 'exponent' if 'e' in a.lower()
                            else 'decimal' if '.' in a else 'integer'] += 1
        for k in seen:
            files_with[src][k] += 1
            names_with[src][k].add(resref)
        norm = '\n'.join(' '.join(ln.split()).lower()
                         for ln in re.split(r'\r\n|\n|\r', text) if ln.strip())
        by_resref[resref][src].add(norm)
        distinct.setdefault((src, norm), (resref, text))
    print(f'distinct TXI texts (normalised): standalone {sum(1 for s, _ in distinct if s == "txi")}, '
          f'in TPC {sum(1 for s, _ in distinct if s == "tpc")}')
    print('line endings / layout:', {s: dict(c) for s, c in endings.items()})
    print('number formats:', dict(numbers))
    print('parse notes:')
    for k, n in notes_all.most_common():
        print(f'  {n:6}  {note_examples[k]}')
    allkeys = sorted(set(keys['txi']) | set(keys['tpc']),
                     key=lambda k: -(files_with['txi'][k] + files_with['tpc'][k]))
    print('keyword: copies with it (standalone .txi / TPC), distinct resrefs (txi / tpc), '
          'in the exe, top values')
    for k in allkeys:
        top = ', '.join(f'{v!r}x{c}' for v, c in values[k].most_common(6))
        print(f'  {k:22} {files_with["txi"][k]:5} /{files_with["tpc"][k]:5}   '
              f'{len(names_with["txi"][k]):5} /{len(names_with["tpc"][k]):5}   '
              f'{"yes" if k in ENGINE else "NO ":4} {top}')
    print(f'distinct resrefs with TXI: standalone {len({r for _s, r, *_ in texts if _s == "txi"})}, '
          f'in TPC {len({r for _s, r, *_ in texts if _s == "tpc"})}')
    # Standalone and embedded for the same resref.
    both = [r for r, v in by_resref.items() if 'txi' in v and 'tpc' in v]
    differ = [r for r in both if by_resref[r]['txi'] != by_resref[r]['tpc']]
    multi_tpc = [r for r, v in by_resref.items() if len(v.get('tpc', ())) > 1]
    print(f'resrefs with both a standalone TXI and a TPC-embedded TXI: {len(both)}; '
          f'differing: {len(differ)}')
    for r in differ[:10]:
        print(f'   {r}: txi {sorted(by_resref[r]["txi"])!r} / tpc {sorted(by_resref[r]["tpc"])!r}')
    print(f'resrefs whose TPC copies (texture packs) carry different TXI: {len(multi_tpc)}')
    for r in multi_tpc[:10]:
        print(f'   {r}: {sorted(by_resref[r]["tpc"])!r}')
    tgas = {e.resref for e in g.every_entry('tga')}
    tpcset = {e.resref for e in tpcs}
    alone = Counter('tga' if r in tgas else 'tpc' if r in tpcset else 'none'
                    for r, v in by_resref.items() if 'txi' in v)
    print(f'standalone TXI resrefs paired with a texture of the same name: {dict(alone)}')
    if dump:
        os.makedirs(dump, exist_ok=True)
        names = Counter()
        for (src, _norm), (resref, text) in distinct.items():
            names[resref] += 1
            suffix = '' if names[resref] == 1 else f'.{names[resref]}'
            with open(os.path.join(dump, f'{resref}{suffix}.{src}.txi'), 'w', newline='') as f:
                f.write(text)
    print(f'failures: {len(fails)}')
    for f in fails[:40]:
        print('  FAIL', f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
