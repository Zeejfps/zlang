# A client and a console for serve, the static file server (serve/PLAN.md), on Windows only:
# `python serve_peer.py SERVE`, the path of serve's executable. For cases/Serve.
#
# It makes a directory to serve, in a temporary directory beside a file that must not be
# served, and runs SERVE on it in a process group of its own on this process's console, as
# console_break.py runs its programs, so that a Ctrl-Break reaches it and nothing else. It then
# fetches with http.client and raw sockets: files, HEAD, a file of 3 MiB sent in chunks, a
# listing, a directory's redirect and index, 404, 405, traversals refused, a broken head, and
# /stats; it waits for each request's line in the server's access log before the next request,
# so the log comes out in order, and prints it without what changes from run to run (the time,
# the client's port, the duration). Then it stops the server gracefully with a Ctrl-Break: a
# kept-alive connection's request during the grace period is answered with Connection: close,
# and an idle one is cancelled when the grace period ends. A second run, which serves one
# connection at most (--connections 1), refuses a second, and shows that a second Ctrl-Break
# ends the server at once. Lines end in "\n" on every platform.
#
# Every wait times out, so a case that fails doesn't leave it running.

import ctypes
import hashlib
import http.client
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading

TIMEOUT = 30
STATUS_CONTROL_C_EXIT = 0xC000013A
LOG = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z 127\.0\.0\.1:\d+ (".*") (\d+) (\d+) \d+\.\d{3}ms(.*)$')
SAID = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z serve: (.*)$')


def say(line):
    sys.stdout.buffer.write(line.encode() + b"\n")
    sys.stdout.buffer.flush()


def ensure_console():
    kernel32 = ctypes.windll.kernel32
    ids = (ctypes.c_uint32 * 1)()
    if kernel32.GetConsoleProcessList(ids, 1) != 0:
        return
    kernel32.AllocConsole()
    window = kernel32.GetConsoleWindow()
    if window:
        ctypes.windll.user32.ShowWindow(window, 0)


def make_site(top):
    """The directory to serve, under `top`, and a file beside it that must not be served."""
    with open(os.path.join(top, "secret.txt"), "wb") as f:
        f.write(b"secret\n")
    root = os.path.join(top, "site")
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "empty dir"))
    with open(os.path.join(root, "hello.txt"), "wb") as f:
        f.write(b"hello\n")
    with open(os.path.join(root, "a b&c.txt"), "wb") as f:
        f.write(b"spaces\n")
    with open(os.path.join(root, "style.css"), "wb") as f:
        f.write(b"body {}\n")
    with open(os.path.join(root, "docs", "index.html"), "wb") as f:
        f.write(b"<p>docs</p>\n")
    big = bytes((i * 7 + (i >> 11)) & 255 for i in range(3 * 1024 * 1024))
    with open(os.path.join(root, "big.bin"), "wb") as f:
        f.write(big)
    return root, hashlib.sha256(big).hexdigest()


