"""Decode every TPC texture in the install and check each against its header.

    python kotor/tools/py/tpcprobe.py               check every TPC (all levels, faces, frames), print tallies
    python kotor/tools/py/tpcprobe.py --top         decode only the top level of each image (faster)
    python kotor/tools/py/tpcprobe.py png NAME...   write NAME's images (first copy found in tpa, gui, patch)
                                                    to kotor/out/tpc/ as upright PNGs (rows flipped: the
                                                    file stores the bottom row first)
    python kotor/tools/py/tpcprobe.py samples       write the sample PNGs and the contact sheet the docs cite
    python kotor/tools/py/tpcprobe.py cubeseams     score cube map face orientations by seam continuity
    python kotor/tools/py/tpcprobe.py pano [--t=KKKKKK] NAME...
                                                    equirectangular view of a cube map, Z up; by default
                                                    with the documented -Z face fix (--t=000006);
                                                    --t=000000 shows the faces as stored

As a library (txiprobe uses it):

    t = tpcprobe.parse(data)       # Tpc: header fields, format, images[i] = list of Level, txi text, problems
    a = tpcprobe.decode(t, i, m)   # RGBA uint8 array (height, width, 4) of image i (face/frame), mip m,
                                   # in file order: a[0] is the first stored row = BOTTOM of the picture

The layout rules here are the ones docs/formats/tpc.md describes. Nothing here is used by the game.
"""

import os
import struct
import sys
from collections import Counter, defaultdict, namedtuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

HEADER_SIZE = 128
OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out', 'tpc'))

Level = namedtuple('Level', 'width height offset size')


class Tpc:
    pass


def level_size(fmt, w, h):
    if fmt == 'dxt1':
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if fmt == 'dxt5':
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    return w * h * {'grey': 1, 'rgb': 3, 'rgba': 4}[fmt]


