# An immediate-mode GUI framework in ctxlang: architecture and staged plan

Written 2026-11-23 against worktree `G:\Dev\zlang-worktree-1` (branch `gui-framework`, HEAD `cc3090a8`).
Inputs: `research-ctxlang.md`, `research-zgf.md`, `research-kotor-ui.md` (same scratchpad), plus the
sources they cite where a decision hinged on a claim.

**How to read the evidence marks.**

- **[compiled]**: I compiled and ran a probe with the scratch `CTX_HOME`. The probes are in
  `C:\Users\zeejf\AppData\Local\Temp\claude\613df46367a5c2b2\8a1fe282-b229-4acf-a4f6-415dcf773e73\scratchpad\ctxprobe\`
  (`a1` to `a10` and `spv`; the appendix says what each one shows).
- **[read]**: I read the source myself (not only the report).
- Everything else is design intent. No behaviour of the framework has been run: only the shape of its
  declarations and of code written against them, and that the native libraries can be called.

Nothing in the repository was modified (`git status` is clean), and nothing was installed.

**Decided by the owner.** These are settled and are not among the open decisions:

1. The seam is a limited set of high-level shapes whose purpose is batching: few instance kinds, each
   drawn by its own instanced shader, with textured quads from an atlas as the games path.
2. "Native APIs" are GPU APIs: OpenGL, Vulkan, Metal. Every backend consumes the staged instances.
3. A rectangle has a radius per corner and a border width and colour per side, as ZGF's `DrawRect`.
4. The shaders are ZGF's, ported, not new ones.
5. The core ships no font. The program registers the fonts it wants.
6. Real text is FreeType and HarfBuzz, as `ZGF.Fonts` does it.
7. The library is `ui/` at the top level, namespace `ui`. The SDL host is its own library, and nothing
   under `ui/` adds a `kotor/` directory. A program composes the core and the backend and host it needs.
8. Vulkan was to be the second backend, as a stage. The owner then decided to build OpenGL only ("can we
   just skip vulkan for now and only build opengl?"): stage 14 is excluded from this plan (section 1.2),
   and section 4.4 stays written as the Vulkan backend's specification for when it is taken up, as
   section 4.5 is Metal's. Metal is specified, not staged.
9. Functions, widgets included, have verb names.
10. **The unit is the device pixel, in whole numbers (i32).** Decided after stages 0 to 7 were built in
    fractional logical units, and the code was converted; section 2.0 ("Units") has the rule and its
    reasons, and every later stage is specified on it.
11. **kotor's renderer draws the staged instances itself** (section 8.1). The owner's words: "KOTOR's
    OpenGL backend gains the four ported shaders and the draw loop (about 400 lines, one new entry in
    render's contract). Everything looks the same in KOTOR as on the other backends, and the adapter
    shrinks to a call."
12. **The developer overlay goes into the game**, beside `fxhud` and behind the same option, with
    `fxhud` left in place and untouched, in a commit separate from the adapter (stage 15).

---

## 1. Goals, non-goals, name and location

### 1.1 Goals

1. **A general-purpose immediate-mode GUI library in ctxlang**, for ordinary desktop software (tools,
   editors, applications) as much as for games. The application describes its whole UI every frame,
   widgets return what happened, and there are no retained widget objects or callbacks. The core needs
   std alone.
2. **Rendering behind a seam of a few high-level shapes.** The core emits a list of shapes as plain data
   and never calls a backend. A shared CPU layer stages the list into ZGF's instance kinds (rounded
   rectangle, glyph, image, line), each drawn by one instanced shader ported from ZGF, in batches. A GPU
   backend uploads and draws them: OpenGL, and kotor's renderer with the same shaders; Vulkan and Metal
   are specified, not built.
3. **Real text for applications, glyph tables for games.** A font is either an outline font the program
   loaded (TrueType or OpenType bytes, shaped by HarfBuzz, rasterised by FreeType into the glyph atlas)
   or a glyph table the program built (KOTOR's byte-indexed bitmap fonts).
4. **One layout model for two kinds of UI**: tool and application UI that lays itself out (rows,
   columns, fit, grow), and screens whose every rectangle comes from data (KOTOR's `.gui` files).
5. **Deterministic and testable without a window**: time and input come only from the host, the draw
   list dumps to text for golden files, widgets are addressable by name, and screenshots come from a real
   backend rendering offscreen.
6. **Enough for the KOTOR UI to be rebuilt on it**, shown by one existing screen drawn through the
   framework and compared with the current renderer, and by a developer overlay in the game.

### 1.2 Non-goals, each with its reason

| Left out | Why |
|---|---|
| Rewriting the KOTOR screens | The owner put it outside this plan; one screen is proved (stage 16). |
| Backends on 2D drawing APIs (Direct2D, CoreGraphics) | The owner's "native APIs" are GPU APIs. |
| A Metal backend | It cannot be built or run on this Windows machine. Section 4.5 specifies it from ZGF's Metal backend. |
| A Vulkan backend (stage 14) | The owner's decision: OpenGL only. The Khronos validation layer is not installed on this machine, and a Vulkan backend written without it is wrong in ways that show only on another driver; and nothing consumes a second backend yet. Section 4.4 and stage 14 stay written as its specification for when it is taken up, as section 4.5 is Metal's. |
| Popups, tooltips or dialogs as separate OS windows | A game's UI lives in one surface, and separate windows need a windowing seam on every platform that is larger than the render seam. Popups are a top layer of the one surface. |
| A font rasteriser or shaper written in ctxlang | FreeType and HarfBuzz do both, and ZGF uses them. |
| Bidirectional reordering (ZGF's `Bidi.cs`) | No program in this plan shows right-to-left text. A line that is wholly right-to-left still shapes correctly, because HarfBuzz orders the run; a line that mixes directions is not reordered. The port would be `Bidi.cs` (371 lines) and `ShapeBidi` in the font package, plus caret mapping in the text field. |
| Finding system fonts and fallbacks automatically (ZGF's `SystemFallbackFonts`) | The owner's rule is that the program loads the fonts it wants. The program registers its fallback fonts the same way, in the order to try them. |
| Synthetic bold, OpenType feature selection | No widget asks for either. Bold is a bold face the program registers. |
| Inline display of an IME composition | Committed text arrives and the OS candidate window is placed at the caret. Drawing the composition inside the field is a second editing path (its own caret and underline) with no program here that needs it. |
| Docking, rich text and markdown, web view, multi-line editor, selectable text | No consumer: neither developer tools nor any KOTOR screen needs them. |
| Blur shadows (ZGF's `DrawBoxShadow`) | A fifth instance kind: one more pipeline, instance buffer and upload in each GPU backend, one more kind for the batcher to interleave under every popup, and nothing kotor's renderer could draw. Popups and dialogs are set off by a border and a scrim. ZGF's shadow shader exists to port if the owner wants it. |
| Curves, dashes and line gradients | The ported line shader can draw them, but no widget does, so the seam does not expose them. |
| Gamepad and touch devices | kotor has no gamepad input path [read: only an init constant]. Navigation is already device-neutral (keys and designer links, section 2.5), so a device is a host mapping onto existing events. |
| Painter hooks in the theme (ZGF's `ButtonPainter`) | The way to replace a look is to write a widget over the public primitives. The KOTOR widget set is exactly that. |
| Growing buffers | Fixed capacities are what make every widget call infallible (section 2.10). Overflow is counted and reported. |
| Accessibility bridges (UI Automation, NSAccessibility) | The node list (section 2.5) holds what a bridge would need, but nothing consumes one. |
| Spring and tween animation | `ui::animate` (a rate towards a target) covers tooltips, slides and fades. |

### 1.3 Name and location

A top-level directory `G:\Dev\zlang-worktree-1\ui\`, namespace `ui` (decided).

- `ui` is unused by std and by kotor [read: no `namespace ui` anywhere in `kotor/` or `ctxlang/`]. The
  sketches compile beside `kotor/lib/base` and `kotor/lib/platform` [compiled, a5].
- A context field named `ui` and the namespace `ui` coexist: `fn f { mut ui: ui::Ui }` with
  `ui::add_button{ &ui, .. }` [compiled, a4].
- Library namespaces: `ui_stage`, `ui_fonts`, `ui_gl`, `ui_sdl`, `ui_rec`, `ui_test`, and `ui_vk` in
  the Vulkan specification (section 4.4). On the
  kotor side: `ui_kotor` (adapter) and `kui` (the KOTOR widget set).

---

## 2. Architecture

### 2.0 Units, and the six tensions, decided

**Units (owner's decision): the core works in whole device pixels.**

The first seven stages were built with every coordinate an `f32` in logical units: layout was not
rounded, and emit put each edge on the device grid with `floor(v * scale + 0.5) / scale`, derived sizes
from the snapped edges, and divided back to logical units, which the staged level multiplied up again.
The owner's words on what that cost: "we sometimes have issues with coordinates and things snapping, I
think the conventional wisdom says to keep everything in pixel coordinates? And only use floating points
in some places?" What it cost, concretely:

- A widget's size depended on its position: 10.5 units wide was 11 pixels at x 0 and 10 at x 0.5, so a
  size wobbled while its element scrolled or slid.
- The divide and the later multiply are not exact in `f32`, so "is this edge on the grid" needed a
  tolerance, and the staged level's batching bounds asked exactly that question.
- At a fractional scale borders, gaps and paddings landed between pixels: one side of a box a pixel
  thicker than the opposite one.
- A fractional text width centred in a fractional box moved by a pixel from frame to frame.

The rule that replaces it (Dear ImGui's: positions and sizes are whole pixels at layout, and style
metrics are scaled once):

1. **The unit is the device pixel.** Element rectangles, clips, hit regions, host slots, node rectangles
   and the draw list's rectangle, image and text positions and text sizes are `i32`. Nothing is snapped
   when the frame is emitted and nothing is converted back to logical units anywhere. Ints and floats
   never mix implicitly in ctxlang, so a fractional value reaching layout is a compile error: that is
   the point of `i32` over whole-valued `f32`.
2. **One scale, applied at the input edge.** The host passes the surface's size in pixels and one scale
   (device pixels a logical unit) in `FrameInfo`. What an application declares (theme metrics, `Box`
   sizes, padding, gap, fixed sizes, placed offsets, font sizes, border widths, radii) is written in
   logical units (`f32`) and becomes pixels once, when its element is recorded:

   | What | Rule | Function |
   |---|---|---|
   | a length (size, `min`, `max`, padding, gap, border width, hit outset) | the nearest pixel, a half away from zero, and never 0 unless it is 0: a border of 1 unit is 1 pixel at scales 1 and 1.25 and 2 at 1.5, 1.75 and 2 | `ui::to_pixels{ ui, length } -> i32` |
   | a position (a placed offset) | the nearest pixel, a half up: `floor(v * scale + 0.5)`, which is kotor's `snap`; it may be 0 | `ui::to_pixel_position{ ui, position } -> i32` |
   | a font size | a whole pixel size (the nearest), at least 1: 13 units is 13, 16, 20, 23 and 26 pixels at scales 1, 1.25, 1.5, 1.75 and 2 | `ui::to_font_size{ ui, size } -> i32` |
   | a corner radius, a line's width and end points | scaled, not rounded | `ui::to_pixels_f32{ ui, length } -> f32` |

   A size never depends on a position: the two are converted separately, and the layout works out every
   size before any position.
3. **Declarations are logical, drawing is pixels.** `Box`, `Size`, `Place`, `Insets`, `TextStyle` and
   the theme are logical units. The `paint_*` calls, `ui::draw`, and everything the core answers with
   (`get_rect`, `measure_text`, the pointer, `Interaction.drag_x`, a node's rectangle) are device
   pixels, and only pixels: a widget converts a theme length it paints with by `ui::to_pixels` itself.
   One rule, no second set of paint calls.
4. **Exact pixel placement is first-class.** `ui::place_pixels{ rect }` puts an element on exactly the
   `i32` rectangle given, beside the logical `ui::place`, and `ui::fix_pixels{ size }` is a size in
   pixels. KOTOR's widget set applies the original game's own per-edge snap to its `.gui` design
   coordinates and hands the resulting pixels over (section 3.2).
5. **Integer layout.** Section 2.4: grow shares spare room in whole pixels with the pixels left over
   going one each to the first children; `take` and anchors round down; centring rounds down; `min` and
   `max` hold in pixels.
6. **Text.** A text's size is a whole number of pixels, converted once at record like any other
   length; there is no fractional text size anywhere. A measured width, a line's height and ascent, and
   a caret offset are whole pixels; a line starts on a pixel, and so does every glyph; inside a run the
   pen moves by fractional advances (section 2.7).
7. **What stays `f32`**, because it really is fractional: a line's end points and width, corner radii,
   rotation angles, opacity, colour maths, `animate` values, scroll velocity (an applied scroll offset is
   `i32`), slider-like values in `Values`, uv coordinates, the advances and the pen inside a text run,
   the staged instances (GPU data, built from the `i32` values exactly) and `dt`. Border widths are
   `i32` a side.
8. **Pointer input is device pixels.** The host converts its window system's coordinates (`ui_sdl`
   does); the scripted test driver speaks pixels.
9. **The draw list carries the surface's size in pixels and no scale.** Nothing downstream of the core
   needs the scale: the staged level's canvas is the surface, one unit a pixel, so its flip to y up and
   its batching bounds are exact.

**1. The seam level (owner's decision): a limited set of high-level shapes, staged into ZGF's instance
kinds and drawn by ZGF's shaders.**

*How ZGF's canvases are implemented* [read: `ZGF.Gui/ICanvas.cs`, `ZGF.Gui/RenderedCanvasBase.cs`,
`ZGF.Gui.OpenGL/OpenGlRenderedCanvas.cs` and all of its `canvas_rect`, `canvas_glyph`, `canvas_image`
and `canvas_shape` shaders, `ZGF.Gui.Metal/MetalRenderedCanvas.cs`]:

- `ICanvas` is the shape level: nine draw calls plus clip, opacity and transform stacks.
- `RenderedCanvasBase` is a shared CPU layer. Each draw call is *staged* as one of five plain instance
  structs (`RectInstance`, `GlyphInstance`, `ImageInstance`, `ShadowInstance`, `ShapeInstance`). Opacity
  is multiplied into the colours, edges are snapped to device pixels, and every instance carries an
  index into a per-frame table of at most 256 clips, interned by a linear scan. A clip is a rectangle
  and, optionally, one rounded rectangle.
- `BuildBatches` walks the instances in paint order and appends each to the most recent draw call of its
  own kind (and texture, for images) that it can reach without passing a draw call of another kind whose
  bounds it overlaps. The result paints the same picture as strict order with far fewer draw calls.
- A frame whose staged bytes equal the last frame's skips sorting, uploading and batching.
- A backend only uploads the instance arrays and the clip table and issues the draw calls: one program
  and one vertex array per kind, a unit quad drawn instanced from a base instance, the texture bound per
  image draw. The clip table is a uniform block tested per fragment, so there is no scissor and a clip
  never breaks a batch. The Metal backend is the same with pipelines in place of programs.

The plan keeps that structure, ports the shaders, and cuts the set where a cut has a reason of its own:

| ZGF | Here | Why |
|---|---|---|
| `DrawRect` (radius per corner, border size and colour per side) | **kept as it is**: `rect` | The shader-drawn primitive, with the shader ported unchanged. |
| `DrawCircle` (disc, ring) | **a case of `rect`** | A square with every radius `w / 2`, with or without a border. It then batches with the other rectangles. |
| `DrawLine` | **kept**: `line` with a width, a colour and a cap | ZGF's rectangle shader has no turn, and it is ported unchanged, so a line cannot be a turned rectangle. The stock widgets' marks (check, arrows, cross) are drawn as lines, because there is no built-in font to take them from. Drawn by ZGF's `canvas_shape` shader. |
| `DrawImage` (string id, aspect fit, corner radius, rotation) | **kept**: `image` with an explicit rectangle, a UV region, tint, rotation and corner radius, plus exact quarter turns and a blend | The games primitive. Aspect fit belongs to layout. Images are numbers, not strings. |
| `DrawText` (shaped) | **kept**: `text`, one run | Staged to one glyph instance per glyph from the atlas, as ZGF does. |
| `DrawGlyphRun` (monospace grid) | dropped | A terminal's primitive; no widget here needs it. |
| `DrawBoxShadow` | dropped | A fifth instance kind: a pipeline, an instance buffer and an upload path in each GPU backend, one more kind for the batcher to interleave, and nothing kotor's renderer could draw. |
| `DrawBezier`, `DrawCubicBezier`, dashes, line gradients | not exposed | The code comes with the ported shape shader, but no widget draws them. |
| `PushClip` as a table index, with the rounded clip | **both kept** | The ported shaders already test both in every kind; the rounded clip costs two more rows in the uniform block. ZGF's rule is kept too: one rounded level at a time. |
| `PushOpacity` | **kept in the core** | Baked into colours at emit, as ZGF bakes it at staging. |
| `PushTranslation`, `PushScale` | dropped | The core has no transforms. The shaders' edge-fading path for off-grid edges stays in the port, but nothing the core draws triggers it: rectangles, image shapes and every glyph of a glyph table (KOTOR's fonts included) are whole pixels, and the path is for unrotated quads only. |
| Z index and sort | dropped | The core emits in paint order, layer by layer. |
| Overlap-aware batching, idle-frame skip | **kept** | The point of the level. |
| Five instance kinds | **four** | `RectInstance`, `GlyphInstance`, `ImageInstance`, `ShapeInstance`, each with ZGF's fields in the order its shader reads them. |
| Y-up canvas space | **kept below the seam only** | The staged instances are in ZGF's canvas space so the shaders port unchanged. The shape list and everything above it are y-down; `stage` flips once. |
| Images by string id, silent clip overflow | dropped | Images are numbers; a full clip table drops the shape and counts it. |

*Glyph and image stay separate kinds*, as in ZGF, because their shaders differ in ways that matter: the
glyph shader reads one channel of coverage from the one glyph atlas and takes its colour from the
instance; the image shader reads RGBA from any texture, clamps to its region, and rounds corners. One
merged kind would be a new shader, which the owner ruled out.

*The games path is the image kind as ZGF has it.* `ImageInstance` already carries what kotor's
`render::Quad` does: rectangle, UV region, tint, rotation about the centre [read: `render.ctx:529`,
`canvas_image.vert.glsl`]. Two things are added, neither in the shader:

- **Additive blend** is a field of the draw, not of the instance. The backend sets the blend state per
  draw, and blend joins the batching key.
- **Quarter turns** are exact at the seam (`quarter`) and become `i_rotation` with a transposed
  rectangle when staged.
- An atlas region crosses the seam as an image number and a UV rectangle, which the `image` shape
  already carries. `ui::Region{ image, uv, width, height }` is the value a sprite or atlas entry is held
  as. kotor's rotated-corner, segmented-edge borders are runs of such images (sketch, section 3.2).
- A UI drawn from one atlas is one draw. A UI drawn from many small textures, as kotor's art is today,
  batches per texture, as kotor's `draw_ui` does now.

*Why the shape list is still what the core emits*, now that no backend draws it directly:

- It is the core's output in the UI's own terms: y down, whole device pixels, text as runs of bytes, a
  rectangle's look as one value. The core therefore needs no atlas, no rasteriser and no font library,
  and stays std-only.
- Golden files of layout and widgets are dumps of this list. They are readable (`text ... "Add"`) and
  stable. A dump of glyph instances would change whenever atlas packing or a font version changed.
- Staging holds state the core must not: the atlas, the glyph cache, the batcher. A program may also
  stage a list that no `Ui` made (kotor's minimap pass).
- It is ZGF's `ICanvas` level, as data instead of an interface, which ctxlang does not have.

**2. Backend selection: the program composes at build time; the core has no backend at all.** Because
the seam is data, the core never dispatches. A program's `build.ctx` adds the core, the widgets, the
staged level, one GPU backend, and the host it needs (section 2.1). Each frame it stages the draw list
and hands the result to the backend's `render`.

- Backends and hosts keep their own namespaces instead of kotor's one shared `gpu` namespace, so two
  can be in one program: the recorder beside OpenGL in the screenshot tests.
- Each backend has a contract file in kotor's manner that pins its function shapes [compiled, a4
  `ui_shapes::check`].
- The single runtime hook is the font provider for outline fonts: a struct of three `fn` values and an
  opaque state pointer, not generic [compiled, a1, a4, a10]. A program that uses only glyph tables has
  no hook at all.

**3. Layout: record, solve, emit (ZGF and Clay), with explicit placement as a first-class sizing mode.**
An element is either in its parent's flow or *placed*: out of flow, at an anchor fraction of the parent
plus an offset, with its own size.

- KOTOR's screens are placed elements throughout: a panel is placed at the centre of the screen, a
  control at its file rectangle inside the panel, each on the pixels kui worked out for it
  (`ui::place_pixels`). The HUD's thirds rule is anchor 0, 0.5 or 1.
- Tool UI uses flow (fit, grow, fixed, part of the parent). Both kinds mix freely in one tree.
- A cursor layout (Dear ImGui) cannot centre, right-align, or draw a background behind content of
  unknown size without a second pass, which is why it was not chosen.
- Interaction is answered from the previous frame's emitted rectangles by id, as ZGF does [read:
  `Ui.cs:455`]. On a static KOTOR screen last frame's rectangles are this frame's.

**4. KOTOR's needs without KOTOR in the framework.** Each need is met by a general feature, and the
KOTOR part lives in kotor:

| KOTOR need | General feature in `ui` | KOTOR part (in `kotor/lib/kui`) |
|---|---|---|
| Rotated-corner, segmented-edge borders | the `image` shape with a UV region, tint, exact quarter turns, free angle, additive blend; rectangles in whole device pixels, and placement and painting that take pixels as given (`ui::place_pixels`, `ui::paint_image`) | `kui::paint_border` works out each piece's pixels with the original's snap and emits the pieces (sketch, section 3.2) |
| 3D views inside the UI z-order | `ui::add_host_slot`: a `host` shape that ends a UI pass | the screen adds its view after the pass that ends at the slot, then the next pass (section 8.1) |
| Controls addressable by tag | names of id scopes are kept; `ui::find_node{ path }` | TAG is the id name |
| Hover is focus | `PressOpts.focus_on_hover` | kui widgets set it |
| Designer navigation links | `ui::set_links{ id, links }` | from `MOVETO` |
| cp1252 text in byte-indexed fonts | a glyph-table font with `Encoding::bytes` | kotor's fonts register as glyph tables on their own textures |
| Exact wrap and metric rules | `ui::paint_text` draws one run where it is told | kui keeps the original's layout rules and paints line by line |

**5. Language constraints.** All of these are in the compiled sketches unless marked.

- One widget call per statement: the API is statements by design, and containers return a `Scope`
  token closed by `ui::end` (with `defer` where a function returns early) [compiled, a1].
- No default arguments: every widget takes `opts: ui::Opts`, a struct whose fields all have defaults,
  and a call's trailing `..` fills `ui` and `opts` from the caller's own names, so a call is as short as
  `ui::add_label{ text = "Settings", .. }` [compiled, a4 `show_settings`].
- "Unset" versus zero: option fields are optionals with `null` defaults (`padding: ?Insets = null`),
  merged with `ifnull` [compiled, a1].
- Label text is copied into the frame's text arena at the call, because the escape check does not catch
  a stack slice stored through a call.
- Number formatting is the language's: `@fmt(&ui, "{:.1} %", v)` writes into the frame arena through the
  Ui's `#write` functions, which take every format spec (`fmt::Int`, `F32`, `Text`, ...) [compiled: prints
  `Volume 37.5 %`].
