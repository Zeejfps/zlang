# Particle emitters in the original (what an MDL emitter node does)

What `swkotor.exe` does with an emitter node, read from the decompiled client code (names are ours;
addresses are of the unpacked image, see [README.md](README.md); rechecked on 2026-10-07 against the
rebuilt decompile; confidence is high unless marked). The node's fields are in
[../formats/mdl.md](../formats/mdl.md); how we use this is in [../design/vfx.md](../design/vfx.md).
The runtime node keeps the MDL emitter header at node `+0x50` (so header +28 spawn type is node
`+0x6c`, +32 update `+0x70`, +64 render `+0x90`, +96 blend `+0xb0`, +180 loop `+0x104`, +220 flags
`+0x12c`).

## The emitter object

- `0x0049d5c0` makes the emitter for a node from its `update` string (exact, case-sensitive match):
  `Fountain` (vtable `0x00743478`), `Explosion` (`0x00743500`, which also registers the animation
  event `Detonate`, whose handler `0x0048d770` sets the latch byte `+0x1f6`), `Single`
  (`0x00743588`); anything else (`Lightning`) is a different class (size `0x290`, `0x0049d1d0`,
  vtable `0x00743610`). The first three share a 0x1f8-byte object and differ only in their
  per-frame update (vtable slot `+0x80`): `0x00496e40`, `0x00497640`, `0x004979c0`.
- Each frame `0x00494da0` saves the previous world position and orientation (`+0x170`, `+0x1b4`),
  fetches the current ones with a virtual call (slot `+0xc`), rebuilds the emitter's world axes
  (X `+0x128`, Y `+0x134`, Z `+0x140`) and calls the slot `+0x80` update with dt.
- `0x0049caa0` (the setup, vtable slot `+0x7c`, called once by the factory as the emitter is made)
  turns the `render` string (exact, case-sensitive) into a code at object `+0x114` and the `blend`
  string (case-insensitive) into one at `+0x4c`:

  | render | code | | blend | code |
  |---|---|---|---|---|
  | Normal | 1 | | Normal | 0 (src alpha, 1 - src alpha) |
  | Billboard_to_Local_Z | 2 | | Punch-Through, PunchThrough | 1 (blending off, alpha test) |
  | Billboard_to_World_Z | 3 | | anything else (Lighten) | 2 (src alpha, one; fog off while drawing) |
  | Linked | 4 | | | |
  | Aligned_to_World_Z | 5 | | | |
  | Aligned_to_Particle_Dir | 8 | | | |
  | Motion_Blur | 9 | | | |

  (The codes are read from the constants `0x00798b6c`..`0x00798b8c`; 6 and 7 are not render
  modes.) A string that matches none leaves the code as it was.
- The emitter's animatable values sit at object offsets **equal to their controller ids**: birthrate
  at `+0x58` (88), bounce_co `+0x5c`, fps `+0x68` (104), frameEnd `+0x6c`, frameStart `+0x70`,
  lifeExp `+0x78` (120), **mass `+0x7c` (124)**, particleRot `+0x88`, randvel `+0x8c`, sizeStart
  `+0x90` (sizeEnd, sizeStart_y, sizeEnd_y follow), spread `+0xa0`, velocity `+0xa8`, xsize/ysize
  `+0xac/+0xb0`, blurlength `+0xb4` (180), percentStart/Mid/End `+0xdc/+0xe0/+0xe4`, sizeMid(_y)
  `+0xe8/+0xec`, m_fRandomBirthRate `+0xf0` (240), colours from `+0x11c` (Mid `+0x11c`, End
  `+0x17c`, Start `+0x188`). So `grav` (116, `+0x74`) is not gravity: it is only read for
  point-to-point emitters (flag `p2p`, the variant without `p2p_sel`, `0x00493ae0`). Gravity is
  `mass`.
- Particles live in **world space**. The emitter's world position is `+0x164`, its world orientation
  quaternion (w, x, y, z) `+0x1a4`; both come from the virtual call each frame.

## A particle

