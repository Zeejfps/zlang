# The d20 rules in swkotor.exe: effects, saves, Force powers, XP, skills, feats

What the engine does with the rules that sit around the attack roll: the effect system (the
object every buff, debuff, crowd-control and Force power result is made of), saving throws, Force
point costs and DCs, experience and level-up, the skills the engine itself rolls, and feat and
power prerequisites. Addresses are for the Steam `swkotor.exe` after SteamStub removal (see
[README.md](README.md)); names are ours, in the Aurora/NWN vocabulary, and are proposed in
`kotor/re/proposals/rules.tsv` (git-ignored, merged into [names.tsv](names.tsv) by the lead).
Every claim ends with a confidence: **high** (read in the code), **med** (role clear, a detail
inferred), **low** (plausible). The whole page was rechecked claim by claim on 2026-10-07 against
the exports rebuilt after the noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that
says "needs a runtime check" rests on static reading alone and is surprising enough to test before
relying on it.

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
| +0x20 | `IsExposed` | the constructor's `bCreateNewId`: 1 for effects made by script constructors, 0 for sub-effects built with `CGameEffectFromParent`. Engine effects built with the constructor's 1 keep it unless the handler clears it (HASTE/SLOW_INTERNAL do). `GetFirstEffect`/`GetNextEffect` (routines 85/86, shared handler `0x00549180`, cursor at object +0x1e8) return only effects with `IsExposed` ≠ 0, type ≠ ICON (0x43) and duration type temporary or permanent, so sub-effects and instant/equipped/innate effects are hidden from scripts | high |
| +0x24 | — | caster level override, −1 by default; `ApplyEffectToObject` copies the creator creature's item-cast caster level (+0x968) here when its flag +0x964 is set | med |
| +0x28 / +0x2c | — | link children (left, right); only LINK effects (`EffectLinkEffects`, `SetEffectIcon`) have them. Not saved | high |
| +0x30 / +0x34 | `NumIntegers` / `IntList` | count and array of int parameters: 8 by default, 21 for `EffectDamage`, 1 for `EffectForceDrain`. `EffectPoison` keeps 8; `LoadEffect` widens a DAMAGE or POISON effect saved with fewer than 21 to 21 | high |
| +0x38..+0x44 | `FloatList` | 4 float parameters | high |
| +0x48..+0x70 | `StringList` | 6 string parameters | high |
| +0x78..+0x84 | `ObjectList` | 4 object id parameters (`OBJECT_INVALID` by default) | high |
| +0x88 | `SkipOnLoad` | set by `ApplyEffect`: 0 only for exposed effects on objects whose +0x1ec is 0; when loading, effects so marked are not re-applied (their parents rebuild them) | med |

Accessors (all high): `GetInteger` `0x00503690`, `SetInteger` `0x005036a0`, `GetFloat`
`0x005036c0`, `SetFloat` `0x005036d0`, `GetObjectID` `0x005036e0`, `SetObjectID` `0x005036f0`,
`GetString` `0x00503700`, `SetString` `0x00503730`, `SetNumIntegers` `0x00503630` (reallocates
and zeroes the array), `Set/GetExpiryTime` `0x00503750`/`0x00503770`.

**SubType word.** Duration type in bits 0–2: 0 instant, 1 temporary, 2 permanent (the script
`DURATION_TYPE_*` values), plus two engine-only values: 3 *equipped* (effects made from item
properties while the item is worn) and 4 *innate* (internal effects the engine adds and removes
itself, e.g. HASTE_INTERNAL, SETSTATE_INTERNAL, the alignment mastery effects). Subtype in bits
3–4: 8 magical, 0x10 supernatural, 0x18 extraordinary (the `SUBTYPE_*` constants), 0 none. Most
script constructors set magical; the ones marked "no subtype" in 1.2 (all KOTOR additions) leave it
0.
`MagicalEffect`/`SupernaturalEffect`/`ExtraordinaryEffect` (routines 112–114, shared handler
`0x005435c0`) rewrite the bits (magical clears 0x10 and sets 8, supernatural clears 8 and sets
0x10, extraordinary sets both) and, for a LINK, push the change down to the children
(`UpdateLinked`). (high)

**Creator and spell id.** `SetCreator` (`0x00503a00`) stores the creator and copies the
creator's *current spell id* (CSWSObject virtual slot 46, the id set while an impact script runs)
into +0x1c; if the creator is an area-of-effect object, the AoE's own creator (+0x248) is stored
instead. Most `Effect*` constructors call it with `OBJECT_SELF` (when that resolves to an object;
`EffectHeal`, `EffectTemporaryForcePoints` and `EffectTemporaryHitpoints` only when it is a
creature), so effects built inside a spell impact script carry that spell's id. The constructors
listed in 1.2 as "no creator" leave `CreatorId` `OBJECT_INVALID` and `SpellId` −1. (high)

**Sub-effects.** Handlers that need extra effects build them with `CGameEffectFromParent`
(`0x00503f70`), which copies id, subtype/duration bits, duration, expiry, creator and spell id from
the parent, gives the child as many (zeroed) ints as the parent has, and leaves type, `IsExposed`,
`SkipOnLoad` and the caster level (+0x24) 0. Because the id is shared, removing the parent removes
them. (high)

### 1.2 Script constructors

Parameter defaults are the `nwscript.nss` ones. "Type" is the internal type in 1.3. All set the
subtype to magical and the creator to `OBJECT_SELF` unless noted: "no subtype" leaves the subtype
bits 0, "no creator" also skips `SetCreator`. An *invalid effect* is one whose type the constructor
left at 0: it is returned to the script, but `OnEffectApplied` drops it. Out-of-range arguments are
clamped where the row says so. (high unless marked)

| Routine | Handler | Type | Parameters as stored |
|---|---|---|---|
| 51 EffectAssuredHit | `0x005313f0` (shared) | 0x65 | — |
| 78 EffectHeal | `0x00532a70` | 0x27 | int0 amount (≤ 0 gives an invalid effect); creator only when `OBJECT_SELF` is a creature |
| 79 EffectDamage | `0x00531ae0` | 0x26 | 21 ints: int0..13 = amount per damage type, −1 for the others (index = log2 of the `DAMAGE_TYPE_*` bit); int14 amount; int16 1000; int17 damage type flags; int18 damage power. Amount outside 0..10000 → 1, type outside 0..0x2000 → 8 (universal), power outside 0..6 → 0 |
| 80 EffectAbilityIncrease / 446 …Decrease | `0x005307f0` / `0x00530680` | 0x24 / 0x25 | int0 ability (0 STR..5 CHA; outside → 0), int1 amount |
| 81 EffectDamageResistance | `0x00532500` | 0x02 | int0 damage type (outside 0..0x2000 → 8), int1 amount, int2 limit |
| 82 EffectResurrection | `0x00533660` | 0x04 | — |
| 115 EffectACIncrease / 450 …Decrease | `0x00530b20` / `0x00530960` | 0x30 / 0x31 | int0 modifier type (0 dodge, 1 natural, 2 armour, 3 shield, 4 deflection; outside 0..4 → 0), int1 amount, int2 race (= "any race", the race count at `g_pRules`+0xaa), int5 versus damage type |
| 117 EffectSavingThrowIncrease / 452 …Decrease | `0x00533910` / `0x00533760` | 0x1a / 0x1b | int0 amount, int1 save (0 all, 1 fort, 2 reflex, 3 will; outside → 0), int2 save type, int3 race (any) |
| 118 EffectAttackIncrease / 447 …Decrease | `0x005310e0` / `0x00530f60` | 0x0a / 0x0b | int0 amount, int1 modifier type (0 misc, 1 on-hand, 2 off-hand; outside 0..7 → 0), int2 race (any) |
| 119 EffectDamageReduction | `0x00532350` | 0x0c | int0 amount, int1 damage power (outside 0..6 → 0), int2 limit (negative amount or limit → 0) |
| 120 EffectDamageIncrease / 448 …Decrease | `0x005321b0` / `0x00531d50` | 0x0d / 0x0e | int0 amount (a row of iprp_damagecost.2da, see 1.9; outside 1..10 → 0), int1 damage type (outside 0..0x2000 → 8), int2 race (any) |
| 130 EffectEntangle | shared | 0x12 | — |
| 133 EffectDeath | shared | 0x13 | int0 spectacular, int1 display feedback (default 1) |
| 134 EffectKnockdown | shared | 0x14 | — |
| 148 EffectParalyze | shared | 0x08 | int0 state 5 |
| 149 EffectSpellImmunity | `0x00533e70` | 0x32 | int0 spell (below −1 or above the spell count gives an invalid effect) |
| 153 EffectForceJump | `0x005348c0` | 0x66 | obj0 target, int0 advanced; no subtype |
| 154 EffectSleep | shared | 0x08 | int0 state 6 |
| 156 EffectTemporaryForcePoints | `0x00534340` | 0x5b | int0 amount (≤ 0 gives an invalid effect); creator only when `OBJECT_SELF` is a creature |
| 157 EffectConfused / 158 EffectFrightened | shared | 0x08 | int0 state 1 / 2 |
| 159 EffectChoke | `0x005351e0` | 0x08 | int0 state 7; no subtype, no creator |
| 161 EffectStunned | shared | 0x08 | int0 state 4 |
| 164 EffectRegenerate | shared | 0x07 | int0 amount, int1 interval in ms (seconds × 1000) |
| 165 EffectMovementSpeedIncrease / 451 …Decrease | `0x00533420` / `0x005332e0` | 0x1c / 0x1d | int0 percent |
| 171 EffectAreaOfEffect | `0x00530ce0` | 0x1f | int0 vfx_persistent row, string0..2 OnEnter/Heartbeat/OnExit scripts |
| 180 EffectVisualEffect | `0x005346b0` | 0x1e | int0 visualeffects.2da row, int2 miss flag |
| 199 EffectLinkEffects | `0x00532f80` | 0x28 | children (child, parent) |
| 207 EffectBeam | `0x00531260` | 0x20 | int0 beam vfx, int1 body part, int2 miss, obj0 effector. A beam row outside the fixed list in `0x004ca960` (2026–2029, 2037, 2038, 2049–2053, 2061, 2065, 2066, 4037, 6000) gives an invalid effect |
| 212 EffectForceResistanceIncrease / 454 …Decrease | `0x00534230` / `0x00534120` | 0x21 / 0x22 | int0 amount |
| 224 EffectBodyFuel | `0x00535290` | 0x62 | —; no subtype, no creator |
| 250 EffectPoison | `0x00533560` | 0x23 | int0 poison.2da row |
| 252 EffectAssuredDeflection | shared | 0x68 | int0 nReturn |
| 269 EffectForcePushTargeted | `0x00534ab0` | 0x3c | int0 1, int1 ignore-line test, float0..2 centre; no subtype |
| 270 EffectHaste | shared | 0x01 | — |
| 273 EffectImmunity | `0x00532d00` | 0x16 | int0 immunity type (clamped to 0..33), int1 race (any) |
| 275 EffectDamageImmunityIncrease / 449 …Decrease | `0x00532050` / `0x00531ef0` | 0x10 / 0x11 | int0 damage type (outside 0..0x2000 → 8), int1 percent (clamped to 0..100 for the increase, −100..100 for the decrease) |
| 314 EffectTemporaryHitpoints | `0x00534490` | 0x0f | int0 amount (≤ 0 gives an invalid effect); creator only when `OBJECT_SELF` is a creature |
| 351 EffectSkillIncrease / 453 …Decrease | `0x00533d00` / `0x00533b90` | 0x37 / 0x38 | int0 skill (0xff = all), int1 amount, int2 race (any). A skill outside 1..count−1 other than 0xff gives an invalid effect, so skill 0 (`SKILL_COMPUTER_USE`) cannot be raised or lowered this way (med: static reading only, needs a runtime check) |
| 372 EffectDamageForcePoints / 373 EffectHealForcePoints | `0x00534f40` / `0x00535020` | 0x5f / 0x60 | int0 amount; no subtype, no creator |
| 387 EffectHitPointChangeWhenDying | `0x00532bd0` | 0x39 | float0 HP per round (0 gives an invalid effect); duration bits cleared, no subtype |
| 391 EffectDroidStun | `0x00534810` | 0x08 | int0 state 3; no subtype, no creator |
| 392 EffectForcePushed | `0x005349f0` | 0x3c | —; no subtype |
| 402 EffectForceResisted | shared | 0x69 | obj0 source |
| 420 EffectForceFizzle | shared | 0x6a | — |
| 457 EffectInvisibility | `0x00532e40` | 0x2f | int0 invisibility type (anything but 1, 2 or 4 gives an invalid effect), int1 race (any) |
| 458 EffectConcealment / 477 EffectMissChance | `0x005319a0` / `0x00533090` | 0x4c | int0 percent (outside 1..100 gives an invalid effect), int1 race (any) / 0 |
| 459 EffectForceShield | `0x00532690` | 0x6b | int0 forceshields.2da row; no subtype |
| 460 EffectDispelMagicAll / 473 …Best | shared | 0x33 / 0x34 | — : the caster level argument is popped and discarded, int0 stays 0 (the handlers use the creator's level, 1.3) |
| 463 EffectDisguise | shared | 0x3e | int0 appearance |
| 465 EffectTrueSeeing / 466 EffectSeeInvisible | `0x005345e0` / `0x00533ac0` | 0x48 / 0x46 | — |
| 467 EffectTimeStop | shared | 0x40 | — |
| 469 / 470 EffectBlasterDeflection Increase / Decrease | `0x00534cd0` / `0x00534db0` | 0x5c / 0x5d | int0 amount; no subtype, no creator |
| 471 EffectHorrified | `0x00534e90` | 0x08 | int0 state 8; no subtype, no creator |
| 472 EffectSpellLevelAbsorption | `0x00533fa0` | 0x41 | int0..2, int3 (int1 == 0); int0 outside −1..9 gives an invalid effect |
| 485 EffectModifyAttacks | `0x005331c0` | 0x2c | int0 attacks (≥ 6 gives an invalid effect) |
| 487 EffectDamageShield | `0x00532790` | 0x3d | int0 amount (outside 0..10000 → 1), int1 random (outside 1..10 → 0), int2 damage type (outside 0..0x2000 → 8) |
| 552 SetEffectIcon | `0x005475a0` | 0x43, linked | builds an ICON effect (int0 effecticon.2da row) and returns `Link(icon, effect)`; icon and link are `CGameEffectFromParent` copies of the effect (same id and subtype), exposed, with the creator set |
| 675 EffectForceDrain | `0x00532920` | 0x5a | int0 amount, the only int (≤ 0 gives an invalid effect) |
| 676 EffectPsychicStatic | `0x00535340` | 0x63 | —; no subtype, no creator |
| 702 EffectLightsaberThrow | `0x005353f0` | 0x64 | obj0..2 targets; no subtype, no creator. `nAdvancedDamage` is popped and discarded, so int0 stays 0 and the handler always uses the basic throw (spell 49) rather than the advanced one (spell 4); no game script passes it (med: needs a runtime check) |
| 703 EffectWhirlWind | `0x00534c20` | 0x08 | int0 state 10; no subtype, no creator |
| 754 / 755 / 756 EffectCutScene Horrified / Paralyze / Stunned | shared | 0x08 | int0 state 8 / 5 / 4, **int1 1** (cutscene: skips immunity) |
| 355–357 Versus{Alignment,RacialType,Trap}Effect | `0x00545470` | — | rewrite the versus ints of the wrapped effect |

The shared handler is `0x005313f0`, which switches on the routine number. (high)

### 1.3 Internal types and their handlers

The effect list handler (`CSWSEffectListHandler`, vtable `0x00744274`, one instance at
`CServerAIMaster`+0x58) keeps two 0x6e-entry function tables, filled by `InitializeEffects`
(`0x004e4a10`): +4 apply handlers, +8 remove handlers, indexed by internal type.
`OnEffectApplied` (`0x004d8320`) and `OnEffectRemoved` (`0x004d8360`) dispatch; type 0, a missing
handler or a type ≥ 0x6e returns 1. Every type from 1 to 0x6d has an apply handler except 0x55.
The item property handler (vtable `0x00744284`, at +0x5c) is the same pattern with 0x3c entries.
(high)

**Return convention.** An apply handler returns **0 to keep the effect** in the object's list
(it is a lasting modifier) and **1 to drop it** (instant effect, rejected by immunity, or one that
only spawned children). Remove handlers return 1. Most handlers act only on creatures; on another
object they return 0 (kept, no effect) or 1 as noted. Generic handlers: `OnApplyPassive`
(`0x004de5f0`, keep; for types read only by getters), `OnRemovePassive` (`0x004ddf20`), a folded
"return 0" (`0x0066b360`, keep, no creature check) and a folded "return 1" (`0x004df410`).
`OnRemoveMarkCombatDirty` (`0x004d92a0`) sets the creature's recompute flag (+0x344, which makes
the next `AIUpdate` call the stats recompute `0x005addc0`). (high)

