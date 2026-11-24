"""Writes case files from what record.py recorded (LLM-FIRST 5.2).

    python tools/convert/convert.py RECORD.jsonl CASES [--tiers TIERS.json] [--only SUBSTRING]

Each program a test ran through run_sources becomes a case: tests/cases/CLASS/TEST.ctx, or
CLASS/TEST/NN.ctx for a test that ran several. The expectations are what the Python run
recorded: ctxc's whole standard error for a compile error, and the run's standard output,
standard error, exit code and panic. Nothing here reads ctxlang: a program is text, and lines
are appended to it.

A case is written at a tier, the first that the runner then passes:

  1  the test's comment on top, `//~` markers on the lines of errors and of the panic
  2  nothing on top and no markers: every expectation after the program, positions in full
  3  the program's bytes untouched, in NAME.ctx, and the expectations in NAME.expect

TIERS.json maps a case's name to its tier (default 1). A program whose run needs more than a
case of one file states (files on disk, absolute paths, the environment) is left for
tools/convert/ledger.json's `todo`, with the reason.
"""

import base64
import collections
import json
import os
import re
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from survey import load  # noqa: E402

ERROR = re.compile(r'^(.*?):(\d+):(\d+): error: (.*)$')
PANIC = re.compile(r'^(.*?)(?::(\d+):(\d+))?: panic(?: in (?:thread )?([^:]*))?: (.*)$')
UPS = re.compile(r'(?<![/.\w])(?:\.\./)+std/')


def b64(s):
    return base64.b64decode(s) if s else b''


def settled(text):
    """As the runner compares output: a run of `../` before `std/` is dropped."""
    return UPS.sub('std/', text)


def plain(data):
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    if text and not text.endswith('\n'):
        return False
    for line in text.split('\n'):
        if line != line.rstrip(' \t') or any((ord(c) < 32 or ord(c) == 127) for c in line):
            return False
    return True


def escape_line(raw):
    out = []
    try:
        text = raw.decode('utf-8')
        for c in text:
            if c == '\\':
                out.append('\\\\')
            elif c == '\r':
                out.append('\\r')
            elif c == '\t':
                out.append('\\t')
            elif ord(c) < 32 or ord(c) == 127:
                out.append('\\x%02x' % ord(c))
            else:
                out.append(c)
    except UnicodeDecodeError:
        for b in raw:
            if b == 0x5c:
                out.append('\\\\')
            elif 32 <= b < 127:
                out.append(chr(b))
            else:
                out.append('\\x%02x' % b)
    s = ''.join(out)
    if s.endswith(' '):
        s = s[:-1] + '\\x20'
    return s


def block(key, data, prefix='//'):
    """The lines of a directive with data as its block."""
    if plain(data):
        lines = data.decode('utf-8').split('\n')[:-1] if data else []
        return [f'{prefix}# {key}:'] + [f'{prefix}| {x}' if x else f'{prefix}|' for x in lines]
    parts = data.split(b'\n')
    ends = data.endswith(b'\n')
    if ends:
        parts = parts[:-1]
    lines = [escape_line(p) for p in parts]
    if not ends:
        lines[-1] += '\\'
    return [f'{prefix}# {key} escaped:'] + [f'{prefix}| {x}' if x else f'{prefix}|' for x in lines]


def word(a):
    if a and re.fullmatch(r'[^\s"\\{}]+', a):
        return a
    out = a.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
    return '"' + out + '"'


def comment_of(source):
    """A test's own words: its docstring, or the comment lines its body starts with."""
    lines = source.split('\n')
    body = lines[1:]
    while body and not body[0].strip():
        body = body[1:]
    if not body:
        return []
    first = body[0].strip()
    out = []
    if first.startswith(('"""', "'''")):
        q = first[:3]
        text = '\n'.join(body).strip()[3:]
        text = text[:text.index(q)] if q in text else text
        out = [x.strip() for x in textwrap.dedent(text).strip().split('\n')]
    else:
        for x in body:
            if x.strip().startswith('#'):
                out.append(x.strip()[1:].strip())
            else:
                break
    return [x for x in out]


def slug(name):
    return name[5:] if name.startswith('test_') else name


class Skip(Exception):
    pass


