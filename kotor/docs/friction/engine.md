# Language friction: the engine core (`lib/engine`, `lib/scene`, `game/`)

Where ctxlang got in the way while writing the world, the routines, the scene and the loop
(about 5,000 lines). Each entry: what I wanted, what I wrote instead, how often.

- **Bind records are never freed, and a `&fn` can't be stored.** The VM's engine is a bound
  function; it can't live in the World, so every function that may run a script takes `engine:
  nwvm::Engine` beside `mut w` and `mut vm` (about 15 functions). A routine has no engine at hand,
  so ExecuteScript binds a new one per call (a leaked record each time), and the scene binds
  `mdl_cache::get` once per (model, animation) it ever binds for `mdl_anim::find`'s lookup.
- **A bind and a `&` of what it holds can't meet in one call.** `routines::call{ &world, _ }` and
  then `world::tick{ &world, ..., engine }` is an exclusivity error. Written instead: the World
  lives in the heap and everything passes the raw `*mut World` (`routines::call{ w, _ }`, `tick{
  w, ... }`), which the checker doesn't track. Sound here, but it is the checker being worked
  around for the program's central object.
- **`try` and errors derived from a local.** A function that takes a name and can fail with an
  error whose payload holds a pointer (`no_area{ area: []u8 }`, any of res/mdl's) makes every
  `try` of it with a name from a local buffer (`resref::bytes{ r = &key }`) an escape error:
  "`try` would return an error that may hold the address of local `key`". Written instead: names
  copied into the module or scene arena before the call (3 places), and `scene::load_model`
  turning the device's errors into a payload-free `upload_failed` (which fixed 5 call sites at
  once). An error's payload rarely points at the caller's argument; a way to say so would help.
- **Results derived from read-only arguments.** `twoda::get_string{ t, row, column = buf[..] }`
  with the column name built in a local array returns a cell "derived from" that array, so it
  can't be kept past it, though the cell points into the table. Written instead: const tables of
  the ten column names (`modela`..`modelj`, `texa`..`texj`). Same family as models.md's map entry.
- **Punning stops at one name.** `values::end_run{ &w.values }` is "no field `w`"; it must be
  `s = &w.values`. About 40 call sites across the engine (a script fixed them).
- **`iferr {}` on a value.** `_ = alloc::resize(...) iferr {}` (freeing) is an error: the block
  must give a value. `_ = alloc::resize(...)` alone discards the `!T`. 20 places.
- **`iferr ... ifnull` can't chain** on one call (`visual::create{} iferr { null } ifnull {
  continue }`): split into two statements with a narrowed `let`.
- **No tuples.** `let (opening, opened) = if two { (a, b) } else { (c, d) }` became two `let`s
  with the same condition.
- **A struct literal names every field.** Adding a field to a struct that many places build
  (obj::Placeable's literal in world::make_ext) breaks them all; a sub-agent that couldn't edit
  that file kept a placeable's inventory cursor in an unrelated map under made-up keys instead.
  Defaults for fields (or a `..default` spread in literals) would let kinds grow by many hands.
- **No module-level state.** Anything "remembered once" (a log-once flag, a parsed table) must be
  a World field; the routine files can't keep a private cache, so every new cache touches
  world.ctx, the one file every agent needs.
- **`@fmt` has no fixed-point floats** (FloatToString's `%18.9f`): an exact decimal expansion
  was written by hand (rt_core::format_fixed). f64 libm functions needed their own externs.
- Fixed since: integer `match` (routine chains can be `match routine { nwscript::X => ... }`),
  big read-only arguments passed by reference.
- **`#write` needs one writer per exact type**: the log prefix's zero-padded milliseconds needed
  its own wrapper struct and writer (`world::Pad3`), and SDL's `c::String` error text another in
  game/main (`kotor_out`), since tools/common has neither.

## 2026-10-03: saves, combat

- **Narrowing hides `is some`.** After `if x != null { ... }` the variable is a plain pointer,
  so `if x is some{ value = v }` inside it is an error ("`is` cannot test through a pointer");
  `x ifnull 0` inside is an error too. Testing `is some` directly on the call
  (`if world::object{ w, id } is some{ value = o }`) avoids it; six places in fight.ctx.
- **`@as(u32, -1)` panics at run time**, not at compile time: writing GFF "none" values
  (SpellId 0xFFFFFFFF, LvlStatAbility -1) crashed a save. lib/save has a `bits{ v }` helper for
  i32-to-u32 reinterpretation; a `@bitcast` would do.
