# LLM-first checklist

What ctxlang still needs so that a model writes correct code on the first or second try. Work
through the items in order, one at a time; tick an item when its *Done when* holds, and note the
commit beside it.

The guiding rules, in order of weight:

1. **No silent wrong answers.** A compile error costs a model one retry; a wrong result costs a
   debugging session, or ships.
2. **The safe form must be the easy form,** or code drifts to the unchecked one.
3. **What a model writes by default compiles,** or fails with an error that states the fix.
4. **Feedback is fast, complete and machine-readable.**

Evidence comes from [FRICTION.md](FRICTION.md) (17 agent write-ups from ctxc and the KOTOR port;
entries are cited by number, e.g. F#24) and [kotor/docs/tooling-gaps.md](../kotor/docs/tooling-gaps.md).

## 1. Silent wrong answers

- [x] **1.1 Reject a read-only argument that a later argument's call changes.**
  `types::prune{ s = c.ty, t = expr{ &c, e } }` copies `c.ty`, then `expr` changes `c`, and
  `prune` reads the stale copy. `show{ n = c.n, z = bump{ &c } }` passes the old `c.n` silently.
  §3.1 checks overlap between one call's own arguments, not a `&c` inside a nested call.
  Either reject it, or evaluate nested calls before plain arguments, and say which in the spec.
  - Details: F#24 (the only entry giving a wrong answer, 8 sites in ctxc); [spec §3.1](spec.md#31-exclusivity), [§14 rule 6](spec.md#14-memory).
  - *Done when:* both examples above are compile errors (or provably read the new value), with tests.
  - *Done:* rejected, not reordered (reordering silently picks the new value where the old may
    have been meant). [spec §3, rule 10](spec.md#3-calls): no item of one call or literal may
    change a place another reads or changes. Precise by field, from summaries of what each fn
    reads and changes of its fields; strict for allocations too. It found 27 conflicts in ctxc
    and 13 in KOTOR (among them RNG draws in `Vec3{ x = rand, y = rand }` and a stale copy of
    `h.lists[1]` in the HUD), each fixed with a `let` in today's order.

- [x] **1.2 Give unchecked pointer indexing its own syntax.**
  `q[i]` on a `*T` is `(q + i).*`, unchecked, but looks the same as the bounds-checked `s[i]` on
  a slice or array. A model will assume it is checked. Same for `s.ptr[i]`.
  Move it to a spelling that says so (e.g. `@unchecked(q, i)` or `(q + i).*` only), so every
  route to undefined behaviour is greppable.
  - Details: [spec §12, Pointers, rule 5](spec.md#pointers), [§12, Slices, rule 2](spec.md#slices).
  - *Done when:* `q[i]` on a pointer is an error that says what to write; ctxc, std and kotor are migrated.
  - *Done:* `(q + i).*` only, no builtin: it existed already, is a place as it stands (written,
    `&`, `(q + i).f`), and leaves one unchecked operation fewer for 1.3, pointer arithmetic, which
    the compiler can find where a text search can't. `q[i]` and `q[lo..hi]` on a pointer are
    errors that spell the fix from the source, e.g. ``write `(s.ptr + (i + 1)).*`, which isn't
    checked``; a `*[N]T` still indexes its array, checked.
    [spec §12, Pointers, rule 5](spec.md#pointers). Migrated by applying the compiler's own
    fixes, behaviour unchanged: 395 sites in KOTOR (300 on the script VM's stack, the rest
    in the Bink, MP3 and mixer loops), 37 in std (23 of them in the posix, linux and macos
    layers), 7 in examples/glfw, 9 in the tests' programs, none in ctxc.

- [x] **1.3 Make the unchecked operations auditable as a set.**
  With 1.2 done, `@cast`, `@slice`, pointer arithmetic, unchecked indexing and `@addr` are the
  ways to undefined behaviour. A build should be able to forbid them outside chosen directories
  (e.g. a `build::allow_unchecked{ &b, exe, dir }`, everything else an error), so game code can't
  reach for them and review only looks where they are allowed.
  - Details: [spec §13](spec.md#13-builtins), [§12, Pointers, rule 7](spec.md#pointers).
  - *Done when:* a build program can deny them per directory, and kotor's game code builds with them denied outside its platform and binding layers (or the exceptions are listed).
  - *Done:* the set is in one place, [spec §13, Unchecked operations](spec.md#unchecked-operations):
    `@cast`, `@slice`, pointer arithmetic, `@record_copy`, a `c::String` from a pointer, and
    declaring an `extern fn`, an `extern union`, a capability's C variable or a `#c::callback`
    fn (a wrong declaration is undefined behaviour, and `extern fn memcpy` would be a way round
    the rest). Not `@addr`, which gives an integer nothing turns back into a pointer. The spec
    also lists what a review must still look for anywhere: use after free, data races, an
    allocator of the program's own, a `#start` without a stack limit.
    `build::deny_unchecked{ &b, exe, except = ["lib/platform", ...] }`
    ([spec §19, rule 17](spec.md#19-build-programs)) makes them errors in the executable's
    files but for the directories listed: one call that says both that they are denied and
    where they aren't, rather than `allow_unchecked` calls whose first would switch the denial
    on. An executable without it builds as before. A directory that holds none of the
    executable's files stops the build, generated files are always denied, std never is. Only
    writing one is denied: calling an extern fn or using a slice an excepted directory made is
    allowed anywhere. The error names the checked form, e.g. ``pointer arithmetic is unchecked,
    and `build::deny_unchecked` in build.ctx denies it here: index an array or a slice (`s[i]`,
    which is bounds-checked), or write it in a directory its `except` lists``.
    KOTOR's game denies them in 310 of its 359 files; [kotor/build.ctx](../kotor/build.ctx)
    excepts six directories, 672 sites in all, each with its reason:
    - `lib/platform` (85): SDL2's binding.
    - `lib/render_gl` (155): OpenGL's binding, and vertex and uniform data as bytes.
    - `lib/base` (36): the C heap behind `heap::alloc`, libm's functions, float bits, and
      `le`'s reads after one bounds check.
    - `lib/script` (301): the NCS VM's stack through pointers, and its untagged `Cell`.
    - `lib/video` (67): the Bink decoder's inner loops, and libm for its audio tables (which
      4.2 moved to `lib/base`'s).
    - `lib/audio` (28): the mixer's and the MP3 decoder's inner loops.

    `lib/engine` and `lib/render` were excepted at first and came off the list: 16 frees of one
    object written `@slice(p, 1)` became `alloc::free`, `put_floats` writes each f32's bits
    (`math::f32_to_bits`) instead of viewing the floats as bytes, and the 9 libm f64
    declarations of routines/core.ctx moved to `lib/base` beside the f32 ones (KOTOR's own
    `math` namespace hides std's).

- [x] **1.4 Fix float-to-float `@as` in the spec.**
  §13 says `@as` panics if the value isn't representable, but `@as(f32, 1e300)` gives `inf`.
  When spec and compiler disagree, the model believes the spec. Say float-to-float rounds and
  overflows to infinity (or give it its own builtin), and check `ifoverflow` doesn't claim to cover it.
  - Details: F#26; [spec §13](spec.md#13-builtins), [§11, Overflow](spec.md#overflow).
  - *Done when:* spec and compiler agree, with a test.
  - *Done:* the spec changed, not the compiler: `@as` to a float type never panics. It rounds to
    the nearest value, an `f64` past `f32`'s range to an infinity, as C, the interpreter and a
    const's evaluation all did already; a panic there would put a check in every audio and
    vertex loop for a value `math::is_finite` can test. [spec §13](spec.md#13-builtins) says so,
    and [§11, Overflow, rule 2](spec.md#overflow) that it never overflows: `ifoverflow` covered
    only `@as` to an integer, and `@as(f32, x) ifoverflow 0.0` was an error already.

## 2. Make the safe form the easy form

- [x] **2.1 Split borrows.**
  `f{ &e, xs = &e.list }` is two mut references to `e`, so the World and the VM live behind raw
  `*mut` pointers that the checker doesn't track at all: the exclusivity rule pushes the
  program's central objects out of checking. Allow disjoint places of one root in one call (and
  a bind beside a `&` of what it doesn't hold), keeping the check where they overlap.
  - Details: F#4 (5 write-ups), F#27, F#28; [spec §3.1](spec.md#31-exclusivity).
  - *Done when:* `f{ &e, xs = &e.list }` compiles where `f` can't reach `list` through `e` (or the rule for what's allowed is in the spec), and kotor's World is passed as a checked `mut` field somewhere it was a raw pointer.
  - *Done:* [spec §3.1, rule 8](spec.md#31-exclusivity): a call or a bind of a function with a
    body may be given mut references that overlap, where what the function does through one
    field doesn't overlap what it changes through the other. It is 1.1's summaries, by field
    and through the functions called, which now also keep an address that is given out
    (returned, or passed to a function that only hands it on) as a use of the place, and where
    each access is. A function value, an extern fn and a capability's field are given nothing
    that overlaps: no body to look at. A bound function's places count as changed whole, so a
    bind beside a `&` of what it doesn't hold is allowed, and two binds over one place aren't.
    The error names the callee's two accesses, e.g. ``two mut references to `e` in one call:
    `f` reads `e.list.len` through its field `e` at 7:11, and changes `e.list.len` through its
    field `xs` at 8:15 (the access is in `push`); pass one of them, or change `f` to use
    `e.list.len` through one of them only``.
    Excluded, and why: a bind beside a `&` of a place it holds, which the callee uses
    (`tick{ &world, engine }`). The bound function runs whenever the callee calls it, whatever
    the callee holds of the place by then (a slice of a list the bound function grows), and the
    checker follows no pointers. The answer is to bind where the function is called, in a call
    that isn't given the place. Memory through a pointer or a slice stored in the places isn't
    compared either, as everywhere (§3.1, rule 6).
    Found on the way, and fixed: a bound function called with a place it holds
    (`h{ b = &n }`) was not checked at all; and two holes in 1.1's summaries, a `match &p`
    without a binding by reference (not counted as reading `p`) and an `@fmt` to a sink in a
    callee's statement (not counted as changing it).
    KOTOR: the World and ncsrun's VM stub were raw pointers because one engine bind, made at
    the root, travelled beside them through 72 signatures. The engine is now bound where a
    script runs (`scripts::run_program`, `scripts::resume`, ExecuteScript; ncsrun's two
    calls), the `engine` field is gone, and the world is a checked `mut w` on every path from
    `world::tick` down, the three `let wp: *mut World = &w` and ncsrun's `stub: *mut Stub`
    (7 fns) included; `world::prefix` (211 calls) and savetest's tests take `mut w` too, and
    `dlg::free{ &w, d = &w.conversation.d }` takes the dialogue as a `mut` field by this rule,
    the one call in KOTOR that passed a part of the world raw beside it. What a script changes
    now counts as a change through `&w` for argument order (1.1), which the raw pointer hid.
    Still raw: the root's `*mut World` from `world::make` (the World is on the heap, and a
    place through a pointer isn't checked); heap objects (`*mut obj::Object`, `Fighter`,
    `Action`, GUI panels); `*World` and `*MessageLog` read-only views, which exist to avoid a
    copy; allocator state (`heap: *mut heap::Heap`), which std's containers hold as a pointer.
    F#27 (a `mut` argument that is a temporary) and F#28 (locking through a read-only pointer)
    are other problems and stay in 8.4.

## 3. First-draft traps

What a model writes by default should compile, or fail with the exact fix.

- [x] **3.1 Pun a place's last name: `&g.rng` fills `rng`.**
  Today `deal_hand{ &g.rng, &g.player, deck }` is a parse error and must be `rng = &g.rng`. Hit by
  12 of 17 write-ups, every file's first compile. Also `g.rng` for a read-only field.
  - Details: F#1; [spec §3, rule 6](spec.md#3-calls).
  - *Done when:* `f{ &a.b.c, a.d }` supplies `c` and `d`, with tests; the old error is gone.
  - *Done:* [spec §3, rule 6](spec.md#3-calls): an item that is a place ending in a field's name
    is a pun of that name, in a call, a bind and every literal (they share one parser). The
    place starts at a name and may go through fields, indexes and derefs on the way
    (`&ws[i].g.rng`); only the last step counts, so `s.len` supplies `len`. What ends in
    anything else is not a pun, since no name there is the field's: an index, `.*`, a range, a
    call or a literal, a `::` path, an operator's expression. Each is one error that keeps the
    rest of the call checked, e.g. ``a pun is a place that ends in a field's name, as `&g.rng`
    is for `rng`, and this one ends in an index: write the field's name, as `name = &g.xs[0]` ``;
    before, `f{ make{} }` and `f{ n + 1 }` were "expected '}'". A pun that names no field says
    what to write from the fields nothing supplies (``write `d = w.g.xs` ``), or lists the fields
    when all are supplied. Argument order (1.1) and split borrows (2.1) see the pun's place as
    they see a named item's. Converted as proof, not everywhere: KOTOR's pazaak (21 sites, the
    `deal_hand` of F#1 among them) and 6 in std.

- [x] **3.2 A `for` loop.**
  Every loop is `let mut i = 0; while i < n { ...; i = i + 1 }`: forgotten increments are hangs,
  the worst failure an agent can hit. A `for i in lo..hi` and a `for x in slice` (with index form)
  would cover nearly all.
  - Details: F#20 (about 70 loops in bink_video.ctx alone); [spec §11](spec.md#11-statements-and-control-flow).
  - *Done when:* both forms are in the spec and ctxc, with `break`/`continue`/labels as for `while`.
  - *Done:* [spec §11, For](spec.md#for). `for i in lo..hi`: half-open, the bounds read once
    (`lo` first), `i` of the bounds' one type after widening as `<` widens (`0..n` gives `n`'s
    type), empty where `lo >= hi`, and counting can't overflow. `for x in e` copies each
    element of a slice, an array place (through its view `e[..]`), a pointer to an array, a
    const array or an array literal; `for &x in e` binds the element's place, as `&f` does in
    a pattern, mutable where `e` is; `for x at i in e` adds the index. Chosen against wrong
    guesses: two names with a comma are an error rather than an order to remember (`for i, x`
    in Go, `for x, i` in Odin: with a `[]usize` either would compile), `lo..=hi` and
    `range(n)` are errors that say what to write, and the names can't be assigned (``cannot
    assign to `i`: it is set by its `for` each time round; change a copy of it, a `let mut` ``).
    What is gone over is evaluated once and held as a `let` holds a slice: its length is
    fixed, later turns see earlier turns' changes, and a body that frees or moves the memory
    is unchecked as for any held slice (§13, Unchecked operations, rule 3). No new check was
    added for that: rejecting a body that changes what the `for`'s expression read would also
    reject well-defined loops over arrays, and its fix, a `let` before the loop, would only
    hide the same dangling slice; the spec says to go over indexes instead. `for` is a
    keyword; `in` and `at` are words only in its head.
    The checker takes it as its own statement in every pass: flow (it ends no path, and a
    `let x: T` assigned in it is an error), narrowing, escape (`&x` is derived from what is
    gone over), argument order (a fn that changes an array through `for &x` changes it; `for
    x` reads it), tasks, and `match &p`'s scan; lowering writes a `while` over a hidden
    counter that steps before the body, so `continue` needs nothing and the IR, the C backend,
    the interpreter and consts are unchanged. A task's handle can't be gone over.
    Converted as proof: 22 loops in ctxc/types.ctx, 3 in std/slice.ctx, 7 in KOTOR's
    lib/base (ci.ctx, resref.ctx).

- [x] **3.3 Index with any integer type.**
  `a[i]` with `i: i32` is "expected usize", so the code is `a[@as(usize, i)]` after a range check
  (about 150 in rules, 84 in walk). Let an index take any integer type, its bounds check
  rejecting negatives too. Also: typed integer consts converting where their value fits, as
  literals do (`@as(i32, gl::LINEAR)`).
  - Details: F#7; [spec §12, Arrays](spec.md#arrays), [§12, Slices](spec.md#slices), [§11, Widening](spec.md#widening).
  - *Done when:* `a[i]` and `s[lo..hi]` accept any integer type and panic below 0.
  - *Done:* [spec §12, Arrays, rule 1](spec.md#arrays) and [Slices, rules 2 and 3](spec.md#slices).
    An index and each bound of a range is an integer of any type; the bounds check takes it as
    it is and panics below 0 in today's words, `index -1 out of bounds for length 3` and
    `range -1..2 out of bounds for length 3`, while compiling too (a const's panic is its
    error). The cost is unchanged: a signed index is compared as its 64 bits, which below 0
    are past any length, so it is still one unsigned compare, and only the panic's text knows
    the sign. An integer literal as an index stays a `usize`, so `a[-1]` is still a compile
    error; a distinct type and an enum still convert with `@as` (the error says so), as for a
    shift count. A pointer's error now comes first and spells the conversion that pointer
    arithmetic needs: ``write `(q + @as(usize, i)).*` `` (1.2). Pointer arithmetic and `@slice`
    keep `usize`: they are the unchecked operations, where a negative would not be caught.
    Consts, [spec §11, Widening, rule 7](spec.md#widening): the name of a const whose type is
    an integer type and whose value is folded converts to another integer type where its
    value fits, as a literal of that value would: as an argument, a field, an assignment, a
    return, an element, a branch's value, a `match` pattern, and one operand of a binary
    operator. It is tried only where the types neither agree nor widen, so no program that
    compiled changes. Not converted, each for its reason: an expression of consts and a local
    (only a name's value is a known constant at its use), a const computed by running code
    (unknown while bodies are checked; the error says to write `@as`), a distinct type or an
    enum either way, and a float target. A value that doesn't fit is an error that gives it:
    ``expected i32, got u32: `gl::BIG` is 4000000000, which doesn't fit i32``.
    Removed as proof: 30 index casts in KOTOR's lib/walk/bwm.ctx and lib/rules/progress.ctx,
    and 12 `@as(i32, gl::...)` in lib/render_gl's fx.ctx and fx_shadow.ctx.

- [x] **3.4 `iferr` and `ifnull` chain.**
  `f{} iferr { return } ifnull { return }` on a `!?T` is a parse error. Also, `x == f{} ifnull y`
  parses as `x == (f{} ifnull y)`; at least make that an error that says so.
  - Details: F#8; [spec §8, Optional, rule 7](spec.md#optional), [§8, Errors, rule 8](spec.md#errors), [§11, Expressions](spec.md#expressions).
  - *Done when:* the chain compiles and the comparison case is unambiguous or an error.
  - *Done:* [spec §11, Expressions, rule 7](spec.md#expressions), one rule for `ifnull`, `iferr`
    and `ifoverflow`. A handler's right side is a block or an expression. An expression takes
    every handler after it, as before (`a ifnull b ifnull 0`); a block ends at its `}`, so a
    handler after one takes the whole expression before it, on the same line or the next:
    `f{} iferr { return } ifnull { return }` is `(f{} iferr { return }) ifnull { return }`.
    Nothing that compiled changes: a handler after a block's `}` was a syntax error. Handlers
    go in the order of the type; the other order and a repeated handler are type errors that
    now say what to write: ``handle its error first, as `f{} iferr { ... } ifnull { ... }` ``
    for a `!?T`, the mirror for a `?!T`, and ``this `iferr` has handled it, and the one after
    it has nothing left to handle``.
    Beside a comparison, `is`, `and` or `or`, a handler is an error that shows both
    spellings, e.g. ``write `x == (f{} ifnull y)` or `(x == f{}) ifnull y` ``, rather than a
    grouping to remember: other languages put `??` below comparison and ctxlang's handlers
    are above it, and with a `?bool` both readings of `f{} ifnull a == b` compile. A handler
    on the left with a block reads one way and stays allowed (`f{} ifnull { return } == y`).
    An `ifnull` or `iferr` after an operator's expression, which could never have the type,
    says where the handler was meant: ``write `a + (f{} ifnull 0)` ``. Arithmetic stays as it
    was on both sides (`a * b + c ifoverflow x`, `a ifnull n + 1`), where ctxlang and `??`
    agree. No site in ctxc, std or KOTOR mixed a handler with a comparison; three of the
    suite's programs did, on purpose, and are now written with parentheses.

- [x] **3.5 A condition may continue on the next line.**
  `if a\n or b {` is a parse error pointing at the wrong place, since a call's `}` ending a line
  starts the block. At minimum, a line starting with `and`/`or`/a binary operator continues the
  condition, and the error points at the break.
  - Details: F#9; [spec §11, rule 2](spec.md#11-statements-and-control-flow).
  - *Done when:* `if a\n or b {` compiles, with tests.
  - *Done:* [spec §11, rules 2 and 3](spec.md#11-statements-and-control-flow). An expression
    goes on to a line that starts with a token that continues an expression and begins none: a
    binary operator other than `-` and `&`, `and`, `or`, `is`, a handler, or `.`. Binary
    operators already went on across lines everywhere but one place, a call's `}` that ended a
    line in a condition, where the `{` was taken for the block; now the `{` is a call's there
    when such a token starts the next line. Every such program was a syntax error before (an
    `if`, `while` or `for` followed by a statement that starts with an operator), so nothing
    that compiled changes: the syntax dumps of all 519 files of std, ctxc, the examples and
    KOTOR are byte-identical before and after. Braces that hold a match's arms are never a
    call's, so `match k { ... }` with `+ 10` on the next line is still the match plus ten.
    Excluded, with the reason: `-` and `&` after such a `}`. They begin an expression too, and
    `if c { f{} }` with `-1` or `&x` on the next line is an `if` and its block's value today,
    so there the `{` still begins the block. If the condition was meant to go on, the error
    is at the line's `-`, in place of the old one inside the braces: ``a condition can't go on
    with a line that starts with `-`, which may begin a statement: end the line before with
    the `-`, or put the condition in parentheses``. It is given where the line isn't a
    statement or the braces aren't statements, and also where both readings parse and only the
    types would tell (`if f{ n }`, then `- 1 > 0 { i = 1 }`): that last case rejects a
    one-line `if c { x = e }` followed by a value that starts with `-` or `&` and ends in a
    call's braces, which compiled before, and the error says to put such a value in
    parentheses. No file of the corpus has one. A postfix `(`, `[` or `{` stays on its
    expression's line (rule 3, as before).

- [x] **3.6 Small syntax.**
  A bare `{ ... }` block as a statement; `defer if c { ... }`; a one-expression match arm without
  braces (`a => "A"`); `try f{}.x` parsing as the spec's own example says.
  - Details: F#11; [spec §11, Defer](spec.md#defer), [§8, Errors, rule 7](spec.md#errors).
  - *Done when:* each of the four compiles, or the spec drops it.
  - *Done:* all four compile.
    - A block is a statement ([spec §11, rule 4](spec.md#11-statements-and-control-flow)): a
      scope whose locals end and whose defers run at its `}`, and no value. It can't be taken
      for a call's or a literal's braces, which are on their expression's line, where a
      statement can't begin. Its own statement kind in the tree and in every pass of the
      checker (flow, borrow summaries, argument order, tasks, `match &p`'s scan), both dumps
      and the recovery test; lowering writes an `if true` of it, so the IR, the C backend and
      the interpreter are unchanged.
    - `defer` takes any statement that can run later by itself
      ([spec §11, Defer, rule 1](spec.md#defer)): also an `if` or `if let`, a `match`, a
      `while` and a `for`. `defer s` was already a block of `s`, so only the parser changed.
      A `let` (``put the `let` and what uses it in a block``), a `return`, `break` or
      `continue` (``a deferred body can't leave``) and another `defer` have their own errors.
    - A match arm takes one statement without braces
      ([spec §8, Match, rule 11](spec.md#match)): an expression, its value, or a call, an
      assignment, a `return`, `break`, `continue` or `if`; not a `let` or a `defer`. It ends
      with its line, at a `,` or at the match's `}`, and a `,` may follow any arm; two arms on
      one line without a comma are ``expected ',' or a newline after a match arm``. A line
      that starts with `-`, an integer literal and `=>`, `|` or `..=` is the next arm's
      pattern rather than more of the value, the one place a line's first token could be
      either. Arms with braces are as before.
    - `try`'s operand ends at the `}` of its first call
      ([spec §8, Errors, rule 7](spec.md#errors)), so `try f{}.x` is `(try f{}).x`, as the
      spec said, and `try a.b{ ... }` still tries the call. This is the one change to
      programs that compiled: `try f{}.x` for an `f` that returns a struct with a `!T` field
      was `try (f{}.x)`, and is now an error that says so (``put the whole expression in
      parentheses after `try` ``); the two readings never both type-check. No file of
      ctxc, std, the examples or KOTOR has one (their syntax dumps are unchanged); one of
      the suite's programs did, and is now `try (mk{ p = &x }.r)`.

- [x] **3.7 `is` doesn't break names.**
  `let is = ...` and `fn is{}` are "expected a name, found 'is'", far from the cause. Make `is`
  contextual (as `distinct` is), or give the error the fix.
  - Details: F#15; [spec §1, rule 4](spec.md#1-top-level).
  - *Done when:* `is` works as a name, or the error says it is a keyword and suggests another.
  - *Done:* `is` is a name ([spec §8, Is, rule 9](spec.md#is), [§1, rule 4](spec.md#1-top-level)):
    a local, a fn, a field, a variant, a namespace. It is the operator only after an
    expression. On the expression's line that is every `is` there, since no name can follow
    an expression; so no program that compiled reads differently. At the start of a line it
    is the operator when a pattern follows on that line (a name, `null`, an integer literal),
    as a test that goes on from the line before does, and a name before anything else
    (`is = 1`, `is{ ... }`, `is.x = 1`); every such statement was a syntax error before. The
    lexer has no `is` token any more, and the syntax dumps of std, ctxc, the examples and
    KOTOR are unchanged.
    Every other keyword where a name belongs now says what it is, at the word: ``expected a
    name, found 'for': `for` is a keyword and can't be a name; use another, such as `for_` ``,
    for a local, a fn, a field, a context field, a variant, a const, a namespace, an item's
    name, a field access and a binding alike (they share the parser's one place for a name).
    `in`, `at`, `distinct`, `error` and `static` were names outside their own place already,
    and the spec's list of keywords now has `ifoverflow`, which it had left out.

## 4. Don't make the model hand-roll error-prone code

- [x] **4.1 Derived equality and hashing.**
  `p == q` on a struct is "no built-in equality", so ctxc has about 90 lines of hand-written
  `hash` and `eq` for types; one that forgets a field is a silent bug. Derive `==` for structs
  and unions without pointers (or slices), and a builtin `@hash`, or derive them in a build
  program (PLAN 3.2).
  - Details: F#30; [spec §11, Expressions, rule 5](spec.md#expressions); [PLAN 3](PLAN.md#3-metaprogramming).
  - *Done when:* `==` on such a struct works, and `map` can key on one without a hand-written hash.
  - *Done:* built in, not generated by a build program: `p == q` has to work where a model
    writes it, in any file and in generic code, with no build step, attribute or generated
    file to remember, and a build program sees declarations, not the instances of generic
    types that need one each.
    [spec §11, Expressions, rule 5](spec.md#expressions) and [§13, Hashing](spec.md#hashing):
    - `==` and `!=` compare a struct field by field, a union by variant and fields, an array
      element by element, an optional, and a distinct type as its base. A slice compares by
      contents, its length and then its elements: `[]u8` is the language's string and its
      commonest key, ctxc's own type table compares slices of ids that way, and by address
      two equal names would differ without a word. Each part must be a number, a `bool`, an
      enum or such a type again.
    - What has none, with an error that names the part and why (``Node has no `==`: its
      `next` is a *Node, a pointer, which a value's `==` neither follows nor compares:
      compare the fields by hand, the pointer by its address or by what it points to``): a
      pointer inside a value, though two pointers still compare by address themselves; a
      function; a capability; an `extern union`; an error or a `!T`. So a `c::String`, one
      pointer, isn't compared by address by accident. Padding is never read: the comparison
      goes part by part.
    - Floats compare as IEEE has it, so a value with a NaN in it isn't equal to itself;
      that is allowed for `==`, and is why `@hash(x)` refuses a type that holds a float,
      saying to hash its bits. For every other type with `==`, `@hash` is a `u64` that equal
      values share (a pointer's is its address), the same in a const, the interpreter and
      compiled code and in every run, and not a stored format.
    - A generic fn may use both on a value whose type has a parameter in it; each use of
      the fn must then give the parameter a type that has them, through the generic fns
      between, or it is an error where the fn is named (``` `map::make` uses `@hash` on its
      `K`, and V has no `@hash`: its `x` is an f32, a float, ... ```). The checker records
      what each generic fn needs of its parameters and carries it to the callers once the
      bodies are checked. That is what lets std's `map::make(K, V){ realloc, &heap }` key a
      map by any such type with nothing written; `map::new` still takes a caller's `hash`
      and `eq`, so no existing map changes.
    - The same record carries an order: a generic fn may write `<`, `<=`, `>` and `>=` on two
      values of a parameter's type ([spec §11, Expressions, rule 1](spec.md#expressions),
      [§9, rule 6](spec.md#9-generics)), and a use that gives a type without one is the same
      error (``` `largest` uses `<` on its `T`, and Point has no `<`: it is a struct, and only
      numbers have an order: ... ```). Only what `<` took already has an order: integers,
      floats and distinct types of them. None is derived for a struct, a union, an array or a
      slice, whose field order would set it without a word, and an enum has none; for those a
      fn takes a `less` function, as `map::new` takes `hash` and `eq`. It is what lets
      `min`, `max` and `clamp` be std fns rather than builtins (4.3).
    Lowering writes one `==` fn and one `@hash` fn for each type that needs them, from the
    IR's own compares, loops and matches, so the C backend, the interpreter and consts are
    unchanged and agree; a const that uses one is run rather than folded. Programs that
    compiled keep their meaning: these comparisons were errors.
    ctxc's hand-written `hash` and `eq` for types (81 lines) and for the interpreter's keys
    (9) are gone for `map::make`. The compiler before and the compiler after write the same
    C for ctxc's source, byte for byte (6,231,485 bytes), in the same time. KOTOR's own
    hashes stay: `resref::hash` and `eq` read a name's bytes up to its length only, which
    a field-by-field `==` wouldn't.

- [x] **4.2 Math in std.**
  No `sqrt`, `sin`, `cos`, `pow`, `floor`, `ceil`, `trunc`: the Bink audio declares libm's itself,
  and MP3's const tables carry their own cosine series (which run while compiling, so they can't
  call C).
  - Details: F#6; [std/math.ctx](std/math.ctx).
  - *Done when:* std's `math` has them, usable in consts too.
  - *Done:* std's `math` had libm's functions already, 28 for `f64` and each again with C's
    `f` suffix for `f32`; what was missing is that no extern fn ran while compiling. They do
    now, in a const and under `ctxc interp`, the only extern fns that do
    ([spec §14, rule 1](spec.md#14-memory), [§17, `math`](spec.md#17-standard-library)): the
    interpreter calls the same C function (eval.ctx, `libm`), found by its C name and its
    types, so a program's own declaration of one runs too. Chosen over writing them in
    ctxlang: a const's call then has the bits the program's call has by construction, with no
    second implementation to keep within a last bit of the C library's, and code that calls
    libm today keeps its results. The C compiler never computes a call itself (an extern fn is
    called under a name of its own, so `sin(0.5)` isn't folded with other rounding), and a
    NaN const now keeps its sign and payload in the C. The test compares all 56 functions over
    15 arguments (zeros, negatives, 1e-300, 1e300, 1e22, the infinities, NaN) bit for bit,
    const against run time. What it rests on: ctxc and the program use one C library, which
    holds wherever one machine builds both, and ctxc builds for no other. Across C libraries
    only the exact functions agree (`sqrt`, `floor`, `ceil`, `round`, `trunc`, `fabs`, `fmod`,
    `fmin`, `fmax`, `copysign`); Linux and macOS were reasoned, not run.
    Added: `math::INF`, `NAN`, `INF_F32`, `NAN_F32`, and the float literal's error now names
    them (``1e999 doesn't fit f64 (its largest value is about 1.8e308): write `math::INF` if
    infinity is meant``), or keeps `@as(f32, 1e300)` where a `math` of the program's own
    hides std's. `PI` was there.
    KOTOR's `math` (its vectors) hides std's, so the game can't name std's functions. Its own
    declarations in lib/base/math.ctx are the same C functions and stay, now usable in consts
    as well; renaming 2,461 uses of `math::` wasn't worth it. Bink audio's four libm
    declarations are gone for lib/base's (the same symbols; lib/video has no extern fn left),
    and MP3's cosine series and two Newton roots (37 lines fewer) are libm's `cos`, `sqrt` and
    `cbrt`, run while compiling: all 11 const tables have the same bits as before.

- [x] **4.3 Integer `@min`, `@max`, and clamping or rounding conversions.**
  `if a < b { a } else { b }` by hand; float-to-integer can only check, so audio code rounds by
  adding 1.5 * 2^52 and reading the bits.
  - Details: F#6, F#17; [spec §13](spec.md#13-builtins), [§17](spec.md#17-standard-library).
  - *Done when:* min/max and a rounding/clamping float-to-int conversion exist.
  - *Done:* six builtins
    ([spec §13, Smallest, largest and clamped](spec.md#smallest-largest-and-clamped) and
    [Rounding and saturating conversions](spec.md#rounding-and-saturating-conversions)).
    - `@min(a, b)` and `@max(a, b)`, for integers and floats: one type after widening, as
      `<` has it, so an `i32` and a `u8` compare as `i32`s and an `i32` with a `u32` is an
      error that says to convert one. Each operand is evaluated once; equal operands give
      the first. Nothing existed for floats but libm's `math::fmin` and `fmax`, which drop a
      NaN; here a NaN operand gives NaN, so one isn't lost on the way (rule 1), and std's
      keep C's answer for who wants it.
    - `@clamp(x, lo, hi)`: the bounds pair with `x` as above; a NaN `x` stays NaN. It
      panics unless `lo <= hi` (a NaN bound too), and two integer literals out of order are
      a compile error that says to swap them.
    - `@min`, `@max` and `@clamp` are builtins, though a generic fn can use `<` on its `T`
      (4.1), because as std's `cmp::min{ a, b }`, `max` and `clamp{ x, lo, hi }`, which they
      were for one commit, the operands widened one way only (`T` is the first argument's
      type), arithmetic code filled named fields, literal bounds out of order panicked where
      the builtin fails to compile, and the panic named std's line, not the caller's.
    - For a type without an order std keeps `cmp::min_by{ a, b, less }` and `cmp::max_by`
      ([std/cmp.ctx](std/cmp.ctx)): the order is a function, as `map::new` takes `hash` and
      `eq` beside `map::make`. std has no sort or search to take a name from; `_by` and
      `less` are what a model writes first.
    - Float to integer, beside `@as`, which rounds toward zero and panics: `@round(T, x)`
      rounds to the nearest integer, a half to the even one (IEEE's default, and what the
      bit trick did; `math::round` is C's, away from zero), and panics or takes an
      `ifoverflow` as `@as` does; `@saturate(T, x)` rounds toward zero and gives `T`'s
      nearest value instead of panicking, 0 for NaN, and clamps an integer too
      (`@saturate(u8, v)`); `@round_saturate(T, x)` does both. The error for an integer
      given to `@round` names `@as` and `@saturate`.
    All six are lowered to the IR's compares, conditionals and float additions (rounding
    is adding and taking away 2^52), so the C, the interpreter and consts agree by
    construction and nothing calls libm: the test compares 28 values through 12
    conversions, const against run time. A const that uses one is run, not folded, so it
    can't be an array's length.
    Converted: the MP3 synthesis and the mixer (`round_to_i16`) and the Bink audio
    (`to_i16`, the 1.5 * 2^52 trick) are `@round_saturate(i16, x)`; sndcheck over the
    whole install (16,818 files, 412 of them against ffmpeg), binkcheck over the 61 movies
    against ffmpeg and mixtest give the same output as before, with MP3 decoding about 3%
    slower and Bink the same. One difference by design: a NaN sample is now 0, where the
    old helpers gave -32768; the tools' outputs show none. Also 40 integer
    `if a < b { a } else { b }` in KOTOR's rules, save, res, mdl, script, dialog and audio
    code (checked to be integers with a compiler that rejected floats there) and the helper
    fns `min_i`, `max_i` and `min_usize` with their 8 calls: 50 calls of the builtins in
    KOTOR, 10 in std's Windows layer and 3 in std's test runner. bink2png's `clamp` is
    `@saturate(u8, v)`. KOTOR's f32 `math::min`, `max` and `clamp` (238 calls) stay: they
    return the second operand for a NaN, which `@min` doesn't.

- [x] **4.4 Format specs in `@fmt`.**
  No width, padding, hex or fixed-point (`{:<16}`, `{:08x}`, `{:.3}`), so programs write a wrapper
  type and writer for each. Also: 100.0 prints as `1e+02`.
  - Details: F#3 (5 write-ups); [spec §13, Formatting](spec.md#formatting).
  - *Done when:* the common specs work on numbers and strings, and floats print in plain form where short.
  - *Done:* [spec §13, Formatting, rules 8 and 9](spec.md#formatting). A hole is `{}` or
    `{:spec}`, with `spec := [<>^][0][width][.precision][x|X|b|o]`, in that order: a width
    up to 255 with spaces at the right of a string and the left of a number unless `<`, `>`
    or `^` says, `0` for zeros after a number's sign, a precision up to 30 for a float's
    digits after the point (rounded to nearest, a half to even, never in exponent form), and
    a base for an integer, a negative one as its type's bits. It is Rust's and Python's
    spelling less what isn't here: no fill character, sign, `#` or `e`, each an error that
    gives the grammar. A spec is checked against the argument's type while compiling, and
    the error says which part doesn't apply and what to write: ``` `{:.2}` has a precision,
    which is a float's digits after the point, and this argument is an i32: drop the
    precision, or convert the argument with `@as(f64, ...)` ```; `{x}` says a spec comes
    after a colon.
    A spec's hole goes to the sink's `#write` fn for one of five std types that hold the
    value and its spec (`fmt::Int`, `Uint`, `F64`, `F32`, `Text`; [std/fmt.ctx](std/fmt.ctx)),
    found as any writer is: no new mechanism, exact error sets, and a sink of the program's
    own gets specs with one-line writers over `fmt::format_int` and the rest. std's three
    sinks have them. A `bool`, an error, a function and a type with its own writer take no
    spec.
    A float's text is now one rule for both types (rule 9): the shortest digits that read
    back as the value of its type, plain from 1e-4 up to 1e16, exponent form outside. An
    f64 printed this way already; an f32 used C's `%g`, which gave `1e+02` for 100.0, and
    now gives `100.0`. This is the one change to what programs print: an f32 from 10 up to
    1e16 whose digits are fewer than its whole part's (100.0, 1200.0, 2500000.0) was in
    exponent form and is plain. No test expectation printed one. Of 20 KOTOR tools run
    before and after, only mgrun's output changed: 62 numbers, `1e+02` to `100.0` and
    `1.5e+02` to `150.0`. The text is one C function's for compiled code and the
    interpreter, as before; `{:.3}` is C's `%.*f` there, which mingw's, glibc's and macOS's
    printf round exactly (reasoned for the last two, not run).
    Replaced in KOTOR: the log prefix's `Pad3` (`{:03}`), sndcheck's `Fixed`, `Right` and
    `Pad` with their 60 lines of writers (`{:<17} {:>7} {:10.3} {:10.2} {:13.0}`; its
    table and its ffmpeg comparison print the same bytes), and `nwvm::Hex` and walkcheck's
    `Padded`, whose own sinks now take any integer spec through one `fmt::Uint` writer each
    (`{:08x}`, `{:>8}`).

## 5. Tests

- [x] **5.1 `#test` functions, `@expect` and a runner.**
  Models work best test-first; today each KOTOR parser needs its own tool program to be tested.
  The design is written: [PLAN 6.3](PLAN.md#6-tools-in-ctxlang). Prerequisite: settling how
  `main -> !` prints an error ([PLAN 3.1](PLAN.md#3-metaprogramming)), which `@expect` shares.
  - *Done when:* `ctxc test DIR` runs a program's `#test` fns, prints failures with both sides of
    a comparison, and a std test and a kotor parser test use it.
  - *Done:* [spec §20](spec.md#20-tests) and [§13, Checks](spec.md#checks).
    - The prerequisite first: `main` and `build` may return `!` or `!i32`
      ([spec §15, Entry point, rule 4](spec.md#entry-point)), and the error is printed by
      ctxlang code the compiler writes around the entry point, with the pieces an `@fmt` to
      std's `io::Stderr` has, not by a second formatter in the C runtime: the program's
      `#write` fns are used, and the interpreter agrees. A payload field without a writer was
      `_` in every `@fmt` of an error; a struct, a union, an enum, an optional, an array and a
      slice are now written from their parts, `Point{ x = 1, y = 2 }`
      ([spec §13, Formatting, rule 10](spec.md#formatting)), which is also what shows a
      check's two sides.
    - `#test fn reads { mut t: Test, mut fs: Fs } -> ! { ... }`: a test takes capabilities, as
      `main` does, one of them a `Test`, and returns nothing or a `!`.
      `#test{ panics = "text" }` passes by panicking with that text.
    - `@expect(&t, text.len == 42)` is the one builtin, and
      [§13, Checks, rule 5](spec.md#checks) says why no function could be it: the report is
      `cfg.ctx:9: fail: cfg_tests::reads: text.len == 42: 17 == 42`, and a function is given
      values, without the check's position, its condition's text, or the two sides of a
      comparison inside it. `test::expect_equal{ &t, a, b }` was weighed first: a
      generic fn can compare its `T`s since 4.1, but it has no line to report and no
      condition to quote, a hole of an `@fmt` in it can't be a `T`, and a position builtin
      passed by hand, `at = @here()`, makes the unsafe form (leaving it out, or pasting
      another line's) the easy one. Everything but those three things is std's: the builtin calls
      `test::check`, and writes the sides with the `#write` fns any `@fmt` uses. It reports
      through the `Test` the test passes down, so no state is hidden and a build that isn't
      a test build can't reach a check. The check goes on, and its value is the condition's;
      `@require(&t, p != null)` is the same check as a statement that ends the test where it
      doesn't hold ([§13, Checks, rule 6](spec.md#checks)).
    - `ctxc test PATH [FILTER...]`, with or without a build.ctx, builds the program with std's
      runner as its entry point in place of `main` (which needn't exist) and runs it. Each
      test runs in a process of its own ([spec §20, rule 6](spec.md#20-tests)), so a panic fails one test
      with its message, no static leaks from one test to the next, and tests run at once;
      a test that doesn't end is ended after `--timeout` seconds. One line for each failure,
      `FILE:LINE: fail: NAME: ...`, then `tests: N run, P passed, F failed, S not selected`;
      the exit code is 1 if a test failed.
    - Rule 1, no silent pass: a test that made no check fails (`no check ran`), a filter that
      matches nothing and a program without tests exit with 1 and say so, and a test whose
      process ends in any way but a pass is a failure with its exit code.
    - The compiler finds the tests, where PLAN 6.3 had a build program generate a `main`:
      a `#test` is checked where it is written, in every build, and takes any capability
      `main` may. The runner is std's `test::main`, a `#test_main` fn a program can replace.
      It needs no threads and no `proc::capture` (which isn't built): a test's output goes to
      a file, and the runner waits with `proc::wait_for`.
    - Used: [std/tests](std/tests) (15 tests of `@min`, `@max`, `@clamp`, `cmp`, `utf8`, `@fmt`'s specs, `list` and
      `map`, `ctxc test std/tests`), and KOTOR's 2DA parser
      ([kotor/lib/formats/twoda_test.ctx](../kotor/lib/formats/twoda_test.ctx), 5 tests on
      tables made by hand, no game install: `ctxc test kotor/tools/fmttest twoda`), which were
      fmttest's `check_text_2da` with its hand-rolled `Tally` and `expect`.
    - Not built, each for its reason ([spec §20, rule 11](spec.md#20-tests)): a leak check
      (std's one allocator is the arena), a temporary directory, tests with arguments. JSON
      output is 6.2's.

- [x] **5.2 Tests as files.**
  The suite's 750+ programs are Python strings; as `.ctx` files with an expected-output header
  they are also examples a model can read. [PLAN 6.1](PLAN.md#6-tools-in-ctxlang).
  - *Done when:* the suite runs from files, and Python only drives the runner (or nothing).
  - *Done:* [tests/README.md](tests/README.md) is the format, [tests/cases](tests/cases) the
    2,446 cases, and [tools/suite](tools/suite) the runner, a ctxlang program
    (`ctxc run tools/suite`). Nothing drives it: the Python tests are deleted.
    - **A case is a program that says what it does.** What it prints goes after it, as
      `//# stdout:` and a block of `//| ` lines; an error or a panic is said on its own line,
      `let x: u8 = 300  //~ error at 17: MESSAGE`, so no line number is written down and the
      marker moves with the code. A program whose bytes matter (one that ends in the middle of
      a comment) keeps them, with its expectations in `NAME.expect` beside it. A directory with
      a `CASE` is a list of steps for what one program can't state: several files, a build.ctx
      project, `ctxc` commands with their output, files written and expected.
    - **Everything is compared whole** (rule 1): every error ctxc reports, with its position
      and its whole message, where 1,460 of the Python suite's 2,246 programs were checked for
      a part of the first error's message; every byte of standard output and standard error;
      the exit code. `has:`, `lacks:`, `any` and the wildcards `{n}`, `{hex}` and `{any}` are
      for what differs from machine to machine, and are written out where they are used.
    - **No silent pass.** A case that states nothing, a filter that selects nothing, a file
      under `cases/` that is no case, and the runner's own crash fail the run; a skipped case
      is printed and counted. A program the interpreter refuses must say `//# interp: cannot
      run` (99 do), where the Python harness skipped it without a word, and one that says so
      and runs fails too. [cases/Suite](tests/cases/Suite) runs the runner on fifteen cases
      that are each wrong in one way and expects each failure's line, so the suite tests that
      it tests.
    - **The runner does what tools/toolchain.py did:** ctxc from the bootstrap and then from
      the current source, the same C compiler and flags, executables cached by their C's hash,
      build.ctx projects through `ctxc graph`, and each program also run by `ctxc interp`,
      which must give the same (685 programs; 2 say why they are left out). Each case has a
      process of its own, as many at once as there are processors, and a pass isn't run again
      until ctxc, std, the runtime, the C compiler, the runner or the case changes, by hash:
      80 s for every case and 5 s when nothing changed, where the Python suite took
      six and a half minutes. A failure is `FILE:LINE: fail: NAME: WHAT`, as `ctxc test`
      prints one, at the statement that didn't hold, with what was expected and what came.
    - **Converted from a recording, not transcribed.** The Python suite ran with hooks in
      toolchain.py's entry points, in `subprocess` and in unittest's assertions, which
      recorded each program, its input and what became of it: 2,246 programs and 385 other
      actions of 872 tests. A case was written from each record and kept only once the runner
      passed it, so each passes because the runner saw what Python saw. The 157 tests that did
      more than run one program (ctxc commands, projects, child processes, files) were then
      checked one by one against their assertions; a child process is a ctxlang helper
      (tests/helpers) where it was the running Python.
    - **Shown to check.** 66 cases across 22 kinds of expectation were each broken in one
      way, and the runner failed every one with the right line; and with two deliberate
      breakages of ctxc (a message changed, a check disabled) the tests the Python suite
      failed and the tests whose cases failed were the same.
    - **Deleted:** tests/test_ctxlang.py, tests/test_borrow_lifetimes.py, tools/corpus.py (the
      runner's `--corpus` writes the recovery test's corpus from the cases), tools/interp_diff.py
      (the runner's summary counts what the interpreter ran, refused and was spared, and `-v`
      the refusals by reason), and all of tools/toolchain.py but what builds ctxc for
      tools/recover.py, the one Python tool left (PLAN 6.2).
    - *Not built:* a mode that rewrites expectations (`--bless`). A failure prints the actual
      text in the case's own block form, to be read before it is pasted: an expectation that
      a tool wrote is one nobody stated.

## 6. Feedback built for agents

- [ ] **6.1 `ctxc check`.**
  Front end only, no C compile: every error in the program, not only the first, fast. Today
  agents use `run` or `exe`.
  - *Done when:* `ctxc check DIR` (with or without a build.ctx) reports all errors and exits non-zero.

- [ ] **6.2 JSON diagnostics with related locations.**
  `--json` on check, run and exe: file, line, column, end, message, and notes pointing at the
  other place involved (the first borrow, the declaration, the earlier variant).
  - Details: today one line per error, `PATH:LINE:COL: error: MSG` ([ctxc/main.ctx](ctxc/main.ctx), `error`).
  - *Done when:* every diagnostic has the JSON form, and the borrow and escape errors carry a note at the other place.

- [ ] **6.3 Machine-applicable fix-its.**
  Many errors already say what to write ("`next` has no field `movie`: write `m = &movie`"). Give
  those a structured replacement (span and new text), and `ctxc check --fix` to apply them.
  - *Done when:* the pun, unused-result (`_ =`), `@as` and missing-field errors carry fixes, and `--fix` applies them.

- [ ] **6.4 Stack traces on panic.**
  A panic gives the check's position only; "a panic in `nwarg::param` names no routine". Print
  the frames, at least in builds that aren't optimized; PLAN's open decision defers it.
  - Details: [PLAN, Open decisions](PLAN.md#open-decisions), [PLAN, Known gaps](PLAN.md#known-gaps), [tooling-gaps.md](../kotor/docs/tooling-gaps.md).
  - *Done when:* a panic in a default `ctxc run` prints its call path with file:line per frame.

- [ ] **6.5 Errors that point at the cause.**
  A build.ctx missing one source directory gives thirty "unknown type or namespace mg" instead of
  one saying no file declares `namespace mg`; a merge conflict gives nine syntax errors at `<<`.
  - Details: F#12.
  - *Done when:* both cases give one error naming the cause.

## 7. A reference a model can trust

- [ ] **7.1 Move the quick reference into ctxlang.**
  Agents learn the language from [kotor/docs/ctxlang-quickref.md](../kotor/docs/ctxlang-quickref.md),
  which lives in the game, not the language. No model has ctxlang in its training data: this
  page is its first source of truth. Move it to `ctxlang/`, keep it short, name the spec
  sections, and list the common mistakes with their fixes.
  - *Done when:* it lives in ctxlang, kotor's AGENTS.md points to it, and it's current with this checklist's changes.

- [ ] **7.2 Every code block in the spec and the reference compiles.**
  The spec has drifted: hex literals work but aren't in §11 (F#16), and §14's folded consts
  aren't what the folder takes (F#37). A test extracts each block (marked as a whole program,
  a fragment, or an expected error) and checks it with ctxc.
  - *Done when:* the test runs in the suite and every block passes or is marked as an error example.

## 8. Next tier

- [ ] **8.1 File-private declarations and choosing files.**
  A directory is one flat namespace: parallel agents agree on helper names by message, a file
  can't keep private helpers, and one half-written file breaks every build that adds its directory.
  - Details: F#5, F#14; [spec §10](spec.md#10-namespaces).
  - *Done when:* a declaration can be private to its file, and a build can add one file.

- [ ] **8.2 Borrow contracts in signatures.**
  The escape check infers what a call borrows from the callee's body, so an error at a call
  depends on code the model doesn't see, and false positives push code to heap copies. A written
  contract (the `#noescape` field attribute that was put off) keeps reasoning local.
  - Details: F#2; [spec §14, Escape check](spec.md#escape-check), [§16](spec.md#16-open-questions).
  - *Done when:* decided: either the attribute, or a reason it isn't needed, recorded in the spec.

- [ ] **8.3 A formatter.**
  `ctxc fmt`: one canonical layout, so a model's edits (exact-string matching) and diffs stay
  reliable.
  - *Done when:* `ctxc fmt` is idempotent over std, ctxc and kotor.

- [ ] **8.4 Remaining friction.** Enum ordering and counts (F#10), `&fn` as a struct field
  (F#13), slices staying `[]mut` until freed (F#22, F#25), a `mut` argument that is a temporary
  (F#27), locking through a read-only pointer (F#28), tuples (F#29), scoped lock (F#23), hex
  literals in the spec (F#16), array lengths from any folded const (F#37). Take them as they
  come up; each has its entry in FRICTION.md.

## Not adding

Methods, macros, traits, implicit conversions and default arguments, for brevity's sake. The
explicitness is why the semantics work for a model: make the explicit forms cheap to write
(3.1, 3.2, 3.3) rather than hiding them.