def outcome(r, name):
    """A recorded run's expectations: {'errors': text} or {'exit', 'stdout', 'stderr', 'panic'},
    with the program's file named `name`."""
    given = {}
    sources = r['sources']
    if len(sources) != 1:
        raise Skip('several files')
    old = sources[0][1] or 'main0.ctx'

    def renamed(text):
        return text.replace(old, name)

    if r['exc'] == 'CompileError':
        text = r['text'].replace('\r\n', '\n')
        return {'errors': settled(renamed(text))}
    if r['exc'] not in (None, 'Panic'):
        raise Skip('ended with ' + str(r['exc']))
    out, err = b64(r['stdout']), b64(r['stderr'])
    code = r['raw_code']
    if code >= 1 << 31:
        code -= 1 << 32
    given['stdout'] = out.replace(old.encode(), name.encode()) if old.encode() in out else out
    err_text = settled(renamed(err.decode('utf-8', 'surrogateescape')))
    given['panic'] = None
    if r['exc'] == 'Panic':
        lines = err_text.rstrip('\n').split('\n')
        given['panic'] = lines[-1]
        err_text = ''.join(x + '\n' for x in lines[:-1])
    given['stderr'] = err_text.encode('utf-8', 'surrogateescape')
    given['exit'] = code
    return given


def interp_lines(r, prefix='//'):
    if r['exc'] == 'CompileError':
        return []
    if not r['diffs']:
        return [f'{prefix}# interp: off: {OFF.get(r["test"], OFF_DEFAULT)}']
    status, reason = r['diffs'][0]
    if status == 'skip':
        return [f'{prefix}# interp: cannot run']
    return []


OFF_DEFAULT = 'UNKNOWN'
OFF = {}


