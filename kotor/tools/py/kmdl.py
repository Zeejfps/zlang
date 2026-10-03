"""Parse KOTOR 1 binary MDL/MDX models (exploration and probes only; not used by the game).

    import kmdl
    m = kmdl.parse(mdl_bytes, mdx_bytes)     # raises kmdl.Bad on malformed data
    m.nodes                                  # every node of the main geometry, tree order
    m.anims                                  # Animation objects, each with its own node tree
    m.problems                               # soft findings (data that parses but looks odd)

The layout is described in kotor/docs/formats/mdl.md. All offsets inside the MDL are relative to
the model data, which starts after the 12-byte file header; MDX offsets are relative to the MDX
file's start.
"""

import math
import struct

# Node type flags (the u16 at node offset 0).
NODE_HEADER = 0x0001
NODE_LIGHT = 0x0002
NODE_EMITTER = 0x0004
NODE_CAMERA = 0x0008
NODE_REFERENCE = 0x0010
NODE_MESH = 0x0020
NODE_SKIN = 0x0040
NODE_ANIM = 0x0080
NODE_DANGLY = 0x0100
NODE_AABB = 0x0200
NODE_SABER = 0x0800

NODE_KINDS = {
    0x0001: 'dummy', 0x0003: 'light', 0x0005: 'emitter', 0x0009: 'camera', 0x0011: 'reference',
    0x0021: 'trimesh', 0x0061: 'skin', 0x00A1: 'animmesh', 0x0121: 'dangly', 0x0221: 'aabb',
    0x0821: 'saber',
}

# MDX attribute bits (mesh header +256) and the mesh-header slot holding each attribute's offset.
MDX_POSITION = 0x0001
MDX_UV0 = 0x0002
MDX_UV1 = 0x0004
MDX_UV2 = 0x0008
MDX_UV3 = 0x0010
MDX_NORMAL = 0x0020
MDX_COLOR = 0x0040
MDX_TANGENT0 = 0x0080
MDX_TANGENT1 = 0x0100
MDX_TANGENT2 = 0x0200
MDX_TANGENT3 = 0x0400

# (bit, slot index in the 11 offsets at mesh+260, component count)
MDX_ATTRS = [
    (MDX_POSITION, 0, 3, 'position'), (MDX_NORMAL, 1, 3, 'normal'), (MDX_COLOR, 2, 3, 'color'),
    (MDX_UV0, 3, 2, 'uv0'), (MDX_UV1, 4, 2, 'uv1'), (MDX_UV2, 5, 2, 'uv2'), (MDX_UV3, 6, 2, 'uv3'),
    (MDX_TANGENT0, 7, 9, 'tangent0'), (MDX_TANGENT1, 8, 9, 'tangent1'),
    (MDX_TANGENT2, 9, 9, 'tangent2'), (MDX_TANGENT3, 10, 9, 'tangent3'),
]

# Emitter flag bits (emitter header +220), named after the ASCII model keywords.
EMITTER_FLAGS = {
    0x0001: 'p2p', 0x0002: 'p2p_sel', 0x0004: 'affectedByWind', 0x0008: 'm_isTinted',
    0x0010: 'bounce', 0x0020: 'random', 0x0040: 'inherit', 0x0080: 'inheritvel',
    0x0100: 'inherit_local', 0x0200: 'splat', 0x0400: 'inherit_part', 0x0800: 'depth_texture',
    0x1000: 'random2',
}

# Controller ids by the node kind that owns them (names are the ASCII model keywords).
CTRL_COMMON = {8: 'position', 20: 'orientation', 36: 'scale'}
CTRL_MESH = {100: 'selfillumcolor', 132: 'alpha'}
CTRL_LIGHT = {76: 'color', 88: 'radius', 96: 'shadowradius', 100: 'verticaldisplacement',
              140: 'multiplier'}
