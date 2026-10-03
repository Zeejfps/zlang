"""Parse and check every BWM walkmesh (WOK, PWK, DWK) in the install (exploration only).

    python kotor/tools/py/bwmprobe.py              check every walkmesh, print failure classes
    python kotor/tools/py/bwmprobe.py --render     also write the PNGs below to kotor/out/
    python kotor/tools/py/bwmprobe.py --dump NAME.EXT   print one walkmesh's header and tables

The format is described in kotor/docs/formats/bwm.md. Besides per-file structure checks, the
probe checks every area against its LYT (perimeter transitions name the room across the edge)
and its GIT (creatures and waypoints stand on walkable faces; door and placeable use hooks land
on walkable faces), using the stored AABB trees for the point queries the engine needs.

Every check result is a "class": a short name, a count and a few examples. Classes whose name
starts with "ok:" or "note:" are tallies, not failures.
"""

import math
import os
import struct
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kres      # noqa: E402
import twodapy   # noqa: E402
import gffpy     # noqa: E402

HEADER_SIZE = 136
OUT_DIR = os.path.join(HERE, '..', '..', 'out')

# AABB "most significant plane" bit values.
PLANES = {0: None, 1: (0, +1), 2: (1, +1), 4: (2, +1), 8: (0, -1), 16: (1, -1), 32: (2, -1)}


class Bad(Exception):
    pass


class Walkmesh:
    pass


def _vec(d, o):
    return struct.unpack_from('<3f', d, o)


def parse(d):
    """Parse a BWM V1.0 file. Raises Bad when a table falls outside the file."""
    if len(d) < HEADER_SIZE:
        raise Bad(f'{len(d)} bytes, shorter than the {HEADER_SIZE}-byte header')
    if d[:8] != b'BWM V1.0':
        raise Bad(f'magic {d[:8]!r}')
    w = Walkmesh()
    w.size = len(d)
    w.type, = struct.unpack_from('<I', d, 8)
    w.rel_hook1 = _vec(d, 12)
    w.rel_hook2 = _vec(d, 24)
    w.abs_hook1 = _vec(d, 36)
    w.abs_hook2 = _vec(d, 48)
    w.position = _vec(d, 60)
    (w.vertex_count, w.vertex_off, w.face_count, w.face_off, w.material_off, w.normal_off,
     w.distance_off, w.aabb_count, w.aabb_off, w.unknown108, w.adjacency_count, w.adjacency_off,
     w.edge_count, w.edge_off, w.perimeter_count, w.perimeter_off) = struct.unpack_from('<16I', d, 72)

    def table(name, off, count, size):
        if count == 0:
            return
        if off < HEADER_SIZE or off + count * size > len(d):
            raise Bad(f'{name}: {count} x {size} bytes at {off} outside the {len(d)}-byte file')

    table('vertices', w.vertex_off, w.vertex_count, 12)
    table('face indices', w.face_off, w.face_count, 12)
    table('materials', w.material_off, w.face_count, 4)
    table('normals', w.normal_off, w.face_count, 12)
    table('planar distances', w.distance_off, w.face_count, 4)
    table('aabb', w.aabb_off, w.aabb_count, 44)
    table('adjacency', w.adjacency_off, w.adjacency_count, 12)
    table('edges', w.edge_off, w.edge_count, 8)
    table('perimeters', w.perimeter_off, w.perimeter_count, 4)

    nv, nf = w.vertex_count, w.face_count
    w.vertices = [struct.unpack_from('<3f', d, w.vertex_off + 12 * i) for i in range(nv)]
    w.faces = [struct.unpack_from('<3I', d, w.face_off + 12 * i) for i in range(nf)]
    w.materials = list(struct.unpack_from(f'<{nf}I', d, w.material_off)) if nf else []
    w.normals = [struct.unpack_from('<3f', d, w.normal_off + 12 * i) for i in range(nf)]
    w.distances = list(struct.unpack_from(f'<{nf}f', d, w.distance_off)) if nf else []
    # AABB node: min[3] max[3] f32, face i32, unknown u32, plane u32, left i32, right i32
    w.aabb = [struct.unpack_from('<6fiIIii', d, w.aabb_off + 44 * i) for i in range(w.aabb_count)]
    w.adjacency = [struct.unpack_from('<3i', d, w.adjacency_off + 12 * i)
                   for i in range(w.adjacency_count)]
    w.edges = [struct.unpack_from('<2i', d, w.edge_off + 8 * i) for i in range(w.edge_count)]
    w.perimeters = list(struct.unpack_from(f'<{w.perimeter_count}I', d, w.perimeter_off)) \
        if w.perimeter_count else []
    return w


# ---------------------------------------------------------------------------------------------
# small vector helpers (plain Python: the probe should not depend on numpy)

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a):
    return math.sqrt(dot(a, a))


def face_corners(w, f):
    a, b, c = w.faces[f]
    return w.vertices[a], w.vertices[b], w.vertices[c]


def edge_vertices(w, edge):
    """Vertex indices of edge `edge` = 3 * face + k: from corner k to corner (k + 1) % 3."""
    f, k = divmod(edge, 3)
    tri = w.faces[f]
    return tri[k], tri[(k + 1) % 3]