- **Escape check on results of calls with local arguments.** `obj::copy_lower{ heap, s =
  info.last_module }` (a fresh heap copy) counted as derived from the local GFF document, so a
  later `try` was refused; the copy had to be written inline with alloc::resize.
- **One flat namespace across a directory's files.** lib/save's files written by two agents at
  once (`put_*` helpers) had to coordinate names by message; per-file private functions would
  avoid it.

## 2026-10-03: effect routines

- **`if` branches that are string literals of different lengths don't unify.**
  `@fmt(&io, "{}", if kept { "kept" } else { "refused" })` is "branches have different types:
  [4]u8 and [7]u8" and then "@fmt has no writer of [4]u8"; it needs `let word: []u8 = if ...`
  first. String literals could coerce to `[]u8` in a conditional's branches.
- **A pun is the parameter's name, whatever the local is called.** `push_group{ &w, &vm, linked }`
  is "`push_group` has no field `linked`" (the parameter is `g`); the error is clear but the
  missing-`g` second error is noise.
- **No way to run a hand-assembled script in the game without writing into the install.** To
  exercise GetFirstEffect/RemoveEffect/DelayCommand-with-an-effect/save-and-load I generated NCS
  with tools/py/ncsasm.py and had to build a fake game directory (directory junctions to
  data/, modules/, ... and a private Override/) because Override/ is searched under `--game` only.
  An `--override DIR` option on kotor/enginetest would make script-level tests a one-liner. The
  scripts also ran once per creature (the guard through Get/SetGlobalNumber did not hold: an
  undeclared global doesn't persist), so each test output repeated 26 times.
- **`kotor/tools/savetest` no longer builds**: its build.ctx lacks lib/rules (and lib/dialog),
  which lib/engine now needs (`unknown type or namespace rules`). Not touched here.
- A heredoc-fed `python` edit again turned `\n` inside an `@fmt` string into a real newline
  (twice); the Edit tool was the only safe way to write it.

## 2026-10-03: stats, equipment and talent routines

- **A routine file per concern needs the dispatcher, the registry and the old file edited
  together.** Moving the talent routines out of combat.ctx meant deleting thirteen `run` arms and
  eighty lines by line number (a script), adding the new namespace to dispatch.ctx's chain, and
  re-running routine_registry.py to see no id was claimed twice. The registry catches a double
  claim but nothing catches an arm left pointing at a deleted function until the build runs.
- **Changing a shared helper's parameters breaks callers in files nobody on the task owns.**
  `rt_item::add_to_inventory{ o, item }` gained `w` for the party's shared inventory, and
  lib/ingame/items_actions.ctx (another agent's) stopped compiling. Names in the flat namespace
  have no visibility, so every caller shows up only as a build error after the change.
- **`mut w: world::World` spreads upward.** A function that now reads the party's shared list
  (`party::inventory_of` takes `mut w` because it returns `&w.bag`) forces every caller that held
  `w: *world::World` to become `mut`, up to the routine. A getter returning a pointer into the world
  could take `*World` and return `?*List` without the mutability.
- **A pun is the parameter's name, and a shadowing local is silent.** Adding a parameter `id`
  to a function whose loops declare `let id = @as(i32, s)` would shadow it without a diagnostic
  (renamed to `owner` before it bit); an "already declared in an enclosing scope" warning would
  help.
- **No tuples makes `(item, index)` results small structs everywhere** (`ItemSpell`, `Pick`,
  `Swap`); fine, but each costs a type, a constructor with every field named and a test.
- **A panic from `nwarg::param` names no routine.** `nwarg: the routine has no such parameter`
  (a handler popping argument 0 of a no-argument routine, GetLastDamager) gave only the file and
  line of nwarg itself; finding the caller meant adding a log line before the call in
  dispatch.ctx (the existing `routine ...` log prints after it returns). Logging the routine name
  before the call under `--log routines`, or putting it in the panic message, would save the hunt.
- **Hand-testing a routine without a script needed a whole program.** kotor/out/routinetest (a
  copy of enginetest that pushes arguments on a Vm and calls `routines::dispatch`) was the quickest
  way to see stats, saves, talents and equipment on the module's creatures; a `--call
  Routine(args)` option on enginetest would do it with no new code. As ever, a `\n` in an `@fmt`
  string written through a bash heredoc or python became a real newline (three times).
