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
position += velocity * dt + the inherited speed `+0x18` * its direction * dt, then
velocity.z -= dt * mass * 9.81, and the inherited speed is multiplied by (1 - dt). `inherit`
(flag 0x40) keeps the particles rigid with the emitter (each frame they are carried by its move and
turn, velocity included); `inherit_local` (0x100, only without `inherit`) adds the owner object's
move each frame, `inherit_part` (0x400) the emitter's move (both also move the streak tail);
`affectedByWind` (0x4) adds an offset from the scene's wind query (scene slot `+0xd0`, given the
particle's position and dt), asked for every particle while the emitter has fewer than 50 and for
every sixth otherwise (the others reuse the last answer); `bounce` (0x10) ray-casts the step against
the scene. On a hit (the scene sets the position to the hit point): with bounce_co 0 the particle
stops; otherwise the velocity is reflected about the surface normal, scaled by 0.75, and its z
further by bounce_co * clamp(0.033 / dt, 0.5, 1). A particle whose squared speed is then below 0.5
freezes (`+0x6c`): it stops being stepped, its quaternion is turned to lie along the surface normal
(kept at `+0x48`), and it sits 2 cm off the surface (plus sizeStart for a chunk model). (The
global `0x00798ba0` that selects this rule is 1; its mode 2 is unused.)

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

State: depth writes off, depth test on, lighting off, alpha test off, the blend of the table above;
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

Linked (med): one ribbon through the particles in list (birth) order, a quad per pair of neighbours
sharing its end corners with the next one, built like the Motion_Blur quad below (width across the
on-screen direction to the next particle, W = sizeX, A = sizeY / 4), each quad coloured and sized by
the first particle of the pair.

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
