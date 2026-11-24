# Concurrent IO: design

Status: **the Threaded backend is built** (Order of work, steps 1 to 7): the language changes, the
audit, `task::Cancel`, the backend in std/task.ctx, the interruptible calls, KOTOR's mixer moved to a
task, and the tests. `thread::create` and `#spawn`, which passed a thread its data through a `*mut T`
that nothing checked, are gone. Steps 8 and 9, net.md and http.md and the Evented backend, are next.
spec §15, Tasks, is the language's side; what the build settled that this document left open is under
Decisions made building it.

## Why

A general purpose language spends much of its time waiting on the operating system: serving and
sending HTTP requests, loading files from disk, reading standard input or a child's pipes. A program
that does one at a time spends its life waiting. It wants many in flight at once, written as ordinary
code that reads top to bottom, without managing threads by hand.

What ctxlang had, `thread::create{ &threads, run, data }`, gave a thread a function and a
`*mut T`. The function's capabilities were carried by a special rule (`#spawn`), the data's type was
generic but its lifetime a comment ("must outlive the thread"), and a result came back through
the same pointer. Everything else in the language reaches a function through its context, checked
at the call. A task should too.

## What other languages learned

- **async/await** (C#, Rust, JavaScript, Python, Kotlin, Swift): the compiler turns a function into a
  state machine that can stop at each `await`. Cheap per task, but **coloured**: an async function can
  be awaited only from another, so `async` spreads up the call graph and libraries come twice, once
  of each colour. Nobody who has it would choose colouring again.
- **Green threads** (Go, Java's virtual threads, Erlang): each task has a small stack of its own, and
  the runtime switches stacks where it would block. No colour. They work where a managed runtime owns
  every stack and every pointer on it; systems languages that tried them dropped them.
- **Zig 0.16** passes an `Io` to every function that does IO, and `main` picks the implementation:
  `Io.Threaded` (blocking calls on a pool of threads) or `Io.Evented` (stackful coroutines over
  io_uring and kqueue). Code is written once and runs on either. It separates "may run concurrently"
  (`async`, which can't fail) from "must" (`concurrent`, which can).
- **Structured concurrency** (Trio's nurseries, Swift's `async let` and task groups, Kotlin's
  `coroutineScope`, Rust's `thread::scope`): a task belongs to a scope, and the scope doesn't end
  until its tasks have. Rust's scoped threads may then borrow the starting frame's locals, which a
  detached thread can't. Swift cancels and awaits an `async let` the scope leaves without awaiting:
  leaving without the result means it wasn't wanted.
- **What the operating systems allow.** Sockets, pipes, timers and child processes can be waited on
  by an event loop. Regular files can't (epoll refuses them; kqueue reports them always readable),
  and Windows' console and inherited anonymous pipes can't be overlapped. So Go, Tokio and libuv run
  file IO on blocking threads anyway. An event loop's gain is in holding many sockets and pipes open
  at once, where a thread each costs memory and scheduling.

ctxlang already passes `Io`, `Fs` and `Proc` down from `main` as capabilities, which is Zig's shape,
and has binds (spec §4), which are its deferred calls, with an escape check that already knows what
they point into (spec §14). So this is Zig's design with capabilities and Rust's scoping, expressed
with what ctxlang has: no keywords, no colour, blocking code everywhere, a task's inputs passed as a
call's are, and the backend that runs tasks picked per executable.

## Shape

A **task** is a call of a `#task` fn, made by a bind that supplies every field, that may run
concurrently with the code that started it:

```
#task
fn load { mut fs: Fs, path: []u8, into: *mut Buffer } -> !usize { ... }

fn load_two { mut fs: Fs, mut threads: Threads, a: *mut Buffer, b: *mut Buffer } -> !usize {
    let mut ta: task::Task(!usize)
    let mut tb: task::Task(!usize)
    task::start{ &threads, task = &ta, run = load{ &fs, path = "a.txt", into = a, _ } }
    task::start{ &threads, task = &tb, run = load{ &fs, path = "b.txt", into = b, _ } }
    let na = try task::wait{ &threads, task = &ta }
    let nb = try task::wait{ &threads, task = &tb }
    return na + nb
}
```

- **A task is like `main`**: a declared entry point (`#task`) that receives exactly what it is given.
  Its context holds capabilities and data alike, supplied at the bind and checked as any call's are.
  Capabilities are passed explicitly (`&fs`), so the call site shows everything the task gets.
- **The handle is a local**, `task::Task(R)`, which also holds the task's result: `wait` returns the
  `R` the task returned, errors included.
- **A task never outlives its handle's scope.** A handle the scope leaves without waiting on is
  cancelled and waited on there, on every path out. So a task may borrow the starting frame's locals,
  and the compiler checks that it borrows nothing that ends before its handle does.
- **While a task runs, what it borrows is its own.** The starting frame can't use a place the task
  holds mutably, or write a place it reads, until it has waited.

IO stays the blocking calls std already has (`fs::read`, `proc::read`, `io::read`, and `net`'s); the
**backend** decides what blocking means:

- **Threaded** (first): each running task has a worker thread, and a blocking call blocks it. This
  covers disk, standard input and pipes completely, and sockets until there are so many that a
  thread each costs too much.
- **Evented** (designed below, built after): tasks are fibers on an event loop per thread, and a
  blocking call submits the operation and switches to another fiber.

## `#task`

```
#task
fn name(Generics) { fields } -> R { body }
```

1. `#task` on a fn with a body makes it a **task fn**: one that `task::start` and its kin can run.
   It is still a fn, which code may call directly and use as a value.
2. Its context may take any field but a **thread-bound** capability (below), directly or through
   one that includes it. The error is reported at the declaration, not at each start.
3. It may have generic parameters; each instance is a task fn.
4. Only a task fn can be a task's entry, and only through a bind written in the start's call
   (The API). So the program's task entries are a closed set the compiler knows, as `main` is one
   it knows. The Evented backend sizes each fiber's stack from it (The Evented backend).

`#task` doesn't restrict the data a task takes: once a task can't outlive what it borrows and owns
what it holds while it runs (Scoping), any data is safe to hand it. What can be unsafe on another
thread is a C library's state, which is the capability's to declare.

**`#thread_bound`** on a capability declaration says its library may be used only on the thread that
made it, or only on the main thread: OpenGL's contexts, GLFW, SDL's video. A capability that includes
a thread-bound one is thread-bound. A binding marks what its library's documentation says; the
compiler can't check the library. A task run at once (The API) runs on its starter's thread, but the
rule is the declaration's: a task fn never takes one, wherever it happens to run.

## Capabilities

```
// Whether the calling thread runs a task, and which: what std's blocking calls check.
namespace task { capability Cancel { #thread_local static current: u64 } }

capability Io { ..io::State, ..task::Cancel }
capability Fs { ..task::Cancel }
capability Proc { ..os::Proc, ..Io, ..proc::State }      // unchanged: Cancel comes through Io
capability Net { ..task::Cancel }                         // net.md

// Permission to run tasks, and the backend's state.
capability Threads { ..os::Threads, ..Mem, ..task::State, ..task::Cancel }
```

`main` receives `Threads` as it does today: every one of these has only statics or inclusions, so
each is a capability without fields (spec §15, rule 1). `Threads` includes `os::Threads`, the
layer's permission to start operating-system threads, which only `task`'s backend uses, and `Mem`,
since the backend keeps its table in pages from `mem::pages`. A program whose `main` or start fn takes
`Threads` is threaded (spec §15, Entry point, rule 8; Language changes, 9).

Capabilities stay granular (Decisions, 2): `Threads` is permission to run concurrently, not to do IO.
A task that reads files takes `Fs`, which its starter passes to the bind.

**Capabilities are shared, data is not.** Many tasks may hold `&fs` at once: a capability is
permission, and holding it isn't holding a place (Scoping, rule 4). In exchange, everything a
capability std hands out reaches must be safe from many threads at once: per-thread (`io`'s output
buffer, `#thread_local`), behind a lock, or atomic. Each of std's capabilities' statics is audited for
this before the backend is built (Order of work, 2).

A capability of a program's own that includes two of these, `capability App { ..Io, ..Fs }`, reaches
`task::Cancel`'s static twice, which spec §15 rule 9 forbids today; Language changes, 8 allows it.

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
    // A task's handle and, once it has ended, its result. Zero is no task. Only a local, a local
    // array's element, or a `mut` field (Language changes, 4): never copied, so it never moves
    // while its task writes its result into it.
    #task_handle
    struct Task(R) { ... }

    // Tasks that end together. Zero is an empty group. The same places as a Task.
    #task_handle
    struct Group { ... }

    error cancelled             // what a blocking call fails with, in a task that is cancelled
    error out_of_resources      // no thread, or no room in the table

    // Runs `run`, maybe concurrently with the caller, maybe at once. Returns no error: when the
    // backend can't run it concurrently (no worker, the limit, or the table can't grow), it runs it
    // here, and `task` holds its result when start returns. `task` must be zero.
    #starts_task
    fn start(R) { mut threads: Threads, mut task: Task(R), run: &fn{} -> R }

    // Runs `run` concurrently with the caller, or fails, and `task` stays zero.
    #starts_task
    fn start_concurrent(R) { mut threads: Threads, mut task: Task(R), run: &fn{} -> R } -> !

    // Runs `run` on an operating-system thread of its own, in every backend: for work that blocks
    // outside std (a C call that waits, a lock held across IO) or computes for long. In Threaded
    // it is start_concurrent.
    #starts_task
    fn start_blocking(R) { mut threads: Threads, mut task: Task(R), run: &fn{} -> R } -> !

    // Waits for the task to end and gives its result; `task` is zero again.
    fn wait(R) { mut threads: Threads, mut task: Task(R) } -> R

    // As `wait` without giving the result: true once the task has ended (then `wait` returns at
    // once), false when `nanoseconds` passed first. 0 looks without waiting.
    fn wait_for(R) { mut threads: Threads, mut task: Task(R), nanoseconds: u64 } -> bool

    // Asks the task to stop (Cancellation), waits for it to end, and gives its result, which is
    // usually `cancelled`; `task` is zero again.
    fn cancel(R) { mut threads: Threads, mut task: Task(R) } -> R

    // As start, start_concurrent and start_blocking, the task belonging to `group`. A group's task
    // returns `!`: the first of its tasks to fail cancels the others, and `wait_all` returns that
    // error. A group being cancelled starts its new tasks cancelled.
    #starts_task
    fn start_in { mut threads: Threads, mut group: Group, run: &fn{} -> ! }
    #starts_task
    fn start_concurrent_in { mut threads: Threads, mut group: Group, run: &fn{} -> ! } -> !
    #starts_task
    fn start_blocking_in { mut threads: Threads, mut group: Group, run: &fn{} -> ! } -> !

    // Waits until the group has no task, those started meanwhile included: the first error of
    // its tasks, or success.
    fn wait_all { mut threads: Threads, mut group: Group } -> !

    // Asks every task of the group to stop, then waits until it has none.
    fn cancel_all { mut threads: Threads, mut group: Group }

    // Fails with `cancelled` if the calling task has been asked to stop: for a task that computes
    // for long between blocking calls. Never fails outside a task.
    fn check_cancelled { mut threads: Threads } -> !

    // Busy workers past which `start` runs a task at once (Threaded backend, below).
    fn set_limit { mut threads: Threads, workers: u32 }

    // Stack for workers started after it; 0 for the default, 8 MiB.
    fn set_stack { mut threads: Threads, bytes: usize }
}
```

**`run` is a bind written in the call**, of a `#task` fn, supplying every field: `run = load{ &fs,
path, into, _ }`. Not a `fn` value, not a `&fn` local, not a bind of a bind. So the compiler sees
everything the task receives at the call that starts it, and the entry is a task fn it knows.

**The result lives in the handle.** A task's `R` is written into its `Task(R)` when it ends, and
`wait` or `cancel` hands it back. A group's tasks report through their binds' `mut` fields (each its
own place, `into = &results[i]`) and their errors through `wait_all`. `wait` returning makes
everything the task wrote visible to the waiter: the task's end and the wait meet under the table's
mutex.

**`start`, `start_concurrent` or `start_blocking`.** `start` says the caller doesn't need the task to
run at the same time as anything; it only allows it. So it returns no error, and code written with it
runs on any backend, on one with no concurrency at all, and in the interpreter. `start_concurrent`
says the program is wrong unless the task runs alongside the caller: a server's accept loop and its
handlers, a reader of a child's standard error while the caller reads its standard output. A task
that waits for something another task must do (a condition another signals, a pipe another fills)
needs the other started with `start_concurrent`. `start_blocking` is for work the backend can't see
waiting.

**A task run at once** runs as part of its starter: on the same thread, with the starter's slot as
`task::Cancel`'s `current`. Cancelling the starter reaches it, and its `check_cancelled` sees the
starter's flag. Its handle holds its result when `start` returns.

**Groups** are for tasks whose number isn't known: a crawler that finds more pages, a server's
connections. Any holder of the group may add tasks to it, its own tasks included, also while another
waits on it. `cancel_all` asks every task of the group to stop before it waits for any, so a task that
needs another of the group to notice cancellation isn't waited on first. A task of a group that waits
on or cancels its own group panics: it would wait for itself.

**Misuse panics**: `start` into a handle that isn't zero; `wait` or `cancel` on a zero handle, which
the compiler reports instead where it can see it (Scoping, rule 3); a group's own task waiting on it.

**What can still deadlock.** No task waits for a free worker (Threaded backend, No queue), so a task
never waits on one that will never start. A program can still deadlock as any threaded program can:
two tasks waiting on each other, a task holding a mutex when `start` runs a task at once that locks
it (mutexes aren't recursive), or a `start`ed task that waits on its starter's signal.

## Scoping

The rules that make a task's borrows safe. The compiler knows the handle types (`#task_handle`) and
the start functions (`#starts_task`); the rules are the escape check's (spec §14) and exclusivity's
(spec §3.1), extended over time.

1. **What a task borrows.** A start call's bind holds each place it takes as `&p` for a `mut` field,
   and its read-only arguments carry their origins (spec §14, rule 2): a slice of a local buffer is
   derived from that buffer. Together these are the task's **borrows**. Capabilities aren't among
   them (rule 4).
2. **The handle can't outlive them.** A start stores the bind into the handle (`mut task` or `mut
   group`): the handle is derived from every borrow, so the escape check's rules apply to it. Its
   local must be declared in a scope within each borrow's scope; it can't be returned, stored
   through a pointer, or held by a local of an outer scope. A local array of handles in the same
   scope as what the tasks borrow is fine. Through a `mut` field (a handle in the caller's frame,
   data reached through the caller's `mut` fields), the function's borrowing summary records which
   of its fields each handle field becomes derived from, and each caller checks the rule at its own
   call: so a function may start a task into its caller's handle, as `audio::start` does (Examples).
3. **A handle's scope ends its task.** When the scope of a local that is or holds a handle ends, by
   any path (falling through, `return`, `try`, `break`, `continue`), every task it still has is
   cancelled and waited on, its result dropped, as if `defer task::end{ &threads, &handle }` followed
   the declaration: after the scope's later `defer`s, before its earlier ones, so data declared before
   the handle still exists while its task ends. A handle that is zero ends nothing, so an array of
   handles of which some were never used needs no bookkeeping. The `Threads` this needs is the one
   the start was given; the compiler keeps it with the handle. The compiler reports a `wait` or
   `cancel` on a handle that is zero on every path to it, and a `start` into one that isn't.
4. **What a running task borrows is its own.** From a start until the handle is waited on or
   cancelled on every path (or its scope ends), the starting function can't use a place the task
   holds through a `mut` field, and can't write, or pass to a `mut` field, a place a borrow is
   derived from. It may still read those. A function that starts into a caller's handle passes this
   up in its summary, so its caller is held to it until it waits, itself or through a function whose
   summary says that it does. Capabilities are exempt: two tasks may each hold `&fs`, and the starter
   may keep using `fs`.
5. **Not checked**, as elsewhere (spec §3.1, rule 6; §14, rule 4): memory reached through a pointer
   that isn't from `&p` in a call, such as pages from `mem` or a `*mut Mixer` passed around, which
   tasks share as threads do, under a mutex or with atomics.

**No detach.** Every task ends inside the scope of its handle, so nothing outlives the code that
started it. A task that runs for the whole program, as the game's mixer does, has its handle in
`main` or in a function `main` waits on. Nothing needs a record that lives for the program, which is
what `#spawn`'s carrying and `#spawn{ owned = true }` were for.

## Cancellation

Each task has a flag and a cancel object (Capabilities), made with its slot and reset when the slot
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

**Checked before only**, by decision, each with its reason: `fs`'s calls (regular files, and
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
handles' scopes, which cancel their tasks (Scoping, rule 3). So cancelling a task reaches every task
it started, and a task never ends before the tasks it started. How a waiting task is woken: a waiter
records in its own slot what it waits on, under the table's mutex; `cancel` sets the flag under the
same mutex and broadcasts the condition the waiter waits on. The waiter checks the flag and the end
under that mutex before every wait, so neither can be missed.

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

What `task::State` holds and does, all of it std over the platform layer's threads:

- **The table.** Slots in pages from `mem::pages`, which grow as tasks start and are reused once their
  task has ended and been waited on, under one mutex. A slot holds the task's entry and record, the
  address of its result (its `Task`'s) or its group, the flag and the cancel object, what the task
  blocks on or waits on, its worker, and its state: running, ended. A slot's generation guards
  against a handle that names a reused slot.
- **The record.** A start copies the bind's record into memory the slot owns (Language changes, 5),
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
  the stack check to land in (a quarter of it, at least 1 MiB), as `thread::create` gave a thread.
  `set_stack` applies to workers started after it; an idle worker whose stack is smaller than
  the setting ends instead of taking a task. A task fn whose stack bound the compiler knows
  (The Evented backend) and that exceeds a worker's stack gets a worker of its own size.
- **A panic** in a task ends the program, as on any thread, reported as `panic in task NAME:`, NAME
  being the task fn's.

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
- **Stacks, from `#task`.** Every task's entry is a task fn the compiler knows, so it computes each
  one's **stack bound**: the deepest its frames can go, over the call graph below it. A task fn whose
  calls are all direct and not recursive has one; one that recurses or calls through a function
  value doesn't. A fiber for a task fn with a bound gets that bound and the headroom the stack check
  lands in; one without gets the default (256 KiB, `set_stack`). C frames aren't counted: a C call
  that needs more than is left stops at the guard page, as on a thread; deep or blocking C goes to
  `start_blocking`. Stacks are reserved, with a guard page, and committed as used
  (`CreateFiberEx`'s reserve and commit sizes; `mmap` with a `PROT_NONE` guard elsewhere). An ended
  fiber's stack goes to a pool by size for the next.
- **Locks and waits.** In an Evented program std's `mutex`, `condition`, `thread::sleep` and
  `yield_now` park the fiber rather than its thread: a fiber that can't lock waits in the mutex's list
  and the loop runs others, and an unlock from any thread wakes it through its loop. Otherwise fiber A
  holding a mutex across IO would leave fiber B on the same thread blocked on it forever. Calls into
  C block the loop's thread: `start_blocking` is for them.
- **Fibers never move between threads**: a loop runs its own, so `#thread_local` statics stay each
  thread's, as code that isn't a task expects.
- **What the loop submits**, by platform: Windows, IOCP for sockets, std's child pipes and files
  opened overlapped, and waits on child processes and the console's input; Linux, io_uring for files,
  sockets, pipes and timeouts, and pidfds for children; macOS, kqueue for sockets, pipes, standard
  input, children and timers. What can't be submitted goes to blocking threads behind the loop, as Go,
  Tokio and libuv do: Windows' inherited anonymous pipes, file system metadata everywhere, and regular
  files on macOS.
- **Cancellation** cancels the fiber's pending operation on its loop: `CancelIoEx` with its
  `OVERLAPPED`, an io_uring cancel, a kqueue delete; then the fiber resumes with `cancelled`.

## What a program without tasks pays

A program that doesn't take `Threads` starts no worker and links nothing of the backend. Its blocking
calls check `task::Cancel`'s `current`, which stays 0: a plain global in a program that isn't
threaded (spec §15, Entry point, rule 8), a thread-local in one that is. One load and a branch per
blocking call. A function with a task handle pays for its scope's end only where the handle might
still hold a task.

## Language changes

1. **`#task`** on fns (`#task`, above): a task fn, whose context takes no thread-bound capability.
2. **`#thread_bound`** on capability declarations, inherited by capabilities that include one.
3. **`#starts_task`** on std's start functions, in place of `#spawn`: a fn whose context has `run:
   &fn{} -> R` and either `mut task: Task(R)` or `mut group: Group`. At its calls, `run` must be a
   bind written in the call, of a `#task` fn, supplying every field (a bind that leaves none open,
   which ctxlang already allows), and Scoping's rules 1, 2 and 4 apply to it.
4. **`#task_handle`** on std's `Task(R)` and `Group`: a type that is or holds one may be only the type
   of a local, a local array's elements, or a `mut` field; never a read-only field, a result, a
   struct's field, a pointer's target or an optional's payload, as for `&fn` (spec §6, rule 1). It is
   never copied, so it doesn't move while a task writes into it. Its zero value is no task. Scoping's
   rule 3 ends what it holds when its scope ends.
5. **A task's record.** Inside a `#starts_task` fn, `@record_size(run)` is the size of `run`'s record,
   and `@record_copy(run, into)` copies it into `into` (a `[]mut u8` at least that long, aligned for
   any record) and returns a `fn{ record: *mut u8, result: *mut u8 }` that runs the copy and writes
   what it returns to `result`: the entry the backend keeps in a slot. Nothing else may use them.
6. **Borrowing over time.** Scoping's rules 2 and 4: a handle is derived from its task's borrows, and
   those borrows are held, as exclusivity holds a call's `mut` references, until the handle is waited
   on or cancelled on every path or its scope ends. Both follow `mut` fields through borrowing
   summaries (spec §14), which today leave origins through mutable arguments unchecked (spec §16,
   question 1): for handles they are checked.
7. **Removed**: `#spawn` (spec §15, rule 14) and carried functions; `thread::create`, `join`,
   `detach`, `Thread` and `Options`. `thread` keeps `sleep`, `yield_now` and `current_id`, and
   `mutex`, `condition` and `atomic` stay as they are.
8. **A static reached twice** (spec §15, rules 9 and 13): a capability may reach the same static
   through two inclusions, `..Io` and `..Fs` both reaching `task::Cancel`'s. It is one static for the
   program already, so nothing is duplicated; the rule against reaching a field twice stays for
   functions and C variables.
9. **Threaded programs** (spec §15, Entry point, rule 8): a program is threaded if `main` or its start
   fn takes `Threads` or a capability that includes it, or has a callback C may call from any thread.

## Examples

### Loading files at once

A handle per file, in a local array, so the loads' number is the caller's. Each load has its own
arena, since allocators aren't shared between tasks. `start` may run a load at once: the code is
right either way.

```
#task
fn load { mut fs: Fs, path: []u8, heap: *mut arena::Arena } -> !alloc::Bytes {
    return fs::read_all{ &fs, heap, realloc = arena::alloc, path }
}

fn load_four { mut fs: Fs, mut threads: Threads, paths: [4][]u8, heaps: *mut [4]arena::Arena, out: *mut [4]alloc::Bytes } -> ! {
    let mut loads: [4]task::Task(!alloc::Bytes)
    let mut i: usize = 0
    while i < 4 {
        task::start{ &threads, task = &loads[i], run = load{ &fs, path = paths[i], heap = &heaps[i], _ } }
        i = i + 1
    }
    i = 0
    while i < 4 {
        out[i] = try task::wait{ &threads, task = &loads[i] }   // a failure returns: the others end with the scope
        i = i + 1
    }
}
```

### A child's standard output and standard error

A child that fills its standard error's pipe while the parent reads only its standard output waits
forever, and so does the parent. Reading standard error in a task of its own ends that; it must run
concurrently, so it is `start_concurrent`. A reader keeps reading after its buffer is full, so the
child never waits on a full pipe. `kept` is a local of `run_tool`'s, which the task borrows: the
compiler checks that `errs_task` is declared within its scope, and that `run_tool` doesn't touch
`kept` until it has waited.

```
// Reads the pipe to its end, keeping what fits in `kept` and dropping the rest.
#task
fn drain { mut proc: Proc, pipe: proc::Pipe, mut kept: [65536]u8 } -> !usize {
    let mut len: usize = 0
    let mut scratch: [4096]u8
    let mut n = try proc::read{ &proc, pipe, into = scratch[..] }
    while n > 0 {
        let room = kept.len - len
        let take = if n < room { n } else { room }
        slice::copy(u8){ dst = kept[len..len + take], src = scratch[..take] }
        len = len + take
        n = try proc::read{ &proc, pipe, into = scratch[..] }
    }
    return len
}

fn run_tool { mut proc: Proc, mut threads: Threads, argv: [][]u8 } -> !i32 {
    let options = proc::Options{ stdout = proc::Stdio::pipe, stderr = proc::Stdio::pipe, .. }
    let mut child = try proc::spawn{ &proc, argv, options }
    let out_pipe = child.stdout ifnull { @panic("piped") }
    let err_pipe = child.stderr ifnull { @panic("piped") }
    let mut out_kept: [65536]u8
    let mut err_kept: [65536]u8
    let mut errs_task: task::Task(!usize)
    task::start_concurrent{ &threads, task = &errs_task, run = drain{ &proc, pipe = err_pipe, kept = &err_kept, _ } } iferr err{ error } {
        proc::kill{ &proc, child } iferr {}         // it would wait on standard error forever
        _ = proc::wait{ &proc, &child } iferr {}
        return error
    }
    let out_len = drain{ &proc, pipe = out_pipe, kept = &out_kept }
    let err_len = task::wait{ &threads, task = &errs_task }
    // A reader that stopped early leaves the child waiting on a full pipe: end it.
    if out_len is err or err_len is err { proc::kill{ &proc, child } iferr {} }
    let code = try proc::wait{ &proc, &child }
    _ = try out_len
    _ = try err_len
    return code
}
```

### A timeout

`wait_for` and `cancel` give a call a deadline. The task must run alongside, so it is
`start_concurrent`: `start` might run it at once, and the wait would begin after it had finished.
At the deadline the task is asked to stop; `cancel` returns when it has, which a call that can't be
interrupted delays (Cancellation).

```
let mut t: task::Task(!Response)
try task::start_concurrent{ &threads, task = &t, run = fetch{ &net, request = &request, _ } }
let response = if task::wait_for{ &threads, task = &t, nanoseconds = 5000000000 } {
    task::wait{ &threads, task = &t }
} else {
    task::cancel{ &threads, task = &t }      // task::cancelled, or what came first
}
```

### A server

A task per connection, in a group, so stopping the server (cancelling the task that runs `serve`)
stops every handler, and `serve` returning, by any path, waits for them: the group is its local.
`mem` gives pages and never takes them back, so a connection's memory is reused: a handler that ends
puts its `Connection` on the server's free list, under a mutex. A handler borrows nothing of `serve`'s
frame: `c` points into pages, which tasks share as threads do (Scoping, rule 5). `net`'s calls are
sketched here; net.md designs them.

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

#task
fn handle { mut net: Net, c: *mut Connection } -> ! {
    serve_requests{ &net, socket = c.socket } iferr {}  // requests and responses until the peer closes
    net::close{ &net, socket = c.socket }
    give_back{ server = c.server, c }
}

fn serve { mut net: Net, mut mem: Mem, mut threads: Threads, server: *mut Server, listener: net::Listener } -> ! {
    let mut handlers: task::Group
    while true {
        let socket = try net::accept{ &net, listener }      // fails with cancelled when serve's task is
        let c = take_connection{ &mem, server } ifnull {
            net::close{ &net, socket }
            continue
        }
        c.* = Connection{ socket, server, next = null }
        task::start_concurrent_in{ &threads, group = &handlers, run = handle{ &net, c, _ } } iferr err{ error } {
            net::close{ &net, socket }
            give_back{ server, c }
            return error
        }
    }
}
```

### The game's mixer

A task that runs as long as the game plays, started by one function and stopped by another. Its
handle is a local of the function that plays, which passes it down: `audio::start` starts into its
caller's handle, so the caller is held to what `pump` borrows (`dev`) until `audio::stop` cancels
it, or the game's loop ends and the handle's scope does. The running flag the thread version kept is
gone: cancelling is how it stops, and `thread::sleep` returns early when it is.

```
#task
fn pump { mut sdl: sdl::Sdl, mut threads: Threads, mut dev: Device, m: *mut mix::Mixer } -> ! {
    while true {
        try task::check_cancelled{ &threads }
        top_up{ &sdl, &dev, m, frames = dev.ahead } iferr {}
        thread::sleep{ &threads, nanoseconds = PUMP_SLEEP_NS }
    }
}

fn start { mut sdl: sdl::Sdl, mut threads: Threads, mut dev: Device, m: *mut mix::Mixer, mut mixer: task::Task(!) } -> ! {
    try task::start_concurrent{ &threads, task = &mixer, run = pump{ &sdl, &threads, &dev, m, _ } }
}

fn stop { mut threads: Threads, mut mixer: task::Task(!) } {
    _ = task::cancel{ &threads, task = &mixer }
}

fn play { mut sdl: sdl::Sdl, mut threads: Threads, ... } {
    let mut dev = try audio::open{ &sdl, rate = 44100, latency_ms = 60 }
    let mut mixer: task::Task(!)
    audio::start{ &sdl, &threads, &dev, m = &game_mixer, &mixer } iferr {}   // update() mixes without it
    // ... the game's loop: `dev` is the mixer's until stop; the mixer itself is shared under its lock
    audio::stop{ &threads, &mixer }
    audio::close{ &sdl, &dev }
}
```

`sdl::Sdl` here is SDL's audio, which SDL allows from any thread; a binding that splits SDL marks its
video capability `#thread_bound`, and `pump` couldn't take that.

## Order of work: the Threaded backend

Language work on its own branch (kotor/AGENTS.md, rule 1), one step at a time.

1. **Language** (Language changes): `#task`, `#thread_bound`, `#starts_task`, `#task_handle`,
   `@record_size` and `@record_copy`; handles' scopes ending their tasks; borrowing over time, with
   borrowing summaries through `mut` fields for handles; a static reached twice; threaded programs
   through an included `Threads`. Spec §2, §3.1, §14, §15 and §17. `#spawn` and `thread::create` stay
   until step 6 moves their users.
2. **The audit** of std's capabilities' statics for use from many threads at once (Capabilities).
3. **`task::Cancel`** in std, included in `Io`, `Fs` and `Threads`, and `task::check`,
   `get_cancel_object`, `begin_synchronous`, `end_synchronous`; `os::pipe_read`, `pipe_write`, `wait`
   and `wait_for` take `cancel`.
4. **The backend**: `task::State`, the table, slots' records and cancel objects, workers, the API
   above; a worker writes out its standard output when a task ends.
5. **Interruptible calls**, each row of Cancellation's table on Windows and POSIX: child pipes, child
   waits, standard input (console, pipe, file), sleep; `O_NONBLOCK` on this program's ends of child
   pipes on POSIX; the synchronous-read protocol on Windows; a cancelled `wait` keeping its `Child`,
   a cancelled `run` killing its own.
6. **Moving off threads**: KOTOR's mixer (`kotor/lib/audio`), `kotor/tools/mixtest` and the tests
   that use `thread::create`; then `#spawn`, `thread::create`, `join`, `detach` are removed.
7. **Tests**: corpus programs for each piece: start and wait; a result through the handle; `start`
   past the limit and with the limit at 0 running at once; `start_concurrent` for a pipe reader;
   cancel of a blocked pipe read, child wait, console read and sleep, and a second blocking call after
   each, which must not see a stale cancel; a handle's scope ending on each kind of exit with its
   task running, and with it zero; an array of handles partly used; a group's `cancel_all` reaching a
   task that waits on its own, a group's first error cancelling the rest, and a task added to a
   cancelled group; a task run at once cancelled with its starter; `wait_for` giving up; each misuse's
   panic; and compile errors for each rule: a task fn taking a thread-bound capability, `run` that
   isn't a bind in the call or isn't of a task fn, a handle declared outside a borrow's scope (also
   through a `mut` field), a held place used before the wait (also through a caller), a handle as a
   struct's field, a result or a read-only field, `wait` on a handle zero on every path. The
   interpreter running `start` programs and refusing `start_concurrent`. Then the bootstrap refresh
   (ctxlang/internals.md, "Changing the language").
8. **net.md and http.md**, written against this contract, then built.
9. **The Evented backend**: the stack switch on each ABI first, then the per-fiber state's audit, the
   stack bounds of task fns, then the loops.

## Decisions

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
7. **`#task` marks entries.** Only task fns start tasks, so the set is closed: stack bounds per task,
   thread-boundness checked at the declaration, and a place that says "this is a unit of concurrent
   work". A library function is started through a small task fn of the program's.
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

## Decisions made building it

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
7. **A bind written as a start's `run` has its size and its task fn's name in its record**, after
   its code: `@record_size` reads the size, and a worker names the task in a panic's report
   (`panic in task NAME:`) from the copy (`rt::task_name`).
8. **The interpreter refuses `start_concurrent`** through the platform layer: `os::CONCURRENT` is
   false there, and `os::concurrency_unsupported` stops the run.
9. **On Linux a child started with `die_with_parent` from a task ends with the worker's thread**
   (`PR_SET_PDEATHSIG`), which may end 10 seconds after the task, when the worker has waited for
   another in vain.
10. **KOTOR's mixer shares its device through a pointer** (rule 5), as the thread did: the game
   reads `pumping` and `underruns` while it runs, so the device can't be the task's alone.

## Open questions

1. **`Threads` includes `Mem`**, since the table lives in pages, so whoever holds `Threads` may
   allocate pages. Should the backend reach the layer's pages through a capability of its own instead,
   so `Threads` grants nothing but tasks?
2. **Groups' results.** A group's tasks report through their binds' `mut` fields; should a group
   collect results of one type itself, `Group(R)`, for crawlers and fan-outs?
