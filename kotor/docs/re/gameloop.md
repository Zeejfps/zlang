# The game loop in swkotor.exe: frame, clocks, object updates, events, transitions, pause, time of day

What one frame of the original engine does and in which order; the clocks (`CWorldTimer`) that
everything time-based reads; how the AI master spreads object updates over the frame; the event
queue behind `DelayCommand`, `AssignCommand` and `SignalEvent`; how a door, trigger or script
moves the party to another module and what happens on arrival; the pause rules; and the game
calendar. Addresses are for the Steam `swkotor.exe` after SteamStub removal (see
[README.md](README.md)). Every claim carries a confidence: **high** = read in the code, **med** =
role clear, detail inferred, **low** = plausible. Names are ours, in the Aurora/NWN vocabulary;
the proposals for every address below are in `kotor/re/proposals/gameloop.tsv` (git-ignored).

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

`WinMain` (`0x004041f0`, details in [app.md](app.md)) does, per iteration with no pending window
message: clear the framebuffer, **client `MainLoop`**, **server `MainLoop`** (when a server exists),
cheat console, `SwapBuffers`, then two optional throttles. (high)

| Throttle | What | Default |
|---|---|---|
| `Sleep(1)` when `0x007a3c58` is set | yields the CPU each frame | flag never written in the exe: off (high) |
| frame-rate cap `g_fFrameRateCap` (`0x007a3c64`) | busy-waits until `1000 / cap` ms passed since the frame began | written only by `LoadModuleFinish` from `0x00832904`, which nothing writes: off (high) |

So the original runs uncapped (vsync aside, `[Graphics Options] V-Sync`), and the frame delta is
whatever the last frame took. Neither loop clamps large deltas: no clamp was found in
`CWorldTimer::Update`, the client loop or `UpdateState` (med; individual systems may clamp, see
movement.md). A reimplementation should clamp the delta (say to 0.1–0.25 s); the original merely
never sees long frames outside loading, during which the clocks are paused (section 5.4).

Because the client runs first, an order issued by input in frame N reaches the server in the same
frame N (section 1.4), is acted on in frame N's `UpdateState`, and its visible result is drawn in
frame N+1. (high)

### 1.2 The client frame (`CClientExoAppInternal::MainLoop` `0x00602eb0`)

In order (high for the order, med for the roles of the smaller steps):

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Finish a load | client `+0x288` set and the player's client creature exists | When the client area is loaded: hide the load-screen panel (`+0x2a0`), restore the in-game GUI, leave movie mode, then **resynchronise and unpause every clock** (the four client timers and the server world timer), and unless an autosave is pending (`0x004aed20`) start the 1 s fade-in after 0.5 s (or, during a conversation, mark it for the conversation's end, `+0xb98`) and re-enable input. The loading flag `+0x288` is cleared at the end of this frame. See 5.5. |
| 2 | Advance the client clocks | `CWorldTimer::Update` | `+0x24` unless any pause bit is set, `+0x28` unless the player-pause bit is set, `+0x2c` always (section 1.6). |
| 3 | Module transition in progress? | transition block `g_pAppManager+0x14`, word 0 = 1 | read server messages; `UpdateModuleTransition` (`0x00602c90`); if still loading (mode 1 or 3): set `+0x288`, draw one `RenderLoadingFrame(1/30 s, no server tick, no 3D)`, and **return**: the rest of the frame is skipped. |
| 4 | Frame delta | `GetFrameDelta(+0x24) × 1e-6` → `g_fFrameDelta` (`0x0078e574`) | seconds; 0 while paused. |
| 5 | Resource manager tick | `CExoResMan::Update` (`0x00408d40`) | async loads |
| 6 | Party table update | `0x00637050(partyTable, dt)` | when an area is loaded (movement.md / party-items-saves.md) |
| 7 | `Render_BeginFrame` | `0x0044ed90` | finishes queued texture uploads |
| 8 | **Input** | `ProcessInput` (`0x006227e0`) | → `HandleInputAction` (`0x00621210`), GUI events; see 1.4 |
| 9 | Slow motion | `UpdateSlowMotion` (`0x005f7330`) | section 6.6 |
| 10 | Party-wipe countdown | `+0x1a8`, `+0x374` | when it runs out (and slow motion is over): unload the module, destroy the server, main menu (6.6) |
| 11 | Game speed | `SetGameSpeed` (`0x005f2f60`) | `1.0`, or `0.25` when the debug flag `0x0083291c` is set (never written: always 1.0) |
| 12 | **Server → client messages** | `CNetLayer::ProcessReceivedFrames` | object updates, time of day, module state (1.5) |
| 13 | Queued client script | `+0x32c` / `+0x330` | one script name run with no `OBJECT_SELF` |
| 14 | Bark bubbles | queue at `+0x168`, timer `+0x16c` | the player's speech bubble queue (dialogue.md) |
| 15 | Listener and camera | `0x005f5e10` (camera, uses the `+0x2c` clock) | skipped while a full-screen panel is up |
| 16 | **Client objects and 3D render** | `UpdateObjectsAndRender` (`0x006048c0`) | every client object's per-frame update (vtable slot 29, all objects, no budget), then `CSWCModule::Render` (render-gui.md) |
| 17 | Area sound environment | `0x005ee860` | EAX room at the listener |
| 18 | Selection highlight | GUI `+0x188` → server object | |
| 19 | In-game GUI per-frame | `0x006339c0`, `0x00632180` | |
| 20 | **Enemy / mine sighting** | `UpdateSelectableObjects` (`0x005fa5a0`), `0x005f3ad0` | only with no modal panel; auto-pause triggers (6.4) |
| 21 | Timed client-creature effects | `0x005f7640(real dt)` | |
| 22 | Tooltip / hover delay | `+0x370`, 0.25 s | |
| 23 | **GUI** | `CSWGuiManager::Update(world dt)`, then `Render(interface dt)` | the global delta is swapped to the `+0x2c` delta for the GUI pass and restored after |
| 24 | Fades and misc timers | `+0x3dc`, `0x005f7500`, `0x0062f780` | |
| 25 | Sound | `UpdateSoundListener` (`0x005f5370`) → `CExoSound::Update` | |
| 26 | Screenshot, clear `+0x288` if the load finished in step 1 | | |
| 27 | Deferred auto-pause | `+0x390` countdown → `RequestAutoPause` | 6.4 |
| 28 | **Apply a pending pause change** | `+0x37c` bit 2 | toggles the server's player pause if it differs from the request, updates the HUD pause label (6.3) |
| 29 | Flush `HD0:FILEERROR` | | |

### 1.3 The server frame (`CServerExoAppInternal::MainLoop` `0x004babb0`)

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Autosave interval | `UpdateAutoSaveTimer` (`0x004b1ee0`) | real milliseconds (`GetTickCount`) summed at `+0x1b930`; past 900,000 ms (15 min) sets "autosave due" `+0x1b938` (5.7) (high) |
| | *If no module transition is in progress:* | | |
| 2 | Advance the server clocks | `+0x10048` unless any pause bit, `+0x1004c` unless the player-pause bit, `+0x10050` always | (high) |
| 3 | **Client → server messages** | `ProcessReceivedFrames` → `CSWSMessage::HandlePlayerToServerMessage` (`0x00527b20`) | player orders become actions here (1.4) (high) |
| 4 | Party death and stragglers | `UpdatePartyDeath` (`0x004b6da0`) | skipped during slow motion or loading; see below (med) |
| 5 | Map exploration | `UpdateMapExploration` (`0x004b4e80`) | reveals the area map around each party member (med) |
| 6 | **AI master** | `CServerAIMaster::UpdateState` (`0x004b0b70`) | only when the server state `+0x10008` is 2 ("module running"); section 2 (high) |
| 7 | Client object updates | `UpdateClientsForPlayers(force)` (`0x004b6950`) | per player, every 200 ms or when forced (1.5) (high) |
| 8 | **Module transition request** | `+0x10080` set and the in-game GUI flag `+0xdc` clear | store the game time and calendar, then `StartModuleTransition(+0x10084)` (5.3) (high) |
| 9 | **Script autosave request** | `+0x100b8` (set by `DoSinglePlayerAutoSave`) | when the player is in an area and the client is not loading: start an `AUTOSAVE` save if there is disk space (≥ 0x641 × 16 KB) and the module is running, else just fade in (high) |
| 10 | Two NWN leftovers | `+0x100bc` (per-player cleanup `0x004b3000`), `+0x100c0` (`0x0056c7f0`) | (low) |
| | *If a transition is in progress:* | | |
| 2' | The load or save state machine | transition block mode 1/3 (load) or 2 (save) | section 5.4 (high) |
| | *Always:* | | |
| 11 | Shutdown countdown | `0x004b4ab0` | NWN's timed server shutdown (warnings at 60 and 30 s); unused in practice (low) |
| 12 | 10 s interval | `0x004b1e10` | result ignored (low) |

