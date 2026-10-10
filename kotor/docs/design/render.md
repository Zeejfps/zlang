# The rendering seam

How the game draws without knowing which graphics API is underneath. Rule 3 of AGENTS.md: game
code describes what to draw through a backend-neutral interface; only the backend calls the API,
and a Metal, Vulkan or D3D backend must be addable without touching game code.

| Directory | Namespace | What |
|---|---|---|
| `lib/base/math.ctx` | `math` | vectors, quaternions, matrices, boxes, planes, rays, frustums |
| `lib/render/render.ctx` | `render` | handles, resource descriptions, materials, the `Frame`, text layout |
| `lib/render/contract.ctx` | `render_contract` | the `gpu` functions every backend must declare, as calls the compiler checks |
| `lib/render_gl/gpu.ctx` | `gpu` | the OpenGL 4.1 core backend |
| `lib/render_gl/shaders.ctx` | `glsl` | its GLSL 410 sources |
| `lib/render_gl/gl.ctx` | `gl` | the GL binding (platform.md) |
| `lib/tex` | `tex` | TPC and TGA decoding into data `gpu::create_texture` takes |
| `lib/material` | `material` | KOTOR textures on the GPU (a cache over `res` + `tex`) and a model mesh's `render::Material` |
| `lib/mdl_render` (models lead) | `mdl_render` | a model's meshes uploaded, and a pose's draws added to a frame |

## The shape

**Two namespaces.** `render` is plain data and pure functions: it holds no capability and calls
no GPU. `gpu` is the device: every backend directory declares a namespace `gpu` with the same
functions. Game code names `render::` and `gpu::` only.

**The backend is chosen by the build.** A program's `build.ctx` adds `lib/render_gl` (or, one
day, `lib/render_metal`); that is the only place a backend is named. ctxlang has no interfaces
or dynamic dispatch to hide a backend behind, and a namespace is the cheapest seam there is:
calls are direct, and a second backend is a second directory with the same declarations.
`lib/render/contract.ctx` gives each `gpu` function as a value of its function type; nothing calls
it, but compiling it checks that the backend in the build matches the contract (a fallible one
converts to a `!T` that may fail with any error, spec §5). A program that adds `lib/render` must
add a backend.

**Only the backend holds the API's capability.** `gpu::Device` holds `gl::Gl`; the game holds a
`gpu::Device` and passes `&dev`. The window comes with the device (`gpu::open` makes both from
an `sdl::Sdl`), because what kind of window a backend needs (a GL context, a Metal layer) is the
backend's business.

**Resources are handles.** `render::Texture`, `Mesh` and `Target` are ids made by `gpu::create_*`.
The GL backend keeps fixed tables (sized by `render::Config`); an id carries its slot and a
generation, so a freed or foreign handle is ignored (or an error) rather than misused.

**A frame is data, submitted once.** The game fills a `render::Frame` (made once with capacities,
emptied by `begin_frame`) with views, draws, bone palettes, lights, shadows, emitters, particles,
debug lines and triangles, and 2D quads, then calls `gpu::submit`. The backend decides order,
sorting, batching and state. Anything over capacity is dropped and counted in `frame.dropped`.

```
let mut dev = try gpu::open{ &sdl, realloc = arena::alloc, &heap, config = render::make_config{ title = "kotor", width = 1280, height = 720, hidden = false } }
let mut frame = try render::make_frame(arena::Arena){ realloc = arena::alloc, &heap, cap = render::default_capacity{} }
let mesh = try gpu::create_mesh{ &dev, desc, vertices = mdx_rows, indices }
let tex = try gpu::create_texture{ &dev, desc, data }
// each frame:
render::begin_frame{ &frame, time }
let v = render::add_view{ &frame, view = render::make_view{ camera } } ifnull { ... }
let mut m = render::make_material{}
m.diffuse = tex
_ = render::add_draw{ &frame, draw = render::make_draw{ view = v, mesh, transform, material = m } }
render::begin_ui{ &frame, width = 800.0, height = 600.0, target = null }
_ = render::draw_text{ &frame, font, x = 10.0, y = 10.0, text = "Hello", color = render::white{}, scale = 1.0, clip = null }
try gpu::submit{ &dev, frame = &frame }
gpu::present{ &dev, &sdl }
```

