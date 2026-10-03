# Language friction: Bink video and audio (`lib/video`, `tools/bink2png`, `tools/binkcheck`)

Where ctxlang got in the way while writing the Bink decoders (about 2,200 lines of library and
800 of tools). Each entry: what we wanted, what we wrote instead, how often.

- **An error whose payload holds a slice taints every `try` near a local.** `error
  bad_header{ what: []u8 }`, only ever given string literals, made `try read_exact{ &fs, file,
  into = head[..44] }` an error: "`try` would return an error that may hold the address of local
  `head`", because the function's error set now has a pointer payload and the call's arguments
  derive from a local. The same with `bink_tables::not_found{ table: []u8 }` at the caller, in
  another file. Replaced by one payload-free error per case (`bad_frame_count`,
  `too_many_tracks`, six `no_*` errors for the tables). Twice; it will recur wherever an error
  names what went wrong. Knowing that a `strlit`-typed payload (or a `[]u8` built only from
  literals) points to static memory would fix it; so would a `strlit` payload type.
- **Every integer operation in a codec is checked, so exact C arithmetic needs `@wrap_*`.** The
  IDCT must wrap like the format's C (and must not panic on a corrupt block): its 8-point
  butterfly is 30 `@wrap_add`/`@wrap_sub` calls and 5 `@wrap_mul`s, `a3 = mul11{ a =
  @wrap_sub(s[2], s[6]), k = K_SQRT2 }` for `a3 = MUL(A1, s2 - s6)`. A wrapping block or a
  wrapping integer type (`w32`) would read as the arithmetic it is. About 50 uses.
- **`@as` to widen or from a literal calls an out-of-line checker.** `@as(usize, x)` for a u32
  emits `ctx_as_u(...)`, a function call, even where the value always fits. In hot loops we
  widen through typed `let`s (`let b0: u64 = data.ptr[i]`) and narrow with `@trunc`. A
  conversion the compiler can prove lossless could be a plain cast.
- **Float to integer has no inline form.** `@as(i32, x)` for an f64 calls the out-of-line checked
  converter, which took about 20% of the audio decoder's time (one call per sample). It now
  rounds by adding 1.5 * 2^52 and reading the low bits through `@cast(*u64, &f).*`. An unchecked
  or rounding conversion (`@round`, `@trunc` for floats) or a bit-cast builtin would do.
- **A `mut` struct field is a pointer, and the C is built with `-fno-strict-aliasing`**, so gcc
  reloads the bit reader's fields after every store through any pointer (every `f64` written to a
  coefficient buffer): about 10% of the audio decoder's time. Worked around with a local copy,
  `let mut rd = r` and `defer r = rd`, in the hot function. The video decoder doesn't bother (it
  is fast enough), but it pays the same cost. Restrict-qualifying `mut` context fields (spec 3.1
  already forbids two overlapping ones) would let gcc keep them in registers.
- **No math functions in std** (as the spike found): the audio decoder declares `cos`, `sin`,
  `sqrt` and `pow` as extern fns itself.
- **No bitwise not.** Rounding down to even is `x / 2 * 2` (or `x & 0xFFFFFFFE`); `~` would say it.
- **No `for` loop.** Every loop over a block is `let mut i: usize = 0; while i < 8 { ...; i = i +
  1 }`: about 70 in bink_video.ctx alone, each three lines of bookkeeping. A counted loop
  (`for i in 0..8`) would halve the decoder's loop code and remove a class of forgotten
  increments.
- **`match` takes no integers** (the spike noted it too): the block-type dispatch is a 10-arm
  `if kind == SKIP ... else if` chain over `const`s.
- **Punning needs a bare name.** `bink::next{ &fs, &movie }` doesn't fill a field named `m`;
  it needs `m = &movie`, and `&m.video` can't pun at all (`d = &m.video`). Natural, but we wrote
  it wrong 8 times before it compiled; the error ("`next` has no field `movie`") is clear.
- **No way to join a path from parts without an allocator.** An array literal is not a place, so
  `join{ parts = [a, "/", b][..] }` doesn't work, and fixed-length `[N][]u8` parameters don't
  take shorter arrays. Both tools have a small `Text { buf, len }` with `add`, over a stack
  buffer. A std helper over a caller's buffer would do.
- **An array of string literals needs its length counted by hand** (as in the spike): FFmpeg's
  argument list is `let with_audio: [20][]u8 = [...]`; without the type the literals are `[N]u8`
  arrays of different lengths ("expected [6]u8, got [2]u8"). `[_][]u8` would help.
- **`@fmt` to standard output**: each tool again declares `namespace out` writers (as the spike
  does), and a `u8` prints as a number, so the revision letter goes through `let revision =
  [h.revision]` and `revision[..]`.
- **`_ = f{} iferr {}` on a bare `!`** is "nothing to discard: this returns no value"; it must be
  `f{} iferr {}`. Minor, but the two forms look alike. 4 times.
