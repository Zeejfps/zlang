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
2. (Effects that read depth and normals go between the opaque and the transparent surfaces: height fog.)
3. The post chain: light shafts, bloom, then the composite (exposure, tone curve, grade, a little noise against banding) into
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
