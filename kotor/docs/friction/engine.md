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
