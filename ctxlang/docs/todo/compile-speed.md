# Compile and check speed: what is left

Profiled 2026-11-25 on Windows (MinGW gcc, 32 processors), with a sampler that suspends ctxc's
thread every millisecond and walks its frame pointers (ctxc built with
`-fno-omit-frame-pointer`; gprof records nothing on MinGW x64). `ctxc check` of KOTOR (140K
lines and std) takes 0.99 s, and of ctxc 0.81 s, from 14.8 s and 2.8 s before the work from
e0732e58 to a1acbae2, whose commits say what each did. What an item costs is from the profile
then.

- [ ] **1. The other side tables, as `nodes::Table`s.** `uses` (iterated with `map::next` for
  `ctxc api` and `where`, so it needs a way to walk it), `literal`, `spreads`, `narrowed`,
  `braces`, `forwards`, `is_vars`, `filled`, `holds`; and the maps keyed by a declaration's
  index (`borrows`, `borrow_low`, `borrow_index`, `foldable`, `values`, ...) as arrays by
  index. Maps were about 16% of the time spent in functions themselves.
- [ ] **2. The lexer's keywords** are found with `slice::eq_bytes` (about 2%).
- [ ] **3. Memory.** A check of KOTOR peaks at 850 to 900 MB, a build at 1.2 GB, with about
  220K page faults. The largest: the parser's lists of `Stmt` by value (93 MB), name paths'
  `Seg`s (73 MB), `add_branch`'s states (68 MB), the lexer's tokens (59 MB), and 130 MB of
  blocks an arena list or map left behind when it grew.
- [ ] **4. An edit recompiles units that only copy a function of the file.** A comment line at
  the top of KOTOR's lib/engine/fight.ctx recompiled 28 of 117 units (3.7 s, against 2.2 s with
  nothing to compile): 3 hold fight's functions, 25 hold copies of its small ones (emit_c.ctx,
  `share`), whose `CTX_AT` and panic positions are absolute lines. Positions relative to the
  fn's first line, with the line in a `ctx_where` that a copy declares `extern` from its own
  unit, would leave the copies' C unchanged.
- [ ] **5. `ctxc exe -o` links every time**, though nothing changed (7% of a build with every
  unit cached): copy the cached executable instead.
- [ ] **6. The build program is compiled on every check.** A check of KOTOR checks build.ctx
  with std and ctxc's lexer and parser first, about 5%. Its graph could be kept, keyed by a hash
  of the build program's files.

## Not worth doing

- ctxc at `-O2`: 2 to 3%; `-O2` without call paths 6 to 8%.
- A mask for `std/map`'s probes and its home slot, in place of `%` and a division: 1 to 2%. What
  maps cost is cache misses in tables of millions of slots.

## To look at

- The recovery test (`tools/recover.py --sample 25`, 2026-11-25) fails 6 of 117,738 damaged
  copies, all inside `check::new`'s `Checker{ ... }` literal (check.ctx, about lines 570 to
  585): deleting or duplicating a token there makes the parser report more errors than its
  cap. It did before the side tables became arrays too (the same literal, at 46a1474f), so it
  is the parser's recovery in a long struct literal. The test last ran at 87ab2738.
- `comptime` runs each const in a new `arena::new` over the same scratch memory
  (comptime.ctx, `scratch`), so what `eval` allocates there isn't zero, as an arena promises
  past `handed`, but the last run's bytes. Harmless only if `eval` never reads memory it hasn't
  written.
- A threaded program's stack check reads a thread's slot: within the noise on Windows (the
  TEB), and on Linux a `_Thread_local`; macOS's, which ctxc now pays, isn't measured.
