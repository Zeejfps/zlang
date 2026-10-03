# Combat in swkotor.exe

How the original engine runs a fight: the combat round and its paired "duel" animations, how many
attacks a creature gets, the attack roll, defense, damage and how it is applied, deflection,
sneak attacks, critical hits, death and party members going down, what the engine does by itself
versus what the AI scripts do, and the combat-log messages. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (see [README.md](README.md)); every claim ends with a
confidence (high = read in the code, med = role clear and detail inferred, low = plausible).
Names are ours, in the engine family's style. Proposed names for every address here are in
`kotor/re/proposals/combat.tsv` (git-ignored scratch, merged into [names.tsv](names.tsv) by the
lead).

Boundaries with the pages written alongside this one:

- [objects.md](objects.md): object model, the creature and stats layouts this page extends, event
  queue, script slots.
- [actions.md](actions.md): the action queue, how ATTACKOBJECT (0xc) walks to its target, the
  combat-step action 0x3f and the player's queued combat actions. This page starts where the
  attack action has a target in range.
- [rules.md](rules.md): the effects system (how effects are applied, stacked and removed), saving
  throws, Force powers, XP and level-up, skills, feat prerequisites. This page only says which
  effect types combat creates and reads.
- [gameloop.md](gameloop.md) (frame, pause, auto-pause options), [gui.md](gui.md) (the combat
  log panel that shows the messages of section 10), [movement.md](movement.md) (targeting),
  [party-items-saves.md](party-items-saves.md) (equipment slots, the body-bag inventory).

All offsets are from the start of the object (creature, stats block, combat round, attack record)
unless a table says otherwise. Creature offsets below `+0x228` are `CSWSObject` members.

## 1. One attack, start to finish

| Step | Where | What |
|---|---|---|
| 1 | `CSWSCreature::AIActionAttackObject` `0x005bbbf0` | the ATTACKOBJECT action, once in range: decide whether the two creatures are *engaged* (paired) and who is *master*, `StartCombatRound` on both, pause the round for the attack animation, then `ResolveAttack` |
| 2 | `CSWSCombatRound::StartCombatRound` `0x004d5f70` | 3000 ms round, number of on-hand and off-hand attacks |
| 3 | `CSWSCreature::ResolveAttack` `0x005bba80` | melee or ranged by the right-hand weapon's `RangedWeapon` |
| 4 | `ResolveMeleeAttack` `0x005bb890` / `ResolveRangedAttack` `0x005bb590` | for each attack of the round: attack roll, special-attack effects, damage roll, impact time |
| 5 | `ResolveAttackRoll` `0x005baca0` | d20 + attack modifier vs. defense, threat and confirmation, deflection |
| 6 | `ResolveDamage` `0x005bb440` → `CSWSCreatureStats::GetDamageRoll` `0x005a9050` | dice, bonuses, critical multiplication, target immunity → resistance → reduction |
| 7 | `CSWSCreature::UpdateCombat` `0x004faf20` (every frame) | runs the round timer and the attack-animation pause; when an impact's time comes, `ApplyAttackImpact` `0x005b8050` |
| 8 | `ApplyAttackImpact` → `SignalMeleeDamage` `0x005b75d0` / `SignalRangedDamage` `0x005b6f30` | queues ON_MELEE_ATTACKED (event 15), a damage effect (event 5, effect type 0x26), on-hit effects, combat-log messages |
| 9 | `CSWSEffectListHandler::OnApplyDamage` `0x004dfa40` → `CSWSCreature::TakeDamage` `0x004f3830` → `CSWSObject::DoDamage` `0x004ccf80` | hit points go down; OnDamaged script; death effect if the target died |
| 10 | `CSWSEffectListHandler::OnApplyDeath` `0x004e0ac0` | OnDeath script, death animation, XP, destroy / body bag |
| 11 | `CSWSCombatRound::EndCombatRound` `0x004d4620` | when the round's time is used up: OnEndRound script, which (in the shipped AI) issues the next attack |

## 2. Data structures

### CSWSCombatRound (0x9d8 bytes at creature `+0x9c8`, ctor `0x004d5cb0`)

Labels are the GFF field names `SaveCombatRound` (`0x004d3ec0`) writes into `CombatRoundData`; the
loader is `0x004d5120`. (high unless marked)

| Offset | GFF label | Meaning |
|---|---|---|
| `+0x004` | AttackList | attack records, 0x14c bytes each; the constructor builds 7, but every reset, save and load touches only the first 5 (med) |
| `+0x918/+0x91c` | SpecAttackList | ushort array of queued special attacks (pointer, count) |
| `+0x924/+0x928` | SpecAttackIdList | ushort array |
| `+0x930` | AttackID | ushort |
| `+0x934` | RoundStarted | |
| `+0x938` | SpellCastRound | the round is a Force power / item cast, not attacks |
| `+0x93c` | — | set with SpellCastRound (`0x004d28b0`) (med) |
| `+0x940` | — | "cutscene attack" flag (StartCombatRound's 5th argument, the ATTACKOBJECT node's first parameter); suppresses OnEndRound (med) |
| `+0x944` | Timer | ms elapsed in the round |
| `+0x948` | — | the current target is debilitated (set when animations are resolved) |
| `+0x94c` | RoundLength | 3000 at start, shortened by attack animations (section 3.4) |
| `+0x950` | OverlapAmount | how far a round may be stretched to fit an animation (≤ 1000 ms) |
| `+0x954` | BleedTimer | |
| `+0x958` | RoundPaused | the round's timer is frozen while an attack animation plays |
| `+0x95c` | RoundPausedBy | object id |
| `+0x960` | PauseTimer | ms left in the current attack animation |
| `+0x964` | InfinitePause | the pause lasts until someone else releases it (a slave waiting for its master) |
| `+0x968` | — | actions started this round |
| `+0x96c` | CurrentAttack | index of the attack record being resolved |
| `+0x970` | — | the current attack is an off-hand attack |
| `+0x974` | AttackGroup | byte, starts at 0xff and counts ranged volleys |
| `+0x978` | DeflectArrow | set to 1 at round start |
| `+0x97c` | WeaponSucks | 0 at round start |
| `+0x980` | ParryIndex | |
| `+0x984/+0x988` | NumAOOs / NumCleaves | reset to 1 at round end and never used otherwise (section 7) |
| `+0x98c` | NewAttackTarget | retarget request picked up by the attack action |
| `+0x990/+0x994` | OnHandAttacks / OffHandAttacks | |
| `+0x998/+0x99c` | OffHandTaken / ExtraTaken | |
| `+0x9a0` | AdditAttacks | |
| `+0x9a4` | EffectAttacks | extra attacks from effect type 0x2c, clamped to 0..2 (`0x004dbd90` / `0x004dbe00`) |
| `+0x9a8` | ParryActions | byte |
| `+0x9ac` | DodgeTarget | object id |
| `+0x9b0` | SchedActionList | linked list of 0x88-byte scheduled combat actions (below) |
| `+0x9b4` | — | owning creature |
| `+0x9b8` | Engaged | the round is paired with another creature's |
| `+0x9bc` | Master | this creature drives the pair |
| `+0x9c0` | MasterID | id of the pair's master |
| `+0x9c4` | — | id of the pair's slave (master side) |
| `+0x9c8` | — | the scheduled action being executed |
| `+0x9cc` | — | the round's target (INVALID when attacking oneself) |
| `+0x9d0` | — | type byte of the scheduled action being executed |

### CSWSCombatAttackData (0x14c bytes)

GFF labels from `SaveData` (`0x004d2210`) / `LoadData` (`0x004d2450`); `Reinitialize` is
`0x004d3010`. The bytes from `+0xc0` on are the numbers the combat log shows (section 10) and are
filled as the roll is made. (high unless marked)

