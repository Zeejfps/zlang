# ctxc internals

`ctxc` is a self-hosting compiler written in ctxlang that emits C. A fresh checkout builds it from
its platform's bootstrap, `bootstrap/ctxc.linux.c`, `ctxc.macos.c` or `ctxc.windows.c`, with
nothing but a C compiler.

This file is the reference: how to work on ctxc, how ctxlang maps to C, how it is tested, and the
design decisions behind them. What is left to do is in [todo/](todo), a file per area. The old plan, with the
history of finished stages, is `PLAN.md` in git history (its last version is at the commit that
removed it; the stages 0–12 version is at `f53a93f`). ctxi, the Python interpreter ctxc replaced,
is at `8436f4d`.

## Working on ctxc

```
cc -std=gnu11 -O1 -w -fwrapv -fno-optimize-sibling-calls -Ictxc/rt bootstrap/ctxc.linux.c ctxc/rt/ctxrt.c ctxc/rt/ctxfloat.c ctxc/rt/ctxthread.c -lm -lpthread -o ctxc0
./ctxc0 run examples/wordcount.ctx -- docs/spec.md       # a file
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
- ctxc takes `Threads`: the front end lexes and parses a program's files on tasks, in chunks of
  about equal bytes with an arena each, and adds each file's diagnostics in the files' order
  (main.ctx, `parse_files`). The rest of a compile runs on one thread.
- ctxc0 is the bootstrap's. `./ctxc0 exe ctxc -o ctxc1` builds the current source's with it
  (about 3 s), for `./ctxc1 run`. The suite's runner builds its own for the cases, into
  `build/suite/ctxc` (cached after the first time).
- `ctxc0 run tools/suite` runs every case through ctxc for the current source
  ([tests/README.md](../tests/README.md)).
- Python is left in `tools/recover.py` alone, with the part of `tools/toolchain.py` that builds
  ctxc for it. Moving it to ctxlang is in [todo/tools.md](todo/tools.md).
- Friction found while writing ctxc, and the KOTOR port, is logged in [friction.md](todo/friction.md).

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
| `cstr`, `?cstr` | `uint8_t *` | A pointer: types::Type's `ptr` with `c_string`, so IR and C see a `*u8`, and `?cstr` is null as 0. A literal's is `((uint8_t *)"...")`, whose NUL is the hidden zero. |
| `extern union` | C `union` | Every field at offset 0. IR `(cunion ...)`. A literal zeroes the other bytes with `memset`. |
| `extern fn{C} -> R`, and its `?` | `R (*)(P...)`, capabilities dropped | IR type `cfn`, params in order; `null` is 0. A named extern fn as a value is `xN`; a `#c_callback` fn is `kK`, a C function calling `fN`. A `#c_export` fn's `kK` is never static and has the exported symbol as its assembler name. |
| enum | its base integer type | `match` becomes an if-else chain on the value (IR `switch`), as a `match` on an integer does: a case lists values and ranges, `lo <= v && v <= hi`. |
| `Io`, `Fs`, `Mem` | empty struct | Size 0 with GNU C. |
| `#c_link` on a capability (spec §18, Extern functions, rule 11) | linker flags after the objects | Lowering lists each reached capability's libraries in the IR's `(link "LIB" ARCHIVE FRAMEWORK ["DIR" ...])` (lower.ctx, `reach_links`): when it first queues an extern fn that takes the capability, or meets one of its C variables, and those of the capabilities it includes. The driver turns them into `-lLIB`, `-framework LIB` or an archive's absolute path (drive.ctx, `library_flags`), placed before the build program's flags. `ctxc build OUT.c` starts its C with a line `// link: FLAG` for each, which the suite's runner passes to the C compiler as it links. |
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
| a start's `run` (spec §15, Tasks) | a bind's record with its size and the name of the fn it calls after the code, `ctx_task_rec` | IR `(tbind ...)` (lower.ctx, `task_record`); `@record_size` reads the size, `@record_copy` copies the record (`ctx_rec_copy`) and gives an entry thunk per result type (lower.ctx, `entering`), and `rt::task_name` names the task for a panic's report. |
| stack overflow | check in each function prologue | `CTX_STACK_CHECK()`, before the function's frame of the call path, so that the panic's path is its caller's, without a `#stack_limit` static none: compares the frame address to the `#stack_limit` static, whose storage is the runtime's (`CTX_STACK_LIMIT`: a global, or in a threaded program the calling thread's TLS slot), which std's start sets (16 MB below its frame, or `CTX_STACK`) and `ctx_on_panic` sets to 0 before the panic fn runs; 0 checks nothing. Linked with a 256 MB stack on Windows and macOS; on Linux, std raises `RLIMIT_STACK` to 256 MB and runs itself again (std/os/linux). No sibling calls, so every call takes a frame. |

## Testing

- **The suite.** `ctxc run tools/suite` runs every case under `tests/cases` through ctxc for the
  current source and cc, and checks all it states: output, exit code, panic, every error
  ([tests/README.md](../tests/README.md)).
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
- **Editor queries** (the language server, [todo/lsp.md](todo/lsp.md); not built yet). Fixture files mark positions (`/*^def*/`, `/*^hover*/`) and state
  the expected answer, which covers the semantic model without a client.
- **Float text.** `f64_digits` must copy Python's `repr` exactly: shortest round-trip digits,
  exponent form below `1e-4` and from `1e16`, and a `.0` suffix; `f32_digits` is the same over
  an f32's own digits (spec §13, Formatting, rule 9).

## Tasks: the Threaded backend

The language's side is spec §15, Tasks; the API is std/task.ctx. What isn't built (the Evented
backend, and open questions) is in [threads.md](todo/threads.md). This section is how the built backend
behaves, and why.

### Capabilities

`Io`, `Fs`, `Proc` (through `Io`) and `Threads` include `task::Cancel`, whose `#thread_local` statics
are `current`, the running task's slot, and `deadline`, the calling thread's deadline (Deadlines,
below), and so do `Net` (net.md) and `Stop`. `Threads` is
`{ ..os::Threads, ..Mem, ..task::State, ..task::Cancel }`: permission to run tasks, with the
backend's state, and `Mem` because the table lives in pages. Each is a capability without fields, so
`main` receives them. Everything a capability std hands out reaches is safe from many threads at
once: per-thread (`io`'s output buffer), behind a lock, or atomic. Only namespace `task` reads
`current` and `deadline`; the platform's layers call `task::check`, `get_stop_error`, `can_stop`,
`get_time_left`, `get_cancel_object`, `begin_synchronous` and `end_synchronous`, passing the
capability they hold, and give `task` its clock, `os::read_deadline_clock`. `proc`'s layer functions take `os::Proc`, which
doesn't include `Io`, so `os::pipe_read`, `pipe_write`, `wait` and `wait_for` take a
`mut cancel: task::Cancel`, passed as `cancel = &proc`; `net`'s blocking layer functions take
`os::Net` and one too, passed as `cancel = &net`, and `os::stop_wait` takes `os::Stop` and one, passed
as `cancel = &stop`.

### Cancellation

Each task has a flag and a cancel object, made with its slot and reset when the slot
is reused. `cancel`, `cancel_all` and a handle's scope ending set the flag and signal the object. A
task that is cancelled isn't stopped: its blocking calls fail, so the code it runs returns through its
usual error paths, `defer`s and all. `cancel` then waits for the task to end, which a call that can't
be interrupted (below) delays: a deadline is a request to stop at that time, not a bound on when the
task has stopped.

**Every blocking call of std's checks the flag before it blocks** (`task::check`) and fails with
`task::cancelled`; `thread::sleep` returns early instead, and `io::read`, which has no error, returns
0 as at the end of its input. Calls that may block for long also wait on the cancel object while
they block:

| Call | Windows | Linux | macOS |
|---|---|---|---|
| `proc::read`, `write` (std's child pipes) | overlapped: `WaitForMultipleObjects` on the operation's event and the cancel event; cancelled, `CancelIoEx(handle, &its_overlapped)` cancels this operation only, then waits for it to complete before its buffer is let go | `poll` on the pipe and the eventfd; this program's ends of child pipes are `O_NONBLOCK` | as Linux, with the cancel pipe |
| `proc::wait`, `wait_for` | `WaitForMultipleObjects` on the child's handle and the cancel event | `poll` on a `pidfd_open` descriptor (Linux 5.3) and the eventfd, then `waitpid` | `kevent` with `EVFILT_PROC`/`NOTE_EXIT` and the cancel pipe, then `waitpid` |
| `io::read` (standard input) | a console: wait on the input handle and the cancel event, then `PeekConsoleInputW`; events that aren't key presses are read and dropped and the wait goes on; on a key press the read begins, and waits for its line uninterruptibly. An inherited pipe: `begin_synchronous`, `_read`, `end_synchronous` (below). A file: checked before only | `poll` on fd 0 and the eventfd, then `read` (fd 0 stays blocking: it is shared with other programs) | as Linux |
| `thread::sleep` | `WaitForSingleObject` on the cancel event, with the time | `poll` on the eventfd, with the time | as Linux |
| `net`'s | overlapped, as pipes | `poll`, as pipes | as Linux |
| `stop::wait`, `wait_for` | `WaitForMultipleObjects` on stop's event and the cancel event | `poll` on stop's eventfd and the task's | `poll` on stop's pipe and the task's |

**Checked before only**, by decision, each with its reason, for a deadline too: `fs`'s calls (regular files, and
metadata: `open`, `list`, `remove`, renames), since disk IO can't be waited on with poll or kqueue
and Windows doesn't promise to cancel file system calls (`MoveFileEx` among them), and they finish
in disk time; reading standard input that is a file, for the same reason; name lookup on POSIX, since
`getaddrinfo` has no cancellation and `getaddrinfo_a` is glibc's alone (net.md); `mutex::lock`,
`condition::wait` and calls into C, which aren't IO and wait on what the program itself holds.

**Windows' synchronous reads** (standard input from an inherited anonymous pipe, which can't be
overlapped): `begin_synchronous` checks the flag and marks the slot "in a synchronous call", under the
slot's lock; `end_synchronous` clears it, under the lock. `cancel`, holding the lock, calls
`CancelSynchronousIo` on the worker's thread while the mark is set, and again every millisecond until
it is cleared. A call not yet entered gets `ERROR_NOT_FOUND`, and the next try reaches it; the worker
can't clear the mark and start another call while `cancel` holds the lock, so a late cancel can't
reach a later call.

**An operation that completes returns its result**, even when its task was cancelled meanwhile; the
next blocking call sees the flag. A `write` cancelled after some of its bytes went fails with
`cancelled`, and how many went is unknown: the stream's state is unknown, so the program closes it.

**Cancellation follows the scopes down.** A task that waits (`wait`, `wait_for`, `wait_all`) when it
is cancelled, or is cancelled while it waits, cancels what it waits for, then still waits for it to
end; `wait_for` then waits to the end and returns true. A cancelled task that returns ends its own
handles' scopes, which cancel their tasks (spec §15, Tasks, rule 6). So cancelling a task reaches every task
it started, and a task never ends before the tasks it started. How a waiting task is woken: a waiter
records in its own slot what it waits on, under the table's mutex; `cancel` sets the flag under the
same mutex and broadcasts the condition the waiter waits on. The waiter checks the flag and the end
under that mutex before every wait, so neither can be missed.

`check_cancelled` is for loops that compute without blocking.

### Deadlines

A deadline is cancellation at a time: the calls a function makes stop when it passes, as a
cancel stops them, without a second task.

```
let response = task::run_within{ cancel = &net, nanoseconds = 5000000000, run = fetch{ &net, request = &request, _ } }
```

**What it is.** `run_within` sets the calling thread's `deadline` (`Cancel`'s second
`#thread_local` static, a time on `os::read_deadline_clock`'s monotonic clock, 0 for none) to
`nanoseconds` from now, or keeps the outer one if that is earlier, runs `run`, and puts the outer
one back when `run` returns, by a `defer`. It is the calling thread's, not a task's: main's calls
have one as a task's do, and a program without `Threads` can bound a connect or a receive. A
worker's is 0 when it begins a task, so a task `run` starts concurrently doesn't run under its
starter's; a task run at once is part of its starter (spec §17, `task`), and does.

**What it stops.** Every call that a cancel stops, the same way, failing with
`task::deadline_passed` instead of `cancelled`, `io::read` returning 0 and `thread::sleep`
returning at the deadline: `check` fails with `cancelled` if the task was asked to stop and
otherwise with `deadline_passed` once the deadline has passed, so a call made after it fails at
once, before it blocks, and each wait that the table above has on the cancel object waits no
longer than the deadline. `fs`'s calls and the other calls checked before only are checked
before only for a deadline too, for the same reasons, and so are Windows' synchronous reads of an
inherited pipe: a cancel interrupts one from the thread that cancels, and a deadline has no
other thread there when it passes. A wait for a task (`wait`, `wait_for`, `wait_all`,
`wait_all_for`) that is still waiting when its waiter's deadline passes cancels what it waits
for and waits to the end, as a waiter asked to stop does: its result is the task's, usually
`cancelled`, since those waits have no error of their own.

| Wait | Windows | Linux | macOS |
|---|---|---|---|
| the clock | QueryPerformanceCounter over its frequency, as std's clock reads it | `clock_gettime(CLOCK_MONOTONIC)`, plus 1 so it is never 0 | as Linux |
| a call's wait | `await_handle`: `WaitForMultipleObjects` on the operation's handle and, in a task, the cancel event, for the time left in milliseconds, rounded up (INFINITE without a deadline); a wait that times out asks `check`, and waits again if Windows woke it early | `poll` with the time left in milliseconds, rounded up (-1 without one); a poll that ends with nothing asks `check` | as Linux |
| a child's wait | `await_handle` on the child's handle | `sys::await_exit` (pidfd and `poll`) for the time left, again until `check` fails | `sys::await_exit` (`kevent`) for the time left |
| `thread::sleep` | the cancel event, or `Sleep`, for the lesser of its time and the time left | `poll` on the eventfd, or `nanosleep`, for the lesser | as Linux |
| a task's wait | `condition::wait_for` until the deadline, then the waiter asks the task to stop | the same | the same |

**Stopped mid-operation.** A call that stopped waits as a cancelled one does: on Windows it
cancels its operation alone (CancelIoEx) and waits for it to finish before its buffer is let go,
and an operation that completed meanwhile returns its result. The error is `get_stop_error`'s:
`cancelled` if the task was asked to stop, else `deadline_passed`.

**A cancel and a deadline at once.** The cancel wins: the flag is checked first, so a task that
was asked to stop fails with `cancelled` whether or not its deadline has passed, and the program
leaves through the task's usual error paths.

**It sticks while it is set, and only then.** A deadline that has passed fails every call under
it at once, as a cancel's flag does, so a loop of calls ends at the first that sees it. Once
`run_within` returns, nothing of it is left: the outer deadline, or none, holds again.

**The interpreter** has no clock (std's clock stops the run there), and its `thread::sleep`
returns at once: its deadlines' clock stands still at 1, so a deadline of 0 has passed and any
other never passes, which is the same each run.

**What it costs.** Without a deadline, `check` reads `deadline` and branches: one load, beside
the flag's. Under one, each blocking call reads the clock (QueryPerformanceCounter, or
`clock_gettime` through the vDSO) once to check and once for the time left.

### How std's IO takes part

| Capability | Calls that block | With the Threaded backend |
|---|---|---|
| `Fs` | `open`, `read`, `write`, `read_all`, `list`, ... | block the worker; checked before (Cancellation) |
| `Io` | `read` (standard input), `flush` and writes that fill the buffer | block the worker. Each worker has its own output buffer (it is `#thread_local`), which it writes out when a task ends and before the end is published, ignoring the flag, so a cancelled task's output isn't lost; output that can't be written blocks it, as it would block the program without tasks. A task run at once shares its starter's buffer |
| `Proc` | `read`, `write` (pipes), `wait`, `wait_for`, `run` | block the worker. A cancelled `wait` or `wait_for` leaves the `Child` as it was: not released, its pipes open, to be waited on or killed. A cancelled `run`, which owns its child, kills it, waits for it uninterruptibly (a killed child ends at once), and fails with `cancelled` |
| `Threads` | `sleep` | waits on the cancel object, and no longer than a deadline |
| `Net` | connect, accept, send, receive, name lookup | block the worker |
| `Stop` | `wait`, `wait_for` | block the worker, and wait on the cancel object (Asked to stop, below) |

`Net` and HTTP are designed in their own documents (net.md, http.md), with TLS: they are a protocol
and a library, not concurrency. What this design fixes for them: blocking calls, `..task::Cancel` in
`Net`, `cancelled` and `deadline_passed` among their errors, and the table's row above. Every
blocking call in the table that a cancel stops, a deadline stops (Deadlines).

std's allocators are one thread's at a time: tasks that allocate each have their own arena, from
pages of their own or from a buffer their starter gives them, or share one behind a mutex.

### The backend

What `task::State` holds and does, all of it std over the platform layer's threads:

What `task::State` holds and does, all of it std over the platform layer's threads:

- **The table.** Slots in pages from `mem::pages`, which grow as tasks start and are reused once their
  task has ended and been waited on, under one mutex. A slot holds the task's entry and record, the
  address of its result (its `Task`'s) or its group, the flag and the cancel object, what the task
  blocks on or waits on, its worker, and its state: running, ended. A slot's generation guards
  against a handle that names a reused slot.
- **The record.** A start copies the bind's record into memory the slot owns (spec §15, Tasks, rule 5),
  from free lists by size under the table's mutex, and frees it when the task ends. The bind's own
  record, in the starter's frame, is dead once the start returns, so a loop that starts a task per
  iteration (a server) keeps no record per task in its frame.
- **Workers.** Threads that run one task at a time. `start` takes an idle worker, or starts one while
  fewer than the limit are busy; otherwise, or when the operating system refuses a thread or the
  table can't grow, it runs the task at once. `start_concurrent` and `start_blocking` take an idle
  worker or start one whatever the limit, and fail with `out_of_resources` only when the operating
  system refuses a thread or the table can't grow. A worker idle for 10 seconds ends.
- **The limit** is soft and applies to `start` only: 64 busy workers, since tasks that do IO spend
  their time blocked and the processors' count would be too few. `set_limit` takes the table's mutex
  and applies to the next `start`; lowering it stops no worker. 0 makes `start` always run at once.
- **No queue.** A task either has a worker or has run. Nothing waits for a free worker.
- **Stacks.** Workers have 8 MiB by default, reserved and committed as used, with headroom past it for
  the stack check to land in (a quarter of it, at least 1 MiB).
  `set_stack` applies to workers started after it; an idle worker whose stack is smaller than
  the setting ends instead of taking a task. (Stack bounds per task fn, which would size a worker to its task, are part of the Evented
  backend: threads.md.)
- **A panic** in a task ends the program, as on any thread, reported as `panic in task NAME:`, NAME
  being the task fn's.

### The interpreter

`ctxc interp` runs `start`'s tasks at once, which `start` allows, and `wait` and its kin return at
once. `start_concurrent`, `start_blocking` and their `_in` forms stop the run as not supported by
interp: it runs one thread, so it can't keep their promise. Files, standard input, other programs and the
network are already not supported there, so what the interpreter runs of tasks is code that computes and
prints; it detects no deadlock beyond what it already stops on (a mutex another thread holds).

### What a program without tasks pays

A program that doesn't take `Threads` starts no worker and links nothing of the backend. Its blocking
calls check `task::Cancel`'s `current` and `deadline`, which stay 0 unless it puts a deadline on
them: plain globals in a program that isn't threaded (spec §15, Entry point, rule 8),
thread-locals in one that is. Two loads and a branch per blocking call. A function with a task handle pays for its scope's end only where the handle might
still hold a task.

### Decisions

1. **A task's inputs are a bind's.** The bind is ctxlang's deferred call: it copies read-only
   arguments and holds `mut` places when it runs (spec §4), and the escape check already knows what it
   points into. A task gets its data, capabilities included, as any call does, checked the same way.
   Considered and rejected: a `*mut T` (unchecked); a work queue as a capability (a capability is
   permission, not data; it holds no state of its own; it goes one way, and a one-shot task becomes a
   queue of one); a generated id per `#task` fn with an argument literal typed by it (the fn's name is
   already its static id and the bind already its typed arguments; it would need a type that depends
   on a value).
2. **Granular capabilities**, not one `Io` for everything as Zig has: `Threads` is permission to run
   concurrently, and `Fs`, `Io`, `Proc` and `Net` stay permissions for what they touch. They share the
   backend's state by including `task::Cancel`, which costs no space and changes no public signature.
3. **No keywords, no colour.** `start` and `wait` are std functions taking `Threads`; a function that
   blocks is the same function in a task or not.
4. **Structured, with no detach.** Every task ends within its handle's scope, which is what lets it
   borrow its starter's locals; leaving a scope without waiting cancels, as Swift's `async let` does,
   so the only implicit thing is cleanup and a scope that wants a result says `wait`. Considered and
   rejected: linear handles that must be waited on exactly once, which fight early returns and need
   the same implicit end anyway, and add a kind of type generics, arrays and control flow must learn.
5. **The handle holds the result**, in the starter's frame, so the backend's table needs no room for
   results of every type. It is never copied, so it doesn't move while the task writes into it.
6. **Capabilities are shared, data is exclusive.** Tasks may share capabilities, which are permission;
   std makes what they reach safe from many threads. Places follow exclusivity over the task's life.
   What a library can't do from another thread is the capability's to declare (`#thread_bound`).
7. **The type marks what may run elsewhere, not the fn.** A task is a bind written into a
   `&thread fn` (spec §5), checked there for thread-bound capabilities, so any fn can be a task's
   entry and a library fn needs no task fn of the program's around it. The entries are still a closed
   set, each start's bind names its fn, so stack bounds per task stay possible. This was `#task` on
   the fn, and `#starts_task` on std's starts, until loans and lent function values were general
   (spec §15, Tasks).
8. **`start` returns no error**, and runs the task at once when it can't run it concurrently; only
   `start_concurrent` and `start_blocking` promise concurrency, and may fail. So most code runs on any
   backend and in the interpreter, and code that needs concurrency says so.
9. **Cancellation fails blocking calls** rather than stopping a task, so a task always leaves through
   its own error paths; a cancelled wait cancels what it waits for and a task's ending scopes cancel
   what it started, so cancellation follows tasks down. Calls that can't be interrupted are listed,
   each with its reason, rather than promised.
10. **The backend is picked per executable when it is built**, as the platform's layer is. `Threads`
   must stay a capability without fields, since `main` receives it, so it can't hold the function
   fields a choice at run time would need; and the blocking calls that would dispatch take `Fs`,
   `Io` and `Proc`, not `Threads`. A test build may pick a backend that simulates IO and time.
11. **No signals for cancellation on POSIX.** A cancel object per slot, waited on with the operation,
   interrupts every call that can be waited on; a signal would add a reserved signal, an
   async-signal-safe handler, and a re-send protocol for no call that the cancel object doesn't
   already reach.
12. **A deadline is the calling thread's, set for a call's extent** (`task::run_within`), and every
   call a cancel stops observes it: their waits are bounded by it as they already wait on the
   cancel object, so a deadline is cancellation at a time, as Decision 9 has it, without a task.
   It was a task cancelled at the time (`start_concurrent`, `wait_for`, `cancel`), which held a
   second thread for every waiting call: two threads per idle kept-alive connection in a server,
   and 25 to 50 µs per request (serve/PLAN.md, Findings 2). Considered and rejected: a deadline
   per socket or a timeout per call (net.md, Timeouts), which covers one kind of call and not the
   others; a deadline that `set` and `clear` change, which a missed `clear` leaves on calls it
   wasn't meant for, where a call's extent restores it on every path; a deadline per task, which
   main's thread wouldn't have, and which a concurrent task would inherit, though structured
   tasks already end with their starter's waits.
13. **A deadline fails calls with its own error, `deadline_passed`**, not `cancelled`: a caller
   tells its own deadline from a request to stop (a server's head deadline closes a connection,
   a stop cancels the server), and neither is the system's `net::timed_out`. A cancel wins when
   both hold, since it stops the whole task while a deadline bounds a part of it. Rejected: a
   passed deadline that sets the task's flag, which would make it stick past the call it was for.

### Decisions made building it

What the Threaded backend's build settled, where this document left room:

1. **`task::Cancel`'s `current` is the running task's slot**, `?*mut Slot`, not a number: slots live
   in pages that are never freed, so the pointer stays valid, and `check` is one load of its flag.
2. **Capabilities never conflict in a call** (spec §3.1, rule 6), not only at a start: one never
   changes (spec §15, rule 8), so `os::pipe_read{ &proc, cancel = &proc, ... }` passes one twice.
3. **The namespace that declares a handle type implements it**: std's `task` keeps pointers to
   groups and copies results, so the handle rules (spec §15, Tasks, rule 4) don't apply inside it.
4. **A handle that is an array's element ends its loan only with its scope**: which element a wait
   names isn't known to the compiler. Waiting on `loads[i]` doesn't free what that task borrowed;
   the array's scope does.
5. **A wait or cancel on a handle zero on every path, and a start into one that holds a task on
   every path, are compile errors**; on some paths only, they panic at run time. A loop forgets
   what it knows of a handle declared before it.
6. **A defer's body is checked against the loans live where it is written**: it may run at an early
   exit while they still are.
7. **A bind written as a start's `run` has its size and the name of the fn it calls in its record**, after
   its code: `@record_size` reads the size, and a worker names the task in a panic's report
   (`panic in task NAME:`) from the copy (`rt::task_name`).
8. **The interpreter refuses `start_concurrent`** through the platform layer: `os::CONCURRENT` is
   false there, and `os::concurrency_unsupported` stops the run.
9. **On Linux a child started with `die_with_parent` from a task ends with the worker's thread**
   (`PR_SET_PDEATHSIG`), which may end 10 seconds after the task, when the worker has waited for
   another in vain.
10. **KOTOR's mixer shares its device through a pointer** (spec §3.1, rule 6), as the thread did: the game
   reads `pumping` and `underruns` while it runs, so the device can't be the task's alone.

## Asked to stop: std's stop

The API is spec §17, `stop`, and std/stop.ctx; the layers' halves are std/os/windows/os.ctx,
std/os/posix/os.ctx with std/os/linux/sys.ctx and std/os/macos/sys.ctx, and std/os/interp/os.ctx.
This section is how the console's and the system's requests reach a program, and why it is built so.

### How it works

The layer keeps three things in `os::Stop`'s statics: a once-guard, what the program was asked (0
until then, then `stop::INTERRUPT` or `TERMINATE`, set once with a compare and exchange), and an
object that is signalled once it has been asked and stays signalled. The first `stop::wait`,
`wait_for` or `ask` makes the object and installs a handler, behind the guard as Winsock's start is.
The handler and `ask` both record: the first to swap 0 for a reason signals the object; any later
request isn't recorded, and ends the program. A wait waits on the object and, in a task, on the
task's cancel object (Cancellation, above), and returns the recorded reason. Nothing ever reads or
resets the object, so every wait after the first request returns at once.

| | Windows | Linux | macOS |
|---|---|---|---|
| handler | `SetConsoleCtrlHandler`: Ctrl-C and Ctrl-Break `interrupt`, the window closing and shutdown `terminate` | `sigaction` for SIGINT (`interrupt`) and SIGTERM (`terminate`), `SA_RESTART`, both blocked while it runs | as Linux, with macOS's `struct sigaction` |
| object | a manual-reset event, `SetEvent` | an eventfd, written | a pipe, its write end non-blocking, written |
| a later request | the handler returns FALSE: Windows' own handler ends the program, exit code 0xC000013A | the first request put both signals back to `SIG_DFL`, so the signal's default action ends it; one that reaches the handler meanwhile puts them back itself and raises its signal again, which the handler's mask holds until it returns | as Linux |
| waits | `WaitForMultipleObjects` on the event and the cancel event | `poll` on the eventfd and the cancel eventfd, again after `EINTR` | `poll` on the pipe's read end and the cancel pipe |

**What the handler may do.** On Windows it runs on a thread Windows starts for the event: it sets an
atomic and an event, which any thread may. On Linux and macOS it runs on whichever thread the
signal lands on, between any two instructions: it uses only atomics and async-signal-safe calls
(`sigaction`, `write`, `raise`) and keeps `errno` around them. Either way it is a
`#c_callback{ any_thread = true }` (spec §18, Callbacks, rule 6): only the install reaches it, so only
a program that calls `stop`'s functions is threaded by it (spec §15, Entry point, rule 8), and one
that doesn't installs nothing, links nothing more, and has Ctrl-C end it as before. The callback
holds no capability, and makes the `os::Stop` it needs from nothing, as `task::begin` does: a
capability without fields is no bytes (friction.md, 41).

**The console's window closing.** For `CTRL_CLOSE_EVENT` and `CTRL_SHUTDOWN_EVENT`, Windows ends the
process as soon as the handler returns, whatever it returns, or about 5 seconds after the event if
it doesn't. So the handler records `terminate` and then sleeps until the process ends: the program
has those seconds for its graceful stop, and ends when `main` returns or when Windows ends it. That
is why `Reason` tells `terminate` from `interrupt`: a program picks a grace period that fits.

**The interpreter** installs no handler: Ctrl-C ends `ctxc interp`, and the run with it, as it ends a
program without `stop`. Its `Stop` keeps only what `ask` asked, which its waits return; a wait with
a time returns at once, as its `thread::sleep` does, and a wait for as long as it takes that nothing
asked would wait for a request that can't come, so it stops the run, as not supported by interp.

### Decisions

1. **A wait a task can be cancelled out of, and a wait with a time**, as proc's `wait` and
   `wait_for` are, rather than a flag to read or a callback of the program's. The program's shape
   is "serve until asked, then stop gracefully" (http.md, Stopping): a task or `main` waits, and
   cancelling it is how the program stops for another reason. `wait_for` with 0 is the look a
   loop that computes makes between items. A callback of the program's would run on the handler's
   thread, where a signal handler can do nearly nothing.
2. **`Stop`, a capability of its own**, not `Io` or `Proc`. Taking the requests over changes how the
   whole process ends: a library given `Proc` to run a compiler, or `Io` to print, shouldn't be able
   to swallow Ctrl-C. SIGTERM and the system's shutdown aren't the console's, and `Proc` is starting
   programs and reading the environment. With its own capability, `main`'s fields say whether a
   program takes Ctrl-C over, as they say whether it reaches the network.
3. **Installed by the first call, not by a call of its own.** A separate install would be one more
   call that must come first, with a misuse to define (a wait before it). The first wait is when a
   program starts caring; one that wants Ctrl-C taken over sooner, before a long start, looks with
   `wait_for{ nanoseconds = 0 }` then. Until then, Ctrl-C ends the program as it always did, which
   is what a program that isn't ready to stop gracefully wants. It is never uninstalled: a program
   is asked to stop once.
4. **The first request is kept for good.** A request isn't an event to consume: a program asked to
   stop stays asked, so every wait after it returns at once, and a wait that was cancelled leaves
   nothing behind that a later wait could find stale. Nothing is reset, so the object needs no
   reading in the handler, and two waiters, in two tasks, both return.
5. **A second request ends the program at once**, as it would without `stop`, which is common
   practice: a graceful stop that hangs (a connection that won't close, a grace period too long)
   leaves a person a way out, Ctrl-C again, without a second terminal and `kill -9`. The program
   ends as Windows or the signal ends any program, so its exit code says it was ended by the
   request. A request after `ask` counts as the second: the program was already stopping.
6. **`ask`**, so that a program stops itself through the same waits: an administrative request, a
   task that found the program can't go on, a test. It takes a `Reason`, so a program passes on
   what a supervisor told it.
7. **Ignored stays ignored.** A shell starts a background job with SIGINT ignored, and a Windows
   process may inherit Ctrl-C ignored (`SetConsoleCtrlHandler(NULL, TRUE)`): `stop` takes over only
   what would have ended the program, and doesn't turn back on what its parent turned off.
8. **Not handled, each with its reason:** SIGHUP, which servers use for "reload your configuration",
   a meaning a program gives it, not std; SIGQUIT, Ctrl-\, which asks for a core dump; and Windows'
   `CTRL_LOGOFF_EVENT`, which only services see, for any user's logoff, and which doesn't mean this
   program ends.
9. **A handler and an object, not `signalfd` or a thread in `sigwait`.** `signalfd` and `sigwait`
   need the signals blocked in every thread, those started before the install and those a C
   library starts included, or a signal lands on a thread that doesn't block it and takes its
   default action. A handler works on whichever thread the signal lands on, and the object is
   waited on as a task's cancel object already is, with the same `poll`.

## Modules

The language's side is spec §10, Modules and Re-exports. This section is how ctxc builds them,
and why they are as they are.

### How it is built

- **Which files are inside which module** is the driver's (ctxc/modules.ctx, `find`), before
  the checker runs, for every command that checks a program. For each of the program's own
  files it walks up from its folder to the root of the file system, asking each folder once
  whether it holds an `api.ctx`; each that does is a module, the next one up its parent. A file a
  build program generates counts as in its executable's root: `analyze` takes a place for each
  file, which `ctxc build` takes as `--place DIR` before a file and `ctxc graph` writes as a
  `place` record after the generated file's. A module's folder is shown as its `api.ctx` is
  named, so messages name it as they name its files. `expose` paths are resolved there too,
  against the folders' keys (`Module.exposes`).
- **Names.** A namespace's table still maps a name to one entry; the other declarations of the
  name are chained from it (`Decl.next`). Each declaration has a `scope`: the outermost module
  whose inside sees it, or none for everywhere; a struct, union or enum has an `open` scope too,
  where its fields or variants are seen. Every lookup goes through `lookup` or `member`, given
  the module the code is in (`Scope.from`, or the name's file): it returns the first
  declaration that code sees, or failing that the first it doesn't, so a hidden name resolves
  and its one error comes from `use` (`hidden_use`), not from every place that resolves names.
  Two declarations of a name clash when their scopes nest (`overlaps`): for a program without
  modules every scope is the same, and `add_name` reports exactly what it did before.
- **api.ctx files.** `collect` declares an api.ctx's declarations without naming them
  (`api_decls`). `settle_modules`, before any type is resolved, takes the modules deepest first:
  each api declaration pairs with the definition of its name in the module's own files (a fn's
  or an opaque type's signature, a capability's fields), restates a declaration a nested api made
  visible inside the module, or is complete and named itself. Pairing and restating widen what
  they declare (`widen`): its scope becomes the module's parent, its `open` scope too unless an
  opaque `type` narrows it, and a clash this makes is reported once (`reclash`). A half has no
  name in any table: uses name the definition, so a fn has one identity at every level and
  lowering never sees a half.
- **Checking the contract** waits for the bodies' inferred error sets (`check_apis`, after
  `infer_sets` and the replay of the bodies' escape checks): a half is resolved with its definition's generic parameters, so their
  types are the same ids, and compared field by field (`compare_half`); a fn's `!T` gets the
  error that writes its set (`result_set`); and the names in each api declaration's types are
  looked up in the side table of uses for any that is hidden where the declaration is visible
  (`leaks`). Opaque types are checked where code looks inside one (`opaque_here`): a field, a
  literal, a variant, a match or `is`, `@as` on an enum. What a fn keeps (spec §14, Escape
  check) is its half's `from` and `into`, which `resolve_sig` gives the definition as its
  contract before the bodies are checked, and `check_contracts` compares with the summary once
  it is inferred.
- **After the checker** nothing changes: the IR names functions by declaration, and C names are
  made unique already (emit_c.ctx, `unique`), so two hidden `gff::put_row` are two functions.
- **Tooling.** `ctxc where` lists a name's declarations with their modules and scopes
  (modules.ctx, `where`). `ctxc api` takes what files outside the folder name of it, from the
  side table of uses, and what those declarations' types name in turn, then writes fns'
  signatures with their inferred sets and contracts (`kept_of`) and moves what is complete without a body out of its file
  (`first_api`), since such a declaration is the api's alone.

### Decisions

1. **Why modules.** Every name was visible everywhere and a namespace open to any file, so
   nothing told a function callers depend on from one file's helper: a changed signature broke
   code anywhere (friction.md #14); a library had no contract to read, and `!T`'s inferred sets
   made what it fails with known to the compiler alone; a subsystem's state went in `World`;
   and parallel agents agreed on helper names by message (#5). Private declarations one at a
   time (an attribute, a private namespace, file-private names) answer the last two but give no
   contract and hide helpers others could reuse. Public by default stays: an agent that finds a
   helper calls it rather than writes it again. A boundary is drawn on purpose, where a contract
   is wanted.
2. **The contract is a file, checked both ways.** C has headers because it compiles files
   separately, and checks them against nothing but the link; Ada's spec and body can't drift,
   but every package needs both; Go's capitals and Rust's `pub` spread the contract through the
   implementation; Go's ban on import cycles comes from compiling packages separately. ctxc
   compiles the whole program, so a contract file isn't needed to build anything: as OCaml's
   `.mli`, it is optional and exists only as the contract, and an opaque type in it is still
   passed by value, its size known.
3. **A file's place decides** which modules it is inside, not the build that adds it, and a
   module whose `api.ctx` isn't in the program is an error: otherwise a build that added a
   module's subfolder alone would make its files public. Folders are asked up to the root of the
   file system, once each.
4. **A generated file is in its executable's root**, as §19 says it is "in one of its
   directories": a generator writing code for a module's internals, as one for an ECS would,
   needs to see them. It can't be named `api`: an `api.ctx` is written by hand.
5. **An opaque type has its zero value outside**, and `==`, `@hash` and an order where it has
   them: a zero value is a property of its bytes (§11, Initialization), which every allocation,
   static and struct holding one already has, and comparing names nothing inside it. `@as` on an
   opaque enum does name its values, and is an error.
6. **Attributes**: a fn's half has `#write` and `#convert`, which change how callers
   use it, and its definition the same; the rest are the definition's. A `#write` fn is exempt
   from stating its errors: its result is a bare `!` (§13), whose errors are its sink's.
7. **An `extern fn` may be declared in `api.ctx`**: it is complete without a body. A
   capability with fields is made only inside its module, as statics are reached only there:
   otherwise a module adding to the namespace could make one.
8. **A definition matches its api exactly**: its context fields in the api's order, names and
   `mut`. It may write `!T` for the api's `E!T` when its body is inferred to fail with E's
   errors, so a set is written once, in the contract, and still checked.
9. **A contract's open set is open, and names what made it so.** std's file and process sets
   are open, since an OS can fail in new ways, so a body that reads a file has an open set.
   Its contract is open too, with the same errors, and names the sets: `error(fs::Error,
   bad_magic)`, written by `--fix` in the fewest names (`written_set`: the largest alias first,
   std's or the api's own). Considered and rejected: closing std's sets, which would promise
   what the OS doesn't; letting a contract say `!T`, which would leave its errors to the
   body; and an open contract as "at least these errors", which would let the module's files
   add errors of their own without the contract changing. `fs::Error` lists `task::cancelled`,
   as `proc::Error` does: every file call checks for it before it blocks.
10. **Tests get no exception.** A `#test` fn sees what its file sees: one inside the module tests
   its internals, kept where the agent changing them works; one outside tests the contract.
   Considered and rejected: a `#test` fn that sees past every boundary (a test is a fn other
   code may call, and could hand a hidden function on), and a list in `api.ctx` of outside
   folders that may see inside (a module's guarantee would depend on files it doesn't own).
11. **Re-exports never rename and never widen** (spec §10, Re-exports): a name means one thing,
    with one type, at every level it reaches, so `let f = gff::read` has one type wherever it
    is written. The directive is `expose`, not `export`, which brings TypeScript's forms with it
    and, this close to C, means the linker's symbols.

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
  origins plus pointer-store effects, then the bodies' escape checks run with them. A body is
  checked once: what its check does that a summary changes (`Late`: what each local is derived
  from, the escape checks, a call's keeps and its parts' order, and the flow errors, which are
  reported only in a body without other errors since its start) is recorded in order as it
  is checked, and done again in that order once the summaries are made (`replay_bodies`), with
  the body's derived sets made again and its errors counted from its start. Checking every body
  a second time did the same, and was a fifth of checking KOTOR. Each store
  says which fields' places, or what they point to, it goes into, and a call keeps what its
  callee's stores say (`check_keeps`): the `into` of a contract. An origin is a field as it
  is, or what its pointees hold (`PRIME`), so a value read through `&doc` holds what `doc`
  holds, not `doc`; a local's origins put there by a call that stores through `&local` are
  marked `DEEP`, what its pointees hold, so that they don't say where a store through it goes.
  Cycles of calls are found as the summaries are made, Tarjan's way (`borrow_fn`): a call
  into a cycle still being made sees what it has, empty at first, and when the walk is back at
  the cycle's first fn the fns that saw too little are made again, and those calling one that
  grew, from where their locals' origins ended, until none grows (`borrow_settle`). Then no fn
  outside the cycle has seen it yet. Checking ctxc's ~2,700 fns makes about 3,400 summaries;
  the inference takes about three times what it did before contracts (about 400 ms of 2.8 s),
  most of it the cycles of the parser and checker and the `mut` fields' origins. Calls through function values go by their
  types' contracts, which `check_fn_values` holds each fn made a value to. Effects carry
  stored types through generic substitution so byte-copy helpers stay precise. Outputs
  conservatively include possible stored origins; this does not model memory aliases,
  allocation lifetimes or struct fields apart: a list that holds a pointer to a local arena is
  derived from it whole.
- **Not planned: generating declarations inside the running compile** (Zig's `inline for` over
  fields with types as values, or Jai's `#insert`). It needs lazy analysis or a fixed-point loop
  in the checker, and generics would become compile-time values. Generated code is written out
  as real `.ctx` files and compiled in a later step, so errors point at files a person can open
  and a generator can't observe its own output. Revisit only if reflection and compile-time
  consts fall short on real code.
- **No checking in a child process for the language server:** every buffer and every answer
  would cross a pipe on each edit. A panic ends the server and the client restarts it; the
  recovery test keeps that rare.
