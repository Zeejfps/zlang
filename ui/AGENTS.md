# ui: an immediate-mode GUI framework in ctxlang

Guide for agents working in `ui/`. [PLAN.md](PLAN.md) is the design and the staged plan (read its
sections 1, 2 and 6, and your stage in section 7); this file is the rules, the commands and the
layout. The language rules are in `kotor/AGENTS.md` (building, style) and `ctxlang/spec.md`; this
file only adds what is particular to `ui/`.

## What it is

The application describes its whole UI every frame and widgets return what happened. The core emits
a **draw list** (plain data: rect, image, text, line, host shapes with a clip table); a staged level
turns that into ZGF's instance kinds; a GPU backend draws them. The core needs std alone and calls no
backend, so the same code runs in a test with no window.

## Units: read this before writing any code here

The core works in **whole device pixels** (`i32`). This is the owner's decision (PLAN.md section 2.0,
"Units", has the reasons); it was made after the first stages were built in fractional logical units,
and the code was converted. There is one rule and it has two halves:

- **A declaration is logical units (`f32`).** `ui::Box`, `Size`, `Place`, `Insets`, `TextStyle`, the
  theme and every stock widget's options. The core converts them to pixels once, when the element is
  recorded, at the frame's one scale (`FrameInfo.scale`, device pixels a logical unit).
- **Drawing, and everything the core answers, is device pixels.** The `paint_*` calls, `ui::draw`,
  `get_rect`, `measure_text`, `measure_line`, `get_pointer`, `Interaction.drag_x`, a node's rectangle,
  hit regions, scroll offsets, `Requests.text_rect`. Rectangles, positions, border widths and a text's
  size are `i32`; a line's end points and width, corner radii, angles and uv are `f32`.

The conversions, which are the same ones the core uses, so a widget that converts a length itself gets
the pixels an element declared with that length gets:

| Call | For | Rule |
|---|---|---|
| `ui::to_pixels{ ui, length } -> i32` | a size, padding, gap, border width | the nearest pixel, a half away from zero; never 0 unless the length is 0 (1 unit is 1, 1, 2, 2, 2 pixels at scales 1, 1.25, 1.5, 1.75, 2) |
| `ui::to_pixel_position{ ui, position } -> i32` | an offset | the nearest pixel, a half up: `floor(v * scale + 0.5)` |
| `ui::to_font_size{ ui, size } -> i32` | a text size | a whole pixel size, the nearest, at least 1 (13 units is 13, 16, 20, 23, 26 pixels at scales 1, 1.25, 1.5, 1.75, 2); `ui::scale_font_size{ size, scale }` is the same rule where there is no `Ui` |
| `ui::to_pixels_f32{ ui, length } -> f32` | a radius, a line | scaled, not rounded |
| `ui::place_pixels{ rect }`, `ui::fix_pixels{ size }` | a placement or a size already in pixels | taken as given |

What follows from it, and what a reviewer checks:

- No snapping anywhere: nothing rounds at emit or at staging, and nothing converts pixels back to
  logical units. If you find yourself writing `/ scale`, stop: the one place a widget divides by the
  scale is to turn a pixel drag into a change of a logical value it stores.
- Ints and floats never mix implicitly, so most unit mistakes do not compile. The ones that do are
  the `f32` quantities (a radius, a line): record a golden or a screenshot at scale 1.5 as well as at
  1, where logical units and pixels are the same numbers and hide the mistake.
- Text has one rule and no flag: a text's size is whole pixels, an outline font is shaped at it, a
  glyph table is magnified by size / height with every glyph put on whole pixels (`ui::lay_glyphs`),
  and only the pen inside a run is fractional. KOTOR text drawn through the framework does not
  reproduce `lib/gui`'s fractional sizes (the owner's decision, PLAN.md section 2.7): do not add a
  path that keeps a text size or a glyph between pixels.
- A size never depends on a position. Where pixels are divided, say who gets the remainder (the first
  children when sharing, rounded down when centring), as the comment at the top of
  `ui/core/layout.ctx` does for the layout.
