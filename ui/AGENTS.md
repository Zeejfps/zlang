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
   (`DrawList.dropped`, later `ui.stats`); misuse is recorded, never a panic. A test asserts after
   every frame that nothing was dropped and no problem was recorded.
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
kotor/tools/ctxc run ui/tests/draw                     # stage 0: draw list, recorder, formatting
kotor/tools/ctxc run ui/tests/text                     # stage 1: fonts, measuring, wrapping, caret
kotor/tools/ctxc run ui/tests/stage                    # stage 2: instances, atlas, batching; writes ui/out/stage-atlas.png
kotor/tools/ctxc run ui/tests/draw -- --update         # rewrite goldens after an intended change
kotor/tools/ctxc run kotor/tools/uicompat              # ui built beside kotor's libraries
ui/tools/check                                         # every headless ui test in turn, then uicompat
```

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
  core/       namespace ui         values, draw list, numbers; later the font table, tree, layout, input
    types.ctx   Rect, Color, Uv, RectStyle, Cmd, Clip, Region, FontDef, DrawList
    draw.ctx    ui::draw: make, reset, add, add_clip, add_rect, add_image, add_line, add_text, add_host
    num.ctx     libm externs (floor_f32 ...), pick_min_f32, pick_max_f32, clamp_f32, snap_f32
    format.ctx  format_fixed, format_hex, format_color: into a caller's buffer, no std float printing
    font.ctx    the provider hook types, decode_char, get_font_scale; ui::draw: add_font, has_font, get_font, add_known_text
    text.ctx    lay_glyphs; ui::text: Cache, measure_text, wrap_text, fit_ellipsis, step_caret, locate_caret, pick_index
  stage/      namespace ui_stage   the staged level: instances, clip slots, atlas and glyph cache, batching, passes
  record/     namespace ui_rec     the recorder: Sink with its own #write fns, write_list, write_quoted
  record_stage/ namespace ui_rec   write_staged, the dump of a Staged: its own directory, because it names ui_stage
                                   and a program that records only draw lists should not have to add ui/stage
  test/       namespace ui_test    Tally, expect, has_flag, compare_golden, make_test_font, write_png (later: scripted driver)
  tests/<name>/                    programs: build.ctx, main.ctx, golden/*.txt
  tools/check                      bash loop over the headless tests
  out/                             (ignored) screenshots from later stages
```

Planned packages (PLAN.md section 2.1): `widgets`, `stage`, `fonts`, `shaders`, `gl`, `vulkan`, `sdl`,
`samples/*`. Backends and hosts are siblings of `core`, never children, because `add_sources` adds a
directory and everything below it; a program lists exactly the directories it needs. A test or sample
(anything with a `fn main`) must not live under a directory another program adds.

**The dump format** (`ui_rec::write_list`): one shape a line after a `frame` line and the clip table.
Radii run top-left, top-right, bottom-right, bottom-left; border widths and colours run top, right,
bottom, left; colours are `RRGGBBAA`; numbers have up to four digits after the point with trailing zeros
dropped. Entry 0 of the clip table (the whole surface) is not listed. A list that dropped shapes ends
with a `dropped N` line. The exact format is the comment at the top of `ui/record/dump.ctx`.

**Draw list conventions.** Coordinates are logical units, y down, origin top left. A full clip table
or a clip index that names no entry drops the shape and counts it in `list.dropped`; the shape is
never drawn unclipped. `ui::draw::add_clip` shares equal entries and counts the drop itself, so the
caller skips its shape without counting again.
