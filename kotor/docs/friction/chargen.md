# Language friction: character generation (`lib/chargen`, `tools/chargentest`)

Where ctxlang got in the way. Each entry: what we wanted, what we wrote instead, how often.

- **`let mut x: T` zero-initialises only when every field has a zero value, and a pointer never
  does.** `chargen::State` holds `*mut heap::Heap`, `*mut rules::Tables` and the like next to a few
  dozen counters and arrays; `let mut s: State` then fails ("may be read before it is assigned") and
  the only way in is a struct literal naming all forty fields, with `[0; N]` for each array. Wrote
  the literal once in `begin`; adding a field to `State` means editing it. Once per big state struct
  (the front end's `Front` has the same shape).
- **A positional `&x.y` is not a call argument.** `random_name{ &fs, ..., &st.rng, into = buf[..] }`
  fails to parse ("expected `}`, found `.`"): the bare `&name` form takes an identifier only. Wrote
  `rng = &st.rng`. Four times (any `mut` field fed from a field of a pointer).
- **A `mut` field fed from a pointer takes the pointer itself, but one fed from a pointer's pointee
  needs `&p.*`.** `gui3d::load{ models, mats = g.cache }` works when `models` is a `*mut Cache`;
  `rules::load_tables{ heap = &heap.* }` is needed when the field is `mut heap: Heap` and what is in
  hand is `*mut Heap`. Both are logical; the second only turned up by trying `&heap`, `heap` and
  `&heap.*` in turn. A line in the quick reference ("`&p.*` passes the pointee of a pointer") would
  have saved the three tries.
