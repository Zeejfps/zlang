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

## The key table (keymap.2da, defaults; the install's `[Keymapping]` is the same)

A key code in the ini is the game's own: letters A..Z = 51..76, digits 1..9 = 77..85, so W = 73, S = 69, Z = 76,
C = 53, A = 51, D = 54, Q = 67, E = 55, R = 68, F = 56, G = 57, B = 52, V = 72, X = 74, Y = 75, T = 70.
The columns say which input class the row works in: world (ICPC), menus (ICPCGUI), free look, minigame.

| Key | Action (id) | World | Menus | Ours |
|---|---|---|---|---|
| W / S | forward / back (280) | yes | | matches |
| Z / C | strafe left / right (281) | yes | | matches |
| A / D | rotate camera left / right (284) | yes | | matches |
| Arrows | minigames only (285, 286); MoveForward.. (200-203) are disabled | no | | matches (arrows do nothing in the world) |
| B (held) | walk modifier "Run / Walk" (265) | yes | | matches |
| Q / E | previous / next target (204, 205); in menus previous / next menu (243, 244) | yes | yes | matches |
| Tab | change leader (206) | yes | yes | matches |
| V | solo mode (207) | yes | | matches |
| Caps Lock | free look (208) | yes (leader idle, game running) | | matches (see Camera) |
| U I P K J L M O | equipment, inventory, character, abilities, messages, journal, map, options (209-216) | yes | yes | matches |
| Escape | the options menu / close the open menu (223) | yes | yes | matches |
| F4 / F5 | quick save / quick load (218, 263) | yes | | matches (`play.ctx`) |
| Ctrl | look about (219, 220) | yes | yes | matches |
| Shift | alternate actions (221, 222) | yes | yes | matches |
| Space, Pause/Break | pause (241, 224) | yes (Space not in free look) | | matches |
| T (held) | show every control's tooltip (225) | yes | yes | open: tooltips show on hover only |
| 1 2 3 | the target block's left, middle, right action (226, 228, 230) | yes | | matches |
| 4 5 7 6 | self slots: friendly powers, medical items, mines, other items (232, 234, 236, 238) | yes | | matches (mines list is empty) |
| R | default action of the target (239) | yes | | matches |
| F | cancel combat: leave combat mode, clear the leader's actions (240) | yes, in combat | | matches |
| X | weapon flourish (242) | yes | | open: the flourish animation is not mapped |
| Y | drop one queued combat action (245) | yes | | matches |
| G | toggle stealth (264) | yes | | open: no stealth unit or stealth mode in the engine |
| Left / right button | select, act / look about | yes | | matches |

Reverse Mouse Buttons (options) swaps left and right: matches.

## Keyboard movement (movement.md 1.1 - 1.4)

