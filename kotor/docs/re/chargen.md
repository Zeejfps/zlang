# Character generation screens

How the original's new-game character creation behaves, screen by screen, so the screens can be
rebuilt faithfully. This is the detail page behind [gui.md](gui.md) section 10.2 (wiring) and
[rules.md](rules.md) (level-up record, skill points). All addresses are `swkotor.exe` (Steam,
unpacked); names marked "(ours)" are ours. Numbers were checked against the install's 2DA and TLK
data with `kotor/out/q.py`. Confidence is tagged high / med / low.

Conventions used below: **S** is the creature's stats block, the object at creature `+0x2f8`
(offsets in the field map, section K). UI order of the six abilities is STR, DEX, CON, WIS, INT,
CHA (the order of the strrefs 211..216 and of the buttons); the engine's *stats* order is STR, DEX,
CON, INT, WIS, CHA. Event codes are those of [gui.md](gui.md) (0x27 activate, 0x28 back, 0x29 X,
0x2a Y, 0x2d/0x2e gamepad accept/back, 0x2f/0x30 minus/plus).

## 0. The panels

| Panel (`.gui`) | Class | Ctor | Vtable | Size | How it is shown |
|---|---|---|---|---|---|
| `classsel` | `CSWGuiClassSelection` | `0x006dc3c0` | `0x00758020` | `0x1560` | from the main menu, full screen |
| `maincg` | `CSWGuiCharGenMain` | `0x006eb420` | `0x007592a8` | `0x22dc` | `AddPanel(3,1)`: full screen, modal |
| `qorcpnl` | `CSWGuiCharGenQuickOrCustom` | `0x006f09f0` | `0x00759710` | `0xd98` | `AddPanel(1,1)` over `maincg` |
| `quickpnl` | `CSWGuiCharGenQuickPanel` | `0x006f0390` | `0x00759668` | `0x1360` | same |
| `custpnl` | `CSWGuiCharGenCustomPanel` | `0x006ef730` | `0x007595e0` | `0x2188` | same |
| `portcust` | `CSWGuiCharGenPortrait` | `0x006f9430` | `0x00759ea8` | `0x1240` | `AddPanel(3,1)` full screen |
| `name` | `CSWGuiCharGenName` | `0x006f9e70` | `0x00759f38` | `0x9c4` | full screen |
| `abchrgen` | `CSWGuiCharGenAbilities` | `0x006f7600` | `0x00759c68` | `0x3df4` | full screen |
| `skchrgen` | `CSWGuiCharGenSkills` | `0x006f51d0` | `0x00759990` | `0x49d0` | full screen |
| `ftchrgen` | `CSWGuiCharGenFeats` | `0x006f3d60` | `0x007598b0` | `0x1a1c` | full screen |
| `pwrlvlup` | `CSWGuiCharGenPowers` | `0x006f2180` | `0x00759780` | | level-up only (section I) |

The three step panels (`qorcpnl`, `quickpnl`, `custpnl`) are created once, inside the `maincg`
constructor (`0x006eb420`), and swapped by `ShowStepPanel` (`0x006ea760`). The five sub-step
panels are created on demand by the step panel's button handlers and deleted when accepted or
cancelled. Every panel after class selection keeps the creature (`+0x64`) and its parent (`+0x68`;
class selection uses `+0x68` for the chosen creature). A sub-step panel also
keeps a mode byte (portrait `+0x123c`, name `+0x998`): 1 when opened from the quick panel, 2 from the
custom panel; it decides which parent function runs on accept (high).

The whole character is **one client creature object** (a `CSWCCreature`, 0x44c bytes, ctor
`0x00616a20`) made by the class-selection panel; every step edits it in place, and Play serialises
it (section C.5).

## A. Class selection (`CSWGuiClassSelection`)

Constructor `0x006dc3c0` (arg: start module name, always `END_M01AA` from `OnNewGame` `0x0067afb0`):
sets the loading-screen picture to the `classsel` row, mounts `RIMS:CHARGEN` if the resource exists,
loads `classsel.gui`, reads `portraits.2da`, builds six slots, then focuses slot 0. (high)

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
| voice | S/creature soundset = `soundset.2da` row from byte 2 (`0x0060b7c0`, creature `+0x2fc`) |
| portrait | a **random** `portraits.2da` row with `ForPC` = 1 and `Sex` = the slot's gender; stored with the creature's SetPortrait slot (vtable `+0xf4`), S `+0x11c` |
| appearance | the chosen row's `Appearance_L` / `AppearanceNumber` / `Appearance_S` by the class byte (0 / 1 / 2); stored in S `+0x8c` and in the visual info (creature `+0x21c`, field `+0x18`) |
| model | applied with `0x006134c0`, shown in a GUI 3D scene (`gui3D_room`, light `cgbody_light`, camera hook `camerahook`) inside `3D_MODEL<k+1>` |

