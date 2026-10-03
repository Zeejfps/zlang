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
gameloop.md (frame, pause, module load), dialogue.md (conversation flow; the dialogue panels'
controls are here), party-items-saves.md (inventory, equipment, stores, save/load rules; the
panels that show them are here), rules.md (point-buy, skills, feats, powers, level-up rules;
the character-generation panels are here), movement.md (the world cursor and targeting),
combat.md.

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
- **The tooltip** picks `tooltip10X8`, `tooltip12X9`, `tooltip12x10`, `tooltip16X12` or the
  800x600 file by screen size (constructor 0x006277c0). (high)
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
thunks that resend a *panel-level* command to the owning panel: 0x00624ba0 → panel slot 20 →
event 0x27 (accept), 0x00624bb0 → slot 21 → 0x28 (back), 0x00624bc0 → slot 22 → 0x29,
0x00644720 → slot 23 → 0x2a, 0x0040b680 / slot 24 → 0x2b; 0x0067cb40 sends 0x2f, 0x0067cb50
0x30, 0x0067cb60 0x2d. The panel's own `HandleInputEvent` (slot 15) then does the work, so the
same code serves the button, the Escape key and the gamepad. A reimplementation should keep this
split: buttons emit commands, panels handle commands. (high)

## 8. Input routing and focus

### From the device to the GUI

`ProcessInput` (0x006227e0) reads the frame's mapped events for the current input class
(client +0x9c: 0 in-game, 1 mini-game, 2 GUI, 3 dialogue, 4 free look, 5 movie; the class
order follows the key-map columns, med). Events 0x27..0x40, and the GUI-reserved actions (the
arrow/Enter codes 0xb4..0xbb, Tab 0xce, Escape 0xdf, the menu-cycling Q/E actions 0xf3/0xf4,
the dialogue number keys 0xfe..0x106), go to `CSWGuiManager::HandleInputEvent` (0x0040c8e0)
when a GUI is in charge (input class 2 or 3, or the in-game GUI's "menu up" state); everything
else goes to the game (`HandleInputAction` 0x00621210). After the events the cursor position goes
to `HandleMouseMove` (0x0040c1e0). (med)

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
  flag (+0x1c bit 3) so `Render` draws the tooltip panel. Placement of the tooltip panel: see
  §10. (high for the text, med for the 2DA row arithmetic)
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

<!-- PANEL-CATALOGUE -->

## 11. Open questions

<!-- OPEN-QUESTIONS -->
