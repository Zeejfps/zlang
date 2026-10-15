# Language friction

Where ctxlang got in the way: while writing ctxc, and while porting KOTOR (kotor/). Each entry is
evidence for a spec or std change: what was wanted, what was written instead, and how often.
Resolved entries are removed, saying which commit fixed them; git history has them.

Entries are ranked by how often they are hit: first by how many of the 17 write-ups this file
merges hit them, then by how many sites they cost. The write-ups are ctxc's own list and the
KOTOR port's, by subsystem: **ctxc**, **glspike** (the platform and GL spike), **engine** (world,
routines, scene, saves), **data** (resources and formats), **audio**, **dialog**, **gui**, **hud**
(HUD and in-game menus), **chargen**, **minigames**, **models**, **render**, **rules**,
**screens**, **script** (NCS and the VM), **video** (Bink) and **walk** (walkmeshes). Counts are
as the write-ups gave them. Ranking by count understates #27: it is the one entry that gives a
wrong answer instead of a compile error.

Checked against ctxc at `2076e06`. Fixed since the write-ups and so not listed: integer `match`;
read-only arguments too big to copy, now passed by reference; `@fmt` writers onto an `Io` for
every hole type, `c::String` included, and a `[]u8` writer into a `utf8::Builder`; multi-line
string literals (`2cf7326`); slices of const arrays (`549e1b5`); `fs::seek` and `read_at`
(`c0b8b45`); `else` at the start of a line; `&p.*` as an argument; `error` as the type of any
error; a callee's fresh allocation returned though an argument viewed a local, and `try` of a
call whose errors' payloads only ever hold literals (the escape check's flow summaries, spec §14
rule 2). Fixed after the check: a string literal with no type expected is a `[]u8`, not a
`[N]u8`, so `if c { "yes" } else { "no" }` joins; a `let`'s or a const's type may be `[_]T`, its
length the initializer's; and an array literal where a slice is expected is a view of its array,
static when every element is a constant and a hidden local otherwise, so `pages = [1, 2, 3]` is
a `[]u32` argument. Optionals that don't narrow (a `let mut`, a field) unwrap with `if let`
(`7bc9525`), and the error where one is used as its `T` says so (`6a31c62`); a `?T` compares
with a `T`, which narrows it (`1f66e0d`); and testing a narrowed one as an optional says it
isn't null there (`8357131`). A struct's field may have a default that a literal ending in `..`
takes (`02abd47`), and every type whose bytes all zero are a value of it has that as its zero
value, enums' and unions' included, with an empty slice a const (`7c6eb91e`): what remains of
naming every field is a pointer, a function or a list, which have no zero value by design.
A number's bits as another type of its size are `@trunc` between integers, which keeps every
bit, and std's `math::f32_from_bits` and the like for floats (`e6da31a7`), so `@as(u32, -1)` and
a pointer `@cast` are no longer the ways to it.

## Ranked

