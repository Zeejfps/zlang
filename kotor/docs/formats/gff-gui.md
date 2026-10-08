# GFF schema: GUI layouts (GUI)

The 91 `.gui` files (84 in `data/gui.bif`, plus 7 in `patch.erf`: new versions of `abilities`, `character`, `equip`, `inventory` and `mainmenu`, and two new ones, `mipc212x10` and `tooltip12x10`) describe every screen: the
top-level struct is the root panel, and `CONTROLS` lists its controls (flat: nesting is expressed
by `Obj_Parent`/`Obj_ParentID`, not by structure). Conventions, path notation and columns:
[gff-schemas.md](gff-schemas.md). BioWare published nothing on this format; everything below is
read from the data and marked *(inferred)* where it is interpretation rather than observation.

## Model

- **Design resolution.** Coordinates are pixels in the GUI's design size: the root `EXTENT`
  is 640x480 for 49 files; a few screens exist per resolution (`mainmenu8x6`, `mainmenu16x12`,
  `mipc28x6`, `tooltip16x12`, ...: the suffix is the resolution in hundreds, 8x6 = 800x600), and
  smaller roots are dialog boxes. Centring is not decided by the file: the code centres a panel
  through its panel flags (full-screen panels, and bits 0x20/0x40 against 640x480) and
  `CenterOnScreen` ([re/render-gui.md](../re/render-gui.md), GUI).
- **Control types** (`CONTROLTYPE`), with the sub-structs each carries in the data:

  | Type | Control | Sub-structs |
  |---|---|---|
  | 2 | panel (the root) | BORDER, EXTENT |
  | 4 | label | BORDER, EXTENT, TEXT |
  | 5 | list-row prototype / highlightable label | BORDER, EXTENT, HILIGHT, TEXT |
  | 6 | button | BORDER, EXTENT, HILIGHT, MOVETO, TEXT |
  | 7 | check box / toggle | + SELECTED, HILIGHTSELECTED, ISSELECTED |
  | 8 | slider | BORDER, EXTENT, HILIGHT, MOVETO, THUMB, CURVALUE, MAXVALUE |
  | 9 | scroll bar (only inside a list box) | BORDER, EXTENT, DIR, THUMB |
  | 10 | progress bar | BORDER, EXTENT, PROGRESS, CURVALUE, MAXVALUE, STARTFROMLEFT |
  | 11 | list box | BORDER, EXTENT, PROTOITEM, SCROLLBAR, PADDING, LOOPING, LEFTSCROLLBAR |

  The type names are *(inferred)* from these sub-structs and from the tags (`BTN_*`, `LBL_*`,
  `LB_*`, `PB_*`, `SLI_*`); the numbering matches what the modding community uses.
- **Border struct** (`BORDER`, `HILIGHT` on mouse-over, `SELECTED`, `HILIGHTSELECTED`,
  `PROGRESS`): `CORNER` and `EDGE` textures drawn `DIMENSION` pixels thick around the extent,
  `FILL` texture inside, inset by `INNEROFFSET`; `FILLSTYLE` 2 (2089 of 2099 borders) stretches
  the fill, 0 draws none, 1 occurs 5 times *(inferred: tiled)*; `COLOR` tints (RGB 0..1, -1 = no
  tint); `PULSING` makes it pulse.
- **Text struct**: `TEXT` (literal) or `STRREF` (dialog.tlk; 0xFFFFFFFF = use `TEXT`), `FONT`
  (a font texture: a TPC/TGA with a TXI giving the glyph metrics), `COLOR`, `PULSING` and
  `ALIGNMENT`, a bit set: horizontal 1 left, 2 centre, 4 right; vertical 8 top, 16 middle,
  32 bottom (values seen 9, 10, 12, 17, 18, 20, 34) *(inferred from the values)*.
- **Image struct** (`DIR`, `THUMB` of scroll bars and sliders): `IMAGE` texture, `ALIGNMENT`,
  `DRAWSTYLE`, `FLIPSTYLE`, `ROTATE`, `ROTATESTYLE` (all 0 or 18 in the data).
- **Navigation**: `MOVETO` gives the control `ID` to move to with up/down/left/right
  (keyboard/gamepad); -1 = none.