The random draw is `rand() % remaining` over the list of eligible rows of that gender
(15 per gender: female rows 1-12 and 15-17, male rows 18-32), and the chosen row is **removed from
the list**, so the three models of one gender always show three different portraits (high). The
draw happens every time the panel is built, so the line-up differs per run.

### Hover and select

| Event | Handler | Behaviour |
|---|---|---|
| hover (event 0) | `OnHoverClass` `0x006dba70` | `LBL_CLASS` text = gender word (646 "Male" / 647 "Female") + " " + class name (133 Scout, 134 Soldier, 135 Scoundrel); `LBL_DESC` strref = table +4. (high) |
| 0x27, 0x2d | `OnSelectClass` `0x006db9b0` | only on press (value != 0); plays the click on 0x2d; stores the slot's creature at panel `+0x68`; builds `CSWGuiCharGenMain` with that creature and the panel itself; `AddPanel(3,1)` (high) |
| 0x28, 0x2e (Back) | `0x006dbd30` | marks the panel for deletion and shows the main menu; keys 0x35/0x36 are mapped to 0x2f/0x30 (high) |

`OnSelectClass` stores nothing else: **class, gender, appearance, portrait and voice all live in
the chosen creature**, and later panels read them from it. The other five creatures are simply
dropped. The panel's `OnPanelAdded` (`0x006db8f0`) empties the `GAMEINPROGRESS:` directory (the
temporary save area) and makes two input-setup calls for events 0x28 and 0x2e (purpose not
identified). Static texts from the `.gui`: `LBL_CHAR_GEN` 208
"CHARACTER GENERATION", `LBL_INSTRUCTION` 32160 "Choose your class", `BTN_BACK` 1581 "Cancel".
Initial `LBL_CLASS` strref in the file is 135 (replaced on first hover); the first hover happens
because slot 0 is the active control (`0x006dc3c0` end). (med)

## B. Main panel (`maincg`, `CSWGuiCharGenMain`)

### Labels the code binds

The constructor binds only these tags; everything else in `maincg.gui` (`OLD_*_LBL`, `NEW_VIT_LBL`,
`NEW_DEF_LBL`, the `*_ARROW_LBL`s, `OLD_LBL`, `NEW_LBL`, `LBL_LEVEL`, `LBL_LEVEL_VAL`) is **never
created in character generation** (they belong to the level-up panel, `CSWGuiLevelUpMain`).
(high)

| Tag | At start | Set later by | Value |
|---|---|---|---|
| `MAIN_TITLE_LBL` | 208 "CHARACTER GENERATION" (file) | never | |
| `LBL_NAME` | empty (`+0x22d4` = "") | name step accepted (`0x006eef70` -> `0x006ea9b0`) | the creature's full name, first + " " + last (last is empty, so just what was typed) |
| `LBL_CLASS` | class name of class slot 0, built at construction by `0x006ea910` (text before " (", so it may carry a trailing space) | re-set with the name | |
| `PORTRAIT_LBL` | the creature's portrait picture (border fill from the creature's portrait id) | portrait step accepted (`0x006ea9f0`) | `baseresref` of the portraits row |
| `MODEL_LBL` | 3D scene `gui3D_room`, light `charrec_light`, showing the creature | portrait accepted (`0x006ea9f0` re-applies the model) | |
| `STR_LBL`, `DEX_LBL`, `CON_LBL`, `WIS_LBL`, `INT_LBL`, `CHA_LBL` | 211, 212, 213, 214, 215, 216 (file) | never | the ability names |
| `STR_AB_LBL` .. `CHA_AB_LBL` | empty | `RefreshSummary` | the **chosen base score** as a plain integer (S `+0x3a..+0x3f`: STR, DEX, CON, INT, WIS, CHA). Not the modifier, and no racial adjustment |
| `LBL_DEF` | empty | `RefreshSummary` | defense, S `+0x50` |
| `LBL_VIT` | empty | `RefreshSummary` | hit die + CON modifier + S `+0x48` (0 at start) |
| `NEW_FORT_LBL`, `NEW_REFL_LBL`, `NEW_WILL_LBL` | empty | `RefreshSummary` | S `+0x5c`, `+0x5e`, `+0x5d` |
| `LBL_FORTITUDE`, `LBL_REFLEX`, `LBL_WILL` | 1056, 1057, 1058 (file) | never | "Fortitude", "Reflex", "Will" |
| `LBL_BEVEL_L/M/R` | decoration | | |

