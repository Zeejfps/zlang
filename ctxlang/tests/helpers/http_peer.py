# An HTTP client for the cases that test std's http server against another implementation
# (cases/Http/server_python_peers): `python http_peer.py PORT SHORT_PORT` sends its requests to
# a ctxlang server on 127.0.0.1:PORT, with http.client where it can say what is wanted and raw
# sockets where it can't (pipelining, broken heads, Expect, HTTP/1.0), and prints a line for
# each. SHORT_PORT is a server whose Limits have a short head_ns and allow 2 requests per
# connection. After each connection it asks the server how that connection ended (GET
# /ending/PORT, by the client's port): serve_connection's Ending, or the error it failed with.
# Lines end in "\n" on every platform.
#
# Every socket times out after 30 seconds, so a case that fails doesn't leave it running.

import http.client
import socket
import struct
import sys
import time

TIMEOUT = 30


def say(line):
    sys.stdout.buffer.write(line.encode() + b"\n")
    sys.stdout.buffer.flush()


class Reader:
    """Responses read from a raw socket, one after another."""

    def __init__(self, sock):
        self.sock = sock
        self.data = b""

    def fill(self):
        more = self.sock.recv(65536)
        if not more:
            raise EOFError
        self.data += more

    def take(self, n):
        while len(self.data) < n:
            self.fill()
        out, self.data = self.data[:n], self.data[n:]
        return out

    def line(self):
        while b"\r\n" not in self.data:
            self.fill()
        out, self.data = self.data.split(b"\r\n", 1)
        return out

    def response(self, method="GET"):
        """(status, headers as a dict of lower-case names, body); 1xx responses are returned too."""
        status = int(self.line().split(b" ")[1])
        headers = {}
        while True:
            line = self.line()
            if not line:
                break
            name, value = line.split(b":", 1)
            headers[name.strip().lower().decode()] = value.strip().decode()
        if method == "HEAD" or status < 200 or status in (204, 304):
            return status, headers, b""
        if headers.get("transfer-encoding") == "chunked":
            body = b""
            while True:
                size = int(self.line().split(b";")[0], 16)
                if size == 0:
                    while self.line():
                        pass
                    return status, headers, body
                body += self.take(size)
                self.take(2)
        if "content-length" in headers:
            return status, headers, self.take(int(headers["content-length"]))
        body = self.data
        while True:
            more = self.sock.recv(65536)
            if not more:
                break
            body += more
        self.data = b""
        return status, headers, body

    def is_closed(self):
        """Whether the server finished sending: the connection ends with nothing more."""
        if self.data:
            return False
        try:
            return self.sock.recv(1) == b""
        except ConnectionResetError:
            return True


def connect(port):
    sock = socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT)
    return sock, Reader(sock)


def ending(port, sock):
    """How the server on `port` says the connection from `sock` ended; `sock` is closed first."""
    local = sock.getsockname()[1]
    sock.close()
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    c.request("GET", "/ending/%d" % local)
    text = c.getresponse().read().decode()
    c.close()
    return text


def show(status, headers, body):
    conn = headers.get("connection")
    text = "%d %r" % (status, body.decode())
    return text + (" (Connection: %s)" % conn if conn else "")


def keep_alive(port):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    bodies = []
    for _ in range(3):
        c.request("GET", "/hello")
        r = c.getresponse()
        bodies.append(r.read().decode().strip())
    first = c.sock
    c.request("GET", "/hello")
    r = c.getresponse()
    r.read()
    say("keep-alive: %s, one connection: %s, ended: %s" % (bodies, c.sock is first, ending(port, c.sock)))


def chunked_request(port):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    c.request("POST", "/echo", body=iter([b"Hel", b"lo, ", b"chunks"]), encode_chunked=True)
    r = c.getresponse()
    say("chunked request: %d %r" % (r.status, r.read().decode()))
    c.request("POST", "/echo", body=b"a length body")
    r = c.getresponse()
    say("length request: %d %r" % (r.status, r.read().decode()))
    c.request("POST", "/echo3", body=iter([b"read three ", b"bytes at a time"]), encode_chunked=True)
    r = c.getresponse()
    say("chunked, read 3 at a time: %d %r" % (r.status, r.read().decode()))
    c.close()


def chunked_response(port):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    c.request("GET", "/stream")
    r = c.getresponse()
    say("chunked response: %d %s %r" % (r.status, r.getheader("Transfer-Encoding"), r.read().decode()))
    c.request("HEAD", "/hello")
    r = c.getresponse()
    say("HEAD: %d Content-Length %s %r" % (r.status, r.getheader("Content-Length"), r.read().decode()))
    c.request("GET", "/hello")
    r = c.getresponse()
    say("after HEAD: %d %r" % (r.status, r.read().decode()))
    c.request("HEAD", "/sized")
    r = c.getresponse()
    say("HEAD of a length body unwritten: %d Content-Length %s" % (r.status, r.getheader("Content-Length")))
    r.read()
    c.request("GET", "/sized")
    r = c.getresponse()
    say("then GET: %d %r" % (r.status, r.read().decode()))
    c.close()


def handler_sent_nothing(port):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    c.request("GET", "/nothing")
    r = c.getresponse()
    say("sent nothing: %d %r" % (r.status, r.read().decode()))
    c.request("GET", "/hello")
    r = c.getresponse()
    say("then: %d %r, ended: %s" % (r.status, r.read().decode(), ending(port, c.sock)))
    sock, reader = connect(port)
    sock.sendall(b"GET /fail HTTP/1.1\r\nHost: x\r\n\r\n")
    said = "handler failed: %s, closed: %s" % (show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))