class Server:
    """SERVE on `root`, its standard output read line by line."""

    def __init__(self, exe, root, grace, more=()):
        self.child = subprocess.Popen(
            [exe, root, "--port", "0", "--grace", str(grace)] + list(more),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        self.lines = queue.Queue()
        threading.Thread(target=self.read, daemon=True).start()
        first = self.said()
        self.port = int(re.search(r"http://127\.0\.0\.1:(\d+)/$", first).group(1))

    def read(self):
        for raw in self.child.stdout:
            self.lines.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
        self.lines.put(None)

    def next_line(self):
        try:
            line = self.lines.get(timeout=TIMEOUT)
        except queue.Empty:
            return "(no line in %d s)" % TIMEOUT
        return "(the output ended)" if line is None else line

    def logged(self):
        """The next access log line, without what changes from run to run."""
        line = self.next_line()
        m = LOG.match(line)
        if not m:
            return "not a log line: " + line
        return "log: %s %s %s%s" % m.groups()

    def said(self):
        """The next line of the server's own, without its time."""
        line = self.next_line()
        m = SAID.match(line)
        return m.group(1) if m else "not the server's line: " + line

    def ctrl_break(self):
        os.kill(self.child.pid, signal.CTRL_BREAK_EVENT)

    def ended(self):
        try:
            code = self.child.wait(timeout=TIMEOUT) & 0xFFFFFFFF
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.wait()
            return "did not end"
        return "ended by Ctrl-Break (0xC000013A)" if code == STATUS_CONTROL_C_EXIT else "exit code %d" % code

    def raw(self, request):
        """Sends `request` on a connection of its own and returns the response's status line and
        whether the server closed the connection after it."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=TIMEOUT) as s:
            s.sendall(request)
            data = b""
            while True:
                more = s.recv(65536)
                if not more:
                    break
                data += more
                if b"\r\n\r\n" in data:
                    head, _, body = data.partition(b"\r\n\r\n")
                    n = int(re.search(rb"(?i)content-length: *(\d+)", head).group(1))
                    if len(body) >= n:
                        break
            return data.split(b"\r\n", 1)[0].decode()


def fetch(conn, server, method, target, show_body=True):
    conn.request(method, target)
    r = conn.getresponse()
    body = r.read()
    parts = ["%s %s: %d" % (method, target, r.status)]
    for name in ("Content-Type", "Content-Length", "Location", "Allow", "Connection"):
        value = r.getheader(name)
        if value is not None:
            parts.append("%s: %s" % (name, value))
    if r.getheader("Date") is None or r.getheader("Server") != "serve":
        parts.append("(no Date or Server)")
    if show_body:
        parts.append(repr(body.decode("utf-8", "replace")))
    say(", ".join(parts))
    say("  " + server.logged())
    return body


def serve_and_fetch(exe, root, digest):
    server = Server(exe, root, grace=2)
    say("started: " + ("yes" if server.port > 0 else "no"))
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=TIMEOUT)
    fetch(conn, server, "GET", "/hello.txt")
    fetch(conn, server, "HEAD", "/hello.txt")
    body = fetch(conn, server, "GET", "/big.bin", show_body=False)
    say("  3 MiB: %s" % ("the same bytes" if hashlib.sha256(body).hexdigest() == digest else "other bytes"))
    listing = fetch(conn, server, "GET", "/", show_body=False).decode()
    say("  links: " + " ".join(re.findall(r'<a href="([^"]*)">', listing)))
    say("  texts: " + " | ".join(re.findall(r'">([^<]*)</a>', listing)))
    fetch(conn, server, "GET", "/docs")
    fetch(conn, server, "GET", "/docs/")
    fetch(conn, server, "GET", "/a%20b%26c.txt")
    listing = fetch(conn, server, "GET", "/empty%20dir/", show_body=False).decode()
    say("  links: " + " ".join(re.findall(r'<a href="([^"]*)">', listing)))
    fetch(conn, server, "GET", "/style.css")
    fetch(conn, server, "GET", "/missing.txt")
    fetch(conn, server, "GET", "/../secret.txt")
    fetch(conn, server, "GET", "/%2e%2e/secret.txt")
    fetch(conn, server, "GET", "/docs/%2e%2e/%2e%2e/secret.txt")
    fetch(conn, server, "GET", "/..%5csecret.txt")
    fetch(conn, server, "GET", "/nul")
    fetch(conn, server, "POST", "/hello.txt")
    conn.close()
    say("broken head: " + server.raw(b"GET / HTTP/1.1\r\nHost x\r\n\r\n"))
    say("  " + server.logged())
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=TIMEOUT)
    stats = json.loads(fetch(conn, server, "GET", "/stats", show_body=False))
    conn.close()
    del stats["uptime_seconds"]
    del stats["connections"]["open"]
    say("  stats: " + json.dumps(stats, sort_keys=True))

    # A graceful stop: one kept-alive connection asks again during the grace period, another
    # stays idle until the grace period ends.
    asking = http.client.HTTPConnection("127.0.0.1", server.port, timeout=TIMEOUT)
    fetch(asking, server, "GET", "/hello.txt")
    idle = http.client.HTTPConnection("127.0.0.1", server.port, timeout=TIMEOUT)
    fetch(idle, server, "GET", "/hello.txt")
    server.ctrl_break()
    say("Ctrl-Break: " + server.said())
    fetch(asking, server, "GET", "/hello.txt")
    asking.close()
    say("then: " + server.said())
    say("then: " + server.said())
    say("server: " + server.ended())
    idle.close()


def stop_twice(exe, root):
    server = Server(exe, root, grace=60, more=["--connections", "1"])
    idle = http.client.HTTPConnection("127.0.0.1", server.port, timeout=TIMEOUT)
    fetch(idle, server, "HEAD", "/")
    with socket.create_connection(("127.0.0.1", server.port), timeout=TIMEOUT) as extra:
        say("a second connection, past --connections 1: " + ("closed" if extra.recv(16) == b"" else "served"))
    stats = json.loads(fetch(idle, server, "GET", "/stats", show_body=False))
    say("  refused: %d" % stats["connections"]["refused"])
    server.ctrl_break()
    say("Ctrl-Break: " + server.said())
    server.ctrl_break()
    say("again: " + server.ended())
    idle.close()


if __name__ == "__main__":
    ensure_console()
    exe = sys.argv[1]
    with tempfile.TemporaryDirectory() as top:
        root, digest = make_site(top)
        serve_and_fetch(exe, root, digest)
        stop_twice(exe, root)
