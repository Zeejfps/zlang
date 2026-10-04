# Conversations, dialogue cameras, barks and cutscenes in swkotor.exe

How the original engine runs a DLG conversation: how one starts (a click, a script, an
`ON_DIALOGUE` event), how the server-side dialogue object walks the entry/reply graph, who speaks
to whom, how long each line stays up, how voice-over, lip sync and the participants' animations
are driven, how the conversation camera frames each shot, and the lighter-weight speech paths
(bark bubbles, `SpeakString`, one-liners) plus the script hooks cutscenes use (fades, static and
animated cameras, video effects, movies). Addresses are for the Steam `swkotor.exe` after
SteamStub removal (see [README.md](README.md)). Every claim carries a confidence: **high** = read
in the code, **med** = role clear, detail inferred, **low** = plausible. Names are ours; proposals
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
| player clicks an NPC | `0x005254c0` (input message case 8) | queues action 0x18 DIALOGOBJECT on the player's creature: {target, resref "", private 0, 1, range check on (0), `OBJECT_INVALID`} (high) |
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
3. Each non-empty ignore name is added to `CGuiInGame`'s ignore list (`+0xb4c`, `0x00632300`):
   AnimList participants with those tags don't hold up a node while they are missing (§5.3).
4. `CGuiInGame+0xbd8` = `bUseLeader` (the reply list is then spoken by the party leader instead
   of the main PC, §5.2).
5. The party leader's (party slot 0) client movement is stopped and its actions are cleared, at
   once.
6. Only if no conversation is pending (`CGuiInGame+0xb4` = 0), OBJECT_SELF is valid and
   commandable (`+0xe8`): raise its AI level to 1 if it is 0, set the pending flag (`+0xb4` = 1,
   `CGuiInGame::SetDialogPending` `0x0062ec60`) and append action 0x18 with parameters
   {target, resref, private, 1, 1, `OBJECT_INVALID`}.

### 2.3 The DIALOGOBJECT action (`0x0057a470`)

Action parameters: 0 target, 1 resref, 2 private, 3 "use-range test" (always 1 from the shipped
callers), 4 "skip the range test" (1 from scripts, 0 from clicks), 5 a creature id used by the
character-switch hand-off (`OBJECT_INVALID` normally). Per run (status codes as in objects.md:
2 done, 3 failed):

1. Fail (clear the pending flag) if the actor is dead, or if **every** party member is dead or
   at 0 HP (`0x004ef890` over the client party table).
2. The target must exist, be commandable and not dead, else fail. The action keeps running
   (status 1) until the player's creature has a client object.
3. If the client is busy (a movie or a mode that blocks conversations, `0x005edad0` /
   `0x005edc10` / client `+0x384` bit 0, med), put the action back at the head of the queue and
   try again next frame.
4. Set the pending flag. If the actor is a creature: drop its "activity" modes
   (`ClearActivities(2)`) and leave any conversation it is in (clear activity bit 4).
5. Unless parameter 4 is set: with parameter 3 set, the actor must be within its use range of
   the target + 1.1 m (`GetIsInUseRange(target, 1.0)`, actions.md); with it clear, within 10 m.
   Out of range: push this action back at the head, then push a move-to-point to the target's
   approach point (`GetUseRange`) in front of it, and return. (high for the order, med for the
   use-range detail, which belongs to actions.md)
6. **Character switch** (med; the decompile is tangled): when the actor is a party member the
   player is not controlling and the target is not the controlled creature, and the PC is not in
   combat: stop and clear the leader and the other two party members, move any party member 30 m
   or more from the leader to a formation spot near it, **fade to black over 0.75 s**
   (`CGuiInGame` fade, mode 0), release the mouse, mark `CGuiInGame+0xb98` ("fade the world in
   at the first line"), and move the action to the target with parameter 5 = the leader's id.
   When that action runs and the fade has finished, the two creatures swap positions (the actor
   turns toward parameter 0), control returns to the main PC (party switch −3,
   party-items-saves.md) and `CGuiInGame+0xba4` remembers the creature to give control back to
   after the conversation (`CancelPostDialogCharacterSwitch` clears it). If the actor *is* the
   controlled creature and the target is the PC, control also switches to the PC.
7. Send script event 7 `ON_DIALOGUE` to the target, caller = the actor, through the AI master
   (delivered next frame), with ints {−1, −1, private, parameter 4} and the resref as string 0.
   Done.

### 2.4 `ON_DIALOGUE` on the target (`0x004fece0`, case 7)

The target stores: `+0x17c` = the caller (what `GetLastSpeaker` returns), `+0x198` = int 1 (the
listen-pattern number: −1 means "a conversation", what `GetListenPatternNumber` returns), `+0x184`
= the resref, `+0x180` = private; the server keeps the resref as "last conversation"
(`GetLastConversation`) and sets a "dialogue event pending" flag (`0x004af010`) that
`BeginConversation` checks. If ScriptDialogue (`+0x268`) is empty or `"default"` it becomes
`k_hen_dialogue01`; the script runs with OBJECT_SELF = the target. Placeables and doors have
their own `OnDialog` slots (objects.md). (high)

The same event type also comes from heard speech that matches a listen pattern (§10.2); then
int 1 is the pattern number instead of −1.

### 2.5 `BeginConversation` (`0x0052e9f0`)

`int BeginConversation(string sResRef = "", object oObjectToDialog = OBJECT_INVALID)` (high):

1. Proceed only if the dialogue-event flag is set or no conversation is pending; the flag is
   cleared either way.
2. Self = OBJECT_SELF; other = `oObjectToDialog`, or self's `+0x17c` (the last speaker).
3. For each side that is not the PC: clear its actions; remember its facing; reset its
   animation to 10000 (stand).
4. Resref: the argument, else self's `+0x184` (from the event).
5. **Owner choice**: the PC never owns a conversation. If the other is the PC, self owns it. If
   self is the PC, the other owns it. If self is a creature under the player's control (a party
   member, `+0xa88`) talking to a non-PC, the other owns it. Otherwise self owns it.
6. `StartConversation(owner, otherSide, resref, private)`. On success return TRUE. On failure
   restore both sides' facing, clear the pending flag, return FALSE.

### 2.6 `StartConversation` (`0x004cf490`)

1. If the owner already has a dialogue object, return 1 (and clear the pending flag if its last
   conversation just ended).
2. Clear the owner's node fields (`+0x38`..`+0x74`, `+0x74` = 1).
3. Resref = the argument, or the owner's virtual `GetDialogResRef` (slot 32: a creature's
   `Conversation` field in its stats, a placeable's or door's own field). Empty → fail.
4. Open the DLG (resource type 2029, `"DLG "`); create `CSWSDialog` and load it
   (`LoadDialog` `0x005a2ae0`, §3). Failure → fail. Dialogue `+0x90` = private.
