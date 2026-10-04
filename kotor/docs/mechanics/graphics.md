# Graphics options and modern displays

What the Graphics and Advanced Graphics panels do in the original, what they do here, and how the game
copes with the screens people have now (1440p, 4K, ultrawide, 144 Hz, Windows display scaling). The code is
`game/display.ctx` (the options made real), `lib/frontend` (the panels), `lib/platform/sdl.ctx` (windows and
displays), `lib/render_gl/gpu.ctx` (the device), `lib/scene/grass.ctx`. Status words: **matches** (checked
against the original's code or strings and run), **ours** (the original has nothing like it), **partial**
(some of what the original does).

## How an option reaches the screen

The panels edit `frontend::Settings`; the engine calls `display::apply` after every change, which makes the
device agree with it and does only what differs from the last call (all of it the first time), so an option
applies **live**, as the original's do (its setters are called from the panel's handlers: `0x006ded30`,
`0x0044ee20`..`0x0044ee90`). Closing a panel writes our own options file (`kotor/out/kotor-settings.ini`,
`--settings FILE`; never the install's `swkotor.ini`) with the original's section and key names.

A window run reads the file for its size, mode and options (`--size` overrides the size). An offscreen run
(`--headless`, `--no-render`) uses the defaults for the graphics keys, so logs and pictures repeat whatever file
is lying about, unless `--gfx` asks for the file. `FRAME gfx KEY VALUE` input lines set an option from a script
(`size W H`, `mode windowed|borderless|fullscreen`, `refresh`, `vsync`, `brightness`, `shadows`, `softshadows`,
`grass`, `emitters`, `framebuffer`, `aniso`, `aa`, `texture`, `scale`, `limit`, `blur`); they work in the front end
and in a game and never write the file.

## The panels, option by option

| Option (panel) | Original | Ours | State |
|---|---|---|---|
| Brightness slider (Graphics), key `Brightness` | The handler (`0x006ded30`) turns the slider `v` (0..100) into the exponent `2 - 1.77 v/100` and loads a 256-entry gamma ramp with `SetDeviceGammaRamp` (`SetGamma 0x0044d990`: `out = in ^ exponent`), live; put back to 1.0 when the window is deactivated. 57 (the install's value) is the exponent 0.99, the picture as drawn | The same curve as a shader in `present` (the picture, movies and GUI together, as a hardware ramp does), live; screenshots apply it too. 56 and 57 are left alone (a plain blit). Default 57 (ours was 50, 1.115: a darker game than before). Needs no display ramp, so alt-tab cannot leave the desktop dark | matches |
| Screen Resolution (Graphics) | A list of the display's modes, rows `%d x %d` or `%d x %d @ %d Hz`; OK applies it through `ChangeVideoMode` (`0x006df690`) | The list is SDL's: `windowed` the sizes that fit the desktop, `borderless` the sizes up to the desktop's (a smaller one is rendered small and scaled up with bars), `fullscreen` every size and refresh rate; the current size is always a row. The button shows `Resolution: W x H`. Applied at once; a full-screen mode the display refuses becomes borderless | matches, modern list |
| Display Mode (Graphics) | `FullScreen` key only (no control); `AllowWindowedMode` | A button: Windowed, Borderless, Fullscreen (key `FullScreen` = 0, 2, 1). Windowed is a resizable window centred on its display, no larger than the room it has; Borderless is a window over the desktop at its resolution; Fullscreen switches the display's mode | ours |
| UI Scale (Graphics) | none: the GUI is never scaled (re/gui.md) | A button: Auto, 100%, 125% ... 400% (key `GUI Scale`, 0 is auto). Auto is the largest quarter step at which the 800x600 main menu fits the window (1080p 175%, 1440p 225%, 4K 350%), so panels, HUD, conversations and text stay readable. Everything lays itself out again at once | ours |
| Shadows (Graphics) | Flag `0x0078e3a8` (`0x0044ee20`); stencil shadow volumes from the lights that cast shadows (`CAurScene::RenderPasses`, `GL_DrawShadowVolume`) | Off: no shadow is drawn. On: each creature casts the meshes its model flags (`Mesh.shadow`) onto the walkmesh face under it, from the nearest light of the room above it, else from the sun overhead; the area's `ShadowOpacity` (50 or 205 in the data) is how dark. (Nothing submitted a shadow before: the option had nothing to switch) | partial (planar, creatures only) |
| Soft Shadows (Advanced) | Flag `0x0078e420`; `CAurScene::RenderSoftShadows` (`0x00451a50`) blurs the shadows through a pbuffer | Twelve projections from points of a 0.5 m area light, each darkening by the share that makes the core as dark as one hard shadow: a limb far above the floor gets a wide penumbra, a foot a sharp one | partial (different technique) |
| Grass (Graphics) | Flag `0x0078e3ac` (`0x00450150`); the ARE's `Grass_TexName`, `Grass_Density`, `Grass_QuadSize`, `Grass_Prob_*` on faces whose surface material has the grass flag (17 areas: Dantooine, Kashyyyk, Manaan, the Unknown World, one Taris area) | Tufts planted once per face by a hash (density a square metre, one of the texture's four quarters by the four probabilities), the ones within 26 m drawn each frame as one punch-through emitter that turns about the vertical, shrinking over the last 7 m; `WindPower` sways them. The option drops them | matches in kind (the original's blade geometry and wind are not known) |
| Emitters (Graphics, ours) | `dialog.tlk` 47958/47959 describe it ("blaster bolts and certain force powers") but the executable never reads an `Emitters` key and the panel has no box | A check box (key `Emitters`) that drops every visual-effect emitter (not grass) | ours |
| Anti-Aliasing (Advanced) | `Render_SetAntiAliasing` (`0x0044f2f0`) sets the sample count; takes effect when the GL context is made again (`SetVideoMode`, `0x00403800`): `wglChoosePixelFormatARB` with N samples | Off, 2x, 4x, 8x: the screen and the GUI's render targets are multisampled renderbuffers resolved into their textures, so it applies live and covers the main menu's 3D scene too (capped at what the driver has) | matches, live |
| Anisotropy (Advanced) | `EXT_texture_filter_anisotropic`, applied when a texture is bound (`0x0041fe80`..) | Off, 2x, 4x, 8x on every mipmapped linear texture, including those already made, live (it was fixed at 8x) | matches |
| Texture Quality (Advanced) | The row of `texpacks.2da` (`0x0061d730` -> `0x005ed8f0` -> `0x005f14a0`): the pack `swpc_tex_tpc` (low, quarter size textures), `tpb` (medium, half), `tpa` (high) is mounted again; textures loaded from the old one stay until loaded again. `AurTextures_SetQuality` (`0x00421d90`) is the video-memory budget of that row, not a resize | The pack is mounted again and the area's scene is loaded again from it, so the change shows at once (a menu scene is not). Default High | matches |
| V-Sync (Advanced) | `Render_SetVSync`, `wglSwapIntervalEXT` | `SDL_GL_SetSwapInterval(1 or 0)`, live. Off, the loop runs as fast as it can (about 1000 frames a second at 4K on the test machine) | matches |
| Frame Buffer Effects (Advanced) | Flag `0x0078d98c`; `Render_ApplyScreenEffects` (`0x00437520`) copies the screen into a texture and runs passes; `dialog.tlk` 47957: "per pixel flares, noise, and speed blur" | **Speed blur**: while the leader moves faster than it walks (Burst of Speed, Force Speed, haste: the rules' speed factor above 1.2) a radial blur, eased in and out, goes over the 3D picture (not the HUD). Off, none | partial (flares and film noise are not drawn: no light we model carries flare data we draw, and nothing in the data says when the noise shows) |
| Default (each panel) | Resets the panel's options | Resets them, and the UI scale and Emitters of the Graphics panel; not the resolution or the display mode | matches |

Also read from the file, not on a panel: `Refresh Rate` (Hz for full screen, 0 the display's highest) and
`Frame Limit` (frames a second at most, 0 none; the loop sleeps then spins for the last half millisecond; the
minigames' own loops do not use it).

The description pane on the right of the two panels, empty before, shows the original's own text: the string
after each label in `dialog.tlk` (Shadows is 47950, its explanation 47951), and ours for the buttons the
original lacks.

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
- **Frame rate**: the simulation runs on the measured frame time, clamped to 0.25 s, never on a count of frames. Checked
  with `--dt` at 1/30, 1/60, 1/144 and 1/240 s (below).

## Checking it

| Check | How | Result |
|---|---|---|
| Walking is frame-rate independent | `kotor/tools/gfx/scripts/walk.txt` from the apartment checkpoint, leader's place after 1.5 s and 3.0 s world time at four steps | x = 85.3042..85.3046 and 82.2125..82.2137 (0.5 mm) at 30, 60, 144, 240 fps |
| Animation, emitters, camera | the main menu scene at world time 3 s at 30, 144, 240 fps; the opening cutscene at 20 s at 30, 60, 144, 240 | menu scene: 1 pixel differs (a random mist particle); the cutscene's camera and poses agree (a character a tick or two ahead at 30 fps: scripts act on tick boundaries, 33 ms against 4 ms) |
| Real time, uncapped | a window with V-Sync off, 6000 frames | 0.84 ms a frame (1180 fps), world time equals wall time; with `limit` the loop keeps to the rate |
| 4K, everything on | a borderless 3840x2160 window, 8x MSAA, 8x anisotropy, soft shadows, V-Sync off | about 1000 frames a second on an RTX 4090 |
| Window modes | `scripts/window_modes.txt` in a real window: windowed, borderless, full screen at 1600x900, 1280x720, back, 1920x1080, 1024x768 | each picture at the right size; borderless at 3840x2160 rendered at the chosen 1600x900 |
| Four scenes at five sizes | `sh kotor/tools/gfx/sizes.sh` (main menu, HUD, a conversation's replies, the character sheet at 1280x720, 1920x1080, 2560x1440, 3840x2160, 2560x1080) | `kotor/out/gfx/sizes/sheet_*.png`: panels, text and HUD in proportion at all five |
| Options by hand | `scripts/menu_*.txt`, `ingame_*.txt`: click through the panels headless | resolution list, UI scale, description pane, the file written on close, the in-game menu applying Grass live |

## Decisions

- Defaults: Brightness 57 (neutral), Anisotropy 8x (what the renderer always did), Anti-aliasing off (cost and risk
  for the many; the panel offers up to 8x), Shadows and Grass on (the original's), GUI Scale auto, V-Sync on, windowed
  1280x720.
- Borderless fullscreen is the recommended mode on a modern PC (instant alt-tab); exclusive full screen is there for
  the player who wants the display's own mode and refresh rate.
- Anti-aliasing is multisampled buffers, not a post filter, so the alpha-tested edges of foliage are the only edges it
  leaves (alpha-to-coverage is not used).

## Open

- Lens flares (the 61 light nodes with flare data) and the film noise texture (`filmnoisetex`) of the original's
  Frame Buffer Effects; the speed blur is ours to the original's description.
- Shadows only from creatures, onto the walkmesh floor; no placeable or door shadows, none onto walls.
- Untested here: exclusive full screen on a second monitor, Retina/Windows-scaled HiDPI, macOS and Linux windows.
- The minigame loops ignore Frame Limit; the movie player draws to the render size, scaled by `present`.
