"""Writes directory cases from what record.py recorded of the tests that do more than run one
program: ctxc commands in a project's directory, build.ctx projects, executables run by hand
(LLM-FIRST 5.2).

    python tools/convert/convert_steps.py RECORD.jsonl CASES [--only SUBSTRING]

Each directory a test worked in becomes a case, CLASS/TEST or CLASS/TEST/NN: its files as they
were before the first command, then a step for each thing the test did there, in order, with the
exit code and output recorded. A file the test changed between two commands becomes a `write`
step. What this can't express is noted in tools/convert/steps.json for a person: a test's own
assertions on files, on timing, on other processes.
"""

import base64
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from survey import load  # noqa: E402
from convert import block, comment_of, settled, slug, word  # noqa: E402

BIG = 6000


def b64(s):
    return base64.b64decode(s) if s else b''


class Case:
    def __init__(self, key):
        self.key = key              # the directory, or the executable of a program built alone
        self.files = {}             # name -> bytes, as the case starts
        self.now = None             # the directory's files after the last step
        self.lines = []
        self.exes = {}              # executable path -> name
        self.notes = []
        self.steps = 0


class Test:
    def __init__(self, name, events):
        self.name = name
        self.events = events
        self.root = events[0].get('root')
        self.native = events[0].get('native')
        self.python = events[0].get('python')
        self.cases = collections.OrderedDict()
        self.dirs = []
        self.notes = []
        self.asserts = []

    def case_for(self, key, snapshot=None):
        c = self.cases.get(key)
        if c is None:
            c = self.cases[key] = Case(key)
            if snapshot is not None:
                c.files = {k: b64(v) for k, v in snapshot.items() if v is not None and not k.endswith('/')}
                c.empty = [k[:-1] for k in snapshot if k.endswith('/') and not any(x.startswith(k) and x != k for x in snapshot)]
                c.now = dict(c.files)
        return c

    def dir_of(self, e, paths):
        """The directory an event is about: its cwd, or the first known directory a path is in."""
        known = list((e.get('dirs') or {}).keys()) + [k for k in self.cases if isinstance(k, str)]
        for p in paths:
            if not isinstance(p, str):
                continue
            for d in known:
                if os.path.normcase(p) == os.path.normcase(d) or os.path.normcase(p).startswith(os.path.normcase(d) + os.sep):
                    return d
        return None

    def text(self, s, d):
        """s with the directory, ctxlang/ and ctxc named by their placeholders."""
        if isinstance(s, bytes):
            return self.text(s.decode('utf-8', 'surrogateescape'), d).encode('utf-8', 'surrogateescape')
        for path, name in ((d, '{dir}'), (self.native, '{ctxc}'), (self.root, '{home}'), (os.path.dirname(self.root or ''), '{repo}')):
            if not path or not isinstance(path, str):
                continue
            for variant in (path, path.replace('\\', '/'), path.replace('\\', '\\\\')):
                pat = re.compile(re.escape(variant) + r'((?:[\\/]+[\w.\-]+)*)', re.I if os.name == 'nt' else 0)
                s = pat.sub(lambda m: name + re.sub(r'[\\/]+', '/', m.group(1)), s)
        return settled(s)

    def sync(self, c, e):
        """Steps for what the test changed in the case's directory since its last step."""
        snap = (e.get('dirs') or {}).get(c.key)
        if snap is None or c.now is None:
            return
        new = {k: b64(v) for k, v in snap.items() if v is not None and not k.endswith('/')}
        for name in sorted(new):
            if c.now.get(name) != new[name]:
                if c.steps == 0:
                    c.files[name] = new[name]
                elif is_text(new[name]):
                    c.lines += block(f'write {word(name)}', new[name])
                else:
                    c.notes.append(f'the test wrote {name}, which is not text')
        for name in sorted(c.now):
            if name not in new:
                if c.steps == 0:
                    c.files.pop(name, None)
                else:
                    c.lines.append(f'//# remove {word(name)}')
        c.now = new

    def after(self, c, e):
        snap = (e.get('dirs_after') or {}).get(c.key)
        if snap is not None:
            c.now = {k: b64(v) for k, v in snap.items() if v is not None and not k.endswith('/')}

    def expect(self, c, code, out, err, d, panic=None):
        if code is not None and code >= 1 << 31:
            code -= 1 << 32
        lines = []
        out, err = self.text(out or b'', d), self.text(err or b'', d)
        if panic is not None:
            rows = err.decode('utf-8', 'surrogateescape').rstrip('\n').split('\n')
            lines.append('//# panic: ' + rows[-1])
            err = ''.join(x + '\n' for x in rows[:-1]).encode('utf-8', 'surrogateescape')
        elif code is not None:
            lines.append(f'//# exit: {code}')
        for name, data in (('stdout', out), ('stderr', err)):
            if not data:
                continue
            if len(data) > BIG:
                needles = [n for n in self.asserts if n and n.encode('utf-8', 'surrogateescape') in data]
                c.notes.append(f'{name} is {len(data)} bytes: stated by `has`, from the test\'s assertIn')
                for n in needles:
                    lines += block(f'{name} has', (n + '\n').encode('utf-8', 'surrogateescape'))
                if not needles:
                    lines.append(f'//# {name} any')
                    c.notes.append(f'{name}: no assertIn found; `any` written: STATE IT BY HAND')
            else:
                lines += block(name, data)
        c.lines += lines

    def words(self, argv, d, cwd):
        out = []
        std = None
        i = 0
        argv = list(argv)
        while i < len(argv):
            a = argv[i]
            if isinstance(a, str) and re.search(r'[\\/]std[\\/]alloc\.ctx$', a.replace('/', os.sep)) or a == 'std/alloc.ctx' or re.fullmatch(r'(\.\./)+std/alloc\.ctx', a or ''):
                j = i
                while j < len(argv) and argv[j] != '--':
                    j += 1
                first = argv[i]
                kind = '{std:abs}' if os.path.isabs(first) else '{std}'
                layers = {re.search(r'std/os/(\w+)/', x.replace('\\', '/')).group(1) for x in argv[i:j] if 'std/os/' in x.replace('\\', '/')}
                host = 'windows' if os.name == 'nt' else 'linux'
                if kind == '{std}' and layers and layers != {host} and layers != {host, 'posix'}:
                    layer = 'interp' if 'interp' in layers else sorted(layers - {'posix'})[0]
                    kind = '{std:%s}' % layer
                out.append(kind)
                i = j
                continue
            out.append(word(self.text(a, d)) if not re.fullmatch(r'[\w./{}:\-=+,@]+', self.text(a, d)) else self.text(a, d))
            i += 1
        return out

    def run(self):
        for e in self.events:
            k = e['kind']
            if k == 'assert' and e['name'] == 'assertIn' and isinstance(e['args'][0], str):
                self.asserts.append(e['args'][0])
        self.asserts_done = True
        for e in self.events:
            k = e['kind']
            if k == 'write_program':
                d = e['ret'][0]
                c = self.case_for(d)
                if c.now is None:
                    c.files = {f or f'main{i}.ctx': s.encode('utf-8', 'surrogateescape') for i, (s, f) in enumerate(e['sources'])}
                    c.now = dict(c.files)
            elif k == 'subprocess.run':
                argv = e['argv']
                d = self.dir_of(e, [e.get('cwd')] + argv[1:])
                head = argv[0]
                if d is None:
                    d = next(reversed(self.cases), None) if self.cases else None
                    if d is None:
                        d = '(none)'
                c = self.case_for(d, (e.get('dirs') or {}).get(d))
                self.sync(c, e)
                if os.path.normcase(head) == os.path.normcase(self.native or ''):
                    name = 'ctxc'
                elif head in c.exes:
                    name = '{%s}' % c.exes[head]
                elif os.path.basename(head).lower() in ('gcc.exe', 'gcc', 'cc', 'clang', 'cc.exe', 'clang.exe'):
                    name = 'cc'
                elif os.path.basename(head).lower() in ('ar', 'ar.exe'):
                    name = 'ar'
                else:
                    c.notes.append(f'a command the case can\'t run: {head}')
                    name = '?' + os.path.basename(head)
                ws = self.words(argv[1:], d, e.get('cwd'))
                c.lines.append('//# $ ' + ' '.join([name] + ws))
                c.steps += 1
                cwd = e.get('cwd')
                if cwd and os.path.normcase(cwd) != os.path.normcase(d):
                    if os.path.normcase(cwd).startswith(os.path.normcase(d) + os.sep):
                        c.lines.append('//# cwd: ' + os.path.relpath(cwd, d).replace(os.sep, '/'))
                    else:
                        c.notes.append(f'cwd is {cwd}')
                if name == 'ar' and '//# needs: ar' not in c.lines:
                    c.lines.insert(0, '//# needs: ar')
                for kk, v in sorted(((e.get('env') or {}).get('set') or {}).items()):
                    if kk == 'CTX_HOME' and os.path.normcase(v) == os.path.normcase(self.root):
                        continue
                    if name in ('cc', 'ar'):
                        continue
                    c.lines.append(f'//# env: {kk}={self.text(v, d)}')
                if e.get('input'):
                    c.lines += block('stdin', b64(e['input']))
                if e['stdout'] is None and e['stderr'] is None:
                    c.lines.append(f'//# exit: {e["code"]}')
                else:
                    self.expect(c, e['code'], b64(e['stdout']), b64(e['stderr']), d)
                self.after(c, e)
            elif k == 'build_project':
                d = e['dir']
                c = self.case_for(d, (e.get('dirs') or {}).get(d) or e.get('snap'))
                self.sync(c, e)
                c.lines.append('//# project')
                c.steps += 1
                if e['exc'] == 'CompileError':
                    c.lines += block('errors', self.text(e['text'].replace('\r\n', '\n'), d).encode('utf-8', 'surrogateescape'))
                elif e['exc'] == 'Panic':
                    pos = e['pos']
                    c.lines.append('//# panic: ' + (f'{pos[2] or "build"}:{pos[0]}:{pos[1]}' if pos else 'build') + ': panic: ' + e['msg'])
                    c.notes.append('a build program\'s panic: check the line')
                elif e['exc']:
                    c.notes.append(f'build_project raised {e["exc"]}: {e["exc_str"][:200]}')
                    m = re.match(r'build.ctx exited with (-?\d+)', e['exc_str'])
                    if m:
                        c.lines.append(f'//# exit: {m.group(1)}')
                else:
                    for name, exe in e['ret']:
                        c.exes[exe] = name
                self.after(c, e)
            elif k == 'build_sources':
                files = collections.OrderedDict((f or f'main{i}.ctx', s.encode('utf-8', 'surrogateescape')) for i, (s, f) in enumerate(e['sources']))
                key = ('built', len(self.cases))
                c = self.case_for(key)
                c.files, c.now = dict(files), None
                name = 'program'
                c.lines.append(f'//# build {name}: ' + ' '.join(word(f) for f in files))
                c.steps += 1
                if e['exc'] == 'CompileError':
                    c.lines += block('errors', settled(e['text'].replace('\r\n', '\n')).encode('utf-8', 'surrogateescape'))
                elif e['exc']:
                    c.notes.append(f'build_sources raised {e["exc"]}')
                else:
                    c.exes[e['ret'][0]] = name
            elif k == 'run_exe':
                call = e['call']
                exe = call['exe']
                c = next((x for x in self.cases.values() if exe in x.exes), None)
                if c is None:
                    c = self.case_for(('exe', exe))
                    c.notes.append(f'an executable no step built: {exe}')
                    c.exes[exe] = 'unknown'
                d = c.key if isinstance(c.key, str) else None
                self.sync(c, e)
                args = [str(a) for a in call.get('args') or ()]
                c.lines.append('//# $ ' + ' '.join(['{%s}' % c.exes[exe]] + [word(self.text(a, d)) if not re.fullmatch(r'[\w./{}:\-=+,@]+', self.text(a, d)) else self.text(a, d) for a in args]))
                c.steps += 1
                for a in args:
                    if os.path.isabs(a) or (self.python and a == self.python):
                        c.notes.append(f'an argument that is a path: {a}')
                if call.get('cwd'):
                    c.notes.append(f'cwd is {call["cwd"]}')
                for kk, v in sorted((call.get('env') or {}).items()):
                    c.lines.append(f'//# env: {kk}={self.text(v, d)}')
                if call.get('stack_size'):
                    c.lines.append(f'//# stack: {call["stack_size"]}')
                if call.get('timeout'):
                    c.lines.append(f'//# timeout: {call["timeout"]}')
                if e.get('had_inp'):
                    c.notes.append('the run had standard input, which wasn\'t recorded')
                x = e['execs'][0] if e['execs'] else None
                if x is None:
                    c.notes.append('the run recorded nothing')
                else:
                    self.expect(c, x['code'], b64(x['stdout']), b64(x['stderr']), d, panic=e['msg'] if e['exc'] == 'Panic' else None)
                self.after(c, e)
            elif k == 'ir_sources':
                files = collections.OrderedDict((f or f'main{i}.ctx', s.encode('utf-8', 'surrogateescape')) for i, (s, f) in enumerate(e['sources']))
                c = self.case_for(('ir', len(self.cases)))
                c.files, c.now = dict(files), None
                c.lines.append('//# $ ctxc ir {std} -- ' + ' '.join(word(f) for f in files))
                c.steps += 1
                if e['exc']:
                    c.lines.append('//# exit: 1')
                    c.lines.append('//# stdout any')
                    c.notes.append(f'ctxc ir failed: {e["exc_str"][:200]}: STATE IT BY HAND')
                else:
                    c.lines.append('//# exit: 0')
                    self.ir = (c, e['ret'], len(c.lines))
                    c.stated = 0
            elif k == 'assert' and getattr(self, 'ir', None):
                c, text, at = self.ir
                a = e['args']
                add = None
                if e['name'] == 'assertIn' and len(a) >= 2 and a[1] == text and isinstance(a[0], str):
                    add = block('stdout has', (a[0] + '\n').encode('utf-8', 'surrogateescape'))
                elif e['name'] == 'assertNotIn' and len(a) >= 2 and a[1] == text and isinstance(a[0], str):
                    add = block('stdout lacks', (a[0] + '\n').encode('utf-8', 'surrogateescape'))
                elif e['name'] == 'assertRegex' and len(a) >= 2 and a[0] == text:
                    w = unregex(a[1])
                    if w is None:
                        c.notes.append(f'a regular expression to state by hand: {a[1]}')
                    else:
                        add = block('stdout has', (w + '\n').encode('utf-8', 'surrogateescape'))
                elif e['name'] in ('assertEqual', 'assertTrue', 'assertFalse', 'assertNotEqual', 'assertNotRegex', 'assertGreater', 'assertLess'):
                    c.notes.append(f'an assertion to state by hand: {e["name"]} {json.dumps(a)[:300]}')
                if add:
                    c.lines += add
                    c.stated += 1
            elif k in ('ctxc_build', 'read_program', 'subprocess.Popen', 'run_sources', 'build_files'):
                self.notes.append(f'{k}: by hand')
            if k not in ('test', 'end', 'subtest', 'assert'):
                env = e.get('environ') or {}
                if env.get('set') or env.get('unset'):
                    self.notes.append(f'os.environ at {k}: {env}')