- Integer `+`, `-`, `*` and an `@as` from a float panic on overflow. Sums of pixels a program could
  make large go through `ui::add_pixels`, `sub_pixels` or `hold_pixels` (an `i64` sum held to
  `ui::MAX_PIXELS`, a thousand million), and a float becomes a pixel only through `ui::floor_pixels`,
  `ceil_pixels`, `round_pixels` or the conversions above, which take NaN as 0 and hold what is out of
  range. Test the extremes: `i32` max, a negative size, a scale of 0 or NaN.
- A test compares rectangles with `==`, never with a tolerance.
- A widget whose pixel sizes come from its own last width (a table's columns from last frame's
  `get_rect`) declares the part that holds them `take{ 1.0 }` of itself, not a fixed size: a part
  counts for nothing when its parent is fitted, so the widget follows its parent and is never held
  at its own last width.
- A window's place and size are logical state. A drag adds the pointer's pixels to the pixel place
  it had at the press and stores the result over the scale, which converts back to the same pixel:
  that, not adding `drag_x / scale` to a logical value, is what keeps a dragged window from drifting.

## Rules

1. **`ui/` stands alone.** No `build.ctx` under `ui/` may name a `kotor` path, and nothing in `ui/`
   adds a directory under `kotor/`. A program composes the packages it needs. The kotor side
   (`kotor/lib/ui_kotor`, `kotor/lib/kui`, `kotor/tools/uicompat`) depends on `ui/`, never the other
   way.
2. **`ui/core` uses std only and never `math::`.** Kotor declares its own `math`, which shadows std's
   whole namespace of that name, so library code calling `math::floorf` breaks inside kotor. The
   libm functions the library needs are declared in `ui` itself (`ui/core/num.ctx`: `floor_f32`,
   `sqrt_f32`, ...). Add one there when you need one.
3. **Function names are verbs** (`add_rect`, `write_list`, `format_fixed`, `from_literal`). Types,
   consts and namespaces follow the plan.
4. **Widget calls cannot fail**, so there is no `try` on one. Overflow drops the item and counts it
   (`DrawList.dropped`, `ui.stats.dropped`); misuse is recorded in `ui.problems`, never a panic. A
   test asserts after every frame that nothing was dropped and no problem was recorded.
5. **No parsing of ctxlang outside the compiler.** Tools and tests never lex or parse ctxlang and
   never mirror the compiler driver; if a tool needs to know something about a program it asks the
   native `ctxc`. `ui/tools/check` is a plain bash loop that runs test programs. No Python in any test
   path: the driver, the script reader and the golden compare are ctxlang.
6. **No "for now", "later" or "v1" in code or docs.** Implement what the stage specifies or say why
   you could not.
7. **Do not touch `ctxlang/`** (compiler, std). A compiler or std problem: write a minimal
   reproduction outside the repository, work around it inside `ui/` if that is cheap, and report it.
8. **Do not commit unless the owner asks.** Leave work in the working tree. Build outputs never land in
   tracked paths: `git status` after a run lists only source files and goldens.
9. **Stage discipline.** A stage touches only the files its entry in PLAN.md section 7 lists. A file the
   stage does not list, or a change outside `ui/` and `kotor/tools/uicompat/`, is a reason to stop and
   report, not to do it.
10. **Language habits that matter here.**
    - One widget call per statement. An argument may not change a place another argument of the same
      call reads or changes, so compute a nested widget call in a `let` first.
    - A call's `..` forwards same-named fields; punning (`&ui`) works by name only, so the context
      parameter is named `ui` everywhere and the draw list `list`.
    - Escape checks do not catch a stack slice stored through a call: text that outlives the call is
      copied into the frame's text arena (`ui::draw::add_text` does).
    - Do not print an `f32` with `@fmt` into a golden: std writes `10.0` as `1e+01`. Use
      `ui::format_fixed` or the recorder's `write_number`.
    - Files stay a few thousand lines at most (a file is the unit of recompiling).

## Commands

From the repository root, in **Git Bash** (PowerShell's `bash` is WSL's). The wrapper builds the
compiler on first use; a cached rerun of a small program takes about 0.1 s.

