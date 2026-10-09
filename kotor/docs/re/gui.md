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
The whole page was rechecked claim by claim on 2026-10-08 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check"
rests on static reading alone and is surprising enough to test before relying on it.

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
by 0x0073ad80): 0 `back`, 1 `store`, 2 `pazaak`, 3 `map`, 4 `comp` (the store sets 1, the
pazaak panels 2, the galaxy map 3; `comp` is used only by the computer panel's own
`GetResolutionTag` 0x006a6e20, which appends a digit). The result names a backdrop
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
| 0x001 | "placed in screen space": hit tests use the computed screen rectangle; set by `CenterOnScreen` (0x0040a600) and by constructors that position themselves (HUD, main menu, credits, tooltip, status summary, pause, conversation panel) |
| 0x004 | active: updated and drawn |
| 0x008 | full-screen menu: centred on screen, draws the backdrop, hides panels below it (§8); set by `AddPanel` flag 2 |
| 0x010 | set by `AddPanel` flag 4 (the HUD, the bark bubble, the fade panel ...); such panels are not counted in manager +0x71, which only the client main loop reads, when it takes a screenshot (render-gui.md) (purpose med) |
| 0x020 / 0x040 | centre horizontally / vertically as if the panel were inside a 640x480 frame |
| 0x080 | visible this frame (recomputed by `UpdateTopPanel` 0x0040acc0) |
| 0x200 / 0x400 | removal request, read after this frame's draw as the field `(flags >> 9) & 3`: 1 (0x200) remove, 2 (0x400) remove and delete, 3 (both) only remove. Panels that close for good set 0x400 (save name, main menu, credits ...); the message box and the bark bubble set 0x200 |

The screen rectangle (`GetScreenExtent` 0x0040aa00) is the panel extent, then:
1. if flag 0x08: `x += (screenW - w) / 2`, `y += (screenH - h) / 2` (integer division), and stop;
2. else if 0x20: `x += (screenW - 640) / 2`; if 0x40: `y += (screenH - 480) / 2`.

Hit tests and "mouse position inside the panel" (`HitTest` 0x0040b690,
`GetLocalMousePosition` 0x0040ba20) use that rectangle only when flag 0x01 is set; otherwise
they subtract `((screenW - 640) / 2, (screenH - 480) / 2)` from the cursor and compare with the
raw extent, i.e. they assume the panel sits in a centred 640x480 frame. The two agree for every
combination the game uses:

- **Full-screen menus** (640x480 files at 0,0) carry flag 2: they are centred, and the backdrop
  fills the rest. The eight in-game menus (equipment, inventory, character, abilities, messages,
  journal, map, options) are **not modal**: `ShowInGameMenu` (0x0062c9b0) and `SwitchInGameMenu`
  (0x0062cf10) add the menu with `AddPanel(menu, 2, 1)` beside the top menu bar (flag 0) and bring
  it to the front. Screens opened from them or from the main menu (options sub-panels, save/load,
  level-up and character-generation steps, store, upgrade, the main menu's options and movies)
  use `AddPanel(panel, 3, 1)`: modal + full screen.
- **Dialog boxes** (message box, save name, skill info, container, ...): the constructor calls
  `CenterOnScreen` (x = (screenW - w) / 2, y = (screenH - h) / 2, flag 0x01), then
  `AddPanel(panel, 1, 1)` (modal only). Their `.gui` LEFT/TOP are ignored.
- **The main menu** (`mainmenu`, 800x600 in `patch.erf`, 640x480 in `gui.bif`): flag 0x01 in
  `InitPanel`, added with flag 2: centred, with the `WxHback` backdrop around it.
- **The loading screen and the character-generation steps** set 0x20|0x40 (centred 640x480
  frame) and draw their own full-screen background label (§10).
- **The HUD** (`CSWGuiMainInterface`) loads a `.gui` chosen by the screen width (and, 1280 wide,
  the height) and sets flag 0x01 at its file's 0,0: `mipc210x7` (1024 wide), `mipc212x9`
  (1280x960), `mipc212x10` (1280x1024, `patch.erf`), `mipc216x12` (1600 wide), `mipc28x6` (every
  other width: 800x600 and every unsupported size). A 1280-wide mode with another height loads
  **no** file (the code falls through):
  a reimplementation should map it to the closest file. The files `maininterface`, `mi8x6`,
  `mipc8x6`, `mipc10x7`, `mipc12x9`, `mipc16x12` are not referenced by the code (Xbox / older
  layouts). (high)
- **The tooltip** picks `tooltip16X12` (1600 wide), `tooltip12X9` (1280x960), `tooltip12x10`
  (1280x1024), `tooltip10X8` (1024), `tooltip8X6` (800), else `tooltip6X4`, by screen size
  (constructor 0x006277c0; as for the HUD, a 1280-wide mode of another height loads none); it is
  placed at the cursor (§10.3). (high)
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
6. unless the free-look camera is active (0x005ee230 asks the module camera whether it is type
   0x106e, [movement.md](movement.md) 2.1): the tooltip panel if showing, and the tooltip timer
   (§9);
7. the software cursor (+0x20, §9);
8. panels with a removal request (0x200 / 0x400, §2) are removed, those with 0x400 alone also
   deleted; then the debug overlay when its global (0x007a3d4c) is set.

`CSWGuiPanel::Render` (0x0040b760) draws only if the panel is visible (0x80), has a positive size
and its file extent (before the placement of §2) lies inside the screen (x, y ≥ 0,
x + w ≤ screenW, y + h ≤ screenH); otherwise it
draws nothing at all. It pushes a viewport over the panel's screen rectangle — filled with the
panel `COLOR` when that is not (-1,-1,-1), at the panel `ALPHA` — then draws the panel's
`BORDER`, then every control in the array whose visible flag (control +0x44 bit 1) is set, in
index order. (high)

**Quads.** Border corners and edges go through one batch (`DrawBatchedPixels` 0x00459800 →
0x0045b290): a quad at pixel
(x, y, w, h) inside the current viewport is converted to viewport fractions; texture v = 1 is
the top edge (textures are stored bottom-up); optional flips (bits 2–3 of a style word) and
rotations of 0/90/180/270 degrees permute the texture corners; a colour of (-1,-1,-1) means
"untinted". The batch flushes on a texture, colour-mode or alpha change. Border fills are not
batched: they are drawn at once (`DrawImmediatePixels` 0x00459920 → 0x004599b0: the same
corner, flip and colour rules, plus arbitrary rotation angles), and text glyphs are emitted
directly by the string's draw (§5). (high)

**Blending.** The batch's flush (`AurGui_FlushQuadBatch` `0x0045a170`) binds the texture and calls
`0x0047b000`, which sets `glBlendFunc` from the texture's own blend pair (render-gui.md, Materials): the
default (`SRC_ALPHA, ONE_MINUS_SRC_ALPHA`), or `SRC_ALPHA, ONE` for a TXI with `blending additive`. So
the 44 GUI pictures that say so (the HUD's `lbl_mileft`, `lbl_mileftbk`, `lbl_miport1-3`, `lbl_mibox00`,
`lbl_minimap`, `lbl_mirightbot`, the menu buttons `lbl_mimsg` and its kin, the four reticles and
arrows, `menuborders`, `innermenu`) add their colour to the screen and their black is clear. (high)

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

1. **Thickness** (`GetThickness` 0x00414cd0). If `DIMENSION` > 0, corners are `DIMENSION` x
   `DIMENSION`, edges are `DIMENSION` thick and edge segments `DIMENSION` long. If `DIMENSION` is
   0 and both corner and edge textures exist, the corner texture's *height* takes its place
   (square corners; the edge texture's own size is never used). If `DIMENSION` is 0 and there is
   no edge texture, the corners are the corner texture's width x height. (No border in the data
   has corner and edge textures with `DIMENSION` 0.)
2. **Corners**, only if a corner texture exists: one texture, drawn four times: top-left as is,
   bottom-left rotated 90°, bottom-right 180°, top-right 270° (the art is the top-left corner).
3. **Edges**, only if both a corner and an edge texture exist (a border with an edge texture
   but no corner texture draws no frame at all: 13 such borders in the data, the `bluefill` /
   `yellowfill` frames of the HUD files); edges are as thick as the corners. The gap between the
   corners along the top is
   `w - 2*corner`. It is cut into `n = gap / segment` segments (if that is 0 but the gap is at
   least half a segment, one segment); the leftover pixels are spread so the segments exactly
   fill the gap, the first `leftover mod n` segments one pixel wider. Top segments are drawn
   unrotated, bottom ones rotated 180°, left ones 90°, right ones 270° (the art is the top edge).
   Along an axis too short for even one segment, the corners take half of the extent on that
   axis (an odd size shifts the far corner by one pixel).
4. **Fill**, only if a fill texture exists, drawn after the frame, inside the corners (the whole
   extent when there is no corner texture, whatever `DIMENSION` says), tinted by `COLOR`, with
   the fill alpha; `FILLSTYLE` defaults to 0 when missing:
   - `FILLSTYLE` 2 — stretched: one quad over the area (3,602 of the 3,619 border structs in the
     game's `.gui` files, `patch.erf` overriding `gui.bif`);
   - `FILLSTYLE` 0 — tiled: like the edges, the area is cut into whole tiles of the texture size
     in both directions, each stretched slightly so they fill the area exactly (0x004155b0);
     a dimension smaller than one tile is covered by a single span of that size (there is no
     half-tile rounding as for edges);
   - `FILLSTYLE` 1 — centred: the texture at its natural size, centred; a dimension where the
     texture is larger than the area is squeezed to the area (0x004157f0).
5. `COLOR` tints corners, edges and fill alike; (-1,-1,-1) and the default (1,1,1) both mean
   untinted.

**`INNEROFFSET`** does not affect the border drawing. It only moves the *text* rectangle of
labels, buttons and list rows: the text area is the border's inner rectangle, inset on each side
by the thickness of step 1 (`DIMENSION` whether or not a corner texture exists; 0 when
`DIMENSION` is 0 and the border lacks a corner or an edge texture; if the extent is too small, a
zero-size rectangle at the centre), grown outward by
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
  `spacingR` (0.02), so console-font text that is centred or right-aligned ends up nearly 2 pixels
  per character left of where its measured width says (the draw adds `spacingR * 100 * T /
  viewportW` pixels: 0.4 for the 128-pixel console font in a 640-wide viewport). Reproduce:
  advance = glyph width; measured line width (the layout pass, 0x0045a2f0) =
  `trunc(w * scale)` for the line's first glyph plus `trunc((w + spacingR*100) * scale + 0.25)`
  for each further glyph, `w` the glyph width in pixels. (The draw has a fallback that measures a
  line when no width is stored, but the layout always stores one per line, so it never runs.)
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
4. If the line overflows with no break opportunity, the word is split before the last character
   that still fit: that character and the overflowing one move to the next line, and the line is
   marked (negative character count) to draw a **`-`** after it; its width is the width up to the
   split plus the hyphen glyph's. If the split would leave the string's first line empty (only
   one character fits), no lines are produced at all.
5. Very narrow boxes: a string of one or two characters is not laid out at all if the box is
   narrower than two `o`s (the one-`o` test the code also makes for a single character is
   subsumed by it).

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
| 16 | middle: the block offset by `(rectH - lines * lineH) / 2`; if that is negative, **leading lines are dropped**, each adding a whole `lineH` to the offset, until it is no longer negative: about half the overflow is cut from the top and the rest hangs past the bottom (clipped), so overflowing centred text shows its middle |
| 32 | bottom: the block offset by `rectH - lines * lineH`; if the block is taller than the rectangle, leading lines are dropped until the rest fits (so overflowing bottom-aligned text shows its end) |

The data uses 9, 10, 12, 17, 18, 20 and 34. A line is drawn if its top is above the rectangle's
bottom (it may hang over; the viewport clips it); lines wholly above the viewport (scrolled
text) are skipped; drawing stops once a line's top passes the viewport bottom. The default for a
text struct without `ALIGNMENT` is 9. (high)

### Text colours set by code

| Constant | Value (RGB) | Use |
|---|---|---|
| 0x0078d3c0 | (0.98, 1.0, 0.0) yellow | button text while hilighted (0x00418e00); also pulses (high) |
| 0x0078d3b4 | (0.0, 0.33, 0.49) dim blue | text of a disabled label (0x00418d00) (high); a disabled button sets it too (0x00418db0), but the un-hilight that follows restores the file colour (§6, Enabled) (med) |
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
| +0x54 / +0x55 | click sound (default 0, `gui_click`; the check box uses 3, `gui_check`) / focus sound (default 1, `gui_scroll`), played when the panel's keyboard focus (0x0040a630) or a list selection lands on the control; mouse hover always plays sound 1. Indices into guisounds.2da |

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

**Enabled.** Disabling a label (slot 34, 0x00418d00) clears flag 0x08 and recolours its text dim
blue (0x0078d3b4). Disabling a button or check box (0x00418db0) clears 0x08, sets the dim blue,
then drops the hilight through slot 16, whose button version (0x00418e00) restores the file
colour: as read, a disabled plain button keeps its file colour, not dim blue (med, needs a
runtime check; the options panels' menu check box recolours itself every frame, below).
Re-enabling restores the file colour. Disabled controls ignore clicks (no 0x27, §7) and are
skipped by keyboard navigation.
(high)

**Check box.** Holds its state at +0x1c8 bit 0; it toggles on the event stored at +0x1c4 (0x27,
activate, set by the constructor 0x0041ca30, which also makes its click sound 3, `gui_check`)
before the normal button handling (0x0041adb0). (high)

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
`PROGRESS` rectangle is the `BORDER`'s text rectangle (inner rectangle grown by `INNEROFFSET`, §4)
cut down along its long axis (vertical when
taller than wide): the filled length is `trunc(frac * length)`; with `STARTFROMLEFT` = 1 it is
anchored left (or top), with 0 right (or bottom). The HUD's vertical health and Force bars use 0
(fill from the bottom); the target health bar uses 1. With `MAXVALUE` 0 the whole rectangle is
drawn. (high)

**Slider** (thumb 0x00418f20, input 0x0041adf0, drag 0x00419250): value 0..`MAXVALUE`. The
thumb keeps its texture's natural size along the slider and spans it across; its position is
`start + (length - thumbLength) * value / max`. Horizontal sliders (w ≥ h): left (0x3f, 0x2f)
and wheel-down (501) decrease by 1, right (0x40, 0x30) and wheel-up (500) increase; vertical
sliders (h > w): up (0x3d, 0x31) and 501 decrease, down (0x3e, 0x32) and 500 increase (the value
grows downward). A change plays the slider's sound (+0x78). Clicking the bar before or after the
thumb steps by one (0x004191d0 sends the slider 501 / 500); dragging sets
`value = max * (mouse - start) / length`, clamped. (high for keys and the formula, med for the
click zones)

**Scroll bar** (0x00419660; inside list boxes only): fields +0x5c max, +0x60 current, +0x64
visible (setters 0x00418070 / 0x004180a0 / 0x004180d0; current is clamped to 0..max, visible to
≥ 1 unless max is 0). `DRAWMODE` 0 draws the border, the thumb and both arrows; `DRAWMODE` 1
draws only the arrows, each only while scrolling that way is possible. The `DIR` image is the
"up" arrow: drawn at the top (left) end, and flipped at the bottom (right) end. In a list box,
pressing an arrow scrolls one row (0x1fb / 0x1fc) and pressing the track pages (0x1fd / 0x1fe);
while the button is held and the cursor stays on the same zone, the list's render (0x0041a3e0)
repeats the event after 0.5 s and then every 0.1 s; pressing the thumb drags it. (high for
drawing and the repeat, med for the zone geometry)

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
needs layout, 0x10 scroll bar on the left, 0x20 scroll bar shown, 0x40 `LOOPING`, 0x80 the window
is anchored at its first row (variable rows, below), 0x100 rows of different heights, 0x200
"scroll only, no selection", 0x400 draw only fully visible rows, 0x800 pulse the scroll bar,
0x1000 keep the selection in view, bits 13–16 the prototype's CONTROLTYPE). +0x2b8 is a float, the
box height over one line of the row's font (1.0 until set), +0x2ca the last visible row. (high)

- **Prototype.** `PROTOITEM` is read once into a template control of type 4–8 (0x0041d3e0);
  panels fill the list by creating row controls (usually copies of the template made by the
  panel code) and handing them over with `SetItems` / `SetItemsArray` (0x0041c1d0 / 0x0041c2c0,
  which renumber each row's `ID` to its index and make the list its owner) or by adding text in
  "one text" mode. (high for the template, med for how panels copy it)
- **Layout** (`UpdateLayout` 0x0041b140): row height = the tallest row; stride = row height +
  padding; visible rows = `areaH / stride`. Visible rows are placed from `y = padding`, each
  stretched by `(areaH - visible*stride - padding) / visible` pixels, the remainder spread one
  pixel per row; rows are inset by the padding on both sides (`width = areaW - 2*padding`);
  rows above and below the window are placed outside the area and not drawn. The scroll bar gets
  `max = count - visible + 1` (at least 1), `visible = min(visible, count)` (1 in "scroll only"
  mode), `current = first visible row`. (high)
- **Rows of different heights** (flag 0x100, the last argument of `SetItems`/`SetItemsArray`; the
  conversation's replies use it, 0x006a86a0): `LayoutText` (0x00419ee0) stacks the rows by their own
  heights from the first visible row down (flag 0x80) or from the last visible row up, works out
  the other end, and gives the bar max = count - shown + 1, visible = shown, current = first row.
  Such a list never scrolls by pixels. (Earlier notes called this "one text" mode; it is not.) (high)
- **Tall content** (`IsPixelScrolling` 0x0041a290): a list of fixed-height rows (no 0x100) with
  at least one row, whose tallest row plus the padding is taller than the row area. Descriptions
  are such lists: `CSWGuiStore::SetDescription` (0x006c0690) and its kind clear the list, size one
  label to the whole wrapped text (height = text height, or one line when empty), hand it over as
  the only row and select it (no sound). Then (high):
  - Layout: +0x2b8 = area height / line height of the row's font; the scroll position +0x2c2 runs
    from 1 to `steps = ceil(rowH / lineH) - floor(areaH / lineH) + 1` (0x004182b0; the ceiling is a
    +0.99998 before truncating), i.e. lines - whole lines in the box + 1. Only the first row is
    placed and drawn (0x0041a2d0): at position `n` its top is `padding - (n-1) * lineH` (computed
    as `(n-1) * areaH / ratio`, truncated); at the last position it is `areaH - rowH - padding`, so
    the text's end sits `padding` above the bottom; its width is the area's minus twice the padding.
  - Scroll bar values: max = rowH - areaH + 1, visible = areaH (UpdateLayout's branch for zero whole
    rows), current = 0 at the first position, rowH (clamped to max) at the last, else
    `(n-1)/(steps-1) * (rowH - areaH)` truncated.
  - One step is one line: wheel 500/501 and the arrow presses 0x1fb/0x1fc move the position by 1;
    the up/down keys (0x3d/0x31, 0x3e/0x32) too, but only while the list has a selection (they do,
    see above), and a move plays the list's move sound; a press on the track (0x1fd/0x1fe) moves
    `floor(ratio)` steps (the whole lines the box holds). All clamp to 1..steps.
  - Dragging the thumb (`OnMouseDrag` 0x0041b670): position = the position at the press + `dY *
    (steps - 1) / (track height - thumb height)` + 0.5, truncated and clamped; rows lists do the same
    with the first row and max - 1.
  - `ClearItems` (0x00419a90) puts the position back to 1, so a new description starts at the top.
- **Keeping the selection in view**: after `SetSelectedIndex` (0x0041c040) the first visible row
  moves just enough to show the selection; scrolling with the wheel or the scroll bar turns
  this off until the next selection. (high)
- **When the scroll bar shows.** The constructor sets flag 0x20 and no list code clears it, so a
  list draws its bar whenever it has one, scrollable or not (`DRAWMODE` 0: border, a thumb that fills
  the track, both arrows). Two exceptions: the conversation's replies set 0x20 only while the last
  visible row is not the last row (0x006a86a0), and the message box's `FitToText` gives the bar
  width 0 (`PlaceScrollBar` 0x004181f0) while it fits the text, and its width back only if the text
  still overflows. (high)
- **Thumb** (the bar's `SetExtent` 0x004193f0, run by every value setter): the track is the inner
  rectangle of the bar's border between the two arrow squares; with max > 1 the thumb is
  `track * visible / (visible + max)` long (at least 4) at `(track - length) * current / (max - 1)`;
  with max ≤ 1 it fills the track. `DRAWMODE` 1 draws the up arrow when `visible < max` and current
  ≥ 1 (0x00418010), the down arrow when `visible < max` and `current + visible < max` (max + 1 for a
  one-row window not in "scroll only" mode and not at max; 0x00418030). So with rows lists the down
  arrow goes before the end, and a tall text less than twice its box shows no arrows. (high)
- **Drawing** (0x0041a3e0): the scroll bar (if shown), the list `BORDER`, then a viewport over
  the row area filled with `COLOR` unless it is (-1,-1,-1) — a list whose file says (0,0,0) gets
  a black background — and the rows that intersect it. (high)
- **Selection** (`SetSelectedIndex`): the old row gets event 1 (un-hilight), the new one event 0
  (hilight) and, if asked, its hover sound; -1 clears it. (high)
- **Keys** (0x0041ce20): up (0x3d, 0x31) selects the previous row; at row 0 with `LOOPING` it
  wraps to the last, else nothing; down (0x3e, 0x32) the next, wrapping to 0 with `LOOPING`;
  with no selection, down selects row 0 with its sound and up selects it silently (lists in
  "scroll only" mode move the window instead); in a pixel-scrolling list with a selection, up/down
  move the pixel scroll instead. A change plays the list's move sound. Wheel 500 scrolls up one
  row, 501 down one; 0x1fb/0x1fc scroll one row (arrow clicks); 0x1fd/0x1fe a page (`visible`
  rows). Every event is then forwarded to the selected row (so Enter reaches a row button) and finally to the
  list's own handlers. (high)
- **Mouse** (0x0041c4a0 / 0x0041a700): pressing on a row of an enabled list sends the list 0x1f9
  only when the press is a double-click (manager +0x1c bit 0) on the hovered list. Then, in lists
  whose flags have bit 0 set or whose first row is a button, the pressed row is selected at once
  (with its sound); otherwise the list only remembers the pressed row and does not select it
  itself, on press or release. Either way it then sends 0x1f8. Releasing on the remembered row
  sends 0x27 to the list (in the select-at-once case, the release of a double-click does). Panels
  hook 0x1f8 ("row clicked") and 0x27 ("row activated") on the list. Pressing on the scroll bar's
  arrows, thumb or track scrolls as above and captures the mouse. (med)

## 7. Events and handlers

### The handler table

`SetEventHandler(control, event, owner, callback)` (0x0041ab20) adds an entry, replaces the
callback of an existing entry for that event, or removes it when the callback is null; a control's
`HandleInputEvent` (0x00418750) first handles events 0 and 1 itself (with a non-zero value: 0
hilights, 1 un-hilights if hilighted), then finds the first entry for the event with a callback,
stores the event and value at +0x48/+0x4c and calls the callback as a method of the owner with the
control as its argument. A selectable control (`CSWGuiSelectable`, 0x0041a9d0) first follows
`MOVETO` for the direction events with a non-zero value (0x3d/0x31 up, 0x3e/0x32 down, 0x3f/0x2f
left, 0x40/0x30 right): it walks the link in that direction, skipping controls that are not
enabled (flag 0x08) and stopping with no move at a missing link or when it comes back to itself,
and asks the panel to make the result its active control (panel slot 2, with the hover sound);
then it dispatches as above. A button (0x0041ad40) plays its click sound (control +0x54, default
row 0) on 0x27 with a non-zero value before that. (high)

### Event codes

| Code | Meaning | Source on PC |
|---|---|---|
| 0 / 1 | gain / lose hilight (hover or keyboard focus) | the manager, `SetActiveControl`, list selection (high) |
| 0x27 | activate / accept | left-button release on an enabled control; Return (key event 0xb5) and numpad Enter (0xbb), remapped by the manager; Enter typed into an edit box (sent to its panel) (high) |
| 0x28 | back / cancel | Escape (key-map action 223 "GUI", event 0xdf, bound in the in-game, GUI and free-look classes); Esc typed into an edit box. 0xb4 is remapped too, but the PC key map never produces it (high) |
| 0x29, 0x2a, 0x2b | third, fourth, fifth panel command (delete, recommended, default ...) | buttons via thunks (below) (high) |
| 0x2d | second accept code: 63 registrations next to 0x27 in 28 panel constructors (main menu, character generation, level-up, options, store, upgrade, party selection ...); the in-game menus close on it as on 0x28 | the pazaak Wager thunk; not produced by the PC key map (high) |
| 0x2e | gamepad back: most panels' `HandleInputEvent` treat it like 0x28 (in-game menus, chargen, options, store ...) | not produced on PC (high) |
| 0x2f / 0x30 | single-step left / right: MOVETO left/right (like 0x3f/0x40), a horizontal slider's minus/plus; minus/plus and arrow buttons send these to their panel | thunks; edit-box characters 0x1c / 0x1e (high) |
| 0x31 / 0x32 | single-step up / down (treated like 0x3d/0x3e by lists, vertical sliders and MOVETO) | edit-box characters 0x1d / 0x1f (high) |
| 0x33, 0x34, 0x37, 0x38 | analog axes; a value of +1/-1 folds them into 0x3e/0x3d, 0x40/0x3f, 0x3a/0x39, 0x3c/0x3b | gamepad; not produced by the PC key map (high) |
| 0x3d / 0x3e / 0x3f / 0x40 | up / down / left / right (MOVETO, lists, sliders) | arrow keys (key events 0xb6, 0xb7, 0xb8, 0xb9, GUI and dialogue classes) (high) |
| 0x44 | right-click release on an enabled control | (high) |
| 500 / 501 | wheel forward / back; a list box gets one per 120 units of wheel delta and scrolls like 0x1fb / 0x1fc, any other control one per wheel message | `HandleMouseWheel` 0x0040c650 (high) |
| 0x1f8 | list row pressed (sent by the list on the left press, after it selects the row) | list box 0x0041c4a0 (high) |
| 0x1f9 | double-click: sent to the control before 0x27 when the release ends a double-click press, and by a list box on a double-click press on a row; in the dialogue input class (3) every left press also sends it to every panel | `HandleLeftMouseUp`, list box, `HandleLeftMouseDown` (high) |
| 0x1fb..0x1fe | list: row up, row down, page up, page down (presses on the scroll bar's arrows and track) | list box (high) |

Events 0x2f..0x32 also take part in a 150 ms debounce in `HandleInputEvent`: a 0x2f/0x30 that
arrives within 150 ms of a 0x31/0x32 (or the reverse) is dropped and reaches no panel (last code
manager +0x72, its time +0x64). (high)

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
(client +0x9c: 0 in-game, 1 mini-game, 2 GUI, 3 dialogue, 4 free look, 5 movie; the key-map
columns ICPC, ICMiniGame, ICPCGUI, ICDialog, ICFreeLook, ICMovie enable an action for classes 0..5
in that order, `SetupKeymapping` 0x005eeb10, high). While the HUD is up or the class is GUI or
dialogue, only the first press-type event of the frame (1, 2, 0xa, 0xb, 0x27..0x2e, 0x35, 0x36)
is kept. Per event:

- a **GUI-reserved action** — the arrow/Enter codes 0xb4..0xbb, Tab 0xce (change character),
  Escape 0xdf, the menu-cycling Q/E actions 0xf3/0xf4, the dialogue number keys 0xfe..0x106 —
  or any event 0x27..0x40 goes to `CSWGuiManager::HandleInputEvent` (0x0040c8e0), provided the
  input class is GUI or dialogue or the in-game GUI's HUD mode (`CGuiInGame` +0x34) is 1
  ("game", the HUD is up);
- except that in HUD mode 1 the GUI-reserved actions outside 0x27..0x40 go to the game instead
  (`HandleInputAction` 0x00621210, which opens menus, cycles characters, etc.);
- and except that in free-look (camera mode 5, options +0x6d) a press bound for the GUI ends the
  free look instead (interface shown, default camera, input class 0), unless `CGuiInGame` +0xdc
  is set;
- everything else goes to `HandleInputAction`.

After each event the cursor position goes to `HandleMouseMove` (0x0040c1e0) unless mouse-look is
active outside the GUI class, or the class is free look (4). HUD modes (`SetHudMode` 0x0062aa00):
1 game (HUD up); 2 mini-game, set only by `SetInputClass(1)` and on the return to the main menu
after the party is lost (MainLoop 0x00602eb0); 3 a menu, conversation (`ShowConversationPanel`
0x0062b730), store or galaxy map (§10.3). (high)

`HandleInputEvent` remaps the key codes (0xb5/0xbb → 0x27, 0xb4/0xdf → 0x28 on a press,
0xb6..0xb9 → 0x3d..0x40) and folds the axes; then **if the modal stack is empty it offers the
event to every panel in the list (in list order, over a copy of the list, skipping panels removed
meanwhile), otherwise only to the top modal panel**. A panel's default `HandleInputEvent`
(0x00409e60) passes it to its active control (+0x1c). Afterwards panels marked for removal are
reaped, and the `RIMS:MAINMENU` / `RIMS:CHARGEN` images are dropped when the resource manager
asks for it. (high)

### The modal stack

`AddPanel(panel, flags, playSound)` (0x0040bc70): plays the panel's open sound (+0x60, none by
default) if asked; a panel not yet in the list gets flag bits 1–2 copied to panel flags
0x08/0x10 and is appended; a panel already in the list only has a pending removal cancelled, and
if none is pending the call stops there. It then pushes the panel on the modal stack if bit 0 is
set, calls the panel's `OnAdded` (slot 18; base 0x0040b870: relayout, refresh the hover control,
re-hover it if it belongs to this panel), and recomputes visibility.
`PushModalPanel` (0x0040bd90) un-hovers the hovered control, adds the panel if it is missing, and
drops edit-box focus before pushing. `PopModalPanel` (0x0040be00) pops and gives focus back to the
new top's active control. `RemovePanel` (0x0040c830) pops or extracts it from the stack, calls
`OnRemoved` (slot 19; base 0x0040c170: hides the tooltip, drops the edit focus if the edit box is
the panel's active control, un-hovers a hovered control of the panel), removes it from the list,
re-runs the hover test at the current cursor, and clears the mouse capture without notifying the
holder. `BringPanelToFront` (0x0040bd20) moves a non-modal panel to the end of the list.
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
- **Moving the mouse** (`HandleMouseMove`): the cursor model moves first; if a control holds the
  mouse capture and its drag call (slot 4) returns non-zero, nothing else happens; otherwise the
  hover is re-tested. A newly hovered selectable control is told to take the hover (control slot
  3: hilight and the hover sound `gui_scroll` if it was not hilighted) and, when it has control
  flags 0x04 and 0x08, becomes its panel's active control (0x04 is set by the selectable and
  edit-box constructors and cleared for labels and progress bars); its selectable ancestors
  (`Obj_ParentID` chain, control +0x14) are hilighted too; the previously hovered control and its
  ancestors are un-hilighted unless they are ancestors of the new one. Leaving all controls
  un-hovers. (med for the ancestor rules)
- **Keyboard focus**: the panel's *active control* (+0x1c) receives the panel's events.
  `SetActiveControl(control, bSound)` (0x0040a630) sends 1 to the old and 0 to the new and, when
  asked, plays the new one's hover sound (+0x55). Arrow keys move it along `MOVETO` (§7). Mouse
  hover and keyboard focus are the same thing: hovering a button makes it the active control.
  (high)
- **Text focus**: only edit boxes; manager +0x18. Typed characters (window message path,
  `HandleCharacter` 0x0040b2a0) go to it, and with a modal panel up only if it is the top modal
  panel's active control. (high)

### Clicks, capture and GUI-versus-world

- **Left press** (`HandleLeftMouseDown` 0x0040c570, from the client's 0x0061f880, which calls it
  only while mouse-look is off and the class is not free look, or in the GUI and dialogue
  classes): stores whether the press is a double-click (manager +0x1c bit 0, from the event value
  -1), hides a shown tooltip, and, unless a control already holds the left capture, sends 0x1f9
  to every panel when the input class is dialogue, re-tests the hover, stops the tooltip timer
  (below) and calls the hovered control's left-down slot (6), which captures the mouse for that
  control (or passes the press to its selectable parent). It returns 1 when a control was under
  the cursor, but the client ignores the result: the press itself never starts a world action.
  (high)
- **Left release** (`HandleLeftMouseUp` 0x0040a170): if a control holds the left capture, it gets
  the left-up slot (7): if the cursor is still on it (or on a control whose selectable parent it
  is) it sends 0x1f9 if the press was a double-click, and **0x27 if the control is enabled**; then
  the capture is released. It returns 1 if a control held the capture. The client's left-up
  (0x00620530) runs the **world click only when the GUI did not consume it**, with one exception:
  when the hovered control is one of the target block's name/health controls (`LBL_NAME`,
  `LBL_NAMEBG`, `LBL_HEALTHBG`, `PB_HEALTH` of `CSWGuiTargetInfo` in the HUD, test 0x00684ed0
  returning 1) the click goes to the world and the GUI's release handler is not called at all, so
  a capture taken by the press stays set (med, needs a runtime check). (high for the rule)
- **Right button** (manager 0x0040c610 / 0x0040a1a0, from the client's 0x0061f940 / 0x0061f960,
  which also hold the look-about flag): the same with capture button 4 and event 0x44 on release;
  the press acts only while no control holds any capture, there is no dialogue broadcast, and the
  client has no world action for the right button. (high)
- **Wheel**: hides a shown tooltip and goes to the control under the cursor, not the focused
  one: a list box (or a control inside one) gets one 500/501 per 120 units; another control
  passes a single 500/501 to itself or its selectable parent, if that is enabled. (high)
- **Capture** (`SetMouseCapture` 0x0040a1c0 / `ReleaseMouseCapture` 0x0040a200): one control
  and a button id (1 left, 4 right); setting a new one tells the old one it lost the capture
  (slot 5). (high)

## 9. Sounds, tooltips and the cursor

### guisounds.2da

Loaded once by `LoadGuiSounds` (0x00409f00) from column `SoundResRef`; `PlayGuiSound(n)`
(0x0040a140) plays row *n* if it exists (*n* is a signed byte; 0xff, a panel's default open
sound, plays nothing). Rows: 0 `gui_click` (default click), 1 `gui_scroll`
(default hover; also every focus move), 2 `gui_error`, 3 `gui_check`, 4 `gui_open` (full-screen
menu opened), 5 `gui_close` (closed), 6 `gui_actuse`, 7 `gui_actscroll`, 8 `gui_button` (action
menu: use, scroll, queue), 9 `gui_invadd`, 10 `gui_invselect`, 11 `gui_invdrop`, 12 `gui_level`
(level-up available), 13 `gui_quest`, 14 `gui_complete`, 15 `gui_prompt`, 16 `gui_upgrade`.
Sounds 4/5 are played by the in-game GUI's open/close code (`ShowInGameMenu` 0x0062c9b0 /
`HideInGameMenu` 0x0062cba0, the galaxy map 0x0062d040 / 0x0062d1d0, the store 0x0062e310 /
0x0062e4a0, party selection 0x0062dd20 / 0x006be560), not by `AddPanel`. (high)

### Tooltips

- The tooltip panel (`CSWGuiToolTip` 0x006277c0, manager +0x3c) is a one-label panel (label
  `tooltip`) from the `tooltip*` file for the resolution: `tooltip8X6` at 800 wide, `tooltip10X8`
  at 1024, `tooltip12X9` / `tooltip12x10` at 1280x960 / 1280x1024 (no file at other 1280
  heights), `tooltip6X4` at any other width. At 1600 wide it loads `tooltip16X12` and then also
  `tooltip6X4`, because the width tests fall through (med, needs a runtime check). (high)
- Timer: the manager keeps a hover timer (+0x44, -1 = stopped) and a delay (+0x48). A change of
  hover restarts it at 0 (`ResetTooltipTimer(0)` 0x0040b500 → `RestartTooltipTimer`
  0x0040b4d0) **only if tooltips are enabled** (client options +0x14 bit 0x400, on by default). A
  left or right press stops it and blocks restarts (`ResetTooltipTimer(1)`: lock +0x4c, the
  hovered control or list row at +0x50) until the hover moves to another control or row; that
  move only clears the lock, so the timer starts again on the next hover change. The wheel never
  restarts it. Each frame `Render` advances it by the frame time; once it passes the delay it
  asks the hovered control for its tooltip (slot 36, 0x00418a90), stops the timer, and
  remembers the control (+0x40) if it produced one. The delay is the option at client options
  +0xc (default 1.0 s, `CClientOptions::SetDefaults` 0x0061db60); while the "ToolTips" key (key
  map action 225, `T`) is held it is 0, so tooltips appear at once (0x005f4be0). (high; the lock
  sequence med, needs a runtime check)
- Tooltip text: the control's tooltip strref (+0x24, 0 = none, via TLK) or string (+0x28); if
  both are empty the parent's tooltip is used, and a control with no parent has none. If the
  control names a key-map action (+0x30) that is bound in the current input class, the key's
  name is appended as `" : " + name` (the name's strref is `KeyNameStrRef` from
  `bindablekeys.2da` at row key index − 6: key index 6, Return, is row 0 `KEYBOARD_RETURN`).
  `ShowTooltip` (0x0040b490, ignored while the press lock is set or tooltips are off) puts the
  text into the tooltip label and sets the manager's "tooltip showing" flag (+0x1c bit 3) so
  `Render` draws the tooltip panel. `PlaceAtCursor` (0x00624af0) sizes it once, to the text's
  width and height plus 8 pixels, at the cursor plus 15 pixels; if that crosses the right or
  bottom edge it is moved to end 2 pixels inside the screen (§10.3). (high)
- Hiding: moving to another control, pressing a button, the wheel, or removing the panel.

### The software cursor

The cursor is not the Windows cursor (`EnableHardwareMouse` aside, app.md): the manager builds a
small GUI 3D scene with the model `gui_mouse` (`CreateCursorModel` 0x0040b060) and draws it last
each frame, positioned at the cursor in units of 0.01 per pixel with y flipped. The cursor image
is a texture swapped onto that model (`SetMouseCursor` 0x0040a270): cursor *n* uses the name at
index *n* of the table at 0x0078d240, and the pressed look (left button down, set by the client's
mouse handlers) uses index *n* + 1 when *n* is odd. The model animation `center` or `default`
chooses between a centred and a top-left hot spot; every caller passes "not centred", so the
`default` pose is the one used (med). (high)

The only ids the game sets are 1 (default), 5 (no action), 7, 11, 23, 25, 33, 37 and 51 (the
target's default action, `GetCursorForAction` 0x0061faa0) and 45 (another selectable object),
all from `SetHoverObject` 0x006222f0 (movement.md 7.2); the other rows below are never chosen.

| Ids | Textures | Use (from the names) |
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
| 47–50 | `gui_mp_createu/d`, `nocreatu/d` | create |
| 51–54 | `gui_mp_killu/d`, `nokillu/d` | attack / cannot |
| 55–58 | `gui_mp_healu/d`, `noheal..` | heal / cannot |
| 59/60 | `gui_mp_pickupu/d` | pick up |
| 61–76 | `gui_mp_arrun00..15` | run, 16 directions |
| 77–92 | `gui_mp_arwalk00..15` | walk, 16 directions |

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
`maininterface`, `mi8x6`, `mipc8x6`, `mipc10x7`, `mipc12x9`, `mipc16x12`, `mainmenu8x6` ..
`mainmenu16x12` and `optkeyentry` are not named by any code (Xbox and older layouts; no code
appends a resolution suffix to a `.gui` name) (high).

### 10.1 Front end

#### Loading screen (`CSWGuiLoadScreen`, `loadscreen`)

Constructor 0x0067a710, vtable 0x00752dc0, 0x6b8 bytes, owned by the client (+0x278; created by
`PostInitialize`, `ChangeVideoMode` or `ShowLoadScreen`). Flags 0x60 (centred 640x480 frame).
(high)

| Tag | Role |
|---|---|
| (root `BORDER` fill) | the picture for the area being loaded; replaced at run time (`SetImage` 0x0067a6d0: only if a TGA or TPC of that name exists) |
| `PB_PROGRESS` | load progress 0–100 |
| `LBL_HINT` | hint text (strref, TLK tokens parsed) |
| `LBL_LOGO` | logo (from the file) |
| `LBL_LOADING` | "Loading" (strref 42493) or "Saving" (42528) |
| (code label +0x578) | full-screen backdrop `WxHload` (e.g. `1024x768load`, from the screen size at construction), sized to the GUI manager's screen and drawn in a full-screen viewport before the panel (`Render` 0x0067ab00) |

- **Picture** (`SetLoadScreenImage` 0x005f3480, client +0x2fc; only caller 0x005edcf0,
  gameloop.md 5.6): `loadscreens.2da` column `BMPResRef` by row label (`classsel` for character
  generation, area/module rows such as `manm26mg`); when the row is missing it uses `load_<name>`
  if that exists as a TGA or TPC, else row `DEFAULT` (`LOAD_DEFAULT`). An empty name clears the
  picture. A picture that differs from the current one is stored and sets the "picture chosen"
  flag (client +0x30c, never cleared), which `ShowLoadScreen` requires. (high)
- **Showing** (`ShowLoadScreen` 0x005f6c60, arguments (fade, music, save); callers 0x005eda80 and
  `PlayQueuedMovies` 0x00602650): first sets the sound mode, 3 for a save, and for a load 4 when
  a load music name is set (client +0x304), else none. Then, only once a picture has been chosen
  (+0x30c) and its name is not empty: creates the panel if needed, applies the picture and the
  Loading/Saving text; if the panel is not up yet it stores the tick count for the hint timer
  (+0x48c), starts a black global fade with zero times (`CGuiInGame::StartGlobalFade`) when the
  fade argument is set and the in-game GUI exists, and adds the panel modal (`AddPanel(…, 1, 1)`,
  not full screen). Last it unacquires input, releases held movement keys (0x005f2980,
  movement.md), sets input-block bit 2 (client +0x3d8, 0x0061f9c0; the input class is not
  changed; the bit is cleared when the load screen goes, gameloop.md 5.5 step 12) and, with the
  music argument, starts the +0x304 music as a looping stream (0x005f6480). (med)
- **Progress** (`SetLoadProgress` 0x005fb3f0, called through 0x005edd40): sets `PB_PROGRESS` to
  0..100; when its second argument is set and the value is below 80 it first runs the hint timer
  (below). The loading code computes the value from per-phase byte weights kept at client +0x3e4
  (`GetLoadPhaseWeight` 0x005edff0, phases 0–3), adding a fraction of the current phase as work
  completes (e.g. `CGuiInGame::CreatePanels` advances phase 3 in steps between panels); after
  each step the caller runs `RenderLoadingFrame` (0x00401c10), which draws a GUI-only frame.
  Phase bookkeeping belongs to gameloop.md. (med)
- **Hints** (`PickLoadScreenHint` 0x005f4760): `loadscreenhints.2da` (columns `GamePlayHint`,
  `StoryHint`, 91 rows; the story column is filled only in rows 0–36) is read round-robin with one
  byte counter per column (client +0x490 gameplay, +0x491 story), wrapping to row 0 when a read
  fails (past the last row, or at an empty cell: so 91 gameplay hints and 37 story hints). The
  kind is chosen by the caller (1 gameplay, 2 story; otherwise, while a server exists, asked from
  it through 0x004aebe0: non-zero story, zero gameplay). `UpdateLoadScreenHint` (0x005f7b20,
  only from `SetLoadProgress`, so only while progress is below 80 and the caller asked for it)
  runs while a server exists and a hint is showing (panel +0x574 non-zero): it adds the
  `GetTickCount` delta since +0x48c to +0x488 and at ≥ 10,000 ms resets it and shows the next
  story hint (`SetHint` 0x0067a9c0). (high)


#### Main menu (`CSWGuiMainMenu`, `mainmenu`)

Constructor 0x0067c4c0 (0x1414 bytes), `InitPanel` 0x0067ace0 (also re-run on a resolution
change by `ChangeVideoMode`), vtable 0x00752f70; created and added by
`CClientExoAppInternal::ShowMainMenu` (0x005fca30, held at client +0x280; does nothing while that
menu is still up), which sets input class 2, adds it with `AddPanel(…, 2, 1)` (full screen, not
modal) and starts the menu music (`mus_theme_cult`, 0x005f9af0). The game reads `mainmenu` from
`patch.erf` (800x600 layout); `mainmenu8x6/10x7/12x9/16x12` are never loaded. (high)

| Tag | Role |
|---|---|
| `LB_MODULES` | debug warp list (hidden by the constructor; only the warp shows it) |
| `LBL_3DVIEW` | the animated 3D background: a GUI 3D scene with the model `mainmenu` from `RIMS:MAINMENU` (the constructor mounts the RIM when a `MAINMENU` resource of type RIM (3002) exists, and clears the "unmount" bit 0x2 of resman +0x34; the manager unmounts it once the menu goes); the scene is built only while the GUI-3D global 0x0078d1e4 is set (gui3d.md) |
| `LBL_GAMELOGO`, `LBL_MENUBG`, `LBL_BW`, `LBL_LUCAS` | art (`LBL_BW`/`LBL_LUCAS` unbound) |
| `LBL_NEWCONTENT` | "New downloadable content is available" (42407, the text in the `.gui`); bound but hidden by the constructor, and no code shows it (high) |
| `BTN_NEWGAME` | → `OnNewGame` 0x0067afb0 |
| `BTN_LOADGAME` | → `OnLoadGame` 0x0067b1a0 |
| `BTN_MOVIES` | → `OnMovies` 0x0067b250 |
| `BTN_OPTIONS` | → `OnOptions` 0x0067b2f0 |
| `BTN_EXIT` | → `OnExit` 0x0067b4a0 |
| `BTN_WARP` | → 0x0067c4b0 → 0x0067c3f0 (debug warp; hidden by the constructor): fills `LB_MODULES` once (0x0067bc40), shows it, hides the other controls and sets the mode +0x350 = 2; back (0x28/0x2e) in that mode restores them (`BTN_WARP` included, which then stays visible) and returns to mode 1 |

- Each button handles 0x27 and 0x2d with the same callback; events 0 / 1 recolour the button
  text to yellow / blue (0x0067b450 / 0x0067b470). `HandleInputEvent` (0x0067b380) plays the
  click (GUI sound 0) for 0x2d before passing it on. The constructor makes `BTN_NEWGAME` the
  active control. (high)
- **Guards**: new game, load, movies and options do nothing until the menu is ready (`Render`
  0x0067ac10 counts draws at +0x1410 and sets +0x140c from the sixth draw on), while the menu is
  already marked for deletion, or for the release half of a click (the event value must be
  non-zero). Exit checks only the ready flag (and in warp mode sends the panel a back event 0x2e
  instead of quitting); the warp checks the ready flag and the deletion mark. (high)
- **New game**: resets the session clock (0x00563cf0), mounts `MODULES:` for the check, looks
  for the start module `END_M01AA` (the Endar Spire) as a `.mod` and then as a `.rim` (the name
  stays `END_M01AA` either way), unmounts `MODULES:`, builds `CSWGuiClassSelection` (0x1560
  bytes) with that module name, adds it full screen, not modal (`AddPanel(…, 2, 1)`), sets the
  sound mode to 0 (pops the mode stack) and marks the main menu for deletion (flag bits 9..10 =
  2, 0x400). (high)
- **Load game**: `CSWGuiSaveLoad` in load mode, opened from the main menu (see "Save and load" below), added
  full screen, not modal (`AddPanel(…, 2, 1)`); the main menu is deleted unless the save panel itself was already closing. (high)
- **Movies** / **Options**: `CSWGuiTitleMovies` / `CSWGuiOptionsMain`, `AddPanel(…, 3, 1)`
  (modal and full screen); the main menu stays underneath (hidden by the full-screen panel).
  Before opening the movies the menu music is faded out and paused (0x005ee120 → 0x005f4a60,
  which runs sound updates in a blocking loop for 750 ms). (high)
- **Exit**: `PostQuitMessage(0)` (0x005ed450 → 0x005eea10). (high)
- **On being added** (0x0067b6c0): reads the free space on `SAVES:` in units of 16 KiB and tries
  to create the autosave directory `SAVES:000001 - AUTOSAVE`; if that succeeds (no autosave yet)
  it removes it again and needs 4800 + 2 units (about 75 MiB), else 3200 + 2 (about 50 MiB).
  With enough space it clears all input-block bits (0x005ee180 with 0xffff); otherwise it shows
  the in-game GUI's message box (OK only) with strref 47992 ("... You need to free <CUSTOM0>
  MB", the shortfall in decimal MB, `%2.3f`, in token 0) whose OK quits the game (0x0067b490).
  (med)
- The constructor also removes `HD0:GAMEINPROGRESS` and `HD0:CURRENTGAME` and empties the
  `GAMEINPROGRESS:`, `CURRENTGAME:` and `REBOOTDATA:` directories (save-game scratch;
  party-items-saves.md), and sets the sound mode to 0. (high)


#### Save and load (`CSWGuiSaveLoad`, `saveload`; `CSWGuiSaveName`, `savename`)

`CSWGuiSaveLoad` constructor 0x006cc680 (0x1160 bytes, vtable 0x00757650), arguments
`(manager, saveMode, fromMainMenu)` (kept as bits 0 and 1 of +0x64). (high)

| Tag | Role |
|---|---|
| `LBL_PANELNAME` | "Load Game" (1585) or "Save Game" (1588) |
| `LB_GAMES` | the saves; rows use the menu blue/yellow text colours and a pulsing hilight; the active control |
| `LBL_SCREENSHOT`, `LBL_PLANETNAME`, `LBL_AREANAME`, `LBL_PM1..3` | details of the hilighted save (screenshot, planet, area, party members; 0x006c89d0) |
| `BTN_SAVELOAD` | "Load" (1589) or "Save" (1587): `OnLoad` 0x006cc0e0 or `OnSave` 0x006cbb60 on 0x27 (the `OnButtonAccept` registered first is replaced: a control keeps one handler per event, `SetEventHandler` 0x0041ab20) |
| `BTN_DELETE` | `OnDelete` 0x006caa90 on 0x27 (replaces the `OnButtonX` registered first) |
| `BTN_BACK` | `OnButtonCancel` |

`HandleInputEvent` (0x006c86d0): back (0x28, 0x2d, 0x2e) plays the click and marks the panel for
deletion; opened from the main menu it re-shows the main menu, otherwise it pops the modal
panel. The list is filled by 0x006cc160: one row per directory in `SAVES:`, each row taking 0x27
→ `OnLoad`/`OnSave`, 0x29 → `OnDelete` and 0 → the details (shown at once for the first row). In
save mode rows numbered 0 and 1 are left out and a "New Slot" row (1590) goes first, numbered one
above the highest save (at least 2). In load mode with no saves the panel closes the same way as
back and the message box says 42491 ("You have no Saved Games."). `TEMP:` is created (emptied if
it already exists) and mounted for the screenshots.

- **Load**: opened from the main menu, `OnLoad` loads at once (`LoadSelectedGame` 0x006cb0e0);
  in game it first asks 32155 ("The current game will not be saved. Continue with load?").
- **Save**: a new slot needs 1600 units of 16 KiB free on `SAVES:` (25 MiB; 2 more when
  `OPTIONS:OPT` is missing or empty), else the message box shows 47989 with the shortfall in MB;
  overwriting a save asks 1591 first (its space test only fails on a 32-bit overflow, so in
  practice there is none). Then 0x006cb820 opens `CSWGuiSaveName` (modal), pre-filled with the
  old name when overwriting.
- **Delete**: asks 1592, then 0x006c8900.

`CSWGuiSaveName` (constructor 0x006cae70, 0x690 bytes, vtable 0x007576d0: `EDITBOX`,
`LBL_TITLE`, `BTN_OK` → 0x006c9d50, `BTN_CANCEL` → 0x006c8470; centred dialog). What saving and
loading do: party-items-saves.md. (high for the panel, med for the callbacks' roles)


#### Movies (`CSWGuiTitleMovies`, `titlemovie`) — skimmed

Constructor 0x006dd910 (0x654 bytes, vtable 0x00758130): `LBL_TITLE`, `LB_MOVIES` (active),
`BTN_BACK` (→ `OnButtonCancel`). The list (0x006dd100) starts with a "Credits" row (47918), which
opens the credits panel (0x005ee1c0 with `credits`). Then comes one row per `.bik` file found in
`MOVIES:` and in `liveN:movies` for each defined `LIVE1`..`LIVE6` alias, labelled by `movies.2da`
`StrrefName` (the file name when 0) and listed when `AlwaysShow` is 1 or the client options
record the movie as seen (0x0061d3d0); rows are kept sorted by `Order`. Activating a row (0x27 or
0x2d, 0x006dcf10) plays that movie (0x005edb30). Back (0x28/0x2e, `HandleInputEvent` 0x006dce80)
restarts the menu music (0x005ed9e0 sets the restart flag client +0x1ec, 0x005ed9b0 plays
`mus_theme_cult`), plays the click, pops and deletes the panel; 0x2d only plays the click. (med)


#### Credits (`CSWGuiCredits`, `credits`) — skimmed

Constructor 0x0068f8d0 (0x5f8 bytes, vtable 0x007541f0), created once by 0x005f4c60 with a
music name and added `AddPanel(…, 3, 1)`, or modal only (1) in end-credits mode (client +0x4bc,
app.md). The text is `credits.2da` column `Name` (one strref per row), shown in a label with the
`fnt_credits` font that is the single item of `LB_CREDITS`. Every row but the last is a page that
fades in over 1 s, holds 2 s, fades out over 1 s and is followed by 1 s of nothing (0x0068f790);
the last row is padded with blank lines and scrolled through the list one line at a time
(0x0068f630); once the end is reached and the music has stopped, the panel deletes itself.
`Render` (0x0068f880) does neither while the game is paused (pause state 2). On being added
(0x0068f260) it sets input-block bit 0x80, saves the input class, switches to class 2 and plays
the music as a streamed sound; 0x27, 0x28, 0x2d or 0x2e close it (0x0068f350). In end-credits
mode the constructor saves the GUI and screen size and switches the GUI to 640x480; the
destructor (0x0068f0e0) then restores both (`SetResolution` with the saved size), clears the
mode (0x005f4e50) and calls `LeaveMovieVideoMode`. The destructor always frees the music stream,
restores the input class and clears input-block bit 0x80. (med)


#### Options

The options panels opened from the main menu, from the in-game options and from each other are
modal full-screen menus (`AddPanel(…, 3, 1)`); the resolution list is a modal centred dialog
(`AddPanel(…, 1, 1)`), and the in-game options panel is an in-game menu page. Most have
`LBL_TITLE`, a `LB_DESC` description list that shows the hovered control's description (each
control keeps a description strref at +0x58, and its event 0 handler writes it to the list),
`BTN_BACK` (→ `OnButtonCancel`) and, where present, `BTN_DEFAULT`; auto-pause has `LB_DETAILS`
instead of `LB_DESC`, the resolution list and key mapping have neither (they close with
`BTN_CANCEL`/`BTN_Cancel` → `OnButtonCancel`), and the in-game options close with `BTN_EXIT`.
Values are kept in the client options block and written to `swkotor.ini` by 0x0061b780 (read at
start-up by 0x0061dbe0, which first applies the defaults 0x0061da60; app.md). (high for the
structure; per-option mapping skimmed)

| Panel | Ctor / vtable | `.gui` | Controls (tag → handler) |
|---|---|---|---|
| Options (main menu) | 0x006e3e80 / 0x00758838 | `optionsmain` | `BTN_GAMEPLAY` 0x006de240, `BTN_FEEDBACK` 0x006e2df0, `BTN_AUTOPAUSE` 0x006de2c0, `BTN_GRAPHICS` 0x006e3d80, `BTN_SOUND` 0x006e3e00 (each opens the sub-panel) |
| Options (in game) | 0x006ab2f0 / 0x00755de0 | `optionsingame` | `BTN_LOADGAME` 0x006aaaf0 / `BTN_SAVEGAME` 0x006aab80 (write the ini, 0x005edf70, then open `CSWGuiSaveLoad` in load / save mode, `AddPanel(…, 3, 1)`), `BTN_GAMEPLAY` 0x006aac10, `BTN_FEEDBACK` 0x006aac90, `BTN_AUTOPAUSE` 0x006aad10, `BTN_GRAPHICS` 0x006aad90, `BTN_SOUND` 0x006aae10, `BTN_QUIT` 0x006ab1b0 (writes the ini, then asks 42348 "Do you really want to quit?"), `BTN_EXIT` → `OnButtonCancel`; held at `CGuiInGame` +0x28 |
| Graphics | 0x006e2e70 / 0x007586f8 | `optgraphics` | `SLI_GAMMA`/`LBL_GAMMA` (left/right/up/down/accept 0x006ded30), `BTN_RESOLUTION` → resolution list 0x006e1660 (`BTN_RESOLUTIONLEFT`/`RIGHT` are bound but get no handler), `CB_SHADOWS` 0x006dedb0, `CB_GRASS` 0x006dee00, `BTN_ADVANCED` 0x006e2cf0, `BTN_DEFAULT` 0x006e0190 |
| Advanced graphics | 0x006e16e0 / 0x007584a0 | `optgraphicsadv` | `BTN_ANTIALIAS` (+ `LEFT`/`RIGHT` 0x006e0520/0x006e05e0), `BTN_TEXQUAL` (0x006e04a0/0x006e04e0), `BTN_ANISOTROPY` (0x006e0680/0x006e06d0), `CB_FRAMEBUFF` 0x006ddb10, `CB_SOFTSHADOWS` 0x006ddb30, `CB_VSYNC` 0x006ddb60, `BTN_DEFAULT` 0x006e0470, `BTN_CANCEL` 0x006ddb80 |
| Resolution | 0x006e0710 / 0x00758348 | `optresolution` | `LB_RESOLUTIONS` (rows `%d x %d` / `%d x %d @ %d Hz`), `BTN_OK` and row activation → 0x006df690 (applies the row's display-mode number through `ChangeVideoMode`, §2, and on success writes `Width`, `Height`, `RefreshRate` under `[Graphics Options]`), `BTN_CANCEL`; centred dialog |
| Sound | 0x006e3550 / 0x007587c0 | `optsound` | `SLI_MUSIC`, `SLI_VO`, `SLI_FX`, `SLI_MOVIE` (+ labels; change 0x006df9b0), `BTN_ADVANCED` 0x006e2d70, `BTN_DEFAULT` 0x006e0f50 |
| Advanced sound | 0x006e20a0 / 0x00758550 | `optsoundadv` | `BTN_EAX` (+ `LEFT`/`RIGHT`), `CB_FORCESOFTWARE`, `BTN_DEFAULT` 0x006e1270, `BTN_CANCEL` 0x006ddff0 |
| Mouse | 0x006e2600 / 0x007585f8 | `optmouse` | `SLI_MOUSESEN`, `CB_REVBUTTONS`, `BTN_DEFAULT` 0x006e12b0 |
| Feedback | 0x006e2a70 / 0x007581e8 | `optfeedback` | `LB_OPTIONS` of check-box rows built by 0x006e1300 (one toggle handler per row, 0x006de550..0x006de780), `BTN_DEFAULT` 0x006e0100 (resets the feedback options, 0x0061d950, and refreshes the rows) |
| Gameplay | 0x006e69a0 / 0x00758e00 | `optgameplay` | difficulty (`BTN_DIFFICULTY` with left/right 0x2f/0x30, `BTN_DIFFLEFT`/`RIGHT`: 0x006e68e0/0x006e6930), `CB_LEVELUP` 0x006e62a0, `CB_INVERTCAM` 0x006e6330, `CB_AUTOSAVE` 0x006e62e0, `CB_REVERSE` 0x006e6380, `CB_DISABLEMOVE` 0x006e63d0, `SLI_MOUSESEN`/`LBL_MOUSESEN` (no handler set here), `BTN_KEYMAP` 0x006e6420, `BTN_MOUSE` 0x006e64a0 (both `AddPanel(…, 3, 1)`), `BTN_DEFAULT` 0x006e68b0 |
| Auto-pause | 0x006e76a0 / 0x00758ee0 | `optautopause` | `CB_ENDROUND`, `CB_ENEMYSIGHTED`, `CB_MINESIGHTED`, `CB_PARTYKILLED`, `CB_ACTIONMENU`, `CB_TRIGGERS`, `LB_DETAILS`, `BTN_DEFAULT` 0x006e7570 |
| Key mapping | 0x006edc90 / 0x00759358 | `OPTKeyMapping` (`optkeyentry.gui` is never loaded) | `LST_EventList`, `BTN_Filter_Move/Game/Mini` (0x006ed390/0x006ed3e0/0x006ed430), `BTN_Default` 0x006ed2d0, `BTN_Accept` 0x006ed310, `BTN_Cancel` |


### 10.2 Character generation and level-up

#### Character generation

The flow (high for the wiring; the screen-by-screen detail is [chargen.md](chargen.md), the rules
— point-buy, skill points, feat and power choice — are in rules.md):

1. **Main menu → class selection.** `OnNewGame` builds `CSWGuiClassSelection` (0x006dc3c0,
   0x1560 bytes, vtable 0x00758020, `classsel`) with the start module name. The constructor sets
   the load-screen picture to the `loadscreens.2da` row `classsel` (`LOAD_CHARGEN`) and shows the
   loading screen, mounts `RIMS:CHARGEN` when a resource `CHARGEN` of type 0xbba (the RIM) exists,
   reads `portraits.2da` (rows with `ForPC` non-zero, split by `Sex`), and builds six class/gender
   slots, each with its own creature (chargen.md A).
2. **Class selection** (`classsel`): `BTN_SEL1..6` each with a `3D_MODEL1..6` child label that
   shows a GUI 3D scene of the slot's creature (room `gui3D_room`, light `cgbody_light`; a random
   `portraits.2da` row of the slot's gender, and its `Appearance_L` / `AppearanceNumber` /
   `Appearance_S` column for Soldier / Scout / Scoundrel); `LBL_CHAR_GEN`, `LBL_INSTRUCTION`,
   `LBL_CLASS`, `LBL_DESC`, `BTN_BACK`. The six slots, from a static table at 0x007a2684
   (8 bytes each: class, gender, soundset row, pad, description strref): male Scoundrel (32109),
   male Scout (32110), male Soldier (32111), female Soldier, female Scout, female Scoundrel. Hover
   (`OnHoverClass` 0x006dba70) writes "Male"/"Female" (646/647) + class name (Scout 133, Soldier
   134, Scoundrel 135) into `LBL_CLASS` and the description into `LBL_DESC`. Clicking
   (`OnSelectClass` 0x006db9b0, 0x27 and 0x2d) stores the slot's creature at panel `+0x68` and
   opens the character generation main panel with `AddPanel(3,1)`: full screen and modal.
3. **Main panel** (`CSWGuiCharGenMain` 0x006eb420, 0x22dc bytes, vtable 0x007592a8, `maincg`):
   the running summary — `MODEL_LBL` (3D model), `PORTRAIT_LBL`, `LBL_NAME`, `LBL_CLASS`, the six
   ability labels `STR_LBL`..`CHA_LBL` with `STR_AB_LBL`..`CHA_AB_LBL` (the chosen base score as a
   plain number, not the modifier), `LBL_VIT`, `LBL_DEF`, saves `LBL_FORTITUDE`/`LBL_REFLEX`/
   `LBL_WILL` with `NEW_FORT_LBL`/`NEW_REFL_LBL`/`NEW_WILL_LBL`, bevel decorations (chargen.md B).
   It owns three step panels and shows exactly one at a time as a modal panel
   (`ShowStepPanel` 0x006ea760: 1 = quick-or-custom, 2 = quick steps, 3 = custom steps).
4. **Quick or custom** (0x006f09f0, vtable 0x00759710, `qorcpnl`): `QUICK_CHAR_BTN`
   → 0x006f0800 (quick) and `CUST_CHAR_BTN` → 0x006f0830 (custom) (hover 0x006f09d0 / 0x006f09e0
   fills `LB_DESC`; quick is the initial active control),
   `BTN_BACK`. Flags 0x60.
5. **Quick steps** (0x006f0390, vtable 0x00759668, `quickpnl`): three step buttons
   (`BTN_STEPNAME1..3` with `LBL_NUM1..3`, `LBL_1..3`): portrait 0x006efe10, name 0x006efd80,
   play 0x006efd60 (runs `Finish` only when the step counter +0x135c is at least 2); only the
   current step's button is enabled (chargen.md C.2); `BTN_BACK`, `BTN_CANCEL` 0x006f0310 (asks
   "Are you sure you want to cancel?", 48541, when steps were done). When the panel is added
   (0x006f0260) it builds the character at once (0x006effd0: the class's `classes.2da` abilities,
   the granted and recommended feats, skill points and recommended ranks; chargen.md C.4) and
   refreshes the summary. (high)
6. **Custom steps** (0x006ef730, vtable 0x007595e0, `custpnl`): six step buttons — portrait
   0x006ef120, abilities 0x006ef3f0, skills 0x006ef360, feats 0x006ef2d0, name 0x006ef240, play
   0x006ef220 (runs `Finish` only after step 5, +0x2184 > 4); `BTN_BACK`, `BTN_CANCEL` 0x006ef6a0.
   Only the current step's button is enabled (`0x006eefd0`), so the steps go in order and a
   finished one is revisited only with Back.
7. **Step panels**, each a full-screen 640x480 menu added with `AddPanel(3,1)` (full screen,
   modal; no 0x60 flags of their own), sharing layout conventions (`MAIN_TITLE_LBL`,
   `SUB_TITLE_LBL`; the list steps add `LB_DESC` for the hovered item's description,
   `REMAINING_SELECTIONS_LBL`, `BTN_ACCEPT`, `BTN_BACK`, `BTN_RECOMMENDED`):
   - **Portrait** (0x006f9430, vtable 0x00759ea8, `portcust`): `LBL_PORTRAIT`, `LBL_HEAD` (3D head,
     light `cghead_light`, camera hook `camerahook%c`), `BTN_ARRL`/`BTN_ARRR` (previous/next,
     via the 0x2f/0x30 thunks), accept/back.
   - **Name** (0x006f9e70, vtable 0x00759f38, `name`): `NAME_BOX_EDIT` (edit box; Enter accepts),
     `BTN_RANDOM` (`OnButtonY` → random name from the LTR name tables, chargen.md E),
     `END_BTN`/accept 0x006f9cd0, `BTN_BACK`.
   - **Abilities** (0x006f7600, vtable 0x00759c68, `abchrgen`): per ability `*_LBL`,
     `*_POINTS_BTN`, `*_PLUS_BTN`, `*_MINUS_BTN`; `COST_POINTS_LBL`, `LBL_ABILITY_MOD`,
     `LBL_MODIFIER`. `HandleInputEvent` 0x006f8880: 0x27/0x2d accept, 0x28/0x2e back, 0x2a
     recommended (if points remain), 0x2f/0x3f decrease and 0x30/0x40 increase the focused
     ability, 0x39/0x3a scroll `LB_DESC` (sent on to it as 0x31/0x32). In character generation each
     score is 8..18 and raising a score `v` costs 1 point below 14, 2 from 14 to 15, 3 from 16
     (`GetIncreaseCost` 0x006f6bb0, used by 0x006f8670); raising past 18 while points remain shows
     42181 (with no points left the press is silent), lowering below 8 shows 42180. At level-up
     (+0x3df0 set) the cost is 1, there is no 18 cap, and the floor is the score the panel opened
     with (0x006f8480). (high)
   - **Skills** (0x006f51d0, vtable 0x00759990, `skchrgen`): the eight skills (`COMPUTER_USE`,
     `DEMOLITIONS`, `STEALTH`, `AWARENESS`, `PERSUADE`, `REPAIR`, `SECURITY`, `TREAT_INJURY`, each
     `*_LBL`, `*_POINTS_BTN`, `XXX_PLUS_BTN`, `XXX_MINUS_BTN`), `CLASSSKL_LBL`, `COST_POINTS_LBL`;
     `HandleInputEvent` 0x006f6a10. Behaviour in chargen.md G. (high)
   - **Feats** (0x006f3d60, vtable 0x007598b0, `ftchrgen`): `LB_FEATS` (row clicked 0x1f8 →
     0x006f3420, double-click 0x1f9 → 0x006f3cf0), `BTN_SELECT` (accept thunk), `BTN_ACCEPT`
     (`OnButtonX`), `BTN_RECOMMENDED`, `LBL_NAME`; `HandleInputEvent` 0x006f4680. `LB_FEATS` holds
     chain rows of icon cells ("Chain rows" under the in-game panels), not the file's prototype.
     Behaviour in chargen.md H. (high)
   - **Force powers** (0x006f2180, vtable 0x00759780, `pwrlvlup`): `LB_POWERS`, `LBL_POWER`,
     `SELECT_BTN` (`OnButtonX`), `ACCEPT_BTN` (accept), `RECOMMENDED_BTN` (`OnButtonY`),
     `BACK_BTN`; `HandleInputEvent` 0x006f28c0. Used by level-up only: its one caller is
     `CSWGuiLevelUpPanel::OnPowers` 0x006ee350. `LB_POWERS` holds chain rows of icon cells, like
     `LB_FEATS`. Behaviour in chargen.md I. (high)
8. **Play** (`Finish` 0x006eb320 → `CSWGuiCharGenMain::Close` 0x006ea830, then
   `CSWGuiClassSelection::StartGame` 0x006dbdf0): `Close` pops the modal, marks each step panel
   that is in the manager for deletion (deleting the others at once) and marks itself;
   `StartGame` stops the menu music, creates the server (`CAppManager::CreateServer`), writes the
   finished creature as a BIC-style GFF `TEMP:temp` (0x006123e0), joins the local server, sends it
   the admin text `Module.Load` with the module named at step 1 (`END_M01AA`), sets the player
   file name `temp`, marks the class selection for deletion, sets the load-screen picture for the
   module, picks a hint and shows the loading screen (chargen.md C.5, chargen-creature.md 2).
   (high for the order, med for the message details)

**Level-up** reuses the steps: the character sheet's `BTN_LEVELUP` (accept, 0x27, handled in the
sheet's input handler) calls `CSWGuiCharacter::StartLevelUp` (0x006b0bb0), which opens
`CSWGuiLevelUpMain` (0x006e8ef0, 0x2560 bytes, vtable 0x00758f50, `maincg` again, binding the same
tags as character generation plus `LBL_LEVEL` and `LBL_LEVEL_VAL`; the file's `OLD_*` labels and
arrows are never created, chargen.md B) with `AddPanel(3,1)`. It owns
`CSWGuiLevelUpPanel` (0x006ee7d0, 0x1cec bytes, vtable 0x00759568, `leveluppnl`, flags 0x60): step
buttons abilities 0x006ee500, skills 0x006ee480, feats 0x006ee3d0, powers 0x006ee350, finish
0x006ee780; `BTN_BACK`, `BTN_CANCEL` 0x006ee5f0. A step's button gets its handler only when the
level offers it: abilities when the creature's total level (`0x00648430`) is a multiple of 4,
skills when the level's skill points (`0x00648a00`) are above 0, feats when the class's
`featgain` counts for the level are above 0 (otherwise the level's granted feats are added at
once and shown in the popup 42258), powers when `0x00649070` is non-zero (rules.md); finish
always (high for the tests, med for which level the total-level test sees). The step panels are
the same classes in level-up mode (constructor flag; +0x3df0 in the abilities panel).
`ShowLevelUpGUI` (script routine, 0x00543870) opens it from scripts through `0x0062dc00`, which
pauses the game if it is running, makes the character sheet if there is none and calls
`StartLevelUp`. (med)


### 10.3 The in-game GUI: CGuiInGame, HUD and overlays

#### CGuiInGame: the owner of the in-game panels

`CGuiInGame` (our name) is the 0xc24-byte object at `CClientExoAppInternal`+0x40 that owns every
in-game panel, decides which of them are up, and is the single entry point the rest of the client
uses to open menus, show message boxes, fade the screen and drive the HUD. Its constructor
(`0x0062fed0`, called from `CClientExoAppInternal::Initialize` `0x005f8550`) creates no panel; the
panels are made in two steps. (high unless noted)

| Address | Name (ours) | What | Conf. |
|---|---|---|---|
| `0x0062fed0` | `CGuiInGame::CGuiInGame` | zeroes the panel pointers and state (a few fields start at 1 or `OBJECT_INVALID`); `+0x164` = 10098; allocates two 64-entry tables (`+0xf8`, `+0xfc`); and sets the client options' camera mode to 3 (`CClientOptions::SetCameraMode` `0x0061b6f0`) | high |
| `0x00632720` | `CGuiInGame::CreateEarlyPanels` | called from `CClientExoAppInternal::PostInitialize` (`0x005f51c0`): makes the panels needed before any module is loaded, so they also serve the main menu: message box `+0x98`, skill info `+0x9c`, tutorial box `+0xa0`, controller box `+0xa4` | high |
| `0x00632860` | `CGuiInGame::CreatePanels` | first module load (reached from `CSWCMessage::HandleServerToPlayerModule` through `0x005ed730` → `0x005f1410`; does nothing once `+0x108` is set): makes all the rest (and the four early panels if any is missing), calling `RenderLoadingFrame` between groups so the load bar moves; sets `+0x108` = 1 (panels exist) and `+0x3c` = `+0x40` | high |
| `0x0062f5f0` | `CGuiInGame::RecreateResolutionPanels` | resolution change (`CClientExoAppInternal::ChangeVideoMode` `0x005f1830`): deletes and rebuilds the HUD, the letterbox dialogue panel and the message box (their `.gui` depends on the resolution), re-centres the debug panels, container, skill info and tutorial box | high |
| `0x0062b490` | `CGuiInGame::OnResolutionChanged` | calls the OnResize slot (+0x68) of the HUD and of the 8 menu panels; called by `CSWGuiManager::OnResolutionChanged` | high |

A build switch at `0x007a2370` (initialised to 1, never written) chooses between creating every
menu panel up front (1, the shipped behaviour) and creating each menu panel only when it is
opened and deleting it when another replaces it (0; `CGuiInGame::SwapMenuPanel` `0x0062b1e0`);
with 0, `CreatePanels` also skips the computer, party-selection, store and galaxy-map panels.
An implementer can create everything up front. (high)

**Field map** (offsets in `CGuiInGame`; ctor addresses are the panel constructors):

| Offset | Panel | `.gui` | Ctor | Conf. |
|---|---|---|---|---|
| `+0x08` | top menu bar | `top` | `0x00627980` | high |
| `+0x0c`..`+0x28` | the 8 menu panels, indexed by the menu number below: equipment `0x006ba980`, inventory `0x006b34c0`, character `0x006b0e40`, abilities `0x006adda0`, messages `0x00626400`, journal `0x00644a40`, map `0x00694d50`, in-game options `0x006ab2f0` | `equip` ... `optionsingame` | | high |
| `+0x2c` | current menu number (0..7) | | | high |
| `+0x30` | a menu is open | | | high |
| `+0x34` | HUD mode: 1 game (HUD shown); 2 minigame (`SetInputClass(1)` `0x006200e0`) or back at the main menu after a party wipe; 3 menu, conversation, store or galaxy map (2 and 3 hide the HUD) | | | high |
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
   muffled world), clear the HUD's target (`0x005edb70` → `0x005f2c60` → `SetHudTarget(OBJECT_INVALID)`),
   switch the HUD to mode 3 (hides it).
2. Run the script `k_sup_guiopen` (object id 0; `k_pend_screenchg` below gets `OBJECT_INVALID`).
3. Choose the menu: n if 0..7; otherwise keep the last one, except that when the party leader has
   a level-up pending (`0x005a6810`) the character sheet (2) is chosen.
4. Add the top bar (flags 0) and the menu panel with flags 2 (full-screen: centred, with the
   resolution backdrop), bring the menu to the front, select the matching tab in the top bar.
5. `+0x30` = 1. If the game was not already paused by the player (`+0xb38` = 0), toggle the
   server's pause bit 2 (`0x00677800` → `0x004ba610`): **menus pause the game**.
6. Hide the bark bubble (pauses its voice) and run `k_pend_screenchg`; play GUI sound 4.

It returns `+0x30`. The caller then switches the client input class to 2 (GUI): the HUD button
(`OnMenuButton` `0x006883c0`) through `SetInputClass` (`0x005eda60` → `0x006200e0`), the key
handler with the same steps inlined. When a menu is already open (HUD mode 3), a menu key for
another menu calls `SwitchInGameMenu(n)` (`0x0062cf10`: remove the old panel, add the new one with
flags 2, select its tab, run `k_pend_screenchg`); the key of the menu that is open closes it and
sets input class 0. The top bar's prev/next events step through 0..7 with wrap-around
(`0x0062cdf0`, `0x0062ccd0`, from `CSWGuiTopMenu::OnPrevMenu`/`OnNextMenu`). Esc (key action
`0xdf`), with no conversation (`+0xb4`) and a party leader, closes an open menu (HUD mode 3), and
when no menu is open and the input class is 0 (game) opens menu 7, the in-game options, then shows
tutorial pop-up 7 (`ShowTutorialPopup` `0x005edf40`); in every other case it is passed to the GUI
manager as input event `0xb4`. While the party leader is down (`0x005f2ed0`: client party member
0's server creature `GetIsDying`, HP below 1) the menu keys do nothing and Esc shows the message box
(modal, flags 1) with 42628 "You can't access the Start Menu while controlling an unconscious
character."; during the party-wipe sequence (client `+0x2c0`, gameloop.md) both instead start a
0.5 s fade to black (`0x005f2f20` → `StartGlobalFade(0, 0, 0.5, black)`). The menus refuse to open
during a conversation (`+0xb4`) or while a modal panel is up (`manager+0x98` non-zero). (high)

`CGuiInGame::HideInGameMenu(bNoPauseBanner)` (`0x0062cba0`): refuses (returns 0) before the panels
exist or while a modal panel is up; otherwise `SetHudMode(4)` (back to mode 1 unless in mode 2),
removes the top bar and the menu panel, `+0x30` = 0; if the player had not paused, toggles pause
bit 2 back off; if the player had paused, re-adds the pause banner (flags 4) when it is not up;
with `bNoPauseBanner` the banner is instead taken down in both cases. It then shows the bark
bubble again, plays GUI sound 5, sets sound mode 0 and returns 1. The caller returns the input
class to 0 (game). (The banner re-add also tests a global `0x007b92ac` that nothing writes, so it
is always 0.) (high)

`CGuiInGame::SetHudMode(nMode, b)` (`0x0062aa00`): 1 (unless the mode is 3) or 4 (unless the mode
is 2) → mode 1, 2 → 2, 3 → 3 (unless 2). Nothing more happens before the panels exist. In mode 1
the HUD, when not already up, is added with flags 4 (overlay) and brought to the front, and the
pause banner is re-added if it is wanted (`+0xb3c`, see `SetPauseState`) and not up; in modes 2
and 3 the HUD is removed and, when `b`, the pause banner is taken down. (high)

##### Pause banner, status summary, fades, conversations

| Address | Name (ours) | What | Conf. |
|---|---|---|---|
| `0x0062def0` | `CGuiInGame::SetPauseState(bPaused, nReason)` | called by the client main loop when the pause state changes (gameloop.md 1.2 step 28, 6.3), and with reason 10 by the target and self action blocks (`0x00689610`, `0x0068ad60`); for reasons 1, 4, 5, 7..11 sets the banner text (`CSWGuiPause::SetReason`) and shows the banner (flags 4) while the HUD is up (mode 1) or in a minigame area, otherwise takes it down until the HUD returns; stores `+0xb38` = paused, `+0xb3c` = banner wanted (0 for the other reasons); unpausing removes it and clears both | high |
| `0x0062eeb0` | `CGuiInGame::AddStatusSummaryEvent(nKind, nValue)` | accumulates into the status-summary panel: 0 journal updated, 1 credits (+/-), 2 XP, 3 stealth XP, 4/5 alignment shift (light/dark), 7 item received, 8 item lost, 9 level-up ready, 10 and 11 extra sounds (9, 10, 11 only queue GUI sounds 12, 13, 14 and never open the panel); kind 6 is ignored; while the suppress counter (`summary+0x78`, set by `SuppressStatusSummaryEntry` through `0x0062f0c0`) is positive, each event is swallowed and decrements it | high |
| `0x0062ef90` | `CGuiInGame::FlushStatusSummary` | from the client main loop (gameloop.md 1.2 step 22: news pending, input class 0, no load, conversation or fade, after 0.25 s): if a panel-worthy event is pending (flag bit 0) and the option "Status Summary" (client options `+0x14` bit 5) is on, requests a pause (`RequestPause(1, reason 6)`), remembers whether the game was already paused, shows the summary modally (flags 1) and sets input class 2; otherwise plays its sounds, flashes the matching HUD icons and clears the data | high |
| `0x0062b0b0` | `CGuiInGame::FlashHudIcon(n)` | forwards to the HUD (`0x00687fe0`) | high |
| `0x0062abf0` | `CGuiInGame::StartGlobalFade(bFadeIn, fWait, fLength, color)` | `SetGlobalFadeIn/Out` (`0x00546010`, `0x005460d0`), load screens, the death camera and others: adds the fade panel (flags 4), activates it and starts it | high |
| `0x0062b730` | `CGuiInGame::ShowConversationPanel` | conversation start (from `ShowDialogEntry` `0x00631d80`): the first time (`+0xb0` = 0 → 1) input class 3, hides the bark bubble (its voice stopped); for the ordinary conversation adds the fade layer, the top bar (grows) and the bottom bar (slides), then the conversation panel with flags 0 (computer: flags 2, full-screen with the `comp` backdrop); HUD mode 3. Flow is in [dialogue.md](dialogue.md) | med |
| `0x0062e550` | `CGuiInGame::ShowSoloModeConfirm(bForStealth)` | only with more than one party member, no conversation, no load, no area transition pending (area `+0x2c4`), player creature neither dead nor dying; pauses (bit 2) unless the player had paused, shows the solo box modally (flags 1), input class 2; otherwise GUI sound 2 (refusal) | high |
| `0x0062e6d0` | `CGuiInGame::CloseSoloModeConfirm` | unpauses (unless the player had paused), pops and removes it, input class 0 | high |
| `0x0062d3e0` / `0x0062d440` | `CGuiInGame::ShowInfoBox(strref)` / `CloseInfoBox` | the "Close" box at `+0x50`, modal (flags 1), input class 2; its only user is the store (`CSWGuiStore::OnBuy` `0x006c1130`, 41950 "You do not have enough credits to purchase this item."). Closing pops and removes it and sets input class 0 (2 only when the stored strref is 1, which no caller passes) | med |
| `0x0062b000` | `CGuiInGame::SetHudTarget(objectId)` | forwards to `CSWGuiMainInterface::SetTargetObject` (`0x006855f0`) | high |

#### CSWGuiMainInterface: the HUD

`.gui`: `mipc28x6` (800x600 and any unlisted size), `mipc210x7` (1024x768), `mipc212x9`
(1280x960), `mipc212x10` (1280x1024, `patch.erf`), `mipc216x12` (1600x1200), chosen in the
constructor (`0x0068c100`) from the manager's screen size; a 1280 width with another height loads
no `.gui` at all (only 1280 checks the height: 1024 wide always gets `mipc210x7`, 1600 wide always
`mipc216x12`). The files without the `2` (`mipc8x6`, `mipc10x7`, `mipc12x9`, `mipc16x12`) are an
older layout with six action slots and `LB_ACTIONS0..5` lists, and `mi8x6` and `maininterface` are
other leftovers; the code never loads any of them. 0xc8cc bytes, vtable `0x00753f50`, owner `CGuiInGame+0x90`, added with flags 4
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
| notifications | `LBL_JOURNAL`, `LBL_CASH`, `LBL_PLOTXP`, `LBL_STEALTHXP`, `LBL_DARKSHIFT`, `LBL_LIGHTSHIFT`, `LBL_ITEMRCVD`, `LBL_ITEMLOST` | icons beside the minimap that appear for 4 s after an event (`FlashNotifyIcon` `0x00687fe0`); showing plot XP hides stealth XP and dark shift hides light shift, and the reverse. Nine notify widgets are made (index 6 has no tag and stays unbound) | high |
| frame | `LBL_MOULDING1..3` | decoration | high |

The code looks up `LBL_DISABLED%d` for the party widgets, but the files call them `LBL_DISABLE1..3`,
so those labels are never bound and stay empty (they draw nothing). The constructor makes six
self-action widgets and four party widgets; only four and three exist in the `mipc2*` files, and an
unbound widget has a zero extent and draws nothing. Reproduce that: bind by tag, ignore missing
tags. (high)

**Construction details** (`0x0068c100`, high): after `FinishLoading` the constructor records the
minimap viewport (`LBL_MAPVIEW`'s rectangle x, y, width, height at `+0x6080..+0x608c`; the label is
read into a temporary and not kept as a control) and `LBL_MAP`'s width and height (`+0x6090`,
`+0x6094`), places `LBL_ARROW` at the centre of the viewport in viewport coordinates
(`((w - arrowW) / 2, (h - arrowH) / 2)`), calls `SetCombatMode(0)`, sets the combat-message strref to
48208, clears the "hover takes focus" flag (control `+0x44` bit 2, §8) on the menu, toggle and clear
buttons, creates the software `blackdot` quad, and sets every button's tooltip strref (control
`+0x24`) and key action (control `+0x30`, whose bound key name the tooltip appends; the clear
buttons get 48456 with `0xf5` and 48518 with `0xf0`).

##### Per-frame order

`Update` (`0x00686ba0`) only: updates the floating labels (damage numbers and the like, list `+0x5cb4`, each
label's slot `+0xa0`; combat.md 10.4);
counts down the combat message (`+0x7724`, total `+0x7720`; the message alpha is 1 for the first
half and then falls linearly to 0; at the end the controlled member's message, kept in its client
party record `+0x84`, reverts to strref 48208, which the HUD then shows); sets
`TB_SOLO` visible when the party has more than one member (party table `+0x00`, NPCs in the party,
above 0) and checked when solo mode is on (party table `server+0x1b770`, `+400`); `TB_STEALTH`
visible when the player creature can stealth (`0x00610ac0`: it has a server creature, the area's
RestrictMode `+0x2b0` is 0, skill 2 (Stealth) is usable (`0x006477e0`: ranks above 0, or, for a skill
flagged in the rules' skill table, one of its classes has it), and an item whose base item has
ItemType 44, a stealth unit, sits in the belt (slot `0x400`) or the creature-hide (slot `0x20000`)
cell; high) and checked when stealthed (creature `+0x194` bit 0); `TB_PAUSE` checked when the
game is paused by the player; the menu buttons and `LBL_MENUBG` hidden by "Hide InGame GUI". (high)

`Render` (`0x0068b4a0`) does the real refresh, only while the panel is visible (flag bit 7) and a
party leader with a valid object id exists:

1. count down the action-failure message timer (`+0x6c`);
2. `UpdatePartyPortraits` (`0x00687860`);
3. `UpdateReticles` (`0x0068a310`: picks `hostilereticle2`, `friendlyreticle2`, `combatreticle`,
   `hostilearrow`, `friendlyarrow` for the target marker; positions are projected from the target);
4. the target block's timers (`0x00684e70`), `UpdateActionMenus` (`0x00689d80`), the nine
   notification icons (`0x00686a20`, on the manager's interface-clock step), the leader-swap
   animation of the party widgets (`+0x5a28` seconds, `0x006851b0`);
5. `SetCombatMode(client in combat)` (`0x006874c0` with `0x005ede70`), the blink of each of the six
   action slots (`0x006858e0`), and in combat (`+0xa45c` bit 1, set by `SetCombatMode`)
   `UpdateCombatQueue` (`0x0068a010`);
6. if the global HUD switch `g_bMainInterfaceVisible` `0x007a2288` is on: `RenderMiniMap`
   (`0x0068ab10`), the panel's own controls (`CSWGuiPanel::Render`), the floating target block
   (`0x00685ed0`, its own viewport at the projected rectangle at target block `+0x15ac..+0x15b8`),
   the floating labels of `+0x5cb4` (slot `+0x38`, in a viewport over the panel's extent), and per
   party widget the effect-count icons (`0x00685330`). (high for the order, med for the inner details)

##### Party portraits

Each party widget (0xea8 bytes, `+0x1f88 + 0xea8·i`, i = 0..2, numbered 1..3 for the control names,
plus a fourth at `+0x4b80`, number 4, used as the "ghost" during a leader swap; init `0x006898a0`)
caches current/max vitality (`+0`/`+4`), current/max Force (`+8`/`+0xc`), level (`+0x10`), the XP
still needed for the next level (`+0x14`), the first and last name (`+0x18`/`+0x20`), the two effect
counts (`+0xea0`/`+0xea1`) and a changed flag (`+0xea4`). `UpdatePartyPortraits` (`0x00687860`,
every frame from the HUD's Render) walks the client party (`0x005ed8b0`, member i via `0x006346c0`,
its server creature via `0x0060fb20`):

- **Slot mapping:** member 0 (the leader) goes to widget 0 (`*CHAR1`). With exactly two members
  the companion goes to widget 2 (`*CHAR3`, next to the leader) and widget 1 is hidden; with three,
  member i goes to widget i. While the swap timer (`+0x5a28`) runs the mapping rotates: member 0
  goes to widget 1, member 1 to widget 2 (with two members: to widget 0, and widget 1 is hidden),
  member 2 to widget 0; the member placed in widget 0 is also copied into the ghost widget. Widgets
  without a member hide all their controls. (high; med for the swap mapping)
- **Portrait:** the creature's portrait resref (client creature slot `+0x148`) becomes the fill of
  `LBL_CHARn`. (high)
- **Vitality:** `PB_VITn` max = max hit points (creature slot `+0x98`, bonus included), value =
  current hit points (slot `+0x9c`); `SetVitality` (`0x006857d0`) takes the poisoned flag
  (`creature+0x9e0`) as its third argument and fills the bar with `greenfill` when poisoned, else
  `redfill`. (high)
- **Force:** `PB_FORCEn` max = `GetMaxForcePoints`, value = the stats' current Force points
  (`+0x124` plus `+0x126`); a creature with no Force gets max 1, value 0. (high)
- **Level and XP:** level = `GetLevel`; `+0x14` = the XP the next level needs (`0x005a6610`, the
  `g_pRules` XP table at the current level) − the creature's XP (`stats+0x68`), 0 when not positive.
  (high)
- **State** (`SetStatus` `0x006867f0`, first match wins): dead (creature slot `+0x94`) or dying
  (`0x004ef890`: in the client party with ≤ 0 hit points) → state 1, `LBL_DISABLEDn`; else able to
  level up (`CanLevelUp` `0x005a6810`: level below the cap at `+0x94` of the server options block
  (server internal `+0x10004`), XP ≥ the `g_pRules` table entry for the current level, not dead or
  dying) → state 4, `LBL_LEVELUPn` (pulsing) and `LBL_LVLUPBGn`; when the client creature's `+0x440`
  bit 1 is set (by its constructor `0x00616a20` and again when a level-up finishes, `0x006e88a0`)
  this also raises status-summary event 9 "level-up ready" (`AddStatusSummaryEvent`) and clears the
  bit; else helpless (`0x005b4880`: creature `+0x8ed` set, or dying) → state 2,
  `LBL_DEBILATATEDn`, and for party member 0 the combat message 47915 "Player debilitated.
  Cancelling combat actions."; otherwise state 0 and it counts the creature's active effects
  (`+0x8f4` list, effect `+0x1c` non-zero) split by the effect's `+0x14` (non-zero → `+0xea0`, zero
  → `+0xea1`), the counts behind `LBL_CMBTEFCTINCn`/`LBL_CMBTEFCTREDn` (both bound outside the
  panel's control list); a non-zero state zeroes both counts. `LBL_BACKn`, `LBL_CHARn`, the two bars
  and `BTN_CHARn` show whenever the widget has a member. A member that is not helpless turns a
  standing 47915 message (combat bar `+0x7728`, timer `+0x7724` = -1) into 48208 "COMBAT MODE
  engaged. Press the Disengage button to cancel.". (high)
- **Clicking** `BTN_CHAR1` (`OnPartyMemberButton` `0x00688690`) opens the equipment menu
  (`BTN_EQU`), or the character sheet (`BTN_CHAR`) when the leader can level up; clicking a
  companion's portrait makes that member the party leader (`0x005edc30` → `SetPartyLeader`) unless
  it is dying (≤ 0 hit points, `0x004ef890`); with two members both companion widgets mean member 1.
  (high)
- **Tooltip:** `BTN_CHARn` is a button subclass (`CSWGuiPartyButton`, vtable `0x00753bd0`, ctor
  `0x00686ab0`) whose tooltip is "*first* *last*\nVitality: *cur*/*max*\nForce: *cur*/*max*\nLevel:
  *n*\nXP Needed: *n*" (strrefs 1061, 1060, 32154, 48459; `0x00684f50`), without the Force line
  when max Force is 0; its Render (`0x00686790`) rebuilds it while the button's flag bit 6 is set
  whenever the widget's changed flag is set, then clears that flag. (high)

##### Action menus (self and target)

An action slot (`CSWGuiActionSlot`, 0x71c bytes, init `0x0068b9d0`) binds `BTN_%s%d` (the frame,
slot `+0`), `LBL_%s%d` (the icon, `+0x1c4`), `BTN_%sUP%d` (`+0x388`), `BTN_%sDOWN%d` (`+0x54c`) with
`%s` = `ACTION` or `TARGET`. The click handler (event 0x27, `OnActionButton` `0x0068b970`), the slot
tooltip and the key action sit on the icon; all four controls take the hilight event (0) and the
wheel events 500/501 (previous/next entry); the up and down buttons' clicks cycle. Self slots are HUD
panel controls (the HUD initialises six at `+0x772c`, indices 0..5, and uses 0..3); target slots are
children of the floating target block and are not in the panel's control list (they are drawn by the
block). Up/down buttons have tooltips 48465/48466 and key actions `0xf8`/`0xf9`; the slot tooltips
are 48486 "Activate Friendly Power", 48291 "Activate Medical Item", 48299 "Activate Non-medical
Item", 48295 "Activate Mine" (self slots 0..3, key actions `0xe8`, `0xea`, `0xee`, `0xec`) and
48303/48307/48311 "Activate Left/Middle/Right Action" (target slots, index + 4: `0xe2`, `0xe4`,
`0xe6`). (high)

`UpdateActionMenus` (`0x00689d80`) rebuilds, every frame (from the HUD's Render, also from
`OnWorldClick`), six action lists in the HUD (`+0x74 + 12·k`, a growable array of 0x38-byte entries)
from the leader's client creature (`0x00619db0`, category k = 0..5; only 0..3 are shown), then the
target block's three lists (`0x00689410`). An entry holds a name (`+0`), an id (`+8`), a callback
(`+0xc`), a target object (`+0x1c`), an icon resref (`+0x20`), flags (`+0x30`: bit 0 usable, bits
1..4 a reason code) and a count (`+0x34`); a fresh entry (`0x0063c000`) is usable, reason 0, count 1,
target `OBJECT_INVALID`. The selected entry id of each slot is kept in `+0x1bac + 4·k` (-1 none;
when it is not in the list the slot shows the first entry); the icon is drawn at alpha 1 when the
entry is usable and the leader is neither dead nor dying, 0.25 otherwise; the up/down arrows show
when the list has more than one entry. How the lists are built (which talents, items and targeted
actions qualify) belongs to [actions.md](actions.md) and [combat.md](combat.md). (high)

The mine slot (category 3, `0x00619db0` → `0x006197d0` with mask 2): three items on the client
creature (`+0x23c`, `+0x240`, `+0x248`, likely worn; only where the area's RestrictMode, server area
`+0x2b0`, is 0), then the leader's item repository (`GetItemRepository(1)`); `0x00616520` keeps an
item whose baseitems `itemtype` is 28 (Trap_Kit) and that passes CanUseItem; when it carries a Trap
property (46) that property must be usable and the creature able to use Demolitions
(`0x005af880(stats, 1)`: Demolitions is not usable untrained, so a base rank of 1 or more); non-plot
items (item `+0x108`) are dropped where RestrictMode is set. The entry (`0x006193a0`) is labelled
"<item name> (self)" (`"%s (%s)"`, 38005), shows the item's own icon, its id is the item's with bit
0x40000000, its target the leader, its count the stack (`+0x28c`; the name is shown as "%s (%d)"
above 1), and its usable flag is never cleared for a repository item. Its callback (`0x0060f590`)
sends input 9 (`0x00677bd0`, message 6/9): the item, the leader as the target and a zero point,
which UseItem turns into SETTRAP ([actions.md](actions.md) 3.14). (high)

##### What the target block offers, by target

`CSWGuiTargetInfo::Refresh` (`0x00689410`) fills the three lists through `FUN_00619c20`, once per slot
(0 left, 1 middle, 2 right), which switches on `GetTargetKind` (`0x0060fcc0`; movement.md 7.4). The
builders behind it never ask who the target is: the switch alone keeps the hostile actions off
friends. A creature is kind 4 when its client hostile slot (vtable `+0x138`, the server's
friend-or-enemy answer: reputation below 11) is set **or while the leader's 1.5 s dead-target keep
timer (`client+0x378`, `FUN_005ee0f0`) runs**, otherwise kind 3, whatever else it is. (high, static
reading of the switch and the builders)

| Target | Kind | Left (0) | Middle (1) | Right (2) |
|---|---|---|---|---|
| hostile creature | 4 | the leader's best rank of the three combat feats for its right-hand weapon, then Attack (`0x00619950`, `0x00619b10`) | the hostile Force powers (`0x006191f0`; a droid leader its equipment's abilities) | the party's grenades (`0x006198e0`: items with baseitems ItemType 6 and a cast-spell property; none under RestrictMode) |
| party member, friendly or neutral creature | 3 | nothing | nothing | nothing |
| dead or dying creature | — | not selectable (`GetIsSelectableTarget`, movement.md 7.1), so no block, except the one just killed while the keep timer runs, which is then kind 4 like every creature | | |
| door | 1 | Bash (`FUN_00684410`: locked, not plot, RestrictMode 0) | Security (locked, no key required, the leader has the skill) | nothing |
| placeable with an inventory | 1 | Bash (`FUN_006837d0`, same tests) | Security (locked, the leader has the skill) | nothing |
| placeable without one | 3 | Bash (`FUN_006837d0`) | the hostile Force powers when its client hostile flag is set and its reputation toward the leader is below 11, else as for a placeable with an inventory (no Security without an inventory) | nothing |
| mine (known trap trigger) | 2 | Disable (`FUN_00691f00`: hostile mine, Demolitions) | Recover (Demolitions) | nothing |

So a party member's block shows its name and health bar only (the block shrinks to them when no list
has an entry), and the keys 1-3 (which run the selected entry of these lists) do nothing on it. The
other ways to act on a friend give no hostile choice either: a click or R runs the default list
(Talk on a kind-3 creature, 7.4), and the self slots hold friendly powers, medical and other items
used on the leader, and mines. Ours (`hud::attack_slot`, `middle_actions`, `grenade_actions`) follows
the table; the keep timer is `w.target_keep` (hud::pick_target), and `hud::is_foe` makes every creature kind 4
while it runs.

##### The target block's drawing

`CSWGuiTargetInfo::Render` (`0x00685ed0`, only while the block's flag `+0x1aec` bit 0 is set) pushes a
viewport over the block's rectangle and draws, in this order, the health background (`LBL_HEALTHBG`),
the name background (`LBL_NAMEBG`), the name label (`LBL_NAME`), the health bar (`PB_HEALTH`), then
each of the three slots (`CSWGuiActionSlot::Render` `0x00685870`: frame, up arrow, down arrow, icon,
each only if its visible flag is set). `FUN_00686090` sets the rectangle every frame: with no target
it clears flag bit 0 (the block is hidden); its height is the first slot's `top + height` (35 + 59 =
94 in `mipc28x6`) when any of the three lists has an entry, else the health bar's `top + height` (27
+ 6 = 33); normally its bottom sits 32 pixels above the target's projected screen point, centred on
it, clamped to the screen area (while flag bit 1 is set or the timer `+0x1ae0` runs it keeps its
bottom and only the height changes), so a target with nothing to offer shows only the name and the
bar, closer to the reticle. The slots are never hidden one by one: `Refresh` (`0x00689410`, every
frame, with a null target too) calls `CSWGuiActionSlot::SetState(slot, bEmpty, bHasMore)`
(`0x00689280`) per slot (and `UpdateActionMenus` the same for the four self slots). SetState does,
whichever way `bEmpty` goes: blank the icon when empty (`SetFill("")`, icon alpha 1); set the
frame's alpha, BORDER (`+0x8c`) and HILIGHT (`+0x100`), to **1.0 when it has a choice and 0.5 when
it has none**; and set the **up and down arrows' visible bit (`+0x3cc`, `+0x590`, bit value 2) to
`bHasMore`**, which the callers pass as "more than one entry". So an empty slot is a blank frame at
half strength with no arrows, a slot with one choice has no arrows, and only a slot with several
shows them. The arrows' initial state (visible, from the control constructor's flags `0x0a`, and no
field of the .gui changes it) never shows: the first `Refresh` hides them. (high)

