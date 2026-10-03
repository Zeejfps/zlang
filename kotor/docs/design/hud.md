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
  (two world points and where they fall in the picture, `NorthAxis` for which world axis runs
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
- **Not built**: the four self action slots (Force powers, medical items, other items, mines) stay
  hidden until lib/rules gives the leader powers and items an activation; the leader-swap
  animation, effect-count icons, stealth toggle and bark bubbles (the dialogue lead's).

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

### Reading the game

`hud::` functions in `state.ctx` are the only way panels read the game: `party_ids`, `name_of`,
`vitality_of`, `force_of`, `level_of`, `portrait_of`, `is_down`, `creature_of`. A panel that needs
more adds its reader to its own file and, if the data is a stand-in, says so in a `PLACEHOLDER`
comment so the rules lead's merge finds it.

## Headless testing

`kotor/tools/ingame/go.sh` builds the game and runs it headless over an input script
(`FRAME command ...`), writing screenshots; the `ui` lines (lib/ingame/script.ctx) move the
pointer, click, press keys, open menus and select targets:

```
sh kotor/tools/ingame/go.sh kotor/tools/ingame/scripts/menus.txt 32 7:equip 10:inventory
```
