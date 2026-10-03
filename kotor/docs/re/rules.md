# The d20 rules in swkotor.exe: effects, saves, Force powers, XP, skills, feats

What the engine does with the rules that sit around the attack roll: the effect system (the
object every buff, debuff, crowd-control and Force power result is made of), saving throws, Force
point costs and DCs, experience and level-up, the skills the engine itself rolls, and feat and
power prerequisites. Addresses are for the Steam `swkotor.exe` after SteamStub removal (see
[README.md](README.md)); names are ours, in the Aurora/NWN vocabulary, and are proposed in
`kotor/re/proposals/rules.tsv` (git-ignored, merged into [names.tsv](names.tsv) by the lead).
Every claim ends with a confidence: **high** (read in the code), **med** (role clear, a detail
inferred), **low** (plausible).

Boundaries with the pages written alongside this one:

- [combat.md](combat.md) owns the combat round, attack rolls, AC as the attacker sees it, damage
  application (including how damage reduction/resistance/immunity effects absorb damage) and
  death as a combat outcome. This page describes those effects as objects and says which getter
  sums them.
- [actions.md](actions.md) owns the action queue; here only the rules inside CASTSPELL, OPENLOCK,
  the trap actions and HEAL are described.
- [gameloop.md](gameloop.md) owns the world timer, the event queue and DelayCommand; this page
  uses event 5 (APPLY_EFFECT), 8 (SPELL_IMPACT) and 14 (REMOVE_EFFECT) from
  [objects.md](objects.md).
- [dialogue.md](dialogue.md) owns conversations (Persuade checks and plot XP awarded by
  dialogue are scripted), [party-items-saves.md](party-items-saves.md) the party table, items and
  save games, [gui.md](gui.md) the level-up and character-creation panels, [movement.md](movement.md)
  perception and targeting.

Background: creature and stats layouts are in [objects.md](objects.md) section 4; the 2DA cache
(`C2DAs`, `g_pRules` `0x007a3a28` +0xb8) in [resources.md](resources.md); the effect as a script
engine structure in [vm.md](vm.md).

## 1. The effect system

### 1.1 The effect object (`CGameEffect`, 0x8c bytes)

Constructor `0x00503e40(bCreateNewId)`; script constructors call it with 1, which takes the next
value of a 64-bit counter (`g_nNextEffectId`, `0x007a1b40`). Save/load `0x00503790`/`0x005043a0`
use the GFF labels in the table; copy `0x00504090`. (high)

| Offset | GFF label | Meaning | Conf. |
|---|---|---|---|
| +0x00 | `Id` (DWORD64) | effect id. Linked children share their parent's id, and removal works by id | high |
| +0x08 | `Type` (WORD) | internal effect type (table in 1.3) | high |
| +0x0a | `SubType` (WORD) | bits 0–2 duration type, bits 3–4 subtype (below) | high |
| +0x0c | `Duration` (FLOAT) | seconds, set by `ApplyEffectToObject` for temporary effects | high |
| +0x10 / +0x14 | `ExpireDay` / `ExpireTime` | absolute world time (calendar day, ms of day) when a temporary effect ends | high |
| +0x18 | `CreatorId` | object id; `OBJECT_INVALID` by default | high |
| +0x1c | `SpellId` | spell (spells.2da row) that created it, −1 for none | high |
| +0x20 | `IsExposed` | 1 for effects made by script constructors, 0 for engine sub-effects | high |
| +0x24 | — | caster level override, −1 by default; `ApplyEffectToObject` copies the creator creature's item-cast caster level (+0x968) here when its flag +0x964 is set | med |
| +0x28 / +0x2c | — | link children (left, right); only `EffectLinkEffects` effects have them | high |
| +0x30 / +0x34 | `NumIntegers` / `IntList` | count and array of int parameters (8 by default; 21 for DAMAGE and POISON) | high |
| +0x38..+0x44 | `FloatList` | 4 float parameters | high |
| +0x48..+0x70 | `StringList` | 6 string parameters | high |
| +0x78..+0x84 | `ObjectList` | 4 object id parameters (`OBJECT_INVALID` by default) | high |
| +0x88 | `SkipOnLoad` | set by `ApplyEffect`: 0 only for exposed effects on objects whose +0x1ec is 0; when loading, effects so marked are not re-applied (their parents rebuild them) | med |

Accessors (all high): `GetInteger` `0x00503690`, `SetInteger` `0x005036a0`, `GetFloat`
`0x005036c0`, `SetFloat` `0x005036d0`, `GetObjectID` `0x005036e0`, `SetObjectID` `0x005036f0`,
`GetString` `0x00503700`, `SetNumIntegers` `0x00503630`, `Set/GetExpiryTime` `0x00503750`/`0x00503770`.

**SubType word.** Duration type in bits 0–2: 0 instant, 1 temporary, 2 permanent (the script
`DURATION_TYPE_*` values), plus two engine-only values: 3 *equipped* (effects made from item
properties while the item is worn) and 4 *innate* (internal effects the engine adds and removes
itself, e.g. HASTE_INTERNAL, SETSTATE_INTERNAL, the alignment mastery effects). Subtype in bits
3–4: 8 magical, 0x10 supernatural, 0x18 extraordinary (the `SUBTYPE_*` constants). Every script
constructor sets magical; `MagicalEffect`/`SupernaturalEffect`/`ExtraordinaryEffect`
(`0x005435c0`) rewrite the bits. (high)

**Creator and spell id.** `SetCreator` (`0x00503a00`) stores the creator and copies the
creator's *current spell id* (CSWSObject virtual slot 46, the id set while an impact script runs)
into +0x1c; if the creator is an area-of-effect object, the AoE's own creator (+0x248) is stored
instead. Every `Effect*` constructor calls it with `OBJECT_SELF`, so effects built inside a spell
impact script automatically carry that spell's id. (high)

**Sub-effects.** Handlers that need extra effects build them with `CGameEffectFromParent`
(`0x00503f70`), which copies id, subtype/duration bits, duration, expiry, creator and spell id from
the parent and leaves `IsExposed` 0. Because the id is shared, removing the parent removes them.
(high)

### 1.2 Script constructors

Parameter defaults are the `nwscript.nss` ones. "Type" is the internal type in 1.3. All set the
subtype to magical and the creator to `OBJECT_SELF` unless noted. (high unless marked)