`RefreshSummary` (ours; `0x006eac30`) first recomputes the three saves (`0x00648b30` fortitude,
`0x00648be0` will, `0x00648c90` reflex), then the defense, then writes the eleven value labels. The
formulas (high): modifier of a score *s* = floor(*s*/2) - 5.

| Value | Formula |
|---|---|
| defense | 10 + DEX modifier (score S `+0x35`) + S `+0x40` (a bonus byte, 0 for a fresh character) + sum over class slots of `acbonus.2da[class column][class level]` (`CSWClass::GetACBonus` `0x005be770`); Scoundrel gets +2 at level 1, Soldier and Scout 0 |
| fortitude | CON modifier + class save bonus for the level (`0x005bccd0`) |
| reflex | DEX modifier + S `+0x40` + class save bonus (`0x005bccf0`) |
| will | WIS modifier + class save bonus (`0x005bcd10`) |
| vitality | class `hitdie` (class record `+0x54`) + CON modifier + S `+0x48` |

It is called (a) when the quick panel is shown (`0x006f0260`) and (b) in custom mode right after the
Attributes step is accepted (`0x006ef500`). Nothing else refreshes it: **in custom mode the value
labels stay blank until Attributes is accepted, and skills and feats never touch them.** (high)

`ResetCharacter` (`0x006eb010`, called by Cancel and by stepping back far enough) blanks the eleven
value labels and resets the creature: all six scores to 8, skill points and ranks to 0, feat list
emptied and then refilled with the level-1 granted feats (`0x00649950`), spell/power lists emptied.
It does not touch the name label, the portrait or the appearance. (high)

### Where the pieces sit

* `maincg.gui` is 640x480 at (0,0); `AddPanel(3,1)` makes it full screen (centred, backdrop around).
* Its `OnPanelAdded` (`0x006ea810`) adds the quick-or-custom panel on top (modal), so the screen
  after a class click is `maincg` + `qorcpnl`. Current step panel id is `+0x22c8`: 1 qorc, 2 quick,
  3 custom, 4 none. (high)
* The step panels are **not** full screen. Their own `.gui` extents are qorc (322,87) 273x281, quick
  and custom (322,87) 267x275, and the code adds panel flags 0x60 (centre inside a 640x480 frame
  both ways), so they sit at their file position over the middle right of `maincg` (x 322-595,
  y 87-362 or 368). What stays visible around them: the left half (portrait, model, name, scores,
  vitality, defense), `LBL_CLASS` above (351,64) and the three save rows below (y 358-408; their
  top edge is a few pixels under the panel). Added with `AddPanel(1,1)` (modal, not full
  screen). (high)
* The five sub-step panels are 640x480 full-screen menus (`AddPanel(3,1)`) and hide `maincg`.
  `maincg.Render` (`0x006eb340`) still advances the 3D model each frame while a step panel is up.
* `ShowStepPanel(n)` (`0x006ea760`): same n does nothing; otherwise pop the modal, remove the old
  step panel, `AddPanel(new,1,1)`. (high)
* Play: `Finish` (`0x006eb320`) = `Close` (`0x006ea830`: pop modals, mark the three step panels and
  itself for deletion) + `StartGame` (`0x006dbdf0`, section C.5). Back on the qorc panel is
  `Close` alone, which returns to class selection (still on screen below). (high)

## C. Quick or custom, the step lists, Back and Cancel

### C.1 Quick or custom (`qorcpnl`)

`QUICK_CHAR_BTN` (239 "Quick Character") -> `OnQuick` `0x006f0800` -> `ShowStepPanel(2)`.
`CUST_CHAR_BTN` (240 "Custom Character") -> `OnCustom` `0x006f0830` -> `ShowStepPanel(3)`.
Hovering fills `LB_DESC` with strref 241 (quick) or 242 (custom) through `0x006f0860`; the quick
button starts active. The texts really begin "Quick Help Text: ..." and "Custom Help Text: ...".
`BTN_BACK` (the file shows strref 1581 "Cancel") sends back (0x28/0x2e): `Close` on `maincg`, which
returns to class selection. (high)

