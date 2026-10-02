# ctxc: a ctxlang compiler written in ctxlang

`ctxc` is a self-hosting compiler written in ctxlang that emits C. A fresh checkout builds it from
its platform's bootstrap, `bootstrap/ctxc.linux.c`, `ctxc.macos.c` or `ctxc.windows.c`, with
nothing but a C compiler.

This file lists only what is left. Finished work is in git history: the last version of this
file that described it, with the old stage numbers (0–12), is at `f53a93f`. ctxi, the Python
interpreter ctxc replaced, is at `8436f4d`.

## Status

| Stage | What | State | Needs |
|---|---|---|---|
| 1 | [Optionals and errors](#1-optionals-and-errors) | in progress | |
| 2 | [C interop](#2-c-interop) | in progress | |
| 3 | [Metaprogramming](#3-metaprogramming) | in progress | |
| 4 | [Literal conversions](#4-literal-conversions) | planned | 3.3 |
| 5 | [Language server](#5-language-server) | planned | |
| 6 | [Tools in ctxlang](#6-tools-in-ctxlang) | planned | 3.1, 3.2 for 6.5 |

## Stages

### 1. Optionals and errors

1. **Unwrap in a `let`, by leaving.** `let p = e else { ... }` with a plain name: for `e: ?T`,
   shorthand for `let some{ value = p } = e else { ... }`.
2. **Errors' remaining gaps.**
   - A function whose result's set is inferred can't be a value of a function type, whose `!T`
     holds any error: that needs the thunk that widens a function value to also renumber its
     result.
   - Matching through a pointer to a `!T`.
3. **`@fmt` as a value** (FRICTION #1). A formatted diagnostic takes three lines, a builder, the
   `@fmt` and the view, about 190 times in ctxc, and no helper can hide them: no function takes
   a format and its arguments to pass on. Without a builder, `@fmt("...", args)` is a function
   that writes the text when called, as Rust's `format_args!` is a value any sink takes:
   ```
   error{ &c, at, msg = @fmt("no variant `{}` in {}", name, tstr{ c, t }) }

   fn error { mut c: Checker, at: source::Span, msg: utf8::Fmt(Heap) } {
       let mut b = message{ c }
       try! msg{ &b }
       report{ &c, at, text = utf8::view{ b } }
   }
   ```
   - It is a hidden fn per site, whose context is the arguments and `mut b`, and whose body is
     `return @fmt(&b, ...)`, bound with `_` (§4): no new IR or C. The two forms can't be
     confused, since a format is always a literal and a builder never is.
   - Its type, `&fn{ mut b: utf8::Builder(S) } -> !`, comes from the expected type. Without one
     (`let w = @fmt(...)`) it is an error, as with an untyped `null`.
   - The arguments are evaluated and copied at the `@fmt`, as a bind's are (§4).
   - The result stays `!`: it can run out of memory, and a hole that is a function may fail.
     The sink decides, as ctxc's `error` does with one `try!`.
   - A writer is what a hole already takes (§13), so writers nest: helpers that build a string
     only to put it in another (`binding_names`) return a writer instead.
   - std gets `type Fmt(S) = &fn{ mut b: Builder(S) } -> !` in `utf8`. An API that takes plain
     text keeps a `utf8::String` field, and adds one that takes a writer (`error` and `errorf`).
   - The bound record is leaked from `ctx_alloc`, as every `&fn`'s is (Open decisions), until
     records live in the frame.
   - It still writes to std's `utf8::Builder`. Any sink, as stage 4 wants, is a later design.

*Later, if wanted:* if patterns nest (a payload's fields, literal values), `_` comes in as a
wildcard inside a pattern (`os{ code = _ }`), and `else` stays the whole-arm default. Optional
chaining (`a?.b`) needs no lambdas, but nothing in FRICTION.md asks for it yet. `==` between a `?T`
and a `T` (FRICTION #8) would follow Swift: `T` widens to `?T`, two nulls are equal, and `!=` is
`==`'s negation, so `null != x` is true. `is` (spec §8) covers enums, and only three integer
comparisons in ctxc would use it; one of them (`d != null and d != NONE`) shows how `!=` would
mislead.

### 2. C interop

The goal is real programs over C libraries: OpenGL or Vulkan rendering, windowing, audio.

1. **proc over the layers.** `ctx_proc_run`, `ctx_proc_exe_path` and Windows' `ctx_proc_env`
   move into ctxlang. The runtime then keeps only what has to be C: startup, panics, the stack
   check, and small helpers. Float formatting and parsing (shortest round-trip text) may stay in
   C.
   - `proc.ctx`, shared: argv and env checks, whether an entry overrides an inherited one
     (case-insensitive on Windows), and the status-to-error mapping.
   - posix (`std/os/posix`): argv and env as `?c::String` arrays, `posix_spawnp` (which returns
     the error number itself), `waitpid` retried on EINTR, and the exit status decoded with bit
     operations, since `WIFEXITED` and the rest are macros; the encoding is the same on Linux
     and macOS. The environment to merge comes from `os::Proc`'s `environ`. The executable's
     path differs, so it goes in `sys`: `readlink("/proc/self/exe")` on Linux,
     `_NSGetExecutablePath` and `realpath` on macOS.
   - windows: `quote_arg` in ctxlang, UTF-8 to UTF-16 and back, the `GetEnvironmentStringsW`
     block walked with pointer arithmetic, `CreateProcessW` with `STARTUPINFOW` and
     `PROCESS_INFORMATION` as ctxlang structs, `_wgetenv`, `GetModuleFileNameW`. This also
     tests Windows' code paths in the driver.
   - The C code uses `malloc` and flushes stdout before the child starts. In ctxlang both show
     in the signatures: `run`, `env` and `exe_path` take an allocator, as `fs::list` does, and
     `run` takes `Io` for the flush. *To settle.*
2. **`const OS` in each layer**, so that `proc::os` and `build::os` stop calling `ctx_build_os`.
3. **Driver caching.** `ctxc run` compiles the runtime and the program again every time (about
   0.5 s).
4. **`#c::export{ name }`**, for a public symbol, over the callback thunk.
5. **Loading a library at run time**, where the capability means "it loaded".

*Later,* each waiting for a target that needs it:
- macOS on x86_64: its `readdir` returns the old `struct dirent` unless it is called as
  `readdir$INODE64`, so `sys::DIRENT_NAME` (21, arm64's) is wrong there. A layer is per OS, not
  per architecture, so this needs a way to choose by both.
- A build program naming a layer of its own for a platform std doesn't know
  (`build::platform{ &b, exe, dir }`), so that a port supplies `namespace os` without editing std.
- A target with no layer at all, where everything that takes no capability still works
  (freestanding). It also needs the runtime's startup and panics replaced.
- Threads. A `#c::callback` must be called on the thread that called into C, since the stack
  limit and the runtime's stdout buffer are global; threads would need a `_Thread_local` limit
  and an entry thunk.

*Done when:* a program opens a window and draws with OpenGL through a binding written in
ctxlang.

### 3. Metaprogramming

The aim is code generation (serializers, for example) and build logic written in ctxlang, as with
Zig's `build.zig` and Jai's `#run`, without macros and without making types compile-time values.
Capabilities already mark what is safe to run: code that needs no capability is deterministic and
hermetic by construction, so compile-time code needs no separate sandbox rules. And the compiler
is a ctxlang library, so reflection needs no builtins.

Generated code is written out as real `.ctx` files and compiled in a later step, never spliced
into the compile that is running. Errors in generated code point at files a person can open, and a
generator can't observe its own output.

1. **Generated files and cross-compiling.** `build::gen_file` writes a file under `build/gen/`
   that joins the program's file list. `build::os` is the host's for now.
   - **`build` and `main` return `!` or `!i32`.** Writing files and checking sources can fail, and
     a build program should pass that up with `try`, as Zig's `build.zig` does, not panic with
     `try!` or handle every failure where it happens. §19 gives `build` main's rules, so `main`
     gains it too, for small programs, tests and examples (Rust, Zig and Swift allow it). `ok`
     exits with its value, or 0 for a bare `!`. An error prints `error: ` and the error as `@fmt`
     prints it (`fs::other{ code = 5 }`) to stderr, and exits with 1. Printing the payload needs a
     small fixed buffer; a first version may print only the name, as `try!` does. Programs that
     report with context and pick their exit codes, as ctxc and the examples do, keep `-> i32`.
2. **Reflection: `build::check`.** Runs the front end on an executable's sources and gives the
   build program the checked declarations as data: structs, unions, fields, layouts and
   attributes. That data is the `Analysis`, read-only trees plus side tables, so no separate
   reflection format is needed.
3. **Compile-time consts.** A `const` initializer may call any function. A const has no context,
   so it holds no capability, and only effect-free code can run there. ctxc evaluates it with an
   interpreter over the IR, which is monomorphized, typed and laid out.
   - **When.** The checker runs in phases (declarations, const folding, bodies, error sets), and
     has no per-declaration `ensure`. A const that calls a function is evaluated after every body
     is checked and the sets are inferred, before lowering, the first time its value is needed.
     A const whose evaluation reaches itself is a cycle error.
   - **Array lengths and enum values** are needed during declarations, so they keep today's
     folding (`const_int`): a const that calls a function there is an error. Nothing uses a named
     const as an array length today; checking bodies on demand can lift this later.
   - **How.** A second `Lower`, separate from the program's so the emitted C doesn't change,
     lowers the initializer as a function without context, and what it reaches. The interpreter
     (`ctxc/eval.ctx`) runs it over memory as bytes, laid out by the IR's sizes and offsets, so
     `@cast`, extern unions, pointer arithmetic and std's allocators, which reinterpret `[]u8`
     as typed memory, behave as they do in C. A pointer is a region (static literal bytes, a stack
     frame, the heap) and an offset.
   - **Limits.** A panic (overflow, bounds, `@panic`, `try!`) is a compile error at the const with
     its message. So are running out of fuel (a step limit) and too deep a recursion. Calling an
     extern fn is an error: none can run while compiling. (The capability-less ones std has, float
     formatting and parsing, are ctxc's own runtime's, so a later version could call ctxc's.)
   - **The result** is read back by its type into the const's value. A `[]u8` or `c::String` must
     point into static literal bytes; any other pointer, or a function value, is an error.
   - The value is cached in the checker (`values`), so the language server doesn't re-run it on
     edits that don't touch its inputs.
   - **Two steps.** The first is done: the interpreter (`ctxc/eval.ctx`) and `ctxc interp FILE`,
     which runs a whole program's `main` in it, emulating the externs that writing to stdout and
     stderr reaches; the tests run every program both ways (Testing). Next, consts that call
     functions, on top of it: `eval::run` runs any function, and `failed` says why it stopped.
   - Uses: lookup tables, perfect-hash keyword maps, precomputed tables for parsers, and
     converting literals to library types (stage 4).

*Not planned:* generating declarations inside the compile that is running (Zig's `inline for`
over fields with types as values, or Jai's `#insert`). It needs lazy analysis or a fixed-point
loop in the checker, and generics would become compile-time values. Revisit only if 3.1–3.3 fall
short on real code.

*Done when:* a JSON generator in ctxlang derives `write` and `read` functions for
`#json::derive` structs, and `examples/json` uses them for a typed round trip.

### 4. Literal conversions

The compiler should know nothing of std: std is built from features any program has, and the
checker, lowering and runtime never name a std declaration. Today they do, most of all for
string literals. A literal where a `utf8::String` or a `c::String` is expected becomes that type,
so the checker looks both up by name (`text_decl`, `cstr_decl`), checks UTF-8 or the lack of a
NUL itself, and lowering builds their structs (`text_lit`). Commit `f53a93f` fixed a symptom: a
program's own `utf8` could shadow the one this lookup wanted.

A literal is only bytes. What text or a C string is, and how one is checked, is the library's to
say; the language gives it a way to receive literals. That way is open to any program, not just
std, and not just to a type's own namespace.

```
namespace utf8 {
    #convert
    fn literal { s: strlit } -> !String { return from{ bytes = s.bytes } }
}

namespace c {
    #convert
    fn literal { s: strlit } -> !String {
        let mut i: usize = 0
        while i < s.bytes.len {
            if s.bytes[i] == 0 { return has_nul{ at = i } }
            i = i + 1
        }
        return String{ ptr = s.bytes.ptr }       // the hidden zero ends it
    }
}

namespace regex {                                // a program's own type
    #convert
    fn literal { s: strlit } -> !Regex { return compile{ s.bytes } }
}

io::println{ &io, s = "hello" }                  // utf8::literal, run while compiling
let r: regex::Regex = "[a-z]+"                   // a bad pattern is a compile error
```

1. **The hidden zero.** A string literal's static bytes are followed by a 0 byte that isn't part
   of them: a `[]u8` view of `"abc"` has `len` 3, and `ptr[3]` is 0. The C backend already gives
   every view a C string literal, so this costs nothing; the change is that the spec promises it.
   Nobody writes `"abc\0"` for C.
2. **Literal types.** `strlit` is the type of a string literal: built in, lowercase and without a
   namespace, like `u8`. `s.bytes` is its bytes as a `[]u8`, with the hidden zero after them,
   even when empty. Only a literal makes one, so every `strlit` has that zero. `intlit` (a number
   literal, as its digits, for a big-integer type) and `arraylit` (an array literal's elements,
   for a list) follow the same pattern when something needs them; neither is designed yet.
3. **`#convert`.** An attribute the compiler declares, not std, so it has no namespace. It goes on
   a fn whose context is one read-only field of a literal type and whose result is a `T` or `!T`.
   The fn has no generic parameters. With only a literal field it can take no capability, so it
   can run at compile time. Any namespace may declare one, for any `T`.
4. **Where it applies.** A string literal where a `T` is expected (also inside `?T`), and
   `T` isn't `[]u8` or `[N]u8`, which the language gives literals itself, is the result of the
   conversion from `strlit` to `T`. "Expected" is what it is today: the places widening applies
   (§11, rule 1), a const's initializer, an `if` or `match` branch next to one of type `T`, and a
   call's `strlit` field, so `utf8::literal{ s = "hi" }` calls one directly. Only literals
   convert: no other value does, and conversions don't chain.
5. **It runs while compiling**, with 3.3's evaluator, so the program holds the finished value,
   and the same rule applies to the result: no pointers but ones to static data. An error result
   is a compile error at the literal, printed as `@fmt` prints an error:
   `string literal: utf8::invalid{ at = 3 }`.
6. **Two conversions to one `T`** are an error where a literal would use them, naming both, and
   not before: two libraries may both declare one, and a program that calls one directly is fine.

*What goes from the compiler:* `text_decl` and `cstr_decl` in literal checking (`str_lit`), the
const evaluator's string case and the `if`/`match` hint, and lowering's `text_lit`. The tests'
literal programs keep their output; the UTF-8 and NUL errors change wording to std's errors.

*Needs* 3.3. A stopgap that runs nothing, an attribute naming one of a fixed set of checks the
compiler knows (`utf8`, no NUL), would remove the names first, but it is a second design to
undo; the evaluator comes first.

*Still naming std after this,* each a later piece of the same goal:
- `@fmt` writes to a `utf8::Builder` through `utf8::push_*` functions found by name, fails with
  `alloc::out_of_memory`, which it names too, and a literal hole expects a `utf8::String`. The direction: `@fmt` receives what it writes with, as a hole
  already may (a function value writes it), rather than knowing std's builder. 1.3 moves that
  way: the sink of an `@fmt` value owns the builder.
- `c::String`'s C layout: a `?c::String` is a nullable pointer, and an extern fn passes it as a
  `const char *`.
- `c::symbol` and `c::callback` are attributes std declares and the compiler acts on. They move
  beside `#convert`, among the attributes the compiler declares itself.
- `main`'s `args` is checked against std's `Args`; it can be checked as `[][]u8`. Only `fn build`
  may take std's `Build`.
- The runtime fills `io`'s `Out`, a struct whose layout std defines (`ctxrt.c`, `out_buffer`).

*Considered and set aside:*
- `@from_literal`: `@` names a builtin call (`@fmt`, `@as`), and attributes are `#`.
- Only the type's own namespace declaring its conversion: a library can't then give literals to
  a type it doesn't own. Traits are the usual way to add to such a type, but ctxlang passes
  behaviour as values instead (`map::Map` takes its hash and equality), and a literal conversion
  is not a value a caller would pass.
- A naming convention (a fn called `literal` in the type's namespace): magic by name.
- No implicit conversion, with `utf8::lit{ "hello" }` at every use: general, but every literal
  is wrapped.
- Converting any value, not only literals: it would hide work, and failures, at run time.
- The user writes the zero (`"hello\0"`): easy to forget, and the language can promise it free.
- `literal` or `str` for the type: there will be one per literal kind, and `str` reads as the
  text type to use everywhere, which `utf8::String` is.

### 5. Language server

`ctxls`, written in ctxlang, speaks LSP (JSON-RPC over stdin and stdout) and answers from the
`Analysis` the front end produces. The JSON reader and writer grow out of `examples/json`.

The front end was built for this: `check{ files }` takes source text (so unsaved buffers work),
never exits or panics on bad input, recovers from errors in the lexer, parser and checker, keeps
comments on the side, and records its results in side tables by node id, so parsed trees stay
read-only and unchanged files (std in particular) needn't be reparsed. What's left is reading
those tables:

| Record | Serves |
|---|---|
| each name use → its declaration (the file and span of a local, field, variant, fn, type or namespace) | go to definition, references, rename, semantic tokens |
| each expression's type, and a local's type at each use (after narrowing, §8) | hover, inlay hints |
| each declaration: kind, name, span, signature text, and its namespace | document and workspace symbols, hover |
| scopes: each block's locals, with the span where each one is live | completion of names |
| the expected type at each `{` of a call or literal, and which fields a pun or `..` supplied | completion of field names, signature help, hover on `..` |

1. **Features, in order:** diagnostics on open and change (with debouncing), go to definition,
   hover (type and signature), document symbols, completion (names in scope, fields after `.`,
   context fields inside `{`), references, rename, workspace symbols, semantic tokens, signature
   help, inlay hints for inferred `let` types.
2. **What std needs:** `io::read` of an exact byte count from stdin, because a message body has
   no trailing newline and `read_line` won't do; and writing raw bytes to stdout without a
   newline.
3. **Doc comments,** for hover: their syntax is a separate spec decision.

Design notes:
- **Positions.** Spans are byte offsets; the server converts to whatever the client negotiated:
  UTF-8 if it accepts `positionEncoding`, UTF-16 otherwise.
- **Workspace.** A program is a directory of `.ctx` files plus std (§10). An open file joins the
  program in its directory. Buffers the editor holds replace the text on disk.
- **Speed.** On every edit the server re-lexes and reparses the files that changed and rechecks
  the whole program. Only if a profile says otherwise: skip unchanged function bodies, or check
  only up to the cursor for completion.
- **Robustness.** A panic kills the server, so the recovery test gates every release. A request
  whose analysis fails for an internal reason returns an LSP error and doesn't take the session
  down with it.

*Done when:* VS Code, with a minimal client extension, shows diagnostics while you type, and go to
definition, hover and completion work on `ctxc/` itself. The editor-query fixtures pass.

### 6. Tools in ctxlang

Python is left in development only: about 8,100 lines in `tests/` and `tools/`. ctxc and std have
none, and `ctxc run` and `exe` drive a build themselves. Steps 1–4 replace the Python and stand
alone; step 5 gives programs a test framework of their own. None blocks the other stages.

1. **Remove `tools/ctxc.py`.** `ctxc run` and `ctxc exe` do what it does. The examples' header
   comments, spec.md's list of examples and "Working on ctxc" name it, and move to `ctxc run`.
2. **`fixpoint.py` in ctxlang.** It builds ctxc with itself twice, compares the C, and with
   `--update` writes the three bootstraps: a few `proc::run` calls and file compares.
3. **Tests as files.** The 454 tests are programs in Python strings (`tests/test_ctxlang.py`).
   Each becomes a `.ctx` file, or a directory for a multi-file program, that states its
   expected output, exit code, panic or first error in a header comment, and a ctxlang runner
   builds, runs and checks them. Then ctxc, the recovery corpus and stage 5's editor-query
   fixtures all read the same files, and `tools/toolchain.py`'s harness (building ctxc from the
   bootstrap, caching by hash, mapping positions back) moves into the runner. Do this before
   stage 5.
4. **`corpus.py` and `recover.py` in ctxlang.** Both run many processes at once, and `proc::run`
   waits for its child, so this needs a way to start a process and wait later (`proc::spawn`
   and `wait`). With tests as files, the corpus is mostly the test directory itself.
5. **`#test` functions** for std, ctxc's internals and programs, next to the code they test. The
   compiler's own suite stays as files (6.3): a program can't catch its own compile error.
   ```
   #test
   fn reads_config { mut fs: Fs } -> ! {
       let text = try fs::read_all{ &fs, ... }
       @expect(text.len == 42)                 // fails with "text.len == 42: 17 == 42"
   }

   #test{ panics = "integer overflow" }
   fn add_overflows {} { _ = max_i32{} + 1 }
   ```
   - **A test's context is what it needs.** One without capabilities is deterministic by
     construction, so it can run in parallel, and with 3.3 while compiling. One that takes `Fs`
     says so, and the runner supplies it as `main`'s are supplied.
   - **No mocking framework.** Behaviour is already passed as values (capabilities with fields,
     `map::Map`'s hash): a test passes a fake.
   - **A test returns `!`,** so it can `try`; an error fails it, printed as `@fmt` prints one.
   - **`@expect(c)`**, a builtin: on failure it records the condition's text and, for a
     comparison, both sides as `@fmt` holes, and the test goes on. ctxlang has no macros or
     generic printing (FRICTION #6), so a library `assert_eq` couldn't show the values.
   - **Leaks.** A std counting allocator fails a test that doesn't free what it took, as Zig's
     `std.testing.allocator` does.
   - **No `cfg(test)`.** Lowering starts from `main`, so tests never reach a normal build.
   - **The compiler knows nothing of tests.** `#test` is std's attribute, and a build program
     finds the tests with `build::check` (3.2) and writes a runner `main` with `build::gen_file`
     (3.1). Only `@expect` is the compiler's. A test that expects a panic runs in its own
     process, which needs 6.4's `proc::spawn`.
   - *Needs* 3.1 and 3.2, and 6.4 for expected panics. It is a first real user of
     `build::check`, next to the JSON generator.
   - *Considered:* finding tests by name (Go's `TestXxx`) is magic by name; `test "name" { }`
     blocks (Zig) are syntax an attribute already gives; fixtures by parameter name (pytest) are
     hidden injection that capabilities make explicit; mocks that patch code at run time (Jest)
     don't fit a language that passes behaviour as values.

*Later, if wanted:* benchmarks (`#bench`, timed through a clock capability the runner supplies)
and fuzzing (`#fuzz` over a `[]u8` input), both built in as Go has them.

## Working on ctxc

```
cc -std=gnu11 -O1 -w -fwrapv -fno-optimize-sibling-calls -Ictxc/rt bootstrap/ctxc.linux.c ctxc/rt/ctxrt.c -lm -o ctxc
./ctxc run examples/wordcount.ctx -- spec.md             # a file
./ctxc run examples/json -- examples/json/sample.json    # a directory
./ctxc run examples/glfw                                 # a directory with a build program
./ctxc exe examples/list.ctx -o list
./ctxc interp examples/list.ctx                          # main in the interpreter, no C compiler
```

- On macOS the bootstrap is `bootstrap/ctxc.macos.c`, and on Windows `bootstrap/ctxc.windows.c`. ctxc finds std/ and ctxc/rt/ through
  CTX_HOME, or above its executable or the working directory, and builds in HOME/build/run.
- That ctxc is the bootstrap's; `tools/toolchain.py` builds the current source's into
  `build/ctxc` (about 7 s the first time, cached after).
- `python tools/ctxc.py PROGRAM --run [args...]` compiles and runs a program with it.
- `python -m unittest discover tests` runs all tests through the native ctxc. They pass on
  Windows (gcc), Linux (gcc) and macOS arm64 (Apple clang).
- Python is left in development only: `tests/` and `tools/`. Stage 6 moves them to ctxlang.
- Friction found while writing ctxc is logged in [FRICTION.md](FRICTION.md).

### Changing the language

ctxc's source may use only what the bootstrap's ctxc understands. A new feature lands in two
steps:

1. Add it to ctxc, without ctxc using it. The bootstrap compiles that source, and the result
   understands the feature.
2. Run `python tools/fixpoint.py --update` to refresh the bootstraps (`bootstrap/ctxc.*.c`, one
   per platform layer, all written from any machine). ctxc's source may now use it.

Removing a feature goes the other way round: stop using it, refresh the bootstraps, then remove
it. Refresh them whenever a change to ctxc lands, so a fresh checkout builds the current compiler
in one step; `fixpoint.py` says when one is out of date.

### Known gaps

- The front end is over its budget: checking and lowering ctxc takes about 215 ms natively,
  against 100 ms for the check alone. It hasn't been profiled.
- The C backend prints no `in fn` stack trace with a panic (see Open decisions).
- 20 corpus programs read temporary files that the test suite deletes once it's done.
  `tools/corpus.py` should copy those files into the case directory.
- The interpreter is the only second implementation, and it runs only programs that just print:
  the suite's programs that use files, processes, input, `mem::pages` or a C library are checked
  by their expected outputs alone.
- `ctxc build`, `ir` and `decls` need std's files listed on the command line; only `run` and
  `exe` find them.

## How ctxlang maps to C

C11 with GNU extensions (overflow builtins, empty structs, statement expressions), built with gcc
(MinGW on Windows), Apple clang on macOS, or `zig cc` (`CTX_CC=zig`). Flags: `-std=gnu11 -O1 -w
-fwrapv -fno-optimize-sibling-calls -fno-strict-aliasing`.

| ctxlang | C | Notes |
|---|---|---|
| `i8`…`u64`, `bool` | `int8_t`…`uint64_t`, `_Bool` | `usize` is fixed at 64 bits for now. |
| `+ - *` on integers | `__builtin_*_overflow` | Panics with `integer overflow`. |
| `/ %` on integers | guarded C `/ %` | Zero divisor panics. `MIN / -1` panics. `MIN % -1` is 0. Both round toward zero. |
| `f32` arithmetic | `float` | Needs `FLT_EVAL_METHOD == 0` (SSE). |
| `@as`, `@trunc`, `@wrap_*` | range check then cast; unsigned arithmetic then cast | |
| `[N]T` | `struct { T a[N]; }` | Wrapped so arrays copy, assign and return as values. |
| `[]T`, `s[i]`, `s[lo..hi]` | `struct { T *m_ptr; uint64_t m_len; }`; `ctx_idx`, `ctx_range` | Bounds checks panic. The runtime's C functions see it as `ctx_slice`. |
| struct | C struct, same field order | Checked with `_Static_assert` on `sizeof` and `offsetof`. |
| union, `?T` | `struct { uint32_t tag; union { … } p; }` | Tag at 0, payload at `align_up(4, payload align)`. `null` is tag 0. |
| `?*T`, `?*mut T` | `T*` | `null` is 0. IR type `nptr`. |
| `c::String`, `?c::String` | `struct { uint8_t *m_ptr; }`, and the same under a typedef | Passed to C by value, which 64-bit C ABIs pass and return as the pointer; a literal is `((uint8_t *)"...")`, NUL-terminated by C. `?c::String` is null when `m_ptr` is 0. |
| `extern union` | C `union` | Every field at offset 0. IR `(cunion ...)`. A literal zeroes the other bytes with `memset`. |
| `extern fn{C} -> R`, and its `?` | `R (*)(P...)`, capabilities dropped | IR type `cfn`, params in order; `null` is 0. A named extern fn as a value is `xN`; a `#c::callback` fn is `kK`, a C function calling `fN`. |
| enum | its base integer type | `match` becomes an if-else chain on the value (IR `switch`). |
| `Io`, `Fs`, `Mem` | empty struct | Size 0 with GNU C. |
| `capability Gl { f: extern fn{C} -> R, ... }` | struct of function pointers | `x.f{ ... }` calls the pointer; dropped from extern and `cfn` params, as other capabilities are. |
| `*T`, `q + n`, `q[i]` | `T*`, pointer arithmetic | Not checked. §12.7 calls a bad pointer UB. |
| `a[i]` on arrays | index with a bounds check | Panics, as the spec requires. |
| `fn{C} -> R` | pointer to a record whose first member is the code | Called with the record and the fields in name order. Conversion to a type with more fields wraps the value in an adapter. |
| `&fn{C} -> R` | a bind record from `ctx_alloc` | Never freed. |
| `defer` | copied to each exit | Innermost first. `return e` evaluates `e` into a temporary first. |
| const of array, struct or union type | `static const qvN = VALUE;` | The checker folds the value to literals; `[x; N]` is a GNU range designator. A scalar const is its value at each use. |
| `if`/`match` expressions | GNU statement expressions | A branch that leaves uses `return`, `break` or `continue`. |
| argument order | temporaries | C leaves argument evaluation order unspecified; ctxlang evaluates left to right. |
| `@panic`, runtime panics | `ctx_panic(file, line, col, msg)` | `file:line:col: panic: msg`, exit code 134. |
| stack overflow | check in each function prologue | Compares the frame address to a limit set at startup (16 MB, or `CTX_STACK`). Linked with a 256 MB stack on Windows and macOS; on Linux, raises `RLIMIT_STACK` to 256 MB and runs itself again. No sibling calls, so every call takes a frame. |

## Testing

- **The suite.** `python -m unittest discover tests` runs every program through the native ctxc
  and cc (`tools/toolchain.py`), and checks its output, exit code, panic or first error.
- **The interpreter.** `run_sources` also runs each program with `ctxc interp` and requires the
  same stdout, stderr, exit code and panic; one that calls an extern fn the interpreter doesn't
  emulate, or recurses too deep, is skipped. `CTX_DIFF=0` turns it off (it adds about a quarter
  to the suite's time); `tools/interp_diff.py` counts matches and skips by reason.
- **Errors.** The compile-error tests match on a message fragment, or the message and position
  exactly, so message text is part of the interface. The tests see the first diagnostic; ctxc
  may report more.
- **Fixpoint** (`tools/fixpoint.py`). ctxc built by itself must write the same C twice, and the
  bootstrap must be current.
- **Corpus.** `tools/corpus.py` records every program the tests run, with its output, exit code,
  panic or error, plus `std/` and `examples/`, into `build/corpus`, for the recovery test.
- **C's undefined behaviour.** `invalid memory access` is undefined behaviour in C, not a panic.
- **Recovery** (`tools/recover.py`). Damage every file in the corpus: cut it at each token
  boundary, and delete or duplicate single tokens. Run the front end on every result, inside
  ctxc (`ctxc recover`), in parallel chunks. It must not panic, must keep under the diagnostic
  cap, and must build a well-formed tree: ids used once, and every span inside its parent's. A
  cut inside a declaration that ends in `}` must report an error, and a cut must still produce
  symbols for the declarations before it. Other damage can leave valid code, so it needn't report
  anything. This is the test that guards editor use.
- **Editor queries** (stage 5). Fixture files mark positions (`/*^def*/`, `/*^hover*/`) and state
  the expected answer, which covers the semantic model without a client.
- **Float text.** `f64_digits` must copy Python's `repr` exactly: shortest round-trip digits,
  exponent form below `1e-4` and from `1e16`, and a `.0` suffix.

## Open decisions

- **Panic stack traces.** Printing the function frames with each panic needs a shadow stack in C,
  which costs time on every call. *Recommendation:* a debug flag, off by default. **Deferred.**
- **Where bound-function records live.** Leaked from `ctx_alloc` for now. §6 already keeps an
  `&fn` from outliving the frame that made it (it can't be returned, stored in a field, or put
  in a `mut` field), so every record could live in that frame; with 1.3 a compiler reporting
  thousands of diagnostics leaks one record each until then. *Recommendation:* move them to
  the frame, as its own change in emit_c's `bind`.

## Risks

- **One implementation.** With ctxi gone, a checker bug that the tests don't state goes
  unnoticed. Mitigation: a test for every language change, with its expected output or error.
- **Checker subtlety.** Literal inference that spans a whole function body, exclusivity and escape
  analysis have many edge cases. Mitigation: error-fragment tests.
- **Language friction.** ctxc pushes on method sugar (Q4), and imports and files as namespaces
  (Q5, Q6). Each point of friction goes in [FRICTION.md](FRICTION.md) as evidence for these
  questions.
