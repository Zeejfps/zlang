# HTTP: design

Status: **design**, threads.md's step 8, after net.md. Nothing here is built. HTTP/1.1, client and
server, written in ctxlang over `net` and `tls` (net.md), with URLs (`url`) and WebSocket
(`websocket`) beside it.

## Why

Fetching and serving over HTTP is most of what a program does with a network. It is a protocol over a
byte stream, not a system interface, so it is ctxlang code over `net::Socket` and `tls::Stream`, and
runs the same on every platform and backend. What it needs from the language is what std already
gives: buffers the caller passes, blocking calls a task can cancel, and tasks for deadlines and for a
server's connections.

## What other languages learned

- **Go's net/http** runs a goroutine per connection behind a `Handler` interface, and its client keeps
  a pool of connections per host in a shared `Transport`, follows up to 10 redirects, and reads proxy
  settings from the environment. Each of these is state or policy the library holds for the program;
  the pool's idle connections and the hidden timeouts are its most reported surprises.
- **Python's h11** is "sans-IO": the protocol is a state machine fed bytes and asked for bytes, with
  no socket in it. Its parsing is then testable at every byte boundary without a network, and any IO
  layer can drive it.
- **Zig's std.http** parses a message head in place, in a buffer the caller gives, and hands out
  slices of it; the buffer's size is the head's limit.
- **Request smuggling** (a front end and a back end disagreeing on where a body ends) taught every
  server to refuse a message with both `Content-Length` and `Transfer-Encoding`, or with two different
  lengths, and to refuse obsolete line folding; RFC 9112 codifies it.
- **HTTP/2 and HTTP/3** are what browsers use, but every server that speaks them speaks HTTP/1.1 too,
  chosen by ALPN or advertised over it (`Alt-Svc`).

So: a sans-IO core over caller buffers, a thin layer that drives it over `net` or `tls`, no hidden
pools or timeouts, and tasks for what is concurrent.

## Shape

```
fn main { mut io: Io, mut net: Net, mut mem: Mem, args: Args } -> i32 {
    let pages = mem::reserve{ &mem, size = 67108864 } ifnull { return 1 }
    let mut heap = arena::new{ buf = pages }
    let got = http::fetch{ &net, &heap, realloc = arena::alloc, url = args[0], options = http::FetchOptions{ .. } } iferr err{ error } {
        _ = @fmt(&io, "fetch failed: {}\n", error)
        return 1
    }
    _ = @fmt(&io, "{} {} bytes\n", got.status, got.body.len)
    return 0
}
```

Three levels, each usable alone:

1. **The core** (sans-IO): parsing a message head in a buffer into slices, deciding how its body is
   framed, decoding and encoding chunked bodies, writing heads into a buffer. No capability; runs in the
   interpreter.
2. **Connections**: a `Connection` over a socket or a TLS stream, with a buffer the caller gives;
   `send_request`, `read_response`, `read_body` for a client, `read_request`, `send_response` for a
   server. Blocking, cancellable through `net`.
3. **Helpers**: `fetch` (a whole request with redirects, the body into an allocator) and
   `serve_connection` (one connection's requests, each answered by the program's function).

## The core

```
namespace http {
    // A header field: a name and a value, slices of the buffer the head was read into or of the
    // caller's own bytes. Values are bytes, not utf8::String: HTTP's field values are octets
    // (RFC 9110 §5.5), which needn't be UTF-8.
    struct Header { name: []u8, value: []u8 }

    // The first field named `name`, compared without ASCII case; null if there is none.
    fn find_header { headers: []Header, name: []u8 } -> ?[]u8

    // The index of the next field named `name` at or after `from`: for fields that repeat.
    fn find_header_from { headers: []Header, name: []u8, from: usize } -> ?usize

    // Whether a comma-separated field value holds `token`, without ASCII case:
    // has_token{ value = "keep-alive, Upgrade", token = "upgrade" } is true.
    fn has_token { value: []u8, token: []u8 } -> bool

    // How a message's body ends (RFC 9112 §6.3).
    union Framing {
        none,                       // no body: HEAD's response, 1xx, 204, 304, a request without either field
        length{ n: u64 },           // Content-Length
        chunked,                    // Transfer-Encoding: chunked
        until_close,                // a response that ends when the server closes
    }

    // How a body this end sends is framed: what send_request and send_response write.
    union Body {
        none,
        bytes{ bytes: []u8 },       // all of it, with its Content-Length, in the same write as the head when it fits the buffer
        length{ n: u64 },           // n bytes, which write_body then sends
        chunked,                    // write_body sends chunks, finish_body the last
    }
}
```

