# Application structure of swkotor.exe: start-up, main loop, input, audio, movies

How the executable starts, runs its frame loop and shuts down, and how keyboard/mouse input,
Miles audio and Bink movies are wired in. Addresses are for the Steam `swkotor.exe` after
SteamStub removal (`kotor/re/bin/swkotor_unpacked.exe`). Names are ours, in the Aurora (NWN)
vocabulary; Ghidra still shows most of them as `FUN_...` until the proposals in
`kotor/re/proposals/app.tsv` are merged into [names.tsv](names.tsv). Confidence: **high** = read
in the code and consistent with strings/imports; **med** = role clear, exact name a guess;
**low** = plausible reading only.

The renderer and the GUI are in [render-gui.md](render-gui.md); the resource manager in
[resman.md](resman.md).

## The picture in one paragraph

The CRT entry calls `WinMain`, which takes a named mutex, builds `g_pExoBase` (ini, timers,
debug log), reads `swKotor.ini` aliases, builds `g_pAppManager` (which owns the client half at
+4; the server half at +8 is created later, when a game starts), creates the windows and the GL
context, initialises the client (resources, display, sound, TLK, GUI, movie player), plays the
legal movies, opens the main menu and enters a `PeekMessage` loop. Each frame: clear, client
`MainLoop` (which also draws the 3D world and then the GUI), server `MainLoop`, console overlay,
`SwapBuffers`, optional frame-rate cap. All of the game's per-frame work hangs off the two
`MainLoop`s. Input comes from window messages (mouse) and DirectInput (keyboard, mouse axes),
audio is Miles Sound System (`mss32`), movies are Bink (`binkw32`) played on a separate thread
into their own child window.

## Global singletons

| Address | Our name | What it is | Conf. |
|---|---|---|---|
| 0x007a39fc | `g_pAppManager` | `CAppManager` (0x20 bytes): +0 a 256 KB scratch buffer, +4 `CClientExoApp*`, +8 `CServerExoApp*` (null until a game starts), +0xc/+0x10 two zeroed 0x184-byte tables, +0x14 a 0x3c module-transition block, +0x18 `GetTickCount()` at start | high |
| 0x007a39e0 | `g_pExoBase` | `CExoBase` (0x18 bytes): +0 `CExoIni`, +4 `CExoTimers`, +8 `CExoDebug`, +0xc/+0x10/+0x14 smaller exo services | high |
| 0x007a39e4 | `g_pExoInput` | `CExoInput`, (re)created by `SetVideoMode` once the render window exists | high |
| 0x007a39e8 | `g_pExoResMan` | resource manager (see resman.md) | high |
| 0x007a39ec | `g_pExoSound` | `CExoSound` | high |
| 0x007a39f8 | `g_pDisplay` | the GL display singleton (`CAurGLDisplay`, from `GetInstance` 0x0044ecd0, see render-gui.md) | high |
| 0x007a39f4 | `g_pGuiManager` | `CSWGuiManager`, owned by the client at +0x274 (see render-gui.md) | high |
| 0x007a3a00 | `g_pVirtualMachine` | NWScript VM (already named) | high |
| 0x007a39c0 / 0x007a39d4 / 0x007a39d8 | `g_hInstance`, `g_hMainWindow`, `g_hRenderWindow` | the module handle, the outer window, the child window that owns the GL context | high |
| 0x007a39b8 | `g_bQuit` | ends the main loop | high |
| 0x0078d1d4 / d8 / dc / e0 | `g_nScreenWidth/Height/RefreshRate/BitsPerPixel` | defaults 800, 600, 60, 32 | high |
| 0x00832894 | `g_bDisableSound` | `[Sound Options] Disable Sound`, also set when Miles fails to start | high |
| 0x0078e39c | `g_pfnPumpMessages` | pointer to `PumpWindowMessages`, called by long loaders | med |

