# BWM walkmeshes: WOK, PWK, DWK

Checked against every walkmesh in the install (1554 files: 1202 WOK, 196 PWK, 156 DWK) by
`kotor/tools/py/bwmprobe.py`. Facts below are verified on that data unless marked
**(inferred)**; the probe's tallies are quoted with them. All values are little-endian.

## 1. Purpose

A walkmesh is a triangle mesh the engine uses for movement and collision, separate from the
rendered model:

- **WOK** (area walkmesh): one per room of an area. Its walkable triangles are the floor that
  creatures stand on; its non-walkable triangles are walls, pits, water and so on. It carries an
  AABB tree for ray and point queries, face-to-face adjacency for walking across the floor, and
  the floor's boundary (perimeter) with links to the neighbouring rooms.
- **PWK** (placeable walkmesh): the footprint a placeable blocks, plus up to two *use hooks*
  (where a creature stands to use it).
- **DWK** (door walkmesh): the volume a door blocks in each of its three states, plus use hooks.

## 2. Where they live

| Ext | Resource type | Count | Container |
|---|---|---|---|
| `wok` | 2016 | 1202 | `data/models.bif` |
| `dwk` | 2052 | 156 | `data/models.bif` |
| `pwk` | 2053 | 196 | `data/models.bif` |

No module RIM, texture pack, `patch.erf`, Override file or save holds a walkmesh (the probe
walks every copy of every resource with `Game.every_entry`). Type 3005 (`bwm`) does not occur.

Naming, verified:

- **WOK**: `<room>.wok`, where `<room>` is a room name in the area's LYT (and also the room's
  model, `<room>.mdl`). 222 WOKs have no geometry at all (sky boxes and similar rooms; 136-byte
  files). Some LYT rooms have no WOK at all (for example `m09zz_01a`, `m12ad_01a`); such a room
  has no floor.
- **PWK**: `<model>.pwk`, where `<model>` is a placeable model: the `modelname` column of
  `placeables.2da` (every PWK matches a row; 25 placeable models, mostly creature-like props such
  as `n_rodian`, have no PWK). 74 PWKs have no geometry, only use hooks.
- **DWK**: `<model>0.dwk`, `<model>1.dwk`, `<model>2.dwk`, where `<model>` is the door's model:
  the `modelname` column of `genericdoors.2da` (row = the UTD's `GenericType` when its
  `Appearance` is 0, which holds for every placed door whose UTD the probe resolved). 52 door models have
  all three files; 11 rows (`t_door01`..`t_door11`) have none. The digit is the door state:
  **0 = closed, 1 = open1, 2 = open2**. The engine's ASCII walkmesh reader names the nodes it
  reads `..._DWK_wg_closed/open1/open2` (walkmesh geometry) and `..._DWK_dp_...` (door use
  points), strings found in `swkotor.exe`; see section 7 for what the two open states mean.

## 3. Coordinate frames

| Kind | Stored vertices are in | To place them in the area |
|---|---|---|
| WOK | **area (world) space** already | nothing: use them as stored |
| PWK, DWK | the walkmesh node's local space | model point = vertex + `position` (header +60); then rotate by the object's GIT `Bearing` about +z and translate by its GIT position |

Evidence:

- **WOK.** For 830 of the 980 WOKs with geometry, every face equals the room model's AABB-node
  face transformed by the node's transform and then translated by the LYT room position, to
  within 1 mm; most other rooms differ by millimetres to centimetres on some faces (the WOK and
  the model were exported separately; `m12ab_01a`, `m12ac_01a`, `m17ab_00b` differ more). The
  header `position` equals the room model's AABB-node position (relative to the model root) in
  1011 of 1012 rooms checked: it is informational, already applied. GIT creatures and
  waypoints stand on walkable WOK faces at their stored z (1602 of 1619 creatures, 3945 of 4064
  waypoints, within 1.0 m in z, with no LYT offset added); the misses are off-mesh scripted
  points.
