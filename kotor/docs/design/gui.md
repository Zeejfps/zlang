# The GUI and the front end

How the game draws and drives its 2D interface: `kotor/lib/gui` loads `.gui` files into panels and
draws and routes input for them; `kotor/lib/frontend` is everything before a game runs (start-up
movies, the main menu with its 3D background, the options, Load Game, the loading screen). What the
original does is in [re/gui.md](../re/gui.md), [re/render-gui.md](../re/render-gui.md),
[re/gui3d.md](../re/gui3d.md) and [re/app.md](../re/app.md); the file format in
[formats/gff-gui.md](../formats/gff-gui.md).

| Directory | Namespace | What |
|---|---|---|
| `lib/gui/types.ctx` | `gui` | `Gui`, `Panel`, `Control`, `Border`, `Text`, `Event` |
| `lib/gui/load.ctx` | `gui` | `.gui` file to `Panel`: textures and fonts resolved, controls in draw order |
| `lib/gui/text.ctx` | `gui` | token expansion, word wrap and alignment as the engine does them |
| `lib/gui/draw.ctx` | `gui` | borders, labels, buttons, check boxes, sliders, progress bars, list boxes |
| `lib/gui/input.ctx` | `gui` | hover/focus, clicks, capture, wheel, keys, events for the owner |
| `lib/gui/gui.ctx`, `api.ctx` | `gui` | the manager (screen, stack, clocks, drawing) and what owners call |
| `lib/frontend/movie` | `movie` | a non-blocking Bink player (video through YUV quads, sound in a mixer feed) |
| `lib/frontend/gui3d` | `gui3d` | a model seen through a camera node, drawn into a GUI rectangle |
| `lib/frontend/*.ctx` | `frontend` | settings file, saves, the screens, the front end's loop, loading screen |
| `tools/guiview` | | any `.gui` to a PNG; `--all` renders every one and reports what the loader doesn't read |
| `tools/menutest` | | the front end driven headless by a script of clicks and keys, with PNGs |
| `tools/menurun` | | the front end in a real window with real sound and time: a reference engine loop (`--seconds N` makes it a smoke test) |
| `tools/movietest`, `tools/gui3dview` | | the player and the 3D scene on their own |

A program that uses them adds `lib/base res formats tex mdl mdl_cache mdl_render material platform
render render_gl audio video gui frontend` (see `tools/menutest/build.ctx`). `lib/gui` alone needs
`base res formats tex material platform render render_gl audio` (`tools/guiview/build.ctx`).

## The model

**The GUI is never scaled** (re/gui.md section 2). A `.gui` file's coordinates are screen pixels in
its design size (640x480 for the menus, 800x600 for the main menu); a panel sits in the middle of a
bigger window over a resolution-named picture (`800x600back`, `1024x768back`, ...) that fills the
rest. We keep that, and add one switch: `gui::set_screen{ width, height, scale }` makes the GUI's
pixel space the window over `scale` (1 is the original's; 0 asks for `gui::auto_scale`, the largest
quarter step at which the 800x600 main menu still fits). Mouse positions and drawing follow.

A **panel** is one `.gui` file. A **control** is a struct of it. The kinds are the file's
CONTROLTYPEs: label 4, row prototype 5, button 6, check box 7, slider 8, scroll bar 9, progress bar
10, list box 11, plus the edit box code makes out of a label. Controls are drawn in ascending ID
order and hit-tested from the highest down. A list box owns two more controls (its prototype row
and its scroll bar, flagged internal) and a vector of rows its owner fills.

