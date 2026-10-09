# The rules library (`lib/rules`)

What the original engine computes for the d20 rules, as a library that knows nothing of the world:
given creature and item data it derives stats, applies and expires effects, rolls attacks, damage
and saves, prices and resists Force powers, awards XP and levels characters up. The engine
(`lib/engine`, its object model and action queues) embeds the library's values in its objects,
calls it, and applies the results. The sources are our reverse-engineering pages
[combat.md](../re/combat.md), [rules.md](../re/rules.md) and
[party-items-saves.md](../re/party-items-saves.md); every function cites the section it follows.

```
lib/rules/            namespace rules (nested: fx, abil, cls, skill, race, save, dmg, imm, slot, feat, dur, sub, ev, cat)
tools/rulescheck/     the corpus and worked-example checks
```

A program that uses it adds `lib/base`, `lib/formats`, `lib/res` and `lib/rules`.

## Boundaries

| Rules library | Engine |
|---|---|
| Creature stats, effects on a creature, equipment as effects | Objects, ids, positions, scripts, action queues, the world clock |
| Attack counts, attack rolls, defense, damage numbers, saves | The combat round's timing and animations, applying hit points, death and its consequences |
| Force point costs, DCs, resistance, who may cast | The cast action's phases, projectiles, impact scripts, area effects |
| XP awards, level-up legality and application | Who gets XP, the GUI, the party table, saves |
| Skill checks (the numbers) | Which objects are locked or trapped |

The library never calls back. Everything it wants done to the world comes out as a result struct
or an `Event` in a buffer the caller owns.

## Data the library owns (all plain values)

Everything is a fixed-size value: no pointers, no allocator state. `let mut c: rules::Creature`
is zero-initialised and can be copied (the equip panel's preview copies the creature, equips,
recomputes and compares). Numbers are `i32` unless they are object ids or bit masks (`u32`).
Object ids are the engine's; `rules::OBJECT_INVALID` is 0x7f000000.

| Type | What | Size |
|---|---|---|
| `Tables` | the 2DAs: typed rows for classes, feats, skills, spells, base items, appearance sizes; the raw item-property, XP and effect tables; `Tables.settings` (difficulty, day length, auto-level) | one per game, by `*Tables` |
| `Creature` | the rules state of one creature (below) | ~30 KB |
| `Item` | a UTI: base item, stack, flags, up to 40 `Prop`s | ~700 B |
| `Effect` | one effect: kind, duration kind, expiry, creator, spell id, `ints[8]`, `floats[4]`, `objects[4]`, `handles[3]` | ~130 B |
| `EffectGroup` | the leaves of an `EffectLinkEffects`: up to 8 `Effect`s sharing one id | ~1 KB |
| `Rng` | the C runtime's `rand()`: one `u32` of state | 4 B |
| `Time` | world time as the effects use it: calendar day and ms of day | 8 B |
| `Env` | per-call facts: `tables`, `now`, the creature's current `hp` | small |
| `Events` | the output buffer: up to 48 `Event { kind, a, b, who }` | ~800 B |

`Creature` holds the template numbers (race, subrace, gender, appearance, base abilities, natural
AC, base HP and FP, save bonuses, good-evil, challenge rating), the classes (up to 3 slots with a
level each), the feat and known-power bit sets, skill ranks, XP, the level-up history of a player
character, 15 equipment cells (`Equipped { used, id, item }`), the effect list (`nfx`, `fx[96]`,
kept in the engine's order: by type, then application order), the current Force points and the
temporary pools, the engine-set flags (`is_pc`, `pc_rules`, `plot`, `min1hp`, `party`, `down`)
and the derived `Stats` (`recompute` rebuilds them).

**What the engine keeps itself:** the creature's current and temporary hit points live on the
engine's object header (doors and placeables have hit points too). The library gives the maximum
(`stats.max_hp`) and returns amounts to add or subtract as events. Temporary hit points are the
exception because they are per-effect state: `Creature.temp_hp` mirrors the sum of the
`TEMPORARY_HITPOINTS` effects, and damage is absorbed by those effects before the engine sees it.

## Loading

```
let mut tables: rules::Tables
try rules::load_tables{ &fs, rm, heap = &heap, out = &tables }      // once; free_tables gives it back
tables.settings.difficulty = 1                                       // the options menu changes these

let mut c: rules::Creature
rules::read_creature{ tables = &tables, doc = &doc, s = gff::ROOT, out = &c }   // a UTC, a saved creature, Mod_PlayerList's entry
let mut it: rules::Item
rules::read_item{ tables = &tables, doc = &doc, s = gff::ROOT, out = &it }       // a UTI or a saved item struct
```

`read_creature` takes the struct index so a GIT's "Creature List" element or the player's save
entry works as well as a blueprint root. It reads abilities, classes and levels, known powers,
feats, skill ranks, special abilities, save bonuses, alignment, challenge rating, XP, the level
history (saves), flags (`IsPC`, `Plot`, `Min1HP`) and the file's current HP and FP (`loaded_hp`,
`fp`), then recomputes. It does not touch items: the engine reads `Equip_ItemList` and
`ItemList`, makes `Item`s with `read_item` and hands the equipped ones to `equip`.