- **DWK.** Each open-state walkmesh is a thin piece at one jamb of the doorway. Taking vertex +
  `position`, 79 of 98 such pieces land on an x end of the closed walkmesh (taken the same
  way); taking the stored vertices alone, 73 of them sit at x = 0, in the middle of the doorway,
  which cannot be right. Two Korriban doors, `dor_lko01` (`position` (-0.137, 0.052, 0)) and
  `dor_lko02` (`position` 0 in x and y), get the same closed box (x from -3.76 to about 3.49)
  and the same open-state jamb (x = -3.76) only under vertex + `position`. Placed this way with
  GIT `X`, `Y`, `Z`, `Bearing`, closed DWKs fill the doorway gaps between rooms (see
  `kotor/out/bwm_area_m28aa_doors.png`).
- **PWK.** Comparing the PWK footprint's centre with the placeable model's mesh centre,
  vertex + `position` is closer for 54 files, the stored vertex for 13, and 30 are ties
  (`plc_cagesm`: `position` (-0.79, -0.50), footprint centre (0.79, 0.47) as stored).

GIT placement used throughout: `Bearing` is an angle in radians about +z, counter-clockwise
seen from above; a model point (x, y, z) goes to
`(X + x cos b - y sin b, Y + x sin b + y cos b, Z + z)`.

## 4. File layout

A 136-byte header, then the tables, packed back to back in the order listed below with no gaps,
and nothing after the last table (true of all 1554 files).

### Header

| Offset | Size | Type | Field |
|---|---|---|---|
| 0 | 8 | char[8] | `"BWM V1.0"` |
| 8 | 4 | u32 | walkmesh type: **1 = area (WOK)**, **0 = placeable or door (PWK, DWK)**; always matches the extension |
| 12 | 12 | f32[3] | relative use hook 1 (node-local) |
| 24 | 12 | f32[3] | relative use hook 2 |
| 36 | 12 | f32[3] | absolute use hook 1 (model space) |
| 48 | 12 | f32[3] | absolute use hook 2 |
| 60 | 12 | f32[3] | position: the walkmesh node's offset in its model |
| 72 | 4 | u32 | vertex count V |
| 76 | 4 | u32 | offset of vertices |
| 80 | 4 | u32 | face count F |
| 84 | 4 | u32 | offset of face vertex indices |
| 88 | 4 | u32 | offset of face materials |
| 92 | 4 | u32 | offset of face normals |
| 96 | 4 | u32 | offset of face planar distances |
| 100 | 4 | u32 | AABB node count N |
| 104 | 4 | u32 | offset of AABB nodes |
| 108 | 4 | u32 | unused: 0 in all PWK/DWK and 1173 WOKs; junk in 29 WOKs (`0x3F800000`, `0xFFFFFFFF`, small integers). Ignore it. |
| 112 | 4 | u32 | adjacency count W (= number of walkable faces) |
| 116 | 4 | u32 | offset of adjacency |
| 120 | 4 | u32 | perimeter edge count E |
| 124 | 4 | u32 | offset of perimeter edges |
| 128 | 4 | u32 | perimeter loop count L |
| 132 | 4 | u32 | offset of perimeter loop ends |

Offsets are from the start of the file. When a count is 0 its offset is meaningless: PWK and DWK
store 0 for the empty AABB/adjacency/edge/loop tables, WOKs store the next free byte, and
geometry-less files store 136 for every geometry table. A reader must check
`offset + count * size <= file size` only for nonzero counts.

### Tables

| Table | Element size | Count | Element |
|---|---|---|---|
| vertices | 12 | V | f32 x, y, z |
| face indices | 12 | F | u32 i0, i1, i2 (vertex indices, 0-based) |
| materials | 4 | F | u32 surface material id (row of `surfacemat.2da`) |
| normals | 12 | F | f32 nx, ny, nz |
| planar distances | 4 | F | f32 d |
| AABB nodes | 44 | N | see 5.4 |
| adjacency | 12 | W | i32 × 3, see 5.5 |
| perimeter edges | 8 | E | i32 edge, i32 transition, see 5.6 |
| perimeter loop ends | 4 | L | u32, see 5.7 |

## 5. Tables in detail

### 5.1 Faces, winding and edge numbering