**Lookup is case-insensitive and allocates nothing**: headers are a slice of `Header`s, the caller's
array, whose names and values point into the connection's buffer; `find_header` walks it. A program
with many lookups per message builds its own index; HTTP messages have tens of fields, which a walk
handles faster than a hash.

**What the parser refuses** (RFC 9112), with `malformed{ at }`, the offset in the head: a request line
or status line that isn't `METHOD SP target SP HTTP/1.x` or `HTTP/1.x SP 3DIGIT SP reason`; a field
name with anything but a token's characters, or whitespace before its colon; obsolete line folding (a
line starting with space or tab); bare CR; a message with both `Content-Length` and
`Transfer-Encoding`; two `Content-Length`s that differ, or one that isn't digits or overflows a `u64`;
a `Transfer-Encoding` whose last coding isn't `chunked` (`unsupported_coding` if it names a coding
besides `chunked`: http doesn't decode gzip or deflate). A version other than 1.0 and 1.1 is
`unsupported_version`. Lines end in CRLF; a bare LF is accepted as one, as RFC 9112 §2.2 allows.

**Chunked**, both ways: the decoder takes chunk sizes of at most 16 hex digits, ignores chunk
extensions, and reads trailer fields and drops them (RFC 9110 §6.5.1 lets a recipient discard them,
and nothing here uses them: trailers carry what HTTP/2's gRPC needs, which is out of scope). The
encoder writes a chunk per `write_body`, and `finish_body` writes `0\r\n\r\n`.

The core's functions are a parser over a buffer (`parse_request_head`, `parse_response_head`,
returning how much of the buffer the head took, or null while it is incomplete), `frame_request` and
`frame_response` (the Framing, from the head and, for a response, the request's method and the
status), a chunk decoder that is a struct fed bytes and giving body bytes (`Chunked`, `decode`), and
writers of heads into a buffer. Connections use them; a program over another transport may too.

## Connections

```
namespace http {
    // What a connection reads and writes: a socket, or a TLS stream over one. The connection
    // owns neither: the program closes them.
    union Stream {
        plain{ socket: net::Socket },
        secure{ tls: *mut tls::Stream },
    }

    // One HTTP/1.1 connection, a client's or a server's. `buffer` is the caller's: it holds a
    // message head, so its length is the longest head this connection takes, and what was
    // received past the head, which the body reads from first. 16 KiB is a good size.
    struct Connection {
        stream: Stream,
        buffer: []mut u8,
        start: usize,                   // received bytes not yet consumed: buffer[start..end]
        end: usize,
        reading: Framing,               // what is left of the body being read
        chunked: Chunked,               // its decoder's state, when it is chunked
        writing: Framing,               // what is left of the body being written
        method_head: bool,              // a client's last request was HEAD: its response has no body
        keep: bool,                     // whether the connection may carry another message after this one
    }

    fn open { stream: Stream, buffer: []mut u8 } -> Connection
}
```

### A client's