def unregex(p):
    r"""A regular expression as an expected text with wildcards, or None if it has more than
    literals, `\d+` ({n}) and `.*`, `.*?`, `\w+`, `[^)]*` ({any})."""
    out = []
    i = 0
    if p.startswith('(?m)'):
        p = p[4:]
    p = p.lstrip('^')
    if p.endswith('$') and not p.endswith('\\$'):
        p = p[:-1]
    while i < len(p):
        c = p[i]
        if p.startswith('\\d+', i):
            out.append('{n}')
            i += 3
        elif p.startswith('\\w+', i):
            out.append('{any}')
            i += 3
        elif p.startswith('.*?', i):
            out.append('{any}')
            i += 3
        elif p.startswith('.*', i):
            out.append('{any}')
            i += 2
        elif p.startswith('[^)]*', i):
            out.append('{any}')
            i += 5
        elif c == '\\' and i + 1 < len(p):
            n = p[i + 1]
            if n == 'n':
                out.append('\n')
            elif n in '()[]{}.*+?|$^\\/-':
                out.append(n)
            else:
                return None
            i += 2
        elif c in '()[]{}.*+?|$^':
            return None
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def is_text(data):
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return b'\x00' not in data


def main(argv):
    record, cases = argv[0], argv[1]
    only = argv[argv.index('--only') + 1] if '--only' in argv else ''
    tests, marks = load(record)
    report = collections.OrderedDict()
    written = 0
    for name, events in tests.items():
        if only and only not in name:
            continue
        kinds = {e['kind'] for e in events} - {'test', 'end', 'subtest', 'assert'}
        if not kinds or kinds == {'run_sources'}:
            continue
        _, cls, method = name.split('.')
        t = Test(name, events)
        t.run()
        desc = comment_of(events[0].get('source', ''))
        base = os.path.join(cases, cls, slug(method))
        entry = {'notes': t.notes, 'cases': {}}
        live = [c for c in t.cases.values() if c.steps]
        for c in live:
            # A program that is only built: the test expected it to compile.
            if c.steps == 1 and len(c.lines) == 1 and c.lines[0].startswith('//# build program: '):
                c.lines = ['//# program: ' + c.lines[0][len('//# build program: '):], '//# compiles']
        for c in live:
            if getattr(c, 'stated', None) == 0:
                c.lines.append('//# stdout any')
                c.notes.append('nothing stated of the IR: STATE IT BY HAND')
        mixed = 'run_sources' in kinds
        for n, c in enumerate(live, 1):
            d = base if len(live) == 1 and not mixed else os.path.join(base, f'c{n:02d}' if mixed else f'{n:02d}')
            rel = os.path.relpath(d, cases).replace(os.sep, '/')
            os.makedirs(d, exist_ok=True)
            for fname, data in c.files.items():
                if fname.lower().endswith(('.exe', '.o', '.a', '.obj')):
                    continue
                path = os.path.join(d, fname)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(data)
            made = [f'//# make dir {word(x)}' for x in getattr(c, 'empty', [])]
            with open(os.path.join(d, 'CASE'), 'w', encoding='utf-8', newline='', errors='surrogateescape') as f:
                f.write('\n'.join([('// ' + x).rstrip() for x in desc] + made + c.lines) + '\n')
            entry['cases'][rel] = c.notes
            written += 1
        report[name] = entry
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'steps.json')
    if not only:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=1)
    print(f'{written} directory cases written for {len(report)} tests')


if __name__ == '__main__':
    main(sys.argv[1:])