`FUN_006859e0` (called by `UpdateReticles` for any target, every frame) sets the three frames' BORDER fill to `lbl_miscroll_h`
(red) when the reticle is the hostile one and `lbl_miscroll_f` (blue) otherwise, and the health bar's PROGRESS fill to
`ENEMY_BAR` / `FRIEND_BAR`, or `POISON_BAR` when the creature is poisoned (`creature+0x9e0`): `enemy_bar` is red,
`friend_bar` blue, `poison_bar` green. The combat reticle swap is the reticle's only combat change; nothing tints the slots
for combat mode. The hilight border stays `lbl_miscroll_hi` (yellow). (high)

**The target marker** (`UpdateReticles` `0x0068a310`) is one control (`mainif+0x5a2c`, fill `+0x5a9c`, fill
rotation `+0x5aa4` in degrees), shown while the HUD target projects at all (the object's slot `+0x13c` answers 0
none, 1 in front of the eye, 2 behind it, with the point divided through either way). Its side is 64 px within
5 m of the leader, shrinking to 16 (creature) or 32 (other) at 30 m. A hostile creature in client combat mode
(`+0x320`, `0x005ede70`) gets `combatreticle`: the timer `+0x5cb0` is set to -1 by `SetTargetObject`
`0x006855f0` on a new target and by `ClearAllCombatActions` `0x006887d0`; at -1 the side gets 64 more and the
timer 0.5 s, then while it runs the side gets `timer x 128` more (truncated). Placement, with the screen
rectangle `+0xbf70`: in front, a point within 32 px of the left or right edge gives a 32 px arrow
(`hostilearrow` / `friendlyarrow`) at that edge (rotation 0 on the left, 180 on the right) at the point's
height less 16, clamped to the top or bottom 32 px; otherwise a point within 32 px of the top or bottom gives
the arrow there at the point's x less 16 (rotation 270 at the top, 90 at the bottom); otherwise the reticle
centred on the point. Behind the eye always the arrow: on the right edge (180) when the divided point is left of
the middle, else the left (0); its y the bottom 32 px for a point within 32 px of the top, the top for one near
the bottom, otherwise the point's y mirrored (`h - (y + 16)`) when it is in the upper half, `y - 16` in the
lower. So the arrow picture points left and the rotation turns it counter-clockwise on the screen. The target
block (`FUN_00686090`) follows the same cases: it stays shown while there is a target, centred over the point
in front, clamped to the screen, and for a target behind the eye moved to the edge on its side. (high)

