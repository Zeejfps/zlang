# Networking and TLS: design

Status: **design**, threads.md's item 1, **built through TCP** (Order of work, 1 to 5, and 8): addresses,
`Net`, `net::Error` and TCP are std/net.ctx and the layers', with `task::wait_all_for` and libraries
linked by use; TCP's tests (Testing, Built for TCP) run on Windows, and Linux's and macOS's layers
are compiled from it, not yet run on those systems. It is written against the tasks'
contract as built (internals.md, Tasks): the Threaded backend, `task::Cancel` and its four functions, cancellation that
fails blocking calls, and the layers' cancellable waits that `proc` already uses. http.md is built on
top of it. TLS is OpenSSL 3 on every platform, verified by the operating system on Windows and
macOS (TLS, OpenSSL).

## Why

A program that serves or fetches anything over a network needs sockets, names, and TLS. ctxlang has
files, pipes and child processes, each behind a capability, each with blocking calls that a task can
cancel. Networking is the case tasks were shaped around: many connections open at once, each a
task, each blocked in a receive most of its life, and a server that stops by cancelling the task that
accepts. What tasks fixed for it (internals.md, Tasks: Capabilities; How std's IO takes part): blocking calls,
`..task::Cancel` in `Net`, `task::cancelled` among its errors, and a row in Cancellation's table.

## What other languages learned

- **Go** has one `net` package over a poller of its own (epoll, kqueue, IOCP), so every call blocks
  the goroutine, not the thread, and deadlines are a socket's state (`SetDeadline`) rather than a
  cancellation of the caller. Name lookup is pure Go (reading resolv.conf and hosts, speaking DNS
  itself) unless the system's resolver is needed, which then runs on a blocked thread. Its TLS is
  written in Go; on Windows and macOS it verifies chains with the OS (`CertGetCertificateChain`,
  `SecTrustEvaluateWithError`) and on Linux reads the distribution's bundle.
- **Rust's std** has blocking `TcpStream`, `TcpListener` and `UdpSocket`, with read and write timeouts
  as socket options, and no TLS. Libraries split three ways: `native-tls` binds each OS's TLS (Schannel,
  Secure Transport, OpenSSL), `openssl` binds one library, and `rustls` is TLS in Rust, with
  `rustls-platform-verifier` handing chain verification to the OS.
- **Zig** has TLS 1.2 and 1.3 client code in std (`std.crypto.tls`), with its own crypto, and builds a
  certificate bundle by reading the OS's store (files on Linux and macOS, the ROOT store's
  certificates on Windows). Reading the Windows store has a known gap: Windows installs roots on
  demand, while building a chain (below), so a store read up front can lack the root a server needs.
- **Python** wraps OpenSSL. On Windows `load_default_certs` enumerates the system store, with the same
  gap; the `truststore` package exists to verify through the OS instead.
- **What the operating systems allow**: every socket call can be waited on (poll, kqueue, overlapped
  IO), so every blocking call but name lookup can be cancelled; Windows' `GetAddrInfoExW` can be too
  (Name lookup). TLS libraries that work over memory buffers (OpenSSL's BIOs, Schannel's SSPI,
  rustls) leave the socket to the caller, so TLS needs no cancellation of its own.

ctxlang's shape follows from what it already has: blocking calls everywhere (internals.md, Tasks,
Decisions, 3), a capability that says who may touch the network, a declared open error set as `proc` has,
the layers' waits for cancellation, and TLS as a state machine over buffers so that net is the only
code that blocks.

## Shape

```
fn echo { mut net: Net, socket: net::Socket } -> ! {
    defer net::close{ &net, socket }
    let mut buf: [4096]u8
    while true {
        // A handler's error would be its group's, which cancels every other handler: a reset
        // or a stop ends this connection alone.
        let n = net::receive{ &net, socket, into = buf[..] } iferr { return }
        if n == 0 { return }                                    // the peer finished sending
        _ = net::send{ &net, socket, bytes = buf[..n] } iferr { return }
    }
}

fn main { mut net: Net, mut threads: Threads } -> i32 {
    let listener = net::listen{ &net, address = "127.0.0.1:7000", backlog = 0 } iferr { return 1 }
    defer net::close_listener{ &net, listener }
    let mut handlers: task::Group
    while true {
        let socket = net::accept{ &net, listener } iferr { break }
        task::start_concurrent_in{ &threads, group = &handlers, run = echo{ &net, socket, _ } } iferr {
            net::close{ &net, socket }
        }
    }
    return 0
}
```

- **`Net` is a capability** that `main` receives, as `Fs` and `Proc` are. Every function of `net` and
  `tls` takes it.
- **Sockets are handles**, `net::Socket{ id }`, as `proc::Pipe` is: a descriptor or a Windows
  `SOCKET`. Copying one copies the number; closing is the program's, once.
- **Calls block.** `accept`, `connect`, `receive`, `send` and name lookup block the calling task's
  worker on the Threaded backend and its fiber on Evented, and fail with `task::cancelled` when the
  task is asked to stop. There are no timeout parameters: a deadline is `task::run_within`'s,
  past which they fail with `task::deadline_passed` (Timeouts).
- **TLS is a stream over a socket**, `tls::Stream`, whose engine works on buffers; `net` does its IO,
  so TLS blocks and cancels as sockets do.

## The capability

```
capability Net { ..task::Cancel, ..os::Net, ..os::Tls }
```

- `task::Cancel`, so that every blocking call checks and waits on the task's cancel object
  (internals.md, Tasks, Capabilities).
- `os::Net`, the platform layer's permission and state for sockets (below), as `Proc` includes
  `os::Proc`. On Windows it holds Winsock's statics; on Linux and macOS it is empty, since sockets are
  the C library's.
- `os::Tls`, the layer's capability for OpenSSL, which every extern fn of the binding takes, and which
  names the libraries OpenSSL is linked from on that platform (TLS, OpenSSL). The interpreter's is
  empty.

As built, `Net` is `{ ..task::Cancel, ..os::Net }`: `os::Tls` joins it with the OpenSSL binding
(Order of work, 9), the first code that has an extern fn to take it.

Each has only statics or nothing, so `Net` is a capability without fields, which `main` may receive
(spec §15, rule 1; Entry point, rule 2). TLS takes `Net` and has no capability of its own: it does
nothing beyond `Net`'s sockets but read the trust store, which is part of reaching the network.

**How it reaches the layer.** The public functions in std/net.ctx call `os::` functions that every
layer declares identically, each declaring `net::Error` (spec §8, Errors, rule 14), as `proc` calls
`os::pipe_read`. They take `mut net: Net`, the layer's own `os::Net`, and those that block also
`mut cancel: task::Cancel`, called as `os::tcp_receive{ &net, cancel = &net, ... }`: std's `Net`
converts to both (internals.md, Tasks, Decisions made building it, 2). As built, TCP's are:

```
namespace os {
    fn tcp_connect { mut net: Net, mut cancel: task::Cancel, address: net::Address } -> net::Error!u64
    fn tcp_listen { mut net: Net, address: net::Address, backlog: u32 } -> net::Error!u64
    fn tcp_accept { mut net: Net, mut cancel: task::Cancel, listener: u64, family: u8 } -> net::Error!u64
    fn tcp_receive { mut net: Net, mut cancel: task::Cancel, socket: u64, into: []mut u8 } -> net::Error!usize
    fn tcp_send { mut net: Net, mut cancel: task::Cancel, socket: u64, bytes: []u8 } -> net::Error!usize
    fn tcp_shutdown { mut net: Net, socket: u64, how: net::Shutdown } -> net::Error!
    fn tcp_close { mut net: Net, socket: u64 }                         // a socket or a listener
    fn tcp_get_address { mut net: Net, socket: u64, peer: bool } -> net::Error!net::Address
    fn tcp_set_no_delay { mut net: Net, socket: u64, on: bool } -> net::Error!
    fn tcp_set_keep_alive { mut net: Net, socket: u64, idle_seconds: u32 } -> net::Error!
}
```

