# The game loop in swkotor.exe: frame, clocks, object updates, events, transitions, pause, time of day

What one frame of the original engine does and in which order; the clocks (`CWorldTimer`) that
everything time-based reads; how the AI master spreads object updates over the frame; the event
queue behind `DelayCommand`, `AssignCommand` and `SignalEvent`; how a door, trigger or script
moves the party to another module and what happens on arrival; the pause rules; and the game
calendar. Addresses are for the Steam `swkotor.exe` after SteamStub removal (see
[README.md](README.md)). Every claim carries a confidence: **high** = read in the code, **med** =
role clear, detail inferred, **low** = plausible. The whole page was rechecked claim by claim on
2026-10-07 against the exports rebuilt after the noreturn fix ([noreturn-fix.md](noreturn-fix.md));
a med claim that says "needs a runtime check" rests on static reading alone and is surprising
enough to test before relying on it. Names are ours, in the Aurora/NWN vocabulary; the proposals
for every address below are in `kotor/re/proposals/gameloop.tsv` (git-ignored).

Related pages, and where the boundary is:

- [app.md](app.md): `WinMain`, the outer loop, input devices, audio, movies. This page refines the
  two `MainLoop`s it lists.
- [objects.md](objects.md): object classes, the id table, script slots, the action queue in brief.
  Its section 5 is superseded here for `UpdateState`, heartbeats and event delivery.
- [modules.md](modules.md): `LoadModule`, mounting, IFO/ARE/GIT reading. This page covers the
  state machine around it, what happens before and after, and the time fields.
- [vm.md](vm.md): script situations, `RunScript`; the routine handlers are summarised in section 4.
- Written in parallel: **actions.md** (the action queue, `RunActions`, each action), **combat.md**
  (rounds, attacks, death), **rules.md** (effects, saves, Force powers, skills, regeneration
  values), **movement.md** (player control, camera, walkmesh, pathing, following), **gui.md**
  (panels, the HUD, the load screen panel, fades), **dialogue.md**, **party-items-saves.md** (party
  table, save/load, the save files). This page names their entry points in the frame and stops
  there.

## 0. The model in brief

- One process, two halves. Each iteration of the `WinMain` loop runs the **client** frame
  (`CClientExoAppInternal::MainLoop` `0x00602eb0`: input, presentation objects, 3D render, GUI)
  and then the **server** frame (`CServerExoAppInternal::MainLoop` `0x004babb0`: game rules,
  scripts, AI). They talk through an in-process message ring and, more often, by calling each
  other directly. (high)
- There is **no fixed time step**. Every time-based system reads a `CWorldTimer`: a microsecond
  counter advanced once per frame from the high-resolution clock, scaled by a speed percentage,
  frozen while paused. The game day is `24 × Mod_MinPerHour` real minutes (48 minutes in almost
  every module). (high)
- The server frame is: advance the clocks, read client messages, a few party/map chores, then
  `CServerAIMaster::UpdateState` (`0x004b0b70`): **deliver every due event, then give objects
  `AIUpdate` calls round-robin within a 10 ms budget**, highest AI level first. Events queued with
  zero delay during the frame are delivered later in the same frame. (high)
- A creature's `AIUpdate` (`0x004fe210`) runs OnSpawn once, OnHeartbeat every 3.0–4.2 s,
  perception (a party check every update, a full pass every 0.2–4 s), the combat round, effect
  expiry, then its action queue; doors,
  placeables, triggers, AoEs, the area and the module run OnHeartbeat every 6 s. (high)
- A module transition is a request (module name, waypoint tag) stored on the server and executed
  at the start of a later server frame: save the module being left into `GAMEINPROGRESS:`, optionally
  autosave, unload, then load the new module over three server ticks while the client shows the
  load screen. World time does not advance during the load. (high/med)
- Pausing freezes the world clock. The AI master keeps running, but nothing that measures time
  advances; zero-delay events and instant actions still go through. GUI and camera run on a
  separate clock that is never paused. (high)

## 1. The frame

### 1.1 The outer loop

`WinMain` (`0x004041f0`, details in [app.md](app.md), "The main loop") does, per iteration in
which `PeekMessage` finds no window message: a pending video-mode change, clear the framebuffer
(skipped while a movie plays), **client `MainLoop`**, **server `MainLoop`** (when a server exists),
cheat console, `SwapBuffers` (skipped while a movie plays or a video-mode change is pending),
`CheckMovieFinished`, then two optional throttles. An iteration that finds a message dispatches it
and runs no frame. (high)

| Throttle | What | Default |
|---|---|---|
| `Sleep(1)` when `0x007a3c58` is set | yields the CPU each frame | flag never written in the exe: off (high) |
| frame-rate cap `g_fFrameRateCap` (`0x007a3c64`) | busy-waits until `1000 / cap` ms have passed since the previous wait ended, i.e. since this frame's iteration began | written only by `LoadModuleFinish` from `0x00832904`, which nothing writes: off (high) |

So the original runs uncapped (vsync aside, `[Graphics Options] V-Sync`), and the frame delta is
whatever the last frame took. Neither loop clamps large deltas: `CWorldTimer::Update`
(`0x004adbd0`), `GetFrameDelta` (`0x004adc80`) and the client loop have no clamp, and none was
found in `UpdateState` (med; individual systems clamp, e.g. player control caps its step at 1 s,
movement.md 1.1). A reimplementation should clamp the delta (say to 0.1–0.25 s); the original merely
never sees long frames outside loading, during which the clocks are paused (section 5.4).

Because the client runs first, an order issued by input in frame N reaches the server in the same
frame N (section 1.4), is acted on in frame N's `UpdateState`, and its visible result is drawn in
frame N+1. (high)

### 1.2 The client frame (`CClientExoAppInternal::MainLoop` `0x00602eb0`)

In order (high for the order, med for the roles of the smaller steps). Before step 1 the frame
resets a point and object id on the in-game GUI (`0x0062b020`, GUI `+0xc0c..+0xc18`, read in step
19). The function returns 1 (quit) when both `+0x250` and `+0x254` are set, also from the early
return in step 3 ([app.md](app.md)).

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Finish a load | client `+0x288` set, a client module (`+0x18`) and the player's client creature (`+0x20`) exist | If the area is not a minigame (area `+0x264` clear) and a leader id is waiting at `+0x338` (stored there by `0x006364c0` while loading), `0x005fb6e0` makes that creature the leader and clears `+0x338`; the load finishes on a later frame. Otherwise: input class 0 (1 in a minigame area), the player control at `+0x2a0` re-enabled (`0x006792e0(1)`), HUD mode 1; the load-screen panel (`+0x278`) removed and input re-acquired (`0x005f6e20`) when a movie is playing or the application is active; movie handling, `LeaveMovieVideoMode`. Then, **only while the application is active** (`0x007a3a38`, set by `OnAppActivate` `0x00401e00`): **resynchronise and unpause every clock** (copy the world clock `+0x24` into `+0x28`/`+0x2c`/`+0x30`, update all four and zero their next delta, unpause them, update and unpause the server world clock), and unless an autosave is pending (`0x004aed20`, server `+0x100b8`) start the fade-in, `StartGlobalFade(fade in, wait 0.5 s, length 1 s, black)` (during a conversation, GUI `+0xb4`, or when `+0xb98` is already set: set `+0xb98` so the conversation's end does it) and sound mode 0; in a minigame area the player creature takes the controls (`+0x28c`). Only then is `+0x288` marked to be cleared at the end of this frame; while the application is inactive the step repeats every frame. Input itself returns through the input-block mask: `0x005f6e20` clears its bit and arms the 0.5 s delay `+0x3dc` (step 23), whether or not an autosave is pending (med). See 5.5. |
| 2 | Advance the client clocks | `CWorldTimer::Update` | `+0x24` unless any pause bit is set, `+0x28` unless the player-pause bit is set, `+0x2c` always (section 1.6). |
| 3 | Module transition in progress? | transition block `g_pAppManager+0x14`, word 0 = 1 | read server messages (unless client `+0x90` is set); `UpdateModuleTransition` (`0x00602c90`); if still loading (block mode, word 1, is 1 or 3): set `+0x288`, draw one `RenderLoadingFrame(1/30 s, bTickServer 0, bNoRender 1)` (GUI only; `WinMain` clears and swaps), run `ProcessInput` when the block's `+0x38` is 4, and **return**: the rest of the frame is skipped. A save (mode 2) runs the whole frame. |
| 4 | Frame delta | `GetFrameDelta(+0x24) × 1e-6` → `g_fFrameDelta` (`0x0078e574`) | seconds; 0 while paused. |
| 5 | Resource manager tick | `CExoResMan::Update` (`0x00408d40`) | async loads |
| 6 | Client party update | `0x00637050(+0x270, dt)` | with a client party (`CSWCParty`, `+0x270`) and an area loaded (movement.md / party-items-saves.md) |
| 7 | `Render_BeginFrame` | `0x0044ed90` | finishes queued texture uploads |
| 8 | **Input** | `ProcessInput` (`0x006227e0`) | → `HandleInputAction` (`0x00621210`), GUI events; see 1.4 |
| 9 | Slow motion | `UpdateSlowMotion` (`0x005f7330`) | section 6.6 |
| 10 | Party-wipe countdown | `+0x1a8`, `+0x374` | only while the in-game GUI's `+0xdc` (controller-disconnected box up, set by `0x0062f780`) is clear; while `+0x374` is positive it re-opens the message box (`0x00627260`) if `+0x1ac` is set and the box is not up, else counts down on the world delta; once it runs out and slow motion (`+0x2c0`) is over: unload the module, destroy the server, main menu (6.6) |
| 11 | Game speed | `SetGameSpeed` (`0x005f2f60`) | 0.25 when client `+0x1b0` or the debug flag `0x0083291c` (never written) is set, else 1.0. It runs every frame right after step 9 and so overwrites the speed `UpdateSlowMotion` set before any clock reads it (the clocks apply the speed at their next `Update`, step 2 and server step 2); `+0x1b0` is only ever zeroed and the debug flag never written, so slow motion never slows the clocks (high from the code; surprising, a runtime check is worth making; 6.6) |
| 12 | **Server → client messages** | `CNetLayer::ProcessReceivedFrames(1)`, `UpdateStatusLoop` | skipped while client `+0x90` is set; object updates, time of day, module state (1.5) |
| 13 | Queued client script | `+0x32c` / `+0x330` | one script name (queued by `0x005edd90`) run with no `OBJECT_SELF` (`RunScript(name, 0, bOidValid 0)`) |
| 14 | Bark bubbles | queue at `+0x168`, timer `+0x16c` | the player's speech bubble queue, timed on the world delta (dialogue.md) |
| 15 | Listener and camera | area `+0x184`; `UpdateCameraInput` (`0x005f5e10`, uses the `+0x2c` clock) | steps 15–17 run only with an area loaded. The area's `+0x184` object is placed at the party leader (at a GUI-supplied point during a conversation, GUI `+0xb4`). Camera input runs unless the input class is 1 or client `+0x90` is set; while the tutorial box (GUI `+0xa0`) is up the camera's yaw inputs are zeroed instead |
| 16 | **Client objects and 3D render** | `UpdateObjectsAndRender` (`0x006048c0`) | every client object's per-frame update (vtable slot 29, all objects, no budget), then `CSWCModule::Render` (render-gui.md) |
| 17 | Area sound environment | `UpdateAreaSoundEnvironment` (`0x005ee860`) | EAX room at the listener point (normally the leader) |
| 18 | Conversation update | in-game GUI `+0x188` (client id) → server object | `CSWSObject::UpdateDialog` (`0x004cd580`), then `DeleteDialog` (`0x004cc330`) when the object's `+0x214` is set |
| 19 | In-game GUI per-frame | `0x006339c0` (`SelectDialogReply`), `0x00632180` | |
| 20 | **Enemy / mine sighting** | `UpdateSelectableObjects` (`0x005fa5a0`), `0x005f3ad0` | only in input class 0 or 4, not while loading (`+0x288`) and not while the global fade runs (`GetIsFadePanelBusy` `0x0062ac60`, `0x0062ded0`); auto-pause triggers (reasons 1 and 11, 6.4) |
| 21 | Timed client-creature effects | `0x005f7640(+0x2c dt)` | (creature id, seconds) pairs at `+0x314` (count `+0x318`), counted down on the `+0x2c` clock, which no pause stops; at zero the client creature's slot `+0xa8(0)` |
| 22 | Status-summary delay | `+0x370`, 0.25 s | when the status summary (GUI `+0xa8`) has news (panel `+0x64` bits 0–1), in input class 0, not loading, with no conversation (`+0xb4`, `+0xb98`) and no fade: after 0.25 s (counted only on frames shorter than 0.25 s) `CGuiInGame::FlushStatusSummary` (`0x0062ef90`) shows it or flashes the HUD icons |
| 23 | **GUI** | `CSWGuiManager::Update(world dt)` (`0x0040ce70`), then `Render(+0x2c dt)` (`0x0040cc50`) on `+0x274` | the global delta is swapped to the `+0x2c` delta for the GUI pass and restored after; on that delta the input-unblock delay `+0x3dc` counts down between `Update` and `Render` (at zero `0x0061fa00(0)` re-enables input); after `Render`, `0x0062b050` when the HUD (GUI `+0x90`) is not shown |
| 24 | Misc timers | `0x005f7500(world dt)`, `0x0062f780`, `+0x3e0` | `0x0062f780` opens the controller-disconnected box (GUI `+0xa4`) and sets GUI `+0xdc` when the controller is lost |
| 25 | Sound | `UpdateSoundListener` (`0x005f5370`) → `CExoSound::Update` | only with `g_pExoSound` |
| 26 | Screenshot, clear `+0x288` if the load finished in step 1 | | |
| 27 | Deferred auto-pause | `+0x390` countdown → `RequestAutoPause` | at zero, and only while `+0x320` is clear, with the reason byte `+0x398` (then reset to 0xff); also counts down `+0x38c` and `+0x39c`; 6.4 |
| 28 | **Apply a pending pause change** | `+0x37c` bit 2 | toggles the server's player pause if it differs from the request (`+0x380`), updates the HUD pause label (reason `+0x388`) (6.3); dropped, with the bit cleared, while the current server area has a transition pending (area `+0x2c4`, 5.2) |
| 29 | Tutorial popup, flush `HD0:FILEERROR` | `+0x3b8` → `0x0062f4a0`; error text at `0x008328d8` | a queued tutorial id (0xff = none) opens the tutorial box (GUI `+0xa0`) once per id below 0x2b when client option `+0x14` bit 1 is on; then recorded file errors are appended to `HD0:FILEERROR` |