Script type is what `GetEffectType` returns (mapping `0x00503a70`; 0 where unmapped, and for
SETSTATE 24/25/35/29/27/30 for states 1–6, 0 for the others). Names marked † are guesses from the
NWN numbering, which KOTOR follows up to 0x2a and then shifts by one; the rest come from a
constructor, an item property that builds the type, or the script mapping. In the handler column
"a, b / c, d" pairs two types: a and b are their apply handlers, c and d their remove handlers.

| Int. | Name | Script | Apply / remove | What the apply handler does | Conf. |
|---|---|---|---|---|---|
| 0x01 | HASTE | 36 | `0x004e2a90` / `0x004e2d50` | shared with SLOW: counts haste (+1) and slow (−1) effects; when the sign of the total changes, adds an innate HASTE_INTERNAL or SLOW_INTERNAL, or removes it at 0. The internal effect is a new effect (own id, `IsExposed` 0, the triggering effect's spell id). Slow is refused by immunity 9 (feedback 0x92 to target and creator). Kept | high |
| 0x02 | DAMAGE_RESISTANCE | 1 | folded keep | read when damage is applied (slot 42, [combat.md](combat.md)) | high |
| 0x03 | SLOW | 37 | as 0x01 | — | high |
| 0x04 | RESURRECTION | — | `0x004e13c0` | only on a creature whose `IsRaiseable` flag (+0xf0) is set (it does not test for death): HP to 1 if ≤ 0, clear actions, +0x19c = 1, AI mask (+0x9f0) all-allowed, commandable (+0xe8), refresh the state animation, remove temporary HP_CHANGE_WHEN_DYING effects. Never kept | med |
| 0x05 | DISEASE | 32 | `0x004e2720` / `0x004db870` | creatures only. An instant one becomes permanent. Dropped for plot creatures, by immunity 3 (feedback 0x7d), when a disease is already present, or on a successful Fortitude save (disease type) against disease.2da `First_Save`. On a failed save: incubation end = now + `Incu_Hours` game hours into int3/int4, a VFX 51 child, kept. On load only the VFX child is re-added | med |
| 0x06 | SUMMON_CREATURE | — | `0x004d8680` / `0x004d8a10` | loads the creature template named by string0 and places it at the nearest safe position (within 20 m) to the stored location (obj0 area, float0..2; the target's own position when unset); stores the summon's id in obj1 and sends event 0x18 to the summoner after float3 s; skipped while a game is loading. Kept | med |
| 0x07 | REGENERATE | 3 | `0x004db2c0` | creatures: stamps the current world time (day, time) in int2/int3; ticks in `UpdateEffectList` (1.6). Kept | high |
| 0x08 | SETSTATE | by state | `0x004e1c20` / `0x004e22f0` | crowd control, 1.10 | high |
| 0x09 | SETSTATE_INTERNAL | — | `0x004da330` / `0x004da870` | the per-state blocking, 1.10 | high |
| 0x0a / 0x0b | ATTACK_INCREASE / DECREASE | 40 / 41 | `0x004d9120`, `0x004d9170` / dirty | kept if amount > 0; the decrease is refused for plot creatures and by immunity 20 | high |
| 0x0c | DAMAGE_REDUCTION | 7 | folded keep | read by slot 41 `DoDamageReduction` (`0x004d09e0`) | high |
| 0x0d / 0x0e | DAMAGE_INCREASE / DECREASE | 42 / 43 | `0x004d9200`, `0x004d9230` / dirty | kept for any amount; the decrease is refused by immunity 21 | high |
| 0x0f | TEMPORARY_HITPOINTS | 9 | `0x004d92d0` / `0x004d9320` | adds int0 to the creature's bonus HP (+0xe4). Removal subtracts it (floor 0); if that leaves the creature newly dead or newly dying, it applies an instant DEATH (int1 feedback 1, no creator) and a blood VFX by appearance.2da `BLOODCOLR` (R 158, G 159, Y 160, otherwise row 0) | high |
| 0x10 / 0x11 | DAMAGE_IMMUNITY_INCREASE / DECREASE | 44 / 45 | `0x004d9620`, `0x004d9680` / `0x004e18d0`, `0x004e19a0` | any object: add (decrease: subtract) int1 to the entry of the lowest set damage-type bit in the per-type immunity table (+0x1ac, clamped ±100). A negative int1 is refused; the decrease is also refused for plot objects and by immunity 22. Removal rebuilds the entry from the remaining effects of that type | high |
| 0x12 | ENTANGLE | 11 | `0x004d9720` / `0x004d9970` | 1.10 | high |
| 0x13 | DEATH | — | `0x004e0ac0` | 1.9 | high |
| 0x14 | KNOCKDOWN | — | `0x004d99b0` / `0x004d9c50` | 1.10 | high |
| 0x15 | DEAF | 13 | `0x004da090` | unless plot or immune (immunity 8, feedback 0x8c): children SET_AI_STATE (int0 0xffef) and ARCANE_SPELL_FAILURE (int0 20). Never kept | med |
| 0x16 | IMMUNITY | 15 | passive / return-1 | read by `GetEffectImmunity` (1.8) | high |
| 0x17 | SET_AI_STATE | — | `0x004da050` / `0x004e1a70` | ANDs int0 into the creature's AI state mask (+0x9f0); removal recomputes the mask from the remaining ones | high |
| 0x18 | ENEMY_ATTACK_BONUS | 17 | `0x004da260` / `0x004e1b00` | adds int0 to the stats byte +0x103 (refused for plot creatures); removal re-sums the remaining ones | high |
| 0x19 | ARCANE_SPELL_FAILURE | 18 | `0x004da2c0` / `0x004e1b80` | only sets the recompute flag (+0x344); int0 is passed to a folded no-op, so the effect does nothing else. Kept | med |
| 0x1a / 0x1b | SAVING_THROW_INCREASE / DECREASE | 50 / 51 | `0x004d8cb0`, `0x004d8d00` / dirty | kept if amount > 0; the decrease is also refused for plot creatures and by immunity 25 | high |
| 0x1c / 0x1d | MOVEMENT_SPEED_INCREASE / DECREASE | 48 / 49 | `0x004da910`, `0x004da990` / `0x004e2490` | 1.7 | high |
| 0x1e | VISUALEFFECT | 75 | `0x004daa40` / `0x004dadc0` | 1.11 | high |
| 0x1f | AREA_OF_EFFECT | 20 | `0x004dade0` / `0x004db010` | creatures only (dropped on other objects): creates an AoE object with the effect's creator and spell id, loads vfx_persistent row int0, overrides its OnEnter/Heartbeat/OnExit scripts with non-empty string0/1/2, attaches it to the target at the target's position, and stores its id in obj0. Kept | med |
| 0x20 | BEAM | 21 | `0x004db090` | on a creature, placeable or door (object types 5, 9, 10): a VISUALEFFECT child copying int0..2 and obj0. Kept | high |
| 0x21 / 0x22 | FORCE_RESISTANCE_INCREASE / DECREASE | 52 / 53 | `0x004db180`, `0x004db210` / `0x004e2570`, `0x004e2650` | 1.7 | high |
| 0x23 | POISON | 31 | `0x004db320` / `0x004db810` | 1.9 | high |
| 0x24 / 0x25 | ABILITY_INCREASE / DECREASE | 38 / 39 | `0x004d84d0`, `0x004d8590` / `0x004d8550`, `0x004d8650` | kept if amount > 0 and the creature is not dead or dying; the decrease also needs not-plot and no immunity 19 | high |
| 0x26 | DAMAGE | — | `0x004dfa40` | applies damage ([combat.md](combat.md)); never kept | high |
| 0x27 | HEAL | — | `0x004e0750` | 1.9 | high |
| 0x28 | LINK | — | `0x004db8a0` | 1.5 | high |
| 0x29 | HASTE_INTERNAL | — | `0x004db8f0` / `0x004dba30` | children: MOVEMENT_SPEED_INCREASE 150, +4 dodge AC; sets creature +0x8cc = 1, +0x8d0 = 0 | high |
| 0x2a | SLOW_INTERNAL | — | `0x004dba50` / `0x004dbcc0` | children: MOVEMENT_SPEED_DECREASE 50, −2 dodge AC, −2 attack, −2 reflex, LIMIT_MOVEMENT_SPEED; sets creature +0x8d0 = 1, +0x8cc = 0 | high |
| 0x2b | ? | — | passive | — | low |
| 0x2c | MODIFYNUMATTACKS | — | `0x004dbd90` / `0x004dbe00` | adds int0 to the combat round's extra attacks (`EffectAttacks`, +0x9a4 of the round at creature +0x9c8), clamped to 0..2; refused when it is already above 2. Removal subtracts, same clamp | high |
| 0x2d | CURSE | 33 | `0x004dbe60` | unless plot or immune (immunity 17, feedback 0x8d): six ABILITY_DECREASE children, ability i by int i. Never kept | med |
| 0x2e | SILENCE | 34 | `0x004dc200` / `0x004dc380` | unless plot or immune (immunity 11, feedback 0x91): SET_AI_STATE child (int0 0xfff7), creature +0x8c8 = 1 | med |
| 0x2f | INVISIBILITY | 56 | `0x004e3be0` / `0x004e3c30` | adds the creature to the module's invisible list (module +0x13c); removal takes it off unless another INVISIBILITY or SANCTUARY effect with a different id remains. Kept | med |
| 0x30 / 0x31 | AC_INCREASE / DECREASE | 46 / 47 | `0x004d8d80`, `0x004d8f80` / `0x004e14d0`, `0x004e16e0` | 1.7 | high |
| 0x32 | SPELL_IMMUNITY | 73 | folded keep | read by the spell immunity check `0x004ccfc0` (int0 = the spell or −1) | high |
| 0x33 / 0x34 | DISPEL_MAGIC_ALL / BEST | 59 / 69 | `0x004e40d0`, `0x004e43c0` | ALL: needs a creature creator; for each magical temporary or permanent effect id on the target, removes it (via event 0xe) when d20 + the dispeller's level > 11 + the level of that effect's creator (0 when not a creature). int0 is not read. BEST not read in detail | low |
| 0x35 | TAUNT † | — | `0x004dc3b0` / `0x004dc500` | unless plot: creature +0x8e4 = 1, an AC_DECREASE child (dodge, int0) and an ARCANE_SPELL_FAILURE child (30) | low |
| 0x36 | LIGHT † | — | `0x004dbce0` | VISUALEFFECT child with int0; built by the item property handler `0x004e62d0`. Kept | low |
| 0x37 / 0x38 | SKILL_INCREASE / DECREASE | 54 / 55 | `0x004dc580`, `0x004dc5d0` / return-1 | kept on a creature when amount ≥ 0; the decrease is also refused for plot objects and by immunity 27 | high |
| 0x39 | HITPOINTCHANGEWHENDYING | — | `0x004dc660` / `0x004dc7a0` | — | med |
| 0x3a | SETWALKANIMATION † | — | `0x004dca80` / `0x004e3050` | sets creature byte +0xa10 to int0; removal sets it from another remaining one, else 0. Built by the item property handler `0x004e68e0` | low |
| 0x3b | LIMIT_MOVEMENT_SPEED | — | `0x004dc530` / `0x004e2fe0` | walk-only flag (creature +0x8e8); refused for plot creatures; removal clears it unless another remains | high |
| 0x3c | FORCE_PUSH | — | `0x004e3800` / `0x004de400` | knock-back along the push direction; SETSTATE child | med |
| 0x3d | DAMAGE_SHIELD | 60 | folded keep | read by `0x005b7d10`, which `OnApplyDamage` calls | high |
| 0x3e | DISGUISE | 62 | `0x004e31d0` / `0x004dcac0` | creatures; refused on a dead one (except while loading). Removes the other DISGUISE effects, then swaps the appearance to int0. Kept | high |
| 0x3f | SANCTUARY | 63 | `0x004e3d10` / `0x004e3e70` | every other creature in the area that perceives the target makes a Will save (DC int4) against it; on a failure it stops attacking and its perception entry is changed. Adds the target to the module's invisible list. Kept | med |
| 0x40 | TIMESTOP | 66 | `0x004dcb40` / `0x004dcc90` | with no pause: adds the target to the time-stop exempt list and toggles pause type 1 on, kept. While a time stop runs: sets the expiry of the target's existing TIMESTOP effect to its clock now + the new duration and discards the new one (a target without one keeps it but is not made exempt). During a player pause: just kept. Removal toggles type 1 and drops the exemption ([gameloop.md](gameloop.md) 6.5) | high |
| 0x41 | SPELL_LEVEL_ABSORPTION | 68 | folded keep | the reader does nothing with it | med |
| 0x43 | ICON | — | `0x004e4790` / `0x004e30d0` | 1.11 | high |
| 0x46 / 0x47 / 0x48 / 0x49 / 0x4a | SEE_INVISIBLE / ULTRAVISION / TRUE_SEEING / BLINDNESS / DARKNESS | 65 / 70 / 64 / 67 / 58 | `0x004dcd00`, `0x004e3320`, `0x004e35b0`, `0x004dcd30`, `0x004dcff0` | vision bits at creature +0x8ec: see invisible 1, ultravision 2, true seeing 4. Ultravision (plus a 0x45 child) and true seeing also remove darkness-blindness links. BLINDNESS (not plot) sets bit int0: 0x10 (immunity 7 refuses it, feedback 0x8b) or 8, which is skipped when bit 2 or 4 is set; children CONCEALMENT 50, 0x45, VFX 5002. DARKNESS adds INVISIBILITY (type 2) and BLINDNESS (8) children | med |
| 0x4b / 0x4c | MISS_CHANCE / CONCEALMENT | 71 / 72 | `0x004dcfc0` | kept if int0 is 1..100; both script constructors build 0x4c | high |
| 0x52 | NEGATIVELEVEL | 61 | `0x004dd520` / `0x004dd970` | int0 ≤ 100 levels, immunity 29 (feedback 0x83): ATTACK, SAVING_THROW (all) and SKILL (all) DECREASE children of int0; lowers the highest class by int0 (class kept in int1), an instant DEATH when the level reaches 0; the creator gets permanent TEMPORARY_HITPOINTS 5 × int0 | med |
| 0x5a | FORCE_DRAIN | — | `0x004ddec0` | current FP (stats +0x124) = current + temporary (+0x126) − int0, floor 0. Never kept | high |
| 0x5b | TEMPORARY_FORCE_POINTS | — | `0x004dde40` / `0x004dde80` | temporary FP (stats +0x126) ± int0 | high |
| 0x5c / 0x5d | BLASTER_DEFLECTION_INCREASE / DECREASE | — | passive | read by the deflection roll | high |
| 0x5f / 0x60 | DAMAGE / HEAL_FORCE_POINTS | — | `0x004de4d0`, `0x004de540` | 3.6 | high |
| 0x62 | BODY_FUEL | — | `0x004de5b0` / `0x004de5d0` | creature flag +0xa9c set; removal clears it | med |
| 0x63 | PSYCHIC_STATIC | — | passive | — | med |
| 0x64 | LIGHTSABER_THROW | 76 | `0x004de600` / `0x004dece0` | throw and return, DAMAGE children; int0 picks the spell row (0 → 49 LIGHT_SABER_THROW, else 4 ADVANCED), see 1.2 | med |
| 0x65 | ASSURED_HIT | 74 | `0x004d83a0` / `0x004d83f0` | sets creature flag +0x8d4; refused when it is already set | high |
| 0x66 / 0x67 | FORCE_JUMP / its internal step | 77 / — | `0x004ddf40`, `0x004de0a0` / return-1 | jump: sets the interact target to obj0, queues the 0x67 step as an event, VFX 1002; the step moves the jumper next to the target and gives the target a SETSTATE 13 child | med |
| 0x68 | ASSURED_DEFLECTION | 78 | `0x004d8420` / `0x004d8490` | creature flags +0x8dc (and +0x8d8 when int0 ≠ 0); refused when either is already set | high |
| 0x69 / 0x6a | FORCE_RESISTED / FORCE_FIZZLE | — | `0x004ded00`, `0x004dede0` | an instant VISUALEFFECT child (4037 with obj0 as source / 4036); FORCE_RESISTED also plays animation 10145 on the object. Never kept | high |
| 0x6b | FORCE_SHIELD | — | `0x004df540` / folded return-1 `0x004df410` | builds an aura child and a limited DAMAGE_RESISTANCE child from forceshields.2da, after taking off the old shield (1.13) | high |
| 0x6c / 0x6d | LIGHT_SIDE / DARK_SIDE_MASTERY | — | `0x004dee90`, `0x004df160` / return-1 | 3.8 | high |

Types 0x42, 0x44, 0x45, 0x4d–0x51, 0x53, 0x54, 0x56–0x59, 0x5e, 0x61 have handlers but no script
constructor (0x4d and 0x58 share `0x004dd100`; 0x42, 0x5e and 0x61 are passive, 0x4e folded keep);
their creators are listed in the proposals file (all low). 0x55 has no handler, so it is always
dropped.

### 1.4 Applying an effect

`ApplyEffectToObject` (`0x0052e570`) sets the duration bits from `nDurationType` (instant 0,
temporary 1 with `Duration` = fDuration, anything else permanent 2), copies the caster level
override (1.1) when the creator is a creature with its flag set, and calls
`CSWSObject::ApplyEffect` **directly** (synchronously, while the script runs). Engine code that
wants a delay queues event 5 (APPLY_EFFECT) instead; the event handler calls the same function. A
target that is not an object frees the effect. (high)

`ApplyEffectAtLocation` (`0x0052e430`) sets the duration bits the same way but does not go
through `ApplyEffect`: it hands the effect to the area of the **player's creature** (not the
location's area; no player area frees it) at `0x0050c6b0`, which handles four types and frees
everything else unapplied: AREA_OF_EFFECT creates the AoE object at the position (registered with
a magical effect's creator), SUMMON_CREATURE is applied to its creator with the area and position
filled in, VISUALEFFECT plays at the position, and a LINK is split and each child handled the same
way. (high for the dispatch; med for the player's-area choice, which only matters off the
player's area)

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
is removed again, taking the already-applied visual with it. (high for the mechanism) By the same
rule a link whose kept children are all visuals (other than vfx 5000/5001) or icons is removed as
soon as it is applied. (med: follows from the code, needs a runtime check)

The list is **sorted by type, stable**. Creatures keep the index of the first effect of 26 types
in their stats (+0x12e..+0x162, rebuilt by `UpdateEffectPtrs` `0x004f14f0`, virtual slot 54) so
that getters can start at the right place and stop at the first higher type. The rebuild only
writes the types present and never resets the others, so the start index of an absent type keeps
its old value (a walker that starts at the stale index of its first type can then miss effects of
its second type, e.g. attack penalties when no attack bonus is left; med, needs a runtime check).
An implementation may use any structure, but iteration order (by type, then by application order)
is visible to the "highest wins" rules below and to `GetFirstEffect`/`GetNextEffect` (which walk
the same list but show only exposed, non-ICON, temporary or permanent effects; 1.1). (high)

`UpdateAttributesOnEffect` (`0x004ffaf0`, slot 55) runs after every applied or removed
ABILITY_INCREASE/DECREASE: it recomputes that ability's modifier; for CON it keeps the HP deficit
(current = new max − (old max − current)) and, if the creature newly drops to dead or dying,
queues an instant DEATH effect (event 5, int1 = 1); for WIS and CHA it keeps the FP deficit the
same way. (high)

### 1.5 Linked effects

`EffectLinkEffects(child, parent)` builds a LINK (0x28) whose two children are the arguments and
calls `UpdateLinked` (`0x00504240`), which copies the link's subtype (when it has one), creator,
duration, duration type, expiry, spell id **and id** into both children, recursively. The LINK apply handler
(`0x004db8a0`) refreshes that, applies each child through `ApplyEffect`, detaches them and
returns 1, so the list never holds the LINK itself, only its leaves, all with the same id. (high)

Consequences an implementer must keep: a link is removed as a unit (removal is by id); a link
applied as temporary makes every child temporary with the same expiry; `GetEffectType` of a link
returns 0. (high)

### 1.6 Expiry and periodic effects

`CSWSObject::UpdateEffectList(day, time)` (`0x004d1730`) is called from the `AIUpdate` of
creatures (`0x004fe210`, after `UpdateCombat` and `0x004ed110`, before `RunActions`), placeables
and doors, i.e. every time the AI master updates the object — normally every frame, not once per
round. "Now" is the object's active timer (`GetActiveTimer` `0x004ae830`: the world timer, or a
pause timer for objects exempt from a pause). For each effect in list order (high):

1. **REGENERATE (0x07)**: elapsed = now − (int2, int3). If the object is a non-creature with
   HP < max and alive, or a creature that is alive, not dying and below its maximum (Force points
   when int4 is 0x36, otherwise HP), and elapsed > int1 ms, it applies an instant HEAL (int0
   amount, int1 = int4, creator = the regen's creator), restamps int2/int3 and restarts the scan
   from the first effect.
2. **POISON (0x23)**: if more than int5 s have passed since the start (int1, int2), queue its
   removal (event 14, no delay); otherwise, once more than int6 s have passed since the last tick
   (int3, int4), apply tick number float0 (`ApplyPoisonTick` `0x004ee770`, 1.9) and add 1 to
   float0. While the in-game GUI flag (+0xb4) is set the tick is skipped and int5 grows by one
   period instead, so the poison lasts that much longer. Either way int3/int4 are restamped.
3. **DISEASE (0x05)**: once now has reached (int3, int4), calls the disease tick `0x004f6790`
   (disease.2da `Dam_`/`Dice_`/`Subs_Save`, the 24-hour and end-of-incubation scripts) and
   restarts the scan.
4. **Expiry**: if the duration type is temporary and `CompareWorldTimes(now, expiry)` (`0x004adfa0`)
   says now is later, `RemoveEffectById` and restart the scan from the first effect.

A temporary effect therefore ends on the first object update after its expiry time. Durations are
seconds; the world timer converts them with seconds-per-day (+0x40) = 1440 × minutes-per-hour
(+0x38, `SetMinutesPerHour` `0x004adba0`) and keeps the remainder in ms (`0x004ae1b0`,
`0x004ae200`). (high)

Poison, disease and regeneration all use this game-time clock, so they stop when it is paused.
(med)

### 1.7 How getters combine effects (stacking)

Most numeric effects are not applied to fields when they arrive; getters walk the list when asked.
The central walker is `CSWSCreature::GetTotalEffectBonus(category, versus, …)` (`0x004f3fe0`):

| Category | Effect types | Filter | Cap (bonus / penalty) | Used by |
|---|---|---|---|---|
| 1 attack | 0x0a / 0x0b | int1 attack type 0 (any) or the current attack's type (attack type 6 also matches 1 and 3, type 8 also 7; with no attack type set, 1 on-hand / 2 off-hand); int2 race any or the versus creature's race; int4 alignment group 0 or the versus creature's | +20 / −20 | attack bonus ([combat.md](combat.md) 4.2) |
| 2 damage | 0x0d / 0x0e | int5 attack type 0 or the current one (as int1 for attack); int2 race; int4 alignment; int1 damage-type flags non-zero (`GetDamageRoll`'s call) | +36 / −36, on the return value only | damage roll ([combat.md](combat.md) 6.1 term 8) |
| 3 saving throw | 0x1a / 0x1b | int1 save 0 or this save; int2 save type 0 or this type; int3 race; int5 alignment | +20 / −20 | saves (2.1) |
| 4 ability | 0x24 / 0x25 | int0 = the ability (value in int1) | +20 / −30 | `GetSTRStat` … `GetCHAStat` |
| 5 skill | 0x37 / 0x38 | int0 0xff or the skill; int2 race; int4 alignment (value in int1) | +30 / −30 | `GetSkillRank` |

Result = min(sum of bonuses, cap) − min(sum of penalties, cap). Without a versus creature only
effects with race "any" and alignment 0 pass. (high)

**Same-source rule.** Within a category, bonuses (and separately penalties) are grouped by source;
from each group only the largest counts, and the groups are added:

- for saves, abilities and skills, an effect whose creator is an **item** (an equipped item's
  property) groups with the other effects of that item, whatever its spell id;
- otherwise an effect with a **spell id** (not −1) groups with the other effects of that spell;
- an effect with neither is its own group (always adds).

Attack and damage never group by item. For attack, only effects with int1 = 0 are grouped (by
spell id, bonuses and penalties alike); effects that name an attack type are added directly.
Ability *penalties* from the same spell or item **add up** instead of taking the largest. The
walker keeps up to 36 groups per sign; further groups are dropped. (high; [combat.md](combat.md)
4.2 term 9 states the same for attack)

Damage effects store an iprp_damagecost.2da row in int0: rows 1–5 are flat amounts, rows 6+ roll
`NumDice`d`Die` (`NumDice` × `Die` when the caller asks for maximum damage). Effects that name an
attack type (int5 ≠ 0, which only the item-property handlers set, 1.12) are added per damage type
straight into the attack's damage record, after the target's immunity and resistance; they are
the only effect damage that reaches the hit. Effects with int5 = 0 (every script
`EffectDamageIncrease/Decrease`) are grouped by spell id and damage flags and only counted in the
return value, which `GetDamageRoll` does not add to the damage ([combat.md](combat.md) 6.1 term 8).
Within a group the `Rank` column is meant to pick the larger entry, but the code compares the
stored entry's Rank with the Rank of the last attack-typed increase read in the same call (0 if
none), so normally the first effect of a group stays. (med: static reading, needs a runtime check)

**AC** is not summed this way. The AC handlers write per-type fields in the stats when the effect
is unconditional (any race, int3 and int4 = 0) and the amount is at least 1: dodge bonuses **add**
into +0x100 (penalties +0x101); natural +0xfe, armour enchantment +0xf8, shield enchantment +0xfc
and deflection +0xfa keep only the **highest** (penalties +0xff, +0xf9, +0xfd, +0xfb). Applying a
non-dodge bonus while that field is already above 0 sends feedback 0xbd–0xc0 (natural, armour,
shield, deflection), whether or not the new value replaces it. On removal the highest remaining value is recomputed by walking the list; dodge
just subtracts. Conditional AC effects (versus race/alignment) are evaluated by the attack code.
AC decreases are refused for plot creatures and by immunity 23. (high)

**Movement speed.** The creature's speed factor (+0xa08) is read through
`GetMovementRateFactor` (`0x004ec370`), clamped to [0.125, 1.5]. Applying an increase first turns
int0 below 100 into 100 + int0 (so "50" means 150 %), then multiplies the factor by int0/100; a
decrease (refused by immunity 24, plot, or int0 ≥ 100) multiplies by 1 − int0/100. Removal
recomputes from scratch as 1 + Σ(increase int0)/100 − Σ(decrease int0)/100 over the remaining
effects other than those with the removed effect's id — note this mixes the two conventions (an
increase stored as 150 adds 1.5); with the clamp the visible result for one haste is still 1.5.
Reproduce as observed. (high)

**Force resistance.** FR = stats +0x11f (bonus) − +0x120 (penalty), not below 0
(`GetForceResistance` `0x005a5a60`). An FR increase (int0 capped at 128) sets the bonus to int0
when int0 exceeds the current FR; a decrease (refused by immunity 26 and for plot creatures) sets
the penalty to max(penalty, int0). So FR does not stack: the highest wins. (high) Removal does not
recompute cleanly: removing an increase (`0x004e2570`) sets the bonus to the highest remaining
increase **minus** the int0 of the last remaining decrease in list order, and removing a decrease
(`0x004e2650`) sets the penalty to the highest remaining **increase** (decreases are ignored), so
with mixed FR effects the value after a removal is off. (med: confirmed in the asm, effect in play
needs a runtime check; reproduce as observed)

**Temporary hit points** add to object +0xe4, which `GetCurrentHitPoints` (`0x004caec0`) adds to
current HP. Removal subtracts them (floor 0); if that leaves the creature newly dead or dying, the
remove handler (`0x004d9320`) applies a blood visual (appearance.2da `BLOODCOLR` R/G/Y → vfx
158/159/160) and an instant DEATH (int1 = 1, no creator) at once. **Temporary Force points** add to
stats +0x126. (high)

### 1.8 Immunity

`CSWSCreatureStats::GetEffectImmunity(type, versus)` (`0x005a6960`) walks the IMMUNITY effects
(0x16) and answers yes if one has int0 = 0 (all) or the asked `IMMUNITY_TYPE_*`, int1 = any race or
the versus creature's race, and int2 = 0 or the versus creature's alignment group (good-evil < 41
→ 3, 41–59 → 1, ≥ 60 → 2). Handlers ask it with the creator as versus. (high)

`GetIsImmuneToEffect(effect)` (`0x005a6a90`) is the table-driven variant used by SETSTATE: it maps
the effect to a gameeffects.2da row (`0x005a5aa0`), and for each of the 33 immunity columns
(immunity types 0–32) set in that row asks `GetEffectImmunity` **without a versus creature**, so
only immunities with race "any" and alignment 0 count; the first hit sends the matching "immune"
feedback (ids 0x7d–0x92) to the target and the creator and returns 1
(a hit on a type without a feedback id returns 1 silently). LINK and VISUALEFFECT skip the table;
when nothing hit, it recurses into the link children. (high)

Plot creatures (object +0xf8) refuse ability, attack, AC, movement, saving-throw, skill and Force
resistance decreases, entangle, knockdown and poison outright; the DEATH effect does nothing to
them. (high)

### 1.9 Removal, death, healing, poison

- **RemoveEffect (script)** (`0x0054ae40`): marks every listed effect with that id as not exposed
  and queues event 14 (REMOVE_EFFECT) for the target; the event handler calls
  `RemoveEffectById` (`0x004d06c0`). The removal therefore happens on the next AI update, not
  inside the script. (high)
- **RemoveEffectById** removes every effect with the 64-bit id: for each, the remove handler, and
  only if it returns 1 (types without a handler count as 1) unlink from the list, creature hooks
  (slots 54 and 55), free, and drop the target from the creator's affected list; an effect whose
  remove handler returns 0 stays. `RemoveEffect(effect)` (`0x004d05c0`) does the same for one
  effect. (high)
- **ClearAllEffects** (`0x00545d40` → `RemoveAllEffects(0)` `0x004d0940`) on `OBJECT_SELF`:
  removes, last to first, every effect except duration types 3 (equipped) and 4 (innate) and
  SETSTATE_INTERNAL, then makes the object commandable (only if it had any effect). With its
  argument set it also keeps effects the object created itself. Removing a party member
  (`0x00565560`) and surrendering (`0x00518990`) call it too. (high)
- **Runaway guard**: `RunActions` warns (feedback 0xa2) above 500 effects and above 1000 (0xa5)
  calls `RemoveEffectsByDurationType` (`0x004d0870`) for temporary, then permanent effects; each
  call removes at most 21 effect ids, so the list shrinks over several updates. (high)
- **Item effects** (duration type 3, creator = item): unequipping runs `RemoveItemProperties`
  (`0x00553c30`: the remove handler of each property in the item's passive-property list (`+0x24c`/`+0x254`), then `RemoveEffectsByCreator(item)`
  `0x004d0820`). That loop advances its index even after a removal, so an effect of the same item
  directly behind a removed one is skipped. (high for the code; med for the consequence, needs a
  runtime check)
- **DEATH (0x13)** (`0x004e0ac0`, [combat.md](combat.md) 8.2): nothing for plot objects; Min1HP
  objects go to 1 HP. For a creature: refused with feedback 0x7f if the effect is magical, has a
  spell id and the creature has death immunity (32, against the killer); otherwise award kill XP
  (4.2), end the combat round, run OnDeath (+0x280), play a random death animation, clear the AI
  state mask, set HP to −11 if higher, and remove **every effect except** duration types 3/4 and
  those `0x004df420` keeps: effects whose script type is listed in removefxondeath.2da
  `EffectType` (62 disguise, 21 beam) and, for the beam row, visual effects whose vfx is one of
  the beam visuals (`0x004ca960`). Unless it is a downed party member, the body is then destroyed
  after appearance.2da `DestroyObjectDelay` (default 3 s) — the rest belongs to
  [combat.md](combat.md). Placeables and doors play their death animation, get an ON_DEATH script
  event (10) at once and are destroyed (event 11) 2 s later. (high)
- **HEAL (0x27)** (`0x004e0750`): int1 = 0x36 heals Force points instead (current + temporary FP
  clamped to max FP, feedback 0xe4). Otherwise: refused for dead or dying creatures, adds int0 up
  to max HP (with bonus), feedback 0x97 to target and healer, and removes the target's temporary
  0x54 effects (low: unknown type). (med)
- **POISON (0x23)** (`0x004db320`): the handler always keeps the effect and refuses by queuing its
  removal (event 14, no delay): for plot, dead or dying creatures, a creature already poisoned
  (+0x9e0 = 1: **one poison at a time**), immunity 2 against the creator (feedback 0x3e to both
  sides), or a passed save. Otherwise it stamps the start time (int1, int2) and rolls a
  **Fortitude save, type 12 (poison), DC = poison.2da `DC_SAVE`**, against the creator. On a
  failure: feedback naming the poison (`Name`), sound-set entry 0x1c, tick 1, int3/int4 = the
  start time, int5 = `DURATION` s, int6 = `PERIOD` s, float0 = 2 (next tick number), and the
  effect becomes temporary with Duration = `DURATION` × 1000 s, so the generic expiry never ends
  it first (UpdateEffectList's own int5 check does, 1.6); then an instant poisoned visual (vfx
  1003) and the poisoned flag (+0x9e0 = 1, +0x9e8 = the effect id, cleared by the remove handler
  `0x004db810`). Loading a game re-applies only the visual and the flag. (high)
  Tick n (`ApplyPoisonTick(row, effect, bLoading, n)` `0x004ee770`, poison.2da row int0):
  `DAM_HP` > 0 → a DAMAGE of `DAM_HP` in damage slot 13 (flags 0x2000, outside the script damage
  types), queued as APPLY_EFFECT (event 5); `DAM_FP` > 0 → DAMAGE_FORCE_POINTS of `DAM_FP`,
  applied at once; each `DAM_STR` … `DAM_CHR` > 0 → the poison's previous ABILITY_DECREASE of that
  ability (same spell id) is removed and a new one of n × `DAM_x` applied, temporary for
  `DURATION` − (n − 1) × `PERIOD` s (skipped once that is not positive). So ability damage grows by
  `DAM_x` per tick and wears off when the poison would have ended. (high)

### 1.10 Crowd control

**SETSTATE (0x08)** carries the state in int0 and a cutscene flag in int1. Apply
(`0x004e1c20`), in order (high unless marked):

1. If not cutscene: `GetIsImmuneToEffect` (gameeffects.2da rows STUN, SLEEP, CONFUSED, HORRIFIED,
   …) → refuse (return 1).
2. The creator's current attack record gets the state number (+0x12d). Per-state immunity
   (asked with the creator as versus) refuses with an "immune" feedback to the creator and the
   target, sets that attack record's +0x138, and returns 1:

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
   SETSTATE_INTERNAL, and apply a new innate SETSTATE_INTERNAL (0x09) carrying the state, the
   creator and the spell id. So when several states overlap, **the highest-numbered one is
   active**.

**SETSTATE_INTERNAL (0x09)** (`0x004da330`): for every state but 9, makes the creature briefly
commandable, `ClearAllActions`, clears its combat round's scheduled actions
(`ClearScheduledActions` `0x004d3770`), and leaves it
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
(`0x004da870`): for states 1 and 3–10 run the creature's **OnEndCombatRound** script (+0x260, so
the AI picks up again); for those and states 12/13 refresh the animation; then, unless +0x9d4 is
set (the player character, [combat.md](combat.md) 2), drop its perception list except its own
entry (`0x005178f0`) and rebuild perception (`UpdatePerception`). (high)

**Others** (high unless marked):
- **ENTANGLE (0x12)**: immunity 10; not for plot. Clears actions and adds −2 attack (misc), −4
  DEX and AI mask −move. Casting a spell while entangled is interrupted (3.3).
- **KNOCKDOWN (0x14)**: immunity 28 (feedback 0x81); not for plot, dead or dying. Pauses the
  combat round (`SetRoundPaused`, `SetPauseTimer`), adds an AI-state child clearing bit 0x100
  that lasts the duration + 1.5 s, makes the creature uncommandable and
  plays the knockdown animation (a different one when hit from behind, facing dot < 0.707). (med
  for the animation choice)
- **SLOW** is refused by immunity 9; **DEAF** by 8; **SILENCE** by 11; **CURSE** by 17.
- **Force push / whirlwind / choke / horror / stun / stasis** are scripted as SETSTATE, FORCE_PUSH
  and DAMAGE effects plus saves in `k_sp1_generic` (its code is in `k_inc_force`; 3.4).

### 1.11 Visual effects, icons, alignment mastery

- **VISUALEFFECT (0x1e)** (`0x004daa40`): int0 visualeffects.2da row, obj0 source (the creator
  when unset), obj1 beam target, int1 a byte passed along, int2 = 1 a miss. If the effect has a
  duration, is not a miss, and the row's `Type_FD` is not `F` (fire-and-forget), it is attached
  to the object as a persistent visual (`0x004cf390`, list at +0x130) and kept (return 0) until
  removed (`0x004dadc0`). Otherwise it is not kept (return 1) and a one-shot visual is sent to the
  client when the player creature is within 252 m (skipped for a beam visual, `0x004ca960`, whose
  source no longer exists). Miss visuals are offset to a point beside the target
  (`0x004cbc00`). (high)
- **ICON (0x43)** (`0x004e4790`): adds effecticon.2da row int0 (`IconResRef`, `Priority`, `Good`)
  to the creature's icon list (+0x8f4/+0x8f8, ordered by `Priority`) unless already there;
  removal (`0x004e30d0`) takes it out unless another ICON effect with the same row remains. The
  HUD draws this list. `SetEffectIcon(e, icon)` is just `Link(Icon(icon), e)`, so the icon lives
  exactly as long as the effect. Instant effects get no icon and are not kept. (high)
- **Alignment mastery**: `UpdateAlignmentMastery` (`0x00501d90`) applies an innate
  LIGHT_SIDE_MASTERY (0x6c) at good-evil 100 and DARK_SIDE_MASTERY (0x6d) at 0, removing the
  other; at any other value it removes both. The handlers (`0x004dee90`, `0x004df160`) add
  children for every Jedi class slot of a creature that has its own client object (the
  player-controlled character; med for that reading): light — Guardian +3 STR, Consular +3 CHA
  (FP pool adjusted), Sentinel +3 CON (HP adjusted); dark — Consular +50 to the current Force
  points (once, not the maximum), Guardian two DAMAGE_INCREASE children of iprp_damagecost row 8
  (1d8, damage flags 3) for attack types 1 and 2, Sentinel an IMMUNITY child for poison (2). Every
  creature with the effect gets icon row 60 (MAX_GOOD_ICON) or 61 (MAX_EVIL_ICON). (high)

### 1.12 Item properties

Equipping an item runs each of its properties through the item property handler
(`ApplyItemProperties` `0x00553bb0` → `CServerAIMaster`+0x5c, `OnItemPropertyApplied`
`0x004e5410`, 0x3c types), which builds ordinary effects with duration type 3 and the item as
creator, and applies them. That is why item save, ability and skill bonuses obey the per-item
"largest wins" rule of 1.7 and why item effects survive ClearAllEffects and death. Property
types are in itempropdef.2da; the per-property handlers (`0x004e5490`…`0x004ea800`) were not
read one by one. (high for the mechanism)

Example, `ApplyEnhancementBonus` (`0x004e5490`, properties 5–7: enhancement, versus alignment
group, versus race), nothing when the `Value` of `iprp_meleecost.2da` at the property's cost value is 0 (the handler reads that table whatever the property's CostTable byte says;
[party-items-saves.md](party-items-saves.md) 4.6): one
ATTACK_INCREASE with int0 = that value and int1 = the attack type of the equipment slot (right
hand 1, left hand 2, the three creature-weapon slots 3–5, the hands slot 7), and one
DAMAGE_INCREASE with the same int0 (an iprp_damagecost row, so values 1–5 are flat), int1 = the
weapon's damage flags and int5 = the same attack type; the versus variants fill the alignment
(int3/int4) or race (int2) filter. A double-bladed base item gets a second copy of each for
attack type 2. Because these name an attack type, they bypass the grouping of 1.7 and are the
effect bonuses that reach the attack and damage rolls. (high)

### 1.13 Energy shields (`EffectForceShield`)

The forearm bands, the droid utility and hazard shields and the plot shields all apply
`EffectForceShield(row)` (routine 459, `0x00532690`: type 0x6b, int0 = a row of forceshields.2da,
no range check). The impact script of the item abilities (`k_sup_bands`: spells.2da 99-107, the
bands, are rows 6-14; 110-115, the droid shields, rows 0-5) links an effect icon to it
(`SetEffectIcon`, icons 45-54) and applies it for 200 s to the spell's target. Of the plot
shields, `k_pman_shield_9` applies row 18; `k_act_com44` puts row 5 on itself for 5000 s. (high)

**`OnApplyForceShield` (`0x004df540`).** It runs before the new marker joins the effect list
(`ApplyEffect` inserts an effect only after its apply handler has accepted it), so any type-0x6b
effect it finds is an earlier shield. In order (high):

1. Anything but a creature (and a null effect) is kept as it is (no children).
2. **The old shield goes.** Through the creature's client object, a helper (`0x00616890`: from
   the client creature back to the server one, int0 of its first type-0x6b effect, 0 for none)
   gives the row of the shield already worn; if it is **not 0**, the creature's first type-0x6b
   effect is removed by id, which takes everything sharing its id with it: the old marker, aura,
   resistance and the effect icon of the same link. So a shield of row 0 (the weakest droid
   shield) is invisible to this check, and a second shield simply stacks on it. A creature
   without a client object skips the check as well.
