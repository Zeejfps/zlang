"""Profiles a ctxlang program under ctxi, per ctxlang function.

    python tools/profile.py PROGRAM [args...]

Prints the functions with the most calls and the most time spent in their own bodies (not in
the ctxlang functions they call).
"""

import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ctxi import runtime  # noqa: E402
from ctxi.__main__ import read_program, run_sources  # noqa: E402
from ctxi.types import qualname  # noqa: E402


def main(argv):
    calls, own = {}, {}
    stack = []
    original = runtime.FnInst.call

    def call(self, args):
        name = qualname(self.decl)
        t0 = time.perf_counter()
        stack.append(0.0)
        try:
            return original(self, args)
        finally:
            dt = time.perf_counter() - t0
            inner = stack.pop()
            own[name] = own.get(name, 0.0) + dt - inner
            calls[name] = calls.get(name, 0) + 1
            if stack:
                stack[-1] += dt
    runtime.FnInst.call = call
    t0 = time.perf_counter()
    code = run_sources(read_program(argv[0]), out=io.BytesIO(), args=argv[1:])
    total = time.perf_counter() - t0
    print(f'exit {code}, {total:.2f}s, {sum(calls.values())} calls')
    print(f"{'own s':>8} {'calls':>9}  function")
    for name in sorted(own, key=own.get, reverse=True)[:25]:
        print(f'{own[name]:8.3f} {calls[name]:9d}  {name}')


if __name__ == '__main__':
    import threading
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(250 << 20)
    t = threading.Thread(target=main, args=(sys.argv[1:],))
    t.start()
    t.join()