`CSWGuiActionSlot::Init` (`0x0068b9d0`, self and target slots) writes 180.0 into the fill rotation (border `+0x1c`) of the
down button's BORDER and HILIGHT, so a down arrow is `lbl_miarr_1` / `_2` drawn half a turn round; for a target slot
(`bTarget`) it also makes the frame the parent of the other three (`AddChild`), so the frame lights when the pointer is on
any of them. `FUN_00685cb0` puts the name of the hovered slot's selected entry in `LBL_NAME` (the creature's name when no
slot is hovered), not in `LBL_ACTIONDESC`, which belongs to the self slots (`OnSelfActionHilight`). (high)

Clicking a self slot (`UseSelfAction` `0x0068ad60`, also reached from `HandleInputAction`): while
`g_bAlternateActionsHeld` is set it first runs `ClearAllCombatActions`; it records the slot as the
current one (`+0x1bc4`) and takes the selected entry (or the first), which needs a resolvable target
object (`+0x1c`). If the entry is not usable (or has no callback), its reason code picks a message
shown for 5 s in `LBL_ACTIONDESC` (strref `+0x70`, timer `+0x6c`, fading over the last 2.5 s,
`0x00686e20`): 1 "Force Depleted" (38613), 2 "Restricted by Armor" (38614), 3 "Missing Item"
(38615), 4 "Target too Close" (42422), 5 "Full Health" (42498), 6 "PC Dead" (47936); GUI sound 2.
If usable: when the leader's client creature is not in combat mode (`+0x440` bit 0, as in
[gameloop.md](gameloop.md) and [combat.md](combat.md)), `0x0063d490` clears the scheduled actions
of the leader's server combat round (`ClearScheduledActions`), and for a door's Bash (block kind 0,
entry `0x3f5`) or a hostile creature (kind 3) the combat message 48208 "COMBAT MODE engaged" is put
up at once (`+0x7724` reset, `ShowCombatMessage(0xbc50)`); in combat mode while auto-paused (client
`+0x384` bit 0, `IsAutoPaused`), the pause banner switches to reason 10 ("Action added to queue.").
Either way GUI sound 6 plays; then the entry's callback runs with its id and the leader (it posts the
request to the server side), the icon blinks once (fade out and back in, two 0.1 s phases,
`0x006858e0`), and if the leader is still out of combat mode: when the target is a hostile
creature (kind 3) and the client was out of combat mode too (`+0x320`), `SetCombatMode(1)` (the
decompile drops this flag; asm `0x006896f4`–`0x00689710`, `0x006897c3`), and the leader's server
actions are cleared at once (`ClearAllActions(0)`), so the new request replaces them instead of
queueing behind them. A callback that turned combat mode on itself (attack, feat, power, grenade)
skips that clear. The block's kind is `FUN_0060fc00`'s (stored at `+0x1aea`): 3 a creature whose
client hostile slot `+0x138` answers or while the 1.5 s keep timer `client+0x378` runs, 2 any other
creature, 0 a door or a placeable with an inventory, 2 one without, 1 a trigger. Who else turns
combat mode on and off: [movement.md](movement.md) 2.1. (high)
Up/down (`0x0068af70`/`0x0068afe0`) select the previous/next entry with wrap-around (GUI sound 7,
only with more than one entry), pausing with reason 7 when the "Action Menu" auto-pause option
(client options bit 15) is on, and offer tutorial popup 5. Hovering a slot records it as the current
one (`+0x1bc4`). While one of the current slot's controls is hilighted, `LBL_ACTIONDESC` shows its
selected entry's name ("%s (%d)" with a count above 1), its height fitted to the text and anchored
at the bottom, `LBL_ACTIONDESCBG` matched to it (`SetActionDescription` `0x00685560`). (high)

##### Combat mode, queue, clear buttons

`SetCombatMode(b)` (`0x006874c0`) shows or hides the combat controls and moves the minimap group
(`LBL_MAPBORDER`, `LBL_MAP`, `BTN_MINIMAP`, the minimap viewport and the nine notification icons)
down by the combat-message bar height (`+0xa458`) when combat starts and back up when it ends. In
combat (HUD `+0xa45c` bit 1) `UpdateCombatQueue` (`0x0068a010`) walks the leader's server action
queue (creature `+0xfc`) and puts up to four icons in `LBL_QUEUE0..3`: one for the first
ATTACKOBJECT (0xc), CASTSPELL (0xf) or ITEMCASTSPELL (0x2e) action, or the combat dispatcher 0x3f
while the combat round has a current action, then, for each 0x3f action, one per entry of the
combat round's scheduled list (round `+0x9b0`); the unused labels are hidden.
`BTN_CLEARONE`/`BTN_CLEARONE2` (tooltip 48456 "Clear Combat Action", key action `0xf5`, only while
visible) offer tutorial popup 0x20 (`ShowTutorialPopup` `0x005edf40`) and, when no popup opens,
remove the last scheduled action of the leader's combat round (`0x006880c0`:
`RemoveLastScheduledAction`, or `ClearAllActions(1)` on the server creature when there was none);
`BTN_CLEARALL` (48518 "Disengage", `0xf0`) ends combat mode for the leader and cancels its server
actions, GUI sound 0 (`0x006887d0`). (high for the wiring, med for the queue filter)

The bar follows the client's combat mode (`client+0x320`, the leader's client creature `+0x440`
bit 0), not the server's combat state (`+0x4e0`): it comes up the moment a fighting order is given
from the target block or as a default action, paused or not, and goes when `0x005f3ad0` finds the
leader with no live target and no live foe on its way ([movement.md](movement.md) 2.1). (high)

##### Minimap

`RenderMiniMap` (`0x0068ab10`) runs when the option "Mini Map" (client options `+0x14` bit 3) is on
and the module's area map (`module+0x218`) has a map. The map texture is `lbl_map` + the module's
area resref (`0x00687e40`, format `lbl_map%s`), loaded once into `LBL_MAP`. Each frame `LBL_MAP` is
offset so that the leader's map point (party slot 0 cached in the area map, `0x005791b0`) times the
map scale (area map `+0x14`) sits at the viewport centre, and the arrow's rotation is the heading of
the current camera (client module `+0x40`, `0x005ed560`; orientation slot `+0x24` turned into a
forward vector by `0x0044f420`) plus the map's north offset (0, 180, 90 or 270 degrees by the area
map's orientation `+0x10`; `0x00578ed0`). Drawing: a viewport of `LBL_MAPVIEW`'s square, `LBL_MAP`,
then markers (`0x00688100`), then `LBL_ARROW`. Clicking the minimap opens the map menu. The map
logic itself (map points, notes) is with the map panel. (med; the arrow following the camera
needs a runtime check)

##### Notification icons

Nine labels (`CSWGuiNotifyLabel`, 0x14c bytes, `+0xa460 + 0x14c·i`, init `0x00686920`) indexed 0
journal, 1 cash, 2 plot XP, 3 stealth XP, 4 dark shift, 5 light shift, 6 unused, 7 item received,
8 item lost. `FlashNotifyIcon(i)` (`0x00687fe0`) makes icon i visible for 4.0 s (hiding its partner:
plot and stealth XP hide each other, so do dark and light shift) and marks it new; their borders
pulse. Called through `CGuiInGame::FlashHudIcon` (`0x0062b0b0`) both by `FlushStatusSummary` when the
status summary is not shown and by the summary panel's `OnPanelAdded` (`0x00625c60`). (high)

##### Toggles

- `TB_PAUSE` (`0x00688590`): requests the opposite of the current player pause (client
  `0x005edc20`, reason 4), ends an auto-pause if one is on (`RequestAutoPause(0)` `0x005edee0`,
  client `+0x384` bit 0), and offers tutorial popup 6 (`ShowTutorialPopup` `0x005edf40`). The pause
  logic is in [gameloop.md](gameloop.md). (high for the calls)