| Routine | Handler | Type | Parameters as stored |
|---|---|---|---|
| 51 EffectAssuredHit | `0x005313f0` (shared) | 0x65 | — |
| 78 EffectHeal | `0x00532a70` | 0x27 | int0 amount |
| 79 EffectDamage | `0x00531ae0` | 0x26 | 21 ints: int0..13 = amount per damage type, −1 for the others (index = log2 of the `DAMAGE_TYPE_*` bit); int14 amount; int16 1000; int17 damage type flags; int18 damage power. Amount outside 0..10000 → 1, type outside 0..0x2000 → 8 (universal), power outside 0..6 → 0 |
| 80 EffectAbilityIncrease / 446 …Decrease | `0x005307f0` / `0x00530680` | 0x24 / 0x25 | int0 ability (0 STR..5 CHA), int1 amount |
| 81 EffectDamageResistance | `0x00532500` | 0x02 | int0 damage type, int1 amount, int2 limit |
| 82 EffectResurrection | `0x00533660` | 0x04 | — |
| 115 EffectACIncrease / 450 …Decrease | `0x00530b20` / `0x00530960` | 0x30 / 0x31 | int0 modifier type (0 dodge, 1 natural, 2 armour, 3 shield, 4 deflection; outside 0..4 → 0), int1 amount, int2 race (= "any race", the race count at `g_pRules`+0xaa), int5 versus damage type |
| 117 EffectSavingThrowIncrease / 452 …Decrease | `0x00533910` / `0x00533760` | 0x1a / 0x1b | int0 amount, int1 save (0 all, 1 fort, 2 reflex, 3 will), int2 save type, int3 race (any) |
| 118 EffectAttackIncrease / 447 …Decrease | `0x005310e0` / `0x00530f60` | 0x0a / 0x0b | int0 amount, int1 modifier type (0 misc, 1 on-hand, 2 off-hand), int2 race (any) |
| 119 EffectDamageReduction | `0x00532350` | 0x0c | int0 amount, int1 damage power, int2 limit |
| 120 EffectDamageIncrease / 448 …Decrease | `0x005321b0` / `0x00531d50` | 0x0d / 0x0e | int0 amount (a row of iprp_damagecost.2da; see 1.9), int1 damage type, int2 race (any) |
| 130 EffectEntangle | shared | 0x12 | — |
| 133 EffectDeath | shared | 0x13 | int0 spectacular, int1 display feedback (default 1) |
| 134 EffectKnockdown | shared | 0x14 | — |
| 148 EffectParalyze | shared | 0x08 | int0 state 5 |
| 149 EffectSpellImmunity | `0x00533e70` | 0x32 | int0 spell |
| 153 EffectForceJump | `0x005348c0` | 0x66 | obj0 target, int0 advanced |
| 154 EffectSleep | shared | 0x08 | int0 state 6 |
| 156 EffectTemporaryForcePoints | `0x00534340` | 0x5b | int0 amount |
| 157 EffectConfused / 158 EffectFrightened | shared | 0x08 | int0 state 1 / 2 |
| 159 EffectChoke | `0x005351e0` | 0x08 | int0 state 7 |
| 161 EffectStunned | shared | 0x08 | int0 state 4 |
| 164 EffectRegenerate | shared | 0x07 | int0 amount, int1 interval in ms (seconds × 1000) |
| 165 EffectMovementSpeedIncrease / 451 …Decrease | `0x00533420` / `0x005332e0` | 0x1c / 0x1d | int0 percent |
| 171 EffectAreaOfEffect | `0x00530ce0` | 0x1f | int0 vfx_persistent row, string0..2 OnEnter/Heartbeat/OnExit scripts |
| 180 EffectVisualEffect | `0x005346b0` | 0x1e | int0 visualeffects.2da row, int2 miss flag |
| 199 EffectLinkEffects | `0x00532f80` | 0x28 | children (child, parent) |
| 207 EffectBeam | `0x00531260` | 0x20 | int0 beam vfx, int1 body part, int2 miss, obj0 effector |
| 212 EffectForceResistanceIncrease / 454 …Decrease | `0x00534230` / `0x00534120` | 0x21 / 0x22 | int0 amount |
| 224 EffectBodyFuel | `0x00535290` | 0x62 | — |
| 250 EffectPoison | `0x00533560` | 0x23 | int0 poison.2da row |
| 252 EffectAssuredDeflection | shared | 0x68 | int0 nReturn |
| 269 EffectForcePushTargeted | `0x00534ab0` | 0x3c | int0 1, int1 ignore-line test, float0..2 centre |
| 270 EffectHaste | shared | 0x01 | — |
| 273 EffectImmunity | `0x00532d00` | 0x16 | int0 immunity type, int1 race (any) |
| 275 EffectDamageImmunityIncrease / 449 …Decrease | `0x00532050` / `0x00531ef0` | 0x10 / 0x11 | int0 damage type, int1 percent |
| 314 EffectTemporaryHitpoints | `0x00534490` | 0x0f | int0 amount (≤ 0 gives an invalid effect) |
| 351 EffectSkillIncrease / 453 …Decrease | `0x00533d00` / `0x00533b90` | 0x37 / 0x38 | int0 skill (0xff = all), int1 amount, int2 race (any) |
| 372 EffectDamageForcePoints / 373 EffectHealForcePoints | `0x00534f40` / `0x00535020` | 0x5f / 0x60 | int0 amount |
| 387 EffectHitPointChangeWhenDying | `0x00532bd0` | 0x39 | float0 HP per round |
| 391 EffectDroidStun | `0x00534810` | 0x08 | int0 state 3 |
| 392 EffectForcePushed | `0x005349f0` | 0x3c | — |
| 402 EffectForceResisted | shared | 0x69 | obj0 source |
| 420 EffectForceFizzle | shared | 0x6a | — |
| 457 EffectInvisibility | `0x00532e40` | 0x2f | int0 invisibility type, int1 race (any) |
| 458 EffectConcealment / 477 EffectMissChance | `0x005319a0` / `0x00533090` | 0x4c | int0 percent (outside 1..100 gives an invalid effect), int1 race (any) / 0 |
| 459 EffectForceShield | `0x00532690` | 0x6b | int0 forceshields.2da row |
| 460 EffectDispelMagicAll / 473 …Best | shared | 0x33 / 0x34 | int0 caster level |
| 463 EffectDisguise | shared | 0x3e | int0 appearance |
| 465 EffectTrueSeeing / 466 EffectSeeInvisible | `0x005345e0` / `0x00533ac0` | 0x48 / 0x46 | — |
| 467 EffectTimeStop | shared | 0x40 | — |
| 469 / 470 EffectBlasterDeflection Increase / Decrease | `0x00534cd0` / `0x00534db0` | 0x5c / 0x5d | int0 amount |
| 471 EffectHorrified | `0x00534e90` | 0x08 | int0 state 8 |
| 472 EffectSpellLevelAbsorption | `0x00533fa0` | 0x41 | int0..2, int3 (int1 == 0) |
| 485 EffectModifyAttacks | `0x005331c0` | 0x2c | int0 attacks |
| 487 EffectDamageShield | `0x00532790` | 0x3d | int0 amount, int1 random, int2 damage type |
| 552 SetEffectIcon | `0x005475a0` | 0x43, linked | builds an ICON effect (int0 effecticon.2da row) and returns `Link(icon, effect)` |
| 675 EffectForceDrain | `0x00532920` | 0x5a | int0 amount |
| 676 EffectPsychicStatic | `0x00535340` | 0x63 | — |
| 702 EffectLightsaberThrow | `0x005353f0` | 0x64 | obj0..2 targets, int advanced |
| 703 EffectWhirlWind | `0x00534c20` | 0x08 | int0 state 10 |
| 754 / 755 / 756 EffectCutScene Horrified / Paralyze / Stunned | shared | 0x08 | int0 state 8 / 5 / 4, **int1 1** (cutscene: skips immunity) |
| 355–357 Versus{Alignment,RacialType,Trap}Effect | `0x00545470` | — | rewrite the versus ints of the wrapped effect |

The shared handler is `0x005313f0`, which switches on the routine number. (high)

### 1.3 Internal types and their handlers

The effect list handler (`CSWSEffectListHandler`, vtable `0x00744274`, one instance at
`CServerAIMaster`+0x58) keeps two 0x6e-entry function tables, filled by `InitializeEffects`
(`0x004e4a10`): +4 apply handlers, +8 remove handlers, indexed by internal type.
`OnEffectApplied` (`0x004d8320`) and `OnEffectRemoved` (`0x004d8360`) dispatch; a missing handler
or a type ≥ 0x6e returns 1. The item property handler (vtable `0x00744284`, at +0x5c) is the same
pattern with 0x3c entries. (high)

**Return convention.** An apply handler returns **0 to keep the effect** in the object's list
(it is a lasting modifier) and **1 to drop it** (instant effect, rejected by immunity, or one that
only spawned children). Remove handlers return 1. Generic handlers: `OnApplyPassive`
(`0x004de5f0`, keep; for types read only by getters), `OnRemovePassive` (`0x004ddf20`), a folded
"return 0" (`0x0066b360`, keep, no creature check) and a folded "return 1" (`0x004df410`).
`OnRemoveMarkCombatDirty` (`0x004d92a0`) sets the creature's recompute flag (+0x344, which makes
the next `AIUpdate` call the stats recompute `0x005addc0`). (high)

Script type is what `GetEffectType` returns (mapping `0x00503a70`; 0 where unmapped). Names
marked † are guesses from the NWN numbering, which KOTOR follows up to 0x2a and then shifts by
one; the rest come from a constructor or the script mapping.

