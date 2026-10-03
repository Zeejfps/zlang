import sys, re
# wh.py LOG KINDS [TAGPART]: compact list of `ui where` lines of the kinds (digits), e.g. 26 = creatures and doors
log, kinds = sys.argv[1], sys.argv[2]
part = sys.argv[3] if len(sys.argv) > 3 else ''
names = {'0': 'module', '1': 'area', '2': 'creature', '3': 'item', '4': 'trigger', '5': 'placeable', '6': 'door', '7': 'aoe', '8': 'waypoint', '9': 'encounter', '10': 'store', '11': 'sound'}
by = {}
for l in open(log, encoding='utf-8', errors='replace'):
    m = re.match(r'where (\d+) k(\d+) (\S*) at (\S+) (\S+) (\S+) hp (\S+)', l)
    if not m:
        continue
    k = m.group(2)
    if k not in kinds.split(',') and not (kinds.isdigit() and len(kinds) > 0 and all(c in kinds for c in k) and False):
        if k not in list(kinds):
            continue
    if part and part not in m.group(3):
        continue
    by.setdefault(k, []).append('%s:%s@%.0f,%.0f' % (m.group(1), m.group(3), float(m.group(4)), float(m.group(5))))
for k, v in by.items():
    print(names.get(k, k), len(v), ' '.join(v))