```
kotor/tools/ctxc run ui/tests/draw                     # stage 0: draw list, recorder, formatting, the unit conversions
kotor/tools/ctxc run ui/tests/text                     # stage 1: fonts, measuring, wrapping, caret
kotor/tools/ctxc run ui/tests/stage                    # stage 2: instances, atlas, batching; writes ui/out/stage-atlas.png
kotor/tools/ctxc run ui/tests/fonts                    # stage 4: FreeType and HarfBuzz; takes --font PATH
kotor/tools/ctxc run ui/tests/layout                   # stages 5 and 6: the Ui, ids, the tree, layout, emit, the pixel properties
kotor/tools/ctxc run ui/tests/input                    # stage 7: input, interaction, focus, state, nodes, the driver
kotor/tools/ctxc run ui/tests/layers                   # stage 8: overlays, windows, modals, popups, tooltips, scroll regions
kotor/tools/ctxc run ui/tests/widgets                  # stages 9 to 12: the stock widgets (basic.ctx, windows.ctx, data.ctx)
kotor/tools/ctxc run ui/tests/shots -- --out ui/out    # stages 3 and 4: pictures from the OpenGL backend (needs a GPU); look at them
kotor/tools/ctxc run ui/tests/draw -- --update         # rewrite goldens after an intended change (any test takes it)
kotor/tools/ctxc run ui/samples/demo_gl                # the gallery in a window
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --page Windows --theme light --scale 1.5 --shot ui/out/windows.png
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --script ui/samples/gallery/tour.txt --shot ui/out/tour.png
kotor/tools/ctxc run ui/samples/tasks                  # stage 13: the desktop application, in a window
kotor/tools/ctxc run ui/samples/tasks -- --headless --script ui/samples/tasks/tour.txt   # its walk-through; ui/out/tasks-*.png
kotor/tools/ctxc run kotor/tools/uicompat              # ui built beside kotor's libraries
kotor/tools/ctxc run kotor/tools/uispike -- --headless --out kotor/out/uispike.png     # the gallery through kotor's renderer
kotor/tools/ctxc run kotor/tools/uispike -- --headless --font C:/Windows/Fonts/segoeui.ttf --against ui/out/gallery-basic.png
                                                       # the same in an outline font, against demo_gl's picture: 0 pixels differ
ui/tools/check                                         # the shader check, every headless ui test in turn, then uicompat
```

