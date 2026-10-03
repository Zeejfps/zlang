# Language friction: audio (lib/audio, sndcheck, sndplay, mixtest)

Where ctxlang got in the way while writing the decoders, the mixer and their tools (about 3,000
lines). Each entry: what I wanted, what I wrote instead, how often. Entries that are evidence for a
language change belong in `kotor/FRICTION.md` too; the orchestrator merges them.

- **A read-only struct argument is copied, however big.** Spec §14.6 lets the compiler pass a
  read-only field by copy or by reference; ctxc copies. `fn voice_of { m: Mixer, h: Handle }`
  copied the 300 KB mixer (two 128 KB feed rings) on every call, and `target_gains{ m, v }` did it
  for every voice in every block: the mixer ran at 12x real time instead of 44x until every such
  field became `m: *Mixer` (6 functions in mix.ctx, 3 in snd.ctx for the 40 KB `Stream`, callers
  writing `&m`). Nothing warns: the generated C shows `f173((*l0), l1)`. Passing large read-only
  structs by reference (above some size), or a warning, would remove a performance cliff that
  reads like idiomatic code.
- **A const isn't a place, so a const table can't be sliced or pointed into.** The decoder's
  tables (Huffman lookups, IMDCT cosines, windows, `x^(4/3)`) are consts, which is right: computed
  while compiling, static in C. But a hot loop that wants `let row = COS36[a..a + 18].ptr` (one
  bounds check, then unchecked reads) gets "`COS36` is a const, not a place", so every read is
  `COS36[a + k]` with its own check; copying the table to a local per call costs more. 5 loops. A
  read-only view of a const (`[]T`, which it already is in C) would do.
- **A struct holding an enum has no zero value.** `snd::Stream` holds `wav::Info`, whose `codec`
  is an enum, so `let mut s: snd::Stream` is an error, and so is every struct around it
  (`mix::Voice`). Tools get one from `snd::make` (allocated, then opened in place) instead of a
  stack local; the mixer's voices are allocator memory that `make` initialises field by field. 3
  places. An enum's first variant as its zero, or `let mut x: T = undefined`-style opt-out, would
  do.
- **`@as` from float to integer is an out-of-line call.** `@as(usize, pos)` for an `f64` sample
  position compiles to `ctx_f2i_u(...)` (range-checked, in ctxrt.c, not inlined), twice per output
  sample per voice. The resampler moved to 32.32 fixed-point `u64` positions to avoid it; the
  float-to-int panics are rightly checked, but an inline fast path would keep float code fast.
- **`is` can't test a `!T`.** "does this fail?" is `match f{} { ok => { false } err => { true } }`
  (2 places in mixtest). `e is err` reading as `is` does for unions would be natural.
- **`return try f{}` in a bare-`!` function is "expression has no value".** It has to be
  `try f{}` then `return` (2 places in sndplay).
- **No math at compile time.** Const tables want `cos`, `sqrt`, `cbrt`, `ldexp`, which are libm
  extern fns and can't run while compiling (§14). mp3.ctx carries its own f64 versions (a cosine
  series over an exactly reduced argument `cos(pi n / d)`, Newton square and cube roots; 60 lines).
  They work well, and computing 10,000-entry tables at compile time is fast (under a second); a
  std `math` usable in consts would save every table-building library from writing them again.
- **Positive: computed const tables.** `const POW43: [8207]f32 = make_pow43{}` runs while
  compiling and lands in C as a static array: no init step, no state to thread through the
  decoder, no generated source for formula tables. Only data that isn't a formula (the Huffman
  codes, the synthesis window) needed a generator script.
- **Writers for `@fmt` by exact type** (already in kotor/FRICTION.md): sndcheck needed its own
  `Fixed`, `Right` and `Pad` writers for a table, and sndplay one for `c::String` (tools/common
  has none).
- **Error-set inference keeps functions from being callbacks** (spec §8 rule 12). The first design
  had `audio::update` take a `&fn{ frames: []i16 } -> !` to queue samples; `sdl::queue_audio{ &sdl,
  out, _ }` can't be one because its error set is inferred. Returning the frames to queue, or
  having `audio` call SDL itself, is cleaner anyway, so this cost nothing here.
