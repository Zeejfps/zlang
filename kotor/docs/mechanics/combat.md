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
d20, total and the defense it was against. The helpers are in `lib/ingame/test_combat.ctx`; test scripts in
`kotor/tools/combat/`.

## Checklist

### Entering and leaving combat

| # | Behaviour (original) | Evidence | Status |
|---|---|---|---|
| 1 | A hostile act puts both sides in combat for 8 s after the last one; faction-mates within range that are hostile join | combat.md 3.6 | matches (engine `enter_combat`; faction pull-in not modelled, scripts' shouts do it) |
| 2 | The HUD: combat bar with Disengage and the queue, "Combat mode engaged" message for a few seconds while the leader is in combat | gui.md "Combat mode" | matches (screenshot) |
| 3 | Disengage (BTN_CLEARALL) ends combat for the leader and clears its actions | gui.md, `ClearAllCombatActions` 0x006887d0 | matches (the controls owner's `hud::disengage`: the client leaves combat mode, the leader's actions are cancelled; the server's combat state times out as usual) |
| 4 | Battle music: the area's MusicBattle while the party fights, its stinger when the fight ends | ambientmusic.2da (`mus_bat_*`, `mus_sbat_*` stingers); no script calls MusicBattlePlay for ordinary fights | open: no battle music plays unless a script asks |
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
| 11 | Click a hostile: first click targets, second (or R) attacks; the leader walks into reach and fights | movement.md 7.4 | matches |
| 12 | Target block slot 1 on a hostile creature: the best rank of Critical Strike / Flurry / Power Attack (melee weapon) or Power Blast / Rapid Shot / Sniper Shot (ranged), then Attack | `0x00619950`, `0x00619b10` | fixed 7713448 (checked by clicks: the block shows Critical Strike, Flurry, Power Attack, Attack with their icons; the arrows cycle; the choice is kept) |
| 13 | Slot 2: hostile Force powers; slot 3: grenades and other items usable on the target | `0x006191f0`, `0x006198e0` | slot 3 grenades: the items owner (merged); slot 2 Force powers: the Force owner |
| 14 | In combat a chosen action is added to the queue (at most 4 pending); out of combat it replaces the queue | actions.md 3.13 "Scheduled", `AddAttackActions` | fixed 7713448 (three feat attacks queued in combat, one per round) |
| 15 | Queue icons: the queued actions' icons (the feat's icon for a feat attack), clear-one drops the last | gui.md "Combat mode" | fixed 7713448 (screenshot: the round and the waiting orders with feat icons) |
| 16 | The leader keeps attacking its target round after round until it dies | play | matches (ours, end of round) |
| 17 | Feat attacks: to-hit/damage/self-defense penalties, extra attack, stun on Critical Strike | combat.md 4.5 | matches (log through the target block: Flurry two attacks at -4, the feat's numbers from the rules library, rulescheck) |
| 18 | Attacking a door or placeable (bash) | combat.md 6.6 | matches (bunk checkpoint, a relocked non-plot door: Bash in the block, defense 0, 8+7+3+3 damage over 4 rounds, the door opens and turns plot, the attacker stops) |

### Others' actions

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 19 | OnAttacked runs for every creature hit, the player's too: the leader's `k_hen_attacked01` shouts GEN_I_WAS_ATTACKED and the companions join | `0x004fece0` event 15 runs ScriptAttacked with no player check; k_ai_master 2005 | fixed: the player's OnAttacked runs, and saves keep the listen patterns (Listening, ExpressionList) without which no loaded companion heard the shout; checked at the Vulkar base (Carth and Mission join 3 s after the first shot at the leader). Open (movement): against Kandon, Carth's approach fails to plan a path from (85.4, 54.2) and he never reaches the fight |
| 20 | OnDamaged runs for everyone but the player character (the main PC, not the leader) | combat.md 6.6 step 5 | fixed |
| 21 | Creature AI by `k_ai_master` (scripts); party AI styles via SetPartyAIStyle / SetNPCAIStyle | scripts | to check |

### Death, going down, recovery

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 22 | A party member at HP < 1 is down (never dead), drops, can do nothing | combat.md 8.1-8.2 | fixed: falls with die or die1 at random, lies still (its queue cleared each frame), gets up with getupdead or getupdead1 (and GetNearestCreature leaves dead and downed creatures out unless asked, 0x0054b550, so the AI stops picking them) |
| 23 | Downed members get up (HP 1, moved to a free spot within 5 m) once 5 s pass with no hostile creature perceiving any party member | `UpdatePartyDeath` `0x004b6da0` | fixed (ours waited for no hostile "in combat" in the area; QA saw Carth stay down for the rest of it): checked, Carth down, the foe killed, Carth up 151 frames later |
| 24 | The leader going down passes control to the next member who is up | combat.md 8.2 | fixed (checked: the player down, Carth leads) |
| 25 | The whole party down: slow motion, death camera, fade to black over 12 s, "Your entire party has been killed." box, then the main menu | `StartDeathCamera` `0x005f7200`, `0x00627260` | open: ours freezes the world and prints the line |
| 26 | Kill XP to the party | combat.md 8.3 | matches (log) |

### Feedback

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 27 | Combat log in Messages > Feedback: attack summary ("X succeeds/fails with attack on Y"), breakdowns, damage, kills | combat.md 10, dialog.tlk 42042, 42119, 1403, 1407 | open: nothing is written |
| 28 | Floating combat numbers (option "Floating Numbers") | gui.md HUD overlay `+0x5cb4` | open |
| 29 | HP bars of the target block and party portraits follow the damage | hud | matches (screenshots: the trooper's bar at 7/25, the leader's vitality bar at 17/22) |

### Options

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 30 | Auto-pause: end of round, enemy sighted, mine sighted, party member down, action menu, new target | gameloop.md 6.4 | matches for enemy sighted, party member down, new target (the controls owner, docs/mechanics/controls.md); end of round and action menu requests come from fight.ctx and the target block; mine sighted waits for the items owner's mines. RE (gameloop.md 6.4): the reasons are 5 end of round and 8 new target, new target only on the cycling keys in combat |
| 31 | Difficulty: easy/normal/difficult change damage (difficultyopt, diffsettings) | combat.md 6.1, 6.7 | fixed: the Difficulty Level option reaches `rules.settings.difficulty` when the game starts (from the settings file) and every frame once the in-game options panel has been opened, so changing it there takes effect at once. Checked with `--log combat` on the same seeded fight (trooper vs the player): the first hit rolls 7 on normal and takes 7; on difficult it takes 10 (x1.5); on easy the roll is 3 (diffsettings MaxNPCDamagePercent 50: roll minus 50 % of the die maximum) and the player takes 1 (3 x 0.5, truncated), so easy is both scalings in a row, as combat.md 6.1 and 6.7 describe them. Changed in game (options, Gameplay, Difficulty arrow) from normal to easy gives the same 3 and 1. Open (combat.md 12): whether the exe applies both scalings on easy (the server difficulty value for diffsettings is not established). |

### Items in combat

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 32 | Energy shields (items used from the self slot) absorb damage until spent or timed out | rules.md | to check |
| 33 | Grenades thrown at a target or point, area damage, saves | items | to check |
| 34 | Mines exploding when walked on in combat | items | to check |
