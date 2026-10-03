# Models and walkmeshes on the CPU

How the game holds models (MDL/MDX) and walkmeshes (WOK/PWK/DWK) once they are read, who owns
what, and how the renderer and the engine use them. The file formats are in
[../formats/mdl.md](../formats/mdl.md), [../formats/models-usage.md](../formats/models-usage.md)
and [../formats/bwm.md](../formats/bwm.md).

| Directory | Namespace | What |
|---|---|---|
| `lib/mdl/mdl.ctx` | `mdl` | MDL/MDX parsed into a `mdl::Model` |
| `lib/mdl/anim.ctx` | `mdl_anim` | animation: supermodel lookup, poses, blending, events, skin palettes, hooks |
| `lib/walk/bwm.ctx` | `bwm` | walkmeshes and their queries |
| `tools/mdlcheck`, `tools/animcheck`, `tools/walkcheck` | | corpus checks over the whole install |

Conventions are lib/base's `math`: Z up, creatures face +Y, metres; `math::Vec3`, `math::Quat`
(unit, `w` first), `math::Mat4` column-major (`m[col * 4 + row]`), points as columns, so
`mat4::mul{ a, b }` applies `b` first. Front faces wind counter-clockwise.

## Loading a model

```
let mdl_bytes = try res::load{ &fs, rm, name, kind = restype::Type::mdl, realloc, &heap } ifnull { ... }
let mdx_bytes = try res::load{ &fs, rm, name, kind = restype::Type::mdx, realloc, &heap } ifnull { empty }
let model = try mdl::parse{ realloc, &heap, mdl = mdl_bytes, mdx = mdx_bytes }
```

`parse` never trusts the file: a structure out of range or impossible (a node reached twice, a
face corner past the vertices, a skin weight on a slot the bone map lacks) is
`mdl::malformed{ what, at }`; running out of memory is `alloc::out_of_memory`. Data that merely
disagrees with itself (a stale copy, a parent pointer) parses; `mdl::parse_traced` reports it,
with the byte range every structure claims, for `tools/mdlcheck`.

**Ownership.** Everything a `Model` holds comes from the allocator passed to `parse` and is never
freed piece by piece: give each model an arena (or a region of one) that lives as long as the
model. The model holds no pointer into the file buffers, so those can be dropped (or allocated
from a scratch arena that is reset) once it is parsed. `tools/animcheck` keeps supermodels in a
long-lived arena and each model it checks in a scratch arena reset per model.

## The model

```
Model
  name, supermodel (resref, empty for none), classification (CLASS_*), anim_scale, ...
  names      [][]u8        the name table (node and animation-node names index it)
  nodes      []Node        depth-first, parent before children: the "tree index"
  meshes     []Mesh        every node with a mesh, in tree order
  lights     []Light
  emitters   []Emitter
  references []Reference
  animations []Animation   the model's own (supermodels hold the rest)
```

A `Node` has its name, flags (`NODE_*`), `parent` (tree index, −1 for the root), `children`
(tree indices in the file's order), its local `position`/`orientation`/`scale`, `alpha` and
`self_illum`, the geometry controllers they came from, and `mesh`, `light`, `emitter`,
`reference` indices into the model's arrays (null when it has none). Each `Mesh`, `Light`,
`Emitter` and `Reference` has `node`, the tree index back. Tree order is what skins index and
what poses are laid out in, and since a parent always comes first, transforms take one forward
pass.

### Meshes: what a renderer uploads

One contiguous array per vertex attribute, `vertex_count` entries each, all `f32`, or empty when
the mesh lacks it:

| Field | Floats per vertex | Notes |
|---|---|---|
| `positions` | 3 | in the node's space |
| `normals` | 3 | |
| `uv0` | 2 | texture 0; v counts texel rows from the first row stored (upload rows as stored, sample (u, v) as is) |
| `uv1` | 2 | the lightmap, texture 1 |
| `uv2`, `uv3`, `colors` | 2, 2, 3 | never present in KOTOR's data |
| `tangents` | 9 | tangent space: three unit vectors, the third the normal (mdl.md, MDX) |
| `skin.weights` | 4 | |
| `skin.bones` | 4 (`u8`) | palette slots; 0 where the weight is 0 |

`indices` is `u16`, three per triangle, counter-clockwise; `faces` keeps each face's plane,
surface material and adjacency for code that wants them (AABB meshes). The arrays can go to the
GPU as they are, as separate streams or interleaved by the backend.

Material data on the mesh: `textures[0]` (diffuse) and `textures[1]` (lightmap, set exactly when
`lightmapped`), empty for none; `diffuse`, `ambient`, `transparency_hint` (non-zero on 680 meshes:
draw after opaque ones, inferred), `render` (draw at all), `shadow` (casts one), `beaming`,
`background`, `rotate_texture`, `animate_uv` with `uv_direction`, `uv_jitter`,
`uv_jitter_speed`. Texture properties (blending, environment and bump maps) come from each
texture's TXI, not the model.

Which meshes to draw: those with `render` set, except AABB meshes (`aabb != null`: the room's
walkmesh copy; our decision, mdl.md) and saber meshes (`saber != null`), whose placeholder faces
aren't geometry: a saber blade is built from `saber.positions`, `uvs`, `normals` (176 vertices,
mdl.md, Saber). `dangly` gives the per-vertex constraints, displacement, tightness and period for
cloth and hair (simulation is the renderer's or engine's; not done here yet).

