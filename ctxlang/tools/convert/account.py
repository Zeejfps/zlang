"""The accounting of the conversion: every Python test, what it did, and the cases it became.

    python tools/convert/account.py RECORD.jsonl CASES [-v]

A test `Class.test_name` has its cases at CASES/Class/name: a file name.ctx, a directory with a
CASE, or a directory of cases. Prints, for each class, its tests, the programs and other
actions they ran (as record.py recorded them), and its cases; then every test without a case.
Exits with 1 if a test has none, or if a case belongs to no test.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from survey import load  # noqa: E402
from convert import slug  # noqa: E402

ACTIONS = ('run_sources', 'subprocess.run', 'subprocess.Popen', 'build_project', 'build_sources', 'run_exe', 'ir_sources',
           'ctxc_build', 'read_program', 'build_files')


def cases_at(path):
    """The cases at path: the file path.ctx, the directory itself, or the cases under it."""
    out = []
    if os.path.isfile(path + '.ctx'):
        out.append(path + '.ctx')
    if os.path.isdir(path):
        if os.path.isfile(os.path.join(path, 'CASE')):
            out.append(path)
        else:
            for base, dirs, files in os.walk(path):
                if 'CASE' in files:
                    out.append(base)
                    dirs[:] = []
                    continue
                out += [os.path.join(base, f) for f in files if f.endswith('.ctx')]
    return out


def main(argv):
    record, cases = argv[0], argv[1]
    verbose = '-v' in argv
    tests, marks = load(record)
    by_class = collections.OrderedDict()
    owned = set()
    missing = []
    for test, events in tests.items():
        _, cls, method = test.split('.')
        c = by_class.setdefault(cls, {'tests': 0, 'skipped': 0, 'programs': 0, 'actions': 0, 'asserts': 0, 'cases': 0})
        c['tests'] += 1
        if test in marks:
            c['skipped'] += 1
        c['programs'] += sum(1 for e in events if e['kind'] == 'run_sources')
        c['actions'] += sum(1 for e in events if e['kind'] in ACTIONS and e['kind'] != 'run_sources')
        c['asserts'] += sum(1 for e in events if e['kind'] == 'assert')
        found = cases_at(os.path.join(cases, cls, slug(method)))
        c['cases'] += len(found)
        owned.update(os.path.normpath(f) for f in found)
        if not found:
            missing.append(test)
        if verbose:
            print(f'{test}: {len(found)} cases')
    every = set()
    for base, dirs, files in os.walk(cases):
        if 'CASE' in files:
            every.add(os.path.normpath(base))
            dirs[:] = []
            continue
        every.update(os.path.normpath(os.path.join(base, f)) for f in files if f.endswith('.ctx'))
    # cases/Suite is new: the runner on broken cases, which no Python test did.
    new = sorted(f for f in every - owned if os.path.relpath(f, cases).replace(os.sep, '/').startswith('Suite/'))
    extra = sorted(every - owned - set(new))
    total = collections.Counter()
    print(f'{"class":28}{"tests":>6}{"skipped":>8}{"programs":>9}{"other":>7}{"asserts":>8}{"cases":>7}')
    for cls, c in by_class.items():
        print(f'{cls:28}{c["tests"]:>6}{c["skipped"]:>8}{c["programs"]:>9}{c["actions"]:>7}{c["asserts"]:>8}{c["cases"]:>7}')
        total.update(c)
    print(f'{"total":28}{total["tests"]:>6}{total["skipped"]:>8}{total["programs"]:>9}{total["actions"]:>7}{total["asserts"]:>8}{total["cases"]:>7}')
    print(f'{len(every)} cases under {cases}: {len(every) - len(new) - len(extra)} from the Python tests, {len(new)} new (Suite/); '
          f'{len(extra)} belong to no Python test; {len(missing)} Python tests have no case')
    for t in missing:
        print('  no case:', t)
    for f in extra:
        print('  no test:', os.path.relpath(f, cases).replace(os.sep, '/'))
    return 1 if missing or extra else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