`receive` of 0 bytes and `send`'s loop are std/net.ctx's, as are TCP_NODELAY on what `connect` and
`accept` make (the socket closed if it can't be set) and a listener's family.

**Winsock's start.** Windows needs `WSAStartup` before the first socket call, and a lookup of
`ConnectEx` and `AcceptEx` (`WSAIoctl` with `SIO_GET_EXTENSION_FUNCTION_POINTER`, so `mswsock` isn't
linked). The layer does both the first time a socket is made, behind a once-guard as `task::table`
makes the table (`ready`: 0, then 1 while it runs, then 2), and keeps the pointers in statics:

```
namespace os {
    #c_link{ lib = "ws2_32" }
    capability Net {
        static ready: u32,              // WSAStartup and the lookups done: 0, 1 while they run, 2
        static connect_ex: ?*u8,        // ConnectEx, called through @cast(ConnectExFn, p)
        static accept_ex: ?*u8,         // AcceptEx
    }
}
```

`WSACleanup` is never called: the process's end releases Winsock, as it releases every handle.

### What a program without networking pays

Nothing. A program that doesn't take `Net` reaches none of its functions, so ctxc lowers none of them
(lowering starts from `main` and takes what it reaches), and links no library for them: `ws2_32` on
Windows, and the TLS engine's libraries everywhere, are linked only when a reached extern fn takes a
capability that names them (Language and driver change, below). A program that takes `Net` but never
uses TLS links no TLS library, for the same reason. No start-up work runs before the first socket.

## Language and driver change: libraries linked by use

Today std's extern fns are the C library's and kernel32's, which every program links (spec §18,
Extern functions, rule 7), and a program's own libraries are its build program's `build::link`. Neither
fits: a single-file program that opens a socket on Windows must link `ws2_32`, and one that doesn't
mustn't.

1. `#c_link{ lib = "...", archive = false, framework = false, dirs = [] }`, a compiler attribute whose
   fields are literals, on a capability declaration names a C library its extern fns need. Several may
   be given. `lib` may be
   `:FILE`, which GNU ld takes as that file's name (`-l:libssl.so.3`); `framework` makes it a macOS
   framework (`-framework LIB`).
2. A program links each library named by a capability that some extern fn it calls takes, directly
   or through one it includes; ctxc collects them while lowering, as it decides a program is threaded,
   and passes `-lLIB` after the objects, in the order they were first reached.
3. `archive = true` links the static archive `libLIB.a`, found in `CTX_LIB_PATH`'s directories
   (separated as PATH is), then where the C compiler finds it (`-print-file-name`), then in `dirs`, and
   passes its path. It fails, naming the archive and the places it looked, if there is none. This is
   for libraries an executable shouldn't need beside it at run time (TLS, OpenSSL).
4. A library's own dependencies are its declaration's: Windows' `os::Tls` names `crypt32`, `ws2_32`
   and `bcrypt` after `ssl` and `crypto`.

Spec §18 gains the attribute; §17's table says which of std's capabilities name which libraries.

## Addresses

```
namespace net {
    // An IP address. A v6 address's `scope` is the interface a link-local address is on (its
    // index; `%N` in text), 0 otherwise.
    union Ip {
        v4{ octets: [4]u8 },
        v6{ octets: [16]u8, scope: u32 },
    }

    // An IP address and a port.
    struct Address { ip: Ip, port: u16 }

    const LOOPBACK_V4: Ip = Ip::v4{ octets = [127, 0, 0, 1] }
    const LOOPBACK_V6: Ip = Ip::v6{ octets = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1], scope = 0 }
    const ANY_V4: Ip = Ip::v4{ octets = [0, 0, 0, 0] }
    const ANY_V6: Ip = Ip::v6{ octets = [0; 16], scope = 0 }

    error bad_address{ at: usize }      // text that isn't an address: the offset of what's wrong

    // "127.0.0.1", "::1", "fe80::1%3": an address's text, as RFC 4291 and inet_pton read it.
    fn parse_ip { text: []u8 } -> !Ip

    // "127.0.0.1:80", "[::1]:443": an address and a port. The port is required.
    fn parse_address { text: []u8 } -> !Address

    // A literal where an Address is expected: parse_address, while compiling (spec §18).
    #convert
    fn from_literal { s: strlit } -> !Address

    // @fmt writers (spec §13): "127.0.0.1", "::1" in RFC 5952's shortest form, "[::1]:443".
    #write
    fn push_ip(S) { mut b: utf8::Builder(S), ip: Ip } -> !
    #write
    fn push_address(S) { mut b: utf8::Builder(S), address: Address } -> !

    fn is_loopback { ip: Ip } -> bool
    fn eq_ip { a: Ip, b: Ip } -> bool
}
```

These are pure: no capability, so they run in the interpreter and while compiling. An IPv4-mapped
IPv6 address (`::ffff:1.2.3.4`) stays a v6 address: no socket of net's ever produces one, since
listeners are IPv6-only (Listening).

Built (Order of work, 3), with what the text reads settled as inet_pton reads it, and std/net.ctx's
header saying it in full:

- **v4** is four decimal numbers to 255, none with a leading zero (`01` would be octal to some
  readers and decimal to others), so `1.2.3` and `1.2.3.4.5` aren't addresses.
- **v6** may end in a dotted IPv4 address as its last two groups, as inet_pton and RFC 4291 read
  it. Written, only an IPv4-mapped address (`::ffff:0:0/96`) keeps the dotted tail, as RFC 5952 §5
  writes it; any other, the deprecated `::1.2.3.4` included, is written in hexadecimal.
- **A scope** is a decimal `u32`. An interface's name (`%eth0`) is bad text at its first letter: its
  index is the system's to give, and parsing takes no capability. `%0` is no scope.
- **A port** is a decimal `u16` without a leading zero.
- **`at`** is the first byte that can't continue an address, or where a number starts whose value
  or leading zero is wrong, or the text's length when it ends too soon; in `parse_address` it counts
  from the text's start, brackets included.
- **`is_loopback`** of an IPv4-mapped `::ffff:127.0.0.1` is false: it is a v6 address that isn't `::1`.

## Name lookup

```
// The addresses of `host` (a name, or an address's text, which is parsed without a lookup), with
// `port`, into `into`: how many, at most into.len, in the order the system prefers (RFC 6724).
// Fails with not_found when the name has none, and lookup_failed when the resolver couldn't say.
fn lookup { mut net: Net, host: []u8, port: u16, into: []mut Address } -> !usize
```

The system's resolver, so `hosts` files, search domains, mDNS and whatever the system is configured
for all apply: `getaddrinfo` on Linux and macOS, `GetAddrInfoExW` on Windows, with `AF_UNSPEC`, a
stream socket, and `AI_ADDRCONFIG` (no IPv6 results on a host without IPv6). What the resolver
allocates is freed before `lookup` returns; nothing of the caller's is allocated.

**Cancellation.**

- **Windows: interruptible.** `GetAddrInfoExW` with an `OVERLAPPED` whose `hEvent` is a manual-reset
  event, and a `lpHandle` for cancelling, completes asynchronously (Windows 8 and later). The layer
  waits with `WaitForMultipleObjects` on that event and the task's cancel event. Asked to stop, it
  calls `GetAddrInfoExCancel` with the handle, which doesn't block, then waits for the event, which
  the cancelled query still sets; `GetAddrInfoExOverlappedResult` then gives `WSA_E_CANCELLED`, and
  `lookup` fails with `task::cancelled`. A query that completed first stands, and its result is
  returned, as internals.md says of any operation (Tasks, Cancellation; verified against Microsoft's documentation of
  `GetAddrInfoExW` and its sample, which cancels the same way).
- **Linux and macOS: checked before only**, as the cancellation table already says (internals.md, Tasks). `getaddrinfo` can't be
  interrupted; `getaddrinfo_a` is glibc's alone, and runs the query on a thread of its own anyway. A
  cancel then waits for the lookup to end: at most the resolver's timeout times its attempts times its
  servers (`timeout:5 attempts:2` by default in resolv.conf, so 10 s for one server).

Considered and rejected for POSIX: a resolver written in ctxlang, as Go has, which could be cancelled
(DNS over UDP is waited on with poll), but which would ignore what the system is configured with
beyond resolv.conf and hosts (nsswitch on Linux, per-domain resolvers and mDNS on macOS), so a name
that every other program resolves wouldn't resolve in a ctxlang one; and on macOS `DNSServiceGetAddrInfo`
(dns_sd), whose descriptor can be polled with the cancel pipe, but which is a second resolver path
with its own behaviour, for one platform. A lookup ends in resolver time, as a file call ends in disk
time.

**Names outside ASCII** are passed as given: `lookup` doesn't apply IDNA (UTS #46's mapping and
Punycode), which needs Unicode tables std doesn't have. A program gives an internationalized name in
its ASCII form (`xn--...`). Windows applies IDNA itself to non-ASCII names; Linux's and macOS's
resolvers mostly don't, so the ASCII form is the portable one.