## Start-up

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x006fb38d | CRT entry | version, heap, environment, command line; calls `WinMain(GetModuleHandle(NULL))` | high |
| 0x004041f0 | `WinMain` | the whole application, see the order below | high |
| 0x0044c980 | `Console_ExecFile(file)` | runs a file of console commands, logging "Done executing file" (used for `config.txt` and `startup.txt`); part of the renderer's console, see render-gui.md | high |
| 0x005e6500 | `CExoBase::CExoBase` | creates the exo services | high |
| 0x005e6680 | `CExoBase::ReadAliases` | reads the alias section (HD0, OVERRIDE, MODULES, LIPS, RIMS, SAVES, ...) of the ini named by its argument | med |
| 0x00401160 | `CAppManager::CAppManager` | builds the client app and the owned blocks | high |
| 0x00403f20 | `CreateMainWindow(hInstance)` | reads PrivateBuild/ProductVersion/InternalName/LegalCopyright from the version resource (0x005e6b10), builds the title, registers the window class "Exo - BioWare Corp., (c) 1999 - Generic Blank Application" with `MainWndProc`, creates the outer window, checks the monitor, then calls `CreateRenderWindow` | high |
| 0x004036f0 | `CreateRenderWindow(hInstance)` | registers "Render Window" (same WndProc) and creates the child window that will own the GL context | high |
| 0x004015b0 / 0x00401610 | screen saver / power settings | remember and switch off two `SystemParametersInfo` settings for the session; restored at exit | med |
| 0x00401700 | `ParseCommandLine` | `-ecf`, `-epf`, `-epr`, `-epm`: capture/playback options forwarded to the client | med |
| 0x005ed860 → 0x005f8550 | `CClientExoAppInternal::Initialize` | the big client initialiser, see below | high |
| 0x005ed7b0 → 0x005f51c0 | `CClientExoAppInternal::PostInitialize` | creates the load screen panel (`CSWGuiLoadScreen`, 0x0067a710) at client+0x278 and a 0xdc-byte global at 0x007a3a28 (reads a `Walk` column per row), rebuilds the key mapping, marks the client ready (+0x204) | med |
| 0x005ed300 → 0x00602dc0 | `PlayLegalMovies` | queues `leclogo`, `biologo`, `legal` unless `Disable Movies` | high |
| 0x005ed420 → 0x005fca30 | `ShowMainMenu` | creates the main menu panel (0x1414 bytes, ctor 0x0067c4c0) at client+0x280 and adds it to the GUI manager | med |

Order inside `WinMain`:

1. `CreateMutexA("swkotor")` + `WaitForSingleObject(..., 0)`; a second instance exits with -1.
2. `CoInitialize`, a dummy `PeekMessage` (creates the thread's queue).
3. `Console_ExecFile("config.txt")`.
4. `g_pExoBase = new CExoBase` (0x18 bytes); `ReadAliases("swKotor.ini")`.
5. `g_pAppManager = new CAppManager` (0x20 bytes).
6. `CreateMainWindow`; on failure return 0.
7. Disable the screen saver/low-power settings; read `[Sound Options] Disable Sound` from
   `.\swkotor.ini` (writing a default if missing) into `g_bDisableSound`.
8. `ParseCommandLine(__argc, __argv)`; `g_pfnPumpMessages = PumpWindowMessages`.
9. `CClientExoApp::Initialize(0, "", "")`; on success:
10. `PostInitialize`, clear `g_bQuit`, `SetActive(1, 0)`, `Console_ExecFile("startup.txt")`,
    0x0044ef00 (packs four float colour components into the 32-bit colour at 0x0078e394), five client byte options at +0x3e4..+0x3e8,
    `PlayLegalMovies`, `ShowMainMenu`, then the main loop.

`CClientExoAppInternal::Initialize` (0x005f8550) in order: four `CWorldTimer`s at +0x24..+0x30;
a 0x18 object at +0x14; `g_pExoResMan`; `[Graphics Options] AllowWindowedMode`;
`g_pDisplay = 0x0044ecd0()`; option blocks (0x005ee990, +0x3c); the net layer (0x2007c bytes,
0x005d54a0) at +0x10; a 0x42c object at +8; a 0x50 object at +0x14c; the client object list at
+0xc (0x00604b20); `EnableReleaseLogging`; resource directories, key file and RIMs (listed in
resman.md); `InitializeSound` (0x005f1f70); the TLK at 0x007a3a08/0x007a3a0c; `HD0:DIALOG`;
Xbox LIVE content dirs (0x005f4180); a 0x138 object at +0x18; then the graphics options
(`Texture Quality` → texture packs 0x005f14a0, `FullScreen`, `Disable Movies` (+0x1f8),
`V-Sync`, `Anisotropy`, `Anti Aliasing`) and `SetDisplayMode` (0x005f5ab0); language from the TLK
(Polish switches the C locale to `Polish_Poland.1250`); IME support for languages >= 1000; the
GUI manager at +0x274 (0xa8 bytes, ctor 0x0040bad0, sized to the screen); the mouse is centred;
the in-game GUI (`CGuiInGame`) at +0x40 (0xc24 bytes, ctor 0x0062fed0); and the movie player at +0x12c
(0x005f2bf0). All ini reads go through `CExoIni::ReadIniEntry` (0x005e67c0, value, file, section,
key) and `WriteIniEntry` (0x005e67d0); a missing value is usually written back with its default.

## The main loop

The loop is inline in `WinMain` (0x004041f0); the frame functions are:

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x004041f0 | `WinMain` loop | see below | high |
| 0x00401510 | `PumpWindowMessages` | drains the queue (also used during loads and movies) | high |
| 0x00402800 | `MainWndProc` | window messages, see Input | high |
| 0x005ed7d0 → 0x00602eb0 | `CClientExoAppInternal::MainLoop` | one client frame; returns 1 to quit | high |
| 0x004ae860 → 0x004babb0 | `CServerExoAppInternal::MainLoop` | one server frame | high |
| 0x00401c10 | `RenderLoadingFrame(dt, bTickServer, bNoRender)` | a GUI-only frame (clear, renderer pre-pass, GUI manager draw, console, `SwapBuffers`), message pump, optional server tick, sound update; called many times from module loading and save/load code | high |
| 0x00403800 | `SetVideoMode(w, h, bpp, fullscreen, notify)` | runs when `g_nPendingVideoModeChange` (0x007a3a2c) is set: tears down and recreates the render window and the GL context through `g_pDisplay`, honours `Disable Vertex Buffer Objects` / `Disable Write-Only VBO`, recreates `g_pExoInput`, restores the clear colour; a fullscreen switch hides the task bar and shows the `KotorCin` black backdrop from a helper thread (0x00401a30) | med |

One iteration, when `PeekMessage` finds nothing:

1. Process-priority change if requested (0x007a3ca4/0x007a3ca0).
2. Pending video-mode change → `SetVideoMode` (640x480x32 when a client flag at options+0x4bc
   is set, else the ini mode).
3. Unless a movie is playing (`CClientExoApp::IsMoviePlaying`, 0x005edb40): `glClear(colour |
   depth | stencil)` and `GL_DisableLight0` (0x0044da80; `GL_EnableLight0` 0x0044da60 when the
   never-written flag 0x007a3c50 is set).
4. Client `MainLoop`; its result is ORed into `g_bQuit`. Time spent → `g_fClientFrameMs`
   (0x007a3c7c), using `CExoTimers::GetHighResolutionTimer` (microseconds).
5. Server `MainLoop` if a server exists (one pass; it stops early when the module-transition
   block says a load is in progress). Time → `g_fServerFrameMs` (0x007a3c80).
6. Cheat console: draws `>` and the input line, executes a submitted line (`Console_Execute`
   0x0044c1f0) and prints the result (`Console_Print` 0x0044d490).
7. Unless a movie is playing: `Console_Render` (0x0044d6a0), the console cursor, then
   `SwapBuffers(GetDC(g_hRenderWindow))` (0x007a3c9c is held at 1 around the swap so the movie
   thread does not start mid-swap).
8. `CheckMovieFinished` (0x005ee1f0).
9. Optional `Sleep` (0x007a3c58, 0x0078d1e8 ms) and the frame-rate cap: if `g_fFrameRateCap`
   (0x007a3c64, set by the server) is above 0, busy-wait until 1000/cap ms have passed since the
   frame started.

When `PeekMessage` finds a message: `GetMessage`, leave on `WM_QUIT`, else
`TranslateMessage`/`DispatchMessage`. There is no fixed time step in the outer loop; timing lives
in the `CWorldTimer`s.

Inside `CClientExoAppInternal::MainLoop` (0x00602eb0), roughly: module-load bookkeeping
(timers paused/resumed while the module-transition block at `g_pAppManager+0x14` says loading,
movies started on demand, a GUI-only frame through `RenderLoadingFrame`); world timers updated
(`CWorldTimer::Update` 0x004adbd0, `GetFrameDelta` 0x004adc80; the frame delta in seconds is
kept in 0x0078e574); resource manager tick (0x00408d40); `Render_BeginFrame` (0x0044ed90, finishes queued texture loads); net layer receive (0x005d57d0,
0x005d5650; client and server talk through two in-process `CNetLayer`s, 0x005d54a0, that link
to each other as peers in `Initialize` 0x005d5550 and exchange messages through 128 KB rings); `ProcessInput` (0x006227e0); queued script calls on `g_pVirtualMachine`; bark/feedback
string queue; camera and area updates; client objects' per-frame update **and the 3D world render** (0x006048c0 over the list at +0xc,
then `CSWCModule::Render` 0x00644650 → camera → scene, see render-gui.md); the GUI manager's update and draw (`CSWGuiManager::Update` 0x0040ce70, `Render` 0x0040cc50 on
+0x274, also `g_pGuiManager` 0x007a39f4);
`UpdateSoundListener` (0x005f5370) which ends in `CExoSound::Update`; and, if file errors were
recorded, appending them to `HD0:FILEERROR` ("Patch 2 Error Logging File").

