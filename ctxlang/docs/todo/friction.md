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
    *Partly:* std's `clock` (spec §17) reads the monotonic and the wall clock under `Clock`,
    which starts no thread (added for serve, whose log needs both); the test runner still
    counts its own waits until it takes one. *Hit by 2:* std's test runner, serve.

39. **Storing through a read-only slice of `mut` elements needs the slice `mut` too.** http's head
    parsers fill the caller's `[]mut Header` with slices of a buffer the caller owns. Written
    `headers: []mut Header`, the escape check (§14, Escape check, rule 3) can't tell where the
    stored slices go and refuses a buffer that is a local array, so the field is `mut headers`
    and every caller writes `let mut headers = fields[..]` and passes `&headers`, though the
    callee never changes which elements the slice names. Following stores through a read-only
    slice's elements, as through a `mut` field, would drop the extra local. *Hit by 1:* http
    (`parse_request_head`, `parse_response_head`, and the connection and server fns over them).

40. **A group's tasks can't fail alone.** A server keeps a task per connection in a
    `task::Group`, so that stopping it ends them all, and a connection's task wants to return
    its error (a reset, a head that missed its deadline) as any fn does. But a group's task that
    fails cancels the group's others (std/task.ctx, `start_in`), so one client's reset would end
    every connection. Written: each connection's fn ends in `serve_connection{ ... } iferr {}`,
    still returning `!` that never fails, and its errors are lost unless it logs them itself. A
    start into a group whose tasks' failures are their own, kept or counted for `wait_all`
    without cancelling the rest, would say it. *Hit by 1:* http (the small server's
    `connection`, and the tests' servers).

41. **A callback that any thread calls can't reach its own namespace's statics.** std's stop
    handler (a console control handler on Windows, a signal handler on Linux and macOS) only sets
    the layer's atomics and signals its object, all `os::Stop` statics, which are global anyway;
    but a `#c_callback{ any_thread = true }` takes no capability (§18, Callbacks, rule 6), and
    neither Windows' handler nor a signal handler gets a user pointer to pass one through. Written:
    `let none: u8 = 0` and `let mut stop = @cast(*Stop, &none).*`, a capability forged from a
    local's address (§15, rule 4), as `task::begin` forges `Threads` from its start pointer. Letting
    such a callback take a capability without fields that isn't `#thread_bound`, on the
    binding's word that what it reaches is safe from any thread, would say what is meant without
    a cast. *Hit by 1:* std (stop's
    handler on every layer, and task's and thread's thread entries).

42. **serve_connection doesn't say what it answered.** A request it refuses (400, 431, 501,
    505) never reaches the handler, and its error doesn't say whether a response went out, so a
    server's access log can't have a line for it from what std gives. Written: serve's
    `find_refusal` (serve/src/run.ctx) maps http's errors back to the statuses std's `refuse`
    chose, and logs them from the connection's task; a handler's own error of the same kind (a
    response head too large for the buffer) would be logged twice. A callback for refusals, or
    the status in the error, would say it. *Hit by 1:* serve.

43. **std has no general-purpose heap.** A server's memory per request is decided by its input
    (a directory's listing, a path as long as the target) and freed when the request is
    answered; an arena only grows, and `mem::pages` is never given back. Written: C's calloc,
    realloc and free behind `alloc::Fn` (serve/src/heap/heap.ctx), which kotor wrote first
    (kotor/lib/base/heap.ctx). *Hit by 2:* kotor, serve.

44. **A task's standard output is its thread's own buffer.** What a task prints comes out when
    its worker's 64 KiB fills or its thread ends (10 seconds after its last task), so lines from
    many tasks come out late and in any order. Flushing after each line makes each one a write
    of the system's, which threads queue for: serve's access log to a file cut it from 25,600
    to 4,000 requests a second. Written: a journal of the program's own, a shared buffer under
    a mutex that one writer task writes out (serve/src/access.ctx, about 90 lines). A std
    writer that tasks share, written out by line, would say it. *Hit by 1:* serve.

45. **A type's `@fmt` writer reaches one sink.** `net::Address` has writers into a
    `utf8::Builder` only, so printing one to an `Io` or an `io::Stderr` goes through a builder
    over an arena first (serve/src/run.ctx). *Hit by 1:* serve.

46. **An error doesn't become a `?error` in one step.** `failure = error`, for an inferred
    set's error and a `failure: ?error`, and `failure = net::reset`, are errors: a set converts
    to `error` and a T to `?T`, but not both at once. Written: `let any: error = error`, then
    `failure = any`. *Hit by 1:* serve (site.ctx, and its tests).

47. **std has no sort.** fs sorts a listing's names with a sort of its own, private; serve's
    load generator wrote a heap sort to take percentiles of latencies
    (serve/tools/load/main.ctx, `sort_u64`). A generic `slice::sort(T)` taking a `less` would
    serve both. *Hit by 1:* serve.

48. **`condition::wait` can't be cancelled.** A task that waits on a condition ends only when
    what it waits for comes, so its handle's scope end waits for that too. Written: serve's
    log writer waits with `condition::wait_for` and wakes every 100 ms to ask
    `task::check_cancelled`. A wait that also waits on the task's cancel object, as
    `thread::sleep` does, would say it. *Hit by 1:* serve.

49. **Windows' file calls put a 64 KiB path buffer on the stack, which stays committed.** Each
    of std's file functions on Windows converts the path into a `[32768]u16` local (the longest
    path Windows takes), and a thread's stack stays committed at the deepest it has been, so
    every worker that ever touched a file keeps those pages: serve's 1,000 idle connections
    that had each asked for a file took 238 MiB, and 176 MiB when they had asked for /stats
    instead. A buffer sized to the path would need memory std doesn't have (entry 43), and a
    long-path fallback in a function of its own could still be inlined into the common frame:
    there is no way to say that a function mustn't be. *Hit by 1:* serve.

50. **`ctxc exe -o` into a directory that isn't there fails in the linker.** `ctxc exe serve -o
    serve/out/serve.exe` before serve/out existed gave ld's "cannot open output file ...: No
    such file or directory" and "the C compiler failed", not ctxc's own word that the directory
    is missing, nor the directory made. *Hit by 1:* serve.

51. **A function value can't be started as many tasks.** A start's `run` is a bind written in
    the call (spec §15, Tasks, rule 3), so a library can't start a task per connection around a
    handler its caller passed as a value: what the value holds can't be seen. This is what
    keeps `http::serve` out of std (docs/todo/http.md, Decision 7; serve/PLAN.md, Findings).
    Written: the accept loop and the connection's task in the program (serve/src/run.ctx,
    `accept_into` and `connection`, about 45 lines with the program's own counting and
    logging). *Hit by 1:* serve.
