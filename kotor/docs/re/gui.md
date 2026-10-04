# The GUI system of swkotor.exe: behaviour

How the original game's 2D interface behaves: where panels go on the screen, how borders, text and
every control type are drawn from the `.gui` fields, how the font metrics turn into glyph quads,
how input reaches a control (modal stack, hover, focus, keyboard and gamepad navigation, mouse
capture, the wheel), and when the GUI eats a click instead of the world. The second half is a
catalogue of every panel the game uses. Addresses are for the Steam `swkotor.exe` after SteamStub
removal (see [README.md](README.md)). Every claim carries a confidence: **high** = read in the
code, **med** = role clear, detail inferred, **low** = plausible. Names are ours (the binary has
no RTTI for these classes); proposals for every address below are in
`kotor/re/proposals/gui.tsv` (git-ignored, merged into [names.tsv](names.tsv) by the lead).

The structural facts (manager and panel field maps, vtables, the `.gui` loading steps, the
CONTROLTYPE → class table, the control classes and their constructors) are in
[render-gui.md](render-gui.md#gui); this page summarises them in §1 and goes deeper. The `.gui`
file format is [../formats/gff-gui.md](../formats/gff-gui.md); font TXI keys are in
[../formats/txi.md](../formats/txi.md) and [../formats/txi-render.md](../formats/txi-render.md).
Neighbouring pages, written in parallel: [app.md](app.md) (input devices, key map),
[gameloop.md](gameloop.md) (frame, pause, module load, load-progress phases),
[dialogue.md](dialogue.md) (conversation flow and cameras; the dialogue panels' controls are
here), [party-items-saves.md](party-items-saves.md) (inventory, equipment, stores, save/load
rules; the panels that show them are here), [rules.md](rules.md) (point-buy, skills, feats,
powers, level-up rules; the character-generation panels are here), [movement.md](movement.md)
(the world cursor choice and targeting), [combat.md](combat.md), [actions.md](actions.md).

Throughout, "event" means the integer passed to a panel's or control's `HandleInputEvent`
(§7), and "GUI pixels" are screen pixels: **the GUI is never scaled** (§2).

## 1. The system in brief

- One `CSWGuiManager` (`g_pGuiManager` 0x007a39f4, owned by the client at +0x274) holds a list
  of panels (+0x88) and a stack of modal panels (+0x94). Each frame the client runs
  `ProcessInput` (0x006227e0, feeds events and the cursor), `CSWGuiManager::Update` (0x0040ce70)
  and `CSWGuiManager::Render` (0x0040cc50). (high)
- A panel (`CSWGuiPanel`, ctor 0x0040b570, vtable 0x0073e010) is one `.gui` file: its
  constructor builds its member controls in place, calls `LoadGui` (0x0040a680) on a resref,
  binds each member to the GFF struct whose `TAG` matches with `InitControl` (0x0040b930),
  calls `FinishLoading` (0x0040b8f0), then registers callbacks with
  `CSWGuiControl::SetEventHandler` (0x0041ab20). Controls the code does not bind are never
  created: a tag in the file that no constructor asks for is ignored. (high)
- Controls are stored in the panel's array **at the index given by their `ID`** (controls with
  `ID` -1 are bound but not stored; the panel draws them itself). The array index is the draw
  order (ascending) and the reverse hit-test order (§8). (high)
- Control classes and the CONTROLTYPE map: render-gui.md. Label 4, proto item 5, button 6,
  check box 7, slider 8, scroll bar 9, progress bar 10, list box 11; the edit box is created by
  code only (save name, character name). (high)
- Panels and controls share one virtual layout; the slots used below: panel slot 13 Render,
  14 Update, 15 HandleInputEvent, 16 HitTest, 18 OnAdded, 19 OnRemoved, 20–24 "send event
  0x27..0x2b to myself", 25 resolution tag, 26 OnResize; control slot 1 SetExtent, 3 SetHover
  (with sound), 6/7 left down/up, 9/33 right up/down, 14 Render, 15 HandleInputEvent,
  16 SetHilighted, 17 HitTest, 18 LoadFromGFF, 19–30 type queries ("as selectable", "as
  label", "as proto item", "as button", "as check box", "as slider", "as progress bar", "as scroll
  bar", "as list box", "as edit box"), 31 SetFocus, 32 IsSelectable, 34 SetEnabled, 35 Relayout,
  36 ShowTooltip. (high for the slots read below, med for the rest)

## 2. Screen placement and resolution

### No scaling

`.gui` coordinates are screen pixels. A control's `EXTENT` is relative to its panel's origin; the
panel's own `EXTENT` gives its size and its position before the placement rules below. Nothing is
ever stretched to the window: a 640x480 panel on a 1600x1200 screen covers 640x480 pixels in the
middle. Bigger screens get dedicated `.gui` files for the few screens that must fill them (HUD,
tooltip), and a resolution-named backdrop around the full-screen menus. (high)

The renderer works in nested viewports (`Render_PushViewport` 0x004592f0 / `Render_PopViewport`
0x00459580): each panel pushes a GL viewport the size of its screen rectangle and draws in
coordinates relative to it; a list box pushes another one for its rows. Within a viewport GUI y
grows downward; the GL viewport is placed at `screenHeight - y - height`. (high)

### Supported resolutions and the resolution tag

`CSWGuiManager::GetResolutionName` (0x0040a3e0) maps the screen size to a tag:
`1024x768`, `1280x960`, `1280x1024`, `1600x1200`; **any other size gives `800x600`**. A panel's
resolution tag (`GetResolutionTag` 0x0040a900, slot 25) is that name plus one of five suffixes
picked by the panel's byte +0x48, held in five static strings at 0x007a3d50 (filled at start-up
by 0x0073ad80): 0 `back`, 1 `store`, 2 `pazaak`, 3 `map`, 4 `comp`. The result names a backdrop
texture: `1024x768back`, `800x600store`, `1600x1200pazaak` ... (all in `swpc_tex_gui.erf`; the
`1280x1024*` set is in `patch.erf`; there is also a `*load` set used by the loading screen,
§10.1). (high)

Resolution-specific `.gui` files use the `WxH` suffix in hundreds of pixels (`mipc28x6`,
`tooltip12x10`, `mainmenu16x12`); the HUD's PC files carry a `2` (`mipc2…`) to tell them from the
unused older set. There is no `_p` / `_x` (PC / Xbox) naming in the PC data or code: the only GUI
texture ending in `_p` is `lbl_align_p`, an ordinary picture, and no string in the exe builds
such a name. (high)

### Where a panel goes

Panel flags (+0x44) involved (high unless noted):

| Bit | Meaning |
|---|---|
| 0x001 | "placed in screen space": hit tests use the computed screen rectangle; set by `CenterOnScreen` (0x0040a600) and by constructors that position themselves (HUD, main menu, credits) |
| 0x004 | active: updated and drawn |
| 0x008 | full-screen menu: centred on screen, draws the backdrop, hides panels below it (§8); set by `AddPanel` flag 2 |
| 0x010 | set by `AddPanel` flag 4; such panels are not counted in manager +0x71 (purpose low) |
| 0x020 / 0x040 | centre horizontally / vertically as if the panel were inside a 640x480 frame |
| 0x080 | visible this frame (recomputed by `UpdateTopPanel` 0x0040acc0) |
| 0x200 / 0x400 | remove / remove and delete after this frame's draw (both bits = value 2 → delete) |

The screen rectangle (`GetScreenExtent` 0x0040aa00) is the panel extent, then:
1. if flag 0x08: `x += (screenW - w) / 2`, `y += (screenH - h) / 2` (integer division), and stop;
2. else if 0x20: `x += (screenW - 640) / 2`; if 0x40: `y += (screenH - 480) / 2`.

Hit tests and "mouse position inside the panel" (`HitTest` 0x0040b690,
`GetLocalMousePosition` 0x0040ba20) use that rectangle only when flag 0x01 is set; otherwise
they subtract `((screenW - 640) / 2, (screenH - 480) / 2)` from the cursor and compare with the
raw extent, i.e. they assume the panel sits in a centred 640x480 frame. The two agree for every
combination the game uses:

- **Full-screen menus** (inventory, character, options ...: 640x480 files at 0,0) are added with
  `AddPanel(panel, 3, 1)`: modal + full screen. They are centred, and the backdrop fills the rest.
- **Dialog boxes** (message box, save name, skill info, container, ...): the constructor calls
  `CenterOnScreen` (x = (screenW - w) / 2, y = (screenH - h) / 2, flag 0x01), then
  `AddPanel(panel, 1, 1)` (modal only). Their `.gui` LEFT/TOP are ignored.
- **The main menu** (`mainmenu`, 800x600 in `patch.erf`, 640x480 in `gui.bif`): flag 0x01 in
  `InitPanel`, added with flag 2: centred, with the `WxHback` backdrop around it.
- **The loading screen and the character-generation steps** set 0x20|0x40 (centred 640x480
  frame) and draw their own full-screen background label (§10).
- **The HUD** (`CSWGuiMainInterface`) loads a `.gui` made for the exact resolution and sets flag
  0x01 at its file's 0,0: `mipc28x6` (800x600 and every unsupported size), `mipc210x7`
  (1024x768), `mipc212x9` (1280x960), `mipc212x10` (1280x1024, `patch.erf`), `mipc216x12`
  (1600x1200). A 1280-wide mode with another height loads **no** file (the code falls through):
  a reimplementation should map it to the closest file. The files `maininterface`, `mi8x6`,
  `mipc8x6`, `mipc10x7`, `mipc12x9`, `mipc16x12` are not referenced by the code (Xbox / older
  layouts). (high)
- **The tooltip** picks `tooltip16X12` (1600 wide), `tooltip12X9` (1280x960), `tooltip12x10`
  (1280x1024), `tooltip10X8` (1024), `tooltip8X6` (800), else `tooltip6X4`, by screen size
  (constructor 0x006277c0); it is placed at the cursor (§10.3). (high)
- The `mainmenu8x6`, `mainmenu10x7`, `mainmenu12x9`, `mainmenu16x12` files are not referenced
  (the code only asks for `mainmenu`). (high)

### The backdrop

When the panel list contains at least one panel with flag 0x08 (counter at manager +0x70),
`Render` first draws a full-screen black viewport and, inside it, a label stretched over the
whole screen whose fill texture is the manager's current tag (+0x74). `UpdateTopPanel` sets that
tag from the topmost visible full-screen panel's `GetResolutionTag`, so the store shows
`WxHstore`, pazaak `WxHpazaak`, the galaxy map `WxHmap`, everything else `WxHback`
(0x0040ae80). (high)

### Changing resolution

`CClientExoAppInternal::ChangeVideoMode` (0x005f1830, our name) sets `g_nScreenWidth/Height`,
calls `SetVideoMode`, then `CSWGuiManager::SetResolution(w, h)` (0x0040be70). That stores the
size (+0x6c/+0x6e), calls every panel's `OnResize` (slot 26; the base version calls every
control's slot 35, which re-applies the font suffix, §5) and the tooltip's, drops the cached
backdrop label, and lets the in-game GUI resize the HUD and its eight menus (0x0062b490). The
client then re-runs the main menu's `InitPanel` if it is up, deletes and re-creates the loading
screen, and calls `CGuiInGame::RecreateResolutionPanels` (0x0062f5f0), which deletes and
re-creates the HUD, the conversation panel and the message box (each picks its file again) and
re-centres the dialog-style panels (debug panels, container, skill info, the second message box
...). (high)

A reimplementation that wants to scale the GUI to modern resolutions can treat the whole of
§2 as "layout at the nearest supported resolution, then scale the result"; the behaviour above is
what to reproduce at the original sizes.

## 3. Drawing: the 2D pass

`CSWGuiManager::Render` (0x0040cc50) runs once per frame after the 3D scene (order: high):

1. advance the two pulse clocks (below);
2. if any full-screen panel exists: the backdrop (§2);
3. every active panel of the list that is not on the modal stack, in list order;
4. the modal stack, bottom to top;
5. the dragged object (+0x54, inventory drag), in a full-screen viewport;
6. unless a movie plays: the tooltip panel if showing, and the tooltip timer (§9);
7. the software cursor (+0x20, §9);
8. panels marked 0x200/0x400 are removed (and deleted).

`CSWGuiPanel::Render` (0x0040b760) draws only if the panel is visible (0x80), has a positive size
and lies entirely inside the screen (x, y ≥ 0, x + w ≤ screenW, y + h ≤ screenH); otherwise it
draws nothing at all. It pushes a viewport over the panel's screen rectangle — filled with the
panel `COLOR` when that is not (-1,-1,-1), at the panel `ALPHA` — then draws the panel's
`BORDER`, then every control in the array whose visible flag (control +0x44 bit 1) is set, in
index order. (high)

**Quads.** Every textured rectangle goes through one batch (0x0045b290): a quad at pixel
(x, y, w, h) inside the current viewport is converted to viewport fractions; texture v = 1 is
the top edge (textures are stored bottom-up); optional flips (bits 2–3 of a style word) and
rotations of 0/90/180/270 degrees permute the texture corners; a colour of (-1,-1,-1) means
"untinted". The batch flushes on a texture, colour-mode or alpha change. (high)

**Alpha.** Each viewport carries an alpha (the panel's `ALPHA`, 1 for nested viewports); the
alpha a quad is drawn with is the product of all pushed viewport alphas times the element's own
alpha. (high)

**Pulsing.** Two global clocks run in `Render`, each a triangle wave with a 0.75 s half period:
the *border pulse* goes 0.4 → 1.0 → 0.4 ... (0x00414a50, value at 0x0078d3d4) and the *list
pulse* 0.2 → 1.0 (0x00418300, value at 0x0078d3e4). Elements with `PULSING` take the clock value
as their alpha (§4, §5). (high)

## 4. Borders and fill styles (`CSWGuiBorder`)

A border struct (`BORDER`, `HILIGHT`, `SELECTED`, `HILIGHTSELECTED`, `PROGRESS`, and the panel
root `BORDER`) is loaded by 0x004153e0: `CORNER`, `EDGE`, `FILL` resrefs (textures), `FILLSTYLE`
(two bits), `DIMENSION`, `INNEROFFSET`, `COLOR` (default (1,1,1)) and `PULSING`. A panel root
without `BORDER` may give `BACKGROUND` (a fill resref) instead. Alpha starts at 1. (high)

`PULSING` bits: bit 0 pulses the corners and edges, bit 1 the fill (so 1 = frame, 2 = fill,
3 = both); a pulsing part uses the border-pulse clock as its alpha. (high)

Drawing (`CSWGuiBorder::Draw` 0x004168c0, high unless noted):

1. **Thickness.** If `DIMENSION` > 0, corners are `DIMENSION` x `DIMENSION` and edges are
   `DIMENSION` thick. If `DIMENSION` is 0 and both corner and edge textures exist, the corner
   size is the corner texture's own width x height and the edge thickness and segment length
   come from the edge texture.
2. **Corners**, only if a corner texture exists: one texture, drawn four times: top-left as is,
   bottom-left rotated 90°, bottom-right 180°, top-right 270° (the art is the top-left corner).
3. **Edges**, only if an edge texture exists: the gap between the corners along the top is
   `w - 2*corner`. It is cut into `n = gap / segment` segments (if that is 0 but the gap is at
   least half a segment, one segment); the leftover pixels are spread so the segments exactly
   fill the gap, the first `leftover mod n` segments one pixel wider. Top segments are drawn
   unrotated, bottom ones rotated 180°, left ones 90°, right ones 270° (the art is the top edge).
   If the extent is too small for any segment, the corners each take half of the extent (an odd
   size shifts the far corners by one pixel).
4. **Fill**, only if a fill texture exists, inside the corners (the whole extent when there is no
   corner texture, whatever `DIMENSION` says), tinted by `COLOR`, with the fill alpha:
   - `FILLSTYLE` 2 — stretched: one quad over the area (2,089 of 2,099 borders in the data);
   - `FILLSTYLE` 0 — tiled: like the edges, the area is cut into whole tiles of the texture size
     in both directions, each stretched slightly so they fill the area exactly (0x004155b0);
     an area smaller than one tile gets a single quad of the area's size;
   - `FILLSTYLE` 1 — centred: the texture at its natural size, centred; a dimension where the
     texture is larger than the area is squeezed to the area (0x004157f0).
5. `COLOR` tints corners, edges and fill alike; (-1,-1,-1) and the default (1,1,1) both mean
   untinted.

**`INNEROFFSET`** does not affect the border drawing. It only moves the *text* rectangle of
labels, buttons and list rows: the text area is the border's inner rectangle (inside the
corners; if the extent is too small, a zero-size rectangle at the centre) grown outward by
`INNEROFFSET` vertically and by `min(INNEROFFSET, thickness)` horizontally (0x00415240; the
asymmetry is as read, med). Negative values shrink it.

## 5. Text and fonts

### The text struct

`CSWGuiText` (+ `CSWGuiTextInfo`) loads `FONT` (default `dialogfont16x16`), `COLOR` (default
(1,1,1)), `TEXT`, `STRREF` (default -1; when not -1 it replaces `TEXT` with the TLK string),
`ALIGNMENT` (default 9 = left/top) and `PULSING` (0x00416050). `SetText` (0x00415e00) and
`SetStrRef` (0x00415e50) re-layout the string immediately. The colour read from the file is kept
(+0x2c) so hilight and disable can recolour and restore it. A pulsing text uses the
border-pulse clock as its alpha. (high)

### Which font file is loaded: the `a`/`b` suffix

Before loading, every GUI font name except `fnt_console` gets a letter appended (0x0040b360,
called from 0x00415d60 whenever the font is set or a control re-lays out): **`a`** when the
`[Game Options] Use Small Fonts` option is on, **`b`** when it is off (the default). (The code
also has a resolution rule — `a` below 1280 pixels wide, else `b` — but only for a third option
value that the options code never produces.) So `dialogfont16x16` loads `dialogfont16x16b`,
`fnt_d16x16` loads `fnt_d16x16b`, `dialogfont10x10` loads `dialogfont10x10b`; with small fonts
the `a` files. The four fonts the `.gui` files name (`dialogfont16x16` 1214 times, `fnt_console`
913, `dialogfont10x10` 103, `fnt_d16x16` 47) all have both variants, so **the unsuffixed
`fnt_d16x16` texture, whose TXI does not fit its pixels, is never used** — this settles the open
point in txi-render.md. Changing the option calls `OnResolutionChanged`, so every control
re-applies the suffix (control slot 35). (high)

### Font metrics

The TXI parser (`ParseFontField` 0x00422210) stores, per font texture: `numchars`,
`fontheight`, `baselineheight`, `texturewidth`, `spacingR`, `spacingB` and the two coordinate
blocks (per glyph `u v 0`; glyph *c* is byte value *c* of the string). Units: the metrics are in
hundreds of pixels, so a pixel size is `value * 100 * scale`, with scale 1 for all GUI text. Let
`T = texturewidth * 100` (the texture width in pixels; every font texture is square, and the code
uses `T` for both axes), `ul[c]`, `lr[c]` the corners. (high)

- **Glyph quad**: width `(lr.u - ul.u) * T` pixels; height `fontheight * 100` pixels, the same
  for every glyph; drawn with its top at the line's top. Texture corners: (ul.u, ul.v) top-left,
  (ul.u, lr.v) bottom-left, (lr.u, lr.v) bottom-right, (lr.u, ul.v) top-right, each coordinate
  minus 0.0001.
- **Advance**: the next glyph starts where this one ends. The draw code (0x0045a850) adds
  `spacingR` scaled twice by the viewport (effectively a fraction of a pixel), while the width
  measurement adds the full `spacingR * 100` pixels per glyph. Only `fnt_console` has a non-zero
  `spacingR` (0.02), so console-font text that is centred or right-aligned ends up about 2 pixels
  per character left of where its measured width says. Reproduce: advance = glyph width;
  measured width = sum of `trunc((glyph width + spacingR*100) * scale + 0.25)` (the layout pass,
  0x0045a2f0) or `sum trunc(glyph width + spacingR*100) - trunc(spacingR*100)` (single-line
  width, computed lazily in the draw).
- **Line height**: `(ul.v - lr.v) * T` of the first character of the next line (all glyph
  cells of a font have the same height, `fontheight * 100`); `spacingB` (0 in every font) is
  meant to add to it. `baselineheight` is parsed but never used for drawing. (high)
- **Colour**: the text colour times the alpha; **bytes below 0x20 are drawn white** (untinted),
  everything else in the text colour. (high)
- `fnt_console` (no suffix) is the debug/console font; `fnt_credits` is named by the credits
  panel (`fnt_creditsa/b` exist); `dialogfont32x32` and `fnt_galahad14` are not named by any
  `.gui`. (high for the names in code, med for "unused")

### Layout and word wrap (0x0045a2f0)

The string is laid out for the text rectangle's width (or an explicit width) into lines, each
with a character count and a pixel width (integers). Rules, in order (high):

1. Each `\n` ends a line; consecutive `\n` give empty lines.
2. Characters are added while the running width stays below the wrap width.
3. A **space** is a break opportunity (the space is dropped at the break and its width
   removed); a **hyphen between two letters** is one too (the hyphen stays on the first line).
4. If the line overflows with no break opportunity, the word is split: the last character that
   overflowed moves to the next line and the line is marked to draw a **`-`** after it (its
   width counts the hyphen glyph).
5. Very narrow boxes: a one-character string is not laid out if the box is narrower than the
   width of `o`; a two-character one if narrower than two `o`s; if not even one character fits,
   no lines are produced.

The text height reported to list boxes and scrolling labels is
`trunc(lines * (fontheight + spacingB) * 100 * scale + 0.5)` (0x0045b7a0).

### Alignment

`ALIGNMENT` bits (low three for horizontal, next three for vertical); the code tests
`alignment & 7` and `alignment & 0x38` (high):

| Bits | Placement |
|---|---|
| 1 | left: lines start at the rectangle's left edge |
| 2 | centre: each line offset by `(rectW - lineWidth) / 2` |
| 4 | right: each line offset by `rectW - lineWidth` |
| 8 | top: the first line at the rectangle's top |
| 16 | middle: the block offset by `(rectH - lines * lineH) / 2`; if that is negative, **leading lines are dropped** until the rest fits (so overflowing centred text shows its end) |
| 32 | bottom: the block offset by `rectH - lines * lineH`, dropping leading lines the same way |

The data uses 9, 10, 12, 17, 18, 20 and 34. A line is drawn if its top is above the rectangle's
bottom (it may hang over; the viewport clips it); lines wholly above the viewport (scrolled
text) are skipped; drawing stops once a line's top passes the viewport bottom. The default for a
text struct without `ALIGNMENT` is 9. (high)

