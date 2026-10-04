# The action queue and the actions in swkotor.exe

What an object does over time is a queue of *actions*: the script `Action*` routines, the
player's clicks and the engine itself append nodes to a per-object list, and once per frame the
object's AI update runs the head of that list. This page covers the queue machinery (node layout,
groups, the per-frame runner, clearing, the commandable flag, how player commands replace the
queue, saving), the mapping between internal action ids and the script `ACTION_*` constants, every
script routine that queues an action, and what each action does frame by frame at the action
level. Addresses are for the Steam `swkotor.exe` after SteamStub removal (see
[README.md](README.md)); every claim carries a confidence: **high** (read in the code), **med**
(role clear, detail inferred), **low** (plausible). Names are ours, in the Aurora/NWN vocabulary;
proposals for every address below are in `kotor/re/proposals/actions.tsv` (git-ignored).

Related pages and the boundary with each:

- [objects.md](objects.md) section 5: the first survey of the queue (this page supersedes its
  action table) and the AI master that calls `AIUpdate`.
- [vm.md](vm.md), "Script situations": how `ActionDoCommand`/`AssignCommand`/`DelayCommand`
  capture the `action` argument; here only the queue side.
- [gameloop.md](gameloop.md): the frame, the world timer, events, `DelayCommand`, pause. Actions measure time
  with the world timer.
- [movement.md](movement.md): path planning, locomotion, walkmesh queries, party following, triggers. Here only
  what the move actions put in the queue, read back and decide.
- [combat.md](combat.md): combat rounds, attack resolution. Here only how ATTACKOBJECT approaches and when
  it starts and ends rounds.
- [rules.md](rules.md): effects, saves, Force powers, skills (Security, Demolitions checks). Here only where
  the checks are called.
- [dialogue.md](dialogue.md): conversation flow, cameras, barks. Here only DIALOGOBJECT's approach and hand-off.
- [party-items-saves.md](party-items-saves.md): inventory, equipping rules, containers, save games. Here only the item
  actions' timing and the `ActionList` GFF.
- [gui.md](gui.md): the HUD action-queue icons and the container panel.

**The exports used to cut these handlers short; they no longer do.** Ghidra had marked
`CSWSCreature::GetUseRange` (`0x004ee440`) as a function that does not return (and
`CExoString::~CExoString`, which cut the decompile of over a thousand more functions), so every
decompiled caller, about 20 action handlers among them (open/close door, lock, unlock, use,
dialog, the trap actions, heal, attack, move-to-object, the check actions), stopped right after
the call. The behaviour below was read from an objdump disassembly of the unpacked exe for those
parts. The exports were rebuilt without the bug on 2026-10-04 ([noreturn-fix.md](noreturn-fix.md));
the statements marked "damaged" or "lost to the noreturn bug" below can now be checked against the
full decompile. (high)

## 1. The queue

### 1.1 The action node (0x74 bytes)

`CSWSObject::AddAction` (`0x004cea20`) and `CSWSObject::AddActionToFront` (`0x004ccb00`) take the
same arguments: action id, group id, then up to 13 pairs (parameter type, pointer to the value).
Parameters stop at the first pair whose type is 0. `AddAction` appends at the tail,
`AddActionToFront` inserts at the head. (high)

| Offset | Size | Meaning | Conf. |
|---|---|---|---|
| `+0x00` | 4 | internal action id (section 1.9) | high |
| `+0x04` | 4 × 13 | parameter types: 1 int, 2 float, 3 object id, 4 string (`CExoString*`, heap copy), 5 script situation (`CVirtualMachineScript*`) | high |
| `+0x38` | 4 × 13 | parameter values: int, float bits, object id, or the pointer for 4/5 (`CSWSObjectActionNode::SetParameter` `0x004cac30`) | high |
| `+0x6c` | 2 | group id | high |
| `+0x6e` | 2 | number of parameters (index of the last one set + 1) | high |
| `+0x70` | 4 | may-be-cleared flag, 1 when created; 0 makes `CSWSCreature::ClearAction` refuse to remove the node | high |

The node destructor (`0x004cc4d0`) frees string parameters and deletes script situations
(`DeleteScriptSituation`); a handler that consumes a situation (DoCommand) zeroes the slot first.
Throughout this page "param *n*" means value slot *n* (`+0x38 + 4n`). (high)

### 1.2 Groups

Every node carries a 16-bit group id. Two values passed to `AddAction`/`AddActionToFront` are
special (high):

- `0xffff`: start a new group. The object's counter at `+0x14` is the next id; the node gets the
  counter's current value, the counter is incremented (skipping `0xffff`, wrapping to 0) and the
  id is also remembered at `+0x16` ("last group").
- `0xfffe`: join the last group created (`+0x16`), whatever was queued since.
- anything else: that exact group id (handlers pass their own node's group to keep sub-steps in
  the same group).

Both counters start at 0 in the `CSWSObject` constructor and are **not saved**; saved nodes keep
their group ids, so after a load new groups may reuse ids of loaded ones (harmless in practice).
(high)

A group is the unit the player sees and cancels: one click (say, "open that door") produces one
group even though the handlers later expand it into move + face + wait + open nodes. What uses
groups (high):

- `GetCurrentAction` (section 1.9) reports the head group, not the head node.
- the HUD action queue (`CSWSCreature::UpdateActionQueueDisplay` `0x004f6f30`): for party members
  shown on the HUD (`+0x9d4 == 1`), every 300 ms (`AIUpdate`) the first 10 groups are summarised
  into 10 entries of 0x1c bytes at creature `+0x3a8`: group id, the group's `ACTION_*` id, spell or
  feat id, a point and a target, taken from the group's "representative" node (the last node of the
  group's first run that has a script id, `0x004cc530`). The GUI draws these as the action icons and
  lets the player cancel one. (med)
- `CSWSObject::RemoveActionGroup` (`0x004cc6f0`) frees every node of a group **without** asking
  `ClearAction`; `RemoveCombatActionsOnTarget` (`0x004f61d0`) uses it to drop every attack, cast
  and item-cast group aimed at an object (or all of them) when the target surrenders or changes
  side, on `CancelCombat`, and for the attackers of a creature that disappears (3.13). (high)
- `CSWSObject::SetActionGroupClearable` (`0x004cc790`) sets the `+0x70` flag of a whole group.
  (high)

There is no generic "when one action of a group fails, drop the rest of the group" rule in
`RunActions`: a failed node (status 3) is freed alone and the next node runs. Handlers that expand
themselves push all their sub-steps in front of the queue, so a failure of an early sub-step (a
move that cannot path) just lets the later sub-steps run and fail their own range checks. (high
for RunActions; med for the consequence)

### 1.3 Running the queue: `CSWSObject::RunActions` (`0x0057f4a0`)

Called from `AIUpdate` of creatures (`0x004fe210`), placeables, doors, triggers, encounters and
areas of effect with the current world time (day, milliseconds) and the microsecond timer value
read when the AI update started. Stores, waypoints and sound objects never run actions. Order of
operations (high):

```
if the queue is not empty and this is the leader the player controls and the client camera
   option (+0x6d) is 5: reset that camera mode                       (low: purpose unknown)
loop:
    if the queue is empty:
        creature: reset attack target (+0x50c, +0x504), spell targets (+0x524, +0x528),
                  move target (+0x508) to OBJECT_INVALID; path state target (+0x254) INVALID,
                  path state +0x258..+0x260 = 0
        stop
    node = remove head; +0x1e4 = node; +0x80 = node id
    if both words of +0xbc/+0xc0 are 0: +0xbc/+0xc0 = now (day, ms)   -- the action's start time
    status = 3 (failed)
    switch node id: call the handler (creature-only handlers are skipped for other types,
                    leaving status 3; see the table in 1.9)
    ATTACKOBJECT: while it runs, +0x84 = the node's param 0, reset to INVALID afterwards
                  (param 0 is the cutscene flag in KOTOR's layout, the target is param 1: the
                  write looks like a leftover from a layout with the target first; med)
    CASTSPELL: on status 2 or 3 the combat round is told the cast ended (0x004d35c0)
    ITEMCASTSPELL: on any status but 1 the creature's +0x524/+0x528 are reset
    FOLLOWLEADER: status 1 when the client has no party leader yet
    +0x1e4 = 0; AI master +0x7c = id; +0x80 = 0xffff; +0xa8/+0xac = now
    status 4: append the node at the tail
    status 1: put the node back at the head
    else:     free it; +0xbc/+0xc0 = 0 (so the next action gets a fresh start time)
    stop if status == 1, or the id is 1, 5, 0x30 or 0x33 (moves and jumps),
         or more than 1000 us have passed since the AI update began
         (constant 1000 at 0x00745dcc)
after the loop:
    queue longer than 75: warning 0xa1; longer than 500: warning 0xa4, then free nodes from
    the head while ClearAction(node, TRUE) agrees; still longer than 1000: free everything
    effect list longer than 500: warning 0xa2; longer than 1000: warning 0xa5 and two purges
```

The status values are read from constants: 1 running (`0x00745dbc`), 2 done (`0x00745dc0`), 3
failed (`0x00745dc4`), 4 retry later (`0x00745dc8`). Note that status 2 and 3 are treated alike by
the runner; the difference only matters to the caller of a few handlers (CASTSPELL). (high)

Consequences an implementer must keep (high):

- Instant actions (speak, play sound, face, take item, set commandable, a finished wait) chain
  within one frame until something returns 1 or the 1 ms budget runs out. A move or jump always
  ends the frame's loop even when it finished.
- While a handler runs, its node is **not** in the list. A script run by DoCommand that calls
  `ClearAllActions` on its own object clears everything queued *after* it; the DoCommand node
  itself is freed normally when it returns.
- Handlers that need several steps do not loop internally. They push sub-actions and a fresh copy
  of themselves in front with `AddActionToFront` and return 2 (done), so the next frames run the
  sub-steps first and then the copy, which re-checks its conditions. Per-object flags in the
  creature (for example `+0x1f0` for doors, `+0x980` for unlocking) remember which phase the
  copy is in. This is the pattern behind every "walk there, then do it" action.

