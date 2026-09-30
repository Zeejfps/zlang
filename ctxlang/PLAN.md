# ctxc: a ctxlang compiler written in ctxlang

`ctxc` is a compiler written in ctxlang that emits C. The Python interpreter `ctxi` becomes the
bootstrap and the reference implementation. The backend comes first, fed by a typed IR that `ctxi`
dumps. The front end is then ported piece by piece and diffed against Python at every step.

## Status

| Stage | What | State | Commit |
|---|---|---|---|
| 0 | Prerequisites in the language and std | done | `3625746` |
| 1 | Typed IR and the Python dumper | done | `cbba391` |
| 2 | C backend and runtime | done | `5f236c1` |
| 3 | First bootstrap: a native backend | done | `aa6a805` |
| 3a | Language work before the lexer (below) | **next** | |
| 4 | Lexer | | |
| 5 | Parser | | |
| 6 | Checker | | |
| 7 | Self-hosting fixpoint | | |
| 8 | Decide ctxi's role | | |

### Where we are

- The C backend runs a native `ctxc`. `ctxi/cbackend.py` bootstraps it into `build/ctxc` on first
  use (about 20s) and rebuilds it when ctxc, the runtime or std changes. ctxc compiles itself in
  0.2s. `CTX_CTXC=interp` runs the interpreted ctxc instead.
- `CTX_BACKEND=c python -m unittest discover tests` passes all 215 tests.
- `tools/ctest.py` passes 110 corpus programs, and skips 20 (below). `tools/ctest.py --same-c`:
  native and interpreted ctxc write byte-identical C for all 130 programs and for ctxc itself.
- Friction found while writing ctxc is logged in [FRICTION.md](FRICTION.md).

### Known gaps

- 20 corpus programs read temporary files that the test suite deletes once it's done, so
  `ctest.py` skips them. `tools/corpus.py` should copy those files into the case directory.
- The C backend prints no `in fn` stack trace with a panic (see Open decisions).
- Linux has no large-stack link flag yet (`cbackend.stack_flags`). The main thread keeps its
  default stack (usually 8 MB), below the runtime's 16 MB check, so deep recursion segfaults instead of panicking.

## Key decisions

- **Target C, not an interpreter.** An interpreter running inside ctxi would stack two interpreters.
  C gives native speed, and ctxlang has no GC or exceptions to translate.
- **Backend before front end.** A Python IR dump lets the C backend run the whole test corpus before
  the checker, the hardest part, is ported.
- **Typed IR as the seam.** The IR is monomorphized, fully typed and has a canonical text form. It
  is the contract between checker and backend, and the diff target for the port.
- **Differential testing throughout.** Tokens, syntax trees, IR, program output and compile errors
  are all compared against ctxi on the same corpus.

## Architecture

The compiler is a pipeline over one program: std plus the user's files. Until stage 6 the Python
front end stands in for the ctxlang one.

```
.ctx files ──> lexer ──> parser ──> checker ──> typed IR ──> C emitter ──> out.c + ctxrt.c ──> cc ──> exe
(std + program)                                  ^
                  ctxi front end (Python) ── irdump
```

### Source layout

```
ctxc/                  one multi-file program (every .ctx in the directory)
  main.ctx             driver: args → files → pipeline → out.c
  lexer.ctx  parser.ctx  syntax.ctx       front end (stages 4–5)
  types.ctx  check_*.ctx                  checker (stage 6)
  ir.ctx  ir_read.ctx  ir_print.ctx       IR, its reader and canonical printer
  emit_c.ctx                              backend (stage 2)
ctxc/rt/ctxrt.h ctxrt.c                   C runtime: panic, natives, startup
ctxi/irdump.py                            Python → IR (stage 1)
ctxi/cbackend.py                          IR → ctxc → cc; bootstraps the native ctxc (stage 3)
tools/ctxc.py                             driver: compiles a program to an executable
tools/corpus.py  irtest.py  ctest.py      corpus, IR roundtrip, C backend differential tests
```

## Stages

Each stage ends with something that runs and a check against ctxi. Line counts are rough
estimates of ctxlang source, which runs longer than the equivalent Python.

