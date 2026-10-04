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
clicked where they are drawn (`ui clicktag TAG`), keys are SDL key events (`ui key 1`). Setup may cheat: `ui spawn
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
| 3 | Disengage (BTN_CLEARALL) ends combat for the leader and clears its actions | gui.md | to check |
| 4 | Battle music: the area's MusicBattle while the party fights, its stinger when the fight ends | ambientmusic.2da (`mus_bat_*`, `mus_sbat_*` stingers); no script calls MusicBattlePlay for ordinary fights | open: no battle music plays unless a script asks |
| 5 | Camera: no change for combat | play | matches |

### The round

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 6 | One round = 3 s; attacks resolved at round start, impacts at the animation's hit times (melee `combatanimations.2da`, ranged `weapondischarge.2da` shots spread over the attacks) | combat.md 3.1-3.4 | matches (log: rounds 91 frames apart) |
| 7 | Attacks per round: 1 + effect attacks (0..2) + 1 for Flurry/Rapid Shot lines; +1 off-hand with a second weapon or a double weapon | combat.md 3.2 | matches (Carth 2 attacks with two pistols) |
| 8 | Hit/miss/critical: d20 + modifier vs defense; natural 1 misses, 20 hits; threat range by weapon, confirmation roll; the modifier and defense terms | combat.md 4, 5 | matches (rules library, `rulescheck`) |
| 9 | Damage dice, STR (melee), Weapon Specialization, crit multiplier, difficulty scaling | combat.md 6 | matches for normal difficulty; open: the difficulty option is not passed to the rules |
| 10 | Melee against a creature holding a ranged weapon +10; ranged within 5 m +10 | combat.md 4.2 | matches (log totals) |

### Player's actions and the queue

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 11 | Click a hostile: first click targets, second (or R) attacks; the leader walks into reach and fights | movement.md 7.4 | matches |
| 12 | Target block slot 1 on a hostile creature: the best rank of Critical Strike / Flurry / Power Attack (melee weapon) or Power Blast / Rapid Shot / Sniper Shot (ranged), then Attack | `0x00619950`, `0x00619b10` | open: only Attack is offered |
| 13 | Slot 2: hostile Force powers; slot 3: grenades and other items usable on the target | `0x006191f0`, `0x006198e0` | open: empty |
| 14 | In combat a chosen action is added to the queue (at most 4 pending); out of combat it replaces the queue | actions.md 3.13 "Scheduled", `AddAttackActions` | open: always replaces |
| 15 | Queue icons: the queued actions' icons (the feat's icon for a feat attack), clear-one drops the last | gui.md "Combat mode" | open: only `i_attack` |
| 16 | The leader keeps attacking its target round after round until it dies | play | matches (ours, end of round) |
| 17 | Feat attacks: to-hit/damage/self-defense penalties, extra attack, stun on Critical Strike | combat.md 4.5 | to check through the menu |
| 18 | Attacking a door or placeable (bash) | combat.md 6.6 | to check |

### Others' actions

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 19 | OnAttacked runs for every creature hit, the player's too: the leader's `k_hen_attacked01` shouts GEN_I_WAS_ATTACKED and the companions join | `0x004fece0` event 15 runs ScriptAttacked with no player check; k_ai_master 2005 | fixed: the player's OnAttacked runs, and saves keep the listen patterns (Listening, ExpressionList) without which no loaded companion heard the shout; checked at the Vulkar base (Carth and Mission join 3 s after the first shot at the leader). Open (movement): against Kandon, Carth's approach fails to plan a path from (85.4, 54.2) and he never reaches the fight |
| 20 | OnDamaged runs for everyone but the player character (the main PC, not the leader) | combat.md 6.6 step 5 | fixed |
| 21 | Creature AI by `k_ai_master` (scripts); party AI styles via SetPartyAIStyle / SetNPCAIStyle | scripts | to check |

### Death, going down, recovery

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 22 | A party member at HP < 1 is down (never dead), drops, can do nothing | combat.md 8.1-8.2 | fixed (and GetNearestCreature leaves dead and downed creatures out unless asked, 0x0054b550, so the AI stops picking them) |
| 23 | Downed members get up (HP 1, moved to a free spot within 5 m) once 5 s pass with no hostile creature perceiving any party member | `UpdatePartyDeath` `0x004b6da0` | fixed (ours waited for no hostile "in combat" in the area; QA saw Carth stay down for the rest of it): checked, Carth down, the foe killed, Carth up 151 frames later |
| 24 | The leader going down passes control to the next member who is up | combat.md 8.2 | fixed (checked: the player down, Carth leads) |
| 25 | The whole party down: slow motion, death camera, fade to black over 12 s, "Your entire party has been killed." box, then the main menu | `StartDeathCamera` `0x005f7200`, `0x00627260` | open: ours freezes the world and prints the line |
| 26 | Kill XP to the party | combat.md 8.3 | matches (log) |

### Feedback

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 27 | Combat log in Messages > Feedback: attack summary ("X succeeds/fails with attack on Y"), breakdowns, damage, kills | combat.md 10, dialog.tlk 42042, 42119, 1403, 1407 | open: nothing is written |
| 28 | Floating combat numbers (option "Floating Numbers") | gui.md HUD overlay `+0x5cb4` | open |
| 29 | HP bars of the target block and party portraits follow the damage | hud | to check |

### Options

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 30 | Auto-pause: end of round, enemy sighted, mine sighted, party member down, action menu, new target | gameloop.md 6.4 | open: the options are saved but nothing pauses |
| 31 | Difficulty: easy/normal/difficult change damage (difficultyopt, diffsettings) | combat.md 6.1, 6.7 | open: always normal |

### Items in combat

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 32 | Energy shields (items used from the self slot) absorb damage until spent or timed out | rules.md | to check |
| 33 | Grenades thrown at a target or point, area damage, saves | items | to check |
| 34 | Mines exploding when walked on in combat | items | to check |