`+0xa8/+0xac` (last AI update time) and `+0xcc` (milliseconds since the previous AI update,
computed by `AIUpdate` before `RunActions`) give handlers frame deltas. `AIUpdate` order for a
creature: heartbeat → combat update → effects/perception step → `RunActions` → snap to walkmesh.
(high; the frame itself is [gameloop.md](gameloop.md)'s)

### 1.4 The common handler skeleton

Nearly every handler starts with the same three tests and fails (3) if any holds (high):

1. the object is dead (virtual slot 37 `GetDead`);
2. a folded always-false function (`0x0063e7f0`, "return 0");
3. for creatures: `GetIsIncapacitatedPartyMember` (`0x004ef890`), a party member whose current
   hit points are below 1 (KOTOR's knocked-out companions act on nothing until revived).

Interaction handlers then call `ClearActivities(2)` (`0x004f87d0`), which drops the creature's
combat/Force modes that are not locked (bits `0x100..0x2000` of `+0x9fc`) and **keeps stealth**:
opening doors and locks, using placeables, picking up, equipping, item abilities, traps and healing
all leave a creature hiding (the Stealth skill's own description says so, 248). Stealth (activity
bit 1, `SetActivity(1, FALSE)`) is dropped by `ClearActivities(1)` (a cast of the creature's own
power) and `ClearActivities(4)` (counter spell, `ResolveAttack`), by SPEAK / SPEAKSTRREF, by the
combat round's next scheduled action (AIActionCombat, below), by `Rest`, and by the party-wide
`SetPartyStealthMode(0)` (conversations, transitions, solo mode off). USEOBJECT and DIALOGOBJECT
call `SetActivity(4, FALSE)`, which leaves a conversation, not stealth. (high; corrected from an
earlier "talking, opening, using all break stealth", docs/mechanics/stealth.md)

**The approach pattern** (open/close door, lock, unlock, use, dialog, pick up, drop, traps, heal,
give item): if the actor is a creature and `GetIsInUseRange(target, extra)` (`0x004f6000`) is
false, compute the use point and range with `GetUseRange` (`0x004ee440`) and push, in front, in
this order of execution (high for UseObject, same shape elsewhere):

```
MoveToPoint(use point, target, range)   (AddMoveToPointActionToFront 0x004f8a50, the node's group)
CHECKINRANGEOFOBJECT 0x11 (target ...)   (UseObject; doors push FACE 0x13 + WAIT 0.5 only for
FACEOBJECT 0x13 (target)                  locked PreciseUse doors, see 3.6)
WAIT 0.5 s
<a fresh copy of the action>
```

and return 2. The copy runs once the move finished and, now in range, does the work.

`GetUseRange(target, &point, &range, bNoReachShortcut)` (`0x004ee440`, high):

| Target | Point | Range |
|---|---|---|
| creature | its position | own radius (path state `+8`, or `+0xc` when the target is the current path target) + target's radius (`+8`) + 0.3 |
| trigger | its position if `+0x2b4` is set, else the nearest point of its outline (`0x0058c8a0`) | own personal radius (path state `+4`) + 0.5 |
| placeable | nearest use node (`0x00584c20`) | 0.1 if `placeables.2da` PreciseUse (`+0x33c`) is set, the point is reachable (`0x004be5e0`) and the flag argument is 0; else radius + 0.75; then + 5.0 for corpses (`IsCorpse`, `+0x44c`) |
| door | nearest of its two sides (`0x00589240`), z snapped to the walkmesh | radius + path state `+0xc` when it is the current path target; 0.1 for a **locked** door (`+0x2c4`) whose `genericdoors.2da` PreciseUse (`+0x3c4`, med) is set, when the point is reachable; else radius + 0.75 |
| anything else | its position | own radius |

`GetIsInUseRange(target, extra)` (`0x004f6000`): different area → false; otherwise compares the
distance to the use point against range + 0.1 + extra (triggers flagged `+0x2b4`: point inside
the trigger instead). (high for the structure, med for the final comparison, which is in the part
Ghidra lost)

### 1.5 Clearing

`CSWSObject::ClearAllActions(bClearCombat)` (`0x004ccd80`, high):

1. Nothing happens unless the object is commandable (`+0xe8 == 1`).
2. For every node, ask virtual slot 29 `ClearAction(node, node == head)`; remove and free it if
   the answer is 1. "Head" is the action in progress between frames (a running action goes back
   to the head).
3. Creatures: stop the path (`0x005d0ec0` on the path state at `+0x340`), `+0xa8c = 1`, move
   target `+0x508` = INVALID, path state `+0x254` = INVALID and `+0x258..+0x260` = 0; if
   `bClearCombat`, clear the combat round's queued attacks (`0x004d37e0`, [combat.md](combat.md)); for a party
   member, reset the client party slot's follow state (`+0x28` of its 0x88-byte slot) to -1.

The script routine `ClearAllActions()` (9, `0x0052f4a0`) always passes `bClearCombat = TRUE`.

`CSWSObject::ClearAction` (base, `0x004cc390`): always agrees; DIALOGOBJECT also clears the GUI's
"conversation pending" flag (`0x0062ec60(gui, 0)`), RESUMECONVERSATION clears `+0x50` (paused).
(high)

`CSWSCreature::ClearAction` (`0x004fab00`) refuses (returns 0) when node `+0x70` is 0, otherwise
undoes the action's side effects and agrees (high):

| Action | Undone when cleared |
|---|---|
| 7, 8, 9, 0xb (pick up, equip, drop, unequip) | the client is told to remove the pending item icon (`0x0056fcb0`, `0x0056fbd0`, `0x0056fb70`, `0x0056fd80`) |
| 0x2a REST | `0x004f3690` |
| 0xc ATTACKOBJECT | attack targets `+0x504`, `+0x50c` = INVALID, animation 10000, `0x004f7530` |
| 1 MOVETOPOINT | path state `+0x30`, `+0x38` = INVALID, `+0xa8c = 1`; if it was the head and the creature has a client twin, animation 10000 |
| 0xf CASTSPELL | spell targets `+0x524/+0x528` INVALID, combat round `0x004d3ba0`, `+0x960 = 0`, animation 10000, `0x004f7530` |
| 0x2e ITEMCASTSPELL | the same with `+0x96c = 0` |
| 0x32 COUNTERSPELL | `0x0050ee80(0, 1)` |
| 9 / 7 | animation 10000, `+0x988` / `+0x98c` = 0 (phase flags) |
| 0x19–0x1d traps | animation 10000, action timer hidden, `+0x97c = 0` |
| 0x36, 0x38 | animation 10000, `+0x970/+0x974`, `+0x978` = 0 |
| 0x26 OPENLOCK, 0x27 LOCK | animation 10000, `+0x980` / `+0x984` = 0, action timer hidden |
| 0x14 OPENDOOR | animation 10000, `+0x1f0 = 0` |
| 0x3d FOLLOWLEADER | for party slots 0–2: reset the client slot (`0x004eae80`) |
| 0x18, 0x20 | as the base class |
| 0x28 USEOBJECT | if the placeable is mid-opening (`+0x450`): clear it, play its close animation (10075 → 10076) when it was showing 10075, speed 1.0 |
| all | if an interact target is set (`+0x944`), clear it (the creature turns to face it, `0x004f34a0`); if the node was the head, the start time `+0xbc/+0xc0` is reset |

Who makes nodes unclearable (`+0x70 = 0`): `SetActionGroupClearable` for APPEAR / DISAPPEAR
(0x34/0x35, queued by the appear/disappear effects through `0x004ecff0`/`0x004ed060`), CASTSPELL
once the conjure time has passed (unless its round is the master of a pair), and ITEMCASTSPELL from
its first frame (section 3.13). Note that `ClearAllActions` skips such nodes but keeps going, so
the queue after a clear can still hold an unclearable head. (high)

### 1.6 The commandable flag

`+0xe8`, 1 at construction, saved as the GFF byte `Commandable` (default 1 on load). (high)

- `SetCommandable(bCommandable, oTarget = OBJECT_SELF)` (162, `0x005426c0`) just stores
  `bCommandable != 0` on any object of type > 4. It neither clears nor freezes the queue: queued
  actions keep running. `GetCommandable` (163) reads it. (high)
- `ClearAllActions` does nothing on a non-commandable object (above).
- Most `Action*` routines refuse to queue when the target object is not commandable (the check is
  in each routine handler or in the `Add*Action` helper it calls; table in section 2).
  Exceptions that queue anyway: ActionMoveToLocation / ActionForceMoveToLocation,
  ActionForceFollowObject and ActionBarkString. (high)
- `ActionDoCommand` on a non-commandable object deletes the situation instead ([vm.md](vm.md)). (high)
- Action 0x2f (`0x0057c7b0`) would set the flag from a queued int, but nothing queues it. (high)

### 1.7 Player commands

The client sends the server a message for every player order (`CSWSMessage::
HandlePlayerToServerMessage` `0x00527b20`, major 6 "Input" → `0x005254c0`, major 0xc "Inventory"
→ `0x00523c20`). The input handler works on the creature the player controls (skipped while
`+0x9dc` is set) and, for most orders, first calls `PrepareForPlayerCommand(kind)` (`0x004f8770`),
which (only for creatures that have a client twin) runs `ClearAllActions(TRUE)` — always for kinds
4 and 8, for kinds 1 and 2 only when the creature's `+0x9f2` state is below 10. A player order
therefore **replaces** the queue: clear, then add. (high for the structure; med for the minor
names)

| Minor | Order | What it does |
|---|---|---|
| 1 | move (`0x005235b0`) | if the new destination equals the current one within 0.1 m only the path priority byte is updated; else (commandable only): the combat mode off (`SetCombatMode(0, 1)`; stealth stays), combat round notified, `PrepareForPlayerCommand(8)`, `AddMoveToPointAction(group 0xffff, or 0xfffe when +0x9f2 == 1, point, area, target, run flag, ...)` |
| 2 | attack | `AddAttackActions(target, ..., player = 1)` ([combat.md](combat.md)); remembers the target at `+0x510` |
| 3 | door | `PrepareForPlayerCommand(2)`, then `AddOpenDoorAction` when the message's word is 10021, else `AddCloseDoorAction` |
| 4 | emote | play an animation: on self → PLAYANIMATION in front; on another object → FACEOBJECT (0x13) or, with no object, FACEPOINT (0x31), then PLAYANIMATION (speed 1, duration 0) in the same group; clears the queue first when mode bit 8 is on |
| 5 | examine | per type (creature, item, trigger → a skill use 0x66, placeable, door) |
| 7 | use skill | `0x004fbe40` ([rules.md](rules.md), trap actions) |
| 8 | talk | `PrepareForPlayerCommand(8)`; queue DIALOGOBJECT (0x18) on the player with param 2 = 0, param 3 = 1, param 4 = 0 (walk up to the target) |
| 9 | use item / talent | `0x004fc210`; feedback 0x17 when it fails |
| 0xb | use object | `PrepareForPlayerCommand(2)`, `AddUseObjectAction` |
| 0xc / 0xe | unlock / lock | `PrepareForPlayerCommand(2)`, `AddUnlockObjectAction` / `AddLockObjectAction` when the door (`+0x2c4`) or placeable (`+0x260`) is locked / unlocked |
| 0xd | rest | REST action 0x2a (`0x004fd1e0`) unless the creature is in a state that forbids it; feedback 0xd5 when not commandable |
| 0x12 / 0x23 | cast a power / use a talent | `PrepareForPlayerCommand(1)` then `AddCastSpellActions` / talent helpers ([combat.md](combat.md), [rules.md](rules.md)) |
| 0x1c | turn | `SetOrientation` directly (no action) when commandable, alive and not down |
| 0x1d | drive (keyboard / stick) | `0x00523450`: the combat mode off (stealth stays), `ClearAllActions(TRUE)`, `PrepareForPlayerCommand(8)`, queue 0x33 |
| 0x24 | put an item into a container | `AddGiveItemAction` (0x22) with the placeable as recipient |

Inventory-panel orders (equip, unequip, drop, pick up) come through `0x00523c20` and the
`Add*ItemAction(s)` helpers of section 3.8. (med)

Party members get FOLLOWLEADER (0x3d) when the client adds them to the party (`0x006364c0`), which
also sets their perception ranges from `ranges.2da` (leader row 12 `PercepRngPlayer` 250/20,
followers row 11 `PercepRngDefault` 20/20, into creature `+0x914/+0x918`). (med)

### 1.8 Saving

`CSWSObject::SaveActionQueue` (`0x004cc7e0`, called by `SaveObjectState`) writes every queued node
— all action types — into the object's struct (high):

```
ActionList            list, one struct per node, in queue order
  ActionId            DWORD   internal id
  GroupActionId       WORD    group id
  NumParams           WORD
  Paramaters          list (sic), one struct per parameter (struct id 1)
    Type              DWORD   1..5
    Value             INT (1) | FLOAT (2) | DWORD object id (3) | CExoString (4) |
                      struct id 2 holding a saved script situation (5, [vm.md](vm.md))
```

`LoadActionQueue` (`0x004cecb0`) re-adds each node with `AddAction` and the saved group id, so the
order and groups survive; the clearable flag comes back as 1, the object's group counters and the
per-action phase flags in the creature (`+0x1f0`, `+0x980` ...) are not saved, so an action saved
mid-way restarts from its first phase. `Commandable` is a BYTE next to the list. (high)

### 1.9 Internal ids, handlers and `ACTION_*`

`GetScriptActionId` (`0x0057a2b0`) maps internal ids to the script constants; `HasScriptActionId`
(`0x0057a240`) says which have one. `GetCurrentAction(oObject)` (522, `0x00549040`) returns
`ACTION_QUEUEEMPTY` (65534) for an empty queue, else walks the run of nodes sharing the head's
group and returns the script id of the **last** node in that run that has one, `ACTION_INVALID`
(65535) if none does. (high)

The full table. "C" = creature-only handler (for other object types the node fails at once). "—"
= no script constant.

| Id | Script id | Name (ours) | Handler | Queued by | Conf. |
|---|---|---|---|---|---|
| 1 | 0 MOVETOPOINT | MoveToPoint | C `0x0051f4f0` | move routines, player move, every approach | high |
| 2 | — | CheckMoveToObject | C `0x005101a0` | no constant-id call site found | low |
| 3 | — | MoveAwayFromObject | C `0x005155b0` | ActionMoveAwayFromObject | high |
| 4 | — | ContinuePath (after a jump) | C `0x0050ff20` | JumpToPoint | low |
| 5 | — | JumpToPoint | C `0x0051d600` | (Action)JumpToLocation, cheat handler | high |
| 6 | — | PlayAnimation | `0x0057d080` | (Action)PlayAnimation, player emote, many handlers | high |
| 7 | 1 PICKUPITEM | PickUpItem | C `0x00517410` | ActionPickUpItem, inventory orders | high |
| 8 | — | EquipItem | C `0x00510fd0` | ActionEquipItem, ActionEquipMost*, inventory orders | high |
| 9 | 2 DROPITEM | DropItem | C `0x00513830` | ActionPutDownItem, inventory orders | high |
| 0xa | — | CheckMoveToPoint | C `0x00510670` | only itself (re-queue); no first queuer found | med |
| 0xb | — | UnequipItem | C `0x00513ec0` | ActionUnequipItem, inventory orders | high |
| 0xc | 3 ATTACKOBJECT | AttackObject | C `0x005bbbf0` | ActionAttack, player attack, AI | high |
| 0xe | — | Speak | `0x0057b430` | ActionSpeakString | high |
| 0xf | 4 CASTSPELL | CastSpell | C `0x00514af0`, placeable `0x00584ec0` | ActionCastSpellAt*, talents | high |
| 0x10 | — | WaitForCombatRound | C `0x00513f60` | nothing | med |
| 0x11 | — | CheckInRangeOfObject | C `0x005103b0` | approaches (move to object, use, attack, cast) | high |
| 0x12 | — | CheckInRangeOfPoint | C `0x005108a0` | approaches to a point (casts at a location, cutscene move) | high |
| 0x13 | — | FaceObject | C `0x0050fb60` | approaches, emote | high |
| 0x14 | 5 OPENDOOR | OpenDoor | `0x0057d490` | ActionOpenDoor, player | high |
| 0x15 | 6 CLOSEDOOR | CloseDoor | `0x0057bbf0` | ActionCloseDoor, player | high |
| 0x16 | — | SetCameraFacing | C `0x005137c0` | SetCameraFacing | high |
| 0x17 | — | PlaySound | `0x0057cf00` | PlaySound | high |
| 0x18 | 7 DIALOGOBJECT | DialogObject | `0x0057a470` | ActionStartConversation, player talk | high |
| 0x19 | 8 DISABLETRAP | DisableTrap | C `0x00519570` | skill use | high |
| 0x1a | 9 RECOVERTRAP | RecoverTrap | C `0x00518c40` | skill use | high |
| 0x1b | 10 FLAGTRAP | FlagTrap | C `0x0050e400` | skill use | high |
| 0x1c | 11 EXAMINETRAP | ExamineTrap | C `0x0050e900` | skill use / examine | high |
| 0x1d | 12 SETTRAP | SetTrap (mines) | C `0x00519e30` | item use (`0x004fc210`) | high |
| 0x1e | 36 WAIT | Wait | `0x0057b5b0` | ActionWait, handlers | high |
| 0x1f | — | PauseConversation | `0x0057b290` | nothing (the routine acts at once) | high |
| 0x20 | — | ResumeConversation | `0x0057b320` | ActionResumeConversation | high |
| 0x21 | — | SpeakStrRef | `0x0057b3d0` | ActionSpeakStringByStrRef | high |
| 0x22 | — | GiveItem | `0x0057b6a0` | ActionGiveItem, put-in-container order | med |
| 0x23 | — | TakeItem | creature/placeable `0x0057bae0` | ActionTakeItem | med |
| 0x24 | — | EncounterDespawn | C `0x00510c20` | nothing | med |
| 0x25 | — | DoCommand | `0x0057b530` | ActionDoCommand | high |
| 0x26 | 13 OPENLOCK | OpenLock | `0x0057d9d0` | ActionUnlockObject, player, skill | high |
| 0x27 | 14 LOCK | Lock | `0x0057bec0` | ActionLockObject, player | high |
| 0x28 | 15 USEOBJECT | UseObject | `0x0057e8c0` | ActionInteractObject, player | high |
| 0x29 | 16 ANIMALEMPATHY | (stub, fails) | C `0x005140d0` | — | high |
| 0x2a | 17 REST | Rest | C `0x005140e0` | player rest (`0x004fd1e0`) | high |
| 0x2b | 18 TAUNT | (stub, fails) | C `0x005140d0` | — | high |
| 0x2c | — | MoveAwayFromLocation | C `0x0050fd50` | ActionMoveAwayFromLocation | high |
| 0x2d | — | RandomWalk | C `0x00515ac0` | ActionRandomWalk | high |
| 0x2e | 19 ITEMCASTSPELL | ItemCastSpell | C `0x0050f170` | item use | high |
| 0x2f | — | SetCommandable | `0x0057c7b0` | nothing | high |
| 0x30 | — | JumpToObject | C `0x0051d110` | (Action)JumpToObject | high |
| 0x31 | — | FacePoint | C `0x0050fc90` | player emote, drop | high |
| 0x32 | 31 COUNTERSPELL | CounterSpell | C `0x00514270` | | med |
| 0x33 | — | DriveDirect (keyboard/stick move) | C `0x0051e6a0` | player input 0x1d | med |
| 0x34 / 0x35 | — | Appear / Disappear | C `0x005140f0` / `0x005141b0` | appear/disappear effects (`0x004ecff0`, `0x004ed060`) | high |
| 0x36 | 34 PICKPOCKET | (stub, fails) | C `0x005140d0` | — | high |
| 0x37 | 35 FOLLOW | Follow | C `0x005132e0` | ActionForceFollowObject | high |
| 0x38 | 33 HEAL | Heal | C `0x00517a60` | skill use (`0x004f0900`) | high |
| 0x3a | — | FollowRepeat | C `0x005136b0` | ActionForceFollowObject | med |
| 0x3c | — | WaitForArea | C `0x00511080` | JumpToPoint into another area | high |
| 0x3d | 38 FOLLOWLEADER | FollowLeader | C `0x00511130` (party members only) | ActionFollowLeader, party join | high |
| 0x3e | — | BarkString | `0x0057ce00` | ActionBarkString | high |
| 0x3f | 39 (no constant) | Combat (dispatcher of scheduled combat orders) | C `0x005b6210` | every scheduled attack, cast, item use, cutscene attack/move | high |
| 0x40 | — | CheckFormationPoint | C `0x00510ab0` (party members only) | `0x0051ac10` (party formation moves, [movement.md](movement.md)) | low |
| 0x41 | — | SurrenderToEnemies | C `0x0051b420` | ActionSurrenderToEnemies | high |

Ids 0, 0xd, 0x39 and 0x3b have no case in `RunActions` and fail at once. `ACTION_SIT` (37) is
never produced. With its unused second argument non-zero, `GetScriptActionId` maps only 0xb → 27
and 0x1e → 24 (dead code). (high)

## 2. Script routines that queue actions

"Cmd" = the routine refuses unless the target is commandable. Group is 0xffff unless noted.
Param lists give value slots in order. (high unless marked)

| Routine | Handler | Queues | Params, notes |
|---|---|---|---|
| 9 ClearAllActions() | `0x0052f4a0` | — | `ClearAllActions(TRUE)` on OBJECT_SELF |
| 20 ActionRandomWalk() | `0x0052d440` | 0x2d, Cmd | home point (self's position now) x,y,z; area id |
| 21 ActionMoveToLocation(l, bRun) | `0x0053fe00` | 1 (not Cmd) | point of `l`; **the creature's own area**, not `l`'s; no target; run; range 0; no timeout |
| 382 ActionForceMoveToLocation(l, bRun, fTimeout = 30) | same | 1 (not Cmd) | as 21 with the timeout |
| 22 ActionMoveToObject(o, bRun, fRange = 1.0) | `0x0053fb00` | 1 + 0x11 (group 0xfffe) (+ 0x13 for PreciseUse placeables), Cmd | point = o's position; range = max(fRange, GetUseRange); target o; no timeout |
| 383 ActionForceMoveToObject(o, bRun, fRange, fTimeout = 30) | same | same | with the timeout |
| 23 ActionMoveAwayFromObject(o, bRun, fRange = 40) | `0x0053f990` | 3, **group 0xfffe**, Cmd | o, run, range, retries = 10 |
| 360 ActionMoveAwayFromLocation(l, bRun, fRange = 40) | `0x0052d090` | 1 then 0x2c (0xfffe), Cmd = 1 | flee point at `fRange` from `l`; 0x2c gets point, run, range, retries 10 |
| 32 ActionEquipItem(o, nSlot, bInstant) | `0x005355f0` | 8 via `AddEquipItemActions` | slot 0..17 turned into the bit mask `1 << nSlot` |
| 33 ActionUnequipItem(o, bInstant) | `0x00545050` | 0xb via `AddUnequipActions` | |
| 34 ActionPickUpItem(o) | `0x005404f0` | 7 via `AddPickUpItemAction`, Cmd | item, container (INVALID), quiet byte |
| 35 ActionPutDownItem(o) | `0x00541970` | 9 via `AddDropItemActions`, Cmd | item, drop point x,y,z, int |
| 37 ActionAttack(o, bPassive) | `0x0052e7f0` | a scheduled attack + 0x3f via `AddAttackActions` | 3.13 |
| 39 ActionSpeakString(s, nVolume) | `0x00544090` | 0xe, Cmd | string; volume mapped 0→1, 1 (whisper)→3, 2 (shout)→2, 3→0xd, 4→0xe |
| 221 SpeakString(s, nVolume) | same | — | sends the line at once |
| 240 ActionSpeakStringByStrRef(n, nVolume) | `0x00544270` | 0x21, Cmd | strref; volume 0→8, 1→10, 2→9 |
| 40 ActionPlayAnimation(n, fSpeed = 1, fDuration = 0) | `0x00540550` | 6, Cmd | internal animation, speed, duration, 1 (first-run flag); negative duration: see 3.9 |
| 300 PlayAnimation(n, fSpeed, fDuration) | same | 6 in front, after `ClearAllActions(TRUE)`, Cmd | |
| 43 ActionOpenDoor(o) | `0x00540260` | 0x14 via `AddOpenDoorAction` (`0x004cfac0`), Cmd | door, int |
| 44 ActionCloseDoor(o) | `0x0052f4f0` | 0x15 via `0x004cfb20`, Cmd | |
| 483 / 484 ActionUnlockObject / ActionLockObject(o) | `0x0052cff0` | 0x26 / 0x27 via `0x004cfb80` / `0x004cfc20`, Cmd | target, item (INVALID), int; a creature must be able to use skill 6 (Security, `0x005af880`), else feedback and nothing queued |
| 338 / 547 DoDoorAction / DoPlaceableObjectAction(o, n) | `0x00530360` | open, unlock, bash (attack), knock (cast) per `DOOR_ACTION_*` | |
| 329 ActionInteractObject(o) | `0x0052cc70` | 0x28 via `AddUseObjectAction` (`0x0057c810`), Cmd | |
| 46 PlaySound(s) | `0x00541170` | 0x17, Cmd | sound resref |
| 48/234/501/502 ActionCastSpellAt*, ActionCastFakeSpellAt* | `0x0052ee50` | a scheduled cast + 0x3f via `AddCastSpellActions` (placeables: 0xf directly) | 3.13 |
| 135 ActionGiveItem(oItem, oGiveTo) | `0x0052c8b0` | 0x22, **group 0xfffe**, Cmd | item, recipient, count (stack), int |
| 136 ActionTakeItem(oItem, oTakeFrom) | same | 1 (range 1.0, run beyond 5 m) then 0x23, Cmd | item, source, int |
| 167 ActionForceFollowObject(o, fDist = 0) | `0x0052c960` | 0x37 then 0x3a | target, run 1, follow point x,y, int 0, own x,y |
| 196 ActionJumpToObject(o, bStraight = TRUE) | `0x0052cce0` | 0x30, Cmd, creature | target, flag |
| 385 JumpToObject(o, bStraight) | same | 0x30 **in front** | |
| 214 ActionJumpToLocation(l) | `0x0052cdc0` | 5, Cmd, creature | point x,y,z; the creature's area; 1; search radius 20.0; facing x,y of `l` |
| 313 JumpToLocation(l) | same | 5 **in front** | |
| 202 ActionWait(f) | `0x00545800` | 0x1e, Cmd | seconds |
| 204 ActionStartConversation(...) | `0x0052d5b0` | 0x18 on OBJECT_SELF, Cmd | see 3.12 |
| 205 ActionPauseConversation() | `0x0052d330` | — | pauses at once (sets `+0x50`), Cmd |
| 206 ActionResumeConversation() | `0x0052d520` | 0x20, Cmd | |
| 294 ActionDoCommand(a) | `0x0052c740` | 0x25 via `0x0057cb10`, Cmd | the situation |
| 360 ActionMoveAwayFromLocation | above | | |
| 379 / 476 / 762 (Action)SurrenderToEnemies, SurrenderRetainBuffs | `0x00544830` | 0x41 for 379 (non-PCs only); 476/762 act at once | 3.13 |
| 54 CancelCombat(o) | `0x00546510` | — | `CancelCombat` `0x004fdaa0`: clears the queue and the attack/cast groups, ends the round |
| 399 / 400 / 404 ActionEquipMost* | `0x0052c7b0` ... | 8 | 404 via `0x004f3a60` |
| 287 / 288 / 309 / 310 ActionUseFeat/Skill/Talent* | `0x0052d8f0`, `0x0052d9b0`, `0x0052daf0` | feat attacks scheduled; skills: traps 0x19–0x1c, OPENLOCK, HEAL; talents dispatch | 3.13 |
| 503 CutsceneAttack, 507 CutsceneMove | `0x0052e890`, `0x0052e950` | scheduled entries + 0x3f | 3.13 |
| 700 ActionBarkString(nStrRef) | `0x0052c6a0` | 0x3e (creature, not Cmd) | only when no conversation is running (GUI `+0xb4 == 0`) |
| 671 BarkString(o, nStrRef) | `0x00548900` | — | shows the bark at once (OBJECT_INVALID: speaker-less) |
| 730 ActionFollowLeader() | `0x0052cbe0` | 0x3d | party members (`+0xa88`), Cmd = 1 |
| 45 SetCameraFacing(f) | `0x00542530` | 0x16, Cmd | int 1, degrees, 0, 0, int 0 |
| 10 / 143 SetFacing, SetFacingPoint | `0x00542830` | — | turns at once |
| 255 BeginConversation, 417 SpeakOneLinerConversation | `0x0052e9f0`, `0x00543f70` | — | act at once ([dialogue.md](dialogue.md)) |
| 514 GetUserActionsPending() | `0x0053e1b0` | — | true if the combat round's scheduled list (`+0x9b0`, 3.13) holds an entry whose `+0x84` field is set and whose two objects (`+0x14`, `+0x44`) are alive |
| 6 AssignCommand / 7 DelayCommand | [vm.md](vm.md) | — | event 1 to the target; the closure then usually calls `Action*` on that object |

## 3. The actions

### 3.1 Moving (ids 1, 2, 0xa, 3, 0x2c, 0x2d, 0x33)

The planner and the walking itself are [movement.md](movement.md)'s; this is what the actions store and decide.

**MOVETOPOINT (1), `CSWSCreature::AIActionMoveToPoint` `0x0051f4f0`.** Parameters, as
`AddMoveToPointAction` (`0x004f8b60`) and its in-front twin `0x004f8a50` pack them (high for the
layout, med where marked):

| Param | Type | Meaning |
|---|---|---|
| 0–2 | float | destination |
| 3 | object | area id |
| 4 | object | target object (INVALID for a point); missing ⇒ INVALID |
| 5 | int | flags: bit 0 run; bit 1 (med: "keep formation"/leader-relative); bit 2 a timeout was given; bit 3 (set by random walk and flee; passed to the planner); bits 4–6, 7–8 (unknown); bit 9; bit 10 (stored in path state `+0x240`) |
| 6 | float | arrival range |
| 7 | int | a byte stored in path state `+0x28` (the player move passes one from the client) |
| 8 | float | timeout in seconds (Force moves) |
| 9–10 | float | an offset rotated by the party leader's facing and added to the leader's position (party formations) |
| 11–12 | int | absolute deadline (world day, ms) once a timeout started |

Queuing sets creature `+0xa8c = 2` and clears path state `+0x26c..+0x274`. Per frame (med; the
decompilation is damaged by the noreturn bug):

1. Common preconditions; no path state → fail; a creature whose can-move bit (`+0x9f0 & 2`) is
   clear (rooted / paralysed by effects, [rules.md](rules.md)) fails. Run is forced off when `+0x8e8 == 1`.
2. With a range > 0 and the creature already within it of the destination (and a straight walk
   available, `0x0050c330`): treated as arrived.
3. Deadline set and reached ⇒ the creature is placed at the destination ("Force Timeout,
   executing a force move" in the log), `+0xa8c = 1`, done. A timeout given but no deadline yet
   ⇒ deadline = now + timeout, re-queue itself in front with it, done.
4. Target is a creature ⇒ chase: re-plan when the target has moved more than max(2.0, 0.4 ×
   distance) from the stored point, or its own move destination differs by more than 2 m.
   Target is a trigger ⇒ on arrival its OnClick fires (script event 30 CLICKED sent to it),
   animation 10000, path stopped, done. Path blocked ⇒ script event 31 PATH_BLOCKED to the
   creature, caller = the blocker (OnBlocked).
5. A new destination is handed to the planner (`0x004c6f70`). Planned (2): move target `+0x508`
   = target, animation 10002 walk or 10004 run, `+0xa98` = run flag, modes off, then the
   per-frame locomotion step (`0x0051bb10`, or `0x0051d9c0` for client-driven creatures) — status
   1 while walking. Failed (3): animation 10000; a forced move teleports to the destination and
   succeeds; otherwise the action fails ("The Path find has Failed... Why?").
6. Already within 0.1 m of the destination in the same area: placed exactly on it when that spot
   is walkable, animation 10001, done.

**CHECKMOVETOPOINT (0xa, `0x00510670`)**: point, area, target, run. If the creature is in another
area or farther than twice its personal radius from the point, it re-queues itself, a move and a
short wait in front; else done. (med) **CHECKMOVETOOBJECT (2, `0x005101a0`)** is the object
version (its tail is lost to the noreturn bug); no call site pushing id 2 as a constant was found
(low).

**AddShortWaitToFront** (`0x004eb5a0`): the movement retries are separated by a WAIT of 0.3 s
(0.1 s for creatures with a client twin). (high)

**MOVEAWAYFROMOBJECT (3, `0x005155b0`)** and **MOVEAWAYFROMLOCATION (0x2c, `0x0050fd50`)**:
params threat (object or point), run, range, retries (10). If still within `range` of the threat
(same area) and retries remain: pick a point `range` away from the threat (`0x004bdf80`),
re-queue itself with one retry less, push a move there (flag bit 3 set) and a short wait; else
done. Before that, 3 removes other queued flee groups from the same object (`0x004f1ef0`). (high)

**RANDOMWALK (0x2d, `0x00515ac0`)**: params home point, area. Each run **deletes everything else
in the queue**, then pushes (in execution order) a move, a WAIT and a fresh RANDOMWALK. The wait is
3.0 s; when the creature's AI level is below 1 (far from the player) it is 15.0 s and no move is
made. The move target is home ± (rand() % 15 − 7) m in x and y, z snapped to the walkmesh; if the
straight walk there is blocked the distance is shrunk by 0.75 up to 20 times, turning the
direction when below 30 % of the original, giving up under 1 m. The walk is never run. So a random
walker stays near where it was when the action was queued, until cleared. (high)

**DRIVEDIRECT (0x33, `0x0051e6a0`)**: keyboard/stick movement of the controlled character,
queued by input minor 0x1d after clearing the queue: direction x,y, a heading word, two bytes,
flags (bit 1 run, cleared when `+0x8e8` forces walking). [movement.md](movement.md). (med)

**CONTINUEPATH (4, `0x0050ff20`)**: pushed by JumpToPoint; if the path state holds a multi-point
path, drops its first point, queues a move along the rest and a short wait; then waits 0.75 s.
(low)

### 3.2 Jumping (5, 0x30, 0x3c)

**JUMPTOPOINT (5, `0x0051d600`)**: params point, area, bWalkable-search flag (default 1), search
radius (default 20.0), facing. Stops the path, finds a free walkable spot near the point within
the radius (`0x004be860`, else uses the point), snaps the camera if it is the controlled
character, then: same area ⇒ `SetPosition`; other area ⇒ moves the creature to that area
(`0x004fa100`) and, for client-driven creatures, pushes WAITFORAREA (0x3c). Sets the facing,
pushes CONTINUEPATH (4), sets `+0xa18 = 1`. Ends the frame's loop. (high for the steps, med for
the status)

**JUMPTOOBJECT (0x30, `0x0051d110`)**: the same towards an object's position (params object,
bWalkStraightLineToPoint). (med)

**WAITFORAREA (0x3c, `0x00511080`)**: fails for creatures not on the HUD, runs (1) until the
creature is in an area, then done. (high)

### 3.3 Following (0x37, 0x3a, 0x3d, 0x40)

**FOLLOW (0x37, `0x005132e0`)** and **FOLLOWREPEAT (0x3a, `0x005136b0`)**:
`ActionForceFollowObject(o, fDist)` queues FOLLOW (target, run 1, a follow point = o's position +
fDist × o's facing — replaced by the party formation slot when the actor is a party member —, a
"there" flag, own position) and FOLLOWREPEAT with the same first four params. FOLLOW computes the
point relative to the party leader's position and facing; when not there, it pushes a fresh FOLLOW,
a WAIT (0.25 s; 0.1 s for party members) and a move to the point, and returns done; when farther
than the client's follow distance (`0x00634a70`) it does the same. FOLLOWREPEAT pushes itself and a
FOLLOW again, so the pair never ends by itself: following lasts until the queue is cleared. (med:
the point arithmetic is [movement.md](movement.md)'s)

**FOLLOWLEADER (0x3d, `0x00511130`)**: party members only (`+0xa88`), with `+0x4c0` set, able to
move (`+0x9f0 & 2`), in an area: sets `+0xa8c = 3` (the locomotion code then follows the leader,
[movement.md](movement.md)) and returns 1 — it runs for ever. `RunActions` also keeps it (status 1) while the
client has no leader. (high)

**CHECKFORMATIONPOINT (0x40, `0x00510ab0`)**, pushed with a move by `0x0051ac10` (party
formation movement): party members: if not within range + 0.01 of a point or in another area, sets
the client party slot state to 5. (low)

### 3.4 Facing and camera (0x13, 0x31, 0x16)

FACEOBJECT (0x13, `0x0050fb60`) turns to face an object in the same area (no turn when closer than
~0.003 m) and is done; another area fails. FACEPOINT (0x31, `0x0050fc90`) faces a point.
SETCAMERAFACING (0x16, `0x005137c0`) sends the facing to the client twin (camera, [movement.md](movement.md)).
All instant. (high)

### 3.5 USEOBJECT (0x28, `CSWSObject::AIActionUseObject` `0x0057e8c0`)

Param 0 = the object. In order (high unless marked):

1. Preconditions; a party member may not use anything while a conversation is running (GUI
   `+0xb4`). The target must exist, be alive and (if a creature) not knocked out.
2. Creature actor: modes off and out of any conversation (`ClearActivities(2)`, `SetActivity(4, FALSE)`; stealth stays); if not `GetIsInUseRange(target, 0)` ⇒ the approach
   pattern of 1.4 (move, 0x11, face, wait 0.5 s, use), done.
3. In range, placeable target:
   - not `Useable` (`+0x328`) ⇒ fail;
   - trapped (`+0x278`), actor a creature, actor's reputation with it < 90 and a different faction
     (`+0x23c` vs stats `+0x78`) ⇒ script event 26 (trap triggered) to the placeable, fail;
   - no inventory (`+0x324` = 0) ⇒ go to step 5;
   - locked (`+0x260`) and `UseKeyOnObject(placeable, 0)` fails ⇒ feedback message 13 ("locked")
     to the actor, go to step 5 (OnUsed still fires);
   - otherwise open it. The sound is `placeableobjsnds.2da` column `Opened` of the row given by
     `placeables.2da` `SoundAppType` for the appearance (`+0x230`). Actor without a client twin
     (NPC): play animation 10075 ("open") and the sound, no GUI. Actor with a client twin (the
     player), placeable not busy (`+0x338` = 0): first pass ⇒ push a fresh USEOBJECT and, in front
     of it, a WAIT of max(open animation length, sound length) — 0.5 s when the placeable has no
     client twin —, play 10075, mark `+0x450` = opening, done; second pass (`+0x450` set) ⇒ open
     the container panel (`CSWSPlaceable::OpenInventory` `0x00587420`), clear `+0x450`, speed 1.0.
4. In range, item target: when the base item's flag at row `+0x70` is set and the actor has a
   client twin, opens or closes that item's container (`0x0055d800`/`0x005561a0`), done. (low)
5. Send script event 25 USED to the placeable (OnUsed, caller = actor), done.

### 3.6 Doors (0x14, 0x15)

**OPENDOOR (0x14, `0x0057d490`)**: params door, int (default 1). Not a creature (a placeable or
door opening something): send event 7 OPEN_OBJECT to the target and push WAIT 0.5 s; done.
Creature (high, from the disassembly):

1. Modes off. Door not closed ⇒ done at once. A door's open state (`+0x2cc`, GFF `OpenState`,
   set by `CSWSDoor::SetOpenState` `0x00589600`) shows as its animation: 0 closed = 10022,
   1 open one way = 10050, 2 open the other way = 10051, 3 (forced when `+0x308` is 0, likely
   destroyed) = 10072; the action tests the animation for 10022. (high)
2. Not in the same area or not in use range ⇒ push a fresh OPENDOOR (new group); for a locked
   PreciseUse door (`+0x2c4` and `+0x3c4`) also a WAIT 0.5 s and a FACEOBJECT; then a
   move to the door's use point (`AddMoveToPointActionToFront`, target INVALID); `+0x1f0 = 1`;
   done.
3. In range: trapped (`+0x2e8`), reputation < 90 and a different faction (`+0x2b8`) ⇒ script
   event 26 to the door, fail. `UseKeyOnObject(door, 0)` fails (locked, no key) ⇒ script event 34
   FAIL_TO_OPEN to the door (OnFailToOpen), `+0x1f0 = 0`, fail.
4. First arrival (`+0x1f0` = 0): push a fresh OPENDOOR, `+0x1f0 = 1`, done (the copy runs at
   once). Second pass (`+0x1f0` = 1): `+0x1f0 = 0`, send event 7 OPEN_OBJECT to the door (caller
   = actor), push WAIT 0.5 s in the same group, done.

The door's side (`CSWSDoor::EventHandler` `0x0058b850`, high):

- event 7 OPEN_OBJECT ⇒ `CSWSDoor::Open(opener)` (`0x00589c70`): open state 1 when the opener
  stands in front of the door (positive dot product of opener − door with the door's facing),
  else 2, so the door swings away from the opener; the opener is remembered at `+0x31c`
  (`GetLastOpenedBy`); `SetOpenState(state, 1)` on the door and on its linked door
  (`0x00589580`); then the OnOpen script (`+0x228`) runs at once.
- event 6 CLOSE_OBJECT ⇒ closer at `+0x320`, state 0 on the door and its linked door, OnClosed
  (`+0x230`).
- script event 34 FAIL_TO_OPEN ⇒ `+0x324` = the actor, OnFailToOpen (`+0x298`); when the door is
  locked, feedback 13 ("locked") to the actor.
- script event 26 (trap triggered) ⇒ when trapped (`+0x2e8`) and the actor is not immune, feedback
  0x52, OnTrapTriggered (`+0x270`), one-shot traps (`+0x304`) are removed. Event 15 ON_MELEE_ATTACKED
  runs OnMeleeAttacked and also springs the trap when the attacker is within 4 m.
- script event 30 CLICKED (a transition door reached by MOVETOPOINT) runs OnClick (default
  `NW_G0_Transition` for transition doors) and starts the area transition ([movement.md](movement.md) /
  [gameloop.md](gameloop.md)).

**CLOSEDOOR (0x15, `0x0057bbf0`)**: target door or placeable (anything else fails). Creature not
in range ⇒ push a fresh CLOSEDOOR (new group, int 1) and a move (node's group), done. In range (or
not a creature) ⇒ event 6 CLOSE_OBJECT to the target, WAIT 0.5 s in front, done. No state check
in the action. (high)

### 3.7 Locks (0x26, 0x27)

**OPENLOCK (0x26, `0x0057d9d0`)**: params target, item used (INVALID or a security tunnel), int.
(high for structure, med for the check details, which are [rules.md](rules.md)'s)

1. Approach (use range + 0); flag `+0x9a4` marks the approach issued.
2. First arrival (`+0x980` = 0): `+0x980 = 1`; push a fresh OPENLOCK and, before it, PLAYANIMATION
   (10128 `0x2790` or 10131 `0x2793`, speed 1.0, 1.5 s); show a 1500 ms action timer
   (`StartActionProgress` `0x004ef480`, type 7); done. For the player the animation action plays
   `gui_lockpick` 250 ms in (3.9).
3. Second pass: trap check as for doors (event 26). `UseKeyOnObject(target, 0)` succeeds ⇒ door:
   `CSWSDoor::Open` (`0x00589c70`, the door opens away from the user); placeable: push USEOBJECT; done.
   (`UseKeyOnObject` is true at once for a lock that is not locked, false without a KeyName, else true
   when an item tagged KeyName is in the creature's inventory or a slot; it unlocks, removes the key when
   AutoRemoveKey, and sends feedback 16 "You used a key.")
4. Not locked ⇒ feedback 14 "That object is not locked.". KeyRequired (door `+0x2d8`, placeable `+0x26c`)
   ⇒ event 34 FAIL_TO_OPEN, feedback 15 "This object cannot be opened through conventional means.", a
   combat log entry with result 5, sound-set entry 0x18, done.
5. Security check ([rules.md](rules.md)): skill roll + item bonus against the OpenLockDC (placeable `+0x274`,
   door `+0x2bf`; 0 counts as 1). Success: Locked = 0, door opened by the user and event 12 UNLOCK_OBJECT; a
   placeable then gets USEOBJECT pushed; the item's charges (`+0x28c`) drop by one, the item is
   destroyed (event 11) at the last charge; sound-set entry 0x19 is played (0x18 on failure). A combat
   log entry (id 0x149, dialog.tlk 1405 "<CUSTOM0> attempts <CUSTOM1> on <CUSTOM2> : *<CUSTOM3>* :
   (<CUSTOM4> <CUSTOM5> <CUSTOM6> = <CUSTOM7><CUSTOM8>)") shows the roll, with result code 1 success, 0
   failure in combat, 3 failure taking 20 below DC 60, 5 taking 20 at DC 60 or more ("success not
   possible", 1397). A failed roll gives no feedback message and the action is done, not failed.
   The feedback messages (`FormatFeedbackMessage` `0x005fcd10`): 13 "Locked" (1439, with the actor's
   sound-set bark), 14 1430, 15 1431, 16 1432.
6. Timer hidden, flags `+0x980/+0x9a4` cleared.

**LOCK (0x27, `0x0057bec0`)**: the mirror: approach, first arrival plays 10128 or 10131 for 1.5 s
with a 1500 ms timer (`+0x984`), then a key (`UseKeyOnObject(target, 1)`) or a Security check
against CloseLockDC (placeable `+0x275`, door `+0x2c0`) sets Locked = 1 and sends event 13
LOCK_OBJECT; KeyRequired ⇒ event 34 and feedback 15. (med)

### 3.8 Items (7, 9, 8, 0xb, 0x22, 0x23)

**PICKUPITEM (7, `0x00517410`)**: params item, container (INVALID for the ground), quiet byte.
Fails if the item already has an owner (`+0x268`). Within 1.1 m (squared distance 1.21) of the
item: first time (`+0x98c` = 0) ⇒ `+0x98c = 1`, push a fresh PICKUPITEM, PLAYANIMATION (10060
"get mid", or 10059 "get low" when the item is at most 1 m above the feet, speed 1.0, 1.5 s) and
FACEOBJECT, done; second time ⇒ `AcquireItem` (`0x005158e0`), client told, `+0x98c = 0`, done.
Farther ⇒ push PICKUPITEM, FACEOBJECT and a move to a free spot within 0.5 m of the item (walk
under 2 m, run beyond), done. (high for the constants, med for the order)

**DROPITEM (9, `0x00513830`)**: params item, point x,y,z, int. Same shape around the drop point:
1.1 m, FACEPOINT instead of FACEOBJECT, the same get-low/get-mid 1.5 s animation, then the item
leaves the inventory onto the ground. (med)

**EQUIPITEM (8, `0x00510fd0`)** and **UNEQUIPITEM (0xb, `0x00513ec0`)**: params item, slot mask,
instant flag. No range, no animation, no delay at the action level: modes off, preconditions, then
the creature's equip/unequip routine (`0x00501de0` / `0x005023a0`, [party-items-saves.md](party-items-saves.md)), the
client's pending icon removed, done. Queuing (`AddEquipItemActions` `0x004f0420`,
`AddUnequipActions` `0x004f06d0`): non-commandable ⇒ only the icon cleanup; in combat (`+0x4e0`)
with `+0xac0 == 1`, a weapon-slot equip gives feedback 0xc1 (0xc2 for unequip); an EQUIP for the
same slot or item already queued (or scheduled) is rewritten instead of adding a new one
(`MergeQueuedEquip` `0x004f0310`); then, still in combat and unless the caller set its
"from the round" flag, the change becomes a combat-round entry (type 6/7, `0x004d3c30` /
`0x004d3ce0`, 1500 ms of the round, run by the 0x3f dispatcher, 3.13) and **no** action 8/0xb is
queued; out of combat, one node, in front when the caller asks. (high)

**GIVEITEM (0x22, `0x0057b6a0`)**: params item, recipient, count, int. Queued by
`ActionGiveItem` (135) through `AddGiveItemAction` (`0x0057c870`) in the **last group (0xfffe)**,
count -1 clamped to the stack size (`+0x28c`), and only when the actor is commandable and holds
the item (or both the holder and the actor are party members); the player's "put this item in the
container" order (input 0x24) uses it too. The actor walks into use range of the recipient
(approach pattern), then splits the stack when needed (`0x0055f280`) and hands it over: to a
creature (`AcquireItem` `0x005158e0`, HUD notice when it is a party member), a placeable
(`0x00584b10`) or a container item (`0x0055dca0`); base item 23 (credits) and 42 get special
handling (`0x004f3ed0`, `0x004efc30`). (med)

**TAKEITEM (0x23, `0x0057bae0`)**: params item, source, int. `ActionTakeItem` (136) through
`AddTakeItemAction` (`0x0057c980`) first queues a MOVETOPOINT to the source's position (new group,
range 1.0, run when farther than 5 m), then TAKEITEM in its own group; only when the actor is
commandable and doesn't already hold the item. The handler takes the item at once with
`AcquireItem` (creature actor) or `0x00584b10` (placeable actor); HUD notice for party members.
(med)

### 3.9 PLAYANIMATION (6, `CSWSObject::AIActionPlayAnimation` `0x0057d080`)

Params: 0 internal animation id, 1 speed, 2 duration (s), 3 first-run flag (1 when queued),
4 sound-played flag, 5 sound delay (ms). (high, from the disassembly)

The routine maps the script constant before queuing (`0x00540550`). Creatures:

| Script | Internal | Script | Internal |
|---|---|---|---|
| 0 PAUSE, unknown values | 10000 | 100 HEAD_TURN_LEFT | 10053 |
| 1 PAUSE2 | 10052 | 101 HEAD_TURN_RIGHT | 10054 |
| 2 LISTEN | 10030 | 102 PAUSE_SCRATCH_HEAD | 10055 |
| 3 MEDITATE | 10032 | 103 PAUSE_BORED | 10056 |
| 4 WORSHIP | 10033 | 104 SALUTE | 10034 |
| 5 TALK_NORMAL | 10038 | 105 BOW | 10035 |
| 6 TALK_PLEADING | 10039 | 106 GREETING | 10029 |
| 7 TALK_FORCEFUL | 10040 | 107 TAUNT | 10028 |
| 8 TALK_LAUGHING | 10041 | 108–110 VICTORY1–3 | 10044 |
| 9 TALK_SAD | 10042 | 112 INJECT | 10070 if `appearance.2da` MODELTYPE is B or F, else 10000 |
| 10 GET_LOW | 10059 | 113 USE_COMPUTER | 10125 |
| 11 GET_MID | 10060 | 114 PERSUADE | 10126 |
| 12 PAUSE_TIRED | 10057 | 115 ACTIVATE | 10127 |
| 13 PAUSE_DRUNK | 10058 | 116 CHOKE | 10150 |
| 14 FLIRT | 10120 | 117 THROW_HIGH | 10129 |
| 15 USE_COMPUTER | 10121 | 118 THROW_LOW | 10130 |
| 16 DANCE | 10122 | 119 CUSTOM01 | 10142 |
| 17 DANCE1 | 10123 | 120 TREAT_INJURED | 10159 |
| 18 HORROR | 10124 | | |
| 19 READY, 20 DEACTIVATE | 10118 | | |
| 21 SPASM | 10023 | | |
| 22 SLEEP | 10137 | | |
| 23 PRONE | 10139 | | |
| 24 PAUSE3 | 10151 | | |
| 25 WELD | 10152 | | |
| 26 DEAD | 10006 | | |
| 27 TALK_INJURED | 10154 | | |
| 28 LISTEN_INJURED | 10155 | | |
| 29 TREAT_INJURED | 10160 | | |
| 30 DEAD_PRONE | 10156 | | |
| 31 KNEEL_TALK_ANGRY | 10163 | | |
| 32 KNEEL_TALK_SAD | 10164 | | |

Placeables: 200–203 → 10073–10076 (activate, deactivate, open, close), 204–213 (ANIMLOOP01–10) →
10106–10108, 10110–10116 (10109 is skipped); other values → 10000. Doors and other types keep the
raw value. When a conversation is running and the object is one of its two participants, the
client twin's animation is reset to 10000 first. A **negative duration** does not queue anything:
for script values 0–32 the looping animation is set on the object at once (`SetAnimation`) and stays
until something else changes it. (high)

Per frame:

1. Preconditions (fail 3).
2. First run: remember the start time in `+0xc4/+0xc8` (world day, ms), clear the first-run flag.
   For the player's own character, animations 10128 and 10131 get a sound 250 ms in
   (`gui_lockpick`); 10132, 10134, 10135, 10141 get `gui_minedisarm` and 10140 `gui_minearm` 750
   ms in; every other animation has no sound.
3. Duration ≥ 30 s: identical PLAYANIMATION nodes (same animation and speed) queued right behind
   it are deleted, so a long looping animation isn't repeated.
4. Length: the animation's length from the client model (`GetAnimationLength` `0x0063c0e0`), 1000 ms
   when unknown, divided by |speed| (speed 0 leaves it). When the duration is > 0 and the animation
   is **not** fire-and-forget (`animations.2da` column `FireForget`, `0x0063c380`), the length is
   the duration × 1000 instead. So a fire-and-forget animation ignores the duration and plays once;
   a looping animation plays for the duration, or one cycle when the duration is 0.
5. When the sound delay has passed and the sound wasn't played: play it (one-shot, `0x005d5e00`).
6. While elapsed < length: speed into `+0xd8`, `SetAnimation(id)` every frame, status 1. Then: a
   creature gets speed 1.0 and animation 10001; done.

Completion is purely time-based on the server; the client just plays what `SetAnimation` says.

### 3.10 WAIT (0x1e), DOCOMMAND (0x25), SETCOMMANDABLE (0x2f)

**WAIT (`0x0057b5b0`)**: param seconds. Preconditions; elapsed = now − the action's start time
(`+0xbc/+0xc0`, set by `RunActions` when the action first ran); status 1 while elapsed (ms) <
seconds × 1000, else done. Only the millisecond part of the difference is compared. World time, so
waits stop while the world timer stops ([gameloop.md](gameloop.md)). The start time is cleared only when an
action ends with 2 or 3, so a WAIT that runs right after an action that returned 4 (re-queued)
inherits that older start and ends early. (high)

**DOCOMMAND (`0x0057b530`)**: preconditions (fail ⇒ the node destructor deletes the situation);
otherwise `RunScriptSituation(situation, self, TRUE)`, the slot is zeroed, done. The script runs
synchronously inside `RunActions`; actions it queues on OBJECT_SELF go to the tail, after
whatever was already queued. (high)

### 3.11 Speech and sound (0xe, 0x21, 0x3e, 0x17)

All instant, all done (2). SPEAK (0xe, `0x0057b430`): modes and stealth off, the string goes to
the clients with the mapped volume (`0x00571960`). SPEAKSTRREF (0x21, `0x0057b3d0`): the same with
a TLK strref (`0x00571760`). BARKSTRING (0x3e, `0x0057ce00`): fetch the strref from the TLK, show a
bark bubble over the object on the client (`0x005edbb0`). PLAYSOUND (0x17, `0x0057cf00`): for every
player whose creature is in the same area within 1000 m, send "play this sound at this object"
(`0x0056d4a0`). (high)

### 3.12 Conversation (0x18, 0x1f, 0x20)

**DIALOGOBJECT (0x18, `CSWSObject::AIActionDialogObject` `0x0057a470`)**. Params: 0 the object
to talk to, 1 dialog resref (empty = the target's own), 2 private flag, 3 approach mode, 4 ignore
start range, 5 the other party once known (INVALID when queued). (high for params; med for the
flow, which is long and partly lost)

- `ActionStartConversation(o, sResRef, bPrivate, nType, bIgnoreStartRange, sIgnore1..6, bUseLeader)`
  (204): the six names go to the in-game GUI's ignore list, `bUseLeader` to GUI `+0xbd8`; the party
  leader's queue is cleared (`ClearAllActions(TRUE)`); then, only when no conversation is running
  (GUI `+0xb4` = 0) and OBJECT_SELF is commandable: its AI level is raised to 1, the GUI's
  "conversation pending" flag is set, and DIALOGOBJECT is queued with params (o, sResRef, bPrivate,
  1, **1**, INVALID). Param 4 is always 1 — scripted conversations never walk to the target — and
  `nConversationType` is not used. (high)
- The player's talk order queues (target, "", 0, 1, 0, INVALID) on the player.
- Handler: dead ⇒ fail (GUI flag cleared). Every party member knocked out ⇒ fail. While param 5
  is INVALID the target must exist, be commandable and alive, and the GUI must be idle; if it is
  busy the action re-queues itself in front and waits. Approach unless param 4: param 3 = 0 ⇒
  walk only if farther than 10 m; param 3 = 1 ⇒ walk into use range + 1.0 m. When the player's
  party starts a conversation away from the leader, party members are cleared and those farther
  than 30 m from the leader are placed near him (search radius 10 m) (low). Then the actual start: script
  event 7 DIALOGUE sent to the target (caller = actor) with ints (-1, -1, private, ignore-range)
  and the resref as string 0 — the target's OnDialog / conversation start ([dialogue.md](dialogue.md)). Done.
  A second phase (param 5 set) positions the two speakers face to face and hands control to the
  dialogue GUI. A knocked-out party member target first gets an effect of type 4 (low).
- CLEARING a DIALOGOBJECT clears the GUI pending flag (1.5).

**PAUSECONVERSATION (0x1f, `0x0057b290`)** sets `+0x50 = 1` (and creature `+0xa00 |= 4`);
`ActionPauseConversation` (205) does exactly that immediately instead of queuing.
**RESUMECONVERSATION (0x20, `0x0057b320`)**, queued by `ActionResumeConversation`, clears `+0x50`
and that bit, drops modes and stealth. A failed precondition calls virtual slot 48 with INVALID.
(high)

### 3.13 Combat, casting and status actions (0xc, 0x3f, 0xf, 0x2e, 0x32, 0x38, 0x11, 0x12, 0x10, 0x24, 0x34, 0x35, 0x41)

The round itself, attack rolls and damage are [combat.md](combat.md)'s; spell effects, Force point costs and
skill checks are [rules.md](rules.md)'s. (high unless marked)

**Scheduled versus direct.** Combat orders are not queued as ATTACKOBJECT / CASTSPELL /
ITEMCASTSPELL straight away. Their helpers (`AddAttackActions` `0x004fde40`, `AddCastSpellActions`
`0x004f9460`, `AddItemCastSpellActions` `0x004f8c70`) take a "direct" flag:

- *Scheduled* (what scripts and the player get): the order becomes a 0x88-byte entry in the combat
  round's scheduled list (round `+0x9b0`, inserted sorted by a due key, `0x004d3660`; refused when
  4 entries are pending, except equip/unequip entries which go to the head). Then, if the creature
  is out of combat (`+0x4e0` = 0) and is the player's creature, its queue is cleared. Finally, if
  no 0x3f node is queued (`0x004cc630` finds a node by id), one is appended (int param 1, new
  group).
- *Direct*: the real action plus its approach steps are queued, at the head when the caller asks
  (as 0x3f does).

Entry types (byte at entry `+0x10`): 1 attack and 0xb feat attack (`0x004d38b0`; cutscene attacks
`0x004d3810` mark `+0x74` and carry animation, attack result and damage), 6 / 7 equip / unequip
(`0x004d3c30` / `0x004d3ce0`), 9 cast (`0x004d39b0`), 0xa item use (`0x004d3a90`), 0xc move
(CutsceneMove, `0x004d3b30`); 2 and 3 exist but no creator was found. Common fields: `+4`
animation (10009 for attacks), `+8` duration in ms (1500 for attacks and equips), `+0x14` target.

**COMBAT dispatcher (0x3f, script id 39, `CSWSCreature::AIActionCombat` `0x005b6210`).** Per
frame:

1. Round busy (`+0x958`, an attack or cast animation in progress) or the server pause bit 2 set ⇒
   1.
2. Free the previous current entry. Nothing due (head key ≤ round `+0x944`) or attacks still
   pending (`+0x968` ≥ 1) ⇒ 2 when no round is active (the dispatcher leaves the queue), else 1.
3. Pop the due entry, make it current (round `+0x9c8`, type `+0x9d0`); unless it is an item use,
   stealth drops.
4. By type: attack ⇒ `AddAttackActions(..., front, direct)` and return **4**; 3 ⇒ round busy for
   `+8` ms, 1; equip / unequip ⇒ round busy for `+8` ms, then the equip happens at once, 1; cast ⇒
   `AddCastSpellActions(front, direct)`, 4; item use ⇒ (target a dead creature: dropped, 1)
   `AddItemCastSpellActions(front, direct)`, 4; move ⇒ push a range check (0x12 to a point / 0x11
   to an object, range 0.2, run flag) and a move, 4.

Returning 4 after pushing work to the head sends the dispatcher to the tail, behind that work; it
comes back for the next entry when the round is free. So `GetCurrentAction` reports 39 for a
creature that has only scheduled combat orders. In combat (`+0x4e0`, with `+0xac0 == 1`),
`AddEquipItemActions` / `AddUnequipActions` schedule a type 6/7 entry and **do not** queue action
8/0xb at all (assembly at `0x004f0529`), so mid-combat equips cost a 1500 ms round slot.

**Range checks 0x11 / 0x12.** `CheckInRangeOfObject` (0x11, `0x005103b0`; params target, int,
range, max range, run, int, int): target gone ⇒ 3; in range (`GetIsInUseRange`, same area) ⇒ 2;
else it pushes itself, a move and a short wait (0.3 s, 0.1 s for the player's creature) ⇒ 2.
`CheckInRangeOfPoint` (0x12, `0x005108a0`; point, area, target, run, range, int): wrong area or 2D
distance > range + 0.01 ⇒ the same retry; else 2. Each combat approach pushes, in execution order,
[move, face (0x13 / 0x31), check (0x11 / 0x12), copy of the action] (attack) or [move, check, face,
copy] (casts in front mode).

**ATTACKOBJECT (0xc, `0x005bbbf0`).** Params: 0 cutscene flag, 1 target, 2 type (1 / 0xb), 3
animation (10009), 4 duration (ms), 5 int, 6 feat, 7–9 cutscene animation, result (default 4),
damage. `AddAttackActions` (15 args): target, feat, p3, bPassive, bClearFirst, bFront, bDirect,
type, animation, duration, p11, bCutscene, cutscene animation/result/damage. Direct path refuses
non-commandable attackers, targets the perception says are invalid, and friendly creatures
(reputation ≥ 90, feedback 0xbb); marks the target's "going to be attacked by" (`+0x520`), sets
`+0x50c` (attempted attack target) when unset, may bark a battle cry (3 in 4 for an out-of-combat
party leader, 1 in 10 for other party members), and attacking a plot door sends it FAIL_TO_OPEN.
Per frame:

1. Reset the path state's approach range; `+0x52c = 3000`.
2. Fail (3), cleaning up the interact target, animation and pending attack animations, when the
   attacker is dead or knocked out, lacks the ability bits 0x80 or 0x04 in `+0x9f0` (cleared by
   stun-type effects, [rules.md](rules.md)), or targets itself.
3. Done (2) quietly when the target is gone, dead, knocked out or not attackable
   (`GetCanAttack` `0x005b48f0`: doors and placeables always; creatures need a valid perception
   entry unless the attacker is party-controlled).
4. Reach: paired fight (both wield melee weapons, `0x004d2b70`) ⇒ both path radii + 0.7, animation
   10109; otherwise attacker HITRADIUS (`appearance.2da`) + 1.6 + target HITRADIUS; doors and
   placeables GetUseRange; other objects 1.5 (`0x004f1310`). Maximum range (`0x004fb0f0`): melee
   reach + 0.5; ranged weapon its base item's `maxattackrange` (30.0 when 0).
5. Line of sight from 1.5 m above each foot (`0x0050c330`). Blocked twice from the same spot by a
   HUD creature ⇒ feedback 0xda, look for another enemy in range (`0x004f2de0`) and switch to it
   (1), or stop (2).
6. Must move when in another area, farther than the maximum range, without sight, or (NPCs only)
   closer than reach² − 0.2 (they step back). Passive attacks fail (3) instead. With clear sight,
   Force Jump is tried first (`0x005b7b30`: target ≥ 10 m away, feat 101 FORCE_JUMP and a suitable
   melee weapon, straight walkable line: applies effect 0x66 and uses the best of feats 101–103).
   Otherwise the approach above (run), or a step back to exactly `reach` from the target; 2.
7. In range: no combat round ⇒ 3; paused or round busy ⇒ 1. Start a round — paired master/slave
   rounds when the two can pair (`0x004d2c30`), animation 10109 if either side has a simple model
   (appearance MODELTYPE S or L), else a solo round with 10009 — and wait (1) until it has started;
   then set the animation, `+0x50c` = target, round busy, round timer = the node's duration,
   attack counter + 1, start the attack (`0x005bba80`, [combat.md](combat.md)) ⇒ 2.

**CASTSPELL (0xf, creature `0x00514af0`, placeable `0x00584ec0`).** The routine
(`0x0052ee50`, 48/234/501/502) pops spell, target object or location, metamagic, cheat, domain
level (48 only), projectile path type (0–3 kept, 4 → 5, other values abort) and, only for 48 with
7 arguments, bInstantSpell (234 has 6, so its flag is never read). Real casts need a commandable
caster and a known spell (class slot that knows it; cheat ⇒ slot 0xff; special ability ⇒ slot
0xfe), fake casts don't. `AddCastSpellActions` (direct) checks the spell row, area, the target in
the same area; range (`0x004eb3a0`) = `ranges.2da` PrimaryRange of the spell's Range code (P and T
2.25, S 10, M 15, L 28, W 15) + (own radius − 0.1) + (target radius − 0.1); `+0x524` = target.
Params: 0 spell, 1 class slot, 2 domain level, 3–4 ints, 5 target, 6–8 point, 9 flags (projectile
path, bit 31 fake, bit 30 instant), 10 feat (−1), 11 caster level. Per frame:

- Fail (3) when dead or knocked out, the spell row is missing, the item masks of `spells.2da`
  (ForbidItemMask, RequireItemMask) don't fit the caster's equipment, or the feat isn't owned.
  Face the target; `+0x528` = target. Real casts drop stealth and modes.
- Instant: solo round busy 1500 ms, animation 10009, the spell fires at once ⇒ 2.
- Otherwise, with conj = ConjTime, cast = CastTime, catch = CatchTime from `spells.2da` (typically
  170, 1330, 0 ms) and t = time since the action started: start (or join) a round with timers
  conj + cast + catch and signal the cast to the target; t < conj ⇒ conjure animation by the
  CastAnim code (3 → 11000, 2 → 10016, 7 → 10162, else 10015), 1.
- First frame with t ≥ conj: node `+0x70` = "the round is a master", so **a solo cast cannot be
  cleared from here on**; pay the Force points (`0x004eddd0`, failure ⇒ 3) unless cheat or already
  paid (`+0x960`); a silence-type effect (true type 0x12) interrupts with feedback 0x41 ⇒ 3. Then
  the cast animation by code (2 → 10018, 1 → 10017, 3 → 10019, 4 → 10020, 7 → 10061, 8/9 none,
  else 10061) and, once, `SpellCastAndImpact` (`0x004cdf50`): "casts" feedback, the visual to
  every client within 250 m, and AI event 8 SPELL_IMPACT to the caster after the projectile delay
  carrying spell, caster, target, item, point, ImpactScript and area. **The impact is scheduled at
  t = conj**; it lands after the projectile flight: no projectile ⇒ 0; else with d = distance,
  v = 3·ln(d) + 2, scaled by the path type (1 ×2, 5 ×1.5, 7 v = d/2, 8 ×0.4, 3 fixed 2000 ms),
  delay = d / v × 1000 ms, + 2500 ms for ProjType 6 (`0x004cb9e0`). Fake casts only show the
  visual. ⇒ 1.
- conj + cast ≤ t < total: catch animation 10161 ⇒ 3 (freed like done). t ≥ total: idle
  animation, spend one use of the feat ⇒ 2. `RunActions` then tells the round (`0x004d35c0`).
- Placeable casts have no timing: they fire at once.

**ITEMCASTSPELL (0x2e, `0x0050f170`)**, from `UseItem` (`0x004fc210`: item properties of type 10
"cast spell" with uses; 0x25 → Security; 0x2e trap kit → SETTRAP). Params: 0 item, 1 property
index, 2 int, 3 target, 4–6 point; the handler appends its own start time (7–8). The node is made
**unclearable on its first frame**. Hostile spells put the user in combat. Timing by the base
item's `itemtype` (humanoid = MODELTYPE B or F):

| itemtype | Items | Animation (humanoid / other) | Impact at | Total |
|---|---|---|---|---|
| 6 | grenades | 10130 under 10 m, else 10129 / 10001 | 700 (near) or 800 ms | 1500 ms |
| 12 | droid utility | 11001, then 11002 | client animation length − 50 ms, or 300 | 1500 ms |
| 20 | forearm shields | 10136 / 10001 | 600 ms | 1000 ms |
| 25, 26, 45 | stims, droid repair, medpacs | 10070 / 10001 (on the target creature) | 750 ms | 1500 ms |
| 47 | squad recovery kit | 10136 / 10001 | 750 ms | 1500 ms |
| other | | 10017 | 1 ms | CastTime + 1 |

A property without uses left fails with feedback 0x17 before the impact; at the impact the spell
fires with class 0xff and the item, one use is consumed. `RunActions` resets `+0x524/+0x528` when
it ends.

**HEAL (0x38, `0x00517a60`)**, Treat Injury from `UseSkill` (`0x004fbe40`) via `0x004f0900`
(needs skill 7, commandable; target, medical item, int, 1). Approach; first pass plays animation
10017 for 2 s; second pass rolls d20 in combat, 20 out of combat, + rank: removes a poison or
disease whose DC it beats, consumes the item, heals roll + rank (effect 0x27) with visual 1001;
nothing to cure and full HP ⇒ feedback 0x38, 3. (med)

**COUNTERSPELL (0x32, `0x00514270`)**, queued by `0x004fce90` from the player input only: target
farther than 28 m or in another area ⇒ approach; then sets the counter mode (`+0x4d2 = 4`,
`+0x4d4` = target) and faces it. Final status unknown. (med)

**Status actions.** APPEAR (0x34, `0x005140f0`) and DISAPPEAR (0x35, `0x005141b0`) are queued in an
unclearable group by the effect handlers of the appear / disappear effects (`0x004ecff0`,
`0x004ed060`; the latter also sends REMOVE_FROM_AREA or DESTROY_OBJECT 2000 ms later): animation
10063 / 10062 for 2000 ms, then 10001 ⇒ 2. SURRENDERTOENEMIES (0x41, `0x0051b420`): fails for HUD
creatures, else `0x00518990`: cancel combat for itself and every creature within 250 m that hates
it (reputation < 11) ⇒ 2; routine 379 queues it for non-PCs only, 476/762 act at once. REST (0x2a)
returns 2 at once; resting itself (`0x004fd1e0`: no enemy within 30 m, area allows it) happens when
it is queued, and clearing it cancels the rest (module event PLAYER_REST with 3). The stubs 0x29,
0x2b, 0x36 fail. 0x10 (`0x00513f60`, "wait while the round is active") and 0x24 (`0x00510c20`,
encounter despawn: tell the encounter, destroy self after 5000 ms, commandable off) have handlers
but no queuer.

**Feat, skill and talent routines.** `ActionUseFeat` (287 → `UseFeat` `0x004ecee0`) upgrades to
the best owned feat of the chain; attack feats (critical strike, flurry, power attack/blast,
sniper/rapid/multi shot, whirlwind and their tiers) become scheduled feat attacks; guard stances
(2, 25, 54) toggle `+0x8e0`. `ActionUseSkill` (288 → `UseSkill` `0x004fbe40`): the skill must be
usable (feedback 0 otherwise), hostile skills on friends give feedback 0xbb; Demolitions:
subskill 100 FLAGTRAP, 101 RECOVERTRAP, 102 EXAMINETRAP, else DISABLETRAP on a detected trap;
Stealth toggles stealth; Security queues OPENLOCK; Treat Injury queues HEAL. `ActionUseTalent*`
(309/310 → `0x00500ca0` / `0x004fd070`) dispatch to the item, cast, feat-attack or skill paths.
`CutsceneAttack` (503) and `CutsceneMove` (507) schedule entries (cutscene attack, type 0xc move).
`CancelCombat` (54 → `0x004fdaa0`): `ClearAllActions(TRUE)`, leave combat, forget the last hostile
actor, remove every attack/cast group (`0x004f61d0`), end the round. `SurrenderByFaction` (736)
moves a faction's creatures in the area to another faction, makes them leave combat and makes
their attackers drop them (`0x004fd960`). (high)

### 3.14 Traps (0x19–0x1d)

Queued by skill use (`0x004fbe40`, examine of a trigger uses 0x66) and, for SETTRAP, by item use
(`0x004fc210`, mines from `traps.2da`). Shape, from DISABLETRAP (`0x00519570`) (high for the
constants):

1. Modes off; target gone ⇒ timer hidden, `+0x97c = 0`, fail.
2. Not within use range + 0.25 m ⇒ approach.
3. First arrival (`+0x97c` = 0): `+0x97c = 1`; push a fresh copy, PLAYANIMATION (10134 for a door,
   10135 for a placeable, **10132 for a trigger (a mine)**, speed 1.0, **4.5 s**) and FACEOBJECT; show a
   4500 ms action timer (type 3); done.
4. Second pass: total Demolitions (`GetSkillRank(1)`) + 20 out of combat, `rand % 20 + 1` in combat,
   against the stored DisarmDC (at least 1; nothing from traps.2da is added here: a trigger's DCs
   already are traps.2da's, a laid mine's were baked in by SETTRAP); a DC above 35 cannot be beaten.
   A trigger whose creator is the actor, or whose creator and the actor are both of the party (or the
   PC), needs no roll. Success: script event 24 to the target at once (a trigger keeps the disarmer at
   `+0x2a4` for GetLastDisarmed and runs OnDisarm `+0x26c`, then gets event 11 and is destroyed; a door or
   placeable clears its trapped flag), delete reason 2 for the client (`0x004ce8a0`), the target leaves
   the area's trap list (`area+0x12c`). Failure: sound set entry 0x18; a total below DC − 10 sets the
   trap off under the actor (a trigger gets OBJECT_ENTER, a door or placeable event 26). Combat message
   9 (`0x004ec700`): actor, target, 1529 "Disable Mine", roll, rank, DC, took-20, result (4 automatic,
   1 success, 3 failed taking 20, 2 missed by more than 10, 0 failed), 324 "Demolitions"; the client
   words 1 and 4 "success" (1392), the rest "failure" (1393). No XP. (high)

The other four, from their handlers (high unless marked):

- **RECOVERTRAP** (0x1a, `0x00518c40`): animation 10060 (door, placeable) or 10141 (mine), 4.5 s,
  timer type 2; DC = DisarmDC + 10 (no cap of 35), the same own-trap rule; success: a trigger is
  destroyed (event 11, no OnDisarm; a door or placeable gets event 24), an item from traps.2da `ResRef`
  of the trap type goes into the party's repository (stacks merged, marked new, possessor the actor);
  failure below DC − 5 sets the trap off; no sound; message 1531 "Recover Mine".
- **FLAGTRAP** (0x1b, `0x0050e400`) and **EXAMINETRAP** (0x1c, `0x0050e900`): use range with no slack,
  animation 10060 (door, placeable) or 10059 (mine), 4.5 s, timer type 1 / 4; own trap automatic, no
  consequence on failure. Flag: DC = DisarmDC − 5 (at least 1); success sets the flagged field (trigger
  `+0x2c8`, door `+0x2f4`, placeable `+0x28c`), which detection then counts as found without a roll and
  which keeps the mine shown; message 0x144 with no action name. Examine: DC = DisarmDC − 7, message
  1532 "Examine Mine", changes nothing; sends the client (`0x0056f160`) the target, the success, the trap
  type and a band: 0 if DisarmDC ≤ rank + 5, 1 if ≤ + 10, 2 if ≤ + 15, 3 if ≤ + 20, else (or not
  disarmable, or DC above 35) 4. What the client shows for it was not traced.
- **SETTRAP** (0x1d, `0x00519e30`): params item (`+0x38`), target (`+0x3c`, may be invalid), point
  (`+0x40..`). P is the target's position, else the point; a zero point fails; an area with 15 or more
  armed party-set mines refuses (`0x005089d0`). The stand spot is P − normalize(actor − P) (a zero vector
  normalises to (1, 0, 0)); 1.5 m or more from it ⇒ FACEPOINT and a run there first. First pass:
  animation 10140 for 2.0 s, timer 2000 ms type 5. Second pass: the traps.2da row is the item's first
  property's subtype; total Demolitions, + 2 with 5 or more base ranks, + 20 or d20, against traps.2da
  SetDC (at least 1). At or above it the trap is made; a miss by 10 or less (or any miss taking 20)
  makes nothing and keeps the item; a worse miss (only in combat) still makes it, and it goes off only
  when the target was a trigger, door or placeable. Made: a door or placeable target is trapped in
  place; otherwise a new trigger, TrapFlag 1, at the actor's feet, a 4-vertex square of half-size 2.0 m
  (heights from the walkmesh), faction = the actor's, CreatorId = the actor, SetByPlayerParty when the
  actor is the PC or of the party, name strref traps.2da TrapName, OnTrapTriggered = TrapScript,
  DetectDC = rank + roll + DetectDCMod, DisarmDC = rank + roll + DisarmDCMod, detectable and
  disarmable; it joins the area and its trap list; no "found" flag is set (the party sees it because
  its faction is theirs). The item is spent only when the trap is made (stack − 1 or destroyed).
  Message 1530 "Set Mine" (results 1, 3, 2, 0); sound set 0x13 on success, 0x18 on failure; the
  actor's activity bits 0xe end and invisibility and stealth effects (0x2f, 0x3f) go (med).

Callers: UseSkill (`0x004fbe40`) for Demolitions queues FLAGTRAP for subskill 100, RECOVERTRAP 101,
EXAMINETRAP 102, else DISABLETRAP, through `AddTrapActions` (`0x004f9da0`); disable and recover refuse a
trapped target that is not disarmable; nothing checks that the trap was found. UseItem (`0x004fc210`)
with property 0x2e (Trap): `+0xe8` set, the area cap not reached, Demolitions usable ⇒ SETTRAP with the
item, the target and the point; the HUD's mine slot sends the leader as the target and a zero point, so
the mine lands at the user's feet. The target block's mine actions (callbacks `0x00691900` Disable,
subskill 0, and `0x00691950` Recover, subskill 101) send input message 0x12 to UseSkill.

## 4. Ranges and other constants

| Constant | Value | Where | Conf. |
|---|---|---|---|
| per-frame action budget | 1000 µs | `0x00745dcc`, RunActions | high |
| queue warnings / trims | 75, 500, 1000 nodes | RunActions | high |
| interaction range, creature target | own radius + target radius + 0.3 | `0x004ee440` | high |
| interaction range, trigger | radius + 0.5 | `0x004ee440` | high |
| interaction range, door / placeable | radius + 0.75, or 0.1 at a reachable PreciseUse node (doors: only when locked); +5.0 for corpse placeables | `0x004ee440` | high |
| in-range slack | +0.1 m | `0x004f6000` | high |
| dialog start distance (scripted, approach mode 0) | 10 m | `0x0057a470` | med |
| dialog approach (player click) | use range + 1.0 m | `0x0057a470` | med |
| party gathering for dialog | 30 m from the leader, placed within 10 m | `0x0057a470` | med |
| pick up / drop reach | 1.1 m (1.21 squared); walk under 2 m, run beyond | `0x00517410`, `0x00513830` | high |
| get-low threshold | item ≤ 1.0 m above the feet ⇒ 10059, else 10060 | same | med |
| pick up / drop / lock / unlock animation | 1.5 s at speed 1.0 | 7, 9, 0x26, 0x27 | high |
| trap animation | 4.5 s, timer 4500 ms; range + 0.25 m | 0x19 | high |
| lock / unlock timer | 1500 ms | 0x26, 0x27 | high |
| wait after open / close / use approach | 0.5 s | 0x14, 0x15, 0x28 | high |
| short retry wait | 0.3 s (0.1 s with a client twin) | `0x004eb5a0` | high |
| post-jump wait | 0.75 s | 4 | med |
| follow wait | 0.25 s (0.1 s party members) | 0x37 | med |
| random walk | home ± 7 m, wait 3 s (15 s at AI level 0), ≤ 20 shrink steps of ×0.75, min 1 m | 0x2d | high |
| flee retries / default range | 10 / 40 m | 3, 0x2c | high |
| force move default timeout | 30 s | 382, 383 | high |
| jump search radius | 20 m | 5 | high |
| creature re-path threshold | max(2.0, 0.4 × distance), 2 m on the target's destination | 1 | med |
| play-animation default length | 1000 ms when the model doesn't say | 6 | high |
| long-animation dedupe | duration ≥ 30 s | 6 | high |
| PlaySound audience | same area, within 1000 m | 0x17 | high |
| HUD action list refresh | 300 ms, 10 groups | `0x004fe210`, `0x004f6f30` | high |

## 5. Open questions

- The noreturn flag on `0x004ee440` hid the tail of about 20 handlers from the decompiled
  export; it is fixed now, so re-read MOVETOPOINT (step 2–6 above are reconstructed from a damaged
  decompilation), CHECKMOVETOOBJECT (2), DIALOGOBJECT's second phase, HEAL and the trap handlers.
- MOVETOPOINT flag bits 1, 3–9 and param 7: what each one changes in the planner ([movement.md](movement.md)).
- Who first queues ids 2 and 0xa (a scan of every `AddAction`/`AddActionToFront` call site finds
  no constant push of 2, and 0xa only in its own handler).
- The camera reset at the start of `RunActions` (client option byte `+0x6d == 5`).
- The creature fields named here only by use: `+0x9f2` (a state below 10 lets player commands keep
  the queue), `+0x4c0`, `+0x9f0` bit 2, `+0x8e8` (forces walking), `+0xac0`, `+0x9dc`.
- The placeable's side of OPEN_OBJECT / CLOSE_OBJECT (event handler `0x00587ba0`) was not read;
  the door's is in 3.6.
- DROPITEM and TAKEITEM details (the second-phase calls) and the item USEOBJECT branch.
- The approach "mode" param 3 of DIALOGOBJECT is set to 1 by both known queuers; mode 0 (10 m) may
  be dead.
- OPENLOCK sends AI event 12 UNLOCK_OBJECT and LOCK sends 13, but the door event handler
  (`0x0058b850`) has no case for them; who fires OnUnlock / OnLock (script events 29 / 28, which
  the door handles by running `+0x278` / `+0x258`) was not found.
- Scheduled combat entry types 2 and 3 (no creator found); COUNTERSPELL's final status and HEAL's
  approach (truncated exports); which effects clear the `+0x9f0` ability bits 0x80 / 0x04 / 0x02.
- Ids 0x10 and 0x24 have working handlers but no queuer; 0x1f and 0x2f neither (the routines act
  directly).