3. The row is read by its label (the decimal text of int0; the labels equal the row numbers):
   `VisualEffectDef`; then `Appearance_01`..`Appearance_04` in turn, the first whose value equals
   the creature's appearance (16 bits, creature +0xa60) replaces the aura column by the matching
   `VisualEffect_0N`; `DamageFlags`, `VulnerFlags`, `Resistance`, `Amount`, and `Permanent`.
   `Permanent` is read into a local nothing uses (every row has Permanent 0), and `DefaultRadius`
   is not named anywhere in the exe: both are dead columns. `Radius_0N` is not read here; only
   the client's bolt drawing reads it (see "A missed bolt").
4. Two children are made with `CGameEffectFromParent` (the shield's id, duration kind and
   length, expiry, spell id; not exposed), their creator set to the creature itself, and applied
   with `ApplyEffect`: a **VISUALEFFECT** (0x1e) with int0 = the aura, and a **DAMAGE_RESISTANCE**
   (0x02) whose subtype is forced to magical, with int0 = DamageFlags, int1 = Resistance,
   int2 = Amount, int3 = VulnerFlags.
5. It returns 0: the marker (0x6b) stays in the list, a plain passive effect.

The remove handler is the shared "return 1" stub (`0x004df410`): nothing happens on removal beyond
the children's own (the aura is taken off, 1.11). Since all four leaves have one id, the shield
ends as a unit: when its time is up (`UpdateEffectList`, 1.6), on death (1.9), by ClearAllEffects,
or when its points are used up. On loading a save the non-exposed children are skipped
(1.1) and the marker rebuilds them, so a half-used shield comes back with its full Amount (med:
inferred from `SkipOnLoad`, not observed).

