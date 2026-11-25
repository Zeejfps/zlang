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
as the write-ups gave them.

## Ranked

1. **Punning `&x` needs the callee's field name.** `next{ &fs, &movie }` for a field `m` is "has
   no field `movie`", and `deal_hand{ &g.rng, &g.player, deck }` for a field `side` the same for
   `player`. Written `m = &movie`, `side = &g.player`. A library whose fns take `mut p: Panels`
   makes callers name their value `p`. *Partly:* a place's last name puns (`&g.rng` fills `rng`,
   `w.d` fills `d`: spec §3, rule 6), which was most of it, and the error says what to write
   ("`next` has no field `movie`: write `m = &movie`", from the fields nothing supplies), and
   `ctxc check --fix` applies it (80510973), so each fix is mechanical. A std convention (name a
   builder `b`) shrinks the rest. *Hit by 12:* ctxc
   (about 30, and
   `mutex::lock{ &shared.lock }`), engine (about 40), data (about 40), dialog (about 36), gui
   (about 25), hud (about 40), chargen (4), minigames (about 46), rules (about 40), screens (about
   15), script (8), video (8).

3. **A sink of the program's own needs a writer per exact type** (a `u16` hole had none), and
   every `@fmt` onto the console needs `_ =` though its writers can't fail (35 in the spike).
   (The rest of this entry is fixed: a hole takes a spec, `{:<16}`, `{:08x}`, `{:.3}`, so the
   wrapper types and their writers are gone, and an f32's 100.0 prints as `100.0`.) *Hit by
   5:* glspike (35), engine (2), audio (3 writers), data (1), script (about 15, and six
   writers).

5. **Sources come by directory, and a directory is one flat namespace.** `build::add_sources`
    takes a directory and `build::exe` one without its subdirectories, so a tool can't pick one
    file (the dialog panels and lip sync moved to directories of their own), and one half-written
    file breaks every build that adds its directory (each rules agent built from a private copy).
    A directory's files share one namespace with no file-private names, so two agents writing
    `put_*` helpers coordinate names by message; a file can't keep private state either, so every
    cache goes in `World`, the file every agent needs. *Partly:* a namespace may now span files
    (spec §10, rule 4; 2540d389), so a big one such as `mdl` can be split; and a folder with an
    `api.ctx` is a module (spec §10, Modules), whose hidden helpers are its own, so two agents'
    `put_*` don't clash, and whose state is in a capability whose statics only it reaches.
    Choosing single files remains. *Hit by 5:* engine (2), dialog (2), models, rules, script.

6. **A program's namespace hides std's of the same name whole.** KOTOR's `math`, its vectors,
    hides std's `math`, so it declares libm and the float-bits fns again (lib/base/math.ctx, 24
    extern fns) rather than reach std's. (The rest of this entry is fixed: std's `math` has
    libm's functions, they run while compiling, the MP3 tables' own cosine series and Newton
    roots are gone, and `@min`, `@max` and `@clamp` are builtins, which no namespace hides.)
    *Hit by 5:* ctxc, audio, video, rules, render (about 6).

7. **Signed and unsigned integers don't mix.** Game data is signed (-1 for none, modifiers) and
    lengths and counts are `usize`, and neither widens to the other: a `usize` going into an
    `i64` payload is `@as(i64, f)`. `@as(i64, b)` refuses a `bool`, so counting is `if b { 1 }
    else { 0 }`. *Partly:* an index takes any integer type with its bounds check (spec §12,
    Arrays, rule 1), and a const's name converts where its value fits (§11, Widening, rule 7),
    which were most of the sites. *Hit by 4:* glspike (11), rules (about 150, and about 60
    bools), walk (84), video.



10. **Enums only compare for equality, and their count isn't a constant.** Sorting by an enum is
    `@as(u8, a.class) >= @as(u8, b.class)`; `@as(usize, Class::last) + 1` isn't folded, so a
    tally array's length is a hand-kept `const CLASS_COUNT: usize = 56`, checked against the enum
    at run time. `@as(Kind, n)` lowers to one compare per variant, which the C backend emits as a
    chain (62 for `tok::Kind`; the lexer now indexes const tables instead); a contiguous enum
    could be one range check. *Hit by 3:* ctxc, data (1), walk (1).


13. **A `&fn` can't be a struct field.** A bound function travels as a context field of its own,
    or is bound again where it is used: the engine's functions bind the script VM's engine at
    each run (`engine = routines::call{ &w, _ }`), and the scene binds `mdl_cache::get` once per
    (model, animation). *Hit by 2:* engine, script.

14. **Changing a shared fn's signature breaks callers nobody on the task owns.** No default
    arguments, so a helper that gains an input edits every call site, in other owners' files; no
    visibility, so callers show up only as build errors; a fn that starts returning a pointer into
    `w` needs `mut w`, which spreads to every caller up to the routine. *Partly:* a module's
    hidden fns have their callers inside it, and its contract changes only in its `api.ctx`
    (spec §10, Modules); default arguments and `mut` spreading remain. *Hit by 2:* engine (2),
    hud.


18. **No methods** (§16 Q4). `list::push{ list = &xs, item }` everywhere: ctxc makes about 580
    `list::` and `map::` calls and 150 `slice::` ones. `xs.push{ item }` would shrink code a lot.
    *Partly:* slices are built in (spec §12), so `slice::get{ s = xs, i }` is `xs[i]`. *Hit by 1:*
    ctxc (about 730).

