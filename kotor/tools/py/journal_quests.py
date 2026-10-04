"""The journal's quests of a planet, with their entries' texts: journal_quests.py [TAG_PREFIX]  (default tar).
Reads global.jrl dumped by kotor/out/gffdump.exe (kotor/out/pt/global_jrl.txt) and resolves strrefs with tlkpy
(dev tooling: the order of a quest's entries is the order a playthrough goes in)."""
import re
import sys

sys.path.insert(0, 'kotor/tools/py')
import tlkpy

prefix = sys.argv[1] if len(sys.argv) > 1 else 'tar'
t = tlkpy.load()
lines = open('kotor/out/pt/global_jrl.txt', encoding='utf-8').read().split('\n')
cat = None
entry = None
end = '0'
for l in lines:
    if re.match(r'    \[\d+\] id \d+', l):
        cat = {'tag': '', 'comment': ''}
        continue
    if cat is None:
        continue
    m = re.match(r'      Tag: CExoString = "(.*)"', l)
    if m:
        cat['tag'] = m.group(1)
        if cat['tag'].lower().startswith(prefix):
            print('\n== %s (%s)' % (cat['tag'], cat['comment']))
        continue
    m = re.match(r'      Comment: CExoString = "(.*)"', l)
    if m:
        cat['comment'] = m.group(1)
        continue
    if not cat['tag'].lower().startswith(prefix):
        continue
    m = re.match(r'          ID: DWORD = (\d+)', l)
    if m:
        entry = m.group(1)
        continue
    m = re.match(r'          End: WORD = (\d+)', l)
    if m:
        end = m.group(1)
        continue
    m = re.match(r'          Text: CExoLocString = strref (\d+)', l)
    if m:
        txt = (t.text(int(m.group(1))) or '').replace('\n', ' ')
        print('  %s%s: %s' % (entry, ' (end)' if end == '1' else '', txt[:230]))