Face `f` has corners `v[i0], v[i1], v[i2]`. Its **edge k** (k = 0, 1, 2) runs from corner `k`
to corner `(k + 1) % 3`, and is named by the integer `3 * f + k` wherever the format refers to
an edge. Verified through adjacency: in all 247,470 adjacency links the two edges share their
two vertex *indices* in reverse order (A's edge goes a→b, B's goes b→a).

Winding is counter-clockwise seen from the side the normal points to: the stored normal equals
`normalize((v1 - v0) × (v2 - v0))` (dot product ≥ 0.999 on every non-degenerate WOK and DWK
face). Floors face +z, so their corners run counter-clockwise seen from above and the face lies
to the left of each of its edges.

**WOK faces are sorted: all walkable faces first** (faces `0 .. W-1`), then the non-walkable
ones, where walkable means `walk = 1` in `surfacemat.2da` (all 980 WOKs with faces). PWK/DWK
faces are not sorted (4 DWKs have a walkable face after a non-walkable one).

### 5.2 Normals and planar distances

Each face's plane is `n · p + d = 0`, with `n` the unit normal and `d` the planar distance
(so `d = -n · v0`). Checked to 1e-3 on every corner of every non-degenerate WOK and DWK face.

- **PWK normals are all zero and the distances are uninitialised junk** (values like 2e17)
  in all 122 PWKs with geometry. Compute them from the corners if needed.
- 113 WOK faces have zero area (collinear corners; 3 of them repeat a vertex index, in
  `m26ad_03a` and `m38aa_11`). Their stored normal is a unit vector but their plane is
  meaningless. Skip zero-area faces in every query.

The ground height under (x, y) on a face is `z = -(d + nx·x + ny·y) / nz`; it is undefined for
vertical faces. 142 WOK faces with a walkable material are vertical or face downwards
(nz ≤ 0); a height query must ignore faces with nz near 0 or below.

### 5.3 Vertices

Plain positions, frame per section 3. Vertex positions are not fully welded: 64 WOKs and 10 DWKs
contain two vertices with identical positions, and 10 WOKs have one unreferenced vertex. Edge
sharing (adjacency) is by index, so this does not matter to adjacency; a tool that rebuilds
connectivity should match by index, not by position.

### 5.4 AABB tree (WOK only)

Present in every WOK with faces (980), absent in PWK/DWK. Node layout (44 bytes):

| Offset | Type | Field |
|---|---|---|
| 0 | f32[3] | box minimum |
| 12 | f32[3] | box maximum |
| 24 | i32 | face index for a leaf; -1 for an interior node |
| 28 | u32 | always 4 (378,136 nodes); meaning unknown, ignore |
| 32 | u32 | split plane ("most significant plane"): 0 in leaves; in interior nodes one of 1 = +x, 2 = +y, 4 = +z, 8 = -x, 16 = -y, 32 = -z |
| 36 | i32 | left child: node index (0-based); -1 in leaves |
| 40 | i32 | right child: node index (0-based); -1 in leaves |

Structure, verified on all 980 trees:

- The **root is node 0**. Nodes are in pre-order: an interior node's left child is always the
  next node (`left = i + 1`). Every node is reachable from the root exactly once.
- Every face appears in exactly one leaf, and every leaf holds one face, so the tree has
  `2F - 1` nodes. It covers **all** faces, walkable and not.
