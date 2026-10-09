# Conversations, dialogue cameras, barks and cutscenes in swkotor.exe

How the original engine runs a DLG conversation: how one starts (a click, a script, an
`ON_DIALOGUE` event), how the server-side dialogue object walks the entry/reply graph, who speaks
to whom, how long each line stays up, how voice-over, lip sync and the participants' animations
are driven, how the conversation camera frames each shot, and the lighter-weight speech paths
(bark bubbles, `SpeakString`, one-liners) plus the script hooks cutscenes use (fades, static and
animated cameras, video effects, movies). Addresses are for the Steam `swkotor.exe` after
SteamStub removal (see [README.md](README.md)). Every claim carries a confidence: **high** = read
in the code, **med** = role clear, detail inferred, **low** = plausible. The whole page was
rechecked claim by claim on 2026-10-07 against the exports rebuilt after the noreturn fix
([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check" rests on static
reading alone and is surprising enough to test before relying on it. Names are ours; proposals
for every address below are in `kotor/re/proposals/dialogue.tsv` (git-ignored, merged into
[names.tsv](names.tsv) by the lead).

The DLG file format is [../formats/gff-dialog.md](../formats/gff-dialog.md) (this page corrects
several of its *inferred* meanings, see §12), LIP is [../formats/lip.md](../formats/lip.md), the
GIT `CameraList` is in [modules.md](modules.md). Neighbouring pages, written in parallel:
[objects.md](objects.md) (object model, events, the action queue), actions.md (the action queue
and each action's handler: the DIALOGOBJECT action's movement part, use ranges, pause/resume
actions), gameloop.md (frame, timing, DelayCommand, pause), [gui.md](gui.md) (the dialogue panels'
controls, input codes, the fade panel as a widget), movement.md (camera modes outside
conversations, clicking objects, party following), rules.md (the plot-XP formula), combat.md
(`CutsceneAttack`/`CutsceneMove`), party-items-saves.md (the journal, party leader switching,
equipment), [app.md](app.md) (the movie player, sound modes). This page owns the conversation flow
and everything shown while a conversation runs.

## 1. The pieces

The engine is a client and a server in one process (README), and a conversation is split along
that line:

| Piece | Where | Role |
|---|---|---|
| `CSWSDialog` | server, 0x12c bytes, ctor `0x005a0e80`, vtable `0x0074a618`, held at the **owner**'s `CSWSObject+0x34` | the loaded DLG, the current node, participants, camera-angle cycle, end flag (high) |
| owner (`CSWSObject`) | server | the object that owns the conversation (always the non-player side, §2.5); its fields `+0x34..+0x74`, `+0x1f4`, `+0x214`, `+0x220` hold the node timer and the pending step (high) |
| `CGuiInGame` | client, `CClientExoApp::GetInGameGui` | the conversation panels (letterbox `+0x40`, computer `+0x44`, computercamera `+0x48`, current `+0x3c`), the current speaker/listener, AnimList, static cameras, lock lists, fades, VO stream (high) |
| `CSWCDialogCamera` | client, 0x9c bytes, ctor `0x006bb670`, vtable `0x00756ae8` | the framed conversation shot, installed as the module camera for the conversation (high) |

The server does the logic and calls the client directly (no network in KOTOR). Each frame the
client main loop (`0x00602eb0`) looks up the owner named by `CGuiInGame+0x188` and calls
`CSWSObject::UpdateDialog` (`0x004cd580`) on it; once the owner's "ended" flag (`+0x214`) is set
it deletes the dialogue object (`0x004cc330`). That per-frame call is the pump that advances
lines. (high)

Fields of the owner used by the conversation (all `CSWSObject`, high unless noted):

| Offset | Meaning |
|---|---|
| `+0x34` | `CSWSDialog*` (null when not owning a conversation) |
| `+0x38/+0x3c` | current node's end time (world day, ms) |
| `+0x40/+0x44` | current node's start time |
| `+0x48` / `+0x4c` | a step is pending / which: entry index, or −1 = "show the replies" |
| `+0x50` | conversation paused (`ActionPauseConversation`) |
| `+0x54` | id of the owner of the conversation this object takes part in (`OBJECT_INVALID` = none); set on the owner itself, the PC and every participant |
| `+0x5c` | current node's WaitFlags (with the engine's extra bits, §6) |
| `+0x1f4` | "skip this line" request from the player |
| `+0x214` | conversation ended, delete the dialogue next frame |
| `+0x220` | the VO was cut (skip / end) |

Creatures also keep: `+0x17c` last speaker (the initiator of the last `ON_DIALOGUE`), `+0x180`
private flag and `+0x184` DLG resref from that event, activity bit 4 of `+0x9fc` = "in a
conversation" (and bit 4 of the lock mask `+0xa00` = "keep it", set while paused). (high)

## 2. Starting a conversation

### 2.1 The paths

| Step | Address | What |
|---|---|---|
| player clicks an NPC | `0x005254c0` (input message case 8) | clears the controlled creature's queue (`PrepareForPlayerCommand(8)`), raises its AI level to 1 when it is 0, and queues action 0x18 DIALOGOBJECT on it (new group): {target, resref "", private 0, 1, range check on (0), `OBJECT_INVALID`} (high) |
| `ActionStartConversation` (204) | `0x0052d5b0` | queues the same action on OBJECT_SELF (§2.2) (high) |
| DIALOGOBJECT action | `CSWSObject::AIActionDialogObject` `0x0057a470` | walks into range, then sends `ON_DIALOGUE` to the target (§2.3) (high) |
| `ON_DIALOGUE` (script event 7) | creature `EventHandler` `0x004fece0` | records the initiator and runs ScriptDialogue, default `k_hen_dialogue01` (§2.4) (high) |
| `BeginConversation` (255) | `0x0052e9f0` | called by that script; picks owner and DLG and calls StartConversation (§2.5) (high) |
| StartConversation | `CSWSObject::StartConversation` `0x004cf490` | loads the DLG, builds `CSWSDialog`, picks the starting entry and runs it (§2.6) (high) |
| `SpeakOneLinerConversation` (417) | `0x00543f70` → `0x004cb220` | separate path: one line as chat text, no conversation (§10) (high) |

So a conversation always goes through the target's dialogue script: a click or
`ActionStartConversation` never opens the DLG directly. A creature whose ScriptDialogue does not
call `BeginConversation` (custom `OnDialogue` scripts do other things first) decides for itself.

### 2.2 `ActionStartConversation` (`0x0052d5b0`)

Order (high, from the disassembly):

1. Pop the target, the resref, `bPrivateConversation`, `nConversationType`,
   `bIgnoreStartRange`, the six ignore names and `bUseLeader`.
2. **`nConversationType` is read and thrown away**: the DLG's own `ConversationType` decides the
   panel (§2.6). **`bIgnoreStartRange` is overwritten with TRUE**: script-started conversations
   never walk to the target.
3. Each non-empty ignore name not already listed is added to `CGuiInGame`'s ignore list
   (`+0xb4c`, `0x00632300`): AnimList participants with those tags don't hold up a node while they
   are missing (§5.3), and StuntList participants with those tags don't hold up the scene (§2.7).
4. `CGuiInGame+0xbd8` = `bUseLeader` (the reply list is then spoken by the party leader instead
   of the main PC, §5.2).
5. The party leader's (party slot 0) client movement is stopped (`CancelServerActions`) and its
   actions are cleared (`ClearAllActions(TRUE)`), at once. Steps 3–5 happen even when step 6
   queues nothing.
6. Only if no conversation is pending (`CGuiInGame+0xb4` = 0), OBJECT_SELF is valid and
   commandable (`+0xe8`): raise its AI level to 1 if it is 0, set the pending flag (`+0xb4` = 1,
   `CGuiInGame::SetDialogPending` `0x0062ec60`) and append action 0x18 (new group) with
   parameters {target, resref, private, 1, 1, `OBJECT_INVALID`}.

### 2.3 The DIALOGOBJECT action (`0x0057a470`)

Action parameters: 0 target, 1 resref, 2 private, 3 "use-range test" (always 1 from the shipped
callers), 4 "skip the range test" (1 from scripts, 0 from clicks), 5 a creature id used by the
character-switch hand-off (`OBJECT_INVALID` normally). Per run (status codes as in objects.md:
2 done, 3 failed); every failure also clears the pending flag:

1. Fail if the actor is dead (slot 37), or if **every** client party member is knocked out
   (`GetIsDying` `0x004ef890`, hit points below 1) or has no server creature.
2. With parameter 5 set, go to the second half of step 6. Otherwise the target must exist, be
   commandable and not dead, else fail. The action keeps running (status 1) until the player's
   creature (`GetPlayerCreatureId`) exists and has a client object.
3. While the client is loading (`IsLoading` `0x005edad0`), player-paused (`0x005edc10`) or
   auto-paused (client `+0x384` bit 0, `0x005edef0`): put a copy of the action back at the head of
   the queue, done (it runs again next frame).
4. Set the pending flag. If the actor is a creature: drop its combat/Force modes
   (`ClearActivities(2)`, stealth stays) and leave any conversation it is in (`SetActivity(4,
   FALSE)`).
5. Creature actors only, unless parameter 4 is set: with parameter 3 set, the actor must be within
   its use range of the target + 1.1 m (`GetIsInUseRange(target, 1.0)`, which also wants a clear
   line, actions.md 1.4); with it clear, within 10 m (3D). Out of range: push a copy of this action
   at the head (with parameter 3 cleared when it was set, so the next pass applies the 10 m rule),
   then in front of it a running move-to-point (`AddMoveToPointActionToFront`, the node's group, the
   target's area and id, range = use range + 1.0) toward the point halfway between the actor and
   the target's use point (`GetUseRange`); done. (high)
6. **Character switch** (med): when the actor's client twin is a party member (`+0x3a4`) and the
   actor is not the player's creature, the target's `PartyInteract` (`+0x218`) is clear, the
   target has a DLG of its own (`GetDialogResRef` valid) and is not the player's creature, and
   the player's creature is a party member (`+0xa88`):
   - if the player's creature is in combat (`+0x4e0` with `+0xac0` = 1), fail;
   - else stop and clear the party leader (client party slot 0) and slots 1–2
     (`CancelServerActions`, `ClearAllActions(TRUE)`), put each of slots 1–2 that stands 30 m or
     more from the leader at its formation slot near the leader (a safe spot within 10 m),
     **fade to black over 0.75 s** (`StartGlobalFade`, mode 0), release input
     (`CExoInput::SetAcquired(0)`), mark `CGuiInGame+0xb98` ("fade the world in at the first
     line"); if the player's creature is knocked out, apply a RESURRECTION effect (type 4) to it
     and then set `+0xf0` (the effect only acts when `+0xf0` was already set, combat.md 8.2);
     push the DIALOGOBJECT, with parameter 5 = the leader's id, onto the **player's creature**,
     and fail this one.

   The pushed action, while the GUI fade panel is busy, puts itself back at the head and fails;
   once it is idle, the player's creature takes the leader's position, facing the target from
   there (the leader's facing when the target is gone), and the leader takes the player's
   creature's old position, client twins following; control returns to the player character
   (client `SetPartyLeader(−3)`, party-items-saves.md 3.5), `CGuiInGame+0xba4` remembers the old
   leader to give control back to after the conversation (`CancelPostDialogCharacterSwitch` clears
   it), input is re-acquired, and the action goes on to step 7 with the player's creature as the
   speaker. When the actor is a party member other than the player's creature and the target *is*
   the player's creature (with a party-member twin), there is no hand-off, but control switches
   to the player character (`SetPartyLeader(−3)`) before step 7.
7. Send script event 7 `ON_DIALOGUE` to the target, caller = the actor, through the AI master
   with no delay (`AddEventDeltaTime`, 0 ms), with ints {−1, −1, private, parameter 4} and the
   resref as string 0. Done.

### 2.4 `ON_DIALOGUE` on the target (`0x004fece0`, case 7)

The target stores: `+0x17c` = the caller (what `GetLastSpeaker` returns), `+0x198` = int 1 (the
listen-pattern number: −1 means "a conversation", what `GetListenPatternNumber` returns), `+0x184`
= the resref, `+0x180` = private; the server keeps the resref as "last conversation"
(`GetLastConversation`, server internal `+0x1b908`), sets a "dialogue event pending" flag
(`0x004af010`, `+0x1b910`) that `BeginConversation` checks, and keeps int 3 (parameter 4, "skip the
range test") at `+0x1b914` (`0x004af030`; read only by `PlayOneLiner`, §10, and cleared with the
pending flag). The target's matched-substring list (`+0x1a0`) is emptied and refilled from the
event's strings 1 to int 0 − 1 (int 0 is −1 here, so it stays empty). If ScriptDialogue
(`+0x268`) is empty or `"default"` it becomes `k_hen_dialogue01`; the script runs with OBJECT_SELF
= the target. Placeables and doors have their own `OnDialog` slots (objects.md). (high)

The same event type also comes from heard speech that matches a listen pattern
(`BroadcastSpeech` `0x004cd760`, §10.2); then int 1 is the pattern number instead of −1 and the
strings carry the matched substrings.

### 2.5 `BeginConversation` (`0x0052e9f0`)

`int BeginConversation(string sResRef = "", object oObjectToDialog = OBJECT_INVALID)` (high):

1. Proceed only if the dialogue-event flag is set or no conversation is pending, and OBJECT_SELF
   is valid; the flag is cleared either way. Otherwise (or when either side does not exist) clear
   the pending flag and return FALSE.
2. Self = OBJECT_SELF; other = `oObjectToDialog`, or self's `+0x17c` (the last speaker).
3. For each side that is a creature (other first): clear its actions unless it is the player's
   creature (`GetPlayerCreatureId`); remember its facing; when the player has an update record
   for it, set its animation to 10000 (stand) silently (animation dirty bit cleared, the record's
   animation set to 10000, so no update is sent).
4. Resref: the argument, else self's `+0x184` (from the event). Private: always self's `+0x180`.
5. **Owner choice**: the PC never owns a conversation. If the other is the PC, self owns it. If
   self is the PC, the other owns it. If self is a creature under the player's control (a party
   member, `+0xa88`) talking to a non-PC, the other owns it. Otherwise self owns it.
6. `StartConversation(owner, otherSide, resref, private)`. On success return TRUE. On failure,
   for each side that is a creature, drop its interact target (`SetInteractTarget(INVALID, 0)`)
   and restore its facing; clear the pending flag, return FALSE.

### 2.6 `StartConversation` (`0x004cf490`)

1. Reset the client's scene-ready and scene-loaded flags (client internal `+0x230` / `+0x234`,
   §2.7), even on the early return. If the owner already has a dialogue object, return 1 (and
   clear the pending flag if its last conversation ended, `+0x214`, and awaits deletion).
2. Clear the owner's node fields (`+0x38`..`+0x50` except `+0x4c`, `+0x60`..`+0x70` except
   `+0x6c`; `+0x74` = 1).
3. Resref = the argument, or the owner's virtual `GetDialogResRef` (slot 32: a creature's
   `Conversation` field in its stats, a placeable's or door's own field). Empty → return 0.
