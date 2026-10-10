# Player controls: what the original does and where we are

The checklist of every player-facing control in the world view (keyboard, mouse, camera, targeting,
party, pause), each with the evidence for what the original does and our state. "matches" means it was
run through the real input path (SDL events: `key`, `mouse` lines of the input script, see
[../playthrough.md](../playthrough.md)) and looked at; "ours" marks a deliberate difference; "open" says
why something is not built. Sources: `swkotor.ini` `[Keymapping]` and `keymap.2da` (the key table below),
[../re/movement.md](../re/movement.md), [../re/gui.md](../re/gui.md), [../re/gameloop.md](../re/gameloop.md),
and the functions named (`CClientExoAppInternal::HandleInputAction` 0x00621210, `SetHoverObject`
0x006222f0, `OnWorldClick` 0x00620350, `UpdateCameraInput` 0x005f5e10, `CSWCParty::SetLeader`
0x00635480).

How to test a line: load a checkpoint (`kotor.exe --load kotor/out/checkpoints/cantina --no-render --input X
--screenshot-at F:PNG`, [../testing.md](../testing.md)), turn the test bot off (`ui bot off`), then drive it
with `key NAME`, `keydown NAME`, `keyup NAME`, `mouse move|down|up|click [left|right] [X Y]`, `mouse wheel DY`
(each is an SDL event on SDL's own queue, `game/inject.ctx`), and read `ui pos`, `ui anims`, `ui pick`, `ui
info`, `ui hover`, `ui list` (screen boxes of what can be picked) and the screenshots.

## The key table (keymap.2da, defaults; ours swap strafe and camera rotation)

A key code in the ini is the game's own: letters A..Z = 51..76, digits 1..9 = 77..85, so W = 73, S = 69, Z = 76,
C = 53, A = 51, D = 54, Q = 67, E = 55, R = 68, F = 56, G = 57, B = 52, V = 72, X = 74, Y = 75, T = 70.
The defaults are those of the `patch.erf` copy of keymap.2da, the one the Steam install loads (the `2da.bif`
copy stops at `Action264`: it has no B row). Rows `Action200`..`Action265` are events of that number; the axis
rows `Action280A/B`..`Action286A/B` pair two keys into one axis event (`SetupKeymapping` 0x005eeb10, which
reads `[Keymapping]` first and writes the 2DA's default only for a missing entry). The install's
`swkotor.ini` has the 2DA's codes for every row except two: `Action281A/B` = 51 / 54 (strafe on A / D) and
`Action284A/B` = 0 / 0 (camera rotation unbound), a remap; the table gives the defaults.

Ours: the bindings are read from **our options file** (`kotor/out/kotor-settings.ini` or `--settings FILE`),
never from the install's `swkotor.ini`: its `[Keymapping]` section has the original's format
(`Action204=67`, `Action280A=73`, the codes above, 0 for no key), each entry it gives is used and every
missing one takes the default (`lib/frontend/keymap.ctx`). The defaults are keymap.2da's `Language0`
(a `Disabled` row gets no key, as `SetupKeymapping` skips it) except that strafe and camera rotation swap:
`Action281A/B` = A / D (51 / 54) strafe, `Action284A/B` = Z / C (76 / 53) rotate the camera (the user's
choice). The file holds only what the remapping screen changed (the original writes every default back
to its ini; ours keeps the file to what the player chose). Every key the game reads goes through the
bindings (`ingame::handle_key`, `menu_of_key`, `play.ctx` `apply_key` and the quick save / load keys,
the minigames' fire and pause keys in `minigame_scene.ctx`). A hidden (`--headless`, `--no-render`) run
without `--settings` uses the defaults whatever the file says, so the input scripts keep their keys. The
options' Keyboard Configuration button opens the remapping screen ([../re/gui.md](../re/gui.md), "Key
mapping"): matches. Not bound to the table: the conversation's reply keys 1-9 (`Dialog1..9`, not
remappable; ours also take the keypad's) and the GUI's own Enter, arrows and Escape, which the original
hard-wires too.
World is the row's ICPC flag, Menus its ICPCGUI flag; the free-look (ICFreelook) and minigame flags are named
where they matter.

| Key | Action (id) | World | Menus | Ours |
|---|---|---|---|---|
| W / S | forward / back (280) | yes | | matches |
| A / D | strafe left / right (281; default Z / C) | yes | | ours: swapped with rotation (A / D steer in minigames) |
| Z / C | rotate camera left / right (284; default A / D) | yes | | ours: swapped with strafe |
| Arrows | minigames only (285, 286); MoveForward.. (200-203) are disabled | no | | matches (arrows do nothing in the world) |
| W / S, A / D, arrows, Space, Escape in a minigame | drive, steer, fire (282, 283, 285, 286, 217 MGshoot), pause (253) | | | matches; fixed: Z / C no longer steer and R no longer fires in a minigame (they are not ICMiniGame rows) |
| B (held) | walk modifier "Run / Walk" (265) | yes | | matches |
| Q / E | previous / next target (204, 205); in menus previous / next menu (243, 244) | yes | yes | matches (in free look they only end it: `tools/camcheck/scripts/freelook.txt`, the target stays); in combat mode with no hostile in view they cycle every entry (see Mouse) |
| Tab | change leader (206) | yes | yes | matches (in free look it only ends it: `tools/camcheck/scripts/freelook.txt`; GUI sound 6 with nobody to take the lead: fixed, by reading) |
| V | solo mode (207) | yes | | matches (in free look it only ends it: `tools/camcheck/scripts/freelook.txt`) |
| Caps Lock | free look (208) | yes (leader idle, game running) | | open (see Camera: free look) |
| U I P K J L M O | equipment, inventory, character, abilities, messages, journal, map, options (209-216): the key of the open menu closes it, another switches to its menu; nothing while the leader is dying (member 0 `GetIsDying`, `0x005f2ed0`; during the party-wipe slow motion they fade the screen out instead) | yes | yes | matches while the leader is down (`tools/ingame/scripts/leader_down.txt`: I opens nothing); the wipe's fade: fixed (`wipe_key.txt`: I ends the wipe after 3.3 s instead of 13 s) |
| Escape | the options menu / close the open menu (223); with the leader dying the box 42628 "You can't access the Start Menu while controlling an unconscious character." instead (`HandleInputAction` 0xdf) | yes | yes | matches (`tools/ingame/scripts/leader_down.txt`: the 42628 box) |
| F4 / F5 | quick save / quick load (218, 263) | yes | | matches (`play.ctx`) |
| Ctrl | look about (219, 220) | yes | yes | matches |
| Shift | alternate actions (221, 222) | yes | yes | matches |
| Space, Pause/Break | pause (241, 224) | yes (Space not in free look) | | matches |
| T (held) | tooltips at once: the delay is 0 while it is held (225, `SetTooltipKeyHeld` 0x005f4be0) | yes | yes | matches for the delay (`tools/ingame/scripts/tooltip_key.txt`: the tooltip 4 frames after the hover); open: what it also changes on the HUD (three of its controls' flags, `0x006856e0`, not read) |
| 1 2 3 | the target block's left, middle, right action (226, 228, 230) | yes | | matches |
| 4 5 7 6 | self slots: friendly powers, medical items, mines, other items (232, 234, 236, 238) | yes | | matches |
| R | default action of the target (239) | yes | | matches |
| F | cancel combat: leave combat mode, clear the leader's actions (240) | yes, in combat | | matches |
| X | weapon flourish (242: `0x005f4460`, the leader's combat state, its weapons' power-up and a combat animation) | yes | | fixed: for a living leader holding one melee weapon, a two-handed one or two (stance digits 2..4) the leader enters combat for reason 2 (its saber lights) and, standing, plays `g<d>w1` for 1.5 s (`fight::flourish`; `tools/combat/flourish1.txt`); open: walking, the original lays the overlay `G<d>F1` (10157) over the walk, which ours cannot draw |
| Y | drop one queued combat action (245) | yes | | matches |
| G | toggle stealth (264): only when the player's creature can stealth (`GetCanStealth` 0x00610ac0), then the leader's request (0x0060f4b0) | yes | | matches ([stealth.md](stealth.md): with a companion and solo mode off the solo-mode box asks first) |
| Left / right button | select, act / look about | yes | | matches |

Reverse Mouse Buttons (options) swaps left and right: matches.

## Keyboard movement (movement.md 1.1 - 1.4)

| Behaviour | Original | State |
|---|---|---|
| Input vector (forward, strafe), diagonals normalised, rotated by the camera's yaw | `CSWCPlayerControl::Update` 0x00679940 steps 3-4 | matches |
| The leader turns toward the input at `MinTurnRate + (MaxTurnRate - MinTurnRate)(1 - v/vmax)` degrees per second (camerastyle.2da of the area) | step 5 | matches; from standstill it faces the input at once (ours) |
| Velocity approaches `u * vmax` exponentially with time constant `vmax / K`: `vmax` the run rate (the movement block's DriveMaxSpeed), `K` the appearance's DriveAccl (50 for humanoids; 15 in stealth; scaled by `vmax / 1.8` below 1.8 m/s); stops below 0.25 m/s with no input | step 6 (RK4 of `dv = K u - K/vmax v`), `CSWCCreature::GetAcceleration` 0x00610590, movement block 0x00698b10 | matches (closed form, ours; `tools/gait/run.sh endar`: 5.06 m/s 8 frames after W) |
| Moves along its facing by the length of `dp` only above 1 m/s; the 0.033 m floor on a frame's step applies only to a debug speed of 5000 m/s or more (`vmax >= 5000`: 0.001089, else 0; asm `0x0067a395`) | step 7 | matches: any step above 1 m/s moves; a move that fails keeps the velocity (the leader runs on the spot against a wall), and a leader with orders, one who cannot move or a helpless one is not moved |
| Walkmesh sliding along walls (6 attempts) | `MoveDirect` 0x00614b90 | matches (x or y part alone, ours) |
| Triggers see the move (enter, exit) | `MoveCreatureFromClient` | matches |
| B held halves the input vector | event 265, step 3 | matches |
| Walk, run and stand animations; cycle rate = speed x the cycle's length / the ground one cycle covers (metres per cycle: appearance DriveAnimWalk / DriveAnimRun for the creature the keys drive and for a party follower, WALKDIST / RUNDIST for a creature on a planned path) | `0x00615960` (driven), `0x00615e80` (follower), `UpdateMovementAnimation` 0x00611f50 (planned path), movement.md 3.6 | matches: the player's 0.733 s run cycle covers 3.96 m, so at 5.4 m/s it plays at rate 1.0 (and the walk's 1.067 s over 1.813 m at 1.7 m/s); the rate follows the speed through the acceleration of the keys (about 0.3 s) and of a MOVETOPOINT (1 s, floor 0.1) and reaches the playing cycle. Which cycle: the driven creature and a follower walk at 0.6 x the run rate or below and run above it (3.24 m/s); a creature on a planned path takes the action's run flag |
| Input while the leader has orders cancels them (the original waits 0.3 s first, then cancels a commandable leader whose control speed is above 0.25 m/s, else waits another 0.1 s; in combat mode the input is dropped while he has orders unless the "Combat Movement" option is on: on by the game's default, off in the install's `swkotor.ini`) | 1.4, `ProcessInput` 0x006227e0, option defaults 0x0061da60 | matches in combat mode (`tools/ingame/scripts/combat_movement.txt`: with the option off the attack goes on under W, with it on W cancels it); ours: at once out of combat mode (the 0.3 s and 0.1 s waits are not modelled) |
| No click-to-move | 1.5 | matches: a click on the ground does nothing |
| Dead or dying leader, a conversation: no movement | step 1 | matches |
| Releasing a key always releases the walk, even if a menu took the event | | matches (`pump_events`) |
| Leader switched while a key is held: the old leader stops | | matches |

## Camera (movement.md 2)

| Behaviour | Original | State |
|---|---|---|
| Chase camera: distance, pitch, height, FOV from camerastyle.2da's row of the area (combat: row 8) | 2.2, 2.3 | matches |
| Position: horizontal error halves every frame; looks at the leader's head; pitch fixed | 2.3 steps 5-7 | matches (the halving is a 0.1 s time constant, ours: see Collision) |
| Rotate keys: rate integrator 200 deg/s, 500 up, 2000 down | `CRateIntegrator` | matches |
| Camera never swings behind a moving player by itself | 2.3 | matches |
| Mouse look while Lookabout (Ctrl or right button) is held, XOR the Mouse Look option; cursor hidden; yaw = clamp(counts/100) x (10 + 0.45 x sensitivity), the mouse moving right turns the view right | `CameraInputMouseYaw`, `UpdateCameraInput` 0x005f5e10 | matches (relative mouse mode in a window; the 0.1 s coast after release: `tools/camcheck/scripts/mouse_coast.txt`) |
| A cursor within max(2, width/1000) px of the left or right edge rotates like the rotation keys (ours Z / C), when no key is down, the mouse is not looking and free look is off | `UpdateCameraInput` 0x005f5e10 | matches |
| Q / E swing the chase camera round to the new target (15 deg to the side it is on, eased); the combat camera has no swing | `TurnTowardObject` 0x00639c30 (from `SelectTarget` 0x005f9c60, chase camera only) | matches (rate 2.5 to 7.5 as read; the stop test is ours; in combat mode nothing swings: `tools/camcheck/scripts/combat_cam.txt`, E leaves the yaw) |
| Leader change keeps the yaw and retargets | `SetPartyLeader` 0x005f6b60, `SetCameraTarget` 0x0063f9d0 | matches |
| Collision: four rays (L to C +- 0.35 sideways and up), creatures' CAMERASPACE circles clip it | 2.3 "Collision" | matches, and goes further: the four rays against the walkmeshes, the drawn rooms (through a bounding tree per room mesh: `lib/scene/raytree.ctx`), doors and placeables, ending 0.25 m beyond the camera and repeated until clear; the rise stops short of a ceiling; a camera that ends inside a creature's circle comes out along the line; a wall or creature holds the camera in for 0.4 s before it eases out (no flicker past railings), eased over a 0.1 s time constant. `cam probe` and `cam trace` check it |
| Combat camera: row 8 at 3.6 m straight behind the leader along the player-turned yaw (no target framing; only the mouse and the rotate keys turn it; it turns toward the target once, when installed by `RestoreDefaultCamera` in combat mode with a target), no easing, the chase camera's wall pull-in, no creature clip | 2.4 | matches (`tools/camcheck/scripts/combat_cam.txt`: 3.6 m behind along the yaw from the first combat frame, 0.55 up, E does not turn it, D does, leaving free look turns it to the target; the creature clip is skipped, by reading) |
| Free look (Caps Lock, only with the leader's queue empty and the game not paused): eye at the head (`FreeLookHook`, else `CameraHook`), the mouse turns the leader (yaw) and pitches the view within -FL_LOOKDOWN and +FL_LOOKUP of the area's camerastyle row (-20 / +15 in DEFAULT, -30 / +30 in most others), the rotation keys (ours Z / C) turn him at 200 deg/s, W / S tilt the view and nothing moves him (the strafe keys, ours A / D, do nothing), the HUD is hidden; the same key, a menu key, Escape, Pause/Break, Q, E, Tab or V (these four only end it), or an order given to the leader ends it | 2.5, `HandleInputAction` 0xcc-0xd8, 0xdf, 0xe0, `ProcessInput` 0x006227e0 (`CameraInputMove` 0x0063fdb0) | matches (`tools/camcheck/scripts/freelook.txt`: W and S tilt to +15 / -20 in Taris and +-30 on the Ebon Hawk, nothing moves the leader, Tab V Q E only end it; the tilt keys' integrator is 200 deg/s and 500 deg/s^2, a mouse move resets it); the leader's appearance.2da `FreeLookEffect` (T3-M4 row 1 blue-grey, HK-47 row 2 red, `CSWCCreature::GetFreeLookEffect` 0x00610490) is switched on with it and off after (`tools/ingame/scripts/freelook_effect.txt`, `kotor/out/items/freelook_*.png`) |
| No zoom; the wheel goes to the GUI | 2.3 | matches |
| Dialogue camera, death camera, shake | 2.1, 2.6 | dialogue: the dialogue lead's; death camera: built (`game/death.ctx`); shake: matches (`tools/camcheck/scripts/shake.txt`: VFX_IMP_SCREEN_SHAKE shakes the view for 1 s by under a degree; ours adds it to whatever camera draws, the death camera too) |

## Mouse: hover, click, target block (movement.md 7, gui.md "Action menus")

| Behaviour | Original | State |
|---|---|---|
| What can be picked: living creatures (companions too), closed doors that are not static (area-transition doors too: an open door of any kind is not pickable), placeables whose Useable flag is set (HasInventory and Static are not looked at; the game clears the flag on an emptied DieWhenEmpty container), traps the leader has detected or that are friendly to it (reputation above 89, or its faction), within 30 m of the leader and in its view: a creature the leader sees (listed, or seen this instant), and the ray from the leader to the object meets no wall and no closed door (open doors and placeables are looked through) (`GetIsTargetVisible` 0x00617ad0, `GetIsSelectableTarget` 0x004f2c30; the pointer's list pick, Q / E and the auto-target all ask it, the pointer's scene ray does not) | 7.1 | matches (boxes are ours: models carry no bounds; the ray is ours, `perception::is_sight_clear`); an opened area-transition door is no longer pickable either (fixed; the Endar Spire replay `10_endar_spire.txt` still reaches `tar_m02af` with 0 faults: it takes its doors with `use`, not a click on an open door) |
| Cursor over a selectable object that is not the target: select; over the target: its default action's (open door -> door, talk -> talk, use -> hand, attack -> kill, bash -> bash, disable / recover mine -> their own); a target with nothing in its list (a hostile creature where the area forbids combat, a mine and a leader without Demolitions) keeps the arrow; over nothing or the GUI: the arrow; the pressed picture while the button is down | `SetHoverObject` 0x006222f0, `GetCursorForAction` 0x0061faa0 | matches (a target with an empty list keeps the arrow: fixed, by reading the code; no run). The cursor comes from entry 0, which on a door is always Open, locked or not (the unlock is a slot entry, not a default), so a locked door shows the door cursor |
| No name label on hover | `SetHoverObject` writes only the hover id `+0x4a4`, the point `+0x4a8` and the cursor | matches (none drawn) |
| An area-transition door or transition trigger the leader is heading for shows its destination in the transition label (`areatransition.gui`), only what follows the first "-" and the character after it. Each frame every transition door and trigger tests a line 8 m ahead of the player's creature (along its facing, or along the camera's direction when the in-game GUI's `+0xc1c` is set) that crosses it with nothing in between; the nearest wins. Hidden while the area has a transition pending. The pointer plays no part (needs a runtime check) | door 0x00684660, trigger 0x006920b0 (their per-frame slot), `FUN_00632180` from `MainLoop`, `CSWGuiAreaTransition::SetTransitionObject` 0x006c7ec0 | open: ours shows it for the transition door under the pointer (`hud::update_transition` on `w.hover`), never for a trigger |
| Left click on an object that is not the target selects it (no sound); a click on the target that was the target at button down runs entry 0 of its action list with GUI sound 6; a click on empty ground changes nothing; a click the GUI took is not a world click; none while the mouse looks | `OnLeftMouseDown` 0x0061f880, `OnWorldClick` 0x00620350, `OnLeftMouseUp` 0x00620530 | matches: the release selects what is under the pointer then, and runs entry 0 only on the object that was the target at the press (fixed; `tools/traps/scripts/detect_disarm.txt`'s click on the mine still disables it, `autotarget/scripts/taris_walk.txt` still selects by click) |
| A talk order walks the leader up to use range + 1 m first (scripts start where they stand); doors and placeables walk up (use range) | `DialogObject` approach mode 1, actions.md 1.4 | matches (engine: `doors::approach_within`) |
| The target block (name, health bar, three action slots with up / down arrows) hangs over the target (a block with no choice in any slot is just the name and the bar); the reticle (hostile red, friendly blue) is drawn round it, and the slots' frames and the health bar follow the same colour. Both follow the HUD target, never the pointer. The pointer has its own smaller **hover reticle** (`friendlyreticle` / `hostilereticle`, half strength) on the object under it, same sizing by distance; hidden while the mouse looks about, within 32 px of the screen's edge, and on the target itself when its block's left slot is empty | gui.md, `UpdateReticles` 0x0068a310 and the routine it ends with 0x006889c0, `SetHudTarget` 0x0062b000 (set by `SelectTarget`, cleared by 0x005f2c60 when an in-game menu opens) | matches. The marker follows the HUD target wherever it is (fixed; `hud::update_reticle`): within 32 px of an edge or behind the eye it is a 32 px `friendlyarrow` / `hostilearrow` at that edge (left 0, right turned half round, bottom a quarter, top three quarters; behind the eye on the target's side, mirrored into the lower half), and a hostile creature in combat mode gets `combatreticle`, 64 px larger at first and back to its size in 0.5 s after each new target or Disengage. Checked by screenshots: the uppercity checkpoint turning away from `droid1` (left and right edge arrows, the block clamped to the edge), `force_run.py --angles 160` (a target behind: arrow at the left edge, key 2 still casts), `force_run.py --cast-at 100` (the zoomed combat reticle) |
| The game keeps a target without a click, every frame. A target still in the 30 m list and in view **stays, whoever set it** (a click, Q / E or the last pick: no stickiness difference); one out of view for 1 s goes. **A leader moving by the keys (control speed 0.25 m/s or more) out of combat mode loses its target after 0.5 s of that**, and with none the pick is the nearest visible selectable object in front of the leader (within 30 degrees of its facing, seen from a point 4 m behind it, so one at arm's length beside him counts), repicked every half second while he walks; standing still keeps what he has. In combat mode the drop never runs; with enemies about the pick is the nearest hostile in front, else the first hostile in sight (by bearing), else the nearest non-hostile in front (`SelectTarget` asks the chase camera to turn to it, but in combat mode the combat camera is installed, so nothing turns). An enemy coming into the leader's view when none has been in it for 10 s becomes the target at once (the camera swings to it, out of combat mode it asks the Enemy Sighted auto-pause). When a combat round moves the leader's attack to a new enemy the server's `SetTarget` (new bit `+0x37c`) makes it the target and asks `SelectTarget(1, 0)`, whose turn reaches only the chase camera, which the combat camera has replaced in combat mode: nothing turns (ours: `continue_fight` sets the target, no turn). No other camera turn (Q / E and these picks). All these timers run on the world's frame time, 0 while the game is paused, so a pause freezes them: a target clicked while paused stays until the unpause. Dead creatures are never picked; the body bag a dead creature leaves is a useable placeable and is picked like any other object (no hostile-first rule out of combat mode) | `UpdateSelectableObjects` 0x005fa5a0, the target drop in `ProcessInput` 0x006227e0 (timer `+0x36c`), `SetTarget` 0x005f4a20, `GetNearbySelectableObjects` 0x004fc4c0, movement.md 7.1 | matches (`lib/hud/autotarget.ctx`; the keys' velocity comes from the loop after the control step); the drop also waits while an auto-pause request waits its second (`+0x390`, set by a request in the 5 s door window after the player's open, unlock or bash of a door: built in `ingame::update_autopause`, fixed but not run, the runs leave the auto-pause off); the timers stop while paused (fixed: they ran on the real frame time, and a player walking by the keys when the Endar Spire's Sith auto-paused the game had a clicked Sith dropped every half second of the pause for the nearest object in front (a body bag in the report), the control not stepping while paused so its velocity stayed; `sh kotor/tools/autotarget/paused_click.sh`); open: the turn to a new foe that a combat round picks is not built |
| The block's slots hold what the leader can do besides the default: a hostile creature the combat feats and Attack (left), Force powers (middle), grenades (right); a mine Disable (left) and Recover (middle); a locked door or placeable: Bash on the left (not plot, area RestrictMode 0; a door only while not open) and Security in the middle when the leader has the skill (a door only when no key is wanted, a placeable only when it has an inventory; an inventory-less placeable that is hostile to the leader lists the hostile Force powers there instead). Open, Use and Talk are in no slot, and a friendly creature's block lists nothing | `FUN_00619c20` by target kind, `GetTargetKind` 0x0060fcc0, `FUN_00684410` (door), `FUN_006837d0` (placeable), movement.md 7.4 | matches (Security only on a placeable with an inventory, the hostile powers on an inventory-less placeable hostile to the leader: fixed, by reading the code; no run) |
| A click on the target and R run entry 0 of `BuildDefaultActions`: a door Open (it cancels the leader's actions and asks the server to open; a locked one is refused with "locked" and OnFailToOpen, nobody unlocks it for you), then Bash on a locked non-plot door when the area allows combat; a placeable Open (with an inventory) or Use (without one, not a corpse), both only when useable, then Bash when not plot and the area allows combat (with an inventory only when locked; without one locked or not, needs a runtime check); a friendly creature Talk; a hostile creature Attack when the area allows combat, else nothing; a mine Disable (hostile) and Recover for a leader with Demolitions | `BuildDefaultActions` 0x00620620, `CSWCDoor::DefaultActionOpen` 0x00683d90 | open: ours gives an inventory-less placeable Bash only when it is locked; doors, creatures and mines match |
| Slot orders: out of combat they replace what the leader was doing; in combat mode they queue behind it; Shift makes them replace; Shift with the slot's key steps to the slot's next choice | `UseSelfAction`, `OnActionButton` 0x0068b970, `HandleInputAction` 0xe2-0xee | matches |
| Slot icons: dimmed (alpha 0.25) when unusable or the leader is dead or dying; each slot's tooltip is its own fixed text ("Activate Left Action" and so on), and the selected entry's name shows in the block's name label (a self slot's in the description label) while the pointer is on the slot | gui.md "Action menus", `FUN_00685cb0` | matches; the middle and right slots stay empty until the leader has powers and items for a target (the rules lead's) |
| Q / E: through the selectable list in view by bearing counted counter-clockwise from the leader's facing (the first is the one just left of straight ahead), wrapping; in combat mode hostile creatures only, or every entry when no hostile creature is in view | `CycleTarget` 0x005fb050 | matches (fixed: in combat mode with no hostile, E steps from one creature to the next in the uppercity checkpoint, `ui combat 1` then `key e` twice) |
| R: entry 0 of the target's list | `HandleInputAction` 0xef | matches |
| A target that stops being selectable is dropped (the original keeps it 1.5 s while enemies remain in combat mode) | `UpdateSelectableObjects` | ours: dropped at once |

## Party (movement.md 6; gui.md "Party portraits")

| Behaviour | Original | State |
|---|---|---|
| Tab: the party table turns until the next member who can act is first, the others keep their order ([A B C] -> [B C A] -> [C A B]); dead or dying members are passed over (at most three turns, nothing with fewer than two members); GUI sound 6 plays whether or not the leader changed; works in menus too (they show the new leader); in free look Tab only leaves free look | `HandleInputAction` 0xce, `CyclePartyLeader` 0x005f7960, `CSWCParty::SetLeader` 0x00635480 | matches (`party::rotate_to_front`; free look: `tools/camcheck/scripts/freelook.txt`; the sound with nobody to take the lead: by reading) |
| Clicking a companion's portrait makes him the leader (not one who is dying); the leader's portrait opens equipment, or the character sheet when the leader can level up | `OnPartyMemberButton` 0x00688690 | matches (`tools/ingame/scripts/portrait_levelup.txt`: with 1000 XP more the portrait opens the sheet) |
| The camera's target becomes the new leader; the yaw is kept. The HUD target becomes the one the new leader had when it last gave up the lead (each client party entry keeps one, `+0x80`, filled from the outgoing leader's attack target `+0x504`; static reading, needs a runtime check) | `SetPartyLeader` 0x005f6b60 (`SetCameraTarget`), `CSWCParty::SetLeader` 0x00635480 | open: ours keeps the HUD target as it was; the camera part matches |
| Followers keep up: every companion holds a FOLLOWLEADER action (queued by `k_ai_master`'s heartbeat while solo mode is off) and steps every frame from the leader's first move. A follower has no acceleration ramp: it moves at its pace x 0.9 (within a metre of its place), x 1.2 (up to 15 m) or x 1.5 (beyond); the pace is the run rate (or the leader's speed if more) when 4 m or more from its place, the leader's speed while he moves, and 3.46 m/s in the walk cycle (0.9 x 1.2 x its PC_Movement walk rate of 3.2; the cycle follows the speed capped at 2.88) when it has a metre or two to go to a standing leader; it walks below 0.6 x the run rate and runs above, each cycle at the rate its speed asks for | `UpdateFollowLeader` 0x0051c360 (formation slots, the leader's trail, speed rules 6.2), `0x00615e80` (movement.md 3.6), party-items-saves.md 3.7 | matches for the places and the pace: the leader's trail is recorded and each follower goes to its formation point on it (formation 0: 2.2 m behind, 1.5 m to either side), along the trail when it cannot walk straight there (`lib/engine/trail.ctx`; checked with `tools/gait/scripts/taris_street.txt`: running, both 3.5 m behind and 1.5 m to the sides, standing 2.5 m behind); deliberate: it starts when the leader is 4 m away and the member has been idle a second, not at the leader's first step (FOLLOW_IDLE_MS, the room 3 guard) |
| Solo mode (V or the TB_SOLO button): pauses (unless the player had), asks "Do you wish to turn Solo Mode on / off?", on OK flips the party flag and runs `k_sup_solo`; the others then do not follow; only with 2+ in the party, no conversation, no load or area transition pending, the player creature neither dead nor dying, else sound 2; V does nothing while a menu is up | `ShowSoloModeConfirm` 0x0062e550, `HandleInputAction` 0xcf, strrefs 37889-37892 | matches |
| Party selection screen pauses the world while up. Done from the map applies at once; opened by a script it asks first, "You have less than 3 characters in your party. Are you sure you wish to proceed?" (38329) when two or more slots can be toggled and fewer than two are picked, else "Are you sure this is the party configuration you want?" (38328), and applies on Yes; it asks nothing when no slot can be toggled or both slots are forced | `CSWGuiPartySelection::OnDone` 0x006bf3b0, `OnConfirmed` 0x006bec90, `CGuiInGame::ShowPartySelection` 0x0062dd20 | matches (`tools/ingame/scripts/partysel.txt`, `partysel4.txt`) |
| Back or Escape on the party selection screen: from the map without forced members every slot goes back to "picked = was a member" and the party applies, unchanged; from a script or with forced members it says "You cannot cancel from this screen at this time..." (42405) and stays up, and Back is coloured disabled | `CSWGuiPartySelection::HandleInputEvent` 0x006bede0, `OnPanelAdded` 0x006beeb0 | matches (`tools/ingame/scripts/partysel2.txt`, `partysel4.txt`) |

## Pause (gameloop.md 6)

| Behaviour | Original | State |
|---|---|---|
| Space or Pause/Break toggles the player pause (reason 4) and ends an auto-pause; GUI sound 6 plays, except when pausing shows tutorial pop-up 6 instead; the Pause key in free look leaves it first (Space is not read there); the banner says PAUSED; the world clock stops (no movement, no timers) while the GUI and camera keep running | `HandleInputAction` 0xe0/0xf1, 6.2, 6.3 | open: tutorial pop-up 6 is not built; the rest matches |
| Orders given while paused are queued (they begin, make no progress) and run on unpausing | 6.2 | matches (tested: a talk order with a walk) |
| Opening a menu pauses (it turns the player pause on unless the player had paused) and closing it turns it off again only if it was the one that turned it on | 6.3, `ShowInGameMenu` 0x0062c9b0, `HideInGameMenu` 0x0062cba0 | matches (ours keeps a separate menu pause bit, with the same result) |
| Auto-pause (install defaults: enemy sighted, mine sighted, party killed, new target selected on; end of combat round, action menu off): an enemy coming into the leader's view within 30 m when none has been in view for 10 s, out of combat mode and not paused (a closed door hides what is behind it); within 5 s of the leader's own open, unlock or bash order on a door a request waits 1 s and is dropped if combat mode is on by then (so opening a door onto enemies pauses a second later); a party member going down while another stands (2 s cool-down); a slot's choice stepped (action menu); the end of the leader's combat round while he is in combat mode; a new target from Q / E in combat mode; a mine coming into view; the banner carries the reason's text | 6.4, `UpdateSelectableObjects` 0x005fa5a0, `CSWCDoor::DefaultActionOpen` 0x00683d90 (the 5 s window, 0x005f4100) | matches: the door window and its 1 s wait (`hud::note_door_action`, `ingame::update_autopause`; since 31ae0e3). The rest matches too: the engine and the HUD call `autopause::request{reason}` (`lib/engine/autopause.ctx`); `ingame::update` takes the frame's first request and weighs it against the option, a person playing, a conversation or menu up and a pause already on. Mine sighted: `ingame::watch_mines` (`lib/ingame/mine_watch.ctx`). Runs only when a person plays: headless runs and replays keep it off (`ui autopause on` turns it on). In `--no-render --speed N` runs the HUD's clocks (the 10 s latch, the 1 s out-of-view timer) tick once per N world ticks with one tick's dt, so use `--headless` to see them at the right pace |
| The banner button unpauses by click | gui.md | matches |
| Switching to another window pauses; coming back resumes unless the game was paused already | `OnAppDeactivate` 0x00401d90, `OnAppActivate` 0x00401e00 | matches (only when a person plays) |

## Minimap and HUD buttons

| Behaviour | Original | State |
|---|---|---|
| Clicking the minimap opens the map menu | `BTN_MINIMAP`, gui.md | matches |
| The arrow turns with the camera's heading (not the leader's facing), plus the map's north offset (0, 90, 180 or 270 degrees by the area map's orientation); needs a runtime check | `RenderMiniMap` 0x0068ab10, `0x00578ed0` | open: ours turns the arrow with the leader's facing (the HUD lead's) |
| Menu buttons, pause, solo and stealth toggles, party portraits, self slots, target block, combat bar (Disengage, Clear one) | gui.md | matches |
| Level-up arrow on a portrait when the member's XP allows a level | `UpdatePartyPortraits` 0x00687860 | matches: it stays until the member is levelled (Level Up or Auto Level Up in the character sheet; "Auto Level Up NPCs" is off by default, as in the install) |

## Cursor shapes by context

default arrow (nothing, the GUI, the leader himself, a target with nothing in its action list); select (a
pickable object that is not the target); over the target, the picture of its default action (`GetCursorForAction`
0x0061faa0): door (a closed door: Open is always first, locked or not), talk (any creature that is not hostile),
use (a placeable, container or not), kill (a hostile creature where the area allows combat), disarm mine / recover
mine (a mine), bash (only where Bash is the first entry, never on a door, whose Open comes first), invalid (an
entry whose action has no picture of its own). `SetHoverObject` 0x006222f0 sets only cursor ids 1, 5, 7, 11, 23,
25, 33, 37, 45 and 51 (each with its pressed form while the button is down); walk, follow, examine, transition,
Force power, lock, create and the run and walk arrows are never chosen. Ours chooses the same set, except that a
target with nothing in its list keeps the arrow (fixed).

## Moving to a point (the planner under every order)

| Behaviour | Original | State |
|---|---|---|
| The straight walk when clear, else the area's path points: the nearest point with a clear walk to the start and to the goal, a search between them, string pulling | 4.3, 4.5 | matches (A*; the original's depth-first search finds the same kind of route) |
| The nearest clear path point is looked for in a window that grows by 10 m | `FindNearestPathPoint` 0x004bd770 | matches: every point by distance, up to 64 (trying only the 8 nearest left a creature on a walled-in ramp, Carth in the Kandon garage, with no route) |
| A goal nobody can stand on (the middle of a closed door) becomes the nearest safe point within 2 m | 4.5, 4.8 | ours: backs off toward the start up to 3 m to a point a path point reaches; the move ends there |
| A step into a closed door sends PATH_BLOCKED (OnBlocked opens it); six blocked steps end the move | 4.9 | matches |

## Found and fixed while testing

Scripted input skipped half the real path (`ui click` missed the conversation panels, `ui key` never reached
the world, `down w` skipped the interface); Tab only swapped two members; arrows and R moved or acted in the
world; hovering showed the action cursor on anything and the attack cursor texture did not exist; a click
on a distant person talked from where the leader stood; a goal in the middle of a closed door made long moves
give up; the party screen did not stop the world; the walk and run cycles played at 1.0 whatever the speed.
