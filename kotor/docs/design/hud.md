# The in-game interface: HUD and menus

What the player sees over a running module: the heads-up display (`mipc2*.gui`), the eight menus
behind the tab bar (equipment, inventory, character, abilities, messages, journal, map, options)
and the panels that belong to them. The GUI toolkit is [gui.md](gui.md) (`lib/gui`); what the
original does is in [re/gui.md](../re/gui.md) (sections 10.3 and 10.4), [re/movement.md](../re/movement.md)
(section 7, targeting) and [re/party-items-saves.md](../re/party-items-saves.md); the world it reads is
[engine.md](engine.md).

| Directory | Namespace | What |
|---|---|---|
| `lib/hud/` | `hud` | the HUD panel and everything it shows: `hud.ctx` (opening, fitting to the window, party widgets), `minimap.ctx`, `target.ctx` + `block.ctx` (picking, default actions, the floating target block, the reticle), `view.ctx` (world to screen), `log.ctx` (the message log), `state.ctx` (**every question the interface asks of the game**) |
| `lib/ingame/` | `ingame` | the session: `ingame.ctx` (one `gui::Gui`, events, update, draw, pause), `menus.ctx` (opening and closing menus, the tab bar, shared buttons), `script.ctx` (headless `ui` input lines), and one `*_panel.ctx` per menu |
| `tools/ingame/` | | `go.sh` (build, run headless over a script, screenshots) and `scripts/` |

## The seam with the game loop

`game/play.ctx` calls `ingame` at six marked points (`HOOK(ingame)`). `ingame::make` once the module
is entered; per frame `begin_frame` (clears last frame's GUI events), `handle_event` for each SDL
event (true: the interface used it, so the game does not also treat it as a key or a world click),
`take` for each outbox note (feedback text), `update` after the scene is synced (the camera is
needed for picking), `draw` before submit. The interface owns **one `gui::Gui`**, `ui.gui`; other
systems that show panels in game (dialogue) open theirs on it and read `gui::take_events{ &ui.gui }`
(events are cleared at the next `begin_frame`, not by `update`).

The interface reads the world through `lib/hud/state.ctx` and writes it in three places only:
`w.target` and `w.hover` (picking), `clock::set_pause` (menus set `PAUSE_MENU`, the pause key
`PAUSE_PLAYER`), and the leader's action queue (`actions::add`) when a target action is chosen.
Everything else it shows is read, so a missing system is a stand-in in `state.ctx`, marked
`PLACEHOLDER`, not a hole in a panel.

## The HUD

`hud::open` loads the HUD file for the GUI's pixel space (`gui::hud_name`: 800x600 for every size
under 1024x768) and **fits it to the window**: the original shows the file made for the exact
window size and, on a size it has no file for (any 16:9 window), no HUD. Here each control keeps its
pixel size and is anchored to the nearest screen edge by where it sat in the file (left, centre
or right third; top, middle or bottom third), so the minimap stays top left, the menu buttons top
right, the portraits bottom left, the action slots bottom right and the combat bar and message
centred. Controls the game decides to show (combat bar, notifications, action slots) start hidden.

- **Party** (`update_party`): member 0 is the leader (big portrait); with two members the companion
  goes to widget 3, next to the leader. The portrait is `portraits.2da`'s `baseresref`, the
  vitality bar is green, the Force bar blue; clicking the leader's portrait opens equipment, a
  companion's makes it the leader (as Tab does).
- **Minimap** (`minimap.ctx`): the area's `lbl_map<area>` picture placed from the ARE's `Map`
  (two world points and where they fall in the map, 0..1 of its 440 x 256 texels: the art fills
  the left 440 columns of the 512 x 256 texture and the rest is padding, and the original's
  conversion rejects points past 0x1b8 x 0x100; `NorthAxis` for which world axis runs
  along the picture's; checked against every ARE: axis 0 is (x, -y), 1 (-x, y), 2 (-y, -x),
  3 (y, x) with each picture axis linear in one of them), the leader at the centre of a viewport
  drawn into a render target each frame, an arrow turned by its facing. The target is the picture
  of `LBL_MAPVIEW`, so the HUD's frame goes over it.
