"""The recovery test: the front end on damaged copies of every file in the corpus (stage 5 on).

    python tools/recover.py [CORPUS] [-k SUBSTRING] [-j JOBS] [--sample N]

For each distinct file of the corpus (tools/corpus.py), plus std/ (its layers too) and ctxc/,
`ctxc recover` parses three damaged copies per token: cut short where the token starts, with it
deleted, and with it duplicated. Then it checks each copy in the file's program: the corpus
case's files, std (which ctxc finds itself), or ctxc's. ctxc/recover.ctx lists what each copy
must satisfy. Large files are split into chunks of tokens, and chunks run in parallel.

ctxc's files are checked at every CTXC_EVERYth copy only: a copy of one takes as long to check as
all of ctxc does, about 0.4 s, and checking every copy would take hours. Each is still parsed.

With --sample N, only every Nth token is damaged, for a quicker run.
"""

import concurrent.futures
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from toolchain import native_ctxc, std_files  # noqa: E402

WORK = 50_000_000     # bytes per chunk: copies times what each parses and checks
CTXC_EVERY = 50       # check every Nth copy of ctxc's files
TIMEOUT = 900         # seconds a chunk may take before it counts as hung


def files(corpus, k):
    """(label, path, program, every) for each file of the corpus, std/, std/os/*/ and ctxc/:
    program is the files it is checked with, [] for std's, and every says which copies are."""
    out = []
    if os.path.isdir(corpus):
        for name in sorted(os.listdir(corpus)):
            d = os.path.join(corpus, name)
            with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
                meta = json.load(f)
            program = [os.path.join(d, local) for _, local in meta['files']]
            for _, local in meta['files']:
                out.append((f'{name}/{local}', os.path.join(d, local), program, 1))
    for sub in (('std',), ('std', 'os', '*')):
        for p in sorted(glob.glob(os.path.join(ROOT, *sub, '*.ctx'))):
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), p, [], 1))
    ctxc = sorted(glob.glob(os.path.join(ROOT, 'ctxc', '*.ctx')))
    for p in ctxc:
        out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), p, ctxc, CTXC_EVERY))
    return [f for f in out if k in f[0]]


def size(paths):
    return sum(os.path.getsize(os.path.join(ROOT, p)) for p in paths)


def token_count(path):
    """How many tokens the file has, by ctxc's own dump."""
    r = subprocess.run([native_ctxc(), 'tokens', path], capture_output=True)
    return sum(1 for line in r.stdout.splitlines()[1:] if b'+' in line.split(b' ', 1)[0])


def chunks(todo):
    """(label, path, program, every, from, to) for each chunk of tokens, costliest first. A copy
    costs its parse and, if it is checked, the check of std and its program."""
    std = size(std_files())
    seen = set()
    out = []
    for label, p, program, every in todo:
        with open(p, 'rb') as f:
            data = f.read()
        key = hashlib.sha256(data).digest()
        if key in seen:
            continue
        seen.add(key)
        n = token_count(p)
        copy = len(data) + (std + size(program)) // every
        per = max(1, WORK // (3 * copy))
        for lo in range(0, n, per):
            out.append((copy * min(per, n - lo), label, p, program, every, lo, min(lo + per, n)))
    out.sort(key=lambda c: c[0], reverse=True)
    return [c[1:] for c in out]


def recover(path, a, b, program, every, verbose, env):
    """`ctxc recover` on tokens a..b: its exit code (None if it hung), stdout and stderr."""
    argv = [native_ctxc(), 'recover', path, str(a), str(b)] + (['-v'] if verbose else [])
    argv += (['--every', str(every)] if every > 1 else []) + (['--'] + program if program else [])
    try:
        r = subprocess.run(argv, capture_output=True, env=env, timeout=TIMEOUT)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b'', e.stderr or b''


def run(job):
    label, path, program, every, lo, hi, sample = job
    env = dict(os.environ, CTX_STACK=str(200 << 20))
    failures = []
    copies = 0
    ranges = [(lo, hi)] if sample == 1 else [(j, j + 1) for j in range(lo, hi, sample)]
    for a, b in ranges:
        code, stdout, _ = recover(path, a, b, program, every, False, env)
        out = stdout.decode('utf-8', 'replace').splitlines()
        if not out or not out[-1].startswith('done '):
            # A crash or a hang: rerun naming each copy, to find the one that did it.
            _, _, stderr = recover(path, a, b, program, every, True, env)
            err = stderr.decode('utf-8', 'replace').splitlines()
            last = [line for line in err if ': ' in line and ' at ' in line]
            where = last[-1] if last else f'{path} tokens {a}..{b}'
            tail = [line for line in err if line not in last][-3:]
            how = f'hung (over {TIMEOUT}s)' if code is None else f'crashed (exit {code})'
            failures.append(f'{label}: {how} on {where} {" | ".join(tail)}')
            continue
        copies += int(out[-1].split()[1])
        failures += [f'{label}: {line.split(": ", 1)[1]}' for line in out[:-1]]
    return copies, failures


def main(argv):
    sys.stdout.reconfigure(errors='backslashreplace')
    opts = {}
    for name in ('-k', '-j', '--sample'):
        if name in argv:
            i = argv.index(name)
            opts[name] = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    rest = [a for a in argv if not a.startswith('-')]
    corpus = rest[0] if rest else os.path.join(ROOT, 'build', 'corpus')
    sample = int(opts.get('--sample', 1))
    start = time.time()
    native_ctxc()
    jobs = [c + (sample,) for c in chunks(files(corpus, opts.get('-k', '')))]
    copies = 0
    failures = []
    with concurrent.futures.ThreadPoolExecutor(int(opts.get('-j', os.cpu_count() or 4))) as pool:
        for n, f in pool.map(run, jobs):
            copies += n
            failures += f
    for line in failures[:50]:
        print(line)
    if len(failures) > 50:
        print(f'... and {len(failures) - 50} more')
    print(f'{copies - len(failures)}/{copies} damaged copies recover, from {len({j[1] for j in jobs})} files '
          f'in {time.time() - start:.1f}s')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