5. Set the pending flag. (If the client camera mode is 5, leave that mode first, low.)
6. Register the player: a 12-byte record {player, other side's id, gender of the player's
   creature} in the dialogue's player list (`+0x64`); dialogue `+0x7c` = the other side (called
   "the PC" below: it normally is), `+0x78` = gender (picks the male/female text variants). The
   other side's `+0x54` = owner; owner's `+0x54` = owner; `CGuiInGame+0x188` = owner. Both sides
   (if creatures) drop activity modes and set activity bit 4. The local player is always
   registered, so even a conversation a script starts between two NPCs shows its replies to the
   player (med).
7. `SetOwner` (`0x0059f430`): dialogue `+0x80` = owner, save the owner's AI level and raise it
   to at least 3 for the conversation.
8. Pick the starting entry (§4.1) and run it (`RunDialogEntry` `0x004cd460`). If that fails
   (−1: no entry, or a one-liner played as a bark): if the world fade-in was being held, fade
   back in over 1 s now; clear the pending flag; return 0. Else return 1.

The panel is chosen while loading: `ConversationType` 1 → the **computer** panel
(`computer.gui`, `ComputerType` passed for the Rakatan skin); anything else → the **letterbox**
panel (`dialog.gui`), and for those the party leaves stealth (`0x00563c60`). `ConversationType`
2 additionally sets dialogue `+0x110`, which only disables the one-liner rule (§4.1). (high)

### 2.7 Scene readiness

Until the client reports the scene ready, every node counts as still running (§4.5), so nothing
advances. `0x005f3070`, called through the node-running test, at most once per second: the owner,
the PC and every `StuntList` participant must have client objects; it then sends the scene setup
(`SendSceneSetup` `0x005a0080` → client `0x0062e020`): stunt models swapped onto their
participants, the DLG's `CameraModel` loaded once (`CGuiInGame+0xb28` = 1), and `AmbientTrack`
started as music on its own stream (`0x0062a8b0`, `CGuiInGame+0xbbc`; stopped with a 0.5 s fade
at the end). Stunt participant names: `PLAYER` = the PC, `OWNER` or empty = the owner, else the
nearest object with that tag (no range limit). (high for the gating, med for the stunt-model
details)

## 3. The loaded dialogue (`LoadDialog` `0x005a2ae0`)

Top-level fields read: `CameraModel` (`+0x50`), `DelayEntry` (kept as the default node delay),
`DelayReply` (read and **ignored**: replies also use `DelayEntry`), `EndConversation` (`+0x1c`),
`EndConverAbort` (`+0x2c`), `Skippable` (default 1, `+0x3c`), `ConversationType`, `ComputerType`,
`AmbientTrack` (`+0xfc`), `UnequipItems` (`+0x40`), `UnequipHItem` (`+0x44`), `AnimatedCut` (→
`CGuiInGame+0xc0`), `OldHitCheck` (→ `CGuiInGame+0xc4`), then `ReplyList` (count `+0xc`,
0xb4-byte nodes at `+0x10`), `EntryList` (count `+0x4`, 0xb0-byte nodes at `+0x8`),
`StartingList` (count `+0x14`, 0x14-byte links at `+0x18`), `StuntList` (`Participant`,
`StuntModel`; count `+0x48`, 0x18-byte records at `+0x4c`). (high)

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
| `+0x8c..+0xa4` | `CameraAngle`, `CameraID`, `CamHeightOffset`, `TarHeightOffset`, `CameraAnimation`, `CamFieldOfView`, `CamVidEffect` | |
| `+0xa8/+0xac` | link count / links | entry→reply links 0x18 bytes {Active, Index, DisplayInactive}; reply→entry links 0x14 bytes {Active, Index} |

Load-time rules (high):

- **Sound beats VO**: if `Sound` is set it becomes the node's sound and the node is marked "not a
  voice line"; else `VO_ResRef` is used; with neither, `SoundExists` is forced to 0.
- **Delay −1** (0xFFFFFFFF, the default): with a sound, `Delay` becomes `DelayEntry` (always 0)
  and a WaitFlags of 0 becomes **2** ("wait for the voice"); with no sound but WaitFlags set, the
  marker `+0x28` = 0 and `Delay` = `DelayEntry`; with neither, nothing changes (the text timer
  applies, §6). **Any other Delay** sets WaitFlags bit **0x10** ("explicit delay").
- `FadeType` 1 or 2 force `FadeLength` 0; `FadeType` 0 (or no `FadeType` field) zeroes all fade
  fields.
- `CamFieldOfView` missing or ≤ 0 → −1. `CameraID` → −1 unless `CameraAngle` is 6.
  `CamVidEffect` defaults to −1.
- A link whose `Index` is beyond the target list makes the whole load fail. (Reply→entry links
  accept `Index` = entry count, an off-by-one in the check.)

## 4. The flow

### 4.1 The starting entry (`GetStartingEntry` `0x005a3640`)

Walk `StartingList` in order and take the first link where (a) the entry's `Speaker` is empty, or
equals the owner's tag (case-insensitive), or can be resolved (§5.1), and (b) the link's `Active`
script passes (§4.2). None → −1 (no conversation). (high)

**One-liners become barks.** Unless `ConversationType` is 2, if the chosen entry has no replies,
or exactly one reply that itself links to no entries, the engine does not open a conversation:
it plays the entry as a bark (`PlayOneLiner` `0x005a1050`, §10.1), which also ends the
conversation normally (DLG `EndConversation` script, then the owner's own end-of-dialogue
script), runs the entry's `Script` (and that single reply's `Script`), and returns −1. That is
how ambient NPCs answer a click with a floating line instead of the letterbox. Because
StartConversation then fails on the −1, `EndConversation` is called a second time and, the
normal end having been done, runs **`EndConverAbort` as well**: a bark runs both end scripts
(shipped DLGs mostly name the same script in both). `BeginConversation` returns FALSE. (high)

### 4.2 Conditions and scripts

- `Active` (`CheckCondition` `0x0059ec90`): empty → TRUE; otherwise run the script with
  **OBJECT_SELF = the owner**; TRUE only if it ran and returned an int ≠ 0. A missing script
  counts as FALSE (`RunScript` fails). (high)
- Node `Script`, `EndConversation`, `EndConverAbort` (`0x0059ed70`): run with OBJECT_SELF = the
  owner when not empty. (high)
- The link's `Active` is the only condition; KOTOR has no `Active2`/`Not` fields (none read).

### 4.3 Running an entry (`RunEntry` `0x005a4010`)

`RunDialogEntry` (`0x004cd460`) first defers when the conversation is paused or the current node
is still running (it stores the entry as pending, §4.5). Then, in this order (high):

1. Entry index out of range → fail (the conversation ends).
2. **Speaker**: empty or the owner's tag → the owner; else resolve the tag (§5.1); not available
   → fail (the conversation ends, abort path).