**Textures and fonts are resolved when a panel opens**: a `gui::Img` is a texture handle, its
size and whether its TXI says `blending additive` (44 pictures in the GUI pack: the HUD's frames and
backings, the menu buttons, the reticles), so drawing needs no file system and no device. An additive
picture is added to what is behind it (`SRC_ALPHA, ONE`, as the original's quad batch does with the
texture's own blend pair), which is why the party panel, the action slots and the combat bar show the
world through their black. Textures come through the shared
`material::Cache` the owner passes to `gui::make`; fonts are `font::load`ed (the `b` variant, or
`a` with small fonts; `fnt_console` has none).

**Hover and keyboard focus are one thing**, as in the engine: the control under the pointer becomes
its panel's focus (hilighted, hover sound); arrow keys move it along the file's MOVETO links. A
button's text turns yellow and pulses while it has the focus; a disabled control's goes dim blue.
The focus hilights the control's ancestors too (the Obj_Parent chain): the top menu bar's invisible
tab buttons sit on `LBLH_*` frame labels, and the label's lit picture is what shows on hover (the
label itself takes no pointer, so a tab lights and clicks over its button's rectangle).

**Events go to the owner, polled.** Controls have no handlers. An action puts an `Event` in a queue
(`activate`, `cancel`, `hilight`, `unhilight`, `row_selected`, `row_activated`, `value_changed`,
`text_accepted`, `right_click`, `scrolled`) with the panel id, the control's ID and TAG, and a
value; the owner takes them once a frame and dispatches with `if`/`match` on tags. (ctxlang cannot
store a function whose error set is inferred, so stored callbacks would need a table of
non-failing wrappers; a poll loop is shorter.) Panels are identified by the `u32` `gui::open`
returns.

## The loop

```
let mut g = try gui::make{ heap = &h, rm, cache = &cache, width, height }      // once
gui::set_tlk{ &g, table = &tlk }; gui::set_mixer{ &g, mixer }                  // GUI sounds, strrefs
try gui::load_defaults{ &g, &fs, &dev }                                          // guisounds.2da, cursors

each frame:
    for each sdl::Event ev:
        let used = gui::handle_event{ &g, ev, scale_x, scale_y }                // scale = drawable / window size
        if not used { /* the game's own input */ }
    gui::update{ &g, dt }                                                        // clocks, tooltips, closes panels
    for ev in gui::take_events{ &g } { ... }  gui::clear_events{ &g }            // what the panels say
    // 3D views first, then
    gui::draw{ &g, &frame }                                                      // backdrop, panels, tooltip, pointer
```

- `handle_event` returns true when the GUI used the event: a press on a control (or any press while
  a modal panel is up), a wheel over a control, a key while a panel that takes keys is up
  (`gui::wants_keys`: a modal or full-screen panel; the HUD does not take keys). The owner must
  not also treat it as a world click or a game key. Mouse positions are in window units.
- `gui::is_modal_open` says the world should pause (re/gameloop.md); `gui::is_covered` that a
  full-screen panel hides the world; `gui::has_panels` that anything is open.
- `gui::draw` is `draw_backdrop_pass` then `draw_panels`; a caller with a 3D view that belongs
  between the backdrop and the panels (the main menu's scene) calls the two itself and adds its
  view in between. Passes run in the order added, so this is just ordering.
- Nothing in lib/gui reads time or SDL state: it gets `dt` and events, so scripted runs repeat
  exactly (menutest).

## Screens, modals and the stack

`gui::open{ &g, &fs, &dev, name, mode, modal } -> !u32` loads `name.gui` and puts the panel on top.
Panels draw in stack order, modal ones after the rest; input goes to the top modal panel only, or
else to the front-most shown panel with a control under the pointer.

| `Mode` | Placement | Use |
|---|---|---|
| `full_screen` | centred, with its file's offset, over the resolution's backdrop; hides every panel under it | menus: inventory, options, the main menu, loading screen |
| `dialog` | centred, the file's position ignored | message boxes, resolution list, save name |
| `placed` | where the file puts it | the HUD, tooltips |
| `framed` | the file's place inside a centred 640x480 frame, nothing hidden | character generation's quick/custom lists over the summary |

`gui::close{ &g, id }` removes it after the frame (events its controls made stay valid until
`update`). `gui::set_backdrop{ ..., kind }` picks the picture (0 back, 1 store, 2 pazaak, 3 map,
4 comp, 5 load). The original stretches the picture over the screen, which is right at the five
sizes it has pictures for (the 640x480 panel then sits in the middle of art made for it: the
store's frame, the pazaak table, the galaxy map's bars under its name bar and buttons). On any
other window (a 16:9 one) the stretch makes a second, larger frame around the panel and art that
no longer lines up with the controls, so kinds 0 to 4 are drawn at their resolution's size
(800x600 for an unlisted one), centred, with black around (`draw_backdrop`); the loading screen's
picture (5) stays stretched. Each of these panels has one .gui file (no resolution variants).
`gui::message_box{ &g, &fs, &dev, text, cancel } -> !u32` opens `confirm.gui`
sized to its text; take the `activate` events of `BTN_OK` and `BTN_CANCEL` and close it.

## Defining a screen over a .gui

There is no class per screen. A screen is the code that, after `open`, sets the controls it cares
about by tag and then reacts to events:

```
let id = try gui::open{ &g, &fs, &dev, name = "optgameplay", mode = gui::Mode::full_screen, modal = true }
gui::set_checked{ &g, panel = id, tag = "CB_AUTOSAVE", on = settings.autosave }
try gui::set_strref{ &g, panel = id, tag = "LBL_TITLE", strref = 42261 }
gui::set_focus{ &g, panel = id, tag = "BTN_DIFFICULTY" }
...
for ev in events {
    if ev.panel == id and ev.kind == gui::EventKind::value_changed and slice::eq_bytes{ a = ev.tag, b = "CB_AUTOSAVE" } {
        settings.autosave = ev.value != 0
    }
}
```

What owners set (all by tag; unknown tags are ignored):

| Call | What |
|---|---|
| `set_text`, `set_strref`, `set_text_tokens` | label/button/edit text: as given, a dialog.tlk string, or text with `<tokens>` expanded |
| `set_text_color`, `set_visible`, `set_enabled`, `set_focus`, `set_tooltip` | state |
| `set_value`, `set_max`, `value_of`, `set_checked`, `is_checked` | sliders, progress bars, check boxes |
| `set_picture`, `clear_picture` | a texture in place of the control's fill (portraits, save screenshots, item icons) |
| `list_clear`, `list_add`, `list_set_color`, `list_set_icon`, `list_set_checked`, `list_select`, `list_selected`, `list_count`, `row_rect` | list box rows (`user` is the owner's value, returned in events) |
| `set_list_text` | a list box that shows one wrapped text (descriptions, messages) |
| `make_edit`, `set_max_chars` | a label that takes typed text (the caret is an `_`) |
| `set_background`, `set_panel_picture`, `set_backdrop` | the panel's own fill, a picture in it, its backdrop |
| `control_rect` | a control's rectangle on the screen (3D views are drawn into one) |

**Tokens.** `gui::set_token{ &g, name = "FullName", value }` (and `CUSTOM0`, `CUSTOM1` ...) fills the
table `<FullName>`, `<CUSTOMn>` expand from when a TLK string is shown; `<<` is `<`, an unknown token
becomes `<UNRECOGNIZED TOKEN>` (docs/formats/tlk.md). The engine sets them before opening a panel
whose strings use them.

**Text** (re/gui.md section 5): glyphs from the font's TXI, lines broken at spaces and at
hyphens between letters (a word with no break is split with a `-`), alignment from the file's
ALIGNMENT bits, vertical middle/bottom dropping leading lines when the text overflows. Colours the
code sets: hilighted menu text yellow `(0.98, 1, 0)`, disabled dim blue `(0, 0.33, 0.49)`, menu blue
`(0, 0.66, 0.98)`. Borders follow CSWGuiBorder::Draw: corners and edges rotated by quarter turns
from one top-left corner and one top edge, edges cut in whole segments, fill stretched, tiled or
centred. At a GUI scale that is not a whole number two things keep them even (`draw.ctx` `put_piece`, the
UI fragment shader's `rim`): every piece's four boundaries sit on device pixels (the render size over the GUI's
pixel space), so the one-texel line of an edge strip is as bright and as thick on all four sides; and a quad
never samples past its picture's outermost texel centres, because the art is REPEAT unless its TXI says
`clamp` and a strip drawn thicker than its 8 texels (1.5 times 6) let the linear filter reach round to the
opposite side: the outer edge's line came back along the inner side of every button, and a side's line
inside the ends. Seen on every bordered control at every scale above 1 (1.25 to 4 checked; at the whole
numbers faintly, at the others also with a brighter side); a scale of 1 was always right.
`python kotor/tools/py/gui_scales.py OUT.png EXE [BASE_EXE] WxH:SCALE ...` shows two buttons at the sizes you give.

**Sounds** are guisounds.2da's rows: click (button activation), scroll (hover), open (message
box). Pass a mixer with `gui::set_mixer`; without one the GUI is silent.

**The pointer** is a quad of the game's own cursor art (`gui_mp_<stem>u` / `d` while the button is
down), drawn last; `gui::set_cursor{ &g, id }` picks `CURSOR_DEFAULT`, `ATTACK`, `BASH`, `DOOR`,
`TALK`, `USE` ... (the install ships these 12 stems; the original's walk/examine/follow textures
do not exist in the PC data). Only the default arrow has its hot spot at the corner; the rest are
centred. `set_cursor_visible` hides it. The OS pointer is the engine's to hide (`display::apply` does, in every window
mode: [../mechanics/graphics.md](../mechanics/graphics.md), "The OS pointer").

## In-game panels (what the engine will do)

Everything above works for the HUD, dialogue, inventory and the rest: they are `.gui` files whose
tags re/gui.md section 10.3 and 10.4 list.

- **HUD**: `mipc28x6` (800x600 and every size not listed), `mipc210x7` (1024x768), `mipc212x9`
  (1280x960), `mipc212x10` (1280x1024), `mipc216x12` (1600x1200), opened `placed`, non-modal. It
  takes no keys, so game input keeps them; clicks on its controls are `activate` events, clicks on
  empty HUD fall through (`handle_event` returns false), so the world sees them. The engine hides
  controls its state doesn't show (`set_visible`), sets bars with `set_value`/`set_max` (health and
  Force bars are progress bars with `STARTFROMLEFT` 0 for vertical fill), portraits with
  `set_picture`, and tooltips with `set_tooltip`. A 16:9 window shows the nearest file at its own
  size, not stretched (open item).
