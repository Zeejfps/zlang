# serve: an HTTP/1.1 static file server in ctxlang

A program people would run, written to bring `net` and the server half of `http` into std
(ctxlang/docs/todo/net.md, http.md) and to be the first program that runs many tasks at once.
Scope agreed with the owner on 2026-11-25.

## What it does

- `serve DIR --port 8080`: GET and HEAD of files over plain HTTP; a directory answers with its
  `index.html` or a generated listing; content types by extension; 400, 404, 405, 431 and the other
  error responses `serve_connection` gives.
- A task per connection in a `task::Group`, kept alive across requests, with `http::Limits`'s
  deadline for a request's head.
- Ctrl-C stops it gracefully: stop accepting, give the connections a grace period
  (`task::wait_all_for`), then cancel what is left.
- An access log on standard output, written from every connection's task.
- `/stats`: requests and connections counted with atomics shared across tasks, as JSON.

## Out of scope

- **TLS, HTTP/2, HTTP/3, compression, ranges**: http.md, Out of scope, gives each one's reason.
- **CGI and dynamic routing**: each is a program of its own over the same server; `/stats` is the
  one dynamic answer this program needs to share state across tasks.
- **Name lookup, UDP, the HTTP client**: a server listening on an address doesn't use them. They
  stay in net.md's and http.md's order of work.

## Platforms

Windows is built and run. Linux and macOS layers are checked by compiling only (the owner's
decision): std is compiled into every program, so each layer must compile, but the owner has no
Linux or macOS machine to run them on.

## Order of work

One agent at a time, each verified with the whole suite and committed (by the owner) before the
next.

1. **`task::wait_all_for`** (net.md, Order of work, 1).
2. **Link by use**, `#c::link` on capabilities (net.md, 2): Windows' sockets need `ws2_32`.
3. **Addresses** (net.md, 3).
4. **TCP on every layer** (net.md, 4 and 5, committed together): Windows run, Linux and macOS
   compiled.
5. **The server test and net's docs** (net.md, 8).
6. **url's percent decoding**, for request targets (http.md, 1).
7. **Heads, then bodies' framing and chunked coding** (http.md, 2 and 3).
8. **The server**: `read_request`, `send_response`, `serve_connection`, `respond` (http.md, 6).
9. **Ctrl-C**: a std function a program waits on until the console asks it to stop
   (`SetConsoleCtrlHandler` on Windows, `SIGINT` and `SIGTERM` on Linux and macOS). Not in either
   design: designed in its own step. On Windows the handler is a C callback on a thread of the
   system's, a threaded program found by its callback (spec §15).
10. **The program**, here in `serve/`, and its load test.

## What it should settle

- **The designs predate `&thread fn`.** http.md's Decision 7 (the accept loop is the program's)
  rests on the old rule that a start's `run` is a bind of a task fn written in the call. The
  program writes its own accept loop first; then whether std gets an `http::serve` taking a
  `&thread fn` handler is decided from that code. Steps 4 to 8 bring net.md's and http.md's
  examples up to the current spec as they make them compile.
- **What the Threaded backend costs**: a blocked worker per idle keep-alive connection. A load test
  with about a thousand idle connections and a flood of requests measures it, the case for or
  against the Evented backend next (threads.md).
- **Friction** from state shared across tasks (the log, the counters) goes into
  ctxlang/docs/todo/friction.md as it is found.

## Built