**Party death and stragglers** (`0x004b6da0`, med; the death rules themselves are combat.md's):
using real milliseconds, if *every* party member is dead the client's party-wipe sequence starts
(`StartDeathCamera` `0x005f7200`); if *some* are dead, once a second it looks for a hostile
creature in the area (reputation below 11) that perceives a party member; after 5 s in a row with
none, each dead member is moved to a free spot within 5 m and gets an effect of type 4 (revival),
and each member farther than 40 m from the leader is teleported next to its party-table position
unless solo mode is on. This timer uses the real clock, so it also runs during a pause. (med)

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
     (`0x00677d10`), 0xc unlock (`0x00677de0`), 0x12 cast (`0x006776a0`), 0x21 (`0x00677e50`),
     0x24 take item (`0x00677870`); also Module 3/4 and 3/5, GuiContainer 0x19/2,
     GuiInventory 0xd/1, Inventory 0xc/1, Party 0xe/2, Login 2/1 and 2/0x13;
   - a **direct call** into the server objects (the client and server share memory): for example
     keyboard/stick movement goes to `0x004fc4c0` on the player's `CSWSCreature`, and the pause
     key toggles the server pause through `TogglePlayerPause` (`0x00677800`);
   - a purely client-side effect (camera, GUI).
4. Server step 3 drains the ring: `CServerExoAppInternal::HandleMessage` (`0x004b15d0`) sends
   `'p'` messages to `CSWSMessage::HandlePlayerToServerMessage` (`0x00527b20`, dispatch on the
   major byte: ServerStatus 1, Login 2, Module 3, Area 4, GameObjUpdate 5, **Input 6**, Gold 8,
   Chat 9/0xb, Inventory 0xc, GuiInventory 0xd, Party 0xe, Cheat 0xf, CharList 0x11, Dialog 0x14,
   GuiCharacterSheet 0x15, QuickChat 0x16, GuiContainer 0x19, Journal 0x1c, LevelUp 0x1d,
   GuiQuickbar 0x1e, MapPin 0x20, Death 0x25, Character_Download 0x2b, ShutDownServer 0x2f,
   PlayModuleCharacterList 0x31), and `'s'` text commands to the admin handler
   `HandleServerAdminMessage` (`0x00528380`: `ServerStatus`, `Module` + `Load <name>`, `Run`,
   `Save …`, written `Module.Run` etc.). (high)
5. The Input handler (`HandlePlayerToServerInputMessage` `0x005254c0`) works on the creature the
   player controls and adds actions to its queue (actions.md). Those actions run in the same
   frame's `UpdateState`, when that creature's turn comes (the player and party are on AI level 4,
   which goes first). Minor 0x18 toggles the player pause and 0x19 sets it (6.3). (high)

### 1.5 Server → client: how state flows back

Three channels (high unless marked):

| Channel | When | What |
|---|---|---|
| Direct push of dirty state | end of every `UpdateState` | for each object on any AI level with a client twin (`CSWSObject::GetClientObject` `0x004cc2b0`, cached at `+0x224`): dirty bit 0 → client slot `+0x134(animation +0xd4, +0xd8)`, bit 1 → `+0x12c` (position), bit 2 → `+0x130(orientation +0x9c)`; bits at `+0x1fc`, tested and cleared by `0x004cc220` / `0x004cc250` |
| Game-object update messages | every 200 ms per player, or at once when `+0x10014` is set | `UpdateClientGameObjectsForPlayer` (`0x004b3ec0`) → `CSWSMessage` `0x00578520`; also re-sends the controlled object id when it changed (`0x0056f430`) |
| Event messages | when something happens | time of day (3/3, `0x0056a5f0`), module state (3/0xb, 3/0xc, 3/0xd), load progress (0x2c/2, 0x2c/3), area load, feedback, dialogue … read by the client in its step 12 next frame (`CSWCMessage::HandleServerToPlayerMessage` `0x0066a640`) |

Pause state is not a message: the server calls the client directly (`NotifyClientPauseState`
`0x0056c9f0` → `CClientExoAppInternal::SetPauseState` `0x005f7fa0`). (high)

Every client object then advances its own animation in `UpdateObjectsAndRender` with the world
delta (0 while paused). (med)

### 1.6 Clocks: `CWorldTimer`

`CWorldTimer` (0x44 bytes, constructor `0x004ae4c0`) is a game clock in microseconds plus a
calendar origin. (high)

| Offset | Field |
|---|---|
| `+0x00` / `+0x04` | fixed-step mode flag / steps per second (`SetFixedStep` `0x004ae170`; used by the movie-capture options, normally off) |
| `+0x08` | speed percentage (100); `SetSpeedScale(f)` (`0x004ae190`) stores `(int)(f × 100)` |
| `+0x0c` | current time, µs (64-bit) |
| `+0x14` | time at the previous `Update` (64-bit) |
| `+0x1c` | last high-resolution clock reading |
| `+0x24` | paused flag |
| `+0x28` / `+0x2c` | the (day, ms) snapshot `GetWorldTime` returns while paused |
| `+0x30` / `+0x34` | calendar origin: day and ms added to the counter |
| `+0x38` | minutes of real time per game hour (byte; 0 means 5) |
| `+0x3c` | ms per game day = `+0x38 × 1,440,000` |
| `+0x40` | s per game day = `+0x38 × 1440` |

Operations (high):

- `Update` (`0x004adbd0`): previous = current; current += (clock now − last reading) × speed / 100;
  last reading = clock now. In fixed-step mode current += `1e6 / steps × speed / 100` instead.
  **`Update` does not look at the paused flag**: pausing works because `GetWorldTime` returns the
  snapshot and `GetFrameDelta` (`0x004adc80`) returns 0 while the flag is set.
- `GetWorldTime(&day, &ms)` (`0x004ade40`): while paused, the snapshot; otherwise
  `day = +0x30 + floor(t / msPerDay)`, `ms = +0x34 + t mod msPerDay` with `t` = current µs / 1000,
  then normalised so `0 ≤ ms < msPerDay`.
- `PauseWorldTimer` (`0x004adff0`) takes the snapshot and sets the flag; `UnpauseWorldTimer`
  (`0x004ae030`) clears it and moves the origin so the clock resumes from the snapshot: paused time
  is lost, not caught up.
- `SetWorldTime(day, ms)` (`0x004adde0`) sets the origin; `CopyFrom` (`0x004adef0`) copies another
  timer (speed reset to 100); `AddWorldTimes` (`0x004adf50`), `SubtractWorldTimes` (`0x004ae460`,
  returns −2 and leaves the outputs alone when the first time is earlier), `CompareWorldTimes`
  (`0x004adfa0`, −1/0/1, −2 for an invalid time of day). A time of day ≥ ms per day is invalid
  everywhere, which matters for `DelayCommand` (4.3).

**Which clock drives what.** The server owns three, the client four. (high for the update rules,
med for the uses)

| Clock | Updated | Paused by | Used for |
|---|---|---|---|
| server `+0x10048` world timer | every frame | any pause bit | game time, every heartbeat, event times, effect durations, everything time-based on the server |
| server `+0x1004c` | every frame | player pause | objects exempt from a time stop (pause type 1), through `GetActiveTimer` |
| server `+0x10050` | every frame | never | objects exempt from the player pause (list `+0x10070`, empty in practice) |
| client `+0x24` world | every frame | any pause | `g_fFrameDelta` for client objects, animation, particles, texture animation |
| client `+0x28` | every frame | player pause | the time-stop twin of `+0x24` |
| client `+0x2c` interface | every frame | never (only movies and loading) | GUI render, camera, `CSWCModule::Render`'s argument, real-time effects |
| client `+0x30` | movie bookkeeping only | — | (low) |

`GetActiveTimer(objectId)` (`0x004b6c40`, forwarder `0x004ae830`) returns the time-stop or
player-pause clock for an object in the matching exempt list while that pause is on, else the
world timer; creatures read their heartbeat, perception, combat and movement time through it.
Doors, placeables, triggers, encounters, AoEs, items, the area and the module read the world timer
directly. (high)

Speed: `SetGameSpeed(f)` (`0x005f2f60`) sets the speed of the client `+0x24`, `+0x2c`, `+0x30`
timers and the server `+0x10048`, `+0x10050` timers. It is called every client frame with 1.0
(step 11), and by the slow-motion update (6.6). (high)

## 2. Object updates: the AI master

### 2.1 AI levels

`CServerAIMaster` (server `+0x10044`) keeps five lists of object ids, level 0 to 4, at
`+4 + 0x10 × level` (`{array, count, capacity, round-robin cursor}`); an object remembers its
level at `+0x78` (−1 = not listed). `AddObject` (`0x004b0850`) moves an object between lists,
`SetAILevel` (`0x004b08a0`) does nothing when the level is unchanged. Waypoints and sound objects
are never listed; every other object type joins level 0 in its constructor. (high)

| Level | Who | Set by |
|---|---|---|
| 4 | the PC and party members under player control | `CSWSCreature::AIUpdate` when `IsPC` (stats `+0x6c`) or player-controlled (`+0xa88`); `SetPlayerControlled(1)` (`0x004fdb20`) (high) |
| 3 | nobody | no code sets it, no script routine exists (NWN's script-set "high") (high) |
| 2 | creatures in combat mode (`+0x4e0` = 1) | `AIUpdate` raises level 0/1 creatures in combat to 2; `SetPlayerControlled(0)` (leaving the party) sets 2 (high) |
| 1 | active objects of an area that holds a player | `CSWSArea::IncrementPlayersInArea` (`0x00508c20`): when the first player enters, every level-0 creature, AoE and trigger, every non-static placeable (`+0x398`) and some non-static doors (`+0x3c0`) go to 1 (`0x00507220`). `CSWSCreature::AddToArea` (`0x004fa100`) picks 1 or 0 by the area's player count `+0x128`; `ActionStartConversation` and the talk order lift 0 to 1. A creature leaving combat drops from 2 to 1 (high) |
| 0 | everything else: items, encounters, stores, static placeables and doors, objects of areas without players | constructors; `DecrementPlayersInArea` (`0x00508c40`) drops level 1 to 0 when the last player leaves (`0x00507340`); a creature's perception tick drops it to 0 when its area has no player (high) |

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
        // movement pre-pass, outside the budget
        for each creature on this level with the flag +0x1f8 set whose first queued action
            is MOVETOPOINT (1) or FOLLOWLEADER (0x3d), or whose movement state +0xa8c is 4, 5, 6:
                UpdateMovement(creature)            // 0x0051d9c0; result 2 sets +0xa8c = 1
        // events
        while the queue head's (day, ms) <= now:
            pop it and deliver it (4.4)
        // one AIUpdate; "elapsed" is measured after the previous AIUpdate (0 on the first pass,
        // so the pre-pass and event time of this pass are only counted after the next update)
        if elapsed <= budget:
            cursor = (cursor + 1) mod count          // the cursor persists across frames
            obj = list[cursor]
            if obj is missing, or is not an object type (< 5), or obj == the first object
               updated at this level this frame:  stop this level
            else obj.AIUpdate()                      // vtable slot 28; > 75 ms logs a warning
            elapsed = clock() − start
        if the queue head is now due: stop this level
        if elapsed > budget: stop this level
    remaining −= min(elapsed, budget)
for each object on every level (4 → 0) with the flag +0x1f8 set and a client twin:
    push dirty animation / position / orientation to it (1.5)
module.UpdateModuleAndArea()                          // 0x004c6dc0, section 2.6
```

Consequences an implementer must keep:

- **Each level gets at least one `AIUpdate` per frame** (elapsed is 0 on the first pass), and
  a level's round-robin resumes where it stopped last frame. Under load, low levels update less
  often; with KOTOR's object counts usually every object is updated every frame. (high/med)
- **A due event ends the current level.** An `AIUpdate` that queues a zero-delay event (a
  `SignalEvent`, `AssignCommand`, …) makes the level stop; the event is delivered at the start of
  the next level's loop, and the interrupted level continues next frame from its cursor. (high)
- **Movement runs outside the budget** for every walking creature of a level, before every
  `AIUpdate` of that level (so possibly several times per frame; it is time-based and idempotent
  within a frame). Movement itself is movement.md's. (high for the call pattern)
- Events are delivered even when no `AIUpdate` happens, and before the first one: scripts queued by
  the client or by the previous frame run first. (high)

### 2.3 What a creature does per update (`CSWSCreature::AIUpdate` `0x004fe210`)

In order (high for the order; the named sub-systems belong to the pages in brackets):

1. Two debug hooks (one-shot "set HP to 1" on a party member, a distance printout); flags never
   set in the exe.
2. If the creature is the PC or player-controlled and not on level 4: `SetAILevel(4)`.
3. **`RunHeartbeat(1)`** (`0x004eb6e0`): OnSpawn once, OnHeartbeat, perception (2.4).
4. `now` = its active clock; `dt` = now − last update (`+0xa8/+0xac`), in ms, stored at `+0xcc`.
   Every per-creature countdown below subtracts `+0xcc`.
5. **`UpdateCombat`** (`0x004faf20`): combat-round timers, skipped while the player pause is on
   (combat.md).
6. `0x004ed110`: a countdown at `+0x384` that pokes the area's client sound object when it ends
   (low).
7. **`UpdateEffectList(now)`** (`CSWSObject::UpdateEffectList` `0x004d1730`): periodic effects tick
   (regeneration-type 7, poison/disease-type 0x23 via event 14 REMOVE_EFFECT, type 5), then every
   temporary effect whose expiry time has passed is removed and the scan restarts (rules.md).
8. **`RunActions(now, start)`** (`0x0057f4a0`, about 1 ms of work per call) (actions.md).
9. last update = now.
10. Ground snap: z = walkmesh height at (x, y) (`0x004bc380`); a non-leader party member off the
    walkmesh is moved to a free spot within 5 m of its party-table position; jumping states 4/5
    add `+0xa94`; `SetPosition` (movement.md).
11. `UpdateActivityFromQueue` (`0x004f1460`: recomputes `+0x9f2/+0x9f4` from the queued actions,
    low) and, in an area,
    trap and mine detection with the Awareness skill (`DoTrapDetection` `0x004fa390`, low;
    rules.md).
12. Combat-mode timers: stealth (`+0x4e4`), a 3000 ms tick at `+0x52c`, cooldowns `+0xab0`,
    `+0x538`, `+0x530` (1500 ms while playing animation 10004/10086/10087), eight countdowns at
    `+0x9a8`, an 8000 ms loop at `+0x398` (low for their meaning).
13. **Regeneration** for player-controlled, living creatures: hit points by
    `regeneration.2da HealthRegen` % of max HP per second and Force points by `ForceRegen` % of max
    FP per second, row 1 `OutOfCombat` or row 0 `InCombat`; shipped values 0/0 and 0/1, i.e. only
    Force regenerates, 1 % of max per second out of combat (med; rules.md has the details).
14. `+0x9d4` set (a "talking/busy" state, low): every 300 ms `0x004f6f30`.
15. AI level: combat mode on and level 0/1 → 2; combat mode off and level 2 → 1 if the area holds
    a player, else 0.
16. Stealth-XP countdown `+0xaa4` against the area's pool (`+0x2b8`/`+0x2bc`, `0x00506aa0`)
    (rules.md).

### 2.4 Heartbeat, spawn and perception (`CSWSCreature::RunHeartbeat` `0x004eb6e0`)

All times from the creature's active clock. (high)

**OnSpawn**: while the "spawn fired" flag `+0x34c` is 0, every call runs `ScriptSpawn` (`+0x270`).
At the end of the first call the flag is set, so OnSpawn runs exactly once, **on the creature's
first `AIUpdate`** — not when it is created. (high)

**OnHeartbeat**: due when `now − lastHeartbeat (+0x350/+0x354) ≥ interval (+0x358)`, or on the
first call — so a creature's first `AIUpdate` runs OnSpawn and then OnHeartbeat at once. Then:

- a counter `+0x394` is incremented; the heartbeat really fires only if the creature is not on
  level 0, or the counter reached `interval / 64` (≈ 47–65 due checks), or it is the first call.
  Level-0 creatures therefore heartbeat much more slowly. (high)
- it runs `ScriptHeartbeat` (`+0x230`) only if the creature is not dead (slot 37), and, after the
  first call, only once a previous heartbeat time exists (`+0x354` non-zero);
- then, for a creature in a mind-affecting state byte `+0x8ed` = 1, 2 or 0xb, it runs
  `statescripts.2da` row 3, 2 or 1 `SCRIPTNAME` (`k_sup_static`, `k_sup_fear`, `k_sup_static`) and
  makes the creature uncommandable (`+0xe8 = 0`); then `0x00518660` (low);
- last heartbeat = now; **interval = 3000 + rand() % 1200 ms**.

**Perception** (`UpdatePerception(mode)` `0x0051b050`), two timers:

| Timer | Who | Out of combat | In combat (`+0x9d4` set) | Mode |
|---|---|---|---|---|
| A (last run `+0x360/+0x364`, period `+0x35c`) | non-party creatures | meant: every 4000 ms | meant: every `300 + rand() % 400` ms | 1: check only the party members |
| B (last run `+0x388/+0x38c`) | everyone | every 4000 ms | every 200 ms | 2 (non-party: everyone but player-controlled creatures) or 0 (party member: everyone) |

**Timer A never stores its last run**: `+0x360/+0x364` are zeroed by the constructor and written
nowhere else (checked in the disassembly of `0x004eb6e0`), so "time since the last run" is the
time of day, and mode 1 runs on **every `AIUpdate`** except during the first 4 s (in combat the
first 0.3–0.7 s) of each game day. A faithful port checks the party every update; mode 1 is cheap
(it only looks at the party members). (high)

Timer B, like the heartbeat, is throttled on level 0 (a counter `+0x390` must exceed 149,
randomised to `rand() % 50` after each run). The first call does both, right after OnSpawn and the
first OnHeartbeat. A perception pass also removes vanished creatures from the perception list and
skips a dead creature that is not in combat. (high)

Ranges (`GetSightRange` `0x004efc70` → `+0x914`, `GetHearingRange` `0x004efd20` → `+0x918`; the
pass uses the larger as a radius, scanning the area's x-sorted creature list `+0x190`):

- PCs: `ranges.2da` row 12 `PercepRngPlayer` (250 / 20) (high);
- other creatures: the UTC's `PerceptionRange` byte (default 11) as a `ranges.2da` row, where 11
  means "use `appearance.2da PERCEPTIONDIST`" (itself a `ranges.2da` row) (high);
- any creature except the player in combat mode: row 18 `PartyCombat` (35 / 20) (high).
  Party followers get rows 12/11 when they join (actions.md).

The individual check (`0x00502ac0`: line of sight, stealth, the ON_PERCEPTION event) is
rules.md's/combat.md's.

### 2.5 Other object types

| Type | `AIUpdate` | Per update, in order | Conf. |
|---|---|---|---|
| placeable | `0x005849d0` | OnHeartbeat (`+0x2b4`) every ≥ 6000 ms of world time (last at `+0x348/+0x34c`; the first due check only records the time; skipped when dead); `UpdateEffectList`; `RunActions` | high |
| door | `0x005889c0` | same, OnHeartbeat `+0x250`, last at `+0x30c/+0x310` | high |
| trigger | `0x0058d760` | OnHeartbeat (`+0x244`) every 6000 ms (no first-time skip, no death check); trap visibility (animation 10143 hidden / 10144 shown: shown once detected, or for a non-hostile trap; med); `RunActions`. No effects | high |
| area of effect | `0x00595d10` | `dt` at `+0xcc`; OnHeartbeat (`+0x260`) every 6000 ms; follows its creator (`+0x24c`) unless stationary (`+0x230`), destroying itself (event 11) when the creator is gone; duration countdown `+0x288` (when `+0x28c` = 1) → destroy; `RunActions` | high |
| encounter | `0x00593fb0` | spawn pending creatures (`0x00591ca0`, which sets their AI level by the area's player count); respawn when `Reset` and `ResetTime` s passed since exhaustion and the count `+0x2c8` is under `Respawns` (−1 = always); while active (`+0x238`): heartbeat **as a SIGNAL_EVENT** (script event 0) every 6000 ms, and `RunActions` | high |
| item | `0x0055cb60` | recharges timed properties: a property of type 10 whose sub-value (+6) is 14–18 and that is marked used is made usable again 60/120/180/240/300 s after its use time. No actions, no heartbeat | med |
| store, waypoint, sound | empty | — | high |

Doors and placeables run their heartbeat script directly, not through the event queue; only the
encounter uses an event. All heartbeats read the world timer, so all of them stop while paused.

### 2.6 The module and the area

At the end of `UpdateState`, `CSWSModule::UpdateModuleAndArea` (`0x004c6dc0`) alternates frames:
(high)

- **Module frame** (`CSWSModule::AIUpdate` `0x004c6c90`): if ≥ 6000 ms of world time passed since
  `+0x128/+0x12c`, run `Mod_OnHeartbeat` (`+0xb0`; skipped the first time) and stop; otherwise
  `UpdateTime` (7.4) and, while a time stop is on, `CheckTimeStopExpired` (`0x004c6480`, 6.5).
- **Area frame** (`CSWSArea::AIUpdate` `0x00508a30`): weather (below), then the area's OnHeartbeat
  (`+0x164`) every 6000 ms (`+0x13c/+0x140`, first skipped).

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
| perception (full pass), out of / in combat | 4000 ms / 200 ms | `0x004eb6e0` | high |
| perception (party check) | every `AIUpdate` in practice (meant 4000 ms / 300–699 ms; last-run time never stored) | `0x004eb6e0` | high |
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
world clock only moves in step 2 of the server frame, **an event queued with zero delay anywhere
during frame N is due in frame N**: queued before `UpdateState` (by the client frame, by a player
order in the message step) it is delivered at `UpdateState`'s first delivery point; queued during
`UpdateState` it is delivered at the next delivery point (2.2); queued after it (server steps 7–9)
it waits for frame N+1. Events queued by an event handler are delivered in the same drain loop, so
chains of zero-delay signals complete within one delivery point, in queue order. An event with a
delay of d ms fires in the first frame whose world time is ≥ queue time + d. (high)

### 4.3 The routines

| Routine | Handler | Queued as | Conf. |
|---|---|---|---|
| 7 `DelayCommand(float s, action)` | `0x0052fe30` | event 1 (TIMED_EVENT) to `OBJECT_SELF`, caller = self, delay `(int)(s × 1000)` ms, 0 days. Dropped (situation freed) when `OBJECT_SELF` is invalid. **A delay of one game day or more (2880 s at MinPerHour 2), or a negative one, is silently dropped** because the delta is invalid | high |
| 6 `AssignCommand(object, action)` | `0x0052e720` | event 1 to the object, delay 0, caller = `OBJECT_SELF` (or invalid). The action runs with `OBJECT_SELF` = the target when the event is delivered, normally later in the same frame | high |
| 294 `ActionDoCommand(action)` | `0x0052c740` | not an event: action 0x25 on `OBJECT_SELF`'s queue, run by `RunActions` in order | high |
| 131 `SignalEvent(object, event)` | `0x005439d0` | event 10 (SIGNAL_EVENT) with the `CScriptEvent` payload, delay 0, caller = `OBJECT_SELF` if it exists | high |
| 8 `ExecuteScript(name, object, n)` | `0x00535b70` | not queued: runs nested, immediately (vm.md) | high |

Event 1 is run by every object type's `EventHandler` (and the area's and module's) as
`RunScriptSituation(situation, its own id)` ([vm.md](vm.md)). (high)

### 4.4 Delivery

The target id decides (high, `0x004b0b70`):

- an object (type ≥ 5): virtual slot 30 `EventHandler(id, caller, payload, day, time)`;
- the area (type 4): `CSWSArea::EventHandler` (`0x0050d6c0`): 1 (situation), 5 APPLY_EFFECT
  (only effect type 0x1e, placed at a location), 17 SPAWN_BODY_BAG (creates the body-bag
  placeable), 10 with script events 0 (OnHeartbeat, also resets its heartbeat timer), 0xb
  (OnUserDefined), 0xc (OnEnter, sets the entering object), 0xd (OnExit), and 26
  AREA_TRANSITION (5.2);
- the module (type 3): `CSWSModule::EventHandler` (`0x004c5120`): 1, and 10 with script events
  0 OnHeartbeat (`+0xb0`, resets the heartbeat timer), 0xb OnUserDefined (`+0xb8`), 0x11
  OnModLoad (`+0xc0`), 0x10 OnModStart (`+0xc8`), 0xe OnClientEnter (`+0xd0`), 0xf OnClientLeave
  (`+0xd8`), 0x12 OnActivateItem (`+0xe0`), 0x13 OnAcquireItem (`+0xe8`), 0x14 OnUnacquireItem
  (`+0xf0`), 10 OnPlayerDeath (`+0xf8`), 0x20 OnPlayerDying (`+0x100`), 0x21 OnSpawnButtonDown
  (`+0x108`), 0x23 OnPlayerRest (`+0x110`), 0x25 OnPlayerLevelUp (`+0x118`), 0x26 OnEquipItem
  (`+0x120`), and 0x24 DESTROYPLAYERCREATURE (deletes the object). The 15 module script names
  are stored in this order from `+0xb0`, 8 bytes apart;
- an id that no longer exists: the payload is freed (`ClearEventData` `0x004b0ab0`).

### 4.5 Pause, transitions and saves

- **Pause**: the world clock is frozen, so delayed events wait; zero-delay events queued during the
  pause are still delivered, because `UpdateState` keeps running (6.2). A delay counts world time
  only: pausing for a minute does not make a `DelayCommand(5.0)` fire early. (high)
- **Loading**: the world clock is paused for the whole module load (5.4), so no queued time passes.
  (high)
- **Leaving a module**: `UnloadModule` (`0x004b9240`) empties the queue (`ClearEventQueue`
  `0x004b11c0`) — but just before, the module being left was written to `GAMEINPROGRESS:` with its
  queue (`SaveModuleIFOStart` `0x004c7050` → `SaveEventQueue`, GFF list `EventQueue`, fields `Day`,
  `Time`, `ObjectId`, `CallerId`, `EventId`, `EventData` with a payload struct per type: 0x7777
  script situation, 0x4444 script event, 0x1111 effect, …). When that module is entered again from
  its saved state, `LoadModuleStart` restores the queue in saved order. Times are absolute, so
  everything that came due while the party was elsewhere fires on the first frame back. (high for
  save/restore, med for the "overdue" consequence)
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
| trigger enter | script event 0xc (OBJECT_ENTER) on a transition trigger (`+0x2b4`) with a link: same handshake | high |
| `StartNewModule(module, waypoint, movie1..6)` (routine 509, `0x00544390`) | sets the request directly, queues the six movies on the client (`AddQueuedMovie` `0x005edb50`), and blacks the screen at once while a conversation is running (in-game GUI `+0xb4`, or `+0xc04`) | high |
| area event 26 | `CSWSArea::EventHandler`: same handshake on the area, payload = 8 strings (module, waypoint, 6 movies). No code queuing the first event 26 was found | med |
| cheats and menus | console warp `0x0060af50`, a GUI path `0x006cf9d0`, loading a save (`0x006ca250`) | med |

### 5.2 The two-phase handshake (doors, triggers, area event 26)

Phase 1, on the click/enter event (high):

1. Only for the player's creature or a party member; refused (pending flag cleared) while a
   conversation is running (in-game GUI `+0xb4`, set by the conversation code through
   `CGuiInGame::SetDialogPending` `0x0062ec60`).
2. **All party members must be within 30 m of the leader** (`AreMembersNearLeader` `0x00635350`);
   otherwise run `k_trg_transfail` on the creature and stop.
3. Take a fresh token from the area (`NextTransitionToken` `0x00506ac0`: a byte counter at area
   `+0x2c8`, never 0), copy the event with the token, and queue it back to the same object with a
   **500 ms** delay.
4. Start a 0.5 s fade to black, mark the area "transition pending" with the token
   (`SetTransitionPending` `0x00506b30`: `+0x2c4`, `+0x2c9`; it also disables client input), and
   **force the player pause off**.

Phase 2, when the copy arrives and a transition is pending with the same token: if the creature is
alive and not a downed party member, set the transition request and clear the pending flag
(input back on); otherwise fade back in and clear. A stale token is ignored. (high)

### 5.3 Leaving: `StartModuleTransition` (`0x004ba920`)

Server step 8 sees the request (only when the in-game GUI flag `+0xdc` is clear), and (high unless
marked):

1. Stores the current world time and calendar (year, month, day, hour, minute, second, ms) and the
   (day, ms) pair as the "pause snapshot" to hand to the next module (`0x004b22d0`, `+0x100ac`,
   `+0x100b0`), and prepares the party table (`0x00565530`).
2. `StartModuleTransition(name)`, unless one is already in progress (`+0x100b4`):
   1. client: pick the load screen for the target (`0x005ee090` / `0x005edf00`), reset input
      state, close panels, stop sounds, **play the queued movies** (`PlayQueuedMovies`
      `0x00602650`);
   2. the target must exist as `MODULES:<name>.mod` or `.rim`, else nothing more happens;
   3. set "in progress" `+0x100b4` and "this is a transition" `+0x1007c`;
   4. **area OnExit for each player** (`RunAreaExitScripts` `0x004b4f50`, sets the area's
      "last exiting" `+0x1d8` to the player creature);
   5. **save the player characters** (`SavePlayerCharacters` `0x004b2ba0`): `ClearAllActions`
      on each player creature, write them in a `Mod_PlayerList` IFO to `TEMP:pifo`, and save the
      party table (party-items-saves.md);
   6. **save the module being left** to `GAMEINPROGRESS:<module>` (`0x004b2e70`:
      `SaveModuleIFO` and the area's GIT, only if `modulesave.2da IncludeInSave` allows it);
   7. `modulesave.2da` for the target: `DeleteSaveGroupOnEnter` deletes the `GAMEINPROGRESS:` saves
      of every module of that save group (`DeleteModuleSaveGroup` `0x004b2380`) — this is how
      Taris, Leviathan etc. are forgotten after leaving them;
   8. **autosave** when `ShouldAutoSaveOnEnter` (`0x004b5050`) says so (5.7):
      `WriteTransitionAutoSave` (`0x004b8300`, a save that loads into the *target* module; its
      `AUTOSAVEPARAMS` carry the start waypoint, movies and time);
   9. `BeginLoadModule` (`0x004ba820`): reset input, **pause the client and server world
      timers**, then `LoadModule(name)` ([modules.md](modules.md)).

`LoadModule` first unloads the current module (`UnloadModule` `0x004b9240`; med for when): both
pause types off, exempt lists emptied, player creatures removed from their area and destroyed,
the party table and the custom tokens cleared, the module and with it the area and every object
deleted, the object array and the event queue emptied, `CURRENTGAME:` removed. Then it fills the
transition block and sets load mode 1 (3 for a module coming from a save). (high)

### 5.4 Loading: the transition block and the ticks

The block at `g_pAppManager+0x14` (`CModuleTransition`, 0x3c bytes): `+0` busy, `+4` mode (1 load,
2 save, 3 load from save), `+8` areas loaded, `+0xc` area count, `+0x10` "skip one client frame",
`+0x14` done, `+0x18` module name, `+0x20` source path, `+0x28` target path, `+0x30` resource type,
`+0x38` error code. (high)

While busy, the server frame does one step per frame (high):

| Tick | Condition | Work |
|---|---|---|
| 1 | count = 0 | `CopyModuleFile`, `new CSWSModule`, `LoadModuleStart` (IFO, time, factions; sets count = 1) |
| 2 | loaded ≠ count | `LoadModuleInProgress(0)`: the area (ARE, LYT, GIT objects, PTH); loaded = 1; progress message to the client |
| 3 | loaded = count | `LoadModuleFinish`: queue **SIGNAL_EVENT MODULE_LOAD (script event 17) to the module**; done = 1; server state = 1 ("module loaded"); `+0x100b4` = 0; tell the client (load result, "ModuleLoaded" status) |

Any failure calls `FailModuleLoad` (`0x004ba5b0`): unload, error code in the block, state 0, tell
the client, which returns to the main menu (`AbortToMainMenu` `0x005fcbd0`).

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
| 4 | server | `Module.Run` → `StartModuleRunning` (`0x004b6270`) | state 2: **the AI master starts**. Players already in the module are placed (none after a transition: `UnloadModule` cleared their flag). For a module loaded from a save the first player is restored from it and **OnClientEnter** queued (`0x004b5f50` → `SignalPlayerEnterModule` `0x004b5c50`). Sends "module running" (3/0xc). |
| 5 | server, same frame | `UpdateState` | delivers the queued events in order: the creatures' area OnEnter (or the restored queue), then **OnModLoad**; then the AIUpdates begin: every GIT creature's **OnSpawn** fires on its first `AIUpdate` (level 0, leftover budget, possibly over several frames) |
| 6 | client | 3/0xc → `0x00652860` | replies Login 2/0xf (`0x00678030`) |
| 7 | server | Login 0xf → `PlayerLoginToModule` (`0x004b7470`) | after a transition: the PC is re-created from `TEMP:pifo` (`0x00561e30`) and the party table restored (`0x00565760`); `SignalPlayerEnterModule` queues **OnClientEnter** (script event 0xe; also OnPlayerDeath when the PC is dead) and sends the module info (3/1). The PC is not in the area yet. |
| 8 | client | 3/1 | builds the client module and camera (`0x0063f660`), replies 3/2 |
| 9 | server | Module 3/2 → `PrepareAreaForPlayer` (`0x004b3a90`) | gives a new player the IFO's `Mod_Entry_*` start, keeps a known player's stored position; sends the area (10/2, 10/1) |
| 10 | client | area message (`HandleServerToPlayerAreaLoad` `0x0064bab0`, `0x0064dcf0`) | loads the client area synchronously, drawing loading frames; replies Area 4/3 (`0x006778f0`) |
| 11 | server | Area 4/3 (`0x00524b80`) → `PlacePlayerInModule` (`0x004b3d10`) | if a waypoint tag is pending, the start position and facing become the waypoint's (tag lookup `0x004c6e00`) and the tag is cleared; snap to a free walkmesh spot within 20 m (`0x004be860`); `AddToArea` (`0x004fa100`) → `AddObjectToArea`, which **queues the area's OnEnter (script event 0xc) for the PC** and, as the first player, raises the area's objects to AI level 1; a perception pass; the party is placed (`0x00565b00`); pause states re-sent |
| 12 | client | step 1 of its frame | the area is loaded and the PC's client creature exists: **the load screen goes away**, all clocks unpause (world time resumes from the stored snapshot, 7.2), and unless an autosave is pending the 1 s fade-in starts after 0.5 s and input returns |

So the script order on arrival is (med for the overall order; high for each step):

1. on a fresh module, the area's **OnEnter once per GIT creature** (entering object = that
   creature); on a module re-entered from `GAMEINPROGRESS:` instead the **restored event queue**
   (4.5), and no creature OnEnter;
2. **OnModLoad** — on every entry, fresh or re-entered;
3. each creature's **OnSpawn** on its first `AIUpdate` (immediately followed by its first
   OnHeartbeat); creatures restored from a saved state keep their "spawn fired" flag and don't
   spawn again;
4. **OnClientEnter** for the PC;
5. the area's **OnEnter for the PC**, then for party members as they are placed;
6. the load screen goes away and control returns to the player.

All of it happens with the world clock still paused, so every event carries the same time and
the queue order is the insertion order. A conversation or cutscene started by any of these
scripts takes over as soon as the load screen is gone. An area OnEnter script that should react
only to the PC has to test `GetEnteringObject()`.

`Mod_OnModStart` (script event 16) is never queued by the engine: no code creates that event (high,
searched; KOTOR's IFOs leave it empty). `Mod_StartMovie` is read into `+0x7c` and saved, but no
reader was found (med). The probe of the 117 shipped module IFOs found `Mod_OnModLoad` set in 13
modules and `Mod_OnClientEntr` in 7: KOTOR mostly uses the area's OnEnter.

### 5.6 The load screen

The client shows `loadscreens.2da BMPResRef` (row from the area's `LoadScreenID`, or a random one)
with a progress bar advanced by the resource loader and the room loading; the hint text and the
panel are gui.md's. `RenderLoadingFrame` (`0x00401c10`) draws GUI-only frames with a fixed 1/30 s
delta and pumps window messages ([app.md](app.md)). (med)

### 5.7 Autosaves

Two independent mechanisms (high):

- **On a transition** (`ShouldAutoSaveOnEnter` `0x004b5050`, column `AutoSaveOnEnter` of
  `modulesave.2da` for the *target*): `force` → save; `no` → don't; `yes` → save only if the
  15-minute real-time timer is due *and* the `AutoSave` game option (client options `+8` bit 2) is
  on; no row → save. A save resets the timer. Shipped rows: 28 force, 60 yes, 35 no.
- **From a script**: `DoSinglePlayerAutoSave` (routine 512) sets `+0x100b8`; server step 9 starts
  an `AUTOSAVE` save (`RequestSaveGame` `0x004b58a0`, run by the save state machine
  `DoSaveGame` `0x004b3110`, mode 2 of the transition block) when there is disk space, and the
  fade-in normally done on arrival is done after the save.

## 6. Pause

### 6.1 Pause types

`CServerExoAppInternal +0x10078` holds two bits (high):

| Bit | Type | Meaning | Exempt list | Exempt clock |
|---|---|---|---|---|
| 1 | 1 | **time stop** (effect type 0x40) | `+0x10074`: the caster | `+0x1004c` |
| 2 | 2 | **player pause** | `+0x10070`: nobody in practice | `+0x10050` |

`SetPauseState(type, on)` (`0x004b8110`): turning a type on sets the bit and pauses the world
clock (and the time-stop clock too when the player pause is on); turning it off syncs the exempt
clocks back to the world clock, lets exempt objects reset their update times (slot 2, empty in
KOTOR's classes), and unpauses what no remaining bit holds. Either way the client is notified
directly and mirrors the same logic on its clocks (`CClientExoAppInternal::SetPauseState`
`0x005f7fa0`, bits at client `+0x1cc`). `TogglePauseState` `0x004ba610`, `GetPauseState(type)`
`0x004b1d80`, `GetPauseType` `0x004b1da0` (2 if player-paused, else 1 if time-stopped, else 0).

### 6.2 What stops and what keeps running

| Keeps running | Stops (world time frozen) |
|---|---|
| both `MainLoop`s, messages, input, `ProcessInput` and the GUI (interface clock) | world time, game calendar, every heartbeat, perception timers, effect durations, delayed events |
| the camera (interface clock) | combat rounds (`UpdateCombat` and the attack action check the player pause explicitly) |
| `UpdateState`: zero-delay events (SignalEvent, AssignCommand, script-signalled events) are delivered; every object gets its `AIUpdate` | creature `dt` = 0: movement, regeneration and countdowns don't advance |
| `RunActions`: actions that need no time (DoCommand, Speak, ClearAllActions, equipping…) complete; time-based ones wait | client object animation, particles, texture animation (world delta 0) |
| the party-death / revival timer (real time) | sound mode 2 ("paused") on a player pause |

So in KOTOR's "pause and queue orders" style, orders given while paused become actions on the queue
and start executing at once, but make no progress until the clock moves. (high for each item from
the code; the overall behaviour med)

### 6.3 Requests

The player pause is changed through the client, which applies requests at the end of its frame
(step 28): (high)

- `RequestPause(bPause, reason, bForce)` (`0x005f2e10`, forwarder `0x005edc20`): records the
  request (bit 2 of `+0x37c`, desired state `+0x380`, reason `+0x388`), sets sound mode 2 or 0 and
  blocks or unblocks game input; during a conversation (in-game GUI `+0xb4`) only unpause or
  forced requests are taken.
- Step 28: if the server's player pause differs from the request, `TogglePlayerPause` (`0x00677800`
  → server `TogglePauseState(2)`), then the HUD's pause label (`0x0062def0`, reason). A request
  made while an area transition is pending is dropped (med).
- Sources: the pause key and the HUD `TB_PAUSE` button (reason 4), `PauseGame(b)` (routine 57,
  `0x00546590`, reason 0), opening the in-game menus (`0x0062c9b0` runs `k_sup_guiopen` and toggles
  the pause; gui.md), the conversation and other GUI paths (`0x0062d040`, `0x0062e310`, …),
  window deactivation (`OnAppDeactivate` `0x00401d90` sets the player pause and remembers whether
  it was already on; `OnAppActivate` `0x00401e00` restores it), the server Input messages 0x18
  (toggle, only with an area and when a flag of the server options block allows it, `+0xc4` of
  internal `+0x10004`) and 0x19 (set).
- Transitions force the pause off (5.2); `UnloadModule` clears both types.

### 6.4 Auto-pause

`[Autopause Options]` in `swkotor.ini` sets bits of the client options word `+0x14` (read by
`0x0061dbe0`): `End Of Combat Round` 0x800, `Enemy Sighted` 0x1000, `Mine Sighted` 0x2000,
`Party Killed` 0x4000, `Action Menu` 0x8000, `New Target Selected` 0x10000. Triggers found (med):

| Trigger | Where | Reason |
|---|---|---|
| a hostile creature becomes visible | `UpdateSelectableObjects` (`0x005fa5a0`), also plays the "enemy sighted" feedback 0x15 | 1 |
| a mine becomes visible | same function | 0xb |
| a party member dies while others live | death handling (`0x004e0ac0`), with a 2 s cooldown (`+0x39c`) | 9 |
| action menu / target selection | HUD handlers `0x006884b0`, `0x00688520`, `0x0068af70`, `0x0068afe0` (option bit 0x8000) | 7 |
| end of a combat round | `CSWSCombatRound::EndCombatRound` (`0x004d4620`) | not traced |

`RequestAutoPause(bOn, reason)` (`0x005f3f10`, forwarder `0x005edee0`) pauses only if the game is
not already paused and no conversation runs, and remembers that the pause is automatic
(`+0x384` bit 0);
during the one-second window `+0x38c` after an unpause it defers the request (`+0x390` = 1 s,
`+0x398` = reason) and client step 27 retries it. Unpausing (the pause key) clears the automatic
flag. (med)

### 6.5 Time stop

Effect type 0x40 (`OnApplyTimeStop` `0x004dcb40`, `OnRemoveTimeStop` `0x004dcc90`): applying it
with no pause adds the caster to the time-stop exempt list and turns pause type 1 on; applying
another while one runs extends the existing effect's expiry; removing it turns type 1 off and
removes the caster. The module frame (`CheckTimeStopExpired` `0x004c6480`) turns type 1 off when
no exempt creature still carries the effect. The caster's creature reads the `+0x1004c` clock, so
it alone keeps acting. No KOTOR power uses it as far as found (med).

### 6.6 Slow motion and the party wipe

The whole party down is the one place the game ends without a script. The server notices it
(`UpdatePartyDeath`, 1.3: every member of the client's party list is dying and no slow motion is
running) and calls `CClientExoApp::StartDeathCamera` (`0x005edc40`, which forwards to
`CClientExoAppInternal::StartDeathCamera` `0x005f7200`). The call repeats every server frame until
it has set the slow-motion flag, and the server's party-death step is skipped while that flag is up,
so nobody gets back up during the sequence. (high)

**`StartDeathCamera`**, in order (high unless marked):

1. Sets `+0x2c0` (slow motion on) and `+0x2c4` (the speed curve is to be fitted afresh).
2. Deactivates every panel in the GUI manager's list (`0x0040c120`, `SetActive(0)` each): the HUD, a
   menu and the pause banner all stop being shown and picked.
3. Opens the in-game GUI's message box (`CGuiInGame+0x98`, set up by `0x00627260`): one button
   (mode byte 2), modal, text dialog.tlk 42351, "Your entire party has been killed." with
   "Return to Main Menu." on a second line. Its OK callback (`0x00625a60`) calls `0x005ede10(client,
   1, 0, 1)`, which sets the wipe flag `+0x1a8` = 1, the countdown `+0x374` = 0.0 and `+0x1ac` = 1.
4. Puts a `CSWCDeathCamera` (`0x0063bbd0`, 0x40 bytes) on the scene's camera, watching the leader
   (the client creature at `+0x2d4`); see below.
5. `StartGlobalFade(bFadeIn 0, wait 12.0, length 1.0, black)` (`0x0062abf0`): the fade layer waits
   12 s and then goes to black over 1 s. The argument order is the script routine's
   (`SetGlobalFadeOut(fWait, fLength, r, g, b)` pops its two floats into the same two slots,
   `0x005460d0`).

**`UpdateSlowMotion`** (`0x005f7330`, every client frame, step 9 of 1.2) times itself on the real
high-resolution clock (`+0x2c8` the last reading, `+0x2cc` the seconds so far, t). While `+0x2c0`
is set it calls `SetGameSpeed(speed)` with

    speed(t) = 0.2 + 0.8 * ln(t / 4) / ln(t0 / 4)     for t <= 4 s   (1.0 at the first frame, t0)
    speed(t) = 0.2                                     after that

where t0 is the first frame's step (the curve is fitted to it when `+0x2c4` is set, then the flag
clears). The world falls to a fifth of its pace in four real seconds, quickly at first. `SetGameSpeed`
(1.6) scales the interface clock too, and the fade layer advances on that clock (`CSWGuiFade::Render`
`0x00624570` adds the clock's step to its elapsed time `+0x6c`, which `Start` sets to 0.1; the layer is
"busy" while that is non-zero and not past wait + length, `0x006244b0`, `GetIsFadePanelBusy`
`0x0062ac60`). The 13 s of fade are therefore 13 s of slowed time: about 1.5 s in the first four real
seconds, then 11.5 s at a fifth, some 61 s of real time in all (med: the second half rests on the
interface clock being scaled).

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
`+0x374`, and sets the sound and HUD modes back for the menu. So OK and the end of the fade lead to
the same place, the main menu with the game's state gone: no retry, no load prompt. The `EndGame`
script routine (564, `0x00535570`) fills the same three fields (`+0x1a8` = 1, `+0x374` = 5.0 s, or 0
when its argument is 0, `+0x1ac` = the argument), so the end of the story leaves through this block
too. (high for the block; low for what the box shows after `EndGame`)

**The death camera** (`CSWCDeathCamera`, a `CAurCameraController`; constructor `0x0063bbd0`,
`SetTarget` `0x0063a770`, `Update` `0x0063a810`). Fields (med): `+0x14` the leader; `+0x18` the
orbit heading in degrees, started as the heading from the camera's position to the leader; `+0x1c` =
30 (degrees per second of the interface clock, that is of slowed time); `+0x20` = 90; `+0x24` = 3.0 m;
easing rates `+0x28` = 0.5 (heading), `+0x2c` = 0.01 (pitch), `+0x30` = 0.5 (distance); `+0x34` = 0.75 m
easing to `+0x38` = 0 at `+0x3c` = 0.01. Each frame (the easings are per frame, not per second): the
orbit heading advances by 30 degrees times the step and wraps at 360; the camera's own heading moves
half the way to it; its pitch moves 1 % of the way to `90 - (+0x20)` = 0, which in the pitch
convention shared with the chase camera (90 is level; the style's 80 is ten degrees below level) is
*straight down*; the look-at point is the leader's position plus a height `+0x34` that drains 1 % a
frame to the feet; the camera stands at that point plus its backward axis times a distance that moves
half the way to 3 m. A ray from the look-at point to the camera is cast against the area and the
camera is kept 0.25 m off what it hits. So the picture swings in from the chase camera to 3 m over the
leader and settles into a slowly turning view from straight above the body. (med: the geometry is
read from a decompile that lost some stack slots)

Ours (`game/death.ctx`, called from `play::run`): the same sequence. The world keeps ticking with
`clock.speed` taken from the curve; the HUD goes away, the box opens (`msgbox::show_strref`), the fade
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
  and back (`ConvertDayIndexToDate` `0x004add50`);
- time of day (ms) = `hour × MinPerHour × 60,000 + minute × 60,000 + second × 1000 + ms`
  (`ConvertTimeToTimeOfDay` `0x004adcf0`; hour clamps to 23, minute to 59, second ≥ 60 gives 56 —
  a slip in the original). A game **minute is a real minute**: within an hour the minute runs
  0..MinPerHour−1 (`ConvertTimeOfDayToTime` `0x004add90`), seconds and ms are real.

### 7.2 Module time

`LoadModuleStart` reads `Mod_MinPerHour`, `Mod_DawnHour`, `Mod_DuskHour` (module bytes
`+0x1a0..+0x1a2`), then (high):

- **new game** (`bResetTime`, client flag `+0x33c` set by the new-game path): `Mod_StartYear`
  (default 1340), `Mod_StartMonth` (6), `Mod_StartDay` (1), `Mod_StartHour` (23),
  `Mod_StartMinute`, `Mod_StartSecond`, `Mod_StartMiliSec`, `Mod_Transition` (`+0x1b8`),
  `Mod_PauseDay`, `Mod_PauseTime`;
- **otherwise**: the calendar and the pause snapshot stored at the transition (5.3 step 1).

Then: `SetMinutesPerHour` (`0x004adba0`; 0 → 5), `SetCalendarTime` (`0x004ae3e0`), the world
timer's pause snapshot := (PauseDay, PauseTime), both exempt clocks := copies of the world timer,
module "last update" := now, and the initial day phase (7.4). Since the world timer is paused
throughout the load and unpausing resumes from the snapshot, **after a transition the time
continues exactly where it was**; the start fields only matter for a new game. (high for the code,
med for the consequence) Shipped IFOs: start year 1372 (or 0), month 6, day 1, hour 13, no
minute/second/pause fields; `Mod_MinPerHour` 2 in 113 of 117 modules (a 48-minute day), 0 or 1 in
the four Dantooine modules `danm14aa`–`danm14ad`, which also have dawn = dusk = 0; elsewhere dawn 6,
dusk 18.

### 7.3 Script routines

| Routine | Handler | Behaviour | Conf. |
|---|---|---|---|
| 16 `GetTimeHour` / 17 minute / 18 second / 19 millisecond | `0x0053e020`… → `GetCurrentHour` `0x004ae090` etc. | from the world timer: hour = `ms / 60,000 / MinPerHour`, minute = `(ms / 60,000) mod MinPerHour`, second = `(ms / 1000) mod 60` | high |
| 12 `SetTime(h, m, s, ms)` | `0x00543670` → `CWorldTimer::SetTime` `0x004ae260` | normalises (1000 ms, 60 s, 60 min carry upward; hours past 24 advance the date by whole days), and **only moves forward**: without such a carry, a time earlier than now advances the date by one day (28-day months, 12-month years); negative arguments are ignored | high |
| 405–408 `GetIsDay/Night/Dawn/Dusk` | `0x00539900`, `0x00539de0`, `0x005398c0`, `0x00539bd0` | the module's day phase `+0x1bc` = 1, 2, 3, 4 | high |
| 121–123 `RoundsToSeconds` etc. | `0x00544e50` | section 3 | high |

### 7.4 Day phases and lighting

`CSWSModule::UpdateTime` (`0x004c6210`, every module frame) computes the calendar and the hour and
the phase (high):

- dawn hour = dusk hour → always day (1);
- hour = dawn → dawn (3); hour = dusk → dusk (4);
- dawn < dusk: night (2) when hour < dawn or hour > dusk, else day;
- dawn > dusk: night when dusk ≤ hour ≤ dawn, else day.

It accumulates the ms spent in dawn or dusk at `+0x1b8`, stores year/month/day/hour at
`+0x1a8..+0x1b4`, and when any of phase, hour, day, month or year changed sends the client a
time message (`SendServerToPlayerModule_SetTime` `0x0056a5f0`, 3/3). The client
(`0x006528b0` → `CSWCModule::SetDayPhase` `0x00640640`) switches the area lighting
(`ApplySunLighting` `0x006058c0`, `ApplyMoonLighting` `0x006059c0`, sun or moon fog, ambient and
diffuse colours from the ARE). With `DayNightCycle` = 0 the area keeps one set chosen by `IsNight`;
with `DayNightCycle` = 1, dawn and dusk start a transition (`0x00606cf0`, `0x00606c50`) lasting one
game hour (`MinPerHour × 60` s). Only two shipped areas (stunt modules) set `DayNightCycle`. (med)

### 7.5 What the shipped data does

Probe of every module RIM (`kotor/re/` scratch script): 117 IFOs, `Mod_MinPerHour` 2 (113) / 0 (3,
read as 5) / 1 (1); dawn 6 and dusk 18 except four 0/0; start hour 13. ARE `DayNightCycle` 1 in two
areas, `IsNight` 0 everywhere. `Mod_OnHeartbeat` set in two modules (`k_pebo_mgheart`,
`k_ptat17af_heart`). In practice KOTOR has no visible day/night; the clock still runs and scripts
can read it. (high)

### 7.6 Saves

The module IFO saved in a game (`SaveModuleIFOStart` `0x004c7050`) holds the current
`Mod_StartYear..Mod_StartMiliSec`, `Mod_Transition`, `Mod_PauseDay`, `Mod_PauseTime` (the world
time), and the save's `AUTOSAVEPARAMS`/global struct (`0x004b28e0`) holds `TIME_YEAR`,
`TIME_MONTH`, `TIME_DAY`, `TIME_HOUR`, `TIME_MINUTE`, `TIME_SECOND`, `TIME_MILLISECOND`,
`TIME_PAUSEDAY`, `TIME_PAUSETIME` with `LOADMUSIC`, `STARTWAYPOINT` and `MOVIE1..6`. Loading a
save restores the time the same way as a transition (paused, resumed from the snapshot). The file
formats are party-items-saves.md's. (med)

## Open questions

- **Who queues the first AREA_TRANSITION event (26)?** Only the area's own phase-2 re-queue was
  found; the initial one may come through a payload built elsewhere (galaxy map, `0x006cf9d0`?).
- **The arrival handshake (5.5)** was stitched from the message handlers on both sides; the exact
  frame of each step (and so how many frames OnSpawn has before OnClientEnter) should be confirmed
  in a running game or by tracing the client handlers of 3/1, 10/1, 10/2 in full. The order of the
  scripts is what matters for a reimplementation, which needs no handshake.
- **Party members on arrival**: `0x00565b00` places them; whether each gets the area's OnEnter and
  in which order relative to the PC was not traced (party-items-saves.md / movement.md).
- New game and save-load paths through `PlayerLoginToModule` (`0x004b7470`, Login minors 1, 2,
  0xe, 0x11, 0x13) were only skimmed.
- The end-of-round auto-pause call site in `EndCombatRound` is hidden in a tail the decompiler did
  not show; the reason code is unknown. Auto-pause reasons 6 (`0x0062ef90`) and 0xb details.
- `+0x9d4` on creatures (in-combat vs. "busy"): perception and the 300 ms tick treat it as "in
  combat"; objects.md calls it party/dying state.
- Level-1 rule for doors (`0x00507220`): which string field gates it (probably a script or the
  `LinkedTo` tag) was not identified.
- The meaning of `+0x10054` (an 0x28-byte object recreated at unload, `0x0052b8e0`), and the
  `+0x100bc`/`+0x100c0` server flags.
- The object flag `+0x1f8` that gates both the movement pre-pass and the dirty-state push in
  `UpdateState` (cleared by the `CSWSObject` constructor; probably "active in an area", low).
- The client `+0x30` timer's purpose.
- Whether any rendering subsystem uses `CSWCModule::Render`'s interface-clock argument for effects
  that should keep animating during a pause (most read the global world delta).
- Large frame deltas: confirm per system (movement, animation, combat timers) whether a clamp
  exists downstream.
