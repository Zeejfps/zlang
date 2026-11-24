"""Prints what a test did, as record.py recorded it: its Python source, then each event.

    python tools/convert/trace.py RECORD.jsonl TEST_SUBSTRING [--full]
"""
import base64, json, sys
sys.path.insert(0, 'tools/convert')
from survey import load
tests, marks = load(sys.argv[1])
full = '--full' in sys.argv
def d(x):
    return base64.b64decode(x).decode('utf-8', 'replace') if x else ''
def clip(s, n=600):
    s = str(s)
    return s if full or len(s) <= n else s[:n] + f'...[{len(s)} chars]'
for name, events in tests.items():
    if sys.argv[2] not in name: continue
    print('=' * 20, name, marks.get(name, {}).get('reason', ''))
    for e in events:
        k = e['kind']
        if k == 'test':
            print(e['source'])
        elif k == 'assert':
            print('  ASSERT', e['name'], clip(json.dumps(e['args']), 400))
        elif k == 'subtest':
            print('  SUBTEST', clip(e['sub'], 200))
        elif k == 'run_sources':
            print('  RUN_SOURCES files=%s args=%s stdin=%r exc=%s code=%s diffs=%s' % ([f for _, f in e['sources']], e['args'], d(e['stdin'])[:80], e['exc'], e['raw_code'], e['diffs']))
            print('     stdout:', clip(repr(d(e['stdout'])), 300), 'stderr:', clip(repr(d(e['stderr'])), 300))
        elif k in ('subprocess.run', 'subprocess.Popen'):
            print('  ' + k, clip(e['argv'], 500), 'cwd=', e.get('cwd'), 'env=', clip(e.get('env'), 300), 'input=', clip(repr(d(e.get('input'))), 100))
            if k == 'subprocess.run':
                print('     code=', e['code'], 'stdout:', clip(repr(d(e['stdout']))), 'stderr:', clip(repr(d(e['stderr']))))
                for p, snap in (e.get('before') or {}).items():
                    print('     before', p, sorted(snap))
                for p, snap in (e.get('after') or {}).items():
                    print('     after ', p, sorted(snap))
        elif k == 'end':
            pass
        else:
            x = {kk: vv for kk, vv in e.items() if kk not in ('test', 'sub', 'seq', 'kind', 'snap', 'sources')}
            if 'sources' in e: x['files'] = [f for _, f in e['sources']]
            if e.get('snap'): x['snap_files'] = sorted(e['snap'])
            print('  ' + k, clip(json.dumps(x, default=repr), 900))