## Calling the library

Every state-changing call takes `env: Env`, a `mut c: Creature`, and a `mut ev: Events`; calls that
roll take `mut rng: Rng`. The caller clears the event buffer (`rules::clear_events`) and drains it
after the call.

```
let env = rules::Env{ tables = &tables, now = world_time, hp = obj.hp }
rules::clear_events{ ev = &events }
let res = rules::apply_group{ env, c = &c, g = group, rng = &rng, ev = &events }
// res.kept / res.refused / res.feedback; then walk events.items[0..events.len]
```

### Effects

- Script constructors are `rules::fx::make_*` (`make_haste`, `make_ac_increase`, `make_damage`, ...).
  They return an `Effect` with the script defaults (magical, instant, no creator, spell -1).
  `fx::set_timing`, `set_creator`, `set_subtype` adjust one; `fx::make_group` wraps it and
  `fx::link_groups{ child, parent }` is `EffectLinkEffects`. `fx::assign_id{ &ids, g = &group }`
  stamps one fresh id on all leaves (call it when the script creates or links an effect; `ids` is
  a `rules::EffectIds` counter in the world). `fx::set_group_timing` / `set_group_creator` are what
  `ApplyEffectToObject` does to the leaves (duration kind, seconds, creator, spell id).
- `apply_effect{ env, c, e, rng, ev } -> ApplyResult` and `apply_group` apply with the engine's
  rules: immunity (the gameeffects.2da rows plus the per-state feats) and the plot refusals, the
  per-kind handler (heal and damage are instant, ability/AC/attack/save/skill modifiers are kept,
  temporary hit points and Force points are added to their pools, poison rolls its Fortitude
  save), the expiry time of a temporary effect, insertion in type order. A group whose real
  (non-visual) leaves were all turned away takes its already-applied visuals with it.