- **Dialogue** (`dialog`, `computer`): `LB_REPLIES` rows with `list_add`, the speaker's line in
  `LBL_MESSAGE` (or `set_list_text`); `row_selected` is the pick. The camera and voice-over are the
  engine's.
- **Inventory, equipment, character, abilities, journal, map, store, container**: full-screen
  modal panels; item slots are `set_picture` on the slot's label with the item's icon texture
  (`material` cache, `i_*` names), item lists are `list_add` with `list_set_icon`. The engine owns
  the data and the rules; a panel's code is a function that fills controls from game state on open
  and on change, and one that turns events into game actions. A 3D view in a panel (character
  preview, galaxy map) is a `gui3d::Scene` drawn into `control_rect` between `draw_backdrop_pass`
  and `draw_panels`, as the main menu does.
- **Loading screen**: `frontend::show_loading` before a module loads, `set_loading_progress` as
  it advances (draw a frame each time: `gui::update`, `gui::draw`, submit), `gui::close` when ready.
  The picture is the row of loadscreens.2da labelled with the name (`classsel`, the minigames), else
  the texture `load_<name>` (most modules have one), else the default row. The game's own use of it
  (every way into an area, the settle rule) is in engine.md, "The frame"; the front end shows it for
  the class selection (`begin_chargen`, drawn once before the work).
