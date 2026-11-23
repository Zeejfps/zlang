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
    - `lib/video` (67): the Bink decoder's inner loops, and libm for its audio tables.
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

- [ ] **3.4 `iferr` and `ifnull` chain.**
  `f{} iferr { return } ifnull { return }` on a `!?T` is a parse error. Also, `x == f{} ifnull y`
  parses as `x == (f{} ifnull y)`; at least make that an error that says so.
  - Details: F#8; [spec §8, Optional, rule 7](spec.md#optional), [§8, Errors, rule 8](spec.md#errors), [§11, Expressions](spec.md#expressions).
  - *Done when:* the chain compiles and the comparison case is unambiguous or an error.

- [ ] **3.5 A condition may continue on the next line.**
  `if a\n or b {` is a parse error pointing at the wrong place, since a call's `}` ending a line
  starts the block. At minimum, a line starting with `and`/`or`/a binary operator continues the
  condition, and the error points at the break.
  - Details: F#9; [spec §11, rule 2](spec.md#11-statements-and-control-flow).
  - *Done when:* `if a\n or b {` compiles, with tests.

- [ ] **3.6 Small syntax.**
  A bare `{ ... }` block as a statement; `defer if c { ... }`; a one-expression match arm without
  braces (`a => "A"`); `try f{}.x` parsing as the spec's own example says.
  - Details: F#11; [spec §11, Defer](spec.md#defer), [§8, Errors, rule 7](spec.md#errors).
  - *Done when:* each of the four compiles, or the spec drops it.

- [ ] **3.7 `is` doesn't break names.**
  `let is = ...` and `fn is{}` are "expected a name, found 'is'", far from the cause. Make `is`
  contextual (as `distinct` is), or give the error the fix.
  - Details: F#15; [spec §1, rule 4](spec.md#1-top-level).
  - *Done when:* `is` works as a name, or the error says it is a keyword and suggests another.

## 4. Don't make the model hand-roll error-prone code

- [ ] **4.1 Derived equality and hashing.**
  `p == q` on a struct is "no built-in equality", so ctxc has about 90 lines of hand-written
  `hash` and `eq` for types; one that forgets a field is a silent bug. Derive `==` for structs
  and unions without pointers (or slices), and a builtin `@hash`, or derive them in a build
  program (PLAN 3.2).
  - Details: F#30; [spec §11, Expressions, rule 5](spec.md#expressions); [PLAN 3](PLAN.md#3-metaprogramming).
  - *Done when:* `==` on such a struct works, and `map` can key on one without a hand-written hash.

- [ ] **4.2 Math in std.**
  No `sqrt`, `sin`, `cos`, `pow`, `floor`, `ceil`, `trunc`: the Bink audio declares libm's itself,
  and MP3's const tables carry their own cosine series (which run while compiling, so they can't
  call C).
  - Details: F#6; [std/math.ctx](std/math.ctx).
  - *Done when:* std's `math` has them, usable in consts too.

- [ ] **4.3 Integer `@min`, `@max`, and clamping or rounding conversions.**
  `if a < b { a } else { b }` by hand; float-to-integer can only check, so audio code rounds by
  adding 1.5 * 2^52 and reading the bits.
  - Details: F#6, F#17; [spec §13](spec.md#13-builtins).
  - *Done when:* min/max and a rounding/clamping float-to-int conversion exist.

- [ ] **4.4 Format specs in `@fmt`.**
  No width, padding, hex or fixed-point (`{:<16}`, `{:08x}`, `{:.3}`), so programs write a wrapper
  type and writer for each. Also: 100.0 prints as `1e+02`.
  - Details: F#3 (5 write-ups); [spec §13, Formatting](spec.md#formatting).
  - *Done when:* the common specs work on numbers and strings, and floats print in plain form where short.

## 5. Tests

- [ ] **5.1 `#test` functions, `@expect` and a runner.**
  Models work best test-first; today each KOTOR parser needs its own tool program to be tested.
  The design is written: [PLAN 6.3](PLAN.md#6-tools-in-ctxlang). Prerequisite: settling how
  `main -> !` prints an error ([PLAN 3.1](PLAN.md#3-metaprogramming)), which `@expect` shares.
  - *Done when:* `ctxc test DIR` runs a program's `#test` fns, prints failures with both sides of
    a comparison, and a std test and a kotor parser test use it.

- [ ] **5.2 Tests as files.**
  The suite's 750+ programs are Python strings; as `.ctx` files with an expected-output header
  they are also examples a model can read. [PLAN 6.1](PLAN.md#6-tools-in-ctxlang).
  - *Done when:* the suite runs from files, and Python only drives the runner (or nothing).

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
  The spec has drifted: `try f{}.x` (F#11) contradicts the parser, hex literals work but aren't in
  §11 (F#16), and §14's folded consts aren't what the folder takes (F#37). A test extracts each
  block (marked as a whole program, a fragment, or an expected error) and checks it with ctxc.
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
