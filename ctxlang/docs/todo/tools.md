# Tools: what is left

- **`recover.py` in ctxlang.** The last Python: `tools/recover.py`, and the part of
  `tools/toolchain.py` that builds ctxc for it. It runs many processes at once, with
  `proc::spawn` and `wait`, as the driver's parallel compiles and the suite's runner do. Its
  corpus is the suite's cases: `ctxc run tools/suite -- --corpus OUT`.
- *If wanted:* benchmarks (`#bench`, timed through a clock capability the runner supplies) and
  fuzzing (`#fuzz` over a `[]u8` input), both built in as Go has them.