- **Pause**: while `gui::is_modal_open` the world should not advance.

## The front end

`frontend::Front` is the state: the options, the stack of menu screens (it mirrors the GUI's panel
stack), the start-up movies, the 3D scene, the menu music. The engine drives it while no game
runs:

```
let mut fe = frontend::make{ &fs, heap = &h, game, config_path }      // options from our own file
try frontend::begin{ &fe, &g, &fs, &dev, &sdl, mixer }                // start-up movies, then the main menu
each frame:
    used = frontend::handle_event{ &fe, &g, ev, scale_x, scale_y }    // skips a movie, else gui::handle_event
    gui::update{ &g, dt }
    match frontend::step{ &fe, &g, &fs, &dev, &sdl, output, mixer, dt } {
        running => {}
        new_game{ module }                => frontend::leave{ ... }; start `module` (end_m01aa)
        load_game{ folder, folder_len }   => frontend::leave{ ... }; load Saves/<folder>
        quit                              => exit
    }
    render::begin_frame{ &frame, time }
    frontend::draw{ &fe, &g, &frame, target = gpu::screen_size{ dev } }   // movie, or backdrop + 3D scene + panels
    gpu::submit{ &dev, frame = &frame }
if frontend::take_display_change{ &fe } { apply fe.settings (resolution, full screen, v-sync, gamma, ...) }
```

