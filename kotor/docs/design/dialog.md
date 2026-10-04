# Conversations: the flow, the camera, the voice and the panels

How the game runs a DLG: the walk through its entries and replies (`dlg`), what the player sees
and hears while it runs (`dlgview`), and the panels, lip sync and shots those use. Behaviour is
from [re/dialogue.md](../re/dialogue.md) (section numbers below are its) and the formats
[gff-dialog.md](../formats/gff-dialog.md), [lip.md](../formats/lip.md), [tlk.md](../formats/tlk.md);
this page is our design on top. Decisions that aren't the original's are marked *ours*.

## Directories

| Directory | Namespace | What | Depends on |
|---|---|---|---|
| `lib/dialog/core` | `dlg`, `dlgcam` | the loaded DLG (`graph.ctx`), the running conversation and its pump (`state.ctx`, `flow.ctx`), who is who (`resolve.ctx`), barks and one-liners (`bark.ctx`), sound files (`sound.ctx`), the GIT's static cameras (`cameras.ctx`), the shot geometry (`shot.ctx`) | lib/engine; **no scene, audio device or render**: runs in `enginetest` |
| `lib/dialog/view` | `dlgview` | the client half: shots, animations, stunt and camera models, voice, lips, the panels' wiring, notes, input | core, scene, audio, gui, panels, lipsync |
| `lib/dialog/panels` | `dlgpanel` | `dialog.gui` (letterbox) and `computer.gui`, the replies, the bars, the fade layer, the bark bubble; knows nothing of the world | lib/gui |
| `lib/dialog/lipsync` | `lipsync` | a LIP and a time to a mouth pose on a head | lib/formats (lip), lib/mdl |
| `lib/engine/routines/dialog.ctx` | `rt_dlg` | the routines | core |
| `tools/dlgcheck` | | every DLG of the install through the loader; headless scripts (`scripts/`) | |
| `tools/dlgsweep` | | every DLG walked node by node with its scripts run in a fresh module, in parallel: faults, missing routines and scripts, speakers not found ([../dlgsweep.md](../dlgsweep.md)) | |
| `tools/dialogpanels`, `tools/lipcheck` | | the panels and the lip sync on their own, with PNGs / a corpus check | |

The conversation's state is `w.conversation` (`dlg::State`, a World field). The loop calls
`dlg::update` after the server frame (step 7), then `dlgview::pre_sync` before `scene::sync`,
`post_sync` after it, `apply_camera` after `cam::update`, `draw` before the GUI, and gives it events
(`handle_event`, `run_command`) and outbox notes (`take_note`). Without a view (`enginetest`) the
flow runs alone and treats the scene as ready and a voice as lasting its text timer.

## Starting (2.1 to 2.6)

```
ActionStartConversation / a click   -> action DIALOGOBJECT on the actor           (engine's actions.ctx)
DIALOGOBJECT                        -> event 7 ON_DIALOGUE to the target, caller = actor; dlg::note_event
the target's dialogue script        -> (k_hen_dialogue01 when it has none) BeginConversation
BeginConversation (rt_dlg)          -> dlg::begin: owner choice, clears the sides' actions, dlg::start
dlg::start                          -> load the DLG, take both sides in, AI level >= 3 for the owner,
                                       load the GIT's cameras, pick the starting entry, run it
```

- `dlg::order` is the "conversation pending" flag (`GetIsConversationActive`); `ResetDialogState`
  clears it. The ON_DIALOGUE ints are `{-1, -1, private, 1}`; `listen_pattern` = -1 marks a
  conversation for the scripts that test `GetListenPatternNumber`.
- **Owner** (2.5): never the player; the target owns it when the actor is the player or a party
  member. A conversation started by the **player's click** has no resref: `StartConversation` takes
  the owner's own `Conversation` field.
- **Starting entry** (4.1): the first starting link whose entry speaker can be found and whose `Active`
  script returns non-zero (a missing script is FALSE). A starting entry with no replies, or one reply
  that leads nowhere, is a **bark** unless `ConversationType` is 2: its text and sound go to the bubble,
  its script runs, then the normal end and the abort end both run (`finish_one_liner`).
- *ours*: no walk to range first (the action always starts where the actor stands, the original's
  "skip the range test" case, which is every script start); no `bUseLeader` and ignore-name arguments
  yet (the loop in rt_act pops and drops them).