| Int. | Name | Script | Apply / remove | What the apply handler does | Conf. |
|---|---|---|---|---|---|
| 0x01 | HASTE | 36 | `0x004e2a90` / `0x004e2d50` | shared with SLOW: counts haste (+1) and slow (−1) effects; when the sign of the total changes, adds an innate HASTE_INTERNAL or SLOW_INTERNAL, or removes it at 0. Slow is refused by immunity 9 (feedback 0x92) | high |
| 0x02 | DAMAGE_RESISTANCE | 1 | folded keep | read when damage is applied (slot 42, [combat.md](combat.md)) | high |
| 0x03 | SLOW | 37 | as 0x01 | — | high |
| 0x04 | RESURRECTION | — | `0x004e13c0` | only on a dead object: HP to 1 if ≤ 0, clear actions, AI mask all-allowed, commandable, remove temporary HP_CHANGE_WHEN_DYING effects | med |
| 0x05 | DISEASE | 32 | `0x004e2720` / `0x004db870` | disease.2da (`First_Save`, `Incu_Hours`), immunity 3 | med |
| 0x06 | SUMMON_CREATURE | — | `0x004d8680` / `0x004d8a10` | loads a creature template and places it | med |
| 0x07 | REGENERATE | 3 | `0x004db2c0` | stamps the current time in int2/int3; ticks in `UpdateEffectList` (1.6) | high |
| 0x08 | SETSTATE | by state | `0x004e1c20` / `0x004e22f0` | crowd control, 1.10 | high |
| 0x09 | SETSTATE_INTERNAL | — | `0x004da330` / `0x004da870` | the per-state blocking, 1.10 | high |
| 0x0a / 0x0b | ATTACK_INCREASE / DECREASE | 40 / 41 | `0x004d9120`, `0x004d9170` / dirty | kept if amount > 0; the decrease is refused for plot creatures and by immunity 20 | high |
| 0x0c | DAMAGE_REDUCTION | 7 | folded keep | read by slot 41 `DoDamageReduction` (`0x004d09e0`) | high |
| 0x0d / 0x0e | DAMAGE_INCREASE / DECREASE | 42 / 43 | `0x004d9200`, `0x004d9230` / dirty | the decrease is refused by immunity 21 | high |
| 0x0f | TEMPORARY_HITPOINTS | 9 | `0x004d92d0` / `0x004d9320` | adds int0 to the object's bonus HP (+0xe4); removal subtracts it (floor 0) | high |
| 0x10 / 0x11 | DAMAGE_IMMUNITY_INCREASE / DECREASE | 44 / 45 | `0x004d9620`, `0x004d9680` / `0x004e18d0`, `0x004e19a0` | update the object's per-damage-type immunity table (+0x1ac); the decrease checks immunity 22 | med |
| 0x12 | ENTANGLE | 11 | `0x004d9720` / `0x004d9970` | 1.10 | high |
| 0x13 | DEATH | — | `0x004e0ac0` | 1.9 | high |
| 0x14 | KNOCKDOWN | — | `0x004d99b0` / `0x004d9c50` | 1.10 | high |
| 0x15 | DEAF | 13 | `0x004da090` | children 0x17 and 0x19; immunity 8 | med |
| 0x16 | IMMUNITY | 15 | passive | read by `GetEffectImmunity` (1.8) | high |
| 0x17 | SET_AI_STATE | — | `0x004da050` / `0x004e1a70` | ANDs int0 into the creature's AI state mask (+0x9f0); removal recomputes the mask from the remaining ones | high |
| 0x18 | ENEMY_ATTACK_BONUS | 17 | `0x004da260` / `0x004e1b00` | touches stats +0x103 | med |
| 0x19 | ARCANE_SPELL_FAILURE | 18 | `0x004da2c0` / `0x004e1b80` | — | low |
| 0x1a / 0x1b | SAVING_THROW_INCREASE / DECREASE | 50 / 51 | `0x004d8cb0`, `0x004d8d00` / dirty | the decrease checks immunity 25 | high |
| 0x1c / 0x1d | MOVEMENT_SPEED_INCREASE / DECREASE | 48 / 49 | `0x004da910`, `0x004da990` / `0x004e2490` | 1.7 | high |
| 0x1e | VISUALEFFECT | 75 | `0x004daa40` / `0x004dadc0` | 1.11 | high |
| 0x1f | AREA_OF_EFFECT | 20 | `0x004dade0` / `0x004db010` | creates the AoE object | med |
| 0x20 | BEAM | 21 | `0x004db090` | visual child | med |
| 0x21 / 0x22 | FORCE_RESISTANCE_INCREASE / DECREASE | 52 / 53 | `0x004db180`, `0x004db210` / `0x004e2570`, `0x004e2650` | 1.7 | high |
| 0x23 | POISON | 31 | `0x004db320` / `0x004db810` | 1.9 | high |
| 0x24 / 0x25 | ABILITY_INCREASE / DECREASE | 38 / 39 | `0x004d84d0`, `0x004d8590` / `0x004d8550`, `0x004d8650` | kept if amount > 0 and the creature is not dead or dying; the decrease also needs not-plot and no immunity 19 | high |
| 0x26 | DAMAGE | — | `0x004dfa40` | applies damage ([combat.md](combat.md)); never kept | high |
| 0x27 | HEAL | — | `0x004e0750` | 1.9 | high |
| 0x28 | LINK | — | `0x004db8a0` | 1.5 | high |
| 0x29 | HASTE_INTERNAL | — | `0x004db8f0` / `0x004dba30` | children: movement 150 %, +4 dodge AC | high |
| 0x2a | SLOW_INTERNAL | — | `0x004dba50` / `0x004dbcc0` | children: movement −50 %, −2 dodge AC, −2 attack, −2 reflex, LIMIT_MOVEMENT_SPEED | high |
| 0x2b | ? | — | passive | — | low |
| 0x2c | MODIFYNUMATTACKS | — | `0x004dbd90` / `0x004dbe00` | adjusts the combat round's attack count (creature +0x9a4) | med |
| 0x2d | CURSE † | 33 | `0x004dbe60` | six ABILITY_DECREASE children, immunity 17 | med |
| 0x2e | SILENCE † | 34 | `0x004dc200` / `0x004dc380` | immunity 11, AI-state child | med |
| 0x2f | INVISIBILITY | 56 | `0x004e3be0` / `0x004e3c30` | — | med |
| 0x30 / 0x31 | AC_INCREASE / DECREASE | 46 / 47 | `0x004d8d80`, `0x004d8f80` / `0x004e14d0`, `0x004e16e0` | 1.7 | high |
| 0x32 | SPELL_IMMUNITY | 73 | folded keep | read by the spell immunity check | high |
| 0x33 / 0x34 | DISPEL_MAGIC_ALL / BEST | 59 / 69 | `0x004e40d0` / `0x004e43c0` | remove magical effects, comparing caster level with the target's level (not read in detail) | low |
| 0x35 | TAUNT † | — | `0x004dc3b0` / `0x004dc500` | AC decrease and 0x19 children | low |
| 0x36 | LIGHT † | — | `0x004dbce0` | visual child; built by an item property | low |
| 0x37 / 0x38 | SKILL_INCREASE / DECREASE | 54 / 55 | `0x004dc580`, `0x004dc5d0` | the decrease checks immunity 27 | high |
| 0x39 | HITPOINTCHANGEWHENDYING | — | `0x004dc660` / `0x004dc7a0` | — | med |
| 0x3a | SETWALKANIMATION † | — | `0x004dca80` / `0x004e3050` | creature +0xa10 | low |
| 0x3b | LIMIT_MOVEMENT_SPEED | — | `0x004dc530` / `0x004e2fe0` | walk-only flag (creature +0x8e8) | high |
| 0x3c | FORCE_PUSH | — | `0x004e3800` / `0x004de400` | knock-back along the push direction; SETSTATE child | med |
| 0x3d | DAMAGE_SHIELD | 60 | folded keep | read on being hit | high |
| 0x3e | DISGUISE | 62 | `0x004e31d0` / `0x004dcac0` | appearance swap | high |
| 0x3f | SANCTUARY | 63 | `0x004e3d10` / `0x004e3e70` | Will save from attackers | med |
| 0x40 | TIMESTOP | 66 | `0x004dcb40` / `0x004dcc90` | pauses world timers | med |
| 0x41 | SPELL_LEVEL_ABSORPTION | 68 | folded keep | the reader does nothing with it | med |
| 0x43 | ICON | — | `0x004e4790` / `0x004e30d0` | 1.11 | high |
| 0x46 / 0x47 / 0x48 / 0x49 / 0x4a | SEE_INVISIBLE / ULTRAVISION / TRUE_SEEING / BLINDNESS / DARKNESS | 65 / 70 / 64 / 67 / 58 | `0x004dcd00`, `0x004e3320`, `0x004e35b0`, `0x004dcd30`, `0x004dcff0` | set vision bits at creature +0x8ec (2 true seeing, 8 blind, 0x10 darkness) | med |
| 0x4b / 0x4c | MISS_CHANCE / CONCEALMENT | 71 / 72 | `0x004dcfc0` | both script constructors build 0x4c | high |
| 0x52 | NEGATIVELEVEL | 61 | `0x004dd520` / `0x004dd970` | attack, save, skill decreases by level; immunity 29 | med |
| 0x5a | FORCE_DRAIN | — | `0x004ddec0` | Force pool − int0, floor 0 | high |
| 0x5b | TEMPORARY_FORCE_POINTS | — | `0x004dde40` / `0x004dde80` | temporary FP (stats +0x126) ± int0 | high |
| 0x5c / 0x5d | BLASTER_DEFLECTION_INCREASE / DECREASE | — | passive | read by the deflection roll | high |
| 0x5f / 0x60 | DAMAGE / HEAL_FORCE_POINTS | — | `0x004de4d0` / `0x004de540` | 3.6 | high |
| 0x62 | BODY_FUEL | — | `0x004de5b0` / `0x004de5d0` | creature +0xa9c flag | med |
| 0x63 | PSYCHIC_STATIC | — | passive | — | med |
| 0x64 | LIGHTSABER_THROW | 76 | `0x004de600` / `0x004dece0` | throw and return, DAMAGE children | med |
| 0x65 | ASSURED_HIT | 74 | `0x004d83a0` / `0x004d83f0` | creature flag +0x8d4 | high |
| 0x66 / 0x67 | FORCE_JUMP / its internal step | 77 / — | `0x004ddf40` / `0x004de0a0` | — | med |
| 0x68 | ASSURED_DEFLECTION | 78 | `0x004d8420` / `0x004d8490` | creature flags +0x8dc (and +0x8d8 when int0 ≠ 0) | high |
| 0x69 / 0x6a | FORCE_RESISTED / FORCE_FIZZLE | — | `0x004ded00` / `0x004dede0` | instant visual child only | high |
| 0x6b | FORCE_SHIELD | — | `0x004df540` | forceshields.2da visuals and resistances | med |
| 0x6c / 0x6d | LIGHT_SIDE / DARK_SIDE_MASTERY | — | `0x004dee90` / `0x004df160` | 3.8 | high |

Types 0x42, 0x44, 0x45, 0x4d–0x51, 0x53, 0x54, 0x56–0x59, 0x5e, 0x61 have handlers but no script
constructor; their creators are listed in the proposals file (all low).

### 1.4 Applying an effect