- `TB_SOLO` (`0x00688610`): opens the solo-mode confirmation (below). (high)
- `TB_STEALTH` (`0x00688640`): when the player creature passes `GetCanStealth` (`0x00610ac0`: area
  RestrictMode 0, Stealth usable, a stealth unit, baseitems itemtype 44, in one of two equipment
  slots, client creature `+0x248`/`+0x258`), toggles stealth for the leader (`0x0060f4b0`). (high)
  The toggle (also key action 264, G, which first asks `0x00610ac0`): with solo mode off (party
  table `+0x190`) and more than one member in the client party it shows the solo-mode box for stealth
  (37890); otherwise it sends the server input 7 (message 6/7, `0x0060ee00` → `0x00677b10`): use
  skill 2 (Stealth) on the leader, which `UseSkill` turns into `SetActivityMode` mode 1
  (`0x004f2a50`). That does nothing for a dead or dying creature or one that cannot use Stealth;
  in stealth it leaves it; in combat (`+0x4e0`) it refuses with feedback 0x3c (1452, "You cannot
  enter stealth mode while in combat."); otherwise it enters it. The box's OK (`0x006c2400`) toggles
  solo mode (`0x005f2a20`: `SetSoloMode(!solo, 1)`, then the script `k_sup_solo`, which the game
  does not ship) and, for stealth, sends the same request for the player creature. (high)

#### CSWGuiTopMenu: the tab bar of the in-game menus (`top`)

0x1c24 bytes, ctor `0x00627980`, vtable `0x00750148`, owner `CGuiInGame+0x08`; panel flags `0x60`
(bits 5 and 6: shifted by the 640x480 centring offset in x and y, so the 640x86 root sits at the
top of the centred 640x480 area; render-gui.md, Panels). Controls: `LBLH_EQU`, `LBLH_INV`,
`LBLH_CHA`, `LBLH_ABI`, `LBLH_MSG`, `LBLH_JOU`, `LBLH_MAP`, `LBLH_OPT` (type 5 highlight frames) and
`BTN_EQU` ... `BTN_OPT` (52x40 tab buttons) with the same tooltips and key actions as the HUD.
Each tab button calls `SwitchInGameMenu` with its menu number (`0x00624cf0` equip 0, `0x00624d10`
inventory 1, `0x00624d30` character 2, `0x00624d70` abilities 3, `0x00624dd0` messages 4,
`0x00624d90` journal 5, `0x00624d50` map 6, `0x00624db0` options 7). Its input handler
(`0x00624970`) turns presses of key actions `0xf3`/`0xf4` into events `0x35`/`0x36`, which every
`LBLH_*` answers with previous/next menu (`0x00624c00`/`0x00624c30`). `SelectTab(n)`
(`0x00624bd0`) makes the control whose `.gui` ID is n the active control: the `LBLH_*` IDs 0..7
equal the menu numbers, so the active control is the frame of the open menu (which is why the
frames receive `0x35`/`0x36`). Update (`0x00624c60`) makes `LBLH_INV` pulse while the party
inventory (party table `+0x118`) holds items flagged "new" (repository `+0x04` count,
party-items-saves.md 5.2) and `LBLH_JOU` pulse while any journal entry carries the "new" flag
(`0x00676470`, entry byte `+0x2c` bit 2). All tags and IDs verified against `top.gui`. (high)

#### CSWGuiMessages: message log (`messages`)

Menu 4. 0xaf4 bytes, ctor `0x00626400`, vtable `0x0074fd18`. Controls: `LB_MESSAGES` (feedback
log) and `LB_DIALOG` (conversation history), both 544x289 at the same place, with 64 preallocated
proto rows each; `LBL_MESSAGES` (title); `BTN_SHOW` (toggle, sends event `0x29`); `BTN_EXIT`
(sends `0x28`). `OnPanelAdded` (`0x00626d90`) refills both lists from the feedback and dialogue
histories kept at `CGuiInGame+0xf8`/`+0xfc` (`0x0062ad60`), shows the view remembered in `CGuiInGame+0xbc8` and asks for
tutorial popup 12.
`ShowDialogLog` (`0x00624df0`): `LB_DIALOG` visible, button text 42142 "Show Feedback", title
"Messages - Dialog" (strrefs 1563, 371), remembers 0. `ShowFeedbackLog` (`0x00624f70`):
`LB_MESSAGES` visible, button 42143 "Show Dialog", title "Messages - Feedback" (42167), remembers
1. Input (`0x00628260`, presses only): events `0x28`, `0x2d`, `0x2e`, `0xdf` close the menu
(`HideInGameMenu`) and, when that succeeds, return to the game input class; `0x29` plays GUI sound
0 and toggles the view. The panel also watches the event sequence `0x29, 0x2f, 0x27, 0x29` and
then shows a hidden feedback line ("Punch it, Chewie!") and sets a flag (`0x008338e8`) that the
free-camera key reads: an easter egg, safe to skip. The
feedback lines are added by the client's combat-feedback formatter and copied into the list when the
panel opens (combat.md section 10.1). All tags verified. (high)

#### CSWGuiMessageBox: the confirm/OK box (`confirm`) and its variants

0x984 bytes, ctor `0x00626df0`, vtable `0x0074fdb0` (33 slots: the panel's 27 plus six).
`confirm.gui` is a 290x87 box: `LB_MESSAGE` (one proto row, `dialogfont16x16`, centred text),
`BTN_OK` (strref 1580 "OK") stacked above `BTN_CANCEL` (1581 "Cancel"), both 100x22; the
constructor adds a hidden 32x32 icon label at (0,10) (`+0x1b4`). A new box is in OK/Cancel mode
(flags bits 1 and 2) with open sound 15. It is centred on the screen and shown with
`AddPanel(box, 1, 1)` (flag 1: pushed as modal). (high)

| Slot / address | Name (ours) | What | Conf. |
|---|---|---|---|
| slot 27 `0x006249d0` | `SetMessageStrRef(strref)` | TLK text, then slot 28 | high |
| slot 28 `0x006271a0` | `SetMessageText(text)` | resolves TLK tokens (`CTlkTable::ParseStr`), puts the text in the list box and re-fits the box (`FitToText` `0x006253a0`) | high |
| slot 29/30 `0x00625260`/`0x00625270` | `SetOkStrRef`/`SetCancelStrRef` | button captions | high |
| slot 31 `0x00625280` | `HideButtons` | flag bit 3, hides both buttons (a "please wait" box) | high |
| slot 32 `0x006252a0` | `OnClose` | run when the box closes: shows both buttons again, clears bit 3, restores the captions 1580/1581 | high |
| slot 15 `0x006250f0` | `HandleInputEvent` | see below | high |
| slot 18 `0x006258f0` | `OnPanelAdded` | saves the client input class and switches to 2 (GUI); makes `BTN_OK` the active control; saves the cursor and moves it to the centre of `BTN_OK`, or of `BTN_CANCEL` in OK/Cancel mode (unless `+0x980` is set) | high |
| slot 19 `0x00625a00` | `OnPanelRemoved` | restores the input class and the mouse position | high |
| `0x00627130` | `SetConfirmMode(b)` | b = 1: OK and Cancel, open sound 15; b = 0: OK only, open sound 2 | high |
| `0x00624a40` | `SetCallback(owner, fn, param)` | called with `param` (owner as `this`) when the box closes; skipped when owner or fn is null | high |
| `0x00627160` | `SetIcon(resref)` | for a valid resref: sets the icon label's fill and shows it (flag bit 4) | high |
| `0x00625a80`/`0x00625aa0` | `OnOk`/`OnCancel` | resend as events `0x1f6`/`0x1f7` | high |

Flags at `+0x64`: bit 0 result (1 = OK), bit 1 OK/Cancel mode, bit 2 buttons shown, bit 3 no
buttons, bit 4 icon. `BTN_OK` is visible when bit 2 is set, `BTN_CANCEL` when bits 1 and 2 are, the
icon when bit 4 is (`0x00625200`). **Closing** (`HandleInputEvent`, presses only): event `0x1f6`
(OK) sets the result to 1; `0x1f7` (Cancel) and the cancel keys `0x28`/`0x2e` set it to 0 in
OK/Cancel mode and to 1 otherwise; then the flags go back to the defaults (bits 1 and 2 set, icon
bit 4 cleared, so the next use is OK/Cancel again unless `SetConfirmMode(0)` is called), slot 32
runs, the box is marked for removal after drawing, `PopModalPanel`, GUI sound 0, and the callback
runs. Up/down (`0x39`/`0x3a`) send the single-step events `0x31`/`0x32` to the message list.
**Fitting** (`0x006253a0`, from the design extents saved by the constructor): an icon adds 32
pixels of height above the text (the box moves up 16); with the buttons hidden the box loses the
OK button's height, in OK-only mode the Cancel button's height + 2. Each visible button is reset to
100 pixels wide and widened in 10-pixel steps until its caption fits on one line, plus twice its
border, and the box is made at least as wide as that button minus 2. Then, while the message list
cannot show every line: if the box is taller than 160 and narrower than 440, it and the list widen
by 40 (the box moves left 20); if it is lower than 280, both grow by one text line (the box moves up
half a line); it stops when the text fits or both limits are reached, and a list that still
overflows gets its scroll bar. Finally the icon is centred horizontally, `BTN_OK` is placed 4
pixels below the list and `BTN_CANCEL` 2 pixels below `BTN_OK`, both centred, and the box is
re-centred on the screen. (high)

Typical use (quit confirmation from the window-close handler `0x005f6960` and the options menu's
Quit `0x006ab1b0`): take `CGuiInGame+0x98`, `SetConfirmMode(1)`, `SetCallback`,
`SetMessageStrRef(42348)` "Do you really want to quit?", `AddPanel(box, 1, 1)`; the window-close
handler also switches the input class to 2 itself (`OnPanelAdded` does so anyway). (high)

Variants (all `confirm.gui`):

| Owner | Ctor / vtable | What | Conf. |
|---|---|---|---|
| `CGuiInGame+0xa0` | `0x006aa100` / `0x00755cd0` | **tutorial box** (`CSWGuiTutorialBox`): message font `fnt_d16x16`; pauses the game when shown (client reason 2) unless already paused; the accept and cancel keys (`0x27`, `0x28`, `0x2d`, `0x2e`) and OK (`0x1f6`) all page forward through the `tutorial.2da` row (`+0x994`, page counter `+0x995`): columns `Message0..2` give the pages' strrefs, `Icon` the icon; each page switches to OK only, with the OK caption 38623 "Continue" while a further page exists, else 1580 "OK" (`NextPage` `0x006aa670`); the box closes only when no page remains | high |
| `CGuiInGame+0xa4` | `0x00626df0` + `0x007513f8` | controller-disconnected box (Xbox heritage): its `OnPanelAdded` (`0x00627220`) sets OK only (open sound 2), message 48398 and callback `0x00625a40` each time it is shown | high |
| `CGuiInGame+0x8c` | `0x006c2270` / `0x00756f28` | **solo-mode box** (0xfc8 bytes): `SetMode(bForStealth)` (`0x006c24a0`) picks 37889 "turn Solo Mode on?", 37890 (stealth needs solo), 37891 "turn Solo Mode off?", 37892 (off also ends stealth); OK and the accept keys (`0x1f6`, `0x27`, `0x2d`) toggle solo mode (`0x005ede60`) and, for the stealth case, request stealth (`0x0060ee00`); those and Cancel / the cancel keys (`0x1f7`, `0x28`, `0x2e`) all call `CloseSoloModeConfirm` instead of the base close path; its Render (`0x006c2310`) marks it for removal by itself while a conversation is pending (`CGuiInGame+0xb4`), during a load, when the server area's `+0x2c4` is set (not identified), or when the player creature is dead (vtable `+0x94`) or dying | high |
| `CGuiInGame+0x50` | `0x006ce9c0` / `0x007579c8` | info box (0x988 bytes; `ShowInfoBox(strref)` `0x0062d3e0`, used by the store's buy, keeps the strref at `+0x984`): OK caption 1582 "Close", OK only; the accept and cancel keys play GUI sound 0 and call `CloseInfoBox` (`0x0062d440`: pop, remove, input class 2 if `+0x984` is 1, else 0); a click on `BTN_OK` (`0x1f6`) takes the base close path instead, whose `OnClose` sets the caption back to 1580 "OK" for later uses (med, needs a runtime check) | high |

#### CSWGuiStatusSummary (`statussummary`)

0x1b44 bytes, ctor `0x006272a0`, vtable `0x0074ff68`, owner `CGuiInGame+0xa8`, 322x332 centred.
Rows (icon label + description label): `LBL_JOURNAL`, `LBL_CREDITS`, `LBL_XP`, `LBL_STEALTH`,
`LBL_DARKSIDE`, `LBL_LIGHTSIDE`, `LBL_RECEIVED`, `LBL_LOST` with `*_DESC`; `BTN_OK`. The code also
asks for `LBL_NETSHIFT`/`LBL_NETSHIFT_DESC`, which the file lacks. Data: flags `+0x64` (bit 0
pending, bit 2 item received, bit 3 item lost, bit 4 journal, bit 8 credit sign changed, bits 5..7
extra sounds 12/13/14), light/dark shift bytes `+0x68`/`+0x69`, credits `+0x6c`, XP `+0x70`,
stealth XP `+0x74`. `OnPanelAdded` (`0x00625c60`) plays the extra sounds, then walks nine rows
(0 journal, 1 credits, 2 XP, 3 stealth XP, 4 dark side, 5 light side, 6 net shift, 7 received,
8 lost) and lays out only the rows that have something, top to bottom from y = 10. Texts it sets
(custom token 0 is set to the number): credits 42437 "Credits Received: <CUSTOM0>" or, when
negative, 42627 "Credits Lost: <CUSTOM0>", prefixed by 47933 "Net Change: " when bit 8 is set (the
credits row also shows for bit 8 alone); XP 42438; stealth XP 42439 "Stealth XP Received:
<CUSTOM0>"; the net-shift row (both shift bytes non-zero and different) 47935 "Net Light Side
Shift" or 47934 "Net Dark Side Shift" with the matching icon; the other rows keep their `.gui`
text. Every shown row also flashes the matching HUD icon (`FlashHudIcon`), the dark and light
rows only when their side is the larger shift, the net-shift row never. It then clears the data,
centres the panel on the screen, asks for tutorial popup 14 and moves the cursor onto `BTN_OK`.
Accept/cancel keys (`0x00625ac0`) remove it, return to the game input class and unpause unless the
game was paused before (`+0x7c` bit 0, set by `FlushStatusSummary`); `BTN_OK` takes the same path
(`OnButtonAccept`, event 0x27). (high / med)

Layout (from the disassembly, high): a shown row's icon keeps its file x, width and height at the
running y (starting at 10); its description goes to the file x, y − 1, the running description width
(starting at 150) and the file height; while the description's text is not empty, needs more than one
line (text info slot +8 against `0x00414ee0`, the font's line height) and the width is below 440, the
width grows by 20 (so at most 450) and the extent is set again. The width carries on to the rows below.
y then grows by 37. At the end the panel is `LBL_JOURNAL_DESC.x + width + 10` wide and `y + 25` high,
centred on the screen, and `BTN_OK` is centred across it at y − 7. Hidden rows lose their visible bit.
The net-shift row's controls are not in `statussummary.gui` (`InitControl` 0x0040b930 adds a control to
the panel only when the file has its tag), so that row is an empty 37-pixel gap (med). The rows without
a number keep the file's strrefs: 42436 journal, 42440 dark side, 42441 light side, 42442 "Item(s)
Received", 42443 "Item(s) Lost". The last row's flash flag is always set when the walk ends, so tutorial
pop-up 14 is always offered. The pointer is moved onto `BTN_OK`'s centre (`SaveMousePosition` first).

When it shows (high): the client main loop (gameloop.md 1.2 step 22) waits while the data has bit 0 or 1
set, the input class is the game's (`+0x9c` 0), nothing loads (`+0x288`), no conversation is pending or
up (GUI `+0xb4`, `+0xb98`) and no fade runs (`GetIsFadePanelBusy`, `0x0062ded0`); any of those resets the
timer `+0x370`. The first good frame sets it to 0.25 s, later ones subtract frames shorter than 0.25 s,
and at zero `FlushStatusSummary` runs. So the panel comes up a quarter second after a conversation that
gave something ends, and events from scripts outside conversations show the same way.

Who adds events (callers of `AddStatusSummaryEvent`, high): GiveGoldToCreature (+n, n > 0, party creature
`+0xa88`), TakeGoldFromCreature (−n for the party creature taken from; the caller's gain is not told),
GiveXPToCreature (n > 0, party), CreateItemOnObject (7 when a party creature acquired it, credits
included), SetItemStackSize (7 when the stack grew, 8 when it shrank, whoever holds the item), the item's
DESTROY_OBJECT with event data 1 (only `DestroyObject` 0x0052ff20 sends 1; a used-up stack sends 0) for
an item a party creature holds (8), AIActionGiveItem (7 to a party recipient), AIActionTakeItem (8 from a
party holder), AdjustAlignment (the asked shift, before the 0..100 clamp, for a party creature),
GivePlotXP / GivePlotXPByRow and a DLG's journal XP (2), AwardStealthXP (3), pazaak's settlement
(`0x005f3950`: the gold change, 1), the client's journal notice (`0x00676c20`, on the message the
journal's state setter `0x005c5a40` sends unless loading: 0, then 10, or 11 when the entry has `End`),
the portraits (`0x00687860`: 9 when a member can level up and its client creature's `+0x440` bit 1 is
set, which its constructor and a finished level-up set) and `CSWGuiNotifyLabel::Update` (`0x00686a20`:
10 on the first update after any icon but the journal's (index `+0x148` non-zero) was flashed). So
loot, purchases, pick-ups and used-up items light no icon, and every icon but the journal's is followed
by gui_quest a quarter second later. `SuppressStatusSummaryEntry` (`0x00547e50` → `0x0062f0c0`) sets the
drop count (a negative count is ignored); a dropped event decrements it, the icon sound events included.

#### CSWGuiFade (`fade`)

0x1b8 bytes, ctor `0x00624810`, vtable `0x0074fc60`, owner `CGuiInGame+0x6c`. `fade.gui` is a
1600x1200 `blackfill` panel with `LBL_MSG`; the code forces the extent to the screen size and the
panel colour to the fade colour, so it is a full-screen coloured quad. `Start(bFadeIn, fWait,
fLength, color)` (`0x006244e0`) sets the colour and the starting alpha (1 for a fade-in, 0 for a
fade-out) and an elapsed time of 0.1 s. Render (`0x00624570`) advances the elapsed time in
whole milliseconds of the client interface clock (client `+0x2c`, which no pause stops;
gameloop.md 1.2 step 2); steps of 5 s or more are dropped. While `0x0062fad0` holds (the galaxy
map `+0x80`, party selection `+0x78`, store `+0x84` or top menu `+0x08` is shown and active, or a
pazaak game is running, client `+0x70`) Render returns at once: the fade is neither advanced nor
drawn, and the time that passes is lost. After `fWait` the alpha is (elapsed − wait) / length,
capped at 1 for a fade-out, inverted and floored at 0 for a fade-in. The panel ignores the mouse once its alpha is ≤ 0.001 (HitTest
`0x006246a0`), so a finished fade-out blocks clicks and a finished fade-in does not. `LBL_MSG`
text can be set from a strref (`0x006246c0`). (high)

#### Letterbox bars and conversation fade (`CGuiInGame+0x60`, `+0x64`, `+0x68`)

Three 0xa4-byte panels without a `.gui` (ctor `0x006a8930`, vtable `0x00755a78`; colour from
`0x00833910`, black): the top bar (`InitTopBar` `0x006a74b0`, mode 1: grows downward from height 0
at twice its full height per second), the bottom bar (`InitBottomBar` `0x006a7540`, mode 2: slides
up from the screen bottom; when it arrives `0x0062ab90` sets `CGuiInGame+0xbb4` and calls the
current conversation panel's slot 32), and a fade layer (mode 3, reset by `0x006a8a60` to alpha
0, started by `StartFade` `0x006a7620`, timed like the global fade). Each bar is
(screen height − screen width × 3/7) / 2 pixels high, i.e. the picture between them is 7:3,
whatever the conversation panel's layout. Render `0x006a7680` clamps the frame step to 0.5 s for
the bars; the fade layer drops steps of 5 s or more. `ShowConversationPanel` (`0x0062b730`) adds
the fade layer, then the top and bottom bars, only when the panel it shows is the cinematic
letterbox panel (`CGuiInGame+0x40`) and `0x0083390c` is 0 (no code writes it). Behaviour belongs to
[dialogue.md](dialogue.md). (high)

#### CSWGuiBarkBubble (`barkbubble`)

0x1cc bytes, ctor `0x006a9770`, vtable `0x00755c60`, owner `CGuiInGame+0x4c`; `LBL_BARKTEXT`
(`fnt_d16x16`, centred). `ShowBark(speaker, text, sound, flag)` (`0x006a9920`, four arguments,
called from four `CGuiInGame` functions): resolves TLK tokens with the player as the token
subject, sets the text, sets the box height to text height + 10 + 2 × border, the display time to
1 + 0.11 × (text length) seconds, keeps the speaker (`+0x1c0`) and flag bit 0 (`+0x1c8`), replaces
any previous voice and plays `sound` as a streaming sound (positional at the speaker unless the
speaker is OBJECT_INVALID; volume from the byte at `0x0074c5e8`), remembering whether it started
(`+0x1c4`). Render (`0x006a9ce0`): while the mini map is not shown (`0x0062f910`: option "Mini
Map", client options `+0x14` bit 3, off, or a minigame area, or the HUD's map hidden) it stretches
the box to the screen width minus 2 × 48 (`0x00409ee0`; 48 is also the design left edge); in
combat mode (client `+0x320`) it draws the box lower by the HUD's combat-bar height. The speaker
counts as lost when its object no longer exists or, unless flag bit 0, it is 6 m or more from the
party leader. While the voice plays the bubble stays (whatever the time left) unless the speaker
is lost; as soon as a voice that started is no longer playing it closes; with no voice it shows
while the time left is above 0 and the speaker is not lost. The time counts down only on frames
shorter than 1.5 s. Opening a menu suspends it (`0x006a9bb0`: pauses the voice and removes the
panel), closing resumes it (`0x006a9c10`: resumes the voice, re-adds the panel with flag 4), both
only while time or a voice remains; `ShowConversationPanel` ends it outright (`0x006a9c60`: voice
stopped, time 0, panel removed). Flow in [dialogue.md](dialogue.md). (high)

#### CSWGuiAreaTransition (`areatransition`)

0x438 bytes, ctor `0x006c7d50`, vtable `0x00757508`, owner `CGuiInGame+0x94`; 400x82 panel with
`LBL_TEXTBG`, `LBL_ICON`, `LBL_DESCRIPTION`; flags: bit 5 set, bit 6 cleared (`0x20`: shifted
horizontally by the 640x480 centring offset only). `SetTransitionObject(id, position)`
(`0x006c7ec0`) keeps the position and, when the id changes, takes the hovered door's or trigger's
name (object types 10 and 7) and keeps only what follows the first "-" and the character after it,
e.g. "Taris - Upper City" → "Upper City". Render (`0x006c8050`) puts its top at the bottom edge of
the bark bubble while one is shown (`0x0062ebe0`), else at its design y, and colours the frames and
text by whether every party member is within 30 m of the leader (`0x00635350`). Which door or
transition trigger it names is decided every frame by the objects themselves (door `0x00684660`,
trigger `0x006920b0`): one ahead of the player creature (along its facing, or the camera's heading
while in-game GUI `+0xc1c` is set) and within 8 m, the nearer one winning; the mouse pointer plays no
part (med: static reading, needs a runtime check). (high for the rest)

#### CSWGuiToolTip (`tooltipWxH`)

0x1a4 bytes, ctor `0x006277c0`, vtable `0x00750030`, owned by the manager (`+0x3c`). File by
resolution: `tooltip16X12` (1600 wide), `tooltip12X9` (1280x960), `tooltip12x10` (1280x1024),
`tooltip10X8` (1024), `tooltip8X6` (800), else `tooltip6X4` (a 1280 width with another height
loads none; at 1600 the fall-through load of `tooltip6X4` is a no-op because `LoadGui` runs only
once); one label `tooltip` (border `confirm5`/`confirm6`, fill `dialog3`, `dialogfont16x16`,
centred). Shown by `CSWGuiManager::ShowTooltip(text)` (`0x0040b490`) only when tooltips are not
suppressed (manager `+0x4c`, set by `ResetTooltipTimer` `0x0040b500` with a non-zero argument) and
the option "Enable Tooltips" (client options `+0x14` bit 10) is on: manager flag bit 3 set,
`SetText` (`0x00624ae0`), `PlaceAtCursor` (`0x00624af0`): width and height = text extent + 8
pixels, position = cursor + 15 pixels, pulled back inside the screen with a 2-pixel margin.
Sources: the hovered control after the manager's hover delay (`GetTooltipText` `0x00418a90`: TLK
strref `+0x24` or literal text `+0x28`, plus " : " and the bound key's name from the keymap
`KeyNameStrRef` column for key action `+0x30`; a control with neither asks its parent) and the
party buttons (`0x00686750`). (high)

#### CSWGuiSkillInfo (`skillinfo`) — skimmed

0x24e8 bytes, ctor `0x006ce7c0`, vtable `0x00757940`, owner `CGuiInGame+0x9c`, centred 333x231:
`LBL_MESSAGE`, `LB_SKILLS` (ten preallocated rows), `BTN_OK`. Accept/cancel keys play GUI sound 0
and mark it for removal (`0x006cd3c0`). What it lists was not traced. (`0x006ce370`, `0x006ce0f0` and `0x006ce570`, once noted here as
its fillers, build the chain rows below, not this panel.) (med)

#### Chain rows (feats and Force powers lists)

The feat and Force power lists show progression chains as rows of icons. Each row is a control of
its own (0x47c bytes, ctor `0x006cccc0`, vtable `0x007578a8`) handed to the list box with
`CSWGuiListBox::SetItems`, which replaces the file's `PROTOITEM` (ftchrgen's 245x56 border2/border1
row is never drawn). A row set (a growable array of row pointers plus the focused cell `+0xc` and
row `+0xd`) is built by:

- `0x006ce570` (feats panel, `0x006cda80` per row): chains by `prereqfeat1`/`prereqfeat2`
  (chargen.md H);
- `0x006ce370` (the in-game abilities screen, `CSWGuiAbilities::SetCreature`): the same sorted
  feats; every root the creature has (`HasFeatInLists`) starts a row, and its other cells are feats
  the creature has whose `prereqfeat1` is the root (without `prereqfeat2` in the second, with it in
  the third; the class-table test beside it is moot, as the feat must be known anyway); no pool
  test; then all cells style 6 (`0x006abce0`). (high)
- `0x006ce0f0` (Force powers panel and the abilities screen's powers, `0x006cd7e0` per row, icon
  `spells.2da` `iconresref`; second argument "every power"): chains by the spell's first force-AI
  code (`+0x12c`, count `+0x130`, getter `0x0059b6a0`). `CSWSpellArray::Load` (`0x0059ba20`)
  makes one code per filled column, in this order: `FORCEFRIENDLY` v gives (5v + 1500) * 2,
  `FORCEHOSTILE` (5v + 500) * 2, `FORCEPASSIVE` (5v + 1000) * 2, each plus `FORCEPRIORITY`. So
  code / 1000 is the kind (3 friendly, 1 hostile, 2 passive), (code mod 1000) / 10 the line
  (`0x00647510`) and code mod 10 the priority (`0x006474d0`), which is the cell: 0 starts a row,
  1 is the second cell, 2 the third (the last match wins until both are found). A spell with no
  code reads as -1, unsigned: tier 5. The sort (`0x006cd590`) is an insertion over the spell ids
  of those with `UserType` (`+0x140`) 1 and a name (`+8`): a spell goes before the first one
  already placed with a higher tier, or the same tier and a **lower** kind, or the same tier and
  kind and a higher line; so tier, then friendly, passive, hostile, then line, then id. The roots
  are the tier-0 prefix; the scan stops at the first spell that is not. With "every power" set
  (the level-up panel, from its ctor `0x006f2180`) every root and cell counts; without it (the
  abilities screen, `0x006abce0`) a root needs `0x005a6e70`(stats, 0, spell, 0) and a second or
  third cell `0x005a6e70`(stats, 0, spell, 1). `0x005a6e70` looks for the spell in every class
  slot's known-power list; with its last argument set it also wants the Force point cost
  (`CSWSpell::GetForcePointCost`) not above the current Force points (stats `+0x124` + `+0x126`).
  So the abilities screen leaves a known upgrade out of its root's row while the character cannot
  pay for it (the push of 1 is in the code, `0x006ce21f`). (high)

The row's makers set three cells (feat or spell id, -1 empty; icon resref, empty for an empty cell)
and the extent (0, 0, 242, 40); the list box then lays it out like any row, padding in from the left
and its own width less twice the padding, the height stretched like a prototype row.

Each cell (0x128 bytes at `+0x5c`) is a border (`+0`, corners `border2d`, edges `border1d`, no
DIMENSION, so the textures' sizes), the icon image (`+0x74`, DRAWSTYLE 1, centred), a backing image
(`+0xc8`, `lbl_indent`), the id (`+0x11c`), the style (`+0x120`) and a hilight bit (`+0x124` bit 0).
Two arrow images (`lbl_skarr`) follow at `+0x3d4`.

- **Layout** (SetExtent `0x006cce30`, row extent x, y, w, h): cells are h by h at x, x + (w - h) / 2
  and x + w - h; the icon fills the border's text rectangle; the arrows are 32x32, vertically
  centred, at x + (w + h) / 4 - 16 and x + (3w - h) / 4 - 16 (centred in each gap).
- **Draw** (`0x006ccc40`): for each filled cell the backing, the icon, the frame; then each arrow
  whose following cell is filled. Hilight and hit test are the base control's, so a row shows no
  hover; the list's selection shows only through the focused cell.
- **Styles** (`0x006ccfd0`; all four alphas start at 1 and the frame pulses, `SetPulsing(1,1)`,
  while the cell has the focus): 0 icon 0.25, frame hidden unless focused, then in the menu hilight
  text colour; 1 and 2 green (0.28, 0.92, 0.11) frame at 0.5 (1 when focused); 3 icon and backing
  0.25, arrow into the cell 0, frame hidden unless focused, then red-orange (0.74, 0.11, 0);
  4 green frame; 5 as 0 but icon 1 and the arrow into it 0.25; 6 as 0 but icon 1.
- **Focus** (`0x006cdc00` by id, `0x006cdd10` first cell, `0x006cdd80` arrows, `0x006cd1c0` hit
  test): chargen.md H. The three panels that hold row sets (feats `0x006f4680`, powers `0x006f28c0`,
  abilities `0x006ae5f0` on its Powers and Feats tabs) send the arrows (0x2f-0x32, 0x3d-0x40) to the
  row set whichever control has the focus, then on to the base handler. (high)

Ours: `lib/gui/cells.ctx` (a list box with `cell_art.on`; a panel's shown cell list takes the
arrows, but the base handling after it is not repeated); `chargen/feat_cells.ctx` builds the feat
rows for both feats steps and the abilities screen, `chargen/power_cells.ctx` the power rows for
the level-up powers step and the abilities screen.

#### CSWGuiPause (`pause`)

0x4b0 bytes, ctor `0x006c03b0`, vtable `0x00756dc8`, owner `CGuiInGame+0x7c`; 251x70 panel:
`LBL_PAUSEREASON`, `LBL_PRESS` (strref 48384 "PRESS THE PAUSE BUTTON TO CONTINUE", token-parsed at
construction), `BTN_UNPAUSE` (a button covering the banner; clicking it toggles the player pause,
client reason 4, and clears an auto-pause, `0x006c0350`). `SetReason(n)` (`0x006c00c0`) picks the text: 1 → 48212 "ENEMY SIGHTED! ..." and 11 →
49118 "MINE SIGHTED! ..." (both without `LBL_PRESS`), 5 → 42432 "End of Combat Round", 7 → 42482
"Menu Used", 8 → 42481 "Target Changed", 9 → 42397 "Party Member Down", 10 → 48423 "Action added to
queue.", anything else → 1508 "PAUSED"; the panel's height is refitted to the texts. OnPanelAdded
(`0x006c02f0`) centres it on the screen in a minigame area (area `+0x264`, via `0x005edb00`),
otherwise the HUD places it (`0x0062b100` → `0x00688db0`). Added with flag 4 by `SetPauseState`,
`SetHudMode` and `HideInGameMenu`. (high)

#### Debug panels (`debug`) — skimmed

Four panels on `debug.gui` (`LBL_BUILD` "Build: ...", `LB_OPTIONS`) at `CGuiInGame+0x58`
(`0x006d0620`, lists `baseitems` labels: an item spawner), `+0x70` (`0x006cfa70`, lists modules
from `MODULES:` and `live%d` / `_s.rim` names: a warp list), `+0x74` (`0x006cf5a0`) and `+0x5c`
(`0x006bdc60`); `CloseDebugPanel` (`0x0062d360`) closes the `+0x5c` one (back to input class 0, 1 in
a minigame area). Developer tools; not needed for the game. (med)

### 10.4 The in-game menus

#### Conventions shared by the in-game menu panels

These apply to every panel in this group; the per-panel sections only list what differs.

**Owner and lifetime.** All of them except the upgrade bench, quest items and script select are
built once by `CGuiInGame::CreatePanels` (0x00632860) and kept in the in-game GUI object
(`CGuiInGame`, `CClientExoApp::GetInGameGui` 0x005ed690). Fields: +0x0c equipment, +0x10
inventory, +0x14 character, +0x18 abilities, +0x1c messages, +0x20 journal, +0x24 map, +0x28
in-game options, +0x54 container, +0x78 party selection, +0x80 galaxy map, +0x84 store (high,
read in CreatePanels). The eight menu panels at +0x0c..+0x28 are the ones the HUD's menu buttons
and the top bar switch between (see the HUD / top-bar section); quest items is owned by the journal (+0xfb4), script select by the
character sheet (+0x59f4), the upgrade panels by the item-select panel (below). (high)

**Buttons forward to the panel's own input handler.** Most buttons do not get a dedicated
callback; they get one of five tiny shared callbacks that re-send a gamepad-style event to the
panel's `HandleInputEvent` slot (vtable +0x3c) through the panel slots 20..24 (`CSWGuiPanel`
0x0040b640..0x0040b680, each `HandleInputEvent(code, 1)`):

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
(returns 0) when no menu is open (+0x108 = 0) or any modal panel is up (manager +0x98), sets HUD
mode 4, removes the menu bar (+0x08) and the current menu panel (`SwapMenuPanel(current, -1)`),
then, if the player had not paused the game before (+0xb38 = 0), toggles the pause off again,
otherwise re-adds the pause banner (+0x7c) if it is not up; it resumes the bark bubble, plays GUI
sound 5, sets sound mode 0, and returns 1. The caller then puts the client back into input class
0 (game) with `CClientExoApp::SetInputClass` (0x005eda60 → 0x006200e0). Which keys produce
0x2e/0xdf is not traced (likely Esc and the menu's own toggle key). (high for the sequence, med
for the keys)

**Closing a popup panel** (quest items, script select, upgrade item list): `PopModalPanel` and
`CSWGuiPanel::MarkForRemoval` (0x00624a00), which sets panel flag 0x200 (or keeps 0x400) so the
manager removes it after drawing, flag bit 8 from the argument. (high)

**Scrolling the description box.** Events 0x39/0x3a are turned into 0x31/0x32 and sent to the
panel's description list box (inventory, equipment, abilities, store, upgrade, quest items, the
message box), so the description scrolls while the item list keeps the focus. 0x39/0x3a come only
from a gamepad's second stick (analog axes 0x37/0x38, §7); the PC key map never makes them, so on
PC the arrow keys move the focused list, and the description scrolls with the wheel, its scroll bar,
or the arrow keys while the pointer is over it (hover is focus). (high)

**Message boxes.** Refusals ("you cannot ...") all use the shared message box at `CGuiInGame`
+0x98: `CSWGuiMessageBox::SetConfirmMode(0)` (0x00627130, sets +0x64 bit1 and the open sound +0x60
to 2 or 0xf), the text slot (vtable +0x6c) with a strref, `CSWGuiMessageBox::SetCallback(owner,
fn, data)` (0x00624a40, stores +0x6c/+0x68/+0x70), then `AddPanel(box, 1, 1)` (modal). (high)

**Tutorial pop-ups.** Opening or using a panel calls `CClientExoApp::ShowTutorialPopup(id, ...)`
(0x005edf40 → 0x005f4120): `CGuiInGame::CanShowTutorial` (0x0062f420) passes when the "Tutorial
Popups" option (client options +0x14 bit1) is on, the id's bit in the shown-set at `CGuiInGame`
+0xba8 is clear (only ids below 0x2b are looked up there), `CGuiInGame` +0xb4 is 0 and
`tutorial.2da` has a `Message0` entry for the id (0x006aa1a0); then the id goes to the tutorial
panel (`CGuiInGame` +0xa0, 0x006aa900) and, if that accepts it, the arguments are stored (client
internal +0x3ac..+0x3b8) and it returns 1. Ids seen here: 0x14 inventory opened, 0x0b equipment
slot opened, 0x0d map opened, 0x27 return-to-base pressed. (high)

**Switching character (BTN_CHANGE1, BTN_CHANGE2, key event 0xce).** Inventory, equipment,
character sheet and abilities share one scheme:

- The two buttons show the portraits (creature vtable +0x148) of party members 1 and 2 of the
  client party list (the list from 0x005ed8b0, member n via 0x006346c0); a button is hidden (flag
  bit1 cleared) when that member does not exist. Both get tooltip strref 38693 "Change Character"
  (control +0x24); BTN_CHANGE1 also gets input event 0xce (+0x30) so the tooltip names the key
  bound to it. (high)
- Clicking BTN_CHANGE1 cycles the party leader one step, BTN_CHANGE2 two steps
  (`CClientExoApp::CyclePartyLeader(0, 0, n)` 0x005edf80 → 0x005f7960, which skips dead or dying
  members and returns 0 when the leader did not change); only on success does the panel play GUI
  sound 1, re-read the leader and refresh. Event 0xce plays sound 1, cycles one step and refreshes
  whatever the result. (high)
- When a server-side flag is set (server internal +0x10004 object, +0x104 bit0, read through
  0x004aec90; meaning not established, plausibly the player-restrict / "view only" mode), the
  buttons instead show *other* characters to view, without changing the leader: each change
  button holds a party-table index (button +0x58; 0xff the player, 0xfe none), filled by the
  panel's `UpdatePartyButtons` with the next two available characters after the viewed one
  among the nine NPC slots of the party table (`CServerExoApp::GetPartyTable` 0x004aee70 =
  server internal +0x1b770; `CSWPartyTable::IsNPCAvailable` 0x005636b0; creature from
  `GetNPCObject` 0x00564700) and the player, and clicking one makes that character the viewed one.
  BTN_CHARLEFT/BTN_CHARRIGHT (shown only when more than two NPCs are available,
  `GetNumAvailableNPCs`) shift that window backwards/forwards. The panel remembers the viewed
  index (0xff = the player). Equipment implements this (character sheet and abilities bind the
  arrows and test the same flag in their `UpdatePartyButtons` / `OnChangeCharacter`); the
  inventory does not (its `UpdatePartyButtons` always shows party members 1 and 2, its arrows are
  never bound and its buttons' stored index stays 0xfe, so a click finds no creature and only
  rebuilds; its 0xce always cycles the leader). (high for the code, med for the flag's meaning)

**Item rows.** Inventory, equipment, container and quest items fill their list boxes with a
shared row control, `CSWGuiItemEntry` (ours; 0x39c bytes, ctor 0x006b7ee0, vtable 0x007568f8, a
button with an extra icon border, stack-count text and state). `CSWGuiItemEntry::SetItem(id,
bEquipped, bNew)` (0x006b6710) fills it (high):

- item id at +0x1c4, flags at +0x394 (bit1 equipped, bit2 new);
- name = the item's localized name (item +0x280), with " (Equipped)" (strref 32346) appended
  when equipped. The **text colour is not touched** (it is the prototype's blue, and a button's
  yellow pulse under the pointer). What `SetItem` sets is the colour of the row's four frames, the
  `BORDER` colour (entry +0x90..0x98), the `HILIGHT` colour (+0x104..0x10c) and the same two of
  the icon's hexagon frame (+0x1ec, +0x260): menu blue (0x007a23b4, 0.0/0.66/0.98) and yellow
  (0x007a23c0, 0.98/1.0/0.0) normally, or magenta (0.95/0.0/0.85, 0x007a23fc) for all four for a
  *new* item, whose `BORDER` alpha (+0x8c) and hexagon alpha (+0x1e8) it also sets to 0.5.
  `FUN_006b5060(row, state)` repaints them after `SetItem` for the equipment list: state 0 or 1
  as normal, state 2 or 3 red-orange (0x007a23d8, 0.74/0.11/0.0) for all four, sets the
  hilight frames pulsing while the row is hilighted (+0x394 bit0) and stores the state at +0x398.
  The new flag is the argument the caller passes: the inventory passes bit 7 of the item's flags,
  the container (0x006b8130, 0x006b8410), the equipment list (0x006b9470) and the quest items
  (0x006d29f0) pass 0;
- icon = the item's icon resref (`CSWSItem::GetIconResRef` 0x005556b0) drawn inside a hexagon
  frame: `lbl_hex_3` for a single item, `lbl_hex_6` for stacks of 2..99, `lbl_hex_7` for 100 and
  more; the stack size (item +0x28c) is printed with font `fnt_d16x16`, alignment 0x22
  (bottom centre) when the stack is 2 or more;
- an empty row (id `OBJECT_INVALID`, or an id that no longer resolves to an item) reads "None"
  (strref 363) with icon `inone`.

Layout and drawing (high). The entry is a button with three extra borders and a text: +0x1c8 the
hexagon frame, +0x23c the hilighted hexagon frame, +0x2b0 the icon, +0x324 the stack count. Each
"frame" is a border with no corner or edge texture, only a fill, so it fills the border's whole
extent:

- Vtable slot 40 (0x006b4db0, `Init(protoText, protoBorder, protoHilight, width, pulse)`, called by
  every maker right after the ctor) copies the prototype's text and its `BORDER` / `HILIGHT`
  frames, recolours them (above), makes the two hexagon borders (fill `lbl_hex_3`, fill style 0,
  menu blue and yellow, the hilighted one with a pulsing fill), and sets the extent to
  (0, 0, `width`, **56**). Callers pass the list box's width less twice its padding. The
  prototype's own height (50 in `inventory.gui`) is never used.
- Slot 1 `SetExtent` (0x006b5270) does nothing unless the width is over 56. It keeps the given
  rectangle as the control's (the list box's layout and hit test use it), then places the parts
  using a fixed height of 56, whatever height it was given:
  - the hexagon, hilighted hexagon and icon borders: (x, y, 56, 56), the square at the left;
  - the stack count text: (x + 56 − w, y + 37, w, 19), with w = 21 when the count string has at
    most two characters and 42 otherwise. That puts it in the square's bottom right corner;
  - the button's `BORDER` and `HILIGHT`: (x + 56, y, width − 56, 56), the rest of the row;
  - the name text: the frames' inner text rectangle (their `GetTextRect`, combined by 0x0040a4a0),
    so the name sits right of the square.
- Slot 14 `Render` (0x006b4d40): when the entry is hilighted (+0x44 bit 0), the `HILIGHT` frame and
  the hilighted hexagon; otherwise the `BORDER` frame and the normal hexagon. Then the icon, the
  name and the count.
- `SetItem` puts the icon resref in the icon border's fill and sets that fill's style to 2,
  **stretched** (+0x2e0 = (… & ~1) | 2). The icon therefore always covers the 56x56 square,
  whatever its own size. Item icons (`iw*`, `ia*`, `ii*`) are 64x64, as are `inone` and every
  `lbl_hex*`. The hexagon keeps fill style 0 (tiled), but a 64-pixel texture on a 56-pixel area
  is one stretched tile, so it covers the square too.
- The count text is font `fnt_d16x16` in menu blue (`g_vGuiMenuTextColor`), alignment 0x22 (bottom
  centre), scale 1. Its string is the stack size when that is 2 or more, else empty.
- The list box's row height is its tallest row's (`UpdateLayout`), so item lists step by 56 plus
  padding. The list's leftover height is spread over the slots as for any list. The entry still
  draws everything 56 high, at the top of its slot.

Two copies of the entry share `SetExtent` and `Render` and paint alike (menu blue and yellow
frames, the `lbl_hex_3/6/7` hexagon, the stretched icon, the `fnt_d16x16` count): the store's row
(0x394 bytes, ctor 0x006b71e0, vtable 0x00756850, `Init` 0x006b53f0, `SetItem` 0x006b7270), and the
upgrade bench's (ctor 0x006c3e00, vtable 0x00757108, `SetExtent` 0x006c2650, `Init` 0x006c2830,
`SetItem` 0x006c3ea0). The bench's own `SetExtent` gives the count text the whole square's height
(y, 56) instead of (y + 37, 19), which looks the same with bottom alignment. The feat and power
chain rows (0x006cccc0) and the abilities screen's skill rows are other controls (see "Chain
rows").

The GUI is never scaled (§2). The entry's 56-pixel square and its icon are the same size in
screen pixels at every resolution. A reimplementation that scales the whole GUI must scale these
rows along with everything else.

#### CSWGuiInventory (inventory.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006b34c0 | `CSWGuiInventory::CSWGuiInventory` | 0x1de8 bytes; loads `inventory`, binds the controls below | high |
| 0x007564e0 | `CSWGuiInventory::vftable` | slots 13 Render, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x006b4c30 | `CSWGuiInventory::OnPanelAdded` | reset viewed character, refresh party buttons, rebuild the list, tutorial 0x14 | high |
| 0x006b4bb0 | `CSWGuiInventory::Render` | rebuild if dirty (+0x1de4 bit0), refresh stats, colour BTN_USEITEM (menu blue when the hilighted row is usable and the player creature's item cooldown +0xab0 is 0, else dim blue 0x007a2408), draw | high |
| 0x006b3ed0 | `CSWGuiInventory::HandleInputEvent` | events below | high |
| 0x006b4430 | `CSWGuiInventory::OnPanelRemoved` | frees rows, clears the "new" flag of the items seen | high |
| 0x006b4810 | `CSWGuiInventory::RebuildItemList` | builds LB_ITEMS | high |
| 0x006b2c90 | `CSWGuiInventory::PassesFilter` | the six filters | high |
| 0x006b44d0 | `CSWGuiInventory::AddItemRow` | makes or reuses a row and picks its click callback | high |
| 0x006b2a80 | `CSWGuiInventory::CycleFilter` | next filter, relabel title and button | high |
| 0x006b28c0 | `CSWGuiInventory::UpdateStats` | portrait, vitality, defense of the viewed character | high |
| 0x006b2dc0 | `CSWGuiInventory::UpdatePartyButtons` | BTN_CHANGE1/2 portraits and visibility | high |
| 0x006b2ec0 | `CSWGuiInventory::OnChangeCharacter` | BTN_CHANGE1/2 | high |
| 0x006b3d10 | `CSWGuiInventory::OnItemHilighted` | row event 0: description into LB_DESCRIPTION | high |
| 0x006b25e0 | `CSWGuiInventory::OnUseItem` | row event 0x27 for usable items | high |
| 0x006b26e0 / 0x006b2740 | `OnEquippableItemClicked` / `OnUnusableItemClicked` | refusal messages | high |
| 0x006b2800 / 0x006b2860 / 0x006b27a0 | `OnMedpacFullHealth` / `OnSquadMedpacNoInjured` / `OnItemClickedViewOnly` | refusal messages | high |
| 0x006b2fd0 / 0x006b3250 | `OnPreviousCharacter` / `OnNextCharacter` | handlers on two buttons that are never bound to the .gui (see below) | high |

Controls (tags checked against `inventory.gui` and the patch.erf version):

| Tag | Type | Role |
|---|---|---|
| `LB_ITEMS` | list | the items; initial keyboard focus |
| `LB_DESCRIPTION` | list | description of the hilighted item (one wrapped label row) |
| `LBL_INV` | label | title: "Party Inventory - <filter>" (32171, " - ", filter name) |
| `LBL_CREDITS`, `LBL_CREDITS_VALUE` | labels | party credits (`CSWSCreature::GetGold` 0x004edd60 of the viewed character's server creature) |
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
item repository (`CSWSCreature::GetItemRepository(1)` 0x004ef770: for a party member the party
table's shared inventory, `CSWPartyTable::GetPartyInventory` 0x00563340). Items with flag +0x288
bit8 (0x100, the item is being destroyed; party-items-saves.md 5.10) are skipped; every item must
pass the current filter. Rows are reused between rebuilds (array at +0x1dc0). Selection: right
after a use (+0x1de4 bit1, set by `OnUseItem`) the saved scroll top and selected index
(+0x1ddc/+0x1dde, clamped to the new list) are restored; otherwise the row holding item +0x1dd8
is selected if it is listed, else row 0 (+0x1dd8 is only set together with bit1, so a plain
rebuild selects row 0). With no items the selection is -1, the description is cleared and the
use button greyed. (high)

**Row click (0x27 on a row or BTN_USEITEM)** — the callback chosen when the row is built:

1. View-only mode while an NPC is viewed (flag set and viewed index not 0xff): message (strref
   49145, empty in this TLK). (high)
2. The creature cannot use the item (0x00616520 fails; it also refuses non-plot items while the
   area's RestrictMode, server area +0x2b0, is set): "You cannot equip items from the INVENTORY
   screen..." (42485) if it has equipable slots, else "This is not a useable or equipable item."
   (42486). (high)
3. Medical items (base item `itemtype` 45, medpacs) and droid repair kits (26) when the viewed
   creature is at full vitality and not poisoned (server creature +0x9e0): "This character does
   not need to use a medical pack..." (42499). (high)
4. Squad recovery kits (`itemtype` 47) when none of the viewed creature and client party members
   1 and 2 is below full vitality: (48494). (high)
5. Otherwise `OnUseItem`, with one exception: a full-vitality *poisoned* creature's medpac row and
   the squad-kit row *with* someone injured get no new 0x27 handler at all (both branches jump past
   the `SetEventHandler`, 0x006b4650 / 0x006b4725), so a freshly made row ignores the click and a
   reused row keeps the previous item's handler. (high for the code, med for the effect; needs a
   runtime check)

`OnUseItem`: if the *player* creature (`GetPlayerCreatureId`) is in combat mode (+0x4e0), combat
reason +0xac0 == 1 and its item cooldown +0xab0 is still running → "can only use one item per
round" (42409); else clear creature +0x1cc and call 0x004efe30 (creature, item id), which uses the
item at once, without an action: it casts the spell of the item's first CastSpell property
(type 10) with `CSWSObject::SpellCastAndImpact`, spends the use (`CSWSItem::ConsumePropertyUse`,
party-items-saves.md 5.10) and, in combat mode, starts the 3000 ms cooldown +0xab0. The panel then
marks the list dirty and saves the item id, scroll top and selected index for re-selection. (high)

**Hilight** of a row shows the item's description (`CSWSItem::GetDescription` 0x0055f340) in
LB_DESCRIPTION, records whether it is usable (row +0x58, set to 1 only for `OnUseItem` rows;
always 0 in view-only mode) in +0x1de4 bit2 for the button colour, and, if the item is new, adds
its id to the seen list (+0x1dcc). `OnPanelRemoved` passes that list to
`CItemRepository::ClearNewFlags` (0x00556050) on the party inventory, which clears bit7 of each
listed item's flags. (high)

No drag and drop: the inventory never uses the manager's dragged-object slot (only the pazaak card
control sets it, render-gui.md). (high)

#### CSWGuiEquip (equip.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006ba980 | `CSWGuiEquip::CSWGuiEquip` | 0x42bc bytes; loads `equip` | high |
| 0x007569a0 | `CSWGuiEquip::vftable` | 13 Render, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x00756560 | `g_aEquipSlots` | 9 records of 5 dwords: slot mask, tag suffix, empty-slot icon suffix, slot-name strref (human), slot-name strref (droid) | high |
| 0x006bb530 | `CSWGuiEquip::OnPanelAdded` | viewed index = 0xff, viewed creature = leader, party buttons, build the hovered slot's list | high |
| 0x006bb510 | `CSWGuiEquip::Render` | `UpdateStats` then draw | high |
| 0x006b9970 | `CSWGuiEquip::UpdateStats` | slot icons, damage/attack/defense/vitality labels, every frame | high |
| 0x006ba3f0 | `CSWGuiEquip::HandleInputEvent` | events below | high |
| 0x006b8e10 | `CSWGuiEquip::OnPanelRemoved` | `EndSelection` if in selection mode (without restoring the originals), frees rows, clears the pending-slot fields +0x42a4/+0x42a8 | high |
| 0x006b9470 | `CSWGuiEquip::OnSlotHilighted` | slot event 0: builds LB_ITEMS for that slot, sets LBL_SLOTNAME | high |
| 0x006b8eb0 | `CSWGuiEquip::OnSlotClicked` | slot event 0x27: enter selection mode | high |
| 0x006b7680 | `CSWGuiEquip::SetSelectionMode` | shows/hides the slot buttons and labels, LB_DESC, BTN_EQUIP, the row frames; BTN_BACK caption | high |
| 0x006b7920 | `CSWGuiEquip::OnRowHilighted` | previews the hovered item by equipping it | high |
| 0x006b9160 | `CSWGuiEquip::OnEquip` | BTN_EQUIP and row 0x27: keep the previewed item | high |
| 0x006b7e30 | `CSWGuiEquip::EndSelection` | back to the slot view | high |
| 0x006b5760 | `CSWGuiEquip::EquipItem` | queue equip actions on the server creature | high |
| 0x006b5910 | `CSWGuiEquip::UnequipItem` | queue unequip actions | high |
| 0x006b5890 | `CSWGuiEquip::EquipMatchingItem` | find an inventory item equal to a saved copy (`CSWSItem::CompareItem`) and equip it | high |
| 0x006b91c0 | `CSWGuiEquip::GetRow` | row n of LB_ITEMS, created on demand | high |
| 0x006b7590 | `CSWGuiEquip::SetCreature` | viewed creature, empty-slot icons, LBL_PORTRAIT | high |
| 0x006b5b60 | `CSWGuiEquip::UpdatePartyButtons` | BTN_CHANGE1/2, BTN_CHARLEFT/RIGHT; argument 0 hides all four | high |
| 0x006ba820 | `CSWGuiEquip::OnChangeCharacter` | BTN_CHANGE1/2 | high |
| 0x006b60f0 / 0x006b6370 | `OnPreviousCharacter` / `OnNextCharacter` | BTN_CHARLEFT / BTN_CHARRIGHT (view-only cycling) | high |

Controls: `BTN_INV_<slot>` and `LBL_INV_<slot>` for the nine slots (`WEAP_L`, `WEAP_R`, `HEAD`,
`ARM_L`, `ARM_R`, `BODY`, `HANDS`, `IMPLANT`, `BELT`; the slot icon is the `LBL_INV_` label's fill,
and `BTN_INV_BODY` has the initial keyboard focus), `LB_ITEMS` (candidate items), `LB_DESC`
(item description), `LBL_PORTRAIT`/`LBL_PORT_BORD`, `LBL_VITALITY`, `LBL_DEF`, `LBL_ATKL`/
`LBL_ATKR` (damage range per hand), `LBL_TOHITL`/`LBL_TOHITR` (attack bonus per hand),
`LBL_ATTACK_INFO`, `LBL_DEF_INFO` (icons `lbl_eq_attack` / `lbl_eq_hlth`), `LBL_TOHIT` ("To
Hit", 31386), `LBL_DAMAGE` ("Damage", 31385) (captions), `LBL_SLOTNAME` (hovered slot),
`LBL_TITLE`, `LBL_SELECTTITLE`, `LBL_TXTBAR`, `LBL_CANTEQUIP`, `BTN_EQUIP`, `BTN_BACK`,
`BTN_CHANGE1`/`2`, `BTN_CHARLEFT`/`RIGHT` (patch.erf version only; the code binds them). (high)

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

Empty-slot icons are `i` + suffix, or `id` + suffix when the viewed creature's race (client
stats +0x24) is 5, droid (`GetEmptySlotIcon` 0x006b5600 formats `"i%s%s"`; both sets exist in
`swpc_tex_gui.erf`); a filled slot shows the item's icon. The slot name in LBL_SLOTNAME takes the
droid column under the same race test. (high)

**Slot view.** Hovering a slot button (event 0) builds LB_ITEMS for that slot so the player sees
what could go there before clicking. The list is only a preview then: the constructor and
`EndSelection` clear the list box's selectable flag 0x08 (`SetSelectable`, vtable +0x88; the hit
test and the keys pass a non-selectable control by), `SetSelectionMode(0)` (0x006b7680, called by
the constructor and `EndSelection`) sets the `BORDER` alpha (+0x8c) of every row to 0, and `GetRow`
(0x006b91c0) gives every row it hands out the same 0, so the rows show their pictures and names
without the frame and cannot be hilighted or clicked (`OnRowHilighted` also un-hilights a row at
once while LB_DESC is hidden). `SetSelectionMode(b)` first clears any "cannot equip" message
(`FUN_006b59f0(0)`) and calls `UpdatePartyButtons(!b)`; with 0 it shows the nine slot buttons and
labels, LBL_PORTRAIT, LBL_PORT_BORD, LBL_TXTBAR and LBL_SLOTNAME, hides LB_DESC and BTN_EQUIP and
sets BTN_BACK to "Close" (1582); with 1 it does the opposite (BTN_BACK "Cancel", 1581), sets the
row alpha to 1.0, and hides the four party buttons. The list is: row 0 "None" (unequip, state 0),
row 1 the equipped item (if any, state 1; the panel caches each slot's item id at +0x427c), then
every item of the creature's item repository (the party inventory for party members) whose base
item's equipable slots include the slot mask and whose `droidorhuman` column (base item +0xb4)
fits the creature (0 anyone; 1 only when the creature's race, server stats +0xdc, is 6; 2 only
when it is 5). For the left weapon slot while the right hand holds an item of weapon size (base
item +0x1b) 4, no inventory items are listed at all. Each candidate is tested with the server's
can-equip check (`CSWSCreature::CanEquipItem(item, &slot, 0, 0, 0)` 0x0051aa60,
party-items-saves.md 4.3); a failure marks the row state 2 (cannot equip). With the "Hide
Unequippable" option (client options +0x14 bit0) items failing it (or `CheckProficiencies`
0x00510e30, which it already includes) are left out. Weapon pairing (state 3, text strref 42271):
a candidate for the right slot is checked against the item in the left hand and a candidate for
the left slot against the item in the right hand; when that other hand holds an item, the two
base items' wield types (+8) must be equal and 2 (one-handed melee) or 4 (pistol), else the row
gets state 3, except that a right-slot candidate of weapon size 4 is never marked. The state is
fixed when the list is built, and state 3 overrides state 2. The list box is only refilled (and
scrolled to the top) when a row changed or the row count differs. (high)

**Selection mode.** Clicking a slot (0x27):
- any slot while the area's RestrictMode (server area +0x2b0, the area of the viewed creature) is
  set: a message box with strref 0 (empty text);
- body armour while in combat (creature +0x4e0 == 1 and +0xac0 == 1): "You cannot equip or unequip
  armor during combat!" (1506);
- left weapon slot while the right hand holds a two-handed weapon (base item +0x1b == 4):
  strref 42344;
- no candidates: "You have no items that can be equipped in this slot." (42345);
- the refusals test the list as built: a list of one row (only "None") is "no candidates";
- otherwise remember the clicked slot button (+0x42a0), `SetSelectionMode(1)`, give LB_ITEMS the
  keyboard focus (panel vtable +8), select the equipped row if there is one
  (`SetSelectedIndex(1, no sound)`; with a bare slot nothing is selected and no description is
  set), set the mode flag (+0x4270 bit 0), LBL_SELECTTITLE "Select Item to Equip" (38154),
  tutorial 0x0b, and make LB_ITEMS selectable. (high)

While in selection mode, **hovering a row really equips that item** (`OnRowHilighted`). Every
hover shows the item's description in LB_DESC ("No Description Set", 32172, when the item is gone
and no saved copy describes it) and, while the list is selectable, plays GUI sound 0. For a row of
state 0 or 1 whose item is not already in the slot: the first time, the originally equipped item's
id and a detached copy are saved (+0x42ac/+0x42b0, copy made by 0x006b65e0); then the hovered item
is equipped (`EquipItem`, GUI sound 0xa) or, for "None", the slot emptied (`UnequipItem`, sound
0xb), so the stat labels update live. If the hovered item's object no longer exists but it is the
saved original, `EquipMatchingItem` puts on an inventory item equal to the copy. Right weapon slot
specials: hovering "None" also saves (+0x42b4/+0x42b8) and unequips the left weapon; hovering a
candidate of weapon size 4 saves the left weapon (the GUI does not unequip it itself; the equip
action handles the displaced weapon, party-items-saves.md); hovering a smaller
right-hand item afterwards puts the saved left weapon back. The slot and hovered id are kept at
+0x42a4/+0x42a8 for `UpdateStats` (below). A row of state 2 or 3 puts nothing on and does not undo
what an earlier row put on: it shows its reason in the numbers' place (`FUN_006b59f0(1, 38450 or
42271)` hides the ten stat controls including the two icons, shows LBL_CANTEQUIP with that text,
dims BTN_EQUIP (0x007a2408) and makes it unselectable). `OnEquip` (BTN_EQUIP or clicking a row,
whatever its state) drops the saved originals, keeps the result and leaves the mode. Cancel
(0x28/0x2e/0xdf in the mode) plays sound 0, re-equips the saved originals (the slot's original
item, or empties the slot if it was empty, then, for the right slot, the saved left weapon) and
leaves the mode; outside
the mode those keys close the menu (0x2d, the menu key, only outside; 0xce, change character, only
outside; up/down scroll LB_DESC only inside). `EndSelection` (0x006b7e30) is `SetSelectionMode(0)`,
clear the flag, make the clicked slot button the active control (so it is hilighted),
`OnSlotHilighted` to rebuild the list, clear LBL_SELECTTITLE, make the list unselectable. (high)

Removing the panel by another route while in selection mode (`OnPanelRemoved`) only calls
`EndSelection`: the previewed item stays on and the saved original (+0x42ac/+0x42b0) is not
cleared, so a later preview starts from that stale original. (med, static reading; needs a
runtime check)

`EquipItem(id, slot, bClear)` checks the item object exists and its base item fits the slot,
then, when bClear is set, clears the creature's action queue (`CSWSObject::ClearAllActions`) and
its combat round's scheduled actions (`CSWSCombatRound::ClearScheduledActions` on +0x9c8), calls
`CSWSCreature::AddEquipItemActions`, and, if the creature is in combat mode (+0x4e0) and its combat
round has a target (+0x9c8 → +0x9cc), re-queues `CSWSCreature::AddAttackActions` on it.
`UnequipItem` does the same with `CSWSCreature::AddUnequipActions`. Equip rules and the action
itself: party-items-saves.md and actions.md. (high)

**Stats** (`UpdateStats`, every frame). Per hand, **damage is a range** and the attack bonus a
signed number. `FUN_005a9e10(stats, creature, item, &lo, &hi, offhand, withEffects)` gives the
range: with an item `lo` = the base item's number of dice (+0x1c), `hi` = dice x die (+0x1d); a
melee item (+0x1a clear) adds the Strength modifier (stats +0xea, a signed byte) to both; a base
item whose specialization feat (+0xb0) the creature has adds 2 to both; with no item `lo` = 1 and
`hi` = 2 for a creature of size below 3, else 1, both plus Strength. With effects asked,
`GetTotalEffectBonus(damage, ...)` adds its sum to both ends (and a `lo` correction for dice), and
each end is at least 1. The damage label (`LBL_ATKL` / `LBL_ATKR`) reads `Format("%d-%d", lo,
hi)` (0x00756a10) with effects; the attack-bonus label (`LBL_TOHITL` / `LBL_TOHITR`) reads
`GetMeleeAttackBonus` / `GetRangedAttackBonus` (0x005a7770 / 0x005a7b60; ranged when base item
+0x1a is set) formatted `+%d` (0x00748ec0) above zero and `%d` (0x0073d720) otherwise. Each text
is the menu colour (0x007a23b4), or green (0.28/0.92/0.11, 0x007a23e4) when the range with
effects is above the range without (either end), respectively the attack bonus is above
`GetBaseAttackBonus`. The left weapon slot's labels are
cleared when it is empty, the right one's show the unarmed numbers (no item), and a right-hand
item of wield type 3 (a double weapon) also fills the left labels with its off-hand numbers
(`offhand` 1). Defense (`LBL_DEF`) is 0x004ed1d0, vitality (`LBL_VITALITY`) "current/max",
shortened when it does not fit. When the right hand holds a two-handed weapon (base item +0x1b ==
4) or one of wield type 3, the left weapon slot shows the same icon, at alpha 0.25 (+0x10c8). The
slot icons and the per-slot item cache (+0x427c) are refreshed here too, so equipping elsewhere
shows at once. While a previewed item (+0x42a4 slot, +0x42a8 id from `OnRowHilighted`) has not yet
arrived in its slot (the slot holds no item, or one `CSWSItem::CompareItem` finds different), the
numbers that depend on that slot read `--`; once it has arrived +0x42a4 is cleared. (high for the
formats, the labels and the range, med for the effect sum)

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
| 0x006aed90 / 0x006aede0 | `RotateModelLeft` / `RotateModelRight` | turn the 3D model by -10 / +10 degrees about +Z (left: clockwise seen from above, the face swings to the screen's left); BTN_3DCHAR's events 0x16256 / 0x16257 (left / right press, below) | high |
| 0x006aed20 | `CSWGuiCharacter::SetModelRotation` | events 0x3b / 0x3c: the same turn, -10 degrees for 0x3b and +10 for 0x3c | high |
| 0x006b0bb0 | `CSWGuiCharacter::StartLevelUp` | same test as event 0x27, refreshes the stats, then creates the level-up panel (`CSWGuiLevelUpMain`, 0x2560 bytes, ctor 0x006e8ef0) for the controlled character with the sheet's model object, and adds it with flags 3; returns 1 when opened | high |
| 0x006b0cb0 | `CSWGuiCharacter::AutoLevelUp` | yes/no box (strref 36811 "...from level <CUSTOM0> to level <CUSTOM1>...", tokens = the leader's level and the highest level its XP reaches); yes (callback 0x006aec80) runs `CSWSCreatureStats::AutoLevelUp` on the leader's server stats | med |

Controls: `LBL_NAME`, `LBL_CLASS`, `LBL_CLASS1`/`2` and `LBL_LEVEL`/`1`/`2` (up to two classes),
`LBL_VITALITY`(`_STAT`), `LBL_FORCE`(`_STAT`), `LBL_DEFENSE`(`_STAT`), the six attributes
(`LBL_STR`/`LBL_STRENGTH`/`LBL_STR_MOD` ... `CHA`), saves `LBL_FORTITUDE`/`REFLEX`/`WILL`(`_STAT`),
`LBL_EXPERIENCE`(`_STAT`), `LBL_NEXT_LEVEL`, `LBL_NEEDED_XP`, `LBL_3DCHAR` / `BTN_3DCHAR` (the
model view), `SLD_ALIGN` (alignment slider), `LBL_LIGHT`/`LBL_DARK` (its end labels),
`LBL_GOOD1`..`10` (ten icon labels), `LBL_MORE`, `LBL_ADORN`, `LBL_BEVEL`/`2`,
`BTN_LEVELUP`, `BTN_AUTO`, `BTN_SCRIPTS`, `BTN_EXIT`, `BTN_CHANGE1`/`2`, `BTN_CHARLEFT`/`RIGHT`
(the last two exist only in the `patch.erf` copy of the .gui, not the `gui.bif` one).
(high, tags checked)

Events: 0x27 (BTN_LEVELUP) starts level-up when one is available (`CGuiInGame` +0x10c, a flag
the client copies from the server's creature-stats update) and not blocked (0x005ee190, client
internal +0x4b4); 0x2a (BTN_AUTO) the automatic level-up under the same test; 0x29
(BTN_SCRIPTS) opens script select for the leader (modal, flags 3); 0x3b/0x3c rotate the model;
0xce and 0x28/0x2d/0x2e/0xdf as in the conventions. The level-up and auto buttons are visible only
when the viewed character can level (`CSWSCreatureStats::CanLevelUp` 0x005a6810) and either the
view-only flag is clear or the viewed character is the player (index -1). (high)

Stats come from the viewed creature's server `CSWSCreatureStats` (`GetSTRStat` 0x005a6190 ...
`GetDEXStat` 0x005a6550, saves 0x005ab810/0x005ab880/0x005ab8f0) and its client stats (class
names and class levels from the client class slots, 0x00647730/0x00647750; vitality and Force as
"%d/%d"). With two classes `LBL_CLASS1`/`LBL_LEVEL1` show the second (newest) class and
`LBL_CLASS2`/`LBL_LEVEL2` the first. `LBL_FORCE`/`LBL_FORCE_STAT` are hidden when the newest class
is not a Force user (0x005be4a0). `LBL_NEXT_LEVEL`/`LBL_NEEDED_XP` show the XP-table entry for the
total level (`GetLevel` 0x005a5fd0 via 0x005a6610) and are hidden when it is -1. Colours: an
attribute above its base value is green (0x007a23e4, 0.28/0.92/0.11) and below it red (0x007a23d8,
0.74/0.11/0); the saves and defense use the same pair by the sign of their effect bonus, vitality
and Force by the sign of a client-stats field (+0x4a, +0x124; meaning not traced).
The ten `LBL_GOOD%d` labels show up to ten icons from a list on the client creature (+0x8f4
array, +0x8f8 count; each entry's resref at +2), `LBL_MORE` shows when there are more than ten;
the offsets match the ICON-effect list (effecticon.2da rows, rules.md ICON 0x43), so most likely
effect icons. The alignment slider is set to 100 - good/evil (client stats +0x80) so light is at
the top; the 3D model (scene object at +0x59e4) is rebuilt only when the viewed creature or its
alignment changes (compared with the server stats' GoodEvil +0x17e), because the dark-side look
depends on it; the slider is updated only then too. (med)

**The 3D character** (rechecked 2026-10-09 against the rebuilt exports). The constructor builds
the scene into the custom 3D control at +0x577c (vtable 0x00752e30, the chargen previews' kind;
scene +0x57d8, camera +0x57f0) on `LBL_3DCHAR`'s place: room `gui3D_room` at the origin, light model
`charrec_light` (`FUN_00417620(scene, name, -1)`), the camera on its `camerahook` in mode 1, field of
view 22.70 degrees (0x41b5ced9), all only when the GUI-3D switch `DAT_0078d1e4` is set; then a
blank `CSWCCreature` (0x44c bytes, ctor 0x00616a20) at +0x59e4, remembered creature +0x59e8 = 0 and
alignment +0x59ec = -1, so the first `UpdateStats` builds it. There is **no background of its own**:
what changes with alignment is the light model's animation (`evil`, `align1`..`align19`, `good`:
its emitters make the red clouds and sparks of the dark side, the blue clouds and light streams of
the light side, plain mist between, and it recolours `AuroraLight01`), the creature's pose and the
dark-side textures, all below. The room is the black box every GUI scene has (gui3d.md). (high)

When the creature or alignment changed, `UpdateStats` (tail of 0x006afda0): copies the first 15
dwords of the viewed creature's appearance record (creature +0x21c: body variation, texture
variation, armoured flag +0x14, appearance row +0x18, head ...; chargen-3d.md) into a local, sets
its dword +0x10 to 0x7f000000, copies the viewed creature's portrait resref (its vtable slot +0x148,
the getter the party bar uses) into the model's (slot +0xec, `0x0060d560`, the setter chargen's
Accept uses; the sheet never shows the model's portrait), applies the
record with `FUN_006134c0(model, record, 3, 1)`: mask 3 = body and head only, so **the creature is
shown as dressed (its armour's body and texture) but without weapons** (bits 4 and 8 would build
the hand items through `FUN_00697b00` / `FUN_00697bc0`); then `FUN_00698150(model appearance,
viewed creature's good/evil)` (the dark-side textures, next paragraph), attaches the model to the
scene (+0x94), puts it at the origin (+0x8c) facing (1, 0, 0) (+0x88), and calls
`FUN_006100f0(model, 3D control, viewed creature, 0, 1)`: the light model's animation, the pose
played on body and head, and the camera hook by the creature's name (chargen-3d.md, "The main
panel and alignment": `t3m4` and `hk47` pause instead of posing and take `camerahookt` /
`camerahookh`, `zaalbar` `camerahookz`; the name is a string at +0x18 of the object
`FUN_0063d4b0` + slot +0x30 returns for the creature, by all appearances its tag). (high for the
calls and the mask, med for the name being the tag)

The record's dword +0x10 is an object id (0x7f000000 is the client's invalid object id, the value
`CancelCreatureActions` and others reset ids to). Its only reader found is `FUN_006978a0`, which
`FUN_006134c0` runs on the appearance: when the appearance's flag +0x68 is set it puts the opacity
of the body's and head's models (creature slot +0x98, parts 0xff and 0xfe), of the object with that
id and of the items in inventory slots 0x10 and 0x20 (the hands) back to 1.0 (`FUN_0043e150(model,
1.0)`). Clearing it keeps the sheet's copy from reaching an object of the viewed creature's in the
world. Nothing on screen depends on it. (high for the reader, med for "only")

