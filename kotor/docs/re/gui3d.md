# GUI 3D scenes in swkotor.exe

Small 3D worlds inside GUI panels: the main menu's animated background, the character and
upgrade panels' models, the galaxy map, the software mouse cursor. This page is what the engine
does for the main menu (found by reading `CSWGuiMainMenu::CSWGuiMainMenu` and the code it calls)
and what `kotor/lib/frontend/gui3d` does about it. Addresses are for the Steam `swkotor.exe`
after SteamStub removal (README.md); each claim has a confidence (high = read in the code, med =
role clear and detail inferred, low = plausible). Names are ours.
The whole page was rechecked claim by claim on 2026-10-08 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check"
rests on static reading alone and is surprising enough to test before relying on it.

## Main menu 3D scene

### How the panel builds it

`CSWGuiMainMenu` (ctor `0x0067c4c0`) holds the control `LBL_3DVIEW` at `+0x360`, a custom control
whose vtable is `0x00752e30` and whose member at control `+0x5c` (panel `+0x3bc`) is a
`CSWGui3DScene` (class vtable `0x0073e3f0`, ctor `0x004174b0`). The panel's own code only does
this, after the button handlers, and only `if (DAT_0078d1e4 != 0)` (a global that is 1 in the
image and that no function in the decompile writes, so always on in this build (med: a store
through a computed address would not show); every GUI 3D panel tests it, the cursor model's
scene, `CSWGuiManager::CreateCursorModel` `0x0040b060`, does not) (high):

1. `scene->vtable[+0x70]("gui3D_room", pos (0,0,0), orientation (0,0,0,1))` = `FUN_00456f30`
   (`CAurScene` slot 28): puts the **room** model `gui3D_room` into the scene at the origin
   (below). The two zero blocks are a position and a quaternion, not colours. (high)
2. `FUN_00417620(&scene3d, "mainmenu", -1)` adds the model `mainmenu` to the scene: it makes the
   object (`FUN_00449cc0`, 0x1cc bytes, vtable `0x00741268`), appends it to the list at
   `+0x1c` and attaches it (`FUN_004175c0`, object slot `+0x4c`). (high)
3. object slot `+0x18` = `PlayAnimation("default", speed 1.0, flags 0, start 0.0)` (`FUN_00485bd0`).
   Flags 0 means loop: the object update (`CAurObject::Update` `0x00486670`) takes an animation
   without flag bit 0 back by its length when it passes the end, and one with the bit as done.
   (high)