## Conventions

- **World space** is KOTOR's: right-handed, Z up, metres. **Matrices** are column-major
  (`m[col * 4 + row]`), vectors are columns, `mat4::mul{ a, b }` applies `b` first.
  **Quaternions** are `Quat{ w, x, y, z }`, scalar first as the MDL header and LYT store them
  (MDL keys are x, y, z, w: reorder when reading them).
- **Cameras** give a view matrix (world to eye, the eye looking down its -Z, as `look_at` makes)
  and a projection in GL's clip convention (`perspective`, depth -1..1). A backend whose clip
  depth runs 0..1 converts inside itself; the game never does.
- **Textures are stored bottom row first**: v = 0 is the first stored row, the bottom of the
  picture. TPC, TGA and MDL UVs all work this way (tpc.md, mdl.md), so data uploads as stored
  and UVs are used as they are. Render targets follow suit. `render::upright{}` is the UV
  rectangle that shows a whole texture the right way up on a quad.
- **2D** is in pixels of a UI pass's own size (`begin_ui`'s width and height, stretched over the
  target), origin top left, y down. Rotation is counterclockwise on screen.
- **Pixels read back** (`read_screen`, `read_target`) are RGBA8, top row first: write them with
  `png::save{ ..., bottom_up = false }`.

## Resources

**Textures** (`render::TextureDesc` + bytes): `flat` or `cube`; `grey8` (sampled as g, g, g, 1),
`rgb8`, `rgba8`, `dxt1`, `dxt5`; `levels` mip levels in the data, or one level with `mipmap` to
have the backend build them; filter and wrap per texture. The data is each face (GL's order +X
-X +Y -Y +Z -Z) with its levels largest first, which is TPC's own order, so `lib/tex` hands a
TPC's pixels over without copying (except cube face 5, which TPC stores upside down and `tex`
flips). `render::texture_size` says how many bytes a description needs. `gpu::update_texture`
replaces a rectangle of an uncompressed level (video planes, generated textures).
`render::Info.dxt` says whether DXT uploads as it is; where it doesn't, decode with `tex` first.