**What it stops.** Everything is the limited resistance of `DoDamageResistance` (`0x004d0e40`,
combat.md 6.4); the numbers of the rows are:

| Column | Meaning | Values |
|---|---|---|
| DamageFlags | the damage types it stops | 6208 = blaster 4096 + ion 2048 + light side 64 (the plain shields, rows 0-2, 6, 12, 13, 16-18); 7232 adds sonic (Sith, Echani); 7520 adds sonic, fire, cold (hazard shields, Arkanian, Verpine, antique droid); 2055 = ion + bludgeoning, piercing, slashing (Mandalorian melee, row 10); 6215 = 6208 + the three physical (Mandalorian power, row 11) |
| VulnerFlags | types that wear the points down twice as fast | 2048 (ion) in every row |
| Resistance | the most one hit's damage can lose to it | 300 in every row: a hit is absorbed whole |
| Amount | the points the shield holds | 20, 30, 50 for the droid shields (rows 0-2 energy, 3-5 hazard), 20 the band (row 6), 30 Sith, 40 Arkanian, 50 Echani, 20 Mandalorian melee, 30 Mandalorian power, 60 and 100 the dueling shields, 120 Verpine, 110 antique droid, 300 / 400 / 300 the plot shields |

How a hit meets it: the strongest matching resistance (largest int1, the first on a tie) is chosen
by the damage's type mask; if **any** DAMAGE_RESISTANCE effect lists one of the types in its int3
the hit counts double (`drain = 2 x damage`). With Amount (int2) above 0: if `Amount - drain < 1`
the shield absorbs what is left of its Amount and is removed by id (the rest of the damage goes
through); otherwise Amount drops by `drain` and the damage is absorbed up to Resistance. The
points therefore count down by the **whole damage** of each hit, not by what was absorbed (an
ion hit by twice that), and the hit that breaks the shield is absorbed only by what remained.
Types outside DamageFlags (electrical, dark side, acid, universal for every row) pass untouched.
Immunity is applied before and reduction after, as for any resistance (combat.md 6.1), and the
same call then takes 2 off for Improved Toughness and 2 for Wookiee Endurance (combat.md 6.4). The
combat log gets feedback 0x42 with the points absorbed and the points left (0x3f when the
resistance has no limit); we do not print it. (high for the arithmetic, med for the messages)