### C.2 Steps

Both step panels hold a step counter (quick `+0x135c`, custom `+0x2184`), set by a "SetStep"
function (quick `0x006efc10`, custom `0x006eefd0`). **Only the button of the current step is
enabled and highlighted; earlier ones are greyed**, so the order is forced and a finished step can
only be revisited with Back. `BTN_BACK` is disabled (dim colour) at step 0.

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
| Back button / Esc / right click (0x28, 0x2e) at counter > 0 | counter - 1, the previous step is enabled again; nothing is undone | same, and when the new counter is 1 the character is reset (`0x006ef540`: `ResetCharacter`, 30 points back), so leaving Skills for Attributes wipes scores, skills and feats |
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
   ones already known, ones failing prerequisites (`0x0064a2e0`: min level, base attack, STR/DEX/INT/WIS
   minimums, prerequisite feats) and ones whose list kind does not fit a free slot. Derived from
   the data (not run): Soldier gets RAPID_SHOT (rank 1), Scout gets CRITICAL_STRIKE (rank 2; rank 1
   FLURRY is already granted), Scoundrel gets DUELING (rank 1). (med)
4. **Skill points** (`0x00648a00`, level 1): (INT modifier + skillpointbase / 2) x 4, where the
   modifier uses the chosen INT and the division is an integer shift, and the result is at least 4.
   Soldier 4, Scout 20, Scoundrel 24 (skillpointbase 2, 6, 8; INT 10, 14, 14).
5. **Skill ranks** (`0x006491a0`): walk the class's skills in rising `skills.2da` `<code>_reco`
   order and keep buying ranks (`0x00648d50`) until each is at its cap or the points run out.
   Derived result: Soldier Treat Injury 4; Scout Computer Use, Demolitions, Repair, Awareness,
   Treat Injury 4 each; Scoundrel Stealth, Demolitions, Security, Awareness 4 each, Treat Injury 2,
   Repair 2. (med)

The auto-build runs every time the quick panel is (re)added, e.g. after Cancel -> Quick again.

### C.5 Play

`StartGame` (`0x006dbdf0`), after `Close`: two client set-up calls I did not identify
(`0x005ee120`, in-game GUI `0x0062b410`), `CAppManager::CreateServer`, then
`0x006123e0` serialises the creature into a BIC-style GFF (`"BIC "`, `V2.0`, in `TEMP:`; fields
include the six base scores minus racial adjustment, `ClassList`/`LvlStatList` with the hit die,
`SkillList`, `SkillPoints`, `FeatList`, `Portrait`/`PortraitId`, `Appearance_Type`,
`SoundSetFile`, `FirstName`/`LastName`, `HitPoints`, `ForcePoints`; max HP is left to the server,
which builds it from the level record), sends the module-load message for `END_M01AA` as a
net-layer message addressed to id `0xfffffffd`, shows the loading screen and marks the
class-selection panel for deletion.
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
| Left / right | `BTN_ARRL`/0x2f/0x35/0x3f = previous, `BTN_ARRR`/0x30/0x36/0x40 = next; both **wrap** (`0x006f8fc0`, `0x006f8ff0`). Each press re-applies the appearance at once | high |
| Head and body | the portrait row's appearance row (`appearance.2da`) drives both: `NormalHead` -> `heads.2da` row (appearance 91 -> row 26 `PFHA01`, 136 -> row 41 `PMHA01`, one head per portrait A1..C5) and the body model `PFBAS`/`PMBAS` with the A/B/C skin texture. `BackUpHead` is empty for all 90 player appearances (rows 91-180), so it never matters here | med (head rule read from data and call chain; the head code in the visual builder was not read) |
| Per change | `0x006f8ad0`: SetPortrait(row), write the appearance into the visual info, re-apply (`0x006134c0`), play idle animation "pause1" on both animation slots; the panel plays "pause2" or "listen" at random every 1-4 s | med |
| Accept (0x27, 0x2d) | `0x006f8a20`: SetPortrait(row), S `+0x8c` = the list's appearance, a SetX call with an empty resref (vtable `+0xec`, purpose unknown), pop and delete the panel; then quick: refresh the main model and counter 1 (`0x006eff60`); custom: refresh the main model and counter 1 (`0x006ef4c0`) | high |
| Back (0x28, 0x2e) | `0x006f8f40`: put the saved original portrait (taken at panel creation, `+0x1238`) back, re-apply, pop; quick/custom just re-highlight the step | high |