```
namespace http {
    struct Request {
        method: []u8 = "GET",
        target: []u8 = "/",             // what the request line names: a path and query, or, to a proxy, a whole URL
        host: []u8,                     // the Host field's value: a URL's authority
        headers: []Header = [],         // others; not Host, Content-Length, Transfer-Encoding or Connection, which http writes
        body: Body = Body::none,
        close: bool = false,            // ask the server to close after this exchange
    }

    struct Response {
        version: u8,                    // 10 or 11
        status: u16,
        reason: []u8,
        headers: []Header,              // a slice of the caller's array, pointing into the connection's buffer
        framing: Framing,
        keep_alive: bool,               // whether the connection may carry another request once this body is read
    }

    // Writes a request's head, and its body if it is `bytes`. A body that is `length` or
    // `chunked` follows with write_body and finish_body.
    fn send_request { mut net: Net, mut conn: Connection, request: Request } -> !

    // Writes some of a body: all of `bytes`, as a chunk if it is chunked. A `length` body fails
    // with body_too_large past its length.
    fn write_body { mut net: Net, mut conn: Connection, bytes: []u8 } -> !

    // Ends a body: the last chunk, or a check that a `length` body was all written (malformed
    // otherwise, and the connection can't be reused).
    fn finish_body { mut net: Net, mut conn: Connection } -> !

    // Reads a response's head into the connection's buffer and `headers`. 1xx responses but
    // 101 are read and passed over.
    fn read_response { mut net: Net, mut conn: Connection, headers: []mut Header } -> !Response

    // Reads at most into.len bytes of the body: how many, 0 at its end. Chunked bodies come
    // de-chunked.
    fn read_body { mut net: Net, mut conn: Connection, into: []mut u8 } -> !usize

    // The rest of the body in memory from an allocator; body_too_large past `limit` bytes.
    fn read_whole_body(S) { mut net: Net, mut conn: Connection, mut heap: S, realloc: alloc::Fn(S), limit: usize } -> !alloc::Bytes

    // Reads the rest of the body and drops it, so the connection can carry the next request.
    fn discard_body { mut net: Net, mut conn: Connection } -> !
}
```

**Keep-alive and reuse.** A connection carries requests one after another: once a response's body has
been read to its end and `keep_alive` is true, `send_request` may send the next on it. `keep_alive` is
HTTP/1.1's default unless either end said `Connection: close`, and HTTP/1.0's only with
`Connection: keep-alive`; an `until_close` body ends it. Sending a request while the last response's
body is unread is the program's error, and panics, as a task handle's misuse does: reading or
discarding it is a decision about the server's bandwidth that http won't make silently.

**No pool.** http keeps no connections between calls. A pool is state shared by tasks (a lock, memory,
connections keyed by host and TLS config, idle limits, and what to do with a connection the server
closed while it sat idle), which is policy a program sets for itself; a program keeps its connections
in its own structures, per task or behind its mutex. What keep-alive gives most of, reusing one
connection for a sequence of requests, is the API above.

**No pipelining** by the client: one request at a time, since a server may close after any response
and the requests after it would be lost with no way to tell which ran. A server reads pipelined
requests in order (the next head is already in the buffer).

**`Expect: 100-continue`** isn't sent by the client: it trades a round trip for not sending a body the
server will refuse, and a server must read or close in either case. A server answers it (below).

**Proxies** are the program's: the proxy's address, from the environment or the system's settings,
which differ per platform, isn't http's to read. Through an HTTP proxy, a program connects to it and
sends `target` as the whole URL; for HTTPS, it sends `CONNECT host:443` with `send_request`, reads the
response, and begins TLS on the same socket with `tls::begin_client`. Both are the API above.

