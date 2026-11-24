"""Compares what the Python suite and the new suite failed, for one change to the compiler.

    python tools/convert/compare.py UNITTEST_OUTPUT SUITE_OUTPUT

UNITTEST_OUTPUT is `python -m unittest discover tests`'s text (its FAIL: and ERROR: lines name
tests); SUITE_OUTPUT is tools/suite's (its `fail:` lines name cases). A case CLASS/NAME/...
belongs to the test CLASS.test_NAME. Prints the tests both fail, those only Python fails (a
difference the new suite would hide), and those only the new suite fails (it checks more).
"""

import re
import sys


def python_failed(path):
    out = set()
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^(?:FAIL|ERROR): (test_\w+) \((?:test_\w+\.)?(\w+)\.\1\)', line) or \
            re.match(r'^(?:FAIL|ERROR): (test_\w+) \((?:test_\w+\.)?(\w+)\)', line)
        if m:
            out.add(f'{m.group(2)}.{m.group(1)}')
    return out


def suite_failed(path):
    out = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^.*?:\d+: fail: ([^:]+): ', line)
        if m:
            parts = m.group(1).split('/')
            out.setdefault(f'{parts[0]}.test_{parts[1]}', set()).add(m.group(1))
    return out


def main(argv):
    py = python_failed(argv[0])
    new = suite_failed(argv[1])
    both = sorted(py & set(new))
    only_py = sorted(py - set(new))
    only_new = sorted(set(new) - py)
    print(f'Python fails {len(py)} tests; the new suite fails {sum(len(v) for v in new.values())} cases of {len(new)} tests')
    print(f'both: {len(both)}; only Python: {len(only_py)}; only the new suite: {len(only_new)}')
    for t in only_py:
        print('  only Python:', t)
    for t in only_new:
        print('  only new:', t, sorted(new[t])[:3])
    return 1 if only_py else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