# ---------------------------------------------------------------------------------------------
# reporting

class Report:
    def __init__(self):
        self.counts = Counter()
        self.examples = defaultdict(list)

    def add(self, cls, example=None, n=1):
        self.counts[cls] += n
        if example is not None and len(self.examples[cls]) < 4:
            self.examples[cls].append(example)

    def print(self):
        fails = [c for c in self.counts if not c.startswith(('ok:', 'note:'))]
        for title, keys in (('tallies', [c for c in self.counts if c not in fails]),
                            ('failure classes', fails)):
            print(f'\n== {title} ({len(keys)})')
            for c in sorted(keys):
                ex = '; '.join(str(e) for e in self.examples[c])
                print(f'{self.counts[c]:8d}  {c}' + (f'   e.g. {ex}' if ex else ''))


# ---------------------------------------------------------------------------------------------
# surfacemat.2da

def load_surfacemat(g):
    t = twodapy.parse(g.get('surfacemat', '2da'))
    rows = []
    for i in range(len(t.rows)):
        rows.append({c: t.get(i, c) for c in t.columns})
    return rows


def walkable_set(surf):
    return {i for i, r in enumerate(surf) if r.get('walk') == '1'}


# ---------------------------------------------------------------------------------------------
# per-file checks

def check_layout(name, w, rep):
    """Tables appear in a fixed order, packed after the header, and the file ends with them."""
    order = [('vertices', w.vertex_off, 12 * w.vertex_count),
             ('faces', w.face_off, 12 * w.face_count),
             ('materials', w.material_off, 4 * w.face_count),
             ('normals', w.normal_off, 12 * w.face_count),
             ('distances', w.distance_off, 4 * w.face_count),
             ('aabb', w.aabb_off, 44 * w.aabb_count),
             ('adjacency', w.adjacency_off, 12 * w.adjacency_count),
             ('edges', w.edge_off, 8 * w.edge_count),
             ('perimeters', w.perimeter_off, 4 * w.perimeter_count)]
    pos = HEADER_SIZE
    packed = True
    for tname, off, size in order:
        if size == 0:
            rep.add(f'note: empty table offset ({tname}) = {"0" if off == 0 else "next free byte" if off == pos else "other"}')
            continue
        if off != pos:
            packed = False
            rep.add('table not packed in the documented order', (name, tname, off, pos))
        pos = off + size
    if packed:
        rep.add('ok: tables packed in order after the header')
    if pos != w.size:
        rep.add('bytes after the last table', (name, w.size - pos))


def check_header(name, ext, w, rep):
    want = 1 if ext == 'wok' else 0
    if w.type != want:
        rep.add('walkmesh type does not match extension', (name, ext, w.type))
    if w.unknown108 != 0:
        rep.add('note: header +108 is not 0 (unused field holding junk)', (name, hex(w.unknown108)))
    hooks = (w.rel_hook1, w.rel_hook2, w.abs_hook1, w.abs_hook2)
    if ext == 'wok':
        if any(any(h) for h in hooks):
            rep.add('WOK with nonzero use hooks', name)
        return
    for i, (rel, ab) in enumerate(((w.rel_hook1, w.abs_hook1), (w.rel_hook2, w.abs_hook2)), 1):
        summed = tuple(r + p for r, p in zip(rel, w.position))
        if max(abs(a - s) for a, s in zip(ab, summed)) < 1e-4:
            rep.add(f'ok: {ext} abs hook {i} == rel hook {i} + position')
        elif not any(ab):
            rep.add(f'note: {ext} abs hook {i} left zero (not rel + position)')
        else:
            rep.add(f'{ext} abs hook {i} is neither rel+position nor zero', name)
    if ext == 'dwk':
        state = name[-1]
        has2 = any(w.rel_hook2)
        rep.add(f'note: dwk state {state}: rel hook 2 {"set" if has2 else "zero"}')


