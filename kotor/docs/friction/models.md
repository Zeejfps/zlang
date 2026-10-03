# Language friction: models (lib/mdl, tools/mdlcheck, tools/animcheck)

What ctxlang made awkward while writing the MDL parser (about 1,500 lines), the animation
library (about 450) and the two corpus tools. Each entry: what we wanted, what we wrote, how
often. For the language's own list see `kotor/FRICTION.md` and `ctxlang/FRICTION.md`.

- **Allocations come back dirty.** `alloc::resize` from an arena returns whatever bytes the
  arena held before: after `arena::reset`, or where `fs::read_all` grew a buffer and left the old
  one behind. Spec §11 says no memory is uninitialized, but heap memory is. The first corpus run
  panicked on an index read from a "fresh" counter array. Written instead: a `make(T, S)` helper
  that zeroes through `slice::fill(u8){ s = slice::cast(T, u8){ s = out }, v = 0 }`, used for
  every array the parser allocates (about 30 call sites), and the same `slice::fill` after two
  allocations in mdlcheck. A zeroing `alloc::make` (or zeroed results from `resize` when it
  grows) would remove the trap.
- **u32 size arithmetic panics on hostile counts.** A parser reads counts as `u32` and computes
  `16 * count`, which overflows `u32` and panics on garbage instead of failing the range check.
  Written instead: a `usize_at` reader for every offset and count (about 60 reads), so sizes are
  computed in 64 bits. Easy to forget one; a lint, or reading as usize by habit, is the fix.
- **A map lookup with a key from a local buffer is "derived from" that buffer.** `map::get{ m,
  key }` where `key` is a lower-cased copy in a `[64]u8` local returns a `?*mdl::Model`, which
  the escape check (§14 rule 2: a call's result is derived from its read-only arguments) ties to
  the buffer, so it can't be returned. Written instead: the map holds an index into a list of
  pointers, and the pointer is read from the list (animcheck's model cache). Once.
- **A file read through a path in a local buffer is "derived from" the buffer.** The same rule
  makes `fs::read_all{ ..., path = local_path }`'s bytes, and the model parsed from them, derived
  from the path's stack buffer, so a loader can't return the model. Written instead: path
  buffers allocated from the arena (animcheck before it moved to lib/res). The rule is right for
  a function that returns into its argument; a way to say "the result doesn't borrow this
  argument" (an attribute on a field) would fit functions like `read_all` and `map::get` whose
  results never point into their keys.
- **A `let mut` optional doesn't narrow** (§8 Optional rule 3). In the node reader the mesh,
  light and emitter are `let mut x: ?T = null`, set in one branch and used after; `if x != null {
  use x }` doesn't type-check. Written instead: `match x { some{ value } => { ... } null => {} }`
  three times.
- **`match` takes no integers** (as in kotor/FRICTION.md). Controller ids select one of 47
  emitter properties: 47 lines of `if id == 80 { props.alpha_end = x; return true }`.
- **One namespace per file.** `mdl` is one 1,500-line file holding the types, the parser and its
  byte readers; the animation code had to become a second namespace (`mdl_anim`) to live in a
  file of its own.
- **No `[]u8` writer into a Builder.** The tools format failure examples into a
  `utf8::Builder` and print names that are bytes; each tool carries a `#write fn push_bytes`.
- **Generic struct literals need their arguments.** `Parser(S){ ... }` inside `parse(S)`: the
  parameter isn't inferred from a field of type `*mut S`. Minor; twice.

What worked well: `parse_traced`'s claims made "every byte accounted for" a 30-line check; bound
functions made the supermodel lookup (`lookup_model{ &fs, &cache, _ }`) and event callbacks
(`count_event{ n = &fired, _ }`) exactly as short as they should be; the escape and exclusivity
checks caught nothing real but cost little; the generated C runs the whole-corpus check in 3.6 s
(the Python probe takes about 7 minutes).