4. Open the DLG (resource type 2029, `"DLG "`); create `CSWSDialog` and load it
   (`LoadDialog` `0x005a2ae0`, §3). Failure → delete it, return 0. Dialogue `+0x90` = private.
5. Set the pending flag. If the camera is in free-look (mode 5, movement.md 2.5), leave it:
   main interface shown, `RestoreDefaultCamera`, input class 0.
6. Register the player: a 12-byte record {player, other side's id, gender of the player's
   creature} in the dialogue's player list (`+0x64`); dialogue `+0x7c` = the other side (called
   "the PC" below: it normally is), `+0x78` = gender (picks the male/female text variants). The
   other side's `+0x54` = owner; owner's `+0x54` = owner, its `+0x5c` = 0; `CGuiInGame+0x188` =
   owner. Each side that is a creature has its queue cleared (`PrepareForPlayerCommand(2)`:
   `ClearAllActions(TRUE)` when it has a client twin and its `+0x9f2` state is below 10) and sets
   activity bit 4 (`SetActivity(4, TRUE)`). The local player is always registered, so even a
   conversation a script starts between two NPCs shows its replies to the player (med).
7. `SetOwner` (`0x0059f430`): dialogue `+0x80` = owner, save the owner's AI level and raise it
   to at least 3 for the conversation.
8. Pick the starting entry (§4.1) and run it (`RunDialogEntry` `0x004cd460`), then close any
   open container panel (`CGuiInGame::CloseContainer`). If the run failed (−1: no entry, or a
   one-liner played as a bark; `RunDialogEntry` has already called `EndConversation` and set
   `+0x214`): if the world fade-in was being held (`+0xb98`), fade back in over 1 s now; clear
   the pending flag; return 0. Else clear the client's hostile-sighting latch (client internal
   `+0x324`, movement.md 7.1) and return 1.

The panel is chosen while loading: `ConversationType` 1 → the **computer** panel
(`computer.gui`, `ComputerType` passed for the Rakatan skin); anything else → the **letterbox**
panel (`dialog.gui`), and for those the party leaves stealth (`0x00563c60`). `ConversationType`
2 additionally sets dialogue `+0x110`, which only disables the one-liner rule (§4.1). (high)

### 2.7 Scene readiness

Until the client reports the scene ready, every node counts as still running (§4.5), so nothing
advances. The node-running test calls `GetIsDialogSceneReady` (`0x005f3070`) every time, which:

1. takes the owner and the PC out of stealth if they are creatures (`SetActivity(1, FALSE)`, on
   every call, computer conversations included);
2. answers "not ready" while the game is player-paused or auto-paused (client `+0x384` bit 0),
   even after the scene was ready;
3. answers "ready" once the scene-ready flag (client internal `+0x230`) is set;
4. otherwise waits until the module has been running for more than 1 s (client internal
   `+0x228` / `+0x22c`, set by `0x005f3030` when a load finishes); after that first wait
   `+0x22c` is moved back 2 s, so later calls are not throttled;
5. requires client objects for the owner, the PC and every `StuntList` participant except tag
   participants on the ignore list (§2.2 step 3);
6. unless the scene-loaded flag (client internal `+0x234`) is already set, sends the scene setup
   (`SendSceneSetup` `0x005a0080` → `SetDialogScene` `0x0062e020`): stunt models applied to their
   participants; only when that succeeds are the DLG's `CameraModel` loaded (once per
   conversation, `CGuiInGame+0xb28` = 1) and `AmbientTrack` started as music on its own stream
   (`0x0062a8b0`, `CGuiInGame+0xbbc`; stopped with a 0.5 s fade at the end), and the scene-loaded
   flag set. A failed setup is retried on the next check. Once the scene is loaded, the
   scene-ready flag is set and the answer is "ready".

Stunt participant names: `PLAYER` = the PC (dialogue `+0x7c`), `OWNER` or empty = the owner, else
the object with that tag nearest to the owner (no range limit). (high)