def check_faces(name, ext, w, rep, surf, walkable):
    nv, nf = w.vertex_count, w.face_count
    used = [False] * nv
    for f, tri in enumerate(w.faces):
        if any(i >= nv for i in tri):
            rep.add('face vertex index out of range', (name, f, tri))
            return False
        for i in tri:
            used[i] = True
        if len(set(tri)) < 3:
            rep.add('face repeats a vertex index', (name, f, tri))
    if not all(used):
        rep.add('note: vertices not used by any face', (name, used.count(False)))
    for f, m in enumerate(w.materials):
        if m >= len(surf):
            rep.add('material id outside surfacemat.2da', (name, f, m))
        rep.add(f'note: material {m:2d} faces in {ext}')
    # walkable faces first; adjacency count == walkable count (area walkmeshes)
    flags = [m in walkable for m in w.materials]
    nwalk = sum(flags)
    if any(flags[nwalk:]):
        rep.add(f'{ext}: walkable faces not all before non-walkable ones' if ext == 'wok'
                else f'note: {ext}: walkable faces not sorted first', name)
    if ext == 'wok' and w.face_count and w.adjacency_count != nwalk:
        rep.add('wok: adjacency count != walkable face count', (name, w.adjacency_count, nwalk))
    # normals, winding, plane distance
    pwk_zero = ext == 'pwk' and all(n == (0.0, 0.0, 0.0) for n in w.normals)
    if pwk_zero and nf:
        rep.add('note: pwk normals all zero and planar distances junk (not filled in)')
    for f in range(nf):
        p0, p1, p2 = face_corners(w, f)
        c = cross(sub(p1, p0), sub(p2, p0))
        a = length(c)
        if a < 1e-6:
            rep.add(f'note: {ext}: zero-area face (stored normal and distance meaningless)', (name, f))
            continue
        if pwk_zero:
            continue
        n = w.normals[f]
        if abs(length(n) - 1) > 1e-4:
            rep.add(f'{ext}: normal not unit length', (name, f, n))
        cn = (c[0] / a, c[1] / a, c[2] / a)
        if dot(cn, n) < 0.999:
            rep.add(f'{ext}: normal disagrees with counter-clockwise winding', (name, f, round(dot(cn, n), 4)))
        r = max(abs(dot(n, p) + w.distances[f]) for p in (p0, p1, p2))
        if r > 1e-3:
            rep.add(f'{ext}: corner off its plane (n.v + d != 0)', (name, f, round(r, 4)))
        if f < w.adjacency_count and cn[2] <= 0.0:
            rep.add(f'note: {ext}: walkable face that is vertical or faces down', (name, f, round(cn[2], 3)))
    return True


def check_aabb(name, w, rep):
    na, nf = w.aabb_count, w.face_count
    if na == 0:
        return
    if na != 2 * nf - 1:
        rep.add('aabb node count != 2 * faces - 1', (name, na, nf))
    seen = Counter()
    visited = set()
    parent = {}
    stack = [0]
    while stack:
        i = stack.pop()
        if i in visited:
            rep.add('aabb node reached twice', (name, i))
            continue
        visited.add(i)
        n = w.aabb[i]
        bmin, bmax, face, unk, plane, left, right = n[0:3], n[3:6], n[6], n[7], n[8], n[9], n[10]
        if unk != 4:
            rep.add('aabb node +28 != 4', (name, i, unk))
        if plane not in PLANES:
            rep.add('aabb plane value unknown', (name, i, plane))
        if i in parent:
            p = w.aabb[parent[i]]
            if any(bmin[k] < p[k] - 1e-5 or bmax[k] > p[3 + k] + 1e-5 for k in range(3)):
                rep.add('aabb child box outside parent box', (name, i))
        if face >= 0:
            if left != -1 or right != -1 or plane != 0:
                rep.add('aabb leaf with children or a plane', (name, i))
            if face >= nf:
                rep.add('aabb leaf face out of range', (name, i, face))
                continue
            seen[face] += 1
            corners = face_corners(w, face)
            lo = [min(c[k] for c in corners) for k in range(3)]
            hi = [max(c[k] for c in corners) for k in range(3)]
            slack = max(max(bmin[k] - lo[k], hi[k] - bmax[k]) for k in range(3))
            if slack > 1e-3:
                rep.add('aabb leaf box does not contain its face', (name, face, round(slack, 3)))
            pad = [lo[k] - bmin[k] for k in range(3)] + [bmax[k] - hi[k] for k in range(3)]
            if all(abs(x - 0.01) < 2e-4 for x in pad):
                rep.add('note: aabb leaf box == face bounds grown by 0.01 on every side')
            else:
                rep.add('note: aabb leaf box != face bounds grown by 0.01 (other slack)')
            continue
        if face != -1:
            rep.add('aabb face index < -1', (name, i, face))
        if not (0 <= left < na and 0 <= right < na):
            rep.add('aabb child index out of range', (name, i, left, right))
            continue
        if left != i + 1:
            rep.add('aabb left child is not the next node (not pre-order)', (name, i, left))
        if plane == 0:
            rep.add('aabb interior node without a plane', (name, i))
        lo_ = w.aabb[left]
        ro_ = w.aabb[right]
        union_lo = [min(lo_[k], ro_[k]) for k in range(3)]
        union_hi = [max(lo_[3 + k], ro_[3 + k]) for k in range(3)]
        if max(max(abs(union_lo[k] - bmin[k]), abs(union_hi[k] - bmax[k])) for k in range(3)) > 1e-4:
            rep.add('aabb interior box != union of children', (name, i))
        if plane in PLANES and PLANES[plane]:
            axis, sign = PLANES[plane]
            lc = lo_[axis] + lo_[3 + axis]
            rc = ro_[axis] + ro_[3 + axis]
            if (rc - lc) * sign > 0:
                rep.add('note: aabb plane: right child box centre is on the plane\'s side (agrees)')
            else:
                rep.add('note: aabb plane: right child box centre not on the plane\'s side', (name, i))
        parent[left] = i
        parent[right] = i
        stack.append(right)
        stack.append(left)
    if len(visited) != na:
        rep.add('aabb nodes unreachable from node 0', (name, na - len(visited)))
    missing = [f for f in range(nf) if seen[f] == 0]
    if missing:
        rep.add('faces missing from the aabb tree', (name, len(missing), missing[:4]))
    if any(v > 1 for v in seen.values()):
        rep.add('face in the aabb tree more than once', name)