3. **Listener**: empty → none (the client picks one, §5.2); `OWNER` → owner; `PLAYER` → the
   party leader; else resolve the tag (none if not found). `OWNER`/`PLAYER` compare
   case-insensitively.
4. Clear "replies sent" (`+0x68`). For each player: send the entry to the client
   (`SendEntry` `0x005a13d0`, §4.4). If a participant isn't ready yet (status 10), stop here and
   retry next frame. Then apply `Quest`/`QuestEntry` for that player (§4.8).
5. Award `PlotIndex`/`PlotXPPercentage` (§4.8).
6. Start the voice: `CGuiInGame::PlayDialogVoice` (`0x0062e1d0`, §7) with the speaker and the
   node's sound.
7. Decide "has VO": normally by probing the file (§7: `streamwaves` path, `.mp3` then `.wav`);
   in one client mode (`0x005ee0d0(8)`, unidentified, low) by `SoundExists` bit 0 instead. With
   sound disabled, "has VO" stays as returned by the play call. When a voiced line's file is
   missing and subtitles are off, force the text on for this line (`CGuiInGame+0xbb0`).
8. Remember the speaker (`+0x94`).
9. **Node duration** (§6) → the owner's end time (`SetDialogNodeTimer` `0x004cb1a0`).
10. Owner `+0x5c` = the node's WaitFlags.
11. Run the entry's `Script` (so scripts run when the line is **shown**, after the client got
    it).
12. Current entry (`+0x70`) = this one; then `RunDialogReplies` (`0x004cd500`): if the node is
    already over and not paused, send the replies now, else mark "pending: replies".

### 4.4 What the client gets for a line (`SendEntry` `0x005a13d0` → `ShowDialogEntry` `0x00631d80`)

Server side (high):

- AnimList participants: `PLAYER` → the PC (if a player is registered), `OWNER` → the owner,
  `NPC1` / `NPC2` → party slots 1 / 2, else the nearest object with the tag in the owner's area
  (no range limit). These four keywords are compared **case-sensitively** here. Missing → logged
  ("Error: dialogue can't find object '%s'!", discarded) and skipped.
- Readiness: listener, speaker and PC must have client objects, and every tagged AnimList
  participant that is not on the ignore list too; otherwise status 10 and retry. After waiting
  **1500 ms** (`+0x120` counts down in world time) it goes ahead anyway.
- `CameraAngle` 0 is resolved (§9.1). Unequip lists are applied (§8.3).
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
   above says so (`+0xbb0`); in the computer panel or with sound off it is always shown.
4. Speaker/listener bookkeeping (§5.2), animations and facing (§8).
5. Fade (§9.6), then the camera (§9).

### 4.5 The pump: `UpdateDialog` (`0x004cd580`) and the node-running test (`0x004cd2d0`)

Every frame, for the owner: start a pending lip-sync once its VO is playing (§7); freeze hostiles
(§4.9); then, if not paused and the node is over and a step is pending: if this is not an
animated cutscene and the VO was cut while the stream still plays, wait; else run the pending
step (an entry, or the replies). If no step is pending and the dialogue's "ending" flag (`+0x60`)
is set and the VO has stopped, leave the conversation. (high)

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

**Skipping** a line: while an entry plays, the dialogue panel turns the accept event (0x27 /
0x2d, click or Enter) and the left-press event 0x1f9 into a skip request
(`CServerExoApp::RequestDialogSkip` `0x004ae970` → owner `+0x1f4` = 1) (`CSWGuiDialog::
HandleInputEvent` `0x006a7230`; see gui.md for the event codes). Non-`Skippable` DLGs ignore it.
The request is cleared when the next entry runs. (high for the effect, med for which panel state
bits gate it)

### 4.6 Replies (`SendReplies` `0x005a3820`, `SendRepliesToPlayer` `0x005a1c00`)

For the current entry (high):

1. For each link in order: run `Active` (OBJECT_SELF = owner). Passing replies are listed in link
   order. Failing ones are dropped, unless the link has `DisplayInactive` = 1, in which case they
   are appended after the passing ones (shown but not selectable; no shipped DLG uses the field).
2. **Error rule**: if the list mixes empty-text and non-empty-text replies, the conversation is
   aborted with "CONVERSATION ERROR: Last Conversation Node Contains Either an END NODE or
   CONTINUE NODE. Please contact a Designer!" (`CGuiInGame+0xb14/+0xb18`). Six shipped DLGs
   contain such an entry.
3. No passing reply, or exactly one that links to no entries → set the dialogue's **end flag**
   (`+0x6c`) (the conversation will end normally after this).
4. With no player registered the first passing reply is picked at once (a multiplayer leftover:
   StartConversation always registers the local player).
5. Otherwise each reply's text (gendered), listener, AnimList, camera and fade fields go to the
   client (`CameraAngle` 0 resolved, §9.1), unequip lists applied, and `CGuiInGame::
   SetDialogReplies` (`0x006340e0`) shows them. With **zero** passing replies the client gets a
   single empty placeholder.
6. Dialogue `+0x68` = 1 (replies out), `+0x74` = −1 (nothing chosen).

Client (`SetDialogReplies`, high):

- **A single empty reply** (the "[continue]" link, and the placeholder above) is selected
  automatically without input: the conversation flows on as soon as the entry is over.
- Otherwise the list is shown and input enabled. Events 0xfe..0x106 pick reply n − 0xfe
  directly (presumably the number keys 1–9, med); up/down and accept select one (`0x006a7230`).
- While the list is up the shot shows the PC (or the party leader with `bUseLeader`, or when the
  player is not controlling the PC) speaking to the last speaker, using **reply 0's** camera
  fields.

### 4.7 Choosing a reply (`HandleReply` `0x005a03c0`)

A **clicked** reply (`SelectDialogReply` `0x006339c0`): the reply text replaces the message, its
AnimList plays, and `HandleReply` runs with "no reply timer", so the next NPC line follows
immediately. An **auto-selected** reply (single empty one) goes through `SpeakDialogReply`
(`0x00633660`): the PC becomes speaker, the reply's own listener/camera/animated camera/fade apply,
and `HandleReply` runs **with** the reply timer, so a reply carrying `Delay`, `WaitFlags` or a
camera animation holds the scene (that is how cutscene DLGs chain shots through empty replies).
(high)

`HandleReply` order (high):

1. Ignore stale selections (not for the current entry, or a reply already chosen).
2. Link index out of range or the PC gone → fail.
3. `+0x74` = link; for each player: apply the reply's `Quest`/`QuestEntry`; award its plot XP.
4. Unless "no reply timer": node duration from the reply (§6, reply table); owner `+0x5c` = the
   reply's WaitFlags (0 in an `AnimatedCut` DLG).
