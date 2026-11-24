# ctxc internals

`ctxc` is a self-hosting compiler written in ctxlang that emits C. A fresh checkout builds it from
its platform's bootstrap, `bootstrap/ctxc.linux.c`, `ctxc.macos.c` or `ctxc.windows.c`, with
nothing but a C compiler.

This file is the reference: how to work on ctxc, how ctxlang maps to C, how it is tested, and the
design decisions behind them. What is left to do is in [todo.md](todo.md). The old plan, with the
history of finished stages, is `PLAN.md` in git history (its last version is at the commit that
removed it; the stages 0–12 version is at `f53a93f`). ctxi, the Python interpreter ctxc replaced,
is at `8436f4d`.

## Working on ctxc

```
cc -std=gnu11 -O1 -w -fwrapv -fno-optimize-sibling-calls -Ictxc/rt bootstrap/ctxc.linux.c ctxc/rt/ctxrt.c ctxc/rt/ctxfloat.c ctxc/rt/ctxthread.c -lm -lpthread -o ctxc0
./ctxc0 run examples/wordcount.ctx -- spec.md            # a file
./ctxc0 run examples/json -- examples/json/sample.json   # a directory
./ctxc0 run examples/glfw                                # a directory with a build program
./ctxc0 exe examples/list.ctx -o list
./ctxc0 interp examples/list.ctx                         # main in the interpreter, no C compiler
```

- On macOS the bootstrap is `bootstrap/ctxc.macos.c`, and on Windows `bootstrap/ctxc.windows.c`. ctxc finds std/ and ctxc/rt/ through
  CTX_HOME, or above its executable or the working directory, and builds in HOME/build/run, in a
  directory for each program. A big program's C is several units, compiled at once, and a unit
  whose C, runtime, compiler and flags haven't changed isn't compiled again: `ctxc run` of an
  unchanged small program takes about 40 ms, the front end included (drive.ctx). `ctxc build`
  writes one file, as the bootstraps are.
- ctxc0 is the bootstrap's. `./ctxc0 exe ctxc -o ctxc1` builds the current source's with it
  (about 3 s), for `./ctxc1 run`. The suite's runner builds its own for the cases, into
  `build/suite/ctxc` (cached after the first time).
- `ctxc0 run tools/suite` runs every case through ctxc for the current source
  ([tests/README.md](tests/README.md)).
- Python is left in `tools/recover.py` alone, with the part of `tools/toolchain.py` that builds
  ctxc for it. Moving it to ctxlang is in [todo.md](todo.md).
- Friction found while writing ctxc, and the KOTOR port, is logged in [FRICTION.md](FRICTION.md).

### Changing the language

ctxc's source may use only what the bootstrap's ctxc understands. A new feature lands in two
steps:

1. Add it to ctxc, without ctxc using it. The bootstrap compiles that source, and the result
   understands the feature.
2. Run `./ctxc0 run tools/fixpoint.ctx -- --update` to refresh the bootstraps
   (`bootstrap/ctxc.*.c`, one per platform layer, all written from any machine). ctxc's source
   may now use it.

Removing a feature goes the other way round: stop using it, refresh the bootstraps, then remove
it. Refresh them whenever a change to ctxc lands, so a fresh checkout builds the current compiler
in one step; the fixpoint says when one is out of date.

## How ctxlang maps to C

C11 with GNU extensions (overflow builtins, empty structs, statement expressions), built with gcc
(MinGW on Windows), Apple clang on macOS, or `zig cc` (`CTX_CC=zig`). Flags: `-std=gnu11 -O1 -w
-fwrapv -fno-optimize-sibling-calls -fno-strict-aliasing`, with another `-O` level where a build
program asks for one (spec §19).