- kotor's `math` shadows std's: the core declares the few libm functions it needs itself, `#pure`, in
  its own namespace [compiled, a1; a5 builds beside kotor's `math`].
- `add_sources` is recursive: core, each backend, samples and tests are sibling directories.
- Per-widget state without a GC: plain values in a fixed table keyed by id (section 2.3).
- A block `{ ... }` is a statement of its own (spec section 11, rule 4): a scope whose locals and
  deferred bodies end at its `}`. A container's content can be grouped in one under its `begin`, or
  in its own function when it needs an early `return`. (The probes, a1, predate this: there a bare
  block was rejected.)
- Two libraries in one program may bind the same C symbol, each under its own capability and with its
  own opaque types [compiled, a9], so `ui/sdl`'s SDL binding and kotor's can coexist.

**6. Testing.** The tests' font is a glyph table built in code, every cell 8 by 16, so metrics are fixed
and no font file is committed (section 6.1). The recorder dumps a draw list as text for golden files;
names give stable identity for scripted input; screenshots come from the OpenGL backend with a hidden
window, the way kotor's tools do.

### 2.1 Packages and dependencies

Every row is a directory; `add_sources` takes exactly the ones a program needs.

```
ui/core      namespace ui         values, draw list, font table and text, ids, state, tree, layout,
                                  emit, input, interaction, focus, layers, scrolling    needs: std
ui/widgets   namespace ui         the stock widgets, their marks, the theme             needs: core
ui/stage     namespace ui_stage   draw list -> four instance kinds, clip table, batched draws,
                                  passes, the glyph atlas and glyph cache               needs: core
ui/fonts     namespace ui_fonts   outline fonts: FreeType rasterises, HarfBuzz shapes   needs: core;
                                                                                        links freetype, harfbuzz
ui/shaders   (GLSL, no ctxlang)   ZGF's four shader pairs, one source for OpenGL and (as SPIR-V) Vulkan
ui/gl        namespace ui_gl      OpenGL 4.1 core backend                               needs: core, stage
ui/gl/glsl   namespace ui_gl      the shaders' text (generated), in a directory of its own so kotor's
                                  renderer adds it without the backend's device       needs: nothing
ui/vulkan    namespace ui_vk      Vulkan backend: specified, not built (section 4.4)    needs: core, stage;
                                                                                        links vulkan-1
ui/sdl       namespace ui_sdl     the SDL2 host: its own SDL binding, a window with a GL context (a
                                  Vulkan surface: section 4.4), events -> ui::Event,
                                  requests -> SDL                                       needs: core; links SDL2
ui/record    namespace ui_rec     draw list, staged draws and node list as text         needs: core, stage
ui/test      namespace ui_test    scripted driver and its script reader, the test font,
                                  a PNG writer (the samples add it too)                needs: core, record
ui/tests/support  namespace ui_check  what the `#test` fns share and no program adds:
                                  golden compare, a test's heap, leaving out what the
                                  machine lacks                                         needs: core
ui/samples/gallery   namespace gallery   one UI that shows every widget (no main)       needs: core, widgets
ui/samples/demo_gl                       program: the gallery on OpenGL (demo_vulkan: section 4.4)
ui/samples/tasks                         program: a desktop application
ui/tests/<name>                          `#test` packages run by `ctxc test`, one per area (section 6)

kotor/lib/ui_kotor   namespace ui_kotor  staged passes -> render::Frame, fonts, events      needs: core, stage, kotor render
                                         (kotor's lib/render_gl draws the passes with ui/gl/glsl's shaders)
kotor/lib/kui        namespace kui       the KOTOR widget set and .gui replay               needs: core, kotor gui data
```

A program composes what it needs. The OpenGL demo's build program:

```
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "demo_gl", root = "." }
    build::add_sources{ &b, exe, dir = "../../core" }
    build::add_sources{ &b, exe, dir = "../../widgets" }
    build::add_sources{ &b, exe, dir = "../../stage" }
    build::add_sources{ &b, exe, dir = "../../fonts" }       // only a program that wants outline fonts
    build::add_sources{ &b, exe, dir = "../../gl" }          // the backend it draws with
    build::add_sources{ &b, exe, dir = "../../sdl" }         // the host it runs on
    build::add_sources{ &b, exe, dir = "../gallery" }
    build::link{ &b, exe, lib = "SDL2" }
    build::link{ &b, exe, lib = "freetype" }
    build::link{ &b, exe, lib = "harfbuzz" }
}
```

Rules that keep this true:

- Nothing under `ui/` adds a directory under `kotor/`. `ui/sdl` carries its own SDL binding and
  `ui/test` its own PNG writer (uncompressed, about 100 lines). The duplication is about 450 lines
  against kotor's two files, and it is what lets `ui/` be used without kotor.
- `ui/core` uses std only and never `math::` (kotor shadows it).
- `ui/widgets` calls only the public primitives of section 3.3, never the core's internals. The core's
  internals sit in nested namespaces (`ui::tree`, `ui::layout`, `ui::emit`), so the check is a grep with
  no matches: `grep -rn "ui::\(tree\|layout\|emit\)::" ui/widgets`.
- A backend never depends on a host: `ui_gl::open` takes a function that looks up GL symbols (and
  `ui_vk::open` would take a surface, section 4.4). The host supplies them.
- kotor's rule 2 (no native library beyond SDL2, OpenGL, libc and libm) is untouched: the game adds the
  core, the widgets, the staged level, `ui/gl/glsl` and its own adapter, never `ui/fonts`, and links
  nothing new. Its tool `kotor/tools/uispike` links FreeType and HarfBuzz to draw the gallery in an
  outline font for its comparison with the library's own picture (stage 15).

### 2.2 Frame lifecycle

```
host                                   core
----                                   ----
ui::push_event{ &ui, event } -> bool   queue it; answer "the UI takes this" from last frame's regions
ui::begin_frame{ &ui, frame }          seal input; pick the hot id from last frame's regions; route the
                                       wheel; advance clocks by frame.dt; empty the frame's buffers
(application records widgets)          each call: answer interaction now, append elements and paints
ui::end_frame{ &ui }                   close open scopes; solve; settle scrolls; place popups; emit the
                                       draw list, hit regions and nodes; move focus; sweep state; fill
                                       the requests
ui_stage::stage{ &staged, list, .. }   shapes -> instances, clip table, batched draws; glyphs into the atlas
backend render{ &dev, staged }         uploads and draws; knows nothing of widgets or fonts
ui::take_requests{ &ui }               host applies cursor, text input, clipboard
```

- The application's code runs exactly once per frame.
- A widget is interactive from its second frame, and geometry queries (`ui::get_rect`) return the
  previous frame's rectangles. After `end_frame` the current rectangles are in the draw list, which is
  how a host places a 3D view in the same frame (host slots carry their solved rectangle).
- `push_event` answers per event, which is kotor's contract (`gui::handle_event -> bool`): a pointer
  event is taken when the pointer is over a hit region, a widget holds the pointer, or a modal layer is
  up; a key or text event when a text field has focus or a layer takes keys.

### 2.3 Identity and state

- `type Id = distinct u64`: FNV-1a 64 of (enclosing scope's id, name bytes). Deterministic across runs,
  unlike ZGF's `HashCode.Combine`. Id 0 means anonymous: not hit-testable, not addressable.
- A widget's id name is its label unless `opts.id` is set. `ui::push_id{ name }` and
  `ui::push_key{ key: u64 }` open id scopes (a list row pushes its index or the item's own key).
- The names of open scopes are kept in the frame's text arena, so every identified element has a path
  (`optgameplay/BTN_BACK`, `items/#3/done`). That path is the stable identity for tests and scripts.
- Two elements with one id in a frame are counted in `ui.stats.duplicate_ids` and listed in the
  problems (section 2.11).
- **Application state stays in the application**, passed as `mut` fields: `value = &app.volume`,
  `text = &app.draft`, `open = &app.open`.
- **Widget state** (scroll offset, caret and selection, window position and size, tree node open,
  animation value) is plain data in a fixed table keyed by id:

```
struct Values { f: [6]f32, i: [2]i64 }                     // zero when new
fn load_state { mut ui: Ui, id: Id } -> Values
fn store_state { mut ui: Ui, id: Id, values: Values }
fn keep_state { mut ui: Ui, id: Id }                       // pin while its widget is not recorded (a hidden tab)
fn animate { mut ui: Ui, id: Id, target: f32, rate: f32 } -> f32
```

- State is copied in and out, so nothing holds a pointer into the table and nothing needs a destructor.
  An entry not asked for within `config.state_ttl` frames (default 600) is freed by a sweep every 64
  frames unless pinned.
- Variable-size state exists in one place only: the undo history of the focused text field, a single
  16 KiB ring in the `Ui`, emptied when focus moves. One field is edited at a time, so one ring is
  enough.

### 2.4 Layout

**Record.** Elements go into a flat array in pre-order, linked by indices (`parent`, `first_child`,
`last_child`, `next`), as ZGF's `LayoutTree` does [read: 929 lines of C#]. Paint items
(`ui::paint_rect` and friends) are leaf elements that take no part in layout, so emission is simply
pre-order and a widget chooses what draws over what by the order of its calls.

**Declaration.** `ui::Box` (section 3.3) carries the layout inputs, in logical units; an unset field
takes the widget's default. Every length of a box becomes whole pixels when its element is recorded
(section 2.0, "Units"), and the tree holds pixels only.

| Sizing | Meaning |
|---|---|
| `ui::FIT` | The content's size, clamped to `min..max`. |
| `ui::GROW` | Starts at content size and shares the parent's spare room along the main axis; fills the parent on the cross axis. When the parent is short, grow children shrink towards `min` first. |
| `ui::fix{ size }` | Exactly that size, in logical units. `ui::fix_pixels{ size }` is exactly that many pixels. |
| `ui::take{ part }` | That fraction of the parent's inner size (minus gaps on the main axis), rounded down. |

Plus `padding`, `gap`, `align_x`, `align_y` (start, center, end) for children, `clip`, `opacity`, and
`place` for an element out of the flow:
`top-left = parent.xy + floor(parent.wh * (anchor_x, anchor_y)) + (x, y)`, with the offset rounded to
the nearest pixel. `ui::place{ x, y, w, h }` is the explicit rectangle in logical units, its position
and its size converted separately; `ui::place_pixels{ rect }` is the explicit rectangle in pixels,
taken as it is. A placed element adds nothing to its parent's fitted size.

**Solve**, at `end_frame`, in ZGF's order [read: `LayoutTree.cs:239`], in integer arithmetic on
pixels. Sizes are worked out before any position, so the size of an element never depends on where it
stands.

1. Fit widths, last element to first (children before parents): a leaf's content is its measured text;
   a container's is the sum (main axis) or maximum (cross axis) of its flow children, plus padding and
   gaps.
2. Distribute widths, first to last: resolve `take`, fill cross-axis `grow`, share main-axis spare room
   among grow children equally with each capped at its `max` and the remainder re-shared; when room is
   short, shrink grow children equally towards `min`.
3. Wrap text at the widths now known; ellipsize single-line text marked `Overflow::ellipsis` when it is
   wider than its room at all (both are whole pixels).
4. Fit heights, then distribute heights, the same way.
5. Position, first to last: flow children from the padding edge, offset by the aligned part of the
   spare room (spare never negative), minus the scroll offset; placed children by their anchor.

Where a division leaves a remainder (the rules are the comment at the top of `ui/core/layout.ctx`):

| Where | Rule | Example |
|---|---|---|
| growing | every grow child gets the same whole share of the spare room, and the pixels left over go one each to the first children | 100 pixels among three: 34, 33, 33 |
| a child at its `max` | it stops there, and what it could not take is shared again among the rest, so the children that did not stop all grow by the same amount to the pixel | 101 among a GROW with max 30 and a GROW: 30 and 71 |
| shrinking | every grow child gives the same whole share, and the odd pixels come one each from the last children, so the first are never the smaller ones | three of 40 in 100: 34, 33, 33 |
| `take` | `floor(room * fraction)`, the product made in `f32` so that 0.7 of 100 is 70 | 0.5 of 101: 50 |
| an anchor | `floor(parent size * anchor)` | 0.5 of 101: 50 |
| centring | half the spare room, rounded down: the odd pixel is left after the content | 61 spare: 30 before |
| `min`, `max` | pixels, by the length rule; `min` wins over `max` | |

What a solve leaves for the stages that build on it:

- A box's `content_w` and `content_h` are what its flow children take once every size is final, without
  its padding: their sizes and gaps along its axis, the largest of them across it. A scroll region
  measures its range by them.
- `solve` may run again on the same tree (it starts from what was recorded), and `position` alone is
  enough after only offsets changed (a scroll offset, a layer moved).
- A scroll region needs its size from outside (fixed, `take`, or GROW in a sized parent): fitted, it is
  as large as its content and has nothing to scroll.
- Grow children share the *spare* room, so two that hold different content are not the same width.
- Text is top-aligned in its element; a text's lines are whole line heights apart.

**Emit**, layer by layer (section 2.5), pre-order within a layer:

- Nothing is rounded or converted. The tree is whole pixels, so an element's rectangle goes into the
  draw list as it was solved, and a paint's rectangle and a text's position are moved by their
  element's whole corner. Pieces that meet in layout meet on screen at any scale, because they are the
  same integers. A line's end points are moved the same way and stay fractional.
- An image's rectangle is the one it covers after its quarter turns, which is what kotor's `put_piece`
  takes [read: `draw.ctx:64`].
- A clipping element adds its absolute, already intersected rectangle to the draw list's clip table
  (or finds the equal entry), and every shape under it carries that index. A clipping element with a
  radius also makes its rectangle the entry's rounded rectangle. Elements wholly outside their clip are
  skipped.
- `opacity` multiplies the alpha of every shape in the subtree. No backend is involved.
- Each identified element adds a hit region: its rectangle (grown by `hit_outset`) intersected with the
  clip, in emission order. The topmost region under the pointer is the last one emitted that contains
  it, so "what is drawn on top takes the pointer" is one rule.

**Not in the layout**, each because no widget in the inventory needs it: wrapping of children onto
lines, margins, grid, aspect-ratio sizing, baseline alignment, ZGF's `Shrink` with priorities,
transforms.

### 2.5 Input, focus and navigation

**Events** are the framework's own, backend-neutral (declaration in section 2.8). The host converts
(`ui_sdl::to_event`, `ui_kotor::to_event`) and pushes them between frames. A frame's input is the
events since the last `begin_frame`: pointer position, per-button down, pressed and released, wheel, an
ordered list of key strokes, typed text.

**Hot, active, focus**: the Dear ImGui and ZGF model.

- `hot` is computed once at `begin_frame`: the topmost hit region under the pointer, ignoring regions
  below a modal layer.
- `ui::press{ &ui, id, opts } -> Interaction` is the one behaviour primitive. A left press on the hot
  id makes it `active` (pointer capture). While something is active nothing else is hovered. Release
  gives `clicked` only if the pointer is still over the same id. A widget that is active but not
  recorded for a frame loses capture.
- `Interaction` also reports `entered` (hover began this frame, for a hover sound), `clicks` (multi-click
  count), and `drag_x`, `drag_y` (pointer movement since the press, for sliders, thumbs and splitters).
- `ui::take_wheel{ &ui, id }` gives the wheel to a widget only while the pointer is over it or inside
  it. `ui::take_key{ &ui, key, mods }` consumes a key stroke so later code does not see it.

**Focus.**

- One focused id. A focusable `press` is a tab stop in recording order. Unconsumed Tab and Shift+Tab
  move focus at `end_frame`. Focus is dropped when its owner is not recorded for a frame.
- **Links**: `ui::set_links{ &ui, id, links }` gives a widget up, down, left and right neighbours by id.
  An unconsumed arrow key moves focus along the focused widget's link. This is KOTOR's `MOVETO`, and any
  application may use it.
- **Hover is focus**: with `PressOpts.focus_on_hover` the hovered widget takes focus. The stock widgets
  use `ui.config.hover_focus` (false by default); kui passes true.
