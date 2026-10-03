# Language friction: minigames (`lib/pazaak`, `tools/pazaakplay`, `tools/pazaaksim`)

Where ctxlang got in the way. Each entry: what we wanted, what we wrote instead, how often.

- **Punning doesn't reach into places.** `deal_hand{ &g.rng, &g.player, deck }` fails with "expected
  '}', found '.'" (the parser sees `&g` then `.`). Calls on a field of a local or of a `mut` field have to
  name the field: `deal_hand{ rng = &g.rng, side = &g.player, deck }`. The message doesn't hint at it.
  About 40 call sites in lib/pazaak, found one compile at a time.
- **An array literal or a `const` array isn't a slice argument.** `show_info{ pages = [1, 2, 3] }` for a
  `[]u32` field is "expected []u32, got [3]{integer}", and `CONST[..]` is "`CONST` is a const, not a
  place". Passed an enum that a function turns into a filled `[N]u32` instead (match.ctx,
  `tutorial_pages`). Twice (tutorial pages, and a table of strrefs in the first draft).
- **A match arm that is a single expression needs braces.** `start_turn => "mgs_startturn"` is "expected
  '{'"; `start_turn => { "mgs_startturn" }` works. The statement form of match doesn't force this on
  the reader's eye; a one-line arm would read better. Once (the sound table), but every match
  expression will hit it.
- **`try` of a call whose arguments include a stack buffer's slice.** `try click{ ..., tag }` with `tag`
  a slice of a local `[16]u8` fails ("`try` would return an error that may hold the address of local
  `tb`") because the callee's error set carries a slice (`gui::no_such_gui{ name }`). Swallowed the
  error with `iferr {}` (pazaakplay's `pick:`); a tool that must report it would have to copy the tag
  into the heap first. Same family as the entries in gui.md and video.md.
- **Two `if` branches with different literal lengths.** `if won { "won" } else { "lost" }` in a call
  argument: "branches have different types: [3]u8 and [4]u8"; `@as([]u8, ...)` is not allowed
  ("needs a numeric target type"). Bind it first: `let verb: []u8 = if ...`. Once (game/pazaak.ctx);
  gui.md has the same entry for `let`.
- **Enums have no zero value, so a struct holding one can't be `let mut x: T`.** `Prompt`, `Match`
  and `Session` all need a `new_*` that spells every field (`kind = PromptKind::none`, ...). Fine in
  itself, but the arrays of them (`[Sound::click; 16]`) need a made-up filler variant.
- **Integer arithmetic that wraps on purpose is verbose.** The C runtime's `rand()` (the original's
  shuffles) is `state * 214013 + 2531011` mod 2^32: `@wrap_add(@wrap_mul(state, 214013), 2531011)`, and
  every seed derivation in the tools (`seed + k * 2654435`) panicked on overflow until wrapped.