`FUN_00698150(appearance, alignment)` (also run by `FUN_006134c0` with the model's own stats and by
`FUN_0060f780` for creatures in the world, see "Dark-side looks in the world" below) does nothing when the alignment is the one it last used
(+0x2c) and nothing is pending (+0x50). Otherwise the head's texture: heads.2da row (the record's
head byte +0x34, or when 0xff the appearance's `normalhead` or `backuphead` column by +0x30), column
`headtexvvve` below 11, `headtexvve` below 21, `headtexve` below 31, `headtexe` below 41; the cell's
texture (TPC or TGA) replaces the head's, and with no cell (41 and up) the head's own texture comes
back. The body: when the record is not armoured (+0x14 = 0) and the alignment is below 31,
appearance.2da `texaevil` + `01` replaces the body's texture if it exists; otherwise the body's own
(`FUN_00697610`) comes back. So a dark Jedi's face and underwear darken by stages; an armoured body
keeps its armour's texture. (high)

Dark-side looks in the world: the same function runs for every client creature, at two places.
`FUN_006134c0` (apply an appearance record to a `CSWCCreature`: the body and head models, the hand
items) ends with `FUN_00698150(creature +0x21c, client stats (+0x2f8) +0x80)`, so every build of a
creature's model takes its good/evil. `FUN_0060f780(creature, good/evil)` stores the value (clamped
0..100) in the client stats +0x80 and calls `FUN_00698150` again; the creature update handler
`FUN_00667265` (via the table at `0x0074dd88`) calls it for the update's `0x1000` block (portrait
id, name, two bytes, good/evil). The server writes that block in `FUN_00574a10` (stats +0x17e, the
value GetGoodEvilValue returns) whenever `FUN_0056b950` finds the creature's portrait, name, class
levels, good/evil or another of a few fields changed since the last update; nothing there limits it
to the player or the party. So any creature re-textures when its alignment changes, and the rule
needs no check of who it is because only the player heads (heads.2da rows 26 on) have `headtex*`
cells and only player bodies have `texaevil`. (high for the calls, med for "every creature": the
update path for non-party creatures was not followed to the end)

