"""Parse every MDL/MDX in the install with kmdl and check it (exploration tool, not the game).

    python kotor/tools/py/mdlprobe.py [--limit N] [--out FILE]

Checks: the parsed structures tile the MDL model data exactly (no gaps, no overlaps); MDX vertex
blocks tile the MDX file (each followed by one sentinel row); node tree, controller, mesh, skin,
dangly, AABB, emitter, light, reference, saber and animation invariants listed in
kotor/docs/formats/mdl.md. Prints failure classes with examples, then statistics used by the doc.
"""

import collections
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402
import kmdl  # noqa: E402


class Tally:
    def __init__(self):
        self.c = collections.defaultdict(collections.Counter)
        self.ex = collections.defaultdict(dict)

    def add(self, table, key, example=None, n=1):
        self.c[table][key] += n
        if example is not None and key not in self.ex[table]:
            self.ex[table][key] = example

    def dump(self, out, table, top=60):
        c = self.c.get(table)
        if not c:
            print(f'\n## {table}: (none)', file=out)
            return
        print(f'\n## {table} ({sum(c.values())} total, {len(c)} keys)', file=out)
        for k, v in c.most_common(top):
            ex = self.ex[table].get(k)
            print(f'  {k!r}: {v}' + (f'   e.g. {ex}' if ex is not None else ''), file=out)
        if len(c) > top:
            print(f'  ... {len(c) - top} more', file=out)


T = Tally()
FAIL = Tally()


def fail(kind, model, detail=''):
    FAIL.add('failures', kind, f'{model}: {detail}')


def near(a, b, eps=1e-3):
    return abs(a - b) <= eps * max(1.0, abs(a), abs(b))


def vlen(v):
    return math.sqrt(sum(c * c for c in v))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def check_coverage(name, data, m):
    """The parsed structures account for every byte of the model data, once."""
    D = data[12:]
    pos = 0
    for off, size, what in sorted(m.claims):
        if off < pos:
            fail('mdl-overlap', name, f'{what} at {off} overlaps up to {pos}')
        elif off > pos:
            fail('mdl-gap', name, f'{off - pos} bytes before {what} at {off}')
        pos = max(pos, off + size)
    if pos != len(D):
        fail('mdl-tail', name, f'structures end at {pos}, data at {len(D)}')


def check_mdx_coverage(name, m, mdx):
    blocks = []
    for n in m.nodes:
        M = n.mesh
        if M and M['vertex_count'] and M['mdx_stride']:
            blocks.append((M['mdx_data_offset'], M['vertex_count'], M['mdx_stride'], n))
    blocks.sort(key=lambda b: b[0])
    pos = 0
    for off, nv, stride, n in blocks:
        pos += pos % 16  # the writer pads by (end % 16), not up to a multiple of 16
        if off != pos:
            fail('mdx-gap', name, f'{n.name} block at {off}, expected {pos}')
        end = off + nv * stride
        # one sentinel row follows every block
        if end + stride <= len(mdx):
            row = mdx[end:end + stride]
            import struct
            p = struct.unpack_from('<3f', row, 0)
            T.add('mdx sentinel position', tuple(round(v) for v in p), name)
            fl = struct.unpack_from(f'<{stride // 4}f', row, 0)
            T.add('mdx sentinel row (kind, rest)', (n.kind, tuple(round(v, 3) for v in fl[3:])), name)
        else:
            fail('mdx-no-sentinel', name, n.name)
        pos = end + stride
    if blocks and pos != len(mdx):
        fail('mdx-tail', name, f'blocks end at {pos}, mdx is {len(mdx)}')
    if not blocks:
        T.add('mdx size when no mesh data', len(mdx), name)


