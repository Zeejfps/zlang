"""Decode every TGA in the install and tally the variants the game ships.

    python kotor/tools/py/tgaprobe.py             decode all, print tallies and failures
    python kotor/tools/py/tgaprobe.py samples     write a few lightmaps and a water flipbook to kotor/out/tga/
    python kotor/tools/py/tgaprobe.py frames      score the frame order of the 8x8 water flipbooks

As a library: tgaprobe.decode(data) -> (RGBA uint8 array with row 0 = BOTTOM of the picture, info dict).
Nothing here is used by the game.
"""

import os
import struct
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out', 'tga'))


def _unrle(d, pos, count, bpp):
    """Expand `count` pixels of TGA run-length data of `bpp` bytes each starting at d[pos]."""
    out = bytearray()
    need = count * bpp
    while len(out) < need:
        if pos >= len(d):
            raise ValueError('RLE data runs past the end of the file')
        h = d[pos]
        pos += 1
        n = (h & 0x7F) + 1
        if h & 0x80:
            px = d[pos:pos + bpp]
            if len(px) < bpp:
                raise ValueError('RLE packet cut short')
            out += px * n
            pos += bpp
        else:
            raw = d[pos:pos + n * bpp]
            if len(raw) < n * bpp:
                raise ValueError('RLE packet cut short')
            out += raw
            pos += n * bpp
    if len(out) > need:
        raise ValueError('RLE packet crosses the end of the image')
    return bytes(out), pos


def decode(d):
    if len(d) < 18:
        raise ValueError('short header')
    id_len, cmap_type, itype, cmap_first, cmap_len, cmap_bits, x0, y0, w, h, bits, desc = \
        struct.unpack_from('<BBBHHBHHHHBB', d, 0)
    info = dict(id_len=id_len, cmap_type=cmap_type, image_type=itype, cmap_len=cmap_len, cmap_bits=cmap_bits,
                x_origin=x0, y_origin=y0, width=w, height=h, bits=bits, descriptor=desc,
                alpha_bits=desc & 15, right_to_left=bool(desc & 0x10), top_down=bool(desc & 0x20),
                interleave=desc >> 6)
    if itype not in (1, 2, 3, 9, 10, 11):
        raise ValueError(f'unsupported image type {itype}')
    if info['interleave']:
        raise ValueError('interleaved TGA')
    pos = 18 + id_len
    palette = None
    if cmap_type == 1:
        cb = (cmap_bits + 7) // 8
        raw = d[pos:pos + cmap_len * cb]
        pos += cmap_len * cb
        palette = _to_rgba(np.frombuffer(raw, np.uint8).reshape(cmap_len, cb), cmap_bits)
    elif cmap_type != 0:
        raise ValueError(f'colour map type {cmap_type}')
    bpp = (bits + 7) // 8
    n = w * h
    if itype in (9, 10, 11):
        pix, pos = _unrle(d, pos, n, bpp)
    else:
        pix = d[pos:pos + n * bpp]
        if len(pix) < n * bpp:
            raise ValueError(f'pixel data cut short ({len(pix)} of {n * bpp} bytes)')
        pos += n * bpp
    a = np.frombuffer(pix, np.uint8).reshape(n, bpp)
    if itype in (1, 9):
        if palette is None:
            raise ValueError('colour-mapped image without a colour map')
        idx = a[:, 0].astype(int) if bpp == 1 else (a[:, 0] | (a[:, 1].astype(int) << 8))
        rgba = palette[np.clip(idx - cmap_first, 0, len(palette) - 1)]
    elif itype in (3, 11):
        g = a[:, 0]
        rgba = np.stack([g, g, g, a[:, 1] if bpp == 2 else np.full(n, 255, np.uint8)], 1)
    else:
        rgba = _to_rgba(a, bits)
    img = rgba.reshape(h, w, 4)
    # Normalise to row 0 = bottom, column 0 = left (the file's default, bottom-left origin).
    if info['top_down']:
        img = img[::-1]
    if info['right_to_left']:
        img = img[:, ::-1]
    info['trailing'] = len(d) - pos
    info['footer'] = d[-18:-2] == b'TRUEVISION-XFILE' if len(d) >= 26 else False
    if info['footer']:
        ext_off, dev_off = struct.unpack_from('<II', d, len(d) - 26)
        info['ext_offset'] = ext_off
        if ext_off:
            info['ext_size'] = struct.unpack_from('<H', d, ext_off)[0]
            info['ext_attr_type'] = d[ext_off + 494] if ext_off + 494 < len(d) else None
    return np.ascontiguousarray(img), info


def _to_rgba(a, bits):
    n = len(a)
    if bits in (24, 32):
        b, g, r = a[:, 0], a[:, 1], a[:, 2]
        al = a[:, 3] if bits == 32 else np.full(n, 255, np.uint8)
        return np.stack([r, g, b, al], 1)
    if bits in (15, 16):
        v = a[:, 0].astype(np.uint16) | (a[:, 1].astype(np.uint16) << 8)
        r = ((v >> 10) & 31) * 255 // 31
        g = ((v >> 5) & 31) * 255 // 31
        b = (v & 31) * 255 // 31
        al = np.where(v & 0x8000, 255, 0) if bits == 16 else np.full(n, 255)
        return np.stack([r, g, b, al], 1).astype(np.uint8)
    if bits == 8:
        g = a[:, 0]
        return np.stack([g, g, g, np.full(n, 255, np.uint8)], 1)
    raise ValueError(f'unsupported pixel depth {bits}')