4. object slot `+0x14` with 1.0 = `CAurObject::Update` (`0x00486670`, slot 5 of `0x00741268`; the
   same slot the scene's per-frame update calls with dt, below): the model is advanced by one second
   straight away, so the animation starts at 1 s. (high) The emitters are not stepped here: they
   run in the scene's render (below), which pre-runs them 10 s on its first frame.
5. camera slot `+0x74` (`FUN_0045c200` → `FUN_00443820`) with the object and `"camerahook"`:
   attaches the camera to that node of the model; the camera's world position and orientation
   are the node's, every frame. (high)
6. camera slot `+0x44` with `0x41b5ced9` = **22.70**: `CAurCamera::SetFieldOfView`, stores
   degrees at camera `+0x1d0`. (high)

`CSWGui3DScene` (ctor `0x004174b0`) has: `+0x14` a `CAurScene` made with `CAurScene::Create("scene")`,
`+0x18` a `CAurCamera` made with `CAurCamera::Create("camera")`, `+0x1c` the model list,
`+0x04..0x10` its rectangle, `+0x28..0x30` a colour. The ctor sets the camera's near and far to
**0.1 and 10000** (slot `+0x40`) and attaches the camera to the scene (slot `+0x14`). The colour
is read from `0x0078d3d8` = (-1,-1,-1), which means "do not fill". (high)

### Drawing

`CSWGuiPanel::Render` (`0x0040b760`) calls each visible control's Render slot (`+0x38`); the 3D
control's (`0x0067acb0`) jumps to the scene object's slot 3 = `FUN_00414fb0(dt)`:

1. scene slot `+0x1c` (`dt`, `0x00451c80`): calls every object's `+0x14` update
   (`CAurObject::Update`) with the frame's own delta time: animations. (high)
2. `Render_PushViewport(x, y, w, h, colour (-1,-1,-1), clear = 1, alpha 1.0)`
   (`0x004592f0`): the control's rectangle in screen pixels, offset
   by the panel's place. No colour fill, because the colour is -1; clear = 1 clears **depth and
   stencil only**. So the colour under the 3D view is whatever was drawn before it: nothing
   (black) except the GUI backdrop. (high)
3. camera slot 2 = `CAurCamera::Render` (`0x0045c540`) → `gluPerspective(fov, w / h, near, far)`
   with `w / h` of the **current GL viewport**, i.e. of that rectangle (the camera has an override
   rectangle at `+0x1e4..0x1f0`, zero here), then the view matrix from the camera object's world
   position and quaternion (`LoadViewMatrix` `0x00425ca0`: rotate by the inverse, translate by the
   negated position, no extra axis swap), then the scene (`CAurScene::Render` `0x004512d0`). (high)

The particles are stepped inside `CAurScene::Render`, not by the object update. Its emitter pass
(`0x004509b0`, scene slot `+0x110`) steps each emitter that is drawn (`0x00494da0`) with
min(frame delta, 0.1 s) and then draws it. And on the scene's **first** render (the frame counter
at scene `+0x50`, zeroed by `CAurScene::CAurScene`, still 0) `0x004511f0` runs every emitter of
the scene's rooms and of the scene's own list (`+0x94`) through `0x00494da0` **100 times with dt
0.1 s**: 10 s of simulation, so the mist (life 10 s) is at its steady state in the first picture.
The model's emitters are on that list: `CAurScene::AddObject` (slot 44, `0x00455670`) walks an
object's node tree with `0x004531a0` when it has a model (object `+0x58`, set by the object's
constructor `0x00449cc0`) and appends each node's emitter (node slot `+0x34`) to `+0x94` once.
(high for the code; med until a runtime check)

**Field of view: vertical, in degrees, 22.70; the aspect is the viewport's.** It is the argument
`fovy` of `gluPerspective`. The model confirms it: `Plane01` (the backdrop, texture `loadscreen3`)
is 6.4 x 4.8 m at 11.956 m from the camera hook, and 2 atan(2.4 / 11.956) = 22.70 degrees, so
the plane fills the viewport's height exactly, and its width exactly at 4:3. On a wider viewport
the sides show whatever is behind the plane (the black room). (high)

### The camera hook

`camerahook` is a dummy node at (0, -6.1136, 1.1934) with orientation w,x,y,z = (0.7071, 0.7071,
0, 0): +90 degrees about X. It is **not animated** (the `default` animation has no keys for it).
Since the view matrix applies the node's rotation inverse as it is, the camera looks along its
local -Z, as GL's does: a +90 degree rotation about X takes local -Z to world +Y and local +Y to
world +Z, so the camera looks along +Y with Z up, toward Malak (at y = 0.85) and the backdrop (y =
5.84). (high)

### The room: `gui3D_room`

`gui3d_room.mdl` (models.bif, 1553 bytes + 600 MDX): a dummy and one mesh `Box01`, 24 vertices,
normals pointing inward, texture `Black`, extents x +-530, y +-530, z 0..150 in the mesh's space,
the mesh node at (0.02, 9.23, -40.36) so the box spans z -40..110: a black room around the camera
and the model. The engine needs a room in a scene for anything to be visible; here it also gives
a black background. Every GUI 3D panel scene uses the same room (main menu, class selection,
character generation, portrait, level-up, character sheet, galaxy map, upgrade: the callers of
the `gui3D_room` string); the cursor's scene loads only `gui_mouse`. The library does not load it: it
clears the viewport to black, which is the same picture. (high for the contents, med for the
role)

**Ambient light.** `CAurScene::RenderPasses` sets `GL_LIGHT_MODEL_AMBIENT` from the scene's
`+0x88..0x90`, which `CAurScene::CAurScene` zeroes; nothing else in the code writes those fields
of a GUI scene. So the scene's ambient is **(0, 0, 0)**. The blue ambience of the picture comes
from the model's ambient-only light node (below). (med: other writers could go through a
differently shaped expression)

