# Movement, camera and targeting in swkotor.exe

How the original engine moves things around an area: keyboard control of the party leader, the
cameras that follow it, how every creature walks along a planned path on the walkmeshes, how
paths are planned (straight lines, the area's PTH graph, a local grid), what happens when
something is in the way, how triggers notice creatures, how party members follow the leader,
and how the player picks targets. Addresses are for the Steam `swkotor.exe` after SteamStub
removal (see [README.md](README.md)). Every claim ends with a confidence: **high** = read in the
code, **med** = role clear, detail inferred, **low** = plausible. Names are ours, in the engine
family's vocabulary; the proposals for every address below are in `kotor/re/proposals/movement.tsv`
(git-ignored scratch, to be merged into [names.tsv](names.tsv)).

Related pages, and where the boundary is:

- [objects.md](objects.md): object layouts, the event queue, script slots. [actions.md](actions.md):
  the action queue and what each move action stores and decides (MOVETOPOINT's parameter list,
  re-queuing, timeouts, chasing a moving target); this page covers the planner and the walking
  that those actions call.
- [gameloop.md](gameloop.md): frames, world time, the module switch that an area transition
  starts. [combat.md](combat.md) and [rules.md](rules.md): combat rounds, trap DCs, effects that
  change movement speed. [dialogue.md](dialogue.md): conversation cameras.
  [gui.md](gui.md): the HUD panels. [party-items-saves.md](party-items-saves.md): party membership.
- Formats: [../formats/bwm.md](../formats/bwm.md) (walkmeshes), [../formats/pth.md](../formats/pth.md)
  (path graphs), [app.md](app.md) (input devices, the keymap 2DA, `ProcessInput`).

Offsets on `CSWSCreature` are from the object start (the `CGameObject` pointer); "path state"
means the 0x278-byte block a creature points to at `+0x340` (see section 4.1).

## 0. The picture

Client and server share one process, and movement uses that shortcut. **The party leader under
keyboard control is moved by the client**: a small controller integrates a velocity from the
keys, moves the client creature with its own collision test, and then writes the new position
straight into the server creature through `CServerExoApp` helper calls, which also run the trigger
checks. No network message is involved. **Every other movement is server-side**: a MOVETOPOINT
action asks the module's planner for a path (time-sliced, 1 ms per call), then each frame the
creature advances along the path's waypoints at its walk or run rate with an acceleration and
braking profile, with its z snapped to the walkmesh face below it, testing every step against
placeables, doors and other creatures. Party followers are server creatures too, but their target
comes from a trail of the leader's positions kept in a client-side party table. Triggers are
volumes in the area; each server-side move step works out which volumes the creature left,
entered or crossed and queues script events for them. The camera is a client-side controller
attached to the module's `CAurCamera`: a chase camera behind the leader, swapped for free-look,
combat, dialogue or death cameras.

## 1. Player control

### 1.1 Input events

The keymap rows `Action200`..`Action264` are button events with those numbers; the axis rows
`Action280A/B`..`Action286A/B` become axis events 280..286 built from two keys (`SetupKeymapping`
`0x005eeb10`, see [app.md](app.md)). The ones this page uses (keymap.2da, PC defaults):

| Event | Keymap name | Default key | Handled by | What it does | Conf. |
|---|---|---|---|---|---|
| 280 (`0x118`) | ActionUp / ActionDown | W / S | `ProcessInput` `0x006227e0` | forward axis −1..1 → player control | high |
| 281 (`0x119`) | ActionLeft / ActionRight | Z / C | `ProcessInput` | strafe axis → player control | high |
| 284 (`0x11c`) | CameraRotateLeft / Right | A / D | `UpdateCameraInput` `0x005f5e10` | camera yaw (section 2) | high |
| 204 / 205 | SelectPrev / SelectNext | Q / E | `HandleInputAction` `0x00621210` | cycle the target (7.3) | high |
| 206 | ChangeChar | Tab | `HandleInputAction` | next party member becomes the leader (6.3) | high |
| 208 | Freelook | Caps Lock | `HandleInputAction` | free-look camera, input class 4 (2.5) | high |
| 219 / 220 | Left/RightLookabout | Ctrl | `HandleInputAction` | hold for mouse look (`g_bLookAboutHeld` `0x008338f0`; the right mouse button sets it too) | high |
| 221 / 222 | AlternateActions | Shift | `HandleInputAction` | `g_bAlternateActionsHeld` `0x008338f8`: the 1–3 keys use the secondary action list | med |
| 226 / 228 / 230 | Target{Left,Middle,Right}Act | 1 / 2 / 3 | `HandleInputAction` | the three target action slots (7.4) | high |
| 232..238 (even) | Personal*Act | 4 / 5 / 7 / 6 | `HandleInputAction` | personal action slots (gui.md) | med |
| 239 | DefaultAction | R | `HandleInputAction` | run the target's default action (7.4) | high |
| 240 | CancleCombat | F | `HandleInputAction` | leave combat mode (`CSWCCreature::SetCombatMode(0)` `0x00610a10`) and cancel the leader's actions | high |
| 264 | STEALTH | G | `HandleInputAction` | toggle stealth (`0x0060f4b0`) | med |
| `0x43` / `0x44` | (mouse buttons, hard-wired) | | `OnLeftMouseDown/Up`, `OnRightMouseDown/Up` | selection clicks (7.4); right button = look about | high |

The keymap rows `MoveForward`/`MoveBack`/`StrafeLeft`/`StrafeRight` (200–203) are disabled; the
arrow keys only drive the minigames. There is **no run/walk toggle** on the PC keymap: the leader
always runs at full keyboard input. (high for the keymap, med for the conclusion)

### 1.2 The player control object

`CClientExoAppInternal+0x2a0` holds a 0xcc-byte controller, `CSWCPlayerControl` (constructor
`0x00679780`, vtable `0x00752d34`, 12 slots; built or re-bound to the new leader by
`CClientExoAppInternal::OnControlledCreatureChanged` `0x005f5cf0`). Its fields: (high unless marked)

| Offset | Meaning |
|---|---|
| `+0x04` | controlled creature (client id) |
| `+0x08` | the module camera (its orientation gives the camera yaw) |
| `+0x10` / `+0x14` | forward input / leftward strafe input, −1..1 (slots 0/1 and 2/3) |
| `+0x18` | walk modifier (slot 4): when set the input vector is halved. Fed from event 265, which no keymap row binds (med) |
| `+0x1c..+0x24` | last desired facing (unit vector) |
| `+0x38` / `+0x3c` | MinTurnRate / MaxTurnRate in °/s, from camerastyle.2da (row = the area's `CameraStyle`) (`LoadSettings` `0x006793c0`) |
| `+0x40` | turn direction, ±1 |
| `+0x5c..+0x64` | velocity (m/s) |
| `+0x68..+0x70` | integrated position (only differences are used) |
| `+0x74..+0x7c` | previous frame's input vector |
| `+0x80` | rate integrator used for turning in free-look (section 2) |
| `+0xc0..+0xc8` | Keyboard Camera DPS / Acceleration / Deceleration options |

`ProcessInput` reads the axes each frame (the joystick axes 7/8 take precedence when non-zero)
and sets the inputs, then calls slot 10, **`CSWCPlayerControl::Update(dt)`** (`0x00679940`).
In order: (high unless marked)

1. `dt` is clamped to at most 1 s. Nothing happens without a controlled creature, while it is
   dead, dying or in an incapacitating state.
2. In free-look (camera mode 5) the creature's facing is turned by the controller's rate
   integrator instead (section 2.5).
3. **Input vector** `i = (−strafe, forward, 0)`, normalised when both components are non-zero
   (diagonals are not faster), halved by the walk modifier.
4. **Camera-relative direction**: `i` is rotated about +z by the camera's yaw. (high for the
   rotation, med for the exact yaw extraction)
5. **Turning**: if there is input, the shortest signed angle Δ between the desired heading and
   the creature's facing is computed. When |Δ| > 0.1° and the creature's current speed
   (`+0x3b0` on the client creature) is above 0.1 m/s, the facing turns by at most
   `rate·dt`, with
   `rate = MinTurnRate + (MaxTurnRate − MinTurnRate)·(1 − |v| / vmax)` °/s,
   so the creature turns fast from standstill (1500 °/s with the DEFAULT style) and slowly at
   full speed (150 °/s). The new facing goes to the client creature; the server copy gets it
   with the next position update (1.3).
6. **Velocity**: with no input and both |vx|, |vy| below 0.25 the velocity is zeroed. Otherwise
   the state (v, p) is advanced by one classical Runge–Kutta step (weights 1/6, 1/3, 1/3, 1/6)
   of
   `dv/dt = K·u − (K / vmax)·v`, `dp/dt = v`,
   where `u` is the direction from step 4 (interpolated half way between last frame's and this
   frame's input for the middle evaluations), `vmax` is the creature's speed and `K` its
   acceleration (`ComputeAcceleration` `0x00679870`). So `v` approaches `u·vmax` exponentially
   with time constant `vmax / K`.
   - `vmax` (`GetMaxSpeed` `0x00679510`): the client creature's movement speed, block `+0x21c`,
     field `+0x5c` (`+0x60` while in stealth); 6.0 when there is no creature; 15.0 under a debug
     flag. The values mirror the server's run rate (3.1) (med).
   - `K` (`CSWCCreature::GetAcceleration` `0x00610590`): the same block's `+0x58`, or 15.0 in
     stealth. When `vmax < 1.8`, `K` is scaled by `vmax / 1.8`. (high for the code, low for where
     `+0x58` comes from)
7. **Moving**: the displacement is `|Δp|` taken **along the creature's facing** (not along `v`).
   The client moves only when the speed |v| is above 1.0 m/s and finite:
   `CSWCCreature::MoveDirect(pos + facing·|Δp|)` (1.3). If that fails, the remembered facing is
   cleared.
8. In combat mode (camera mode 6) and with a hostile target, a creature that is not moving turns
   to face its target at up to 900 °/s (`0x007a25f4`). (med)
9. The speed |v| is stored on the client creature (`SetMoveSpeed` `0x0060f0d0`, `+0x3b0`); it
   drives the walk/run animation blend and the followers' speed (section 6).

Defaults that matter, from camerastyle.2da: DEFAULT 1500/150 °/s, EbonHawk 500/500, OutDoor and
Manaan 480/150, Combat 800/200.

### 1.3 Moving the client creature: `CSWCCreature::MoveDirect` (`0x00614b90`)

The target point is tested with `CSWCArea::TestWalkLine` (`0x00604c40`), which forwards to the
server area's straight-walk test (4.4) with the creature's personal-space radius (PERSPACE) and
height. Up to **six** attempts: (high for the loop, med for the geometry)

- result 1: the move is accepted;
- −1 / −2 (walkmesh edge or object): **slide**. The test reports the edge it hit. The target is
  projected onto that edge's line (from whichever end is nearer), or, at a vertex, pushed 0.06 m
  sideways along the edge direction; a reversed slide on the second and later tries (the new
  direction pointing back) stops the loop with a 0.03 m nudge;
- −3 (a creature): the blocker may be pushed aside (`PushCreatureAside`, 4.9) and the test is
  repeated; if still blocked and the creature's own spot is not safe, it is moved to the nearest
  safe point within 1.0 m.

On success the client creature takes the new position, the server is told through
`CServerExoApp::MoveCreatureFromClient` (`0x004aead0` → `0x004b6cc0`), which runs the trigger
bookkeeping for the segment (section 5), and through `SetCreaturePositionFromClient`
(`0x004aeaa0` → `0x004b1cb0`: server `SetPosition` and `SetOrientation`). The client party table
records the leader's new position (the followers' trail, section 6). (high)

### 1.4 Direct input versus queued actions

When the leader is busy (`CSWCCreature::GetIsBusy` `0x0060f0f0`: a non-empty server action
queue, or a busy animation), movement input is **ignored for 0.3 s** (`client+0x2a4` counts down
from 0.3). After that, if the controller's speed is above 0.25 the leader's actions are cancelled
(`CancelServerActions` `0x0063d470` → `CServerExoApp::CancelCreatureActions` `0x004aef40`:
`ClearAllActions(1)`, the combat round ended, the attack targets cleared), the action menu is
closed and direct control takes over; otherwise the wait is extended by 0.1 s. **In combat mode**
(2.1) a busy leader ignores movement input altogether, unless an option bit (`options+8` bit 4)
is set. (med)

### 1.5 Click-to-move, run/walk and messages

- **No click-to-move.** A left click in the world never moves the leader to a point: it selects
  an object or runs the current target's default action (7.4). The server still has the NWN
  handler for input minor 1 "move to point" (`HandlePlayerToServerInputMoveToPoint`
  `0x005235b0`; it queues MOVETOPOINT, see [actions.md](actions.md)), but no client code sends
  it. (high that no sender exists among the client's message writers; med for the conclusion)
- Likewise the input minor `0x1d` handler (queues DRIVEDIRECT, action `0x33`) has no PC client
  sender found; keyboard control goes through the direct calls of 1.3 instead. (med)
- Client → server messages start with `'p'`, major, minor (`SendPlayerToServerMessage`
  `0x00677410`). The input ones (major 6) that the PC client does send: 2 attack (`0x00677a90`),
  3 open/close door (`0x00677d70`, with 10021 open / 10022 close), 7, 8 talk (`0x00677ea0`),
  9, `0xb` use object (`0x00677d10`), `0xc` unlock (`0x00677de0`), `0x12` cast (`0x006776a0`),
  `0x21`, `0x24`. The server side is `CSWSMessage::HandlePlayerToServerInputMessage`
  (`0x005254c0`, cases listed in actions.md). (high for the ids, med for the meanings not listed
  in actions.md)

## 2. The camera

The in-game camera is one `CAurCamera` named "camera" at `CSWCModule+0x40`, created when the
client handles the module message (`CSWCModule::LoadFromMessage` `0x0063f660`), with near 0.1 and
far 10000 (high). It never moves itself: each frame the **controller** attached to it (`CAurObject`
`+0x188`, one at a time, `SetController` deletes the old one) sets its position and orientation.
Controllers derive from `CAurCameraController` (vtable `0x00743864`, 8 slots: 0 dtor,
2 `Update(dt)`, 3 `SetParameter(char*)` for console tweaks, 4 `GetType`); `CAurCamera::Update`
(`0x0045d220`) → `CAurObject::Update` (`0x00486670`) calls slot 2 during the client object
update, just before rendering. The options byte `CClientOptions+0x6d` records the camera mode.
(med)

### 2.1 Controllers and modes

| Mode (`options+0x6d`) | Type id | Class (vtable) | Constructor | Entered by | Conf. |
|---|---|---|---|---|---|
| 0 / 1 / 2 | — | legacy NWN modes | `0x00640700` / `0x00640a80` / `0x00640b90` | only script `SetCameraMode`, which no game script calls | med |
| 3 | `0x106a` | `CSWCChaseCamera` (`0x0075165c`) | `0x00639fc0`, from saved state `0x0063ad60` | default | high |
| 4 | `0x106d` | dialogue camera ([dialogue.md](dialogue.md); vtable `0x00756ae8`) | `0x006bb670` | conversations, `0x006412f0` | med |
| 5 | `0x106e` | `CSWCFreeLookCamera` (`0x0075167c`) | `0x0063a5d0`, `0x0063baf0` | Freelook key → `StartFreeLook` `0x006413c0` | high |
| 6 | `0x1070` | `CSWCCombatCamera` (`0x00757bdc`) | `0x006d12b0` | combat mode → `StartCombatCamera` `0x00641540` | high |
| 7 | `0x1071` | `CSWCFlyCamera` (`0x007515f4`), debug | `0x00638670` | Freelook key when the debug global `0x008338e8` is 1 | med |
| — | `0x106f` | `CSWCDeathCamera` (`0x0075169c`) | `0x0063bbd0` | whole party dead: `0x004b6da0` → `StartDeathCamera` `0x005f7200` | med |

Before a mode 4–7 controller is installed, `CSWCChaseCamera::SaveState` (`0x0063ba80`) stores the
target part, the style row, the has-CAMERAHOOK flag and the look-at height in `CSWCModule+0x10c`.
`CSWCModule::RestoreDefaultCamera` (`0x00641dc0`) rebuilds the chase camera (or free-look) from
that block, **or the combat camera while combat mode is on**. When the outgoing controller is a
framing camera the new chase camera starts at its last pose (`0x00637c20`) and converges back
behind the player. `CSWCModule::SyncCameraMode` (`0x006419a0`) runs every frame and rebuilds the
controller whenever `options+0x6d` differs from the module's current mode (`+0xc`). (med)

**Combat mode.** `CSWCCreature::SetCombatMode(b)` (`0x00610a10`) sets the client creature's
`+0x440` bit 0; for the controlled creature it calls `CClientExoAppInternal::SetCombatMode`
(`0x005f3a80`), which stores `client+0x320` and switches to the combat camera (on) or back
(off). The CancelCombat key (240) turns it off. While it is on, target cycling only offers
hostiles (7.3). (high)

### 2.2 camerastyle.2da and the ARE's CameraStyle

| Row | name | distance | pitch | height | speed | tiltup | tiltdown | tiltspeed | rotation | viewangle | maxturnrate | minturnrate | fl_tiltspeed | fl_rotatespeed | fl_lookup | fl_lookdown |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | DEFAULT | 3.2 | 83 | 0.45 | 20 | 0 | 0 | 30 | 180 | 55 | 1500 | 150 | 12 | 25 | 15 | 20 |
| 1 | EbonHawk | 1.3 | 78 | 0.15 | 20 | 0 | 0 | 30 | 280 | 60 | 500 | 500 | 12 | 25 | 30 | 30 |
| 2 | OutDoor | 6.25 | 80 | 2 | 20 | 0 | 0 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 3 | Manaan | 4.25 | 60 | 1 | 20 | 0 | 0 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 4 | E3test | 3 | 80 | 0.8 | 20 | 0 | 0 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 5 | Highview | 100 | 80 | 100 | 20 | 0 | 0 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 6 | Chess | 10 | 80 | 4 | 20 | 0 | 0 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 7 | QAVis | 60 | 60 | 30 | 20 | 10 | 10 | 30 | 110 | 55 | 480 | 150 | 12 | 25 | 30 | 30 |
| 8 | Combat | 3.6 | 76 | 0.55 | 20 | 0 | 0 | 30 | 90 | 55 | 800 | 200 | 12 | 25 | 15 | 20 |

`CSWSArea::LoadAreaHeader` reads the ARE's `CameraStyle` into `CSWSArea+0xb8`; the area message
carries it to `CSWCArea+0xb8` (`CSWCArea::LoadArea` `0x00607610`), and the chase camera and the
player control read the row from there. The table is cached at `C2DAs+0x74`
(`C2DAs::LoadCameraStyle` `0x005c2540`). The combat camera always uses **row 8**. (high)

| Column | Reader | Stored at | Notes |
|---|---|---|---|
| DISTANCE, SPEED, PITCH, HEIGHT, TILTSPEED | `CSWCChaseCamera::LoadCameraStyle` `0x00638070` | chase `+0x110`, `+0x114`, `+0x11c`, `+0x120`, `+0x134` | SPEED is stored only (med) |
| TILTUP, TILTDOWN, ROTATION | same | globals `0x007a2420`, `0x007a2424`, `0x007a2428` | tilt limits used; ROTATION unused by the chase camera (med) |
| VIEWANGLE | same | `CAurCamera::SetFieldOfView` `0x0045bee0` (vertical FOV, degrees) | 0 becomes 55 (high) |
| FL_TiltSpeed, FL_RotateSpeed, FL_LOOKUP, FL_LOOKDOWN | `CSWCFreeLookCamera::LoadCameraStyle` `0x006383c0` | free-look `+0x2c`, `+0x28`, `+0x30`, `+0x34` | (high) |
| MaxTurnRate, MinTurnRate | `CSWCPlayerControl::LoadSettings` `0x006793c0` | control `+0x3c`, `+0x38` | player turning, 1.2 (high) |
| DISTANCE, HEIGHT, PITCH, ROTATION, SPEED, VIEWANGLE (row 8) | `CSWCCombatCamera` constructor `0x006d12b0` | combat `+0x38`, `+0x40`, `+0x30`, `+0x34`, `+0x3c`, FOV | (high) |

`LoadCameraStyle` reloads only when the row changes; without the 2DA the chase camera falls back
to distance 6.25, speed 20, pitch 80, height 3.5. (high)

### 2.3 The chase camera (mode 3)

**Look-at point.** `CSWCModule::SetCameraTarget` (`0x0063f9d0`) aims the camera at the controlled
creature; switching characters retargets it and keeps the current yaw and pitch (med). The
tracked part is the creature model's `CAMERAHOOK` node if it has one, otherwise the model
(`0x0060efe0`). The height offset (`+0x6c`) is the target height plus appearance.2da
`CameraHeightOffset` (`0x0060f010`); the target height is the `CAMERAHOOK` height (low) or the
`HEAD_G` node's height above the model origin (`0x006973b0`). Look-at = tracked part position +
(0, 0, `+0x6c`) (`GetLookAtPoint` `0x005f5180`); the 3D sound listener sits on the same point.

**One update** (`CSWCChaseCamera::Update` `0x0063bcb0`):

1. (Dormant) FOV compensation of the distance when `+0x84` is set; nothing sets it. (med)
2. `RefreshOptions` (`0x00638f60`): Keyboard Camera DPS, Acceleration, Deceleration into the
   embedded rate integrator at `+0xb4`. (high)
3. Without a target, stop. On the first frame `SnapBehindTarget` (`0x00638fe0`) takes the yaw from
   the target's facing and the pitch from the style. (med)
4. `UpdateYaw` (`0x006391a0`, below) gives the new orientation at `+0x28`.
5. **Position** (`ComputeFollowPosition` `0x006398f0`): with `h` the current horizontal distance
   to the look-at and `d` = DISTANCE, `h' = d + 0.5·(h − d)` (the error halves every frame —
   frame-rate dependent, constant `0x007a243c`); θ' = the yaw of `+0x28` (snapped normally; while
   auto-turning, eased by Δ·rate·dt); camera.xy = look.xy − h'·(−sin θ', cos θ'), camera.z =
   look.z + HEIGHT. Headings follow `atan2(−x, y)` in degrees (`0x004aa0f0`): yaw 0 faces +y.
   (high for the formula, med for the snap/ease split)
6. **Collision** (`ResolveCollision` `0x0063b050`, below).
7. **Orientation** (`ComputeOrientation` `0x00639760`): yaw = heading from the camera to the
   tracked part + shake offset `+0x90`, so the camera always looks at the player. The tilt input
   (`+0x104`, divided by 75 above magnitude 1, i.e. a mouse value) moves the target pitch at
   TILTSPEED·input·dt within [PITCH − TILTDOWN, PITCH + TILTUP]; every row but QAVis has zero tilt,
   so **the pitch is fixed at PITCH**. Output pitch = target − (target − current)·dt·0.5 + shake
   `+0x94`. Quaternion = Rz(yaw)·Rx(pitch)·Ry(roll) in degrees (`0x004acac0`); pitch 0 looks
   straight down, 90 is level (DEFAULT's 83 looks 7° below the horizon). (high)

**Yaw input** (`UpdateYaw`):

- *Mouse look* is active while Lookabout (Ctrl or the right mouse button) is held, XOR the "Mouse
  Look" option (`options+8` bit 2). The cursor is hidden and restored on release. Yaw changes by
  the frame's mouse value in degrees: dx·sens·(−1), dx = clamp(−mickeys/100, −1, 1)
  (`CExoInputInternal::UpdateMouseAxes` `0x005e0110`), sens = 10 + 0.45·slider (`options+0x50`,
  0..100). (high)
- *Keys* (event 284, A/D) give an input u in −1..1 to the rate integrator (`CRateIntegrator`
  `0x006d0b20`/`0x006d1190`): with input `rate' = Acc·u − (Acc/DPS)·rate`, without
  `rate' = −(Dec/DPS)·rate`; RK4, dt clamped to 0.2 s; the angle integrated over the frame
  rotates the camera about +z. Defaults (`0x0061d9e0`, ini "Keyboard Camera DPS/Acceleration/
  Deceleration"): DPS 200 °/s, Acc 500 °/s², Dec 2000 °/s², so the rate reaches 200·u °/s with a
  0.4 s time constant and stops with 0.1 s. (high for the law, med for the state layout)
- *Screen edge*: with no key input, no mouse look and not in free-look, a cursor within
  max(2, ⌊width·0.001⌋) px of the left or right edge acts like the rotate keys at full input
  (`UpdateCameraInput` `0x005f5e10`). (high)
- *Auto-turn toward a target*: `+0x80` holds an object id set by `TurnTowardObject`
  (`0x00639c30`) when target cycling selects something (`0x005fb050` → `0x005f9c60`). Without
  manual input the desired yaw becomes the heading from the player to the object offset by ±15°
  (the object beside the player); the eased rate `+0x9c` rises 3/s while the camera is more than
  1 m from its ideal spot and falls 5/s otherwise, within [2.5, 7.5]. It stops once the object is
  near the centre (low on the test) and any manual yaw input clears it. (med)
- **The camera never swings behind a moving player by itself**: only input, target auto-turn or a
  controller change moves its yaw. (med)

**Collision** (one pass):

1. *Creatures* (server side): `CSWSArea::ClipCameraSegmentToCreatures` (`0x004bf650`) shortens the
   segment look-at L → camera C. It takes creatures within ±3 m of the segment's xy box from the
   area's x-sorted creature array (`+0x190`/`+0x194`), skips any whose PERSPACE circle contains L
   (the player), and pulls C to the nearer intersection with each creature's **CAMERASPACE**
   circle (appearance.2da, default CREPERSPACE; path state `+0x10`), minus 1 mm; z is
   interpolated, minus 0.01. (high)
2. *Geometry* (client side): side = normalize(cross(Z, C − L))·0.35 (`0x007a241c`); four rays from
   L to C ± side and C ± 0.35 z go through `CAurScene::RayTest` (`0x00456b60`): the rooms' AABB
   meshes first (the same geometry as the WOKs), then scene objects; the player's own model is
   excluded and every material except 30 (Trigger) blocks. (med)
3. If a ray hits, p = the largest distance from a hit to its ray's end; C −= normalize(C − L)·p
   and C += up·(0.35 + 0.15)·p/|C − L| (`up` = the target's +z): the camera moves in and rises a
   little. (high)

Notes on this (read from `ResolveCollision` `0x0063b050` and `ClipCameraSegmentToCreatures` `0x004bf650`
again): the loop in `ResolveCollision` runs once (its counter starts at 1), so the four rays are cast once
from the camera `ComputeFollowPosition` gave; the hit nearest the ray's end does not matter, the stretch
left past the hit does, and the camera ends *on* the surface of the worst ray. The creature clip only acts
when the camera is inside a creature's CAMERASPACE circle (the pre-test) *and* the segment crosses that
circle twice (the call that finds the crossings returns 2 only then); a segment that ends inside a circle
has one crossing, so as decompiled the clip never fires (low: a flag test in the compare could hide it).
The up vector for the lift is the target's orientation applied to +z (the quaternion is stored w first).

There is **no zoom**: the mouse wheel goes to the GUI; the zoom input `0x006401d0` belongs to the
legacy modes. (med)

### 2.4 The combat camera (mode 6)

`CSWCCombatCamera` (`0x006d12b0`, update `0x006d1fc0`) reads camerastyle row 8 (distance 3.6,
pitch 76, height 0.55, rotation 90, view angle 55) and the keyboard camera options, and frames
the controlled creature together with its current target (`client+0x2b4`; the leader alone
without one). It handles mouse look like the chase camera. The framing helpers
(`0x006d14e0`, `0x006d18e0`, `0x006d16f0`, `0x006d1760`) were not read. (high for the inputs,
low for the framing)

### 2.5 Free-look (mode 5, input class ICFreeLook)

- **Enter**: Freelook (Caps Lock), only when the leader's action queue is empty.
  `StartFreeLook` (`0x006413c0`) saves the chase state, turns the creature to face away from the
  camera, installs the controller (which also starts the appearance's `FreeLookEffect` screen
  effect), sets input class 4 and hides the HUD (`g_bMainInterfaceVisible` `0x007a2288` = 0).
  (high)
- **Leave** (`RestoreDefaultCamera`, input class 0): the Freelook key again, a GUI key (209–216)
  or Pause (241), or the leader getting a queued action. (med)
- **Update** (`0x00639d00`): the eye is the model node `FreeLookHook`, else `CameraHook`, else
  root + 2 m. Yaw is the creature's own facing: mouse x turns the creature (client and server),
  the A/D keys feed the control's turn integrator (200 °/s, 500 °/s²). Pitch: mouse y adds
  dt·FL_TiltSpeed·v, keys go through a rate integrator; clamped to [−FL_LOOKDOWN, FL_LOOKUP];
  the orientation uses pitch + 90. (high for the pitch, med for the yaw formula)

### 2.6 Death camera, shake, script commands

- **Death camera** (`0x0063a810`): orbits the dead leader at 30 °/s, eases yaw (×0.5 per frame),
  pitch toward 90 (×0.01) and distance toward 3.0, and keeps 0.25 m short of geometry. (med)
- **Shake** (`UpdateCameraShake` `0x00641760`, started from visualeffects.2da `shaketype` 2 via
  `0x006416f0`): yaw/pitch offsets written into the current controller (low on the waveform).
- Script **SetCameraFacing** (routine 45, `0x00542530`) queues action `0x16`
  (`AIActionSetCameraFacing` `0x005137c0`) which sends message major `0x10` minor 1; the client
  (`0x0064b8e0`) formats `"yaw %f"` / `"dist %f"` / `"pitch %f"` camera commands, but no chase
  camera handler for them was found (low). **SetCameraMode** (504) sets `options+0x6d` (legacy
  modes). Neither is used by any game script. **SetDialogPlaceableCamera** (461) belongs to
  dialogue.md.

## 3. Creature movement

### 3.1 Speeds and sizes

**Rates.** `CSWSCreatureStats::SetMovementRate(n)` (`0x005a5680`) stores the row at stats
`+0x194` and copies creaturespeed.2da `WALKRATE` to stats `+0x19c` and `RUNRATE` to `+0x198`.
Row 7 ("Default") is resolved through appearance.2da `MOVERATE` (a string like `NORM`) matched
case-insensitively against creaturespeed's `2DAName`. The stats reader takes the UTC/save BYTE
`MovementRate`, else the INT `WalkRate`. (high)

| creaturespeed row | label | 2daname | walkrate | runrate |
|---|---|---|---|---|
| 0 | PC_Movement | PLAYER | 3.20 | 5.40 |
| 1 | Immobile | NOMOVE | 0.00 | 0.00 |
| 2 | Very_Slow | VSLOW | 0.75 | 1.50 |
| 3 | Slow | SLOW | 1.25 | 2.50 |
| 4 | Normal | NORM | 1.70 | 5.40 |
| 5 | Fast | FAST | 2.00 | 6.00 |
| 6 | Very_Fast | VFAST | 2.50 | 6.50 |
| 7 | Default | DEFAULT | (appearance MOVERATE) | |
| 8–11 | DM_Fast, HUGE, GIANT, Wee_Folk | | 5.5 / 5 / 5 / 0.7 | 11 / 10 / 10 / 1.4 |

The rates actually used (`GetWalkRate` `0x004f1b20`, `GetRunRate` `0x004f1be0`), in mm/s:

- walk = clamp(`+0xa08`, 0.125, 1.5) · WALKRATE · 1000, and 0 when below 100 (an immobile
  creature never moves); in stealth mode (`+0x9fc` bit 0) the client creature's stealth speed is
  used instead (`+0x21c` block `+0x60`; nothing found writes it, so its value is open: we walk at the
  walk rate);
- run = clamp(`+0xa08`, 0.125, 1.5) · RUNRATE · 1000, at least 1000.

`+0xa08` is the movement speed multiplier that the speed effects change (rules.md). (high)

**Sizes.** `CSWSCreature::UpdatePathfindSizes` (`0x004ed6e0`) copies the appearance row
(`+0xa60`) into the path state: (high)

| Path state | appearance.2da | Default | Used for |
|---|---|---|---|
| `+0x04` | PERSPACE | 0.6 | the creature's radius for walkmesh and creature tests, the grid cell size |
| `+0x08` | CREPERSPACE | PERSPACE | radius against other creatures (pushing, detours, chasing range) |
| `+0x10` | CAMERASPACE | CREPERSPACE | camera collision |
| `+0x14` | HEIGHT | 1.0 | swept height in walk tests |
| `+0x18` | hitdist | 0.5 | combat (combat.md) |

Typical humanoid rows: PERSPACE 0.35, CREPERSPACE 0.36–0.4, HEIGHT 1–1.6.

### 3.2 Who moves when

The planned path is walked by one of two functions (high):

- `CSWSCreature::UpdateMovement` (`0x0051d9c0`) for creatures a client knows (`CSWSObject+0x1f8`
  set by the server's visibility update). `CServerAIMaster::UpdateState` calls it **every frame**
  for every such creature whose head action is MOVETOPOINT or FOLLOWLEADER, or whose movement state
  (`+0xa8c`) is 4–6, outside the AI time budget; a return of 2 sets `+0xa8c = 1`.
  AIActionMoveToPoint itself calls it once when the path is ready.
- `CSWSCreature::StepMovementUnseen` (`0x0051bb10`), from AIActionMoveToPoint (inside the budgeted
  `RunActions`) for creatures no client knows. Same physics, coarser timing.

`+0xa8c`, the movement state: −1 re-plan, 0 walking a path, 1 idle/done, 2 move queued (planning),
3 following the leader (section 6), 4–6 forced motion (3.7). (med)

**`UpdateMovement`, one frame**, in order (high unless marked):

1. Nothing for a creature that is dead, dying or in an incapacitating state, or in state 1.
2. Frame delta: world time now minus the creature's last update (`+0xb0/+0xb4`), in ms, at `+0xd0`.
3. State 3 → `UpdateFollowLeader`; states 4–6 → `UpdateForcedMotion`; return.
4. **Timeout**: if the move has a deadline (path state `+0x26c`, world time `+0x270/+0x274`) and it
   has passed, the creature **jumps** to the destination, the MOVETOPOINT node is removed, the
   idle animation set; done (Force* moves, see actions.md).
5. **Speed**: in stealth the walk rate (entering stealth applies a walk-only LIMIT_MOVEMENT_SPEED
   effect, +0x8e8 = 1, which clears the run flag when the move starts: `0x004f6d70`); else the run
   rate if the action's run flag (`+0xa98`) is set, walk otherwise; the walk (10002) or run (10004) animation is (re)set when the creature has
   a client twin (`+0x9f0` bit 1). A party member following the leader overrides it (6.2).
6. **Speed factor** `f` (`GetSpeedFactor` `0x00512f10`), 3.3. Distance this frame:
   `s = dt_ms · (f + f_prev) · speed_mm/s · 0.5 · 10⁻⁶` m (trapezoidal), `f_prev = f` stored at
   `+0xb8`. A debug flag (`0x00832814`) multiplies `s` by 15.
7. `StepAlongPath(s)` (3.4) gives the new position and direction. If the new z differs from the old
   by 0.001 or more, the step is redone with `s` scaled by the horizontal part of the slope
   direction, so the creature covers `s` along the slope, not across the map.
8. Notify an item or placeable the creature is heading to (`0x004eded0`).
9. Volumes: `UpdateVolumesAfterMove(old, new)` (section 5).
10. `SetPosition`, the client party table's copy for party members, `SetOrientation` to the step
    direction (z = 0, normalised). **NPCs turn instantly** to their walking direction on the
    server. (high; whether the client smooths the visible turn was not checked)
11. For the controlled creature: the client party table and route are updated (`0x00636a30`) and
    the action menu closed (`0x0060b920`).
12. **Arrival / interaction**: if the path's target object (path state `+0x30`) is a trigger that
    is not a trap and the creature is in range, script event 30 CLICKED is sent to it; if it is an
    area-transition door (LinkedToFlags 1 or 2, `CSWSDoor::GetIsAreaTransition` `0x005890d0`) in
    range: open (`+0x2cc`) → CLICKED, closed → PATH_BLOCKED (31) to the creature (its OnBlocked
    script opens it); a creature target that moved 2 m or more since planning → re-plan
    (`+0xa8c = −1`). When `StepAlongPath` reported arrival: path cleared, `+0xa8c = 1`, the
    MOVETOPOINT node removed, idle animation, return 2.

### 3.3 Acceleration and braking

`GetSpeedFactor(speed, dt_ms)` (`0x00512f10`), with `R` the remaining path length
(`GetRemainingPathLength` `0x005111c0`: current position to the next waypoint, then waypoint to
waypoint) and `D = 0.0005 · speed_mm/s` (the distance covered in 0.5 s at full speed): (high)

```
f = 1
if R < D:                         // braking zone
    f = (R/D < 0.01) ? 0.1 : sqrt(R / D)
    f = f - dt_ms / 1000
if f_prev < 1:                    // accelerating
    f = min(f, f_prev + dt_ms / 1000)
f = max(f, 0.1)
```

So a creature reaches full speed 1 s after starting (from the 0.1 it ended its last move with) and
slows with the square root of the remaining distance over the last half second's worth of path.
`f_prev` is never reset between moves (med).

### 3.4 Walking the waypoints: `StepAlongPath` (`0x00516630`)

The path state holds the final waypoint list as x,y floats (`+0x8c` float count, `+0x90` data) and
the index of the next waypoint (`+0x9c`, in floats). For a distance `s`: (high unless marked)

1. With the "stop when in sight" flag (MOVETOPOINT flag bit 10, path state `+0x240`) and a target
   object: once the creature is within the range (`+0x68`) of the last waypoint and both a
   line-of-sight ray (`CSWSArea::ClearLineOfSight` `0x0050c330`, eyes 1.5 m above the walkmesh)
   and an object test are clear, it stops there (arrived).
2. Otherwise, waypoint by waypoint: the segment from the current point toward the next waypoint
   is tested with `CheckStepCollision` (4.9). Not blocked: if the waypoint is farther than the
   remaining `s`, move `s` toward it and stop; else move onto it, subtract its distance, advance
   `+0x9c` by 2 and continue. The z of every point is the walkmesh height under it
   (`CSWSArea::ComputeHeight` `0x004bc380`). The volumes each sub-segment crosses are collected
   (`GetVolumesCrossed`) for the trigger check of section 5.
3. Blocked: a counter (`+0x268`, reset when the move is planned) counts blocked steps. At the 6th
   the creature gives up: path cleared, idle animation, arrived (status 1). Before that: if the blocker is the move's
   own target object, that counts as arrival; if it is a creature, the avoidance helper tries a
   detour (4.9); if no detour exists the creature stops, and the player's own creature shows the
   feedback string 47859 "The path to your target is blocked."
4. **Back-pedalling**: on a single-segment path (two waypoints) in a walk animation, when the goal
   is less than 2 m away and more than 135° behind the facing (dot < −0.707), the creature keeps
   its facing and plays animation 10003 (walk backwards) instead of turning round. (high for the
   test, med for the animation's meaning)

### 3.5 The walkmesh queries

The server area keeps one `CSWSRoom` per LYT room (array at area `+0x230`, 0x4c bytes each, count
`+0x22c`; LYT position at `+4`, name at `+0x20`, "no walkmesh" flag `+0x38`, the walkmesh object
`CSWWalkMesh` at `+0x3c`, loaded from `<room>.wok` by `CSWSRoom::LoadWalkmesh` `0x00579520` →
`CSWWalkMesh::Load` `0x00596670`, which also loads placeable PWKs and door DWKs). (high)

| Query | Function | What it does | Conf. |
|---|---|---|---|
| room at a point | `CSWSArea::GetRoomAtPoint` `0x004bb600` | first room whose walkmesh has a face under (x, y): rooms are tried **in LYT order** | high |
| face under a point | `CSWWalkMesh::FindFaceUnderPoint` `0x00581530` | vertical query through the AABB tree; when the point lands exactly on an edge, retried with x and y nudged by 0.001·(1,1)/√2 | med |
| height | `CSWSArea::ComputeHeight` `0x004bc380` | plane of the face under (x, y) | high |
| walkable | `CSWSArea::IsWalkablePoint` `0x00506400` | surfacemat.2da `Walk` of the face's material (table at `C2DAs+0x14`, material ids at walkmesh `+0x64`) | high |
| face normal | `CSWSRoom::GetFaceNormal` `0x00579840` | stored normal, (0,0,1) for no face | high |
| perimeter transition | `CSWWalkMesh::GetPerimeterTransition` `0x00581150` | the BWM perimeter entry's room index (`+0x8c` table) | high |

**Crossing rooms.** The straight-walk test (`TestWalkLine`, 4.4) follows a segment inside the
current room's walkmesh through face adjacency (`CSWWalkMesh::WalkSegment` `0x00584220`) until it
ends or leaves the floor through a perimeter edge. At that edge the BWM transition gives the next
room: none (−1) or a room without a walkmesh (`+0x38`) means blocked; otherwise the walk continues
in that room from the exit point. Movement itself does not track faces: each step asks for the
room and face under the new point. (high)

### 3.6 Animations

Movement picks server-side animation ids; the client blends them. `CSWCCreature::UpdateMovementAnimation`
`0x00611f50` sets the walk or run cycle's playback rate to `S x A / D x f` (high for the shape, med for the
details): S the creature's walk or run speed, A the length of the cycle that is playing, D the appearance's
`WALKDIST` or `RUNDIST` (the **metres one cycle covers**, scaled by 1000 against the millisecond length in the
code) and f the acceleration and braking factor of 3.3 (the client recomputes it, `0x0060bf60`; floor 0.1). The
cycle's own pace is D / A; the data agrees: the humanoid run cycle is 0.733 s and RUNDIST 3.96 m (5.4 m/s, the
Normal run rate), the walk 1.067 s and WALKDIST 1.813 m (1.7 m/s), and the stance foot of both moves back at
about that speed. A cycle that replaces another starts at the same fraction of its length. (Not modelled: that, and a run
case that reads WALKDIST while the animation is in its first half second.)

| Id | Use |
|---|---|
| 10000 | stand (idle); 10001 when in combat (`GetIdleAnimation` `0x004f0f90`) |
| 10002 | walk |
| 10003 | walk backwards (short reverse moves, 3.4) |
| 10004 | run |
| 10093, 10133 | other walk variants (`IsWalkAnimation` `0x004cc1c0`) |

### 3.7 Forced motion (states 4–6)

`UpdateForcedMotion` (`0x0051c0d0`) slides the creature along a two-point path at a fixed speed —
25 m/s in state 4, otherwise the path length × 3.03 per second (the whole slide in 0.33 s) —
with a vertical arc kept in `+0xa90`/`+0xa94`, running the volume checks. Set by effect code
(`0x004de0a0`, `0x004e3800`), presumably Force Jump and knock-back (rules.md). (med for the motion,
low for the uses)

## 4. Pathfinding

### 4.1 The path state (`CPathfindInformation`, 0x278 bytes at creature `+0x340`)

Constructor `0x005d0ce0` (the area also builds one). Resets: `Clear` `0x005d0ec0` (everything,
used by `ClearAllActions` and at arrival), `ResetPath` `0x005d0e70`, `ResetSearch` `0x005d0e00`,
`ResetGridSearch` `0x005cefa0`, `ResetPathPoints` `0x005cf060`. Fields (high unless marked):

| Offset | Meaning |
|---|---|
| `+0x00` | flag bit 1 of the move ("don't fall back to a partial path", med) |
| `+0x04 .. +0x18` | sizes (3.1) |
| `+0x28` | the byte parameter 7 of MOVETOPOINT (low) |
| `+0x2c` | the owner creature id |
| `+0x30` | target object of the move (`OBJECT_INVALID` for a point) |
| `+0x38` | the creature's current attack target (bigger interaction range) |
| `+0x3c` | planner call counter (> 100 = give up) |
| `+0x58` | "new request" flag |
| `+0x5c..+0x64`, `+0x70` | goal x, y, z and area |
| `+0x68` | arrival range (stop this far from the goal) |
| `+0x6c` | grid goal radius in cells (low) |
| `+0x74..+0x7c`, `+0x80` | start x, y, z and area |
| `+0x84` | the search runs goal-to-start (reversed) |
| `+0x88` | search finished |
| `+0x8c` / `+0x90` | final waypoints: float count / x,y floats |
| `+0x94` / `+0x98` | the raw route before straightening |
| `+0x9c` | next waypoint index (floats) |
| `+0x194` | plan with the grid only (set when the creature has an attack target, `+0x50c`, and the goal is within 5 m; also by a byte of the move message) (med) |
| `+0x198` | flag bit 3 of the move: binary-search the straight line (4.3) |
| `+0x1a4` / `+0x1a8` | nearest PTH points to start / goal |
| `+0x1ac` / `+0x1b0` | PTH node route / count |
| `+0x1e0` | PTH planner state (4.5) |
| `+0x240` | flag bit 10: stop when the target is in sight (3.4) |
| `+0x244` | avoidance side (0/1) |
| `+0x254`, `+0x258..+0x260` | the creature currently being avoided and its position |
| `+0x264` | blocker passed to `k_def_pathfail01` |
| `+0x268` | consecutive blocked steps |
| `+0x26c..+0x274` | move deadline (has one, world day, ms) |

### 4.2 The request

`AIActionMoveToPoint` (`0x0051f4f0`, behaviour in actions.md) fills the goal and start, and when
the goal changed by 0.1 m or more marks a new request, then calls
**`CSWSModule::DoPathfinding(info, 1000)`** (`0x004c6f70`) every frame until it returns 2 (path
ready) or 3 (failed); 1 means "still working, ask again next frame". The time slice is
`g_nPathfindTimeSliceUs` = 1000 µs (`0x00832824`, set by `0x0073b140`). A new request restarts
the search state. `ComputePath` (`0x004c6e20`) builds the area list (KOTOR modules have one area,
so the inter-area part, `0x004c6bd0`, never matters) and calls `PlotAreaPath`. (high)

### 4.3 `CSWSModule::PlotAreaPath` (`0x004c3260`)

All planning is 2D (x, y); z always comes from the walkmesh. (high)

1. Count the call; after 100 calls without a result the request fails.
2. **Stop short**: with an arrival range r > 0.001, the goal is moved toward the start by r (to the
   start if it is closer than r).
3. **Straight line** (first call only, cached): `TestWalkLine(start, goal, PERSPACE, HEIGHT,
   creatures = 1)`. Clear (1) → the path is the two points; done.
4. With flag bit 3 (`+0x198`; random walk and flee moves), a blocked line is shortened by
   bisection (step 0.5, halving to 0.005 of the length) to the farthest clear point, which becomes
   the goal.
5. Otherwise a planner, whatever blocked the line (0, −1, −2 or −3): the grid planner (4.6) when
   `+0x194` is set; else **the PTH planner if the area has path points** (`CSWSArea+0x238` > 0,
   4.5), else the grid planner. **A creature at AI level 0** (the lowest, `+0x78`; far from every
   player) gets no planner at all: the request fails and goes to step 6. (med)
6. **Fallback**: if planning failed and flag bit 1 is clear, the goal becomes the farthest point
   along the straight line that a walk test without creatures (`creatures = 0`) reaches
   (bisection again); the path is the two points.
7. A reversed search is turned round (`SwapStartAndGoal`, the point list reversed).

### 4.4 The straight-walk test: `CSWSArea::TestWalkLine` (`0x004bcb70`)

`(from, to, &radius, height, bCheckCreatures, out)` → (high for the codes, med for the
internals):

| Result | Meaning |
|---|---|
| 1 | clear |
| 0 | left the floor into no room or a disabled room |
| −1 | the walkmesh blocks (a perimeter edge, or non-walkable geometry within `radius` of the line between the segment's z range −0.1 and +`height`+0.1, `CSWWalkMesh::CheckSegmentClearance` `0x005972b0`) |
| −2 | a placeable's PWK or a door's DWK is in the way (`TestSegmentAgainstObjects` `0x00506650`, swept 1000 m tall) |
| −3 | a creature's circle is in the way (`TestSegmentAgainstCreatures` `0x004bc590`; only when `bCheckCreatures`, and only for creatures other than the one the request ignores) |

It walks room by room as described in 3.5, then checks objects and creatures. Many callers accept
−3 as "clear enough" (PTH legs, nearest path point).

### 4.5 The PTH planner: `CSWSArea::PlotPathPointRoute` (`0x004c2200`)

The area keeps the PTH as loaded by `LoadPathPoints` (`0x00508400`): count `+0x238`, points
`+0x23c` (16 bytes: x, y, connection count, first connection), connection count `+0x240`,
destinations `+0x244`. A small state machine at path state `+0x1e0`, each state ending the call
when the time slice is used up: (high for the order, med for details)

1. **State 1, ends.** If the start or the goal is not a safe position (4.8), it is replaced by the
   nearest safe position within 2.0 m (and the creature is moved there if its own spot was
   unsafe). Then the nearest path point to each (`FindNearestPathPoint` `0x004bd770`): the closest
   point (2D) inside a square window of ±10 m, grown by 10 m up to 50 times, **whose straight walk
   from the position is clear** (1 or −3). The window search assumes the points are **sorted by x**
   (it stops at the first point beyond the window); all 94 non-empty PTH files in the game are.
   No point → fail. → state 4.
2. **State 4, graph search.** Same point → a one-node route. Otherwise a bounded depth-first
   search over the graph (`PathPointSearch` `0x004c0b30`, recursive), iterative deepening: the
   cost bound of the first pass is d/2 + 10 (d = start-to-goal distance) and grows by d/4 per
   pass while the time slice lasts; the bound is kept across frames as long as start and goal do
   not change. Edge cost = link length; a branch is cut when its cost so far plus the straight-line
   distance to the goal exceeds the bound, or when a transposition table already reached that
   point more cheaply. More than 4096 expansions in a pass → fail. Successors come from
   `GetPathPointSuccessors` (`0x004bdb00`). The route that came closest to the goal is recorded
   too (not seen used). → state 2.
3. **State 2, first leg.** Straight walk from the start to the first route point: clear → that
   segment; blocked → the grid planner (4.6) for this leg. If the leg fails, the first route point
   is dropped and the leg retried from the next; with one point left → fail. → state 3.
4. **State 3, last leg**, the same from the last route point to the goal (−3 accepted as clear);
   failing legs drop route points from the end. → state 5.
5. **State 5, assemble**: first leg + route points + last leg into one x,y list, then
   straightening (4.7). Done: state back to 1.

### 4.6 The grid planner: `CSWSArea::PlotGridRoute` (`0x004c1a00`)

A search on an implicit square grid in a frame centred on the **goal**: the u axis points toward
the start, the v axis perpendicular, cell size = PERSPACE (at least 0.1). Cells are integer pairs;
a cell's world point is goal + i·u + j·v. (med)

- `GridSearch` (`0x004c0930`) is a recursive depth-first search from the start cell (n cells out
  along u, n = the start's distance in cells) with an iterative bound: n + 4 in the first pass,
  growing by 2 per pass while below n + 36;
  a branch is cut when its cost plus the Manhattan distance |i| + |j| exceeds the bound, or by a
  transposition table; a pass expanding more than 64 nodes is marked as overflowing. Successors
  are the walkable neighbour cells (`GetGridSuccessors` `0x004bcee0`, which test the step with
  `TestWalkLine`). The goal is reached within `+0x6c` cells (low).
- The time budget is checked between passes; the best partial path (smallest |i| + |j|) is kept
  and used when the first pass ran 4× (or, unchanged, 1×) over budget. More than 40× or a full
  failure → fail.
- The cells are converted back to world points and straightened (4.7).

### 4.7 Straightening and corner rounding

Both planners finish the same way (`FinishPathPointRoute` `0x004c17a0` time-sliced at
`g_nPathSmoothTimeSliceUs` = 10 ms, `FinishGridRoute` `0x004c1670`): (med)

1. **Three string-pulling passes** (`StraightenRouteSliced` `0x004c04e0` / `StraightenRoute`
   `0x004c0180`): from the last kept point, find the farthest later point whose straight walk is
   clear (radius PERSPACE + 0.001, creatures checked), trying the farthest first and halving the
   look-ahead after a miss when it is 5 or more, else stepping back by one; skip the points in
   between. The passes are: (a) no pulling, but segments of length ≥ 5.0 (PTH) / ≥ 1.1 (grid) are
   cut into 1 m pieces; (b) pulling plus cutting at 1.1; (c) pulling only.
2. **Corner rounding** (`RoundPathCorners` `0x004bfe20`): at every interior point P with
   neighbours A and B, if the turn is sharper than cos = 0.9 (about 26°), find by bisection the
   largest cut c (start at half the shorter leg, halving the step until it is under 0.1 m) such
   that the straight walk between P + c·(A−P)/|A−P| and P + c·(B−P)/|B−P| is clear, and replace P
   by those two points (`CutCorner` `0x004be3a0`); then try to cut the two new corners once more.

Ours (`paths::route`): A* over the graph in place of the iterative-deepening search, skipping an edge
that an active placeable's walkmesh stands on (`walkmap::meets_placeable`; the original tests only its
first and last legs, with the grid planner as the detour, so a placeable created after the PTH was
authored, such as Calo Nord's landspeeders across the Tatooine camp road, would stop it too), then
string pulling over the route, each shortcut tested with the walkmesh and every placed mesh.

### 4.8 Safe positions

- `CSWSArea::IsPositionSafe(pos, info)` (`0x004be5e0`): the point (a ±0.01 m box, z ± 0.1) is on
  the floor of a room, and the creature standing there — radius PERSPACE, height HEIGHT — touches
  no wall of any room it overlaps, no placeable or door walkmesh and no other creature's circle.
  (med)
- `CSWSArea::FindNearestSafePosition(pos, radius, info, bNeedLine, out)` (`0x004be860`): the point
  itself (z from the walkmesh) if safe; otherwise square rings around it with half-size 1, 2, …
  up to `radius`, sampled every PERSPACE along each ring; the first safe sample wins, and with
  `bNeedLine` it must also be reachable by a clear straight walk from the original point.
  Radii used: 2.0 (planner ends), 1.0 (direct control), 3.0 (follow), 5.0 (pushing), 20.0
  (JumpToPoint, see actions.md). (med)

### 4.9 Obstacles and blocking

**Per step** (`CSWSCreature::CheckStepCollision` `0x00512fd0`), between the old and new point,
z range −0.1 .. +HEIGHT+0.1, radius PERSPACE, ignoring the move's own target object: (high)

1. Placeable PWKs and door DWKs (`TestSegmentAgainstObjects`; which DWK state a door uses was not
   read, low). A blocking door whose animation is
   10022 (closed) sends **script event 31 PATH_BLOCKED** to the moving creature with the door as
   caller: its **OnBlocked** script (`ScriptOnBlocked`, creature `+0x290`) runs, which for the
   default scripts opens the door. (high for the event, low for the scripts' contents)
2. Creature circles (`TestSegmentAgainstCreatures`). A blocking creature may be **pushed aside**
   (`PushCreatureAside` `0x004f6390`) when `CanPushCreature` (`0x004f62a0`) allows it: the mover
   is not the player's creature, the other is not hostile (reputation above 9), not a party member,
   has an empty action queue and is out of combat; and the global switch `0x007a1b34` is off. The
   other creature is placed off the mover's segment, at the closest point plus (both CREPERSPACE
   + 0.1) sideways, moved to the nearest safe point within 5 m; failing that, 4 m behind the
   mover. Then the step is retested. (med)

**A creature that stays in the way** (`CPathAvoidance::ResolveBlockingCreature` `0x005d0840`, via
`StepAlongPath`): (med)

- The blocker is hostile (reputation below 11): the mover runs the script **`k_def_pathfail01`**
  with the blocker remembered (path state `+0x264`) and stops.
- Otherwise a detour: a circle of radius (both CREPERSPACE + 0.2, `0x007a2274`) around the
  blocker. If the end of the path lies inside it, the goal is occupied: stop (result −2). Else arcs
  round both sides are built and tested; the side with fewer (or no) further blockers wins and is
  spliced into the waypoint list. Two creatures avoiding each other coordinate the side through
  `+0x244`: facing the same way, the other takes the opposite side value; facing each other, the
  same value (both step to their own right or left). If a detour meets another hostile creature,
  `k_def_pathfail01` runs; if no side works, `k_def_pathfail01` runs and the move stops.
- After six consecutive blocked steps the move ends anyway (3.4).

**No path at all**: the planner returns 3; AIActionMoveToPoint ends the action (a Force move
teleports the creature to the destination instead; actions.md). Paths are never re-planned because
the world changed, only when a chased target moves (3.2 step 12).

### 4.10 Where to stand to interact

`CSWSCreature::GetUseRange(target, &pos, &range)` (`0x004ee440`) gives the point a move to an
object aims for and the range that counts as arrived (base = own PERSPACE): creature → its
position, range = own CREPERSPACE (or `+0xc` for the attack target) + its CREPERSPACE + 0.3;
trigger → its position for transition triggers, else the nearest point of its outline and +0.5;
placeable → nearest use hook (PWK) with range 0.1 if reachable, else +0.75 (+5 more for some
placeables); door → nearest DWK use hook, z snapped, 0.1 if reachable, else +0.75; anything else →
its position. `GetIsInUseRange` (`0x004f6000`) adds 0.1 and tests transition triggers as "inside
the outline". Full details are in actions.md. (med)

## 5. Triggers and other volumes

### 5.1 Detection

Volumes are the area's triggers, areas of effect, encounters and transition doors, listed by id
at `CSWSArea+0x1a0` (count `+0x1a4`; ids of vanished objects are dropped when met). A creature
remembers the volumes it is inside at `+0x330` (count `+0x334`). **Detection runs on every
server-side movement step** — path walking, follow steps, forced motion and the client's direct
control (`MoveCreatureFromClient`) — not in `SetPosition`. Jumps (JumpToPoint, JumpToObject,
moving to another area) recompute the volumes at the destination only
(`CSWSCreature::UpdateVolumesAtPosition` `0x0051b940`: enter/exit, no crossing); a bare
`SetPosition` fires nothing. (high)

`CSWSCreature::UpdateVolumesAfterMove(old, new)` (`0x0051b7b0`):

1. **Inside now** (`CSWSArea::GetVolumesAtPoint` `0x004bf470`): for each volume, the inside test of
   its type:
   - trigger (`CSWSTrigger::InTrigger` `0x0058ce40`): **traps** (Type 2) are inside when within
     **1.0 m** (`g_fTrapTriggerRadius` `0x007a206c`) of the trigger's position, in 3D; all other
     triggers use an even-odd point-in-polygon test of (x, y) against the outline (vertices at
     `+0x288`, index list `+0x298`, count `+0x294`; z ignored);
   - area of effect: `0x00595450` (vfx_persistent shape); encounter: `0x00590090`; transition
     door: `0x005897d0`.
2. **Crossed** (`CSWSArea::GetVolumesCrossed` `0x004bf2c0`): volumes whose outline the segment
   old → new intersects (2D segment against every edge, `IntersectSegments2D` `0x0058f840`), so a
   fast creature cannot step over a thin trigger.
3. Only when the creature was or is now inside something: `SendVolumeEvents` (`0x00516020`) and the
   new list replaces the old.

`SendVolumeEvents` queues `SIGNAL_EVENT` (10) with a script event whose object 0 is the creature,
to run next frame: (high)

| Case | Event |
|---|---|
| was inside, not now | OBJECT_EXIT (13) — not for doors |
| inside now, not before | OBJECT_ENTER (12) for triggers, AoEs, encounters. A transition **door**: CLICKED (30) when the creature is the party leader, nothing for other party members |
| crossed, neither before nor now | OBJECT_ENTER then OBJECT_EXIT |
| crossed, inside before and now | OBJECT_EXIT then OBJECT_ENTER |

(The script-event route replaces the `ENTERED_TRIGGER`/`LEFT_TRIGGER` event ids 2/3 of
objects.md, which this code does not use. med)

### 5.2 What a trigger does

The trigger fields that matter (`CSWSTrigger::LoadTrigger` `0x0058da80`): `Type` 1 → `+0x2b4`
(area transition), 2 → `+0x2bc` (trap); `TrapType` `+0x2d4` (traps.2da row; its `TrapScript`
replaces an empty or "default" `OnTrapTriggered`), `TrapOneShot` `+0x2d0`, `LinkedTo` `+0x230`,
`LinkedToFlags` `+0x240`, `LinkedToModule` (`+0x238`, med), `HighlightHeight` `+0x2e0` (default
0.1), `LoadScreenID` `+0x308`, `Geometry` (`LoadGeometry` `0x0058d060`; the vertices are rotated
and moved with the trigger's GIT orientation and position). (high)

`CSWSTrigger::EventHandler` (`0x0058f140`) for the SIGNAL_EVENT script events: (high unless
marked)

- **OBJECT_ENTER (12)**: the entering object id goes to `+0x29c` (GetEnteringObject).
  - generic trigger: run `ScriptOnEnter` (`+0x24c`);
  - **trap**: `CSWSTrigger::OnTrapEntered` (`0x0058d570`): only creatures; unless the event's int 0
    ("force") is set, the creature sets it off when it is not immune to traps (immunity type 5), not of
    the trap's faction (`+0x2b8`) and its reputation toward the trap's creator (`+0x2e4`; the trap
    itself without one) is 10 or less (`0x0058d4a0`); detection is not checked. A creature carrying an
    item tagged KeyName disarms it instead (AutoRemoveKey takes the key; disarmer `+0x2a4`, OnDisarm,
    event 11). Otherwise: feedback 0x52 (1461 "You triggered a Mine!") to the victim, OnTrapTriggered
    (`+0x264`) at once as the trap (GetEnteringObject `+0x29c`), then ScriptOnEnter too; a one-shot
    trap gets event 11 at 0 ms (IsDestroyable, removed from the area, deleted) and the client delete
    reason 1 (`0x004ce8a0`: the mine plays `activate` and traps.2da ExplosionSound; reason 2,
    disarmed, plays `deactivate`). Script event 26 is not handled by triggers (only by trapped doors
    and placeables). (high)
  - **area transition** (movement side; the switch itself is gameloop.md's): if the area has no
    transition pending (`area+0x2c4`) and the creature is a player-party character: when the other
    party members are not gathered near the leader (`0x00635350` on the client party), the
    creature runs **`k_trg_transfail`**;
    otherwise a fade to black over 0.5 s starts (`0x0062abf0`), the area is marked "transition
    pending" with a counter, the game is paused (`0x004ae9a0(2)`) and a second OBJECT_ENTER is
    queued to the trigger **500 ms** later carrying the counter. When that one arrives with a
    matching counter and the creature is alive and well, the server starts the module transition
    with `LinkedToModule` and `LinkedTo` (`0x004aecc0` / `0x004aecd0` / `0x004aed30`); if it died
    meanwhile, the fade is undone. Walking into the polygon is therefore enough — no click needed.
    (med for the meaning of the pending flags)
- **OBJECT_EXIT (13)**: exiting id at `+0x2a0`, run `ScriptOnExit` (`+0x254`).
- **USER_DEFINED (11)**: number at `+0x2f8`, run `ScriptUserDefine` (`+0x25c`).
- **DISARM (24)**: run `OnDisarm` (`+0x26c`).
- **CLICKED (30)**: clicker at `+0x29c`, run `OnClick` (`+0x274`); for transition triggers an empty
  or "default" script becomes **`NW_G0_Transition`**, and the trigger's LoadScreenID is passed to
  the client. CLICKED comes from a move whose target was the trigger (3.2 step 12).
- TIMED_EVENT (1): runs the queued script situation (DelayCommand on the trigger); DESTROY (11
  event id): removes it.

A trigger's heartbeat comes from its own `AIUpdate` (`0x0058d760`), not read here.

### 5.3 Encounters and areas of effect

Both are volumes in the same list, with their own inside and crossing tests (`CSWSEncounter::
InArea` `0x00590090` / `SegmentCrosses` `0x0058ffd0`; `CSWSAreaOfEffectObject::InArea`
`0x00595450` / `SegmentCrosses` `0x005950c0`), so they receive the same OBJECT_ENTER/EXIT events;
what an encounter spawns on entry is the encounter's event handler (`0x00594220`), not covered
here. (med)

## 6. Party following

### 6.1 The pieces

- The **client party table** (`FUN_005ed8b0(client)`, also at `client+0x270`): up to three
  0x88-byte entries from `+0x24`, index 0 = the leader. Per member: `+0x00` id, `+0x04` follow
  state, `+0x18` the follow target point, `+0x24` formation slot, `+0x28` the leader's reference
  point, `+0x44` stuck counter, `+0x48` smoothed speed, `+0x4c` remembered facing, `+0x5c` last
  good position, `+0x68` reset flag, `+0x74` the leader position at the last re-plan. A route
  object at `+0x2dc` records the **leader's trail** (`0x00636a30` adds the leader's position and
  facing whenever it moves; `0x006350f0` hands out trail points; `0x00634cc0(slot)` the formation
  offset of a slot). (med for the table, low for individual fields)
- Each follower runs action **FOLLOWLEADER (0x3d)** (`AIActionFollowLeader` `0x00511130`): for a
  party member under player control (`+0xa88`) that is not the leader it sets `+0xa8c = 3` and
  stays running; the leader fails it at once. From then on `UpdateMovement` calls
  **`CSWSCreature::UpdateFollowLeader`** (`0x0051c360`) every frame. (high)

### 6.2 One follower step (`UpdateFollowLeader`)

1. Not in the party table → keep waiting; the leader → done.
2. **Speed** (mm/s): let L be the leader's client speed (`+0x3b0`, m/s) and Dl the squared
   distance the leader moved from the follower's reference point.
   - Dl ≥ 16 (4 m) or the follower is 10 m or more from its last good position: L·1000 if the
     leader moves faster than 0.1 m/s and that is more than the follower's run rate, else the
     follower's run rate.
   - Otherwise, leader moving: L·1000. Leader standing: the run rate (×0.6, `0x007a22f4`, when Dl
     ≥ 4), or 0.9·walk rate capped by the smoothed speed when the follower is still settling.
   - Then by the squared distance d² to its target: d² < 1 → ×0.9, 1 ≤ d² < 225 → ×1.2,
     d² ≥ 225 (15 m) → ×1.5 (catch-up running).
   (med; the branches are hard to read)
3. **Follow state machine** (path state `+0x34` = the other follower, area `+0x1ac` = this path
   state): the entry's state (0..10) picks a handler (`FollowState*` `0x00511290` …
   `0x00512de0`) which consumes the frame's distance and may move to another state in the same
   frame; more than 50 rounds without progress (`+0x44` > 50) resets the state to 5 via −1. Known
   states (low unless marked):
   - 0 `MoveToFormationPoint` (`0x0051ac10`): the formation point = the leader's position +
     the slot's offset rotated by the leader's facing, nearest safe point within 3 m; queues an
     ordinary MOVETOPOINT run there (group 0xfffe, a 30 s timeout parameter) and goes to state 6
     or 7 — a far or stuck follower **pathfinds**. (med)
   - 5 (`0x005127d0`): takes the next trail point; when the follower is 7 m or more from the leader
     (or on first use) it computes the formation point and goes to 4 if a straight walk reaches it,
     2 if the trail point can be walked to, else 0.
   - 1–4, 6–10: walking along the trail and toward the formation point (not read in detail).
4. The position is written through `MoveCreatureFromClient` (triggers fire for followers too); if
   the follower did not move it turns its head toward the leader within 8 m and keeps its facing,
   else it faces its walking direction. The smoothed speed `+0x48` = average of the frame speed and
   the old value (0 below 10 mm/s). (med)

There is **no teleport** of a far follower in this code: it pathfinds instead (state 0). Script
and module-transition code place party members explicitly. (med)

### 6.3 Switching the controlled character

ChangeChar (Tab) → `0x005f7960`: the leader slot is rotated to the next member
(`CClientExoAppInternal::SetPartyLeader` `0x005f6b60` with −2, "next"), skipping dead or incapacitated ones, at most 3 × the party size
tries. On a change (`0x005f6b60`): the party table's leader index changes, the leader trail is
restarted at the new leader's position and facing (`0x00637890`), the new leader's FOLLOWLEADER
actions are removed (`0x004f76c0(…, 0x3d)`), the camera retargets (`SetCameraTarget`) and the player
control is rebound (`OnControlledCreatureChanged`). The old leader gets FOLLOWLEADER from the party
code (not traced, low). (med)

## 7. Selection and targeting

### 7.1 Selectable objects

(The target reticle and the action buttons are drawn by the main interface panel, see
[gui.md](gui.md); this section covers what feeds them.)

Every frame `CClientExoAppInternal::UpdateSelectableObjects` (`0x005fa5a0`, from `MainLoop`) asks
the server leader for the objects within **30 m** (`CSWSCreature::GetNearbySelectableObjects`
`0x004fc4c0`, walking the area's x-sorted object list outward from the leader) and stores them at
`client+0x2a8` (12-byte entries: id, a cached visibility byte, flags; count `+0x2ac`), with their
bearings relative to the leader's facing. Selectable (`GetIsSelectableTarget` `0x004f2c30`):
(med)

| Type | Selectable when | Hostile flag |
|---|---|---|
| creature | alive, not dying, and seen by the leader (perception list bit 0) or otherwise visible | reaction 2 (hostile) |
| trigger | traps only: detected by the leader, or friendly to it (reputation > 89, e.g. its own mines), or of its faction; the client can pick one only while it plays animation 10144 (`detect`: CSWSTrigger::AIUpdate `0x0058d760` sets 10144 when flagged, of the player's faction, reputation 90 or more, or the player is in its detected list, else 10143 `default`) | a trap of another faction with reputation below 90 (sent per player, `0x00577000`) |
| placeable | useable (`+0x328`) | reputation < 11 with a hostile-capable flag (`+0x340`) |
| door | closed (`+0x2cc` = 0) and not static (`+0x3c0` = 0) | — |

Items are not selectable on their own (KOTOR keeps them in containers). The same pass watches for
mines (`0x005fa83a`): a selectable trap with the hostile and trap flags that passes the leader's
visibility test, while nothing is paused and no auto-pause waits and the "mine in sight" latch
(`+0x328`) is clear, becomes the current target; with the Mine Sighted option (ini bit 0x2000) and out
of combat mode (`+0x320`) the game also pauses with reason 11 (49118). The latch clears after 10 s
(`+0x3a0`) with no such mine seen. (high) If the current target
disappears from the list while hostiles are present in combat mode, a 1.5 s timer (`+0x378`) runs
before a new target is picked automatically. (med)

**What decides who is selectable and visible** (read from `0x004f2c30`, `0x004fc4c0`, `0x00617ad0`,
`0x00502ac0`; high). `GetNearbySelectableObjects` fills two lists from the x-sorted area list,
skipping the leader: every selectable object within 30 m, sorted by bearing (degrees from the
leader's facing, 0 up to 360, ascending), and the **front list**, the objects with a non-negative
dot product with the facing whose direction from a point **4 m behind** the leader makes an angle
under 30 degrees with the facing (cos > 0.866), sorted by distance. A creature is selectable when
it is alive, not dying, and the leader's perception entry for it has its seen bit **or** the
sight check `0x004f1fd0` says the leader sees it now. The PC's own perception pass (`0x00502ac0`)
sets seen for everything in its area with no range or line test (the 250 m of ranges row 12 are
not even looked at); what keeps a PC leader from selecting what is behind a wall is the client's
visibility ray, `CSWCCreature::GetIsTargetVisible` (`0x00617ad0`): a walkmesh line-of-sight test
(`CSWSArea::ClearLineOfSight`'s room half) and a scene ray from the leader to the object, the
object's own model and the leader's left out, that gives up on a **closed door** in the way and
steps past any other object. Visibility is cached per entry per frame; the pointer's pick
(`ProcessInput`), `CycleTarget` (invisible entries are dropped) and the auto-target below all use it.

**What the client does every frame** (`UpdateSelectableObjects`, from `MainLoop`; ours:
`lib/hud/autotarget.ctx`). Read in full, with `GetNearbySelectableObjects` and
`SelectTarget` (high):

1. *The two lists.* The server leader's `GetNearbySelectableObjects(30, 30)` gives the **all list**
   (every selectable object within 30 m, 3-D distance, by bearing: the angle of the direction to the object
   minus the leader's heading, 0 up to 359, counter-clockwise, smallest first) and the **front list** (the
   members of it whose direction from the leader has a dot product of at least 0 with the leader's facing
   and whose direction from the point 4 m behind the leader makes an angle under 30 degrees with the
   facing, cosine above 0.866; sorted by squared distance **from the leader**, nearest first). The facing is
   the leader's own orientation, never the camera's. The cone is wide near the leader: an object beside him
   at arm's length is inside it, and at 5 m ahead the cone is 10 m across. The client copies the all list
   to `+0x2a8`, each entry marked "in the front list" (flag bit 0) and with its visibility not yet known; the
   visibility is `GetIsTargetVisible` (the ray tests of the section above), asked at most once per entry per
   frame and only for entries a step looks at.
2. *The current target* (`+0x2b4`, one value for every way a target gets set: a click, Q / E, a script,
   the last frame's pick). If it is **in the all list** it is kept as it is: while it is visible the
   out-of-view timer (`+0x368`) is 0; when it is not, the timer counts real seconds and at 1.0 the target is
   dropped and picked afresh. Nothing in this function prefers a nearer object over a kept target, and
   a clicked target is no stickier than an automatic one: the same value, the same rules. The one extra
   with enemies in combat mode: a target that left the list (it died) is kept for 1.5 s while a hostile
   creature is still in the list (`+0x378`).
3. *A hostile coming into sight* overrides the above: in bearing order the first visible hostile creature
   (or hostile trap, handled apart), when the *sighting latch* (`+0x324`) is clear and nothing is paused or
   auto-paused, becomes the target and is selected with both flags of `SelectTarget` set (the leader's creature is handed the
   object, and the chase camera swings toward it even out of combat mode); with the Enemy Sighted option
   (`0x1000`) and combat mode (`+0x320`) off it asks auto-pause reason 1. The latch is set while any
   visible hostile is in the list and clears when none has been for 10 s (`+0x394`).
4. *Picking a new target* (no target, or it left the list or view): out of combat mode, or with no hostile
   creature in the list, **the first visible entry of the front list**, nearest first. In combat mode with a
   hostile creature in the list: the first visible *hostile* in the front list; else the first visible
   hostile in the all list (bearing order); else the nearest entry of the front list that is not hostile
   (this last one without a visibility test). Nothing found: no target, and the HUD target is cleared.
   The pick is made by `SelectTarget(object, 1, 0)`: it sets the HUD target (`CGuiInGame::SetHudTarget`),
   hands the leader's client creature the object with a duration of 10 s (`FUN_006146e0`, a look-at; not
   traced further) and, only **in combat mode**, swings the chase camera toward it (`TurnTowardObject`
   `0x00639c30`). A kept target is passed to `SelectTarget` again with both flags 0, so the camera never
   moves for it.

**The target drop that makes the auto-target follow a walking player** is not in that function but in
`ProcessInput` (`0x006227e0`, the branch that steps the player control, near its end): each frame, when
the leader is **not in combat mode**, the HUD target is not none, the auto-pause cool-down (`+0x390`) is
not running (it is set to 1.0 by `RequestAutoPause`; where it counts down was not found, and ours
ignores it) and the player control's current speed (`CSWCPlayerControl::GetCurrentSpeed` `0x00679750`, the
larger of |vx| and |vy| of the keyboard velocity, so the keys and nothing else: a leader walking to a
clicked door is not "moving" here) is **0.25 m/s or more**, a timer (`+0x36c`) adds the frame's time; at
**0.5 s** the target (`+0x2b4`) is set to none and the timer to 0; any other frame resets the timer. So
a player on the move loses his target after half a second of walking, the same frame's
`UpdateSelectableObjects` finds none, and step 4 picks the nearest visible object in front; this repeats
every half second. A player who stops keeps what he has (and a click while standing sets a target that
stays until he walks). In combat mode the drop never runs, so the target stays on the foe until Q / E,
a click, its death or a second out of view. Without this drop the "keep it while it is in the list"
rule of step 2 would hold the first object caught for as long as it stays within 30 m and in sight
(the reported bug: a reticle on a footlocker behind the player while a door right ahead was unmarked).

**What is selectable** (`GetIsSelectableTarget` `0x004f2c30`, by the object-type byte): 5 creature
(alive, not dying, seen); 7 trigger (traps only, as the table above); 9 placeable: **only its Useable
flag** (`+0x328`), which the game itself clears when a DieWhenEmpty container has been emptied (`CloseInventory`
`0x00587560`): HasInventory and Static are not looked at; 10 door: closed and not static. Every other
object type (items, waypoints, sounds, stores, encounters, areas of effect) answers no, and so do triggers
that are not traps.

**The reticles** (`CSWGuiMainInterface::UpdateReticles` `0x0068a310`, which ends by calling
`FUN_006889c0`): there are **two**. The *target's* reticle ("hostilereticle2" / "friendlyreticle2", with
"hostilearrow" / "friendlyarrow" at the screen edge when the target is off screen, "combatreticle" in
combat mode) hangs on the HUD target (`+0x64`, set by `SetHudTarget`). The *hover* reticle ("hostilereticle"
/ "friendlyreticle", the smaller pair, drawn at half strength: the border's alpha is set to 0.5) hangs on
the object under the pointer (`mainif+0x5cac`, set by `ProcessInput` from the same pick that sets the
cursor). Both are sized by the leader's distance to the object: 64 px within 5 m, then smaller in a straight
line to 16 px (creature) or 32 px (other) at 30 m. The hover reticle is hidden while the mouse looks about
(Lookabout held, xor the Mouse Look option), when the point is within 32 px of the screen's edge, and
when the pointer is over the target and the target's first action slot is empty. The cursor over a
selectable object that is not the target is the select cursor; over the target, the default action's.

### 7.2 Hover picking

`ProcessInput` works out the object under the cursor every frame and calls `SetHoverObject`
(`0x006222f0`): hover id `client+0x4a4`, hover point `+0x4a8`, and the cursor chosen from the
hovered object's default action (`GetCursorForAction` `0x0061faa0`, after `BuildDefaultActions`).
The pick walks the same **all list** the auto-target uses (so only what is selectable, within 30 m of
the leader and visible to him can be hovered), asks each entry's client object for its screen bounds
(slots `+0x13c`, `+0x144`) and keeps the one nearest the camera that the pointer is over; the pointer
over a GUI control hovers nothing. The id also goes to the main interface (`+0x5cac`), where it hangs
the hover reticle (7.1). The squared distance of 900 in the hover code is the reticle's size ramp
(30 m), not a limit on picking. How the bounds are computed (the model's box or its meshes) was not
read. (med for the flow, low for the pick)

### 7.3 Target cycling

Q / E → `CycleTarget(bPrevious, filter)` (`0x005fb050`): through the selectable list in its order
(by bearing), wrapping around, from the current target (`client+0x2b4`). The filter is 0 (anything)
normally and 2 (hostile creatures only) **in combat mode**. Entries whose cached visibility test
(`0x00617ad0`) fails are dropped. The chosen object becomes the target (`0x005f9c60`), which also
starts the camera auto-turn toward it (2.3). (high)

### 7.4 Default actions and clicks

`BuildDefaultActions` (`0x00620620`) fills the target's action list at `client+0x4c8` (0x38-byte
entries: label strref, action code, callback, target id, icon resref, flags; count `+0x4cc`) by
the target kind (`GetTargetKind` `0x0060fcc0`): (high for the table, med for the callbacks'
behaviour)

| Kind | Target | Actions (icon) | Code | Callback |
|---|---|---|---|---|
| 0 | none | "no action" (`i_noaction`, strref 32236) | `0x404` | — |
| 1 | door | open (`i_opendoor`, 365) unless `0x0061f790` (the door's animation is already an open one, 10050 / 10051) or `+0x138` refuses it; then bash (`i_attack`, 368) if not plot (`+0x104`), **locked** (`+0x108`: the same flag gates the Security entry, so it is the Locked field, not a "bashable" one) and the area's RestrictMode (`area+0x2b0`) is 0 | `0x3f2` / `0x3f5` | `CSWCDoor::DefaultActionOpen` `0x00683d90` sends the open message (a locked door is refused by the server: locked feedback, OnFailToOpen; there is no unlock in this list) / `0x00683e90` |
| 1 / 3 | placeable | use or open (`i_useplace` 366 / `i_openplace` 365) if it has an inventory or is useable; bash (368) if not plot and bashable | `0x3f7` / `0x3f5` | `0x00682660` / `0x006826a0` |
| 3 | friendly creature | talk (`i_dialog`, 371) | `0x3ea` | `DefaultActionTalk` `0x0060f620`: cancel actions, face, send (6,8) |
| 2 | mine (any client trigger) | disable (`i_disablemine`, 370) when the mine is hostile, recover (`i_recovermine`, 1531) on any; both need the leader's Demolitions (`0x006477e0`). In the target block (`0x00691f00`) Disable is the left slot, Recover the middle, the right empty; no flag or examine | `0x3f4` / `0x402` | `0x00691900` / `0x00691950` (input message 0x12 to UseSkill, subskill 0 / 101) |
| 4 | hostile creature (or any creature while the auto-target timer runs) | attack (`i_attack`, 375) unless the area forbids combat (`area+0x2b0`) | `0x3eb` | `0x00616800` |

- **The target block's slots are not this list.** The block asks `FUN_00619c20` for each of its three lists by the target's kind: a door (`FUN_00684410`): slot 0 Bash (`0x3f5`, `i_attack`) under the conditions above, slot 1 Security (`0x3f3`, strref 329, the skills.2da icon; door locked, server `KeyRequired` +0x2d8 clear, leader has skill 6), slot 2 empty; a placeable (`FUN_006837d0`): slot 0 Bash (not plot, area RestrictMode 0, locked `+0x118`), slot 1 Security (useable, locked, leader trained); a hostile creature: feats and Attack, Force powers, grenades; a mine (`FUN_00691f00`); a friendly creature: nothing. Each slot's selected entry is remembered per target kind by the entry's code. Open, Use and Talk are only default actions.
- **Mouse**: on left button up in the world (not over a GUI, not in mouse look), clicking the
  object that is already the target and was under the cursor at button down runs **entry 0**
  (the default action, GUI sound 6); clicking another object makes it the target
  (`CClientExoAppInternal::OnWorldClick` `0x00620350`). Clicking ground does nothing. (med)
- **R** (DefaultAction, 239) runs entry 0 of the current target. **1 / 2 / 3** run the target
  action menus of the main interface (gui.md), which hold more choices (Force powers, items) than
  this default list. (med)
- The callbacks send the player-to-server input messages of 1.5; the server queues the matching
  actions (actions.md).

### 7.5 Hostility

Hostility comes from the server: `GetIsSelectableTarget` uses the creature reaction
(`0x0057cd90`, 2 = hostile) and reputation (`0x0057cb80`, below 11 hostile, above 89 friendly,
from repute.2da and the faction tables). Pushing (4.9) and `k_def_pathfail01` use the same
reputation thresholds. The client's own test is the creature's virtual slot `+0x138` (med).
rules.md owns the faction system.

## 8. Notes for an implementer

- Plan in 2D on the walkmesh, take z from the face under each point, test every step. The
  engine's planners are expensive-looking but simple: straight line first; PTH graph between the
  nearest reachable path points when the area has one (all areas but cutscene/minigame ones);
  a local grid otherwise and for the legs; then string pulling and corner chamfering. Any
  reasonable A* over the PTH graph plus a walkmesh-face funnel gives equivalent paths; keep the
  constants that change feel: PERSPACE radius, the stop-short range, the 1 m subdivision, the
  0.9-cosine corner cut, the 6-blocked-steps give-up, and the 2 m re-plan when chasing.
- Keep the speed profile (1 s ramp-up, square-root braking over 0.5 s of travel) and the instant
  NPC facing; keep the player's RK4 velocity law and its turn-rate formula with camerastyle's
  Min/MaxTurnRate.
- Run trigger detection on movement segments (inside test plus crossing test), not on positions;
  jumps test the destination only, plain position changes nothing.

## 9. Open questions

- The exact geometry of `CSWWalkMesh::CheckSegmentClearance` (`0x005972b0`, 11 KB): which faces
  count as walls (walkcheck column? non-walkable only?), how the radius sweeps, and whether steps
  up/down have a height limit. Not read.
- `TestSegmentAgainstObjects`/`TestSegmentAgainstCreatures` internals (circle vs. box, which
  creatures are ignored: dead ones? party members?), and the grid successor rules
  (`0x004bcee0`: 4 or 8 neighbours, costs).
- The source of the client creature's movement block (`+0x21c`: `+0x58` acceleration, `+0x5c`
  speed, `+0x60` stealth speed) and whether it equals the server's run rate.
- The walk modifier event 265: unbound on PC; is there any way to walk slowly with the keyboard?
- The follow states 1–4 and 6–10 and the client trail object (`+0x2dc`, `0x00636a30`,
  `0x006350f0`, `0x00634cc0`): trail spacing, formation offsets per slot, when a follower stops.
- Whether the client smooths NPC turning visually (the server snaps the facing).
- Hover picking geometry and the cursor table (`0x0061faa0`).
- The meaning of input messages (6,7), (6,9), (6,0x21), (6,0x24) and of `MOVETOPOINT` flag bits
  4–8 (actions.md lists them as unknown too).
- Camera: the sign conventions of the 284 axis and of mouse yaw, the CAMERAHOOK height branch,
  the auto-turn stop test, the two vertical collision rays, the `"yaw/dist/pitch %f"` client
  commands, the shake waveform, the combat camera's framing helpers, and the legacy modes 0–2.
