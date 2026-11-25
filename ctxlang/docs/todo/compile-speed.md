# Compile and check speed: what is left

Profiled 2026-11-25 on Windows (MinGW gcc, 32 processors), with a sampler that suspends ctxc's
thread every millisecond and walks its frame pointers (ctxc built with
`-fno-omit-frame-pointer`; gprof records nothing on MinGW x64). Baseline: `ctxc check` of KOTOR
(140K lines and std) took 14.8 s, and of ctxc 2.8 s. Each item gives what was measured on a
prototype, or what the profile says it costs now. Prototypes 1 to 3 wrote byte-identical C for
ctxc.

## Measured

- [x] **1. `handles_own` is a scan of every declaration.** It copies each `Decl` (about 300
  bytes) to test `task_handle`, and runs for every call with type arguments (`braced_as`), for
  every local holding a handle (`handle_local`), and once per declaration in `task_decls`, which
  makes that quadratic. 80% of KOTOR's check, 56% of ctxc's. Keep the namespaces that declare a
  `#task_handle` struct, filled in `handle_attr`. KOTOR 14.8 s to 1.87 s, ctxc 2.8 s to 1.16 s.
- [ ] **2. Windows' `os::commit` asks `VirtualQuery` at every MiB an arena reaches.** `analyze`
  reserves `64 MiB + 512 × the source's bytes`, several GB for KOTOR, and the query's cost grows
  with what is reserved after the address: 10% of KOTOR's check, 8% of ctxc's. Commit to the
  end of the MiB at once (`VirtualAlloc` with `MEM_COMMIT` succeeds on committed pages), and ask
  only if that fails. KOTOR 1.88 s to 1.69 s, ctxc 1.16 s to 1.07 s.
- [ ] **3. Side tables keyed by `key{ file, id }` as arrays.** Node ids are 0 to `ids - 1` in
  each file (`syntax::File.ids`), so a table is a slot per node, at the file's base plus the id,
  with a map for any other key. Done for `expr_ty`, `refs`, `type_of`, `access`, `convs`,
  `decl_of` and `local_of`: KOTOR 1.70 s to 1.42 s, ctxc 1.10 s to 0.99 s.

## From the profile

After 1 to 3, KOTOR's check is about 1.4 s: the first body pass about 28%, borrow inference 16%,
the second body pass 22%, lexing and parsing 15%, maps still 16% of the time in functions
themselves.

- [ ] **4. Bodies are checked twice.** `check::program` runs `Phase::bodies` over every fn again
  after `infer_borrows`, so that eight `borrow_ready` places (`escape_error`, `derives` through
  `direct_borrow`, `check_order`, `check_keeps`, the `fn_values`) see the summaries. The second
  pass is about 22% of KOTOR's check. Checking escapes as a walk of the checked tree of its own,
  over the side tables, as `borrow_fn` walks it, would replace it.
- [ ] **5. Lexing and parsing, one file at a time.** About 15% of the check, and the files are
  independent: in parallel, on tasks (threads.md), with an arena each. The lexer's keywords are
  found with `slice::eq_bytes` (about 2%).
- [ ] **6. The other side tables.** `uses` (iterated with `map::next` for `ctxc api` and
  `where`, so it needs a way to walk it), `literal`, `spreads`, `narrowed`, `braces`,
  `forwards`, `is_vars`, `filled`, `holds`; and the maps keyed by a declaration's index
  (`borrows`, `borrow_low`, `borrow_index`, `foldable`, `values`, ...) as arrays by index.
- [ ] **7. Memory.** A check of KOTOR peaks at 850 to 900 MB, a build at 1.2 GB, with about
  220K page faults. The largest: the parser's lists of `Stmt` by value (93 MB), name paths'
  `Seg`s (73 MB), `add_branch`'s states (68 MB), the lexer's tokens (59 MB), and 130 MB of
  blocks an arena list or map left behind when it grew.
- [ ] **8. An edit recompiles units that only copy a function of the file.** A comment line at
  the top of KOTOR's lib/engine/fight.ctx recompiled 28 of 117 units (3.7 s, against 2.2 s with
  nothing to compile): 3 hold fight's functions, 25 hold copies of its small ones (emit_c.ctx,
  `share`), whose `CTX_AT` and panic positions are absolute lines. Positions relative to the
  fn's first line, with the line in a `ctx_where` that a copy declares `extern` from its own
  unit, would leave the copies' C unchanged.
- [ ] **9. `ctxc exe -o` links every time**, though nothing changed (7% of a build with every
  unit cached): copy the cached executable instead.
- [ ] **10. The build program is compiled on every check.** A check of KOTOR checks build.ctx
  with std and ctxc's lexer and parser first, about 5%. Its graph could be kept, keyed by a hash
  of the build program's files.

## Not worth doing

- ctxc at `-O2`: 2 to 3%; `-O2` without call paths 6 to 8%.
- A mask for `std/map`'s probes and its home slot, in place of `%` and a division: 1 to 2%. What
  maps cost is cache misses in tables of millions of slots.

## To look at

- `comptime` runs each const in a new `arena::new` over the same scratch memory
  (comptime.ctx, `scratch`), so what `eval` allocates there isn't zero, as an arena promises
  past `handed`, but the last run's bytes. Harmless only if `eval` never reads memory it hasn't
  written.