def check_controllers(model, n, anim, owner_names):
    used = []
    for c in n.controllers:
        cols = c.columns & 0xF
        per_row = 1 if c.compressed else (3 * cols if c.bezier else cols)
        used.append((c.time_index, c.rows))
        used.append((c.data_index, c.rows * per_row))
    pos = 0
    tiled = True
    for off, size in sorted(used):
        if off != pos:
            tiled = False
        pos = off + size
    if n.controllers:
        T.add('controller key+data ranges tile the float array', tiled and pos == n.controller_data_count, model)
        if not (tiled and pos == n.controller_data_count):
            fail('ctrl-data-not-tiled', model, f'{n.name} {sorted(used)} of {n.controller_data_count}')
        order = [k for c in n.controllers for k in (c.time_index, c.data_index)]
        T.add('controller arrays order: times then data, controller by controller', order == sorted(order), model)
    for c in n.controllers:
        kind = n.kind
        key = (kind if anim is None else 'anim:' + kind, c.type, c.name, c.columns)
        T.add('controllers (node kind, id, name, columns byte)', key, model)
        T.add('controller u16 at +4 (value, id, in animation)', (c.unknown, c.type, anim is not None), model)
        T.add('controller pad bytes', c.pad.hex(), model)
        if c.name is None:
            fail('ctrl-unknown-id', model, f'{n.kind} {n.name} id {c.type}')
        if c.bezier:
            T.add('bezier controllers', (c.type, c.name, anim is not None), model)
        if anim is None:
            T.add('geometry controller rows', (c.rows, c.times[0] if c.times else None) if c.rows <= 1 else 'many', model)
        else:
            T.add('anim controller rows > 1', c.rows > 1)
            prev = -1e9
            for t in c.times:
                if t < prev - 1e-6:
                    fail('ctrl-time-decreasing', model, f'{anim.name}/{n.name} {c.name}')
                    break
                prev = t
            if c.times and (c.times[0] < -1e-4 or c.times[-1] > anim.length + 1e-3):
                fail('ctrl-time-outside-length', model,
                     f'{anim.name}/{n.name} {c.name} {c.times[0]:.3f}..{c.times[-1]:.3f} len {anim.length:.3f}')
        if c.type == 20:
            T.add('orientation encoding', ('compressed' if c.compressed else f'cols{c.columns}',
                                           'anim' if anim else 'geom'), model)
            for q in c.values:
                if len(q) == 4 and not c.bezier:
                    L = vlen(q)
                    if abs(L - 1) > 0.01:
                        fail('quat-not-unit', model, f'{n.name} |q|={L:.4f}')
                        break
        if anim is None and c.type == 8 and c.rows == 1:
            if not all(near(a, b) for a, b in zip(c.values[0], n.position)):
                fail('header-position-differs-from-controller', model, n.name)
        if anim is None and c.type == 20 and c.rows == 1 and not c.compressed:
            x, y, z, w = c.values[0]
            hw, hx, hy, hz = n.orientation
            same = all(near(a, b) for a, b in zip((x, y, z, w), (hx, hy, hz, hw)))
            neg = all(near(a, -b) for a, b in zip((x, y, z, w), (hx, hy, hz, hw)))
            if not (same or neg):
                fail('header-orientation-differs-from-controller', model,
                     f'{n.name} ctrl xyzw {c.values[0]} header wxyz {n.orientation}')


