"""Runs the test suite, and counts how its programs fared in ctxc's interpreter.

    python tools/interp_diff.py [-v] [unittest args...]

Each program the tests run through run_sources is run both ways (tools/toolchain.py): compiled,
and with `ctxc interp`. Their stdout, stderr, exit code and panic must be the same; a test fails
with DiffMismatch where they aren't. This prints how many matched, differed, and were skipped,
by reason: an extern fn the interpreter doesn't emulate (files, processes and input need them),
too deep, out of fuel. -v lists the skipped programs' messages. Other arguments go to unittest,
e.g. `tests.test_ctxlang.Basics` for one class.
"""

import collections
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    verbose = '-v' in argv
    rest = [a for a in argv if a != '-v']
    fd, log = tempfile.mkstemp(prefix='interp-diff-', suffix='.jsonl')
    os.close(fd)
    env = dict(os.environ, CTX_DIFF='1', CTX_DIFF_LOG=log)
    cmd = [sys.executable, '-m', 'unittest', *(rest or ['discover', 'tests'])]
    start = time.monotonic()
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    took = time.monotonic() - start
    with open(log, encoding='utf-8') as f:
        rows = [json.loads(line) for line in f]
    os.remove(log)
    status = collections.Counter(row['status'] for row in rows)
    skips = collections.Counter(row['reason'] for row in rows if row['status'] == 'skip')
    print(f'\n{len(rows)} programs in {took:.1f} s: {status["match"]} match, '
          f'{status["mismatch"]} differ, {status["skip"]} skipped')
    for reason, n in skips.most_common():
        print(f'  {n:4}  {reason}')
    if verbose:
        for row in rows:
            if row['status'] == 'skip' and row['detail']:
                print(f'  skip: {row["detail"]}')
    return 1 if r.returncode != 0 or status['mismatch'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
