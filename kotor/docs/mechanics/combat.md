# Combat as the player meets it: checklist

Every combat behaviour of the original, what the evidence for it is, and where our build stands. Owned by
the combat mechanics owner; the RE pages are [re/combat.md](../re/combat.md), [re/actions.md](../re/actions.md),
[re/rules.md](../re/rules.md), [re/gameloop.md](../re/gameloop.md), [re/gui.md](../re/gui.md); the design pages
[design/rules.md](../design/rules.md), [design/vfx.md](../design/vfx.md), [design/hud.md](../design/hud.md).

Status words: **matches** (checked against the evidence through the player's input path), **fixed** (was wrong,
fixed on this branch, then checked), **open** (wrong or missing, with the reason it is not done yet).

## How it is tested

Real input only for the fight itself: the pointer is moved onto the object and clicked (`ui clickon TAG`, which
computes where the object is on the screen and sends SDL motion/button events through the HUD), HUD buttons are
clicked where they are drawn (`ui clicktag TAG`), keys are SDL key events (`ui key 1`). Setup may cheat: `ui foe
TEMPLATE DIST [SIDE]` puts a creature ahead of the leader, `ui heal` undoes the bot's god mode, `ui grantfeat N`
gives the leader a combat feat, `cam toward TAG` turns the follow camera as the player does with the keys. `ui fight`
prints the leader's combat state, its queue and the target block's slots. `--log combat` prints every attack's
d20, total and the defense it was against. The helpers are in `lib/ingame/test_combat.ctx` (also `ui damage TAG N`,
`ui sethp TAG N`, `ui giveto TAG RESREF N`, `ui aistyle TAG N`, `ui plot TAG 0|1`); the test scripts and their runner
are in `kotor/tools/combat/` (`sh kotor/tools/combat/run.sh CHECKPOINT TEST FRAMES`, the list in run.sh).

## Checklist

### Entering and leaving combat

