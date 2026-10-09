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
The scripts are in `kotor/tools/items/scripts/`; `sh kotor/tools/items/check.sh` runs the ones with a checkable log line (18 scenarios; 6 of their patterns are stale, see "Known failing checks"). They click controls by tag with `ui clickctl TAG [ROW]` and
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
| A medpac or repair kit at full vitality: 42499, except for a poisoned user, whose row gets no click handler, so the click does nothing; a recovery kit with nobody hurt (the user and party members 1 and 2): 48494; with someone hurt the recovery kit's row also gets no click handler, so it cannot be used from here (both no-handler cases need a runtime check) | gui.md Row click 3, 4, 5 (`AddItemRow` 0x006b44d0) | matches for the two messages; open: ours says 42499 to a poisoned user too, and uses a recovery kit when someone is hurt | `inv_click.txt` |
| Using an item from the inventory is instant and is no action: the item's first CastSpell power is cast on the user and the use spent at the click (no animation, the user's queue left alone); its effect arrives through the spell-impact event after the user's stored impact delay (`+0x1c8`, not computed for this use), so while the menu has the world paused it lands when the menu closes (needs a runtime check: a stored delay of 0 would land at once) | OnUseItem 0x006b25e0 → 0x004efe30 (`SpellCastAndImpact`, `ConsumePropertyUse`), SpellCastAndImpact 0x004cdf50, gameloop.md 6.2 | open: ours queues the item's 1.5 s action in place of the user's queue (animation, the use spent at its impact); the effect does wait for the menu to close | `inv_click.txt` (hp 6 until closed, then 18) |
| Only one item per combat round from the inventory: an inventory use in combat mode starts a 3 s cooldown (creature `+0xab0` = 3000); while it runs, the player creature in combat after being attacked (`+0xac0` = 1) is told 42409 ("Each party member can only use one item per round during combat") and the Use Item button is dim. Uses from the HUD and the target block (ITEMCASTSPELL) neither start nor check it | OnUseItem 0x006b25e0, 0x004efe30, CSWGuiInventory.Render 0x006b4bb0 | open: ours starts the 3 s window (`Fighter.item_ms`) when any item ability begins, a HUD use's too and an inventory use's only when the menu closes, and does not dim the button | `one_item_round3.txt` |
| HUD self slots (bottom right), best first: friendly power, **medical** (ItemType 45 medpacs, 47 recovery kit, 26 repair kits), **other** (stims, ItemType 25, and any item whose power has `itemtargeting` 1 in spells.2da: disguises, energy shields, droid devices, plot serums; a forearm shield or droid device only while worn), mines. Each item list takes the leader's worn left-arm, right-arm and belt items first (only where the area's RestrictMode is 0), then the bag. Grenades are not here | list builder 0x006197d0 (masks 1, 4, 2 from 0x00619db0), entries 0x006193a0, the item test 0x00616520 | matches (items) except the order: ours lists the worn items after the bag (open); mines and powers: see traps.md and the Force owner | `slots_lists.txt` |
| A slot's arrows cycle its entries; an unusable one shows dimmed and a click says why for 5 s in the slot description (`LBL_ACTIONDESC`, fading over the last 2.5 s; Force Depleted, Restricted by Armor, Missing Item, Full Health, PC Dead), GUI sound 2. A medpac or repair kit is dimmed at full vitality unless the leader is poisoned, a recovery kit while party members 0 to 2 are all unhurt | UseSelfAction 0x0068ad60, 0x00686e20, 0x006193a0 | matches (the dimming, the reasons, 5 s); open: ours shows the reason in the combat message bar without the fade, and dims a poisoned leader's medpac at full vitality | `selfslots.txt` (earlier lead) |
| A click out of combat mode replaces the leader's queued actions (ClearAllActions right after the request); in combat mode it is added behind them. Once an item's ability has begun it is **unclearable**, a second order waits behind it | UseSelfAction 0x0068ad60 (client combat mode `+0x440` bit 0), actions.md 3.13 (ITEMCASTSPELL "unclearable on its first frame") | matches out of combat mode (`actions::clear_for_player`; was cleared, so two quick uses lost the first); open: in combat mode ours clears the queue too | `consumables2.txt` |
| From the HUD and the target block the ability lands part way through the action and the use is spent with it: medpacs, stims, repair kits 750 ms of 1.5 s (injection animation 10070), recovery kit 750 of 1.5 s (10136), grenades 700 of 1.5 s (800 from 10 m or more) with the throw, forearm shields 600 of 1 s, droid utility devices at their animation's length less 50 ms (300 without a client object) of 1.5 s, any other item (droid shields) at once, the action lasting the power's cast time + 1 ms; a cleared cast keeps its item | AIActionItemCastSpell 0x0050f170, actions.md 3.13 table | matches for medpacs, stims, repair and recovery kits, grenades and forearm shields (`item_cast_ms`; was spent at the start and ran the power's 1.5 s); open: droid utility devices (ours a fixed 300 ms), the other items (ours 1.5 s), and the animation of the recovery kit, shields and devices (ours 10127) | `consumables2.txt`, `grenade.txt` |
| Medpac / advanced / life support: heal = 10 + the Treat Injury rank, 20 + 2x, 30 + 3x the rank, + Wisdom modifier (the script k_sup_healing); antidote kit removes poison; repair kits heal droids (15 + the Repair rank, 25 + 2x, 35 + 3x, + Intelligence modifier) | the original's scripts | script (hp 5 to 17, 22 and 22 observed) | `consumables2.txt` |
| Adrenals, battle stimulants (+ability, speed, attack, damage for 120 s with a visual) | k_sup_comshots | script (effects listed by `ui fx`) | `consumables2.txt` |
| Using an item does not by itself fire the module's OnActivateItem: the module event (script event 0x12, which sets what GetItemActivated, GetItemActivator and GetItemActivatedTarget answer) is built only by EventActivateItem for a script's SignalEvent, and no shipped script calls that routine (a scan of every NCS). So the OnActivateItem scripts of end_m01aa (k_pend_activate, which waits for a medpac) and tar_m02ad (k_ptar_m02ad_aci) never run in the original (needs a runtime check) | CSWSModule::EventHandler 0x004c5120, ExecuteCommandEventActivateItem 0x00535710, UseItem 0x004fc210 and 0x004efe30 (no module event) | open: ours fires OnActivateItem on every use (`rt_item::signal_activation`) | `medpac_tutorial.txt` (the script runs) |
| Uses of an item: single use takes one from the stack and the item goes with the last one ("Lost Item: ..." and the HUD's lost icon); n charges per use take 7 - row charges, and an item whose last CastSpell property can no longer be paid is destroyed when no charge property is left usable; unlimited rows (13) are free; per-day rows (8-12) are not in the data of any shipped CastSpell property; per-minute rows (14, 16: one droid shield) are not counted | party-items-saves.md 5.10, ConsumePropertyUse 0x0055de20; a scan of every UTI | matches except per-minute (open, one item) and a charged item whose charges run out (ours keeps it at 0 charges, open) | |
| Droid repair kits and energy shields with a droid as leader | CanUseItem race rule | matches (hp 5 to 22 by both kits) | `consumables2.txt` |
| The Useable Items filter and a row click use one test (0x00616520 with every category; the filter also CanUseItem): medical items, stims, items whose power has `itemtargeting` 1 (shields and droid devices only worn), mines for a creature with Demolitions. **A grenade is not usable from the inventory**: it is absent from Useable and a click says "This is not a useable or equipable item" (42486). The Use Item button is lit only while the hilighted row's click would use the item and the inventory cooldown is not running | the test's callers (gui.md Filters, Row click, CSWGuiInventory.Render) | matches for the filter and the click (a click on a grenade did nothing; Useable listed grenades); open: ours lights the button for any usable item (a medpac at full vitality too) and ignores the cooldown | `inv_filters.txt` |
| The slot description names the entry and a stack: "Medpac (self) (2)" (every self item entry is named "<item> (self)") | 0x006193a0 (`%s (%s)`, dialog.tlk 38005), 0x00686e20 (`%s (%d)` above 1) | open: ours adds "(self)" only to a mine's entry | `slots_lists.txt` |
| Security spikes (property 37, "+10 bonus to Security", one use): the player's Security click passes no item (the target block's entry sends the unlock with OBJECT_INVALID), so OPENLOCK rolls without a spike; a spike reaches OPENLOCK only through UseItem's property-37 branch (UseSkill), and no inventory or HUD list offers a spike (the item test wants a CastSpell or Trap property), so a player never uses one up (needs a runtime check). Given one, OPENLOCK spends it on success and on failure | 0x00683e50 (doors), 0x00682dd0 (placeables), `SendPlayerToServerInput_Unlock`, UseItem 0x004fc210, 0x00616520, actions.md 3.7 | open: ours uses up the weakest spike in the bag that makes the roll succeed | `security_spike.txt` (32 vs DC 28, Tunneler x2 to x1) |

## 2. Equipping

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| **Slot view.** Nine slot buttons; pointing at one (or the keys moving to it) lists "None", the worn item and every carried item that fits the creature's kind (droid/human) on the right, **without the rows' frames and not selectable**: the pointer passes the list by, a row is not hilighted or clicked, the keys do not enter it. The description pane, the title and OK are hidden. Only a click (or Enter) on the slot makes the list selectable | CSWGuiEquip OnSlotHilighted, SetSelectionMode (clears the list's flag 0x08 and every row's frame alpha; GetRow starts rows at alpha 0), OnRowHilighted (un-hilights a row at once while LB_DESC is hidden) | matches (rows could be clicked at once, which opened selection mode, and had frames) | `equip_flow.txt` |
| **Selection mode** (click or Enter on a slot): the slots, the portrait and the party buttons hide, the list becomes selectable with its rows' frames and the keyboard, the worn item's row is selected (nothing is when the slot is bare), the description sits where the portrait was, "Select Item to Equip", Cancel; the **numbers stay**; pointing at a row (or the keys on it) **puts that item on** (OnRowHilighted) so defense, damage and to-hit follow; Cancel / Escape puts the worn items back, a click on a row or OK keeps what is on; either goes back to the slot view with the slot's button hilighted and the party buttons back. The menu going away by another route in selection mode only leaves the mode: the previewed item stays on (needs a runtime check). Escape closes the menu only in the slot view | gui.md "Selection mode", EndSelection, OnPanelRemoved 0x006b8e10, UpdatePartyButtons | matches; open: ours puts the worn items back when the menu closes in selection mode | `equip_preview.txt`, `equip_flow.txt` |
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
| Identical items stack up to `baseitems.stacking`; a list row shows the count as a number on the item's picture (`%d`, in the `lbl_hex_6` frame, `lbl_hex_7` from 100), the name alone beside it | 5.2, 5.3, CSWGuiItemEntry::SetItem 0x006b6710 | open: ours writes "Name xN" (the hexagonal frames are not drawn, section 2) | `equip_preview.txt` (Blaster Pistol x2) |
| New items (loot taken, purchases, pick-ups, CreateItemOnObject) have a magenta frame in the inventory and are listed by the New Items filter until their description has been shown, then ordinary when the screen closes | CSWGuiInventory.OnItemHilighted / OnPanelRemoved, SetItem frame colours | matches (not saved: a load makes none new) | `new_items.txt` |
| "Acquired Item: <name>", "Lost Item: <name>", "Acquired N Credits" in the message log and the HUD's item/credits icons light for 4 s | feedback 50/51, notices 7/8 (SetPossessor, AddItem), dialog.tlk 1449, 1450, 1493, 1494 | matches (nothing was logged or lit) | `loot_click.txt` |
| Plot items are in the Quest Items filter and cannot be sold | 5.8 | matches (the stores are the screens lead's) | |
| Script gold (GiveGoldToCreature, TakeGoldFromCreature) logs "Acquired/Lost N Credits" and lights the credits icon | feedback 148/149, notice 1 | matches | |
| Item values, prices, the stores | 5.8 | not in this scope (screens lead) | |

## 4. Picking up, containers, giving

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Using a container opens the loot panel listing its items, which cannot be clicked (no row handler, the list not selectable); Get Items takes all, last to first, Cancel takes nothing; OnInvDisturbed per item | 5.7, CSWGuiContainer.ShowContainerItems 0x006b8130 | open: ours takes an item on one click (the original has no taking of a single item) | `loot_click.txt` |
| Switch To lists the party's non-plot items; one click puts one in the container (a chosen count while the alternate-action key is held) | CSWGuiContainer.ShowGiveItems 0x006b8410, input 0x24 → GIVEITEM (0x22) | matches for the click; open: ours also lists plot items and has no count | `container_give.txt` |
| PICKUPITEM walks to 1.1 m, crouches 1.5 s, acquires on the second pass | actions.md 3.8 | matches (earlier lead's action, now with the feedback) | |
| There is no drop command in the original's inventory | gui.md ("No drag and drop") | matches | |

## 5. Grenades and area effects

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| The target block's right slot lists the party's grenades (base items of ItemType 6) for a creature target, only where the area's RestrictMode is 0; a click throws one (the leader approaches to the power's range, throws, the blast runs k_sup_grenade: damage in a radius with a Reflex save for half, the visual and sound) | list builder 0x006198e0 / 0x006196a0; AIActionItemCastSpell | matches (the slot was an empty placeholder; `grenade.txt` passes in `tools/items/check.sh`); the RestrictMode gate fixed (by reading the code; no run) | `grenade.txt` (hp 15 to -11, Frag Grenade x4 to x3) |
| The middle slot lists the leader's hostile Force powers (a droid leader's own list), only where RestrictMode is 0; the combat feats are in the left slot with Attack | 0x006191f0 (0x0064af10, droids 0x00618c20); left slot 0x00619950 / 0x00619b10 | not mine (the Force owner) | |
| Throwing an item whose power is hostile (spells.2da HostileSetting) puts the thrower in combat and ends its stealth; the target hears a harmful OnSpellCastAt from k_sup_grenade. Nothing found turns a creature that is not an enemy hostile (needs a runtime check) | AIActionItemCastSpell 0x0050f170 (`ClearActivities(1)`, `SetCombatState(1, 1)`), actions.md 3.13 | open: ours enters combat only against an enemy, and an item's power ends stealth only through the combat it starts, so one used at a point keeps it (`fight.ctx` cast_spell, `enter_combat`) | |

## 6. Locks and Security (re-verified)

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A locked door or container offers Security in the target block's middle slot when the leader can use the skill and the lock wants no key (a door's left slot has Bash when it is not plot and combat is allowed); a click walks up, kneels 1.5 s, rolls Security + spike bonus + (20 out of combat, d20 in combat) against OpenLockDC, the roll goes to the combat log worded with dialog.tlk 1408 ("<name> <success or failure> Security: ... (roll ...) vs. DC <DC>"), the door opens | actions.md 3.7, rules.md 5.2, 0x00684410 (doors), client skill-roll case 0x0065b4a0 | matches for the middle slot, the walk, the roll and the opening; open: our line uses the attack-roll wording 1405 (`Player attempts Security on Door : *success* : (Take 20 + 5 = 25 vs. DC 12)`); `security2.txt` still clicks `BTN_TARGET0` (see "Known failing checks") | `security2.txt` |
| Failure: the roll is the only message; key-only locks say so; keys open; AutoRemoveKey | playthrough.md "Lock picking" | matches (earlier lead; the Endar Spire replay runs the bridge door) | replay |