### 1.3 The server frame (`CServerExoAppInternal::MainLoop` `0x004babb0`)

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Autosave interval | `UpdateAutoSaveTimer` (`0x004b1ee0`) | every frame, transitions and pauses included: real milliseconds (`GetTickCount`) summed at `+0x1b930`; past 900,000 ms (15 min) the sum resets and "autosave due" `+0x1b938` is set, after which nothing is summed until the flag is cleared (5.7) (high) |
| | *If no module transition is in progress:* | | |
| 2 | Advance the server clocks | `+0x10048` unless any pause bit, `+0x1004c` unless the player-pause bit, `+0x10050` always | (high) |
| 3 | **Client → server messages** | `ProcessReceivedFrames(1)` → `CSWSMessage::HandlePlayerToServerMessage` (`0x00527b20`), then `UpdateStatusLoop` | player orders become actions here (1.4) (high) |
| 4 | Party death and stragglers | `UpdatePartyDeath` (`0x004b6da0`) | skipped during slow motion or loading; see below (high) |
| 5 | Map exploration | `UpdateMapExploration` (`0x004b4e80`) | for each client party member, the module's `+0x218` object is updated with the member's position: reveals the area map around it (med) |
| 6 | **AI master** | `CServerAIMaster::UpdateState` (`0x004b0b70`) | only when still no transition is in progress and the server state `+0x10008` is 2 ("module running"); section 2 (high) |
| 7 | Client object updates | `UpdateClientsForPlayers(force)` (`0x004b6950`) | under the same condition as step 6, right after it: per player, every 200 ms or when forced by `+0x10014`, which is then cleared (1.5) (high) |
| 8 | **Module transition request** | `+0x10080` = 1 and the in-game GUI's `+0xdc` (controller-disconnected box up) clear | store the game time and calendar and the pause-time snapshot (`StoreGameTime`, `SetStoredPauseTime`/`Day`), save the NPC states (`CSWPartyTable::SaveAllNPCStates(0)` on `+0x1b770`), then `StartModuleTransition(+0x10084)` and clear `+0x10080` (5.3) (high) |
| 9 | **Script autosave request** | `+0x100b8` (set by `DoSinglePlayerAutoSave`) | if no transition is now in progress, the player creature is in an area and the client is not loading (otherwise the request waits): start an `AUTOSAVE` save (`RequestSaveGame(1, "AUTOSAVE", 0)`) if `HasDiskSpaceForSave` finds at least 0x641 × 16 KB free on `SAVES:` and the module is running, else do what client step 1 skipped for the pending autosave: the fade-in (or, during a conversation, GUI `+0xb98`) and the same arrival calls; then clear the request (high) |
| 10 | Pending character export, and a dead flag | `+0x100bc` is set by routine 557 `ExportAllCharacters`; the loop then runs `ProcessPendingPlayerUpdates` (`0x004b3000`) and clears it. `+0x100c0` (`0x0056c7f0`) is only ever cleared | (med) |
| | *If a transition is in progress:* | | |
| 2' | The load or save state machine | transition block mode 1/3 (load) or 2 (save) | client messages are not processed (`ProcessReceivedFrames(0)`); nothing happens while the block's `+0x38` is set; mode 1/3: one load tick, mode 2: `DoSaveGame` (`0x004b3110`); section 5.4 (high) |
| | *Always:* | | |
| 11 | Shutdown countdown | `UpdateShutdownCountdown` (`0x004b4ab0`) | NWN's timed server shutdown on the high-resolution clock (messages to every player when the remaining time crosses 60 and 30 s); at zero `DestroyServer` when no player is listed (`+0x10020` = 0), else `0x004b69c0`; unused in practice (low) |
| 12 | 10 s interval | `0x004b1e10` | result ignored (high) |