## TCP

```
namespace net {
    // A connected TCP socket: a file descriptor, or a Windows SOCKET.
    struct Socket { id: u64 }

    // A listening TCP socket. `family` is 4 or 6: what Windows' AcceptEx makes its socket of.
    struct Listener { id: u64, family: u8 }

    enum Shutdown: u8 { send, receive, both }

    // Connects to `address`. TCP_NODELAY is set on the socket (Options).
    fn connect { mut net: Net, address: Address } -> !Socket

    // Looks `host` up and connects to its addresses in turn: the first that connects, or the
    // last one's error. At most 16 are tried. Name lookup's (Order of work, 6).
    fn connect_host { mut net: Net, host: []u8, port: u16 } -> !Socket

    // A socket listening on `address`; port 0 takes one the system picks (listener_address says
    // which). `backlog` is the queue of connections not yet accepted; 0 for the system's most.
    fn listen { mut net: Net, address: Address, backlog: u32 } -> !Listener

    // Waits for a connection and returns it, with TCP_NODELAY set.
    fn accept { mut net: Net, listener: Listener } -> !Socket

    // Receives at most into.len bytes. Returns how many; 0 once the peer has finished sending
    // (it shut down its sending side, or closed). It waits until there is something.
    fn receive { mut net: Net, socket: Socket, into: []mut u8 } -> !usize

    // Sends all of `bytes`, waiting while the system's buffer is full. Returns bytes.len.
    fn send { mut net: Net, socket: Socket, bytes: []u8 } -> !usize

    // Ends one direction or both: `send` tells the peer this end has finished (its receive
    // returns 0), and the socket may still receive.
    fn shutdown { mut net: Net, socket: Socket, how: Shutdown } -> !

    // Closes the socket. Data already sent still goes. No task may be using it.
    fn close { mut net: Net, socket: Socket }
    fn close_listener { mut net: Net, listener: Listener }

    fn local_address { mut net: Net, socket: Socket } -> !Address
    fn listener_address { mut net: Net, listener: Listener } -> !Address
    fn peer_address { mut net: Net, socket: Socket } -> !Address
}
```

Built (Order of work, 4 and 5) as declared, but `connect_host`, with what building it settled:

- **The layers' sockets.** On Linux `socket` and `accept4` take `SOCK_NONBLOCK | SOCK_CLOEXEC`; on
  macOS, whose calls take no flags, `fcntl` sets `FD_CLOEXEC` and `O_NONBLOCK` and `setsockopt`
  `SO_NOSIGPIPE` right after `socket` or `accept`, and a socket that can't have them is closed.
  `connect` that `EINTR` interrupts is waited for as one in progress, since it goes on without the
  call.
- **Linux's `accept`** passes on a pending connection's network errors (`ENETDOWN`, `EPROTO`,
  `ENOPROTOOPT`, `EHOSTDOWN`, `ENONET`, `EHOSTUNREACH`, `EOPNOTSUPP`, `ENETUNREACH`), which
  accept(2) says to treat as `EAGAIN`: the layer accepts again, so `accept` fails only for the
  listener's own errors.
- **The backlog** for 0 is the largest `int`, which Linux and macOS cut to their limits
  (`net.core.somaxconn`, `kern.ipc.somaxconn`), and Windows' `SOMAXCONN` is: the system's most,
  where C's `SOMAXCONN` is a header's guess (4096 or 128).
- **Keep-alive** past what the system takes fails with `other`: Linux's `TCP_KEEPIDLE` is at most
  32767 seconds.

**Partial IO**, as `proc`'s: `receive` returns what is there, at least one byte unless the peer is
done; `send` loops until every byte is sent, each round the layer's `tcp_send` of some of them. A
receive of 0 bytes asked for returns 0 without a call.

**Sharing.** A socket may be used by two tasks at once, one receiving and one sending: the systems
allow it, and the layer's operations each have their own `OVERLAPPED` or `poll`. Two receiving at
once is allowed and splits the stream between them in an unspecified way. `close` while another task
uses the socket is the program's error, as closing a file another thread reads: on POSIX the number
may already name another descriptor. The program cancels and waits for the tasks first.

**Signals.** A send to a peer that has gone raises SIGPIPE on Linux and macOS unless asked not to:
the Linux layer sends with `MSG_NOSIGNAL`, and the macOS layer sets `SO_NOSIGPIPE` on each socket it
makes or accepts. `send` then fails with `closed`. A setting on `main` for broken pipes, which isn't
built, would be about pipes and standard output; sockets never raise the signal, whatever it says.

**Inheritance.** Sockets aren't inherited by children `proc` starts: `SOCK_CLOEXEC` and `accept4` on
Linux, which forks; on macOS `posix_spawn`'s `POSIX_SPAWN_CLOEXEC_DEFAULT` already keeps them, and
`FD_CLOEXEC` is set as well; on Windows `WSA_FLAG_NO_HANDLE_INHERIT`, beside `proc`'s handle list.

**`connect_host`** tries addresses one after another.

**Happy Eyeballs is out of scope** (RFC 8305: start a connect to the first address, start the next
250 ms later if none has connected, take the first that does). It needs concurrent connects, so
`Threads`, which `net`'s functions don't take: `Net` is permission to reach the network, not to run
tasks (internals.md, Tasks, Decisions, 2). A program composes it from `lookup` and `connect` in tasks:

```
struct Race { lock: mutex::Mutex, socket: ?net::Socket, last: ! }
error connected                 // the winner's: a group's first error cancels the rest

fn attempt { mut net: Net, mut threads: Threads, address: net::Address, delay_ns: u64, race: *mut Race } -> ! {
    thread::sleep{ &threads, nanoseconds = delay_ns }       // returns early when cancelled
    let socket = net::connect{ &net, address } iferr err{ error } {
        mutex::lock{ mutex = &race.lock }
        race.last = error
        mutex::unlock{ mutex = &race.lock }
        return                                              // a loser's failure cancels nothing
    }
    mutex::lock{ mutex = &race.lock }
    defer mutex::unlock{ mutex = &race.lock }
    if race.socket != null {
        net::close{ &net, socket }                          // another won meanwhile
        return
    }
    race.socket = socket
    return connected
}

fn connect_racing { mut net: Net, mut threads: Threads, addresses: []net::Address } -> !net::Socket {
    let mut race = Race{ lock = mutex::make{}, socket = null, last = net::unreachable }
    defer mutex::free{ mutex = &race.lock }
    let mut tries: task::Group
    let mut i: usize = 0
    while i < addresses.len and i < 8 {
        try task::start_concurrent_in{ &threads, group = &tries, run = attempt{ &net, &threads, address = addresses[i], delay_ns = @as(u64, i) * 250000000, race = &race, _ } }
        i = i + 1
    }
    _ = task::wait_all{ &threads, group = &tries } iferr {}  // `connected`, or every attempt ended
    if let s = race.socket { return s }
    match race.last {
        ok => { return net::unreachable }
        err{ error } => { return error }                    // the last attempt's failure
    }
}
```

### Listening

`listen` sets, without options:

- `SO_REUSEADDR` on Linux and macOS, so a server restarts while its old connections are in
  TIME_WAIT. On Windows `SO_EXCLUSIVEADDRUSE` instead: Windows' `SO_REUSEADDR` lets another program
  bind the same port and take its connections.
- `IPV6_V6ONLY` on an IPv6 listener, everywhere. A listener on `[::]` takes IPv6 connections only,
  and peers' addresses are never v4-mapped; a server for both listens twice, a task each. The
  systems' defaults differ (Linux dual-stack, Windows IPv6-only, OpenBSD with no choice), so one
  setting gives one behaviour.
- The backlog, the system's most for 0 (TCP, Built).

### A server

A task per connection, in a group, so stopping the server (cancelling the task that runs `serve`)
stops every handler, and `serve` returning, by any path, waits for them: the group is its local.
`mem` gives pages and never takes them back, so a connection's memory is reused: a handler that ends
puts its `Connection` on the server's free list, under a mutex. A handler borrows nothing of `serve`'s
frame: `c` points into pages, which tasks share as threads do (spec §3.1, rule 6). It compiles
against the built API, with a `serve_requests` of the program's; tests/cases/Net/tcp_group_server
runs it (Testing 4).

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

### Options