`ApplyEffectToObject` (`0x0052e570`) and `ApplyEffectAtLocation` (`0x0052e430`) set the duration
bits from `nDurationType` (instant 0, temporary 1 with `Duration` = fDuration, permanent 2), copy
the caster level override (1.1), and call `CSWSObject::ApplyEffect` **directly** (synchronously,
while the script runs). Engine code that wants a delay queues event 5 (APPLY_EFFECT) instead; the
event handler calls the same function. A target that is not an object frees the effect. (high)

`CSWSObject::ApplyEffect(effect, bLoadingGame, bLinkTop)` (`0x004d14f0`), in order (high unless
marked):

```
effect.SkipOnLoad = not (object+0x1ec == 0 and effect.IsExposed)              (med)
result = OnEffectApplied(object, effect, bLoadingGame)
if result == 1:                                       # not kept
    if effect is a LINK and bLinkTop and object.linkPending: RemoveEffectById(effect.id)
    else free the effect
    return
if not (effect is VISUAL with int0 not 5000/5001, or ICON): object.linkPending = 0
if duration type == temporary and not bLoadingGame:
    expiry = now + Duration                            # days and ms via the world timer
insert into the list (+0x124/+0x128) after the last effect of the same or lower type
if creature: UpdateEffectPtrs(); UpdateAttributesOnEffect(effect)
if subtype == magical: add this object's id to the creator's affected-object list (+0x13c)
```

`linkPending` (+0x148) is set by `ApplyEffectToObject` and by the APPLY_EFFECT event when the
effect is a LINK, cleared afterwards. Its purpose: when a linked effect is refused (say the target
is immune to the stun in a stun + visual link) and no non-cosmetic child stuck, the whole link id
is removed again, taking the already-applied visual with it. (med)

The list is **sorted by type, stable**. Creatures keep the index of the first effect of 26 types
in their stats (+0x12e..+0x162, rebuilt by `UpdateEffectPtrs` `0x004f14f0`, virtual slot 54) so
that getters can start at the right place and stop at the first higher type. An implementation
may use any structure, but iteration order (by type, then by application order) is visible to
the "highest wins" rules below and to `GetFirstEffect`/`GetNextEffect`. (high)

`UpdateAttributesOnEffect` (`0x004ffaf0`, slot 55) runs after every applied or removed
ABILITY_INCREASE/DECREASE: it recomputes that ability's modifier; for CON it keeps the HP deficit
(current = new max − (old max − current)) and, if the creature newly drops to dead or dying,
queues an instant DEATH effect (event 5, int1 = 1); for WIS and CHA it keeps the FP deficit the
same way. (high)

### 1.5 Linked effects

`EffectLinkEffects(child, parent)` builds a LINK (0x28) whose two children are the arguments and
calls `UpdateLinked` (`0x00504240`), which copies the link's subtype, creator, duration, duration
type, expiry, spell id **and id** into both children, recursively. The LINK apply handler
(`0x004db8a0`) refreshes that, applies each child through `ApplyEffect`, detaches them and
returns 1, so the list never holds the LINK itself, only its leaves, all with the same id. (high)

Consequences an implementer must keep: a link is removed as a unit (removal is by id); a link
applied as temporary makes every child temporary with the same expiry; `GetEffectType` of a link
returns 0. (high)

### 1.6 Expiry and periodic effects

`CSWSObject::UpdateEffectList(day, time)` (`0x004d1730`) is called from the `AIUpdate` of
creatures (`0x004fe210`, right after `UpdateCombat` and before `RunActions`), placeables and doors,
i.e. every time the AI master updates the object — normally every frame, not once per round.
For each effect in list order (high):

