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
The scripts are in `kotor/tools/items/scripts/`. They click controls by tag with `ui clickctl TAG [ROW]` and
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
| Only one item per combat round from the inventory: "can only use one item per round" (42409) | OnUseItem, creature +0xab0 | open (low): the round model keeps no per-round item flag | |
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
| Nine slot buttons; pointing at one lists "None", the worn item and every carried item that fits the creature's kind (droid/human); a click opens selection mode | CSWGuiEquip OnSlotHilighted, OnSlotClicked | matches | `equip_survey.txt` |
| Selection mode hides the slots; the portrait is under the description; the **numbers stay**; pointing at a row **puts that item on** (OnRowHilighted) so defense, damage and to-hit follow; Cancel or the menu closing puts the worn items back; a click on a row or OK keeps it | gui.md "Selection mode" | matches (we hid the numbers and changed nothing until OK) | `equip_preview.txt` |
| A row the creature cannot wear is red; pointing at it shows "You cannot equip this item. You don't have the prerequisites..." where the numbers are and OK is disabled | OnRowHilighted, CanEquipItem | matches | `equip_refuse.txt` |
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
| New items (loot taken, purchases, pick-ups, CreateItemOnObject) are magenta and listed by the New Items filter until their description has been shown, then ordinary when the screen closes | CSWGuiInventory.OnItemHilighted / OnPanelRemoved, SetItem colours | matches (not saved: a load makes none new) | `new_items.txt` |
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
| Awareness / Demolitions on mines | [traps.md](traps.md) | see there |
| Stealth | [stealth.md](stealth.md) | see there |
| Skill rank = ranks + effects + key ability + best feat tier, 0 when untrained and not usable untrained | rules.md 5.1 | matches (lib/rules) |

## 8. Mines and stealth

Summarised from [traps.md](traps.md) and [stealth.md](stealth.md) once those agents report; see them for the
lines and statuses.

## Open items

- One item per combat round (inventory message 42409).
- An equip in combat as a combat-round entry; OnEquipItem (no module uses it).
- Per-minute item uses (one droid shield).
- The HEAL action for scripts; stack counts on the HUD slots (the original keeps the stack size in the
  entry; whether and where the slot draws it was not traced).
- The new flag is not saved.
