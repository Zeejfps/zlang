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