### Lights, emitters, references

`Light` has the flare data and flags; its animatable values (`color`, `radius`, `multiplier`,
`shadow_radius`, `vertical_displacement`) are in `props`. `Emitter` has the header's settings
(`update`, `render`, `blend` as enums plus their names, `texture`, grid, `chunk`, flags) and every
animatable property in `props: EmitterProps` (birthrate, life_exp, velocity, sizes, colours,
alphas, frames, lightning, ...). `Reference` names a model to instance at its node. Poses carry
animated copies of `props` (below).

## Animation

```
let found = mdl_anim::find{ model = &m, name = "pause1", lookup } ifnull { ... }   // along the supermodel chain
let binding = try mdl_anim::bind{ realloc, &heap, model = &m, animation = found.animation }
let pose = try mdl_anim::make_pose{ realloc, &heap, model = &m }
let mut player = mdl_anim::new_player{}
mdl_anim::play{ &player, binding, looping = true, speed = 1.0, transition = -1.0 }     // -1: the animation's own blend time

each frame:
mdl_anim::advance{ &player, dt, on_event }        // fires the events time passes (footsteps, hits, ...)
mdl_anim::evaluate{ model = &m, player, pose }    // bind pose, outgoing animation, incoming one by blend weight
```

- `lookup: &fn{ name: []u8 } -> ?*mdl::Model` gives a model by resref, loading it if needed. The
  engine passes a bound function over its model cache; supermodels (`S_Female03`, ...) are shared
  by many models and must outlive every binding to their animations.
- `bind` matches animation nodes to the model's nodes by name (case-insensitive) once; when the
  animation's root names a node of the model (`torso_g`), only that subtree is driven. Keep
  bindings per (model, animation) in the engine's cache.
- Keys: orientations replace; positions are offsets added to the node's own position, times the
  driven model's `anim_scale`; other controllers replace their property, read by the driven
  node's kind. Linear interpolation, slerp for orientations; bezier keys use their values only
  (our decision until the curve is proven, mdl.md).
- `apply{ ..., weight }` layers any animation onto a pose for engine-specific mixing; `pose_at`
  samples one animation alone.

### The pose: what a renderer reads

```
Pose
  nodes     []NodeState   local position, orientation, scale, alpha, self_illum, per tree index
  world     []Mat4        model space, per tree index        (after finish / evaluate)
  alpha     []f32         the node's alpha times its ancestors' (a dummy's alpha fades its subtree)
  lights    []LightProps  per Model.lights
  emitters  []EmitterProps per Model.emitters
```

For a placed object with transform `instance` (from the GIT or LYT):

- a mesh draws with `instance * pose.world[mesh.node]`, opacity `pose.alpha[mesh.node]`,
  emissive `pose.nodes[mesh.node].self_illum`;
- a **skinned** mesh draws the same way, with bone matrices from
  `mdl_anim::skin_palette{ model, mesh, pose, out }`: one `Mat4` per slot
  (`skin.bone_nodes.len`, up to 17 in the data), and each vertex
  `sum over its 4 weights of weight * palette[slot] * position` (normals likewise without
  translation). The palette maps bind-pose vertices to posed ones **in the skin node's own
  space**, so skinned and rigid meshes share one transform path; in the bind pose every palette
  matrix is the identity (`animcheck` checks it for every skin).
- lights and emitters use `pose.lights[i]`, `pose.emitters[i]` and their node's `world`.

### Attachments

`mdl_anim::hook_transform{ model, pose, name }` is a hook node's model-space transform:
`HOOK_HEAD` (`headhook`), `HOOK_RIGHT_HAND` (`rhand`), `HOOK_LEFT_HAND` (`lhand`), `HOOK_GOGGLES`
(`gogglehook`). An attached model's root goes there: its nodes draw with
`instance * body_pose.world[hook] * attached_pose.world[node]`. A head is a model of its own,
with its own player and pose, playing its own animations through its own supermodel chain (which
leads to the body's), never the body's (models-usage.md, Heads).

## Checked

- `tools/mdlcheck`: every model through lib/res (2,832) or every copy of every model
  (`--extract`, 3,072, mdl.md's numbers): all parse, every byte of every MDL claimed exactly once,
  MDX blocks tile their files, totals equal to the Python probe's, and only the data quirks mdl.md
  lists fail.
- `tools/animcheck`: every animation each model's chain offers (97,317 model/animation pairs,
  585,479 poses, 1.2 million palettes): finite transforms, unit orientations, identity bind
  palettes, each event once per pass, blends mid-transition. `--dump` prints a pose; it agrees
  with `tools/py/mdlrender.py` to 2e-6 once both slerp (Bastila `run`, rancor `cwalk`, door
  `opening1`).

## Open

- The bezier curve's exact form, the dangly spring, the particle simulation (mdl.md, open).
- Whether the engine scales supermodel position keys by `anim_scale` (models-usage.md).
- `mdlview`: a headless render through lib/render once that API lands.
