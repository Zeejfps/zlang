"""Counts what record.py recorded: tests, events by kind, and which tests do more than run programs.

    python tools/convert/survey.py RECORD.jsonl
"""

import collections
import json
import sys


def load(path):
    tests = collections.OrderedDict()
    marks = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r['kind'] in ('skipped', 'failed', 'errored'):
                marks[r['test']] = r
                continue
            if r['test'] is None:
                continue
            tests.setdefault(r['test'], []).append(r)
    return tests, marks


if __name__ == '__main__':
    tests, marks = load(sys.argv[1])
    kinds = collections.Counter()
    shape = collections.Counter()
    odd = collections.defaultdict(list)
    for name, events in tests.items():
        ks = collections.Counter(e['kind'] for e in events if e['kind'] not in ('test', 'end', 'subtest', 'assert'))
        kinds.update(ks)
        key = '+'.join(sorted(ks)) or 'nothing'
        shape[key] += 1
        if key != 'run_sources':
            odd[key].append(name)
    print(len(tests), 'tests;', {k: v['kind'] for k, v in marks.items()})
    print(kinds)
    for k, v in shape.most_common():
        print(v, k)
    if len(sys.argv) > 2:
        for k, v in odd.items():
            print('==', k)
            for n in v:
                print('  ', n)
