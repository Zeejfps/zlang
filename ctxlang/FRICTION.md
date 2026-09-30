# Language friction

Points that came up while writing ctxc in ctxlang. Each one is evidence for a spec change; §16
numbers refer to spec.md's open questions. Resolved items are removed, and the rest keep their
numbers, which PLAN.md and commit messages cite; git history has the resolved ones.

- **7. Exclusivity blocks "context plus one field".** `f{ &e, xs = &e.list }` is rejected, so the
  heap is threaded separately. Split borrows, or a pattern for it.
- **10. No methods** (§16 Q4). `slice::get{ s = xs, i }` and `list::push{ list = &xs, item }`
  everywhere; `xs.get{ i }` would shrink code a lot. *Partly:* slices are built in (spec §12), so
  `slice::get{ s = xs, i }` is now `xs[i]`; `list::` and `map::` calls remain.
- **11. Float-to-float `@as` reads as fallible.** It never panics, but looks like it might. A
  separate conversion, or saying so in §13.
- **14. ctxi call overhead** (implementation, not language): `slice::get`/`at` made about a million
  calls in one profile. Inlining trivial std accessors in ctxi would speed development.
  *Partly:* slice indexing is built in now, so those calls are gone.
- **16. A parameter name can defeat punning.** `utf8::push`, `push_char` and `push_u64` call their
  builder `b`, so a builder named `out` must be passed as `b = &out`, not `&out`. A std
  convention (name a builder `b` everywhere, or name the field after its role) would help.
- **17. No `@min` or `@max`.** ctxc writes them out by hand. A generic std function can't compare
  an opaque `T` (§9), so they would have to be builtins, and the builtin set stays small: they
  stay written out unless a way to constrain `T` to numbers comes along.
- **19. Enum from an index is a chain of compares** (implementation). `@as(Kind, base + i)`, the
  lexer's keyword and operator lookup, checks every variant in turn (62 for `tok::Kind`). An enum
  whose values are contiguous could lower to one range check instead.
- **21. An inferred slice type is too mutable.** `let mut bs = list::items{ list = xs }` gives `bs`
  the type `[]mut T`, so a later `bs = f{}` with a `[]T` result is an error. The parser annotates
  such locals. Inferring the type from every assignment, as literals are (spec §11 Literals),
  would fix it.
- **22. No structural equality or hashing.** Interning types in a `map::Map` keyed by a union
  took a hand-written `hash` and `eq` (`types.ctx`, about 90 lines). `eq` is a match inside a
  match for each variant. Derived `==` for structs and unions without pointers, or a builtin
  `@hash`, would remove this.
- **23. Narrowing skips `let mut` locals** (spec §8). A `?T` local that a loop reassigns has to be
  copied (`let q = p`) before it can be narrowed or matched (`check::const_decl`).
- **24. A `?Union` takes two steps to match.** `map::get` returns `?Entry`, so code tests for
  `null` and then matches the value. A pattern that goes through `some`, or `match` arms that
  list a `?U`'s variants next to `null`, would take one.
- **25. A diagnostic takes three lines.** `let mut b = message{ c }`, then
  `pushed{ ok = @fmt(&b, ...) }`, then `error{ &c, at, msg = utf8::view{ b } }`: 24 times in
  `check.ctx`. `@fmt` can't produce a `utf8::String` in an expression.
- **26. Allocation failure everywhere.** Each `list::push` or `map::put` needs
  `if not ... { @panic(...) }`, so every module grows its own `push`/`add` wrappers
  (`check.ctx` has six). An arena that can't fail, or a std `must` helper, would help.
- **27. No checked arithmetic.** Const folding detects i64 overflow by hand, with `@wrap_*` and
  sign tests (`check::arith`). `@checked_add` and the like, returning `?T`, would do it, and
  stage 6 step 7 needs the same for every const.
- **28. `null` can't name a variant.** A union for types can't have a `null` variant, so it is
  `nil` (`types::Type`, and `syntax::ExprKind` before it).
- **29. An `if` of literals has no type as a `@fmt` hole** (spec §11 Literals). `@fmt(&b, "{}",
  if m { "mut " } else { "" })` makes two arrays of different lengths. The hole needs a typed
  `let` first. A hole could expect a `utf8::String`, as a bare literal hole already does.
- **30. ctxi takes the first `--`** (implementation). `python -m ctxi ctxc decls STD -- FILE`
  loses the `--`, so it has to be `ctxc -- decls STD -- FILE`.
- **31. A read-only argument can be copied before a later argument changes it.** Arguments are
  evaluated in order, so `types::prune{ s = c.ty, t = expr{ &c, e } }` copies the type store,
  then `expr` adds a type to the real one, and `prune` indexes the stale copy out of bounds.
  §3.1 only checks overlap between arguments of one call, not a `&c` inside a nested one. The
  fix is a local first (`check::typed`). A rule that rejects this, or evaluates nested calls
  before plain arguments, would have caught eight such calls.
- **32. An empty slice is inferred as `[]mut`** (again #21). `let mut fields =
  slice::empty(types::Field){}` can't later take a `[]types::Field`.