```
// Nagle's algorithm off (true, the default net sets) or on.
fn set_no_delay { mut net: Net, socket: Socket, on: bool } -> !

// TCP keep-alive: probes after `idle_seconds` without traffic, at the system's interval and
// count; 0 turns it off. A peer that never answers then fails receive with timed_out.
fn set_keep_alive { mut net: Net, socket: Socket, idle_seconds: u32 } -> !
```

- **TCP_NODELAY is on** for every socket `connect` and `accept` make, as Go does. With Nagle's
  algorithm on, a message written as a head and then a body waits for the peer's delayed
  acknowledgement, 40 to 200 ms; a program that writes many small pieces should buffer them, which
  `http` and `tls` do.
- **Keep-alive** is `SO_KEEPALIVE` with `TCP_KEEPIDLE` (Linux; Windows 10 1709 and later),
  `TCP_KEEPALIVE` (macOS).
- **Not offered**, each with its reason: buffer sizes (`SO_SNDBUF`, `SO_RCVBUF`; the systems tune
  them per connection, and a fixed size turns that off), `SO_LINGER` (a close that resets or blocks;
  `shutdown` and `close` cover orderly ends, and a reset is what closing a socket with unread data
  does already), receive and send timeouts (`SO_RCVTIMEO`; deadlines are cancellation, Timeouts).

## UDP

In: datagrams can't be built from TCP, and programs need them (game networking, discovery, DNS, time).
It is four calls over the machinery TCP needs anyway.

```
namespace net {
    struct Datagram { id: u64 }

    // What receive_from got: its length, its sender, and whether it was longer than `into`
    // (the rest is lost, as UDP does).
    struct Received { len: usize, from: Address, truncated: bool }

    // A UDP socket bound to `address`; port 0 for one the system picks.
    fn bind_datagram { mut net: Net, address: Address } -> !Datagram

    // Sends one datagram. Fails with message_too_large past what the path allows.
    fn send_to { mut net: Net, datagram: Datagram, to: Address, bytes: []u8 } -> !

    // Waits for one datagram.
    fn receive_from { mut net: Net, datagram: Datagram, into: []mut u8 } -> !Received

    // Allows sending to a broadcast address.
    fn set_broadcast { mut net: Net, datagram: Datagram, on: bool } -> !

    fn close_datagram { mut net: Net, datagram: Datagram }
    fn datagram_address { mut net: Net, datagram: Datagram } -> !Address
}
```

`truncated` is `MSG_TRUNC` in `recvmsg`'s flags on Linux and macOS, and `WSAEMSGSIZE` from
`WSARecvFrom` on Windows. On Windows the layer also turns off `SIO_UDP_CONNRESET`, so an ICMP "port
unreachable" for an earlier send doesn't fail the next receive, which is how the POSIX systems
behave.

**Out of scope**, each with its reason: multicast (joining a group names an interface, by index on
some systems and by address on others, and choosing one needs interface enumeration, an API of its
own), connected UDP sockets (`connect` on a datagram socket only filters senders, which a program does
by comparing `from`), Unix-domain sockets (Windows has no datagram ones, no descriptor passing, and no
abstract names, so a portable API would be TCP's over paths; local IPC between ctxlang programs is
`proc`'s pipes or loopback TCP), raw sockets and ICMP (they need privileges).

## Errors

```
namespace net {
    error refused               // nothing listens there (ECONNREFUSED)
    error reset                 // the peer reset the connection (ECONNRESET)
    error aborted               // the connection ended before accept took it (ECONNABORTED)
    error closed                // a send after the peer, or this end's shutdown, closed sending (EPIPE, ENOTCONN)
    error unreachable           // no route to the network or the host (ENETUNREACH, EHOSTUNREACH, ENETDOWN, EHOSTDOWN)
    error timed_out             // the system gave up: a connect unanswered, keep-alive unanswered (ETIMEDOUT)
    error address_in_use        // listen or bind on a port taken (EADDRINUSE)
    error address_unavailable   // an address that isn't this host's (EADDRNOTAVAIL)
    error unsupported_address   // IPv6 on a host without it, or the reverse (EAFNOSUPPORT)
    error permission_denied     // a port below 1024 without privilege, a firewall's refusal (EACCES, EPERM)
    error too_many_open         // no descriptor or handle left, in the process or the system (EMFILE, ENFILE, ENOBUFS)
    error message_too_large     // a datagram past what the path allows (EMSGSIZE)
    error not_found             // lookup: the name has no address (EAI_NONAME, WSAHOST_NOT_FOUND)
    error lookup_failed         // lookup: the resolver couldn't say, for now (EAI_AGAIN, WSATRY_AGAIN, EAI_FAIL)
    error other{ code: i64 }    // the OS's number: errno, an EAI_ code minus 10000, or a WSA code

    // What the platform's layer may fail with, on every platform: each of its functions declares
    // this set. Open, as proc::Error is.
    type Error = error(refused, reset, aborted, closed, unreachable, timed_out, address_in_use,
                       address_unavailable, unsupported_address, permission_denied, too_many_open,
                       message_too_large, not_found, lookup_failed, other, bad_address, task::cancelled, ..)
}
```

The names say what happened to the connection, not which call failed. Each layer maps its numbers in
one function, as `proc_failed` does: Linux's and macOS's `errno` values differ (`ECONNREFUSED` is 111
and 61), so their numbers are in `sys`; Windows' `WSAE*` values are the same as Winsock's on every
version. `getaddrinfo`'s `EAI_*` codes are a separate space, so `other` gets them shifted out of
`errno`'s range. A server's accept loop should go on after `aborted` (a client gave up while queued)
and pause after `too_many_open`, rather than return; http.md's server does. `ENOTCONN` (macOS's
`shutdown` once the peer has closed) is `closed`, as `EPIPE` is; on Windows `WSAESHUTDOWN` (a send
after this end's shutdown) and `WSAENOTCONN` are `closed`, and `WSAENETRESET` (keep-alive found the
connection dead) is `timed_out`.

## Cancellation

Every blocking call checks the flag first (`task::check`) and fails with `task::cancelled`; then:

| Call | Windows | Linux | macOS |
|---|---|---|---|
| `receive`, `send`, `receive_from`, `send_to` | overlapped `WSARecv`/`WSASend`/`WSARecvFrom`/`WSASendTo` with an event; `WaitForMultipleObjects` on it and the cancel event; asked to stop, `CancelIoEx(socket, &its_overlapped)`, then `WSAGetOverlappedResult` waits for it to complete before the buffer is let go | non-blocking sockets (`SOCK_NONBLOCK`); on `EAGAIN`, `poll` on the socket and the eventfd | as Linux (`O_NONBLOCK` by `fcntl`), with the cancel pipe |
| `accept` | `AcceptEx` into a socket made for it, overlapped, waited on as above; asked to stop, cancelled and the made socket closed; on success `SO_UPDATE_ACCEPT_CONTEXT` | `accept4` on `EAGAIN` after `poll` for readable | `accept`, then `fcntl` |
| `connect` | `bind` to the any-address, then `ConnectEx`, overlapped, as above; on success `SO_UPDATE_CONNECT_CONTEXT` | `connect` gives `EINPROGRESS`; `poll` for writable, then `SO_ERROR` | as Linux |
| `lookup` | `GetAddrInfoExW` with an event and a cancel handle; `GetAddrInfoExCancel` (Name lookup) | checked before only | checked before only |
| `shutdown`, `close`, options, addresses | don't block | | |

What a cancelled call leaves, as internals.md says of any operation (Tasks, Cancellation): **one that completed stands**, and
returns its result; the next call sees the flag. Otherwise:

- A cancelled `receive` received nothing that is lost on Windows (`CancelIoEx` cancels before data is
  copied, or the operation completes and stands) and nothing on POSIX (poll was cancelled, no recv
  ran). The socket is still usable, but a protocol over it is mid-message, so a program normally
  closes it.
- A cancelled `send` may have sent some of the bytes, how many unknown: **the stream's state is
  unknown, and the program closes it** (internals.md, Tasks, Cancellation).
- A cancelled `connect` or `accept` leaves nothing: the socket being connected, or made for AcceptEx,
  is closed by the call.

Windows' operations each have an event of their own, made and closed per call, as `proc`'s pipe
reads do. The cost is two system calls per operation; the Evented backend replaces it (below).

## Timeouts

There are no timeout parameters and no deadlines on sockets. A deadline is the caller's, on every
blocking call it makes, as a cancel is a task's: `task::run_within` runs a function with a
deadline on the calling thread's calls, each of which fails with `task::deadline_passed` once it
has passed (internals.md, Tasks, Deadlines):