**A missed bolt.** `GetCanDeflectProjectile` (`0x005b78e0`) has a second branch, taken by
`ResolveRangedAttack` for a ranged attack that missed (result 4-6) and whose defender is not a
Jedi guarding himself (no Jedi Defense feat, or debilitated, or dying): if the defender wears a
shield by the helper above (row != 0) and the weapon in the shooting hand (slot 0x10, or 0x20 for
the left hand) has an ammunition type whose `ShieldHit` (ammunitiontypes.2da; 1 for Blaster,
Sonic and Bowcaster, the red, `_s` and `_bc` bolts; 0 for Ion and Disruptor, blue and white) is
set, the attack result becomes 10 and the bolt is drawn flying to the target
(`SetRangedHitPoint`) with no damage. No weapon in that slot means no shield hit. The client's
bolt drawing (`0x006501b0`) stops a result-10 bolt short of the target by a radius: it scans
`Appearance_01`..`_04` of the shield's row (by the same helper) for the target's appearance and
reads the matching `Radius_0N` (1, 1.5 or 2.5 for the droid rows); no match, or a row without
those columns, gives 0. The same helper picks the "forcefield" column of weaponsounds.2da
(`forcefield0`/`1` at random) for the hit sound on a shielded creature (`0x00617470`). (high for
the branch and the columns read, med for how the radius and the sound show on screen)

**Aura.** The aura is a duration visual (visualeffects.2da `Type_FD` D). The default one of every
row but 15 is an engine-coded effect (`progfx_duration` 1413-1421, no model in the 2DA); row 15 and
the four droid appearances (59, 60, 61 and 65, for rows 0-5 and 15-18) get a model on the root node
(`v_fieldmrk*_dur`, `v_fieldmk*b_dur`, `v_fieldsp*_dur`). The 2DA's `soundimpact` /
`soundduration` / `soundcessastion` give the sounds of putting it on, keeping it and taking it
off. (high for the structure, low for what the engine-coded effects draw)

Our library (`lib/rules/shield.ctx`, `effects.ctx`): the same two children, one id (the creator
of the children stays the caster: the library does not know its creature's object id), removal
of the spent resistance by id, the miss branch in `combat_finish_miss`.

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
`savingthrowtable` 2DAs (`CLS_ST_*`, named by classes.2da `SavingThrowTable`) loaded by
`CSWClass::LoadSavingThrowTable` (`0x005bd480`): rows 0–59 of `FortSave`, `WillSave` and `RefSave`
go into three 60-byte tables at class +0x57, +0x93 and +0xcf, and the getters (`0x005bccd0`,
reflex `0x005bccf0`, will `0x005bcd10`) read entry level−1 for levels 1–60, 0 otherwise. The
shipped tables have 20 rows; rows past the end read the 2DA's default, 0. (high)

**Helpless** (`GetIsHelpless` `0x005b4880`): debilitated (+0x8ed, set by SETSTATE), or a member of
the client's party down at 0 HP or less (`GetIsDying`). (high)

Effects are category 3 of `GetTotalEffectBonus` (1.7), filtered by save and save type, ±20. In
the value functions the save type passed is 0, so only effects for every save type (int2 = 0)
count; type-specific ones count only in the roll (2.2). The sum is a signed byte.
`GetFortitudeSavingThrow` & co. (routines 491–493) call them with bExcludeEffects = 0, so for
creatures they return the value **with** those effects; for doors and placeables they return the
`Fort`/`Ref`/`Will` bytes (door +0x2bc/+0x2bd/+0x2be, placeable +0x314 fort, +0x316 reflex, +0x315
will), 0 for anything else. (high)

### 2.2 The roll

`CSWSCreature::SavingThrowRoll(save, DC, saveType, versus, …)` (`0x005b92b0`), used by
`FortitudeSave`/`ReflexSave`/`WillSave` (`0x005421e0`, routines 108–110), poison, disease (the
first save and the later ones from `UpdateEffectList`, `0x004f6790`), sanctuary (when applied, and
the Will save of a creature facing it in `GetIsHiddenFrom` `0x00501950`, combat.md 5),
`GetReflexAdjustedDamage` and the combat code (special attacks, on-hit effects); the script
routines return 0 for non-creatures. A save number other than 1–3 returns 0 at once. (high)

```
base   = Get<Save>SavingThrow(bExcludeEffects = 1)
bonus  = min(GetTotalEffectBonus(3, versus, save, saveType), 20)   # already within ±20
roll   = d20
total  = roll + bonus + base
if total >= DC: return 1                           # no automatic success on 20 or failure on 1
if saveType has an immunity and the creature is immune to it (versus = the versus creature): return 2
return 0
```

Immunity is looked at **only after a failed roll**: a creature that makes its save gets 1 even
when immune. Immunity by save type: mind-affecting (10) → immunity 1, poison (12) → 2, disease (5)
→ 3, fear (8) → 4, trap (14) → 5, death (4) → immunity 32, but only when the saving creature's own
current spell (+0x14c, set only while that creature runs an impact script as the caster, 3.4) is a
Force power or special ability (spells.2da UserType 1 or 2); against another caster's power the
field is −1 and death immunity is not consulted (med: static reading, needs a runtime check). No
shipped KOTOR script uses save type 4 (`nw_s0_lghtnbolt` is a NWN leftover). The routine returns
0 failure, 1 success, 2 immune. A feedback message with save, type, roll, bonus, base, DC and the
target's id goes to the target (when it has a client object) and to the versus creature if that
is another creature, or is attached to the versus creature's current attack record when deferred.
Whenever the versus object is a creature the same numbers and the result also go into its current
attack record (+0x12c..+0x134, combat.md `CSWSCombatAttackData`). (high)

There are no evasion-like feats in the engine's save code: neither `SavingThrowRoll` nor
`GetReflexAdjustedDamage` (half damage on a result of 1 or 2) looks at a feat; Jedi defence feats
act on deflection in combat. (high)

## 3. Force powers

### 3.1 spells.2da as the engine reads it

`CSWSpellArray::Load` (`0x0059ba20`, called from the `CSWRules` constructor) builds 0x198-byte
`CSWSpell` records (`GetSpell` `0x0059b6d0`, array at `g_pRules`+0x8c: row count, then the
array). Every column is read for every row; a column missing from the table reads as 0 (FeatID,
AltMessage) or −1 (Counter2). Columns that drive the rules (high):

| Column | Offset | Use |
|---|---|---|
| `forcepoints` | +0x14e (byte) | base FP cost |
| `goodevil` | +0x14f (first character) | `G` light power, `E` dark power, `-` universal |
| `guardian`, `consular`, `sentinel`, `inate` | +0x3c..+0x3f (byte, 0xff when the cell is empty) | level at which the power is available to Jedi Guardian / Consular / Sentinel; `inate` is the level for every class other than those three and Soldier/Scout/Scoundrel (which never get one) (`0x0059b650`), and gives 2 × `inate` − 1 as a caster level (3.5, 3.6) |
| `usertype` | +0x140 (byte) | 1 Force power (44 rows), 2 special/monster ability (16), 4 item ability (65), −2 disabled (7); only 1 is subject to Force resistance |
| `prerequisites` | string +0x150, ids +0x160 | up to 5 spell ids separated by `_` or `:` (−1 = unused): the upgrade chain (3.7) |
| `masterspell` | string +0x158, ids +0x174 | parsed the same way; also required when learning (6); empty in every shipped row |
| `category`, `maxcr`, `range`, `targettype`, `itemtargeting` | +0x124, +0x128, +0x20 (string), +0x30 (word), +0x194 | AI and targeting |
| `impactscript` | +0x34 | run on the caster at impact |
| `conjtime`, `casttime`, `catchtime` | +0x40, +0xa8, +0xec (ms) | phase lengths of the cast action |
| `castanim` | +0x44 and +0xa6 (word code: self 1, dark 2, up 3, area 4, point/touch 6, throw 7, jump 8, monster 9, else 0) | picks both the conjure and the cast animation (3.3): `conjanim` is **not read**; `catchanim` is read but its value is dropped, so the catch code (+0xf0) stays 0 |
| visuals, sounds, `proj*` columns | +0x46…+0xdc, +0xf4…+0x11d | presentation |
| `forcehostile` / `forcefriendly` / `forcepassive` + `forcepriority` | count +0x130 (byte), array +0x12c | AI categories, each stored as 10 × value + 1000 (hostile), 3000 (friendly) or 2000 (passive) + priority |
| `hostilesetting` | +0x148 (0/1) | whether casting is hostile |
| `featid` | +0x14c (word) | no such column in the shipped table, so always 0 |
| `exclusion` | +0x188 | bitmask (shipped 0x00/0x01/0x02) tested against a caller's mask by two power-list builders (`0x00618c20`, `0x0064a870`) (med) |
| `forbiditemmask` / `requireitemmask` | +0x18c / +0x190 | equipment restrictions (3.3) |

`immunitytype`, `itemimmunity`, `pips`, `dark_recom` and `light_recom` are in the shipped table
but not read by the loader.

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
pool first (stats +0x126), the rest from the current pool (+0x124), never below 0; it never
refuses (it returns 0 only for a missing spell row). (high)

### 3.3 The CASTSPELL action

`CSWSCreature::AIActionCastSpell` (`0x00514af0`, action 0xf; queueing, the instant-cast path, the
round handling and the projectile delay are in [actions.md](actions.md) 3.13): (high, from the
full decompile and the asm)

- Fails if the caster is dead or dying, the spell row is missing, or the target object is gone,
  dead or dying.
- **Equipment check**: the caster's equipped-item mask (`GetEquippedItemTypeMask` `0x004efa80`:
  baseitems.2da `itemtype` 31–36, the six armour classes, set bits 0x01–0x20; 39–41, the
  lightsabers, set 0x40) must not intersect `forbiditemmask` and must contain `requireitemmask`.
  The mask is built by passing 0–17 straight to `GetItemInSlot`, which takes a slot *mask*, so
  only the slots with masks 1, 2, 4, 8 and 0x10 (head, body, hands, right weapon) are looked at:
  a lightsaber held only in the left hand does not count (needs a runtime check).
  22 spells.2da rows forbid 0x3f, so **these cannot be cast in armour**: the self buffs (speed
  burst, knight speed, speed mastery, the three valors, Force armour/aura/shield, resist Force,
  Force immunity), shock, lightning, storm, drain life, death field, plague, breach, suppress
  Force, stasis field and the two disabled jump rows. Push, stun, choke, wound, heal, throw and
  the rest are allowed; Jedi robes and clothing are itemtype 37/38 and never block. Force jump
  and lightsaber throw require 0x40, a lightsaber. A feat
  parameter, if given, must be a known feat.
