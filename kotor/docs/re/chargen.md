# Character generation screens

How the original's new-game character creation behaves, screen by screen, so the screens can be
rebuilt faithfully. This is the detail page behind [gui.md](gui.md) section 10.2 (wiring) and
[rules.md](rules.md) (level-up record, skill points). All addresses are `swkotor.exe` (Steam,
unpacked); names marked "(ours)" are ours. Numbers were checked against the install's 2DA and TLK
data with `kotor/out/q.py`. Confidence is tagged high / med / low. The whole page was rechecked
claim by claim on 2026-10-07 against the exports rebuilt after the noreturn fix
([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check" rests on static
reading alone and is surprising enough to test before relying on it.

Conventions used below: **S** is the creature's stats block, the object at creature `+0x2f8`
(offsets in the field map, section K). UI order of the six abilities is STR, DEX, CON, WIS, INT,
CHA (the order of the strrefs 211..216 and of the buttons); the engine's *stats* order is STR, DEX,
CON, INT, WIS, CHA. Event codes are those of [gui.md](gui.md) (0x27 activate, 0x28 back, 0x29 X,
0x2a Y, 0x2d/0x2e gamepad accept/back, 0x2f/0x30 minus/plus).

## 0. The panels

| Panel (`.gui`) | Class | Ctor | Vtable | Size | How it is shown |
|---|---|---|---|---|---|
| `classsel` | `CSWGuiClassSelection` | `0x006dc3c0` | `0x00758020` | `0x1560` | from the main menu, `AddPanel(2,1)`: full screen, not modal |
| `maincg` | `CSWGuiCharGenMain` | `0x006eb420` | `0x007592a8` | `0x22dc` | `AddPanel(3,1)`: full screen, modal |
| `qorcpnl` | `CSWGuiCharGenQuickOrCustom` | `0x006f09f0` | `0x00759710` | `0xd98` | `AddPanel(1,1)` over `maincg` |
| `quickpnl` | `CSWGuiCharGenQuickPanel` | `0x006f0390` | `0x00759668` | `0x1360` | same |
| `custpnl` | `CSWGuiCharGenCustomPanel` | `0x006ef730` | `0x007595e0` | `0x2188` | same |
| `portcust` | `CSWGuiCharGenPortrait` | `0x006f9430` | `0x00759ea8` | `0x1240` | `AddPanel(3,1)` full screen, modal |
| `name` | `CSWGuiCharGenName` | `0x006f9e70` | `0x00759f38` | `0x9c4` | same |
| `abchrgen` | `CSWGuiCharGenAbilities` | `0x006f7600` | `0x00759c68` | `0x3df4` | same |
| `skchrgen` | `CSWGuiCharGenSkills` | `0x006f51d0` | `0x00759990` | `0x49d0` | same |
| `ftchrgen` | `CSWGuiCharGenFeats` | `0x006f3d60` | `0x007598b0` | `0x1a1c` | same |
| `pwrlvlup` | `CSWGuiCharGenPowers` | `0x006f2180` | `0x00759780` | `0x1a10` | level-up only (section I): its one caller is `CSWGuiLevelUpPanel::OnPowers` `0x006ee350` |

The three step panels (`qorcpnl`, `quickpnl`, `custpnl`) are created once, inside the `maincg`
constructor (`0x006eb420`), and swapped by `ShowStepPanel` (`0x006ea760`). The five sub-step
panels are created on demand by the step panel's button handlers and deleted when accepted or
cancelled. Every panel after class selection keeps the creature (`+0x64`) and its parent (`+0x68`;
class selection uses `+0x68` for the chosen creature). A sub-step panel also
keeps a mode byte (portrait `+0x123c`, name `+0x998`, set with the parent by `0x006f8a00` /
`0x006f9b80`): 1 when opened from the quick panel, 2 from the custom panel; it decides which parent
function runs on accept (high).

The whole character is **one client creature object** (a `CSWCCreature`, 0x44c bytes, ctor
`0x00616a20`) made by the class-selection panel; every step edits it in place, and Play serialises
it (section C.5).

## A. Class selection (`CSWGuiClassSelection`)

Constructor `0x006dc3c0` (arg: start module name, always `END_M01AA` from `OnNewGame` `0x0067afb0`,
kept at `+0x1558`): shows the loading screen with the `classsel` picture and advances its progress
bar between steps, mounts `RIMS:CHARGEN` if `CHARGEN.rim` exists, loads `classsel.gui`, reads
`portraits.2da`, builds six slots, binds `BTN_BACK` (event 0x27 -> `CSWGuiPanel::OnButtonCancel`),
then makes slot 0's button the active control. (high)

### The slot table

`g_aClassSelSlots` at `0x007a2684`: six entries of 8 bytes. The file holds only the gender, soundset
and strref parts; the **class byte of each entry is written by a start-up initialiser
(`0x0073b690`)**, so a raw read of the image shows zeros there. (high)

| Offset | Size | Meaning |
|---|---|---|
| +0 | u8 | class id: 0 Soldier, 1 Scout, 2 Scoundrel (it is also the body-build selector, below) |
| +1 | u8 | gender: 0 male, 1 female |
| +2 | u8 | `soundset.2da` row of the voice: 85 `Player_Male_W` (male), 83 `Player_Female_W` (female) |
| +3 | u8 | padding |
| +4 | u32 | strref of the hover description |

| Slot | Control | Class | Gender | Body (portraits.2da column) | Description strref | Conf |
|---|---|---|---|---|---|---|
| 0 | `BTN_SEL1`, `3D_MODEL1` | Scoundrel | male | `Appearance_S` (small) | 32109 "A skillful rogue ..." | high |
| 1 | `BTN_SEL2`, `3D_MODEL2` | Scout | male | `AppearanceNumber` (medium) | 32110 "An explorer ..." | high |
| 2 | `BTN_SEL3`, `3D_MODEL3` | Soldier | male | `Appearance_L` (large) | 32111 "A battle-ready fighter ..." | high |
| 3 | `BTN_SEL4`, `3D_MODEL4` | Soldier | female | `Appearance_L` | 32111 | high |
| 4 | `BTN_SEL5`, `3D_MODEL5` | Scout | female | `AppearanceNumber` | 32110 | high |
| 5 | `BTN_SEL6`, `3D_MODEL6` | Scoundrel | female | `Appearance_S` | 32109 | high |

So the build per class is: **Soldier = large, Scout = medium, Scoundrel = small**. In
`portraits.2da` the three columns point at three `appearance.2da` rows with the same head
(for example row 1: small 91 `P_FEM_A_SML_01`, medium 92 `..._MED_01`, large 93 `..._LRG_01`).

### What each slot's creature is given

For slot *k* the constructor builds a creature and sets: (high unless noted)

| What | How |
|---|---|
| gender | S `+0x31` = table byte 1 |
| class | class slot 0 (S `+0xf0`) = table byte 0 (`0x00647770`); the creature starts with one class slot at level 1 and race 6 (human) |
| voice | creature `+0x2fc` (on the `CSWCCreature`, not in S) = `soundset.2da` row from byte 2; the setter `0x0060b7c0` also loads that row's sound set file when the value changes |
| portrait | a **random** `portraits.2da` row with `ForPC` non-zero and `Sex` = the slot's gender; stored with the creature's SetPortrait slot (vtable `+0xf4`, `0x0060d5c0` -> `0x00647b80`): S `+0x11c` = the row, S `+0x70` = its portrait resref |
| appearance | the chosen row's `Appearance_L` / `AppearanceNumber` / `Appearance_S` by the class byte (0 / 1 / 2; any other value would take `AppearanceNumber`); stored in S `+0x8c`, and in a copy of the creature's 0x3c-byte appearance record (pointed to by creature `+0x21c`) at field `+0x18`, with `+0x14` = 1 and bytes 0 / 1 = 2 / 1 |
| model | that record applied with `0x006134c0(record, 3, 1)`, the creature attached to the slot's GUI 3D scene (`gui3D_room`, light `cgbody_light`, camera hook `camerahook`) inside `3D_MODEL<k+1>` and given one animation update (`0x0060f7c0(creature, 0, 1)`); all of this only when the GUI-3D global `0x0078d1e4` is set (chargen-3d.md) |

The random draw is `rand() % remaining` (MSVC's per-thread `rand`, seeded once with
`srand(GetTickCount())` in `CClientExoAppInternal::Initialize`, `0x005f8d68`) over the list of eligible rows of that gender
(15 per gender: female rows 1-12 and 15-17, male rows 18-32), and the chosen row is **removed from
the list**, so the three models of one gender always show three different portraits (high). The
draw happens every time the panel is built, so the line-up differs per run. The slot record
(`0x25c` bytes, six from `+0x6c`) holds the button at `+0`, the 3D label at `+0x1c4`, the creature at
`+0x254` and the animation timer at `+0x258` (high).

### The hilighted button is the large one

`classsel.gui` gives `BTN_SEL1` the extent (55, 118, 95x213) and the other five (x, 128, 75x193): the
large size is 10 pixels more on every side, and each `3D_MODELn` label is its button inset by 3 and
moves with it. The panel's per-frame render (vtable slot 13, `0x006dc030`, then `CSWGuiPanel::Render`)
animates this for all six slots from the button's hilight flag (control `+0x44` bit 0, which hover and
the keyboard focus set): hilighted buttons go to TOP 118 (0x76), the others to TOP 128 (0x80). Each
step moves left and top by the TOP change and shrinks or grows width and height by twice it, on the
button and on its 3D label alike (the scene's viewport is the label's rectangle, so the model scales
with it). The animation: when TOP is off its target and the slot's timer (`+0x258` of the slot record,
-1.0 = idle) is idle, the timer is set to `(distance / 10) * 0.25` s (integer division, so a distance
under 10 snaps on the next frame) and that frame does not move; each later frame subtracts the frame
time, and while the timer is positive TOP is `128 - trunc((0.25 - timer) * 40)` growing (`118 +
trunc(...)` shrinking), until it reaches the target; when the timer runs out it snaps and goes idle.
So 10 pixels take a quarter of a second. At start slot 0 is the active control, hence large. (high)
The same render, while the panel is visible (flag `0x80`) and the GUI-3D global is set, advances
each slot creature's animation by the frame time (`0x0060f7c0`) and, when a creature's model is no
longer in its slot's scene, re-attaches it by calling vtable `+0x94` on the creature at panel `+0x68`
with that slot's scene: the chosen creature, the only one that leaves (it is shown in `maincg`), so
after Back it returns to its slot (med).

