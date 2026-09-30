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
| 3a | Language work before the lexer (below) | done | `2056bb4` |
| 4 | Lexer | done | |
| 5 | Parser | done | |
| 6 | Checker | **in progress**: sub-steps 1–4 done | |
| 7 | Self-hosting fixpoint | | |
| 7a | Language server | | |
| 8 | Decide ctxi's role | | |
| 9 | Metaprogramming: build programs, attributes, compile-time consts | future | |

### Where we are

- The C backend runs a native `ctxc`. `ctxi/cbackend.py` bootstraps it into `build/ctxc` on first
  use (about 20s) and rebuilds it when ctxc, the runtime or std changes. ctxc compiles itself in
  0.2s. `CTX_CTXC=interp` runs the interpreted ctxc instead.
- `CTX_BACKEND=c python -m unittest discover tests` passes all 334 tests.
- `tools/ctest.py` passes 171 corpus programs, and skips 20 (below). `tools/ctest.py --same-c`:
  native and interpreted ctxc write byte-identical C for all 180 programs and for ctxc itself.
- `tools/lextest.py`: ctxc's token dumps match ctxi's for all 483 files (stage 4).
- `tools/parsetest.py`: ctxc's syntax trees match ctxi's for the 392 files that parse, and the
  first diagnostic matches for the 91 that don't (stage 5). `tools/recover.py`: all 333,900
  damaged copies of the corpus's files parse and pass its checks.
- `tools/checktest.py`: ctxc's dump of the checked declarations, const initializers and function
  bodies matches ctxi's (`--decls`) for all 249 corpus programs that check, and the first
  diagnostic matches for 443 of the 457 that don't; the other 14 stop at a safety check of
  sub-step 5 (stage 6, sub-steps 1–4). The checker runs without a panic on 15,060 damaged files.
- Friction found while writing ctxc is logged in [FRICTION.md](FRICTION.md).

### Known gaps

- 20 corpus programs read temporary files that the test suite deletes once it's done, so
  `ctest.py` skips them. `tools/corpus.py` should copy those files into the case directory.