| ctxlang | C | Notes |
|---|---|---|
| `i8`…`u64`, `bool` | `int8_t`…`uint64_t`, `_Bool` | `usize` is fixed at 64 bits for now. |
| `+ - *` on integers | `__builtin_*_overflow` | Panics with `integer overflow`. |
| `/ %` on integers | guarded C `/ %` | Zero divisor panics. `MIN / -1` panics. `MIN % -1` is 0. Both round toward zero. |
| `f32` arithmetic | `float` | Needs `FLT_EVAL_METHOD == 0` (SSE). |
| `@as`, `@trunc`, `+%` `-%` `*%` | range check then cast; unsigned arithmetic then cast | Float-to-integer `@as` checks are inline in ctxrt.h; only a failed conversion calls the runtime for its diagnostic. |
| `[N]T` | `struct { T a[N]; }` | Wrapped so arrays copy, assign and return as values. |
| `[]T`, `s[i]`, `s[lo..hi]` | `struct { T *m_ptr; uint64_t m_len; }`; `ctx_idx`, `ctx_range` | Bounds checks panic. The runtime's C functions see it as `ctx_slice`. |
| `strlit` | its bytes' `[]u8` | A literal's view points to a C string literal, whose NUL is the hidden zero. |
| struct | C struct, same field order | Checked with `_Static_assert` on `sizeof` and `offsetof`. |
| union, `?T` | `struct { uint32_t tag; union { … } p; }` | Tag at 0, payload at `align_up(4, payload align)`. `null` is tag 0. |
| `?*T`, `?*mut T` | `T*` | `null` is 0. IR type `nptr`. |
| `c::String`, `?c::String` | `struct { uint8_t *m_ptr; }`, and the same under a typedef | Passed to C by value, which 64-bit C ABIs pass and return as the pointer; a literal's is `((uint8_t *)"...")`, whose NUL is the hidden zero. `?c::String` is null when `m_ptr` is 0. |
| `extern union` | C `union` | Every field at offset 0. IR `(cunion ...)`. A literal zeroes the other bytes with `memset`. |
| `extern fn{C} -> R`, and its `?` | `R (*)(P...)`, capabilities dropped | IR type `cfn`, params in order; `null` is 0. A named extern fn as a value is `xN`; a `#c::callback` fn is `kK`, a C function calling `fN`. |
| enum | its base integer type | `match` becomes an if-else chain on the value (IR `switch`), as a `match` on an integer does: a case lists values and ranges, `lo <= v && v <= hi`. |
| `Io`, `Fs`, `Mem` | empty struct | Size 0 with GNU C. |
| `capability Gl { f: extern fn{C} -> R, ... }` | struct of function pointers | `x.f{ ... }` calls the pointer; dropped from extern and `cfn` params, as other capabilities are. |
| `*T`, `q + n`, `(q + i).*` | `T*`, pointer arithmetic | Not checked. §12.7 calls a bad pointer UB. |
| `a[i]` on arrays | index with a bounds check | Panics, as the spec requires. |
| `fn{C} -> R` | pointer to a record whose first member is the code | Called with the record and the fields in name order. Conversion to a type with more fields wraps the value in an adapter. Conversion to one whose `!T` may fail with any error, or that has `mut` a field the value takes read-only (spec §5), is a widening thunk that lowering writes as a function (lower.ctx, `widen_fn`), which reads such a field through its pointer: a named function's is its static record, a bind's binds the thunk instead, and any other value is held by a bind of a thunk calling it. |
| read-only param of a struct, union or array over 32 bytes | `T *`, used as `(*lN)` | Spec §14.6: the caller passes its place, or a copy where another argument or the callee could change it (emit_c.ctx, `pass`). Not to extern fns. A 300 KB struct passed 20,000 times: 0.89 s to 0.06 s; `ctxc build` of ctxc, 451 ms to 317 ms. |
| `&fn{C} -> R` | a record in a frame slot, or borrowed from the runtime's record stack | emit_c.ctx, Records. A slot when no earlier record of the bind can still be called when it runs again: no loop around it, or it is only passed to a call or called, or only held by a confined local (one `let`, only called or passed). Otherwise `ctx_rec_alloc`, released when the function returns (`CTX_RECORDS`, after defers, including early `try` returns). An adapter of a `&fn` goes where a bind's record would; one of a `fn` is static for a named function and otherwise one per pair (`ctx_adapt`), as are widening thunks of `fn` values. A bind of nothing has a static record. A loop of 20M binds passed to a call: 1.5 GB and 2.0 s before, 6 MB and 0.19 s after. |
| `defer` | copied to each exit | Innermost first. `return e` evaluates `e` into a temporary first. |
| const of array, struct or union type | `static const qvN = VALUE;` | The checker folds the value to literals; `[x; N]` is a GNU range designator. A scalar const is its value at each use. Const array slices borrow this static storage read-only, without copying; each C unit may have its own copy. |
| `if`/`match` expressions | GNU statement expressions | A branch that leaves uses `return`, `break` or `continue`. |
| argument order | temporaries | C leaves argument evaluation order unspecified; ctxlang evaluates left to right. |
| `@panic`, runtime panics | `ctx_panic(line, col, &w_NAME, CTX_UPV, msg)`, and `ctx_panic_index` and the rest for the checks | The runtime finds the file and calls the `#panic` fn (`ctx_on_panic`, which C's main gives it), once, with the stack check off; std's writes `file:line:col: panic: msg`, then the call path, and exits with 134. `w_NAME` is the function's `ctx_where`, static, before it: its name, its file and how a path shows it. The file is FNV-1a of its name with the top bit set, which the runtime finds in main's file table, so a unit's C doesn't depend on the program's other files. |
| call paths (spec §15) | `CTX_UP` first in every function's parameters, and in a function value's code's; `CTX_FRAME(&w_NAME);` in a function that calls; `(CTX_AT(LINE, COL), f_NAME(CTX_ME args))` | ctxrt.h, call paths. A frame is its caller's frame, the function's `ctx_where` and the position of its last call, line and column in one 32-bit store (20 and 12 bits; a call past them stores 0, "not known"). A call's arguments go into temporaries first if one of them may call, so that the position noted is the one in force during the call. A function that calls nothing has no frame; a panic passes its own `ctx_where` and its caller's frame (`CTX_UPV`), so a frame is used only by the functions it is passed to, and one whose callees C inlines away is dead stores that C removes. Nothing is linked through a global and nothing is undone on return. The frame that last called C is noted for the thread (`CTX_OUT`, in an extern fn's `eN` and before a call of a C function pointer), where a callback's C function takes it up (`CTX_C_FRAME`) and a native's panic finds its path. With `-DCTX_NO_PATH` (an executable without call paths, `build::trace_calls`) every one of these macros is empty: no parameter, no frame, and the C is otherwise the same. An earlier form linked the frames through a per-thread global, pushed on entry and popped on return: 15% on the script VM, and two stores for a call's position instead of one cost 13% more than one. Now, against the C before call paths: ctxc checking its own source, 2.18 s to 2.26 s (4%); ncsrun's VM at `-O2` (`--repeat 20`), 2.50 s to 2.59 s (4%), and 2.34 s without paths; binkcheck's decode at `-O2`, 25.7 s to 27.8 s (8%), and 26.2 s without paths; sndcheck's MP3 decode the same within its noise (65 to 68 s either way). Executables are 9% (mixtest, 543 KB to 592 KB) to 33% (ctxc, 2.57 MB to 3.41 MB) larger with paths, and 3% to 5% without them, the functions' names, which a build without paths has too. |
| `fn main`, `#start`, `#panic` | IR functions that lowering writes (lower.ctx, `entry_fns`): `<entry>` calls the start fn with its capabilities, the `argc` and `argv` it takes and `<main value>`, a function value that calls main; without a start fn, main itself. `<on panic>` zeroes the stack limit and calls the panic fn. A capability from nothing is IR `capref`, `(void *)cap` in C. | C's `main` only calls `ctx_start` and `<entry>`, and `ctx_on_panic` `<on panic>`, with C's values by name (emit_c.ctx, `entry`); the interpreter calls the same functions (eval.ctx, `main`). |
| fn | `f_NAME`, after its qualified name | Global across units, `static` in a program of one; a name that isn't an identifier, or a long one, is cut and gets a hash. Types, consts and the rest are numbered within each unit (emit_c.ctx, "Units"). |
| capability static (`static name: T`) | `s_` and its qualified name, a zeroed C global | emit_c.ctx: `static` in a program of one unit; with several, main's unit defines every one and the others declare those they use `extern`. A use is `(*(&s_NAME))`: IR `(deref (saddr N))`, so it is a place through a pointer, as the checker treats it (`Access::stat`). A `#thread_local` one is `_Thread_local` too, in a threaded program only (spec §15, Entry point, rule 8; IR `(threaded)`, whose C defines `CTX_THREADS`). |
| `@atomic_load` and the rest, `@fence` | GCC's `__atomic_*_n`, `__atomic_fetch_add` and `_sub`, `__atomic_thread_fence` | IR `(atomic T OP ORDER [ARGS])`; operands in temporaries, in order. A compare and exchange gives the value found, and lowering makes it `null` or `some` (lower.ctx, `atomic`). |
| a start's `run` (spec §15, Tasks) | a bind's record with its size and its task fn's name after the code, `ctx_task_rec` | IR `(tbind ...)` (lower.ctx, `task_record`); `@record_size` reads the size, `@record_copy` copies the record (`ctx_rec_copy`) and gives an entry thunk per result type (lower.ctx, `entering`), and `rt::task_name` names the task for a panic's report. |
| stack overflow | check in each function prologue | `CTX_STACK_CHECK()`, before the function's frame of the call path, so that the panic's path is its caller's, without a `#stack_limit` static none: compares the frame address to the `#stack_limit` static, whose storage is the runtime's (`CTX_STACK_LIMIT`: a global, or in a threaded program the calling thread's TLS slot), which std's start sets (16 MB below its frame, or `CTX_STACK`) and `ctx_on_panic` sets to 0 before the panic fn runs; 0 checks nothing. Linked with a 256 MB stack on Windows and macOS; on Linux, std raises `RLIMIT_STACK` to 256 MB and runs itself again (std/os/linux). No sibling calls, so every call takes a frame. |

## Testing

- **The suite.** `ctxc run tools/suite` runs every case under `tests/cases` through ctxc for the
  current source and cc, and checks all it states: output, exit code, panic, every error
  ([tests/README.md](tests/README.md)).
- **`#test` fns** (spec §20). `ctxc test std/tests` runs std's own, which are a program beside
  std, and `ctxc test DIR` any program's; the suite's `TestFns` cases check the runner's lines.
- **The interpreter.** The suite also runs each program with `ctxc interp` and requires the same
  stdout, stderr and exit code (a trap is 132 for both). One that calls an extern fn the
  interpreter doesn't emulate, does what std/os/interp can't, or recurses too deep, says
  `//# interp: cannot run`, and the interpreter must then refuse it; the summary counts the
  programs that were the same, refused and left out, and `-v` the refusals by reason.
- **Errors.** A case states every error ctxc reports, with its position and whole message, so
  message text is part of the interface, and so is how many errors a mistake gives.
- **Fixpoint** (`tools/fixpoint.ctx`, `ctxc run tools/fixpoint.ctx`). ctxc built by itself must
  write the same C twice, and the bootstraps must be current.
- **Corpus.** `ctxc run tools/suite -- --corpus build/corpus` writes every program of the cases,
  and `examples/`, each once, for the recovery test, which adds `std/` and `ctxc/` itself.
- **C's undefined behaviour.** `invalid memory access` is undefined behaviour in C, not a panic.
- **Recovery** (`tools/recover.py`). Damage every file in the corpus: cut it at each token
  boundary, and delete or duplicate single tokens. Run the front end on every result, inside
  ctxc (`ctxc recover`), in parallel chunks. The parser must not panic, must keep under the
  diagnostic cap, and must build a well-formed tree: ids used once, and every span inside its
  parent's. A cut inside a declaration that ends in `}` must report an error, and a cut must
  still produce symbols for the declarations before it. Other damage can leave valid code, so it
  needn't report anything. Then each copy is checked in its program (the corpus case's files,
  std, or ctxc), and the checker must not panic; it has no cap of its own, since a cut can
  remove declarations the rest of the program uses, and each use is an error. ctxc's files are
  checked at every 50th copy: each check takes as long as checking ctxc. std's 131K copies take
  about 4 minutes on 24 processors, and ctxc's 951K about 54. This is the test that guards
  editor use.
