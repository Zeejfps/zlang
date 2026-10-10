# The enhanced renderer

Modern rendering over the original's assets: each effect a switch on the **Enhanced Graphics** panel, the
original's art direction kept (enhance, don't repaint), the GUI, HUD, movies and text untouched, the simulation
untouched. The code is `lib/render_gl/fx*.ctx` (the GL backend's passes), `lib/render/render.ctx` (what the game
says, below), `lib/scene` (what the game knows: draw kinds, the light around objects, the sun), `lib/frontend/enhanced.ctx`
(the panel) and `game/fxhud.ctx` (the GPU timing lines). [render.md](render.md) is the seam this extends.

## Through the seam

Everything is data; only `lib/render_gl` knows how. A Metal or Vulkan backend implements the same inputs.

| Input | Where | What |
|---|---|---|
| `render::Enhance` | `gpu::set_enhance{ &dev, enhance }`, from `display::apply` (live, like the other options) | which effects, at which level (0 off, 1 low, 2 high); `on` false is the original look |
| `View.sun` | per view | the area's sun: the way its light travels, its colour, how dark its shadows are |
| `View.focus` | per view | depth of field: focus distance, sharp range, how much the rest blurs |
| `View.grade` | per view | a colour grade: a 32x32x32 lookup table as a 1024x32 rgb8 strip (slice b at x = 32 b) |
| `View.height_fog` | per view | fog thickest at height `base`, thinning by e every `falloff` metres |
| `View.exposure` | per view | times `Enhance.exposure`; 1 keeps the original's mid-tones |
| `Draw.kind` | per draw | `room` (baked light: receives shadows and occlusion), `creature`, `object` (placeable, door, item), `effect` (VFX, blades: emissive), `other` |
| `Draw.casts` | per draw | throws a shadow from the sun and shadow-casting lights (the MDL mesh's shadow flag, on creatures and objects) |
| `Draw.ambient` | per draw | the light around it: `frame.ambients[ambient - 1]`, an ambient cube (six colours, world axes) |
| `gpu::get_timings{ dev }` | out | the GPU's time per pass of the last measured frame (`Enhance.timing`) |

**Which views.** A view drawn to the screen that clears its colour, with `Enhance.on`: the game's view and the
main menu's 3D scene. A view into a target (portraits, GUI previews) or one drawn over a panel without clearing
(character generation's figure) keeps the original look. The GUI, the HUD, movies and text are drawn after the
tone curve, into the screen as before.

**Original Look.** `Enhance.on` false takes the original path in every view: the same programs, state and order
as before the enhanced renderer existed. Checked pixel for pixel against a build of the previous commit
(`python kotor/tools/py/imgdiff.py`): the bridge at 1280x720, and the apartment with 4x anti-aliasing and soft
shadows, 0 pixels differ.

## The frame of an enhanced view

1. Shadow maps (the sun's and the chosen lights', one depth atlas).
2. The scene into floating-point targets the size of the screen: the light (RGBA16F, unclamped), the view-space
   normal and the share of the light that occlusion may darken (RGB10_A2, a second output of the same draws), with
   reflections the environment map's share (RGBA16F, a third output), depth and stencil (a texture). Multisampled
   twins when Anti-Aliasing is on, resolved by blits. Opaque surfaces write every output; shadows, transparent
   surfaces, particles and debug geometry the light alone.
3. Between the opaque and the transparent surfaces, the passes that read depth and normals and blend into the light:
   ambient occlusion, reflections, height fog.
4. The transparent surfaces and particles, then the post chain: depth of field, light shafts, bloom, the composite
   (exposure, tone curve, grade, a little noise against banding) into the screen over the view's viewport (through
   the edge filter when it is on). The speed blur (Frame Buffer Effects) follows as before; then the GUI.

## Cost, all of it

RTX 4090, Tatooine's Anchorhead (the sun's shadows, 30 draws of creatures and objects, an environment-mapped
square), every option at its default (high, tessellation off, FXAA), GPU timestamps per pass (`gfx timing 1`; the
opaque and transparent passes partly measure the CPU's pace of issuing draws):

| | 1920x1080 | 2560x1440 | 3840x2160 |
|---|---|---|---|
| shadow maps | 0.10 | 0.18 | 0.12 |
| opaque (with shadows received, room light, smooth lightmaps) | 0.30 | 0.23 | 0.31 |
| occlusion | 0.10 | 0.17 | 0.39 |
| reflections | 0.12 | 0.19 | 0.46 |
| height fog | 0.01 | 0.02 | 0.06 |
| transparent | 0.01 | 0.01 | 0.02 |
| bloom | 0.06 | 0.07 | 0.11 |
| composite (tone curve, grade) | 0.01 | 0.02 | 0.05 |
| edge AA (FXAA) | 0.04 | 0.07 | 0.14 |
| **3D total** | **0.75** | **0.96** | **1.66** |
| the original renderer's 3D view, same scene | | 0.10 | |

Under the 3 ms aim at 1440p with room to spare. Depth of field (conversations, +0.03 ms at 720p) and light shafts
(toward the sun, 0.07 ms at 1440p) add only when they apply. For a weaker GPU (a Mac): every effect has a low
level or a switch; the heaviest at 4K are reflections and occlusion (low halves their taps), shadows (low: one
light, 2048² atlas, PCF), bloom (low: 4 levels).

## The fixed scene set

| Scene | Pictures (in `kotor/out/fx/`, from this branch's runs) |
|---|---|
| Endar Spire corridor, a lightsaber fight (the Jedi duel cutscene from the `bunk` checkpoint) | `duel_saber_cmp.png` (original above, enhanced below: blades glow, focus on the duel, the floor reflects, soft shadows); `bolt_crop_before_after.png` (a blaster bolt) |
| Endar Spire bridge | `t/bridge_sm_cmp.png` (shadows), `t/bridge_ao_cmp.png`, `t/bridge_ssr_cmp.png`, `t/bridge_lm_cmp.png`, `aa/edges_cmp_bridge.png` |
| Taris apartment | `t/apt_rl_cmp.png` (room light), `t/apt_ao_d.png` (occlusion) |
| Taris Upper City | `t/up_sm_cmp.png` (planar, low, soft shadows), `atmos/taris_before.png` / `taris_after.png` |
| Dantooine grove (outdoor sun) | `t/grove_rl_cmp.png`, `t/grove_all.png`, `atmos/grove_cmp.png`, `atmos/sun_cmp.png`, `aa/foliage_cmp_grove.png` |
| Tatooine Anchorhead (sun shadows) | `t/tat_sm_cmp.png`, `t/tat_lm_cmp.png` |
| Kashyyyk Shadowlands (foliage) | `atmos/kashyyyk_before.png` / `kashyyyk_after.png`, `aa/foliage_cmp_kashyyyk_grass.png` |
| A conversation (Trask on the Endar Spire) | `t/talk_dof_cmp.png`, `t/tess_cmp.png` |
| The main menu's 3D scene | `t/menu_fx3d.png`, `aa/edges_cmp_menu.png`; the panel: `t/menu_fx.png` |
| Planet grades | `p/sheet1.png` .. `sheet4.png` |

Not captured: the Star Map (its dome is sealed until the story opens it); self-illumination's glow shows on the
Endar Spire's screens and lamps instead.

## The effects

### HDR, tone curve and bloom

- **Inputs**: `Enhance.bloom`, `Enhance.exposure`, `View.exposure`; the materials' self-illumination and additive blend.
- **What**: the scene's light is kept past white. Self-illuminated surfaces (screens, holograms, the Star Maps,
  lamps) add 0.35 of their emission again past the original's clamped colour, additive surfaces (blades, bolts,
  glows) and additive particles half again as much; nothing else changes. The bloom takes what is brighter
  than 0.9 (soft knee 0.35, each 2x2 group weighted by 1 / (1 + brightness) against flicker), down a chain of
  half-size levels (13-tap filter; 6 levels high, 4 low) and back up (3x3 tent, added level by level), and
  adds it at 0.5 / levels. The tone curve leaves every colour whose brightest channel is up to 0.9 as it is (the
  original's mid-tones exactly), bends that channel smoothly to 1 at 1.1 (white shows at 0.975), scales the
  colour with it (hue kept) and fades what is far past white toward white (a blade's core). Exposure is fixed (1).
- **Cost** (RTX 4090, the Endar Spire bridge): bloom 0.05 ms at 1080p, 0.10 ms at 4K; composite 0.01 / 0.03 ms.
- **Pictures**: `kotor/out/fx/t/bridge_base.png` / `bridge_fx_planar.png`.

### Room light (creatures lit by the room)

- **Inputs**: `Enhance.room_light`; `Draw.ambient` and `frame.ambients` (ambient cubes), filled by `lib/scene/probes.ctx`.
- **What**: the game finds the light around each creature, placeable and door from the rooms' lightmaps and hands it
  over as an ambient cube; the shader uses it in place of the area's flat ambient (`DynAmbientColor`), so a character
  in shadow is darker, one by a red wall is tinted by it, and the floor lights it from below. The frame's point lights
  still add on top, per pixel as before.
- **Probes**: a lattice of cells 1.5 m across and 2 m high; a cell's probe is made the first time something drawn
  stands next to it and kept for the area. A probe casts 12 rays over each face's hemisphere (cosine-spread) at the
  rooms' opaque triangles (world space, kept with their lightmap UVs; triangles far from the walkmeshes and backdrops
  over 80 m are left out) through a grid of 2 m cubes; a hit sends back its lightmap texel (lightmaps kept on the CPU
  at 64x64 at most) times its texture's mean colour, a miss the area's ambient. A ray meeting a surface from behind is
  inside geometry; a probe that sees mostly backs counts for nothing. An object's cube mixes the four probes around it.
  Decisions, to keep the art direction: half of each face's colour is pulled back to the area's ambient tint (the
  designers' choice) at the face's brightness, and the brightness stays between half and twice the area's ambient.
- **Cost**: CPU, the first frame of an area (the triangles, lightmaps and grid, then the visible objects' probes):
  65 ms on the Endar Spire bridge (77,000 triangles, 104 probes), 37 ms in the Dantooine grove; afterwards only new
  cells, at ~0.1 ms a probe. GPU: one more uniform array per draw.
- **Pictures**: `kotor/out/fx/t/apt_rl_cmp.png` (the Taris apartment: flat ambient, room light), `grove_rl_cmp.png`.

### Shadows (shadow maps)

- **Inputs**: `Enhance.shadows` (0 the original's planar shadows, 1 shadow maps with 3x3 PCF, 2 soft), the Shadows
  option (off: none at all); `View.sun` (direction, colour, `strength` = the ARE's ShadowOpacity, `light` = which frame
  light is the sun); `Light.shadow` (the MDL light's shadow flag); `Draw.casts`, `Draw.kind`.
- **The sun**: the ARE has no sun direction. The rooms carry the light their lightmaps were baked from: an outdoor
  area has one shadow-casting light that reaches 100 m or more from far overhead (the grove: 2000 m from 270 m up,
  Anchorhead, the Shadowlands, the ruins' exterior). `lib/scene/sun.ctx` finds it (not in interior areas, nor
  underground ones unless natural) and the view's sun travels from it to the camera's subject; dynamic shadows then
  fall the way the baked ones do. `scene::mark_sun` tells the backend which frame light it is.
- **Point lights**: the shadow-casting frame lights (not the sun) that light this view's casters near the camera's
  subject most (Σ over the casters of (1 − d/r)² × brightness, nearer casters more; a caster counts fully within
  8.4 m of the subject and not at all past 12 m, and a light fully from 0.75 m above it, not below 0.25 m, so no
  term is cut off at an edge): 1 low, 3 soft. Only the casters the maps draw are counted (`casts_into_map`, the
  rule `draw_casters` uses). **The choice holds still**: it is kept from frame to frame by the lights' places, a
  chosen light keeps its place unless another scores 1.5 times as much, and stays chosen at least 0.5 s; a light's
  shadows fade in and out over 0.4 s of frame time (its weight scales its darkening of the rooms and its share of a
  creature's light), so up to 5 lights have maps at once (the chosen and those fading out). A camera cut (the eye
  2 m from the last frame's), a new area or time running back takes the new choice at once.
- **No light near** (no sun, no chosen point light): an overhead map, the moving casters from above and a little to
  one side (the direction the original look's volumes take then, `visual.ctx` `shadow_of`), at the indoor strength
  0.6, fading in and out with the point lights. Decision: an enhanced view never switches to the original's volumes
  while its Shadows level is Low or Soft. It used to, for the whole view, the frame no light qualified: the shadows
  went from soft maps to hard, darker volumes from another direction in one frame and back (the "shadows flicker or
  become hard" report: 4 such flips and 124 light pops in 80 s of the Endar Spire's bridge replay).
- **Maps**: one depth atlas (2048² low, 4096² soft). Top half: the sun's two orthographic maps (a 48 m low / 64 m
  soft square around the point 0.5 × reach ahead of the camera, snapped to whole texels against shimmer), one with
  the moving casters only, one with the rooms too (alpha-tested and alpha-blended-with-depth surfaces cut by their
  texture's alpha). Bottom half: 6 faces per point light (512² / 256² tiles), moving casters only (a lamp sits in its
  fixture: rooms would shadow everything), the far plane at 1.6 × the light's radius (the original's shadows were not
  cut off where the light ends; the last third fades). Casters draw two-sided with slope-scaled depth offset;
  receivers offset along their normal by 1.5 texels.
- **Receiving**: rooms (their own shadows are baked) take only the moving casters' maps: the lightmap is darkened by
  ShadowOpacity × (how much the surface faces the sun, or the point light's falloff) × occlusion, at most 85%; a
  dim sun's shadows are fainter (× its brightness × 2, at most 1). Creatures and objects take the second sun map
  (a building or a tree shades them) and the point maps, each on the light it belongs to. Low: 9 bilinear compares.
  Soft: a 12-tap blocker search, then 16 compares over a penumbra that widens with the caster-to-receiver distance
  (PCSS; a sun of about a degree, a 0.15 m lamp), rotated per pixel. With the Shadows level Planar the original's
  stencil volumes are drawn instead (hard in an enhanced view: their Soft Shadows blur is the original look's).
- **Cost** (RTX 4090, 1280x720 timer marks): the maps 0.2 ms on Tatooine's Anchorhead (sun), 0.19 / 0.33 ms in
  Taris's Upper City (1 / 3 lights); receiving is part of the opaque pass (+0.02-0.1 ms).
- **Pictures**: `kotor/out/fx/t/tat_sm_cmp.png` (Anchorhead: planar, low, soft), `up_sm_cmp.png` (Upper City),
  `bridge_sm_cmp.png` (the Endar Spire bridge: the planar shadows' dark band gone).

### Ambient occlusion

- **Inputs**: `Enhance.ao`; the opaque surfaces' depth and view-space normals (the scene's second output), whose
  alpha is the share of a pixel's light that occlusion may darken: 1 for lightmapped surfaces, 2/3 for lit creatures
  and objects (their light is part direct), less as self-illumination rises, 0 for unlit, additive and effect draws.
- **What**: after the opaque surfaces (their depth resolved from the multisampled buffers), at half resolution: for
  each pixel's view-space point, 12 taps (6 low) of the depth buffer on a spiral within 0.9 m (in screen space by
  the depth, at most 96 half-pixels), rotated per pixel; each counts by how far above the surface it rises (the
  normal), fading with distance, less a 0.15 bias. Then a depth-aware 9-tap blur across and down, and a joint
  bilateral upsample (the four half-resolution texels weighted by distance and depth likeness) multiplied into the
  light (blending DST_COLOR, ZERO) as much as the pixel's share says. Transparent surfaces and particles are drawn
  after it.
- **Cost**: 0.05-0.12 ms at 1280x720 (the apartment, the bridge).
- **Pictures**: `kotor/out/fx/t/bridge_ao_cmp.png` (off, high), `apt_ao_d.png` (the difference, times 8).

### Smooth lightmaps

- **Inputs**: `Enhance.smooth_lightmaps`; lightmapped materials.
- **What**: the lightmap is read texel by texel (four `texelFetch`, wrapping as the original's sampler does) and
  mixed with quintic weights (6t⁵ − 15t⁴ + 10t³) instead of linear ones: the light's slope is continuous across
  texels, so bilinear's diamond grid and stepped gradients on walls and floors smooth out. Decision: a B-spline
  bicubic (4x4 texels) was tried first; KOTOR's lightmap charts have no padding, so its wider footprint pulled
  dark texels across every chart border and drew each floor triangle as a block (`kotor/out/fx/t/tat_lm_d.png`
  shows that version's difference). The quintic filter keeps bilinear's 2x2 footprint and never bleeds.
- **Cost**: four fetches instead of one per lightmapped pixel; not measurable in the opaque pass.
- **Pictures**: `kotor/out/fx/t/bridge_lm_cmp.png` (bilinear, smooth; 3x).

### Lifted lightmaps (near-black texels)

- **Inputs**: `Enhance.lift_lightmaps` (the Lightmaps row's Lifted, the default; it implies Smooth); lightmapped
  materials; `LIGHTMAP_FLOOR` (fx.ctx, 0.12) in `u_fx2.z`.
- **What**: `lift_dark` (fx_shaders.ctx) right after the lightmap read (smooth or bilinear), before anything else
  touches that light. On the texel's brightest channel `m`, below 0.25, it adds `floor * (1 - m/0.25)²`: black
  becomes 0.12, 0.05 becomes 0.127, 0.1 becomes 0.143, 0.2 becomes 0.205, and from 0.25 up nothing changes. The
  curve meets the identity with the same slope at 0.25 (no knee) and rises everywhere (its slope at black is
  1 − 2·floor/0.25 = 0.04, so the floor must stay at most 0.125). The amount goes to all three channels alike at
  black and in the texel's own proportions as `m` nears 0.25, so dark coloured light keeps its hue and the 1/255
  noise of a black chart is not blown up into colour. Everything after works on the lifted light as on any other:
  received shadow-map shadows multiply it (a shadow still darkens a lifted wall), ambient occlusion multiplies the
  result, self-illumination adds to it, and the lift stays far below bloom's threshold (1.1).
- **Not in room light**: the probes (`lib/scene/probes.ctx`) read the raw lightmap texels. A creature standing in a
  black corner already keeps half the area's ambient (`keep_tint`), so it is never lost against the lifted wall;
  lifting the probes' texels too would make their cached cubes depend on a display option (rebuilt on every
  toggle) for a few percent of bounce light from walls that are dark either way.
- **Why ours**: the original multiplies by the lightmap and adds nothing (render-gui.md, "Lightmaps: black texels,
  missing lightmaps"), so the Endar Spire's corridor dead ends draw pitch black there too; with the room around
  them well lit, only thin lit edges float in a black void and read as a hole in the model. Lifted, their panels
  show, dark. Original and Smooth keep the original's black.
- **Cost**: a few ALU per lightmapped pixel; not measurable.
- **Pictures**: `kotor/out/fx/t/es_lift_end_cmp.png`, `es_lift_side_cmp.png` (the Endar Spire's far end and side
  passage, Smooth then Lifted; the dead end's mean goes from 16 to 26 of 255), `sithbase_lift_cmp.png` (a dark
  area, the most changed: mean 14.5 to 17.7 of 255, its shadows still deep), `cantina_lift_cmp.png` (no visible change).

### Depth of field (conversations)

- **Inputs**: `Enhance.dof`; `View.focus` (`distance` along the view, `range` kept sharp, `blur` 0..1); the view's
  projection (its field of view is the lens's focal length). The game sets the focus (`game/focus.ctx`): while a
  dialogue camera is up, the speaker's eyes if they are in the shot, else the listener's, else none (a cutscene's
  shot of something else stays sharp); the blur fades in over a third of a second when a shot comes up and out
  when it ends, and a cut to the next speaker pulls focus in about a fifth of a second; `range` is 0.3 m, a face's
  depth. In normal play there is no focus. Eased every tick, so pictures taken with `--no-render` see the same.
- **What**: a thin lens. Each pixel's circle of confusion is `A f |d − s| / (d (s − f))`, with `f` the focal length
  the view's vertical field of view gives a 24 mm tall sensor (55° is 23 mm; a close-up's 30° is 45 mm), `A = f / N`
  at f/2 (f/2.8 low) and `s` the focus distance, measured on that sensor and capped at a radius of 1/108 of the
  picture's height (10 pixels at 1080p; 1/144 low). So a wide shot focused a few metres away blurs its background
  by a pixel or two, a close-up with a long lens by several, as a camera would. The sky and anything far take the
  lens's far limit `A f / (s − f)`, a finite blur. After the scene is resolved, before the light shafts and the
  bloom: at half resolution the light, the 2x2 pixels weighted by brightness (1 + 4 l², so a one-pixel star keeps
  its light), and the largest blur of the four; a gather over a disc as wide as the pixel's own blur (24 taps on a
  spiral, 12 low), each tap counting only if its own blur reaches the pixel (a sharp speaker never smears into the
  background) and bright taps counting more (1 + 4 l², 2 low), so stars and lamps open into soft discs instead of
  being averaged away; then blended over the full-resolution light from a blur radius of half a pixel (nothing)
  to two (all of it). The subtitles and panels are drawn after, sharp.
- **Decision** (tuning after the first pictures read as a miniature): the first version blurred by a fixed share of
  the focus distance up to 1/90 of the height whatever the lens, so wide shots blurred as hard as close-ups and the
  starfield's points were averaged away. Now the field of view and the focus set the blur, and points survive.
- **Cost**: 0.02-0.03 ms at 1280x720 (the Endar Spire, Trask's conversation).
- **Pictures**: `kotor/out/fx/t/talk_dof_cmp.png` (a medium shot, off above, on below: Trask sharp, the stars kept,
  the player's head in front soft), `t/talk_closeup_cmp.png` (a close-up: the window and its stars as soft discs),
  `duel_saber_cmp.png` (the wide duel shot: its subject isn't a speaker in the shot, so no blur).

### Reflections (screen space)

- **Inputs**: `Enhance.reflections`; materials with an `envmap` (KOTOR's TXI `envmaptexture` / `bumpyshinytexture`,
  appearance.2da `envmap`), whose diffuse alpha masks the reflection.
- **What**: the scene's third output (with reflections on) holds, per opaque pixel, the environment map's share of its
  colour (`env × amount × (1 − alpha)`, after fog) and that share's weight. After the occlusion pass, the opaque
  light is copied (resolved when multisampled) and, for every pixel with a weight, the view ray reflected off its
  normal (the bump-mapped one) is marched through view space: 48 steps (24 low) over 24 m, quadratically spaced,
  a step landing up to 0.6 m behind the depth buffer is a hit, refined by four halvings. The pass adds
  `(what the ray met × weight − the environment map's share) × confidence` (blending ONE, ONE into the float light),
  so a hit replaces the cube map's reflection and a miss leaves it: the original's environment map is the fallback.
  Confidence fades over the last 8% of the screen's edges, past 60% of the reach, and as the ray turns toward the camera.
  Transparent surfaces keep their cube-map reflection only.
- **Cost**: 0.06 ms at 1280x720 on the Endar Spire bridge (its floor is environment-mapped); pixels without a weight
  return at once.
- **Pictures**: `kotor/out/fx/t/bridge_ssr_cmp.png` (the bridge floor under a console: cube map, then screen space).

### Tessellation (smoother silhouettes)

- **Inputs**: `Enhance.tessellation` (0 off, 1 low, 2 high); `Draw.kind` creature with a bone palette; nothing else:
  the smooth normals are the backend's own.
- **What**: skinned creature draws (opaque, alpha-tested, alpha-depth) go through PN triangles (GL 4.0 tessellation
  control and evaluation stages): the vertex stage skins as before but stays in world space; each patch's cubic control
  points come from its corners and their *smooth* normals, made at `create_mesh` for every skinned mesh (the normals of
  all vertices at the same place, to the millimetre, averaged; opposite normals keep their own). MDX splits a vertex
  wherever its UV or normal changes, and a PN surface curved by split normals opens along those seams; with smooth
  normals both sides of a seam curve alike. Shading still uses each corner's own normal, tangents and UVs,
  interpolated, and the same fragment program as everything else. Each edge is cut by its midpoint's distance from the
  eye (both triangles of an edge agree): up to 4 (2 low) from 2 m, falling to 1, flat and identical to the
  untessellated mesh, at 12 m (8 low). Shadow casters are not tessellated.
- **Decision: off by default.** Within a mesh it is crack-free; across separate meshes of one body (KOTOR splits
  heads, hands and some armour pieces into meshes of their own) each mesh's border curves by its own normals, so a
  hairline gap can open where two meshes meet, and the rounder silhouettes are a modest gain on characters this
  low-poly (they also round off a few deliberately hard edges, belts and armour rims). Worth turning on to look at;
  not clean enough to be the default.
- **Cost**: within the opaque pass's noise at 1280x720 (+0.01-0.02 ms with two characters near the camera).
- **Pictures**: `kotor/out/fx/t/tess_cmp.png` (off, high: shoulders and arms), `talk_tess_d.png` (only silhouettes change).

### Anti-aliasing

- **Inputs**: `Enhance.post_aa` (the Edge AA row: 0 off, 1 FXAA, 2 High), `Enhance.alpha_coverage` (Foliage AA), the
  Anti-Aliasing option's sample count (`dev.samples`, 0 off); per draw and per emitter `Material.blend` /
  `Emitter.blend` being `punch` (alpha-tested). Nothing else crosses the seam. A backend needs: (1) a pass that takes
  the view's finished picture as an 8-bit colour image whose alpha is the colour's luma (0.299 R + 0.587 G + 0.114 B,
  what the composite writes) and returns the same picture over the view's pixel rectangle; (2) per-sample coverage
  from a fragment's alpha for the punch-through draws (Metal `alphaToCoverageEnabled`, Vulkan
  `alphaToCoverageEnable`, D3D `AlphaToCoverageEnable`) and the coverage alpha below.
- **Which runs when**: the two are alternatives. With multisampling off, Edge AA filters the picture; with it
  on, the multisampled buffers already smooth geometry and Edge AA does nothing, and Foliage AA smooths what
  they cannot, the cut of alpha-tested surfaces. Original Look runs neither.
- **Edge filter** (`fx_aa.ctx`, `fx_aa_shaders.ctx`): the composite writes the tone-mapped picture (after bloom, grade and
  the dither noise) into an RGBA8 target the size of the screen instead of the screen, and one full-screen pass filters
  it into the screen over the view's area. Each pixel: (1) skips itself when the luma range of it and its four
  neighbours is under 0.0312 and under an eighth of the brightest (flat areas, texture noise, the dither); (2) says
  whether the edge there runs along x or y (second differences of luma over the 3x3, centre row and column
  doubled) and which neighbour across it differs more, and takes the mean of that neighbour and itself as the edge's
  level; (3) walks along the edge line half a pixel to that side, both ways, with bilinear taps of growing stride
  (1 px for four steps, then +0.5 px a step, capped at 4 px; 10 steps) until the luma on the line has moved a quarter
  of the edge's step from its level; (4) if the nearer end bends the way that shows the pixel lies on the edge's wrong
  side, moves its sample 0.5 - nearer/length pixels across the edge; (5) separately, for detail too small for an edge,
  measures how far its luma is from the 3x3 low-pass (tent weights 1-2-1) as a share of the range, shapes it
  (smoothstep, squared) and takes the larger of the two offsets, the sub-pixel part at 0.75 strength. The output alpha
  is 1. Taps are clamped to the view's pixel rectangle, so a view in a viewport (the main menu's figure) never reads
  its neighbours' pixels.
  **High** differs in: a 20-step walk (stride capped at 6 px, so edges up to ~75 px long are measured instead of ~20),
  sub-pixel strength 1, and, for specks (a pixel brighter or darker than all four neighbours with a luma range over
  0.25: a lit rim, a sparkle), the unsquared shape and a mix of the low-pass itself into the result. It is the
  same family of filter, not a morphological (SMAA-like) one: that needs a precomputed area table and search table
  (~180 KB of numbers) that would have to be copied from a reference or derived from its published construction, and
  two more passes with targets of their own for the edges and the blend weights. Decision: both
  levels are searching filters; High costs a little more and blurs a little more.
- **Alpha to coverage**: for a `punch` draw or emitter in an enhanced view with multisampling on and Foliage AA, the
  fragment's alpha is `clamp((a - 0.35) / max(fwidth(a), 1e-4) + 0.5, 0, 1)` (a the texture's alpha times the colour's
  and the vertex's; fully clear fragments still `discard`) instead of the hard cut at 0.35, and the backend enables
  alpha-to-coverage, so the fraction of the pixel's samples that survive is the share of the pixel the cut leaves:
  a leaf's or a blade's edge gets 2, 4 or 8 grades of coverage in place of two. `fwidth` makes the transition one
  pixel wide in screen space whatever the texture's scale; the 0.35 stays the line where coverage is one half. Blending
  stays off for punch-through draws, so the alpha reaches only the coverage. GL's flag is cached in `State`, left on
  between punch-through draws and turned off at the end of the opaque and of the transparent passes, so full-screen
  passes and shadows never see it. Not done: mip-level alpha rescaling (grass thins with distance exactly as in the
  original), and anything for alpha-blended surfaces (they blend per pixel already).
- **Settings**: Edge AA (key `Edge Smoothing`) `Off, FXAA, High` (`gfx edges 0..2`), Foliage AA `Off, On` (`gfx foliage 0|1`).
  Both default on (FXAA; on); the panel's descriptions say Edge AA applies when Anti-Aliasing is off and Foliage AA when it is on.
- **Cost** (RTX 4090, `gfx timing 1`): the edge pass at 1920x1080 0.03-0.04 ms (bridge 0.031 FXAA / 0.035 High, grove
  0.036 / 0.039) and at 3840x2160 0.09-0.13 ms (bridge 0.088 / 0.106, grove 0.125 / 0.129), plus the RGBA8 target the
  composite writes to (8 MB at 1080p, 33 MB at 4K; made with the other targets). Foliage AA with 4x multisampling in the Dantooine grove:
  the transparent stage (the grass emitters) 0.216 -> 0.247 ms at 1080p, 0.248 -> 0.295 ms at 4K.
- **Measured against 8x multisampling** (the bridge at 1280x720, every pixel where the unfiltered picture differs by more
  than 8/255 from 8x MSAA, 26,120 of them): FXAA brings 40% of those within 8, High 44%; 4x MSAA itself 59%. Both
  also change pixels that were already right (11,900 FXAA, 15,100 High); in the grove's noisy ground texture High
  softens visibly more than FXAA, which is the price of its stronger sub-pixel handling.
- **Checks**: Original Look (`gfx original 1`) against the previous build (`kotor_base.exe`), 0 pixels differ: the
  bridge with Anti-Aliasing off and 4x, the Dantooine grove and the Kashyyyk Shadowlands (`kas_m25aa`; punch-through
  emitters) with 4x, `kas_m23aa` (a lattice and leaf cards: punch-through meshes) with 4x, the Shadowlands with it off.
  (The previous build differs from itself by one pixel, by 1/255, on some runs.) Edge AA with 4x multisampling is identical to off.
- **Pictures** (left to right off, FXAA, High, 8x MSAA as the reference; crops enlarged 5-7x, nearest):
  `kotor/out/fx/aa/edges_cmp_bridge.png` (the door arch), `edges_cmp_grove.png` (a standing stone against the sky),
  `edges_cmp_grove_grass.png` (grass and the noise it sits in), `edges_cmp_menu.png` (the main menu's figure: off,
  High); Foliage AA, 4x multisampling, off / on: `foliage_cmp_grove.png` (grass stems),
  `foliage_cmp_kashyyyk_grass.png` (a Shadowlands flower), `foliage_cmp_kashyyyk_mesh.png` (a lattice of holes in a
  mesh, brightened 3x). Whole pictures: `bridge_e0/e1/e2.png`, `grove_e0/e1/e2.png`, `grove_a2f0/a2f1.png`.

### Light shafts

- **Inputs**: `Enhance.shafts`; `View.sun` (`on`, `direction`: the way its light travels, `color`) and the view's camera;
  the opaque surfaces' depth (resolved) and the normal target's alpha, which finds the sky (below). The game gives
  nothing else: `lib/scene/sun.ctx` already finds the sun of an open-air area.
- **What**: the sun is a point at infinity, `-direction` through the view's projection and view matrices. Behind the
  camera (clip w under 0.05) there are no shafts; they are full while the sun is on the screen or up to 0.25 screen
  heights past its edge, and fade out by 1.1 heights (the follow camera mostly looks level and the sun hangs high, so
  they show when the player turns toward it). A first pass at half the screen's size (a quarter past 1080p: the
  shafts are soft and the reads scatter) marches each pixel 28 steps toward the sun's place on the screen, at most
  0.6 view heights, starting a random part of a step in (interleaved gradient noise), and adds up the *sky* it sees,
  weighted by a glow around the sun (`(1 - r / 0.9)^2`, r the distance from the sun in view heights) and by 0.955 per
  step. What stands in front of the sky leaves its shadow in the sum, so the light streams from its silhouette. A
  sample past the view's edge takes the edge pixel. The sum, `^1.35 x 0.35 x fade`, is added to the light at full size
  (bilinear), tinted by the sun's hue (`0.3 + 0.7 colour / its largest channel`: a warm sun gives warm shafts without
  changing their brightness), and weighted by the pixel's distance (the light is gathered along the whole ray from the
  eye): half at 12 m, nearly all by 60 m; the sky itself gets a quarter, so its colour stays the artists'. After the
  scene is resolved (transparent surfaces included), before the bloom.
- **The sky**: a surface the scene's lights do not light writes alpha 0 to the normal target (the scene shader's
  `occludable`): the cleared background, the sky dome (Dantooine's is a model among the rooms, about 220 m away, so the
  far plane does not find it) and what glows by itself. Any of them is a source, near the sun only. A backend that
  stores its targets another way must supply the same mask.
- **Settings**: Light Shafts, Off / On (`gfx shafts`). The pass is skipped when the view has no sun, or the sun is
  behind the camera or far off the screen.
- **Cost** (RTX 4090, the Dantooine grove looking at the sun, shafts alone): 0.061 ms at 1080p, 0.067 ms at 1440p,
  0.18 ms at 4K (quarter size past 1080p; at half size 1440p took 0.13 ms and 4K 0.40 ms).
- **Pictures**: `kotor/out/fx/atmos/sun_cmp.png` (before, after: the grove and the crash site toward the sun, all three
  effects), `sun_before.png` / `sun_shafts.png` (shafts alone), `sun4k_crop.png` (4K, quarter-size sum).

### Height fog

- **Inputs**: `Enhance.height_fog`; `View.height_fog` (`on`, `color`, `base` height, `density` per metre at the base,
  `falloff`: it thins by e every `falloff` metres up); the camera; the opaque surfaces' depth and the normal target's
  alpha.
- **What**: a full-screen pass after the opaque surfaces and before the transparent ones, blending `(fog colour, share)`
  into the light. It turns the depth back into a world position (the inverse of projection x view, made on the CPU)
  and integrates an exponential fog along the ray from the eye to it in closed form: the density is
  `d0 exp(-(z - base) / falloff)` (heights below the base count as the base); z is linear along the ray, so the fog
  crossed is `d0 x length x (e^(-k h0) - e^(-k h1)) / (k (h1 - h0))` between the ends' heights h0 and h1. The share
  is `1 - e^-tau`, at most 0.85, gone toward the far plane (0.8 to 0.9 of its distance). The sky (alpha 0 in the
  normal target, or depth 1) gets none. It lies over the area's linear fog (`View.fog`, which the scene shader
  applied already), so a fogged area gets both; the transparent surfaces drawn later (glass, particles, planar
  shadows) take only the linear fog.
- **The game's side** (`lib/scene/atmosphere.ctx`, found the first time a view asks in an area): on in open-air areas
  only, by the ARE's Flags: not interior (1), and not underground (2) unless natural (4) (the Kashyyyk Shadowlands are
  underground and natural, and get a forest-floor mist; the Endar Spire and other interiors get none). `base` is the
  lowest point of the rooms' walkable faces; `density` 0.006 per metre; `falloff` 4 m plus 0.4 per metre between the
  walkmesh's lowest and highest points, 5 to 14 m (the Dantooine grove spans 14 m: 9.6 m). `color` is the ARE's fog
  colour where it has one (the grove's is its sky's pink, so the far hills dissolve into the sky), else the area's
  ambient colour times 1.5 plus 0.05 (the Taris upper city's pale blue).
- **Settings**: Height Fog, Off / On (`gfx hfog`).
- **Cost** (RTX 4090): 0.011 ms at 1080p, 0.017 ms at 1440p, 0.043 ms at 4K.
- **Pictures**: `kotor/out/fx/atmos/grove_cmp.png` (before, all three, fog alone, grade alone),
  `kashyyyk_before.png` / `kashyyyk_after.png`, `taris_before.png` / `taris_after.png`.

### Colour grades

- **Inputs**: `Enhance.grade`; `View.grade`, a texture: a 32x32x32 lookup table as a 1024x32 rgb8 strip, slice b (blue)
  at x = 32 b, red along a slice's row, green up its rows, bottom row first, filtered linearly, clamped, no mips. The
  composite reads it after the tone curve (it did already) and blends between the two nearest slices. `View.grade`
  null: the picture as it is.
- **The game's side** (`lib/scene/atmosphere.ctx`): the planet comes from the module's name (`end_` Endar Spire, `tar_`
  Taris, `danm` Dantooine, `tat_` Tatooine, `kas_` Kashyyyk, `manm` Manaan, `korr` Korriban, `lev_` Leviathan, `unk_`
  Unknown World, `sta_` Star Forge, `ebo_` Ebon Hawk; the others have none, so no table). The table is computed in code
  the first time a view asks in an area (32,768 colours, a few milliseconds), uploaded with `gpu::create_texture`,
  freed with the scene (`scene::release`) and given to every view of the area. A grade does, in order, to each colour:
  contrast (toward a smoothstep S curve), gamma, lift (raises the blacks) and gain (scales the whites), split toning (a
  colour added in the shadows and one in the highlights, by `(1 - luma)^2` and `luma^2`), saturation.
- **Choices**, all small (a few per cent at most, so the artists' colours stay what they are; the numbers are in the
  code): Endar Spire: clean steel, cold shadows, 0.97 saturation. Taris: smog, sickly green shadows, yellow highlights,
  0.93 saturation, mid-tones a little darker. Dantooine: warm gold, 1.06 saturation, mid-tones lifted a little.
  Tatooine: sun-bleached, warm shadows and orange highlights, firmer contrast, 0.96 saturation. Kashyyyk: deeper green
  in the shadows, a little darker, 1.04 saturation. Manaan: sea and glass, teal in the shadows and the lights.
  Korriban: ochre and dried blood, deeper darks, red shadows. Leviathan: cold, dim and sickly, 0.94 saturation.
  Unknown World: dust and ancient stone, warm gold with cool shade. Star Forge: hard contrast, cold blue-teal
  shadows. Ebon Hawk: a hair warm.
- **Settings**: Colour Grade, Off / On (`gfx grade`).
- **Cost** (RTX 4090): the composite takes 0.003 ms more at 1080p, 0.005 ms at 1440p, 0.008 ms at 4K with a grade.
- **Pictures**: `kotor/out/fx/p/sheet1.png` to `sheet4.png` (off on the left, on on the right: Endar Spire, Taris,
  Dantooine / Tatooine, Kashyyyk, Manaan / Korriban, Leviathan, Unknown World / Star Forge, Ebon Hawk),
  `kotor/out/fx/atmos/bridge_before.png` / `bridge_after.png` (the Endar Spire bridge: an interior, no shafts, no fog,
  the grade alone).

All three together (RTX 4090, shafts and fog active): 0.09 ms at 1440p, 0.075 ms at 1080p, 0.23 ms at 4K. Original
Look (`gfx original 1`) against the build before the enhanced renderer: 0 pixels differ in the Dantooine grove and on
the Endar Spire bridge at 1280x720. With Enhance.on false none of these passes runs; the game's side only keeps a
table and a few numbers.

## Settings

The panel is the Advanced Graphics panel's file (`optgraphicsadv.gui`) laid out again: one column of fifteen
rows (the original's choice button and arrows, cloned), the description pane where it was. It opens from the
Graphics panel's **Enhanced Graphics** button (under Advanced Options). Every change applies at once; Cancel puts
back what it opened with; closing it writes the settings file's `[Enhanced Graphics]` section. Decision: a new
settings file starts with every enhancement on (tessellation off); offscreen runs use the same defaults.

| Row | Key | Levels | `gfx` word |
|---|---|---|---|
| Original Look | `Original Look` | Off, On | `original` |
| Bloom | `Bloom` | Off, Low, High | `bloom` |
| Room Light | `Room Light` | Off, On | `roomlight` |
| Shadows | `Shadow Maps` | Planar, Low, Soft | `shadowmaps` |
| Occlusion | `Ambient Occlusion` | Off, Low, High | `ao` |
| Lightmaps | `Lightmaps` (0, 1, 2; a file with only the old `Smooth Lightmaps` reads 1 as Lifted, 0 as Original) | Original, Smooth, Lifted | `lightmaps` |
| Focus Blur | `Depth Of Field` | Off, Low, High | `dof` |
| Reflections | `Reflections` | Off, Low, High | `reflections` |
| Light Shafts | `Light Shafts` | Off, On | `shafts` |
| Height Fog | `Height Fog` | Off, On | `hfog` |
| Colour Grade | `Colour Grade` | Off, On | `grade` |
| Edge AA | `Edge Smoothing` | Off, FXAA, High | `edges` |
| Foliage AA | `Foliage AA` | Off, On | `foliage` |
| Tessellation | `Tessellation` | Off, Low, High | `tess` |
| GPU Timing | `GPU Timing` | Off, On | `timing` |
| (file only) | `Exposure` | 0.25..4 | `exposure` |

## Measuring

`gfx timing 1` (or the GPU Timing row) puts a timestamp query after each pass; the times are read back four
frames later (no stall), drawn at the top right over the game and written to the log with each screenshot
(`gpu: 0.43 ms in all: opaque ... bloom ...`). A pass's time is GPU time from the mark before it, so a pass whose
draws the CPU issues slower than the GPU runs them (the scene's own) shows the CPU's pace; the full-screen
passes show the GPU's. Use `--headless` (with `--no-render` most frames are not drawn).

**The GUI pass.** `draw_ui` (gpu.ctx) used to cost more than every 3D effect together, because each run of quads
that shares an image, blend and clip called `stream`, which orphaned the whole 1 MB stream buffer (`buffer_data`)
before uploading a few hundred bytes. Now:

- The stream buffer is a 4 MB ring (`STREAM_RING`, `dev.stream_at`). `stream` appends a draw's vertices after the
  last draw's and returns their byte offset; the buffer is orphaned only when the ring is used up. The upload is
  `map_buffer_range` with WRITE | UNSYNCHRONIZED | INVALIDATE_RANGE on just the new part (nothing in flight reads it;
  it measured 7-12 us faster than `buffer_sub_data` here, and is the way macOS's driver is meant to be fed), with
  `buffer_sub_data` as the fallback when the map fails. GL 4.1 has no base instance, so each draw points its vertex
  attributes at its offset (`aim_quads`, `aim_particles`, `aim_debug`); particles and debug geometry use the ring too.
- `draw_ui` builds a whole step's quads into the scratch (as many as fit), uploads them once, and draws the runs from
  that upload. It sets the image uniform and the scissor only when they change.
- The batching of consecutive quads with the same image, blend and clip was already there (`same_batch`), and draw
  order is untouched: the scenes below are 16-53 draws for 300-900 quads (`ui: N quads in M draws` in the log next to
  `gpu:`), so merging across other runs would save little and could only be done by reordering.

GPU time of the `ui` pass (RTX 4090, headless, `gfx timing 1`, median of 10-12 frames; the apartment on Taris for the
HUD and inventory, the Endar Spire's opening conversation for the dialogue, the main menu):

| Scene | 1080p before | 1080p after | 4K before | 4K after |
|---|---|---|---|---|
| HUD in the apartment (297 quads, 33 draws) | 0.139 ms | 0.012 | 0.139 | 0.015 |
| Inventory (754 quads, 45 draws) | 0.184 (up to 2.4) | 0.014 | 0.223 (up to 1.3) | 0.063 |
| Dialogue reply list (546 quads, 25 draws) | 0.112 (up to 1.1) | 0.003 | 0.099 | 0.007 |
| Main menu (38 quads, 5 draws) | 0.023 | 0.014 | 0.051 | 0.043 |

The other panels (character, abilities, journal, map, options, equip, messages; 313-901 quads in 16-53 draws) went from
0.19-0.40 ms to 0.014-0.05 ms at 1080p. What is left at 4K is fill (the inventory's big panel), not the driver. A
first frame after a panel opens can still show 0.2 ms or a millisecond (textures being made), before and after.

**Checked** with `--screenshot-at` of the same frame before and after, at 1080p and 4K, of the four scenes with
Original Look off and on: 0 pixels differ in all 16 pairs (at 1080p a 1 MB ring, which wraps every 25 frames or so, also gave
0). Headless runs without screenshots every frame can run the CPU ahead of the GPU, so the timing readback (four
frames behind) comes back empty; two screenshots a few frames apart (a readback waits for the GPU) fix that, which
is what the main menu rows used.