- Turns to the target point, or takes the target object as interact target; starts (or takes
  over) a combat round paused and shortened by conj + cast + catch time.
- Before conj time has passed: the conjure animation, chosen by the CastAnim code (3.1).
- **Payment once conj time has passed** (first frame with t ≥ conj, once, `+0x960` marks it
  paid): `PayForcePowerCost` (`0x004eddd0`) spends the FP for an ordinary class slot, or, for
  slot 0xfe (special abilities), spends no FP and clears that known-spell entry's flag
  (`SetKnownSpellFlag`) instead. Nothing is paid for slot 0xff (cheat casts), for casts queued with
  the "no Force cost" parameter, or for fake casts. Payment cannot fail for lack of points (3.2):
  the FP check happens only when the cast is queued (actions.md 3.13), so points lost in between
  just floor the pool at 0. If the caster has an ENTANGLE effect (true type 0x12), the cast is
  interrupted (animation 10001, feedback 0x41 unless instant) and fails.
- On that same frame the impact is scheduled: a real cast calls `SpellCastAndImpact`
  (`0x004cdf50`), which sends the "casts" feedback (showing the FP cost), broadcasts the visual
  (`BroadcastSpellVisual` `0x004cdd30`) and posts event 8 (SPELL_IMPACT) to the caster after the
  projectile delay; a fake cast only broadcasts the visual. The cast animation plays until conj +
  cast.