Created by `0x004921d0` (and its constructors `0x00494c40`, 0x74 bytes, and `0x00494cb0`, 0x78
bytes, used when the header's chunk name is set: the particle then carries a model at `+0x74`, and
the emitter is drawn by `0x00490700` instead of quads). It takes dt and a scale: the owner's scale
(owner `+0x1b4`, 1 without an owner) for a new particle; an Explosion passes 1.0 for a particle it
reuses from its free list.

- position `+0x08` = the emitter's world position, plus, when int(xsize * scale * 100) and
  int(ysize * scale * 100) are not both 0, a random offset along the emitter's X and Y axes of up to
  **xsize / 200 and ysize / 200 metres either way** (a rectangle xsize/100 by ysize/100 m centred on
  the emitter, in 0.1 mm steps; `0x0048d870`); the streak tail `+0x60` starts at the same point;
- orientation quaternion `+0x2c` = the emitter's; with `spread` != 0 it is tilted about the emitter's
  X axis by a random angle in **0..spread/2** (0.01 rad steps; so `spread` is the full cone angle)
  and then turned about the emitter's Z axis by a random angle in 0..6.27 (`0x0048de60`); a non-zero
  dead space (header +0) then re-tilts it away from the line to the camera (med: the loop in
  `0x0048de60` was not worked through); **velocity** `+0x54` = (velocity + random) along that
  quaternion's Z axis, the random part a multiple of 0.01 in (-randvel, +randvel), only when
  randvel > 0.01;
- with `inheritvel` (0x80), an inherited speed `+0x18` and direction `+0x1c` from the emitter's
  move and turn over the last frame (`0x0048d9e0`);
- **angle `+0x14` = 0** (not random); each frame the update adds `particleRot * dt`, wrapping once
  by 2 pi when it leaves +-2 pi;
- age `+0x70` = 0, frame `+0x3c` = int(frameStart) (or, with `random` bit 0 (flag 0x20), a random
  cell frameStart + rand % (|int(frameEnd - frameStart)| + 1), `0x0048dcf0`).

Each frame (`0x00492450`, through `0x00494d40` for emitters without `p2p`; p2p emitters use
`0x00492ea0`/`0x00493ae0` instead, and only while they have a target), for each particle not frozen:
first the carrying flags (header +300; read 2026-10-09, high), then position += velocity * dt + the
inherited speed `+0x18` * its direction * dt, then velocity.z -= dt * mass * 9.81, and the inherited
speed is multiplied by (1 - dt). Without a carrying flag a particle stays where it is in the world
whatever its emitter does. The flags:

- `inherit` (0x40): position = R(now) * R(before)^-1 * (position - the emitter's previous world
  position `+0x170`) + its world position now `+0x164` (R the world orientations `+0x1a4` and the
  previous `+0x1b4`), and the velocity turned the same way: rigid with the emitter's move and turn. The
  streak tail `+0x60` and the particle's own orientation are not carried, so a carried Motion_Blur
  particle's tail lags a frame's move behind it.