**Cookies and authentication** are headers the program writes and reads. A cookie jar is a policy
store (domains, paths, the public suffix list), the program's to keep. Basic authentication is a
header with base64 (`base64`, WebSocket's package); Digest and other schemes are out of scope, since
servers that use them use them with TLS-terminated proxies and they are a header each way over this
API.

### A server's

```
namespace http {
    struct Incoming {
        method: []u8,
        target: []u8,
        version: u8,
        headers: []Header,
        framing: Framing,
        keep_alive: bool,
        expects_continue: bool,         // Expect: 100-continue: send_continue before reading the body
    }

    // Reads a request's head. Null when the peer closed the connection before a new request
    // began, which is how a kept-alive connection ends.
    fn read_request { mut net: Net, mut conn: Connection, headers: []mut Header } -> !?Incoming

    // Writes "100 Continue", for a request that expects it, before its body is read.
    fn send_continue { mut net: Net, mut conn: Connection } -> !

    // Writes a response's head, and its body if it is `bytes`. `close` asks to end the
    // connection after it; so does a request that asked to, and a body that is none of
    // `bytes`, `length` or `chunked` for HTTP/1.0.
    fn send_response { mut net: Net, mut conn: Connection, status: u16, headers: []Header, body: Body, close: bool } -> !
}
```

A request's body is read with `read_body`, `read_whole_body` and `discard_body`, as a response's is,
and a response's sent with `write_body` and `finish_body`. A handler that doesn't read the whole body
leaves the rest for `serve_connection`, which discards up to 64 KiB of it and otherwise closes the
connection rather than read a body nobody wants.

## URLs

```
namespace url {
    // A URL's parts, slices of the text it was parsed from (RFC 3986). `port` is null when the
    // URL has none; `host` has no brackets ("::1"); `authority` is what a Host field takes
    // ("[::1]:8080"), without user information; `target` is the path and query, as a request
    // line takes them, "/" when the path is empty.
    struct Url {
        scheme: []u8,
        user: []u8,
        host: []u8,
        port: ?u16,
        authority: []u8,
        path: []u8,
        query: []u8,
        fragment: []u8,
        target: []u8,
    }

    error bad_url{ at: usize }

    fn parse { text: []u8 } -> !Url

    // The URL `reference` names relative to `base` (RFC 3986 §5.2, with dot segments removed),
    // written into `into`, and parsed: what a redirect's Location gives.
    fn resolve { base: Url, reference: []u8, into: []mut u8 } -> !Url

    // The port a scheme implies: 80 for http, 443 for https, 80 and 443 for ws and wss.
    fn default_port { scheme: []u8 } -> ?u16

    // %XX escapes decoded into `into`: how many bytes. bad_url for a broken escape.
    fn decode_percent { text: []u8, into: []mut u8 } -> !usize

    // Bytes other than RFC 3986's unreserved ones escaped into `into`: for a query's values.
    fn encode_percent { text: []u8, into: []mut u8 } -> !usize

    // An @fmt writer: the URL as text.
    #write
    fn push_url(S) { mut b: utf8::Builder(S), u: Url } -> !
}
```

A scheme is matched without case; a host isn't changed (no IDNA: net.md, Name lookup), and an IPv6
host's `%zone` is decoded. Query strings stay bytes: `application/x-www-form-urlencoded`'s `+` and
pairs are a program's to split, with `decode_percent`. `url` is pure.

## Fetch

```
namespace http {
    struct FetchOptions {
        method: []u8 = "GET",
        headers: []Header = [],
        body: []u8 = "",
        redirects: u32 = 10,            // redirects followed at most; 0 follows none and returns the 3xx
        limit: usize = 67108864,        // the body's most bytes: 64 MiB
        tls: ?tls::ClientConfig = null, // for https: null makes one that trusts the system's roots, for this call
    }

    // A response, all of it in memory from the allocator: its head copied, its body.
    struct Fetched { status: u16, headers: []Header, body: alloc::Bytes, url: []u8 }

    // Sends a request to `url` on a connection of its own, follows redirects, and reads the
    // final response whole. The connection is closed before it returns. Statuses aren't errors:
    // a 404 is a Fetched.
    fn fetch(S) { mut net: Net, mut heap: S, realloc: alloc::Fn(S), url: []u8, options: FetchOptions } -> !Fetched

    fn free_fetched(S) { mut heap: S, realloc: alloc::Fn(S), fetched: Fetched }
}
```

**Redirects are followed by `fetch`**, and never by the connection level, where the program sees every
response. `fetch` is for the program that wants a resource and doesn't care how many hops it took; the
rules are browsers' and RFC 9110 §15.4's:

1. 301, 302 and 303 repeat as GET without a body, unless 301 or 302 answered a GET or HEAD, which
   repeat as they were. 307 and 308 repeat the method and body.
2. `Location` is resolved against the URL that gave it (`url::resolve`).
3. To another origin (scheme, host or port), `Authorization`, `Cookie` and `Proxy-Authorization` are
   dropped from `options.headers`.
4. From https to http fails with `insecure_redirect`: a redirect must not move a request off TLS
   without the program choosing to.
5. Past `options.redirects`, `too_many_redirects`.

`fetch`'s connection buffer (16 KiB) and TLS buffer are on its stack, so a task that fetches needs
about 60 KiB of stack for it, within a worker's 8 MiB and the Evented default's 256 KiB.

**An https URL without `options.tls`** gets a config made for the call with `Trust::system`, and
freed before `fetch` returns, also when a redirect leads from http to https. Making one loads the
distribution's bundle on Linux, some milliseconds; on Windows and macOS the OS verifies each chain, so
a config costs little. A program that fetches often makes one config and passes it.

**Deadlines** are a task's, as for every blocking call: fetch in a task and `task::wait_for`, then
`task::cancel` (threads.md, Examples, A timeout, which is a fetch).

## Serving

```
namespace http {
    struct Limits {
        head_ns: u64 = 30000000000,     // for the next request's head to arrive whole, from when the connection is ready for it
        headers: usize = 100,           // fields per request; the caller's array is this long
        requests: u32 = 0,              // requests per connection before it closes; 0 for no limit
    }

    // What a handler gets: the request, and the connection to read its body from and send the
    // response on. It must send one response (serve_connection sends 500 if it didn't).
    struct Exchange { conn: *mut Connection, request: Incoming, responded: bool }

    // Answers one connection's requests, each with `handle`, until the peer closes, a response
    // ends the connection, a limit is reached, or `handle` fails. A request it can't parse gets
    // 400 (431 for a head larger than the buffer, 501 for an unknown transfer coding, 505 for the
    // version) and ends the connection. The head's deadline runs the read in a task of its own,
    // started with start_concurrent and waited for with wait_for.
    fn serve_connection { mut net: Net, mut threads: Threads, mut conn: Connection, headers: []mut Header, limits: Limits, handle: &fn{ mut net: Net, mut exchange: Exchange } -> ! } -> !

    // A whole response, for a handler: status, headers, and the body as bytes.
    fn respond { mut net: Net, mut exchange: Exchange, status: u16, headers: []Header, body: []u8 } -> !
}
```

**A head's deadline takes a task.** A server must not wait forever for a client that opened a
connection and sends nothing, or sends a head a byte a minute. Deadlines are cancellation (net.md,
Timeouts), so `serve_connection` reads each head in a task, borrowing `conn`, and waits for it with
`wait_for`; at the deadline it cancels the read and closes the connection. On the Threaded backend
that is a worker woken per request (idle workers are reused; nothing is created per request when the
server is busy), on Evented a fiber. A handler that reads a body slowly is the handler's to bound the
same way; `serve_connection` doesn't time a body, whose size and pace only the handler knows.

**The accept loop is the program's**, a task per connection in a `task::Group`, as threads.md's server
is. `http` has no `serve` that accepts and starts tasks itself: a start's `run` must be a bind of a
task fn written in the call (threads.md, The API), so a `serve` of std's would start its own task fn
around the program's handler, calling one function value from many tasks at once with whatever that
value holds, which exclusivity can't check through a `&fn`. The loop is twenty lines, and shows what
runs concurrently and what each connection costs.

### A small server

```
#task
fn connection { mut net: Net, mut threads: Threads, socket: net::Socket, site: *Site } -> ! {
    defer net::close{ &net, socket }
    let mut buffer: [16384]u8
    let mut headers: [100]http::Header
    let mut conn = http::open{ stream = http::Stream::plain{ socket }, buffer = buffer[..] }
    try http::serve_connection{ &net, &threads, &conn, headers = headers[..], limits = http::Limits{ .. }, handle = answer{ site, _ } }
}

fn answer { site: *Site, mut net: Net, mut exchange: http::Exchange } -> ! {
    let r = exchange.request
    if not slice::eq_bytes{ a = r.method, b = "GET" } {
        return http::respond{ &net, &exchange, status = 405, headers = [http::Header{ name = "Allow", value = "GET" }], body = "" }
    }
    let page = site_page{ site, path = r.target } ifnull {
        return http::respond{ &net, &exchange, status = 404, headers = [], body = "not found\n" }
    }
    return http::respond{ &net, &exchange, status = 200, headers = [http::Header{ name = "Content-Type", value = "text/html" }], body = page }
}

// Accepts until cancelled. The group is this function's local: however it returns, every
// connection's task ends first.
fn serve { mut net: Net, mut threads: Threads, listener: net::Listener, site: *Site } -> ! {
    let mut connections: task::Group
    while true {
        let socket = net::accept{ &net, listener } iferr err{ error } {
            match error {
                net::aborted => { continue }                          // a client gave up while queued
                net::too_many_open => {
                    thread::sleep{ &threads, nanoseconds = 100000000 }  // let connections end
                    continue
                }
                else => { return error }
            }
        }
        task::start_concurrent_in{ &threads, group = &connections, run = connection{ &net, &threads, socket, site, _ } } iferr {
            net::close{ &net, socket }                                // no thread for it: refuse it
        }
    }
}
```

Each connection's buffers are its task's locals, on the worker's stack: nothing is allocated per
connection, and nothing needs returning to a free list. `site` is shared read-only through a pointer
(threads.md, Scoping, rule 5); a site that changes while served puts its state behind a mutex.

### Stopping

**Stopping at once** is cancelling the task that runs `serve`: `accept` fails with `cancelled`,
`serve` returns, and its group's scope cancels every connection, whose blocked reads fail and whose
`defer`s close their sockets.

**Stopping gracefully** lets requests in progress finish. The program holds the group outside the
accept loop, so it can stop accepting first and then give the connections a grace period with
`task::wait_all_for`, a group's `wait_for` (net.md, Order of work, 1: a change to std/task.ctx):

```
#task
fn accept_into { mut net: Net, mut threads: Threads, listener: net::Listener, site: *Site, mut connections: task::Group } -> ! {
    while true {
        let socket = try net::accept{ &net, listener }
        task::start_concurrent_in{ &threads, group = &connections, run = connection{ &net, &threads, socket, site, _ } } iferr {
            net::close{ &net, socket }
        }
    }
}

fn serve_until { mut net: Net, mut threads: Threads, listener: net::Listener, site: *Site, stop: *Signal, grace_ns: u64 } -> ! {
    let mut connections: task::Group
    let mut acceptor: task::Task(!)
    try task::start_concurrent{ &threads, task = &acceptor, run = accept_into{ &net, &threads, listener, site, &connections, _ } }
    wait_for_signal{ &threads, stop }                       // the program's: a condition, a console handler
    _ = task::cancel{ &threads, task = &acceptor }          // no new connections
    if task::wait_all_for{ &threads, group = &connections, nanoseconds = grace_ns } {
        return task::wait_all{ &threads, group = &connections }     // at once: the first error of the connections
    }
    task::cancel_all{ &threads, group = &connections }      // the grace period is over
}
```

The connections' tasks finish their exchange and then wait for the next request's head, so a client
that keeps its connection idle holds it until the grace period ends, when the cancel reaches it. A
handler that should end kept-alive connections sooner sends `close = true` once the program says it is
stopping (a flag it reads with atomics).

## WebSocket

In. It is the one extension of HTTP/1.1 that programs need for traffic both ways on one connection
(RFC 6455), it is small (an upgrade handshake, then frames), and nothing but HTTP/1.1 gives it.

```
namespace websocket {
    union Kind { text, binary }

    struct Socket { conn: *mut http::Connection, client: bool, ... }   // a client masks what it sends

    // The client's handshake on a connection: GET with Upgrade, checked 101 and Sec-WebSocket-Accept.
    fn connect { mut net: Net, mut socket: Socket, conn: *mut http::Connection, host: []u8, target: []u8, protocols: [][]u8 } -> !

    // The server's: for an Exchange whose request asks to upgrade; sends 101.
    fn accept { mut net: Net, mut socket: Socket, mut exchange: http::Exchange, protocol: []u8 } -> !

    // One message: its kind and length, into `into`; fragments joined; pings answered and pongs
    // dropped meanwhile. message_too_large past into.len. Null once the peer closed, after this end
    // answered its close.
    fn receive { mut net: Net, mut socket: Socket, into: []mut u8 } -> !?Message
    struct Message { kind: Kind, len: usize }

    fn send { mut net: Net, mut socket: Socket, kind: Kind, bytes: []u8 } -> !
    fn ping { mut net: Net, mut socket: Socket, bytes: []u8 } -> !

    // Sends a close frame with `code` (RFC 6455 §7.4) and waits for the peer's.
    fn close { mut net: Net, mut socket: Socket, code: u16, reason: []u8 } -> !
}
```

A text message that isn't UTF-8 fails with `invalid_text` and closes with 1007, as the RFC requires.
**One task reads and one writes**: a WebSocket's point is that either end sends at any time, so a
program receives in one task and sends from another; `net::Socket` allows that, and `tls::Stream`
allows one reader and one writer (net.md, TLS, The API). The `Socket` holds a mutex for the frame
writer, since `receive` answers pings, which is a write. **permessage-deflate is out**: it needs
deflate and inflate, which std doesn't have; servers that offer it serve clients that don't ask for
it.

The handshake's key is base64 of SHA-1, so this package adds `base64` (encode and decode, standard and
URL alphabets, into caller buffers) and `sha1` (pure, for this and for nothing security-bearing; SHA-1
is broken for signatures) to std.