demo_gl's options: `--font PATH` (default the platform's, `C:/Windows/Fonts/segoeui.ttf` on
Windows), `--theme dark|light`, `--page TITLE` (a listed gallery page: Basic, Windows, Data),
`--scale S` (device pixels a logical unit; in a window, the monitor's scale times S), `--size WxH`
(the surface in logical units, default 1040x720), `--script PATH` (drive the gallery with a
script, then stop), `--frames N` (headless without a script: 2), `--headless` (an offscreen target
of a hidden window), `--shot PATH` (the last frame as a PNG when it stops). It exits 1 when a
frame was not well formed, GL reported an error, the font library refused something or a script
line failed. A script (`ui/test/script.ctx` has the commands: frames, wait, move, down, up, click,
drag, key, type, wheel, shot, expect, value, text, resize, idle) is how a screenshot shows a menu
open, a combo open, a tooltip or a drag in progress. `resize` and `idle` are asked of the host:
demo_gl has neither, tasks has both (`idle 2 0 0`: two seconds of its event loop draw no frame).

tasks takes the same options but `--page` (its `--size` default is 520x620), and `--fallback PATH`
(a face for the characters the font lacks; default the platform's CJK face, `msyh.ttc` on
Windows). It draws only when an event came, its state changed or a frame asked to animate.

Later stages add `ui/tests/<name>` programs (PLAN.md section 6.2 lists them with their stage). A test
exits 1 when any check fails and prints each failure; `ui/tools/check` exits non-zero if any test does.

**Golden files.** A test builds something, writes it as text with `ui_rec`, and compares it with
`ui/tests/<name>/golden/<name>.txt`. On a mismatch it prints the first differing line both ways and
writes `<name>.actual.txt` beside the golden (git ignores it). A golden is written by hand from what
the test built, or reviewed line by line against it when `-- --update` produced it: a golden that
merely records what the code printed proves nothing. The reviewer reads the git diff of goldens.
Carriage returns are ignored in the compare, so a checkout with Windows line ends still matches.

## Layout

```
ui/
  AGENTS.md PLAN.md .gitignore     (.gitignore: /out/ and *.actual.txt)
  core/       namespace ui         values, draw list, numbers, fonts and text, the Ui, ids, tree, layout, emit
    types.ctx   Rect (i32 pixels), Color, Uv, Sides (i32), RectStyle, Cmd, Clip, Region, FontDef, DrawList
    draw.ctx    ui::draw: make, reset, add, add_clip, add_rect, add_image, add_line, add_text, add_host
    num.ctx     libm externs (floor_f32 ...), pick_min/max, clamp_f32, clamp_i32; the pixel helpers: MAX_PIXELS,
                hold_pixels, add_pixels, sub_pixels, floor_pixels, ceil_pixels, round_pixels, hold_scale,
                scale_length, scale_font_size, scale_position, take_fraction
    format.ctx  format_fixed, format_hex, format_color: into a caller's buffer, no std float printing
    font.ctx    the provider hook types, decode_char, get_font_scale; ui::draw: add_font, has_font, get_font, add_known_text
    text.ctx    lay_glyphs, LineBox; ui::text: Cache, measure_text (i32, rounded up), sum_text, get_line_metrics,
                wrap_text, fit_ellipsis, step_caret, locate_caret, pick_index, ceil_width, round_metrics
    ui.ctx      Ui, Capacity, Theme, Config, Stats, Problem, FrameInfo; make, begin_frame, end_frame; report_problem,
                report_drop; add_font, set_provider, measure_text, measure_line; the conversions (to_pixels,
                to_pixel_position, to_pixels_f32, to_font_size, to_pixel_sides, to_pixel_corners, get_scale);
                the Ui as an @fmt sink, write_fixed, take_text
    id.ctx      Id, Scope, make_id, push_id, push_key, end; ui::id: the scope stack, write_path
    tree.ctx    Box, Size, Place, Insets, TextStyle, Opts (logical units); fix, fix_pixels, take, place, place_pixels, inset;
                begin_element, add_text, add_host_slot, paint_* (pixels); ui::tree: Element (pixels), Extent, open_element
    layout.ctx  ui::layout: solve, position: the flow solver in integer pixels (fit, grow, fix, take, min and max,
                alignment, wrapped text and dots); its rounding rules are the comment at its top
    emit.ctx    Hit, get_rect; ui::emit: emit_frame (clips, opacity, hit regions; nothing is rounded here)
    host.ctx    Event (the pointer in device pixels), Key, Cursor, Requests
    input.ctx interact.ctx focus.ctx state.ctx nodes.ctx layers.ctx scroll.ctx
                one subsystem each: its state (a field of Ui) and make_state, reset_state, finish_frame
    input.ctx   push_event, get_pointer, get_time, is_released, take_key, get_keys, take_key_at, take_typed,
                take_typed_before (typed text and strokes in the order they came), take_paste, set_cursor, set_text_input, copy_text, ask_paste, set_animating, take_requests
    interact.ctx PressOpts, Interaction, press, get_hover_time, take_wheel, take_wheel_x, is_pointer_over
    focus.ctx   Links, set_links, set_focus, claim_focus (a press's focus, for a widget's part), is_focused,
                is_focus_visible and set_focus_visible (the focus came by keys or by hover-focus: draw the ring;
                a pointer press hides it)
    layers.ctx  begin_overlay, begin_modal, begin_window_layer, raise_window, open_popup, open_popup_on, begin_popup,
                close_popup, close_popups, is_popup_open, get_open_popup, make_popup_id, is_tip_due, begin_tooltip
    scroll.ctx  begin_scroll, begin_scroll_with, get_scroll, set_scroll, find_rows (a virtual list's rows in view)
  widgets/    namespace ui         the stock widgets, over the core's public calls only (no ui::tree/layout/emit)
    opts.ctx    Range, get_widget_name, merge_box, make_press_opts, take_activation, finish_widget,
                get_widget_flags, add_focus_ring (drawn only while is_focus_visible), get_ring_width
    theme.ctx   make_dark_theme, make_light_theme, derive_theme, mix_color, get_accent_pressed,
                get_border_strong, get_raised_color, get_rule_color
    icons.ctx   Icon, paint_icon (the stock marks as lines), get_mark_stroke
    basic.ctx   add_label, add_button, add_checkbox, add_radio, add_progress, add_image, add_separator,
                add_spacer, begin_row, begin_column, begin_panel, begin_group, add_tooltip
    slider.ctx  add_slider
    window.ctx  WindowOpts, begin_window (move, resize, fold, close, held reachable), begin_dialog
    popup.ctx   add_combo; make_global_id, pack_id, unpack_id, write_popup_name (what popup widgets share)
    menu.ctx    begin_menu_bar, begin_menu (a bar's title or a submenu), add_menu_item, add_menu_check,
                add_menu_separator, begin_context_menu
    drag.ctx    Payload, Drop, begin_drag (the ghost in the front overlay), accept_drop, is_dragging
    list.ctx    begin_list, begin_list_row; make_part_id
    tree.ctx    begin_tree_node
    tabs.ctx    begin_tabs, begin_tab
    table.ctx   begin_table, begin_table_row, next_cell, add_cell_text
    plot.ctx    add_plot
    color.ctx   add_color_edit
  samples/gallery/  namespace gallery  every widget, no main: gallery.ctx (the page switcher, the theme
                                   switch) and one page a file, page_basic.ctx, page_text.ctx,
                                   page_windows.ctx, page_data.ctx, each with its LISTED flag; tour.txt
                                   (a script through the basic page)
  samples/demo_gl/                 program: the gallery on OpenGL and SDL (options under Commands)
  samples/tasks/   namespace tasks program: a to-do list as ordinary desktop software (stage 13): app.ctx
                                   (the application, core and widgets only), main.ctx (the host: window,
                                   fonts, the event-driven loop, the script hook), tour.txt
  stage/      namespace ui_stage   the staged level: instances, clip slots, atlas and glyph cache, batching, passes;
                                   its canvas is the surface in device pixels
  fonts/      namespace ui_fonts   outline fonts: FreeType rasterises, HarfBuzz shapes; the TextProvider
  shaders/    (GLSL)               ZGF's four shader pairs
  gl/         namespace ui_gl      the OpenGL 4.1 backend
    glsl/       shaders_glsl.ctx   the shaders' text (generated by tools/build_shaders), a directory of its own
                                   so kotor's renderer adds it without the backend (PLAN.md section 8.1)
  sdl/        namespace ui_sdl     the SDL2 host: window, events (pointer in device pixels), requests, sizes and scale
  record/     namespace ui_rec     the recorder: Sink with its own #write fns, write_list, write_quoted
  record_stage/ namespace ui_rec   write_staged, the dump of a Staged: its own directory, because it names ui_stage
                                   and a program that records only draw lists should not have to add ui/stage
  test/       namespace ui_test    Tally, expect, has_flag, compare_golden, make_test_font, write_png, Driver (the scripted
                                   host, which speaks device pixels: click, drag, tap_key, ...)
    script.ctx  run_script: the text scripts demo_gl's --script runs (the commands are its top comment)
  tests/<name>/                    programs: build.ctx, main.ctx, golden/*.txt
  tests/widgets/                   main.ctx (make_ui, make_driver, write_frame, write_nodes, count_text) and a file
                                   of checks a stage: basic.ctx (9), field.ctx (10), windows.ctx (11), data.ctx
                                   (12), with goldens golden/basic-*, field-*, windows-*, data-*
  tools/check                      the shader check and a bash loop over the headless tests
  out/                             (ignored) screenshots
```

`vulkan` and `samples/demo_vulkan` are specified, not built: the owner decided to build OpenGL only
(PLAN.md sections 1.2 and 4.4). Backends and hosts are siblings of `core`, never children, because
`add_sources` adds a
directory and everything below it; a program lists exactly the directories it needs. A test or sample
(anything with a `fn main`) must not live under a directory another program adds.

**The dump format** (`ui_rec::write_list`): one shape a line after a `frame WxH` line (the surface in
pixels) and the clip table. Radii run top-left, top-right, bottom-right, bottom-left; border widths and
colours run top, right, bottom, left; colours are `RRGGBBAA`. What the list holds as whole pixels
(rectangles, text positions and sizes, border widths, the frame's size) is written as an integer and
cannot print a fraction; what it holds as a float (radii, a line's end points and width, uv, angles)
has up to four digits after the point with trailing zeros dropped. Entry 0 of the clip table
(the whole surface) is not listed. A list that dropped shapes ends with a `dropped N` line. The exact
format is the comment at the top of `ui/record/dump.ctx`. A scene recorded at scale 1.5 is in pixels:
a box declared 100 units wide is `150` in its golden.

**Draw list conventions.** Coordinates are device pixels, y down, origin top left; the list carries
the surface's size and no scale. A full clip table
or a clip index that names no entry drops the shape and counts it in `list.dropped`; the shape is
never drawn unclipped. `ui::draw::add_clip` shares equal entries and counts the drop itself, so the
caller skips its shape without counting again.

**The Ui and its subsystems.** `ui/core/ui.ctx` holds `Ui`, `make`, `begin_frame` and `end_frame`, and
a core stage does not edit it: each subsystem has one field of `Ui` and its own file, with
`make_state` (called by `make`), `reset_state` (by `begin_frame`) and `finish_frame` (by `end_frame`).

- `begin_frame` resets ids, tree, layout, emit, then input, interact, focus, state, nodes, layers,
  scroll. `end_frame` closes open scopes, calls `layout::solve`, `scroll::settle_regions` (which may ask
  for one more solve, or for `layout::position`), `layers::place_layers` (which may ask for
  `layout::position`), `emit::emit_frame`, and then `finish_frame` of nodes, interact, focus, state,
  layers, scroll, input.
- What does not fit is `ui::report_drop{ &ui, kind }` (counted in `ui.stats.dropped`, its kind listed
  once a frame); misuse is `ui::report_problem{ &ui, kind, id }`. A test checks after every
  well-formed frame that `ui.stats.dropped` and `ui.stats.problems` are 0.
- The tree is `ui.tree.elements[..ui.tree.count]`, parents before children. `tree::get_open{ ui }` is
  the element being recorded into. An element holds pixels only (its sizes as `tree::Extent`, its
  padding and hit outset as `Sides`, its gap, offsets and scroll as `i32`): `tree::make_element`
  converted the box. The layout owns `x`, `y`, `w`, `h`, `content_w`, `content_h` (all `i32`) and a
  text element's `first_line`, `line_count`, `dots` (its lines are in `ui.layout.lines`); emit reads
  them and nothing else of a solve.
- What the layout leaves for the stages built on it: a box's `content_w` and `content_h` are what its
  flow children take once every size is final, without its padding (a scroll region's range); `solve`
  may run again on the same tree and `position` alone is enough after only offsets changed; a scroll
  region needs its size from outside (fitted, it is as large as its content); grow children share the
  spare room, so two with different content are not the same width; text is top-aligned in its
  element. `scroll_x` and `scroll_y` of an element are whole pixels.
- `ui.emit.hits[..ui.emit.hit_count]` is the last finished frame's identified elements in emission
  order, topmost last, from one `end_frame` to the next: `rect` is the element's rectangle, `area`
  where it takes the pointer (empty when it is out of sight or behind a modal tree), both in device
  pixels. A pixel is in a rectangle when it is on its left or top edge and not on its right or bottom.
- A layer is `tree::open_element` with `root` set; a scope that must record something when it closes
  (a scroll region's bars) passes `on_end`.