### Text colours set by code

| Constant | Value (RGB) | Use |
|---|---|---|
| 0x0078d3c0 | (0.98, 1.0, 0.0) yellow | button text while hilighted (0x00418e00); also pulses (high) |
| 0x0078d3b4 | (0.0, 0.33, 0.49) dim blue | text of a disabled button or label (0x00418db0, 0x00418d00) (high) |
| 0x007a23b4 | (0.0, 0.66, 0.98) blue | normal menu text set by code (main menu hover-off, save list rows, ...) (high) |
| 0x007a23c0 | (0.98, 1.0, 0.0) yellow | hilighted menu text set by code (main menu hover-on, ...) (high) |

## 6. Controls

Common fields of every control (`CSWGuiControl`, ctor 0x0041aa80) (high unless noted):

| Offset | Meaning |
|---|---|
| +0x04 | extent (x, y, w, h), panel-relative |
| +0x14 | parent control (`Obj_ParentID` resolved through the panel's array at load) |
| +0x18 | children |
| +0x24 / +0x28 | tooltip strref / tooltip string (set by code; 0 and "" = ask the parent) |
| +0x30 | key-map event whose key name is appended to the tooltip |
| +0x34 | owning panel |
| +0x38 | event handler table: {owner, callback, event} |
| +0x44 | flags: 0x01 hilighted, 0x02 visible, 0x04 "hover acts as focus" (med), 0x08 enabled/selectable, 0x20 ignore hit tests, 0x40 showing tooltip |
| +0x48 / +0x4c | last event and value handled |
| +0x50 | `ID` |
| +0x54 / +0x55 | click sound (default 0, `gui_click`) / hover sound (default 1, `gui_scroll`), indices into guisounds.2da |

A new control is visible and enabled (flags 0x0a). The `TAG` is only used for matching at load
and is not stored. `MOVETO` (selectable controls only) is read with default 0 for a missing
direction inside an existing struct; -1 or an id out of range means none (resolved to control
pointers by `ResolveMoveToLinks` 0x0040a890).

### Per control type: fields and drawing

| Control | Load (fields) | Draw (in order) |
|---|---|---|
| Label (4) | `BORDER`, `TEXT` | border, text |
| Proto item (5) | + `HILIGHT` | `HILIGHT` instead of `BORDER` while hilighted, text |
| Button (6) | `BORDER`, `HILIGHT`, `TEXT`, `MOVETO` | `HILIGHT` *instead of* `BORDER` while hilighted (the normal border is not drawn underneath), text |
| Check box (7) | button + `SELECTED`, `HILIGHTSELECTED`, `ISSELECTED` | off: `BORDER`/`HILIGHT`; on: `SELECTED`/`HILIGHTSELECTED`; then text |
| Slider (8) | `BORDER`, `HILIGHT`, `THUMB` image, `CURVALUE`, `MAXVALUE`, `MOVETO` | border or hilight, then the thumb |
| Scroll bar (9) | `BORDER`, `DIR` image (arrows), `THUMB` image, `MAXVALUE`, `CURVALUE`, `VISIBLEVALUE`, `DRAWMODE` | see below |
| Progress bar (10) | `BORDER`, `PROGRESS` border, `MAXVALUE`, `CURVALUE`, `STARTFROMLEFT` (default 1) | border, then the `PROGRESS` border over the filled part |
| List box (11) | `BORDER`, `SCROLLBAR`, `LEFTSCROLLBAR` (default 1), `PADDING`, `COLOR` (default (0,0,0)), `LOOPING`, `MOVETO`, `PROTOITEM` | see below |
| Edit box | `BORDER`, `TEXT` | border, text (with `_` appended while it has focus) |

(high: loaders 0x0041b960, 0x0041ba20, 0x0041c930, 0x0041cb40, 0x0041cc30, 0x0041bcd0,
0x0041bbc0, 0x0041d5b0, 0x0041c7d0; renders 0x00417750, 0x00417880, 0x00417ab0, 0x00417b10,
0x00417e60, 0x00419660, 0x00417f60, 0x0041a3e0, 0x00418420)

Labels, buttons and list rows place their text in the border's inner rectangle (§4) whenever
their extent is set (0x00417780).

**Hilight.** A button's `SetHilighted` (0x00418e00) sets flag 0x01, recolours the text yellow
(0x0078d3c0) and makes it pulse; un-hilighting restores the file colour. Labels have no hilight
state; proto items swap borders only. (high)

**Enabled.** Disabling a button or label (slot 34, 0x00418db0 / 0x00418d00) clears flag 0x08,
recolours the text dim blue (0x0078d3b4) and drops the hilight; re-enabling restores the file
colour. Disabled controls ignore clicks (no 0x27, §7) and are skipped by keyboard navigation.
(high)

**Check box.** Holds its state at +0x1c8 bit 0; it toggles on the event stored at +0x1c4 (the
activate event, 0x27, med) before the normal button handling (0x0041adb0). (high)

**Menu check box** (vtable 0x00758258, a subclass of the check box that the options panels
create: the check boxes of `optgameplay`, `optautopause`, `optgraphics`, `optgraphicsadv`,
`optsoundadv`, `optmouse`, and the rows of `optfeedback`'s list; the HUD's toggles and the party
selection's slots are the plain class). Three overrides turn the file's full-width control into a
bullet with a label (high):

- `SetExtent` (0x006de000): the control keeps the whole extent (so the whole row is the click
  target), but the four borders (`BORDER`, `HILIGHT`, `SELECTED`, `HILIGHTSELECTED`) are put in a
  **25 x 25 square at the extent's left edge**, top = `y + 2 + (height - 25) / 2`, and the text
  gets `(x + 30, y, width - 30, height)`. Without it the 32x32 ring art (`i_checkbox01`, the dotted
  `i_checkbox02` when on) is stretched over the 240x40 extent into a huge ellipse.
- `LoadFromGFF` (0x006de160): after the base load it overwrites the tint of `BORDER` and `SELECTED`
  with the menu text colour (0, 0.66, 0.98) and of `HILIGHT` and `HILIGHTSELECTED` with the
  hilight colour (0.98, 1, 0), whatever the file says (the options panels' files say white).
- `Render` (0x006de0e0): each frame it sets the text colour from the state, then draws as the base
  class: hilighted, the hilight colour with the text pulsing; disabled (flag 0x08 clear), dim blue
  (0, 0.33, 0.49); else menu blue.

**Progress bar** (0x00419300): with `MAXVALUE` > 0, `frac = CURVALUE / MAXVALUE`; the
`PROGRESS` rectangle is the `BORDER`'s inner rectangle cut down along its long axis (vertical when
taller than wide): the filled length is `trunc(frac * length)`; with `STARTFROMLEFT` = 1 it is
anchored left (or top), with 0 right (or bottom). The HUD's vertical health and Force bars use 0
(fill from the bottom); the target health bar uses 1. With `MAXVALUE` 0 the whole inner
rectangle is drawn. (high)

**Slider** (thumb 0x00418f20, input 0x0041adf0, drag 0x00419250): value 0..`MAXVALUE`. The
thumb keeps its texture's natural size along the slider and spans it across; its position is
`start + (length - thumbLength) * value / max`. Horizontal sliders (w ≥ h): left (0x3f, 0x2f)
and wheel-down (501) decrease by 1, right (0x40, 0x30) and wheel-up (500) increase; vertical:
up/down. A change plays the slider's sound (+0x78). Clicking the bar before or after the thumb
steps by one; dragging sets `value = max * (mouse - start) / length`, clamped. (high for keys
and the formula, med for the click zones)

**Scroll bar** (0x00419660; inside list boxes only): fields +0x5c max, +0x60 current, +0x64
visible (setters 0x00418070 / 0x004180a0 / 0x004180d0; current is clamped to 0..max, visible to
≥ 1). `DRAWMODE` 0 draws the border, the thumb and both arrows; `DRAWMODE` 1 draws only the
arrows, each only while scrolling that way is possible. The `DIR` image is the "up" arrow: drawn
at the top (left) end, and flipped at the bottom (right) end. Clicking an arrow scrolls one row
and repeats every 0.1 s after 0.5 s while held; clicking the track pages. (high for drawing,
med for the click zones)

**Edit box** (`CSWGuiEditBox`, focus 0x0041a820, keys 0x004184f0): focus switches the input
layer to text mode and makes the box the manager's keyboard target (+0x18). Typed characters:
backspace and delete remove the last character; printable characters (≥ 0x20) except `_`, `/`
and `\` are appended up to the maximum length (+0x70 of the text, -1 = unlimited); Enter sends
0x27 to the panel, Escape 0x28; four control codes map to navigation. While focused the shown
text is the content plus `_`. (high)

### List boxes (`CSWGuiListBox`)

Fields (high): +0x28c..+0x298 the row area (inside the border, beside the scroll bar), +0x29c
rows (count +0x2a0), +0x2b4 row height, +0x2c0 `PADDING` (byte), +0x2c1 move sound (0xff =
none), +0x2c2 pixel-scroll position, +0x2c4 visible rows, +0x2c6 selected index (-1 = none),
+0x2c8 first visible row, +0x2cc the prototype row control, +0x2d0 `COLOR`, +0x2bc flags (0x08
needs layout, 0x10 scroll bar on the left, 0x20 scroll bar shown, 0x40 `LOOPING`, 0x100 "one
text" mode, 0x200 "scroll only, no selection", 0x400 draw only fully visible rows, 0x800 pulse
the scroll bar, 0x1000 keep the selection in view, bits 13–16 the prototype's CONTROLTYPE).

- **Prototype.** `PROTOITEM` is read once into a template control of type 4–8 (0x0041d3e0);
  panels fill the list by creating row controls (usually copies of the template made by the
  panel code) and handing them over with `SetItems` / `SetItemsArray` (0x0041c1d0 / 0x0041c2c0)
  or by adding text in "one text" mode. (high for the template, med for how panels copy it)
- **Layout** (`UpdateLayout` 0x0041b140): row height = the tallest row; stride = row height +
  padding; visible rows = `areaH / stride`. Visible rows are placed from `y = padding`, each
  stretched by `(areaH - visible*stride - padding) / visible` pixels, the remainder spread one
  pixel per row; rows are inset by the padding on both sides (`width = areaW - 2*padding`);
  rows above and below the window are placed outside the area and not drawn. The scroll bar gets
  `max = count - visible + 1` (at least 1), `visible = min(visible, count)`, `current = first
  visible row`. (high)
- **Tall content.** When a single row is taller than the area (descriptions), the list scrolls
  by pixels instead (+0x2c2, 0x0041a2d0) and only that row is drawn. (med)
- **Keeping the selection in view**: after `SetSelectedIndex` (0x0041c040) the first visible row
  moves just enough to show the selection; scrolling with the wheel or the scroll bar turns
  this off until the next selection. (high)
- **Drawing** (0x0041a3e0): the scroll bar (if shown), the list `BORDER`, then a viewport over
  the row area filled with `COLOR` unless it is (-1,-1,-1) — a list whose file says (0,0,0) gets
  a black background — and the rows that intersect it. (high)
- **Selection** (`SetSelectedIndex`): the old row gets event 1 (un-hilight), the new one event 0
  (hilight) and, if asked, its hover sound; -1 clears it. (high)
- **Keys** (0x0041ce20): up (0x3d, 0x31) selects the previous row; at row 0 with `LOOPING` it
  wraps to the last, else nothing; down (0x3e, 0x32) the next, wrapping to 0 with `LOOPING`;
  with no selection, up/down select row 0 (lists in "scroll only" mode move the window
  instead). A change plays the list's move sound. Wheel 500 scrolls up one row, 501 down one;
  0x1fb/0x1fc scroll one row (arrow clicks); 0x1fd/0x1fe a page (`visible` rows). Every event
  is then forwarded to the selected row (so Enter reaches a row button) and finally to the
  list's own handlers. (high)
- **Mouse** (0x0041c4a0 / 0x0041a700): pressing on a row sends the list event 0x1f9 and then
  selects the row (immediately for button rows or lists flagged "select on press", else on
  release) and sends 0x1f8; releasing on the same row sends 0x27 to the list. Panels hook 0x1f8
  ("row clicked") and 0x27 ("row activated") on the list. Pressing on the scroll bar's arrows,
  thumb or track scrolls as above and captures the mouse. (med)

## 7. Events and handlers

### The handler table

`SetEventHandler(control, event, owner, callback)` (0x0041ab20) adds an entry; a control's
`HandleInputEvent` (0x00418750) first handles events 0 and 1 itself (0 with a non-zero value
hilights, 1 un-hilights if hilighted), then finds the first entry for the event and calls
`callback(owner)` after storing the event and value at +0x48/+0x4c. A selectable control
(`CSWGuiSelectable`, 0x0041a9d0) first follows `MOVETO` for the four direction events: it walks
the link in that direction, skipping disabled controls (stopping if it comes back to itself), and
asks the panel to make the result its active control; then it dispatches as above. A button
(0x0041ad40) plays its click sound on 0x27 before that. (high)

### Event codes

| Code | Meaning | Source on PC |
|---|---|---|
| 0 / 1 | gain / lose hilight (hover or keyboard focus) | the manager, `SetActiveControl`, list selection (high) |
| 0x27 | activate / accept | left-button release on the control; Enter (key event 0xbb) and a second key (0xb5) remapped by the manager (high) |
| 0x28 | back / cancel | Escape (key-map action 223 "GUI", event 0xdf) and event 0xb4 (high) |
| 0x29, 0x2a, 0x2b | third, fourth, fifth panel command (delete, recommended, default ...) | buttons via thunks (below) (high) |
| 0x2d | gamepad accept; main-menu and chargen buttons register it next to 0x27 | not produced by the PC key map (med) |
| 0x2e | gamepad back (main menu, save/load treat it like 0x28) | not produced on PC (med) |
| 0x2f / 0x30 | decrement / increment (minus/plus and arrow buttons send these to their panel) | thunks; edit-box control codes (high) |
| 0x31 / 0x32 | second up/down pair (treated like 0x3d/0x3e by lists, sliders and MOVETO) | edit-box control codes (med) |
| 0x33, 0x34, 0x37, 0x38 | analog axes; folded by sign into 0x3d/0x3e, 0x3f/0x40, 0x39/0x3a, 0x3b/0x3c | gamepad (med) |
| 0x3d / 0x3e / 0x3f / 0x40 | up / down / left / right (MOVETO, lists, sliders) | arrow keys (key events 0xb6, 0xb7, 0xb8, 0xb9) (high) |
| 0x44 | right-click release on the control | (high) |
| 500 / 501 | wheel up / wheel down (one per 120 units of wheel delta) | `HandleMouseWheel` 0x0040c650 (high) |
| 0x1f8 | list row clicked | list box (med) |
| 0x1f9 | left press (sent to every panel in the "GUI" input class, and to the pressed list) | `HandleLeftMouseDown` (med) |
| 0x1fb..0x1fe | list: row up, row down, page up, page down | list box (high) |

Events 0x2f..0x32 also take part in a 150 ms debounce in `HandleInputEvent` (a pair in the same
group within 150 ms of each other is dropped). (med)

### Panel commands: the thunk pattern

Most buttons do not carry behaviour themselves. Their 0x27 handler is one of a few one-line
thunks that resend a *panel-level* command, named after the Xbox pad buttons the codes come
from, to the owning panel:

| Thunk | Panel slot | Event | Typical use |
|---|---|---|---|
| `OnButtonAccept` 0x00624ba0 | 20 `SendAccept` 0x0040b640 | 0x27 | OK, Accept, Use, Load/Save |
| `OnButtonCancel` 0x00624bb0 | 21 `SendCancel` 0x0040b650 | 0x28 | Back, Exit, Cancel |
| `OnButtonX` 0x00624bc0 | 22 `SendButtonX` 0x0040b660 | 0x29 | Delete, Select, filter, quest items |
| `OnButtonY` 0x00644720 | 23 `SendButtonY` 0x0040b670 | 0x2a | Recommended, Default, Random, swap |
| `OnButtonZ` 0x00644730 | 24 `SendButtonZ` 0x0040b680 | 0x2b | sort |
| `OnButtonPrev` 0x0067cb40 | — | 0x2f | minus, left arrow |
| `OnButtonNext` 0x0067cb50 | — | 0x30 | plus, right arrow |
| `OnButtonAlternateAccept` 0x0067cb60 | — | 0x2d | pazaak Wager |

The panel's own `HandleInputEvent` (slot 15) then does the work, so the same code serves the
button, the Escape key and the gamepad. A reimplementation should keep this split: buttons emit
commands, each panel has one command handler. (high)

## 8. Input routing and focus

### From the device to the GUI

`ProcessInput` (0x006227e0) reads the frame's mapped events for the current input class
(client +0x9c: 0 in-game, 1 mini-game, 2 GUI, 3 dialogue, 4 free look, 5 movie; the class
order follows the key-map columns, med). Per event:

- a **GUI-reserved action** — the arrow/Enter codes 0xb4..0xbb, Tab 0xce (change character),
  Escape 0xdf, the menu-cycling Q/E actions 0xf3/0xf4, the dialogue number keys 0xfe..0x106 —
  or any event 0x27..0x40 goes to `CSWGuiManager::HandleInputEvent` (0x0040c8e0), provided the
  input class is GUI or dialogue or the in-game GUI's HUD mode (`CGuiInGame` +0x34) is 1
  ("game", the HUD is up);
- except that in HUD mode 1 the GUI-reserved actions outside 0x27..0x40 go to the game instead
  (`HandleInputAction` 0x00621210, which opens menus, cycles characters, etc.);
- everything else goes to `HandleInputAction`.

After each event the cursor position goes to `HandleMouseMove` (0x0040c1e0) unless mouse-look is
active. HUD modes: 1 game, 2 conversation, 3 menu (§10.3). (med)

`HandleInputEvent` remaps the key codes (0xb5/0xbb → 0x27, 0xb4/0xdf → 0x28, 0xb6..0xb9 →
0x3d..0x40) and folds the axes; then **if the modal stack is empty it offers the event to every
panel in the list (in list order), otherwise only to the top modal panel**. A panel's default
`HandleInputEvent` (0x00409e60) passes it to its active control (+0x1c). Afterwards panels marked
for removal are reaped. (high)

### The modal stack

`AddPanel(panel, flags, playSound)` (0x0040bc70): plays the panel's open sound (+0x60, none by
default) if asked, appends the panel to the list (or reactivates it), copies flag bits 1–2 to
panel flags 0x08/0x10, pushes it on the modal stack if bit 0 is set, calls the panel's
`OnAdded` (base: relayout, refresh the hover control, re-focus), and recomputes visibility.
`PushModalPanel` (0x0040bd90) un-hovers the hovered control and drops edit-box focus first.
`PopModalPanel` (0x0040be00) pops and gives focus back to the new top's active control.
`RemovePanel` (0x0040c830) pops or extracts it from the stack, calls `OnRemoved` (drops tooltip,
edit focus and hover inside it), removes it from the list, and re-runs the hover test at the
current cursor. `BringPanelToFront` (0x0040bd20) moves a non-modal panel to the end of the list.
(high)

**Visibility** (`UpdateTopPanel` 0x0040acc0): walking the modal stack top-down and then the
panel list end-to-start, every active panel is marked visible (0x80) until the first
**full-screen** one (flag 0x08) has been marked; everything below it is hidden. So opening a
full-screen menu hides the HUD and any menu under it, and the backdrop texture becomes that
menu's tag. (high)

### Hover, focus and the active control

- **Hover** (manager +0x08) is the control under the cursor (`GetPanelAndControlAt`
  0x0040abe0): with a modal panel, only the top modal panel is tested; otherwise every panel,
  from the end of the list (front-most) backwards. Within a panel the control array is tested
  from the highest index down; a control is hit if it is visible, not flagged 0x20, and the point
  is inside its extent, edges included (0x004187c0). (high)
- **Moving the mouse** (`HandleMouseMove`): if a control holds the mouse capture, it gets the
  drag call and nothing else happens; otherwise the hover is re-tested. A newly hovered enabled
  control is told to take the hover (control slot 3: hilight and the hover sound `gui_scroll` if
  it was not hilighted) and becomes its panel's active control; its ancestors (`Obj_Parent`
  chain) are hilighted too; the previously hovered control and its ancestors are un-hilighted
  unless they are ancestors of the new one. Leaving all controls un-hovers. (med for the
  ancestor rules)
- **Keyboard focus**: the panel's *active control* (+0x1c) receives the panel's events.
  `SetActiveControl` (0x0040a630) sends 1 to the old and 0 to the new, with the new one's hover
  sound. Arrow keys move it along `MOVETO` (§7). Mouse hover and keyboard focus are the same
  thing: hovering a button makes it the active control. (high)
- **Text focus**: only edit boxes; manager +0x18. Typed characters (window message path,
  `HandleCharacter` 0x0040b2a0) go to it, and with a modal panel up only if it belongs to the
  top modal panel. (high)

### Clicks, capture and GUI-versus-world

- **Left press** (`HandleLeftMouseDown` 0x0040c570, from the client's 0x0061f880): records the
  button, re-tests the hover, and calls the hovered control's left-down slot, which captures the
  mouse for that control (or its selectable parent). It **returns 1 when a control was under the
  cursor**; the client then does not treat the press as a world click. (high)
- **Left release** (`HandleLeftMouseUp` 0x0040a170): if a control holds the left capture, it gets
  the left-up slot: if the cursor is still on it (or on one of its children) it sends 0x1f9 if
  the button flag is still set, and **0x27 if the control is enabled**; then the capture is
  released. It returns 1 if a control held the capture. The client's left-up (0x00620530) runs
  the **world click only when the GUI did not consume it**, with one exception: a click on the
  HUD's minimap area is passed on as a world/map click. (high for the rule, med for the
  minimap test 0x00684ed0)
- **Right button**: the same with capture button 4 and event 0x44 on release. (high)
- **Wheel**: goes to the control under the cursor, not the focused one: a list box gets one
  500/501 per 120 units; another control passes it to itself or its selectable parent, if that
  is enabled. (high)
- **Capture** (`SetMouseCapture` 0x0040a1c0 / `ReleaseMouseCapture` 0x0040a200): one control
  and a button id (1 left, 4 right); setting a new one tells the old one it lost the capture
  (slot 5). (high)

## 9. Sounds, tooltips and the cursor

### guisounds.2da

Loaded once by `LoadGuiSounds` (0x00409f00) from column `SoundResRef`; `PlayGuiSound(n)`
(0x0040a140) plays row *n* if it exists. Rows: 0 `gui_click` (default click), 1 `gui_scroll`
(default hover; also every focus move), 2 `gui_error`, 3 `gui_check`, 4 `gui_open` (full-screen
menu opened), 5 `gui_close` (closed), 6 `gui_actuse`, 7 `gui_actscroll`, 8 `gui_button` (action
menu: use, scroll, queue), 9 `gui_invadd`, 10 `gui_invselect`, 11 `gui_invdrop`, 12 `gui_level`
(level-up available), 13 `gui_quest`, 14 `gui_complete`, 15 `gui_prompt`, 16 `gui_upgrade`.
Sounds 4/5 are played by the in-game GUI's open/close-menu code (0x0062c9b0, 0x0062cba0, ...),
not by `AddPanel`. (high for the table, med for which code plays which row)

### Tooltips

- The tooltip panel (`CSWGuiToolTip` 0x006277c0, manager +0x3c) is a one-label panel from the
  `tooltip*` file for the resolution. (high)
- Timer: the manager keeps a hover timer (+0x44, -1 = stopped) and a delay (+0x48). Any change
  of hover, button press or wheel restarts it (0x0040b500 / 0x0040b4d0) **only if tooltips are
  enabled** (client options +0x14 bit 0x400, on by default). Each frame `Render` advances it;
  once it passes the delay it asks the hovered control for its tooltip (slot 36, 0x00418a90),
  stops the timer, and remembers the control (+0x40). The delay is the option at client options
  +0xc (default 1.0 s); while the "ToolTips" key (key map action 225, `T`) is held it is 0, so
  tooltips appear at once (0x005f4be0). (high)
- Tooltip text: the control's tooltip strref (via TLK) or string; if both are empty the parent's
  tooltip is used. If the control names a key-map event, the key's name is appended as
  `" : " + name` (the name's strref is `KeyNameStrRef` from the key-name 2DA at row
  `key - 6`). The text goes into the tooltip label and the manager sets its "tooltip showing"
  flag (+0x1c bit 3) so `Render` draws the tooltip panel, sized to the text plus 8 pixels each
  way and placed 15 pixels from the cursor, kept 2 pixels inside the screen (§10.3). (high for
  the text, med for the 2DA row arithmetic)
- Hiding: moving to another control, pressing a button, the wheel, or removing the panel.

### The software cursor

The cursor is not the Windows cursor (`EnableHardwareMouse` aside, app.md): the manager builds a
small GUI 3D scene with the model `gui_mouse` (`CreateCursorModel` 0x0040b060) and draws it last
each frame, positioned at the cursor in units of 0.01 per pixel with y flipped. The cursor image
is a texture swapped onto that model (`SetMouseCursor` 0x0040a270): cursor *n* uses the name at
index *n* of the table at 0x0078d240, and the pressed look (left button down, set by the client's
mouse handlers) uses index *n* + 1 when *n* is odd. The model animation `center` or `default`
chooses between a centred and a top-left hot spot. (high)

| Ids | Textures | Use (from the names; chosen by movement/targeting code 0x006222f0) |
|---|---|---|
| 1/2 | `gui_mp_defaultu/d` | default |
| 3/4 | `gui_mp_walku/d` | walk to |
| 5/6 | `gui_mp_invalidu`, `gui_mp_invalid` | cannot go |
| 7–10 | `gui_mp_bashu/d`, `..bashup/dp` | bash (and its "p" variants) |
| 11–14 | `gui_mp_talku/d`, `notalku/d` | talk / cannot talk |
| 15/16 | `gui_mp_followu/d` | follow |
| 17–20 | `gui_mp_examineu/d`, `noexamu/d` | examine |
| 21/22 | `gui_mp_transu/d` | area transition |
| 23/24, 43/44 | `gui_mp_dooru/d`, `doorup/dp` | door |
| 25–28 | `gui_mp_useu/d`, `useup/dp` | use |
| 29–32 | `gui_mp_magicu/d`, `nomagicu/d` | Force power / cannot |
| 33–40 | `gui_mp_dismineu..`, `recmineu..` | disarm / recover mine |
| 41/42 | `gui_mp_locku/d` | locked |
| 45/46 | `gui_mp_selectu/d` | select |
| 47–50 | `gui_mp_createu/d`, `nocreatu/d` | create (unused, low) |
| 51–54 | `gui_mp_killu/d`, `nokillu/d` | attack / cannot |
| 55–58 | `gui_mp_healu/d`, `noheal..` | heal / cannot |
| 59/60 | `gui_mp_pickupu/d` | pick up |
| 61–76 | `gui_mp_arrun00..15` | run, 16 directions (free-look/keyboard move arrows, med) |
| 77–92 | `gui_mp_arwalk00..15` | walk, 16 directions (med) |

Index 0 is the empty name. (high for the table; med for the meanings)

## 10. Panel catalogue

The catalogue has five groups: the front end (loading screen, main menu, save/load, movies,
credits, options), character generation and level-up, the in-game GUI (the `CGuiInGame` owner,
the HUD and the overlays), the in-game menus (inventory, equipment, character, abilities,
journal, map, galaxy map, container, store, upgrade bench, party selection, script select), and
the conversation and pazaak panels. For every panel: the `.gui` resref (tags checked against the
dumps of every file, including the `patch.erf` versions), constructor, vtable, size and owner,
the controls by tag, the callbacks, what game state it reads or changes, how it opens and closes.
Panels only skimmed are marked. The `.gui` files `splashscreen`, `startscreen`, `ntscpat`,
`maininterface`, `mi8x6`, `mipc8x6`, `mipc10x7`, `mipc12x9`, `mipc16x12` and `mainmenu8x6` ..
`mainmenu16x12` are not named by any code (Xbox and older layouts) (high).

### 10.1 Front end

#### Loading screen (`CSWGuiLoadScreen`, `loadscreen`)

Constructor 0x0067a710, vtable 0x00752dc0, 0x6b8 bytes, owned by the client (+0x278). Flags
0x60 (centred 640x480 frame). (high)

| Tag | Role |
|---|---|
| (root `BORDER` fill) | the picture for the area being loaded; replaced at run time (`SetImage` 0x0067a6d0: only if a TGA or TPC of that name exists) |
| `PB_PROGRESS` | load progress 0–100 |
| `LBL_HINT` | hint text (strref, TLK tokens parsed) |
| `LBL_LOGO` | logo (from the file) |
| `LBL_LOADING` | "Loading" (strref 42493) or "Saving" (42528) |
| (code label +0x578) | full-screen backdrop `WxHload` (e.g. `1024x768load`), stretched over the whole screen and drawn before the panel (`Render` 0x0067ab00) |

- **Picture** (`SetLoadScreenImage` 0x005f3480, client +0x2fc): `loadscreens.2da` column
  `BMPResRef` by row label (`classsel` for character generation, area/module rows such as
  `manm26mg`); when the row is missing it tries `load_<name>` as a texture and falls back to row
  `default` (`LOAD_DEFAULT`). (high)
- **Showing** (`ShowLoadScreen` 0x005f6c60): creates the panel if needed, applies the picture
  and the Loading/Saving text, adds it modal (`AddPanel(…, 1, 1)`), unacquires input, switches
  the input class to GUI, sets the sound mode (3 for a save, 4 when the area has load music).
  (med)
- **Progress** (`SetLoadProgress` 0x005fb3f0, called through 0x005edd40): sets `PB_PROGRESS` to
  0..100. The loading code computes the value from per-phase byte weights kept at client +0x3e4
  (phases 0–3), adding a fraction of the current phase as work completes (e.g.
  `CGuiInGame::CreatePanels` advances phase 3 in steps between panels); each step calls
  `RenderLoadingFrame` (0x00401c10), which draws a GUI-only frame. Phase bookkeeping belongs to
  gameloop.md. (med)
- **Hints** (`PickLoadScreenHint` 0x005f4760): `loadscreenhints.2da` (columns `GamePlayHint`,
  `StoryHint`, 92 rows) is read round-robin with one counter per column (client +0x490 gameplay,
  +0x491 story), wrapping to row 0 at the end. The kind is chosen by the caller (1 gameplay,
  2 story; otherwise asked from the server, defaulting to gameplay). While progress is below 80,
  `UpdateLoadScreenHint` (0x005f7b20) switches to the next story hint every 10 s (it accumulates
  millisecond ticks and fires at ≥ 10,000). (high)


#### Main menu (`CSWGuiMainMenu`, `mainmenu`)

Constructor 0x0067c4c0 (0x1414 bytes), `InitPanel` 0x0067ace0 (also re-run on a resolution
change), vtable 0x00752f70; created and added by `CClientExoAppInternal::ShowMainMenu`
(0x005fca30) with `AddPanel(…, 2, 1)` (full screen, not modal). The game reads `mainmenu` from
`patch.erf` (800x600 layout); `mainmenu8x6/10x7/12x9/16x12` are never loaded. (high)

| Tag | Role |
|---|---|
| `LB_MODULES` | debug warp list (hidden in normal play) |
| `LBL_3DVIEW` | the animated 3D background: a GUI 3D scene with the model `mainmenu` from `RIMS:MAINMENU` (the RIM is mounted by the constructor if `MAINMENU` is not already a resource, and unmounted by the manager once the menu goes) |
| `LBL_GAMELOGO`, `LBL_MENUBG`, `LBL_BW`, `LBL_LUCAS` | art (`LBL_BW`/`LBL_LUCAS` unbound) |
| `LBL_NEWCONTENT` | "New downloadable content is available" (42407); bound, shown only when the content check says so (low) |
| `BTN_NEWGAME` | → `OnNewGame` 0x0067afb0 |
| `BTN_LOADGAME` | → `OnLoadGame` 0x0067b1a0 |
| `BTN_MOVIES` | → `OnMovies` 0x0067b250 |
| `BTN_OPTIONS` | → `OnOptions` 0x0067b2f0 |
| `BTN_EXIT` | → `OnExit` 0x0067b4a0 |
| `BTN_WARP` | → 0x0067c4b0 → 0x0067c3f0 (debug warp; hidden) |

- Each button handles 0x27 and 0x2d with the same callback; events 0 / 1 recolour the button
  text to yellow / blue (0x0067b450 / 0x0067b470). The constructor makes `BTN_NEWGAME` the active
  control. (high)
- **Guards**: the callbacks do nothing until the menu has been drawn five times (`Render`
  0x0067ac10 counts frames and sets +0x140c after the fifth), while the menu is already marked
  for deletion, or for the release half of a click (the event value must be non-zero). (high)
- **New game**: chooses the start module — `END_M01AA` (the Endar Spire) — after checking it
  exists as a `.mod` in `MODULES:` or as a `.rim`; builds `CSWGuiClassSelection` with that
  module name, adds it full-screen and modal (`AddPanel(…, 2, 1)`), sets the sound mode to 0 and
  marks the main menu for deletion (flag 0x400). (high)
- **Load game**: `CSWGuiSaveLoad` in load mode, opened from the main menu (see "Save and load" below), added
  full-screen; the main menu is deleted unless the save panel itself was already closing. (high)
- **Movies** / **Options**: `CSWGuiTitleMovies` / `CSWGuiOptionsMain`, `AddPanel(…, 3, 1)`; the
  main menu stays underneath (hidden by the full-screen panel). (high)
- **Exit**: ends the application (0x005ed450). (high)
- **On being added** (0x0067b6c0): checks free space on `SAVES:` (by creating and removing a test
  directory); if below the needed amount it shows the message box with strref 47992 ("... You need to free <CUSTOM0> MB", the
  amount in token 0) whose OK quits the game (0x0067b490). (med)
- The constructor also wipes the `GAMEINPROGRESS:` and `CURRENTGAME:` working directories
  (save-game scratch; party-items-saves.md). (high)


#### Save and load (`CSWGuiSaveLoad`, `saveload`; `CSWGuiSaveName`, `savename`)

`CSWGuiSaveLoad` constructor 0x006cc680 (0x1160 bytes, vtable 0x00757650), arguments
`(manager, saveMode, fromMainMenu)`. (high)

| Tag | Role |
|---|---|
| `LBL_PANELNAME` | "Load Game" (1585) or "Save Game" (1588) |
| `LB_GAMES` | the saves; rows use the menu blue/yellow text colours and a pulsing hilight |
| `LBL_SCREENSHOT`, `LBL_PLANETNAME`, `LBL_AREANAME`, `LBL_PM1..3` | details of the selected save (screenshot, planet, area, party members) |
| `BTN_SAVELOAD` | "Load" (1589) or "Save" (1587): `OnButtonAccept` plus `OnLoad` 0x006cc0e0 or `OnSave` 0x006cbb60 |
| `BTN_DELETE` | `OnButtonX` (0x29) and `OnDelete` 0x006caa90 |
| `BTN_BACK` | `OnButtonCancel` |

`HandleInputEvent` (0x006c86d0): back (0x28, 0x2d, 0x2e) plays the click, marks the panel for
deletion, re-shows the main menu if it was opened from there, and pops it. The list is filled by
0x006cc160 from the save directories (`TEMP:` is mounted for the screenshots). Save mode asks for
a name with `CSWGuiSaveName` (constructor 0x006cae70, vtable 0x007576d0: `EDITBOX`, `LBL_TITLE`,
`BTN_OK` → 0x006c9d50, `BTN_CANCEL` → 0x006c8470; centred dialog). What saving and loading do:
party-items-saves.md. (high for the panel, med for the callbacks' roles — skimmed)


#### Movies (`CSWGuiTitleMovies`, `titlemovie`) — skimmed

Constructor 0x006dd910 (0x654 bytes, vtable 0x00758130): `LBL_TITLE`, `LB_MOVIES`, `BTN_BACK`.
The list comes from `movies.2da` (`strrefname`, `alwaysshow`, `order`; a movie appears when
`alwaysshow` is 1 or it has been seen, med). Back (0x28/0x2e) restores the menu music state
(0x005ed9e0, 0x005ed9b0), pops and deletes the panel (0x006dce80). (med)


#### Credits (`CSWGuiCredits`, `credits`) — skimmed

Constructor 0x0068f8d0 (vtable 0x007541f0): `LB_CREDITS` with the `fnt_credits` font, filled
from a credits text resource and scrolled by `Render` (0x0068f880); it plays its own streamed
music; the destructor (0x0068f0e0) restores the screen size saved when the credits switched to
movie video mode (it calls `SetResolution` with the saved size and `LeaveMovieVideoMode`). (med)


#### Options

Every options panel is a full-screen menu (`AddPanel(…, 3, 1)`) with `LBL_TITLE`, a `LB_DESC`
description list that shows the hovered control's description (each control's event 0 handler
writes it), `BTN_BACK` (→ `OnButtonCancel`) and, where present, `BTN_DEFAULT`. Values are kept in
the client options block and written to `swkotor.ini` by 0x0061b780 (read at start-up by
0x0061dbe0; defaults 0x0061db60). (high for the structure; per-option mapping skimmed)

| Panel | Ctor / vtable | `.gui` | Controls (tag → handler) |
|---|---|---|---|
| Options (main menu) | 0x006e3e80 / 0x00758838 | `optionsmain` | `BTN_GAMEPLAY` 0x006de240, `BTN_FEEDBACK` 0x006e2df0, `BTN_AUTOPAUSE` 0x006de2c0, `BTN_GRAPHICS` 0x006e3d80, `BTN_SOUND` 0x006e3e00 (each opens the sub-panel) |
| Options (in game) | 0x006ab2f0 / 0x00755de0 | `optionsingame` | `BTN_LOADGAME` 0x006aaaf0, `BTN_SAVEGAME` 0x006aab80, `BTN_GAMEPLAY` 0x006aac10, `BTN_FEEDBACK` 0x006aac90, `BTN_AUTOPAUSE` 0x006aad10, `BTN_GRAPHICS` 0x006aad90, `BTN_SOUND` 0x006aae10, `BTN_QUIT` 0x006ab1b0, `BTN_EXIT` back; held at `CGuiInGame` +0x28 |
| Graphics | 0x006e2e70 / 0x007586f8 | `optgraphics` | `SLI_GAMMA`/`LBL_GAMMA` (left/right/accept 0x006ded30), `BTN_RESOLUTION` (+ `LEFT`/`RIGHT`) → resolution list 0x006e1660, `CB_SHADOWS` 0x006dedb0, `CB_GRASS` 0x006dee00, `BTN_ADVANCED` 0x006e2cf0, `BTN_DEFAULT` 0x006e0190 |
| Advanced graphics | 0x006e16e0 / 0x007584a0 | `optgraphicsadv` | `BTN_ANTIALIAS` (+ `LEFT`/`RIGHT` 0x006e0520/0x006e05e0), `BTN_TEXQUAL` (0x006e04a0/0x006e04e0), `BTN_ANISOTROPY` (0x006e0680/0x006e06d0), `CB_FRAMEBUFF` 0x006ddb10, `CB_SOFTSHADOWS` 0x006ddb30, `CB_VSYNC` 0x006ddb60, `BTN_DEFAULT` 0x006e0470, `BTN_CANCEL` 0x006ddb80 |
| Resolution | 0x006e0710 / 0x00758348 | `optresolution` | `LB_RESOLUTIONS` (rows `%d x %d` / `%d x %d @ %d Hz`), `BTN_OK` and row activation → 0x006df690 (applies through `ChangeVideoMode`, §2), `BTN_CANCEL`; centred dialog |
| Sound | 0x006e3550 / 0x007587c0 | `optsound` | `SLI_MUSIC`, `SLI_VO`, `SLI_FX`, `SLI_MOVIE` (+ labels; change 0x006df9b0), `BTN_ADVANCED` 0x006e2d70, `BTN_DEFAULT` 0x006e0f50 |
| Advanced sound | 0x006e20a0 / 0x00758550 | `optsoundadv` | `BTN_EAX` (+ `LEFT`/`RIGHT`), `CB_FORCESOFTWARE`, `BTN_DEFAULT` 0x006e1270, `BTN_CANCEL` 0x006ddff0 |
| Mouse | 0x006e2600 / 0x007585f8 | `optmouse` | `SLI_MOUSESEN`, `CB_REVBUTTONS`, `BTN_DEFAULT` 0x006e12b0 |
| Feedback | 0x006e2a70 / 0x007581e8 | `optfeedback` | `LB_OPTIONS` of check-box rows (toggle 0x006e0100) |
| Gameplay | 0x006e69a0 / 0x00758e00 | `optgameplay` | difficulty (`BTN_DIFFLEFT`/`RIGHT` 0x006e68e0/0x006e6930), `CB_INVERTCAM`, `CB_LEVELUP`, `CB_AUTOSAVE`, `CB_REVERSE`, `CB_DISABLEMOVE`, `SLI_MOUSESEN`, `BTN_KEYMAP`, `BTN_MOUSE` |
| Auto-pause | 0x006e76a0 | `optautopause` | `CB_ENDROUND`, `CB_ENEMYSIGHTED`, `CB_MINESIGHTED`, `CB_PARTYKILLED`, `CB_ACTIONMENU`, `CB_TRIGGERS`, `LB_DETAILS` |
| Key mapping | 0x006edc90 / 0x00759358 | `optkeymapping` (+ `optkeyentry`) | `LST_EventList`, `BTN_Filter_Move/Game/Mini`, `BTN_Default`, `BTN_Accept`, `BTN_Cancel` |


### 10.2 Character generation and level-up

#### Character generation

The flow (high for the wiring, med for the step semantics; the rules — point-buy, skill
points, feat and power choice — are in rules.md):

1. **Main menu → class selection.** `OnNewGame` builds `CSWGuiClassSelection` (0x006dc3c0,
   0x1560 bytes, vtable 0x00758020, `classsel`) with the start module name. The constructor sets
   the load-screen picture to row `classsel` (`LOAD_CHARGEN`) and shows the loading screen, mounts
   `RIMS:CHARGEN` if `CHARGEN` is not already a resource, reads `portraits.2da` (rows with
   `ForPC` = 1), and builds six class/gender slots.
2. **Class selection** (`classsel`): `BTN_SEL1..6` each with a `3D_MODEL1..6` child label that
   shows a GUI 3D scene of a body model (light `cgbody_light`, appearance from `portraits.2da`
   `Appearance_L` / `Appearance_S` and `appearance.2da`); `LBL_CHAR_GEN`, `LBL_INSTRUCTION`,
   `LBL_CLASS`, `LBL_DESC`, `BTN_BACK`. The six slots, from a static table at 0x007a2684
   (8 bytes each: class, gender, ..., description strref): male Scoundrel (32109), male Scout
   (32110), male Soldier (32111), female Soldier, female Scout, female Scoundrel. Hover
   (`OnHoverClass` 0x006dba70) writes "Male"/"Female" (646/647) + class name (Scout 133, Soldier
   134, Scoundrel 135) into `LBL_CLASS` and the description into `LBL_DESC`. Clicking
   (`OnSelectClass` 0x006db9b0, 0x27 and 0x2d) remembers the slot and opens the character
   generation main panel full-screen and modal.
3. **Main panel** (`CSWGuiCharGenMain` 0x006eb420, 0x22dc bytes, vtable 0x007592a8, `maincg`):
   the running summary — `MODEL_LBL` (3D model), `PORTRAIT_LBL`, `LBL_NAME`, `LBL_CLASS`, the six
   ability labels `STR_LBL`..`CHA_LBL` with modifiers `STR_AB_LBL`..`CHA_AB_LBL`, `LBL_VIT`,
   `LBL_DEF`, saves `LBL_FORTITUDE`/`LBL_REFLEX`/`LBL_WILL` with `NEW_*_LBL`, bevel decorations.
   It owns three step panels and shows exactly one at a time as a modal panel
   (`ShowStepPanel` 0x006ea760: 1 = quick-or-custom, 2 = quick steps, 3 = custom steps).
4. **Quick or custom** (0x006f09f0, vtable 0x00759710, `qorcpnl`): `QUICK_CHAR_BTN`
   → 0x006f0800 (quick) and `CUST_CHAR_BTN` → 0x006f0830 (custom) (hover 0x006f09d0 / 0x006f09e0
   fills `LB_DESC`; quick is the initial active control),
   `BTN_BACK`. Flags 0x60.
5. **Quick steps** (0x006f0390, vtable 0x00759668, `quickpnl`): three step buttons
   (`BTN_STEPNAME1..3` with `LBL_NUM1..3`, `LBL_1..3`): portrait 0x006efe10, name 0x006efd80,
   play 0x006efd60 (enabled once step count +0x135c > 1); `BTN_BACK`, `BTN_CANCEL` 0x006f0310
   (asks "Are you sure you want to cancel?", 48541, when steps were done). Quick characters presumably get the
   recommended abilities, skills and feats (outside knowledge, low).
6. **Custom steps** (0x006ef730, vtable 0x007595e0, `custpnl`): six step buttons — portrait
   0x006ef120, abilities 0x006ef3f0, skills 0x006ef360, feats 0x006ef2d0, name 0x006ef240, play
   0x006ef220 (enabled after step 5, +0x2184 > 4); `BTN_BACK`, `BTN_CANCEL` 0x006ef6a0. Steps
   unlock in order.
7. **Step panels**, each full-screen 640x480 with flags 0x60 and the same layout conventions
   (`MAIN_TITLE_LBL`, `SUB_TITLE_LBL`, `LB_DESC` for the hovered item's description,
   `REMAINING_SELECTIONS_LBL`, `BTN_ACCEPT`, `BTN_BACK`, `BTN_RECOMMENDED`):
   - **Portrait** (0x006f9430, vtable 0x00759ea8, `portcust`): `LBL_PORTRAIT`, `LBL_HEAD` (3D head,
     light `cghead_light`, camera hook `camerahook%c`), `BTN_ARRL`/`BTN_ARRR` (previous/next,
     via the 0x2f/0x30 thunks), accept/back.
   - **Name** (0x006f9e70, vtable 0x00759f38, `name`): `NAME_BOX_EDIT` (edit box; Enter accepts),
     `BTN_RANDOM` (`OnButtonY` → random name from the name tables, rules.md),
     `END_BTN`/accept 0x006f9cd0, `BTN_BACK`.
   - **Abilities** (0x006f7600, vtable 0x00759c68, `abchrgen`): per ability `*_LBL`,
     `*_POINTS_BTN`, `*_PLUS_BTN`, `*_MINUS_BTN`; `COST_POINTS_LBL`, `LBL_ABILITY_MOD`,
     `LBL_MODIFIER`. `HandleInputEvent` 0x006f8880: 0x27 accept, 0x28 back, 0x2a recommended (if
     points remain), 0x2f/0x3f decrease and 0x30/0x40 increase the focused ability, 0x39/0x3a
     scroll `LB_DESC`. In character generation each score is 8..18 and raising a score `v`
     costs 1 point below 14, 2 from 14 to 15, 3 from 16 (0x006f8670); trying to pass 18 or go
     below 8 shows a message box (42181 / 42180). At level-up the cost is 1 and the floor is the
     starting value. (high)
   - **Skills** (0x006f51d0, vtable 0x00759990, `skchrgen`): the eight skills (`COMPUTER_USE`,
     `DEMOLITIONS`, `STEALTH`, `AWARENESS`, `PERSUADE`, `REPAIR`, `SECURITY`, `TREAT_INJURY`, each
     `*_LBL`, `*_POINTS_BTN`, `XXX_PLUS_BTN`, `XXX_MINUS_BTN`), `CLASSSKL_LBL`, `COST_POINTS_LBL`;
     `HandleInputEvent` 0x006f6a10. (skimmed)
   - **Feats** (0x006f3d60, vtable 0x007598b0, `ftchrgen`): `LB_FEATS` (row clicked 0x1f8 →
     0x006f3420, press 0x1f9 → 0x006f3cf0), `BTN_SELECT` (accept thunk), `BTN_ACCEPT`
     (`OnButtonX`), `BTN_RECOMMENDED`, `LBL_NAME`; `HandleInputEvent` 0x006f4680. (skimmed)
   - **Force powers** (0x006f2180, vtable 0x00759780, `pwrlvlup`): `LB_POWERS`, `LBL_POWER`,
     `SELECT_BTN`, `ACCEPT_BTN`, `RECOMMENDED_BTN`, `BACK_BTN`; `HandleInputEvent` 0x006f28c0.
     Used by level-up (Jedi), not by the first character generation. (skimmed)
8. **Play** (`Finish` 0x006eb320 → `CSWGuiCharGenMain::Close` 0x006ea830, then
   `CSWGuiClassSelection::StartGame` 0x006dbdf0): all character-generation panels are marked
   for deletion and popped; the client creates the server (`CAppManager::CreateServer`), sends
   it the finished player creature, starts the module named at step 1 (`END_M01AA`), sets the
   load-screen picture for it, picks a story hint and shows the loading screen. (high for the
   order, med for the message details)

**Level-up** reuses the steps: the character sheet's level-up button (0x006b0bb0) opens
`CSWGuiLevelUpMain` (0x006e8ef0, vtable 0x00758f50, `maincg` again, with `LBL_LEVEL`,
`LBL_LEVEL_VAL` and old/new value labels `OLD_*`/`NEW_*` and arrows) which owns
`CSWGuiLevelUpPanel` (0x006ee7d0, vtable 0x00759568, `leveluppnl`): step buttons abilities
0x006ee500, skills 0x006ee480, feats 0x006ee3d0, powers 0x006ee350, finish 0x006ee780;
`BTN_BACK`, `BTN_CANCEL` 0x006ee5f0. The step panels are the same classes in level-up mode
(+0x3df0 set in the abilities panel). `ShowLevelUpGUI` (script routine, 0x00543870) opens it from
scripts. (med)


### 10.3 The in-game GUI: CGuiInGame, HUD and overlays

#### CGuiInGame: the owner of the in-game panels

`CGuiInGame` (our name) is the 0xc24-byte object at `CClientExoAppInternal`+0x40 that owns every
in-game panel, decides which of them are up, and is the single entry point the rest of the client
uses to open menus, show message boxes, fade the screen and drive the HUD. Its constructor
(`0x0062fed0`) only zeroes fields; the panels are made in two steps. (high unless noted)

| Address | Name (ours) | What | Conf. |
|---|---|---|---|
| `0x0062fed0` | `CGuiInGame::CGuiInGame` | zeroes the panel pointers and state; `+0x164` = 10098 | high |
| `0x00632720` | `CGuiInGame::CreateEarlyPanels` | called from `CClientExoAppInternal::PostInitialize` (`0x005f51c0`): makes the panels needed before any module is loaded, so they also serve the main menu: message box `+0x98`, skill info `+0x9c`, tutorial box `+0xa0`, controller box `+0xa4` | high |
| `0x00632860` | `CGuiInGame::CreatePanels` | first module load: makes all the rest, calling `RenderLoadingFrame` between groups so the load bar moves; sets `+0x108` = 1 (panels exist) and `+0x3c` = `+0x40` | high |
| `0x0062f5f0` | `CGuiInGame::RecreateResolutionPanels` | resolution change: deletes and rebuilds the HUD, the letterbox dialogue panel and the message box (their `.gui` depends on the resolution), re-centres the debug panels, container, skill info and tutorial box | high |
| `0x0062b490` | `CGuiInGame::OnResolutionChanged` | calls the OnResize slot (+0x68) of the HUD and of the 8 menu panels; called by `CSWGuiManager::OnResolutionChanged` | high |

A build switch at `0x007a2370` (initialised to 1, never written) chooses between creating every
menu panel up front (1, the shipped behaviour) and creating each menu panel only when it is
opened and deleting it when another replaces it (0; `CGuiInGame::SwapMenuPanel` `0x0062b1e0`).
An implementer can create everything up front. (high)

**Field map** (offsets in `CGuiInGame`; ctor addresses are the panel constructors):

| Offset | Panel | `.gui` | Ctor | Conf. |
|---|---|---|---|---|
| `+0x08` | top menu bar | `top` | `0x00627980` | high |
| `+0x0c`..`+0x28` | the 8 menu panels, indexed by the menu number below: equipment `0x006ba980`, inventory `0x006b34c0`, character `0x006b0e40`, abilities `0x006adda0`, messages `0x00626400`, journal `0x00644a40`, map `0x00694d50`, in-game options `0x006ab2f0` | `equip` ... `optionsingame` | | high |
| `+0x2c` | current menu number (0..7) | | | high |
| `+0x30` | a menu is open | | | high |
| `+0x34` | HUD mode: 1 game (HUD shown), 2 conversation, 3 menu (both hide the HUD) | | | high |
| `+0x38` | `CSWGuiManager*` | | | high |
| `+0x3c` | the active conversation panel (`+0x40` or `+0x44`) | | | high |
| `+0x40` | conversation panel | `dialog` | `0x006a8b40` | high |
| `+0x44` | computer panel | `computer` | `0x006a8eb0` | high |
| `+0x48` | computer camera panel | `computercamera` | `0x006a95f0` | high |
| `+0x4c` | bark bubble | `barkbubble` | `0x006a9770` | high |
| `+0x50` | info box ("Close" button) | `confirm` | `0x006ce9c0` | high |
| `+0x54` | container | `container` | `0x006b6dc0` | high |
| `+0x58`, `+0x5c`, `+0x70`, `+0x74` | debug panels | `debug` | `0x006d0620`, `0x006bdc60`, `0x006cfa70`, `0x006cf5a0` | med |
| `+0x60`, `+0x64` | top and bottom letterbox bars | none | `0x006a8930` | high |
| `+0x68` | conversation fade layer | none | `0x006a8930` | med |
| `+0x6c` | global fade | `fade` | `0x00624810` | high |
| `+0x78` | party selection | `partyselection` | `0x006bfa40` | high |
| `+0x7c` | pause banner | `pause` | `0x006c03b0` | high |
| `+0x80` | galaxy map | `galaxymap` | `0x00695180` | high |
| `+0x84` | store | `store` | `0x006c1c00` | high |
| `+0x8c` | solo-mode confirmation box | `confirm` | `0x006c2270` | high |
| `+0x90` | HUD (`CSWGuiMainInterface`) | `mipc2*` | `0x0068c100` | high |
| `+0x94` | area-transition label | `areatransition` | `0x006c7d50` | high |
| `+0x98` | message box | `confirm` | `0x00626df0` | high |
| `+0x9c` | skill info popup | `skillinfo` | `0x006ce7c0` | high |
| `+0xa0` | tutorial box | `confirm` | `0x006aa100` | high |
| `+0xa4` | controller-disconnected box | `confirm` | `0x00626df0` + vtable `0x007513f8` | high |
| `+0xa8` | status summary | `statussummary` | `0x006272a0` | high |
| `+0xac` | saved status-summary data, copied into a re-created `+0xa8` | | | med |
| `+0xb0` | a conversation is shown | | | med |
| `+0xb4` | conversation/cutscene in progress (menus refuse to open) | | | med |
| `+0xb38` / `+0xb3c` | game paused / pause banner wanted (see `SetPauseState`) | | | high |
| `+0xbc8` | messages panel shows feedback (1) or dialogue history (0) | | | high |

##### Menus: opening, switching, closing

The 8 in-game menus are numbered **0 equipment, 1 inventory, 2 character, 3 abilities, 4 messages,
5 journal, 6 map, 7 options**; `+0x0c + 4·n` holds panel n. The key actions `0xd1`..`0xd8` map to
menus 0..7 in that order (`CClientExoAppInternal::HandleInputAction` `0x00621210`), the HUD buttons
`BTN_EQU`, `BTN_INV`, `BTN_CHAR`, `BTN_ABI`, `BTN_MSG`, `BTN_JOU`, `BTN_MAP`/`BTN_MINIMAP`, `BTN_OPT`
likewise. (high)

`CGuiInGame::ShowInGameMenu(n)` (`0x0062c9b0`), in order:

1. Refuse if the panels do not exist yet. Set the sound mode to 4 (`CExoSound::SetSoundMode`,
   muffled world), clear the client's examine target, switch the HUD to mode 3 (hides it).
2. Run the script `k_sup_guiopen` (no caller object).
3. Choose the menu: n if 0..7; otherwise keep the last one, except that when the party leader has
   a level-up pending (`0x005a6810`) the character sheet (2) is chosen.
4. Add the top bar (flags 0) and the menu panel with flags 2 (full-screen: centred, with the
   resolution backdrop), bring the menu to the front, select the matching tab in the top bar.
5. `+0x30` = 1. If the game was not already paused by the player (`+0xb38` = 0), toggle the
   server's pause bit 2 (`0x00677800` → `0x004ba610`): **menus pause the game**.
6. Hide the bark bubble (pauses its voice) and run `k_pend_screenchg`; play GUI sound 4.

The caller then switches the client input class to 2 (GUI) (`0x005eda60` → `0x006200e0`). When a
menu is already open, a menu key for another menu calls `SwitchInGameMenu(n)` (`0x0062cf10`: remove
the old panel, add the new one with flags 2, select its tab, run `k_pend_screenchg`); the key of the
menu that is open closes it. The top bar's prev/next events step through 0..7 with wrap-around
(`0x0062cdf0`, `0x0062ccd0`). Esc (key action `0xdf`) closes an open menu, and when no menu is
open (game input class) opens menu 7, the in-game options, and sends client request 7 (asm at
`0x0062147e`). While the player controls an unconscious character (`0x005f2ed0`) the menu keys do
nothing and Esc shows the message box with 42628 "You can't access the Start Menu while controlling an
unconscious character.". The menus refuse to open during a conversation (`+0xb4`) or while a modal
panel is up (`manager+0x98` non-zero). (high)

`CGuiInGame::HideInGameMenu(bNoPauseBanner)` (`0x0062cba0`): refuses while a modal panel is up;
otherwise HUD back to mode 1, removes the top bar and the menu panel, `+0x30` = 0; if the player
had not paused, toggles pause bit 2 back off; if the player had paused, re-adds the pause banner
(unless `bNoPauseBanner`); shows the bark bubble again, plays GUI sound 5, sound mode 0. The
caller returns the input class to 0 (game). (high)

`CGuiInGame::SetHudMode(nMode, b)` (`0x0062aa00`): 1 (unless the mode is 3) or 4 (unless the mode
is 2) → mode 1, 2 → 2, 3 → 3 (unless 2). In mode 1 the HUD is added with flags 4 (overlay) and
brought to the front, and the pause banner is re-added if the game is paused; in modes 2 and 3 the
HUD is removed and, when `b`, the pause banner is taken down. (high)

##### Pause banner, status summary, fades, conversations

| Address | Name (ours) | What | Conf. |
|---|---|---|---|
| `0x0062def0` | `CGuiInGame::SetPauseState(bPaused, nReason)` | called by the client main loop when the pause state changes; for reasons 1, 4, 5, 7..11 sets the banner text (`CSWGuiPause::SetReason`) and shows the banner (flags 4) while the HUD is up; stores `+0xb38` = paused, `+0xb3c` = banner wanted; unpausing removes it | high |
| `0x0062eeb0` | `CGuiInGame::AddStatusSummaryEvent(nKind, nValue)` | accumulates into the status-summary panel: 0 journal updated, 1 credits (+/-), 2 XP, 3 stealth XP, 4/5 alignment shift (light/dark), 7 item received, 8 item lost, 9 level-up ready, 10 and 11 extra sounds; a positive suppress counter (`summary+0x78`, set by `0x0062f0c0`) swallows events | high |
| `0x0062ef90` | `CGuiInGame::FlushStatusSummary` | each frame (client main loop): if something is pending and the option "Status Summary" (client options `+0x14` bit 5) is on, pauses (client pause reason 6) and shows the summary modally; otherwise plays its sounds, flashes the matching HUD icons and clears the data | high |
| `0x0062b0b0` | `CGuiInGame::FlashHudIcon(n)` | forwards to the HUD (`0x00687fe0`) | high |
| `0x0062abf0` | `CGuiInGame::StartGlobalFade(bFadeIn, fWait, fLength, color)` | `SetGlobalFadeIn/Out` (`0x00546010`, `0x005460d0`): adds the fade panel (flags 4) and starts it | high |
| `0x0062b730` | `CGuiInGame::ShowConversationPanel` | conversation start: input class 3, hides the bark bubble, for the ordinary conversation adds the fade layer, the top bar (grows) and the bottom bar (slides), then the conversation panel with flags 0 (computer: flags 2, full-screen with the `comp` backdrop); HUD mode 3. Flow is in [dialogue.md](dialogue.md) | med |
| `0x0062e550` | `CGuiInGame::ShowSoloModeConfirm(bForStealth)` | only with more than one party member, no conversation, leader alive; pauses (bit 2) unless paused, shows the solo box modally (flags 1), input class 2; otherwise GUI sound 2 (refusal) | high |
| `0x0062e6d0` | `CGuiInGame::CloseSoloModeConfirm` | unpauses, pops and removes it, input class 0 | high |
| `0x0062d3e0` / `0x0062d440` | `CGuiInGame::ShowInfoBox(strref)` / `CloseInfoBox` | the "Close" box at `+0x50`; used by party selection | med |
| `0x0062b000` | `CGuiInGame::SetHudTarget(objectId)` | forwards to `CSWGuiMainInterface::SetTargetObject` (`0x006855f0`) | high |

#### CSWGuiMainInterface: the HUD

`.gui`: `mipc28x6` (800x600 and any unlisted size), `mipc210x7` (1024x768), `mipc212x9`
(1280x960), `mipc212x10` (1280x1024, `patch.erf`), `mipc216x12` (1600x1200), chosen in the
constructor (`0x0068c100`) from the manager's screen size; a 1280 width with another height loads
no `.gui` at all. The files without the `2` (`mipc8x6`, `mipc10x7`, ..., `mi8x6`,
`maininterface`) are an older layout with six action slots and `LB_ACTIONS*` lists; the code never
loads them. 0xc8cc bytes, vtable `0x00753f50`, owner `CGuiInGame+0x90`, added with flags 4
(overlay) by `SetHudMode`. The panel is not scaled: every resolution has its own pixel layout, and
for widths ≥ 1024 the panel extent is set to the whole screen. Overridden slots: 13 Render
`0x0068b4a0`, 14 Update `0x00686ba0`, 16 HitTest `0x00686b70` (the floating target block first,
then the normal panel test), 26 OnResize `0x00685760`. (high)

**Controls** (tags from `mipc28x6`; every one exists in all five files):

| Group | Tags | What | Conf. |
|---|---|---|---|
| menu buttons | `BTN_EQU`, `BTN_INV`, `BTN_CHAR`, `BTN_ABI`, `BTN_MSG`, `BTN_JOU`, `BTN_MAP`, `BTN_OPT`, background `LBL_MENUBG` | open menus 0..7 (`OnMenuButton` `0x006883c0`); tooltip strrefs 48219, 48220, 48225, 48224, 48223, 48218, 48221, 48222 with the bound key appended (key actions `0xd1`..`0xd8`); hidden while the option "Hide InGame GUI" (client options `+0x14` bit 9) is on | high |
| toggles | `TB_PAUSE`, `TB_SOLO`, `TB_STEALTH` (check boxes) | pause (key action `0xf1`, tooltip 48019), solo mode (`0xcf`, 48035), stealth (`0x108`, 247) | high |
| party | `BTN_CHAR1..3`, `LBL_CHAR1..3`, `PB_VIT1..3`, `PB_FORCE1..3`, `LBL_BACK1..3`, `LBL_LEVELUP1..3`, `LBL_LVLUPBG1..3`, `LBL_DEBILATATED1..3`, `LBL_CMBTEFCTRED1..3`, `LBL_CMBTEFCTINC1..3` | one widget per party member; slot 1 is the leader (big portrait, bottom left) | high |
| self actions | `BTN_ACTION0..3`, `BTN_ACTIONUP0..3`, `BTN_ACTIONDOWN0..3`, `LBL_ACTION0..3`, `LBL_ACTIONDESC`, `LBL_ACTIONDESCBG` | the four action slots at the bottom right | high |
| target | `BTN_TARGET0..2`, `BTN_TARGETUP0..2`, `BTN_TARGETDOWN0..2`, `LBL_TARGET0..2`, `LBL_NAME`, `LBL_NAMEBG`, `PB_HEALTH`, `LBL_HEALTHBG` | the block that floats over the selected object (design position 0,0) | high |
| combat | `LBL_COMBATBG1..3`, `LBL_QUEUE0..3`, `BTN_CLEARONE`, `BTN_CLEARONE2`, `BTN_CLEARALL`, `LBL_CMBTMODEMSG`, `LBL_CMBTMSGBG` | shown only in combat mode | high |
| minimap | `LBL_MAPBORDER`, `LBL_MAPVIEW`, `LBL_MAP`, `LBL_ARROW`, `BTN_MINIMAP`, `LBL_ARROW_MARGIN` | top left | high |
| notifications | `LBL_JOURNAL`, `LBL_CASH`, `LBL_PLOTXP`, `LBL_STEALTHXP`, `LBL_DARKSHIFT`, `LBL_LIGHTSHIFT`, `LBL_ITEMRCVD`, `LBL_ITEMLOST` | icons beside the minimap that appear for 4 s after an event | high |
| frame | `LBL_MOULDING1..3` | decoration | high |

The code looks up `LBL_DISABLED%d` for the party widgets, but the files call them `LBL_DISABLE1..3`,
so those labels are never bound and stay empty (they draw nothing). The constructor makes six
self-action widgets and four party widgets; only four and three exist in the `mipc2*` files, and an
unbound widget has a zero extent and draws nothing. Reproduce that: bind by tag, ignore missing
tags. (high)

**Construction details** (`0x0068c100`, high): after `FinishLoading` the constructor records the
minimap viewport (`LBL_MAPVIEW`'s rectangle, square, side = its width), centres `LBL_ARROW` in it,
creates the software `blackdot` quad, sets every button's tooltip strref (control `+0x24`) and
key action (control `+0x30`, whose bound key name the tooltip appends), clears the "plays click
sound" flag (control `+0x44` bit 2) on the menu, toggle and clear buttons, sets the combat-message
strref to 48208 and calls `SetCombatMode(0)`.

##### Per-frame order

`Update` (`0x00686ba0`) only: updates the floating overlay list (`+0x5cb4`, objects' slot `+0xa0`);
counts down the combat message (`+0x7724`, total `+0x7720`; the message alpha is 1 for the first
half and then falls linearly to 0; at the end the message reverts to strref 48208); sets
`TB_SOLO` visible when the party has more than one member and checked when solo mode is on
(party table `server+0x1b770`, `+400`); `TB_STEALTH` visible when the leader can stealth
(`0x00610ac0`) and checked when stealthed (creature `+0x194` bit 0); `TB_PAUSE` checked when the
game is paused by the player; the menu buttons hidden by "Hide InGame GUI". (high)

`Render` (`0x0068b4a0`) does the real refresh, only while the panel is visible and a party leader
exists:

1. count down the action-failure message timer (`+0x6c`);
2. `UpdatePartyPortraits` (`0x00687860`);
3. `UpdateReticles` (`0x0068a310`: picks `hostilereticle2`, `friendlyreticle2`, `combatreticle`,
   `hostilearrow`, `friendlyarrow` for the target marker; positions are projected from the target);
4. the target block's timers (`0x00684e70`), `UpdateActionMenus` (`0x00689d80`), the nine
   notification icons (`0x00686a20`), the leader-swap animation of the party widgets
   (`+0x5a28` seconds, `0x006851b0`);
5. `SetCombatMode(client in combat)` (`0x006874c0` with `0x005ede70`), the blink of each action
   slot (`0x006858e0`), and in combat `UpdateCombatQueue` (`0x0068a010`);
6. if the global HUD switch `0x007a2288` is on: `RenderMiniMap` (`0x0068ab10`), the panel's own
   controls (`CSWGuiPanel::Render`), the floating target block (`0x00685ed0`, its own viewport at
   the projected rectangle `+0x15ac..+0x15b8`), the overlay list, and per party widget the
   effect-count icons (`0x00685330`). (high for the order, med for the inner details)

##### Party portraits

Each party widget (0xea8 bytes, `+0x1f88 + 0xea8·i`, i = 0..2, plus a fourth at `+0x4b80` used as
the "ghost" during a leader swap; init `0x006898a0`) caches current/max vitality (`+0`/`+4`),
current/max Force (`+8`/`+0xc`), level (`+0x10`), pending levels (`+0x14`), two strings and the
counts of good/bad effects (`+0xea0`/`+0xea1`). `UpdatePartyPortraits` (`0x00687860`) walks the
client party (`0x005ed8b0`, member i via `0x006346c0`, its server creature via `0x0060fb20`):

- **Slot mapping:** member 0 (the leader) goes to widget 0 (`*CHAR1`). With exactly two members
  the companion goes to widget 2 (`*CHAR3`, next to the leader) and widget 1 is hidden; with three,
  member i goes to widget i. During the swap animation the mapping is shifted by one. Widgets
  without a member hide all their controls. (high)
- **Portrait:** the creature's portrait resref (client creature slot `+0x148`) becomes the fill of
  `LBL_CHARn`. (high)
- **Vitality:** `PB_VITn` max = max hit points (creature slot `+0x98`), value = current hit points
  (slot `+0x9c`); the bar's fill is `greenfill` or `redfill` (`0x006857d0`; which condition picks
  red is not settled). (high / low for the colour)
- **Force:** `PB_FORCEn` max = `GetMaxForcePoints`, value = the stats' current Force points
  (`+0x124` plus `+0x126`); a creature with no Force gets max 1, value 0. (high)
- **Level up:** pending levels = (level reachable with the current XP, `0x005a6610`) − current
  level (`stats+0x68`); `LBL_LEVELUPn`/`LBL_LVLUPBGn` show when the creature can level up
  (`0x005a6810`: level below the module cap, XP ≥ `g_pRules` table entry, alive). The first time,
  the tutorial event 9 is raised. (med)
- **State** (`SetStatus` `0x006867f0`): dead or debilitated (`0x004ef890`: in the party with ≤ 0
  hit points) → `LBL_BACKn` (state bit 0); debilitated/unable to act (`0x005b4880`) → state bit 1
  `LBL_DEBILATATEDn`, and for the leader the combat message 47915 "Player debilitated. Cancelling
  combat actions."; level-up ready → bit 2 (`LBL_LEVELUPn`, `LBL_LVLUPBGn`); otherwise counts the
  creature's effects (`+0x8f4` list, active ones; beneficial vs harmful by the effect's `+0x14`)
  for the red/increase icons. (med)
- **Clicking** `BTN_CHAR1` (`OnPartyMemberButton` `0x00688690`) opens the equipment menu, or the
  character sheet when a level-up is pending; clicking a companion's portrait makes that member the
  party leader (`0x005edc30`, unless it is dead). (high)
- **Tooltip:** `BTN_CHARn` is a button subclass (`CSWGuiPartyButton`, vtable `0x00753bd0`, ctor
  `0x00686ab0`) whose tooltip is "*name* ...\nVitality: *cur*/*max*\nForce: *cur*/*max*\nLevel:
  *n*\nXP Needed: *n*" (strrefs 1061, 1060, 32154, 48459; `0x00684f50`), rebuilt while it is shown
  whenever the widget's data changes (`0x00686790`). (high)

##### Action menus (self and target)

An action slot (`CSWGuiActionSlot`, 0x71c bytes, init `0x0068b9d0`) binds `LBL_%s%d` (the icon),
`BTN_%s%d` (activate), `BTN_%sUP%d`, `BTN_%sDOWN%d` with `%s` = `ACTION` or `TARGET`. Self slots
are HUD panel controls; target slots are children of the floating target block and are not in the
panel's control list (they are drawn and hit-tested by the block). Up/down buttons have tooltips
48465/48466 and key actions `0xf8`/`0xf9`; the slot tooltips are 48486 "Activate Friendly Power",
48291 "Activate Medical Item", 48299 "Activate Non-medical Item", 48295 "Activate Mine" (self slots
0..3, key actions `0xe8`, `0xea`, `0xee`, `0xec`) and 48303/48307/48311 "Activate
Left/Middle/Right Action" (target slots, `0xe2`, `0xe4`, `0xe6`). (high)

`UpdateActionMenus` (`0x00689d80`) rebuilds, every frame, six action lists in the HUD (`+0x74 +
12·k`, a growable array of 0x38-byte entries) from the leader's client creature (`0x00619db0`,
category k = 0..5; only 0..3 are shown), then the target block's three lists (`0x00689410`). An
entry holds an id (`+8`), a callback (`+0xc`), a target object (`+0x1c`), an icon resref (`+0x20`)
and flags (`+0x30`: bit 0 usable, bits 1..4 a reason code). The selected entry id of each slot is
kept in `+0x1bac + 4·k` (-1 none); the icon is drawn at alpha 1 when usable, 0.25 otherwise; the
up/down arrows show when the list has more than one entry. How the lists are built (which talents,
items and targeted actions qualify) belongs to [actions.md](actions.md) and
[combat.md](combat.md). (med)

The mine slot (category 3, `0x00619db0` → `0x006197d0` with mask 2): three items on the client creature
(likely worn, only where combat is allowed), then the leader's item repository (`GetItemRepository(1)`);
`0x00616520` keeps an item whose baseitems `itemtype` is 28 (Trap_Kit) with a usable Trap property (46),
for a creature that can use Demolitions (`0x005af880(stats, 1)`: not usable untrained, so a base rank of
1 or more) and passes CanUseItem; non-plot items are dropped where the area forbids combat. The entry
(`0x006193a0`) is labelled "<item name> (self)" (`"%s (%s)"`, 38005), shows the item's own icon, its id
is the item's with bit 0x40000000, its target the leader, its count the stack ("%s (%d)" above 1), and it
is never dimmed. Its callback (`0x0060f590`) sends input 9 (`0x00677bd0`): the item, the leader as the
target and a zero point, which UseItem turns into SETTRAP ([actions.md](actions.md) 3.14). (high)

Clicking a self slot (`UseSelfAction` `0x0068ad60`): if the entry is not usable, its reason code
picks a message shown for 5 s in the combat message bar: 1 "Force Depleted" (38613), 2
"Restricted by Armor" (38614), 3 "Missing Item" (38615), 4 "Target too Close" (42422), 5 "Full
Health" (42498), 6 "PC Dead" (47936); GUI sound 2. If usable: when the leader's client creature
flag `+0x440` bit 0 is clear, `0x0063d490` runs and GUI sound 6 plays; when it is set and the game
is paused (client `+0x384` bit 0), the pause banner switches to reason 10 ("Action added to
queue."); then the entry's callback runs with its id and the leader (it posts the request to the
server side), the slot blinks twice (0.1 s per phase, `0x006858e0`), and when the flag is clear the
leader's server actions are cleared at once, so the new request replaces them instead of queueing
behind them (med: the flag's meaning is inferred from this use). Up/down
(`0x0068af70`/`0x0068afe0`) cycle the slot's selection with wrap-around (GUI sound 7), pausing with
reason 7 when the "Action Menu" auto-pause option (client options bit 15) is on. Hovering a slot
records it as the current one (`+0x1bc4`). `LBL_ACTIONDESC` shows the hovered entry's description,
its height fitted to the text and anchored at the bottom (`SetActionDescription` `0x00685560`).
(high)

##### Combat mode, queue, clear buttons

`SetCombatMode(b)` (`0x006874c0`) shows or hides the combat controls and moves the minimap group
(`LBL_MAPBORDER`, `LBL_MAP`, `BTN_MINIMAP`, the minimap viewport and the nine notification icons)
down by the combat-message bar height (`+0xa458`) when combat starts and back up when it ends. In
combat `UpdateCombatQueue` (`0x0068a010`) walks the leader's server action queue (creature
`+0xfc`) and puts up to four icons in `LBL_QUEUE0..3` (attack-type actions and the current combat
action's sub-actions), hiding the unused ones. `BTN_CLEARONE`/`BTN_CLEARONE2` (tooltip 48456 "Clear
Combat Action", key action `0xf5`) remove the last queued action (client request `0x20`, falling
back to `0x006880c0`); `BTN_CLEARALL` (48518 "Disengage", `0xf0`) ends combat for the leader and
clears its actions (`0x006887d0`). (high for the wiring, med for the queue filter)

##### Minimap

`RenderMiniMap` (`0x0068ab10`) runs when the option "Mini Map" (client options `+0x14` bit 3) is on
and the module's area map (`module+0x218`) has a map. The map texture is `lbl_map` + the module's
area resref (`0x00687e40`, format `lbl_map%s`), loaded once into `LBL_MAP`. Each frame the
leader's position is converted to map pixels (area map `0x005791b0`/`0x00579090`), `LBL_MAP` is
offset so that point sits at the viewport centre, and the arrow's rotation is the leader's facing
plus the map's north offset (0, 180, 90 or 270 degrees by the area map's orientation `+0x10`;
`0x00578ed0`). Drawing: a viewport of `LBL_MAPVIEW`'s square, `LBL_MAP`, then markers
(`0x00688100`), then `LBL_ARROW`. Clicking the minimap opens the map menu. The map logic itself
(map points, notes) is with the map panel. (med)

##### Notification icons

Nine labels (`CSWGuiNotifyLabel`, 0x14c bytes, `+0xa460 + 0x14c·i`, init `0x00686920`) indexed 0
journal, 1 cash, 2 plot XP, 3 stealth XP, 4 dark shift, 5 light shift, 6 unused, 7 item received,
8 item lost. `FlashNotifyIcon(i)` (`0x00687fe0`) makes icon i visible for 4.0 s (hiding the opposite
alignment icon) and marks it new; their borders pulse. Called when the status summary is not shown
(`FlushStatusSummary`). (high)

##### Toggles

- `TB_PAUSE` (`0x00688590`): requests the opposite of the current player pause (client
  `0x005edc20`, reason 4), clears client flag `+0x384` bit 0 if set (`0x005edee0`), and sends client
  request 6 (`0x005edf40`). The pause logic is in [gameloop.md](gameloop.md). (high for the calls)
- `TB_SOLO` (`0x00688610`): opens the solo-mode confirmation (below). (high)
- `TB_STEALTH` (`0x00688640`): when the leader can stealth, toggles stealth (`0x0060f4b0`). (med)

#### CSWGuiTopMenu: the tab bar of the in-game menus (`top`)

0x1c24 bytes, ctor `0x00627980`, vtable `0x00750148`, owner `CGuiInGame+0x08`; panel flags `0x60`
(centred as a 640-wide panel at the top: the root is 640x86). Controls: `LBLH_EQU`, `LBLH_INV`,
`LBLH_CHA`, `LBLH_ABI`, `LBLH_MSG`, `LBLH_JOU`, `LBLH_MAP`, `LBLH_OPT` (type 5 highlight frames) and
`BTN_EQU` ... `BTN_OPT` (52x40 tab buttons) with the same tooltips and key actions as the HUD.
Each tab button calls `SwitchInGameMenu` with its menu number (`0x00624cf0` equip 0, `0x00624d10`
inventory 1, `0x00624d30` character 2, `0x00624d70` abilities 3, `0x00624dd0` messages 4,
`0x00624d90` journal 5, `0x00624d50` map 6, `0x00624db0` options 7). Its input handler
(`0x00624970`) turns key actions `0xf3`/`0xf4` into events `0x35`/`0x36`, which every `LBLH_*`
answers with previous/next menu (`0x00624c00`/`0x00624c30`). `SelectTab(n)` (`0x00624bd0`) makes
tab n the active control. Update (`0x00624c60`) makes `LBLH_INV` pulse while the player's quest
item repository is non-empty (low: probably "new items") and `LBLH_JOU` pulse while any journal
entry carries the "new" flag (`0x00676470`, entry byte `+0x2c` bit 2). All tags verified against
`top.gui`. (high)

#### CSWGuiMessages: message log (`messages`)

Menu 4. 0xaf4 bytes, ctor `0x00626400`, vtable `0x0074fd18`. Controls: `LB_MESSAGES` (feedback
log) and `LB_DIALOG` (conversation history), both 544x289 at the same place, with 64 preallocated
proto rows each; `LBL_MESSAGES` (title); `BTN_SHOW` (toggle, sends event `0x29`); `BTN_EXIT`
(sends `0x28`). `OnPanelAdded` (`0x00626d90`) shows the view remembered in `CGuiInGame+0xbc8`.
`ShowDialogLog` (`0x00624df0`): `LB_DIALOG` visible, button text 42142 "Show Feedback", title
"Messages - Dialog" (strrefs 1563, 371), remembers 0. `ShowFeedbackLog` (`0x00624f70`):
`LB_MESSAGES` visible, button 42143 "Show Dialog", title "Messages - Feedback" (42167), remembers
1. Input (`0x00628260`): events `0x28`, `0x2d`, `0x2e`, `0xdf` close the menu
(`HideInGameMenu`) and return to the game input class; `0x29` toggles the view. The panel also
watches the event sequence `0x29, 0x2f, 0x27, 0x29` and then shows a hidden feedback line and
sets a flag (`0x008338e8`) that the free-camera key reads: an easter egg, safe to skip. How the
log lines are filled is not traced (the log lives in the client). All tags verified. (high /
low for the filling)

#### CSWGuiMessageBox: the confirm/OK box (`confirm`) and its variants

0x984 bytes, ctor `0x00626df0`, vtable `0x0074fdb0` (32 slots: the panel's 27 plus five).
`confirm.gui` is a 290x87 box: `LB_MESSAGE` (one proto row, `dialogfont16x16`, centred text),
`BTN_OK` (strref 1580 "OK"), `BTN_CANCEL` (1581 "Cancel"); the constructor adds a hidden 32x32 icon
label at (0,10) (`+0x1b4`). It is centred on the screen and shown with `AddPanel(box, 1, 1)`
(modal). (high)

| Slot / address | Name (ours) | What | Conf. |
|---|---|---|---|
| slot 27 `0x006249d0` | `SetMessageStrRef(strref)` | TLK text, then slot 28 | high |
| slot 28 `0x006271a0` | `SetMessageText(text)` | resolves TLK tokens (`CTlkTable::ParseStr`), puts the text in the list box and re-fits the box (`FitToText` `0x006253a0`) | high |
| slot 29/30 `0x00625260`/`0x00625270` | `SetOkStrRef`/`SetCancelStrRef` | button captions | high |
| slot 31 `0x00625280` | `HideButtons` | flag bit 3, hides both buttons (a "please wait" box) | high |
| slot 15 `0x006250f0` | `HandleInputEvent` | see below | high |
| slot 18 `0x006258f0` | `OnPanelAdded` | saves the client input class and switches to 2 (GUI); makes `BTN_OK` the active control; saves the cursor and moves it to the centre of `BTN_OK`, or of `BTN_CANCEL` in OK/Cancel mode (unless `+0x980` is set) | high |
| slot 19 `0x00625a00` | `OnPanelRemoved` | restores the input class and the mouse position | high |
| `0x00627130` | `SetConfirmMode(b)` | b = 1: OK and Cancel, open sound 15; b = 0: OK only, open sound 2 | high |
| `0x00624a40` | `SetCallback(owner, fn, param)` | called with `param` (owner as `this`) when the box closes | high |
| `0x00627160` | `SetIcon(resref)` | shows the icon label (flag bit 4) | high |
| `0x00625a80`/`0x00625aa0` | `OnOk`/`OnCancel` | resend as events `0x1f6`/`0x1f7` | high |

Flags at `+0x64`: bit 0 result (1 = OK), bit 1 OK/Cancel mode, bit 2 buttons shown, bit 3 no
buttons, bit 4 icon. `BTN_OK` is visible when bit 2 is set, `BTN_CANCEL` when bits 1 and 2 are, the
icon when bit 4 is (`0x00625200`). **Closing** (`HandleInputEvent`): event `0x1f6` (OK) sets the
result to 1; `0x1f7` (Cancel) and the cancel keys `0x28`/`0x2e` set it to 0 in OK/Cancel mode and
to 1 otherwise; then the flags reset to "buttons shown", slot 32 runs, the box is marked for
removal after drawing, `PopModalPanel`, GUI sound 0, and the callback runs. Up/down (`0x39`/`0x3a`)
scroll the message list. **Fitting** (`0x006253a0`): each button widens in 10-pixel steps until its
caption fits on one line; the box then grows in 40-pixel steps up to 440 pixels wide, and in
row-height steps up to 280 high, until the message list shows every line; it is re-centred. (high
/ med for the fitting numbers)

Typical use (quit confirmation, `0x005f6960` and `0x006ab1b0`): take `CGuiInGame+0x98`,
`SetConfirmMode(1)`, `SetCallback`, `SetMessageStrRef(42348)` "Do you really want to quit?",
`AddPanel(box, 1, 1)`, switch the input class to 2. (high)

Variants (all `confirm.gui`):

| Owner | Ctor / vtable | What | Conf. |
|---|---|---|---|
| `CGuiInGame+0xa0` | `0x006aa100` / `0x00755cd0` | **tutorial box** (`CSWGuiTutorialBox`): message font `fnt_d16x16`; pauses the game when shown (client reason 2) unless already paused; OK/accept pages through `tutorial.2da` row (`+0x994`): columns `Message0..2` give the pages, `Icon` the icon; the OK caption is 38623 "Continue" while pages remain, else 1580 "OK" (`NextPage` `0x006aa670`) | high |
| `CGuiInGame+0xa4` | `0x00626df0` + `0x007513f8` | controller-disconnected box (Xbox heritage): OK only, message 48398, callback `0x00625a40` | high |
| `CGuiInGame+0x8c` | `0x006c2270` / `0x00756f28` | **solo-mode box**: `SetMode(bForStealth)` (`0x006c24a0`) picks 37889 "turn Solo Mode on?", 37890 (stealth needs solo), 37891 "turn Solo Mode off?", 37892 (off also ends stealth); OK toggles solo mode (`0x005ede60`) and, for the stealth case, requests stealth (`0x0060ee00`); any close calls `CloseSoloModeConfirm`; its Render closes it by itself if a conversation starts or the leader dies | high |
| `CGuiInGame+0x50` | `0x006ce9c0` / `0x007579c8` | info box: OK caption 1582 "Close", OK only; closing calls `CloseInfoBox` | high |

#### CSWGuiStatusSummary (`statussummary`)

0x1b44 bytes, ctor `0x006272a0`, vtable `0x0074ff68`, owner `CGuiInGame+0xa8`, 322x332 centred.
Rows (icon label + description label): `LBL_JOURNAL`, `LBL_CREDITS`, `LBL_XP`, `LBL_STEALTH`,
`LBL_DARKSIDE`, `LBL_LIGHTSIDE`, `LBL_RECEIVED`, `LBL_LOST` with `*_DESC`; `BTN_OK`. The code also
asks for `LBL_NETSHIFT`/`LBL_NETSHIFT_DESC`, which the file lacks. Data: flags `+0x64` (bit 0
pending, bit 2 item received, bit 3 item lost, bit 4 journal, bit 8 credit sign changed, bits 5..7
extra sounds 12/13/14), light/dark shift bytes `+0x68`/`+0x69`, credits `+0x6c`, XP `+0x70`,
stealth XP `+0x74`. `OnPanelAdded` (`0x00625c60`) plays the extra sounds, then lays out only the
rows that have something, top to bottom from y = 10, with texts such as 42437 "Credits Received:
<CUSTOM0>", 42627 "Credits Lost: <CUSTOM0>", 42438 "Experience Points (XP) Received: <CUSTOM0>",
47933 "Net Change: " prefix (custom token 0 is set to the number). Accept/cancel keys
(`0x00625ac0`) remove it, return to the game input class and unpause unless the game was paused
before (`+0x7c` bit 0). Skimmed: the exact row spacing. (high / med)

#### CSWGuiFade (`fade`)

0x1b8 bytes, ctor `0x00624810`, vtable `0x0074fc60`, owner `CGuiInGame+0x6c`. `fade.gui` is a
1600x1200 `blackfill` panel with `LBL_MSG`; the code forces the extent to the screen size and the
panel colour to the fade colour, so it is a full-screen coloured quad. `Start(bFadeIn, fWait,
fLength, color)` (`0x006244e0`) sets the colour and the starting alpha (1 for a fade-in, 0 for a
fade-out) and an elapsed time of 0.1 s. Render (`0x00624570`) advances the elapsed time with the
real-time millisecond clock (steps over 5 s are dropped; nothing advances while the game is
paused by `0x0062fad0`); after `fWait` the alpha is (elapsed − wait) / length, clamped to 0..1,
inverted for a fade-in. The panel ignores the mouse once its alpha is ≤ 0.001 (HitTest
`0x006246a0`), so a finished fade-out blocks clicks and a finished fade-in does not. `LBL_MSG`
text can be set from a strref (`0x006246c0`). (high)

#### Letterbox bars and conversation fade (`CGuiInGame+0x60`, `+0x64`, `+0x68`)

Three 0xa4-byte panels without a `.gui` (ctor `0x006a8930`, vtable `0x00755a78`; colour from
`0x00833910`, black): the top bar (`InitTopBar` `0x006a74b0`, mode 1: grows downward from height 0),
the bottom bar (`InitBottomBar` `0x006a7540`, mode 2: slides up from the screen bottom; when it
arrives `0x0062ab90` notifies the conversation panel), and a fade layer (mode 3, timed like the
global fade, `0x006a7620`). Render `0x006a7680` advances at most 0.5 s per frame. Added by
`ShowConversationPanel` for ordinary conversations; the bar height comes from the conversation
panel's layout. Behaviour belongs to [dialogue.md](dialogue.md). (med)

#### CSWGuiBarkBubble (`barkbubble`)

0x1cc bytes, ctor `0x006a9770`, vtable `0x00755c60`, owner `CGuiInGame+0x4c`; `LBL_BARKTEXT`
(`fnt_d16x16`, centred). `ShowBark(speaker, text, flags)` (`0x006a9920`, called from four
`CGuiInGame` functions): resolves TLK tokens with the player as the token subject, sets the text,
sets the box height to text height + 10 + 2 × border, the display time to 1 + 0.11 × (text length)
seconds, and plays the line's voice as a streaming sound (positional at the speaker when there is
one). Render (`0x006a9ce0`): stretches the box to the screen width minus twice its design margin
when the HUD is hidden, moves it down by the combat bar in combat, and closes it when the time is
up and the voice has finished, or when the speaker is 6 m or more from the leader (unless flag bit
0). Opening a menu suspends it (`0x006a9bb0`, pauses the voice), closing resumes it
(`0x006a9c10`). Flow in [dialogue.md](dialogue.md). (high)

#### CSWGuiAreaTransition (`areatransition`)

0x438 bytes, ctor `0x006c7d50`, vtable `0x00757508`, owner `CGuiInGame+0x94`; 400x82 panel with
`LBL_TEXTBG`, `LBL_ICON`, `LBL_DESCRIPTION`; flags `0x20` (centred horizontally as a 640 panel).
`SetTransitionObject(id, ...)` (`0x006c7ec0`) takes the hovered door's or trigger's name (object
types 10 and 7) and keeps only the part after the first "- ", e.g. "Taris - Upper City" → "Upper
City". Render (`0x006c8050`) places it below the top HUD elements (`0x0062ebe0`) and colours text
and frame by whether the party can use the transition (`0x00635350`). Shown while the cursor is
over a transition; the hover logic is in [movement.md](movement.md). (high / med)

#### CSWGuiToolTip (`tooltipWxH`)

0x1a4 bytes, ctor `0x006277c0`, vtable `0x00750030`, owned by the manager (`+0x3c`). File by
resolution: `tooltip16X12` (1600 wide), `tooltip12X9` (1280x960), `tooltip12x10` (1280x1024),
`tooltip10X8` (1024), `tooltip8X6` (800), else `tooltip6X4`; one label `tooltip` (border
`confirm5`/`confirm6`, fill `dialog3`, `dialogfont16x16`, centred). Shown by
`CSWGuiManager::ShowTooltip(text)` (`0x0040b490`) only when the option "Enable Tooltips" (client
options `+0x14` bit 10) is on: manager flag bit 3 set, `SetText` (`0x00624ae0`), `PlaceAtCursor`
(`0x00624af0`): size = text extent + 8 pixels each way, position = cursor + 15 pixels, pulled back
inside the screen with a 2-pixel margin. Sources: the hovered control's tooltip slot after the
manager's hover delay (strref `+0x24` plus the bound key) and the party buttons. (high)

#### CSWGuiSkillInfo (`skillinfo`) — skimmed

0x24e8 bytes, ctor `0x006ce7c0`, vtable `0x00757940`, owner `CGuiInGame+0x9c`, centred 333x231:
`LBL_MESSAGE`, `LB_SKILLS` (ten preallocated rows), `BTN_OK`. Accept/cancel keys close it
(`0x006cd3c0`). Filled by the abilities panel (`0x006adb00` → `0x006ce370`), the Force-power
level-up (`0x006f2180` → `0x006ce0f0`) and the feats panel (`0x006f3460` → `0x006ce570`); contents
not traced. (med)

#### CSWGuiPause (`pause`)

0x4b0 bytes, ctor `0x006c03b0`, vtable `0x00756dc8`, owner `CGuiInGame+0x7c`; 251x70 panel:
`LBL_PAUSEREASON`, `LBL_PRESS` (strref 48384 "PRESS THE PAUSE BUTTON TO CONTINUE", token-parsed at
construction), `BTN_UNPAUSE` (a button covering the banner; clicking it toggles the pause,
`0x006c0350`). `SetReason(n)` (`0x006c00c0`) picks the text: 1 → 48212 "ENEMY SIGHTED! ..." and 11 →
49118 "MINE SIGHTED! ..." (both without `LBL_PRESS`), 5 → 42432 "End of Combat Round", 7 → 42482
"Menu Used", 8 → 42481 "Target Changed", 9 → 42397 "Party Member Down", 10 → 48423 "Action added to
queue.", anything else → 1508 "PAUSED"; the panel's height is refitted to the texts. OnPanelAdded
(`0x006c02f0`) centres it during a conversation, otherwise asks `CGuiInGame` for its place
(`0x0062b100`). Added with flags 4 by `SetPauseState`/`SetHudMode`. (high)

#### Debug panels (`debug`) — skimmed

Four panels on `debug.gui` (`LBL_BUILD` "Build: ...", `LB_OPTIONS`) at `CGuiInGame+0x58`
(`0x006d0620`, lists `baseitems` labels: an item spawner), `+0x70` (`0x006cfa70`, lists modules
from `MODULES:` and `live%d` / `_s.rim` names: a warp list), `+0x74` (`0x006cf5a0`) and `+0x5c`
(`0x006bdc60`); closed by `0x0062d360`. Developer tools; not needed for the game. (med)

### 10.4 The in-game menus

#### Conventions shared by the in-game menu panels

These apply to every panel in this group; the per-panel sections only list what differs.

**Owner and lifetime.** All of them except the upgrade bench, quest items and script select are
built once by `CGuiInGame::CreatePanels` (0x00632860) and kept in the in-game GUI object
(`CGuiInGame`, `CClientExoApp::GetInGameGui` 0x005ed690). Fields: +0x0c equipment, +0x10
inventory, +0x14 character, +0x18 abilities, +0x20 journal, +0x24 map, +0x54 container, +0x78
party selection, +0x80 galaxy map, +0x84 store (high, read in CreatePanels). The eight menu
panels at +0x0c..+0x28 are the ones the HUD's menu buttons and the top bar switch between (see
the HUD / top-bar section); quest items is owned by the journal (+0xfb4), script select by the
character sheet (+0x59f4), the upgrade panels by the item-select panel (below). (high)

**Buttons forward to the panel's own input handler.** Most buttons do not get a dedicated
callback; they get one of five tiny shared callbacks that re-send a gamepad-style event to the
panel's `HandleInputEvent` slot (vtable +0x3c) through the panel slots 20..24:

| Address | Proposed name | Event re-sent | Typical use | Conf. |
|---|---|---|---|---|
| 0x00624ba0 | `CSWGuiPanel::OnButtonAccept` | 0x27 | Use, Level Up, Accept, OK, Party Select | high |
| 0x00624bb0 | `CSWGuiPanel::OnButtonCancel` | 0x28 | Exit / Back / Cancel | high |
| 0x00624bc0 | `CSWGuiPanel::OnButtonX` | 0x29 | inventory filter, journal quest items, character scripts, map return, container give | high |
| 0x00644720 | `CSWGuiPanel::OnButtonY` | 0x2a | character auto-level, journal swap active/completed | high |
| 0x00644730 | `CSWGuiPanel::OnButtonZ` | 0x2b | journal sort | high |

So a keyboard/gamepad press and a mouse click on the button take the same path. An implementer
can give each panel one `handle_event(code)` and bind buttons to codes. (high)

**Closing a menu panel.** Events 0x28, 0x2d, 0x2e and 0xdf close the in-game menu (inventory,
equipment, character, abilities, journal, map): `CGuiInGame::HideInGameMenu` (0x0062cba0) refuses
while any modal panel is up, removes the menu bar and the current menu panel, restores the HUD
(re-adding the pause panel when needed), plays GUI sound 5, sets sound mode 0, and returns 1; the
caller then puts the client back into input class 0 (game) with `CClientExoApp::SetInputClass`
(0x005eda60 → 0x006200e0). Which keys produce 0x2e/0xdf is not traced (likely Esc and the menu's
own toggle key). (med)

**Closing a popup panel** (quest items, script select, upgrade item list): `PopModalPanel` and
`CSWGuiPanel::MarkForRemoval` (0x00624a00), which sets panel flag 0x200 (or keeps 0x400) so the
manager removes it after drawing, flag bit 8 from the argument. (high)

**Scrolling the description box.** Events 0x39/0x3a (up/down navigation) are turned into 0x31/0x32
and sent to the panel's description list box, so the up/down keys scroll the item or quest text
while the item list keeps keyboard focus. (high)

**Message boxes.** Refusals ("you cannot ...") all use the shared message box at `CGuiInGame`
+0x98: `CSWGuiMessageBox::SetConfirmMode(0)` (0x00627130, sets +0x64 bit1 and the open sound +0x60
to 2 or 0xf), the text slot (vtable +0x6c) with a strref, `CSWGuiMessageBox::SetCallback(owner,
fn, data)` (0x00624a40, stores +0x6c/+0x68/+0x70), then `AddPanel(box, 1, 1)` (modal). (high)

**Tutorial pop-ups.** Opening or using a panel calls `CClientExoApp::ShowTutorialPopup(id, ...)`
(0x005edf40 → 0x005f4120): when the "Tutorial Popups" option (client options +0x14 bit1) is on,
the id is below 0x2b and its bit in the shown-set at `CGuiInGame` +0xba8 is clear, it opens the
tutorial panel (`CGuiInGame` +0xa0) and returns 1. Ids seen here: 0x14 inventory opened, 0x0b
equipment slot opened, 0x0d map opened, 0x27 return-to-base pressed. (med)

**Switching character (BTN_CHANGE1, BTN_CHANGE2, key event 0xce).** Inventory, equipment,
character sheet and abilities share one scheme:

- The two buttons show the portraits (creature vtable +0x148) of party members 1 and 2 of the
  client party list (the list from 0x005ed8b0, member n via 0x006346c0); a button is hidden (flag
  bit1 cleared) when that member does not exist. Tooltip strref 38693 "Change Character" plus the
  name of the key bound to input event 0xce (control +0x24 tooltip strref, +0x30 bound event).
- Clicking BTN_CHANGE1 cycles the party leader one step, BTN_CHANGE2 two steps
  (`CClientExoApp::CyclePartyLeader(0, 0, n)` 0x005edf80 → 0x005f7960, which skips dead or
  unavailable members and refuses during some states); the panel then re-reads the leader and
  refreshes. Event 0xce does the same with one step. GUI sound 1 plays. (high)
- When a server-side flag is set (server internal +0x10004 object, +0x104 bit0; meaning not
  established, plausibly the player-restrict / "view only" mode), the buttons instead cycle the
  *viewed* character through the nine NPC slots of the party table (`CServerExoApp::GetPartyTable`
  0x004aee70 = server internal +0x1b770; slot available `CSWPartyTable::IsNPCAvailable` 0x005636b0;
  creature from 0x00564700) without changing the leader, and BTN_CHARLEFT/BTN_CHARRIGHT step
  backwards/forwards. The panel remembers the viewed NPC index (-1 = the player). (med)

**Item rows.** Inventory, equipment, container and quest items fill their list boxes with a
shared row control, `CSWGuiItemEntry` (ours; 0x39c bytes, ctor 0x006b7ee0, vtable 0x007568f8, a
button with an extra icon border, stack-count text and state). `CSWGuiItemEntry::SetItem(id,
bEquipped, bNew)` (0x006b6710) fills it (high):

- item id at +0x1c4, flags at +0x394 (bit1 equipped, bit2 new);
- name = the item's localized name (item +0x280), with " (Equipped)" (strref 32346) appended
  when equipped; name colour normal blue (0x007a23b4, image value 0.0/0.66/0.98) with yellow
  hilight (0x007a23c0, 0.98/1.0/0.0), or (0.95/0.0/0.85) from 0x007a23fc for *new* items;
- icon = the item's icon resref (`CSWSItem::GetIconResRef` 0x005556b0) drawn inside a hexagon
  frame: `lbl_hex_3` for a single item, `lbl_hex_6` for stacks of 2..99, `lbl_hex_7` for 100 and
  more; the stack size (item +0x28c) is printed with font `fnt_d16x16`, alignment 0x22
  (bottom centre) when the stack is 2 or more;
- an empty row (id `OBJECT_INVALID`) reads "None" (strref 363) with icon `inone`.

#### CSWGuiInventory (inventory.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006b34c0 | `CSWGuiInventory::CSWGuiInventory` | 0x1de8 bytes; loads `inventory`, binds the controls below | high |
| 0x007564e0 | `CSWGuiInventory::vftable` | slots 13 Render, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x006b4c30 | `CSWGuiInventory::OnPanelAdded` | reset viewed character, refresh party buttons, rebuild the list, tutorial 0x14 | high |
| 0x006b4bb0 | `CSWGuiInventory::Render` | rebuild if dirty, refresh stats, colour BTN_USEITEM, draw | high |
| 0x006b3ed0 | `CSWGuiInventory::HandleInputEvent` | events below | high |
| 0x006b4430 | `CSWGuiInventory::OnPanelRemoved` | frees rows, clears the "new" flag of the items seen | high |
| 0x006b4810 | `CSWGuiInventory::RebuildItemList` | builds LB_ITEMS | high |
| 0x006b2c90 | `CSWGuiInventory::PassesFilter` | the six filters | high |
| 0x006b44d0 | `CSWGuiInventory::AddItemRow` | makes or reuses a row and picks its click callback | high |
| 0x006b2a80 | `CSWGuiInventory::CycleFilter` | next filter, relabel title and button | high |
| 0x006b28c0 | `CSWGuiInventory::UpdateStats` | portrait, vitality, defense | med |
| 0x006b2dc0 | `CSWGuiInventory::UpdatePartyButtons` | BTN_CHANGE1/2 portraits and visibility | high |
| 0x006b2ec0 | `CSWGuiInventory::OnChangeCharacter` | BTN_CHANGE1/2 | high |
| 0x006b3d10 | `CSWGuiInventory::OnItemHilighted` | row event 0: description into LB_DESCRIPTION | high |
| 0x006b25e0 | `CSWGuiInventory::OnUseItem` | row event 0x27 for usable items | high |
| 0x006b26e0 / 0x006b2740 | `OnEquippableItemClicked` / `OnUnusableItemClicked` | refusal messages | high |
| 0x006b2800 / 0x006b2860 / 0x006b27a0 | `OnMedpacFullHealth` / `OnSquadMedpacNoInjured` / `OnItemClickedViewOnly` | refusal messages | high |
| 0x006b2fd0 / 0x006b3250 | `OnPreviousCharacter` / `OnNextCharacter` | handlers on two buttons that are never bound to the .gui (see below) | med |

Controls (tags checked against `inventory.gui` and the patch.erf version):

| Tag | Type | Role |
|---|---|---|
| `LB_ITEMS` | list | the items; initial keyboard focus |
| `LB_DESCRIPTION` | list | description of the hilighted item (one wrapped label row) |
| `LBL_INV` | label | title: "Party Inventory - <filter>" (32171, " - ", filter name) |
| `LBL_CREDITS`, `LBL_CREDITS_VALUE` | labels | party credits (`CSWSCreature::GetGold` 0x004edd60 of the leader's server creature) |
| `LBL_PORT`, `LBL_BGPORT`, `LBL_BGSTATS` | labels | portrait of the viewed character (fill texture set every frame) and backgrounds |
| `LBL_VIT`, `LBL_DEF` | labels | vitality "current/max" (shortened when it does not fit) and defense |
| `BTN_USEITEM` | button | 0x27: activates the selected row (use the item) |
| `BTN_QUESTITEMS` | button | 0x29: despite its tag this is the **filter** button: "Show <next filter>" (42359) |
| `BTN_EXIT` | button | 0x28: close the menu |
| `BTN_CHANGE1`, `BTN_CHANGE2` | buttons | switch character (shared scheme) |

The patch.erf `inventory.gui` adds `BTN_CHARLEFT`/`BTN_CHARRIGHT`; this exe never binds them by
tag (the panel constructs two buttons at +0x1a38/+0x1bfc with previous/next handlers but no
`InitControl`), so they never show. Implementers can ignore those two tags. (high)

**Filters** (`CGuiInGame` +0xbc1, 0..5, cycled by event 0x29 and kept between openings; names
from the strref table at 0x00756444) (high):

| # | Name (strref) | An item passes when |
|---|---|---|
| 0 | All Items (41822) | always |
| 1 | New Items (42165) | item flag +0x288 bit7 ("new") |
| 2 | Quest Items (41818) | plot flag (item +0x108) |
| 3 | Equippable Items (41821) | its base item has equipable slots (base item +4 nonzero) |
| 4 | Utility Items (41819) | not plot and no equipable slots |
| 5 | Useable Items (41820) | the viewed creature can use it now (0x00616520) and passes 0x0051b440 |

**Building the list** (`RebuildItemList`): take the viewed creature (leader, or the viewed NPC in
view-only mode); write the credits; then add, in this order, (1) the items equipped in each of the
14 slots (slot bits 1<<0..1<<13), marked equipped, the left-arm, right-arm and belt slots
(0x80, 0x100, 0x400) flagged for the usability test, and (2) every item of the creature's
inventory repository (`CSWSCreature::GetInventory` 0x004ef770). Items with flag +0x288 bit8 set
are skipped (hidden); every item must pass the current filter. Rows are reused between rebuilds
(array at +0x1dc0). The selection is restored to the item just used (id kept at +0x1dd8) or to the
saved scroll/selection (+0x1ddc/+0x1dde); with no items, the description is cleared and the use
button greyed. (high)

**Row click (0x27 on a row or BTN_USEITEM)** — the callback chosen when the row is built:

1. View-only mode: message (strref 49145, empty in this TLK). (high)
2. The creature cannot use the item (0x00616520 fails): "You cannot equip items from the
   INVENTORY screen..." (42485) if it has equipable slots, else "This is not a useable or equipable
   item." (42486). (high)
3. Medical items (base item `itemtype` 45, medpacs) and droid repair kits (26) when the creature
   is at full vitality: "This character does not need to use a medical pack..." (42499). (high)
4. Squad recovery kits (`itemtype` 47) when no party member is injured: (48494). (high)
5. Otherwise `OnUseItem`: in combat, if the player creature already used an item this round
   (creature +0x4e0, +0xac0 == 1, +0xab0) → "can only use one item per round" (42409); else clear
   creature +0x1cc and call the server's use-item entry (0x004efe30, creature, item id), mark the
   list dirty and remember the item for re-selection. The item's effects are the business of
   rules.md / actions.md. (high)

**Hilight** of a row shows the item's description (`CSWSItem::GetDescription` 0x0055f340) in
LB_DESCRIPTION, records whether it is usable (for the button colour), and, if the item is new,
adds its id to the seen list (+0x1dcc), which `OnPanelRemoved` hands to the party table
(0x00556050) to clear the new flags. (high)

No drag and drop: the inventory never uses the manager's dragged-object slot. (med)

#### CSWGuiEquip (equip.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006ba980 | `CSWGuiEquip::CSWGuiEquip` | 0x42bc bytes; loads `equip` | high |
| 0x007569a0 | `CSWGuiEquip::vftable` | 13 Render, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x00756560 | `g_aEquipSlots` | 9 records of 5 dwords: slot mask, tag suffix, empty-slot icon suffix, slot-name strref (human), slot-name strref (droid) | high |
| 0x006bb530 | `CSWGuiEquip::OnPanelAdded` | viewed creature = leader, party buttons, build the hovered slot's list | high |
| 0x006bb510 | `CSWGuiEquip::Render` | `UpdateStats` then draw | high |
| 0x006b9970 | `CSWGuiEquip::UpdateStats` | slot icons, attack/damage/defense/vitality labels, every frame | med |
| 0x006ba3f0 | `CSWGuiEquip::HandleInputEvent` | events below | high |
| 0x006b8e10 | `CSWGuiEquip::OnPanelRemoved` | leaves selection mode, frees rows | high |
| 0x006b9470 | `CSWGuiEquip::OnSlotHilighted` | slot event 0: builds LB_ITEMS for that slot | high |
| 0x006b8eb0 | `CSWGuiEquip::OnSlotClicked` | slot event 0x27: enter selection mode | high |
| 0x006b7680 | `CSWGuiEquip::SetSelectionMode` | shows/hides the slot buttons and the list | high |
| 0x006b7920 | `CSWGuiEquip::OnRowHilighted` | previews the hovered item by equipping it | high |
| 0x006b9160 | `CSWGuiEquip::OnEquip` | BTN_EQUIP and row 0x27: keep the previewed item | high |
| 0x006b7e30 | `CSWGuiEquip::EndSelection` | back to the slot view | high |
| 0x006b5760 | `CSWGuiEquip::EquipItem` | queue equip actions on the server creature | high |
| 0x006b5910 | `CSWGuiEquip::UnequipItem` | queue unequip actions | high |
| 0x006b5890 | `CSWGuiEquip::EquipMatchingItem` | find an inventory item equal to a saved copy and equip it | med |
| 0x006b91c0 | `CSWGuiEquip::GetRow` | row n of LB_ITEMS, created on demand | high |
| 0x006b7590 | `CSWGuiEquip::SetCreature` | viewed creature, empty-slot icons, LBL_PORTRAIT | high |
| 0x006b5b60 | `CSWGuiEquip::UpdatePartyButtons` | BTN_CHANGE1/2, BTN_CHARLEFT/RIGHT | med |
| 0x006ba820 | `CSWGuiEquip::OnChangeCharacter` | BTN_CHANGE1/2 | high |
| 0x006b60f0 / 0x006b6370 | `OnPreviousCharacter` / `OnNextCharacter` | BTN_CHARLEFT / BTN_CHARRIGHT (view-only cycling) | med |

Controls: `BTN_INV_<slot>` and `LBL_INV_<slot>` for the nine slots (`WEAP_L`, `WEAP_R`, `HEAD`,
`ARM_L`, `ARM_R`, `BODY`, `HANDS`, `IMPLANT`, `BELT`), `LB_ITEMS` (candidate items), `LB_DESC`
(item description), `LBL_PORTRAIT`/`LBL_PORT_BORD`, `LBL_VITALITY`, `LBL_DEF`, `LBL_ATKL`/
`LBL_ATKR` (attack bonus per hand), `LBL_TOHITL`/`LBL_TOHITR` (damage per hand), `LBL_ATTACK_INFO`,
`LBL_DEF_INFO`, `LBL_TOHIT`, `LBL_DAMAGE` (captions), `LBL_SLOTNAME` (hovered slot), `LBL_TITLE`,
`LBL_SELECTTITLE`, `LBL_TXTBAR`, `LBL_CANTEQUIP`, `BTN_EQUIP`, `BTN_BACK`, `BTN_CHANGE1`/`2`,
`BTN_CHARLEFT`/`RIGHT` (patch.erf version only; the code binds them). (high)

The slot table, in slot-button order (tag suffix, slot mask, empty icon, human / droid name):

| Tag | Mask | Empty icon | Human | Droid |
|---|---|---|---|---|
| `INV_WEAP_L` | 0x20 | `iweap_l` / `idweap_l` | Left Weapon (31378) | same |
| `INV_WEAP_R` | 0x10 | `iweap_r` | Right Weapon (31379) | same |
| `INV_HEAD` | 0x01 | `ihead` | Head (31375) | Sensor (41810) |
| `INV_ARM_L` | 0x80 | `iforearm_l` | Left Arm (31376) | Special Weapon (41814) |
| `INV_ARM_R` | 0x100 | `iforearm_r` | Right Arm (31377) | Special Weapon (41814) |
| `INV_BODY` | 0x02 | `iarmor` | Body (31380) | Plating (41813) |
| `INV_HANDS` | 0x08 | `ihands` | Hands (31383) | Utility (41811) |
| `INV_IMPLANT` | 0x200 | `iimplant` | Implant (31388) | Utility (41811) |
| `INV_BELT` | 0x400 | `ibelt` | Belt (31382) | Shield (41812) |

Empty-slot icons are `i` + suffix, or `id` + suffix for droids (both exist in
`swpc_tex_gui.erf`); a filled slot shows the item's icon. (high for the table, med for the
`i`/`id` rule, which is inferred from the textures and `0x006b5600`)

**Slot view.** Hovering a slot button (event 0) builds LB_ITEMS for that slot so the player sees
what could go there before clicking. The list is: row 0 "None" (unequip), row 1 the equipped item
(if any), then every inventory item whose base item's equipable slots include the slot mask and
whose `droidorhuman` column (base item +0xb4) fits the creature (0 anyone; 1 only when the
creature's race is 6; 2 only when it is 5). Each candidate is tested with the server's
can-equip check (0x0051aa60); a failure marks the row state 2 (cannot equip). With the "Hide
Unequippable" option (client options +0x14 bit0) failing items are left out. For the weapon
slots, an item whose wield type (base item +8) does not pair with the weapon in the other hand
(both must be 2 or both 4) gets state 3. (high for the order and the tests, med for the meaning
of the states)

**Selection mode.** Clicking a slot (0x27):
- body armour while in combat (creature +0x4e0 == 1 and +0xac0 == 1): "You cannot equip or unequip
  armor during combat!" (1506);
- left weapon slot while the right hand holds a two-handed weapon (base item +0x1b == 4):
  strref 42344;
- no candidates: "You have no items that can be equipped in this slot." (42345);
- otherwise hide the slot buttons and stat labels, show LB_ITEMS with keyboard focus, select the
  equipped row, title "Select Item to Equip" (38154), BTN_BACK reads "Cancel" (1581; "Close" 1582
  outside), tutorial 0x0b. (high)

While in selection mode, **hovering a row really equips that item** (`OnRowHilighted`): the first
time, the originally equipped item's id and a copy are saved (+0x42ac/+0x42b0; for a two-handed
right weapon also the left weapon, +0x42b4/+0x42b8, which is unequipped); then the hovered item is
equipped (`EquipItem`) or the slot emptied (`UnequipItem`) with GUI sounds 0xb / 0xa, so the stat
labels update live. `OnEquip` (BTN_EQUIP or clicking the row) keeps the result and leaves the
mode. Cancel (0x28/0x2e/0xdf in the mode) re-equips the saved originals and leaves the mode;
outside the mode those keys close the menu. (high)

`EquipItem` checks the base item fits the slot, clears the creature's action queue
(`CSWSObject::ClearAllActions`) and combat state when asked, calls
`CSWSCreature::AddEquipItemActions`, and, if the creature is in combat with a target
(creature +0x9c8 → +0x9cc), re-queues `CSWSCreature::AddAttackActions` on it. `UnequipItem` does
the same with `CSWSCreature::AddUnequipActions`. Equip rules and the action itself:
party-items-saves.md and actions.md. (high)

**Stats** (`UpdateStats`, every frame): attack bonus and damage per hand from the creature stats
(0x005a9e10 attack modifier, 0x005a7770 / 0x005a7b60 damage), defense (0x004ed1d0), vitality
"current/max"; a hand's labels go blank (colour 0x007a23b4) when the hand is empty; when the
right hand holds a two-handed weapon (base item +0x1b == 4) or one of wield type 3, the left
weapon slot shows the same icon. The slot icons are refreshed here too, so equipping elsewhere
shows at once. The formulas are combat.md's. (med)

#### CSWGuiCharacter (character.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006b0e40 | `CSWGuiCharacter::CSWGuiCharacter` | 0x59f8 bytes; loads `character`, a 3D scene (`gui3D_room`, camera hook `camerahook`), creates the script-select panel | high |
| 0x00756100 | `CSWGuiCharacter::vftable` | 13 Render, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved 0x006ae980 | high |
| 0x006b2250 | `CSWGuiCharacter::HandleInputEvent` | events below | high |
| 0x006b2220 | `CSWGuiCharacter::OnPanelAdded` | reset view, `UpdateStats`, refresh party | high |
| 0x006b0b90 | `CSWGuiCharacter::Render` | `UpdateStats` then draw | high |
| 0x006afda0 | `CSWGuiCharacter::UpdateStats` | all labels, effect icons, alignment, 3D model | med |
| 0x006aee30 | `CSWGuiCharacter::UpdatePartyButtons` | BTN_CHANGE1/2 portraits | med |
| 0x006af350 | `CSWGuiCharacter::OnChangeCharacter` | BTN_CHANGE1/2 | med |
| 0x006af450 / 0x006af6d0 | `OnPreviousCharacter` / `OnNextCharacter` | BTN_CHARLEFT / BTN_CHARRIGHT | med |
| 0x006aed90 / 0x006aede0 | `RotateModelLeft` / `RotateModelRight` | turn the 3D model by -10 / +10 degrees | high |
| 0x006aed20 | `CSWGuiCharacter::SetModelRotation` | events 0x3b / 0x3c | low |
| 0x006b0bb0 | `CSWGuiCharacter::StartLevelUp` | opens the level-up panel (ctor 0x006e8ef0) | med |
| 0x006b0cb0 | `CSWGuiCharacter::AutoLevelUp` | confirmation text with custom tokens, then automatic level-up | low |

Controls: `LBL_NAME`, `LBL_CLASS`, `LBL_CLASS1`/`2` and `LBL_LEVEL`/`1`/`2` (up to two classes),
`LBL_VITALITY`(`_STAT`), `LBL_FORCE`(`_STAT`), `LBL_DEFENSE`(`_STAT`), the six attributes
(`LBL_STR`/`LBL_STRENGTH`/`LBL_STR_MOD` ... `CHA`), saves `LBL_FORTITUDE`/`REFLEX`/`WILL`(`_STAT`),
`LBL_EXPERIENCE`(`_STAT`), `LBL_NEXT_LEVEL`, `LBL_NEEDED_XP`, `LBL_3DCHAR` / `BTN_3DCHAR` (the
model view), `SLD_ALIGN` (alignment slider), `LBL_LIGHT`/`LBL_DARK` (its end labels),
`LBL_GOOD1`..`10` (ten icon buttons along the slider), `LBL_MORE`, `LBL_ADORN`, `LBL_BEVEL`/`2`,
`BTN_LEVELUP`, `BTN_AUTO`, `BTN_SCRIPTS`, `BTN_EXIT`, `BTN_CHANGE1`/`2`, `BTN_CHARLEFT`/`RIGHT`.
(high, tags checked)

Events: 0x27 (BTN_LEVELUP) starts level-up when one is pending (`CGuiInGame` +0x10c) and not
blocked (0x005ee190); 0x2a (BTN_AUTO) the automatic level-up under the same test; 0x29
(BTN_SCRIPTS) opens script select for the leader (modal, flags 3); 0x3b/0x3c rotate the model;
0xce and 0x28/0x2d/0x2e/0xdf as in the conventions. The level-up and auto buttons are visible only
when the viewed character can level (stats 0x005a6810) and not in view-only mode. (high)

Stats come from `CSWSCreatureStats` (`GetSTRStat` 0x005a6190 ... `GetDEXStat` 0x005a6550, level
0x005a5fd0, saves 0x005ab810/0x005ab880/0x005ab8f0) and the client creature's vitality/force
accessors. The ten `LBL_GOOD%d` buttons show up to ten icons from a list on the client creature
(+0x8f4 array, +0x8f8 count; each entry's resref at +2), `LBL_MORE` shows when there are more
than ten; what the list holds is not established (likely active effects). The alignment slider
is set to 100 - good/evil (stats +0x80) so light is at the top; the 3D model (a client creature
copy, scene object at +0x59e4) is rebuilt only when the viewed creature or its alignment changes,
because the dark-side look depends on it. (med)

#### CSWGuiAbilities (abilities.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006adda0 | `CSWGuiAbilities::CSWGuiAbilities` | 0x3f98 bytes; loads `abilities`, ten prebuilt row controls (+0x70, stride 0x310) | high |
| 0x00755e50 | `CSWGuiAbilities::vftable` | 15 HandleInputEvent 0x006ae5f0, 18 OnPanelAdded, 19 OnPanelRemoved 0x006ab8b0 | high |
| 0x006adc20 | `CSWGuiAbilities::OnPanelAdded` | viewed creature = leader | high |
| 0x006adb00 | `CSWGuiAbilities::SetCreature` | portrait, feat/power trees, hide Powers for non-Force classes, rebuild | med |
| 0x006adad0 / 0x006adaa0 / 0x006ada70 | `OnSkillsTab` / `OnPowersTab` / `OnFeatsTab` | set tab 0/1/2 (`CGuiInGame` +0xbc0) and rebuild | high |
| 0x006ac8d0 | `CSWGuiAbilities::KeepTabHilighted` | tab button event 1: keep the current tab's text yellow | high |
| 0x006ad560 | `CSWGuiAbilities::RebuildList` | fills `LB_ABILITY` for the tab | med |
| 0x006ad180 | `CSWGuiAbilities::OnRowHilighted` | name, description, rank / bonus / total | med |
| 0x006ad4b0 | `CSWGuiAbilities::OnSelectionChanged` | list event 0x1f8: for powers/feats, show the chosen entry | med |
| 0x006adc80 | `CSWGuiAbilities::OnChangeCharacter` | BTN_CHANGE1/2 | med |
| 0x006abec0 | `CSWGuiAbilities::UpdatePartyButtons` | | med |

Controls: `LB_ABILITY` (the skill / power / feat list; in both versions of the .gui), `LB_DESC`,
`LBL_PORTRAIT`, `LBL_NAME`, `LBL_SKILLRANK`/`LBL_RANKVAL`, `LBL_BONUS`/`LBL_BONUSVAL`,
`LBL_TOTAL`/`LBL_TOTALVAL` (skills: rank, attribute bonus, total), `LBL_INFOBG`, `BTN_SKILLS`,
`BTN_POWERS`, `BTN_FEATS`, `BTN_EXIT`, `BTN_CHANGE1`/`2`, `BTN_CHARLEFT`/`RIGHT`. The tab is kept
in `CGuiInGame` +0xbc0 between openings; Powers is hidden and the tab reset to Skills when the
character's class is not a Force user (0x005be4a0). Feats and powers are read through a tree
helper shared with the level-up screens (objects at +0x3f78/+0x3f88, functions 0x006cd1c0,
0x006cdc00, 0x006ce370), described with the level-up panels. Skimmed. (med)

#### CSWGuiJournal (journal.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00644a40 | `CSWGuiJournal::CSWGuiJournal` | 0xfc8 bytes; loads `journal`, owns the quest-items panel (+0xfb4) | high |
| 0x00751960 | `CSWGuiJournal::vftable` | 13 Render 0x00645670, 15 HandleInputEvent, 18 OnPanelAdded 0x00645e00, 19 OnPanelRemoved 0x00646070 (a thunk to `ClearQuestRows`) | high |
| 0x006456e0 | `CSWGuiJournal::HandleInputEvent` | events below | high |
| 0x00645330 | `CSWGuiJournal::RebuildQuestList` | one button row per quest, from the client journal (0x005ed320) | med |
| 0x00645610 | `CSWGuiJournal::ClearQuestRows` | | med |

Controls: `LB_ITEMS` (quests), `LBL_ITEM_DESCRIPTION` (a list box despite the prefix: the quest
text), `LBL_TITLE`, `BTN_QUESTITEMS`, `BTN_SWAPTEXT`, `BTN_SORT`, `BTN_EXIT`. (high)

State in `CGuiInGame`: +0xbc4 bit0 = showing completed quests; a sort mode 0..3 per list (active
and completed each keep their own; read and written through four small accessors 0x00712fc0 /
`CRes::GetSize`-folded getter and 0x00676bc0 / 0x00676bf0). Sort names (table 0x007a2474): by
Order Received (32173), by Name (32174), by Priority (32175), by Planet (32176). (high)

Events: 0x29 (BTN_QUESTITEMS) opens the quest-items panel (flags 3); 0x2a (BTN_SWAPTEXT) toggles
active/completed, rebuilds, sets the button text to the other list's name ("Completed Quests"
32177 / "Active Quests" 32178) and the title to "<list> - <sort>"; 0x2b (BTN_SORT) advances the
sort mode (wrapping 3 → 0), re-sorts, sets BTN_SORT to "Sort <next mode>" (42566) and the title;
0x39/0x3a scroll the text; close keys as usual. The quest data model (JRL, states, priorities)
is not in this document's scope; nothing else here reads it. (high for the panel, med for list
contents)

#### CSWGuiQuestItems (questitem.gui) — skimmed

Ctor 0x006d26c0 (vtable 0x00757c20), owned by the journal. Controls `LB_ITEMS`,
`LB_ITEM_DESCRIPTION`, `LBL_TITLE`, `BTN_BACK`. On open (0x006d2c20 → 0x006d29f0) it lists every
plot item (item +0x108) in the leader's inventory as `CSWGuiItemEntry` rows (no equipped/new
marks) and selects the first; hilighting a row (0x006d2580) shows its description. Back/0x28/0x2e
pop it; 0x39/0x3a scroll the description. (med)

#### CSWGuiMap (map.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00694d50 | `CSWGuiMap::CSWGuiMap` | 0x10dc bytes; loads `map` | high |
| 0x00754830 | `CSWGuiMap::vftable` | 13 Render, 15 HandleInputEvent, 16 HitTest, 18 OnPanelAdded, 19 OnPanelRemoved 0x00693ba0 | high |
| 0x00693650 | `CSWGuiMap::OnPanelAdded` | area name, map texture, map notes, enables Party Select / Return, tutorial 0x0d | high |
| 0x00693bc0 | `CSWGuiMap::HandleInputEvent` | events below | high |
| 0x00692810 | `CSWGuiMap::Render` | dims disabled buttons, draws the panel, then the map in LBL_Map's rectangle | high |
| 0x00692930 | `CSWGuiMap::HitTest` | a click outside any control goes to the map view (map-local coordinates) | high |
| 0x006927b0 / 0x006927c0 | `CSWGuiMap::OnNoteUp` / `OnNoteDown` | BTN_UP / BTN_DOWN send 0x31 / 0x32 to itself | high |
| 0x006929b0 | `CSWGuiMap::ShowMapNote` | puts the selected note's text in LBL_MapNote | med |
| 0x00692bc0 | `CSWGuiMap::OnReturnToBase` | the Return button's action | low |

Controls: `LBL_Map` (the map's rectangle; the texture is drawn by a map-view object at +0xe38 and
an image at +0x1080 inside a viewport pushed at LBL_Map's extent), `LBL_MapNote`, `LBL_Area` (area
name, area +0x17c), `LBL_COMPASS`, `BTN_UP`/`BTN_DOWN` (previous/next map note), `BTN_PRTYSLCT`,
`BTN_RETURN`, `BTN_EXIT`. (high)

Map texture: `lbl_map` + the module resref (format `lbl_map%s`), or `lbl_mapm28aa` when the module
has no map flag (module +0x218 → +4 is zero). The world-to-map transform and the drawing of party
arrows and notes live in the map-view object, shared with the HUD minimap (see the HUD section and
movement.md). (med)

**Party Select** (0x27) is enabled only when (1) the area allows it (area +0x2ac == 0; else
"That function is unavailable at this time." 38451), (2) the party is together (0x00635350; else
"You must rejoin your party first." 38452) and (3) no creature in the area that the party
perceives is hostile (reputation below 11 via 0x0057cb80 and seen via 0x00517a20; else "That
cannot be done while there are enemies nearby." 38462). When disabled, clicking shows the stored
message; when enabled it opens party selection with no exit script
(`CGuiInGame::ShowPartySelection` 0x0062dd20, from-script 0). (high)

**Return** (0x29) is enabled when the party table's return flag (+0x100) is set; its label is the
strref stored with it (+0x104), both set by script (`SetReturnStrref`-style routines; not traced
here). Pressing it first offers tutorial 0x27 and otherwise runs the return action
(0x00692bc0). (med)

Disabled buttons are drawn with text colour 0x007a2408 and hilight 0x007a2384 (greys). (high)

#### CSWGuiGalaxyMap (galaxymap.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00695180 | `CSWGuiGalaxyMap::CSWGuiGalaxyMap` | 0x2550 bytes; loads `galaxymap`, a 3D scene `galaxy` (`gui3D_room`, `camerahook`) and up to 16 planet buttons | high |
| 0x00754910 | `CSWGuiGalaxyMap::vftable` | 13 Render 0x00693610, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved 0x006927d0 | high |
| 0x0062d040 | `CGuiInGame::ShowGalaxyMap` | from NWScript `ShowGalaxyMap(nPlanet)` (routine 739); selects the planet, opens the panel | high |
| 0x0062d1d0 | `CGuiInGame::CloseGalaxyMap` | | med |
| 0x00694b40 | `CSWGuiGalaxyMap::OnPanelAdded` | validates the selected planet, shows it | med |
| 0x00695980 | `CSWGuiGalaxyMap::HandleInputEvent` | events below | high |
| 0x006935a0 | `CSWGuiGalaxyMap::OnPlanetClicked` | planet button 0x27: select it | high |
| 0x006933a0 | `CSWGuiGalaxyMap::ShowPlanet` | name, description, planet model with animations `rotate` / `zoomin` | med |
| 0x00694ca0 / 0x00694bf0 | `SelectPreviousPlanet` / `SelectNextPlanet` | | med |

Planet buttons come from `planetary.2da` (rules 2DA cache +0x104): for each row the button tag is
the `guitag` column (`LBL_Planet_Taris` ... `LBL_Live01`..`05`), the name/description strrefs and
`icon`, `model` columns feed `LBL_PLANETNAME`, `LBL_DESC` and `3D_PlanetModel`; `3D_PlanetDisplay`
is the galaxy view. Rows without a guitag (Ebon Hawk) have no button. Availability and
selectability per planet are party-table state set by `SetPlanetAvailable`/`SetPlanetSelectable`
(routines 742/740); the selected planet is the party table's +0xe0 (`CSWPartyTable::SetSelectedPlanet`
0x00563b60). (high for the 2DA use, med for the availability display)

Events: 0x27/0x2d (BTN_ACCEPT) set `CGuiInGame` +0xc04 = 1, run the script `k_sup_galaxymap`
(owner `OBJECT_INVALID`), clear the flag and close; 0x28/0x2e/0xdf (BTN_BACK) close; 0x2f, 0x31,
0x3d, 0x3f select the previous planet and 0x30, 0x32, 0x3e, 0x40 the next (GUI sound 1). The
script reads the selected planet and does the travel. (high)

#### CSWGuiContainer (container.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006b6dc0 | `CSWGuiContainer::CSWGuiContainer` | 0x101c bytes; loads `container` (a 305x327 box, centred) | high |
| 0x007567e0 | `CSWGuiContainer::vftable` | 14 Update, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x0062d4b0 | `CGuiInGame::OpenContainer` | called when the server opens a container for the player (via 0x00651810); fills and adds the panel | med |
| 0x0062d510 | `CGuiInGame::CloseContainer` | removes the panel, pops modal, back to game input | med |
| 0x006b51d0 | `CSWGuiContainer::OnPanelAdded` | saves the cursor and warps it to the centre of BTN_OK | high |
| 0x006b5250 | `CSWGuiContainer::OnPanelRemoved` | restores the cursor position | high |
| 0x006b8770 | `CSWGuiContainer::Update` | rebuilds the give-items list when flagged | med |
| 0x006b92f0 | `CSWGuiContainer::HandleInputEvent` | events below | high |
| 0x006b8130 | `CSWGuiContainer::ShowContainerItems` | lists the placeable's items | med |
| 0x006b8410 | `CSWGuiContainer::ShowGiveItems` | lists the party's items to put into the container | med |
| 0x00677630 | `SendContainerClose` | client-to-server message (type 0x19, subtype 2) with the container id and a take-all flag | med |

Controls: `LBL_MESSAGE` (title), `LB_ITEMS`, `BTN_OK` (take all), `BTN_GIVEITEMS`, `BTN_CANCEL`;
the code also binds `LBL_BUTTON`, `LBL_OK`, `LBL_B`, `LBL_X`, `LBL_CANCEL` (gamepad hint labels)
which this .gui does not have, so they stay empty. (high)

Panel flags at +0x6c: bit0 = the container's own items are showing (set by `ShowContainerItems`,
cleared by `ShowGiveItems`), bit1 = give list needs a rebuild (handled in `Update`), bit2 = skip
one update. Events: 0x27 (BTN_OK) and 0x2d act only while the container's items are showing: they
send the close message with take-all = (mode byte +0x68 == 1) and close; 0x28/0x2e (BTN_CANCEL)
send it with take-all 0 and close; 0x29 (BTN_GIVEITEMS) switches between the container list and
the give-items list. The container id is at +0x64. The actual item transfer happens on the server
when it receives the message (party-items-saves.md). (med)

#### CSWGuiStore (store.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006c1c00 | `CSWGuiStore::CSWGuiStore` | 0x2280 bytes; loads `store` | high |
| 0x00756e38 | `CSWGuiStore::vftable` | 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x0062e310 | `CGuiInGame::OpenStore` | from NWScript `OpenStore` (0x00540300): needs no other menu up; GUI input, sound mode 4, store id +0x2278, customer +0x227c, `AddPanel(3)`, GUI sound 4 | high |
| 0x0062e4a0 | `CGuiInGame::CloseStore` | | med |
| 0x006c2170 | `CSWGuiStore::OnPanelAdded` | mode set-up, credits, buy list | high |
| 0x006c2190 | `CSWGuiStore::HandleInputEvent` | 0x28/0x2e close; 0x29 = Examine; 0x39/0x3a scroll | high |
| 0x006c1b50 | `CSWGuiStore::SetupForStoreMode` | store mode byte (store +0x256): 1 buy only, 2 sell only, 3 both | high |
| 0x006c1b00 | `CSWGuiStore::OnToggleList` | BTN_Examine: in mode 3 switch between buy and sell lists | high |
| 0x006c1a50 | `CSWGuiStore::ShowBuyList` | LB_SHOPITEMS, labels "Buy", BTN_Accept → `OnBuy` | high |
| 0x006c13c0 | `CSWGuiStore::ShowSellList` | LB_INVITEMS, BTN_Accept → `OnSell` | med |
| 0x006c1840 / 0x006c0850 | `FillStoreItems` / `FillPlayerItems` | | med |
| 0x006c1660 | `CSWGuiStore::AddItemRow` | | med |
| 0x006c0aa0 | `CSWGuiStore::OnItemHilighted` | description, cost, stock | med |
| 0x006c1130 / 0x006c0f40 | `OnBuy` / `OnSell` | checks and confirmation | med |
| 0x006c0be0 / 0x006c0d80 | `DoBuy` / `DoSell` | the transaction (server store calls 0x005c6f70 / 0x005c7610) | med |
| 0x006c0790 / 0x006c07f0 | `GetBuyPrice` / `GetSellPrice` | below | high |
| 0x006c0610 | `CSWGuiStore::UpdateCredits` | | high |

Controls: `LB_SHOPITEMS` and `LB_INVITEMS` (same rectangle; one is shown), `LB_DESCRIPTION`,
`LBL_BUYSELL`, `LBL_CREDITS`/`_VALUE`, `LBL_COST`/`_VALUE`, `LBL_STOCK`/`_VALUE`, `BTN_Accept`,
`BTN_Examine` (in a buy-and-sell store: "Show Sell List" 41938 / back), `BTN_Cancel`. (high)

Prices, with `cost` = the item's value (0x00554000) and the store's percentages: **buy price**
(player pays) = cost × (store +0x248 + store +0x250) / 100, **sell price** (player receives) =
cost × (store +0x244 + store +0x24c) / 100, integer division. +0x248/+0x244 are the store's own
mark-up / mark-down and +0x250/+0x24c the bonus mark-up / mark-down passed to `OpenStore`
(written by 0x00540300). Rules for stock and infinite items: party-items-saves.md. (high)

#### Upgrade bench: CSWGuiUpgradeSelect, CSWGuiUpgradeItems, CSWGuiUpgrade — skimmed

Opened by NWScript `ShowUpgradeScreen(oItem)` (routine 354, 0x00543990 →
`CGuiInGame::ShowUpgradeScreen` 0x0062e760), which creates the category panel and (when an item
is given) goes straight to it. Three panels:

| Address | Name | .gui | What | Conf. |
|---|---|---|---|---|
| 0x006c78d0 / 0x007571b0 | `CSWGuiUpgradeSelect` | upgradesel | four category buttons `BTN_LIGHTSABER`, `BTN_RANGED`, `BTN_MELEE`, `BTN_ARMOR` (with `LBL_*` pictures), `BTN_UPGRADEITEMS`, `BTN_BACK` | high |
| 0x006c2b60 | `CSWGuiUpgradeSelect::OnCategory` | | category button 0x27/0x2d (or BTN_UPGRADEITEMS on the hilighted one): if that category has items, set the item panel's category (+0xc2c = index + 1) and open it (flags 3) | high |
| 0x006c2b10 | `CSWGuiUpgradeSelect::HandleInputEvent` | | 0x28/0x2e close the bench (`CGuiInGame::CloseUpgradeScreen` 0x0062e870) | high |
| 0x006c7630 / 0x00757228 | `CSWGuiUpgradeItems` | upgradeitems | `LB_ITEMS` (items of the category, `CSWGuiItemEntry` rows), `LB_DESCRIPTION`, `BTN_UPGRADEITEM`, `BTN_BACK`, `LBL_TITLE` | high |
| 0x006c2df0 | `CSWGuiUpgradeItems::OnUpgradeItem` | | takes the chosen item: an equipped one is unequipped from its wearer (0x004faa70; for weapons both hands are handled and remembered), a stacked one is split off one unit (0x0055f280), a loose one is removed from the party inventory (0x00555fd0); then opens the upgrade panel with the item (+0x2f54) and kind (+0x2f4c, 1 = lightsaber) | med |
| 0x006c6b60 / 0x00757298 | `CSWGuiUpgrade` | upgrade | `LB_ITEMS`, `LB_DESC`/`LB_DESC_LS`, `LBL_DESCBG`(`_LS`), `3D_MODEL`(`_LS`), `LBL_SLOTNAME`, `LBL_LSSLOTNAME`, `LBL_UPGRADES`, `LBL_UPGRADE_COUNT`, `LBL_PROPERTY`, `LBL_UPGRADE31..33` + `BTN_UPGRADE31..33` (three slots, other items), `LBL_UPGRADE41..44` + `BTN_UPGRADE41..44` (four slots, lightsabers), `BTN_ASSEMBLE`, `BTN_BACK` | high |
| 0x006c6500 | `CSWGuiUpgrade::OnSlotClicked` | | empty slot: list the matching upgrade items found in the party inventory (`upgrade.2da` `UpgradeType`/`Template`, crystals from `upcrystals.2da` `Template`) and enter selection; filled slot: remove the upgrade (clear the item's upgrade bit, item +0x294) and return it to the inventory (0x0055d330). Adding an upgrade that would stop the wearer re-equipping the item asks first (42489) | med |
| 0x006c6190 | `CSWGuiUpgrade::OnAssemble` | | finishes (0x006c5e90 on the item panel), closes | med |
| 0x006c6a80 | `CSWGuiUpgrade::HandleInputEvent` | | 0x28/0x2e: leave selection (0x006c4d30) or close and give the item back (0x006c61f0); 0x39/0x3a scroll the description | med |

The upgrade rules (which property each upgrade adds) belong to rules.md /
party-items-saves.md. (med)

#### CSWGuiPartySelection (partyselection.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006bfa40 | `CSWGuiPartySelection::CSWGuiPartySelection` | 0x3a80 bytes; nine NPC records of 0x454 bytes from +0x7c | high |
| 0x00756d28 | `CSWGuiPartySelection::vftable` | 15 HandleInputEvent 0x006bede0, 18 OnPanelAdded 0x006beeb0, 19 OnPanelRemoved 0x006be490 | high |
| 0x0062dd20 | `CGuiInGame::ShowPartySelection(exitScript, bFromScript, forceNPC1, forceNPC2)` | from NWScript `ShowPartySelectionGUI` (routine 712) and the map's Party Select | high |
| 0x006beeb0 | `CSWGuiPartySelection::OnPanelAdded` | per slot: portrait, available / selected / forced state from the party table | med |
| 0x006bf2a0 | `CSWGuiPartySelection::OnToggleNPC` | BTN_NPCn 0x27/0x2d and BTN_ACCEPT (acts on the hilighted slot) | high |
| 0x006bf5b0 | `CSWGuiPartySelection::OnNPCHilighted` | name, level, 3D model of the hilighted NPC | med |
| 0x006bf3b0 | `CSWGuiPartySelection::OnDone` | BTN_DONE: confirm and apply | high |
| 0x006bec90 | `CSWGuiPartySelection::OnConfirmed` | message-box callback → apply | high |
| 0x006be560 | `CSWGuiPartySelection::ApplyAndClose` | rebuilds the party (adds/removes NPCs via the party table, places them by the leader), runs the exit script, closes | med |

Controls: per slot n = 0..8 `BTN_NPCn` (check box), `LBL_CHARn` (portrait), `LBL_NAn` ("not
available" overlay); `LBL_3D` (model), `LBL_NPC_NAME`, `LBL_NPC_LEVEL`, `LBL_COUNT` +
`LBL_AVAILABLE` (members left to pick), `LBL_TITLE`, `LBL_BEVEL_L`/`R`/`M`, `BTN_ACCEPT`,
`BTN_DONE`, `BTN_BACK`. Slot n is NPC n of the party table (the nine `npc.2da`-style NPC indices).
(high)

Toggling a slot that is not available shows "The party member you have selected is currently
unable to join the party." (42376) or, for a forced member, "This character must be a member of
your party at this time." (42406). Done counts the selected and forced slots: with nothing
selected, or both forced members chosen, it applies at once; otherwise it asks "Are you sure this
is the party configuration you want?" (38328), or "You have less than 3 characters in your
party..." (38329) when only one companion is picked, and applies on Yes. The party size limit
(two companions) and the party table belong to party-items-saves.md. (med for the counting
details)

#### CSWGuiScriptSelect (scriptselect.gui)

The party AI style panel: the character sheet's Scripts button (BTN_SCRIPTS, event 0x29) opens it
as a modal (flags 3) for the character the sheet shows. Ctor 0x006ea000 (vtable 0x007590a8, 0xc40
bytes), owned by the character sheet (+0x59f4). Ghidra cuts the ctor at 0x006ea0fd (an exception
frame); the rest, to the `ret` at 0x006ea46a, was read from the bytes. (high)

Controls (file `scriptselect.gui`, 640x480): `LST_AIState` (+0x70, the rows), `LB_DESC` (+0x350, the
description), `LBL_TITLE` (+0x770, "Script Selection", strref 42293), `BTN_Back` (+0x8b0, "Cancel",
1581), `BTN_Accept` (+0xa74, "Select", 236). The label at +0x630 is the description list's
prototype item. The ctor reads `aiscripts.2da` (label, `name_strref`, `description_strref`,
`aistate`; shipped rows DEFAULT 1116/1109/0 "Default attack", GRENADE 1120/1112/4 "Grenadier",
JEDI 1121/1114/5 "Jedi/Droid support", the values of NPC_AISTYLE_*) and, for each row, builds a
list item (0x006e9f10: a 0x2b4-byte check-box control with the name as its text) and keeps
`{description strref, aistate}` in an 8-byte-per-row table at +0x64 (count +0x68). Each item has
two handlers: event 0 (hilight, from the pointer or the up/down keys) 0x006e9fe0 -> 0x006e9d50,
which clears `LB_DESC` and puts the row's description in it; event 0x27 0x006e9e70, which is
Accept. (high)

`CSWGuiScriptSelect::SetCreature` (0x006e9ca0) stores the creature id (+0xc3c) and walks the rows:
the one whose `aistate` equals the creature's AI state (creature stats +0x13a, a short) gets its
check box state (+0x1c8 bit 0) set and `SetSelectedIndex` (so event 0 shows its description), the
others are cleared. No match: nothing is selected and the description stays empty. Accept
(`HandleInputEvent` 0x006e9bc0: 0x27/0x2d, and the item handler 0x006e9e70) writes the selected row's
`aistate` into stats +0x13a, plays GUI sound 0, pops the modal and marks the panel for removal;
0x28/0x2e (BTN_Back through `OnButtonCancel`, Escape) do the last three only. BTN_Accept is the
`OnButtonAccept` thunk, i.e. the same 0x27 sent to the panel. `OnPanelAdded` 0x006e9b90 asks for
tutorial popup 10 (`ShowTutorialPopup`; ours has no tutorial popups). (high)

So the list is a set of one-click buttons: a click on a row (or Enter on the selected one) chooses
it and closes the panel; Select takes the selected row, which opens as the creature's own. The
description follows the hilighted row.

**Is it saved?** Yes. `CSWSCreatureStats::ReadStatsFromGff` (it runs on well past the 431 bytes
Ghidra gives it, which is why the string had no cross reference) reads the INT `AIState` at
0x005b067a with the stats value as its default, and the stats writer writes it back at 0x005b22a5,
both next to `ChallengeRating`. Found by scanning the unpacked image for the immediate 0x0074ae30.
A UTC may carry it too. Ours: `lib/save/objects.ctx` `write_creature` and `lib/engine/templates.ctx`
`read_creature` (INT `AIState` <-> `obj::Creature.ai_style`). (high)

What the style does: `k_inc_generic`'s `GN_DetermineCombatRound` reads `GetNPCAIStyle(OBJECT_SELF)`
(stats +0x13a) for a party member who does not lead (`GetPartyMemberByIndex(0)`) outside restrict
mode: 4 runs `GN_RunGrenadeAIRoutine` (`GN_FindGrenadeTarget`: a seen creature with at least two
enemies and no friend within 4 m, then `GN_GetGrenadeTalent`, talents 87..95, used through
`ActionUseTalentOnObject`), 5 `GN_RunJediSupportAIRoutine`, 0 the default attack.

Ours: `lib/ingame/scriptselect_panel.ctx`, opened by the sheet (`character_panel`) as a modal
over it, with the rows as click rows (`gui::set_click_rows`: press selects and shows the
description, release activates); the check box state is the row's `checked`. `--log combat`
prints `ai style: NAME old -> new` when a row is chosen. Checked headless on the Upper City
checkpoint: the panel with the description of the selected row, the description following the
pointer and the down key, a click, Enter and Select choosing, Cancel and Escape leaving the style,
`GetNPCAIStyle` answering 4 in Carth's combat rounds (`--log routines`), and the style surviving a
save and load.

Found while testing a Grenadier with two Sith troopers close together (open, for the combat
owner): the grenade is not thrown because of the shape iteration. The original keeps the cursor
of `GetFirstObjectInShape`/`GetNextObjectInShape` in the area (`ExecuteCommandGetFirstObjectInShape`
0x0054a260: index in +0x19c) and walks the area's array of creatures (+0x190, count +0x194),
which is kept sorted by position X (the first call binary-searches it, 0x00506f20, for the shape's
lowest X, and the walk stops at its highest X). `GN_FindGrenadeTarget` runs two more shape loops
inside its own, so in the original too its outer loop ends after the first seen creature in
ascending-X order; ours walks `objects.all` in creation order (`routines/objects.ctx`
`get_in_shape`), so the first seen creature is the oldest bystander (the Upper City's id 481), a
friend (Carth) stands within 4 m of it, and the routine falls through to the default attack. The
ordering of the shape iteration is the thing to match.

### 10.5 Conversation and pazaak panels

#### Conversation panels (`CSWGuiDialog` and subclasses)

Base constructor 0x006a85b0 (vtable 0x007559e0); flow and cameras: dialogue.md. The panel side
(high unless noted):

| Panel | Ctor / vtable / size | `.gui` | Held at |
|---|---|---|---|
| Conversation (letterbox) | 0x006a8b40 / 0x00755800 / 0x1e00 | `dialog` (`LBL_MESSAGE`, `LB_REPLIES`) | `CGuiInGame` +0x40 (and +0x3c) |
| Computer | 0x006a8eb0 / 0x00755888 / 0x3620 | `computer` (`LB_MESSAGE`, `LB_REPLIES`, `LBL_OBSCURE`, skill/spike/repair labels `LBL_COMP_SKILL*`, `LBL_REP_SKILL*`, `LBL_COMP_SPIKES*`, `LBL_REP_UNITS*`) | +0x44 |
| Computer camera | 0x006a95f0 / 0x00755958 | `computercamera` (`LBL_RETURN`) | +0x48 |

- **Replies**: `LB_REPLIES` rows hilight yellow on hover (0x006a6fc0) and return to the panel's
  stored reply colour (+0x1de4) when left (0x006a6fe0).
- **Input** (`HandleInputEvent` 0x006a7230, shared): the dialogue number-key actions
  (0xfe..0x106, `Dialog1..9`) pick reply *n*-1 if it exists; Enter/click (0x27, 0x2d) picks the
  selected row of `LB_REPLIES` while replies are shown; while only an NPC line is shown (flag
  +0x1df8 bit 0, without bit 1) Enter, click (0x27) or a left press (0x1f9) instead asks the
  server to **skip the current line** (0x004ae970 with the speaker's id at +0x19c0); up/down move
  the selection.
- **Choosing a reply** (slot 27; letterbox 0x006a7e20): hands the index to the in-game GUI
  (0x0062ada0), which sends it to the server, then clears the panel and removes the bark panel.
- **Layout** (slot 28; letterbox 0x006a7ef0): the conversation panel spans the screen width with
  the letterbox bars; it positions one of the in-game GUI's small bar panels (+0x64) and the
  message label from the screen size. (med)
- The computer panel's backdrop is `WxHcomp0` / `WxHcomp1` (its own `GetResolutionTag`
  0x006a6e20 adds a digit to the `comp` suffix) and it overrides `OnAdded` / `OnRemoved`
  (0x006a6de0 / 0x006a6e00). (med)

#### Pazaak — skimmed

| Panel | Ctor / vtable | `.gui` | What |
|---|---|---|---|
| Side-deck setup | 0x00681a90 / 0x007532e8 | `pazaaksetup` | 18 available cards `BTN_AVAILxy` with `LBL_AVAILxy` and counts `LBL_AVAILNUMxy` (3 rows × 6), 10 chosen slots `BTN_CHOSEN0..9` / `LBL_CHOSEN0..9`; `BTN_ATEXT`, `LBL_LTEXT`, `LBL_RTEXT`; card hover 0x0067e530, click 0x006807e0, accept 0x006819e0. Opened by 0x005f3810 (the client's start-pazaak handler, gui sound 4); it builds the wager panel |
| Wager | 0x0067f000 / 0x007534c8 | `pazaakwager` | `LBL_WAGERVAL`, `LBL_MAXIMUM`, `BTN_LESS`/`BTN_MORE` (0x2f/0x30 thunks), `BTN_WAGER` (0x2d thunk), `BTN_QUIT` (back) |
| Game | 0x006808a0 | `pazaakgame` | 9 table slots per side `BTN_PLR0..8`/`BTN_NPC0..8` with labels, 4 side cards each `BTN_PLRSIDE0..3`/`BTN_NPCSIDE0..3`, `BTN_FLIP0..3` (± flip), `LBL_PLRTOTAL`/`LBL_NPCTOTAL`, set scores `LBL_PLRSCORE0..2`/`LBL_NPCSCORE0..2`, turn markers, `BTN_XTEXT`/`BTN_YTEXT` (end turn / stand); opened by 0x00681890 |

Full-screen with the `WxHpazaak` backdrop (resolution suffix 2). The game rules live in the
mini-game code; how the panels drive them is an open question. (low beyond the tags and
addresses)


## 11. Open questions

**System (§1–§9)**

- The `INNEROFFSET` text rectangle grows by `INNEROFFSET` vertically but by
  `min(INNEROFFSET, thickness)` horizontally as decompiled (0x00415240); confirm with `rex.py asm`
  before relying on the asymmetry.
- `spacingR` is applied twice-scaled by the viewport in the glyph advance (0x0045a850) but in full
  in the width measurement: it looks like an engine bug; check on screen with `fnt_console`
  centred text before reproducing it.
- Panel flag 0x10 (`AddPanel` flag 4, used for the global fade) and the manager counter +0x71 of
  panels without it are read by the client main loop; their effect was not traced.
- The list box "one text" mode (flag 0x100, 0x00419ee0), the pixel-scroll mode (0x0041a2d0), the
  "select on press" and "scroll only" flags, and scroll-bar thumb dragging (0x0041b670) were not
  read in detail; the click zones of the scroll bar and slider are inferred.
- The 150 ms debounce on events 0x2f..0x32 in `CSWGuiManager::HandleInputEvent`: which device
  produces those codes on PC (edit-box control characters only?) is not settled.
- Which key produces event 0xb5 (hard-wired to key 6) and whether 0xb4 is registered anywhere.
- The overlay drawn by `CSWGuiManager::DrawDebugOverlay` (0x0040bec0) when 0x007a3d4c is set.
- The cursor meaning of ids 47–50 (create) and of the 32 running/walking arrows (61–92) — the
  code that picks cursors (0x006222f0) belongs to movement.md.

**Front end and character generation (§10.1, §10.2, §10.5)**

- How `PB_PROGRESS` values are composed from the per-phase byte weights at client +0x3e4 (the
  phase table and its fractions; gameloop.md).
- The movies list rule (`movies.2da` `alwaysshow` versus "seen") and how a movie is played from
  `LB_MOVIES`.
- Credits text source and scroll speed (0x0068f880).
- Save/load list contents (which fields the rows and the details labels show; 0x006cc160) and
  the save-name rules (maximum length, allowed characters beyond the edit box's).
- Per-option mapping of every options control to its client option field and ini key
  (0x0061b780 / 0x0061dbe0); only the panel wiring was read.
- Character generation: what quick generation fills in automatically, the random name tables,
  the portrait list filter, how the class-selection slot table's class bytes are filled, the
  skills/feats/powers panels' internals, and the exact message sent to start the game
  (0x006dbdf0).
- Pazaak panels: how they drive the mini-game state and return the result.
- Conversation panels: the computer panel's skill/spike/repair counters, the letterbox geometry
  (0x006a7ef0) and the reply-list fill (dialogue.md).

**In-game GUI and HUD (§10.3)**

- Which condition turns a party member's vitality bar `redfill` (`0x006857d0`'s third argument):
  the decompiled call passes values in an order that cannot be right; needs `rex.py asm` of the
  call in `0x00687860`.
- The action-list builder `0x00619db0` (what goes into categories 0..5) and the target list
  builder `0x00689410` were not read; they decide what the action slots offer.
- `UseSelfAction` clears the leader's actions after queuing outside combat; the order relative to
  the callback looks odd and should be checked in the disassembly.
- `CGuiInGame+0xb4` (blocks menus) is set by conversation/cutscene code not traced here.
- The overlay list at HUD `+0x5cb4` (updated and drawn every frame) is not identified; likely the
  floating combat numbers ("Floating Numbers" option, bit 4).
- `LBLH_INV` pulsing condition (quest item repository count) is a guess.
- How the message log lines reach `LB_MESSAGES`/`LB_DIALOG` was not traced.
- `CSWGuiMessageBox` slot 32 (`0x006252a0`) runs on close; not read.

**In-game menus (§10.4)**

- The server flag at server internal +0x10004 → +0x104 bit0 that switches the menus from
  "change leader" to "view other NPCs" is not identified (player restrict mode is a guess).
- Which input raises event 0x2e (0xdf is Escape, key-map action 223; 0x2e looks like a gamepad
  back button and is not produced by the PC key map); 0x2d closes menus here but accepts in the
  galaxy map, party selection and upgrade screens.
- The meaning of equipment row states 2 and 3 on screen (colour) and of the `LBL_GOOD1..10` icon
  list on the character sheet.
- The character sheet's model-rotation event codes (the decompiler shows nonsense constants for
  the two handlers on `BTN_3DCHAR`; an `asm` look at 0x006b0e40 around the calls would settle it).
- Map: the map-view object at +0xe38 (world-to-map transform, note picking by click) and the
  Return action 0x00692bc0 were not read.
- Upgrade bench internals (slot-to-upgrade-type mapping, how `upgrade.2da` rows map to the three
  or four slots, `BTN_ASSEMBLE` effects) were only skimmed.
- Store buy/sell confirmation texts and the stock/infinite handling in `DoBuy`/`DoSell`.
- Journal quest list contents (which JRL fields, how priority and planet sorting are computed).