| Offset | Label / meaning |
|---|---|
| `+0x00` | AttackGroup (byte) |
| `+0x08` | AnimationLength (ushort, ms) |
| `+0x0c` | ReactObject (the target) |
| `+0x10` | ReaxnDelay (ms; for ranged shots the bolt's travel time) |
| `+0x12` | ReaxnAnimation (the target's reaction: 10014 hit, 10011 miss, 10012 deflected, 10001 none) |
| `+0x14` | ReaxnAnimLength |
| `+0x18` | MissedBy |
| `+0x1c` | DamageList: 15 shorts, one per damage-type bit 0..14 (−1 = none) |
| `+0x38` | total damage (short) |
| `+0x3a` | WeaponAttackType (section 4.1) |
| `+0x3b` | AttackMode |
| `+0x3c` | Concealment |
| `+0x40` | RangedAttack |
| `+0x44` | SneakAttack |
| `+0x48` | KillingBlow |
| `+0x4c` | CoupDeGrace |
| `+0x50` | CriticalThreat |
| `+0x58` | AttackDeflected |
| `+0x5c` | AttackResult (section 4.4) |
| `+0x64` | AttackType: the combat feat used (0 = plain attack) |
| `+0x68..+0x70` | RangedTargetX/Y/Z |
| `+0x74` | AmmoItem |
| `+0x78` / `+0x80` | AttackDebugText / DamageDebugText (filled only when the debug flag `0x008327e4` is set) |
| `+0x88` | effects to apply to the target on impact (array of `CGameEffect*`, count `+0x8c`) |
| `+0x94` | item on-hit spell impacts (count `+0x98`), queued as event 19 on the attacker |
| `+0xa0` | feedback messages to send on impact (count `+0xa4`) |
| `+0xac` | impact list: 0xd0-byte records, count `+0xb0` (section 3.4) |
| `+0xc1` / `+0xc2` | d20 roll / total attack modifier |
| `+0xc3` / `+0xc4` | STR part / DEX part of the modifier |
| `+0xc6` / `+0xc7` | special-attack to-hit / base attack bonus |
| `+0xc8` | off-hand attack (dword) |
| `+0xcc..+0xcf` | dual-wield base penalty, light off-hand bonus, two-weapon feat reduction, that feat's id |
| `+0xd0/+0xd1` | Dueling bonus / feat id |
| `+0xd2` / `+0xd3` | close-range ranged bonus / melee-vs-ranged bonus |
| `+0xd4` / `+0xd5` | Weapon Focus bonus / effect attack bonus |
| `+0xd8` / `+0xdc` | natural 20 / natural 1 (dwords) |
| `+0xe0..+0xf1` | threat range, is-threat, confirmation d20, confirmed, critical multiplier |
| `+0xf4..+0xfc` | defense: total, armour, DEX part, DEX modifier, class bonus, natural, dodge + effects, Dueling, debilitated penalty |
| `+0xfe..+0x109` | damage: base dice, special-attack bonus, —, sneak, STR, Weapon Specialization, …, effect bonus |
| `+0x12c..+0x13c` | stun-from-special-attack report (`+0x12d` = 4, `+0x13c` = 1) (med) |
| `+0x140..+0x148` | deflection: d20, attack total, Jedi Defense feat and bonus, effect bonus, result, BAB, stat bonus, total |

### Scheduled combat actions (0x88 bytes, list at round `+0x9b0`)

Written by `0x004d1dd0` as `SchedActionList` entries: ActionTimer `+0x00`, Animation `+0x04`,
AnimationTime `+0x08`, NumAttacks `+0x0c`, ActionType `+0x10` (1 attack, 0xb attack with a combat
feat whose id is at `+0x5c`, 6/7 item use, 9 cast, 10 item cast, 0xc move…), Target `+0x14`,
Retargettable `+0x18`, InventorySlot `+0x1c`, TargetRepository `+0x20`; `+0x74` marks a cutscene
attack. `CSWSCombatRound::AddAttackAction` (`0x004d38b0`) creates attack entries (NumAttacks 1) with
animation 10009 and AnimationTime `(g_nCombatActionTime + 3000) / 2` (global `0x008327dc`). They are consumed by action 0x3f
(`0x005b6210`, see [actions.md](actions.md)), which turns each due entry into a real action
(`AddAttackActions` with the direct flag, `AddCastSpellActions`, item use…). (high for the
fields, med for the action types)

### Creature members used by combat

| Offset | Meaning | Conf. |
|---|---|---|
| `+0x154` | last killer (GetLastKiller) | high |
| `+0x158` | last hostile actor (GetLastHostileActor; `CSWSObject::SetLastHostileActor` `0x004cc0c0`) | high |
| `+0x15c` | last attacker (GetLastAttacker), set by event 15 | high |
| `+0x160` | last damager (GetLastDamager) | high |
| `+0x168` | pointer to 15 ints: damage of the last hit by type (GetDamageDealtByType) | med |
| `+0x16c` / `+0x16e` / `+0x170` | last attack type (combat feat), last attack mode, last weapon used | high |
| `+0x4d2` | combat-mode byte: 2 → +5 damage, 3 → +10 damage (no writer found) | low |
| `+0x4dc` | set when a non-player-controlled creature is attacked or attacks | med |
| `+0x4e0` | in combat (GetIsInCombat) | high |
| `+0x4e4` | combat timeout, 8000 ms (section 3.6) | high |
| `+0x504` / `+0x50c` | attack target (GetAttackTarget) / attempted attack target (GetAttemptedAttackTarget) | high |
| `+0x524` / `+0x528` | attempted spell target / spell target (see actions.md) | med |
| `+0x53c` / `+0x544` / `+0x554` | last hostile target, last attack action, last combat feat used (copied at round end) | high |
| `+0x540` | kind of the current round's action: 3 attack, 4 cast | med |
| `+0x550` | combat feat of the current attack | high |
| `+0x558` | outcome of the last attack: 0 hit, 1 miss, 2 deflected | high |
| `+0x55c` | GetLastAttackResult reads it; no writer found | med |
| `+0x8d4` | assured hit (effect type 0x65): every attack hits | high |
| `+0x8d8` / `+0x8dc` | assured deflection returns the bolt / assured deflection (effect type 0x68) | high |
| `+0x8ec` | see-invisible / true-seeing bits read by the invisibility test | med |
| `+0x8ed` | debilitating state (set by effect type 8: stun, paralysis …) | high |
| `+0x9d4` | the creature is the player character (dying rules, never destroyed) | med |
| `+0x9f0` | ushort state flags; an attacker needs bits 0x80 and 0x04; cleared at death | med |
| `+0xa2c` | equipped-items holder; `0x005a4c20(slotMask)` returns the item | high |
| `+0xa88` | player-controlled party member | med |

Equipment slot masks combat uses: `0x2` body armour, `0x8` gloves (unarmed attacks), `0x10` right
weapon, `0x20` left weapon, `0x4000/0x8000/0x10000` creature weapons. (high)

Stats (`CSWSCreatureStats`, [objects.md](objects.md)) fields used here: `+0x89` class count, class
slot *i* at `+0x8c + 0x28·i` (class `+0x1b`, level `+0x1c`), `+0xea/+0xec` STR/DEX modifiers,
`+0xf5..+0x101` the armour-class pieces (section 5), `+0x102` base-attack-bonus override (only ever
zeroed), `+0x6c` IsPC, `+0x78` faction. (high)

### Base items (`CSWBaseItemArray` at `g_pRules+0x34`, 200-byte records)

Loaded from `baseitems.2da` by `0x005b31d0`; `CSWBaseItemArray::GetBaseItem(row)` is `0x005b31a0`,
`CSWSItem::GetBaseItem()` (`0x005b4790`) uses the item's `+0xc`. Fields combat reads: `+0x08`
WeaponWield, `+0x09` WeaponType, `+0x0c` DamageFlags, `+0x18` ModelType, `+0x1a` RangedWeapon,
`+0x1b` WeaponSize, `+0x1c` NumDice, `+0x1d` DieToRoll, `+0x1e` CritThreat, `+0x1f` CritHitMult,
`+0x8a` BaseAC, `+0x8e` AmmunitionType, `+0xac` ItemType, `+0xad` DEXBONUS, `+0xb0` SpecFeat,
`+0xb2` FocFeat. (high)

## 3. The combat round

### 3.1 Starting a round

`AIActionAttackObject` (`0x005bbbf0`), once the target is in range and in line (the approach is in
[actions.md](actions.md)), does in order (high unless marked):

1. If the game is paused, or the round is paused for an attack animation already in progress,
   return "still running".
2. Bail out ("failed", stand to idle animation 10000, clear the round's queued attacks) if the
   attacker is dead or a downed party member, lacks state bits 0x80/0x04 at `+0x9f0`, or targets
   itself; return "done" if the target is dead, a downed party member, or not a valid attack
   target (`0x005b48f0`: doors and placeables always are; a non-player-controlled attacker must
   perceive a creature target).
3. **Engagement.** `GetCanEngage` (`0x004d2c30`) says the target can be paired when its round has
   not started and it has no attempted attack target, or it is already attacking this creature
   (attempted attack or spell target), or its round runs without a target; never when the target
   is debilitated, and with extra conditions when the target is the party member the player is
   controlling. `GetShouldBeMaster` (`0x004d2d60`) makes the attacker the master when the target
   has no attempted attack target, or attacks the attacker but is not itself a master; a
   player-controlled attacker is always master. (med for the exact conditions)
4. **Animation request.** 10009 for an unengaged round. When engaged, 10109 if both sides hold
   non-ranged weapons whose WeaponWield is not 1 or 8 (`GetBothWieldMelee` `0x004d2b70`) or
   either creature's appearance `MODELTYPE` starts with S or L (`0x005b47c0`); otherwise the
   action's own animation parameter. These are engine animation numbers the client maps to model
   animations. (med)
5. **Start.** Not engageable: `StartCombatRound(target, engaged = 0, master)`. Engageable and
   master: `StartCombatRound(target, 1, 1)` on the attacker and `StartCombatRound(attacker, 1, 0)`
   on the target (which becomes the slave; its `+0x4dc` = 1). Engageable but not master: the
   attacker does nothing new this frame (the target's own round drives the pair).
6. If the round started: store the combat feat in the current attack record (`AttackType`) when
   the attacker holds a right-hand weapon, `+0x8e0` is 0 and the action's parameters ask for it; play the requested animation; set the
   attempted attack target; pause the round by the attacker for the animation (`SetRoundPaused`
   `0x004d28f0`, `SetPauseTimer` `0x004d2920`); count the action (`+0x968`). With a combat feat,
   the partner's round is paused too (infinitely for a slave, until the master releases it).
7. A pending `NewAttackTarget` replaces the target; then `ResolveAttack` (`0x005bba80`); return
   "done". The attack action lasts one round; the next round's attack comes from outside
   (section 9).

`StartCombatRound(target, bEngaged, bMaster, nCombatFeat, bCutscene)` (`0x004d5f70`): a slave first
ends its current round; MasterID is the master's id (the attacker's own id on the master side, the
partner's on the slave side), and the master copies MasterID and its slave id into the slave's round
and zeroes the slave's timer; then RoundStarted = 1, Timer = 0, unpaused, PausedBy = INVALID,
SpellCastRound = 0, RoundLength = **3000 ms**, the five attack records are reset, the attack
counts are computed (3.2), OffHandTaken = ExtraTaken = 0, the round target and DodgeTarget = the
target, DeflectArrow = 1, WeaponSucks = 0, the creature's look-at target is set (`0x004f34a0`)
and its `+0x540` = 3. (high)

Spell rounds start the same way from the cast actions (`AIActionCastSpell` `0x00514af0`,
`AIActionItemCastSpell` `0x0050f170`) with `SetSpellCastRound` (`0x004d28b0`). (high)

### 3.2 Number of attacks

KOTOR does not use iterative attacks from the base attack bonus. (high)

- **On-hand attacks** (`InitializeNumberOfAttacks` `0x004d2a10`): 1 (a folded "return 1" at
  `0x005a4cf0`, called on the stats block) + EffectAttacks (0..2, from effect type 0x2c — see
  rules.md for which script effects produce it) + 1 if the combat feat is Flurry (11), Improved
  Flurry (91), Master Flurry (53, `WHIRLWIND_ATTACK`), Rapid Shot (30), Improved Rapid Shot (92) or
  Multi Shot (26). (high)
- **Off-hand attack** (`CalculateOffHandAttacks` `0x004d2a70`): 1 when the right weapon's
  WeaponSize ≤ the creature's size (`+0x4f8`) and the left slot holds an item whose WeaponType
  and WeaponWield are both non-zero; or when the right weapon is larger than the creature and its
  WeaponWield is 3 (double weapons: double-bladed swords and lightsabers, quarterstaff, ghaffi
  stick, Wookiee warblade). Otherwise 0. (high)
- The round makes OnHand + OffHand attacks (`GetTotalAttacks` `0x004d2eb0`); attack *i* is an
  off-hand attack when *i* ≥ OnHand. (high)

**Weapon attack type** of the current attack (`GetWeaponAttackType` `0x004d3da0`, stored in the
record's `+0x3a`): if the creature has no hand weapons but has a creature weapon
(`HasCreatureWeapons` `0x004d2e20`) → 3 when the 0x4000 slot is filled, else 0; off-hand → 2; an
extra attack (AdditAttacks or EffectAttacks non-zero and the index past OnHand) → 6 with a right
weapon, 8 without; otherwise 1 with a right weapon, 7 without. `GetCurrentAttackWeapon`
(`0x004d4ff0`) maps 1/6 → right weapon, 2 → right weapon if it is a double weapon (WeaponWield 3)
else left, 3/4/5 → creature weapon slots, 7/8 → gloves. (high)

### 3.3 Resolving the round's attacks

`ResolveAttack` (`0x005bba80`): if the target is gone or is not a creature, door or placeable, unpause
the round and stand ready (10001). Otherwise remember the target in `+0x504`, then melee or ranged
by the right weapon's RangedWeapon. (high)

**Melee** (`ResolveMeleeAttack` `0x005bb890`), for each attack *i* of the round:

1. Record the target and weapon attack type; set the off-hand flag (*i* ≥ OnHand).
2. **Coup de grace**: if the target creature is debilitated, its total level is below 5 and it is
   not player-controlled, the record's CoupDeGrace = 1. (high)
3. `ResolveAttackRoll` (section 4).
4. Ask the client for the attack animation and look up the hit time of attack *i*:
   `combatanimations.2da`, row labelled with the animation number, column *i* + 1 (`hit1`, `hit2`,
   `hit3`; `GetCombatAnimationHitTime` `0x005b4f30`). (med for the client half)
5. With a combat feat, `ResolveMeleeSpecialAttack` (`0x005ba8e0`, section 4.5).
6. On a hit (results 1–3): `ResolveDamage` (section 6) then `ResolvePostMeleeDamage`
   (`0x005b8b00`): KillingBlow = 1 when the record's total damage ≥ the target's current HP; a
   coup de grace adds a death effect (type 0x13) to the record's on-impact effects.
7. Queue the impact at that hit time (`AddMeleeImpact` `0x004d5a50`) and update `+0x558`
   (`0x005b7400`).

Afterwards `ResolveMeleeAnimations` (`0x005b7470`) stores the animation length, shortens the round
(3.4), chooses the target's reaction (10014 when hit, 10012 after a deflection, 10011 after a
miss) and, when the attacker's round is engaged and the target is not debilitated and its own
round has room (`CheckActionLength` `0x004d2970`), makes the target play it and shortens the
target's round too; otherwise the reaction is 10001 (none). (high)

**Ranged** (`ResolveRangedAttack` `0x005bb590`): the attack animation selects a row of
`weapondischarge.2da` (`shots`, `hits`, `switchmask`, `shot1..shot12` in ms). The round's attacks
(OnHand + OffHand) are spread at random over the visual shots: for each shot *u*, with *S* shots
and *A* attacks still to place, the shot carries an attack when `rand() % S < A`. A carrying shot
gets the off-hand flag as in melee, a full `ResolveAttackRoll`, and the special-attack step
(`ResolveRangedSpecialAttack` `0x005ba540`); a shot that missed (4–6) may still be deflected or hit
an energy shield (results 8/10, section 4.6). Hits run `ResolveDamage` and
`ResolvePostRangedDamage` (`0x005b8c20`). Each shot is queued as an impact at its `shotN` time,
fired from the hand given by the `switchmask` digit (`AddRangedImpact` `0x004d5b60`); the bolt's
travel time (≈ distance × 23.8 ms per metre, constant `0x0074b2ec`) becomes ReaxnDelay. The
`hits` column is read but not used. `ResolveRangedAnimations` (`0x005b6c40`) then mirrors the melee
step. (high for the selection rule, med for travel time)

### 3.4 Timing inside the 3 seconds

The round has two clocks. (high unless marked)

- **Round timer.** `IncrementTimer` (`0x004d4c10`) adds the frame time (creature `+0xcc`, ms) to
  Timer while the round is not paused. When Timer ≥ RoundLength the round ends
  (`EndCombatRound(1)`), except that an engaged master's slave is reset first, and a spell round
  only ends once the head of the action queue is no longer a cast (action 0xf). A negative timer
  or a vanished master also ends it (log strings at `0x00746418..0x007464e0`).
- **Animation pause.** While an attack animation plays the round is paused and PauseTimer counts
  down (`DecrementPauseTimer` `0x004d4e80`, which ends the round if the master has vanished).
  Each frame `UpdateCombat` (`0x004faf20`) fires the next impact of the current record when its
  time has come (impact time < AnimationLength − PauseTimer, `0x004d45e0`), via
  `ApplyAttackImpact` (`0x005b8050`). When PauseTimer reaches 0 it fires any impacts left,
  unpauses (`FinishAttackPause` `0x004f1250`: clear pause, advance the round timer by the
  overshoot, return to the combat-ready animation), does the same for the slave, and ends the round
  if the round's target is now dead or a downed party member.
- **Shortening.** `DecrementRoundLength(animLen, bForce)` (`0x004d3440`): if the animation is longer
  than the time left and the excess is ≤ 1000 − OverlapAmount, the round is first stretched to
  animLen + 1 (OverlapAmount is meant to record this but the arithmetic leaves it unchanged); with
  bForce the round is set to animLen. Timer and the pending scheduled actions' timers are rescaled
  by (RoundLength − animLen) / RoundLength, and RoundLength becomes RoundLength − animLen (at
  least 0). In effect the attack animation consumes round time instead of running on top of it.
  (med)

Global pause (`0x004ae980(2)` on the server) freezes everything. (high)

### 3.5 Ending a round, OnEndRound and continuing

`EndCombatRound(bRunScript)` (`0x004d4620`), in order (high):

1. Clear RoundStarted, Timer, RoundLength, pause state, DodgeTarget, AdditAttacks and `+0x968`.
2. If creature `+0xa9c` is set, refill current Force points to the maximum (med: which state sets
   it is unknown).
3. A master releases its slave: unpause, clear its Engaged and MasterID.
4. If the round's target is dead or down (doors: open; placeables: destroyed) clear it, and pick the
   creature's current attack (or spell) target as the "next" target.
5. Animation 10001 (combat ready); reset the five attack records; clear the creature's attack,
   spell and hostile-target fields that point at dead objects.
6. Unless the creature is the one the player controls, stop its combat stepping (`0x0050ee80`).
7. **OnEndRound** (`ScriptEndRound`, creature `+0x260`) runs when bRunScript is set, the head of
   the action queue is not a move-to-point, the round was not a spell round or a cutscene attack,
   and the creature is neither dead nor down.
8. Copy current → last fields (`+0x504→+0x53c`, `+0x540→+0x544`, `+0x550→+0x554`, spell
   fields); NumAOOs = NumCleaves = 1.

`IncrementTimer` and `UpdateCombat` call it with bRunScript = 1. Because ATTACKOBJECT returns
"done" after resolving one round, the next round depends on who re-issues an attack (section 9).

### 3.6 Combat state

`CSWSCreature::SetCombatState(bInCombat, nReason)` (`0x004f2610`) (high):

- Entering combat sets `+0x4e0` and the **8000 ms** timeout `+0x4e4`; `+0xac0` keeps the reason
  (1 = this creature is being attacked, 2 = it is attacking or reacting). A non-player creature
  entering combat for reason 1 plays a battle cry 30 % of the time (`0x004ec8e0`). A creature of
  faction 5 (`STANDARD_FACTION_NEUTRAL`; `GetFaction` `0x00513fc0`, faction `+0xc`) never enters
  combat. (med for the faction-id reading)
- `CSWSCreature::AIUpdate` (`0x004fe210`) counts the timeout down by the frame time and leaves
  combat when it runs out; stealth is dropped on entering combat for reason 1. Every hostile act
  resets it: `SignalCombatWith` (`0x004fbbe0`) is called by attacks, by ON_MELEE_ATTACKED on both
  sides and by damage. It puts the creature in combat when the other party is hostile (reputation
  < 11) and pulls in every faction-mate within range that is also hostile to it (30 m for
  player-controlled creatures, otherwise the member's perception range or `ranges.2da` row 11
  PrimaryRange). (med for the range choice)
- Leaving combat clears the attack/spell targets, the round's queued attacks and specials,
  `+0x540..+0x554`, the hostile actor, and ends a running round.
- `CancelCombat` (routine 54 → `0x004fdaa0`): clear actions, leave combat, end the round.
  `ClearAttackersInArea` (`0x004fd960`) and `0x004fda20` make everyone targeting a creature leave
  combat (used when it dies, surrenders or becomes unseen).
- When the player's leader attacks (`AddAttackActions` `0x004fde40`, direct mode): the PC plays a
  battle cry 75 % of the time if not yet in combat, other party members 10 %.

### 3.7 When the target dies mid-round

Already-queued impacts still fire, but `OnApplyDamage` ignores a dead or downed target
(section 6.6). At the end of the attack pause `UpdateCombat` ends the round early when the round's
target is dead or down; `EndCombatRound` clears dead targets; the next ATTACKOBJECT finds the
target dead and returns "done". (high)

## 4. The attack roll

### 4.1 Order of operations (`ResolveAttackRoll` `0x005baca0`)

1. Clear the threat block; refresh the weapon attack type.
2. **d20** = `RollDice(1, 20)` (`0x00550b60`: the sum of N × (1 + rand() % sides)); a debug
   global `0x00832874` can force it.
3. **Attack modifier** = `GetAttackModifierVersus(target)` (4.2) on the attacker's stats.
4. **Defense** = `GetArmorClassVersus(attacker, bTouch = 0)` (section 5) on the target's stats, if
   the target is a creature (doors/placeables: 0). Then `ResolveSneakAttack` (`0x005b8820`, 4.7).
5. A forced result (cutscene attack) is stored and the roll ends.
6. CoupDeGrace → result 3 (automatic hit), d20 shown as 20.
7. Assured hit (`+0x8d4`) → result 1.
8. **Deflection check** `ResolveProjectileDeflection` (`0x005b8e50`, 4.6) with "would hit"
   = (defense ≤ d20 + modifier); if it deflects, the roll ends with result 8 or 9.
9. **Natural 1** → miss (result 4), flagged.
10. If d20 + modifier < defense → miss unless the d20 is 20 (natural 20 always hits).
11. **Threat**: threat = `GetCriticalHitRoll(offhand)` (4.3); if d20 < threat → hit (1).
12. **Confirmation**: a second d20; if it + modifier < defense → hit (1).
13. Confirmed: multiplier = `GetCriticalHitMultiplier(offhand)`; if the target is immune to
    critical hits (immunity type 31, `GetEffectImmunity` `0x005a6960`) → hit (1) with feedback message
    0x7e ("immune to critical hits", strref 1480); otherwise **critical hit** (2).

(high)

### 4.2 Attack modifier (`CSWSCreatureStats::GetAttackModifierVersus` `0x005a7ea0`)

Summed in this order (each term is also written to the record for the log) (high):

| # | Term | Rule |
|---|---|---|
| 1 | Base attack bonus | `GetBaseAttackBonus` `0x005a60d0`: Σ over class slots of `cls_atk_*` `BAB` at row (class level − 1) (`CSWClass::GetAttackBonus` `0x005bccb0`, levels 1–60, table loaded by `LoadAttackBonusTable` `0x005bcda0` from `classes.attackbonustable`). Multiclass simply adds. A stats override at `+0x102` would replace it but is never set. |
| 2 | Dual-wield penalty | Only when wielding an off-hand weapon (left slot, or a double weapon in the right) with WeaponType ≠ 0. On-hand attack: −6, or −4 if the off-hand weapon is "light" (WeaponSize − creature size = −1, `GetRelativeWeaponSize` `0x004ed190`) or a double weapon; then +4 with Two-Weapon Mastery (85) or else +2 with Two-Weapon Advanced (9). Off-hand attack: −10, then +8 Mastery, else +6 Advanced, else +4 Two-Weapon Fighting (3). (OffHandTaken is counted here.) |
| 3 | Special-attack to-hit | `GetSpecialAttackModifier` `0x005a4ec0` by the record's combat feat: Flurry 11 / Rapid Shot 30: −4; Improved 91 / 92: −2; Master 53 / Multi Shot 26: −1; Power Attack 28, Improved 17, Master 83 and Power Blast 29, 18, 82: −3; Force Jump 101/102/103: 0/+2/+4; Critical Strike and Sniper Shot lines: 0. |
| 4 | Dueling | Right weapon only (no left item) with WeaponWield 2 (one-handed melee) or 4 (pistol): +3 Master Dueling (115), +2 Advanced (114), +1 Dueling (113). |
| 5 | Close-range ranged | Ranged attack and target within 5 m (distance² ≤ 25): **+10** ("Close Proximity Ranged Bonus", strref 42330). |
| 6 | Melee vs. ranged | Melee attack against a target whose right weapon is ranged: **+10** ("melee on ranged", strref 42317). |
| 7 | Ability modifier | Melee: STR modifier, or the DEX modifier when the weapon is a lightsaber (baseitems 8, 9, 10; `GetIsLightsaber` `0x00555690`) and DEX mod > STR mod (`GetUseDexterityForAttack` `0x005a54f0`). Ranged: DEX modifier. A debilitated attacker's DEX modifier is capped at 0. |
| 8 | Weapon Focus | +1 if the creature has the weapon's `FocFeat`. |
| 9 | Effects | `GetTotalEffectBonus(1, target)` (`0x004f3fe0`, rules.md): Σ attack-increase effects (type 0x0a) − Σ attack-decrease (0x0b), filtered by weapon attack type (0 = any; types 6 and 8 also match 1/3 and 7), the target's race and alignment group; effects created by the same item do not stack (only the largest counts). |

There is no size modifier and no range penalty. Weapon enhancement and attack-bonus item
properties reach the roll only as effects the item applies when equipped (rules.md). (high for the
absence in this function)

### 4.3 Critical threat and multiplier

`GetCriticalHitRoll(bOffHand)` (`0x005a5130`), returns the lowest d20 that threatens (high):

1. Weapon = right weapon; for an off-hand attack the left weapon unless the right is a double
   weapon; if none, the gloves; if still none the threat width is 1.
2. *t* = baseitem `CritThreat`; Keen (item property 28) adds *t* again.
3. Combat feat: Critical Strike (8) or Sniper Shot (31) add *t*; Improved (19, 20) add 2*t*; Master
   (81, 77) add 3*t*.
4. Result = 21 − (sum). Example: lightsaber (CritThreat 2) → 19; with Critical Strike → 17.

`GetCriticalHitMultiplier(bOffHand)` (`0x005a52b0`): the same weapon choice without the gloves
fall-back; no weapon → 2; else baseitem `CritHitMult` (2 for every shipped weapon). (high)

`diffsettings.2da` row 0 `NoCriticalOnPC` is never read: NPCs can crit the player on every
difficulty. (high: no reader of that row)

### 4.4 Attack results

| Value | `ATTACK_RESULT_*` | Meaning in the exe |
|---|---|---|
| 1 | HIT_SUCCESSFUL | hit |
| 2 | CRITICAL_HIT | confirmed critical |
| 3 | AUTOMATIC_HIT | coup de grace ("Automatic Hit!", strref 42390) |
| 4 | MISS | miss (5 and 6 are treated as misses too; nothing in combat produces them) |
| 8 | (PARRIED) | bolt deflected away ("Deflected!", 42411) |
| 9 | (DEFLECTED) | bolt sent back at the shooter ("Returned!", 42421) |
| 10 | — | a missed bolt absorbed by an energy shield (visual only) |

`+0x558` keeps the class of the last result: 1–3 hit, 4–6 miss, 8–10 deflected (`0x005b7400`;
`0xff` = keep). The target's reaction animation follows it. (high)

### 4.5 Combat feats ("special attacks")

The feat comes from the action (player menu or AI `ActionAttack` with a talent) and is stored in
the record's AttackType. The melee/ranged special-attack step runs only for the first attack of
the round and first checks the creature still has the feat (`CSWSCreatureStats::HasFeat`
`0x005a6680`, which returns remaining uses); otherwise AttackType is cleared. (high)

| Feats | Attack | Damage | Defense effect on self | On hit |
|---|---|---|---|---|
| Power Attack 28 / Power Blast 29 | −3 | +5 | — | — |
| Improved 17 / 18 | −3 | +8 | — | — |
| Master 83 / 82 | −3 | +10 | — | — |
| Flurry 11 / Rapid Shot 30 | −4 | — | dodge AC −4 for 3 s | +1 attack |
| Improved Flurry 91 / Improved Rapid Shot 92 | −2 | — | −2 for 3 s | +1 attack |
| Master Flurry 53 / Multi Shot 26 | −1 | — | −1 for 3 s | +1 attack |
| Critical Strike 8, 19, 81 (melee) | 0 | — | −5 for 3 s | threat ×2/×3/×4 width; stun 6 s unless Fortitude vs. level + STR mod |
| Sniper Shot 31, 20, 77 (ranged) | 0 | — | −5 for 3 s | as above with INT mod |
| Force Jump 101 / 102 / 103 | 0 / +2 / +4 | 0 / +2 / +4 | — | — |

The self-penalty is an AC-decrease effect (type 0x31, dodge, versus everything) of 3.0 s. The stun
is effect type 8 (int 0 = 4) of 6.0 s, added to the record's on-impact list only if the target is
not immune (`0x005a6a90`) and fails the save (`SavingThrowRoll` `0x005b92b0`, type 1). Flurry and
Rapid Shot effects come from `0x005ba8e0` (melee) and `0x005ba540` (ranged); damage bonuses from
`GetSpecialAttackDamageBonus` `0x005a4fb0`. The feat descriptions (strrefs 1133–1155, 1144)
describe the same numbers. (high)

### 4.6 Deflecting blaster bolts

Only ranged attacks can be deflected. (high)

- **Who can** (`GetCanDeflectProjectile` `0x005b78e0`): a target with Jedi Defense (55), Advanced
  (1) or Master (24), not debilitated or down, holding a lightsaber, not busy (`+0xa04`), and
  facing the shooter (the dot product of its facing and the shooter's facing ≤ 0). Without the
  feats, a shot that missed can still hit an energy shield (the ammunition type's `ShieldHit` in
  `ammunitiontypes.2da`), giving result 10.
- **Roll** (`ResolveProjectileDeflection` `0x005b8e50`), made before the attack is resolved:
  deflect = d20 + 6 (Master Jedi Defense) or + 3 (Advanced) + the defender's base attack bonus
  + two stat bytes `+0x16c/+0x16d` + Σ blaster-deflection effects (types 0x5c/0x5d, int 1). If
  deflect < d20 + attack modifier → not deflected. If deflect ≥ attack + 6 → result 9 (returned),
  else 8. Assured deflection (`+0x8dc`) skips the roll: 9 when `+0x8d8`, else 8.
- **Effect** (`SignalRangedDamage`): 8 and 10 fly off to a deflection point (no damage). 9 applies
  the damage to the shooter (its own damage resistance then immunity are applied) at twice the
  travel time.

(high for the rules, med for the stat bytes' meaning)

### 4.7 Sneak attack eligibility (`ResolveSneakAttack` `0x005b8820`)

Only for attackers with any of the feats 60–69 (Sneak Attack 1d6 … 10d6). The record's SneakAttack
is set when (high):

- the target is debilitated or a downed party member, or it does not see the attacker (no
  perception entry with the seen bit) and the attack is melee or ranged within 10 m — and in these
  cases the target must not be immune to sneak attacks (30) or critical hits (31), else feedback
  0x86 ("immune to Sneak Attacks", strref 1487); or
- the target sees the attacker, but the attacker is outside the 90° cone in front of the target
  (cosine of the angle between the target's facing and the direction to the attacker < 0.707)
  and, for ranged attacks, within 10 m. This path does not check immunities.

The damage is in section 6.2.

## 5. Defense (`CSWSCreatureStats::GetArmorClassVersus(attacker, bTouch)` `0x005ad0e0`)

Summed in this order (high unless marked):

1. **10 + class bonus**: Σ over class slots of `acbonus.2da` at row = class level, column
   `classes.armorclasscolumn` (`CSWClass::GetACBonus` `0x005be770`, table `+0x10c` loaded by
   `LoadArmorClassTable` `0x005bde80`, rows 0–20). Soldier and Scout get 0; Scoundrel and the three
   Jedi 2/4/6 at levels 1–5/6–11/12+; both droid classes use the Scoundrel column.
2. Unless bTouch: **natural** (`+0xf5` base + `+0xfe` − `+0xff`), **armour** (`+0xf6` + `+0xf8` −
   `+0xf9`), **shield** (`+0xf7` + `+0xfc` − `+0xfd`). The base values come from equipped items,
   the ±pairs from AC effects without a "versus" condition, both kept up to date by the effect and
   equipment code (rules.md, party-items-saves.md). (med for who writes them)
3. **DEX and dodge**: if the attacker is not hidden from the defender (`GetIsHiddenFrom`
   `0x00501950`, below) and the defender perceives it (seen bit): dodge = min(`+0x100` − `+0x101`,
   10) and DEX = `GetDexModifierForDefense(1)` (`0x005a5330`): the DEX modifier, capped by the
   body armour's `DEXBONUS` when that armour has ModelType 1 and BaseAC > 0 (Jedi robes have
   BaseAC 0 and so no cap), and capped at 0 when the defender is debilitated. If the attacker is
   hidden: no dodge, and DEX counts only if it is negative. If the defender does not perceive the
   attacker at all: neither.
4. **Versus effects**: the defender's AC-increase/decrease effects (types 0x30/0x31) that carry a
   condition (a racial type, an alignment group, or a damage-type filter other than 0x4007): dodge
   type summed (decreases subtract); deflection type: the best of the stats deflection value
   (`+0xfa`) and matching increases. Natural, armour and shield "versus" effects are gathered but
   only added when bTouch is set, and the deflection-decrease branch adds instead of subtracting
   (both look like slips in the original). The damage-type filter compares 1/2/4 against the
   attacker's weapon flags 0/1/2 (another mismatch), and the script constant
   `AC_VS_DAMAGE_TYPE_ALL` is 8199 = 0x2007 while the exe tests 0x4007. (med for the reading of
   these quirks)
5. **Dueling**: `GetDuelingDefenseBonus` (`0x005a9f50`): +3/+2/+1 for Master/Advanced/Dueling with
   a single one-handed melee weapon or pistol.
6. **Debilitated**: −4 (and DEX capped at 0 above).

`GetIsHiddenFrom(defender)` (`0x00501950`) walks the attacker's invisibility effects (type 0x2f):
the attacker is hidden unless the defender's `+0x8ec` bits see through that kind (1 and 4 by bits
0x5, 2 by bits 0x6). A stealth-type effect (0x3f) against a hostile defender that has not spotted
the attacker triggers an Awareness check; failing it leaves the defender flat-footed and marks
combat between them. (med)

Touch attacks (script `TouchAttackMelee/Ranged`, `0x00548ca0`) call this with bTouch = 1 and use
the display bonuses `GetMeleeAttackBonus` (`0x005a7770`) / `GetRangedAttackBonus` (`0x005a7b60`).
Flurry, Rapid Shot and Critical Strike penalties reach defense through their 3-second effects
(4.5). There is no flat-footed state other than the DEX/dodge rule above. (high)

## 6. Damage

### 6.1 Order (`ResolveDamage` `0x005bb440` → `GetDamageRoll` `0x005a9050`)

`ResolveDamage(target, bForced, nForced)`: if the target is plot (`+0xf8`), or the debug no-damage
flag `0x00832878` is set, or the in-game GUI flag `+0xb4` is set while the attacker is
player-controlled, the damage is 0 (or the forced amount). A forced amount (cutscene attack) is
used as is with the weapon's damage type. Otherwise (high):

1. `GetDamageRoll(target, bOffHand, bCritical = (result 2), bSneak, bMaximize = 0, bRecord = 1)`.
2. Add it to the record's total (`+0x38`).
3. `ResolveOnHitEffect` (`0x005bafa0`): item property 32 (OnHit) on the weapon (subtypes 0–10 from
   `iprp_onhit.2da`, chance and duration from `iprp_onhitdur.2da`, save DC from cost table 25
   `Value`, default 20); the effect goes on the record's impact list if the chance roll passes and
   the target fails the save.
4. `ResolveDamageVisualEffects` (`0x005b9040`): per damaged type, `damagehitvisual.2da`
   `VisualEffect` (melee) or `RangedEffect`; a deflection adds visual 4023.
5. On a critical hit, sound-set entry 0x11 (`0x004f2520`).

`GetDamageRoll` (high):

1. **Weapon**: off-hand → left weapon (or the current attack weapon if none); else the current
   attack weapon (3.2).
2. **Difficulty scaling setup**: PC attacker (stats `IsPC`) against a non-PC → percentage =
   `diffsettings.2da` row 3 `MinPCDamagePercent`; NPC against the PC → row 4
   `MaxNPCDamagePercent`; columns by the server's difficulty value (`CSWRules::GetDifficultySetting`
   `0x00550c30`, table loaded by `0x00550c50`; `****` reads as 0).
3. **Dice**:
   - no weapon, or ItemType 19 (gauntlets) / 20 (forearm bands): unarmed, 1d2 for tiny/small
     creatures, 1d1 for medium and larger (`GetUnarmedDamageRoll` `0x005a4d90`; a folded constant
     selects the 1d4/1d6 monk-style branch never taken);
   - creature weapons (attack types 3–5): item property 51 (Monster damage) → `iprp_monstcost.2da`
     `NumDice` d `Die`;
   - otherwise baseitems `NumDice` d `DieToRoll`.
   Each roll goes through `ApplyDifficultyToDamageRoll` (`0x00550d10`, below). On a critical the
   dice are rolled *multiplier* times and added. With bMaximize the dice give their maximum.
4. Item property 31 (DamageNone) → 0.
5. With bRecord and damage > 0: store as the base damage in the record's type slot.
6. **Sneak attack** (bSneak): highest feat 60–69 → 1d6 … 10d6, added once (never multiplied).
7. **Bonuses** (`GetDamageBonus` `0x005a8be0`): STR modifier for melee attacks only (full
   modifier, also off-hand and two-handed; ranged 0); Weapon Specialization +2 (`SpecFeat`);
   special-attack bonus (4.5) plus the `+0x4d2` combat-mode bonus. Not critical: added once.
   Critical: each of the three is added *multiplier* times, then item property 49 (Massive
   Criticals) adds `iprp_damagecost.2da` `NumDice` d `Die` once.
8. **Effect damage bonus** `GetTotalEffectBonus(2, target)`: damage-increase/decrease effects
   (0x0d/0x0e); amounts 1–5 are flat, 6+ index `iprp_damagecost.2da` dice, rolled *multiplier*
   times on a critical; each is pushed through the target's immunity and resistance and recorded
   in its own damage-type slot; increases and decreases are each capped at 36. (med: rules.md owns
   the effect details)
9. **Minimum 1**: if the weapon damage is < 1 it becomes 1.
10. **Target mitigation** on the weapon damage, in this order: `DoDamageImmunity` (virtual slot 43,
    `0x004cf160`), `DoDamageResistance` (slot 42, `0x004d0e40`), `DoDamageReduction` (slot 41,
    `0x004d09e0`); never below 0.

`ApplyDifficultyToDamageRoll(roll, max, bPCAttacker, bNPCvsPC, pct)` (`0x00550d10`) (high):

- PC attacker, pct ≠ 0: if pct% of max equals max, the result is max; otherwise
  roll + (pct + rand % (100 − pct))% of max, capped at max.
- NPC vs. PC, pct ≠ 0: pct < 100 → roll − (100 − pct)% of max, at least 1; pct > 100 → roll +
  (rand % (pct − 100))% of max; 100 → roll.

With the shipped table: easy raises the PC's rolls by 50–99 % of the maximum and halves the NPCs'
(roll − 50 % of max); normal and hardcore change nothing here. Rows 1, 2 and 5 are covered in 7 and
8.4.

### 6.2 What a critical multiplies

Weapon dice, STR, Weapon Specialization, the special-attack bonus and effect damage bonuses are
multiplied (re-rolled or re-added *multiplier* times). Sneak attack dice and Massive Criticals are
not. The multiplier is `CritHitMult`, 2 for every shipped weapon. (high)

### 6.3 Damage types and the damage list

The record keeps 15 damage values indexed by bit: 1 bludgeoning, 2 piercing, 4 slashing,
8 universal, 16 acid, 32 cold, 64 light side, 128 electrical, 256 fire, 512 dark side, 1024 sonic,
2048 ion, 4096 blaster; bits 13–14 unused. A weapon's `DamageFlags` picks its slot as the nearest
integer to log₂(flags) (`AddDamage` `0x004d20d0`, `SetDamage` `0x004d2070`): 7 (disruptors: B|P|S)
lands in slot 3 (universal), 4096 in slot 12. An item without flags counts as 8; an unarmed
attack as 1. The record's total (`+0x38`) is what the summary log shows; `GetTotalDamageFromList`
(`0x004d2180`) sums slots 0–13 only (slot 14 is skipped). (high)

### 6.4 Immunity, resistance, reduction

- **Immunity** (slot 43): percentage = virtual slot 45 (`GetDamageImmunityByFlags`, the 15-byte
  table at `+0x1ac`); absorbed = damage × pct / 100 truncated, at least 1 when pct > 0; negative
  percentages (vulnerability) increase the damage. Feedback 0x3e (strref 1453). (high)
- **Resistance** (slot 42): the strongest damage-resistance effect (type 2) whose type mask matches
  is subtracted; limited resistances lose what they absorb and are removed when used up (feedback
  0x3f, strrefs 1454/1456). (med)
- **Reduction** (slot 41): damage reduction against the attack's "power" (strrefs 1455/1457).
  (med; rules.md)

### 6.5 Delivery

At impact time (section 3.4) `ApplyAttackImpact` (`0x005b8050`) (high):

- on a critical against the player creature, queue a controller-rumble event (27, data 20);
- for melee attacks and for ranged shots that carried an attack: send the combat-log messages
  (section 10);
- melee: `SignalMeleeDamage(target, 1)` (`0x005b75d0`): queue ON_MELEE_ATTACKED (event 15, the
  attack record as data); on a hit, create a damage effect (type 0x26, creator = attacker, subtype
  0x16, ints 0–14 = the damage list, 15 = 1, 16 = AnimationLength / 2, 19 = 1 "combat damage",
  21 = 1 "no feedback") and queue it as APPLY_EFFECT (event 5); queue the record's feedback
  messages (event 22), apply its on-impact effects to the target, queue item on-hit spells (event
  19) on the attacker. A miss by the controlled character updates the client's target display.
- ranged: `SignalRangedDamage` (`0x005b6f30`): the same, with the effect delayed by the travel
  time, int 20 = 1, deflections as in 4.6, and a stun effect on impact reported by `0x005b60f0`.

### 6.6 Applying the damage (`CSWSEffectListHandler::OnApplyDamage` `0x004dfa40`)

The effect-type 0x26 apply handler (registered by `0x004e4a10`). (high unless marked)

1. Ignore a dead or downed target. Plot targets (and the debug no-damage flag) zero every
   non-negative type. Read the effect's ints.
2. **Doors and placeables**: for non-combat damage apply immunity, resistance and (for
   non-physical types) reduction to the total, and an object in its 10022 or 10076 animation
   replays it (event 9) and shows 10014; `DoDamage`; queue ON_DAMAGED (script event 4) with the amount; feedback.
   If now dead: a door is bashed open (plot set, `0x00589c70`); a placeable gets a death effect,
   or, when it opens rather than dies (`+0x324`), is set plot, plays 10075 and opens after 1 s.
   The attacker's actions are cleared.
3. **Creatures**: non-combat damage gets immunity, resistance and reduction here (combat damage
   already had them). Last damager `+0x160` = the creator; mark hostility (`SetLastHostileActor`)
   unless the effect is one of the target's own type-0x23 effects; store the per-type amounts at
   `+0x168`; for melee combat damage run `0x005b7d10` (damage shields, rules.md) (med).
4. If the total > 0: `TakeDamage` (6.7); a creature casting a concentration-breakable power
   (spells.2da flag `+0x134` of the current spell; casting animations 10015/10016/11000) rolls d20
   against 10 + spell level + damage and is interrupted (animation 10014, feedback, effect type
   0x1e) when it rolls lower; for non-combat damage the target plays 10302 or, for electrical or
   dark-side damage while idle, 10023 with its round paused.
5. **OnDamaged** (`ScriptDamaged` `+0x250`) runs immediately unless the creature is the PC
   (`+0x9d4`), dead, down, or the party is in a state `0x00563a00` reports. (med for the last)
6. Feedback (unless int 21): the damage message to the target, and to the attacker when their
   factions differ.
7. A dead target, or a party member that is now down, gets a **death effect** (type 0x13, creator
   the attacker; int 0 = 1 when the killing attack was melee, int 1 = 1). (A branch that would
   signal PLAYER_DYING (script event 32) to the module is behind a constant-false test and never
   runs.)

### 6.7 Hit points (`CSWSCreature::TakeDamage` `0x004f3830`, `CSWSObject::DoDamage` `0x004ccf80`)

(high)

1. Damage to a party member or the PC is multiplied by `difficultyopt.2da` `MULTIPLIER` of the
   client's difficulty option (Easy 0.5, Normal 1.0, Difficult 1.5), truncated.
2. Damage to a creature that is not player-controlled is multiplied by `g_nNPCDamageMultiplier`
   (`0x007a1b30`, 1 unless a cheat changes it).
3. **Temporary hit points** (`+0xe4` > 0): the creature's temporary-HP effects (type 0x0f) absorb
   damage in list order; exhausted ones are removed; `+0xe4` becomes what is left.
4. `diffsettings.2da` row 5 `MinHP1` (1 only on the first column): the PC cannot drop below 1.
5. `DoDamage`: HP −= damage; with Min1HP (`+0x200`) the HP stays at 1. Doors and placeables skip
   this when plot (`0x00589190`).

## 7. Attacks of opportunity

KOTOR has none. The event BROADCAST_AOO (20) exists in the event table, but nothing queues it and
the creature event handler ignores it; the round's NumAOOs/NumCleaves are only reset and saved;
`diffsettings.2da` rows 1 (`NoAoOWithRanged`) is never read and row 2 (`NoAoOWithPotion`) only
gates a client call when the PC uses a stim (ItemType 25) in `AIActionItemCastSpell`. (high)

## 8. Death and going down

### 8.1 Who counts as dead

- `CSWSObject::GetDead` (slot 37, `0x004cb810`): HP < 1; for the PC (`+0x9d4`) HP < −9.
- `CSWSCreature::GetDead` (`0x004ef820`): a member of the client's party list is **never** dead.
- `GetIsIncapacitatedPartyMember` (`0x004ef890`): a member of the client's party list with HP < 1.
- `GetIsDebilitated` (`0x005b4880`, script GetIsDebilitated): state `+0x8ed` set, or down.

(high)

### 8.2 The death effect (`CSWSEffectListHandler::OnApplyDeath` `0x004e0ac0`)

(high unless marked)

1. Plot → nothing. Min1HP → HP = 1, nothing else.
2. Notify its client object (`0x00610950`, med), clear its look-at target (`0x004f34a0`),
   `ClearAllActions(1)`.
3. **Placeable**: `0x00587770`, animation 10072. **Door**: destroyed state, and its linked door
   gets a death effect too. Both then signal OnDeath (script event 10) and are destroyed after
   2000 ms (event 11).
4. **Creature** (skipped when `+0x9f0` is already 0):
   - a "magical" death (effect subtype bits 8) against a creature immune to death (immunity 32)
     with a spell id only gives feedback 0x7f;
   - killer `+0x154` = the creator; `AwardKillXP` (`0x004fb1e0`, 8.3); unless player-controlled,
     leave the party/faction structures (`0x005bfa70`);
   - `EndCombatRound`, clear the round target; run **OnDeath** (`ScriptDeath` `+0x280`)
     immediately;
   - death animation: unless the animation state `+0x4c4` is 3, 4 or 14, pick state 3 or 4 at
     random and play 10000 (`0x004efef0`);
   - `+0x19c` = 0, state flags `+0x9f0` = 0, HP = −11 (if higher), `0x004eded0`, `0x004f6f30`;
     remove every effect except those with duration type 3 or 4 and those `0x004df420` keeps
     (`removefxondeath.2da`, rules.md) (med);
   - if the creature is **not** a downed party member: with int 0 = 0 (or the creature not
     destroyable) queue DESTROY_OBJECT after `appearance.2da` `DestroyObjectDelay` seconds
     (default 3); with int 0 = 1 also apply visual effect 6003 first. Encounter bookkeeping
     (`+0xa24`, `0x00594310`, `+0xa28`);
   - if it **is** a downed party member: send script event 10 to the module, which runs
     `Mod_OnPlrDeath` (module `+0xf8`; GetLastPlayerDied = `+0x16c`). The shipped modules name
     `nw_o0_death`, which does not exist, except `k_pkor_pcdeath` and `k_dan_death`;
   - sound-set entry 0x10; if client option bit 0x4000 ("Party Member Down" auto-pause) is set and
     another party member is up, pause (reason 9); if it is the player's creature, switch control
     to the next party member who is up (`0x005edf80` → `0x005f7960`) and close panels
     (`0x0062b150`).

What brings a downed party member back up, and the "Your entire party has been killed" end
(strref 42351), were not found (see Open questions). Party members up and out of combat
regenerate in `AIUpdate` using `regeneration.2da` (InCombat/OutOfCombat × health/Force, per
second as a percentage of the maximum); the shipped table gives only out-of-combat Force
regeneration (1 %/s). (high for the regeneration code)

### 8.3 XP for a kill (`CSWSCreature::AwardKillXP` `0x004fb1e0`)

Only when the dead creature is not the PC, not a party member, and its faction's standing towards
the player's is ≤ 10 (hostile). XP = `GetKillXPValue` (`0x004f19e0`, formula in rules.md) ×
(1 + `npc.2da` row 10 `PercentXP` / 100 × party count), rounded, given to the party
(`0x005653a0`). Feedback "<killer> killed <victim>: N XP" (strref 1407) goes to the killer (an
area of effect's creator stands in for it) or to the player creature. (high for the gate, med for
the party-count term)

### 8.4 Destruction and the body bag

DESTROY_OBJECT (event 11) in the creature handler (`0x004fece0`) acts only when the creature is not
the PC, is destroyable (`+0xec`, GFF `IsDestroyable`; also `IsRaiseable` `+0xf0`, `DeadSelectable`
`+0xf4`) and not player-controlled (high):

1. If dead: `SpawnBodyBag` (`0x004ce220`) and tell the client which bag belongs to the corpse.
2. Fade out after `appearance.2da` `FadeDelayOnDeath` (`0x004ce8a0`, `0x004ce9a0`).
3. Leave every trigger, door and placeable occupant list in the area; encounter bookkeeping; delete
   the object.

`SpawnBodyBag` (high): body-bag row = stats `BodyBag` (`+0x9da`) or else `appearance.2da`
`BODY_BAG`; if `bodybag.2da` `Corpse` is 0 and the creature has nothing to drop (`0x004f3770`,
`0x004edd60`), no bag. Otherwise build a placeable (appearance from `bodybag.2da` `Appearance`, name
from `Name`, IsBodyBag = 1, owner = the creature; a corpse row makes it non-plot and usable), place
it at the creature's position and facing, and queue SPAWN_BODY_BAG (event 17) to the area after
500 ms. `SetIsDestroyable` (routine 323) queues a destroy after 3000 ms when a dead creature
becomes destroyable.

## 9. What the engine does, what the scripts do

The engine (high):

- runs exactly one round per ATTACKOBJECT action and the impacts, reactions, damage and death
  described above;
- keeps creatures in combat for 8 s after the last hostile act and drags hostile faction-mates in
  (3.6);
- fires, in this order for one hit: **OnAttacked** when ON_MELEE_ATTACKED (event 15) is handled
  (immediately at impact; it records last attacker, attack type/mode and weapon, hostility, and
  runs `ScriptAttacked` `+0x248` unless dead or down), then **OnDamaged** when the damage effect is
  applied (6.6), then **OnDeath** (8.2); **OnEndRound** at the end of every round (3.5);
- for the player: `ActionAttack` (routine 37) queues a scheduled attack for one round plus the
  combat-step action (see actions.md); the player's own clicks go through `AddAttackActions` too.

The shipped AI (`k_ai_master` with event numbers 1003/1005/1006/1007 from the default
`k_def_*` scripts) decides what happens next: on end of round and when attacked it calls
`GN_DetermineCombatRound`, which issues the next attack, talent or move; on damage it may retarget
or approach an unseen damager; on death it shouts to allies. So "keep attacking until the target
dies" is the AI's job, round by round. (high for the script names, med for the summary)

Script getters and where they read: GetLastAttacker `+0x15c`, GetLastDamager `+0x160`,
GetLastKiller `+0x154`, GetLastHostileActor `+0x158`, GetAttackTarget `+0x504`,
GetAttemptedAttackTarget `+0x50c`, GetLastAttackType `+0x16c`, GetLastAttackMode `+0x16e`,
GetLastWeaponUsed `+0x170`, GetLastCombatFeatUsed `+0x554`, GetLastHostileTarget `+0x53c`,
GetLastAttackAction `+0x544`, GetLastAttackResult `+0x55c`, GetIsInCombat `+0x4e0`. (high)

## 10. Combat-log messages

The server sends combat details as "CC messages" (`CSWCCMessageData`, the `CScriptEvent` layout:
ints, then object ids) to every player whose creature is in the same area within 30 m
(`SendCombatMessageToNearbyPlayers` `0x004ecae0` → `0x00568570`). Each attack sends a pair: the
attacker's and the target's view. The client formats them in `0x00656d20` (a switch on the
message type) with `dialog.tlk` tokens. (high for the server side, med for the formatting)

| Type | Sender | Ints sent | Text (strrefs) |
|---|---|---|---|
| 0x12 | `SendAttackSummary` `0x005b5ea0` via `0x004ec9e0` | result, combat feat, d20 + mod, defense, damage (× the difficulty multiplier when the target is a party member), confirmed crit, sneak, coup de grace, stun state, `+0x138`, natural 20, natural 1; objects attacker, target | 42119 "<CUSTOM0> with <CUSTOM1> vs. Defense <CUSTOM2> for damage <CUSTOM3>.", 42042, 42133 Hit / 42134 Miss, 1511 Critical Hit!, 1459 Sneak Attack!, 42303 Death Blow!, 42390/42391 Automatic Hit/Miss!, 42411 Deflected!, 42421 Returned!, 42315 Offhand |
| 0x14 | `0x004ecbe0` | total, d20, mod, STR part, DEX part, feat, special to-hit, off-hand, light bonus, two-weapon feat bonus and id, Dueling bonus and id, close-range, melee-vs-ranged, Weapon Focus, effects, BAB, dual-wield penalty, natural 20, natural 1 | 42146 "Attack Breakdown: <CUSTOM0> <CUSTOM1> =", 42316 roll, 42419 base attack bonus, 42333 Dual Wield Penalty, 42334 Small Offhand Bonus, 42330 Close Proximity Ranged Bonus, 42317 melee on ranged, 42331 Weapon Focus Bonus, 42332 Effect Bonus, 42375 dexterity mod … |
| 0x15 | `0x004ecc20` | d20, threat range, is threat, confirm total, defense, `+0xf0`, confirmed | 42148 "Threat Breakdown: Roll … vs. required … - 20, threat … with Attack … vs. Defense …" |
| 0x16 | `0x004ecc60` | defense, armour, DEX part, DEX mod, class, natural, dodge + effects, Dueling, debilitated | 42149 "Defense Breakdown: <CUSTOM0> = base 10", 42338 armor, 42339 dex mod, 42340 class, 42341 natural, 42342 feats and effects mod, 42427 debilitated penalty |
| 0x17 | `0x004ecca0` | the 15 damage values, base dice, STR, feat, special bonus, —, sneak, Weapon Specialization, crit multiplier, `+0x104..+0x108` | 42150 "Damage Breakdown: <CUSTOM0> = <CUSTOM1>", 42386 Critical x, 42387 base, 42154 strength mod, 42155 bonus damage, 42156 sneak attack damage, 42363 weapon specialization, 1440–1448 damage-type words |
| 0x19 | `0x004ecce0` | the stun report bytes `+0x12c..+0x134` | (special-attack stun) |
| 0x1a | `0x004ecd20` | deflection bytes `+0x140..+0x148` | 42417 "Deflection Breakdown: <CUSTOM0> deflects projectile with <CUSTOM1> = <CUSTOM2> vs. attack <CUSTOM3>" |

Other combat messages go through the creature's feedback channel (`0x004ede10`, numbered
messages): 0x3e/0x3f damage immunity/resistance absorbed, 0x7e immune to critical hits, 0x7f
immune (death), 0x86 immune to sneak attacks, 0xbb cannot attack a friendly target; damage
summaries "<CUSTOM0> damages <CUSTOM1> for <CUSTOM2> damage" (1403), kills (1407).
`feedbacktext.2da` holds Resisted/Immune/Saved (36847–36849). The client's feedback options
(`optfeedback.gui`) choose which of these are shown (gui.md). (med)

## 11. Names

The proposals file lists every address of this page; the main ones:

| Address | Name | Conf. |
|---|---|---|
| `0x004d5f70` | `CSWSCombatRound::StartCombatRound` | high |
| `0x004d4620` | `CSWSCombatRound::EndCombatRound(int bRunScript)` | high |
| `0x004d2a10` / `0x004d2a70` | `CSWSCombatRound::InitializeNumberOfAttacks` / `CalculateOffHandAttacks` | high |
| `0x004d3da0` / `0x004d4ff0` | `CSWSCombatRound::GetWeaponAttackType` / `GetCurrentAttackWeapon` | high |
| `0x004d3440` | `CSWSCombatRound::DecrementRoundLength` | med |
| `0x005bba80` | `CSWSCreature::ResolveAttack` | high |
| `0x005bb890` / `0x005bb590` | `CSWSCreature::ResolveMeleeAttack` / `ResolveRangedAttack` | high |
| `0x005baca0` | `CSWSCreature::ResolveAttackRoll` | high |
| `0x005bb440` | `CSWSCreature::ResolveDamage` | high |
| `0x005a7ea0` | `CSWSCreatureStats::GetAttackModifierVersus` | high |
| `0x005ad0e0` | `CSWSCreatureStats::GetArmorClassVersus` | high |
| `0x005a9050` | `CSWSCreatureStats::GetDamageRoll` | high |
| `0x005a8be0` | `CSWSCreatureStats::GetDamageBonus` | high |
| `0x005a5130` / `0x005a52b0` | `CSWSCreatureStats::GetCriticalHitRoll` / `GetCriticalHitMultiplier` | high |
| `0x005a60d0` | `CSWSCreatureStats::GetBaseAttackBonus` | high |
| `0x005b8050` | `CSWSCreature::ApplyAttackImpact` | high |
| `0x005b75d0` / `0x005b6f30` | `CSWSCreature::SignalMeleeDamage` / `SignalRangedDamage` | high |
| `0x004dfa40` / `0x004e0ac0` | `CSWSEffectListHandler::OnApplyDamage` / `OnApplyDeath` | high |
| `0x004f3830` | `CSWSCreature::TakeDamage` | high |
| `0x004f2610` | `CSWSCreature::SetCombatState` | high |
| `0x00550b60` | `CSWRules::RollDice` | high |
| `0x004d09e0` / `0x004d0e40` / `0x004cf160` | `CSWSObject::DoDamageReduction` / `DoDamageResistance` / `DoDamageImmunity` (virtual slots 41–43; objects.md guessed saving throws) | high |

`0x005a6680` already carries `CSWSCreatureStats::HasFeat` but returns the remaining uses (100 =
unlimited) after checking `0x005a6630`, which is the plain "has this feat" test; the proposals
suggest `GetFeatRemainingUses` and `HasFeatInLists`, for the lead to decide.

## 12. Open questions

- **Party members getting back up and game over.** Downed members (HP < 1) get the death effect,
  HP −11 and the module OnPlayerDeath; nothing found yet restores them after combat or ends the
  game with strref 42351 ("Your entire party has been killed"). Look in the client party code
  (`0x005f7960` and around), the in-game GUI update, and `CSWPartyTable`.
- The server difficulty value used for `diffsettings.2da` (`(internal+0x10004)+0x108`) versus the
  client option used for `difficultyopt.2da`: which column each KOTOR setting selects.
- The exact pause time set by ATTACKOBJECT (a local the decompiler confused) and the client half of
  animation selection (`0x005f32e0`) that returns the `combatanimations.2da` row.
- `+0x4d2` combat mode (+5/+10 damage): no writer found. `+0x55c` (GetLastAttackResult): no writer
  found, so the routine may always return 0.
- What `+0xa9c` is (Force points refilled at round end) and `+0x8e0` (blocks storing the feat).
- The AC "versus" quirks of section 5.4 and the 0x2007 vs 0x4007 "all damage types" sentinel:
  confirm against how the effect constructors store the value (rules.md).
- Stats bytes `+0x16c/+0x16d` in the deflection roll; the energy-shield path (result 10) and its
  client function `0x00616890`.
- Damage reduction details (slot 41) and resistance bookkeeping (slot 42) are only skimmed.
- The client formatter `0x00656d20` was mapped by its strrefs, not read case by case; the exact
  token order of each line is still to be read.
- Seven attack records are constructed but only five are used.
