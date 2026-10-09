# The game screens: store, loot, level-up, upgrade bench, galaxy map

The modal panels a script or the world opens over a running module that are not the HUD's menus
([hud.md](hud.md)): the merchant's, a container's, the level-up panels, the upgrade bench and the
galaxy map. They are `.gui` files on the in-game interface's one `gui::Gui`; the engine owns the
data and the rules, a screen is the code that fills the panel from them and turns its events into
engine calls. What the original does is in [re/gui.md](../re/gui.md) (10.2, 10.4),
[re/party-items-saves.md](../re/party-items-saves.md) (5.5 to 5.11, 3.1) and
[re/rules.md](../re/rules.md) (4.3, 4.4, 6).

| Where | Namespace | What |
|---|---|---|
| `lib/screens/screens.ctx` | `screens` | `State` (one field per screen), `take` (outbox note to request), `update` (events, the next request, the world's pause), `draw_views` / `draw_over` (the 3D views under and over the panels) |
| `lib/screens/msgbox.ctx` | `msgbox` | the OK and OK/Cancel boxes (`confirm.gui`) a screen puts over itself, `answer` of an event |
| `lib/screens/store_panel.ctx` | `store_panel` | `store.gui` |
| `lib/screens/container_panel.ctx` | `container_panel` | `container.gui` |
| `lib/screens/lvl_*.ctx` | `lvl` | level-up: `lvl_main` (the panels, steps, numbers, apply), `lvl_abilities`, `lvl_skills`, `lvl_feats`, `lvl_powers`, `lvl_view` (the creature on maincg) |
| `lib/screens/ups_*.ctx` | `ups` | the bench: `ups_data` (categories, slots, the two 2DAs), `ups_bench` (the three panels), `ups_events` (slots, Assemble, Cancel) |
| `lib/screens/gal_*.ctx` | `galaxy`, `galview` | the galaxy map and its two `gui3d` views |
| `lib/screens/test_screens.ctx` | `test_screens` | the headless `ui` commands (below) |
| `lib/engine/store.ctx`, `container.ctx`, `xfer.ctx`, `levelup.ctx`, `templates_store.ctx`, `routines/galaxy.ctx` | `store`, `container`, `xfer`, `levelup`, `tmpl`, `rt_galaxy` | the world's side: stock and prices, open and close, item copies and moves, applying a level, the planet routines |
| `tools/twodacat` | | any 2DA (or `--str N` dialog.tlk strings) as text |

A program that links `lib/ingame` adds `lib/screens` (`kotor/build.ctx` does). `lib/screens` needs
`lib/ingame` (it calls `items::add_row`, `items::describe`), `lib/hud`, `lib/chargen` (its helpers
and the `preview3d` creature view), `lib/frontend` (`gui3d`, settings) and the engine.

## The seam

Scripts and the engine never call a panel: they put a note in the outbox (`w.out`), the interface
takes it and opens the screen.

| Note | Posted by | Screen |
|---|---|---|
| `open_store{ store, customer, markup, markdown }` | `OpenStore` | merchant |
| `open_container{ placeable, user }` | `container::open`, from USEOBJECT on a container (`doors::use_object`) | loot |
| `level_up{ who }` | `ShowLevelUpGUI`, the character sheet's Level Up | level-up |
| `upgrade_screen{ item }` | `ShowUpgradeScreen` | bench |
| `galaxy_map{ planet }` | `ShowGalaxyMap` | galaxy map |

`ingame::take` passes every note to `screens::take`, which records a request (opening needs the
device, which a note does not carry). `ingame::update` closes an open menu when a request waits, then
calls `screens::update` with the frame's GUI events: each open screen's `on_event` takes the ones for
its panels, and when nothing is open the next request opens. While a screen is up `PAUSE_MENU` holds
the clock. `ingame::draw` draws the backdrop, `screens::draw_views` (the galaxy map's 3D galaxy and
planet, which the panel must not cover: the panel's own fill is switched off), the panels, then
`screens::draw_over` (the level-up creature, which sits in a hole of maincg and is hidden by the full
screen step panels, so it is drawn after and only while none is up).

A screen is a `State` with `open` and a panel id, `begin`, `on_event -> bool`, a close, and, for the
ones with 3D, `update` / `draw`. Events are the GUI's poll-style ones ([gui.md](gui.md)); a message box
a screen opens is a modal on top, whose events the screen answers first (`msgbox::answer`).

## Merchant (`store.gui`)

`tmpl::read_store` reads a UTM (and a saved store): `MarkUp`, `MarkDown`, `BuySellFlag`, and the
`ItemList` of blueprints or whole items (the `Infinite` mark on the element), inserted in ascending value,
the order `CSWSStore::LoadStore` leaves them in. Identical entries stack as `AddItem` stacks them
(`xfer::absorb`: the same template and `CompareItem`, up to the base item's `Stacking`): Dantooine's
general store lists Antidote Kit five times, one infinite, and shows one row. An infinite entry
swallows its finite twins and stays a single unit (its amount reads "Infinite", never a count: ours,
the data does not say what the original does); creatures' and containers' item lists and the party
inventory a joining member's items go into stack the same way. `obj::Store.stock` is a list of item ids; an item's
`infinite` field is its stock mark. The save writes a store whole (`save::write_merchant`).

Prices (re/party-items-saves.md 5.8), integer arithmetic, no skill enters:

- value of an item (`store::value_of`): 0 for a plot item, else `max(1, trunc(AddCost x multiplier of its
  base item))`, the multiplier being `ChangeItemCost`'s (`w.party.cost_mult`); per unit;
- `store::buy_price` = value x (MarkUp + bonus mark-up) / 100, `store::sell_price` = value x (MarkDown +
  bonus mark-down) / 100; the bonuses are `OpenStore`'s, kept by `store::open`.

The panel: `LB_SHOPITEMS` (the stock) and `LB_INVITEMS` (the party's bag, `w.bag`) share a rectangle, one
shown; rows are grouped by `baseitems.2da` `StorePanelSort` and in list order inside a group, plot items
never listed; selecting a row shows its description, its price for the page (`LBL_COST_VALUE`) and its
stock (`LBL_STOCK_VALUE`: the stack, or "Infinite" 41951). `BuySellFlag` bit 0 gives the buy page, bit 1
the sell page, both a toggle button ("Show Sell List" 41938 / "Show Buy List" 41937); the panel starts
on buy. Buy or a second click: not enough credits shows 41950; a price over 50 x the player's level asks
42020 (its `<CUSTOM0>` filled); then `store::buy` takes the price from the purse and gives one unit: an
infinite item is copied (`xfer::copy_item`), a stack is split by one, a single leaves the stock; the unit
joins the party's inventory through `xfer::to_party`. Sell: over min(50 x level, 250) asks 41985; then
`store::sell` pays and the unit joins an item of the stock that stacks with it (`rules::compare_items`;
an infinite one swallows it, a finite one grows by one whatever the stack limit) or is inserted by value.
The credits label follows the purse each frame. Sounds: 9 on a purchase, 11 on a sale.

## Containers (`container.gui`)

`container::open` (USEOBJECT on a placeable with an inventory that is not locked, by a party member)
marks it in use, plays the open animation (10075), posts OnOpen and the note; the original's wait for
the animation before the panel is not kept. The panel is a centred dialog: the container's name and its
rows (a row takes that item on a second click or Enter), Get Items (`BTN_OK`: take all, last to first, and
close), Switch To (`BTN_GIVEITEMS`: the party's bag to put items in; Get Items greys), Close. Each take
posts OnInvDisturbed with the type (1 removed, 0 added) and the item (`GetInventoryDisturbType` and
`Item` answer); a body bag that dies when empty is silent and destroys itself when emptied
(`die_when_empty`). Credits in a container become gold, pazaak cards are counted, stacks merge
(`xfer::to_party`, over `rt_misc::move_item`). `tmpl::read_container` reads a UTP's or a saved
placeable's `ItemList`. Verified on the Endar Spire's footlocker: two takes run `k_pend_chest02` twice.

## Level-up (`maincg`, `leveluppnl`, `abchrgen`, `skchrgen`, `ftchrgen`, `pwrlvlup`)

The panels are character generation's files; the logic is not chargen's (that builds a creature from
nothing, this works on a living one through `rules::level_up_options` and `rules::apply_level_up`);
chargen's pure helpers (`set_number`, `ability_tag`, the tag tables) are shared.

- Who and which class: the creature's last class slot (`AddMultiClass` leaves a slot at level 0 for the
  Jedi class; AutoLevelUp uses the same rule). `levelup::can_level` is `rules::can_level_up`.
- `maincg` full screen with `leveluppnl` framed over it; the title is "Level Up" (1071); name, class,
  portrait, new level, the six scores, and the old and new vitality, defense and saves (`OLD_*`/`NEW_*`
  with their arrows) from a trial application of the record on a copy of the rules creature, refreshed
  after every step. The creature stands on `MODEL_LBL` (chargen's `preview3d` main preview), made by
  `lvl_view` as the character sheet makes it (below).
- `lvl_view` (`lvl::make_view`, `add_view`) is also the in-game character sheet's 3D character
  (`character_panel`, over `LBL_3DCHAR`): the creature as dressed, the way lib/scene/visual.ctx picks
  the body (the armour's body letter and texture variation, `a` without armour; F and S/L types their
  single model), its head, no weapons; below alignment 31 an unarmoured body wears `texaevil` + `01`, and
  below 41 the head the dark side's `headtex*e` of its stage (re/gui.md, "CSWGuiCharacter"); the light
  model plays the alignment's animation and the creature its pose; tags `t3m4` / `hk47` / `zaalbar` take
  `camerahookt` / `h` / `z`, the two droids loop `pause1`. A pose the model lacks loops `pause1`. The sheet
  draws the view with `gui::set_overlay_after` so the controls after `LBL_3DCHAR` in the file (alignment
  bar, level-up buttons) cover it, as the original's do, and turns it 10 degrees per 0.1 s while
  `BTN_3DCHAR` holds the left or right mouse button: the left turns the character to its own right (clockwise
  seen from above, the face toward the screen's left) as the original's -10 degrees do, the right the other way
  (`kotor/tools/ingame/scripts/sheet_turn.txt` from the `uppercity` checkpoint). Not under a modal panel (the AI style panel): the
  model is hidden while one is up.
- The steps list: Attributes (only on a level whose class level is a multiple of 4), Skills, Feats (when
  featgain gives any), Powers (Force classes), Accept. A step opens when it is needed, not done, and every
  needed step before it is done; Accept applies when all are. Back asks 48541 once something was chosen.
- Attributes: one point, cost 1, no ceiling, floor the opening score; Recommended is the class's
  primary ability (`classes.2da`); Accept without spending asks 48217.
- Skills: the level's points (`opts.skill_points`), cost 1 for class skills and 2 otherwise, the cap
  `skill_max_rank`; a skill the creature may not use is greyed; the messages 42178 / 42179 (with
  `<CUSTOM0>`) and 42464; Recommended is the auto-leveller's spend (`prepare_auto_level` on a copy);
  Accept with points left asks 41815.
- Feats: chargen's rows of icon cells (`chargen::build_feat_chains`, `fill_chain_cells`): the chains by
  `prereqfeat1`/`prereqfeat2` the class lists or the creature knows; selectable if the pass's pool takes
  the feat and the prerequisites hold (`meets_feat_requirements` with the pass's picks as pending), picked
  through `can_select_feat` with that pool only; 42182, 42183, 42184, 42530, 48215. A level with bonus
  feats opens a second ftchrgen after Accept, the bonus pass (sub title 1316), on a copy of the creature
  that has the regular picks; the record takes both passes' picks. Back in the bonus pass leaves the
  regular picks on the character, as the original's (they were added at the regular Accept): the step is
  not taken, the regular pass opens again with them known and a fresh count, and the level applies them
  with the rest (ours applies nothing before the level is accepted). (The game's `featgain.2da` gives no
  bonus feats, so this only runs with modded data; checked with `bonus_feats` forced to 1.)
- Recommended in the feats and powers steps also opens the original's list popup (`skillinfo`: caption
  42256 or 42257, a row per pick with its icon and name, OK / Enter / Escape close it with GUI sound 0),
  even when it lists nothing (`kotor/tools/ingame/scripts/levelup_jedi.txt`).
- Powers: rows of icon cells (`chargen::build_power_chains`, every Force power, rows by force-AI kind and
  line, cells by priority); known green at half, picks green, the selectable set (CanLearnForcePower with
  the count + 1) faint, the rest faint on a faint backing; Affect Mind and Dominate Mind locked for
  anyone but the PC (42470); 42185, 42186, 42529, 48210; "Add Power" / "Remove Power";
  `classpowergain.2da` says how many.
- The cell lists take the arrow keys whichever control has the focus, as the original's panels do, and
  then pass them on to the focused control once the new cell is shown: with the pointer over the
  description it scrolls the new text a line in the same frame (`levelup_desc.txt`), a focused button
  follows its MOVETO. Enter picks or drops the focused cell's feat in the feats steps and accepts the
  powers step, whichever control has the focus, then reaches the focused control (`gui::EventKind::
  cell_enter`; `levelup_enter.txt`).
- Accept: `levelup::apply` (the rules' record, maxima follow, full heal, OnPlayerLevelUp posted to the
  module for the player). The character sheet's Level Up posts the `level_up` note; Auto calls
  `levelup::auto_level`. The option "Auto Level Up NPCs" (`rules::Settings.auto_level`, read from the
  settings file and kept current by the options menu) makes `levelup::after_xp` level every companion
  in the party when XP is given; it is named for the NPCs, so the player is not included.

## Upgrade bench (`upgradesel`, `upgradeitems`, `upgrade`)

K1 has no lab station: the data has no panel for one (a K2 feature).

- `upgrade.2da` rows are the upgrade items (template, type: 0 lightsaber power crystals, 1 to 3 melee, 4 to 7
  ranged, 8 and 9 armour); an upgradeable weapon or armour blueprint carries every property any upgrade
  could give, each tagged with its row, and `Upgrades` bit n installs row n (rules: `prop_active`). The
  category of an item is the type of its first tagged property's row.
- `upgradesel`: the four categories, enabled by what the party's members wear and the bag holds;
  clicking one (or Upgrade Items on the hilighted one) opens `upgradeitems`: those items, the worn marked.
  `ShowUpgradeScreen(item)` goes straight to the bench.
- Picking an item takes it out of play: a worn one comes off, a stack gives one unit. `upgrade` shows its
  slots: a lightsaber has two power-crystal slots and the colour crystal, a ranged weapon four typed
  slots, a melee weapon three, armour two. An installed upgrade shows its item's icon; an empty typed
  slot the one that would fit, dimmed when the party has none; an empty power slot the generic icon.
  Clicking an installed slot removes it, an empty typed slot installs the upgrade from the bag, a power
  or colour slot opens a list (`LB_ITEMS`) of the crystals the party has (colour: others than the
  current one).
- The session is a **ledger**: the item's bits and two sets of rows (to take from the party, to give back)
  change on the bench and nothing else does. Assemble makes it true (`consume_one`, `create_item`; a new
  colour crystal replaces the saber with the upcrystals row's saber of the same kind, keeping the upgrade
  bits and the stolen flag) and puts the item back where it came from (`equip::equip_item`, else the bag);
  Cancel restores the item as it was. An install that stops the wearer using the item asks 42489 and
  undoes itself on Cancel.

## Galaxy map (`galaxymap`)

`SetPlanetAvailable` / `SetPlanetSelectable` set bits in `w.party.planet_mask` (bits 0 to 15 and 16 to 31,
as PARTYTABLE's `GlxyMapPlntMsk`, saved and loaded), `GetSelectedPlanet` answers `planet_selected`.
`ShowGalaxyMap(n)` selects n and opens the panel: the buttons of `planetary.2da`'s `guitag` column show
for available planets and can be clicked for selectable ones (the five Xbox Live planets never show: no
art), the selected one's name and description are `LBL_PLANETNAME` and `LBL_DESC`, its model (`model`
column) zooms in (`zoomin`) and turns (`rotate`) in `3D_PlanetModel`, and `3D_PlanetDisplay` is the
`galaxy` model (a particle spiral, camera on `camerahook`). Travel posts `k_sup_galaxymap` to the module
(`Payload::run_script`), which reads `GetSelectedPlanet` and does the travel (it calls `StartNewModule`).

## Headless testing

`ui` commands (scripts in `kotor/tools/ingame/scripts/`, run with `kotor.exe --module M --headless
--frames N --input FILE --screenshot-at F:PATH`): `gold N`, `store RESREF [UP DOWN]` (spawns a merchant and
prints its stock with prices), `loot TAG`, `containers`, `bag`, `stockdrop TAG N`, `storecount TAG`,
`xp N`, `levelup`, `autolevel`, `addclass N`, `sheet`, `levels`, `autoopt 0|1`, `bench [TAG]`,
`upcheck NAMES...`, `planets N...`, `galaxy [N]`. Scripts: `store.txt`, `store_ask.txt`, `store_save.txt`,
`loot.txt` (Dantooine), `loot_endar.txt`, `levelup.txt`, `levelup4.txt` (the ability point),
`levelup_jedi.txt` (powers), `levelup_auto.txt`, `bench.txt`, `bench_melee.txt`, `bench_worn.txt`,
`galaxy.txt`. Checked by looking at the pictures and the prints: prices equal AddCost x markup
(Medpac 40 at MarkUp 100, sold for 10 at MarkDown 25), a purchase and a sale move the credits and the
stock, the 50 x level question appears at a bonus mark-up of 100, a store's stock survives a save and a
load (52 of 55 after dropping three), a soldier takes level 2 (hit points 22 to 34 and a full heal, saves 5/2/1,
one rank) and level 4 (the point), a Jedi Guardian level takes its powers (46 Force points), Carth levels
with the option on and not with it off, the bench consumes and returns crystals and re-equips a worn
sword, and the galaxy map's Travel runs the script with the right planet.

## Decisions (ours)

- Requests, not direct calls: a note is recorded and opened on the next `screens::update`, one screen at
  a time (the next waits).
- A row that takes an item (container) or starts a deal (store) needs the second click or Enter, as every
  list in lib/gui does; the original's rows act on one click.
- The auto-level option applies to companions only.
- The bench is a ledger so that Cancel is exact; the original moves items as it goes and undoes them.
- An upgrade slot's empty icon is its item's own picture (dimmed), which is what the original's code does
  with the party's stock; the original dims by alpha 0.25 on the control, here the control's border tint.
- The sheet's 3D character is made each time the sheet opens or shows another character, from what it
  wears then; the original rebuilds its model only when the creature or its alignment changed, so an
  outfit changed since the last look keeps the old one. A creature whose appearance makes no view gets
  its portrait on `LBL_3DCHAR` (the original shows nothing).

## Not done

- Item property lines are ours from the data, not traced in the binary (`GetDescription` 0x0055f340 is
  not read; see "Item descriptions" in hud.md).
- The bench's 3D models (`3D_MODEL`, `3D_MODEL_LS`) and the model of an item in the store.
- Arrow keys on the galaxy map (previous and next planet), the tutorial pop-ups these screens raise.
- Dying companions' levels and NPCs outside the area: `levelup::after_xp` only reaches the party in the area.
- The level-up creature is not dressed in its armour; non-body appearances (droids, the large ones) show nothing.