## 7. Skills in play

| Skill | The original | Status |
|---|---|---|
| Security | OPENLOCK, above | matches |
| Computer Use, Repair | the computer panel shows the leader's Computer Use and Repair ranks and the party's programming spikes (`k_computer_spike`) and repair parts (`k_repair_part`), recounted with every line (0x006a8240); the replies' checks and the spike use are the terminal's scripts (GetSkillRank, TakeItem) | matches (the counters always read 0; `dlgview::sync_computer`) - `computer.txt`; the camera views (a node with CameraAngle 6 swaps in `computercamera.gui` over the 3D view, with the security camera's video effect, re/dialogue.md 9.7) and the slicing and plot XP's feedback - `computer_camera.txt`, `camcheck/computer.sh` |
| Repair on droids | repair kits (ItemType 26) heal a droid leader; the skill's rank enters the heal script | matches (script) |
| Treat Injury | the medpac script adds the rank; the HEAL action (0x38, 0x00517a60: walk up, a 2 s animation, Treat Injury + 20 or d20 against the target's first poison or disease, heal by the total, one medical item spent) is queued by UseSkill (0x004fbe40) with the item it is given: only scripts pass one (the player's own skill request carries no item, and no button sends it) | script for medpacs; the HEAL action is open (nothing in the player's UI calls it) |
| Persuade, Awareness (outside traps) | dialogue scripts roll GetSkillRank + d20 or fixed; Awareness is also the stealth contests' skill (section 8) | script |
| Awareness / Demolitions on mines | detection and the four trap actions, [traps.md](traps.md) | matches for detection, Disable and Recover (section 8); open: where the worker stops, the combat log's wording, flag and examine details |
| Stealth | the toggle, the contests, [stealth.md](stealth.md) | matches for the toggle, the contests and most of what ends it; open: the stealth pace, laying a mine, a hostile item used at a point (section 8) |
| Skill rank = ranks + effects + key ability (- 4 for a Strength or Dexterity skill while blind) + best feat tier, 0 when untrained and not usable untrained; Computer Use also adds a bonus kept on the placeable in use (+0x43c; nothing that sets it was found); the armour term of Demolitions and Stealth is always 0 | rules.md 5.1, GetSkillRank 0x005aa570 | matches (lib/rules; no placeable bonus) |

## 8. Mines and stealth

Written by two sub-agents against the same rules (every line, evidence and test is in their docs):

**Mines ([traps.md](traps.md); scenarios in `kotor/tools/traps/scripts/`, run with `tools/items/run.sh` on
`module:tar_m04aa`).** Matches, through the pointer, keys and HUD: trap triggers load (TrapType to traps.2da for
the DCs and the script, the faction rule); detection is the original's always-on detect mode (Awareness + d10 + 10,
every 0.1 s, traps within 20 m of their outline; a find by a player-controlled creature marks it for the party;
ours lets only party members search); a mine the party knows of shows its model, is picked with the mouse and Q/E
and can become the target; the target block offers Disable (left) and Recover (middle) to a leader with
Demolitions, a second click and R take the default; Disable and Recover walk up, kneel 4.5 s and roll Demolitions +
(20, or d20 in combat) against the disarm DC (Disable above 35 impossible, Recover + 10; the mine's creator, and a
party member on a mine the party laid, need no roll); a hostile mine within 1 m goes off under the party ("You
triggered a Mine!", the type's script does the damage through the rules, explosion, one-shot removal); a party
mine hurts only others; the HUD's mine slot lists trap kits and lays one (SetDC roll, kit spent). Open: the MINE
SIGHTED auto-pause (ours also wants the mine's box on the screen), where the worker stops (ours: within its radius
+ 1.25 m of the mine's centre), flag and examine (ours skips their roll on any party mine; what the client shows
for Examine), the combat log's wording of the rolls (ours 1405, the original 1408), laying a mine ends our stealth
(the original keeps it), the mine slot is never dimmed and ignores RestrictMode, a step across a trap's outline
does not set it off here, trap script routines
nothing calls, the mine slot label wraps.

**Stealth ([stealth.md](stealth.md); `sh kotor/tools/stealth/check.sh`).** Matches: TB_STEALTH and G (only with
Stealth ranks and a stealth unit worn, in an area that allows it), the solo-mode box when companions are about,
the shimmer, detection by the original's sight and hearing contests (Awareness and a d20 look or listen roll
against Stealth and a d10 + 10 hide roll, each rolled again every 20 s; ours draws the rolls from a hash), what
ends it (attack, combat, one's own powers, taking off the belt, conversations and transitions; doors and using
objects do not), the stealth XP pool and routines, save and load. Open: the stealth pace and walk animation (we
use the walk rate and the ordinary walk), laying a mine ends ours, a hostile item ability ends ours only through the combat it starts with a creature (one
used at a point keeps it), entering
stealth during a conversation is not refused, a stealth XP countdown kept while the area's pool is off, a save's
RestrictMode, the frame-buffer distortion look, the combat log's spot line, rest ending stealth (no party rest),
the straggler teleport that solo mode turns off.

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
| A category the party has nothing for has its button's text in the disabled colour and its picture hidden, and a click on it does nothing (the dimmed label alone left four white tiles that looked like buttons and did not answer a click: the report "I can't click any category" was a party with nothing upgradeable). The count covers the same items as the list (next line) | `CSWGuiUpgradeSelect::OnPanelAdded` sets the button's text colour and the picture label's visible bit (+0x44 bit 1); `OnCategory` 0x006c2b60 opens only a category with items | matches (the picture stayed); ours also disables the button, so it does not hilight under the pointer, and counts only the current party's worn items | `bench_empty.txt` |
| Items listed: the equipped upgradeable items of the player's creature, then of every available, selectable companion, in the party or not (slots 0 to 17), then the party's bag | `FillItemList`, `AddCreatureItems` 0x006c4960 | open: ours lists the worn items of the current party only (`ups::collect`), so a companion waiting aboard is left out | `bench_ranged.txt` |
| An item row is a button: **one click** takes the item to the bench, pointing at a row describes it; the Upgrade Item button takes the selected row | `FillItemList` gives each row handlers 0 (describe), 0x27 and 0x2d (`OnUpgradeItem`) | matches (a click on an unselected row only selected it) | `bench_ranged.txt` |
| Taking an item: a worn one comes off, a stack gives one unit, a loose one leaves the bag. **A dual wielder's other-hand weapon comes off too** (the left first when the right is taken) | `OnUpgradeItem` (flags +0xc30, id +0xc34) | matches (the engine slid the left weapon into the right hand and the upgraded one then pushed it into the bag) | `bench_dual.txt` |
| The lightsaber and the melee items use the three slot controls (`LBL/BTN_UPGRADE31..33`), the ranged items and the armour the four (`41..44`; the armour's two slots are the second and third) | `FUN_006c3aa0`, `FUN_006c2f80`, `CSWGuiUpgrade::OnPanelAdded` | matches (it was lightsaber and ranged on the four, melee and armour on the three, armour on the first two) | `bench_saber.txt`, `bench_armour.txt` |
| Slots by category: lightsaber power crystal, colour crystal, power crystal; ranged scope, improved energy cell, beam splitter, hair trigger; melee vibration cell, durasteel alloy, energy projector; armour reinforcement, mesh underlay. An empty slot shows its kind's own picture (`i_scope`, `i_energy`, `i_beam`, `i_hair`, `i_vcell`, `i_durasteel`, `i_imp_eng`, `i_armorrein` for both armour slots, `i_powerc`, `i_colorc`); an empty slot of a weapon or armour is dimmed (alpha 0.25) when the bench opens if the party has none of its upgrade, a lightsaber's never; a filled slot shows the upgrade's icon | `g_aUpgradeSlots` (type, picture, strref per slot), `CSWGuiUpgrade::OnPanelAdded`, `FUN_006c3aa0` | matches for weapons and armour; open: ours also dims an empty lightsaber power slot while the party has no spare power crystal | `bench_ranged.txt` |
| On opening the first slot is hilit. Pointing at a slot of a weapon or armour names its kind of upgrade (top left), says "Upgrades:", puts in the count box how many of that upgrade the party holds (the stack of the first bag item with its tag, 0 for none) and gives the item properties that upgrade adds in the big box on the left; the item's description is in the right box | `OnSlotHilighted` 0x006c3c30 (asm 0x006c3d43-0x006c3d88), `FUN_0055f510`, `FUN_006c3aa0` | matches (the item name was in the top box, the whole description on the left and the right box was empty: `LB_DESC` has no prototype row in the file, so it shared the lightsaber box's); open: ours leaves the count box empty | `bench_ranged.txt` |
| A lightsaber slot names what is in it, else "Power Crystal" / "Color Crystal" | `OnSlotHilighted` | matches | `bench_saber.txt` |
| A slot of a weapon or armour: a filled one gives its upgrade back to the party, an empty one takes the one upgrade item of its kind from the party's stock (nothing when there is none); if the item came off a wearer who then could not use it, the box 42489 asks: OK takes the upgrade, Cancel clears the bit on the upgrade item and not on the bench item, so as read the item keeps the upgrade and the party keeps its unit (an engine bug; needs a runtime check). A lightsaber crystal never asks | `OnSlotClicked`, callback `FUN_006c6120` (asm 0x006c6168), `OnUpgradeChosen` (no CanEquipItem) | matches for the slots; open for the box: ours undoes the install on Cancel and also asks for a power crystal | `bench_ranged.txt` (the box: open, no shipped upgrade needs a feat the leader lacks) |
| **A lightsaber slot always opens the list of crystals**: a power slot lists None, the crystal it has, and every power crystal the party has that is not in the other power slot; the colour slot lists the saber's colour and every other colour crystal the party has. The pictures, the names and Assemble give way to the list (the description box stays); one click chooses, pointing at a row names it (and a power crystal gives the properties it adds). None gives the crystal back | `OnSlotClicked` (lightsaber branch), `OnUpgradeChosen` 0x006c5510, `FUN_006c5370`, `FUN_006c2f80` selection mode | matches (a filled slot gave its crystal back at once, no None, an empty one needed stock) | `bench_saber.txt` |
| A new colour crystal replaces the saber at once by the `upcrystals.2da` saber of that colour and kind (short, long, double), keeping its upgrades and its stolen flag; the old colour crystal goes back to the party | `OnUpgradeChosen` | matches in effect (ours makes the new saber at Assemble, so the description box shows the old saber until then) | `bench_saber.txt` |
| Assemble keeps the changes, Cancel (and Escape) restores the item and the stock; either puts the item back in its hand if it still may wear it, else in the bag, and returns to the item list with that item selected; a bench opened by a script's item closes the whole screen | `OnAssemble` 0x006c6190, `OnCancel` 0x006c61f0, `ReturnItem` 0x006c5e90 | matches (the first row was selected again) | `bench_saber.txt`, `bench_dual.txt` |
| Armour comes off and goes back on across the bench; an upgrade's properties apply from the next equip (Armor Reinforcement: defense, Mesh Underlay: resistance and immunity) | `ReturnItem`, the upgrade rule (4.6) | matches | `bench_armour.txt` |
| The item is shown as a turning 3D model (the `upgitem_light` rig with the item's model, the rig's "rotate" animation and the panel turning the view 70 degrees a second; an item whose base item is powered plays "powered", armour "neutral") in `3D_MODEL` (lower right) or `3D_MODEL_LS` (upper left, big) | `FUN_006c3630`, `CSWGuiUpgrade::Render` 0x006c33a0 | open: the area stays empty | |

## Open items

- The bench's 3D model of the item (above).
- The bench lists only the current party's worn items, not those of every available companion; its count box stays
  empty; Cancel on the 42489 box undoes the install (the original, as read, keeps the upgrade without taking it) and
  a power crystal asks too; an empty lightsaber power slot is dimmed.

- An equip in combat as a combat-round entry; OnEquipItem (no module uses it).
- Per-minute item uses (one droid shield).
- The HEAL action (Treat Injury as an action): only scripts can queue it and none of the shipped ones was found
  to; medpacs add the rank through their own script.
- The new flag is not saved. No action timer is drawn for lock picking and the trap actions, as in the original:
  the server sends `StartActionProgress`, but the client's handler (`0x00654a30`) reads the message and drops it.
- Security spikes: the player's Security click in the original sends no spike (both unlock senders pass no item and
  no list offers one; needs a runtime check), so a player's roll gets no spike bonus; ours uses up the weakest spike
  that makes the roll succeed.
