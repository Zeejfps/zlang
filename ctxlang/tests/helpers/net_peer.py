# A TCP peer for the cases that talk to another implementation of sockets (cases/Net): what it
# does is its first argument. A case's program starts it as `python net_peer.py MODE ...`, and
# a server prints the port it listens on, on 127.0.0.1, as its first line.
#
#   echo_server     accepts one connection and sends back what it receives until the peer has
#                   finished sending, then closes
#   reset_server    accepts one connection and resets it: SO_LINGER of 0, then close
#   client PORT     connects to 127.0.0.1:PORT, sends `from python`, finishes sending, and
#                   prints what it receives until the peer closes
#
# It ends within 30 seconds whatever happens, so a case that fails doesn't leave it running.

import socket
import struct
import sys


def serve(mode):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(30)
    print(listener.getsockname()[1], flush=True)
    conn, _ = listener.accept()
    conn.settimeout(30)
    if mode == "reset_server":
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        conn.close()
        return
    while True:
        data = conn.recv(65536)
        if not data:
            break
        conn.sendall(data)
    conn.close()


def client(port):
    conn = socket.create_connection(("127.0.0.1", port), timeout=30)
    conn.sendall(b"from python")
    conn.shutdown(socket.SHUT_WR)
    got = b""
    while True:
        data = conn.recv(65536)
        if not data:
            break
        got += data
    conn.close()
    print(got.decode(), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "client":
        client(int(sys.argv[2]))
    else:
        serve(sys.argv[1])