1. **REGENERATE (0x07)**: elapsed = now − (int2, int3). If the object is a non-creature with
   HP < max and alive, or a creature that is alive, not dying, and either below max HP or (when
   int4 is 0x36) below max Force points, and elapsed > int1 ms, it applies an instant HEAL (int0
   amount, int1 = int4, creator = the regen's creator) and restamps int2/int3.
2. **POISON (0x23)**: if more than int5 s have passed since the start (int1, int2), queue its
   removal (event 14); otherwise, every int6 s since the last tick (int3, int4), apply one more
   tick (`ApplyPoisonTick` `0x004ee770`) — skipped while the in-game GUI flag (+0xb4) is set,
   which only advances the schedule.
3. **DISEASE (0x05)**: compares (int3, int4) with now and calls the disease tick `0x004f6790`.
4. **Expiry**: if the duration type is temporary and `CompareWorldTimes(now, expiry)` (`0x004adfa0`)
   says now is later, `RemoveEffectById` and restart the scan from the first effect.

A temporary effect therefore ends on the first object update after its expiry time. Durations are
seconds; the world timer converts them with seconds-per-day = 1440 × minutes-per-hour (+0x40) and
keeps the remainder in ms (`0x004ae1b0`, `0x004ae200`). (high)

Poison and disease use world time, so they stop when the timer is paused. Regeneration uses the
same clock. (med)

### 1.7 How getters combine effects (stacking)

Most numeric effects are not applied to fields when they arrive; getters walk the list when asked.
The central walker is `CSWSCreature::GetTotalEffectBonus(category, versus, …)` (`0x004f3fe0`):

| Category | Effect types | Filter | Cap (bonus / penalty) | Used by |
|---|---|---|---|---|
| 1 attack | 0x0a / 0x0b | int1 modifier type 0 (misc) or the current attack's hand; int2 race any or the versus creature's race; int4 alignment group 0 or the versus creature's | +20 / −20 | attack bonus ([combat.md](combat.md)) |
| 2 damage | 0x0d / 0x0e | as attack, plus int5 attack type; damage type flags must overlap | +36 / −36 | damage roll |
| 3 saving throw | 0x1a / 0x1b | int1 save 0 or this save; int2 save type 0 or this type; int3 race; int5 alignment | +20 / −20 | saves (2.1) |
| 4 ability | 0x24 / 0x25 | int0 = the ability | +20 / −30 | `GetSTRStat` … `GetCHAStat` |
| 5 skill | 0x37 / 0x38 | int0 0xff or the skill; int2 race; int4 alignment | +30 / −30 | `GetSkillRank` |

Result = min(sum of bonuses, cap) − min(sum of penalties, cap). (high)

**Same-source rule.** Within a category, bonuses (and separately penalties) are grouped by source;
from each group only the largest counts, and the groups are added:

- for saves, abilities and skills, an effect whose creator is an **item** (an equipped item's
  property) groups with the other effects of that item (attack and damage only group by spell);
- otherwise an effect with a **spell id** (not −1) groups with the other effects of that spell;
- an effect with neither is its own group (always adds).

Exceptions: ability *penalties* from the same spell or item **add up** instead of taking the
largest; for attack and damage, bonuses whose modifier type is on-hand/off-hand are added
directly without grouping. The walker keeps up to 36 groups per sign. (high)

Damage bonuses store a row of iprp_damagecost.2da in int0: rows below 6 are flat amounts, higher
rows roll `NumDice`d`Die` (maximised when the caller asks for maximum damage); the row's `Rank`
decides which of two same-source dice bonuses is "largest". (med)

**AC** is not summed this way. The AC handlers write per-type fields in the stats when the effect
is unconditional (any race, no alignment restriction): dodge bonuses **add** into +0x100 (penalties
+0x101); natural +0xfe, armour enchantment +0xf8, shield enchantment +0xfc and deflection +0xfa
keep only the **highest** (penalties +0xff, +0xf9, +0xfd, +0xfb). Replacing a lower bonus sends
feedback 0xbd–0xc0. On removal the highest remaining value is recomputed by walking the list; dodge
just subtracts. Conditional AC effects (versus race/alignment) are evaluated by the attack code.
AC decreases are refused for plot creatures and by immunity 23. (high)

**Movement speed.** The creature's speed factor (+0xa08) is read through
`GetMovementRateFactor` (`0x004ec370`), clamped to [0.125, 1.5]. Applying an increase first turns
int0 below 100 into 100 + int0 (so "50" means 150 %), then multiplies the factor by int0/100; a
decrease (refused by immunity 24, plot, or int0 ≥ 100) multiplies by 1 − int0/100. Removal
recomputes from scratch as 1 + Σ(increase int0)/100 − Σ(decrease int0)/100 over the remaining
effects — note this mixes the two conventions (an increase stored as 150 adds 1.5); with the clamp
the visible result for one haste is still 1.5. Reproduce as observed. (high)

**Force resistance.** FR = stats +0x11f (bonus) − +0x120 (penalty), not below 0
(`GetForceResistance` `0x005a5a60`). An FR increase sets the bonus to max(current, int0) with int0
capped at 128; a decrease sets the penalty likewise (immunity 26); removal recomputes. So FR does
not stack: the highest wins. (high)

**Temporary hit points** add to object +0xe4, which `GetCurrentHitPoints` adds to current HP.
**Temporary Force points** add to stats +0x126. (high)

### 1.8 Immunity

`CSWSCreatureStats::GetEffectImmunity(type, versus)` (`0x005a6960`) walks the IMMUNITY effects
(0x16) and answers yes if one has int0 = 0 (all) or the asked `IMMUNITY_TYPE_*`, int1 = any race or
the versus creature's race, and int2 = 0 or the versus creature's alignment group (good-evil < 41
→ 3, 41–59 → 1, ≥ 60 → 2). Handlers ask it with the creator as versus. (high)

`GetIsImmuneToEffect(effect)` (`0x005a6a90`) is the table-driven variant used by SETSTATE: it maps
the effect to a gameeffects.2da row (`0x005a5aa0`), and for each of the 32 immunity columns set in
that row asks `GetEffectImmunity`; the first hit sends the matching "immune" feedback (ids
0x7d–0x92) to both sides and returns 1. It recurses into link children. (high)

Plot creatures (object +0xf8) refuse ability, attack, AC and movement decreases, entangle,
knockdown and poison outright; the DEATH effect does nothing to them. (high)

### 1.9 Removal, death, healing, poison

- **RemoveEffect (script)** (`0x0054ae40`): marks every listed effect with that id as not exposed
  and queues event 14 (REMOVE_EFFECT) for the target; the event handler calls
  `RemoveEffectById` (`0x004d06c0`). The removal therefore happens on the next AI update, not
  inside the script. (high)
- **RemoveEffectById** removes every effect with the 64-bit id: for each, the remove handler, then
  unlink from the list, creature hooks (slots 54 and 55), free, and drop the target from the
  creator's affected list. `RemoveEffect(effect)` (`0x004d05c0`) does the same for one effect.
  (high)
- **ClearAllEffects** (`0x00545d40` → `RemoveAllEffects` `0x004d0940`) on `OBJECT_SELF`: removes
  every effect except duration types 3 (equipped) and 4 (innate) and SETSTATE_INTERNAL, then makes
  the object commandable. Removing a party member (`0x00565560`) and surrendering (`0x00518990`)
  call it too. (high)
- **Runaway guard**: `RunActions` warns above 500 effects and above 1000 removes all temporary and
  permanent ones (`0x004d0870`). (high)
- **Item effects** (duration type 3, creator = item) are removed by creator when the item is
  unequipped (`RemoveEffectsByCreator` `0x004d0820`). (med)
- **DEATH (0x13)** (`0x004e0ac0`): nothing for plot objects; Min1HP objects go to 1 HP. For a
  creature: refused with feedback 0x7f if the effect is magical, has a spell id and the creature
  has death immunity (32); otherwise award kill XP (4.2), end the combat round, run OnDeath
  (+0x280), play a random death animation, clear the AI state mask, set HP to −11 if higher, and
  remove **every effect except** duration types 3/4 and those listed in removefxondeath.2da
  (EffectType 62 disguise, 21 beam; for the beam row, also visual effects whose vfx is a beam;
  check `0x004df420`). Then the body fades after appearance.2da `DestroyObjectDelay` (default 3 s)
  — the rest belongs to [combat.md](combat.md). Placeables and doors play their death animation,
  get an ON_DEATH script event (10) at once and are destroyed (event 11) 2 s later. (high for the
  order, med for the 2DA reading)
- **HEAL (0x27)** (`0x004e0750`): int1 = 0x36 heals Force points instead (pool clamped to max FP,
  feedback 0xe4). Otherwise: refused for dead or dying creatures, adds int0 up to max HP (with
  bonus), feedback 0x97 to target and healer, and removes the target's temporary 0x54 effects
  (low: unknown type). (med)
- **POISON (0x23)** (`0x004db320`): refused for plot, dead or immune (2) creatures; stamps the
  start time and rolls a **Fortitude save, type 12 (poison), DC = poison.2da `DC_SAVE`**. On a
  failure: feedback naming the poison, a poisoned visual (vfx 1003) and status flag, the first
  tick, and the effect becomes temporary with Duration = `DURATION` s and tick period `PERIOD` s
  (int5, int6); a success drops it. Ticks damage HP/FP/abilities per the `dam_*` columns. (high
  for the save and columns, med for the tick contents)

### 1.10 Crowd control

**SETSTATE (0x08)** carries the state in int0 and a cutscene flag in int1. Apply
(`0x004e1c20`), in order (high unless marked):

1. If not cutscene: `GetIsImmuneToEffect` (gameeffects.2da rows STUN, SLEEP, CONFUSED, HORRIFIED,
   …) → refuse.
2. Per-state immunity, refused with an "immune" feedback to both sides (med for the exact
   return path):

   | State | Effect | Immune if | Feedback |
   |---|---|---|---|
   | 1 | confused (`EffectConfused`) | immunity 16 | 0x89 |
   | 2 | frightened (`EffectFrightened`) | immunity 4 (fear) | 0x80 |
   | 3 | droid stun (`EffectDroidStun`) | — | — |
   | 4 | stunned (`EffectStunned`) | not cutscene and (immunity 12, or feat 99 Force Immunity: Stun, or feat 100 Force Immunity: Paralysis) | 0x8a |
   | 5 | paralyzed (`EffectParalyze`) | not cutscene and (immunity 6, or feat 100) | 0x82 |
   | 6 | sleep (`EffectSleep`) | immunity 13 | 0x87 |
   | 7 | choke (`EffectChoke`) | — | — |
   | 8 | horrified (`EffectHorrified`) | not cutscene and feat 98 Force Immunity: Fear | 0xe3 |
   | 10 | whirlwind (`EffectWhirlWind`) | — | — |
3. Add a SET_AI_STATE child clearing AI bit 0x100.
4. If the state number is higher than the creature's current state (+0x8ed): store it, remove any
   SETSTATE_INTERNAL, and apply a new innate SETSTATE_INTERNAL (0x09) carrying the state. So when
   several states overlap, **the highest-numbered one is active**.

**SETSTATE_INTERNAL (0x09)** (`0x004da330`): for every state but 9, makes the creature briefly
commandable, `ClearAllActions`, aborts its combat round (`0x004d3770`), and leaves it
**uncommandable** (+0xe8 = 0: scripts and the player cannot queue actions). Then per state it adds
children that share the parent's id and expiry (high):

| State | Children |
|---|---|
| 2 frightened | −2 to all saves |
| 3 droid stun | visual 1007, −2 to all saves, AI mask −move |
| 4 stunned | AI mask −move, visual 2002 |
| 5 paralyzed | AI mask −move −attack −bit 8 (0xfff1) |
| 6 sleep | AI mask 0xfea1 (−move −attack −bits 8, 0x10, 0x40, 0x100) |
| 7 choke, 8 horrified, 9, 10 whirlwind | AI mask −move |
| 1 confused | nothing beyond the action wipe (the AI scripts make confused creatures wander) |

Then `UpdateStateAnimation` (`0x004f28d0`) starts the looping state animation (sleep, stun,
choke, horror, whirlwind, paralysis, droid stun each have their own). (med for the animation ids)

**AI state mask** (creature +0x9f0, 16 bits, 0xffff when free; AND of all SET_AI_STATE int0s):
bit 2 *can move* (checked by move, jump and follow actions), bits 4 and 0x80 *can attack* (checked
by `AIActionAttackObject`), bit 8 used by a skill/feat check (`0x005aaa30`), bit 0x40 sent to the
client, bit 0x100 cleared by every SETSTATE (meaning not identified). Death sets the mask to 0;
RESURRECTION restores 0xffff. (med; bit 2 and 4/0x80 high)

**Removal.** SETSTATE remove (`0x004e22f0`): commandable again, current state 0, remove every
SETSTATE_INTERNAL, and if another SETSTATE is still on the creature re-create a SETSTATE_INTERNAL
(permanent) for the highest remaining state (and stay uncommandable). SETSTATE_INTERNAL remove
(`0x004da870`): for states 1 and 3–10 run the creature's **OnEndCombatRound** script (so the AI
picks up again), refresh the animation and, unless the creature is a party member down at 0 HP,
reset its stance. (high)

**Others** (high unless marked):
- **ENTANGLE (0x12)**: immunity 10; not for plot. Clears actions and adds −2 attack (misc), −4
  DEX and AI mask −move. Casting a spell while entangled is interrupted (3.3).
- **KNOCKDOWN (0x14)**: immunity 28; not for plot or dead. Sets combat round timers, adds an
  AI-state child (bit 0x100) lasting the duration + 1.5 s, makes the creature uncommandable and
  plays the knockdown animation (a different one when hit from behind, facing dot < 0.707). (med
  for the animation choice)
- **SLOW** is refused by immunity 9; **DEAF** by 8; **SILENCE** by 11; **CURSE** by 17.
- **Force push / whirlwind / choke / horror / stun / stasis** are scripted as SETSTATE, FORCE_PUSH
  and DAMAGE effects plus saves in `k_sp1_generic` (3.4).

### 1.11 Visual effects, icons, alignment mastery

- **VISUALEFFECT (0x1e)** (`0x004daa40`): int0 visualeffects.2da row, obj0 optional source. If the
  effect has a duration, is not a miss, and the row's `Type_FD` is not `F`
  (fire-and-forget), it is attached to the object as a persistent visual (`0x004cf390`) and kept
  until removed (`0x004dadc0`). Otherwise a one-shot visual is sent to the client when the player
  creature is within 252 m. Miss visuals are offset to a point beside the target. (high)
- **ICON (0x43)** (`0x004e4790`): adds effecticon.2da row int0 (`IconResRef`, `Priority`, `Good`)
  to the creature's icon list (+0x8f4/+0x8f8) unless already there; removal takes it out. The HUD
  draws this list. `SetEffectIcon(e, icon)` is just `Link(Icon(icon), e)`, so the icon lives
  exactly as long as the effect. Instant effects get no icon. (high)
