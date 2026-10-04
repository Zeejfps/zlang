"""A script's story in one line: the strings it names and the routines it calls, in order (dev tooling).

    python kotor/tools/playthrough/manaan/ncssum.py NAME...        needs kotor/out/ncs/NAME.txt (ncsall.sh)

Routines that only fetch things (GetObjectByTag, GetFirstPC, ...) are left out; the branch structure is not shown,
so read the full listing when the order of a branch matters."""
import re
import sys

SKIP = {'GetObjectByTag', 'GetFirstPC', 'GetEnteringObject', 'GetLoadFromSaveGame', 'GetArea', 'GetModule', 'GetTag',
        'GetIsObjectValid', 'GetPCSpeaker', 'GetLastSpeaker'}
for name in sys.argv[1:]:
    out = []
    pending = []
    for line in open(f'kotor/out/ncs/{name}.txt', encoding='utf-8', errors='replace'):
        m = re.search(r"CONSTS\s+'(.*)'", line)
        if m:
            pending.append(repr(m.group(1)))
            continue
        m = re.search(r'CONSTI\s+(-?\d+)', line)
        if m:
            pending.append(m.group(1))
            continue
        m = re.search(r'ACTION\s+\d+ \d+\s+; (\w+)', line)
        if m:
            if m.group(1) not in SKIP:
                out.append(f"{m.group(1)}({','.join(pending[-4:])})")
            pending = []
    print(f'{name}: ' + ' '.join(out))