```
fn dial { mut net: Net, host: []u8, port: u16 } -> !net::Socket {
    return net::connect_host{ &net, host, port }
}

fn connect_within { mut net: Net, host: []u8, port: u16, nanoseconds: u64 } -> !net::Socket {
    return task::run_within{ cancel = &net, nanoseconds, run = dial{ &net, host, port, _ } }
}
```

It needs no task and no `Threads`: main's thread has a deadline as a task's does. A connect,
accept, receive or send waiting when it passes stops as a cancelled one does (the operation alone
cancelled, and one that completed meanwhile returns its result), and the next call under it fails
at once; once `run_within` returns, no call sees it. Inside another, the earlier holds.

The system's own limits still apply without one: a connect to a silent address fails with `timed_out`
after the system's SYN retries (about 21 s on Windows, about 2 minutes on Linux), and a receive from a
peer that vanished waits until keep-alive, if set, says it is gone.

Considered and rejected: a deadline per socket, as Go has, or a timeout per call. Either is a second
way to stop a call, beside cancellation, for the network's calls alone, with its own interaction
with a cancel, and the tasks' design is that a deadline is a request to stop at a time
(internals.md, Tasks, Decisions, 9 and 12). A deadline on the caller's calls keeps that: it stops
every call a cancel stops (pipes, a child's wait, a sleep, stop's waits, standard input), the same
way, with `cancelled` winning when both hold. It was a task cancelled at the time, until a
server's idle connections showed its cost, a second thread for each waiting call
(serve/PLAN.md, Findings 2).

## TLS

### What it must do

TLS 1.2 and 1.3 (1.0 and 1.1 are refused: RFC 8996), as a client and as a server, over a connected
`net::Socket`: the handshake, with SNI and ALPN; reading and writing; `close_notify`; the server's
certificate checked against the operating system's trust store, or against roots the program gives;
a server's certificate chain and key loaded from PEM; client certificates both ways.

Out of scope, each with its reason:

- **0-RTT data** (TLS 1.3 early data): it can be replayed by an attacker, so it is safe only for
  requests the application knows are idempotent, a judgment `tls` can't make.
- **Client-side session resumption.** In TLS 1.3 a resumed handshake without 0-RTT takes as many
  round trips as a full one, and saves only the server's signature and the client's verification;
  resuming needs a cache shared between connections (a lock, memory, keys by host), which is state
  the API would have to own. A server resumes clients that offer tickets, if its engine does by
  default (OpenSSL and Schannel do).
- **Revocation on Linux.** Windows' and macOS's verifiers check revocation as the OS is configured to;
  Linux has no system revocation service, and online OCSP is slow, leaks what a client visits, and has
  been dropped by browsers and by Let's Encrypt (2025). So on Linux a revoked certificate isn't
  noticed, as with curl's defaults.
- **Skipping verification.** No option turns it off: a test or a private network gives its own roots
  (`Trust::roots`), which is what such a program means.
- **DTLS and QUIC**: TLS over datagrams; nothing in `net` or `http` needs them (http.md, HTTP/3).

### The engine

Whatever implements TLS is an **engine**: a state machine over bytes that never touches a socket. It
takes what was received, gives what must be sent, and between them gives and takes plaintext. `tls`'s
public functions do the socket IO through `net`, around the engine:

```
loop:
    engine step (handshake, decrypt, or encrypt)
    → wants to send: net::send its output
    → wants input:   net::receive into its input buffer
    → done:          return
```

So **TLS blocks and cancels exactly as sockets do**: every wait is a `net::receive` or `net::send`,
on every backend, the Evented one included, with nothing for TLS to submit. A cancelled TLS call fails
with `task::cancelled` and leaves the session's state unknown, as a cancelled send does: the program
frees the stream without `close_notify` and closes the socket.

The engine's interface is namespace `tls::engine`, which std/tls.ctx is written over. Its
implementation is std/tls/openssl.ctx (below); the public API knows only this:

```
namespace tls::engine {
    // One step: consume what `input` holds of the peer's bytes, write what must be sent to
    // `output`, and plaintext to or from `plain`. Says what it needs next; an error ends the
    // session.
    union Step { send{ len: usize }, receive, plain{ len: usize }, done }
    fn handshake { mut tls: os::Tls, s: u64, input: *mut Buffer, output: []mut u8 } -> tls::Error!Step
    fn decrypt { mut tls: os::Tls, s: u64, input: *mut Buffer, plain: []mut u8, output: []mut u8 } -> tls::Error!Step
    fn encrypt { mut tls: os::Tls, s: u64, plain: []u8, output: []mut u8 } -> tls::Error!Step
    fn close_notify { mut tls: os::Tls, s: u64, output: []mut u8 } -> tls::Error!Step
}
```

(`decrypt` has an `output` because TLS 1.3 may answer a received message, a key update, with one of
its own.)

### OpenSSL

The engine is **OpenSSL 3** on every platform, driven through memory BIOs (`BIO_s_mem`, one for what
was received and one for what must be sent), so it never sees the socket. Its alternatives are under
Decisions, 10.

**The binding**, std/tls/openssl.ctx, namespace `openssl`: about 40 extern fns of libssl and
libcrypto (`TLS_client_method`, `TLS_server_method`, `SSL_CTX_new`, `SSL_new`, `SSL_set_bio`,
`SSL_do_handshake`, `SSL_read_ex`, `SSL_write_ex`, `SSL_get_error`, `SSL_shutdown`, `BIO_read`,
`BIO_write`, `SSL_set1_host`, `SSL_set_alpn_protos`, `SSL_CTX_set_alpn_select_cb`,
`PEM_read_bio_X509`, `PEM_read_bio_PrivateKey`, `SSL_CTX_use_certificate`, `SSL_CTX_use_PrivateKey`,
`SSL_CTX_check_private_key`, `X509_STORE_add_cert`, `ERR_get_error`, and their kin). OpenSSL's macros
(`SSL_set_tlsext_host_name`, `SSL_CTX_set_min_proto_version`, `SSL_CTX_add1_chain_cert`) are `SSL_ctrl`
and `SSL_CTX_ctrl` calls with their constants, since ctxlang reads no headers. Every extern fn takes
`mut tls: os::Tls`, the layer's capability for the engine's libraries, which `Net` includes. The ALPN
selection callback is a `#c_callback` that OpenSSL calls inside `SSL_do_handshake`, on the calling
thread. OpenSSL 3 needs no initialization call, and its contexts (`SSL_CTX`) are safe to share between
threads, which a config is (The API).

