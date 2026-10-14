# Decisions

One line per decision, newest last. The samples are the spec; this file records *why*.

- `todo.tbl`: general purpose (tables, projections, contexts)
- `game.tbl`: ECS (keyed tables, joins, systems)
- `todo_ui.tbl`: declarative GUI (views, state, events)

## Settled

- Declarations start with a keyword (`table`, `projection`, `context`, `fn`, `let`), so the parser always knows what it is reading from the first token.
- Statements end with `;`. A missing `;` gives a precise error and avoids newline-sensitivity rules.
- Types appear only after `:` or `->`, so `<` in `Table<Todo>` never has to be told apart from less-than.

## Open

1. **Projections:** must a projection come `from` a table, or are free-standing ones (like `Stats`) fine too?
2. **Contexts:** pass them explicitly (`app: App`), or have functions declare them (`fn add(text: str) uses App`) so they are in scope?
3. **Queries:** is `from … where … select …` built into the language, or are they method chains (`app.todos.where(…)`)?
4. **Struct literals:** `Todo { … }` is ambiguous after `if x {` and `for x in y {`. The new samples make this worse, with `for p in world.velocities {` and trailing-block elements like `row(gap: 4) {`. Choose between `Todo.{ … }`, `new Todo { … }`, or banning literals in conditions (as Rust does).
5. **Row identity:** are implicit `id` and `Id<T>` the right defaults?
6. **`required`:** does it mean "no default, must be set on insert"? If so, should fields without a default be required anyway?

### From ECS (`game.tbl`)

7. **Keyed tables:** `id Entity;` plus `table Position key Entity` lets rows in different tables share an identity. Is `table Todo` then shorthand for `table Todo key Id<Todo>`?
8. **Joins:** several bindings in one `for` join on the shared key, and `_ in world.players` filters by a tag. Do we also need `without` (entities *lacking* a component)?
9. **Rows, references or copies:** the ECS loops write through loop variables (`p.x += …`), but `todo.tbl` uses `update(id, { … })`. Keep one way or both?
10. **Changes during iteration:** `despawn` inside a loop is deferred until the loop ends. Should that be the rule, an error, or something to make explicit?
11. **Scheduling:** should systems declare what they read and write (for example `uses World.positions mut`) so they can run in parallel? This connects to #2.

### From GUI (`todo_ui.tbl`)

12. **Reactivity:** for views to re-run, the runtime must track which tables and rows a view read. Should tracking be per row or per table, and should it be automatic or declared?
13. **View state:** keep `state` local to a view, or store UI state in tables and contexts as well ("everything is a table")?
14. **Binding:** use `text_input(bind draft)` as shorthand for `value: draft, on_change: fn(s) { draft = s; }`?
15. **Row to projection:** can a `Todo` row be passed where a `TodoLine` is expected, without being converted explicitly?
16. **Trailing blocks:** are `row(…) { children }` calls allowed only inside `view`, or everywhere?
17. **Closures and modules:** `fn(b: bool) { … }` and `use todo { … }` are placeholders, used here without discussion.
