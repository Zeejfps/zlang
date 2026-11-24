# ctxc: what is left

Only open work. How ctxc works, and the decisions behind it, are in [internals.md](internals.md);
finished work is in git history. Concurrency (net, http, the Evented backend) is tracked in
[threads.md](threads.md).

## C interop

The goal is real programs over C libraries: OpenGL or Vulkan rendering, windowing, audio.

- **`#c::export{ name }`**, for a public symbol, over the callback thunk.
- **Loading a library at run time**, where the capability means "it loaded".
- **Floats as text in ctxlang.** `ctxc/rt/ctxfloat.c` is the last of std's natives in C:
  shortest round-trip printing over `snprintf`, as Python's `repr`, and parsing over `strtod`,
  which a program links only if its C uses them (drive.ctx, `uses_float`). A printer with exact
  big-integer digits (Steele and White's, or Ryu's tables) and a correctly rounding parser would
  make std need no C of its own. The failed float-to-integer `@as` writes its value as text too,
  so its message would come from std as well, through the panic fn.

Platforms, each waiting for a target that needs it:
- **macOS on x86_64:** its `readdir` returns the old `struct dirent` unless it is called as
  `readdir$INODE64`, so `sys::DIRENT_NAME` (21, arm64's) is wrong there. A layer is per OS, not
  per architecture, so this needs a way to choose by both.
- **A port's own layer:** a build program naming a layer of its own for a platform std doesn't
  know (`build::platform{ &b, exe, dir }`), so that a port supplies `namespace os` without
  editing std.
- **Freestanding:** a target with no layer at all, where everything that takes no capability
  still works. A program supplies its own `#start` and `#panic` fns (spec §15); what's left is
  std compiling without a layer, a pages fn for function values' records past the runtime's
  first 64 KiB (std/rt.ctx, `record_pages`), and memcpy, memset and fmod, which C compilers call
  themselves.

## Metaprogramming

Code generation and build logic written in ctxlang, without macros and without making types
compile-time values. Generated files, build programs of several files, `deny_unchecked`,
`build::declarations` and attributes on fields are done (spec §19).

- **Cross-compiling.** `build::os` is the host's: building for another platform needs std's layer
  for it, its C compiler, and a build program run on the host but describing the target.
- **Reflection: the checked program.** `build::declarations` gives declarations as the parser
  sees them. What it can't give is what only the checker knows: names resolved, types as types,
  layouts, and attributes' values folded, the `Analysis`. *Direction:* ctxc's checker answers,
  either over a two-way channel between ctxc and the running build program, or by running build
  programs in ctxc's interpreter (eval.ctx), where its calls can reach the checker directly.
  Either avoids a second copy of the front end in every build program.
- **Done when:** a JSON generator in ctxlang derives `write` and `read` functions for
  `#json::derive` structs, and `examples/json` uses them for a typed round trip.

Smaller gaps in `declarations`:
- A union's and an enum's variants have no attributes: `Variant` would need `attrs` as `Field`
  has, when a generator wants them.
- Not in the model: a capability's inclusions (`..Base`), whether its field is a C variable or a
  static, which generic parameters are error sets (`E: error`), and a fn's body.
- A declaration with a syntax error in it is there as far as it parsed, beside the error.
- The ctxc front end is in every build program, used or not (about 50 ms a run): the driver could
  add it only to build programs whose tokens name `declarations`.
- std remembers at most 64 KiB of roots and directories (`build::Known`); a build that gives more
  panics at `declarations`, not before.

Smaller gaps in build programs:
- The driver reads `#build::sources` as written: a `dir` from a const isn't one, and a namespace
  `build` of the program's own, which would shadow std's for the checker, doesn't hide it.
- Only build.ctx's `fn build` names directories: a library of the build program's can't name
  those it needs itself.
- Windows device names (`CON`, `NUL` and the like) aren't refused as executables' names.
- `build_project`'s generated files under build/cbackend/gen are never removed, as the rest of
  that cache isn't.

## Compile-time consts and literal conversions

- **Consts and converted literals in a program with errors.** Both run only in a program without
  errors, so their errors come after the others', and the language server would miss them.
  - *Tried:* marking the declaration that holds each error, and having lowering refuse to enter a
    marked one. Not enough: the checker stays quiet about anything that involves the error type,
    so a declaration with no error of its own can still hold types without a layout from another's
    signature. A const that only calls a clean fn crashed lowering (`lower: a type that isn't
    concrete`, `a struct without a layout`), and lowering has about 45 panics that assume checked
    code.
  - *Direction:* the checker decides, so lowering only ever sees clean code. While it checks a
    declaration, it records what that declaration depends on: each name use, each recorded type,
    inferred error sets, the conversions its literals use, and the writers its `@fmt`s use. A
    declaration is blocked if it holds an error, if a type it records contains the error type, or
    if something it depends on is blocked. At `evaluate`, a const or literal whose root or
    conversion is blocked is skipped, with no error of its own. `lower::alone` keeps a cheap check
    that treats meeting a blocked declaration as a bug.
  - *The risk* is completeness: the dependencies must cover everything lowering can reach, or the
    crashes come back. It needs its own design pass, with the recovery test running consts in
    damaged programs.
- Array lengths, enum values and attributes take only folded consts, since they are needed while
  declarations are resolved. Checking bodies on demand would lift this; nothing has needed it yet.
  For the same reason an attribute can't hold a converted literal.
- No extern fn runs while compiling but the C library's math functions (eval.ctx, `libm`). Float
  formatting and parsing are ctxc's own runtime's, so ctxc could call its copies too.
- `intlit` (a number literal, as its digits, for a big-integer type) and `arraylit` (an array
  literal's elements, for a list) follow `strlit` when something needs them; neither is designed.
- Each literal's conversion runs in a fresh interpreter, which costs ctxc's own build about 30 ms
  of its 450. A machine kept per conversion, between runs, would save most of it.

## The compiler knowing nothing of std

The checker, lowering and runtime should never name a std declaration. Still naming std:
- `c::String`'s C layout: a `?c::String` is a nullable pointer, and an extern fn passes it as a
  `const char *` (`cstr_decl`).
- `c::symbol` and `c::callback` are attributes std declares (std/c.ctx) and the compiler acts on.
  They move beside `#convert` and `#write`, among the attributes the compiler declares itself.
- `main`'s `args` is checked against std's `Args` (check.ctx, `std_type{ .., name = "Args" }`);
  it can be checked as `[][]u8`. Only `fn build` may take std's `Build`.

## Language server

`ctxc lsp` speaks LSP (JSON-RPC over stdin and stdout) and answers from the checker's side
tables. It is a command of ctxc, in `ctxc/lsp.ctx` and files beside it, so the front end, the
driver and std's files are already there and the editor finds the server wherever it finds ctxc.

The front end was built for this: `check::new{ files, .. }` and `check::program` take source text
(so unsaved buffers work), recover from errors in the lexer, parser and checker, keep comments on
the side (`lexer::Lexed.comments`), and record results in side tables by node key, so parsed trees
stay read-only and std's needn't be reparsed after an edit: its trees stay in the arena below a
`mark`, and each check `restore`s to it.

| Record | In `check::Checker` | Serves |
|---|---|---|
| each name use → what it names | `uses` (a `Ref`), `refs` (a `PathRef`), `local_of`; a local's span is `Var.at`, a declaration's its `syntax::Decl` | go to definition, references, rename, semantic tokens |
| a field use → its field | not kept: found from the receiver's type in `expr_ty` and the field's name | go to definition, hover |
| each expression's type | `expr_ty`; a narrowed field's own `?T` in `narrowed` | hover, inlay hints |
| each declaration: kind, name, namespace | `decls` (`Decl.kind`, `name`, `qual`, `syn`) | document and workspace symbols, hover |
| what a `..` supplies | `forwards`, `filled` | hover on `..` |
| where each local's name is in scope | `lives` (a `Live`: the local, from where its name takes effect to where its scope ends; the latest `from` wins), and its type in `Var.ty`, narrowed for a narrowed view | completion of names |
| the fields each `{` takes: a call's, generic arguments inferred, or a literal's type's | `braces` (recorded by `supplied`, so half-typed braces have them too) | completion of field names, signature help |

1. **The server:** reading messages (a `Content-Length` header, then that many bytes, by
   `io::read` in a loop), writing them (`io::write_bytes`, then `io::flush`), and JSON, by the
   parser and printer of `examples/json` moved into `ctxc/`.
2. **Features, in order:** diagnostics on open and change (debounced), go to definition, hover
   (type and signature), document symbols, completion (names in scope, fields after `.`, context
   fields inside `{`), references, rename, workspace symbols, semantic tokens, signature help,
   inlay hints for inferred `let` types.
3. **Doc comments,** for hover: their syntax is a spec decision of its own, still to make.
4. **Editor-query fixtures:** files that mark positions (`/*^def*/`, `/*^hover*/`) and state the
   expected answer, read by the suite's runner, which covers the semantic model without a client.

Design notes:
- **Threads.** One thread reads stdin and queues messages; the main thread takes them, and waits
  with `condition::wait_for` to debounce a run of changes into one check (std/thread.ctx).
- **Positions.** Spans are byte offsets; the server converts to whatever the client negotiated:
  UTF-8 if it accepts `positionEncoding`, UTF-16 otherwise.
- **Workspace.** A program is a directory of `.ctx` files plus std (§10). An open file joins the
  program in its directory. Buffers the editor holds replace the text on disk. A directory with a
  build.ctx is checked with the files its build program gives each executable, generated ones
  included, which the server learns by running it as the driver does (drive.ctx); it runs again
  when build.ctx or a file under a `#build::sources` directory is saved.
- **Speed.** On every edit the server re-lexes and reparses the files that changed and rechecks
  the whole program: about 100 ms for ctxc's own source. Only if a profile says otherwise: skip
  unchanged function bodies, or check only up to the cursor for completion.
- **Consts and converted literals** have their errors only in a program without other errors
  (above); the server reports what the checker reports.

*Done when:* VS Code, with a minimal client extension, shows diagnostics while you type, and go to
definition, hover and completion work on `ctxc/` itself. The editor-query fixtures pass.

## Tools

- **`recover.py` in ctxlang.** The last Python: `tools/recover.py`, and the part of
  `tools/toolchain.py` that builds ctxc for it. It runs many processes at once, with
  `proc::spawn` and `wait`, as the driver's parallel compiles and the suite's runner do. Its
  corpus is the suite's cases: `ctxc run tools/suite -- --corpus OUT`.
- *If wanted:* benchmarks (`#bench`, timed through a clock capability the runner supplies) and
  fuzzing (`#fuzz` over a `[]u8` input), both built in as Go has them.

## The driver

Each only if it gets in the way (ctxc/drive.ctx):
- The front end runs on every `ctxc run`, changed or not: 1.9 s for 99K lines, now the largest
  part of a rebuild. A hash of the sources and of ctxc itself could skip it too; checking and
  lowering only the files that changed is a bigger change.
- A unit's C holds the declarations its functions use, so a big program's units hold about a
  third more C than one file does. The layouts are checked (`_Static_assert`) only in main's.
- Inserting a line moves the positions after it, so every unit of that file is recompiled, though
  only one function changed. Positions relative to their function's first line would keep them.
- A file's units are its functions by a hash of their names; files smaller than a unit share one
  with the next files of their directory, so one that grows past a boundary moves the files after
  it into other units.
- Copies are chosen by size alone, counted in the IR rather than in what C would inline. A big
  function called once from another unit, as a generated ECS runner calls its system, still
  isn't inlined there; grouping functions into units by who calls whom would let it be.
- A file reached twice is found by its absolute path, without looking at links, so a file reached
  through a symbolic link or a junction and directly is compiled twice.
- A C compiler replaced in place by another version isn't noticed: removing build/run starts
  afresh. Nor are the files a killed build leaves, `NAME.N.c` and the like, ever removed.
- `ctxc build`, `ir` and `decls` need std's files listed on the command line; only `run` and `exe`
  find them.

## Known gaps

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