- The module's OnActivateItem: the original never fires it on its own (only the EventActivateItem routine builds the
  event, and no shipped script calls it; needs a runtime check); ours fires it on every use.
- Using an item from the inventory is instant in the original (0x004efe30: the power is cast and the use spent at the
  click, no action or animation, the queue untouched); ours queues a 1.5 s action.
- A container's rows cannot be clicked in the original (0x006b8130: take all only); ours takes one item per click.
- A charged item that reaches 0 charges is destroyed in the original; ours keeps it.
- Skill rolls in the combat log: ours words them with 1405, the original formats its combat message 9 with 1408
  (the trap actions, [traps.md](traps.md) 4; the Security roll goes through the same message, `AIActionOpenLock`
  0x0057d9d0).
- Mines, stealth: see their docs.
- The equipment list leaves out unwearable rows only when the "Hide Unequippable" option is on; ours reads the option but does not use it. The hexagonal frames (`lbl_hex_3/6/7`) around the rows' pictures are not drawn.

## Known failing checks (`check.sh`, left as they are)

`sh kotor/tools/items/check.sh` reports **6 failures** in 4 scenarios, the same with the executable from before the
equipment-screen work and with fresh checkpoints, so they are not regressions of the screens. All 6 are checks that
went stale; the behaviour they test was seen working by hand.