def check_adjacency(name, w, rep):
    nadj = w.adjacency_count
    if nadj == 0:
        return
    for f, row in enumerate(w.adjacency):
        for k, t in enumerate(row):
            if t == -1:
                continue
            if not (0 <= t < 3 * nadj):
                rep.add('adjacency entry out of range', (name, f, k, t))
                continue
            g, j = divmod(t, 3)
            if g == f:
                rep.add('adjacency points into its own face', (name, f, k))
            if w.adjacency[g][j] != 3 * f + k:
                rep.add('adjacency not symmetric', (name, f, k, t, w.adjacency[g][j]))
            a0, a1 = edge_vertices(w, 3 * f + k)
            b0, b1 = edge_vertices(w, t)
            if (a0, a1) != (b1, b0):
                rep.add('adjacent edges do not share their vertices reversed', (name, f, k, t))


def check_perimeter(name, w, rep, walkable):
    nadj = w.adjacency_count
    if w.edge_count == 0 and w.perimeter_count == 0:
        if nadj:
            rep.add('walkable faces but no perimeter edges', name)
        return
    open_edges = {3 * f + k for f in range(nadj) for k in range(3) if w.adjacency[f][k] == -1}
    listed = [e for e, _ in w.edges]
    if len(set(listed)) != len(listed):
        rep.add('perimeter edge listed twice', name)
    if set(listed) != open_edges:
        rep.add('perimeter edges != walkable edges without adjacency',
                (name, len(set(listed) - open_edges), len(open_edges - set(listed))))
    else:
        rep.add('ok: perimeter edges == walkable edges without adjacency')
    for e, t in w.edges:
        if not (0 <= e < 3 * w.face_count):
            rep.add('perimeter edge index out of range', (name, e))
            return
        if t < -1:
            rep.add('perimeter transition < -1', (name, e, t))
    if not w.perimeters or w.perimeters[-1] != w.edge_count:
        rep.add('last perimeter end != edge count', (name, w.perimeters[-1:] or None, w.edge_count))
        return
    start = 0
    for end in w.perimeters:
        if end <= start:
            rep.add('perimeter loop ends not increasing', (name, w.perimeters))
            return
        loop = [w.edges[i][0] for i in range(start, end)]
        for i, e in enumerate(loop):
            _, v_end = edge_vertices(w, e)
            v_next, _ = edge_vertices(w, loop[(i + 1) % len(loop)])
            if v_end != v_next:
                rep.add('perimeter loop does not chain end-to-start', (name, start, i))
                break
        else:
            rep.add('ok: perimeter loop closes')
        start = end


# ---------------------------------------------------------------------------------------------
# point queries (what the engine needs: the walkable face under a point)

def point_in_triangle_xy(p, a, b, c, eps=1e-6):
    def side(o, u, v):
        return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
    d0, d1, d2 = side(a, b, p), side(b, c, p), side(c, a, p)
    return (d0 >= -eps and d1 >= -eps and d2 >= -eps) or (d0 <= eps and d1 <= eps and d2 <= eps)


def faces_under(w, x, y, pad=0.0):
    """Faces whose XY projection contains (x, y), found through the stored AABB tree, with the
    height of the face plane there. Faces with a vertical plane are skipped."""
    out = []
    if not w.aabb:
        return out
    stack = [0]
    while stack:
        n = w.aabb[stack.pop()]
        if x < n[0] - pad or x > n[3] + pad or y < n[1] - pad or y > n[4] + pad:
            continue
        if n[6] >= 0:
            f = n[6]
            if f >= w.face_count:
                continue
            a, b, c = face_corners(w, f)
            if point_in_triangle_xy((x, y), a, b, c):
                nrm = cross(sub(b, a), sub(c, a))
                if abs(nrm[2]) > 1e-9:
                    z = a[2] - (nrm[0] * (x - a[0]) + nrm[1] * (y - a[1])) / nrm[2]
                    out.append((f, z))
            continue
        stack.append(n[9])
        stack.append(n[10])
    return out


def faces_under_brute(w, x, y):
    out = []
    for f in range(w.face_count):
        a, b, c = face_corners(w, f)
        if point_in_triangle_xy((x, y), a, b, c):
            nrm = cross(sub(b, a), sub(c, a))
            if abs(nrm[2]) > 1e-9:
                out.append((f, a[2] - (nrm[0] * (x - a[0]) + nrm[1] * (y - a[1])) / nrm[2]))
    return out


# ---------------------------------------------------------------------------------------------
# areas: LYT rooms, transitions, GIT objects

def read_lyt(text):
    rooms = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        p = lines[i].split()
        if p and p[0] == 'roomcount':
            for j in range(int(p[1])):
                q = lines[i + 1 + j].split()
                rooms.append((q[0].lower(), tuple(float(v) for v in q[1:4])))
            i += int(p[1])
        i += 1
    return rooms


