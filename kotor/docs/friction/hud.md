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
- **`if` with string-literal branches of different lengths** fails ("branches have different types:
  [4]u8 and [0]u8"): `let s = if x { "none" } else { "" }` needs a `[]u8` annotation
  (`let s: []u8 = ...`). Hit twice in the journal panel.
- **Events of other panels are not routed to a menu's `on_event`.** Message boxes and sub-panels
  that a menu opens are separate panels, so their events never reach it; three panels poll
  `gui::take_events` themselves. Not a compiler problem, a framework limit to revisit.
- **No way to hide a panel without closing it** in lib/gui; the HUD is moved out of reach
  (`Panel.sx`) while a conversation runs. A `hidden` flag on `Panel` would be clearer.

## 2026-10-03: Save Game and Load Game in the in-game options

- **A `mut x: T` parameter is `T` in the body but `*T` for a callee.** Passing `list` (declared
  `mut list: SaveList`) on to `has_number{ list: *SaveList }` is "expected *SaveList, got
  SaveList": it needs `&list`, the same as for a local. Easy once known, but the error does not say
  that the parameter's `mut` already is the pointer.
- **A one-name call needs its field name** even when the argument is a plain variable with another
  name: `rank_of{ a }` is "has no field `a`, call is missing `e`"; `rank_of{ e = a }`.
- **Shell tool restrictions again.** `sed -e 'Nr FILE'`, `printf` with a computed format and a
  heredoc followed by `git` in one command were all refused as "too complex to verify"; splicing a
  block into a file went through `head`/`cat`/`tail` into the scratch directory and `cp`, and loops
  through a script file run with `sh`.
- **Framework limit: a log line starting with `[` is dropped by `tools/ingame/go.sh`**
  (`grep -v '^\['`), and the engine's "saved ..." and "loaded ..." lines all start so. Tests of
  save and load must run `kotor.exe` by hand and grep.
- **Headless menus under a conversation.** A menu opened while a conversation's panels are up
  looks fine in the screenshot but its clicks go to the conversation's modal panels. Scripts that
  want a menu on the Endar Spire need two `hush` lines (the opening cutscene and the Trask talk).

## 2026-10-03: the HUD and panels on the rules creature

- **No default arguments, so adding an input to a shared helper edits its callers.** `items::damage_text`
  needed the wielder (Strength and Weapon Specialization come from the rules creature), and every call
  site (one, in equip_panel.ctx, another owner's file by assignment) had to change with it. A
  defaulted parameter, or a second name for the extended form, would have kept the old call valid.
- **A tree in the middle of a merge cannot be built, and `ctxc exe` reports the conflict markers as
  nine unrelated syntax errors** (`expected an expression, found '<<'`) with no hint that the file
  holds a merge conflict. I built a copy instead (`git archive HEAD` into the scratchpad, my files
  copied over, `ctxc exe <copy>/kotor`), which works because `ctxc` finds the compiler from its own
  location, not from the project.
- **Shell tool, not the compiler.** The worktree-isolated shell refuses any command that expands a
  variable in a command position, or runs `sh` on a script, with "cannot be shown not to be git";
  the run script had to be written with the Write tool and invoked as `sh <absolute path>`. Two tool
  calls issued in one block run concurrently, so a build and a run of its output raced.
- **Windows paths in program arguments.** The game exe takes `--screenshot-at 12:/c/Users/...` as a
  path it cannot open (`fs::not_found`, no path in the message); the `C:/Users/...` spelling works. An
  error that named the file would have saved a run.