### Hover and select

| Event | Handler | Behaviour |
|---|---|---|
| hover (event 0) | `OnHoverClass` `0x006dba70` | only when the event value is non-zero; `LBL_CLASS` text = gender word (646 "Male" for byte 1 = 0, else 647 "Female") + " " + class name (class byte 2: 135 Scoundrel, 1: 133 Scout, otherwise 134 Soldier); `LBL_DESC` strref = table +4. (high) |
| 0x27, 0x2d | `OnSelectClass` `0x006db9b0` | only on press (value != 0); plays the click on 0x2d; stores the slot's creature at panel `+0x68`; builds `CSWGuiCharGenMain` with that creature and the panel itself; `AddPanel(3,1)` (high) |
| 0x28, 0x2e (Back; `BTN_BACK` sends 0x28 through `OnButtonCancel`) | `0x006dbd30` (the panel's input handler, vtable slot 15) | on press: plays GUI sound 0, marks the panel for deletion (flag 0x400) and shows the main menu (`ShowMainMenu`); events 0x35/0x36 are re-sent as 0x2f/0x30; every event then goes to `CSWGuiPanel::HandleInputEvent` (high) |

`OnSelectClass` stores nothing else: **class, gender, appearance, portrait and voice all live in
the chosen creature**, and later panels read them from it. The other five creatures stay in their
slots unused (the class selection stays under `maincg` and comes back on Back). The panel's
`OnPanelAdded` (`0x006db8f0`, vtable slot 18) empties the `GAMEINPROGRESS:` directory (the temporary
save area), makes two input-setup calls for events 0x28 and 0x2e with the value 500
(`0x005df4b0`; purpose not identified), takes the loading screen down (`0x005eda90(1,1)` ->
`0x005f6e20`) and, after the base `OnPanelAdded`, keeps or starts the menu music `mus_theme_rep`
(`0x005ed9b0(0, 0x7f, 2)`, med for the arguments). Static texts from the `.gui`: `LBL_CHAR_GEN` 208
"CHARACTER GENERATION", `LBL_INSTRUCTION` 32160 "Choose your class", `BTN_BACK` 1581 "Cancel".
Initial `LBL_CLASS` strref in the file is 135 (replaced on first hover); the first hover happens
because the constructor makes slot 0's button the active control, and `SetActiveControl`
(`0x0040a630`) sends the new control event 0 with value 1. (high)

## B. Main panel (`maincg`, `CSWGuiCharGenMain`)

### Labels the code binds

The constructor binds only these tags; everything else in `maincg.gui` (`OLD_*_LBL`, `NEW_VIT_LBL`,
`NEW_DEF_LBL`, the `*_ARROW_LBL`s, `OLD_LBL`, `NEW_LBL`, `LBL_LEVEL`, `LBL_LEVEL_VAL`) is **never
created in character generation**. `LBL_LEVEL` and `LBL_LEVEL_VAL` are bound by the level-up panel
(`CSWGuiLevelUpMain` `0x006e8ef0`, which loads the same `maincg.gui`); the other tags are not in the
executable at all, so no panel ever creates them. (high)

| Tag | At start | Set later by | Value |
|---|---|---|---|
| `MAIN_TITLE_LBL` | 208 "CHARACTER GENERATION" (file) | never | |
| `LBL_NAME` | empty (`+0x22d4` = "") | name step accepted (`0x006eef70` -> `0x006ea9b0`) | the creature's name (vtable `+0x70`, `0x00647ce0`): first + " " + last when both are set, otherwise whichever is set (the Name step fills only the first, so just what was typed) |
| `LBL_CLASS` | class name of class slot 0, built at construction (before `LoadGui`) by `0x006ea910`: `0x00648470` makes `<class name> (<level>)` and the label keeps the text before "(", so it always ends with a space | re-set with the name, from the same stored string (`+0x22cc`) | |
| `PORTRAIT_LBL` | the creature's portrait picture: border fill = creature vtable `+0x148` with flag 0, i.e. the portrait resref S `+0x70` that SetPortrait stored | portrait step accepted (`0x006ea9f0`, which also blanks the label's text) | that resref (the portraits row's `baseresref`) |
| `MODEL_LBL` | 3D scene `gui3D_room`, light `charrec_light`, showing the creature (`0x006100f0`) | portrait accepted (`0x006ea9f0` re-applies the model from S `+0x8c` and re-aims the camera) | |
| `STR_LBL`, `DEX_LBL`, `CON_LBL`, `WIS_LBL`, `INT_LBL`, `CHA_LBL` | 211, 212, 213, 214, 215, 216 (file) | never | the ability names |
| `STR_AB_LBL` .. `CHA_AB_LBL` | empty | `RefreshSummary` | the **chosen base score** as a plain integer (S `+0x3a..+0x3f`: STR, DEX, CON, INT, WIS, CHA). Not the modifier, and no racial adjustment |
| `LBL_DEF` | empty | `RefreshSummary` | defense, S `+0x50` (read back with `0x00647720`) |
| `LBL_VIT` | empty | `RefreshSummary` | hit die + CON modifier + S `+0x48` (0 at start); computed for the label only, not stored |
| `NEW_FORT_LBL`, `NEW_REFL_LBL`, `NEW_WILL_LBL` | empty | `RefreshSummary` | S `+0x5c`, `+0x5e`, `+0x5d` |
| `LBL_FORTITUDE`, `LBL_REFLEX`, `LBL_WILL` | 1056, 1057, 1058 (file) | never | "Fortitude", "Reflex", "Will" |
| `LBL_BEVEL_L/M/R` | decoration | | |

`RefreshSummary` (ours; `0x006eac30`) recomputes the three saves into S (`0x00648b30` fortitude,
`0x00648be0` will, `0x00648c90` reflex), writes the six score labels, computes the defense into S
`+0x50`, then writes `LBL_DEF`, the fortitude and reflex labels, `LBL_VIT` and the will label. The
formulas (high): modifier of a score *s* = floor(*s*/2) - 5 (`0x00647630`); every term uses the
scores with the racial adjustment (S `+0x34..+0x39`).

| Value | Formula |
|---|---|
| defense | 10 + DEX modifier (score S `+0x35`) + S `+0x40` (a bonus byte, 0 for a fresh character) + sum over class slots of `acbonus.2da[class column][class level]` (`CSWClass::GetACBonus` `0x005be770`); Scoundrel gets +2 at level 1, Soldier and Scout 0 |
| fortitude (S `+0x5c`) | CON modifier + sum over class slots of the class's save bonus at that slot's level (`CSWClass::GetFortSaveBonus` `0x005bccd0`) |
| reflex (S `+0x5e`) | DEX modifier + S `+0x40` + the same sum from the reflex table (`0x005bccf0`; levels 1..60, else 0) |
| will (S `+0x5d`) | WIS modifier + the same sum from the will table (`0x005bcd10`) |
| vitality | class `hitdie` (class record `+0x54`, of the last class slot: the only one at chargen) + CON modifier + S `+0x48` |

It is called (a) when the quick panel is shown (`0x006f0260`, the quick panel's `OnPanelAdded`,
vtable slot 18) and (b) in custom mode right after the Attributes step is accepted (`0x006ef500`,
reached from `CSWGuiCharGenAbilities::Accept` `0x006f7330` through `0x006f6e70`). Nothing else refreshes it: **in custom mode the value
labels stay blank until Attributes is accepted, and skills and feats never touch them.** (high)

`ResetCharacter` (`0x006eb010`, called by Cancel and by stepping back far enough) blanks the eleven
value labels and resets the creature: all six base scores to 8 (each setter also rewrites the
adjusted score), the saves recomputed, then `0x00649a70`: skill points left (S `+0xae`) and the base
and total rank arrays to 0, totals recomputed from the base ranks (`0x00649380`), the feat list and
the two other lists beside it emptied (`0x00648320`), the per-class power lists emptied
(`0x00649520`), the level-1 granted feats added again (`0x00649950`) and the starting-item resref
list (S `+0x128`) emptied. It does not touch the name label, the portrait, the appearance or the
attribute points left (S `+0xac`). (high)

### Where the pieces sit

* `maincg.gui` is 640x480 at (0,0); `AddPanel(3,1)` makes it full screen (centred, backdrop around).
* Its `OnPanelAdded` (`0x006ea810`, vtable slot 18) adds the quick-or-custom panel on top
  (`AddPanel(1,1)`), so the screen after a class click is `maincg` + `qorcpnl`. Current step panel
  id is `+0x22c8` (the constructor sets 1): 1 qorc, 2 quick, 3 custom, 4 none. The step panels are
  at `+0x6c`, `+0x70`, `+0x74`. (high)
* The step panels are **not** full screen. Their own `.gui` extents are qorc (322,87) 273x281, quick
  and custom (322,87) 267x275, and the code adds panel flags 0x60 (centre inside a 640x480 frame
  both ways), so they sit at their file position over the middle right of `maincg` (x 322-595,
  y 87-362 or 368). What stays visible around them: the left half (portrait, model, name, scores,
  vitality, defense), `LBL_CLASS` above (351,64) and the three save rows below (y 358-408; their
  top edge is a few pixels under the panel). Added with `AddPanel(1,1)` (modal, not full
  screen). (high)
* The five sub-step panels are 640x480 full-screen menus (`AddPanel(3,1)`) and hide `maincg`.
  `maincg.Render` (`0x006eb340`, vtable slot 13) still advances the 3D model each frame (`0x0060f7c0`
  with the frame time) while `maincg` is visible (flag `0x80`), i.e. under a step panel; when the
  creature's model has left the `MODEL_LBL` scene it re-attaches it and re-aims the camera. (high)
* `ShowStepPanel(n)` (`0x006ea760`): same n does nothing; otherwise pop the modal, remove the old
  step panel, `AddPanel(new,1,1)` and store n. If the current id is 4 (none) it only pops the modal;
  an n outside 1..3 sets 4. Every caller passes 1, 2 or 3. (high)
* Play: `Finish` (`0x006eb320`) = `Close` (`0x006ea830`) + `StartGame` (`0x006dbdf0`, section C.5).
  `Close` pops the modal, marks each step panel that is in the manager for deletion (flag 0x400)
  and deletes the others at once (pointer cleared), pops the modal again and marks itself for
  deletion. Back on the qorc panel (`0x006f07d0`) is `Close` and the qorc panel marking itself,
  which returns to class selection (still on screen below). (high)

## C. Quick or custom, the step lists, Back and Cancel

### C.1 Quick or custom (`qorcpnl`)

`QUICK_CHAR_BTN` (239 "Quick Character") -> `OnQuick` `0x006f0800` -> `ShowStepPanel(2)`.
`CUST_CHAR_BTN` (240 "Custom Character") -> `OnCustom` `0x006f0830` -> `ShowStepPanel(3)`.
Hovering fills `LB_DESC` with strref 241 (quick) or 242 (custom) through `0x006f0860`; the quick
button starts active. The texts really begin "Quick Help Text: ..." and "Custom Help Text: ...".
`BTN_BACK` (the file shows strref 1581 "Cancel") sends back (0x28; Esc/right click 0x28/0x2e go the
same way, `0x006f0e10` -> `0x006f07d0`): `Close` on `maincg` and the panel marks itself for deletion,
which returns to class selection. (high)

### C.2 Steps

Both step panels hold a step counter (quick `+0x135c`, custom `+0x2184`), set by a "SetStep"
function (quick `0x006efc10`, custom `0x006eefd0`). **Only the button of the current step is
enabled and highlighted; every other one, earlier or later, is disabled**, so the order is forced
and a finished step can only be revisited with Back. Each step is three controls: the circle `LBL_k`
(type 5, `lbl_cg_circ1`, hilight fill `lbl_cg_circ2`), the number `LBL_NUMk` and the name
`BTN_STEPNAMEk`. SetStep hilights the current step's circle (vtable slot 16, SetHilighted) and makes
its number and name selectable (slot 34) in `g_vGuiMenuHilightTextColor` (0x007a23c0: 0.98, 1, 0);
the others' circles lose the hilight and their numbers and names are made unselectable, which dims
their text. The circles are never made selectable: the pointer doesn't hover or click them. Each handler also checks the counter (table).
`BTN_BACK` is disabled (dim colour) at step 0.

| Panel | Step | Button | strref | Opens | Needs counter | Finishing sets counter to |
|---|---|---|---|---|---|---|
| quick | 0 | `BTN_STEPNAME1` | 231 Portrait | portrait | any | 1 |
| quick | 1 | `BTN_STEPNAME2` | 234 Name | name | >= 1 | 2 |
| quick | 2 | `BTN_STEPNAME3` | 235 Play | `Finish` | >= 2 (`0x006efd60`) | |
| custom | 0 | `BTN_STEPNAME1` | 231 Portrait | portrait | any | 1 |
| custom | 1 | `BTN_STEPNAME2` | 209 Attributes | abilities | >= 1 | 2 (`0x006ef500`, also refreshes the summary) |
| custom | 2 | `BTN_STEPNAME3` | 233 Skills | skills | >= 2 | 3 (`0x006ef520`) |
| custom | 3 | `BTN_STEPNAME4` | 232 Feats | feats | >= 3 | 4 (`0x006ef530`) |
| custom | 4 | `BTN_STEPNAME5` | 234 Name | name | >= 4 | 5 (`0x006ef4e0`) |
| custom | 5 | `BTN_STEPNAME6` | 235 Play | `Finish` | >= 5 (`0x006ef220`) | |

All six custom steps and both quick steps before Play are mandatory; nothing can be skipped.
**Play is enabled only after the name has been accepted** (so the portrait and, in custom mode,
abilities, skills and feats have been done too). The quick panel's buttons list "Portrait / Name /
Play" with step-number labels `LBL_NUM1..3`. (high)

Quirk: the quick panel registers its Cancel handler (`0x006f0310`) on the **gamepad-accept event
0x2d of the Play button**; with mouse and keyboard (0x27) Play works. Irrelevant on PC. (med)

### C.3 Back, Cancel and the confirmation

| Action | Quick (`0x006f0280`) | Custom (`0x006ef610`) |
|---|---|---|
| Back button / Esc / right click (0x28, 0x2e) at counter > 0 | counter - 1, the previous step is enabled again; nothing is undone | same, and when the new counter is 1 the character is reset (`0x006ef540`: `ResetCharacter` `0x006eb010`, then S `+0xac` = 30 points), so leaving Skills for Attributes wipes scores (all 8), skill points and ranks and the feat list (the level-1 granted feats are added back, `0x00649a70`); other Back steps undo nothing |
| same at counter 0 (keys only; the button is disabled) | `ShowStepPanel(1)` + `ResetCharacter`, counter 0 | `ShowStepPanel(1)` + `ResetCharacter` + points = 30 (`0x006ef570`) |
| `BTN_CANCEL` at counter 0 | `OnCancel` `0x006f0310`: same as above, no question | `OnCancel` `0x006ef6a0`: same |
| `BTN_CANCEL` at counter > 0 | confirm box (`CSWGuiMessageBox` at in-game GUI `+0x98`, confirm mode on) with strref 48541 "Are you sure you want to cancel?"; on Yes `0x006f0220` / `0x006ef5b0` do the reset | same |

(high)

### C.4 What Quick Character fills in

When the quick panel is added (`OnPanelAdded` `0x006f0260`) it runs the auto-build `0x006effd0` and
then `RefreshSummary`, so the summary shows a finished character before the portrait is touched.
The build, for the class in the last class slot (high):

1. **Abilities** = the class row's `str, dex, con, wis, int, cha` columns of `classes.2da`
   (class record `+0x17b..+0x180`; stored order STR, DEX, CON, INT, WIS, CHA, loader `0x0054f2c0`).
   Soldier 16/14/14/12/10/10, Scout 12/16/12/12/14/10, Scoundrel 10/16/10/12/14/14 (STR/DEX/CON/WIS/INT/CHA).
   Each set costs exactly 30 points under the section F price list (checked: Soldier 10+6+6+4+2+2,
   Scout 4+10+4+4+6+2, Scoundrel 2+10+2+4+6+6).
2. **Granted feats**: every feat whose `<code>_List` is 3 and `<code>_Granted` equals the class
   level (1), plus racial ones (`0x00649950`).
3. **Recommended feats** (`0x0064a770`): `featgain.2da` `<code>_REG` + `<code>_BON` for level 1
   (1 + 0 for all three classes) feats, taken in rising `feat.2da` `<code>_Recom` rank, skipping
   ones already known, ones failing prerequisites (`0x0064a2e0`, the client copy of rules.md 6:
   granted level, `mincharlevel` against the total level, base attack, STR/DEX/INT/WIS minimums on
   the base scores, prerequisite feats, required skill) and ones whose list kind does not fit a free
   slot (`_List` 0 general, 1 general or bonus, 2 bonus). Derived from
   the data (not run): Soldier gets RAPID_SHOT (rank 1), Scout gets CRITICAL_STRIKE (rank 2; rank 1
   FLURRY is already granted), Scoundrel gets DUELING (rank 1). (med)
4. **Skill points** (`0x00648a00`, level 1): (INT modifier + skillpointbase / 2) x 4, where the
   modifier uses the chosen base INT (S `+0x3d`, before racial adjustment) and the division is an
   integer shift, and the result is at least 4 (rules.md 4: max(1, ...) x 4).
   Soldier 4, Scout 20, Scoundrel 24 (skillpointbase 2, 6, 8; INT 10, 14, 14).
5. **Skill ranks** (`0x006491a0`): walk the class's skills in rising `skills.2da` `<code>_reco`
   order and keep buying ranks (`0x00648d50`) until each is at its cap (level + 3 = 4 for a class
   skill at 1 point a rank, half that for a cross-class one at 2 points) or the points run out.
   Derived result: Soldier Treat Injury 4; Scout Computer Use, Demolitions, Repair, Awareness,
   Treat Injury 4 each; Scoundrel Stealth, Demolitions, Security, Awareness 4 each, Treat Injury 2,
   Repair 2. (med)

The auto-build runs every time the quick panel is (re)added, e.g. after Cancel -> Quick again. It
does not clear ranks or feats itself (it adds to them); every way back to the quick-or-custom panel
goes through `ResetCharacter` first, so it always starts from a clean creature.

### C.5 Play

`StartGame` (`0x006dbdf0`), after `Close`: `0x005ee120` (acts on the client's streaming sound
source at `+0x238`, pumps sound updates for 750 ms, then pauses it: the menu music stops; med),
`0x0062b410(1)` (increments a counter at in-game GUI `+0xd8`, purpose unknown), stats `+0x120`
(written as `ForcePoints`) = 0, `CAppManager::CreateServer`, then `0x006123e0` serialises the
creature into a BIC-style GFF (`"BIC "`, `V2.0`, written as `TEMP:temp`, resource type 0x7df;
fields include the six base scores minus racial adjustment, `ClassList`/`LvlStatList` with the hit
die, `SkillList`, `SkillPoints`, `FeatList`, `Portrait`/`PortraitId`, `Appearance_Type`,
`SoundSetFile`, `FirstName`/`LastName`, `HitPoints`, `MaxHitPoints`, `ForcePoints`, the default
`k_hen_*`/`k_def_*` scripts; the server ignores the file's maximum and builds max HP from the level
record, [chargen-creature.md](chargen-creature.md) 4.3), joins the local server (`0x005d5040`),
sends the admin text `s` + `Module.Load END_M01AA` (format `%c%s.%s %s`, the module name from
class selection `+0x1558`) as a net-layer message addressed to id `0xfffffffd`, sets the player
file name `temp` (`0x005edaa0`), marks the class-selection panel for deletion, then sets the
loading-screen image and shows the loading screen (`0x005eda80`) with a hint.
Unspent skill points are stored in the file. (high for order, med for the message)

## D. Portrait step (`portcust`)

Controls: `LBL_HEAD` (532x190 3D view, light `cghead_light`, camera hook `camerahook%c`),
`LBL_PORTRAIT` (98x98 picture), `BTN_ARRL`, `BTN_ARRR`, `BTN_ACCEPT` (1580 "OK"), `BTN_BACK` (1581
"Cancel"), titles `MAIN_TITLE_LBL` 208 and `SUB_TITLE_LBL` 231 "Portrait" (both from the file).

| Question | Answer | Conf |
|---|---|---|
| Which portraits | `portraits.2da` rows with `ForPC` = 1 **and** `Sex` equal to the creature's gender (`0x006f90f0`), in table order. No race or class filter. That is 15 female (rows 1-12, 15-17) and 15 male (rows 18-32) | high |
| Class dependence | none on the list; the class build only picks which appearance column is used for each row (`Appearance_L` Soldier, `AppearanceNumber` Scout, `Appearance_S` Scoundrel) | high |
| Initial portrait | the creature's current portrait id (the random one from class selection) if it is in the list, else index 0 | high |
| Left / right | `BTN_ARRL`/0x2f/0x35/0x3f = previous, `BTN_ARRR`/0x30/0x36/0x40 = next; both **wrap** (previous inline in the input handler `0x006f8ff0`, next `0x006f8fc0`). Each press re-applies the appearance at once | high |
| Draw order | `LBL_HEAD` is the file's first control and has `ID` 0 (controls draw in `ID` order, [gui.md](gui.md) 1), so the 3D head is drawn first and the portrait picture (`LBL_PORTRAIT`, left), the bevels and the two arrow buttons (`BTN_ARRL` at 259, `BTN_ARRR` at 527) are drawn over it; the 3D control fills no colour, the panel's `lbl_cg_portbk` picture shows around the scene | high |
| Head and body | the portrait row's appearance row (`appearance.2da`) drives both: `NormalHead` -> `heads.2da` row (appearance 91 -> row 26 `PFHA01`, 136 -> row 41 `PMHA01`, one head per portrait A1..C5) and the body model `PFBAx`/`PMBAx` (x = `S` Scoundrel, `M` Scout, `L` Soldier, from the class's appearance column) with the row's skin texture. `BackUpHead` is empty for all 90 player appearances (rows 91-180), so it never matters here | med (head rule read from data and call chain; the head code in the visual builder was not read) |
| Per change | `0x006f8ad0`: when the row differs from the creature's current portrait id: SetPortraitId(row) (`CSWCCreature` vtable `+0xf4`, `0x0060d5c0` -> `0x00647b80`), write the appearance into the visual info, re-apply (`0x006134c0`), play idle animation "pause1" on both animation slots; always: refresh the `LBL_PORTRAIT` picture and the 3D camera. Opening the step plays "pause2" on both slots; the panel's update (`0x006f8c60`) plays "pause2" or "listen" at random on a timer of 1.00-3.99 s (first one at once) | med |
| Accept (0x27, 0x2d) | `0x006f8a20`: set the portrait resref to empty (vtable `+0xec`, `0x0060d560`: stats `+0x70`), SetPortraitId(row) (`0x00647b80`: S `+0x11c` = row and S `+0x70` = that row's resref), S `+0x8c` = the list's appearance, pop and delete the panel; then quick: refresh the main model and counter 1 (`0x006eff60`); custom: refresh the main model and counter 1 (`0x006ef4c0`) | high |
| Back (0x28, 0x2e) | `0x006f8f40`: look up the saved original portrait (taken at panel creation, `+0x1238`) in the list and re-apply it, pop; quick re-highlights the step and, at counter 0, refreshes the main model (`0x006eff10`); custom only re-highlights (`0x006ef480`). If the original were not in the list the index becomes -1 and the list is read out of bounds; the class-selection portrait always comes from the same list | high |

The portrait step stores nothing but the portrait row id (S `+0x11c`), its resref (S `+0x70`)
and the appearance id (S `+0x8c` and the visual info); the gender, class build and voice are
untouched.

## E. Name step (`name`)

| Item | Value | Conf |
|---|---|---|
| Titles | `MAIN_TITLE_LBL` 208, `SUB_TITLE_LBL` 234 "Name" (file) | high |
| Controls | `NAME_BOX_EDIT` (edit box), `BTN_RANDOM` (48579 "Random Name", sends Y = 0x2a), `END_BTN` (1580 "OK"), `BTN_BACK` (1581) | high |
| Initial text | when the panel is added (`0x006fa140`): the name already stored on `maincg` (`+0x22d4`, read through the step panel, `0x006effa0`) if any, else a **random name** | high |
| Random name | `0x006f9bf0` (also on Y = 0x2a) calls the LTR generator `0x007118c0` with race 6 (human), flags 6 = female first + last (`humanf`, `humanl`) for gender 1 or flags 5 = male first + last (`humanm`, `humanl`) otherwise, length 15. The 15 is a budget for both parts: the first name gets a maximum of *u* = 5 + rand() % 5 (5-9) letters, the last name 15 - *u*; if either comes back empty other splits are tried (*u* up to 9, then smaller starting values). The parts are joined by one space (see [../formats/ltr.md](../formats/ltr.md)), so a generated name normally has at most 16 characters and fits the edit box limit; it is set with `SetText`, not typed | high (resrefs, flags), med (length) |
| Max length | 18 characters: `0x006f9e70` writes 0x12 into the edit text's limit field (`+0x70`, i.e. panel `+0x380`), and `CSWGuiEditText::AppendText` (`0x004163a0`) only appends while the length is below it. The edit box ignores `_`, `/`, `\` and control codes (`0x004184f0`); Enter accepts, Esc is back | high |
| Accept (0x27, 0x2d, Enter) | `0x006f9cd0`: if the text is empty, message box strref 42360 "You must specify a name." (OK only) and the panel stays; otherwise strip trailing spaces, store it as the **first name** with an empty last name (`0x0060d600`: S `+0x14`, `+0x1c`), pop and delete the panel, update `LBL_NAME`/`LBL_CLASS` (`0x006eef70`), then quick counter 2 (`0x006eff80`) or custom counter 5 (`0x006ef4e0`) | high |
| Back (0x28, 0x2e) | `0x006f9ba0`: pops the panel without storing and re-highlights the step | high |
| Default name | there is none: an empty name is refused, and the box starts with a random one, so the Name step is always visited | high |

A name of only spaces passes the length test, is trimmed to empty and is stored as empty (the
loop strips it away; `CExoString::GetChar(-1)` returns 0, which ends the loop), so Play is then
enabled with an empty first name; an original quirk, med (static reading, needs a runtime check).

## F. Attributes step (`abchrgen`)

Panel state: remaining points `+0x3db8`, six current scores `+0x3dbc..+0x3dd0` in **panel row
order** (STR, DEX, CON, WIS, INT, CHA; the controls of each row are laid out in that order too, a
stride of 0x1c4 per button), focused row `+0x3dec` (0, STR, at open), level-up flag `+0x3df0` (0
here), description strrefs `+0x3da0..` = 222..227. On screen the file puts INT above WIS (rows at
y 137, 183, 228, **273 INT, 318 WIS**, 363). (high)

| Item | Value | Conf |
|---|---|---|
| Titles | `MAIN_TITLE_LBL` 208, `SUB_TITLE_LBL` 209 "Attributes", `SELECTIONS_REMAINING_LBL` 210 "Remaining Points", `DESC_LBL` 217 "Description", `COST_LBL` 218 "Point Cost", `LBL_MODIFIER` 32112 "Modifier" (file) | high |
| Start | scores copied from the creature (8 each after a reset, 8 for a fresh creature); points = S `+0xac`, which a fresh creature has as 30 (`0x0064b2d0`) and every custom-panel reset sets to 30 (`ResetCharacter` itself does not touch it; quick mode never changes it) | high |
| Range | 8 to 18 | high |
| Cost to raise from *v* to *v*+1 | 1 for *v* below 14, 2 for 14 and 15, 3 for 16 and up (`0x006f8670`, `GetIncreaseCost` `0x006f6bb0`). Total from 8: 14 -> 6, 15 -> 8, 16 -> 10, 17 -> 13, 18 -> 16 | high |
| Refund when lowering *v* | the same price paid for *v*-1 -> *v* (`GetDecreaseRefund` `0x006f6b60`): 1 above 8 up to 14, 2 for 15 and 16, 3 for 17 and 18 | high |
| Plus | does nothing silently when points are 0 (checked first, so 18 with no points left is silent too) or the price exceeds the points; at 18 with points left shows strref 42181 "Attribute scores cannot be raised above 18 during character generation." (reachable by key only, the button being hidden). The plus button is **hidden** at 18 and the minus at 8 (`IncreaseAbility` `0x006f8670` / `DecreaseAbility` `0x006f8480` clear the button's visible bit, control `+0x44` 0x02, and set it on the other one); running out of points hides nothing. In level-up (`+0x3df0` set) there is no cap of 18 and every point costs 1, so plus is never hidden, and minus hides at the score the panel opened with (`+0x3dd4..`) | high |
| Minus | at 8 shows 42180 "Attribute scores cannot be reduced below 8." | high |
| Focus | hovering a `*_POINTS_BTN` (event 0, `OnHoverAbility` `0x006f70e0`) focuses that row; un-hover (event 1, `0x006f6e40`) only drops the highlight, the focus stays. The +/- buttons (`OnButtonPrev/Next`, events 0x2f/0x30; keys 0x3f/0x40; handler `0x006f8880`) act on the **focused** row, not on the row the button sits in (static reading, needs a runtime check) | med |
| Labels per change | the row's `*_POINTS_BTN` text = its score; `REMAINING_SELECTIONS_LBL` = points left; on hover `COST_POINTS_LBL` = price of the next point for that row, `LBL_ABILITY_MOD` = modifier of its current score ("-" for 0, "+n" above, "-n" below), `LB_DESC` = strref 222 STR, 223 DEX, 224 CON, 225 WIS, 226 INT, 227 CHA. | high |
| Recommended (`BTN_RECOMMENDED`, strref 221; event 0x2a) | works **only while points remain** (`> 0`): sets the six scores to the class's `classes.2da` row (section C.4 values) and points to 0 (`0x006f7390`) | high |
| Accept (0x27, 0x2d) | if points > 0: message 48217 "You must spend all of your points. Click on the +/- arrows or use the arrow keys to assign points." and stay; else write the six scores to the creature (`0x006f6e70`: STR, CHA, INT, WIS, CON, DEX setters, S `+0x3a..` and the racial-adjusted `+0x34..`; DEX also updates defense, CON recomputes the level-1 hit points), S `+0xac` = 0, pop, refresh the summary, custom counter 2 (`0x006ef500`) | high |
| Back (0x28, 0x2e) | `0x006f6de0`: nothing written; S `+0xac` set back to 30; re-highlight | high |

The scores a human gets after Accept equal the chosen ones (racial adjustments of `racialtypes`
are applied on top inside S `+0x34..+0x39`, none for humans).

## G. Skills step (`skchrgen`)

| Item | Value | Conf |
|---|---|---|
| Titles | `SUB_TITLE_LBL` 233 "Skills", `SELECTIONS_REMAINING_LBL` 210, `COST_LBL` 218; skill names 243, 245, 247, 249, 251, 253, 255, 257 (file). In level-up the constructor's third argument (the level-up flag) replaces `MAIN_TITLE_LBL` with 1071 "Level Up" | high |
| Rows (top to bottom = `skills.2da` rows) | 0 Computer Use, 1 Demolitions, 2 Stealth, 3 Awareness, 4 Persuade, 5 Repair, 6 Security, 7 Treat Injury. Each row is a label, `*_MINUS_BTN`, `*_POINTS_BTN` (shows the base rank, S `+0x88`) and `*_PLUS_BTN`; the points buttons chain up/down through `MOVETO`, and the panel opens focused on Computer Use | high |
| Points at level 1 | S `+0xae` = 4 x max(1, INT modifier + `skillpointbase` / 2), the division an integer shift (`0x00648a00`; at total level 1 it overwrites `+0xae`, at later levels it adds max(1, (modifier + base) / 2), as rules.md 4.4 has it). The modifier is floor(INT / 2) - 5 of the chosen base INT (S `+0x3d`, `0x00648280`), without the racial adjustment; humans have none and a fresh creature has no effects, so it equals the effective modifier rules.md uses. The constructor recomputes the points every time the panel opens | high |
| Opening | in chargen the panel sets every base and total rank to 0 first (`0x006488e0` with 0, then total `+0x84` = 0), so re-entering starts from 0, and recomputes the points. It remembers each row's rank at opening (0 in chargen) as the minus floor. Minus starts **hidden** on rows at that floor, plus hidden on rows at the cap (the visible bit, control `+0x44` 0x02, not the enabled bit; the same rule in Recommended `0x006f4e20`). Running out of points hides nothing | high |
| Cost per rank | class skill 1, cross-class 2 (`0x00647900`, `0x00648d50`); a skill is "class" when any of the creature's class slots lists it as class in its skill table (class `+0x164`, from `skills.2da` `<code>_class`; `0x006f4b60`); a skill is buyable when `AllClassesCanUse` is set or a class table has it, and all eight have `AllClassesCanUse` | high |
| Cap | class skill: total class level + 3 (4 at level 1); cross-class: (level + 3) / 2 rounded down (2 at level 1) | high |
| Plus (0x30/0x40) | acts on the focused row (`+0x49bc`, see "Focused row") (`0x006f6570`). First the fixed refusals: row 4 Persuade when the creature lacks player rules: 42469 "Only the main character can pick the persuade skill."; rows 2 Stealth and 7 Treat Injury on a droid (race 5): 42471 "Droids cannot allocate points to this skill." Then not enough points: 42464 "You do not have enough skill points to increase that skill." (checked before the cap); then at cap: 42178 "Class skills can have a maximum skill rank of <CUSTOM0> (current level + 3)." or 42179 "Cross-class skills can have a maximum skill rank of <CUSTOM0> ((current level + 3) / 2).", CUSTOM0 = the cap. Otherwise it buys one rank, updates the row's value, `REMAINING_SELECTIONS_LBL` and the cost/class labels, shows minus, and hides plus when the cap is reached | high |
| Minus (0x2f/0x3f) | refunds one rank (1 or 2 points) down to the value the panel opened with (0 in chargen) (`0x006f6370`, `0x00648eb0`); shows plus and hides minus at the floor | high |
| Focused row | set only when a row's `*_POINTS_BTN` gets event 0 (hover or keyboard focus, `0x006f4bf0`); the minus and plus buttons carry only a click handler that forwards 0x2f/0x30 to the panel. In `skchrgen.gui` minus (x 254-281), points (274-301) and plus (292-319) overlap and the later minus/plus win the hit test, so reaching a plus or minus from the label side crosses the row's points button and focuses that row, but moving straight down the plus or minus column (rows 33-35 px apart, gaps of 4-6 px) or entering from the description side does not: the click then acts on the previously focused row (med: static reading of the panel and the manager's hover rule, gui.md "Hover, focus and the active control"; needs a runtime check) | med |
| Class label | `CLASSSKL_LBL`: 38152 "Class Skill" or 38153 "Cross-class Skill" for the focused row; `COST_POINTS_LBL` = rank price (1 or 2); the focused row's label and value are hilighted (`0x006f4bf0`) | high |
| Descriptions | focused row's `LB_DESC` = the `skills.2da` `description` strref (244, 246, ... 258) | high |
| Recommended (event 0x2a) | in chargen: points to 0 and recomputed, every rank cleared, then the same auto-allocation as Quick Character (`0x006491a0`, C.4 step 5; order from `<code>_reco`), which for a creature with player rules may use every skill (`0x006f4e20`). In level-up it restores the points and ranks the panel opened with instead | high |
| Accept (0x27/0x2d) | if points remain: confirm box 41815 "You have not spent all of your skill points. These will be saved and you may spend them the next time you gain a level. Do you wish to continue?" (Yes proceeds, `0x006f4dc0`); with 0 left it proceeds without asking (`0x006f6980`). **The first level may end with unspent points** (kept in S `+0xae`, saved) | high |
| Back (0x28/0x2e) | in chargen resets all ranks and points to 0 and returns (`0x006f49d0`) | high |
| Disabled rows | a row is greyed (label and value in (0, 0.33, 0.49)) and its plus hidden when the creature lacks player rules and `skills.2da` `NPCCanUse` is 0, or it is a droid (race 5) and `DroidCanUse` is 0. "Player rules" (panel flag 2) is set whenever the level-up flag is clear, and in level-up only when the server creature's stats `+0x6c` is set and the party table's controlled NPC (`+0xf0`) is -1 (the same test as rules.md 6.1). So in chargen no row is greyed and Persuade is never refused; the droid refusals depend only on race, which is 6 in chargen | high |
| On open | shows tutorial popup 17 (`OnPanelAdded` override `0x006f49a0`) | high |

`skills.2da` `<code>_class` / `_reco` (class flag / recommended rank; a blank rank reads as 0, and a priority position that no skill ranks falls to the rank-0 skills in table order, so Persuade comes last for Soldier and Scout: rules.md 6.1):

| Skill | Soldier | Scout | Scoundrel |
|---|---|---|---|
| Computer Use | 0 / 6 | 1 / 1 | 0 / 7 |
| Demolitions | 1 / 3 | 1 / 2 | 1 / 2 |
| Stealth | 0 / 7 | 0 / 7 | 1 / 1 |
| Awareness | 1 / 2 | 1 / 4 | 1 / 4 |
| Persuade | 0 / - | 0 / - | 1 / 8 |
| Repair | 0 / 4 | 1 / 3 | 0 / 6 |
| Security | 0 / 5 | 0 / 6 | 1 / 3 |
| Treat Injury | 1 / 1 | 1 / 5 | 0 / 5 |

## H. Feats step (`ftchrgen`)

Controls: `LB_FEATS` (rows; events 0x1f8 row clicked -> `0x006f3420`, 0x1f9 pressed -> `0x006f3cf0`),
`LBL_NAME` (feat name), `LB_DESC`, `BTN_SELECT` (38455 "Add" in the file; the code shows 38455 + " " +
42487, "Add Feat", or 38456 + " " + 42487, "Remove Feat"; it sends 0x27 via `OnButtonAccept`),
`BTN_ACCEPT` (1580, via `OnButtonX`), `BTN_RECOMMENDED` (221, via Y), `BTN_BACK` (via `OnButtonCancel`),
`STD_SELECTIONS_REMAINING_LBL` 32062 "Remaining Feats" and `STD_REMAINING_SELECTIONS_LBL` (count),
`SUB_TITLE_LBL` 232 "Feats". Constructor arguments: level-up flag, "bonus feats" flag (both 0 here);
the level-up flag sets `MAIN_TITLE_LBL` to 1071 "Level Up", the bonus flag `SUB_TITLE_LBL` to 1316
"Bonus Feats". The panel opens focused on `LB_FEATS`. (high)

| Item | Value | Conf |
|---|---|---|
| Feats to pick at level 1 | `featgain.2da` `<code>_REG` for level 1 = 1 for Soldier, Scout, Scoundrel (and every Jedi and droid class); `_BON` is 0. `0x00648fe0` reads them from the last class slot's record (`+0x150 + level - 1` regular, `+0x13c + level - 1` bonus, levels 1-20). The regular pass counts only the regular picks, the bonus pass only the bonus ones. If the pass has nothing to pick, the constructor runs the accept handler at once (`0x006f44c0`), which opens the bonus pass if there is a bonus count, so a regular count of 0 offers the bonus pass instead and both 0 accept the panel by itself | high |
| On open (`0x006f3460`) | in chargen (neither flag) clears the creature's feat lists (`0x00648320`); remembers the feats known now; outside the bonus pass grants the feats of this level (`0x00649950`: the last class's table entries with `_List` 3 whose `_Granted` equals the class level, plus the race's feats at total level 1 with 0 XP; humans have none) and, if there were any, queues the "granted" popup (the `skillinfo` panel, caption 42258 "You have been granted the following feat(s) this level.") listing those not already known; then builds the list and the selectable set (`0x006f3290`). When the panel is added (`0x006f2f30`) it shows tutorial popup 18, and the granted popup after it (from the tutorial box's callback) or at once if the tutorial is not shown | high |
| Selectable set (`0x006f3290`) | every feat not known at opening, not granted this level, not chosen, that passes `0x0064a4c0`, the GUI's own copy of `CanSelectFeat` on the client stats (rules.md 6, 6.1): not known or pending; the prerequisites of `0x0064a2e0` (a class-table level not above the total level, `MinCharLevel` and `MinAttackBonus`, `MinSTR/DEX/INT/WIS` against the base scores, `prereqfeat1/2` and `orreqfeat` counting pending picks, `reqskill`); a class pool that fits; the same greedy slot matching. Each pool's size is passed as the level's count + 1 (0 stays 0), so the set does not shrink as picks are made: the pick limit is enforced by Select (42530) (med for that consequence) | high |
| What the list shows (`0x006ce570`) | one row per progression chain, built from `feat.2da` `prereqfeat1` / `prereqfeat2`, not `successor`: feats with a name are ordered by tier, 0 = no `prereqfeat1`, 1 = `prereqfeat1` only, 2 = both, by feat id within a tier (`0x006cd960`). Each tier-0 feat that the creature knows or the last class's feat table lists starts a row if it fits the pass's pool (regular: `_List` 0 or 1; bonus: 1 or 2; a feat the class grants and the creature knows skips this test). Its second and third cells are a known or class-listed feat whose `prereqfeat1` is the root: without `prereqfeat2` in cell 2, with it in cell 3 (e.g. Dueling / Advanced Dueling / Master Dueling, armour light / medium / heavy). A known feat outside the class table (or failing the pool test) gets no row. Each row is its own control, not the file's `PROTOITEM` (gui.md, "Chain rows"): three icon cells, the cells' feat.2da `icon`, arrows between them | high |
| Row states (`0x006f2d30`) | 0 selectable, 1 chosen in this panel, 2 granted this level, 3 already known, 4 unavailable (prerequisites); tested in the order 0, 1, 3, 2. `BTN_SELECT` text shows "Add Feat" (0, 4) or "Remove Feat" (1, 2, 3), in the normal colour (0, 0.66, 0.98) for 0 and 1 and the dim colour (0, 0.33, 0.49) for 2-4 (`0x006f2fb0`, re-applied each frame by the render override `0x006f2cc0`). The cells are styled per state (`0x006f30f0`: every cell style 3, then the known list 1, the chosen list 4, the selectable set 0, the granted list 2; styles in gui.md, "Chain rows"): selectable = icon at 0.25 alpha, no frame; chosen = green (0.28, 0.92, 0.11) frame; known and granted = green frame at 0.5 alpha; unavailable = icon and backing at 0.25, the arrow into the cell hidden, no frame. The focused cell's frame shows at full alpha and pulses, in the menu hilight colour (selectable), red-orange (0.74, 0.11, 0) (unavailable) or green (the rest) | high |
| Selecting / unselecting (Enter, A, `BTN_SELECT`, row press on the focused cell; `0x006f3c20`) | state 0 with picks left: choose it (remaining - 1, `0x006f37e0`; the set is topped up, so successors may become selectable); state 0 with none left: message 42530 "You have selected all your available feats for this level."; state 1: unchoose (remaining + 1, then every other pick whose prerequisite feats no longer hold is unchosen too, and the set is rebuilt; `0x006f3990`); state 2: 42183 "You gain this feat automatically at this level. You cannot deselect it."; state 3: 42182 "You cannot deselect a feat you already have."; state 4: 42184 "You do not yet have the necessary prerequisites to select this feat, or you have not yet selected the previous feat in this progression." | high |
| Recommended (event 0x2a) | drops the current picks, takes the recommended list (`0x0064a770`: C.4 step 3, regular or bonus by the mode), chooses them, and opens the popup with caption 42256 "The following feat(s) have been recommended." (`0x006f3a80`); there is no "picks remain" gate | high |
| Focus and description | one cell has the focus, not a row (`+0x1a14` cell, `+0x1a15` row of the row set at `+0x1a08`). On open the first row's first cell (`0x006cdd10`), after a pick the same feat (`0x006cdc00`). A row click (0x1f8, `0x006f3420`) focuses the cell under the pointer (`0x006cd1c0`: the first filled cell whose square holds it, else cell 0); a press (0x1f9, `0x006f3cf0`) selects or unselects only when it lands on the cell that already has the focus. Arrows (`0x006cdd80`): left/right move along the row (no wrap, not past the last filled cell, GUI sound 1); up/down move a row and wrap at both ends, then step left until the cell is filled. The focused cell gives `LBL_NAME` = feat `name` strref, `LB_DESC` = `description` strref (`0x006f2fb0`); Enter/A act on it (`0x006aba50` returns its feat) | high |
| Accept (event 0x29, X; `0x006f44c0`) | if picks remain **and** the selectable set is not empty: message 48215 "You have gained new feats. You must use "Add Feat" to select your new feats before continuing." and stay; otherwise add the chosen feats to the creature, pop; if this is not the bonus pass and the level has a bonus count, open a second feats panel in bonus mode; else level-up returns to its panel, chargen sets custom counter 4 (`0x006ef530`). So accept requires all picks used unless nothing is selectable | high |
| Back (0x28/0x2e; `0x006f2c70`) | pops without adding; the creature keeps the granted feats | high |
| The bonus pass | a second `ftchrgen` panel (`CSWGuiCharGenFeats` ctor with the bonus flag, added with flags 3 over the level-up list), opened by Accept of the regular pass after its picks were added to the creature (`0x005a7670`); sub title 1316 "Bonus Feats"; no feats granted and no granted popup; its rows, selectable set and pick count are the bonus pool's (`_List` 1 or 2, `featgain` `_BON`), and the regular picks show as known. Its Accept returns to level-up (`0x006ee5d0`), its Back leaves the regular picks on the creature without finishing the step. In the game's data every `featgain.2da` `*_bon` cell is 0, so the pass never opens unless a mod sets one | high |

For the three starting classes the granted level-1 feats (data, `_List` 3 and `_Granted` 1): Soldier
armour proficiency light/medium/heavy, Power Attack, Power Blast, blaster/blaster rifle/heavy/melee
weapon proficiency; Scout armour light/medium, Flurry, Implant Level 1, Rapid Shot, blaster/rifle/melee
proficiency; Scoundrel armour light, Critical Strike, Sniper Shot, Sneak Attack 1d6, Scoundrel's
Luck, blaster/rifle/melee proficiency.

## I. Force powers

Character generation never asks for Force powers. (high) The three offered classes (Soldier, Scout,
Scoundrel) are not Force classes (`classes.2da` `spellcaster` 0, `forcedie` 0); the Jedi classes
are chosen later in the story and entered through level-up. The custom step list is Portrait,
Attributes, Skills, Feats, Name, Play, and `CSWGuiCharGenPowers` (`0x006f2180`) has exactly one
caller, `CSWGuiLevelUpPanel::OnPowers` (`0x006ee350`); it loads `pwrlvlup.gui` for a creature given
by id, not a chargen creature.

The level-up Powers panel (`pwrlvlup`, `CSWGuiCharGenPowers`; all high, read from the decompile):

| Item | Value |
|---|---|
| Controls | `LB_POWERS` (0x1f8 row clicked → `0x006f1940`, 0x1f9 pressed → `0x006f2110`), `LBL_POWER` (name), `LB_DESC`, `SELECT_BTN` (X, 0x29), `RECOMMENDED_BTN` (Y, 0x2a), `ACCEPT_BTN` (0x27), `BACK_BTN` (0x28), `REMAINING_SELECTIONS_LBL` |
| Lists (ctor, `0x006f1990`) | known: every power in every class slot's known list (`0x006487d0` / `0x006495a0`), kept sorted by name; picks left `+0x19bc` = the level's count (`0x00649070`), and `+0x19bd` = count + 1; the selectable set (`0x006f1730`): every spell neither known, picked nor already in it that passes `0x00649b50` (CanLearnForcePower, rules.md, with count + 1 and the picks as pending), whose `+0x174` is not -2 and that has a name; sorted by name. With count + 1 the set does not empty as picks are made |
| List | chain rows from every Force power (`0x006ce0f0` with "every power"; gui.md "Chain rows"): rows by kind and line, friendly first, cells by `FORCEPRIORITY` |
| States (`0x006f1280`) | 2 known, 1 picked, 0 in the selectable set, else 3 |
| Styles (`0x006f15a0`) | every cell 3 (icon and backing faint, no arrow into it), the known 1 (green frame at half), the picks 4 (green frame), the selectable set 0 (faint icon); but Affect Mind (6) and Dominate Mind (14) get 3 when the panel's creature is not the PC (stats `+0x6c` bit 0, kept at `+0x19c0`). Then the focus: the first cell on opening (`0x006cdd10`), else the power shown last |
| Shown (`0x006f1460`) | `LBL_POWER` the spell's name, `LB_DESC` its `spelldesc`; `SELECT_BTN` 38455 or 38456 + " " + 42488 ("Add Power" for states 0 and 3, "Remove Power" for 1 and 2), in the menu text colour for 0 and 1 and the dim colour for 2 and 3 |
| Select (X, press on the focused cell; `0x006f2030`) | 0: 42470 "Only the main character can select this feat." for spells 6 and 14 on a non-PC, 42529 "You have selected all your available powers for this level." with no picks left, else pick it (`0x006f1c90`); 1: unpick (`0x006f1e40`); 2: 42185 "You cannot deselect a power you already have."; 3: 42186 "You do not yet have the necessary prerequisites to select this power, ..." |
| Recommended (`0x006f1f30`) | drops the picks, picks the auto-level list (`0x00649c30`), shows the list popup with caption 42257 "The following power(s) have been recommended." |
| Accept (`0x006f1130`) | with picks left and a non-empty selectable set: 48210 "You have gained new powers. You must use "Add Power" ..."; else each pick is added to the last class slot (`0x00649f90`), the panel pops and level-up marks the step (`0x006ee5d0`) |
| Arrows | to the row set whichever control has the focus (`0x006cdd80`), then the power is shown |

Ours: `lib/screens/lvl_powers.ctx` with `chargen/power_cells.ctx`. Not done: the Recommended
popup, and the known list's name order (only the selectable test uses the lists).

## J. Strrefs set for titles, subtitles and messages

"file" = comes from the `.gui` only; "code" = set by the constructor or a handler.

| Where | Tag | Strref / source |
|---|---|---|
| classsel | `LBL_CHAR_GEN` | 208 (file) |
| classsel | `LBL_INSTRUCTION` | 32160 "Choose your class" (file) |
| classsel | `LBL_CLASS` | 135 in file; code on hover: 646/647 + class 133/134/135 |
| classsel | `LBL_DESC` | code, table +4: 32109 / 32110 / 32111 |
| classsel | `BTN_BACK` | 1581 (file) |
| maincg | `MAIN_TITLE_LBL` | 208 (file) |
| maincg | `STR/DEX/CON/WIS/INT/CHA_LBL` | 211 / 212 / 213 / 214 / 215 / 216 (file) |
| maincg | `LBL_FORTITUDE/REFLEX/WILL` | 1056 / 1057 / 1058 (file) |
| qorcpnl | `QUICK_CHAR_BTN`, `CUST_CHAR_BTN`, `BTN_BACK` | 239, 240, 1581 (file); `LB_DESC` 241 / 242 (code) |
| quickpnl | steps | 231 Portrait, 234 Name, 235 Play (file); `BTN_BACK` 219 "Back", `BTN_CANCEL` 1581 "Cancel" (file) |
| custpnl | steps | 231, 209 Attributes, 233 Skills, 232 Feats, 234, 235 (file); `BTN_BACK` 219, `BTN_CANCEL` 1581 (file) |
| quick / custom | cancel question | 48541 "Are you sure you want to cancel?" (code) |
| portcust | `MAIN_TITLE_LBL`, `SUB_TITLE_LBL` | 208, 231 (file); `BTN_ACCEPT` 1580, `BTN_BACK` 1581 |
| name | titles | 208, 234 (file); `BTN_RANDOM` 48579, `END_BTN` 1580, `BTN_BACK` 1581; empty-name message 42360 (code) |
| abchrgen | titles | 208, 209; `SELECTIONS_REMAINING_LBL` 210; `DESC_LBL` 217; `COST_LBL` 218; `LBL_MODIFIER` 32112; `BTN_RECOMMENDED` 221; `BTN_ACCEPT` 1580; `BTN_BACK` 1581 (file); descriptions 222-227, messages 42180, 42181, 48217 (code); in level-up the main title is replaced by 1071 "Level Up" |
| skchrgen | titles | 208, 233; 210; 217; 218; 221; 1580; 1581 (file); skill names 243..257 odd; class label 38152 / 38153, messages 42464, 42178, 42179, 41815, 42469, 42471 (code); in level-up the main title is replaced by 1071 "Level Up" |
| ftchrgen | titles | 208, 232; `DESC_LBL` 217; `LBL_NAME` 217 (replaced by the focused feat's name); `STD_SELECTIONS_REMAINING_LBL` 32062; `BTN_SELECT` 38455; `BTN_RECOMMENDED` 221; `BTN_ACCEPT` 1580; `BTN_BACK` 1581 (file); 38456, 42487 "Feat", popups 42258 / 42256, messages 42530, 42183, 42182, 42184, 48215 (code); the bonus pass replaces the sub title with 1316 "Bonus Feats" and level-up the main title with 1071 "Level Up" (code) |

The remaining-count labels (`REMAINING_SELECTIONS_LBL`, `STD_REMAINING_SELECTIONS_LBL`) are empty in
the files and are filled by code with plain integers.

## K. Field map used by these panels

Creature (`CSWCCreature`, vtable `0x0074f5f8`) offsets: `+0x21c` pointer to the appearance object
(`CSWCCreatureAppearance`); the panels copy its first 0x3c bytes as a record, change it (appearance
id at +0x18) and apply it with `0x006134c0(creature, record, 3, 1)`; `+0x2f8` stats S; `+0x2fc`
soundset id (on the creature, not in S). Vtable `+0x70` GetName (`0x00617090`: first + " " + last),
`+0xec` SetPortrait(resref) (`0x0060d560`: S `+0x70`, when it differs), `+0xf4` SetPortraitId
(`0x0060d5c0` -> `0x00647b80`: S `+0x11c` = id and S `+0x70` = that row's resref).

| S offset | Meaning |
|---|---|
| `+0x14`, `+0x1c` | first name, last name (the Name step puts the whole name in the first) |
| `+0x24` | race id (6 human by default) |
| `+0x31` | gender (0 male, 1 female) |
| `+0x32` | class slot count (1 at chargen) |
| `+0xf0 + 0x20 * slot`, `+0xf1 + 0x20 * slot` | class id, class level of a slot |
| `+0x34..+0x39` | STR, DEX, CON, INT, WIS, CHA including the racial adjustment |
| `+0x3a..+0x3f` | the same six, the chosen base scores (what the screens show; the BIC writer saves `+0x34..` minus the race's adjustment, the same values) |
| `+0x40` | bonus byte added to defense and to the reflex save |
| `+0x48`, `+0x4c`, `+0x4e` | HP fields saved as `HitPoints`, `PregameCurrent`, `MaxHitPoints` (`+0x48` is added to the vitality label; 0 for a fresh creature) |
| `+0x50` | defense |
| `+0x58` | experience (BIC `Experience`) |
| `+0x5c`, `+0x5d`, `+0x5e` | fortitude, will, reflex |
| `+0x70` | portrait resref (BIC `Portrait`) |
| `+0x84`, `+0x88` | per-skill total and per-skill base ranks (8 bytes each) |
| `+0x8c` | appearance id |
| `+0xac` | attribute points left (30 fresh) |
| `+0xae` | skill points left |
| `+0xb0`, `+0xb4` | feat id list (u16) and its count |
| `+0x11c` | portrait id |

Class record (stride `0x1a0`, array at rules `+0xac`): `+0x54` hit die, `+0x56` skillpointbase,
`+0x13c..` bonus feats per level, `+0x150..` regular feats per level, `+0x164` skill table (12-byte
rows: skill id, class-skill flag at +4, recommended rank at +8), `+0x16c` feat table (8-byte rows: feat id
u16, granted level byte, pool mask byte (bit 0 regular, bit 1 bonus; from `_List` 0 -> 1, 1 -> 3,
2 -> 2, 3 -> 0), recommended rank u32; rules.md 6.1), `+0x17a` primary ability, `+0x17b..+0x180` STR, DEX, CON, INT, WIS, CHA recommended scores.

## Open

* The head the visual builder picks for the portrait list. The head code is `0x006964c0` (from
  `0x00697a20` for `MODELTYPE` "B"): the appearance record's byte `+0x34` if it is not 0xff, else
  `appearance.2da` `NORMALHEAD` when record `+0x30` is 0, else `BACKUPHEAD`; heads.2da `HEAD` gives
  the model. Which values `+0x30`/`+0x34` hold in the chargen creature's record was not traced, so
  the rule in D still rests on the data.
* Field `+0x40` of S (added to defense and reflex) and `+0x48` (added to vitality): zero for a
  fresh creature. A search finds `+0x48` written through the stats pointer only in `0x006655e0` and
  `0x00666667` (client update parsing, not followed) and no such write of `+0x40`.
* Whether the server adds anything to starting hit points beyond the level record (the BIC stores
  `HitPoints` 0 and `LvlStatHitDie`); the screen shows hit die + CON modifier.
