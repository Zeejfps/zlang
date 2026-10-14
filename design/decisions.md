# Decisions

One line per decision, newest last. The samples are the spec; this file records *why*.

- `todo.tbl`: general purpose (tables, projections, contexts)
- `game.tbl`: ECS (keyed tables, joins, systems)
- `todo_ui.tbl`: declarative GUI (views, state, events)

## Settled

- Declarations start with a keyword (`table`, `projection`, `context`, `fn`, `let`), so the parser always knows what it is reading from the first token.
- Statements end with `;`. A missing `;` gives a precise error and avoids newline-sensitivity rules.
- Types appear only after `:` or `->`, so `<` in `Table<Todo>` never has to be told apart from less-than.
- Values are constructed with named-argument calls: `Stats(total: 1, open: 0)`, `App()`. There is no `Todo { … }` literal, so `{` after an expression always opens a block. Construction, function calls and GUI elements share one syntax, and a missing `required` field is reported as a missing argument. `insert` and `update` take columns as named arguments too: `update(id, done: true)`.
- A trailing block attaches only to a call that begins a statement (`row(gap: 4) { … }`). Inside an `if`/`for`/`while` header, `{` is always the body. The parser decides this from position alone and never needs types.
- `..p: T` in a parameter list takes T's fields as named parameters, and `p` is the assembled value in the body. `Table<T>.insert` is declared the same way, so this is a general feature, not a special case for tables. Rules:
  - Spread fields are passed by name only, so column order never becomes part of an API.
  - A field name that appears in two spreads is an error at the declaration.
  - `f(..value)` at a call site passes a whole value.
  - Calling with named fields requires a concrete T. Generic code passes whole values only, so errors never appear late, at instantiation.
  - There are no prefix ranges (`..5`), so a leading `..` always means spread.
  - There is no overloading.

## Open

1. **Projections:** must a projection come `from` a table, or are free-standing ones (like `Stats`) fine too?
2. **Contexts:** pass them explicitly (`app: App`), or have functions declare them (`fn add(text: str) uses App`) so they are in scope?
3. **Queries:** is `from … where … select …` built into the language, or are they method chains (`app.todos.where(…)`)?
5. **Row identity:** are implicit `id` and `Id<T>` the right defaults?
6. **`required`:** does it mean "no default, must be set on insert"? If so, should fields without a default be required anyway?

### From ECS (`game.tbl`)

7. **Keyed tables:** `id Entity;` plus `table Position key Entity` lets rows in different tables share an identity. Is `table Todo` then shorthand for `table Todo key Id<Todo>`?
8. **Joins:** several bindings in one `for` join on the shared key, and `_ in world.players` filters by a tag. Do we also need `without` (entities *lacking* a component)?
9. **Rows, references or copies:** the ECS loops write through loop variables (`p.x += …`), but `todo.tbl` uses `update(id, done: true)`. Keep one way or both?
10. **Changes during iteration:** `despawn` inside a loop is deferred until the loop ends. Should that be the rule, an error, or something to make explicit?
11. **Scheduling:** should systems declare what they read and write (for example `uses World.positions mut`) so they can run in parallel? This connects to #2.

### From GUI (`todo_ui.tbl`)

12. **Reactivity:** for views to re-run, the runtime must track which tables and rows a view read. Should tracking be per row or per table, and should it be automatic or declared?
13. **View state:** keep `state` local to a view, or store UI state in tables and contexts as well ("everything is a table")?
14. **Binding:** use `text_input(bind draft)` as shorthand for `value: draft, on_change: fn(s) { draft = s; }`?
15. **Row to projection:** can a `Todo` row be passed where a `TodoLine` is expected, without being converted explicitly?
16. **Trailing blocks:** the parsing rule is settled. Are they allowed only inside `view`, or everywhere (for example `with_lock(m) { … }`)? And can a projection like `Button` be an element directly?
17. **Closures and modules:** `fn(b: bool) { … }` and `use todo { … }` are placeholders, used here without discussion.

### From spreads

19. **Spread details:** (a) `update` needs every field optional, meaning "unchanged". Add a partial spread (`..changes: Partial<T>`), or keep `update` built-in? (b) Is `f(..p, y: 5.0)` allowed, with the explicit field overriding (as in Rust's struct update syntax), or is it a duplicate-field error?