1. **Punning `&x` needs the callee's field name, and `&a.b` doesn't pun at all.** `deal_hand{
   &g.rng, &g.player, deck }` is "expected '}', found '.'"; `next{ &fs, &movie }` for a field `m`
   is "has no field `movie`". Written `rng = &g.rng`, `m = &movie`. Each file's first compile
   trips on it, one call at a time; a library whose fns take `mut p: Panels` makes callers name
   their value `p`. *Partly:* the errors say what to write ("a pun is a name alone: write `rng =
   &g.rng`", "`next` has no field `movie`: write `m = &movie`", from the fields nothing supplies),
   so each fix is mechanical, but each call is still written out. A std convention (name a
   builder `b`) shrinks it; punning a place's last name (`&g.rng` fills `rng`) would remove most
   of it. *Hit by 12:* ctxc (about 30, and
   `mutex::lock{ &shared.lock }`), engine (about 40), data (about 40), dialog (about 36), gui
   (about 25), hud (about 40), chargen (4), minigames (about 46), rules (about 40), screens (about
   15), script (8), video (8).

2. **The escape check ties a lookup's or a read's result to a local key or path.** A call's
   result counts as derived from its read-only arguments: `map::at{ m, key = k[..] }` with `k` a
   local array, `fs::read_all{ path = buf[..n] }`, `font::load{ name = buf[..] }`,
   `twoda::get_string{ column = buf[..] }` and a bound lookup by a name copied to a local all
   return values "holding the address of local" the key, though they point into the map, the
   heap or the cache. So do a by-pointer argument (`build{ doc = &doc, bytes }`) and an
   out-pointer (`numkeys = &n`). Written: keys and paths copied to the heap first and freed with
   a `defer`, maps holding an index into a list of pointers, const tables of column names,
   `mut` fields (which don't count). *Partly:* the flow summaries fixed fresh allocations and
   literal-only errors, and map lookups and reads by path borrow nothing since an extern fn or
   an unbound fn value (`map`'s `hash` and `eq`, the OS's file calls) is taken to store an
   argument only where it reaches a mutable place that holds a pointer (`712e40a`; KOTOR's
   copies went in `40e80d0`). An out-pointer to a number borrows nothing. Still tied: a lookup
   through a fn value or `&fn` whose result holds a pointer, an extern's pointer result, and a
   value read through a pointer to a local (`read_info{ doc = &info_doc }` in lib/save, which
   copies the module name). A `#noescape` field attribute, checked on a body and part of a fn
   type, was weighed and put off: only KOTOR's model lookup (`&fn{ name: []u8 } ->
   ?*mdl::Model`, 7 declarations) and two std externs would use it. *Hit by 8:* glspike,
   engine (about 5), data (5), dialog (7), gui (3), hud, minigames (7), models (2).

3. **Checked arithmetic costs in code that must be exact or fast.** Every integer `+ - *` and `@as`
   to an integer is checked. Arithmetic that must wrap as the format's C does is
   `@wrap_add(@wrap_mul(state, 214013), 2531011)`, and an IDCT butterfly 35 `@wrap_*` calls; a VM's
   indices, already bounds-checked, needed `@wrap_*` to go from 184 to 450 million instructions a
   second: a checked `+` is inline, an `add` and a branch, but the branch is on every operation,
   and can keep gcc from vectorizing (a test loop's checked adds stayed scalar). `@as(i32, f)` from
   a float is inline too (`823c678f`; it was an out-of-line call that took about 20% of the audio
   decoder) but still two compares (an `f32` widened to double first), and no integer conversion
   rounds or clamps instead, so the Bink audio rounds by adding 1.5 * 2^52 and reading the bits.
   u32 size arithmetic on a hostile count panics instead of failing the range check. The other way,
   the compile-time evaluator detects overflow by hand (`signed_arith` in ctxc/eval.ctx, a sign
   test per operation and a division for `*`). `ifoverflow` (`fff522fc`, spec §11 Overflow) now
   does both: `count * 16 ifoverflow { return too_big{ count } }` takes the arithmetic and `@as`
   written before it. A wrapping type or block and rounding float conversions would help. A
   lossless widening (`@as(usize, x)` from a `u32`) costs nothing now. *Hit by 6:* ctxc, audio,
   minigames, models (about 60 reads), script (75), video (about 50).

4. **Allocation needs helpers every program writes.** `alloc::resize` from an arena returns the
   bytes it held before (after `reset`, or where `read_all` grew a buffer), though spec §11 says
   no memory is uninitialised: the first model corpus run panicked on a "fresh" counter array,
   so the parser zeroes every array it allocates. A typed allocation is `alloc::resize(T, S){
   realloc, &heap, mem = slice::empty(T){}, count }`, so parsers grew a `make(T)`. `list::items`
   is the first `len` of a `cap` allocation, so a list returned as a slice is resized first to be
   freed rightly (`lists::take`, written three times). `fs::list`'s result can't be freed: it is
   two allocations, the outer read-only, and a `*T` can't go back to `*mut T`, so slices that
   will be freed are `[]mut` from allocation to free though nothing writes them. No arena mark
   and restore. A zeroing `alloc::make`, `list::take`, `fs::list_free` and an arena mark would
   serve every parser. *Hit by 5:* models (about 30), walk (28), data (14, and 8 fields), render
   (1), gui (1).

5. **`@fmt` formats only by type.** There are no width, padding, hex or fixed-point specs
   (`{:<16}`, `{:08x}`, `%18.9f`), so a program writes a wrapper type and a writer for each
   (`world::Pad3`, `Fixed`, `Right`, `Pad`, `Hex`) or pads by hand; std's padded writers
   (`utf8::push_padded`, `push_hex`) are for a `Builder` only. A sink of the program's own needs
   a writer per exact type (a `u16` hole had none). Every `@fmt` onto the console needs `_ =`
   though its writers can't fail (35 in the spike). std's float writer prints 100.0 as `1e+02`.
   *Hit by 5:* glspike (35), engine (2), audio (3 writers), data (1), script (about 15, and six
   writers).

6. **Small `!T` forms that don't exist.** `_ = f{} iferr {}` (discarding a failing call's value)
   is "this branch must end in a value", so it is `iferr { return }` or `iferr 0`; on a bare `!`
   it is the reverse, `f{} iferr {}` without the `_ =`. `if f{} is ok` is "`is` cannot test a
   `!T`", so it is a `match` with `ok => { true } err => { false }`. `return try f{}` in a function
   returning a bare `!` is "expression has no value", so it is `try f{}` then `return`. *Hit by 5:*
   engine (20), data (24, 5 and 1), audio (2 and 2), script (3), video (4).

7. **Exclusivity blocks a context and a part of it in one call.** `f{ &e, xs = &e.list }` is two
    mut references to `e`, and so is a bind beside a `&` of what it holds (`routines::call{
    &world, _ }` then `tick{ &world, ..., engine }`). Written: a struct holds its heap as a `*mut`
    (`Parser.heap`), the World and the VM stub live behind raw `*mut` pointers the checker doesn't
    track, and `fs = &w.fs` goes only in calls without `&w`. Sound, but it is the checker worked
    around for the program's central object. Split borrows would remove it. *Hit by 5:* ctxc,
    engine, hud, screens (about ten calls), script (7 fns).

8. **Sources come by directory, and a directory is one flat namespace.** `build::add_sources`
    takes a directory and `build::exe` one without its subdirectories, so a tool can't pick one
    file (the dialog panels and lip sync moved to directories of their own), and one half-written
    file breaks every build that adds its directory (each rules agent built from a private copy).
    A directory's files share one namespace with no file-private names, so two agents writing
    `put_*` helpers coordinate names by message; a file can't keep private state either, so every
    cache goes in `World`, the file every agent needs; `mdl` is one 1,500-line file because a
    namespace is a file's. *Hit by 5:* engine (2), dialog (2), models, rules, script.

9. **No math in std, and none while compiling.** No `cos`, `sin`, `sqrt`, `pow`, `ceil` or
    `trunc` (std's math has `is_nan` and the like): the Bink audio declares libm's as extern fns,
    and MP3's const tables, which run while compiling and can't call one, carry their own f64
    cosine series and Newton roots (60 lines). No integer `@min` or `@max`: `if a < b { a } else {
    b }` by hand, and a generic std one can't compare an opaque `T` (§9). *Hit by 5:* ctxc, audio,
    video, rules, render (about 6).

10. **Signed and unsigned integers don't mix.** Game data is signed (-1 for none, modifiers) and
    every table is indexed by `usize`, which an `i32` isn't (`a[i]` is "expected usize"), and
    neither widens to the other: every lookup is `a[@as(usize, i)]` after a range check, and a
    `usize` going into an `i64` payload `@as(i64, f)`. A typed integer const doesn't convert where
    its value fits (`@as(i32, gl::LINEAR)`), and `@as(i64, b)` refuses a `bool`, so counting is `if
    b { 1 } else { 0 }`. An index that takes any integer type with its bounds check, and consts
    that convert as literals do, would remove most. *Hit by 4:* glspike (11), rules (about 150,
    and about 60 bools), walk (84), video.

11. **No bitwise not.** Clearing a flag is `f & (4294967295 ^ bits)` or `x & 0xFFFFFFFE`; `~`
    would say it. *Hit by 4:* gui (8), rules (4), screens (3), video.

12. **`iferr` and `ifnull` don't chain, and bind tighter than comparison.** A `!?T` wants `f{}
    iferr { return } ifnull { return }`, which is "expected a newline or ';' after statement,
    found 'ifnull'", so it is two statements; with parentheses it groups right to left. `x ==
    f{} ifnull y` is `x == (f{} ifnull y)`. *Hit by 4:* engine, data (3), dialog (9), gui (2).

13. **A condition continued on the next line must break after the operator.** `if a\n or b {`
    is a parse error, since a call's `}` ending a line starts the block, and the error points at
    the wrong place. *Hit by 3:* data (1), rules (2), script (1).

14. **Enums only compare for equality, and their count isn't a constant.** Sorting by an enum is
    `@as(u8, a.class) >= @as(u8, b.class)`; `@as(usize, Class::last) + 1` isn't folded, so a
    tally array's length is a hand-kept `const CLASS_COUNT: usize = 56`, checked against the enum
    at run time. `@as(Kind, n)` lowers to one compare per variant, which the C backend emits as a
    chain (62 for `tok::Kind`; the lexer now indexes const tables instead); a contiguous enum
    could be one range check. *Hit by 3:* ctxc, data (1), walk (1).

15. **Small syntax.** A bare `{ ... }` block isn't a statement, so each section became a fn;
    `defer if c { ... }` is a parse error, so it is `defer { if c { ... } }`; a match arm that is
    one expression needs braces (`a => { "A" }`); `try f{}.x` parses as `try (f{}.x)`, against
    the spec's own example. *Hit by 3:* dialog (2), minigames (1), render (2).

16. **Some errors don't point at the cause.** A build.ctx missing one source directory gives
    "unknown type or namespace mg" at every use (thirty errors) instead of one saying no file
    declares `namespace mg`; a file in the middle of a merge gives nine syntax errors at `<<`
    with no hint of a conflict; finding that a `mut heap: Heap` field takes `&heap.*` from a
    `*mut Heap` took three tries. *Hit by 3:* engine, hud, chargen.

17. **A `&fn` can't be a struct field, and bind records are never freed.** The VM's engine bind
    travels as its own context field beside `mut w` and `mut vm` (about 15 engine fns, 6 in
    ncsrun); ExecuteScript binds a new engine per call and leaks its record, and the scene binds
    `mdl_cache::get` once per (model, animation). *Hit by 2:* engine, script.

18. **Changing a shared fn's signature breaks callers nobody on the task owns.** No default
    arguments, so a helper that gains an input edits every call site, in other owners' files; no
    visibility, so callers show up only as build errors; a fn that starts returning a pointer into
    `w` needs `mut w`, which spreads to every caller up to the routine. *Hit by 2:* engine (2),
    hud.

19. **`is` is a keyword,** so `let is = gff::get_struct{ ... }` and `fn is{ a, b }` are "expected a
    name, found 'is'", far from the cause. *Hit by 2:* gui (1), render (1).

20. **Hex literals aren't in the spec.** The lexer takes `0xFFFFFFFF`, `0b` and `_` separators,
    but §11 Literals shows only decimal, so drafts wrote `4294967295`. *Hit by 2:* glspike, walk.

21. **No methods** (§16 Q4). `list::push{ list = &xs, item }` everywhere: ctxc makes about 580
    `list::` and `map::` calls and 150 `slice::` ones. `xs.push{ item }` would shrink code a lot.
    *Partly:* slices are built in (spec §12), so `slice::get{ s = xs, i }` is `xs[i]`. *Hit by 1:*
    ctxc (about 730).

22. **A GL function is written three times:** a capability field with its C type, then `name =
    @cast(_, try proc{ get_proc, name = "glName" })` in the loader, the C name the field's in
    another case. An attribute on the field (`#c::symbol{ name = "glClear" }`; fields carry
    attributes since `304f48d`) and a generator over `build::declarations` would make a binding
    one line per function. *Hit by 1:* glspike (132 loader lines).