The portrait step stores nothing but the portrait row id (S `+0x11c`) and the appearance id
(S `+0x8c` and the visual info); the gender, class build and voice are untouched.

## E. Name step (`name`)

| Item | Value | Conf |
|---|---|---|
| Titles | `MAIN_TITLE_LBL` 208, `SUB_TITLE_LBL` 234 "Name" (file) | high |
| Controls | `NAME_BOX_EDIT` (edit box), `BTN_RANDOM` (48579 "Random Name", sends Y = 0x2a), `END_BTN` (1580 "OK"), `BTN_BACK` (1581) | high |
| Initial text | when the panel is added (`0x006fa140`): the name already stored on `maincg` (`+0x22d4`) if any, else a **random name** | high |
| Random name | `0x006f9bf0` calls the LTR generator `0x007118c0` with race 6 (human), flags 6 = female first + last (`humanf`, `humanl`) for gender 1 or flags 5 = male first + last (`humanm`, `humanl`) otherwise, length argument 15 (handed to the generator; whether it limits each part or the sum was not checked); the two parts are joined by one space (see [../formats/ltr.md](../formats/ltr.md)). A generated name can therefore be longer than the edit box limit | high (resrefs, flags), low (length) |
| Max length | 18 characters: `0x006f9e70` writes 0x12 into the edit text's limit field (`+0x70`, i.e. panel `+0x380`), and `CSWGuiEditText::AppendText` (`0x004163a0`) only appends while the length is below it. The edit box ignores `_`, `/`, `\` and control codes (`0x004184f0`); Enter accepts, Esc is back | high |
| Accept (0x27, 0x2d, Enter) | `0x006f9cd0`: if the text is empty, message box strref 42360 "You must specify a name." (OK only) and the panel stays; otherwise strip trailing spaces, store it as the **first name** with an empty last name (`0x0060d600`: S `+0x14`, `+0x1c`), pop and delete the panel, update `LBL_NAME`/`LBL_CLASS` (`0x006eef70`), then quick counter 2 (`0x006eff80`) or custom counter 5 (`0x006ef4e0`) | high |
| Back | pops the panel without storing | high |
| Default name | there is none: an empty name is refused, and the box starts with a random one, so the Name step is always visited | high |

A name of only spaces passes the length test, is trimmed to empty and is stored as empty (the
loop strips it away); an original quirk, low confidence.

## F. Attributes step (`abchrgen`)

Panel state: remaining points `+0x3db8`, six current scores `+0x3dbc..+0x3dd0` in **UI order**
(STR, DEX, CON, WIS, INT, CHA), focused row `+0x3dec`, level-up flag `+0x3df0` (0 here), description
strrefs `+0x3da0..` = 222..227. (high)