- Highlighting a parent with its focused child (KOTOR's `Obj_Parent`) is kui asking
  `ui::is_focused{ ui, id }` for the child and choosing the lit border itself.

**Layers**, back to front: back overlay, the base tree, windows (by last-focused order), modals,
popups, tooltips, front overlay.

- `ui::begin_overlay{ front }` is a full-surface layer with no hit testing, for raw drawing in the
  surface's pixels: world-attached labels, reticles, fades, a software cursor, a drag ghost.
- A modal layer blocks pointer and keys for everything below it and remembers the focus to restore.
- A popup closes on a press outside it or on Escape, and is placed below or beside its anchor, flipped
  and clamped to the surface.
- Layer content is recorded where the code is but emitted with its layer.

**Nodes: what tests and scripts see.** A widget calls
`ui::describe{ &ui, id, role, label, value, flags }`. At emit each described element becomes a
`ui::Node` with its path and solved rectangle. `ui::find_node{ ui, path }` finds one from the last
frame, by full path or by a suffix that matches exactly one node. kotor's `ui clickctl TAG` and
`ui ctl TAG` become `find_node` plus injected events. The list costs a few kilobytes a frame and is
switched by `config.nodes`.

### 2.6 The render seam

The seam has two faces, as ZGF's does: the **shape list** the core emits, and the **staged instances**
the shared CPU layer makes from it, which every backend draws. The declarations below are the code's
(`ui/core/types.ctx`, `ui/stage/types.ctx`); their first form, in `f32` logical units, was compiled in
the probe [compiled, a4].

#### The shape list

Everything in the list is device pixels. Rectangles, text positions, text sizes and border widths are
whole (`i32`); a line's end points and width, corner radii, angles and uv are `f32`.

```
namespace ui {
    struct Rect { x: i32 = 0, y: i32 = 0, w: i32 = 0, h: i32 = 0 }     // device pixels
    struct Color { r: u8 = 0, g: u8 = 0, b: u8 = 0, a: u8 = 255 }      // sRGB, straight alpha
    struct Uv { u0: f32 = 0.0, v0: f32 = 0.0, u1: f32 = 1.0, v1: f32 = 1.0 }
    struct Span { start: u32 = 0, len: u32 = 0 }                       // bytes of DrawList.text
    struct Image { id: u32 = 0, width: i32 = 0, height: i32 = 0 }      // made by a backend, its size in texels; id 0 is none
    struct Font { index: u16 = 0 }                                     // an index into DrawList.fonts
    enum Blend: u8 { alpha, additive }

    // A rectangle's look, as ZGF's DrawRect has it: a radius for each corner (pixels, may be fractional),
    // a border width (whole pixels) and colour for each side.
    struct Corners { top_left: f32 = 0.0, top_right: f32 = 0.0, bottom_right: f32 = 0.0, bottom_left: f32 = 0.0 }
    struct Sides { top: i32 = 0, right: i32 = 0, bottom: i32 = 0, left: i32 = 0 }
    struct SideColors {
        top: Color = Color{ a = 0, .. }, right: Color = Color{ a = 0, .. },
        bottom: Color = Color{ a = 0, .. }, left: Color = Color{ a = 0, .. },
    }
    struct RectStyle {
        fill: Color = Color{ a = 0, .. },
        radius: Corners = Corners{ .. },
        border: Sides = Sides{ .. },
        border_color: SideColors = SideColors{ .. },
    }
    fn round { radius: f32 } -> Corners               // the same radius at every corner
    fn stroke { width: i32 } -> Sides                 // the same width on every side
    fn color_sides { color: Color } -> SideColors     // the same colour on every side
    enum Cap: u8 { round, butt, square }

    union Cmd {
        rect{ rect: Rect, style: RectStyle, clip: u16 },
        image{ rect: Rect, image: Image, uv: Uv, tint: Color, quarter: u8, angle: f32, radius: Corners, blend: Blend, clip: u16 },
        text{ font: Font, size: i32, x: i32, y: i32, text: Span, color: Color, clip: u16 },
        line{ x0: f32, y0: f32, x1: f32, y1: f32, width: f32, color: Color, cap: Cap, clip: u16 },
        host{ slot: u32, rect: Rect },
    }
    // A piece of a picture: how a sprite or an atlas entry is named; its size in texels.
    struct Region { image: Image = Image{ .. }, uv: Uv = Uv{ .. }, width: i32 = 0, height: i32 = 0 }
    // What shapes are cut to: a rectangle, and optionally a rounded rectangle as well (radius 0: none).
    struct Clip { rect: Rect = Rect{ .. }, round: Rect = Rect{ .. }, radius: f32 = 0.0 }

    struct DrawList {
        cmds: []mut Cmd, count: u32,          // in paint order: a later shape draws over an earlier one
        text: []mut u8, text_len: u32,        // what the Spans point into
        fonts: []mut FontDef, font_count: u32,
        clips: []mut Clip, clip_count: u32,   // the clip table; clips[0] is the whole surface
        width: i32, height: i32,              // the surface, in device pixels
        dropped: u32,                         // shapes that did not fit
    }
}
```

| Shape | Meaning |
|---|---|
| `rect` | `rect` filled with `fill` (alpha 0: no fill), each corner rounded by its own radius, each side with its own border width and colour, drawn inside the edge. A disc or ring is a square with every radius `w / 2`. |
| `image` | The part `uv` of `image` over `rect`, multiplied by `tint`, corners rounded by `radius`. `uv` (0, 0) is the picture's top left. `rect` is where the picture ends up after `quarter` counterclockwise quarter turns; `angle` (radians, counterclockwise) then turns it about the rectangle's centre. `blend` is alpha or additive. |
| `text` | One line of `text` in `font` at `size` (the line height wanted, a whole number of pixels) with the line box's top left at the pixel (`x`, `y`). Wrapping and alignment are already done. An outline font is shaped and rasterised at `size`; a glyph table is magnified by `size / height` with each glyph put on whole pixels (section 2.7). |
| `line` | A straight segment `width` thick with the given cap, antialiased at any angle. |
| `host` | A rectangle the host draws itself, in order: shapes before it are under it, shapes after are over it. |

- **Clips are a table**, as in ZGF: each shape names what it is cut to by index. An entry's rectangle
  is absolute and already the intersection of every enclosing clip. Its rounded rectangle, when it has
  one, is that of the nearest enclosing rounded clip (one rounded level at a time: an inner rounded clip
  replaces it, a plain one keeps it) [read: `RenderedCanvasBase.PushClip`]. Equal entries are shared. A
  full table (256) drops the shape and counts it; it never draws unclipped.
- Coordinates are device pixels, y down, origin top left. The list carries the surface's size and no
  scale: nothing below the core needs one. (ZGF and kotor snap each edge when they draw and derive
  sizes from the snapped edges [read: `RenderedCanvasBase.DrawRect`, `draw.ctx:56`]; here nothing is
  left to snap, and a size does not depend on a position.)
- Filtering and wrap are properties of an image, set when the backend creates it.

The draw list is usable without a `Ui`, for a surface with no widgets (kotor's minimap pass into a
render target):

```
namespace ui { namespace draw {
    fn make(S) { realloc: alloc::Fn(S), mut heap: S, cmds: u32, text: u32, clips: u32, fonts: u32 } -> !DrawList
    fn reset { mut list: DrawList, width: i32, height: i32 }      // the surface, in device pixels
    fn add { mut list: DrawList, cmd: Cmd }
    fn add_clip { mut list: DrawList, clip: Clip } -> ?u16        // the entry's index; null when the table is full
    fn add_rect { mut list: DrawList, rect: Rect, style: RectStyle, clip: u16 }
    fn add_image { mut list: DrawList, rect: Rect, region: Region, tint: Color, quarter: u8, angle: f32, radius: Corners, blend: Blend, clip: u16 }
    fn add_line { mut list: DrawList, x0: f32, y0: f32, x1: f32, y1: f32, width: f32, color: Color, cap: Cap, clip: u16 }
    // add_text, add_host: the same pattern
} }
```

#### The staged instances

Each struct is ZGF's, field for field in the order its shader's attributes read them [read: the four
`canvas_*.vert.glsl` files and the structs at the top of `RenderedCanvasBase.cs`].

```
namespace ui_stage {
    // canvas_rect: i_rect, i_borderRadius (tl, tr, br, bl), i_borderSize (top, right, bottom, left), five colours, i_clipIndex.
    struct RectInstance {
        x: f32, y: f32, w: f32, h: f32,
        radius_tl: f32, radius_tr: f32, radius_br: f32, radius_bl: f32,
        border_top: f32, border_right: f32, border_bottom: f32, border_left: f32,
        fill: u32, color_top: u32, color_right: u32, color_bottom: u32, color_left: u32,
        clip: u32,
    }
    // canvas_glyph: i_rect, i_atlasUV (u, v, w, h), i_color, i_clipIndex, i_rotation.
    struct GlyphInstance { x: f32, y: f32, w: f32, h: f32, u: f32, v: f32, uw: f32, vh: f32, color: u32, clip: u32, angle: f32 }
    // canvas_image: i_rect, i_srcUV (u, v, w, h), i_tint, i_clipIndex, i_rotation, i_cornerRadius (tl, tr, br, bl).
    struct ImageInstance {
        x: f32, y: f32, w: f32, h: f32, u: f32, v: f32, uw: f32, vh: f32, tint: u32, clip: u32, angle: f32,
        radius_tl: f32, radius_tr: f32, radius_br: f32, radius_bl: f32,
    }
    // canvas_shape: i_outerRect, i_shapeData, i_shapeData2, i_halfWidth, i_color, i_shapeType, i_clipIndex, i_color2, i_flags.
    struct ShapeInstance {
        x: f32, y: f32, w: f32, h: f32, data: [4]f32, data2: [4]f32,
        half_width: f32, color: u32, kind: u32, clip: u32, color2: u32, flags: u32,
    }
    const SHAPE_LINE: u32 = 2
    // The clip uniform block's three rows for one entry: (left, bottom, right, top), the rounded rectangle, its radius.
    struct ClipSlot { left: f32, bottom: f32, right: f32, top: f32, round_left: f32, round_bottom: f32, round_right: f32, round_top: f32, radius: f32 }
    enum Kind: u8 { rect, glyph, image, shape }
    struct Draw { kind: Kind, first: u32, count: u32, image: u32, blend: ui::Blend }     // image: for an image draw
    struct Pass { first: u32, count: u32, host: bool, slot: u32, rect: ui::Rect }        // draws up to a host slot
    // One byte of coverage a texel, bottom row first, as ZGF's glyph atlas is.
    struct Atlas { pixels: []mut u8, width: u32, height: u32, version: u32, dirty_x0: u32, dirty_y0: u32, dirty_x1: u32, dirty_y1: u32 }
    struct Staged {
        rects: []mut RectInstance, rect_count: u32,
        glyphs: []mut GlyphInstance, glyph_count: u32,
        images: []mut ImageInstance, image_count: u32,
        shapes: []mut ShapeInstance, shape_count: u32,
        clips: []mut ClipSlot, clip_count: u32,
        draws: []mut Draw, draw_count: u32,
        passes: []mut Pass, pass_count: u32,
        atlas: Atlas,
        width: i32, height: i32,    // the canvas in device pixels: u_canvasMetrics is (width, height, width, height)
        revision: u64,          // changes only when the staged bytes differ from the last frame's
        dropped: u32,
    }
    struct Capacity { rects: u32 = 4096, glyphs: u32 = 16384, images: u32 = 16384, shapes: u32 = 2048, draws: u32 = 1024, passes: u32 = 16, atlas_width: u32 = 2048, atlas_height: u32 = 2048 }
    fn make(S) { realloc: alloc::Fn(S), mut heap: S, cap: Capacity } -> !Staged
    fn stage { mut out: Staged, list: *ui::DrawList, provider: ?ui::TextProvider }
}
```

The default capacities for rectangles, glyphs and shapes are ZGF's (`MaxRects` 4096, `MaxGlyphs` 16384,
`MaxShapes` 2048). Images get 16384 instead of ZGF's 1024, because a KOTOR panel is thousands of image
pieces.

What `stage` does with each shape:

- Everything is flipped into ZGF's canvas space (y up, origin bottom left) as it is written. The canvas
  is the surface, one unit a pixel, so the shaders' "logical" and "device" sizes are the same two
  numbers and the flip of a whole-pixel rectangle is exact: the instances are `f32` (they are GPU data)
  holding whole numbers. Colours are packed as ARGB.
- `rect` becomes one `RectInstance`.
- `image` becomes one `ImageInstance`. A quarter turn becomes part of the rotation, with the rectangle
  transposed about its centre for odd turns. The V of the region is flipped, so backends keep images
  top row first.
- `text` in an outline font is shaped by the provider and becomes one `GlyphInstance` per glyph. A
  glyph not yet in the atlas is rasterised into it by the provider. The glyph cache is keyed as ZGF
  keys it: (sized face, glyph index) [read: `FreeTypeFontBackend.MakeKey`].
- `text` in a glyph table whose pixels the program supplied is packed into the atlas once and becomes
  `GlyphInstance`s. In a glyph table that lives on a backend image (KOTOR's fonts) it becomes
  `ImageInstance`s on that image, tinted.
- `line` becomes one `ShapeInstance` of type 2, as `RenderedCanvasBase.DrawLine` builds it: the padded
  bounding rectangle, the two end points, the half width, the cap in the flags.
- `host` ends a pass. Draws never span passes.
- The clip table is converted entry for entry.

**The atlas** is a port of ZGF's `GlyphAtlas` [read: 375 lines]: skyline packing with one texel of
padding, reuse of freed rectangles, a quarantine of four frames before freed space is reused, growth in
height up to a limit with `version` raised when the texture must be made again, and a dirty rectangle
so a backend uploads only what changed. Glyphs are freed when their font is released. When the atlas
is full at its limit, the frame's missing glyphs are counted as dropped, and the cache is emptied at
the end of the frame so the next frame refills it.

**Batching** is ZGF's rule: walking instances in paint order, each joins the most recent draw of its
kind (and, for images, its texture and blend) that it can reach without passing a draw of another kind
whose bounds (clipped, and widened for a rotation) it overlaps. A rectangle's, an image shape's and a
glyph's bounds are exactly their whole-pixel quads, so two that touch never overlap (no unrotated quad
lies between pixels, so the image shader never grows one), and a line's padded box is what its
instance carries. Instances
are then laid out per kind in draw order. A tool UI is a few draws; a KOTOR panel is one draw per
texture it uses.

**What a backend does with a `Staged`:**

1. Skip all uploads when `revision` is unchanged.
2. Upload the four instance arrays and the clip table; upload the atlas's dirty rectangle, or all of it
   when `version` changed.
3. For each pass, for each draw: bind the pipeline of its kind, the atlas for a glyph draw or the
   draw's image for an image draw, the blend, and draw `count` instances from `first` of a unit quad.

#### The shaders

They are ZGF's, kept as GLSL files in `ui/shaders/` and not rewritten. The instance structs above carry
exactly what they read.

| Shader pair (ZGF.Gui.OpenGL/Assets/Shaders) | Lines | Draws |
|---|---|---|
| `canvas_rect.vert.glsl`, `canvas_rect.frag.glsl` | 59 + 172 | `RectInstance` |
| `canvas_glyph.vert.glsl`, `canvas_glyph.frag.glsl` | 38 + 54 | `GlyphInstance` |
| `canvas_image.vert.glsl`, `canvas_image.frag.glsl` | 63 + 83 | `ImageInstance` |
| `canvas_shape.vert.glsl`, `canvas_shape.frag.glsl` | 42 + 192 | `ShapeInstance` |

What I checked in them before deciding to change nothing in their drawing:

- The rectangle shader **already** works out a rounded corner's coverage from the geometry and not from
  screen-space derivatives, and already rebuilds the fragment's position from `gl_FragCoord` so straight
  borders are even at any scale [read: the comments and code of `canvas_rect.frag.glsl`]. Nothing is
  redesigned.
- The image shader already does what the games quad needs: rotation about the centre, a UV region, a
  tint, and sampling clamped to the region [read: `canvas_image.vert.glsl`, `canvas_image.frag.glsl`].
  No field is added to it. It clamps to the region's edge, not to its texel centres, so an atlas keeps
  one texel of padding around each entry, as ZGF's glyph atlas does.
- The rounded clip's coverage uses `fwidth`, in every kind. It is ported as it is.

Deliberate changes, each with its reason:

| Change | Reason | Evidence |
|---|---|---|
| `u_projection` and `u_canvasMetrics` move from two plain uniforms into one `std140` block, the same in all eight files | Vulkan's GLSL does not allow plain non-opaque uniforms. A block is valid in OpenGL 4.1 too, so one source serves both backends. | With only this edit and the next, all eight files compile to SPIR-V with `glslc`, and the same files still validate as OpenGL GLSL 4.10 [compiled, `spv`]. |
| `canvas_rect.frag` flips `gl_FragCoord.y` under `#ifdef VULKAN` | Vulkan counts `gl_FragCoord.y` from the top; the shader assumes the bottom. | Same probe. |
| Explicit `layout(location = N)` on the values passed from vertex to fragment shader | SPIR-V matches them by location. The probe relied on `glslc` numbering them in declaration order, which holds today but is fragile. | Design intent. |
| Additive blend is a state of the draw | ZGF has one blend mode. kotor's art needs additive. No shader changes. | Design intent. |
| The shadow shader is not ported | Section 1.2. | |

`ui/tools/build_shaders` (a script) validates each file as OpenGL GLSL, compiles it to SPIR-V with
`glslc` (so the one source stays valid for Vulkan), and writes the generated data file
`ui/gl/glsl/shaders_glsl.ctx` (the sources as literals, one a line). It has a directory of its own so
that kotor's renderer, which draws staged passes with these shaders (section 8.1), adds the text
without `ui_gl`'s device: there is one text, and no copy to drift. It is committed, so building a
program needs neither tool, in the way `ctxlang/bootstrap/ctxc.windows.c` is committed. The Vulkan
backend, when it is taken up, adds `ui/vulkan/shaders_spv.ctx` (the SPIR-V as byte strings) the same
way (section 4.4). The script's `--check` mode fails when the generated file does not match its source,
and the test runner calls it when `glslc` is present.

### 2.7 Text and fonts

The core ships no font. A program registers each font it wants with `ui::add_font` and names one in the
theme. Text drawn in a font that is not registered is skipped and reported (section 2.11).

```
namespace ui {
    enum Encoding: u8 { utf8, bytes }
    struct Glyph { uv: Uv = Uv{ .. }, width: f32 = 0.0, height: f32 = 0.0, left: f32 = 0.0, top: f32 = 0.0, advance: f32 = 0.0 }
    union FontKind {
        bitmap{ image: Image, glyphs: []Glyph, first: u32, pixels: []u8, pixels_width: u32, pixels_height: u32 },
        outline{ handle: u32 },
    }
    struct FontDef { kind: FontKind, encoding: Encoding, height: f32, ascent: f32 }
    fn add_font { mut ui: Ui, font: FontDef } -> ?Font            // null when the font table is full

    // What serves outline fonts (TrueType, OpenType): line metrics, shaping, and one glyph's coverage.
    struct Opaque {}
    struct LineMetrics { height: f32 = 0.0, ascent: f32 = 0.0 }
    struct Shaped { glyph: u32 = 0, face: u32 = 0, x_offset: f32 = 0.0, y_offset: f32 = 0.0, x_advance: f32 = 0.0, cluster: u32 = 0 }
    struct GlyphBitmap { pixels: []mut u8, width: u32, height: u32, left: i32, top: i32 }
    type MetricsFn = fn{ mut state: Opaque, handle: u32, pixels: u32 } -> LineMetrics
    type ShapeFn = fn{ mut state: Opaque, handle: u32, pixels: u32, text: []u8, out: []mut Shaped } -> usize
    type RasterFn = fn{ mut state: Opaque, face: u32, glyph: u32, mut out: GlyphBitmap } -> bool
    struct TextProvider { state: *mut Opaque, metrics: MetricsFn, shape: ShapeFn, rasterize: RasterFn }
    fn set_provider { mut ui: Ui, provider: TextProvider }

    // A glyph of a glyph table as it is laid out: its quad in whole pixels. `pen` is how far into
    // the run the text starts (0 for a whole text; a text laid out in pieces goes on from there).
    struct Placed { rect: Rect, uv: Uv }
    fn lay_glyphs { font: FontDef, size: i32, x: i32, y: i32, pen: f32, text: []u8, out: []mut Placed } -> usize
    // A line's height and where its baseline lies below its top, in whole pixels.
    struct LineBox { height: i32 = 0, ascent: i32 = 0 }
    fn measure_text { mut ui: Ui, font: Font, size: i32, text: []u8 } -> i32      // rounded up
    fn measure_line { mut ui: Ui, font: Font, size: i32 } -> LineBox
}
```

`Shaped` is ZGF's `ShapedGlyph`: the glyph's index, the sized face it came from (which may be a
fallback), its offsets and advance in device pixels, and the byte offset of its cluster in the text
[read: `ShapedGlyph.cs`].

**Text in whole pixels.** A text's `size` is always a whole number of device pixels (`i32`); a size
written in logical units becomes one with `ui::to_font_size` when its element is recorded (the
nearest pixel, at least 1). There is one rule for every font and every scale, and no flag.

| | Rule |
|---|---|
| inside a run | advances and offsets are fractional (`f32`), as the provider and the glyph table give them: the pen moves by them exactly, because adding rounded advances would drift |
| an outline font | shaped and rasterised at `size` pixels by the provider; nothing is divided by a scale. The staged level puts each glyph's bitmap on the pixel the pen rounds to |
| a glyph table | magnified by exactly `size / height`. Each glyph is put on whole pixels: its left edge at the pen plus its bearing and its top at its offset, each the nearest pixel, and its width and height its own magnified to the nearest pixel, at least 1. So a glyph is the same size wherever it stands, a table drawn at a whole multiple of its height draws texel for pixel, and the same text a pixel over is the same quads a pixel over |
| a measured width, a line's width | the sum of the advances rounded up, so a box as wide as the measure holds the text; a line fits a limit when its rounded-up width is no more than it |
| a line's height and ascent | whole: the height rounded up, the ascent to the nearest pixel, so every baseline is a pixel row |
| a line's position | a whole pixel (`Cmd::text` has `i32` `x`, `y`); a centred line's spare room is halved and rounded down |
| a caret offset | the advances before the caret, to the nearest pixel: offsets never go down, and the last is the measured width or the pixel before it |

**Outline fonts (`outline`): ordinary software.** The package `ui/fonts` is designed after `ZGF.Fonts`
[read: `FreeTypeFontBackend.cs`, `GlyphAtlas.cs`, `ShapedGlyph.cs`, `GlyphRef.cs`,
`GlyphRenderInfo.cs`, `SystemFallbackFonts.cs`]:

```
namespace ui_fonts {
    capability Fonts                 // main receives it; every FreeType and HarfBuzz call takes it
    struct Library { ... }           // FreeType's library, the faces, their sized variants, the shaped-run cache
    struct Face { id: u32 }
    fn open(S) { mut fonts: Fonts, realloc: alloc::Fn(S), mut heap: S, cap: Capacity } -> !Library
    fn add_face { mut lib: Library, data: []u8, index: u32 } -> !Face     // TrueType or OpenType bytes the program loaded and keeps alive
    fn add_fallback { mut lib: Library, face: Face }                      // tried in this order when a face lacks a character
    fn make_font { mut lib: Library, mut ui: ui::Ui, face: Face } -> ?ui::Font     // registers FontKind::outline with the core
    fn get_provider { lib: *mut Library } -> ui::TextProvider
    fn release_face { mut lib: Library, face: Face }
    fn close { mut lib: Library }
}
```