5. Run the reply's `Script`.
6. Take the first of the reply's entry links whose entry speaker is available (§5.1) and whose
   `Active` passes, and run that entry (deferred until the reply's node is over).
7. None → end flag and "ending" flag; return failure, which ends the conversation **normally**.

### 4.8 Journal and plot XP

- `Quest`/`QuestEntry` (`UpdateJournal` `0x0059ef00`, med): with a non-empty `Quest`, for the PC
  and then each other party member: if the journal's current state id for that quest tag is
  **lower** than `QuestEntry`, set it (with the current world date and time). The journal never
  moves backwards from a DLG. A changed quest with a plot index also awards that plot's XP and
  posts the "journal updated" feedback (`CGuiInGame` `0x0062eeb0`). Journal storage is
  party-items-saves.md.
- `PlotIndex`/`PlotXPPercentage` (`AwardPlotXP` `0x0059f3c0`, med): when `PlotIndex` ≠ −1 and
  the percentage > 0, call the party's plot-XP award (`0x005666e0`) with the plot index and
  percentage × 100 as an integer percent. The XP formula is rules.md's.

Both happen when the node is shown (entries) or chosen (replies), before the node's script.

### 4.9 Ending

`EndConversation` (`0x005a0a40`, high):

- **Normal end** (end flag set: the last entry had no usable replies, or the chosen reply led
  nowhere): run the DLG's `EndConversation` script (once), then run the end-of-dialogue script
  of **every creature** (`ScriptEndDialogue`, `0x004ef910`) and **every placeable**
  (`OnEndDialogue`, `0x00585460`) in the owner's area. (After a one-liner: only the owner's.)
- **Abort** (anything else, or any later call once the normal end has run): run only
  `EndConverAbort`.

Then the dialogue is cleared (`0x005a27b0`): the owner's AI level is restored, participants and
players are released (`+0x54` = invalid, activity bit 4 cleared), the panels close, the owner's
`+0x214` is set and the client deletes the dialogue next frame.

**What ends a conversation early (abort path)** (high unless noted):

- a node's speaker is not available (§5.1), or an entry/link index is bad;
- the owner, the PC or a player participant leaves: activity bit 4 cleared, which happens when
  that creature starts casting a power, counterspells, attacks (`ClearActivities` kinds 1 and 4,
  actions.md), starts another conversation, or a script/feature clears it;
- the panel is closed with the abort code (−3 → `HandleReply` with abort set, which clears the
  PC's bit 4) (med: which key produces −3 was not traced);
- `ResetDialogState` (749) just clears the pending flag (does not end the owner's dialogue).

Moving, picking up items, equipping and other kind-2/8 actions do **not** end a conversation,
and apart from the participant check (§5.1) nothing tests distance once it has started.

**Hostiles freeze** (`FreezeHostiles` `0x005a0940`, high): every frame of a conversation, every
creature in the area that is not under the player's control and whose reputation toward the PC
is ≤ 10 (hostile) has its actions cleared and its movement stopped.

It is nothing but that per-frame `ClearAllActions(1)` (plus the client creature's
`CancelServerActions`): no suspended queue, no flag on the creature, nothing to undo. It runs from
`UpdateDialog` (4.5), which returns before it unless the owner's `+0x54` names the owner itself,
so it stops the frame the dialogue is cleared. And a conversation whose last reply leads nowhere
is cleared in the very call that handled the reply: `HandleDialogReply` (`0x004cb480`) runs
`HandleReply` (the reply's script among it) and, when that returns 0, `EndConversation` (the
DLG's end script, then every creature's end-of-dialogue script) and clears the dialogue, all
before the next frame. So what the last reply's script orders of a hostile (the Great Beast's run
to `kas25_wp_wraid3` in `k_pkas_wraidattk`, an `AssignCommand` that is delivered on the next
server update) is never cleared by the freeze; an order given by an *entry* script, or by a
reply that leads on to another entry, is cleared on the next frame.

**Action queues**: starting a conversation clears the actions of the party leader
(`ActionStartConversation`) and of both sides (`BeginConversation`); participants found by tag
are not cleared. NPC scripts in node `Script`s commonly queue actions on participants; those run
normally during the conversation.

### 4.10 Pause and resume

- `ActionPauseConversation` (205, `0x0052d330`) acts at once (nothing is queued): if OBJECT_SELF
  is commandable and alive, set its `+0x50` (paused) and lock activity bit 4 (`+0xa00` bit 4) so
  the actions it performs meanwhile don't end the conversation. (high)
- `ActionResumeConversation` (206, `0x0052d520`) queues action 0x20 (`0x0057b320`): clear `+0x50`
  and the lock, drop activity modes. (high)

While paused, no pending step runs: the current line stays (or the replies don't appear) until
the resume action runs. The owner must be OBJECT_SELF for this to matter (it is in shipped
scripts).

## 5. Speakers, listeners, participants

### 5.1 Finding an object by tag (`GetParticipant` `0x0059fc30`)

Used for `Speaker` and `Listener` tags (high):

1. Look in the conversation's cache of tag → id pairs (filled as tags are resolved, `+0x84`).
2. Else: the owner's own tag → the owner; otherwise the **nearest object with that tag in the
   owner's area within 1000 m** (`GetNearestObjectByTag` `0x004cb5c0`, case-insensitive), and
   cache the answer (even "not found").
3. Accept it only if it is in the owner's area and within 1000 m of the owner, and it is not
   taking part in another conversation (`+0x54` names an owner whose own `+0x54` matches). A
   stale `+0x54` is cleared.
4. A free object **joins** this conversation (`+0x54` = owner; creatures drop activity modes and
   set bit 4). An object that has moved out of range or area is released and refused.

`GetNearestObjectByTag` quirk: after the first match it compares later candidates' squared
distance with the previous match's plain distance, so the "nearest" pick is not exact when
several objects share a tag (low impact; reproduce if exactness matters).

`Speaker` is never `PLAYER`/`OWNER` in the shipped data and the engine has no keyword for it: an
empty `Speaker` means the owner. The PC never speaks entries.

### 5.2 The client's speaker/listener (`ShowDialogEntry`, `SetDialogReplies`, high)

`CGuiInGame` keeps current speaker `+0x170`, current listener `+0x174`, previous speaker `+0x178`,
previous listener `+0x17c`, and "the player" `+0x184`. For an entry:

- First line of the conversation: player = the PC; listener = the node's listener, or the PC.
- Later lines: listener = the node's listener if set; else the PC if the speaker hasn't changed,
  else **the previous speaker**.
- Speaker = the node's speaker; previous values shift down.

For the reply list (and a spoken reply): speaker = the PC (or the party leader, see §4.6),
listener = the reply's listener or the previous speaker.

### 5.3 Party members and others

Party members take part only as tagged speakers/listeners, `NPC1`/`NPC2` AnimList participants,
or stunt participants; nothing else pulls them in. Names passed to `ActionStartConversation` as
"objects to ignore" only exempt AnimList participants from the readiness wait (§4.4).

## 6. Timing

Node duration (`RunEntry` / `HandleReply` → `SetNodeDuration` `0x0059ff50`, high):

Entries:

| Entry | Duration (seconds, from the moment it is shown) | Held longer by |
|---|---|---|
| explicit `Delay` d (WaitFlags 0x10) | d (VO or not) | any WaitFlags data bits |
| voiced (file found), Delay −1 | 0.01 (minimum) | WaitFlags 2: until the VO stops |
| sound set but file missing, Delay −1 | text timer | |
| no sound, Delay −1, WaitFlags 0 | text timer | |
| no sound, Delay −1, WaitFlags set | 0.01 | the WaitFlags conditions |
| `AnimatedCut` DLG, no VO, Delay −1, WaitFlags 0 | 0 | |

Replies get a timer only when spoken automatically (§4.7); the test is different (bit 2, not
0x10):

| Reply | Duration |
|---|---|
| WaitFlags bit 2 (a reply with a sound and Delay −1) | its Delay (`DelayEntry`, 0) |
| no sound, Delay −1, WaitFlags set | 0 |
| anything else, **including an explicit `Delay`** | text timer (0 for the usual empty text; 0 in `AnimatedCut` DLGs) |

So an explicit `Delay` on a reply is ignored (18 shipped replies carry one). (high)

An explicit `Delay` also drops the "wait for the voice" bit. The data uses this on purpose:
`Delay` 0 on a voiced entry that leads to real choices (357 entries) makes the reply list
appear at once while the voice keeps playing; with the default −1 (6120 such entries) the list
waits for the voice. The stream is only replaced when the next voiced line starts, so a voice
keeps playing over the reply list and over unvoiced lines. (high for the mechanism, the intent is
inferred from the data)

- **Text timer** = `floor(len(text) × 0.11 + 1.0)` whole seconds, 0 for an empty text
  (`CExoLocString::GetDisplayTime` `0x005ea270`, truncated by `_ftol`); `len` is the gendered
  text in the PC's language, before token substitution. Shipped no-VO entries give 1..23 s,
  median 5 s.
- The 0.01 s minimum is skipped for replies and in `AnimatedCut` DLGs.
- With no player registered (never in single player), a node with links uses the TLK sound
  length of its text, or 0.1125 s per character when that is under 0.15 s.
- End time = world time now + duration × 1000 ms; world time is the server's (it stops when the
  world timer is paused, gameloop.md).

`WaitFlags` bits (data uses 0, 1, 8 and 9): **1** camera animation, **8** dialogue fade; the
engine adds **2** (voice) and **0x10** (explicit delay); **4** (dialogue animations) exists but no
file sets it. (high)

## 7. Voice-over and lip sync

- **Path** (`RunEntry`, high): a sound resref of 16 characters starting with `n`/`N` whose second
  character isn't `_` is a module VO line: `HD0:STREAMWAVES\<chars 1-5>\<chars 6-11>\<resref>`;
  anything else is `HD0:STREAMWAVES\<resref>`. The file is tried with the MP3 extension (resource
  type 8) first, then WAV (type 4). (The file is MP3 inside a RIFF header, lip.md.)
- **Playback** (`PlayDialogVoice` `0x0062e1d0`, high): one stream (`CGuiInGame+0xb40`, sound
  category 9) replaces the previous line's. If neither file plays, the resref is handed to the
  speaker's creature-sound/lip slot directly. On success the lip sync is armed (`+0xbdc` speaker,
  `+0xbe0` resref) and started by `0x0062fa30` on the first frame the stream really plays.