- After conj + cast: a spell with a CatchTime (the two lightsaber throws, 500 ms) plays animation
  10161 and the action **ends as failed** (3) there; otherwise, at conj + cast + catch, idle
  animation, done (2), and, if a feat parameter was given, `0x005a6720` adds one to that feat's
  use counter (med for the counter's meaning).

There is no concentration or arcane-failure roll. FP are lost even if the power then fails a
resistance check. (high)

### 3.4 The impact script

The SPELL_IMPACT event (8; 0x13 for item on-hit spells, from `SignalMeleeDamage` /
`SignalRangedDamage`) is handled by the caster (`CSWSCreature::EventHandler` `0x004fece0`), only
when the payload's caster is the event's sender: it stores the spell id (+0x1c0, `GetSpellId`),
the target object (+0x1bc, `GetSpellTargetObject`) and location (the payload point, or the
target's position when it is a creature in the same area), the item (+0x95c), sets the current
spell id (vtable slot 47, +0xbc, and +0x14c) used by `SetCreator`; for item spells (0x13) it sets
the caster level override (+0x964 = 1, +0x968 = payload caster level) and recomputes the impact
delay; it runs the `impactscript` with **OBJECT_SELF = the caster**, then resets the current spell
id and the override. The spell id and target stay set. (high)

All 44 Force powers and the 16 special/monster abilities use `k_sp1_generic`
(`Sp_RunForcePowers` in `k_inc_force`), which builds the effects itself: it calls
`EventSpellCastAt` + `SignalEvent`, `ResistForce` (in `Sp_BlockingChecks`, together with a link
immunity check), the save routines with a DC obtained from `GetSpellSaveDC` (the one-line helper
`Sp_GetJediDCSave`), `GetHitDice` for scaling, and applies linked effects with icons. Item
abilities use their own scripts (`k_sup_*` and plot scripts). (high, from the shipped source)

### 3.5 DC and caster level

- `GetSpellSaveDC` (`0x0053d320`) → `GetForcePowerDC` (`0x004ef6e0`): **5 + total character level
  (less negative levels) + WIS modifier + CHA modifier**, plus the best of Force Focus (88) +1,
  Advanced (89) +2, Mastery (90) +4. For an area of effect, its creator's DC, or the DC stored on
  the AoE (+0x258) when the creator is gone; 14 for any other caller (placeables, doors). (high)
- `GetCasterLevel` (`0x00536ad0`): for creatures the item-cast override if set, else by the casting
  class slot (+0x1d4): an ordinary slot gives that class's level, slot 0xfe the special ability's
  stored caster level (`GetKnownSpellCasterLevel`), slot 0xff (none or cheat) 2 × `inate` − 1, at
  least 10; for placeables 2 × `inate` − 1, at least 10; for AoEs the same rules applied to the
  creator (creature or placeable) with its current state, 0 when the creator is gone. (high)

### 3.6 Force resistance and immunity

`ResistForce(source, target)` (`0x00541cc0`), used by `k_sp1_generic`; the spell is the source's
current spell (+0x1c0). Caster level: when OBJECT_SELF is an AoE, its stored level (+0x25c); for a
creature source the override, else its total level (negative levels not subtracted), but
2 × `inate` − 1 when it casts from slot 0xff or 0xfe; any other source 2 × `inate` − 1 (no floor
of 10 here). Only creature targets are checked (otherwise 0):

1. Spell immunity (`0x004ccfc0`): an effect of true type 0x32 whose first integer is the spell
   or −1 ⇒ feedback 0x44 to target and source, **returns 2**. (The other helper called first,
   `0x004d13a0`, always answers "undecided".)
2. Otherwise, for UserType ≠ 1 it **returns −1**, which scripts read as true: `Sp_BlockingChecks`
   then treats special and monster abilities (Fire Breath, Sonic Howl) as resisted by every
   creature target (med: static reading, needs a runtime check).
3. For UserType 1: when the target's FR (1.7) is above 0, **resisted if d20 + caster level < FR**
   ⇒ feedback 10 and 0x11 (roll, caster level, FR) to both, returns 1; else 0. (high)

FP damage and healing effects work on the pool "current + temporary": DAMAGE_FORCE_POINTS sets
current = max(0, current + temporary − int0); HEAL_FORCE_POINTS sets current = min(max FP,
current + temporary + int0); FORCE_DRAIN is the damage formula. The temporary pool is left as it
was — a quirk only visible when both are non-zero. (high as read)

### 3.7 Upgrade chains

Power lines are linked only through `prerequisites`: Force Whirlwind requires 23 (Force Push),
Force Wave 23_27 (Push and Whirlwind), Heal requires 10 (Cure), Choke requires 50 (Wound), Kill
50_9 (Wound and Choke), and so on. Knowing the higher power does not remove the lower one; the
level-up code checks prerequisites (and `masterspell`) when offering powers (6, `0x005a7110`).
(high)

### 3.8 Force points: maximum and regeneration

`CSWSCreature::GetMaxForcePoints` (`0x004fd490`), 0 for droids (race 5): (high)

- **The player character** (IsPC and the party is not controlling an NPC, `PT_CONTROLLED_NPC` =
  −1): 0 unless the class in the last class slot is a Force class (3–5); otherwise Σ over the
  level-up history of max(1, `forcedie` + WIS mod + CHA mod) for levels whose record has a Force
  die (classes.2da `forcedie`: Guardian 4, Consular 8, Sentinel 6).
- **Everyone else**: base max FP (stats +0x122, from the template, grown by level-ups) + total
  level × (WIS mod + CHA mod); then 0 unless some class slot is a Jedi class (3–5), and at least
  the total level.
- Both: +40 with feat 116 (Force Sensitive); +50 if a class slot is Jedi Consular (4) and the
  creature has a DARK_SIDE_MASTERY effect (0x6d, 1.11).

**Regeneration** (in `CSWSCreature::AIUpdate`, for alive, not-dying party members, `+0xa88`):
row = regeneration.2da 1 (OutOfCombat) out of combat and also in combat the creature entered by
attacking (`+0xac0` = 2); row 0 (InCombat) only when it was put into combat by being attacked
(`+0xac0` = 1) (combat.md 8.2). Per update: HP gain = `healthregen` % × max HP × dt(ms)/1000;
and, only when max FP > 0, FP gain = `forceregen` % × (max FP + temporary FP) × dt/1000; each rate
at least 0.0001 per second, accumulated in fractional stores (stats +0x1ac / +0x1b0) and added
whole. HP is clamped to max HP; FP are written as current = min(max FP + temporary, current +
temporary + gain), the same temporary-pool quirk as HEAL_FORCE_POINTS (3.6). Shipped values:
health 0/0, force 0/1 — **1 % of the pool per second out of combat or in a fight the party
started, nothing (beyond the 0.0001/s floor) when attacked first, no HP regeneration**. (high)

### 3.9 Alignment

Casting a dark or light power **does not change alignment** in the engine (the cast path only
spends FP), and `k_sp1_generic` never calls `AdjustAlignment`; alignment moves only through
scripts (`AdjustAlignment`, 55 shipped scripts, mostly dialogue; `SetGoodEvilValue` is unused)
and the console commands `addlightside` / `adddarkside` (`0x0060aac0` / `0x0060ab30`). Alignment affects powers only through the
FP cost (3.2) and the mastery bonuses (1.11). (high)

## 4. Experience and level-up

### 4.1 Thresholds and cap

exptable.2da column `XP` rows 0–20 are copied into `g_pRules`+0x38 (`CSWRules::CSWRules`
`0x00552c50`); entry *L* is the XP needed to reach level *L* + 1 (row 1 = 1000 for level 2 … row
19 = 190000 for level 20, row 20 = 0xFFFFFFFF). `CanLevelUp` (`0x005a6810`): total level < the
server's level cap (`CServerExoAppInternal`+0x10004 → +0x94) and XP ≥ entry[level], and not dead
(slot 37) or dying. So the cap is 20 (or lower if the server cap is lower). (high)

### 4.2 Awarding XP

- **The party pool.** `CSWPartyTable::AddExperience(xp, bFeedback)` (`0x005653a0`), only for xp > 0:
  adds to `PT_XP_POOL` (+0xf8), then gives `CSWSCreature::AddExperience` to every NPC in the
  party table's member list (count at +0; the current party, not the whole roster) and to the
  player creature. With client option bit 0x1 (options +8, the auto-level-up option) each **NPC**
  member that `CanLevelUp` is auto-leveled (`AutoLevelUp(1)`, 4.4); the player creature never is
  here. Feedback 0x8f "experience gained" (with xp) to the player creature when asked. (high)
- **Per creature.** `CSWSCreature::AddExperience` (`0x004ef930`): xp × npc.2da `PercentXP` of the
  creature's NPC row (80 for every companion; the player is not an NPC row → 100 %) × row 9
  (`GAME_XP_General`, 100) / 100, **rounded up**, then `CSWSCreatureStats::AddExperience`
  (`0x005af6a0`) → `SetExperience` (`0x005af480`). The stats step keeps NWN's multiclass XP
  penalty (−20 % per non-favoured class two or more levels behind the highest non-favoured one),
  which never fires: racialtypes.2da `Favored` is blank for every race, so the favoured class is the
  highest-level slot and with two slots at most nothing is left behind it. `SetExperience` refuses
  to lower XP (it only logs "Tried to reduce XP …"), so script `SetXP` can only raise it; on a
  rise it re-applies stored history records beyond the current level (`LevelUp(record, 0)`) while
  `CanLevelUp` holds, and sends feedback 0x0b (level-up available) when the creature has a client
  and has just crossed its next threshold. (high)
- **GiveXPToCreature** (routine 393, `0x0053e750`): amount > 0 and a valid creature target, else
  nothing; the target only decides the status-summary plot-XP icon (kind 2, when it is
  player-controlled, `+0xa88`); the amount goes to the whole party through `AddExperience(xp, 1)`.
  (high)
- **Plot XP**: `GivePlotXP(plot, percent)` (`0x00566600`): ceil(plot.2da `XP` of the row whose label
  is *plot* × percent / 100); when > 0, to the party with feedback (`AddExperience(xp, 1)`) and the
  status-summary plot-XP icon (kind 2). Dialogue nodes use `GivePlotXPByRow` (`0x005666e0`, the same
  formula by row index `PlotIndex`) with percent = ceil(`PlotXPPercentage` × 100)
  ([dialogue.md](dialogue.md)). (high)
- **Kill XP** (`AwardKillXP` `0x004fb1e0`, from the DEATH effect; [combat.md](combat.md) 8.3):
  nothing if the victim is the PC (`+0x9d4`) or a party member, or if the Player row of the live
  reputation table at the victim's faction column (`0x0052b420`) is above 10, i.e. it was not
  hostile. Otherwise `GetKillXPValue` (`0x004f19e0`): player level *L* = the highest level whose
  threshold the player creature's XP reaches (not its class levels), value =
  xptable.2da[row *L* − 1][column `c<CR>`] with CR = the victim's truncated `ChallengeRating`
  (stats +0x84; a CR above 20 has no column and gives 0, med), × npc.2da row 9 `PercentXP` / 100;
  if row 10 (`PER_NPC_Bonus`) is > 0 it is multiplied by (1 + bonus/100 × the party table's NPC
  count) (0 in the shipped table, so no bonus). The result is rounded up and added to the party
  **without** the gain message (`AddExperience(xp, 0)`), so each member's share then passes the
  per-creature step above (row 9 is applied a second time there; both are 100 in the shipped
  table). The kill feedback goes to the killer, the creator of a mine that killed, or else the
  player creature (combat.md 8.3). (high)
- **Mod_XPScale** is read from and written to the module IFO (+0x1a6, default 10) but nothing else
  reads it. (med)
- Stealth XP: a pool per area (ARE `StealthXPEnabled`, `StealthXPMax`, `StealthXPLoss`; the current
  amount starts at the maximum and is saved in the GIT's AreaProperties) that the engine lowers when
  someone notices the party (5.3) and `AwardStealthXP` (`0x00508770`) pays to the party with feedback,
  lighting the status summary's stealth XP icon (kind 3), then empties and switches off. The setters
  keep the current amount at most the maximum (`0x00506a80`, `0x00506aa0`). (high)

### 4.3 The level-up record and `LevelUp`

A level is described by a 0x30-byte record (`CSWSLevelStats`, ctor `0x005cb1b0`; the history list
is stats +0x28, `LvlStatList`). `CSWSCreatureStats::ApplyLevelUp(record)` (`0x005af950`) checks
`CanLevelUp` (returns 0 without it), signals script event 37 PLAYER_LEVEL_UP to the module for PCs
(stats +0x6c), then calls `LevelUp(record, 1)` (`0x005aabf0`) and recomputes derived stats
(`UpdateCombatInformation`). `LevelUp`: (high)

1. Append the record to the history (only when the second argument is set; `SetExperience`'s
   replay passes 0).
2. Find the class slot of the record's class (+0x2c) and add 1 to its level; if none, open a new
   slot at level 1 (**multiclassing** is just a record of another class; the stats hold two slots,
   +0x8c and +0xb4, and `LevelUp` itself does not check the count).
3. Max HP (creature +0xe0) += record HP (+0x2b); base max FP (stats +0x122) += record FP (+0x2d).
4. Ability increase (record +0x2a, 0–5): +1 to that score and recompute its modifier as
   (score − 10) / 2 rounded down.
5. Skill ranks += the record's per-skill points; unspent skill points (stats +0x164) = record's
   remainder (+0x28).
6. Add the record's feats; then remove the record's dropped powers from the class slot's known
   list and add its new powers there (no duplicates). For a PC the new powers are added only when
   the slot's class is a Force class; for anyone else always.
7. Current HP = max HP (**a level-up heals fully**); current FP += the change in max FP.

### 4.4 Automatic level-up (NPCs, and everyone with the option on)

`CSWSCreatureStats::AutoLevelUp` (`0x005b27e0`) loops while XP ≥ the next threshold, always in
the **last** class slot, building and applying one record per level: (high unless marked)

- New class level *n* (the slot's level + 1). Every 4th level (*n* % 4 = 0) an ability point in the
  class's preferred ability (classes.2da `PrimaryAbil`, class +0x17a).
- HP = classes.2da `hitdie` (the maximum, no roll); FP = `forcedie`.
- Skill points = stored remainder + (level 1: max(1, `skillpointbase`/2 + INT mod) × 4; later:
  max(1, (INT mod + `skillpointbase`) / 2)). They are spent along the class's skill priority list
  (skills.2da `<class>_reco`, `0x005be430`) on skills the class can use (`allclassescanuse` or a
  `<class>_class` entry) up to rank max (new class level + 3 for class skills, half for
  cross-class, which cost 2 points per rank). The PC (stats +0x6c with no NPC controlled, as in
  3.8) may spend on any of them; anyone else only on skills with skills.2da `npccanuse`, and a
  droid (race 5) also needs `droidcanuse`.
- Feats the class grants at level *n* (feat.2da `<class>_list` = 3 with `<class>_granted` = *n*,
  `0x005be310`) are added straight to the creature (`AddFeat`, not through the record); then as
  many feats as featgain.2da allows (`<class>_REG` general, `<class>_BON` bonus, row *n* − 1,
  `GetNumFeatsToGain` `0x005a6f40`) are picked along the class's feat priority list (feat.2da
  `<class>_recom`) among those with feat.2da `mincharlevel` ≤ *n* that pass `CanSelectFeat` (6).
- For Force classes (classes.2da `SpellCaster`), `GetNumForcePowersToGain` (`0x005a59d0`) powers —
  2 when the slot is at class level 1 *before* this level (so on the step to level 2), else 1
  (classpowergain.2da, which gives Consulars 2 at levels 1, 5, 9, 13, 17, is loaded by
  `CSWClass::LoadSpellGainTable` `0x005bd900` but nothing on this path reads it) — picked along
  spells.2da `dark_recom` when evil (good-evil < 41) or `light_recom` otherwise, among UserType 1/5
  spells, validated by `CanLearnForcePower` (`0x005ac8f0`). That test wants the count still to gain
  above the number already picked, and the count is decremented after each pick, so a second power
  is never taken: one power per level in practice (med: static reading, needs a runtime check; 6.1).
- `ApplyLevelUp`; if it refuses (`CanLevelUp` false) the record is freed and the loop goes on with
  XP and level unchanged, so it would not end if entered for a creature that is dead, dying or at
  the server cap with XP past the threshold (med: callers test `CanLevelUp` first except the
  character-sheet button). With feedback asked, a floating level-up notice over the creature
  (`0x005edea0`, type 4).

Callers: `CSWPartyTable::AddExperience` and `SpawnAvailableNPC` (`0x00565130`) for NPC members when
client option bit 0x1 is on; `AutoLevelUpMembers` (`0x00563b90`, every party NPC that can level)
when that option is switched on (`0x0061b740`); and the character sheet's auto-level button
(`CSWGuiCharacter::AutoLevelUp` → `0x006aec80`), which levels the party leader, PC included, without
feedback. The player's own level-up goes through the level-up GUI ([gui.md](gui.md)), which sends
the choices to the server (`0x00527560`) to build the same record and end in `ApplyLevelUp`. There
is no engine "autobalance" of companions to the player's level; companions in the party earn the
same XP (at 80 %). A companion outside the party earns nothing directly, but when it is spawned
(`SpawnAvailableNPC`) it is topped up from `PT_XP_POOL`: with *f* = its npc.2da `PercentXP` / 100
(1 when the cell is missing or 0), if its XP minus `JoiningXP` (`+0x22c`, [objects.md](objects.md))
is below pool × *f*, it is given pool − (XP − `JoiningXP`) / *f* through `AddExperience` (which
scales by *f* again), so it ends near `JoiningXP` + pool × *f*, then is auto-leveled under the same
option. (high)

### 4.5 Hit points

`CSWSCreature::GetMaxHitPoints` (`0x004ed310`, slot 38): (high)

- **The player character** (same PC test as 3.8): Σ over the level history of max(1, record HP +
  CON mod), + per level 2 with Master Toughness (124) or else 1 with Toughness (84) when
  bonuses are included. Improved Toughness (123) is not tested here, so it adds nothing beyond
  Toughness in this function (med). Base max HP (+0xe0) and Wookiee Endurance are not used. CON
  changes therefore re-price every level.
- **Everyone else**: with *B* = the Toughness bonus (2 or 1, only when bonuses are included) + 2
  with Wookiee Endurance (95, always): base max HP (+0xe0) + level × (CON mod + *B*); but when
  base + level × CON mod is below the level, level × (1 + *B*) instead (at least 1 HP per level
  before the feat bonuses).

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
| Security | OPENLOCK `0x0057d9d0` | Security + security-spike property bonus + (20 or d20) ≥ the lock's `OpenLockDC` (min 1) → unlocked; a door is then opened by the user, a placeable gets USEOBJECT queued only when the actor has stats +0x6c or is the party leader; the spike is spent on success and failure ([actions.md](actions.md) OPENLOCK). The scripts' "can unlock" query (`GetIsDoorActionPossible` `0x00539940`, doors and placeables) answers yes when Security ≥ 1, the target is locked and not KeyRequired, and Security + 20 ≥ `OpenLockDC` | high |
| Security | LOCK `0x0057bec0` | Security + (20 or d20) ≥ the target's `CloseLockDC` (door +0x2c0, placeable +0x275; min 1) → locked | med |
| Demolitions | DISABLETRAP `0x00519570`, RECOVERTRAP `0x00518c40`, FLAGTRAP `0x0050e400`, EXAMINETRAP `0x0050e900` | Demolitions + (20 or d20) ≥ a DC from the trap's `DisarmDC`: disable DisarmDC (min 1; above 35 impossible), recover DisarmDC + 10, flag DisarmDC − 5, examine DisarmDC − 7 (min 1, no 35 cap on these three). Disable and recover need no roll when the trap's creator is the actor, or the creator and the actor are both of the party (or the PC); flag and examine only for the actor's own mine ([actions.md](actions.md) 3.14) | high |
| Demolitions | SETTRAP `0x00519e30` | Demolitions (+2 if base ranks > 4) + (20 or d20) ≥ traps.2da `SetDC` (min 1) | high |
| Awareness | trap detection `DoTrapDetection` `0x004fa390` (every creature's AIUpdate) | every 3 s within 3 m, or every 0.1 s within 20 m in detect mode (or while standing, animation 10000); **detect mode is always on** (activity bit 2, mirrored in `+0x4d0`: set by the constructor and LoadCreature, the GFF `DetectMode` ignored, never cleared), so in practice 0.1 s / 20 m / d10 + 10. Candidates: detectable traps (triggers by the nearest point of their outline, doors and placeables by position) within range, reputation toward the creature below 90, another faction, not yet in the trap's detected list (trigger `+0x2a8`); Awareness + d10 (+ 10) ≥ the detect DC (trigger `+0x2d8`, traps.2da DetectDCMod for a placed trigger; door `+0x2ed`, placeable `+0x276`), or flagged (no roll). A player-controlled finder adds the whole party to the list, anyone else itself; a roll success (not a flagged find) on a **trigger** sends combat message 0x13 (42132 and 42123 in the feedback log) to the clients of the finder's faction in its area; doors and placeables send nothing. No sound, no script event | high (med for the "player-controlled" flag `+0xa88`) |
| Stealth vs Awareness | sight `0x004f1fd0`; hearing `0x004fb4b0` (the one Ghidra names `GetCanSeeStealthed`) | two contests, each side's roll kept for 20 s: 5.3 | high for the terms, med for the wall term |
| Treat Injury | HEAL action `0x00517a60` | roll (20, or d20 when +0x4e0 = 1) + Treat Injury rank against the target. The first poison (0x23) or disease (5) effect in the target's effect list is removed when the total ≥ poison.2da `Save_DC` / disease.2da `Subs_Save` (min 1). With nothing to cure, feedback 0x37, and if the target is also at full HP feedback 0x38 and the action fails. Otherwise one item of the stack is spent and the target heals the total (effect 0x27) ([actions.md](actions.md) HEAL) | high |
| Computer Use, Repair, Persuade | — | used only by dialogue scripts (`GetSkillRank`, 144 shipped scripts) and the computer/repair GUIs; spike consumption is scripted | med |

### 5.3 Stealth and Awareness

How a creature in stealth mode is perceived. The mode itself (entering, leaving, what ends it) is
[docs/mechanics/stealth.md](../mechanics/stealth.md); this is the arithmetic. The individual
perception check (`0x00502ac0`, from `UpdatePerception` `0x0051b050`) asks two questions of a
viewer V about a target T in its area: hearing (`0x004fb4b0`) always, sight (`0x004f1fd0`) only
when T is within the larger of V's sight and hearing ranges (eyes 1.5 m up) with a clear line
(`ClearLineOfSight`); for the player's own creature (`GetPlayerCreatureId`) that gate is skipped,
and the sight test then applies its own range. Two members of the player's (client) party always
see and hear each other; no contest. (high)

**Hidden and blind.** The check also decides whether T is hidden from V by an invisibility-type
effect V cannot see through (`GetIsHiddenFrom` `0x00501950`); it asks only while a player creature
is in V's area, otherwise T counts as not hidden. V's vision bits at `+0x8ec` (set by the effect
handlers): 1 see invisible, 2 ultravision, 4 true seeing, 8 darkness (not applied over ultravision
or true seeing), 0x10 blind. V blind (0x10), or in darkness (8) without ultravision (2), counts as
T hidden. A hidden T is never seen, and is heard only within V's maximum attack range
(`GetMaxAttackRange`) and not when V's perception entry for T has bits 0xc equal to 4. (high for the
code; med for the entry bits' meaning)

**The rolls.** Every creature keeps four bytes: two it hides with (`+0x91c` against sight, `+0x91d`
against hearing) and two it looks and listens with (`+0x91e`, `+0x91f`). The constructor rolls all
four 1..10. Each time the creature's own perception check runs and 20 s of world time (`+0x37c`)
have passed since its last roll, it rolls again: the hiding pair 11..20 (d10 + 10) when it is in
stealth mode itself (left as they were otherwise), the looking pair 1..20 (d20) when it is in detect
mode or standing idle (animation 10000), else 1..10. Detect mode is switched on for every creature
by the constructor and by `LoadCreature`, and nothing in the shipped game turns it off, so in
practice the looking rolls are d20. (high)

**Who hides.** Either contest runs only when T is in stealth mode (`+0x4d1`) and T's Stealth rank
against V (`GetSkillRank(2, V)`: ranks, item and effect bonuses, DEX, feats) is not 0; otherwise V
perceives T as usual (within range). So a creature without Stealth ranks cannot hide, and the stealth
unit's own bonus (item property 36, subtype 2: +2 .. +8) only adds to a creature that has ranks.
(high)

**Sight** (`0x004f1fd0`), within V's sight range (eye heights + 1 m), with a clear line. A hidden T
is not seen. A viewer with true seeing (`+0x8ec` bit 4) sees. Else V's score is

- V's Awareness against T (in full: detect mode, or standing idle; half otherwise) + V's look roll
- − T's Stealth − T's hide-from-sight roll
- − 5 when V is not one of the player's creatures, T is (the client's objects), and T stands behind V:
  the direction from V to T against V's facing below −0.707 (more than 135° off)
- − 10 while V is in combat (`+0x4e0`)
- − 5 while T stands still, + 5 while V stands still (an animation outside the moving set 10002,
  10003, 10004, 10078, 10079, 10084..10087, 10093, 10094, 10133: `0x004cae60`)
- − the whole number of 3 m steps in the distance, only beyond 6 m (d / 3 > 2).

T is seen at 1 or more. When it is and V or T is a client creature, the original sends a feedback
message with all the terms (server message 0x10, the combat log's spot line) to the client-controlled
members of that creature's faction in its area. (high; the feedback's text not read)

**Hearing** (`0x004fb4b0`), within V's hearing range (eye heights + 1.5 m); a target flagged at
`+0x8c8` is never heard. V's score is

- a wall term from two line casts (`ClearLineOfSight`), V to T and T to V, each reporting the
  object it hit and a hit point. Both casts on the same object: −2 in an area whose ARE Flags have
  bit 1 or 2 (interior, underground; the propagation test there, `0x006054e0`, is a stub that
  always passes), 0 outdoors (the code takes the gap as 0.4 m, which truncates to 0). Otherwise the
  gap between the two hit points, each replaced by the hit object's position when it resolves; 0
  m ⇒ 0, else −2 indoors, outdoors −5 per whole metre. The second lookup reuses the first cast's
  object id, so when the first cast hits an object both points are that object's position and the
  term is 0; with nothing in the way both points stay at their zero start and the term is 0. (med:
  the casts write their outputs only on a hit, so the unhit case rests on the callers' initial
  values; needs a runtime check)
- − T's Stealth − T's hide-from-hearing roll + V's Awareness (full / half as for sight) + the area's
  `+0x18c` (ModListenCheck; 0 in every shipped ARE) + V's listen roll
- − 10 while V is in combat, − 5 while T stands still, + 5 while V stands still
- − the whole number of 3 m steps in the distance (from 0 m)
- T's size (`+0x4f8`, creaturesize.2da): tiny − 8, small − 4, large + 4, huge + 8.

T is heard at 1 or more. (high)

**Being found does not end stealth.** A viewer that perceives a hiding creature just has it in its
perception list (and the AI scripts react to the ON_PERCEPTION event); stealth ends when combat
reaches the hider (`AIUpdate`, each tick while it is in combat, `+0x4e0`, with combat reason
`+0xac0` = 1 and stealth not locked in `+0xa00`), when it attacks, casts or speaks, and the other
cases of actions.md 1.4. (high)

**Stealth XP.** A viewer that newly sees the player's character or the party leader (a new entry,
or the seen bit set again) starts a 6000 ms countdown (`+0xaa4`); attacking one of them while the
countdown runs makes it 0xffffffff (charge at once, `ResolveAttack` `0x005bba80`). Its `AIUpdate`
runs the countdown only while the area pays stealth XP (`+0x2c0`; otherwise it clears it); when it
runs out the area's current amount (`+0x2b8`) loses the area's loss (`+0x2bc`, StealthXPLoss), not
below 0 and never above the maximum (`+0x2b4`, `0x00506aa0`). The viewer is anyone, a party member
included: a companion's first sight of the leader in a newly entered area costs the loss too.
(high for the code, med for that consequence, which was not seen in play)

## 6. Feat and power prerequisites

feat.2da is loaded into 0x48-byte `CSWFeat` rows (`g_pRules`+0x90, count +0xa4, `GetFeat`
`0x00550c00`, valid only when flag 0x10 at +0x28 is set). `MeetsFeatRequirements(feat, pending)`
(`0x005afb00`) is called only by `CanSelectFeat` (`0x005b2530`), whose only caller is
`AutoLevelUp`; the GUI's feat screens use their own client-side copies of the same checks
(`0x0064a4c0` / `0x0064a2e0`, [chargen.md](chargen.md) H), which also test `mincharlevel`: (high)

1. The last class's feat table may name a level for the feat (`0x005be220`); total level must reach
   it.
2. `minspelllvl` (+0x32): some Force class slot must have that power level available
   (`0x005bcd60`). The loader reads the column but stores 0 (`0x005515e0`), so this test never runs.
3. `minattackbonus` (+0x2c) ≤ base attack bonus (`0x005a60d0`).
4. `minstr`, `mindex`, `minint`, `minwis` (+0x2e..+0x31) ≤ the **base** scores (no effects).
5. Prerequisite feats (`prereqfeat1/2`, the `orreqfeat0..4` list), counting feats pending in the
   same level-up (`0x005a7230`; 6.1).
6. A required skill (+0x46, `reqskill`) must have ranks (`0x005af880`; 6.1).

`CanSelectFeat` then requires that the feat is not known or pending and that a general or bonus
slot is left: the class feat table says whether the feat is a general choice, a class bonus
choice or both (`GetFeatSelectableAs` `0x005a6fe0`), and the pending choices are matched to slots
greedily (6.1). (high)

Class tables: `CSWClass::LoadFeatTable` (`0x005bd0f0`, from `feat.2da`'s `<class code>_List` / `_Granted` / `_Recom` columns: granted level and selectability
per feat), `LoadFeatGain` (`0x005bcf70`, featgain.2da `_REG`/`_BON` for levels 1–20 into class
+0x150/+0x13c), `LoadSkillsTable` (`0x005bd6c0`, class skills), `LoadSpellGainTable`
(`0x005bd900`: cls_spgn_jedi `NumSpellLevels` per level into class +0x114, classpowergain.2da's
column for the class into +0x128), `LoadSavingThrowTable` (`0x005bd480`), `LoadAttackBonusTable`
(`0x005bcda0`). (high)

Power prerequisites: a power is offered when the class's spells.2da level column (`guardian`,
`consular`, `sentinel`) ≤ the character's total level before the level-up and its `masterspell`
and `prerequisites` are known or pending (`CanLearnForcePower`, 6.1; high). The ability point buy of
character creation is in the GUI, not the rules code ([gui.md](gui.md)). (med)

### 6.1 The level-up helpers read in detail (for lib/rules/progress.ctx and force.ctx)

All of this was read from the decompiled functions named; it refines 4.4 and 6. (high unless marked)

- **Class feat table** (`CSWClass::LoadFeatTable` `0x005bd0f0`): one 8-byte entry per valid feat
  whose `<class>_list` is not 4, in feat order: feat, granted level (`<class>_granted`), a pool
  mask, rank (`<class>_recom`). Pool mask from `_list`: 0 → general only, 1 → general or bonus, 2 →
  bonus only, 3 → granted by the class (mask 0, never selectable). Blank cells read as 0.
  `GetFeatSelectableAs` (`0x005a6fe0`) is bit 0 = general, bit 1 = bonus. Only granted entries
  carry a usable level (`0x005be220`). The table's count (+0x170) is feat.2da's row count, not the
  number of entries kept: the slots after the last kept entry hold feat 0 (the first of them: the
  last skipped row's feat) with mask 0, level 0 and an unwritten rank (med: they can surface in the
  priority list below; needs a runtime check).
- **Priority lists** (feats `0x005be3c0`, skills `0x005be430`, powers `0x005be6d0`) share one
  shape: position *p* returns the entry whose rank is *p*; if none has it, the (*p*+1)-th entry
  with rank 0 in table order, or the last such. Powers: entries are the UserType 1/5 spells, the
  rank is `light_recom` for a character with good-evil above 40, else `dark_recom`.
- **MeetsFeatRequirements** (`0x005afb00`): a granted feat needs the total level to have reached
  its granted level; `minspelllvl` is always 0 after loading, so its test (`0x005bcd60`) never runs;
  BAB (the class tables' sum, or the override at stats +0x102 when set), then
  `minstr/mindex/minint/minwis` against the base scores; both `prereqfeat` entries known or pending;
  the `orreqfeat` list needs at least one named feat to be known or pending (`0x005a7230`; no
  entries, no condition); `reqskill` needs ranks unless skills.2da's untrained flag is set, and
  then one of the creature's classes must be able to use the skill (always true with the shipped
  `allclassescanuse` = 1). **`mincharlevel` is not tested here**: AutoLevelUp compares it with the
  new class level before calling `CanSelectFeat`. The shipped feat.2da uses only `mincharlevel` and
  `prereqfeat1/2`.
- **CanSelectFeat** (`0x005b2530`) has the level's totals (general, bonus) and the feats already
  picked; no slots at all ⇒ no. Pending feats that fit one pool take it first: a general-only one
  with no general slot left fails the candidate, a bonus-only one with no bonus slot left falls
  back to the flexible pass. Then the candidate: one that fits one pool needs it free; a flexible
  one reserves nothing. Then the remaining pending feats take a general slot, else a bonus slot,
  else the candidate fails. It passes when it reserved a slot or any slot is left.
- **CanLearnForcePower** (`0x005ac8f0`): UserType 1 or 5, a nonzero count still to gain, not in
  the known list of the class slot being levelled (the last), not pending, every `masterspell` and
  `prerequisites` spell (`0x005a7110`; the shipped spells.2da fills only `prerequisites`) known in
  any slot or pending, the total level before the level-up at least the class column
  (`FUN_0059b650`: guardian/consular/sentinel columns for classes 3 to 5, 255 for classes 0 to 2,
  `inate` otherwise, for the last slot's class), and the count still to gain above the number
  pending. A known prerequisite counts only while the creature's current + temporary Force points
  cover its cost (`0x005a6e70` is called with its Force-point flag set: `PUSH 1` in the binary;
  med, needs a runtime check). The Force class gate is the caller's (class +0x19c). The last test
  is made with the count already decremented by the caller, so AutoLevelUp can never take a second
  power in one level (med: static reading, needs a runtime check).
- **Powers per level**: GetNumForcePowersToGain gives 2 when the slot is at level 1 *before* the
  level (so for the step to level 2, not to level 1), else 1, and 0 for a class that is not a Force
  user; AutoLevelUp uses it. classpowergain.2da (2 at levels 1, 5, 9, 13, 17 for Consulars, 2 at
  level 1 for the others) is stored per class level at class +0x128 and read by the GUI's level-up
  panel (`0x00649070` → `0x005bcd30`, from `CSWGuiLevelUpPanel`, Jedi classes 3 to 5; med for which
  level the panel passes) and by a stats helper (`0x005a5ee0`, NWN-style with a CHA bonus, called
  from `LevelUp` and `ReadStatsFromGff`; its use was not followed). Our code uses the table.
- **AutoLevelUp skills** (`0x005b27e0`): positions 1 to 8 of the class's skill list; a skill is
  used when the creature has player rules (stats `+0x6c` set and the party table's
  `PT_CONTROLLED_NPC` `+0xf0` is −1), or skills.2da `npccanuse` is set (and `droidcanuse` for a
  droid, race 5); max rank = new class level + 3, halved (rounded down) for a cross-class skill,
  which costs 2 points per rank; `allclassescanuse` or a class entry makes a skill usable; each skill
  in turn takes as many ranks as the cap and the points allow. Points: new class level 1: 4 × max(1,
  skillpointbase/2 + INT mod); later max(1, (INT mod + skillpointbase)/2), plus the unspent points.
  The INT mod is the one kept at stats `+0xf0`, computed from the effective score (base + race +
  effect bonuses, `GetINTStat`) when stats load, effects change or a level-up raises INT.
- **ApplyLevelUp** (`0x005af950`) calls `CanLevelUp` itself and, for a PC, signals the module
  (event 0x25, PLAYER_LEVEL_UP); `LevelUp` (`0x005aabf0`) has no limit on the number of class slots
  and does not add the class's granted feats: AutoLevelUp adds them with `AddFeat` (entries granted
  at the new class level) before choosing. The level record's power removals apply to anyone; its
  new powers are added always for a non-PC, and for a PC only when the slot's class is a Force
  user. `GetMaxForcePoints` is taken before and
  after; the difference is added to current Force points, and current HP is set to the maximum.
- **XP arithmetic** (the constant 0.01 is a single-precision float everywhere): `AddExperience`
  (`0x004ef930`) builds factor = float(NPC percent × 0.01f), then float(row 9 percent × 0.01f ×
  factor), and credits ceil(XP × factor) with the product in double precision: 100 XP at 80 %
  is ceil(79.9999952) = 80, the player's factor is exactly 1. `GivePlotXP` is ceil(XP × percent ×
  0.01f), the integer product first. `GetKillXPValue` (`0x004f19e0`) is row-9 percent × 0.01f × the
  table cell stored as a float; `AwardKillXP` multiplies by (1 + npc.2da row 10 `PER_NPC_Bonus` ×
  0.01f × the party table's NPC count) when the bonus is above 0 (shipped: 0), rounds up, and gives
  the result to the party pool (combat.md 8.3). The party level is the highest level whose threshold
  the player's XP reaches.
- **Spending Force points** (`0x005a55c0`) never refuses: temporary points first, then current,
  floored at 0; `HasEnoughForcePoints` is the gate. The cost multiplication is done in the x87
  unit with the float cell widened, so 20 × 0.9 truncates to 17.
- **ResistForce** (`0x00541cc0`): against a creature target, a first check (`0x004d13a0`) always
  answers −1 (undecided); then spell immunity (`0x004ccfc0`: an effect of type 0x32 whose first
  integer is the spell or −1, feedback 0x44 to target and caster) returns **2**; otherwise a spell
  of UserType other than 1 returns −1, and for UserType 1, when the target's Force resistance is
  above 0, `d20 + caster level < FR` returns 1 (resisted, with feedback messages 10 and 0x11 to both
  sides' clients), else 0. A non-creature target or an unknown spell gives 0. Caster level is the
  override, or the caster's total level (class-slot casts), or 2 × `inate` − 1 (also the level an
  area-of-effect running the script carries, its `+0x25c`).

## 7. Open questions

- Internal types without constructors (0x2b, 0x42, 0x44, 0x45, 0x4d–0x51, 0x53, 0x54,
  0x56–0x59, 0x5e, 0x61) and the exact behaviour of curse, silence, deaf, dispel, sanctuary,
  timestop, force push, lightsaber throw, force jump, disease and the per-property item handlers.
- What the engine-coded shield auras (`progfx_duration` 1413-1421) draw, and the combat-log
  lines for a shield that absorbs (feedback 0x3f / 0x42).
- AI state bits 8, 0x10, 0x40 and 0x100: what each one gates.
- `SkipOnLoad` and object +0x1ec: the exact reload rule.
- Stealth (5.3): what the client's stealth speed (`+0x21c` block `+0x60`) is set from; the spot
  feedback message (server message 0x10) the player's client formats.
- The level-up screens' own feat counts were not read (their power count reads classpowergain.2da,
  6.1).
- Medpacs used as items (their own heal properties) against Treat Injury; the HEAL action itself
  heals roll + rank (actions.md).
- Resting: `Rest` (`0x004fd1e0`) drops stealth and activity bits 4..0x80 (`0x004eb1b0` with 0xf,
  then bits 8..0x80, setting bit 8), signals PLAYER_REST and queues the REST action, which returns
  at once (actions.md); where healing and effect removal on rest happen is not found in the rules
  code.