| Behaviour | Original | State |
|---|---|---|
| Input vector (forward, strafe), diagonals normalised, rotated by the camera's yaw | `CSWCPlayerControl::Update` 0x00679940 steps 3-4 | matches |
| The leader turns toward the input at `MinTurnRate + (MaxTurnRate - MinTurnRate)(1 - v/vmax)` degrees per second (camerastyle.2da of the area) | step 5 | matches; from standstill it faces the input at once (ours) |
| Velocity approaches `u * vmax` exponentially, `vmax` the run rate, stops below 0.25 m/s with no input | step 6 (RK4 of `dv = K u - K/vmax v`) | matches (closed form, K = 15 ours: the source of K is not found) |
| Moves along its facing by `|dp|` only above 1 m/s | step 7 | matches |
| Walkmesh sliding along walls (6 attempts) | `MoveDirect` 0x00614b90 | matches (x or y part alone, ours) |
| Triggers see the move (enter, exit) | `MoveCreatureFromClient` | matches |
| B held halves the input vector | event 265, step 3 | matches |
| Walk, run and stand animations; cycle rate = speed x the cycle's length / appearance WALKDIST or RUNDIST (metres per cycle) | `UpdateMovementAnimation` 0x00611f50 | matches: the player's 0.733 s run cycle covers 3.96 m, so at 5.4 m/s it plays at rate 1.0 (and the walk's 1.067 s over 1.813 m at 1.7 m/s); the rate follows the speed through the 1 s acceleration and the braking (floor 0.1) and reaches the playing cycle. Which cycle: walk below the midpoint of the walk and run rates (ours) |
| Input while the leader has orders cancels them (the original waits 0.3 s first; in combat mode movement is allowed with the "Combat Movement" option on, the install's default) | 1.4 | ours: at once |
| No click-to-move | 1.5 | matches: a click on the ground does nothing |
| Dead or dying leader, a conversation: no movement | step 1 | matches |
| Releasing a key always releases the walk, even if a menu took the event | | matches (`pump_events`) |
| Leader switched while a key is held: the old leader stops | | matches |

## Camera (movement.md 2)

| Behaviour | Original | State |
|---|---|---|
| Chase camera: distance, pitch, height, FOV from camerastyle.2da's row of the area (combat: row 8) | 2.2, 2.3 | matches |
| Position: horizontal error halves every frame; looks at the leader's head; pitch fixed | 2.3 steps 5-7 | matches |
| Rotate keys: rate integrator 200 deg/s, 500 up, 2000 down | `CRateIntegrator` | matches |
| Camera never swings behind a moving player by itself | 2.3 | matches |
| Mouse look while Lookabout (Ctrl or right button) is held, XOR the Mouse Look option; cursor hidden; yaw = clamp(counts/100) x (10 + 0.45 x sensitivity) | `CameraInputMouseYaw` | matches (relative mouse mode in a window; mouse right turns the view right: the original's sign is not read) |
| A cursor within max(2, width/1000) px of the left or right edge rotates like A / D, when no key is down and the mouse is not looking | `UpdateCameraInput` 0x005f5e10 | matches |
| Q / E swing the camera round to the new target (15 deg to the side it is on, eased) | `TurnTowardObject` 0x00639c30 | matches (rate 2.5 to 7.5 as read; the stop test is ours) |
| Leader change keeps the yaw and retargets | `SetPartyLeader` | matches |
| Collision: four rays (L to C +- 0.35 sideways and up), creatures' CAMERASPACE circles clip it | 2.3 "Collision" | partly: one ray against the walkmeshes and the drawn rooms; creatures do not clip it (open: low value) |
| Combat camera frames the leader and its target | 2.4 | open: the combat style row is used, the framing is not (the original's helpers were not read) |
| Free look (Caps Lock): eye at the head, the mouse turns the leader (yaw) and pitches the view within -20 and +15 degrees, A / D turn him at 200 deg/s, W S Z C still move him, the HUD is hidden; the same key, a menu key, Escape, Pause, Q or E, or an order given to the leader ends it | 2.5, `HandleInputAction` 0xd0 | matches (the screen effect of the appearance's FreeLookEffect is not drawn) |
| No zoom; the wheel goes to the GUI | 2.3 | matches |
| Dialogue camera, death camera, shake | 2.1, 2.6 | dialogue: the dialogue lead's; death camera and shake: open |

## Mouse: hover, click, target block (movement.md 7, gui.md "Action menus")

| Behaviour | Original | State |
|---|---|---|
| What can be picked: living creatures (companions too), closed doors (area transitions in any state), placeables whose Useable flag is set (HasInventory and Static are not looked at; the game clears the flag on an emptied DieWhenEmpty container), detected traps, within 30 m of the leader and in its view: a creature the leader sees (listed, or seen this instant), and the line from the leader's eyes meets no wall and no closed door (`GetIsTargetVisible` 0x00617ad0; the pointer, Q / E and the auto-target all ask it) | 7.1 | matches (boxes are ours: models carry no bounds; the ray is ours, `perception::is_sight_clear`) |
| Cursor over a selectable object that is not the target: select; over the target: its default action's (open door -> door, talk -> talk, use -> hand, attack -> kill, bash -> bash); over nothing or the GUI: the arrow; the pressed picture while the button is down | `SetHoverObject` 0x006222f0, `GetCursorForAction` 0x0061faa0 | matches. The cursor comes from entry 0, which on a door is always Open, locked or not (the unlock is a slot entry, not a default), so a locked door shows the door cursor |
| No name label on hover | `SetHoverObject` writes only the cursor | matches (none drawn) |
| Hovering an area-transition door shows its destination in the transition label (`areatransition.gui`), text after the first "- " | `CSWGuiAreaTransition::SetTransitionObject` 0x006c7ec0 | matches for doors; transition triggers cannot be picked (open) |
| Left click on an object that is not the target selects it (no sound); a click on the target that was the target at button down runs entry 0 of its action list with GUI sound 6; a click on empty ground changes nothing; a click the GUI took is not a world click; none while the mouse looks | `OnLeftMouseDown` 0x0061f880, `OnWorldClick` 0x00620350, `OnLeftMouseUp` 0x00620530 | matches |
| A talk order walks the leader up to use range + 1 m first (scripts start where they stand); doors and placeables walk up (use range) | `DialogObject` approach mode 1, actions.md 1.4 | matches (engine: `doors::approach_within`) |
| The target block (name, health bar, three action slots with up / down arrows) hangs over the target; the reticle (hostile red, friendly blue) is drawn round it. Both follow the HUD target, never the pointer. The pointer has its own smaller **hover reticle** (`friendlyreticle` / `hostilereticle`, half strength) on the object under it, same sizing by distance; hidden while the mouse looks about, within 32 px of the screen's edge, and on the target itself when its block's left slot is empty | gui.md, `UpdateReticles` 0x0068a310 and the routine it ends with 0x006889c0, `SetHudTarget` 0x0062b000 (set only by `SelectTarget`) | matches (the target's off-screen arrows `hostilearrow` / `friendlyarrow` and the combat reticle are open) |
| The game keeps a target without a click, every frame. A target still in the 30 m list and in view **stays, whoever set it** (a click, Q / E or the last pick: no stickiness difference); one out of view for 1 s goes. **A leader moving by the keys (control speed 0.25 m/s or more) out of combat mode loses its target after 0.5 s of that**, and with none the pick is the nearest visible selectable object in front of the leader (within 30 degrees of its facing, seen from a point 4 m behind it, so one at arm's length beside him counts), repicked every half second while he walks; standing still keeps what he has. In combat mode with enemies about the drop never runs and the pick is the nearest hostile in front, else the first hostile in sight (by bearing), else the nearest non-hostile in front, and the camera swings to it. An enemy coming into the leader's view when none has been in it for 10 s becomes the target at once (the camera swings to it, out of combat mode it asks the Enemy Sighted auto-pause). No other camera turn (Q / E and these picks) | `UpdateSelectableObjects` 0x005fa5a0, the target drop in `ProcessInput` 0x006227e0 (timer `+0x36c`), `GetNearbySelectableObjects` 0x004fc4c0, movement.md 7.1 | matches (`lib/hud/autotarget.ctx`; the keys' velocity comes from the loop after the control step; the post-auto-pause timer `+0x390` is ignored) |
| The block's slots hold what the leader can do besides the default: a hostile creature the combat feats and Attack (left), Force powers (middle), grenades (right); a mine Disable and Recover; a door or placeable that is locked: Bash on the left (not plot, area RestrictMode 0) and Security in the middle (a door only when no key is wanted, and the leader has the skill). Open, Use and Talk are in no slot, and a friendly creature's block lists nothing | `FUN_00619c20` by target kind, `FUN_00684410` (door), `FUN_006837d0` (placeable) | matches |
| A click on the target and R run entry 0 of `BuildDefaultActions`: a door Open (a locked one refuses with "locked" and OnFailToOpen, nobody unlocks it for you), then Bash on a locked non-plot door when the area allows combat; a creature Talk, or Attack when hostile and the area allows combat | `BuildDefaultActions` 0x00620620, `CSWCDoor::DefaultActionOpen` 0x00683d90 | matches |
| Slot orders: out of combat they replace what the leader was doing; in combat mode they queue behind it; Shift makes them replace; Shift with the slot's key steps to the slot's next choice | `UseSelfAction`, `OnActionButton` 0x0068b970, `HandleInputAction` 0xe2-0xee | matches |
| Slot icons: dimmed when unusable, tooltip with the name | gui.md | matches; the middle and right slots stay empty until the leader has powers and items for a target (the rules lead's) |
| Q / E: through the selectable list in view by bearing counted counter-clockwise from the leader's facing (the first is the one just left of straight ahead), wrapping; in combat mode hostile creatures only | `CycleTarget` 0x005fb050 | matches |
| R: entry 0 of the target's list | `HandleInputAction` 0xef | matches |
| A target that stops being selectable is dropped (the original keeps it 1.5 s while enemies remain in combat mode) | `UpdateSelectableObjects` | ours: dropped at once |

## Party (movement.md 6; gui.md "Party portraits")

| Behaviour | Original | State |
|---|---|---|
| Tab: the party table turns until the next member who can act is first, the others keep their order ([A B C] -> [B C A] -> [C A B]); dead members are passed over; plays GUI sound 6; works in menus too (they show the new leader) | `CSWCParty::SetLeader` 0x00635480, `CyclePartyLeader` 0x005f7960 | matches (`party::rotate_to_front`) |
| Clicking a companion's portrait makes him the leader (not a dead one); the leader's portrait opens equipment | `OnPartyMemberButton` 0x00688690 | matches |
| The old leader's camera target moves to the new leader; the yaw is kept | `SetPartyLeader` | matches |
| Followers keep up: each non-leader member with nothing to do follows at once when more than 4 m behind | `UpdateFollowLeader` 0x0051c360 (formation slots, the leader's trail, speed rules 6.2) | partly: one follow action to 2 m behind the leader instead of the trail and formation points (open: the formation offsets are not read) |
| Solo mode (V or the TB_SOLO button): pauses, asks "Do you wish to turn Solo Mode on / off?", on OK flips the party flag and runs `k_sup_solo`; the others then do not follow; only with 2+ in the party, no conversation, leader alive, else sound 2 | `ShowSoloModeConfirm` 0x0062e550, strrefs 37889-37892 | matches |
| Party selection screen pauses the world while up; Done applies at once (no confirmation: no code refers to the "Are you sure" strings) | `CSWGuiPartySelection` | matches |

## Pause (gameloop.md 6)

| Behaviour | Original | State |
|---|---|---|
| Space or Pause/Break toggles the player pause with GUI sound 6; the banner says PAUSED; the world clock stops (no movement, no timers) while the GUI and camera keep running | `HandleInputAction` 0xe0/0xf1, 6.2 | matches |
| Orders given while paused are queued (they begin, make no progress) and run on unpausing | 6.2 | matches (tested: a talk order with a walk) |
| Opening a menu pauses (the menu bit) and closing it resumes | 6.3 | matches |
| Auto-pause (install defaults: enemy sighted, mine sighted, party killed, new target selected on; end of combat round, action menu off): the first hostile in the leader's view within 30 m (a closed door hides what is behind it, so opening it onto them pauses at once), a party member going down while others stand (2 s cool-down), a slot's choice stepped (action menu), the end of a combat round, a new target in combat mode; the banner carries the reason's text | 6.4, `UpdateSelectableObjects` 0x005fa5a0 | matches. The engine and the HUD call `autopause::request{reason}` (`lib/engine/autopause.ctx`); `ingame::update` takes the frame's first request and weighs it against the option, a person playing, a conversation or menu up and a pause already on. Mine sighted: nothing calls it yet (no mines). Runs only when a person plays: headless runs and replays keep it off (`ui autopause on` turns it on). In `--no-render --speed N` runs the HUD's clocks (the 10 s latch, the 1 s out-of-view timer) tick once per N world ticks with one tick's dt, so use `--headless` to see them at the right pace |
| The banner button unpauses by click | gui.md | matches |
| Switching to another window pauses; coming back resumes unless the game was paused already | `OnAppDeactivate` 0x00401d90, `OnAppActivate` 0x00401e00 | matches (only when a person plays) |

## Minimap and HUD buttons

| Behaviour | Original | State |
|---|---|---|
| Clicking the minimap opens the map menu | `BTN_MINIMAP`, gui.md | matches |
| The arrow turns with the leader's facing, north from the ARE | `RenderMiniMap` 0x0068ab10 | matches (the HUD lead's) |
| Menu buttons, pause and solo toggles, party portraits, self slots, target block, combat bar (Disengage, Clear one) | gui.md | matches |
| Level-up arrow on a portrait when the member's XP allows a level | `UpdatePartyPortraits` 0x00687860 | matches: it stays until the member is levelled (Level Up or Auto Level Up in the character sheet; "Auto Level Up NPCs" is off by default, as in the install) |

## Cursor shapes by context

default arrow (nothing, the GUI, the leader himself); select (a pickable object that is not the target); over
the target: door (open door), talk (creature with a conversation), use (placeable, container), kill (hostile),
bash (bashable locked door), lock (Security first, ours), invalid (target with no action). Cursor ids 11-92
of the original (walk, follow, examine, transition, magic, heal, create, run and walk arrows) are never chosen by the
client's mouse code in the world and are not used.

## Moving to a point (the planner under every order)

| Behaviour | Original | State |
|---|---|---|
| The straight walk when clear, else the area's path points: the nearest point with a clear walk to the start and to the goal, a search between them, string pulling | 4.3, 4.5 | matches (A*; the original's depth-first search finds the same kind of route) |
| The nearest clear path point is looked for in a window that grows by 10 m | `FindNearestPathPoint` 0x004bd770 | matches: every point by distance, up to 64 (trying only the 8 nearest left a creature on a walled-in ramp, Carth in the Kandon garage, with no route) |
| A goal nobody can stand on (the middle of a closed door) becomes the nearest safe point | 4.8 | ours: backs off toward the start up to 3 m to a point a path point reaches; the move ends there |
| A step into a closed door sends PATH_BLOCKED (OnBlocked opens it); six blocked steps end the move | 4.9 | matches |

## Found and fixed while testing

Scripted input skipped half the real path (`ui click` missed the conversation panels, `ui key` never reached
the world, `down w` skipped the interface); Tab only swapped two members; arrows and R moved or acted in the
world; hovering showed the action cursor on anything and the attack cursor texture did not exist; a click
on a distant person talked from where the leader stood; a goal in the middle of a closed door made long moves
give up; the party screen did not stop the world; the walk and run cycles played at 1.0 whatever the speed.