`CGuiInGame::ApplyStuntModels` (`0x0062c620`, called by `SetDialogScene` `0x0062e020`) does the swap: for each
`StuntList` participant with a non-empty model it takes the client creature and gives the stunt resref as the
model to its part 0xff and then to its part 0xfe (the same string to both, asm `0x0062c682`..`0x0062c6c1`;
which parts these are, body and head, is med); a participant without part 0xff makes the whole setup fail, to be
retried on the next check (high). Stunt models such as `m02af_c10_char01` are
full skeletons (`cutscenedummy` > `rootdummy` > ..., `S_Male02` as supermodel) whose `cutNNNw` animations carry
`cutscenedummy` through the area in area coordinates (the apartment's at about x 92, y 144). Neither the stunt
model nor its supermodels (`S_Male02`, `S_Male01`) has a `camerahook` node (`S_Male01` has only a `Camera03`
under `head_g`); an ordinary body model's `camerahook` is a child of the model's root. The dialogue camera
does not touch the creatures' objects, and only `CSWCChaseCamera::Update` calls `ResolveCollision`
(`0x0063b050`), so the chase camera's obstruction test does not apply to a dialogue shot (`SetShot`'s own
rays do, 9.2). Where the stunt models are put back, and what `SetShot` takes as a stunt body's eye once the
scene animation is over, was not traced (ours: the player's talk and listen loops play from the first ordinary
line on, and a stunt body's eye is its head hook).

## 3. The loaded dialogue (`LoadDialog` `0x005a2ae0`)

Top-level fields read: `CameraModel` (`+0x50`), `DelayEntry` (kept as the default node delay),
`DelayReply` (its value is **ignored**: replies also use `DelayEntry`; but the field must be
present, see below), `EndConversation` (`+0x1c`),
`EndConverAbort` (`+0x2c`), `Skippable` (default 1, `+0x3c`), `ConversationType`, `ComputerType`,
`AmbientTrack` (`+0xfc`), `UnequipItems` (`+0x40`), `UnequipHItem` (`+0x44`), `AnimatedCut` (→
`CGuiInGame+0xc0`), `OldHitCheck` (→ `CGuiInGame+0xc4`), then `ReplyList` (count `+0xc`,
0xb4-byte nodes at `+0x10`), `EntryList` (count `+0x4`, 0xb0-byte nodes at `+0x8`),
`StartingList` (count `+0x14`, 0x14-byte links at `+0x18`), `StuntList` (`Participant`,
`StuntModel`; count `+0x48`, 0x18-byte records at `+0x4c`). (high)

The load's success flag is **overwritten** by each "required" read, not accumulated: the last one
before each check decides. In practice a missing (or non-DWORD) `DelayReply` fails the whole load;
so does a node whose last required read misses (in read order: `Text`, each AnimList
`Participant` and `Animation`, then each link's `Active` and `Index`), and any link `Index` out of
range. All shipped DLGs have these fields; all other fields are optional. With `bFull` = 0 (`SpeakOneLinerConversation`) the reply list and all
links are skipped (reply count 0). (high)

Not read at all: `IsChild`, `Comment`, `LinkComment`, `VO_ID`, `NumWords`. A link to a node
"shown elsewhere" is just a link. (high)

Per node (`ReadNode` `0x0059f5f0`, camera part `ReadNodeCamera` `0x0059eaa0`), node offsets:

| Offset | Field | Notes |
|---|---|---|
| `+0x00` | `Speaker` | tag (CExoString) |
| `+0x08` | `Text` | CExoLocString |
| `+0x10` | `Script` | |
| `+0x20` | `WaitFlags` | plus engine bits 2 and 0x10 (below) |
| `+0x24` | `Delay` | |
| `+0x28` | "text timer" marker | −1 by default, 0 = "no sound, but WaitFlags set" |
| `+0x2c` | "not a voice line" | 1 when the sound came from `Sound` or there is no sound |
| `+0x34` | the node's sound | `Sound` if set, else `VO_ResRef` |
| `+0x4c/+0x54` | `Quest` / `QuestEntry` | |
| `+0x58/+0x5c` | `PlotIndex` / `PlotXPPercentage` | |
| `+0x60/+0x64` | `AnimList` | 0xc-byte records {Participant, Animation (WORD)} |
| `+0x68..+0x7c` | `FadeType`, `FadeColor`, `FadeLength` (`+0x78`), `FadeDelay` (`+0x7c`) | |
| `+0x80` | `SoundExists` | default 0x80 when absent |
| `+0x84` | `Listener` | |
| `+0x8c..+0xa4` | `CameraAngle`, `CameraID`, `CamHeightOffset`, `TarHeightOffset`, `CameraAnimation`, `CamFieldOfView`, `CamVidEffect` | in that order: `+0x8c`, `+0x90`, `+0x94`, `+0x98`, `+0x9c` (WORD), `+0xa0`, `+0xa4` |
| `+0xa8/+0xac` | link count / links | entry→reply links 0x18 bytes {Active, Index, DisplayInactive}; reply→entry links 0x14 bytes {Active, Index} |

Load-time rules (high):

- **Sound beats VO**: if `Sound` is set it becomes the node's sound and the node is marked "not a
  voice line"; else `VO_ResRef` is used; with neither, `SoundExists` is forced to 0.
- **Delay −1** (0xFFFFFFFF, the default): with a sound, `Delay` becomes `DelayEntry` (always 0)
  and a WaitFlags of 0 becomes **2** ("wait for the voice"); with no sound but WaitFlags set, the
  marker `+0x28` = 0 and `Delay` = `DelayEntry`; with neither, nothing changes (the text timer
  applies, §6). **Any other Delay** sets WaitFlags bit **0x10** ("explicit delay"); a node with
  no `Delay` field reads 0, i.e. an explicit delay of 0 (every shipped node has the field).
- `FadeType` 1 or 2 force `FadeLength` 0; `FadeType` 0 (or no `FadeType` field) zeroes all fade
  fields.
- `CamFieldOfView` missing or ≤ 0 → −1. `CameraID` → −1 unless `CameraAngle` is 6.
  `CamVidEffect` defaults to −1.
- A link whose `Index` is beyond the target list makes the whole load fail. All three link kinds
  (`StartingList`, entry→reply, reply→entry) accept `Index` = the target count, an off-by-one in
  the check (`0x0059ec10` and the two loops in `LoadDialog`); no shipped DLG has such a link.

## 4. The flow

### 4.1 The starting entry (`GetStartingEntry` `0x005a3640`)

Walk `StartingList` in order and take the first link where (a) the entry's `Speaker` is empty, or
equals the owner's tag (case-insensitive), or can be resolved (§5.1), and (b) the link's `Active`
script passes (§4.2). The speaker test comes first: a link whose speaker is unavailable is
skipped without running its `Active`. None → −1: StartConversation fails and, the end flag not
being set, only `EndConverAbort` runs (§4.9). (high)

**One-liners become barks.** Unless `ConversationType` is 2 (dialogue `+0x110`), if the chosen
entry has no reply links, or exactly one whose reply itself links to no entries (that reply's
`Active` is not tested), the engine does not open a conversation. In this order: it plays the
entry as a bark (`PlayOneLiner` `0x005a1050`, §10.1), which, when the text is not empty and the
PC and owner exist, sets the end flag and ends the conversation normally for the owner only
(`EndConversation(owner, bOwnerOnly = 1)`: DLG `EndConversation` script, then the owner's own
end-of-dialogue script); then it runs the entry's `Script`, then that single reply's `Script`;
then it empties the player list and returns −1. So the end scripts run **before** the line's
own scripts. That is how ambient NPCs answer a click with a floating line instead of the
letterbox. Because StartConversation then fails on the −1 (`RunDialogEntry` → `RunEntry` index
check), `EndConversation` is called a second time and, the normal end having been done
(`+0x10c` set), runs **`EndConverAbort` as well**: a bark runs both end scripts (shipped DLGs
mostly name the same script in both). A bark with an empty text skips the normal end, so only
`EndConverAbort` runs. `BeginConversation` returns FALSE. (high)

### 4.2 Conditions and scripts

- `Active` (`CheckCondition` `0x0059ec90`): empty → TRUE; otherwise run the script with
  **OBJECT_SELF = the owner**; TRUE only if it ran and returned an int ≠ 0. A missing script
  counts as FALSE (`RunScript` fails). (high)
- Node `Script`, `EndConversation`, `EndConverAbort` (`0x0059ed70`): run with OBJECT_SELF = the
  owner when not empty. (high)
- The link's `Active` is the only condition; KOTOR has no `Active2`/`Not` fields (none read).

### 4.3 Running an entry (`RunEntry` `0x005a4010`)

`RunDialogEntry` (`0x004cd460`) first defers when the conversation is paused or the current node
is still running (it stores the entry as pending, owner `+0x48` = 1, `+0x4c` = entry, §4.5); the
entry −1 is never deferred. It then clears the skip request (owner `+0x1f4`) and calls
`RunEntry`; a failure (any status but 10) ends the conversation with `EndConversation(owner, 0)`
(normal end if the end flag is set, else `EndConverAbort`) and marks the owner's dialogue for
deletion (`+0x214`). `RunEntry`, in this order (high):

1. Entry index out of range → fail (the conversation ends).
2. **Speaker**: empty or the owner's tag → the owner; else resolve the tag (§5.1); not available
   → fail (the conversation ends, abort path).
3. **Listener**: empty → none (the client picks one, §5.2); `OWNER` → owner; `PLAYER` → the
   player's creature (`GetPlayerCreatureId`); else resolve the tag (none if not found).
   `OWNER`/`PLAYER` compare case-insensitively.
4. Clear "replies sent" (`+0x68`). For each player: send the entry to the client
   (`SendEntry` `0x005a13d0`, §4.4). If a participant isn't ready yet (status 10), stop here;
   `RunDialogEntry` stores the entry as pending and the pump retries it (§4.5). Then apply
   `Quest`/`QuestEntry` for that player (§4.8).
5. Award `PlotIndex`/`PlotXPPercentage` (§4.8).
6. Start the voice: `CGuiInGame::PlayDialogVoice` (`0x0062e1d0`, §7) with the speaker and the
   node's sound.
7. Decide "has VO": normally by probing the file (§7: `streamwaves` path, `.mp3` then `.wav`);
   when client byte `+0x498` has bit 8 (`0x005ee0d0(8)`; the byte is a copy of the resource manager's
   module-loader status bits, `resman+0x5c`, made by `CSWSModule::AddModuleResources`, and bit 8 means
   the module was mounted from `<m>_s.rim`, which every stock PC module is) by `SoundExists` bit 0
   instead. So on a normal install the file is not probed and the forced-text path below never runs
   (med: needs a runtime check). With sound disabled, "has VO" stays as returned by the play
   call. Outside that client mode, when "has VO" is false, the node is a voice line (`+0x2c` = 0),
   the Subtitles option is off and the dialogue panel is the current one, force the text on for
   this line (`CGuiInGame+0xbb0` = 1, refreshed at once when `+0xbb4` is set).
8. Remember the speaker (`+0x94`; only when a player is registered, always in single player).
9. **Node duration** (§6) → the owner's end time (`SetDialogNodeTimer` `0x004cb1a0`).
10. Owner `+0x5c` = the node's WaitFlags.
11. Run the entry's `Script` (so scripts run when the line is **shown**, after the client got
    it).
12. Current entry (`+0x70`) = this one; then `RunDialogReplies` (`0x004cd500`): if the node is
    already over and not paused, send the replies now (clearing the skip request), else mark
    "pending: replies" (`+0x4c` = −1). A failed send ends the conversation like a failed entry.

### 4.4 What the client gets for a line (`SendEntry` `0x005a13d0` → `ShowDialogEntry` `0x00631d80`)

Server side (high):

- AnimList participants: `PLAYER` → the PC (if a player is registered), `OWNER` → the owner,
  `NPC1` / `NPC2` → party slots 1 / 2, else the nearest object with the tag in the owner's area
  (no range limit). These four keywords are compared **case-sensitively** here. Missing → logged
  ("Error: dialogue can't find object '%s'!", discarded) and its slot is sent as no object with
  animation 0.
- Readiness, in this order: the listener (when there is one), the speaker and the PC must each
  have a server and a client object; if one doesn't, status 10 and retry, **with no time limit**.
  Then every AnimList participant resolved by tag and not on the ignore list
  (`GetIsDialogIgnoreName` `0x0062f840`) must have both too; the first that doesn't starts a
  **1500 ms** countdown (`+0x120`, charged with the world time elapsed since the previous call,
  stamp `+0x124/+0x128`) and gives status 10; once the countdown runs out the participants are
  taken as ready and the line goes ahead. The countdown is not reset when the participants turn up
  in time, and the next wait is charged with all the time since the last stamp, so a later wait
  usually expires at once (med, needs a runtime check).
- `CameraAngle` 0 is resolved (§9.1) and written back into the entry node itself, so a replayed
  entry keeps the angle it got the first time. Unequip lists are applied (§8.3) to the speaker,
  listener, PC and every AnimList participant.
- Sent: the text in the PC's language/gender (`0x0059f320`), owner, speaker, listener, PC, the
  AnimList, `CameraAngle`, `CameraID`, `CamHeightOffset`, `TarHeightOffset`, `WaitFlags`,
  `CameraAnimation`, `CamFieldOfView`, `CamVidEffect`, the fade fields, and a "show the text even
  without subtitles" flag = (not a voice line) or (sound disabled) or (`SoundExists` bit 1) or
  (not `SoundExists` bit 0).

Client side, `ShowDialogEntry` (high unless noted):

1. If the world fade-in is held (`+0xb98`, from the character switch or
   `HoldWorldFadeInForDialog`): clear it and **fade in from black over 1.0 s**.
2. Store the AnimList; parse tokens (`<FullName>`, `<CUSTOMnn>` …) with the PC as the token
   object (`CTlkTable::ParseStr`); set the message text.
3. Subtitles: with the Subtitles option off and sound on, the text is shown only when the flag
   above says so (`+0xbb0`); in the computer panel or with sound off it is always shown. In an
   `AnimatedCut` DLG with sound on, `+0xbb0` is left as it was. With Subtitles on it is not
   touched here (the text shows anyway).
4. Speaker/listener bookkeeping (§5.2), animations and facing (§8).
5. Fade (§9.6), then the camera (§9): in the conversation panel the animated camera is tried
   first, else `SetDialogCamera`; in the computer panel only angle 6 (static camera) does
   anything.

### 4.5 The pump: `UpdateDialog` (`0x004cd580`) and the node-running test (`0x004cd2d0`)

Every frame, for the owner (only while its conversation id `+0x54` is its own id): start a
pending lip-sync once its VO is playing (§7); freeze hostiles (§4.9); then, if not paused: if the
node is over and a step is pending (`+0x48`): if this is not an `AnimatedCut` DLG and the VO was
cut (`+0x220`) while the stream still plays, wait; else clear both flags and run the pending step
(`+0x4c`: an entry, or −1 for the replies). Otherwise (node still running, or nothing pending), if
the dialogue's "ending" flag (`+0x60`) is set and the VO has stopped, leave the conversation.
(high)

**A node is still running** (`GetIsDialogNodeRunning`) while any of these hold (high):

1. the scene is not ready (§2.7);
2. a skip was requested (`+0x1f4`) on a `Skippable` DLG → instead: stop the VO, mark it cut,
   set the end time to now + 1 ms, and report **not** running;
3. WaitFlags bit **2** and the dialogue VO is still playing;
4. WaitFlags bit **4** and an AnimList participant still plays a dialogue animation (§8.1);
5. WaitFlags bit **1** and the camera model's animation is still playing (§9.4);
6. WaitFlags bit **8** and the dialogue fade (`CGuiInGame+0x68`) is still running;
7. none of the above and world time < the node's end time.

There is no fixed pause between lines: the next step runs on the first frame after the node is
over.

**Skipping** a line: while an entry plays, the dialogue panel turns the accept events (0x27
click/Enter, 0x2d gamepad accept) and the left-press event 0x1f9 into a skip request
(`CServerExoApp::RequestDialogSkip` `0x004ae970` → owner `+0x1f4` = 1) (`CSWGuiDialog::
HandleInputEvent` `0x006a7230`; see gui.md for the event codes). The gate is panel `+0x1df8` bit 1
set and bit 2 clear; with bit 1 clear, 0x27/0x2d accept the highlighted reply instead.
Non-`Skippable` DLGs ignore the request. It is cleared whenever the next entry runs or the
replies are sent (`RunDialogEntry`, `RunDialogReplies`). (high for the effect, med for what the
panel state bits mean)

### 4.6 Replies (`SendReplies` `0x005a3820`, `SendRepliesToPlayer` `0x005a1c00`)

For the current entry (high):

1. For each link in order: run `Active` (OBJECT_SELF = owner). Passing replies are listed in link
   order. Failing ones are dropped, unless the link has `DisplayInactive` = 1, in which case they
   are appended after the passing ones, in **reverse** link order (shown but not selectable; no
   shipped DLG uses the field).
2. **Error rule** (`SendRepliesToPlayer`): if the list mixes empty-text and non-empty-text
   replies (texts in the player's language and gender), the conversation is aborted
   (`EndConverAbort`, via `RunDialogReplies`) with "CONVERSATION ERROR: Last Conversation Node
   Contains Either an END NODE or CONTINUE NODE. Please contact a Designer!"
   (`CGuiInGame+0xb14/+0xb18`). Six shipped DLGs contain such an entry.
3. No passing reply, or exactly one that links to no entries → set the dialogue's **end flag**
   (`+0x6c`) (the conversation will end normally after this).
4. With no player registered the first passing reply is picked at once, with the reply timer (a
   multiplayer leftover: StartConversation always registers the local player).
5. Otherwise each reply's text (gendered), listener, AnimList, `WaitFlags`, camera and fade fields
   and its link index go to the client. `CameraAngle` 0 is resolved on a copy (§9.1: the first
   reply list of the conversation gets 2, later lists take one cycle value shared by all their
   replies). The listener resolves `OWNER` and tags, but **`PLAYER` is dropped** (sent as no
   listener: that branch never stores the id, `0x005a20c5`); 6 shipped replies name `PLAYER`.
   AnimList keywords resolve as for entries (§4.4), with no readiness wait. Unequip lists are
   applied to every reply's listener and AnimList participants. Then `0x00634340` stores the
   replies on the GUI (token-parsing the non-empty texts) and calls `CGuiInGame::
   SetDialogReplies` (`0x006340e0`). With **zero** passing replies the client gets a single
   empty placeholder (link −1).
6. Dialogue `+0x68` = 1 (replies out), `+0x74` = −1 (nothing chosen).

Client (`SetDialogReplies`, high):

- **A single empty reply** (the "[continue]" link, and the placeholder above) is selected
  automatically without input (pending-reply state `+0xc8..+0xd4` set with "clicked" = 0, then
  `SelectDialogReply`): the conversation flows on as soon as the entry is over.
- Otherwise the list is shown and input enabled. Events 0xfe..0x106 pick reply n − 0xfe
  directly (presumably the number keys 1–9, med); up/down and accept select one (`0x006a7230`).
- While the list is up the shot shows the PC (or the party leader with `bUseLeader`, or when the
  player is not controlling the PC) speaking to the last speaker, using **reply 0's** camera
  fields (conversation panel only).

### 4.7 Choosing a reply (`HandleReply` `0x005a03c0`)

`SelectDialogReply` (`0x006339c0`, also called every frame from the client main loop while a
selection is pending) first waits until the reply's listener (or, with none, the last speaker),
the PC and every AnimList participant of the reply have client objects; an AnimList slot that
resolved to nothing would hold it indefinitely (med, needs a runtime check). Then the reply text
replaces the message, and:

- A **clicked** reply: its AnimList plays (not in an `AnimatedCut` DLG), and `HandleReply` runs
  with "no reply timer", so the next NPC line follows immediately. The camera is not changed.
  (high)
- An **auto-selected** reply (single empty one) goes through `SpeakDialogReply` (`0x00633660`).
  Its block that makes the PC the speaker, resets and starts the reply's AnimList and applies the
  reply's camera (animated, framed or static) is gated on its second argument, which the
  auto-select path always passes as 0 ("text not empty", `0x006341c6`), so for these replies only
  the reply's **fade** applies; the AnimList is copied into the client's slots but not started.
  Then `HandleReply` runs **with** the reply timer, so the reply's own `WaitFlags` (§6, reply
  table) hold the scene; an explicit reply `Delay` does not (§6). That is how cutscene DLGs chain
  beats through empty replies. (high for the code path; med for the visible effect that a
  continue-reply's `CameraAngle`/`CameraAnimation`/AnimList never show, which needs a runtime
  check: 210 shipped empty replies have a non-zero `CameraAngle`, 5 a `CameraAnimation`, 18 an
  AnimList.)

`HandleReply` order (high):

1. Ignore stale selections (not for the current entry, or a reply already chosen), and
   selections from a player not in the conversation. An abort (`bAbort`, index −3 in
   `SpeakDialogReply`) instead
   puts a creature PC's activity bit 4 off, or makes a non-creature leave the conversation.
2. Link index out of range or the PC gone → fail without setting the end flag (abort path,
   `EndConverAbort`).
3. `+0x74` = link; for each player: apply the reply's `Quest`/`QuestEntry`; award its plot XP.
   `+0x98` = the PC.
4. Unless "no reply timer": node duration from the reply (§6, reply table: the test is WaitFlags
   bit 2); owner `+0x5c` = the reply's WaitFlags (0 in an `AnimatedCut` DLG).
5. Run the reply's `Script`.
6. Take the first of the reply's entry links whose entry speaker is available (§5.1) and whose
   `Active` passes, and run that entry (deferred until the reply's node is over).
7. None → end flag and "ending" flag; return failure, which ends the conversation **normally**
   (`HandleDialogReply` `0x004cb480` → `EndConversation(owner, 0)`, then `+0x214` = 1).

### 4.8 Journal and plot XP

- `Quest`/`QuestEntry` (`UpdateJournal` `0x0059ef00`, high): with a non-empty `Quest`: if the
  party journal's current state id for that quest tag (0 for a quest not in the journal yet, so
  `QuestEntry` 0 never adds a quest) is **lower** than `QuestEntry` (signed), set the date and
  time (current world time) and then the state (`0x005c5a40`, which reloads the quest's title,
  text, priority, `PlotIndex` and planet from `global.jrl` and marks the quest "new",
  journal.md). The journal never moves backwards from a DLG. Then the quest's experience
  (record `+0x38`, filled by `0x005c5a40` as plot.2da `XP` of the category's `PlotIndex` ×
  the entry's `XP_Percentage`, + 0.5, truncated) goes to the party when non-zero
  (`CSWPartyTable::AddExperience(xp, 1)`) with the status-summary XP event (kind 2,
  `CGuiInGame::AddStatusSummaryEvent` `0x0062eeb0`). The code then repeats the test for each
  other member of the PC's faction, but the journal is the party's single one (`0x004edb00`),
  already raised, so that loop never changes anything (and never awards XP). Journal storage is
  party-items-saves.md.
- `PlotIndex`/`PlotXPPercentage` (`AwardPlotXP` `0x0059f3c0`, high): when `PlotIndex` ≠ −1 and
  the percentage > 0, call `CSWPartyTable::GivePlotXPByRow` (`0x005666e0`) with the plot index
  and percent = ceil(`PlotXPPercentage` × 100): XP = ceil(plot.2da `XP` of that row × percent ×
  0.01f), and when > 0 `AddExperience(xp, 1)` plus the XP event (kind 2) (rules.md 4.2).
  `AddExperience`'s 1 is bFeedback: the player creature gets feedback 0x8f
  (`FormatFeedbackMessage` `0x005fcd10` → dialog.tlk 42438 "Experience Points (XP) Received:
  <CUSTOM0>", the whole amount) in the message log. GivePlotXP (`0x00566600`) and
  GiveXPToCreature (`0x0053e750`, the kind-2 event only for a player-controlled target) do the
  same; kill XP (`AwardKillXP` `0x004fb1e0`) passes 0 and has its own "killed" line. (high)
  Ours: `notices::xp_gained` (the feedback line and the HUD's `LBL_PLOTXP` icon for the kind-2
  event; the status-summary panel itself is not made).

Both happen when the node is shown (entries: the journal for each player after the entry is
sent, the plot XP once) or chosen (replies: both inside the per-player loop), before the node's
voice and script.

### 4.9 Ending

`EndConversation` (`0x005a0a40`, high):

- **Normal end** (end flag set: the last entry had no usable replies, or the chosen reply led
  nowhere): run the DLG's `EndConversation` script (once), then run the end-of-dialogue script
  of **every creature** (`ScriptEndDialogue` `+0x298`, `0x004ef910`) and **every placeable**
  (`OnEndDialogue` `+0x30c`, `0x00585460`) in the owner's area. (After a one-liner, which sets
  the end flag itself: the DLG's end script and only the owner's.)
- **Abort** (anything else, or any later call once the normal end has run, `+0x10c`): run only
  `EndConverAbort`.

The callers that end a conversation from its own flow (`HandleDialogReply` `0x004cb480`,
`RunDialogEntry` `0x004cd460`, `RunDialogReplies` `0x004cd500`) then zero the owner's node timer
(`+0x38/+0x3c`) and pending flag (`+0x48`) and set the owner's `+0x214`; the dialogue itself is
destroyed by `DeleteDialog` (`0x004cc330`) in client step 18 right after `UpdateDialog`
(gameloop.md 1.2): in the same step when the end came from `UpdateDialog` (an entry with no
replies), on the **next** frame when it came from a reply chosen in step 19. When the owner itself
leaves (`LeaveConversation` `0x004cb4f0`) the dialogue is destroyed at once. Destroying it runs
`ClearDialog` (`0x005a27b0`): the owner's AI level is restored and its dialogue voice stopped,
the owner, the players and every cached participant are released (`+0x54` = invalid, activity
bit 4 cleared), and the dialogue panel closes (`0x006332b0`, per player).

**The ending flag after a dead-end reply** (med, static reading; needs a runtime check): a reply
that leads nowhere also sets the dialogue's "ending" flag `+0x60` (§4.7). On the next frame,
before `DeleteDialog`, `UpdateDialog` still finds the owner in its own conversation (`+0x54` is
only cleared by `ClearDialog`), sees `+0x60` and, when no dialogue voice is playing, calls
`LeaveConversation`, which calls `EndConversation` a second time: the normal end has already run,
so **`EndConverAbort` runs too**, and the dialogue is destroyed there. With a voice still playing
it is simply deleted. All 74 shipped DLGs that set `EndConverAbort` set it to their
`EndConversation` script, so by this reading that script runs twice after such an ending.

**What ends a conversation early (abort path)** (high unless noted):

- a node's speaker is not available (§5.1), or an entry/link index is bad;
- the owner, the PC or a player participant leaves: activity bit 4 cleared, which happens when
  that creature starts casting a power, counterspells, attacks (`ClearActivities` kinds 1 and 4,
  actions.md), starts another conversation, or a script/feature clears it (`SetActivity(4,
  FALSE)` → `LeaveConversation`; on a participant this asks the owner's
  `RemoveDialogParticipant` `0x004cd660`, which ends the conversation only for the last player;
  a tagged non-player participant that leaves is just released);
- the panel is closed with the abort code (−3 → `HandleReply` with abort set, which clears the
  PC's bit 4) (med: which key produces −3 was not traced);
- `ResetDialogState` (749) just clears the pending flag (does not end the owner's dialogue).

Moving, picking up items, equipping and other kind-2/8 actions do **not** end a conversation
(`ClearActivities` touches bit 4 only for kinds 1 and 4), and apart from the participant check
(§5.1) nothing tests distance once it has started.

**Hostiles freeze** (`FreezeHostiles` `0x005a0940`, high): every frame of a conversation (paused
or not), every creature in the current area that is not under the player's control (`+0xa88`)
and whose reputation toward the player's creature is ≤ 10 (hostile) has its actions cleared and
its movement stopped. `ClearAllActions` does nothing on a non-commandable creature (actions.md),
so a creature made non-commandable is not frozen.

It is nothing but that per-frame `ClearAllActions(1)` (plus the client creature's
`CancelServerActions`): no suspended queue, no flag on the creature, nothing to undo. It runs from
`UpdateDialog` (4.5), which returns before it unless the owner's `+0x54` names the owner itself,
so it stops once the dialogue is destroyed (above). A conversation that ends on an entry is
destroyed in the same client step, so the freeze has already stopped by the next server update.
One whose last reply leads nowhere ends in client step 19 (`SelectDialogReply` →
`HandleDialogReply` → `HandleReply`, the reply's script among it, then `EndConversation`), the
server update of that frame delivers what the script ordered (`AssignCommand` events), and the
next frame's step 18 still runs `UpdateDialog`, freeze included, before the dialogue is deleted.
So by static reading one more freeze clears what the last reply's script ordered of a creature
that is hostile by then: `k_pkas_wraidattk` assigns the Great Beast a run to `kas25_wp_wraid3`
and a combat round and turns it hostile (`ChangeToStandardFaction` 1), so its run would be
cleared (med, needs a runtime check). An order given by an *entry* script, or by a reply that
leads on to another entry, is cleared on the next frame.

**Action queues**: starting a conversation clears the actions of the party leader
(`ActionStartConversation`) and of both sides (`BeginConversation`, except the creature the
player controls); a tagged participant that joins (§5.1) is cleared only if it is the player's
creature. NPC scripts in node `Script`s commonly queue actions on participants; those run
normally during the conversation.

### 4.10 Pause and resume

- `ActionPauseConversation` (205, `0x0052d330`) acts at once (nothing is queued): if OBJECT_SELF
  is commandable and alive, set its `+0x50` (paused) and lock activity bit 4 (`+0xa00` bit 4) so
  the actions it performs meanwhile don't end the conversation (a dead or dying object gets
  virtual slot `+0xc0(INVALID)` instead). (high)
- `ActionResumeConversation` (206, `0x0052d520`) queues action 0x20 (`0x0057b320`): clear `+0x50`
  and the lock, drop activity modes (`ClearActivities(2)`) and stealth (`SetActivity(1, FALSE)`).
  (high)

While paused, no pending step runs: the current line stays (or the replies don't appear) until
the resume action runs; the hostile freeze keeps running. The owner must be OBJECT_SELF for this
to matter: node scripts run with OBJECT_SELF = the owner, and the shipped pause scripts
(`k_pkas_pause3sec`, `k_pman_pause2sec`, `UT_ActionPauseConversation` in `k_inc_utility`) pause
and `DelayCommand` the resume on OBJECT_SELF.

## 5. Speakers, listeners, participants

### 5.1 Finding an object by tag (`GetParticipant` `0x0059fc30`)

Used for `Speaker` and `Listener` tags (high):

1. Look in the conversation's cache of tag → id pairs (filled as tags are resolved, `+0x84`,
   count `+0x88`; the cache match is exact, case-sensitive).
2. Else: the owner's own tag → the owner; otherwise the **nearest object with that tag in the
   owner's area within 1000 m** (`GetNearestObjectByTag` `0x004cb5c0`, case-insensitive), and
   cache the answer (even "not found").
3. Accept it only if it is in the owner's area and within 1000 m of the owner (squared distance
   ≤ 10⁶), and it is not taking part in another conversation (`+0x54` names an owner whose own
   `+0x54` matches). A stale `+0x54` is cleared.
4. A free object **joins** this conversation (`+0x54` = owner; a creature sets activity bit 4,
   and the player's own creature also has its actions cleared, `PrepareForPlayerCommand(2)`; no
   activity modes are dropped). An object that has moved out of range or area is refused, and
   released if it was in this conversation.

`GetNearestObjectByTag` quirk: the first match must be within the range (squared distance ≤
range²), but after it the threshold becomes that match's plain distance *d* and a later candidate
is taken only if its *squared* distance is ≤ *d*, i.e. within √*d* m. So with several objects
sharing a tag the pick is usually the first match in the area's object order, not the nearest
(reproduce if exactness matters).

`Speaker` is never `PLAYER`/`OWNER` in the shipped data and the engine has no keyword for it: an
empty `Speaker` means the owner. The PC never speaks entries.

### 5.2 The client's speaker/listener (`ShowDialogEntry`, `SetDialogReplies`, high)

`CGuiInGame` keeps current speaker `+0x170`, current listener `+0x174`, previous speaker `+0x178`,
previous listener `+0x17c`, and "the player" `+0x184`. For an entry:

- First line of the conversation: player = the PC; listener = the node's listener, or the PC.
- Later lines: listener = the node's listener if set; else the PC if the speaker hasn't changed,
  else **the previous speaker**.
- Speaker = the node's speaker; previous values shift down.

For the reply list (`SetDialogReplies` `0x006340e0`): listener = the entry's speaker (the
replies' own `Listener` is not used here), speaker = the player's creature, or the party leader
(see §4.6); values shift down as above. A single empty reply is auto-selected before this
bookkeeping. For a spoken reply (`SpeakDialogReply` `0x00633660`): speaker = "the player"
(`+0x184`), listener = the reply's listener, else the entry's speaker.

### 5.3 Party members and others

Party members take part only as tagged speakers/listeners, `NPC1`/`NPC2` AnimList participants,
or stunt participants; nothing else pulls them in (med: an absence, not traced exhaustively).
Names passed to `ActionStartConversation` as "objects to ignore" (`CGuiInGame::
GetIsDialogIgnoreName` `0x0062f840`) exempt AnimList participants from the readiness wait (§4.4,
`SendEntry`) and stunt participants from the scene-ready check (`GetStuntParticipant`
`0x005a0240` → `GetIsDialogSceneReady` `0x005f3070`).

## 6. Timing

Node duration (`RunEntry` / `HandleReply` → `SetNodeDuration` `0x0059ff50`, high):

Entries:

| Entry | Duration (seconds, from the moment it is shown) | Held longer by |
|---|---|---|
| explicit `Delay` d (WaitFlags 0x10) | max(d, 0.01) (VO or not) | any WaitFlags data bits |
| voiced (file found), Delay −1 | `DelayEntry` (0 in all shipped DLGs), minimum 0.01 | WaitFlags 2: until the VO stops (only when the node's WaitFlags was 0; voiced entries with WaitFlags 1 or 9 do not wait for the voice) |
| sound set but file missing, Delay −1 | text timer | |
| no sound, Delay −1, WaitFlags 0 | text timer | |
| no sound, Delay −1, WaitFlags set | 0.01 (0 in `AnimatedCut` DLGs) | the WaitFlags conditions |
| `AnimatedCut` DLG, no VO, Delay −1, WaitFlags 0 | 0 | |

"Voiced" and "file missing" are decided as in §4.3 step 7: on a stock install by the node's
`SoundExists` bit 0, not by probing the file (med: needs a runtime check).

Replies get a timer only when spoken automatically (§4.7); the test is different (bit 2, not
0x10):

| Reply | Duration |
|---|---|
| WaitFlags bit 2 (a reply with a sound and Delay −1) | its Delay (`DelayEntry`, 0) |
| no sound, Delay −1, WaitFlags set | 0 |
| anything else, **including an explicit `Delay`** | text timer (0 for the usual empty text; 0 in `AnimatedCut` DLGs) |

So an explicit `Delay` on a reply is ignored (counting every copy in the install, 985 shipped
replies carry one: 967 carry 0, nearly all on empty-text replies, and 18 a non-zero value). (high)

An explicit `Delay` also drops the "wait for the voice" bit: `Delay` 0 on a voiced entry that
leads to real choices makes the reply list appear at once while the voice keeps playing; with the
default −1 the list waits for the voice. In the data (distinct DLGs) 338 entries with a sound
resref and real choices carry `Delay` 0, but all except about 15 are computer-panel lines
whose `VO_ResRef` names no existing file (`SoundExists` 0); about 5,700 voiced entries with
choices keep −1. The stream is replaced (stopped and recreated) whenever a line with a valid
sound resref starts (§7), even if its file then fails to play, so a voice keeps playing over the reply
list and over lines with no sound resref. (high for the mechanism; counts from the data)

- **Text timer** = `floor(len(text) × 0.11 + 1.0)` whole seconds, 0 for an empty text
  (`CExoLocString::GetDisplayTime` `0x005ea270`, single-precision, truncated by `_ftol`); `len`
  is the text in the player's language (string id language × 2 + gender, but for language 0,
  English, the gender is ignored and id 0 is used), before token substitution. Shipped entries
  with no sound, `Delay` −1, WaitFlags 0 and text (not `AnimatedCut`) give 1..23 s, median 6 s.
- The 0.01 s minimum is skipped for replies and in `AnimatedCut` DLGs.
- With no player registered (never in single player), a node with links uses the TLK sound
  length of its text, or 0.1125 s per character when that is under 0.15 s.
- End time = world time now + duration × 1000 ms, truncated (`SetDialogNodeTimer` `0x004cb1a0`,
  owner `+0x38/+0x3c`); world time is the server's (it stops when the world timer is paused,
  gameloop.md).

`WaitFlags` bits (data uses 0, 1, 8 and 9): **1** camera animation, **8** dialogue fade; the
engine adds **2** (voice) and **0x10** (explicit delay); **4** (dialogue animations) exists but no
file sets it. (high)

## 7. Voice-over and lip sync

- **Path** (`RunEntry`, high): a sound resref of 16 characters starting with `n`/`N` whose second
  character isn't `_` is a module VO line: `HD0:STREAMWAVES\<chars 1-5>\<chars 6-11>\<resref>`;
  anything else is `HD0:STREAMWAVES\<resref>`. The file is tried with the MP3 extension (resource
  type 8) first, then WAV (type 4); this existence test is what makes the entry "voiced" for §6.
  (The file is MP3 inside a RIFF header, lip.md.)
- **Playback** (`PlayDialogVoice` `0x0062e1d0`, high): only when the GUI's current speaker
  (`+0x170`) has a client object and the resref is valid; then one stream (`CGuiInGame+0xb40`,
  sound category 9) replaces the previous line's and plays the resref as MP3 (type 8), else WAV
  (type 4). If neither plays, the speaker's lip-sync slot (`+0x128`) is called directly with the
  resref (lip movement without sound) and the call reports failure. On success the lip sync is
  armed (`+0xbdc` speaker, `+0xbe0` resref) and started by `UpdatePendingLipSync` (`0x0062fa30`,
  from `UpdateDialog`) on the first frame the stream really plays.
- **LIP** (`CSWCCreature::PlayLipSync` `0x00616310`, vtable slot 0x128, high/med): loads
  `<resref>.lip` (LIPs live in `lips/*_loc.mod` and `lips/localization.mod`, lip.md); keys become
  normalised times `time / length` and pose values `(shape + 1) / 16`; it plays only if the first
  normalised time is exactly 0 and the last is within [0.99999, 1.00001) (then set to 1). The
  head's and body's `talk` animation is driven by a lip track (`CAurModel::PlayLipAnimation`
  `0x00485130` creates it, `CAurLipAnimInstance` `0x004818c0` stores each pose × the `talk`
  length; evaluated per frame in `CAurObject::Update` `0x00486670`): at elapsed time *t* it finds
  the bracketing keys and **linearly** blends the `talk` pose sampled at `pose × talkLength` of
  the two keys; past the end it holds and fades the track out. So shape *s* = `talk` sampled at **(s+1)/16 of its length**,
  not *s*/30 s as lip.md assumes (med; see Open questions). A missing LIP leaves the mouth still.
- **No LIP, no VO**: the mouth does not move; the speaker still loops its talk animation (§8.1).
- Bark sounds (`Sound` on one-liners, TLK sounds) and `SpeakString` chat sounds play on 3D
  sources at the speaker and also start lip sync through the same slot (the creature's bark slot
  `+0x120` calls `+0x128` before showing the bubble; the chat-message handler `0x00654cc0` calls
  `+0x128` too) (med).

## 8. Animations, facing, equipment

### 8.1 AnimList and default animations (`UpdateDialogAnimations` `0x006313a0`, high)

- Participants listed for the previous line but not this one go back to animation 10000 (a
  placeable participant goes back to its own default animation instead). The previous speaker
  and listener, when they were not in the previous line's AnimList, are also reset to 10000
  before this line's defaults are applied.
- A listed participant is (re)started only when new or when its number changed: the same
  looping number on consecutive lines keeps playing without a restart.
- Looping animations (`IsLoopingDialogAnimation` `0x0062d5e0`): clear the head look-at, reset,
  then loop. Fire-and-forget (`0x0062d700`): play once (cutscene numbers 1000..1327 get extra
  preparation). Placeables in the AnimList are animated the same way, without the
  `CanAnimateParticipant` gate.
- Participants without an entry: the **speaker loops 10038 (`Talk_Normal`)** and the **listener
  loops 10030 (`Listen`)**, reset through 10000 and restarted on every line; a creature under
  20 % HP (`GetIsInjured` `0x004eff30`, `0x007a1b38` = 0.2; never while its `+0xac4` is set)
  uses 10154 `Talk_Injured` / 10155 `Listen_Injured`. Dead creatures are left alone.
- **`CanAnimateParticipant` (`0x0062f0e0`, high) gates every one of these**: the AnimList entries, the
  back-to-10000 of the previous line's cast, the talk and listen loops, and the stand-up of
  everyone at the end of the conversation (`0x00631b70`, `0x00631c60`, reached from the
  in-game GUI's end-of-dialogue function `0x006332b0`). It answers no for a creature that is
  dead, debilitated (`GetIsHelpless` `0x005b4880`, script GetIsDebilitated: state `+0x8ed` set, combat.md 2, or
  dying) or a downed party member (0 HP or less), and for an id whose server object is gone;
  any other object answers yes. So a creature that died during the conversation lies where it
  fell through every later line and the end. Ours: `fight::can_animate_participant`, asked by
  `lib/dialog/view`.
- The server side agrees: `CSWSCreature::SetAnimation` (`0x004f0d70`) drops any animation but the
  three dead ones (10006, 10008, 10156) on a dead or dying creature. It maps 10000 (and 10001)
  through the creature's animation state `+0x4c4` (among others 4 gives 10006, 3 gives 10008,
  14 gives 10156, the dead pose of the way it fell), so a script's `ActionPlayAnimation` or an
  idle reset cannot stand a corpse up either.
  Ours: `world::set_animation` ignores everything but `fight::is_dead_pose` on a dead creature.

Animation numbers (`GetCutsceneAnimationName` `0x006288f0` and the tests above, high):

| Number | Meaning |
|---|---|
| 10000 + r | `dialoganimations.2da` row r (`name`, `looping`, `fireforget`, `dialog`, `overlay`, `cu_pb_range`) |
| 1000 + k | model animation `cutNNN`, NNN = k+1 (k 0..127) |
| 1200 + k | `cutNNNw` |
| 1400 + k | `cutNNNl` (looping) |
| 1600 + k | `cutNNNwl` (looping) |
| 10098 | "none" (as is any number the name table does not list) |
| other | `animations.2da` row (the small numbers 35..70 in the data) |

Exe quirk: k = 28 yields `cut039` in every block instead of `cut029` (reproduce if a model has
`cut039` but needs `cut029`; no shipped DLG uses 1028, 1228, 1428 or 1628 in `CameraAnimation`
or an AnimList, high). Loop vs. once for cutscene numbers: 1400..1727 loop, 1000..1327 once.
"Still playing" for WaitFlags 4 = any AnimList participant whose current animation is a
dialogue fire-and-forget or looping one (`0x0062d570`).

### 8.2 Facing (`SetDialogCamera` `0x006306e0`, first half, high)

Not in `AnimatedCut` DLGs or the computer panel. For each line the listener turns toward the
speaker and then the speaker toward the listener, only if the creature is not
orientation-locked (`SetLockOrientationInDialog` list) and has a head that can track (client
creature `+0x20c` > 0, med):

- If head-follow is not locked (`SetLockHeadFollowInDialog` list): compute the angle between its
  facing and the direction to the other. If it exceeds the head's horizontal arc
  (`appearance.2da` `HEAD_ARC_H`, default 40°) the **body turns by (angle − arc − 1°)** toward
  the other, so the head can cover the rest.
- Then the head looks at the other (look-at with 10.0 as the turn parameter, med); if that
  fails or head-follow is locked the body turns fully to face the other.
- Orientation is set on both the server object and the client object (no turning animation
  here; the client's own turning smooths it, med). The server creature's interact target is
  cleared.

Previous speaker/listener's head look-at is cleared first.

### 8.3 Equipment

`UnequipItems` (`0x005a0ba0`): each speaker, listener, PC and AnimList participant of each
entry, and each listed reply's participant and AnimList, has its equipment hidden on the client
once per conversation. `UnequipHItem` (`0x005a0d10`): the held weapon of the same set is hidden.
They come back when the dialogue object is deleted, the frame after the conversation ends
(destructor `0x005a4880` through `0x005a0c80` and `0x005a0dd0`, high).

## 9. Cameras

### 9.1 Choosing the shot

`CameraAngle` meanings (high):

| Value | Shot | Where |
|---|---|---|
| 0 | engine's choice: the **first node of the conversation gets 2**, every later 0 takes the next value of a fixed 19-entry cycle | server, `SendEntry`/`SendRepliesToPlayer` |
| 1 | close-up of the speaker | client |
| 2 | over the listener's shoulder onto the speaker | client |
| 3 | wide two-shot from the side | client |
| 4 | animated camera (`CameraAnimation` on `CameraModel`) | client |
| 5 | keep the current shot; speaker/listener revert to the previous pair | client |
| 6 | static camera `CameraID` from the GIT `CameraList` | client |

The cycle (dialogue `+0x9c` index, `+0xa0` step, `+0xa4` direction, `+0xa8` table, ctor
`0x005a0e80`): table = 1, 3, 1, 3, 2, 2, 1, 3, 1, 2, 1, 2, 1, 3, 2, 3, 1, 1, 1. `LoadDialog`
seeds it from the DLG's resref (`0x0059f220`): h = Σ cᵢ·(10ⁱ + 1) over the characters of the
lower-case resref (signed bytes, i from 0, 10ⁱ cut to its low 32 bits, the sum in unsigned
32-bit arithmetic); the index starts at h mod 19, the step is h mod 5 + 1, and it moves **up**
when h is odd, **down** when h is even. Each node reads the table at the current index, then
moves the index by the step; past 18 it goes to 0 and below 0 to 18 (not modulo: 17 + 3 gives
0). It steps for **every** entry sent and every reply list sent, whatever their `CameraAngle`.
The first entry and the first reply list each take 2 instead when their angle is 0 (flags
`+0xf4`, `+0xf8`, set by `LoadDialog`, cleared by the first one sent whatever its angle). An
entry's resolved angle is written back into the loaded node (`+0x8c`), so a replayed entry
keeps the angle it got the first time; a reply list is resolved on copies, and every angle-0
reply in the list gets the same cycle value. Example: `end_trask` gives h = 3369732564, so
start 9, step 5, down (high for the code, med for the worked example).

Client order for a cinematic line (`ShowDialogEntry`): try the animated camera first, **whatever
the angle** (§9.4); if it doesn't apply, enter the dialogue camera mode (`+0xb20`; once per
conversation, and again after each animated-camera line) (`CSWCModule::EnterDialogCameraMode`
`0x006412f0`, which installs a `CSWCDialogCamera` with the DLG's `OldHitCheck`) and call
`SetDialogCamera` with the angle. In the computer panel only angle 6 does anything (§9.7).
A spoken reply (`SpeakDialogReply` `0x00633660`) does the same with the reply's fields; an
auto-selected empty reply (second argument 0) runs only the reply's fade: no speaker change, no
AnimList start, no camera. (high)

### 9.2 Framed shots (angles 1–3)

`CSWCDialogCamera::SetShot` (`0x006bd260`) and `ComputeShot` (`0x006bb7b0`) (high for the
constants, med for the exact roles of the two eye points where the decompile lost them):

- FOV is set to **55°**. Angle 6, and angle 3 following angle 3, leave the camera alone.
- Eye points: the speaker's and listener's `CAMERAHOOK` model node (fallback: model position +
  0.1 m up + the model's height). With `OldHitCheck` = 1 the model root positions are used and
  each model's height is added inside the shot computation instead. S = speaker eye, L =
  listener eye.
- Side: ±1 picks the sign of the yaw offset (side 2 = negative), §9.3.

Constants per angle:

| Angle | lerp *c* | back *b* | yaw | target z | camera z |
|---|---|---|---|---|---|
| 1 | – | 0.5 + pull-back | ±30° | — | see below |
| 2 | 0.3 | 0.8 | ±30° | lerp z | + CamHeightOffset; S.z −0.1·d, L.z −0.05·d |
| 3 | 0.5 | 1.5 | ±90° | lerp z − 0.2·d + TarHeightOffset | + 0.3·d + CamHeightOffset |

where d = |S − L|.

- **Angle 1 (close-up)**: horizontal direction u = normalise(S − L) (z = 0). Look-at point
  T = S − 0.2·u, its z lowered by 0.04 and by 0.2 × pull-back, plus `TarHeightOffset`. Rotate
  (S − L) by ±30° about z and normalise to v. Camera = T − (0.5 + pull-back)·v, then z +=
  `CamHeightOffset` + 0.2 × pull-back. Pull-back = the speaker's AnimList animation's
  `cu_pb_range` (`dialoganimations.2da`, default animation 10038 → 0), kept at `+0xbb8`: once
  non-zero it is reused by the following close-ups until one whose animation's range is 0 (or a
  shot of another angle) resets it.
- **Angle 2 (over the shoulder)**: P = L + 0.3·(S − L) (after the z tweaks above), the look-at
  point T = P with z + `TarHeightOffset`; v = (S − L) rotated ±30° **about z, not normalised and
  with its z** (so |v| = d, the distance between them); camera = T − 0.8·v − 0.15·normalise(v)
  (normalised in 3D), then z += `CamHeightOffset`. The camera backs off by 0.8 of the distance
  between them plus 15 cm: 1.75 m for two creatures 2 m apart.
- **Angle 3 (wide)**: P = midpoint; v = (S − L) rotated ±90° about z, **not normalised** (|v| = d);
  T = P with z − 0.2·d + `TarHeightOffset`; camera = T − 1.5·v, then z += 0.3·d +
  `CamHeightOffset`. The camera stands 1.5 distances to the side (3 m for 2 m apart, 13.5 m for 9 m
  apart) and 0.1·d over their eyes, looking 0.2·d under them. v is normalised only in angle 1
  and in angle 2's 0.15 term. The camera's z starts from the look-at point's z in every angle, so
  `TarHeightOffset` raises the camera as well.
- If S and L coincide, L is replaced by S + (1.5, 1.5, 0.1) and the close-up formula is used.
- Orientation: yaw = heading of v (`atan2(−x, y)`), pitch = elevation of (target − camera) +
  90°, roll 0, built as Rz(yaw)·Rx(pitch) (`Quaternion_FromEulerDegrees` `0x004acac0`; the camera
  looks down its −z at pitch 0).
- **Obstruction**: after computing a new shot, `SetShot` ray-tests it against the scene, ignoring
  both participants' models and heads (angle 3: three rays, one with `OldHitCheck`; other
  angles: one). Any hit marks the shot blocked (`+0x34`), and a blocked shot is computed with the
  **close-up formula without pull-back** for the rest of the line. With `OldHitCheck` = 1 a
  blocked shot keeps its angle's formula and the camera is moved to 0.1 m in front of whatever
  the ray from the target hit; its close-up uses a fixed 0.5 m and no pull-back. (high for the
  flag and the fallback, med for the ray end points)
- The camera **re-frames every frame** from the participants' current positions (`Update`
  `0x006bcf50`), so it follows moving speakers. Changes between shots are **cuts**; there is no
  interpolation. (high)

### 9.3 The side (180° rule)

`GetSide` (`0x006bcec0`): the side is chosen once per speaker/listener pair and cached (four
pairs; when all four are taken a new pair overwrites the first slot); the same pair the other
way round gets the opposite side (`0x006bb610`), so the camera stays on one side of the line
between two characters. A new pair's side is picked by `ChooseSide` (`0x006bc600`): compute the
angle-3 and both angle-2 shots for each side, count how many of their ray tests hit scene
geometry, and take the side with fewer hits (side 2 on a tie, high). With `OldHitCheck` the
cache is used as stored, the reversed pair included.

### 9.4 Animated cameras (angle 4, `CameraModel`)

`CGuiInGame::TryAnimatedDialogCamera` (`0x0062bf70`, high): applies when the DLG names a camera
model (loaded by `SetDialogScene` `0x0062e020`, flag `+0xb28`) and 1000 ≤ `CameraAnimation` <
1728. Then `CSWCModule::PlayCameraAnimation` (`0x00641010`; it needs the line's speaker and the
loaded model, otherwise the camera is left as it was): clip planes 0.1 / 10000, the camera model
is placed at the area origin with no rotation, the game camera is attached to the model's
`camerahook` node, and the model plays the animation named as in §8.1 (`CameraAnimation` 1200 →
`cut001w`), looping for 1400–1727, else once. `CamFieldOfView` > 0 sets the FOV; −1 keeps it.
WaitFlags bit 1 holds the node until the model's animation ends (`0x006412b0`). 10098 ("none")
and values outside the range fall back to the framed/static camera with the node's angle. Stunt
models (§2.7) carry matching `cutNNNw` animations on the participants, started by the AnimList.

### 9.5 Static cameras (angle 6, `SetDialogPlaceableCamera`)

The GIT `CameraList` is copied to the client when the area loads (`0x00505eb0`; **at most 50
cameras: a list of 51 or more is ignored**): `CameraID` (default −1), `Position`, `Orientation`
(quaternion), `Pitch` (0), `Height` (0), `FieldOfView` (55), `MicRange` (0). For angle 6 the
camera with that id is used (high):

- position = `Position` + (0, 0, `Height`);
- orientation: take yaw, pitch and roll out of `Orientation`, add `Pitch` (degrees) to the pitch
  (the X rotation; 0 = looking straight down, 90 = level), rebuild as Rz·Rx·Ry;
- FOV = `FieldOfView`; `MicRange` is kept for the sound listener (`+0xf4`, med);
- unknown id: the origin, identity rotation, FOV 55;
- then `CamVidEffect` (unless −1/−2) enables that `videoeffects.2da` row (§9.6); with −1/−2 an
  effect switched on earlier stays on (med).

`SetDialogPlaceableCamera(n)` (461, `0x00546a80` → `0x0062e900`) does the same from a script,
only while a conversation is active, except that an unknown id does nothing and no video effect
is applied (the handler passes −1). In the computer panel it goes through
`SetComputerStaticCamera` (§9.7).

### 9.6 Fades, video effects, letterbox

- **Node fades** (`ShowDialogEntry` / `SpeakDialogReply`): `FadeType` 0 none; 3 → fade **in**
  over `FadeLength` after `FadeDelay`; 4 → fade **out**; 1 → out and 2 → in, with the same
  `FadeDelay`/`FadeLength` (any other non-zero type fades in). The shipped type-1 nodes have no
  `FadeLength` (0), so they cut to black. Colour `FadeColor` (RGB 0..1), on the dialogue fade
  layer (`CGuiInGame+0x68`, `CSWGuiLetterbox::StartFade` `0x006a7620`). WaitFlags 8 waits for
  it. (high for the mapping, med for the panel's own timing, gui.md)
- **Global fades** (`SetGlobalFadeIn`/`Out` 719/720, `0x00546010`/`0x005460d0`): a separate fade
  panel (`CSWGuiFade`) on `CGuiInGame+0x6c` with (in/out, wait, length, colour).
  `HoldWorldFadeInForDialog` (760, `0x00547e30`) sets `+0xb98` so the next conversation's first
  line fades that panel in from black over 1 s. (high)
- **Video effects**: `CamVidEffect` on a static-camera node, or `EnableVideoEffect` (508,
  `0x005471e0` → `0x005f7710`), switch the previous effect off and then apply
  `videoeffects.2da` row n: scan noise when `EnableScanNoise`, and when `EnableSaturation` the
  `Saturation` and `ModulationRed/Green/Blue` values; the client keeps the active row at
  `+0x3a8` (−2 = none). `DisableVideoEffect` (510) sets −2 and switches both off. Framed shots
  turn the effect off (`0x005edf20`). (high) In `SetDialogCamera` (`0x006306e0`): angle 5 changes
  nothing, angle 6 enables the node's effect unless it is −1/−2, every other angle frames a shot
  and calls `0x005edf20`; animated-camera nodes do not call it, so an effect stays on through
  them. The dialogue panel's close (`0x006332b0`, from `ClearDialog`, the module transition and
  `SpeakDialogReply`) switches it off too, so a conversation's effect ends with it. (high)

  **What it draws.** `EnableVideoEffect` only sets render globals (`0x0044f0c0`..`0x0044f100`:
  saturation on `0x007a6881`, scan noise on `0x007a6882`, modulation r/g/b `0x0078db24..2c`,
  saturation `0x007a6884`). `CAurScene::RenderPasses` (`0x004514f0`) runs the frame-buffer
  passes after the scene and before the GUI, only with the **Frame Buffer Effects** option
  (`0x0078d98c`, mechanics/graphics.md) and a GPU path that has them:
  - scan noise (`Render_ApplyScreenEffects` `0x00437520` bit 4; ATI path `0x00432780`, NV path
    `0x00432ad0`): the screen copy plus the scene's `filmnoisetex` (`CAurScene` +0xe4, requested
    in `CAurScene::CAurScene` `0x00458790`; a TXI-only procedural texture: `proceduretype
    random`, 32×32, channel scale 0.02, so a grain of 0..0.02) tiled 7.5 times across the
    screen, **added** (ATI fragment shader `0x007a6920` built in `0x00427490`: `ADD` of the two
    samples); (high for the add and the tiling, med for how often the grain changes)
  - saturation (`Render_ApplyScreenEffectsLate` `0x004361f0` → `0x00434890`, NV register
    combiners, stage 0x16 of `GL_SetupScreenEffectStage` `0x004299c0`: three dot products): a
    colour matrix whose row for channel c is m_c · (s·e_c + (1−s)·(0.3086, 0.6094, 0.082)),
    each entry clamped to 1 (the code tests the blue row's first entry where it means its last;
    no shipped row reaches 1 there). Row 0 (s 0.15, m 1/1.4/2) gives a blue-grey picture: the
    security camera and the comlink calls (`end_carth001`'s static-camera lines, CamVidEffect
    0). Rows 1 and 2 are T3-M4's and HK-47's free-look views. (high for the matrix, med for the
    clamp being a register limit)
  Ours: `render::VideoEffect` on the view (`dlgview::video_effect_of` builds the rows), drawn by
  `gpu::video_effect` after the speed blur in both renderers, under the GUI.