def check_transitions(g, woks, rep):
    """A perimeter edge's transition is the LYT index of the room across that edge."""
    for le in g.entries(ext='lyt'):
        rooms = read_lyt(kres.read_entry(le).decode('latin-1'))
        names = [r for r, _ in rooms]
        geo = {}
        for r in names:
            w = woks.get(r)
            if w and w.edge_count:
                geo[r] = [(w.vertices[edge_vertices(w, e)[0]], w.vertices[edge_vertices(w, e)[1]], t)
                          for e, t in w.edges]
        for i, r in enumerate(names):
            for a, b, t in geo.get(r, ()):
                if t < 0:
                    continue
                if t >= len(names) or t == i or names[t] not in geo:
                    rep.add('transition is not another walkmeshed room of this LYT', (le.resref, r, t))
                    continue
                best, back = 1e9, None
                for a2, b2, t2 in geo[names[t]]:
                    dd = max(max(abs(a[k] - b2[k]), abs(b[k] - a2[k])) for k in range(3))
                    if dd < best:
                        best, back = dd, t2
                if best < 1e-3 and back == i:
                    rep.add('ok: transition edge meets a reversed edge of that room pointing back')
                elif best < 0.1 and back == i:
                    rep.add('note: transition edge meets that room\'s edge only within 0.1', (le.resref, r, names[t], round(best, 3)))
                else:
                    rep.add('transition edge has no matching edge in that room', (le.resref, r, names[t], round(best, 3), back))


def module_areas(g):
    """(module rim, its _s rim or None, area resref) for every module in modules/."""
    mods = os.path.join(g.dir, 'modules')
    out = []
    for n in sorted(os.listdir(mods)):
        low = n.lower()
        if not low.endswith('.rim') or low.endswith('_s.rim'):
            continue
        main = os.path.join(mods, n)
        s = os.path.join(mods, n[:-4] + '_s.rim')
        out.append((main, s if os.path.exists(s) else None))
    return out


def area_on_walkable(woks_in_area, x, y, z, walkable, tol=1.0):
    """'hit' if a walkable face lies within tol of z under (x, y), 'nonwalk' if only
    non-walkable ones do, 'miss' otherwise."""
    best = None
    for w in woks_in_area:
        for f, fz in faces_under(w, x, y, pad=1e-3):
            if abs(fz - z) <= tol:
                kind = 'hit' if w.materials[f] in walkable else 'nonwalk'
                if best != 'hit':
                    best = kind
    return best or 'miss'


def check_git(g, woks, dwks, pwks, rep, walkable):
    gd = twodapy.parse(g.get('genericdoors', '2da'))
    pl = twodapy.parse(g.get('placeables', '2da'))
    for main, s in module_areas(g):
        ents = kres.read_container(main) + (kres.read_container(s) if s else [])
        local = {(e.resref, e.ext): e for e in ents}
        gits = [e for e in ents if e.ext == 'git']
        for ge in gits:
            lyt = g.get(ge.resref, 'lyt')
            if lyt is None:
                rep.add('note: module area without a LYT', ge.resref)
                continue
            rooms = [woks[r] for r, _ in read_lyt(lyt.decode('latin-1')) if r in woks and woks[r].aabb]
            git = gffpy.read(kres.read_entry(ge))
            for lst, xs in (('Creature List', ('XPosition', 'YPosition', 'ZPosition')),
                            ('WaypointList', ('XPosition', 'YPosition', 'ZPosition'))):
                for o in git.get(lst, []):
                    x, y, z = (o[k] for k in xs)
                    r = area_on_walkable(rooms, x, y, z, walkable)
                    rep.add(f'note: GIT {lst} position over walkmesh: {r}',
                            None if r == 'hit' else (ge.resref, o.get('Tag', o.get('TemplateResRef', '?'))))

            def template(resref, ext):
                e = local.get((resref.lower(), ext))
                return kres.read_entry(e) if e else g.get(resref, ext)

            def hooks_on_walk(x, y, z, bearing, hooks, label):
                c, s_ = math.cos(bearing), math.sin(bearing)
                for hname, h in hooks:
                    if not any(h):
                        continue
                    hx = x + c * h[0] - s_ * h[1]
                    hy = y + s_ * h[0] + c * h[1]
                    r = area_on_walkable(rooms, hx, hy, z + h[2], walkable)
                    rep.add(f'note: {label} {hname} over walkmesh: {r}')

            for o in git.get('Door List', []):
                t = template(o['TemplateResRef'], 'utd')
                if t is None:
                    continue
                utd = gffpy.read(t)
                if utd.get('Appearance', 0) != 0:
                    rep.add('note: door with nonzero Appearance (not via genericdoors)', o['TemplateResRef'])
                    continue
                model = gd.get(utd['GenericType'], 'modelname').lower()
                w = dwks.get(model + '0')
                if w is None:
                    continue
                hooks_on_walk(o['X'], o['Y'], o['Z'], o['Bearing'],
                              [('abs hook 1', w.abs_hook1), ('abs hook 2', w.abs_hook2)], 'door closed')
            for o in git.get('Placeable List', []):
                t = template(o['TemplateResRef'], 'utp')
                if t is None:
                    continue
                utp = gffpy.read(t)
                try:
                    model = pl.get(utp['Appearance'], 'modelname').lower()
                except (IndexError, KeyError):
                    continue
                w = pwks.get(model)
                if w is None:
                    continue
                plus = [tuple(h[k] + w.position[k] for k in range(3)) if any(h) else h
                        for h in (w.rel_hook1, w.rel_hook2)]
                hooks_on_walk(o['X'], o['Y'], o['Z'], o['Bearing'],
                              [('rel hook 1 + position', plus[0]), ('rel hook 2 + position', plus[1])],
                              'placeable')
                hooks_on_walk(o['X'], o['Y'], o['Z'], o['Bearing'],
                              [('rel hook 1 as stored', w.rel_hook1), ('rel hook 2 as stored', w.rel_hook2)],
                              'placeable')