| Scenario | Failed patterns | Why |
|---|---|---|
| `security` | `*success* : (Take 20 + 5 = 25 vs. DC 12)` | The script clicks `BTN_TARGET0`, but a locked door's target block now has the Security lock in the second slot (`BTN_TARGET1`) and the first holds only Bash, which a plot door such as `end_door01` does not offer, so the click does nothing and the leader never walks up. Clicking `BTN_TARGET1` logs "Player attempts Security on Door : *success* : (Take 20 + 5 = 25 vs. DC 12)" (our 1405 wording; the original words the roll with 1408). |
| `security_sp` | `*success* : (Take 20 + 12 = 32 vs. DC 28)`, `Security Spike Tunneler x1` | The same click on `BTN_TARGET0`: no roll, so no spike is used up. The spike pattern checks our choice: the original's Security click uses no spike. |
| `consumables` | `fx : 7 effects` | `ui fx` prints the creature's id now (`fx 2147483647 : 7 effects`), so the pattern without it matches nothing. The effects are there. |
| `props` | `fx : 3 effects`, `fx : 0 effects` | The same id in the `ui fx` line. |

Fixing them is changing `BTN_TARGET0` to `BTN_TARGET1` in `security2.txt` and `security_spike.txt` and the patterns to `fx [0-9]* : N effects`.