- **Letterbox**: the cinematic panel is `dialog.gui` (`CSWGuiDialogLetterbox` `0x006a8b40`,
  0x1e00 bytes): `LBL_MESSAGE` for the line and `LB_REPLIES` for the replies (20 rows with hover
  colours), laid out across the screen width. It also builds a small text panel (`+0x1dfc`)
  that shows the NPC's line inside the top bar while the replies are listed and is removed when
  one is picked. The black bars themselves are separate panels (`CGuiInGame+0x60`, `+0x64`)
  added by `ShowConversationPanel` (render-gui.md, gui.md). The computer panel is
  `computer.gui`; with angle 6 it is swapped for `computercamera.gui` so the 3D view shows
  (§9.7).

### 9.7 Computer conversations (`ConversationType` 1)

Panel `computer.gui` (`CSWGuiDialogComputer`, created on first use, `ComputerType` picks the
skin's `comptypes.2da` row). Lines and replies are text in the panel; facing, framed shots and
animated cameras are skipped. A node with `CameraAngle` 6 swaps in the `computercamera` panel
and places the static camera (`SetComputerStaticCamera` `0x0062c030`; nothing happens when the
area has no static cameras). Here `CamVidEffect` −1 applies `videoeffects.2da` row 0
(`VIDEO_EFFECT_SECURITY_CAMERA`), only −2 means none. Every following line and reply first puts
the computer panel back and turns the video effect off (`0x0062d990`, `0x0062d8c0`), so the
next node without angle 6 shows the computer panel. (high)

- `SetComputerStaticCamera(id, effect)`: returns at once when the area's camera count
  (`CGuiInGame+0x1b0`) is 0; else removes the current panel (`+0x3c`), adds the camera panel
  (`+0x48`) and gives it the speaker (slot 30), places the static shot, then effect −1 → 0, −2 →
  none, else that row. `SetDialogPlaceableCamera` (461) in a computer conversation calls it with
  effect −1, so a script's camera gets the security camera's look as well. (high)
- `computercamera.gui` (`CSWGuiDialogComputerCamera` `0x006a95f0`) is sized to the screen and has
  one label, `LBL_RETURN` (strref 48226 "Press 'Enter' to Cancel Live Feed and Return to
  Interface."), moved to x = (screen width − its width) / 2, y = screen height − 75. Its input is
  the shared `CSWGuiDialog::HandleInputEvent` (`0x006a7230`): Enter or a click while the line is
  up skips it. The camera nodes in the data have empty text, a `Delay` (the Endar Spire's: 5 s, 2
  s, 5 s) and one empty reply, so the view stays up for the delay and the next entry brings the
  panel back. (high)
- Ours until 2026-10: the computer panel stayed up over the static camera and nothing read the
  video effect, so "view camera" showed the panel with an empty line for the delay
  (`end_securitycomp`, `tar08_aacompdlg`, `tar09_*`, `man27_comp*`, `dan16_comp*`,
  `lev40_*compdlg`, `unk_comp*`, `sta45_turretcomp`: 45 of the 102 computer DLGs have angle-6 nodes).
  `kotor/tools/camcheck/computer.sh` checks the Endar Spire's.

## 10. Barks, speech, one-liners, cutscenes, movies

### 10.1 Bark bubbles

Sources (high): a one-liner DLG (§4.1, `PlayOneLiner` `0x005a1050`), `BarkString(o, strref)`
(671, `0x00548900`) and `ActionBarkString(strref)` (700, `0x0052c6a0`, action 0x3e
`0x0057ce00`). The two script commands do nothing while a conversation is active or pending
(`CGuiInGame+0xb4`); `ActionBarkString` tests this when it is called, not when the queued action
runs, and only queues on a creature. `BarkString` with `OBJECT_INVALID` shows a bubble with no
speaker.

`PlayOneLiner(entry)` in order (high):

1. Text = the entry's text in the PC's language and the dialogue's gender (`+0x78`); sound = the
   node's sound (`Sound`, else `VO_ResRef`, §3).
2. If the world fade-in is held (`CGuiInGame+0xb98`): clear it and fade in from black over 1 s.
3. No valid sound: take the TLK sound resref of the text's strref.
4. **Empty text: stop here** — no bubble, and the end flag is not set, so the conversation is
   then only aborted (§4.1: the entry's `Script` and the reply's run, then `EndConverAbort`; the
   DLG's `EndConversation` and the owner's end-of-dialogue script do not run). 10 shipped
   starting one-liner links have an empty text, 5 of them with a `Script`.
5. Speaker quirk: the bubble's speaker comes from **entry 0's** `Speaker` (not the chosen
   entry's): empty → the owner, else the object with that tag nearest the PC in the PC's area
   (`GetNearestObjectByTag` with range 0 = no limit); none → no speaker. 24 shipped one-liner
   starting links (12 DLGs, e.g. `bastila`, `tar08_canderous`, `end_trask01`) name a speaker in
   entry 0, usually the owner's own tag; the rest are empty.
6. Show the bubble (`ShowBark` `0x005edbb0`) with the "keep at any distance" flag = integer 3 of
   the `ON_DIALOGUE` event that started the conversation (`GetDialogEventFlag`): the
   DIALOGOBJECT "skip the range test" parameter, 1 when a script started the conversation, 0 for
   a click (§2.3).
7. Set the end flag (`+0x6c`) and call `EndConversation` for the owner only: the DLG's
   `EndConversation` script, then the owner's own end-of-dialogue script. `GetStartingEntry`
   then runs the entry's `Script` (and the single reply's), and the second `EndConversation`
   runs `EndConverAbort` (§4.1).

The client (`0x005f2c90`): if the speaker has a client object, its slot 0x120 (`0x0060f510`)
starts lip sync with the sound (slot 0x128, §7) and then shows the bubble; otherwise the bubble is
shown with no speaker. `BarkString` / `ActionBarkString` pass the flag 0. (high)

- The bubble (`barkbubble.gui`, `CSWGuiBarkBubble` `0x006a9770`, `CGuiInGame+0x4c`, shown only
  once the in-game panels exist, `+0x108`): **one at a time** (a new bark replaces the text and
  stops and frees the old sound); text token-parsed with the PC as the token object, height = text
  height + 10 + 2 × border; duration = `len(text) × 0.11 + 1.0` s, `len` after token parsing (not
  truncated). The sound is a streaming source, positioned at the speaker when there is one
  (category 0x1a, volume 127, med for the category). (high)
- Lifetime (`Render` `0x006a9ce0`, high): the bubble is *visible* when it has no speaker, or the
  speaker has a client object and (the flag is set, or the speaker is under 6 m from party member
  0). While its sound plays it is drawn if visible and **closed** if not (the sound plays on).
  Once a sound that started has stopped, the bubble closes at once; the duration then does not
  matter. With no sound (none set, or the file missing) it is drawn while visible and the
  duration is above 0, and closes otherwise. The duration counts down by the frame time only on
  drawn frames under 1.5 s. Position: the panel's own extent (stretched across the screen while
  the HUD is hidden, lowered by the combat bar in combat), not above the speaker (med).
- The message-log copy of one-liner barks ("Name: text") is behind a flag that nothing in the
  binary writes (`0x00833a9c`, 0 in the image; its only readers are `PlayOneLiner` and the chat
  handler `0x00654cc0`), so it never happens (high).

### 10.2 `SpeakString` family

`ActionSpeakString` (39, queued as action 0xe `0x0057b430`), `SpeakString` (221, immediate), both
`0x00544090`; `ActionSpeakStringByStrRef` (240, action 0x21 `0x0057b3d0`). The two actions are
queued only on a commandable object (`+0xe8`) and, on a creature, first drop its activity modes
(`ClearActivities(2)`) and stealth (`SetActivity(1, FALSE)`); `SpeakString` sends at once. The
string commands map the talk volume to a chat type (TALK 1, WHISPER 3, SHOUT 2, SILENT_TALK 0xd,
SILENT_SHOUT 0xe, anything else 1) routed by `SendSpeakMessage` (`0x00571960`, high):

| Volume | Players who see the text | Listeners who can hear it (patterns) |
|---|---|---|
| TALK | same area, within 1000 m | 1000 m |
| WHISPER | same area, within 3 m | 3 m |
| SHOUT | all players | 250 m |
| SILENT_TALK | none | 35 m, silent test below |
| SILENT_SHOUT | none | 1000 m |

`ActionSpeakStringByStrRef` maps TALK → chat type 8, WHISPER → 10, SHOUT → 9 and anything else
(the silent volumes included) → 8, and goes through `SendSpeakStrRefMessage` (`0x00571760`): type
8 to players in the same area within 1000 m, 10 within 3 m, 9 to all players. It never reaches
listeners: a strref line fires no `ON_DIALOGUE`. (high)

Hearing (`BroadcastSpeech` `0x004cd760`, high): objects in the speaker's area, other than the
speaker, with listening on (`SetListening`, `+0x19c`) within the range (inclusive). When both are
creatures the listener's perception entry for the speaker must have bit 0x02 (heard); for
SILENT_TALK it must also have bit 0x01 (seen) or be within 10 m (SILENT_SHOUT has no extra test).
A creature listener hearing a non-creature speaker needs it within its hearing range; a
non-creature listener has no test. The first listen pattern that matches (`SetListenPattern`,
`MatchListenPattern` `0x004cd700`) sends the listener `ON_DIALOGUE` (script event 7, through the
AI master, no delay) with the pattern number as integer 1 and the matched substrings as strings
from 1 on. The client shows "Name: text" as floating text 2 m above the speaker and plays any
sound at the speaker with lip sync (med).

### 10.3 `SpeakOneLinerConversation` (417, `0x00543f70` → `0x004cb220`)

Loads the DLG (argument, else `GetDialogResRef`) without links (reply counts only), takes the
first starting link whose entry has an empty `Speaker`, a passing `Active` (OBJECT_SELF = the
caller) and no replies at all (`0x0059ee00`; a single dead-end reply does not qualify here),
sends its text and sound as chat type 8 to players in the same area within 1000 m (gender from
`oTokenTarget` when it is a creature, else 0), and runs its `Script` on OBJECT_SELF. No
conversation, no camera, no bubble, no listeners; it also runs during a conversation. (high)

### 10.4 Cutscene support

There is no cutscene mode flag in KOTOR; cutscenes are conversations with `AnimatedCut` = 1, a
`CameraModel`, `StuntList`, `CameraAngle` 4 entries chained through empty replies, and `Delay` /
`WaitFlags`. `AnimatedCut` (`CGuiInGame+0xc0`) changes (high): no facing (`SetDialogCamera`), no
0.01 s minimum (`SetNodeDuration`) and a zero text timer for unvoiced entries with Delay −1
(`RunEntry`) and for replies (`HandleReply`), reply WaitFlags ignored (`HandleReply`), the
VO-still-playing wait before advancing is skipped (`UpdateDialog`), and the client does not apply
the "show the text without subtitles" flag (`ShowDialogEntry`, §4.4). Scripts add:

| Routine | Handler | Effect |
|---|---|---|
| `SetDialogPlaceableCamera` 461 | `0x00546a80` | static camera, §9.5 |
| `SetLockOrientationInDialog` 505 / `SetLockHeadFollowInDialog` 506 | `0x005470e0` / `0x00547160` | value 1 adds the object to `CGuiInGame+0xb44` / `+0xb48` (`0x0062f160` / `0x0062f2b0`; adding to the head list also clears its look-at), any other value removes it, §8.2 |
| `CutsceneMove` 507 / `CutsceneAttack` 503 | `0x0052e950` / `0x0052e890` | creatures only: scheduled move / attack entries in the combat round plus action 0x3f (actions.md 3.13, combat.md) |
| `EnableVideoEffect` 508 / `DisableVideoEffect` 510 | §9.6 | |
| `SetGlobalFadeIn`/`Out` 719/720, `HoldWorldFadeInForDialog` 760 | §9.6 | |
| `SetCameraMode` 504 | `0x00542640` | camera mode message to that player's client (movement.md) |
| `ResetDialogState` 749 | `0x00547bc0` | `SetDialogPending(0)`: clears the pending flag and the dialogue event flag, and releases a held world fade-in (1 s) |
| `CancelPostDialogCharacterSwitch` 757 | `0x00547d20` | forget the creature to return control to (§2.3) |
| `PlayMovie` 733 | `0x00540ed0` | synchronous: input reset, sound mode 3, play, sound mode 0 (app.md) |
| `QueueMovie` 769 / `PlayMovieQueue` 770 / `IsMoviePlaying` 768 | `0x00548210` / `0x005482d0` / `0x005481e0` | movie queue (app.md) |

`Mod_CutSceneList` in the IFO is read by the module loader (`LoadModuleStart` `0x004c9050`:
`CutScene_Name`, `CutScene_ID` into a list at module `+0x2c`) and written back on save
(`SaveModuleIFOStart` `0x004c7050`); nothing else was found reading that list (med).

## 11. Script routines

| # | Routine | Handler | Behaviour |
|---|---|---|---|
| 204 | ActionStartConversation | `0x0052d5b0` | §2.2 |
| 205 / 206 | ActionPause/ResumeConversation | `0x0052d330` / `0x0052d520` | §4.10 |
| 255 | BeginConversation | `0x0052e9f0` | §2.5 |
| 238 | GetPCSpeaker | `0x0053c9c0` | always the party leader (the player's controlled creature) (high) |
| 254 | GetLastSpeaker | `0x0053b410` | creature `+0x17c`: the caller of the last `ON_DIALOGUE` it received (a clicker or a speaker it heard); `OBJECT_INVALID` for non-creatures (high) |
| 295 | EventConversation | `0x005358c0` | an empty script event of type 7 (high) |
| 445 | GetIsInConversation | `0x0053eec0` | the object's `+0x54` names an owner whose `+0x54` is the same (high) |
| 701 | GetIsConversationActive | `0x0053ef70` | `CGuiInGame+0xb4`, the pending flag: TRUE from the moment a conversation is requested (high) |
| 711 | GetLastConversation | `0x0053f010` | string 0 of the last creature `ON_DIALOGUE` (the DLG resref; "" after a heard listen pattern, med) (high) |
| 417 | SpeakOneLinerConversation | `0x00543f70` | §10.3 |
| 39 / 221 / 240 | ActionSpeakString / SpeakString / ActionSpeakStringByStrRef | `0x00544090`, `0x00544270` | §10.2 |
| 671 / 700 | BarkString / ActionBarkString | `0x00548900` / `0x0052c6a0` | §10.1 |
| 461, 503–510, 719, 720, 733, 749, 757, 760, 768–770 | | | §9, §10.4 |

## 12. Corpus facts and corrections to gff-dialog.md

Counted over the 1146 distinct DLGs in the install (distinct resref and content, saves excluded;
recount with `kres.Game().every_entry('dlg')` and `gff.py`):

- `ConversationType`: 0 in 730, absent (= 0) in 163, **2 in 139**, 1 in 114. Type 2 = "always a
  real conversation, never a bark" (§4.1), used by party-member and plot DLGs.
- `OldHitCheck` 1 in 27 DLGs = the older dialogue-camera framing (`CSWCDialogCamera+0x38`): model
  root positions instead of `CAMERAHOOK` nodes (§9.2), and a cached side returned as stored for
  the reversed pair (§9.3). It is not a line-of-sight start check: nothing else reads it.
- `CameraAngle` entries: 0 18815, 6 3207, 1 1428, 2 272, 3 258, 4 232, 5 24; replies: 0 26448,
  1 461, 6 417, 5 20, 2 13, 4 5, 3 2. Angle 5 = "keep the shot" (§9.1).
- `FadeType` 1 (17 entries, 62 replies) = instant fade out; 2 = instant fade in (unused).
- `SoundExists` on entries: 1 13855, 3 6550, 0 1233, 2 24, absent 2574. Bit 1 forces the
  subtitle on (§4.4); bit 0 = "has a voice line", which `RunEntry` uses instead of probing the
  file on a module mounted from its `_s.rim` (§4.3).
- `Delay`: 0xFFFFFFFF on 22910 entries; explicit values 0..20 s otherwise. 0 on 893 entries:
  0.01 s, i.e. go on at once (with VO: replies shown while it plays, §6); the larger values sit
  mostly on silent pass-through entries with a single empty reply (cutscene beats).
- `WaitFlags`: entries 0/1/9, replies 0/1/8 (§6).
- One-liners: 767 starting links lead to an entry with no replies and 1149 to an entry with one
  reply leading nowhere (88 and 223 of them in type-2 DLGs); the others bark when chosen. 10 of
  the barking ones have an empty text and show nothing (§10.1).
- Single empty-text replies (auto-continue): 16284. Entries mixing empty and non-empty replies
  (engine error): 6 (`dan14_elise`, `dan14_cutscene`, `kas22_dasol_01`, `kas23_chuunda_01`,
  `man26_manmerc`, `tat17_griff`); the engine aborts those conversations when such an entry's
  replies are offered with both kinds passing (`SendRepliesToPlayer` `0x005a1c00` stores
  "CONVERSATION ERROR: …" at `CGuiInGame+0xb18` and returns 0).
- `DisplayInactive`: no DLG has it. `Speaker` is never a keyword; `Listener` `PLAYER` 1716
  entries; AnimList participants: tags 2010, `OWNER` 1363, `PLAYER` 362, `NPC1` 7, `NPC2` 8.

## 13. Open questions

- Which key/panel action sends the abort code −3 to `SpeakDialogReply`, and whether Escape
  aborts a conversation (gui.md's 0x28 handling in the dialogue panels was not traced).
- The ray end points of the obstruction tests in `SetShot` and `ComputeShot` (the decompile lost
  the arguments).
- `MicRange` of static cameras: stored, but its use by the sound listener was not traced.
- `AmbientTrack` stop/restore of the area music (the music stop fades over 0.5 s; whether area
  music is paused meanwhile is not traced).
- The `UnequipItems` restore at the end of the conversation (the add-only lists at dialogue
  `+0x114/+0x118` were read; the restore was not).
- Multiplayer remnants (several players, `+0x8c` "player-only replies") were not followed.