`CWorldTimer` (0x44 bytes, ctor 0x004ae4c0): a speed percentage at +8, the current and previous
times (microseconds) at +0xc/+0x14, the high-resolution stamp at +0x1c, a paused flag at +0x24,
7,200,000 ms per game day. `PauseWorldTimer` 0x004adff0, `UnpauseWorldTimer` 0x004ae030,
`GetWorldTime(&day, &time)` 0x004ade40. Confidence med.

## Shutdown

After the loop: `CAppManager::DestroyServer` (0x00401280), `CClientExoApp::ShutDownClient`
(0x005ed810 → 0x005f8470), `CClientExoApp::ShutDown` (0x005ed880 → 0x00604130, removes the
resource directories added by Initialize), restore the two system settings,
`~CAppManager` (0x004012c0), `~CExoBase` (0x005e66a0), `CoUninitialize`, close the mutex. The
exit code is the `WM_QUIT` wParam.

## Client and server halves

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005ee2f0 | `CClientExoApp::CClientExoApp` | 8 bytes: vtable 0x0074e6d8, `CClientExoAppInternal*` at +4 | high |
| 0x005fbfe0 | `CClientExoAppInternal::CClientExoAppInternal` | 0x4d4 bytes | high |
| 0x005ed000–0x005ee2f0 | `CClientExoApp` methods | ~220 one-line forwarders to the internal object or getters of its fields; e.g. `GetClientOptions` 0x005ed700 (+4), `GetInGameGui` 0x005ed690 (+0x40), `GetGuiManager` 0x005eda40 (+0x274), `IsMoviePlaying` 0x005edb40 | high |
| 0x00401380 | `CAppManager::CreateServer` | replaces the server: new `CServerExoApp` (0x004aec00, vtable 0x00744184, 0x1b944-byte internal 0x004b55e0), `Initialize` (0x004ae8f0 → 0x004b63e0); called from the main menu and load paths (0x0067b9d0, 0x006cb0e0, 0x006dbdf0) | high |
| 0x00401280 | `CAppManager::DestroyServer` | `ShutDownServer` (0x004ae900 → 0x004b7c60) and delete | high |

Fields of `CClientExoAppInternal` used above: +4 options block (volumes at +0x48, swap mouse
buttons at +0x54, ...), +0xc client object list, +0x10 net layer, +0x18 game/area state,
+0x24..+0x30 world timers, +0x40 in-game GUI, +0x9c current input class, +0x12c movie player,
+0x1f8 Disable Movies, +0x274 GUI manager, +0x278 GUI object from PostInitialize, +0x280 main
menu panel.

## Input

Two paths, both ending in `CExoInput`:

- **Mouse buttons, moves and wheel** arrive as window messages. `MainWndProc` (0x00402800) flips
  y to bottom-up (`height - y - 1`), swaps left/right when the options say so (options+0x54), and
  hands a small message record to `CExoInput::HandleWindowMessage` (0x005df590 → 0x005e12a0);
  button-down also calls `SetCapture`.
- **Keyboard and mouse axes** come from DirectInput: keys as buffered device data, the mouse as
  an immediate `DIMOUSESTATE` turned into -1..1 axis values (0x005e0110).

`MainWndProc` also handles: `WM_ACTIVATEAPP` (pause, re-acquire, fullscreen restore through
`g_pDisplay`), `WM_SETFOCUS`/`WM_KILLFOCUS` (`CClientExoApp::SetActive` → 0x005f6b10, which
acquires or releases input), `WM_CLOSE` (→ 0x005f6960, opens the in-game quit panel instead of
quitting), `WM_SIZE` maximise of the render window (sets the pending mode change to fullscreen), `WM_SETCURSOR`, `WM_SYSKEYDOWN`
Alt+F4 and Alt+Enter, Esc while a movie plays (skip), the IME messages (forwarded to the client's
IME helper at client+0xe0, functions 0x005df740–0x005dfc40), and private messages 0x409/0x40a
(mode switch / leave movie mode). `WM_KEYDOWN` goes to 0x004024f0 (input recording, console arrow
keys) and `WM_CHAR` to 0x00402240, which toggles the **cheat console** on the language's tilde
key when `[Game Options] EnableCheats=1`; the console state is `g_bCheatConsoleOpen`
(0x007a3a40) with its line at 0x007a3a4c.

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005df3f0 | `CExoInput::CExoInput` | vtable 0x0074d5ec; creates the 0x3b0-byte internal object | high |
| 0x005e1880 | `CExoInputInternal::CExoInputInternal(hInstance, hWnd)` | vtable 0x0074d624; six input-class tables of 0x30 bytes at +8, event array at +0x128 (count +0x12c), lists at +0x134/+0x138, the DirectInput wrapper at +0x140 | high |
| 0x005df6b0 → 0x005e24e0 | `CExoInput::GetEvents(events, &count, inputClass)` | per frame: reads the key buffer (0x005e3ae0) and joystick/mouse state (0x005e30e0), applies repeats and axis scaling, returns the events bound in the given class | high |
| 0x005df460 → 0x005e0e20 | `AddEvent(event, type, device, key, modifier)` | registers an event and its binding | med |
| 0x005df470 → 0x005e0fa0 | `EnableEventForClass(event, class)` | | med |
| 0x005df480 / 0x005df490 | `SetEventScale`, `SetEventRepeat` | | low |
| 0x005df600 | `ClearEvents` | | med |
| 0x005df540 / 0x005df510 | `SetAcquired`, `GetAcquired` | | med |
| 0x005df5a0 → 0x005e1740 | `SetHardwareCursorHidden` | hides the Windows cursor (software cursor drawn by the GUI) or restores it; `EnableHardwareMouse` ini key (0x005f1c20) | med |
| 0x005df5d0 → 0x005e0960 | `SetMousePosition(x, y)` | `SetCursorPos` with bottom-up y | med |
| 0x005e3e80 | `CExoDirectInput::CExoDirectInput(hInstance, hWnd)` | `DirectInput8Create` (version 0x800, retry 0x300); keyboard device, keyboard data format, cooperative level non-exclusive + foreground, buffer of 256 events | high |
| 0x005e3fa0 | `CExoDirectInput::CreateMouse` | mouse device on the render window, non-exclusive + background | high |
| 0x005e3c20 / 0x005e3dc0 | `SetAcquired`, `Release` | | high |
| 0x005e4050 | `GetMouseState` | `GetDeviceState(DIMOUSESTATE)`, re-acquires when lost | high |
| 0x005eeb10 | `CClientExoAppInternal::SetupKeymapping` | registers every game event: hard-wired bindings first, then the `keymap` 2DA (columns per input class `ICPC`, `ICMiniGame`, `ICPCGUI`, `ICDialog`, `ICFreeLook`, `ICMovie`, plus `EventType`, `Repeatable`, `RepeatWait`, `RepeatRate`, `Scale`, `ScaleMag`, `ScaleExp`, `Disabled`, `Language`) and the `[Keymapping]` ini overrides | med |
| 0x006227e0 | `CClientExoAppInternal::ProcessInput` | per frame: mouse update, `GetEvents` for the current class (client+0x9c); game actions to `HandleInputAction` (0x00621210), GUI actions to `CSWGuiManager::HandleInputEvent` (0x0040c8e0), then the cursor position to `HandleMouseMove`; while recording, writes "%d %c %f %f %f" lines | med |