**Settings**: the minimum version is TLS 1.2 (`SSL_CTX_set_min_proto_version`), so 1.0 and 1.1 are
refused; cipher suites and groups are OpenSSL's defaults, which are its maintainers' current judgment
and change with its releases; renegotiation is refused (`SSL_OP_NO_RENEGOTIATION`); compression is off
(OpenSSL's default); 0-RTT is never sent or accepted.

**Libraries, per platform**, each named by the layer's `os::Tls` (Language and driver change):

| Platform | Linked | From |
|---|---|---|
| Windows | `libssl.a`, `libcrypto.a` static, then `crypt32`, `ws2_32`, `bcrypt` (what a static libcrypto needs, and crypt32 for the verifier) | MSYS2's OpenSSL 3.5 (`mingw64/lib`, in the C compiler's own path: this repository's G:/Dev/msys64/mingw64 has both archives) |
| Linux | `libssl.so.3`, `libcrypto.so.3`, as `-l:libssl.so.3 -l:libcrypto.so.3` | the distribution's OpenSSL 3, so its security updates apply; the `-l:` form needs no development package |
| macOS | `libssl.a`, `libcrypto.a` static, and the Security and CoreFoundation frameworks for the verifier | Homebrew's `openssl@3` (below) |

Static on Windows and macOS, so an executable needs no DLL or dylib beside it (about 6 MB; OpenSSL's
Apache 2.0 licence asks only for its notice); there, OpenSSL's security fixes reach a program when it
is rebuilt with a newer OpenSSL. macOS ships no OpenSSL a program may link: its `/usr/lib/libssl.dylib`
aborts a program that loads it.

**macOS's archives** are Homebrew's `openssl@3`. The driver looks for an archive in `CTX_LIB_PATH`'s
directories first, then in the C compiler's paths, then in the directories the `#c_link` names
(`dirs`): the layer's `os::Tls` names Homebrew's two standard prefixes, `/opt/homebrew/opt/openssl@3/lib`
(Apple silicon) and `/usr/local/opt/openssl@3/lib` (Intel), whose `opt` links Homebrew keeps whether or
not a formula is linked into the prefix. So `brew install openssl@3` is all a Mac needs, and
`CTX_LIB_PATH` covers an OpenSSL elsewhere (MacPorts, a build of one's own). A missing archive fails
the link naming `libssl.a` and these places. The driver never builds OpenSSL.

**Trust.**

- **Linux**: OpenSSL verifies, with the distribution's paths (`SSL_CTX_set_default_verify_paths`, which
  takes the distribution's OpenSSL's directory and honours `SSL_CERT_FILE` and `SSL_CERT_DIR`), and
  the host with `SSL_set1_host`.
- **Windows**: the chain OpenSSL received is checked by Windows, in OpenSSL's verify callback
  (`SSL_CTX_set_cert_verify_callback`): the certificates go into a memory store
  (`CertOpenStore`, `CertAddEncodedCertificateToStore`), then `CertGetCertificateChain` and
  `CertVerifyCertificateChainPolicy` with `CERT_CHAIN_POLICY_SSL` and the host name. Not OpenSSL's
  `org.openssl.winstore:` store (3.2 and later, present in MSYS2's build), which reads the ROOT store as
  it is: Windows adds roots to it on demand, while building a chain that needs them (automatic root
  update), so a fresh machine's store lacks roots that every Windows program trusts.
- **macOS**: the same callback with Security.framework: `SecCertificateCreateWithData` for each
  certificate, `SecPolicyCreateSSL` with the host, `SecTrustCreateWithCertificates`,
  `SecTrustEvaluateWithError`, so the keychain's roots and the user's trust settings apply.
- **`Trust::roots`**, everywhere: OpenSSL verifies against only the given certificates, in a store of
  the config's own, and the host with `SSL_set1_host`; the OS isn't asked.

The verifiers are the layers' (`os::tls_verify`, declared by every layer; Linux's says "OpenSSL's
own"), since they are the systems' APIs. This is what Go and `rustls-platform-verifier` do.

**Memory.** OpenSSL allocates its sessions and contexts with `malloc`, outside any allocator of the
program's, as the layers' C does for `proc`. A stream's buffer, the caller's, is what moves bytes
between the socket and the BIOs.

### The API

```
namespace tls {
    // What this end trusts to vouch for the peer's certificate.
    union Trust {
        system,                         // the operating system's trust store and verifier
        roots{ pem: []u8 },             // only these CA certificates, PEM: a private CA, or a test's
    }

    // A certificate chain, leaf first, and its private key, loaded for the engine. PEM.
    struct Identity { handle: u64 }
    fn load_identity { mut net: Net, chain_pem: []u8, key_pem: []u8 } -> !Identity
    fn free_identity { mut net: Net, identity: Identity }

    // What a client's sessions share: made once, used by many connections and tasks at once
    // (the engine's context is safe from many threads), freed when none uses it.
    struct ClientConfig { handle: u64 }
    struct ClientOptions {
        trust: Trust = Trust::system,
        protocols: [][]u8 = [],         // ALPN names, in this end's preference
        identity: ?Identity = null,     // a client certificate, for a server that asks
    }
    fn make_client_config { mut net: Net, options: ClientOptions } -> !ClientConfig
    fn free_client_config { mut net: Net, config: ClientConfig }

    struct ServerConfig { handle: u64 }
    struct ServerOptions {
        identity: Identity,
        protocols: [][]u8 = [],         // ALPN names, in this end's preference; a client offering none of them fails with alert
        clients: ?Trust = null,         // ask clients for a certificate, and require one this trusts
    }
    fn make_server_config { mut net: Net, options: ServerOptions } -> !ServerConfig
    fn free_server_config { mut net: Net, config: ServerConfig }

    // A TLS session over a connected socket. Zero is no session. It doesn't own the socket.
    struct Stream { socket: net::Socket, session: u64, lock: mutex::Mutex, buffer: []mut u8, ... }

    // At least this many bytes for a stream's buffer: a record each way, at its largest.
    const BUFFER: usize = 36864

    // The handshake, as the client: `host` is sent as SNI and the certificate must be for it;
    // an IP address's text checks the certificate's IP entries and sends no SNI.
    fn begin_client { mut net: Net, mut stream: Stream, socket: net::Socket, config: ClientConfig, host: []u8, buffer: []mut u8 } -> !

    // The handshake, as the server.
    fn begin_server { mut net: Net, mut stream: Stream, socket: net::Socket, config: ServerConfig, buffer: []mut u8 } -> !

    // Reads at most into.len bytes of plaintext. 0 once the peer has sent close_notify. A
    // connection that ends without it fails with truncated.
    fn read { mut net: Net, mut stream: Stream, into: []mut u8 } -> !usize

    // Writes all of `bytes`, in records of at most 16 KiB.
    fn write { mut net: Net, mut stream: Stream, bytes: []u8 } -> !usize

    // Sends close_notify and frees the session. The socket stays open: the caller closes it.
    fn close { mut net: Net, mut stream: Stream } -> !

    // Frees the session without a word to the peer: after an error or a cancel, whose state is
    // unknown. The caller closes the socket.
    fn free { mut net: Net, mut stream: Stream }

    // The ALPN name both ends chose; empty if none. The peer's verified name, its certificate's
    // DER, the version (12 or 13).
    fn protocol { stream: Stream } -> []u8
    fn version { stream: Stream } -> u8
    fn peer_certificate { stream: Stream } -> []u8
}
```

**Buffers are the caller's**, as everywhere in std: a stream's `buffer`, at least `BUFFER` bytes, holds
a record received and a record to send. A stream doesn't allocate in ctxlang; the engine's library
allocates its own session (OpenSSL's `malloc`).

**Configs are made once.** Loading the trust store and parsing certificates is the expensive part of
TLS, so it is a config's, made once and shared by every stream: a server makes one `ServerConfig`, a
client one `ClientConfig` per kind of trust. Freeing one that a stream still uses is the program's
error.

**One reader and one writer.** A stream may be read by one task while another writes it: the engine
runs only under the stream's lock, and the socket IO between engine steps doesn't hold it, so a
reader blocked in `net::receive` doesn't block the writer. This is what WebSocket needs (http.md).
Two readers, or two writers, at once are the program's error. Since `read` and `write` take the
stream as `mut`, two tasks share it through a pointer to memory both reach (spec §3.1, rule
6), as the mixer's device is shared.

**Server name.** `begin_client`'s `host` is required and is the name verified: `Trust::roots` checks
the name too, so a test's certificate is for `localhost` or `127.0.0.1`.

**Errors.**

```
namespace tls {
    error untrusted                 // the chain reaches no root this end trusts
    error wrong_host                // the certificate isn't for `host`
    error expired                   // a certificate of the chain is outside its dates
    error revoked                   // the OS's verifier found one revoked (Windows, macOS)
    error bad_certificate           // malformed, or a key or signature the engine doesn't take
    error incompatible              // no version, cipher suite or group both ends have
    error alert{ code: u8 }         // the peer ended the handshake or session with this alert (RFC 8446 §6)
    error protocol                  // the peer broke the protocol: a malformed record, a failed MAC
    error truncated                 // the connection ended without close_notify
    error bad_pem{ at: usize }      // load_identity, Trust::roots: not PEM, or not what it should hold
    error key_mismatch              // load_identity: the key isn't the leaf certificate's
    error other{ code: i64 }        // the engine's own code

    type Error = error(net::Error, untrusted, wrong_host, expired, revoked, bad_certificate, incompatible,
                       alert, protocol, truncated, bad_pem, key_mismatch, other, ..)
}
```

An engine's errors map to these in its binding: OpenSSL's verify results (`X509_V_ERR_*`) and Windows'
and macOS's chain statuses to the first five, `SSL_R_*` reasons to the rest.

### Using it

```
fn fetch_banner { mut net: Net, config: tls::ClientConfig, host: []u8, into: []mut u8 } -> !usize {
    let socket = try net::connect_host{ &net, host, port = 443 }
    defer net::close{ &net, socket }
    let mut buffer: [36864]u8
    let mut stream: tls::Stream
    try tls::begin_client{ &net, &stream, socket, config, host, buffer = buffer[..] }
    _ = tls::write{ &net, &stream, bytes = "HEAD / HTTP/1.0\r\n\r\n" } iferr err{ error } {
        tls::free{ &net, &stream }
        return error
    }
    let n = tls::read{ &net, &stream, into } iferr err{ error } {
        tls::free{ &net, &stream }
        return error
    }
    tls::close{ &net, &stream } iferr {}
    return n
}
```

## The Evented backend

Built after this; the API above doesn't change for it. Each layer has one place where a socket call
waits: on Windows the function that waits for an overlapped operation and cancels it (`net_finish`,
as `finish` is for pipes), on POSIX the one that polls a descriptor with the cancel object (`net_ready`, as `ready` is for pipes).
Evented replaces those two, and the lookups:

- **Windows, IOCP.** Every socket is associated with the process's one completion port when it is
  made (`CreateIoCompletionPort`), with `FILE_SKIP_COMPLETION_PORT_ON_SUCCESS`, so an operation that
  completes at once returns without a trip through the port. One port for the process, not one per
  loop: a socket accepted on one loop's fiber is often handed to a task on another, and a handle can be
  associated with one port only, forever. Each loop's thread dequeues completions, and one whose
  `OVERLAPPED` belongs to another loop's fiber is handed to that loop. The overlapped calls are those
  of the Threaded backend without the event; a cancelled one is `CancelIoEx` with its `OVERLAPPED`, as
  now. `GetAddrInfoExW` with a completion routine, run on the loop's thread in an alertable wait.
- **Linux, io_uring.** `IORING_OP_ACCEPT`, `CONNECT`, `RECV`, `SEND`, `RECVMSG`, `SENDMSG`, cancelled
  with `IORING_OP_ASYNC_CANCEL`. `getaddrinfo` runs on the blocking threads behind the loop.
- **macOS, kqueue.** `EVFILT_READ` and `EVFILT_WRITE` on the non-blocking descriptors, as poll is now;
  a cancel deletes the filter. `getaddrinfo` on the blocking threads.
- **TLS** needs nothing: its waits are net's.

The Threaded backend leaves room for this by keeping the waits in those few functions, by making every
socket non-blocking or overlapped from the start, so the functions that make sockets don't change, and
by keeping the event per operation inside the layer, where no caller sees it.

## The interpreter

Networking is not supported there, as files and other programs aren't: std/os/interp's `os::` socket
and lookup functions stop the run with "not supported by interp: the network". Its `os::TLS` is
false, and every function of `tls` checks it first, as `task::start_concurrent` checks
`os::CONCURRENT`, so the interpreter stops before an OpenSSL call, including `make_client_config` and
`load_identity`, which don't touch a socket. Addresses, `parse_address` and its literal conversion are pure and run there.

## Testing

Tests are cases of the suite (tests/README.md): the runner builds each program with native
ctxc and runs it; a peer, when one is needed, is a helper program the case builds
(tests/helpers/child.ctx, the `Proc` cases' pattern). Every test listens on `127.0.0.1` or `::1`, port 0, so tests run at once
without colliding, and passes the port to its peer on the command line or through standard output.

1. **Loopback in one program**: a listener, an accept task and a client task (`start_concurrent`),
   echoing, both ways, 1 MiB each way at once (more than the socket buffers, so `send` waits);
   `shutdown{ send }` making the peer's receive return 0; `peer_address` and `local_address`; IPv6 on
   `::1` (skipped when the host has no IPv6, which `listen` tells by `unsupported_address`); UDP to
   itself, with a datagram longer than the buffer giving `truncated`.
2. **Python peers**: a Python echo server (`socket`) that a ctxlang client talks to, and the reverse;
   a Python server that resets (`SO_LINGER` 0, then close) giving `reset`; connect to a closed port
   giving `refused`; listen twice on one port giving `address_in_use`.
3. **Cancellation**, each followed by a second blocking call that must not see a stale cancel: an
   `accept` with no client; a `receive` from a peer that sends nothing; a `send` to a peer that doesn't
   read (blocked once the buffers are full); a `connect` that hangs, to 192.0.2.1 (TEST-NET-1, which
   no host answers; the test is skipped where it fails at once with `unreachable`, a host without a
   default route); a `lookup` in a task already asked to stop (its check before, everywhere). Each
   ends with `task::cancel` returning `cancelled` within a second. A lookup cancelled while Windows
   is still resolving can't be produced reliably (a test can't make the configured DNS servers
   slow), so `GetAddrInfoExCancel`'s path is covered by Testing 6.
4. **A group's server** as in TCP, A server: 50 clients at once against an accept loop with a
   handler per connection, then cancelling the server's task, which must end every handler.
5. **TLS** against Python's `ssl`: a Python TLS server with checked-in test certificates
   (tests/data/tls: a test CA, a server certificate for `localhost` and `127.0.0.1`, one expired, one
   for another name, one from a CA nobody trusts, and a client certificate, made by a script with the
   `openssl` command and valid for 100 years, the expired one excepted); a ctxlang client with
   `Trust::roots` giving each error; a ctxlang server and a Python client; ALPN chosen both ways;
   close_notify both ways and `truncated` when the Python end closes without it; a client
   certificate required and missing; a cancelled handshake; one reader and one writer task on one
   stream.
6. **Not tested automatically**: `Trust::system` against public servers (a test that fetches from a
   well-known HTTPS host runs only with `CTX_TEST_NETWORK=1`, by hand, on each platform: it is the only
   test of Windows' on-demand roots and macOS's keychain, and it also cancels a lookup of a fresh
   random name under a real domain 1 ms after it starts, on Windows); keep-alive's timing (minutes); the systems'
   own connect timeouts; behaviour under memory or descriptor exhaustion beyond `too_many_open` with a
   lowered `ulimit -n` on Linux.

Built for TCP, in tests/cases/Net:

- `tcp_loopback`: Testing 1's TCP cases, and `refused` and `address_in_use`, which need no Python
  peer. Its IPv6 line says `echoed`, or that the host has no IPv6.
- `tcp_python_peers`: Testing 2's Python peers, tests/helpers/net_peer.py, which the program starts
  as `python net_peer.py MODE`, found on PATH (the case `needs: python`); a server peer prints its
  port as its first line.
- `tcp_cancellation`: Testing 3's TCP cases. Windows' loopback takes tens of MiB from a send that
  no peer reads before it waits, so the blocked send is a loop of sends that goes on until one waits.
- `tcp_every_layer`: every layer's TCP built from any machine, the C for Linux and macOS compiled
  as far as its syntax and types (`cc -fsyntax-only`), and `ws2_32` linked on Windows only by a
  program that takes `Net`.
- `tcp_group_server`: Testing 4, TCP's server above with an echoing `serve_requests`: 50
  clients at once, each keeping its connection open, then the server's task cancelled, which ends
  every handler, each closing its socket.

UDP's and name lookup's cases (Testing 1's UDP, 3's lookup) are Order of work 6 and 7's.

## Order of work

Each package is one sitting for one agent, in this order, each committed (by the user) before the
next. "Verified" is what must pass before it is done; every package also runs the whole suite.

1. **`task::wait_all_for`.** A deadline on a group's wait, which http.md's graceful stop uses, and
   which doesn't depend on networking: as `wait_for` is to `wait`,

   ```
   // As wait_all without its result: true once the group has no task (wait_all then returns at
   // once), false when `nanoseconds` passed first. 0 looks without waiting. A waiter asked to
   // stop stops the group and waits to the end, then returns true, as wait_all does.
   fn wait_all_for { mut threads: Threads, mut group: Group, nanoseconds: u64 } -> bool
   ```

   A change to std/task.ctx: `await_group` with a deadline, as `await` has one. Files: std/task.ctx,
   spec §17's `task` row. Verified: a group whose tasks end before the deadline
   (true, and `wait_all` then gives their first error at once), one whose task sleeps past it (false,
   the group untouched, then `cancel_all`), 0 on a busy group, and a waiter cancelled while it waits
   (the group stopped, true).
2. **Link by use.** `#c_link{ lib, archive, framework, dirs }` on capabilities: spec §18 and §17, ctxc's checker (a
   compiler attribute, as `#c_symbol` is), lowering collecting the libraries of reached extern fns, the
   driver passing them (and finding archives in `CTX_LIB_PATH`, with `-print-file-name`, and in `dirs`),
   and `ctxc build`'s C naming them for the suite's runner. Files: ctxc/check.ctx,
   ctxc/lower.ctx, ctxc/ir.ctx, ir_print/ir_read, ctxc/drive.ctx, spec.md. Verified: a test program whose
   capability names a library that doesn't exist builds when it doesn't call the extern fn and fails
   to link, naming it, when it does; `archive = true` with a missing archive fails naming it.
3. **Addresses.** std/net.ctx's `Ip`, `Address`, `parse_ip`, `parse_address`, `from_literal`, the
   writers, `is_loopback`, `eq_ip`, `bad_address`. Files: std/net.ctx, spec §17. Verified: tests of
   parsing and printing (RFC 5952's cases, scopes, bad text with its offset), a literal that is a
   compile error, run compiled and in the interpreter.
4. **TCP on Linux and macOS.** `Net`, `os::Net` in each layer (empty on POSIX; the interpreter's
   stopping the run), `net::Error` and the mapping, `connect`, `listen`, `accept`, `receive`, `send`,
   `shutdown`, `close`, addresses, `set_no_delay`, `set_keep_alive`, with non-blocking sockets and
   `ready`. Files: std/net.ctx, std/os/posix/os.ctx, std/os/linux/sys.ctx, std/os/macos/sys.ctx,
   std/os/interp/os.ctx. Verified: Testing 1, 2 and 3's TCP cases on Linux and macOS.
5. **TCP on Windows.** WSAStartup's once-guard, ConnectEx and AcceptEx, overlapped operations with
   `net_finish`, `SO_EXCLUSIVEADDRUSE`, `WSA_FLAG_NO_HANDLE_INHERIT`. Files: std/os/windows/os.ctx.
   Verified: Testing 1, 2, 3's TCP cases on Windows.

   std is compiled into every program, so std/net.ctx's calls need every layer's `os::tcp_*`: 4 and 5
   are built one after the other on one branch, each verified on its platforms, and committed together.
6. **Name lookup.** `lookup` and `connect_host`: getaddrinfo, GetAddrInfoExW with its cancel. Files:
   the layers, std/net.ctx. Verified: `localhost` gives a loopback address; an address's text gives
   itself without a lookup; `name.invalid` gives `not_found`; the cancel test on Windows.
7. **UDP.** The datagram functions, `SIO_UDP_CONNRESET`. Files: the layers, std/net.ctx. Verified:
   Testing 1's UDP cases and a cancelled `receive_from`.
8. **Server test and docs.** Testing 4; TCP's server example made to compile against the real
   API; spec §17's table rows for `net`. Files: tests, net.md, spec.md.
9. **The OpenSSL binding.** std/tls/openssl.ctx over memory BIOs; `os::Tls` in every layer with its
   `#c_link`s (Windows' static archives and their dependencies, Linux's `-l:libssl.so.3`, macOS's
   archives with Homebrew's `dirs` and the frameworks, the interpreter's empty, with `os::TLS` false);
   `tls::engine`, configs, identities, Linux's verification. Files: std/tls/openssl.ctx, std/tls.ctx,
   the layers. Verified on Linux: a handshake with a Python server using the test CA, and each
   certificate error.
10. **TLS streams.** `begin_client`, `begin_server`, `read`, `write`, `close`, `free`, the lock that
    lets one reader and one writer in, and the error mapping. Files: std/tls.ctx. Verified: Testing 5
    on Linux.
11. **Windows and macOS.** The static links checked on each, and the verify callback over
    `CertGetCertificateChain` and over `SecTrustEvaluateWithError`, as `os::tls_verify` in each layer
    (Linux's says "OpenSSL's own"). Files: the layers, std/tls/openssl.ctx. Verified: Testing 5 on
    each, and Testing 6's manual test once on each.

    As for 4 and 5, std/tls/openssl.ctx calls every layer's `os::tls_verify`, so 9 to 11 are one
    branch, committed together.

## Decisions

1. **`Net` is one capability for TCP, UDP, lookup and TLS.** Considered and rejected: `Tls` of its
   own (it reaches nothing but sockets and the trust store, so it would be a permission no program
   holds without `Net`); `Dns` of its own (a program that connects to names needs both, always).
2. **Blocking calls, cancellation for deadlines**, as tasks decide for all IO (internals.md, Tasks,
   Decisions, 9 and 12): a deadline is the caller's (`task::run_within`), on every call a cancel
   stops. Rejected: timeouts per call and deadlines per socket (Timeouts).
3. **Sockets are numbers, as `proc::Pipe` and `fs::File` are**, closed by the program. Rejected: a
   socket that closes itself when its scope ends, which ctxlang has no destructors for; a handle type
   like `#loan_holder`, which would forbid storing sockets in a server's connection records.
4. **Listeners are IPv6-only, `SO_REUSEADDR` on POSIX and `SO_EXCLUSIVEADDRUSE` on Windows, TCP_NODELAY
   on**, with no options for the first two: each is the setting a server wants, and the systems'
   defaults differ in ways that surprise.
5. **UDP is in; multicast, Unix-domain and raw sockets are out** (UDP, Out of scope).
6. **Name lookup is the system's**, interruptible on Windows and checked before on POSIX. Rejected: a
   resolver of ctxlang's own (Name lookup).
7. **TLS is an engine over buffers that net drives**, so TLS adds no blocking and no cancellation of its
   own and works on every backend unchanged. Rejected: letting the library own the socket (OpenSSL's
   socket BIOs, Network.framework), which would put blocking calls outside `net`, out of reach of
   the cancel object and the event loop.
8. **Verification is the operating system's on Windows and macOS** whatever the engine, since only it
   knows the roots Windows installs on demand and the policies macOS's keychain holds. Rejected:
   reading the store into the engine (OpenSSL's winstore, Zig's and Python's way), which misses roots.
9. **Configs are explicit**, made once and shared. Rejected: a hidden cache of the system trust in a
   static, which would be state std keeps for the program without a place the program chose.

10. **OpenSSL 3 is the engine on every platform** (TLS, OpenSSL). Considered and rejected:
    - **Each operating system's TLS behind one API**: Schannel through SSPI on Windows, OpenSSL on
      Linux, and on macOS one of two Apple APIs, neither of which fits. Secure Transport takes IO
      callbacks, so it could run over buffers, but it is deprecated (since macOS 10.15), has no TLS
      1.3, and curl removed its Secure Transport backend in 2025. Network.framework has TLS 1.3 but
      owns the connection (`nw_connection`): it makes the socket, connects, and delivers on Apple's
      dispatch queues, so it can't run over a `net::Socket`; Apple has no TLS API over a socket a
      program owns. So macOS would need a bundled library anyway, which is OpenSSL. Beside that, three
      engines are three behaviours (cipher suites, errors, what each accepts) to test behind one API,
      and Schannel's SSPI loop is intricate (`SECBUFFER_EXTRA`, renegotiation,
      `SEC_I_CONTEXT_EXPIRED`), with a server's PEM key to import into CNG.
    - **TLS written in ctxlang**: TLS 1.2 and 1.3; X25519 and P-256; AES-GCM and ChaCha20-Poly1305;
      SHA-256 and SHA-384, HMAC, HKDF; RSA and ECDSA verification and a server's signing; DER, X.509,
      name matching and path validation; PEM. By Zig's std and Go's crypto/tls and crypto/x509, 20 to
      30 thousand lines, mostly crypto and X.509, whose bugs are security bugs. Constant-time code must
      survive a C compiler's optimizations, and fast, cache-safe AES-GCM needs AES-NI and PCLMULQDQ or
      ARMv8's crypto instructions, for which ctxlang has no intrinsics. Its trust would still be the
      operating systems' verifiers. As a fact about the design, not a plan: such an engine would sit
      behind the same `tls::engine` interface, and no caller of `tls` would change.
    - **Another library**: BoringSSL has no stable API and no releases; LibreSSL isn't in MSYS2;
      mbedTLS isn't either, and has no trust store; GnuTLS is in MSYS2 but LGPL, which a static link
      would put on every program, and isn't on macOS.
11. **Static OpenSSL on Windows and macOS, the system's on Linux.** An executable for Windows or macOS
    needs nothing beside it, and Linux's distributions update their OpenSSL for every program at once.
    The driver finds macOS's archives in `CTX_LIB_PATH` or Homebrew's two standard prefixes, which the
    layer's `#c_link` names, so `brew install openssl@3` is enough. It doesn't build OpenSSL: MSYS2 and
    Homebrew ship the archives, and OpenSSL's build needs Perl and its own configure step.

## Open questions

None: what this design left open is settled above (Decisions, 10 and 11; TCP, Happy Eyeballs).