## Out of scope

Each with its reason; none is "later":

- **HTTP/2.** Multiplexed streams with flow control, HPACK, and a connection-level state machine shared
  by the streams' tasks: a second protocol larger than HTTP/1.1. Every HTTP/2 server serves HTTP/1.1
  to a client that doesn't offer `h2` in ALPN, so nothing on the web is unreachable without it; what is
  lost is gRPC, which requires HTTP/2 and its trailers, and is a protocol of its own over it.
- **HTTP/3.** QUIC over UDP, with TLS 1.3's handshake carried in QUIC's frames rather than records,
  which `tls` doesn't expose (OpenSSL's QUIC is an API of its own, beside the TLS one `tls` binds), and loss
  recovery and congestion control written in ctxlang. Every HTTP/3 server advertises itself over
  HTTP/1.1 or 2 (`Alt-Svc`), so it is never the only way in.
- **Compressed bodies** (`Content-Encoding: gzip`, `br`, and `gzip` as a transfer coding): std has no
  inflate or deflate. A client that doesn't send `Accept-Encoding` gets bodies uncompressed from every
  server that follows RFC 9110; a server sends bodies as they are.
- **`CONNECT` as a server**, a tunnelling proxy: a proxy is a program, and after its 2xx the connection
  is two sockets copied both ways, which `net` does.