- **Start-up** (re/app.md `PlayLegalMovies`): `leclogo`, `biologo`, `legal` from `movies/`, each
  skippable with Escape, Enter, Space or a click, unless `disable_movies` is set or `binkw32.dll`
  can't give the codec tables (then the menu comes at once). While a movie plays the GUI is hidden.
- **Main menu**: `mainmenu.gui` (800x600) centred over the backdrop; the debug warp list and
  button and the DLC label hidden, as the original's code does. Its background is a 3D scene, not
  a picture: the model `mainmenu` (Malak in mist, one 16 s animation `default`, two lights, six
  emitters) seen from its node `camerahook` at 22.7 degrees, drawn into `LBL_3DVIEW`'s rectangle
  between the backdrop and the panel (`gui3d`, re/gui3d.md). The still picture in the file
  (`loadscreen3`) is what the original shows without GUI 3D; we show it only if the scene fails.
  `mus_theme_cult` plays in a loop in the music group.
- **New Game** opens character generation ([chargen.md](chargen.md), `lib/chargen`): class selection
  with its six 3D models, quick or custom character and the five steps, then returns `new_game` with
  the start module `end_m01aa` and `player`, the created character as the bytes of a UTC-shaped GFF
  (empty if chargen could not start: the engine then makes its default soldier). While it runs
  `Front.cg` is set, `frontend::step` hands the GUI events to `chargen::on_event`, `frontend::draw`
  adds its 3D views after the panels, and Cancel returns to the main menu. A program that links
  `lib/frontend` also links `lib/rules` and `lib/chargen`.
- **Load Game** (`saveload.gui`): lists our saves directory (`set_own_saves`, the engine's `--saves`)
  and the install's `Saves/` (folder `NNNNNN - Name`; 0 quick save, 1 autosave, 2+ manual): quick
  and auto first (ours hide the install's of the same number), then the manual saves, newest number
  first. Each row's `savenfo.res` (name, area as "Planet - Place", play time, up to three party
  portraits) and `Screen.tga` give the details. A click selects and shows them, a second click or
  Load returns `load_game` with the save's folder as a path (`save::find_save` resolves it, ours or
  the install's). Delete is hidden: the install is never written.
- **Save Game** (in game only, from the options menu; `SCR_SAVE`): the same screen in save mode:
  our manual saves with a "New Slot" row first (selected). Save (or a second click) opens
  `savename.gui` over it (`make_edit` on `EDITBOX`) with "Game N - Hh Mm" (dialog.tlk 1594) for a
  new slot or the chosen save's name; OK or Enter makes the request (`take_save_request`, a name
  for `save::save_named`) and the screens close. Overwriting makes a new slot (the old save stays),
  so the original's "Are you sure you want to overwrite" (1591) is not asked. The options menu
  closes itself on a save or load request, so the saved picture is the game's frame.