| Item | Value | Conf |
|---|---|---|
| Titles | `MAIN_TITLE_LBL` 208, `SUB_TITLE_LBL` 209 "Attributes", `SELECTIONS_REMAINING_LBL` 210 "Remaining Points", `DESC_LBL` 217 "Description", `COST_LBL` 218 "Point Cost", `LBL_MODIFIER` 32112 "Modifier" (file) | high |
| Start | scores copied from the creature (8 each after a reset, 8 for a fresh creature); points = S `+0xac`, which a fresh creature has as 30 (`0x0064b2d0`) and every reset sets to 30 | high |
| Range | 8 to 18 | high |
| Cost to raise from *v* to *v*+1 | 1 for *v* below 14, 2 for 14 and 15, 3 for 16 and up (`0x006f8670`, `GetIncreaseCost` `0x006f6bb0`). Total from 8: 14 -> 6, 15 -> 8, 16 -> 10, 17 -> 13, 18 -> 16 | high |
| Refund when lowering *v* | the same price paid for *v*-1 -> *v* (`GetDecreaseRefund` `0x006f6b60`): 1 above 8 up to 14, 2 for 15 and 16, 3 for 17 and 18 | high |
| Plus | does nothing silently when points are 0 or the price exceeds the points; at 18 shows strref 42181 "Attribute scores cannot be raised above 18 during character generation."; the plus button is greyed at 18 and the minus at 8 | high |
| Minus | at 8 shows 42180 "Attribute scores cannot be reduced below 8." | high |
| Focus | hovering a `*_POINTS_BTN` (events 0/1, `OnHoverAbility` `0x006f70e0`) focuses that row; the +/- buttons (`OnButtonPrev/Next`, events 0x2f/0x30; keys 0x3f/0x40) act on the **focused** row | med |
| Labels per change | the row's `*_POINTS_BTN` text = its score; `REMAINING_SELECTIONS_LBL` = points left; on hover `COST_POINTS_LBL` = price of the next point for that row, `LBL_ABILITY_MOD` = modifier of its current score ("-" for 0, "+n" above, "-n" below), `LB_DESC` = strref 222 STR, 223 DEX, 224 CON, 225 WIS, 226 INT, 227 CHA. | high |
| Recommended (`BTN_RECOMMENDED`, strref 221; event 0x2a) | works **only while points remain** (`> 0`): sets the six scores to the class's `classes.2da` row (section C.4 values) and points to 0 (`0x006f7390`) | high |
| Accept (0x27) | if points > 0: message 48217 "You must spend all of your points. Click on the +/- arrows or use the arrow keys to assign points." and stay; else write the six scores to the creature (`0x006f6e70`: STR, CHA, INT, WIS, CON, DEX setters, S `+0x3a..` and the racial-adjusted `+0x34..`; DEX also updates defense), S `+0xac` = 0, pop, refresh the summary, custom counter 2 | high |
| Back | nothing written; S `+0xac` set back to 30; re-highlight | high |

The scores a human gets after Accept equal the chosen ones (racial adjustments of `racialtypes`
are applied on top inside S `+0x34..+0x39`, none for humans).

## G. Skills step (`skchrgen`)

| Item | Value | Conf |
|---|---|---|
| Titles | `SUB_TITLE_LBL` 233 "Skills", `SELECTIONS_REMAINING_LBL` 210, `COST_LBL` 218; skill names 243, 245, 247, 249, 251, 253, 255, 257 (file) | high |
| Rows (top to bottom = `skills.2da` rows) | 0 Computer Use, 1 Demolitions, 2 Stealth, 3 Awareness, 4 Persuade, 5 Repair, 6 Security, 7 Treat Injury | high |
| Points at level 1 | S `+0xae` = (INT modifier + `skillpointbase` / 2) x 4, at least 4 (`0x00648a00`; the later-level formula in rules.md is different: (modifier + base) / 2). The panel recomputes it every time it opens | high |
| Opening | in chargen the panel zeroes every rank first (so re-entering starts from 0) and recomputes the points | high |
| Cost per rank | class skill 1, cross-class 2 (`0x00647900`, `0x00648d50`); a skill is "class" when the class's skills table lists it as class (`skills.2da` `<code>_class`); all eight have `AllClassesCanUse` so every skill can be bought | high |
| Cap | class skill: total class level + 3 (4 at level 1); cross-class: (level + 3) / 2 rounded down (2 at level 1) | high |
| Plus (0x30/0x40) | buys one rank of the focused row (`0x006f6570`), updates the row text, `REMAINING_SELECTIONS_LBL`, and cost label. Errors as message boxes: not enough points 42464 "You do not have enough skill points to increase that skill."; at cap 42178 "Class skills can have a maximum skill rank of <CUSTOM0> (current level + 3)." or 42179 "Cross-class skills ... ((current level + 3) / 2)." | high |
| Minus (0x2f/0x3f) | refunds one rank (1 or 2 points) down to the value the panel opened with (0 in chargen) (`0x006f6370`) | high |
| Class label | `CLASSSKL_LBL`: 38152 "Class Skill" or 38153 "Cross-class Skill" for the focused row; `COST_POINTS_LBL` = rank price (1 or 2) | high |
| Descriptions | focused row's `LB_DESC` = the `skills.2da` `description` strref (244, 246, ... 258) | high |
| Recommended (event 0x2a) | clears ranks, recomputes points and runs the same auto-allocation as Quick Character (C.4 step 5; order from `<code>_reco`) | high |
| Accept | if points remain: confirm box 41815 "You have not spent all of your skill points. These will be saved and you may spend them the next time you gain a level. Do you wish to continue?" (Yes proceeds, `0x006f4dc0`); with 0 left it proceeds without asking. **The first level may end with unspent points** (kept in S `+0xae`, saved) | high |
| Back | resets all ranks and points to 0 and returns | high |
| Disabled rows | in chargen none are greyed (the rule that greys NPC-unusable skills needs the level-up flag); Persuade and (for droids) Stealth and Treat Injury would be refused with 42469 / 42471 outside chargen | med |
| On open | shows tutorial popup 17 (`0x006f49a0`) | med |