- `inherit_local` (0x100, only without `inherit`, and only with an owner, emitter `+0x40`, the model's
  object): position and tail += the owner's world position `+0x78` minus the copy kept at emitter
  `+0x158`. The copy (and the owner's orientation, `+0x194`) is taken on the emitter's first step and
  again after every step.
- `inherit_part` (0x400, checked apart from the others): position and tail += the emitter's world
  position now minus `+0x158`, which for this flag is the emitter's own position, taken on its first
  step and after every step: its move without its turn. (No emitter in the data has it with `inherit`
  or `inherit_local`.)
- `inheritvel` (0x80) is not a carry: it is the birth's inherited speed (above).

`0x00494da0` also uses `inherit_local` before the update: the emitter's previous position `+0x170` is then
its last position plus the owner's move, so the owner's move does not count as the emitter's own (for
the per-metre spawn type 1 and `inheritvel`). Nothing else carries a particle: drawing (`0x0049b680`,
`0x0048f040`) takes the stored world positions as they are, and a `Single` emitter's update
(`0x004979c0`) never puts its one particle back on the emitter, so a `Single` sprite born on a moving
node stays where it was born unless a flag carries it. In the data (every model's emitter nodes, `kmdl`
census, 2026-10-09) the room `Single` sprites on nodes that some animation moves all have `inherit`
(Kashyyyk's 445 birds in `m22aa`, `m13aa_01f`'s 36, `m14`, `m23`, `m25`, `m26`, `m41`, `m44`: 1,460
nodes), and every one with `inherit_local` (4,926: the duelling ring's crowd in `m02ae_07a`, 172, and
4,754 in `m31aa/ab/ad_00a`, rooms no module's LYT names) is on a node no animation moves, in a room,
whose owner never moves: they stand still in either reading. The exceptions are `m45ac_bmap`'s 35 capital
ships, `Single` sprites without a flag under a `RotDummy` keyed in the room's `default` animation, which
would stand where they were born if that animation ran.

Then, for every particle not frozen, carried or not:
`affectedByWind` (0x4) adds an offset from the scene's wind query (scene slot `+0xd0`, given the
particle's position and dt), asked for every particle while the emitter has fewer than 50 and for
every sixth otherwise (the others reuse the last answer); `bounce` (0x10) ray-casts the step against
the scene. On a hit (the scene sets the position to the hit point): with bounce_co 0 the particle
stops; otherwise the velocity is reflected about the surface normal, scaled by 0.75, and its z
further by bounce_co * clamp(0.033 / dt, 0.5, 1). A particle whose squared speed is then below 0.5
freezes (`+0x6c`): it stops being stepped, its quaternion is turned to lie along the surface normal
(kept at `+0x48`), and it sits 2 cm off the surface (plus sizeStart for a chunk model). (The
global `0x00798ba0` that selects this rule is 1; its mode 2 is unused.)

## Which emitters run, and when

Read on 2026-10-09 from the decompile (confidence high unless marked). The original has no update pass
for emitters: they are stepped while the scene is drawn, and only those that are drawn.

- **Collection.** `CAurScene::Render` (`0x004512d0`) calls `0x0046e5c0`, which gathers the frame's
  meshes and emitters. With rooms (scene `+0xc8` array, count `+0xcc`), `0x0046d070` lists the rooms
  to look at: the current room (scene `+0xd4`) and the rooms its VIS entry names (room `+0x5c`, count
  `+0x60`), or every room when there is no current room. Each listed room's node tree is walked
  against the camera's frustum (`0x004ad7e0`, planes at camera `+0x1f8`), calling `0x0046d3b0` on
  each node. That callback tests the node's meshes (`+0xc`/`+0x10`, `0x0046a8c0`) and its emitters
  (`+0x24`/`+0x28`) and appends each emitter that passes to a global list (`0x007fbf78`, count
  `0x007fbf7c`); a second emitter list of the node (`+0x8c`, copied by `0x0046d250`) is appended
  without duplicates. Our reading is that the second list holds the emitters of the models placed in
  the node besides the room's own, the placeables', doors' and creatures' (med: the code that fills
  it was not traced).
- **The cull is a point.** `0x0046a730` asks the emitter for its world position (vtable `+0xc`) and
  drops it when the distance outside any frustum plane exceeds emitter `+0xd0`. `+0xd0` is written
  only for point-to-point emitters (the distance to the target, `0x00494da0` and `0x0049b240`), so
  for every other emitter it is 0: an emitter whose origin is off screen is neither stepped nor
  drawn, even when its particles would be in view. (high for the code; med for the frustum's planes
  being the camera's own, unclipped)
- **The pass.** The scene's emitter pass (`0x004509b0`, vtable slot `+0x110`) runs when the globals
  `0x0078e3d8` and `0x0078e614` are set (both 1 in the image; nothing found that clears the first).
  It sorts the list (`0x0044f5a0`: two emitters of the same model by a short at node `+0x108`;
  otherwise Lighten emitters, blend code 2 at `+0x4c`, after the rest; otherwise far to near by the
  distance from the camera to the owning model's position `+0x78`, or the emitter's own `+0x8`
  without an owner), then for each one: steps it (`0x00494da0` with min(frame delta, 0.1 s), see
  [gui3d.md](gui3d.md)) when the scene's byte `+0xda` is set or the owning model's byte `+0x10` is
  (vtable `+0x170`, `0x0043e850`; set by slot `+0xdc`, `0x0043e830`), and draws it (`0x0049b680`).
  `CAurScene::CAurScene` sets `+0xda` to 1 and no direct caller of the clearing slot 25 (`0x0044f3b0`)
  was found, so in practice every emitter that is drawn is stepped (med). An emitter out of sight
  keeps its particles where they were until it is seen again, then goes on by one frame's time.
- **Warm-up.** On the scene's first render (frame counter scene `+0x50` still 0) `0x004511f0` steps
  every emitter of every room (room `+0x58`, emitters `+0x24`/`+0x28`) and of the scene's own list
  (`+0x94`/`+0x98`) 100 times by 0.1 s: the rooms' smoke and mist are 10 s along in the first picture.
  The objects' emitters are not in those lists and start empty.
- **Detonate.** An Explosion emitter registers `Detonate` on its owning model (above); the handler
  (`0x0048d770`) sets the latch `+0x1f6`, which the Explosion update consumes, so a latch set while the
  emitter is not drawn waits for its next step.
- **No option.** Nothing reads an `Emitters` key or switches the pass off from the options
  ([../mechanics/graphics.md](../mechanics/graphics.md)): every emitter of a visible room runs.

What the area data holds (counted over every LYT's rooms): at most 200 emitters an area (`m25ab`;
`m22aa` 186, `m02ae` 172), mostly `Single` sprites (Kashyyyk's birds, 342 in `m22aa`'s rooms, a
crowd of sprites in `m02ae_07a`, waves) and `Fountain` smoke, steam, fire, sparks, ripples, sand
and bubbles; Explosion 34 and Lightning 3 in rooms. Placeables (539 emitters, e.g. `plc_starmap`'s 68
`Single` sprites, `plc_smk01` smoke), doors (`dor_lsi06`'s 20 flares, `dor_lta02` smoke) and a few
creatures (`c_drdastro`, `c_drdwar`, `c_turret01`) have them too.

## The three update types

Fountain and Explosion first age their particles (`0x00494b30`): a particle whose age has reached
`lifeExp` is removed to the free list, the others get age += dt; a negative lifeExp never removes
(drawn at its start size and colour). Then (all three types) the streak tails ease, the angles turn
and the particles are stepped, before any births of the frame.

- **Fountain**: nothing at all while int(birthrate) < 1 (so a birthrate below 1 never emits).
  - spawn type (header +28) 0: a timer `+0xcc` accumulates dt; once it reaches 1/birthrate, the
    rate b = birthrate +- rand % round(m_fRandomBirthRate) (random sign, only when that rounds above
    0; not below 0) gives **int(b * timer) mod (int(b) + 1)** particles at once and the timer is
    reset to 0, dropping the remainder. So the real rate is at most birthrate a second and lower when
    frames are long (at 30 fps: birthrate 20 gives 15/s, 100 gives 90/s).
  - spawn type 1: births are per **metre moved**, not per second: int(birthrate * distance moved
    since the last births) particles, spaced 1/birthrate m apart along the path (when xsize and
    ysize are both 0), the leftover distance carried to the next frame; a still emitter emits
    nothing. m_fRandomBirthRate is not used.
- **Explosion**: nothing until the animation's `Detonate` event; then `int(birthrate)` particles at
  once (none if that is 0), and not again until the event has been off for a frame (`+0xf4`). With a
  non-zero blast radius (header +4) it also queues a 24-byte record (emitter position, blast radius,
  blast length, 1.0) on a scene list (scene `+0x84`, also fed by `CAurObject::Update` `0x00486670`;
  its consumer was not traced, med).
- **Single**: exactly one particle while `int(birthrate)` != 0 (made on the first such frame and
  stepped from the next; destroyed when it becomes 0). It is never removed by age: with a positive
  lifeExp it ages and stays at its end values, or restarts at age 0 once past lifeExp when the
  node's `loop` flag (header +180) is set; with a negative lifeExp it is drawn at its start values.

## Drawing (`0x0049b680` picks, `0x0048f040` draws quads)

`0x0049b680` draws nothing for a `p2p` emitter without a target (`+0x1e4`); otherwise it calls
`0x00490700` when the chunk name is set, `0x00495b20` for Linked, `0x00490820` for Motion_Blur and
`0x0048f040` for the other modes. Each first runs the flipbook (below).

State: depth writes off, depth test on, lighting off, alpha test off, the blend of the table above (so a
particle is hidden by any opaque surface in front of it, a closed door included: sparks seen through a door
are on the near side of it);
`0x0048f040` also turns face culling off when the header's two-sided field (+176) is set, and
`0x00490820` always. Per particle the colour and alpha, and the half-sizes (size * 0.5) are the
start / mid / end values at the particle's age / lifeExp between percentStart / Mid / End (a percentStart
of 255 means "start to end, no middle"; before percentStart the start values, after percentEnd the
end values); colour and alpha are clamped to 0..1. The half-height is the sizeY curve when either
sizeY key of the current stretch is non-zero, else the width. Both half-sizes are multiplied by the
owner's scale (owner `+0x1b4`) and the alpha by the owner's alpha (owner `+0xd8`) and a fade factor
(`0x0048dc90`). The quad is `position +- X * halfwidth +- Y * halfheight` for two unit axes:

| render | X axis | Y axis |
|---|---|---|
| Normal | the camera's right, turned by the particle's angle about the view axis | view axis x X: the camera's up |
| Billboard_to_Local_Z | the emitter's X axis, turned by the angle about the emitter's Z | emitter Z x X: the emitter's Y. **The quad lies in the emitter's own XY plane** (a scorch on the floor, the crossed sheets of a muzzle flash) |
| Billboard_to_World_Z | world X turned by the angle about world Z | world Y. **Flat on the ground** whatever the emitter's orientation |
| Aligned_to_World_Z | the camera's right (turned by the angle) | world Z (minus when the camera is upside down): upright |
| Aligned_to_Particle_Dir | X axis of the particle's own quaternion | its Z axis (the way it was sent; the angle is not used) |
| Linked | `0x00495b20`, below | |
| Motion_Blur | `0x00490820`, below | |

A frozen (bounced) particle is instead turned by its angle about the surface normal, starting from
its own quaternion. With the `splat` flag (0x200) the Y axis is `+0x48` x X (the particle's launch
direction, or the surface normal once frozen) and the sizes are the full sizeStart (sizeStart_y)
while flying and sizeEnd (sizeEnd_y) once frozen, with no curve and no halving (med). A non-zero
frame-blending field (header +186) draws the emitter in 5 passes: the current cell at half alpha,
then neighbouring cells additively with alpha fading by the time into the cell (med).

Linked (`0x00495b20`, read 2026-10-09): one ribbon through the particles in list (birth) order, n - 1
quads for n particles. For the pair (i, i + 1) the segment's direction is projected onto the camera's X and
Y axes (columns 0 and 1 of the camera quaternion, camera `+0x88`): e2 is that on-screen direction, unit, and
e1 the perpendicular in the camera's plane (both the camera's axes when the projection is under 1e-5). The
quad's end corners are p(i+1) +- e1 * W + e2 * A, with W = particle i's sizeX (twice the half-size) and A a
quarter of its sizeY (of sizeX without one); its start corners are the previous quad's end corners (the
first quad's: p0 +- e1 * W - e2 * A). Each quad is coloured by particle i (one packed colour for its four
corners); u runs across the ribbon (the +e1 corners take the cell's right edge), v along it, each quad
showing the whole cell of particle i's flipbook frame. Positions are the particles' plus, when the emitter
answers vtable `+0x84` (only the Lightning class does, returning itself), its per-point offsets at `+0x270`.
For a Lightning emitter (the short at `+0x1f4` is 6) the curves run by the point's index over the count,
not by age over lifeExp. Depth writes off, depth test on, the blend of the table above; the owner's scale
multiplies the sizes.

Motion_Blur: a quad from the particle's tail `+0x60` to its head. Each frame, before the move, the tail
eases to the head: tail = (1 - t) tail + t head, t = min(dt, blurlength) / blurlength, so the streak
trails by blurlength seconds of motion (at least one frame's). The corners are head +- e1 * W + e2 * A and
tail +- e1 * W - e2 * A, with e2 the on-screen direction of head - tail (e1 across it, both in the camera's
plane), **W = sizeX** (so the streak is 2 * sizeX wide) and A = sizeY / 4 (sizeX / 4 when sizeY is 0).
The two tail corners' alpha is further multiplied by min(1, sizeX / the streak's on-screen length)
(med).

Flipbook (`0x0048e460`, run by the drawers, so only while drawn): when fps > 0 a particle's cell
advances one every 1/fps seconds from frameStart to frameEnd and stays at frameEnd (with frameStart
above frameEnd it stays on frameStart, med); with `random` bit 0 (flag 0x20) it wraps round instead; with
`random` bit 1 (flag 0x1000) each step jumps to a random cell rand % (|frameEnd - frameStart| + 1)
(not offset by frameStart). Cell c is the texture's tile c % xgrid across, c / xgrid down (header
+20, +24). After a step a particle with negative lifeExp has its age reset to 0.

