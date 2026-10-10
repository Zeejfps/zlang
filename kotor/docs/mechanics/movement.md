# Movement and pathfinding in play: the original's behaviour and where we stand

How creatures plan and walk their paths (scripted moves, AI approaches, followers, random walkers, jumps),
one line per behaviour, with the evidence and our status. The status is **matches** (checked by a run, named
in the last column), **fixed** (made to match by the 2026-10 pathfinding audit, [audit/pathfinding.md](../audit/pathfinding.md)),
**ours** (a deliberate difference, with the reason), or **open** (with the reason and what a fix needs).
Evidence is the RE notes ([movement.md](../re/movement.md) 3, 4, 6; [actions.md](../re/actions.md) 3.1-3.3) and the
decompiled functions named in the lines (`python kotor/tools/py/rex.py fn ADDR`).

The code: [lib/engine/movement.ctx](../../lib/engine/movement.ctx) (MOVETOPOINT's walk, the speeds, the follower's
pace, safe spots), [lib/engine/paths.ctx](../../lib/engine/paths.ctx) (the planner), [lib/engine/walkmap.ctx](../../lib/engine/walkmap.ctx)
(the walkmesh queries), [lib/engine/trail.ctx](../../lib/engine/trail.ctx) (the leader's trail), [lib/engine/actions.ctx](../../lib/engine/actions.ctx)
(jumps, FOLLOW, RANDOMWALK), [lib/scene/control.ctx](../../lib/scene/control.ctx) (the leader under the keys).

## How these were tested

- `sh kotor/tools/gait/run.sh` (docs/testing.md) from a checkpoint, and the same `--log gait` from a fresh module
  (`kotor.exe --module tar_m02aa --no-render --frames 900 --log gait,actions`): every walker's speed, cycle rate and
  place each frame; `python kotor/tools/py/gait_check.py LOG` tabulates it. A checkpoint carries its creatures'
  rows as the build that made it saved them (before the audit: none, so row 7), so a speed row is tried on a module.
- `ui jump TAG` (lib/ingame/script.ctx): the leader JumpToObjects the tagged object; `ui pos` and `ui where TAG` print
  where both stand.
- The stealth scenarios (`sh kotor/tools/stealth/check.sh`) for the hider's pace; the Endar Spire replay and the
  apartment checkpoint's for the story.

## 1. Speeds

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A creature's row is the save's `MovementRate`, else the blueprint's `WalkRate`; row 7 resolves through appearance.2da MOVERATE (no match: row 0); the resolved row is saved | `ReadStatsFromGff` `0x005afce0`, `SetMovementRate` `0x005a5680`, `SaveStats` `0x005b1b90` | fixed (`tmpl::set_rate`): ours took the appearance's row for everyone | fresh tar_m02aa: Larrim (row 6) walks 2.5/1.7 faster than before |
| A companion is on row 0, PC_Movement (walk 3.2, run 5.4), whatever its blueprint | `AddAvailableNPCByObject` `0x00564300` | fixed: ours left companions at their appearance's NORM (walk 1.7) | |
| GetCreatureMovmentType returns the resolved row | `0x0053efa0` | fixed | |
| Walk = clamp(factor, 0.125, 1.5) × WALKRATE, 0 at 0.1 m/s or less; run = clamp × RUNRATE, at least 1 m/s | `GetWalkRate` `0x004f1b20`, `GetRunRate` `0x004f1be0` | matches for the factor (clamped in lib/rules); open (low): the 0.1 m/s walk floor and the 1 m/s run floor | |
| In stealth the walk rate is the appearance's DriveAnimWalk (2 when 0), not scaled; the hidden leader is capped at it too | `0x004f1b20`, `GetMaxSpeed` `0x00679510` | fixed (`movement::walk_pace`): ours walked hiders at the walk rate, 3.2 m/s for the party | stealth `key_unequip` (3.4 m in 2 s), `walk_past` |
| Acceleration over 1 s, braking with √ of the remaining path over the last 0.5 s of it; the factor carries over between moves | `GetSpeedFactor` `0x00512f10` | matches | |
| The factor starts at 1.0 when the creature is made, so its first move starts at full speed | constructor `0x004cfcb0` | fixed: ours started at 0.1 | |
| The braking zone's first leg is measured against the waypoint at z = 0, so on floors far from z = 0 nobody brakes | movement.md 3.3 (med, needs a runtime check) | open (low): ours measures in 2D | |
| A party follower's pace (catch-up, the leader's speed, 0.9 × walk to a standing leader; × 0.9 / 1.2 / 1.5 by distance; smoothed speed picks the cycle) | `UpdateFollowLeader` `0x0051c360` | matches (movement.md 6.2 "Ours") | gait `taris_street`, `endar_corridor` |
| A script's forced move to an object is an ordinary move (braking, its own run/walk) | `AIActionMoveToPoint` `0x0051f4f0` | fixed: ours walked it at the follower's pace (the follow mark shared param 5 with the force flag): Taris' ambient walkers ran at up to 8.1 m/s | fresh tar_m02aa: woman02, janitor, twilek walk at 1.7 m/s, feet on the ground |
| Back-pedalling: a short single-leg walk (< 2 m) behind the creature plays walk-backwards (10003) instead of turning | `StepAlongPath` `0x00516630` | open (low): ours turns | |
| NPCs face their walking direction at once | `UpdateMovement` `0x0051d9c0` | matches | |

