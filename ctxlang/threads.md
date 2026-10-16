# Concurrent IO: design

Status: **designed, not built.** The first backend is Threaded ("Order of work"). It is std, built on
the threads, atomics, mutexes and conditions ctxlang already has (spec §13, §15 rule 14, §17
`thread`; std/thread.ctx), with three changes to the language (Language changes).

## Why

A general purpose language spends much of its time waiting on the operating system: serving and
sending HTTP requests, loading files from disk, reading standard input or a child's pipes. A program
that does one at a time spends its life waiting. It wants many in flight at once, written as ordinary
code that reads top to bottom, without managing threads by hand.

## What other languages learned

- **async/await** (C#, Rust, JavaScript, Python, Kotlin, Swift): the compiler turns a function into a
  state machine that can stop at each `await`. Cheap per task, but **coloured**: an async function can
  be awaited only from another, so `async` spreads up the call graph and libraries come twice, once
  of each colour. Rust adds `Pin`, `Send` bounds, executors that don't mix, and cancellation by drop,
  which leaves "is this cancel-safe?" to every caller. Nobody who has it would choose colouring again.
- **Green threads** (Go's goroutines, Java's virtual threads, Erlang): each task has a small stack of
  its own, and the runtime switches stacks where it would block. No colour: code blocks as usual.
  They work where a managed runtime owns everything, the stacks, every call into C, every blocking
  call, and can move a stack because it knows every pointer on it. Systems languages that tried them
  dropped them: Rust before 1.0, .NET's 2023 experiment, Java's first green threads.
- **Zig 0.16** passes an `Io` to every function that does IO, as it passes an `Allocator`, and
  `main` picks the implementation: `Io.Threaded` (blocking calls on a pool of threads, shipped) or
  `Io.Evented` (stackful coroutines over io_uring and kqueue, experimental). `async` and `await` are
  functions on the `Io`, not keywords, so code is written once and runs on either. It separates
  "may run concurrently" (`async`, which can't fail: it may run the function at once) from "must"
  (`concurrent`, which can).
- **Odin** has no async in the language: threads, and `core:nbio`, an event loop per thread with
  callbacks, as a library.
- **What the operating systems allow.** Sockets, pipes, timers and child processes can be waited on
  by an event loop. Reading a regular file can't be made non-blocking that way (epoll refuses regular
  files; kqueue reports them always readable, which doesn't make the read fast), and Windows' console
  and inherited anonymous pipes can't be overlapped. So Go, Tokio and libuv run file IO on blocking
  threads anyway. An event loop's gain is in holding many sockets and pipes open at once, where a
  thread each costs memory and scheduling.

ctxlang already passes `Io`, `Fs` and `Proc` down from `main` as capabilities, which is Zig's shape.
So this is Zig's design with capabilities: no keywords, no colour, blocking code everywhere, and the
backend that runs tasks is std's, picked per executable.

## Shape

A **task** is one call of a run function, `run{ data }`, that may happen concurrently with the code
that started it. Tasks can be waited on, cancelled, and grouped so none outlives the code that
started it. IO stays the blocking calls std already has (`fs::read`, `proc::read`, `io::read`, and
`net`'s); the **backend** decides what blocking means:

- **Threaded** (first): each running task has a worker thread, and a blocking call blocks it. This
  covers disk, standard input and pipes completely, and sockets until there are so many that a
  thread each costs too much.
- **Evented** (designed below, built after): tasks are fibers on an event loop per thread, and a
  blocking call submits the operation and switches to another fiber.

A program's backend is picked when it is built (Decisions, 8).

## Capabilities

```
// Whether the calling thread runs a task, and which: what std's blocking calls check.
namespace task { capability Cancel { #thread_local static current: u64 } }

capability Io { ..io::State, ..task::Cancel }
capability Fs { ..task::Cancel }
capability Threads { ..task::Cancel }
capability Proc { ..os::Proc, ..Io, ..proc::State }      // unchanged: Cancel comes through Io
capability Net { ..task::Cancel }                         // net.md

// Permission to run functions concurrently with the caller, and the backend's state. Cancel comes
// through Threads.
capability Tasks { ..Threads, ..Mem, ..task::State }
```

`main` receives `Tasks` as it receives `Threads`: every one of these has only statics or inclusions,
so each is a capability without fields (spec §15, rule 1). `Tasks` includes `Threads`, since the
Threaded backend starts threads, and `Mem`, since it keeps its table of tasks in pages from
`mem::pages`. A program whose `main` or start fn takes `Tasks` is threaded (Language changes, 1).

Capabilities stay granular (Decisions, 2): `Tasks` is permission to run things concurrently, not to
do IO. A task that reads files still needs `Fs`, which its run function takes and its starter must
hold, as for `thread::create` (`#spawn`, spec §15, rule 14).

A capability of a program's own that includes two of these, `capability App { ..Io, ..Fs }`, reaches
`task::Cancel`'s static twice, which spec §15 rule 9 forbids today; Language changes, 2 allows it.

**How the platform's layers reach it.** Only functions of namespace `task` read `current`
(spec §15, rule 13), so the layers call these, passing the capability they hold, which converts to
the `task::Cancel` it includes:

```
namespace task {
    // Fails with `cancelled` if the calling task has been asked to stop. Never outside a task.
    fn check { mut cancel: Cancel } -> !

    // The calling task's cancel object, which is signalled when it is asked to stop: a Windows
    // event, a Linux eventfd, or the read end of a macOS pipe. 0 outside a task.
    fn get_cancel_object { mut cancel: Cancel } -> u64

    // Around a synchronous call that only CancelSynchronousIo can interrupt (Windows, below).
    fn begin_synchronous { mut cancel: Cancel } -> !
    fn end_synchronous { mut cancel: Cancel }
}
```

`fs`'s layer functions take `Fs` and `io`'s take `Io`, so they pass what they hold. `proc`'s take
`os::Proc`, which doesn't include `Io`, so `os::pipe_read`, `pipe_write`, `wait` and `wait_for` gain
a field `mut cancel: task::Cancel`, which the public `proc` functions pass as `cancel = &proc`.

## The API

```
namespace task {
    // A task, as the backend's table knows it: its slot's index (32 bits) and generation (32
    // bits). ENDED, 0, is a task that ran at once and has no slot. Waited on (to its end),
    // cancelled or detached exactly once.
    struct Task { id: u64 }
    const ENDED: Task = Task{ id = 0 }

    // Tasks that end together.
    struct Group { id: u64 }

    error cancelled             // what a blocking call fails with, in a task that is cancelled
    error out_of_resources      // no thread, or no room in the table

    // Runs `run{ data }`, maybe concurrently with the caller, maybe at once. Returns no error:
    // when the backend can't run it concurrently (no worker, the limit, or the table can't grow),
    // it runs it here and returns ENDED.
    #spawn{ owned = true }
    fn start(T) { mut tasks: Tasks, run: fn{ data: *mut T }, data: *mut T } -> Task

    // Runs `run{ data }` concurrently with the caller, or fails.
    #spawn{ owned = true }
    fn start_concurrent(T) { mut tasks: Tasks, run: fn{ data: *mut T }, data: *mut T } -> !Task

    // Runs `run{ data }` on an operating-system thread of its own, in every backend: for work that
    // blocks outside std (a C call that waits, a lock held across IO) or computes for long. In
    // Threaded it is start_concurrent.
    #spawn{ owned = true }
    fn start_blocking(T) { mut tasks: Tasks, run: fn{ data: *mut T }, data: *mut T } -> !Task

    // Waits for the task to end; then the handle is used up.
    fn wait { mut tasks: Tasks, task: Task }

    // As `wait`, giving up after `nanoseconds`: false when it gave up, and the handle is still
    // to be waited on, cancelled or detached.
    fn wait_for { mut tasks: Tasks, task: Task, nanoseconds: u64 } -> bool

    // Asks the task to stop (Cancellation, below) and waits for it to end.
    fn cancel { mut tasks: Tasks, task: Task }

    // Lets the task end on its own; the handle is used up.
    fn detach { mut tasks: Tasks, task: Task }

    // Fails with `cancelled` if the calling task has been asked to stop: for a task that computes
    // for long between blocking calls. Never fails outside a task.
    fn check_cancelled { mut tasks: Tasks } -> !

    fn make_group { mut tasks: Tasks } -> !Group

    // As start, start_concurrent and start_blocking, the task belonging to the group: there is
    // no Task to wait on. A group being cancelled starts its new tasks cancelled.
    #spawn{ owned = true }
    fn start_in(T) { mut tasks: Tasks, group: Group, run: fn{ data: *mut T }, data: *mut T }
    #spawn{ owned = true }
    fn start_concurrent_in(T) { mut tasks: Tasks, group: Group, run: fn{ data: *mut T }, data: *mut T } -> !
    #spawn{ owned = true }
    fn start_blocking_in(T) { mut tasks: Tasks, group: Group, run: fn{ data: *mut T }, data: *mut T } -> !

    // Waits until the group has no task, those started meanwhile included.
    fn wait_all { mut tasks: Tasks, group: Group }

    // Asks every task of the group to stop, then waits until it has none.
    fn cancel_all { mut tasks: Tasks, group: Group }

    // cancel_all, then frees the group: the handle is used up.
    fn free_group { mut tasks: Tasks, group: Group }

    // Busy workers past which `start` runs a task at once (Threaded backend, below).
    fn set_limit { mut tasks: Tasks, workers: u32 }

    // Stack for workers started after it; 0 for thread::DEFAULT_STACK.
    fn set_stack { mut tasks: Tasks, bytes: usize }
}
```

A task's result is what its run function writes through `data`: `data` must outlive the task, and
nothing checks it. A field of type `!T` holds a result that may have failed (spec §8, Errors, rule
5), so a run function stores what its calls return, error or not (Examples). `wait` returning makes
everything the task wrote visible to the waiter: the task's end and the wait meet under the table's
mutex.

**`start`, `start_concurrent` or `start_blocking`.** `start` says the caller doesn't need the task to
run at the same time as anything; it only allows it. So it returns no error, and code written with
it runs on any backend, on one with no concurrency at all, and in the interpreter. Its only failure
is the runtime's: when a run function takes a capability with fields, its record (Language changes,
3) is allocated, and running out of memory there panics, as for any record. `start_concurrent` says
the program is wrong unless the task runs alongside the caller: a server's accept loop and its
handlers, a reader of a child's standard error while the caller reads its standard output. A task
that waits for something another task must do (a condition another signals, a pipe another fills)
needs the other started with `start_concurrent`. `start_blocking` is for work the backend can't see
waiting.

**A task run at once** runs as part of its starter: on the same thread, with the starter's slot as
`task::Cancel`'s `current`. Cancelling the starter reaches it, and its `check_cancelled` sees the
starter's flag. It has no handle until it has ended, so nothing else could cancel it. On the main
thread, which is no task, it can't be cancelled, as the main thread can't.

**Groups are how nothing outlives its caller.** A function that starts tasks in a group and frees it
with `defer task::free_group{ &tasks, group = g }` can return early, by an error or not, and leave
nothing running; it calls `wait_all` first when it wants the results. Any holder of the group may add
tasks to it, its own tasks included (a crawler that finds more pages), also while another waits on
it. `cancel_all` asks every task of the group to stop before it waits for any, so a task that needs
another task of the group to notice cancellation isn't waited on first. A task of a group that waits
on, cancels or frees its own group panics: it would wait for itself.

**Misuse panics**: a handle used after it is used up (its slot's generation no longer matches), a
second `wait` on one handle while one waits, and a group's own task waiting on it. A slot whose
generation would wrap is retired, never reused.

**What can still deadlock.** No task waits for a free worker (Threaded backend, No queue), so a task
never waits on one that will never start. A program can still deadlock as any threaded program can:
two tasks waiting on each other, a task holding a mutex when `start` runs a task at once that locks
it (mutexes aren't recursive), or a `start`ed task that waits on its starter's signal.

## Cancellation

Each task has a flag and a cancel object (Capabilities), made with its slot and reset when the slot
is reused. `cancel`, `cancel_all` and `free_group` set the flag and signal the object. A task that is
cancelled isn't stopped: its blocking calls fail, so the code it runs returns through its usual error
paths, `defer`s and all. `cancel` then waits for the task to end, which a call that can't be
interrupted (below) delays: a deadline is a request to stop at that time, not a bound on when the
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

**Checked before only**, by decision, each with its reason: `fs`'s calls (regular files, and
metadata: `open`, `list`, `remove`, renames), since disk IO can't be waited on with poll or kqueue
and Windows doesn't promise to cancel file system calls (`MoveFileEx` among them), and they finish
in disk time; reading standard input that is a file, for the same reason; name lookup on POSIX, since
`getaddrinfo` has no cancellation and `getaddrinfo_a` is glibc's alone (net.md); `mutex::lock`,
`condition::wait`, `thread::join` and calls into C, which aren't IO and wait on what the program
itself holds.

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

**Cancellation follows waits down.** A task that waits (`wait`, `wait_for`, `wait_all`) when it is
cancelled, or is cancelled while it waits, cancels what it waits for, then still waits for it to end;
`wait_for` then waits to the end and returns true. So cancelling a task reaches every task it
started and waits on, and a task never ends before the tasks it waits on. How a waiting task is
woken: a waiter records in its own slot what it waits on, under the table's mutex; `cancel` sets the
flag under the same mutex and broadcasts the condition the waiter waits on. The waiter checks the
flag and the end under that mutex before every wait, so neither can be missed.

`check_cancelled` is for loops that compute without blocking.

## How std's IO takes part

| Capability | Calls that block | With the Threaded backend |
|---|---|---|
| `Fs` | `open`, `read`, `write`, `read_all`, `list`, ... | block the worker; checked before (Cancellation) |
| `Io` | `read` (standard input), `flush` and writes that fill the buffer | block the worker. Each worker has its own output buffer (it is `#thread_local`), which it writes out when a task ends and before the end is published, ignoring the flag, so a cancelled task's output isn't lost; output that can't be written blocks it, as it would block the program without tasks. A task run at once shares its starter's buffer |
| `Proc` | `read`, `write` (pipes), `wait`, `wait_for`, `run` | block the worker. A cancelled `wait` or `wait_for` leaves the `Child` as it was: not released, its pipes open, to be waited on or killed. A cancelled `run`, which owns its child, kills it, waits for it uninterruptibly (a killed child ends at once), and fails with `cancelled` |
| `Threads` | `sleep` | waits on the cancel object |
| `Net` | connect, accept, send, receive, name lookup | block the worker |

`Net` and HTTP are designed in their own documents (net.md, http.md), with TLS: they are a protocol
and a library, not concurrency. What this design fixes for them: blocking calls, `..task::Cancel` in
`Net`, `cancelled` among their errors, and the table's row above.

std's allocators are one thread's at a time: tasks that allocate each have their own arena, from
pages of their own or from a buffer their starter gives them, or share one behind a mutex.

## The Threaded backend

What `task::State` holds and does, all of it std over `std/thread.ctx`:

- **The table.** Slots in pages from `mem::pages`, which grow as tasks start and are reused once used
  up, under one mutex. A slot holds the run function and `data`, the flag and the cancel object, what
  the task blocks on or waits on, its group, its worker, and its state: running, ended, used up.
  A task's slot is used up when its handle is (`wait`, `wait_for` returning true, `cancel`), or when
  it ends after `detach`, or, for a group's task, when it ends. A `Task` handle stays good while its
  task runs and after it ends, until it is used up.
- **Workers.** Threads that run one task at a time. `start` takes an idle worker, or starts one while
  fewer than the limit are busy; otherwise, or when the operating system refuses a thread or the
  table can't grow, it runs the task at once. `start_concurrent` and `start_blocking` take an idle
  worker or start one whatever the limit, and fail with `out_of_resources` only when the operating
  system refuses a thread or the table can't grow. A worker idle for 10 seconds ends.
- **The limit** is soft and applies to `start` only: 64 busy workers, since tasks that do IO spend
  their time blocked and the processors' count would be too few. `set_limit` takes the table's mutex
  and applies to the next `start`; lowering it stops no worker. 0 makes `start` always run at once.
- **No queue.** A task either has a worker or has run. Nothing waits for a free worker.
- **Stacks.** Workers have `thread::DEFAULT_STACK`, 8 MiB, reserved and committed as used, with the
  headroom `thread::create` gives every thread for the stack check. `set_stack` applies to workers
  started after it; an idle worker whose stack is smaller than the setting ends instead of taking a
  task.
- **Capabilities.** A run function's capabilities reach the worker as they reach a thread (`#spawn`).
  Its record, when one of them has fields, is the task's: the backend frees it once the run function
  has returned, or when `start_concurrent` fails without running it (Language changes, 3).
- **A panic** in a task ends the program, as on any thread, reported as `panic in thread task N:`.

## The interpreter

`ctxc interp` runs `start`'s tasks at once, which `start` allows, and `wait` and its kin return at
once. `start_concurrent`, `start_blocking` and their `_in` forms stop the run as not supported by
interp: it runs one thread, so it can't keep their promise. Files, standard input and other programs
are already not supported there, so what the interpreter runs of tasks is code that computes and
prints; it detects no deadlock beyond what it already stops on (a mutex another thread holds).

## The Evented backend

Built after Threaded; designed now, so that Threaded leaves room for it. Tasks are **fibers**: each
has a stack of its own, and an event loop per thread runs them. A blocking call submits its
operation to the loop, records which fiber waits for it, and switches to the next fiber that can run;
the loop switches back when the operation completes. Code doesn't change: `fs::read` still returns
what it read. `start_concurrent` starts a fiber; `start_blocking` an operating-system thread.

What it needs, and how each is solved:

- **Switching stacks.** On Windows, `CreateFiberEx` and `SwitchToFiber`, which keep the thread
  information block's stack bounds and exception chain right. On Linux and macOS, a switch routine
  per ABI in an assembly file of its own, which the C compiler assembles: System V x86-64 saves `rbx`,
  `rbp`, `r12`–`r15`, `rsp` and the MXCSR and x87 control words; AArch64 saves `x19`–`x29`, `lr`,
  `sp` and `d8`–`d15`. Not extended asm inside a C function, which GCC requires to leave the stack
  pointer as it found it. It is the first thing built for Evented, and tested optimized (-O2) on each
  ABI before anything relies on it.
- **What each fiber has of its own**, saved and loaded with its stack: the stack limit, the runtime's
  stack of borrowed function-value records (ctx_thread's; fiber A returning would otherwise rewind
  records fiber B still uses), `task::Cancel`'s `current`, and its output buffer. Every field of
  `ctx_thread` is audited for which kind it is, per fiber or per thread, before Evented is built.
- **Standard output.** Each fiber writes to a buffer of its own, which `io`'s `out` points to while it
  runs, so a flush that suspends isn't overwritten by another fiber.
- **Stacks.** A fiber's usable stack (256 KiB by default, `set_stack`), headroom past it for the stack
  check to land in (a quarter of it, at least 64 KiB, as `thread::create` does for threads), and a
  guard page; reserved, and committed as used (`CreateFiberEx`'s reserve and commit sizes; `mmap`
  with a `PROT_NONE` guard elsewhere). An ended fiber's stack goes to a pool for the next. C frames
  aren't checked: a C call that needs more than is left stops at the guard page, as on a thread; deep
  or blocking C goes to `start_blocking`.
- **Locks and waits.** In an Evented program std's `mutex`, `condition`, `thread::sleep` and
  `yield_now` park the fiber rather than its thread: a fiber that can't lock waits in the mutex's list
  and the loop runs others, and an unlock from any thread wakes it through its loop. Otherwise fiber A
  holding a mutex across IO would leave fiber B on the same thread blocked on it forever.
  `thread::join` and calls into C block the loop's thread: `start_blocking` is for them.
- **Fibers never move between threads**: a loop runs its own, so `#thread_local` statics stay each
  thread's, as code that isn't a task expects.
- **What the loop submits**, by platform: Windows, IOCP for sockets, std's child pipes and files
  opened overlapped, and waits on child processes and the console's input; Linux, io_uring for files,
  sockets, pipes and timeouts, and pidfds for children; macOS, kqueue for sockets, pipes, standard
  input, children and timers. What can't be submitted goes to blocking threads behind the loop, as Go,
  Tokio and libuv do: Windows' inherited anonymous pipes, file system metadata everywhere, and regular
  files on macOS (POSIX AIO there is a second completion mechanism for one platform, which the pool
  makes unnecessary).
- **Cancellation** cancels the fiber's pending operation on its loop: `CancelIoEx` with its
  `OVERLAPPED`, an io_uring cancel, a kqueue delete; then the fiber resumes with `cancelled`.

## What a program without tasks pays

A program that doesn't take `Tasks` starts no worker and links nothing of the backend. Its blocking
calls check `task::Cancel`'s `current`, which stays 0: a plain global in a program that isn't
threaded (spec §15, Entry point, rule 8), a thread-local in one that is. One load and a branch per
blocking call.

## Language changes

1. **Threaded programs** (spec §15, Entry point, rule 8): a program is threaded if `main` or its
   start fn takes `Threads` or a capability that includes it.
2. **A static reached twice** (spec §15, rules 9 and 13): a capability may reach the same static
   through two inclusions, `..Io` and `..Fs` both reaching `task::Cancel`'s. It is one static for the
   program already, so nothing is duplicated; the rule against reaching a field twice stays for
   functions and C variables.
3. **`#spawn{ owned = true }`** (spec §15, rule 14): the record a carried `fn` needs, when a
   capability it carries has fields, belongs to the fn the attribute is on, not to the program. It
   comes from the runtime's free lists, by size, under its lock, rather than `ctx_alloc`, which never
   frees; `@free_record(run)` gives it back. The fn must free it once it will never call `run`
   again: after the one call, or without calling it when it fails. Calling `run` after that is
   undefined, as any use of freed memory. Only std's `task` functions have it; `#spawn` without it,
   `thread::create`'s and any program's own, stays as it is.

## Examples

### Loading files at once

Each load has its own arena, since allocators aren't shared between tasks, and its result in a `!T`
field. `start` may run a load at once: the code is right either way.

```
struct Load {
    path: []u8,
    heap: arena::Arena,             // this load's alone
    bytes: !alloc::Bytes,           // what read_all returned, error or not
    task: task::Task,
}

fn load { mut fs: Fs, data: *mut Load } {
    data.bytes = fs::read_all{ &fs, &data.heap, realloc = arena::alloc, path = data.path }
}

fn load_all { mut fs: Fs, mut tasks: Tasks, loads: []mut Load } {
    let mut i: usize = 0
    while i < loads.len {
        loads[i].task = task::start{ &tasks, run = load, data = &loads[i] }
        i = i + 1
    }
    i = 0
    while i < loads.len {
        task::wait{ &tasks, task = loads[i].task }
        i = i + 1
    }
}
```

### A child's standard output and standard error

A child that fills its standard error's pipe while the parent reads only its standard output waits
forever, and so does the parent. Reading standard error in a task of its own ends that; it must run
concurrently, so it is `start_concurrent`. A reader keeps reading after its buffer is full, so the
child never waits on a full pipe; a reader that fails, or a reader that can't start, ends the child.

```
struct Drain { pipe: proc::Pipe, kept: [65536]u8, len: usize, result: !usize }

// Reads the pipe to its end, keeping what fits in `kept` and dropping the rest.
fn read_to_end { mut proc: Proc, d: *mut Drain } -> !usize {
    let mut scratch: [4096]u8
    let mut n = try proc::read{ &proc, pipe = d.pipe, into = scratch[..] }
    while n > 0 {
        let room = d.kept.len - d.len
        let take = if n < room { n } else { room }
        slice::copy(u8){ dst = d.kept[d.len..d.len + take], src = scratch[..take] }
        d.len = d.len + take
        n = try proc::read{ &proc, pipe = d.pipe, into = scratch[..] }
    }
    return d.len
}

fn drain { mut proc: Proc, data: *mut Drain } {
    data.result = read_to_end{ &proc, d = data }
}

fn run_tool { mut proc: Proc, mut tasks: Tasks, argv: [][]u8, out: *mut Drain, errs: *mut Drain } -> !i32 {
    let options = proc::Options{ stdout = proc::Stdio::pipe, stderr = proc::Stdio::pipe, .. }
    let mut child = try proc::spawn{ &proc, argv, options }
    if let p = child.stdout { out.pipe = p }        // both are pipes, as options asked
    if let p = child.stderr { errs.pipe = p }
    let reader = task::start_concurrent{ &tasks, run = drain, data = errs } iferr err{ error } {
        proc::kill{ &proc, child } iferr {}         // it would wait on standard error forever
        _ = proc::wait{ &proc, &child } iferr {}
        return error
    }
    drain{ &proc, data = out }
    task::wait{ &tasks, task = reader }
    // A reader that stopped early leaves the child waiting on a full pipe: end it.
    if out.result is err or errs.result is err { proc::kill{ &proc, child } iferr {} }
    let code = try proc::wait{ &proc, &child }
    _ = try out.result
    _ = try errs.result
    return code
}
```

### A timeout

`wait_for` and `cancel` give a call a deadline. The task must run alongside, so it is
`start_concurrent`: `start` might run it at once, and the wait would begin after it had finished.
At the deadline the task is asked to stop; `cancel` returns when it has, which a call that can't be
interrupted delays (Cancellation).

```
let t = try task::start_concurrent{ &tasks, run = fetch, data = &request }
if not task::wait_for{ &tasks, task = t, nanoseconds = 5000000000 } {
    task::cancel{ &tasks, task = t }        // request.result is task::cancelled, or what came first
}
```

### A server

A task per connection, in a group, so stopping the server stops every handler and waits for them.
`mem` gives pages and never takes them back, so a connection's memory is reused: a handler that ends
puts its `Connection` on the server's free list, under a mutex. A handler always closes its socket
and gives its connection back, whatever `serve_requests` failed with, `cancelled` included. `net`'s
calls are sketched here; net.md designs them.

```
struct Connection { socket: net::Socket, server: *mut Server, next: ?*mut Connection }
struct Server { lock: mutex::Mutex, free: ?*mut Connection }        // connections to reuse

fn give_back { server: *mut Server, c: *mut Connection } {
    mutex::lock{ mutex = &server.lock }
    c.next = server.free
    server.free = c
    mutex::unlock{ mutex = &server.lock }
}

fn take_connection { mut mem: Mem, server: *mut Server } -> ?*mut Connection {
    mutex::lock{ mutex = &server.lock }
    defer mutex::unlock{ mutex = &server.lock }
    if let c = server.free {
        server.free = c.next
        return c
    }
    let page = mem::pages{ &mem, size = @size_of(Connection) } ifnull { return null }
    return @cast(*mut Connection, &page[0])
}

fn handle { mut net: Net, data: *mut Connection } {
    serve_requests{ &net, socket = data.socket } iferr {}  // requests and responses until the peer closes
    net::close{ &net, socket = data.socket }
    give_back{ server = data.server, c = data }
}

fn serve { mut net: Net, mut mem: Mem, mut tasks: Tasks, server: *mut Server, listener: net::Listener } -> ! {
    let group = try task::make_group{ &tasks }
    defer task::free_group{ &tasks, group }
    while true {
        let socket = try net::accept{ &net, listener }      // fails with cancelled when serve's task is
        let c = take_connection{ &mem, server } ifnull {
            net::close{ &net, socket }
            continue
        }
        c.* = Connection{ socket, server, next = null }
        task::start_concurrent_in{ &tasks, group, run = handle, data = c } iferr err{ error } {
            net::close{ &net, socket }
            give_back{ server, c }
            return error
        }
    }
}
```

## Order of work: the Threaded backend

Language work on its own branch (kotor/AGENTS.md, rule 1), one step at a time.

1. **Language** (Language changes): threaded programs through an included `Threads`; a static
   reached twice; `#spawn{ owned = true }`, the runtime's free lists and `@free_record`. Spec §15 and
   §17.
2. **`task::Cancel`** in std, included in `Io`, `Fs` and `Threads`, and `task::check`,
   `get_cancel_object`, `begin_synchronous`, `end_synchronous`; `os::pipe_read`, `pipe_write`, `wait`
   and `wait_for` take `cancel`.
3. **The backend**: `Tasks`, `task::State`, the table, slots' cancel objects, workers, the API above;
   a worker writes out its standard output when a task ends.
4. **Interruptible calls**, each row of Cancellation's table on Windows and POSIX: child pipes, child
   waits, standard input (console, pipe, file), sleep; `O_NONBLOCK` on this program's ends of child
   pipes on POSIX; the synchronous-read protocol on Windows; a cancelled `wait` keeping its `Child`,
   a cancelled `run` killing its own.
5. **Tests**: corpus programs for each piece: start and wait; `start` past the limit and with the
   limit at 0 running at once, and returning ENDED; a handle waited on after its task ended;
   `start_concurrent` for a pipe reader; cancel of a blocked pipe read, child wait, console read and
   sleep, and a second blocking call after each, which must not see a stale cancel; a group's
   `cancel_all` reaching a task that waits on its own, and a task added to a group being cancelled; a
   task run at once cancelled with its starter; `wait_for` giving up; each misuse's panic; a record
   with fields freed after its task; the interpreter running `start` programs and refusing
   `start_concurrent`. Then the bootstrap refresh (ctxlang/PLAN.md, "Changing the language").
6. **net.md and http.md**, written against this contract, then built.
7. **The Evented backend**: the stack switch on each ABI first, then the per-fiber state's audit,
   then the loops.

## Decisions

1. **No channels, no task pools.** Tasks replace the pool: a worker per running task is what a pool
   gives, without its queue. A program that wants a queue between threads builds one from a mutex and
   a condition.
2. **Granular capabilities**, not one `Io` for everything as Zig has: `Tasks` is permission to run
   concurrently, and `Fs`, `Io`, `Proc` and `Net` stay permissions for what they touch. They share the
   backend's state by including `task::Cancel`, which costs no space and changes no public signature.
3. **No keywords, no colour.** `start` and `wait` are std functions taking `Tasks`; a function that
   blocks is the same function in a task or not. The compiler's part is the three Language changes.
4. **Task handles are the backend's**, an id into its table, as a `Thread` is the operating system's
   handle: no `Task` lives in the caller's memory, so none must stay put. A result goes through
   `data`, as a thread's does. A task run at once has the handle ENDED and no slot, so `start` needs
   neither a thread nor a slot to succeed.
5. **A task's record is the task's** (`#spawn{ owned = true }`): a server that starts a task per
   connection would otherwise keep a record per connection for good. Opt-in, so `thread::create` and
   programs' own `#spawn` fns keep their meaning.
6. **`start` returns no error**, and runs the task at once when it can't run it concurrently; only
   `start_concurrent` and `start_blocking` promise concurrency, and may fail. So most code runs on any
   backend and in the interpreter, and code that needs concurrency says so.
7. **Cancellation fails blocking calls** rather than stopping a task, so a task always leaves through
   its own error paths; a cancelled wait cancels what it waits for, so cancellation follows tasks and
   groups down. Calls that can't be interrupted are listed, each with its reason, rather than
   promised.
8. **The backend is picked per executable when it is built**, as the platform's layer is. `Tasks`
   must stay a capability without fields, since `main` receives it and it includes `Threads` and
   `Mem` (spec §15, rules 2 and 9), so it can't hold the function fields a choice at run time would
   need; and the blocking calls that would dispatch take `Fs`, `Io` and `Proc`, not `Tasks`. A test
   build may pick a backend that simulates IO and time the same way.
9. **No signals for cancellation on POSIX.** A cancel object per slot, waited on with the operation,
   interrupts every call that can be waited on; a signal would add a reserved signal, an
   async-signal-safe handler, and a re-send protocol for no call that the cancel object doesn't
   already reach.

## Open questions

1. **Bound functions for `start`.** Allowing `run = fetch{ &request, _ }`, with the record the task's
   (Language changes, 3), reads better than a data pointer, but changes spec §6, rule 3.
2. **Waiting before the frame ends.** Should the compiler warn when `data` points into the starting
   function's own locals and the task isn't waited on before it returns? The escape check could see
   the simple cases.
