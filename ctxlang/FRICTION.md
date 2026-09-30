# Language friction

Points that came up while writing ctxc in ctxlang (stages 0–2 of the self-hosting plan).
Each one is evidence for a spec change; §16 numbers refer to spec.md's open questions.

1. ~~**String literals need a local.** Every literal is bound (`let x = "..."`) and passed as
   `utf8::of{ chars = &x }`. The reader and emitter use a generic `put(A){ a = "..." }` to get
   around it. Literals should work where a slice or string is expected (§16 Q11).~~
   *Done:* a literal is a view where a `[]u8` or `utf8::String` is expected (spec §11 Literals).
2. ~~**Narrowing is narrow.** It works only for a lone `x != null` / `x == null` on a local: not
   through `and`/`or`, not on fields (`v.fields != null`). Code copies into locals or uses
   `let … else` instead.~~ *Done:* narrowing goes through `and`, `or` and `not`, applies to field
   paths from a read-only root and in `while` bodies (spec §8 Optional). Mutable places and
   paths through a pointer or index still need a copy.
3. **A local shadows a function.** After `let binds = ...`, `binds{...}` resolves to the local and
   fails. Warn, or let calls skip non-function locals.
4. ~~**No shared match arms.** `a | b => { }` would collapse long runs of `x => { true }`.~~
   *Done:* spec §8 Match, rule 3; patterns in an arm may share bindings.
5. ~~**No labeled break** out of nested loops; flags instead (§16 Q10).~~ *Done:* `name:` labels a
   `while`, and `break name` / `continue name` act on it (spec §11, rule 10).
6. ~~**No shift or bitwise operators.** `256 << 20` becomes `268435456`; masks go through
   `@wrap_*`. Needed: `<< >> & | ^`.~~ *Done:* spec §11 Expressions.
7. **Exclusivity blocks "context plus one field".** `f{ &e, xs = &e.list }` is rejected, so the
   heap is threaded separately. Split borrows, or a pattern for it.
8. ~~**Parentheses around `if` / `while` conditions** are noise when braces are required.~~
   *Done:* dropped for conditions and scrutinees (spec §11.1–2).
9. **Integer literals default to i32.** `let mut i = 0` compared with a `usize` length is an error;
   many `: usize` annotations follow. Infer from use.
10. **No methods** (§16 Q4). `slice::get{ s = xs, i }` and `list::push{ list = &xs, heap, item }`
    everywhere; `xs.get{ i }` would shrink code a lot. *Partly:* slices are built in (spec §12), so
    `slice::get{ s = xs, i }` is now `xs[i]`; `list::` and `map::` calls remain.
11. **Float-to-float `@as` reads as fallible.** It never panics, but looks like it might. A
    separate conversion, or saying so in §13.
12. ~~**No const string or byte tables** in namespaces without a local (keywords, names). Ties to 1.~~
    *Done:* a const may hold literal views, e.g. `const KEYWORDS: [2][]u8 = ["fn", "let"]` (spec §14).
13. ~~**No must-use results.** Dropping the `bool` from `list::push` is silent.~~ *Done:* every
    result must be used or dropped with `_ = e` (spec §11.6).
14. **ctxi call overhead** (implementation, not language): `slice::get`/`at` made about a million
    calls in one profile. Inlining trivial std accessors in ctxi would speed development.
    *Partly:* slice indexing is built in now, so those calls are gone.