- **Range requests** as a feature: `Range` and `Content-Range` are headers a program reads and writes;
  http neither generates 206 nor parses ranges, since what a range addresses is the program's resource.

## Errors

```
namespace http {
    error malformed{ at: usize }        // not HTTP/1.1: the offset in the head, or 0 in a body's framing
    error head_too_large                // a head longer than the connection's buffer
    error too_many_headers              // more fields than the caller's array holds
    error body_too_large                // past read_whole_body's or fetch's limit, or past a `length` body's length
    error unsupported_version           // not HTTP/1.0 or 1.1
    error unsupported_coding            // a transfer coding other than chunked
    error ended_early                   // the connection ended inside a message
    error unsupported_scheme            // fetch: not http or https
    error too_many_redirects
    error insecure_redirect             // fetch: from https to http
    error timed_out                     // serve_connection: a head didn't arrive within Limits

    type Error = error(tls::Error, url::bad_url, alloc::out_of_memory, malformed, head_too_large, too_many_headers,
                       body_too_large, unsupported_version, unsupported_coding, ended_early, unsupported_scheme,
                       too_many_redirects, insecure_redirect, timed_out, ..)
}

namespace websocket {
    error handshake_refused{ status: u16 }   // the server didn't answer 101, or answered it wrongly
    error message_too_large
    error invalid_text                       // a text message that isn't UTF-8
    error protocol{ code: u16 }              // the peer broke RFC 6455: the close code this end sent
}
```