def check_mesh(model, n, game_textures):
    M = n.mesh
    nv = M['vertex_count']
    T.add('mesh fn pointers (kind)', (n.kind, M['fn']), model)
    T.add('mesh transparency hint', M['transparency_hint'], model)
    T.add('mesh flags (lightmapped, rotate, background, shadow, beaming, render)',
          (M['lightmapped'], M['rotate_texture'], M['background'], M['shadow'], M['beaming'],
           M['render']), model)
    T.add('mesh byte 314', M['unknown314'], model)
    T.add('mesh byte 315', M['unknown315'], model)
    T.add('mesh unknown212 (3 ints)', M['unknown212'], model)
    T.add('mesh bytes 224..231', M['saber_bytes'].hex(), model)
    T.add('mesh u32 at 320', M['unknown320'], model)
    T.add('mesh animate_uv', M['animate_uv'], model)
    if M['animate_uv']:
        T.add('animate_uv params (dirx, diry, jitter, speed)',
              (round(M['uv_direction'][0], 3), round(M['uv_direction'][1], 3),
               round(M['uv_jitter'], 3), round(M['uv_jitter_speed'], 3)), model)
    T.add('mesh texture_count', M['texture_count'], model)
    named = sum(1 for k in ('texture0', 'texture1', 'texture2', 'texture3') if M[k] and M[k].lower() != 'null')
    T.add('texture_count vs named textures', (M['texture_count'], named), model)
    T.add('texture2/3 raw nonempty', (bool(M['texture2']), bool(M['texture3'])), model)
    T.add('mdx flags (kind)', (n.kind, hex(M['mdx_flags'])), model)
    T.add('mdx offsets by flags', (hex(M['mdx_flags']), M['mdx_stride'], M['mdx_offsets'],
                                    (n.skin['mdx_weights'], n.skin['mdx_bones']) if n.skin else None), model)
    T.add('diffuse', tuple(round(v, 2) for v in M['diffuse']), model)
    T.add('ambient', tuple(round(v, 2) for v in M['ambient']), model)
    T.add('index arrays counts (counts, offsets, inverted)',
          (M['index_counts'][1], M['index_offsets'][1], M['inverted_counter'][1]), model)
    for k in ('texture0', 'texture1'):
        t = M[k].lower()
        if t and t != 'null':
            have = t in game_textures
            T.add(f'{k} resolves to', game_textures.get(t, 'missing'), (model, t))
    if M['lightmapped']:
        T.add('lightmapped: texture1 set / uv1 present', (bool(M['texture1']), bool(M['mdx_flags'] & kmdl.MDX_UV1)), model)
    else:
        T.add('not lightmapped: texture1 set / uv1 present', (bool(M['texture1']), bool(M['mdx_flags'] & kmdl.MDX_UV1)), model)
    if M['mdx_flags'] & kmdl.MDX_TANGENT0:
        T.add('tangent space meshes: texture0', M['texture0'].lower(), model)
    # MDX flag/offset consistency
    for bit, slot, comps, key in kmdl.MDX_ATTRS:
        has = bool(M['mdx_flags'] & bit)
        off = M['mdx_offsets'][slot]
        if has != (off != -1):
            fail('mdx-flag-offset-mismatch', model, f'{n.name} {key} flag {has} offset {off}')
    size = 0
    for bit, slot, comps, key in kmdl.MDX_ATTRS:
        if M['mdx_flags'] & bit:
            size += 4 * comps
    if n.skin:
        size += 32
    if nv and size != M['mdx_stride']:
        fail('mdx-stride-not-sum', model, f'{n.name} stride {M["mdx_stride"]} vs {size} flags {M["mdx_flags"]:#x}')
    # faces
    faces = M['faces']
    if n.saber:
        # Saber meshes keep placeholder faces (zero normals, junk adjacency) and no index list;
        # the blade is built from the saber vertex arrays instead. Nothing more to check here.
        T.add('saber face normals all zero', all(f[0] == (0.0, 0.0, 0.0) for f in faces), model)
        return
    if M['index_lists']:
        flat = [v for f in faces for v in f[4]]
        if M['index_lists'][0] != flat:
            fail('index-list-differs-from-faces', model, n.name)
        if M['index_counts'][1] != 1:
            fail('index-lists-not-one', model, n.name)
    elif faces:
        fail('faces-without-index-list', model, n.name)
    T.add('inverted counter value', 'n/a' if not M['inverted_counter_values'] else 'present', model)
    verts = M['mdl_vertices']
    pos = M['mdx'].get('position')
    if nv and verts is None:
        fail('mesh-no-mdl-vertices', model, n.name)
    if pos is not None and verts is not None:
        bad = sum(1 for a, b in zip(verts, pos) if not all(near(x, y, 1e-5) for x, y in zip(a, b)))
        if bad:
            fail('mdx-position-differs-from-mdl', model, f'{n.name}: {bad}/{nv}')
    vs = pos or verts
    area = 0.0
    adj_bad = 0
    for i, (nrm, dist, mat, adj, vi) in enumerate(faces):
        T.add('face material (kind)', (n.kind, mat), model)
        if any(v >= nv for v in vi):
            fail('face-vertex-out-of-range', model, f'{n.name} face {i} {vi} nv {nv}')
            continue
        for a in adj:
            if a != -1 and not (0 <= a < len(faces)):
                adj_bad += 1
        if vs:
            a, b, c = (vs[v] for v in vi)
            cr = cross(sub(b, a), sub(c, a))
            L = vlen(cr)
            area += L / 2
            if L > 1e-8:
                geo = tuple(x / L for x in cr)
                d = dot(geo, nrm)
                T.add('face normal vs (v1-v0)x(v2-v0)', 'same' if d > 0.99 else ('opposite' if d < -0.99 else 'other'), model)
                if abs(vlen(nrm) - 1) > 1e-2:
                    fail('face-normal-not-unit', model, f'{n.name} face {i}')
                pd = -dot(nrm, a)
                if not near(pd, dist, 1e-2):
                    alts = [-dot(nrm, vs[v]) for v in vi]
                    T.add('bad plane distance matches -n.v of', tuple(near(x, dist, 1e-2) for x in alts), (model, n.name, i))
                    fail('face-plane-distance', model, f'{n.name} face {i}: {dist} vs {pd}')
                    T.add('face plane distance wrong (kind, render, faces)', (n.kind, n.mesh['render'], d > 0.99), (model, n.name))
            else:
                T.add('degenerate faces', n.kind, model)
    if adj_bad:
        fail('face-adjacency-out-of-range', model, f'{n.name}: {adj_bad}')
    if vs and faces:
        if not near(area, M['total_area'], 1e-2):
            T.add('total_area vs computed', 'differs', (model, n.name, M['total_area'], area))
        else:
            T.add('total_area vs computed', 'equal', model)
    if vs:
        lo = tuple(min(v[k] for v in vs) for k in range(3))
        hi = tuple(max(v[k] for v in vs) for k in range(3))
        ok = all(near(a, b, 1e-3) for a, b in zip(lo + hi, M['bmin'] + M['bmax']))
        lo0 = tuple(min(a, 0.0) for a in lo)
        hi0 = tuple(max(a, 0.0) for a in hi)
        ok0 = all(near(a, b, 1e-3) for a, b in zip(lo0 + hi0, M['bmin'] + M['bmax']))
        T.add('mesh bbox == extent of vertices and the node origin', ok0, (model, n.name, M['bmin'], M['bmax'], lo, hi))
        avg = tuple(sum(v[k] for v in vs) / len(vs) for k in range(3))
        fv = [vs[v] for f in faces for v in f[4] if v < len(vs)]
        favg = tuple(sum(v[k] for v in fv) / len(fv) for k in range(3)) if fv else avg
        which = 'vertex mean' if all(near(a, b, 1e-3) for a, b in zip(avg, M['average'])) else (
            'mean over face corners' if all(near(a, b, 1e-3) for a, b in zip(favg, M['average'])) else 'neither')
        T.add('mesh average point is', which, (model, n.name, M['average'], avg, favg))
        cen = tuple((a + b) / 2 for a, b in zip(lo, hi))
        rmax = max(vlen(sub(v, M['average'])) for v in vs)
        T.add('mesh radius == max |v - average|', near(rmax, M['radius'], 1e-2), (model, n.name, M['radius'], rmax))
    nr = M['mdx'].get('normal')
    if nr:
        bad = sum(1 for v in nr if abs(vlen(v) - 1) > 0.02)
        T.add('vertex normals unit', bad == 0, (model, n.name, bad))
    for key in ('uv0', 'uv1'):
        uv = M['mdx'].get(key)
        if uv:
            lo = min(min(u) for u in uv)
            hi = max(max(u) for u in uv)
            T.add(f'{key} range bucket', ('in [0,1]' if lo >= -1e-3 and hi <= 1.001 else 'outside [0,1]'), (model, n.name, lo, hi))
    col = M['mdx'].get('color')
    if col:
        lo = min(min(c) for c in col)
        hi = max(max(c) for c in col)
        T.add('vertex color range', 'in [0,1]' if lo >= 0 and hi <= 1 else 'outside', (model, n.name, lo, hi))
    tan = M['mdx'].get('tangent0')
    if tan:
        # three vectors: check they are unit and what handedness relates them to the normal
        bad = 0
        rel = collections.Counter()
        for i, t9 in enumerate(tan):
            a, b, c = t9[0:3], t9[3:6], t9[6:9]
            if any(abs(vlen(v) - 1) > 0.05 for v in (a, b, c)):
                bad += 1
            if nr:
                nn = nr[i]
                rel[tuple(round(dot(v, nn), 1) for v in (a, b, c))] += 1
        T.add('tangent vectors unit', bad == 0, (model, n.name, bad))
        for k, v in rel.most_common(3):
            T.add('tangent triplet . vertex normal (a, b, c)', k, (model, n.name), v)


