# PTH: an area's path-finding graph

A PTH is a GFF ([gff.md](gff.md)) with file type `PTH ` that holds one area's coarse navigation
graph: a set of points on the floor (2D, X/Y in the area's world coordinates) and, for each point,
the points it connects to. The modding community describes it as the paths creatures use to get
from one part of a module to another when there is no direct line between them; fine movement
still happens on the walkmesh (`.wok`). The schema table also appears in
[gff-module.md](gff-module.md#pth-area-path-graph); this document adds the graph rules, quirks and
the exact write layout.

## Where the game keeps it

- Resource type 3003, extension `pth` ([resource-types.md](resource-types.md)).
- 132 copies, 109 distinct names, **all in `modules/*_s.rim`** ([rim.md](rim.md)); none in BIFs,
  Override or the save (the engine doesn't save it).
- Every module's `_s.rim` holds a PTH named after its area (the `Mod_Area_list/Area_Name` of the
  module's `module.ifo`; checked for all 117 modules). The engine presumably loads
  `<area resref>.pth` (*inferred*: not yet confirmed in the executable).
- 10 `_s.rim` files carry extra PTHs named after other areas: `e3_m21aa` and `m14aa` in the
  `danm14a*` rims, `m26gen` in `manm26ac`/`manm26ae`, `m01aa` and `m45gen` in
  `sta_m45ac`/`sta_m45ad` (all empty), and `m18ab` in `tat_m18aa` and `tat_m18ac` (not empty).
  Only the one named after the module's area matters.

## Layout

A GFF V3.2 tree. All values are inline (DWORD, FLOAT), so a PTH's field data block is always
empty.

| Path | GFF type | Meaning |
|---|---|---|
| (top struct) | Struct, id 0xFFFFFFFF | Exactly two fields, in this order: |
| `Path_Points` | List of struct id 2 | The graph's points, indexed from 0 in list order. |
| `Path_Points[i]/Conections` | DWORD | Number of links leaving point i (0..8 in the data). |
| `Path_Points[i]/First_Conection` | DWORD | Index in `Path_Conections` of point i's first link. |
| `Path_Points[i]/X` | FLOAT | World X of the point, metres (same space as GIT positions). |
| `Path_Points[i]/Y` | FLOAT | World Y. There is no Z: the walkmesh gives the height. |
| `Path_Conections` | List of struct id 3 | All links, grouped by source point. |
| `Path_Conections[k]/Destination` | DWORD | Index in `Path_Points` of the point link k leads to. |

The labels are spelt `Conections` and `First_Conection` (one n) and `Path_Conections`; a reader
must use these exact strings. Every point struct has exactly these four fields in this order, every
connection struct exactly one field; struct ids are always 2 and 3.

## Semantics and lookup rules

The links are an adjacency list stored the compressed way: point i's neighbours are

```
for k in First_Conection(i) .. First_Conection(i) + Conections(i) - 1:
    neighbour = Path_Conections[k].Destination
```

Rules that hold in every file in the install:

- Ranges are in bounds, contiguous and in point order: `First_Conection(0) = 0`,
  `First_Conection(i+1) = First_Conection(i) + Conections(i)`, and the last range ends exactly at
  the end of `Path_Conections` (no link belongs to no point).
- Every `Destination` is a valid point index.
- Links are **symmetric**: if i lists j, j lists i (0 one-way links), so the graph can be treated
  as undirected. A link's cost is presumably the 2D distance between its points (*inferred*); link
  lengths range from 1.04 m to 80.6 m.
- Links within a point are **not sorted** by destination (817 points in 91 files).
- Points are connected to 1..3 neighbours mostly: of 7014 points, 1436 have 1, 3643 have 2, 1442
  have 3, 409 have 4, and 83 have 5 to 8.

A path query therefore runs a graph search (for instance A* with straight-line distance) over the
points nearest the start and the goal; how the engine picks entry and exit points and blends with
walkmesh movement is engine behaviour to be confirmed by reverse engineering.

## Writing

The 94 non-empty PTHs were all built in the same creation order (the 38 empty ones are trivially
in any order). With the GFF strategies of [gff.md](gff.md#writing-files-the-way-the-game-does)
"second" (field indices) and "field" (list indices), the following reproduces every PTH byte for
byte:

```
top struct: add List Path_Points, then List Path_Conections
for each point i in order:
    create the point struct (id 2) as the next element of Path_Points
    for each of its links, in its order:
        create a connection struct (id 3) as the next element of Path_Conections
        add Destination (DWORD)
    add to the point struct: Conections, First_Conection (DWORD), X, Y (FLOAT)
```

So the struct array alternates a point and its links; the field array has each point's
`Destination` fields before the point's own four fields; the field-indices array holds the top
struct's two fields, then each point's four fields in point order; the list-indices array holds
`Path_Points` (count, point struct indices), then `Path_Conections` (count, connection struct
indices). `gff.write(g)` with the default depth-first order gives a valid file with different
bytes (points first, then links); `gff.write(g, order='keep')` on a read tree reproduces the
original.

## Quirks found in real data

- 38 PTHs are **empty** (no points, no links): every STUNT (cutscene) module, the minigame modules
  (`m03mg`, `m17mg`, `m26mg`), `m12ab`, the Ebon Hawk area `m12aa` in `ebo_m40aa` (other Ebon
  Hawk modules have a real graph), and the stray extra PTHs listed above.
- 18 **self links** (a point listing itself) in 10 files, e.g. `m13aa` point 81. Skip them.
- 3 files have **two disconnected components**: `m02ae` (Taris), and both copies of `m18ab`; the
  `tat_m18ac_s.rim` copy also has the only **isolated point** (0 links).
- The misspelt labels (`Conections`, `First_Conection`, `Path_Conections`).
- Points per area: up to 345; links up to 790.

## Checked

`kotor/tools/py/pth_probe.py` (from `G:\Dev\zlang`; `-v` prints one line per file):

```
python kotor/tools/py/pth_probe.py
```

It reads every copy of every `.pth` (`kres.Game().every_entry('pth')`) with `gff.py` and checks
the schema (top-level labels and types, point and connection fields, struct ids), that every
connection range lies inside `Path_Conections`, contiguity and order of the ranges, destination
bounds, and reports self links, duplicate links, unsorted links, one-way links, isolated points,
connected components, link lengths and which creation order the file follows. Result: **132 files
checked, 0 failing**; 7014 points, 15134 links; 0 duplicate links, 0 one-way links, 0 unreferenced
links; 18 self links in 10 files; 1 isolated point; 3 files with 2 components; creation order
interleaved 94, empty 38. `gff_probe.py` (see [gff.md](gff.md#checked)) also reproduces all 132
byte for byte.

## Sources

- Purpose and use by creatures: Deadly Stream, ".pth Editor" thread,
  https://deadlystream.com/topic/1583-pth-editor/
- GFF container: BioWare, *Aurora Generic File Format* (see [gff.md](gff.md#sources)).
- Everything else: measured on the install with the probe above.
