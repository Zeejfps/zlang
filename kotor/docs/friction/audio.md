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

## Resolved: read-only views of const arrays

Since `549e1b5`, const arrays can be sliced, including array fields and nested arrays in a const. The view
borrows immutable static storage without copying; it can outlive the function that made it.
`&C` remains an error. Views can be used during compile-time computation, but the evaluator
cannot retain them in another const's stored value (ctxlang spec §12, Slices, and §14).

The long MP3 IMDCT now takes one checked view of its 36-entry window before the output loop.
The intermediate product is explicit to preserve f32 rounding before overlap-add: simplifying
an expression can otherwise let Clang fuse multiply-add and change a few PCM samples by one.

Measured on macOS arm64 with Apple Clang at `-O2`, seven alternating runs after warmup:

| Workload | Before, median | Window view, median | Speedup |
|---|---:|---:|---:|
| 20 million long IMDCT calls | 1.1224 s | 0.9526 s | 1.178× |
| Six-second synthetic stereo MP3, decoded 128 times | 1.0843 s | 1.0708 s | 1.013× |

All decoded PCM bytes matched. These are synthetic measurements, not the purchased game's
audio corpus. A cosine-row view was also measured: Clang already removes those index checks;
that rewrite slowed the isolated transform about 6.5% and gave no full-decoder improvement,
so the cosine loop retains its array indexing.

Reproduce with `python3 kotor/tools/py/constviewsbench.py --before 5ae1c76`. It generates its
input with ffmpeg and saves sources, generated C, assembly, and individual timings under
`kotor/out/constviewsbench/`; build time and PCM verification are outside the timed runs.