| ZGF.Fonts | `ui/fonts` |
|---|---|
| `LoadFontFromMemory(data, pixelSize)`: a FreeType face over pinned bytes | `add_face`: the program reads the file and passes the bytes. `FT_New_Memory_Face` over them. |
| `GetSizedVariant(font, pixelSize)`: one face per pixel size, each with its own id | The same: a sized variant is made the first time a size is asked for, and its id is the `face` in `Shaped`. Sizes are device pixels (a text's whole pixel size), so text is rasterised at the pixels it is shown at. |
| `TryGetGlyph`: `FT_Load_Glyph` with `FT_LOAD_RENDER`, `FT_LOAD_NO_BITMAP`, `FT_LOAD_TARGET_NORMAL`; 8-bit coverage into the atlas | `rasterize`: the same call and flags, copied into the caller's buffer. The atlas and the glyph cache live in `ui_stage`, so glyph-table fonts share them. |
| `GetShapedText`: HarfBuzz per run, positions in 26.6 units divided by 64, results cached per font by text in two generations of 256 | `shape`: the same, with the same cache, so measuring and then staging a line shapes it once. |
| `ShapeWithFallback`: the line split into runs by which face covers each character (`FT_Get_Char_Index`), each run shaped by its face | The same, over the faces the program gave `add_fallback`. |
| `ShapeBidi`, `Bidi.cs` | Excluded (section 1.2). |
| `SystemFallbackFonts`, `SystemFonts/*` | Excluded (section 1.2). |
| Emboldened variants, `FontFeatureSet` | Excluded (section 1.2). |
| `GetMetrics`: ascender, descender, line height of the sized face | `metrics`. |

- The core measures a run by shaping it and summing the advances, and rounds the sum up; a text field
  takes its caret positions from the clusters, each to the nearest pixel. The core caches a frame's
  sums by a hash of font, pixel size and bytes.
- The provider's functions get only the opaque state pointer, so the `Library` holds the `Fonts`
  capability itself [compiled, a10].
- **Verified on this machine** [compiled and run, a7]: a ctxlang program read `segoeui.ttf`, FreeType
  rasterised 'A' at 32 pixels (21 by 23, 138 covered pixels, line height 43) and HarfBuzz shaped two
  strings (kerned advances of 78 and 92 pixels). Both libraries are the MSYS2 packages already
  installed (FreeType 2.13.3, HarfBuzz 11.2.1), linked from `build.ctx` with
  `build::link{ lib = "freetype" }` and `"harfbuzz"`.
- FreeType has no accessor functions for a face's glyph slot and size, so the binding mirrors the heads
  of three C structs. Their offsets depend on the size of C's `long` (4 bytes on Windows, 8 elsewhere),
  so the mirrors are per platform, chosen in `build.ctx` as kotor chooses its backend directory. The
  probe's offsets came from a C program compiled against the installed headers.

**Glyph tables (`bitmap`): games, and tests.**

- `glyphs[c - first]` is the glyph of character `c`: its box in the picture, its size in font units, its
  offset from the pen, its advance. `height` is the line height in font units, so a text shape at `size`
  pixels draws at `size / height` pixels a font unit, fractional when the size is not a multiple of the
  height, with every glyph on whole pixels (the rule above). A pixel font drawn at a multiple of its
  height is crisp; at any other size each glyph is stretched to whole pixels, which is what a pixel
  font at a scale of 1.25 can be. There is no option to round the magnification instead: it would draw
  text larger or smaller than the size the layout measured it at.
- The picture is either a backend image (KOTOR's TPC textures), or 8-bit coverage in `pixels` with
  `image.id` 0, which the staged level packs into its atlas.
- **KOTOR fonts.** `ui_kotor::from_font` turns a `render::Font` into a glyph table with
  `Encoding::bytes` and `advance` equal to the glyph width (the original zeroes spacing
  when drawing [read: report 2.6]). kui keeps the original's wrapping, integer line widths and alignment
  rules and calls `ui::paint_text` once per line, so the general wrapping code never has to match the
  original engine. kotor's developer overlay uses the game's own console font this way, as `fxhud` does
  today [read: `fxhud.ctx`].
- **What kotor does with its fonts today** [read: `kotor/lib/gui/draw.ctx`, `text.ctx`,
  `kotor/lib/render/render.ctx:857`]. `lib/gui` lays text out in whole GUI pixels (integer glyph
  widths, integer line positions) and `render::draw_text` draws each glyph quad at its design size in
  GUI pixels; the UI pass then scales GUI pixels to the window by the quarter-step scale. Borders are
  snapped to device pixels piece by piece (`snap`, `put_piece`); text is not snapped at all. So at a
  fractional scale a line that starts at an odd GUI pixel starts half a device pixel in, and a glyph 7
  GUI pixels wide covers 10.5 device pixels. Text drawn through the framework is not made to match
  that. The owner's decision: "It's ok if it's not exact. I'd rather not add a special case if it's not
  good." So KOTOR's fonts follow the one rule above:
  - kui draws a font at its design height times the scale converted to a whole pixel size
    (`ui::scale_font_size`): a font 13 high is 13, 16, 20, 23 and 26 pixels at scales 1, 1.25, 1.5,
    1.75 and 2, where `lib/gui` draws 13, 16.25, 19.5, 22.75 and 26. At 1.25 a line is about 1.5 %
    narrower than the original's, at 1.5 about 2.5 % wider.
  - kui places a line at the pixel the original's snap formula gives its GUI coordinate, and each glyph
    lands on whole pixels, where `lib/gui` leaves glyphs between pixels at fractional scales.
  - So KOTOR text drawn through the framework need not match `lib/gui` pixel for pixel; its borders,
    fills and pictures still must (stage 16).
- **The test font** is a glyph table built in code (section 6.1).

**Where a sample gets a font file.** A sample takes `--font PATH` and otherwise tries a system path for
its platform (`C:\Windows\Fonts\segoeui.ttf`, `/System/Library/Fonts/Helvetica.ttc`,
`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`), reads the bytes with `fs::read_all`, and exits with
a message naming the option when none is found. Nothing font-shaped is committed.

**Encoding.** `bytes`: one byte is one character and indexes the glyph table (KOTOR's cp1252 text).
`utf8`: text is decoded by code point. The encoding also decides how a text field's caret steps in a
glyph table; in an outline font the caret steps by cluster.

**General wrapping** (for stock widgets): break at spaces and after hyphens, split an unbreakable word
at the width; `Overflow::ellipsis` cuts a single line and appends `...`. Widths come from the glyph
table or from the provider, so the same code wraps both kinds.

**Formatting numbers.** `ui::Ui` is an `@fmt` sink: the core has `#write` functions for integers, floats,
byte slices, literals and every format spec (`{:.2}`, `{:>6}`), and `ui::write_fixed{ v, digits, _ }` for a digit count known only at run time. `ui::take_text{ &ui }` returns
the formatted bytes, which live in the frame arena until the next `begin_frame`:

```
_ = @fmt(&ui, "{} of {} done", done, app.count)
ui::add_label{ &ui, text = ui::take_text{ &ui }, opts }          // the nested call is allowed [compiled, a6]
```

### 2.8 The host and platform seam

Everything on the OS side is either input the host pushes or a request the host applies after the
frame. The core calls nothing. Declarations [compiled, a4]:

```
namespace ui {
    enum Key: u8 { none, tab, enter, escape, backspace, delete, left, right, up, down, home, end, page_up, page_down, space, a, c, v, x, y, z, menu,
                   insert, b, d, ... w (every letter), digit_0 ... digit_9, f1 ... f12, minus, equals, plus, comma, period, slash,
                   backslash, semicolon, apostrophe, grave, left_bracket, right_bracket, alt }   // alt: Alt pressed and released alone
    struct Shortcut { key: Key = Key::none, mods: u8 = 0 }
    const MOD_SHIFT: u8 = 1
    const MOD_CTRL: u8 = 2
    const MOD_ALT: u8 = 4
    union Event {
        pointer_move{ x: i32, y: i32 },                    // device pixels
        pointer_button{ button: u8, down: bool, clicks: u8 },
        pointer_leave,
        wheel{ dx: f32, dy: f32 },                         // notches, fractional on a smooth wheel
        key{ key: Key, down: bool, repeat: bool, mods: u8 },
        text{ bytes: [32]u8, len: u8 },                    // committed text, in the focused font's encoding
        paste{ text: []u8 },                               // the host's answer to Requests.paste; copied at the push
        focus{ gained: bool },
    }
    enum Cursor: u8 { arrow, text, hand, resize_h, resize_v, resize_diag, move, hidden }
    struct Requests {
        cursor: Cursor = Cursor::arrow,
        wants_pointer: bool = false, wants_keys: bool = false,
        text_input: bool = false, text_rect: Rect = Rect{ .. },   // turn OS text input on; where the caret is, in device pixels
        copy: []u8 = "", paste: bool = false,                     // set the clipboard; send me a paste event
        animating: bool = false,                                  // something moves with time: draw another frame
        wake: ?f32 = null,                                        // draw a frame this many seconds on (a caret's blink, a tip's delay)
    }
    // The surface in device pixels, device pixels a logical unit, seconds since the last frame.
    struct FrameInfo { width: i32, height: i32, scale: f32, dt: f32 }
}
```

- **DPI and scale.** The host states the surface's size in device pixels and one scale each frame:
  how many device pixels a logical unit is. A tool passes `monitor scale * zoom` (1.5 on a 150 %
  display). The core applies it in one place, when a declaration is recorded (section 2.0, "Units"),
  and holds it to what it can use: a scale that is not a positive number is 1, and it is kept between
  1/64 and 64. kotor passes its quarter-step scale; kui does not rely on it for its own art, whose
  pixels it works out from the design coordinates with the original's snap [read: `draw.ctx:44`,
  `draw.ctx:56`] and places with `ui::place_pixels`.
- **The pointer** arrives in device pixels, and so do the rectangles the core hands back. A host whose
  window system reports points converts them (`ui_sdl::to_event` multiplies by the drawable's pixels a
  window coordinate).
- **Clipboard** is two requests and one event, so no call leaves the core mid-frame: Ctrl+C sets
  `copy`, Ctrl+V sets `paste` and the host answers with `Event::paste` before the next frame.
- **Text input.** `text_input` follows whether a text field has focus (the host calls
  `sdl::set_text_input`), and `text_rect` places the OS candidate window.
- **Time** is `frame.dt` only. The core reads no clock, so a scripted run with fixed `dt` repeats
  exactly.
- **Event-driven hosts** redraw when events arrived, `animating` is set or `wake` seconds have passed
  (`ui::ask_wake`: the soonest a widget asked for; `ui_sdl::get_wait` and `is_frame_due`); a game ignores them and draws
  every frame.
- The test driver is a host with a fake clipboard, which is why the tests need no OS.

### 2.9 Theme

- `ui::Theme` is a plain struct in `ui.theme`, read when each widget is recorded, so assigning a field
  mid-frame changes what comes after. There is no style stack.
- Colours are named by role (ZGF's scheme): `background`, `surface`, `control`, `field`, `accent`,
  `on_accent`, `text`, `text_muted`, `text_disabled`, `border`, `selection`, `focus_ring`, `scrim`,
  `danger`. State colours (`control_hovered`, `control_pressed`, `accent_hovered`) are filled in from
  the base roles by `ui::derive_theme{ theme }` when left at alpha 0.
- Metrics: `font_size`, `gap`, `padding`, `control_height`, `row_height`, `radius`, `border_width`,
  `scrollbar`, `tip_delay`. They are logical units (`f32`): a widget passes them on in a `Box`, which
  the core converts when the element is recorded, and converts the ones it paints with itself
  (`ui::to_pixels`, `ui::to_font_size`).
- `font` is a font the program registered. The theme has no default for it: a program sets
  `ui.theme.font` from what `ui::add_font` or `ui_fonts::make_font` returned.
- `ui::make_dark_theme{}` and `ui::make_light_theme{}` are the two built in.
- One widget's look is changed through `opts.box`: fill, a border width and colour per side, a radius
  per corner, padding, size. A different look altogether is a different widget over the primitives.

### 2.10 Memory

- `ui::make(S){ realloc, &heap, cap }` allocates every buffer once from the caller's allocator. `Ui`
  itself is not generic, so neither is any widget or any user function that takes `mut ui: ui::Ui`
  [compiled, a1 and a4]. This is the pattern of `render::make_frame` [read: `render.ctx:589`].
- `ui::Capacity` has a default for every count: elements 8192, text 256 KiB, shapes 32768, clips 256, hit
  regions 8192, states 2048, nodes 8192, fonts 16, scopes 128, layers 64. About 5 MB at the defaults; a
  program passes smaller or larger numbers.
- The staged level is made the same way (`ui_stage::make`), with its own capacities and the atlas
  (2048 by 2048 bytes to start). The font library allocates through FreeType and HarfBuzz, which use
  the C allocator.
- Per frame nothing is allocated. `begin_frame` resets counts. Hit regions and nodes are kept in two
  buffers that swap, because this frame's interaction reads last frame's.
- Text lives in one frame arena: copies of labels, names of id scopes, formatted text. Slices from
  `take_text` and the `Span`s in the draw list are valid until the next `begin_frame`.
- A text field's text is the application's: `ui::TextBuf{ bytes: []mut u8, len: usize }`, edited in
  place, never reallocated.

### 2.11 Error handling

- Widget calls cannot fail, so there is no `try` on a widget. `ui::make` and a backend's `open` and
  `create_image` return `!T`.
- **Overflow** drops the item and counts it (`ui.stats`, `DrawList.dropped`, `Staged.dropped`), as
  `render::Frame` does.
- **Misuse** is recorded, never a panic: a scope left open at `end_frame` (closed for the caller, and
  counted), `ui::end` with a scope that is not open, a duplicate id, a state table that is full, text
  in a font that was never registered (it is skipped). `ui.problems` holds the first 16 of a frame with
  kind, id and path.
- The tests assert that `stats` shows no drops and `problems` is empty after every frame; the gallery
  shows both in a corner.
- `ui::end{ &ui, scope }` closes that scope and everything opened inside it that is still open, so an
  early `return` between a `begin` and its `end` cannot corrupt the tree (ZGF's depth rule).

---

## 3. API sketch

Both sketches below are compiled and run against stub declarations (real signatures, placeholder
bodies): `ctxprobe/a4/app.ctx` and `ctxprobe/a4/kotor_style.ctx` over `ui_stub.ctx` and `ui_stub2.ctx`
[compiled, a4], and again beside kotor's `lib/base` and `lib/platform` [compiled, a5]. The stub lays
nothing out, so this checks that the API can be written and called in today's ctxlang, not that it
behaves. That was the sketches' first form, in logical units throughout. They are shown here on the
units rule of section 2.0: 3.1 is unchanged but for its host loop (an application declares in logical
units, which is what it did), 3.2 is rewritten for pixel placement, and 3.3 is the surface the code has
after stages 0 to 7 and the conversion.

**Which unit a call takes** is one rule: what *declares* an element (`Box`, `Size`, `Place`, `Insets`,
`TextStyle`, `Opts`, `WindowOpts`, the theme, and so every stock widget's options) is logical units;
what *draws* or *answers* (`paint_*`, `ui::draw`, `get_rect`, `measure_text`, `get_pointer`,
`Interaction`, `Node`) is device pixels. A widget moves between the two with `ui::to_pixels`.

### 3.1 A frame of application code

```
struct Todo { title: [48]u8, len: usize, done: bool }
struct App { open: bool, draft: ui::TextBuf, items: [64]Todo, count: usize, selected: i32, menu_for: i32, volume: f32, dark: bool }

fn show_app { mut ui: ui::Ui, mut app: App } {
    let opts = ui::Opts{ .. }
    let win = ui::begin_window{ &ui, title = "Tasks", open = &app.open, window = ui::WindowOpts{ width = 420.0, height = 560.0, .. }, opts }
    if win.open {
        show_entry{ &ui, &app }
        show_settings{ &ui, &app }
        show_items{ &ui, &app }
        show_item_menu{ &ui, &app }
    }
    ui::end{ &ui, scope = win }
}

// A row: a text field that takes the spare width, and a button.
fn show_entry { mut ui: ui::Ui, mut app: App } {
    let opts = ui::Opts{ .. }
    let mut done: usize = 0
    let mut i: usize = 0
    while i < app.count {
        if app.items[i].done { done = done + 1 }
        i = i + 1
    }
    _ = @fmt(&ui, "{} of {} done", done, app.count)
    let summary = ui::take_text{ &ui }
    ui::add_label{ &ui, text = summary, opts }

    let row = ui::begin_row{ &ui, opts }
    defer ui::end{ &ui, scope = row }
    let entered = ui::add_text_field{
        &ui, label = "draft", text = &app.draft, rules = ui::TextRules{ hint = "What needs doing?", .. },
        opts = ui::Opts{ box = ui::Box{ width = ui::GROW, .. }, .. },
    }
    let add = ui::add_button{ &ui, label = "Add", opts = ui::Opts{ enabled = app.draft.len > 0, tip = "Add the task", .. } }
    if (entered or add) and app.draft.len > 0 and app.count < 64 {
        let n = if app.draft.len < 48 { app.draft.len } else { 48 }
        slice::copy(u8){ dst = app.items[app.count].title[..n], src = app.draft.bytes[..n] }
        app.items[app.count].len = n
        app.items[app.count].done = false
        app.count = app.count + 1
        app.draft.len = 0
    }
}

// A panel with a checkbox and a slider. `..` fills `ui` and `opts` from this function's own names:
// the short way to write a widget call.
fn show_settings { mut ui: ui::Ui, mut app: App } {
    let opts = ui::Opts{ .. }
    let panel = ui::begin_panel{ .. }
    ui::add_label{ text = "Settings", .. }
    _ = ui::add_checkbox{ label = "Dark mode", value = &app.dark, .. }
    let row = ui::begin_row{ .. }
    _ = @fmt(&ui, "Volume {:.1} %", app.volume * 100.0)
    let text = ui::take_text{ &ui }
    ui::add_label{ text, .. }
    _ = ui::add_slider{ label = "volume", value = &app.volume, range = ui::Range{ step = 0.05, .. }, .. }
    ui::end{ scope = row, .. }
    ui::end{ scope = panel, .. }
}

// A scroll area holding a virtual list: only the rows in view are recorded.
fn show_items { mut ui: ui::Ui, mut app: App } {
    let opts = ui::Opts{ .. }
    let scroll = ui::begin_scroll{ &ui, id = "tasks", opts = ui::Opts{ box = ui::Box{ height = ui::GROW, .. }, .. } }
    let list = ui::begin_list{ &ui, id = "items", count = @as(u32, app.count), row_height = 28.0, opts }
    let mut removed: i32 = -1
    let mut i = list.first
    while i < list.last {
        let item = &app.items[@as(usize, i)]
        let row = ui::begin_list_row{ &ui, list, index = i, selected = app.selected == @as(i32, i) }
        if row.clicked { app.selected = @as(i32, i) }
        if row.context {
            app.menu_for = @as(i32, i)
            ui::open_popup{ &ui, id = "item-menu" }
        }
        _ = ui::add_checkbox{ &ui, label = item.title[..item.len], value = &item.done, opts = ui::Opts{ id = "done", .. } }
        ui::add_spacer{ &ui }
        if ui::add_button{ &ui, label = "x", opts = ui::Opts{ id = "delete", tip = "Delete", .. } } { removed = @as(i32, i) }
        ui::end{ &ui, scope = row.scope }
        i = i + 1
    }
    ui::end{ &ui, scope = list.scope }
    ui::end{ &ui, scope = scroll }
    if removed >= 0 { remove_item{ &app, at = @as(usize, removed) } }
}

// A popup: recorded only while it is open, closed by the item that was picked.
fn show_item_menu { mut ui: ui::Ui, mut app: App } {
    let opts = ui::Opts{ .. }
    let menu = ui::begin_popup{ &ui, id = "item-menu", opts }
    if menu.open and app.menu_for >= 0 {
        let at = @as(usize, app.menu_for)
        if ui::add_menu_item{ &ui, label = "Toggle done", opts } {
            app.items[at].done = not app.items[at].done
            ui::close_popup{ &ui }
        }
        if ui::add_menu_item{ &ui, label = "Delete", opts } {
            remove_item{ &app, at }
            ui::close_popup{ &ui }
        }
    }
    ui::end{ &ui, scope = menu }
}
```

The host loop around it, as the probe's `main` has it:

```
let mut gui = ui::make{ realloc = arena::alloc, &heap, cap = ui::Capacity{ .. } } iferr { return 1 }
// The program registers the fonts it wants; here the tests' glyph table built in code.
let test_font = ui_test::make_test_font{ realloc = arena::alloc, &heap } iferr { return 1 }
gui.theme.font = ui::add_font{ ui = &gui, font = test_font } ifnull { return 1 }
let mut staged = ui_stage::make{ realloc = arena::alloc, &heap, cap = ui_stage::Capacity{ .. } } iferr { return 1 }
// each frame:
let used = ui::push_event{ ui = &gui, event = ui::Event::pointer_move{ x = 60, y = 90 } }      // device pixels
// A surface of 1200 by 900 pixels at 1.5 pixels a logical unit: the UI is laid out as 800 by 600 units.
ui::begin_frame{ ui = &gui, frame = ui::FrameInfo{ width = 1200, height = 900, scale = 1.5, dt = 0.016 } }
show_app{ ui = &gui, &app }
ui::end_frame{ ui = &gui }
let req = ui::take_requests{ ui = &gui }
ui_stage::stage{ out = &staged, list = &gui.draw, provider = null }     // null: glyph tables only
// then: a GPU backend's render{ &dev, staged = &staged }, and the host applies req
```

A program with outline fonts differs in three lines (design intent, with each call's shape compiled in
a4 or a7): it opens a `ui_fonts::Library`, adds a face from bytes it read, sets
`gui.theme.font = ui_fonts::make_font{ &lib, ui = &gui, face }`, and passes
`ui_fonts::get_provider{ lib = &lib }` to `ui::set_provider` and to `stage`.

Two things the sketch shows about writing against this API:

- With `..`, any local that has a widget field's name is passed too (`text`, `label`, `value`). That is
  the language's rule. Library code spells `&ui` and `opts` out; the short form is for application code.
- A container's content may be grouped in a block statement under its `begin`; content that needs
  an early `return` goes in its own function with `defer ui::end{ ... }`, since a `return` leaves
  the function, not the block.

### 3.2 An explicit-rectangle, data-driven screen in KOTOR's manner

`kui` is the KOTOR widget set. Its widgets are written over `ui`'s primitives exactly as the stock
widgets are. Controls come from a table the `.gui` loader filled once; a control's TAG is its id.

kui does not use logical units at all. A `.gui` file's coordinates are the original's design pixels,
and the original puts every piece on the device grid itself: each edge on its own with
`floor(v * scale + 0.5)`, the size the difference of the two snapped edges
[read: `kotor/lib/gui/draw.ctx:56`, `put_piece`]. kui does the same arithmetic in integers and hands
the framework the resulting device pixels: `ui::place_pixels` for elements, the `paint_*` calls for
pieces. The framework neither scales nor rounds them, so a panel lands on exactly the pixels the
original's formula gives. (The sketch was compiled in its first form, in logical units; this form
follows the units rule and is design intent.)

```
namespace kui {
    struct Art { image: ui::Image = ui::Image{ .. }, additive: bool = false }
    struct Border {
        corner: Art = Art{ .. }, edge: Art = Art{ .. }, fill: Art = Art{ .. },
        dimension: i32 = 0, tint: ui::Color = ui::Color{ r = 255, g = 255, b = 255, .. }, pulsing: bool = false,
    }
    struct Control {
        tag: []u8,
        x: i32, y: i32, w: i32, h: i32,                 // design pixels in the panel, as the file has them
        border: Border = Border{ .. }, hilight: Border = Border{ .. }, selected: Border = Border{ .. },
        font: ui::Font = ui::Font{ .. }, font_height: f32 = 16.0,              // the font's own height, in design pixels
        text_color: ui::Color = ui::Color{ r = 0, g = 168, b = 250, .. },
        up: []u8 = "", down: []u8 = "", left: []u8 = "", right: []u8 = "",      // MOVETO, by TAG
    }
    struct Panel { name: []u8, w: i32, h: i32, controls: []Control }
    // `scale` is device pixels a design pixel (the game's quarter-step scale); the screen is in design pixels.
    struct Skin { pulse: f32 = 1.0, lit_text: ui::Color = ui::Color{ r = 250, g = 255, b = 0, .. }, scale: f32 = 1.0, screen_w: i32 = 640, screen_h: i32 = 480 }

    // The original's snap: the device pixel a design coordinate lands on, floor(v * scale + 0.5).
    fn snap { v: i32, scale: f32 } -> i32 {
        return ui::scale_position{ position = @as(f32, v), scale }
    }

    // Where an element's design corner is on the screen. Pieces are snapped in the screen's
    // coordinates, edge by edge, and answered in the element's own pixels, which is what a
    // placement in a parent and a paint in an element take.
    struct Grid { scale: f32, x: i32, y: i32 }
    fn snap_rect { g: Grid, x0: i32, y0: i32, x1: i32, y1: i32 } -> ui::Rect {
        let left = snap{ v = g.x + x0, scale = g.scale }
        let top = snap{ v = g.y + y0, scale = g.scale }
        return ui::Rect{
            x = left - snap{ v = g.x, scale = g.scale }, y = top - snap{ v = g.y, scale = g.scale },
            w = snap{ v = g.x + x1, scale = g.scale } - left, h = snap{ v = g.y + y1, scale = g.scale } - top,
        }
    }

    // The panel's design corner: rigid, centred in the design screen.
    fn get_panel_grid { skin: Skin, panel: *Panel } -> Grid {
        return Grid{ scale = skin.scale, x = (skin.screen_w - panel.w) / 2, y = (skin.screen_h - panel.h) / 2 }
    }

    // The panel: placed on the pixels its design rectangle snaps to, its controls placed in it.
    fn begin_panel { mut ui: ui::Ui, skin: Skin, panel: *Panel } -> ui::Scope {
        let outer = ui::push_id{ &ui, name = panel.name }
        let g = get_panel_grid{ skin, panel }
        let screen = Grid{ scale = skin.scale, x = 0, y = 0 }
        let mut box = ui::place_pixels{ rect = snap_rect{ g = screen, x0 = g.x, y0 = g.y, x1 = g.x + panel.w, y1 = g.y + panel.h } }
        box.clip = true
        _ = ui::begin_element{ &ui, id = ui::make_id{ ui, name = "panel" }, axis = ui::Axis::column, box }
        return outer                                        // ending the id scope ends the element opened inside it
    }

    // CSWGuiBorder's scheme: one corner picture turned four ways, one edge picture in whole segments,
    // then the fill. Every piece is an ordinary image shape, one quad once staged; the quarter turns
    // are exact, and each piece's pixels are the original's: `g` is the control's design corner.
    fn paint_border { mut ui: ui::Ui, skin: Skin, g: Grid, b: Border, w: i32, h: i32 } {
        let tint = mul_alpha{ c = b.tint, a = if b.pulsing { skin.pulse } else { 1.0 } }
        let c = b.dimension
        let uv = ui::Uv{ .. }
        if b.corner.image.id != 0 and c > 0 {
            let blend = if b.corner.additive { ui::Blend::additive } else { ui::Blend::alpha }
            ui::paint_image{ &ui, rect = snap_rect{ g, x0 = 0, y0 = 0, x1 = c, y1 = c }, image = b.corner.image, uv, tint, quarter = 0, angle = 0.0, blend }
            ui::paint_image{ &ui, rect = snap_rect{ g, x0 = 0, y0 = h - c, x1 = c, y1 = h }, image = b.corner.image, uv, tint, quarter = 1, angle = 0.0, blend }
            ui::paint_image{ &ui, rect = snap_rect{ g, x0 = w - c, y0 = h - c, x1 = w, y1 = h }, image = b.corner.image, uv, tint, quarter = 2, angle = 0.0, blend }
            ui::paint_image{ &ui, rect = snap_rect{ g, x0 = w - c, y0 = 0, x1 = w, y1 = c }, image = b.corner.image, uv, tint, quarter = 3, angle = 0.0, blend }
        }
        // ... edge runs (quarter 0 and 2 along the top and bottom, 1 and 3 down the sides) and the fill,
        // each piece through snap_rect, so neighbours share the edge they meet on
    }

    // A button: hover is focus, the hilight border and yellow pulsing text while it has it, MOVETO links.
    fn add_button { mut ui: ui::Ui, skin: Skin, panel: *Panel, tag: []u8, text: []u8 } -> bool {
        let c = find_control{ panel, tag } ifnull { return false }
        let id = ui::make_id{ ui, name = tag }
        let it = ui::press{ &ui, id, opts = ui::PressOpts{ focus_on_hover = true, .. } }
        ui::set_links{ &ui, id, links = ui::Links{ up = link_of{ ui, tag = c.up }, down = link_of{ ui, tag = c.down }, left = link_of{ ui, tag = c.left }, right = link_of{ ui, tag = c.right } } }
        let lit = it.focused or it.hovered
        let in_panel = get_panel_grid{ skin, panel }
        let place = snap_rect{ g = in_panel, x0 = c.x, y0 = c.y, x1 = c.x + c.w, y1 = c.y + c.h }
        let el = ui::begin_element{ &ui, id, axis = ui::Axis::row, box = ui::place_pixels{ rect = place } }
        let g = Grid{ scale = skin.scale, x = in_panel.x + c.x, y = in_panel.y + c.y }
        paint_border{ &ui, skin, g, b = if lit { c.hilight } else { c.border }, w = c.w, h = c.h }
        // The font is drawn at its design height times the scale as a whole pixel size, and the
        // line starts on a whole pixel: its measured width and height are pixels.
        let size = ui::scale_font_size{ size = c.font_height, scale = skin.scale }
        let tw = ui::measure_text{ &ui, font = c.font, size, text }
        let line = ui::measure_line{ &ui, font = c.font, size }
        let color = if lit { mul_alpha{ c = skin.lit_text, a = skin.pulse } } else { c.text_color }
        ui::paint_text{ &ui, font = c.font, size, x = (place.w - tw) / 2, y = (place.h - line.height) / 2, text, color }
        ui::end{ &ui, scope = el }
        return it.clicked
    }

    // A list that scrolls by whole rows, as the original's do: its scroll position is the widget's own
    // state, the wheel is taken only while the pointer is over it, and rows are placed, never flowed.
    fn begin_rows { mut ui: ui::Ui, skin: Skin, panel: *Panel, tag: []u8, count: i32, row_h: i32 } -> ui::List {
        let c = find_control{ panel, tag } ifnull { return ui::List{ scope = ui::Scope{ .. }, first = 0, last = 0 } }
        let id = ui::make_id{ ui, name = tag }
        let mut st = ui::load_state{ &ui, id }
        let visible = @as(i64, c.h / row_h)
        let max = if @as(i64, count) > visible { @as(i64, count) - visible } else { 0 }
        st.i[0] = st.i[0] - @as(i64, ui::take_wheel{ &ui, id })
        if st.i[0] > max { st.i[0] = max }
        if st.i[0] < 0 { st.i[0] = 0 }
        ui::store_state{ &ui, id, values = st }
        ui::describe{ &ui, id, role = ui::Role::list, label = tag, value = @as(f32, st.i[0]), flags = 0 }
        let mut box = ui::place_pixels{ rect = snap_rect{ g = get_panel_grid{ skin, panel }, x0 = c.x, y0 = c.y, x1 = c.x + c.w, y1 = c.y + c.h } }
        box.clip = true
        let scope = ui::begin_element{ &ui, id, axis = ui::Axis::column, box }
        return ui::List{ scope, first = @as(u32, st.i[0]), last = @as(u32, st.i[0] + (if max > 0 { visible } else { @as(i64, count) })) }
    }

    // A 3D view inside the panel's z-order: the host draws it between the UI passes on either side,
    // in the slot's rectangle, which is device pixels.
    fn add_view { mut ui: ui::Ui, skin: Skin, panel: *Panel, tag: []u8, slot: u32 } {
        let c = find_control{ panel, tag } ifnull { return }
        ui::add_host_slot{ &ui, slot, box = ui::place_pixels{ rect = snap_rect{ g = get_panel_grid{ skin, panel }, x0 = c.x, y0 = c.y, x1 = c.x + c.w, y1 = c.y + c.h } } }
    }
}

// The Gameplay options screen: what kotor's tag-keyed glue becomes.
fn show_gameplay_options { mut ui: ui::Ui, skin: kui::Skin, panel: *kui::Panel, mut settings: Settings } -> Action {
    let mut action = Action::none
    let p = kui::begin_panel{ &ui, skin, panel }
    kui::add_label{ &ui, skin, panel, tag = "LBL_TITLE", text = "Gameplay" }
    kui::add_view{ &ui, skin, panel, tag = "LBL_3DVIEW", slot = 1 }
    _ = kui::add_check{ &ui, skin, panel, tag = "CB_AUTOSAVE", value = &settings.autosave }
    if kui::add_button{ &ui, skin, panel, tag = "BTN_DIFFICULTY", text = "Difficulty" } { action = Action::pick_difficulty }
    if kui::add_button{ &ui, skin, panel, tag = "BTN_BACK", text = "Close" } { action = Action::close }
    ui::end{ &ui, scope = p }
    return action
}
```

The host side of a 3D view inside the UI, as the probe's `walk_passes` does it: each run of shapes up
to a `host` shape is one UI pass (a `ui_stage::Pass` once staged), then the host draws its view in the
slot's rectangle.

```
// printed by the probe for the screen above:
//   ui pass: commands 0..1
//   host slot 1 at 340,70
//   ui pass: commands 2..7
```

### 3.3 The rest of the public surface

The first form of these was compiled in the stub [compiled, a4]; the declarations of stages 0 to 7 are
the code's. Common options, all in logical units:

```
struct Insets { left: f32 = 0.0, top: f32 = 0.0, right: f32 = 0.0, bottom: f32 = 0.0 }    // a length a side, logical
fn inset { by: f32 } -> Insets                                  // the same length on every side
struct Size { kind: SizeKind = SizeKind::fit, value: f32 = 0.0, min: f32 = 0.0, max: f32 = NO_LIMIT, pixels: i32 = 0 }
const FIT: Size = Size{ .. }
const GROW: Size = Size{ kind = SizeKind::grow, .. }
fn fix { size: f32 } -> Size                                    // logical units
fn fix_pixels { size: i32 } -> Size                             // exactly that many device pixels
fn take { part: f32 } -> Size
struct Place { anchor_x: f32 = 0.0, anchor_y: f32 = 0.0, x: f32 = 0.0, y: f32 = 0.0 }
struct Box {
    width: ?Size = null, height: ?Size = null,
    padding: ?Insets = null, gap: ?f32 = null,
    align_x: ?Align = null, align_y: ?Align = null,
    fill: ?Color = null, border: ?SideColors = null, border_width: ?Insets = null, radius: ?Corners = null,
    clip: ?bool = null, opacity: ?f32 = null,
    place: ?Place = null,
    pixels: ?Rect = null,                                       // a placement in device pixels; it wins over width, height and place
    hit_outset: ?Insets = null,
}
fn place { x: f32, y: f32, w: f32, h: f32 } -> Box              // logical units
fn place_pixels { rect: Rect } -> Box                           // device pixels, taken as they are
struct Opts { id: []u8 = "", box: Box = Box{ .. }, enabled: bool = true, tip: []u8 = "", tab_stop: bool = true, shortcut: Shortcut = Shortcut{ .. } }
// tab_stop false: Tab passes it by; shortcut: a key that works it (a menu item shows it) when no widget took the key
struct Range { min: f32 = 0.0, max: f32 = 1.0, step: f32 = 0.0, digits: u32 = 2 }
struct TextRules { hint: []u8 = "", max_chars: u32 = 0, password: bool = false, filter: ?fn{ c: u32 } -> bool = null }
struct WindowOpts { x: f32 = 40.0, y: f32 = 40.0, width: f32 = 360.0, height: f32 = 0.0, movable: bool = true, resizable: bool = true, closable: bool = true }
struct TextBuf { bytes: []mut u8, len: usize }
```

A clipping element with a radius clips its children to the rounded shape (the clip table's rounded
entry).

The conversions, which the core applies to every declaration and a widget calls for a length of its
own (the rules are section 2.0's table):

```
fn get_scale { ui: Ui } -> f32                                  // device pixels a logical unit this frame
fn to_pixels { ui: Ui, length: f32 } -> i32                     // a length: nearest pixel, never 0 unless 0
fn to_pixel_position { ui: Ui, position: f32 } -> i32           // a position: nearest pixel
fn to_pixels_f32 { ui: Ui, length: f32 } -> f32                 // a radius, a line: scaled, not rounded
fn to_font_size { ui: Ui, size: f32 } -> i32                    // a whole pixel size, at least 1
fn scale_font_size { size: f32, scale: f32 } -> i32             // the same rule at a scale, for code with no Ui (kui)
fn to_pixel_sides { ui: Ui, insets: Insets } -> Sides
fn to_pixel_corners { ui: Ui, corners: Corners } -> Corners
```

Primitives, which the stock widgets and kui are both built from. Everything a `paint_*` call takes is
device pixels in the open element's own coordinates, and everything the core answers is device pixels:

```
struct Scope { depth: u32 = 0, open: bool = false }
fn make_id { ui: Ui, name: []u8 } -> Id
fn push_id { mut ui: Ui, name: []u8 } -> Scope
fn push_key { mut ui: Ui, key: u64 } -> Scope
fn begin_element { mut ui: Ui, id: Id, axis: Axis, box: Box } -> Scope
fn end { mut ui: Ui, scope: Scope }
fn add_text { mut ui: Ui, text: []u8, style: TextStyle, box: Box }                 // flowed, wrapped or ellipsized
fn add_host_slot { mut ui: Ui, slot: u32, box: Box }
fn paint_rect { mut ui: Ui, rect: Rect, style: RectStyle }                         // relative to the open element; whole pixels
fn paint_image { mut ui: Ui, rect: Rect, image: Image, uv: Uv, tint: Color, quarter: u8, angle: f32, blend: Blend }
fn paint_region { mut ui: Ui, rect: Rect, region: Region, tint: Color }            // a sprite or an atlas entry
fn paint_rounded_image { mut ui: Ui, rect: Rect, region: Region, tint: Color, radius: Corners }
fn paint_text { mut ui: Ui, font: Font, size: i32, x: i32, y: i32, text: []u8, color: Color }   // a whole pixel size and position
fn paint_line { mut ui: Ui, x0: f32, y0: f32, x1: f32, y1: f32, width: f32, color: Color, cap: Cap }   // pixels, may be fractional
enum Icon: u8 { check, cross, arrow_right, arrow_down, arrow_up, arrow_left }
fn paint_icon { mut ui: Ui, icon: Icon, rect: Rect, color: Color }                 // a stock mark, drawn as lines
struct PressOpts { enabled: bool = true, focusable: bool = true, focus_on_hover: bool = false, button: u8 = 0, tab_stop: bool = true }
struct Interaction {
    id: Id,
    hovered: bool = false, entered: bool = false,
    pressed: bool = false, held: bool = false, clicked: bool = false, clicks: u8 = 0,
    focused: bool = false,
    drag_x: i32 = 0, drag_y: i32 = 0,                           // device pixels from where the press was
}
fn press { mut ui: Ui, id: Id, opts: PressOpts } -> Interaction
struct Links { up: ?Id = null, down: ?Id = null, left: ?Id = null, right: ?Id = null }
fn set_links { mut ui: Ui, id: Id, links: Links }
fn set_focus { mut ui: Ui, id: Id }
fn is_focused { ui: Ui, id: Id } -> bool
fn take_wheel { mut ui: Ui, id: Id } -> f32
fn take_key { mut ui: Ui, key: Key, mods: u8 } -> bool
fn get_pointer { ui: Ui } -> Point                                                 // Point{ x: i32, y: i32 }: device pixels
fn get_time { ui: Ui } -> f32
fn get_hover_time { ui: Ui, id: Id } -> f32
fn get_rect { ui: Ui, id: Id } -> ?Rect                                            // last frame's, in device pixels
fn measure_text { mut ui: Ui, font: Font, size: i32, text: []u8 } -> i32           // at a pixel size; whole pixels, rounded up
fn measure_line { mut ui: Ui, font: Font, size: i32 } -> LineBox                   // a line's height and ascent, whole pixels
fn begin_overlay { mut ui: Ui, front: bool } -> Scope
fn begin_modal { mut ui: Ui, id: []u8, opts: Opts } -> Scope
fn describe { mut ui: Ui, id: Id, role: Role, label: []u8, value: f32, flags: u8 }
struct Node { id: Id, role: Role, rect: Rect, flags: u8, value: f32, label: []u8, path: []u8 }
fn find_node { ui: Ui, path: []u8 } -> ?Node
```

How a widget is written on this, in three lines: it declares its element with a `Box` in logical units
(sizes and paddings from the theme go in as they are); for what it paints inside, it takes its pixels
from the core (`ui::to_pixels{ ui, length = ui.theme.padding }`, `measure_text`, last frame's
`get_rect`) and does its arithmetic in integers; and where it centres something it halves the spare
pixels and rounds down, as the layout does. `ui/tests/layout/placed.ctx` (`show_button`, `scale_rect`)
is that pattern in the tests.

**The stock marks need no font and no picture.** A check mark, a cross and the four arrows are each two
round-capped lines scaled to the pixel rectangle they are given, so a checkbox, a tree node, a combo and
a window's close button draw the same with any font the program registered, or with none. Lines are
the one shape that is not on the pixel grid: a mark's end points are fractions of its rectangle. A radio
button's dot and a slider's knob are rectangles with every radius half their size.

**On names.** Every function is a verb or verb phrase (decided): `begin_*` and `end` for containers,
`add_*` for a widget or element that the call adds to this frame's tree, `paint_*` for drawing in the
open element, `take_*` for something consumed, and `make_*`, `push_*`, `set_*`, `get_*`, `find_*`,
`load_*`, `store_*`. `add_` matches `render::add_quad`.

---

## 4. Backends and the host

A backend is an ordinary library with its own namespace that draws a `ui_stage::Staged`. The
conventional shapes (compiled as a contract check in a4):

```
fn open ... -> !Device                                                     // per backend: what it needs to start
fn create_image { mut dev: Device, width: u32, height: u32, rgba: []u8, smooth: bool } -> !ui::Image
fn update_image / free_image
fn render { mut dev: Device, staged: *ui_stage::Staged } -> !
fn read_pixels { mut dev: Device, into: []mut u8 } -> !                    // RGBA8, top row first, for screenshots
```

| Backend | Shaders | Plan |
|---|---|---|
| Recorder | none: writes text | stage 0 (shapes), stage 2 (staged) |
| OpenGL 4.1 core | the four ported pairs, as GLSL | stage 3 |
| Vulkan | the same four pairs, as SPIR-V | specified in 4.4, not staged (the owner's decision) |
| Metal | ZGF's four `.gen.metal` files | specified in 4.5, not staged |
| kotor's renderer (`kotor/lib/render_gl`) | the four ported pairs, from `ui/gl/glsl` | stage 15 (section 8.1) |

### 4.1 Recorder (`ui/record`, `ui_rec`)

Writes a draw list as text, one shape a line, into its own byte sink (with its own `#write` functions,
so numbers are fixed-point and stable), then the clip table and the node list as an indented tree. From
stage 2 it also writes a `Staged`: the draws with their kinds, counts, images and blends, which is how
batching is pinned by golden files. It has no device. The format, in device pixels: what the list holds
as whole pixels is written as an integer (the frame's size, rectangles, text positions and sizes,
border widths) and cannot print a fraction; radii, a line's end points and width, uv and angles are
floats with up to four digits.

```
frame 1200x900
clip 1 24,24 600x450 round 24,24 600x450 r=12
rect 24,24 180x42 fill=30343EFF radius=6,6,0,0 border=2,2,0,2 404552FF,404552FF,00000000,404552FF clip=1
text 36,33 font=0 size=24 E4E7EDFF clip=1 "Add"
image 15,15 48x48 img=3 uv=0,0,1,1 tint=FFFFFFFF quarter=1 angle=0 radius=0,0,0,0 blend=alpha clip=0
line 60.5,90 78,108.25 width=1.5 cap=round E4E7EDFF clip=0
host 1 480,90 420x540
```

### 4.2 OpenGL 4.1 core (`ui/gl`, `ui_gl`)

A port of the structure of ZGF's `OpenGlRenderedCanvas` [read: 560 lines].

- `ui_gl::open{ get_proc, realloc, &heap, ... }` takes a bound function that looks up GL symbols, so
  the backend does not depend on a host. It holds its GL functions in a device-owned capability struct,
  as kotor's `gl::Gl` does [read], which is also ZGF's stated lesson about static GL entry points. Its
  own binding of about 45 functions lives in `ui_gl`.
- Four programs, each with the unit quad and one instance buffer whose attribute layout is the instance
  struct. The clip table and the canvas block are uniform blocks bound by `glUniformBlockBinding`,
  since GLSL 410 has no `binding` qualifier [read: `canvas_rect.frag.glsl`].
- Draws use a base instance where the driver has it and re-point the instance attributes per draw where
  it does not (GL 4.1 on macOS), as ZGF does [read: `OpenGlRenderedCanvas.cs:232`].
- Blending keeps destination alpha as real coverage (separate alpha factors) [read: the same file];
  an additive draw swaps the colour factors.
- The atlas is an R8 texture updated by dirty rectangle; a program's images are RGBA8.
- `ui_gl::render` draws every pass; `ui_gl::render_pass{ &dev, staged, pass }` draws one, for a program
  that draws its own 3D between them.

### 4.3 The SDL host (`ui/sdl`, `ui_sdl`)

Its own library, with its own SDL2 binding (decided). A program that runs on something else writes the
same three things for its platform and uses none of this.

- A window with an OpenGL 4.1 core context (`open_gl_window`, `get_gl_proc`, `swap`). A window with a
  Vulkan surface (`open_vulkan_window`, `get_vulkan_extensions`, `create_vulkan_surface`) belongs to
  the Vulkan specification (section 4.4).
- `to_event{ event, pointer_scale } -> ?ui::Event`: SDL's events as the core's, pointer positions in
  device pixels (SDL's window coordinates times the drawable's pixels a window coordinate, which is 1
  where the program is DPI aware and 2 on a Retina display), keys as `ui::Key`.
- `apply_requests{ &host, requests, pointer_scale }`: the system cursor, text input on and off with
  its rectangle (device pixels, back into window coordinates), the clipboard (set on `copy`, an
  `Event::paste` pushed on `paste`).
- `get_sizes{ zoom } -> Sizes{ width, height, scale, pointer_scale }`: the drawable in device pixels
  and the scale (the monitor's times the zoom), which `make_frame{ sizes, dt }` puts into a
  `ui::FrameInfo`; a clock for `dt`; and a wait-for-event call for programs that draw only when
  something happened.
- About 350 lines, written against SDL2's headers; kotor's `sdl.ctx` shows the binding style [read].

### 4.4 Vulkan (`ui/vulkan`, `ui_vk`): specified, not staged

The owner decided to build OpenGL only ("can we just skip vulkan for now and only build opengl?"), so
stage 14 is excluded from this plan: the Khronos validation layer is not installed on this machine (the
table below), and nothing consumes a second backend yet. What follows is the backend's specification for
when it is taken up, as section 4.5 is Metal's: a second GPU backend, drawing the same `Staged` with the
same shader sources compiled to SPIR-V.

**What is on this machine** [run]:

| Present | |
|---|---|
| The loader | `vulkan-1.dll` 1.4.341 in System32; MSYS2's import library `libvulkan-1.dll.a`. A ctxlang program linked it, made an instance and listed the devices [compiled and run, a8]. |
| A device | NVIDIA GeForce RTX 4090, API 1.4.351, with `VK_KHR_surface` and `VK_KHR_win32_surface`. |
| The shader compiler | `glslc` (shaderc 2025.2), `glslangValidator` and `spirv-cross` in MSYS2. All eight ported shader files compile to SPIR-V [compiled, `spv`]. |
| SDL's Vulkan support | MSYS2's SDL2 import library exports `SDL_Vulkan_CreateSurface`, `SDL_Vulkan_GetInstanceExtensions` and `SDL_Vulkan_GetDrawableSize`. |
| A capture tool | The RenderDoc layer is installed. |

| Missing | What to install |
|---|---|
| The Khronos validation layer (`VK_LAYER_KHRONOS_validation` is not among the layers `vulkaninfo` lists) | MSYS2 package `mingw-w64-x86_64-vulkan-validation-layers`, or the LunarG Vulkan SDK. Stage 14 should not start without it: a Vulkan backend written without validation is wrong in ways that show only on another driver. |
| The Vulkan headers (no `include/vulkan`) | MSYS2 package `mingw-w64-x86_64-vulkan-headers`. ctxlang does not read them; they are the reference the hand-written binding is checked against. |

I installed neither.

**Design.**

- The program makes the instance with the extensions the host asks for, the host makes the surface,
  and `ui_vk::open{ instance, surface, ... }` picks a device and queue family and makes the device, the
  swapchain, one render pass with a colour attachment and no depth, and the framebuffers.
- Five pipelines: rectangle, glyph and shape with alpha blending, image with alpha and image with
  additive blending. Each has two vertex bindings: the unit quad per vertex, the instance struct per
  instance, with attribute formats that match the struct (colours as 32-bit unsigned integers).
- The viewport has a negative height (core since Vulkan 1.1), so ZGF's projection and y-up canvas
  space apply unchanged. `gl_FragCoord` is the one place that differs, handled in the shader source
  (section 2.6).
- Descriptor set 0 holds the canvas block and the clip block, rewritten each frame. Set 1 holds one
  sampled texture: the atlas for glyph draws, or an image for image draws. Each image gets its set when
  it is created.
- Instance buffers are host-visible and stay mapped, one per kind per frame in flight.
- A draw is `vkCmdDraw(6, count, 0, first)`: the first instance is part of core Vulkan, so there is no
  fallback path.
- `ui_vk::render` acquires, draws every pass and presents. `ui_vk::record{ &dev, staged, pass, cmd }`
  records one pass into a command buffer the program owns, inside its render pass, for a program with
  its own Vulkan renderer.
- An offscreen target with readback serves `read_pixels`.
- The swapchain and the offscreen target use a UNORM format, so colours match the OpenGL backend's.
- The binding is hand-written in `ui/vulkan/api.ctx`: about 70 functions and 40 structs.

### 4.5 Metal: specified, not staged

Reason: it cannot be built or tested on this machine. The source to port is ZGF's own Metal backend:

- `ZGF.Gui.Metal/MetalRenderedCanvas.cs` (423 lines), `MetalSharedResources.cs` and
  `MetalImageManager.cs` for the structure: one render pipeline per kind, shared-storage instance
  buffers grown geometrically and bound at encode time, the clip table in a buffer bound to the fragment
  functions, `drawPrimitives:vertexStart:vertexCount:instanceCount:baseInstance:` per draw [read].
- `ZGF.Gui.Metal/Assets/Shaders/canvas_rect.gen.metal`, `canvas_glyph.gen.metal`,
  `canvas_image.gen.metal` and `canvas_shape.gen.metal` for the shaders. They are generated from Slang
  sources that live in ZGF's sandbox repository, so the generated files are what is ported.
  `canvas_shadow.gen.metal` is left out with the shadow.
- ZGF's plan records one open fault in that backend: shared-storage textures fail on Intel and AMD
  Macs. A port inherits it unless it uses managed storage there.
- The Objective-C runtime is called through `objc_msgSend` cast to a typed C function pointer per
  selector. Casting a C function pointer to a typed one and calling it works in ctxlang [compiled and
  run, a2].
- Fonts need nothing new: FreeType and HarfBuzz build on macOS, and the atlas is one R8 `MTLTexture`.

### 4.6 kotor's renderer (`kotor/lib/render_gl`, `kotor/lib/ui_kotor`)

Section 8.1: kotor's OpenGL backend draws a `Staged` with the four ported pairs, through its own GL
binding.

---

## 5. Widget inventory by stage

| Stage | Package | Widgets and primitives |
|---|---|---|
| 5 | core | `begin_element`, `end`, `add_text` (single line), `paint_rect`, `paint_image`, `paint_region`, `paint_rounded_image`, `paint_text`, `paint_line`, `add_host_slot`, `place`, `push_id`, `push_key` |
| 6 | core | flow sizing (`FIT`, `GROW`, `fix`, `take`), alignment, wrapped and ellipsized `add_text` |
| 7 | core | `press`, `take_wheel`, `take_key`, focus and tab order, `set_links`, hover-focus, `load_state`, `store_state`, `keep_state`, `animate`, `describe`, `find_node` |
| 8 | core | `begin_overlay`, `begin_modal`, popup layer, window layer order, tooltip layer, `begin_scroll` with bars, virtual range helper |
| 9 | widgets | `paint_icon` (the stock marks), `add_label`, `add_button`, `add_checkbox`, `add_radio`, `add_slider`, `add_progress`, `add_image`, `add_separator`, `add_spacer`, `begin_row`, `begin_column`, `begin_panel`, `add_tooltip`, the two themes |
| 10 | widgets | `add_text_field` (caret, selection, clipboard, undo, hint, password, filter, maximum length), `add_number` (type or drag) |
| 11 | widgets | `begin_window` (move, resize, collapse, close, bring to front), `begin_popup`, `open_popup`, `close_popup`, `begin_dialog` (modal card), `begin_menu_bar`, `begin_menu`, `add_menu_item`, context menu, `add_combo`, drag and drop (`begin_drag`, `accept_drop`, ghost in the front overlay) |
| 12 | widgets | `begin_list` and `begin_list_row` (virtual, selection, activation), `begin_tree_node`, `begin_tabs` and `begin_tab`, `begin_table` with `begin_table_row` and `next_cell` (fixed and grow columns, header, virtual rows), `add_plot` (line plot of `[]f32`), `add_color_edit` (swatch, channel sliders, hex field) |
| 16 | kui (kotor) | panel placement modes, border painter, label, button, check and toggle, slider, progress, list with prototype rows and scroll bar, text block with the original's wrap rules, 3D view slot, tooltip |

The stock set (stages 9 to 12) is what ordinary desktop software is built from: windows and dialogs,
a menu bar and context menus, text and number entry with selection and the clipboard, lists, trees,
tabs and tables. Rounded panels, tabs rounded on top only, and joined button groups come from the
per-corner radius; separators and underlined tabs from the per-side border. Two samples show the set.
The gallery shows every widget in both themes. The tasks application (stage 13) is a normal desktop
program: a font it loaded, a resizable DPI-aware window, menus, a dialog, and no frames drawn while
idle. kui (stage 16) is the games counterpart: the same primitives with every look taken from textures.

Excluded from the stock set, each with its reason:

- Table column resizing and sorting: the table is for inspectors and logs, which need neither.
- A colour picker square: it needs gradients, which are not in the seam.
- Range slider, segmented control, spinner: no consumer; each is a short composition of the primitives.

---

## 6. Testing

### 6.1 Strategy

Tests are the language's `#test` fns, checked with `@expect` and run by `ctxc test` (ctxlang
spec section 20), each in a process of its own: a failure is one line, `FILE:LINE: fail: NAME:
TEXT: LEFT OP RIGHT`, at the check. They live in a package per area under `ui/tests/<name>/`, a
program whose `build.ctx` adds the directories it tests, `ui/test` and `ui/tests/support`, and links
what they need (SDL2, FreeType, HarfBuzz). They are not beside the code they test: `add_sources`
adds a directory and everything below it, and a test is checked in every build of a program that
has its file, so tests and their helpers inside `ui/core` would be compiled into the samples, kotor
and its tools. One `#test` is one coherent case, named for what it checks; a case run at several
scales or in both themes is a test for each. The shared helpers that take a `Test` or exist only
for tests are `ui/tests/support` (namespace `ui_check`), which no program adds; `ui/test` keeps the
scripted driver, the script reader, the test font and the PNG writer, which the samples use too.

**The test font.** `ui_test::make_test_font` builds a glyph table in code [compiled and run, a4]: 95
cells of 8 by 16 for the printable ASCII characters, each cell's coverage a frame with the character's
bits as marks inside it, so glyphs differ from one another. Every metric is fixed (advance 8, line
height 16), so layout goldens are the same on every machine, and no font file exists anywhere under
`ui/` for the core's tests. Text in it is not readable, which is why screenshots meant to be looked at
use an outline font from stage 4 on.

Four kinds of check:

1. **Unit checks** on pure functions: ids, formatting, wrapping, glyph placement, layout arithmetic,
   atlas packing, batching.
2. **Golden draw dumps.** A test builds a UI, runs frames, and compares `ui_rec`'s text of the draw
   list with a file under `ui/tests/<name>/golden/`. The staged level is pinned the same way: its dump
   lists the draws, so a change that breaks batching shows as a diff. On a mismatch the test prints the
   first differing line both ways and writes `<name>.actual.txt` beside the golden (ignored by git);
   the check is `@expect(&t, ui_check::compare_golden{ ... })`, so the failure's line is the test's.
   `UI_UPDATE_GOLDENS=1` in the environment rewrites the goldens after an intended change (`ctxc test`
   passes a test no arguments, and each test's process inherits the runner's environment); the
   reviewer reads the git diff of the golden files. This pins a widget's look without pixels (ZGF's
   `StockLookTests`).
3. **Scripted interaction** through `ui_test::Driver`, which is a host: it steps frames with a fixed
   `dt`, pushes pointer, key and text events, and addresses widgets by node path
   (`click{ &d, path = "tasks/add" }` finds the node's rectangle from the last frame, then moves,
   presses and releases over three frames). Checks read application state, `find_node` flags and
   values, and the requests (cursor, clipboard, text input).
4. **Screenshots from a real backend.** The OpenGL backend with a hidden window renders a hand-built
   conformance list (every shape, radii and borders that differ per corner and side, a rounded clip,
   lines at angles, quarter turns, additive, text at scales 1, 1.5 and 2) and the gallery to PNG under
   `ui/out/` (ignored by git), written by `ui_test`'s own PNG writer. The implementing agent looks at
   the PNG with the Read tool, as kotor's rule 6 requires. PNGs are not compared byte for byte within
   one backend, because GPUs differ. The conformance check between backends, which ZGF's own plan lists
   as not built, is between `ui_gl` and kotor's renderer: `kotor/tools/uispike --against` counts the
   pixels of the gallery that differ from demo_gl's picture (stage 15). A Vulkan backend would be held
   to the same check (section 4.4).

Every test also asserts, after each frame, that nothing was dropped and no problem was recorded.

**What a machine may lack.** The font tests need a system font and the screenshots an OpenGL window.
`ctxc test` has no skip, and a test that checks nothing fails, so a package whose tests need either
declares its own `#test_main` fn, which finds out what is there and runs std's runner through
`ui_check::run_tests_without`: each test it leaves out gets a line `FILE:LINE: skip: NAME: REASON`,
and the runner's summary counts it as not selected, never as passed. Only a missing font file or a
window SDL cannot open leaves a test out; a failure of `ui_gl` or `ui_fonts` is the test's own.

Rules that keep the tooling honest: no Python in any test path (the driver, the script reader and the
golden compare are ctxlang). The one script that writes ctxlang is the shader embedder, which copies
bytes into data literals and never reads ctxlang.

### 6.2 Commands

From the repository root, in Git Bash (the wrapper builds the compiler on first use):

```
kotor/tools/ctxc test ui/tests/draw                    # stage 0: draw list, recorder, formatting
kotor/tools/ctxc run kotor/tools/uicompat              # stage 0 on: ui's libraries built beside kotor's
kotor/tools/ctxc test ui/tests/text                    # stage 1
kotor/tools/ctxc test ui/tests/stage                   # stage 2: instances, atlas, batching
ui/tools/build_shaders --check                         # stage 3: generated shader files match ui/shaders
kotor/tools/ctxc test ui/tests/shots                   # stages 3 and 4: ui/out/conformance-gl.png, text-gl.png (UI_SHOTS_DIR)
kotor/tools/ctxc test ui/tests/fonts                   # stage 4: FreeType and HarfBuzz (UI_FONT, UI_CJK_FONT)
kotor/tools/ctxc test ui/tests/layout                  # stages 5 and 6
kotor/tools/ctxc test ui/tests/input                   # stage 7
kotor/tools/ctxc test ui/tests/layers                  # stage 8
kotor/tools/ctxc test ui/tests/widgets                 # stages 9 to 12
kotor/tools/ctxc test ui/tests/widgets field_          # only the tests whose names contain a filter
UI_UPDATE_GOLDENS=1 kotor/tools/ctxc test ui/tests/widgets   # rewrite goldens after an intended change
kotor/tools/ctxc run ui/samples/demo_gl                # the gallery, interactive
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --script ui/samples/gallery/tour.txt --shot ui/out/tour.png
kotor/tools/ctxc run ui/samples/tasks                  # stage 13: the desktop application
kotor/tools/ctxc run kotor/tools/uispike -- --headless --out kotor/out/uispike.png   # stage 15: the gallery through kotor's renderer, console font
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --shot ui/out/gallery-basic.png
kotor/tools/ctxc run kotor/tools/uispike -- --headless --font C:/Windows/Fonts/segoeui.ttf --against ui/out/gallery-basic.png   # stage 15: 0 pixels differ
kotor/tools/ctxc run kotor/tools/uiview -- optgameplay --scale 1.5 --out kotor/out/uiview   # stage 16
ui/tools/check                                         # everything: shaders, every package, both tours, uicompat
```

`ui/tools/check` runs the shader check, `ctxc test` on each directory under `ui/tests` with a
`build.ctx`, the two samples' scripted tours (demo_gl's `tour.txt` and tasks' `tour.txt`, headless),
and `kotor/tools/uicompat`, and exits non-zero if any of them failed. It neither lexes nor parses
ctxlang: the tests are found by the compiler. Measured on this machine: the whole check takes about
12 s cached and 25 s from a clean build, of which the tours are about 5 s.

---

## 7. Staged implementation plan

**Conventions for every stage.**

- A stage ends at a commit candidate: it builds, its tests pass, the earlier stages' tests still pass,
  and the agent reports what it ran. The agent does not commit; the owner decides.
- An agent touches only the files its stage lists. Where two stages may run together, the note says
  which files each owns.
- To make that possible, stage 5 creates every core subsystem file with its state struct and its
  `make_*` and `reset_*` functions as empty shells, and `Ui` gets one field per subsystem. Later core
  stages fill in their own file and never edit `ui.ctx`. Stage 9 does the same for the widget tests and
  the gallery pages.
- Model tiers are suggestions: **fable** for the stages where a subtle mistake is expensive, **opus**
  for stateful, geometric or native-library work, **sonnet** for well-specified work with goldens to
  check against.
- **Units, for every stage from 8 on** (section 2.0; stages 0 to 7 were converted to it after they were
  built, and their entries below describe them as they are now):
  - A widget's options and the theme are logical units (`f32`). Pass them on in a `Box` and the core
    converts them; never multiply by the scale yourself and never keep a pixel value in an option.
  - Everything a widget computes, stores per frame, paints with or reads back is device pixels in
    `i32`: rectangles, paint positions, measured text, the pointer, drags, scroll offsets (`scroll_x`,
    `scroll_y` of an element), popup and window positions once placed. Get a pixel from a logical
    length with `ui::to_pixels` (lengths), `ui::to_pixel_position` (offsets) or `ui::to_font_size`.
  - State that must survive a change of scale (a window's position, a split ratio) is kept in logical
    units or as a fraction in `Values.f`, and converted each frame; state that is a scroll offset is
    pixels (`Values.i`), held to its range each frame.
  - Where a widget divides pixels it says who gets the remainder, as the layout does: the first
    children when sharing, rounded down when centring.
  - A golden recorded at a scale other than 1 is in pixels: 16 units at scale 1.5 is 24. Record at
    least one scene of each widget at scale 1.5 and check that every border of it is the same number
    of pixels on all four sides.
  - No test may depend on `f32` tolerances for a rectangle: positions and sizes are compared with `==`.

### Stage 0: the seam, the recorder, the test harness

- **Scope.** Values, `RectStyle`, `Cmd`, `DrawList` with its clip table, `ui::draw::*`, the libm
  externs, small number helpers (min, max, clamp) and the conversions from logical units to pixels
  (`scale_length`, `scale_position`, `scale_font_size`, the held sums), fixed-point and hex number writing, the
  recorder's sink and `write_list`, the golden compare the tests check with, the agent guide, and a
  kotor-side build check.
- **Files.** `ui/AGENTS.md` (rules, commands, layout: this plan's sections 2.1, 6.2 and conventions),
  `ui/PLAN.md` (this plan), `ui/.gitignore` (`/out/`, `*.actual.txt`), `ui/core/types.ctx`,
  `ui/core/draw.ctx`, `ui/core/num.ctx`, `ui/core/format.ctx`, `ui/record/dump.ctx`,
  `ui/tests/support/golden.ctx`, `ui/tests/draw/{build.ctx, main.ctx, golden/list.txt}`, `ui/tools/check`,
  `kotor/tools/uicompat/{build.ctx, main.ctx}`.
- **Acceptance.** `ctxc test ui/tests/draw` passes: a hand-built list with all five shapes and three clips, one
  of them rounded, matches its golden; equal clips share a table entry; the overflow of a 4-shape list
  and of a full clip table is counted; fixed-point writing gives `10`, `0.5`, `-3.25`, `100` for the
  values std prints as `1e+01` and `1e+02`; a length of 1 unit is 1, 1, 2, 2 and 2 pixels at scales 1,
  1.25, 1.5, 1.75 and 2, a length that is not 0 never converts to 0, and a length or a scale that is
  not a number, or a sum past an `i32`, is held and never panics. `kotor/tools/uicompat` builds `ui/core` and `ui/record`
  beside `kotor/lib/base`, `lib/platform`, `lib/render` and `lib/gui` and runs. No `build.ctx` under
  `ui/` names a `kotor` path.
- **Agent.** sonnet, medium effort. **Depends on:** nothing. **Alone.**

### Stage 1: text

- **Scope.** The font table and `add_font`, the provider hook, measuring (glyph tables directly,
  outline fonts through `shape`, with the frame cache), `lay_glyphs` (exact magnification, every glyph
  on whole pixels), whole-pixel widths, line metrics and caret
  offsets, UTF-8 and byte stepping, wrapping into line ranges, ellipsis, the index under a pixel (from
  glyph advances or from clusters), and the test font.
- **Files.** `ui/core/font.ctx`, `ui/core/text.ctx`, `ui/test/font.ctx`,
  `ui/tests/text/{build.ctx, main.ctx, golden/*.txt}`.
- **Acceptance.** In the test font "Hello" measures 40 at size 16 and 80 at size 32; wrap goldens for
  spaces, hyphens, a word longer than the width and explicit newlines; ellipsis; a byte-encoded and a
  UTF-8 glyph table give different caret steps for `é`; the test font's glyphs at size 24 (16 units at
  scale 1.5) are 12 by 24 pixels at every pen position; a table with fractional metrics is magnified
  exactly and its glyphs put on the nearest pixels, its advances of 17.5 measure 18, its caret offsets
  are the nearest pixels, and a line of 20.5 fits 21 pixels and not 20; 13 units at scales 1, 1.25,
  1.5, 1.75 and 2 is a whole pixel size, and at each a text at eight places a pixel apart is the same
  glyph quads moved by exactly the offset. A fake provider (7 pixels a byte, one cluster
  a byte, and a two-byte ligature) measures an outline font, wraps with its widths, gives caret offsets
  that step over the ligature as one, and its line of 21.25 pixels is 22 high. Drawing in a font that
  was never registered is reported, not drawn.
- **Agent.** sonnet, medium effort. **Depends on:** stage 0. **Alone.**

### Stage 2: the staged level

- **Scope.** `ui_stage`: the four instance types, the flip into canvas space, staging of every shape,
  the clip table's conversion, the atlas (a port of ZGF's `GlyphAtlas`), the glyph cache, glyph-table
  pixels packed into the atlas, the overlap-aware batching, passes, the revision, and the recorder's
  dump of a `Staged`. Outline text is exercised with a fake provider that rasterises boxes.
- **Files.** `ui/stage/types.ctx`, `ui/stage/atlas.ctx`, `ui/stage/stage.ctx`, `ui/stage/batch.ctx`,
  `ui/record/staged.ctx`, `ui/tests/stage/{build.ctx, main.ctx, golden/*.txt}`.
- **Acceptance.** Golden dumps for the stage 0 list, with every field of every instance: per-corner
  radii and per-side borders arrive in the shader's order; a rectangle at the top left of a 100-high
  list has canvas y 90; a rounded clip fills all three rows of its slot. 200 buttons side by side (a
  rectangle and a text each) stage to 2 draws. A rectangle recorded between two texts and overlapping
  the first forces a third draw, and the dump shows paint order kept. Pictures from two textures that do
  not overlap stage to 2 draws however they are interleaved; an additive picture gets its own draw. A
  host slot gives two passes and no draw spans them. An odd quarter turn gives a transposed rectangle
  and the right rotation, on half pixels when its sides differ by an odd number, with bounds that are
  still exactly its rectangle. A rectangle's bounds are its rectangle (rectangles and pictures that
  only touch share draws); a glyph of a table with fractional metrics on a backend image is whole
  pixels, so its runs that only touch a picture share a draw. On random lists (rectangles,
  pictures, text in both kinds of table, lines on half pixels, turned pictures) every pair of
  overlapping instances is drawn in paint order. The same list twice gives the same revision; one
  changed colour, or another surface size, gives a new one. A glyph drawn twice is rasterised once; releasing its font frees its atlas space after four
  frames; a full atlas grows and raises `version`; at the limit the missing glyphs are counted and the
  next frame refills. Overflow of each array is counted. The atlas is written as a PNG and looked at.
- **Agent.** opus, high effort. **Depends on:** stage 1. **May run with stage 5** (it owns `ui/stage`,
  `ui/record/staged.ctx` and `ui/tests/stage` only).

### Stage 3: the shaders, the OpenGL backend, the SDL host, first pixels

- **Scope.** The four shader pairs copied from ZGF with the changes section 2.6 lists and no others;
  the script that validates, compiles and embeds them; `ui_gl` (GL subset binding, device, images, the
  four programs, the uniform blocks, `render`, `render_pass`, `read_pixels`); `ui_sdl` (its own SDL
  binding, the window with a GL context, events with the pointer in device pixels, requests, the
  surface's pixel size and scale); `ui_test`'s PNG writer; the screenshot tests with the conformance
  list, which is written in logical units and converted to pixels by the test at each scale, as a
  widget converts.
- **Files.** `ui/shaders/canvas_{rect,glyph,image,shape}.{vert,frag}.glsl`, `ui/tools/build_shaders`,
  `ui/tools/embed_shaders.py`, `ui/gl/api.ctx`, `ui/gl/device.ctx`, `ui/gl/shaders_glsl.ctx`
  (generated; in `ui/gl/glsl/` since stage 15), `ui/gl/contract.ctx`, `ui/sdl/sdl.ctx`, `ui/sdl/host.ctx`, `ui/test/png.ctx`,
  `ui/tests/shots/{build.ctx, main.ctx}`.
- **Acceptance.** The agent shows the `diff` of each shader file against ZGF's: only the listed
  changes. `build_shaders --check` passes. `ui/tests/shots` writes `ui/out/conformance-gl.png` at scales
  1, 1.5 and 2 with a hidden window; the agent looks at each and confirms smooth rounded corners with
  no seam where a corner starts, four different radii on one rectangle, four different border widths
  and colours on one rectangle, a disc and a ring, lines at several angles with each cap, test-font
  glyphs on the pixel grid, nested clips and a rounded clip cutting every kind, the four quarter turns,
  an additive image, and a magnified atlas piece with no bleed. The draw count the device reports equals
  the staged draw count, and a second identical frame uploads nothing. The contract file compiles.
- **Agent.** opus, high effort. **Depends on:** stage 2. **May run with stages 6 and 7** (it owns
  `ui/shaders`, `ui/tools`, `ui/gl`, `ui/sdl`, `ui/test/png.ctx`, `ui/tests/shots`).

### Stage 4: outline fonts with FreeType and HarfBuzz

- **Scope.** `ui_fonts` (section 2.7): the two bindings, the library, faces and sized variants, the
  provider's `metrics`, `shape` (with the shaped-run cache and fallback runs) and `rasterize`; a real
  font in a screenshot.
- **Files.** `ui/fonts/freetype.ctx`, `ui/fonts/harfbuzz.ctx`, `ui/fonts/library.ctx`,
  `ui/fonts/shape.ctx`, `ui/tests/fonts/{build.ctx, main.ctx}`, `ui/tests/shots/text.ctx` and the two
  lines in stage 3's `ui/tests/shots/{build.ctx, main.ctx}` that add and call it.
- **Acceptance.** With a system font (UI_FONT, or the platform's default path; with none the package's
  `#test_main` leaves every test out on a `skip:` line each): a face loads and a start-up check of the mirrored FreeType fields passes
  (units per em and glyph count in range), so wrong offsets fail at once; 'A' rasterises to a non-empty
  bitmap; "AV" is narrower than 'A' plus 'V' in a font with kerning; a second shaping of the same text
  is a cache hit; with a CJK font registered as fallback, a line mixing Latin and CJK comes back as runs
  from two faces; releasing a face frees its glyphs; in the core's walks over the real font a measured
  width is the advances rounded up, caret offsets are whole pixels that never go down and end at the
  measured width or the pixel before it, and no wrapped line is wider than its limit in whole pixels,
  at 16 pixels and at 24 (16 units at scale 1.5). `ui/out/text-gl.png` at scales 1 and 1.5 shows
  proportional, kerned, readable text on the pixel grid, every baseline on a pixel row, and a second
  identical frame uploads no atlas bytes.
- **Agent.** opus, high effort. **Depends on:** stage 3. **May run with stage 8** (it owns `ui/fonts`,
  `ui/tests/fonts`, `ui/tests/shots/text.ctx`).

### Stage 5: the tree, placed layout, emit

- **Scope.** `Ui`, `Capacity`, `make`, `begin_frame` and `end_frame` (without input), ids and scopes,
  element and paint recording with every declared length converted to whole pixels (section 2.0,
  "Units"), placement in logical units and in pixels, layout for fixed sizes and placed elements (flow
  children stacked along the axis with padding and gap), clips into the table (plain and rounded),
  opacity, emission order, hit regions, problems and stats. Shells for the later core subsystems.
- **Files.** `ui/core/ui.ctx`, `ui/core/id.ctx`, `ui/core/tree.ctx`, `ui/core/layout.ctx`,
  `ui/core/emit.ctx`, shells `ui/core/{input,interact,focus,state,nodes,layers,scroll}.ctx`,
  `ui/tests/layout/{build.ctx, main.ctx, placed.ctx, pixels.ctx, golden/*.txt}`.
- **Acceptance.** Goldens: a panel placed at the screen centre with five placed controls; anchors 0,
  0.5 and 1 on a resized parent; nested clips, and a rounded clip inside a plain one and the reverse;
  opacity; paint order (decoration, then paints and children as recorded); a host slot; the same input
  twice gives byte-identical dumps; at scale 1.5 hand-computed cases land on whole pixels by the
  conversion rules (a position at `floor(v * s + 0.5)`, a size as its own length rounded, two pieces
  1 unit wide 2 pixels each and meeting, a border of 1 unit 2 pixels on every side); an unclosed scope
  and a duplicate id are reported and nothing panics; a full element array drops and counts. The
  properties the units rule exists for (`pixels.ctx`), on seeded trees at scales 1, 1.25, 1.5, 1.75
  and 2: a subtree has identical sizes at every pixel offset from 0 to 7 and at logical positions
  between pixels, every edge moving by exactly the offset; scrolling by a pixel moves every edge by
  exactly a pixel; a border is the same number of pixels on all four sides and a padded child is
  inset equally on opposite sides; pieces side by side meet exactly; a pixel placement lands on
  exactly its pixels. A scale of 0, a negative one or NaN is 1; the largest surface and the largest
  rectangles an `i32` can name are held and nothing overflows.
- **Agent.** fable, high effort. **Depends on:** stage 1. **May run with stage 2.**

### Stage 6: flow layout

- **Scope.** The solver of section 2.4, in integer arithmetic on pixels: fit, grow, fix, take, min and
  max, alignment, wrapped text between the width and height passes, ellipsis, shrinking when short,
  and the remainder rules of section 2.4's table.
- **Files.** `ui/core/layout.ctx`, `ui/tests/layout/{flow.ctx, golden/flow-*.txt}`.
- **Acceptance.** Goldens: equal split of three grow children; grow capped by `max` with the remainder
  re-shared; `take` beside `fix`; centre and end alignment on both axes; a fit panel around wrapped
  text; text ellipsized when its row is short; overflow that starts at the start edge; a placed child
  inside a flow parent leaves the parent's size alone; and the cases that exist only in whole pixels
  (`flow-pixels`): 100 pixels among three grow children are 34, 33, 33; 101 among two with one capped
  at 30 are 30 and 71; three of 40 shrunk into 100 are 34, 33, 33; an odd spare is centred rounded
  down; `take` 0.5 of 101 is 50; 100 among seven are 15, 15, 14, 14, 14, 14, 14. On seeded trees at
  five scales the rules hold exactly, with no tolerance: children follow one another exactly the gap
  apart, room that is spare by a single pixel is taken by grow children up to their `max`, solving
  twice gives identical results.
- **Agent.** fable, high effort. **Depends on:** stage 5. **May run with stages 3 and 7** (it owns
  `layout.ctx` and the `flow` test files only).

### Stage 7: input, interaction, focus, state, nodes

- **Scope.** Events and frame input, `push_event`'s answer, hot and active, `press`, wheel and key
  taking, focus, tab order, links, hover-focus, the state table and sweep, `animate`, requests,
  `describe` and `find_node`, the scripted driver.
- **Files.** `ui/core/input.ctx`, `ui/core/interact.ctx`, `ui/core/focus.ctx`, `ui/core/state.ctx`,
  `ui/core/nodes.ctx`, `ui/test/driver.ctx`, `ui/tests/input/{build.ctx, main.ctx}`.
- **Acceptance.** Scripted: a press and release over a primitive-built button gives `clicked` exactly
  once; a release elsewhere gives none; press and release within one frame still clicks; a held widget
  hides hover from others; Tab and Shift+Tab walk recording order; an arrow key follows a link; hover-
  focus moves focus; state survives while asked for, is freed after the TTL and is kept when pinned;
  `push_event` answers true over a region and false over empty space; `find_node` by full path and by
  unique suffix. The pointer is device pixels: at scale 1.5 a spot declared at (10, 10) 100 by 40
  takes the pointer on exactly the pixels (15, 15) to (164, 74), a drag is counted in pixels, and the
  driver clicks a node's centre pixel.
- **Agent.** opus, high effort. **Depends on:** stage 5. **May run with stages 3 and 6.**

### Stage 8: layers and scrolling

- **Scope.** Overlays, modal blocking and focus restore, popup placement and dismissal, window layer
  order, the tooltip layer and hover timing, scroll regions (offset state, bars as placed children,
  wheel routing to the innermost region that can move, one re-solve when a bar appears), the virtual
  range helper.
- **Units.** A scroll offset is whole pixels: `scroll_x`, `scroll_y` of the region's element are `i32`,
  the offset is kept in `Values.i` and held to `0..content - inner` each frame (both are pixels the
  solver left: `content_w`, `content_h` and the element's size less its padding). The wheel arrives in
  notches (`f32`); a region multiplies it by a step in logical units converted with `ui::to_pixels`,
  and a velocity or a remainder of a smooth wheel may stay `f32` in `Values.f` while the applied offset
  is rounded. A thumb's position and length are integer shares of the track (say which pixel a
  remainder goes to), and a thumb drag maps `Interaction.drag_y` pixels to an offset by the ratio,
  rounded to the nearest pixel. A popup is placed in pixels from its anchor's `get_rect` (flipped and
  clamped against the surface's pixel size, `ui.draw.width` and `height`) with `ui::place_pixels`. The
  virtual range helper works in pixels: a row height converted once, the first and last row by integer
  division of the offset.
- **Files.** `ui/core/layers.ctx`, `ui/core/scroll.ctx`, `ui/tests/layers/{build.ctx, main.ctx, golden/*.txt}`.
- **Acceptance.** Goldens of emission order across layers; a modal swallows a click on what is under
  it; a popup at the right edge flips; Escape and an outside press close it; the wheel scrolls the inner
  region until its end and then the outer; a thumb drag moves the offset by the right ratio; a 10,000
  row virtual list records only the rows in view. Scrolling by one pixel moves every edge of the
  content by exactly one pixel and changes no size, at scales 1 and 1.5; an offset past either end is
  held; a bar is the same whole number of pixels thick at every offset.
- **Agent.** opus, high effort. **Depends on:** stages 6 and 7. **May run with stage 4.**

### Stage 9: stock widgets I, the theme, the marks, the gallery

- **Scope.** `Opts`, the theme and its two palettes, `paint_icon`, the stage 9 row of section 5, the
  gallery (page switcher and the first page), the OpenGL demo program with `--font`, `--headless`,
  `--script` and `--shot`, and shells for the later widget test files and gallery pages.
- **Units.** Every widget option and theme metric is logical units and goes into a `Box` as it is. A
  widget's own drawing is pixels: a mark's rectangle is cut from the element's pixel size (last frame's
  `get_rect`, or the same lengths converted with `ui::to_pixels`), a label is centred by integer
  halving of the spare pixels, a slider maps `Interaction.drag_x` pixels over the track's pixel width
  to its value, and a 1-unit separator or border is `ui::to_pixels{ length = 1.0 }` pixels, never a
  literal 1. `paint_icon` takes a pixel `Rect` and draws lines at fractions of it; a line's width is a
  theme length through `ui::to_pixels_f32`. `add_image` sizes a picture by its texel size taken as
  logical units unless the box says otherwise.
- **Files.** `ui/widgets/theme.ctx`, `ui/widgets/opts.ctx`, `ui/widgets/icons.ctx`,
  `ui/widgets/basic.ctx`, `ui/widgets/slider.ctx`, `ui/samples/gallery/{gallery.ctx, page_basic.ctx}`
  plus shells `page_text.ctx`, `page_windows.ctx`, `page_data.ctx`,
  `ui/samples/demo_gl/{build.ctx, main.ctx}`,
  `ui/tests/widgets/{build.ctx, main.ctx, basic.ctx, golden/basic-*.txt}` plus shells `field.ctx`,
  `windows.ctx`, `data.ctx`.
- **Acceptance.** Golden dumps (test font) of each widget at rest, hovered, pressed, focused and
  disabled in both themes; no golden of a widget's mark contains a `text` shape; node snapshots;
  scripted: a click toggles a checkbox, a drag moves a slider by the right amount and respects `step`,
  Enter and Space activate a focused button; the grep of section 2.1 finds no use of core internals;
  one golden of each widget at scale 1.5, in which every border is the same number of pixels on all
  four sides and every rectangle is the size the conversion rules give its declared length; a widget
  recorded at eight positions a pixel apart draws the same shapes moved by exactly the offset;
  `ui/out/gallery-basic.png` in an outline font looked at in both themes, at scales 1 and 1.5.
- **Agent.** sonnet, medium effort. **Depends on:** stages 4 and 8. **Alone.**

### Stage 10: text field

- **Scope.** `add_text_field` and `add_number`: caret, selection by keyboard and pointer, word steps,
  clipboard through requests, the undo ring, horizontal scroll of long text, hint, password, filter,
  maximum length, glyph tables in both encodings and outline fonts by cluster.
- **Units.** The caret, the selection and the field's horizontal scroll are whole pixels: caret offsets
  come from `ui::text::locate_caret` (`i32`, the advances before the caret to the nearest pixel, never
  past the measured width), a click maps the pointer's pixel to an index with `pick_index`, the scroll
  that keeps the caret in view is an `i32` in `Values.i`, the caret is a rectangle
  `ui::to_pixels{ length = 1.0 }` wide, and `set_text_input` gets the caret's rectangle in device
  pixels. The text is drawn at `ui::to_font_size` of the theme's size, and its line box is
  `ui::measure_line`'s whole height.
- **Files.** `ui/widgets/field.ctx`, `ui/samples/gallery/page_text.ctx`,
  `ui/tests/widgets/{field.ctx, golden/field-*.txt}`.
- **Acceptance.** Scripted: type, move, select, delete, cut, copy and paste against the driver's fake
  clipboard; undo and redo; a full buffer refuses input without corrupting; a click places the caret at
  the right character; double-click selects a word; with the fake provider's ligature the caret never
  stops inside a cluster; the requests show text input on with the caret rectangle while focused and
  off after; Enter returns true once.
- **Agent.** opus, high effort. **Depends on:** stage 9. **May run with stages 11 and 12.**

### Stage 11: windows, popups, menus, combo, tooltips, drag and drop

- **Scope.** The stage 11 row of section 5.
- **Units.** `WindowOpts` (position, size) is logical units. A window's position and size are kept as
  state in logical units (`Values.f`), so they survive a change of scale, and become pixels each frame
  through the window's `Box`; a drag adds `Interaction.drag_x` pixels divided by `ui::get_scale` to the
  logical position it had at the press, and the box rounds the result, so a dragged window follows the
  pointer to the pixel and never drifts. Popups, menus and tooltips are placed in pixels from the
  anchor's `get_rect` with `ui::place_pixels`, clamped to the surface's pixel size. The drag threshold
  is `ui.config.drag_start` through `ui::to_pixels`.
- **Files.** `ui/widgets/window.ctx`, `ui/widgets/popup.ctx`, `ui/widgets/menu.ctx`,
  `ui/widgets/drag.ctx`, `ui/samples/gallery/page_windows.ctx`,
  `ui/tests/widgets/{windows.ctx, golden/windows-*.txt}`.
- **Acceptance.** Scripted: drag a window by its title, resize by its corner, collapse, close (the
  `open` flag goes false), click to bring to front (emission order changes); a menu opens, a submenu
  follows the pointer, an item click closes all and returns true once; a combo picks; a tooltip appears
  after `tip_delay` and not before; a drag passes the threshold, the ghost is in the front overlay, and
  the drop target reports the payload.
- **Agent.** opus, medium effort. **Depends on:** stage 9. **May run with stages 10 and 12.**

### Stage 12: lists, trees, tabs, tables, plot, colour

- **Scope.** The stage 12 row of section 5.
- **Units.** `row_height` and column widths are logical options, converted once a frame; a virtual
  list's first and last row come from integer division of the pixel scroll offset by the pixel row
  height, and its spacer is `count * row height` pixels (`ui::fix_pixels`, held by the core at a
  thousand million). Table columns are sized by the layout, so header and rows get the same integer
  widths because they are declared the same. The plot maps values to `f32` pixel points inside its
  element's pixel rectangle: lines are the one shape that is fractional.
- **Files.** `ui/widgets/list.ctx`, `ui/widgets/tree.ctx`, `ui/widgets/tabs.ctx`,
  `ui/widgets/table.ctx`, `ui/widgets/plot.ctx`, `ui/widgets/color.ctx`,
  `ui/samples/gallery/page_data.ctx`, `ui/tests/widgets/{data.ctx, golden/data-*.txt}`.
- **Acceptance.** Scripted: list selection by click and arrow keys, activation by Enter and
  double-click, the selection scrolls into view; a tree node's open state persists and survives a
  hidden tab with `keep_state`; table columns share widths between header and rows; the plot's golden
  is `line` shapes; the colour editor round-trips a hex value.
- **Agent.** sonnet, medium effort. **Depends on:** stage 9. **May run with stages 10 and 11.**

### Stage 13: a desktop application

- **Scope.** The task list of section 3.1 as a normal desktop program: a menu bar, a dialog, a
  resizable DPI-aware window, a font it loads from a path, a fallback font, the clipboard, and a loop
  that draws only when events arrive, `animating` is set or `wake` is due. DPI-aware means: each frame the program
  takes `ui_sdl::get_sizes{ zoom }` (the drawable in pixels, the monitor's scale times its zoom) and
  passes them on with `ui_sdl::make_frame`; nothing in the application mentions pixels.
- **Files.** `ui/samples/tasks/{build.ctx, main.ctx, app.ctx}`.
- **Acceptance.** A scripted run adds, checks and deletes tasks through the menu and the keyboard;
  `ui/out/tasks.png` is looked at, at scales 1, 1.25 and 1.5, and at each every border and separator
  is the same thickness along its length and on every side; the program draws no frame during two
  idle seconds of the script; resizing the window re-lays the content with nothing clipped.
- **Agent.** sonnet, medium effort. **Depends on:** stages 10, 11 and 12. **May run with stage 15.**

### Stage 14: the Vulkan backend (excluded)

- **Excluded from this plan** (the owner's decision, section 1.2): OpenGL only. The Khronos validation
  layer is not installed on this machine, and nothing consumes a second backend yet. The entry stays
  as the specification for when it is taken up, as section 4.5 is Metal's.
- **Scope.** Section 4.4: the binding, the device and swapchain, the five pipelines from the embedded
  SPIR-V, descriptor sets, instance buffers, the atlas and images, `render`, `record`, the offscreen
  target and `read_pixels`; `ui_sdl`'s Vulkan window and surface; the gallery on Vulkan.
- **Units.** The backend sees only a `Staged`, whose canvas is the surface in device pixels: the canvas
  block is the projection for (0, 0) to (`width`, `height`) and the metrics (`width`, `height`,
  `width`, `height`), the viewport and the swapchain extent are `staged.width` by `staged.height`, and
  there is no scale anywhere in it.
- **Files.** `ui/vulkan/api.ctx`, `ui/vulkan/device.ctx`, `ui/vulkan/pipelines.ctx`,
  `ui/vulkan/shaders_spv.ctx` (generated), `ui/vulkan/contract.ctx`, `ui/sdl/vulkan.ctx`,
  `ui/samples/demo_vulkan/{build.ctx, main.ctx}`, `ui/tests/shots_vulkan/{build.ctx, main.ctx}`.
- **Before it starts.** The Khronos validation layer must be installed (section 4.4).
- **Acceptance.** Every run in the tests has the validation layer on and ends with no message.
  `ui/out/conformance-vulkan.png` at scales 1, 1.5 and 2 is compared with the OpenGL picture and the
  count of differing pixels is reported and explained (antialiased edges may differ by a level; nothing
  else may). The gallery in an outline font matches `gallery-basic.png` the same way. A second
  identical frame uploads nothing. Resizing recreates the swapchain without a validation message.
- **Agent.** fable, high effort. **Depends on:** stages 3 and 9.

### Stage 15: the kotor adapter and a developer overlay

- **Scope.** Section 8.1 as the owner decided it: kotor's OpenGL backend draws a `Staged` itself, with
  the library's four shader pairs (their one text, `ui/gl/glsl`) and `ui_gl`'s draw loop ported onto
  kotor's GL binding, reached through one new kind of step in `render::Frame` (`render::add_staged`);
  `ui_kotor`: the passes into the frame, a host slot's viewport, `from_font`, `to_event` (window
  coordinates to device pixels, SDL's buttons to the core's, cp1252 mapping of typed text), the
  requests, textures as images, and the `FrameInfo` kotor passes; a spike tool that shows the gallery
  through kotor's renderer, in the game's console font or in an outline font compared pixel for pixel
  with demo_gl's picture; and the GPU timing overlay drawn with the stock widgets beside the existing
  `fxhud`, behind the same option, in a commit of its own.
- **Units.** The UI pass is the screen target (`gpu::screen_size`, the drawable's size unless the game
  renders smaller), one unit a device pixel, not `ui_w` by `ui_h`. The `FrameInfo` is that size and the
  GUI's quarter-step scale; the pointer arrives in render pixels.
- **Files.** `kotor/lib/render/render.ctx` (`StepKind::staged`, `Step.staged`, `add_staged`),
  `kotor/lib/render_gl/canvas.ctx` (new) and `gpu.ctx` (the device's canvas, the step in `submit`),
  `kotor/lib/ui_kotor/{adapter.ctx, font.ctx, events.ctx}`, `kotor/tools/uispike/{build.ctx, main.ctx}`,
  `kotor/game/devui.ctx`, `kotor/game/play.ctx` (the overlay's state, its draw beside `fxhud`'s, its
  events in `pump_events`), `kotor/build.ctx` and the `build.ctx` of every tool that adds `lib/render`
  (they add `ui/core`, `ui/stage` and `ui/gl/glsl`), and `ui/gl/shaders_glsl.ctx` moved to
  `ui/gl/glsl/` (`ui/tools/build_shaders`, `embed_shaders.py` and `ui/.gitattributes` follow it).
- **Acceptance.** `uispike --headless --font PATH --against ui/out/gallery-basic.png` finds no pixel
  that differs from demo_gl's picture, rounded corners, smooth marks and outline text included, and
  the same at other pages, themes and scales; `uispike --headless` writes the gallery in the console
  font; `frame.dropped` is 0; the UI draws and quads `gpu::get_stats` reports are logged; the game
  with the timing option shows the overlay beside `fxhud` and its window takes the pointer (it moves
  and folds), while kotor's headless pictures (`rendertest`, `guiview`, the game's screenshots) are
  byte for byte what they were with the option off; `fxhud` is untouched; the game adds no `ui/fonts`
  and links nothing new.
- **Agent.** opus, medium effort. **Depends on:** stages 2 and 9. **May run with stage 13.**

### Stage 16: kui, and one KOTOR screen through the framework

- **Scope.** The KOTOR widget set over `ui`'s primitives, reading the control data that the existing
  loader produces (`gui::open` already resolves textures and fonts; kui reads those panels and does not
  load files itself); the replay of a whole panel; one screen's glue written against kui; a tool that
  draws a `.gui` both ways.
- **Units.** kui works in the original's design pixels and device pixels and never in logical units
  (section 3.2): it applies the original's per-edge snap, `floor(v * scale + 0.5)` with the size the
  difference of the snapped edges, to each control's and each border piece's design coordinates and
  hands the pixels to `ui::place_pixels` and the `paint_*` calls, which take them as they are. Text is
  painted a line at a time at the whole pixel size the font's design height times the scale comes to
  (`ui::scale_font_size`), with its origin on the pixel the snap gives.
- **Files.** `kotor/lib/kui/{skin.ctx, border.ctx, text.ctx, controls.ctx, list.ctx, panel.ctx}`,
  `kotor/tools/uiview/{build.ctx, main.ctx}`.
- **Acceptance.** `uiview optgameplay` writes the panel drawn by `lib/gui` and by kui and the count of
  differing pixels, counted apart for text and for everything else. Borders, fills and pictures must
  be 0 at scale 1.0 and at 1.5: they are the same pixels by the same formula. Text need not match
  `lib/gui` pixel for pixel: the owner decided that KOTOR text drawn through the framework follows the
  framework's one text rule (a whole pixel size, every glyph on whole pixels) rather than reproduce
  `lib/gui`'s unsnapped text with a special case (section 2.7). Its differing pixels are reported, not
  required to be 0, and a line must still wrap where `lib/gui` wraps it. A scripted run addresses
  `CB_AUTOSAVE` by tag, clicks it, and the setting flips; arrow keys follow `MOVETO`; hover lights a
  button and plays through `Interaction.entered`. A sweep over all `.gui` files prints how many panels
  already match, as the measure of the remaining work.
- **Agent.** fable, high effort. **Depends on:** stages 8 and 15. **Alone.**

### Order and concurrency

```
0 -> 1 -> { 2 | 5 } -> { 3 | 6 | 7 } -> { 4 | 8 } -> 9 -> { 10 | 11 | 12 } -> { 13 | 15 } -> 16
```

Braces are stages that may run together, never more than three. With two agents: run 6 and 7 together
and 3 after; 10 with 11, then 12; 13 with 15. Every stage in braces owns disjoint files, as its entry
says. Stage 14 (Vulkan) is excluded (section 1.2).

---

## 8. The path to KOTOR

### 8.1 The adapter

kotor's renderer draws the staged instances itself (the owner's decision): its OpenGL backend has
`ui_gl`'s four programs and draw loop, ported onto kotor's own GL binding
(`kotor/lib/render_gl/canvas.ctx`), with the shaders' text taken from `ui/gl/glsl`, not copied. So a UI
looks the same in KOTOR as on the library's backend (stage 15 compares the two pixel for pixel), and the
adapter, `kotor/lib/ui_kotor`, hands the staged passes to the frame and converts fonts and events.

**The seam.** A `render::Frame` is a list of steps that `gpu::submit` draws in order: a view's 3D
drawing, a run of `render::Quad`s (lib/gui's), and now a pass of a `ui_stage::Staged`:

- `render::add_staged{ &frame, staged, pass, target }` adds pass `pass` of `*staged`, drawn over what came
  before into `target` (null: the screen). The frame keeps the pointer, not a copy: the instances are
  read at submit, so the `Staged` must not change before. `ui_kotor::submit{ &frame, staged, target }`
  adds every pass; `add_pass` adds one.
- A step and not a function of its own beside `submit`, because a pass must take its place among the
  frame's other steps: under or over a view, before or after lib/gui's runs, under the game's pointer.
  So `render`'s change is the step kind (`StepKind::staged`, `Step.staged`, `add_staged`), and
  `render/contract.ctx` is unchanged: `gpu::submit` draws the new step. In exchange `render` names
  `ui_stage::Staged`, so every program that adds `lib/render` adds `ui/core` and `ui/stage`, and one
  that adds `lib/render_gl` adds `ui/gl/glsl`.

**Units.** The staged instances are device pixels, so a pass is drawn on the target's pixels, one unit a
pixel, its canvas anchored at the target's top left: on the screen that is the screen target
(`gpu::screen_size`), not kotor's GUI pixel space (`ui_w` by `ui_h`, the window over the quarter-step
scale), which lib/gui's own passes stretch. The `FrameInfo` kotor passes is that size and the GUI's
quarter-step scale (`ui_kotor::make_frame_info`); kui's pixels come from its own snap of design
coordinates (section 3.2), which is the same arithmetic lib/gui does with `Grid` [read: `draw.ctx:44`],
so a border piece lands on the same device pixels either way.

| `ui_stage` | kotor's renderer |
|---|---|
| `Pass` | one `render::add_staged` step |
| the four instance arrays, the clip table, the canvas block | uploaded once per revision of a `Staged`, as `ui_gl` does: four programs, each with the unit quad and an instance buffer laid out by `@offset_of`; `ClipRects` and `Canvas` bound to points 2 and 3, because the scene's `Frame` block has 0; GL 4.1 has no base instance, so a draw points the attributes at its first instance |
| `Draw.image` n | the texture whose id is n: `ui_kotor::to_image` makes a `ui::Image` of a `render::Texture` (kui of a `gui::Img`); an id the device does not have skips the draw and is counted |
| `ImageInstance` | as it is, but its V flipped as it is uploaded, because kotor's textures are stored bottom row first: above the seam a region's uv (0, 0) is the picture's top left, in kotor as everywhere |
| the glyph atlas | an R8 texture updated by its dirty rectangle, as `ui_gl`'s (bottom row first in both) |
| `Draw.blend` | the library's blending (separate alpha factors; additive adds the colour), not kotor's `render::Blend` states |
| `Pass.host` | `ui_kotor::get_slot` gives the slot and its rectangle as a `View`'s viewport: the screen adds its `render::add_view` there, then the next pass |
| a KOTOR font | `ui_kotor::from_font`: a glyph table on the font's texture with `Encoding::bytes`, a glyph's advance its width; staged as image instances, tinted |

- The step leaves GL as the rest of `lib/render_gl` expects it: program, vertex array, texture unit 0,
  depth, cull, offset and stencil go through the backend's cached setters, and its blend state is marked
  unknown after the pass.
- lib/gui's quads keep their own path (`draw_ui`); a frame holds both, in any order, which is how
  screens move one at a time (section 8.2).
- The stats count a staged draw as a UI draw and its instances as quads (`gpu::get_stats`).

The frame composition a screen with a 3D view uses today (`draw_panels_under_views`, the views,
`draw_overlay`) becomes a loop over passes: `add_pass`, and after a pass that ends at a host slot the
view in `get_slot`'s viewport. UI into a render target (minimap, map) is a second `ui::DrawList` built
with `ui::draw::*`, staged as a canvas the target's size, and added with that target.

**The atlas path for KOTOR's art.** kui holds every piece of border and picture art as a `ui::Region`.
Today a region is a whole texture, so a panel is a draw per texture, which is what kotor does now.
Packing the GUI's textures into atlas pages when a panel opens turns the same panel into a draw or two
and changes only where kui's regions point: no framework code, no seam change. It works because the
original stretches whole edge segments instead of relying on texture repeat [read: `draw.ctx:211`].
Excluded from this plan: it is an optimisation of kotor's material loading, and it can be measured only
once screens run on kui (stage 15 logs the draw counts it would improve).

Input: `ui_kotor::to_event` converts kotor's `sdl::Event` to the core's with the pointer in device
pixels (an event's coordinates times `pointer_scale`: 1 for the game's events, which `display::map_event`
has already put in render pixels; `gui::handle_event` divides by the scale into GUI pixels instead,
which the framework does not want), SDL's buttons as the core's (left 0, right 1, middle 2) and typed
UTF-8 as cp1252 bytes, the encoding of kotor's fonts. `ui_kotor::push_event` moves the pointer to a
button's position before the button, and answers with `ui::push_event`'s answer, which is what the game
loop already expects from `gui::handle_event`. `ui_kotor::apply_requests` turns OS text input on and
off; kotor draws its own pointer, and its SDL binding has no clipboard, so the cursor, copy and paste
requests are not applied (no screen built on it has a field that copies or pastes). kotor keeps its own
SDL binding and does not add `ui/sdl`.

### 8.2 Two ways to move a screen, both on kui

- **Replay.** kui draws a whole loaded panel from its control table each frame and reports what
  happened through a queue with the shapes of today's `gui::Event`. Properties the glue sets by tag
  (text, visibility, checked, picture) stay in the table. A screen moved this way changes `gui::` to
  `kui::` in its glue and nothing else. This is the route for the bulk of the 28k lines of glue.
- **Immediate.** The screen's code calls `kui::add_button{ tag = ... }` and friends itself and reads
  results, as in section 3.2. It suits screens that are mostly computed each frame anyway: the HUD,
  which today caches what it last set so as to set only what changed [read: report 2.1].

During the move both toolkits run: each screen belongs to one of them, the host's screen stack records
which, and the frame gets the old GUI's passes and the new one's in stack order.

### 8.3 Order in which screens could move

Simplest art and behaviour first, so each step adds one kui capability:

1. The developer overlay (stage 15): new UI, stock widgets, the game's console font.
2. Message boxes and the tooltip: one border, wrapped text, one or two buttons, modal.
3. Options panels: labels, buttons, checks, sliders, MOVETO, no lists. Stage 16 proves `optgameplay`.
4. Main menu and front end: the 3D background through a host slot.
5. Save and load: list boxes, scroll bars, row stretching, pictures set from code.
6. In-game menus: equipment and inventory (item entries), character sheet (3D view), abilities (cell
   rows), journal (text-mode list scrolled by lines), map (a render target as a picture), messages,
   party selection.
7. Store, container, level-up, galaxy map, upgrade bench.
8. Character generation: the edit box, 3D previews.
9. Conversation panels and barks: laid out by code, fades in an overlay.
10. The HUD: anchoring by thirds, the target block and reticles in an overlay, the minimap pass.
11. Pazaak: drag and drop.

`lib/gui`'s loader and types move into kui when the last screen has moved; until then kui reads them
where they are.

---

## 9. Open decisions for the owner

None is open. Already decided, and so not on this list: the seam level, GPU-only backends, the
rectangle's per-corner and per-side fields, ZGF's shaders, no built-in font, FreeType and HarfBuzz, the
location and the SDL library, OpenGL only (Vulkan, like Metal, specified and not staged: section 1.2),
verb names, the unit (whole device pixels, section 2.0), and the two decisions about how far the adapter
stage reaches into kotor:

- **The game.** The developer overlay goes into the game beside `fxhud`, behind the same option, with
  `fxhud` left in place and untouched, in a commit separate from the adapter. (The alternative was the
  spike tool only.)
- **kotor's renderer.** kotor's OpenGL backend draws a `Staged` itself with the library's four shader
  pairs and draw loop, so stock widgets look in KOTOR as they do on the library's backend (section 8.1).
  (The alternative was to leave the renderer alone and lower the instances to square `render::Quad`s:
  no rounded corners, lines without antialiasing.)

---

## 10. Risks, and language gaps

### 10.1 Risks

| Risk | Why it matters | What the plan does |
|---|---|---|
| Interaction lags layout by a frame | A widget cannot be clicked on its first frame; moving content is hit-tested where it was. Scripted tests must step frames. | One rule everywhere, stated in the guide; the driver steps for the caller; KOTOR's screens are static so last frame equals this frame. |
| The layout solver is the hardest code | A wrong pass order shows only in some trees. | Split in two stages (placed first, then flow), goldens before any widget exists, the strongest model. |
| Fixed capacities | A big screen silently loses widgets. | Never silent: counted, asserted zero in every test, shown in the gallery; capacities are a `make` argument. |
| The staged level is y up and everything above it is y down | A missed flip puts a corner radius or a border on the wrong side, and only asymmetric cases show it. | One function does the flip; stage 2's goldens and stage 3's picture use four different radii and four different borders on one rectangle. |
| Instance structs must match the shaders' attributes | A field out of order draws garbage. | The structs are ZGF's in ZGF's order; each backend sets attribute offsets from `@offset_of`; the conformance picture exercises every field. |
| Shader edits drift from ZGF | Later fixes in ZGF would be hard to take. | The files stay as files, the changes are few and listed, and stage 3 shows the diff. |
| Batching that reorders | A wrong overlap test paints in the wrong order, and only in some layouts. | ZGF's rule, taken as written; goldens with overlapping and non-overlapping interleavings; draws never span a pass. |
| The clip table fills (256) | A deep UI with many distinct clips loses shapes. | Equal clips share an entry; overflow drops and counts, never draws unclipped; asserted zero in tests. |
| The atlas fills | A program with many fonts, sizes or scripts exhausts it. | ZGF's atlas: growth to a limit, reuse of freed space; at the limit the frame's misses are counted and the cache refills next frame. |
| FreeType's struct layouts | The binding mirrors three C structs whose offsets depend on the platform's `long`. A wrong offset reads garbage. | Offsets chosen by `target::OS`; a start-up check of mirrored fields on every face; the probe's offsets came from a C program against the installed headers. |
| Vulkan without validation | A backend that works on one driver and breaks on another. | Stage 14 is excluded (section 1.2); its specification requires the validation layer and a clean run with it on before it starts, and the layer is not installed today. |
| Vulkan's size | It is the largest single backend (binding, swapchain, pipelines). | Not built (section 1.2). When it is taken up: its own stage with the strongest model, now that OpenGL has fixed what a backend does; nothing else depends on it. |
| Pixel parity with `lib/gui` | The proof screen must match the original's borders, wrap and snapping. | The core does not snap at all: kui applies kotor's own formula to its design coordinates and the core takes the resulting pixels as given (`ui::place_pixels`, the `paint_*` calls), so borders and pictures are the same integers; kui keeps kotor's wrap; text is not required to match: it is drawn at a whole pixel size with every glyph on whole pixels, where `lib/gui` draws fractional sizes between pixels (the owner's decision, section 2.7); `uiview` counts differing pixels and sweeps every `.gui`. |
| A value in the wrong unit | A logical length passed where pixels are taken, or the reverse, draws at the wrong size at any scale but 1, where the two are the same numbers and tests pass. | Most such mistakes do not compile: declarations are `f32` and pixels, text sizes included, are `i32`, and the language converts neither way. The ones that do (a radius, a line, `f32` in both worlds) are caught by recording goldens and screenshots at scale 1.5 as well as 1, which every widget stage must. |
| kotor's renderer keeps a port of `ui_gl`'s draw loop | `kotor/lib/render_gl/canvas.ctx` can drift from `ui/gl/device.ctx`, and a UI then looks different in KOTOR. | The shaders' text is one (`ui/gl/glsl`); `uispike --against` counts the gallery's pixels that differ from demo_gl's picture (0 at stage 15), to rerun when either backend changes. |
| Two SDL bindings in the repository | kotor's and `ui/sdl`'s can diverge. | They serve different programs and may even share one [compiled, a9]; `ui/sdl` is small and only what a UI host needs. |
| `..` forwarding binds any same-named local | `ui::add_label{ .. }` picks up a stray local called `text`. | Library code never uses it; the guide says to keep widget field names out of local names in functions that use it. |
| Frame-arena slices outlive the frame | `take_text` results kept across frames point at reused bytes; the escape check cannot see it. | Documented at the function; nothing in the library keeps one. |
| Two widget sets drift | Stock widgets and kui both grow. | Both use only the public primitives; kui lives in kotor and has its own parity tool. |
| Hover-as-focus one frame late | KOTOR's hover sound and highlight follow the pointer a frame behind. | 16 ms at 60 frames a second. Checked by eye in stage 16. |
| A machine without a system font | Samples and the font tests need a font file. | `--font PATH` for a sample, UI_FONT for the tests; without one the font tests are left out by name on `skip:` lines, never passed; the core's tests need no file at all. |

### 10.2 Language and std gaps

None of these blocks the plan. Each is either worked around inside `ui` with a few lines, or better
fixed in the language on its own branch, as kotor's rules require.

| Gap | In the plan | Better fixed in ctxlang or std? |
|---|---|---|
| Float formatting (`10.0` prints `1e+01`), no precision | Fixed in the language: `@fmt` has format specs and prints a short f32 plainly; the Ui and the recorder have the spec writers. `ui::write_fixed` stays for a digit count known at run time. | Done in std (`fmt`). |
| A program's `math` shadows std's (kotor) | The core declares its own few libm externs [compiled, a1, a5]. | The fix belongs in kotor (stop shadowing, or carry the missing functions), not in the GUI and not in the language. |
| The escape check misses a stack slice stored through a call | All text is copied at the call. | **Yes: a compiler fix would turn this class of bug into an error.** It affects every library that keeps slices. |
| No C `long` type and no way to mirror a C struct from its header | `ui/fonts` computes FreeType's offsets from `target::OS` and checks them at start-up. | A `c::Long` in std would remove the per-platform arithmetic. Small, and other bindings would use it. |
| No `ctxc check` (front end only) | Builds are fast enough (0.4 s for small programs). | Useful for agents, not needed. |
| No skip in `ctxc test` (`#test`, `@expect` and the runner landed: spec section 20) | The tests are `#test` fns; a package that needs a font or an OpenGL window has a `#test_main` that leaves out what cannot run, by name, on a `skip:` line, so the summary counts it as not selected (section 6.1). | A skip in the runner would remove the two `#test_main` fns and count skips in the summary. |
| No sort, no integer min and max | Only tiny insertion sorts (at most 64 layers) and three-line helpers. | No: not worth a std change for this. |
| No vector or rectangle math in std | `ui::Rect` and four helpers. | No: kotor's and ui's types differ for good reasons (f32 colours versus bytes). |
| No bare block statement | Closed: ctxlang now has block statements (spec section 11, rule 4). | Done in the language. |
| No default arguments | `Opts` with defaults and `..` forwarding [compiled]. | No: the workaround reads well. |
| No clock without `Threads` | The host passes `dt`. | No: it is the right design for determinism. |
| A build program cannot run a tool | The shader files are generated by a script and committed. | No: committed generated files have a precedent in `ctxlang/bootstrap`. |

---

## Appendix: the probes

All under `scratchpad\ctxprobe\`, built with `ctxc0.exe` and `CTX_HOME=ctxprobe\home`.

| Probe | Shows |
|---|---|
| `a1` | Scope tokens closed by `defer` across an early return; optional option fields with `null` defaults merged by `ifnull`; a non-generic `Ui` made by a generic `make`; an opaque-state hook (the font provider's shape) called through a `fn` value; a `?fn{ mut ui: Ui }` stored in a theme inside `Ui`; a pointer into the context's own buffer returned; `distinct u64` ids hashed with wrapping multiply; libm externs declared in `ui` beside a program `math` that binds the same symbol. Also that a bare block is rejected. |
| `a2` | C function pointers read from a table, cast to typed `extern fn` pointers and called (Windows COM methods). The evidence for the `objc_msgSend` technique in the Metal specification. |
| `a3` | A 4 KiB constant table as an array literal and as a byte-string literal, which is how the generated SPIR-V is embedded. |
| `a4` | Every declaration of sections 2.6, 2.7, 2.8 and 3.3 as written: the shape list with `RectStyle`, the `line` shape and the clip table; the four instance structs, `Draw`, `Pass`, `Atlas`, `Staged`; the font provider; the test font built in code; both sketches of section 3; the recorder's dump loop; the pass split at a host slot; a trivial `stage` that fills rectangle, image and line instances; the backend and provider contract check. 1,178 lines, builds and runs. Rebuilt after each of the owner's decisions. |
| `a5` | `a4` again with `kotor/lib/base` and `kotor/lib/platform` added: no name clashes, kotor's `math` present. |
| `a6` | A widget call whose argument is another call on the same context (`text = ui::take_text{ &ui }`); an extern function declared under another namespace's capability. |
| `a7` | FreeType and HarfBuzz linked from `build.ctx` and called: a font file read by the program, a glyph rasterised, two strings shaped. |
| `a8` | Vulkan linked and called: the loader's version, an instance, the device list. |
| `a9` | Two namespaces binding the same C symbol, each under its own capability and with its own opaque type, in one program. |
| `a10` | A capability stored in a library struct and used by a `fn` value that gets only an opaque pointer to it. |
| `spv` | ZGF's eight shader files with the two edits of section 2.6: all compile to SPIR-V with `glslc` and still validate as OpenGL GLSL 4.10 with `glslangValidator`. |
| `ccheck` | A C program against the installed FreeType and HarfBuzz headers printing the struct offsets `a7` uses. |