def full_mip_count(w, h):
    n = 1
    while w > 1 or h > 1:
        w, h = max(1, w // 2), max(1, h // 2)
        n += 1
    return n


def chain(fmt, w, h, count, offset):
    """Levels of one mip chain starting at `offset`."""
    out = []
    for _ in range(count):
        s = level_size(fmt, w, h)
        out.append(Level(w, h, offset, s))
        offset += s
        w, h = max(1, w // 2), max(1, h // 2)
    return out


def parse_txi_simple(text):
    """First value line of each keyword (lower-cased). Enough to find numx/numy/cube."""
    kw = {}
    for line in text.splitlines():
        p = line.split()
        if p and p[0].lower() not in kw:
            kw[p[0].lower()] = p[1:]
    return kw


def parse(d):
    t = Tpc()
    t.problems = []
    if len(d) < HEADER_SIZE:
        raise ValueError(f'short header ({len(d)} bytes)')
    t.data_size, t.alpha_mean, t.width, t.height, t.encoding, t.mips = struct.unpack_from('<IfHHBB', d, 0)
    t.padding_zero = not any(d[14:HEADER_SIZE])
    t.compressed = t.data_size != 0
    if t.encoding not in (1, 2, 4):
        raise ValueError(f'unknown encoding {t.encoding}')
    if t.compressed:
        if t.encoding == 1:
            raise ValueError('compressed grey')
        t.fmt = 'dxt1' if t.encoding == 2 else 'dxt5'
    else:
        t.fmt = {1: 'grey', 2: 'rgb', 4: 'rgba'}[t.encoding]
    if t.width == 0 or t.height == 0 or t.mips == 0:
        raise ValueError(f'empty image {t.width}x{t.height}, {t.mips} mips')
    w, h = t.width, t.height
    t.kind = 'plain'
    if h == 6 * w:
        # A cube map: six square faces, each with its own full chain, one after another.
        t.kind = 'cube'
        t.images = []
        off = HEADER_SIZE
        for _ in range(6):
            c = chain(t.fmt, w, w, t.mips, off)
            t.images.append(c)
            off = c[-1].offset + c[-1].size
        pixel_end = off
    elif t.compressed and t.mips == 1 and t.data_size > level_size(t.fmt, w, h):
        # A flipbook: the data size counts every frame's chain; the TXI after it says the grid.
        t.kind = 'cycle'
        pixel_end = HEADER_SIZE + t.data_size
        kw = parse_txi_simple(d[pixel_end:].decode('latin-1'))
        try:
            nx, ny = int(kw['numx'][0]), int(kw['numy'][0])
        except (KeyError, IndexError, ValueError):
            raise ValueError('data size exceeds one level but the TXI has no numx/numy')
        if nx <= 0 or ny <= 0 or w % nx or h % ny:
            raise ValueError(f'{w}x{h} does not split into {nx}x{ny} frames')
        fw, fh = w // nx, h // ny
        n = full_mip_count(fw, fh)
        t.images = []
        off = HEADER_SIZE
        for _ in range(nx * ny):
            c = chain(t.fmt, fw, fh, n, off)
            t.images.append(c)
            off = c[-1].offset + c[-1].size
        t.numx, t.numy = nx, ny
        if off != pixel_end:
            t.problems.append(f'flipbook frames end at {off}, data size says {pixel_end}')
    else:
        t.images = [chain(t.fmt, w, h, t.mips, HEADER_SIZE)]
        pixel_end = t.images[0][-1].offset + t.images[0][-1].size
        top = level_size(t.fmt, w, h)
        if t.compressed and t.data_size != top:
            t.problems.append(f'data size {t.data_size} != top level {top}')
    t.pixel_end = pixel_end
    if len(d) < pixel_end:
        raise ValueError(f'file is {len(d)} bytes, pixel data ends at {pixel_end}')
    t.txi_raw = d[pixel_end:]
    t.txi = t.txi_raw.decode('latin-1')
    t.data = d
    return t


# ---- decoding ---------------------------------------------------------------------------------

def _rgb565(c):
    r = (c >> 11) & 31
    g = (c >> 5) & 63
    b = c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1).astype(np.int32)


def _colour_block(b8, force_four):
    """Palette indices -> RGBA for 8-byte colour blocks b8 (n, 8). Returns (n, 16, 4)."""
    c0 = b8[:, 0].astype(np.int32) | (b8[:, 1].astype(np.int32) << 8)
    c1 = b8[:, 2].astype(np.int32) | (b8[:, 3].astype(np.int32) << 8)
    idx = (b8[:, 4].astype(np.uint32) | (b8[:, 5].astype(np.uint32) << 8)
           | (b8[:, 6].astype(np.uint32) << 16) | (b8[:, 7].astype(np.uint32) << 24))
    p0, p1 = _rgb565(c0), _rgb565(c1)
    four = np.ones(len(c0), bool) if force_four else (c0 > c1)
    pal = np.empty((len(c0), 4, 4), np.int32)
    pal[:, 0, :3], pal[:, 1, :3] = p0, p1
    f = four[:, None]
    pal[:, 2, :3] = np.where(f, (2 * p0 + p1 + 1) // 3, (p0 + p1) // 2)
    pal[:, 3, :3] = np.where(f, (p0 + 2 * p1 + 1) // 3, 0)
    pal[:, :, 3] = 255
    pal[:, 3, 3] = np.where(four, 255, 0)
    sel = ((idx[:, None] >> (2 * np.arange(16, dtype=np.uint32))) & 3).astype(np.intp)
    px = np.take_along_axis(pal, sel[:, :, None].repeat(4, axis=2), axis=1)
    return px, four, sel


def _blocks_to_image(px, w, h):
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    img = px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return img[:h, :w].astype(np.uint8)


def decode_dxt1(buf, w, h, stats=None):
    n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4)
    b = np.frombuffer(buf, np.uint8, n * 8).reshape(n, 8)
    px, four, sel = _colour_block(b, False)
    if stats is not None:
        three = ~four
        stats['dxt1_blocks'] += n
        stats['dxt1_three_colour_blocks'] += int(three.sum())
        stats['dxt1_transparent_px'] += int(((sel == 3) & three[:, None]).sum())
    return _blocks_to_image(px, w, h)


def decode_dxt5(buf, w, h, stats=None):
    n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4)
    b = np.frombuffer(buf, np.uint8, n * 16).reshape(n, 16)
    a0 = b[:, 0].astype(np.int32)
    a1 = b[:, 1].astype(np.int32)
    bits = np.zeros(n, np.uint64)
    for k in range(6):
        bits |= b[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
    eight = a0 > a1
    ap = np.empty((n, 8), np.int32)
    ap[:, 0], ap[:, 1] = a0, a1
    for i in range(1, 7):
        ap[:, 1 + i] = np.where(eight, ((7 - i) * a0 + i * a1 + 3) // 7, 0)
    for i in range(1, 5):
        ap[:, 1 + i] = np.where(eight, ap[:, 1 + i], ((5 - i) * a0 + i * a1 + 2) // 5)
    ap[:, 6] = np.where(eight, ap[:, 6], 0)
    ap[:, 7] = np.where(eight, ap[:, 7], 255)
    asel = ((bits[:, None] >> (np.uint64(3) * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.intp)
    alpha = np.take_along_axis(ap, asel, axis=1)
    # DXT5 colour blocks are always four-colour, whatever the endpoint order (S3TC spec).
    px, _four, _sel = _colour_block(b[:, 8:16], True)
    px[:, :, 3] = alpha
    if stats is not None:
        c0 = b[:, 8].astype(np.int32) | (b[:, 9].astype(np.int32) << 8)
        c1 = b[:, 10].astype(np.int32) | (b[:, 11].astype(np.int32) << 8)
        stats['dxt5_blocks'] += n
        stats['dxt5_c0_le_c1_blocks'] += int((c0 <= c1).sum())
    return _blocks_to_image(px, w, h)


def decode_level(fmt, buf, w, h, stats=None):
    if fmt == 'dxt1':
        return decode_dxt1(buf, w, h, stats)
    if fmt == 'dxt5':
        return decode_dxt5(buf, w, h, stats)
    a = np.frombuffer(buf, np.uint8, level_size(fmt, w, h))
    if fmt == 'grey':
        g = a.reshape(h, w)
        return np.dstack([g, g, g, np.full_like(g, 255)])
    if fmt == 'rgb':  # stored R, G, B (checked visually: portraits, GUI art)
        return np.dstack([a.reshape(h, w, 3), np.full((h, w), 255, np.uint8)])
    return a.reshape(h, w, 4).copy()  # stored R, G, B, A


def decode(t, image=0, mip=0, stats=None):
    lv = t.images[image][mip]
    return decode_level(t.fmt, t.data[lv.offset:lv.offset + lv.size], lv.width, lv.height, stats)


# ---- corpus check -----------------------------------------------------------------------------

def every_tpc(g):
    """(label, entry) for every TPC in the install: the four TexturePacks ERFs, patch.erf, BIFs,
    modules, Override and saves (Game.every_entry)."""
    for e in g.every_entry('tpc'):
        yield os.path.basename(e.container).lower(), e


def check_all(top_only=False):
    g = kres.Game()
    stats = Counter()
    tallies = defaultdict(Counter)
    failures = []
    notes = []
    by_pack = defaultdict(dict)
    n = 0
    for label, e in every_tpc(g):
        n += 1
        d = kres.read_entry(e)
        name = f'{e.resref}.tpc in {label}'
        try:
            t = parse(d)
        except ValueError as ex:
            failures.append(f'{name}: {ex}')
            continue
        by_pack[label][e.resref] = (t.width, t.height, t.mips, t.fmt, t.kind, t.data_size)
        tallies['container'][label] += 1
        tallies['format'][t.fmt] += 1
        tallies['kind'][t.kind] += 1
        tallies['format x kind'][f'{t.fmt} {t.kind}'] += 1
        tallies['size'][f'{t.width}x{t.height}'] += 1
        pow2 = (t.width & (t.width - 1)) == 0 and (t.height & (t.height - 1)) == 0
        tallies['power of two'][pow2] += 1
        if t.kind == 'cycle':
            tallies['mips field'][f'{t.kind}: {t.mips}'] += 1
            tallies['flipbook grid'][f'{t.numx}x{t.numy} of {t.width // t.numx}x{t.height // t.numy} {t.fmt}'] += 1
        else:
            side = t.width if t.kind == 'cube' else None
            full = full_mip_count(t.width, side or t.height)
            tallies['mips field'][f'{t.kind}: ' + ('1' if t.mips == 1 else 'full chain' if t.mips == full else
                                                   f'partial {t.mips}/{full}')] += 1
        tallies['mean alpha field'][round(t.alpha_mean, 4)] += 1
        tallies['header padding all zero'][t.padding_zero] += 1
        has_txi = bool(t.txi_raw.strip())
        tallies['TXI text after pixels'][has_txi] += 1
        if t.txi_raw and any(not (32 <= b < 127 or b in (9, 10, 13)) for b in t.txi_raw):
            failures.append(f'{name}: {len(t.txi_raw)} bytes after the pixel data are not plain text')
        if t.txi_raw:
            tallies['TXI ends with'][repr(t.txi_raw[-2:])] += 1
        kw = parse_txi_simple(t.txi)
        if t.kind == 'cube' and kw.get('cube', ['0'])[0] != '1':
            failures.append(f'{name}: height is 6 x width but the TXI has no "cube 1"')
        if t.kind != 'cube' and kw.get('cube', ['0'])[0] == '1':
            failures.append(f'{name}: TXI says cube but height != 6 x width')
        is_cycle = kw.get('proceduretype', [''])[:1] == ['cycle']
        if is_cycle != (t.kind == 'cycle'):
            failures.append(f'{name}: TXI proceduretype cycle={is_cycle} but layout kind is {t.kind}')
        for p in t.problems:
            notes.append(f'{name}: {p}')
        if t.fmt == 'rgba':
            a = np.frombuffer(d, np.uint8, t.width * t.height * 4, HEADER_SIZE)[3::4]
            tallies['raw rgba alpha'][('all 255' if a.min() == 255 else 'all 0' if a.max() == 0 else 'varies')] += 1
        try:
            local = Counter()
            for i, levels in enumerate(t.images):
                for m in range(1 if top_only else len(levels)):
                    img = decode(t, i, m, local)
                    if img.shape != (levels[m].height, levels[m].width, 4):
                        failures.append(f'{name}: image {i} mip {m} decoded to {img.shape}')
            stats.update(local)
            stats['images decoded'] += sum(1 if top_only else len(lv) for lv in t.images)
            if local['dxt1_transparent_px']:
                tallies['DXT1 with 3-colour transparent texels'][
                    'blending ' + ' '.join(kw.get('blending', ['-']))] += 1
        except Exception as ex:  # a decode crash is a failure of this file, keep going
            failures.append(f'{name}: decode failed: {ex!r}')
    # The lower-quality packs against tpa.
    for q in ('swpc_tex_tpb.erf', 'swpc_tex_tpc.erf'):
        a, b = by_pack.get('swpc_tex_tpa.erf', {}), by_pack.get(q, {})
        tallies[f'{q} vs tpa: same names'][set(a) == set(b)] += 1
        for k in a:
            if k not in b:
                continue
            wa, ha, ma, *_ = a[k]
            wb, hb, mb, *_ = b[k]
            tallies[f'{q} vs tpa'][f'size /{wa // max(1, wb)}, mips {mb - ma:+d}'] += 1
    print(f'TPC files checked: {n}, images decoded: {stats["images decoded"]}'
          f' ({"top level only" if top_only else "every level of every face/frame"})')
    for title, c in tallies.items():
        print(f'\n{title}:')
        items = c.most_common(25) if title in ('size', 'mean alpha field') else sorted(c.items(), key=lambda kv: -kv[1])
        for k, v in items:
            print(f'  {v:6d}  {k}')
        if len(c) > 25 and title in ('size', 'mean alpha field'):
            print(f'  ... {len(c)} distinct values')
    print('\nblock statistics:')
    for k in sorted(stats):
        print(f'  {k}: {stats[k]}')
    print(f'\nheader notes ({len(notes)}):')
    for x in notes[:40]:
        print('  ' + x)
    if len(notes) > 40:
        print(f'  ... {len(notes) - 40} more')
    print(f'\nfailures ({len(failures)}):')
    for x in failures:
        print('  ' + x)
    return 1 if failures else 0


# ---- PNG output ---------------------------------------------------------------------------------

def find_tpc(g, name, prefer=('swpc_tex_tpa.erf', 'swpc_tex_gui.erf', 'patch.erf')):
    found = {os.path.basename(e.container).lower(): e for e in g.every_entry('tpc') if e.resref == name.lower()}
    for p in prefer:
        if p in found:
            return found[p]
    return next(iter(found.values()), None)


def checker(h, w, cell=8):
    y, x = np.mgrid[0:h, 0:w]
    v = np.where(((y // cell) + (x // cell)) % 2 == 0, 200, 140).astype(np.uint8)
    return np.dstack([v, v, v])


def over_checker(rgba):
    a = rgba[:, :, 3:4].astype(np.float32) / 255
    bg = checker(rgba.shape[0], rgba.shape[1]).astype(np.float32)
    return (rgba[:, :, :3] * a + bg * (1 - a)).astype(np.uint8)


def save_png(arr, path):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr).save(path)
    print('wrote', path)


def png_of(g, name, scale_to=None):
    from PIL import Image
    e = find_tpc(g, name)
    if e is None:
        print(f'{name}: not found')
        return None
    t = parse(kres.read_entry(e))
    if t.kind == 'cube':
        faces = [decode(t, i) for i in range(6)]
        s = t.width
        strip = np.zeros((s, 6 * s, 4), np.uint8)
        for i, f in enumerate(faces):
            strip[:, i * s:(i + 1) * s] = f
        img = strip
    elif t.kind == 'cycle':
        fw, fh = t.width // t.numx, t.height // t.numy
        img = np.zeros((t.height, t.width, 4), np.uint8)
        for i in range(t.numx * t.numy):
            r, c = divmod(i, t.numx)
            img[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw] = decode(t, i)
    else:
        img = decode(t)
    # Frames sit in the grid row-major from the first stored rows (the bottom of the picture), the
    # order the TGA flipbooks use; then flip everything so the PNG is upright.
    out = over_checker(img)[::-1].copy()
    if scale_to:
        k = max(1, scale_to // max(out.shape[:2]))
        out = np.asarray(Image.fromarray(out).resize((out.shape[1] * k, out.shape[0] * k), Image.NEAREST))
    save_png(out, os.path.join(OUT_DIR, f'{name}.png'))
    print(f'  {name}: {t.fmt} {t.kind} {t.width}x{t.height} mips={t.mips} alpha_mean={t.alpha_mean:.3f}'
          f' txi={t.txi.strip()!r}')
    return t


SAMPLES = [
    'fnt_d16x16',      # font: text must read correctly
    'po_pbastila',     # portrait (uncompressed or DXT): colours and upright face
    'pfha01',          # a head skin
    'cm_anchorhead',   # cube map
    'c_holododonna',   # flipbook 2x2
    'fx_tex_01',       # flipbook 1x16
    'lmg_numbers',     # text-like texture
    'biowarelogo',     # logo with text
    'gui_atmoss_1',    # DXT5 with alpha
]


def write_samples():
    g = kres.Game()
    for n in SAMPLES:
        png_of(g, n)
    contact_sheet(g)


def contact_sheet(g, cols=10, cell=96):
    """A grid of top levels from a spread of textures (every 40th TPC in tpa and gui)."""
    from PIL import Image
    picks = []
    for p in ('swpc_tex_tpa.erf', 'swpc_tex_gui.erf'):
        es = [e for e in kres.read_container(os.path.join(g.dir, 'TexturePacks', p)) if e.ext == 'tpc']
        picks += es[::40]
    rows = (len(picks) + cols - 1) // cols
    sheet = np.full((rows * cell, cols * cell, 3), 64, np.uint8)
    for k, e in enumerate(picks):
        t = parse(kres.read_entry(e))
        img = over_checker(decode(t))[::-1].copy()
        im = Image.fromarray(img)
        im.thumbnail((cell - 4, cell - 4))
        a = np.asarray(im)
        r, c = divmod(k, cols)
        sheet[r * cell + 2:r * cell + 2 + a.shape[0], c * cell + 2:c * cell + 2 + a.shape[1]] = a
    save_png(sheet, os.path.join(OUT_DIR, 'contact_sheet.png'))


# ---- cube map seams -----------------------------------------------------------------------------

# OpenGL's cube map face selection (major axis ma, then s = (sc/|ma| + 1)/2, t = (tc/|ma| + 1)/2,
# image row 0 = t near 0, column 0 = s near 0). Face order +X -X +Y -Y +Z -Z.
GL_FACES = [
    (0, +1, lambda x, y, z: (-z, -y)),
    (0, -1, lambda x, y, z: (+z, -y)),
    (1, +1, lambda x, y, z: (+x, +z)),
    (1, -1, lambda x, y, z: (+x, -z)),
    (2, +1, lambda x, y, z: (+x, -y)),
    (2, -1, lambda x, y, z: (-x, -y)),
]


def _face_dir(f, s, t):
    """Direction for face f at s, t in [-1, 1] (inverse of GL_FACES)."""
    axis, sign, _ = GL_FACES[f]
    # Solve sc = s, tc = t for each face.
    if f == 0:
        return np.stack([np.ones_like(s), -t, -s], -1)
    if f == 1:
        return np.stack([-np.ones_like(s), -t, s], -1)
    if f == 2:
        return np.stack([s, np.ones_like(s), t], -1)
    if f == 3:
        return np.stack([s, -np.ones_like(s), -t], -1)
    if f == 4:
        return np.stack([s, -t, np.ones_like(s)], -1)
    return np.stack([-s, -t, -np.ones_like(s)], -1)


def _lookup(dirs):
    """Face index and (row, col) in [0,1) coordinates for unit-ish directions (n, 3)."""
    ax = np.abs(dirs).argmax(1)
    out_f = np.empty(len(dirs), int)
    out_s = np.empty(len(dirs))
    out_t = np.empty(len(dirs))
    for f, (axis, sign, fn) in enumerate(GL_FACES):
        m = (ax == axis) & (np.sign(dirs[:, axis]) == sign)
        if not m.any():
            continue
        x, y, z = dirs[m].T
        sc, tc = fn(x, y, z)
        ma = np.abs(dirs[m, axis])
        out_f[m] = f
        out_s[m] = (sc / ma + 1) / 2
        out_t[m] = (tc / ma + 1) / 2
    return out_f, out_s, out_t


def _transform(img, k):
    """One of the 8 symmetries of a square: k%4 quarter turns counter-clockwise, then a flip if k>=4."""
    r = np.rot90(img, k % 4)
    return r[:, ::-1] if k >= 4 else r


def _edge_geometry(s):
    """For each face slot f and each of its 4 edges: (texel rows, cols just inside the edge,
    neighbouring slot, its rows, cols just across the edge), with faces laid out as OpenGL expects."""
    u = (np.arange(s) + 0.5) / s * 2 - 1
    out = []
    out_off = 1 + 1.0 / s
    idx = np.arange(s)
    for f in range(6):
        for edge in range(4):
            if edge == 0:
                ss, tt, rr, cc = u, np.full(s, -out_off), np.zeros(s, int), idx
            elif edge == 1:
                ss, tt, rr, cc = u, np.full(s, out_off), np.full(s, s - 1), idx
            elif edge == 2:
                ss, tt, rr, cc = np.full(s, -out_off), u, idx, np.zeros(s, int)
            else:
                ss, tt, rr, cc = np.full(s, out_off), u, idx, np.full(s, s - 1)
            nf, ns, nt = _lookup(_face_dir(f, ss, tt))
            assert (nf == nf[0]).all() and nf[0] != f
            nr = np.clip((nt * s).astype(int), 0, s - 1)
            nc = np.clip((ns * s).astype(int), 0, s - 1)
            out.append((f, rr, cc, int(nf[0]), nr, nc))
    return out


def best_transforms(faces):
    """Exhaustive search over the 8^6 per-face symmetries (stored face order kept) for the
    layout whose cube edges are most continuous. Returns (error as stored, best error, transforms)."""
    s = faces[0].shape[0]
    geo = _edge_geometry(s)
    tf = [[_transform(f[:, :, :3].astype(np.float32), k) for k in range(8)] for f in faces]
    total = np.zeros((8,) * 6, np.float32)
    for f, rr, cc, g, nr, nc in geo:
        a = np.stack([tf[f][k][rr, cc] for k in range(8)])      # (8, s, 3)
        b = np.stack([tf[g][k][nr, nc] for k in range(8)])
        e = np.abs(a[:, None] - b[None, :]).mean(axis=(2, 3))   # (8 kf, 8 kg)
        shape = [1] * 6
        shape[f], shape[g] = 8, 8
        if f < g:
            total += e.reshape(shape) / len(geo)
        else:
            total += e.T.reshape([8 if i in (f, g) else 1 for i in range(6)]) / len(geo)
    best = np.unravel_index(int(total.argmin()), total.shape)
    return float(total[(0,) * 6]), float(total[best]), [int(k) for k in best]


def cube_seams():
    """For every cube map in tpa, find the per-face symmetry (of 8) that makes the GL cube most
    continuous, with the stored face order kept, and report how often each assignment wins."""
    g = kres.Game()
    es = [e for e in kres.read_container(os.path.join(g.dir, 'TexturePacks', 'swpc_tex_tpa.erf'))
          if e.ext == 'tpc']
    wins = Counter()
    for e in es:
        t = parse(kres.read_entry(e))
        if t.kind != 'cube':
            continue
        faces = [decode(t, i) for i in range(6)]
        stored, best, ks = best_transforms(faces)
        # Texel-to-texel noise inside the faces, for scale.
        inner = np.mean([np.abs(np.diff(f[:, :, :3].astype(np.float32), axis=0)).mean() for f in faces])
        wins[tuple(ks)] += 1
        print('  %-20s %4d  as stored %6.1f  best %6.1f  inner %5.1f  transforms %s'
              % (e.resref, t.width, stored, best, inner, ks))
    print()
    print('winning per-face transforms (k = quarter turns CCW, +4 = then mirror left-right):')
    for k, v in wins.most_common():
        print(f'  {v:4d}  {list(k)}')


def panorama(faces, width=512):
    """Equirectangular view of a cube map sampled the OpenGL way, with world Z up (KOTOR's up
    axis): top row looks straight up (+Z), the middle row is the horizon, longitude 0 at the left
    edge looks along +X and longitude increases towards +Y."""
    h = width // 2
    lon = (np.arange(width) + 0.5) / width * 2 * np.pi
    lat = np.pi / 2 - (np.arange(h) + 0.5) / h * np.pi
    lon, lat = np.meshgrid(lon, lat)
    d = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], -1).reshape(-1, 3)
    f, s, t = _lookup(d)
    n = faces[0].shape[0]
    F = np.stack([x[:, :, :3] for x in faces])
    r = np.clip((t * n).astype(int), 0, n - 1)
    c = np.clip((s * n).astype(int), 0, n - 1)
    return F[f, r, c].reshape(h, width, 3)


def write_panoramas(names, transforms=None):
    g = kres.Game()
    for name in names:
        t = parse(kres.read_entry(find_tpc(g, name)))
        faces = [decode(t, i) for i in range(6)]
        ks = transforms or [0, 0, 0, 0, 0, 6]
        faces = [_transform(faces[i], ks[i]) for i in range(6)]
        tag = '_' + ''.join(map(str, ks))
        save_png(panorama(faces), os.path.join(OUT_DIR, f'{name}_pano{tag}.png'))


def main(argv):
    if argv and argv[0] == 'pano':
        ks = None
        names = argv[1:]
        if names and names[0].startswith('--t='):
            ks = [int(c) for c in names[0][4:]]
            names = names[1:]
        write_panoramas(names, ks)
        return 0
    if argv and argv[0] == 'png':
        g = kres.Game()
        for n in argv[1:]:
            png_of(g, n)
        return 0
    if argv and argv[0] == 'samples':
        write_samples()
        return 0
    if argv and argv[0] == 'cubeseams':
        cube_seams()
        return 0
    return check_all(top_only='--top' in argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