- **Editor queries** (the language server, [todo.md](todo.md); not built yet). Fixture files mark positions (`/*^def*/`, `/*^hover*/`) and state
  the expected answer, which covers the semantic model without a client.
- **Float text.** `f64_digits` must copy Python's `repr` exactly: shortest round-trip digits,
  exponent form below `1e-4` and from `1e16`, and a `.0` suffix; `f32_digits` is the same over
  an f32's own digits (spec §13, Formatting, rule 9).


## Decisions made

- **Panic call paths** (spec §15, Call paths; How ctxlang maps to C, call paths): frames the
  compiler keeps, passed from caller to callee, on at optimization levels 0 and 1 and in every
  test build, off at 2 and 3 unless `build::trace_calls` says so; every build names the function
  a panic is in. Walking the native stack was the other way: it costs nothing until a panic, but
  a return address names a ctxlang line only through the C compiler's debug information, which
  isn't in the executable on macOS, is in two formats on Windows (DWARF from MinGW, CodeView from
  `zig cc`), and has no frame for a function the C compiler inlined; and a table of return
  addresses can't be written in C. The frames are exact, the same from the interpreter, and need
  nothing at run time. What they cost decided when they are on: 4% on ctxc at `-O1`, and at
  `-O2` 4% on KOTOR's script VM and 8% on its Bink decoder.
