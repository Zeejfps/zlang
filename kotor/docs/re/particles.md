# Particle emitters in the original (what an MDL emitter node does)

What `swkotor.exe` does with an emitter node, read from the decompiled client code (names are ours;
addresses are of the unpacked image, see [README.md](README.md)). The node's fields are in
[../formats/mdl.md](../formats/mdl.md); how we use this is in [../design/vfx.md](../design/vfx.md).

## The emitter object

- `0x0049d5c0` makes the emitter for a node from its `update` string: `Fountain` (vtable `0x00743478`),
  `Explosion` (`0x00743500`, which also registers the animation event `Detonate`), `Single`
  (`0x00743588`); anything else (`Lightning`) is a different class (size `0x290`, `0x0049d1d0`). The first
  three share a 0x1f8-byte object and differ in their per-frame update (vtable slot `+0x80`):
  `0x00496e40`, `0x00497640`, `0x004979c0`.
- `0x0049caa0` (the setup, run once as the emitter is made) turns the `render` string into a code
  at object `+0x114` and the `blend` string into one at `+0x4c`:

  | render | code | | blend | code |
  |---|---|---|---|---|
  | Normal | 1 | | Normal | 0 (src alpha, 1 - src alpha) |
  | Billboard_to_Local_Z | 2 | | Punch-Through, PunchThrough | 1 (alpha test) |
  | Billboard_to_World_Z | 3 | | anything else (Lighten) | 2 (src alpha, one; fog off while drawing) |
  | Linked | 4 | | | |
  | Aligned_to_World_Z | 5 | | | |
  | Aligned_to_Particle_Dir | 8 | | | |
  | Motion_Blur | 9 | | | |

  (6 and 7 are not render modes.) A string that matches none leaves the code as it was.
- The emitter's animatable values sit at object offsets **equal to their controller ids**: birthrate
  at `+0x58` (88), fps `+0x68` (104), frameEnd `+0x6c`, frameStart `+0x70`, lifeExp `+0x78` (120),
  **mass `+0x7c` (124)**, particleRot `+0x88`, randvel `+0x8c`, sizeStart `+0x90`, spread `+0xa0`,
  velocity `+0xa8`, xsize/ysize `+0xac/+0xb0`, blurlength `+0xb4` (180), percentStart/Mid/End
  `+0xdc/+0xe0/+0xe4`, colours from `+0x11c`. So `grav` (116, `+0x74`) is not gravity: it is only read for
  point-to-point emitters (flag `p2p`). Gravity is `mass`.
- Particles live in **world space**. The emitter's world position is `+0x164`, its world orientation
  quaternion (w, x, y, z) `+0x1a4`; both come from a virtual call each frame.

## A particle

Created by `0x004921d0` (and its constructors `0x00494c40`/`0x00494cb0`):

- position `+0x08` = the emitter's world position, plus, when xsize/ysize are not both 0, a random offset
  of up to size/100 metres along the emitter's X and Y axes (`0x0048d870`); the streak tail `+0x60`
  starts at the same point;
- orientation quaternion `+0x2c` = the emitter's; with `spread` != 0 it is tilted about the emitter's X axis
  by a random angle in 0..spread and then turned about the emitter's Z axis by a random angle in 0..2 pi
  (`0x0048de60`); **velocity** `+0x54` = (velocity + random in +-randvel) along that quaternion's Z axis;
- **angle `+0x14` = 0** (not random); each frame `angle += particleRot * dt`, wrapped to +-2 pi;
- age `+0x70`, frame `+0x3c` = frameStart (or, with the `random` flag, a random cell of the range, `0x0048dcf0`).

Each frame (`0x00492450`, for emitters without `p2p`): position += velocity * dt (+ the inherited velocity
`+0x18` * its vector, which decays by (1 - dt) a second), then velocity.z -= dt * mass * 9.81. `inherit`
(flag 0x40) keeps the particles rigid with the emitter (they are carried by its move and turn), `inherit_local`
(0x100) adds the owner object's move each frame, `inherit_part` (0x400) the emitter's move; `affectedByWind`
(0x4) adds the area's wind; `bounce` (0x10) ray-casts the step against the scene and reflects the velocity
by the bounce coefficient, and a particle that comes to rest there freezes (`+0x6c`), lies along the surface
normal and sits 2 cm off it.

## The three update types

- **Fountain**: about `birthrate` particles a second (plus the random part `m_fRandomBirthRate`),
  each living `lifeExp` seconds (a negative lifeExp: it never dies and is drawn at its start size and
  colour). The spawn type field (header +28) of 1 spreads a moving emitter's births along its path.
- **Explosion**: nothing until the animation's `Detonate` event; then `int(birthrate)` particles at once
  (none if that is 0), and not again until the event has been off for a frame.
- **Single**: exactly one particle while `int(birthrate) >= 1` (none when it is 0). It ages; with a
  positive lifeExp it stays at its end values, or restarts when the node's `loop` flag is set; with a
  negative one it stays at its start values.

## Drawing (`0x0049b680` picks, `0x0048f040` draws quads)

State: depth writes off, depth test on, the blend of the table above. Per particle the colour and alpha, and the half-sizes (size * 0.5) are the
start / mid / end values at the particle's age / lifeExp between percentStart / Mid / End (a percentStart
of 255 means "start to end, no middle"); the half-height is the sizeY curve when any of its three keys
is set, else the width. The quad is `position +- X * halfwidth +- Y * halfheight` for two unit axes:

| render | X axis | Y axis |
|---|---|---|
| Normal, Linked | the camera's right, turned by the particle's angle about the view axis | view axis x X: the camera's up |
| Billboard_to_Local_Z | the emitter's X axis, turned by the angle about the emitter's Z | emitter Z x X: the emitter's Y. **The quad lies in the emitter's own XY plane** (a scorch on the floor, the crossed sheets of a muzzle flash) |
| Billboard_to_World_Z | world X turned by the angle about world Z | world Y. **Flat on the ground** whatever the emitter's orientation |
| Aligned_to_World_Z | the camera's right (turned by the angle) | world Z (minus when the camera is upside down): upright |
| Aligned_to_Particle_Dir | X axis of the particle's own quaternion | its Z axis (the way it was sent; the angle is not used) |
| Motion_Blur | `0x00490820`, below | |

Motion_Blur: a quad from the particle's tail `+0x60` to its head. Each frame, before the move, the tail
eases to the head: tail = (1 - t) tail + t head, t = min(dt, blurlength) / blurlength, so the streak
trails by blurlength seconds of motion (at least one frame's). The corners are head +- e1 * W + e2 * A and
tail +- e1 * W - e2 * A, with e2 the on-screen direction of head - tail (e1 across it, both in the camera's
plane), **W = sizeX** (so the streak is 2 * sizeX wide) and A = sizeY / 4 (sizeX / 4 when sizeY is 0).

Flipbook (`0x0048e460`, per frame): when fps > 0 a particle's cell advances one every 1/fps seconds from
frameStart to frameEnd and stays at frameEnd; with the `random` flag it wraps round instead.