### 0. Prerequisites in the language and std — done

The compiler is the first large, long-running ctxlang program, and it needed things the language
didn't provide:

- **Large memory.** The `Mem` capability and `mem::pages` (§15, §17).
- **One-node allocation.** `alloc::new(T, S)` returns `?*T`.
- **File discovery.** `fs` can't list a directory, so the driver passes the file list in `args`.
  `fs::list` can come later.
- **Running the C compiler.** There is no process capability. `ctxi/cbackend.py` runs cc after
  ctxc writes the C.
- **Text output helpers** for integers and floats on a builder.

*Done when:* a test program can allocate 256 MB from the new capability under ctxi, and
`alloc::new` is in std with tests.

### 1. Typed IR and the Python dumper — done

`ir.ctx` defines the IR, `ctxi/irdump.py` produces it from the checked tree (`python -m ctxi
PROGRAM --ir`), and `ir_read.ctx` loads it back. The IR is what the backend needs and nothing
more:

- **Monomorphized.** The dumper walks reachable instances from `main`.
- **Fully typed, with implicit steps made explicit.** Widening and `T` to `?T` conversions are
  nodes. Punning, `..` forwarding and inferred generics are resolved. A narrowed local becomes a
  read of the optional's payload. Consts are folded to values.
- **Types interned by id.** Type equality is id equality.
- **Layouts included.** The backend checks them with `_Static_assert`, so `@size_of` agrees across
  implementations.
- **Canonical text** (S-expressions). The Python and ctxlang printers produce identical bytes, so a
  diff means a real difference.

*Done when:* the dumper handles every program in the corpus, and read-then-print in ctxlang
reproduces the Python dump byte for byte (`tools/irtest.py --roundtrip`).

### 2. C backend and runtime — done

`emit_c.ctx` prints C: temporaries fix evaluation order, `if`/`match` expressions become statement
expressions, and deferred bodies are copied to every exit. `ctxrt.c` provides panics, startup
(capabilities, `args`, exit code) and the natives: `io`, `fs::sys_*`, `mem::sys_pages`, and float
formatting and parsing. The mapping is in the table below.

*Done when:* the test suite passes with `CTX_BACKEND=c`, apart from the listed expected
divergences.

### 3. First bootstrap: a native backend — done

Dump IR for `ctxc` itself, run the interpreted backend on it to get `ctxc.c`, and compile that. The
Python front end now feeds a native backend, and every program in the repo compiles to native code.

*Done when:* the native backend passes the stage 2 suite, and its C output for the corpus is
byte-identical to the interpreted backend's (`tools/ctest.py --same-c`).

### 3a. Language work before the lexer — next

The lexer is the first user of string literals as text and of keyword tables, so FRICTION.md #1
(string literals need a local) and #12 (no const string tables) come first. Literals need somewhere
to live and a read-only type to have, which in turn needs read-only pointers and slices. In order:

1. **Read-only pointers** (§16 Q2) — *done.* `*T` is read-only and `*mut T` is writable; `*mut T`
   converts to `*T`, also inside `?`. `&p` is `*mut T` only if `p` is a mutable place. A place
   through a deref is mutable only through a `*mut`. A `mut` field holds a `*mut T`. Checker only:
   `tkey` erases mutability, so the IR and backend are unchanged. For now `slice::Slice` holds a
   `?*mut T` and `@cast` may still drop read-only-ness (`slice::of` needs it); step 2 removes both.
2. **Built-in slices.** `[]T` and `[]mut T`, with `.ptr` (never null; an empty slice holds a
   placeholder address) and `.len`. `s[i]` is bounds-checked; `s.ptr[i]` stays the unchecked form.
   `s[lo..hi]`, `s[lo..]`, `s[..hi]`. `*[N]T` converts to `[]T`. `@slice(p, n)` builds one from a
   pointer. The dumper lowers slices to structs, bounds checks and `ptradd`, so the IR and backend
   don't change. `slice::` keeps `copy`, `fill` and `cast`. Then sweep std, ctxc and the examples.
