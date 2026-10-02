# Language friction

Points that came up while writing ctxc in ctxlang. Each one is evidence for a spec change; §16
numbers refer to spec.md's open questions. Resolved items are removed; git history has them.

Items are numbered by how much fixing them would pay off, most first: how often ctxc hits them
today, and whether they cost lines or correctness. Counts are from ctxc's source as of the
errors and capability-variable work (`e19f1fe`).

- **1. Allocation failure everywhere.** Each `list::push` or `map::put` returns `bool`, so it
  needs `if not ... { @panic(...) }`: about 115 such lines in ctxc, 100 of them in `check.ctx`
  and `lower.ctx`, and every module grows its own `add`/`push` wrapper (diag, drive, ir_read,
  parser, types, source, lexer, emit_c, and four in `check.ctx`). Errors (spec §8) now give a
  cheap fix: `list::push` and the rest return `!` with an `alloc::out_of_memory` error, so a
  caller that can fail writes `try`, and one that can't writes `iferr { @panic(...) }`. An arena
  that can't fail, or a std `must` helper, would still help code that wants neither.
- **2. A diagnostic takes three lines.** `let mut b = message{ c }`, then
  `pushed{ ok = @fmt(&b, ...) }`, then `error{ &c, at, msg = utf8::view{ b } }`. This was 24
  times in `check.ctx` when first noted; it is now 188, plus 12 in `lower.ctx` and `parser.ctx`.
  `@fmt` can't produce a `utf8::String` in an expression. An `@fmt` form that returns the text
  (from an allocator in scope), or a std `error_fmt`-style helper once `@fmt` can forward its
  arguments, would make each one a line.
- **3. A read-only argument can be copied before a later argument changes it.** Arguments are
  evaluated in order, so `types::prune{ s = c.ty, t = expr{ &c, e } }` copies the type store,
  then `expr` adds a type to the real one, and `prune` indexes the stale copy out of bounds.
  §3.1 only checks overlap between arguments of one call, not a `&c` inside a nested one. The
  fix is a local first (`check::typed`). Still silent: `show{ n = c.n, z = bump{ &c } }` passes
  the old `c.n` with no error. Rare, but the only item here that gives a wrong answer instead of
  a compile error. A rule that rejects this, or evaluates nested calls before plain arguments,
  would have caught eight such calls.
- **4. No methods** (§16 Q4). `list::push{ list = &xs, item }` everywhere: ctxc makes about 580
  `list::` and `map::` calls, and 150 `slice::` ones. `xs.push{ item }` would shrink code a lot.
  *Partly:* slices are built in (spec §12), so `slice::get{ s = xs, i }` is now `xs[i]`.
- **5. A `?Union` takes two steps to match.** `map::get` returns `?Entry`, so code tests for
  `null` and then matches the value; ctxc calls `map::get` about 100 times. A pattern that goes
  through `some`, or `match` arms that list a `?U`'s variants next to `null`, would take one.
  `ifnull` (spec §8) helps when the missing case leaves, but not when it is one arm among the
  variants. *Planned:* PLAN.md stage 1 (`null` arms).
- **6. No checked arithmetic.** Const folding detects i64 overflow by hand, with `@wrap_*` and
  sign tests (`check::arith`). `@checked_add` and the like, returning `?T`, would do it. This
  matters more now: PLAN.md 3.3's compile-time evaluator runs IR and must detect overflow on
  every integer operation.
- **7. No structural equality or hashing.** Interning types in a `map::Map` keyed by a union
  took a hand-written `hash` and `eq` (`types.ctx`, about 90 lines). `eq` is a match inside a
  match for each variant. Derived `==` for structs and unions without pointers, or a builtin
  `@hash`, would remove this. Still: `p == q` on a struct is "P has no built-in equality".
  PLAN.md 3.2's reflection could derive them in a build program instead.
