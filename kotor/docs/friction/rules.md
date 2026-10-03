# Language friction: the rules library (`lib/rules`, `tools/rulescheck`)

Where ctxlang got in the way while writing the d20 rules (about 4,000 lines of library, 1,500 of
checks, several agents). Each entry: what I wanted to write, what I wrote instead, how often.

- **Signed data, unsigned indices.** Game data is signed (class rows -1 for none, modifiers, HP
  deficits) and every table is indexed by `usize`, and neither widens to the other, so every
  lookup is `a[@as(usize, i)]` after a range check, and every count going back into a result is
  `@as(i32, n)`. About 150 `@as(usize, ...)` in the library. Plain `i32` for all rule numbers
  was the least bad choice (the alternative, `usize` for rows, turns every modifier into a cast);
  an index operator that accepts any integer type with a bounds check would remove all of them.
- **`&x` punning needs equal names.** `recompute{ tables, &c }` only works when the callee's field is
  also called `c`; in a library where the same creature is `c` in some functions and `out` or
  `target` in others it is `c = &out` everywhere. Not a bug, but a source of "has no field `out`"
  compile errors on nearly every first build (the message is clear). About 40 calls.
- **Struct literals list every field.** `Stats` has 35 fields, so the `recompute` prologue is a
  10-line literal of zeros. `let mut s: Stats` zero-initialises, but a struct with a field that has
  no zero value (a `fn` or a pointer) can't, and those must be written out; `Creature` avoids it
  by holding no pointers (hence fixed arrays instead of a `list::List`). A struct literal with
  defaults for omitted fields (`Stats{ speed_factor = 1.0, ..zero }`) would do.
- **No `~`.** Clearing a bit is `x & ((1 << b) ^ 0xffffffff)` (4 places in the feat and power sets).
- **No `match` on integers.** Effect kinds, damage slots, slot masks and class rows are dispatched
  with `if` chains (`game_effect_row` is 25 arms, `slot_index` 15). Known (kotor/FRICTION.md).
- **A fallible function can't be a table entry.** The engine dispatches apply/remove handlers by
  effect type through a function table; here `apply_leaf` is one long `if` chain on `e.kind` with
  the handlers inline (~250 lines), because functions with inferred error sets are not values.
  (The handlers here are infallible, but the rule applies to any `fn` whose body `try`s.)
- **Read-only struct arguments are copied.** A creature is 30 KB, so every function takes
  `c: *Creature` and callers write `c = &c`; `Env`, `Versus` and `BonusQuery` are small enough to pass
  by value. Forgetting this is silent (a copy), so the rule had to be a convention.
- **Condition continuation lines.** `if a and\n b {` must break after the operator; the natural
  layout with `and` leading the continuation line is a parse error that points at the wrong place.
  Twice.
- **`@fmt` into `Io` needs the writers of `tools/common/out.ctx`** in every program that prints
  (rulescheck and each dev build add the directory); std has no stdout writers (kotor/FRICTION.md).
- **Tools that write files from Python** produce CRLF; ctxc accepts it but git warns. Edit with LF.
- **`build::add_sources` takes whole directories.** Four agents worked in `lib/rules` at once; one
  half-written file broke every build that added the directory, so each agent built from a
  private copy of the stable files (`sync.sh`, `sync.py`). Per-file sources, or a build that skips
  files that fail to parse, would have saved a copy script per agent.
- **`@as(i64, bool)` is rejected.** Counting passes and failures wrote `if b { 1 } else { 0 }`
  (about 60 times in the checks) or a separate `expect_true`.
- **`else` can't start a line**, so `}\n else if ...` chains are written `} else if` (style slip, a
  parse error each time it happened: 3).
- **A `mut` argument can't be a temporary.** `f{ mut x = g{} }` has no place to point to, so each
  such call is a `let mut tmp = g{}` first, or a wrapper (4 in combat).
- **`let mut` optionals don't narrow** (ctxlang FRICTION #7): helpers returning `?*Item` for the
  equipped weapon instead of `let mut weapon: ?*Item` (5 places).
- **No `ceil`/`trunc` for floats** in std or `lib/base/math`: `ceil_to_i32` in progress.ctx, and the
  XP arithmetic keeps the exe's f32-constant-widened-to-f64 trick by hand.
- **The Bash tool refuses compound commands** (heredocs mixed with `cd` and other commands, here-docs
  longer than a screen): scripts were written with the Write tool and run as one plain command.