## Lightning (`0x0049d1d0`, vtable `0x00743610`; read 2026-10-09)

A Lightning emitter births nothing: its particles are the points of a chain from the emitter to a target
(`+0x1e4`, a node), drawn as the Linked ribbon above. Every one of the 44 Lightning emitters in the data
(beam models `v_*_dur`, `plc_endcorps`, `m45ac_bmap`) is Linked, Lighten and point-to-point (flag 0x2).

- **Setup** (`0x0049d480`, slot `+0x7c`): the usual setup, then lifeExp (`+0x78`) = 1, the animation
  event `_EmitterTarget` registered on the owner (handler `0x0049b240`), the marker short `+0x1f4` = 6, and
  `branch_count` (header +12) child Lightning emitters of the same node made (arrays `+0x258`, their
  start points `+0x264`).
- **Target.** `0x0049b240` takes the target from the emitter's children: the first whose vtable `+0x38`
  answers, i.e. a reference node. Every Lightning node in the data has an `fx_ref` reference child a few
  metres along its +Z; the beam models' are `reattachable`, and a beam (render-gui.md, codes 600-699) hangs
  them on the target's node, so the bolt ends there. Without a target nothing is stepped or drawn (the
  update drops every particle, `0x0049b680` returns).
- **Point count** (`0x00494da0`, when slot `+0x84` answers): `+0xd0` = the distance to the target and
  birthrate (`+0x58`) = lightningSubDiv * distance + 2. The update (`0x00498b80`, slot `+0x80`) keeps
  exactly int(birthrate) particles (reusing a free list), so lightningSubDiv is points a metre.