<!-- gff-table GUI -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `CONTROLS` | List | all | 0..120 entries; struct id 0 | The panel's controls, in draw order *(inferred)*; struct id 0. |
| `CONTROLS/CONTROLTYPE` | INT | 90 | 4..11 (7 values) | Control type (table above). |
| `CONTROLS/ID` | INT | 90 | 0..139 | Control id, unique in the file (referenced by `MOVETO` and `Obj_ParentID`). |
| `CONTROLS/Obj_Locked` | BYTE | 90 | 0, 1 | Editor lock flag; never read by the game (the string is not in the executable, [re/render-gui.md](../re/render-gui.md)). |
| `CONTROLS/Obj_Parent` | CExoString | 90 | e.g. `TGuiPanel`, `MAIN_PANEL`, `MAIN_PNL` | Tag of the parent (the panel's tag or a control's). Never read by the game: parents come from `Obj_ParentID` ([re/render-gui.md](../re/render-gui.md)). |
| `CONTROLS/TAG` | CExoString | 90 | e.g. `LB_DESC`, `MAIN_TITLE_LBL`, `SUB_TITLE_LBL` | Control tag; the game code finds controls by tag. |
| `CONTROLS/Obj_ParentID` | INT | 83 | -1..116 | Id of the parent control; -1 = the panel. |
| `CONTROLS/EXTENT` | Struct | 90 | struct id 0, 14 | Position and size. |
| `CONTROLS/EXTENT.LEFT` | INT | 90 | -7..1572 | Left edge, design pixels (relative to the panel origin). |
| `CONTROLS/EXTENT.TOP` | INT | 90 | -16..1184 | Top edge, design pixels. |
| `CONTROLS/EXTENT.WIDTH` | INT | 90 | 4..1594 | Width, design pixels. |
| `CONTROLS/EXTENT.HEIGHT` | INT | 90 | 6..933 | Height, design pixels. |
| `CONTROLS/BORDER` | Struct | 90 | struct id 0, 14 | Normal-state border struct. |
| `CONTROLS/BORDER.CORNER` | ResRef | 90 | 2158 empty; e.g. `boxline1`, `bluefill`, `clearborder` | Corner texture. |
| `CONTROLS/BORDER.EDGE` | ResRef | 90 | 2154 empty; e.g. `boxline2`, `bluefill`, `clearborder` | Edge texture. |
| `CONTROLS/BORDER.FILL` | ResRef | 90 | 1090 empty; e.g. `i_empathy`, `lbl_leftplus`, `lbl_rightminus` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/BORDER.FILLSTYLE` | INT | 90 | 0, 1, 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/BORDER.DIMENSION` | INT | 90 | 0..32 (7 values) | Border thickness in pixels. |
| `CONTROLS/BORDER.INNEROFFSET` | INT | 86 | -5..14 (8 values) | Inset of the fill from the extent. |
| `CONTROLS/BORDER.COLOR` | Vector | 85 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/BORDER.PULSING` | BYTE | 86 | 0, 1, 2 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/TEXT` | Struct | 89 | struct id 0, 14 | Text struct. |
| `CONTROLS/TEXT.ALIGNMENT` | INT | 89 | 9..34 (7 values) | Alignment bits (see above). |
| `CONTROLS/TEXT.COLOR` | Vector | 88 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/TEXT.FONT` | ResRef | 89 | e.g. `dialogfont16x16`, `fnt_console`, `dialogfont10x10` | Font texture resref. |
| `CONTROLS/TEXT.STRREF` | DWORD | 89 | 135..4294967295 | dialog.tlk strref; 0xFFFFFFFF = use `TEXT`. |
| `CONTROLS/TEXT.PULSING` | BYTE | 86 | 0, 1 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/TEXT.TEXT` | CExoString | 64 | 1530 empty; e.g. `0`, `18`, `+10` | Literal text (placeholders and numbers; the game usually fills it at run time). |
| `CONTROLS/HILIGHT` | Struct | 72 | struct id 0 | Border struct used while the mouse is over the control. |
| `CONTROLS/HILIGHT.CORNER` | ResRef | 72 | 698 empty; e.g. `boxline3`, `yellowfill`, `blackfill` | Corner texture. |
| `CONTROLS/HILIGHT.EDGE` | ResRef | 72 | 698 empty; e.g. `boxline4`, `yellowfill`, `blackfill` | Edge texture. |
| `CONTROLS/HILIGHT.FILL` | ResRef | 72 | 379 empty; e.g. `lbl_miarrow02`, `lbl_mibox02`, `lbl_cg_circ2` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/HILIGHT.FILLSTYLE` | INT | 72 | 1, 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/HILIGHT.DIMENSION` | INT | 72 | 0, 1, 2, 4, 6, 16 | Border thickness in pixels. |
| `CONTROLS/HILIGHT.INNEROFFSET` | INT | 72 | -4..14 (7 values) | Inset of the fill from the extent. |
| `CONTROLS/HILIGHT.COLOR` | Vector | 71 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/HILIGHT.PULSING` | BYTE | 72 | 0, 1, 2 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/MOVETO` | Struct | 70 | struct id 0 | Navigation targets. |
| `CONTROLS/MOVETO.DOWN` | INT | 70 | -1..35 (27 values) | Id to move to on down; -1 none. |
| `CONTROLS/MOVETO.LEFT` | INT | 70 | -1..138 (31 values) | Id on left. |
| `CONTROLS/MOVETO.RIGHT` | INT | 70 | -1..138 (31 values) | Id on right. |
| `CONTROLS/MOVETO.UP` | INT | 70 | -1..35 (27 values) | Id on up. |
| `CONTROLS/COLOR` | Vector | 49 | ('-1', '-1', '-1'); ('0', '0', '0') | List box: item colour; (-1,-1,-1) = default *(inferred)*. |
| `CONTROLS/LOOPING` | BYTE | 49 | 0, 1 | List box: selection wraps around *(inferred)*. |
| `CONTROLS/PADDING` | INT | 49 | 0, 1, 2, 3, 4, 5 | List box: pixels between rows *(inferred)*. |
| `CONTROLS/PROTOITEM` | Struct | 49 | struct id 0, 14 | List box: prototype control cloned for every row (type 4 to 7). |
| `CONTROLS/PROTOITEM.CONTROLTYPE` | INT | 49 | 4, 5, 6, 7 | Type of the row control. |
| `CONTROLS/PROTOITEM.Obj_Parent` | CExoString | 49 | e.g. `LB_DESC`, `LB_ITEMS`, `LB_MODULES` | Tag of the owning list box. |
| `CONTROLS/PROTOITEM.TAG` | CExoString | 49 | e.g. `PROTOITEM` | Always `PROTOITEM`. |
| `CONTROLS/PROTOITEM.Obj_ParentID` | INT | 47 | 0..39 (21 values) | Id of the owning list box. |
| `CONTROLS/PROTOITEM.EXTENT` | Struct | 49 | struct id 0, 14 | Size of one row (left/top relative to the list box). |
| `CONTROLS/PROTOITEM.EXTENT.LEFT` | INT | 49 | 6..1317 (38 values) | Left edge, design pixels (relative to the panel origin). |
| `CONTROLS/PROTOITEM.EXTENT.TOP` | INT | 49 | 0..256 (35 values) | Top edge, design pixels. |
| `CONTROLS/PROTOITEM.EXTENT.WIDTH` | INT | 49 | 225..528 (29 values) | Width, design pixels. |
| `CONTROLS/PROTOITEM.EXTENT.HEIGHT` | INT | 49 | 16..392 (19 values) | Height, design pixels. |
| `CONTROLS/PROTOITEM.BORDER` | Struct | 49 | struct id 0, 14 | Row border. |
| `CONTROLS/PROTOITEM.BORDER.CORNER` | ResRef | 49 | 37 empty; e.g. `border2`, `invent1`, `border2c` | Corner texture. |
| `CONTROLS/PROTOITEM.BORDER.EDGE` | ResRef | 49 | 37 empty; e.g. `border1`, `invent2`, `border1c` | Edge texture. |
| `CONTROLS/PROTOITEM.BORDER.FILL` | ResRef | 49 | 85 empty; e.g. `i_checkbox01`, `scr_def_nn` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/PROTOITEM.BORDER.FILLSTYLE` | INT | 49 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/PROTOITEM.BORDER.DIMENSION` | INT | 49 | 0, 1, 4, 6, 14 | Border thickness in pixels. |
| `CONTROLS/PROTOITEM.BORDER.INNEROFFSET` | INT | 47 | 0, 9, 10 | Inset of the fill from the extent. |
| `CONTROLS/PROTOITEM.BORDER.COLOR` | Vector | 47 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROTOITEM.BORDER.PULSING` | BYTE | 47 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/PROTOITEM.TEXT` | Struct | 49 | struct id 0, 14 | Row text. |
| `CONTROLS/PROTOITEM.TEXT.ALIGNMENT` | INT | 49 | 9, 10, 17, 18 | Alignment bits (see above). |
| `CONTROLS/PROTOITEM.TEXT.COLOR` | Vector | 49 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROTOITEM.TEXT.FONT` | ResRef | 49 | e.g. `fnt_d16x16`, `dialogfont16x16`, `dialogfont10x10` | Font texture resref. |
| `CONTROLS/PROTOITEM.TEXT.TEXT` | CExoString | 49 | 74 empty; e.g. `(Unitialized)`, `Debug Option`, `FEAT` | Literal text (placeholders and numbers; the game usually fills it at run time). |
| `CONTROLS/PROTOITEM.TEXT.STRREF` | DWORD | 49 | 4294967295 | dialog.tlk strref; 0xFFFFFFFF = use `TEXT`. |
| `CONTROLS/PROTOITEM.TEXT.PULSING` | BYTE | 47 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/PROTOITEM.HILIGHT` | Struct | 33 | struct id 0, 14 | Row border when highlighted. |
| `CONTROLS/PROTOITEM.HILIGHT.CORNER` | ResRef | 33 | 2 empty; e.g. `border2`, `border2a`, `invent3` | Corner texture. |
| `CONTROLS/PROTOITEM.HILIGHT.EDGE` | ResRef | 33 | 2 empty; e.g. `border1`, `border1a`, `invent4` | Edge texture. |
| `CONTROLS/PROTOITEM.HILIGHT.FILL` | ResRef | 33 | 53 empty; e.g. `i_checkbox01`, `scr_def_sn` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/PROTOITEM.HILIGHT.FILLSTYLE` | INT | 33 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/PROTOITEM.HILIGHT.DIMENSION` | INT | 33 | 0, 1, 2, 4, 6, 14 | Border thickness in pixels. |
| `CONTROLS/PROTOITEM.HILIGHT.INNEROFFSET` | INT | 32 | 0, 9, 10 | Inset of the fill from the extent. |
| `CONTROLS/PROTOITEM.HILIGHT.COLOR` | Vector | 32 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROTOITEM.HILIGHT.PULSING` | BYTE | 32 | 0, 1 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/PROTOITEM.SELECTED` | Struct | 6 | struct id 0 | Row border when selected. |
| `CONTROLS/PROTOITEM.SELECTED.CORNER` | ResRef | 6 | 1 empty; e.g. `border2`, `boxline7` | Corner texture. |
| `CONTROLS/PROTOITEM.SELECTED.EDGE` | ResRef | 6 | 1 empty; e.g. `border1`, `boxline8` | Edge texture. |
| `CONTROLS/PROTOITEM.SELECTED.FILL` | ResRef | 6 | 24 empty; e.g. `i_checkbox02`, `scr_def_nc` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/PROTOITEM.SELECTED.FILLSTYLE` | INT | 6 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/PROTOITEM.SELECTED.DIMENSION` | INT | 6 | 0, 4, 6 | Border thickness in pixels. |
| `CONTROLS/PROTOITEM.SELECTED.INNEROFFSET` | INT | 6 | 0, 9 | Inset of the fill from the extent. |
| `CONTROLS/PROTOITEM.SELECTED.COLOR` | Vector | 6 | ('0', '1', '0'); ('0', '0.549', '0.8706'); ('0.902', '1', '0.902') | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROTOITEM.SELECTED.PULSING` | BYTE | 6 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED` | Struct | 6 | struct id 0 | Row border when selected and highlighted. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.CORNER` | ResRef | 6 | 1 empty; e.g. `border2`, `boxline5` | Corner texture. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.EDGE` | ResRef | 6 | 1 empty; e.g. `border1`, `boxline6` | Edge texture. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.FILL` | ResRef | 6 | 24 empty; e.g. `i_checkbox02`, `scr_def_sc` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.FILLSTYLE` | INT | 6 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.DIMENSION` | INT | 6 | 0, 4, 6 | Border thickness in pixels. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.INNEROFFSET` | INT | 6 | 0, 9 | Inset of the fill from the extent. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.COLOR` | Vector | 6 | ('0', '1', '0'); ('0.9804', '1', '0'); ('0.9216', '1', '0.9216') | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROTOITEM.HILIGHTSELECTED.PULSING` | BYTE | 6 | 0, 1 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/PROTOITEM.ISSELECTED` | BYTE | 6 | 0 | Initial selected state; 0. |
| `CONTROLS/SCROLLBAR` | Struct | 49 | struct id 0, 14 | List box: its scroll bar (a type-9 control). |
| `CONTROLS/SCROLLBAR.CONTROLTYPE` | INT | 49 | 9 | Always 9. |
| `CONTROLS/SCROLLBAR.Obj_Parent` | CExoString | 49 | e.g. `LB_DESC`, `LB_ITEMS`, `LB_MODULES` | Tag of the owning list box. |
| `CONTROLS/SCROLLBAR.TAG` | CExoString | 49 | e.g. `SCROLLBAR` | Always `SCROLLBAR`. |
| `CONTROLS/SCROLLBAR.Obj_ParentID` | INT | 47 | 0..39 (22 values) | Id of the owning list box. |
| `CONTROLS/SCROLLBAR.EXTENT` | Struct | 49 | struct id 0, 14 | Scroll bar rectangle. |
| `CONTROLS/SCROLLBAR.EXTENT.LEFT` | INT | 49 | 0..1299 (29 values) | Left edge, design pixels (relative to the panel origin). |
| `CONTROLS/SCROLLBAR.EXTENT.TOP` | INT | 49 | 0..252 (33 values) | Top edge, design pixels. |
| `CONTROLS/SCROLLBAR.EXTENT.WIDTH` | INT | 49 | 0, 10, 15, 16, 25 | Width, design pixels. |
| `CONTROLS/SCROLLBAR.EXTENT.HEIGHT` | INT | 49 | 20..472 (33 values) | Height, design pixels. |
| `CONTROLS/SCROLLBAR.BORDER` | Struct | 49 | struct id 0, 14 | Scroll bar border. |
| `CONTROLS/SCROLLBAR.BORDER.CORNER` | ResRef | 49 | 8 empty; e.g. `border2`, `border2a` | Corner texture. |
| `CONTROLS/SCROLLBAR.BORDER.EDGE` | ResRef | 49 | 8 empty; e.g. `border1`, `border1a` | Edge texture. |
| `CONTROLS/SCROLLBAR.BORDER.FILL` | ResRef | 49 | always empty | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/SCROLLBAR.BORDER.FILLSTYLE` | INT | 49 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/SCROLLBAR.BORDER.DIMENSION` | INT | 49 | 0, 4 | Border thickness in pixels. |
| `CONTROLS/SCROLLBAR.BORDER.INNEROFFSET` | INT | 47 | 0 | Inset of the fill from the extent. |
| `CONTROLS/SCROLLBAR.BORDER.COLOR` | Vector | 47 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/SCROLLBAR.BORDER.PULSING` | BYTE | 47 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/SCROLLBAR.DIR` | Struct | 49 | struct id 0, 14 | Arrow image struct. Never read by the game (no loader reads `DIR`; [re/render-gui.md](../re/render-gui.md)). |
| `CONTROLS/SCROLLBAR.DIR.IMAGE` | ResRef | 49 | 2 empty; e.g. `uparrow` | Image texture. |
| `CONTROLS/SCROLLBAR.DIR.DRAWSTYLE` | INT | 49 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.DIR.FLIPSTYLE` | INT | 49 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.DIR.ROTATE` | FLOAT | 48 | 0 | Rotation; always 0. |
| `CONTROLS/SCROLLBAR.DIR.ALIGNMENT` | INT | 49 | 18 | Always 18 (centred). |
| `CONTROLS/SCROLLBAR.DIR.ROTATESTYLE` | INT | 1 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.DRAWMODE` | BYTE | 48 | 0, 1 | 0 or 1; read by the scroll-bar loader (`0x0041bcd0`, [re/render-gui.md](../re/render-gui.md)). |
| `CONTROLS/SCROLLBAR.MAXVALUE` | INT | 49 | 1, 5, 10, 99 | Scroll range. |
| `CONTROLS/SCROLLBAR.VISIBLEVALUE` | INT | 49 | 1, 4, 5, 50, 99 | Rows visible at once *(inferred)*. |
| `CONTROLS/SCROLLBAR.THUMB` | Struct | 49 | struct id 0, 14 | Thumb image struct. |
| `CONTROLS/SCROLLBAR.THUMB.IMAGE` | ResRef | 49 | 2 empty; e.g. `bluefill`, `blendbar` | Image texture. |
| `CONTROLS/SCROLLBAR.THUMB.DRAWSTYLE` | INT | 49 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.THUMB.FLIPSTYLE` | INT | 49 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.THUMB.ROTATE` | FLOAT | 48 | 0 | Rotation; always 0. |
| `CONTROLS/SCROLLBAR.THUMB.ALIGNMENT` | INT | 49 | 18 | Always 18 (centred). |
| `CONTROLS/SCROLLBAR.THUMB.ROTATESTYLE` | INT | 1 | 0 | Always 0. |
| `CONTROLS/SCROLLBAR.CURVALUE` | INT | 49 | 0, 1 | Initial position. |
| `CONTROLS/LEFTSCROLLBAR` | BYTE | 49 | 0, 1 | List box: 1 if the scroll bar is on the left. |
| `CONTROLS/MAXVALUE` | INT | 17 | 99, 100 | Slider or progress bar maximum. |
| `CONTROLS/THUMB` | Struct | 5 | struct id 0 | Slider: thumb image struct. |
| `CONTROLS/THUMB.IMAGE` | ResRef | 5 | e.g. `lbl_optslidera`, `lbl_alignarr` | Image texture. |
| `CONTROLS/THUMB.DRAWSTYLE` | INT | 5 | 0 | Always 0. |
| `CONTROLS/THUMB.FLIPSTYLE` | INT | 5 | 0 | Always 0. |
| `CONTROLS/THUMB.ROTATE` | FLOAT | 5 | 0 | Rotation; always 0. |
| `CONTROLS/THUMB.ALIGNMENT` | INT | 5 | 18 | Always 18 (centred). |
| `CONTROLS/CURVALUE` | INT | 17 | 0, 50, 99, 100 | Slider or progress bar value. |
| `CONTROLS/Obj_Layer` | INT | 1 | 1, 2 | Editor layer; one file *(unknown)*. |
| `CONTROLS/PROGRESS` | Struct | 12 | struct id 0 | Border struct whose fill shows the progress. |
| `CONTROLS/PROGRESS.CORNER` | ResRef | 12 | always empty | Corner texture. |
| `CONTROLS/PROGRESS.EDGE` | ResRef | 12 | always empty | Edge texture. |
| `CONTROLS/PROGRESS.FILL` | ResRef | 12 | e.g. `bluefill`, `redfill`, `lbl_force` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/PROGRESS.FILLSTYLE` | INT | 12 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/PROGRESS.DIMENSION` | INT | 12 | 0 | Border thickness in pixels. |
| `CONTROLS/PROGRESS.INNEROFFSET` | INT | 12 | 0 | Inset of the fill from the extent. |
| `CONTROLS/PROGRESS.COLOR` | Vector | 12 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/PROGRESS.PULSING` | BYTE | 12 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/STARTFROMLEFT` | BYTE | 12 | 0, 1 | Progress bar: 1 if it fills from the left. |
| `CONTROLS/SELECTED` | Struct | 16 | struct id 0 | Border struct when selected (check box on). |
| `CONTROLS/SELECTED.CORNER` | ResRef | 16 | 41 empty; e.g. `border2c` | Corner texture. |
| `CONTROLS/SELECTED.EDGE` | ResRef | 16 | 41 empty; e.g. `border1c` | Edge texture. |
| `CONTROLS/SELECTED.FILL` | ResRef | 16 | 9 empty; e.g. `i_checkbox02`, `i_solo3`, `i_pause3` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/SELECTED.FILLSTYLE` | INT | 16 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/SELECTED.DIMENSION` | INT | 16 | 0, 2, 4 | Border thickness in pixels. |
| `CONTROLS/SELECTED.INNEROFFSET` | INT | 16 | 0 | Inset of the fill from the extent. |
| `CONTROLS/SELECTED.COLOR` | Vector | 16 | ('1', '1', '1'); ('0.9648', '1', '0.9648'); ('0.9961', '1', '0.9961') | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/SELECTED.PULSING` | BYTE | 16 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/HILIGHTSELECTED` | Struct | 16 | struct id 0 | Border struct when selected and highlighted. |
| `CONTROLS/HILIGHTSELECTED.CORNER` | ResRef | 16 | 41 empty; e.g. `border2c` | Corner texture. |
| `CONTROLS/HILIGHTSELECTED.EDGE` | ResRef | 16 | 32 empty; e.g. `yellowfill`, `border1c` | Edge texture. |
| `CONTROLS/HILIGHTSELECTED.FILL` | ResRef | 16 | 9 empty; e.g. `i_checkbox02`, `i_solo2`, `i_pause2` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `CONTROLS/HILIGHTSELECTED.FILLSTYLE` | INT | 16 | 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `CONTROLS/HILIGHTSELECTED.DIMENSION` | INT | 16 | 0, 1, 4 | Border thickness in pixels. |
| `CONTROLS/HILIGHTSELECTED.INNEROFFSET` | INT | 16 | -4, 0, 4 | Inset of the fill from the extent. |
| `CONTROLS/HILIGHTSELECTED.COLOR` | Vector | 16 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `CONTROLS/HILIGHTSELECTED.PULSING` | BYTE | 16 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `CONTROLS/ISSELECTED` | BYTE | 16 | 0 | Check box: initial state; 0. |
| `CONTROLS/PARENTID` | INT | 1 | -1..7 (9 values) | Same role as `Obj_ParentID` in one file, but never read by the game ([re/render-gui.md](../re/render-gui.md)). |
| `CONTROLTYPE` | INT | all | 2 | Root panel: always 2. The root's value is not read ([re/render-gui.md](../re/render-gui.md)). |
| `Obj_Locked` | BYTE | all | 0, 1 | Editor lock flag. |
| `TAG` | CExoString | all | e.g. `TGuiPanel`, `MAIN_PNL`, `CUST_PNL` | Panel tag. The root's `TAG` is not read ([re/render-gui.md](../re/render-gui.md)). |
| `Obj_ParentID` | INT | 83 | -1 | Always -1. |
| `EXTENT` | Struct | all | struct id 0, 14 | Panel rectangle: its size is the design resolution or dialog size. |
| `EXTENT.LEFT` | INT | all | 0..322 (13 values) | Left edge, design pixels (relative to the panel origin). |
| `EXTENT.TOP` | INT | all | 0..378 (14 values) | Top edge, design pixels. |
| `EXTENT.WIDTH` | INT | all | 251..1600 (19 values) | Width, design pixels. |
| `EXTENT.HEIGHT` | INT | all | 70..1200 (21 values) | Height, design pixels. |
| `ALPHA` | FLOAT | 90 | 1 | Panel opacity; always 1. |
| `BORDER` | Struct | all | struct id 0, 14 | Panel background border struct. |
| `BORDER.CORNER` | ResRef | all | 81 empty; e.g. `confirm1`, `confirm5`, `border2` | Corner texture. |
| `BORDER.EDGE` | ResRef | all | 81 empty; e.g. `confirm2`, `confirm6`, `border1` | Edge texture. |
| `BORDER.FILL` | ResRef | all | 26 empty; e.g. `lbl_optback`, `lbl_back01`, `dialog2` | Fill texture (resources missing for a few unused ones such as `lbl_live02`). |
| `BORDER.FILLSTYLE` | INT | all | 0, 2 | 0 none, 1 tiled *(inferred)*, 2 stretched. |
| `BORDER.DIMENSION` | INT | all | 0, 4, 16 | Border thickness in pixels. |
| `BORDER.INNEROFFSET` | INT | 86 | 0 | Inset of the fill from the extent. |
| `BORDER.COLOR` | Vector | 85 | varies | Tint, RGB 0..1; (-1,-1,-1) = none. |
| `BORDER.PULSING` | BYTE | 86 | 0 | 1 or 2 if the element pulses *(inferred)*. |
| `COLOR` | Vector | 90 | ('0', '0', '0'); ('-1', '-1', '-1'); ('0.25', '0.25', '0.25') | Panel colour; (-1,-1,-1) = none. |
| `Obj_Layer` | INT | 1 | 0 | Editor layer; one file. |
<!-- /gff-table -->