Step 10, in serve/: `kotor/tools/ctxc exe serve -o serve/out/serve.exe` from the repository's root
(serve/out is ignored, as kotor's is), and `kotor/tools/ctxc test serve` for its tests.

- **Layout.** build.ctx (`-O2`, call paths kept for panics, the unchecked operations denied in
  every file); src/main.ctx, the command line; src/run.ctx, `main`, the acceptor, a task per
  connection, and stopping; src/site.ctx, what is answered; src/paths.ctx, a target as a path
  under the root; src/mime.ctx, content types; src/access.ctx, the log, its journal and the
  times; src/*_test.ctx. A request's buffers come from std's heap (`heap::alloc`, spec §17); serve
  carried its own copy of kotor's C heap in src/heap until std had one (friction.md, 43), and has
  no unchecked code of its own since. tools/load is the load generator, a program of its own
  (`kotor/tools/ctxc exe serve/tools/load -o serve/out/load.exe`); tools/measure.ps1 runs the
  load test.
- **`serve DIR [--port N] [--address A] [--grace SECONDS] [--connections N]`**, on 127.0.0.1:8080
  unless told otherwise: a server someone starts on a directory shouldn't reach the network until
  they say so. Port 0 lets the system pick; the first line says where it is.
- **Targets** are percent-decoded first, then their dot segments resolved, so no spelling of `..`
  escapes the check: `..` above the root is 403; a segment with `\`, `:` or a zero byte, only dots
  and spaces, or a Windows device name (CON, NUL, COM1...) is 404 on every platform, since no
  file under the root has that name on Windows; a target that isn't a path, or a bad escape, is
  400. Symbolic links are followed, as the system follows them.
- **Files are streamed**: Content-Length from the size, the body read and sent 64 KiB at a time
  (`write_body`), so a file of any size takes 64 KiB. A file that shrinks while it is sent ends
  the connection, as `finish_body` does for a short body. A directory without its `/` is
  redirected (301); with it, it is its index.html or a listing (links percent-encoded, names
  escaped as HTML). GET and HEAD only, else 405 with `Allow: GET, HEAD`. Every response has Date
  and Server. Not done, with reasons: Last-Modified and conditional requests (std's fs has no
  modification time, and caching is out of scope as ranges are), and a per-connection limit on
  requests (`Limits.requests` stays 0: nothing here is worth a reconnect).
- **The access log** is a line per request, from the task that answered it, with the time (std's
  new `clock`, below), the client, the request line escaped, the status, the body's bytes and the
  duration; serve_connection's refusals (400, 431, 501, 505) are logged by the connection's task.
  A connection that fails otherwise (a reset, a head past its 30-second deadline, a handler's
  error) fails alone: the connections' group keeps its failures (`task::Failures::keep`), and the
  acceptor logs each as a `serve: a connection failed: net::reset` line after each accept, or
  once a second without one (the accept runs under `task::run_within`). Only the group's holder
  reads them, and the acceptor holds it while it runs, so a reporter task of its own couldn't;
  once the acceptor is cancelled, `run` reads what is left, before `cancel_all` drops it.
  Lines go through a journal, a shared buffer under a mutex, which one writer task writes out:
  whole, in the order the answers ended, at once when the server is quiet and in batches under
  load (Findings 2 says why not a flush per line).
- **/stats** is JSON of counters that every task changes with relaxed atomics: connections
  accepted, open, refused, failed (each logged) and dropped (failed past the 64 the group holds
  between looks, counted with `task::count_dropped` and logged as a number); requests, by status
  class; body bytes; uptime.
- **Stopping**: the first Ctrl-C stops the acceptor, sets a flag that makes each response say
  `Connection: close`, and gives the connections `--grace` seconds (5, or 3 when the system asks)
  with `task::wait_all_for`, then cancels the rest; a second Ctrl-C ends it at once (std's stop).
  A connection that is idle between requests is held until the grace period ends, as http.md's
  Stopping says. An acceptor that fails asks the program to stop with `stop::ask`, so `main` sees
  it.
- **Connections** past `--connections` (4096) are closed as they are accepted and counted refused.
- **std's clock** (spec §17, `clock`): `read_monotonic`, `read_wall` and `to_utc`, under a
  `Clock` capability that starts no thread (friction.md, 38). The log needs a wall clock and a
  duration, and std had neither for programs (`os::now` is the task backend's, to the millisecond
  on Windows). Built on every layer (QueryPerformanceCounter and GetSystemTimePreciseAsFileTime on
  Windows, clock_gettime on Linux and macOS, compile-checked; the interpreter has none), tested
  in tests/cases/Clock.
- **Tested** by tests/cases/Serve/python_peer: `ctxc test serve` (11 tests: targets resolved and
  refused, log lines, dates, content types), then serve built by its build program and run
  against Python's http.client and raw sockets (tests/helpers/serve_peer.py) on a temporary
  directory: files, HEAD, 3 MiB compared byte for byte, listings, a redirect and an index, 404,
  403 and 405, traversals plain and encoded, a broken head, /stats, `--connections 1`, and a
  graceful stop by Ctrl-Break, with a kept-alive connection's request answered with
  `Connection: close` during the grace period and an idle one cancelled at its end, then a second
  Ctrl-Break ending a server at once. Each request's log line is awaited before the next request.

## Findings

Measured on Windows 11, an AMD Ryzen 9 9950X3D (16 cores, 32 threads), client and server on one
machine over loopback, with serve/tools/measure.ps1: tools/load holds N idle kept-alive
connections (each asked for the file once), then 16 clients flood the server for 10 seconds,
each on a kept-alive connection; Get-Process samples the server while the idle connections are
held and in the middle of the flood. The access log went to a file. Latencies are in
milliseconds, from a request's first byte sent to its response's last byte read.

### 1. Decision 7: no `http::serve`

The program's own loop is `accept_into` and `connection` in src/run.ctx: about 45 lines, of which
the part `http::serve` could take is a dozen (accept, retry on `aborted` and `too_many_open`,
start a task in a group, the buffers, `open`, `serve_connection`).

- **It can't be written in std today.** A start's `run` must be a bind written in the call (spec
  §15, Tasks, rule 3), so `serve` couldn't start `connection{ ..., handle, _ }` around a handler
  its caller passed as a value: what a function value holds can't be seen, and the handler would
  run on every connection's thread at once. It would take a new kind of function value that may
  be called from many tasks at once (one that holds capabilities and pointers but no `&` places,
  which the checker could see at the bind that makes it), or an unchecked start in std. Neither
  is small (friction.md, 51).
- **What it would save is where the program's policy lives.** serve's loop counts accepted,
  open and refused connections for /stats, refuses past `--connections`, takes the client's
  address for the log, logs serve_connection's refusals (which no handler sees: friction.md,
  42), and asks the program to stop when accepting fails. An `http::serve` would need a hook for
  each, or a config struct, and would still leave stopping (the group held outside the acceptor,
  `wait_all_for`, the flag) to the program.
- **Recommendation: keep Decision 7.** What would help instead is smaller: serve_connection
  saying what it refused (friction.md, 42). A group whose tasks fail alone, the other thing
  this asked for, is std's now (`task::Failures::keep`, 910508b2), and `connection` returns its
  error instead of dropping it.

### 2. What the Threaded backend costs

16 clients asking for a 6-byte file, each connection reading its heads under a deadline on its
own thread (`task::run_within`, below):

| Idle connections | Threads, idle held | Private memory, idle held | Threads, flooding | Requests/s | p50 | p90 | p99 | p99.9 | Max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 3.5 MiB | 22 | 27,036 | 0.589 | 0.660 | 0.746 | 0.863 | 6.62 |
| 100 | 106 | 10.7 MiB | 122 | 27,099 | 0.589 | 0.655 | 0.724 | 0.805 | 3.33 |
| 1,000 | 1,006 | 76.2 MiB | 1,022 | 26,734 | 0.593 | 0.668 | 0.839 | 1.018 | 4.43 |
| 4,000 | 4,006 | 293.6 MiB | 4,022 | 27,089 | 0.589 | 0.656 | 0.728 | 0.799 | 6.55 |

Before, when each head was read in a task of its own (http.md, Decision 15, as first built), and
before std's Windows file calls stopped putting 64 KiB on the stack (friction.md, 49, fixed by 6c6b1f43):

| Idle connections | Threads, idle held | Private memory, idle held | Threads, flooding | Requests/s | p50 | p90 | p99 | p99.9 | Max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 3.6 MiB | 30 | 25,612 | 0.622 | 0.695 | 0.776 | 0.862 | 6.94 |
| 100 | 206 | 27.0 MiB | 231 | 25,556 | 0.624 | 0.696 | 0.776 | 0.861 | 6.90 |
| 1,000 | 2,006 | 237.9 MiB | 2,033 | 25,339 | 0.626 | 0.705 | 0.826 | 0.993 | 7.46 |
| 4,000 | 8,006 | 948.8 MiB | 8,029 | 25,213 | 0.632 | 0.704 | 0.781 | 0.853 | 6.98 |

/stats, an answer from memory: 111,105 requests/s with no idle connections (p50 0.133, p99
0.341) and 118,951 with 1,000 (p50 0.124, p99 0.323), with the head's task. So the server's own
ceiling is about 115,000 requests/s here, and a file's about 25,000 to 27,000, which is Windows'
file calls (a size, an open, a read and a close per request): Go's net/http FileServer on the
same files and machine does 19,300 to 22,100 with Go's client and 21,900 to 23,800 with
tools/load, and serve, with the head's task, did 20,800 to 21,200 with Go's client (each from 4
clients to 64). By clients, on the file, with the head's task: 1 client 8,220/s (p50 0.128), 4
clients 23,301/s (0.170), 16 clients 22,380/s (0.710), 64 clients 20,908/s (2.904).

- **1,000 idle connections fit, and 4,000 do**: throughput and latency don't move with them.
  `task::set_limit` (64 busy workers) bounds only `start` and `start_in`, which run a task at once
  past it; a server starts its tasks with `start_concurrent_in`, which the limit doesn't bound,
  so each connection has its thread. Workers' stacks are 8 MiB, reserved (CreateThread's
  STACK_SIZE_PARAM_IS_A_RESERVATION) and committed as they are touched: 4,006 threads reserve
  31 GiB of a 64-bit address space's 128 TiB, and commit what Get-Process calls private. The
  task table holds 65,536 tasks, so it stops at 65,536 idle connections, one task each; serve's
  own `--connections` (4,096) stops first.