CTRL_EMITTER = {
    80: 'alphaEnd', 84: 'alphaStart', 88: 'birthrate', 92: 'bounce_co', 96: 'combinetime',
    100: 'drag', 104: 'fps', 108: 'frameEnd', 112: 'frameStart', 116: 'grav', 120: 'lifeExp',
    124: 'mass', 128: 'p2p_bezier2', 132: 'p2p_bezier3', 136: 'particleRot', 140: 'randvel',
    144: 'sizeStart', 148: 'sizeEnd', 152: 'sizeStart_y', 156: 'sizeEnd_y', 160: 'spread',
    164: 'threshold', 168: 'velocity', 172: 'xsize', 176: 'ysize', 180: 'blurlength',
    184: 'lightningDelay', 188: 'lightningRadius', 192: 'lightningScale', 196: 'lightningSubDiv',
    200: 'lightningZigzag', 216: 'alphaMid', 220: 'percentStart', 224: 'percentMid',
    228: 'percentEnd', 232: 'sizeMid', 236: 'sizeMid_y', 240: 'm_fRandomBirthRate',
    252: 'targetsize', 256: 'numcontrolpts', 260: 'controlptradius', 264: 'controlptdelay',
    268: 'tangentspread', 272: 'tangentlength', 284: 'colorMid', 380: 'colorEnd',
    392: 'colorStart', 502: 'detonate',
}


def controller_names(flags):
    """The controller id -> name table for a node with these flags."""
    t = dict(CTRL_COMMON)
    if flags & NODE_MESH:
        t.update(CTRL_MESH)
    if flags & NODE_LIGHT:
        t.update(CTRL_LIGHT)
    if flags & NODE_EMITTER:
        t.update(CTRL_EMITTER)
    return t


class Bad(Exception):
    """The file cannot be parsed."""


class Reader:
    def __init__(self, data, base=0, what='mdl'):
        self.d = data
        self.base = base
        self.what = what

    def need(self, off, size, why):
        if off < 0 or size < 0 or self.base + off + size > len(self.d):
            raise Bad(f'{why}: {self.what} range {off}+{size} outside {len(self.d) - self.base}')

    def u8(self, off):
        self.need(off, 1, 'u8')
        return self.d[self.base + off]

    def u16(self, off):
        self.need(off, 2, 'u16')
        return struct.unpack_from('<H', self.d, self.base + off)[0]

    def i16(self, off):
        self.need(off, 2, 'i16')
        return struct.unpack_from('<h', self.d, self.base + off)[0]

    def u32(self, off):
        self.need(off, 4, 'u32')
        return struct.unpack_from('<I', self.d, self.base + off)[0]

    def i32(self, off):
        self.need(off, 4, 'i32')
        return struct.unpack_from('<i', self.d, self.base + off)[0]

    def f32(self, off):
        self.need(off, 4, 'f32')
        return struct.unpack_from('<f', self.d, self.base + off)[0]

    def fmt(self, fmt, off):
        n = struct.calcsize(fmt)
        self.need(off, n, fmt)
        return struct.unpack_from(fmt, self.d, self.base + off)

    def raw(self, off, n):
        self.need(off, n, 'raw')
        return self.d[self.base + off:self.base + off + n]

    def cstr(self, off, n):
        b = self.raw(off, n)
        return b.split(b'\0', 1)[0].decode('latin-1')

    def zstr(self, off, limit=256):
        self.need(off, 1, 'zstr')
        s = self.base + off
        e = self.d.find(b'\0', s, s + limit)
        if e < 0:
            raise Bad(f'unterminated string at {off}')
        return self.d[s:e].decode('latin-1')

    def array(self, off):
        """An (offset, used, allocated) triple."""
        return self.fmt('<3I', off)


class Controller:
    __slots__ = ('type', 'unknown', 'rows', 'time_index', 'data_index', 'columns', 'pad',
                 'bezier', 'compressed', 'times', 'values', 'name')

    def __repr__(self):
        return f'<ctrl {self.name or self.type} rows={self.rows} cols={self.columns:#x}>'