## 2. Moves: who may, arrival, failure

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| MOVETOPOINT fails when the AI state mask's can-move bit is clear (stun, paralysis, sleep, Entangle, creaturespeed's Immobile row) | `0x0051f4f0` step 5, rules.md AI state mask | fixed (`movement::can_move`): an entangled enemy walked up to its target, Immobile creatures walked scripted moves | |
| ActionMoveToObject: range = max(fRange, use range), the destination a door's or placeable's use point; a creature target is reached within range + 0.1 with a clear line of sight | routine 22 `0x0053fb00`, `GetIsInUseRange` `0x004f6000` | open (low): ours walks to the object's centre and stops at fRange from it (1.0 against the original's ~1.2 for a creature) | |
| Within range but without a line of sight: the range is taken as 0, so the creature walks onto the point | `0x0051f4f0` step 2 | open (low) | |
| Within 0.1 m: set exactly on the point when safe | step 6 | open (low): ours stops where it is | |
| A planner failure ends the action at once | step 7 | ours: six tries, a frame apart (`GIVE_UP`) | |
| A step blocked by a wall or a placeable ends the move (status 1); after six blocked steps in a row (only reachable through detours) the move gives up | `StepAlongPath` step 4 | ours: the move plans again from where it stands, up to six times in a row | |
| A forced move's timeout jumps: JUMPTOOBJECT to its target (nearest safe spot within 20 m), else JUMPTOPOINT with a 1 m search (the point only if free; else no jump) | `0x004edba0`, actions.md 3.1 step 3 | fixed: ours set the creature on the target's own position | |
| A move to a trap trigger stops 0.5 m outside its nearest edge | `0x0051f4f0` step 4, `0x0058c8a0` | open (low) | |