- **Alignment mastery**: `UpdateAlignmentMastery` (`0x00501d90`) applies an innate
  LIGHT_SIDE_MASTERY (0x6c) at good-evil 100 and DARK_SIDE_MASTERY (0x6d) at 0, removing the other.
  For the player character's Jedi class: light — Guardian +3 STR, Consular +3 CHA (FP pool
  adjusted), Sentinel +3 CON (HP adjusted), icon row 60 (MAX_GOOD_ICON); dark — Consular +50
  Force points, Guardian two DAMAGE_INCREASE children, Sentinel an IMMUNITY child, icon row 61.
  (high for the trigger and light side, med for the dark side contents)

### 1.12 Item properties

Equipping an item runs each of its properties through the item property handler
(`CServerAIMaster`+0x5c, `OnItemPropertyApplied` `0x004e5410`, 0x3c types), which builds ordinary
effects with duration type 3 and the item as creator, and applies them. That is why item bonuses
obey the per-item "largest wins" rule of 1.7 and survive ClearAllEffects and death. Property
types are in itempropdef.2da; the per-property handlers (`0x004e5490`…`0x004ea800`) were not
read one by one. (high for the mechanism)

## 2. Saving throws

### 2.1 The value

| Save | Function | Formula | Conf. |
|---|---|---|---|
| Fortitude | `GetFortSavingThrow(bExcludeEffects)` `0x005ab810` | CON mod (stats +0xee) + class base + FortBonus (+0x1a0) + effects | high |
| Reflex | `0x005ab8f0` | DEX mod (+0xec; only if negative while helpless) + class base + RefBonus (+0x1a2) + effects | high |
| Will | `0x005ab880` | WIS mod (+0xf2) + class base + WillBonus (+0x1a1) + effects | high |

**Class base** (`GetBaseFortSavingThrow` `0x005aa1b0`, reflex `0x005aa430`, will `0x005aa2f0`):
the sum over the creature's class slots of that class's table value at its class level — so
multiclass saves simply add — plus the Conditioning feats: Master Conditioning (22) +3, else
Improved Conditioning (21) +2, else Conditioning (13) +1. Class tables are the
`savingthrowtable` 2DAs (`CLS_ST_*`) loaded by `CSWClass::LoadSavingThrowTable` (`0x005bd480`);
the fortitude byte table sits at class +0x57 for levels 1–60 (`0x005bccd0`). (high for fortitude,
med that reflex/will mirror it)

**Helpless** (`GetIsHelpless` `0x005b4880`): any SETSTATE active, or a party member down at 0 HP.
(med)

Effects are category 3 of `GetTotalEffectBonus` (1.7), filtered by save and save type, ±20.
`GetFortitudeSavingThrow` & co. (routines 491–493) return the value without effects for creatures,
and the door/placeable `Fort`/`Ref`/`Will` bytes for those objects. (high)

### 2.2 The roll

`CSWSCreature::SavingThrowRoll(save, DC, saveType, versus, …)` (`0x005b92b0`), used by
`FortitudeSave`/`ReflexSave`/`WillSave` (`0x005421e0`, routines 108–110), poison, disease,
sanctuary, `GetReflexAdjustedDamage` and the combat code; the script routines return 0 for non-creatures:
(high)

```
base   = Get<Save>SavingThrow(bExcludeEffects = 1)
bonus  = min(GetTotalEffectBonus(3, versus, save, saveType), 20)
roll   = d20
total  = roll + bonus + base
result = 1 if total >= DC else 0                    # no automatic success on 20 or failure on 1
if immune for saveType: result = 2
```

Immunity by save type: mind-affecting (10) → immunity 1, poison (12) → 2, disease (5) → 3, fear
(8) → 4, trap (14) → 5, death (4) → immunity 32 when the current spell is a Force power (spells.2da
UserType 1 or 2). The routine returns 0 failure, 1 success, 2 immune. A feedback message with
save, type, roll, bonus, base, DC goes to the target and the versus creature (or is attached to the
attacker's current attack record when deferred). (high; the immunity list med)

There are no evasion-like feats in the engine's save code; Jedi defence feats act on deflection
in combat. (med)

## 3. Force powers

### 3.1 spells.2da as the engine reads it

`CSWSpellArray::Load` (`0x0059ba20`) builds 0x198-byte `CSWSpell` records (`GetSpell`
`0x0059b6d0`, array at `g_pRules`+0x8c). Columns that drive the rules (high):

| Column | Offset | Use |
|---|---|---|
| `forcepoints` | +0x14e (byte) | base FP cost |
| `goodevil` | +0x14f | `G` light power, `E` dark power, `-` universal |
| `guardian`, `consular`, `sentinel`, `inate` | +0x3c..+0x3f | class level at which the power may be chosen; `inate` also gives the caster level of non-creature casters (2 × inate − 1, at least 10) |
| `usertype` | +0x140 | 1 Force power, 2 special ability, −2 disabled; only 1 is subject to Force resistance |
| `prerequisites` | parsed `_`-separated list of spell ids | the upgrade chain (3.7) |
| `masterspell` | parsed | — |
| `category`, `maxcr`, `range`, `targettype`, `itemtargeting` | +0x124, +0x128, +0x20, +0x30, +0x194 | AI and targeting |
| `impactscript` | +0x34 | run on the caster at impact |
| `conjtime`, `casttime`, `catchtime` | +0x40, +0xa8, +0xec (ms) | phase lengths of the cast action |
| `conjanim`, `castanim`, `catchanim`, visuals, sounds, projectile columns | +0x44… | presentation |
| `forcehostile` / `forcefriendly` / `forcepassive` + `forcepriority` | +0x130 | AI category |
| `hostilesetting` | +0x148 | whether casting is hostile |
| `featid` | +0x14c | feat that grants it (special abilities) |
| `exclusion` | +0x188 | — |
| `forbiditemmask` / `requireitemmask` | +0x18c / +0x190 | equipment restrictions (3.3) |

### 3.2 Force point cost

`CSWSpell::GetForcePointCost(goodEvil, bPlayerControlled)` (`0x0059b8a0`):

```
cost = forcepoints
if caster is player-controlled (creature +0xa88):
    row  = goodEvil / 10                         # 0..10
    mult = forceadjust.2da[row].goodcost  if goodevil == 'G'
           forceadjust.2da[row].evilcost  if goodevil == 'E'
           1.0                            otherwise
    cost = trunc(cost * mult)
```

forceadjust.2da: row 0 (most evil) goodcost 1.75 / evilcost 0.5 … row 5 1.0 / 1.0 … row 10
(most good) 0.5 / 1.75. Non-party casters always pay the base cost. No feat or armour changes the
cost. (high)

`HasEnoughForcePoints(spell, classSlot)` (`0x005a5550`): the class slot must exist and current +
temporary FP ≥ cost. `SpendForcePoints(spell)` (`0x005a55c0`) takes the cost from the temporary
pool first (stats +0x126), the rest from the current pool (+0x124), never below 0. (high)

### 3.3 The CASTSPELL action

`CSWSCreature::AIActionCastSpell` (`0x00514af0`, action 0xf; queueing is in
[actions.md](actions.md)): (med for the phase details, high for the checks)

- Aborts if the caster is dead or dying.
- **Equipment check**: the caster's equipped-item mask (`GetEquippedItemTypeMask` `0x004efa80`:
  baseitems.2da `itemtype` 31–36, the six armour classes, set bits 0x01–0x20; 39–41, the
  lightsabers, set 0x40) must not intersect `forbiditemmask` and must contain `requireitemmask`.
  22 spells.2da rows forbid 0x3f, so **these cannot be cast in armour**: the self buffs (speed
  burst, knight speed, speed mastery, the three valors, Force armour/aura/shield, resist Force,
  Force immunity), shock, lightning, storm, drain life, death field, plague, breach, suppress
  Force, stasis field and the two disabled jump rows. Push, stun, choke, wound, heal, throw and
  the rest are allowed; Jedi robes and clothing are itemtype 37/38 and never block. Force jump
  and lightsaber throw require 0x40, a lightsaber. A feat
  parameter, if given, must be a known feat.
- Faces the target, starts a combat round sized conj + cast + catch time.
- **Payment at conjuration start** (first frame of the action, once): `PayForcePowerCost`
  (`0x004eddd0`) spends the FP (not when cast from class slot 0xfe, i.e. item/feat talents) and
  marks the known spell. Failing to pay aborts. If the caster has an ENTANGLE effect, the cast is
  interrupted (feedback 0x41).
- At the cast moment the impact is scheduled: the projectile/visual broadcast (`0x004cdd30`) and
  `0x004cdf50`, which leads to event 8 (SPELL_IMPACT) on the caster.
- At the end of catch time: idle animation, uses-per-day of the feat decremented
  (`0x005a6720`).

There is no concentration or arcane-failure roll. FP are lost even if the power then fails a
resistance check. (med)

### 3.4 The impact script