Turning: `BTN_3DCHAR` (+0x580c) is a repeat button (vtable 0x007533c8, see the open questions at the
end): a left press sends 0x16256 (`RotateModelLeft`, -10 degrees) and a right press 0x16257
(`RotateModelRight`, +10 degrees) at once, then again every +0x59d0 = 0.1 s while the button keeps the
mouse (the constructor sets +0x59d0 / +0x59d4 to 0.2 / 0.5 and then both to 0.1). The turn is the
model's own orientation, so it lasts until the model is rebuilt. The handler rotates the model's
facing (model +0x30) by `Quaternion_FromEulerDegrees(-10, 0, 0)` (the first angle is about +Z, the
quaternion (w, x, y, z) from `QuatFromAxisAngle` is the usual one) through `FUN_004a9bb0` (the usual
q v q* rotation) and sets it (slot +0x88): -10 degrees about +Z is clockwise seen from above. The
model starts facing (1, 0, 0) toward the camera, so **a left press turns the character to its own
right: its face swings toward the screen's left**, and a right press the other way. (high) Events 0x3b / 0x3c (the gamepad's
right stick) turn it too. `OnPanelAdded` (0x006b2220) resets the viewed index (+0x59f0 = -1) and two
other fields, not +0x59e8, so reopening the sheet keeps the old model, turn and outfit unless the
creature or the alignment changed. (high)

#### CSWGuiAbilities (abilities.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006adda0 | `CSWGuiAbilities::CSWGuiAbilities` | 0x3f98 bytes; loads `abilities`, ten prebuilt row controls (+0x70, stride 0x310) | high |
| 0x00755e50 | `CSWGuiAbilities::vftable` | 15 HandleInputEvent 0x006ae5f0, 18 OnPanelAdded, 19 OnPanelRemoved 0x006ab8b0 | high |
| 0x006adc20 | `CSWGuiAbilities::OnPanelAdded` | viewed creature = leader | high |
| 0x006adb00 | `CSWGuiAbilities::SetCreature` | portrait, feat/power trees, Powers button by the newest class (below), rebuild | med |
| 0x006adad0 / 0x006adaa0 / 0x006ada70 | `OnSkillsTab` / `OnPowersTab` / `OnFeatsTab` | set tab 0/1/2 (`CGuiInGame` +0xbc0) and rebuild | high |
| 0x006ac8d0 | `CSWGuiAbilities::KeepTabHilighted` | tab button event 1: keep the current tab's text yellow | high |
| 0x006ad560 | `CSWGuiAbilities::RebuildList` | fills `LB_ABILITY` for the tab (skills: the prebuilt rows, at most ten; powers / feats: the tree lists), restores the tab's remembered selection, hides the rank / bonus / total labels on the Feats tab, tutorial 0x24 / 0x26 / 0x25 (skills / powers / feats) | med |
| 0x006ad180 | `CSWGuiAbilities::OnRowHilighted` | name, description, rank / bonus / total | med |
| 0x006ad4b0 | `CSWGuiAbilities::OnSelectionChanged` | list event 0x1f8: for powers/feats, show the chosen entry | med |
| 0x006adc80 | `CSWGuiAbilities::OnChangeCharacter` | BTN_CHANGE1/2 | med |
| 0x006abec0 | `CSWGuiAbilities::UpdatePartyButtons` | | med |

Controls: `LB_ABILITY` (the skill / power / feat list; in both versions of the .gui), `LB_DESC`,
`LBL_PORTRAIT`, `LBL_NAME`, `LBL_SKILLRANK`/`LBL_RANKVAL`, `LBL_BONUS`/`LBL_BONUSVAL`,
`LBL_TOTAL`/`LBL_TOTALVAL` (skills: rank, attribute bonus, total), `LBL_INFOBG`, `BTN_SKILLS`,
`BTN_POWERS`, `BTN_FEATS`, `BTN_EXIT`, `BTN_CHANGE1`/`2`, `BTN_CHARLEFT`/`RIGHT` (the last two only in
the `patch.erf` copy). The tab is kept
in `CGuiInGame` +0xbc0 between openings; Powers is hidden and the tab reset to Skills when the
character's newest class is not a Force user (0x005be4a0), and shown when it is one and the power
list is not empty (an empty list leaves the button as it was). Feats and powers are read through a tree
helper shared with the level-up screens (row sets at +0x3f78 powers / +0x3f88 feats, built by
`SetCreature` through `0x006abce0` / `0x006ce370` with the focus on the first cell; "Chain rows"
above). `RebuildList` hands the tab's row set to `LB_ABILITY` and restores its focused row and cell,
so each tab keeps its focus across tab changes until the creature changes; a click (0x1f8,
`OnSelectionChanged`) focuses the cell under the pointer and shows it, the arrows move it. The
Skills tab shows the ten prebuilt rows. (high for the row sets, med for the rest)

#### CSWGuiJournal (journal.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00644a40 | `CSWGuiJournal::CSWGuiJournal` | 0xfc8 bytes; loads `journal`, owns the quest-items panel (+0xfb4) | high |
| 0x00751960 | `CSWGuiJournal::vftable` | 13 Render 0x00645670, 15 HandleInputEvent, 18 OnPanelAdded 0x00645e00, 19 OnPanelRemoved 0x00646070 (a thunk to `ClearQuestRows`) | high |
| 0x006456e0 | `CSWGuiJournal::HandleInputEvent` | events below | high |
| 0x00645330 | `CSWGuiJournal::RebuildQuestList` | one button row per quest of the shown list, from the client journal (0x005ed320); a quest with the "new" flag gets its own colour; selects the first row | med |
| 0x00645610 | `CSWGuiJournal::ClearQuestRows` | clears the "new" flag of the quests whose text was shown (journal.md) | med |

Controls: `LB_ITEMS` (quests), `LBL_ITEM_DESCRIPTION` (a list box despite the prefix: the quest
text), `LBL_TITLE`, `BTN_QUESTITEMS`, `BTN_SWAPTEXT`, `BTN_SORT`, `BTN_EXIT`. (high)

State: `CGuiInGame` +0xbc4 bit0 = showing completed quests. The client journal keeps a sort mode
0..3 per list (active +0x38, completed +0x18; getters 0x00712fc0 and the `CRes::GetSize`-folded
0x00644760, setters 0x00676bc0 / 0x00676bf0, which accept 0..3 and re-sort the list when journal +0x40 bit0 is
set). The panel remembers one mode
in the global 0x00833a90 (saved as `JNL_SortOrder`, journal.md) and `OnPanelAdded` applies it to
the shown list only (mode 0 instead when the flag 0x00833a94 is set). `Render` rebuilds the rows
when the shown list's changed flag (journal +0x3c / +0x1c) is set. Sort names (table 0x007a2474):
by Order Received (32173), by Name (32174), by Priority (32175), by Planet (32176). (high)

Events: 0x29 (BTN_QUESTITEMS) opens the quest-items panel (flags 3); 0x2a (BTN_SWAPTEXT) clears
the rows, stores the mode of the list it leaves in the global, toggles active/completed, rebuilds,
sets the button text to the other list's name ("Completed Quests" 32177 / "Active Quests" 32178)
and the title to "<list> - <stored mode>", so the title can name a mode the new list is not sorted
by (med: needs a runtime check); 0x2b (BTN_SORT) takes the shown list's mode + 1 (wrapping 3 → 0),
stores it in the global, sets it on the shown list (which re-sorts), sets BTN_SORT to "Sort <the
mode after that>" (42566 + a space + the name) and the title; 0x39/0x3a scroll the text; close
keys as usual. The quest data model (JRL, states, priorities, the "new" flag) and the sorting
are in journal.md. (high for the panel, med for list contents)

#### CSWGuiQuestItems (questitem.gui) — skimmed

Ctor 0x006d26c0 (0xa70 bytes, vtable 0x00757c20), owned by the journal. Controls `LB_ITEMS`,
`LB_ITEM_DESCRIPTION`, `LBL_TITLE`, `BTN_BACK`. On open (0x006d2c20 → 0x006d29f0) it lists every
plot item (item +0x108) in the party inventory (the leader's `GetItemRepository(1)`) as `CSWGuiItemEntry` rows (no equipped/new
marks) and selects the first; hilighting a row (0x006d2580) shows its description. Back/0x28/0x2e
pop it; 0x39/0x3a scroll the description. (med)

#### CSWGuiMap (map.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00694d50 | `CSWGuiMap::CSWGuiMap` | 0x10dc bytes; loads `map` | high |
| 0x00754830 | `CSWGuiMap::vftable` | 13 Render, 15 HandleInputEvent, 16 HitTest, 18 OnPanelAdded, 19 OnPanelRemoved 0x00693ba0 | high |
| 0x00693650 | `CSWGuiMap::OnPanelAdded` | area name, map texture, map notes, enables Party Select / Return, tutorial 0x0d | high |
| 0x00693bc0 | `CSWGuiMap::HandleInputEvent` | events below | high |
| 0x00692810 | `CSWGuiMap::Render` | dims disabled buttons, draws the panel, then the map image and the map view in a viewport at LBL_Map's rectangle (shifted by the 640x480 centring offset) | high |
| 0x00692930 | `CSWGuiMap::HitTest` | a click outside any control goes to the map view (map-local coordinates) | high |
| 0x006927b0 / 0x006927c0 | `CSWGuiMap::OnNoteUp` / `OnNoteDown` | BTN_UP / BTN_DOWN send 0x31 / 0x32 to itself | high |
| 0x006929b0 | `CSWGuiMap::ShowMapNote` | LBL_MapNote = "Map Note" (349) + ": " + the note's text, or empty when there is none | high |
| 0x00692bc0 | `CSWGuiMap::OnReturnToBase` | the Return button's action (below) | high |

Controls: `LBL_Map` (the map's rectangle; the texture is drawn by a map-view object at +0xe38 and
an image at +0x1080 inside a viewport pushed at LBL_Map's extent), `LBL_MapNote`, `LBL_Area` (area
name, area +0x17c), `LBL_COMPASS`, `BTN_UP`/`BTN_DOWN` (previous/next map note), `BTN_PRTYSLCT`,
`BTN_RETURN`, `BTN_EXIT`. Events 0x31/0x3d step to the previous map note and 0x32/0x3e to the next
(GUI sound 1). (high)

Map texture: `lbl_map` + the module resref (format `lbl_map%s`), or `lbl_mapm28aa` when the module
has no map flag (module +0x218 → +4 is zero). The world-to-map transform and the drawing of party
arrows and notes live in the map-view object, shared with the HUD minimap (see the HUD section and
movement.md). (med)

**Party Select** (0x27) is enabled only when (1) the area allows it (area +0x2ac == 0; else
"That function is unavailable at this time." 38451), (2) the party is together (every member within 30 m of the leader,
0x00635350; else "You must rejoin your party first." 38452) and (3) no creature in the area has
seen a party member while that member rates it hostile: for each creature of the area's x-sorted
list (+0x190/+0x194) from the first whose x is at least the smallest (member x - member sight
range), and each party member, the member's reputation toward it is 10 or less (0x0057cb80) and
the creature's perception entry for the member has the seen bit (0x00517a20 on the creature; else
"That cannot be done while there are enemies nearby." 38462). When disabled, clicking shows the stored
message; when enabled it opens party selection with no exit script
(`CGuiInGame::ShowPartySelection` 0x0062dd20, from-script 0). (high)

**Return** (0x29) is enabled only when Party Select passed all three tests and the party table's
return flag (+0x100) is set; its label is the strref at +0x104 and its question the strref at
+0x108, all three set by `SetReturnStrref` (routine 152, `CSWPartyTable::SetReturnStrref`
0x00563ab0; defaults in party-items-saves.md). Pressing it first offers tutorial 0x27 and
otherwise runs the return action (0x00692bc0): when disabled, the stored refusal (38451 when none
was stored); when enabled, a yes/no box with the question; yes (0x00692b00) closes the in-game menu
and, if that succeeded, sets `CGuiInGame` +0xc04 = 1, runs the script `k_sup_gohawk` (owner id 0)
and clears the flag. (high)

Disabled buttons are drawn with text colour 0x007a2408 (0, 0.33, 0.49: the menu blue at half) and
border colour 0x007a2384 (grey 0.35) instead of the menu blue and white (0x007a2378), set in
`OnPanelAdded` and again each `Render`. When the client option +0x14 bit 0x100 is set, both
buttons' text alignment becomes 0x12. (high)

#### CSWGuiGalaxyMap (galaxymap.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x00695180 | `CSWGuiGalaxyMap::CSWGuiGalaxyMap` | 0x2550 bytes; loads `galaxymap`, the model `galaxy` in the `3D_PlanetDisplay` scene (`gui3D_room`, `camerahook`) and up to 16 planet buttons | high |
| 0x00754910 | `CSWGuiGalaxyMap::vftable` | 13 Render 0x00693610, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved 0x006927d0 | high |
| 0x0062d040 | `CGuiInGame::ShowGalaxyMap` | from NWScript `ShowGalaxyMap(nPlanet)` (routine 739); only when `CGuiInGame` +0x108 is set and +0x30 and the conversation flag +0xb4 are clear: pauses, sound mode 4, HUD mode 3, clears the bark bubble, GUI input (class 2), creates the panel if missing, `SetSelectedPlanet(nPlanet)` (ignored unless that planet is available and selectable), `AddPanel(2, 1)`, GUI sound 4 | high |
| 0x0062d1d0 | `CGuiInGame::CloseGalaxyMap` | unpauses, HUD mode 4, game input, removes the panel (and deletes it unless the global 0x007a2370 is set), GUI sound 5, sound mode 0 | high |
| 0x00694b40 | `CSWGuiGalaxyMap::OnPanelAdded` | with no selected planet picks the first one available and selectable; marks its button, shows it; each planet button is visible only while its planet is available | high |
| 0x00695980 | `CSWGuiGalaxyMap::HandleInputEvent` | events below | high |
| 0x006935a0 | `CSWGuiGalaxyMap::OnPlanetClicked` | planet button 0x27: unmark the old button, `SetSelectedPlanet` (which refuses a planet that is not selectable, so the old one stays selected but unmarked), show the selected planet | high |
| 0x006933a0 | `CSWGuiGalaxyMap::ShowPlanet` | name, description, planet model with animations `rotate` / `zoomin` | med |
| 0x00694ca0 / 0x00694bf0 | `SelectPreviousPlanet` / `SelectNextPlanet` | step down / up through 0..15 with wrap, to the next planet that is available and selectable | high |

Planet buttons come from `planetary.2da` (rules 2DA cache +0x104), rows 0..15 only (row 16,
`Live_Planet_06`, is never read): for each row the button tag is the `guitag` column
(`LBL_Planet_Taris` ... `LBL_Live01`..`05`), the `icon` column is the button's image (normal and
hilight), and the `name`/`description` strrefs and `model` column feed `LBL_PLANETNAME`,
`LBL_DESC` and `3D_PlanetModel`; `3D_PlanetDisplay` is the galaxy view. Rows without a guitag
(Ebon Hawk) have no button. Availability and
selectability per planet are party-table state set by `SetPlanetAvailable`/`SetPlanetSelectable`
(routines 742/740); the selected planet is the party table's +0xe0 (`CSWPartyTable::SetSelectedPlanet`
0x00563b60). (high for the 2DA use, med for the availability display)

Events: 0x27/0x2d (BTN_ACCEPT) set `CGuiInGame` +0xc04 = 1, run the script `k_sup_galaxymap`
(owner `OBJECT_INVALID`), clear the flag and close; 0x28/0x2e/0xdf (BTN_BACK) close; 0x2f, 0x31,
0x3d, 0x3f select the previous planet and 0x30, 0x32, 0x3e, 0x40 the next (GUI sound 1); the
base panel handler runs before this switch. The
script reads the selected planet (`GetSelectedPlanet`) and does the travel. (high)

#### CSWGuiContainer (container.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006b6dc0 | `CSWGuiContainer::CSWGuiContainer` | 0x101c bytes; loads `container` (a 305x327 box, centred) | high |
| 0x007567e0 | `CSWGuiContainer::vftable` | 14 Update, 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x0062d4b0 | `CGuiInGame::OpenContainer` | called when the server opens a container for the player (message handler 0x00651810: object id and a byte); fills the panel (`ShowContainerItems`), adds it modal (`AddPanel(1, 1)`), GUI input (class 2), pauses | high |
| 0x0062d510 | `CGuiInGame::CloseContainer` | when the panel is up: pops modal, removes the panel, back to game input, unpauses | high |
| 0x006b51d0 | `CSWGuiContainer::OnPanelAdded` | saves the cursor and warps it to the centre of BTN_OK | high |
| 0x006b5250 | `CSWGuiContainer::OnPanelRemoved` | restores the cursor position | high |
| 0x006b8770 | `CSWGuiContainer::Update` | rebuilds the give-items list when flagged | med |
| 0x006b92f0 | `CSWGuiContainer::HandleInputEvent` | events below | high |
| 0x006b8130 | `CSWGuiContainer::ShowContainerItems` | stores the container id and the byte, lists the placeable's items (its repository +0x36c), title 393 "Container Inventory" (byte non-zero) or 394 "Container is Empty" (byte 0) | med |
| 0x006b8410 | `CSWGuiContainer::ShowGiveItems` | lists the party inventory's non-plot items, title 392 "Items Available to Place in Container"; a row's 0x27/0x2d (0x006b7170) has the leader put one of it into the container (0x0060eea0; a count from 0x006b4fe0 while the alternate-action key is held) and sets bits 1 and 2 | med |
| 0x00677630 | `SendContainerClose` | client-to-server message (type 0x19, subtype 2) with the container id and a take-all flag | med |

Controls: `LBL_MESSAGE` (title), `LB_ITEMS`, `BTN_OK` (take all), `BTN_GIVEITEMS`, `BTN_CANCEL`;
the code also binds `LBL_BUTTON`, `LBL_OK`, `LBL_B`, `LBL_X`, `LBL_CANCEL` (gamepad hint labels)
which this .gui does not have, so they stay empty. (high)

Panel flags at +0x6c: bit0 = the container's own items are showing (set by `ShowContainerItems`,
cleared by `ShowGiveItems`), bit1 = give list needs a rebuild (handled in `Update`), bit2 = skip
one update. Events: 0x27 (BTN_OK) and 0x2d act only while the container's items are showing: they
send the close message with take-all = (the open message's byte, +0x68, == 1) and close; 0x28/0x2e (BTN_CANCEL)
send it with take-all 0 and close; 0x29 (BTN_GIVEITEMS) switches between the container list and
the give-items list. The container id is at +0x64. The actual item transfer happens on the server
when it receives the message (party-items-saves.md). (med)

#### CSWGuiStore (store.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006c1c00 | `CSWGuiStore::CSWGuiStore` | 0x2280 bytes; loads `store` | high |
| 0x00756e38 | `CSWGuiStore::vftable` | 15 HandleInputEvent, 18 OnPanelAdded, 19 OnPanelRemoved | high |
| 0x0062e310 | `CGuiInGame::OpenStore` | from NWScript `OpenStore` (0x00540300): only when `CGuiInGame` +0x108 is set and +0x30 and the conversation flag +0xb4 are clear; pauses, HUD mode 3, sound mode 4, clears the bark bubble, GUI input (class 2), creates the panel if missing, store id +0x2278, customer +0x227c, `AddPanel(3, 1)`, GUI sound 4 | high |
| 0x0062e4a0 | `CGuiInGame::CloseStore` | unpauses, HUD mode 4, game input, removes the panel (or, when the global 0x007a2370 is clear, flags it for deletion and forgets it), GUI sound 5, sound mode 0 | high |
| 0x006c2170 | `CSWGuiStore::OnPanelAdded` | `SetupForStoreMode`, credits, then `ShowBuyList` unconditionally | high |
| 0x006c2190 | `CSWGuiStore::HandleInputEvent` | 0x28/0x2e close; 0x29 = Examine; 0x39/0x3a scroll | high |
| 0x006c1b50 | `CSWGuiStore::SetupForStoreMode` | store mode byte (store +0x256, `BuySellFlag`): 1 buy only, 2 sell only, 3 both (BTN_Examine shown); because `OnPanelAdded` then shows the buy list anyway, a mode-2 store opens on the buy list with no way to switch (no shipped store uses 2; med: needs a runtime check) | high |
| 0x006c1b00 | `CSWGuiStore::OnToggleList` | BTN_Examine: in mode 3 switch between buy and sell lists | high |
| 0x006c1a50 | `CSWGuiStore::ShowBuyList` | LB_SHOPITEMS, labels "Buy", BTN_Accept → `OnBuy` | high |
| 0x006c13c0 | `CSWGuiStore::ShowSellList` | LB_INVITEMS, labels "Sell" (32130), BTN_Examine "Show Buy List" (41937), BTN_Accept → `OnSell` | high |
| 0x006c1840 / 0x006c0850 | `FillStoreItems` / `FillPlayerItems` | | med |
| 0x006c1660 | `CSWGuiStore::AddItemRow` | reuses or creates a row (0x394 bytes, ctor 0x006b71e0) in the store (+0x68) or player (+0x74) pool; row 0x27 → `OnBuy` / `OnSell` | med |
| 0x006c0aa0 | `CSWGuiStore::OnItemHilighted` | description, the buy or sell price by the shown list, stack size or 41951 "Infinite" | high |
| 0x006c1130 / 0x006c0f40 | `OnBuy` / `OnSell` | checks and confirmation | med |
| 0x006c0be0 / 0x006c0d80 | `DoBuy` / `DoSell` | the transaction (server store calls 0x005c6f70 / 0x005c7610) | med |
| 0x006c0790 / 0x006c07f0 | `GetBuyPrice` / `GetSellPrice` | below | high |
| 0x006c0610 | `CSWGuiStore::UpdateCredits` | the customer's gold into +0x2270 and `LBL_CREDITS_VALUE` | high |

Controls: `LB_SHOPITEMS` and `LB_INVITEMS` (same rectangle; one is shown), `LB_DESCRIPTION`,
`LBL_BUYSELL`, `LBL_CREDITS`/`_VALUE`, `LBL_COST`/`_VALUE`, `LBL_STOCK`/`_VALUE`, `BTN_Accept`,
`BTN_Examine` (in a buy-and-sell store: "Show Sell List" 41938 / back), `BTN_Cancel`. (high)

Prices, with `cost` = the item's value (0x00554000) and the store's percentages: **buy price**
(player pays) = cost × (store +0x248 + store +0x250) / 100, **sell price** (player receives) =
cost × (store +0x244 + store +0x24c) / 100, unsigned integer division. +0x248/+0x244 are the store's own
mark-up / mark-down and +0x250/+0x24c the bonus mark-up / mark-down passed to `OpenStore`
(written by 0x00540300, clamped to -100..100). Rules for stock and infinite items: party-items-saves.md. (high)

#### Upgrade bench: CSWGuiUpgradeSelect, CSWGuiUpgradeItems, CSWGuiUpgrade

Opened by NWScript `ShowUpgradeScreen(oItem)` (routine 354, 0x00543990 →
`CGuiInGame::ShowUpgradeScreen` 0x0062e760). It does nothing while a bench is already open
(`CGuiInGame` +0x88) or when the given id is not an item; otherwise it sets sound mode 4, pauses
the game (unless +0xb38), creates the category panel (0x1158 bytes, kept at +0x88, the item id at
its +0x113c), adds it with flags 3 and sets input class 2. When an item is given the category
panel's `OnPanelAdded` goes straight on to the items panel. `CloseUpgradeScreen` 0x0062e870
undoes the pause, input class and sound mode and marks the category panel for removal. Three
panels:

| Address | Name | .gui | What | Conf. |
|---|---|---|---|---|
| 0x006c78d0 / 0x007571b0 | `CSWGuiUpgradeSelect` | upgradesel | `LBL_TITLE`, four category buttons `BTN_LIGHTSABER`, `BTN_RANGED`, `BTN_MELEE`, `BTN_ARMOR` (with `LBL_*` pictures), `BTN_UPGRADEITEMS`, `BTN_BACK` (cancel) | high |
| 0x006c2b60 | `CSWGuiUpgradeSelect::OnCategory` | | category button 0x27/0x2d (or BTN_UPGRADEITEMS on the hilighted one): if that category has items, set the item panel's category (+0xc2c = index + 1) and open it (flags 3) | high |
| 0x006c2b10 | `CSWGuiUpgradeSelect::HandleInputEvent` | | 0x28/0x2e: GUI sound 0 and close the bench (`CGuiInGame::CloseUpgradeScreen` 0x0062e870) | high |
| 0x006c7630 / 0x00757228 | `CSWGuiUpgradeItems` | upgradeitems | `LB_ITEMS` (items of the category, `CSWGuiItemEntry` rows), `LB_DESCRIPTION`, `BTN_UPGRADEITEM`, `BTN_BACK`, `LBL_TITLE` | high |
| 0x006c2df0 | `CSWGuiUpgradeItems::OnUpgradeItem` | | takes the chosen item: an equipped one is unequipped from its wearer (0x004faa70; for weapons both hands are handled and remembered), a stacked one is split off one unit (0x0055f280), a loose one is removed from the party inventory (0x00555fd0); then opens the upgrade panel with the item (+0x2f54) and kind (+0x2f4c, the category: 1 lightsaber, 2 ranged, 3 melee, 4 armour) | high |
| 0x006c6b60 / 0x00757298 | `CSWGuiUpgrade` | upgrade | `LB_ITEMS`, `LB_DESC`/`LB_DESC_LS`, `LBL_DESCBG`(`_LS`), `3D_MODEL`(`_LS`), `LBL_SLOTNAME`, `LBL_LSSLOTNAME`, `LBL_UPGRADES`, `LBL_UPGRADE_COUNT`, `LBL_PROPERTY`, `LBL_UPGRADE31..33` + `BTN_UPGRADE31..33` (three slots: lightsaber and melee), `LBL_UPGRADE41..44` + `BTN_UPGRADE41..44` (four slots: ranged, and armour in the second and third), `BTN_ASSEMBLE`, `BTN_BACK` | high |
| 0x006c6500 | `CSWGuiUpgrade::OnSlotClicked` | | lightsaber: list the choices for the slot found in the party inventory (`upgrade.2da` `UpgradeType`/`Template`, colour crystals from `upcrystals.2da` `Template`) and enter selection; other items, no list: a filled slot loses its upgrade (the item's upgrade bit, item +0x294, cleared) back to the inventory (0x0055d330), an empty one takes the matching upgrade from the inventory. Adding an upgrade that would stop the wearer re-equipping the item asks first (42489) | high |
| 0x006c6190 | `CSWGuiUpgrade::OnAssemble` | | finishes (`ReturnItem` 0x006c5e90 on the item panel), pops the panel | high |
| 0x006c6a80 | `CSWGuiUpgrade::HandleInputEvent` | | 0x28/0x2e (GUI sound 0): leave selection (0x006c4d30) or cancel the bench (`OnCancel` 0x006c61f0: undo and give the item back); 0x39/0x3a scroll the description box (`LB_DESC_LS` for a lightsaber) as 0x31/0x32 | high |

The upgrade rules (which property each upgrade adds) belong to rules.md /
party-items-saves.md. (med)

In detail (high unless noted):

- **Categories** (`OnPanelAdded` 0x006c4520). It counts the categories of the PC's and every available selectable NPC's equipped items
  (`FUN_006c2ab0`) and of the party inventory; for each category (lightsaber 1, ranged 2, melee 3, armour 4, in the order of the buttons
  and of the picture labels `LBL_LSABER`, `LBL_RANGED`, `LBL_MELEE`, `LBL_ARMOR`) it sets the **picture label's visible bit** (flag +0x44
  bit 1) to "has items" and the button's text colour to the menu or the disabled colour. With an item given (`ShowUpgradeScreen(item)`) it
  stores the item (+0xc38) and its category in the item panel and adds that panel at once. Hilighting a category button (event 0,
  `FUN_006c2bd0`) remembers it in +0x1154 and colours `BTN_UPGRADEITEMS` normal when the category has items, disabled (and +0x1154 = 0)
  otherwise. `OnCategory` 0x006c2b60 (0x27, 0x2d; sound 0 for 0x2d) takes the control, or for `BTN_UPGRADEITEMS` the last hilit category
  button (+0x1154), and opens the items panel when the category has items.
- **Items panel**. `FillItemList` 0x006c5b90 makes one entry per upgradeable item: the PC's equipped items, those of each available
  selectable NPC (`AddCreatureItems` 0x006c4960: slot bits 0 to 17), then the inventory's. Each entry is a `CSWGuiItemEntry` (0x3a4 bytes)
  with handlers 0 (`FUN_006c4880`: the description of the item in the right box), 0x27 and 0x2d (`OnUpgradeItem`): a click on a row takes
  it. `BTN_UPGRADEITEM` (+0x8a4) acts on the list's selected entry. `OnUpgradeItem` 0x006c2df0: a loose item leaves the inventory (one
  unit of a stack: `SplitItem`), a worn one is unequipped; for a weapon in the right (0x10) or left (0x20) hand with the other hand filled
  **both are unequipped** and the other's id and which hand are kept (+0xc30 bit 0 "pair", bit 1 "the item was the left one", +0xc34 the
  other's id). `ReturnItem` 0x006c5e90 puts the item back with `CanEquipItem`: not allowed any more -> the inventory; a pair: item in the
  right and the other in the left, or, when the item no longer fits, the other weapon in the right hand; for a left item the right one
  first. Then, for the list's own opening, the list is filled again when the item's id changed (a new saber), the entry of the item is
  selected and scrolled to; for a script's item the items panel closes and the screen with it (`CloseUpgradeScreen`).