- **Targets** (`target.ctx`, `block.ctx`): every frame the pointer's pick is the nearest selectable
  creature, door or placeable whose projected box holds it (`w.hover`, and the pointer's picture
  from the default action); a click targets (`w.target`), a click on the target does its default
  action; Q and E cycle. The block with name, health and three action slots floats over the target;
  the reticle is drawn under the panels. Models carry no usable bounds (the compiler's default
  box), so the boxes are ours: creature height scaled by `PERSPACE`, typical door and placeable
  sizes. Slot 1 holds the default actions (open/bash, use, talk, attack); the Force-power and item
  slots are empty until lib/rules gives the leader any (PLACEHOLDER).
- **Combat** (`combat.ctx`): while the leader's `in_combat` flag is set the combat bar (queue
  icons from the leader's attack actions, Disengage, clear-one) and for six seconds the combat-mode
  message show; Disengage clears the actions and the flag. There is no combat system to set the
  flag yet, so `ui combat TAG` sets it for tests.
- **Feedback** (`feedback.ctx`, `log.ctx`): outbox `feedback` notes go to a 64-line ring
  (`hud::MessageLog`, also read by the Messages menu); the young ones draw as blue lines under the
  minimap's notification icons and fade after six seconds.
- **Notification icons** (`notify.ctx`): `ingame::notify{ ui, hud::NOTE_* }` lights the journal,
  credits, experience, alignment and item icons for four seconds. No engine routine calls it yet
  (the outbox has no note for them).
- **Tooltips**: menu buttons carry their name and key (`Messages : J`), the toggles theirs, a party
  button its name, vitality, Force and level.
- **Pause**: Space or `TB_PAUSE` toggles `PAUSE_PLAYER` and shows `pause.gui`.
- **Level-up and downed marks** on the party widgets, from `exptable.2da` and the hit points.
- **Window resizes** reopen the HUD fitted to the new size (`ingame::resize` also calls
  `gpu::resize`: nothing else in the loop handles `resized`).
