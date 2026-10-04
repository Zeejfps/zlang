# Force powers and feats as the player meets them: checklist

Every Force-power behaviour of the original, what the evidence for it is, and where our build stands. Owned by
the Force mechanics owner. The RE pages are [re/rules.md](../re/rules.md) (3, Force powers; 1.10 crowd control),
[re/actions.md](../re/actions.md) (3.13, CASTSPELL), [re/gui.md](../re/gui.md) ("Action menus"),
[re/combat.md](../re/combat.md); the design pages [design/rules.md](../design/rules.md),
[design/vfx.md](../design/vfx.md), [design/hud.md](../design/hud.md); the combat owner's list is
[combat.md](combat.md). The data are `spells.2da`, `forceadjust.2da`, `regeneration.2da`, `ranges.2da`,
`visualeffects.2da`, `feat.2da`; the power scripts are the original's `k_sp1_generic` (every power), so
effects, damage dice, saves and durations come from it and what is checked here is the engine around it.

Status words as in combat.md: **matches** (checked against the evidence through the player's input path),
**fixed** (was wrong, fixed on this branch, then checked), **open** (wrong or missing, with the reason).

## How it is tested

The casting itself goes through the HUD like a player: the target is selected, the middle slot of the target
block is cycled with a click on its arrows and pressed with the key `2` (or a click), the self slots with the
keys `4`..`7`. Setup may cheat (`lib/ingame/test_force.ctx`, `FRAME ui ...`):

| Command | Does |
|---|---|
| `jedi CLASS LEVEL [dark]` | the leader becomes a Jedi (3 Guardian, 4 Consular, 5 Sentinel) of that level by the level-up rules (history, Force die, feats, powers by the auto-level order) |
| `powers all\|ROW,ROW\|none`, `fp N`, `feat ROW,ROW` | the Force powers (spells.2da rows) the leader knows, its Force points, feats |
| `fspawn TEMPLATE TAG DIST [DEG]` | a creature DIST m from the leader, DEG degrees left of its facing |
| `rules [TAG]` | the rules' view of the leader or a tagged creature: classes, abilities, Force points, DC, state, AI mask, effects, gear mask |
| `fclick TAG` | clicks the centre of a HUD control (the block's arrows move with the target) with the same mouse events as `ui click` |
| `play TAG ROW` | plays an animations.2da row on a creature |

`python kotor/tools/py/force_run.py --powers 46 --target g_sithtroop01 --count 2 --shots 70,90` builds the input
script, runs `kotor/out/kotor_frc.exe` headless and prints the lines about the leader and the targets (cast, payment,
save, effects, damage, state); `force_battery.py` does one power per process; `montage.py` lays screenshots in a
grid. `--log combat,trace` prints every effect applied (`effect KIND (N leaves, id, duration KIND SECONDS s, spell
ROW) on ID`), every save, vfx and sound. `--speed 1` when a script presses a key right after changing the
powers (the HUD lists rebuild every 0.2 s of presented time, and `--speed 8` presents every 8th tick).

## The player's input path

| # | Behaviour (original) | Evidence | Status |
|---|---|---|---|
| 1 | The target block of a hostile creature has three slots; the middle one lists the leader's hostile Force powers: one entry per `ForceHostile` line (0 stun/stasis, 1 droid, 2 choke/wound/kill, 3 affliction/plague/slow, 4 fear/horror/insanity, 5 shock/lightning/storm, 6 push/whirlwind/wave, 7 drain/death field, 8 breach/suppress, 9 saber throw), the known power of the line with the highest `ForcePriority`, lines in order | gui.md "Action menus"; `0x006191f0` → `0x0064af10` → `0x0064a870` (category 1 = hostile; entry value = category x 1000 + line x 10 + priority) | fixed (the slot was empty: no hostile power could be cast) |
| 2 | A power whose `Exclusion` bit matches the target's race is left out: bit 2 (organic powers) for a droid (racialtypes 5), bit 1 (droid powers) for a human (6), both shown for other races | `0x006191f0` | fixed |
| 3 | An entry that cannot be used is dimmed (alpha 0.25); pressing it shows the reason in the message bar for 5 s with the refusal sound: "Force Depleted" (38613), "Restricted by Armor" (38614), "Missing Item" (38615) | gui.md; `UseAction 0x00689610` | fixed (checked: armour, depleted) |
| 4 | The arrows cycle the slot with wrap-around; the chosen power stays chosen from target to target | gui.md; `Refresh 0x00689410` keeps the selected id per kind of target | fixed |
| 5 | Keys `1` `2` `3` press the target slots, Shift with them cycles; keys `4` `5` `6` `7` press the self slots (friendly power, medical item, other item, mine) | keymap.2da | fixed (`4`..`7` were not bound; Shift is the controls owner's) |
| 6 | The self slot of friendly powers lists one power per `ForceFriendly` line (0 cure/heal, 1 aura/shield/armor, 2 speeds, 3 valors, 4 resist force/immunity, 5 energy resistances), the highest priority first | `0x00616230` (category 3); the items per the items owner's rules | fixed (it listed every friendly row) |
| 7 | Using a power puts a hostile target in combat and replaces what the leader was doing (queues behind it in combat mode unless Shift) | UseAction; controls owner's queue rule | matches |
| 8 | Out of range the leader runs toward the target until it is within the range, then casts | actions.md 3.13: range = `ranges.2da` PrimaryRange of the Range letter (P and T 2.25, S 10, M 15, L 28, W) + both creatures' personal space less 0.1 | matches (checked from 19 m; the range of `W` is 10, the RE page says 15: unread) |
| 9 | The block's lists only exist while the target is on the screen | ours (the HUD builds the block over the visible target) | open (the original builds the lists from the selection; keys on an off-screen target do nothing here) |
| 10 | Hovering a target slot names its selected entry above the self slots (`LBL_ACTIONDESC`); the tooltips are "Activate Left/Middle/Right Action" (48303/48307/48311) | gui.md | fixed (the tooltip was the entry's name and nothing showed in the label) |
| 11 | A droid leader's middle slot lists the droid utilities of its equipment (`FUN_00618c20`) | gui.md | open (T3-M4 and HK-47 are not Force users; their device lists are the items owner's) |

## The cast

The original (`AIActionCastSpell 0x00514af0`, actions.md 3.13) per power: the action faces the target and starts
a combat round of conjuration + cast + catch time (170 + 1330 + 0 ms; the saber throws 560 + 1940 + 500);
during the conjuration the conjure animation plays; **at its end** (170 ms) the Force points are paid, the cast
animation starts, the cast visuals and sound play and the impact script runs at once: no Force power has a
projectile (spells.2da `Proj` is 0; only the grenades fly), so the effect lands then, and the cast animation plays
on until the end of the round. A silence (entangle) effect breaks the cast after the payment.

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 12 | Payment at the end of the conjuration, not at the click; refused when the Force points are short, the armour forbids the power (`ForbidItemMask`) or the saber is missing (`RequireItemMask`) | actions.md 3.13 | fixed (paid at the click and the effect landed 1.5 s late) |
| 13 | The impact script runs at the end of the conjuration (170 ms) | `SpellCastAndImpact 0x004cdf50`, delay `ComputeSpellImpactDelay 0x004cb9e0` = 0 without a projectile | fixed |
| 14 | Cost = base x `forceadjust.2da` (row = alignment / 10; `goodcost` for light powers, `evilcost` for dark, 1.0 for universal) for the player's party; others pay the base | rules.md 3.2 | matches (L10 light 85: Stun 20 -> 16, Choke 15 -> 22, Push 10) |
| 15 | Casting never changes alignment | rules.md 3.9 | matches |
| 16 | Save DC = 5 + level + WIS + CHA + Force Focus (+1/+2/+4) | rules.md 3.5 | matches (DC 24 at consular level 10, WIS 20, CHA 14) |
| 17 | The caster plays the conjure then the cast animation (`hand`/`self` castout1, `dark` castout2, `up` castout3, `throw` throwsab), the power's `cast*visual` models and the cast sound `v_useforce` | spells.2da columns; the animation names are ours (the client's table is unread) | matches (sound and models added); the light cast model `v_con_light` does not exist in the install, so a light power shows no hand glow, as the data say |
| 18 | After the cast the player's creature goes on attacking its target | ours (the original's client-side auto-attack was not read) | matches (the attack is queued when the cast ends) |
| 19 | Force points come back at 1 % of the pool a second out of combat and not in combat; no hit-point regeneration | `regeneration.2da`, rules.md 3.8 | fixed (nothing ever called `regenerate_pools`: the pool only fell); checked 170 -> 190 in 10 s |
| 20 | The Force bar of the HUD and the character sheet follow the pool | gui.md | matches |

## Crowd control, push, speed, visuals (what the world does with the rules' events)

The rules library reports STATE, FORCE_PUSH, KNOCKDOWN, VISUAL_ON/OFF; `lib/engine/fight_state.ctx` is what the
engine does with them.

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 21 | A state (stun 4, paralysis 5, sleep 6, choke 7, horror 8, whirlwind 10, droid stun 3) clears the creature's actions, aborts its round, makes it uncommandable, masks its AI (no move, no attack) for the duration and runs OnEndCombatRound when it ends | rules.md 1.10 | matches (rules) and fixed (the engine now does the AI pickup) |
| 22 | The state's looping animation: choke, horror, whirlwind, sleep, paralyzed (the creature set for beasts); a stunned creature stays in its stance | `UpdateStateAnimation 0x004f28d0` (stun = `pausedrnk`, which most models lack) | fixed (the animation names are the animations.2da rows that carry the state's name) |
| 23 | A stun keeps VFX_DUR_STUN (`v_stun_imp`) on the creature until it ends, a droid stun sparks (1007) | rules.md 1.10 | fixed |
| 24 | Force push: thrown 5 m away from the pusher (or from the centre of EffectForcePushTargeted) up to the end of the walkmesh, facing the pusher; it falls, lies and gets up over 2.55 s (the original leaves it unable to act that long); the script then stuns 2 s unless saved | `OnApplyForcePush 0x004e3800`, `OnRemoveForcePush 0x004de400` (AI state 0xfea1 for 2.55 s) | fixed (the target stood still); animations `die1`/`dead1`/`getupdead1` are ours |
| 25 | Knockdown: uncommandable for the duration + 1.5 s with the fall animation | rules.md 1.10 | fixed (same machinery) |
| 26 | Movement speed effects (Burst of Speed and the speeds: x1.5 after the rules' clamp; Slow, Plague, Affliction, Stasis-slow: below 1) change the creature's walk and run and their animation rate | rules.md 1.3 (HASTE_INTERNAL 150 %, SLOW_INTERNAL 50 %, clamp 0.125 .. 1.5) | fixed (the speed factor was never read) |
| 27 | Duration visuals (Type_FD D) stay until their effect leaves; the others play once | rules.md 1.11 | fixed for those with a model; the programmed ones (aura/shield rings, hold cage, speed streaks, `progfx` 1401-1424, 1601) have none in the install and are not drawn: open |
| 28 | Beams (EffectBeam: lightning, shock, drain life, death field, storm arcs, the droid powers) are programmed effects | rules.md 1.3 (BEAM), visualeffects `progfx_duration` 608..621 | fixed (ours: a jagged chain of `fx_lightning` streaks hand to chest, tinted per beam; the original's look was not read) |
| 29 | Spell shapes of `GetFirstObjectInShape`: the spell cylinder is a line from the caster through the target, `size` long and 1.5 m either side; the spell cone 30 degrees and `size`; the sphere around the point | `0x0054a260` | fixed (the cylinder was a capsule of radius `size`: lightning hit everything around) |
| 30 | Throw Lightsaber and its advanced form: the saber flies to up to three targets and back, always hitting for 1d6 per two levels each | `OnApplyLightsaberThrow 0x004de600` | fixed (it did nothing); the flight takes 75 ms a metre (ours), the flying saber shows its hilt without a blade: open |

## Per power (K1 has 44 Force powers, usertype 1)

Costs are the base; the party pays them times `forceadjust` (0.8 for light powers, 1.5 for dark, at light 85).
Learn levels are `spells.2da` guardian/consular/sentinel; "Jedi" means the first level. Saves use the script's DC.

| Row | Power | Side | FP | Learned at (G/C/S) | Range | Reaches | Save | What it does (script, observed) | Status |
|---|---|---|---|---|---|---|---|---|---|
| 4 | Adv Throw Lightsaber | universal | 20 | 9/9/9 | W | hostile, up to 3 in a chain (W) | none (always hits) | saber flies to each in turn and back; 1d6 per 2 levels each; cast animation `throw` | matches; the flying saber has no blade |
| 6 | Affect Mind | universal | 0 | Jedi | **** | passive | none | no action: dialogue lines test GetHasSpell(6) (k_con_fperslow) | matches (script-driven) |
| 7 | Affliction | dark | 15 | 6/6/6 | M | hostile single (M) | Fort DC 20 (poison.2da row 1) | poison, a tick every 6 s for 36 s: -1 to each ability for 60 s per tick (the data drain all six abilities; the description says the physical ones and 7 points over 21 s), slowed | fixed (the ticks drained nothing); matches poison.2da |
| 8 | Burst of Speed | universal | 20 | Jedi | P | self | - | +50% movement (rules clamp 1.5), +2 AC for 36 s | matches (movement, animation rate follow it) |
| 9 | Choke | dark | 15 | 9/9/9 | M | hostile single (M) | Fort negates part | choke state 6 s (choke animation, held), 2/3 level damage every 2 s, -4 STR/DEX/CON 24 s | matches |
| 10 | Cure | light | 25 | 6/6/6 | T | party within 15 m (cast on self) | - | heals 5 + CHA + WIS + level (22 at L10), no droids | matches |
| 11 | Death Field | dark | 20 | 18/18/18 | S | hostile within 10 m of caster | Fort half | 1-4 per level (max 10) damage, heals the caster by the sum; death-field beam | matches (beam tinted red) |
| 12 | Disable Droid | light | 10 | 6/6/6 | M | droids within 5 m of the target droid | Fort | droid stun 12 s + level damage; disable beam | matches (droid stun state and spark) |
| 13 | Destroy Droid | light | 10 | 12/12/12 | M | droids within 6 m of the target droid | Fort half | 1-6 per level damage, disabled 12 s; destroy beam | matches |
| 14 | Dominate Mind | universal | 0 | 6/6/6 | **** | passive | none | dialogue lines test GetHasSpell(14) (k_con_fpershigh) | matches (script-driven) |
| 15 | Drain Life | dark | 20 | 9/9/9 | M | hostile single (M) | Fort half | 1-4 per level (max 10) damage, heals the caster; drain beam | matches (beam tinted red) |
| 16 | Fear | dark | 10 | Jedi | M | hostile single (M) | Will negates | horrified (cowering) 6 s | matches (horror animation) |
| 17 | Force Armor | light | 15 | 12/12/12 | P | self | - | +6 AC and saves 20 s | matches |
| 18 | Force Aura | light | 15 | Jedi | P | self | - | +2 AC and saves 20 s | matches |
| 19 | Force Breach | universal | 25 | 15/15/15 | M | hostile single (M) | none | strips Force Aura/Shield/Armor, valors, speeds, resistances | matches (script; RemoveEffect checked with the valors) |
| 20 | Force Immunity | universal | 20 | 15/15/15 | P | self | - | Force immunity 60 s (opposed roll DC 15 + level) | matches (effect applied; the roll belongs to the attacker) |
| 22 | Force Valor | light | 20 | Jedi | P | party in 15 m | - | +2 STR/DEX/CON and saves 20 s | matches (stack replaced by Knight/Master Valor) |
| 23 | Force Push | universal | 10 | Jedi | M | hostile single (M) | Reflex | thrown 5 m away, lies 2.55 s then stunned 2 s unless saved; level damage after 0.4 s | matches (throw, fall, lie, rise) |
| 24 | Force Shield | light | 15 | 6/6/6 | P | self | - | +4 AC and saves 20 s | matches |
| 25 | Force Storm | dark | 20 | 18/18/18 | S | hostile within 10 m of the target (S) | Will half | 1-6 per level damage to HP and Force points; storm arcs | matches (arc beam tinted purple) |
| 26 | Force Wave | universal | 10 | 15/15/15 | S | hostile within 15 m of the caster | Reflex | thrown 5 m, 1.5 x level damage, down 6 s | matches |
| 27 | Force Whirlwind | universal | 10 | 9/9/9 | M | hostile single (M) | Reflex | whirlwind state 9 s (lifted, spinning), level/3 damage every 2 s | matches (whirlwind animation); the script says 9 s, the description 12 s |
| 28 | Heal | light | 25 | 12/12/12 | T | party within 15 m (self cast) | - | heals 10 + CHA + WIS + level (27 at L10), cures poison | matches |
| 29 | Stasis | light | 20 | 9/9/9 | M | hostile single (M) | Fort slows instead | paralysed 12 s (paralyzed animation) | matches |
| 30 | Horror | dark | 10 | 6/6/6 | M | hostile within 5 m of the target | Will negates | horrified 12 s | matches |
| 31 | Insanity | dark | 10 | 12/12/12 | M | hostile within 10 m of the target | Will negates | horrified 12 s | matches |
| 32 | Kill | dark | 15 | 12/12/12 | M | hostile single (M) | Fort | choke 6 s, damage half the target's maximum over the choke | matches |
| 33 | Knight Valor | light | 20 | 9/9/9 | P | party in 15 m | - | +3 STR/DEX/CON and saves, poison immunity, 20 s; replaces Force Valor | matches |
| 34 | Knight Speed | universal | 20 | 9/9/9 | P | self | - | speed x1.5 (clamp), +4 AC, +1 attack per round, 36 s | matches (extra attacks are the combat owner's) |
| 35 | Force Lightning | dark | 20 | 9/9/9 | M | hostile on a line 16 m ahead, 1.5 m either side | Will half | 1-6 per level (max 10) damage; lightning beam to each | matches (shape fixed; beam drawn) |
| 36 | Master Valor | light | 20 | 15/15/15 | P | party in 15 m | - | +5 STR/DEX/CON and saves, poison immunity, 20 s; replaces the lesser valors | matches |
| 37 | Master Speed | universal | 20 | 15/15/15 | P | self | - | speed x1.5 (clamp), +4 AC, +2 attacks, 36 s | matches (extra attacks are the combat owner's) |
| 38 | Plague | dark | 15 | 12/12/12 | M | hostile single (M) | none (poison.2da row 2, DC 100) | poison, a tick every 6 s for 72 s: -1 to each ability for 100 s per tick (description: 12 points over 12 s), slowed | fixed (the ticks drained nothing); matches poison.2da |
| 40 | Improved Energy Resistance | universal | 10 | 9/9/9 | P | party | - | absorbs 15 of sonic/fire/cold/electrical, poison and disease immunity, 120 s | matches (effect applied) |
| 41 | Force Resistance | universal | 20 | 9/9/9 | P | self | - | Force resistance (opposed roll vs the attacker) | matches (effect applied; ResistForce is the rules lead's) |
| 42 | Energy Resistance | universal | 10 | Jedi | P | self | - | absorbs 15 of sonic/fire/cold/electrical, 120 s | matches (effect applied) |
| 43 | Shock | dark | 20 | Jedi | M | hostile single (M) | Will half | 1-6 per level (max 10) damage; shock beam | matches |
| 44 | Stasis Field | light | 20 | 15/15/15 | M | hostile within 10 m of the target | Fort slows instead | paralysed 12 s | matches |
| 45 | Slow | dark | 15 | Jedi | M | hostile single (M) | Will negates | -2 AC, Reflex and attack, slowed 30 s | matches |
| 46 | Stun | light | 20 | Jedi | M | hostile single (M) | Fort slows instead | stunned 9 s (the stun's stars held on it) | matches |
| 47 | Stun Droid | light | 10 | Jedi | M | droid single (M) | Fort negates | droid stun 12 s + level damage; stun beam | matches |
| 48 | Force Suppression | universal | 25 | 9/9/9 | M | hostile single (M) | none | strips first and second tier buffs | matches (script) |
| 49 | Throw Lightsaber | universal | 20 | Jedi | W | hostile single (W), at least 5 m | none (always hits) | saber flies out and back; 1d6 per 2 levels | matches; the flying saber has no blade |
| 50 | Wound | dark | 15 | Jedi | M | hostile single (M) | Fort negates | choke-like state 6 s, 2/3 level damage every 2 s | matches |

## Level-up, abilities, feats

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 31 | The level-up panel's Powers step lists the powers the class's level column reaches that the Jedi lacks, dimmed while a prerequisite is missing, with as many picks as classpowergain.2da gives; Recommended fills the auto-level order; Affect Mind and Dominate Mind are for the player character only | gui.md (`pwrlvlup`); rules.md 6 | matches (the screens lead's panel; checked with `tools/ingame/scripts/levelup_jedi.txt`: the Powers step, Recommended, OK) |
| 32 | The Abilities panel's Powers tab shows each known power with base cost, the light/dark modifier and the cost per use for the leader's alignment | gui.md | matches |
| 33 | Passive feats: Force Focus (+1/+2/+4 to the DC), Force Immunity: Stun/Paralysis/Fear (refuse the state), Jedi Defense, Conditioning and the implants show in the sheet and the rules | rules.md 3.5, 1.10 | matches (rulescheck; the combat feats are combat.md's) |
| 34 | Affect Mind and Dominate Mind add dialogue options for a Jedi who knows them: the DLG lines test `GetHasSpell(6)` / `GetHasSpell(14)` (k_con_fperslow, k_con_fpershigh) | scripts | matches (script-driven; `GetHasSpell` reads the known powers) |

## Open

- The look of a cast and of the programmed effects (auras, shields, the hold cage, the beams' exact look, the saber's
  blade in flight) is ours or missing; there is no reference but the data.
- The block's lists for an off-screen target (row 9).
- Companions in the party did not fight or cast in the test arenas (their OnPerception ran but they never
  attacked the hostile troopers); that is the party AI, not the powers. Bastila/Jolee casting through
  `k_ai_master` is therefore unchecked.
- `W` range (saber throws): 10 m (ranges.2da row 5) against the RE page's 15 m.
- The animation names of the cast and state animations are ours (the client's table, `0x0069f650`, is unread).