19. **A GL function is written three times:** a capability field with its C type, then `name =
    @cast(_, try proc{ get_proc, name = "glName" })` in the loader, the C name the field's in
    another case. An attribute on the field (`#c_symbol{ name = "glClear" }`; fields carry
    attributes since `304f48d`) and a generator over `build::declarations` would make a binding
    one line per function. *Hit by 1:* glspike (132 loader lines).

21. **A diagnostic takes three lines** in ctxc. *Mostly solved:* `@fmt` without a sink is a writer
    (spec §13), so 163 of 197 sites are one line (`errorf{ &c, at, msg = @fmt("...", args) }`).
    About 50 keep a builder: reports through `flow_error` and `escape_error`, which take a
    `utf8::String`, and messages built from more than one `@fmt` or with a loop between. *Hit by
    1:* ctxc (about 50).

22. **An inferred slice type is too mutable.** `let mut bs = list::items{ list = xs }` gives `bs`
    `[]mut T`, so a later `bs = f{}` with a `[]T` result is an error; the same for
    `slice::empty(T){}`. Inferring the type from every assignment, as literals are, would fix it.
    The same mutability stops a comparison: what `fs::read_all` returns, an `alloc::Bytes`, is
    a `[]mut u8`, and `back == "hello"` is "a string literal is read-only; it cannot be a
    []mut u8" until it is copied to a `let got: []u8 = back`. *Hit by 2:* ctxc (about 30), a
    test of std's (1).

23. **No scoped lock.** Every public fn of the mixer starts with `mutex::lock{ mutex = &m.lock }`
    and `defer mutex::unlock{ mutex = &m.lock }`, naming the lock twice. A block form (`with`-like)
    would do without destructors. *Hit by 1:* audio (21 pairs, kotor/lib/audio/mix.ctx).

25. **A slice that will be freed stays `[]mut`.** Freeing hands the memory back to the allocator
    as `[]mut u8`, and a `[]T` can't become a `[]mut T` again, so a slice or a field that is only
    read after it is filled is still `[]mut` from its allocation to its free. (The rest of this
    entry, from the models, walk and data write-ups, is fixed: allocators hand out zeros, and std
    has `alloc::make`, `list::take`, `fs::list_free` and an arena mark.) *Hit by 1:* data (8
    fields).

27. **A `mut` argument can't be a temporary.** `f{ x = g{} }` for a `mut x` has no place to point
    to, so it is `let mut tmp = g{}` first. *Hit by 1:* rules (4).

28. **Locking a structure needs `mut`.** A query that only reads a shared structure
    (`mix::is_playing`, `played`, `feed_room`) must lock its mutex, which takes `mut mutex`, so it
    takes `mut m: Mixer` and its signature no longer says it changes nothing. A read-only `*T`
    that may still lock its mutex field would say it. *Hit by 1:* audio (4 fns).

29. **No tuples.** `let (a, b) = if two { (x, y) } else { (z, w) }` is two `let`s on the same
    condition, and an `(item, index)` result a small struct with every field named (`ItemSpell`,
    `Pick`, `Swap`). *Hit by 1:* engine (2 entries).

31. **A `mut` struct field is a pointer, and the C is built with `-fno-strict-aliasing`,** so gcc
    reloads the bit reader's fields after every store through any pointer: about 10% of the Bink
    audio decoder, worked around with a local copy (`let mut rd = r`, `defer r = rd`).
    Restrict-qualifying `mut` context fields (§3.1 already forbids two overlapping ones) would let
    gcc keep them in registers. *Hit by 1:* video.

33. **No pointer from an integer.** GL takes buffer offsets as `const void *`; the binding
    declares them `offset: usize`, which works only because 64-bit ABIs pass the two alike.
    *Hit by 1:* glspike.

35. **`null` can't name a variant,** so `types::Type`'s is `nil`. Cosmetic. *Hit by 1:* ctxc.

36. **The mutex isn't fair, and std doesn't say so.** Windows' slim locks let a thread that
    unlocks and locks again keep the lock: mixtest let the other thread in 97 times in 3,000
    blocks, and about 1,000 once it yielded between blocks. Worth a line in std's `mutex` comment.
    *Hit by 1:* audio.

37. **An array length or enum value can't use every folded const.** §14 says they can use any
    folded const, but ctxc's early folder for them (`const_int`, check.ctx) works in untyped i64
    and knows only literals, consts, unary `-` and the plain binary operators. So `const N: usize =
    @size_of(u32)` or `const N: u8 = 255 +% 2`, both folded, is "an array length must be a
    compile-time integer constant" in `[N]u8`. Folding them with the typed folder, or the spec
    narrowing what they may use, would fix it. *Hit by 0:* found reviewing the wrapping operators.

38. **No clock without `Threads`.** `os::now` and `thread::sleep` take a `Threads`, and taking
    one makes a program threaded (§15, Entry point, rule 8). std's test runner only waits for
    processes, so it has none, and counts a test's time limit in its own 20 ms waits
    (std/test.ctx, `SLICE`): a limit is at least what it says, and nothing can print how long
    a test took. A monotonic clock under a capability that doesn't start threads would fix it.
    *Hit by 1:* std's test runner.