The SPELL_IMPACT event (8; 0x13 for item on-hit spells) is handled by the caster
(`CSWSCreature::EventHandler` `0x004fece0`): it stores the spell id (+0x1c0, `GetSpellId`), the
target object (+0x1bc, `GetSpellTargetObject`) and location, sets the current spell id for
`SetCreator` (slot 47), for item spells sets the caster level override (+0x964 = 1, +0x968 =
payload caster level), runs the `impactscript` with **OBJECT_SELF = the caster**, then clears
them. (high)

All shipped powers use `k_sp1_generic`, which builds the effects itself: it calls
`EventSpellCastAt` + `SignalEvent`, `ResistForce`, the save routines with a DC obtained from
`GetSpellSaveDC` (a one-line helper in the script), `GetHitDice` for scaling, and applies linked
effects with icons. (high, from the disassembled script)

### 3.5 DC and caster level

- `GetSpellSaveDC` (`0x0053d320`) → `GetForcePowerDC` (`0x004ef6e0`): **5 + total character level
  + WIS modifier + CHA modifier**, plus the best of Force Focus (88) +1, Advanced (89) +2, Mastery
  (90) +4. For an area of effect, its creator's DC, or the DC stored on the AoE (+0x258); 14 when
  no caster. (high)
- `GetCasterLevel` (`0x00536ad0`): for creatures the item-cast override if set, else the level of
  the casting class slot (+0x1d4), else total level; for placeables and AoEs 2 × `inate` − 1,
  at least 10. (med; the decompile is tangled)

### 3.6 Force resistance and immunity

`ResistForce(source, target)` (`0x00541cc0`), used by `k_sp1_generic`: caster level = the
override, or total level for creatures, the AoE's stored level (+0x25c), or 2 × `inate` − 1. For a
creature target: spell immunity (SPELL_IMMUNITY effects, `0x004d13a0`) or the second check
`0x004ccfc0` first; otherwise, only for UserType 1 powers, **resisted if d20 + caster level < FR**
(FR from 1.7). Feedback 10/0x11 to both. Returns 1 when resisted or immune, else 0. (med)

FP damage and healing effects work on the pool "current + temporary": DAMAGE_FORCE_POINTS sets
current = max(0, current + temporary − int0); HEAL_FORCE_POINTS sets current = min(max FP,
current + temporary + int0); FORCE_DRAIN is the damage formula. The temporary pool is left as it
was — a quirk only visible when both are non-zero. (high as read)

### 3.7 Upgrade chains

Power lines are linked only through `prerequisites`: Force Whirlwind requires 23 (Force Push),
Force Wave 23_27 (Push and Whirlwind), Heal requires Cure, Kill requires Choke (50) and 9, and so
on. Knowing the higher power does not remove the lower one; the level-up code checks
prerequisites when offering powers (6). (high for the data, med for the use)

### 3.8 Force points: maximum and regeneration

`CSWSCreature::GetMaxForcePoints` (`0x004fd490`), 0 for droids (race 5): (high)

- **The player character** (IsPC and the party is not controlling an NPC, `PT_CONTROLLED_NPC` =
  −1): if the current class is a Force class, Σ over the level-up history of
  max(1, `forcedie` + WIS mod + CHA mod) for levels whose record has a Force die (classes.2da
  `forcedie`: Guardian 4, Consular 8, Sentinel 6).
- **Everyone else**: base max FP (stats +0x122, from the template, grown by level-ups) + total
  level × (WIS mod + CHA mod).
- Both: +40 with feat 116 (Force Sensitive); +50 if a class slot is Jedi Consular (4) and the
  creature has feat 109 (Master Sense) (med on the last condition).

**Regeneration** (in `CSWSCreature::AIUpdate`, for alive, not-dying, player-controlled party
members only): row = regeneration.2da 0 (InCombat) while the combat flag (+0x4e0) is set, else 1
(OutOfCombat). Per update: HP gain = `healthregen` % × max HP × dt(ms)/1000 and FP gain =
`forceregen` % × (max FP + temporary FP) × dt/1000, each at least 0.0001, accumulated in fractional
stores (stats +0x1ac / +0x1b0) and added whole, clamped to the maximum. Shipped values: health 0/0,
force 0/1 — **1 % of the pool per second out of combat, nothing in combat, no HP regeneration**.
(high)

### 3.9 Alignment

Casting a dark or light power **does not change alignment** in the engine (the cast path only
spends FP), and `k_sp1_generic` never calls `AdjustAlignment`; alignment moves only through
scripts (`AdjustAlignment`, 55 shipped scripts, mostly dialogue). Alignment affects powers only
through the FP cost (3.2) and the mastery bonuses (1.11). (high)

## 4. Experience and level-up

### 4.1 Thresholds and cap

exptable.2da column `XP` rows 0–20 are copied into `g_pRules`+0x38 (`CSWRules::CSWRules`
`0x00552c50`); entry *L* is the XP needed to reach level *L* + 1 (row 1 = 1000 for level 2 … row
19 = 190000 for level 20, row 20 = 0xFFFFFFFF). `CanLevelUp` (`0x005a6810`): total level < the
server's level cap (`CServerExoAppInternal`+0x10004 → +0x94) and XP ≥ entry[level], and not dead or
dying. So the cap is 20 (or lower if the server cap is lower). (high)

### 4.2 Awarding XP

- **The party pool.** `CSWPartyTable::AddExperience(xp, bFeedback)` (`0x005653a0`): adds to
  `PT_XP_POOL` (+0xf8), then gives `CSWSCreature::AddExperience` to every NPC in the party table
  and to the player creature; with the auto-level-up client option (options+8 bit 1) it
  auto-levels anyone who can (4.4). Feedback 0x8f "experience gained" when asked. (high)
- **Per creature.** `CSWSCreature::AddExperience` (`0x004ef930`): xp × npc.2da `PercentXP` of the
  creature's NPC row (80 for every companion; the player is not an NPC row → 100 %) × row 9
  (`GAME_XP_General`, 100) / 100, **rounded up**, then `CSWSCreatureStats::AddExperience`
  (`0x005af6a0`) → `SetExperience` (`0x005af480`). (high)
- **GiveXPToCreature** (`0x0053e750`): the target only matters for the feedback; the amount goes
  to the whole party through `AddExperience(xp, 1)`. (high)
- **Plot XP**: `GivePlotXP(plot, percent)` (`0x00566600`): ceil(plot.2da `XP` of the row whose label
  is *plot* × percent / 100) to the party. `PlotXPPercentage` on dialogue nodes uses the same
  path ([dialogue.md](dialogue.md)). (high)