## 3. Planning

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Straight line first, then the PTH graph between the nearest reachable path points, else a local grid; links crossed by a placeable's or a static door's walkmesh are dropped | `PlotAreaPath` `0x004c3260`, `PlotPathPointRoute` `0x004c2200`, `GetPathPointSuccessors` `0x004bdb00` | matches in kind (A* over the PTH, `paths::route`); a static door is not dropped from the graph (open, low: its walkmesh still stops the walk) | |
| Stop short: the planner aims range − 0.001 short of the goal | step 2 | matches (the walk stops `range` short) | |
| No path: the farthest clear point on the straight line | step 6 | matches | |
| Every walk test sweeps the creature's PERSPACE circle against the walls (`CheckSegmentClearance`) | `TestWalkLine` `0x004bcb70` | **open (medium)**: ours tests the centre line only (`walkmap::walk_segment`), so creatures cut corners and door frames with half their body; needs a clearance test against non-walkable edges, then the planner's samples and the PTH legs re-checked | |
| String pulling in three passes, segments ≥ 5 m cut at 1 m, then corner rounding (cut where the turn is sharper than cos 0.9) | `FinishPathPointRoute` `0x004c17a0`, `RoundPathCorners` `0x004bfe20` | open (low): ours pulls strings once and turns sharply at the corners | |
| A creature at AI level 0 gets no planner (the request fails) | step 5 | open (low) | |
| Heights: z from the face under each point; rooms crossed through perimeter edges | movement.md 3.5 | ours: the highest floor within 0.6 m up and 1.5 m down (`STEP_UP`, `STEP_DOWN`), seams bridged by a short step | |

## 4. Creatures in the way

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A creature's circle (both CREPERSPACEs + 0.01) blocks a walk; dead and dying ones do not | `TestSegmentAgainstCreatures` `0x004bc590`, `CheckStepCollision` `0x00512fd0` | **open (high)**: ours lets creatures walk through each other (Carth and a Duros follower 0.17 m apart in the `taris_street` gait run) | gait `taris_street` |
| A neutral, idle, non-party creature in the way is pushed aside (to the nearest safe spot) | `PushCreatureAside` `0x004f6390`, `CanPushCreature` `0x004f62a0` | open (high, with the above) | |
| Otherwise a detour round the blocker (side coordinated between two creatures), `k_def_pathfail01` for a hostile blocker, feedback 47859 for the player | `ResolveBlockingCreature` `0x005d0840` | open (high, with the above) | |
| A closed door's walkmesh in the way sends PATH_BLOCKED (OnBlocked, which opens it) on every blocked step and ends the move | `CheckStepCollision` | ours: told at most once a second; a move with a timeout waits for the door instead of ending | Dantooine replay (Bastila's legs) |
| A trigger the move targets is clicked on arrival; an area-transition door in use range is clicked when open, else PATH_BLOCKED | `UpdateMovement` step 12 | matches in kind (lib/engine/doors.ctx) | |

## 5. Jumps and safe spots

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| JumpToLocation / JumpToObject land on the nearest safe spot within 20 m (the point if free, else square rings PERSPACE apart, first the corner (−1, −1)); none: the jump fails | `0x0051d600`, `0x0051d110`, `FindNearestSafePosition` `0x004be860` | fixed (`movement::safe_spot`); ours: walls within PERSPACE are not tested | `ui jump carth` from `uppercity`: the leader lands 1.4 m from Carth (was on him) |
| JumpToObject a door: from its approach side, twice CREPERSPACE out; a waypoint: its facing too | `0x0051d110` | fixed for the door (its nearer side, `doors::use_point`); facing as before (the target's) | |

## 6. Random walk and following

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| ActionRandomWalk: home = where the walker stood; each leg home ± (−7..7) m, walked, 3 s wait, the rest of the queue dropped; far from the player (AI level 0) a 15 s wait and no walk | `AIActionRandomWalk` `0x00515ac0` | fixed: ours aimed each leg from wherever the walker was, so walkers drifted (the Undercity's rakghouls up to 130 m in five minutes; now within 10 m) | fresh tar_m04aa, 9000 frames |
| FOLLOWLEADER: the trail, the formation point, the pace | movement.md 6 | matches in kind (movement.md 6.2 "Ours"); the order comes after a second of an idle queue (`FOLLOW_IDLE_MS`, ours) | combat `straggle1`, `straggle2`, `companions` |
| ActionForceFollowObject: the follow point is the leader's position plus the offset; a new move when that point moved by the party table's PrimaryRange (5 m); waits 0.25 s (0.025 s for party members) | FOLLOW `0x005132e0` | open (low): ours moves when farther than max(fDist, 1) + 0.5, after a 0.25 s wait | |