- **LIP** (`CSWCCreature::PlayLipSync` `0x00616310`, vtable slot 0x128, high/med): loads
  `<resref>.lip` (LIPs live in `lips/*_loc.mod` and `lips/localization.mod`, lip.md); keys become
  normalised times `time / length` and pose values `(shape + 1) / 16`; it plays only if the first
  normalised time is 0 and the last is 1 (±1e-5). The head's and body's `talk` animation is
  driven by a lip track (`0x00485130`): at elapsed time *t* it finds the bracketing keys and
  **linearly** blends the `talk` pose sampled at `pose × talkLength` of the two keys; past the end
  it holds and fades the track out. So shape *s* = `talk` sampled at **(s+1)/16 of its length**,
  not *s*/30 s as lip.md assumes (med; see Open questions). A missing LIP leaves the mouth still.
- **No LIP, no VO**: the mouth does not move; the speaker still loops its talk animation (§8.1).
- Bark sounds (`Sound` on one-liners, TLK sounds) and `SpeakString` chat sounds play on 3D
  sources at the speaker and also start lip sync through the same slot (med).

## 8. Animations, facing, equipment

### 8.1 AnimList and default animations (`UpdateDialogAnimations` `0x006313a0`, high)

- Participants listed for the previous line but not this one go back to animation 10000.
- A listed participant is (re)started only when new or when its number changed: the same
  looping number on consecutive lines keeps playing without a restart.
- Looping animations (`IsLoopingDialogAnimation` `0x0062d5e0`): clear the head look-at, reset,
  then loop. Fire-and-forget (`0x0062d700`): play once (cutscene numbers 1000..1327 get extra
  preparation).
- Participants without an entry: the **speaker loops 10038 (`Talk_Normal`)** and the **listener
  loops 10030 (`Listen`)**; a creature under 20 % HP (`0x004eff30`, `0x007a1b38` = 0.2) uses
  10154 `Talk_Injured` / 10155 `Listen_Injured`. Dead creatures are left alone.