- **An idle connection costs one thread and about 73 KiB**, its own task waiting in
  serve_connection's receive, once it has asked for the file: 1,000 of them 76.2 MiB, from 3.5
  MiB with none. A task that only sleeps costs 37 KiB (1,000 sleeping tasks: 1,004 threads, 37.7
  MiB); the rest is the 16 KiB buffer, the fields, and the stack the file's request reached,
  since a thread's stack stays committed at the deepest it has been. It was two threads and 172
  KiB with the head read in a task of its own (175.6 MiB at 1,000, measured with the same build
  of std otherwise: main with friction.md's 49), and 238 KiB before that, when std's Windows layer
  put a 64 KiB UTF-16 path on the stack in each file call (friction.md, 49, fixed by 6c6b1f43). Before serve moved
  its request buffers (the decoded target, the path, the 64 KiB file chunk) from the stack to the
  C heap, a file's idle connection cost 376 KiB: that move is in site.ctx, with the reason.
  They come from std's heap now, measured the same (76.2 MiB at 1,000 idle, 26,800 to 27,200
  requests/s on the small file); a request's arena over `mem::reserve`, given back with
  `mem::release`, measured the same idle but 4 to 8% slower, and site.ctx says why the heap stays.
- **The head's deadline is `task::run_within`'s**, on the connection's thread (http.md, Decision
  15): a deadline the blocked receive's own wait observes, as it observes a cancel, instead of a
  task that is cancelled. With one client asking for the file, 1,000 idle connections held: 10,446
  requests/s (p50 0.083 ms, p99 0.160) against 8,577 (p50 0.104, p99 0.176) with the head's task,
  and with none held 10,503 (0.083) against 8,683 (0.103), both builds measured back to back. The
  task cost a worker's wake and a wait per request, about 20 µs; from 4 clients on, the
  machine's processors hid it. A build that read heads without any deadline had done 10,555 with
  one client: the deadline itself costs nothing to measure. Each blocking call under one reads
  the performance counter twice.
