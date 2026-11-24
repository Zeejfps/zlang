"""Shows that the runner checks: breaks a sample of cases, one expectation each, and requires
the runner to fail each with a message that names the case (LLM-FIRST 5.2's proof).

    python tools/convert/breakit.py [--each N] [--seed S]      from ctxlang/, in Git Bash

A case is copied to build/breakit/cases, where the runner must pass it as it is (the control);
then one thing in the copy is changed and the runner must fail it. Each way of breaking is
applied to N cases (default 3) it applies to, picked by a seeded shuffle. The cases' text is
edited as lines; nothing here reads ctxlang.
"""

import os
import random
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = os.path.join(ROOT, 'tests', 'cases')
WORK = os.path.join(ROOT, 'build', 'breakit', 'cases')
# The checkout's ctxc, as kotor/tools/ctxc builds it from the bootstrap (run that once first).
CTXC = os.path.join(ROOT, 'build', 'ctxc-boot' + ('.exe' if os.name == 'nt' else ''))


def all_cases():
    out = []
    for base, dirs, files in os.walk(CASES):
        dirs.sort()
        if 'CASE' in files:
            out.append(base)
            dirs[:] = []
            continue
        out += [os.path.join(base, f) for f in sorted(files) if f.endswith('.ctx')]
    return out


def script_of(case):
    """The file that holds a case's directives."""
    if os.path.isdir(case):
        return os.path.join(case, 'CASE')
    side = case[:-4] + '.expect'
    return side if os.path.exists(side) else case


def read(path):
    with open(path, encoding='utf-8', newline='', errors='surrogateescape') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
        f.write(text)


def block_line(key):
    """Changes the first line of the first block of a directive whose key matches."""
    def change(text):
        lines = text.split('\n')
        for i, x in enumerate(lines):
            if re.match(r'//# (\[\w+\] )?' + key + r'( escaped)?:$', x) and i + 1 < len(lines) and lines[i + 1].startswith('//| '):
                # Before a `\` that ends an escaped line, so that the line is still well formed.
                lines[i + 1] = lines[i + 1][:-1] + '~\\' if lines[i + 1].endswith('\\') else lines[i + 1] + '~'
                return '\n'.join(lines)
        return None
    return change


def sub(pattern, repl):
    def change(text):
        new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
        return new if n else None
    return change


def no_expectation(text):
    lines = [x for x in text.split('\n') if not x.startswith(('//#', '//|'))]
    lines = [re.sub(r'\s*//~.*$', '', x) for x in lines]
    new = '\n'.join(lines)
    return new if new != text else None


def printed_text(text):
    """Changes the first text the program prints with io::println that its expected standard
    output has as a line: one it does print."""
    for m in re.finditer(r'io::println\{ &io, s = "([^"\\]+)" \}', text):
        if '\n//| ' + m.group(1) + '\n' in text:
            return text[:m.start(1)] + '~' + text[m.start(1):]
    return None


def add_cannot(text):
    if '//# interp:' in text or '//~ error' in text or '//# errors:' in text or '//# compiles' in text:
        return None
    return text.rstrip('\n') + '\n//# interp: cannot run\n'


