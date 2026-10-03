# Language friction: dialogue (`lib/dialog`, its tools)

Where ctxlang got in the way. Each entry: what we wanted, what we wrote instead, how often.

## conversation panels (`lib/dialog/panels`, `tools/dialogpanels`)

- **`build::add_sources` takes a directory, never a file, and `build::exe` a directory without its
  subdirectories.** The panels have to be built by a test tool without the rest of `lib/dialog` (which
  needs the world), and a single `panels.ctx` cannot be named. Moved them into `lib/dialog/panels/`
  (the lip-sync code did the same with `lib/dialog/lipsync/`); the game's `add_sources lib/dialog`
  still reaches them. Once.
- **A bare `{ ... }` block is not a statement.** Wanted a scope per test section in one function
  (`check_picks`): `{ ... }` fails with "expected an expression, found '{'". Split each section into a
  function of its own. Twice.
- **`if` of two string literals has an array type, also as an `@fmt` argument.** `@fmt(&io, "{}", if ok
  { "ok  " } else { "FAIL" })` fails with "@fmt has no writer of [4]u8 to Io", and as a field value
  (`name = if a { "x.png" } else { "yy.png" }`) with "expected []u8". Wrote `either{ first, a, b } ->
  []u8` and called it five times; same as the entry in gui.md.
- **`&local` is shorthand only when the local has the callee's field name.** A tool that keeps its
  state in `dp` cannot write `dlgpanel::open{ &dp, ... }` when the field is `p`: "has no field `dp`" for
  every call (about thirty). Named the local `p`. A library taking `mut p: Panels` makes the shorthand
  only work for callers who name their value `p`; the others write `p = &dp`.
- **A read-only struct field is passed as the value, not `&`.** `shot{ ..., &p, ... }` for a field
  `p: Panels` fails with "expected dlgpanel::Panels, got *mut dlgpanel::Panels" (six calls). Right by
  the rules; the lead's brief asked for `*Panels` in `is_open`, `fade_running` and `bark_running`, which
  would make every caller write `p = &x`, so those take `p: Panels` (a big read-only struct is passed
  by reference anyway).

## lip sync (`lib/dialog/lipsync`, `tools/lipcheck`)

- **`try` refused: the error "may hold the address of a local".** `try render_all{ ..., track =
  &track }` (an `&` of a local `let` passed to a function whose error set includes `no_model{ name:
  []u8 }`) fails the escape check, since any error carrying a slice could point into an argument.
  Wrote `iferr err{ error } { ... }` at that one call instead. The rule is sound but the error's slice
  fields have nothing to do with the argument. Once.
- **The directory-only `build::add_sources`** (see the panels entry above) is why the lip sync sits
  in `lib/dialog/lipsync/`. A per-file `build::add_source` would let a tool pick files.
- **`if` of string literals as a format argument** needs a typed `let s: []u8 = if ...` first
  (known, gui.md; hit three times in the tool's output code).