`skills.2da` `<code>_class` / `_reco` (class flag / recommended rank, blank = not recommended):

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
`LBL_NAME` (feat name), `LB_DESC`, `BTN_SELECT` (38455 "Add", toggles text with 38456 "Remove"),
`BTN_ACCEPT` (1580, via `OnButtonX`), `BTN_RECOMMENDED` (221, via Y), `BTN_BACK`,
`STD_SELECTIONS_REMAINING_LBL` 32062 "Remaining Feats" and `STD_REMAINING_SELECTIONS_LBL` (count),
`SUB_TITLE_LBL` 232 "Feats". Constructor arguments: level-up flag, "bonus feats" flag (both 0 here).
(high)

| Item | Value | Conf |
|---|---|---|
| Feats to pick at level 1 | `featgain.2da` `<code>_REG` for level 1 = 1 for Soldier, Scout, Scoundrel (and every Jedi class); `_BON` is 0. `0x00648fe0` reads them from the class record (`+0x150 + level - 1` regular, `+0x13c + level - 1` bonus). If the regular count is 0 the bonus pass is offered instead; if both are 0 the panel accepts itself | high |
| On open | clears the creature's feats, re-grants the level-1 granted feats, and shows the "granted" popup (the `skillinfo` panel, caption 42258 "You have been granted the following feat(s) this level.") (`0x006f3460`); then builds the selectable set from every feat that passes the prerequisite check (`0x006f3290`) | high |
| What the list shows | feats of the class's list (`feat.2da` `<code>_List`: 0 regular only, 1 regular and bonus, 2 bonus only, 3 granted-only, 4 not for this class; regular picks use 0 and 1) plus feats the creature already has, ordered in progression chains by `successor` (root feats first, `0x006ce570`) | med |
| Row states (`0x006f2d30`) | 0 selectable, 1 chosen in this panel, 2 granted this level, 3 already known, 4 unavailable (prerequisites). States 2-4 are drawn dim (colour (0, 0.33, 0.49) against the normal (0, 0.66, 0.98)); `BTN_SELECT` text shows "Add Feat" (0, 4) or "Remove Feat" (1, 2, 3) with the dim colour for 2-4 | med |
| Selecting / unselecting (Enter, A, `BTN_SELECT`, row press on the focused row; `0x006f3c20`) | state 0 with picks left: choose it (remaining - 1, successors may become selectable); state 0 with none left: message 42530 "You have selected all your available feats for this level."; state 1: unchoose (remaining + 1, dependants that lose their prerequisite are dropped too, `0x006f3990`); state 2: 42183 "You gain this feat automatically at this level. You cannot deselect it."; state 3: 42182 "You cannot deselect a feat you already have."; state 4: 42184 "You do not yet have the necessary prerequisites ..." | high |
| Recommended (event 0x2a) | drops the current picks, takes the recommended list (`0x0064a770`: C.4 step 3, regular or bonus by the mode), chooses them, and opens the popup with caption 42256 "The following feat(s) have been recommended." (`0x006f3a80`) | high |
| Description | focused row: `LBL_NAME` = feat `name` strref, `LB_DESC` = `description` strref (`0x006f2fb0`) | high |
| Accept (event 0x29, X) | if picks remain **and** the selectable set is not empty: message 48215 "You have gained new feats. You must use "Add Feat" to select your new feats before continuing." and stay; otherwise add the chosen feats to the creature, pop; if a bonus count exists, open a second feats panel in bonus mode; else custom counter 4. So accept requires all picks used unless nothing is selectable | high |
| Back | pops without adding; the creature keeps the granted feats | high |

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
caller, `CSWGuiLevelUpPanel::OnPowers` (`0x006ee350`).

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
| abchrgen | titles | 208, 209; `SELECTIONS_REMAINING_LBL` 210; `DESC_LBL` 217; `COST_LBL` 218; `LBL_MODIFIER` 32112; `BTN_RECOMMENDED` 221; `BTN_ACCEPT` 1580; `BTN_BACK` 1581 (file); descriptions 222-227, messages 42180, 42181, 48217 (code) |
| skchrgen | titles | 208, 233; 210; 217; 218; 221; 1580; 1581 (file); skill names 243..257 odd; class label 38152 / 38153, messages 42464, 42178, 42179, 41815, 42469, 42471 (code); in level-up the main title is replaced by 1071 "Level Up" |
| ftchrgen | titles | 208, 232; `DESC_LBL` 217; `STD_SELECTIONS_REMAINING_LBL` 32062; `BTN_SELECT` 38455; `BTN_RECOMMENDED` 221; `BTN_ACCEPT` 1580 (file); 38456, 42487 "Feat", popups 42258 / 42256, messages 42530, 42183, 42182, 42184, 48215 (code); the bonus pass replaces the sub title with 1316 "Bonus Feats" (code) |