# (name, applies to: 'file', 'dir' or 'any', what the copy's script becomes or None, what the failure must say)
WAYS = [
    ('stdout: a line changed', 'file', block_line('stdout'), 'stdout differs'),
    ('stderr: a line changed', 'file', block_line('stderr'), 'stderr differs'),
    ('errors: a line changed', 'any', block_line('errors'), "ctxc's errors differ"),
    ('exit: another code', 'file', sub(r'^//# exit: (-?\d+)$', lambda m: f'//# exit: {int(m.group(1)) + 1}'), 'exited with'),
    ('//~ error: another column', 'file', sub(r'//~ error at (\d+):', lambda m: f'//~ error at {int(m.group(1)) + 1}:'), "ctxc's errors differ"),
    ('//~ error: another message', 'file', sub(r'(//~ error at \d+: .*?)( //~|$)', lambda m: m.group(1) + '~' + m.group(2)), "ctxc's errors differ"),
    ('//~ error: taken out', 'file', sub(r'\s*//~ error at .*$', ''), None),
    ('//~ panic: another message', 'file', sub(r'(//~ panic at \d+: .*)$', lambda m: m.group(1) + '~'), "didn't panic as expected"),
    ('//~ panic: another column', 'file', sub(r'//~ panic at (\d+):', lambda m: f'//~ panic at {int(m.group(1)) + 1}:'), "didn't panic as expected"),
    ('panic: another line', 'any', sub(r'^(//# panic: .*)$', lambda m: m.group(1) + '~'), "didn't panic as expected"),
    ('every expectation taken out', 'file', no_expectation, None),
    ('interp: cannot run, of a program it runs', 'file', add_cannot, 'take that out'),
    ('interp: cannot run, taken out', 'any', sub(r'^//# interp: cannot run\n', ''), "can't run the program"),
    ('the program prints another text', 'file', printed_text, 'stdout differs'),
    ('a command: stdout changed', 'dir', block_line('stdout'), 'stdout differs'),
    ('a command: stderr changed', 'dir', block_line('stderr'), 'stderr differs'),
    ('a command: another exit code', 'dir', sub(r'^//# exit: (-?\d+)$', lambda m: f'//# exit: {int(m.group(1)) + 1}'), 'exited with'),
    ('stdout has: a text that is not there', 'dir', block_line('stdout has'), "doesn't have the text"),
    ('file: a line changed', 'dir', block_line(r'file \S+'), 'differs'),
    ('list: a name changed', 'dir', block_line(r'list \S+'), 'differs'),
    ('exists: a path that is not there', 'dir', sub(r'^//# exists (\S+)$', lambda m: f'//# exists {m.group(1)}.none'), "doesn't exist"),
    ('missing: a path that is there', 'dir', sub(r'^//# missing (\S+)$', '//# missing .'), 'exists'),
]


def run(name):
    r = subprocess.run([CTXC, 'run', os.path.join(ROOT, 'tools', 'suite'), '--', '--cases', WORK, '--fresh', name],
                       capture_output=True, text=True, errors='replace', env=dict(os.environ, CTX_HOME=ROOT))
    return r.returncode, r.stdout + r.stderr


def copy(case, name):
    shutil.rmtree(WORK, ignore_errors=True)
    to = os.path.join(WORK, name) if os.path.isdir(case) else os.path.join(WORK, name + '.ctx')
    os.makedirs(os.path.dirname(to), exist_ok=True)
    if os.path.isdir(case):
        shutil.copytree(case, to)
    else:
        shutil.copyfile(case, to)
        if os.path.exists(case[:-4] + '.expect'):
            shutil.copyfile(case[:-4] + '.expect', to[:-4] + '.expect')
    return to


def main(argv):
    each = int(argv[argv.index('--each') + 1]) if '--each' in argv else 3
    seed = int(argv[argv.index('--seed') + 1]) if '--seed' in argv else 1
    cases = all_cases()
    random.Random(seed).shuffle(cases)
    bad = 0
    done = 0
    skipped = 0
    for way, kind, change, must in WAYS:
        found = 0
        for case in cases:
            if found == each:
                break
            is_dir = os.path.isdir(case)
            if (kind == 'file' and is_dir) or (kind == 'dir' and not is_dir):
                continue
            target = case if way == 'the program prints another text' else script_of(case)
            text = read(target)
            if way == 'the program prints another text' and '//# stdout:' not in text:
                continue
            new = change(text)
            if new is None:
                continue
            name = os.path.relpath(case, CASES).replace(os.sep, '/')
            name = name[:-4] if not is_dir else name
            to = copy(case, name)
            code, out = run(name)
            if code != 0:
                skipped += 1            # a case that doesn't pass away from its place (it names its own path): not a sample
                if skipped > 20:
                    print(out[-2000:])
                    raise SystemExit('too many cases fail before they are broken: the runner itself is failing')
                continue
            mutated = to if way == 'the program prints another text' else script_of(to)
            write(mutated, new)
            code, out = run(name)
            fails = [x for x in out.split('\n') if ': fail: ' in x]
            ok = code == 1 and fails and f': fail: {name}: ' in fails[0] and (must is None or any(must in x for x in fails))
            found += 1
            done += 1
            if not ok:
                bad += 1
            line = fails[0] if fails else out.strip().split('\n')[-1]
            line = line[line.index(': fail: ') + 8:] if ': fail: ' in line else line
            print(f'{"ok  " if ok else "BAD "}{way} | {line[:150]}', flush=True)
        if found < each:
            print(f'     ({way}: {found} of {each} cases found)')
    shutil.rmtree(os.path.join(ROOT, 'build', 'breakit'), ignore_errors=True)
    print(f'{done} cases broken, {done - bad} failed as they must, {bad} did not')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