def write_case(r, path, tier, desc):
    """Writes the case of recorded run r at path (without .ctx). Returns its files."""
    name = os.path.basename(path) + '.ctx'
    src = r['sources'][0][0]
    exp = outcome(r, name)
    for arg in r['args']:
        if os.path.isabs(arg) or '\\' in arg or 'ctxlang' in arg.lower() or 'temp' in arg.lower():
            raise Skip('an argument that is a path: ' + arg)
    if r['arg_snaps']:
        raise Skip('arguments that are files')
    for text in (src, exp.get('errors', ''), exp.get('stdout', b'').decode('latin-1'), exp.get('stderr', b'').decode('latin-1')):
        if re.search(r'\{(dir|home|repo|gen|exe|ctxc|n|any)\}', text):
            raise Skip('text that holds a placeholder')
    if tier < 3 and ('//~' in src or re.search(r'^//[#|]', src, re.M)):
        tier = 3
    if tier < 3 and ('\r' in src or '\x00' in src):
        tier = 3

    trailer = []
    for k, v in sorted(((r.get('environ') or {}).get('set') or {}).items()):
        trailer.append(f'//# env: {k}={v}')
    if (r.get('environ') or {}).get('unset'):
        raise Skip('the test unset an environment variable')
    if r['args']:
        trailer.append('//# args: ' + ' '.join(word(a) for a in r['args']))
    if r['stdin']:
        trailer += block('stdin', b64(r['stdin']))
    if r['stack_size'] != 16 << 20:
        trailer.append(f'//# stack: {r["stack_size"]}')
    if r['timeout']:
        trailer.append(f'//# timeout: {r["timeout"]}')
    trailer += interp_lines(r)

    lines = src.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
    top = [('// ' + x).rstrip() for x in desc] if desc else []
    marks = {}                  # line number (from 1) -> [marker text]
    inline = tier == 1
    if 'errors' in exp:
        errs = exp['errors']
        rows = errs.split('\n')
        if rows and rows[-1] == '':
            rows = rows[:-1]
        parsed = [ERROR.match(x) for x in rows]
        ok = inline and errs.endswith('\n') and all(parsed) and all(m.group(1) == name for m in parsed)
        if ok:
            where = [(int(m.group(2)), int(m.group(3)), m.group(4)) for m in parsed]
            ok = all(1 <= ln <= len(lines) for ln, _, _ in where) and [w[0] for w in where] == sorted(w[0] for w in where)
            ok = ok and all(msg == msg.rstrip() and '//~' not in msg for _, _, msg in where)
        if ok:
            for ln, col, msg in where:
                marks.setdefault(ln, []).append(f'//~ error at {col}: {msg}')
        else:
            inline = False
            trailer += block('errors', errs.encode('utf-8', 'surrogateescape'))
    else:
        if exp['exit'] not in (0, 134) or (exp['exit'] == 134 and exp['panic'] is None):
            trailer.append(f'//# exit: {exp["exit"]}')
        if exp['stdout']:
            trailer += block('stdout', exp['stdout'])
        if exp['stderr']:
            trailer += block('stderr', exp['stderr'])
        if exp['panic'] is not None:
            m = PANIC.match(exp['panic'])
            if inline and m and m.group(2) and m.group(1) == name and not m.group(4) and 1 <= int(m.group(2)) <= len(lines) \
                    and m.group(5) == m.group(5).rstrip():
                marks.setdefault(int(m.group(2)), []).append(f'//~ panic at {m.group(3)}: {m.group(5)}')
            else:
                trailer.append('//# panic: ' + exp['panic'])
        if not exp['stdout'] and not exp['stderr'] and exp['panic'] is None and exp['exit'] == 0:
            trailer.append('//# exit: 0')

    if tier == 3:
        with open(path + '.ctx', 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
            f.write(src)
        with open(path + '.expect', 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
            f.write('\n'.join(top + trailer) + '\n')
        return [path + '.ctx', path + '.expect']
    body = []
    for i, x in enumerate(lines, 1):
        if i in marks:
            x = (x + '  ' if x.strip() else x) + ' '.join(marks[i])
        body.append(x)
    if tier == 1 and marks and not inline:
        raise AssertionError('markers without inline')
    if tier == 2 or (tier == 1 and not inline and 'errors' in exp):
        # Nothing on top: positions are the file's own.
        out = body + [''] + top + trailer
    else:
        while body and not body[0].strip() and top:
            body = body[1:]
        out = top + ([''] if top else []) + body + ([''] + trailer if trailer else [])
    with open(path + '.ctx', 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
        f.write('\n'.join(out) + '\n')
    return [path + '.ctx']


def is_text(data):
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return b'\x00' not in data and b'\r' not in data


def write_dir_case(r, path, desc, root):
    """Writes the directory case of recorded run r at path: a program of several files, or one
    whose arguments name files in directories the test made, which become the case's tmp/."""
    sources = r['sources']
    lines = [('// ' + x).rstrip() for x in desc]
    files = {}
    names = []
    in_repo = all(f and os.path.exists(os.path.join(root, f)) and
                  open(os.path.join(root, f), encoding='utf-8', newline='').read() == src for src, f in sources)
    for i, (src, f) in enumerate(sources):
        if in_repo:
            names.append('{home}/' + f)
        else:
            name = f or ('main.ctx' if len(sources) == 1 else f'main{i}.ctx')
            if os.path.isabs(name) or '..' in name:
                raise Skip('a file named outside the program')
            names.append(name)
            files[name] = src.encode('utf-8', 'surrogateescape')
    dirs = list((r.get('dirs') or {}).items())
    subs = {d: ('tmp' if k == 0 else f'tmp{k + 1}') for k, (d, _) in enumerate(dirs)}

    def text(t):
        if isinstance(t, bytes):
            return text(t.decode('utf-8', 'surrogateescape')).encode('utf-8', 'surrogateescape')
        for d, sub in subs.items():
            for variant in (d, d.replace('\\', '/')):
                pat = re.compile(re.escape(variant) + r'((?:[\\/]+[\w.\-]+)*)', re.I if os.name == 'nt' else 0)
                t = pat.sub(lambda m: '{dir}/' + sub + re.sub(r'[\\/]+', '/', m.group(1)), t)
        if sources[0][1] is None and len(sources) == 1:
            t = t.replace('main0.ctx', 'main.ctx')
        return settled(t)

    for d, snap in dirs:
        for name, data in sorted(snap.items()):
            if name.endswith('/'):
                lines.append(f'//# make dir {subs[d]}/{name[:-1]}')
            elif data is None:
                raise Skip('a file too large to record')
            else:
                files[subs[d] + '/' + name] = b64(data)
        if not any(not n.endswith('/') for n in snap):
            lines.append(f'//# make dir {subs[d]}')
    args = []
    for a in r['args']:
        t = text(a)
        if (os.path.isabs(a) or '\\' in a) and not t.startswith('{dir}/'):
            raise Skip('an argument that is a path: ' + a)
        args.append(t)
    lines.append('//# program: ' + ' '.join(names))
    for k, v in sorted(((r.get('environ') or {}).get('set') or {}).items()):
        lines.append(f'//# env: {k}={v}')
    if args:
        lines.append('//# args: ' + ' '.join(word(a) if not re.fullmatch(r'[\w./{}:\-=+,@]+', a) else a for a in args))
    if r['stdin']:
        lines += block('stdin', b64(r['stdin']))
    if r['stack_size'] != 16 << 20:
        lines.append(f'//# stack: {r["stack_size"]}')
    lines += interp_lines(r)
    if r['exc'] == 'CompileError':
        lines += block('errors', text(r['text'].replace('\r\n', '\n')).encode('utf-8', 'surrogateescape'))
    elif r['exc'] in (None, 'Panic'):
        out, err = text(b64(r['stdout'])), text(b64(r['stderr']))
        code = r['raw_code']
        if code >= 1 << 31:
            code -= 1 << 32
        panic = None
        if r['exc'] == 'Panic':
            rows = err.decode('utf-8', 'surrogateescape').rstrip('\n').split('\n')
            panic = rows[-1]
            err = ''.join(x + '\n' for x in rows[:-1]).encode('utf-8', 'surrogateescape')
        if code not in (0, 134) or (code == 134 and panic is None) or (code == 0 and not out and not err):
            lines.append(f'//# exit: {code}')
        if out:
            lines += block('stdout', out)
        if err:
            lines += block('stderr', err)
        if panic is not None:
            lines.append('//# panic: ' + panic)
    else:
        raise Skip('ended with ' + str(r['exc']))
    # What the program did to the directories.
    after = r.get('dirs_after') or {}
    later = []
    for d, snap in dirs:
        new = after.get(d)
        if new is None:
            continue
        for name in sorted(new):
            if name.endswith('/'):
                if name not in snap:
                    later.append(f'//# exists {subs[d]}/{name[:-1]}')
            elif new[name] != snap.get(name):
                data = b64(new[name]) if new[name] is not None else None
                if data is not None and len(data) <= 4000:
                    lines += block(f'file {subs[d]}/{name}', data)
                else:
                    later.append(f'//# exists {subs[d]}/{name}')
        for name in sorted(snap):
            if name not in new:
                later.append(f'//# missing {subs[d]}/{name.rstrip("/")}')
    lines += later
    os.makedirs(path, exist_ok=True)
    for name, data in files.items():
        full = os.path.join(path, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(data)
    with open(os.path.join(path, 'CASE'), 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
        f.write('\n'.join(lines) + '\n')


def main(argv):
    record, cases = argv[0], argv[1]
    tiers = {}
    only = ''
    if '--tiers' in argv:
        p = argv[argv.index('--tiers') + 1]
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                tiers = json.load(f)
    if '--only' in argv:
        only = argv[argv.index('--only') + 1]
    off_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'interp_off.json')
    if os.path.exists(off_path):
        with open(off_path, encoding='utf-8') as f:
            OFF.update(json.load(f))
    tests, marks = load(record)
    ledger = collections.OrderedDict()
    written = 0
    for test, events in tests.items():
        _, cls, method = test.split('.')
        if only and only not in test:
            continue
        runs = [e for e in events if e['kind'] == 'run_sources']
        others = [e['kind'] for e in events if e['kind'] not in ('test', 'end', 'subtest', 'assert', 'run_sources')]
        desc = comment_of(events[0].get('source', ''))
        entry = {'programs': len(runs), 'cases': [], 'todo': [], 'other_events': others,
                 'skipped': marks.get(test, {}).get('reason') if test in marks else None}
        base = os.path.join(cases, cls, slug(method))
        width = max(2, len(str(len(runs))))
        for n, r in enumerate(runs, 1):
            name = base if len(runs) == 1 else os.path.join(base, f'{n:0{width}d}')
            rel = os.path.relpath(name, cases).replace(os.sep, '/')
            os.makedirs(os.path.dirname(name), exist_ok=True)
            for ext in ('.ctx', '.expect'):
                if os.path.exists(name + ext):
                    os.remove(name + ext)
            import shutil
            if os.path.isdir(name):
                shutil.rmtree(name)
            try:
                paths = any(os.path.isabs(a) or '\\' in a for a in r['args'])
                if len(r['sources']) > 1 or paths:
                    write_dir_case(r, name, desc, events[0].get('root') or os.getcwd())
                else:
                    write_case(r, name, tiers.get(rel, 1), desc)
                entry['cases'].append(rel)
                written += 1
            except Skip as e:
                entry['todo'].append({'program': n, 'why': str(e)})
        ledger[test] = entry
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ledger.json')
    if not only:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(ledger, f, indent=1)
    todo = sum(1 for e in ledger.values() if e['todo'] or e['other_events'] or e['skipped'] or not e['programs'])
    print(f'{written} cases written; {todo} tests of {len(ledger)} have something left')


if __name__ == '__main__':
    main(sys.argv[1:])