**Meshes** (`render::MeshDesc` + vertex bytes + u16 indices): a `VertexLayout` gives the byte
offset of each attribute, -1 where absent: position, normal, uv0, uv1, tangent space (9 floats as
MDX keeps them: +dP/dv, -dP/du, normal), skin weights (4 f32), bone slots (4 f32 with -1 unused,
as MDX stores them, or 4 u8 with `bones_u8`), colour (4 u8) and dangly constraint (1 f32,
0..255). Interleaved, offsets are into `stride`-byte rows of MDX's shapes, so an MDX block
uploads as it is. `planar`, each attribute is its own packed array: `render::pack_streams` lays
out lib/mdl's per-attribute arrays (`render::Streams`) that way in one buffer
(`streams_size` bytes), with u8 bone slots, and returns the layout; `layout_size` says how many
bytes any layout needs. Triangles wind counterclockwise from the front (MDL's winding); lines are
a primitive too. `gpu::update_mesh` rewrites vertex bytes (lightsaber blades, anything
CPU-animated).

**Targets**: `gpu::create_target{ width, height }` makes an offscreen RGBA8 colour texture
(`gpu::target_texture`) with its own depth and stencil. A view can draw into one and a quad or
material can then show it: GUI 3D views (the main menu's character), portraits, screen effects.

## A frame

| Item | What it says |
|---|---|
| `View` | a camera (view, projection, eye), a target (null: the screen) and viewport, clears, ambient light, linear fog |
| `Draw` | a mesh (or an index range of it), a transform, a `Material`, a bone palette range, a dangly displacement, a bounding sphere |
| bones | matrices appended with `add_bones`, referred to by a draw's `bones`/`bone_count` |
| `Light` | a point light: position, colour (times its multiplier), radius |
| `Shadow` | a draw whose shadow volume to sweep from a light, how far, and how dark |
| `Emitter` + `Particle`s | a texture with a sprite grid, a blend, how particles face, their space; each particle's position, size, angle, colour, cell, direction |
| `Line`, `Tri` | debug geometry in world space, depth-tested or on top |
| `Quad` | a 2D rectangle: UVs, colour, an image (none, a texture, or a video frame's YUV planes), blend, clip rectangle, angle |
| `Step` | the passes in order: a view's 3D drawing (`add_view`), or a run of quads (`begin_ui`) |

Passes run in the order they were added, so a GUI can draw a panel, then a 3D view into a target
or a viewport, then more GUI over it.

**Materials** (`render::Material`, by value in each draw; `make_material` gives an opaque, lit,
fogged white): diffuse (uv0, through `uv_scale`/`uv_offset`, wrapped into a cell first with
`uv_cell` for flipbook atlases: `set_flipbook_frame`), lightmap (uv1, multiplied in place of
lighting), envmap (a cube is reflected in world space with Z up; a flat texture is used as a
sphere map), bumpmap (a tangent-space normal map), blend (`opaque`; `punch` = kept where alpha >
0.35, the original's cut, otherwise opaque; `alpha` = blended, no depth writes; `additive`;
`alpha_depth` = blended but writing depth and discarding only alpha 0, the original's default for
textures with alpha), colour (tint; its alpha is the opacity of the alpha controller or
`wateralpha`), self-illumination (the original's GL_EMISSION, 0x00473900: added to the light, the
sum clamped to 1 as the fixed-function pipeline clamps the lit colour, then modulated by the
texture), `lit`, `fog`, `two_sided`, `decal` (depth bias, no depth
write), `env_amount`, `inflate` (metres each vertex is pushed out along its normal, after skinning:
a shell drawn over a body, the original's energy shield; 0 for everything else) and `sort` (the
MDL transparency hint: lower draws first among transparent surfaces). With an envmap on an opaque or punch surface, the diffuse alpha is the reflection
mask and the surface stays opaque (re/render-gui.md, "Environment maps"): on a lightmapped surface
the reflection is added, `lit + reflection × (1 − alpha)`; on any other (creatures, placeables,
doors) the two are blended by alpha, `mix(reflection, lit diffuse, alpha)`, so low-alpha armour
plates show the (dark) environment and not a light diffuse plus a mirror.

### How KOTOR's materials map

The seam says what a surface does, not where that came from; `lib/material` maps KOTOR's data onto
it (`material::for_mesh`, given a mesh's texture names and flags), loading textures through its
`Cache` (res's TPC-or-TGA rule, tex's decoding, the standalone TXI for TGAs):

| KOTOR | Material |
|---|---|
| texture 0 | `diffuse` (a TPC flipbook as its atlas, frame 0: `set_flipbook_frame` animates it) |
| `lightmapped` + texture 1 | `lightmap` |
| TXI `blending additive` / `punchthrough` | `additive` / `punch` |
| TXI `decal 1` | `decal` |
| TXI `envmaptexture`, `bumpyshinytexture`; appearance.2da `envmap` (not `DEFAULT`) | `envmap` (cube or sphere by the texture) |
| TXI `bumpmaptexture` (an RGB(A) normal map; grey height maps not yet) | `bumpmap` |
| TXI `wateralpha` | `alpha` at that opacity |
| transparency hint | `sort` |
| no blending keyword, no env/bumpy-shiny/bump map named, TPC AlphaMean < 0.999 | `alpha_depth` (the original's default blend, below) |
| node alpha (pose, times ancestors') < 1 | `alpha`, colour.a times it (`material::set_alpha`) |
| `selfillumcolor` | `selfillum` |
| TXI `mipmap 0`, `filter 0`, `clamp` | the texture's sampling |

Texture alpha, from the binary (re/render-gui.md, Materials): a material's default blend is
`SRC_ALPHA, ONE_MINUS_SRC_ALPHA` with depth writes and alpha test `> 0`, so a texture's alpha is
transparency unless the TXI says `punchthrough` (`ONE, ZERO`, alpha test `> 0.35`) or `additive`
(`SRC_ALPHA, ONE`, no depth writes). Scorch marks (`LHR_blst02`, AlphaMean 0.07) and Dantooine's
bushes and leaves (`LDA_bush*`, `LDA_leaf*`, about 0.3) rely on it. Where the TXI names an
environment, bumpy-shiny or bump map, the alpha is a mask for that instead (HK-47, the
astromech, `c_rancor01` with its bump map, all solid in the game): `opaque`. A texture without
alpha (AlphaMean 1, DXT1) looks the same either way, and stays `opaque`, which sorts better.

**Skinning**: a draw's palette slot k takes a mesh-space vertex to the space `transform` takes to
world. lib/mdl's `mdl_anim::skin_palette` gives palettes in the skin node's own space (identity at
bind), so a skinned mesh draws with `transform = instance · pose.world[mesh.node]` like a rigid
one. Up to 32 slots (KOTOR uses at most 17).

**Dangly meshes**: the vertex shader moves each vertex by `dangle × constraint / 255`. The spring
(displacement, tightness, period from the dangly header) is simulated by whoever animates the
model, one displacement per mesh per frame; the seam only applies it.

**Lights**: each lit draw without a lightmap gets ambient plus the eight frame lights that reach
its bounding sphere most strongly; each falls off as (1 − d/radius)². The game puts in the frame
only the lights that should touch dynamic objects (the room's light nodes, by priority).

**Shadows**: stencil shadow volumes, as the original's: a geometry shader sweeps every triangle of
the draw's mesh (skinned the same way) that faces the light into a closed prism, the prisms are
counted into the stencil (depth-fail), and every counted pixel that is not a model's (creatures,
objects and effects mark the stencil's top bit as they draw) is darkened once. Soft Shadows blurs
that mask in a 512 x 512 target. The game picks the light and the reach. `Material.distort` asks
for the Frame Buffer Effects' screen distortion instead of the surface (lib/render_gl/orig_fx.ctx).

**Particles**: one emitter is one batch. Facing: `camera` (MDL `Normal`, `Linked`), `emitter_plane` (lie in the
emitter's own X/Y plane: `Billboard_to_Local_Z`), `world_plane` (lie flat in the world's X/Y plane:
`Billboard_to_World_Z`), `upright` (stand along `axis`, its side square to the view: `Aligned_to_World_Z`),
`tangent` (lie in the plane of each particle's `dir` and the tangent about `axis`: `Aligned_to_Particle_Dir`),
`velocity` (a streak along each particle's `dir`, turned about it toward the eye: `Motion_Blur`; the game
sets the quad's length and centre), and two the MDL has no name for: `axis` (stand along `axis`, turn about it
toward the eye: grass) and `plane` (lie in the plane whose normal is `axis`). What the modes are in the
original: [../re/particles.md](../re/particles.md). The simulation (birth, life, colour and size curves) belongs
to the game; the frame gets the live particles. Emitters sort with transparent draws.

**Text**: `render::Font` is a texture and a glyph box per byte (a font TXI's `upperleftcoords` and
`lowerrightcoords`; v of the upper corner is the larger), with `fontheight`, `baselineheight` and
`spacingR` × 100 in texels. `draw_text` lays out one line into quads, `measure_text` says how
wide it is. Wrapping and alignment are the GUI's. `font::load` (lib/material/font.ctx) makes a
`render::Font` from a game font through `res`: the TPC's top level, nearest filtering, and the
glyph table from its TXI; with `variant` it takes `NAMEb` when that exists (txi-render.md: GUI
files name `fnt_d16x16`, whose table doesn't fit its pixels, and `fnt_d16x16b`'s does).

**Video**: a movie's Y, U and V planes as three `grey8` textures updated each frame, drawn with
`Image::yuv`; the backend converts BT.601 limited range (bink.md) in the shader.

## The GL backend

- Programs: one scene program for every mesh material (uniform switches pick the paths: maps
  present, blend, lit, fog, shadow), instanced programs for quads and particles, one for debug
  geometry. GLSL 410: samplers' units and the per-view `Frame` uniform block's binding are set
  after linking.
- Order within a view: opaque and punch draws sorted by (punch, diffuse, lightmap, mesh); then
  shadows; then transparent draws and emitters together, by `sort` and then far to near; then
  debug triangles and lines (depth-tested first). Culling: draws with a radius are tested
  against the view frustum.
- Every frame draws into an offscreen `screen` target of the window's drawable size; `present`
  blits it to the window, `read_screen` reads it. A hidden window (Config.hidden) gives the same
  pixels headless, which is how every agent checks rendering.
- Streamed data (quads, particles, debug geometry) goes through one orphaned vertex buffer in
  chunks; the vertex arrays for it are made once.

## The enhanced renderer

`render::Enhance` (set on the device with `gpu::set_enhance`), `View.sun`, `focus`, `grade`, `height_fog` and
`exposure`, `Draw.kind`, `casts` and `ambient`, `frame.ambients` and `gpu::get_timings` are the inputs of the
modern effects (HDR and bloom, room light on creatures, shadow maps, occlusion, ...): every effect, its inputs,
cost and pictures are in [enhanced-render.md](enhanced-render.md). With `Enhance.on` false a backend draws
exactly what this document describes. The GL backend's enhanced passes are `lib/render_gl/fx*.ctx`.

## Checking it

`kotor/tools/ctxc run kotor/tools/rendertest` writes, in `kotor/out/render/`: `materials.png`
(every material path, skinning, dangly, particles, shadows, fog, debug geometry, a second
viewport), `ui.png` (game fonts loaded through `res`, clipping, rotation, additive quads, a render
target, a YUV frame, alpha steps), `m01aa_02a_iso.png` (the lightmapped room, as
`tools/py/mdlrender.py`'s `out/mdl/m01aa_02a_iso.png`) and `bastila.png` (`p_bastilabb` with
`p_bastilah` at the headhook: bind pose, `pause1` at 0.5 s, `run` at 0.2 s from the side, GPU
skinned; as `out/mdl/bastila_skinned.png`), `gallery.png` (HK-47 and an astromech with their
TXI environment maps, a lightsaber hilt, a chrome ball reflecting the real `cm_tat` cube map:
sky above, sand below), `area_top.png` (every room of `m01aa.lyt` from above, as
`out/mdl/lyt_m01aa_top.png`) and `ingame.png` (Bastila standing on the room's walkmesh, found by
casting a ray at its AABB mesh, lit by the room's lights and shadowed onto the floor from the
nearest one, at eye height). `kotor/tools/texcheck` decodes every TPC and TGA of
the install (11,536 + 5,602, 0 failures) and writes a contact sheet and single textures to
`kotor/out/tex/`; `kotor/tools/mathcheck` checks the math identities.

## Open

- **Not verified against the engine**: the light falloff, the env-map strength and mask rule,
  bump-map channel orientation on real models, the punch threshold, additive weighting by alpha,
  particle grid order (cell i counted from v = 0, as TXI flipbooks are), fog for additive
  surfaces (faded to black). RE of the renderer's material setup (re/render-gui.md, part render
  0x00474220 and DrawIndexed variants) would settle them.
- Not yet: lightsaber blade geometry (the engine builds it; game side), the original's film noise outside the
  video effects. Done since: multisampled screen and target buffers, the brightness curve in `present`, stencil
  shadow volumes and their blurred soft shadows, the glow and the stealth distortion, a view's speed blur, anisotropy and v-sync switched live, window kinds and the
  screen scaled to the window with its aspect kept ([../mechanics/graphics.md](../mechanics/graphics.md)).