- `remove_effect_id`, `remove_effects_by_creator` (an item's effects when it is unequipped),
  `clear_effects` (ClearAllEffects: everything but the equipped and innate ones).
- `update_effects{ env, c, rng, ev }` is `UpdateEffectList`: call it whenever the engine updates
  the creature (normally every frame). It runs regeneration and poison ticks and expires
  temporary effects whose time has passed.
- Getters (all read-only, `*Creature`): `effect_bonus` (attack, saves, abilities, skills with the
  same-source rule and caps), `has_immunity`, `ac_effects`, `active_state`, `can_move`,
  `can_attack`, `is_debilitated`. Mitigation: `mitigate_damage` (immunity, then resistance, then
  reduction), `absorb_temp_hp`.

### Equipment (`equip.ctx`, `itemprops.ctx`)

`rules::equip` and `unequip` are `RunEquip`/`EquipItem` and `RunUnequip`/`UnequipItem` without the
inventory: the engine removes the item from its repository (splitting one off a stack), asks
`can_equip_item` (the nine CanEquipItem checks: proficiency feats, use limitations, droid and
subrace limits, the weapon-hand rules) when the player or an AI picks something, then calls
`equip{ env, c, slot, id, item, loading, rng, ev }`. The item's passive properties become
effects with duration kind `dur::EQUIPPED` and the item's object id as creator, so the per-item
"largest wins" stacking rule holds and `clear_effects` leaves them; `unequip` removes them by
creator and moves a left-hand weapon to the right hand when the right one comes out. The results
carry the items that were displaced (`EquipResult.displaced`, `UnequipResult`) for the engine to
put back in an inventory. Usable properties (cast spell, security spikes, traps, computer spikes)
are never applied. `armour_change_refused` is the "no armour changes while attacked" rule for the
action layer; `compare_items` says whether two items would stack.

The weapon questions combat asks at attack time (`find_property`, `weapon_keen`,
`weapon_massive_criticals_row`, `weapon_on_hit_properties`, `weapon_monster_damage`,
`weapon_damage_none`, `weapon_enhancement`) read the properties directly; they are not effects.
Properties whose upgrade bit is not set in `Item.upgrades` do not count (`prop_active`).

### Combat (`combat.ctx`, `combat_attack.ctx`, `combat_damage.ctx`)

The engine runs the round (timing, animations, who pairs with whom); the library answers the
rules questions with plain results. `AttackSituation` carries the facts only the world knows:
squared distance, whether the defender perceives the attacker, the cosine of the defender's
facing to the attacker, whether the target is a door or placeable, the defender's HP, a forced
result for cutscene attacks. `make_situation{}` gives the defaults.

```
let counts = rules::attack_counts{ tables, c = &attacker, combat_feat = 0 }        // on-hand, off-hand, total; per attack off-hand? weapon type
let mut i = 0
while i < counts.total {
    let res = rules::resolve_attack{ tables, rng = &rng, atk = &attacker, def = &defender, ev = &events,
                                     sit = &situation, attack_index = i, combat_feat = feat, simulate = false }
    // res.roll (result 1 hit / 2 crit / 3 automatic / 4 miss / 8 parried / 9 returned / 10 shield, d20, every term),
    // res.damage (15 type slots + the breakdown), res.hit, res.killing_blow,
    // res.effects (Effect values for the defender or the attacker: DAMAGE effects marked "combat damage",
    //              the combat feat's AC penalty, the Critical Strike stun, on-hit properties)
    i = i + 1
}
```

`resolve_attack` is attack roll (`roll_attack`), then damage (`roll_damage`), the combat feat's
side effects and on-hit properties, with every die drawn from `rng` in the engine's order (d20,
deflection d20, threat confirmation d20, stun save, damage dice, on-hit chance). The pieces are
also public for the AI and the log: `attack_modifier`, `defense_versus`, `critical_threat_roll`,
`critical_multiplier`, `sneak_attack_eligible`, `deflection_roll`, `apply_difficulty_to_damage_roll`,
`make_damage_effects`. With `simulate = true` limited resistances are not spent (a preview).
The engine applies each returned effect with `apply_effect` at the impact time: the DAMAGE effects
come out as `DAMAGE_HP` events (and a `DEATH` effect for a coup de grace or a killed party member).

### Force powers (`force.ctx`)

