import re, sys
# stage.py LOG: per conversation the speaker/listener pairs with distance ranges and room pairs
cur = None
rows = {}
order = []
for l in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = re.match(r'\[(\d+) [\d.]+\] dialog start (\S+) owner=(\d+) \((\S*)\)', l)
    if m:
        cur = '%s@%s' % (m.group(2), m.group(1))
        rows[cur] = {}
        order.append(cur)
        continue
    m = re.match(r'\[(\d+) [\d.]+\] dialog stage: (\S*) and (\S*) stand ([\d.e+-]+) m apart \(rooms (-?\d+) and (-?\d+)\)', l)
    if m and cur:
        key = (m.group(2) or '<pc>', m.group(3) or '<pc>', m.group(5), m.group(6))
        d = float(m.group(4))
        lo, hi, n = rows[cur].get(key, (d, d, 0))
        rows[cur][key] = (min(lo, d), max(hi, d), n + 1)
for c in order:
    print(c)
    for k, (lo, hi, n) in rows[c].items():
        flag = ''
        if hi > 8.0: flag += ' FAR'
        if k[2] != k[3]: flag += ' ROOMS'
        print('   %s -> %s  %.1f..%.1f m  rooms %s/%s  x%d%s' % (k[0], k[1], lo, hi, k[2], k[3], n, flag))
