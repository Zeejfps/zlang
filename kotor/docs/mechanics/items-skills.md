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
The scripts are in `kotor/tools/items/scripts/`; `sh kotor/tools/items/check.sh` runs the ones with a checkable log line (12 scenarios, about a minute). They click controls by tag with `ui clickctl TAG [ROW]` and
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

## Open items

- An equip in combat as a combat-round entry; OnEquipItem (no module uses it).
- Per-minute item uses (one droid shield).
- The HEAL action (Treat Injury as an action): only scripts can queue it and none of the shipped ones was found
  to; medpacs add the rank through their own script.
- The new flag is not saved. The action timer over the portrait (lock picking and the trap actions) is not drawn.
- Which security spike a player would choose (ours: the weakest that makes the roll).
- Mines, stealth: see their docs.