Mouse and camera options (`Mouse Sensitivity`, `Mouse Look`, `Reverse Mouse Buttons`, `Keyboard
Camera DPS/Acceleration/Deceleration`, `Enable Mouse Teleporting To Buttons`) are read and written
by 0x0061dbe0 / 0x0061b780.

## Audio (Miles Sound System)

Everything goes through `g_pExoSound` (a 4-byte `CExoSound` whose only field is the
`CExoSoundInternal*`; all wrappers return quietly when sound is disabled).

`CClientExoAppInternal::InitializeSound` (0x005f1f70) reads `[Sound Options]`: `Sound Init`
(a crash guard: if the previous start-up did not finish, hardware sound is skipped), `Number 2D
Voices` (default 24), `Number 3D Voices` (default 16), `EAX`, `Force Software`, then constructs
`CExoSound` and applies `Environment Effects Nonstreaming`, `Environment Effects Streaming`,
`2D3D Bias`, writing all values back.

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005d5bc0 | `CExoSound::CExoSound(n2D, n3D, provider, hardware)` | new 0x14c-byte `CExoSoundInternal` (0x005d86e0) and `Initialize` | high |
| 0x005da8a0 | `CExoSoundInternal::Initialize` | `AIL_set_redist_directory("Miles")`, `AIL_quick_startup` (44.1 kHz, 16-bit, stereo); failure sets `g_bDisableSound`; picks a 3D provider (0x005da6d0, `3D Provider Filter`), allocates 2D and 3D sample handles; when called again it closes and reopens streams and samples | high |
| 0x005d66d0 | `SetEnvironment(room)` | EAX room type, EAX2/EAX3 parameters, master room | med |
| 0x005d6d30 | `ShutDown` | releases handles, `AIL_close_3D_provider`, `AIL_quick_shutdown`; warns "CExoSoundSource %s not freed" | high |
| 0x005d5dd0 → 0x005d9590 | `Update` | per frame (from `UpdateSoundListener` and `RenderLoadingFrame`): fades, stream volumes, finished sources, listener | med |
| 0x005d5de0 / 0x005d5df0 | `SetListenerOrientation`, `SetListenerPosition` | `AIL_set_3D_orientation` / `AIL_set_3D_position` on the listener | high |
| 0x005d5e80 → 0x005d8560 | `SetSoundMode(mode)` | game / paused / movie / dialog modes; 5 and 6 push and pop a pause | med |
| 0x005d5c50, 0x005d5cd0, 0x005d5d50 | group volume setters | three 0..1 volumes (music, effects, voice in some order) | low |
| 0x005d60e0 | `CExoSoundSource::CExoSoundSource(resref)` | vtable 0x0074c608; 0xa0-byte internal; one-shot and positional sounds. `Play` 0x005d5930, `GetIsPlaying` 0x005d5920, `SetVolume` (0..127) 0x005d5950, `SetPosition` 0x005d59e0 | high/med |
| 0x005db4d0 | `CExoSoundSourceInternal::Play` | loads the WAV data and starts a 2D (0x005d7480) or 3D (0x005d71c0) Miles sample with loop count, rate, distances and room level | med |
| 0x005d5a50 | `CExoStreamingSoundSource::CExoStreamingSoundSource` | 0x84-byte internal stream (0x005dbbe0): music, ambience, voice-over | high |
| 0x005dca30 | `CExoStreamingSoundSourceInternal::Play` | builds `HD0:STREAMMUSIC\%s`, `HD0:STREAMWAVES\%s` (or the per-module `\%s\%s\%s` form) or `HD0:STREAMSOUNDS\%s`, opens with `AIL_open_stream` (0x005dbd30, `.wav` or `.mp3`), sets loop count and start position, `AIL_start_stream` | high |
| 0x005dc3c0 / 0x005dc380 / 0x005dcdb0 | `Stop`, `Pause`, `Resume` | `AIL_pause_stream` and friends | med |
| 0x005dc560 / 0x005dc930 | volume, pan and reverb levels of a stream | | med |
| 0x005df230 | WAV resource decode | `AIL_WAV_info`, then `AIL_decompress_ADPCM` or `AIL_decompress_ASI` (MP3 inside WAV) into PCM; vtable 0x0074d398 slot 4 | low |

