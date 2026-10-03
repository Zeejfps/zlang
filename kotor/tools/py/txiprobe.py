"""Collect every TXI in the install and tally its keywords.

    python kotor/tools/py/txiprobe.py          tally keywords (counts, example values, sources), check
                                               block lengths and font coordinate tables, cross-check
                                               texture references and the keywords swkotor.exe knows
    python kotor/tools/py/txiprobe.py font NAME TEXT   render TEXT with font NAME to kotor/out/txi/

TXI text comes from two places: standalone .txi resources (lightmaps*.bif, textures.bif,
templates.bif, the GUI texture pack) and the text appended after the pixel data of TPC files
(tpcprobe.parse finds it). Nothing here is used by the game.
"""

import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402
import tpcprobe  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out', 'txi'))

# Keyword strings found in swkotor.exe's data section (the TXI parser's table and the material
# keywords next to the MDL-reading code). See docs/formats/txi-render.md.
EXE_KEYWORDS = {
    # font
    'numchars', 'fontheight', 'baselineheight', 'texturewidth', 'spacingr', 'spacingb',
    'upperleftcoords', 'lowerrightcoords',
    # texture properties
    'specularbumpintensity', 'diffusebumpintensity', 'envmapalpha', 'isenvironmentmapped',
    'useglobalalpha', 'temporary', 'bumpintensity', 'cube', 'numy', 'numx', 'specularcolor',
    'bumpmapscaling', 'isspecularbumpmap', 'isdiffusebumpmap', 'alphamean', 'clamp', 'isbumpmap',
    'gamma', 'maptexelstopixels', 'filter', 'mipmap', 'downsamplemin', 'downsamplemax',
    'defaultheight', 'defaultwidth', 'filerange', 'proceduretype', 'blending',
    # procedural parameters
    'channeltranslate', 'channelscale', 'speed', 'distortionamplitude', 'distortangle', 'distort',
    'waterheight', 'waterwidth', 'anglecyclespeed', 'forcecyclespeed', 'arturoheight', 'arturowidth',
    'fps',
    # material keywords (next to the model code)
    'wateralpha', 'renderbmlmtype', 'decal', 'envmaptexture', 'bumpyshinytexture', 'bumpmaptexture',
}
EXE_PROCEDURE_TYPES = {'ringtexdistort', 'random', 'cycle', 'wave', 'arturo', 'perlin', 'life', 'water'}
EXE_BLENDING = {'punchthrough', 'additive'}

NUMBER = re.compile(r'^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$')


