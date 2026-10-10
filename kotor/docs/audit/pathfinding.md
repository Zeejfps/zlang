# Audit: pathfinding and movement (2026-10)

Ours against the original for how creatures plan and walk paths: scripted moves, AI approaches, followers,
random walkers, jumps, doors in the way, speeds. The line-by-line comparison is
[mechanics/movement.md](../mechanics/movement.md); the original's behaviour is [re/movement.md](../re/movement.md) 3-6
and [re/actions.md](../re/actions.md) 3.1-3.3. Severity is how much a player would notice.

## Fixed

| Severity | What a player saw | Fix | Commit |
|---|---|---|---|
| high | Taris' ambient walkers (and every script's ActionForceMoveToObject) ran at up to 8.1 m/s with sliding feet, never braking: the follower's mark shared MOVETOPOINT's param 5 with the force flag | the follower's mark is param 6 | efdf8a0 |
| high | Random walkers drifted away: each leg was aimed from wherever the walker stood, so the Undercity's rakghouls wandered up to 130 m in five minutes | legs aimed at the home point the routine stored, ±7 m, 3 s waits, the queue dropped, 15 s and no walk far from the player (`AIActionRandomWalk` 0x00515ac0) | 040dfca |
| medium | A companion told to JumpToObject the player stood inside him; a jump to a door stood in its walkmesh; a timed-out forced move put the mover on its target | jumps land on the nearest safe spot within 20 m (`FindNearestSafePosition` 0x004be860), a door's from its nearer side; none, and the jump fails | f1727e1 |
| medium | Speeds from the wrong creaturespeed row: blueprints that name their own (Immobile crew and victims, Slow Jawas, Fast gizka and droids, Larrim's VFAST) moved at their appearance's; companions walked at NORM's 1.7 m/s instead of PC_Movement's 3.2 | `MovementRate`, else `WalkRate`, resolved and saved; companions on row 0 (`AddAvailableNPCByObject` 0x00564300) | 07ef92e |
| medium | Hiders walked at 3.2 m/s (the party's walk rate) instead of their appearance's DriveAnimWalk, 1.6-1.9 m/s | `movement::walk_pace` for the keys, scripted moves and followers | dbaaae6 |
| medium | An entangled enemy (adhesive grenade) walked up to its target; an Immobile creature walked scripted moves | MOVETOPOINT fails when the can-move bit is clear | 45f6dea |
| low | Every creature's first move after loading ramped up over a second | the speed factor starts at 1.0 (0x004cfcb0) | acf63dd |

All verified headless: the fresh-module gait logs (`--module tar_m02aa`, `tar_m04aa`), `ui jump carth` from
`uppercity`, the stealth, combat (companions, engage, queue, straggle), autotarget (paused click), camcheck
(17/17) and gait checks, the Endar Spire replay (0 faults, reaches tar_m02af, no `companion idle`) and the
apartment checkpoint's replay (to the Undercity, the same 26-27 instruction-budget faults in k_ai_master as
before the audit).

Note for the Endar Spire replay: with the new speeds the fights' timing moves and Trask offers his medpac
tutorial ("How do I use a medpac?") after the welding droid's fight, which took one of the replay's queued
replies, so Carth's apartment conversation ended without k_ptar_addcarth and the replay stayed in the
apartment. `kotor/tools/playthrough/10_endar_spire.txt` queues one more reply for it; the replay reaches
tar_m02aa at frame 40,172 again (0 faults). The checkpoints after `bunk` should be made again
(`kotor/tools/checkpoints/make.sh`) so that their creatures carry the speed rows.

## Open, by severity

| Severity | Difference | What a fix needs |
|---|---|---|
| high | Creatures walk through each other: no creature circle in the walk tests, no pushing aside, no detours, no `k_def_pathfail01` for a hostile in the way (followers overlap: Carth and a Duros 0.17 m apart in the `taris_street` gait run; attackers converge on one spot) | `TestSegmentAgainstCreatures` (both CREPERSPACEs + 0.01, skipping dead and dying ones, the mover and its target) in the step test; `CanPushCreature`/`PushCreatureAside` for idle neutrals; `ResolveBlockingCreature`'s arc detour with the side coordinated between two movers; the 6-blocked-steps give-up. Big: every scripted scene and fight changes, so it wants the story replays rerun and likely the checkpoints remade. Start with blocking + detour for MOVETOPOINT only, leave the followers' trail alone |
| medium | No PERSPACE clearance against walls: creatures cut corners and door frames with half their body | a clearance test against the non-walkable edges of the faces near the segment (`CheckSegmentClearance` 0x005972b0, not yet read: needs RE first), used by `walkmap::step_to` and the planner; then recheck the narrow places (the Endar Spire's doors, the Ebon Hawk) |
| low | ActionMoveToObject goes to the object's centre and stops at fRange (the original: max(fRange, use range), a door's or placeable's use point, a creature reached at range + 0.1 with a clear line) | in `routines/actions.ctx` `move_to_object`: the use point and range from `doors::use_point` (with CREPERSPACE for creatures) |
| low | No corner rounding (cos 0.9 cut), no 1 m subdivision | `RoundPathCorners` after the string pulling in `paths::route` |
| low | No walking backwards on short moves behind the creature (10003) | `StepAlongPath` step 5 in `move_to_point` |
| low | Walk floor (0 at 0.1 m/s), run floor (1 m/s); the braking zone measured against z = 0 (never brakes high up) | `walk_pace` and the run rate; the braking quirk needs a runtime check first |
| low | MOVETOPOINT within range without a line of sight walks onto the point; within 0.1 m it is set on it; a trap trigger as target stops 0.5 m outside | `move_to_point` |
| low | ActionForceFollowObject's follow point and PrimaryRange (5 m) re-move rule | `actions::follow` (not FOLLOWLEADER) |
| low | Static doors are not dropped from the PTH graph | `paths::route`'s edge test: count a static door's walkmesh |

Deliberate (ours, kept): FOLLOWLEADER queued after a second of an idle queue (`FOLLOW_IDLE_MS`); a moved-on
blocked step plans again (up to six times) where the original ends the move; a closed door says PATH_BLOCKED
at most once a second and a move with a timeout waits for it; the planner's six tries; heights by STEP_UP and
STEP_DOWN with seams bridged.