def check_dwk_frames(dwks, rep):
    """Evidence for the DWK coordinate frame. An open door's walkmesh is a thin piece at one
    jamb of the doorway; with vertex + position it lands on an x end of the closed walkmesh
    (also taken as vertex + position), with the stored vertices alone it mostly sits at x = 0,
    in the middle of the doorway."""
    for door in sorted({n[:-1] for n in dwks}):
        closed = dwks.get(door + '0')
        if not closed or not closed.vertex_count:
            continue
        for reading, add in (('vertex + position', True), ('vertex as stored', False)):
            def xs(w):
                return [v[0] + (w.position[0] if add else 0.0) for v in w.vertices]
            cx = xs(closed)
            for s in '12':
                w = dwks.get(door + s)
                if not w or not w.vertex_count:
                    continue
                ox = xs(w)
                if max(ox) - min(ox) > 1.0:
                    rep.add(f'note: dwk open state wider than 1 (not a jamb piece), {reading}')
                    continue
                mid = (max(ox) + min(ox)) / 2
                at_end = min(abs(mid - min(cx)), abs(mid - max(cx))) < 0.2
                at_centre = abs(mid) < 0.2
                rep.add(f'note: dwk open state piece, {reading}: '
                        + ('at an x end of the closed walkmesh' if at_end else
                           'at the doorway centre' if at_centre else 'elsewhere'),
                        None if at_end else door + s)


