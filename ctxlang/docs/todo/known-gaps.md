# Known gaps

- The front end is over its budget: checking and lowering ctxc takes about 215 ms natively,
  against 100 ms for the check alone. It hasn't been profiled.
- On Linux and macOS, `mem::pages` clears its memory with memset (std/os/posix), touching every
  page up front; calloc, as `mem::reserve` uses, would leave that to the OS. Untested there, so
  left for a machine that can run it.
- The interpreter's layer (std/os/interp) has no standard input, files or processes, and calls no
  C library but the math functions: the suite's programs that use those are checked by their
  expected outputs alone.
- Bind storage: a record that a loop's outer local holds (`prev = cur; cur = f{ x = i, _ }`, or a
  chain of binds) keeps its memory until the function returns. Last-use reclamation would need
  liveness across loop iterations.
- Borrowing summaries: an indirect hash/equality callback may conservatively retain a map key as
  a possible store origin. Written function types have no borrowing contracts. Local result
  values and pattern payloads may merge success/error provenance. The extra body check adds
  front-end work; a safety-only replay could replace it if profiling justifies it.