3. **Literal views** (#1). A string literal converts to `[]u8` where one is expected, backed by
   static read-only bytes, and is derived from no local (§14). Needs one new IR node for the bytes.
   **Open:** whether literals also convert to `ascii::String` and `utf8::String`, or §16 Q11 is
   settled by making `utf8::String` the only text type. Decide after steps 1 and 2.
4. **Const tables** (#12). Consts may hold literal views, e.g. `const KEYWORDS: [12][]u8 = [...]`.
   Emit large consts as static data instead of inlining them if a profile shows the copies.

*Done when:* each step passes the test suite under both backends and `ctest.py --same-c`, and
FRICTION.md #1 and #12 are struck through.

### 4. Lexer (~500 ctxlang)

Port `ctxi/lexer.py` using `ascii::Cursor`. Positions (line, column, file) must match, because
error messages depend on them.

*Done when:* token dumps match Python for all of `std/`, `examples/` and the corpus, including
lexer errors.

### 5. Parser (~1,800 ctxlang)

Port `ctxi/parser.py` into syntax-tree unions allocated from an arena. `examples/json/parser.ctx`
shows the style: recursive descent and `let … else` error propagation. Newline sensitivity (§11.3)
and the rule for generic application on the same line (§9.2) are where the two parsers are most
likely to disagree.

*Done when:* syntax-tree dumps match Python across the corpus, and every syntax-error test gives the
same message and position.

### 6. Checker (~5,000 ctxlang, the largest risk)

Port `checker.py` and `types.py`. The checker's output is the IR, so the dumper becomes the spec and
the diff target. Work in sub-steps, each diffed on its own:

1. Name resolution and namespaces (§10), declaration collection, type expressions, layout.
2. Inference: type variables as arena nodes with union-find, integer and float literal defaulting
   (§11 Literals), generic application and inference (§9).
3. Statements, expressions, calls, binds, `match`, `let … else`, narrowing (§8).
4. Flow checks: initialization, paths that must end, `defer` rules.
5. Safety checks: exclusivity (§3.1), escape analysis (§14), bound-function scope (§6).
6. Monomorphization and IR output.

*Done when:* IR matches the Python dump across the corpus, and every compile-error test produces a
message containing the same fragment at the same position.

### 7. Self-hosting fixpoint

The native `ctxc` from stage 3, now with the ctxlang front end, compiles its own source to `ctxc2`.
`ctxc2` compiles the source again to `ctxc3`.

*Done when:* `ctxc2.c` and `ctxc3.c` are byte-identical, and the full suite passes under `ctxc3`.

### 8. Decide ctxi's role

Choose one: keep ctxi as the executable reference, with every spec change landing in both
implementations, or freeze it as the bootstrap for a pinned `ctxc` version. Bootstrapping from a
committed `ctxc.c` would remove the Python dependency entirely.

### Bootstrap chain

| Step | Front end | Backend runs as | Produces |
|---|---|---|---|
| Stage 2 | ctxi (Python) | ctxlang interpreted by ctxi | C for test programs |
| Stage 3 | ctxi (Python) | ctxlang interpreted by ctxi | `ctxc.c`, a native backend |
| Stages 3–6 | ctxi (Python) | native | C for any program |
| Stage 7 | ctxc (native) | native | `ctxc2`, then `ctxc3`; their C output must be identical |

## How ctxlang maps to C

C11 with GNU extensions (overflow builtins, empty structs, statement expressions), built with gcc
(MinGW on Windows), Apple clang on macOS, or `zig cc` (`CTX_CC=zig`). Flags: `-std=gnu11 -O1 -w
-fwrapv -fno-optimize-sibling-calls`. Layout follows ctxi's exactly.

| ctxlang | C | Notes |
|---|---|---|
| `i8`…`u64`, `bool` | `int8_t`…`uint64_t`, `_Bool` | `usize` is fixed at 64 bits for now. |
| `+ - *` on integers | `__builtin_*_overflow` | Panics with `integer overflow`. |
| `/ %` on integers | guarded C `/ %` | Zero divisor panics. `MIN / -1` panics. `MIN % -1` is 0. Both round toward zero, as in ctxi. |
| `f32` arithmetic | `float` | Needs `FLT_EVAL_METHOD == 0` (SSE). |
| `@as`, `@trunc`, `@wrap_*` | range check then cast; unsigned arithmetic then cast | |
| `[N]T` | `struct { T a[N]; }` | Wrapped so arrays copy, assign and return as values. |
| struct | C struct, same field order | Checked with `_Static_assert` on `sizeof` and `offsetof`. |
| union, `?T` | `struct { uint32_t tag; union { … } p; }` | Tag at 0, payload at `align_up(4, payload align)`. `null` is tag 0. |
| `Io`, `Fs`, `Mem` | empty struct | Size 0 with GNU C, as in ctxi. |
| `*T`, `q + n`, `q[i]` | `T*`, pointer arithmetic | Not checked. §12.7 calls a bad pointer UB. |
| `a[i]` on arrays | index with a bounds check | Panics, as the spec requires. |
| `fn{C} -> R` | pointer to a record whose first member is the code | Called with the record and the fields in name order. Conversion to a type with more fields wraps the value in an adapter. |
| `&fn{C} -> R` | a bind record from `ctx_alloc` | Never freed, like ctxi. |
| `defer` | copied to each exit | Innermost first. `return e` evaluates `e` into a temporary first. |
| `if`/`match` expressions | GNU statement expressions | A branch that leaves uses `return`, `break` or `continue`. |
| argument order | temporaries | C leaves argument evaluation order unspecified; ctxi evaluates left to right. |
| `@panic`, runtime panics | `ctx_panic(file, line, col, msg)` | Same `file:line:col: panic: msg` text, exit code 134. |
| stack overflow | check in each function prologue | Compares the frame address to a limit set at startup (16 MB, or `CTX_STACK`). Linked with a 256 MB stack on Windows and macOS. No sibling calls, so every call takes a frame. |

## Testing

- **Corpus.** `tools/corpus.py` records every program the tests run, with its expected output, exit
  code, panic or error, plus `std/` and `examples/`, into `build/corpus`. Every stage checks against
  it.
- **Backend switch.** `CTX_BACKEND=c` sends `run_source` through ctxc and cc, so the existing tests
  run unchanged against both implementations.
- **Expected divergences** (`tools/ctest.py` `DIVERGENCES`): `invalid memory access` (UB in C), the
  `in fn` lines of a panic's stack trace, and the exact point where the stack overflows.
- **Front-end diffs.** Token, syntax-tree and IR dumps are compared byte for byte with Python on the
  whole corpus.
- **Errors.** The compile-error tests match on a message fragment, so the ported checker has to
  produce the same wording. Message text is part of the interface.
- **Float text.** `f64_digits` must copy Python's `repr` exactly: shortest round-trip digits,
  exponent form below `1e-4` and from `1e16`, and a `.0` suffix.

## Open decisions

- **Freezing the spec during the checker port.** Every feature added during stage 6 has to be
  written twice. *Recommendation:* freeze the spec for stage 6, or require each feature commit to
  update both checkers. **Open; decide before stage 6.**
- **Panic stack traces.** ctxi prints the function frames with each panic. Doing this in C needs a
  shadow stack, which costs time on every call. *Recommendation:* a debug flag, off by default.
  **Deferred;** the C backend prints no trace.
- **Where bound-function records live.** **Settled:** leaked into memory from `ctx_alloc`, matching
  ctxi. A spec rule that lets records live in the frame may come later.
- **Widening a stored `fn` value to a wider type.** **Settled:** a static thunk for a named function,
  and an adapter allocated like a bind record for a value known only at runtime.
- **Memory capability design.** **Settled:** a narrow `mut mem: Mem` capability with `mem::pages`,
  separate from `Fs`.

## Risks

- **Checker subtlety.** Literal inference that spans a whole function body, exclusivity and escape
  analysis have many edge cases. Mitigation: IR diffs on every sub-step, and error-fragment tests.
- **Language friction.** ctxc pushes on method sugar (Q4), imports and files as namespaces (Q5, Q6),
  labeled `break` (Q10) and string literals as slices (Q11). Each point of friction goes in
  [FRICTION.md](FRICTION.md) as evidence for these questions.
- ~~**Stage 3 speed.**~~ The interpreted backend compiles ctxc in about 20s, so it wasn't a problem.