The remaining-count labels (`REMAINING_SELECTIONS_LBL`, `STD_REMAINING_SELECTIONS_LBL`) are empty in
the files and are filled by code with plain integers.

## K. Field map used by these panels

Creature (`CSWCCreature`) offsets: `+0x21c` visual info (appearance id at +0x18), `+0x2f8` stats S,
`+0x2fc` soundset id, vtable `+0xf4` SetPortrait, `+0x70` GetName.

| S offset | Meaning |
|---|---|
| `+0x14`, `+0x1c` | first name, last name (the Name step puts the whole name in the first) |
| `+0x24` | race id (6 human by default) |
| `+0x31` | gender (0 male, 1 female) |
| `+0x32` | class slot count (1 at chargen) |
| `+0xf0 + 0x20 * slot`, `+0xf1 + 0x20 * slot` | class id, class level of a slot |
| `+0x34..+0x39` | STR, DEX, CON, INT, WIS, CHA including the racial adjustment |
| `+0x3a..+0x3f` | the same six, the chosen base scores (what the screens show and save) |
| `+0x40` | bonus byte added to defense and to the reflex save |
| `+0x48`, `+0x4c`, `+0x4e` | HP fields saved as `HitPoints`, `PregameCurrent`, `MaxHitPoints` (`+0x48` is added to the vitality label; 0 for a fresh creature) |
| `+0x50` | defense |
| `+0x5c`, `+0x5d`, `+0x5e` | fortitude, will, reflex |
| `+0x84`, `+0x88` | per-skill total and per-skill base ranks (8 bytes each) |
| `+0x8c` | appearance id |
| `+0xac` | attribute points left (30 fresh) |
| `+0xae` | skill points left |
| `+0xb0`, `+0xb4` | feat id list (u16) and its count |
| `+0x11c` | portrait id |

Class record (stride `0x1a0`, array at rules `+0xac`): `+0x54` hit die, `+0x56` skillpointbase,
`+0x13c..` bonus feats per level, `+0x150..` regular feats per level, `+0x164` skill table (12-byte
rows, rank at +8), `+0x16c` feat table (8-byte rows: feat id, granted level, list code, recommended
rank), `+0x17a` primary ability, `+0x17b..+0x180` STR, DEX, CON, INT, WIS, CHA recommended scores.

## Open

* Which row the +/- buttons act on when the mouse is on a non-focused row's buttons (only the
  `*_POINTS_BTN` controls carry hover handlers; the minus and plus controls forward to the
  panel). Real behaviour might refocus on hover; test or read the manager's hover code. (low)
* The visual builder's head choice (`CreateBTypeBody` `0x00697ce0`, `0x00697a20`) was not read; the
  head rule in D comes from the data and the call chain.
* Vtable `+0xec` on the creature, called with an empty resref when a portrait is accepted.
* Field `+0x40` of S (added to defense and reflex) and `+0x48` (added to vitality): zero for a
  fresh creature; no writer was looked for.
* Whether the server adds anything to starting hit points beyond the level record (the BIC stores
  `HitPoints` 0 and `LvlStatHitDie`); the screen shows hit die + CON modifier.
* The exact module-load message format (`"%c%s.%s %s"` at `0x00752fe4`) and the BIC's file name in
  `TEMP:` (`0x006123e0` was skimmed, 4.3 KB).
* Per-run randomness: class selection uses the C `rand()` seeded elsewhere; it only needs to look
  random.
* Feat list order and indentation (progression chains) were derived from `0x006ce570` and the
  `successor` columns, not rendered.