23. **No `for` loop.** Every loop over a block is `let mut i: usize = 0; while i < 8 { ...; i = i
    + 1 }`: three lines of bookkeeping, and a class of forgotten increments. *Hit by 1:* video
    (about 70 in bink_video.ctx).

24. **A diagnostic takes three lines** in ctxc. *Mostly solved:* `@fmt` without a sink is a writer
    (spec §13), so 163 of 197 sites are one line (`errorf{ &c, at, msg = @fmt("...", args) }`).
    About 50 keep a builder: reports through `flow_error` and `escape_error`, which take a
    `utf8::String`, and messages built from more than one `@fmt` or with a loop between. *Hit by
    1:* ctxc (about 50).

25. **An inferred slice type is too mutable.** `let mut bs = list::items{ list = xs }` gives `bs`
    `[]mut T`, so a later `bs = f{}` with a `[]T` result is an error; the same for
    `slice::empty(T){}`. Inferring the type from every assignment, as literals are, would fix it.
    *Hit by 1:* ctxc (about 30).

26. **No scoped lock.** Every public fn of the mixer starts with `mutex::lock{ mutex = &m.lock }`
    and `defer mutex::unlock{ mutex = &m.lock }`, naming the lock twice. A block form (`with`-like)
    would do without destructors. *Hit by 1:* audio (21 pairs, kotor/lib/audio/mix.ctx).

