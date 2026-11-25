# Concurrent IO: what is left

The Threaded backend is built: the language's side is spec §15, Tasks; the API std/task.ctx; how it
behaves and why, internals.md, Tasks. Left:

1. **net and http**, designed in [net.md](net.md) and [http.md](http.md), written against the
   built backend.
2. **The Evented backend**, below: the stack switch on each ABI first, then the per-fiber state's
   audit, the stack bounds of task fns, then the loops.

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
- **Stacks, from each start's bind.** Every task's entry is the fn its start's bind names, which
  the compiler knows, so it computes each one's **stack bound**: the deepest its frames can go, over the call graph below it. A task fn whose
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

A test build may also pick a backend that simulates IO and time (internals.md, Tasks, Decisions, 10),
if one is wanted.

## Open questions

1. **`Threads` includes `Mem`**, since the table lives in pages, so whoever holds `Threads` may
   allocate pages. Should the backend reach the layer's pages through a capability of its own instead,
   so `Threads` grants nothing but tasks?
2. **Groups' results.** A group's tasks report through their binds' `mut` fields; should a group
   collect results of one type itself, `Group(R)`, for crawlers and fan-outs?