- The C backend prints no `in fn` stack trace with a panic (see Open decisions).
- A const whose value panics (`[200 + 100]` as `[1]u8`) panics at runtime, not at compile time
  as spec §14 implies, and the backends differ on when: ctxi when it compiles the function that
  uses it, C on first use. Stage 6 folds consts in the checker, which makes it a compile error.
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
- **The front end is built for an editor from the start.** It is a library that returns every
  diagnostic and a queryable model of the program, not a pass that stops at the first error. See
  [Editor support](#editor-support). ctxi stays a stop-at-first-error reference.

## Architecture

The compiler is a pipeline over one program: std plus the user's files. Until stage 6 the Python
front end stands in for the ctxlang one.

```
.ctx files ──> lexer ──> parser ──> checker ──> typed IR ──> C emitter ──> out.c + ctxrt.c ──> cc ──> exe
(std + program)                                  ^
                  ctxi front end (Python) ── irdump
```

The ctxlang front end's result is an `Analysis`: every diagnostic, plus a semantic model that the
language server (stage 7a) queries. IR is lowered from it only when there are no errors.

### Source layout

```
ctxc/                  one multi-file program (every .ctx in the directory)
  main.ctx             driver: args → files → pipeline → out.c
  source.ctx  diag.ctx                    spans and line tables, the diagnostics list
  lexer.ctx  parser.ctx  syntax.ctx       front end (stages 4–5)
  recover.ctx                             the recovery test's checks (tools/recover.py)
  types.ctx  check.ctx                    checker (stage 6): interned types; declarations
  ir.ctx  ir_read.ctx  ir_print.ctx       IR, its reader and canonical printer
  emit_c.ctx                              backend (stage 2)
  dump.ctx                                token, syntax-tree and declaration dumps for the diffs
ctxc/rt/ctxrt.h ctxrt.c                   C runtime: panic, natives, startup
ctxi/irdump.py                            Python → IR (stage 1)
ctxi/declsdump.py                         Python's checked declarations, for checktest (stage 6)
ctxi/cbackend.py                          IR → ctxc → cc; bootstraps the native ctxc (stage 3)
tools/ctxc.py                             driver: compiles a program to an executable
tools/corpus.py  irtest.py  ctest.py      corpus, IR roundtrip, C backend differential tests
tools/lextest.py  parsetest.py            token and tree dumps against ctxi's, and fuzzing
tools/recover.py                          the recovery test, in parallel over the corpus
tools/checktest.py                        declaration dumps against ctxi's (stage 6)
```

## Editor support

A language server (stage 7a) runs the front end on every edit, on code that is usually
half-written, in a process that stays up for hours. Retrofitting that onto a compiler that stops at
the first error, keeps only start positions and throws away what it learned means rewriting the
front end, so stages 4–6 build these in from the start. ctxi is not changed: it stays the
stop-at-first-error reference, and the differential tests compare against ctxc's *first*
diagnostic (see Testing).

**Front end as a library.** `check{ files } -> Analysis` takes source text, not paths, so an editor
can pass unsaved buffers. It never exits or panics on bad input; `@panic` means a compiler bug. All
of one analysis lives in one arena, which is dropped whole when the next edit arrives. There is no
global mutable state. The driver's `build` is `check`, then IR, then C, and it stops after `check`
if there are errors.

**Positions.**
- Every token and syntax node carries a span: file id plus start and end byte offsets. Lines and
  columns are computed on demand from a per-file table of line starts. The lexer no longer counts
  columns as it goes.
- Error messages print columns in characters, as ctxi does. The language server converts offsets to
  whatever the client negotiated: UTF-8 if it accepts `positionEncoding`, UTF-16 otherwise.
- Nodes that the parser makes up during recovery get zero-width spans at the point where it
  recovered.

**Diagnostics.** A diagnostic is a severity, a primary span, a message and optional related spans
with notes ("first borrowed here"). Phases append to one list, passed as a `mut diags` context field,
rather than returning at the first error. The list is capped (100) so a broken file can't flood the
client. Message text stays the interface that tests match on.

**Lexer recovery.** A bad character, an unterminated literal or a bad escape becomes an error token
plus a diagnostic, and lexing continues. An unterminated literal ends at the end of the line and an
unterminated block comment at the end of the file.

**Comments are kept.** The lexer records comments in a side list per file, not in the token stream,
so the parser doesn't see them. Hover docs, a formatter and folding ranges need them later. They
cost nothing now and are hard to recover afterwards. The doc-comment syntax is a separate spec
decision.

**Parser recovery.**
- The tree has `error` variants in `Decl`, `Stmt`, `Expr` and `TypeExpr`. A missing name is a name
  node flagged as missing, so `a.` parses as a field access with a missing field. Completion
  depends on this.
- After an error the parser skips to a synchronization point: a top-level keyword (`fn`, `struct`,
  `union`, `type`, `const`, `namespace`), the next statement (a newline at the same brace depth,
  §11.3), or the brace that closes the current block. It counts `{` `}` so one bad token doesn't
  swallow the rest of the file.
- A new error is reported only once the parser has consumed a token since the previous one, so a
  single mistake doesn't produce a cascade.
- Nesting depth is limited, and too deep is a diagnostic, not a stack overflow.

**Checker recovery.**
- An `error` type unifies with everything and never produces a message. An unresolved name, or an
  `error` node from the parser, gets that type.
- Each declaration and function body is checked on its own, and an error in one doesn't stop the
  others. A missing `main` is a diagnostic, not a stop.
- Flow and safety checks (6.4, 6.5) skip a function whose body already has type errors, since what
  they would report is mostly noise.
- IR is produced only when there are no errors.

**The semantic model.** The checker's result is kept as data, not only lowered to IR. The IR is
monomorphized with names resolved away, and ctxi already checks each generic body once with opaque
type parameters (§9), which is the view an editor wants. The checker records:

| Record | Serves |
|---|---|
| each name use → its declaration (the file and span of a local, field, variant, fn, type or namespace) | go to definition, references, rename, semantic tokens |
| each expression's type, and a local's type at each use (after narrowing, §8) | hover, inlay hints |
| each declaration: kind, name, span, signature text, and its namespace | document and workspace symbols, hover |
| scopes: each block's locals, with the span where each one is live | completion of names |
| the expected type at each `{` of a call or literal, and which fields a pun or `..` supplied | completion of field names, signature help, hover on `..` |

These are side tables indexed by node id, not fields written into the tree as ctxi does (`e.ty`,
`e.ref`). That keeps parsed trees read-only, so a file that didn't change, std in particular,
doesn't have to be reparsed for each check.

**Speed.** On every edit the server re-lexes and reparses the files that changed and rechecks the
whole program. That is simple and probably fast enough: ctxc's backend compiles all of ctxc in
0.2s, and the front end should take the same order of time. Measure it in stage 6, with a budget of
about 100 ms for ctxc itself. Only if a profile says otherwise: skip unchanged function bodies, or check
only up to the cursor for completion.

**What is built during the port and what waits.** A change to the shape of the data or of the
control flow is built during stages 4–6, because retrofitting it means rewriting the port. That
covers spans, node ids, error nodes and recovery, comments kept on the side, the diagnostics list,
side tables, per-declaration check state (stage 6), and lowering from any root. Anything that only
*reads* those structures waits for the stage that needs it: the language server and its queries
(7a), doc-comment syntax, reflection (9.3) and the compile-time evaluator (9.5). The diffs against
ctxi still work, because on valid code the extra structure changes no dump, and on invalid code only
the first diagnostic is compared.

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

### 3a. Language work before the lexer — done

The lexer is the first user of string literals as text and of keyword tables, so FRICTION.md #1
(string literals need a local) and #12 (no const string tables) come first. Literals need somewhere
to live and a read-only type to have, which in turn needs read-only pointers and slices. In order:

1. **Read-only pointers** (§16 Q2) — *done.* `*T` is read-only and `*mut T` is writable; `*mut T`
   converts to `*T`, also inside `?`. `&p` is `*mut T` only if `p` is a mutable place. A place
   through a deref is mutable only through a `*mut`. A `mut` field holds a `*mut T`. Checker only:
   `tkey` erases mutability, so the IR and backend are unchanged.
2. **Built-in slices** (§12, Slices) — *done.* `[]T` and `[]mut T`, with `.ptr` and `.len`; the
   zero value is the empty slice, whose `ptr` is unspecified. `s[i]` is bounds-checked and
   `s.ptr[i]` is the unchecked form. `s[lo..hi]` with either end optional; an array place or
   `*[N]T` slices too, and `*[N]T` converts to `[]T`. `@slice(p, n)` builds one from a pointer.
   `@cast` can no longer drop read-only-ness. In the IR a slice type is a struct of `ptr` and
   `len`, plus two nodes, `sindex` and `ssub` (IR version 3). `slice::` keeps `empty`, `cast`,
   `copy` and `fill`.
3. **Literal views** (#1) — *done.* `utf8::String` is the only text type (`ascii` is byte-level
   character tests). A string literal where a `[]u8` or `utf8::String` is expected (also inside
   `?`) views static read-only bytes and is derived from no local (§14); as a `utf8::String` it
   is checked for valid UTF-8 at compile time. Elsewhere it is still a `[N]u8`. A literal branch
   of an `if` or `match` follows a sibling branch that is a view. In the IR, `(sbytes T STR)`
   (IR version 4); a `utf8::String` is a struct literal around one. C emits a string literal.
4. **Const tables** (#12) — *done.* Consts may hold literal views, e.g. `const KEYWORDS: [12][]u8 =
   [...]`, as `[]u8` or `utf8::String`, also inside struct literals. This fell out of step 3 with
   no checker or IR change. Each use of a const was still a copy of its initializer; since
   stage 4, a const of array, struct or union type is an IR `const` item, kept in a static in C
   and computed on first use (IR version 7).

*Done when:* each step passes the test suite under both backends and `ctest.py --same-c`, and
FRICTION.md #1 and #12 are resolved.

### 4. Lexer — done

`lexer.ctx` ports `ctxi/lexer.py` (about 500 lines, with `source.ctx` and `diag.ctx`). A token is
a kind, a newline flag and a span, with no value: the parser reads a literal's value from its
text (`lexer::int_value`, `float_value`, `char_value`, `str_value`). Kinds are an enum,
`tok::Kind: u8`: enums (spec §12) were added for this (FRICTION.md #15). An enum is its base
integer type in the IR, and a `match` on one is a `switch` (IR version 6). The tables in `tok`
led to consts as IR items (FRICTION.md #20, IR version 7). Comments go in a side list.
A problem becomes an error token plus a diagnostic, and lexing goes on. `source.ctx` has spans
and line tables, and `diag.ctx` has the capped diagnostics list that the parser and checker will
append to.

`ctxc tokens FILE...` prints a dump (`dump.ctx`), and `tools/lextest.py` compares it with ctxi's.
It also has a `--fuzz N` mode, which damages each file N ways and compares again.

ctxi changed to give both lexers one exact definition:
- Names and digits are ASCII only (spec §1). `str.isalpha` had let `café` be a name, and
  `1²` crashed ctxi.
- `0x` or `0b` with no digits is `invalid number literal` instead of a crash.
- `''` and `'''` are errors: a quote inside a character literal must be escaped.
- A bad character is shown by `show_char`: `'c'`, `'\x01'`, and for non-ASCII `'é' (U+00E9)`,
  because the character may be invisible (a BOM, a zero-width space).
- The end of a file after a trailing `// comment` is now at the end, not at the comment's start.
- Tokens record their width, and `lex` can collect comments, for the dump.

ctxc alone rejects invalid UTF-8, which ctxi can't read at all. An int literal above `u64` is
`toobig` in the dump; the checker will need its own message for it (ctxi prints the value).

*Done:* the dumps match for all 397 files of the corpus, `std/` and `ctxc/`, and all 25
lexer-error cases give the same first diagnostic (new `Lexer` tests put each error in the
corpus). `--fuzz 20` agrees on 7,940 damaged files. Natively, all 397 files lex and dump in 0.6s.

### 5. Parser — done

`parser.ctx` ports `ctxi/parser.py` into the tree of `syntax.ctx` (about 1,200 and 140 lines).
Nodes are structs holding a union of kinds, built as values and boxed into the arena when they
become children. Every node has a span from its first token to its last, so parentheses count,
and an expression also has `at`, the position ctxi gives it (the operator of a binary or postfix
expression). Declarations, statements, expressions, types, blocks and names have ids, numbered
per file for side tables. A pun `c` is two uses of the name, so its item and its value get
different ids. Decl, Stmt, Expr and TypeExpr have `error` variants, and a missing name is one
with empty text and a zero-width span.

Recovery ([Editor support](#editor-support)) needs no exceptions. An error sets `bad`, and while
it is set the parser sees the end of the file, so every loop ends and every parse function
returns what it has. That unwinds to the nearest statement, match arm or declaration, which skips
to a synchronization point (`sync`) and goes on. An error is reported only if a token was
consumed since the last one, and not at an error token, which the lexer has reported. Until its
first error the parser takes ctxi's path exactly. Nesting deeper than 256 is `too deeply nested`.

`ctxc syntax FILE...` prints tree dumps (`dump.ctx`), which `tools/parsetest.py` compares with
dumps of ctxi's tree. The dump shows ctxi's positions, not spans, which ctxi doesn't have; the
recovery test checks those instead. `parsetest.py --fuzz N` damages each file N ways at token
boundaries and compares again.

ctxi changed so that both parsers give the same messages:
- `found X` quotes the token as written (`'0x10'`, `'"b"'`, `'@size_of'`). It used to quote the
  token's value, so a string printed as `'b'b''`.
- In a pun `&d`, the path `d` is at `d`, not at the `&`.

*Done:* the dumps match for the 392 files of the corpus, `std/` and `ctxc/` that parse, and the
first diagnostic matches for the 91 that don't (new `Parser` tests put each syntax error in the
corpus). `--fuzz 20` agrees on 9,160 damaged files. The recovery test passes on all 333,900
damaged copies. Natively, the 483 files lex and parse in 0.3s.

### 6. Checker (~5,000 ctxlang, the largest risk)

Port `checker.py` and `types.py`. The IR is the diff target, so the dumper becomes the spec. The
checker also produces the semantic model and recovers from errors with an `error` type ([Editor
support](#editor-support)); neither is in ctxi. Results go in side tables by node id, not into the
tree. Two structural choices serve compile-time consts (9.5), which have to check, lower and run
code while the check is still going:

- **Per-declaration check state.** Each declaration's entry in a side table says whether it is
  unchecked, in progress or done, and holds its results (signature, body types, a const's value). A
  checker entry point `ensure{ decl }` checks a declaration on demand if it isn't done yet. A
  declaration reached while it is in progress is a cycle, reported with the path of the cycle. The
  top-level passes run in ctxi's order and call the same `ensure`, so diagnostics still come out in
  ctxi's order. On-demand checking only happens where the pass order would otherwise reach a
  declaration before it has been checked. Before 9.5 there is one such case, and ctxi already
  handles it ad hoc: an array length `[N]T` that names a const is evaluated while types are
  resolved, with `const_stack` catching cycles (`checker.py` `const_int`). In ctxc this becomes
  `ensure`.
- **Lowering from any root.** Monomorphization and IR output start from a set of roots, not only
  `main`: a const initializer, or later a test function. The IR for one root and what it reaches
  can then be produced in the middle of a check.

Work in sub-steps, each diffed on its own:

1. Name resolution and namespaces (§10), declaration collection, type expressions, layout. The
   name-use table and symbol list come from this step.
2. Inference: type variables as arena nodes with union-find, integer and float literal defaulting
   (§11 Literals), generic application and inference (§9).
3. Statements, expressions, calls, binds, `match`, `let … else`, narrowing (§8), with the paths
   that must end and the `defer` rules on jumps and `return`.
4. Flow checks: definite initialization (§11, Initialization), in loops and `defer` too.
5. Safety checks: exclusivity (§3.1), escape analysis (§14), bound-function scope (§6).
6. Monomorphization and IR output.
7. Const folding. The checker computes every const's value while checking it, as spec §14
   requires, and reports overflow, division by zero, a bad shift count or an out-of-range
   `@as` in an initializer as a compile error at the operation. A const item in the IR then holds
   only literals (`int`, `float`, `bool`, `sbytes`, `null`, `struct`, `variant`, `array`), so
   the C backend can emit it as a `static const` initializer in read-only data and drop the
   `qN()` accessors. ctxi makes the same change first, since its IR is the diff target. The
   value is kept in the const's check state, which compile-time consts (9.5) extend to any
   initializer.

Until sub-step 6 there is no IR to diff, so the diff target is a dump of the checked
declarations (`python -m ctxi PROGRAM --decls`, `ctxi/declsdump.py`; `ctxc decls STD... --
FILE...`; `tools/checktest.py`), plus the first diagnostic. The dump grows with each sub-step.
The `Declarations` tests put every error of the declaration phases in the corpus, at its exact
position.

ctxi checks types, flow and safety in one pass over a body, so its first diagnostic in a body can
be a flow or safety error that comes before a type error. To report the same first diagnostic,
ctxc keeps them in one pass too, in ctxi's order, and a flow or safety check is skipped only
once the body has had a type error.

**Sub-step 1 — done.** `types.ctx` interns types: an `Id` per distinct type, so equality is id
equality, with fixed ids for the error type, the primitives and the capabilities, and
substitution of generic arguments. `check.ctx` collects declarations into namespaces (universe,
std, root) and resolves struct fields, union payloads, enum bases and values, aliases, const
types, signatures and the natives' signatures, which it parses from source like any function.
It then checks `main`, and computes layouts as ctxi's runtime does. The phases run in ctxi's
order (`Checker.check_decls`, split from `check`). An unresolved type becomes `types::ERROR`, and
a message repeated at the same place (a type alias is resolved at each use) is reported once.
Side tables record each syntax declaration's `Decl`, each namespace's `Space`, what each name in
a type refers to and each type expression's type. Array lengths and enum values are computed in
i64, and a value that doesn't fit is `integer constant is too large`; ctxi's integers have no
limit. Checking the declarations of all of ctxc, with lexing and parsing, takes 0.1s natively.

**Sub-step 2 — done.** Inference: `types.ctx` has type variables (`var`, with the kind `any`,
`int` or `float` and a binding in `Store.vars`), prune, zonk, unify, the occurs check and
widening, as in ctxi. The error type unifies with everything. The checker has coercion (to `?T`,
to a slice, `null`, function types by §5), literal defaulting and range checks at the end of a
body, with the operand that fixed a literal's type, generic arguments inferred for literals,
variants and function values (`partial` in `decl_type`), and `cannot infer`. A body's results
are side tables: each expression's type, its implicit conversion (ctxi's Coerce and ToSlice
nodes), what each path names, and whether braces are a literal or a call.

Inference shows only in bodies, and the first bodies checked are const initializers, which have
no locals or flow: literals, arrays, paths, struct and variant literals, operators, `@size_of`
and the other builtins except `@fmt`, then §14's rule for what a const may hold. The dump gives
each initializer a line per expression with its type. What bodies need and consts can't reach
(`&`, ranges, `if` and `match` expressions, `@fmt`) reports `(ctxc) not yet checked`, which
checktest counts as skipped. The `ConstInitializers` tests put every const error in the corpus.

**Sub-step 3 — done.** Function bodies: statements, locals, context fields and match bindings,
paths to locals (with §10's rule for a local that isn't a function in a call), calls with `&p`
for `mut` fields and `..` forwarding, binds, places and their mutability, fields, indexes,
ranges, `&`, `if` and `match` as statements and expressions (with ctxi's `join` and literal
views), `let … else`, labeled loops, `defer`, `@fmt` and narrowing: facts through `and`, `or`
and `not`, on locals and field paths, in branches, `while` bodies and after an `if` that leaves.
Locals are a list of `Var`s, and scopes a list of bindings with a mark where each scope starts;
a scope keeps only its latest binding of a name, as ctxi's dict per scope does. Narrowing needs
to know where a path ends, so the flow state that says so (`dead`) came with this step, and with
it the checks that use nothing else: paths that must end in `return`, a branch that must end in
a value, a `let … else` that must leave, and the `defer` rules for `return` and jumps. New side
tables: the local each `let` and binder declares, how each field or index reaches its value, a
narrowed field's `?T`, what `..` supplied, and each `@fmt`'s pieces with the push each becomes.

The dump gives every function body a line per statement and expression (`ctxi/declsdump.py`
describes it). ctxi's checker rewrites the tree it checks, so checktest gives each program its
own copy of std. Where ctxi stops at a sub-step 4 or 5 check that ctxc doesn't make yet,
checktest skips the program (`PENDING`). The `Bodies` tests put every error of this step in the
corpus.

Natively, lexing, parsing and checking all of ctxc with std takes about 130 ms, up from 80 ms for
the declarations alone, so bodies are already past the 100 ms budget for the whole front end.
Profile before sub-step 5 adds its passes.

**Sub-step 4 — done.** Definite initialization. The flow state is ctxi's: besides `dead`, the
tracked locals (`let x: T` without a value, not a `let mut` of a type with a zero value)
assigned on every path (`defs`) and on some path (`maybe`). The sets hold only tracked locals and
are never changed in place, so saving a state is a copy of three words. They are saved and merged
where ctxi does, at `if`, `match`, `let … else` and `defer`, and each loop keeps the state at each
`break` and `continue`. A read of a tracked local must come after it is assigned on every path,
and a `let` local may be assigned once: not twice on one path, not on a path that can repeat a
loop, not in a `defer`. A flow error is reported only while its body has no other error. The
`Initialization` tests put each of these errors in the corpus.

*Done when:* IR matches the Python dump across the corpus, every compile-error test's first
diagnostic contains the same fragment at the same position, the recovery test passes on the whole
front end, and checking ctxc stays within the time budget.

### 7. Self-hosting fixpoint

The native `ctxc` from stage 3, now with the ctxlang front end, compiles its own source to `ctxc2`.
`ctxc2` compiles the source again to `ctxc3`.

*Done when:* `ctxc2.c` and `ctxc3.c` are byte-identical, and the full suite passes under `ctxc3`.

### 7a. Language server

`ctxls`, written in ctxlang, speaks LSP (JSON-RPC over stdin and stdout) and answers from the
`Analysis` that stages 4–6 produce ([Editor support](#editor-support)). The JSON reader and writer
grow out of `examples/json`.

- **Features, in order:** diagnostics on open and change (with debouncing), go to definition, hover
  (type and signature), document symbols, completion (names in scope, fields after `.`, context
  fields inside `{`), references, rename, workspace symbols, semantic tokens, signature help, inlay
  hints for inferred `let` types.
- **Workspace.** A program is a directory of `.ctx` files plus std (§10). An open file joins the
  program in its directory. Buffers the editor holds replace the text on disk.
- **What std needs:** `io::read` of an exact byte count from stdin, because a message body has no
  trailing newline and `read_line` won't do; `fs::list` to find a program's files (deferred at
  stage 0); and writing raw bytes to stdout without a newline. A client that sends
  `workspace/didChangeWatchedFiles` could stand in for `fs::list`.
- **Robustness.** A panic kills the server, so the recovery test gates every release. A request
  whose analysis fails for an internal reason returns an LSP error and doesn't take the session down
  with it.

*Done when:* VS Code, with a minimal client extension, shows diagnostics while you type, and go to
definition, hover and completion work on `ctxc/` itself. The editor-query fixtures pass.

### 8. Decide ctxi's role

Choose one: keep ctxi as the executable reference, with every spec change landing in both
implementations, or freeze it as the bootstrap for a pinned `ctxc` version. Bootstrapping from a
committed `ctxc.c` would remove the Python dependency entirely.

### 9. Metaprogramming — future

The aim is code generation (serializers, for example) and build logic written in ctxlang, as with
Zig's `build.zig` and Jai's `#run`, without macros and without making types compile-time values.
Two facts make this cheaper here than in those languages:

- **Capabilities already mark what is safe to run.** Every effect comes through the context (§1.3)
  and user code can't construct a capability (§15.3). Code that needs no capability is
  deterministic and hermetic by construction, so compile-time code needs no separate sandbox rules.
- **The compiler is a ctxlang library after stage 7.** A program can import the lexer, parser and
  checker and get a checked program as plain unions and structs, so reflection needs no builtins.

Generated code is written out as real `.ctx` files and compiled in a later step, never spliced
into the compile that is running. Errors in generated code point at files a person can open, and a
generator can't observe its own output, which removes the fixed-point problem of generating code
that changes the types being reflected on.

Steps, each usable on its own:

1. **Build programs.** `build.ctx` declares `fn build { mut b: Build, ... }`. It is compiled and
   run with the existing pipeline before the program it describes. `Build` is a new capability
   type whose natives record a build graph: executables, their source roots, and generated files
   (`build::exe`, `build::gen_file`). Generated files go under `build/gen/` and join the program's
   file list. A build program declares `Fs` or `Mem` only if it needs them, as `main` does.
2. **Attributes, parser only.** `#path` or `#path{ field = e, ... }` on its own line before a
   declaration, a struct field, a union variant or a context field. The parser keeps them in the
   syntax tree and the checker ignores them. `#` is used rather than `@` because `@` means the
   compiler acts (§13), knows every name and rejects unknown ones, while attributes are inert data
   for generators. Compiler-level annotations, if any are added (`@inline`, `@export`), stay under
   `@`. The `{ }` form is the language's own named-argument syntax, so there is no separate
   attribute grammar as with Rust's `#[...]`.
3. **Reflection: `build::check`.** Runs the front end on an executable's sources and gives the build
   program the checked declarations as data: structs, unions, fields, layouts and attributes. That
   data is the stage 6 `Analysis`, read-only trees plus side tables, so no separate reflection
   format is needed.
   Needs stage 7, since before it the front end is Python and this would have to go through a
   native.
4. **Typed attributes.** `#name{ ... }` resolves `name` as a path to a struct (§10) and checks the
   braces as a const struct literal of it (§7, §14.1). Bare `#name` requires a struct with no
   fields. The compiler still gives attributes no meaning; the check
   catches typos such as `#jsno` or `rename_to =`, which would otherwise be dropped silently.
   Generators receive attributes as typed values. A generator library declares its own:

   ```
   namespace json {
       struct derive {}
       struct field { rename: ?[]u8, skip: bool }
   }

   #json::derive
   struct User {
       #json::field{ rename = "user_id", skip = false }
       id: u64,
       name: []u8,
   }
   ```

5. **Compile-time consts.** A `const` initializer may call any function. No capability exists at
   compile time, apart perhaps from a compile-time arena for allocation, so only effect-free code
   can run there. ctxc evaluates it with an interpreter over the IR, which is monomorphized, typed
   and laid out, so the interpreter is much smaller than ctxi. Checking the const calls `ensure` on
   the functions it reaches, lowers from the initializer as the root, and runs that IR. All three
   are stage 6 machinery, so this step adds the interpreter and a new caller, not a change to the
   checker's structure. The value is cached in the const's check state, so the language server
   doesn't re-run it on edits that don't touch its inputs. A const whose evaluation reaches itself
   is a cycle error from `ensure`, and running out of fuel (a step limit) is a diagnostic, not a
   hang. The result must hold no pointers
   other than ones to static data, the same rule as 3a step 4. Uses: lookup tables, perfect-hash
   keyword maps, precomputed tables for parsers.

Not planned: generating declarations inside the compile that is running (Zig's `inline for` over
fields with types as values, or Jai's `#insert`). It needs lazy analysis or a fixed-point loop in
the checker, and generics would become compile-time values. Revisit only if steps 1–5 fall short
on real code.

*Done when:* a JSON generator in ctxlang derives `write` and `read` functions for
`#json::derive` structs, and `examples/json` uses them for a typed round trip.

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
| `[]T`, `s[i]`, `s[lo..hi]` | `struct { T *m_ptr; uint64_t m_len; }`; `ctx_idx`, `ctx_range` | Bounds checks panic as in ctxi. The runtime's natives see it as `ctx_slice`. |
| struct | C struct, same field order | Checked with `_Static_assert` on `sizeof` and `offsetof`. |
| union, `?T` | `struct { uint32_t tag; union { … } p; }` | Tag at 0, payload at `align_up(4, payload align)`. `null` is tag 0. |
| enum | its base integer type | `match` becomes an if-else chain on the value (IR `switch`). |
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
  produce the same wording. Message text is part of the interface. ctxc reports diagnostics in the
  order it finds them, running its phases and visiting files and declarations in ctxi's order, so
  its first diagnostic is the one ctxi stops at. That first diagnostic is compared with ctxi.
  Later ones are ctxc's own, and ctxc may report more than ctxi.
- **Recovery** (`tools/recover.py`, from stage 5). Damage every file in the corpus: cut it at each
  token boundary, and delete or duplicate single tokens. Run the front end on every result, inside
  ctxc (`ctxc recover`), in parallel chunks. It must not panic, must keep under the diagnostic
  cap, and must build a well-formed tree: ids used once, and every span inside its parent's. A
  cut inside a declaration that ends in `}` must report an error, and a cut must still produce
  symbols for the declarations before it. Other damage can leave valid code, so it needn't report
  anything. This is the test that guards editor use.
- **Editor queries** (stage 7a). Fixture files mark positions (`/*^def*/`, `/*^hover*/`) and state
  the expected answer, which covers the semantic model without a client.
- **Float text.** `f64_digits` must copy Python's `repr` exactly: shortest round-trip digits,
  exponent form below `1e-4` and from `1e16`, and a `.0` suffix.

## Open decisions

- **Freezing the spec during the checker port.** **Settled:** the spec is frozen for stage 6. No
  language changes until the IR diffs match across the corpus; a bug fix in ctxi lands in both
  checkers.
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
- **Language friction.** ctxc pushes on method sugar (Q4), and imports and files as namespaces
  (Q5, Q6). Each point of friction goes in
  [FRICTION.md](FRICTION.md) as evidence for these questions.
- ~~**Stage 3 speed.**~~ The interpreted backend compiles ctxc in about 20s, so it wasn't a problem.
