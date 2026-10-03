# Friction: the HUD and in-game menus

Things in ctxlang or the toolchain that got in the way of lib/hud and lib/ingame (what I wrote,
what I had to write instead, how often).

- **Positional `&field.path` in a call.** `f{ &ui.gui }` is a parse error ("expected '}', found
  '.'"): the one-word shorthand only takes a plain name, so every call on a field needs the long
  form `f{ g = &ui.gui }`. About 40 times while wiring the session; the error message points at the
  `.` but does not say that the shorthand is the problem.
- **A `mut` slice or struct parameter can't be passed with another `&` into the same place.**
  `hud::update{ &w, ..., fs = &w.fs }` is an overlap error, so functions that need both the world
  and its file system take `mut w` and write `fs = &w.fs` in the one call that needs it (never
  next to `&w`). Fine once known, surprising the first time.
- **Optional narrowing on a `let` only.** `let b = if o != null { f{ o } } else { null }` does not
  type as `?T` (the branches differ); I wrote the null test first and `ifnull { return }` after.
- **Returned slices of by-value read-only parameters** ("returned value holds the address of local")
  force the owner to be passed as a pointer (`log: *MessageLog`) even though the function only
  reads it; callers then write `log = &ui.log`.
- **Shell tool restrictions (not the compiler).** In a worktree-isolated agent the shell refuses
  compound commands that mix `cd`, `&&`, globs and heredocs ("too complex to verify"); every
  repeated build or run needs its own small script file (`tools/ingame/go.sh`).