def parse(text):
    """List of (keyword, args, block rows). A keyword line with one integer argument that is
    followed by lines starting with a number owns those lines as its block."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = []
    i = 0
    while i < len(lines):
        p = lines[i].split()
        i += 1
        if not p:
            continue
        if NUMBER.match(p[0]):
            out.append(('<stray number line>', p, []))
            continue
        kw, args = p[0], p[1:]
        rows = []
        if len(args) == 1 and args[0].isdigit():
            while i < len(lines):
                q = lines[i].split()
                if q and NUMBER.match(q[0]):
                    rows.append(q)
                    i += 1
                elif not q and rows and int(args[0]) > len(rows):
                    i += 1  # tolerate blank lines inside a block
                else:
                    break
        out.append((kw, args, rows))
    return out


def every_txi(g):
    """(source label, resref, text) for every TXI text in the install."""
    for e in g.every_entry('txi'):
        where = os.path.basename(e.container).lower()
        if where.startswith('lightmaps'):
            where = 'lightmaps*.bif'
        yield f'standalone in {where}', e.resref, kres.read_entry(e).decode('latin-1')
    for e in g.every_entry('tpc'):
        where = os.path.basename(e.container).lower()
        try:
            t = tpcprobe.parse(kres.read_entry(e))
        except ValueError:
            continue
        if t.txi.strip():
            yield f'in TPC in {where}', e.resref, t.txi


def check_all():
    g = kres.Game()
    tpcs = {}
    for e in g.every_entry('tpc'):
        tpcs.setdefault(e.resref, e)
    kw_texts = Counter()            # keyword -> number of TXI texts using it
    kw_sources = defaultdict(Counter)
    kw_values = defaultdict(Counter)
    kw_spelling = defaultdict(Counter)
    kw_examples = {}
    dup_in_text = Counter()
    block_checks = Counter()
    problems = []
    fonts = []
    refs = defaultdict(Counter)
    n_texts = Counter()
    for src, resref, text in every_txi(g):
        n_texts[src] += 1
        entries = parse(text)
        seen = Counter()
        for kw, args, rows in entries:
            k = kw.lower()
            seen[k] += 1
            kw_spelling[k][kw] += 1
            val = ' '.join(args)
            kw_values[k][val if len(val) < 40 else val[:37] + '...'] += 1
            kw_examples.setdefault(k, f'{resref} ({src})')
            if rows:
                block_checks[f'{k}: {"rows == count" if len(rows) == int(args[0]) else "rows != count"}'] += 1
                if len(rows) != int(args[0]):
                    problems.append(f'{resref} ({src}): {kw} {args[0]} has {len(rows)} rows')
                widths = Counter(len(r) for r in rows)
                block_checks[f'{k}: values per row {sorted(widths)}'] += 1
            if k in ('envmaptexture', 'bumpyshinytexture', 'bumpmaptexture') and args:
                ref = args[0].lower()
                e = tpcs.get(ref)
                if e is None:
                    tga = [x for x in g.every_entry('tga') if x.resref == ref]
                    refs[k]['missing' if not tga else 'is a TGA'] += 1
                    if not tga:
                        problems.append(f'{resref} ({src}): {k} {args[0]} names no TPC/TGA in the install')
                else:
                    t = tpcprobe.parse(kres.read_entry(e))
                    refs[k][f'{t.kind} {t.fmt}'] += 1
        for k, v in seen.items():
            kw_texts[k] += 1
            kw_sources[k][src] += 1
            if v > 1:
                dup_in_text[k] += 1
        d = {kw.lower(): (args, rows) for kw, args, rows in entries}
        if 'numchars' in d:
            fonts.append((src, resref, d))
    print('TXI texts:')
    for s, c in sorted(n_texts.items()):
        print(f'  {c:6d}  {s}')
    print(f'  {sum(n_texts.values()):6d}  total')
    print('\nkeywords (texts using it; spellings; top values; example; sources):')
    for k, c in kw_texts.most_common():
        vals = ', '.join(f'{v!r}x{n}' for v, n in kw_values[k].most_common(8))
        more = f' (+{len(kw_values[k]) - 8} more values)' if len(kw_values[k]) > 8 else ''
        exe = '' if k in EXE_KEYWORDS else '   [NOT in swkotor.exe]'
        print(f'  {c:6d}  {k}{exe}')
        print(f'          spellings: {dict(kw_spelling[k])}')
        print(f'          values: {vals}{more}')
        print(f'          e.g. {kw_examples[k]}; sources: {dict(kw_sources[k])}')
    print('\nkeywords swkotor.exe knows that no TXI in the install uses:')
    print('  ' + ', '.join(sorted(EXE_KEYWORDS - set(kw_texts))))
    print('\nproceduretype values:', dict(kw_values['proceduretype']),
          '(exe knows: ' + ', '.join(sorted(EXE_PROCEDURE_TYPES)) + ')')
    print('blending values:', dict(kw_values['blending']), '(exe knows: ' + ', '.join(sorted(EXE_BLENDING)) + ')')
    print('\nkeywords repeated inside one text:', dict(dup_in_text))
    print('\nblock checks:')
    for k, v in sorted(block_checks.items()):
        print(f'  {v:6d}  {k}')
    print('\ntexture references (what the named texture is):')
    for k, c in refs.items():
        print(f'  {k}: {dict(c)}')
    check_fonts(g, fonts, problems)
    print(f'\nproblems ({len(problems)}):')
    for p in problems:
        print('  ' + p)
    return 0


def check_fonts(g, fonts, problems):
    print(f'\nfonts ({len(fonts)}):')
    for src, resref, d in fonts:
        n = int(d['numchars'][0][0])
        ul, lr = d.get('upperleftcoords', ([], []))[1], d.get('lowerrightcoords', ([], []))[1]
        e = tpcprobe.find_tpc(g, resref)
        t = tpcprobe.parse(kres.read_entry(e)) if e else None
        w, h = (t.width, t.height) if t else (0, 0)
        ok = len(ul) == n and len(lr) == n
        if not ok:
            problems.append(f'font {resref}: numchars {n}, {len(ul)} upper-left rows, {len(lr)} lower-right rows')
        uls = np.array([[float(x) for x in r[:2]] for r in ul]) if ul else np.zeros((0, 2))
        lrs = np.array([[float(x) for x in r[:2]] for r in lr]) if lr else np.zeros((0, 2))
        m = min(len(uls), len(lrs))
        gw = (lrs[:m, 0] - uls[:m, 0]) * w
        gh = (uls[:m, 1] - lrs[:m, 1]) * h
        thirds = Counter(r[2] if len(r) > 2 else '-' for r in ul + lr)
        other = {k: d[k][0] for k in ('fontheight', 'baselineheight', 'texturewidth', 'spacingr', 'spacingb',
                                      'caretindent') if k in d}
        print(f'  {resref} ({src}) {w}x{h} {t.fmt if t else "?"}: numchars {n}, rows {len(ul)}/{len(lr)}'
              f' {"OK" if ok else "MISMATCH"}; {other}')
        print(f'      coords x in [{min(uls[:, 0].min(), lrs[:, 0].min()):.4f}, {max(uls[:, 0].max(), lrs[:, 0].max()):.4f}]'
              f' y in [{min(uls[:, 1].min(), lrs[:, 1].min()):.4f}, {max(uls[:, 1].max(), lrs[:, 1].max()):.4f}];'
              f' upper-left y >= lower-right y for {(uls[:m, 1] >= lrs[:m, 1]).sum()}/{m};'
              f' glyph px w {gw.min():.1f}..{gw.max():.1f}, h {gh.min():.1f}..{gh.max():.1f};'
              f' third column {dict(thirds)}')


def render_text(name, text):
    """Draw `text` with a font's glyph rectangles, reading v upwards from the first stored row,
    and write a top-down PNG: if the convention is right the text reads normally."""
    from PIL import Image
    g = kres.Game()
    e = tpcprobe.find_tpc(g, name)
    t = tpcprobe.parse(kres.read_entry(e))
    d = {kw.lower(): (args, rows) for kw, args, rows in parse(t.txi)}
    ul = [[float(x) for x in r[:2]] for r in d['upperleftcoords'][1]]
    lr = [[float(x) for x in r[:2]] for r in d['lowerrightcoords'][1]]
    img = tpcprobe.decode(t).astype(np.float32)   # row 0 = first stored row
    w, h = t.width, t.height
    glyphs = []
    for ch in text:
        c = ord(ch)
        if c >= len(ul):
            continue
        x0, x1 = int(round(ul[c][0] * w)), int(round(lr[c][0] * w))
        # v = 1 is the top of the picture; rows are stored bottom-up, so v maps to row v*h.
        r_top, r_bot = int(round(ul[c][1] * h)), int(round(lr[c][1] * h))
        cell = img[min(r_bot, r_top):max(r_bot, r_top), max(0, x0):min(w, x1)]
        glyphs.append(cell[::-1])  # flip to top-down for the PNG
    hh = max(x.shape[0] for x in glyphs)
    line = np.zeros((hh, sum(x.shape[1] for x in glyphs) + 1, 4), np.float32)
    x = 0
    for gl in glyphs:
        line[:gl.shape[0], x:x + gl.shape[1]] = gl
        x += gl.shape[1]
    a = line[:, :, 3:4] / 255
    rgb = (line[:, :, :3] * a + 40 * (1 - a)).astype(np.uint8)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{name}_text.png')
    Image.fromarray(rgb).resize((rgb.shape[1] * 3, rgb.shape[0] * 3), Image.NEAREST).save(path)
    print('wrote', path)


def main(argv):
    if argv and argv[0] == 'font':
        render_text(argv[1], ' '.join(argv[2:]) or 'The quick brown fox, Taris 0123!')
        return 0
    return check_all()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
