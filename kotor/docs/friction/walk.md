# Language friction: walkmeshes (`lib/walk/bwm.ctx`, `tools/walkcheck`)

Where ctxlang got in the way while writing the BWM library (about 820 lines) and its corpus check
(about 1,080 lines). Each entry: what I wanted to write, what I wrote instead, how often.

- **`#write` fns over `Io` can't live in a library.** The check's code is a library that other
  tools build in (`tools/mdlcheck` adds `../walkcheck/lib`), and tools declare their own writers
  over `Io` (glspike's and mathcheck's top-level `namespace out`). An `@fmt` sees every writer its
  code could name, a top-level namespace's included, so a library's `put_u32 { mut io: Io, ... }`
  next to a program's is "@fmt has two writers of strlit to Io: `lib::put_text` and
  `out::put_text`", in the library and in the program alike (repro:
  `kotor/out/repro/walk_writers/main.ctx`). Wrote instead a sink of the library's own,
  `walkcheck::Con { io: Io }`, with 14 one-line writers (`io::print_u64{ io = &c.io, n }`), and
  `let mut con = Con{ io }` at the top of `run`. Once per library that prints. Writers over `Io`
  in std's `io` would remove the need for every program and library to declare them.
- **Signed indices and unsigned counts don't mix.** The format's links are i32 with -1 for none
  (AABB children and leaf faces, adjacency, perimeter edges), counts are `usize`, and neither
  widens to the other, so every range check is `x >= 0 and @as(usize, x) < n` and every use
  `@as(usize, x)`: 18 `@as(usize, ...)` in bwm.ctx and 16 in check.ctx. In the other direction
  `usize` doesn't widen to `i64`, so passing a face or node number as an i64 example payload is
  `@as(i64, f)`: 50 times in check.ctx.
- **An optional accumulator can't narrow.** Wanted `let mut best: ?Floor = null` and
  `if best == null or h > best.z { best = ... }`; a `let mut` optional doesn't narrow (ctxlang
  FRICTION #7), so `find_face_under` and `cast_ray` each keep `found: bool` beside a dummy
  `best`, and a `beats_floor{ found, best, ... }` helper. 2 places, plus 2 `same_floor` /
  `same_hit` helpers comparing two optionals.
- **No `match` on integers.** The AABB split plane (1, 2, 4, 8, 16, 32) becomes an axis and a sign
  through `if plane == 1 { ... }` chains: `bwm::is_left_nearer` and `walkcheck::plane_axis`, six
  arms each. (Known: kotor/FRICTION.md, glspike.)
- **An enum's size can't size an array.** The check's failure classes are an enum indexing
  `[N]u64` tallies. `@as(usize, Class::count)` isn't folded, so `N` is a hand-written
  `const CLASS_COUNT: usize = 56` checked against the enum at run time; it had to be bumped by
  hand when a class was added (once so far). Folding `@as` of an enum value, or `@count(E)`, would do.
- **A typed slice allocation is long.** `alloc::resize(T, S){ realloc, &heap, mem =
  slice::empty(T){}, count }` for every table; both files grew a `make(T, ...)` helper (19 uses in
  bwm.ctx, 9 in check.ctx). A std `alloc::make(T, S){ realloc, &heap, count }` (and a filled one)
  would serve every parser.
- **An `if` of two equal-length literals as an `@fmt` hole** (ctxlang FRICTION #11):
  `if differs { "DIFF" } else { "    " }` is a `[4]u8` with no writer; needed
  `let tag: []u8 = if ...` first. Once.
- **Hex literals aren't in the spec.** §11 Literals shows only decimal, so the first draft wrote
  `4294967295` and `2654435761`; the lexer accepts `0xFFFFFFFF` (and `0b`, `_`). Docs only.
- **Reading an f32 or i32 from its bits takes a pointer**: `let u = u32_at{ ... }` then
  `@cast(*f32, &u).*`. Twice (bwm's `f32_at`, `i32_at`); fine, but a `@bitcast(f32, u)` would say it.
