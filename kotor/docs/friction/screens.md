# Language friction: the game screens (`lib/screens`, the engine's store, container and level-up files)

Where ctxlang got in the way. Each entry: what we wanted, what we wrote instead, how often.

- **`&a.b` is not shorthand for a field.** `screens::take{ &ui.screens, &w, note }` fails ("expected
  '}', found '.'", then a flood of "has no field `ui`"): the shorthand is only for a plain local, so a
  place inside a struct needs the field's name, `s = &ui.screens`. Hit about fifteen times while
  wiring the panels' state structs into `ingame::Ingame` and `screens::State`; the error does not
  suggest the fix. (Same as the entry in gui.md.)
- **No type for "some error".** A helper that logs a failure, `fn report { mut w, error: anyerror }`,
  cannot be written: an inferred error set has no name. Every `iferr err{ error } { _ = @fmt(&w.io,
  "...: {}\n", error) }` is written out where it is used (about 30 times in lib/screens).
- **String literals in `if` branches** are arrays of different lengths: `let tail = if x { " infinite" }
  else { "" }` is "branches have different types: [9]u8 and [0]u8". Annotated `: []u8` (4 times).
- **No bitwise not.** Clearing a bit is `mask & (m ^ 0xFFFFFFFF)` (3 times: planet flags, upgrade bits).
- **A function with `mut` fields cannot take `&place.field` and a second `&` of the same place** (the
  exclusivity rule is right, but `foo{ &s, w = &w, f }` style calls grew long and error messages name
  only the call). Passing `w = &w` where the callee wants `*World` (read-only) while another argument
  is `&s` needed care in lvl_feats.ctx and lvl_powers.ctx (about ten calls).
- **`let mut s: State` zero-initialises only if every field has a zero value**: `State` structs with a
  `?*mut T` and tables worked, a struct holding a `*mut` (never null) would not. `lvl::new` and
  `ups::new` build the struct with `let mut s: State` and set the sentinels (`OBJECT_INVALID`) after.
- **Tooling, not the language:** the sandbox rejects shell commands that mix `cd` with anything it
  cannot prove is not git (heredocs, `*` patterns in arguments, `;` chains), so `sed -i` with a
  `\\n` in the replacement wrote a real newline (twice) and file edits went through the Edit tool
  instead; there is no Python in the worktree's PATH (`python3` is the Store stub).
