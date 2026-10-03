# Language friction: scripting (`lib/script`, `tools/ncsdis`, `tools/ncsrun`)

Where ctxlang got in the way while writing the NCS decoder, the VM, the stub engine and their
tools (about 3,700 lines, not counting the generated tables). Each entry: what I wanted to
write, what I wrote instead, how often.

- **A function returning `!T` can't be a function value** (spec §8, Errors, rule 12; a bind of
  one neither). The engine interface wanted to be `&fn{ mut vm: Vm, call: Call } -> !` so a
  routine handler could `try` its pops and fail; it is `-> Reply` (a union of `done`, `failed`,
  `equal{ same }`) instead, and every engine needs a wrapper that turns its handlers' errors into
  `Reply::failed` (nwstub::call, and the engine's own later). The same rule rules out a table of
  772 handler functions that use `try`: dispatch has to be a chain of direct calls (docs/design/
  script.md, "Dispatch"). A function value whose `!T` holds any error, accepting functions whose
  inferred set is a subset, would do.
- **`&fn` can't be a struct field** (spec §6). The engine bind travels as its own context field
  through `run`, `resume`, `exec`, `compare` and every tool function; ncsrun wanted a `Runner {
  opts, engine }` to pass as one (the compiler said "`&fn` can only be the type of a local or a
  read-only context field"), and passes both separately to six functions.
- **Bind records are never freed** (PLAN.md: "a bind record from `ctx_alloc`; never freed"). An
  engine bound to its state for each script run would leak a record per run, so the bind is made
  once and passed down; the stub's ExecuteScript still binds itself once per call. Documented in
  the design for the engine to follow.
- **A bind and a `&` of what it holds can't meet in one call** (§3.1). ncsrun's helpers take the
  engine (`nwstub::call{ &stub, _ }`) and need the stub too (to clear it, take its actions): they
  take `stub: *mut nwstub::Stub`, a raw pointer the checker doesn't track, made once with
  `let stub_at = &stub`. 7 functions. Sound here, but it is the checker being worked around.
- **No bit casts.** Floats travel as their bits in cells, in CONSTF operands and in saved
  situations. Wrote `ncs::f32_of_bits`, `bits_of_f32`, `i32_of_bits`, `bits_of_i32`, each
  `let mut v = x; return @cast(*T, &v).*`, and an `extern union Cell { i: i32, f: f32, u: u32 }`
  for the stack. 4 helpers, used about 15 times. An `@bitcast(T, x)` for same-size numbers would
  do.
- **Checked arithmetic and conversions in the interpreter loop.** Every `+`, `-` and `@as` is a
  checked operation; the first VM (offsets as signed cells, `@as(i64, sp) + @as(i64, off)`) ran
  184 million instructions a second. Re-encoding offsets as unsigned distances below SP and writing
  `@wrap_add`/`@wrap_sub` for every index after its explicit bounds check (75 places in
  `exec`) brought it to about 450 million. The checks were all ones the code had just made
  impossible; nothing tells the compiler so. An unchecked block or `@assume` would keep the source
  readable.
- **`match` takes no integers, and `@as(E, n)` is a compare chain** (ctxlang FRICTION #17). The
  opcode byte can't be matched, so the loader turns (opcode, type byte) into an `Op` enum once,
  with an `if` chain (`nwvm::lower`, 70 arms), and validity is another chain (`ncs::allowed`). The
  interpreter's `match` on `Op` lowers to an `if`/`else` chain in C too; gcc -O2 turns it into a
  jump table, which the speed depends on.
- **`@fmt` writers are by exact type.** nwvm's fault text goes into its own sink (`nwvm::Text`,
  a fixed buffer), which needed writers for `[]u8`, `strlit`, `i64`, `i32`, `u32` and a `Hex`
  wrapper; a `u16` hole was "no writer of u16 to nwvm::Text" until `@as(u32, ...)`. The
  disassembler (a sub-agent's notes): no width, padding or hex in `@fmt`, so `{:<16}`, `{:08x}`,
  `{:+d}` and `ljust` are done by hand in about 15 places; no `[]u8` writer for `utf8::Builder`;
  every tool copies the same writers over `Io` (ncsdis, ncsrun).
- **`is` can't test a `!T`.** "Did the run succeed" is `match ran { ok => { true } err => {
  false } }`: 3 times.
- **Punning names the field, not the role** (ctxlang FRICTION #12). `fs::read_all{ &fs, &work,
  ... }` passes field `work`; it must be `heap = &work`: 8 times in ncsrun.
- **A condition can't break after a call's `}`** (spec §11.2). A four-way `or` of
  `slice::eq_bytes{ ... }` calls had to break after `or`, not before it. Once.
- **`build::add_sources` takes whole directories.** A tool that needs only `ncs.ctx` and
  `routines.ctx` (the disassembler) builds all of `lib/script`, so a half-written `nwvm.ctx` there
  broke its build while both were being written in parallel. Once, briefly.
