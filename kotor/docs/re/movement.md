# Movement, camera and targeting in swkotor.exe

How the original engine moves things around an area: keyboard control of the party leader, the
cameras that follow it, how every creature walks along a planned path on the walkmeshes, how
paths are planned (straight lines, the area's PTH graph, a local grid), what happens when
something is in the way, how triggers notice creatures, how party members follow the leader,
and how the player picks targets. Addresses are for the Steam `swkotor.exe` after SteamStub
removal (see [README.md](README.md)). Every claim ends with a confidence: **high** = read in the
code, **med** = role clear, detail inferred, **low** = plausible. Names are ours, in the engine
family's vocabulary; the proposals for every address below are in `kotor/re/proposals/movement.tsv`
(git-ignored scratch, to be merged into [names.tsv](names.tsv)). The page was rechecked claim by
claim on 2026-10-07 against the exports rebuilt after the noreturn fix
([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check" rests on static
reading alone and is surprising enough to test before relying on it.

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

The keymap rows `Action200`..`Action265` are events with those numbers (buttons, or value events
when the row's `EventType` is 1); the axis rows `Action280A/B`..`Action286A/B` become axis events
280..286 built from two keys, valued second key minus first (`SetupKeymapping` `0x005eeb10`, see
[app.md](app.md) Input). The ones this page uses (keymap.2da as the Steam install loads it: the
`patch.erf` copy, which adds the `EventType` column and row `Action265`; PC defaults):

| Event | Keymap name | Default key | Handled by | What it does | Conf. |
|---|---|---|---|---|---|
| 280 (`0x118`) | ActionUp / ActionDown | W / S | `ProcessInput` `0x006227e0` | forward axis −1..1 (W = −1, S = +1) → player control | high (sign med) |
| 281 (`0x119`) | ActionLeft / ActionRight | Z / C | `ProcessInput` | strafe axis (Z = −1, C = +1) → player control | high (sign med) |
| 265 (`0x109`) | WALKMODIFY | B | `ProcessInput` | value event: while held, the walk modifier halves the input (1.2) | high |
| 284 (`0x11c`) | CameraRotateLeft / Right | A / D | `UpdateCameraInput` `0x005f5e10` | camera yaw (section 2) | high |
| 204 / 205 | SelectPrev / SelectNext | Q / E | `HandleInputAction` `0x00621210` | cycle the target (7.3) | high |
| 206 | ChangeChar | Tab | `HandleInputAction` | next party member becomes the leader (6.3); in free-look it leaves free-look instead | high |
| 208 | Freelook | Caps Lock | `HandleInputAction` | free-look camera, input class 4 (2.5), only while the leader's server action queue is empty and the game is not paused; pressed in free-look, it returns to the default camera | high |
| 219 / 220 | Left/RightLookabout | Ctrl | `HandleInputAction` | hold for mouse look (`g_bLookaboutHeld` `0x008338f0`; the right mouse button sets it too). Held (inverted when the `Mouse Look` option is on) together with the left mouse button, it runs the leader forward (1.5) | high |
| 221 / 222 | AlternateActions | Shift | `HandleInputAction` | `g_bAlternateActionsHeld` `0x008338f8`: the action keys 1–7 take their alternate branch (the secondary lists) | med |
| 226 / 228 / 230 | Target{Left,Middle,Right}Act | 1 / 2 / 3 | `HandleInputAction` | the three target action slots (7.4) | high |
| 232..238 (even) | Personal*Act | 4 / 5 / 7 / 6 | `HandleInputAction` | personal action slots (gui.md) | med |
| 239 | DefaultAction | R | `HandleInputAction` | run the target's default action (7.4) | high |
| 240 | CancleCombat | F | `HandleInputAction` | only while the client is in combat mode (client `+0x320`): leave combat mode (`CSWCCreature::SetCombatMode(0)` `0x00610a10`) and cancel the leader's actions (`CancelServerActions`, 1.4) | high |
| 264 | STEALTH | G | `HandleInputAction` | when the player creature can stealth (`GetCanStealth` `0x00610ac0`), toggle the leader's stealth (`0x0060f4b0`) | med |
| `0x43` / `0x44` | (mouse buttons, hard-wired) | | `OnLeftMouseDown/Up`, `OnRightMouseDown/Up` | selection clicks (7.4); right button = look about | high |

The keymap rows `MoveForward`/`MoveBack`/`StrafeLeft`/`StrafeRight` (200–203) are disabled; the
arrow keys only drive the minigames (and GUI navigation, app.md). There is **no run/walk toggle**,
but there is a **hold-to-walk key**: `Action265` WALKMODIFY (B, `EventType` 1, class PC) feeds the
walk modifier, which halves the input vector, so the leader moves at half its run speed while B is
held; otherwise it runs at full keyboard input. The row exists only in the `patch.erf` keymap (the
`2da.bif` copy stops at `Action264` and has no `EventType` column). (high)

### 1.2 The player control object

`CClientExoAppInternal+0x2a0` holds a 0xcc-byte controller, `CSWCPlayerControl` (constructor
`0x00679780`, vtable `0x00752d34`, 12 slots; built or re-bound to the new leader by
`CClientExoAppInternal::OnControlledCreatureChanged` `0x005f5cf0`). Its fields: (high unless marked)

| Offset | Meaning |
|---|---|
| `+0x04` | controlled creature (client id) |
| `+0x08` | the module camera (its orientation gives the camera yaw) |
| `+0x0c` | control active, set by `SetInputClass` (`0x006200e0`, through `0x006792e0`) and `MainLoop`; while 0, `ProcessInput` feeds no input and `Update` does not turn the creature (med) |
| `+0x10` / `+0x14` | forward input (−1 = forward, W) / strafe input (−1 = left, Z; +1 = right, C), −1..1 (slots 0/1 and 2/3; signs med) |
| `+0x18` | walk modifier (slot 4, read back by slot 5): when set the input vector is halved. Fed every frame from event 265, WALKMODIFY (B held, 1.1) |
| `+0x1c..+0x24` | last desired facing (unit vector) |
| `+0x38` / `+0x3c` | MinTurnRate / MaxTurnRate in °/s, from camerastyle.2da (row = the area's `CameraStyle`) (`LoadSettings` `0x006793c0`) |
| `+0x40` | turn direction, ±1 |
| `+0x44..+0x58` | the Runge–Kutta step's result (velocity, position), copied to `+0x5c..+0x70` at the end of `Update` |
| `+0x5c..+0x64` | velocity (m/s), in the input frame of step 3 below, not in the world |
| `+0x68..+0x70` | integrated position (only differences are used) |
| `+0x74..+0x7c` | previous frame's input vector |
| `+0x80` | rate integrator used for turning in free-look (section 2) |
| `+0xc0..+0xc8` | Keyboard Camera DPS / Acceleration / Deceleration options |

`ProcessInput` reads the axes each frame (the joystick axes 7/8 take precedence when non-zero; no
joystick is ever enumerated on PC, app.md) and sets the inputs, but only while the controller is
active (`+0x0c`), the input class (client `+0x9c`) is 0, nothing is loading (client `+0x288`) and
the camera mode is not 7; in any other state it sets both inputs to 0. It also sets the walk
modifier from event 265, and holding the look-about key (inverted by the `Mouse Look` option,
options+8 bit 1) together with the left mouse button (`g_bLeftMouseDown` `0x008338f4`) forces the
forward input to −1 (full forward) unless S is held. Then it applies the busy rule of 1.4 and, every
frame there is a player creature, calls slot 10, **`CSWCPlayerControl::Update(dt)`**
(`0x00679940`). In order: (high unless marked)

1. `dt` is clamped to at most 1 s. Nothing happens without a controlled creature (client and
   server copy), without a camera or a server, or while the server creature is dead (its virtual
   slot `+0x94`) or dying. (The second "dead" test, `0x0063e7f0`, is a folded stub that always
   returns 0; being helpless is tested later, in `MoveDirect`.)
2. In free-look (camera mode 5, options `+0x6d`) the creature's facing is turned by the
   controller's rate integrator (section 2.5), on the client and the server copy; the inputs are
   0 in that mode, so nothing else moves it.
3. **Input vector** `i = (−strafe, forward, 0)`, normalised when both components are non-zero
   (diagonals are not faster), halved by the walk modifier.
4. **Camera-relative direction**: a copy of `i` rotated about +z by the camera's yaw gives the
   desired heading. (high for the rotation, med for the exact yaw extraction)
5. **Turning**: only while the controller is active (`+0x0c`) and there is input. The shortest
   signed angle Δ between the desired heading and the creature's facing is computed and kept
   on the client creature (`+0x3b8`, 0 without input). When |Δ| > 0.1° and the creature's
   stored speed (`+0x3b0` on the client creature, step 9) is above 0.1 m/s, the facing turns by
   at most `rate·dt`, with
   `rate = MinTurnRate + (MaxTurnRate − MinTurnRate)·(1 − |v| / vmax)` °/s,
   so the creature turns fast at low speed (up to 1500 °/s with the DEFAULT style) and slowly at
   full speed (150 °/s). The new facing is remembered (`+0x1c`) and, when the server creature can
   move (`+0x9f0` bit 0x02), goes to the client creature; the server copy gets it with the next
   position update (1.3). Because `+0x3b0` is 0 unless the creature moved more than 1 m/s the
   frame before, the leader never turns on the spot: from standstill it first steps along its
   old facing, then curves round (med, needs a runtime check).
6. **Velocity**: with no input and |vx|, |vy| both below 0.25 the velocity is zeroed and the step
   ends. Otherwise, when exactly one input component is 0 the matching velocity component is
   zeroed (letting go of strafe kills the sideways speed at once), and the state (v, p) is
   advanced by one classical Runge–Kutta step (weights 1/6, 1/3, 1/3, 1/6) of
   `dv/dt = K·u − (K / vmax)·v`, `dp/dt = v`,
   where `u` is the input vector `i` of step 3, **not** the camera-rotated one (the first
   evaluation uses last frame's `i`, `+0x74`, the middle two the half-way vector, the last this
   frame's), `vmax` is the creature's speed and `K` its acceleration (`ComputeAcceleration`
   `0x00679870`). So `v` approaches `i·vmax` exponentially with time constant `vmax / K`; only
   its length is used to move.
   - `vmax` (`GetMaxSpeed` `0x00679510`): the client creature's movement speed, block `+0x21c`,
     field `+0x5c` (`+0x60` while in stealth, client creature `+0x2d4` bit 0); 6.0 when there is
     no creature; `g_fDebugControlSpeed` (`0x007a25f8`, 15.0) when `0x00833bac` or options
     `+0x88` is set. The values mirror the server's run rate (3.1) (med).
   - `K` (`CSWCCreature::GetAcceleration` `0x00610590`): the same block's `+0x58`, or 15.0 in
     stealth; 25.0 when there is no creature. When `vmax < 1.8`, `K` is scaled by `vmax / 1.8`.
     (high for the code, low for where `+0x58` comes from)
7. **Moving**: whenever the frame's displacement `|Δp|` is above 0 (`|Δp|²` > 0); the floor is
   0.033 m (`|Δp|²` > 0.001089) only when `vmax` ≥ 5000, a debug speed (the asm at `0x0067a395`
   compares GetMaxSpeed with 5000.0 at `0x00743fdc` and loads 0.0 from `0x0073d700` when it is
   below; an earlier reading had the two the other way round). The creature's facing, flattened and
   normalised, is set on the client creature, and the step is `|Δp|` taken **along that
   facing** (not along `v`). The client moves only when the new speed |v| is above 1.0 m/s and
   finite: `CSWCCreature::MoveDirect(pos + facing·|Δp|)` (1.3). If that fails, the remembered
   facing is cleared. After the attempt, `0x0060b920` runs for the party leader: it leaves
   free-look and clears the chase camera's turn-toward-object. (high)
8. Otherwise (no step this frame), in combat mode (camera mode 6), a leader that is not busy
   turns to face the current target (client `+0x2b4`) when that is a creature whose reputation
   towards it is 10 or less (hostile), by at most 900 °/s · dt (`0x007a25f4`), on the server
   creature and the client creature. (high for the code, med for which creature's reputation)
9. The speed is stored on the client creature (`SetMoveSpeed` `0x0060f0d0`, `+0x3b0`, its only
   caller): |v| when step 7 ran with |v| > 1.0 (even if `MoveDirect` failed), else 0. It drives
   the walk/run animation blend and the followers' speed (section 6).

Defaults that matter, from camerastyle.2da: DEFAULT 1500/150 °/s, EbonHawk 500/500, OutDoor and
Manaan 480/150, Combat 800/200.

### 1.3 Moving the client creature: `CSWCCreature::MoveDirect` (`0x00614b90`)

`MoveDirect` reports success (1) **without moving** when the server creature is helpless (in a
SETSTATE, `+0x8ed`, or dying: `GetIsHelpless` `0x005b4880`) or cannot move (`+0x9f0` bit 0x02
clear), when the client creature is busy (`GetIsBusy`, 1.4), or when the creature is not under
direct control (client creature `+0x3a8` ≠ 1) or there is no client area; so `Update` does not
clear its remembered facing in those cases. (high)

Otherwise the target point is tested with `CSWCArea::TestWalkLine` (`0x00604c40`), which forwards
to the server area's straight-walk test (4.4) with the creature's personal-space radius
(PERSPACE) and height. Up to **six** attempts; the loop stops on any result other than −1/−2/−3,
and the move fails (0) unless that result is 1: (high for the loop, med for the geometry)

- result 1: the move is accepted;
- −1 / −2 (walkmesh edge or object): **slide**, when the test reports the edge it hit (otherwise
  the same target is tried again). The target is projected onto that edge's line (from
  whichever end is nearer), or, at a vertex, pushed 0.06 m sideways along the edge direction.
  On the second and later tries a slide whose new direction points back against the previous
  one becomes, at a vertex, a 0.03 m nudge (and the test is repeated); away from a vertex it
  ends the loop and the move fails;
- −3 (a creature): the blocker, when it is found, is pushed aside (`PushCreatureAside`, 4.9) and
  the test is repeated; if still blocked and the creature's own spot is not safe, it is moved to the
  nearest safe point within 1.0 m and the test is repeated once more. A result that is still
  −1/−2/−3 goes through the slide handling above.

On success the server is told first through `CServerExoApp::MoveCreatureFromClient`
(`0x004aead0` → `0x004b6cc0`), which runs the trigger bookkeeping for the segment (section 5);
then the client creature takes the new position (its virtual slot `+0x8c`), the server copy gets
position and facing through `SetCreaturePositionFromClient` (`0x004aeaa0` → `0x004b1cb0`: server
`SetPosition` and `SetOrientation`), and the client party table records the leader's new position
and heading (`CSWCPartyTrail::RecordLeaderPosition` `0x00636a30`; the followers' trail, section 6).
(high)

### 1.4 Direct input versus queued actions

When the leader is busy (`CSWCCreature::GetIsBusy` `0x0060f0f0`: a non-empty server action
queue, the client creature's own busy flag `+0x13c`, or a dialogue animation playing),
`ProcessInput` treats movement input like this (high for the code):

- **In combat mode** (the leader's client creature `+0x440` bit 0) the input is dropped
  altogether, unless an option bit (`options+8` bit 4) is set.
- Otherwise, with no input the timer `client+0x2a4` is set to −1. When input arrives and the
  timer is not running it starts at **0.3 s**; while it runs down the input is **ignored**
  (set to 0).
- On the frame it runs out the input is let through, and if the leader is commandable (server
  `+0xe8`) and the controller's speed (`GetCurrentSpeed` `0x00679750`, the larger of |vx|, |vy|)
  is above 0.25, the leader's actions are cancelled and direct control takes over:
  `CancelServerActions` (`0x0063d470` → `CServerExoApp::CancelCreatureActions` `0x004aef40`:
  `ClearAllActions(1)`, the combat round's scheduled actions freed and its target cleared, the
  attack, attempted-attack, spell and attempted-spell targets `+0x504/+0x50c/+0x528/+0x524`
  cleared), then on the client creature `0x0063cad0` (clears `+0x64`, calls its virtual slot `+0x9c` with
  the word at `+0x58`), `+0x2f4` set to none (`0x00610950`; `SetFacing`, death and the dialogue
  camera set the same field), the busy flag `+0x13c` cleared, the chase camera's secondary part cleared and the array at `+0x1bc` emptied
  (`0x0060c790`). If the speed is 0.25 or less, another 0.1 s wait starts. A non-commandable
  leader is never cancelled this way.

Since the input is 0 during the waits, the controller's speed at each check comes from the
single frames let through (and step 6 of 1.2 zeroes a speed below 0.25 once the input is 0),
so how quickly held movement breaks a queued action depends on `K` and the frame rate (med,
needs a runtime check).

### 1.5 Click-to-move, run/walk and messages

- **No click-to-move.** A left click in the world never moves the leader to a point: it selects
  an object or runs the current target's default action (7.4). The server still has the NWN
  handler for input minor 1 "move to point" (`HandlePlayerToServerInputMoveToPoint`
  `0x005235b0`; it queues MOVETOPOINT, see [actions.md](actions.md)), but no client code sends
  it. (high that no sender exists among the client's message writers; med for the conclusion)
- Likewise the input minor `0x1d` handler (queues DRIVEDIRECT, action `0x33`) has no PC client
  sender found; keyboard control goes through the direct calls of 1.3 instead. (med)
- **Mouse run.** Holding the look-about key (Ctrl or the right button; inverted by the `Mouse
  Look` option) together with the left button forces the forward input to full forward unless S
  is held (`ProcessInput`, 1.2), so the leader runs where the camera faces. (high for the code)
- Client → server messages start with `'p'`, major, minor (`SendPlayerToServerMessage`
  `0x00677410`). The input ones (major 6) that the PC client does send: 2 attack (`0x00677a90`),
  3 open/close door (`0x00677d70`, with 10021 open / 10022 close), 7 use skill (`0x00677b10`,
  e.g. the trap disarm and recover actions), 8 talk (`0x00677ea0`), 9 use item (`0x00677bd0`),
  `0xb` use object (`0x00677d10`), `0xc` unlock (`0x00677de0`), `0x12` cast (`0x006776a0`),
  `0x21` (`0x00677e50`, from `0x005f2980`; server handler `0x00525450`) and `0x24` put an item
  into a container (`0x00677870`). Most go through `SendPlayerToServerMessage`; `0x21` and some
  other writers build the three header bytes themselves. The server side is
  `CSWSMessage::HandlePlayerToServerInputMessage` (`0x005254c0`, cases listed in actions.md). (high for the ids, med for the meanings not listed
  in actions.md)

## 2. The camera

The in-game camera is one `CAurCamera` named "camera" at `CSWCModule+0x40`, created when the
client handles the module message (`CSWCModule::LoadFromMessage` `0x0063f660`, only if the module
has none yet), with near 0.1 and far 10000, camera mode set to 3 (high). It never moves itself:
each frame the **controller** attached to it (`CAurObject` `+0x188`, one at a time, `SetController`
deletes the old one) sets its position and orientation. Controllers derive from
`CAurCameraController` (vtable `0x00743864`, 8 slots: 0 dtor, 2 `Update(dt)`, 3
`SetParameter(char*)` for console tweaks, 4 `GetType`); `CAurCamera::Update` (`0x0045d220`) →
`CAurObject::Update` (`0x00486670`) calls slot 2 during the client object update, just before
rendering. The options byte `CClientOptions+0x6d` records the camera mode (`SetCameraMode`
`0x0061b6f0`; modes 0 and 1 are also copied to `+0x6e`). (med)

### 2.1 Controllers and modes

| Mode (`options+0x6d`) | Type id | Class (vtable) | Constructor | Entered by | Conf. |
|---|---|---|---|---|---|
| 0 / 1 / 2 | — | legacy NWN modes: no controller class; `SyncCameraMode` runs `0x00640700` / `0x00640a80` / `0x00640b90` every frame on whatever controller is installed | — | only script `SetCameraMode`, which no game script calls | med |
| 3 | `0x106a` | `CSWCChaseCamera` (`0x0075165c`) | `0x00639fc0`, from saved state `0x0063ad60` | default | high |
| 4 | `0x106d` | dialogue camera ([dialogue.md](dialogue.md); vtable `0x00756ae8`) | `0x006bb670` | conversations, `EnterDialogCameraMode` `0x006412f0` | high |
| 5 | `0x106e` | `CSWCFreeLookCamera` (`0x0075167c`) | `0x0063a5d0`, `0x0063baf0` | Freelook key → `StartFreeLook` `0x006413c0` | high |
| 6 | `0x1070` | `CSWCCombatCamera` (`0x00757bdc`) | `0x006d12b0` | combat mode → `StartCombatCamera` `0x00641540` | high |
| 7 | `0x1071` | `CSWCFlyCamera` (`0x007515f4`), debug | `0x00638670` | Freelook key when the debug global `0x008338e8` is 1 (`StartFlyCamera` `0x00641610`) | med |
| — | `0x106f` | `CSWCDeathCamera` (`0x0075169c`) | `0x0063bbd0` | whole party dead: `0x004b6da0` → `0x005edc40` → `StartDeathCamera` `0x005f7200` ([gameloop.md](gameloop.md) 6.6) | high |

Before the dialogue, free-look, combat or fly controller is installed, `CSWCChaseCamera::SaveState`
(`0x0063ba80`, only when the current mode is 3) stores the target part, the style row, the
has-CAMERAHOOK flag and the look-at height in `CSWCModule+0x10c` (`+0x10c` = 1 marks it valid,
`+0x110` = 0 chase / 1 free-look). `CSWCModule::RestoreDefaultCamera` (`0x00641dc0`):

- while combat mode is on, installs the combat camera (`StartCombatCamera`) and places it once
  looking from the leader toward its target (`0x006d22c0`, 2.4);
- with no saved block, only sets the mode option to 3 and returns 0 (`SyncCameraMode` then decides);
- otherwise, when the module's mode (`+0xc`) is 3, 5 or 7, rebuilds the chase camera (or
  free-look) from the block. When the outgoing controller is the combat camera, the new chase
  camera starts at its pose (`SetPositionAndOrientation` `0x00637c20`) and converges from there to
  its own distance and height, keeping the yaw; after the dialogue or free-look camera it is
  flagged (`+0x60` = 1) and snaps behind the creature's facing instead (2.3, step 5).

(high for the branches, med for the roles)

`CSWCModule::SyncCameraMode` (`0x006419a0`) is called from `UpdateCameraInput` every frame **while
combat mode is off** (client `+0x320` clear); it does nothing while the mode option is 4 or
`module+0x8c` is set. When `options+0x6d` differs from the module's current mode (`+0xc`) and the
camera's target object (`+0x70`) has a model, it drops the controller if the current mode is 3,
builds a fresh chase (3), free-look (5) or fly (7) controller, and stores the new mode in `+0xc`;
then, for modes 0–2, it runs the legacy per-frame update. `StartCombatCamera` sets the option to 6
but leaves `+0xc` alone; since `SyncCameraMode` is not called during combat mode, the combat
camera is not torn down by it. (high)

**Combat mode.** `CSWCCreature::SetCombatMode(b)` (`0x00610a10`) sets the client creature's
`+0x440` bit 0; for the controlled creature it calls `CClientExoAppInternal::SetCombatMode`
(`0x005f3a80`), which clears `client+0x3e0` when turning off and, when the value changes, stores
`client+0x320` and calls `StartCombatCamera` (on) or `RestoreDefaultCamera` (off). The CancelCombat
key (240) turns it off for the leader and cancels the leader's server actions. While it is on,
target cycling only offers hostiles (7.3). `CSWCParty::SetLeader` (`0x00635480`) hands the client
the new leader's own bit. (high)

Combat mode is **not** the server's combat state (`SetCombatState` `0x004f2610`, creature `+0x4e0`,
8 s after the last hostile act, [combat.md](combat.md)), nor the server's attack mode `+0x4d2` that
the move command turns off (`SetCombatMode(0, 1)` `0x0050ee80`, [actions.md](actions.md)). Everything
the player sees of "combat" follows the client bit: the HUD's combat bar and queue
([gui.md](gui.md) "Combat mode, queue, clear buttons"), Disengage and F, the combat camera, the
combat reticle, hostile-only Q / E, the end-of-round, new-target and enemy-sighted auto-pause
conditions, the dropped movement keys (1.4). (high)

*Turned on* (all high):
- by the target block (`CSWGuiTargetInfo::UseAction` `0x00689610`): when the leader is out of
  combat mode (`+0x440` and `client+0x320` both clear) and the block's target kind
  (`FUN_0060fc00`, stored at `+0x1aea`: 3 a creature whose client hostile slot `+0x138` answers or
  while the 1.5 s keep timer `client+0x378` runs, 2 another creature, 0 a door or a placeable with
  an inventory, 2 one without, 1 a trigger) is 3, then after the entry's callback, if the leader is
  still out of combat mode, `SetCombatMode(1)`. (The decompile loses this flag: asm
  `0x006896f4`–`0x00689710` and `0x006897c3`.) Security on a door, a mine's Disable or Recover do
  not turn it on;
- by the hostile-target callbacks themselves, before or after the order goes to the server: attack
  (`0x00616900`), feat attack (`0x00617dd0`, after its tutorial pop-up), Force power (`0x00616200`),
  grenade / item (`0x006167d0`, `0x00617e40`), and `DefaultActionAttack` (`0x00616800`: the R key or
  a second click on a hostile, after tutorials 0x23 and 0x22; it also arms a 3000 ms window
  `client+0x3e0` in which another default attack offers tutorial 0x23). None of them waits for the
  game to run: paused, the combat bar is up at once;
- every client frame by `0x005f3ad0` (below), from the server's targets.

*Turned off*: by Disengage (`ClearAllCombatActions` `0x006887d0`) and F (`HandleInputAction` 240,
only while `client+0x320`), both with `CancelServerActions` (1.4); by `CSWSCreature::CancelCombat`
(`0x004fdaa0`, the CancelCombat routine and `SurrenderToEnemies`); and by `0x005f3ad0`. (high)

**`0x005f3ad0`**, called by `MainLoop` right after `UpdateSelectableObjects` (7.1, so also while
paused), walks the client party (`client+0x270`), every member, not only the leader (high for the
flow; the vtable slots read from the vtables: object `+0x10` returns the object for every server
object, `+0x30` only for a creature, slot `+0x94` is `GetDead`, the client creature's `+0x138` is
`+0x2dc == 2`, its client hostile flag):

1. *Out of combat mode*: on when its server creature's attempted attack target (`+0x50c`) is a live
   object, or its attempted spell target (`+0x524`) is one that is neither itself nor `+0x50c`.
   "Live" is `GetDead` false: a creature with HP 1 or more (-9 or more for the player's character; a party member never counts as dead:
   `CSWSCreature::GetDead` `0x004ef820`), a door or placeable with HP 1 or more (or its `+0xf8`
   set, `0x00588ab0`). So bashing a door turns it on too, a frame after the order, since
   `AddAttackActions` sets `+0x50c` as the order is queued. (high)
2. *In combat mode*: off when all of these hold (high):
   - the member is not slot 0, or the leader's dead-target keep timer (`client+0x378`, 1.5 s, 7.1)
     has run out;
   - the member's client creature is not hostile (`+0x138`);
   - (a test of the door / placeable callbacks `FUN_00683ee0` `+0x2c4`, `FUN_00682e00` `+0x260`
     that only runs for a member whose client object is not a creature: dead code in practice);
   - `+0x50c` is not a live object, `+0x524` (when it differs from `+0x50c`) is not a live object
     (itself included), and the "going to be attacked by" `+0x520` (when it differs from both) is
     gone, dead, or a live creature whose client hostile flag is clear. A live attacker that is not
     a creature, or a live hostile one, keeps combat mode on.
   It then sets `client+0x394` = -1, so the enemy-sighted latch (7.1 step 3) lets go on the first
   frame without a hostile in view instead of after 10 s, and calls `SetCombatMode(0)`.
3. Afterwards, for the controlled creature in combat mode, the party entry's combat message
   (`party+0xa8` for its slot, set by `0x006345e0` from the attack, cast and item-cast actions and
   the HUD's `Update`) is shown again with `ShowCombatMessage` through `0x0062b110` unless it is
   48208 (`0xbc50`, "COMBAT MODE engaged"). (high) The messages (all through `0x006345e0`, which stores the
   strref in the member's record and shows it at once when the member is the controlled creature): 48208 at
   every run of `AIActionAttackObject` (`0x005bbd06`) and of the cast actions (`AIActionCastSpell` `0x00514b82`,
   `AIActionItemCastSpell` `0x0050f292`), for a party member (`+0xa88`); 42477 "Closing to attack range." when
   the attack pushes its approach and the target is more than 0.5 m away in the plane (`0x005bca13`, squared
   distance above 0.25) and when `AddCastSpellActions` / `AddItemCastSpellActions` push the walk into range
   (`0x004f9d50`, `0x004f93fe`); from `ProcessInput` (asm `0x00623c2c`..`0x00623c8e`) for the controlled
   creature in combat mode, 42476 "Player moving. Cancelling combat actions." while the player control's speed
   (slot `+0x1c`) is 0.25 or more, else, when its message is 42476, 48208; and 48208 from the HUD's `Update`
   when a timed message runs out. `ShowCombatMessage` (`0x00687700`) does nothing while a timed message runs
   (`+0x7724` not -1); 42476, 42477 and 47859 are refused while auto-paused; every message but 48208 and 47915
   gets a 2.5 s timer (`+0x7720`, `+0x7724`; alpha 1 for the first half, then falling to 0); the colour is by
   strref (48208 (0.74, 0.11, 0), 42476 and 42478 (0.28, 0.92, 0.11), 47859 (0.95, 0, 0.85), 47915 (0.98, 0.45,
   0), others the menu text colour (0, 0.66, 0.98)). The HUD's `SetCombatMode` shows the bar (`LBL_CMBTMSGBG`,
   `LBL_CMBTMODEMSG`) for the whole of combat mode and ends a timed message when it ends. Ours:
   `hud::show_combat_message`, `fight::say_combat_message`. (high)

`+0x50c` is set by `AddAttackActions` (`0x004fde40`, when unset), by `AIActionAttackObject` and by
the end-of-round continuation; `+0x524` by the cast actions when unset; `RunActions` clears both
when the queue runs dry (actions.md 1.3), `CancelCreatureActions` clears them (1.4), and the end of
a round clears any whose object is dead. `+0x520` is set by `AddAttackActions` on its target when
that is the player's character (`+0x9d4`) or the party leader, and is cleared only by the target's
`EndCombatRound` when the attacker is gone or dead. So once a foe has been ordered to attack the
leader, the leader stays in combat mode until that foe dies or stops being hostile, or the player
presses F, however far he walks. (high for the code, med for the consequence)

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
carries it to `CSWCArea+0xb8` (`CSWCArea::LoadArea` `0x00607610`), and the chase camera, the
free-look camera and the player control read the row from there (module `+0x48` → area `+0xb8`).
The table is cached at `C2DAs+0x74` (`C2DAs::LoadCameraStyle` `0x005c2540`). The combat camera
always uses **row 8**. (high)

| Column | Reader | Stored at | Notes |
|---|---|---|---|
| DISTANCE, SPEED, PITCH, HEIGHT, TILTSPEED | `CSWCChaseCamera::LoadCameraStyle` `0x00638070` | chase `+0x110`, `+0x114`, `+0x11c`, `+0x120`, `+0x134` | SPEED is stored only (the console `m_fSpeed` writes it too) (med) |
| TILTUP, TILTDOWN, ROTATION | same | globals `0x007a2420`, `0x007a2424`, `0x007a2428` | tilt limits used by `ComputeOrientation`; ROTATION has no reader (high) |
| VIEWANGLE | same | `CAurCamera::SetFieldOfView` `0x0045bee0` (vertical FOV, degrees) | 0 becomes 55; also kept at chase `+0x8c` with the distance at `+0x88` for the dormant FOV compensation (high) |
| — | same | chase `+0xf4`, `+0xf8`, `+0xfc` | the Keyboard Camera DPS, Acceleration and Deceleration options, reread with the row (high) |
| FL_TiltSpeed, FL_RotateSpeed, FL_LOOKUP, FL_LOOKDOWN | `CSWCFreeLookCamera::LoadCameraStyle` `0x006383c0` | free-look `+0x2c`, `+0x28`, `+0x30`, `+0x34` | `+0xbc` = the larger of the two look limits; without the table, tilt and rotate speed are 60 (high) |
| MaxTurnRate, MinTurnRate | `CSWCPlayerControl::LoadSettings` `0x006793c0` | control `+0x3c`, `+0x38` | player turning, 1.2; the same call sets `+0x34` = 480 and copies the keyboard camera options to `+0xc0`..`+0xc8` (high) |
| DISTANCE, HEIGHT, PITCH, ROTATION, SPEED, VIEWANGLE (row 8) | `CSWCCombatCamera` constructor `0x006d12b0` | combat `+0x38`, `+0x40`, `+0x30`, `+0x34`, `+0x3c`, FOV (no 0 → 55 fix-up) | ROTATION and SPEED have no reader; the keyboard camera options go to `+0x84`..`+0x8c` (high) |

`LoadCameraStyle` reloads only when the row differs from the cached one (`+0x5c`), and ignores a
row above the table's row count. Without the 2DA the chase camera falls back to distance 6.25, speed 20,
pitch 80, height 3.5 (row cache −1, FOV and tilt untouched). (high)

### 2.3 The chase camera (mode 3)

**Look-at point.** `CSWCModule::SetCameraTarget` (`0x0063f9d0`) aims the camera at the controlled
creature (only while combat mode is off and the module is in mode 3); switching characters
retargets the existing chase camera and keeps the current yaw and pitch (med). The tracked part
(`+0x14`) is the creature model's `CAMERAHOOK` node if it has one, otherwise the model
(`0x0060efe0`). The height offset (`+0x6c`) is the target height (`0x0060f000` →
`CSWCCreatureAppearance::GetCameraHookHeight` `0x006974d0`) plus appearance.2da
`CameraHeightOffset` (`0x0060f010`); the target height is the `CAMERAHOOK` node's z as the model
reports it, or else the `HEAD_G` node's height above the model origin (`0x006973b0`, which falls
back to a stored appearance height when that is 0 or negative) (med). Look-at = tracked part
position + (0, 0, `+0x6c`) (`GetLookAtPoint` `0x005f5180`); the 3D sound listener sits on the same
point (`UpdateSoundListener` `0x005f5370`).

**One update** (`CSWCChaseCamera::Update` `0x0063bcb0`):

1. (Dormant) FOV compensation of the distance when `+0x84` is set; only the constructor writes it
   (0). (high)
2. `RefreshOptions` (`0x00638f60`): Keyboard Camera DPS, Acceleration, Deceleration into the
   embedded rate integrator at `+0xb4` (`+0xf4`/`+0xf8`/`+0xfc`); it would also load a pending
   style row from `0x007a242c`, which nothing sets. (high)
3. After the base controller update: the debug manual mode (`g_bDebugCameraManual` `0x00833938`)
   takes over if set; without a target part, stop. A freshly constructed camera (`+0x44` =
   FLT_MAX; not one rebuilt from saved state) runs `SnapBehindTarget` (`0x00638fe0`), which takes
   the yaw from the target's facing and the pitch from the style. (med)
4. `UpdateYaw` (`0x006391a0`, below) gives the new orientation at `+0x28`.
5. **Position** (`ComputeFollowPosition` `0x006398f0`): with `h` the current horizontal distance
   to the look-at and `d` = DISTANCE, `h' = d + 0.5·(h − d)` (the error halves every frame —
   frame-rate dependent, constant `0x007a243c`); θ' = the yaw of `+0x28` (snapped normally; while
   auto-turning, eased by Δ·rate·dt, Δ the wrapped difference from the camera's current heading);
   camera.xy = look.xy − h'·(−sin θ', cos θ'), camera.z = look.z + HEIGHT. Headings follow
   `atan2(−x, y)` in degrees (`0x004aa0f0`): yaw 0 faces +y. While `+0x60` is set (a new chase
   camera, and one that replaces the dialogue or free-look camera), `+0x28` is reset to the
   tracked part's orientation, so from the next frame the camera sits behind the creature's
   facing; `+0x60` is then cleared. (high)
6. **Collision** (`ResolveCollision` `0x0063b050`, below).
7. **Orientation** (`ComputeOrientation` `0x00639760`): yaw = heading from the camera to the
   tracked part + shake offset `+0x90`, so the camera always looks at the player. The tilt input
   (`+0x104`, divided by 75 above magnitude 1, i.e. a mouse value) moves the target pitch
   (`+0x108`, PITCH at construction) at TILTSPEED·input·dt within [PITCH − TILTDOWN,
   PITCH + TILTUP]; every row but QAVis has zero tilt, so **the pitch is fixed at PITCH**. Output
   pitch = target − (target − current)·dt·0.5 + shake `+0x94`. Quaternion = Rz(yaw)·Rx(pitch)·
   Ry(roll) in degrees (`0x004acac0`); pitch 0 looks straight down, 90 is level (DEFAULT's 83 looks
   7° below the horizon). (high)

**Yaw input** (`UpdateYaw`):

- *Mouse look* is active while Lookabout (Ctrl or the right mouse button) is held, XOR the "Mouse
  Look" option (`options+8` & 2). The cursor is hidden and restored on release. The caller
  (`UpdateCameraInput` `0x005f5e10`) passes v = −dx·sens (sign flipped when `g_bInvertCameraYaw`
  `0x00832920` is set; no code writes it), dx = clamp(−mickeys/100, −1, 1)
  (`CExoInputInternal::UpdateMouseAxes` `0x005e0110`), sens = 10 + 0.45·slider (`options+0x50`,
  0..100); `UpdateYaw` rotates the camera by −v degrees about +z, i.e. yaw changes by dx·sens:
  moving the mouse right turns the view right. (The mouse exponent `0x007a2448` = 2 is applied to
  1.0, so it has no effect.) The integrator is also fed −dx during mouse look, so a rate built up
  while dragging coasts out over ~0.1 s after release (med, needs a runtime check). (high)
- *Keys* (event 284, A/D) give an input u in −1..1 to the rate integrator (`CRateIntegrator`
  `0x006d0b20`/`0x006d1190`): with input `rate' = Acc·u − (Acc/DPS)·rate`, without
  `rate' = −(Dec/DPS)·rate`; RK4, dt clamped to 0.2 s; the angle integrated over the frame
  rotates the camera about +z. Defaults (`0x0061d9e0`, ini "Keyboard Camera DPS/Acceleration/
  Deceleration"): DPS 200 °/s, Acc 500 °/s², Dec 2000 °/s², so the rate reaches 200·u °/s with a
  0.4 s time constant and stops with 0.1 s. With `g_bInvertCameraYaw` set (and `0x0083394c`
  clear) `UpdateYaw` keeps only the part of the key rotation with the other sign, so key turning
  does nothing (low; the flag is never set). (high for the law, med for the state layout)
- *Screen edge*: with no key input, no mouse look and not in free-look, a cursor within
  max(2, ⌊width·0.001⌋) px of the left or right edge acts like the rotate keys at full input
  (`UpdateCameraInput` `0x005f5e10`). (high)
- *Auto-turn toward a target*: `+0x80` holds an object id set by `TurnTowardObject`
  (`0x00639c30`) when `SelectTarget` (`0x005f9c60`) picks something with the cycling flag (target
  cycling, `0x005fb050`) or while combat mode is on (`client+0x320`; also the automatic selection
  in `UpdateSelectableObjects` `0x005fa5a0`). Without manual input the desired yaw becomes the
  heading from the tracked part to the object offset by ±15° (the object beside the player; the
  sign follows the side the object is on); the eased rate `+0x9c` (`0x00637b80`) rises 3/s while
  the camera is more than 1 m from its ideal spot (look-at − DISTANCE along `+0x28`,
  `GetIdealPosition` `0x00637af0`) and falls 5/s otherwise, within [2.5, 7.5] (0 when not
  auto-turning). The turn ends when the object lies within 0.866 m of the camera's forward line
  through the player (|right·(object − part)| < 0.866, unnormalised, so metres), and any manual
  yaw input clears it. (med)
- **The camera never swings behind a moving player by itself**: only input, target auto-turn or a
  controller change (the `+0x60` snap in step 5) moves its yaw; the forced-yaw global
  `0x007a2440` is never set. (med)

**Collision** (one pass; the loop counter starts at 1):

1. *Creatures* (server side, via `CServerExoApp::ClipCameraToCreatures` `0x004aebb0`):
   `CSWSArea::ClipCameraSegmentToCreatures` (`0x004bf650`) shortens the segment look-at L →
   camera C. It takes creatures within ±3 m of the segment's xy box from the area's x-sorted
   creature array (`+0x190`/`+0x194`) and skips any whose PERSPACE circle (path state `+4`)
   contains L (the player). For each remaining creature whose **CAMERASPACE** circle
   (appearance.2da; path state `+0x10`) contains C, it intersects the 2D segment with that circle
   (`0x004aab50`, crossings in [0, 1)): with one crossing (L outside) C moves to it, with two to
   the one nearer L, pulled back 1 mm toward L; z = min z + (max z − min z)·(|L−C'|²/|L−C|²) −
   0.01 (a ratio of squared xy distances). The scan repeats until no creature moves C.
   (high for the test, med for the z formula)
2. *Geometry* (client side): side = normalize(cross(Z, L − C))·0.35 (`0x007a241c`); four rays from
   L to C ± side and C ± 0.35 z go through `CAurScene::RayTest` (`0x00456b60`): the rooms' AABB
   meshes first (the same geometry as the WOKs), then scene objects; the tracked part (the
   player's model) is excluded and the query mask `0xbfffffff` lets every material except 30
   (Trigger) block. (med)
3. If a ray hits, p = the largest distance from a hit to its ray's end (the stretch left past the
   hit, not the hit nearest the end); C −= normalize(C − L)·p and C += up·(0.35 + 0.15)·p/|C − L|
   (`up` = the target part's orientation applied to +z, quaternion stored w first): the camera
   moves in to about the surface of the worst ray and rises a little. (high)

There is **no zoom**: the mouse wheel goes to the GUI; the zoom input `0x006401d0` belongs to the
legacy modes (it calls controller slot 7, which returns 0 for the chase camera). (med)

### 2.4 The combat camera (mode 6)

`CSWCCombatCamera` (`0x006d12b0`, 0x94 bytes; update `0x006d1fc0`) reads camerastyle row 8
(distance 3.6, pitch 76, height 0.55, view angle 55; ROTATION and SPEED are stored at `+0x34`,
`+0x3c` and never read) and the keyboard camera options, which it rereads every frame into the
rate integrator at `+0x44` (`CRateIntegratorDecel`, the chase camera's key law). Despite its name
it does **not** keep the target in the picture: the update fetches the current target
(`client+0x2b4`, `0x005edd80`; the leader when there is none) only to test that it exists, and its
position never enters the result. It is a rigid chase camera: a fixed distance behind the leader
along the camera's own yaw, no lag, the yaw moved only by mouse look and the rotate keys. (high,
from the asm of the update and its helpers)

**One update** (`0x006d1fc0`):

1. Without a party leader, nothing moves.
2. Mouse look on/off as in the chase camera (Lookabout held XOR `options+8` & 2; the cursor
   position is saved and the cursor hidden on entry, restored on exit; input class 2 forces it
   off). State at `+0x90`, started from the Lookabout flag by the constructor.
3. Look-at L = leader position + (0, 0, head height) (`HEAD_G` above the model origin,
   `0x006973b0`).
4. **Yaw** (`0x006d14e0`). While combat mode is on, `CameraInputMouseYaw` (`0x0063fe10`) writes
   `+0x28` = −m when mouse look is active (else 0) and clears `+0x2c`; `CameraInputKeyYaw`
   (`0x00640090`, keys and screen edge) writes `+0x2c` = −u and clears `+0x28`. m and u are the
   values `UpdateCameraInput` gives the chase camera (m = −dx·sens, 2.3), so the mouse turns both
   cameras the same way.
   If `+0x28` ≠ 0 the step is Δ = `+0x28` degrees (the key integrator is reset to that rate,
   `0x006d1030`, and `+0x2c` cleared); otherwise Δ is the angle the integrator turns this frame
   from input `+0x2c` (angle reset each frame). Q = Rz(Δ) · the camera's current orientation
   (`0x004a9ac0`), ψ = yaw(Q); the forward f is Q's local +y flattened to xy and normalised,
   = (−sin ψ, cos ψ).
5. **Position**: C = (leader.x − 3.6·f.x, leader.y − 3.6·f.y, leader.z + h + HEIGHT), h the
   creature's camera height (`0x006974d0`: the `CAMERAHOOK` node's height, else the head height).
6. **Collision** (`0x006d18e0`): the chase camera's geometry pass (2.3, collision steps 2–3: four
   rays from L to C ± 0.35 side and C ± 0.35 z, pull-in by the worst overshoot, lift along the
   leader's up by (0.35 + 0.15)·p/|C − L|); there is no creature clip. (med: same constants and
   shape, decompile partly garbled)
7. `0x006d16f0` returns ψ unchanged (it reads the mouse sensitivity and drops it); `0x006d1760`
   would ease the camera toward C, but the update passes it a speed of 0, so the camera is put
   on C directly.
8. Orientation = Euler(yaw ψ + shake `+0x14`, pitch 76 + shake `+0x18`, roll 0)
   (`0x004acac0`); position = C. The camera does not aim at L: it looks along ψ at the fixed
   pitch (14° below level), and since C lies straight behind the leader on ψ the leader stays
   centred left-right.

**Entering.** `SetCombatMode(1)` installs the camera with no placement, so the first update
continues from the chase camera's yaw and cuts to 3.6 m / pitch 76 at once. Only when
`RestoreDefaultCamera` runs while combat mode is on (the end of a conversation, a closed window,
leaving free-look) is it placed once by `0x006d22c0`, and only if there is a target: d =
normalize(target − leader) (3D, positions only); C = leader − 3.6·d, through the same collision
with L = the leader's position; orientation = (heading of d, 76, 0). The next update moves it to
its proper height but keeps that yaw, so the camera then looks from the leader toward the target
until the player turns it. Leaving combat goes through `RestoreDefaultCamera` (2.1), and the
chase camera starts at the combat camera's pose. (high)

### 2.5 Free-look (mode 5, input class ICFreeLook)

- **Enter**: Freelook (Caps Lock), handled in `HandleInputAction` (`0x00621210`) on key down,
  only when there is a player creature (with `+0x138` clear), no party wipe is running, the mode
  is not already 5, the leader's server action queue is empty and the game is not paused. The key
  handler hides the HUD (`g_bMainInterfaceVisible` `0x007a2288` = 0) and sets input class 4;
  `StartFreeLook` (`0x006413c0`) saves the chase state and turns the creature (client side) to
  face away from the camera (both only when the mode was 3), installs the controller (which also
  starts the appearance's `FreeLookEffect` screen effect) and sets mode 5 (option and `+0xc`).
  (high) The effect: `CSWCCreature::GetFreeLookEffect` (`0x00610490`) reads appearance.2da
  `FreeLookEffect` for the appearance record's row (+0x18), -1 when the cell is blank (only rows 2,
  T3-M4, = 1 and 3, HK-47, = 2 have one); the controller's constructor (`0x0063a5d0`) keeps it at
  +0x78 and calls `EnableVideoEffect` with it, which with -1 only switches an earlier effect off; its
  destructor (`0x0063a6c0`) switches the effect off (`0x005edf20`). (high)
- **Leave** (`RestoreDefaultCamera`, input class 0, HUD shown): the Freelook key again, a GUI key
  (209–216) or Pause (241), or the leader getting a queued action. (med)
- **Update** (`0x00639d00`): hides the cursor every frame; the eye is the model node
  `FreeLookHook`, else `CameraHook`, else `root` + 2 m. Yaw is the creature's own facing: mouse x
  turns the creature (client and server, `CameraInputMouseYaw` mode 5: the value halved and
  clamped to ±30, times FL_RotateSpeed), the A/D keys feed the control's turn integrator
  (200 °/s, 500 °/s²). Pitch: mouse y adds dt·FL_TiltSpeed·v (and resets the key integrator), keys go
  through a rate integrator (`+0x7c`, the plain `CRateIntegrator`: 200 °/s and 500 °/s² set by the
  constructor, no separate braking; its input is minus the forward input, so W tilts up and S down,
  `CameraInputMove` `0x0063fdb0`); wrapped to ±180 and clamped to [−FL_LOOKDOWN, FL_LOOKUP]; the orientation uses
  pitch + 90 plus the shake offsets `+0x70`/`+0x74`. (high for the pitch, med for the yaw
  formula)

### 2.6 Death camera, shake, script commands

- **Death camera** (`0x0063a810`; [gameloop.md](gameloop.md) 6.6 has the fields): watches the
  last player-controlled creature to die (client `+0x2d4`). The orbit heading advances 30 °/s and
  wraps at 360; per frame the camera's heading moves half the way to it, its pitch 1 % of the way
  to 0 (straight down), the look-at height drains from 0.75 m toward the feet by 1 %, and the
  distance moves half the way to 3.0 m; a ray from the look-at point keeps the camera 0.25 m off
  geometry. (med)
- **Shake**: `StartCameraShake` (`0x006416f0`, delay and duration in ms; a shorter shake does not
  replace a longer one) is started by visualeffects.2da `ShakeType` 2 with `ShakeDelay` and
  `ShakeDuration`, seconds times 1000 (`0x00690010`, `0x006a5fc0`; type 1 goes to `0x00641730` instead, a
  rumble request). Only row 6002, VFX_IMP_SCREEN_SHAKE, has type 2 (1 s, no delay).
  `UpdateCameraShake` (`0x00641760`, every frame from `UpdateCameraInput`) acts only when a chase,
  dialogue, free-look or combat controller is installed, and cancels any shake unless the options
  bit `CClientOptions+0` & 4 is set. After the delay, while r ms of the duration D remain:
  a = sin(2π·r/30)·(1 + cos(2π·r/D))·20·π/180, and the yaw and pitch offsets each get −a or 0
  (a coin per axis per frame), written to chase `+0x90`/`+0x94`, combat `+0x14`/`+0x18`, dialogue
  `+0x2c`/`+0x30` or free-look `+0x70`/`+0x74`. The offsets are added to angles in degrees, so the
  shake is at most 0.7° (med: the degree-to-radian factor looks like a slip; needs a runtime check).
- Script **SetCameraFacing** (routine 45, `0x00542530`) queues action `0x16`
  (`AIActionSetCameraFacing` `0x005137c0`) which sends message major `0x10` minor 1
  (`0x0056c610`); the client (`0x0064b8e0`) formats `"yaw %f"` / `"dist %f"` / `"pitch %f"` and
  hands each to the camera (slot 24, `0x0045c160` → `0x0043f5a0`), which passes it to the current
  controller's `SetParameter`. No controller knows those words (chase: `m_fDist`, `m_fSpeed`,
  `m_fPresetPitch`, `m_fHeight`; death: `m_yaw`, `m_desiredPitch`, ...; fly: `speed`, `turn`, ...),
  so the command has no effect (high). **SetCameraMode** (504, `0x00542640`) sends minor 2, which
  sets `options+0x6d` (legacy modes). Neither is used by any game script. **SetDialogPlaceableCamera**
  (461) belongs to dialogue.md.

## 3. Creature movement

### 3.1 Speeds and sizes

**Rates.** `CSWSCreatureStats::SetMovementRate(n)` (`0x005a5680`) stores the row at stats
`+0x194` and copies creaturespeed.2da `WALKRATE` to stats `+0x19c` and `RUNRATE` to `+0x198`.
Row 7 ("Default") is resolved through appearance.2da `MOVERATE` (a string like `NORM`; the row is
stats `+0x186`) matched case-insensitively against creaturespeed's `2DAName`, and the resolved row
is what `+0x194` keeps; no match (or no MOVERATE) gives row 0, PLAYER. Row 7's own 1.70 / 5.40 are
never read. Resolving to row 1 (Immobile) also sets the creature's AI state mask `+0x9f0` to
0xfffd, clearing the *can move* bit (rules.md). The stats reader takes the UTC/save BYTE
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

- walk = clamp(`+0xa08`, 0.125, 1.5) · WALKRATE · 1000, and 0 when 100 or less (an immobile
  creature never moves); in stealth mode (`+0x9fc` bit 0), for a creature with a client twin, the
  walk rate is instead the client movement block's `+0x60` × 1000 (`+0x21c` block, 3.6): appearance
  **DriveAnimWalk** read as m/s (0 → 2), not scaled by `+0xa08` — 1.6 to 1.9 m/s for the humanoid
  rows, whatever the creaturespeed row, and speed effects do not change it (needs a runtime
  check). It is the same field the client caps the driven creature's speed at in stealth
  (`CSWCPlayerControl::GetMaxSpeed` `0x00679510`: `+0x60` in stealth, else `+0x5c`, 3.6), so server
  and client agree on the stealth pace;
- run = clamp(`+0xa08`, 0.125, 1.5) · RUNRATE · 1000, at least 1000.

`+0xa08` is the movement speed multiplier that the speed effects change (rules.md). (high)

**Who sets the row.** (high)

- `ReadStatsFromGff` (`0x005afce0`) reads the BYTE `MovementRate` (default: the current row) and calls
  `SetMovementRate` with it; only when that field is absent does it read the INT `WalkRate` (same default)
  and call it again. A blueprint has only `WalkRate`; a save has both, `MovementRate` being the resolved
  row that `SaveStats` (`0x005b1b90`) writes from stats `+0x194`. So row 7 is resolved once, when the
  blueprint is read, and a saved creature keeps the row it had.
- `CSWPartyTable::AddAvailableNPCByObject` (`0x00564300`, also reached from `AddAvailableNPCByTemplate`
  `0x005645f0`) sets **row 0, PC_Movement**, before it writes `AVAILNPC<n>`: every companion walks at 3.2 m/s
  and runs at 5.4, whatever its blueprint says (`p_carth001` names row 8, DM_Fast, which is never used
  in the party). The player's own character is row 0 from character generation (`MovementRate` 0).
- `0x004ed850` (the appearance-row reader, called by `PostProcess` with 0) sets row 7 only when its
  argument is set (callers `0x004ee010`, `0x004ee150`: an appearance change, not traced); `0x005228d0`, a
  player-to-server message handler, sets row 7 too (not traced, low).
- `GetCreatureMovmentType` (routine 566, `0x0053efa0`) returns stats `+0x194`, the resolved row; 1 for a
  non-creature.

The data: 57 of the 1,942 distinct UTCs name a row other than 7: row 1 (Immobile) for 12 (the Leviathan
bridge crew `kor37_bridge*`, victims, a stunt soldier), 3 (Slow) for Jawas and a few others, 4, 5 (gizka,
the Manaan droids), 6 (`tar02_larrim`, `kas_fake`, `sta_45darthmalak`), 8 (`p_bastilla001`, `p_carth001`,
`g_sithtroop002`), 9 (the krayt dragon).

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

- `CSWSCreature::UpdateMovement` (`0x0051d9c0`) for creatures with the object flag
  `CSWSObject+0x1f8` set (taken to mean "a client knows it"; what sets it is open, gameloop.md 9).
  `CServerAIMaster::UpdateState` calls it **every frame** for every such creature on an AI level
  whose head action is MOVETOPOINT or FOLLOWLEADER, or whose movement state (`+0xa8c`) is 4–6, in
  the movement pre-pass that runs before each budgeted AI update (gameloop.md 2.2; the repeats in
  the same frame find a zero time delta and do nothing); a return of 2 sets `+0xa8c = 1`.
  AIActionMoveToPoint itself calls it once, with the start flag, when the path is ready: that call
  only restarts the creature's clock (zero delta, no step).
- `CSWSCreature::StepMovementUnseen` (`0x0051bb10`), from AIActionMoveToPoint (inside the budgeted
  `RunActions`) for creatures without the flag. The same step inlined, with its delta from `+0xcc`
  and its speed from the current animation (walk rate for 10002/10003, run rate for 10004); no
  deadline, no stealth or follower override, no chased-creature re-plan; the trigger and
  area-transition-door cases of step 12 below are the same, and a reported arrival clears the path
  and plays 10000. (med)

`+0xa8c`, the movement state (objects.md 4): −1 none (set by the constructor and for creatures
without the flag; `UpdateMovement` sets it to make MOVETOPOINT plan afresh), 0 walking a path
(`UpdateMovement` drives it and MOVETOPOINT just reports running), 1 stopped, 2 move-to-point
queued / planning, 3 following the leader (section 6), 4 Force Push, 5/6 Force Jump (3.7). (high)

**`UpdateMovement`, one frame**, in order (high unless marked); it returns 2 when the move is over
and 1 otherwise:

1. Return 2 at once for a creature without the flag, in state 1, dead (slot 37 `GetDead`) or
   dying (`GetIsDying`: a party member below 1 HP), the common preconditions of actions.md 1.4.
2. Frame delta: world time now minus the creature's last update (`+0xb0/+0xb4`), in ms, at `+0xd0`;
   with the start flag the delta is 0 and the clock restarts.
3. State 3 → `UpdateFollowLeader`; states 4–6 → `UpdateForcedMotion`; the clock is restarted and
   their result returned.
4. **Timeout**: if the move has a deadline (path state `+0x26c`, world time `+0x270/+0x274`) and it
   has passed, the creature **jumps** (`0x004edba0`, running `AIActionJumpToPoint` on the
   destination `+0x5c..+0x64` in area `+0x70`, or `AIActionJumpToObject` on the target `+0x30` when
   the move has one), `+0xa8c = 1`, the head action node removed if it is a MOVETOPOINT, the idle
   animation set, the deadline cleared; return 2 (Force* moves, see actions.md).
5. A zero delta stops here (return 1). Otherwise the clock is restarted and the **speed** chosen: in
   stealth (`+0x9fc` bit 0) the walk rate (3.1), with no animation change (entering stealth also
   applies a walk-only LIMIT_MOVEMENT_SPEED effect, +0x8e8 = 1, which clears the run flag when the
   move starts: `0x004f6d70`); else the run rate if the action's run flag (`+0xa98`) is set, the
   walk rate otherwise, and the run (10004) or walk (10002) animation is (re)set every frame when
   the creature's *can move* bit is set (AI state mask `+0x9f0` bit 2, rules.md). A speed of 0
   stops here (return 1).
   **Following party members**: for a player-controlled creature (`+0xa88`) with a FOLLOWLEADER
   (0x3d) anywhere in its queue, with d the distance between its client party entry's trail point
   (`+0x18`) and follow point (`+0x28`) (6.2's A and B): when d² ≥ 0.001 the speed becomes the larger
   of its run rate and the leader's client speed (member 0 `+0x3b0` × 1000); then × 0.9 for d up to
   1 m, × 1.2 up to 15 m, × 1.5 beyond. Unlike 6.2, the speed factor below still applies. (high)
6. **Speed factor** `f` (`GetSpeedFactor` `0x00512f10`), 3.3. Distance this frame:
   `s = dt_ms · (f + f_prev) · speed_mm/s · 0.5 · 10⁻⁶` m (trapezoidal), `f_prev = f` stored at
   `+0xb8`. A debug flag (`0x00832814`) multiplies `s` by 15.
7. `StepAlongPath(s)` (3.4) gives the new position, direction and status. If the new z differs from
   the old by 0.001 or more, the waypoint index is restored and the step redone with
   `s · s / √(s² + dz²)`, so the creature covers `s` along the slope, not across the map.
8. Walking away closes an open container: if the client twin has an item's or placeable's
   inventory open (client object `+0x58`), it is closed (`0x004eded0`).
9. Volumes: `UpdateVolumesAfterMove(old, new)` (section 5).
10. `SetPosition`, the client party table's copy for party members, `SetOrientation` to the step
    direction (z = 0, normalised). **NPCs turn instantly** to their walking direction on the
    server. (high; whether the client smooths the visible turn was not checked)
11. For a player-controlled creature (`+0xa88`):
    - if it is client party member 0 (the leader): its position and heading are recorded on the
      party trail (`CSWCPartyTrail::RecordLeaderPosition` `0x00636a30`), and `0x0060b920` leaves
      free-look (camera mode 5 → interface shown, default camera, input class 0) and clears the
      chase camera's turn-toward-object;
    - if it has a FOLLOWLEADER queued, is still walking (status 0) and the leader is 7 m or more
      from the point its entry recorded (`+0x74`), it re-aims: the follow point plus the entry's
      offset (`+0x38`) rotated about z by its formation slot's angle (`CSWCPartyTrail::GetFormationSlot`
      `0x00634cc0`), z from the walkmesh, taken when the entry's state (`+4`) is 6 and the point is
      safe (`IsPositionSafe`), or the bare follow point when the state is 7 and it is safe; the goal
      and the MOVETOPOINT node's point are rewritten, `+0xa8c = −1`, return 1. (med)
12. **Interaction / arrival**, by the path's target object (path state `+0x30`):
    - a trigger that is not a trap (`+0x2bc` = 0) and within use range (`GetIsInUseRange(target, 0)`
      `0x004f6000`): script event 30 CLICKED to it (caller the creature), animation 10000, return 2.
      The path and the MOVETOPOINT node stay; the action, run next with `+0xa8c = 1`, takes the
      trigger case of actions.md 3.1, which sends a CLICKED of its own (a second click: needs a
      runtime check);
    - an area-transition door (LinkedToFlags 1 or 2, `CSWSDoor::GetIsAreaTransition` `0x005890d0`)
      within use range: open (`+0x2cc`) → CLICKED to the door, animation 10000, return 2; closed →
      PATH_BLOCKED (31) to the creature with the door as caller (its OnBlocked script), animation
      10000, return 1, so it repeats every frame until the door opens (med);
    - a creature 2 m or more (3D) from the goal the path was planned to (`+0x248..+0x250`): the goal
      is updated, `+0xa8c = −1` (re-plan), return 1;
    - otherwise, or with no target: when `StepAlongPath` reported status 1 and the state is not 2 (a
      move queued meanwhile): path cleared, `+0xa8c = 1`, the head node removed if it is a
      MOVETOPOINT, idle animation, return 2. Any other case returns 1.

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
`f_prev` is never reset between moves: the object constructor sets it to 1.0 (`0x004cfcb0`), so a
creature's first move starts at full speed, and a move that ended without braking (blocked,
re-planned, interrupted) leaves the next one starting from where it stopped. Only
`UpdateMovement` and `StepMovementUnseen` write it. (high)

The first leg of `R` is measured in 3D against the waypoint at z = 0 (waypoints are x,y only), so
it includes the creature's own height |z|: on a floor more than `D` above or below z = 0 (0.85 m
at the 1.7 m/s walk, 2.7 m at the 5.4 m/s run) the braking zone is never entered and the creature
arrives at full speed. (med: read in the code and the disassembly; needs a runtime check)

### 3.4 Walking the waypoints: `StepAlongPath` (`0x00516630`)

The path state holds the final waypoint list as x,y floats (`+0x8c` float count, `+0x90` data) and
the index of the next waypoint (`+0x9c`, in floats). For a distance `s` it returns the new
position and direction and a status: 0 still walking, 1 arrived or stopped (which `UpdateMovement`
treats as the end of the move, 3.2 step 12). An exhausted or empty path starts as status 1; no area
gives 0. The early stops (items 1, 2 and 4) leave the creature where it is. (high unless marked)

1. **Already there**: with a target object (path state `+0x30`) whose use point and range
   `GetUseRange` (`0x004ee440`) gives, a creature within that range (3D) of the use point stops at
   once: idle animation, status 1.
2. With the "stop when in sight" flag (MOVETOPOINT flag bit 10, path state `+0x240`), two tests,
   each needing a clear line-of-sight ray (`CSWSArea::ClearLineOfSight` `0x0050c330`, from eyes
   1.5 m above the creature to 1.5 m above the point) and a clear object test
   (`TestSegmentAgainstObjects`, 4.9); either one passing stops the creature there (idle
   animation, status 1):
   - a target object whose use range is smaller than the move's range (`+0x68`), the creature
     within `+0x68` (3D) of its use point;
   - a path of at least two waypoints whose last waypoint is within `+0x68` (horizontally); this
     one needs no target object.
3. Otherwise, waypoint by waypoint: the segment from the current point toward the next waypoint
   (horizontal; the step is min(`s`, its length)) is tested with `CheckStepCollision` (4.9). Not
   blocked: if the waypoint is farther than the remaining `s`, move `s` toward it, status 0; else
   move onto it, subtract its distance, advance `+0x9c` by 2 and continue; running out of
   waypoints is arrival (status 1). The z of every point is the walkmesh height under it
   (`CSWSArea::ComputeHeight` `0x004bc380`). The volumes each sub-segment crosses are collected
   (`GetVolumesCrossed`) for the trigger check of section 5.
4. Blocked: a counter (`+0x268`, reset when the move is planned) counts blocked steps. At the 6th
   the creature gives up: path cleared, idle animation, status 1. Before that:
   - the blocker is the move's own target object: path cleared, idle animation, status 1 (arrival);
   - a creature other than the one being avoided (path state `+0x254`), or that one when it has
     moved from where it was recorded (`+0x258..+0x260`): the avoidance helper
     (`CPathAvoidance::ResolveBlockingCreature` `0x005d0840`, 4.9) tries a detour on side `+0x244`
     and sets the blocker's side (the opposite value when both face the same way, the same value
     when they face each other). A detour gives status 0 (the creature stays put this frame and
     takes the detour next); result −2 gives idle animation, status 1; no detour clears the
     avoided creature, plays the idle animation and gives status 1, and the player's own creature
     shows the feedback string 47859 "The path to your target is blocked.";
   - anything else (a wall, a placeable, the same creature still on its spot): idle animation,
     status 1 with the path kept.
   Since `UpdateMovement` ends the move on status 1, the counter only ever reaches 6 through
   detours.
5. **Back-pedalling**: on a single-segment path (two waypoints) while the animation is a walk
   (10002, 10093 or 10133; never while running), when the goal is less than 2 m away
   (horizontally) and the step direction is more than 135° from the facing (dot < −0.707), the
   direction returned is the reverse of the step direction (so the creature faces within 45° of
   where it faced and moves backwards) and animation 10003 (walk backwards) is set instead of
   turning round. (high for the test, med for the animation's meaning)

### 3.5 The walkmesh queries

The server area keeps one `CSWSRoom` per LYT room (array at area `+0x230`, 0x4c bytes each, count
`+0x22c`; LYT position at `+4`, name at `+0x20`, "no walkmesh" flag `+0x38`, the walkmesh object
`CSWWalkMesh` at `+0x3c`, loaded from `<room>.wok` by `CSWSRoom::LoadWalkmesh` `0x00579520` →
`CSWWalkMesh::Load` `0x00596670`, the loader that also reads placeable PWKs and door DWKs). (high)

| Query | Function | What it does | Conf. |
|---|---|---|---|
| room at a point | `CSWSArea::GetRoomAtPoint` `0x004bb600` | first room whose walkmesh has a face under (x, y): rooms are tried **in LYT order** | high |
| face under a point | `CSWWalkMesh::FindFaceUnderPoint` `0x00581530` | vertical query through the AABB tree (none without one, walkmesh `+0xb0`); when the first query finds no face, retried once with both ends nudged by 0.001 m along (1,1,0)/√2 (meant for points exactly on an edge) | high |
| height | `CSWSArea::ComputeHeight` `0x004bc380` | with the walkable-only flag (as movement passes it) the plane of the face under (x, y), else the room's `GetHeight`; 0 when no room has a face there | high |
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

Movement picks server-side animation ids; the client blends them. Three client routines choose the walk
or run cycle and its playback rate, by who is moving: the client creature's update (`0x0061ad60`) runs the first
for the creature under the keys (`+0x3a8` = 1 and not busy) and otherwise the second for a party member
(`+0x3a4`) whose server twin has FOLLOWLEADER at the head of its queue; the third is the client creature's
position handler (vtable slot 75, `+0x12c`), which the server's dirty-state push calls after the server creature
moved (gameloop.md 2.2). The walk and run rate is always **speed x the cycle's length / the ground one cycle covers**, so the feet keep up
with the ground; what differs is which speed, which distance and who picks walk or run. (high for the shape, med
for the details)

| Who | Routine | Walk or run | Rate |
|---|---|---|---|
| The creature the player drives (the leader under the keys) | `0x00615960` | its forward velocity above 0.6 x its run speed: run (10004), else walk (10002); any sideways velocity plays a strafe cycle (10102–10105), pure backward velocity the run cycle in reverse, no velocity the stand cycle | forward: velocity x cycle length / appearance **DriveAnimRun** or **DriveAnimWalk**; strafe and backward: velocity / run speed |
| A party member (slot 1 or 2) with FOLLOWLEADER at the head of its queue | `0x00615e80` | its smoothed speed (6.2) 0: stand; below 0.6 x its run rate: walk; else run | smoothed speed x cycle length / DriveAnimRun or DriveAnimWalk |
| Everyone else: a creature on a planned path (MOVETOPOINT and everything built on it) | `CSWCCreature::UpdateMovementAnimation` `0x00611f50` | the server's animation id: run when the action's run flag is set, else walk | speed x cycle length / appearance **RUNDIST** or **WALKDIST** x f (the acceleration and braking factor of 3.3, which the client recomputes, `0x0060bf60`; floor 0.1) |

The run speed is the run rate the server last sent the client (creature `+0x210`, mm/s, with the speed effects in it:
`GetRunRate`) and the same figure in m/s at the movement block `+0x5c` (written from the server's message,
`0x006655e0`; until then it holds DriveMaxSpeed × the movement-rate factor). The movement block (`+0x21c`, one per client
creature) is the appearance row's DriveAccl (`+0x58`), DriveMaxSpeed (`+0x5c`), DriveAnimWalk (`+0x60`) and DriveAnimRun
(`+0x64`), filled by `0x00698b10`; a DriveAnim column of 0 reads as 2 (walk) or 4 (run). In stealth mode
the driven creature's velocity is capped to `+0x60` and both cycles are replaced by the stealth walk (10133). The
distance columns are the **metres one cycle covers** (scaled by 1000 against the millisecond length in the code):
the humanoid run cycle is 0.733 s and RUNDIST / DriveAnimRun 3.96 m (5.4 m/s, the Normal run rate, plays at
rate 1.0), the walk 1.067 s and 1.813 m (1.7 m/s), and the stance foot of both moves back at about that speed. The
two column pairs agree for the humanoids and differ for some rows (the Envirosuit's DriveAnimWalk 0.75 and
DriveAnimRun 1.25 against WALKDIST 1.2 and RUNDIST 2.3; the Rodians' 1.7 and 5.4 against 2 and 4). There is **no
blending between walk and run by anything but the speed threshold**: a creature under control passes from the
walk to the run cycle when its velocity crosses 0.6 x its run speed (3.24 m/s for a run rate of 5.4), the walk
cycle playing at up to 1.9 x on the way. A cycle that replaces another starts at the same fraction of its length.
(Not modelled: that, and a run case that reads WALKDIST while the animation is in its first half second.)

| Id | Use |
|---|---|
| 10000 | stand (idle). `GetIdleAnimation` (`0x004f0f90`) asks the client twin when there is one (`0x0060f020`): 10001 when its combat flag `+0x138` is set, else 10092 (injured stand) for a creature under 20 % HP (`GetIsInjured` `0x004eff30`, dialogue.md) unless it is the leader in free-look, else 10000; without a twin, 10001 when `+0x4e0` is set (in combat), else 10000 |
| 10002 | walk |
| 10003 | walk backwards (short reverse moves, 3.4) |
| 10004 | run |
| 10093, 10133 | the other walks (`IsWalkAnimation` `0x004cc1c0`: 10002, 10093, 10133): 10093 is the injured walk (and 10094 the injured run) a party member under 20 % HP uses in the first two routines, except the leader in free-look; 10133 is the stealth walk both cycles turn into |

### 3.7 Forced motion (states 4–6)

`UpdateForcedMotion` (`0x0051c0d0`) slides the creature along a two-point path through
`StepAlongPath` (3.4, so walls and creatures still stop it) at a fixed speed — 25 m/s in state 4,
otherwise the path length × 3.03 per second (the whole slide in 0.33 s) — with no speed factor.
`+0xa90` accumulates the distance covered; `+0xa94` is written as a parabola 4·h·t·(1 − t) of the
progress t with the height h a constant 0.0, so it is always 0: there is **no vertical arc**, and z
follows the walkmesh as in walking. While the step reports 0 it runs the volume checks
(`UpdateVolumesAfterMove`) and moves the creature; on status 1 it moves it without the volume
check, resets `+0xa90` and returns 2 (the AI master then sets `+0xa8c = 1`). For the player's
creature the position is recorded on the party trail. (high)

The effect handlers build the two-point path (path state `+0x8c` = 4 floats), set the state and
call `UpdateMovement(1)` at once (rules.md): FORCE_PUSH (`0x004e3800`) sets state 4, the knock-back;
FORCE_JUMP's internal step (`0x004de0a0`) sets state 5 on the jumper, sliding it to one melee
range short of its target; when that spot is not safe for the target's size (`IsPositionSafe`
through `0x004b4d70`) the jumper slides onto the target's own position instead and the target gets
state 6, pushed one melee range further along the same line (with a MOVETOPOINT to the end point
queued in front and a SETSTATE 13 effect). (high)

## 4. Pathfinding

### 4.1 The path state (`CPathfindInformation`, 0x278 bytes at creature `+0x340`)

Constructor `0x005d0ce0` (the area also builds one). Resets: `Clear` `0x005d0ec0` (everything,
used by `ClearAllActions` and at arrival), `ResetPath` `0x005d0e70`, `ResetSearch` `0x005d0e00`,
`ResetGridSearch` `0x005cefa0`, `ResetPathPoints` `0x005cf060`. Fields (high unless marked):

| Offset | Meaning |
|---|---|
| `+0x00` | flag bit 1 of the move: don't fall back to a partial straight line (4.3 step 6) |
| `+0x04 .. +0x18` | sizes (3.1) |
| `+0x1c` | set while the grid planner plans a PTH leg (4.5): its route is copied unstraightened |
| `+0x28` | the byte parameter 7 of MOVETOPOINT (low) |
| `+0x2c` | the owner creature id |
| `+0x30` | target object of the move (`OBJECT_INVALID` for a point); the creature test of a walk test ignores it, the per-step test does not (4.9) |
| `+0x38` | the creature's current attack target (bigger interaction range) |
| `+0x3c` | planner call counter (> 100 = give up) |
| `+0x58` | "new request" flag |
| `+0x5c..+0x64`, `+0x70` | goal x, y, z and area |
| `+0x68` | arrival range (stop this far from the goal) |
| `+0x6c` | grid goal radius in cells: arrival range / PERSPACE, truncated (`0x005cec90`) |
| `+0x74..+0x7c`, `+0x80` | start x, y, z and area |
| `+0x84` | "the search runs goal-to-start (reversed)"; nothing in the binary sets it to 1, so the reversed paths are dead code (med) |
| `+0x88` | search finished |
| `+0x8c` / `+0x90` | final waypoints: float count / x,y floats |
| `+0x94` / `+0x98` | the raw route before straightening |
| `+0x9c` | next waypoint index (floats) |
| `+0xbc` | object the object tests ignore; `OBJECT_INVALID` from construction, no writer found (med) |
| `+0x194` | plan with the grid only (set when the creature has an attempted attack target, `+0x50c`, and the goal is within 5 m; also by a byte of the player's move message) (med) |
| `+0x198` | flag bit 3 of the move: binary-search the straight line (4.3) |
| `+0x19c` | the cached straight-line result of the first planner call (4.3) |
| `+0x1a4` / `+0x1a8` | nearest PTH points to start / goal |
| `+0x1ac` / `+0x1b0` | PTH node route / count |
| `+0x1e0` | PTH planner state (4.5) |
| `+0x210` | skip the creature test in `TestWalkLine` (4.4); set only around the PTH legs (4.5) |
| `+0x240` | flag bit 10: stop when the target is in sight (3.4); also turns off the stop-short (4.3) |
| `+0x244` | avoidance side (0/1) |
| `+0x254`, `+0x258..+0x260` | the creature currently being avoided and its position |
| `+0x264` | blocker passed to `k_def_pathfail01` |
| `+0x268` | consecutive blocked steps |
| `+0x26c..+0x274` | move deadline (has one, world day, ms) |

### 4.2 The request

`AIActionMoveToPoint` (`0x0051f4f0`, behaviour in actions.md) fills the goal and start, and when
the goal moved by 0.1 m or more (or its area changed) marks a new request, then calls
**`CSWSModule::DoPathfinding(info, 1000)`** (`0x004c6f70`) every frame until it returns 2 (path
ready) or 3 (failed); 1 means "still working, ask again next frame". The time slice is
`g_nPathfindTimeSliceUs` = 1000 µs (`0x00832824`, set by `0x0073b140`). A new request restarts
the search state. `ComputePath` (`0x004c6e20`) builds the area list (KOTOR modules have one area,
so the inter-area part, `0x004c6bd0`, never matters) and calls `PlotAreaPath`. (high)

### 4.3 `CSWSModule::PlotAreaPath` (`0x004c3260`)

All planning is 2D (x, y); z always comes from the walkmesh. (high)

1. Count the call; after 100 calls without a result the request fails.
2. **Stop short**: with an arrival range r > 0.001 and flag bit 10 (`+0x240`) clear, the goal used
   for planning is moved toward the start by r − 0.001 (to the start if it is within r); the stored
   goal is unchanged.
3. **Straight line** (first call only, cached at `+0x19c`): `TestWalkLine(start, goal, PERSPACE,
   HEIGHT)`. Clear (1) → the path is the two points; done.
4. With flag bit 3 (`+0x198`; random walk and flee moves), a blocked line is shortened by
   bisection (fraction 0.5, step 0.25 halving down to 0.005) to the farthest clear point, which
   becomes the goal (the path is the two points). With no clear point at all the line counts as
   −4, which no planner accepts: the request fails (step 6 still applies). This also clears
   `+0x194`.
5. Otherwise a planner, whatever blocked the line (0, −1, −2 or −3): the grid planner (4.6) when
   `+0x194` is set; else **the PTH planner if the area has path points** (`CSWSArea+0x238` > 0,
   4.5), else the grid planner. **A creature at AI level 0** (the lowest, `+0x78`; far from every
   player) gets no planner at all: the request fails and goes to step 6. (high)
6. **Fallback**: if planning failed, flag bit 1 is clear and the cached straight-line result is
   not −1 (walkmesh), the goal becomes the farthest point along the straight line to the stored
   (not stopped-short) goal that a walk test reaches (bisection again); the path is the two
   points. The walk test passes "no creatures", but that argument is ignored (4.4), so creatures
   still block it. (high)
7. A reversed search is turned round (`SwapStartAndGoal`, the point list reversed); unreachable,
   since `+0x84` is never set.

### 4.4 The straight-walk test: `CSWSArea::TestWalkLine` (`0x004bcb70`)

`(from, to, &radius, height, bCheckCreatures, out)` → (high for the codes, med for the
internals):

| Result | Meaning |
|---|---|
| 1 | clear |
| 0 | the start is in no room, or the line leaves the room through a perimeter edge with no room beyond or into a room without a walkmesh (3.5) |
| −1 | the walkmesh blocks (the face walk `CSWWalkMesh::WalkSegment` fails, or non-walkable geometry within `radius` of the line between the segment's z range −0.1 and +`height`+0.1, `CSWWalkMesh::CheckSegmentClearance` `0x005972b0`) |
| −2 | a placeable's PWK or a door's DWK is in the way (`TestSegmentAgainstObjects` `0x00506650`, swept 1000 m tall) |
| −3 | a creature's circle is in the way (`TestSegmentAgainstCreatures` `0x004bc590`, ignoring the path state's owner `+0x2c`, target `+0x30` and `+0x34`) |

**`bCheckCreatures` is never read.** Whether creatures are tested depends on the area's current
path state (`CSWSArea+0x1ac`, set by `PlotAreaPath`, the planners, `IsPositionSafe`,
`FindNearestSafePosition` and the other callers): its `+0x210` set → no creature test; clear →
tested. With no current path state, or with creatures tested and a radius ≤ 0, the result is −3
whenever the earlier tests pass. (high, from the disassembly)

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
   (it stops at the first point beyond the window); every non-empty PTH in the game is (87
   resources, 94 copies across the containers). No point → fail. → state 4.
2. **State 4, graph search.** Same point → a one-node route. Otherwise a bounded depth-first
   search over the graph (`PathPointSearch` `0x004c0b30`, recursive), iterative deepening: the
   cost bound of the first pass is d/2 + 10 (d = start-to-goal distance) and grows by d/4 per
   pass while the time slice lasts; the bound is kept across frames as long as start and goal do
   not change (a later frame resumes at the saved bound + d/2). A branch is cut when its cost so
   far plus the straight-line distance to the goal exceeds the bound, or when a transposition
   table already reached that point more cheaply. The 4096th expansion in a pass → fail.
   Successors come from `GetPathPointSuccessors` (`0x004bdb00`): each link of the point, **dropped
   when a placeable's walkmesh or a static door's (`+0x3c0`) crosses it** (`TestSegmentAgainstObjects`,
   radius PERSPACE); its cost is the link length, or, when a creature's circle crosses the link,
   the length of a dog-leg around that creature (sidestepped by both PERSPACEs); the successors
   are tried **nearest to the goal point first**. The route that came closest to the goal is
   recorded too (not seen used). → state 2.
3. **State 2, first leg.** Straight walk from the start to the first route point: clear → that
   segment; blocked → the grid planner (4.6) for this leg. When the two nearest points differ,
   `+0x210` is set for the leg, so neither the straight test nor the grid detour tests creatures.
   If the leg fails, the first route point is dropped and the leg retried (next frame) from the
   next; with one point left → fail. → state 3.
4. **State 3, last leg**, the same from the goal to the last route point (−3 accepted as clear);
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
  a branch is cut when its cost plus the Manhattan distance |i| + |j| minus the goal radius exceeds
  the bound, or by a transposition table; **a pass stops after 64 expansions** (the overflow flag
  `CSWSArea+0x1cc` unwinds the recursion). Successors are the walkable neighbour cells
  (`GetGridSuccessors` `0x004bcee0`, which test the step with `TestWalkLine`). The goal is reached
  at a cell within `+0x6c` cells of it (Euclidean, in cells), after at least one step.
- The time budget is checked between passes; the best partial path (smallest |i| + |j|) is kept.
  When the first pass of a call took 4× the slice, or 1× without improving the best distance,
  the partial path is copied out and returned as the result (unless that pass overflowed, which
  keeps the search running). The search fails when the bound reaches n + 36, or when the first
  pass of a call took 40× the slice, or 10× without improving the best distance. A reversed
  search fails at once ("we can not return a closest result if points are reversed"; dead, 4.1).
- The cells are converted back to world points and straightened (4.7), except for a PTH leg
  (`+0x1c`), whose cells are copied as they are.

### 4.7 Straightening and corner rounding

Both planners finish the same way (`FinishPathPointRoute` `0x004c17a0` time-sliced at
`g_nPathSmoothTimeSliceUs` = 10 ms, `FinishGridRoute` `0x004c1670`): (med)

1. **Three string-pulling passes** (`StraightenRouteSliced` `0x004c04e0` / `StraightenRoute`
   `0x004c0180`): from the last kept point, find the farthest later point whose straight walk is
   clear (radius PERSPACE + 0.001 for the PTH route, PERSPACE for the grid route; creatures tested,
   `+0x210` being clear by then), trying the farthest first and halving the
   look-ahead after a miss when it is 5 or more, else stepping back by one; skip the points in
   between. The passes are: (a) no pulling, but segments of length ≥ 5.0 (PTH) / ≥ 1.1 (grid) are
   cut into 1 m pieces; (b) pulling plus cutting at 1.1; (c) pulling only.
2. **Corner rounding** (`RoundPathCorners` `0x004bfe20`): at every interior point P with
   neighbours A and B, if the turn is sharper than cos = 0.9 (about 26°), find by bisection the
   largest cut c (start at half the shorter leg, halving the step until it is under 0.1 m) such
   that the straight walk between P + c·(A−P)/|A−P| and P + c·(B−P)/|B−P| is clear, and replace P
   by those two points (`CutCorner` `0x004be3a0`); then try to cut the two new corners once more.

Ours (`paths::route`): A* over the graph in place of the iterative-deepening search, skipping an edge
that an active placeable's walkmesh stands on (`walkmap::meets_placeable`; the original does the same
in `GetPathPointSuccessors`, which drops a link crossed by a placeable's or a static door's walkmesh,
4.5, so a placeable created after the PTH was authored, such as Calo Nord's landspeeders across the
Tatooine camp road, is routed round there too), then string pulling over the route, each shortcut
tested with the walkmesh and every placed mesh.

### 4.8 Safe positions

- `CSWSArea::IsPositionSafe(pos, info)` (`0x004be5e0`): the point (a ±0.01 m box, z ± 0.1) is on
  the floor of a room, and the creature standing there — radius PERSPACE, height HEIGHT — touches
  no wall of any room it overlaps, no placeable or door walkmesh and no other creature's circle.
  (med)
- `CSWSArea::FindNearestSafePosition(pos, radius, info, bNeedLine, out)` (`0x004be860`): the point
  itself (z from the walkmesh) if safe; otherwise square rings around it with half-size 1,
  1 + PERSPACE, 1 + 2·PERSPACE, … while below `radius` (so a radius of 1 or less tries only the
  point itself), sampled every PERSPACE along each ring; the first safe sample wins. With
  `bNeedLine` it must also be reachable from the original point: a clear object sweep plus a
  straight walk that gives 1 or −3 for the samples on the rows below and above the point but any
  result except 0 for those on the columns to its sides (asymmetric in the code; needs a runtime
  check). `bNeedLine` is dropped when the original point is not walkable or overlaps an object.
  The rings in order: a ring of half-size r tries the row below (y − r) and the row above (y + r) at x = cx − r,
  cx − r + PERSPACE, ... up to cx + r, then the columns x = cx − r and x = cx + r at y = cy − r + PERSPACE ...
  cy + r − PERSPACE; r grows by PERSPACE. The first sample of the first ring is the corner (cx − 1, cy − 1).
  (high, from `0x004be860`)
- `CSWSArea::TestSegmentAgainstCreatures` (`0x004bc590`), as `IsPositionSafe` and the walk tests use it:
  creatures from the area's x-sorted creature list (`+0x190`, window ±6 m beyond the segment's x range),
  skipping the path state's owner (`+0x2c`), the move's target (`+0x30`), `+0x34`, dead creatures (vtable
  `+0x94`) and dying ones (`GetIsDying`); with the push flag (its fifth argument) also the ones the owner
  may push aside (`CanPushCreature`). A creature blocks when the segment passes within the owner's
  CREPERSPACE (path state `+8`) + 0.01 + its own CREPERSPACE of its centre. (high for the skips and the
  radius, med for the segment geometry)
  Radii used: 2.0 (planner ends), 1.0 (the client's direct control, point only), 0.5 (DRIVEDIRECT,
  point only), 3.0 (formation moves), 5.0 (pushing; also `AIUpdate`), 20.0 (JumpToPoint's default,
  see actions.md). (med)

### 4.9 Obstacles and blocking

**Per step** (`CSWSCreature::CheckStepCollision` `0x00512fd0`), between the old and new point,
z range −0.1 .. +HEIGHT+0.1, radius PERSPACE. The object test ignores path state `+0xbc` (never
set, so nothing); the move's target (`+0x30`) is cleared for the duration of the check, so even
the creature being walked to blocks: (high)

1. Placeable PWKs and door DWKs (`TestSegmentAgainstObjects`; which DWK state a door uses was not
   read, low). A blocking door whose animation is
   10022 (closed) sends **script event 31 PATH_BLOCKED** to the moving creature with the door as
   caller: its **OnBlocked** script (`ScriptOnBlocked`, creature `+0x290`) runs, which for the
   default scripts opens the door. (high for the event, low for the scripts' contents)
2. Creature circles (`TestSegmentAgainstCreatures`; tested only when no object blocks). A blocking
   creature may be **pushed aside** (`PushCreatureAside` `0x004f6390`) when `CanPushCreature`
   (`0x004f62a0`) allows it: the mover is not the player's creature, the other is not the player's
   creature, not hostile (reputation above 9), not player-controlled (`+0xa88`), has an empty
   action queue, is out of combat (`+0x4e0`) and its combat round is not paused for an attack
   (`+0x958`); and the global switch `0x007a1b34` is off. The other creature is placed off the
   mover's segment, at the closest point plus (both CREPERSPACE + 0.1) sideways, moved to the
   nearest safe point within 5 m that a clear object sweep from its old spot reaches; failing that,
   the nearest safe spot from 1 m behind the mover, searched within 4 m (`0x004c0fa0`); failing
   that, no push. Then the step is retested. (med)

**A creature that stays in the way** (`CPathAvoidance::ResolveBlockingCreature` `0x005d0840`, via
`StepAlongPath`): (med)

- The blocker is hostile (its reputation toward the mover below 11): the mover runs the script
  **`k_def_pathfail01`** with the blocker remembered (path state `+0x264`) and stops; a mover that
  is not commandable (`+0xe8` = 0) goes on to the detour instead.
- Otherwise a detour: a circle of radius (both CREPERSPACE + 0.2, `0x007a2274`) around the
  blocker. If the end of the path lies inside it, the goal is occupied: stop (result −2). Else arcs
  round both sides are built and tested; a clear side beats a side blocked by a creature, which
  beats a side blocked by anything else (a tie keeps the current side), and the winner is spliced
  into the waypoint list. Two creatures avoiding each other coordinate the side through
  `+0x244`: facing the same way, the other takes the opposite side value; facing each other, the
  same value (both step to their own right or left). If the chosen side meets a hostile creature,
  `k_def_pathfail01` runs (with that creature) but the detour stands; if both sides are blocked by
  something other than a creature, `k_def_pathfail01` runs and the move stops.
- After six consecutive blocked steps the move ends anyway (3.4).

**No path at all**: the planner returns 3; AIActionMoveToPoint ends the action (a Force move
teleports the creature to the destination instead; actions.md). Paths are never re-planned because
the world changed, only when a chased target moves (3.2 step 12).

### 4.10 Where to stand to interact

`CSWSCreature::GetUseRange(target, &pos, &range, bNoUsePoint)` (`0x004ee440`) gives the point a move
to an object aims for and the range that counts as arrived (base = own PERSPACE): creature → its
position, range = own CREPERSPACE (or `+0xc` for the attack target) + its CREPERSPACE + 0.3;
trigger → its position for transition triggers, else the nearest point of its outline and +0.5;
placeable → nearest use hook (PWK), range 0.1 if the placeable has use hooks (`+0x33c`), the caller
allows them and the hook is a safe standing point (4.8), else +0.75, then +5 more when `+0x44c` is
set; door → nearest DWK use hook, z snapped, own `+0xc` + base for the attack target, else 0.1 under
the same test (`+0x3c4` and `+0x2c4`), else +0.75; anything else → its position.
`GetIsInUseRange` (`0x004f6000`) requires the same area, adds 0.1 to the extra range, tests
transition triggers as "inside the outline", and otherwise needs a clear line of sight between
points 1.5 m above the creature and above the use point and a 2D distance within range + extra.
Full details are in actions.md. (med)
## 5. Triggers and other volumes

### 5.1 Detection

Volumes are the area's triggers, areas of effect, encounters and transition doors, listed by id
at `CSWSArea+0x1a0` (count `+0x1a4`; triggers are added by `0x0058f030` at load; an id whose
object has vanished is dropped when the inside test meets it, at most one per call). A creature
remembers the volumes it is inside at `+0x330` (count `+0x334`). **Detection runs on every
server-side movement step** — path walking (`UpdateMovement`, `StepMovementUnseen`), follow steps
and the client's direct control (both through `MoveCreatureFromClient`), DRIVEDIRECT steps
(`StepDriveDirect`), combat steps (`StartCombatStep`) and forced motion — not in `SetPosition`.
Jumps (JumpToPoint, JumpToObject, `AddToArea`, `PlacePlayerInModule`) recompute the volumes at the
destination only (`CSWSCreature::UpdateVolumesAtPosition` `0x0051b940`: enter/exit, no crossing;
`AddToArea` sends no events while a save is loading); the areas of effect the creature owns
(its list `+0x324`, count `+0x328`) are moved with it to the destination and stay in its volume
list. A bare `SetPosition` fires nothing. (high)

`CSWSCreature::UpdateVolumesAfterMove(old, new, …)` (`0x0051b7b0`):

1. **Inside now** (`CSWSArea::GetVolumesAtPoint` `0x004bf470`): for each volume, the inside test of
   its type:
   - trigger (`CSWSTrigger::InTrigger` `0x0058ce40`): **traps** (Type 2) are inside when within
     **1.0 m** (`g_fTrapTriggerRadius` `0x007a206c`) of the trigger's position, in 3D; all other
     triggers use an even-odd point-in-polygon test of (x, y) against the outline (vertices at
     `+0x288`, index list `+0x298`, count `+0x294`; z ignored);
   - area of effect: `0x00595450` (vfx_persistent shape); encounter: `0x00590090`; transition
     door: `0x005897d0` (x, y).
2. **Crossed** (`CSWSArea::GetVolumesCrossed` `0x004bf2c0`): triggers, areas of effect and
   encounters (not doors) whose outline the segment old → new intersects (for triggers a 2D segment
   against every edge, `SegmentCrossesGeometry` `0x0058cd80` → `IntersectSegments2D` `0x0058f840`;
   a trap is tested against its polygon here too), so a fast creature cannot step over a thin
   trigger. Path walking passes the crossings `StepAlongPath` (`0x00516630`) collected over the
   segments it walked; DRIVEDIRECT and combat steps compute them here.
3. Only when the creature was or is now inside something: `SendVolumeEvents` (`0x00516020`), and
   the new list replaces the old when it reports a change (any volume left or entered).

`SendVolumeEvents` queues `SIGNAL_EVENT` (10) to the volume, caller = the creature, with no delay,
carrying a script event whose object 0 is the creature; volumes whose object no longer exists get
nothing: (high)

| Case | Event |
|---|---|
| was inside, not now | OBJECT_EXIT (13) — not for doors |
| inside now, not before | OBJECT_ENTER (12) for triggers, AoEs, encounters. A transition **door**, and an area-transition **trigger** entered by a DRIVEDIRECT step (the only caller that passes the "click" flag): CLICKED (30) when the creature is the client party's leader (index 0); for any other party member (`+0xa88`) nothing, and the "changed" result is reset, so unless a later volume sets it again the member's volume list is not updated and it re-enters on its next step (med); for a creature outside the party the event is queued with its type never set (med, needs a runtime check) |
| crossed, neither before nor now | OBJECT_ENTER (CLICKED for a transition trigger crossed by a DRIVEDIRECT step, with no leader test; doors are never "crossed") then OBJECT_EXIT |
| crossed, inside before and now | OBJECT_EXIT then OBJECT_ENTER (or CLICKED, as above) |

(The script-event route replaces the `ENTERED_TRIGGER`/`LEFT_TRIGGER` event ids 2/3 of
objects.md, which this code does not use; the trigger's event handler has no case for them. med)

### 5.2 What a trigger does

The trigger fields that matter (`CSWSTrigger::LoadTrigger` `0x0058da80`, objects.md 3): `Type` 1 →
`+0x2b4` (area transition, cursor byte `+0x2fc` = 1), 2 → `+0x2bc` (trap, cursor 0), only when the
field is present; `TrapType` `+0x2d4` (traps.2da row; its `TrapScript` replaces an empty or
"default" `OnTrapTriggered`), `TrapOneShot` `+0x2d0`, `LinkedTo` `+0x230`, `LinkedToFlags` `+0x240`,
`LinkedToModule` `+0x238`, `Faction` `+0x2b8`, `KeyName` `+0x27c`, `AutoRemoveKey` `+0x2cc`,
`HighlightHeight` `+0x2e0` (default 0.1, kept only when above 0), `LoadScreenID` `+0x308`, `OnClick`
`+0x274` (a missing field defaults to the OnEnter script), `Geometry` (`LoadGeometry` `0x0058d060`:
each point's `PointX/Y/Z` plus the trigger's position, no rotation; the index list is 0..n−1).
The GIT entry with templates (`CSWSArea::LoadTriggers` `0x0050a350`) sets the position first and
then reads `Geometry`; `LoadTrigger`'s rotation by the orientation fields only touches vertices
already loaded, so a freshly loaded outline is never rotated. (high)

`CSWSTrigger::EventHandler` (`0x0058f140`) for the SIGNAL_EVENT script events: (high unless
marked)

- **OBJECT_ENTER (12)**: the entering object id goes to `+0x29c` (GetEnteringObject). Every
  OBJECT_ENTER ends by setting the trigger's client removal reason to 1 (`0x004ce8a0`).
  - generic trigger: run `ScriptOnEnter` (`+0x24c`);
  - **trap**: `CSWSTrigger::OnTrapEntered` (`0x0058d570`): only creatures. The creature sets it off
    (`0x0058d4a0`) unless it is immune to traps (immunity type 5, checked always) and when either
    the event's int 0 ("force") is set, or the trap's creator (`+0x2e4`) has no faction, or its
    reputation toward the creator (the trap itself without one) is 10 or less and it is not of the
    trap's faction (`+0x2b8`); detection is not checked. A creature carrying an item tagged KeyName
    (inventory, then the 18 equipment slots) disarms it instead: AutoRemoveKey removes and
    destroys the key, disarmer `+0x2a4` = the creature, OnDisarm runs, and event 11 at 0 ms
    deletes the trap. Otherwise: feedback 0x52 (1461 "You triggered a Mine!") to the victim,
    OnTrapTriggered (`+0x264`) at once as the trap (GetEnteringObject `+0x29c`), then ScriptOnEnter
    too; a one-shot trap gets event 11 at 0 ms (destroyable `+0xec`: removed from the area,
    deleted). The client sees removal reason 1 in both cases (`0x0064f960`: the mine plays its
    animation 0x15c, `activate`, and traps.2da ExplosionSound; reason 2, from the disarm actions,
    plays 0x15d, `deactivate`). Script event 26 is not handled by triggers (only by trapped doors
    and placeables). (high)
  - **area transition** (movement side; the switch itself is gameloop.md 5.2): if the entering
    object is not a creature or a conversation is running (in-game GUI `+0xb4`), the area's
    pending flag is cleared and nothing else happens; with an empty `LinkedToModule` nothing
    happens at all (not even ScriptOnEnter). If the area has no transition pending (`area+0x2c4`):
    only the PC (`+0x9d4`) or the party leader (`CSWPartyTable::IsCreatureLeader`) goes on; when a
    party member is more than **30 m** from the leader (`AreMembersNearLeader` `0x00635350`, 3D),
    the creature runs **`k_trg_transfail`** as `OBJECT_SELF`; otherwise a fade to black over 0.5 s
    starts (`StartGlobalFade` `0x0062abf0`), the area is marked "transition pending" with a fresh
    token (`NextTransitionToken` `0x00506ac0`, `SetTransitionPending` `0x00506b30`, which also
    disables client input), the player pause is forced off (`SetPauseState(2, 0)` `0x004ae9a0`)
    and a second OBJECT_ENTER is queued to the trigger **500 ms** later (caller = the trigger,
    int 0 kept, int 1 = the token). When that one arrives with a matching token and the creature
    is neither dead nor dying, the server requests the module transition with `LinkedToModule`
    and `LinkedTo` (`0x004aecc0` / `0x004aecd0` / `0x004aed30`) and clears the pending flag; if it
    died meanwhile, the fade panel is removed (`0x0062ac40`) and the flag cleared; another token is
    ignored. Walking into the polygon is therefore enough — no click needed.
- **OBJECT_EXIT (13)**: exiting id at `+0x2a0`, run `ScriptOnExit` (`+0x254`).
- **USER_DEFINED (11)**: number at `+0x2f8`, run `ScriptUserDefine` (`+0x25c`) with the event's
  caller (the object that signalled it) as `OBJECT_SELF`, not the trigger (med, needs a runtime
  check).
- **DISARM (24)**: disarmer (the event's caller) at `+0x2a4`, run `OnDisarm` (`+0x26c`).
- **CLICKED (30)**: clicker at `+0x29c`, run `OnClick` (`+0x274`); for transition triggers an empty
  or "default" script becomes **`NW_G0_Transition`** (stored back into the field), and a non-zero
  LoadScreenID is passed to the clicker's client object (`0x00560cd0`). CLICKED comes from a move
  whose target was the trigger (3.2 step 12) or from a DRIVEDIRECT step into a transition trigger
  (5.1).
- TIMED_EVENT (1): runs the queued script situation (DelayCommand on the trigger); DESTROY (11
  event id): removes it from the area and deletes it when destroyable (`+0xec`).

A trigger's heartbeat comes from its own `AIUpdate` (`0x0058d760`), not read here.

### 5.3 Encounters and areas of effect

Both are volumes in the same list, with their own inside and crossing tests (`CSWSEncounter::
InArea` `0x00590090` / `SegmentCrosses` `0x0058ffd0`; `CSWSAreaOfEffectObject::InArea`
`0x00595450` / `SegmentCrosses` `0x005950c0`), so they receive the same OBJECT_ENTER/EXIT events;
what an encounter spawns on entry is the encounter's event handler (`0x00594220`), not covered
here. (med)

## 6. Party following

### 6.1 The pieces

- The **client party table** (`CClientExoApp::GetClientParty` `0x005ed8b0`, the internal client's
  `+0x270`): a count at `+0`, up to three 0x88-byte entries from `+0x24`, index 0 = the leader. Per
  member: `+0x00` id, `+0x04` follow state, `+0x08` its distance along the trail, `+0x18` A (its
  place on the leader's trail, trail index `+0x24`), `+0x28` B (the follow point, trail index
  `+0x34`), `+0x38` its formation offset, `+0x44` stuck counter, `+0x48` smoothed speed, `+0x4c`
  remembered facing, `+0x5c` C (its planned position), `+0x68` reset flag, `+0x70` a re-plan flag
  (state 5), `+0x74` the leader position at the last re-plan. A trail object at `+0x2dc` records
  the **leader's trail**: 100 records of 0x28 bytes (count at trail `+0xfa8`);
  `RecordLeaderPosition` `0x00636a30` adds the leader's position and facing after each move
  (MoveDirect, path and forced-motion steps); `GetTrailPoint` `0x006350f0` hands out trail points;
  `0x00634cc0(n)` returns record n (heading at `+0xc`). (med for the table, low for individual
  fields)
- **Formation offsets.** The client party's constructor (`0x00636170`) fills three formations at
  `+0x1c8` (0x24 bytes each: the offsets of follower 1 and follower 2) and a float per formation at
  `+0x234` (1.5 for all three), then selects formation 0 (`0x00634760`, which copies the pair into
  entries 1 and 2's `+0x38` and the float into `+0x1c0`, and swaps the pair when the mirror flag
  `+0x1c4` is set; `0x006346f0` negates both x and flips that flag). Formation 0: follower 1
  (1.5, −0.7, 0), follower 2 (−1.5, 0.8, 0); formation 1: both 0; formation 2: (−2, 1.5, 0) and
  (2, 4.5, 0). The offset is turned by the quaternion that takes (0, 1, 0) to the heading (y ahead,
  x to the right; `0x006348c0`, `PlacePartyAroundLeader` `0x00565b00`). A restarted trail
  (`CSWCPartyTrail::Reset` `0x00637890` → `0x00637630`) puts follower 1's follow point 1.5 m and
  follower 2's 3.0 m behind the leader (nearest safe spots within 2 m) and records them, so with
  formation 0 both followers stand 2.2 m behind the leader, 1.5 m to either side. Who calls
  `0x00634760` with another formation, and when the mirror flips, was not traced. (med)
- Each follower runs action **FOLLOWLEADER (0x3d)** (`AIActionFollowLeader` `0x00511130`): for a
  party member (`+0xa88`) with a follow record, alive, not dying, with a path state and able to
  move, that is not the player's creature (`GetPlayerCreatureId`, the controlled leader), it sets
  `+0xa8c = 3` and stays running; the player's creature fails it at once (actions.md 3.3). From then
  on `UpdateMovement` calls **`CSWSCreature::UpdateFollowLeader`** (`0x0051c360`) every frame. (high)

### 6.2 One follower step (`UpdateFollowLeader`)

1. Not in the party table → keep waiting; the leader → done; a zero frame time → keep waiting. A set
   reset flag first puts C at the creature's position.
2. **Speed** (mm/s). L is the leader's client speed (`+0x3b0`, m/s); A the follower's place on the leader's
   trail (entry `+0x18`, which `FUN_00634e80` moves along the trail by the frame's distance toward B); B where
   that walk ends (entry `+0x28`: the follow point behind the leader); d the straight distance from A to B (what is
   left to walk); C the follower's planned position (`+0x5c`, which the state handlers advance). The pace before
   the factor, `base`:
   - d at least 4 m, or B 10 m or more from C (**catch-up**): the run rate; L when the leader moves (above
     0.1 m/s) faster than that.
   - Else, leader moving: L.
   - Else (leader standing): d under 3 cm: 0.6 x the run rate (`g_fFollowCloseRunFactor`, `0x007a22f4`);
     otherwise the follower's smoothed speed, at least 0.9 x the walk rate (so a follower that has to walk a
     metre or two to a standing leader moves at 0.9 x 1.2 x 3.2 = 3.46 m/s, a companion's walk rate being
     PC_Movement's 3.2 (3.1), its cycle the walk's, as the smoothed speed is capped at 2.88, below 0.6 x 5.4; one
     that was running goes on at its running pace and slows over the last metre).
   - The speed is `base` x 0.9 (d up to 1 m), x 1.2 (up to 15 m) or x 1.5 (beyond).
   There is no acceleration ramp and no braking (3.3 belongs to MOVETOPOINT): the speed applies from the first
   frame. In a steady chase the follower hovers about 1 m from its follow point, its speed flipping between 0.9 L and 1.2 L,
   so its mean is L. (high for the structure and the constants, med for what A and B are)
3. **Follow state machine** (the path state's `+0x34` is set to INVALID — the other follower's id
   is looked up but not used —, area `+0x1ac` = this path state, entry `+0x58` = 1.0): the entry's
   state (0..10) picks a handler (`FollowState*` `0x00511290` … `0x00512de0`) which consumes the
   frame's distance and may move to another state in the same frame (the loop goes on while the
   handler returns 1 and distance is left); every round adds 1 to `+0x44`, states 6–10 clear it,
   and more than 50 rounds (`+0x44` > 50) set the state to −1, which next round puts C at the
   creature's position and goes to state 5. Known states (low unless marked):
   - 0 `MoveToFormationPoint` (`0x0051ac10`): the formation point = B + the member's offset
     (`+0x38`) rotated by the heading of B's trail record; if that spot is not safe, the nearest
     safe point within 3 m of B instead (state 7, else state 6). It queues to the front a
     CHECKFORMATIONPOINT (0x40, range 0.5) and before it an ordinary MOVETOPOINT run there (group
     0xfffe, a 30 s timeout parameter), sets `+0xa8c = −1` (ordinary path walking until the move
     is done), records the leader's position at `+0x74` and sets the reset flag — a far or stuck
     follower **pathfinds**. (med)
   - 5 (`0x005127d0`): only once the trail holds more than 4 records: puts A and B on the trail
     point at the follower's trail distance (`+0x08`); when the leader is 7 m or more from the
     follower (or `+0x70` is clear) it computes the formation point (that point + the offset
     rotated by its heading) and goes to 4 if a straight walk from C reaches it, 2 if the trail
     point can be walked to from C, else 0 (in the same frame).
   - 1–4, 6–10: walking along the trail and toward the formation point (not read in detail).
4. **Moving the creature to C.** C within 3 cm of the creature: it is set on C if the straight walk
   is clear. Otherwise, if the straight walk between C and the creature is clear, the creature moves
   **halfway** to C (x, y; the height recomputed; factor `0x007a1b58` = 0.5); if it is blocked but C
   is a safe spot, the creature is set on C; else it stays and `+0x44` rises. `SetPosition` writes
   the position, then `MoveCreatureFromClient(old, new)` runs the volume bookkeeping (triggers fire
   for followers too, 5.1). If the follower did not move (x and y unchanged) it turns its head toward
   the leader within 8 m and keeps its facing, else it faces its walking direction and `+0x44` is cleared. The
   **smoothed speed** `+0x48` is the speed made this frame (the horizontal step's length over the
   frame time, mm/s) averaged with the old value (this frame's alone when it is 0.0001 or less), 0
   below 10 mm/s, and then capped by the pace before the factor (`base`, the stack slot traced in
   the assembly; the decompile names the wrong slot), which keeps the animation at the leader's own
   pace while the follower hurries at 1.2 x or 1.5 x. The cycle (3.6) follows this speed: walk below
   0.6 x the run rate, run above, the rate speed x cycle length / DriveAnim. (med)

**Ours** (`lib/engine/trail.ctx`; `movement::follow_pace`, `settle_follow_gait`): the leader's place is recorded
once a frame when he has gone 0.25 m from the last record (100 records; a new leader, another area or a jump of
more than 3 m restarts the trail with the two seeded follow points, as `Reset`). Follower n's follow point B is on
the trail 1.5 × n m behind the leader's place, its formation point B + formation 0's offset turned by the heading
of the record there (B itself when that spot is off the walkmesh or not in a straight walk from B; the original
looks for the nearest safe spot within 3 m). FOLLOWLEADER queues a MOVETOPOINT to the formation point (range 0.5,
CHECKFORMATIONPOINT's) flagged as a follower; the move takes the formation point afresh every frame, is not done
while the leader moves, and plans its way along the trail: straight when it can, else onto the trail at the
record nearest B that it can walk straight to (within 15 m), along the records to B and on to the formation point,
else a planned path (state 0). d is the path still to walk less the 0.5 m; the rules above give the speed, the
smoothed speed (kept in `follow_speed`, 0 whenever the follower stops), the cycle and its rate. The follow state
machine's states are not reproduced one by one, and the creature walks its path rather than moving halfway to
C each frame. The order to follow still comes from `ai::wake_follower` (leader over 4 m away, queue empty for a
second), not from the first step the leader takes as in the original, so a follower starts a few metres behind
where the original's would be and walks or runs in by the same rules.

There is **no teleport** of a far follower in this code: it pathfinds instead (state 0); the only
direct placement is step 4's hop onto C, which stays within about a frame's walk. Script and
module-transition code place party members explicitly. (med)

### 6.3 Switching the controlled character

ChangeChar (Tab) → `CClientExoAppInternal::CyclePartyLeader` (`0x005f7960`, one step): the leader
slot is rotated to the next member (`CClientExoAppInternal::SetPartyLeader` `0x005f6b60` with −2,
"next"); a dead or dying member is skipped at the cost of one of 3 × the step count tries (3 for
Tab). On a change (`0x005f6b60`): the party table's leader index changes, the leader trail is
restarted at the new leader's position and facing (`0x00637890`), the new leader's path state
`+0x34` is cleared and its FOLLOWLEADER actions are removed (`RemoveActionsById(…, 0x3d)`
`0x004f76c0`), the camera retargets (`SetCameraTarget`) and the player control object
(`client+0x2a0`, its slot 11) is told (`OnControlledCreatureChanged`). The old leader gets
FOLLOWLEADER from the party code (not traced, low). (med)

## 7. Selection and targeting

### 7.1 Selectable objects

(The target reticle and the action buttons are drawn by the main interface panel, see
[gui.md](gui.md); this section covers what feeds them.)

Every frame `CClientExoAppInternal::UpdateSelectableObjects` (`0x005fa5a0`, from `MainLoop`) asks
the server leader for the objects within **30 m** (`CSWSCreature::GetNearbySelectableObjects`
`0x004fc4c0`, walking the area's x-sorted object list `+0x190` outward from the leader, the whole
list, with no early stop) and stores them at `client+0x2a8` (12-byte entries: `+0` client id, `+4` a
cached visibility byte, `+8` flags; count `+0x2ac`), in order of their bearing from the leader's
facing (the bearings themselves are not kept). Selectable (`GetIsSelectableTarget` `0x004f2c30`,
by the object-type byte): (high)

| Type | Selectable when | Hostile flag |
|---|---|---|
| creature | alive (slot `+0x94`), not dying, and seen by the leader (perception entry bit 0) or seen now by the sight check (`0x004f1fd0`) | friend-or-enemy 2 (`0x0057cd90`: the creature's reputation toward the leader below 11) |
| trigger | traps only (`+0x2bc`): the leader is in its detected list (`+0x2a8`), or its reputation toward the leader is above 89 (e.g. the party's own mines), or it has the leader's faction. The pointer's scene pick (7.2) also takes a mine only while it plays animation 10144 (`detect`: `CSWSTrigger::AIUpdate` `0x0058d760` sets 10144 when flagged `+0x2c8`, of the player creature's faction, at reputation 90 or more, or the player creature is in its detected list, else 10143 `default`) | never set here; the client's hostile flag for a trap is sent with the object update: a trap of another faction with reputation below 90 (`0x00577000`, `0x00574a10`) |
| placeable | useable (`+0x328`) | reputation toward the leader < 11 with the flag `+0x340` set |
| door | closed (`OpenState` `+0x2cc` = 0) and not static (`+0x3c0` = 0) | — |

Items are not selectable on their own (KOTOR keeps them in containers). The same pass watches for
mines (`0x005fa83a`): a selectable trap with the hostile and trap flags (client trigger `+0x108`)
that passes the leader's visibility test, while nothing is paused and no auto-pause waits and the
"mine in sight" latch (`+0x328`) is clear, becomes the current target; with the Mine Sighted option
(ini bit 0x2000) and out of combat mode (`+0x320`) the game also pauses with reason 11 (49118). The
latch clears after 10 s (`+0x3a0`) with no such mine seen. (high) If the current target is a creature
that died (dead or dying) and left the list while a hostile creature is in it in combat mode, it is
kept for 1.5 s (`+0x378`) before a new target is picked automatically; while that timer runs every
creature counts as hostile for the target kind (7.4) and the reticle. (high)

**What decides who is selectable and visible** (read from `0x004f2c30`, `0x004fc4c0`, `0x00617ad0`,
`0x00502ac0`; high). `GetNearbySelectableObjects` fills two lists from the x-sorted area list,
skipping the leader: every selectable object within 30 m, sorted by bearing (degrees from the
leader's facing, 0 up to 359, ascending), and the **front list**, the objects with a non-negative
dot product with the facing whose direction from a point **4 m behind** the leader makes an angle
under 30 degrees with the facing (cos > 0.866), sorted by distance. A creature is selectable when
it is alive, not dying, and the leader's perception entry for it has its seen bit **or** the
sight check `0x004f1fd0` says the leader sees it now. For the player's creature the perception
check (`0x00502ac0`) skips the range gate and the line test (gameloop.md 2.4), and its sight test
then asks only for the PC's sight range, 250 m (ranges.2da row 12; eyes 1 m up), so everything in
its area within 250 m that does not out-stealth it (rules.md 5.3) is seen; what keeps a PC leader
from selecting what is behind a wall is the client's visibility ray,
`CSWCCreature::GetIsTargetVisible` (`0x00617ad0`): a ray from the leader to the object, clipped
against the rooms' walkmeshes (`0x0060f1e0`; med, its decompile is garbled) and cast through the
scene with the leader's and the object's own models left out. The first hit decides: level
geometry (a hit with no game object) or a **closed door** (`OpenState` 0) means not visible; an
open door or a placeable is added to the left-out models and the ray is cast again; any other
object (another creature) counts as visible (asm `0x00617d03`–`0x00617dc1`). Visibility is cached
per entry per frame; the pointer's list pick (`ProcessInput`), `CycleTarget` (invisible entries are
dropped) and the auto-target below all use it.

**What the client does every frame** (`UpdateSelectableObjects`, from `MainLoop`; ours:
`lib/hud/autotarget.ctx`). Read in full, with `GetNearbySelectableObjects` and
`SelectTarget` (high):

1. *The two lists.* The server leader's `GetNearbySelectableObjects(30, 30)` (the range for hostile
   objects, then for the rest) gives the **all list**
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
   out-of-view timer (`+0x368`) is 0; when it is not, the timer counts the world's frame time (0 while paused, below) and at 1.0 the target is
   dropped and picked afresh. Nothing in this function prefers a nearer object over a kept target, and
   a clicked target is no stickier than an automatic one: the same value, the same rules. The one extra
   with enemies in combat mode: a target that left the list (it died) is kept for 1.5 s while a hostile
   creature is still in the list (`+0x378`).
3. *A hostile coming into sight* overrides the above. The scan runs when the list holds a hostile creature
   or a hostile trap; it then walks the all list in bearing order and takes the first visible entry whose
   client hostile flag (virtual slot `+0x138`) is set, mines handled apart (7.1): when the *sighting latch*
   (`+0x324`) is clear and nothing is paused or auto-paused, it becomes the target and is selected with both
   flags of `SelectTarget` set (the leader's creature is handed the object, and the chase camera swings
   toward it even out of combat mode); the "enemy sighted" tutorial (0x15) is offered, and with the Enemy
   Sighted option (`0x1000`) and combat mode (`+0x320`) off it asks auto-pause reason 1. The latch is set
   while any visible hostile is in the list and clears when none has been for 10 s (`+0x394`). A
   placeable's client hostile flag is its `+0x340` alone, without the reputation test of 7.1, so a visible
   placeable with that flag can be the "hostile" taken here (med, needs a runtime check).
4. *Picking a new target* (no target, or it left the list or view): out of combat mode, or with no hostile
   creature in the list, **the first visible entry of the front list**, nearest first. In combat mode with a
   hostile creature in the list: the first visible *hostile* in the front list; else the first visible
   hostile in the all list (bearing order); else the nearest entry of the front list that is not hostile
   (this last one without a visibility test). Nothing found: no target, and the HUD target is cleared.
   The pick is made by `SelectTarget(object, 1, 0)`: it sets the HUD target (`CGuiInGame::SetHudTarget`),
   hands the leader's client creature the object with a duration of 10 s (`FUN_006146e0`, a look-at; not
   traced further) and, only **in combat mode**, swings the chase camera toward it (`TurnTowardObject`
   `0x00639c30`); in combat mode a hostile creature target also gets a 0.25 s entry in the list at
   `client+0x314` and a call of its slot `+0xa4` (not traced). A kept target is passed to `SelectTarget`
   again with both flags 0, so the camera never moves for it, with one exception: a target set through
   `SetTarget` (`0x005f4a20`) with its "new" bit (`+0x37c` bit 0, cleared at the end of every pass) gets
   `(1, 0)` on the next pass. The server sets it that way when a combat round moves the attack to a new
   enemy (`0x005b6980`); the turn in `SelectTarget` fetches the controller of type `0x106a` (the chase
   camera), which `StartCombatCamera` (`0x00641540`) has replaced in combat mode, so nothing turns
   (the condition on combat mode in `SelectTarget` only ever finds a chase camera out of it). A click sets
   it without the bit.

**While the game is paused** (any pause bit, the player's or an auto-pause; high, read from the asm).
`UpdateSelectableObjects(float fDelta)` and `ProcessInput(float)` are both handed `g_fFrameDelta`
(`0x0078e574`: the client world timer's `GetFrameDelta` (`+0x24`) times 1e-6, which is 0 while that timer is
paused, [gameloop.md](gameloop.md) step 4), by `MainLoop` at `0x00603b61` and at `0x00603323` / `0x006033ac`.
Every timer of the auto-target adds or subtracts that argument (`[ESP+0x68]` in `0x005fa5a0`, `[ESP+0x134]`
in `0x006227e0`): the out-of-view second (`+0x368`, `0x005fac66`), the 1.5 s keep of a dead target (`+0x378`,
`0x005fa862`), the sighting latch (`+0x394`, `0x005fab12`), the mine latch (`+0x3a0`, `0x005fab5d`) and the
walking drop (`+0x36c`, `0x00623cd9`). So a pause freezes them all: the walking drop cannot fire while paused,
whatever the keys did when the pause came, and a target out of view is not given up. The rest of the pass
still runs every paused frame (input class 0, no fade): a target that leaves the list is replaced at once,
and an empty target is picked by the step 4 rules; the sighting (step 3) waits for the unpause. Hence a
target the player clicks while paused (`OnWorldClick` is not refused by a pause) stays until he unpauses.

**What the auto-target may choose, and clicks** (high, from the functions above). Dead or dying creatures are
never in the list (`GetIsSelectableTarget`), so a corpse is never a candidate. What a dead creature leaves
is another matter: when it is destroyed, `SpawnBodyBag` (combat.md 8.4) puts down a placeable holding its
drops, useable, so it is selectable like any useable placeable and the auto-target may pick it. There is no
hostile-first priority out of combat mode: step 4 takes the nearest visible object in the front cone, a
body bag or a footlocker as readily as a Sith; only the sighting (step 3, which also asks the auto-pause)
and combat mode's picks prefer hostiles. A click holds no better than a pick (step 2): no timer and no flag
lock it; it is let go when it leaves the list (death, 30 m, not selectable), after a second out of view, or
by the walking drop below, all three on the world's clock.

**The target drop that makes the auto-target follow a walking player** is not in that function but in
`ProcessInput` (`0x006227e0`, the branch that steps the player control, near its end): each frame, when
the leader is **not in combat mode**, the HUD target is not none, the deferred auto-pause (`+0x390`) is
not running (`RequestAutoPause` sets it to 1 s for a request made in the 5 s door window, and client step 27
counts it down, [gameloop.md](gameloop.md) 6.4) and the player control's current speed (`CSWCPlayerControl::GetCurrentSpeed` `0x00679750`, the
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
selectable object that is not the target is the select cursor (0x2d); over the target, the default
action's (7.2).

### 7.2 Hover picking

`ProcessInput` works out the object under the cursor every frame and calls `SetHoverObject`
(`0x006222f0`): hover id `client+0x4a4`, hover point `+0x4a8`, and the cursor. The cursor (outside
dialogue and free look): when the hovered object is the current target and no GUI control is under
the pointer, `BuildDefaultActions` (7.4) is run for the HUD target and its entry 0's code picks the
cursor (`GetCursorForAction` `0x0061faa0`: talk `0x3ea` → 0xb, attack `0x3eb` → 0x33, open door
`0x3f2` → 0x17, disable mine `0x3f4` → 0x21, bash `0x3f5` → 7, use `0x3f7` → 0x19, recover mine
`0x402` → 0x25, anything else, "no action" included → 5); any other object of the selectable list
gives the select cursor 0x2d; anything else the default cursor. The pick has two routes (high for the
flow, med for the per-type rules):

1. *A scene ray under the pointer* (a `CAurRayQuery` cast by the camera) takes the model it hits by
   type: a creature (one whose client `+0x3dc` names a body bag hovers that bag instead, hidden
   behind the body or not; one with none, dead or dying, is refused while it is in the area's
   corpse ring, which `0x00604bc0` searches: actions.md 3.15; high); an item; a trigger, a mine only while it plays 10144
   (7.1); a placeable only when useable (client `+0x128`) and not static (server `+0x398`), and one that
   is not is left out and the ray cast again when its placeables.2da row has a non-zero value in a
   column not identified (`DAT_007a225c`; low); a door only when not open (10050 / 10051) and its
   `+0x138` is clear. This route does not consult the selectable list. Its hover reticle (`+0x5cac`)
   is set only when the object is in front of the camera and within 30 m (squared distance 900) of the
   player's creature, and no GUI control is under the pointer.
2. *Otherwise* the pick walks the **all list** of 7.1 (only the visible entries), asks each entry's
   client object for its screen bounds (slots `+0x13c`, `+0x144`) and keeps the one nearest the camera
   that the pointer is over; its reticle is set unless a GUI control is under the pointer (over the
   target, only when the target's first action slot is filled, 7.1).

Over the main interface's target block (`0x00684ed0` answers 1) the hover is the current target; over
a party portrait (answer 2) nothing; over any other GUI control the world pick above still runs, but
its reticle is hidden. The id goes to the main interface (`+0x5cac`), where it hangs the hover
reticle (7.1). How the screen bounds of route 2 are computed was not read.

### 7.3 Target cycling

Q / E → `CycleTarget(bPrevious, filter)` (`0x005fb050`): through the selectable list in its order
(by bearing), wrapping around, from the current target (`client+0x2b4`; with none, next starts at
the first entry and previous at the last). Input events 204 / 205 (`HandleInputAction`), not in
free-look. The filter is 0 (anything) normally and 2 (hostile creatures only) **in combat mode**; when
the list holds no visible hostile creature the filter falls back to 0. Entries whose cached
visibility test (`0x00617ad0`) fails are removed from the list. The chosen object becomes the target
through `SelectTarget(object, 1, 1)` (`0x005f9c60`), which starts the camera auto-turn toward it
(2.3) in or out of combat mode. In combat mode with the options bit `+0x16` bit 0 set, a cycle also
asks auto-pause reason 8. (high)

### 7.4 Default actions and clicks

`BuildDefaultActions` (`0x00620620`) fills the action list of the HUD target (main interface
`+0x64`) at `client+0x4c8` (0x38-byte entries: `+0` label text (the strref's string), `+8` action
code, `+0xc` callback, `+0x1c` target id, `+0x20` icon resref, `+0x30` flags; count `+0x4cc`) by the
target kind (`GetTargetKind` `0x0060fcc0`: a creature is 4 when its client hostile slot `+0x138`
answers or the 1.5 s keep timer `+0x378` runs, else 3; a door 1; a placeable 1 with an inventory
(server `HasInventory` `+0x324`), else 3; a trigger 2; nothing 0). It runs only from `SetHoverObject`
while the pointer is on the target and from R (event 239), so a click uses the list built while the
pointer was there. (high for the table, med for the callbacks' behaviour)

| Kind | Target | Actions (icon) | Code | Callback |
|---|---|---|---|---|
| 0 | none | "no action" (`i_noaction`, strref 32236) | `0x404` | — |
| 1 | door | open (`i_opendoor`, 365) unless `0x0061f790` (the door's animation is already an open one, 10050 / 10051) or `+0x138` refuses it; then, only with open offered, bash (`i_attack`, 368) if not plot (`+0x104`), **locked** (`+0x108`: the same flag gates the Security entry, so it is the Locked field, not a "bashable" one) and the area's RestrictMode (server area `+0x2b0`) is 0 | `0x3f2` / `0x3f5` | `CSWCDoor::DefaultActionOpen` `0x00683d90` cancels the leader's actions and sends the door message (6,3) with 10021 (open) when the door shows 10022, or 10022 (close) when it shows an open animation (a locked door is refused by the server: locked feedback, OnFailToOpen; there is no unlock in this list) / `0x00683e90` |
| 1 / 3 | placeable | with an inventory: open (`i_openplace`, 365) if useable (client `+0x128`), then bash (368) if not plot (`+0x110`), RestrictMode 0 and locked (`+0x118`). Without one: use (`i_useplace`, 366) if useable and not a corpse (server `IsCorpse` `+0x44c`), then bash if not plot and RestrictMode 0, locked or not (med, needs a runtime check). With an inventory, the entries' flags (`+0x30`) are changed (bit 0 cleared, bits 2–3 set) when the player creature is not the leader, has `+0x3a4` set and its server creature passes `0x004ef890`, and the placeable is not `PartyInteract` (low: meaning) | `0x3f7` / `0x3f5` | `CSWCPlaceable::DefaultActionUse` `0x00682660` (use-object message (6,0xb), not inside a `NoClicksFor` window) / `0x006826a0` |
| 3 | friendly creature | talk (`i_dialog`, 371) | `0x3ea` | `DefaultActionTalk` `0x0060f620`: not inside a `NoClicksFor` window (in-game GUI `+0xbcc..+0xbd4`, `0x0062f9a0`), with no dialogue pending (`+0xb4`) and the creature's `+0x138` clear: clears the **target's** server actions, turns the target to face party member 0 (when its server `+0x21c` and `+0xe8` are set), sends (6,8) and marks a dialogue pending |
| 2 | mine (any client trigger) | disable (`i_disablemine`, 370) when the mine is hostile, recover (`i_recovermine`, 1531) on any; both need the leader's Demolitions (skill 1, `0x006477e0`). In the target block (`0x00691f00`) Disable is the left slot, Recover the middle, the right empty; no flag or examine | `0x3f4` / `0x402` | `CSWCTrigger::DefaultActionDisarm` `0x00691900` / `DefaultActionRecover` `0x00691950`: input message (6,7) (`0x00677b10`: skill byte 1, sub-skill byte 0 / 101, the mine's id, a zero point; 0x12 is the buffer size), which the server hands to `UseSkill` (actions.md 1.7) |
| 4 | hostile creature (or any creature while the auto-target timer runs) | attack (`i_attack`, 375) unless the area forbids combat (server area `+0x2b0`) | `0x3eb` | `CSWCCreature::DefaultActionAttack` `0x00616800`: after the attack tutorials (0x23, 0x22), combat mode on (`SetCombatMode(1)`) and the attack message (6,2) |

- **The target block's slots are not this list** (per target in gui.md, "What the target block offers, by target"). The block asks `FUN_00619c20` for each of its three lists by the target's kind: a door (`FUN_00684410`): slot 0 Bash (`0x3f5`, `i_attack`) under the conditions above, slot 1 Security (`0x3f3`, strref 329, the skills.2da icon; door locked, server `KeyRequired` +0x2d8 clear, leader has skill 6), slot 2 empty; a placeable with an inventory (`FUN_006837d0`): slot 0 Bash (not plot, area RestrictMode 0, locked `+0x118`), slot 1 Security (has an inventory, locked, leader has skill 6); a placeable without one: the same Bash, and in slot 1, when its client hostile flag is set and its reputation toward the leader is below 11, the Force-power list of a hostile creature instead; a hostile creature: feats and Attack, Force powers, grenades; a mine (`FUN_00691f00`); a friendly creature: nothing. Each slot's selected entry is remembered per target kind by the entry's code. Open, Use and Talk are only default actions.
- **Mouse**: on left button up in the world (`OnLeftMouseUp` `0x00620530`: not over a GUI control
  other than the target block, not in mouse look; `OnWorldClick` itself refuses during a pending
  dialogue and in free look), clicking the object that is already the target and was under the
  cursor at button down (`+0x2b8`) runs **entry 0** (the default action, GUI sound 6); clicking
  another hovered object makes it the target (`SetTarget(hover, 0)`) and refreshes the action menus
  (`CClientExoAppInternal::OnWorldClick` `0x00620350`). A click on the target block hovers the target
  (7.2), so it too runs entry 0. Clicking ground does nothing. An object hovered by the scene ray
  (7.2) that is not in the selectable list becomes the target too, but the next
  `UpdateSelectableObjects` finds it outside the list and picks afresh (med, needs a runtime check).
- **R** (DefaultAction, 239) runs `BuildDefaultActions` and then entry 0 of the current target.
  **1 / 2 / 3** run the target action menus of the main interface (gui.md), which hold more choices
  (Force powers, items) than this default list. (high for R, med for 1–3)
- The callbacks send the player-to-server input messages of 1.5; the server queues the matching
  actions (actions.md).

### 7.5 Hostility

Hostility comes from the server: `GetIsSelectableTarget` uses the friend-or-enemy test
(`CSWSObject::GetIsFriendOrEnemy` `0x0057cd90`: the other object's reputation toward the viewer,
below 11 → 2 hostile, above 89 → 1 friendly, else 0) and reputation (`0x0057cb80`, from repute.2da
and the faction tables). Pushing (4.9) and `k_def_pathfail01` use the same reputation thresholds.
The client's own test is each client object's virtual slot `+0x138`: for a placeable the server's
`+0x340` alone (`0x006831b0`), for a door always 0; for creatures and traps it was not read, the
server sends a creature's friend-or-enemy value and a trap's hostile bit with the object update
(`0x00574a10`) (med). rules.md owns the faction system.

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
- What A and B of the follower step (6.2, entry `+0x18` and `+0x28`) are exactly and what caps the smoothed speed
  (`0x0051cccc`: the stack slot it is compared with is not the one the decompile names). The rules are read from
  the code; the trail's spacing (a point every 0.5 m of the leader's walk, `0x00636a30`) decides how often a follower
  is more than a metre from its follow point, and with it how often it hurries at 1.2 x.
- The follow states 1–4 and 6–10 and the client trail object (`+0x2dc`, `0x00636a30`,
  `0x006350f0`, `0x00634cc0`): trail spacing, formation offsets per slot, when a follower stops.
- Whether the client smooths NPC turning visually (the server snaps the facing).
- How the hover pick's fallback route computes an object's screen bounds (slots `+0x13c`, `+0x144`,
  7.2), and the placeables.2da column the scene pick tests (`DAT_007a225c`).
- Input message (6,0x21): its handler (`0x00525450`) zeroes param 5 of a DRIVEDIRECT at the head of
  the controlled creature's queue; the client builds it in `0x00677e50` (sent through
  `CNetLayer::SendMessageToPlayer` directly, from `0x005f2980`, 1.5), but when `0x005f2980` runs was
  not traced. Also open: whether anything reads `MOVETOPOINT` flag bits 4–8 (the handler
  carries them along unread, actions.md 3.1).
- Camera: the sign conventions of the 284 axis and of mouse yaw, the CAMERAHOOK height branch,
  the auto-turn stop test, the two vertical collision rays, the `"yaw/dist/pitch %f"` client
  commands, the shake waveform, the combat camera's framing helpers, and the legacy modes 0–2.