## The graph (`graph.ctx`)

`dlg::load` reads the DLG into flat arrays in the session heap (entries, replies, links, animation
lists; strings are views into the file's bytes) with LoadDialog's rules applied once: **sound beats
VO**, the Delay/WaitFlags defaults (a voiced node with `Delay` -1 gets WaitFlags 2 "wait for the
voice"; any explicit Delay sets 0x10), fade fields zeroed by `FadeType`, `CamFieldOfView` <= 0 is -1,
`CameraID` only for angle 6, links past their target list fail the load (a reply may link one past
the entries). `text_of` gives a node's text for the player's gender: an embedded string for the
table's language, else the talk table's. `tools/dlgcheck` reads all 1,120 versions of the install's
dialogues (the same name in several modules counts per size) with none failing, and its counts match
re/dialogue.md section 12 where they can be compared (139 type-2 dialogues, 6 entries mixing empty
and non-empty replies, camera angle 1 / 3 / 4 histogram exact).

## The pump (`flow.ctx`)

`dlg::update` once a frame (4.5): the player's pick, if any; nothing while paused; nothing while the
node is still running; then the pending step: run an entry, or send the replies, or leave.

- **Running an entry** (4.3): speaker (owner, or found by tag: the nearest in the owner's area, cached),
  listener (`OWNER`, `PLAYER` = the player, a tag), the client-side bookkeeping of who talks to whom
  (5.2), the camera angle (0 = the first node 2, then the 19-entry cycle that steps for every node),
  has-voice (the file exists), subtitles flag, **facing** (the two turn to each other, not in cutscenes
  or terminals; *ours*: the body turns fully, there is no head tracking yet), journal and plot XP
  (a logged hook, see below), the node duration, the entry's script, then `RunDialogReplies`.
- **Node duration** (6): explicit Delay -> that; voiced -> 0.01 s and held by the voice (WaitFlags 2);
  sound set but the file missing -> the **text timer** `floor(len x 0.11 + 1)` s (0 for no text);
  no sound with WaitFlags -> 0.01 s; in an `AnimatedCut` DLG the 0.01 s and the text timer are 0. A spoken
  reply uses the reply table (only a waiting reply uses its Delay).
- **Still running** (4.5): the scene isn't ready; the voice (bit 2); the dialogue animation (bit 4); the
  camera animation (bit 1); the dialogue fade (bit 8); the end time not reached. A view that is attached
  owns the three busy flags; `expect_view` sets them when a node starts so the node cannot end in the frame
  before the view has seen it. A skip request on a `Skippable` DLG stops the voice and ends the node.
- **Replies** (4.6): each link's `Active` in order; passing ones are listed, `DisplayInactive` ones
  appended disabled; empty and non-empty together is the designers' error and aborts; none passing, or
  one that leads nowhere, sets the end flag; **one empty reply is chosen by the engine** (`speak_reply`:
  the player's creature speaks it, with its camera, and it holds the scene by the reply table);
  otherwise the list waits for `choose`. A click replaces the line by the reply and the next entry
  follows at once (4.7). `choose` takes the first entry link whose speaker exists and whose `Active`
  passes; none ends the conversation normally.
- **Ending** (4.9): normal -> the DLG's `EndConversation` once, then `end_dialogue` of every creature and
  placeable in the owner's area; abort -> `EndConverAbort`; either way the owner's AI level goes back, the
  state is cleared and `ended_serial` counts. A conversation does not cross a module change: the loop
  aborts it and `dlgview::leave` lets go of the scene.
- Scripts run with OBJECT_SELF = the owner through `scripts::run` (a nested run on the VM when the
  caller is BeginConversation, with its own engine bind as ExecuteScript does). Every script run and
  node is logged with `--log dialog`: `dialog entry 55 speaker=5 ... "text"`, `dialog condition script
  k_pend_trask00 self=5 -> 1`, `dialog replies 2: 0 1`, `dialog end end_trask01 (normal), 8 nodes shown`.

*Not done*: freezing hostiles every frame (4.9), `UnequipItems`/`UnequipHItem`, `OldHitCheck`'s older
framing, the character-switch hand-off (2.3 step 6), the journal and plot XP (`apply_quest` logs
`dialog journal Q entry N` and `dialog plot xp`; HOOK(journal), HOOK(rules)), `SpeakString`'s
chat types (it shows the bubble for TALK and WHISPER and drops SHOUT), `ActionBarkString` queued
(plays at once), the 6 m rule of bark bubbles.

## The view (`dlgview`)

`pre_sync` -> a conversation begins (open the panels, the tokens, the AmbientTrack) or ends (stunt
models back, animations to standing, voice and track faded, panels closed); the scene gets ready
(`prepare`: the camera model and the stunt models, at most 1.5 s); a new `Line` (the flow bumps
`line.serial`) -> animations, shot, fade, voice, panel text; new `Choices` -> the first reply's shot
with the player speaking, the reply rows; the player's pick in the panels becomes `w.conversation.pick`
(taken by the next pump, which has the VM) and a skip `w.conversation.skip`.

### Animations (8.1)

The node's `AnimList` participants (`PLAYER`, `OWNER`, `NPC1`, `NPC2`, else a tag) get their animation
numbers as the objects' `animation`; the speaker without an entry loops 10038 (talk), the listener
10030 (listen), or the injured 10154/10155 under a fifth of their health; whoever the last line
animated and this one doesn't stands again. `animname::name_in` names a number: the table's entries,
the cutscene animations `cutNNN`, `cutNNNw`, `cutNNNl`, `cutNNNwl` (1000..1727), and rows of
animations.2da (`10000 + row`, or a small row number). The scene plays it on the visual's body
(`visual::animate_creature`); a one-shot dialogue animation holds its last pose until the next line
(*ours*).

### Shots (9)

`set_shot` for each line: the cutscene's **camera model** first, whatever the angle, when the node has a
`CameraAnimation` in 1000..1727; else by `CameraAngle`: 1 close-up, 2 over the shoulder, 3 wide, all
rebuilt **every frame** from the two eye points (`dlgcam::close_up`, `shoulder`, `wide`; the formulas of
9.2); 5 keeps the shot; 6 a GIT camera (`dlg::camera_by_id`, `dlgcam::static_rig`: yaw, pitch and roll
from the orientation, the camera's `Pitch` added to the pitch, `Height` to z); computers move the camera
only for 6. The **side** of the line the camera keeps to is cached per pair of speakers and chosen once by
counting walls in the way of the wide and both shoulder shots (9.3); a shot whose camera is in a wall
falls back to the plain close-up for the line (9.2). A cutscene's replies picked by the engine don't cut
away from the running camera animation (*ours*). `apply_camera` then writes eye, direction, **up** and field
of view into the chase camera (`cam::Camera.up`, new), which resumes when the shot ends. It runs after
`cam::update`, so the chase camera's four-ray obstruction test (`ResolveCollision`, a `CSWCChaseCamera` method
that only `CSWCChaseCamera::Update` calls) never moves a dialogue shot, as in the original, whose
`CSWCDialogCamera` has only `SetShot`'s own ray tests and the close-up fallback; the scene's
visibility follows the camera's room (`view_room`). *ours*: an eye point is the model's `camerahook`, else
the head hook's place in its pose plus 0.1 m (the appearance table's `height` gave Trask 1.0 m and the
player 1.6 m).

### Cutscenes: camera model and stunt models (2.7, 9.4)

`CameraModel` (`m01aa_c01_cam`) is a scene part of its own at the area origin; its `camerahook` node's
world matrix is the camera (it looks down -Z with +Y up, like a GUI 3D camera), and the animation
`cutNNNw` is the node's `CameraAnimation` - 1200 + 1. `WaitFlags` 1 holds the node until it is done
(`camera_busy`). A **stunt model** (`m01aa_c01_char01`) has **no meshes of its own** (`render` false on
every mesh): it is the skeleton that carries the scene's `cutNNNw` animations. So the participant keeps
its body and head and plays the stunt model's animation (`Part.source`: `scene::binding_for` looks there
first and binds to the body's nodes by name). The animations are authored in **area space**, so the
visual draws at the origin (`Visual.stunt`) and `cutscenedummy`'s position keys are **not scaled by the
body's `anim_scale`** (that put the sleeping player a metre off his bed). All of this was found on
`m01aa_c01` (the Endar Spire's opening: four camera animations over the sleeping player) and checked
on `STUNT_07`'s `scene_start` (three stunt participants, voiced lines, an AmbientTrack).

**A cut changes the pose at once.** A scene animation is in area space and the body's own animations are not,
so the usual 0.25 s blend into or out of one (or from one shot's `cutNNNw` to the next) lerped the root from
wherever the other left it: the stunt body glided in from the origin (or off screen) at every camera cut, for
8 frames, and a stale `cutscenedummy` position hung on for the blend after a body animation. So
`visual::animate_creature` uses no transition when the animation it starts, or the one it replaces, is a `cut`
one, and a swap or restore of the stunt model resets the part's player (nothing to blend from). The dialogue's
defaults leave a running scene animation alone as well, **inside a cut**: an animated cutscene's line, or a line
with a camera animation, would play the player's talk loop for a frame (the real creature at its own place,
mid-cut), so `update_animations` skips the talk and listen loops for a stunt body that runs one there, and
`set_shot` keeps the running camera animation through such a reply unless the reply starts its own. A line with
a framed or static shot after the cut is the original's ordinary line, whose speaker and listener loop Talk and
Listen. The exemption once held for every line, and the wake-up talk in the Taris apartment (`tar02_carth022`:
two cut entries, then 60 ordinary ones) left the player on its last scene animation for the whole talk, drawn in
area space: the wide and shoulder shots, built on the player's eye, put the camera hundreds of metres from the
apartment (a black screen with some far towers in it). The eye of a stunt body is its head hook (+0.1 m),
which moves with the pose the animation carries through the area; the `camerahook` hangs off the model's root
and stays at the origin. The original's `ApplyStuntModels` (`0x0062c620`) swaps the participant's model parts
(body 0xff, head 0xfe) for the stunt model at the scene setup (where it puts them back is not traced, and what
the original's framed shots take as the eye of a stunt body is open). `--log dialog` has a `dialog camera:` line for every shot (the eye, where it looks, the room
under it, the two participants' eyes), and `sh kotor/tools/camcheck/run.sh` fails on a black or empty shot
(testing.md, "Conversation shots"). Found with a per-frame log of
the object's and the drawn root's place (steps over 0.15 m/frame outside walking), checked on `m01aa_c01`
(the dream), `cut00_convers` and `tar02_carth022` (the apartment wake-up): no multi-frame glide is left.
What remains is a script's `AssignCommand(ActionJumpToLocation)` landing one frame after the line that ran it
(AssignCommand queues for the next frame), which snaps and is off screen in the checked cutscenes.

### No picture between two shots

A cut shows the new shot in the frame it happens in and nothing else before it. Four things used to put an
odd frame in between, found by writing every frame of a stretch to disk (`--screenshot-range`, testing.md) and
looking at the ones that differ from both neighbours:

- **The engine's empty reply.** An entry whose one reply is empty ("continue") is followed by the reply the engine
  speaks for the player, and by the next entry a tick later. The reply's own shot (a computed one of the player
  speaking, from the 19-entry cycle) and animations showed for that frame, with the last line's text still up; in a
  cutscene with static cameras it was a wide shot of two actors between two fixed ones. `is_pass_through`
  (view_line.ctx) shows nothing for such a reply: no text, angle 0, no camera animation, no fade, no animations. A
  reply that has any of those is a real cut and is shown. (The original handles the reply and the entry in one client
  frame; we have them a tick apart, so the view skips the first.)
- **Angle 5 (keep).** The shot kept is the one built for the pair it was built for; `set_shot` took the line's pair
  first, and a framed shot is rebuilt every frame from the pair, so "keep" cut to the other side of the talk.
- **The panel's visibility.** `dlgpanel::update` shows the line or the replies that are set, but ran before this
  frame's `set_line`, so the new text appeared a frame after the shot (a blank bar after picking a reply, the old
  text over the new shot). `set_line` and `set_replies` now apply it themselves (`show_what_is_set`).
- **A cutscene hands over to the next conversation.** The end script of an animated cutscene starts the next
  conversation about 0.1 s later (`k_pend_cut09` delays it), and the picture between was the world's camera with
  the HUD. When an animated cutscene ends the view holds its last shot, bars and stunt bodies for up to 0.4 s
  (`HOLD_SECONDS`, `w.conversation.hold` keeps the HUD away); a conversation that begins meanwhile takes over with
  the bars in already (`hand_over`), the hold runs out into the usual `finish` otherwise, and a module change lets go
  at once (`leave`; the loading screen covers it).

### Voice and lips (7)

One stream in the voice group, replaced only when the next voiced line starts, so it plays on over the
replies and unvoiced lines; found by `dlg::load_sound` (a resource, then `streamwaves/`, then
`streamsounds/`; a missing file is silence and the flow treats the line as unvoiced). The line's `.lip`
(`res` kind `lip`, mounted with the module) plays on the speaker's **head** (a B body's second part;
else the body) from `mix::played` less the device's buffering (`voice_delay`):
`lipsync::apply` samples `talk` for the shapes around the time and blends them linearly, touching only
the face bones. Shape s is the pose at **(s + 1) / 16 of `talk`'s length** (the exe's rule, lip.md
"Playback (verified)"). Heads without a `talk` animation (45 of 90 whole-creature models; all 106
heads have one) stay still. `AmbientTrack` plays in the music group for the conversation and fades in
0.5 s at its end (*ours*: the area's music keeps playing beneath).

### Panels, tokens, fades, barks

`dlgpanel` (see its header): the cinematic panel is `dialog.gui` laid out as `CSWGuiDialogLetterbox`
does with bars that slide in over 0.5 s, the NPC line moving to the top bar while the replies are up
(numbered `1.` .. `9.`, wrapped, yellow when selected, dim when disabled; a click on a row or the digit
picks it, Enter takes the selected one, Space/Enter/click with only a line is a skip); the computer panel
is `computer.gui` over `WxHcomp0/1`. `<FullName>`, `<FirstName>`, `<LastName>` and `<CUSTOMn>` (from
`w.tokens`) are handed to the GUI before each line. Node fades (`FadeType` 3 in, 4 out, 1 and 2 at
once) and the outbox's global fades (SetGlobalFadeIn/Out) run on the panels' fade layer, drawn after
the 3D view and before the GUI. Barks (`Note::bark`: a one-liner, BarkString, SpeakString) show the
bubble (`len x 0.11 + 1` s) and play their sound 3D at the speaker with its mouth. The in-game UI
hides the HUD while `w.conversation.active` (the bars and fade are drawn under the GUI).

## Headless checks

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor.exe
kotor/out/kotor.exe --module end_m01aa --headless --frames 1400 --log dialog \
    --input kotor/tools/dlgcheck/scripts/trask.txt --screenshot-at 200:kotor/out/dlg/cutscene.png ...
kotor/out/kotor.exe --module end_m01aa --headless --frames 1130 --log dialog --input kotor/tools/dlgcheck/scripts/others.txt
kotor/tools/ctxc exe kotor/tools/enginetest -o kotor/out/enginetest.exe
kotor/out/enginetest.exe --module end_m01aa --frames 400 --log dialog --replies 1,0    # the flow alone
kotor/out/dlgcheck.exe                                                           # the corpus
```

Input script commands for conversations: `FRAME talk RESREF [TAG]` (start any conversation on the
creature TAG, default `end_trask`, cutting a running one short), `FRAME ui reply N` (pick reply N),
`FRAME ui key NAME` / `ui click X Y` / `ui move X Y` (through the panels while they are open).
On `end_m01aa` the opening cutscene `m01aa_c01` (frames 6 to 548) runs by itself and a script then
starts `end_trask01` (frame 551); with `ui key 2` at frame 830 the second reply is taken. Screenshots
of the run: the cutscene's close-up of the sleeping player (frame 200), Trask's close-up with the
subtitle and his mouth moving (700), the player's shot with the replies (830).

## Open

- Head look-at (the speaker's head following the listener within the head arc, `SetLockHeadFollowInDialog`
  only records the lists), equipment hiding, `bUseLeader`, the 6 m bark rule, hostiles frozen, journal
  and XP when those systems exist, the character-switch hand-off.
- The side-choice and obstruction tests use the area's walkmeshes only (not doors, placeables or the
  model geometry the original ray-tests).
- Camera and eye details the decompile left open: the ray end points of `SetShot`, the tie rule of
  `ChooseSide`, `OldHitCheck`.
- A one-shot dialogue animation could hand back to the talk/listen loop when it ends.
