# Graphics options and modern displays

What the Graphics and Advanced Graphics panels do in the original, what they do here, and how the game
copes with the screens people have now (1440p, 4K, ultrawide, 144 Hz, Windows display scaling). The code is
`game/display.ctx` (the options made real), `lib/frontend` (the panels), `lib/platform/sdl.ctx` (windows and
displays), `lib/render_gl/gpu.ctx` (the device), `lib/scene/grass.ctx`. Status words: **matches** (checked
against the original's code or strings and run), **ours** (the original has nothing like it), **partial**
(some of what the original does).

## How an option reaches the screen

The panels edit `frontend::Settings`; the engine calls `display::apply` after every change, which makes the
device agree with it and does only what differs from the last call (all of it the first time), so every option
applies **live**. In the original only the Graphics panel is live: its brightness slider, Shadows and Grass call
their setters from the panel's handlers (`0x006ded30`, `0x006dedb0`, `0x006dee00`). Its Advanced panel keeps its
choices in the panel until Back (`0x006e01c0`), which then calls every setter (`0x006defe0`: anti-aliasing, texture
quality, frame buffer, anisotropy, V-Sync, soft shadows) and, when anything but V-Sync changed, makes the window
and the GL context again (`SetVideoMode` `0x00403800`); its Cancel throws the choices away. Ours applies the
Advanced panel live too, and its Cancel puts back the options the panel opened with. Closing a panel writes our
own options file (`kotor/out/kotor-settings.ini`, `--settings FILE`; never the install's `swkotor.ini`) with the
original's section and key names (except `Refresh Rate`, ours; `Anisotropy` and `Anti Aliasing` hold our steps
0..3, where the original's hold the tap and sample counts).

A window run reads the file for its size, mode and options (`--size` overrides the size and makes it a window). An
offscreen run (`--headless`, `--no-render`) uses the defaults for the graphics keys, so logs and pictures repeat
whatever file is lying about, unless `--gfx` asks for the file. `FRAME gfx KEY VALUE` input lines set an option from
a script (`size W H`, `mode windowed|borderless|fullscreen`, `refresh`, `vsync`, `brightness`, `shadows`,
`softshadows`, `grass`, `emitters`, `framebuffer`, `aniso`, `aa`, `texture`, `scale`, `limit`, `blur`, and the
Enhanced Graphics panel's words in [../design/enhanced-render.md](../design/enhanced-render.md)); they work in the
front end and in a game and never write the file themselves.

The **Enhanced Graphics** panel (ours, under Advanced Options on the Graphics panel) switches the modern effects:
bloom, room light on characters, shadow maps, occlusion, smooth lightmaps, depth of field, reflections, light
shafts, height fog, colour grades, edge smoothing, foliage anti-aliasing, tessellation, and an Original Look that
turns them all off. See [../design/enhanced-render.md](../design/enhanced-render.md).

Its **Lightmaps** row (key `Lightmaps`, `gfx lightmaps 0|1|2`) is Original, Smooth or Lifted (the default). Lifted
(ours) is Smooth plus a soft floor under the rooms' baked light: a texel baked black draws at 0.12 instead of 0,
fading out by 0.25, so a dead end the original leaves pitch black (the Endar Spire's corridor ends) shows its walls,
dark, while ordinary shadows stay as they are. Original and Smooth, and Original Look, keep the original's black.

## The panels, option by option

| Option (panel) | Original | Ours | State |
|---|---|---|---|
| Brightness slider (Graphics), key `Brightness` | The handler (`0x006ded30`) turns the slider `v` (0..100) into the exponent `2 - 1.77 v/100` and loads a 3 x 256 gamma ramp (the same curve for red, green and blue) with `SetDeviceGammaRamp` (`SetGamma 0x0044d990`: `out = in ^ exponent`), live; put back to 1.0 when a full-screen window is deactivated (display slot 6, `0x0044d8d0`) and set again on activation. 57 (the default, `0x0061da60`, and the install's value) is the exponent 0.99, the picture as drawn | The same curve as a shader in `present` (the picture, movies and GUI together, as a hardware ramp does), live; screenshots apply it too. 56 and 57 are left alone (a plain blit). Default 57 (ours was 50, 1.115: a darker game than before). Needs no display ramp, so alt-tab cannot leave the desktop dark | matches |
| Screen Resolution (Graphics) | A list of the display's 32-bit modes of five sizes only, 800x600, 1024x768, 1280x960, 1280x1024 and 1600x1200 (the sizes of its GUI files, `0x005f0c60`), rows `%d x %d` (a mode with no refresh rate given) or `%d x %d @ %d Hz` (60 Hz and up; above 85 Hz only with `AllowHighMonitorFrequency` = 1), built by `0x006e0710`. OK (`0x006df690`) writes `Width`, `Height` and `RefreshRate` to swkotor.ini at once and applies the mode through `ChangeVideoMode` (`0x005f1830`), which makes the window and the GL context again (`SetVideoMode`) and lays the GUI out again. At start an ini size outside the five becomes 800x600 and a refresh rate below 60, or above 85 without `AllowHighMonitorFrequency`, becomes 60 (`0x005f0ce0`) | The list is SDL's: `windowed` the sizes that fit the desktop, `borderless` the sizes up to the desktop's (a smaller one is rendered small and scaled up with bars), `fullscreen` every size and refresh rate; the current size is always a row. The button shows `Screen: W x H` (`Screen: Desktop` for a borderless window at the desktop's size). Applied at once and written to the file; a full-screen mode the display refuses becomes borderless | matches, modern list |
| Display Mode (Graphics) | No control on the panel. `FullScreen` 0 (written back when the key is missing) asks for a window, but `ChangeVideoMode` gives one only when `AllowWindowedMode` = 1 (default 0) and the mode is smaller than the desktop both ways, else full screen; with `AllowWindowedMode`, Alt+Enter toggles windowed and full screen (`0x00401e90`, re/app.md) | A button: Windowed, Borderless, Fullscreen (key `FullScreen` = 0, 2, 1). Windowed is a resizable window centred on its display, no larger than the room it has; Borderless is a window over the desktop at its resolution; Fullscreen switches the display's mode | partial (the button and Borderless are ours; Alt+Enter does nothing) |
| UI Scale (Graphics) | none: the GUI is never scaled (re/gui.md) | A button: Auto, 100%, 125%, 150%, 175%, 200%, 250%, 300%, 400% (key `GUI Scale`, 0 is auto). Auto is the largest quarter step at which the 800x600 main menu fits the window (1080p 175%, 1440p 225%, 4K 350%), so panels, HUD, conversations and text stay readable. Everything lays itself out again at once | ours |
| Shadows (Graphics) | Flag `0x0078e3a8` (setters `0x0044ee20` / `0x0044f080`; off also clears soft shadows); stencil shadow volumes (`GL_DrawShadowVolume`) drawn by `CAurScene::RenderSoftShadows` (`0x00451a50`), which `CAurScene::RenderPasses` (`0x004514f0`) runs only while the flag is set, from the scene's shadow-casting light | Off: no shadow is drawn. On: each creature casts the meshes its model flags (`Mesh.shadow`) onto the walkmesh face under it, from the nearest light that reaches it and hangs at least 0.5 m above its feet, else from the sun overhead; the area's `ShadowOpacity` (50 or 205 in the data) is how dark. (Nothing submitted a shadow before: the option had nothing to switch) | partial (planar, creatures only) |
| Soft Shadows (Advanced) | Flag `0x0078e420` (setters `0x0044ee50` / `0x0044ee60`; on also sets Shadows, and Shadows off clears it); `CAurScene::RenderSoftShadows` (`0x00451a50`) blurs the shadows through a pbuffer (`0x0042d1c0`, `0x0042d9a0`) | Twelve projections from points of a 0.5 m area light, each darkening by the share that makes the core as dark as one hard shadow: a limb far above the floor gets a wide penumbra, a foot a sharp one. Not tied to Shadows: on with Shadows off draws nothing | partial (different technique; does not switch Shadows on) |
| Grass (Graphics) | Flag `0x0078e3ac` (setters `0x0044ee30` / `0x0044ee40`; read by the grass draw `0x00450150`); the ARE's `Grass_TexName`, `Grass_Density`, `Grass_QuadSize`, `Grass_Prob_*` on faces whose surface material has the grass flag (17 areas: Dantooine, Kashyyyk, Manaan, the Unknown World, one Taris area) | Tufts planted once per face by a hash (density a square metre, one of the texture's four quarters by the four probabilities), the ones within 26 m drawn each frame as one punch-through emitter that turns about the vertical, shrinking over the last 7 m; `WindPower` sways them. The option drops them | matches in kind (the original's blade geometry and wind are not known) |
| Emitters (Graphics, ours) | `dialog.tlk` 47958/47959 describe it ("blaster bolts and certain force powers") but the executable never reads an `Emitters` key (the install's swkotor.ini has the line) and the panel has no box | A check box (key `Emitters`) that drops every visual-effect emitter (not grass): the effects' and the world's (rooms', placeables', doors', creatures'), which then are not stepped either ([../design/vfx.md](../design/vfx.md), "World emitters") | ours (the original's world emitters always run) |
| Anti-Aliasing (Advanced) | Off, 2, 4, 6 or 8 samples, each offered only when the driver has a multisample pixel format for it (`0x006e0520`, `0x006e05e0`; the control is greyed when none). `Render_SetAntiAliasing` (`0x0044f2f0`) stores the count; it takes effect when the GL context is made again (`SetVideoMode`, `0x00403800`): `wglChoosePixelFormatARB` with N samples. The Advanced panel's Back does that itself, and start-up does when the ini asks for samples | Off, 2x, 4x, 8x: the screen and the GUI's render targets are multisampled renderbuffers resolved into their textures, so it applies live and covers the main menu's 3D scene too (capped at what the driver has) | partial (no 6x step), live |
| Anisotropy (Advanced) | `EXT_texture_filter_anisotropic`: Off, 2x, 4x, 8x, 16x (doubling up to the driver's maximum, `0x006e06d0`), stored by `0x0044f2c0` and applied when a texture is bound (`GL_BindTextureCached` `0x00420440`, `CAurTexture::Bind` `0x004204f0`) | Off, 2x, 4x, 8x on every mipmapped linear texture, including those already made, live (it was fixed at 8x) | partial (no 16x step) |
| Texture Quality (Advanced) | The row of `texpacks.2da` (`0x0061d730` -> `0x005ed8f0` -> `0x005f14a0`): the pack `swpc_tex_tpc` (low, quarter size textures), `tpb` (medium, half), `tpa` (high) is mounted at `TEXTUREPACKS:` (with `swpc_tex_gui`). Before mounting, every resident texture is released (`0x00421d50`); `AurTextures_SetQuality` (`0x00421d90`) then sets the video-memory budget of the row (`Mem` times `DynMemRatio`), not a resize, and loads every texture again at once from the new pack (needs a runtime check) | The pack is mounted again and the area's scene is loaded again from it, so the change shows at once (a menu scene is not). Default High | partial (a menu scene keeps its textures) |
| V-Sync (Advanced) | `Render_SetVSync` (`0x0044ee90`), `wglSwapIntervalEXT` when the driver has it | `SDL_GL_SetSwapInterval(1 or 0)`, live. Off, the loop runs as fast as it can (about 1000 frames a second at 4K on the test machine) | matches |
| Frame Buffer Effects (Advanced) | Flag `0x0078d98c` (`0x0061d750`, which also swaps each party member's client effect 8000 for 8002 or back); `Render_ApplyScreenEffects` (`0x00437520`) copies the screen into a texture and runs passes; `dialog.tlk` 47957: "per pixel flares, noise, and speed blur" | **Speed blur**: while the leader moves faster than it walks (Burst of Speed, Force Speed, haste: the rules' speed factor above 1.2) a radial blur, eased in and out, goes over the 3D picture (not the HUD). Off, none | partial (flares and film noise are not drawn: no light we model carries flare data we draw, and nothing in the data says when the noise shows) |
| Default (each panel) | Graphics (`0x0061d9a0`): Brightness 57 (applied at once), Shadows and Grass on; it only stores those two, so their render switches keep their old state until set again (needs a runtime check). Advanced (`0x0061d520`): Anti-aliasing off, Texture Quality Low, Anisotropy off, Frame Buffer Effects on, V-Sync off, Soft Shadows on, shown on the panel and applied by Back | Resets them to our defaults (Advanced: Anti-aliasing off, Texture Quality High, Anisotropy 8x, Frame Buffer Effects on, V-Sync on, Soft Shadows off), live, and the UI scale and Emitters of the Graphics panel; not the resolution or the display mode | partial (our Advanced defaults differ: see Decisions) |

Also read from the file, not on a panel: `Refresh Rate` (ours: Hz for full screen, 0 the display's highest; the
original's key is `RefreshRate`) and `Frame Limit` (frames a second at most, 0 none; the loop sleeps a millisecond at a
time, then spins for the last 1/600 s; the minigames' own loops do not use it).

The description pane on the right of the two panels, empty before, shows the original's own text, as the original's
does for the control under the pointer (`0x006dee40`, `0x006df390`): the string after each label in `dialog.tlk`
(Shadows is 47950, its explanation 47951), and ours for the brightness slider and the buttons the original lacks.

## Modern displays

- **Resolution list and modes**: from `SDL_GetDisplayMode` of the window's display (167 on the test machine, from
  640x480 to 4K at 144 Hz), the desktop's mode and `SDL_GetDisplayUsableBounds` (the room a window has, less the
  task bar). 16:9, 16:10, 21:9, 1440p and 4K appear as the display offers them. A window larger than its display
  shrinks to fit it; leaving full screen is done before the room is measured (a 1280x720 full-screen mode makes the
  desktop look 1280 wide).
- **Window, drawable, render**: three sizes. The window is in the OS's units (what the mouse reports; half the pixels
  on a Retina display), the drawable in pixels, the render size is what the game draws at (the screen target). It is
  the drawable, except in a borderless window asked to render below the desktop's size: `present` then scales it up
  with its aspect kept and bars around, and `display::map_event` undoes window units, drawable and bars for the mouse.
- **Windows display scaling**: SDL is told `SDL_WINDOWS_DPI_AWARENESS=permonitorv2` before it starts, so a 150% desktop
  gives real pixels (without it Windows reports a smaller screen and stretches ours). macOS gets pixels from
  `ALLOW_HIGHDPI`. Untested on real HiDPI hardware here (this machine's desktop is 4K at 100%); the mapping is code.
- **Field of view**: the camera styles' `viewangle` is the vertical angle (`CAurCamera::SetFieldOfView`, gluPerspective's
  `fovy`, re/movement.md) and the projection takes the window's aspect, so a wider window sees more to the sides (Hor+, no
  stretching): for the default 55 degrees, 69.5 across at 4:3, 85.6 at 16:9, about 102 at 21:9. The GUI 3D views (main
  menu, character generation) and the dialogue cameras use the aspect of their own viewport.
- **GUI and HUD**: the GUI scale (above) sets the pixel space the panels are placed in; the HUD file is the largest
  of the original's five that fits that space and its controls are anchored to the screen edges, so the minimap stays
  top left and the action slots bottom right at any size or aspect. Backdrops of the store, pazaak and map are drawn at
  their own resolution, centred, with black round them (docs/design/gui.md).
- **Main menu and movies**: the 3D scene fills the 800x600 panel's rectangle (letterboxed black on a wide window);
  movies keep their aspect with bars (lib/frontend/movie).
- **Resize, focus, minimise**: a resized window makes the device follow the drawable and every interface (the front
  end, the HUD, the conversation panels, the pazaak table, the loading screen) lays itself out again; the GL context
  and every resource are kept (the window is never remade). A minimised window is not drawn into and the loop rests.
  The game already pauses when focus is lost.
- **The OS pointer** (The original, with `EnableHardwareMouse` = 1, the value it writes when the key is missing and the
  install's, shows Windows' own pointer with the game's cursor images from the executable's resources; only with 0 does
  it hide Windows' cursor and draw its own (`SetHardwareCursorHidden` `0x005e1740`, read by `0x005f1c20`, re/app.md).
  It does not confine the pointer in a window.) Ours always draws its own, as the original does with 0:
  `display::apply` hides the OS pointer (`SDL_ShowCursor(0)`) the first time it runs, so the front end, the loading
  screens and a game all start without it; SDL holds the state through mode switches (windowed, borderless, full
  screen, both ways), minimise and restore. The pointer shows again over a windowed window's title bar and border (the
  frame is the OS's) and wherever it leaves the window; it is never confined, so a second monitor stays reachable from
  a borderless window. (Before this the front end never hid it: the main menu and every options panel showed Windows'
  arrow under the game's own, in every mode; only a game in progress hid it.) The log's `display:` line says
  `OS pointer hidden`. `kotor/tools/py/pointer_probe.py` watches what Windows draws over a real window through mode
  switches, minimise and focus moves. SDL moves the real pointer to the same window-relative place when a window
  changes size or place, so the game's pointer stays under it; `display::map_event` undoes the window, the drawable
  and the bars of a borderless window that renders below the desktop's size (checked with the real pointer: 2176,1332
  on a 3840x2160 desktop with a 1440x1080 render is 848,666, the Options button).
- **Labels of our added buttons** keep the margins of the original's: the original's buttons leave 17 to 25 pixels
  either side of their text (dialogfont16x16: "Frame Buffer Effects" in 240 leaves 18, "Texture Quality" in 200
  leaves 24), so ours take at most 204 pixels in the Graphics panel's 240: `Screen: 3840 x 2160` (200),
  `Display: Borderless` (184), `UI Scale: Auto 350%` (200), `Enhanced Graphics` (176). The Enhanced Graphics rows are
  218 wide between their arrows (the original's were 198) for the longest, `Lightmaps: Original` (176, 21 either side).
  Before, `Display Mode: Borderless` took 239 of 240 and `Resolution: Desktop (3840 x 2160)` 327. Seen at 1.0, 1.5,
  2.25 and 3.5 in all three modes (widths from the font's TXI, counted the way `gui::glyph_width` does).
- **Frame rate**: the simulation runs on the measured frame time, clamped to 0.25 s, never on a count of frames. Checked
  with `--dt` at 1/30, 1/60, 1/144 and 1/240 s (below).

## Checking it

| Check | How | Result |
|---|---|---|
| Walking is frame-rate independent | `kotor/tools/gfx/scripts/walk.txt` from the apartment checkpoint, leader's place after 1.5 s and 3.0 s world time at four steps | x = 85.3042..85.3046 and 82.2125..82.2137 (0.5 mm) at 30, 60, 144, 240 fps |
| Animation, emitters, camera | the main menu scene at world time 3 s at 30, 144, 240 fps; the opening cutscene at 20 s at 30, 60, 144, 240 | menu scene: 1 pixel differs (a random mist particle); the cutscene's camera and poses agree (a character a tick or two ahead at 30 fps: scripts act on tick boundaries, 33 ms against 4 ms) |
| World emitters and the Emitters option | `sh kotor/tools/gfx/world_emitters.sh EXE`: a fresh Endar Spire, the camera on the corridor's south dead end, the option on then off | on: 1 emitter, 244 particles (the room's smoke); off: none drawn |
| Real time, uncapped | a window with V-Sync off, 6000 frames | 0.84 ms a frame (1180 fps), world time equals wall time; with `limit` the loop keeps to the rate |
| 4K, everything on | a borderless 3840x2160 window, 8x MSAA, 8x anisotropy, soft shadows, V-Sync off | about 1000 frames a second on an RTX 4090 |
| Window modes | `scripts/window_modes.txt` in a real window: windowed, borderless, full screen at 1600x900, 1280x720, back, 1920x1080, 1024x768 | each picture at the right size; borderless at 3840x2160 rendered at the chosen 1600x900 |
| Four scenes at five sizes | `sh kotor/tools/gfx/sizes.sh` (main menu, HUD, a conversation's replies, the character sheet at 1280x720, 1920x1080, 2560x1440, 3840x2160, 2560x1080) | `kotor/out/gfx/sizes/sheet_*.png`: panels, text and HUD in proportion at all five |
| Options by hand | `scripts/menu_*.txt`, `ingame_*.txt`: click through the panels headless | resolution list, UI scale, description pane, the file written on close, the in-game menu applying Grass live |

## Decisions

- Defaults: Brightness 57 (neutral), Anisotropy 8x (what the renderer always did), Anti-aliasing off (cost and risk
  for the many; the panel offers up to 8x), Shadows, Grass and Frame Buffer Effects on (the original's), Soft Shadows
  off, Texture Quality High, GUI Scale auto, V-Sync on, windowed 1280x720. The original's own defaults (`0x0061da60`,
  and the Advanced panel's Default `0x0061d520`) are Brightness 57, Shadows, Grass, Soft Shadows and Frame Buffer
  Effects on, Anti-aliasing and Anisotropy off, V-Sync off (the swap interval is left to the driver when the key is
  missing), Texture Quality Low (also when the key is missing or above 3), full screen.
- Borderless fullscreen is the recommended mode on a modern PC (instant alt-tab); exclusive full screen is there for
  the player who wants the display's own mode and refresh rate.
- Anti-aliasing is multisampled buffers, not a post filter. The alpha-tested edges of foliage are the edges it leaves
  alone unless the Enhanced Graphics panel's foliage anti-aliasing is on (the default; not with Original Look), which
  sends punch-through surfaces through alpha-to-coverage while multisampling is on (`lib/render_gl/fx_aa.ctx`).

## Open

- Lens flares (the 61 light nodes with flare data) and the film noise texture (`filmnoisetex`) of the original's
  Frame Buffer Effects; the speed blur is ours to the original's description.
- Shadows only from creatures, onto the walkmesh floor; no placeable or door shadows, none onto walls.
- Untested here: exclusive full screen on a second monitor, Retina/Windows-scaled HiDPI, macOS and Linux windows.
- The minigame loops ignore Frame Limit; the movie player draws to the render size, scaled by `present`.