| # | Behaviour (original) | Evidence | Status |
|---|---|---|---|
| 1 | A hostile act puts both sides in combat for 8 s after the last one; faction-mates within range that are hostile join | combat.md 3.6 | matches (engine `enter_combat`; faction pull-in not modelled, scripts' shouts do it) |
| 2 | The HUD: combat bar with Disengage and the queue, "Combat mode engaged" message for a few seconds while the leader is in combat | gui.md "Combat mode" | matches (screenshot) |
| 3 | Disengage (BTN_CLEARALL) ends combat for the leader and clears its actions | gui.md, `ClearAllCombatActions` 0x006887d0 | matches (the controls owner's `hud::disengage`: the client leaves combat mode, the leader's actions are cancelled; the server's combat state times out as usual) |
| 4 | Battle music: the area's MusicBattle while the party fights, its stinger when the fight ends | ambientmusic.2da (`mus_bat_*`, `mus_sbat_*` stingers); the engine starts it from the creatures' combat code, combat.md 3.6 "Battle music" | fixed: a hostile act stirs the creatures it concerns (and their faction-mates within 30 m) up for 10 s; with an enemy within 30 m the area's battle track starts, and when the first of those 10 s runs out it stops and a random stinger plays over the background music. Checked at uppercity with two troopers (log: `battle music on` the frame after the first attack, `music mus_bat_townint`; off 9.4 s after the last attack, `stinger mus_sbat_townint`). Open: the enemy search ignores perception (distance and reputation only); the faction pull-in range is 30 m for every creature |
| 5 | Camera: no change for combat | play | matches |

### The round

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 6 | One round = 3 s; attacks resolved at round start, impacts at the animation's hit times (melee `combatanimations.2da`, ranged `weapondischarge.2da` shots spread over the attacks) | combat.md 3.1-3.4 | matches (log: rounds 91 frames apart) |
| 7 | Attacks per round: 1 + effect attacks (0..2) + 1 for Flurry/Rapid Shot lines; +1 off-hand with a second weapon or a double weapon | combat.md 3.2 | matches (Carth 2 attacks with two pistols) |
| 8 | Hit/miss/critical: d20 + modifier vs defense; natural 1 misses, 20 hits; threat range by weapon, confirmation roll; the modifier and defense terms | combat.md 4, 5 | matches (rules library, `rulescheck`) |
| 9 | Damage dice, STR (melee), Weapon Specialization, crit multiplier, difficulty scaling | combat.md 6 | matches (the difficulty option reaches the rules, row 31) |
| 10 | Melee against a creature holding a ranged weapon +10; ranged within 5 m +10 | combat.md 4.2 | matches (log totals) |

### Player's actions and the queue

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 11 | Click a hostile: first click targets, second (or R) attacks; the leader walks into reach (melee: both personal spaces + 0.7; ranged: the weapon's maxattackrange with a clear line) and fights | movement.md 7.4, actions.md 3.13 | matches; fixed e8c7a15 for ranged (we came within 15 m whatever the weapon; now a blaster fires from 18.6 m without moving) |
| 12 | Target block slot 1 on a hostile creature: the best rank of Critical Strike / Flurry / Power Attack (melee weapon) or Power Blast / Rapid Shot / Sniper Shot (ranged), then Attack | `0x00619950`, `0x00619b10` | fixed 7713448 (checked by clicks: the block shows Critical Strike, Flurry, Power Attack, Attack with their icons; the arrows cycle; the choice is kept) |
| 13 | Slot 2: hostile Force powers; slot 3: grenades and other items usable on the target | `0x006191f0`, `0x006198e0` | slot 3 grenades: the items owner (merged); slot 2 Force powers: the Force owner |
| 14 | In combat a chosen action is added to the queue (at most 4 pending); out of combat it replaces the queue | actions.md 3.13 "Scheduled", `AddAttackActions` | fixed 7713448 (three feat attacks queued in combat, one per round) |
| 15 | Queue icons: the queued actions' icons (the feat's icon for a feat attack), clear-one drops the last | gui.md "Combat mode" | fixed 7713448 (screenshot: the round and the waiting orders with feat icons) |
| 16 | At the end of its round the leader attacks its target again while it lives and nothing else waits; when it died, the leader turns on the nearest enemy it sees within its attack range + 2 m (the HUD target follows, waiting attacks turn on it), else stands down | EndCombatRound -> `0x005b6980`, `0x004f2de0`, `0x004ffad0` | fixed c801482 (Upper City, three troopers: killed one, turned on the next and the last) |
| 17 | Feat attacks: to-hit/damage/self-defense penalties, extra attack, stun on Critical Strike | combat.md 4.5 | matches (log through the target block: Flurry two attacks at -4, the feat's numbers from the rules library, rulescheck) |
| 18 | Attacking a door or placeable (bash) | combat.md 6.6 | matches (bunk checkpoint, a relocked non-plot door: Bash in the block, defense 0, 8+7+3+3 damage over 4 rounds, the door opens and turns plot, the attacker stops) |

### Others' actions

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 19 | OnAttacked runs for every creature hit, the player's too: the leader's `k_hen_attacked01` shouts GEN_I_WAS_ATTACKED and the companions join | `0x004fece0` event 15 runs ScriptAttacked with no player check; k_ai_master 2005 | fixed: the player's OnAttacked runs, and saves keep the listen patterns (Listening, ExpressionList) without which no loaded companion heard the shout; checked at the Vulkar base (Carth and Mission join 3 s after the first shot at the leader). Open (movement): against Kandon, Carth's approach fails to plan a path from (85.4, 54.2) and he never reaches the fight |
| 20 | OnDamaged runs for everyone but the player character (the main PC, not the leader) | combat.md 6.6 step 5 | fixed |
| 21 | Creature AI by `k_ai_master` (scripts); party AI styles via SetPartyAIStyle / SetNPCAIStyle | scripts | matches for what the fights showed: targets by GN_DetermineAttackTarget (downed members left out), switches to its melee weapon at close range, a wounded trooper uses a medpac (spell 64) under half health, Vulkar droids fire their carbonite projectors; party members join on the leader's shout. The Scripts button on the character sheet opens the AI style panel (scriptselect.gui: Default attack, Grenadier, Jedi/Droid support from aiscripts.2da) and sets GetNPCAIStyle's value, saved as AIState (merged 3170b91); a grenadier companion throws grenades (row 33) |

### Death, going down, recovery

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 22 | A party member at HP < 1 is down (never dead), drops, can do nothing | combat.md 8.1-8.2 | fixed: falls with die or die1 at random, lies still (its queue cleared each frame), gets up with getupdead or getupdead1 (and GetNearestCreature leaves dead and downed creatures out unless asked, 0x0054b550, so the AI stops picking them) |
| 23 | Downed members get up (HP 1, moved to a free spot within 5 m) once 5 s pass with no hostile creature perceiving any party member | `UpdatePartyDeath` `0x004b6da0` | fixed (ours waited for no hostile "in combat" in the area; QA saw Carth stay down for the rest of it): checked, Carth down, the foe killed, Carth up 151 frames later |
| 24 | The leader going down passes control to the next member who is up | combat.md 8.2 | fixed (checked: the player down, Carth leads) |
| 25 | The whole party down: slow motion, death camera, fade to black (12 s wait, 1 s fade), "Your entire party has been killed." box, then the main menu | `StartDeathCamera` `0x005f7200`, `0x00627260`, gameloop.md 6.6 | fixed: the world slows on the original's curve (1.0 to 0.2 in 4 real seconds), the HUD goes, the box opens, the camera orbits the leader at 3 m (30 degrees per second, settling to straight down) and the fade runs on the slowed clock; OK, Escape or the end of the fade (61 s of real time, 12.9 s of world time) ends the loop, as the options menu's Exit Game does. Checked at uppercity (Carth and the player downed): screenshots in the box, orbit and fade. Open: a return to the front end (Exit Game does not have one either); the camera's geometry is read from a lossy decompile (gameloop.md 6.6) |
| 26 | Kill XP to the party | combat.md 8.3 | matches (log) |

### Feedback

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 27 | Combat log in Messages > Feedback: attack summary ("X succeeds/fails with attack on Y", red), attack / threat / defense / damage breakdowns, "X damages Y for N damage", "X killed Y: N XP"; sent for the player's side within 30 m | re/combat.md 10.1-10.3 (`FormatCombatFeedback` read case by case), dialog.tlk 42042, 42119, 42146..42150, 1403, 1407 | fixed: checked in Messages > Feedback after a fight (lines in the original's order, summary red, the rest blue; `--log combat` also prints each `log:` line). Open: the stun (0x19) and deflection (0x1a) breakdown lines, the exact tail of the damage breakdown, the numbered `feedbacktext` messages (immunity, resistance ...) |
| 28 | Floating combat numbers (option "Floating Numbers"): red damage numbers over what the leader hits and over the leader when hurt, white "miss" for the leader's melee misses, magenta "XP n" over a kill, 1.5 s (XP 3 s), fading, stacking upward | re/combat.md 10.4 (`FUN_006027c0`, label `0x0068b7c0`) | fixed: checked over the target (damage, miss, XP) and with the option off (nothing). Open: the green healing and orange "Level n" kinds are drawn but nothing posts them (`fight_log::healed`, `leveled` wait for the heal and level-up code); the label hangs at 0.9 of the box height, not on the head bone |
| 29 | HP bars of the target block and party portraits follow the damage | hud | matches (screenshots: the trooper's bar at 7/25, the leader's vitality bar at 17/22) |

### Options

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 30 | Auto-pause: end of round, enemy sighted, mine sighted, party member down, action menu, new target | gameloop.md 6.4 | matches for enemy sighted, party member down, new target (the controls owner, docs/mechanics/controls.md); end of round and action menu requests come from fight.ctx and the target block; mine sighted waits for the items owner's mines. RE (gameloop.md 6.4): the reasons are 5 end of round and 8 new target, new target only on the cycling keys in combat |
| 31 | Difficulty: easy/normal/difficult change damage (difficultyopt, diffsettings) | combat.md 6.1, 6.7 | fixed: the Difficulty Level option reaches `rules.settings.difficulty` when the game starts (from the settings file) and every frame once the in-game options panel has been opened, so changing it there takes effect at once. Checked with `--log combat` on the same seeded fight (trooper vs the player): the first hit rolls 7 on normal and takes 7; on difficult it takes 10 (x1.5); on easy the roll is 3 (diffsettings MaxNPCDamagePercent 50: roll minus 50 % of the die maximum) and the player takes 1 (3 x 0.5, truncated), so easy is both scalings in a row, as combat.md 6.1 and 6.7 describe them. Changed in game (options, Gameplay, Difficulty arrow) from normal to easy gives the same 3 and 1. Open (combat.md 12): whether the exe applies both scalings on easy (the server difficulty value for diffsettings is not established). |

### Items in combat

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 32 | Energy shields (items used from the self slot) absorb damage until spent or timed out | rules.md 1.13, `OnApplyForceShield` 0x004df540 | fixed (sub-agent, merged 3f13a64): bands absorb blaster and ion damage until their points run out (20, 7, 3, then the shield breaks and 4 gets through), a missed bolt on a shield is result 10, a new shield replaces the old; open: the shield aura of rows 0-14 is an engine-coded effect lib/vfx does not draw |
| 33 | Grenades thrown at a target or point, area damage, saves | items | grenades in the block's third slot: the items owner; a fighting order (queues in combat). Thrown by AI: Trask as grenadier throws frag grenades (spell 87) at two troopers on the Endar Spire and the blasts kill both (052d337 made GetFirst/NextObjectInShape walk ascending x, which GN_FindGrenadeTarget depends on) |
| 34 | Mines exploding when walked on in combat | items | the items/skills owner (traps and mines sub-agent); hooks agreed: MINE_SIGHTED auto-pause, damage as rules effects |

## QA reports

| Report | Cause | Status |
|---|---|---|
| A party member at 0 HP stays down (red X) for the rest of the area | we waited for no hostile in the area to be "in combat"; the original gets them up 5 s after no hostile sees the party (`UpdatePartyDeath`) | fixed (row 23) |
| Fights are very slow (Kandon Ark, 88 HP: ~8,000 frames with three fighters) | Carth never fought: no loaded companion listened to the leader's GEN_I_WAS_ATTACKED shout (listen patterns were not saved), the leader's own OnAttacked never ran, and the AI could pick downed members; the rest is the replay's player never levelling up (22 HP, attack +3 against Kandon's defense 23: 2 hits in 45) | fixed (rows 19-23): from the garage checkpoint with `44_kandon.txt` the Kandon fight now ends 3,900 frames after his conversation, Carth and Mission fighting throughout (48 and 47 attack rounds) |
| Companions sit idle in some fights | as above; also a pathing failure (Carth could not plan a way to Kandon), fixed by the controls owner | fixed |
