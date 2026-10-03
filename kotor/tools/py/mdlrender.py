"""Render KOTOR models to PNG with a small numpy rasterizer, to eyeball geometry, UVs and lightmaps.

    python kotor/tools/py/mdlrender.py MODEL [MODEL...] [--view front|side|top|iso] [--size N]
                                       [--wire] [--no-tex] [--anim NAME --time T]
    python kotor/tools/py/mdlrender.py MODEL --head HEAD [--anim NAME --time T]  body with a head at headhook
    python kotor/tools/py/mdlrender.py --lyt AREA [--view top] [--no-sky]         every room of an area layout
    python kotor/tools/py/mdlrender.py --uv MODEL        texture0 with each mesh's UV0 wireframe on top

Writes kotor/out/mdl/MODEL[_view].png. Exploration only; the game's renderer is ctxlang + GL.

Conventions checked with these renders (see docs/formats/mdl.md):
  * node transforms: child = parent * T(position) * R(orientation), quaternion stored w,x,y,z in
    the node header and x,y,z,w in orientation controllers; Z is up.
  * UVs: texel row = v * height counted from the first row stored in the file (TPC), i.e. the GL
    convention of uploading rows in file order and sampling with v as-is.
  * lightmaps: texture1 sampled with uv1, multiplied onto texture0 sampled with uv0.
  * animations: orientation keys replace, position keys are added to the geometry position.
  * skins: bonemap/qbones/tbones indexed by depth-first tree order.

Experiments kept as switches: LM_FLIP=1 (sample lightmaps with 1-v), ANIM_POS_ABSOLUTE=1,
SKIN_HEADER_BIND=1 (inverse bind from node headers instead of qbones/tbones).
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402
import kmdl  # noqa: E402

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out', 'mdl'))

_game = None
_tex_cache = {}


def game():
    global _game
    if _game is None:
        _game = kres.Game()
    return _game


def load_model(name):
    g = game()
    mdl = g.get(name, 'mdl')
    mdx = g.get(name, 'mdx')
    if mdl is None:
        raise SystemExit(f'{name}.mdl not found')
    return kmdl.parse(mdl, mdx or b'', name)


def load_texture(name):
    """RGBA float array (rows in file order) or None."""
    name = name.lower()
    if not name or name == 'null':
        return None
    if name in _tex_cache:
        return _tex_cache[name]
    img = None
    g = game()
    try:
        import tpcprobe
        e = tpcprobe.find_tpc(g, name)
        if e is not None:
            t = tpcprobe.parse(kres.read_entry(e))
            img = tpcprobe.decode(t, 0, 0)
    except Exception as err:  # noqa: BLE001
        print(f'  texture {name}: tpc decode failed: {err}')
    if img is None:
        d = g.get(name, 'tga')
        if d is not None:
            import tgaprobe
            img, info = tgaprobe.decode(d)
            # tgaprobe returns row 0 = bottom of the picture, which for the usual bottom-left
            # origin TGA is the first row in the file.
    if img is not None:
        img = img.astype(np.float32) / 255.0
    _tex_cache[name] = img
    return img


# --- math ------------------------------------------------------------------------------------

def quat_wxyz_to_mat(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def local_matrix(pos, quat_wxyz):
    m = np.eye(4)
    m[:3, :3] = quat_wxyz_to_mat(quat_wxyz)
    m[:3, 3] = pos
    return m


def sample_controller(c, t):
    """Linear/slerp-free sampling of a keyed controller at time t (enough for a still)."""
    times = c.times
    vals = c.values
    if not times:
        return None
    if t <= times[0]:
        return vals[0]
    for i in range(1, len(times)):
        if t <= times[i]:
            t0, t1 = times[i - 1], times[i]
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            a, b = vals[i - 1], vals[i]
            if c.bezier:
                cols = c.columns & 0xF
                a, b = a[:cols], b[:cols]
            if c.type == 20 and len(a) == 4:
                if sum(x * y for x, y in zip(a, b)) < 0:
                    b = tuple(-x for x in b)
            return tuple(x + (y - x) * f for x, y in zip(a, b))
    v = vals[-1]
    return v[:c.columns & 0xF] if c.bezier else v


def node_transforms(m, anim=None, t=0.0):
    """name_index -> 4x4 model-space matrix."""
    pose = {}
    scale = m.anim_scale or 1.0
    if anim is not None:
        for n in anim.nodes:
            p = q = None
            for c in n.controllers:
                if c.type == 8:
                    p = sample_controller(c, t)
                elif c.type == 20:
                    v = sample_controller(c, t)
                    q = (v[3], v[0], v[1], v[2])
            pose[n.name.lower()] = (p, q)
    out = {}

    def walk(n, parent):
        pos, quat = n.position, n.orientation
        if n.name.lower() in pose:
            p, q = pose[n.name.lower()]
            if p is not None:
                # animation position keys are offsets from the node's geometry position (468 of
                # the 527 animated models in the install only make sense this way; see mdl.md)
                if os.environ.get('ANIM_POS_ABSOLUTE'):
                    pos = p
                else:
                    pos = tuple(a + b * scale for a, b in zip(pos, p))
            quat = q if q is not None else quat
        w = parent @ local_matrix(pos, quat)
        out[n.name_index] = w
        for c in n.children:
            walk(c, w)

    walk(m.root, np.eye(4))
    return out


# --- rasterizer --------------------------------------------------------------------------------

def view_matrix(view):
    # Camera looks along -Z of camera space; we map model space (Z up) to screen x right, y up.
    # Rows: screen x, screen y, depth (larger = nearer the camera). Models face +Y with Z up.
    if view == 'front':      # camera on +Y looking at the model's face
        r = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], float)
    elif view == 'back':
        r = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
    elif view == 'side':
        r = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float)
    elif view == 'top':
        r = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    else:  # iso
        a = math.radians(-35)
        b = math.radians(30)
        rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
        base = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
        r = rx @ base @ rz
    return r


def collect(m, xf, use_tex=True, bind_xf=None):
    """List of draw batches: (world positions Nx3, normals Nx3, uv0 Nx2|None, uv1|None,
    faces Fx3, texture0 img|None, lightmap img|None, mesh dict, node)."""
    batches = []
    if bind_xf is None:
        bind_xf = node_transforms(m)
    for n in m.nodes:
        M = n.mesh
        if not M or not M['vertex_count'] or n.saber or n.aabb:
            continue
        if not M['render']:
            continue
        mdx = M['mdx']
        pos = mdx.get('position') or M['mdl_vertices']
        if pos is None:
            continue
        P = np.array(pos, float)
        Wm = xf[n.name_index]
        Pw = P @ Wm[:3, :3].T + Wm[:3, 3]
        N = np.array(mdx['normal'], float) @ Wm[:3, :3].T if 'normal' in mdx else None
        S = n.skin
        if S and S['weights'] and S['qbones']:
            # world = sum_i w_i * Bone_i(now) * InvBind_i * v. The bonemap, qbones and tbones are
            # indexed by the node's position in the depth-first walk of the tree (m.nodes order),
            # not by its name index; MDX bone values are bone slots, bonemap maps node -> slot.
            slot_node = {}
            for dfs, sl in enumerate(S['bonemap']):
                if sl >= 0:
                    slot_node[int(sl)] = dfs
            mats = {}
            for sl, dfs in slot_node.items():
                bone = m.nodes[dfs]
                if os.environ.get('SKIN_HEADER_BIND'):
                    mats[sl] = xf[bone.name_index] @ np.linalg.inv(bind_xf[bone.name_index]) @ bind_xf[n.name_index]
                else:
                    inv = local_matrix(S['tbones'][dfs], S['qbones'][dfs])
                    mats[sl] = xf[bone.name_index] @ inv
            Wt = np.array(S['weights'], float)
            Bi = np.array(S['bones'], float)
            out = np.zeros_like(P)
            outn = np.zeros_like(P) if N is not None else None
            Nl = np.array(mdx['normal'], float) if 'normal' in mdx else None
            for k in range(4):
                for sl, Mx in mats.items():
                    sel = (Bi[:, k] == sl) & (Wt[:, k] > 0)
                    if not sel.any():
                        continue
                    w = Wt[sel, k][:, None]
                    out[sel] += w * (P[sel] @ Mx[:3, :3].T + Mx[:3, 3])
                    if outn is not None:
                        outn[sel] += w * (Nl[sel] @ Mx[:3, :3].T)
            Pw = out
            N = outn
        F = np.array([f[4] for f in M['faces']], int)
        if len(F) == 0:
            continue
        t0 = load_texture(M['texture0']) if use_tex else None
        t1 = load_texture(M['texture1']) if use_tex and M['lightmapped'] else None
        uv0 = np.array(mdx['uv0'], float) if 'uv0' in mdx else None
        uv1 = np.array(mdx['uv1'], float) if 'uv1' in mdx else None
        batches.append((Pw, N, uv0, uv1, F, t0, t1, M, n))
    return batches


def sample(img, uv):
    h, w = img.shape[:2]
    u = uv[:, 0] % 1.0
    v = uv[:, 1] % 1.0
    x = np.clip((u * w).astype(int), 0, w - 1)
    y = np.clip((v * h).astype(int), 0, h - 1)
    return img[y, x]


def render(batches, view='front', size=512, wire=False, bg=(0.15, 0.15, 0.18), cull=True):
    R = view_matrix(view)
    allp = np.concatenate([b[0] for b in batches]) if batches else np.zeros((1, 3))
    sp = allp @ R.T
    lo = sp.min(0)
    hi = sp.max(0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
    scale = (size * 0.92) / span
    cx = (lo[0] + hi[0]) / 2
    cy = (lo[1] + hi[1]) / 2
    img = np.zeros((size, size, 3), np.float32)
    img[:] = bg
    zbuf = np.full((size, size), -np.inf, np.float32)
    light = np.array([0.3, 0.5, 0.8])
    light /= np.linalg.norm(light)
    for Pw, N, uv0, uv1, F, t0, t1, M, n in batches:
        S = Pw @ R.T
        X = (S[:, 0] - cx) * scale + size / 2
        Y = size / 2 - (S[:, 1] - cy) * scale
        Z = S[:, 2]
        Ns = N @ R.T if N is not None else None
        base = np.array(M['diffuse'], np.float32) if t0 is None else None
        # Back-face culling: (v1-v0) x (v2-v0) is the outward face normal in KOTOR data.
        fn = np.cross(Pw[F[:, 1]] - Pw[F[:, 0]], Pw[F[:, 2]] - Pw[F[:, 0]])
        facing = fn @ R[2] > 0
        for fi, f in enumerate(F):
            if cull and not facing[fi]:
                continue
            a, b, c = f
            xs = X[[a, b, c]]
            ys = Y[[a, b, c]]
            x0 = max(int(math.floor(xs.min())), 0)
            x1 = min(int(math.ceil(xs.max())), size - 1)
            y0 = max(int(math.floor(ys.min())), 0)
            y1 = min(int(math.ceil(ys.max())), size - 1)
            if x0 > x1 or y0 > y1:
                continue
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-12:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
            l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if wire:
                inside &= (np.minimum(np.minimum(l0, l1), l2) < 0.04)
            if not inside.any():
                continue
            z = l0 * Z[a] + l1 * Z[b] + l2 * Z[c]
            iy, ix = np.nonzero(inside)
            iy0 = iy + y0
            ix0 = ix + x0
            zz = z[iy, ix]
            closer = zz > zbuf[iy0, ix0]
            if not closer.any():
                continue
            iy, ix, iy0, ix0, zz = iy[closer], ix[closer], iy0[closer], ix0[closer], zz[closer]
            w0, w1, w2 = l0[iy, ix], l1[iy, ix], l2[iy, ix]
            if Ns is not None:
                nn = w0[:, None] * Ns[a] + w1[:, None] * Ns[b] + w2[:, None] * Ns[c]
                nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-9
                shade = 0.35 + 0.65 * np.abs(nn @ light)
            else:
                shade = np.ones(len(zz))
            if t0 is not None and uv0 is not None:
                uv = w0[:, None] * uv0[a] + w1[:, None] * uv0[b] + w2[:, None] * uv0[c]
                col = sample(t0, uv)
                alpha = col[:, 3]
                col = col[:, :3]
                keep = alpha > 0.3
                if not keep.any():
                    continue
                iy0, ix0, zz, col, shade = iy0[keep], ix0[keep], zz[keep], col[keep], shade[keep]
                w0, w1, w2 = w0[keep], w1[keep], w2[keep]
            else:
                col = np.tile(base if base is not None else np.array([0.7, 0.7, 0.7]), (len(zz), 1))
            if t1 is not None and uv1 is not None:
                uv = w0[:, None] * uv1[a] + w1[:, None] * uv1[b] + w2[:, None] * uv1[c]
                if os.environ.get('LM_FLIP'):  # experiment: sample the lightmap with 1 - v
                    uv = np.stack([uv[:, 0], 1 - uv[:, 1]], 1)
                lm = sample(t1, uv)[:, :3]
                col = col * lm * 1.0
                shade = np.ones(len(zz))
            img[iy0, ix0] = np.clip(col * shade[:, None], 0, 1)
            zbuf[iy0, ix0] = zz
    return (img * 255).astype(np.uint8)


def save(arr, path):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr).save(path)
    print('wrote', path)


def uv_sheet(name, size=512):
    """texture0 of every mesh with its UV0 triangles drawn on top, v down from file row 0."""
    from PIL import Image, ImageDraw
    m = load_model(name)
    done = set()
    for n in m.nodes:
        M = n.mesh
        if not M or 'uv0' not in M['mdx'] or not M['texture0'] or M['texture0'].lower() in done:
            continue
        t = load_texture(M['texture0'])
        if t is None:
            continue
        done.add(M['texture0'].lower())
        im = Image.fromarray((t[:, :, :3] * 255).astype(np.uint8)).resize((size, size))
        d = ImageDraw.Draw(im)
        uv = M['mdx']['uv0']
        for f in M['faces']:
            pts = [(uv[v][0] * size, uv[v][1] * size) for v in f[4]]
            d.polygon(pts, outline=(255, 0, 255))
        path = os.path.join(OUT, f'uv_{name}_{M["texture0"].lower()}.png')
        os.makedirs(OUT, exist_ok=True)
        im.save(path)
        print('wrote', path)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == '--uv':
        for name in argv[1:]:
            uv_sheet(name)
        return 0
    if argv[0] == '--lyt':
        # every room of an area layout, placed at its LYT position (rooms are not rotated)
        name = argv[1]
        view = argv[argv.index('--view') + 1] if '--view' in argv else 'top'
        size = int(argv[argv.index('--size') + 1]) if '--size' in argv else 1024
        text = game().get(name, 'lyt').decode('latin-1').splitlines()
        rooms = []
        i = 0
        while i < len(text):
            parts = text[i].split()
            if parts[:1] == ['roomcount']:
                for k in range(int(parts[1])):
                    r = text[i + 1 + k].split()
                    rooms.append((r[0], tuple(float(v) for v in r[1:4])))
                break
            i += 1
        batches = []
        for room, off in rooms:
            m = load_model(room)
            xf = node_transforms(m)
            rb = collect(m, xf)
            allp = np.concatenate([b[0] for b in rb]) if rb else np.zeros((1, 3))
            if '--no-sky' in argv and (allp.max(0) - allp.min(0)).max() > 150:
                print('  skipping', room, '(sky-sized)')
                continue
            for b in rb:
                batches.append((b[0] + np.array(off),) + b[1:])
        arr = render(batches, view, size)
        save(arr, os.path.join(OUT, f'lyt_{name}_{view}.png'))
        return 0
    view = argv[argv.index('--view') + 1] if '--view' in argv else 'front'
    size = int(argv[argv.index('--size') + 1]) if '--size' in argv else 512
    anim = argv[argv.index('--anim') + 1] if '--anim' in argv else None
    t = float(argv[argv.index('--time') + 1]) if '--time' in argv else 0.0
    wire = '--wire' in argv
    use_tex = '--no-tex' not in argv
    skip = {'--view', '--size', '--anim', '--time', '--head', '--attach'}
    names = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in skip)]
    for name in names:
        m = load_model(name)
        a = None
        if anim:
            chain = [m]
            while not any(x.name.lower() == anim.lower() for x in chain[-1].anims):
                sm = chain[-1].supermodel.lower()
                if sm in ('', 'null'):
                    raise SystemExit(f'{anim}: not found in {name} or its supermodels')
                chain.append(load_model(sm))
            a = next(x for x in chain[-1].anims if x.name.lower() == anim.lower())
        xf = node_transforms(m, a, t)
        batches = collect(m, xf, use_tex)
        for i, arg in enumerate(argv):
            if arg == '--attach':
                # --attach MODEL:NODE puts MODEL's root at NODE (weapons at rhand/lhand)
                am_name, node_name = argv[i + 1].split(':')
                am = load_model(am_name)
                hook = next(n for n in m.nodes if n.name.lower() == node_name.lower())
                axf = {k: xf[hook.name_index] @ v for k, v in node_transforms(am).items()}
                batches += collect(am, axf, use_tex)
        if '--head' in argv:
            # attach a head model at the body's headhook, as the engine does for B-type bodies
            hm = load_model(argv[argv.index('--head') + 1])
            hook = next(n for n in m.nodes if n.name.lower() == 'headhook')
            # the head plays its own animations (its supermodel chain), never the body's
            ha = None
            if anim:
                chain = [hm]
                while chain[-1] and not any(x.name.lower() == anim.lower() for x in chain[-1].anims):
                    sm = chain[-1].supermodel.lower()
                    chain.append(load_model(sm) if sm not in ('', 'null') else None)
                if chain[-1]:
                    ha = next(x for x in chain[-1].anims if x.name.lower() == anim.lower())
            hxf = node_transforms(hm, ha, t)
            base = xf[hook.name_index]
            hxf = {k: base @ v for k, v in hxf.items()}
            batches += collect(hm, hxf, use_tex)
        arr = render(batches, view, size, wire)
        suffix = f'_{view}' + (f'_{anim}{t:g}' if anim else '') + ('_wire' if wire else '')
        save(arr, os.path.join(OUT, f'{name}{suffix}.png'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