### The model `mainmenu`

`mainmenu.mdl` (387,699 bytes) and `.mdx` (264,688) are in `models.bif`; `rims/mainmenu.rim` and
`mainmenudx.rim` carry the same files (same sizes), which the constructor mounts as `RIMS:MAINMENU`
when a resource `MAINMENU` of type 0xbba (3002, the RIM) exists (`CExoResMan::Exists`). The
menu's destructor (`0x0067b500`) flags it for removal (resman `+0x34` bit 1) under the same test,
and the GUI manager's input pass (`0x0040c8e0`) or a `CSWGui3DScene` destructor (`0x004165e0`)
then removes it. `lib/res`
finds the BIF copy; no special case. Another model, `mainmenu_model`, is in the BIF and unused.

- Classification 4, bounding box +-5 x +-5 x -1..10, radius 40, no supermodel, one animation
  `default`, 16 s, blend 0.25 s, no events. It moves only Malak's skeleton (83 nodes with orientation keys,
  81 with position keys); no emitter, light or camera keys.
- Meshes that draw: `floor_01` (14.5 x 4.8 m at z = 0, texture `InnerMenu` + lightmap
  `mainmenu_a00005`, which is **in no archive** of the install: the floor draws without it),
  `Plane01` (the backdrop, `loadscreen3`, self-illumination colour white), and Malak as skinned
  meshes `torso`, `BackCape`, `RArm`, `LArm`, `headlo02`, `MidFlap` (`N_DarthMalak01`, `N_DarthMalakh01`)
  with four small eye meshes. The `*_g` meshes of the same skeleton do not render (flag 0).
- Lights: `AuroraLight04` ambient-only, colour (0.204, 0.243, 0.380), multiplier 1, radius 2, at
  (-1.007, -0.494, 1.242), priority 2; `AuroraLight01`, colour (0.980, 0.961, 0.961), multiplier 1,
  radius 2.534, at (-0.087, 0.837, 2.595), priority 1, shadow 1.
- Emitters (all update `Fountain`, texture `fx_Smoke` 4 x 4 cells, frames 0..15, no `fps`):

| Node | Facing | Order | Birth/s (+random) | Life s | Size start / mid / end | Alpha | Colour start / mid / end | Area x, y | Spin | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| `Mist` | `Billboard_to_World_Z` | 0 | 7 | 10 | 5 / 3 / 1 | 0 / 0.4 / 0 at 0, 0.1, 1 | 0.06 / 0.09 / 0.24 | 400, 400 | +0.2 | 0x122 |
| `Mist01` | same | 1 | 7 (+2) | 10 | 1 / 3 / 5 | 0 / 0.3 / 0 | 0.15 / 0.11 / 0.06 | 400, 400 | -0.2 | 0x122 |
| `Fx_PuffySand` | `Normal` | 4 | 25 | 4 | 1.5 flat | 0 / 0.5 / 0 at 0, 0.3, 1 | 0.06 / 0.11 / 0.18 | 281, 160 | +0.1 | 0x22 |
| `Fx_PuffySand01` | `Normal` | 4 | 30 | 4 | 1 / 1.5 / 1.5 | 0 / 0.5 / 0 at 0, 0.05, 1 | 0.18 / 0.18 / 0.10 | 182, 170 | -0.3 | 0x22 |
| `Fx_PuffySand02` | `Normal` | 5 | 25 (+5) | 6 | 0.5 / 1.5 / 1.5 | 0 / 0.6 / 0 at 0, 0.08, 1 | 0 / 0 / 0.18 | 149, 170 | +0.3 | 0x22 |
| `Fx_PuffySand03` | `Normal` | 0 | 22 (+8) | 4 | 1 / 2 / 2 | 0 / 0.3 / 0 at 0, 0.3, 1 | 0 / 0.27 / 0.80 | 180, 170 | -0.2 | 0x22 |

  (Velocity 0 everywhere, `randvel` 0 for the two `Mist` emitters and 0.1 to 0.2 for the sand
  puffs, `spread` 0 or 2 pi, `mass` (the gravity, particles.md), `grav` and `drag` 0; the puffs
  have `bounce_co` 0.3 but no `bounce` flag. Flags: 0x2 `p2p_sel`, 0x20 `random`, 0x100
  `inherit_local`.)

