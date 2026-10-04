"""A route along an area's path graph, as bot stops: python pthroute.py FILE.pth X0,Y0 X1,Y1 [SPACING]

FILE.pth is `kotor/out/resls.exe --module MODULE get NAME.pth`. Prints the shortest way over the graph's points from the point
nearest the first place to the point nearest the second as `X,Y` stops about SPACING metres apart (default 25), for a
`ui bot route` line in a part that must keep to a hidden path (the Eastern Dune Sea). Dev tooling only."""
import heapq
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'py'))
import gff  # noqa: E402

g = gff.read(open(sys.argv[1], 'rb').read())
pts = g.root.get('Path_Points')
conns = [c.get('Destination') for c in g.root.get('Path_Conections')]
xy = [(p.get('X'), p.get('Y')) for p in pts]
adj = [[] for _ in pts]
for i, p in enumerate(pts):
    first, n = p.get('First_Conection'), p.get('Conections')
    for k in range(first, first + n):
        j = conns[k]
        adj[i].append(j)
        adj[j].append(i)


def nearest(at):
    return min(range(len(xy)), key=lambda i: (xy[i][0] - at[0]) ** 2 + (xy[i][1] - at[1]) ** 2)


a = tuple(float(v) for v in sys.argv[2].split(','))
b = tuple(float(v) for v in sys.argv[3].split(','))
space = float(sys.argv[4]) if len(sys.argv) > 4 else 25.0
s, t = nearest(a), nearest(b)
dist = {s: 0.0}
prev = {}
heap = [(0.0, s)]
while heap:
    d, u = heapq.heappop(heap)
    if u == t:
        break
    if d > dist.get(u, 1e30):
        continue
    for v in adj[u]:
        nd = d + math.hypot(xy[u][0] - xy[v][0], xy[u][1] - xy[v][1])
        if nd < dist.get(v, 1e30):
            dist[v] = nd
            prev[v] = u
            heapq.heappush(heap, (nd, v))
if t not in dist:
    print('no path between', xy[s], 'and', xy[t])
    sys.exit(1)
path = [t]
while path[-1] != s:
    path.append(prev[path[-1]])
path.reverse()
stops = [path[0]]
acc = 0.0
for i in range(1, len(path)):
    acc += math.hypot(xy[path[i]][0] - xy[path[i - 1]][0], xy[path[i]][1] - xy[path[i - 1]][1])
    if acc >= space:
        stops.append(path[i])
        acc = 0.0
if stops[-1] != path[-1]:
    stops.append(path[-1])
print('length %.0f m over %d points' % (dist[t], len(path)))
print(' '.join('%d,%d' % (round(xy[i][0]), round(xy[i][1])) for i in stops))