- **8. Narrowing skips `let mut` locals** (spec §8). A `?T` local that a loop reassigns has to be
  copied (`let q = p`) before it can be narrowed or matched (`check::const_decl`). Spec §8 rule 3
  now says so; about ten copies in ctxc.
- **9. An optional can't be compared with a value.** `map::get{ m = c.access, key } ==
  Access::field` is an error ("cannot compare ?A with A"), so it takes a local and
  `x != null and x == Access::field` (`check::access_is`). With #8, a `let mut` optional needs a
  copy even for that. `==` between `?T` and `T` meaning "is some and equal" would do. *Planned:*
  PLAN.md stage 1.
- **10. An inferred slice type is too mutable.** `let mut bs = list::items{ list = xs }` gives `bs`
  the type `[]mut T`, so a later `bs = f{}` with a `[]T` result is an error. The same goes for an
  empty slice: `let mut fields = slice::empty(types::Field){}` can't later take a
  `[]types::Field`. ctxc annotates about 30 such locals. Inferring the type from every
  assignment, as literals are (spec §11 Literals), would fix it.
- **11. Exclusivity blocks "context plus one field".** `f{ &e, xs = &e.list }` is rejected ("two
  mut references to `e` in one call"). ctxc settled on an idiom: a struct holds its heap as a
  `*mut` (`Parser.heap`, `Checker.heap`), which §3.1 doesn't track, and lists that a helper
  pushes to are locals. Split borrows would still remove the idiom.
- **12. An `if` of literals has no type as a `@fmt` hole** (spec §11 Literals). `@fmt(&b, "{}",
  if m { "mut " } else { "" })` makes two arrays of different lengths ("branches have different
  types: [4]u8 and [0]u8"). The hole needs a typed `let` first. A hole could expect a
  `utf8::String`, as a bare literal hole already does. PLAN.md stage 4 rewrites this rule, so it
  could be settled there.
- **13. A parameter name can defeat punning.** `utf8::push_char`, `push_u64` and the rest call
  their builder `b`, so a builder named `out` must be passed as `b = &out`, not `&out`: about 30
  times, mostly in `dump.ctx`. `@fmt` has replaced most direct pushes, which shrank this. A std
  convention (name a builder `b` everywhere, or name the field after its role) would help.
- **14. A pattern can't bind a mutable local.** Calling through a capability's field needs a
  mutable capability, and `let ... else` bindings are read-only (spec §11, Let-else). *Mostly
  solved:* `ifnull` (spec §8, Optional) unwraps into any `let`, so examples/glfw has
  `let mut gl = gl::load_2_0{ ... } ifnull { ... }`. Only a pattern's own bindings are still
  read-only (`let some{ value = mut g } = ...` is a syntax error), and PLAN.md 1.1
  (`let p = e else { ... }`) would take the rest.
- **15. Float-to-float `@as` reads as fallible, and the spec says it is.** §13 says `@as` "panics
  if the value isn't representable in T", but `@as(f32, 1e300)` gives `inf` without panicking.
  Only five such conversions in ctxc and std, so this is a spec fix: say float to float rounds
  (and overflows to infinity), or give it a separate conversion.
- **16. No `@min` or `@max`.** ctxc writes them out by hand, in only a few places. A generic std
  function can't compare an opaque `T` (§9), so they would have to be builtins, and the builtin
  set stays small: they stay written out unless a way to constrain `T` to numbers comes along.
- **17. `null` can't name a variant.** A union for types can't have a `null` variant, so it is
  `nil` (`types::Type`, and `syntax::ExprKind` before it). Cosmetic, and one place.
- **18. Enum from an index is a chain of compares** (implementation). `@as(Kind, base + i)`, the
  lexer's keyword and operator lookup, lowers to a `switch` with one case per variant (62 for
  `tok::Kind`, `lower::to_enum`), which the C backend emits as a chain. An enum whose values are
  contiguous could lower to one range check instead. With the C compiler in between, this is
  unlikely to show in a profile; the front end's time hasn't been profiled (PLAN.md, Known gaps).

