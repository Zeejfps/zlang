"""The recovery test: the front end on damaged copies of every file in the corpus (stage 5 on).

    python tools/recover.py [CORPUS] [-k SUBSTRING] [-j JOBS] [--sample N]

For each distinct file of the corpus (tools/corpus.py), plus std/ and ctxc/, `ctxc recover`
parses three damaged copies per token: cut short where the token starts, with it deleted, and
with it duplicated. ctxc/recover.ctx lists what each copy must satisfy. Large files are split into
chunks of tokens, and chunks run in parallel.

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

from toolchain import native_ctxc  # noqa: E402

WORK = 200_000_000    # bytes to parse per chunk: copies times the file's size


def files(corpus, k):
    """(label, path) for each file of the corpus, std/ and ctxc/."""
    out = []
    if os.path.isdir(corpus):
        for name in sorted(os.listdir(corpus)):
            d = os.path.join(corpus, name)
            with open(os.path.join(d, 'case.json'), encoding='utf-8') as f:
                meta = json.load(f)
            for _, local in meta['files']:
                out.append((f'{name}/{local}', os.path.join(d, local)))
    for sub in ('std', 'ctxc'):
        for p in sorted(glob.glob(os.path.join(ROOT, sub, '*.ctx'))):
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), p))
    return [(label, p) for label, p in out if k in label]


def token_count(path):
    """How many tokens the file has, by ctxc's own dump."""
    r = subprocess.run([native_ctxc(), 'tokens', path], capture_output=True)
    return sum(1 for line in r.stdout.splitlines()[1:] if b'+' in line.split(b' ', 1)[0])


def chunks(todo, sample):
    """(label, path, from, to) for each chunk of tokens, largest files first."""
    seen = set()
    out = []
    for label, p in todo:
        with open(p, 'rb') as f:
            data = f.read()
        key = hashlib.sha256(data).digest()
        if key in seen:
            continue
        seen.add(key)
        n = token_count(p)
        per = max(1, WORK // (3 * max(len(data), 1)))
        for lo in range(0, n, per):
            out.append((len(data) * min(per, n - lo), label, p, lo, min(lo + per, n)))
    out.sort(reverse=True)
    return [(label, p, lo, hi) for _, label, p, lo, hi in out]


def run(job):
    label, path, lo, hi, sample = job
    exe = native_ctxc()
    env = dict(os.environ, CTX_STACK=str(200 << 20))
    failures = []
    copies = 0
    ranges = [(lo, hi)] if sample == 1 else [(j, j + 1) for j in range(lo, hi, sample)]
    for a, b in ranges:
        r = subprocess.run([exe, 'recover', path, str(a), str(b)], capture_output=True, env=env)
        out = r.stdout.decode('utf-8', 'replace').splitlines()
        if not out or not out[-1].startswith('done '):
            # A crash: rerun naming each copy, to find the one that did it.
            v = subprocess.run([exe, 'recover', path, str(a), str(b), '-v'], capture_output=True, env=env)
            err = v.stderr.decode('utf-8', 'replace').splitlines()
            last = [line for line in err if ': ' in line and ' at ' in line]
            where = last[-1] if last else f'{path} tokens {a}..{b}'
            tail = [line for line in err if line not in last][-3:]
            failures.append(f'{label}: crashed (exit {r.returncode}) on {where} {" | ".join(tail)}')
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
    jobs = [(label, p, lo, hi, sample) for label, p, lo, hi in chunks(files(corpus, opts.get('-k', '')), sample)]
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
