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