def check_skin(model, n, m):
    S = n.skin
    M = n.mesh
    T.add('skin weights array (unused)', S['weights_array'], model)
    T.add('skin tail u16[2]', S['tail'], model)
    T.add('skin arrays counts == node count', (len(S['qbones']) == len(m.names), len(S['tbones']) == len(m.names),
                                               S['const_array'][1] == len(m.names), S['bonemap_n'] == len(m.names)),
          (model, n.name, len(S['qbones']), len(m.names), S['bonemap_n']))
    used = sorted({int(b) for b in S['bonemap'] if b >= 0})
    T.add('skin bonemap distinct slots', 'contiguous from 0' if used == list(range(len(used))) else 'gappy', model)
    # bone_nodes: the node numbers of the slots in order
    slots = {}
    for node_idx, b in enumerate(S['bonemap']):
        if b >= 0:
            slots[int(b)] = node_idx
    bn = [v for v in S['bone_nodes']]
    k = min(16, len(used))
    first = [slots.get(i, -1) for i in range(k)]
    T.add('skin bone_nodes[:slots] == bonemap index of slot', bn[:k] == first, (model, n.name, bn[:6], first[:6]))
    T.add('skin bone_nodes beyond slots', tuple(sorted(set(bn[k:]))), model)
    T.add('skin bone slot count', len(used) if len(used) <= 16 else '>16', model)
    if S['weights'] and S['bones']:
        bad_sum = bad_idx = 0
        for w, b in zip(S['weights'], S['bones']):
            if abs(sum(w) - 1) > 0.01:
                bad_sum += 1
            for wi, bi in zip(w, b):
                if wi > 0 and not (0 <= bi < len(used) and float(bi).is_integer()):
                    bad_idx += 1
                if wi == 0:
                    T.add('skin unused influence bone value', bi)
        if bad_sum:
            fail('skin-weights-not-1', model, f'{n.name}: {bad_sum}')
        if bad_idx:
            fail('skin-bone-index-bad', model, f'{n.name}: {bad_idx}')
    # qbone/tbone: inverse bind transforms. Check the bound pose: tbone + rotate(qbone, world pos of node) ~ 0
    T.add('skin qbone unit', all(abs(vlen(q) - 1) < 0.01 for q in S['qbones']), model)


