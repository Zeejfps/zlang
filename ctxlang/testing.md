# Testing: research

Status: the test framework is **research only**. Its prerequisite, child processes in std's `proc`,
is designed below ("Child processes"), and its first part is built. This collects what the current
tests are, what is missing for ctxlang to run them itself, and what makes a good test framework in
other languages (Rust, Zig, Odin, Go, C#, Swift). The open questions at the end come before a design.

## Today

The tests are Python: tests/test_ctxlang.py (721 tests, about 14.3k lines) and
tests/test_borrow_lifetimes.py, over tools/toolchain.py (about 600 lines). The harness builds ctxc
from bootstrap/, caches builds by hash, compiles each program, runs it with captured stdout and
stderr, and diffs it against `ctxc interp`. Nothing in that is Python-specific: no ctxlang is parsed
in Python, everything goes through native ctxc.

The suite is almost all "source in, expected result out":

| Kind | Count |
|---|---|
| `assertOutput` (expected stdout) | 303 |
| `assertCompileError` (expected message fragment) | 209 |
| `assertPanic` (expected panic fragment) | 38 |
| Projects, stdin, multiple files | about 40 |

There is already demand in ctxlang itself: at least 8 KOTOR tools (kotor/tools/fmttest, basetest,
savetest, ...) each hand-roll the same `Tally{ run, failed }`, an `expect{ ok, what }` and an
`h.live == 0` leak check at the end. That is a test framework, written over and over.

## What ctxlang lacks to run the tests itself

1. **Capturing a child's output.** `proc::spawn` and `proc::run` share stdio with the parent
   (std/proc.ctx): no pipe or redirect, so a runner can't read what a test program printed. Most
   of the suite depends on that.
2. **Timeouts and kill.** `proc` has `wait`, but no deadline and no kill. The Python harness relies
   on `subprocess.TimeoutExpired`.
3. **Surviving a panic.** `rt::fail` is an extern C call with no unwinding (std/rt.ctx), so a panic
   ends the process. The 38 panic tests, and any crash, need a process boundary between the runner
   and the test.

Bootstrapping is also worth keeping in mind: if the runner is written in ctxlang, a broken compiler
can break the runner too. A tiny step that builds ctxc from bootstrap/ and then hands off is enough,
and that step is already C, not Python.

## What makes a good test framework

1. **The compiler finds the tests; the runner is just a program.** Rust (`#[test]`), Zig
   (`test "name" {}`), Odin (`@(test)`) and Go (`TestXxx`) have the compiler or toolchain collect
   the tests and generate a `main`. C# is moving the same way: older xUnit and NUnit find tests by
   runtime reflection, while TUnit uses a source generator to wire them up at build time, which
   makes startup much faster and works with Native AOT. Zig keeps the runner swappable: the test
   runner is ordinary code with a `main`, and you can replace it. Rust shows what happens when that
   split is missing: custom test frameworks have been unstable for years, so cargo-nextest works
   around libtest from outside. Lesson: "what is a test" belongs in the language; "how tests run"
   belongs in a library you can replace.

2. **A crashing test must not end the run.** This matters most for us. Three approaches:
   - A process per test (cargo-nextest): the most robust, slower to start.
   - Catching the panic (Rust's libtest): needs unwinding, which we don't have.
   - Signal handlers plus threads (Odin): it survives segfaults, asserts and panics; cleanup
     procedures then run on the main thread.

   Zig's default runner is the counterexample: one panic ends the whole test binary, a common
   complaint. For ctxlang a process boundary is the obvious fit, at least for tests that are
   expected to panic.

3. **Test that things fail, with expected-output files.** For a compiler this is the most important
   pattern. Rust's compiler test suite keeps each test as a `.rs` file next to a checked-in
   `.stderr`, with `//~ ERROR` notes inline, and `--bless` rewrites the expected files. Rust also
   has `#[should_panic(expected = "...")]`, `compile_fail` doc tests and the `trybuild` crate; Go
   uses an `-update` flag on golden files. Our output, compile-error and panic tests map directly
   onto this: they don't need to be test functions at all.

4. **Failure messages that show values.** Swift Testing's `#expect(list.count == 2)` reports
   `(list.count → 7) == 2`, because the macro sees the expression. Rust's `assert_eq!` shows left
   and right; Odin's `expect_value` does the same. A compiler builtin can do this better than a
   library: an `@expect(a == b)` could print both sides with no assertion API to learn.

5. **Soft and hard failures.** Odin has `expect` and `fail_now`, Swift `#expect` and `#require`, Go
   `Errorf` and `Fatalf`. A soft check records the failure and keeps going, so you see every failure
   at once; a hard check stops the test.

6. **Built-in resource checks.** Zig's `std.testing.allocator` fails a test that leaks. Odin gives
   every test a tracking allocator by default and reports leaks and bad frees. ctxlang is well
   placed here because `Mem` is passed explicitly: the runner can hand each test a tracking heap,
   and the leak check fmttest does by hand becomes automatic.

7. **Tests declare what they touch.** Go and Odin pass a `t` handle into each test. ctxlang can go
   further: a test asks for `mut t: Test` plus whatever capabilities it needs, so a test that
   doesn't take `Fs` or `Proc` provably can't touch the disk or start programs. None of the other
   languages offer that.

8. **Parallel by default, and reproducible.** Odin runs every test on its own thread, uses one
   random seed per run (`t.seed`) and replays one with `ODIN_TEST_RANDOM_SEED`. nextest, Swift
   Testing and TUnit also run in parallel by default. Odin has per-test timeouts
   (`testing.set_fail_timeout`).

9. **Easy to drive from tools.** Name filters (Odin's `ODIN_TEST_NAMES`, `cargo test foo`), `--list`,
   re-running only the failures (Odin can copy failed names to the clipboard), and machine-readable
   results (nextest's JUnit XML, Go's `test2json`), which a dashboard or an agent would use.

10. **Parameterized tests, each case with its own name.** Swift's `@Test(arguments:)`, xUnit's
    `[Theory]`/`[InlineData]`, Go's table tests with `t.Run`. A failure then points at the case.

11. **Later, not v1.** Integrated fuzzing (Zig's `zig build test --fuzz`, Go's native fuzzing with a
    corpus), benchmarks (Go's `testing.B`), runnable examples (Go `Example` functions checked
    against `// Output:`, Rust doc tests). Our interpreter-vs-C-backend diff should stay, as a
    runner mode.

**To avoid:** fluent assertion libraries (`x.Should().Be(...)`) and assertion APIs that keep growing;
fixture class hierarchies (NUnit/xUnit setup classes), where `defer` plus a `cleanup` hook covers
most of it; finding tests by runtime reflection; hidden global state; a runner with no extension
point.

## What this suggests for ctxlang

Two layers, which need different things:

1. **Unit tests in the language**, for std and the KOTOR libraries: `test "name" { mut t: Test, ... }`
   blocks next to the code, run with `ctxc test PATH`; a small `testing` namespace (soft and hard
   checks, logging) and an `@expect` builtin that shows both sides; a tracking heap per test. This
   replaces the hand-rolled `Tally`/`expect` in the KOTOR tools.
2. **Expected-output tests for the compiler**: a directory of `.ctx` cases, each with its expected
   stdout, compile error or panic inline or in a file beside it, run by a ctxlang driver, one
   process per case, in parallel, with `--bless`, plus the interpreter diff. This absorbs about 550
   of the 721 Python tests almost mechanically.

The `proc` work (capturing output, timeouts, kill) comes before either layer.

## Child processes

`proc` gets there in two parts. The first is built and needs no tasks; the second, `capture`, is
tasks (threads.md) over the first part's blocking calls.

**threads.md's Threaded backend comes first.** `capture` takes `Tasks`, which doesn't exist yet, and
Ctrl-C needs its cancellation (`task::Cancel`, interrupting a blocked call), so neither can be built
before that backend, and the test runner waits on both. Only the broken-pipe setting doesn't.

### The first part: spawning, pipes, waiting, killing (built)

```
union Stdio { inherit, ignore, pipe, file{ file: fs::File } }
union Leftovers { kill, keep }

struct Options {
    env: [][]u8 = [],                       // "KEY=VALUE", each replacing an inherited entry
    dir: []u8 = "",                         // working directory; "" is this program's
    stdin: Stdio = Stdio::inherit,
    stdout: Stdio = Stdio::inherit,
    stderr: Stdio = Stdio::inherit,
    group: bool = false,                    // its own process group (POSIX) or Job Object (Windows)
    leftovers: Leftovers = Leftovers::kill, // with `group`: what wait does with what is left of it
    die_with_parent: bool = false,
}

fn spawn { mut proc: Proc, argv: [][]u8, options: Options } -> !Child     // Child holds a ?Pipe for each piped stream
fn wait { mut proc: Proc, mut child: Child } -> !i32                       // and releases it, pipes still open included
fn wait_for { mut proc: Proc, mut child: Child, nanoseconds: u64 } -> !?i32   // null: still running; 0 checks without blocking
fn kill { mut proc: Proc, child: Child } -> !                              // the child, or its whole group or job
fn read / write / close                                                     // on a Pipe, blocking
```

- **Streams.** Each takes a `Stdio`; the default is `inherit`, so a tool that runs `cc` still lets it
  write to the terminal (C#, Rust, Zig and Python default the same; Go and Odin to the null device). A
  child inherits only the handles its streams name: POSIX_SPAWN_CLOEXEC_DEFAULT on macOS,
  pipe2(O_CLOEXEC) on Linux, PROC_THREAD_ATTRIBUTE_HANDLE_LIST on Windows, so one thread's pipes never
  reach another thread's child.
- **Exit codes** are an `i32`: the code, or 128 + N for signal N, as a shell says. No union of code and
  signal: Windows has no signals, so it wouldn't tell a crash apart everywhere, and the harness tells a
  panic by 134 and its message. A killed child is 137 on every platform (`proc::KILLED`), not an option,
  since POSIX can't honour another code.
- **Groups.** `group` puts the child in a process group of its own, or a Job Object, so `kill` reaches
  everything it started. `leftovers = kill` has `wait` end what is left of the group: on POSIX,
  kill(-pgid) before the leader is reaped, while its pid, the group's id, can't be reused; on Windows,
  closing the job, which has KILL_ON_JOB_CLOSE. `keep` leaves them running, for a launcher whose child
  daemonizes.
- **Dying with the parent** is opt-in, as in Go (`Pdeathsig`). Linux: PR_SET_PDEATHSIG, which fires
  when the *thread* that started the child ends. Windows: a Job Object with KILL_ON_JOB_CLOSE, even
  without `group`. macOS has no mechanism and ignores it: a platform limit, which deadlines bound. It
  covers the child until it ends: what it started is let go of then, unless `wait` ends it (`group`
  with `leftovers = kill`), as PR_SET_PDEATHSIG only ever covered the child. On Windows that is
  `die_with_parent` without `group`, or with `leftovers = keep`: `wait` clears the job's
  KILL_ON_JOB_CLOSE, then closes it, so no handle is kept.
- **Linux spawns with fork and exec**, so the child can ask for PR_SET_PDEATHSIG; the child's branch
  calls only extern fns, prepared before fork, and reports a failed exec through a CLOEXEC pipe. macOS
  uses posix_spawnp.
- **Ready for an event loop.** Windows' pipes are overlapped named pipes, which IOCP needs (anonymous
  pipes can't do overlapped IO); `wait_for` waits on a pidfd, a kqueue or the process handle, which an
  event loop can wait on too.

### `capture`: the second part, on tasks

```
struct Capture {
    env: [][]u8 = [],
    dir: []u8 = "",
    input: []u8 = "",               // fed to its standard input, which then closes
    timeout: ?u64 = null,           // nanoseconds
    max_bytes: usize = 16777216,    // kept of each stream; past it, read and dropped
    die_with_parent: bool = true,
}

struct Output { code: i32, timed_out: bool, truncated: bool, stdout: alloc::Bytes, stderr: alloc::Bytes }

fn capture(S) { mut proc: Proc, mut tasks: Tasks, mut heap: S, realloc: alloc::Fn(S), argv: [][]u8, options: Capture } -> !Output
fn free_output(S) { mut heap: S, realloc: alloc::Fn(S), output: Output }
```

It spawns the child with all three streams piped, `group` and `leftovers = kill`, then:

1. `start_concurrent`: write `input` to standard input and close it. A child that closes its input
   early isn't an error: feeding stops.
2. `start_concurrent`, twice: read standard output, and standard error, to the end, into the caller's
   allocator, past `max_bytes` reading and dropping (`truncated`), so the child never blocks on a full
   pipe.
3. The caller waits: `proc::wait_for` with the timeout. If it gives up, `capture` kills the group and
   sets `timed_out`; the output is what came before.
4. It waits for the three tasks, and returns.

The deadline needs no cancellation: killing the group closes every end of the pipes the child and its
descendants held, so the readers reach the end and the writer fails with `broken_pipe`, and the tasks
end on their own. A child that exits normally has its leftovers killed by `wait`, which closes the pipes
a background process kept. A `capture` that is cancelled (its `wait_for` fails with `cancelled`) kills
the group the same way and returns `cancelled`. An allocator or OS failure kills and waits for the child
and frees the buffers before returning the error.

A program that pipes only standard output, with no input to feed, can't deadlock: it reads with
`proc::read` and needs no tasks. Only two pipes or more need `capture`, and so `Tasks`; the test runner
takes `Tasks` anyway, to run tests at once.

`capture` isn't a multiplexer of its own (poll on Linux, kqueue on macOS, overlapped IO and
WaitForMultipleObjects on Windows, as Rust's `output()` and Zig's `run()` are): that would be an
evented backend for pipes alone, written three times, with its own way into cancellation, where
threads.md has one mechanism for waiting. On tasks, it is portable ctxlang in std/proc.ctx, on worker
threads with the Threaded backend and on one loop with Evented, unchanged.

### Broken pipes

What a write to a pipe whose reader has gone does is the program's choice, not a child's, so it is an
attribute on `main` (spelled as spec §18's attributes are), as Rust has `#[unix_sigpipe]` and Zig
`std_options.keep_sigpipe`, with three settings:

| Setting | A write to a child's pipe | A write to a broken standard output or error |
|---|---|---|
| `exit` (default) | fails with `broken_pipe` | ends the program quietly, with 141 |
| `signal` | ends the program (C's default) | ends the program |
| `ignore` | fails with `broken_pipe` | is dropped; the program goes on |

On POSIX, std's start installs a handler that does nothing (with SA_RESTART) for `exit` and `ignore`,
as Zig does, and SIG_DFL for `signal`. SIGPIPE is never left ignored, since exec keeps an ignored signal
but resets a handled one: every child starts with the default, even when this program was started with
SIGPIPE ignored, and no child needs resetting (Rust and Python reset it in each child). std's `io` writes
don't return errors, so a broken standard output is `io`'s to act on, as Go does for descriptors 1 and 2:
under `exit`, `prog | head` ends when `head` does instead of computing on into nothing. Windows has no
SIGPIPE, but its writes to a broken pipe fail (ERROR_NO_DATA), and `io` does the same there. This part
doesn't depend on tasks.

### Ctrl-C

A child in a process group of its own doesn't receive the terminal's Ctrl-C, which goes to the
foreground group only. A handler for SIGINT and SIGTERM (Windows: the console's control handler)
cancels the program's tasks, a test runner's group among them; each `capture` they are in kills its
child's group and returns `cancelled`, and the program then ends as the signal would have ended it. It
needs threads.md's `task::Cancel` and its interrupting of a blocked call.

### Order of work

1. `proc`'s first part (built; not committed).
2. The broken-pipe setting on `main`: ctxc, std's start, `io`.
3. threads.md's Threaded backend (its own order of work), all of it, cancellation included: everything
   after this step needs it.
4. `capture` on tasks, with tests: separate streams, input and output larger than a pipe both ways at
   once, the deadline (partial output, 137), `truncated`, a leftover holding standard output open, a
   child that closes its input early, a missing program, captures from several tasks at once.
5. Ctrl-C: the handler that cancels the program's tasks, and `capture` killing its child's group when
   cancelled.
6. The test runner, a task per test in a group.

## Open questions

- The `test` block syntax, and whether tests live inside source files or in separate files.
- For unit tests: one process per test, or one process per file with crash isolation.
- Whether expected output goes inline in comments or in files beside each case.
- Ctrl-C's handler: std's alone, installed with `Tasks`, or a small public API through which a program
  says what an interrupt cancels and adds cleanup of its own.

## Sources

- [Odin: The Test Runner](https://odin-lang.org/docs/testing/)
- [Odin PR #3646 (test runner rework)](https://github.com/odin-lang/Odin/pull/3646)
- [Using a Custom Test Runner in Zig](https://openmymind.net/Using-A-Custom-Test-Runner-In-Zig)
- [What is a test in Zig? (Ziggit)](https://ziggit.dev/t/what-is-a-test-in-zig/8885)
- [Zig testing and fuzzing notes (skills.cat)](https://skills.cat/skills/tkersey/dotfiles/zig)
- [Faster Rust tests with cargo nextest (JetBrains)](https://blog.jetbrains.com/rust/2026/05/01/faster-rust-tests-with-cargo-nextest/)
- [Rust custom_test_frameworks tests](https://rust.googlesource.com/rust/+/6fde77cd60dca48cc4279c7a1cfcf73f4e111cdc/tests/ui/custom_test_frameworks)
- [swift-testing](https://github.com/apple/swift-testing)
- [Swift Parameterized Testing](https://useyourloaf.com/blog/swift-parameterized-testing/)
- [TUnit.Engine on NuGet](https://www.nuget.org/packages/TUnit.Engine/1.65.38)