27. **A read-only argument can be copied before a later argument changes it.** Arguments are
    evaluated in order, so `types::prune{ s = c.ty, t = expr{ &c, e } }` copies the type store,
    then `expr` adds a type to the real one, and `prune` indexes the stale copy out of bounds.
    §3.1 checks overlap between one call's arguments only, not a `&c` inside a nested call. The
    fix is a local first (`check::typed`). Still silent: `show{ n = c.n, z = bump{ &c } }` passes
    the old `c.n`. A rule that rejects this, or evaluates nested calls before plain arguments,
    would have caught eight such calls. *Hit by 1:* ctxc (8). The only entry that gives a wrong
    answer.

28. **Float-to-float `@as` reads as fallible, and the spec says it is.** §13 says `@as` "panics if
    the value isn't representable in T", but `@as(f32, 1e300)` gives `inf`. A spec fix: say float
    to float rounds (and overflows to infinity), or give it a separate conversion. *Hit by 1:*
    ctxc (5).

29. **A `mut` argument can't be a temporary.** `f{ x = g{} }` for a `mut x` has no place to point
    to, so it is `let mut tmp = g{}` first. *Hit by 1:* rules (4).

30. **Locking a structure needs `mut`.** A query that only reads a shared structure
    (`mix::is_playing`, `played`, `feed_room`) must lock its mutex, which takes `mut mutex`, so it
    takes `mut m: Mixer` and its signature no longer says it changes nothing. A read-only `*T`
    that may still lock its mutex field would say it. *Hit by 1:* audio (4 fns).

