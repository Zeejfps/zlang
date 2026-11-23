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

- [ ] **1.1 Reject a read-only argument that a later argument's call changes.**
  `types::prune{ s = c.ty, t = expr{ &c, e } }` copies `c.ty`, then `expr` changes `c`, and
  `prune` reads the stale copy. `show{ n = c.n, z = bump{ &c } }` passes the old `c.n` silently.
  §3.1 checks overlap between one call's own arguments, not a `&c` inside a nested call.
  Either reject it, or evaluate nested calls before plain arguments, and say which in the spec.
  - Details: F#24 (the only entry giving a wrong answer, 8 sites in ctxc); [spec §3.1](spec.md#31-exclusivity), [§14 rule 6](spec.md#14-memory).
  - *Done when:* both examples above are compile errors (or provably read the new value), with tests.

- [ ] **1.2 Give unchecked pointer indexing its own syntax.**
  `q[i]` on a `*T` is `(q + i).*`, unchecked, but looks the same as the bounds-checked `s[i]` on
  a slice or array. A model will assume it is checked. Same for `s.ptr[i]`.
  Move it to a spelling that says so (e.g. `@unchecked(q, i)` or `(q + i).*` only), so every
  route to undefined behaviour is greppable.
  - Details: [spec §12, Pointers, rule 5](spec.md#pointers), [§12, Slices, rule 2](spec.md#slices).
  - *Done when:* `q[i]` on a pointer is an error that says what to write; ctxc, std and kotor are migrated.

- [ ] **1.3 Make the unchecked operations auditable as a set.**
  With 1.2 done, `@cast`, `@slice`, pointer arithmetic, unchecked indexing and `@addr` are the
  ways to undefined behaviour. A build should be able to forbid them outside chosen directories
  (e.g. a `build::allow_unchecked{ &b, exe, dir }`, everything else an error), so game code can't
  reach for them and review only looks where they are allowed.
  - Details: [spec §13](spec.md#13-builtins), [§12, Pointers, rule 7](spec.md#pointers).
  - *Done when:* a build program can deny them per directory, and kotor's game code builds with them denied outside its platform and binding layers (or the exceptions are listed).

- [ ] **1.4 Fix float-to-float `@as` in the spec.**
  §13 says `@as` panics if the value isn't representable, but `@as(f32, 1e300)` gives `inf`.
  When spec and compiler disagree, the model believes the spec. Say float-to-float rounds and
  overflows to infinity (or give it its own builtin), and check `ifoverflow` doesn't claim to cover it.
  - Details: F#26; [spec §13](spec.md#13-builtins), [§11, Overflow](spec.md#overflow).
  - *Done when:* spec and compiler agree, with a test.

## 2. Make the safe form the easy form

- [ ] **2.1 Split borrows.**
  `f{ &e, xs = &e.list }` is two mut references to `e`, so the World and the VM live behind raw
  `*mut` pointers that the checker doesn't track at all: the exclusivity rule pushes the
  program's central objects out of checking. Allow disjoint places of one root in one call (and
  a bind beside a `&` of what it doesn't hold), keeping the check where they overlap.
  - Details: F#4 (5 write-ups), F#27, F#28; [spec §3.1](spec.md#31-exclusivity).
  - *Done when:* `f{ &e, xs = &e.list }` compiles where `f` can't reach `list` through `e` (or the rule for what's allowed is in the spec), and kotor's World is passed as a checked `mut` field somewhere it was a raw pointer.

## 3. First-draft traps

What a model writes by default should compile, or fail with the exact fix.

- [ ] **3.1 Pun a place's last name: `&g.rng` fills `rng`.**
  Today `deal_hand{ &g.rng, &g.player, deck }` is a parse error and must be `rng = &g.rng`. Hit by
  12 of 17 write-ups, every file's first compile. Also `g.rng` for a read-only field.
  - Details: F#1; [spec §3, rule 6](spec.md#3-calls).
  - *Done when:* `f{ &a.b.c, a.d }` supplies `c` and `d`, with tests; the old error is gone.

- [ ] **3.2 A `for` loop.**
  Every loop is `let mut i = 0; while i < n { ...; i = i + 1 }`: forgotten increments are hangs,
  the worst failure an agent can hit. A `for i in lo..hi` and a `for x in slice` (with index form)
  would cover nearly all.
  - Details: F#20 (about 70 loops in bink_video.ctx alone); [spec §11](spec.md#11-statements-and-control-flow).
  - *Done when:* both forms are in the spec and ctxc, with `break`/`continue`/labels as for `while`.

- [ ] **3.3 Index with any integer type.**
  `a[i]` with `i: i32` is "expected usize", so the code is `a[@as(usize, i)]` after a range check
  (about 150 in rules, 84 in walk). Let an index take any integer type, its bounds check
  rejecting negatives too. Also: typed integer consts converting where their value fits, as
  literals do (`@as(i32, gl::LINEAR)`).
  - Details: F#7; [spec §12, Arrays](spec.md#arrays), [§12, Slices](spec.md#slices), [§11, Widening](spec.md#widening).
  - *Done when:* `a[i]` and `s[lo..hi]` accept any integer type and panic below 0.

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
  Many errors already say what to write ("a pun is a name alone: write `rng = &g.rng`"). Give
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

- [ ] **8.4 Remaining friction.** Enum ordering and counts (F#10), `&fn` as a struct field and
  bind records freed (F#13), slices staying `[]mut` until freed (F#22, F#25), tuples (F#29), scoped
  lock (F#23), hex literals in the spec (F#16), array lengths from any folded const (F#37). Take
  them as they come up; each has its entry in FRICTION.md.

## Not adding

Methods, macros, traits, implicit conversions and default arguments, for brevity's sake. The
explicitness is why the semantics work for a model: make the explicit forms cheap to write
(3.1, 3.2, 3.3) rather than hiding them.