### Emitter behaviour read from the code

`FUN_00496e40` (the Fountain emitter's per-frame update, 2019 bytes) and the particle initialiser
`FUN_004921d0` (vtable `0x007432d8` slot 2) give (high unless stated; the full rules are in
[particles.md](particles.md)):

- each particle's rotation adds `dt x particleRot` (radians per second), wrapped at +-2 pi;
- births: a timer accumulates dt; once it reaches 1 / birthrate, the rate b = birthrate plus or
  minus `rand % round(m_fRandomBirthRate)` (random sign) gives `int(b x timer) mod (int(b) + 1)`
  particles at once and the timer restarts at 0; when the `random` flag (0x20) is set the cell
  number is frameStart + a random one of `frameEnd - frameStart + 1`;
- start position (`0x0048d870`): `x`, `y` offsets = `(rand x rand) mod N` with N =
  int(int(size x scale x 100) x 0.5), either sign, times 0.0001, along the emitter's own X and Y
  axes: **an offset of up to size / 200 metres each way** (a 400 area is +-2 m);
- start velocity: speed = `velocity` + (rand mod (randvel x 100)) x 0.01 with a random sign when
  `randvel` > 0.01, along +Z turned by the `spread` cone;
- drawing (particles.md): colour, alpha and size are linear start / mid / end at the percent
  keys; `Normal` blending is src alpha, 1 - src alpha; the quad's half-size is size x 0.5, so
  `size` is the full width in metres; `p2p`, `inherit*`, bounce and the `Single` / `Explosion` /
  `Lightning` updates are described there.

### What lib/frontend/gui3d does

`gui3d::load` / `update` / `add_to_frame` / `free` (gui3d.ctx; particles.ctx):

- the model, its light nodes, pose and animation (`default` looped, started at 0, plus an optional
  warm-up of the animation alone that the main menu sets to 1.0 s, the original's one-second object
  update) come through `mdl_cache`, `mdl_anim`, `mdl_render` and `material`; then every emitter runs
  100 steps of 0.1 s, the original's first render (above);
- the camera is `pose.world[camera node]` inverted, `perspective(fov, viewport w / h, 0.1, 10000)`;
- the ambient-only light is a flat ambient term (colour x multiplier) and the others are frame
  lights; the original lights through up to three GL lights per object with quadratic attenuation,
  and gives the ambient-only one that attenuation too (the code in `FUN_004a2a00` sets the light's
  ambient to its colour); ours is brighter away from the light (med);
- the view clears its viewport to black (the room);
- full emission (the backdrop's white `selfillumcolor`) is drawn unlit. The seam adds
  self-illumination after the texture, which turns the plane white; the engine adds it to the lit
  colour **before** the texture multiplies it (GL emission), so a fully emissive surface shows its
  texture as it is. Other values still go through the seam's rule. Worth a fix in the seam's
  shader (`rgb = base.rgb * (light + selfillum)`) for the render lead;
- emitters are simulated on the CPU as particles.md describes (births in clumps, per metre for spawn
  type 1, the size / 200 start offset, world-space particles, `inherit*`, `inheritvel`, `p2p` toward
  the emitter's reference child, Lightning bolts), stored in the emitter node's space, drawn one batch
  per emitter in the facing of their render mode (`Billboard_to_World_Z` lies flat on the ground,
  which is what the original does: re/particles.md), sorted by `render_order`, at the full `size` as
  the original draws it. Nothing bounces (a GUI scene has nothing to bounce off), and `Explosion`
  emits like a Fountain (no animation of these models says `detonate`);
- not done: the room model, fog, the shadow of `AuroraLight01`.

Checked by running `kotor/tools/ctxc run kotor/tools/gui3dview` (pictures in `kotor/out/gui/`):
Malak in a dark red robe and dark cape with a pale mask, arms crossed, on the left; the dark
bulkhead of `loadscreen3` behind him; haze rising from the floor from about 3 s on and thickening
to a steady state at about 10 s (life); a 4:3 slice of picture with black beside it at 16:9. (The
original should show that steady state from its first frame, by the 10 s pre-run above.)