- **Movies** (`titlemovie.gui`): rows of `movies.2da` whose `alwaysshow` is 1 or that the player
  has seen (`[Movies Shown]` in our settings file); activating one plays it over the menu.
- **Options**: `optionsmain` opens `optgameplay`, `optfeedback`, `optautopause`, `optgraphics`
  (+ `optresolution`, `optgraphicsadv`), `optsound` (+ `optsoundadv`) and `optmouse`. They edit
  `fe.settings` live and write the file when a panel closes. Their check boxes (and the Feedback
list's rows) are the engine's menu check box (re/gui.md, "Menu check box"): the loader marks every
check box of a panel whose name starts with `opt` (`F_MENU_CHECK`) and tints its borders blue and
yellow; `draw_menu_check` puts the ring in a 25x25 square at the left and the label beside it. Sound sliders apply to the mixer's
  groups at once; graphics changes set `take_display_change` and game/display.ctx makes the device agree
  ([../mechanics/graphics.md](../mechanics/graphics.md)). The resolution list is the display's own
  (`set_display_info`, `build_rows`: SDL's modes, by display mode). The Graphics panel gets two buttons (Display Mode, UI Scale)
  and the Emitters check box, cloned from its neighbours with `gui::clone_control`. Key mapping is not built (its
  button is disabled). The `LB_DESC` description pane shows the string after the control's label in dialog.tlk
  (Shadows 47950, its text 47951), which is where the original keeps them.
- **The options file** is ours (`kotor-settings.ini`, wherever `config_path` says), never the
  install's `swkotor.ini`. Its sections and keys are swkotor.ini's (`[Graphics Options]` ...), so it
  reads familiarly (`Brightness`, `Frame Buffer`, `FullScreen`: 0 windowed, 1 full screen, 2 borderless); unset keys keep
  the original's defaults; `GUI Scale` (0, auto, by default), `Refresh Rate`, `Emitters` and `Frame Limit` are ours.

## Decisions

- **Scaling is automatic**: `scale` 0 picks the largest quarter step at which the 800x600 menu fits the window (1 up to
  1280x720), so a 1080p or 4K window is not a small panel on black; 1 is the original's pixels and is a choice on the Graphics panel.
- **Poll-style events**, agreed with the engine-core lead, instead of handlers.
- **Hover is focus** and keyboard navigation uses MOVETO, as in the engine; Escape is a `cancel`
  event for the top panel (a screen closes itself on it), Enter activates the focused control.
- **A list row needs a second click to activate** (`row_selected` on the first, `row_activated` on
  the second or Enter); lists that act on one click (dialogue replies) use `row_selected`.
- **Unbound controls**: the generic loader creates every control in a file. Controls the original's
  code never binds (the main menu's `LBL_BW`, `LBL_LUCAS`, the debug warp) are hidden by the screen's
  code, not by the loader. `guiview` shows files unhidden.
- **Delete in Load Game is hidden** because the install is read-only for us.
- **The movie list and the options descriptions** are as complete as the data allows; the original's
  per-option description strings are not in the files.

## Open

- The HUD on wide windows (above), and HUD controls the engine must hide per state.
- Gamepad events (0x2d..0x38), key remapping (`optkeymapping`), the dragged inventory item.
- The tooltip is a plain box with the dialog font, not `tooltipWxH.gui`.
- The credits (credits.2da's title cards, then its long list scrolling over black to credits.wav), the story's films (PlayMovie, StartNewModule's sMovie1..6, QueueMovie / PlayMovieQueue) and EndGame's way back to the main menu are game/cine.ctx; see [playthrough-star-forge.md](../playthrough-star-forge.md). The level-up panels, the store, container, upgrade bench and galaxy map are [screens.md](screens.md). Character generation is done (chargen.md). Pazaak: see minigames.md.
- Text colour per list row exists (`list_set_color`); per-row fonts do not.