- **Kill XP** (`AwardKillXP` `0x004fb1e0`, from the DEATH effect): nothing if the victim is in the
  party or dying, or if the reputation between its faction and faction 0 (the player's) is above
  10, i.e. it was not hostile (med for the faction reading).
  Otherwise `GetKillXPValue` (`0x004f19e0`): player level *L* from the player's XP and the table,
  value = xptable.2da[row *L* − 1][column `c<CR>`] with CR = truncated `ChallengeRating`, ×
  npc.2da row 9 `PercentXP` / 100; if row 10 (`PER_NPC_Bonus`) is > 0 it is multiplied by
  (1 + bonus/100 × party size) (0 in the shipped table). The result is rounded up and added to the
  party **without** the gain message; the killer gets a kill feedback. (high)
- **Mod_XPScale** is read from and written to the module IFO (+0x1a6, default 10) but nothing else
  reads it. (med)
- Stealth XP (`AwardStealthXP` etc.) is a script-side system. (low, not read)

### 4.3 The level-up record and `LevelUp`

A level is described by a 0x30-byte record (`CSWSLevelStats`, ctor `0x005cb1b0`; the history list
is stats +0x28, `LvlStatList`). `CSWSCreatureStats::ApplyLevelUp(record)` (`0x005af950`) checks
`CanLevelUp`, signals script event 37 PLAYER_LEVEL_UP to the module for PCs, then calls
`LevelUp(record, 1)` (`0x005aabf0`) and recomputes derived stats. `LevelUp`: (high)

1. Append the record to the history.
2. Find the class slot of the record's class and add 1 to its level; if none, open a new slot at
   level 1 (**multiclassing** is just a record of another class; at most two slots exist).
3. Max HP (creature +0xe0) += record HP; base max FP (stats +0x122) += record FP.
4. Ability increase (record +0x2a, 0–5): +1 to that score and recompute its modifier as
   (score − 10) / 2 rounded down.
5. Skill ranks += the record's per-skill points; unspent skill points (stats +0x164) = record's
   remainder.
6. Add the record's feats; for PCs in a Force class, remove and add the record's powers in the
   class slot's known list.
7. Current HP = max HP (**a level-up heals fully**); current FP += the change in max FP.

### 4.4 Automatic level-up (NPCs, and everyone with the option on)

`CSWSCreatureStats::AutoLevelUp` (`0x005b27e0`) loops while XP ≥ the next threshold, always in
the **last** class slot, building and applying one record per level: (high unless marked)

- New class level *n*. Every 4th level (*n* % 4 = 0) an ability point in the class's preferred
  ability (class +0x17a).
- HP = classes.2da `hitdie` (the maximum, no roll); FP = `forcedie`.
- Skill points = stored remainder + (level 1: max(1, `skillpointbase`/2 + INT mod) × 4; later:
  max(1, (INT mod + `skillpointbase`) / 2)). They are spent along the class's skill priority list
  (`0x005be430`) up to rank max (level + 3 for class skills, half for cross-class, which cost 2
  points per rank), for the PC and for skills flagged usable by everyone (droids need another
  flag).
- Feats the class grants at level *n* are added (`0x005be310`); then as many feats as featgain.2da
  allows (`<class>_REG` general, `<class>_BON` bonus, `GetNumFeatsToGain` `0x005a6f40`) are picked
  along the class's feat priority list among those with feat.2da `mincharlevel` ≤ *n* that pass
  `CanSelectFeat` (6).
- For Force classes, `GetNumForcePowersToGain` (`0x005a59d0`) powers — 2 at the first Jedi level,
  then 1 (med: classpowergain.2da, which gives Consulars 2 at level 5, is loaded by
  `CSWClass::LoadSpellGainTable` `0x005bd900` but this path does not seem to read it) — picked
  along the light or dark priority list depending on alignment (evil = good-evil < 41) and
  validated by `CanLearnForcePower` (`0x005ac8f0`, low).
- `ApplyLevelUp`; feedback to the client.

The player's own level-up goes through the level-up GUI ([gui.md](gui.md)), which builds the same
record from the player's choices and ends in `ApplyLevelUp`. There is no engine "autobalance" of
companions to the player's level beyond companions earning the same XP (at 80 %) and leveling;
joining NPCs carry `JoiningXP` ([objects.md](objects.md)). (med)

### 4.5 Hit points

`CSWSCreature::GetMaxHitPoints` (`0x004ed310`, slot 38): (high)

- **The player character** (same PC test as 3.8): Σ over the level history of max(1, record HP +
  CON mod), + per level 2 with Master Toughness (124) or else 1 with Toughness (84) when
  bonuses are included. Improved Toughness (123) is not tested here, so it adds nothing beyond
  Toughness in this function (med). CON changes therefore re-price every level.
- **Everyone else**: base max HP (+0xe0) + level × (CON mod + Toughness bonus + 2 with Wookiee
  Endurance (95)), but at least 1 HP per level.

## 5. Skills in play

### 5.1 Rank

`CSWSCreatureStats::GetSkillRank(skill, versus, bBaseOnly)` (`0x005aa570`): (high)

```
rank = ranks[skill]                                  # stats +0x168
if bBaseOnly: return rank
if skill not usable untrained (skills.2da flag) and rank == 0: return 0
rank += GetTotalEffectBonus(5, versus, skill)        # ±30
rank += key ability mod (keyability: STR, DEX*, CON, INT, WIS, CHA)
if key ability is STR or DEX and the creature is blind: rank -= 4
if skills.2da armorcheckpenalty: rank += stats +0x16c + +0x16d   # armour/shield penalties
rank += best tier of the skill's feat line
clamp to -127..127
```

\* DEX counts only when negative while helpless. Feat lines (best tier only): Computer Use, Repair,
Security — Gear Head (12) +1, Adept (119) +2, Master (120) +3; Demolitions, Stealth — Cautious (7)
+1, Improved (117) +2, Master (118) +3; Awareness, Persuade, Treat Injury — Empathy (10) +1,
Improved (121) +2, Master (122) +3. Computer Use also adds the bonus stored on the placeable the
creature is using (+0x43c, low). `GetSkillRank` (routine 315) returns this with no versus, −1 for
non-creatures. (high)

### 5.2 Where the engine rolls skills

Out-of-combat checks **take 20** (the roll is fixed at 20), in combat (+0x4e0 set) they roll d20.
(high)

| Skill | Where | Rule | Conf. |
|---|---|---|---|
| Security | OPENLOCK `0x0057d9d0` | Security + security-spike property bonus + (20 or d20) ≥ the lock's `OpenLockDC` (min 1) → unlock, then a USEOBJECT action is queued | high |
| Demolitions | DISABLETRAP `0x00519570`, RECOVERTRAP `0x00518c40`, FLAGTRAP `0x0050e400`, EXAMINETRAP `0x0050e900` | Demolitions + (20 or d20) ≥ the trap's `DisarmDC` (min 1); a DC above 35 is impossible; the setter of a trap, or a party member disarming a party trap, succeeds automatically | high |
| Demolitions | SETTRAP `0x00519e30` | Demolitions (+2 if base ranks > 4) + (20 or d20) ≥ traps.2da `SetDC` (min 1) | high |
| Awareness | trap detection `DoTrapDetection` `0x004fa390` | every 3 s within 3 m, or every 0.1 s within 20 m in detect mode, each non-friendly armed trap of another faction: Awareness + d10 (d10 + 10 in detect mode) ≥ the trap's `TrapDetectDC`, or the trap is flagged always detected; a party member's success marks the trap for the whole party | med |
| Stealth vs Awareness | `GetCanSeeStealthed` `0x004fb4b0` | deterministic, no die: observer score = distance/line term − target Stealth − target stealth bonus + observer Awareness (full when searching or standing still, else half) + area modifier + observer bonus − 10 while the observer is in combat ± 5 by both animations + size modifier (−8/−4/+4/+8); seen if ≥ 1 | low (terms med) |
| Treat Injury | HEAL action `0x00517a60` | Treat Injury + (20 or d20) for medpac/antidote use; poison or disease on the target are handled first; healing a creature at full HP fails with feedback 0x38 | med |
| Computer Use, Repair, Persuade | — | used only by dialogue scripts (`GetSkillRank`, 144 shipped scripts) and the computer/repair GUIs; spike consumption is scripted | med |

## 6. Feat and power prerequisites

feat.2da is loaded into 0x48-byte `CSWFeat` rows (`g_pRules`+0x90, count +0xa4, `GetFeat`
`0x00550c00`, valid only when flag 0x10 at +0x28 is set). `MeetsFeatRequirements(feat, pending)`
(`0x005afb00`), used by `CanSelectFeat` (`0x005b2530`) for both the GUI and auto-level-up: (high)

1. The last class's feat table may name a level for the feat (`0x005be220`); total level must reach
   it.
2. `minspelllvl` (+0x32): some Force class slot must have that power level available
   (`0x005bcd60`).
3. `minattackbonus` (+0x2c) ≤ base attack bonus (`0x005a60d0`).
4. `minstr`, `mindex`, `minint`, `minwis` (+0x2e..+0x31) ≤ the **base** scores (no effects).
5. Prerequisite feats (`prereqfeat1/2`, the `orreqfeat0..4` list), counting feats pending in the
   same level-up (`0x005a7230`, med for the exact OR logic).
6. A required skill (+0x46, `reqskill`) must have ranks (`0x005af880`, med).

`CanSelectFeat` then requires that the feat is not known or pending and that a general or bonus
slot is left: the class feat table says whether the feat is a general choice, a class bonus
choice or both (`GetFeatSelectableAs` `0x005a6fe0`), and the pending choices are matched to slots
greedily. (med)

Class tables: `CSWClass::LoadFeatTable` (`0x005bd0f0`, cls_feat_*: granted level and selectability
per feat), `LoadFeatGain` (`0x005bcf70`, featgain.2da `_REG`/`_BON` for levels 1–20 into class
+0x150/+0x13c), `LoadSkillsTable` (`0x005bd6c0`, class skills), `LoadSpellGainTable`
(`0x005bd900`), `LoadSavingThrowTable` (`0x005bd480`), `LoadAttackBonusTable` (`0x005bcda0`). (high
for the loaders, from their log strings)

Power prerequisites: a power is offered when the class's spells.2da level column (`guardian`,
`consular`, `sentinel`) ≤ class level and its `prerequisites` are known (`CanLearnForcePower`,
low). The ability point buy of character creation is in the GUI, not the rules code
([gui.md](gui.md)). (med)

## 7. Open questions

- Internal types without constructors (0x2b, 0x42, 0x44, 0x45, 0x4d–0x51, 0x53, 0x54,
  0x56–0x59, 0x5e, 0x61) and the exact behaviour of curse, silence, deaf, dispel, sanctuary,
  timestop, force push, lightsaber throw, force jump, force shield, disease and the per-property
  item handlers.
- AI state bits 8, 0x10, 0x40 and 0x100: what each one gates.
- `GetFirstEffect`/`GetNextEffect`: whether unexposed engine sub-effects are hidden from scripts
  (NWN hides them).
- `SkipOnLoad` and object +0x1ec: the exact reload rule.
- `ResistForce` return path for immunity (1 or 2) and the second check `0x004ccfc0`.
- The stealth/awareness formula: which animations count as moving, the distance term, and how
  often it is evaluated (the caller is in the perception code, [movement.md](movement.md)).
- Whether the GUI level-up uses classpowergain.2da while `AutoLevelUp` gives 2-then-1 powers.
- `CanLearnForcePower` (`0x005ac8f0`) and the OR-prerequisite logic (`0x005a7230`) were not read.
- Treat Injury's effect on the healed amount (medpac items carry their own heal properties).
- Resting (the party rest GUI) and how it removes effects; not found in the rules code.
- Feat 109 + Consular +50 FP: confirm the helper `0x004f7880` is "has feat".