**Party death and stragglers** (`0x004b6da0`; the death rules themselves are combat.md's, 8.2):
skipped during slow motion or while the client is loading. On real milliseconds (the
high-resolution clock): if *every* member of the client party is down (`GetIsDying`), the client's
party-wipe sequence starts (`StartDeathCamera` `0x005edc40` → `0x005f7200`, 6.6). While *any*
member is down, a counter (`+0x100d4`) grows by the real frame time, and once a second
(`+0x100d0`) a scan of the area's creatures looks for one that is not player-controlled (`+0xa88`),
has reputation below 11 toward the last member of the client party list and perceives a party
member (`IsPerceivingPartyMember` `0x004f7650`); finding one resets the counter, and so does nobody
being down. Past 5 s each downed member is moved to a free spot within 5 m, gets a RESURRECTION
effect (type 4, which acts only if `IsRaiseable` `+0xf0` is already set, combat.md 8.2) and has
`+0xf0` set; and unless solo mode is on (party table `+0x190`, 6.7), each member farther than 40 m
from the leader (client party member 0) is moved to a free spot within 5 m of its formation place
in the client party (`+0x4c + 0x88 × index`). The counter is not reset there, so this repeats every
frame while anyone is still down. The clock is real, so all of this also runs during a pause. (high)

### 1.4 How input becomes game commands

1. `MainWndProc` and DirectInput feed `CExoInput` ([app.md](app.md)).
2. Client step 8, `ProcessInput` (`0x006227e0`), maps device events to game actions for the
   current input class and calls `HandleInputAction` (`0x00621210`) or the GUI manager.
3. The client turns a game action into one of three things (high for the mechanism, the full
   table is actions.md's section 1.7 and movement.md's):
   - a **message** `'p' major minor payload` written with the `CNWMessage` writers and sent by
     `SendPlayerToServerMessage` (`0x00677410`) into the server's 128 KB ring (`CNetLayer`,
     `SendMessageToPlayer` `0x005d4cb0` writes into the *peer's* ring). Builders found:
     Input (major 6) minors 2 attack (`0x00677a90`), 3 door (`0x00677d70`), 7 skill
     (`0x00677b10`), 8 talk (`0x00677ea0`), 9 item/talent (`0x00677bd0`), 0xb use
     (`0x00677d10`), 0xc unlock (`0x00677de0`), 0x12 cast (`0x006776a0`), 0x21 (`0x00677e50`,
     three bytes with no payload, written straight to `SendMessageToPlayer`), 0x24 take item (`0x00677870`); also Module 3/4 and 3/5, GuiContainer 0x19/2,
     GuiInventory 0xd/1, Inventory 0xc/1, Party 0xe/2, Login 2/1 and 2/0x13;
   - a **direct call** into the server objects (the client and server share memory): for example
     keyboard/stick movement is integrated by `CSWCPlayerControl::Update` (`0x00679940`, called
     from `ProcessInput`), which moves the client creature (`CSWCCreature::MoveDirect`
     `0x00614b90`) and tells the server at once through `MoveCreatureFromClient` (`0x004aead0`)
     and `SetCreaturePositionFromClient` (`0x004aeaa0`) (movement.md 1.3); and the pause key
     (`HandleInputAction` → `RequestPause` `0x005f2e10`, reason 4) records a request at client
     `+0x37c` that client step 28 applies at the end of the same client frame through
     `TogglePlayerPause` (`0x00677800` → the server's `TogglePauseState(2)`);
   - a purely client-side effect (camera, GUI).
4. Server step 3 drains the ring: `CServerExoAppInternal::HandleMessage` (`0x004b15d0`) sends
   `'p'` messages to `CSWSMessage::HandlePlayerToServerMessage` (`0x00527b20`, dispatch on the
   major byte: ServerStatus 1, Login 2, Module 3, Area 4, GameObjUpdate 5, **Input 6**, Gold 8,
   Chat 9/0xb, Inventory 0xc, GuiInventory 0xd, Party 0xe, Cheat 0xf, CharList 0x11, Dialog 0x14,
   GuiCharacterSheet 0x15, QuickChat 0x16, GuiContainer 0x19, Journal 0x1c, LevelUp 0x1d,
   GuiQuickbar 0x1e, MapPin 0x20, Death 0x25, Character_Download 0x2b, ShutDownServer 0x2f,
   PlayModuleCharacterList 0x31), and `'s'` text commands to the admin handler
   `HandleServerAdminMessage` (`0x00528380`: `Echo`; `ServerStatus.GetStatus`, `.GetModuleList`,
   `.GetPlayerList`; `Module.Load <name>`, `Module.Run`, `Module.Save …`; `Control.Boot`,
   `.SAPass`, `.Say`; otherwise server-option assignments). (high)
5. The Input handler (`HandlePlayerToServerInputMessage` `0x005254c0`) works on the creature the
   player controls and mostly adds actions to its queue (actions.md 1.7); a few minors act at
   once (the pause minors below, for example). Those actions run in the same
   frame's `UpdateState`, when that creature's turn comes (the player and party are on AI level 4,
   which goes first). Minor 0x18 toggles the player pause and 0x19 sets it (6.3). (high)

### 1.5 Server → client: how state flows back

Three channels (high unless marked):

| Channel | When | What |
|---|---|---|
| Direct push of dirty state | end of every `UpdateState`, before `UpdateModuleAndArea` | for each object on any of the five AI levels (not the module or an area) whose `+0x1f8` is set and that has a client twin (`CSWSObject::GetClientObject` `0x004cc2b0`, cached at `+0x224`): dirty bit 0 → client slot `+0x134(animation +0xd4, +0xd8)`, bit 1 → `+0x12c()` (position), bit 2 → `+0x130(orientation +0x9c)`; bits at `+0x1fc`, tested and cleared by `0x004cc220` / `0x004cc250` |
| Game-object update messages | while the module is running (server step 7): every 200 ms per player, or at once when `+0x10014` is set | `UpdateClientGameObjectsForPlayer` (`0x004b3ec0`) → `CSWSMessage` `0x00578520`; also re-sends the controlled object id when it changed and the object is in an area, and INVALID when it has left its area (`0x0056f430`) |
| Event messages | when something happens | time of day (3/3, `0x0056a5f0`), module state (3/0xc `0x0056cc50`, 3/0xd `0x0056c850`; the client also handles 3/0xb, for which no server sender was found), load progress (0x2c/2 `0x0056c910`, 0x2c/3 `0x0056c980`), area load, feedback, dialogue … read by the client in its step 12 next frame, or in its step 3 during a transition (`CSWCMessage::HandleServerToPlayerMessage` `0x0066a640`) |

Pause state is not a message: the server calls the client directly (`NotifyClientPauseState`
`0x0056c9f0` → `CClientExoApp::SetPauseState` → `CClientExoAppInternal::SetPauseState`
`0x005f7fa0`). (high)

Every client object then advances its own animation in `UpdateObjectsAndRender` with the world
delta (0 while paused). (med)

### 1.6 Clocks: `CWorldTimer`

`CWorldTimer` (0x44 bytes, constructor `0x004ae4c0`) is a game clock in microseconds plus a
calendar origin. (high)

| Offset | Field |
|---|---|
| `+0x00` / `+0x04` | fixed-step mode flag / steps per second (`SetFixedStep` `0x004ae170`, which also zeroes current and previous; set only by debug and capture code, e.g. the console's "Frame rate set." command `0x005ee4a0`; normally off) |
| `+0x08` | speed percentage (100); `SetSpeedScale(f)` (`0x004ae190`) stores `(int)(f × 100)` |
| `+0x0c` | current time, µs (64-bit) |
| `+0x14` | time at the previous `Update` (64-bit) |
| `+0x1c` | last high-resolution clock reading |
| `+0x24` | paused flag |
| `+0x28` / `+0x2c` | the (day, ms) snapshot `GetWorldTime` returns while paused |
| `+0x30` / `+0x34` | calendar origin: day and ms added to the counter |
| `+0x38` | minutes of real time per game hour (byte, 5 from the constructor; `SetMinutesPerHour` `0x004adba0` turns 0 into 5 and recomputes the next two) |
| `+0x3c` | ms per game day = `+0x38 × 1,440,000` |
| `+0x40` | s per game day = `+0x38 × 1440` |

Operations (high):

- `Update` (`0x004adbd0`): previous = current; current += (clock now − last reading) × speed / 100;
  last reading = clock now. In fixed-step mode current += `1e6 / steps × speed / 100` instead.
  **`Update` does not look at the paused flag**: pausing works because `GetWorldTime` returns the
  snapshot and `GetFrameDelta` (`0x004adc80`, current − previous) returns 0 while the flag is set;
  the main loops also skip `Update` on a paused clock (table below).
- `GetWorldTime(&day, &ms)` (`0x004ade40`): while paused, the snapshot; otherwise
  `day = +0x30 + floor(t / msPerDay)`, `ms = +0x34 + t mod msPerDay` with `t` = current µs / 1000,
  then normalised so `0 ≤ ms < msPerDay`.
- `PauseWorldTimer` (`0x004adff0`) takes the snapshot and sets the flag; `UnpauseWorldTimer`
  (`0x004ae030`) clears it and moves the origin so the clock resumes from the snapshot: paused time
  is lost, not caught up.
- `SetWorldTime(day, ms)` (`0x004adde0`) sets the origin; `CopyFrom` (`0x004adef0`) copies another
  timer except its high-resolution stamp `+0x1c` (speed reset to 100); `AddWorldTimes`
  (`0x004adf50`, −2 for an invalid time of day), `SubtractWorldTimes` (`0x004ae460`, returns −2 and
  leaves the outputs alone when the first time is earlier), `CompareWorldTimes` (`0x004adfa0`,
  −1/0/1, −2 for an invalid time of day). A time of day ≥ ms per day is rejected by Add and Compare
  (Subtract skips its order check and computes anyway), which matters for `DelayCommand` (4.3).

**Which clock drives what.** The server owns three, the client four. Pause bit 1 (server
`+0x10078`, client `+0x1cc`) is the time stop, bit 2 the player pause. The main loops advance a
clock only while it is not paused (server `0x004babb0`, only while no module transition runs;
client `0x00602eb0`); `SetPauseState` (server `0x004b8110`, client `0x005f7fa0`) pauses and, on
unpause, resyncs them by `CopyFrom`. (high for the update rules, med for the uses)

| Clock | Advanced | Paused by | Used for |
|---|---|---|---|
| server `+0x10048` world timer | each server frame unless a pause bit is set | any pause bit | game time, every heartbeat, event times, effect durations, everything time-based on the server |
| server `+0x1004c` | each server frame unless bit 2 is set | player pause | objects exempt from a time stop (pause type 1, list `+0x10074`), through `GetActiveTimer`; copied from the world timer when the time stop ends |
| server `+0x10050` (`GetPauseTimer` `0x004aee00`) | every server frame | never | objects exempt from the player pause (list `+0x10070`, empty in practice); the 300 ms action-queue display tick of 2.3 |
| client `+0x24` world | each client frame unless `+0x1cc` & 3 | any pause | `g_fFrameDelta` for client objects, animation, particles, texture animation |
| client `+0x28` | each client frame unless `+0x1cc` & 2 | player pause | the time-stop twin of `+0x24` |
| client `+0x2c` interface | every client frame | never (resynced after loading and pauses) | GUI render, camera (`UpdateCameraInput`), `CSWCModule::Render`'s argument, real-time effects |
| client `+0x30` aux (`GetAuxTimer` `0x005ed510`) | once per area render, by `0x006097f0` (from `CSWCModule::Render`) | never | its delta goes to the client area's `+0x184` object (vtable slot 7) (low) |

`GetActiveTimer(objectId)` (`0x004b6c40`, forwarder `0x004ae830`) returns, while the player pause
is on, `+0x10050` for an object in the player-pause exempt list; while only the time stop is on,
`+0x1004c` for an object in the time-stop exempt list (`IsObjectPauseExempt` `0x004b48e0`); else
the world timer. Creatures read their update time (`AIUpdate`), heartbeat, perception,
movement, trap detection and spell actions through it, and every object's effect list
(`UpdateEffectList`) does too; the AI updates of doors, placeables, triggers, encounters, AoEs,
items, the area and the module read the world timer directly. (high)

Speed: `SetGameSpeed(f)` (`0x005f2f60`) sets the speed of the client `+0x24`, `+0x2c`, `+0x30`
timers and the server `+0x10048`, `+0x10050` timers (not client `+0x28` or server `+0x1004c`).
It is called every client frame (step 11) with 0.25 when client `+0x1b0` or the debug flag
`0x0083291c` is set, else 1.0, right after `UpdateSlowMotion` (`0x005f7330`), which calls it too
(6.6); the per-frame call therefore overwrites the slow-motion speed, and as `+0x1b0` is only
ever zeroed and the debug flag never written, all these clocks always run at 100 % (high from the
code; a runtime check is worth making).
(high for the calls)

## 2. Object updates: the AI master

### 2.1 AI levels

`CServerAIMaster` (server `+0x10044`) keeps five lists of object ids, level 0 to 4, at
`+4 + 0x10 × level` (`{array, count, capacity, round-robin cursor}`); an object remembers its
level at `+0x78` (−1 = not listed). `AddObject` (`0x004b0850`) moves an object between lists,
`SetAILevel` (`0x004b08a0`) does nothing when the level is unchanged. Waypoints and sound objects
are never listed; every other object type joins level 0 in its constructor. (high)

| Level | Who | Set by |
|---|---|---|
| 4 | the PC and party members under player control | `CSWSCreature::AIUpdate` when `IsPC` (stats `+0x6c`) or player-controlled (`+0xa88`); `CSWSCreature::PostProcess` (`0x004f1c40`, after loading) for the PC; `SetPlayerControlled(1, bUpdateAILevel)` (`0x004fdb20`) (high) |
| 3 | nobody | no code sets it, no script routine exists (NWN's script-set "high") (high) |
| 2 | creatures in combat mode (`+0x4e0` = 1) | `AIUpdate` raises level 0/1 creatures in combat to 2; `SetPlayerControlled(0, bUpdateAILevel)` (leaving the party) sets 2 (high) |
| 1 | active objects of an area that holds a player | `CSWSArea::IncrementPlayersInArea` (`0x00508c20`): when the first player enters, every level-0 creature, AoE and trigger, every placeable that is not Static (`+0x398`) and every door that is not Static (`+0x3c0`) and has an OnHeartbeat script (`+0x250`) go to 1 (`0x00507220`). `CSWSCreature::AddToArea` (`0x004fa100`) moves 0 to 1 when the area's player count `+0x128` is positive and 1 to 0 when it is zero (other levels are left alone); a creature spawned by an encounter (`0x00591ca0`) gets 1 or 0 the same way; `ActionStartConversation` and the talk order lift 0 to 1. A creature leaving combat drops from 2 to 1 (high) |
| 0 | everything else: items, encounters, stores, Static placeables and doors, doors without OnHeartbeat, objects of areas without players | constructors; `DecrementPlayersInArea` (`0x00508c40`) drops level-1 **creatures** (only) to 0 when the last player leaves (`0x00507340`; other level-1 objects stay on 1); a creature's perception tick in `RunHeartbeat` drops it from any level to 0 when its area has no player (high) |

In KOTOR a module has one area and the player is always in it, so in practice: party on 4,
fighting creatures on 2, everything that acts on 1, the rest on 0.

### 2.2 `CServerAIMaster::UpdateState` (`0x004b0b70`)

Read in the code and the disassembly (high):

```
now = GetWorldTime(world timer)                     // once; the clock does not move during the frame
remaining = 10,000 µs
for level = 4 down to 0:
    budget = (level > 0) ? remaining × 60 / 100 : remaining
    start = clock(); elapsed = 0
    loop:
        // movement pre-pass, before the budget check (its time is counted only later, see below)
        for each creature on this level with the flag +0x1f8 set whose first queued action
            is MOVETOPOINT (1) or FOLLOWLEADER (0x3d), or whose movement state +0xa8c is 4, 5, 6:
                UpdateMovement(creature)            // 0x0051d9c0; result 2 sets +0xa8c = 1
        // events
        while CompareWorldTimes(queue head's (day, ms), now) <= 0:   // −2 (invalid time) counts too
            pop it and deliver it (4.4)
        // one AIUpdate; "elapsed" is measured after the previous AIUpdate (0 on the first pass,
        // so the pre-pass and event time of this pass are only counted after the next update)
        if elapsed <= budget:
            cursor = (cursor + 1) mod count          // the cursor persists across frames
            obj = list[cursor]
            if obj is missing, or is not an object type (< 5), or obj == the first object
               updated at this level this frame:  stop this level
            else obj.AIUpdate()                      // vtable slot 28; >= 75 ms: debug feedback 0xa3
                                                     // to the players (0x004ce6e0), only while the
                                                     // server flag +0x1006c is set
            elapsed = clock() − start
        if the queue head is now due: stop this level
        if elapsed > budget: stop this level
    remaining −= min(elapsed, budget)
for each object on every level (4 → 0) with the flag +0x1f8 set and a client twin:
    push dirty animation / position / orientation to it (1.5)
if a module is loaded: module.UpdateModuleAndArea()   // 0x004c6dc0, section 2.6
```

Consequences an implementer must keep:

- **Each level gets at least one `AIUpdate` per frame** (elapsed is 0 on the first pass) unless
  its list is empty or its next entry is missing, and a level's round-robin resumes where it
  stopped last frame. Under load, low levels update less
  often; with KOTOR's object counts usually every object is updated every frame. (high/med)
- **A due event ends the current level.** An `AIUpdate` that queues a zero-delay event (a
  `SignalEvent`, `AssignCommand`, …) makes the level stop; the event is delivered in the next
  level's first pass, right after that level's movement pre-pass (level 0's wait for the next
  frame), and the interrupted level continues next frame from its cursor. (high)
- **Movement runs ahead of the budget check** for every walking creature of a level, before every
  `AIUpdate` of that level (so possibly several times per frame; it is time-based and idempotent
  within a frame). Its time and the event time are added to `elapsed` only by the clock reading
  after the pass's update step, so a pass that finds the budget already spent is not charged for
  them. Movement itself is movement.md's. (high for the call pattern)
- Events are delivered even when no `AIUpdate` happens, and before the first one: scripts queued by
  the client or by the previous frame run first. (high)

### 2.3 What a creature does per update (`CSWSCreature::AIUpdate` `0x004fe210`)

In order (high for the order; the named sub-systems belong to the pages in brackets):

1. Two debug hooks (one-shot "set HP to 1" on a player-controlled creature, `0x008327f8`; a
   distance printout, `0x00832838`); three more later in the function (`0x008327e8`, `0x008327ec`
   / `0x008327f0`, and `0x00832800`, which zeroes the regenerated Force points once). Nothing in
   the exe sets these flags.
2. `start` = the high-resolution clock (the action budget of step 8 counts from here). If the
   creature is the PC (stats `+0x6c`) or player-controlled (`+0xa88`) and not on level 4:
   `SetAILevel(4)`.
3. **`RunHeartbeat(1)`** (`0x004eb6e0`): OnSpawn once, OnHeartbeat, perception (2.4).
4. `now` = its active clock; `dt` = now − last update (`+0xa8/+0xac`), in ms, stored at `+0xcc`
   (0 if now is earlier). Every per-creature countdown below subtracts `+0xcc`.
5. **`UpdateCombat`** (`0x004faf20`): combat-round timers, only with a combat round (`+0x9c8`) and
   skipped while the player pause is on (combat.md).
6. `0x004ed110`: the battle-music countdown `+0x384`; when it runs out, and the creature has a
   client object, the area's sound object (`CSWSArea+0x208`) gets `MusicBattle(0)` (combat.md 3.6,
   battle music).
7. **`UpdateEffectList(now)`** (`CSWSObject::UpdateEffectList` `0x004d1730`): periodic effects tick
   (REGENERATE 7, POISON 0x23, which queues event 14 REMOVE_EFFECT when its duration is over,
   DISEASE 5), and a temporary effect whose expiry time has passed is removed; a removal, a
   regeneration heal or a disease tick restarts the scan (rules.md 1.6).
8. **`RunActions(now, start)`** (`0x0057f4a0`): runs actions until 1000 µs have passed since
   `start`, so steps 3–7 count against that budget (actions.md 1.3).
9. last update = now.
10. Ground snap, when in an area: z = walkmesh height at (x, y) (`0x004bc380`); a player-controlled
    creature other than the player creature that is off the walkmesh (while the in-game GUI's
    `+0xb4` and `+0xc0` are clear) is moved to a free spot within 5 m of its client party-table
    position (`FindNearestSafePosition` `0x004be860`), but z is then recomputed at its old (x, y)
    (med, needs a runtime check); jumping states 4/5 add `+0xa94`; `SetPosition` (movement.md).
11. `UpdateActivityFromQueue` (`0x004f1460`: recomputes `+0x9f2/+0x9f4` from the queued actions,
    low) and, in an area,
    trap and mine detection with the Awareness skill (`DoTrapDetection` `0x004fa390`, low;
    rules.md).
12. In combat mode (`+0x4e0`): for combat reason 1 (`+0xac0`, attacked) stealth is dropped unless
    locked (`+0xa00` bit 0); the combat timeout `+0x4e4` (8000 ms) counts down and, once it is
    below 1, `SetCombatState(0)` leaves combat (combat.md 3.6). Then the cooldown `+0xab0`, and in
    combat mode a 3000 ms tick at `+0x52c` whose only call (slot 37, `GetDead`) has its result
    ignored (low).
13. **Regeneration** for player-controlled creatures that are neither dead nor dying: hit points by
    `regeneration.2da HealthRegen` % of max HP per second and, when max FP > 0, Force points by
    `ForceRegen` % of (max + temporary) FP per second; row 1 `OutOfCombat` out of combat and in a
    fight the creature started (`+0xac0` = 2), row 0 `InCombat` only when it was attacked first
    (`+0xac0` = 1). Shipped values 0/0 and 0/1, i.e. only Force regenerates, 1 % per second (high;
    rules.md 3.8 has the details).
14. More countdowns: `+0x538` while `+0x534` is set (both cleared when it runs out); `+0x530`
    (reloads 1500 ms while playing animation 10004/10086/10087); then, if `+0x9d4` is set (the
    player character, objects.md 4), every 300 ms measured on the server pause clock `+0x10050`,
    `UpdateActionQueueDisplay` (`0x004f6f30`, actions.md 1.2); eight countdowns at `+0x9a8`; an
    8000 ms loop at `+0x398` while the cheat flag `0x007a1b28` is 1 (its initial value) (low for
    their meaning).
15. The combat-information recompute flag `+0x344` (set by effect removals, rules.md 1.3): when
    set, `CSWSCreatureStats::UpdateCombatInformation` (`0x005addc0`) and clear it.
16. AI level: combat mode on and level 0/1 → 2; combat mode off, level 2 and in an area → 1 if the
    area holds a player, else 0.
17. Stealth XP, in an area: while the area pays stealth XP (`+0x2c0`) the viewer's countdown
    `+0xaa4` runs; when it runs out (or is 0xffffffff) the area's current amount `+0x2b8` loses
    `+0x2bc` (not below 0, `0x00506aa0`) and the countdown is cleared; with stealth XP off it is
    just cleared (rules.md 5.3).

### 2.4 Heartbeat, spawn and perception (`CSWSCreature::RunHeartbeat` `0x004eb6e0`)

All times from the creature's active clock. Each interval test looks only at the time-of-day part
of the difference (`SubtractWorldTimes` `0x004ae460` borrows a day into it), so against a last run
of 0 the elapsed time is the current time of day. (high)

`AIUpdate` calls `RunHeartbeat(1)` on every update; `CSWSCreature::EventHandler` (`0x004fece0`)
calls `RunHeartbeat(0)` when an event reaches a creature whose spawn flag is still 0. With 0 only
the first-call branches below can fire. (high)

**OnSpawn**: while the "spawn fired" flag `+0x34c` is 0, every call runs `ScriptSpawn` (`+0x270`),
so OnSpawn runs exactly once, **on the creature's first `AIUpdate`, or on the first event that
reaches it if that comes earlier** — not when it is created. Right after OnSpawn the flag is set,
unless the creature was spawned by an encounter (`+0xa24` ≠ `OBJECT_INVALID`) or is
player-controlled (`+0xa88`) (asm `0x004eb7a2`); for those two it stays 0 until the end of the
call, so the rest of that call is a "first call". (high)

**OnHeartbeat**: due when `RunHeartbeat(1)` finds `now − lastHeartbeat (+0x350 day / +0x354 time)
≥ interval (+0x358)`, or on a first call. Then:

- a counter `+0x394` (constructor: `rand() % 100`) is incremented; the heartbeat really fires only
  if the creature is not on level 0, or the counter reached `interval / 64` (46–65 due checks), or
  it is a first call. Level-0 creatures therefore heartbeat much more slowly. (high)
- it runs `ScriptHeartbeat` (`+0x230`) only if the creature is not dead (slot 37), and, except on
  a first call, only once a previous heartbeat time exists (`+0x354` non-zero). So an ordinary
  creature's first due check only records the time and its first OnHeartbeat comes one interval
  (3.0–4.2 s) after its first update; only an encounter-spawned or player-controlled creature runs
  OnSpawn and OnHeartbeat in the same call; (high)
- then, for a creature whose debilitating state byte `+0x8ed` (combat.md 2) is 1, 2 or 0xb, it runs
  `statescripts.2da` row 3, 2 or 1 `SCRIPTNAME` (`k_sup_static`, `k_sup_fear`, `k_sup_static`) and
  makes the creature uncommandable (`+0xe8 = 0`); then `0x00518660`, which ages two timed lists
  (`+0x93c` entries dropped after 30 s with feedback message 0x2b, `+0x940` entries after 60 s)
  (low: what the lists hold);
- last heartbeat = now; **interval = 3000 + rand() % 1200 ms** (the constructor rolls the first
  interval the same way). These two happen whenever the level-0 test passes, whether or not the
  script ran.

**Perception** (`UpdatePerception(mode)` `0x0051b050`), two timers. Outside a first call both need
`RunHeartbeat(1)`:

| Timer | Who | Period | Mode |
|---|---|---|---|
| A (last run `+0x360/+0x364`, period `+0x35c`) | creatures that are not player-controlled (`+0xa88` = 0) | meant: every 4000 ms (`300 + rand() % 400` ms, re-rolled after each run, for a PC `+0x9d4` that is not player-controlled, which does not normally happen) | 1: check only the client party's members |
| B (last run `+0x388/+0x38c`) | everyone | the PC (`+0x9d4`): every 200 ms; everyone else: every 4000 ms | 2 (not player-controlled: everyone but player-controlled creatures) or 0 (player-controlled: everyone) |

**Timer A never stores its last run**: `+0x360/+0x364` are zeroed by the constructor (`0x004f7a10`)
and written nowhere else, so "time since the last run" is the time of day, and mode 1 runs on
**every `AIUpdate`** except during the first 4 s of each game day. A faithful port checks the party
every update; mode 1 is cheap (it only looks at the party members). A first call runs mode 1 for
any creature (it does nothing for a player-controlled one). (high)

Timer B, like the heartbeat, is throttled on level 0 (a counter `+0x390`, constructor
`rand() % 100`, must exceed 149; it is re-randomised to `rand() % 50` after each pass). A pass calls
`UpdatePerception` only once a previous pass time exists (`+0x38c` non-zero) or on a first call, so
an ordinary creature's first pass only records the time and its first full perception comes 4 s
later (200 ms for the PC); an encounter-spawned or player-controlled creature perceives on its
first call. After each pass, a creature not on level 0 whose area holds no player (area `+0x128` =
0) is put on level 0 (`SetAILevel`). (high)

`UpdatePerception` returns at once for a dead creature other than the PC (`+0x9d4`). A full pass
(mode 0 or 2) first rechecks every creature already in the perception list (`+0x920`, count
`+0x924`), removing those that no longer exist (`0x00517960`), then checks the creatures not yet in
the list that are within the radius. (high)

Ranges (`GetSightRange` `0x004efc70` → `+0x914`, `GetHearingRange` `0x004efd20` → `+0x918`; the
pass uses the larger as a radius, scanning the area's x-sorted creature list `+0x190` from
x − radius to x + radius):

- PCs: `ranges.2da` row 12 `PercepRngPlayer` (250 / 20) (high);
- other creatures: the UTC's `PerceptionRange` byte (default 11) as a `ranges.2da` row, where 11
  means "use `appearance.2da PERCEPTIONDIST`" (itself a `ranges.2da` row) (high);
- any creature except the player's creature (`GetPlayerCreatureId`) while in combat (`+0x4e0`):
  row 18 `PartyCombat` (35 / 20) (high).
  Party members get row 12 or 11 when they join (`0x006364c0`), and `CSWCParty::SetLeader`
  (`0x00635480`) rewrites them on a leader change (actions.md).

The individual check (`DoPerceptionCheck` `0x00502ac0`: line of sight, stealth, the ON_PERCEPTION
event) is rules.md's (5.3) and combat.md's.
Its gate: the player's creature (`GetPlayerCreatureId`) as viewer skips the range and line test (its
sight test then applies its own range, rules.md 5.3); any other viewer needs the target within the
larger of its two ranges and `ClearLineOfSight` (`0x0050c330`) clear, from 1.5 m above each foot:
the room walkmeshes (materials with LineOfSight 1) and, through `TestSegmentAgainstObjects`
(`0x00506650`), the walkmeshes of every door and placeable of the area in their current state (a
closed door's DWK blocks, an open one's does not), the two creatures themselves excluded. Hearing
is asked whatever the gate says (rules.md 5.3). So a closed door keeps the other side from being
seen and from a ranged attack's line (actions.md 3.13 step 5).

### 2.5 Other object types

| Type | `AIUpdate` | Per update, in order | Conf. |
|---|---|---|---|
| placeable | `0x005849d0` | OnHeartbeat (`+0x2b4`) every ≥ 6000 ms of world time (last at `+0x348/+0x34c`; the first due check only records the time; skipped when dead); `UpdateEffectList`; `RunActions` | high |
| door | `0x005889c0` | same, OnHeartbeat `+0x250`, last at `+0x30c/+0x310` | high |
| trigger | `0x0058d760` | OnHeartbeat (`+0x244`) every 6000 ms (no first-time skip, no death check); for a trap trigger (`+0x2bc`, `Type` 2) the visibility animation: 10144 (shown) once the trap is flagged (`+0x2c8`, set by the flag-trap action), or when the player's creature shares its faction, is at reputation ≥ 90 with it (`GetReputation`) or is in its detected-by list (`+0x2a8`), else 10143 (hidden) (med); `RunActions`. No effects | high |
| area of effect | `0x00595d10` | `dt` at `+0xcc`; OnHeartbeat (`+0x260`) every 6000 ms (last at `+0x280/+0x284`; the first due check only records the time); follows its creator (`+0x24c`) unless stationary (`+0x230`), destroying itself (event 11) when the creator is gone; duration countdown `+0x288` (when `+0x28c` = 1) → destroy, skipping `RunActions`; `RunActions` | high |
| encounter | `0x00593fb0` | spawn the next pending creature, one per update (`0x00591ca0`, which sets its AI level by the area's player count); respawn when `Reset` and `ResetTime` s passed since exhaustion and the count `+0x2c8` is under `Respawns` (−1 = always); while active (`+0x238`): heartbeat **as a SIGNAL_EVENT** (script event 0) every 6000 ms (the first due check only records the time), and `RunActions` | high |
| item | `0x0055cb60` | recharges timed properties: a property of type 10 whose sub-value (+6) is 14–18 and that is marked used is made usable again 60/120/180/240/300 s after its use time. No actions, no heartbeat | med |
| store, waypoint, sound | empty | — | high |

Doors and placeables run their heartbeat script directly, not through the event queue; only the
encounter uses an event. All of these read the world timer, so all of them stop while paused.

### 2.6 The module and the area

At the end of `UpdateState`, `CSWSModule::UpdateModuleAndArea` (`0x004c6dc0`) alternates frames:
(high)

- **Module frame** (`CSWSModule::AIUpdate` `0x004c6c90`): if ≥ 6000 ms of world time passed since
  `+0x128/+0x12c`, run `Mod_OnHeartbeat` (`+0xb0`; skipped the first time) and stop; otherwise
  `UpdateTime` (7.4) and, while a time stop is on, `CheckTimeStopExpired` (`0x004c6480`, 6.5).
- **Area frame** (`CSWSArea::AIUpdate` `0x00508a30`, for the module's current area `+0x40`): weather
  (below), then the area's OnHeartbeat (`+0x164`) every 6000 ms (`+0x13c/+0x140`, first skipped).

Weather (med): only for an area with no forced weather (`+0x220` = −1) and not flagged interior
(`+0x4` bit 0): every 300,000 ms (5 min) roll `rand() % 100` against `ChanceRain` (`+0xa8`), or
`ChanceSnow` (`+0xa9`) when there is no rain chance, and start or stop the weather
(`SetWeather` `0x00508050`). Only two shipped modules have a non-zero chance (probe, section 7.5).

Note that module and area heartbeats can drift by a frame (they are checked every other frame), and
that a SIGNAL_EVENT with script event 0 to the module or area runs its heartbeat script and resets
its heartbeat timer. (high)

## 3. Timing constants

| Constant | Value | Where | Conf. |
|---|---|---|---|
| AI budget per frame | 10,000 µs; levels 4..1 take 60 % of what is left, level 0 the rest | `0x004b0b70` | high |
| slow `AIUpdate` warning | 75,000 µs | `0x004b0b70` | high |
| `RunActions` budget | about 1 ms per call | `0x0057f4a0` (actions.md) | high |
| creature heartbeat | 3000 + rand() % 1200 ms (3.0–4.2 s) | `0x004eb6e0` | high |
| placeable, door, trigger, AoE, encounter, area, module heartbeat | 6000 ms (≥) | their `AIUpdate`s | high |
| perception (full pass), everyone / the PC | 4000 ms / 200 ms | `0x004eb6e0` | high |
| perception (party check) | every `AIUpdate` in practice (meant 4000 ms; last-run time never stored) | `0x004eb6e0` | high |
| combat round | 3000 ms | `StartCombatRound` `0x004d5f70` (combat.md) | high |
| `RoundsToSeconds(n)` / `TurnsToSeconds(n)` / `HoursToSeconds(n)` | 3 n / 30 n / `MinPerHour` × 60 n seconds | `0x00544e50` | high |
| client object update messages | every 200 ms | `0x004b3ec0` | high |
| transition delay and fade | 500 ms, fade out 0.5 s; fade in 1 s after 0.5 s | door/trigger/area handlers, client step 1 | high |
| transition range | every party member within 30 m of the leader | `0x00635350` | high |
| autosave interval | 15 min of real time | `0x004b1ee0` | high |
| party revival | 5 s with no perceived hostile, checked every 1 s | `0x004b6da0` | med |
| straggler teleport | farther than 40 m from the leader | `0x004b6da0` | med |
| weather roll | 5 min | `0x00508a30` | med |
| day | `24 × MinPerHour × 60,000` ms; 7,200,000 at the default 5, 2,880,000 at KOTOR's usual 2 | `CWorldTimer` | high |

Heartbeats and rounds are independent: a creature's heartbeat is its own 3.0–4.2 s timer, combat
rounds are 3 s and run from `UpdateCombat`, and nothing aligns them. NWN's 6 s heartbeat survives
only for non-creature objects. (high)

## 4. Events and delayed commands

### 4.1 The queue

`CServerAIMaster +0x54` is a linked list of 0x18-byte nodes `{day, time, caller, target, event id,
payload}` sorted by absolute world time (high). `AddEventDeltaTime(days, ms, caller, target, id,
payload)` (`0x004b08d0`) adds the delta to the **world timer's** current time (whatever the target's
active clock) and calls `AddEventAbsoluteTime` (`0x004afdb0`), which inserts the node **before the
first node with a strictly later time**: events due at the same time are delivered in the order
they were queued (FIFO). If the delta is invalid (ms ≥ ms per day) the payload is freed and
nothing is queued. Event ids and payloads are listed in [objects.md](objects.md) section 5.

### 4.2 When events fire

Only `UpdateState` delivers events (2.2), and only while the module is running (server state 2) and
no transition is in progress. "Now" is the world time read at the start of `UpdateState`; since the
world clock normally moves only in step 2 of the server frame (`GetWorldTime` `0x004ade40`
returns the value of the last `Update`; `SetPauseState` also calls `Update` when a pause changes,
6.1, which may move it mid-frame so that a zero-delay event queued after that waits a frame — med),
**an event queued with zero delay anywhere during frame N is due in frame N**: queued before
`UpdateState` (by the client frame, by a player order in the message step) it is delivered at
`UpdateState`'s first delivery point; queued during
`UpdateState` it is delivered at the next delivery point (2.2); queued after it (server steps 7–9)
it waits for frame N+1. Events queued by an event handler are delivered in the same drain loop, so
chains of zero-delay signals complete within one delivery point, in queue order. An event with a
delay of d ms fires in the first frame whose world time is ≥ queue time + d. (high)

### 4.3 The routines

| Routine | Handler | Queued as | Conf. |
|---|---|---|---|
| 7 `DelayCommand(float s, action)` | `0x0052fe30` | event 1 (TIMED_EVENT) to `OBJECT_SELF`, caller = self, delay `(int)(s × 1000)` ms, 0 days. Dropped (situation freed) when `OBJECT_SELF` is invalid. **A delay of one game day or more (2880 s at MinPerHour 2), or a negative one, is silently dropped** because the delta is invalid | high |
| 6 `AssignCommand(object, action)` | `0x0052e720` | event 1 to the object, delay 0, caller = `OBJECT_SELF` (or invalid). Dropped (situation freed) when the object does not exist. The action runs with `OBJECT_SELF` = the target when the event is delivered, normally later in the same frame | high |
| 294 `ActionDoCommand(action)` | `0x0052c740` | not an event: action 0x25 on `OBJECT_SELF`'s queue (`AddDoCommandAction` `0x0057cb10`), run by `RunActions` in order | high |
| 131 `SignalEvent(object, event)` | `0x005439d0` | event 10 (SIGNAL_EVENT) with the `CScriptEvent` payload, delay 0, caller = `OBJECT_SELF` if it exists. Nothing is queued when the target does not exist (the event struct is not freed) | high |
| 8 `ExecuteScript(name, object, n)` | `0x00535b70` | not queued: runs nested, immediately (vm.md) | high |

Event 1 is run by every object type's `EventHandler` (and the area's and module's) as
`RunScriptSituation(situation, its own id)` ([vm.md](vm.md)). (high)

### 4.4 Delivery

The target id decides (high, `0x004b0b70`):

- an object (type ≥ 5): virtual slot 30 `EventHandler(id, caller, payload, day, time)`;
- the area (type 4): `CSWSArea::EventHandler` (`0x0050d6c0`): 1 (situation), 5 APPLY_EFFECT
  (only effect type 0x1e, placed at a location), 17 SPAWN_BODY_BAG (puts the body-bag
  placeable that `SpawnBodyBag` `0x004ce220` created 500 ms earlier into the area at the
  payload's position), 10 with script events 0 (OnHeartbeat, also resets its heartbeat timer),
  0xb (OnUserDefined), 0xc (OnEnter: the entering object is the event's caller, and while the
  script runs `GetLoadFromSaveGame` returns the int the event was queued with), 0xd (OnExit,
  "last exiting" = the caller), and 26 AREA_TRANSITION (5.2);
- the module (type 3): `CSWSModule::EventHandler` (`0x004c5120`): 1, and 10 with script events
  0 OnHeartbeat (`+0xb0`, resets the heartbeat timer), 0xb OnUserDefined (`+0xb8`), 0x11
  OnModLoad (`+0xc0`), 0x10 OnModStart (`+0xc8`), 0xe OnClientEnter (`+0xd0`), 0xf OnClientLeave
  (`+0xd8`), 0x12 OnActivateItem (`+0xe0`), 0x13 OnAcquireItem (`+0xe8`), 0x14 OnUnacquireItem
  (`+0xf0`), 10 OnPlayerDeath (`+0xf8`), 0x20 OnPlayerDying (`+0x100`), 0x21 OnSpawnButtonDown
  (`+0x108`), 0x23 OnPlayerRest (`+0x110`), 0x25 OnPlayerLevelUp (`+0x118`), 0x26 OnEquipItem
  (`+0x120`), and 0x24 DESTROYPLAYERCREATURE (deletes the caller if it is a creature). The 15 module script names
  are stored in this order from `+0xb0`, 8 bytes apart;
- an id that no longer exists (or names a type below 3): the payload is freed (`ClearEventData`
  `0x004b0ab0`). The encounter, waypoint and sound-object handlers (`0x00594220`, `0x005c7f10`,
  `0x005c8650`) ignore event 1, so a command assigned to or delayed on one of those objects never
  runs ([vm.md](vm.md), script situations).

### 4.5 Pause, transitions and saves

- **Pause**: the world clock is frozen, so delayed events wait; zero-delay events queued during the
  pause are still delivered, because `UpdateState` keeps running (6.2). A delay counts world time
  only: pausing for a minute does not make a `DelayCommand(5.0)` fire early. (high)
- **Loading**: the world clock is paused for the whole module load (`BeginLoadModule`, 5.3), so
  no queued time passes. (high) One exception read in the code: if a pause (player pause or time
  stop) is still on when `UnloadModule` switches both off, `SetPauseState` (`0x004b8110`) also
  unpauses the world timer, which then runs during the load (med, needs a runtime check; door and
  trigger transitions force the player pause off beforehand, 5.2).
- **Leaving a module**: `UnloadModule` (`0x004b9240`) empties the queue (`ClearEventQueue`
  `0x004b11c0`) — but just before, the module being left was written to `GAMEINPROGRESS:` with its
  queue, unless `modulesave.2da` `IncludeInSave` excludes it (`SaveModuleIFOStart` `0x004c7050` →
  `SaveEventQueue` `0x004b0970`, GFF list `EventQueue` of 0xABCD structs, fields `Day`, `Time`,
  `ObjectId`, `CallerId`, `EventId`, `EventData` with a payload struct per type: 0x7777 script
  situation, 0x4444 script event, 0x1111 effect, …). When that module is entered again from its
  saved state (`Mod_IsSaveGame`, which `SaveModuleIFO` sets), `LoadModuleStart` (`0x004c9050`)
  restores the queue in saved order (`LoadEventQueue` `0x004b0a00`, appended as read). The world
  time is not taken from that module's IFO on a transition: `LoadModuleStart` continues from the
  snapshot of 5.3 step 1 (only a normal save load, client `+0x33c`, takes the IFO's time). Times
  are absolute, so everything that came due while the party was elsewhere fires on the first
  frame back. (high)
- **Save games** keep the queue the same way (it is part of the module's `.sav`); the world time is
  restored too (7.6), so pending delays resume where they were. (high)

## 5. Area transitions and module loading

### 5.1 Who asks for a transition

All roads end in three server fields, the **transition request**: flag `+0x10080`
(`SetMoveToModulePending` `0x004aecc0`), module name `+0x10084` (`0x004aecd0`) and waypoint tag
`+0x1008c` (`0x004aed30`). (high)

| Source | How | Conf. |
|---|---|---|
| door click | script event 0x1e (CLICKED) on a door whose `LinkedToFlags` (`+0x384`) is 1 or 2 (`GetIsAreaTransition` `0x005890d0`) and whose `LinkedToModule` (`+0x390`) is set: the two-phase handshake below with module = `LinkedToModule`, waypoint = `LinkedTo` (`+0x388`). A door that is not a transition runs its OnClick instead. | high |
| trigger enter | script event 0xc (OBJECT_ENTER) on a transition trigger (`+0x2b4`) with a non-empty module (`+0x238`; waypoint `+0x230`): same handshake (`CSWSTrigger::EventHandler` `0x0058f140`). A transition trigger runs no OnEnter script | high |
| `StartNewModule(module, waypoint, movie1..6)` (routine 509, `0x00544390`) | sets the request directly (no party, conversation or token checks), queues the six movies on the client (`AddQueuedMovie` `0x005edb50`; empty when fewer than five arguments), and blacks the screen at once (a zero-length fade) while a conversation is running (in-game GUI `+0xb4`, or `+0xc04`) | high |
| area event 26 | `CSWSArea::EventHandler`: a reduced handshake on the area (5.2), payload = 8 strings (module, waypoint, 6 movies). No code queuing the first event 26 was found | med |
| cheats and menus | console warp `0x0060af50` and the debug module list (`CSWGuiDebugModules`, `0x006cf9d0`) set the pending flag and the module name only. Loading a transition autosave (`LoadTransitionAutoSave` `0x006ca250`) does not use the request: it restores the waypoint and calls `BeginLoadModule` itself (party-items-saves.md 1.7) | high |

### 5.2 The two-phase handshake (doors, triggers, area event 26)

Phase 1, on the click/enter event (high):

1. If the clicker/enterer is not a creature, or a conversation is running (in-game GUI `+0xb4`,
   set by the conversation code through `CGuiInGame::SetDialogPending` `0x0062ec60`), the area's
   pending flag is cleared and nothing else happens. The same test runs first on the phase-2 copy,
   so a conversation that starts within the 500 ms cancels the transition without undoing the
   fade (med). With no transition pending on the area, only a creature with the PC flag
   (`+0x9d4`) or the party leader (`CSWPartyTable::IsCreatureLeader`) goes on; anyone else is
   ignored.
2. **All party members must be within 30 m of the leader** (`AreMembersNearLeader` `0x00635350`,
   3D distance); otherwise run `k_trg_transfail` at once with the creature as `OBJECT_SELF` and
   stop.
3. Take a fresh token from the area (`NextTransitionToken` `0x00506ac0`: a byte counter at area
   `+0x2c8`, never 0), copy the event with the token (a door's copy: object 0 = the clicker,
   int 0 = token; a trigger's keeps its int 0 and puts the token in int 1), and queue it back to
   the same object as event 10, caller = that object, with a **500 ms** delay.
4. Start a 0.5 s fade to black, mark the area "transition pending" with the token
   (`SetTransitionPending` `0x00506b30`: `+0x2c4`, `+0x2c9`; it also disables client input), and
   **force the player pause off** (`SetPauseState(2, 0)`).

Phase 2, when an event arrives while a transition is pending: with the same token, if the
creature is alive (not dead, and not a party member at 0 HP or less, `GetIsDying` `0x004ef890`),
set the transition request and clear the pending flag (input back on); otherwise remove the fade
panel (`0x0062ac40`: the picture comes back at once, no fade-in) and clear. A different token is
ignored. The PC/leader and distance tests are not repeated. (high)

Area event 26 (`0x0050d6c0`) is a reduced form: phase 1 has no creature, conversation, leader or
distance test and leaves the pause alone; the copy (token in int 0, the 8 strings) is queued as
event 26 to the area after 500 ms, with the same 0.5 s fade and input lock. Phase 2 (matching
token) sets the request from strings 0 and 1, queues strings 2–7 as movies (`AddQueuedMovie`)
and clears the pending state, with no alive test. (high)

### 5.3 Leaving: `StartModuleTransition` (`0x004ba920`)

Server step 8 sees the request (only while the transition block is idle and the in-game GUI flag
`+0xdc` is clear), and (high unless marked):

1. Stores the current world time and calendar (year, month, day, hour, minute, second, ms;
   `StoreGameTime` `0x004b22d0`, `+0x1009c`..`+0x100a8`) and the (day, ms) pair as the "pause
   snapshot" (`+0x100b0` day, `+0x100ac` time) to hand to the next module, and writes the NPC
   slots out (`SaveAllNPCStates(0)` `0x00565530`, party-items-saves.md 1.8).
2. `StartModuleTransition(name)`, unless one is already in progress (`+0x100b4`):
   1. client: pick and set the load-screen hint for the target (`PickLoadScreenHint`
      `0x005f4760` through `0x005ee090`, `SetLoadScreenHint` through `0x005edf00`; gui.md), clear
      two client flags (`+0x488`, `+0x228`; med), clear the conversation-pending flag
      (`SetDialogPending(0)`), an in-game GUI reset (`0x006332b0`, med), a sound call
      (`0x005d5e70`, med), **play the queued movies** (`PlayQueuedMovies` `0x005edb20` →
      `0x00602650`);
   2. the target must exist as `MODULES:<name>.mod` or `.rim`, else nothing more happens;
   3. set "in progress" `+0x100b4` and "this is a transition" `+0x1007c`;
   4. **area OnExit for each player**, run at once rather than queued (`RunAreaExitScripts`
      `0x004b4f50`: sets the area's "last exiting" `+0x1d8` to the player creature and runs the
      area's OnExit `+0x17c` with the area as `OBJECT_SELF`);
   5. **save the player characters** (`SavePlayerCharacters` `0x004b2ba0`): `ClearAllActions(1)`
      on each player creature, write them in a `Mod_PlayerList` IFO to `TEMP:pifo`, then
      `SaveAllNPCStates(1)` and `SaveInventory(1)` (party-items-saves.md 1.8). It returns false
      when no player creature was written; the transition then stops here with `+0x1007c`
      cleared but `+0x100b4` left set, which blocks later transitions (static reading, needs a
      runtime check);
   6. **save the module being left** to `GAMEINPROGRESS:<module>` (`0x004b2e70`:
      `SaveModuleIFO`, `SaveAreaGIT`, `FinishModuleSave`, only if `modulesave.2da IncludeInSave`
      allows it);
   7. `modulesave.2da` for the target: `DeleteSaveGroupOnEnter` deletes the `GAMEINPROGRESS:` saves
      of every module of that save group (`DeleteModuleSaveGroup` `0x004b2380`) — this is how
      Taris, Leviathan etc. are forgotten after leaving them;
   8. **autosave**, if a module is loaded, when `ShouldAutoSaveOnEnter` (`0x004b5050`) says so
      (5.7), or always when `modulesave.2da` cannot be loaded: `WriteTransitionAutoSave`
      (`0x004b8300`, a save that loads into the *target* module; its `AUTOSAVEPARAMS` carry the
      start waypoint, movies and time; party-items-saves.md 1.4);
   9. `BeginLoadModule` (`0x004ba820`): reset input, **pause the client and server world
      timers**, then `LoadModule(name)` ([modules.md](modules.md)).
3. Clears the request flag, whatever the call did.

`LoadModule` (`0x004b95b0`) sets `+0x100b4`, then, when a module is loaded, unloads it
(`UnloadModule` `0x004b9240`): both pause types off, exempt lists emptied, player creatures
removed from their area and destroyed (each player's "in module" flag `+0x24` cleared), the
client party emptied, the party table's inventory list and the custom tokens cleared, the module
and with it the area and every object deleted, the object array and the event queue emptied,
`CURRENTGAME:` removed. Then it looks for the module, in `GAMEINPROGRESS:` first when
`IncludeInSave` allows it (resource type 0xbc1, then 0x809 `.sav`), else `NWMFILES:` (0x80e) and
`MODULES:` (`.mod`, `.rim`), fills the transition block and sets load mode 3 when the file comes
from `GAMEINPROGRESS:` — a save load *and* a module re-entered after a transition — and 1
otherwise; busy = 1, "skip one client frame" = 1, counters and error 0. (high)

### 5.4 Loading: the transition block and the ticks

The block at `g_pAppManager+0x14` (`CModuleTransition`, 0x3c bytes): `+0` busy, `+4` mode (1 load,
2 save, 3 load from `GAMEINPROGRESS:`), `+8` areas loaded, `+0xc` area count, `+0x10` "skip one client frame",
`+0x14` done, `+0x18` module name, `+0x20` source path, `+0x28` target path, `+0x30` resource type,
`+0x38` error code. (high)

While busy, the server frame does one step per frame (high):

| Tick | Condition | Work |
|---|---|---|
| 1 | count = 0 | `CopyModuleFile`, `new CSWSModule`, `LoadModuleStart` (IFO, time, factions; sets the count to the length of `Mod_Area_list`, 1 in every shipped module) |
| 2 | loaded ≠ count | `ClearNPCObjectIds` (`0x005639c0`), then `LoadModuleInProgress(loaded)`: the area (ARE, LYT, GIT objects, PTH); loaded = 1; progress message to the client |
| 3 | loaded = count | `LoadModuleFinish`: queue **SIGNAL_EVENT MODULE_LOAD (script event 17) to the module**; done = 1; server state = 1 ("module loaded"); `+0x100b4` = 0; tell the client (load result, "ModuleLoaded" status) |

Any failure calls `FailModuleLoad` (`0x004ba5b0`): unload, error code in the block, done = 1,
state 0, `+0x100b4` = 0, tell the client; the client's `UpdateModuleTransition` (`0x00602c90`)
then returns to the main menu (`AbortToMainMenu` `0x005fcbd0`, when its flag `+0x264` was set by
that message; med).

Meanwhile the client frame stops at its step 3 every frame, drawing a loading frame (load screen
from `loadscreens.2da`, progress bar). When the area message arrives it builds the client area
synchronously inside its message handling, drawing more loading frames ([modules.md](modules.md),
step 8). The next client frame after "done" clears the busy flag (`UpdateModuleTransition`). (med)

### 5.5 Arrival: the order of events

After tick 3 the client and server finish with NWN's login handshake, over the message rings
(client → server messages are handled in the same frame, server → client ones in the next client
frame, so each round trip costs about one frame). The steps are read in the code; the stitching
of the round trips is med:

| # | Who | Message / call | What happens |
|---|---|---|---|
| 1 | server tick 2 | — | **GIT objects are created** in the GIT list order of [modules.md](modules.md) (creatures, items, doors, triggers, encounters, waypoints, sounds, placeables, stores, AoEs) and join the AI master on level 0 (no player in the area yet). Each creature is added with `AddToArea(…, fromSave)` (`0x004fa100`): on a fresh module this **queues the area's OnEnter (script event 0xc) for every GIT creature**, in GIT order; from a saved module state it does not. Nothing runs yet. |
| 2 | server tick 3 | `LoadModuleFinish` | **OnModLoad** queued (script event 17 to the module); server state 1; "ModuleLoaded" status to the client |
| 3 | client | `'S'` status → `HandleServerStatusMessage` (`0x00675710`) | replies with the admin text `Module.Run` (`SendAdminCommand` `0x00675690`, format `%s.%s`) |
| 4 | server | `Module.Run` → `StartModuleRunning` (`0x004b6270`, only from state 1) | state 2: **the AI master starts**. Players already in the module are placed (none after a transition: `UnloadModule` cleared their flag). For a module whose IFO says `Mod_IsSaveGame` (`+0x1c8`) when this is not a transition, the first player is restored from it and **OnClientEnter** queued (`RestorePlayerFromSave` `0x004b5f50` → `SignalPlayerEnterModule` `0x004b5c50`) and the party restored (`RestoreParty`, party-items-saves.md 1.6). Only for a transition (`+0x1007c`, then cleared) does it send "module running" (3/0xc). |
| 5 | server, same frame | `UpdateState` | delivers the queued events in order: the creatures' area OnEnter (or the restored queue), then **OnModLoad**; then the AIUpdates begin: every GIT creature's **OnSpawn** fires on its first `AIUpdate` (level 0, leftover budget, possibly over several frames) |
| 6 | client | 3/0xc → `0x00652860` | replies Login 2/0xf (`0x00678030`) |
| 7 | server | Login 0xf → `PlayerLoginToModule` (`0x004b7470`) | after a transition: the PC is re-created from `TEMP:pifo` (`LoadCharacter(-1, …)` `0x00561e30`) and the party restored (`RestoreParty` `0x00565760`), which re-spawns the members straight into the area (`AddToArea(…, fromSave = 1)`, so **no area OnEnter for them**); `SignalPlayerEnterModule` queues **OnClientEnter** (script event 0xe; also OnPlayerDeath, script event 10, when the PC is dead or down at 0 HP or less, `GetIsDying`) and, the first time the player enters the module (flag `+0x24`), sends the module info (3/1). The PC is not in the area yet. |
| 8 | client | 3/1 | builds the client module and camera (`0x0063f660`), replies 3/2 |
| 9 | server | Module 3/2 → `PrepareAreaForPlayer` (`0x004b3a90`) | gives a new player the IFO's `Mod_Entry_*` start, keeps a known player's stored position; sends the area (major 4 / minor 1, which the client routes to `HandleServerToPlayerAreaLoad`, through `0x0056cd20`; then 0x32/2 through `0x0056d2d0`) |
| 10 | client | area message (`HandleServerToPlayerAreaLoad` `0x0064bab0`, `0x0064dcf0`) | loads the client area synchronously, drawing loading frames; replies Area 4/3 (`0x006778f0`) |
| 11 | server | Area 4/3 (`0x00524b80`) → `PlacePlayerInModule` (`0x004b3d10`) | if a waypoint tag is pending, the start position and facing become the waypoint's (tag lookup `0x004c6e00`) and the tag is cleared; snap to a free walkmesh spot within 20 m (`0x004be860`); `AddToArea(…, fromSave = 0)` (`0x004fa100`) → `AddObjectToArea` (`0x0050dfd0`), which **queues the area's OnEnter (script event 0xc) for the PC** (caller = the PC, int 0 = `GetLoadFromSaveGame`) and, as the first creature with a client twin, raises the area's objects to AI level 1 (`IncrementPlayersInArea` `0x00508c20`); a perception pass; the party is placed (`PlacePartyAroundLeader` `0x00565b00`, positions only); only while the server is in state 2. The handler then re-sends each pause type that is on |
| 12 | client | step 1 of its frame | while the loading flag (client `+0x288`) is set and the PC's client creature exists: a pending leader switch (client `+0x338`, `0x005fb6e0`) is handled first and ends the step for that frame; otherwise input class and HUD are restored, and then, only while the application is active (`0x007a3a38`, app.md; else the step repeats next frame): **the load screen (client `+0x278`) goes away** (`0x005f6e20`, which also clears an input-block bit so that input returns 0.5 s later through the `+0x3dc` delay, autosave or not), all clocks unpause (world time resumes from the stored snapshot, 7.2), and unless an autosave is pending the fade-in starts: a 1 s fade-in after 0.5 s, or, while a conversation is pending (in-game GUI `+0xb4`) or `+0xb98` is set, only `+0xb98` = 1 (the conversation's end fades in, `SetDialogPending(0)`); `+0x288` is then cleared |

So the script order on arrival is (med for the overall order; high for each step):

1. on a fresh module, the area's **OnEnter once per GIT creature** (entering object = that
   creature); on a module re-entered from `GAMEINPROGRESS:` instead the **restored event queue**
   (4.5), and no creature OnEnter;
2. **OnModLoad** — on every entry, fresh or re-entered;
3. each creature's **OnSpawn** on its first `AIUpdate` (followed at once by a heartbeat only for
   encounter-spawned or player-controlled creatures, 2.4); creatures restored from a saved state
   keep their "spawn fired" flag (`CreatnScrptFird`, `+0x34c`) and don't spawn again;
4. **OnClientEnter** for the PC;
5. the area's **OnEnter for the PC** only: the party members re-spawned by `RestoreParty` in
   step 7 are added as "from save" and get no OnEnter (static reading);
6. the load screen goes away and control returns to the player.

All of it happens with the world clock still paused, so every event carries the same time and
the queue order is the insertion order. A conversation or cutscene started by any of these
scripts takes over as soon as the load screen is gone. An area OnEnter script that should react
only to the PC has to test `GetEnteringObject()`.

`Mod_OnModStart` (script event 16) is never queued by the engine: no code creates that event (high,
searched; KOTOR's IFOs leave it empty). `Mod_StartMovie` is read into `+0x7c` by
`LoadModuleStart` only: `SaveModuleIFOStart` does not write it back and no reader was found (med).
The probe of the 117 shipped module IFOs found `Mod_OnModLoad` set in 13 modules and
`Mod_OnClientEntr` in 7 (`Mod_OnModStart` in none): KOTOR mostly uses the area's OnEnter.

### 5.6 The load screen

Two code paths pick a `loadscreens.2da BMPResRef` picture (high for the paths, med for what is
on screen when):

- **Per module**: `SetLoadScreenImage` (`0x005f3480`, gui.md) takes the row labelled with the
  module's name, else a `load_<module>` texture, else the `DEFAULT` row. Its only caller
  (`0x005edcf0`) runs when the client module is built (`CSWCModule::LoadFromMessage`
  `0x0063f660`, arrival step 8) and in the save, autosave and load paths; on a transition without
  an autosave nothing sets it before the load ticks, so they would show the previous picture
  (static reading, needs a runtime check).
- **Per area**: the area message (built by `0x0056cd20`, arrival step 9) carries a row number:
  the area's `LoadScreenID` (stored on the player through `0x00560cd0`), or, when that is 0 or
  out of range, a random row from 2 up; the client also draws a random row from 2 up when it
  receives 0, and reads that row's `BMPResRef` while it loads the area
  (`HandleServerToPlayerAreaLoad` `0x0064bab0`).

The hint comes from `loadscreenhints.2da` (`PickLoadScreenHint`, gui.md). The progress bar is
advanced by the resource loader and the room loading. `RenderLoadingFrame` (`0x00401c10`) draws
GUI-only frames with a fixed 1/30 s delta and pumps window messages ([app.md](app.md)). (med)

### 5.7 Autosaves

Two independent mechanisms (high):

- **On a transition** (`ShouldAutoSaveOnEnter` `0x004b5050`, column `AutoSaveOnEnter` of
  `modulesave.2da` for the *target*, by row label): `force` → save; `no` → don't; `yes` → save
  only if the 15-minute real-time timer is due *and* the `AutoSave` game option (client options
  `+8` bit 2) is on; any other value → save when the timer is due; no row → save; no
  `modulesave.2da` at all → save (5.3). Every "save" answer resets the timer. The timer
  (`UpdateAutoSaveTimer` `0x004b1ee0`, every server frame) adds `GetTickCount` milliseconds to
  `+0x1b930` and sets "due" `+0x1b938` past 900,000 ms, then stops counting until reset. Shipped
  rows: 28 force, 60 yes, 35 no.
- **From a script**: `DoSinglePlayerAutoSave` (routine 512, `0x00530660`) sets `+0x100b8`; server
  step 9, once the transition block is idle, the PC is in an area and the client is not loading,
  starts an `AUTOSAVE` save in slot 1 (`RequestSaveGame` `0x004b58a0`, run by the save state
  machine `DoSaveGame` `0x004b3110`, mode 2 of the transition block) when there is disk space and
  the server is running (state 2), else only does the fade-in itself (or leaves it to a pending
  conversation, `+0xb98`); the flag is cleared either
  way. The fade-in normally done on arrival (5.5 step 12, skipped while the flag is set) is done
  after the save (party-items-saves.md 1.3).

## 6. Pause

### 6.1 Pause types

`CServerExoAppInternal +0x10078` holds two bits (high):

| Bit | Type | Meaning | Exempt list | Exempt clock |
|---|---|---|---|---|
| 1 | 1 | **time stop** (effect type 0x40) | `+0x10074`: the caster | `+0x1004c` |
| 2 | 2 | **player pause** | `+0x10070`: nobody in practice | `+0x10050` |

`SetPauseState(type, on)` (`0x004b8110`) does nothing when the bit already has that state. Turning
a type on sets the bit and pauses the world clock (and the time-stop clock too when the player
pause is on). Turning type 2 off copies the time-stop clock into the pause clock and unpauses the
world clock unless a time stop still holds it; turning type 1 off copies the world clock into both
exempt clocks and unpauses all three, without looking at bit 2 (so a time stop that ends during a
player pause starts the world clock again; med, an edge case). Before the copy, every object in
that type's exempt list gets slot 2 (`ResetExemptObjectUpdateTimes` `0x004b8020`) with its clock's
time: empty (`0x005b5e90`) except on the server creature, whose `0x004eb6b0` resets its last
heartbeat and perception times (`+0x350`, `+0x388`, `+0xa8`; objects.md 3). After a change the
client is notified directly (`NotifyClientPauseState` `0x0056c9f0`, with the exempt list) and
mirrors the same logic on its clocks (`CClientExoAppInternal::SetPauseState` `0x005f7fa0`, bits at
client `+0x1cc`). `TogglePauseState` `0x004ba610`, `GetPauseState(type)` `0x004b1d80`,
`GetPauseType` `0x004b1da0` (2 if player-paused, else 1 if time-stopped, else 0). The only caller of
`AddPauseExemptObject` (`0x004b4730`) is the time stop with type 1, so the player-pause list stays
empty. (high)

### 6.2 What stops and what keeps running

| Keeps running | Stops (world time frozen) |
|---|---|
| both `MainLoop`s, messages, input, `ProcessInput` and the GUI (its render on the interface clock; `CSWGuiManager::Update` gets the world delta, 0 while paused) | world time, game calendar, every heartbeat, perception timers, effect durations, delayed events |
| the camera (interface clock) | combat rounds (`UpdateCombat` and the attack action check the player pause explicitly) |
| `UpdateState`: zero-delay events (SignalEvent, AssignCommand, script-signalled events) are delivered; every object gets its `AIUpdate` | creature `dt` = 0: movement, regeneration and countdowns don't advance |
| `RunActions`: actions that need no time (DoCommand, Speak, ClearAllActions, equipping…) complete; time-based ones wait | client object animation, particles, texture animation (world delta 0) |
| the party-death / revival timer (real time) | sound mode 2 ("paused"), set with a pause request (6.3) |

So in KOTOR's "pause and queue orders" style, orders given while paused become actions on the queue
and start executing at once, but make no progress until the clock moves. (high for each item from
the code; the overall behaviour med)

### 6.3 Requests

Most changes of the player pause go through the client, which applies requests at the end of its
frame (step 28); a few paths set the server's state directly (marked below). (high)

- `RequestPause(bPause, reason, bForce)` (`0x005f2e10`, forwarder `0x005edc20`): taken when the
  in-game GUI's `+0xb4` is 0, when it is 1 (a conversation pending, dialogue.md) and the request is
  an unpause, or when forced. It is recorded only when no request is waiting and the server's
  player pause differs from bPause: bit 2 of `+0x37c`, desired state `+0x380`, reason `+0x388`,
  sound mode 2 or 0, game input blocked or unblocked.
- Step 28: unless the client's area is in a server area whose transition is pending (`+0x2c4`,
  `SetTransitionPending` `0x00506b30`; the request is then dropped): if the server's player pause
  differs from the request, `TogglePlayerPause` (`0x00677800` → server `TogglePauseState(2)`), then
  the HUD's pause banner (`0x0062def0`) with the resulting state and the reason.
- Sources: the pause key and the HUD `TB_PAUSE` button (`OnPauseToggle` `0x00688590`) and the
  banner's `BTN_UNPAUSE` (`CSWGuiPause::OnUnpause` `0x006c0350`), all toggling with reason 4;
  `PauseGame(b)` (routine 57, `0x00546590`, reason 0); the galaxy map, containers, stores, the
  status summary, tutorial boxes and party selection (`ShowGalaxyMap` `0x0062d040`, `OpenStore`
  `0x0062e310`, …; reasons 0, 2, 3 or 6, which show no banner, 6.4). Direct: opening the in-game menus (`ShowInGameMenu`
  `0x0062c9b0` runs `k_sup_guiopen` and calls `TogglePlayerPause` when its pause flag `+0xb38` is
  clear; gui.md); window deactivation (`OnAppDeactivate` `0x00401d90` sets the server's player
  pause and remembers whether it was already on; `OnAppActivate` `0x00401e00` restores it); the
  server Input messages 0x18 (toggle, only with a controlled creature whose `+0x9dc` is clear, in an
  area, and when a flag of the server options block allows it, `+0xc4` of internal `+0x10004`) and
  0x19 (set, skipped while that creature's `+0x9dc` is set).
- Transitions force the pause off (5.2, door and trigger event handlers); `UnloadModule` clears both
  types.

### 6.4 Auto-pause

`[Autopause Options]` in `swkotor.ini` sets bits of the client options word `+0x14` (read by
`0x0061dbe0`; the ini keys are `End Of Combat Round` 0x800, `Enemy Sighted` 0x1000, `Mine Sighted`
0x2000, `Party Killed` 0x4000, `Action Menu` 0x8000, `New Target Selected` 0x10000, which is the
order of the check boxes of `optautopause`: `CB_ENDROUND`, `CB_ENEMYSIGHTED`, `CB_MINESIGHTED`,
`CB_PARTYKILLED`, `CB_ACTIONMENU`, `CB_TRIGGERS`; the install's `swkotor.ini` has 0, 1, 1, 1, 0, 1;
a key that is missing leaves its bit as it was). Every call site tests its own option bit, then
calls `RequestAutoPause(1, reason)`. The reason picks the banner text (`CGuiInGame::SetPauseState`
`0x0062def0` → `CSWGuiPause::SetReason` `0x006c00c0`, dialog.tlk). `CGuiInGame::SetPauseState` shows
the banner only for reasons 1, 4, 5, 7, 8, 9, 10 and 11; a pause with any other reason (0 from
`PauseGame` and most GUI paths, 2, 3, 6) shows none. (high)

| Reason | Trigger and its extra conditions | Banner (strref) |
|---|---|---|
| 1 | enemy sighted (below) | 48212 "ENEMY SIGHTED! Press the Pause key (`<Pause>` or Pause) to continue" |
| 4 | the pause key, the HUD button or the banner's own button (not automatic) | 1508 "PAUSED" (`SetReason`'s default, reached only by reason 4) |
| 5 | end of a combat round: `EndCombatRound` (`0x004d4620`) called with bRunScript set, for the round of the client party's leader only (asm `0x004d4af9`; combat.md 3.5 step 8), the game not paused, option 0x800, and the leader's client creature in combat mode (`+0x440` bit 0) | 42432 "End of Combat Round" |
| 7 | the arrow buttons of the target block and the self-action block (`0x006884b0`, `0x00688520`, `0x0068af70`, `0x0068afe0`), option 0x8000, no other condition (each also shows tutorial pop-up 5) | 42482 "Menu Used" |
| 8 | the target-cycling keys (events 0xcc / 0xcd in `HandleInputAction` `0x00621210`), only while the client is in combat mode (`+0x320`) and option 0x10000; clicking an object does not ask | 42481 "Target Changed" |
| 9 | a player-controlled creature dies (`OnApplyDeath` `0x004e0ac0`, `+0xa88`) while some member of the client party has a server creature that is not dying (HP of 1 or more, `GetIsDying`), option 0x4000 (combat.md 8.2); `RequestAutoPause` itself gives reason 9 a 2 s cooldown (`+0x39c`, on the frame delta) | 42397 "Party Member Down" |
| 10 | not requested: while auto-paused, picking an action from the target or self block (`0x00689610`, `0x0068ad60`) for a creature whose `+0x440` bit 0 is set re-shows the banner with this reason; the game stays paused | 48423 "Action added to queue." |
| 11 | mine sighted (below) | 49118 "MINE SIGHTED! Press the Pause button to continue" |

Banner layout: for reasons 1 and 11 `LBL_PRESS` ("PRESS THE PAUSE BUTTON TO CONTINUE", 48384) is
hidden, since the text carries its own instruction; otherwise it hangs below the reason label; the
reason label is as tall as its wrapped text and the panel as tall as both. `<Pause>` is the key
bound to the Pause action (keymap.2da has two rows named Pause: the Pause key and Space).

`RequestAutoPause(bOn, reason)` (`0x005f3f10`, forwarder `0x005edee0`), for bOn = 1, in this order:
nothing if the automatic flag (`+0x384` bit 0) is already set or the server's player pause is on.
If the door window `+0x38c` is positive, the request is not made: the window is cleared and the
reason kept in `+0x398` with a 1 s countdown `+0x390`. Otherwise nothing if the in-game GUI's
`+0xb4` is not 0 (a conversation); reason 9 is dropped while its 2 s cooldown `+0x39c` runs, else it
starts the cooldown. Then the flag is set and, if no request is waiting, a player-pause request is
recorded (reason, sound mode 2, input blocked), applied at the end of the frame (6.3).

Client step 27 (asm `0x00603e80`..`0x00603f19`): while `+0x390` is positive it counts down on the
frame delta, and when it reaches 0 it calls `RequestAutoPause(1, +0x398)` and sets `+0x398` to 0xff,
but only if the client is not in combat mode (`+0x320`). In combat mode the deferred request is
dropped and `+0x398` keeps the reason, which blocks the enemy and mine sightings below (they need
`+0x398` = 0xff) until the module is unloaded (med: static reading, needs a runtime check). While
`+0x390` is not running, the door window `+0x38c` counts down on the frame delta; `+0x39c` always
does. The window `+0x38c` is not "after an unpause": its only writer (`0x005f4100`, forwarder
`0x005edf30`) sets it to 5 s, and only when no deferred request is counting, at the end of the
player's default action on a door: open (`CSWCDoor::DefaultActionOpen` `0x00683d90`, for a door in
state 0x2726), unlock (`0x00683e50`) and bash (`CSWCDoor::DefaultActionBash` `0x00683e90`, when its
tutorial pop-up is not shown). So a request that comes within 5 s of such an order waits a second.

bOn = 0 clears the flag and, when the player pause is still on, the in-game GUI's `+0xb4` is 0 or 1
and no request is waiting, requests an unpause (reason 0). The pause key (`RequestPause(toggle, 4)`,
then this when the pause was automatic), the HUD pause button (`OnPauseToggle` `0x00688590`) and the
banner's button (`CSWGuiPause::OnUnpause` `0x006c0350`) call it. Unloading the client's module
(`0x005f8290`: on the server's module message `0x006684f0`, on loading a save and on
`AbortToMainMenu`) first requests an unpause and clears both client pause bits, then resets the
flag, `+0x38c`, `+0x390`, `+0x394`, `+0x3a0`, `+0x398` (to 0xff = none), the sighting flags and
`+0x320`. (high unless marked)

Sighting: `UpdateSelectableObjects` (`0x005fa5a0`, then `0x005f3ad0`) runs once a client frame
with the frame delta (0 while paused), when the module state (`+0x9c`) is 0 or 4, no load is in
progress (`+0x288`), the fade layer is not busy and `0x0062ded0` is false. It rebuilds the leader's
list of selectable objects within 30 m (`GetNearbySelectableObjects`) and, for the hostile ones that
are creatures, asks
`GetIsTargetVisible` (a render ray query from the leader's head to the object, cached per entry
for the frame). `+0x324` says an enemy was in view lately: it is set on any frame with a visible
hostile creature (also while paused) and cleared only after 10 s (`+0x394`, frame delta) without
one. The first visible hostile creature on a frame where `+0x324` is clear, the server not
player-paused and no request waiting (`+0x398` = 0xff) shows the tutorial pop-up 0x15, and if the
option is on and the client is not in combat mode (`+0x320`) calls reason 1; it also stores the
creature as the object to focus (`+0x2b4`). Mines are the same with `+0x328` / `+0x3a0`, for a
hostile object whose trap trigger flag (`+0x108`) is set, reason 11, option 0x2000, but with no
tutorial pop-up. (high for the
flow, med for the roles of the hostile test (vtable `+0x138`) and the trap flag)

### 6.5 Time stop

Effect type 0x40 (`OnApplyTimeStop` `0x004dcb40`, `OnRemoveTimeStop` `0x004dcc90`): applying it
with no pause adds its target to the time-stop exempt list and toggles pause type 1 on, keeping the
effect. Applying another while a time stop runs (and no player pause) sets the expiry of the
time-stop effect the target already carries to the target's clock now plus the new duration, and
discards the new effect; a target without one keeps the new effect but is not made exempt. During a
player pause the effect is just kept. Removing an effect toggles type 1 (off, in the normal case)
and removes the target from the list. The module frame (`CSWSModule::AIUpdate` `0x004c6c90`, while
the pause type is 1) calls `CheckTimeStopExpired` (`0x004c6480`), which toggles type 1 off when no
exempt creature still carries the effect. The exempt creature reads the `+0x1004c` clock through
`GetActiveTimer`, so it alone keeps acting. No shipped script calls `EffectTimeStop` (routine 467 is
absent from the routine table of `extract/ncs-stats.txt`, 13139 NCS copies), so no KOTOR power uses
it. (high)

### 6.6 Slow motion and the party wipe

The whole party down is the one place the game ends without a script. The server notices it
(`UpdatePartyDeath` `0x004b6da0`, 1.3: the client party list is not empty and every member in it
has a server creature that is dying; the whole step is skipped while slow motion runs or the client
is loading) and calls `CClientExoApp::StartDeathCamera` (`0x005edc40`, which forwards to
`CClientExoAppInternal::StartDeathCamera` `0x005f7200`). That sets the slow-motion flag at once, so
the call is made once: from the next server frame the party-death step is skipped while the flag is
up, and nobody gets back up during the sequence. (high)

**`StartDeathCamera`**, in order (high unless marked):

1. Sets `+0x2c0` (slow motion on) and `+0x2c4` (the speed curve is to be fitted afresh).
2. Deactivates every panel in the GUI manager's list (`0x0040c120`, `SetActive(0)` each): the HUD, a
   menu and the pause banner all stop being shown and picked.
3. Opens the in-game GUI's message box (`CGuiInGame+0x98`, set up by `0x00627260`): one button
   (mode byte 2), modal, text dialog.tlk 42351, "Your entire party has been killed." with
   "Return to Main Menu." on a second line. Its OK callback (`0x00625a60`) calls `0x005ede10(client,
   1, 0, 1)`, which sets the wipe flag `+0x1a8` = 1, the countdown `+0x374` = 0.0 and `+0x1ac` = 1.
4. Puts a `CSWCDeathCamera` (`0x0063bbd0`, 0x40 bytes) on the scene's camera, watching the object
   at client `+0x2d4`: the last player-controlled creature to die, noted by `OnApplyDeath`
   (combat.md 8.2). Only when that object is a creature (type byte 5) and the client area and its
   scene exist; otherwise no death camera. See below.
5. `StartGlobalFade(bFadeIn 0, wait 12.0, length 1.0, black)` (`0x0062abf0`): the fade layer waits
   12 s and then goes to black over 1 s. The argument order is the script routine's
   (`SetGlobalFadeOut(fWait, fLength, r, g, b)` pops its two floats into the same two slots,
   `0x005460d0`).

**`UpdateSlowMotion`** (`0x005f7330`, every client frame, step 9 of 1.2) times itself on the real
high-resolution clock (`+0x2c8` the last reading in ms, taken every frame; `+0x2cc` the seconds of
slow motion so far, t, zeroed only by the constructor, so a second wipe in one run starts with t
already past 4). While `+0x2c0` is set it calls `SetGameSpeed(speed)` with

    speed(t) = 0.2 + 0.8 * ln(t / 4) / ln(t0 / 4)     for t <= 4 s   (1.0 at the first frame, t0)
    speed(t) = 0.2                                     after that

where t0 is the first frame's step (the curve is fitted to it when `+0x2c4` is set, then the flag
clears).

**The curve has no effect.** `SetGameSpeed` only stores `(int)(speed × 100)` in each timer's `+0x8`
(`CWorldTimer::SetSpeedScale` `0x004ae190`); the only reader of that field is `CWorldTimer::Update`
(`0x004adbd0`), which scales the real-time step by it when the timer next advances, that is at the
top of the next client frame and in the server frame. Before either, the same client frame reaches
step 11, which calls `SetGameSpeed` again unconditionally (asm `0x006034b8`..`0x006034d8`) with 0.25
if client `+0x1b0` or `g_bDebugSlowMotion` (`0x0083291c`) is set, else 1.0. Client `+0x1b0` is
written only by the constructor (0; no other store to `[reg+0x1b0]` in the client's code), and
`0x0083291c` has no reference in the image but that test. Nothing advances a timer between the two
calls, so every timer always runs at 100 % and the party wipe plays at normal speed. (high from the
code; surprising, so a runtime check would be worth making)

The fade layer advances on the interface clock (`CSWGuiFade::Render` `0x00624570` adds that clock's
step to its elapsed time `+0x6c`, which `Start` sets to 0.1; the layer is "busy" while that is
non-zero and not past wait + length, `0x006244b0`, `GetIsFadePanelBusy` `0x0062ac60`), so it holds
for about 12.9 s of real time and is black for its last second.

The slow motion ends when the fade is no longer busy, or at once when the wipe flag `+0x1a8` is set
(the OK button), provided the countdown `+0x374` is not above zero: speed back to 1.0, `+0x2c0` off,
`+0x2c4` on, the fade layer reset and removed, `+0x1a8` = 1, `+0x374` = 0, `+0x1ac` = 1, and the
message box popped and removed. (high)

**The countdown** (step 10 of 1.2, `0x006033b8`..`0x00603489`). With `+0x1a8` set and the in-game
GUI's `+0xdc` clear: while `+0x374` is above zero it counts down by the frame delta (first showing the
message box, if `+0x1ac` is set and the box is not up). Once `+0x374` is at or below zero and the
slow-motion flag `+0x2c0` is clear, the client closes the in-game menu (`0x0062cba0`), unloads the
module on the server (`0x004ae8a0`, `UnloadModule`), destroys the server (`0x00401280`), shows the
main menu (`0x005fca30`), frees the in-game GUI's game state (`0x0062c310`), clears `+0x1a8` and
`+0x374`, sets `+0x1ac` = 1, and sets the sound and HUD modes back for the menu. So OK and the end
of the fade lead to the same place, the main menu with the game's state gone: no retry, no load
prompt. The `EndGame` script routine (564, `0x00535570`) fills the same three fields (`+0x1a8` = 1,
`+0x374` = 5.0 s, or 0 when its argument is 0, `+0x1ac` = the argument), so the end of the story
leaves through this block too (high). With a true argument it also sets `+0x2c0` and `+0x2c4`
(`0x005f2f00`), with no camera and no fade: the block's first frame then opens the message box,
whose setup (`0x00627260`) always loads strref 42351, the 5 s run down on the world delta, and the
slow-motion end then pops the box and the block goes to the main menu (med: static reading; what
the player sees there needs a runtime check).

**The death camera** (`CSWCDeathCamera`, a `CAurCameraController`; constructor `0x0063bbd0`,
`SetTarget` `0x0063a770`, `Update` `0x0063a810`). Fields (constants high, roles med): `+0x14` the
watched creature; `+0x18` the orbit heading in degrees, started as the heading from the camera's
position to it; `+0x1c` = 30 (degrees per second of the step `Update` is given); `+0x20` = 90; `+0x24` = 3.0 m;
easing rates `+0x28` = 0.5 (heading), `+0x2c` = 0.01 (pitch), `+0x30` = 0.5 (distance); `+0x34` = 0.75 m
easing to `+0x38` = 0 at `+0x3c` = 0.01. Each frame (the easings are per frame, not per second): the
orbit heading advances by 30 degrees times the step and wraps at 360; the camera's own heading moves
half the way to it; its pitch moves 1 % of the way to `90 - (+0x20)` = 0, which in the pitch
convention shared with the chase camera (90 is level; the style's 80 is ten degrees below level) is
*straight down*; the look-at point is the creature's position plus a height `+0x34` that drains 1 % a
frame to the feet; the camera stands at that point plus its backward axis times a distance that moves
half the way to 3 m. A ray from the look-at point to the camera is cast against the area and the
camera is kept 0.25 m off what it hits. So the picture swings in from the chase camera to 3 m over the
creature and settles into a slowly turning view from straight above the body. (med: the geometry is
read from a decompile that lost some stack slots)

Ours (`game/death.ctx`, called from `play::run`): the same sequence. The world keeps ticking with
`clock.speed` taken from the curve, which the game itself overrides every frame (above), so ours
runs the sequence slowed where the game does not; the HUD goes away, the box opens (`msgbox::show_strref`), the fade
is the dialogue layer's (an `outbox` fade note: wait 12, length 1, black), the camera is the orbit
above, placed after the chase camera's update. The box's OK (or Escape) and the end of the fade end the
loop, as the options menu's Exit Game does (a return to the front end is built for neither).

### 6.7 Solo mode

`GetSoloMode` (routine 462, `0x00546af0`) reads the party table (`+0x1b770 + 0x190`). In the loop it
only disables the straggler teleport (1.3); following and the party AI are movement.md's. (high)

## 7. Time of day

### 7.1 The calendar

12 months of 28 days, 24 hours per day (high, `CWorldTimer` conversions):

- day index = `year × 336 + (month − 1) × 28 + (day − 1)` (`ConvertDateToDayIndex` `0x004adca0`;
  a year above 32,000 becomes 1340, a month outside 1–12 becomes 6, a day outside 1–28 becomes 1),
  and back (`ConvertDayIndexToDate` `0x004add50`; a year above 32,767 becomes 1340);
- time of day (ms) = `hour × MinPerHour × 60,000 + minute × 60,000 + second × 1000 + ms`
  (`ConvertTimeToTimeOfDay` `0x004adcf0`; hour clamps to 23, minute to 59, second ≥ 60 gives 56 —
  a slip in the original). A game **minute is a real minute**: within an hour the minute runs
  0..MinPerHour−1 (`ConvertTimeOfDayToTime` `0x004add90`), seconds and ms are real.

### 7.2 Module time

`LoadModuleStart` (`0x004c9050`) reads `Mod_MinPerHour`, `Mod_DawnHour`, `Mod_DuskHour` (module
bytes `+0x1a0..+0x1a2`), then takes the calendar from one of two places, chosen by its `bResetTime`
argument (high):

- **`bResetTime` set**: the IFO's `Mod_StartYear` (default 1340), `Mod_StartMonth` (6),
  `Mod_StartDay` (1), `Mod_StartHour` (23), `Mod_StartMinute`, `Mod_StartSecond`,
  `Mod_StartMiliSec`, `Mod_Transition` (`+0x1b8`), `Mod_PauseDay`, `Mod_PauseTime` (all 0 when
  absent);
- **otherwise**: the calendar and the pause pair stored at the last transition (5.3 step 1) or by
  a transition-autosave load (`StoreGameTime`, server `+0x1009c..+0x100a8`; pause pair
  `+0x100ac`/`+0x100b0`).

The server's `MainLoop` passes `bResetTime` = client `+0x33c` (read through `0x005edfb0`). That flag
is 0 from the client constructor and is set to 1 only by `CSWGuiSaveLoad::LoadSelectedGame`
(`0x006cb0e0`, through `0x005edfc0`) on the normal-save path; the transition-autosave path and
`QuickLoad` (`0x00633c50`) do not set it, and nothing clears it. (high)

Then: `SetMinutesPerHour` (`0x004adba0`; 0 → 5), `SetCalendarTime` (`0x004ae3e0`, which sets the
timer's origin), the world timer's pause snapshot (`+0x28`/`+0x2c`) := (PauseDay, PauseTime), both
exempt clocks := copies of the world timer, module "last update" (`+0x1c0`/`+0x1c4`) := the world
time, and the initial day phase (7.4) from the hour field `+0x1b4`, not from the timer. (high)

Which of the two writes wins depends on whether the world timer is paused at this point
(`GetWorldTime` returns the snapshot while paused, and `UnpauseWorldTimer` rebuilds the origin from
the snapshot, discarding what `SetCalendarTime` set):

| Load | Timer | Effective time | Conf. |
|---|---|---|---|
| transition (`BeginLoadModule` `0x004ba820` pauses both world timers), flag 0 | paused | the stored pause pair, i.e. **the time continues exactly where it was** | high |
| normal save from the main menu (`LoadSelectedGame` pauses both timers), flag 1 | paused | the save's `Mod_PauseDay`/`Mod_PauseTime` (7.6) | high for the code |
| normal save from in game (no explicit pause on this path; `UnloadModule` clears any pause bit), flag 1 | running | the save's `Mod_Start*` calendar (7.6) | med, needs a runtime check |
| transition autosave (1.7 of party-items-saves.md) | paused | `TIME_PAUSEDAY`/`TIME_PAUSETIME` | high for the code |
| new game (`CSWGuiClassSelection::StartGame` `0x006dbdf0` → admin message → `LoadModule`; nothing pauses the fresh server's timer), flag 0 | running | the stored calendar, which the server constructor never initialises (it zeroes only the pause pair): whatever that memory holds — if zero, year 0, month 6, day 1, 00:00, an initial phase of night | med, needs a runtime check |
| any transition after a normal save was loaded in the session (flag stays 1) | paused | the destination IFO's pause pair: (0, 0) for a module not visited yet (shipped IFOs have none), so the clock jumps to day 0, 00:00; for a revisited module, the snapshot saved when it was left | med, needs a runtime check |
| `QuickLoad` in game, flag 0 | running unless a pause bit was set (`UnloadModule` clears them) | the calendar stored at the last transition, not the save's | med, needs a runtime check |

Shipped IFOs: start year 1372 (93 modules) or 0 (24), month 6, day 1, hour 13, no
minute/second/transition/pause fields; `Mod_MinPerHour` 2 in 113 of 117 modules (a 48-minute day),
0 or 1 in the four Dantooine modules `danm14aa`–`danm14ad`, which also have dawn = dusk = 0;
elsewhere dawn 6, dusk 18.

### 7.3 Script routines

| Routine | Handler | Behaviour | Conf. |
|---|---|---|---|
| 16 `GetTimeHour` / 17 minute / 18 second / 19 millisecond | `0x0053e020`, `0x0053e0a0`, `0x0053e0e0`, `0x0053e060` → `GetCurrentHour` `0x004ae090` etc. | from the world timer: hour = `ms / 60,000 / MinPerHour`, minute = `(ms / 60,000) mod MinPerHour`, second = `(ms / 1000) mod 60`, millisecond = `ms mod 1000` | high |
| 12 `SetTime(h, m, s, ms)` | `0x00543670` → `CWorldTimer::SetTime` `0x004ae260` | negative arguments are ignored; normalises (1000 ms, 60 s, 60 min carry upward; hours past 24 give whole days) and **only moves forward**: without a day carry, a time earlier than now (`CompareWorldTimes`) advances the date by one day. The date step wraps the day at 29 and the month at 13 instead of 28 and 12: from day 28 it lands on day 0 of the next month (read as day 1), from month 12 on month 0 of the next year (read as June, 7.1); a resulting year above 32,000 cancels the call. Minutes are not limited to MinPerHour, so a large minute spills into later game hours. The handler then calls `CSWSModule::UpdateTime` at once with a zero delta (7.4) | high |
| 405–408 `GetIsDay/Night/Dawn/Dusk` | `0x00539900`, `0x00539de0`, `0x005398c0`, `0x00539bd0` | the module's day phase `+0x1bc` = 1, 2, 3, 4 (FALSE without a module) | high |
| 121–123 `RoundsToSeconds` etc. | `0x00544e50` | section 3 | high |

### 7.4 Day phases and lighting

`CSWSModule::UpdateTime` (`0x004c6210`) runs from the module's `AIUpdate` on module frames (2.6;
not on the frame that runs the module heartbeat) with the world time and the ms since the last
update, and from `SetTime`. It computes the calendar and the hour and the phase (high):

- dawn hour = dusk hour → always day (1);
- hour = dawn → dawn (3); hour = dusk → dusk (4);
- dawn < dusk: night (2) when hour < dawn or hour > dusk, else day;
- dawn > dusk: night when dusk ≤ hour ≤ dawn, else day.

While the previous phase is dawn or dusk it adds the delta to `+0x1b8` (otherwise `+0x1b8` := 0),
stores year/month/day/hour at `+0x1a8..+0x1b4`, and when any of phase, hour, day, month or year
changed sends every player a time message (`SendServerToPlayerModule_SetTime` `0x0056a5f0`, 3/3:
a change mask, then the phase with `+0x1b8` for dawn/dusk, the hour, day, month, year). The client
(`0x006528b0`) stores hour/day/month/year at client module `+0xb0/+0xac/+0xa8/+0xa4` and, when the
phase changed, calls `CSWCModule::SetDayPhase` (`0x00640640`; also called by `CSWCArea::LoadArea`
`0x00607610`), which switches the area lighting: day → `ApplySunLighting` (`0x006058c0`), night →
`ApplyMoonLighting` (`0x006059c0`), dawn → moon lighting then `StartDawnTransition`
(`0x00606cf0`), dusk → sun lighting then `StartDuskTransition` (`0x00606c50`); the two `Apply`
functions set the sun or moon fog, ambient and diffuse colours from the ARE. With `DayNightCycle`
(area `+0xa0`) = 0 every one of these falls back to the set chosen by `IsNight` (`+0xa4`), so the area never changes; with
`DayNightCycle` = 1 the dawn/dusk transition lasts one game hour (client module `+0xbc` =
`MinPerHour × 60` s), starting `+0x1b8` ms in (`+0xb8`). Only two shipped areas (stunt modules)
set `DayNightCycle`. (high for the dispatch, med for the rendering)

### 7.5 What the shipped data does

Probe of every module RIM (`kotor/re/` scratch script): 117 IFOs, `Mod_MinPerHour` 2 (113) / 0 (3,
read as 5) / 1 (1); dawn 6 and dusk 18 except four 0/0; start hour 13. ARE `DayNightCycle` 1 in two
areas (`stunt_ebocom` in `STUNT_42` and `STUNT_44`), `IsNight` 0 everywhere. `Mod_OnHeartbeat` set
in two modules (`k_pebo_mgheart`, `k_ptat17af_heart`). In practice KOTOR has no visible day/night;
the clock still runs and scripts can read it. (high)

### 7.6 Saves

The module IFO saved in a game (`SaveModuleIFOStart` `0x004c7050`) holds `Mod_StartYear`,
`Mod_StartMonth`, `Mod_StartDay`, `Mod_StartHour` from the module's last `UpdateTime` calendar
(`+0x1a8..+0x1b4`), `Mod_StartMinute`/`Mod_StartSecond`/`Mod_StartMiliSec` from the current world
time, `Mod_Transition` (`+0x1b8`), and `Mod_PauseDay`/`Mod_PauseTime` copied raw from the world
timer's pause snapshot (`+0x28`/`+0x2c`), which is the current time only while the timer is paused
(otherwise the time of the last pause). (high) Only the transition autosave also writes an
`AUTOSAVEPARAMS` struct in `savenfo.res` (`CAutoSaveParams::Save` `0x004b28e0`, called only by
`WriteTransitionAutoSave` `0x004b8300`, party-items-saves.md 1.4): `TIME_YEAR`, `TIME_MONTH`,
`TIME_DAY`, `TIME_HOUR`, `TIME_MINUTE`, `TIME_SECOND`, `TIME_MILLISECOND`, `TIME_PAUSEDAY`,
`TIME_PAUSETIME` with `LOADMUSIC`, `STARTWAYPOINT` and `MOVIE1..6`; loading it stores them as the
transition calendar and pause pair (party-items-saves.md 1.7). How each kind of load sets the clock
is the table in 7.2. The file formats are party-items-saves.md's.

## Open questions

- **Who queues the first AREA_TRANSITION event (26)?** Only the area's own phase-2 re-queue
  (`CSWSArea::EventHandler` `0x0050d6c0`) passes event id 26 to `AddEventDeltaTime`; no other
  call site passes it as a constant. `0x006cf9d0` is not it: it is the debug-modules panel's warp button, which sets the
  server's move-to-module request.
- **The arrival handshake (5.5)** was stitched from the message handlers on both sides; the exact
  frame of each step (and so how many frames OnSpawn has before OnClientEnter) should be confirmed
  in a running game or by tracing the client handlers of 3/1, 10/1, 10/2 in full. The order of the
  scripts is what matters for a reimplementation, which needs no handshake.
- New game paths through `PlayerLoginToModule` (`0x004b7470`, Login minors 1, 2, 0xe, 0x11, 0x13)
  were only skimmed (the save-load paths are in party-items-saves.md 1.6–1.7).
- The object flag `+0x1f8` that gates both the movement pre-pass and the dirty-state push in
  `UpdateState` (cleared by the `CSWSObject` constructor; probably "active in an area", low).
- The client `+0x30` timer's purpose.
- Whether any rendering subsystem uses `CSWCModule::Render`'s interface-clock argument for effects
  that should keep animating during a pause (most read the global world delta).
- Large frame deltas: confirm per system (movement, animation, combat timers) whether a clamp
  exists downstream.
- The game clock after a quick load, a new game, and transitions after a normal-save load (7.2
  table): confirm in a running game.