class Node:
    def __init__(self):
        self.children = []
        self.controllers = []
        self.mesh = None
        self.skin = None
        self.dangly = None
        self.aabb = None
        self.anim = None
        self.saber = None
        self.light = None
        self.emitter = None
        self.reference = None
        self.camera = None

    def __repr__(self):
        return f'<node {self.name} {self.kind}>'


class Animation:
    pass


class Model:
    pass


def decompress_quaternion(v):
    """KOTOR's 32-bit packed orientation: 11 bits x, 11 bits y, 10 bits z; w recovered."""
    x = (v & 0x7FF) / 1023.0 - 1.0
    y = ((v >> 11) & 0x7FF) / 1023.0 - 1.0
    z = (v >> 22) / 511.0 - 1.0
    m = x * x + y * y + z * z
    if m < 1.0:
        w = math.sqrt(1.0 - m)
    else:
        n = math.sqrt(m)
        x, y, z, w = x / n, y / n, z / n, 0.0
    return (x, y, z, w)


class Parser:
    def __init__(self, mdl, mdx, name=''):
        if len(mdl) < 12:
            raise Bad('shorter than the file header')
        self.file = mdl
        self.r = Reader(mdl, 12, 'mdl')
        self.x = Reader(mdx or b'', 0, 'mdx')
        self.name = name
        self.problems = []
        self.claims = []  # (offset, size, what): MDL bytes each structure accounts for

    def claim(self, off, size, what):
        if size:
            self.claims.append((off, size, what))

    def warn(self, kind, detail=''):
        self.problems.append((kind, detail))

    # -- headers ----------------------------------------------------------------------------

    def parse(self):
        r = self.r
        m = Model()
        m.zero, m.mdl_size, m.mdx_size = struct.unpack_from('<3I', self.file, 0)
        if m.zero != 0:
            raise Bad(f'file header first word {m.zero:#x}, not 0 (ASCII model?)')
        if m.mdl_size + 12 != len(self.file):
            self.warn('mdl-size', f'header says {m.mdl_size}, file has {len(self.file) - 12}')
        if m.mdx_size != len(self.x.d):
            self.warn('mdx-size', f'header says {m.mdx_size}, mdx has {len(self.x.d)}')
        m.geometry = self.geometry_header(0)
        if m.geometry['type'] != 2:
            self.warn('geom-type', str(m.geometry['type']))
        m.name = m.geometry['name']
        m.classification, m.subclassification, m.unknown83, m.fog = r.fmt('<4B', 80)
        m.child_model_count = r.u32(84)
        anim_off, anim_n, anim_alloc = r.array(88)
        if anim_n != anim_alloc:
            self.warn('array-alloc', 'animations')
        m.supermodel_ptr = r.u32(100)
        m.bmin = r.fmt('<3f', 104)
        m.bmax = r.fmt('<3f', 116)
        m.radius = r.f32(128)
        m.anim_scale = r.f32(132)
        m.supermodel = r.cstr(136, 32)
        m.root_again = r.u32(168)
        m.unknown172 = r.u32(172)
        m.mdx_size2 = r.u32(176)
        m.mdx_offset = r.u32(180)
        names_off, names_n, names_alloc = r.array(184)
        if m.mdx_size2 != m.mdx_size:
            self.warn('mdx-size-dup', f'{m.mdx_size2} vs {m.mdx_size}')
        m.names = [r.zstr(r.u32(names_off + 4 * i)) for i in range(names_n)]
        self.claim(0, 196, 'model header')
        self.claim(names_off, 4 * names_n, 'name offsets')
        for i in range(names_n):
            self.claim(r.u32(names_off + 4 * i), len(m.names[i]) + 1, 'name')
        self.claim(anim_off, 4 * anim_n, 'animation offsets')
        m.names_off = names_off
        self.names = m.names
        self.seen = set()
        m.nodes = []
        m.root = self.node(m.geometry['root'], None, m.nodes, 0)
        m.anims = []
        for i in range(anim_n):
            m.anims.append(self.animation(r.u32(anim_off + 4 * i)))
        # Animation nodes are plain dummies (flags 1): their controller ids mean what they mean
        # for the model node of the same name, so name them from that node's flags.
        flags_by_name = {n.name.lower(): n.flags for n in m.nodes}
        for a in m.anims:
            for n in a.nodes:
                table = controller_names(flags_by_name.get(n.name.lower(), n.flags))
                for c in n.controllers:
                    c.name = table.get(c.type)
        m.problems = self.problems
        m.claims = self.claims
        return m

    def geometry_header(self, off):
        r = self.r
        g = {}
        g['fn'] = r.fmt('<2I', off)
        g['name'] = r.cstr(off + 8, 32)
        g['root'] = r.u32(off + 40)
        g['node_count'] = r.u32(off + 44)
        g['rt1'] = r.array(off + 48)
        g['rt2'] = r.array(off + 60)
        g['refcount'] = r.u32(off + 72)
        g['type'] = r.u8(off + 76)
        g['pad'] = r.raw(off + 77, 3)
        return g

    def animation(self, off):
        r = self.r
        a = Animation()
        a.offset = off
        a.geometry = self.geometry_header(off)
        a.name = a.geometry['name']
        if a.geometry['type'] != 5:
            self.warn('anim-geom-type', f'{a.name}: {a.geometry["type"]}')
        a.length = r.f32(off + 80)
        a.transition = r.f32(off + 84)
        a.root_name = r.cstr(off + 88, 32)
        ev_off, ev_n, ev_alloc = r.array(off + 120)
        a.unknown132 = r.u32(off + 132)
        self.claim(off, 136, 'animation header')
        self.claim(ev_off, 36 * ev_n, 'events')
        a.events = []
        for i in range(ev_n):
            t = r.f32(ev_off + 36 * i)
            a.events.append((t, r.cstr(ev_off + 36 * i + 4, 32)))
        a.nodes = []
        a.root = self.node(a.geometry['root'], None, a.nodes, 0, anim=a)
        return a

    # -- nodes ------------------------------------------------------------------------------

    def node(self, off, parent, out, depth, anim=None):
        r = self.r
        if off in self.seen:
            raise Bad(f'node at {off} reached twice (cycle or shared child)')
        if depth > 200:
            raise Bad('node tree deeper than 200')
        self.seen.add(off)
        n = Node()
        n.offset = off
        n.flags, n.part, n.name_index, n.pad6 = r.fmt('<4H', off)
        n.kind = NODE_KINDS.get(n.flags, f'flags{n.flags:#x}')
        if n.flags not in NODE_KINDS:
            self.warn('node-flags', f'{n.flags:#x}')
        if n.name_index >= len(self.names):
            raise Bad(f'node name index {n.name_index} >= {len(self.names)}')
        n.name = self.names[n.name_index]
        n.geom_ptr, n.parent_ptr = r.fmt('<2I', off + 8)
        n.position = r.fmt('<3f', off + 16)
        n.orientation = r.fmt('<4f', off + 28)  # w, x, y, z
        n.parent = parent
        n.anim_owner = anim
        expect_parent = parent.offset if parent else 0
        if n.parent_ptr != expect_parent:
            self.warn('parent-ptr', f'{n.name}: {n.parent_ptr} vs {expect_parent}')
        ch_off, ch_n, ch_alloc = r.array(off + 44)
        ct_off, ct_n, ct_alloc = r.array(off + 56)
        cd_off, cd_n, cd_alloc = r.array(off + 68)
        if (ch_n, ct_n, cd_n) != (ch_alloc, ct_alloc, cd_alloc):
            self.warn('array-alloc', f'node {n.name}')
        r.need(cd_off, 4 * cd_n, 'controller data')
        self.claim(ch_off, 4 * ch_n, 'children')
        self.claim(ct_off, 16 * ct_n, 'controllers')
        self.claim(cd_off, 4 * cd_n, 'controller data')
        data = r.fmt(f'<{cd_n}f', cd_off) if cd_n else ()
        raw = r.fmt(f'<{cd_n}I', cd_off) if cd_n else ()
        names = controller_names(n.flags)
        for i in range(ct_n):
            c = Controller()
            o = ct_off + 16 * i
            c.type, c.unknown, c.rows, c.time_index, c.data_index, c.columns = r.fmt('<IHHHHB', o)
            c.pad = r.raw(o + 13, 3)
            c.name = names.get(c.type)
            c.bezier = bool(c.columns & 0x10)
            cols = c.columns & 0x0F
            c.compressed = c.type == 20 and cols == 2
            per_row = 1 if c.compressed else (cols * 3 if c.bezier else cols)
            if c.time_index + c.rows > cd_n or c.data_index + c.rows * per_row > cd_n:
                raise Bad(f'{n.name}: controller {c.type} rows {c.rows} beyond data {cd_n}')
            c.times = data[c.time_index:c.time_index + c.rows]
            if c.compressed:
                c.values = [decompress_quaternion(raw[c.data_index + k]) for k in range(c.rows)]
            else:
                c.values = [data[c.data_index + k * per_row:c.data_index + (k + 1) * per_row]
                            for k in range(c.rows)]
            n.controllers.append(c)
        n.controller_data_count = cd_n
        p = off + 80
        if n.flags & NODE_LIGHT:
            n.light = self.light(p)
            p += 92
        if n.flags & NODE_EMITTER:
            n.emitter = self.emitter(p)
            p += 224
        if n.flags & NODE_CAMERA:
            n.camera = {}
        if n.flags & NODE_REFERENCE:
            n.reference = {'model': r.cstr(p, 32), 'reattachable': r.u32(p + 32)}
            p += 36
        if n.flags & NODE_MESH:
            if anim is None:
                n.mesh = self.mesh(p, n)
            else:
                n.mesh = self.mesh(p, n, anim=True)
            p += 332
        if n.flags & NODE_SKIN:
            n.skin = self.skin(p, n)
            p += 100
        if n.flags & NODE_ANIM:
            n.anim = self.animmesh(p, n)
            p += 56
        if n.flags & NODE_DANGLY:
            n.dangly = self.dangly(p, n)
            p += 28
        if n.flags & NODE_AABB:
            n.aabb = self.aabb(p, n)
            p += 4
        if n.flags & NODE_SABER:
            n.saber = self.saber(p, n)
            p += 20
        n.end = p
        self.claim(off, p - off, 'node ' + n.kind)
        out.append(n)
        for i in range(ch_n):
            n.children.append(self.node(r.u32(ch_off + 4 * i), n, out, depth + 1, anim))
        return n

    def light(self, p):
        r = self.r
        L = {}
        L['flare_radius'] = r.f32(p)
        L['unknown_array'] = r.array(p + 4)
        sz = r.array(p + 16)
        pos = r.array(p + 28)
        cs = r.array(p + 40)
        tx = r.array(p + 52)
        L['priority'], L['ambient_only'], L['dynamic_type'], L['affect_dynamic'], L['shadow'], \
            L['flare'], L['fading'] = r.fmt('<7I', p + 64)
        L['flare_sizes'] = list(r.fmt(f'<{sz[1]}f', sz[0])) if sz[1] else []
        L['flare_positions'] = list(r.fmt(f'<{pos[1]}f', pos[0])) if pos[1] else []
        L['flare_colorshifts'] = [r.fmt('<3f', cs[0] + 12 * i) for i in range(cs[1])]
        L['flare_textures'] = [r.zstr(r.u32(tx[0] + 4 * i)) for i in range(tx[1])]
        self.claim(sz[0], 4 * sz[1], 'flare sizes')
        self.claim(pos[0], 4 * pos[1], 'flare positions')
        self.claim(cs[0], 12 * cs[1], 'flare colorshifts')
        self.claim(tx[0], 4 * tx[1], 'flare texture ptrs')
        for i in range(tx[1]):
            self.claim(r.u32(tx[0] + 4 * i), len(L['flare_textures'][i]) + 1, 'flare texture name')
        L['counts'] = (sz[1], pos[1], cs[1], tx[1])
        return L

    def emitter(self, p):
        r = self.r
        E = {}
        E['deadspace'], E['blast_radius'], E['blast_length'] = r.fmt('<3f', p)
        E['branch_count'] = r.u32(p + 12)
        E['control_point_smoothing'] = r.f32(p + 16)
        E['xgrid'], E['ygrid'], E['spawn_type'] = r.fmt('<3I', p + 20)
        E['update'] = r.cstr(p + 32, 32)
        E['render'] = r.cstr(p + 64, 32)
        E['blend'] = r.cstr(p + 96, 32)
        E['texture'] = r.cstr(p + 128, 32)
        E['chunk'] = r.cstr(p + 160, 16)
        E['twosided'], E['loop'] = r.fmt('<2I', p + 176)
        E['render_order'] = r.u16(p + 184)
        E['frame_blending'] = r.u8(p + 186)
        E['depth_texture'] = r.cstr(p + 187, 32)
        E['pad219'] = r.u8(p + 219)
        E['flags'] = r.u32(p + 220)
        return E

    def mesh(self, p, n, anim=False):
        r = self.r
        M = {}
        M['fn'] = r.fmt('<2I', p)
        f_off, f_n, f_alloc = r.array(p + 8)
        M['bmin'] = r.fmt('<3f', p + 20)
        M['bmax'] = r.fmt('<3f', p + 32)
        M['radius'] = r.f32(p + 44)
        M['average'] = r.fmt('<3f', p + 48)
        M['diffuse'] = r.fmt('<3f', p + 60)
        M['ambient'] = r.fmt('<3f', p + 72)
        M['transparency_hint'] = r.u32(p + 84)
        M['texture0'] = r.cstr(p + 88, 32)
        M['texture1'] = r.cstr(p + 120, 32)
        M['texture2'] = r.cstr(p + 152, 12)
        M['texture3'] = r.cstr(p + 164, 12)
        M['tex2raw'] = r.raw(p + 152, 24)
        M['index_counts'] = r.array(p + 176)
        M['index_offsets'] = r.array(p + 188)
        M['inverted_counter'] = r.array(p + 200)
        M['unknown212'] = r.fmt('<3i', p + 212)
        M['saber_bytes'] = r.raw(p + 224, 8)
        M['animate_uv'] = r.u32(p + 232)
        M['uv_direction'] = r.fmt('<2f', p + 236)
        M['uv_jitter'], M['uv_jitter_speed'] = r.fmt('<2f', p + 244)
        M['mdx_stride'] = r.u32(p + 252)
        M['mdx_flags'] = r.u32(p + 256)
        M['mdx_offsets'] = r.fmt('<11i', p + 260)
        M['vertex_count'], M['texture_count'] = r.fmt('<2H', p + 304)
        (M['lightmapped'], M['rotate_texture'], M['background'], M['shadow'], M['beaming'],
         M['render'], M['unknown314'], M['unknown315']) = r.fmt('<8B', p + 308)
        M['total_area'] = r.f32(p + 316)
        M['unknown320'] = r.u32(p + 320)
        M['mdx_data_offset'] = r.u32(p + 324)
        M['vertex_offset'] = r.u32(p + 328)
        nv = M['vertex_count']
        # faces
        faces = []
        r.need(f_off, 32 * f_n, 'faces')
        for i in range(f_n):
            nx, ny, nz, dist, mat, a0, a1, a2, v0, v1, v2 = r.fmt('<4fI3h3H', f_off + 32 * i)
            faces.append(((nx, ny, nz), dist, mat, (a0, a1, a2), (v0, v1, v2)))
        M['faces'] = faces
        self.claim(f_off, 32 * f_n, 'faces')
        self.claim(M['index_counts'][0], 4 * M['index_counts'][1], 'index count array')
        self.claim(M['index_offsets'][0], 4 * M['index_offsets'][1], 'index offset array')
        self.claim(M['inverted_counter'][0], 4 * M['inverted_counter'][1], 'inverted counter array')
        M['faces_off'] = f_off
        # MDL vertex positions
        M['mdl_vertices'] = None
        if nv and M['vertex_offset'] not in (0, 0xFFFFFFFF):
            r.need(M['vertex_offset'], 12 * nv, 'mdl vertices')
            M['mdl_vertices'] = [r.fmt('<3f', M['vertex_offset'] + 12 * i) for i in range(nv)]
            self.claim(M['vertex_offset'], 12 * nv, 'mdl vertices')
        # index lists
        ic = M['index_counts']
        io = M['index_offsets']
        M['index_lists'] = []
        if ic[1] and io[1]:
            for k in range(min(ic[1], io[1])):
                cnt = r.u32(ic[0] + 4 * k)
                lo = r.u32(io[0] + 4 * k)
                M['index_lists'].append(list(r.fmt(f'<{cnt}H', lo)) if cnt else [])
                self.claim(lo, 2 * cnt, 'index list')
        M['inverted_counter_values'] = [r.u32(M['inverted_counter'][0] + 4 * k)
                                        for k in range(M['inverted_counter'][1])]
        # MDX vertex block
        M['mdx'] = {}
        stride = M['mdx_stride']
        base = M['mdx_data_offset']
        if nv and stride and not anim:
            self.x.need(base, stride * nv, f'mdx block of {n.name}')
            for bit, slot, comps, key in MDX_ATTRS:
                o = M['mdx_offsets'][slot]
                if o == -1:
                    continue
                M['mdx'][key] = [self.x.fmt(f'<{comps}f', base + stride * i + o) for i in range(nv)]
        return M

    def skin(self, p, n):
        # The bonemap, qbones, tbones and bone constants have one entry per node, indexed by the
        # node's position in the depth-first walk of the tree (Model.nodes order), not by its
        # name index; bone_nodes holds those tree indices for slots 0..15.
        r = self.r
        S = {}
        S['weights_array'] = r.array(p)
        S['mdx_weights'], S['mdx_bones'] = r.fmt('<2i', p + 12)
        S['bonemap_off'], S['bonemap_n'] = r.fmt('<2I', p + 20)
        qb = r.array(p + 28)
        tb = r.array(p + 40)
        cb = r.array(p + 52)
        S['bone_nodes'] = r.fmt('<16h', p + 64)
        S['tail'] = r.fmt('<2H', p + 96)
        S['bonemap'] = list(r.fmt(f'<{S["bonemap_n"]}f', S['bonemap_off'])) if S['bonemap_n'] else []
        S['qbones'] = [r.fmt('<4f', qb[0] + 16 * i) for i in range(qb[1])]
        S['tbones'] = [r.fmt('<3f', tb[0] + 12 * i) for i in range(tb[1])]
        S['const_array'] = cb
        self.claim(S['bonemap_off'], 4 * S['bonemap_n'], 'bonemap')
        self.claim(qb[0], 16 * qb[1], 'qbones')
        self.claim(tb[0], 12 * tb[1], 'tbones')
        self.claim(cb[0], 4 * cb[1], 'bone constants')
        S['arrays'] = (qb, tb, cb)
        M = n.mesh
        S['weights'] = S['bones'] = None
        if M and M['vertex_count'] and M['mdx_stride'] and n.anim_owner is None:
            base, stride, nv = M['mdx_data_offset'], M['mdx_stride'], M['vertex_count']
            if S['mdx_weights'] != -1:
                S['weights'] = [self.x.fmt('<4f', base + stride * i + S['mdx_weights']) for i in range(nv)]
            if S['mdx_bones'] != -1:
                S['bones'] = [self.x.fmt('<4f', base + stride * i + S['mdx_bones']) for i in range(nv)]
        return S

    def animmesh(self, p, n):
        r = self.r
        A = {}
        A['sample_period'] = r.f32(p)
        A['arrays'] = (r.array(p + 4), r.array(p + 16), r.array(p + 28))
        A['tail'] = r.raw(p + 40, 16)
        return A

    def dangly(self, p, n):
        r = self.r
        Dg = {}
        c = r.array(p)
        Dg['constraints'] = list(r.fmt(f'<{c[1]}f', c[0])) if c[1] else []
        Dg['constraints_array'] = c
        self.claim(c[0], 4 * c[1], 'constraints')
        Dg['displacement'], Dg['tightness'], Dg['period'] = r.fmt('<3f', p + 12)
        Dg['vertex_offset'] = r.u32(p + 24)
        nv = n.mesh['vertex_count'] if n.mesh else 0
        Dg['vertices'] = None
        if Dg['vertex_offset'] and nv:
            r.need(Dg['vertex_offset'], 12 * nv, 'dangly vertices')
            Dg['vertices'] = [r.fmt('<3f', Dg['vertex_offset'] + 12 * i) for i in range(nv)]
            self.claim(Dg['vertex_offset'], 12 * nv, 'dangly vertices')
        return Dg

    def aabb(self, p, n):
        r = self.r
        root = r.u32(p)
        nodes = []
        seen = set()

        def walk(o, depth):
            if o in seen or depth > 64:
                raise Bad(f'{n.name}: aabb tree loop at {o}')
            seen.add(o)
            bmin = r.fmt('<3f', o)
            bmax = r.fmt('<3f', o + 12)
            left, right, face, plane = r.fmt('<2Ii I', o + 24)
            e = {'off': o, 'bmin': bmin, 'bmax': bmax, 'left': left, 'right': right,
                 'face': face, 'plane': plane, 'kids': []}
            nodes.append(e)
            self.claim(o, 40, 'aabb node')
            for c in (left, right):
                if c:
                    e['kids'].append(walk(c, depth + 1))
            return e

        tree = walk(root, 0) if root else None
        return {'root': root, 'tree': tree, 'nodes': nodes}

    def saber(self, p, n):
        r = self.r
        S = {}
        S['vertex_off'], S['uv_off'], S['normal_off'] = r.fmt('<3I', p)
        S['inv1'], S['inv2'] = r.fmt('<2I', p + 12)
        nv = n.mesh['vertex_count'] if n.mesh else 0
        S['vertices'] = [r.fmt('<3f', S['vertex_off'] + 12 * i) for i in range(nv)] if S['vertex_off'] else []
        S['uvs'] = [r.fmt('<2f', S['uv_off'] + 8 * i) for i in range(nv)] if S['uv_off'] else []
        S['normals'] = [r.fmt('<3f', S['normal_off'] + 12 * i) for i in range(nv)] if S['normal_off'] else []
        self.claim(S['vertex_off'], 12 * len(S['vertices']), 'saber vertices')
        self.claim(S['uv_off'], 8 * len(S['uvs']), 'saber uvs')
        self.claim(S['normal_off'], 12 * len(S['normals']), 'saber normals')
        return S


def parse(mdl, mdx, name=''):
    return Parser(mdl, mdx, name).parse()


def corpus(game):
    """Every MDL in the install with its MDX: yields (Entry for mdl, mdl bytes, mdx bytes).

    The MDX is taken from the same container when it is there; the RIMs under rims/ keep models
    in X.rim and their MDX in Xdx.rim (global/globaldx, chargen/chargendx, ...). patch.erf, which
    kres.Game() does not read, is included.
    """
    import os
    import kres
    entries = list(game.entries())
    patch = os.path.join(game.dir, 'patch.erf')
    if os.path.exists(patch):
        entries += kres.read_container(patch)
    mdx = {}
    for e in entries:
        if e.ext == 'mdx':
            mdx.setdefault(e.resref, []).append(e)
    for e in entries:
        if e.ext != 'mdl':
            continue
        cands = mdx.get(e.resref, [])
        stem, ext = os.path.splitext(e.container)
        pick = [x for x in cands if x.container == e.container]
        pick = pick or [x for x in cands if x.container == stem + 'dx' + ext]
        pick = pick or cands
        x = kres.read_entry(pick[-1]) if pick else b''
        yield e, kres.read_entry(e), x
