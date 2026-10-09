# MDL / MDX: binary models (KOTOR 1)

Every 3D thing the game draws (area rooms, creatures, heads, items, placeables, doors, effects,
lightsabers, GUI 3D widgets) is a binary model: an **MDL** file holding the node tree, materials,
faces, controllers and animations, plus an **MDX** file holding the per-vertex arrays the GPU
consumes. This is the layout KOTOR 1 (PC, 2003) ships, which keeps the in-memory structures of
BioWare's compiler, function-pointer fields included. Everything below was checked against all
3,072 MDL files in the install (see [Checked](#checked)). Tags: **confirmed** = holds for every
file, or seen in a render; **RE** = read from `swkotor.exe` (Ghidra export); **docs** = public
write-ups (xoreos-docs `kotor_mdl.html`, Torlack's NWN binary-model notes); **inferred** = our
best reading, not proven.

Related: [models-usage.md](models-usage.md) (how the game assembles models),
[tpc.md](tpc.md) / [tga.md](tga.md) / [txi-render.md](txi-render.md) (textures),
[bwm.md](bwm.md) (walkmeshes; the AABB nodes here are their in-model twin).

## Where it lives

| Type | Id | Where | Count |
|---|---|---|---|
| `mdl` | 2002 | `data/models.bif` 2445, `data/items.bif` 305, `data/player.bif` 63, `data/party.bif` 19, `rims/global.rim` 168, `rims/miniglobal.rim` 40, `rims/chargen.rim` 30, `rims/mainmenu.rim` 1, `patch.erf` 1 | 3,072 entries |
| `mdx` | 3008 | the same BIFs; for the RIMs, **`X.rim` holds the MDL and `Xdx.rim` the MDX** (`global`/`globaldx`, `miniglobal`/`miniglobaldx`, `chargen`/`chargendx`, `mainmenu`/`mainmenudx`) | 3,085 entries |

Pair an MDL with the MDX of the same resref from the same container, else from the `dx` sibling
RIM. 538 models have no mesh data and an empty (0-byte) MDX. Area modules (`modules/*.rim`) carry
no models: rooms live in `models.bif`.

## Conventions

* Little-endian. `u8/u16/u32`, `i16/i32`, `f32` (IEEE single). Quaternions are unit `f32[4]`.
* **Model offsets.** Every offset stored in the MDL counts from the start of the *model data*,
  which is file offset **12** (just after the file header). "Offset 0" below means file byte 12.
* **MDX offsets** count from the start of the MDX file.
* **Array** = 12 bytes: `u32 offset, u32 count, u32 count again` (the second is the allocated
  size; equal to the first in every file). An array with count 0 may have any offset.
* **Names** are `char[N]`, NUL-padded, not necessarily NUL-terminated if full, compared
  case-insensitively (the data mixes case freely: `P_BastilaBB` vs `p_bastilabb`).
* **Function-pointer fields** are addresses inside the original compiler/engine. They are the
  same in every file of a kind (listed below) and carry no information; ignore them.
* **Garbage fields.** Several padding bytes hold uninitialized memory from the compiler (noted
  per field). Never interpret them.
* **Space.** Right-handed, **Z up**, characters and creatures **face +Y**. Front faces wind
  **counter-clockwise**: the stored face normal equals `(v1 - v0) × (v2 - v0)` normalized in
  5,768,814 of 5,771,426 faces (confirmed); renderers back-face cull (confirmed by room renders,
  which look right only when culled).
* **Layout.** The structures below account for every byte of every MDL exactly once: no gaps, no
  overlaps (confirmed: the probe tiles all 3,072 files). Use the offsets, not file order, but the
  order is: file header, geometry+model header, name table, then node data, animations.

## File header (12 bytes, file offset 0)

| Off | Type | Meaning |
|---|---|---|
| 0 | u32 | 0. A non-zero value means an ASCII model (none ship). |
| 4 | u32 | Size of the model data (= MDL file size − 12, confirmed) |
| 8 | u32 | Size of the MDX file (confirmed) |

## Geometry header (80 bytes)

At model offset 0 for the model, and at the start of every animation header.

| Off | Type | Meaning |
|---|---|---|
| 0 | u32 | function pointer: `0x413670` (model), `0x4134F0` (animation) |
| 4 | u32 | function pointer: `0x405520` (model), `0x43ECE0` (animation) |
| 8 | char[32] | name: the model resref (case may differ; `dor_lma022` says `DOR_LMA02`) or the animation name |
| 40 | u32 | offset of the root node |
| 44 | u32 | node count, see below (do not use it to size anything; walk the tree) |
| 48 | array | runtime only, always 0,0,0 |
| 60 | array | runtime only, always 0,0,0 |
| 72 | u32 | reference count, always 0 |
| 76 | u8 | geometry type: **2** = model, **5** = animation (confirmed) |
| 77 | u8[3] | padding |

Node count: for a model, its own node count, plus (supermodel's node count + 1) when it has a
supermodel (3,068 of 3,072; the 4 exceptions are cut-scene puppets). For an animation it usually
equals the *model's* name count (6,011 of 7,143), not the animation's node count.

## Model header (116 bytes, model offset 80; header total 196)

| Off | Type | Meaning |
|---|---|---|
| 80 | u8 | classification, see below |
| 81 | u8 | subclassification: 0 (2,777), 2 (81), 4 (214, all `plc_*`). Meaning unknown. |
| 82 | u8 | 0 in every file |
| 83 | u8 | affected by fog: 1 (2,983), 0 (89: sky domes, space backdrops) |
| 84 | u32 | child model count, always 0 |
| 88 | array | animation offsets: `u32` model offsets of the animation headers |
| 100 | u32 | supermodel pointer: runtime leftover (0 or garbage); ignore |
| 104 | f32[3] | bounding box min. 2,405 models keep the compiler default (−5,−5,−1) |
| 116 | f32[3] | bounding box max, default (5,5,10) |
| 128 | f32 | radius, default 7 |
| 132 | f32 | animation scale (1.0 in 2,905; e.g. 1.06 for `pmb?m`, 0.971 `pfb?s`, 0.278 `c_holovandar`) |
| 136 | char[32] | supermodel resref, `NULL` when none (2,659) |
| 168 | u32 | offset of the **head root** node: the root itself, except 136 character models where it is `neck_g` |
| 172 | u32 | 0 |
| 176 | u32 | MDX size (same as the file header's) |
| 180 | u32 | 0 (MDX offset) |
| 184 | array | name table: `u32` model offsets of NUL-terminated node names |

Classification (values seen, names inferred from which models carry them):

| Value | Models | Meaning |
|---|---|---|
| 0x00 | 1,306 (rooms `m*`, `gui*`, stunt rooms) | other / area geometry |
| 0x01 | 561 (`v_*`, `fx_*`, `w_laserfire*`) | effect |
| 0x02 | 23 | tile |
| 0x04 | 679 (`n_*`, `c_*`, `p_*`, `s_*`, heads, bodies) | character |
| 0x08 | 56 (`dor_*`) | door |
| 0x10 | 23 (`w_*sbr*`) | lightsaber |
| 0x20 | 421 (`plc_*`, weapons, items) | placeable |
| 0x40 | 3 | flyer |

The bounding box and radius are coarse; renderers should compute their own from the meshes.

## Name table

`count` u32 offsets, each to a NUL-terminated name. Node headers and animation nodes refer to names
by **index** into this table. The table can hold more names than the tree has nodes (162 models):
the extras are walkmesh helper nodes of the authoring scene (`DOR_LDA01_DWK`,
`md_DWK_wg_closed`, ...) that the compiler moved to the DWK/PWK files. Indices are unique per
node.

## Node header (80 bytes)

| Off | Type | Meaning |
|---|---|---|
| 0 | u16 | node type flags (below) |
| 2 | u16 | part number (see [Supermodels](#supermodels-and-part-numbers)) |
| 4 | u16 | name index |
| 6 | u16 | 0 |
| 8 | u32 | geometry pointer, always 0 |
| 12 | u32 | offset of the parent node (0 for the root; confirmed consistent with the tree) |
| 16 | f32[3] | position (local, relative to the parent) |
| 28 | f32[4] | orientation quaternion **w, x, y, z** |
| 44 | array | children: `u32` node offsets |
| 56 | array | controller keys (16 bytes each) |
| 68 | array | controller data (`f32`) |

The position and orientation repeat the node's geometry controllers (equal in every file; the
controller stores the quaternion as x, y, z, w). After the header come the sub-headers its flags
call for, in this order, each immediately after the previous:

| Flag | Name | Sub-header | Size |
|---|---|---|---|
| 0x0001 | header | (every node) | 80 |
| 0x0002 | light | [Light](#light-92-bytes) | 92 |
| 0x0004 | emitter | [Emitter](#emitter-224-bytes) | 224 |
| 0x0008 | camera | none (no node uses it) | 0 |
| 0x0010 | reference | [Reference](#reference-36-bytes) | 36 |
| 0x0020 | mesh | [Mesh](#mesh-header-332-bytes) | 332 |
| 0x0040 | skin | [Skin](#skin-100-bytes) (after the mesh header) | 100 |
| 0x0080 | anim mesh | none (no node uses it) | |
| 0x0100 | dangly | [Dangly](#dangly-28-bytes) (after the mesh header) | 28 |
| 0x0200 | AABB | [AABB](#aabb-4-bytes--tree) (after the mesh header) | 4 |
| 0x0800 | saber | [Saber](#saber-20-bytes) (after the mesh header) | 20 |

Combinations in the data (geometry nodes): dummy `0x001` 22,457; light `0x003` 5,599; emitter
`0x005` 9,442; reference `0x011` 2,012; trimesh `0x021` 73,577; skin `0x061` 1,033; dangly `0x121`
2,641; AABB `0x221` 1,102; saber `0x821` 68. No other value occurs. Animation nodes are always
`0x001` (dummy) whatever the node they drive.

**Tree order.** Children are stored in order. The *depth-first, parent-first walk* of the tree
(root, then each child's subtree in array order) defines each node's **tree index**, which skin
data uses (see [Skin](#skin-100-bytes)). It equals the name index in all but 196 models.

## Controllers

A node's animatable properties are controllers: a key array (16 bytes per controller) plus one
`f32` data array shared by the node's controllers.

| Off | Type | Meaning |
|---|---|---|
| 0 | u32 | controller id (table below; the meaning depends on the node type) |
| 4 | u16 | in animations: **16** for position, **28** for orientation (the node-header offset of the field it drives); 0xFFFF otherwise |
| 6 | u16 | row (key) count |
| 8 | u16 | index of the first time key in the node's data array |
| 10 | u16 | index of the first value in the data array |
| 12 | u8 | columns: low 4 bits = values per key; **0x10 = bezier**; orientation with **2** = compressed |
| 13 | u8[3] | garbage |

Data: the `rows` times are consecutive floats from the time index; the values are consecutive from
the value index, `rows × per_row` floats, where `per_row` is the column count, **3 × the column
count for bezier keys** (value, in-tangent, out-tangent), or **1 for a compressed orientation**.
In every node the controllers' time and value ranges tile the data array exactly, in controller
order, times before values (confirmed, 330,608 nodes).

* **Geometry controllers** (on the model's own nodes) always have one row at time 0: they are
  the node's static values.
* **Animation controllers** have 1..n rows; times are non-decreasing and lie in
  [0, animation length] (confirmed for all 312,930 animation controllers).
* **Orientation** (id 20) values are quaternions **x, y, z, w** (4 columns). In animations,
  104,083 of 205,838 orientation controllers are **compressed**: one `u32` per key (the value
  float's bits):

  ```
  x = (v & 0x7FF) / 1023 - 1           11 bits
  y = ((v >> 11) & 0x7FF) / 1023 - 1   11 bits
  z = (v >> 22) / 511 - 1              10 bits
  w = sqrt(1 - (x²+y²+z²)) if that sum < 1, else 0 (and normalize x,y,z)
  ```

  Confirmed by rendering `c_rancor` walk and pause frames (all compressed): natural poses.
* **Bezier** keys (2,351 controllers: position, colorStart/Mid/End, selfillumcolor) store
  `[value(n), in(n), out(n)]` per row; in every key seen `in = −out`. Inferred: a cubic segment
  from key k to k+1 with control points `v_k + out_k·Δt/3` and `v_{k+1} + in_{k+1}·Δt/3`. Most
  bezier keys are zeros or constants; treating them as linear on the value columns is a safe
  first implementation (our decision).

### Controller ids

Ids are byte offsets of the property in the engine's node class, so the same id means different
things on different node types. Names are the ASCII-model keywords. Ids confirmed from the
engine's ASCII model parser (RE: `FUN_004658b0` emitter, `FUN_00469150` light, `FUN_00469700`
mesh) and by column counts in the data.

| Node | Id | Name | Cols |
|---|---|---|---|
| all | 8 | position | 3 |
| all | 20 | orientation | 4 or compressed |
| all | 36 | scale (uniform) | 1 |
| mesh | 100 | selfillumcolor | 3 |
| mesh | 132 | alpha | 1 |
| light | 76 | color | 3 |
| light | 88 | radius | 1 |
| light | 96 | shadowradius | 1 |
| light | 100 | verticaldisplacement | 1 |
| light | 140 | multiplier | 1 |

Emitter (each column count 1 except colors, 3):

| Id | Name | Id | Name | Id | Name |
|---|---|---|---|---|---|
| 80 | alphaEnd | 136 | particleRot | 196 | lightningSubDiv |
| 84 | alphaStart | 140 | randvel | 200 | lightningZigzag |
| 88 | birthrate | 144 | sizeStart | 216 | alphaMid |
| 92 | bounce_co | 148 | sizeEnd | 220 | percentStart |
| 96 | combinetime | 152 | sizeStart_y | 224 | percentMid |
| 100 | drag | 156 | sizeEnd_y | 228 | percentEnd |
| 104 | fps | 160 | spread | 232 | sizeMid |
| 108 | frameEnd | 164 | threshold | 236 | sizeMid_y |
| 112 | frameStart | 168 | velocity | 240 | m_fRandomBirthRate |
| 116 | grav | 172 | xsize | 252 | targetsize |
| 120 | lifeExp | 176 | ysize | 256 | numcontrolpts |
| 124 | mass | 180 | blurlength | 260 | controlptradius |
| 128 | p2p_bezier2 | 184 | lightningDelay | 264 | controlptdelay |
| 132 | p2p_bezier3 | 188 | lightningRadius | 268 | tangentspread |
| | | 192 | lightningScale | 272 | tangentlength |
| 284 | colorMid (3) | 380 | colorEnd (3) | 392 | colorStart (3) |
| 502 | detonate | | | | |

What actually occurs: trimesh, dangly, skin, saber and AABB nodes carry position, orientation and
(on 84k meshes) scale, selfillumcolor, alpha; dummies and references position and orientation;
lights add radius, color, multiplier; every emitter carries 39 controllers (fps, birthrate,
velocity, randvel, mass, particleRot, spread, lifeExp, xsize, ysize, colorStart/End, alphaStart/End,
sizeStart/End and _y, frameStart/End, bounce_co, lightning*, combinetime, p2p_bezier2/3, drag,
grav, threshold, blurlength) and about half add the Mid/percent/control-point set. Animations
animate position, orientation, scale, alpha, selfillumcolor, birthrate, m_fRandomBirthRate,
alpha*/size*/color*, lifeExp, velocity, mass, light color and radius. Six animation controllers
(alpha on a dummy, e.g. `dor_lts07` `trans`) target a node type without that property;
inferred: alpha on a dummy fades its subtree.

## Mesh header (332 bytes)

Follows the node header on every node with flag 0x20. Offsets relative to the mesh header.

| Off | Type | Meaning |
|---|---|---|
| 0 | u32 | function pointer: `0x405750` trimesh/AABB/saber, `0x405710` skin, `0x405740` dangly |
| 4 | u32 | function pointer: `0x405760`, `0x405720` skin, `0x405730` dangly |
| 8 | array | faces (32 bytes each) |
| 20 | f32[3] | bounding box min: extent of the vertices **and the node origin** (78,231 of 78,338) |
| 32 | f32[3] | bounding box max |
| 44 | f32 | radius: max distance from the average point (confirmed 78,267) |
| 48 | f32[3] | average point (vertex mean in 32,705 meshes, else a compiler variant; unused) |
| 60 | f32[3] | diffuse colour (1,1,1 in 57,330 meshes; 0.8 grey default) |
| 72 | f32[3] | ambient colour (1,1,1 or 0 mostly) |
| 84 | u32 | transparency hint: 0 (77,741), 1, 2, 3, 4, 5, 7, 8, 13 |
| 88 | char[32] | texture 0: diffuse texture resref, or empty / `NULL` |
| 120 | char[32] | texture 1: lightmap resref (set exactly when lightmapped) |
| 152 | char[12] | texture 2: empty in every file |
| 164 | char[12] | texture 3: empty in every file |
| 176 | array | index counts: one `u32` = faces × 3 (count 1; 0 on saber meshes) |
| 188 | array | index offsets: one `u32` model offset of the `u16` index list (count 1) |
| 200 | array | "inverted counter": one `u32` per mesh (e.g. 92, 97 in `plc_chair1`); inferred a compiler sequence number, unused |
| 212 | i32[3] | −1, −1, 0 (15 meshes hold garbage in the first) |
| 224 | u8[8] | `03 00 00 00 00 00 00 00` (garbage on saber meshes) |
| 232 | u32 | animate UV: 1 on 214 meshes |
| 236 | f32[2] | UV scroll direction x, y |
| 244 | f32 | UV jitter |
| 248 | f32 | UV jitter speed |
| 252 | u32 | MDX row size in bytes (stride); 0 or 0xFFFFFFFF when there is no MDX data |
| 256 | u32 | MDX attribute flags (below) |
| 260 | i32[11] | MDX byte offset of each attribute within a row, −1 when absent: position, normal, colour, uv0, uv1, uv2, uv3, tangent space 0..3 |
| 304 | u16 | vertex count |
| 306 | u16 | texture count (not reliable: use the names) |
| 308 | u8 | lightmapped |
| 309 | u8 | rotate texture (0 everywhere) |
| 310 | u8 | background geometry (0 everywhere) |
| 311 | u8 | shadow: casts a shadow |
| 312 | u8 | beaming (0 everywhere) |
| 313 | u8 | render: draw this mesh (0 on 19,127 meshes, mostly untextured helpers; 8,335 of those still cast a shadow) |
| 314 | u8 | garbage |
| 315 | u8 | garbage |
| 316 | f32 | total face area (equal to the sum of face areas for trimesh and AABB; 0 for skin and dangly) |
| 320 | u32 | 0 |
| 324 | u32 | MDX offset of this mesh's first row |
| 328 | u32 | model offset of the vertex positions (`f32[3]` × count, a copy of the MDX positions; confirmed equal) |

### MDX attribute flags and rows

| Bit | Attribute | Floats | Slot in the offsets |
|---|---|---|---|
| 0x001 | position | 3 | 0 |
| 0x002 | uv0 (diffuse) | 2 | 3 |
| 0x004 | uv1 (lightmap) | 2 | 4 |
| 0x008 | uv2 | 2 | 5 (never set) |
| 0x010 | uv3 | 2 | 6 (never set) |
| 0x020 | normal | 3 | 1 |
| 0x040 | colour | 3 | 2 (never set) |
| 0x080 | tangent space 0 | 9 | 7 |
| 0x100..0x400 | tangent space 1..3 | 9 | 8..10 (never set) |

A bit is set exactly when its offset is not −1, and the stride is the sum of the attribute sizes
plus 32 bytes for skin weights and bone indices (confirmed). Layouts in the data:

| Flags | Stride | Row | Meshes |
|---|---|---|---|
| 0x27 | 40 | pos, normal, uv0, uv1 | 37,012 (lightmapped room geometry) |
| 0x23 | 32 | pos, normal, uv0 | 21,049 |
| 0x21 | 24 | pos, normal | 14,392 (untextured, mostly `render` 0) |
| 0xA7 | 76 | pos, normal, uv0, uv1, tangent | 4,529 |
| 0x23 + skin | 64 | pos, normal, uv0, weights @32, bones @48 | 957 |
| 0xA3 | 68 | pos, normal, uv0, tangent | 286 |
| 0xA3 + skin | 100 | ... tangent @32, weights @68, bones @84 | 76 |
| 0xA1 | 60 | pos, normal, tangent | 23 |
| 0x25 | 32 | pos, normal, uv1 | 14 |
| 0 | 0 / 0xFFFFFFFF | none | 83 (68 saber, 15 empty) |

Tangent space (9 floats): three unit vectors. The third is the vertex normal; the first follows
+∂P/∂v (−∂P/∂v on mirrored UV islands) and the second −∂P/∂u (measured on 5 bump-mapped models).
Inferred: bitangent, tangent, normal for the `bumpmaptexture` TXI path.

**MDX packing quirk.** After each mesh's rows comes one **sentinel row** (position 1e7,1e7,1e7 for
plain meshes, 1e6 for skins, everything else 0, skin weight 1 on bone 0), then `p % 16` zero bytes
where `p` is the offset after the sentinel (the compiler meant to pad to 16 and got the
arithmetic wrong). The last mesh has no padding. Always use offset 324; never assume packing.

### UVs

`uv0` addresses texture 0, `uv1` the lightmap. **v selects texel rows in storage order**: row
`floor(v × height)` counted from the first row stored in the file, for TPC and TGA alike (i.e.
upload rows as stored and sample with (u, v) unchanged). Confirmed by renders: a head
(`pmhc01`) maps correctly, and lightmaps are smooth with v as-is and garbage with 1 − v
(`out/mdl/lm_compare.png`). UVs wrap: 44,864 meshes have uv0 outside [0,1].

### Faces (32 bytes)

| Off | Type | Meaning |
|---|---|---|
| 0 | f32[3] | plane normal (unit) |
| 12 | f32 | plane distance: `n · p + d = 0` for points on the face |
| 16 | u32 | surface material (`surfacemat.2da` row; meaningful on AABB meshes, see bwm.md) |
| 20 | i16[3] | adjacent face per edge, −1 none |
| 26 | u16[3] | vertex indices |

The index list (offset 188) repeats the faces' vertex indices in order (confirmed). Quirks: 7,127
faces are degenerate (zero area); 7,069 have a plane distance computed at another corner than v0;
treat stored normals/distances as hints and recompute if needed. Saber meshes keep 12 placeholder
faces with zero normals and junk adjacency.

## Skin (100 bytes)

After the mesh header on flag 0x40 nodes (1,033 meshes).

| Off | Type | Meaning |
|---|---|---|
| 0 | array | compile-time weights, always 0,0,0 |
| 12 | i32 | MDX offset (within a row) of 4 bone weights `f32[4]` |
| 16 | i32 | MDX offset of 4 bone indices `f32[4]` |
| 20 | u32 | model offset of the **bone map**: `f32` per node, in **tree order** |
| 24 | u32 | bone map length = the model's node count |
| 28 | array | **qbones**: `f32[4]` w,x,y,z per node, tree order |
| 40 | array | **tbones**: `f32[3]` per node, tree order |
| 52 | array | `u32` per node, tree order (bone constants; unused) |
| 64 | i16[16] | tree index of bone slots 0..15 (−1/garbage past the last slot) |
| 96 | u16[2] | garbage |

* The bone map gives, for the node at tree index i, its **bone slot** (or −1). Used slots are
  0..k−1, contiguous (confirmed). k is at most 17, but 22 meshes have more than 16 slots, so the
  16-entry table at 64 is incomplete; invert the bone map instead.
* Each MDX row holds 4 weights and 4 bone values; a bone value is a slot number stored as a float,
  −1.0 for an unused influence (its weight is 0). Weights sum to 1 (confirmed).
* `qbones[i]`, `tbones[i]` are the bind inverse of the bone at tree index i *relative to the skin
  mesh*: with `Rel_i = Mesh_bind⁻¹ · Bone_i_bind`, the transform `x ↦ R(qbone)x + tbone` equals
  `Rel_i⁻¹` (confirmed for every bone of all 1,033 skins when indexed by tree order; indexing by
  name index fails for the 19 models where the orders differ, e.g. Bastila's legs).
* Skinning, in model space: `p' = Σ_k w_k · Bone_{slot_k}(now) · InvBind_{slot_k} · p`, where
  `p` is the MDX position (mesh-local) and `InvBind = (qbone, tbone)` of that slot's node. Normals
  likewise without translation. Confirmed by rendering `p_bastilabb` in bind, `pause1` and `run`
  poses (`out/mdl/bastila_skinned.png`).

## Dangly (28 bytes)

After the mesh header on flag 0x100 nodes (2,641 meshes: cloaks, hair, plants).

| Off | Type | Meaning |
|---|---|---|
| 0 | array | constraints: `f32` per vertex, 0..255 (count = vertex count, confirmed) |
| 12 | f32 | displacement (0.1 in 2,444 meshes) |
| 16 | f32 | tightness (0.5 typical) |
| 20 | f32 | period (0.3 typical) |
| 24 | u32 | model offset of a copy of the vertex positions (equal to the mesh's, confirmed) |

Inferred: a vertex with constraint 0 is pinned, 255 swings freely up to `displacement`, driven by a
spring of the given tightness and period.

## AABB (4 bytes + tree)

After the mesh header on flag 0x200 nodes: `u32` model offset of the root tree node. Tree nodes,
40 bytes:

| Off | Type | Meaning |
|---|---|---|
| 0 | f32[3] | box min |
| 12 | f32[3] | box max |
| 24 | u32 | model offset of the left child, 0 for a leaf |
| 28 | u32 | model offset of the right child |
| 32 | i32 | face index for a leaf, −1 for an internal node |
| 36 | u32 | split plane: 1 +X, 2 +Y, 4 +Z, 8 −X, 16 −Y, 32 −Z on internal nodes, 0 on leaves |

Internal nodes always have two children; each face is a leaf exactly once (all but `m02af_01a`
`_walk14`, 110 leaves for 140 faces); 77 leaf boxes do not contain their face. The AABB mesh of a
room is its walkmesh (same faces as the room's WOK, with `surfacemat.2da` materials). AABB meshes
have no diffuse texture (`NULL`); 821 of 1,102 are `render` 0, and we skip all of them when
drawing (our decision; the `m01aa` render has no holes). Collision should use the WOK
([bwm.md](bwm.md)).

## Light (92 bytes)

| Off | Type | Meaning |
|---|---|---|
| 0 | f32 | flare radius (0 in 5,538) |
| 4 | array | unknown, always empty |
| 16 | array | flare sizes `f32` |
| 28 | array | flare positions `f32` (along the light-to-camera line, inferred) |
| 40 | array | flare colour shifts `f32[3]` |
| 52 | array | flare texture names: `u32` offsets to NUL-terminated strings |
| 64 | u32 | light priority 1..5 |
| 68 | u32 | ambient only |
| 72 | u32 | dynamic type (`nDynamicType`): 0, 1, 2 |
| 76 | u32 | affect dynamic objects |
| 80 | u32 | shadow |
| 84 | u32 | generate flare: 0 in every file, although 61 lights have flare data |
| 88 | u32 | fading light |

The four flare arrays always have equal lengths (1, 2, 4 or 6 in 61 lights). Colour, radius and
multiplier come from controllers. Inferred: rooms are lit by their lightmaps; their light nodes
light dynamic objects (creatures, placeables), choosing by priority.

## Emitter (224 bytes)

| Off | Type | Meaning | Values seen |
|---|---|---|---|
| 0 | f32 | dead space | 0 mostly |
| 4 | f32 | blast radius | |
| 8 | f32 | blast length | |
| 12 | u32 | branch count (lightning) | 0..5 |
| 16 | u32 | control point smoothing: a flag, 0 or 1 in the data (the original tests the dword, `0x00498b80`; read as a float it is a denormal) | 0 |
| 20 | u32 | x grid (texture frames across) | 0, 1, 2, 4, 5, 8, 16 |
| 24 | u32 | y grid (frames down) | |
| 28 | u32 | spawn type | 0, 1 |
| 32 | char[32] | update | `Single` 6,539, `Fountain` 2,171, `Explosion` 655, `Lightning` 77 |
| 64 | char[32] | render | `Billboard_to_Local_Z` 5,099, `Normal` 3,227, `Billboard_to_World_Z` 459, `Motion_Blur` 440, `Linked` 144, `Aligned_to_Particle_Dir` 50, `Aligned_to_World_Z` 23 |
| 96 | char[32] | blend | `Normal` 7,934, `Lighten` 1,485, `Punch-Through` 19, `PunchThrough` 4 |
| 128 | char[32] | texture | 103 different |
| 160 | char[16] | chunk model (spawned instead of quads) | empty in 9,191 |
| 176 | u32 | two-sided texture | |
| 180 | u32 | loop | |
| 184 | u16 | render order | 0..8 |
| 186 | u8 | frame blending | 0 |
| 187 | char[32] | depth texture name | `NULL`/empty, once `fx_depth` |
| 219 | u8 | garbage | |
| 220 | u32 | flags (below) | |

Flags (RE: the ASCII parser's setters at `0x0048d790`..`0x0048d850`): 0x1 `p2p`, 0x2 `p2p_sel`,
0x4 `affectedByWind`, 0x8 `m_isTinted`, 0x10 `bounce`, 0x20 `random` (bit 0), 0x40 `inherit`,
0x80 `inheritvel`, 0x100 `inherit_local`, 0x200 `splat`, 0x400 `inherit_part`, 0x800
`depth_texture`, 0x1000 `random` (bit 1). The particle simulation that uses these is in
[re/particles.md](../re/particles.md); in short: birthrate is not simply particles per second (a
Fountain emits in bursts once 1/birthrate s have passed, so the real rate depends on frame time;
spawn type 1 emits per metre moved, and nothing is emitted while birthrate < 1), lifeExp is
seconds, velocity ± randvel along the node's +Z tilted by up to spread/2 (`spread` is the full cone
angle), colours/alphas/sizes interpolated start→mid→end at
percentStart/Mid/End of life, xgrid × ygrid flipbook from frameStart to frameEnd at fps; `Lighten`
= additive).

## Reference (36 bytes)

| Off | Type | Meaning |
|---|---|---|
| 0 | char[32] | model resref to instance at this node (42 different: shrubs, `fx_ref`, crowds) |
| 32 | u32 | reattachable (1 in 65) |

All 2,012 referenced models exist.

## Saber (20 bytes)

On lightsaber blades (68 meshes, classification 0x10 models). The mesh has 176 vertices, no MDX
data, placeholder faces; the blade geometry is in three model-offset arrays of 176 entries.

| Off | Type | Meaning |
|---|---|---|
| 0 | u32 | offset of `f32[3]` positions (equal to the mesh's MDL positions) |
| 4 | u32 | offset of `f32[2]` UVs |
| 8 | u32 | offset of `f32[3]` normals |
| 12 | u32 | unknown counter (86..98) |
| 16 | u32 | unknown counter |

Vertex layout (observed in every saber): 44 groups of 4 vertices; each group is 4 points along
the blade (z ≈ −0.04, 0.005, 0.93, 0.98: base cap, base, tip, tip cap). Group 0 lies on the blade
axis (u = 0.5), group 1 on one edge (x ≈ +0.1, u = 1), groups 2..21 repeat group 0; group 22 the
axis again, group 23 the other edge (x ≈ −0.1, u = 0), groups 24..43 repeat the axis. The blade
is the strip across groups 23, 22, 0, 1 (edge, axis, axis, edge), 3 quads along each half: 12
triangles, the count of the mesh's placeholder faces (confirmed by render:
`kotor/out/mdlview/w_lghtsbr_001_side_powered0.png`). Each saber model has two saber meshes at
right angles (`plane242`, `plane239`). Inferred: the repeated groups are for the swing trail.
Blade length is the saber nodes' `scale` controller: 0 in the geometry (the blade is off), keyed
0→1 over `powerup` (0.8 s), 1→0 over `powerdown`, 1 in `powered`. Each saber model also has two
ordinary trimesh planes (34 vertices) crossing the blade at ±45° that draw the glow; the texture
is additive (`w_lsabre*01`).

## Animations

The model header's animation array points at animation headers (136 bytes):

| Off | Type | Meaning |
|---|---|---|
| 0 | geometry header | name = animation name, type 5, root = animation node tree |
| 80 | f32 | length in seconds |
| 84 | f32 | transition time (blend-in), seconds: 0.25 (3,643), 0 (2,812), 0.05..5 |
| 88 | char[32] | animation root: the model name (7,077) or a node (`torso_g`, `torsoupr_g`, `talkdummy`, `neck`, ...) |
| 120 | array | events, 36 bytes each: `f32` time, `char[32]` name |
| 132 | u32 | 0 |

The animation's node tree mirrors (a subset of) the model's: every animation node is a dummy
(flags 0x001) whose **name index** is that of the model node it drives (and its part number is
that node's part number in 99.8% of nodes); 20 nodes name walkmesh helpers that are not in the
geometry. Only controllers matter. Interpret a controller id with the **flags of the model node
of the same name** (an emitter's 88 is birthrate, a light's 88 is radius).

Applying a keyed animation at time t (confirmed by renders of doors, Bastila and the rancor):

* **orientation keys replace** the node's orientation;
* **position keys are offsets added to the node's geometry position**: `p = p_geometry + key`.
  Door panels key 0 → −1.18 along X, facial bones key ~0, `rootdummy` keys around 0 (not around
  its 1.06 m height). 494 animated models follow this; 59 look absolute (first key equals the
  geometry position): all of them are unused test models (`c_bmspecdiff`, `c_female`, `p_juhani`,
  `n_gammorean`, `h_m_hi01`...) or minigame/GUI props whose single key equals the geometry
  position, so the offset rule is the one to implement (our decision). Inferred: the model's
  animation scale multiplies the keyed offsets;
* other controllers replace the property.

Events (3,884): `snd_footstep` 1,228, `detonate` 1,050, `swingshort`, `hit`, `contact`,
`swinglong`, `hitparry`, `clash`, `snd_hitground`, `swingtwirl`, `draw_weapon`, `door`,
`hitdamage`, `cast`, `fire0`, and door-specific sound names (`manaandoor01_16`, `omenevent01`).
All event times lie within the animation length.

Animation names are listed in [models-usage.md](models-usage.md#animation-names).

## Supermodels and part numbers

A model names a **supermodel** (413 do); the chain continues (`pfbcm` → `S_Female03` →
`S_Female02` → `S_Female01` → `S_Male02` → `S_Male01`). An animation is looked up by name in the
model, then its supermodel, and so on; it drives nodes by name (confirmed by rendering
`p_bastilabb` with `S_Female03`'s `run`). All resolve except `cspar2` (from the unused `h_m_hi01`) and
`s_male02h` (from `n_djedi_h` and `p_carthbbh`).

Part numbers (node header +2): the compiler gives a node the part number of the same-named node in
the supermodel, and new nodes numbers after the supermodel's highest; the root keeps 0. Without a
supermodel the part number equals the name index (2,668 models). Inferred: the engine uses part
numbers to map supermodel animation nodes quickly; matching by name gives the same result.

## Drawing a model (summary)

1. Walk the tree. A node's model-space transform is `parent · T(position) · R(orientation)`,
   orientation from the header (w, x, y, z), or from the current animation (keys x, y, z, w;
   positions as offsets). Apply `scale` controllers if present.
2. For each mesh with `render` 1 and not AABB/saber: positions/normals/UVs from its MDX rows,
   triangles from the face vertex indices. Skin meshes: skin on the GPU with the bone map,
   qbones and tbones (tree-order indexing).
3. Material: texture 0 with uv0 (resolve the resref as TPC, then TGA), modulated by the lightmap
   (texture 1 with uv1) when `lightmapped`; texture properties (blending, envmap, bump) come from
   the texture's TXI ([txi-render.md](txi-render.md)). `alpha` and `selfillumcolor` controllers
   give opacity and an emissive term. Diffuse/ambient colours are 1 or defaults in nearly all
   meshes (inferred: material colours for dynamic lighting).
4. Transparency hint ≠ 0 (680 meshes, values 1..13; inferred: sort transparent meshes after
   opaque ones). Animate-UV meshes scroll uv0 by `direction × time` with jitter (inferred).
5. Emitters, lights, references and sabers as above.

## Checked

Probe: `kotor/tools/py/mdlprobe.py` (parser `kotor/tools/py/kmdl.py`):

```
python kotor/tools/py/mdlprobe.py --out kotor/out/mdlprobe.txt     # about 7 minutes
```

It parses **all 3,072 MDL entries** (2,832 distinct resrefs; BIFs, `rims/*`, `patch.erf`) with
their MDX: 117,931 geometry nodes, 7,143 animations (232,309 animation nodes), 1,151,264
controllers, 5.77 million faces. Checks: every byte of every MDL claimed exactly once; MDX blocks
in place with their sentinel and padding; header copies agree; tree and parent pointers; node
flags; controller ranges tile each node's data; key times ordered and within the animation;
quaternions unit; mesh flag/offset/stride consistency; MDX positions equal MDL positions; index
list equals faces; face normals against winding; bounding boxes, radius, area; skin weights and
bone indices, inverse binds (tree order); dangly counts; AABB coverage and nesting; light flare
arrays; references resolve; events within length; animation nodes name model nodes.

Result: **0 parse failures**. Remaining failure classes are data quirks, all described above:
7,069 faces with a stale plane distance, 77 AABB meshes with leaf boxes that miss their face (by
more than 1 mm), 1 AABB tree that omits 30 faces (`m02af_01a`), 6 animation controllers aimed at
a node type without that property.

The game's own parser, `lib/mdl` (`tools/mdlcheck`, 7 s for the whole corpus with `--extract`, or
the 2,832 models lib/res finds), reproduces every total and failure class above, and
`tools/animcheck` plays every animation of every model's chain; see
[../design/models.md](../design/models.md).

Renders (`kotor/tools/py/mdlrender.py`, a numpy rasterizer; PNGs in `kotor/out/mdl/`, looked at):
`pmhc01` head front/side (UV orientation, facing +Y), `c_rancor` bind/walk/pause (compressed
quaternions), `m01aa_02a` room and the whole `m01aa` area from its LYT (lightmaps, culling),
`lm_compare.png` (lightmap v orientation), `p_bastilabb` + `p_bastilah` at the headhook in bind,
`pause1` and `run` (skinning, supermodel animations, position offsets), `dor_lda03` closed /
opening / open (door animations), `w_lghtsbr_001`.