- **The curve** (`0x00497c60`, slot `+0x88`, every controlptdelay seconds, `+0xf8` the clock; arrays of
  0x0c-byte points). The count is int(numcontrolpts (`+0x100`) * distance + 0.5) + 2 (`0x0073e9ac` is 0.5),
  so numcontrolpts is control points a metre (0.1 to 0.3 in the beams: one or two inner points on a 6 m
  bolt). The base curve is laid only when that count differs from the base's (and once by `0x00494da0` on the
  emitter's first step with a target, guarded by the byte `+0x1f7`); otherwise the base kept from before is
  used, as carried with the line (below) and with its ends set at the renewal. A base curve (`+0x210` points, `+0x234` tangents) is a cubic from the emitter's world position
  (`+0x164`) to the target's (slot `+0x64`) with handles start + R(q) * (0, 0, tangentlength), where q is
  the quaternion (w, x, y, z) at `+0x14`, the emitter part's **own** orientation (CAurPart's local
  transform, `0x004457a0`: position `+0x8`, orientation `+0x14`, scale `+0x24`; for an emitter part, its
  node's orientation in the model), used as a world direction without its parents' turns; and target +
  R(target's slot `+0x68` quaternion) * (0, 0, tangentlength). Its inner points are the cubic at k / (n -
  1), its inner tangents the cubic's derivative there scaled to tangentlength (`0x004ab130` normalises).
  The new curve (`+0x228` points, `+0x24c` tangents) then: the ends are the base ends, the start tangent
  R(`+0x1a4`, the emitter's world orientation) * (0, 0, tangentlength) and the end tangent the unit line
  to the target times tangentlength, neither perturbed; each inner point is the base point plus (rand %
  int(controlptradius * 100)) / 100 with a random sign times the square direction `+0x27c` (set once, on the
  first step, from the unit line u to the target as (-u.y, u.z, -u.x), `0x00494da0`: square to u only for some
  directions, and fixed in the world afterwards; a branch's from its own line at each branching), that offset
  turned about **world X** by rand % 360 degrees (`Quaternion_FromEulerDegrees(0, rand % 360, 0)`); each
  inner tangent is the base tangent turned by `Quaternion_FromEulerDegrees(a, b, 0)` (Z then X, degrees),
  a and b each (rand % int(tangentspread * 100)) / 100 with a random sign (`0x00741838` is 100). Before
  that, the previous new curve is copied into the old (`+0x21c`, `+0x240`); a branch (`+0x28c` set) copies
  the new points into the old at once. Each chain point i lies at i / (n - 1) of the old curve's cubics
  (points and tangents of neighbouring control points: s^3 A + 3 s^2 t (A + TA) + 3 s t^2 (B - TB) + t^3 B).
  (high for the formulas; med for slot `+0x68` being the target's world orientation)
- **Smoothing and carrying** (`0x00498b80`): while the control clock is within controlptdelay, a main
  chain (`+0x28c` clear) whose node has control-point smoothing (header +16, a dword flag, 1 where set:
  `v_drain_dur`, `v_deathfld_dur`, `v_fshock_dur`, `plc_endcorps`, `m45ac_bmap` ...) evaluates its points
  on the blend of the old and new control points and tangents by clock / controlptdelay, so the bolt moves
  from one curve to the next; without it, or for a branch, the points stay. At the renewal the clock
  resets, the base ends are set to the emitter's and the target's positions, the curve is made (slot
  `+0x88`) and, for a main chain with branches, the branches (slot `+0x8c`) with their clocks set to
  controlptdelay. Between flickers (the flicker clock within lightningDelay) the points, control points
  and tangents are turned and moved rigidly with the line from the emitter to its target (`0x004ab630`,
  the rotation from the old line `+0x1f8` to the new).
- **The flicker** (every lightningDelay seconds, `+0xf4`): for each inner point i of n, an offset
  (`+0x270`, added only when drawing) = a direction square to the chain times 2 * min(i/n, 1 - i/n) *
  lightningRadius * (rand % 100) / 100, plus the chain's unit direction times (L / n) * 0.5 *
  lightningScale * (rand % 100) / 100 with a random sign. The square direction (`+0x27c`, set from the
  chain's direction) is turned about the chain before each point by an angle that grows by rand %
  int(lightningZigzag) degrees (or 360 minus that) a point, so a non-zero zigzag twists the bolt; the
  end points are not moved. (A second rule behind the global `0x0083049c`, an offset along a fixed
  perpendicular of up to rand % int(...) hundredths times lightningScale, is not used: the global is 0, med.)
- **Branches** (`0x00491a50`, slot `+0x8c`, with each new curve): rand % (branch_count + 1) of the
  children run (each a Lightning emitter of its own, so its control points are made by the same `0x00497c60` on
  its next step, its clock having been set to controlptdelay; its base's start tangent is the parent's square
  times tangentlength turned by (-(rand % 45)) degrees about Z and rand % 360 about the third axis, its end
  tangent that one again for a fork or the parent's last base tangent otherwise; read 2026-10-09, med: the
  child's own base count and target node, which decide whether those are used, were not followed). Each gets s = 0.1 + (rand % 80) / 100, its sizes (start, mid, end and the y ones) s times
  the parent's, and a start point on the parent's chain. With s <= 0.5 it forks to a point of its own:
  from its start, (rand % 75 / 100 + 0.25) * L / 2 along the parent's square turned about world X by rand % 360
  degrees plus
  (rand % 25 / 100 + 0.25) of the chain's line; with s > 0.5 it runs to the parent's target. Its point
  count is lightningSubDiv * its length + 2, its start follows the parent's offset point each frame, and
  it is stepped and flickers as a chain of its own (the children are drawn as emitters of their own).
