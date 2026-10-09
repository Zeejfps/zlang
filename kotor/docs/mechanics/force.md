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
| 1 | The target block of a hostile creature has three slots; the middle one lists the leader's hostile Force powers: one entry per `ForceHostile` line (0 stun/stasis, 1 droid, 2 choke/wound/kill, 3 affliction/plague/slow, 4 fear/horror/insanity, 5 shock/lightning/storm, 6 push/whirlwind/wave, 7 drain/death field, 8 breach/suppress, 9 saber throw), the known power of the line with the highest `ForcePriority` (the first one found on a tie), lines in order; nothing is listed while the area's RestrictMode is set | gui.md "Action menus"; `0x006191f0` → `0x0064af10` (once per class slot) → `0x0064a870` (category 1 = hostile; entry value = category x 1000 + line x 10 + priority; both test RestrictMode, area `+0x2b0`) | fixed (the slot was empty: no hostile power could be cast); the RestrictMode gate fixed too (by reading the code; no run) |
| 2 | A power whose `Exclusion` value matches the target's race is left out: 0x02 (the organic-only powers) against a droid (racialtypes 5), 0x01 (the droid powers) against a human (6), both shown for other races | `0x006191f0` builds the mask (2 droid, 1 human, 0 other creature, 4 not a creature); `0x0064a870` tests it against spells.2da Exclusion (+0x188) | fixed |
| 3 | An entry that cannot be used is dimmed (alpha 0.25); pressing it shows the reason for 5 s in the target block's name label (`LBL_NAME`, in place of the target's name) with the refusal sound (GUI sound 2): "Force Depleted" (38613: the cost is above current + temporary points), "Restricted by Armor" (38614: `ForbidItemMask`), "Missing Item" (38615: `RequireItemMask` not met), "Target too Close" (42422: the target is within the Range letter's SecondaryRange, which only `W` has, 5 m) | gui.md; `0x0064a870` sets the reason codes 1 to 4 (forbidden equipment wins over too close, too close over depleted; missing item only when nothing else stops it); `UseAction 0x00689610` stores the message, `0x00685cb0` shows it | matches: `force_run.py --powers 49 --dist 3` with a saber worn says "Target too Close" in the block's name label (screenshot), `--powers 49 --dist 8` with no saber "Missing Item", `--powers 46 --fp 1` "Force Depleted" (each a `refused:` line of the combat log), `--powers 49 --dist 13` with a saber casts at once; armour checked before |
| 4 | The arrows cycle the slot with wrap-around; the chosen power stays chosen from target to target | gui.md; `UseAction 0x00689610` and `Refresh 0x00689410` keep the selected id per kind of target and slot; Shift with a slot key steps to the next entry (`0x006865b0`) | fixed |
| 5 | Keys `1` `2` `3` press the target slots, Shift with them cycles; keys `4` `5` `6` `7` press the self slots (friendly power, medical item, other item, mine) | keymap.2da | fixed (`4`..`7` were not bound; Shift is the controls owner's) |
| 6 | The self slot of friendly powers lists one power per `ForceFriendly` line (0 cure/heal, 1 aura/shield/armor, 2 speeds, 3 valors, 4 resist force/immunity, 5 energy resistances), the known power of the line with the highest priority, lines in order | `0x00616230` → `0x0064af10` (category 3, no exclusion mask); the items per the items owner's rules | fixed (it listed every friendly row) |
| 7 | Using a target slot out of combat mode turns the leader's combat mode on and replaces what the leader was doing; in combat mode the order queues behind the others, and Shift clears the queued combat actions first | `UseAction 0x00689610` (SetCombatMode, then ClearAllActions on the server creature), `0x0068ad20` (Shift: ClearAllCombatActions); controls owner's queue rule | matches for the replace and queue rule; open: the press itself does not turn combat mode on here. The original sets only the client's combat mode (`CSWCCreature::SetCombatMode` 0x00610a10 → `CClientExoApp::SetCombatMode` 0x005f3a80: the HUD flag `+0x320` and the combat camera), which the server's combat state does not follow; ours has one flag for both (`in_combat`), and setting it at the press makes the rules treat the leader as fighting (no Take 20 on a Security press, stealth broken before the attack), so this waits for a separate HUD combat-mode flag |
| 8 | Out of range the leader runs toward the target until it is within the range, then casts | actions.md 3.13: range = `ranges.2da` PrimaryRange of the Range letter (P and T 2.25, S 10, M 15, L 28, W 15 from row 19 SpellRngThrow) + each creature's radius less 0.1; `GetSpellRange 0x004eb3a0`, the ranges loaded by `CSWRules 0x00552c50` (rows 0..4 and 19) | matches for P to L (checked from 19 m); fixed for `W`, now row 19 (15 m) rather than row 5 (10 m): `force_run.py --powers 49 --dist 13` with a lightsaber, the leader casts Throw Lightsaber at once where the HEAD build walked in first |
| 9 | The block's lists follow the selection, so the keys 1 to 3 work on a target off the screen; the block then sits at the screen's edge on the target's side | `UpdateActionMenus` 0x00689d80, `FUN_00686090` | matches: `force_run.py --powers 46 --angles 160` (the target behind the leader) casts on key 2, the block and the arrow at the left edge (screenshot) |
| 10 | Hovering a target slot puts its selected entry's name in the target block's name label (`LBL_NAME`, in place of the target's name; `LBL_ACTIONDESC` belongs to the self slots); the tooltips are "Activate Left/Middle/Right Action" (48303/48307/48311) | gui.md; `0x00685cb0` | fixed (the tooltip was the entry's name and nothing showed in the label) |
| 11 | A droid leader's middle slot lists the hostile abilities of its equipment, one per ForceHostile line (10 to 19 for the droid items), the higher ForcePriority keeping a line, cast with the item; dimmed for no use left (reason 1), a forbidden item (2) or a missing one (3), the last that applies winning | `0x006191f0` (leader race 5) → `FUN_00618c20` | matches: T3-M4 made leader (`ui leader`) with a stun ray (`g_i_drdutldev001`) lists it in the middle slot and key 2 casts spell 116 at the target (`force_run.py`, `ui fight`) |

## The cast

The original (`AIActionCastSpell 0x00514af0`, actions.md 3.13) per power: the action faces the target and starts
a combat round of conjuration + cast + catch time (170 + 1330 + 0 ms; the saber throws 560 + 1940 + 500);
during the conjuration the conjure animation plays (picked by `CastAnim`; `ConjAnim` is never read); **at its
end** (170 ms) the Force points are paid, the cast animation starts, the cast visuals and sound play and the
impact script runs at once: no Force power has a projectile (spells.2da `Proj` is 0; only the grenades fly), so
the effect lands then, and the cast animation plays on to the end of the cast time; the saber throws then play
the catch for 500 ms and the action ends. An entangle effect (true type 0x12, `EffectEntangle`; not silence)
breaks the cast after the payment, so the points are lost.

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 12 | Payment at the end of the conjuration, not at the click; the Force points are checked when the cast is ordered, and the payment itself cannot fail (points lost in between floor the pool at 0); the cast fails on any frame where the armour forbids the power (`ForbidItemMask`) or the saber is missing (`RequireItemMask`) | actions.md 3.13, rules.md 3.2, 3.3; `PayForcePowerCost 0x004eddd0` | fixed (paid at the click and the effect landed 1.5 s late); open: ours checks the points again after the approach and at the payment and refuses where the original pays down to 0 |
| 13 | The impact script runs at the end of the conjuration (170 ms) | `SpellCastAndImpact 0x004cdf50` posts AI event 8 (SPELL_IMPACT) to the caster after the delay of `ComputeSpellImpactDelay 0x004cb9e0`, 0 without a projectile | fixed |
| 14 | Cost = base x `forceadjust.2da` (row = alignment / 10; `goodcost` for light powers, `evilcost` for dark, 1.0 for universal) for the player's party; others pay the base | rules.md 3.2 | matches (L10 light 85: Stun 20 -> 16, Choke 15 -> 22, Push 10) |
| 15 | Casting never changes alignment | rules.md 3.9 | matches |
| 16 | Save DC = 5 + level + WIS + CHA + Force Focus (+1/+2/+4) | rules.md 3.5 | matches (DC 24 at consular level 10, WIS 20, CHA 14) |
| 17 | The caster plays the conjure then the cast animation, both picked by the `CastAnim` code (`ConjAnim` is never read; ours names them `self` castout1, `dark` castout2, `up` castout3, `throw` throwsab), the power's `cast*visual` models and the cast sound `v_useforce` | spells.2da columns; `AIActionCastSpell 0x00514af0` (conjure 10015/10016/11000/10162, cast 10017/10018/10019/10061 by code), rules.md 3.1; the animation names are ours (the client's table is unread) | matches (sound and models added); open: ours picks the conjure animation from `ConjAnim`, so the eight powers that conjure `hand` but cast `dark` or `up` (Affliction, Drain Life, Fear, Horror, Insanity, Plague, Force Storm, Force Wave) conjure with the wrong set; the light cast model `v_con_light` does not exist in the install, so a light power shows no hand glow, as the data say |
| 18 | After the cast the player's creature goes on attacking its target | ours (the original's client-side auto-attack was not read) | matches (the attack is queued when the cast ends) |
| 19 | Force points come back for a party member at 1 % of the pool (maximum + temporary) a second out of combat and also in a fight it started by attacking; nothing once it was attacked, until that combat ends; no hit-point regeneration | `regeneration.2da`, rules.md 3.8; `AIUpdate 0x004fe210` takes the OutOfCombat row unless in combat for reason 1 (+0xac0) | fixed (nothing ever called `regenerate_pools`: the pool only fell); checked 170 -> 190 in 10 s; open: ours stops it in every fight, also one the party started |
| 20 | The Force bar of the HUD and the character sheet follow the pool | gui.md | matches |

