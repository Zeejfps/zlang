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

1. The scene into floating-point targets the size of the screen: the light (RGBA16F, unclamped), the view-space
   normal and the share of the light that occlusion may darken (RGB10_A2, a second output of the same draws), depth
   and stencil (a texture). Multisampled twins when Anti-Aliasing is on, resolved by blits. Opaque surfaces write
   both outputs; shadows, transparent surfaces, particles and debug geometry the light alone.
2. (Effects that read depth and normals go between the opaque and the transparent surfaces.)
3. The post chain: bloom, then the composite (exposure, tone curve, grade, a little noise against banding) into
   the screen over the view's viewport. The speed blur (Frame Buffer Effects) follows as before.

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
- **Point lights**: the shadow-casting frame lights (not the sun) that light the casters near the camera's subject
  most (Σ over casters within 12 m of it of (1 − d/r)² × brightness, nearer casters more): 1 low, 3 soft.
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
  (PCSS; a sun of about a degree, a 0.15 m lamp), rotated per pixel. Where no shadow map is drawn (Planar, or no
  sun and no shadow-casting light near), the original's planar shadows are drawn instead.
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

### Depth of field (conversations)

- **Inputs**: `Enhance.dof`; `View.focus` (`distance` along the view, `range` that stays sharp, `blur` 0..1). The
  game sets it (`game/focus.ctx`): while a dialogue camera is up (`dlgview::focus_point`: the speaker's eyes, the
  point the shots frame), the focus is the distance to them; the blur fades in over a third of a second when a
  shot comes up and out when it ends, and a cut to the next speaker pulls focus in about a fifth of a second. In
  normal play there is no focus. Eased every tick, so pictures taken with `--no-render` see the same.
- **What**: after the scene is resolved, before the light shafts and the bloom: at half resolution the light and,
  per pixel, its blur (none within half the range of the focus, growing to the largest one and a half focus
  distances past that; the largest is 1/90 of the picture's height); a gather over a disc as wide as the pixel's
  own blur (24 taps on a spiral, 12 low), each tap counting only if its own blur reaches the pixel, so a sharp
  speaker never smears into the background, and bright taps counting more (high), so highlights open into discs;
  then blended over the full-resolution light as much as each pixel is out of focus. The subtitles and panels are
  drawn after, sharp.
- **Cost**: 0.026 ms at 1280x720 (the Endar Spire, Trask's conversation).
- **Pictures**: `kotor/out/fx/t/talk_dof_cmp.png` (off, high).

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
| Lightmaps | `Smooth Lightmaps` | Original, Smooth | `lightmaps` |
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