- **The log was the bottleneck, not the threads.** Flushing each line from the task that wrote it
  (one write of the system's per request, which every connection's thread queued for) gave 3,839
  to 4,124 requests/s with a p50 of 3.8 ms; the journal and its writer task give 25,600. With the
  log thrown away (NUL), a flush per line did 22,000 to 24,000: the cost is the file's.

**The Evented backend: not yet.** At a thousand connections, and at four thousand, the Threaded
backend's cost is memory and threads, not throughput or latency: serve matches Go's evented
net/http on the same files, and idle connections don't slow the busy ones. What it costs is
about 73 KiB and a thread per idle connection: about 290 MiB at 4,000, about 730 MiB and 10,000
threads at 10,000, where Windows' scheduler and the task table become the limits, and where
Evented's fibers would be the answer. It was 240 KiB and two threads until std's Windows file
calls stopped putting a 64 KiB path on the stack (friction.md, 49, fixed by 6c6b1f43) and a head's deadline stopped
taking a second thread (`task::run_within`). The case for Evented is a server meant for ten
thousand connections or more, which serve isn't.

### 3. Friction

Entries added to ctxlang/docs/todo/friction.md during this plan:

- 38 (*Partly*, step 10): no clock without `Threads`; std's `clock` now reads both clocks under
  a `Clock` that starts no thread, which the test runner can take.
- 39 (step 7): storing through a read-only slice of `mut` elements needs the slice `mut` too
  (`mut headers` on every parser).
- 40 (*Fixed*, step 8): a group's tasks couldn't fail alone, so a connection's task dropped its
  error; a handle declared with its settings (583add53) and a group that keeps its failures
  (910508b2) answer it, and serve's connections fail alone, each failure logged and counted.
- 41 (step 9): a callback any thread calls can't reach its namespace's statics without a forged
  capability (stop's handler).
- 42: serve_connection doesn't say what it answered, so a log maps errors back to statuses.
- 43 (*Fixed*): std had no general-purpose heap, so serve wrote kotor's over C's malloc again;
  std's `heap` (1c129692) and `mem::release` (7a9ef685) answer it, and serve uses std's heap.
- 44: a task's standard output is its thread's buffer: a log from many tasks needs a journal of
  the program's own, or a write per line, which cut throughput to a sixth.
- 45: a type's `@fmt` writer reaches one sink (`net::Address` into a Builder only).
- 46: an error doesn't become a `?error` in one step.
- 47: std has no sort.
- 48: `condition::wait` can't be cancelled.
- 49: Windows' file calls put a 64 KiB path buffer on the stack, which stays committed.
- 50: `ctxc exe -o` into a missing directory fails in the linker.
- 51: a function value can't be started as many tasks (what keeps `http::serve` out of std).