def world_transforms(nodes):
    """name -> (rotation quaternion wxyz, translation) in model space from header pos/orient."""
    out = {}

    def qmul(a, b):
        aw, ax, ay, az = a
        bw, bx, by, bz = b
        return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)

    def qrot(q, v):
        p = (0.0,) + tuple(v)
        c = (q[0], -q[1], -q[2], -q[3])
        r = qmul(qmul(q, p), c)
        return r[1:]

    def walk(n, q, t):
        lq = n.orientation
        lt = n.position
        wq = qmul(q, lq)
        wt = tuple(a + b for a, b in zip(t, qrot(q, lt)))
        out[n.name_index] = (wq, wt)
        for c in n.children:
            walk(c, wq, wt)

    walk(nodes[0], (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return out, qmul, qrot


def check_skin_bind(model, n, m):
    """qbones/tbones invert each bone's bind transform relative to the skin mesh. The bonemap,
    qbones and tbones are indexed by the node's depth-first position (m.nodes order); this
    checks that against the name-index alternative."""
    S = n.skin
    if not S['qbones']:
        return
    root = next(x for x in m.nodes if x.parent is None)
    W, qmul, qrot = world_transforms([root])
    mesh_q, mesh_t = W[n.name_index]
    mq_inv = (mesh_q[0], -mesh_q[1], -mesh_q[2], -mesh_q[3])

    def ok(node_name_index, k):
        bq, bt = W[node_name_index]
        rel_q = qmul(mq_inv, bq)
        rel_t = qrot(mq_inv, tuple(a - c for a, c in zip(bt, mesh_t)))
        q = S['qbones'][k]
        t = S['tbones'][k]
        comb_q = qmul(q, rel_q)
        comb_t = tuple(a + b for a, b in zip(qrot(q, rel_t), t))
        return abs(abs(comb_q[0]) - 1) < 1e-2 and vlen(comb_t) < 1e-2

    bad_dfs = bad_name = 0
    for k, b in enumerate(S['bonemap']):
        if b < 0:
            continue
        if not ok(m.nodes[k].name_index, k):
            bad_dfs += 1
        if k >= len(m.nodes) or not ok(k, k):
            bad_name += 1
    T.add('skin inverse bind with depth-first indexing', 'all bones ok' if bad_dfs == 0 else 'some bad',
          (model, n.name, bad_dfs))
    T.add('skin inverse bind with name-index indexing', 'all bones ok' if bad_name == 0 else 'some bad',
          (model, n.name, bad_name))
    if bad_dfs:
        fail('skin-inverse-bind', model, f'{n.name}: {bad_dfs} bones')
    T.add('depth-first order == name order', [x.name_index for x in m.nodes] == list(range(len(m.nodes))), model)


def check_anim_positions(model, m):
    """Animation position keys: offsets from the geometry position, or absolute positions?"""
    bind = {x.name.lower(): x.position for x in m.nodes}
    absn = deln = 0
    for a in m.anims:
        for x in a.nodes:
            b = bind.get(x.name.lower())
            if b is None or vlen(b) < 0.02:
                continue
            for c in x.controllers:
                if c.type == 8 and c.values:
                    v = c.values[0][:3]
                    if vlen(sub(v, b)) < 1e-3:
                        absn += 1
                    elif vlen(v) < 1e-3:
                        deln += 1
    if absn or deln:
        T.add('animation position keys look like', 'offsets' if deln and not absn else (
            'absolute' if absn and not deln else 'mixed'), (model, absn, deln))


def check_dangly(model, n):
    Dg = n.dangly
    nv = n.mesh['vertex_count']
    if len(Dg['constraints']) != nv:
        fail('dangly-constraints-count', model, f'{n.name} {len(Dg["constraints"])} vs {nv}')
    if Dg['constraints']:
        T.add('dangly constraint range', (min(Dg['constraints']) >= 0, max(Dg['constraints']) <= 255), model)
    T.add('dangly params (displacement, tightness, period)',
          tuple(round(v, 3) for v in (Dg['displacement'], Dg['tightness'], Dg['period'])), model)
    if Dg['vertices'] and n.mesh['mdl_vertices']:
        same = all(all(near(a, b, 1e-5) for a, b in zip(u, v)) for u, v in zip(Dg['vertices'], n.mesh['mdl_vertices']))
        T.add('dangly vertices == mesh vertices', same, (model, n.name))
    else:
        T.add('dangly vertex array present', bool(Dg['vertices']), model)


def check_aabb(model, n):
    A = n.aabb
    faces = n.mesh['faces']
    leaves = []
    bad_contain = 0

    def walk(e, parent):
        nonlocal bad_contain
        if parent is not None:
            for k in range(3):
                if e['bmin'][k] < parent['bmin'][k] - 1e-3 or e['bmax'][k] > parent['bmax'][k] + 1e-3:
                    bad_contain += 1
                    break
        if e['face'] >= 0:
            leaves.append(e['face'])
            if e['kids']:
                fail('aabb-leaf-with-children', model, n.name)
            T.add('aabb leaf plane value', e['plane'], model)
        else:
            T.add('aabb internal: children', len(e['kids']), model)
            T.add('aabb internal plane value', e['plane'], model)
        for k in e['kids']:
            walk(k, e)

    if A['tree']:
        walk(A['tree'], None)
    if sorted(leaves) != list(range(len(faces))):
        fail('aabb-leaves-not-each-face-once', model, f'{n.name}: {len(leaves)} leaves, {len(faces)} faces')
    if bad_contain:
        fail('aabb-child-outside-parent', model, f'{n.name}: {bad_contain}')
    vs = n.mesh['mdl_vertices'] or []
    badleaf = 0
    for e in A['nodes']:
        if e['face'] >= 0 and vs and e['face'] < len(faces):
            for v in faces[e['face']][4]:
                p = vs[v]
                if any(p[k] < e['bmin'][k] - 1e-3 or p[k] > e['bmax'][k] + 1e-3 for k in range(3)):
                    badleaf += 1
                    break
    if badleaf:
        fail('aabb-leaf-box-misses-face', model, f'{n.name}: {badleaf}')
    # internal-node plane: compare with the axis of greatest extent
    for e in A['nodes']:
        if e['face'] < 0:
            ext = [e['bmax'][k] - e['bmin'][k] for k in range(3)]
            T.add('aabb internal plane vs longest axis', (e['plane'], 'xyz'[ext.index(max(ext))]))


def check_emitter(model, n):
    E = n.emitter
    for k in ('update', 'render', 'blend', 'spawn_type', 'xgrid', 'ygrid', 'twosided', 'loop',
              'render_order', 'frame_blending', 'depth_texture', 'chunk', 'branch_count', 'pad219'):
        T.add(f'emitter {k}', E[k], model)
    T.add('emitter texture', E['texture'].lower(), model)
    for bit in range(32):
        if E['flags'] & (1 << bit):
            T.add('emitter flag bits', 1 << bit, model)
    T.add('emitter (deadspace, blastradius, blastlength, cp smoothing)',
          tuple(round(v, 2) for v in (E['deadspace'], E['blast_radius'], E['blast_length'], E['control_point_smoothing'])), model)


def check_light(model, n):
    L = n.light
    for k in ('priority', 'ambient_only', 'dynamic_type', 'affect_dynamic', 'shadow', 'flare', 'fading'):
        T.add(f'light {k}', L[k], model)
    T.add('light flare counts (sizes, positions, colorshifts, textures)', L['counts'], model)
    T.add('light unknown array', L['unknown_array'][1:], model)
    T.add('light flare radius', round(L['flare_radius'], 2), model)
    for t in L['flare_textures']:
        T.add('light flare texture', t.lower(), model)
    if L['flare'] and not L['counts'][3]:
        T.add('light flare flag but no textures', 1, model)


def check_saber(model, n):
    S = n.saber
    M = n.mesh
    T.add('saber vertex count', M['vertex_count'], model)
    T.add('saber (inv1, inv2)', (S['inv1'], S['inv2']), model)
    T.add('saber mesh faces', len(M['faces']), model)
    T.add('saber mdx flags/stride', (hex(M['mdx_flags']), M['mdx_stride']), model)
    T.add('saber texture0', M['texture0'].lower(), model)


def main(argv):
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else None
    outp = argv[argv.index('--out') + 1] if '--out' in argv else None
    out = open(outp, 'w', encoding='utf-8') if outp else sys.stdout
    g = kres.Game()
    textures = {}
    for e in g.entries():
        if e.ext in ('tpc', 'tga'):
            textures.setdefault(e.resref, set()).add(e.ext)
    patch = os.path.join(g.dir, 'patch.erf')
    if os.path.exists(patch):
        for e in kres.read_container(patch):
            if e.ext in ('tpc', 'tga'):
                textures.setdefault(e.resref, set()).add(e.ext)
    textures = {k: '+'.join(sorted(v)) for k, v in textures.items()}
    all_models = set(e.resref for e in g.entries('mdl'))
    files = 0
    nodes = 0
    ctrls = 0
    anims = 0
    for i, (e, data, mdx) in enumerate(kmdl.corpus(g)):
        if limit and i >= limit:
            break
        files += 1
        name = f'{e.resref} ({os.path.basename(e.container)})'
        try:
            m = kmdl.parse(data, mdx, e.resref)
        except kmdl.Bad as err:
            fail('parse-error', name, str(err))
            continue
        for k, d in m.problems:
            fail('parser:' + k, name, d)
        check_coverage(name, data, m)
        check_mdx_coverage(name, m, mdx)
        T.add('geometry fn pointers (model)', m.geometry['fn'], name)
        T.add('geometry runtime arrays/refcount', (m.geometry['rt1'], m.geometry['rt2'], m.geometry['refcount']), name)
        T.add('geometry name == resref', m.name.lower() == e.resref, (name, m.name))
        T.add('classification', m.classification, e.resref)
        T.add('subclassification', m.subclassification, e.resref)
        T.add('model byte 82', m.unknown83, e.resref)
        T.add('affected by fog', m.fog, e.resref)
        T.add('child model count', m.child_model_count, e.resref)
        T.add('supermodel ptr', m.supermodel_ptr, e.resref)
        T.add('model u32 at 172', m.unknown172, e.resref)
        T.add('mdx offset field at 180', m.mdx_offset, e.resref)
        T.add('animation scale', round(m.anim_scale, 3), e.resref)
        T.add('model bbox/radius', (m.bmin, m.bmax, round(m.radius, 2)) if m.radius == 7.0 else 'non-default', e.resref)
        sm = m.supermodel.lower()
        if sm in ('', 'null'):
            T.add('supermodel', 'NULL' if sm == 'null' else 'empty', e.resref)
        else:
            T.add('supermodel', 'exists' if sm in all_models else 'missing', (e.resref, sm))
            T.add('supermodel names', sm, e.resref)
        # node counts: own nodes, plus the supermodel's node_count + 1 when there is one
        expect = len(m.nodes)
        if sm not in ('', 'null'):
            sd = g.get(sm, 'mdl')
            if sd:
                import struct
                expect += struct.unpack_from('<I', sd, 12 + 44)[0] + 1
        T.add('geometry node_count == nodes (+ supermodel node_count + 1)', m.geometry['node_count'] == expect,
              (e.resref, m.geometry['node_count'], expect))
        T.add('names count vs nodes', 'equal' if len(m.names) == len(m.nodes) else
              ('more names' if len(m.names) > len(m.nodes) else 'fewer names'), (e.resref, len(m.names), len(m.nodes)))
        used = collections.Counter(n.name_index for n in m.nodes)
        if any(v > 1 for v in used.values()):
            fail('name-index-shared', name, '')
        T.add('node part == name index', all(n.part == n.name_index for n in m.nodes),
              (e.resref, [(n.name, n.part, n.name_index) for n in m.nodes if n.part != n.name_index][:3]))
        T.add('node name index == tree order', [n.name_index for n in m.nodes] == sorted(n.name_index for n in m.nodes), e.resref)
        root = next(n for n in m.nodes if n.parent is None)
        T.add('root node name == model name', root.name.lower() == m.name.lower(), (e.resref, root.name))
        T.add('root node kind', root.kind, e.resref)
        head = {n.offset: n for n in m.nodes}.get(m.root_again)
        T.add('model +168 node', (head.name if head else None) if m.root_again != m.geometry['root'] else 'root', e.resref)
        for n in m.nodes:
            nodes += 1
            ctrls += len(n.controllers)
            T.add('node kinds', n.kind, e.resref)
            T.add('node pad6', n.pad6, e.resref)
            T.add('node geom ptr', n.geom_ptr, e.resref)
            T.add('node controller ids by kind', (n.kind, tuple(sorted(c.type for c in n.controllers))), e.resref)
            check_controllers(name, n, None, m.names)
            if n.mesh:
                check_mesh(name, n, textures)
            if n.skin:
                check_skin(name, n, m)
                check_skin_bind(name, n, m)
            if n.dangly:
                check_dangly(name, n)
            if n.aabb:
                check_aabb(name, n)
            if n.emitter:
                check_emitter(name, n)
            if n.light:
                check_light(name, n)
            if n.saber:
                check_saber(name, n)
            if n.reference:
                r = n.reference['model'].lower()
                T.add('reference model', 'exists' if r in all_models else 'missing', (e.resref, r))
                T.add('reference reattachable', n.reference['reattachable'], e.resref)
                T.add('reference model names', r, e.resref)
            if n.name.lower().endswith('hook') or n.name.lower() in ('headhook', 'rhand', 'lhand', 'impact', 'head', 'gogglehook', 'maskhook'):
                T.add('hook-like node names', (n.name.lower(), m.classification), e.resref)
        check_anim_positions(name, m)
        names_set = {nm.lower() for nm in m.names}
        T.add('animations per model', len(m.anims) if len(m.anims) < 5 else '5+', e.resref)
        for a in m.anims:
            anims += 1
            T.add('animation fn pointers', a.geometry['fn'], e.resref)
            T.add('animation names', a.name.lower(), e.resref)
            T.add('anim unknown132', a.unknown132, e.resref)
            T.add('anim node_count == walked nodes', a.geometry['node_count'] == len(a.nodes), (e.resref, a.name, a.geometry['node_count'], len(a.nodes)))
            T.add('anim root name', 'model name' if a.root_name.lower() == m.name.lower() else a.root_name.lower(), e.resref)
            T.add('anim first node name', 'model name' if a.root.name.lower() == m.name.lower() else a.root.name.lower(), e.resref)
            T.add('anim transition time', round(a.transition, 3), e.resref)
            for t, ev in a.events:
                T.add('anim event names', ev.lower(), (e.resref, a.name))
                if t < -1e-4 or t > a.length + 1e-3:
                    fail('event-outside-length', name, f'{a.name} {ev} {t} > {a.length}')
            for n in a.nodes:
                ctrls += len(n.controllers)
                T.add('anim node kinds', n.kind, (e.resref, a.name, n.name))
                T.add('anim node part == name index', n.part == n.name_index, e.resref)
                if n.name.lower() not in names_set:
                    fail('anim-node-name-not-in-model', name, f'{a.name}/{n.name}')
                check_controllers(name, n, a, m.names)
    print(f'# mdlprobe: {files} models, {nodes} geometry nodes, {anims} animations, {ctrls} controllers', file=out)
    FAIL.dump(out, 'failures', top=200)
    for table in sorted(T.c):
        T.dump(out, table, top=150 if table.startswith('controllers (') else 60)
    if outp:
        out.close()
        print(f'{files} models; report in {outp}')
        c = FAIL.c.get('failures', {})
        print('failures:', dict(c) if c else 'none')


if __name__ == '__main__':
    main(sys.argv[1:])
