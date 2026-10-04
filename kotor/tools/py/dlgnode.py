"""Prints one entry or reply of a DLG dump: dlgnode.py DUMP.txt entry|reply N
(DUMP.txt is `kotor/out/gffdump.exe --module M NAME.dlg > DUMP.txt`; exploration only)."""
import sys

lines = open(sys.argv[1], encoding='utf-8').read().split('\n')
want = 'EntryList' if sys.argv[2] == 'entry' else 'ReplyList'
n = sys.argv[3]
i = next(k for k, l in enumerate(lines) if l.startswith('  ' + want))
j = i + 1
while j < len(lines) and not lines[j].startswith('    [%s] id' % n):
    if lines[j].startswith('  ') and not lines[j].startswith('   '):
        sys.exit('not found')
    j += 1
out = [lines[j]]
j += 1
while j < len(lines) and not (lines[j].startswith('    [') and ' id ' in lines[j]) and (lines[j].startswith('     ') or lines[j].strip() == ''):
    out.append(lines[j])
    j += 1
print('\n'.join(out))
