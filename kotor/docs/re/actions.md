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
the call. The exports were rebuilt without the bug on 2026-10-04 ([noreturn-fix.md](noreturn-fix.md)),
and on 2026-10-07 the whole page was rechecked claim by claim against the full decompile (and the
disassembly where the decompile was unclear). A med claim that says "needs a runtime check" rests on
static reading alone and is surprising enough to test before relying on it. (high)

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
| `+0x70` | 4 | may-be-cleared flag, 1 when created; 0 makes `CSWSCreature::ClearAction` refuse to remove the node. Not saved (`SaveActionQueue` `0x004cc7e0` writes id, group and parameters only), so a loaded node is clearable again | high |

The node destructor (`0x004cc4d0`) frees string parameters and deletes script situations
(`DeleteScriptSituation`); a handler that consumes a situation (DoCommand) zeroes the slot first.
Throughout this page "param *n*" means value slot *n* (`+0x38 + 4n`). (high)

### 1.2 Groups

Every node carries a 16-bit group id. Two values passed to `AddAction`/`AddActionToFront` are
special (high):

- `0xffff`: start a new group. The object's counter at `+0x14` is the next id; the node gets the
  counter's current value, the counter is incremented (an increment that reaches `0xffff` wraps
  to 0, so ids run 0..`0xfffe`) and the id is also remembered at `+0x16` ("last group"). An
  issued id of `0xfffe` would later read as "join the last group" when a handler passes it back.
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
- the HUD action queue (`CSWSCreature::UpdateActionQueueDisplay` `0x004f6f30`): for the player
  character (`+0x9d4 == 1`, the PC flag, [combat.md](combat.md) 2), every 300 ms (`AIUpdate`; also on death) the first 10 groups
  that have a script-visible node are summarised (groups without one are skipped, not shown) into
  10 entries of 0x1c bytes at creature `+0x3a8`: group id, the group's `ACTION_*` id, a spell id
  (casts; for item casts the item property's spell), a point and a target, taken from the group's
  "representative" node (the last node of the group's first run that has a script id,
  `0x004cc530`). The GUI draws these as the action icons and lets the player cancel one. (med)
- `CSWSObject::RemoveActionGroup` (`0x004cc6f0`) frees every node of a group **without** asking
  `ClearAction`. `RemoveCombatActionsOnTarget` (`0x004f61d0`) uses it on every group whose
  representative is ATTACKOBJECT, CASTSPELL or ITEMCASTSPELL: all of them when called without a
  target (`CancelCombat` `0x004fdaa0`), else those aimed at the target, compared against param 5
  (CASTSPELL), param 3 (ITEMCASTSPELL) and **param 0** (ATTACKOBJECT). Param 0 of ATTACKOBJECT is
  the cutscene flag, not the target (param 1), so the targeted form never drops attack groups,
  only casts (high for the code; med that this is the shipped behaviour, needs a runtime check).
  The targeted form is reached through `ClearAttacker` (`0x004fda20`: sanctuary,
  `GetIsHiddenFrom`, `SetLastHostileActor`, `SetCombatState`), `ClearAttackersInArea`
  (`0x004fd960`: surrender by faction, `SetLastHostileActor`, `SetCombatState`, the effect 0x4f
  handler that queues DISAPPEAR) and `DoPerceptionCheck` (`0x00502ac0`). After a removal the scan restarts at group
  index 1, not 0, against the group count taken at entry. (high)
- `CSWSObject::SetActionGroupClearable` (`0x004cc790`) sets the `+0x70` flag of a whole group.
  (high)

There is no generic "when one action of a group fails, drop the rest of the group" rule in
`RunActions`: a failed node (status 3) is freed alone and the next node runs. Handlers that expand
themselves push all their sub-steps in front of the queue, so a failure of an early sub-step (a
move that cannot path) lets the later sub-steps run. In the approach pattern (1.4) the next one is
CHECKINRANGEOFOBJECT (`0x005103b0`), which does not fail when out of range: it pushes, in
execution order, a short wait (`0x004eb5a0`), a new move and a copy of itself, and returns 2. A
target that cannot be reached therefore keeps the actor retrying until something clears the
queue. (high for RunActions and 0x11; med for the consequence)

### 1.3 Running the queue: `CSWSObject::RunActions` (`0x0057f4a0`)

Called from `AIUpdate` of creatures (`0x004fe210`), placeables, doors, triggers, encounters and
areas of effect with the current world time (day, milliseconds) and the microsecond timer value
read when the AI update started. Stores, waypoints and sound objects never run actions. Order of
operations (high):

```
if the queue is not empty and this is the leader the player controls and the client option
   byte +0x6d is 5: show the main interface, restore the default camera and set input class 0
   (the option itself is left at 5)                                   (low: purpose unknown)
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
                  (param 0 is the cutscene flag in KOTOR's layout, the target is param 1;
                  UpdateActivityFromQueue 0x004f1460 and RemoveCombatActionsOnTarget read
                  param 0 / +0x84 as the target too: a leftover from a layout with the target
                  first; med)
    CASTSPELL: on status 2 or 3 a combat-round query (0x004d35c0) is called and its result
               discarded: no effect
    ITEMCASTSPELL: on any status but 1 the creature's +0x524/+0x528 are reset
    FOLLOWLEADER: status 1 when the client has no party leader yet; otherwise it (and 0x40)
                  runs only for party members (+0xa88), anyone else gets 3
    +0x1e4 = 0; AI master +0x7c = id; +0x80 = 0xffff; +0xa8/+0xac = now
    status 4: append the node at the tail
    status 1: put the node back at the head
    else:     free it; +0xbc/+0xc0 = 0 (so the next action gets a fresh start time); for any id
              but ATTACKOBJECT with an interact target set, virtual slot 48 (set interact
              target) is called with INVALID, a no-op stub (0x0060e760) for every type
    stop if status == 1, or the id is 1, 5, 0x30 or 0x33 (move to point, jump to point,
         jump to object, drive direct), or more than 1000 us have passed since the AI update
         began (constant 1000 at 0x00745dcc)
after the loop:
    queue longer than 75: warning 0xa1; longer than 500: warning 0xa4, then free nodes from
    the head while ClearAction(node, TRUE) agrees; still longer than 1000: free everything
    effect list longer than 500: warning 0xa2; longer than 1000: warning 0xa5 and two purges
    (RemoveEffectsByDurationType 1, then 2)
```

The status values are read from constants: 1 running (`0x00745dbc`), 2 done (`0x00745dc0`), 3
failed (`0x00745dc4`), 4 retry later (`0x00745dc8`). The runner treats status 2 and 3 exactly
alike (the CASTSPELL branch that tests for both has no effect). (high)

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
creature: read the microsecond timer → heartbeat → `+0xcc` → combat update → a `+0x384`
countdown (`0x004ed110`) → effect list update → `RunActions` → snap to walkmesh →
`UpdateActivityFromQueue` → trap detection. The 1 ms budget therefore also counts the heartbeat,
combat and effect work done before `RunActions`. (high; the frame itself is
[gameloop.md](gameloop.md)'s)

### 1.4 The common handler skeleton

Nearly every handler starts with the same three tests and fails (3) if any holds (high):

1. the object is dead (virtual slot 37 `GetDead`);
2. a folded always-false function (`0x0063e7f0`, "return 0");
3. for creatures: `CSWSCreature::GetIsDying` (`0x004ef890`), true for a member of the client
   party whose current hit points are below 1 (KOTOR's knocked-out companions act on nothing
   until revived).

Interaction handlers then call `ClearActivities(2)` (`0x004f87d0`), which drops the creature's
combat/Force modes (bits `0x100..0x2000` of `+0x9fc`): each one not locked in `+0xa00` is turned
off through `SetActivity`, then all six bits are cleared from `+0x9fc` (locked ones silently),
unless all six are locked, in which case nothing changes. It **keeps stealth**:
opening doors and locks, using placeables, picking up, equipping, item abilities, traps and healing
all leave a creature hiding (the Stealth skill's own description says so, 248). Stealth (activity
bit 1, `SetActivity(1, FALSE)`) is dropped by `ClearActivities(1)` (CASTSPELL unless bit 31 of
its param 9 is set; ITEMCASTSPELL of a spell whose `spells.2da` HostileSetting is set) and
`ClearActivities(4)` (counter spell, `ResolveAttack`), by SPEAK / SPEAKSTRREF, by the combat
round's next scheduled action (AIActionCombat, below: any entry but type 0xa, and a cast of a
hostile spell), and by the party-wide `SetPartyStealthMode` (`0x00563c60`: conversations,
transitions, solo mode off; it passes `bOn = 0` to `SetActivity` whatever its own argument).
`Rest` (`0x004fd1e0`) drops it too: it calls `0x004eb1b0(0xf)` (asm `0x004fd2ba`), which ends
activities 1 (stealth), 4 and 8 when they are set and not locked in `+0xa00`, then turns off
activity bits 8..0x80 and sets bit 8. (high) USEOBJECT and DIALOGOBJECT call `SetActivity(4, FALSE)`, which leaves a conversation, not
stealth. (high; corrected from an earlier "talking, opening, using all break stealth",
docs/mechanics/stealth.md)

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

and return 2. The copy runs once the move finished and, now in range, does the work. In UseObject
the move, the check and the copy carry the node's group, but FACEOBJECT and WAIT are queued with
`0xfffe`, i.e. in the object's most recently created group, which is a different group whenever
something else was queued after the use. (high)

USEOBJECT also calls `ClearActivities(2)` and `SetActivity(4, FALSE)` before the range test, so
they happen on the approaching frame too, and it fails (3) while the actor is a party member and
the in-game GUI flag `+0xb4` is set. (high)

`GetUseRange(target, &point, &range, bNoReachShortcut)` (`0x004ee440`, high):

| Target | Point | Range |
|---|---|---|
| creature | its position | own radius (path state `+8`, or `+0xc` when the target is the current path target) + target's radius (`+8`) + 0.3 |
| trigger | its position if `+0x2b4` is set, else the nearest point of its outline (`0x0058c8a0`) | own personal radius (path state `+4`); + 0.5 only for the outline point |
| placeable | nearest use node (`0x00584c20`) | 0.1 if `placeables.2da` PreciseUse (`+0x33c`) is set, the point is reachable (`0x004be5e0`) and the flag argument is 0; else radius + 0.75; then + 5.0 for corpses (`IsCorpse`, `+0x44c`) |
| door | nearest of its two sides (`0x00589240`), z snapped to the walkmesh | radius + path state `+0xc` when it is the current path target; 0.1 for a **locked** door (`+0x2c4`) whose `genericdoors.2da` PreciseUse (`+0x3c4`, med) is set, when the point is reachable; else radius + 0.75 |
| anything else | its position | own radius |

"Radius" without qualification is the actor's own personal radius (path state `+4`), the value
the range starts from; the "current path target" is path state `+0x38`. Returns 0 (range left at
the personal radius) when the target is missing or in no area.

`GetIsInUseRange(target, extra)` (`0x004f6000`): missing target, target in no area or in a
different area → false; triggers flagged `+0x2b4`: whether the actor stands inside the trigger.
Otherwise it takes `GetUseRange(target, …, 0)` and is true only when the line from 1.5 m above
the actor's feet to 1.5 m above the use point is clear (`CSWSArea::ClearLineOfSight`) **and** the
2D (x, y) distance to the use point is at most range + extra + 0.1. (high)

### 1.5 Clearing

`CSWSObject::ClearAllActions(bClearCombat)` (`0x004ccd80`, high):

1. Nothing happens unless the object is commandable (`+0xe8 == 1`).
2. For every node, ask virtual slot 29 `ClearAction(node, node == head)`; remove and free it if
   the answer is 1. "Head" is the action in progress between frames (a running action goes back
   to the head).
3. Creatures: stop the path (`0x005d0ec0` on the path state at `+0x340`), `+0xa8c = 1`, move
   target `+0x508` = INVALID, path state `+0x254` = INVALID and `+0x258..+0x260` = 0; if
   `bClearCombat`, reinitialise the combat round's five attack-data records (0x14c bytes each,
   `0x004d37e0`, [combat.md](combat.md)); the round's scheduled-action list is **not** touched.
   For a party member, set `+4` of its 0x88-byte client party slot (slots start at party
   `+0x24`, `+0` is the member's id) to -1, the same field `0x004eae80` resets.

The script routine `ClearAllActions()` (9, `0x0052f4a0`) always passes `bClearCombat = TRUE`.

`CSWSObject::ClearAction` (base, `0x004cc390`): always agrees; DIALOGOBJECT also clears the GUI's
"conversation pending" flag (`0x0062ec60(gui, 0)`), RESUMECONVERSATION clears `+0x50` (paused).
(high)

`CSWSCreature::ClearAction` (`0x004fab00`) refuses (returns 0) when node `+0x70` is 0, otherwise
undoes the action's side effects and agrees (high):

| Action | Undone when cleared |
|---|---|
| 7, 8, 9, 0xb (pick up, equip, drop, unequip) | when the creature has a client object, the client is told to remove the pending item icon (`0x0056fcb0`, `0x0056fbd0`, `0x0056fb70`, `0x0056fd80`; the icon meaning is med) |
| 0x2a REST | `0x004f3690` |
| 0xc ATTACKOBJECT | attack targets `+0x504`, `+0x50c` = INVALID, animation 10000, `0x004f7530` |
| 1 MOVETOPOINT | path state `+0x30`, `+0x38` = INVALID, `+0xa8c = 1`; if it was the head, animation 10000 (guarded only by the server message object existing) |
| 0xf CASTSPELL | spell targets `+0x524/+0x528` INVALID, combat round `0x004d3ba0`, `+0x960 = 0`, animation 10000, `0x004f7530` |
| 0x2e ITEMCASTSPELL | the same with `+0x96c = 0` |
| 0x32 COUNTERSPELL | `0x0050ee80(0, 1)` |
| 9 / 7 | animation 10000, `+0x988` / `+0x98c` = 0 (meant as phase flags, but DROPITEM's own phase flag is `+0x9a4` (3.8), which is left set) |
| 0x19–0x1d traps | animation 10000, action timer hidden, `+0x97c = 0` |
| 0x36, 0x38 | animation 10000, `+0x970/+0x974`, `+0x978` = 0 |
| 0x26 OPENLOCK, 0x27 LOCK | animation 10000, `+0x980` / `+0x984` = 0, action timer hidden; OPENLOCK's face-step flag `+0x9a4` is not reset (3.7) |
| 0x14 OPENDOOR | animation 10000, `+0x1f0 = 0` |
| 0x3d FOLLOWLEADER | for party slots 0–2: reset the client slot (`0x004eae80`) |
| 0x18, 0x20 | as the base class |
| 0x28 USEOBJECT | if the placeable is mid-opening (`+0x450`): clear it, play its close animation (10075 → 10076) when it was showing 10075, speed 1.0 |
| all | if an interact target is set (`+0x944`), clear it with `SetInteractTarget(INVALID, 0)` (`0x004f34a0`: the creature turns to face the old target if it is a game object other than itself; a dead or knocked-out creature keeps the target set); if the node was the head, the start time `+0xbc/+0xc0` is reset |

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
  Exceptions that queue anyway: ActionMoveToLocation / ActionForceMoveToLocation (`0x0053fe00`),
  ActionForceFollowObject, ActionBarkString, ActionSurrenderToEnemies (379, `0x00544830`),
  ActionUseFeat (287, `0x0052d8f0` → `UseFeat` schedules a combat-round attack) and ActionAttack
  (37: `AddAttackActions` checks `+0xe8` only on its direct path, and the routine uses the
  scheduled one). For the last two only the queueing is unchecked: the round entry and the 0x3f
  node are added, but when the dispatcher expands the entry it calls `AddAttackActions` on the
  direct path (and `AddCastSpellActions`, which also checks), so no ATTACKOBJECT is queued while
  the flag is 0 (med for the net effect). `RunActions` itself never reads the flag. (high)
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
| 1 | move (`0x005235b0`) | if the area and the destination equal the current path's within 0.1 m only the path priority byte (path state `+0x28`) is updated; else the path state is cleared, and when the creature's `+0x9f2` state is 2 and the clicked point is within 1.5 m, no move is queued: the combat round is paused 500 ms and a combat step starts instead (`StartCombatStep` kind 2 towards / 3 away from / 4 or 5 sideways of the attack target `+0x9f4`, 500 ms; med, needs a runtime check); otherwise (commandable, `+0xe8 == 1`): the combat mode off (`SetCombatMode(0, 1)`; stealth stays), the round's special attacks cleared, `PrepareForPlayerCommand(8)`, `AddMoveToPointAction(group 0xffff, or 0xfffe when +0x9f2 == 1, point, area, target, run flag, ...)` |
| 2 | attack | `AddAttackActions(target, ..., player = 1)` ([combat.md](combat.md)), no `PrepareForPlayerCommand`; stores the target at `+0x510` when it differs from the current attack target `+0x50c` |
| 3 | door | `PrepareForPlayerCommand(2)`, then `AddOpenDoorAction` when the message's word is 10021, else `AddCloseDoorAction` |
| 4 | emote | commandable only; play an animation: on self → PLAYANIMATION in front; on another object → FACEOBJECT (0x13) or, with no object, FACEPOINT (0x31), then PLAYANIMATION (speed 1, duration 0) in the same group (the face opens a group, the animation joins it with 0xfffe); clears the queue first when mode bit 8 (`+0x9fc`) is on |
| 5 | examine | per type (creature, item, trigger → a skill use 0x66, placeable, door) |
| 6 | use a feat | `UseFeat` (`0x004ecee0`) at once with the feat, a second word and the target ([combat.md](combat.md)); no `PrepareForPlayerCommand` |
| 7 | use skill | `0x004fbe40` ([rules.md](rules.md), trap actions) |
| 8 | talk | `PrepareForPlayerCommand(8)`; raises the player object's AI level to 1 when it is 0 (`+0x78`); queue DIALOGOBJECT (0x18) on the player with the target, resref "", param 2 = 0, param 3 = 1, param 4 = 0 (walk up to the target), param 5 = INVALID |
| 9 | use item / talent | `PrepareForPlayerCommand(1)` unless in combat mode (`+0x4e0`), then `UseItem` `0x004fc210`; feedback 0x17 when it fails |
| 0xa | activity mode | commandable only: `SetActivityMode(mode)`; mode 5 first queues COUNTERSPELL (0x32) at the given object through `AddCounterSpellAction` (`0x004fce90`) |
| 0xb | use object | `PrepareForPlayerCommand(2)`, `AddUseObjectAction` |
| 0xc / 0xe | unlock / lock | `PrepareForPlayerCommand(2)`, `AddUnlockObjectAction` / `AddLockObjectAction` when the door (`+0x2c4`) or placeable (`+0x260`) is locked / unlocked; unlock only when commandable |
| 0xd | rest | REST action 0x2a (`0x004fd1e0`) unless the creature is in a state that forbids it; feedback 0xd5 when not commandable |
| 0x12 / 0x23 | cast a power / use a talent | 0x12: needs the spell, flag bit 4 clear and enough Force points; `PrepareForPlayerCommand(1)` unless `+0x4e0 == 1`, then `AddCastSpellActions`. 0x23: `PrepareForPlayerCommand(1)`, then `UseTalentOnObject` (`0x00500ca0`) or, with no object, `UseTalentAtLocation` (`0x004fd070`) ([combat.md](combat.md), [rules.md](rules.md)) |
| 0x1c | turn | `SetOrientation` directly (no action) when commandable, alive and not down |
| 0x1d | drive (keyboard / stick) | `0x00523450`, commandable (`+0xe8 == 1`) only: the combat mode off (stealth stays), the round's special attacks cleared, `ClearAllActions(TRUE)`, `PrepareForPlayerCommand(8)`, queue 0x33 |
| 0x24 | put an item into a container | `AddGiveItemAction` (0x22) on the creature the message names (not necessarily the controlled one) with the placeable as recipient and the message's count |

Inventory-panel orders (equip, unequip, drop, pick up) come through `0x00523c20` and the
`Add*ItemAction(s)` helpers of section 3.8. (med)

Followers get FOLLOWLEADER (0x3d) when the client adds them to the party (`0x006364c0`), which
also sets their perception ranges from `ranges.2da` (leader slot: row 12 `PercepRngPlayer` 250/20 and
no action; follower slots: row 11 `PercepRngDefault` 20/20, into creature `+0x914/+0x918`). (med)

### 1.8 Saving

`CSWSObject::SaveActionQueue` (`0x004cc7e0`, called by `SaveObjectState`) writes every queued node
— all action types — into the object's struct (high):

```
ActionList            list, one struct (id 0) per node, in queue order
  ActionId            DWORD   internal id
  GroupActionId       WORD    group id
  NumParams           WORD
  Paramaters          list (sic), only when NumParams > 0; one struct per parameter (struct id 1)
    Type              DWORD   1..5
    Value             INT (1) | FLOAT (2) | DWORD object id (3) | CExoString (4) |
                      struct id 2 holding a saved script situation (5, [vm.md](vm.md))
```

`LoadActionQueue` (`0x004cecb0`) re-adds each node with `AddAction` and the saved group id, so the
order and groups survive; the clearable flag comes back as 1, the object's group counters
(`+0x14/+0x16`) and the per-action phase flags (object `+0x1f0`, creature `+0x980` ...) are not
saved, so an action saved mid-way restarts from its first phase. `Commandable` is a BYTE next to the list. (high)

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
| 4 | — | ContinuePath (after a jump) | C `0x0050ff20` | JumpToPoint and JumpToObject (in front) | high |
| 5 | — | JumpToPoint | C `0x0051d600` | (Action)JumpToLocation, cheat handler | high |
| 6 | — | PlayAnimation | `0x0057d080` | (Action)PlayAnimation, player emote, many handlers | high |
| 7 | 1 PICKUPITEM | PickUpItem | C `0x00517410` | ActionPickUpItem, inventory orders | high |
| 8 | — | EquipItem | C `0x00510fd0` | ActionEquipItem, ActionEquipMost*, inventory orders | high |
| 9 | 2 DROPITEM | DropItem | C `0x00513830` | ActionPutDownItem, inventory orders | high |
| 0xa | — | CheckMoveToPoint | C `0x00510670` | only itself (re-queue); no first queuer found | med |
| 0xb | — | UnequipItem | C `0x00513ec0` | ActionUnequipItem, inventory orders | high |
| 0xc | 3 ATTACKOBJECT | AttackObject | C `0x005bbbf0` | ActionAttack, player attack, AI | high |
| 0xe | — | Speak | `0x0057b430` | ActionSpeakString, cheat handler | high |
| 0xf | 4 CASTSPELL | CastSpell | C `0x00514af0`, placeable `0x00584ec0` | ActionCastSpellAt*, talents | high |
| 0x10 | — | WaitForCombatRound | C `0x00513f60` | nothing | med |
| 0x11 | — | CheckInRangeOfObject | C `0x005103b0` | approaches (move to object, use, attack, cast) | high |
| 0x12 | — | CheckInRangeOfPoint | C `0x005108a0` | approaches to a point (casts at a location, cutscene move) | high |
| 0x13 | — | FaceObject | C `0x0050fb60` | approaches, emote | high |
| 0x14 | 5 OPENDOOR | OpenDoor | `0x0057d490` | ActionOpenDoor, DoDoorAction, player | high |
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
| 0x26 | 13 OPENLOCK | OpenLock | `0x0057d9d0` | ActionUnlockObject, DoDoorAction, player, skill | high |
| 0x27 | 14 LOCK | Lock | `0x0057bec0` | ActionLockObject, player | high |
| 0x28 | 15 USEOBJECT | UseObject | `0x0057e8c0` | ActionInteractObject, DoPlaceableObjectAction, player | high |
| 0x29 | 16 ANIMALEMPATHY | (stub, fails) | C `0x005140d0` | — | high |
| 0x2a | 17 REST | Rest | C `0x005140e0` | player rest (`0x004fd1e0`) | high |
| 0x2b | 18 TAUNT | (stub, fails) | C `0x005140d0` | — | high |
| 0x2c | — | MoveAwayFromLocation | C `0x0050fd50` | ActionMoveAwayFromLocation | high |
| 0x2d | — | RandomWalk | C `0x00515ac0` | ActionRandomWalk | high |
| 0x2e | 19 ITEMCASTSPELL | ItemCastSpell | C `0x0050f170` | item use | high |
| 0x2f | — | SetCommandable | `0x0057c7b0` | nothing | high |
| 0x30 | — | JumpToObject | C `0x0051d110` | (Action)JumpToObject | high |
| 0x31 | — | FacePoint | C `0x0050fc90` | player emote, drop | high |
| 0x32 | 31 COUNTERSPELL | CounterSpell | C `0x00514270` | `AddCounterSpellAction` (`0x004fce90`): player activity-mode order 5 | high |
| 0x33 | — | DriveDirect (keyboard/stick move) | C `0x0051e6a0` | player input 0x1d | med |
| 0x34 / 0x35 | — | Appear / Disappear | C `0x005140f0` / `0x005141b0` | appear/disappear effects (`0x004ecff0`, `0x004ed060`) | high |
| 0x36 | 34 PICKPOCKET | (stub, fails) | C `0x005140d0` | — | high |
| 0x37 | 35 FOLLOW | Follow | C `0x005132e0` | ActionForceFollowObject | high |
| 0x38 | 33 HEAL | Heal | C `0x00517a60` | skill use (`0x004f0900`) | high |
| 0x3a | — | FollowRepeat | C `0x005136b0` | ActionForceFollowObject | med |
| 0x3c | — | WaitForArea | C `0x00511080` | JumpToPoint / JumpToObject into another area | high |
| 0x3d | 38 FOLLOWLEADER | FollowLeader | C `0x00511130` (party members only; while the client has no player object (`0x005ed550`) the node reports running and stays at the head) | ActionFollowLeader, party join | high |
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
| 22 ActionMoveToObject(o, bRun, fRange = 1.0) | `0x0053fb00` | 1 + 0x11 (group 0xfffe), Cmd | point = o's position, area = o's area; range = max(fRange, GetUseRange); target o; no timeout. 0x11 gets o, run, range, range, 1. A FACEOBJECT (0x13, 0xfffe) is guarded by a PreciseUse test (placeable `+0x33c`) made on the mover, which is always a creature here, so it is never queued (med, needs a runtime check) |
| 383 ActionForceMoveToObject(o, bRun, fRange, fTimeout = 30) | same | same | with the timeout |
| 23 ActionMoveAwayFromObject(o, bRun, fRange = 40) | `0x0053f990` | 3, **group 0xfffe**, Cmd | o, run, range, retries = 10 |
| 360 ActionMoveAwayFromLocation(l, bRun, fRange = 40) | `0x0052d090` | 1 then 0x2c (0xfffe), Cmd = 1 | nothing when the creature is already farther than `fRange` from `l`; else a flee point at `fRange` from `l` (own area, flag bit 3); 0x2c gets `l`'s point, run, range, retries 10 |
| 32 ActionEquipItem(o, nSlot, bInstant) | `0x005355f0` | 8 via `AddEquipItemActions` | slot 0..17 turned into the bit mask `1 << nSlot` |
| 33 ActionUnequipItem(o, bInstant) | `0x00545050` | 0xb via `AddUnequipActions` | |
| 34 ActionPickUpItem(o) | `0x005404f0` | 7 via `AddPickUpItemAction`, Cmd | item, container (INVALID), byte 0xff |
| 35 ActionPutDownItem(o) | `0x00541970` | 9 via `AddDropItemActions`, Cmd | item, drop point x,y,z, int |
| 37 ActionAttack(o, bPassive) | `0x0052e7f0` | a scheduled attack + 0x3f via `AddAttackActions` | 3.13 |
| 39 ActionSpeakString(s, nVolume) | `0x00544090` | 0xe, Cmd | string; volume mapped 0→1, 1 (whisper)→3, 2 (shout)→2, 3→0xd, 4→0xe |
| 221 SpeakString(s, nVolume) | same | — | sends the line at once |
| 240 ActionSpeakStringByStrRef(n, nVolume) | `0x00544270` | 0x21, Cmd | strref; volume 0→8, 1→10, 2→9 |
| 40 ActionPlayAnimation(n, fSpeed = 1, fDuration = 0) | `0x00540550` | 6, Cmd | internal animation, speed, duration, 1 (first-run flag); negative duration: see 3.9 |
| 300 PlayAnimation(n, fSpeed, fDuration) | same | 6 in front, after `ClearAllActions(TRUE)`, Cmd | |
| 43 ActionOpenDoor(o) | `0x00540260` | 0x14 via `AddOpenDoorAction` (`0x004cfac0`), Cmd | door, int |
| 44 ActionCloseDoor(o) | `0x0052f4f0` | 0x15 via `0x004cfb20`, Cmd | |
| 483 / 484 ActionUnlockObject / ActionLockObject(o) | `0x0052cff0` | 0x26 / 0x27 via `0x004cfb80` / `0x004cfc20`, Cmd | 0x26: target, item (INVALID), int 0; 0x27: the target only; a creature must be able to use skill 6 (Security, `0x005af880`), else nothing is queued (unlock also sends feedback 0) |
| 338 / 547 DoDoorAction / DoPlaceableObjectAction(o, n) | `0x00530360` | in front, creature, not Cmd, per `DOOR_ACTION_*` | OPEN: 0x14 (door) / 0x28 (placeable); UNLOCK: 0x26 then that open/use, same group; BASH: `AddAttackActions`; IGNORE (doors only): path state `+0xbc` = the door, nothing queued; KNOCK: when the target's `+0xf8` is 0, `AddCastSpellActions` spell 93 with the first class that has the Force points |
| 329 ActionInteractObject(o) | `0x0052cc70` | 0x28 via `AddUseObjectAction` (`0x0057c810`), Cmd, creature | `o` must be a placeable |
| 46 PlaySound(s) | `0x00541170` | 0x17, Cmd | sound resref |
| 48/234/501/502 ActionCastSpellAt*, ActionCastFakeSpellAt* | `0x0052ee50` | a scheduled cast + 0x3f via `AddCastSpellActions` (placeables: 0xf directly) | 3.13 |
| 135 ActionGiveItem(oItem, oGiveTo) | `0x0052c8b0` | 0x22, **group 0xfffe**, Cmd | item, recipient, count -1 (only a count above the stack size `+0x28c` is cut down), int; only when the actor holds the item or actor and holder are both party members |
| 136 ActionTakeItem(oItem, oTakeFrom) | same | 1 (range 1.0, run beyond 5 m; creatures only) then 0x23 in a new group, Cmd | item, source, int 1; nothing when the actor already holds the item |
| 167 ActionForceFollowObject(o, fDist = 0) | `0x0052c960` | 0x37 then 0x3a | target, run 1, follow point x,y, int 0, own x,y |
| 196 ActionJumpToObject(o, bStraight = TRUE) | `0x0052cce0` | 0x30, Cmd, creature | target, flag |
| 385 JumpToObject(o, bStraight) | same | 0x30 **in front** | |
| 214 ActionJumpToLocation(l) | `0x0052cdc0` | 5, Cmd, creature | point x,y,z; the creature's area; 1; search radius 20.0; facing x,y of `l` |
| 313 JumpToLocation(l) | same | 5 **in front** | |
| 202 ActionWait(f) | `0x00545800` | 0x1e, Cmd | seconds |
| 204 ActionStartConversation(...) | `0x0052d5b0` | 0x18 on OBJECT_SELF, Cmd | see 3.12 |
| 205 ActionPauseConversation() | `0x0052d330` | — | pauses at once (sets `+0x50`, and bit 4 of `+0xa00` on creatures), Cmd; a dead or dying object gets virtual slot `+0xc0(INVALID)` instead |
| 206 ActionResumeConversation() | `0x0052d520` | 0x20, Cmd | |
| 294 ActionDoCommand(a) | `0x0052c740` | 0x25 via `0x0057cb10`, Cmd | the situation |
| 360 ActionMoveAwayFromLocation | above | | |
| 379 / 476 / 762 (Action)SurrenderToEnemies, SurrenderRetainBuffs | `0x00544830` | non-PCs only: 0x41 for 379; 476/762 act at once | 3.13 |
| 54 CancelCombat(o) | `0x00546510` | — | `CancelCombat` `0x004fdaa0`: clears the queue and the attack/cast groups, ends the round |
| 399 / 400 / 404 ActionEquipMost* | `0x0052c7b0` ... | 8 | 404 via `0x004f3a60` |
| 287 / 288 / 309 / 310 ActionUseFeat/Skill/Talent* | `0x0052d8f0`, `0x0052d9b0`, `0x0052daf0` | feat attacks scheduled; skills: traps 0x19–0x1c, OPENLOCK, HEAL; talents dispatch | 3.13 |
| 503 CutsceneAttack, 507 CutsceneMove | `0x0052e890`, `0x0052e950` | scheduled entries + 0x3f | 3.13 |
| 700 ActionBarkString(nStrRef) | `0x0052c6a0` | 0x3e (creature, not Cmd) | only when no conversation is running (GUI `+0xb4 == 0`) |
| 671 BarkString(o, nStrRef) | `0x00548900` | — | only when no conversation is running (GUI `+0xb4 == 0`); shows the bark at once (OBJECT_INVALID: speaker-less) |
| 730 ActionFollowLeader() | `0x0052cbe0` | 0x3d | party members (`+0xa88`), Cmd = 1 |
| 45 SetCameraFacing(f) | `0x00542530` | 0x16, Cmd, creature | int 1, `f` × 57.2958, 0, 0, int 0 (a radians-to-degrees factor although nwscript gives `f` in degrees; med, needs a runtime check) |
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
| 5 | int | flags: bit 0 run; bit 1 (med: set from the player's move message `0x005235b0`; copied to path state `+0`; when the move fails or the creature cannot move, the client's update record for the creature is reset, `0x005110b0`); bit 2 a timeout was given (timeout ≠ 0); bit 3 (set by random walk and flee; path state `+0x198` while the planner runs); bits 4–6, 7–8 (carried along unread by the handler; the player's move fills 7–8 from its message); bit 9 the destination is already the target's use point (placeable/door targets, USEOBJECT's approach); bit 10 (stored in path state `+0x240`) |
| 6 | float | arrival range (path state `+0x68`, the planner's goal radius) |
| 7 | int | a byte stored in path state `+0x28` (the player move passes one from the client) |
| 8 | float | timeout in seconds (Force moves; formation moves `0x0051ac10` use 30 s) |
| 9–10 | float | an offset rotated by the client party leader's orientation and added to the leader's position, used when param 4 is a creature (FOLLOW passes its follow offset here) |
| 11–12 | int | absolute deadline (world day, ms) once a timeout started |

Queuing sets creature `+0xa8c = 2`, clears path state `+0x26c..+0x274` and resets the interact
target (`SetInteractTarget(INVALID)`). Per frame, in this order (high unless marked):

1. Common preconditions; no path state (`+0x340`) → fail. A creature a client knows (`+0x1f8`)
   whose movement state `+0xa8c` is 0, 4, 5 or 6 just reports running (1): `UpdateMovement` walks
   it every frame from the AI master ([movement.md](movement.md) 3.2). For a creature no client
   knows, `+0xa8c` is set to −1. Run is forced off when `+0x8e8 == 1`.
2. Range > 0 and the creature already within it of the destination but without a clear line of
   sight to it (`CSWSArea::ClearLineOfSight` `0x0050c330`): the range is taken as 0 this frame, so
   it walks onto the point itself. Arrival within the range is otherwise the planner's (goal radius).
3. Deadline set and reached ⇒ forced move: a JUMPTOPOINT node (destination, area, walkable search
   on, radius 1 m) — or JUMPTOOBJECT when param 4 names a target — is built and run at once
   (`0x004edba0`), `+0xa8c = 1`, done. Timeout given (bit 2 and timeout > 0) ⇒ deadline = now +
   timeout × 1000 ms; a copy carrying that deadline and no timeout is queued in front, path state
   `+0x26c..+0x274` cleared, `+0xa8c = 1`, done.
4. Target object (param 4), by type; each case first stores the target's position in path state
   `+0x248`:
   - **creature (5)**. Not in any area: its stored area and position (`+0x310`/`+0x314`) differ
     from the destination (other area or more than 2 m) ⇒ a copy aimed there is queued in front,
     done. In an area: the chase point is its position — or, with an offset (params 9–10), the
     client party leader's position (party `+0x2c0`) plus the offset rotated by the leader's
     orientation (`+0x2cc`), the target then dropped. When the destination is in another area or
     farther than max(2.0, 0.4 × the creature's distance to the chase point) from it, the nearest
     safe spot to the chase point within 20 m (`0x004be860`) is taken and, if it is closer to the
     chase point than the old destination, a copy aimed at it is queued in front, done. Arrival:
     without offset `GetIsInUseRange(target, range − use range)` (`0x004f6000`, `0x004ee440`), with
     offset within ~0.03 m of the point ⇒ path cleared, animation 10000, `+0xa8c = 1`, done.
   - **trigger (7)**. A trap trigger (`+0x2bc`) ⇒ a point move to 0.5 m outside its nearest edge on
     the creature's side (`0x0058c8a0`, no target) is queued in front, done: walkers stop short of
     traps. Otherwise, in use range ⇒ script event 30 CLICKED to the trigger (caller = the
     creature, its OnClick), done.
   - **placeable (9) / door (10)**. Bit 9 clear ⇒ the destination becomes the target's use point:
     unless it already is (same range, within 0.001 m), a copy aimed at the use point with range =
     use range and bit 9 set is queued in front, `+0xa8c = 1`, done. An area-transition door
     (`0x005890d0`) already in use range: open (`+0x2cc`) ⇒ script event 30 CLICKED to the door
     (OnClick starts the transition), animation 10000, path search/points/avoidance reset,
     `+0xa8c = 1`, done; closed ⇒ script event 31 PATH_BLOCKED to the creature with the door as
     caller (OnBlocked), status running.
   - anything else, or no target: go on.
5. Can-move bit (`+0x9f0 & 2`) clear (rooted / paralysed by effects, [rules.md](rules.md)) ⇒ fail.
   The target cases above come first, so a rooted creature still clicks a trigger or door in range.
   Not in an area ⇒ running.
6. Same area and within 0.1 m of the destination ⇒ placed exactly on it when that spot is safe
   (`IsPositionSafe` `0x004be5e0`), animation 10001, done.
7. Otherwise walk. Path state `+0x2c` = the creature, `+0x30` = the target; `+0xa14 = 0`. A
   destination that differs (area, or 0.1 m) from the planner's current goal becomes the new goal
   (radius = range, start = own position, `+0x88 = 0`). While no path exists (`+0x88 = 0`), the
   planner runs with the AI time slice (`0x004c6f70`; path state `+0x194 = 1` when the creature has
   an attack target `+0x50c` and the destination is within 5 m):
   - still planning (1): status 1.
   - planned (2): move target `+0x508` = path state `+0x30` (written back to param 4 when the
     planner changed it), path state `+0x28` = param 7, animation 10002 walk or 10004 run, `+0xa98`
     = run flag, modes off (`ClearActivities(8)`), then the locomotion step: `StepMovementUnseen`
     (`0x0051bb10`) for creatures no client knows, `UpdateMovement(1)` (`0x0051d9c0`, after
     `+0xa8c = 0`) for the others; the status is the step's.
   - failed (3): animation 10000; the planner's goal is reset to the creature's own position; a
     forced move (deadline set) is placed on the destination and done (gated by a global
     `0x0083280c` that no code is seen writing); otherwise the action fails.
   With a path already planned: walk/run animation, modes off, `+0xa8c = 0`, then
   `StepMovementUnseen` for creatures no client knows, status 1 for the others.

The debug strings ("Force Timeout, executing a force move", "The Path find has Failed... Why?",
"Bailed the desired position is unsafe.", "I have no legs!...") go to an empty stub
(`0x005b5e90`): the retail build logs nothing.

**CHECKMOVETOPOINT (0xa, `0x00510670`)**: point, area, target, run. Fails when the creature cannot
move (`+0x9f0 & 2`) or the area id does not resolve. If the creature is in another area or at
least twice its personal radius (path state `+4`) from the point, it re-queues itself, a move and a
short wait in front; done. (high) **CHECKMOVETOOBJECT (2, `0x005101a0`)** is the object version:
params target, run; the target must exist; its use point and range come from `GetUseRange`; a
creature target outside any area is aimed at through its stored area and position
(`+0x310`/`+0x314`), fail if there is none. In another area or not in use range ⇒ a fresh
CHECKMOVETOOBJECT, a move to the use point (range = use range, target kept) and a short wait are
pushed in front. It resets the interact target and is done. (high) Ids 2 and 0xa are pushed as
constants only by these two handlers themselves (scan of the decompiled `AddAction` /
`AddActionToFront` calls; low on who queues them first).

**AddShortWaitToFront** (`0x004eb5a0`): the movement retries are separated by a WAIT of 0.3 s
(0.1 s for creatures with a client twin). (high)

**MOVEAWAYFROMOBJECT (3, `0x005155b0`)** and **MOVEAWAYFROMLOCATION (0x2c, `0x0050fd50`)**:
params threat (object or point), run, range, a count (the routines pass 10; default range 40 m).
3 first removes every other queued group holding a MOVEAWAYFROMOBJECT from the same object
(`0x004f1ef0`). Then, while the creature is within `range` of the threat (3: also in the same area
and with count > 0), it picks a flee point (`0x004bdf80`), re-queues itself (3 with count − 1; 0x2c
passes the count on unchanged and never checks it), and pushes a move there (run per param, flag
bit 3) and a short wait; else done. So fleeing an object gives up after 10 rounds, fleeing a
location lasts until the creature is out of range or the queue is cleared. (high)

The flee point (`0x004bdf80`, med): eight directions from the creature at 45° steps, starting
towards the threat; each a step of `range` (doubled when it would still end within `range` of the
threat), halved until the walk line is clear (up to 8 times) and dropped if none is or if it ends
closer to the threat than the creature is; each candidate is scored by its distance from the threat
× 256 straight away, × 64 at ±135°, × 16 at ±90°, × 4 at ±45°, × 1 towards; the best wins (own
position if none).

**RANDOMWALK (0x2d, `0x00515ac0`)**: params home point, area (fails when it is not an area). Each
run **deletes everything else in the queue**, then pushes (in execution order) a move, a WAIT and a
fresh RANDOMWALK. The wait is 3.0 s; when the creature's AI level is below 1 (far from the player)
it is 15.0 s and no move is made. The move target is home ± (rand() % 15 − 7) m in x and y, z
snapped to the walkmesh; if the straight walk there is blocked the distance is shrunk by 0.75 up to
21 times, giving up (no move) under 1 m. Below 30 % of the original length it is reset to the full
length: the code computes a "turn" with two cross products that cancel out, so the direction never
changes. The walk is never run. The script routine passes the creature's current position as home,
so a random walker stays near where it was when the action was queued, until cleared. (high)

**DRIVEDIRECT (0x33, `0x0051e6a0`)**: keyboard/stick movement of the controlled character,
queued by input minor 0x1d (`0x00523450`) after combat mode off and `ClearAllActions(TRUE)` (only
when commandable): direction x,y, a heading in tenths of a degree, a byte, flags, an int and a
first-frame flag. Flags: bit 0 forward, bit 1 backward, both together forward at run speed (else
walk speed); bits 2/3 sidestep; bits 4/5 turn the move by ±30°. When `+0x8e8` forces walking the
queuer clears bit 1 (so run becomes walk, and backward is dropped). [movement.md](movement.md). (med)

**CONTINUEPATH (4, `0x0050ff20`)**: pushed by JUMPTOPOINT and JUMPTOOBJECT. Not in an area ⇒
running. If the path state holds a path of two or more points, drops its first point
(`0x004c3ea0` on the path state), shifts the stored goal 5 m in x so the next MOVETOPOINT sees a
new destination and plans again, sets path state `+0xa4 = 1`, and pushes a walk to the goal and a
short wait; with fewer points the path is reset. Always pushes a WAIT of 0.75 s at the very front
and is done, so the order is: 0.75 s, short wait, move. (med)

### 3.2 Jumping (5, 0x30, 0x3c)

**JUMPTOPOINT (5, `0x0051d600`)**: params point, area (must be an area, else fail),
bWalkable-search flag (default 1), search radius (default 20.0), facing direction x, y (params
6–7, default the current facing). No path state ⇒ fail. Resets the path's avoidance and grid
search and finds a free spot near the point within the radius (`0x004be860`); none ⇒ path reset,
fail. For the party leader the client's party trail (formation history) is restarted at the spot
(`CSWCPartyTrail::Reset` `0x00637890`). Then: same area ⇒ `SetPosition`; other area ⇒ moves the
creature to that area (`0x004fa100`) and, for creatures with a client twin, pushes WAITFORAREA
(0x3c). Volumes are updated for the new position (except on that client-twin area change). Sets
the facing, pushes CONTINUEPATH (4) in front (so it runs before WAITFORAREA), sets `+0xa18 = 1`,
done. Ends the frame's loop. (high)

**JUMPTOOBJECT (0x30, `0x0051d110`)**: the same towards an object (params object,
bWalkStraightLineToPoint, passed as the walkable-search flag; radius fixed at 20 m). The spot is,
for a door, a point on its approach side (`0x00589240`) moved by twice the path state's `+8` radius;
for a waypoint, its position (and facing); otherwise the object's position; a creature outside any
area is aimed at through its stored area and position (`+0x310`/`+0x314`), fail if none. (med)

**WAITFORAREA (0x3c, `0x00511080`)**: fails for any creature but the player character (`+0x9d4`, the PC flag), runs (1) until
the creature is in an area, then done. (high)

### 3.3 Following (0x37, 0x3a, 0x3d, 0x40)

**FOLLOW (0x37, `0x005132e0`)** and **FOLLOWREPEAT (0x3a, `0x005136b0`)**:
`ActionForceFollowObject(o, fDist)` (`0x0052c960`) queues FOLLOW (target, run 1, a follow point x,y
= o's position + fDist × o's facing — replaced by the client party slot's point when the actor is a
party member —, a "there" flag 0, own position x,y) and FOLLOWREPEAT with the same first four
params. FOLLOW (target must exist, else fail) treats params 2–3 as an offset: the point P is the
client party leader's position plus that offset rotated by the leader's orientation (although the
routine stores a world point there; needs a runtime check). With the flag clear it sets the flag to
"P within 0.1 m of the stored point" and pushes a fresh FOLLOW (storing P), a WAIT (0.25 s; 0.025 s
for party members) and a move to P (target o, the offset as params 9–10), done. With the flag set
it does the same when P has moved at least the follow distance (`0x00634a70`: `PrimaryRange` of a
2DA row picked by the party table's mode, default 5.0) from the stored point, else runs (1). Both
distances include P's z unsubtracted from the stored x,y-only point, so the flag is rarely set away
from z ≈ 0 (needs a runtime check). FOLLOWREPEAT pushes itself and a FOLLOW again, so the pair never
ends by itself: following lasts until the queue is cleared. (med: the point arithmetic is
[movement.md](movement.md)'s)

**FOLLOWLEADER (0x3d, `0x00511130`)**: party members only (`+0xa88`), with a follow record
(`+0x4c0`), common preconditions, a path state, able to move (`+0x9f0 & 2`), else fail. The player
character itself fails. In an area it sets `+0xa8c = 3` (the locomotion code then follows the
leader, [movement.md](movement.md)); either way it returns 1 — it runs for ever. `RunActions` also
keeps it (status 1) while the client has no leader. (high)

**CHECKFORMATIONPOINT (0x40, `0x00510ab0`)**, pushed with a move by `0x0051ac10` (party
formation movement; params point, area, INVALID, 1, range 0.5): fails when the area does not
resolve; a party member that is not within range + 0.01 of the point or is in another area gets its
client party slot state set to 5; done. (med)

### 3.4 Facing and camera (0x13, 0x31, 0x16)

FACEOBJECT (0x13, `0x0050fb60`) turns to face an object in the same area (no turn when closer than
~0.003 m) and is done; another area, a missing object or an area/module id fails. FACEPOINT (0x31,
`0x0050fc90`) faces a point. SETCAMERAFACING (0x16, `0x005137c0`) sends the facing to the client
twin (camera, [movement.md](movement.md)). All instant. (high)

### 3.5 USEOBJECT (0x28, `CSWSObject::AIActionUseObject` `0x0057e8c0`)

Param 0 = the object. In order (high unless marked):

1. Preconditions; a party member may not use anything while a conversation is running (GUI
   `+0xb4`). The target must exist, be alive and (if a creature) not knocked out.
2. Creature actor and a target in an area: modes off and out of any conversation
   (`ClearActivities(2)`, `SetActivity(4, FALSE)`; stealth stays); if not
   `GetIsInUseRange(target, 0)` ⇒ the approach pattern of 1.4 (a running move with bit 9 set,
   0x11, face, wait 0.5 s, use), done. Then the target is recorded (virtual slot 48).
3. In range, placeable target:
   - not `Useable` (`+0x328`) ⇒ fail;
   - trapped (`+0x278`), actor a creature, the placeable's reputation towards the actor < 90 and a
     different faction (`+0x23c` vs stats `+0x78`) ⇒ script event 26 (trap triggered) to the
     placeable, fail;
   - no inventory (`+0x324` = 0) ⇒ go to step 5;
   - locked (`+0x260`), actor a creature and `UseKeyOnObject(placeable, 0)` fails ⇒ feedback
     message 13 ("locked") to the actor, go to step 5 (OnUsed still fires);
   - otherwise open it. The sound is `placeableobjsnds.2da` column `Opened` of the row given by
     `placeables.2da` `SoundAppType` for the appearance (`+0x230`), 3D at the placeable (3.15). Actor without a client twin
     (NPC): the actor plays animation 10075 and the sound plays, no GUI, then step 5. Actor with a
     client twin (the player): placeable already open (`+0x338` set) ⇒ done, no OnUsed; first pass
     ⇒ push a fresh USEOBJECT and, in front of it, a WAIT of max(the placeable's animation 312
     length, sound length) — 0.5 s when the placeable has no client twin —, the placeable plays
     10075 (its own `SetAnimation`, vtable `+0x7c`; the NPC path above calls it on the actor), mark the
     placeable's `+0x450` = opening, done; second pass (`+0x450` set) ⇒ open the container panel
     (`CSWSPlaceable::OpenInventory` `0x00587420`, bAnimate 0: the lid is already up), clear `+0x450`, the
     placeable's speed `+0xd8` = 1.0, then step 5. The 312 is `animations.2da` row 312 `close2open` on the
     placeable's model (the footlocker's 0.67 s against its `pl_footlkr_open` 0.99 s: a 1 s wait; a body bag's
     model has none, so it waits for its sound).
4. In range, item target: when the base item's flag at row `+0x70` is set and the actor has a
   client twin, opens that item's container (`0x005561a0`), or closes it
   (`CSWSItem::CloseInventory` `0x0055d800`) when it is the one the client has open; done. Any
   other target type (creature, door, ...) ⇒ done, nothing happens. (med)
5. Send script event 25 USED to the placeable (OnUsed, caller = actor), done.

### 3.6 Doors (0x14, 0x15)

**OPENDOOR (0x14, `0x0057d490`)**: params door, int (the run flag of the approach; missing or 0
counts as 1, and `AddOpenDoorAction` `0x004cfac0`, which `ActionOpenDoor` (43) and the player's
order use, passes 0, so the approach always runs). Dead, knocked out (`GetIsDying`) or an invalid
target ⇒ `+0x1f0 = 0`, fail. Then modes off (`ClearActivities(2)`).

Not a creature (a placeable or door running the action): send event 7 OPEN_OBJECT to the target
(any object type, no payload), `+0x1f0 = 0`, push WAIT 0.5 s in the node's group; done. A door
target opens; a placeable ignores it (its event handler `0x00587ba0` handles event 7 only with an
inventory payload and has no case for 6). (high)

Creature (high):

1. The target must be a door (else fail). Door not closed ⇒ done at once. A door's open state
   (`+0x2cc`, GFF `OpenState`) shows as its animation: 0 closed = 10022, 1 open one way = 10050,
   2 open the other way = 10051, 3 = 10072, forced whenever `+0x308` is 0 (`+0x308` is
   `doortypes.2da` `VisibleModel` for a door with a non-zero `Appearance`, 1 by default). The
   action tests the animation (`+0xd4`) for 10022. `CSWSDoor::SetOpenState(state, 1)`
   (`0x00589600`), which `Open` and the close event use, writes only the pending state `+0x2cd`
   and the animation; `0x00589680` later copies `+0x2cd` into `+0x2cc` and, when it changed, updates
   the area's door walkmesh (called from `0x00683f00`; med). (high)
2. Not in the same area or not in use range (`GetIsInUseRange(door, 0)`) ⇒ push, all in one new
   group: a fresh OPENDOOR (door, int); for a locked (`+0x2c4`) PreciseUse door (`+0x3c4`, from
   `genericdoors.2da` `PreciseUse`, so only doors with `Appearance` 0) a WAIT 0.5 s and a
   FACEOBJECT; then a move to the door's use point (`AddMoveToPointActionToFront`, target INVALID,
   range from `GetUseRange`, run flag = the int). Order of execution: move, face, wait, OPENDOOR.
   `+0x1f0 = 1`; done.
3. In range: trapped (`+0x2e8`), door's reputation with the actor < 90 and a different faction
   (`+0x2b8` vs stats `+0x78`) ⇒ script event 26 to the door, fail. `UseKeyOnObject(door, 0)` fails
   (locked, no key) ⇒ script event 34 FAIL_TO_OPEN to the door (OnFailToOpen), `+0x1f0 = 0`, fail.
4. First arrival (`+0x1f0` = 0): push a fresh OPENDOOR (new group), `+0x1f0 = 1`, done (the copy runs
   in the same frame). Second pass (`+0x1f0` = 1): `+0x1f0 = 0`, send event 7 OPEN_OBJECT to the door
   (caller = actor), push WAIT 0.5 s in the node's group, done.

The door's side (`CSWSDoor::EventHandler` `0x0058b850`, high):

- event 7 OPEN_OBJECT ⇒ `CSWSDoor::Open(opener)` (`0x00589c70`): open state 1 when the opener
  stands in front of the door (positive dot product of opener − door with the door's facing),
  else 2 (also when the opener no longer exists), so the door swings away from the opener; the
  opener is remembered at `+0x31c` (`GetLastOpenedBy`); `SetOpenState(state, 1)` on the door and on
  its linked door (`GetLinkedDoor` `0x00589580`); then the OnOpen script (`+0x228`) runs at once.
- event 6 CLOSE_OBJECT ⇒ closer at `+0x320`, state 0 on the door and its linked door, OnClosed
  (`+0x230`).
- events 12 and 13 (UNLOCK/LOCK_OBJECT, sent by OPENLOCK and LOCK) have no case here or in the
  placeable's handler.
- script event 34 FAIL_TO_OPEN ⇒ `+0x324` = the actor, OnFailToOpen (`+0x298`); when the door is
  locked and the door's own queue holds no OPENDOOR aimed at itself, feedback 13 ("This object is
  locked.") to the actor.
- script event 26 (trap triggered) ⇒ when trapped (`+0x2e8`), the actor is not a creature immune
  to traps (immunity 5), and either the event's int 0 is set or the door's reputation with the
  actor is < 90 with a different faction: feedback 0x52 to the actor, `+0x324` = the actor,
  OnTrapTriggered (`+0x270`); a one-shot trap (`+0x304`) clears `+0x2e8` and leaves the area's trap
  list. Event 15 ON_MELEE_ATTACKED runs OnMeleeAttacked (`+0x260`) and, when `+0x2e8` is 1 and the
  attacker is within 4 m, sends script event 26 with the attacker as caller.
- script event 30 CLICKED (sent by MOVETOPOINT when it reaches a door): `+0x324` = the clicker.
  A door that is not an area transition runs OnClick (`+0x288`; the code that would default an
  empty OnClick to `NW_G0_Transition` only fires for transition doors, so it never applies) and,
  with a `LoadScreenID`, shows that load screen. A transition door runs no script: with a
  non-empty destination module (`+0x390`), no conversation running and the clicker the player's
  creature or the party leader, a first click checks that the party is near the leader (else
  `k_trg_transfail` runs on the clicker), fades out 0.5 s, forces the player pause off (`SetPauseState(2, 0)`), marks the area's transition
  pending and re-sends event 30 to itself 500 ms later with a token; that second event (matching
  token, clicker alive) sets the module transition (module `+0x390`, waypoint `+0x388`)
  ([movement.md](movement.md) / [gameloop.md](gameloop.md)).

**CLOSEDOOR (0x15, `0x0057bbf0`)**: params target, int (run flag, default 0; `AddCloseDoorAction`
`0x004cfb20` passes 0, so the approach walks). Dead, knocked out or invalid target ⇒ fail. A
creature's target must be a door or placeable (anything else fails). Creature not in the same area
or not in use range ⇒ push a fresh CLOSEDOOR (new group, target and the same int) and a move to the
use point (node's group, target INVALID, run flag = the int), done. In range (or not a creature)
⇒ event 6 CLOSE_OBJECT to the target, WAIT 0.5 s in front (node's group), done. No state check in
the action, and a placeable ignores event 6, so CLOSEDOOR on a placeable only waits. (high)

### 3.7 Locks (0x26, 0x27)

**OPENLOCK (0x26, `0x0057d9d0`)**: params target, item used (INVALID or a security tunnel), int
(the index of the item's active property that gives the bonus). (high for structure, med for the
check details, which are [rules.md](rules.md)'s)

Dead, knocked out, an invalid target or one that is not an object ⇒ timer hidden, flags
`+0x980/+0x9a4` cleared, fail. Modes off first.

1. Creature out of use range ⇒ push a fresh OPENLOCK (target and item only; the int is dropped),
   FACEOBJECT (door or placeable target) or FACEPOINT (use point, other types), and a move to the
   use point (node's group, target = the target, run), done. In range the first time (`+0x9a4` = 0)
   ⇒ `+0x9a4 = 1`, push a fresh OPENLOCK and the face action, play sound-set entry 0x17, done.
2. First pass with `+0x980` = 0 (creature): `+0x980 = 1`; push a fresh OPENLOCK and, before it,
   PLAYANIMATION (10128 `0x2790` for a door, 10131 `0x2793` otherwise, speed 1.0, 1.5 s); show a
   1500 ms action timer (`StartActionProgress` `0x004ef480`, type 7, sent only for the
   player character, `+0x9d4` = 1; message 0x30/1, whose client handler `0x00654a30`, reached from
   `HandleServerToPlayerMessage` `0x0066a640` through `0x00665590`, reads the flag, the type and the
   milliseconds and does nothing with them, so no timer is ever shown, for any type); done. For the player the animation action plays
   `gui_lockpick` 250 ms in (3.9).
3. Second pass, creature: trap check as for doors (door `+0x2e8` / `+0x2b8`, placeable `+0x278` /
   `+0x23c`; reputation < 90 and a different faction ⇒ event 26, flags cleared, fail).
   `UseKeyOnObject(target, 0)` succeeds ⇒ door: `CSWSDoor::Open` (`0x00589c70`, the door opens away
   from the user); placeable: push USEOBJECT; timer hidden, flags cleared, done.
   (`UseKeyOnObject` `0x004f0b20` is true at once for a lock that is not locked, false without a
   KeyName, else true when an item tagged KeyName is in the creature's inventory or a slot; it
   unlocks, sends event 16 to the key when AutoRemoveKey, and sends feedback 16 "You used a key.")
   Because an unlocked target passes this test, a creature never reaches step 4's "not locked".
   Key failed and the creature is no longer in use range ⇒ timer hidden, flags cleared, done.
4. Not locked ⇒ feedback 14 "That object is not locked.", fail. KeyRequired (door `+0x2d8`,
   placeable `+0x26c`) ⇒ event 34 FAIL_TO_OPEN, feedback 15 "This object cannot be opened through
   conventional means.", timer hidden, flags cleared, a combat log entry with result 5, sound-set
   entry 0x18, fail. A target that is the actor itself (a door or placeable unlocking itself) is
   unlocked (a door also opened) without a roll.
5. Security check ([rules.md](rules.md)): roll + Security rank + item bonus against the OpenLockDC
   (placeable `+0x274`, door `+0x2bf`; 0 counts as 1). The roll is d20 in combat (`+0x4e0`), else
   a fixed 20 ("take 20"). The bonus is the value (`+6`) of the item's active property number
   *int*, when `0x004eada0` accepts it. Success: Locked = 0; a door is opened by the user; a
   placeable gets USEOBJECT pushed only when the actor's stats `+0x6c` is set (likely the PC
   flag) or the actor is the party leader; then event 12 UNLOCK_OBJECT to the target and sound-set entry 0x19 (0x18 on failure).
   A combat log entry (id 0x149, formatted by the client's skill-roll case `0x0065b4a0` with dialog.tlk
   1408 "<CUSTOM0> <CUSTOM1> <CUSTOM2>: <CUSTOM3> (roll <CUSTOM4> <CUSTOM5> <CUSTOM6> <CUSTOM7>) vs. DC
   <CUSTOM8>"; 1405 is the attack-roll line) shows the roll, with result
   code 1 success, 0 failure in combat, 3 failure taking 20 below DC 60, 5 taking 20 at DC 60 or
   more ("success not possible", 1397). Then, on success **and** failure, when the item is in the
   creature's inventory its stack size (`+0x28c`) drops by one; at the last one it is removed
   (client told) and destroyed (event 11). A failed roll gives no feedback message and the action
   is done, not failed. No script event 29 is sent, so OnUnlock does not run from here.
   The feedback messages (`FormatFeedbackMessage` `0x005fcd10`): 13 prints 1437 "This object is
   locked." and also barks 1439 "Locked" over the door or placeable with the `Locked` sound of its
   `SoundAppType` row in `placeableobjsnds.2da`; 14 1430, 15 1431, 16 1432.
6. Timer hidden, flags `+0x980/+0x9a4` cleared. (`ClearAction` resets `+0x980` but not `+0x9a4`,
   so an OPENLOCK cleared after its face step leaves `+0x9a4` set for the next OPENLOCK or
   DROPITEM, which share it; med.)

**LOCK (0x27, `0x0057bec0`)**: the mirror, with differences. Param target only. Out of use range ⇒
copy, face, move as above (no separate face step, no sound-set entry). First pass (`+0x984` = 0):
`+0x984 = 1`, PLAYANIMATION 10128 (door) or 10131 (placeable) for 1.5 s and a 1500 ms timer
(type 8). Then a key (`UseKeyOnObject(target, 1)`, also true at once for a target already
locked) ⇒ timer hidden, flag cleared, done: no event and no OnLock. Already locked ⇒ feedback 13 and
fail (unreachable for a creature, see above). KeyRequired ⇒ event 34 and feedback 15, fail (no log,
no sound). The Security roll (as OPENLOCK, no item bonus) against CloseLockDC (placeable `+0x275`,
door `+0x2c0`; 0 counts as 1), or a self target, sets Locked = 1 and sends event 13 LOCK_OBJECT
and script event 28 (OnLock: door `+0x258`, placeable `+0x2c4`) to the target. Log result codes
1 / 0 / 3 (no 5). No sound-set entries. Done after a roll either way. (high)

### 3.8 Items (7, 9, 8, 0xb, 0x22, 0x23)

**PICKUPITEM (7, `0x00517410`)**: params item, container (INVALID for the ground), and a byte read
from param **3** (`+0x44`; the copies the handler pushes carry it in param 2, so they read 0).
Dead, knocked out or no item ⇒ client told, `+0x98c = 0`, fail; the item already has an owner
(`+0x268`) ⇒ fail. Within 1.1 m (squared distance 1.21) of the item: first time (`+0x98c` = 0) ⇒
`+0x98c = 1`, push a fresh PICKUPITEM, PLAYANIMATION (speed 1.0, 1.5 s) and FACEOBJECT, done. The
animation is meant to be 10060 "get mid" or 10059 "get low" by height, but the value compared with
1.0 is a local that this path never writes (0), so it is always 10059 (med, needs a runtime check).
Second time ⇒ `AcquireItem` (`0x005158e0`, with the container and the byte); success ⇒ client told,
`+0x98c = 0`, done; failure ⇒ client told, `+0x98c = 0`, fail. Farther ⇒ push PICKUPITEM, FACEOBJECT
and a move (target INVALID, range 0) to the point 1 m from the item toward the creature, moved to
the nearest safe position within 0.5 m (`FindNearestSafePosition`; the item's own position when
there is none); run flag 1 beyond 2 m, under 2 m the creature's client object pointer (non-zero,
so running, for the player's creature; 0 for others; med); done. (high for the constants)

**DROPITEM (9, `0x00513830`)**: params item, point x,y,z, int (1 = credits). Phase flag `+0x9a4`
(shared with OPENLOCK; `ClearAction` resets `+0x988` instead, med). Dead or knocked out ⇒ client
told, `+0x9a4 = 0`, fail. The item must be held by the creature or by a container the creature
holds, else the same failure. Farther than 1.1 m from the point ⇒ push DROPITEM, FACEPOINT and a
move to the point 1 m from the drop point toward the creature (no safe-position search; same run
flag rule as PICKUPITEM), done. In range, first time ⇒ `+0x9a4 = 1`, push DROPITEM, PLAYANIMATION
(1.5 s) and FACEPOINT, done; the animation is 10059 when the drop point's **world** z is ≤ 1.0, else
10060 (not the height above the feet; med, needs a runtime check). Second time ⇒ `+0x9a4 = 0`;
the item leaves the inventory (`RemoveItem`; an open container item is closed first) and is added
to the area at the point, client told, done; with int 1 the creature instead loses gold equal to
the stack size (`RemoveGold`) and the item is placed. Any failure ⇒ client told, fail. (high)

**EQUIPITEM (8, `0x00510fd0`)** and **UNEQUIPITEM (0xb, `0x00513ec0`)**: params item, slot mask
(EQUIP) or destination container (UNEQUIP; INVALID = own inventory), instant flag. EQUIP with
fewer than 3 params fails. No range, no animation, no delay at the action level: modes off,
preconditions, then the creature's equip/unequip routine (`RunEquip` `0x00501de0` / `RunUnequip`
`0x005023a0`, [party-items-saves.md](party-items-saves.md)); success ⇒ done; a failed precondition or
routine ⇒ the client's pending icon removed, fail. Queuing (`AddEquipItemActions` `0x004f0420`,
`AddUnequipActions` `0x004f06d0`): an EQUIP of an item already equipped, for slot mask 1, 2, 0x10 or
0x20, does nothing; non-commandable ⇒ nothing queued (EQUIP also removes the pending icon); in
combat (`+0x4e0`) with `+0xac0 == 1`, equipping into the body (armour) slot (mask 2), or
unequipping the item in that slot, is refused with feedback 0xc1 (1506 "You cannot equip or unequip
armor during combat!") or 0xc2, icon removed; an EQUIP for the same slot or item already queued (or
scheduled) is rewritten instead of adding a new one (`MergeQueuedEquip` `0x004f0310`, skipped when
the caller forces a new node), and an UNEQUIP of the same item likewise (`0x004f05d0`); then, still
in combat and unless the caller set its "from the round" flag, the change becomes a combat-round
entry (type 6/7, `0x004d3c30` / `0x004d3ce0`, 1500 ms of the round, run by the 0x3f dispatcher, 3.13)
and **no** action 8/0xb is queued; out of combat, one node in a new group, in front when the
caller asks. (high)

**GIVEITEM (0x22, `0x0057b6a0`)**: params item, recipient, count, notify flag. Queued by
`ActionGiveItem` (135) through `AddGiveItemAction` (`0x0057c870`) in the **last group (0xfffe)**
with count -1 and notify 1; a count larger than the stack size (`+0x28c`) is clamped to it, -1 is
kept and means the whole stack. Queued only when the actor is commandable and holds the item (or
both the holder and the actor have `+0xa88` set, party members); the player's "put this item in
the container" order (input 0x24) uses it too. The handler has no dead/knocked-out test. Fewer than
2 params, no recipient or no item ⇒ fail. A creature out of use range of the recipient pushes a
fresh GIVEITEM, FACEPOINT (use point), CHECKINRANGEOFOBJECT (0x11) and a move to the use point
(target = recipient, run when the use point is farther than 5 m), done. Otherwise: credits (`baseitems.2da`
ItemType 23, record `+0xac`) are first taken from the actor's gold (`RemoveGold` `0x004f3ed0`) and a pazaak card (ItemType 42)
from its pazaak deck (`RemovePazaakCard` `0x004efc30`); the stack is split when the count is not
-1 (`SplitItem` `0x0055f280`); then it goes to a creature (`AcquireItem` `0x005158e0`, feedback
except for credits; HUD notice 7 when the notify flag is set and the recipient has `+0xa88`), a
placeable (`0x00584b10`) or a container item (base item `+0x70` = 1, `0x0055dca0`). Done. (high)

**TAKEITEM (0x23, `0x0057bae0`)**: params item, source, notify flag. `ActionTakeItem` (136) through
`AddTakeItemAction` (`0x0057c980`) queues, for a creature actor, a MOVETOPOINT to the source's
position (new group, target = source, range 1.0, run when farther than 5 m), then TAKEITEM in its
own new group; only when the actor is commandable and doesn't already hold the item. The handler
has no range or precondition test: no params or no item ⇒ fail; else it takes the item at once
with `AcquireItem` (creature actor) or `0x00584b10` (placeable actor); HUD notice 8 when the notify
flag is set and the **source** has `+0xa88`; done. (high)

### 3.9 PLAYANIMATION (6, `CSWSObject::AIActionPlayAnimation` `0x0057d080`)

Params: 0 internal animation id, 1 speed, 2 duration (s), 3 first-run flag (1 when queued),
4 sound-played flag, 5 sound delay (ms). (high, from the disassembly)

The routine (`ActionPlayAnimation` 40 and `PlayAnimation` 300 share `0x00540550`) maps the script
constant before queuing. Creatures:

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
client twin's animation is reset to 10000 first. A duration ≥ 0 queues PLAYANIMATION (new group,
params 0–3) only when the object is commandable: `ActionPlayAnimation` appends it,
`PlayAnimation` (300) first clears the queue (`ClearAllActions(TRUE)`) and puts it in front. A
**negative duration** does not queue anything: for script values 0–32 the looping animation is set
on the object at once (`SetAnimation`, commandable or not) and stays until something else changes
it. (high)

Per frame:

1. Preconditions (fail 3).
2. First run: remember the start time in `+0xc4/+0xc8` (world day, ms), clear the first-run flag.
   For the player's creature (`GetPlayerCreatureId`), animations 10128 and 10131 get a sound delay
   of 250 ms (`gui_lockpick`); 10132, 10134, 10135, 10141 (`gui_minedisarm`) and 10140
   (`gui_minearm`) 750 ms; every other animation is marked "sound played" (no sound). Other objects
   keep the queued sound flag and delay (both 0 from every known queuer), so for them these same
   animations play their sound on the first frame (med, needs a runtime check).
3. Duration ≥ 30 s: identical PLAYANIMATION nodes (same animation and speed) at the head of the
   queue right behind it are deleted, so a long looping animation isn't repeated.
4. Length: the animation's length in ms from the client model (`GetAnimationLength` `0x0063c0e0`;
   1000 ms when the object has no client twin, 1 when the twin has no model), divided by |speed|
   (speed 0 leaves it). When the duration is > 0 and the animation is **not** fire-and-forget
   (`animations.2da` column `FireForget`, `0x0063c380`), the length is the duration × 1000 instead.
   So a fire-and-forget animation ignores the duration and plays once; a looping animation plays
   for the duration, or one cycle when the duration is 0.
5. When the sound delay has passed and the sound wasn't played: play it (one-shot, `0x005d5e00`)
   and set the flag.
6. While elapsed (ms part of the world-time difference) < length: speed into `+0xd8`,
   `SetAnimation(id)` every frame, status 1. Then: a creature gets speed 1.0 and animation 10001;
   done.

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

All instant, all done (2), with no precondition test. SPEAK (0xe, `0x0057b430`): modes and stealth
off (`ClearActivities(2)`, `SetActivity(1, FALSE)`), the string (param 0) goes to the clients with
the volume in param 1 (`SendSpeakMessage` `0x00571960`). SPEAKSTRREF (0x21, `0x0057b3d0`): the same
with a TLK strref (`SendSpeakStrRefMessage` `0x00571760`). BARKSTRING (0x3e, `0x0057ce00`): fetch
the strref from the TLK, show a bark bubble over the object on the client (`ShowBark`
`0x005edbb0`). PLAYSOUND (0x17, `0x0057cf00`): for every player whose creature is in the same area
within 1000 m, send "play this sound at this object" (`0x0056d4a0`). (high)

### 3.12 Conversation (0x18, 0x1f, 0x20)

**DIALOGOBJECT (0x18, `CSWSObject::AIActionDialogObject` `0x0057a470`)**. Params: 0 the object
to talk to, 1 dialog resref (empty = the target's own), 2 private flag, 3 approach mode, 4 ignore
start range, 5 the other party once known (INVALID when queued). (high for params; med for the
party hand-over and the second phase)

- `ActionStartConversation(o, sResRef, bPrivate, nType, bIgnoreStartRange, sIgnore1..6, bUseLeader)`
  (204, `0x0052d5b0`): the six names go to the in-game GUI's ignore list, `bUseLeader` to GUI
  `+0xbd8`; the party leader's queue is cleared (`ClearAllActions(TRUE)`); then, only when no
  conversation is running (GUI `+0xb4` = 0) and OBJECT_SELF is commandable: its AI level is raised
  to 1 (when 0), the GUI's "conversation pending" flag is set, and DIALOGOBJECT is queued (new
  group) with params (o, sResRef, bPrivate, 1, **1**, INVALID). Param 4 is always 1 — scripted
  conversations never walk to the target — and `nConversationType` is not used. (high)
- The player's talk order (input 8) raises the AI level to 1 and queues (target, "", 0, 1, 0,
  INVALID) on the player's creature.
- Handler: dead ⇒ GUI flag cleared, fail. Every party member knocked out ⇒ the same.
- First phase (param 5 INVALID): the target must exist, be commandable and not dead, else GUI flag
  cleared, fail. When `0x004b2820` finds no player or its client creature is missing, the action
  stays running (1) (med). While the
  client is loading or paused (player or auto pause) the action re-queues itself in front, done.
  Otherwise the GUI flag is set; a creature actor drops its modes and leaves any conversation
  (`ClearActivities(2)`, `SetActivity(4, FALSE)`). Approach unless param 4: param 3 = 0 ⇒ walk
  only if farther than 10 m; param 3 = 1 ⇒ walk unless within use range + 1.0 m, and the copy it
  pushes carries param 3 = 0, so the 10 m rule decides the next pass. Walking pushes a fresh
  DIALOGOBJECT and a move (node's group, target = the target, run, range = use range + 1.0)
  toward the point halfway between the actor and the target's use point; done.
- Hand-over to the player's creature (`GetPlayerCreatureId`): when the actor is a creature whose
  client twin has `+0x3a4` set and is not the player's creature, the target has `+0x218` = 0 and a
  valid dialog resref and is not the player's creature, and the player's creature is a party member
  (`+0xa88`): in combat (`+0x4e0` and `+0xac0` = 1) ⇒ GUI flag cleared, fail. Otherwise the leader
  (party slot 0) and members 1–2 are stopped (`CancelServerActions`, `ClearAllActions(TRUE)`),
  members 30 m or more from the leader are placed at their formation slot near the leader (safe position,
  radius 10 m), the screen fades out (0.75 s), input is released, GUI `+0xb98 = 1`; a knocked-out
  player's creature gets an effect of type 4 and `+0xf0 = 1`; a DIALOGOBJECT with param 5 = the
  leader is pushed on the player's creature, and this action fails. (med)
- Then the actual start: script event 7 DIALOGUE sent to the target (caller = actor) with ints
  (-1, -1, private, ignore-range) and the resref as string 0 — the target's OnDialog /
  conversation start ([dialogue.md](dialogue.md)). Done. (When the target is the player's creature
  and its client twin has `+0x3a4`, `0x005edc30(-3, 0)` is called on the client first.)
- Second phase (param 5 set): while the GUI's fade panel is busy the action re-queues itself in
  front and fails. Then the actor and the param-5 creature swap places: the actor moves to that
  creature's position facing the target (or that creature's facing when the target is gone), the
  other moves to the actor's old position, client twins follow; GUI `+0xba4` = param 5, input
  re-acquired, `0x005edc30(-3, 0)`; then the DIALOGUE event as above, done. (med)
- CLEARING a DIALOGOBJECT clears the GUI pending flag (1.5).

**PAUSECONVERSATION (0x1f, `0x0057b290`)** sets `+0x50 = 1` (and creature `+0xa00 |= 4`);
`ActionPauseConversation` (205) does exactly that immediately, for a commandable object, instead
of queuing. **RESUMECONVERSATION (0x20, `0x0057b320`)**, queued (new group) by
`ActionResumeConversation` (206) for a commandable object, clears `+0x50` and that bit, drops modes
and stealth. A failed precondition calls virtual slot 48 with INVALID (a no-op `RET 4` in every
class checked: creature, door, placeable) and fails. (high)

### 3.13 Combat, casting and status actions (0xc, 0x3f, 0xf, 0x2e, 0x32, 0x38, 0x11, 0x12, 0x10, 0x24, 0x34, 0x35, 0x41)

The round itself, attack rolls and damage are [combat.md](combat.md)'s; spell effects, Force point costs and
skill checks are [rules.md](rules.md)'s. (high unless marked)

**Scheduled versus direct.** Combat orders are not queued as ATTACKOBJECT / CASTSPELL /
ITEMCASTSPELL straight away. Their helpers (`AddAttackActions` `0x004fde40`, `AddCastSpellActions`
`0x004f9460`, `AddItemCastSpellActions` `0x004f8c70`) take a "direct" flag:

- *Scheduled* (what scripts and the player get): the order becomes a 0x88-byte entry in the combat
  round's scheduled list (round `+0x9b0`, inserted sorted by its due key `+0x00` by
  `InsertScheduledAction` `0x004d3660`, which frees the entry instead when 4 entries are already
  pending; equip/unequip entries bypass it and go straight to the head, with no limit). Then, if
  the creature is out of combat (`+0x4e0` = 0) and is the player's creature (it has a client
  object), its queue is cleared: always for attacks, for casts only when nothing is due (the new
  entry has key 0 and is itself due, so in practice only when it was refused), for item uses only
  when something is due (med: static reading). Finally, if no 0x3f node is queued (`0x004cc630`
  finds a node by id), one is appended (int param 1, new group).
- *Direct*: the real action plus its approach steps are queued, at the head when the caller asks
  (as 0x3f does).

**The player's attack orders and the queue** (high unless marked). Every attack the player gives
reaches the server as the input message (6,2) with the feat (0 for a plain attack), and the server
calls `AddAttackActions(target, feat, 1, bPassive 0, bClearFirst 0, front 0, direct 0)`
(`0x005254c0`, case 2): the scheduled path, which never clears the scheduled list. So:

- the scheduled list holds at most **four waiting orders**: `InsertScheduledAction` frees a fifth.
  The order under way (popped by 0x3f and turned into a real ATTACKOBJECT, walking up or in its
  round) is no longer on the list, so the leader can have one attack under way and four waiting;
- out of the combat state (`+0x4e0` = 0) the server's `ClearAllActions(1)` empties the action queue
  (an approach, a walk, the 0x3f node, which it adds again) but not the scheduled list. The first
  0x3f run puts the leader in combat (the direct `AddAttackActions` signals it with itself), so from
  then on each order only adds;
- **a second click on a hostile target, or R** (`DefaultActionAttack` `0x00616800`: tutorials,
  `SetCombatMode(1)`, the message) clears nothing on the client: each one adds an attack, in combat
  mode or not, and a click on the creature already being attacked adds one more round on it. A
  first click on another object only makes it the target (`OnWorldClick`, movement.md 7.4);
- **the target block** (`UseAction` `0x00689610`, keys 1–3, the slot buttons): when the leader is
  not in combat mode it first empties the leader's scheduled list (`0x0063d490` →
  `ClearScheduledActions`) and so replaces; in combat mode it only adds. With Shift held
  (`g_bAlternateActionsHeld`) `OnActionButton` (`0x0068b970`) first runs `ClearAllCombatActions`
  (combat mode off, the server actions cancelled), so the choice replaces;
- the input handler then stores the target in `+0x510` when it is not the current attempted attack
  target `+0x50c`; only the end-of-round continuation (`0x005b6980`) clears it, when it schedules
  that same target. `GetCanEngage` reads it for a target that is the leader (combat.md 3.1);
- the bar (`UpdateCombatQueue`) shows the order under way and then the waiting ones, at most four
  icons; Clear Combat Action drops the last waiting one.

Entry types (byte at entry `+0x10`, [combat.md](combat.md) "Scheduled combat actions"): 1 attack
and 0xb feat attack (feat at `+0x5c`; `0x004d38b0`; cutscene attacks `0x004d3810` are type 1, mark
`+0x74` and carry animation `+0x78`, attack result `+0x7c` and damage `+0x80`), 6 / 7 equip /
unequip (`0x004d3c30` / `0x004d3ce0`; they also shorten the round by 1500 ms at once,
`DecrementRoundLength(1500, force)`), 9 cast (`0x004d39b0`), 0xa item use (`0x004d3a90`), 0xc move
(CutsceneMove, `0x004d3b30`: point `+0x38`, target `+0x14`, run `+0x54`); 2 and 3 exist but no
creator was found. Fields: `+4` animation (10009 for attacks, 10017 for casts), `+8` duration in ms
(1500 for attacks and equips, 500 for casts; the dispatcher reads it only for types 3, 6, 7),
`+0x14` target for attacks, equips and moves; casts and item uses keep theirs at `+0x44` (and set
the creature's attempted spell target `+0x524` when it is unset, as attacks set `+0x50c`).

**COMBAT dispatcher (0x3f, script id 39, `CSWSCreature::AIActionCombat` `0x005b6210`).** Per
frame:

1. Round busy (`+0x958`, an attack or cast animation in progress) or the server pause bit 2 set ⇒
   1.
2. Free the previous current entry. Nothing due (an entry is due when its key ≤ round Timer
   `+0x944`) or an action already started in this round (`+0x968` ≥ 1; `EndCombatRound` zeroes
   it, so one entry per round) ⇒ 2 when no round is active (the dispatcher leaves the queue),
   else 1.
3. Pop the due entry, make it current (round `+0x9c8`, type `+0x9d0`); unless it is an item use,
   stealth drops.
4. By type: attack ⇒ `AddAttackActions(target, feat +0x5c, ..., front, direct)` (a cutscene
   attack passes no feat and its forced animation, result and damage) and return **4**; 3 ⇒ round
   busy for `+8` ms, 1; equip / unequip ⇒ round busy for `+8` ms, then the equip happens at once
   (`RunEquip` / `RunUnequip`), 1; cast ⇒ `AddCastSpellActions(front, direct)`, entry freed, 4;
   item use ⇒ (target a dead creature: dropped, 1) a spell with HostileSetting drops stealth;
   unless the spell's FORCEHOSTILE is ≥ 1 or the target is the user itself, the target is cleared
   and the item is used at the entry's point (every shipped grenade, medpac and stim has no
   FORCEHOSTILE; med: static reading, needs a runtime check); then
   `AddItemCastSpellActions(front, direct)`, entry freed, 4; move ⇒ push a range check (0x12 to a
   point / 0x11 to an object, range 0.2, run flag) and a move, 4.

Returning 4 (`g_nActionStatusRetryLater`) after pushing work to the head sends the dispatcher to
the tail, behind that work; it comes back for the next entry when the round is free. So
`GetCurrentAction` reports 39 for a creature that has only scheduled combat orders. In combat
(`+0x4e0`, with `+0xac0 == 1`) and unless the caller sets its own flag (fourth argument),
`AddEquipItemActions` / `AddUnequipActions` schedule a type 6/7 entry and **do not** queue action
8/0xb at all (assembly at `0x004f0529` / `0x004f0785`), so mid-combat equips cost a 1500 ms round
slot.

**Range checks 0x11 / 0x12.** `CheckInRangeOfObject` (0x11, `0x005103b0`; params target, run,
range, max range, int, int, int): actor dead or target gone ⇒ 3; in range (`GetIsInUseRange` with
max range − the target's use range as slack, same area) ⇒ 2; else it pushes itself, a move to the
use point and a short wait (0x1e: 0.3 s, 0.1 s for a creature with a client object) ⇒ 2. A target
that is in no area is looked for at the creature's stored area and position (`+0x310..+0x31c`).
`CheckInRangeOfPoint` (0x12, `0x005108a0`; point, area, target, run, range, int): wrong area or 2D
distance > range + 0.01 ⇒ the same retry; else 2. Each combat approach pushes, in execution order,
[move, face (0x13), check (0x11), copy of the action] (attack), [move, check (0x11 / 0x12), face
(0x13 / 0x31), cast] (casts in front mode; the move only when out of range) or, for casts queued
at the back, [move, check] only when out of range, then [face, cast].

**ATTACKOBJECT (0xc, `0x005bbbf0`).** Params: 0 cutscene flag, 1 target, 2 type (1 / 0xb), 3
animation (10009), 4 duration (ms), 5 int, 6 feat, 7–9 cutscene animation, result (default 4),
damage. `AddAttackActions` (15 args): target, feat, p3, bPassive, bClearFirst, bFront, bDirect,
type, animation, duration, p11, bCutscene, cutscene animation/result/damage. Direct path refuses
non-commandable attackers (`+0xe8`), targets whose perception entry is of kind 4 (bits 0x0c), and
friendly creatures (the target's reputation of the attacker ≥ 90, feedback 0xbb); marks
"going to be attacked by" (`+0x520`) on a target that is the player character (`+0x9d4`) or the party leader;
calls `SignalCombatWith(self, self)`; sets `+0x4dc` (= not party-controlled) when the target is a
creature, `+0x50c` (attempted attack target) when unset and `+0x4e8` = bPassive; may bark a battle
cry (1 in 10 for a party member, `+0xa88`; the 3-in-4 branch for the player character out of combat
never runs because `SignalCombatWith` has just put it in combat, [combat.md](combat.md) 3.6, med);
and attacking a plot door sends it FAIL_TO_OPEN. Per frame (the order of
[combat.md](combat.md) 3.1):

1. Reset the path state's approach range and target; `+0x52c = 3000`.
2. Fail (3) when the attacker is dead or knocked out, lacks the state bits 0x80 or 0x04 in `+0x9f0`
   ([combat.md](combat.md): cleared at death), or targets itself; the cleanup clears the interact
   target, plays 10000, leaves combat mode (`SetCombatMode(0, 1)` `0x0050ee80`) and drops the
   round's queued special attacks (`0x004d4f60`).
3. Done (2) quietly when the target is gone, dead, knocked out or not attackable
   (`GetCanAttack` `0x005b48f0`: doors and placeables always; creatures need a valid perception
   entry unless the attacker is party-controlled). These checks come before the approach.
4. Animation request 10109 when both wield melee weapons (`GetBothWieldMelee` `0x004d2b70`). Reach
   (`0x004f1310`): paired (that same test) ⇒ both path radii + 0.7; otherwise attacker HITRADIUS
   (`appearance.2da`) + 1.6 + target HITRADIUS; doors and placeables GetUseRange (the aim point is
   then their use point); other objects 1.5. Maximum range (`0x004fb0f0`): melee reach + 0.5;
   ranged weapon its base item's `maxattackrange` (30.0 when 0).
5. Line of sight from 1.5 m above each foot (`0x0050c330`). Blocked twice from the same spot
   (`+0x514`) by the player character (`+0x9d4`) ⇒ feedback 0xda, clear `+0x504`, look for another enemy within
   `GetMaxAttackRange(self, targeting)` (20 m with a ranged weapon; `0x004f2de0`) and switch to it
   when it is a creature (`RetargetAttack`, 1), or stop (2).
6. Must move when in another area, farther than the maximum range, without sight, or (NPCs only)
   closer than reach² − 0.2 (2D, squared; they step back). Passive attacks (`+0x4e8`) fail (3)
   instead. A target creature that is in no area is chased to its stored area and position
   (`+0x310..+0x31c`) unless the attacker belongs to an encounter (`+0xa24`), which fails (3).
   With clear sight, Force Jump is tried first (`0x005b7b30`: creature target ≥ 10 m away, the
   order carries no other feat, feat 101 FORCE_JUMP and a suitable melee weapon, straight walkable
   line: applies effect 0x66 and uses the best of feats 101–103); when it starts, the action goes
   straight on to step 7 this frame. Otherwise the approach above (run; the check uses the reach,
   or the maximum range with a ranged weapon), or a step back to exactly `reach` from the target
   (or as far as the walk line allows); 2.
7. In range: no combat round ⇒ 3; paused or round busy ⇒ 1. Engagement and mastership
   (`GetCanEngage` `0x004d2c30`, `GetShouldBeMaster` `0x004d2d60`, [combat.md](combat.md) 3.1):
   not engageable ⇒ animation 10009 and a solo round; engageable ⇒ 10109 when both wield melee or
   either side is a simple model (appearance MODELTYPE S or L), else the node's animation, and a
   master starts its own round and the target's as slave, while a slave starts none and returns 1
   until its master has started its round. Then: store the feat in the attack record when the
   node is a feat attack (0xb) or a Force jump started this frame (no guard stance `+0x8e0`, a
   right-hand weapon), set the animation, `+0x50c` = target, pause the round by itself for the
   node's duration, `+0x968` + 1, pause the engaged partner too, pick up a pending
   `NewAttackTarget`, start the attack (`0x005bba80`, [combat.md](combat.md)) ⇒ 2.

**CASTSPELL (0xf, creature `0x00514af0`, placeable `0x00584ec0`).** The routine
(`0x0052ee50`, 48/234/501/502) pops spell, target object or location, metamagic, cheat, domain
level (48 only), projectile path type (0–3 kept, 4 → 5, other values abort) and, only for 48 with
7 arguments, bInstantSpell (234 has 6, so its flag is never read); metamagic is popped but passed
on as 0. Real casts need a commandable caster and a known spell (the first class slot, never the third,
whose class is a Force user, has enough Force points (`0x005a5550`) and has a level for the
spell (`0x0059b650`); cheat ⇒ slot 0xff; special ability ⇒ slot 0xfe with its caster level), fake
casts skip these. Both routines schedule the cast. `AddCastSpellActions` (direct) checks, for a
real cast with param 4 = 0 and a slot other than 0xff, the special-ability uses (0xfe) or the Force
points; for a real cast by a non-party creature at another creature, a perception entry (not kind
4, and seen when bit 0x10 is set); a target object in the caster's area; the spell row, an area and
a commandable caster (`+0xe8`, fake casts included); range (`0x004eb3a0`) = `ranges.2da`
PrimaryRange of the spell's Range code (P counts as T: 2.25, S 10, M 15, L 28, W row 19 15) + (own
radius − 0.1) + (target radius − 0.1); `+0x524` = target. Instant casts skip the approach.
Params: 0 spell, 1 class slot, 2 domain level, 3 metamagic, 4 "no Force cost", 5 target, 6–8
point, 9 flags (projectile path, bit 31 fake, bit 30 instant), 10 feat (−1), 11 caster level (0xff
when none). Per frame:

- Fail (3) when the caster is dead or knocked out, the spell row is missing, the item masks of
  `spells.2da` (ForbidItemMask, RequireItemMask) don't fit the caster's equipment, the feat isn't
  owned, or the target object is gone, dead or knocked out. At a location the caster turns to the
  point and `+0x528` = the area id; at an object it becomes the interact target and `+0x528` =
  target. Real casts drop stealth and modes (`ClearActivities(1)`).
- Instant: a solo round paused (by no one) for 1500 ms, animation 10009, the current attack record
  given combat feat 28 (Power Attack) and **an ordinary attack resolved on the target**
  (`ResolveAttack`), then the spell fires at once (`SpellCastAndImpact`, no "casts" feedback) ⇒ 2
  (med for the effect in play: static reading, needs a runtime check).
- Otherwise, with conj = ConjTime, cast = CastTime, catch = CatchTime from `spells.2da` (typically
  170, 1330, 0 ms) and t = time since the action started (t = 0 stores the spell, point, target
  and domain level in creature `+0x1b0..+0x1c4` and clears the fired flag `+0x1cc`):
  - Round: with no round running, start one with engagement and mastership as for attacks, mark it
    a spell round (`SetSpellCastRound(spell, fake)` `0x004d28b0`), pause it by the caster for
    total = conj + cast + catch and shorten it by total; when it is engaged with another creature,
    a real cast also starts the target's round (slave, or master when the caster is not), paused
    and shortened the same way. A real cast then calls `0x004fb9e0`, which rebuilds a list at
    creature `+0x950` of the area's creatures within 28 m (ranges row 4); the message it builds is
    freed unsent (med: the list's reader was not traced). With a round already running, not
    paused and nothing started in it (`+0x968` = 0), the cast takes it over the same way (spell
    round, pause, shortening, and the engaged partner's), without that call.
  - t < conj ⇒ conjure animation by the CastAnim code (`spells.2da` ConjAnim is never read, [rules.md](rules.md) 3.1; 3 → 11000, 2 → 10016, 7 → 10162, else
    10015), 1.
- From the first frame with t ≥ conj: while node `+0x70` is 1 it is set to the round's Engaged
  flag (`+0x9b8`), so **a solo cast cannot be cleared from here on** (an engaged one stays
  clearable and repeats this step each frame); a real cast fails (3) without an area, pays the
  Force points (`0x004eddd0`, failure ⇒ 3) unless the slot is 0xff (cheat), param 4 is set, or
  they are already paid (`+0x960`), and an entangle effect (true type 0x12, from `EffectEntangle`, routine 130) interrupts it with
  animation 10001 and feedback 0x41 ⇒ 3; the projectile delay is computed. Then, while t < conj +
  cast or the spell has not fired, the cast animation by CastAnim code (2 → 10018, 1 → 10017,
  3 → 10019, 4 → 10020, 7 → 10061, 8/9 none, else 10061) and, once: a fake cast only sends the
  visual (`BroadcastSpellVisual`); a real cast counts the action (`+0x968` + 1) and calls
  `SpellCastAndImpact` (`0x004cdf50`): "casts" feedback (not for instant casts), the visual to
  every client within 250 m, and AI event 8 SPELL_IMPACT to the caster after the projectile delay
  carrying spell, caster, target, item, point, ImpactScript and area. **The impact is scheduled at
  t = conj**; it lands after the projectile flight (`0x004cb9e0`): no projectile ⇒ 0; else with
  d = distance, v = 3·ln(d) + 2, scaled by the path type (path 0 takes the spell's ProjType;
  1 ×2, 5 ×1.5, 7 v = d/2, 8 ×0.4, 3 fixed 2000 ms), delay = d / v × 1000 ms (1 ms when v ≤ 0),
  + 2500 ms for ProjType 6. ⇒ 1.
- conj + cast ≤ t < total (only spells with a CatchTime): animation 10161 when the CatchAnim code
  is 0, `+0x960` = 0 ⇒ 3 (freed like done). t ≥ total: idle animation, `+0x960` = 0, spend one use
  of the feat ⇒ 2. `RunActions` then calls `0x004d35c0`, a side-effect-free test for a due type-2
  entry whose result it ignores.
- Placeable casts have no timing: they fire at once.

**ITEMCASTSPELL (0x2e, `0x0050f170`)**, from `UseItem` (`0x004fc210`: item properties of type 10
"cast spell" with uses; 0x25 → Security; 0x2e trap kit → SETTRAP). Params: 0 item, 1 property
index, 2 int, 3 target, 4–6 point; the handler appends its own start time (7–8). User dead or
knocked out, target gone, dead or knocked out, or item, property or spell missing ⇒ 3. The node is
made **unclearable on its first frame** (`+0x70` = 0). A spell with HostileSetting drops stealth
and puts the user in combat (`SetCombatState(1, 1)`); others call `ClearActivities(2)`. With no
round running, one is started as a spell round (`SetSpellCastRound(0, 0)`), paused by the user for
the total and shortened by it: grenades mark it engaged and master without consulting the target,
other items decide as for attacks but start no round for the target. Timing by the base item's
`itemtype` (humanoid = the user's MODELTYPE B or F):

| itemtype | Items | Animation (humanoid / other) | Impact at | Total |
|---|---|---|---|---|
| 6 | grenades | 10130 under 10 m, else 10129 (animations.2da rows 58 `throwgren1` and 57 `throwgren`) / 10001 | 700 (near) or 800 ms: the grenade leaves the hand; the impact script runs when it lands, after the projectile's flight ([render-gui.md](render-gui.md) "Spell projectiles") | 1500 ms |
| 12 | droid utility | 11001, then 11002 | client animation length − 50 ms, or 300 | 1500 ms |
| 20 | forearm shields | 10136 / 10001 | 600 ms | 1000 ms |
| 25, 45 | stims, medpacs | 10070 / 10001, played by the target creature when there is one | 750 ms | 1500 ms |
| 26 | droid repair | 10070 / 10001 | 750 ms | 1500 ms |
| 47 | squad recovery kit | 10136 / 10001, played by the target creature when there is one | 750 ms | 1500 ms |
| other | | 10017 | 1 ms | CastTime + 1 |

Before the impact a property without uses left (cost table other than 7 and 0xd) fails with
feedback 0x17 ⇒ 3; at the impact the spell fires with class 0xff and the item
(`SpellCastAndImpact`, round `+0x968` + 1), a due type-2 entry is removed, one use is consumed, and
a droid utility switches the node to a short tail that only plays 11002 until the total. t ≥ total
⇒ idle animation, 2. `RunActions` resets `+0x524/+0x528` when it ends.

**HEAL (0x38, `0x00517a60`)**, Treat Injury from `UseSkill` (`0x004fbe40`) via `0x004f0900`
(needs skill 7, feedback 0 otherwise; commandable; target, medical item, int, 1). Dead or knocked
out healer ⇒ 3; target not a creature or item gone ⇒ 3. Out of use range with param 3 set ⇒ push
[move, check 0x11, face, copy with param 3 = 0] ⇒ 2 (the copy no longer checks range). First pass
(creature `+0x978` = 0): queue PLAYANIMATION 10017 for 2 s and a copy behind it ⇒ 2. Second pass:
roll d20 in combat, 20 out of combat, + Treat Injury rank against the target; of the target's
poison (0x23) and disease (5) effects only the first in its list (sorted by type; asm `0x00517e10`–`0x00517eb9`) is tried, against poison.2da
Save_DC or disease.2da Subs_Save (at least 1), and removed when roll + rank ≥ DC; nothing to cure
⇒ feedback 0x37, and with full HP also 0x38 ⇒ 3; otherwise the roll is reported (message 0x14a with roll, rank, DC, take-20 flag and outcome),
one item of the stack is consumed (the last one destroyed), the target is healed roll + rank
(effect 0x27) with visual 1001 (effect 0x1e) ⇒ 2. poison.2da has no `Save_DC` column (its DC column is
`dc_save`), so the lookup fails and a poison's DC is 1: any treatment cures it. The roll message's ints 0 and 6 are
0x14a = 330, dialog.tlk "Treat Injury" (Security's is 0x149 = 329), the skill-roll line of 3.9. Feedback 0x37 and
0x38 are formatted with string 0 (nothing shown). Ours: `rt_act::heal`. (high)

**COUNTERSPELL (0x32, `0x00514270`)**, queued by `0x004fce90` from the player input only: actor dead
or knocked out, or target creature gone, dead or knocked out ⇒ 3; target in no area ⇒ 1. Target
farther than 28 m (ranges row 4) or in another area: without state bit 0x02 (`+0x9f0`) feedback 7
⇒ 3; with it, push [short wait, move, check 0x11, copy] ⇒ 2. In range: `SignalCombatWith(target)`,
combat mode 4 (`+0x4d2`, activity 0x800 replacing the old mode's bit), `+0x4d4` = target, interact
target ⇒ 1, every frame until the action is cleared, which leaves the mode (`SetCombatMode(0, 1)`).
(med)

**Status actions.** APPEAR (0x34, `0x005140f0`) and DISAPPEAR (0x35, `0x005141b0`) are queued, for
commandable creatures only, in an unclearable group by `0x004ecff0` / `0x004ed060`, which the
effect handlers call (appear: removal of effect 0x4f, apply of 0x51; disappear: apply of 0x4f and
0x50; the latter also sends REMOVE_FROM_AREA or DESTROY_OBJECT 2000 ms later): animation
10063 / 10062 for 2000 ms, then 10001 ⇒ 2. SURRENDERTOENEMIES (0x41, `0x0051b420`): fails for HUD
creatures, else `SurrenderToEnemies(0)` (`0x00518990`, [combat.md](combat.md) 8.5: cancel combat
and remove effects for itself and every creature within 250 m it counts an enemy, reputation < 11,
then move itself to the Neutral faction) ⇒ 2; routine 379 queues it, 476/762 act at once, all three
only for a caller whose stats `+0x6c` is clear. REST (0x2a) returns 2 at once; resting itself
(`0x004fd1e0`: refused in an area that forbids it, feedback 0x36, with an enemy within 30 m, 0xba,
or while the player character's battle-music countdown runs, 0x11) happens when it is queued, and
clearing it cancels the rest (module event PLAYER_REST with 3). The rest command is input message 0xd, but
no client code sends it (there is no `SendPlayerToServerInput` for it, and no key or button rests), and the
client formats feedback 0x11, 0x12, 0x36 and 0xba with string 0 (`FormatFeedbackMessage` `0x005fcd10`): empty.
Ours: `party::rest` (test command `ui rest`), with the player's fight countdown taken as being in combat. (high) The stubs 0x29, 0x2b, 0x36 fail.
0x10 (`0x00513f60`, "wait while the round is active") and 0x24 (`0x00510c20`, encounter despawn:
tell the encounter, destroy self after 5000 ms, commandable off) have handlers but no queuer.

**Feat, skill and talent routines.** `ActionUseFeat` (287 → `UseFeat` `0x004ecee0`) upgrades to
the best owned feat of the chain; attack feats (critical strike, flurry, power attack/blast,
sniper/rapid/multi shot, whirlwind and their tiers) are scheduled as attacks (1500 ms), but
`UseFeat` passes the feat as the entry's `+0x84` argument and 0 as its combat feat, so the entry is
a plain attack (type 1) and the dispatcher, which takes the feat from `+0x5c`, attacks without it
(med: static reading, needs a runtime check); guard stances (2, 25, 54) toggle `+0x8e0`.
`ActionUseSkill` (288 → `UseSkill` `0x004fbe40`): the skill must be usable (feedback 0 otherwise),
hostile skills on friends give feedback 0xbb; Demolitions: subskill 100 FLAGTRAP, 101 RECOVERTRAP,
102 EXAMINETRAP, else DISABLETRAP (nothing checks that the trap was found; a trapped target that
is not disarmable is refused, below); Stealth toggles stealth; Security queues
OPENLOCK; Treat Injury queues HEAL. `ActionUseTalent*` (309/310 → `0x00500ca0` / `0x004fd070`)
dispatch to the item, cast, feat-attack (`AddAttackActions` with the feat, so type 0xb) or skill
paths. `CutsceneAttack` (503) and `CutsceneMove` (507) schedule entries (cutscene attack, type 0xc
move). `CancelCombat` (54 → `0x004fdaa0`): `ClearAllActions(TRUE)`, leave combat, forget the last
hostile actor, remove every attack/cast group (`0x004f61d0`), end the round, clear its target and
the client creature's combat mode. `SurrenderByFaction` (736) moves a faction's creatures in the
area to another faction, makes them leave combat and clears their actions, and makes their
attackers drop them (`0x004fd960`). (high)
### 3.14 Traps (0x19–0x1d)

Queued by skill use (`0x004fbe40`, Demolitions with a subskill) and, for SETTRAP, by item use
(`0x004fc210`, mines from `traps.2da`). Shape, from DISABLETRAP (`0x00519570`) (high for the
constants):

1. Modes off; target gone ⇒ timer hidden, `+0x97c = 0`, fail.
2. Not within use range + 0.25 m ⇒ approach: a fresh copy, FACEOBJECT and a run to the use point
   with range use range + 0.25, done.
3. First arrival (`+0x97c` = 0): `+0x97c = 1`; push a fresh copy, PLAYANIMATION (10134 for a door,
   10135 for a placeable, **10132 for a trigger (a mine)**, speed 1.0, **4.5 s**) and FACEOBJECT; show a
   4500 ms action timer (type 3); done.
4. Second pass: total Demolitions (`GetSkillRank(1)`) + 20 out of combat, `rand % 20 + 1` in combat,
   against the stored DisarmDC (at least 1; nothing from traps.2da is added here: a trigger's DCs
   already are traps.2da's, a laid mine's were baked in by SETTRAP); a DC above 35 cannot be beaten.
   A trigger whose creator (`+0x2e4`) is the actor, or whose creator and the actor are both of the
   party (or the PC), needs no roll; doors and placeables have no such rule. Success: script event 24
   to the target at once (a trigger keeps the disarmer at `+0x2a4` for GetLastDisarmed and runs
   OnDisarm `+0x26c`, then gets event 11 and is destroyed, with delete reason 2 for the client
   (`0x004ce8a0`); a door or placeable that is trapped clears its trapped flag, keeps the disarmer
   (door `+0x328`, placeable `+0x360`) and runs its OnDisarm (door `+0x248`, placeable `+0x2ac`)), and
   the target leaves the area's trap list (`area+0x12c`). Failure: sound set entry 0x18; a total below
   DC − 10 sets the trap off under the actor (a trigger gets OBJECT_ENTER, a door or placeable event
   26). Combat message 9 (`0x004ec700`, sent only when the actor has a client): actor, target, 1529
   "Disable Mine", roll, rank, DC, took-20, result (4 automatic, 1 success, 3 failed taking 20, 2
   missed by more than 10, 0 failed; a total at or above a DC over 35 leaves the result unset), 324
   "Demolitions"; the client words 1 and 4 "success" (1392), the rest "failure" (1393). No XP. (high)

The other four, from their handlers (high unless marked):

- **RECOVERTRAP** (0x1a, `0x00518c40`): the same approach (+ 0.25 m); animation 10060 (door,
  placeable) or 10141 (mine), 4.5 s, timer type 2; DC = DisarmDC + 10 (no cap of 35), the same
  own-trap rule; success: a trigger is destroyed (event 11 and delete reason 2, no OnDisarm; a door or
  placeable gets event 24, which runs its OnDisarm as above), an item from traps.2da `ResRef` of the
  trap type (trigger `+0x2d4`, door `+0x2f8`, placeable `+0x290`) goes into `GetItemRepository(1)`
  (the party inventory for a party member, else the actor's own; stacks merged, marked new, possessor
  the actor), and the target leaves the trap list (only when the `ResRef` cell was read); failure
  below DC − 5 sets the trap off (OBJECT_ENTER / event 26); no sound; message 1531 "Recover Mine"
  with the disable result codes (2 still means a miss by more than 10).
- **FLAGTRAP** (0x1b, `0x0050e400`) and **EXAMINETRAP** (0x1c, `0x0050e900`): use range with no slack,
  animation 10060 (door, placeable) or 10059 (mine), 4.5 s, timer type 1 / 4; a mine whose creator is
  the actor is automatic (no party rule here), no consequence on failure, no DC cap. Flag: DC =
  DisarmDC − 5 (at least 1); success sets the flagged field (trigger `+0x2c8`, door `+0x2f4`,
  placeable `+0x28c`), which detection (`0x004fa390`) then counts as found without a roll and which
  keeps the mine shown (animation 10144, `0x0058d760`); message with no target and no action name
  (results 4, 1, 3, 0), skill 324. Examine: DC = DisarmDC − 7 (at least 1), message 1532 "Examine
  Mine" (no target; results 4, 1, 3, 0), changes nothing; when the actor has a client it sends
  (`0x0056f160`, server message 0x1b/5) the target, the success, the trap type and a band from the
  actor's Demolitions rank: 0 if DisarmDC ≤ rank + 5, 1 if ≤ + 10, 2 if ≤ + 15, 3 if ≤ + 20, else (or
  not disarmable — trigger `+0x2c4`, door `+0x2fc`, placeable `+0x280` — or DC above 35) 4. What the
  client shows for it was not traced.
- **SETTRAP** (0x1d, `0x00519e30`): params item (`+0x38`), target (`+0x3c`, may be invalid), point
  (`+0x40..`). Item gone ⇒ fail. P is the target's position, else the point; no target and a zero
  point fails; an area with 15 or more armed (`+0x2bc`) party-set (`+0x314`) mines refuses
  (`0x005089d0`). With a target: outside its use range + 0.5 m ⇒ a fresh copy, FACEOBJECT and a run to
  its use point (use range). Without one: the stand spot is P − normalize(actor − P) (a zero vector
  normalises to (1, 0, 0)), 1 m beyond P; 1.5 m or more from it ⇒ a run there with range 1.0 m (so
  the actor stops about at P), then FACEPOINT P, then the copy. First pass: animation 10140 (10060 for
  a door or placeable target), speed 1.0, 2.0 s, timer 2000 ms type 5. Second pass: the traps.2da row
  is the item's first active property's subtype; total Demolitions, + 2 with 5 or more base ranks,
  + 20 or d20, against traps.2da SetDC (at least 1). At or above it the trap is made; a miss by 10 or
  less (or any miss taking 20) makes nothing and keeps the item; a worse miss (only in combat) still
  makes it, and it goes off only when the target was a trigger, door or placeable (a trigger target
  first gets its trap flag `+0x2bc` set, then OBJECT_ENTER; a door or placeable event 26). Made: a door
  or placeable target is trapped in place (door: trap flag `+0x2e8`, type `+0x2f8`, OnTrapTriggered
  `+0x270`, DetectDC `+0x2ed` and DisarmDC `+0x2ec` as bytes, `+0x2fc` disarmable, `+0x300`, `+0x304`
  one-shot all 1; placeable: `+0x278`, `+0x290`, `+0x2e4`, `+0x276`, `+0x27c`, `+0x280`, `+0x284`,
  `+0x288` likewise) and joins the area's trap list; otherwise (no target, or a creature or trigger
  target) a new trigger, TrapFlag 1, at the actor's feet, a 4-vertex square of half-size 2.0 m around
  them (heights from the walkmesh, the actor's z where that gives 0; `0x0058d210`), faction (`+0x2b8`)
  = the actor's, CreatorId = the actor, SetByPlayerParty (`+0x314`) when the actor is the PC or of the
  party (`0x0058d700`), name strref traps.2da TrapName, OnTrapTriggered = TrapScript, TrapType = the
  row, DetectDC = rank + roll + DetectDCMod, DisarmDC = rank + roll + DisarmDCMod, detectable and
  disarmable; it joins the area and its trap list; no "found" flag is set (the party sees it because
  its faction is theirs). The item is spent only when the trap is made and only if it is in
  `GetItemRepository(1)` (stack − 1, or removed and destroyed with event 11 when the stack is 1).
  Message 1530 "Set Mine" (no target; results 1, 3, 2, 0 — a worse miss that still made the trap
  reports 2); sound set 0x13 on success, 0x18 on failure; the actor's activities 4 and 8 end (mask
  0xe to `0x004eb1b0`, which has no case for 2) and its effects 0x2f with integer 0 = 1 and 0x3f
  (likely invisibility and stealth) are removed (`0x004f5f70`) (med for the effect names).

Callers: UseSkill (`0x004fbe40`) for Demolitions queues FLAGTRAP for subskill 100, RECOVERTRAP 101,
EXAMINETRAP 102 through `AddTrapActions` (`0x004f9da0`), and any other subskill queues DISABLETRAP
itself with the same checks: `+0xe8` set, the queue cleared first for a client-driven creature whose
`+0x9f2` is below 10, the target exists, Demolitions usable (`0x005af880(stats, 1)`); disable and
recover refuse a trapped target that is not disarmable; nothing checks that the trap was found. All go
in group 0xffff with the target as the only param. `AddTrapActions` also has a SETTRAP branch (area
cap; params target before item, the reverse of what the handler reads) that no caller reaches. UseItem
(`0x004fc210`) with property 0x2e (Trap): `CanUseItem`, `+0xe8` set, the area cap not reached, the
same queue clearing, Demolitions usable ⇒ SETTRAP with the item, the target and the point; the HUD's
mine slot (`0x0060f590`) sends the user itself as the target and a zero point, so the mine lands at
the user's feet. The target block's mine actions (callbacks `0x00691900` Disable, subskill 0, and
`0x00691950` Recover, subskill 101) send player input message 7 (`0x00677b10`, major 6; skill 1, the
subskill, the target, a zero point), which the server hands to UseSkill (`0x005254c0`).

### 3.15 Door and placeable sounds (`placeableobjsnds.2da`)

The object's row of `placeableobjsnds.2da` is its `SoundAppType`: for a door, `genericdoors.2da`'s
for its GenericType (client door `+0x125`), or `doortypes.2da`'s when its `Appearance` (`+0x124`) is
non-zero (no UTD has one); for a placeable, `placeables.2da`'s for its appearance. Every play below
goes through `0x005d5e10` (misnamed `CExoSound::PlayVoiceStream`: it is the one-shot "play this
wave at a point" call; args resref, position, height added to z, prioritygroups.2da row, delay,
volume, min and max distance, the last four 0 here, so the row's defaults). All are 3D at the
object, in row 22 `Single_Shot_Positional`; a door's 1.5 m above its position, a placeable's at it.
A blank cell plays nothing. The loader `C2DAs::LoadPlaceableobjsnds` (`0x005c1980`) resolves the
columns `ArmorType`, `Locked`, `Opened`, `Closed`, `Destroyed`; `Used` is read by name. (high)

| When | Column | Where |
|---|---|---|
| A door's animation turns from closed (10022) to open 10050 / 10051: the client plays the transition 334 / 335 | `Opened` | client door update `0x00684030` |
| A door's animation turns to closed 10022 from 10050 / 10051 (transition 336 / 337), whoever closed it, `YavinHackCloseDoor` too | `Closed` | same |
| A door turns to destroyed 10072 (transition 329; the death effect, 8.2 of combat.md). Blank for every door row | `Destroyed` | same |
| USEOBJECT opens an unlocked container (3.5 step 3), the NPC path and the player's first pass alike; at the placeable, height 0 | `Opened` | `0x0057e8c0`, three calls |
| A placeable's animation leaves open 10075 (transition 313, closing) | `Closed` | client placeable update `0x006832a0` |
| A placeable's animation turns to dead 10072 (transition 306; the death effect) | `Destroyed` | same |
| A placeable's animation turns to or from on 10073 / off 10074 (transitions 314 / 315) | `Used` | same |
| Feedback message 13 "This object is locked." (the actor's client only, so the player's): the door's (1.5 m up) or placeable's | `Locked` | `FormatFeedbackMessage` `0x005fcd10` |
| A hit on a door or placeable: `ArmorType` picks weaponsounds.2da's `<armortype>0`/`1` column (random), as a creature's material does | `ArmorType` | hit sound `0x00617470` |

Feedback message 13 (`FormatFeedbackMessage` case 0xd) shows dialog.tlk 1437 "This object is
locked." in the feedback log, and besides the `Locked` sound gives the door's or placeable's client
object the text 1439 "Locked" for 5000 ms (`0x0063d2d0`: the string at `+0xe8`, the time at `+0xf0`;
`DisplayFeedBackText` and a client message call it too). The target block (`CSWGuiTargetInfo`,
`0x00685cb0` from `Refresh` `0x00689410`) shows that text in its name label while the time lasts,
over the refusal message and the hovered slot's name. (high)

The hit sound (`0x00617470`) builds the column name from a material and `rand() % 2` (`"0"` or
`"1"`; also for the `Parry` columns, and the `Clash` animation event's sound `0x0060dc50` adds the
same suffix to `Clash`). For a creature (type 5) the material is `forcefield` when `0x00616890`
says so (the first effect of type 0x6b FORCE_SHIELD in the server creature's sorted effect list
`+0x124`/`+0x128` has a nonzero integer 0, its forceshields.2da row; rules.md), `stone` when its
client object's `+0xc` or `+0x14` is set, `wood` for `+0x10`. Those three flags look like NWN's
stoneskin, petrify and barkskin: the client object constructor (`0x0063e530`) clears them and no
other write to them was found (med: searched the decompile, not every instruction), so in KOTOR they stay
clear and the material comes from the shield or else `appearancesndset.2da` `ArmorType` (by `appearance.2da`
`SoundAppType`), else the worn body armour's base item ArmorType (`+0xbc`), else `leather`: the
sound set wins over the armour. For a door (type 10) the row is `doortypes.2da`'s or
`genericdoors.2da`'s SoundAppType as above, for a placeable (9) `placeables.2da`'s, and the material
is that `placeableobjsnds.2da` row's `ArmorType` (blank: no sound). Any other type has no material.
(high)

The client picks those transitions in `0x0063e930` from the old and new animation (an old 10075
gives 313, a new 10074 314, ..., a new 10075 312, then a new 10072 306 for a placeable (type 9) or
329 for a door (type 10) last), so a dead placeable sounds `Destroyed` whatever it was doing. 312,
the opening itself, plays nothing in `0x006832a0`: the open sound is USEOBJECT's. A placeable
opened another way (PlayAnimation open) is silent. (high)

The transitions are `animations.2da` rows, played once on the object's model before the new state's own animation
loops (10075 row 310 `open`, 10076 311 `close`, 10073 308 `on`, 10074 309 `off`): 312 `close2open`, 313
`open2close`, 314 `on2off`, 315 `off2on`. For a placeable the tests run new 10075 → 312, old 10075 → 313, new 10074
→ 314, old 10074 → 315, new 10073 → 315, old 10073 → 314, the later winning. The container models have all four
open/close names (`plc_footlker`: `close2open` and `open2close` 0.67 s, `open` and `close` one-frame poses);
corpses and bags have none. (high)

A body bag left by a creature uses row 53 `Corpse` for the client's sounds instead of its
appearance's while the creature's corpse still lies there (`0x006832a0`): server `IsBodyBag` `+0x440`
set, `+0x444` clear, and `0x006057b0` finds the bag among the client area's recent corpses. That is a
ring of four creature ids at area `+0x268` (read `+0x278`, write `+0x279`) that `0x006056b0` fills
from `0x0064cc90`, the client's handling of a creature that leaves a corpse, unless the creature's
`appearance.2da` `Body_Bag` row of `bodybag.2da` is itself a `Corpse` (the Rancor's, the Krayt's).
The insert that fills the ring evicts the oldest at once, so three corpses stay: the evicted
creature fades out (`0x0063ce60` with 45000 and 1000, taken to be ms; med), its bag (client creature `+0x3dc`, set when `SpawnBodyBag`
ran, combat.md 8.4) is shown and marked `+0x444`, and sounds as its own appearance from then on;
a bag still in the ring is hidden behind its corpse (`0x0064d500`). The test reads the client
creature's `+0x3dc` for each id in the ring. (high)

What lies there is the client creature itself, in the pose its death animation left: the server
deletes its creature at DESTROY_OBJECT (combat.md 8.4) and sends the client the deletion
(`0x0056df60` writes it, `0x0064cc90` reads it): for a creature a 1, the entry's `+0x148`, the
fade delay `+0x150` and the keep flag `+0x14c`. The death's destroy (no event data) sets `+0x150` to
`appearance.2da` `FadeDelayOnDeath` when the cell has a value (`0x004ce8a0`) and `+0x14c` when it is
blank (`0x004ce9a0`); `DestroyObject` (`0x0052ff20`) instead posts its destroy with data 1 and sets
`+0x148` and `+0x150` from its own arguments, leaving `+0x14c` clear. On the client a set keep flag
(only 506 of 509 appearance rows have a blank cell; the spider droids and the terentatek have 0)
leaves the creature drawn, detaches it from its server object (`+0xe4`), and pushes it into the
ring unless its bag row is a `Corpse`; a clear one hides it through `0x0063ce60` (visible 0, fade
on, wait `+0x150` ms; immediately when `+0x148` is set). `0x0063ce60(object, visible, fade,
linger, wait)` sets the target visibility `+0x91`, fade `+0x94`, `+0x88` linger and `+0x8c` wait
ms from now (world time); the client object's update `0x0063df60` waits `+0x8c`, then moves the
alpha `+0x98` by 0.0005 a ms of frame time (2 s from whole to gone), and once there reports the
object done `+0x88` ms after the wait. The ring's eviction calls it with wait 1000 and linger
45000: the oldest body waits 1 s, fades over 2 s and is deleted 46 s after the eviction. The
evicted corpse's bag gets visible 1 without a fade. (high for the fields and calls, med for the
reading of `+0x88` as how long the faded object lingers) Ours (corpses.ctx) keeps the dead
creature's object out of the world in `w.corpses` (ring and fades as above, the body freed when its
fade ends), the scene draws it with the visual made while it lived, and a bag in the ring is not
drawn and sounds as row 53. It stays clickable, and the body is how: the pointer's scene ray
(`ProcessInput` 0x006227e0, movement.md 7.2) that hits a client creature whose `+0x3dc` names a bag
hovers the bag instead, hidden or not, without the selectable list's visibility test; a body with no
bag is refused while it is in the ring (`0x00604bc0`). The hidden bag itself (`0x0064d500`: visible
0 at once, `0x0063e220(0)`) keeps its place in the selectable list (a useable placeable), so Q/E and
the list pick find it too. Ours: `hud::pick_at` gives the bag when the pointer's ray meets
the body's triangles as the scene posed them for the frame (`scene::shape_body`: every drawn mesh of
its parts, skinned ones through their bones, kept in the corpse record) and for the bag's own box.
(high; checked by `tools/combat/corpses.sh`, `bodyhit`) A `Corpse` bag row (the rancor, the krayt) and `DestroyObject` leave nothing of
the creature, as before (the original keeps a `Corpse` creature's client body too, under the
corpse placeable; ours draws the placeable alone). A bashed door is opened (`CSWSDoor::Open`, combat.md
6.6), so it sounds `Opened`; a bashed container opens rather than dies (no sound but the hits'). No
other caller reads these columns (no unlock or trap sound comes from this table; the unlock's
sounds are the user's sound set, 3.7).

## 4. Ranges and other constants

| Constant | Value | Where | Conf. |
|---|---|---|---|
| per-object action budget | 1000 µs per AIUpdate, timed from the start of the object's AIUpdate (combat and effect updates count) | `0x00745dcc`, RunActions, `0x004fe210` | high |
| queue warnings / trims | 75, 500, 1000 nodes | RunActions | high |
| interaction range, creature target | own radius + target radius + 0.3 | `0x004ee440` | high |
| interaction range, trigger | radius + 0.5 | `0x004ee440` | high |
| interaction range, door / placeable | radius + 0.75, or 0.1 at a reachable PreciseUse node when the flag argument is 0 (doors: only when locked); a door that is the current path target: radius + path state `+0xc`; +5.0 for corpse placeables | `0x004ee440` | high |
| in-range slack | +0.1 m | `0x004f6000` | high |
| dialog start distance (approach mode 0, which the handler's own re-queued copy carries after a mode-1 approach) | walk only when farther than 10 m, centre to centre | `0x0057a470` | med |
| dialog approach (player click) | use range + 1.0 m | `0x0057a470` | med |
| party gathering for dialog | 30 m from the leader, placed within 10 m | `0x0057a470` | med |
| pick up / drop reach | 1.1 m (1.21 squared, 3-D); beyond 2 m run; under 2 m the run flag is the actor's client player object, so the controlled character runs and others walk (needs a runtime check) | `0x00517410`, `0x00513830` | med |
| get-low animation | pick up: always 10059 (compares a zeroed local to 1.0); drop: 10059 when the drop point's world z ≤ 1.0, else 10060 (needs a runtime check) | same | med |
| pick up / drop / lock / unlock animation | 1.5 s at speed 1.0 | 7, 9, 0x26, 0x27 | high |
| trap animation | 4.5 s, timer 4500 ms; range + 0.25 m (disable, recover; flag and examine + 0); set: 2.0 s, timer 2000 ms, range + 0.5 m | 0x19–0x1d | high |
| lock / unlock timer | 1500 ms | 0x26, 0x27 | high |
| wait after open / close / use approach | 0.5 s | 0x14, 0x15, 0x28 | high |
| short retry wait | 0.3 s (0.1 s with a client twin) | `0x004eb5a0` | high |
| post-jump wait | 0.75 s | 4 | med |
| follow wait | 0.25 s (0.025 s for party members, `+0xa88`) | 0x37 | high |
| random walk | home ± 7 m (whole metres), wait 3 s (15 s, no move, when AI level `+0x78` < 1), ≤ 21 retests shrinking ×0.75, back to full length below 30 %, give up under 1 m | 0x2d | high |
| flee retries / default range | 10 / 40 m | 3, 0x2c | high |
| force move default timeout | 30 s | 382, 383 | high |
| jump search radius | 20 m | 5 | high |
| creature re-path threshold | max(2.0, 0.4 × distance), 2 m on the target's destination | 1 | med |
| play-animation default length | 1000 ms when there is no client object or the model length is ≤ 0 (a client object without a model reports 1 ms) | 6 | med |
| long-animation dedupe | duration ≥ 30 s | 6 | high |
| PlaySound audience | same area, within 1000 m | 0x17 | high |
| HUD action list refresh | 300 ms, 10 groups | `0x004fe210`, `0x004f6f30` | high |

## 5. Open questions

- MOVETOPOINT flags (3.1): what the path-state fields that bits 1, 3 and 10 and param 7 are copied
  into (`+0`, `+0x198`, `+0x240`, `+0x28`) change in the planner ([movement.md](movement.md)).
- Who first queues ids 2 and 0xa (every constant `AddAction`/`AddActionToFront` push of 2 or 0xa is
  the handler re-queuing itself: CHECKMOVETOOBJECT `0x005101a0`, CHECKMOVETOPOINT `0x00510670`).
- The camera reset at the start of `RunActions` (client option byte `+0x6d == 5`).
- The creature fields named here only by use: `+0x9f2` (a state below 10 lets player commands keep
  the queue), `+0x4c0`, `+0x9f0` bit 2, `+0x8e8` (forces walking), `+0xac0`, `+0x9dc`.
- OPENLOCK sends AI event 12 UNLOCK_OBJECT and LOCK sends 13, but neither the door event handler
  (`0x0058b850`) nor the placeable's (`0x00587ba0`) has a case for them. LOCK also sends script event 28 itself (OnLock, door `+0x258`),
  but no code was found that builds script event 29, so what runs OnUnlock (`+0x278`) is unknown.
- Scheduled combat entry types 2 and 3 (no creator found); which effects clear the `+0x9f0` ability
  bits 0x80 / 0x04 / 0x02.
- Ids 0x10 and 0x24 have working handlers but no queuer; 0x1f and 0x2f neither (the routines act
  directly).
