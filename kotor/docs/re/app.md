# Application structure of swkotor.exe: start-up, main loop, input, audio, movies

How the executable starts, runs its frame loop and shuts down, and how keyboard/mouse input,
Miles audio and Bink movies are wired in. Addresses are for the Steam `swkotor.exe` after
SteamStub removal (`kotor/re/bin/swkotor_unpacked.exe`). Names are ours, in the Aurora (NWN)
vocabulary, kept in [names.tsv](names.tsv); an address given here only as a number has no name
there yet. Confidence: **high** = read in the code and consistent with strings/imports; **med** =
role clear, exact name a guess; **low** = plausible reading only. The whole page was rechecked claim by claim on 2026-10-07
against the exports rebuilt after the noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med
claim that says "needs a runtime check" rests on static reading alone and is surprising enough to
test before relying on it.

The renderer and the GUI are in [render-gui.md](render-gui.md); the resource manager in
[resman.md](resman.md).

## The picture in one paragraph

The CRT entry calls `WinMain`, which takes a named mutex, builds `g_pExoBase` (ini, timers,
debug log, alias list), reads `swKotor.ini` aliases, builds `g_pAppManager` (which owns the client
half at +4; the server half at +8 is created later, when a game is started or loaded), creates the
windows, initialises the client (resources, sound, TLK, display mode and GL context, GUI, movie
player), plays the legal movies (blocking until they end), opens the main menu and enters a
`PeekMessage` loop. Whenever the message queue is empty it runs a frame: clear, client
`MainLoop` (which also draws the 3D world and then the GUI), server `MainLoop`, console overlay,
`SwapBuffers`, optional frame-rate cap. All of the game's per-frame work hangs off the two
`MainLoop`s. Input comes from window messages (mouse buttons, wheel and position; keys and
characters for the console) and DirectInput 8 (keyboard buffer, mouse axes), audio is Miles Sound
System (`mss32`), movies are Bink (`binkw32`) played on a separate thread into their own pop-up
window laid over the render window.

## Global singletons