Statuses are not errors: 404 and 500 are responses. `tls::truncated` on a body that is `until_close`
over TLS is an error (the body may be cut short by an attacker); on a body whose framing ended first it
isn't seen, since the connection is closed without reading further.

## The interpreter

`url`, the core (heads, framing, chunked), `base64` and `sha1` are pure and run there, which is where
their tests run too. Everything over `net` stops at its first socket call, as net.md says.

## Testing

As net.md's: corpus programs, Python peers from `sys.executable`, ports from 0.

1. **Core, in the interpreter and compiled**: request and status lines and fields, each refusal of the
   parser with its offset, smuggling cases (both length fields, two lengths, obs-fold, a coding before
   chunked), framing for HEAD, 1xx, 204, 304 and HTTP/1.0; the chunked decoder fed a body split at
   every byte boundary; heads written and parsed back; `find_header` with case and repeats;
   `has_token`. URLs: RFC 3986 §5.4's resolution examples, all of them; IPv6 hosts and zones;
   percent-encoding both ways.
2. **Client against Python**: `http.server.ThreadingHTTPServer` with a handler script that answers by
   path: a fixed body, a chunked body, a body until close, HEAD, 204, 304, a 100 then 200, a redirect
   chain across two Python servers, a redirect loop, a redirect to another origin (the test checks
   `Authorization` was dropped), keep-alive with three requests on one connection, `Connection: close`,
   a server that closes mid-body (`ended_early`). Over TLS: the same server wrapped with `ssl` and
   net.md's test certificates, `fetch` with `Trust::roots`, and https to http refused.
