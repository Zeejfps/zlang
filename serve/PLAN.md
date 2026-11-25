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