## Crowd control, push, speed, visuals (what the world does with the rules' events)

The rules library reports STATE, FORCE_PUSH, KNOCKDOWN, VISUAL_ON/OFF; `lib/engine/fight_state.ctx` is what the
engine does with them.

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 21 | A state (stun 4, paralysis 5, sleep 6, choke 7, horror 8, whirlwind 10, droid stun 3) clears the creature's actions and its round's scheduled actions, makes it uncommandable, masks its AI for the duration (movement only for stun, droid stun, choke, horror and whirlwind; movement and attack for paralysis, 0xfff1; sleep 0xfea1) and runs OnEndCombatRound when it ends | rules.md 1.10; `0x004da330` | matches (rules) and fixed (the engine now does the AI pickup) |
| 22 | The state's looping animation: choke, horror, whirlwind, sleep, paralyzed (the creature set for beasts); a stunned creature stays in its stance | `UpdateStateAnimation 0x004f28d0` sets a state code (sleep 11, stun 2, choke 5, whirlwind 6, horror 7, droid stun 8, paralysis 12) and plays animation 10000; the code's animation is the client's (unread), so stun as `pausedrnk`, which most models lack, is unchecked | fixed (the animation names are the animations.2da rows that carry the state's name) |
| 23 | A stun keeps VFX_DUR_STUN (`v_stun_imp`) on the creature until it ends, a droid stun sparks (1007) | rules.md 1.10 | fixed |
| 24 | Force push: thrown 5 m away from the pusher (or from the centre of EffectForcePushTargeted) up to the end of the walkmesh, facing the pusher; it falls, lies and gets up over 2.55 s (the original leaves it unable to act that long); the script then stuns 2 s unless saved | `OnApplyForcePush 0x004e3800` (distance float 3, 5 m when 0; walk-line test unless int 1 is set), `OnRemoveForcePush 0x004de400` (AI state 0xfea1 for 2.55 s once the 0.1 s push effect ends) | fixed (the target stood still); animations `die1`/`dead1`/`getupdead1` are ours |
| 25 | Knockdown: uncommandable for the duration + 1.5 s with the fall animation | rules.md 1.10 | fixed (same machinery) |
| 26 | Movement speed effects (Burst of Speed and the speeds: x1.5 after the rules' clamp; Slow, Plague, Affliction, Stasis-slow: below 1) change the creature's walk and run and their animation rate | rules.md 1.3 (HASTE_INTERNAL 150 %, SLOW_INTERNAL 50 %), 1.7 (`GetMovementRateFactor 0x004ec370`, clamp 0.125 .. 1.5) | fixed (the speed factor was never read) |
| 27 | Duration visuals (Type_FD D) stay until their effect leaves; the others play once | rules.md 1.11 | fixed for those with a model; the programmed ones (aura/shield rings, hold cage, speed streaks, `progfx` 1401-1424, 1601) have none in the install and are not drawn: open |
| 28 | Beams (EffectBeam: lightning, shock, drain life, death field, storm arcs, the droid powers) are programmed effects | rules.md 1.3 (BEAM), visualeffects `progfx_duration` 608..621 | fixed (ours: a jagged chain of `fx_lightning` streaks hand to chest, tinted per beam; the original's look was not read) |
| 29 | Spell shapes of `GetFirstObjectInShape`: the spell cylinder is a line from the caster through the target, `size` long and 1.5 m either side; the spell cone within 30 degrees of the line (cosine 0.866) and `size`; the sphere around the point | `0x0054a260` (shapes 0, 3, 4) | fixed (the cylinder was a capsule of radius `size`: lightning hit everything around) |
| 30 | Throw Lightsaber and its advanced form: the saber flies to up to three targets and back with no attack roll, each hit for d6 x (level / 2) through the target's resistances; the legs share the power's cast time (1940 ms) in proportion to their length, whatever the distance (static reading, needs a runtime check) | `OnApplyLightsaberThrow 0x004de600` (dice = level x 0.5, `0x0073e9ac`; leg time = leg length x CastTime / path length) | fixed (it did nothing); open: the flight takes 75 ms a metre here, and the flying saber shows its hilt without a blade |

## Per power (K1 has 44 Force powers, usertype 1)

Costs are the base; the party pays them times `forceadjust` (0.8 for light powers, 1.5 for dark, at light 85).
Learn levels are `spells.2da` guardian/consular/sentinel; "Jedi" means the first level. Saves use the script's DC.

| Row | Power | Side | FP | Learned at (G/C/S) | Range | Reaches | Save | What it does (script, observed) | Status |
|---|---|---|---|---|---|---|---|---|---|
| 4 | Adv Throw Lightsaber | universal | 20 | 9/9/9 | W | hostile target (W) and up to two creatures friendly to it within 5 m of it; the menu refuses a target within 5 m | none (no attack roll) | saber flies to each in turn and back; d6 per 2 levels each (the engine's roll); cast animation `throw` | matches (the range 15 m, row 8; the 5 m refusal, row 3, same code as row 49); open: the flying saber has no blade |
| 6 | Affect Mind | universal | 0 | Jedi | **** | passive | none | no action: dialogue lines test GetHasSpell(6) or GetHasSpell(14) (k_con_fperslow) | matches (script-driven) |
| 7 | Affliction | dark | 15 | 6/6/6 | M | hostile single (M) | Fort DC 20 (poison.2da row 1; the script itself rolls none) | poison, a tick every 6 s for 36 s: -1 to each ability for 60 s per tick (the data drain all six abilities; the description says the physical ones and 7 points over 21 s), slowed 50 %; nothing when the target is already poisoned | fixed (the ticks drained nothing); matches poison.2da |
| 8 | Burst of Speed | universal | 20 | Jedi | P | self | - | +99 % movement (x1.5 after the rules' clamp), +2 AC for 36 s | matches (movement, animation rate follow it) |
| 9 | Choke | dark | 15 | 9/9/9 | M | hostile single (M) | Fort negates | choke state 6 s (choke animation, held), 2/3 level damage at 1, 3 and 5 s, -4 STR/DEX/CON 24 s | matches |
| 10 | Cure | light | 25 | 6/6/6 | T | party within 15 m (cast on self) | - | heals 5 + CHA + WIS + level (22 at L10), no droids | matches |
| 11 | Death Field | dark | 20 | 18/18/18 | S | hostile humans (and placeables) within 12 m of the caster | Fort half | d4 per level (max 10 dice) damage, heals a hurt caster by the sum; death-field beam | matches (beam tinted red) |
| 12 | Disable Droid | light | 10 | 6/6/6 | M | the target droid and hostile droids within 5 m of it | Reflex half (no stun) | droid stun 12 s + level damage; disable beam | matches (droid stun state and spark) |
| 13 | Destroy Droid | light | 10 | 12/12/12 | M | the target droid and hostile droids within 6 m of it | Reflex half (no stun) | d6 per level damage (no cap), droid stun 12 s; destroy beam | matches |
| 14 | Dominate Mind | universal | 0 | 6/6/6 | **** | passive | none | dialogue lines test GetHasSpell(14) (k_con_fpershigh) | matches (script-driven) |
| 15 | Drain Life | dark | 20 | 9/9/9 | M | hostile single (M) | Fort half | 1-4 per level (max 10) damage, heals the caster; drain beam | matches (beam tinted red) |
| 16 | Fear | dark | 10 | Jedi | M | hostile single (M) | Will negates | horrified (cowering) 6 s | matches (horror animation) |
| 17 | Force Armor | light | 15 | 12/12/12 | P | self | - | +6 AC and saves 20 s | matches |
| 18 | Force Aura | light | 15 | Jedi | P | self | - | +2 AC and saves 20 s | matches |
| 19 | Force Breach | universal | 25 | 15/15/15 | M | hostile single (M) | none (no resistance check) | strips Force Aura/Shield/Armor, the three valors, the three speeds, both energy resistances, Resist Force and Force Immunity | matches (script; RemoveEffect checked with the valors) |
| 20 | Force Immunity | universal | 20 | 15/15/15 | P | self | - | Force resistance 15 + level for 60 s (an attacker's power is resisted when d20 + its level falls short); replaces Resist Force | matches (effect applied; the roll belongs to the attacker) |
| 22 | Force Valor | light | 20 | Jedi | P | friends within 30 m | - | +2 Fort/Reflex/Will and +2 to all six abilities 20 s; first removes every valor (and Battle Meditation) from the caster's faction within 30 m | matches (stack replaced by Knight/Master Valor) |
| 23 | Force Push | universal | 10 | Jedi | M | hostile single (M); not large, huge, turret or immobile creatures | Reflex (still pushed) | failed: thrown 5 m away, level damage after 0.4 s, lies 2.55 s then stunned 2 s; saved: thrown, half the level damage at once, no stun | matches (throw, fall, lie, rise) |
| 24 | Force Shield | light | 15 | 6/6/6 | P | self | - | +4 AC and saves 20 s | matches |
| 25 | Force Storm | dark | 20 | 18/18/18 | S | hostile within 12 m of the target (S) | Will half | d6 per level (max 10 dice, one roll for all) damage to HP and Force points; storm arcs | matches (arc beam tinted purple) |
| 26 | Force Wave | universal | 10 | 15/15/15 | S | hostile within 15 m of the caster | Reflex (still pushed) | failed: 1.5 x level damage after 0.4 s, thrown 5 m, stunned 6 s from 2.55 s; saved: thrown, half damage, no stun | matches |
| 27 | Force Whirlwind | universal | 10 | 9/9/9 | M | hostile single (M); hostile creatures within 5 m of it are pushed away unless they save | Reflex negates | whirlwind state 9 s (lifted, spinning), level/3 damage at once and every 2 s up to 11 s; shielded geo droids are not lifted | matches (whirlwind animation); the state lasts 9 s, the damage about 12 s, as the description says |
| 28 | Heal | light | 25 | 12/12/12 | T | party within 15 m (self cast) | - | heals 10 + CHA + WIS + level (27 at L10), cures poison | matches |
| 29 | Stasis | light | 20 | 9/9/9 | M | hostile single (M) | Fort slows instead | paralysed 12 s (paralyzed animation) | matches |
| 30 | Horror | dark | 10 | 6/6/6 | M | hostile humans within 5 m of the target | Will negates | horrified 12 s | matches |
| 31 | Insanity | dark | 10 | 12/12/12 | M | hostile humans within 10 m of the target | Will negates | horrified 12 s | matches |
| 32 | Kill | dark | 15 | 12/12/12 | M | hostile single (M) | Fort (level damage instead) | failed: choke 6 s and three ticks of a third of half the target's maximum HP at 1, 3 and 5 s | matches |
| 33 | Knight Valor | light | 20 | 9/9/9 | P | friends within 30 m | - | +3 Fort/Reflex/Will and +3 to all six abilities, poison immunity, 20 s; replaces the other valors | matches |
| 34 | Knight Speed | universal | 20 | 9/9/9 | P | self | - | speed x1.5 (clamp), +4 AC, +1 attack per round, 36 s | matches (extra attacks are the combat owner's) |
| 35 | Force Lightning | dark | 20 | 9/9/9 | M | hostile on a line 17 m from the caster through the target, 1.5 m either side | Will half | d6 per level (max 10 dice, one roll) damage, each save halving the shared amount for the rest of the line (script); lightning beam to each | matches (shape fixed; beam drawn) |
| 36 | Master Valor | light | 20 | 15/15/15 | P | friends within 30 m | - | +5 Fort/Reflex/Will and +5 to all six abilities, poison immunity, 20 s; replaces the lesser valors | matches |
| 37 | Master Speed | universal | 20 | 15/15/15 | P | self | - | speed x1.5 (clamp), +4 AC, +2 attacks, 36 s | matches (extra attacks are the combat owner's) |
| 38 | Plague | dark | 15 | 12/12/12 | M | hostile single (M) | none (poison.2da row 2, DC 100) | poison, a tick every 6 s for 72 s: -1 to each ability for 100 s per tick (description: 12 points over 12 s), slowed | fixed (the ticks drained nothing); matches poison.2da |
| 40 | Improved Energy Resistance | universal | 10 | 9/9/9 | P | the party, at any distance (not those with an energy resistance) | - | absorbs 15 of cold/fire/sonic/blaster/electrical, poison immunity, 120 s | matches (effect applied) |
| 41 | Force Resistance | universal | 20 | 9/9/9 | P | self | - | Force resistance 10 + level for 60 s (opposed roll vs the attacker; not while Force Immunity is on) | matches (effect applied; ResistForce is the rules lead's) |
| 42 | Energy Resistance | universal | 10 | Jedi | P | self | - | absorbs 15 of sonic/fire/cold/electrical, 120 s | matches (effect applied) |
| 43 | Shock | dark | 20 | Jedi | M | hostile single (M) | Will half | 1-6 per level (max 10) damage; shock beam | matches |
| 44 | Stasis Field | light | 20 | 15/15/15 | M | hostile within 10 m of the target, not droids | Fort slows instead | paralysed 12 s | matches |
| 45 | Slow | dark | 15 | Jedi | M | hostile single (M) | Will negates | -2 AC, Reflex and attack, slowed 30 s | matches |
| 46 | Stun | light | 20 | Jedi | M | hostile single (M) | Fort slows instead | stunned 9 s (the stun's stars held on it) | matches |
| 47 | Stun Droid | light | 10 | Jedi | M | droid single (M) | Fort (half damage, no stun) | droid stun 12 s + level damage; stun beam | matches |
| 48 | Force Suppression | universal | 25 | 9/9/9 | M | hostile single (M) | none | strips Force Aura, Force Shield, Force Valor, Knight Valor, Burst of Speed, Knight Speed, Resist Force and Energy Resistance | matches (script) |
| 49 | Throw Lightsaber | universal | 20 | Jedi | W | hostile single (W); the menu refuses a target within 5 m | none (no attack roll) | saber flies out and back; d6 per 2 levels (the engine's roll) | matches (the range 15 m, row 8; the 5 m refusal, row 3); open: the flying saber has no blade |
| 50 | Wound | dark | 15 | Jedi | M | hostile single (M) | Fort negates | choke-like state 6 s, 2/3 level damage every 2 s | matches |

## Level-up, abilities, feats

| # | Behaviour | Evidence | Status |
|---|---|---|---|
| 31 | The level-up panel's Powers step lists the powers the class's level column reaches that the Jedi lacks, dimmed while a prerequisite is missing, with as many picks as classpowergain.2da gives; Recommended fills the auto-level order; Affect Mind and Dominate Mind are for the player character only | gui.md (`pwrlvlup`); rules.md 6 | matches (the screens lead's panel; checked with `tools/ingame/scripts/levelup_jedi.txt`: the Powers step, Recommended, OK) |
| 32 | The Abilities panel's Powers tab shows each known power with base cost, the light/dark modifier and the cost per use for the leader's alignment | gui.md | matches |
| 33 | Passive feats: Force Focus (+1/+2/+4 to the DC), Force Immunity: Stun/Paralysis/Fear (refuse the state), Jedi Defense, Conditioning and the implants show in the sheet and the rules | rules.md 3.5, 1.10 | matches (rulescheck; the combat feats are combat.md's) |
| 34 | Affect Mind and Dominate Mind add dialogue options for a Jedi who knows them: the DLG lines' k_con_fperslow passes with either power (`GetHasSpell(6)` or `GetHasSpell(14)`), k_con_fpershigh only with Dominate Mind (`GetHasSpell(14)`) | scripts | matches (script-driven; `GetHasSpell` reads the known powers) |

## Open

- The look of a cast and of the programmed effects (auras, shields, the hold cage, the beams' exact look, the saber's
  blade in flight) is ours or missing; there is no reference but the data.
- Companions in the party did not fight or cast in the test arenas (their OnPerception ran but they never
  attacked the hostile troopers); that is the party AI, not the powers. Bastila/Jolee casting through
  `k_ai_master` is therefore unchecked.
- Combat mode at the press of a target slot needs a HUD combat-mode flag apart from `in_combat` (row 7).
- The Force points: checked again at the payment here (row 12); regeneration in a fight the party started
  (row 19).
- The conjure animation comes from `CastAnim`, not `ConjAnim` (row 17).
- The saber's flight time: the original spreads the cast time over the legs (row 30).
- The animation names of the cast and state animations are ours (the client's table, `0x0069f650`, is unread).