- **Bind storage** (How ctxlang maps to C, `&fn`): frame slots where an earlier record can't
  still be called, a stack of records released on return otherwise, and static or one-per-pair
  records for `fn` values. The interpreter keeps its own representation, a fresh record for each
  bind, so the tests compare the C against it.
- **Several C units, with small functions copied.** A big program's C is units of about 256 KiB,
  grouped by the files that declare their functions, compiled in parallel and cached by hash
  (emit_c.ctx, "Units"; drive.ctx): 99K lines took 63 s at -O1 as one file and 8.4 s as 61 units
  on 24 processors. C inlines only within a unit, so a function no other unit names is static,
  and one of fewer than 32 statements and expressions that another unit calls is copied into it,
  static (emit_c.ctx, `share`): ctxc runs within 1.5% of one file, for 16 to 46% more C. A limit
  of 48 gained nothing; gcc's `-flto` was as fast at run time but made every link of KOTOR take
  54 s, and `-flto=auto` runs its jobs one after another on Windows.
- **Direct borrowing summaries.** A checked-AST pass infers whole-parameter success/error
  origins plus pointer-store effects, then bodies are checked again for escapes. Recursion and
  indirect calls are conservative; effects carry stored types through generic substitution so
  byte-copy helpers stay precise. Outputs conservatively include possible stored origins; this
  does not model memory aliases or allocation lifetimes.
- **Not planned: generating declarations inside the running compile** (Zig's `inline for` over
  fields with types as values, or Jai's `#insert`). It needs lazy analysis or a fixed-point loop
  in the checker, and generics would become compile-time values. Generated code is written out
  as real `.ctx` files and compiled in a later step, so errors point at files a person can open
  and a generator can't observe its own output. Revisit only if reflection and compile-time
  consts fall short on real code.
- **No checking in a child process for the language server:** every buffer and every answer
  would cross a pipe on each edit. A panic ends the server and the client restarts it; the
  recovery test keeps that rare.