31. **No tuples.** `let (a, b) = if two { (x, y) } else { (z, w) }` is two `let`s on the same
    condition, and an `(item, index)` result a small struct with every field named (`ItemSpell`,
    `Pick`, `Swap`). *Hit by 1:* engine (2 entries).

32. **No structural equality or hashing.** Interning types in a map keyed by a union took a
    hand-written `hash` and `eq` (`types.ctx`, about 90 lines), `eq` a match inside a match per
    variant; `p == q` on a struct is "P has no built-in equality". Derived `==` for structs and
    unions without pointers, a builtin `@hash`, or PLAN.md 3.2's reflection deriving them in a
    build program would remove it. *Hit by 1:* ctxc.

33. **A `mut` struct field is a pointer, and the C is built with `-fno-strict-aliasing`,** so gcc
    reloads the bit reader's fields after every store through any pointer: about 10% of the Bink
    audio decoder, worked around with a local copy (`let mut rd = r`, `defer r = rd`).
    Restrict-qualifying `mut` context fields (§3.1 already forbids two overlapping ones) would let
    gcc keep them in registers. *Hit by 1:* video.

34. **A pattern can't bind a mutable local.** *Mostly solved:* `ifnull` unwraps into any `let`,
    including `let mut`. A pattern's own bindings are still read-only (`let some{ value = mut g }
    = ...` is a syntax error), and PLAN.md 1.1 would take the rest. *Hit by 1:* ctxc.

35. **No pointer from an integer.** GL takes buffer offsets as `const void *`; the binding
    declares them `offset: usize`, which works only because 64-bit ABIs pass the two alike.
    *Hit by 1:* glspike.

36. **A typed function value can't be cast.** A thread's start record holds `fn{ data: *mut T }`
    for any `T`, read through `@cast(*fn{ data: *mut u8 }, &run).*`, since `@cast` takes pointers
    only. Every `fn` value is one pointer, which a cast of `fn` values whose fields differ only in
    pointer types could say outright. *Hit by 1:* ctxc (std/thread.ctx).

37. **`null` can't name a variant,** so `types::Type`'s is `nil`. Cosmetic. *Hit by 1:* ctxc.

38. **The mutex isn't fair, and std doesn't say so.** Windows' slim locks let a thread that
    unlocks and locks again keep the lock: mixtest let the other thread in 97 times in 3,000
    blocks, and about 1,000 once it yielded between blocks. Worth a line in std's `mutex` comment.
    *Hit by 1:* audio.