- **Self action slots** (`lib/ingame/selfslots.ctx`, re/gui.md "Action menus"): the four buttons at
  the bottom right hold the leader's friendly Force powers, medical items, other usable items and
  mines; the arrows cycle, a click casts on the leader in place of its queued actions (the cast
  action spends the item's use as it begins, `rt_item::spend_use`), an entry that cannot be used
  shows dimmed and says why in the message bar for five seconds (Force Depleted, Restricted by
  Armor, Full Health, PC Dead), and the hovered slot's entry is named above the slots. Which
  entries make up each list is ours (the original's list builder was not read): see the header of
  the file. Mines are not listed (no trap action in the engine) and the keys (keymap.2da) are not
  bound. `ui useitem RESREF [N]` is the headless test; `scripts/selfslots.txt` the run.
- **Not built**: the leader-swap animation, effect-count icons, stealth toggle and bark bubbles
  (the dialogue lead's).

## Menus

`ingame::open_menu` puts the menu's file on the GUI as a full-screen, **non-modal** panel (non-modal
so the tab bar over it, which is opened after it, takes clicks; a modal panel would take all
input), adds `top.gui` centred at the top, plays the open sound and sets `PAUSE_MENU`. Keys are the
original's keymap.2da defaults: U equipment, I inventory, P character, K abilities, J messages,
L journal, M map, O options; Q and E step through the menus; Escape closes the open menu or opens
the options. They are handled before the GUI sees the key (a full-screen panel takes every key).

### A panel module

Each menu has `lib/ingame/<name>_panel.ctx` with namespace `<name>_panel` and these functions,
called by the framework (`menus.ctx`):

```
struct State { ... }                                     // its state, a field of ingame::Menus
fn new {} -> State
fn open { mut s: State, mut g: gui::Gui, mut w: world::World, mut dev: gpu::Device, panel: u32 } -> !
fn update { s, g, w, dev, panel, dt: f32 }               // every frame while shown
fn on_event { s, g, w, dev, panel, ev: gui::Event } -> bool
fn close { s, g, w, panel }                              // no dev
```

`open` fills the controls from the game (by tag) and is called again when the leader changes, so
it must be repeatable. The framework handles `BTN_EXIT` and Escape (close), `BTN_CHANGE1/2` (the
party members' portraits: pressing one makes that member the leader and calls `open` again), and
the tab bar. A panel handles the rest in `on_event`: `activate` for buttons, `row_selected` /
`row_activated` for list boxes, `value_changed` for check boxes. Menu panels use the leader as
"the character". `messages_panel` also gets `log: *hud::MessageLog`.

### The panels

| Menu | Files | Reads / does | Stand-ins (grep `PLACEHOLDER`) |
|---|---|---|---|
| Equipment | `equip_panel`, `items_*` | slots, candidate lists, descriptions, defence/damage/to-hit; equip and unequip apply on OK, refusals open the original's message boxes | no EQUIPITEM/UNEQUIPITEM action handlers (applied to the creature directly); item-property text; proficiency checks; base attack bonus is the level |
| Inventory | `inventory_panel`, `items_*` | worn items first, then the bag by base item and name; six filters kept between openings; Use Item | the party's shared inventory and purse (the leader's own bag stands in); using an item only posts its activate event |
| Character | `character_panel`, `sheet_*` | name, classes, vitality, Force, defence, attributes with modifiers, saves, alignment bar, XP and next level; Level Up / Auto show when the XP allows | all numbers come from `sheet::read` / `known_of` / `skill_total` (d20 formulas over the creature's data) until lib/rules is wired into the creature; the Level Up and Auto buttons open the level-up panels ([screens.md](screens.md)); the script-select panel and the 3D model are not built |
| Abilities | `abilities_panel`, `sheet_*` | skills, feats and Force powers from the creature's blueprint with icons and descriptions | as above |
| Messages | `messages_panel` | the dialogue and feedback logs (`hud::MessageLog`), switched with BTN_SHOW | dialogue lines are added by whoever speaks them (`hud::log_add` with `LOG_DIALOG`) |
| Journal | `journal_panel`, `journal_*` | `global.jrl` quests with their text from dialog.tlk, active and completed lists, four sorts, quest items; see [re/journal.md](../re/journal.md) | the engine keeps no journal: `journal::Journal` lives in the panel (move it to `World`, `AddJournalQuestEntry` calls `journal::set_state`) |
| Map | `map_panel` | the area picture fitted into LBL_Map in a render target (`map_panel::draw`, called by `ingame::draw`), party arrows, the area's waypoint notes stepped with the arrows, the Party Selection rules (area, together, no enemies) | the Return button (no flag in the party table); "enemy near" is a distance test |
| Party selection | `partysel_panel` | a modal over the map: the available companions, pick two, put back, Done | spawning a companion beside the leader |
| Options | `options_panel` | the front end's Gameplay, Feedback, Auto-Pause, Graphics and Sound screens over the menu (a `frontend::Front` kept in the panel, the same settings file), sound sliders to the mixer, Exit Game asks and ends the loop via `ingame::wants_quit` | Load and Save show "unavailable"; display changes are not applied (`options_panel::take_display_change` is not read by the loop) |

### Item descriptions

`items::describe` (`items_data.ctx`) builds the text every list box of an item shows (inventory,
equipment, store, container, bench): the blueprint's identified description (else the plain one), then
`items_props.ctx`'s property lines, then the base item's own numbers (`Damage: 2d6`, `Armor bonus: +4`;
these two are ours). A property line is `Name: Subtype Cost (Parameter: Value)` for each active
property of the item's rules record (the upgrade rule: native, or its upgrade installed, so the bench
shows the result), every part from the data in the way docs/formats/2da-catalog.md describes:
`itempropdef.name` is the name, its `subtyperesref` names the 2DA the subtype indexes, the UTI's
`CostTable` row of `iprp_costtable` names the cost 2DA, `Param1` a row of `iprp_paramtable` the
parameter's name and 2DA; each row's text is its `name` strref, else its `label`. Two of ours, for
reading: the melee cost table's plain numbers show as `+1` (it serves the attack, damage, defense
and enhancement bonuses), and the charge table's text goes in brackets (`Activate Item: Medpac I
(Single Use)`). The original's own wording was not traced (no Ghidra project was at hand), so the
format follows the shipped descriptions, which embed lines of the same shape (`Attribute Bonus:
Strength +4`). Checked over every base-game UTI (`ui describe`, 557 blueprints) and in the store.

The panels were written by four agents against the protocol above; each has headless scripts in
`tools/ingame/scripts/` with the `go.sh` line in its header and test commands in `test_*.ctx`
(`ui giveitem`, `ui stock`, `ui journal add`, `ui note`, `ui leader`, ...).

### Reading the game

`hud::` functions in `state.ctx` are the only way panels read the game: `party_ids`, `name_of`,
`vitality_of`, `force_of`, `level_of`, `portrait_of`, `is_down`, `creature_of`. A panel that needs
more adds its reader to its own file and, if the data is a stand-in, says so in a `PLACEHOLDER`
comment so the rules lead's merge finds it.

## Decisions (ours)

- The HUD file is chosen by the GUI's pixel space and **anchored** on windows it was not made for;
  the original shows nothing on sizes it has no file for (a bug, not a feature).
- Menus are **non-modal** full-screen panels so the tab bar over them takes clicks; a modal panel
  (message box, party selection, option screens) opened by a menu takes input and Escape itself.
- Models carry no usable bounds, so picking boxes and the reticle are built from `PERSPACE` and
  typical sizes; picks are by projected box, not triangles.
- The leader is "the character" of every menu; BTN_CHANGE1/2 and Tab change the leader (`w.pc`
  follows), and a dead member cannot become leader.
- Space pauses (keymap.2da action 241); Escape closes a menu or opens the options; the engine
  loop no longer quits on Escape.
- The conversation system hides the HUD and closes any menu (`w.conversation.active`); the world
  is not picked then.
- The Force bar, level and several panel numbers read stand-ins until lib/rules is attached to the
  creature; the stand-ins are in `hud/state.ctx`, `sheet_data.ctx` and `items_data.ctx`.

## Open

- Self action slots: the mines slot and the keys; the leader-swap
  animation, effect-count icons, the stealth toggle, bark bubbles (dialogue lead's).
- Item drag-and-drop; variable-height list rows (the journal splits long texts into rows);
  a scrolling description box.
- The journal in `World`; the party's shared inventory and purse; equip actions in the engine.
- Applying display options from the in-game options (needs the window handle and fullscreen).
- Per-creature heights from the models' head nodes instead of the `PERSPACE` heuristic.

## Headless testing

`kotor/tools/ingame/go.sh` builds the game and runs it headless over an input script
(`FRAME command ...`), writing screenshots; the `ui` lines (lib/ingame/script.ctx) move the
pointer, click, press keys, open menus and select targets:

```
sh kotor/tools/ingame/go.sh kotor/tools/ingame/scripts/menus.txt 32 7:equip 10:inventory
```

The Endar Spire (`end_m01aa`) opens with a cutscene conversation (about 25 s of world time) that
hides the HUD, as the original does; the scripts that need it visible without waiting use
`MODULE=tar_m02aa` (`scripts/showcase.txt`, `notify.txt`), or open menus with `ui menu` (menus work
whatever the module does, except during a conversation, which closes them).