def check_all():
    g = kres.Game()
    tallies = defaultdict(Counter)
    failures = []
    txi = {}
    for e in g.every_entry('txi'):
        txi.setdefault((e.resref, e.container), kres.read_entry(e).decode('latin-1'))
    txi_by_name = defaultdict(list)
    for (r, c), t in txi.items():
        txi_by_name[r].append((c, t))
    n = 0
    for e in g.every_entry('tga'):
        n += 1
        d = kres.read_entry(e)
        where = os.path.basename(os.path.dirname(e.container)) if e.container.lower().endswith('.tga') \
            else os.path.basename(e.container)
        name = f'{e.resref}.tga in {where}'
        try:
            img, info = decode(d)
        except Exception as ex:
            failures.append(f'{name}: {ex}')
            continue
        group = 'lightmaps*.bif' if 'lightmaps' in where else where
        tallies['container'][group] += 1
        tallies['variant'][f'type {info["image_type"]}, {info["bits"]} bit, descriptor 0x{info["descriptor"]:02x}'
                           f' (alpha bits {info["alpha_bits"]}, top_down={info["top_down"]},'
                           f' right_to_left={info["right_to_left"]}), id {info["id_len"]},'
                           f' cmap {info["cmap_type"]}'] += 1
        tallies['trailing bytes after pixels'][f'{info["trailing"]}'
                                               + (' (TGA 2.0 footer)' if info['footer'] else '')] += 1
        if info.get('ext_offset'):
            tallies['extension area'][f'size {info.get("ext_size")}, attributes type {info.get("ext_attr_type")}'] += 1
        tallies['size'][f'{info["width"]}x{info["height"]}'] += 1
        if info['bits'] == 32:
            a = img[:, :, 3]
            tallies['32-bit alpha'][f'{group}: ' + ('all 255' if a.min() == 255 else 'all 0' if a.max() == 0
                                                     else 'varies')] += 1
        pair = [t for c, t in txi_by_name.get(e.resref, []) if c == e.container]
        if pair:
            t = pair[0]
            first = ' '.join(x.split()[0] for x in t.splitlines() if x.split())
            tallies['paired TXI (same name, same container): keywords'][f'{group}: {first}'] += 1
        else:
            tallies['paired TXI (same name, same container): keywords'][f'{group}: (none)'] += 1
        if 'lightmaps' in where and not e.resref.endswith(tuple(f'lm{i}' for i in range(10))):
            tallies['lightmap names not ending lmN'][e.resref[-5:]] += 1
    print(f'TGA files checked: {n}')
    for title, c in tallies.items():
        print(f'\n{title}:')
        for k, v in c.most_common(30):
            print(f'  {v:6d}  {k}')
        if len(c) > 30:
            print(f'  ... {len(c)} distinct')
    print(f'\nfailures ({len(failures)}):')
    for x in failures:
        print('  ' + x)
    return 1 if failures else 0


def save_png(arr, path, scale=1):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.fromarray(arr)
    if scale > 1:
        im = im.resize((arr.shape[1] * scale, arr.shape[0] * scale), Image.NEAREST)
    im.save(path)
    print('wrote', path)


def samples():
    g = kres.Game()
    want = ['m01aa_01a_lm0', 'm01aa_02a_lm0', 'm09zz_01a_lm000', 'm17mg_01c_a0001l', 'lda_water01b', 'chrome1']
    seen = set()
    for e in g.every_entry('tga'):
        if e.resref in want and e.resref not in seen:
            seen.add(e.resref)
            img, info = decode(kres.read_entry(e))
            # PNG rows run top-down, so flip the bottom-up rows for viewing.
            save_png(img[::-1, :, :3].copy(), os.path.join(OUT_DIR, f'{e.resref}.png'),
                     scale=max(1, 256 // info['width']))


def frames():
    """The water flipbooks are one 256x256 grey TGA holding an 8x8 grid of 32x32 frames. Score
    candidate frame orders by how similar consecutive frames are (including the wrap-around)."""
    g = kres.Game()
    for e in g.every_entry('tga'):
        if 'textures.bif' not in e.container:
            continue
        img, info = decode(kres.read_entry(e))
        grey = img[:, :, 0].astype(np.float32)   # row 0 = bottom of the picture
        nx = ny = 8
        fw, fh = info['width'] // nx, info['height'] // ny

        def cell(r, c):  # r counts rows of frames from the bottom of the picture
            return grey[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]

        orders = {
            'rows from top, left to right': [(ny - 1 - i // nx, i % nx) for i in range(nx * ny)],
            'rows from bottom, left to right': [(i // nx, i % nx) for i in range(nx * ny)],
            'columns from left, top down': [(ny - 1 - i % ny, i // ny) for i in range(nx * ny)],
            'columns from left, bottom up': [(i % ny, i // ny) for i in range(nx * ny)],
        }
        res = []
        for k, o in orders.items():
            cs = [cell(*rc) for rc in o]
            cost = np.mean([np.abs(cs[i] - cs[(i + 1) % len(cs)]).mean() for i in range(len(cs))])
            res.append((cost, k))
        res.sort()
        print(f'{e.resref:16s} ' + '  '.join(f'{k}: {c:5.2f}' for c, k in res))


def main(argv):
    if argv and argv[0] == 'samples':
        samples()
        return 0
    if argv and argv[0] == 'frames':
        frames()
        return 0
    return check_all()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