| Address | Our name | What it is | Conf. |
|---|---|---|---|
| 0x007a39fc | `g_pAppManager` | `CAppManager` (0x20 bytes): +0 a 256 KB scratch buffer, +4 `CClientExoApp*` (8 bytes: vtable, then the 0x4d4-byte `CClientExoAppInternal`), +8 `CServerExoApp*` (null until a game starts; `CAppManager::CreateServer` 0x00401380 builds it from new game / load game), +0xc/+0x10 two zeroed 0x184-byte tables, +0x14 a 0x3c module-transition block (`CModuleTransition`), +0x18 `GetTickCount()` at start | high |
| 0x007a39e0 | `g_pExoBase` | `CExoBase` (0x18 bytes): +0 `CExoIni`, +4 `CExoTimers`, +8 `CExoDebug` (0x10 bytes), +0xc the alias list (`CExoAliasList`, filled by `ReadAliases`), +0x10 a small exo service (0x005ea420), +0x14 `CExoResTypes` | high |
| 0x007a39e4 | `g_pExoInput` | `CExoInput` (8 bytes), (re)created only by `SetVideoMode` once the render window exists | high |
| 0x007a39e8 | `g_pExoResMan` | resource manager (0x60 bytes, built by the client's `Initialize`; see resman.md) | high |
| 0x007a39ec | `g_pExoSound` | `CExoSound`, built by `InitializeSound` (0x005f1f70) | high |
| 0x007a39f8 | `g_pDisplay` | the GL display singleton (`CAurGLDisplay`, from `GetInstance` 0x0044ecd0, called through the thunk 0x0044ed70; see render-gui.md) | high |
| 0x007a39f4 | `g_pGuiManager` | `CSWGuiManager` (set by its constructor), owned by the client at +0x274 (see render-gui.md) | high |
| 0x007a3a00 | `g_pVirtualMachine` | NWScript VM, created by the server's `Initialize` (0x004b63e0) together with its command implementer, so only once a game starts | high |
| 0x007a39c0 / 0x007a39d4 / 0x007a39d8 | `g_hInstance`, `g_hMainWindow`, `g_hRenderWindow` | the module handle; the main window (a tool window that nothing shows; it carries the title and receives the movie window's `WM_CLOSE`) (med); the render window, a second top-level window with no parent that is the visible game window and owns the GL context (high) | high |
| 0x007a39b8 | `g_bQuit` | ends the main loop: set by `PumpWindowMessages` (0x00401510) on `WM_QUIT` and ORed with the return values of the client and server `MainLoop`s; `WinMain`'s own loop also leaves directly on `WM_QUIT` | high |
| 0x0078d1d4 / d8 / dc / e0 | `g_nScreenWidth/Height/RefreshRate/BitsPerPixel` | defaults 800, 600, 60, 32 | high |
| 0x00832894 | `g_bDisableSound` | `[Sound Options] Disable Sound`, also set when Miles fails to start (`AIL_quick_startup` in 0x005da8a0) | high |
| 0x0078e39c | `g_pfnPumpMessages` | pointer to `PumpWindowMessages` (0x00401510: drains the queue with Peek/Get/Translate/Dispatch), set by `WinMain`; called inside two renderer loops over long object lists (0x004504d0, 0x00457b90) | med |

## Start-up

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x006fb38d | CRT entry | version, heap, environment, command line; calls `WinMain(GetModuleHandle(NULL))` | high |
| 0x004041f0 | `WinMain` | the whole application, see the order below | high |
| 0x0044c980 | `Console_ExecFile(file)` | runs a file of console commands and returns "Done executing file '%s'" (or an error text when the file is missing; `WinMain` ignores the text); used for `config.txt` and `startup.txt`; part of the renderer's console, see render-gui.md | high |
| 0x005e6500 | `CExoBase::CExoBase` | creates the exo services | high |
| 0x005e6680 | `CExoBase::ReadAliases` | reads the `[Alias]` entries (HD0, CD0, OVERRIDE, ERRORTEX, MODULES, LIPS, RIMS, SAVES, ...) of the ini named by its argument into the alias list at `g_pExoBase`+0xc (0x005e7a90 → 0x005e7760); a missing alias gets its built-in PC default (`.\override`, ...) and is not written back | med |
| 0x00401160 | `CAppManager::CAppManager` | builds the client app and the owned blocks | high |
| 0x00403f20 | `CreateMainWindow(hInstance)` | reads PrivateBuild/ProductVersion/InternalName/LegalCopyright from the version resource (0x005e6b10), builds the title, registers the window class "Exo - BioWare Corp., (c) 1999 - Generic Blank Application" with `MainWndProc`, creates the main window (`WS_EX_TOOLWINDOW`, not visible), then checks its monitor (when `MonitorFromWindow` finds one, `GetMonitorInfo` must succeed and report the primary monitor, else it returns NULL and start-up ends), then calls `CreateRenderWindow` and stores `g_hInstance`/`g_hMainWindow` | high |
| 0x004036f0 | `CreateRenderWindow(hInstance)` | registers "Render Window" (same WndProc) and creates a second top-level window (`WS_EX_APPWINDOW`, no parent, titled with the InternalName) that will own the GL context; `SetVideoMode` calls it again to recreate the window on every mode change | high |
| 0x004015b0 / 0x00401610 | mouse trails / screen saver | remember the mouse-trail length (`SPI_GETMOUSETRAILS`) and whether the screen saver is active (`SPI_GETSCREENSAVEACTIVE`) and switch each off when it is on; 0x004015f0 / 0x00401650 restore them at exit and whenever the app loses activation (`WM_ACTIVATEAPP`), and activation switches them off again | high |
| 0x00401700 | `ParseCommandLine` | `-ecf [file]` records input to `HD0:<file>` (default `capture`, 0x005f5720), `-epf [file]` plays such a recording back (0x005f5910), `-epr [n]` fixes the client world timer's step at n (default 30, 0x005eeae0); `-epm` is compared but does nothing | med |
| 0x005ed860 → 0x005f8550 | `CClientExoAppInternal::Initialize` | the big client initialiser, see below | high |
| 0x005ed7b0 → 0x005f51c0 | `CClientExoAppInternal::PostInitialize` | creates the load screen panel (`CSWGuiLoadScreen`, 0x6b8 bytes, 0x0067a710) at client+0x278 if missing; creates `g_pRules` (0x007a3a28, the 0xdc-byte `CSWRules`, resources.md 4) if missing and ORs the `Walk` column of surfacemat.2da (the rules' C2DAs +0x14) into a walkable-surface bitmask at client+0xa4 (bit n = row n); `CGuiInGame::CreateEarlyPanels`; `SetupKeymapping`; if a movie is already playing, switches the in-game GUI, input and sound (mode 3) to movie mode; marks the client ready (+0x204) | high |
| 0x005ed300 → 0x00602dc0 | `PlayLegalMovies` | when client+0x1fc is 0 (`Initialize` clears it) queues `leclogo`, `biologo`, `legal` (flag 1 each) and plays the queue at once (0x00602d40 → 0x00602af0): with `Disable Movies` (+0x1f8) set nothing plays, otherwise it enters movie video mode and blocks in 0x005f6f20 until the player stops (pumping window messages every 500 polls), so the main menu is built only after the movies | high |
| 0x005ed420 → 0x005fca30 | `ShowMainMenu` | unless it is already shown, creates the main menu panel (0x1414 bytes, ctor 0x0067c4c0) at client+0x280 and adds it to the GUI manager | med |

Order inside `WinMain`:

1. `CreateMutexA("swkotor")` + `WaitForSingleObject(..., 0)`; a second instance exits with -1.
2. `CoInitialize`, a dummy `PeekMessage` (creates the thread's queue).
3. `Console_ExecFile("config.txt")`.
4. `g_pExoBase = new CExoBase` (0x18 bytes); `ReadAliases("swKotor.ini")`.
5. `g_pAppManager = new CAppManager` (0x20 bytes).
6. `CreateMainWindow`; on failure return 0.
7. Switch off mouse trails and the screen saver (0x004015b0, 0x00401610); read
   `[Sound Options] Disable Sound` from `.\swkotor.ini` (writing 0 if missing) into
   `g_bDisableSound`.
8. `ParseCommandLine(__argc, __argv)`; `g_pfnPumpMessages = PumpWindowMessages`.
9. `CClientExoApp::Initialize(0, "", "", "", 0)` (five arguments; it jumps to
   `CClientExoAppInternal::Initialize`, which always returns 0, so the failure branch, which
   closes the mutex and returns 0, is never taken); then:
10. `PostInitialize`, clear `g_bQuit`, `SetActive(1, 0)`, `Console_ExecFile("startup.txt")`,
    0x0044ef00(0, 0, 0, 0) (packs four float colour components, each ×255, into the 32-bit colour
    at 0x0078e394, so it becomes 0; nothing in the decompiled code reads it back) (med), the five
    load-phase weights at client+0x3e4..+0x3e8 (10, 20, 23, 23, 23; read by `GetLoadPhaseWeight`
    0x005edff0 for the loading progress bar, see gui.md), `PlayLegalMovies` (blocking),
    `ShowMainMenu`, then the main loop.

`CClientExoAppInternal::Initialize` (0x005f8550) in order: four `CWorldTimer`s (0x44 bytes each)
at +0x24..+0x30; the client object array (`CGameObjectArray`, 0x18 bytes) at +0x14;
`g_pExoResMan` (0x60 bytes); `[Graphics Options] AllowWindowedMode` into 0x007a3a30;
`g_pDisplay = GetInstance()` (thunk 0x0044ed70); a 0x20-byte object at +0x3c (0x005ee990, ctor
0x00676da0); the net layer (0x2007c bytes, 0x005d54a0) at +0x10; when +8 is empty, a 0x42c-byte
settings block there (0x0054eb10, the constructor the server's `Initialize` also uses); a 0x50
object at +0x14c (0x0064b510); the client object list at +0xc (0x10 bytes, 0x00604b20, holding a
back-pointer to the client); `[Game Options] EnableReleaseLogging` into the debug log
(`g_pExoBase`+8, +0xc) and the log name `swc` (0x005e93f0); the directories `TEMPCLIENT:`,
`OVERRIDE:`, `ERRORTEX:`; the TLK object (the 100-byte client subclass, vtable 0x0074e700) in
0x007a3a08 and 0x007a3a0c; the remaining resource sources (key file, RIMs, ERFs, directories,
listed in resman.md; the three `HD0:DATAXBOX\...` lines only copy strings and register nothing);
the renderer's resource callbacks (0x007a39f0); `InitializeSound` (0x005f1f70); a streaming-music
path only when the first argument is non-zero (+0x304, 0x005f6480; `WinMain` passes 0);
`SetTlkFile("HD0:DIALOG")`; the Xbox LIVE slots `LIVE1`..`LIVE6` (0x005f4180: each defined alias
adds its TLK, key file, RIMs and ERFs); `CNetLayer::Initialize`; `srand(GetTickCount())`; the
client module at +0x18 (0x138 bytes, ctor 0x00643f40, a game object of internal type 3) (med); and,
only when that allocation succeeded, the rest: `Texture Quality` (0..3, anything else becomes 0)
→ texture packs from texpacks.2da (0x005f14a0); `FullScreen` (written back as 0 if missing);
`[Game Options] Disable Movies` (+0x1f8; +0x1fc cleared); the client options (`CClientOptions` at
+4) reset to defaults (0x0061da60) and loaded (0x005f4710, defaults again if loading fails);
`SetDisplayMode(movie mode, FullScreen)` (0x005f5ab0), where movie mode = `FullScreen` with movies
enabled: the mode switch then uses 640x480x32 and afterwards puts the ini resolution back into
`g_nScreenWidth/Height/BitsPerPixel`; a missing or unavailable ini mode falls back to 800x600x32
at 60 Hz (med); `V-Sync`, `Anisotropy` and `Anti Aliasing` into the client options (an
anti-aliasing level above 0 outside movie mode re-runs `SetVideoMode` at the current size); TLK
string 0 at +0x13c and the TLK language id at +0x144 (Polish, id 5, sets the CRT `LC_CTYPE`
locale to `Polish_Poland.1250`); IME support for language ids >= 1000 (+0xdc = 1, a 0x128-byte
object at +0xe0, 0x005ee400); 0x005ee920; a 0x10-byte table at +0x1c4 (0x00678c10, reads
`SoundSet`/`SoundSetType`/`RESREF`/`STRREF`/`GENDER` columns) (med); inventorysnds.2da
(0x005f0ad0); `EnableHardwareMouse` and `TooltipDelay Sec` (0x005f1c20); the GUI manager at
+0x274 (0xa8 bytes, ctor 0x0040bad0, sized to the screen); when `g_pExoInput` exists the mouse is
centred (and `CreateCursorModel` called when the input's flag at +0x378 is 1); 0x0061f980;
`LoadGuiSounds`; the in-game GUI (`CGuiInGame`) at +0x40 (0xc24 bytes, ctor 0x0062fed0); and,
when that exists, the movie player at +0x12c (`CreateMoviePlayer` 0x005f2bf0, a 4-byte
`CExoMoviePlayer`). It always returns 0. All ini reads go through `CExoIni::ReadIniEntry`
(0x005e67c0, value, file, section, key) and `WriteIniEntry` (0x005e67d0); only a few callers write
a missing value back (`Disable Sound`, `FullScreen`, `TooltipDelay Sec` here), the others just
keep their built-in default.

## The main loop

The loop is inline in `WinMain` (0x004041f0); the frame functions are:

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x004041f0 | `WinMain` loop | see below | high |
| 0x00401510 | `PumpWindowMessages` | drains the queue; a `WM_QUIT` sets `g_bQuit` (0x007a39b8). Called by `RenderLoadingFrame` and the post-load movie handler 0x005f6f20, and through `g_pfnPumpMessages` (0x0078e39c, set by `WinMain`) by two `CAurScene` methods (vtable 0x00741708 slots 55/56) | high |
| 0x00402800 | `MainWndProc` | window messages, see Input | high |
| 0x005ed7d0 → 0x00602eb0 | `CClientExoAppInternal::MainLoop` | one client frame; returns 1 to quit when both +0x250 and +0x254 are set (0x005f1bd0, a callback registered by `OnWindowClose` 0x005f6960, sets them and posts `WM_QUIT`) | high |
| 0x004ae860 → 0x004babb0 | `CServerExoAppInternal::MainLoop` | one server frame; always returns 0 | high |
| 0x00401c10 | `RenderLoadingFrame(dt, bTickServer, bNoRender)` | a GUI-only frame: `Render_BeginFrame`; unless `bNoRender` or a movie, clear and the light-0 toggle; `CSWGuiManager::Render(dt)` (also with `bNoRender`); unless `bNoRender` or a movie, cheat-console prompt, `Console_Render`, `SwapBuffers`; message pump; with `bTickServer == 1` one server `MainLoop` and another pump (its client receive calls pass `bProcess = 0` and do nothing); `CExoSound::Update`; the client net layer's `UpdateStatusLoop`; a second `CSWGuiManager::Render(0)`. 17 callers in module loading and save/load code | high |
| 0x00403800 | `SetVideoMode(w, h, bpp, fullscreen, notify)` | runs when `g_nPendingVideoModeChange` (0x007a3a2c, 2 = fullscreen) is set: tears down and recreates the render window and the GL context through `g_pDisplay`, honours `Disable Vertex Buffer Objects` / `Disable Write-Only VBO`, recreates `g_pExoInput` (keeping the hardware-cursor state), restores the clear colour, clears the pending flag. When the display's slot 1 returns 1 and the new mode is fullscreen, the task bar is disabled and hidden for the switch and a helper thread (`CinematicBackdropThread` 0x00401a30) shows the `KotorCin` black backdrop; afterwards the task bar is shown again and the thread signalled to close | med |

One iteration, when `PeekMessage` finds nothing:

1. Process-priority change if 0x007a3ca4 is set: 0x007a3ca0 = 1 → `HIGH_PRIORITY_CLASS`, else
   `NORMAL_PRIORITY_CLASS` (2 sets `REALTIME_PRIORITY_CLASS` and then falls through to `NORMAL`).
   Nothing in the exe writes either global, so this never runs (high).
2. Pending video-mode change → `SetVideoMode` (640x480x32 when the client flag +0x4bc is set, else
   the ini mode). +0x4bc is the end-credits mode: set when `.\movies\55.bik` is queued (0x00602d40),
   cleared by `~CSWGuiCredits` (0x0068f0e0) (med).
3. Unless a movie is playing (`CClientExoApp::IsMoviePlaying`, 0x005edb40, the movie player at
   +0x12c): `glClear(colour | depth | stencil)`. Then, movie or not, `GL_DisableLight0`
   (0x0044da80; `GL_EnableLight0` 0x0044da60 when 0x007a3c50 is set, which nothing writes).
4. Client `MainLoop`; its result is ORed into `g_bQuit`. Time spent → `g_fClientFrameMs`
   (0x007a3c7c), using `CExoTimers::GetHighResolutionTimer` (microseconds).
5. Server `MainLoop` once, if a server exists (the call sits in a one-iteration loop whose break on
   module-transition state 1 changes nothing); its result, always 0, is ORed into `g_bQuit`.
   Time → `g_fServerFrameMs` (0x007a3c80).
6. Cheat console: while it is open (`g_bCheatConsoleOpen` 0x007a3a40) prints `>` and the input line
   (0x007a3a4c); a submitted line (flag 0x007a3a48) is executed (`Console_Execute` 0x0044c1f0), the
   result printed (`Console_Print` 0x0044d490) and the line cleared.
7. Unless a movie is playing: `Console_Render` (0x0044d6a0). While the console is open, the `_`
   cursor (also during a movie). Unless a movie is playing or a video-mode change is pending:
   `SwapBuffers(GetDC(g_hRenderWindow))`, with 0x007a3c9c held at 1 around the swap; the movie
   thread's `OpenMovie` (0x004053e0) sleeps while it is 1 before blanking the render window.
8. `CheckMovieFinished` (0x005ee1f0).
9. Two throttles, both off in the shipped exe (gameloop.md 1.1): `Sleep(1)` (0x0078d1e8 = 1) when
   `g_bSleepEachFrame` (0x007a3c58) is set, which nothing writes; and the frame-rate cap: if
   `g_fFrameRateCap` (0x007a3c64) is above 0, busy-wait until 1000/cap ms have passed since the
   previous wait ended. The cap is written only by `CSWSModule::LoadModuleFinish` (0x004c5880) from
   `g_nDebugFrameRateCap` (0x00832904), which nothing writes.

When `PeekMessage` finds a message: `GetMessage`, leave on `WM_QUIT`, else
`TranslateMessage`/`DispatchMessage`. Each iteration handles one message or runs one frame, so
frames run only when the queue is empty. There is no fixed time step in the outer loop; timing
lives in the `CWorldTimer`s.

Inside `CClientExoAppInternal::MainLoop` (0x00602eb0), in order (gameloop.md 1.2 has the step
table): finishing a load (when the loading flag +0x288 is set and the player's client creature
exists: input class, HUD, hide the load screen 0x005f6e20, movie handling, `LeaveMovieVideoMode`;
then, only while the application is active (0x007a3a38, set by `OnAppActivate` 0x00401e00), copy
the world clock +0x24 into the other three, unpause all four and the server world clock, start
the fade-in unless an autosave is pending, and mark +0x288 for clearing at the end of the frame);
the clocks advanced (`CWorldTimer::Update` 0x004adbd0: +0x24 unless +0x1cc & 3, +0x28 unless
+0x1cc & 2, +0x2c always); if the module-transition block at `g_pAppManager+0x14` says a
transition is running: net receive, `UpdateModuleTransition` (0x00602c90), and while word 1 is 1 or
3 set +0x288, draw `RenderLoadingFrame(1/30 s, no server tick, bNoRender = 1)` (GUI only; `WinMain`
clears and swaps), run `ProcessInput` when block +0x38 is 4, and **return**, skipping the rest;
the frame delta (`GetFrameDelta` 0x004adc80 on +0x24, in seconds in 0x0078e574, 0 while that clock
is paused); resource manager tick (`CExoResMan::Update` 0x00408d40); party table update
(0x00637050) when an area is loaded; `Render_BeginFrame` (0x0044ed90: optional throttle, free
memory sample, `AurTextures_Update` for queued texture loads); `ProcessInput` (0x006227e0);
`UpdateSlowMotion` (0x005f7330); the party-wipe countdown (+0x1a8/+0x374: unload, `DestroyServer`,
main menu); `SetGameSpeed` (0x005f2f60) with 0.25 when +0x1b0 or the debug flag 0x0083291c is set,
else 1.0, which overwrites the speed `UpdateSlowMotion` just set (med, needs a runtime check); net
layer receive (`ProcessReceivedFrames(1)` 0x005d57d0 and `UpdateStatusLoop` 0x005d5650 on +0x10,
skipped while the client flag +0x90 is set); the one queued script name at +0x330 run on
`g_pVirtualMachine` when +0x32c is set; the player creature's bark queue (+0x168, timer +0x16c,
med); with an area loaded: the area's +0x184 object placed at the party leader, camera input
(`UpdateCameraInput` 0x005f5e10, yaw zeroed while the GUI panel at in-game GUI +0xa0 is up), client
objects' per-frame update **and the 3D world render** (`UpdateObjectsAndRender` 0x006048c0: vtable
slot +0x74 of every object in the list at +0xc, then `CSWCModule::Render` 0x00644650 on the module
at +0x18 with the +0x2c clock's delta, see render-gui.md), `UpdateAreaSoundEnvironment`
(0x005ee860); the current conversation (the server object whose client id is at in-game GUI +0x188:
`CSWSObject::UpdateDialog` 0x004cd580, `DeleteDialog` when its +0x214 is set;
`CGuiInGame::SelectDialogReply` 0x006339c0); `UpdateSelectableObjects` (0x005fa5a0); the GUI
manager's update and draw (`CSWGuiManager::Update` 0x0040ce70 with the world delta, `Render`
0x0040cc50 with the +0x2c delta, on +0x274, also `g_pGuiManager` 0x007a39f4);
`UpdateSoundListener` (0x005f5370, only with `g_pExoSound`) which ends in `CExoSound::Update`;
screenshot; the deferred auto-pause (+0x390) and pending pause change (+0x37c bit 2); and, if file
errors were recorded, appending them to `HD0:FILEERROR` ("Patch 2 Error Logging File").

Client and server talk through two in-process `CNetLayer`s (constructor 0x005d54a0), each owning a
0x20000-byte (128 KB) receive ring; `Initialize` (0x005d5550) links the second one created to the
first as peers (+0x2000c, via the global 0x0083288c), and a sender writes into its peer's ring.
`ProcessReceivedFrames` hands frames starting with `BN` to the net layer itself and the rest to the
owning app (vtable slot 1). (high)

`CWorldTimer` (0x44 bytes, ctor 0x004ae4c0): a fixed-step flag and rate at +0/+4 (normally off), a
speed percentage at +8 (100), the current and previous times (microseconds) at +0xc/+0x14, the
high-resolution stamp at +0x1c, a paused flag at +0x24 (`GetFrameDelta` returns 0 while it is set;
`Update` ignores it), ms per game day at +0x3c (7,200,000 by default). `PauseWorldTimer`
0x004adff0, `UnpauseWorldTimer` 0x004ae030, `GetWorldTime(&day, &time)` 0x004ade40. Full layout in
gameloop.md 1.6. Confidence high.

## Shutdown

After the loop: `CAppManager::DestroyServer` (0x00401280), `CClientExoApp::ShutDownClient`
(0x005ed810 → 0x005f8470: empties the +0x168 queue, deletes `g_pRules`, the load screen +0x278 and
+0x27c), `CClientExoApp::ShutDown` (0x005ed880 → 0x00604130: the full client teardown: movie
player, main menu, module, in-game GUI, GUI manager, client objects, net layer, `g_pExoInput`, sound,
`g_pTlkTable`, `g_pDisplay`, then removes the resource directories added by Initialize (PORTRAITS,
SERVERVAULT, the CHITIN key file, OVERRIDE, MOVIES, STREAMMUSIC, STREAMWAVES, TEMPCLIENT, RIMS:GLOBAL,
RIMS) and deletes `g_pExoResMan`, then the four clocks and the options block), restore the two
system settings saved at startup when they were above 0 (mouse trails, SPI 0x5d, from 0x007a3ca8;
screen saver active, SPI 0x11, from 0x007a3cac), `~CAppManager` (0x004012c0), `~CExoBase`
(0x005e66a0), `CoUninitialize`, close the mutex. The exit code is the `wParam` left in `WinMain`'s
message buffer: the `WM_QUIT` code (0 from the game's own quit) when the loop ends on `WM_QUIT`,
otherwise whatever the last message left there (med).

## Client and server halves

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005ee2f0 | `CClientExoApp::CClientExoApp` | 8 bytes: vtable 0x0074e6d8, `CClientExoAppInternal*` at +4 | high |
| 0x005fbfe0 | `CClientExoAppInternal::CClientExoAppInternal` | 0x4d4 bytes | high |
| 0x005ed000–0x005ee2f0 | `CClientExoApp` methods | ~210 functions, nearly all one-line forwarders to the internal object or getters of its fields; e.g. `GetClientOptions` 0x005ed700 (+4), `GetInGameGui` 0x005ed690 (+0x40), `GetGuiManager` 0x005eda40 (+0x274), `IsMoviePlaying` 0x005edb40 | high |
| 0x00401380 | `CAppManager::CreateServer` | replaces the server (an old one gets `ShutDownServer` and is deleted): new `CServerExoApp` (0x004aec00, vtable 0x00744184, 0x1b944-byte internal 0x004b55e0), `Initialize` (0x004ae8f0 → 0x004b63e0), then `LoadGlobalVariableCatalogue` (0x004ae850); called from the main menu's module warp (0x0067b9d0), loading a save (0x006cb0e0) and starting a new game (0x006dbdf0) | high |
| 0x00401280 | `CAppManager::DestroyServer` | `ShutDownServer` (0x004ae900 → 0x004b7c60) and delete, then `UpdateWindowTitle` (0x00401440) | high |

Fields of `CClientExoAppInternal` used above: +4 options block (byte volumes at +0x45 music, +0x46
voice-over, +0x47 sound effects, +0x48 movie; reverse mouse buttons at +0x54, ...), +0xc client
object list, +0x10 net layer, +0x18 current client module (`CSWCModule`, area at its +0x48),
+0x24/+0x28/+0x2c/+0x30 clocks (world `GetWorldTimer` 0x005ed4f0; +0x28 not advanced while +0x1cc bit 2
is set; interface `GetInterfaceTimer` 0x005ed500; aux `GetAuxTimer` 0x005ed510),
+0x40 in-game GUI, +0x9c current input class, +0x12c movie player, +0x1f8 Disable Movies, +0x250/
+0x254 quit flags, +0x274 GUI manager, +0x278 load screen (`CSWGuiLoadScreen`, created by
PostInitialize), +0x280 main menu panel, +0x288 loading flag.

## Input

Two paths, both ending in `CExoInput`:

- **Mouse buttons, moves and wheel** arrive as window messages. `MainWndProc` (0x00402800)
  forwards them only while input is acquired, flips y to bottom-up (`height - y - 1`; wheel
  coordinates are first made client-relative), swaps left/right (and their double-clicks) when
  `Reverse Mouse Buttons` is set (options+0x54), and hands a small message record to
  `CExoInput::HandleWindowMessage` (0x005df590 → 0x005e12a0). That turns a move into a pending
  cursor position (+0x37c/+0x380, emitted as mouse X/Y events by the next `GetEvents`) and a
  button or wheel message into a button event (double-click = value -1) plus a cursor update; the
  first move after `SetMousePosition` is dropped (+0x384). Left, right and middle button-down and
  the right double-click also call `SetCapture`.
- **Keyboard and mouse axes** come from DirectInput: keys as buffered device data (up to 256 per
  read, 0x005e3ae0), the mouse once per frame as an immediate `DIMOUSESTATE`
  (`CExoInput::UpdateMouse` 0x005df620 → 0x005e0110): -dx/100 and -dy/100 (divisor 0x007a2278 =
  100.0) clamped to -1..1, kept at +0x3a0/+0x3a4. A joystick reader (0x005e30e0, `DIJOYSTATE`
  buttons and POV hats) exists, but no joystick is ever enumerated (the wrapper's count +0x18 is
  only ever set to 0), so the device count stays at 2 and it never runs (med).

`MainWndProc` also handles:

- `WM_ACTIVATEAPP`: on activation, in fullscreen with no change pending it asks for fullscreen
  again (pending mode change 2, display slot 0x1c), then `OnAppActivate` (0x00401e00: restores
  the player pause, acquires input, sound mode 6, re-applies gamma); on deactivation, in
  fullscreen and unless a movie is playing, it minimises the render window and restores the
  desktop mode (display slot 0x18), then `OnAppDeactivate` (0x00401d90: sets the player pause
  remembering its old state at `g_pAppManager+0x1c`, releases input, sound mode 5). It also
  disables and restores the screen-saver/low-power settings.
- `WM_SETFOCUS`/`WM_KILLFOCUS`: `CClientExoApp::SetActive` → 0x005f6b10, which acquires or
  releases input (kill-focus is ignored while a movie plays).
- `WM_CLOSE` → 0x005f6960: when the in-game GUI exists, pauses the game and opens a quit
  confirmation message box (StrRef 42348) instead of quitting; otherwise it does nothing.
- `WM_SIZE` maximise of the render window: pending mode change 2 (fullscreen; 1 is windowed).
- `WM_SETCURSOR` (client area of the render window): re-applies the hardware cursor (0x005e0930).
- `WM_SYSCOMMAND` `SC_SIZE`, `SC_SCREENSAVE` and `SC_MONITORPOWER` are swallowed.
- Alt alone releases input and re-acquires it on release; Alt+F4 re-acquires and sends `WM_CLOSE`;
  F10 is swallowed; Alt+Enter (on key-up, 0x00401e90) toggles windowed/fullscreen through the
  pending mode change when `[Graphics Options] AllowWindowedMode` is set (0x007a3a30), otherwise
  sends `WM_ACTIVATEAPP(0)` to the render window.
- Esc while a movie plays: skip-all (0x005f4a00 → `Skip(1, 0)`).
- `WM_CANCELMODE` clears `g_bLookaboutHeld`; `WM_WINDOWPOSCHANGING`/`CHANGED` while a movie plays
  are posted to the movie window as 0x407/0x408.
- The IME messages, while client+0xdc is set: forwarded to the client's IME helper at client+0xe0
  (functions 0x005df740–0x005dfc40).
- Private messages 0x409 (mode switch, wParam non-zero = fullscreen) and 0x40a (leave movie mode,
  0x00403de0).

`WM_KEYDOWN` goes to 0x004024f0 and `WM_CHAR` to 0x00402240, both skipped while an input
playback runs (client+0x90). 0x004024f0 logs the key when recording (client+0x8c, file
client+0x88), moves in the console with the arrow keys when it is open or sends them on as
characters 0x1c..0x1f, swallows F10 and passes `VK_PROCESSKEY` to the IME. 0x00402240 logs the
character, and toggles the **cheat console** on the language's tilde key (`` ` `` 0x60; `°`
0xb0 for TLK language 2, character 3 for language 5) when `[Game Options] EnableCheats=1`
(re-read on every press); other characters go to the console line when it is open, otherwise to
`CSWGuiManager::HandleCharacter`. The console state is `g_bCheatConsoleOpen` (0x007a3a40) with
its line at 0x007a3a4c.

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005df3f0 | `CExoInput::CExoInput` | vtable 0x0074d5ec; creates the 0x3b0-byte internal object on (`g_hInstance`, `g_hRenderWindow`) | high |
| 0x005e1880 | `CExoInputInternal::CExoInputInternal(hInstance, hWnd)` | vtable 0x0074d624; six input-class tables of 0x30 bytes at +8 (named "Unnamed Input Class"), event array at +0x128 (count +0x12c), lists at +0x134/+0x138 and +0x374, a key-code table at +0x164..+0x330 (DirectInput scan codes and joystick offsets by key index), the 0x34-byte DirectInput wrapper at +0x140 (deleted and left null when DirectInput fails), device count +0x158 = joysticks + 2 | high |
| 0x005df6b0 → 0x005e24e0 | `CExoInput::GetEvents(events, &count, inputClass)` | per frame: reads the key buffer (0x005e3ae0; joysticks through 0x005e30e0, never present), drains the queued mouse messages and the pending cursor position, ages the timers on +0x134 and generates repeats (list +0x138: first after `RepeatWait` ms, then every `RepeatRate` ms), returns the events bound in the given class; an invalid class (>= 6) warns and returns none | high |
| 0x005df460 → 0x005e0e20 | `AddEvent(event, type, device, key, modifier)` | registers an event and its binding; fails if the event id already exists, so the first registration wins; types: 0/2/5 value, 1 button (press/release edges), 3 relative axis (accumulated), 4 two-key pair; key 0x84 = none | med |
| 0x005df470 → 0x005e0fa0 | `EnableEventForClass(event, class)` | adds the event to one of the six classes; refused when its key is already bound to another event of that class on the same device | med |
| 0x005df480 / 0x005df490 | `SetEventScale`, `SetEventRepeat` | scale/magnitude on an axis event (a button event is wrapped in a scaled one); repeat wait/rate entry on +0x138 (button events only) | med |
| 0x005df600 | `ClearEvents` | empties the six class tables and sets the event count to 0 | med |
| 0x005df540 / 0x005df510 | `SetAcquired`, `GetAcquired` | | med |
| 0x005df5a0 → 0x005e1740 | `SetHardwareCursorHidden` | hides the Windows cursor (`ShowCursor(0)` until hidden; the GUI then draws a cursor model) or sets the cursor resource again; driven by `[Graphics Options] EnableHardwareMouse` (read by 0x005f1c20 with `TooltipDelay Sec`; hidden when 0) | med |
| 0x005df5d0 → 0x005e0960 | `SetMousePosition(x, y)` | `SetCursorPos` with bottom-up y, updates the mouse X/Y events and drops the next move message | med |
| 0x005e3e80 | `CExoDirectInput::CExoDirectInput(hInstance, hWnd)` | `DirectInput8Create` (version 0x800, retry 0x300); keyboard device, keyboard data format, cooperative level non-exclusive + foreground, buffer of 256 events | high |
| 0x005e3fa0 | `CExoDirectInput::CreateMouse` | mouse device on the render window, non-exclusive + background; created lazily by `GetMouseState` | high |
| 0x005e3c20 / 0x005e3dc0 | `SetAcquired`, `Release` | | high |
| 0x005e4050 | `GetMouseState` | `GetDeviceState(DIMOUSESTATE)` while acquired, re-acquires when lost | high |
| 0x005eeb10 | `CClientExoAppInternal::SetupKeymapping` | from `PostInitialize` (and 0x005ed870): `ClearEvents`, then hard-wired events (GUI/dialog Enter, arrows and keypad Enter 0xb5..0xbb; a SysRq screenshot event 0x50 when `EnableScreenShot` (options+0x58); mouse axes and buttons 0x17..0x19, 0x41..0x46; joystick axes), then the `keymap` 2DA (`C2DAs`+0x68, rows `Action200`..`Action265` and the two-key rows `Action280A/B`..`Action286A/B`): rows with `Disabled=1` are skipped; the key comes from `[Keymapping] Action<n>` in `swkotor.ini`, else from the column `Language<TLK language id>` (or `Language0` when no row has that column; only `Language0` ships), written back to the ini when non-zero; `EventType` 1 makes a value event, otherwise a button; then per row the class columns `ICPC`, `ICMiniGame`, `ICPCGUI`, `ICDialog`, `ICFreeLook`, `ICMovie`, `Repeatable` with `RepeatWait`/`RepeatRate`, and `Scale` with `ScaleMag`/`ScaleExp`. A "key already used" table is checked but never filled, so duplicate keys are not caught here. The Steam install loads `patch.erf`'s keymap, which adds row `Action265` WALKMODIFY on B (a held key in the PC class: half-speed walking, [movement.md](movement.md) 1.1); an axis pair's value is the second key minus the first | med |
| 0x006227e0 | `CClientExoAppInternal::ProcessInput` | per frame (skipped while client+0x2bc is set; during an input playback it replays the recording instead, 0x006224e0): `UpdateMouse`, then, while input is acquired, `GetEvents` for the current class (client+0x9c); events outside 0x27..0x40 that are not GUI-navigation events (or any, while the in-game GUI flag +0x34 is set) go to `HandleInputAction` (0x00621210), the rest to `CSWGuiManager::HandleInputEvent` (0x0040c8e0) when a GUI is up or the class is 2/3; after each event the cursor (client+0x3c8/+0x3cc) goes to `HandleMouseMove` unless mouse-look/free-look is active; while recording, writes "%d %c %f %f %f" lines. `Mouse Look` (options+8 bit 1) inverts the look-about key outside classes 2/3 | med |

Mouse and camera options are fields of the client options block (client+4): `Mouse Look`
options+8 bit 1, `Reverse Minigame YAxis` bit 3, `Enable Mouse Teleporting To Buttons` +0x10,
`Mouse Sensitivity` byte +0x50 (default 44), `Reverse Mouse Buttons` +0x54, `EnableScreenShot`
+0x58, `Keyboard Camera DPS/Acceleration/Deceleration` floats +0x94/+0x98/+0x9c. The options
loader 0x0061dbe0 (from `Initialize` via 0x005f4710) applies the defaults (0x0061da60) and then
every key present in `swkotor.ini`, and always returns 1; the writer 0x0061b780 (via 0x005f46f0 /
0x005edf70, called by the options panels and on load, save and quit) writes them all back.

## Audio (Miles Sound System)

Everything goes through `g_pExoSound` (a 4-byte `CExoSound` whose only field is the
`CExoSoundInternal*`; all wrappers return quietly when sound is disabled).

`CClientExoAppInternal::InitializeSound` (0x005f1f70) reads `[Sound Options]`: `Sound Init`
(a crash guard: it is written as 1 before the sound system starts and as 0 at the end; if it was
still 1, EAX is set to 0 and software sound is forced without reading `EAX` / `Force Software`),
`Number 2D Voices` (default 24), `Number 3D Voices` (default 16), `EAX` (default 3), `Force
Software` (also stored at options+0x4c), then constructs `CExoSound(n2D, n3D, EAX, !Force
Software)` and applies `Environment Effects Nonstreaming`, `Environment Effects Streaming` and
`2D3D Bias` (clamped 0.1..1.9). It writes back `EAX` (the level actually chosen, also kept at
options+0x49), `Force Software`, `2D3D Bias` (`%.2f`) and the voice counts actually allocated;
the two environment-effects keys are not written back.

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x005d5bc0 | `CExoSound::CExoSound(n2D, n3D, eaxLevel, hardware)` | new 0x14c-byte `CExoSoundInternal` (0x005d86e0) and `Initialize`, unless `g_bDisableSound` | high |
| 0x005da8a0 | `CExoSoundInternal::Initialize` | `AIL_set_redist_directory("Miles")`, `AIL_quick_startup` (44.1 kHz, 16-bit, stereo); failure sets `g_bDisableSound`; enumerates the 3D providers that open (0x005da6d0, `3D Provider Filter`) and keeps those listed in `SoundProvider.2da` (`Provider`, `Hardware`, `EAX`, `2D3DBias`; 0x005d9140); takes the first whose `Hardware` and `EAX` match the request, lowering the EAX level step by step and finally falling back to software; if none matches, `AIL_quick_shutdown` and return 0 (`g_bDisableSound` stays clear). Then 3D voices clamped to 16..64 (+0x29, handles +0x30) and 2D voices to 24..64 (+0x28, handles +0x2c); it releases the upper half of the 2D handles again right after allocating them (med, needs a runtime check); 3D rolloff 1.0, `SetEnvironment(0)`. When called again it first stops and closes streams and samples, and afterwards restarts the sources that were playing and reopens and resumes the streams | high |
| 0x005d66d0 | `SetEnvironment(room)` | room types 0..23 from a table of 0x70-byte presets at 0x0074c610 (24 and up = none): EAX room type and EAX2/EAX3 parameters on the 3D provider when `Environment Effects Nonstreaming` is on (+4), the digital master room type when `Environment Effects Streaming` is on (+0) | med |
| 0x005d6d30 | `ShutDown` | stops every stream, deletes leftover sources (formatting "CExoSoundSource %s not freed" for those not owned elsewhere; no output call survives), releases the 2D/3D handles, `AIL_close_3D_provider`, `AIL_quick_shutdown` | high |
| 0x005d5dd0 → 0x005d9590 | `Update` | per frame from `UpdateSoundListener` and `RenderLoadingFrame`, and in short busy-waits that let a fade finish (0x005f1b20, 0x005f4a60: 750 ms, 0x005f4ae0: 500 ms): fades, stream volumes, finished sources, listener | med |
| 0x005d5de0 / 0x005d5df0 | `SetListenerOrientation`, `SetListenerPosition` | `AIL_set_3D_orientation` / `AIL_set_3D_position` on the listener | high |
| 0x005d5e80 → 0x005d8560 | `SetSoundMode(mode)` | a 10-deep mode stack (+0x118, top +0x140): a non-zero mode is pushed (ignored if already on top), 0 pops. Modes seen: 1 fade-out over 500 ms (0x005f4ae0), 2 pause (`RequestPause`, auto-pause, the quit box), 3 movie, save and load screen, 4 in-game menu screens (menu, galaxy map, party selection, store, upgrade); entering 2/3/4 pauses the streams (0x005d82c0, 2 and 4 keep some stream kinds playing) and leaving them resumes (0x005d83f0). 5 (app deactivated) pauses everything and sets a suspend flag (+0x144, which also stops any sound started meanwhile); 6 clears it, resumes and re-applies the top mode | med |
| 0x005d5c50 / 0x005d5d50 / 0x005d5cd0 | group volume setters: music, voice-over, sound effects | clamp to 0..1 and recompute the volumes (0x005d8110); set from the options (`Music Volume` +0x45, `Voiceover Volume` +0x46, `Sound Effects Volume` +0x47, percent, default 85) by 0x0061d1c0 and by 0x006df9b0; script `SetMusicVolume` (routine 765) calls the music setter with a flag that also updates the current music stream at once | med |
| 0x005d60e0 | `CExoSoundSource::CExoSoundSource(resref)` | vtable 0x0074c608; 0xa0-byte internal (a WAV resource helper with the resref); one-shot and positional sounds. `Play` 0x005d5930, `GetIsPlaying` 0x005d5920, `SetVolume` (0..127) 0x005d5950, `SetPosition` 0x005d59e0 | high/med |
| 0x005db4d0 | `CExoSoundSourceInternal::Play` | restarts the sample in place when it already has one (stop, loop count, rewind, resume); otherwise loads the WAV data (`AIL_WAV_info`) and starts a 2D (0x005d7480) or 3D (0x005d71c0) Miles sample with loop count, rate, distances and room level, subject to the per-priority voice limits; a sound started while the system is suspended (mode 5) is stopped at once | med |
| 0x005d5a50 | `CExoStreamingSoundSource::CExoStreamingSoundSource` | 0x84-byte internal stream (0x005dbbe0): music, ambience, voice-over | high |
| 0x005dca30 | `CExoStreamingSoundSourceInternal::Play` | builds `HD0:STREAMMUSIC\%s`, `HD0:STREAMWAVES\%s` (or the per-module `\%s\%s\%s` form for 16-character names starting with `n`) or `HD0:STREAMSOUNDS\%s`, opens with `AIL_open_stream` (0x005dbd30, `.wav` or `.mp3`; a WAV's `RIFF` header may sit at 0 or after a 0x1d6-byte prefix, passed to Miles as a file handle and offset), sets loop count and start position, `AIL_start_stream` | high |
| 0x005dc3c0 / 0x005dc380 / 0x005dcdb0 | `Stop`, `Pause`, `Resume` | 0x005dc3c0 pauses a playing stream and saves its position (the sound-mode pause and re-initialisation; the `evil_ending` stream is left playing unless client+0x4b8 is set); 0x005dc380 pauses and rewinds (position cleared) and takes it off the active lists (`CExoStreamingSoundSource::Pause` 0x005d5b80, `Update`, `ShutDown`); 0x005dcdb0 resumes a paused stream at the saved position with its volume and loop count | med |
| 0x005dc560 / 0x005dc930 | volume, pan and reverb levels of a stream | 0x005dc930: stream volume byte (+0x50) / 127 × group volume × master / 127 into `AIL_set_stream_volume_levels`; 0x005dc560: pan from the stream's position | med |
| 0x005df230 | `CResWAV::Decompress` | vtable 0x0074d398 slot 4: data starting with `BMU V1.0` is MP3, decoded with `AIL_decompress_ASI`; otherwise `AIL_WAV_info` on a `RIFF` header at 0 or after a 0x1d6-byte prefix, and ADPCM (format 0x11) is decoded with `AIL_decompress_ADPCM`; plain PCM is kept | med |

The listener follows the camera/player each frame (`UpdateSoundListener` 0x005f5370), and the
area's EAX room follows the listener (0x005ee860).

### Voices: how many, who gets one, how loud

Read for the sound fixes of 2026-10 (docs/design/audio.md, "Voices and loudness"); confidence
high where a decompile says it plainly, medium where it rests on a field's use.

- **Handles.** `Initialize` (0x005da8a0) allocates the 3D sample handles (`Number 3D Voices`,
  clamped to 16..64; count at internal+0x29, an array of 16-byte entries at +0x30: owning source,
  Miles handle, a busy flag, one more word) and the 2D ones (`Number 2D Voices`, clamped to
  24..64; count +0x28, array +0x2c). Sound sources (`CExoSoundSource`, effects) only ever take the
  first half of the 2D handles (0x005d8ff0 scans `count >> 1`: 12 by default); 0x005d8470 counts
  against the other half (the streams', med). Miles mixes on its own service thread, so a long
  game frame never starves the output; the game only calls `AIL_set_preference(1, 64)` once in the
  constructor (0x005d86e0; which preference index 1 is wasn't checked).
- **PriorityGroups.2da** is read by 0x005d7bd0 into a table at internal+0x4c (row count +0x2a), one
  0x18-byte row per group: +0 `Interrupt` (int), +4 `MaxPlaying`, +5 how many play now, +6
  `Priority`, +7 `Volume` (bytes), +8 `MinVolumeDist`, +0xc `MaxVolumeDist` (floats, only when
  both are present), +0x14 `FadeTime` (u16), then `PlaybackVariance`. A source's group is its
  byte +0x35, a stream's its byte +8. A blank cell keeps the row's default (0x005d6c10):
  `Interrupt` 1, `MaxPlaying` 255, `Priority` 0, `Volume` 127, `FadeTime` 0. Nothing reads
  `FadeTime` (the row getter 0x005d6080 serves only `Update`, which reads +4/+5; no other user of the
  table touches +0x14).
- **Which player volume** (0x005d6a90 for a source, 0x005d6ad0 for a stream, then 0x005d6b10):
  rows 8, 9, 16, 17 and 26 (the chat rows, creature vocalizations, bark bubbles) follow the
  Voiceover volume, rows 1 and 2 (stingers, music) the Music volume, every other row Sound
  Effects. Each has a current and a target value (+0x64/+0x74 voice, +0x7c/+0x70 effects,
  +0x78/+0x6c music), for the sound-mode fades.
- **Starting a source** (`CExoSoundSourceInternal::Play` 0x005db4d0): a 3D source at or past its
  max distance from the listener (0x005db050) is not started; a looping one waits on a list
  (0x005d7b80) until it comes in range. When its group already plays `MaxPlaying` sources, it
  stops one of them if `Interrupt` is set (0x005d7fe0: the first of the group on the playing list
  at +0x40, where 0x005d7b40 adds at the head, so the most recently started; a looping one is
  parked on the waiting list +0x38) and otherwise isn't started (a looping one waits). A stream
  checks the same counts (`CExoStreamingSoundSourceInternal::Play` 0x005dca30, interrupting through
  0x005d80a0). A parked loop is started again by `Update` only when its group has room (it never
  interrupts). Then it needs a handle (0x005d8ff0 2D, 0x005d8eb0 3D): a free one, or else the
  one whose owner's group `Priority` is the largest number (the least important) **and strictly
  larger than the new sound's**; that owner is stopped (0x005db210) and, if looping, parked on
  the waiting list (+0x38) to start again later. With no such handle the new sound is simply not
  played: a sound never cuts off one of its own priority.
- **Out of range later**: `Update` (0x005d9590) stops a playing source that has moved out of range
  (0x005db050) and parks it on the waiting list if it loops.
- **Loudness** (`CExoSoundSourceInternal::SetVolume` 0x005db800): byte +0x84 is the group's
  `Volume` (set by 0x005dbb20), byte +0x85 the source's own (0..127). The level is
  `groupVolume * volume / 127` (an integer 0..127). A 2D source gets `level / 127 * user` where
  `user` is the Sound Effects volume (0x005d6b10), times `2 - bias` when `2D3D Bias` (+0x60) is
  over 1, as `AIL_set_sample_volume_levels`. A 3D source gets `(level / 127 * user * b)` squared
  (`_CIpow` with 2.0), `b` being the bias when it is under 1, as `AIL_set_3D_sample_volume`. The
  installed swkotor.ini has `2D3D Bias=1.50` (the hardware rows of `SoundProvider.2da` say 1.5,
  Miles Fast 2D 1.0), so 2D effects play at half their level. `user` is inside the square, so the
  player's volume is squared too.
- **Streams** (music, the ambient bed, voice-over; 0x005dc930): `AIL_set_stream_volume_levels`
  gets `groupVolume / 127 * user * round(volume * f) / 127`, with `groupVolume` the stream's row's
  `Volume` (byte +0x50, set with the row by 0x005dcd50), `volume` its own (+0x46, 127 unless
  `CExoStreamingSoundSource::SetVolume` 0x005d5b50 sets it), and `f` 1.0 except for rows 4 and 21,
  which take a fade factor from the caller (the sound-mode fades). No 2D3D bias, no squaring. The
  rows: music 2 (64: half), stingers 1 (64), `CGuiInGame::PlayDialogVoice` 9 (90),
  `PlayDialogAmbientTrack` 4 (95, so Sound Effects), `CSWGuiBarkBubble::ShowBark` 26 (127, volume
  127); a new stream's row is 2 (its constructor 0x005dbbe0).
- **GUI sounds** (`CSWGuiManager::LoadGuiSounds` 0x00409f00): one `CExoSoundSource` per
  `guisounds.2da` row, put in row 11 `GUI` (0x005d5900 with 0xb), 2D; `PlayGuiSound` (0x0040a140)
  plays that source. So a click is priority 11, Volume 127, at most two at once (MaxPlaying 2,
  Interrupt 1), with the 2D sources' Sound Effects volume and 2D3D Bias scale. (high)
- **Sound modes** (`CExoSoundInternal::SetSoundMode` 0x005d8560): a stack of ten modes at +0x118
  (top index +0x140); 0 pops, any other pushes (unless it is already on top). Entering 2, 3 or 4
  stops (pauses, 0x005d82c0) every stream and source except, in mode 2 (a pause request),
  rows 1, 2, 4 and 11 and, in mode 4 (stores, the galaxy map, a load), rows 1, 2 and 11;
  mode 3 (movies, saving) stops all; leaving them resumes everything (0x005d83f0). Mode 1 starts a
  500 ms fade (0x005d6a10: +0xc set, +0x54 500, start time +0x50; leaving it, 0x005d6a50 fades
  back over +0x5c 500) whose factor only rows 4 and 21 take (0x005dc930); its only user is
  0x005f4ae0, from `CGuiInGame::QuickLoad` and `CSWGuiSaveLoad::LoadSelectedGame`, which pushes
  mode 1 and spins `CExoSound::Update` for 500 ms before the load: the area's ambient bed fades
  out as a saved game loads. 5 and 6 are the window losing and regaining activation (all paused,
  then resumed and the stack popped back to the mode below). (high for the stack and the rows,
  med for the fade's shape)

## Movies (Bink)

| Address | Our name | What it does | Conf. |
|---|---|---|---|
| 0x0070c170 | `CExoMoviePlayer::CExoMoviePlayer` | owns a 0xa0-byte `CExoMoviePlayerInternal`; created at client+0x12c by 0x005f2bf0 | high |
| 0x00405d70 | `CExoMoviePlayerInternal::CExoMoviePlayerInternal` | creates an event and the movie thread (stack 32 KB, proc 0x00405b30) | high |
| 0x0070c200 → 0x00405e50 | `PlayMoviesAsync(list, arg, skippable)` | copies the movie names and per-movie skippable flags (warns when there are fewer flags than movies; no list = all skippable), sets playing (+0x30), signals the thread | high |
| 0x00405b30 | `MovieThreadProc` | waits on the event; for each queued name: `OpenMovie`, `PlayFrames`, `CloseMovie` (which clears playing), stopping early when a skippable movie is skipped with skip-all; at the end posts 0x40a (leave movie mode) to the render window, or, when playback was interrupted (the names stay queued), 0x409 (to windowed when fullscreen, else to fullscreen) after Alt+Enter, or `WM_ACTIVATEAPP(0)` after losing activation | high |
| 0x004053e0 | `OpenMovie(name)` (its error text reuses the name `CExoMoviePlayerInternal::CExoMoviePlayerInternal`) | registers `SWMovieWindow` once, creates the "SW Movie Player Window" as a topmost popup owned by the render window over its client area, captures the mouse; a name without `.` becomes `MOVIES:<name>` resolved as a `.bik`; routes Bink audio through Miles (`BinkSetSoundSystem(BinkOpenMiles, AIL handle)`), `BinkOpen`, `BinkBufferOpen`, volume from `Movie Volume` (options+0x48, 0 while client+0x4bc is set), centres a movie as wide as the window or scales it, clears the render window with `PatBlt`, shows the movie window | high |
| 0x00404c80 | `PlayFrames` | `BinkDoFrame`, lock/copy/unlock the BinkBuffer, `BinkGetRects`/`BinkBufferBlit`, `BinkNextFrame`, `BinkWait` with 1 ms sleeps; stops on skip; pumps the thread's messages | high |
| 0x00404bb0 | `CloseMovie` | `BinkPause`, `BinkClose`, `BinkBufferClose`, destroys the movie window | high |
| 0x00405190 | `MovieWndProc` | Esc and a primary-button release (the right button when buttons are reversed) skip the current movie; Alt+Enter (key-up) and losing activation stop playback and remember why (0x00404c20); Alt+F4 posts `WM_CLOSE` to the main window; messages 0x407/0x408 forwarded by `MainWndProc` reposition the Bink buffer (0x00404f40 `BinkBufferCheckWinPos`; 0x00404f80 moves the window back over the render window) | high |
| 0x0070c1f0 / 0x0070c1e0 | `IsPlaying`, `Skip(skipAll, force)` | a non-forced skip only stops the current movie when it is playing and skippable; the skip-all flag is recorded either way | high/med |
| 0x00405a50 | `~CExoMoviePlayerInternal` | sets the quit flag, signals the thread and waits until it has exited, then closes the movie | high |

While a movie plays the main loop draws nothing (Bink blits straight into its own window) and the
sound mode is 3. `PlayQueuedMovies` (0x00602650, skipped when Disable Movies is set) also pauses
the client and server world timers (when a server exists), then starts the client's queued list asynchronously.
0x00602af0 plays a list at once and blocks in a modal loop (0x005f6f20) until the player stops,
or returns without playing when Disable Movies (client+0x1f8) is set; it serves script
`PlayMovie` (0x00540ed0 → 0x00602cf0, sound mode 3 pushed and popped around it) and 0x00602d40
(from 0x005ee220 and from `PlayLegalMovies` 0x00602dc0, which queues `leclogo`, `biologo` and
`legal` unless client+0x1fc is set (Initialize clears it) and plays them this way).
0x00403cf0 / 0x00403de0 enter and leave the movie display mode (fullscreen switches to 640×480×32
and the main thread's priority is lowered while movies play).

## Open questions

- The fields of the 0x3c module-transition block at `CAppManager+0x14`. (The two zeroed 0x184-byte
  blocks at `CAppManager+0xc/+0x10` are only created and destroyed; nothing else in the binary
  reaches them through `g_pAppManager`, so they look unused.)
