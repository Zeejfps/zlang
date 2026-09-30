# Language friction

Points that came up while writing ctxc in ctxlang. Each one is evidence for a spec change; §16
numbers refer to spec.md's open questions. Resolved items are removed, and the rest keep their
numbers, which PLAN.md and commit messages cite; git history has the resolved ones.

- **3. A local shadows a function.** After `let binds = ...`, `binds{...}` resolves to the local and
  fails. Warn, or let calls skip non-function locals. The lexer renamed a local `span` to `s` to
  stay clear of the function `span`. Context fields and match bindings do it too: the parser's
  `binders` function was renamed `binder_list` because a context field `binders` hid it, and the
  dumps bind `name = n` in patterns to keep the `name` function visible.
- **7. Exclusivity blocks "context plus one field".** `f{ &e, xs = &e.list }` is rejected, so the
  heap is threaded separately. Split borrows, or a pattern for it.
- **10. No methods** (§16 Q4). `slice::get{ s = xs, i }` and `list::push{ list = &xs, heap, item }`
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
- **17. No `@min` or `@max`.** The lexer writes them out by hand. They could be std functions,
  generic over integer types.
- **18. `fn main { ... }` without a context misparses.** The first braces are always the context,
  so `fn main { let x = 1 }` fails with `expected a name, found 'let'`. Writing tests hit this
  three times, and the parser's tests once more. The error could say that a function needs its
  context `{}` before the body.
- **19. Enum from an index is a chain of compares** (implementation). `@as(Kind, base + i)`, the
  lexer's keyword and operator lookup, checks every variant in turn (62 for `tok::Kind`). An enum
  whose values are contiguous could lower to one range check instead.
- **21. An inferred slice type is too mutable.** `let mut bs = list::items{ list = xs }` gives `bs`
  the type `[]mut T`, so a later `bs = f{}` with a `[]T` result is an error. The parser annotates
  such locals. Inferring the type from every assignment, as literals are (spec §11 Literals),
  would fix it.
- **22. Building a message takes a line per piece.** `expected ')', found 'x'` is five `utf8::push`
  calls on a builder. The parser and lexer have a dozen of these. *Partly:* a builder holds its
  allocator's state now, as lists and maps do, so the calls no longer pass the heap. A std
  function joining a slice of strings would shorten them further, but an array literal can't be
  passed where a slice is expected, so it needs a named local array first.