def pipelined(port):
    sock, reader = connect(port)
    sock.sendall(
        b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n"
        b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 4\r\n\r\nping"
        b"POST /hello HTTP/1.1\r\nHost: x\r\nContent-Length: 7\r\n\r\nunread!"
        b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n"
    )
    got = [show(*reader.response()) for _ in range(4)]
    say("pipelined: %s, ended: %s" % ("; ".join(got), ending(port, sock)))


def expect_continue(port):
    sock, reader = connect(port)
    sock.sendall(b"POST /echo HTTP/1.1\r\nHost: x\r\nExpect: 100-continue\r\nContent-Length: 5\r\n\r\n")
    first = reader.response()
    sock.sendall(b"hello")
    say("100-continue: %d, then %s" % (first[0], show(*reader.response())))
    # A handler that answers without reading the body: no 100, and the connection ends, since
    # the client may never send the body.
    sock.sendall(b"POST /hello HTTP/1.1\r\nHost: x\r\nExpect: 100-continue\r\nContent-Length: 5\r\n\r\n")
    said = "unread with 100-continue: %s, closed: %s" % (show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))


def refused(port, what, head):
    sock, reader = connect(port)
    sock.sendall(head)
    said = "%s: %s, closed: %s" % (what, show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))


def errors(port):
    refused(port, "bad field", b"GET / HTTP/1.1\r\nHost: x\r\nBad Field: y\r\n\r\n")
    refused(port, "no Host", b"GET / HTTP/1.1\r\n\r\n")
    refused(port, "both lengths", b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n")
    # A head that fills the server's 16 KiB buffer without ending.
    refused(port, "head too large", b"GET / HTTP/1.1\r\nHost: x\r\nX-Big: " + b"a" * 16384)
    refused(port, "too many fields", b"GET / HTTP/1.1\r\nHost: x\r\n" + b"".join(b"X-%d: y\r\n" % i for i in range(120)) + b"\r\n")
    refused(port, "gzip", b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: gzip, chunked\r\n\r\n")
    refused(port, "HTTP/2.0", b"GET / HTTP/2.0\r\nHost: x\r\n\r\n")


def closing(port):
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    said = "client's close: %s, closed: %s" % (show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))
    sock, reader = connect(port)
    sock.sendall(b"GET /close HTTP/1.1\r\nHost: x\r\n\r\n")
    said = "server's close: %s, closed: %s" % (show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))


def http_1_0(port):
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.0\r\n\r\n")
    said = "HTTP/1.0: %s, closed: %s" % (show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(port, sock)))
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.0\r\nConnection: keep-alive\r\n\r\n")
    first = show(*reader.response())
    sock.sendall(b"GET /stream HTTP/1.0\r\nConnection: keep-alive\r\n\r\n")
    status, headers, body = reader.response()
    said = "HTTP/1.0 keep-alive: %s, then %s (%s)" % (first, show(status, headers, body), headers.get("transfer-encoding", "no chunks"))
    say("%s, ended: %s" % (said, ending(port, sock)))


def short_limits(port, plain):
    """`port` is the short server's; `plain` the other's, which says how they ended."""
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n")
    a = show(*reader.response())
    sock.sendall(b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n")
    said = "2 requests a connection: %s, then %s, closed: %s" % (a, show(*reader.response()), reader.is_closed())
    say("%s, ended: %s" % (said, ending(plain, sock)))
    # Idle: nothing sent, empty lines, or a request answered and then nothing, as a browser
    # keeps a connection. Stalled: half a head, or a whole request and half the next one's head.
    for what, first, send in (
        ("nothing", False, b""),
        ("empty lines", False, b"\r\n\r\n"),
        ("a request, then nothing", True, b""),
        ("half a head", False, b"GET /hello HTTP/1.1\r\nHo"),
        ("a request, then half a head", True, b"GET /hello HTTP/1.1\r\nHo"),
    ):
        sock, reader = connect(port)
        if first:
            sock.sendall(b"GET /hello HTTP/1.1\r\nHost: x\r\n\r\n")
            reader.response()
        began = time.monotonic()
        sock.sendall(send)
        closed = reader.is_closed()
        took = time.monotonic() - began
        say("sends %s: closed: %s, after the deadline: %s, ended: %s" % (what, closed, 0.4 < took < 10, ending(plain, sock)))


def broken_off(port):
    """A client that resets its connection inside a head, and one that finishes sending there."""
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.1\r\nHo")
    time.sleep(0.1)
    # A close with SO_LINGER of 0 resets the connection.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    say("reset inside a head, ended: %s" % ending(port, sock))
    sock, reader = connect(port)
    sock.sendall(b"GET /hello HTTP/1.1\r\nHo")
    sock.shutdown(socket.SHUT_WR)
    say("finished inside a head: closed: %s, ended: %s" % (reader.is_closed(), ending(port, sock)))


if __name__ == "__main__":
    port, short = int(sys.argv[1]), int(sys.argv[2])
    keep_alive(port)
    chunked_request(port)
    chunked_response(port)
    handler_sent_nothing(port)
    pipelined(port)
    expect_continue(port)
    errors(port)
    closing(port)
    http_1_0(port)
    broken_off(port)
    short_limits(short, port)
