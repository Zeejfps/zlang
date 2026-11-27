# Known gaps

- The front end is over its budget: checking and lowering ctxc takes about 215 ms natively,
  against 100 ms for the check alone. It hasn't been profiled.
- The interpreter's layer (std/os/interp) has no standard input, files or processes, and calls no
  C library but the math functions: the suite's programs that use those are checked by their
  expected outputs alone.
- Bind storage: a record that a loop's outer local holds (`prev = cur; cur = f{ x = i, _ }`, or a
  chain of binds) keeps its memory until the function returns. Last-use reclamation would need
  liveness across loop iterations.
- Borrowing summaries: local result values and pattern payloads may merge success/error
  provenance. A struct is one value to them, not its fields apart: a list over an arena that is
  a local holds the arena's address, so what is read out of it is derived from that local, and
  a store into its buffer goes where the arena points; ctxc's `declarations` keeps its lists on
  pages for that reason. Telling fields apart would need summaries by field path. The extra
  body check adds front-end work; a safety-only replay could replace it if profiling justifies
  it.
