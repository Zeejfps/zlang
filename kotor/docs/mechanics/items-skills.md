# Items and skills in play: the original's behaviour and where we stand

What the original does when the player uses, wears, finds and throws things and when the party's skills are
rolled, one line per behaviour, with the evidence and our status. The status is **matches** (checked by a
run that goes through the mouse and keys, named in the last column), **open** (with the reason), or
**script** (the original's own scripts do it; we run them). Evidence is the RE notes
([party-items-saves.md](../re/party-items-saves.md) 4 and 5, [actions.md](../re/actions.md) 3.7, 3.8, 3.13,
3.14, [gui.md](../re/gui.md) "Action menus", "CSWGuiInventory", "CSWGuiEquip", [rules.md](../re/rules.md)
5) and the decompiled functions named in the lines (addresses; `python kotor/tools/py/rex.py fn ADDR`).

Mines and traps are [traps.md](traps.md), stealth [stealth.md](stealth.md); their lines are summarised at the end.

## How these were tested

`sh kotor/tools/items/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...` runs an input script from a checkpoint
(`docs/testing.md`) with `--no-render --speed 8` and keeps the log and the pictures under `kotor/out/items/`.
The scripts are in `kotor/tools/items/scripts/`; `sh kotor/tools/items/check.sh` runs the ones with a checkable log line (13 scenarios, about a minute; 6 of their patterns are stale, see "Known failing checks"). They click controls by tag with `ui clickctl TAG [ROW]` and
`ui movectl`, which find the control (or the list row) in the topmost shown panel and send the platform's own
pointer events to its centre, so the panels' hit test decides what happens, as for a player. Test-only commands
are used only for setup (`ui giveitem`, `ui stat KEY N`, `ui relock`, `ui faction`, `ui hp`); reading helpers:
`ui fx` (the effects on a creature), `ui log` (the HUD's message log), `ui inv`, `ui bag`, `ui locks`,
`ui getglobal`, `ui ctl` (where a control is). Things that bit while testing: a checkpoint fades in for about 100
frames and its story starts a conversation, which hides the HUD (`hush`); the fast mode steps the UI every 8
frames, so setup and click are spaced out.

## 1. Using items

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Inventory (I): the pointer over a row shows its description, **one click on a row** does what the row does (uses the item, or says why not); Use Item does the same for the row last pointed at | CSWGuiInventory.OnItemHilighted, the row's click callback (gui.md); the refusals only make sense on a click | matches (was two clicks, and no description until a click) | `inv_click.txt` |
| An equippable item clicked in the inventory: "You cannot equip items from the INVENTORY screen..." (42485); other non-usable: 42486 | OnEquippableItemClicked / OnUnusableItemClicked | matches | `inv_click.txt` |
| A medpac or repair kit at full vitality: 42499; a recovery kit with nobody hurt: 48494 | gui.md Row click 3, 4 | matches | `inv_click.txt` |
| Using an item while the menu is up pauses the world: the item is used when the menu closes (actions wait for the clock) | gameloop.md 6.2 | matches | `inv_click.txt` (hp 6 until closed, then 18) |
| Only one item per combat round from the inventory (42409: "Each party member can only use one item per round during combat") | OnUseItem, creature +0xab0 | matches (a 3 s window after an item ability begins, `Fighter.item_ms`) | `one_item_round3.txt` |
| HUD self slots (bottom right), best first: friendly power, **medical** (ItemType 45 medpacs, 47 recovery kit, 26 repair kits), **other** (stims, ItemType 25, and any item whose power has `itemtargeting` 1 in spells.2da: disguises, energy shields, droid devices, plot serums; a forearm shield or droid device only while worn), mines. Grenades are not here | list builder 0x006197d0 and the item test 0x00616520 (the arm and belt cells are offered with the bag) | matches (items); mines and powers: see traps.md and the Force owner | `slots_lists.txt` |
| A slot's arrows cycle its entries; an unusable one shows dimmed and a click says why for 5 s (Force Depleted, Restricted by Armor, Missing Item, Full Health, PC Dead) | UseSelfAction 0x0068ad60 | matches | `selfslots.txt` (earlier lead) |
| A click replaces the leader's queued actions; once an item's ability has begun it is **unclearable**, a second order waits behind it | actions.md 3.13 (ITEMCASTSPELL "unclearable on its first frame") | matches (`actions::clear_for_player`; was cleared, so two quick uses lost the first) | `consumables2.txt` |
| The ability lands part way through a 1.5 s action and the use is spent with it: medpacs, stims, repair kits 750 ms (injection animation 10070), recovery kit 750, grenades 700 (800 from 10 m or more) with the throw, droid devices 300, forearm shields 600 of 1 s; a cleared cast keeps its item | AIActionItemCastSpell 0x0050f170, actions.md table | matches (`item_cast_ms`; was spent at the start and ran the power's 1.5 s) | `consumables2.txt`, `grenade.txt` |
| Medpac / advanced / life support: heal = 10, 20 + 2x, 30 + 3x the Treat Injury rank, + Wisdom modifier (the script k_sup_healing); antidote kit removes poison; repair kits heal droids | the original's scripts | script (hp 5 to 17, 22 and 22 observed) | `consumables2.txt` |
| Adrenals, battle stimulants (+ability, speed, attack, damage for 120 s with a visual) | k_sup_comshots | script (effects listed by `ui fx`) | `consumables2.txt` |
| Using an item fires the module's OnActivateItem; GetItemActivated, GetItemActivator, GetItemActivatedTarget answer (the Endar Spire's k_pend_activate waits for a medpac) | module script, nwscript | matches (the getters returned OBJECT_INVALID; `rt_item::signal_activation`) | `medpac_tutorial.txt` (the script runs) |
| Uses of an item: single use takes one from the stack and the item goes with the last one ("Lost Item: ..." and the HUD's lost icon); n charges per use take 7 - row charges; unlimited rows (13) are free; per-day rows (8-12) are not in the data of any shipped CastSpell property; per-minute rows (14, 16: one droid shield) are not counted | party-items-saves.md 5.10; a scan of every UTI | matches except per-minute (open, one item) | |
| Droid repair kits and energy shields with a droid as leader | CanUseItem race rule | matches (hp 5 to 22 by both kits) | `consumables2.txt` |
| The Useable Items filter, the Use Item button's colour and a row click use one test (0x00616520 with every category): medical items, stims, items whose power has `itemtargeting` 1 (shields and droid devices only worn), mines for a creature with Demolitions. **A grenade is not usable from the inventory**: it is absent from Useable and a click says "This is not a useable or equipable item" (42486) | the test's callers (gui.md Filters and Row click) | matches (a click on a grenade did nothing; Useable listed grenades) | `inv_filters.txt` |
| The slot description names a stack: "Medpac (2)" | 0x00686e20, format `%s (%d)` | matches | `slots_lists.txt` |
| Security spikes (property 37, "+10 bonus to Security", one use): the weakest spike in the bag that makes the roll succeed is used up | OPENLOCK takes the spike as an action parameter (the player's choice in the original; which one a player picks was not traced) | matches in effect, the selection is ours | `security_spike.txt` (32 vs DC 28, Tunneler x2 to x1) |

## 2. Equipping

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| **Slot view.** Nine slot buttons; pointing at one (or the keys moving to it) lists "None", the worn item and every carried item that fits the creature's kind (droid/human) on the right, **without the rows' frames and not selectable**: the pointer passes the list by, a row is not hilighted or clicked, the keys do not enter it. The description pane, the title and OK are hidden. Only a click (or Enter) on the slot makes the list selectable | CSWGuiEquip OnSlotHilighted, SetSelectionMode (clears the list's flag 0x08 and every row's frame alpha; GetRow starts rows at alpha 0), OnRowHilighted (un-hilights a row at once while LB_DESC is hidden) | matches (rows could be clicked at once, which opened selection mode, and had frames) | `equip_flow.txt` |
| **Selection mode** (click or Enter on a slot): the slots, the portrait and the party buttons hide, the list becomes selectable with its rows' frames and the keyboard, the worn item's row is selected (nothing is when the slot is bare), the description sits where the portrait was, "Select Item to Equip", Cancel; the **numbers stay**; pointing at a row (or the keys on it) **puts that item on** (OnRowHilighted) so defense, damage and to-hit follow; Cancel / Escape or the menu closing puts the worn items back, a click on a row or OK keeps what is on; either goes back to the slot view with the slot's button hilighted and the party buttons back. Escape closes the menu only in the slot view | gui.md "Selection mode", EndSelection, UpdatePartyButtons | matches | `equip_preview.txt`, `equip_flow.txt` |
| A row is marked when the list is built (OnSlotHilighted) and not when it is pointed at: **state 2** the creature cannot wear it (CanEquipItem: proficiency, class, alignment, race); **state 3** (a weapon hand) the other hand holds a weapon that does not pair with it, the screen's own rule on top of the engine's: equal WeaponWield and it must be 2 (one-handed melee) or 4 (pistol), except a weapon of size 4 in the right hand. A marked row has a red-orange frame (0.74, 0.11, 0); pointing at it shows 38450 ("You cannot equip this item. You don't have the prerequisites...") or 42271 ("...while an incompatible weapon is equipped in your other hand") in the numbers' place **and hides the two stat icons with them**, OK is dimmed, and nothing is put on (what the pointer put on before stays; a click on it just leaves selection mode with that) | OnSlotHilighted 0x006b9470, OnRowHilighted, CanEquipItem 0x0051aa60, FUN_006b5060 | matches (the text was drawn over the icons, state 3 did not exist, a click stayed in selection mode) | `equip_refuse.txt`, `equip_dual.txt` |
| Row colours (CSWGuiItemEntry::SetItem 0x006b6710, FUN_006b5060): the **frame** carries the colour, the name keeps the list's blue and turns yellow and pulses under the pointer like a button's. Usable and worn: frame menu blue (0, 0.66, 0.98), hilight frame yellow (0.98, 1, 0). New (the inventory only): magenta (0.95, 0, 0.85), the normal frame at alpha 0.5. Cannot wear: red-orange (0.74, 0.11, 0) hilighted or not. The equipment, loot and store lists never pass the new flag, so the items a player is given or picks up are not magenta there | SetItem's callers (inventory passes bit 7 of the item flags, container and equip pass 0) | matches (names were magenta, frames near-white, the equipment list showed new items) | `new_items.txt`, pictures |
| Open: the "Hide Unequippable" option (the row is left out when CanEquipItem or the proficiency fails) is read by the Options panel but not by the list; the hexagonal icon frames (`lbl_hex_3/6/7`) around the rows' pictures are not drawn | OnSlotHilighted (client options +0x14 bit 0), SetItem | open | |
| Proficiency feats, class/alignment/race/feat limits, droid/human, the weapon-hand rules (a two-handed weapon empties the left hand, dual wield needs a one-handed right weapon of the same family) | party-items-saves.md 4.3 (lib/rules/equip.ctx) | matches | `equip_refuse.txt`, earlier `equip_rules.txt` |
| Left weapon slot while the right weapon has WeaponSize 4: 42344; no candidates: 42345; body armour in combat: 1506 | gui.md "Selection mode" | matches | earlier `equip_cant.txt` |
| Taking an item off puts it in the bag and **merges** with an identical stack | RunUnequip, AddItem | matches (put_back used to add a second entry) | `equip_preview.txt` |
| Item properties become equipped-duration effects owned by the item, removed when it comes off | party-items-saves.md 4.6 | matches | `props_effects.txt` (gauntlets, belt, visor, armour, sword; 0 effects after) |
| An equip in combat is a combat-round entry costing 1.5 s; the module hears OnEquipItem | actions.md 3.8 | open: equipping is instant. No shipped module sets OnEquipItem (scan of every IFO) | |
| The equip screen is a 2D portrait with the numbers, there is no 3D view | CSWGuiEquip.SetCreature (LBL_PORTRAIT) | matches | |
| The numbers of a hand: **damage as a range "lowest-highest"** (format `%d-%d`, 0x00756a10), not dice: lowest = number of dice, highest = dice x die, each plus the Strength modifier for a melee weapon (none for a ranged one), +2 for Weapon Specialization, plus the damage effects (item properties and spells: a flat 1 to 5 or the dice of a larger iprp_damagecost row, minus decreases, each side capped at 36), each end at least 1: a Long Sword (1d12) at Strength 18 reads "5-16", at Strength 8 "1-11". **Attack bonus** `+%d` above zero and `%d` otherwise ("+3", "0", "-1"). Both are the menu blue; **green** (0.28, 0.92, 0.11) when the effects raised the damage, or the attack bonus is above the base attack bonus. A bare right hand shows the unarmed numbers (1 to 2 for a small creature, 1 to 1 for a medium one, plus Strength; the melee attack bonus); a bare left hand shows nothing, except that a double weapon (WeaponWield 3) in the right hand fills the left column with its off-hand end | UpdateStats 0x006b9970, FUN_005a9e10 (the range), format strings at 0x00756a10 (`%d-%d`), 0x00748ec0 (`+%d`), 0x0073d720 (`%d`), colour 0x007a23e4 | matches (we printed dice and a sign: "1d12+2" does not fit the 56 pixel box and wrapped to "1D12+-" / "2" with the wrap's hyphen; zero read "+0"; nothing was green; a bare hand was blank). The effect sum is ours, not traced past the cap and the hand test | `equip_damage.txt` |

## 3. Stacks, plot items, the shared inventory

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| One party inventory and one purse; every member shares it | party-items-saves.md 3.6, 5.5 | matches (`w.bag`, `party::inventory_of`) | |
| Identical items stack up to `baseitems.stacking`; a list shows "Name xN" | 5.2, 5.3 | matches | `equip_preview.txt` (Blaster Pistol x2) |
| New items (loot taken, purchases, pick-ups, CreateItemOnObject) have a magenta frame in the inventory and are listed by the New Items filter until their description has been shown, then ordinary when the screen closes | CSWGuiInventory.OnItemHilighted / OnPanelRemoved, SetItem frame colours | matches (not saved: a load makes none new) | `new_items.txt` |
| "Acquired Item: <name>", "Lost Item: <name>", "Acquired N Credits" in the message log and the HUD's item/credits icons light for 4 s | feedback 50/51, notices 7/8 (SetPossessor, AddItem), dialog.tlk 1449, 1450, 1493, 1494 | matches (nothing was logged or lit) | `loot_click.txt` |
| Plot items are in the Quest Items filter and cannot be sold | 5.8 | matches (the stores are the screens lead's) | |
| Script gold (GiveGoldToCreature, TakeGoldFromCreature) logs "Acquired/Lost N Credits" and lights the credits icon | feedback 148/149, notice 1 | matches | |
| Item values, prices, the stores | 5.8 | not in this scope (screens lead) | |

## 4. Picking up, containers, giving

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Using a container opens the loot panel; **one click on an item takes it** (to the party, "Acquired Item"); Get Items takes all, last to first; OnInvDisturbed per item | 5.7, CSWGuiContainer | matches (a click used to select; a second took) | `loot_click.txt` |
| Switch To lists the party's items; one click puts one in the container | CSWGuiContainer.ShowGiveItems, 0x24 GIVEITEM | matches | `container_give.txt` |
| PICKUPITEM walks to 1.1 m, crouches 1.5 s, acquires on the second pass | actions.md 3.8 | matches (earlier lead's action, now with the feedback) | |
| There is no drop command in the original's inventory | gui.md ("No drag and drop") | matches | |

## 5. Grenades and area effects

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| The target block's right slot lists the party's grenades (base items of ItemType 6) for a creature target; a click throws one (the leader approaches to the power's range, throws, the blast runs k_sup_grenade: damage in a radius with a Reflex save for half, the visual and sound) | list builder 0x006198e0 / 0x006196a0; AIActionItemCastSpell | matches (the slot was an empty placeholder) | `grenade.txt` (hp 15 to -11, Frag Grenade x4 to x3) |
| The middle slot lists Force powers and combat feats | 0x006191f0 | not mine (the Force owner) | |
| Throwing at a creature that is not an enemy turns it hostile | spell hostile setting | matches (cast_spell's combat start) | |

## 6. Locks and Security (re-verified)

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A locked door or container offers Security first in the target block when the leader has it; a click walks up, kneels 1.5 s, rolls Security + spike bonus + (20 out of combat, d20 in combat) against OpenLockDC, "Player attempts Security on Door : *success* : (Take 20 + 5 = 25 vs. DC 12)", the door opens | actions.md 3.7, rules.md 5.2 | matches through `ui clickctl BTN_TARGET0` | `security2.txt` |
| Failure: the roll is the only message; key-only locks say so; keys open; AutoRemoveKey | playthrough.md "Lock picking" | matches (earlier lead; the Endar Spire replay runs the bridge door) | replay |

## 7. Skills in play

| Skill | The original | Status |
|---|---|---|
| Security | OPENLOCK, above | matches |
| Computer Use, Repair | the computer panel shows the leader's Computer Use and Repair ranks and the party's programming spikes (`k_computer_spike`) and repair parts (`k_repair_part`), recounted with every line (0x006a8240); the replies' checks and the spike use are the terminal's scripts (GetSkillRank, TakeItem) | matches (the counters always read 0; `dlgview::sync_computer`) - `computer.txt` |
| Repair on droids | repair kits (ItemType 26) heal a droid leader; the skill's rank enters the heal script | matches (script) |
| Treat Injury | the medpac script adds the rank; the HEAL action (UseSkill, 0x00517a60) is queued only by scripts (no player button) | script for medpacs; the HEAL action is open (nothing in the player's UI calls it) |
| Persuade, Awareness (outside traps) | dialogue scripts roll GetSkillRank + d20 or fixed | script |
| Awareness / Demolitions on mines | detection and the four trap actions, [traps.md](traps.md) | matches (section 8) |
| Stealth | the toggle, the contests, [stealth.md](stealth.md) | matches (section 8) |
| Skill rank = ranks + effects + key ability + best feat tier, 0 when untrained and not usable untrained | rules.md 5.1 | matches (lib/rules) |

## 8. Mines and stealth

Written by two sub-agents against the same rules (every line, evidence and test is in their docs):

**Mines ([traps.md](traps.md); scenarios in `kotor/tools/traps/scripts/`, run with `tools/items/run.sh` on
`module:tar_m04aa`).** Matches, through the pointer, keys and HUD: trap triggers load (TrapType to traps.2da, the
type's script, the faction rule); detection is the original's always-on detect mode (Awareness + d10 + 10, every
0.1 s within 20 m, a party find marks it for the party); a found mine shows its model, is picked with the mouse and
Q/E, becomes the target with the MINE SIGHTED auto-pause; the target block offers Disable (left) and Recover
(middle) to a leader with Demolitions, a second click and R take the default; the four trap actions walk up, kneel
4.5 s and roll Demolitions + (20 or d20) against the DC (DC above 35 impossible, the setter succeeds); a hostile
mine goes off under the party ("You triggered a Mine!", the type's script does the damage through the rules,
explosion, one-shot removal); a party mine hurts only others; the HUD's mine slot lists trap kits and lays one
(SetDC roll, kit spent). Open: no action-timer bar (the HUD has none; lock picking lacks it too), what the client
shows for Examine, trap script routines nothing calls, the mine slot label wraps.

**Stealth ([stealth.md](stealth.md); `sh kotor/tools/stealth/check.sh`).** Matches: TB_STEALTH and G (only with a
stealth unit worn or Stealth ranks, in an area that allows it), the solo-mode box when companions are about,
stealth walk speed and the shimmer, detection by the original's sight and hearing contests (Stealth against
Awareness, no die), what ends it (attack, combat, one's own powers, taking off the belt, conversations and
transitions; doors and using objects do not), the stealth XP pool and routines, save and load. Open: the exact
client stealth speed (we use the walk rate), the frame-buffer distortion look, the combat log's spot line, rest
ending stealth (no party rest), the straggler teleport that solo mode turns off.

## 9. The upgrade bench (workbench)

The Ebon Hawk's workbench (`RepairTable1` in `ebo_m12aa`, OnUsed `k_pebo_upgrade`) and every other `ShowUpgradeScreen` call open it: three
panels, `upgradesel` (the categories), `upgradeitems` (the items of one) and `upgrade` (the slots of one item); code `lib/screens/ups_*.ctx`.
RE: [gui.md](../re/gui.md) "Upgrade bench"; functions `CSWGuiUpgradeSelect::OnPanelAdded` 0x006c4520, `CSWGuiUpgradeItems::FillItemList`
0x006c5b90 / `OnUpgradeItem` 0x006c2df0 / `ReturnItem` 0x006c5e90, `CSWGuiUpgrade::OnPanelAdded` 0x006c4d70 / `OnSlotClicked` 0x006c6500 /
`OnUpgradeChosen` 0x006c5510 / `OnSlotHilighted` 0x006c3c30 / `OnCancel` 0x006c61f0, the slot table `g_aUpgradeSlots` 0x00756fb0.
Scripts `bench_*.txt` run by `check.sh` (module `ebo_m12aa`, items given with `ui giveitem`, clicks by `ui clickctl`; `ui ctl TAG` also prints
whether the control is visible and enabled); `LOG=actions` adds a line `upgrade bench: NAME assembled|cancelled, upgrades BITS (were BITS)`.

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A category is upgradeable by the type of the upgrade slots its items carry (upgrade.2da `upgradetype` of the property tags: 0 lightsaber, 1-3 melee, 4-7 ranged, 8-9 armour); only items whose UTI properties carry an `UpgradeType` are upgradeable at all (a plain Blaster Pistol is not; Carth's, Bendak's, Mission's Vibroblade, Bastila's saber are) | `CSWSItem::GetUpgradeCategory` 0x005541c0 | matches | `bench_*.txt` |
| A category the party has nothing for has its button **disabled and its picture hidden** (the dimmed label alone left four white tiles that looked like buttons and did not answer a click: the report "I can't click any category" was a party with nothing upgradeable) | `CSWGuiUpgradeSelect::OnPanelAdded` flips the button's text colour and the picture label's visible bit (+0x44 bit 1) | matches (the picture stayed) | `bench_empty.txt` |
| Items listed: the equipped upgradeable items of the leader, then of every available selectable companion (slots 0 to 17), then the party's bag | `FillItemList`, `AddCreatureItems` | matches | `bench_ranged.txt` |
| An item row is a button: **one click** takes the item to the bench, pointing at a row describes it; the Upgrade Item button takes the selected row | `FillItemList` gives each row handlers 0 (describe), 0x27 and 0x2d (`OnUpgradeItem`) | matches (a click on an unselected row only selected it) | `bench_ranged.txt` |
| Taking an item: a worn one comes off, a stack gives one unit, a loose one leaves the bag. **A dual wielder's other-hand weapon comes off too** (the left first when the right is taken) | `OnUpgradeItem` (flags +0xc30, id +0xc34) | matches (the engine slid the left weapon into the right hand and the upgraded one then pushed it into the bag) | `bench_dual.txt` |
| The lightsaber and the melee items use the three slot controls (`LBL/BTN_UPGRADE31..33`), the ranged items and the armour the four (`41..44`; the armour's two slots are the second and third) | `FUN_006c3aa0`, `FUN_006c2f80`, `CSWGuiUpgrade::OnPanelAdded` | matches (it was lightsaber and ranged on the four, melee and armour on the three, armour on the first two) | `bench_saber.txt`, `bench_armour.txt` |
| Slots by category: lightsaber power crystal, colour crystal, power crystal; ranged scope, improved energy cell, beam splitter, hair trigger; melee vibration cell, durasteel alloy, energy projector; armour reinforcement, mesh underlay. An empty slot shows its kind's own picture (`i_scope`, `i_energy`, `i_beam`, `i_hair`, `i_vcell`, `i_durasteel`, `i_imp_eng`, `i_armorrein`, `i_powerc`, `i_colorc`), dim while the party has none; a filled slot shows the upgrade's icon | `g_aUpgradeSlots` (type, picture, strref per slot) | matches | `bench_ranged.txt` |
| On opening the first slot is hilit. Pointing at a slot of a weapon or armour names its kind of upgrade (top left), says "Upgrades:", empties the count box and gives the item properties that upgrade adds in the big box on the left; the item's description is in the right box | `OnSlotHilighted` 0x006c3c30, `FUN_0055f510` | matches (the item name was in the top box, the whole description on the left and the right box was empty: `LB_DESC` has no prototype row in the file, so it shared the lightsaber box's) | `bench_ranged.txt` |
| A lightsaber slot names what is in it, else "Power Crystal" / "Color Crystal" | `OnSlotHilighted` | matches | `bench_saber.txt` |
| A slot of a weapon or armour: a filled one gives its upgrade back to the party, an empty one takes the one upgrade item of its kind from the party's stock (nothing when there is none); if the wearer then could not use the item again the box 42489 asks, and Cancel undoes the install | `OnSlotClicked`, callback `FUN_006c6120` | matches | `bench_ranged.txt` (the box: open, no shipped upgrade needs a feat the leader lacks) |
| **A lightsaber slot always opens the list of crystals**: a power slot lists None, the crystal it has, and every power crystal the party has that is not in the other power slot; the colour slot lists the saber's colour and every other colour crystal the party has. The pictures, the names and Assemble give way to the list (the description box stays); one click chooses, pointing at a row names it (and a power crystal gives the properties it adds). None gives the crystal back | `OnSlotClicked` (lightsaber branch), `OnUpgradeChosen` 0x006c5510, `FUN_006c5370`, `FUN_006c2f80` selection mode | matches (a filled slot gave its crystal back at once, no None, an empty one needed stock) | `bench_saber.txt` |
| A new colour crystal replaces the saber by the `upcrystals.2da` saber of that colour and kind (short, long, double), keeping its upgrades and its stolen flag; the old colour crystal goes back to the party | `OnUpgradeChosen` | matches (made at Assemble) | `bench_saber.txt` |
| Assemble keeps the changes, Cancel (and Escape) restores the item and the stock; either puts the item back in its hand if it still may wear it, else in the bag, and returns to the item list with that item selected; a bench opened by a script's item closes the whole screen | `OnAssemble` 0x006c6190, `OnCancel` 0x006c61f0, `ReturnItem` 0x006c5e90 | matches (the first row was selected again) | `bench_saber.txt`, `bench_dual.txt` |
| Armour comes off and goes back on across the bench; an upgrade's properties apply from the next equip (Armor Reinforcement: defense, Mesh Underlay: resistance and immunity) | `ReturnItem`, the upgrade rule (4.6) | matches | `bench_armour.txt` |
| The item is shown as a rotating 3D model (`upgitem_light` rig with the item's model, "rotate" at 70 degrees a second; a lightsaber "powered") in `3D_MODEL` (lower right) or `3D_MODEL_LS` (upper left, big) | `FUN_006c3630`, `CSWGuiUpgrade::Render` 0x006c33a0 | open: the area stays empty | |

## Open items

- The bench's 3D model of the item (above).

- An equip in combat as a combat-round entry; OnEquipItem (no module uses it).
- Per-minute item uses (one droid shield).
- The HEAL action (Treat Injury as an action): only scripts can queue it and none of the shipped ones was found
  to; medpacs add the rank through their own script.
- The new flag is not saved. The action timer over the portrait (lock picking and the trap actions) is not drawn.
- Which security spike a player would choose (ours: the weakest that makes the roll).
- Mines, stealth: see their docs.
- The equipment list leaves out unwearable rows only when the "Hide Unequippable" option is on; ours reads the option but does not use it. The hexagonal frames (`lbl_hex_3/6/7`) around the rows' pictures are not drawn.

## Known failing checks (`check.sh`, left as they are)

`sh kotor/tools/items/check.sh` reports **6 failures** in 4 scenarios, the same with the executable from before the
equipment-screen work and with fresh checkpoints, so they are not regressions of the screens. All 6 are checks that
went stale; the behaviour they test was seen working by hand.

| Scenario | Failed patterns | Why |
|---|---|---|
| `security` | `*success* : (Take 20 + 5 = 25 vs. DC 12)` | The script clicks `BTN_TARGET0`, but a locked door's target block now has its first slot empty and the Security lock in the second (`BTN_TARGET1`), so the click does nothing and the leader never walks up. Clicking `BTN_TARGET1` logs "Player attempts Security on Door : *success* : (Take 20 + 5 = 25 vs. DC 12)". |
| `security_sp` | `*success* : (Take 20 + 12 = 32 vs. DC 28)`, `Security Spike Tunneler x1` | The same click on `BTN_TARGET0`: no roll, so no spike is used up. |
| `consumables` | `fx : 7 effects` | `ui fx` prints the creature's id now (`fx 2147483647 : 7 effects`), so the pattern without it matches nothing. The effects are there. |
| `props` | `fx : 3 effects`, `fx : 0 effects` | The same id in the `ui fx` line. |

Fixing them is changing `BTN_TARGET0` to `BTN_TARGET1` in `security2.txt` and `security_spike.txt` and the patterns to `fx [0-9]* : N effects`.