- An interior node's box is exactly the union of its children's boxes.
- A leaf's box is its face's bounds grown by about 0.01 on every side (exactly 0.01 within
  2e-4 in 70% of leaves). The tree comes from the room model's AABB node: in 978 of 980 rooms
  it has the same node count and, node for node, the model's boxes translated into area space
  and grown by 0.01; leaf face numbers differ because the WOK reorders faces walkable-first.
  So where the WOK geometry differs from the model's mesh, the boxes follow the model, not the
  WOK. (The split-plane values agree with the model's in 629 of 980 rooms; for the MDL doc.)
- The split plane names the axis along which the two children were separated; its sign says
  which side the right child is on (+: the right child's box centre is the larger one on that
  axis, -: the smaller). This holds for 183,627 of 188,578 interior nodes. It is only useful to
  visit the nearer child first in a ray cast. Values seen: 1 ×65,984, 2 ×67,571, 4 ×22,151,
  8 ×11,565, 16 ×12,901, 32 ×8,406.

Defects (see section 10): `m02af_01a`'s tree has 219 nodes for 140 faces and leaves out 30
faces (110..139, all non-walkable); 87 leaves in 25 WOKs have boxes that do not contain their
face (by 4 mm up to 0.73 m); the swoop tracks `m17mg_01a`/`m26mg_01a` have leaf boxes far larger
than their faces (harmless). Point queries through the stored tree missed a walkable face that
brute force finds at 4 of 22,794 sampled walkable-face centroids. **Recommendation: at load, refit every
box from the faces (leaves = face bounds + 0.01, then unions bottom-up), or rebuild the tree
when its face set is incomplete.**

### 5.5 Adjacency (WOK only)

One row of three i32 per walkable face: row `f` is face `f` (faces `0 .. W-1`, which are the
walkable ones). Entry `k` describes edge `k` of face `f`:

- `3 * g + j`: the edge is shared with edge `j` of walkable face `g`.
- `-1`: no walkable face across this edge (the edge borders a wall, a non-walkable face, a
  hole, or the room's edge). Every `-1` edge is a perimeter edge (5.6).

Only walkable faces have rows and only walkable faces are linked; non-walkable faces have no
adjacency. W equals the walkable face count in all 980 WOKs with faces; 11 WOKs have faces but
no walkable ones (W = 0, no perimeter). Links are symmetric (if A's edge points at B's edge, B's
points back) in all but 2 entries: in `m38aa_03` one edge is shared by four walkable faces, two
of which are the same triangle with opposite winding.

### 5.6 Perimeter edges and transitions (WOK only)

E entries of two i32:

| Offset | Type | Field |
|---|---|---|
| 0 | i32 | edge `3 * face + k` |
| 4 | i32 | transition: **-1 = none; otherwise the index (0-based) of a room in the area's LYT room list**, the room on the other side of this edge |

The listed edges are **exactly the walkable edges whose adjacency is -1**, each once (969 of
969 WOKs). They are grouped into closed loops (5.7): within a loop each edge ends at the vertex
index where the next begins, and the last edge ends where the first begins.

Transitions, verified against the LYTs: of 39,366 perimeter edges, 35,440 have -1 and 3,926 a
room index. 3,884 of these meet an edge of the named room's WOK at the same place (to 1 mm)
running the other way, whose own transition is the first room's index; 80 more meet it only to
within 0.1 m (`m38aa` rooms). The remaining 33 are in cut-scene layouts (`stunt_*`) that reuse
rooms of another area (`m12aa_01o` appears in seven LYTs); the index refers to the room's home
LYT. So a transition is a room-to-room link through a doorway or an open seam between rooms,
not a door or module transition.

### 5.7 Perimeter loop ends (WOK only)

L u32 values: the exclusive end index, into the perimeter edge table, of each loop. Loop 0 is
edges `[0, ends[0])`, loop i is `[ends[i-1], ends[i])`; the last value equals E (969 of 969).
L counts boundary loops, not islands: an outer boundary runs counter-clockwise seen from above
(positive signed area) and a hole clockwise; 81 WOKs have more than one outer loop (separate
islands of floor). 1,789 loops in all; the first loop is an outer one in 933 of 969 files.

## 6. Which tables each kind has

| | WOK | PWK | DWK |
|---|---|---|---|
| header type | 1 | 0 | 0 |
| vertices, faces, materials | yes (222 empty files) | yes (74 empty) | yes |
| normals, distances | valid | **zero normals, junk distances** | valid |
| AABB tree | yes | none | none |
| adjacency, perimeter edges, loops | yes, if any walkable face | none | none |
| use hooks | all zero | set (see 7) | set (see 7) |
| position | room model's walkmesh node offset, already applied | node offset, **add it** | node offset, **add it** |

Shapes: closed DWKs are all an 8-vertex, 12-face box around the door slab; open DWKs are a
4-vertex, 2-face vertical quad at a jamb in 44 doors (8/4, 16/24 or 16/20 in the rest). 110 of
the 122 PWK footprints are flat at z = 0; 12 have height.

## 7. Use hooks, position and door states

The header stores two use hooks (points where a creature stands to use the object) twice:
relative to the walkmesh node, and absolute (in model space), plus the node's position.

- **DWK**: `absolute = relative + position` holds for both hooks in all 156 files. Use the
  absolute hooks, in model space, then the GIT placement.
  - Closed state (`0`): two hooks, one on each side of the door (hook 1 at negative model y,
    hook 2 at positive y in 47 of 52 doors, the reverse in 5).
  - Open states (`1`, `2`): only hook 1 is set; relative hook 2 is zero, so absolute hook 2
    equals `position` and is **not** a use point. In every door, open1's hook is on the same
    side as the closed hook 1 and open2's on the side of closed hook 2. **(inferred)** open1 is
    the door opened from (or away from) the hook-1 side, open2 from the hook-2 side; which
    animation pairs with which state is not checked here.
  - Placed with the GIT, closed hooks land on walkable floor in front of and behind the door
    (640/724 and 593/724 door instances; the rest face unwalkable space behind locked or
    decorative doors).
- **PWK**: the absolute hooks are left zero in 187 and 189 of 196 files (they equal
  relative + position only where both are zero or position is zero). Only the relative hooks
  carry data: 184 PWKs have both hooks, 1 only hook 1, 3 only hook 2, 8 none.
  **(inferred, open)** whether a PWK's relative hook needs `position` added: the two readings
  differ by `position` (nonzero in 100 PWKs, median 0.085 m, 22 over 0.3 m) and the data does
  not decide it (placed hooks over walkable floor: 2,651 with position added vs 2,653 as
  stored, for hook 1; hooks falling inside their own footprint, among PWKs with a position
  over 0.1 m: 5 with position added vs 2 as stored). Recommended until the engine is read: model hook = relative + position,
  the same rule as the vertices and as DWK's absolute hooks.
- **WOK**: hooks are all zero.

## 8. Surface materials

`surfacemat.2da` (2DA V2.b in `2da.bif`, also in `global.rim`/`miniglobal.rim`), columns
`label walk walkcheck lineofsight grass sound name`. `name` is a plain string, not a strref.

| Id | label | walk | walkcheck | lineofsight | grass | sound | WOK faces | PWK | DWK |
|---|---|---|---|---|---|---|---|---|---|
| 0 | NotDefined | 0 | 0 | 0 | 0 | | | | |
| 1 | Dirt | **1** | 1 | 1 | 0 | DT | 57,142 | 3 | 56 |
| 2 | Obscuring | 0 | 0 | 1 | 0 | | 15,869 | | 8 |
| 3 | Grass | **1** | 1 | 1 | 1 | GR | 12,143 | | |
| 4 | Stone | **1** | 1 | 1 | 0 | ST | 6,501 | | |
| 5 | Wood | **1** | 1 | 1 | 0 | WD | 882 | | |
| 6 | Water | **1** | 1 | 1 | 0 | WT | 47 | | |
| 7 | Nonwalk | 0 | 1 | 1 | 0 | | 74,009 | 762 | 912 |
| 8 | Transparent | 0 | 1 | 0 | 0 | | 103 | | |
| 9 | Carpet | **1** | 1 | 1 | 0 | CP | 20 | | |
| 10 | Metal | **1** | 1 | 1 | 0 | MT | 18,534 | | |
| 11 | Puddles | **1** | 1 | 1 | 0 | WT | 16 | | |
| 12 | Swamp | **1** | 1 | 1 | 0 | WT | | | |
| 13 | Mud | **1** | 1 | 1 | 0 | WT | 327 | | |
| 14 | Leaves | **1** | 1 | 1 | 0 | LV | | | |
| 15 | Lava | 0 | 1 | 1 | 0 | | | | |
| 16 | BottomlessPit | 0 | 1 | 1 | 0 | | | | |
| 17 | DeepWater | 0 | 1 | 1 | 0 | | 29 | | |
| 18 | Door | **1** | 1 | 0 | 0 | | | | |
| 19 | NonWalkGrass | 0 | 1 | 1 | 1 | | 3,966 | | |
| 20-29 | CRAP | 0 | 0 | 0 | 0 | | | | |
| 30 | Trigger | **1** | 1 | 0 | 0 | | | | |

- **Walkable** = `walk = 1`: ids 1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30. This is the
  set that decides the WOK face order and adjacency (exact on all 980 WOKs).
- `lineofsight` **(confirmed in the executable)**: 1 = the face blocks sight. The room walkmesh keeps one
  bit mask of the materials it tests a line of sight against (`CSWWalkMesh` +0xd8, as +0xe0 is the walk
  mask `FindFaceUnderPoint` uses) and `QueryAABB` skips a face whose material bit is clear. Obscuring and
  Nonwalk block it; Transparent, Door and Trigger (0) let it through. A door's or placeable's walkmesh
  is tested differently: `CheckSegmentClearance` stops the line at any face nobody can walk on, in the
  door's current open state (closed DWK, or the open one), whatever its material. Most Obscuring faces are vertical (11,504 of 15,869).
- `walkcheck` **(inferred)**: 1 = the face takes part in movement collision. 0 only for
  NotDefined, Obscuring and the CRAP placeholders, so obscuring faces block sight but not
  movement.
- `grass` marks grass rendering surfaces; `sound` is the footstep sound family.
- Every material id in the data is a valid row; ids 0, 12, 14-16, 18, 20-30 never occur.
- PWK/DWK materials are mostly 7; the material-1 faces in DWKs are vertical quads of some
  open-door states (`dor_lda03x`, `dor_lma05x`, `dor_lts05x`, ...), and `plc_lockerlg` and
  `plc_chwdnblc` have a flat material-1 footprint. **(inferred)** Treat every PWK/DWK face as an
  obstacle: a creature cannot stand on a vertical face, and placing standable floor inside a
  locker is surely an exporter default rather than intent.

## 9. Queries an implementation needs

These are our recipes, built on the facts above; they are not read from the engine.

**Load.** Parse the header, bounds-check each nonzero table, reject indices out of range (face
corners < V, leaf faces < F, children < N, adjacency in [-1, 3W), perimeter edges < 3F, loop
ends increasing and last = E). Compute normals and planar distances for PWKs. Mark zero-area
faces. For WOKs, refit the AABB boxes from the faces, and rebuild the
tree if any face is missing from it. Keep everything in area space for WOK; for PWK/DWK keep
model space (`vertex + position`) and transform per placed object.

**Face under a point (ground height).** Descend the AABB tree from node 0, skipping nodes whose
box does not contain (x, y) in x and y. At a leaf, test (x, y) against the face's triangle in
the xy plane (same-sign 2D cross products, with a small epsilon); skip zero-area faces and faces
with |nz| tiny. Among the walkable faces found, take the one whose height
`z = -(d + nx·x + ny·y)/nz` is nearest at or below the creature's z plus a step allowance. Run
this over every room of the area (rooms' boxes can be culled first). The probe's
`faces_under` does exactly this and agrees with brute force.

**Ray cast** (line of sight, picking, camera). Descend from node 0 with a slab test against
each box; at leaves intersect the triangle (any standard ray-triangle test), keeping the
nearest hit. To visit the nearer child first: for split plane (axis a, sign s), if
`s * dir[a] > 0` the ray travels from the left child's side to the right child's, so visit left
first. For line of sight, ignore faces whose material has `lineofsight = 0`.

**Walking across the floor.** Track the walkable face a creature is on. To move along a
segment, find which edge of the current face the segment leaves through; look up
`adjacency[f][k]`: a value `3g + j` moves the creature into face `g` (entering through its edge
`j`); `-1` means the segment hits the perimeter. Find that edge's perimeter entry (index the
perimeter table by edge number at load): a transition `t ≥ 0` hands the creature to room `t` of
the LYT, where it is on the face of that room's WOK that shares the edge; `-1` blocks movement
(slide along the edge). Door and placeable walkmeshes are separate obstacles tested against the
movement segment after transforming them into area space; use the closed DWK while a door is
closed and the open1/open2 DWK while it is open.

**Pathfinding.** Adjacency is a ready-made face graph for the floor of one room; transitions
connect rooms. **(inferred)** The game also ships per-area PTH files with coarse waypoint
graphs, which are outside this format.

## 10. Data quirks a loader must tolerate

| What | Where | Count |
|---|---|---|
| PWK normals zero, planar distances junk | every PWK with geometry | 122 files |
| Header +108 holds junk | WOKs | 29 files |
| Zero-area faces (3 with a repeated vertex index) | WOKs | 113 faces |
| Walkable material on vertical or downward faces | WOKs | 142 faces |
| AABB tree for another face set (219 nodes, 140 faces, 30 faces missing) | `m02af_01a` | 1 file |
| AABB leaf box does not contain its face | 25 WOKs | 87 leaves |
| Asymmetric adjacency (an edge shared by four walkable faces) | `m38aa_03` | 2 entries |
| Transition index valid only in the room's home LYT | `stunt_*` LYTs | 33 edges |
| Transition edges that meet the neighbour only within 0.1 m | `m38aa` | 80 edges |
| Duplicate vertex positions, unreferenced vertices | WOK, DWK | 74 / 10 files |
| Empty-table offsets: 0 (PWK/DWK) or the next free byte (WOK) | all | |

## 11. Open questions for reverse engineering

- Whether the engine adds `position` to PWK use hooks; whether it uses the stored AABB trees
  or builds its own; what the AABB node's constant 4 is.
- How the engine uses the two open door states (which side, which animation).
- `swkotor.exe` contains an ASCII walkmesh reader (strings `pwk_use`, `pwk_dp_use_`,
  `_DWK_wg_`, `_DWK_dp_`, `closed`, `vertices`, ` trimesh `, ` dummy ` near 0x0074C358, used
  from code around 0x005CDB00-0x005CE6A0) and a binary walkmesh writer (the error string
  "ERROR: opening a Binary walkmesh file for writeing that already exists", used at
  0x0059A040). Reading those functions should settle the hook frames.

## 12. The probe

```
python kotor/tools/py/bwmprobe.py              # check everything (about 20 s)
python kotor/tools/py/bwmprobe.py --render     # also write the PNGs below
python kotor/tools/py/bwmprobe.py --dump m01aa_01a.wok
```

It parses every WOK, PWK and DWK in the install and checks: header magic and type; every table
inside the file, packed in order; all indices in range; normals unit length, agreeing with the
winding and with `n · v + d = 0`; walkable faces first and W = walkable count; the AABB tree
(root 0, pre-order, each face exactly once, interior boxes = union of children, leaf boxes
containing their faces, split-plane sign); adjacency symmetric and sharing vertices in reverse;
perimeter edges = walkable edges without adjacency; loops closing; DWK naming and the
abs = rel + position rule; the DWK frame evidence of section 3; every LYT's transitions against
the neighbouring room's edges; GIT creatures, waypoints and door/placeable use hooks against
the area floor, through the stored trees, compared with brute force.

Last run: 1554 walkmeshes, all parsed; the only failure classes are the quirks of section 10
(87 leaf boxes, 1 tree, 4 tree-query misses, 2 adjacency entries, 3 repeated indices,
33 stunt-layout transitions).

Renders in `kotor/out/` (looked at): `bwm_area_m01aa.png` (the Endar Spire's 15 room WOKs as
stored, by material, perimeters black, transition edges red: rooms meet at their transition
edges without any LYT offset), `bwm_area_m01aa_objects.png` and `bwm_area_m28aa_doors.png`
(crops with closed DWKs, PWKs, use hooks and creatures placed from the GIT: doors fill the
doorways, hooks lie on the floor either side), `bwm_dwk_dor_lma01.png` and
`bwm_dwk_dor_lhr01.png` (the three states of a door in model space, plan and elevation).

## Sources

The game data (above), BioWare's naming in `swkotor.exe` strings, and community descriptions of
the format (the KotOR modding wiki's "WOK Format" page and KotORBlender's walkmesh notes on
Deadly Stream for field names and the use-node idea; the NWN wiki's PWK page for use nodes in
the Aurora toolset). Every layout and meaning here was re-derived from the files.