`force_point_cost` (forceadjust.2da multipliers for party-controlled casters on light and dark
powers), `has_enough_force_points`, `spend_force_points` (temporary pool first),
`force_power_dc` (5 + level + WIS + CHA + Force Focus tiers), `caster_level`, `can_cast_spell`
(the equipped-armour mask against the power's forbid/require masks, entanglement, dead; returns
a reason code `cast::*`), `begin_cast` (the check, then the payment), `resist_force` (spell
immunity effects, then d20 + caster level against Force resistance for usertype 1 powers),
`spell_phase_times` (conjuration, cast, catch in ms for the engine's cast action),
`can_learn_force_power` and `learnable_powers` (class level column and the prerequisite chain),
`power_at_priority` (auto-level order). The impact scripts (`k_sp1_generic`) are NWScript and use
the VM's routines (`GetSpellSaveDC`, `ResistForce`, save routines) which call these.
`regenerate_pools` is the out-of-combat Force regeneration (1 % of the pool per second).

### Experience and level-up (`progress.ctx`)

XP: `xp_to_reach_level`, `level_for_xp`, `can_level_up`, `add_experience{ tables, c, xp,
percent_xp }` (the creature's share: `npc_percent_xp` of its npc.2da row, the player 100),
`plot_xp_value`, `kill_xp_value`, `awards_kill_xp`, `joining_xp`, `catch_up_xp`. The party pool
and who gets what is the engine's (`CSWPartyTable`): the library does the per-creature arithmetic
(rounding up, as the exe does it in float).

Level-up as data for the GUI and the engine: `level_up_options` fills a `LevelUpOptions` (skill
points, how many feats and powers this level gives, class skills and their costs, selectable
feats via `can_select_feat`/`meets_feat_requirements`, learnable powers); the GUI builds a
`LevelRecord` from the player's choices and calls `apply_level_up` (LevelUp steps 1-7: history,
class slot, feats, powers, skill ranks, ability point; the result says to heal fully).
`auto_level_up` is AutoLevelUp for companions and the auto-level option. Skill checks the engine
rolls itself: `open_lock_check`, `disarm_trap_check`, `set_trap_check`, `treat_injury_check`,
`detect_trap_check` (take 20 outside combat, d20 in it).

### Alignment mastery (`mastery.ctx`)

`update_alignment_mastery{ env, c, ids, rng, ev }`: call it when the creature's good-evil changes
and when it levels up; at 100 / 0 the light / dark side bonuses go on as innate effects, in the
middle they come off.

### Who is dead (`life.ctx`)

`is_dead{ c, hp }` (hit points < 1, < -9 for the player's creature, never for party members),
`is_downed_party_member`, `can_fight`, `DEATH_HP` (-11).

### Events the engine drains

| Event | Meaning | Fields |
|---|---|---|
| `HEAL_HP` | add hit points (the engine clamps to the maximum) | a amount, who healer |
| `DAMAGE_HP` | subtract hit points (immunity, resistance, reduction, temporary HP and the difficulty option already applied) | a amount, b damage type bits, who source |
| `DEATH` | the creature dies; the effects were stripped; set HP to -11 if higher, run the death script, award XP | a melee, b spectacular, who killer |
| `RESURRECT` | set hit points to `a` (a dead creature, or Min1HP) | a hp |
| `MAX_HP_CHANGED` | the maximum changed: keep the deficit (`hp += new - old`), die if now below 1 | a old, b new |
| `FEEDBACK` | a feedback message number (`SendFeedbackMessage`) | a number, b value |
| `CLEAR_ACTIONS`, `COMBAT_ROUND_ABORT`, `COMMANDABLE` | a crowd-control state took hold or ended | a 1/0 for commandable |
| `STATE` | the active crowd-control state changed | a new, b old |
| `VISUAL_ON/OFF`, `ICON_ON/OFF`, `APPEARANCE` | presentation | a row |
| `KNOCKDOWN`, `FORCE_PUSH` | the engine plays the animation / moves the body | |
| `EFFECT_ENDED` | an effect left the list (for the creator's affected-list bookkeeping) | a kind, who creator |

If the buffer fills, `Events.lost` counts what was dropped (the buffer holds 48).

### Time

The library keeps no clock. `Env.now` is the world time; `rules::time_add_seconds` and
`time_diff_ms` convert with `Tables.settings.ms_per_day` (1440 x the module's minutes per hour x
1000: 2,880,000 for the shipped 2).

## Determinism

All randomness goes through the `Rng` the caller passes (`rules::seed_rng`, `next_rand`,
`roll_dice`, `roll_below`, `roll_percent`). It is MSVC's `rand()` (LCG, 15 bits) and dice are
`1 + rand() % sides` summed, as in `CSWRules::RollDice`, so a seed plus the same sequence of calls
gives the same fight and the state (one `u32`) can go in a save. Nothing else reads the clock or
memory addresses.

## Decisions (where the docs left a choice)

- **Creature size** is `appearance.2da` `sizecategory` of the creature's appearance (creaturesize.2da numbering).
- **Dead creatures' effects**: `DEATH` removes everything except equipped (3) and innate (4) effects and the kinds in `removefxondeath.2da` (disguise, beam). The table's name is misleading: they are the ones *kept* (checked in the decompilation, `0x004df420`).
- **HASTE/SLOW** are derived, not stored as internal child effects: the net count sets the movement factor (x1.5 / x0.5), dodge AC (+4 / -2) and, when slowed, -2 attack and -2 reflex. The result equals the engine's HASTE_INTERNAL/SLOW_INTERNAL children.
- **Crowd-control state** is the highest-numbered active SETSTATE; the AI mask and save penalties follow from it in `recompute`; the engine learns of transitions through events instead of internal effects.
- **Limited resistance and reduction** count the limit down by the whole damage as the exe does (`0x004d0e40`, `0x004d09e0`), not by what they absorbed.
- **AC damage filter**: as the exe: the attack's versus pass admits only its own sentinel 0x4007 (the script constant is 0x2007, so a script AC effect never counts there), and the stats count every effect with any race and no alignment whatever its filter (re/combat.md 5.2, 5.4).
- **Difficulty**: `Tables.settings.difficulty` 0/1/2 (easy, normal, difficult) selects `difficultyopt.2da` row = difficulty and `diffsettings.2da` column easy/normal/hardcore (1, 2, 3).
- **Temporary effects while a creature is not updated**: expiry happens at the next `update_effects` after the time passes, as in the engine.

- **Item effects** carry derived ids (high bit, item id, number among the item's effects), subtype bits 0 (Dispel leaves them alone) and are not exposed to scripts; `equip` therefore needs no `EffectIds`. The item-level check of CanEquipItem is skipped (its table holds no limit). `equip` sends feedback events unless `loading`.
- **Difficulty columns**: difficulty 0, 1, 2 read the diffsettings columns `easy`, `normal`, `hardcore` (the exe stores columns 1-5 by the server's 0-4 value and the file's first value column is `dmeasy`; unverified); the party's damage multiplier (difficultyopt) is applied by the DAMAGE effect.
- **Combat**: a combat feat the attacker lacks counts as none; its to-hit and damage apply to every attack of the round, its side effects (self AC penalty, stun) to the first only; DAMAGE_REDUCTION is compared with the low byte of the attacker's attack effect bonus against the target, as the exe does (`0x004fd6f0`); doors and placeables are targets with defense 0, no deflection, sneak attack or mitigation; effect damage bonuses are added to the total and spread over the 15 type slots.
- **Blaster deflection effects** hold the amount in int0 (script-made) or int1 (item-made, int0 is the subtype): the roll sums both.
- **Force Push** is goodevil `-` in spells.2da, so alignment never changes its cost; the multiplied powers are the `G` and `E` ones.
- **Powers per level** come from classpowergain.2da everywhere (level screen and automatic level-up): the exe's AutoLevelUp effectively grants one per level, a quirk we don't copy. The level column is compared with the level before the level-up. The prerequisite check ignores the exe's extra "enough Force points to cast the prerequisite" condition.
- **Auto-leveller feat and skill order** is a literal port of the exe's priority-list walk (Expert Droid fills 7 of its 10 feat slots); at most two class slots (the screens' limit; LevelUp has none).
- **Skill checks**: take 20 outside combat, d20 in combat, one `in_combat` flag on the call.
- **XP** arithmetic follows the exe's float math (100 XP at an 80 % share is 80, rounded up).

## Verification

`kotor/tools/ctxc run kotor/tools/rulescheck -- [--only examples|census|items|combat|progress]`
(exit code 0 when every check passed):

- **examples**: worked examples computed by hand from the docs (ability modifiers, BAB, saves, max HP
  and FP for player characters and others, class AC bonus, effect stacking and caps, temporary
  hit points, damage mitigation order, haste/slow, crowd-control states, links, saving throw
  rolls, the `rand()` sequence).
- **census**: every UTC copy in the install (1959) through `read_creature`: levels, abilities,
  BAB, saves, hit points, Force points, armour class and skill ranks in range.
- **saved**: the 20 creatures in the install's saved game (the player, companions, enemies) have
  their equipment put on with `equip`; our fortitude, reflex and will saves, armour class, maximum
  hit points and maximum Force points equal the totals the original saved, for every one, and so do
  its CombatInfo numbers: attacks per round, the sheet attack modifier (ability, Weapon Focus and
  dual-wield terms), critical threat width and multiplier, the weapon dice and Force resistance.
- **items**: all 1055 UTIs through `read_item` and the property handlers (the documented counts
  are reproduced: 61 with upgrade-gated properties, Keen 47, OnHit 107, Massive Criticals 36,
  Monster damage 33), equip examples and the CanEquipItem rules for humans, droids and Wookiees.
- **combat**: worked examples of every attack-modifier term, defense, threat ranges, dual wield,
  combat feats, sneak attack, mitigation order, the roll order for a seed; 40,000 seeded fights
  (hit rate .748 against .75 expected, criticals .076 against .075, 2d8 mean 8.98); every UTC as
  an attacker (modifier -4..45, defense 6..35, no anomalies).
- **progress**: thresholds, Force point costs at both ends of the alignment axis, DCs, casting
  with and without armour, XP awards, feat requirements; a player character levelled from 1 to 10
  (Guardian: 120 HP, 110 FP, BAB 10, saves 9/9/7), all nine classes to level 20; the 1959
  templates swept for Force points, power prerequisites and feat requirements.

`kotor/tools/ctxc exe kotor/tools/rulescheck -o kotor/out/rulescheck.exe` and run it: 1143
checks pass (a few seconds with a warm disk cache).

## Not done

- **Writing creatures back to GFF** (saves, stage 6): the library reads the template and saved
  fields; the engine writes its own object fields and needs `Creature` serialised next to them
  (classes, history, feats, powers, skills, effects). The fields are all plain values, so a
  writer is straightforward once the save layout is fixed.
- Disease ticks, Dispel Magic, Force push/jump/lightsaber-throw
  movement, the impact scripts themselves: the docs mark them low confidence or they belong to
  the engine and the script layer.
- **Resting and the party rest GUI**: the engine has no such code that we found.