def check_tree_queries(name, w, rep):
    """The tree finds every face the brute-force search finds, at sample points (face centroids)."""
    for f in range(0, w.adjacency_count, max(1, w.adjacency_count // 25)):
        a, b, c = face_corners(w, f)
        x = (a[0] + b[0] + c[0]) / 3
        y = (a[1] + b[1] + c[1]) / 3
        brute = {ff for ff, _ in faces_under_brute(w, x, y)}
        tree = {ff for ff, _ in faces_under(w, x, y)}
        if brute - tree:
            rep.add('aabb query misses faces brute force finds (stored boxes)', (name, f))
        else:
            rep.add('ok: aabb query == brute force at a walkable face centroid')


# ---------------------------------------------------------------------------------------------
# rendering

MAT_COLOURS = {
    0: (255, 0, 255), 1: (150, 110, 70), 2: (90, 90, 160), 3: (70, 160, 60), 4: (150, 150, 150),
    5: (170, 120, 50), 6: (60, 120, 220), 7: (60, 60, 60), 8: (180, 220, 240), 9: (170, 40, 90),
    10: (120, 140, 170), 11: (80, 150, 200), 12: (70, 100, 60), 13: (110, 80, 50),
    14: (180, 160, 40), 15: (240, 80, 0), 16: (0, 0, 0), 17: (20, 40, 140), 18: (250, 250, 0),
    19: (40, 90, 30), 30: (255, 255, 255),
}


def model_space(w, v):
    """A PWK/DWK vertex or rel hook in the door's or placeable's model space."""
    return (v[0] + w.position[0], v[1] + w.position[1], v[2] + w.position[2])


def placed(x, y, z, bearing, v):
    c, s = math.cos(bearing), math.sin(bearing)
    return (x + c * v[0] - s * v[1], y + s * v[0] + c * v[1], z + v[2])


def git_overlays(g, dwks, pwks, module):
    """Outlines of closed door walkmeshes and placeable walkmeshes placed by the module's GIT
    (model space = vertex + position, then rotate by Bearing and translate), use hooks as dots."""
    mods = os.path.join(g.dir, 'modules')
    ents = []
    for n in (module + '.rim', module + '_s.rim'):
        p = os.path.join(mods, n)
        if os.path.exists(p):
            ents += kres.read_container(p)
    local = {(e.resref, e.ext): e for e in ents}

    def template(resref, ext):
        e = local.get((resref.lower(), ext))
        return kres.read_entry(e) if e else g.get(resref, ext)
    gd = twodapy.parse(g.get('genericdoors', '2da'))
    pl = twodapy.parse(g.get('placeables', '2da'))
    out = []
    for ge in [e for e in ents if e.ext == 'git']:
        git = gffpy.read(kres.read_entry(ge))
        for o in git.get('Door List', []):
            t = template(o['TemplateResRef'], 'utd')
            utd = gffpy.read(t) if t else None
            if not utd or utd.get('Appearance', 0) != 0:
                continue
            w = dwks.get(gd.get(utd['GenericType'], 'modelname').lower() + '0')
            if not w:
                continue
            at = (o['X'], o['Y'], o['Z'], o['Bearing'])
            for f in range(w.face_count):
                out.append(([placed(*at, model_space(w, v)) for v in face_corners(w, f)], (255, 140, 0)))
            for h in (w.abs_hook1, w.abs_hook2):
                out.append(([placed(*at, h)], (230, 0, 0)))
        for o in git.get('Placeable List', []):
            t = template(o['TemplateResRef'], 'utp')
            try:
                w = pwks.get(pl.get(gffpy.read(t)['Appearance'], 'modelname').lower())
            except (IndexError, KeyError, TypeError, gffpy.GffError):
                continue
            if not w:
                continue
            at = (o['X'], o['Y'], o['Z'], o['Bearing'])
            for f in range(w.face_count):
                out.append(([placed(*at, model_space(w, v)) for v in face_corners(w, f)], (0, 150, 0)))
            for h in (w.rel_hook1, w.rel_hook2):
                if any(h):
                    out.append(([placed(*at, model_space(w, h))], (0, 150, 0)))
        for o in git.get('Creature List', []):
            out.append(([(o['XPosition'], o['YPosition'], o['ZPosition'])], (230, 0, 230)))
    return out


def render_area(g, woks, lyt_name, path, scale=10, extra=(), crop=None, edges=False):
    """Top-down view of an area's room walkmeshes as stored (they are already in area space),
    coloured by material; perimeter edges black, transition edges red; `extra` outlines on top."""
    from PIL import Image, ImageDraw
    rooms = [(r, p) for r, p in read_lyt(g.get(lyt_name, 'lyt').decode('latin-1')) if r in woks]
    if crop:
        x0, y0, x1, y1 = crop
    else:
        pts = [v for r, _ in rooms for v in woks[r].vertices]
        x0 = min(p[0] for p in pts) - 2
        y0 = min(p[1] for p in pts) - 2
        x1 = max(p[0] for p in pts) + 2
        y1 = max(p[1] for p in pts) + 2
    W, H = int((x1 - x0) * scale), int((y1 - y0) * scale)
    img = Image.new('RGB', (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)

    def P(v):
        return ((v[0] - x0) * scale, (y1 - v[1]) * scale)
    for r, _ in rooms:
        w = woks[r]
        # non-walkable faces first, so floors are drawn over the footprints of walls
        order = sorted(range(w.face_count), key=lambda f: (f < w.adjacency_count, face_corners(w, f)[0][2]))
        for f in order:
            a, b, c = face_corners(w, f)
            dr.polygon([P(a), P(b), P(c)], fill=MAT_COLOURS.get(w.materials[f], (255, 0, 255)),
                       outline=(255, 255, 255) if edges and f < w.adjacency_count else None)
    for r, _ in rooms:
        w = woks[r]
        for e, t in w.edges:
            a, b = (w.vertices[i] for i in edge_vertices(w, e))
            dr.line([P(a), P(b)], fill=(220, 0, 0) if t >= 0 else (0, 0, 0), width=3 if t >= 0 else 1)
    for poly, colour in extra:
        if len(poly) == 1:
            x, y = P(poly[0])
            dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=colour)
        else:
            dr.polygon([P(p) for p in poly], outline=colour)
    for r, pos in rooms:
        x, y = P(pos)
        dr.text((x + 3, y + 3), r, fill=(0, 0, 0))
    img.save(path)
    return W, H


def render_dwk(g, dwks, door, path, scale=60):
    """Each state of a door walkmesh in model space (vertex + position): plan (x-y) and elevation
    (x-z). Faces outlined in their material colour (grey: the closed state, for reference); abs use
    hooks red; the walkmesh position green; the model origin a grey cross."""
    from PIL import Image, ImageDraw
    states = [dwks[door + s] for s in '012']
    allv = [model_space(w, v) for w in states for v in w.vertices] + \
           [h for w in states for h in (w.abs_hook1, w.abs_hook2, w.position)]
    lo = [min(v[k] for v in allv) - 0.5 for k in range(3)]
    hi = [max(v[k] for v in allv) + 0.5 for k in range(3)]
    pw = int((hi[0] - lo[0]) * scale)
    ph_xy = int((hi[1] - lo[1]) * scale)
    ph_xz = int((hi[2] - lo[2]) * scale)
    img = Image.new('RGB', (3 * pw + 40, ph_xy + ph_xz + 60), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    for si, w in enumerate(states):
        ox = 10 + si * (pw + 10)
        dr.text((ox, 2), f'{door}{si}.dwk ({"closed open1 open2".split()[si]})', fill=(0, 0, 0))
        for view, oy, ph, ax in (('plan x-y', 20, ph_xy, 1), ('elevation x-z', 40 + ph_xy, ph_xz, 2)):
            def P(v):
                return (ox + (v[0] - lo[0]) * scale, oy + (hi[ax] - v[ax]) * scale)
            dr.rectangle([ox, oy, ox + pw, oy + ph], outline=(200, 200, 200))
            dr.text((ox + 2, oy + 2), view, fill=(120, 120, 120))
            o = P((0, 0, 0))
            dr.line([o[0] - 6, o[1], o[0] + 6, o[1]], fill=(160, 160, 160))
            dr.line([o[0], o[1] - 6, o[0], o[1] + 6], fill=(160, 160, 160))
            layers = [(states[0], (200, 200, 200))] if si else []
            for lw, col in layers + [(w, None)]:
                for f in range(lw.face_count):
                    pts = [P(model_space(lw, v)) for v in face_corners(lw, f)]
                    dr.polygon(pts, outline=col or MAT_COLOURS.get(lw.materials[f], (255, 0, 255)))
            for h in (w.abs_hook1, w.abs_hook2):
                if any(h):
                    x, y = P(h)
                    dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(220, 0, 0))
            x, y = P(w.position)
            dr.line([x - 5, y - 5, x + 5, y + 5], fill=(0, 160, 0), width=2)
            dr.line([x - 5, y + 5, x + 5, y - 5], fill=(0, 160, 0), width=2)
    img.save(path)


# ---------------------------------------------------------------------------------------------

def dump(g, spec):
    resref, _, ext = spec.rpartition('.')
    w = parse(g.get(resref, ext))
    for k in ('type', 'rel_hook1', 'rel_hook2', 'abs_hook1', 'abs_hook2', 'position', 'vertex_count',
              'face_count', 'aabb_count', 'unknown108', 'adjacency_count', 'edge_count',
              'perimeter_count'):
        print(f'{k:16} {getattr(w, k)}')
    for name in ('vertices', 'faces', 'materials', 'normals', 'distances', 'aabb', 'adjacency',
                 'edges', 'perimeters'):
        rows = getattr(w, name)
        print(f'-- {name} ({len(rows)})')
        for i, r in enumerate(rows[:40]):
            print(f'  {i:4d} {r}')


def main(argv):
    g = kres.Game()
    if '--dump' in argv:
        dump(g, argv[argv.index('--dump') + 1])
        return 0
    rep = Report()
    surf = load_surfacemat(g)
    walkable = walkable_set(surf)
    woks, pwks, dwks = {}, {}, {}
    files = 0
    seen = set()
    for ext, table in (('wok', woks), ('pwk', pwks), ('dwk', dwks)):
        for e in g.every_entry(ext):
            key = (e.resref, ext)
            if key in seen:
                rep.add('note: walkmesh present in several containers', key)
            seen.add(key)
            files += 1
            rep.add(f'note: {ext} files in {os.path.relpath(e.container, g.dir)}')
            data = kres.read_entry(e)
            try:
                w = parse(data)
            except Bad as ex:
                rep.add('parse failed', (e.resref, ext, str(ex)))
                continue
            table[e.resref] = w
            rep.add(f'note: {ext} {"empty (no vertices)" if w.vertex_count == 0 else "with geometry"}')
            if ext != 'wok' and (w.aabb_count or w.adjacency_count or w.edge_count or w.perimeter_count):
                rep.add(f'{ext} with aabb/adjacency/perimeter tables', e.resref)
            if ext == 'wok' and w.face_count and not w.aabb_count:
                rep.add('wok with faces but no aabb tree', e.resref)
            check_layout(e.resref, w, rep)
            check_header(e.resref, ext, w, rep)
            if check_faces(e.resref, ext, w, rep, surf, walkable):
                check_aabb(e.resref, w, rep)
                check_adjacency(e.resref, w, rep)
                check_perimeter(e.resref, w, rep, walkable)
                if ext == 'wok' and w.aabb_count:
                    check_tree_queries(e.resref, w, rep)
    # naming
    for n in dwks:
        if n[-1] not in '012' or not all(n[:-1] + s in dwks for s in '012'):
            rep.add('dwk name is not <model>0/1/2 with all three states', n)
    check_dwk_frames(dwks, rep)
    check_transitions(g, woks, rep)
    check_git(g, woks, dwks, pwks, rep, walkable)
    print(f'walkmeshes checked: {files} (wok {len(woks)}, pwk {len(pwks)}, dwk {len(dwks)})')
    rep.print()
    if '--render' in argv:
        os.makedirs(OUT_DIR, exist_ok=True)
        p = os.path.join(OUT_DIR, 'bwm_area_m01aa.png')
        print('wrote', p, render_area(g, woks, 'm01aa', p, scale=10))
        # Manaan doors (dor_lma01) have a nonzero walkmesh position: a check of vertex + position
        p = os.path.join(OUT_DIR, 'bwm_area_m28aa_doors.png')
        print('wrote', p, render_area(g, woks, 'm28aa', p, scale=25, crop=(128, 112, 192, 140),
                                      extra=git_overlays(g, dwks, pwks, 'manm28aa'), edges=True))
        p = os.path.join(OUT_DIR, 'bwm_area_m01aa_objects.png')
        print('wrote', p, render_area(g, woks, 'm01aa', p, scale=25, crop=(10, 100, 40, 150),
                                      extra=git_overlays(g, dwks, pwks, 'end_m01aa'), edges=True))
        for door in ('dor_lma01', 'dor_lhr01'):
            p = os.path.join(OUT_DIR, f'bwm_dwk_{door}.png')
            render_dwk(g, dwks, door, p)
            print('wrote', p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
