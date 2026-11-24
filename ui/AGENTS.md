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
- Dots mean "may be cut". A single line marked `Overflow::ellipsis` with a FIT width is laid out as
  GROW capped at its own width: it gives room up when its row is short, shared alike with every
  other child that may (a stock label is one). Text that must never be cut (a status bar's counts)
  is left `Overflow::clip`, which keeps its width; the comment at `ui::Overflow` and the status-bar
  check in `ui/tests/layout/flow.ctx` show both.
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
   native `ctxc`. The tests are `#test` fns, which the compiler finds; `ui/tools/check` is a plain
   bash script that runs `ctxc test` on each package and the programs. No Python in any test path:
   the driver, the script reader and the golden compare are ctxlang.
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
    - Format numbers with a spec: `@fmt(&ui, "{:.1} %", v)`; the Ui and the recorder take every spec.
      A golden writes a float with the recorder's `write_number` (trimmed: `10`, `0.5`) or a precision.
    - Files stay a few thousand lines at most (a file is the unit of recompiling).

## Commands

From the repository root, in **Git Bash** (PowerShell's `bash` is WSL's). The wrapper builds the
compiler on first use; a cached rerun of a small program takes about 0.1 s.

```
kotor/tools/ctxc test ui/tests/draw                    # stage 0: draw list, recorder, formatting, the unit conversions
kotor/tools/ctxc test ui/tests/text                    # stage 1: fonts, measuring, wrapping, caret
kotor/tools/ctxc test ui/tests/stage                   # stage 2: instances, atlas, batching; writes ui/out/stage-atlas.png
kotor/tools/ctxc test ui/tests/fonts                   # stage 4: FreeType and HarfBuzz; UI_FONT, UI_CJK_FONT name the faces
kotor/tools/ctxc test ui/tests/layout                  # stages 5 and 6: the Ui, ids, the tree, layout, emit, the pixel properties
kotor/tools/ctxc test ui/tests/input                   # stage 7: input, interaction, focus, state, nodes, the driver
kotor/tools/ctxc test ui/tests/layers                  # stage 8: overlays, windows, modals, popups, tooltips, scroll regions
kotor/tools/ctxc test ui/tests/widgets                 # stages 9 to 12: the stock widgets (basic.ctx, windows.ctx, data.ctx, keys.ctx)
kotor/tools/ctxc test ui/tests/sdl                     # the SDL host's conversions, from raw SDL_Event bytes to a Ui (no window)
kotor/tools/ctxc test ui/tests/shots                   # stages 3 and 4: pictures from the OpenGL backend in ui/out (UI_SHOTS_DIR); look at them
kotor/tools/ctxc test ui/tests/widgets slider          # only the tests whose names contain `slider` (any number of filters)
kotor/tools/ctxc test ui/tests/widgets --list          # the tests, FILE:LINE: NAME, without running them (also -v, --jobs N, --timeout S)
UI_UPDATE_GOLDENS=1 kotor/tools/ctxc test ui/tests/draw   # rewrite the goldens after an intended change (any package)
kotor/tools/ctxc run ui/samples/demo_gl                # the gallery in a window
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --page Windows --theme light --scale 1.5 --shot ui/out/windows.png
kotor/tools/ctxc run ui/samples/demo_gl -- --headless --script ui/samples/gallery/tour.txt --shot ui/out/tour.png
kotor/tools/ctxc run ui/samples/tasks                  # stage 13: the desktop application, in a window
kotor/tools/ctxc run ui/samples/tasks -- --headless --script ui/samples/tasks/tour.txt   # its walk-through; ui/out/tasks-*.png
kotor/tools/ctxc run kotor/tools/uicompat              # ui built beside kotor's libraries
kotor/tools/ctxc run kotor/tools/uispike -- --headless --out kotor/out/uispike.png     # the gallery through kotor's renderer
kotor/tools/ctxc run kotor/tools/uispike -- --headless --font C:/Windows/Fonts/segoeui.ttf --against ui/out/gallery-basic.png
                                                       # the same in an outline font, against demo_gl's picture: 0 pixels differ
ui/tools/check                                         # everything: the shader check, `ctxc test` on every package, both tours, uicompat
```

demo_gl's options: `--font PATH` (default the platform's, `C:/Windows/Fonts/segoeui.ttf` on
Windows), `--theme dark|light`, `--page TITLE` (a listed gallery page: Basic, Windows, Data),
`--scale S` (device pixels a logical unit; in a window, the monitor's scale times S), `--size WxH`
(the surface in logical units, default 1040x720), `--script PATH` (drive the gallery with a
script, then stop), `--frames N` (headless without a script: 2), `--headless` (an offscreen target
of a hidden window), `--shot PATH` (the last frame as a PNG when it stops). It exits 1 when a
frame was not well formed, GL reported an error, the font library refused something or a script
line failed. A script (`ui/test/script.ctx` has the commands: frames, wait, move, down, up, click,
drag, key, type, wheel, shot, expect, value, text, wake, resize, idle) is how a screenshot shows a menu
open, a combo open, a tooltip or a drag in progress. `resize` and `idle` are asked of the host:
demo_gl has neither, tasks has both (`idle 2 0 0`: two seconds of its event loop draw no frame).

tasks takes the same options but `--page` (its `--size` default is 520x620), and `--fallback PATH`
(a face for the characters the font lacks; default the platform's CJK face, `msyh.ttc` on
Windows). It draws only when an event came, its state changed, a frame asked to animate or the time a frame
asked to be woken at came (`Requests.wake`: a caret blinking draws two frames a second).

**Fonts in a program.** A font that is a file is added with `ui_fonts::add_face_file{ &lib, path,
index }`: HarfBuzz maps the file, so only the pages FreeType and HarfBuzz read are resident and the
program never reads the font (the tasks sample's 20 MB fallback font adds about 0.1 MB to its working
set, measured). Do not read a font file to hand its bytes to `add_face`, which copies them whole and
keeps the copy resident; that is for a font a program holds in memory anyway. While a face is alive
its file is mapped (on Windows it cannot be written over); `release_face` or `close` unmaps it. The
rules (path encoding, errors) are the comment at `add_face_file`.

**Tests.** A test is a `#test` fn (ctxlang spec section 20) in a package under `ui/tests/<name>/`,
run by `ctxc test`, each in a process of its own. The runner prints one line a failure, at the
check, with both sides of a comparison (`ui/tests/draw/main.ctx:105: fail: counts_what_does_not_fit:
rect_x_of{ cmd = list.cmds[3] } == 3: 4 == 3`) after what the test printed, and last
`tests: N run, P passed, F failed, S not selected`; it exits 1 if a test failed or none ran.
Run a package from the repository root (the goldens' paths start there); filters pick the tests
whose names contain one, and `--list` names them. `ui/tools/check` exits non-zero if any package,
tour or uicompat does.

Writing one:

- Put it in the package of what it tests (PLAN.md section 6.2 lists them), never beside the code: a
  program that adds `ui/core` would compile it. A new package is a directory with a `build.ctx` that
  adds what it tests, `../../test` and `../support`, and links what it needs; `ui/tools/check` finds
  it by its `build.ctx`.
- One coherent case a test, named for what it checks with a verb (`clicks_on_the_frame_after_the_release`,
  `wraps_as_the_golden`); a case run at two scales or in both themes is a test for each, over a
  helper that takes the scale. A test takes the capabilities it uses, a `Test` among them:
  `#test fn ... { mut t: Test, mut io: Io, mut mem: Mem } -> ! { let mut heap = ui_check::make_heap{ &mem } ... }`.
- Check with `@expect(&t, condition)` where the condition is decided, so the failure points there;
  compare values with `==` and friends so both sides are printed. A comment above the check says what
  it means. What cannot fail in a passing run (an allocation, a write into a sink) is `try`, and the
  test returns its error; a check in a helper reports the helper's line, so a helper that checks takes
  `mut t: Test` and prints what it looked at before its `@expect`.
- A test that needs what a machine may lack (a font, an OpenGL window) goes in a package whose
  `#test_main` fn leaves it out with `ui_check::run_tests_without` when that is missing (fonts' and
  shots' `main.ctx`). The runner has no skip: a test left out has its own `skip:` line and counts as
  not selected.
- Helpers that take a `Test` or exist only for tests go in `ui/tests/support` (namespace `ui_check`),
  which no program adds. `ui/test` is for what the samples use too (the driver, the script reader,
  the test font, the PNG writer), so nothing there takes a `Test`.

**Golden files.** A test builds something, writes it as text with `ui_rec`, and checks it with
`@expect(&t, ui_check::compare_golden{ &io, &fs, dir = GOLDEN_DIR, name, actual, scratch, update })`
against `ui/tests/<name>/golden/<name>.txt`. On a mismatch the compare prints the first differing line
both ways and writes `<name>.actual.txt` beside the golden (git ignores it). `update` is
`ui_check::is_updating{ &proc }`: run with `UI_UPDATE_GOLDENS=1` to rewrite the goldens after an
intended change (an environment variable, because `ctxc test` passes a test no arguments and each
test's process inherits the runner's environment). A golden is written by hand from what the test
built, or reviewed line by line against it when an update produced it: a golden that merely records
what the code printed proves nothing. The reviewer reads the git diff of goldens. Carriage returns
are ignored in the compare, so a checkout with Windows line ends still matches.

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
    format.ctx  format_fixed (a runtime digit count, trimmed or not, over std's fmt), format_hex, format_color
    font.ctx    the provider hook types, decode_char, get_font_scale; ui::draw: add_font, has_font, get_font, add_known_text
    text.ctx    lay_glyphs, LineBox; ui::text: Cache, measure_text (i32, rounded up), sum_text, get_line_metrics,
                wrap_text, fit_ellipsis, step_caret, locate_caret, pick_index, ceil_width, round_metrics
    ui.ctx      Ui, Capacity, Theme, Config, Stats, Problem, FrameInfo; make, begin_frame, end_frame; report_problem,
                report_drop; add_font, set_provider, measure_text, measure_line; the conversions (to_pixels,
                to_pixel_position, to_pixels_f32, to_font_size, to_pixel_sides, to_pixel_corners, get_scale);
                the Ui as an @fmt sink (every spec), write_fixed (a runtime digit count), take_text
    id.ctx      Id, Scope, make_id, push_id, push_key, end; ui::id: the scope stack, write_path
    tree.ctx    Box, Size, Place, Insets, TextStyle, Opts (logical units); fix, fix_pixels, take, place, place_pixels, inset;
                begin_element, add_text, add_host_slot, paint_* (pixels); ui::tree: Element (pixels), Extent, open_element
    layout.ctx  ui::layout: solve, position: the flow solver in integer pixels (fit, grow, fix, take, min and max,
                alignment, wrapped text and dots); its rounding rules are the comment at its top
    emit.ctx    Hit, get_rect; ui::emit: emit_frame (clips, opacity, hit regions; nothing is rounded here)
    host.ctx    Event (the pointer in device pixels), Key (a desktop's keys; `alt`: Alt alone), Shortcut, Cursor, Requests
    input.ctx interact.ctx focus.ctx state.ctx nodes.ctx layers.ctx scroll.ctx
                one subsystem each: its state (a field of Ui) and make_state, reset_state, finish_frame
    input.ctx   push_event, get_pointer, get_time, is_released, take_key, get_keys, take_key_at, take_typed,
                take_typed_before (typed text and strokes in the order they came), take_paste, set_cursor,
                set_text_input, copy_text, ask_paste, set_animating, ask_wake (a frame at a time: `Requests.wake`),
                take_requests; take_shortcut and has_shortcuts (the strokes the last frame left), get_key_name,
                write_shortcut
    interact.ctx PressOpts, Interaction, press, get_hover_time, take_wheel, take_wheel_x, is_pointer_over
    focus.ctx   Links, set_links, set_focus (waits up to two frames for a widget not recorded yet), get_focus, ask_first_focus
                (a dialog's first tab stop), claim_focus (a press's focus, for a widget's part), is_focused,
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
                add_menu_separator, begin_context_menu; an item's `opts.shortcut` is drawn in a shortcut column and
                works with its menu closed (a closed menu gives an open, silent scope on a frame with strokes left)
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
  fonts/      namespace ui_fonts   outline fonts: FreeType rasterises, HarfBuzz shapes; the TextProvider.
                                   A face comes from a file (add_face_file: HarfBuzz maps it, the program never
                                   holds its bytes) or from bytes a program holds (add_face: copied)
  shaders/    (GLSL)               ZGF's four shader pairs
  gl/         namespace ui_gl      the OpenGL 4.1 backend
    glsl/       shaders_glsl.ctx   the shaders' text (generated by tools/build_shaders), a directory of its own
                                   so kotor's renderer adds it without the backend (PLAN.md section 8.1)
  sdl/        namespace ui_sdl     the SDL2 host: window, events (pointer in device pixels), requests, sizes and scale
  record/     namespace ui_rec     the recorder: Sink with its own #write fns, write_list, write_quoted
  record_stage/ namespace ui_rec   write_staged, the dump of a Staged: its own directory, because it names ui_stage
                                   and a program that records only draw lists should not have to add ui/stage
  test/       namespace ui_test    make_test_font, write_png, Driver (the scripted host, which speaks device pixels:
                                   click, drag, tap_key, ...); the samples add it too, so nothing here takes a Test
    script.ctx  run_script: the text scripts demo_gl's --script runs (the commands are its top comment)
  tests/<name>/                    `#test` packages run by `ctxc test`: build.ctx, main.ctx, golden/*.txt
  tests/support/ namespace ui_check  what the tests share and no program adds: compare_golden, is_updating
                                   (UI_UPDATE_GOLDENS), make_heap, has_wake (golden.ctx); run_tests_without
                                   and the system fonts a test may need, found by path, not read (skip.ctx)
  tests/fonts/, tests/shots/       each with a `#test_main` that leaves out what the machine lacks
  tests/widgets/                   main.ctx (make_ui, make_driver, make_dump, write_frame, write_nodes, count_text)
                                   and a file of tests a stage: basic.ctx (9), field.ctx (10), windows.ctx (11), data.ctx
                                   (12), with goldens golden/basic-*, field-*, windows-*, data-*
  tools/check                      the shader check, `ctxc test` on every package, the samples' tours, uicompat
  out/                             (ignored) screenshots
```

`vulkan` and `samples/demo_vulkan` are specified, not built: the owner decided to build OpenGL only
(PLAN.md sections 1.2 and 4.4). Backends and hosts are siblings of `core`, never children, because
`add_sources` adds a
directory and everything below it; a program lists exactly the directories it needs. A sample
(anything with a `fn main`) or a test (a `#test` fn, which every build of its files checks) must not
live under a directory another program adds.

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