3. **Server against Python**: `urllib.request` and `http.client` requests to a ctxlang server: GET,
   POST with a length body and with a chunked body, `Expect: 100-continue`, keep-alive, pipelined
   requests written by a raw Python socket in one send, a head larger than the buffer (431), too many
   fields, a slow client that sends a byte a second past `head_ns` (the connection is closed), a
   handler that doesn't read the body; graceful and immediate shutdown while requests are in flight.
4. **WebSocket**: Python has no WebSocket in its library, so the peer script speaks RFC 6455 itself
   (the handshake with `hashlib.sha1` and `base64`, frames by `struct`): echo both ways, fragmented
   messages, ping and pong, a masked frame from the server refused, a close handshake, a message larger
   than the buffer, a reader task and a writer task on one socket over TLS.
5. **Not tested automatically**: real servers on the internet (one manual test with `CTX_TEST_NETWORK=1`
   fetches a page over https from a public host with `Trust::system`, following its redirect, on each
   platform); throughput and many thousands of connections, which belong to the Evented backend's
   benchmarks.

## Order of work

After net.md's packages 1 to 8 (1, `task::wait_all_for`, for 6), and its 9 to 11 for 5 and after. One sitting each, committed between.

1. **url.** std/url.ctx: `Url`, `parse`, `resolve`, `default_port`, percent encoding, the writer.
   Verified: Testing 1's URL cases, compiled and interpreted.
2. **Heads.** std/http.ctx's core: `Header`, `find_header`, `find_header_from`, `has_token`, head
   parsing for requests and responses with every refusal, head writing. Verified: Testing 1's head
   cases.
3. **Bodies.** `Framing` and its decision, `Body`, the chunked decoder and encoder. Verified: Testing
   1's framing and chunked cases, split at every byte.
4. **A client over sockets.** `Stream` (plain), `Connection`, `open`, `send_request`, `write_body`,
   `finish_body`, `read_response`, `read_body`, `read_whole_body`, `discard_body`, keep-alive.
   Verified: Testing 2 without TLS or redirects.
5. **TLS and fetch.** `Stream::secure`, `fetch` with its redirect rules, `free_fetched`. Verified:
   Testing 2 whole.
6. **The server.** `read_request`, `send_continue`, `send_response`, `serve_connection` with `Limits`
   and its head deadline, `respond`, the error responses. Verified: Testing 3, and the small server
   above compiled as a test.
7. **base64 and sha1.** std/base64.ctx, std/sha1.ctx. Verified: RFC 4648's and FIPS 180's test vectors,
   interpreted and compiled.
8. **WebSocket.** std/websocket.ctx. Verified: Testing 4.

Each package also updates spec §17's table for what it adds.

## Decisions

1. **Sans-IO core, thin connections.** Parsing and framing take buffers and give slices, so they are
   tested without sockets, run in the interpreter, and serve any transport. Rejected: a parser that
   reads from the socket as it goes, whose every branch then needs a network to test.
2. **The caller's buffer is the head's limit**, and the caller's array the fields' limit. No allocation
   in the connection level; `fetch` and `read_whole_body` take an allocator, and say so.
3. **Methods and field values are bytes.** Methods are an open set of tokens, so a union would need an
   `other` beside every comparison; values are octets.
4. **No pool, no proxy settings, no cookie jar** in http: each is state or policy a program owns.
   Rejected: Go's `Transport`, whose hidden pool and timeouts are its most-asked-about behaviour.
5. **`fetch` follows redirects; connections don't.** Rejected: following at the connection level, where
   the program would lose the 3xx it may want, and a `fetch` that doesn't follow, which would make every
   caller write the rules above.
6. **Deadlines are tasks**, in `fetch`'s callers and inside `serve_connection`. Rejected: socket
   deadlines (net.md, Timeouts).
7. **The accept loop is the program's** (Serving). Rejected: `http::serve` taking a handler, which
   would call one function value from many tasks at once.
8. **WebSocket in; HTTP/2, HTTP/3, compression out** (Out of scope).

## Open questions

None: a group's deadline is `task::wait_all_for` (net.md, Order of work, 1), the head's deadline task
per request stays as designed (Serving), and `fetch` without a config trusts the system's roots for
the call (Fetch).