- **`CanAnimateParticipant` (`0x0062f0e0`, med) gates every one of these**: the AnimList entries, the
  back-to-10000 of the previous line's cast, the talk and listen loops, and the stand-up of
  everyone at the end of the conversation (`0x00631b70`, `0x00631c60`, reached from the
  in-game GUI's end-of-dialogue function `0x006332b0`). It answers no for a creature that is
  dead, helpless (`GetIsHelpless`: held in a SETSTATE, or dying) or a downed party member, so a
  creature that died during the conversation lies where it fell through every later line and
  the end. Ours: `fight::can_animate_participant`, asked by `lib/dialog/view`.
- The server side agrees: `CSWSCreature::SetAnimation` (`0x004f0d70`) drops any animation but the
  three dead ones (10006, 10008, 10156) on a dead or dying creature, and turns 10000 into the dead
  pose of the way it fell (animation state `+0x4c4`: 4 gives 10006, 3 gives 10008, 14 gives
  10156), so a script's `ActionPlayAnimation` or an idle reset cannot stand a corpse up either.
  Ours: `world::set_animation` ignores everything but `fight::is_dead_pose` on a dead creature.

Animation numbers (`GetCutsceneAnimationName` `0x006288f0` and the tests above, high):

| Number | Meaning |
|---|---|
| 10000 + r | `dialoganimations.2da` row r (`name`, `looping`, `fireforget`, `dialog`, `overlay`, `cu_pb_range`) |
| 1000 + k | model animation `cutNNN`, NNN = k+1 (k 0..127) |
| 1200 + k | `cutNNNw` |
| 1400 + k | `cutNNNl` (looping) |
| 1600 + k | `cutNNNwl` (looping) |
| 10098 | "none" |
| other | `animations.2da` row (the small numbers 35..70 in the data) |

Exe quirk: k = 28 yields `cut039` in every block instead of `cut029` (reproduce if a model has
`cut039` but needs `cut029`; no shipped number hits it, low). Loop vs. once for cutscene numbers:
1400..1727 loop, 1000..1327 once. "Still playing" for WaitFlags 4 = any participant whose
current animation is a dialogue fire-and-forget or looping one (`0x0062d570`).

### 8.2 Facing (`SetDialogCamera` `0x006306e0`, first half, high)

Not in `AnimatedCut` DLGs or the computer panel. For each line the listener turns toward the
speaker and then the speaker toward the listener:

- If the creature is not orientation-locked (`SetLockOrientationInDialog` list) and has a head
  that can track: compute the angle between its facing and the direction to the other. If it
  exceeds the head's horizontal arc (`appearance.2da` `HEAD_ARC_H`, default 40°) the **body turns
  by (angle − arc − 1°)** toward the other, so the head can cover the rest.
- If head-follow is not locked (`SetLockHeadFollowInDialog` list), the head looks at the other
  (look-at with 10.0 as the turn parameter, med); if that fails or head-follow is locked the
  body turns fully to face the other.
- Orientation is set on both the server object and the client object (no turning animation
  here; the client's own turning smooths it, med).

Previous speaker/listener's head look-at is cleared first.

### 8.3 Equipment

`UnequipItems` (`0x005a0ba0`): each speaker, listener, PC and AnimList participant of each node
has its equipment hidden on the client once per conversation. `UnequipHItem` (`0x005a0d10`): the
held weapon is hidden. They come back when the conversation ends (med).

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

The cycle (dialogue `+0x9c` index, `+0xa8` table, ctor `0x005a0e80`): table = 1, 3, 1, 3, 2, 2,
1, 3, 1, 2, 1, 2, 1, 3, 2, 3, 1, 1, 1; the index starts at 0 and steps **down** by one per sent
node (wrapping 0 → 18), and it steps for **every** entry sent and every reply list sent,
whatever their `CameraAngle`. Each node reads the table at the current index, then steps. The
first entry and the first reply list each take 2 instead (flags `+0xf4`, `+0xf8`). So the
second node with angle 0 gets table[18] = 1, then 1, 1, 3, 2, 3, 1, 2 … (high)

Client order for a cinematic line (`ShowDialogEntry`): try the animated camera first, **whatever
the angle** (§9.4); if it doesn't apply, enter the dialogue camera mode once per conversation
(`CSWCModule::EnterDialogCameraMode` `0x006412f0`, which installs a `CSWCDialogCamera` with the
DLG's `OldHitCheck`) and call `SetDialogCamera` with the angle. In the computer panel only angle 6
does anything (§9.7). (high)

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
  `cu_pb_range` (`dialoganimations.2da`, default animation 10038 → 0), kept while it stays > 0.
- **Angle 2 (over the shoulder)**: P = L + 0.3·(S − L) (after the z tweaks above), the look-at
  point T = P with z + `TarHeightOffset`; v = (S − L) rotated ±30° **about z, not normalised and
  with its z** (so |v| = d, the distance between them); camera = T − 0.8·v − 0.15·normalise(v)
  (normalised in 3D), then z += `CamHeightOffset`. The camera backs off by 0.8 of the distance
  between them plus 15 cm: 1.75 m for two creatures 2 m apart.
- **Angle 3 (wide)**: P = midpoint; v = (S − L) rotated ±90° about z, **not normalised** (|v| = d);
  T = P with z − 0.2·d + `TarHeightOffset`; camera = T − 1.5·v, then z += 0.3·d +
  `CamHeightOffset`. The camera stands 1.5 distances to the side (3 m for 2 m apart, 13.5 m for 9 m
  apart) and 0.1·d over their eyes, looking 0.2·d under them. (Both come from the decompile, which
  normalises v only in angle 1 and in angle 2's 0.15 term; this page used to say v was unit
  length, which put a wide shot of two creatures 9 m apart 1.5 m to the side and 2.7 m up, looking
  at the floor.) The camera's z starts from the look-at point's z in every angle, so
  `TarHeightOffset` raises the camera as well.
- If S and L coincide, L is replaced by S + (1.5, 1.5, 0.1) and the close-up formula is used.
- Orientation: yaw = heading of v (`atan2(−x, y)`), pitch = elevation of (target − camera) +
  90°, roll 0, built as Rz(yaw)·Rx(pitch) (`Quaternion_FromEulerDegrees` `0x004acac0`; the camera
  looks down its −z at pitch 0).
- **Obstruction**: after computing a new shot, `SetShot` ray-tests it against the scene, ignoring
  both participants' models and heads (angle 3: three rays; other angles: one). Any hit marks the
  shot blocked (`+0x34`), and a blocked shot is computed with the **close-up formula without
  pull-back** for the rest of the line. With `OldHitCheck` = 1 the close-up uses a fixed 0.5 m and
  no pull-back, and a blocked camera is moved to 0.1 m in front of whatever the ray from the
  target hit. (high for the flag and the fallback, med for the ray end points)
- The camera **re-frames every frame** from the participants' current positions (`Update`
  `0x006bcf50`), so it follows moving speakers. Changes between shots are **cuts**; there is no
  interpolation. (high)

### 9.3 The side (180° rule)

`GetSide` (`0x006bcec0`): the side is chosen once per speaker/listener pair and cached (four
pairs); the same pair the other way round gets the opposite side, so the camera stays on one side
of the line between two characters. A new pair's side is picked by `ChooseSide` (`0x006bc600`):
compute the angle-3 and both angle-2 shots for each side, count how many of their ray tests hit
scene geometry, and take the side with fewer hits (side 2 on a tie, med). With `OldHitCheck` the
cache is used as stored.

### 9.4 Animated cameras (angle 4, `CameraModel`)

`CGuiInGame::TryAnimatedDialogCamera` (`0x0062bf70`, high): applies when the DLG's camera model
is loaded and 1000 ≤ `CameraAnimation` < 1728. Then `CSWCModule::PlayCameraAnimation`
(`0x00641010`): clip planes 0.1 / 10000, the camera model is placed at the area origin with no
rotation, the game camera is attached to the model's `camerahook` node, and the model plays the
animation named as in §8.1 (`CameraAnimation` 1200 → `cut001w`), looping for 1400–1727, else
once. `CamFieldOfView` > 0 sets the FOV; −1 keeps it. WaitFlags bit 1 holds the node until the
model's animation ends (`0x006412b0`). 10098 ("none") and values outside the range fall back to
the framed/static camera with the node's angle. Stunt models (§2.7) carry matching `cutNNNw`
animations on the participants, started by the AnimList.

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
- then `CamVidEffect` (unless −1/−2) enables that `videoeffects.2da` row (§9.6).

`SetDialogPlaceableCamera(n)` (461, `0x00546a80` → `0x0062e900`) does the same from a script,
only while a conversation is active.

### 9.6 Fades, video effects, letterbox

- **Node fades** (`ShowDialogEntry` / `SpeakDialogReply`): `FadeType` 0 none; 3 → fade **in**
  over `FadeLength` after `FadeDelay`; 4 → fade **out**; 1 → out with length 0 (instant black);
  2 → in with length 0 (instant clear); colour `FadeColor` (RGB 0..1), on the dialogue fade panel
  (`CGuiInGame+0x68`, `0x006a7620`). WaitFlags 8 waits for it. (high for the mapping, med for
  the panel's own timing, gui.md)
- **Global fades** (`SetGlobalFadeIn`/`Out` 719/720, `0x00546010`/`0x005460d0`): the same fade
  widget on `CGuiInGame+0x6c` with (in/out, wait, length, colour). `HoldWorldFadeInForDialog`
  (760, `0x00547e30`) sets `+0xb98` so the next conversation's first line fades in from black
  over 1 s. (high)
- **Video effects**: `CamVidEffect` on a static-camera node, or `EnableVideoEffect` (508,
  `0x005471e0` → `0x005f7710`), read `videoeffects.2da` row n (`EnableScanNoise`,
  `EnableSaturation`, `Saturation`, `ModulationRed/Green/Blue`) into the client (`+0x3a8`);
  `DisableVideoEffect` (510) sets −2. Framed shots turn the effect off (`0x005edf20`). (high)
- **Letterbox**: the cinematic panel is `dialog.gui` (`CSWGuiDialogLetterbox` `0x006a8b40`): the
  bars, `LBL_MESSAGE` for the line and `LB_REPLIES` for the replies (render-gui.md, gui.md).
  The computer panel is `computer.gui`; with angle 6 it is swapped for `computercamera.gui` so
  the 3D view shows (§9.7).

### 9.7 Computer conversations (`ConversationType` 1)

Panel `computer.gui` (`CSWGuiDialogComputer`, created on first use, `ComputerType` 0/1 picks the
skin). Lines and replies are text in the panel; facing, framed shots and animated cameras are
skipped. A node with `CameraAngle` 6 swaps in the `computercamera` panel and places the static
camera (`SetComputerStaticCamera` `0x0062c030`); the next node without it restores the computer
panel (med). (high otherwise)

## 10. Barks, speech, one-liners, cutscenes, movies

### 10.1 Bark bubbles

Sources (high): a one-liner DLG (§4.1, `PlayOneLiner` `0x005a1050`), `BarkString(o, strref)`
(671, `0x00548900`) and `ActionBarkString(strref)` (700, `0x0052c6a0`, action 0x3e
`0x0057ce00`). The two script commands do nothing while a conversation is active.

- Text: the node's gendered text (one-liner) or the TLK string; sound: the node's sound, else
  the TLK entry's sound resref.
- One-liner speaker quirk: the bubble's speaker comes from **entry 0's** `Speaker` (not the
  chosen entry's): empty → the owner, else the object with that tag nearest the PC (no range
  limit). Shipped one-liners have empty speakers.
- After the bubble the one-liner ends: the DLG's `EndConversation`, the owner's own
  end-of-dialogue script, then `EndConverAbort` (§4.1).
- The bubble (`barkbubble.gui`, `CSWGuiBarkBubble` `0x006a9770`, `CGuiInGame+0x4c`): **one at a
  time** (a new bark replaces the text and stops the old sound); text token-parsed, height = text
  height + 10 + 2 × border; duration = `len(text) × 0.11 + 1.0` s (not truncated). It stays while
  its sound plays; otherwise (or after the sound) the duration counts down by the frame time
  (frames under 1.5 s only) and the bubble closes at 0. It is hidden (not closed) while the
  speaker is 6 m or more from the party leader. Position: the panel's `.gui` extent, not above the
  speaker (med). The sound is a 3D source at the speaker (category 0x1a, volume 127, med).
- The message-log copy of barks is behind a flag nothing sets (`0x00833a9c`, low).

### 10.2 `SpeakString` family

`ActionSpeakString` (39, queued as action 0xe `0x0057b430`), `SpeakString` (221, immediate), both
`0x00544090`; `ActionSpeakStringByStrRef` (240, action 0x21 `0x0057b3d0`). Talk volume → chat
type and ranges (`0x00571960`, med-high):

| Volume | Players who see the text | Listeners who can hear it (patterns) |
|---|---|---|
| TALK | same area, within 1000 m | 1000 m |
| WHISPER | within 3 m | 3 m |
| SHOUT | all players | 250 m |
| SILENT_TALK | none | 35 m |
| SILENT_SHOUT | none | 1000 m |

Hearing (`0x004cd760`): objects with listening on (`SetListening`) within range whose patterns
match (`SetListenPattern`, `0x004cd700`); a creature must perceive the speaker by hearing (silent
types: by sight, or within 10 m). A match signals `ON_DIALOGUE` with the pattern number (med).
The client shows "Name: text" as floating text 2 m above the speaker and plays any sound with lip
sync (med).

### 10.3 `SpeakOneLinerConversation` (417, `0x00543f70` → `0x004cb220`)

Loads the DLG (argument, else `GetDialogResRef`) without links, takes the first starting entry
with an empty `Speaker`, a passing `Active` and no replies (`0x0059ee00`), sends its text and
sound as chat type 8 to players within 1000 m (gendered by `oTokenTarget`), and runs its
`Script` on OBJECT_SELF. No conversation, no camera. (high)

### 10.4 Cutscene support

There is no cutscene mode flag in KOTOR; cutscenes are conversations with `AnimatedCut` = 1, a
`CameraModel`, `StuntList`, `CameraAngle` 4 entries chained through empty replies, and `Delay` /
`WaitFlags`. `AnimatedCut` changes (high): no facing, no 0.01 s minimum and zero text timer, reply
WaitFlags ignored, the VO-still-playing wait before advancing is skipped. Scripts add:

| Routine | Handler | Effect |
|---|---|---|
| `SetDialogPlaceableCamera` 461 | `0x00546a80` | static camera, §9.5 |
| `SetLockOrientationInDialog` 505 / `SetLockHeadFollowInDialog` 506 | `0x005470e0` / `0x00547160` | add/remove the object in `CGuiInGame+0xb44` / `+0xb48` (adding to the head list also clears its look-at), §8.2 |
| `CutsceneMove` 507 / `CutsceneAttack` 503 | `0x0052e950` / `0x0052e890` | scripted move/attack through the combat round (combat.md) |
| `EnableVideoEffect` 508 / `DisableVideoEffect` 510 | §9.6 | |
| `SetGlobalFadeIn`/`Out` 719/720, `HoldWorldFadeInForDialog` 760 | §9.6 | |
| `SetCameraMode` 504 | `0x00542640` | camera mode message (movement.md) |
| `ResetDialogState` 749 | `0x00547bc0` | clears the pending flag |
| `CancelPostDialogCharacterSwitch` 757 | `0x00547d20` | forget the creature to return control to (§2.3) |
| `PlayMovie` 733 | `0x00540ed0` | synchronous: input reset, sound mode 3, play, sound mode 0 (app.md) |
| `QueueMovie` 769 / `PlayMovieQueue` 770 / `IsMoviePlaying` 768 | `0x00548210` / `0x005482d0` / `0x005481e0` | movie queue (app.md) |

`Mod_CutSceneList` in the IFO is read by the module loader (modules.md); nothing in the
conversation code uses it (low: not traced further).

## 11. Script routines

| # | Routine | Handler | Behaviour |
|---|---|---|---|
| 204 | ActionStartConversation | `0x0052d5b0` | §2.2 |
| 205 / 206 | ActionPause/ResumeConversation | `0x0052d330` / `0x0052d520` | §4.10 |
| 255 | BeginConversation | `0x0052e9f0` | §2.5 |
| 238 | GetPCSpeaker | `0x0053c9c0` | always the party leader (high) |
| 254 | GetLastSpeaker | `0x0053b410` | creature `+0x17c` (high) |
| 295 | EventConversation | `0x005358c0` | an empty script event of type 7 (high) |
| 445 | GetIsInConversation | `0x0053eec0` | the object's `+0x54` names an owner whose `+0x54` is the same (high) |
| 701 | GetIsConversationActive | `0x0053ef70` | `CGuiInGame+0xb4` (high) |
| 711 | GetLastConversation | `0x0053f010` | the resref of the last `ON_DIALOGUE` (high) |
| 417 | SpeakOneLinerConversation | `0x00543f70` | §10.3 |
| 39 / 221 / 240 | ActionSpeakString / SpeakString / ActionSpeakStringByStrRef | `0x00544090`, `0x00544270` | §10.2 |
| 671 / 700 | BarkString / ActionBarkString | `0x00548900` / `0x0052c6a0` | §10.1 |
| 461, 503–510, 719, 720, 733, 749, 757, 760, 768–770 | | | §9, §10.4 |

## 12. Corpus facts and corrections to gff-dialog.md

Counted over the 1146 distinct DLGs in the install (`kotor/re/scratch/dlgstats.py`, git-ignored):

- `ConversationType`: 0 in 730, absent (= 0) in 163, **2 in 139**, 1 in 114. Type 2 = "always a
  real conversation, never a bark" (§4.1), used by party-member and plot DLGs.
- `OldHitCheck` 1 in 27 DLGs = use the older framing without `CAMERAHOOK` nodes or side cache
  (§9.2), not a line-of-sight start check.
- `CameraAngle` entries: 0 18815, 6 3207, 1 1428, 2 272, 3 258, 4 232, 5 24; replies: 0 26448,
  1 461, 6 417, 5 20, 2 13, 4 5, 3 2. Angle 5 = "keep the shot" (§9.1).
- `FadeType` 1 (17 entries, 62 replies) = instant fade out; 2 = instant fade in (unused).
- `SoundExists` on entries: 1 13855, 3 6550, 0 1233, 2 24, absent 2574. Bit 1 forces the
  subtitle on (§4.4).
- `Delay`: 0xFFFFFFFF on 22910 entries; explicit values 0..20 s otherwise. 0 on 893 entries:
  0.01 s, i.e. go on at once (with VO: replies shown while it plays, §6); the larger values sit
  mostly on silent pass-through entries with a single empty reply (cutscene beats).
- `WaitFlags`: entries 0/1/9, replies 0/1/8 (§6).
- One-liners: 767 starting entries have no replies and 1149 have one reply leading nowhere; all
  of them bark unless their DLG is type 2.
- Single empty-text replies (auto-continue): 16284. Entries mixing empty and non-empty replies
  (engine error): 6 (`dan14_elise`, `dan14_cutscene`, `kas22_dasol_01`, `kas23_chuunda_01`,
  `man26_manmerc`, `tat17_griff`); the engine aborts those conversations when such an entry's
  replies are offered with both kinds passing.
- `DisplayInactive`: no DLG has it. `Speaker` is never a keyword; `Listener` `PLAYER` 1716
  entries; AnimList participants: tags 2010, `OWNER` 1363, `PLAYER` 362, `NPC1` 7, `NPC2` 8.

## 13. Open questions

- **LIP pose mapping**: the decompile of the lip track setup (`0x00485130`) was garbled; the
  `(shape + 1) / 16` reading conflicts with lip.md's frame-*s* reading of the `talk` keys (frame 0
  = rest). Check with the disassembly or by rendering a head at both mappings.
- The client modes that make the DIALOGOBJECT action wait (`0x005edad0`, `0x005edc10`, client
  `+0x384` bit 0) and that make `RunEntry` trust `SoundExists` (`0x005ee0d0(8)`) are unnamed.
- The character-switch hand-off (§2.3 step 6) is reconstructed from a tangled decompile:
  positions swapped, fade 0.75 s, leader switch −3 are read; the exact conditions (PartyInteract,
  combat byte at `+0xac0`) are med/low.
- Which key/panel action sends the abort code −3 to `SpeakDialogReply`, and whether Escape
  aborts a conversation (gui.md's 0x28 handling in the dialogue panels was not traced).
- The ray end points of the obstruction tests in `SetShot` and `ComputeShot` (the decompile lost
  the arguments); the tie rule of `ChooseSide`.
- How the dialogue fade panel (`+0x68`) times `FadeDelay`/`FadeLength` (gui.md's fade widget).
- `MicRange` of static cameras: stored, but its use by the sound listener was not traced.
- `Mod_CutSceneList` and `AmbientTrack` stop/restore of the area music (the music stop fades
  over 0.5 s; whether area music is paused meanwhile is not traced).
- The `UnequipItems` restore at the end of the conversation (the add-only lists at dialogue
  `+0x114/+0x118` were read; the restore was not).
- Multiplayer remnants (several players, `+0x8c` "player-only replies") were not followed.