The listener follows the camera/player each frame (`UpdateSoundListener` 0x005f5370), and the
area's EAX room follows the listener (0x005ee860).

## Movies (Bink)

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x0070c170 | `CExoMoviePlayer::CExoMoviePlayer` | owns a 0xa0-byte `CExoMoviePlayerInternal`; created at client+0x12c by 0x005f2bf0 | high |
| 0x00405d70 | `CExoMoviePlayerInternal::CExoMoviePlayerInternal` | creates an event and the movie thread (stack 32 KB, proc 0x00405b30) | high |
| 0x0070c200 → 0x00405e50 | `PlayMoviesAsync(list, arg, skippable)` | copies the movie names and per-movie skippable flags (warns when there are fewer flags than movies), sets playing, signals the thread | high |
| 0x00405b30 | `MovieThreadProc` | waits on the event; for each queued name: `OpenMovie`, `PlayFrames`, `CloseMovie`, stopping early when a skippable movie is skipped with skip-all; at the end posts 0x40a (leave movie mode) to the render window, or, when playback was interrupted, 0x409 (mode toggle) or `WM_ACTIVATEAPP(0)` | high |
| 0x004053e0 | `OpenMovie(name)` (auto-named `CExoMoviePlayerInternal::CExoMoviePlayerInternal`; its error text reuses that name) | registers `SWMovieWindow`, creates a topmost child "SW Movie Player Window" over the render window, captures the mouse, resolves `MOVIES:<name>` (adds `.bik`), routes Bink audio through Miles (`BinkSetSoundSystem(BinkOpenMiles, AIL handle)`), `BinkOpen`, `BinkBufferOpen`, volume from the options, centres or scales to the window, clears the render window with `PatBlt`, shows the movie window | high |
| 0x00404c80 | `PlayFrames` | `BinkDoFrame`, lock/copy/unlock the BinkBuffer, `BinkGetRects`/`BinkBufferBlit`, `BinkNextFrame`, `BinkWait` with 1 ms sleeps; stops on skip; pumps the thread's messages | high |
| 0x00404bb0 | `CloseMovie` | `BinkPause`, `BinkClose`, `BinkBufferClose`, destroys the movie window | high |
| 0x00405190 | `MovieWndProc` | Esc and a primary-button release skip the current movie; Alt+Enter and losing activation stop playback and remember why (0x00404c20); Alt+F4 posts `WM_CLOSE` to the main window; messages 0x407/0x408 forwarded by `MainWndProc` reposition the Bink buffer (0x00404f40 `BinkBufferCheckWinPos`, 0x00404f80) | high |
| 0x0070c1f0 / 0x0070c1e0 | `IsPlaying`, `Skip` | | high/med |
| 0x00405a50 | `~CExoMoviePlayerInternal` | stops and joins the thread | high |

While a movie plays the main loop draws nothing (Bink blits straight into its own window), the
client pauses its timers and sets the sound mode to 3.
Script `PlayMovie` (0x00540ed0) and the client (0x00602650 `PlayQueuedMovies`, 0x00602af0) queue
movies; 0x00403cf0 / 0x00403de0 enter and leave the movie display mode.

## Open questions

- The exact roles of `CAppManager+0xc/+0x10` (two zeroed 0x184-byte blocks) and of the 0x3c
  module-transition block's fields.
- `PostInitialize` (0x005f51c0): what the 0xdc-byte global at 0x007a3a28 is (it reads a `Walk`
  value per row of some table).
- The five byte options the start-up writes at client+0x3e4..+0x3e8 (values 10, 20, 23, 23, 23).
- Which of the three group-volume setters is music, effects and voice.