- **Bench panel**. `OnPanelAdded` 0x006c4d70 keeps a backup copy of the item (`CopyItem`, used by `OnCancel`) and fills `+0x2fa4[slot]`
  with the upgrade.2da row of the slot (row whose `UpgradeType` is the slot's type in `g_aUpgradeSlots`) and `+0x2f74[slot]` with a made
  copy of the upgrade item when the item's Upgrades bit is set. For a lightsaber slot 1 holds the colour crystal made from the
  `upcrystals.2da` row whose `LongMdlVar`/`ShortMdlVar`/`DoubleMdlVar` (by the base item's ItemType 41/40/39) names the saber's tag; **no
  row, or a base ItemType other than 39..41, closes the panel**. A slot takes the first matching row while the slot is still empty, so of
  two slots of the same type (the saber's two power slots) the second gets a row only when the first holds an upgrade. Slot pictures are
  the item's icon or the slot's own (`g_aUpgradeSlots[(category-1)*4+slot]`: type, picture, name strref; lightsaber {0, i_powerc, 36977},
  {-1, i_colorc, 36978}, {0, i_powerc, 36977}; ranged 4 to 7 {i_scope 32487, i_energy 32488, i_beam 32489, i_hair 32490}; melee 1 to 3
  {i_vcell 32493, i_durasteel 32494, i_imp_eng 32495}; armour {none}, {8, i_armorrein 32491}, {9, i_armorrein 32492}); an empty
  non-lightsaber slot whose upgrade the party lacks is drawn at alpha 0.25 (set at opening). `FUN_006c2f80(selecting)` shows/hides
  controls by their visible bit: normal mode shows the 3D model, the slot name, "Upgrades:", the count, the property box and Assemble for
  the weapons and armour (the `_LS` ones for a lightsaber), the three-slot controls for lightsaber and melee, the four for ranged (all)
  and armour (the second and third), and hilights the first slot; selection mode hides all of those and shows `LB_ITEMS` (the description
  box stays).
- **Slots**. `OnSlotHilighted` 0x006c3c30: lightsaber: `LBL_LSSLOTNAME` = the slot's item name, else the slot's strref; others:
  `LBL_SLOTNAME` = the slot's strref, `LBL_UPGRADES` = 42026 "Upgrades:", `LBL_UPGRADE_COUNT` = the stack size of the party
inventory's item with the slot's template tag (0 when there is none; `0x006c3d43`..`0x006c3d88`), `LBL_PROPERTY` = the item's own
  properties tagged with the slot's upgrade row (`FUN_0055f510`). `OnSlotClicked` 0x006c6500: **lightsaber**: the list `LB_ITEMS` with
  entries made by `FUN_006c58c0(item, row)`: colour slot: the colour crystal it has, then each upcrystals row (other than it) whose
  crystal the inventory holds; power slot: an entry with no item (shown as None), the crystal it has, then each upgrade.2da row of type 0
  whose item the inventory holds and which is in neither power slot. **Other items**: a filled slot clears the item's Upgrades bit and
  returns the upgrade to the inventory; an empty one finds the inventory's item with the slot's template tag (none: nothing), sets the
  item's bit, and when the item came from a wearer and `CanEquipItem` now fails opens the confirm box 42489 instead of taking it. Its
  callback `FUN_006c6120` takes the upgrade on OK (`TakeUpgradeItem` 0x006c59a0); on No it clears the bit on the *upgrade* item (the
  callback's argument), not on the bench item, so as decompiled and in the disassembly the bench item keeps the bit set without the
  upgrade (med, an engine bug; needs a runtime check). `OnUpgradeChosen` 0x006c5510 (a list entry's 0x27/0x2d): colour slot: a new saber
  is made from the chosen row's template (possessor the player, identified, Upgrades and the stolen flag copied) and replaces the bench
  item at once, then the old colour crystal returns to the inventory and the chosen one is taken into slot 1 (no bit for the colour slot);
  the entry of the crystal it has changes nothing. Power slot: the old crystal returns to the inventory (its bit cleared), "None" stops
  there, the chosen entry's crystal is taken (one unit of a stack) and the slot's row and bit become the chosen row's; the "keep" entry
  changes nothing. The hover handler `FUN_006c5370` shows the entry's name (for a power crystal after the properties that row adds to the
  item) in the description box. All inventory moves are ledgered (+0x2f68 upgrades taken from the inventory, +0x2f5c ones put into it; a
  move that undoes a ledgered one just drops it from its list) so `OnCancel` 0x006c61f0 can undo them: it restores the backup item, puts
  the +0x2f68 items back into the inventory, takes the +0x2f5c ones out again, calls `ReturnItem` and pops the panel. `OnAssemble`
  0x006c6190 calls `ReturnItem` and pops the panel.
- **Render** 0x006c33a0: the item's 3D view turns by -70 degrees a second (`3D_MODEL_LS` for a lightsaber, else `3D_MODEL`; both scenes
  load the `gui3D_room` rig `upgitem_light` in the constructor). `FUN_006c3630` puts the item in: the model by `GetModelResRef` (armour
  through 0x006c3460), the camera on `camerahook`, the "rotate" animation, "powered" for powered bases, "neutral" for armour.

#### CSWGuiPartySelection (partyselection.gui)

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x006bfa40 | `CSWGuiPartySelection::CSWGuiPartySelection` | 0x3a80 bytes; nine NPC records of 0x454 bytes from +0x7c | high |
| 0x00756d28 | `CSWGuiPartySelection::vftable` | 15 HandleInputEvent 0x006bede0, 18 OnPanelAdded 0x006beeb0, 19 OnPanelRemoved 0x006be490 | high |
| 0x0062dd20 | `CGuiInGame::ShowPartySelection(exitScript, bFromScript, forceNPC1, forceNPC2)` | from NWScript `ShowPartySelectionGUI` (routine 712, bFromScript 1) and the map's Party Select (0); only when the panel (`CGuiInGame` +0x78, created once) is not up, the party table's +0xf0 is -1, the PC is in an area and that area's +0x2ac is 0 or the call is from a script. From a script it pauses the game (unless +0xb38), plays GUI sound 4 and sets sound mode 4. Stores the exit script (+0x74), bFromScript (+0x70), the forced slots (record flag bit 2; +0x6c = 1) and the input class to return to (+0x64: 0 from a script, 2 from the map); `AddPanel` flags 3, input class 2 | high |
| 0x006beeb0 | `CSWGuiPartySelection::OnPanelAdded` | per slot from the party table: not available → the `LBL_NAn` overlay and no portrait; available → portrait, record bit 0 "can toggle"; not selectable → portrait at alpha 0.25 and bit 0 cleared. Without forced slots the current party members start selected (count +0x68 = the party size); with forced slots only those start selected (count = their number) and lose bit 0. Back is coloured disabled when opened from a script or with forced slots. Ends with tutorial popup 0x29 | high |
| 0x006bf2a0 | `CSWGuiPartySelection::OnToggleNPC` | BTN_NPCn 0x27/0x2d and BTN_ACCEPT (acts on the hilighted slot, +0x3a7c): a slot without bit 0 gives a message (below); selecting with two already selected does nothing; then `BTN_ACCEPT` reads Add (38455) or Remove (38456) and `LBL_COUNT` is refreshed | high |
| 0x006bf5b0 | `CSWGuiPartySelection::OnNPCHilighted` | `LBL_NPC_NAME`, `LBL_NPC_LEVEL` ("Level" 32154 and the level) and, in `LBL_3D`, the NPC's **portrait** `<portrait>3` (its `e` variant when GoodEvil, stats +0x17e, is below 50 and that texture exists), not a 3D model; an unavailable slot hides the three | high |
| 0x006bf3b0 | `CSWGuiPartySelection::OnDone` | BTN_DONE: confirm (from a script only) and apply; rules below | high |
| 0x006bec90 | `CSWGuiPartySelection::OnConfirmed` | message-box callback → apply | high |
| 0x006be560 | `CSWGuiPartySelection::ApplyAndClose` | removes the deselected members (player control off, `RemovePartyMember`), spawns the newly selected ones (`SpawnAvailableNPC`) by the leader (positions from the client party's formation slots and a walk-line test from the leader; the decompile does not show how they reach the spawn call, med), faces them like the leader, adds them as player-controlled members; then pops the panel, runs the exit script (with `CGuiInGame` +0xc04 set meanwhile), unpauses when +0x64 is 0, plays GUI sound 5 and resets the sound mode when from a script, and restores input class +0x64 | med |

Controls: per slot n = 0..8 `BTN_NPCn` (check box), `LBL_CHARn` (portrait), `LBL_NAn` ("not
available" overlay); `LBL_3D` (the hilighted NPC's portrait), `LBL_NPC_NAME`, `LBL_NPC_LEVEL`, `LBL_COUNT` +
`LBL_AVAILABLE` (members left to pick), `LBL_TITLE`, `LBL_BEVEL_L`/`R`/`M`, `BTN_ACCEPT`,
`BTN_DONE`, `BTN_BACK`. Slot n is NPC n of the party table (the nine `npc.2da`-style NPC indices).
(high)

Toggling a slot without the "can toggle" bit shows "The party member you have selected is
currently unable to join the party." (42376) or, for a forced member, "This character must be a
member of your party at this time." (42406). Done opened from the map applies at once. From a
script it counts the toggleable slots (bit 0), the forced slots (bit 2) and the selected slots:
with no toggleable slot, or two forced slots, it applies at once (and clears `CGuiInGame` +0x30);
otherwise it asks "You have less than 3 characters in your party.  Are you sure you wish to
proceed?" (38329) when at least two slots are toggleable and fewer than two are selected, else
"Are you sure this is the party configuration you want?" (38328), and applies on Yes
(`OnConfirmed`). Back or Escape (0x28/0x2e, GUI sound 0), opened from the map without forced slots,
puts every slot back to "selected = was a party member" and applies, so the party is unchanged;
from a script or with forced slots it shows "You cannot cancel from this screen at this time. You
must accept the required party configuration." (42405). The party size limit (two companions)
and the party table belong to party-items-saves.md. (high)

#### CSWGuiScriptSelect (scriptselect.gui)

The party AI style panel: the character sheet's Scripts button (BTN_SCRIPTS, event 0x29, GUI
sound 0) opens it as a modal (flags 3) for client party member 0, the party leader
(`CSWGuiCharacter::HandleInputEvent` 0x006b2250); that is the character the sheet shows as long as
switching characters there changes the leader (med: in the "view other NPCs" mode of §10.4 it
would not be). Ctor 0x006ea000 (vtable 0x007590a8, 0xc40
bytes), owned by the character sheet (+0x59f4). (high)

Controls (file `scriptselect.gui`, 640x480): `LST_AIState` (+0x70, the rows), `LB_DESC` (+0x350, the
description), `LBL_TITLE` (+0x770, "Script Selection", strref 42293), `BTN_Back` (+0x8b0, "Cancel",
1581), `BTN_Accept` (+0xa74, "Select", 236). The label at +0x630 is the description list's only
item: the description goes into its text and it is set as the list's item. The ctor reads
`aiscripts.2da` (label, `name_strref`, `description_strref`, `aistate`; shipped rows DEFAULT
1116/1109/0 "Default attack", GRENADE 1120/1112/4 "Grenadier", JEDI 1121/1114/5 "Jedi/Droid
support", the values of NPC_AISTYLE_*) and, for each row, builds a list item (0x006e9f10: a
0x2b4-byte check-box control with the name as its text) and keeps `{description strref, aistate}` in
an 8-byte-per-row table at +0x64 (count +0x68). Each item has two handlers: event 0 (hilight, from
the pointer or the up/down keys) 0x006e9fe0 -> 0x006e9d50, which clears `LB_DESC` and puts the row's
description in it; event 0x27 0x006e9e70, which is Accept. (high)

`CSWGuiScriptSelect::SetCreature` (0x006e9ca0) stores the creature id (+0xc3c; no such creature:
`OBJECT_INVALID` and nothing else) and walks the rows:
the one whose `aistate` equals the creature's AI state (creature stats +0x13a, a short) gets its
check box state (+0x1c8 bit 0) set and `SetSelectedIndex` (so event 0 shows its description), the
others are cleared. No match: nothing is selected and the description stays empty. Accept
(`HandleInputEvent` 0x006e9bc0: 0x27/0x2d) writes the selected row's `aistate` into stats +0x13a,
plays GUI sound 0, pops the modal and marks the panel for removal; the item handler 0x006e9e70 does
the same without the sound; 0x28/0x2e (BTN_Back through `OnButtonCancel`, Escape) play the sound,
pop and remove only. BTN_Accept is the `OnButtonAccept` thunk, i.e. the same 0x27 sent to the
panel. `OnPanelAdded` 0x006e9b90 asks for
tutorial popup 10 (`ShowTutorialPopup`; ours has no tutorial popups). (high)

So the list is a set of one-click buttons: a click on a row (or Enter on the selected one) chooses
it and closes the panel; Select takes the selected row, which opens as the creature's own. The
description follows the hilighted row.

**Is it saved?** Yes. `CSWSCreatureStats::ReadStatsFromGff` (0x005afce0) reads the INT `AIState`
(at 0x005b067a) with the stats value as its default, and `CSWSCreatureStats::SaveStats`
(0x005b1b90) writes it (at 0x005b22a4), both right after `ChallengeRating`. A UTC may carry it
too. Ours: `lib/save/objects.ctx` `write_creature` and `lib/engine/templates.ctx` `read_creature`
(INT `AIState` <-> `obj::Creature.ai_style`). (high)

What the style does: `k_inc_generic`'s `GN_DetermineCombatRound` reads `GetNPCAIStyle(OBJECT_SELF)`
(stats +0x13a) and uses it for any creature other than the party leader (`GetPartyMemberByIndex(0)`)
outside restrict mode, after the force-field, resistance, Malak and boss checks: 4 runs
`GN_RunGrenadeAIRoutine` (always for a party member, half the time otherwise;
`GN_FindGrenadeTarget`: in a 40 m sphere, a seen living creature with more enemies within 4 m than
the minimum, 1 for a party member and 0 otherwise, and no friend within 4 m, the one with the most
enemies; then `GN_GetGrenadeTalent`, talents 87..95, used through `ActionUseTalentOnObject`; no
target or talent: the default attack), 5 `GN_RunJediSupportAIRoutine`, 0 the default attack.

Ours: `lib/ingame/scriptselect_panel.ctx`, opened by the sheet (`character_panel`) as a modal
over it, with the rows as click rows (`gui::set_click_rows`: press selects and shows the
description, release activates); the check box state is the row's `checked`. `--log combat`
prints `ai style: NAME old -> new` when a row is chosen. Checked headless on the Upper City
checkpoint: the panel with the description of the selected row, the description following the
pointer and the down key, a click, Enter and Select choosing, Cancel and Escape leaving the style,
`GetNPCAIStyle` answering 4 in Carth's combat rounds (`--log routines`), and the style surviving a
save and load.

Found while testing a Grenadier with two Sith troopers close together: whether the grenade is
thrown hangs on the shape iteration. The original keeps the cursor of
`GetFirstObjectInShape`/`GetNextObjectInShape` in the area (`ExecuteCommandGetFirstObjectInShape`
0x0054a260: index in +0x19c) and walks the area's array of creatures (+0x190, count +0x194),
which is kept sorted by position X (the first call binary-searches it, 0x00506f20, for the shape's
lowest X, and the walk stops at its highest X). `GN_FindGrenadeTarget` runs two more shape loops
inside its own, so in the original too its outer loop ends after the first seen creature in
ascending-X order. Ours matches this: `lib/engine/routines/objects.ctx` `get_in_shape` collects the
matches once on `GetFirstObjectInShape`, sorts them by X then id, and every call (the nested loops
included) hands out the next one from that one walk. (Walking in creation order instead made the
first seen creature the oldest bystander, the Upper City's id 481, with Carth within 4 m of it, so
the routine fell through to the default attack.)

### 10.5 Conversation and pazaak panels

#### Conversation panels (`CSWGuiDialog` and subclasses)

Base constructor 0x006a85b0 (vtable 0x007559e0); flow and cameras: dialogue.md. The panel side
(high unless noted):

| Panel | Ctor / vtable / size | `.gui` | Held at |
|---|---|---|---|
| Conversation (letterbox) | 0x006a8b40 / 0x00755800 / 0x1e00 | `dialog` (`LBL_MESSAGE`, `LB_REPLIES`; reply colour the menu text colour) | `CGuiInGame` +0x40 |
| Computer | 0x006a8eb0 / 0x00755888 / 0x3620 | `computer` (`LB_MESSAGE`, `LB_REPLIES`, `LBL_OBSCURE`, `LBL_STATIC1..4` at alpha 0.4, skill/spike/repair labels `LBL_COMP_SKILL`/`_ICON`/`_VAL`, `LBL_REP_SKILL*`, `LBL_COMP_SPIKES*`, `LBL_REP_UNITS*`, the two skills' names and icons from the rules' skill table; reply colour (0.67, 0.56, 0.87); a `computer_lp_04` loop sound at volume 30) | +0x44; made by `CreatePanels` only when 0x007a2370 is set, else on first use by `SetDialogPanelType` 0x00628670 |
| Computer camera | 0x006a95f0 / 0x00755958 / 0x2080 | `computercamera` (`LBL_RETURN`, centred 75 px above the bottom; the panel is sized to the screen) | +0x48 |

`CGuiInGame` +0x3c is the current conversation panel: `SetDialogPanelType` sets it to the computer
panel for type 1, else to the letterbox.

- **Replies**: `LB_REPLIES` rows hilight yellow on hover (0x006a6fc0) and return to the panel's
  stored reply colour (+0x1de4) when left (0x006a6fe0).
- **Input** (`HandleInputEvent` 0x006a7230, shared; the computer panel's own 0x006a81e0 first
  turns 0x39/0x3a into 0x31/0x32 on `LB_MESSAGE`, a scroll): the dialogue number-key actions
  (0xfe..0x106, `Dialog1..9`) pick reply *n*-1 if it exists (GUI sound 0); Enter/click (0x27,
  0x2d) picks the selected row of `LB_REPLIES` while replies are shown; while only an NPC line is
  shown (flag +0x1df8 bit 0, without bit 1) 0x27, 0x2d or 0x1f9 (the double-click code, which in
  input class 3 every panel also gets on a left press, render-gui.md) instead asks the server to
  **skip the current line** (`CServerExoApp::RequestDialogSkip` 0x004ae970 with the speaker's id
  at +0x19c0); 0x31/0x3d and 0x32/0x3e move the panel's index +0x68 within the reply count +0x6c.
  While a line is shown only events 0 and 1 reach the controls.
- **Choosing a reply** (slot 27; letterbox 0x006a7e20, computer 0x006a7110): when the index is
  below the reply count, `CGuiInGame::SetPendingReply` (0x0062ada0) and `SelectDialogReply`
  (0x006339c0) send it on; the letterbox then empties and removes its small top-bar text panel
  (+0x1dfc, dialogue.md 9.6).
- **Layout** (slot 28; letterbox 0x006a7ef0): the conversation panel spans the screen width less
  a margin on each side, 100 px high; it positions the in-game
  GUI's lower letterbox bar panel (+0x64, dialogue.md 9.6) and `LBL_MESSAGE` from the screen size
  and empties the message. (med)
- The computer panel's type is a `comptypes.2da` row (0 Standard, 1 Rakata; an out-of-range type
  becomes 0), set by 0x006a8400 from `SetDialogPanelType` into byte +0x48; the same call sets the
  panel's own fill to the row's `ComputerBackground` (`panel01`, `panel02`). Its `GetResolutionTag`
  (0x006a6e20) appends that byte as a digit to `comp`, so the backdrop is `WxHcomp0` / `WxHcomp1`.
  Its `OnPanelAdded` / `OnPanelRemoved` overrides (0x006a6de0 / 0x006a6e00) start and stop the
  loop sound.

#### Pazaak — skimmed

| Panel | Ctor / vtable | `.gui` | What |
|---|---|---|---|
| Side-deck setup | 0x00681a90 / 0x007532e8 / 0x8928 | `pazaaksetup` | `LBL_TITLE`, 18 available cards `BTN_AVAILxy` with `LBL_AVAILxy` and counts `LBL_AVAILNUMxy` (3 rows × 6), 10 chosen slots `BTN_CHOSEN0..9` / `LBL_CHOSEN0..9`; `BTN_ATEXT` (Play, enabled once ten cards are chosen, +0x7600), `LBL_LTEXT`, `LBL_RTEXT`; card hover 0x0067e530, click 0x006807e0, Play 0x006819e0: with ten cards "Are you sure you want to use this sidedeck?" (32322) and on Yes 0x00681890, else "You must select ten cards..." (38630). Opened by 0x005f3810, the client's start-pazaak handler (from `PlayPazaak`, routine 364): it caps the wager at the leader's gold, sets sound mode 4, adds the panel with flags 3, input class 2, GUI sound 4. The ctor builds the wager panel only when the wager is above 0 |
| Wager | 0x0067f000 / 0x007534c8 / 0xcac | `pazaakwager` | `LBL_TITLE`, `LBL_BG`, `LBL_WAGERVAL`, `LBL_MAXIMUM`, `BTN_LESS`/`BTN_MORE` (repeat buttons, vtable 0x007533c8: a held left button sends 0x16256 every 1/15 s, wired to the 0x2f/0x30 thunks), `BTN_WAGER` (0x2d thunk), `BTN_QUIT` (`SendCancel`, 0x28) |
| Game | 0x006808a0 / 0x00753358 / 0x86e8 | `pazaakgame` | 9 table slots per side `BTN_PLR0..8`/`BTN_NPC0..8` with labels `LBL_PLRn`/`LBL_NPCn`, 4 hand cards each `BTN_PLRSIDE0..3`/`BTN_NPCSIDE0..3` with labels, `BTN_FLIP0..3` (± flip), `LBL_FLIPICON`/`LBL_FLIPLEGEND`, `LBL_PLRNAME`/`LBL_NPCNAME`, `LBL_PLRTOTAL`/`LBL_NPCTOTAL`, `LBL_PLRSIDEDECK`/`LBL_NPCSIDEDECK`, set scores `LBL_PLRSCORE0..2`/`LBL_NPCSCORE0..2`, turn markers `LBL_PLRTURN`/`LBL_NPCTURN`, `BTN_XTEXT` End Turn / `BTN_YTEXT` Stand (with the tutorial on, End Turn above 15 asks 38641 and Stand below 14 asks 38640); sounds `mgs_startturn`, `mgs_drawmain`, `mgs_playside`, `mgs_warnbust`. Opened by 0x00681890 (the setup's Yes): it copies the ten chosen cards to the party table (+0x168..+0x18c, the remembered side deck) and to the game state, pops the setup panel and adds the game panel with flags 3 |

The setup and game panels are full-screen with the `WxHpazaak` backdrop (byte +0x48 = 2; the
wager panel's ctor does not set it). The rules, the
game panel's state machine (0x00680030) and how the result returns to the script (0x005f3950)
are in [pazaak.md](pazaak.md). (high for the tags, addresses and the handlers named here)


## 11. Open questions

**System (§1–§9)**

- The `INNEROFFSET` text rectangle grows by `INNEROFFSET` vertically but by
  `min(INNEROFFSET, thickness)` horizontally (0x00415240). Solved: the disassembly confirms the
  asymmetry (y and height use +0x18 itself, x and width the smaller of +0x18 and the thickness).
- `spacingR` is applied twice-scaled by the viewport in the glyph advance (0x0045a850) but in full
  in the width measurement: it looks like an engine bug; check on screen with `fnt_console`
  centred text before reproducing it.
- Panel flag 0x10 (`AddPanel` flag 4, used for the global fade) only keeps a panel out of the
  manager counter +0x71, and the client main loop (0x00602eb0) reads that counter only when it
  takes a screenshot: a non-zero count (or a client flag) sets the second argument of
  `Render_TakeScreenshot`. What that argument changes was not traced.
- The list box "one text" mode (flag 0x100, 0x00419ee0), the pixel-scroll mode (0x0041a2d0), the
  "select on press" and "scroll only" flags, and scroll-bar thumb dragging (0x0041b670) were not
  read in detail; the click zones of the scroll bar and slider are inferred.
- The 150 ms debounce on events 0x2f..0x32 in `CSWGuiManager::HandleInputEvent`: an edit box
  makes those codes from characters 0x1c..0x1f (render-gui.md, input event codes); whether the PC
  key map also produces them is not settled.
- Which key produces event 0xb5 (hard-wired to key 6) and whether 0xb4 is registered anywhere (the
  manager remaps 0xb5 to 0x27 and 0xb4 to 0x28, render-gui.md).
- The overlay drawn by `CSWGuiManager::DrawDebugOverlay` (0x0040bec0) when 0x007a3d4c is set.
  Solved: nothing writes 0x007a3d4c (the manager's `Render` read is its only reference), so the
  overlay never shows (render-gui.md).
- The cursor meaning of ids 47–50 (create) and of the 32 running/walking arrows (61–92); the
  cursors the hover code picks (movement.md 7.2) do not include them.

**Front end and character generation (§10.1, §10.2, §10.5)**

- How `PB_PROGRESS` values are composed from the per-phase byte weights at client +0x3e4 (10, 20,
  23, 23, 23, set at start-up, app.md; read by `GetLoadPhaseWeight` 0x005edff0 from the area,
  module, save and panel loaders).
- The movies list rule (`movies.2da` `alwaysshow` versus "seen") and how a movie is played from
  `LB_MOVIES`.
- Credits text source and scroll speed (0x0068f880).
- Save/load list contents (which fields the rows and the details labels show; 0x006cc160).
  Solved: [party-items-saves.md](party-items-saves.md) 1.5. Still open: the save-name rules
  (maximum length, allowed characters beyond the edit box's).
- Per-option mapping of every options control to its client option field and ini key
  (0x0061b780 writer / 0x0061dbe0 loader, which applies the defaults 0x0061da60 first; app.md
  lists the mouse and camera fields); only the panel wiring was read.
- Character generation: what quick generation fills in, the random name tables, the portrait
  list filter, how the class-selection slot table's class bytes are filled, the skills, feats and
  powers steps, and the message sent to start the game (0x006dbdf0). Solved:
  [chargen.md](chargen.md) (A "The slot table", C.4, C.5, D, E, G, H, I) and
  [chargen-creature.md](chargen-creature.md) (`StartGame`).
- Pazaak panels: how they drive the mini-game state and return the result. Solved:
  [pazaak.md](pazaak.md) (the game panel's state machine 0x00680030, the result 0x005f3950).
- Conversation panels: the computer panel's skill/spike/repair counters, the exact letterbox
  geometry (0x006a7ef0, outlined in §10.5) and how `LB_REPLIES` is filled.

**In-game GUI and HUD (§10.3)**

- Which condition turns a party member's vitality bar `redfill` (`0x006857d0`'s third argument).
  Solved from the disassembly of both calls in `0x00687860`: `GetMaxHitPoints` and
  `GetCurrentHitPoints` take one argument each, so the call is SetVitality(current HP, maximum HP,
  creature +0x9e0), and +0x9e0 is the poisoned flag ([rules.md](rules.md) 1.9): the bar is
  `greenfill` while the creature is poisoned and `redfill` otherwise.
- The action-list builder `0x00619db0` (what goes into categories 0..5) and the target list
  builder `0x00689410` were not read; they decide what the action slots offer.
- `UseSelfAction` clears the leader's actions after queuing outside combat; the order relative to
  the callback looks odd and should be checked in the disassembly.
- `CGuiInGame+0xb4` (blocks menus). Solved: it is the conversation-pending flag, set when a
  conversation is requested and read by `GetIsConversationActive` ([dialogue.md](dialogue.md) 2.2
  and the routine table).
- The overlay list at HUD `+0x5cb4` (updated and drawn every frame) is the floating labels:
  damage, healing, "miss", "XP n" and "Level n" over the creatures (the "Floating Numbers" option,
  bit `0x10` of the client options' dword at `+0x14`). Solved: [combat.md](combat.md) section 10.4.
- `LBLH_INV` pulsing condition (quest item repository count) is a guess.
- How the message log lines reach `LB_MESSAGES`: the client formatter adds each line to the in-game GUI's
  array at `+0xf8` with `0x0062b5c0`; `OnPanelAdded` copies it into the list (`0x00626920`, red rows
  for kind byte 1). Solved: [combat.md](combat.md) section 10.1. How `LB_DIALOG` is filled (the
  array at `+0xfc`, `0x00626b10`; the row format is in [journal.md](journal.md), "The message
  log") is still not traced.
- `CSWGuiMessageBox` slot 32 (`0x006252a0`) runs on close; not read.

**In-game menus (§10.4)**

- The server flag at server internal +0x10004 → +0x104 bit0 that switches the menus from
  "change leader" to "view other NPCs" is not identified. It is not player restrict mode, which
  is the current area's +0x2b0 (`GetPlayerRestrictMode` 0x0053cf70, `SetPlayerRestrictMode`
  0x00543450); no writer of the bit was found ([party-items-saves.md](party-items-saves.md)).
- Which input raises event 0x2e (0xdf is Escape, key-map action 223; 0x2e looks like a gamepad
  back button and is not produced by the PC key map); 0x2d closes menus here but accepts in the
  galaxy map, party selection and upgrade screens.
- The meaning of equipment row states 2 and 3 on screen (colour) and of the `LBL_GOOD1..10` icon
  list on the character sheet.
- The character sheet's model-rotation event codes. Solved: `BTN_3DCHAR` is a repeat button
  (vtable 0x007533c8): a left press sends it event 0x16256 and a right press 0x16257
  (0x0067e800 / 0x0067e830), repeated while the button keeps the mouse (its `Render` 0x0067e860);
  the sheet's handlers are `RotateModelLeft` on 0x16256 and `RotateModelRight` on 0x16257.
- Map: the map-view object at +0xe38 (world-to-map transform, note picking by click) and the
  Return action 0x00692bc0 were not read.
- Store buy/sell confirmation texts and the stock/infinite handling in `DoBuy`/`DoSell`. Solved:
  [party-items-saves.md](party-items-saves.md) 5.8.
- Journal quest list contents (which JRL fields, how priority and planet sorting are computed).
  Solved: [journal.md](journal.md) ("The client journal", "Sorting").

