# Renderer and GUI of swkotor.exe

The OpenGL renderer (context, extensions, frame, models, textures) and the GUI system (manager,
panels, controls, `.gui` loading, fonts, input routing). Addresses are for the Steam
`swkotor.exe` after SteamStub removal (`kotor/re/bin/swkotor_unpacked.exe`). All class and
function names here are ours; the binary has no RTTI or log strings for these classes, so they
follow the NWN Aurora vocabulary (`CAur*` for the rendering library, `CSWGui*` for the GUI) and
are kept in [names.tsv](names.tsv). Confidence: **high** = read in the code and
consistent with strings/imports; **med** = role clear, name a guess; **low** = plausible only.
The whole page was rechecked claim by claim on 2026-10-07 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check"
rests on static reading alone and is surprising enough to test before relying on it.

Start-up, the main loop, input, audio and movies are in [app.md](app.md).

## How a frame is drawn

`WinMain` applies a pending video-mode change, clears the buffers (unless a movie is playing) and
calls the client main loop. Inside it, `CClientExoAppInternal::UpdateObjectsAndRender` (0x006048c0)
updates the client objects and renders the 3D world through the module's camera and scene
(`CSWCModule::Render` 0x00644650 → `CAurCamera::Render` 0x0045c540 → `CAurScene::Render` 0x004512d0
→ passes 0x004514f0); later in the same loop `CSWGuiManager::Render` (0x0040cc50) draws every
active panel, tooltip and the software cursor in 2D on top. Back in `WinMain` the server loop
ticks, then the console overlay (0x0044d6a0) is drawn and `SwapBuffers` presents (both skipped
while a movie plays). During long loads `RenderLoadingFrame` (0x00401c10) draws a GUI-only frame
instead (the load screen panel, `CSWGuiLoadScreen` 0x0067a710).

## Renderer

KOTOR draws with fixed-function OpenGL 1.x plus extensions (ARB vertex programs, NV register
combiners or ATI_fragment_shader, VBOs, pbuffers). The rendering library sits roughly between
0x0041d000 and 0x004ab000 and keeps the NWN "Aurora" shape: a refcounted display object,
named scenes, cameras, and "parts" built from MDL nodes. The game hooks resource loading into it
through a callback table. No class names survive in the binary, so the `CAur*` names below are
descriptive (they follow the NWN Aurora layer), and so are the `GL_*` / `Render_*` helper names.

Defaults in .data: render size 800x600, 60 Hz, 32 bpp (`g_nScreenWidth` 0x0078d1d4, `g_nScreenHeight`
0x0078d1d8, refresh 0x0078d1dc, bpp 0x0078d1e0). The client's display-mode code (see
[app.md](app.md)) and the credits panel write them; display slot 5 would also store the client
size there, but nothing calls it.

### Display object and context creation

The display is a singleton of 0xb8 bytes with vtable 0x00741518 (12 slots). Its abstract base vtable
0x007414f0 has 10 slots: slot 0 is the base destructor 0x0044da40, slots 1-9 are pure-virtual.
`CAurGLDisplay::GetInstance` (0x0044ecd0, reached through the thunks 0x0044ed70 → 0x0044ed60)
creates it (fullscreen flag +0xac and HGLRC +0xb4 zero, stored gamma +0xb0 = 1.0), counts references
(`g_pAurGLDisplay` 0x007b921c, count 0x007b9218) and returns it; `ReleaseInstance` (0x0044d940) frees
it when the count reaches zero. Client init (0x005f8550) stores the pointer in the app global
`g_pDisplay` 0x007a39f8, and client shutdown (0x00604130) releases it. The rest of the game calls it
only through these slots: `SetVideoMode` 0x00403800 uses 1, 2, 3 and 8; the window procedure and
activation code use 1, 6, 7 and 9; the movie player and the options panels use 1 and 9; nothing
calls slots 4, 5, 10 or 11.

| slot | addr | name | what it does | conf |
|---|---|---|---|---|
| 0 | 0x0044ed40 | DeletingDestructor | destructor 0x0044ec60, then free | high |
| 1 | 0x0044d6d0 | IsFullscreen | returns the flag at +0xac | med |
| 2 | 0x0044dab0 | CreateContext | the real context setup (below) | high |
| 3 | 0x0044d6e0 | FindBestDisplayMode | picks the largest enumerated mode with w/h/bpp/Hz all at or below the request, tests it (CDS_TEST) and, when asked, writes it back | med |
| 4 | 0x0044e3b0 | CreateContextBasic | older path: plain ChoosePixelFormat, no multisample; no caller | med |
| 5 | 0x0044e9e0 | SetViewportSize | with a context: stores the size at +0xa0/+0xa4 and in the screen globals, glViewport; no caller | med |
| 6 | 0x0044d8d0 | RestoreDesktop | gamma 1.0 (not stored) and, if it changed the mode (+0xa8), the desktop display mode (on deactivate) | med |
| 7 | 0x0044d900 | ReapplyDisplayMode | puts back the stored gamma and, if +0xa8, the stored fullscreen DEVMODE at +4 (on activate) | med |
| 8 | 0x0044ea30 | DestroyContext | frees the ten vertex programs and the render targets (0x00432180), deletes the context, can restore the mode and destroy the render window | med |
| 9 | 0x0044d990 | SetGamma | builds a 3x256 ramp from the brightness value and calls SetDeviceGammaRamp; a second argument of 0 also stores the value at +0xb0 | high |
| 10 | 0x0044d970 | GetGLContext | returns the HGLRC at +0xb4 | med |
| 11 | 0x0044d980 | wglMakeCurrent thunk | | high |

Steps inside `CreateContext` (0x0044dab0), with arguments main HWND (unused), render HWND, width,
height, bpp, refresh, fullscreen, colour bits and depth bits (`SetVideoMode` passes bpp for the last
two); it returns 1 on success, 0 on failure:
1. The first time through, `GL_ProbeMultisampleSupport` (0x0042e040) makes a hidden "Test GL
   Window" with a throwaway context. It looks up `wglGetExtensionsStringARB` and
   `wglChoosePixelFormatARB` and sets the WGL_ARB_multisample bit when the WGL string lists it;
   on a driver with GL_ATI_fragment_shader only when Windows is newer than 4.x. CreateContext also
   invalidates the light-0 cache (0x0078e388).
2. Fullscreen: it enumerates the modes for an exact w/h/bpp/Hz match and applies it with
   ChangeDisplaySettings (CDS_TEST first; a failed test returns 0; then CDS_FULLSCREEN), keeping the
   DEVMODE at +4 and setting +0xa8. With no exact match it carries on windowed. The window gets
   WS_POPUP and topmost when fullscreen, WS_OVERLAPPEDWINDOW otherwise (both with WS_CLIPCHILDREN),
   is placed at 0,0, sized with AdjustWindowRect, sent WM_SIZE and shown.
3. Pixel format: when anti-aliasing is set (0x007a6888 > 0) and `Render_SetAntiAliasing`
   (0x0044f2f0, which asks `GL_IsMultisampleFormatAvailable` 0x0044f140) agrees, it uses
   wglChoosePixelFormatARB: window, full acceleration, double buffer, the colour bits, 8 alpha,
   min(depth bits, 24) depth, 8 stencil, N samples. If that fails, or otherwise, it uses a classic
   PFD: double-buffered RGBA, 32-bit colour, 8 alpha, 24 depth, 8 stencil.
4. wglCreateContext / wglMakeCurrent, then `GL_LoadExtensions` (0x00436490, through the thunk
   0x0044f070); with vertex programs on, 0x004a2400 unbinds the program.
5. `GL_CaptureMainContext` (0x00425c30) remembers the main HGLRC/HDC (0x007a6854 / 0x007a47e4) and
   clears the bound-texture cache. 0x00422360 rebuilds the console font and texture-quality state.
   `GL_CreateFrameBufferTargets` (0x00426cc0) and `GL_CreateEffectTargets` (0x00427c90) build the
   pbuffers and screen-copy textures for soft shadows and frame-buffer effects.
6. If vertex programs are in use (`GL_UseVertexPrograms`, i.e. GL_ARB_vertex_program is present),
   it enables GL_VERTEX_PROGRAM and builds ten `CAurVertexProgram` objects (0x004a27d0: 0x201c
   bytes holding source text, bound via 0x004a24d0). All are `!!ARBvp1.0` source (two of them
   assembled per backend in `GL_LoadExtensions`, 0x0083028c / 0x00830290); the `!!VP1.0` (NV)
   alternatives, whose comments name them standard, skinned, bumpy-shiny and bumped-out, are only
   chosen when 0x0078e5ec is 0, which never happens.
7. It enables GL_MULTISAMPLE when it got a multisample format (else disables it if a sample count
   was set before), and applies v-sync through `wglSwapIntervalEXT`.

The app-side video-mode function `SetVideoMode` (0x00403800, see [app.md](app.md)) wraps all of
this. It destroys the old context (slot 8), reads "Disable Vertex Buffer Objects" from
`[Graphics Options]` (1 calls `Render_DisableVBO` 0x0044ef60), recreates the "Render Window", calls
slot 3 when fullscreen and then slot 2. After the context exists it reads "Disable Write-Only VBO"
(1 calls `Render_DisableWriteOnlyVBO` 0x0044ef70, any other value `Render_EnableWriteOnlyVBO`
0x0044ef80, overriding the GeForce3 default below), destroys the old window and calls
`GL_SetDefaultState` (0x00401bb0): black clear colour, and cull face, depth test, lighting,
texture 2D, blend (src-alpha / one-minus-src-alpha) and alpha test all enabled.

### Extension loading and capability bits

`GL_LoadExtensions` (0x00436490, high) does the following:
- It tests the GL and WGL extension strings with `GL_HasExtension` (0x0045f980, a space-separated
  token match) and ORs one bit per feature into `g_nGLCaps` (0x007bb85c). The bit values sit in a
  table at 0x0078e480. In order from bit 0: EXT_bgra, ARB_multitexture, EXT_texture_env_combine,
  NV_register_combiners, EXT_texture_cube_map, EXT_fog_coord, EXT_secondary_color,
  NV_vertex_program, EXT_texture_filter_anisotropic, (bit 9 unused), NV_texture_shader,
  NV_vertex_array_range, NV_vertex_array_range2, NV_fence, ARB_texture_compression,
  EXT_texture_compression_s3tc, ATI_pn_triangles, EXT_compiled_vertex_array,
  WGL_ARB_render_texture, SGIS_generate_mipmap, ATI_fragment_shader, ARB_vertex_program,
  ARB_vertex_buffer_object, NV_register_combiners2, EXT_stencil_two_side,
  WGL_NV_render_texture_rectangle, WGL_ARB_buffer_region, WGL_ARB_multisample (set by the probe),
  WGL_EXT_swap_control, and ARB_depth_texture at bit 29.
- It resolves 202 entry points with wglGetProcAddress into globals 0x007bb524-0x007bb854. The
  important ones are proposed by role: `g_glActiveTextureARB` 0x007bb80c,
  `g_glClientActiveTextureARB` 0x007bb6b0, `g_glCompressedTexImage2DARB` 0x007bb774, the VBO set
  (Bind 0x007bb7b4, Data 0x007bb544, Gen 0x007bb5b4, Map 0x007bb634, Delete 0x007bb7bc), the ARB
  program set (Bind 0x007bb788, String 0x007bb580, EnvParameter4f 0x007bb850), the pbuffer set
  (Create 0x007bb530, GetDC 0x007bb6b8), and `wglSwapIntervalEXT` 0x007bb538.
- If NV_vertex_program is present and the renderer string contains "GeForce3", write-only VBOs are
  turned off (0x0078e398 = 0; the ini switch read later by `SetVideoMode` can override it).
- It reads the maximum anisotropy (when supported, into 0x007a6858), builds a 64x64 noise texture
  (`GL_CreateNoiseTexture` 0x004263c0), and picks the texture-shader backend. With
  ATI_fragment_shader the hook is 0x0047a2f0, and `GL_LoadExtensions` itself builds the ATI
  fragment shaders through 0x004794e0. Otherwise it is the NV register combiner / texture-env
  switch 0x0042e600. The hook pointer is `g_pfnSetupTextureShader` 0x007a47e0; two sibling hooks
  sit at 0x007a6820 and 0x007a47dc (ATI 0x0047a280 / 0x0047a2a0, NV 0x00424940 / 0x00424960).
  Each branch also assembles its two ARB vertex-program sources (0x0083028c, 0x00830290).
- It creates the vertex-buffer manager `g_pAurVertexBufferManager` (0x007a68a4): the VBO flavour
  (0x00436400, 0x5c bytes, vtable 0x0073f4fc) when `GL_UseVBO` (0x0045fc90) agrees, else plain
  client memory (0x00436390, 0x28 bytes, vtable 0x0073f4b8), and calls its slot 11. Both share
  base vtable 0x0073f488.

Cached capability tests, each keeping its answer in a .data word that holds -1 until first asked:
`GL_UseVertexPrograms` 0x0045f770, `GL_HasMultitexture` 0x0045f710, `GL_HasAnisotropy` 0x0045f8e0,
`GL_GetStencilBits` 0x0045fd00 (glGetIntegerv). 0x0045f580 (swap control) is a plain bit test with
no cache. There are also several combined path tests (0x0045f640, 0x0045f680,
0x0045f7b0, 0x0045f7e0, 0x0045f820, 0x0045f860, 0x0045f8b0, 0x0045fbd0). The .data flag 0x0078e5ec
is never written and is 1, so vertex programs are always ARB ones: `GL_UseVertexPrograms` needs
both that flag and GL_ARB_vertex_program, and the NV `!!VP1.0` branches are unreachable.

### Per-frame render chain

| step | addr | name | notes | conf |
|---|---|---|---|---|
| 1 | 0x004041f0 | WinMain loop | applies a pending mode change (`SetVideoMode`), glClear of colour/depth/stencil unless a movie plays, GL_LIGHT0 on/off by flag 0x007a3c50 (0x0044da60/0x0044da80, cached in 0x0078e388), then client MainLoop | high |
| 2 | 0x00602eb0 | CClientExoAppInternal::MainLoop | see app.md; the render work happens in the next two calls | high |
| 3 | 0x006048c0 | CClientExoAppInternal::UpdateObjectsAndRender | runs client object updates (vtable +0x74) under a timer, then the module render | med |
| 4 | 0x00644650 | CSWCModule::Render | only with an area (+0x48) and a camera (+0x40); advances the module clock +0xb8 unless the game is paused (client +0x1cc, read by 0x005ee910), runs the area's per-frame visual update (0x006097f0: time of day, weather flashes); unless the GUI manager's fullscreen flag (+0x70) is set, calls camera slot 2 | med |
| 5 | 0x0045c540 | CAurCamera::Render | viewport (a camera rectangle wholly off-screen skips the frame), gluPerspective (0x0045c300) or, when the FOV +0x1d0 is 0 or less, ortho (0x00404b60), six frustum planes, view matrix (0x00425ca0), sets `g_pAurCurrentCamera` 0x007bb4e8 for the call to scene slot 6 and clears it after, restores the viewport | high |
| 6 | 0x004512d0 | CAurScene::Render | timing (`Render_GetMicroseconds` 0x0044f320), stats, `AurTextures_Update`, sets `g_pAurCurrentScene` 0x007b92a0, depth func LEQUAL, vertex/normal/texcoord arrays on, alpha test GREATER, lighting on; a scene with nothing to draw (+0xa0 and +0xcc both 0) gets slot 72 (0x00450d60) instead; otherwise it ticks the scene's timed helper (+0x84, 0x004a5e30) with the frame delta, calls slot 46, records stats and calls slot 42 | high |
| 7 | 0x004514f0 | CAurScene::RenderPasses | vertex-program constants from the current camera; fog (slot 73, 0x00450de0); ambient zero, then the opaque pass (slot 49, 0x00450c30), then the scene ambient (+0x88); stencil shadow volumes (slots 69/70, 0x00456300) only when 0x007b92e4 is set, and nothing writes it (needs a runtime check); stencil clear and soft shadows (slot 47, 0x00451a50) when scene+0xd4 and the shadows switch 0x0078e3a8 are set; slot 48 (0x00450b50); two debug overlays (0x00450fa0, 0x004510e0); slots 68 and 58, 0x00432720; the blended pass with depth writes off (slot 51); slot 57 (stencil mark); screen effects (0x00437520) when scene+0xd4; slot 50 (0x00457ec0); late screen effects (0x004361f0) when scene+0xd4; then a state reset | med |
| 8 | 0x0040cc50 | GUI manager render | 2D pass over the 3D frame; see the GUI section | high |
| 9 | 0x0044d6a0 | Console_Render | console lines and watches on top, after the server tick; skipped while a movie plays | med |
| 10 | 0x004041f0 | SwapBuffers | through GetDC on the render window, skipped while a movie plays (`IsMoviePlaying` 0x005edb40, which also skips glClear) or while a mode change is pending | high |

`Render_BeginFrame` (0x0044ed90) is called from the client loop, the GUI render, `RenderLoadingFrame`
and a GUI control method (0x004193f0), so it runs at least twice in a normal frame. It does an
optional throttle (a clock() busy-wait of 0x007b9270 ms when that is non-zero), records free
physical memory (KB, 0x007b9274), and calls `AurTextures_Update` (0x00421ee0), which finishes
queued texture loads (the scene render calls it too). `RenderLoadingFrame` (0x00401c10, see
app.md) is the stand-in frame used during long loads (module load, save and load, 17 callers). It
draws the GUI (load screen and progress) and, unless told not to render or a movie plays, clears
first and draws the console and swaps after; it then pumps messages, can run one server tick,
updates sound and the net status, and finally runs the GUI render once more with a zero delta. The
client loop's call during a module transition passes "don't render", so there `WinMain` clears and
swaps.

Scenes are named objects (0x2c4 bytes, vtable 0x00741708, 75 slots; constructor 0x00458790; factory
0x00458e70) kept in `g_apAurScenes` 0x007b9398 / `g_nAurScenes` 0x007b939c and found with
`CAurScene::FindByName` 0x0044fd60 (case-insensitive). Each area makes one "mainscene" when it
loads (0x00607610 stores it at area+0x184). GUI 3D views (character models in menus and the 3D
cursor model, 0x004174b0) make their own "scene" plus "camera". Cameras are 0x234-byte objects
(`CAurCamera::Create` 0x0045d930, vtable 0x00741b20, multiple inheritance with a secondary vtable
at +4). The module camera lives at module+0x40 and is created in 0x0063f660.

### 2D / GUI pass helpers

| addr | name | what | conf |
|---|---|---|---|
| 0x004591b0 | Render_Begin2D | records the current viewport as the base of the viewport stack, disables lighting and depth test, pushes a unit ortho projection, identity modelview, alpha blend | high |
| 0x004592b0 | Render_End2D | restores the projection, re-enables lighting and depth | high |
| 0x004592f0 | Render_PushViewport | pushes a sub-rectangle viewport relative to the current one (returns 0 and pushes nothing when it is empty or off-screen), optionally fills it with a colour quad and optionally clears depth/stencil and turns depth test on (used for GUI 3D views and clipping) | med |
| 0x00459580 | Render_PopViewport | pops it, restoring the parent viewport and its depth-test state | med |

These have 9 to 12 callers, all in GUI code: the manager (0x0040ae80, 0x0040cc50),
`CSWGuiPanel::Render` 0x0040b760, the render methods of individual panels and controls (0x0067ab00, 0x00685330, 0x0068b4a0, ...)
and of the list box (0x0041a3e0).

### Models: parts and draw calls

`CAurPart::CreateFromMdlNode` (0x00448a70) builds the render object for each MDL node by switching
on the node-type flags. It matches the whole flag word exactly; any other value gives no part:

| flags | constructor | vtable | kind |
|---|---|---|---|
| 0x001 | 0x00447b20 (0x004457a0) | 0x00740ae8 | dummy / base part |
| 0x003 | 0x00447b90 (0x00445a40) | 0x00740c08 | light |
| 0x005 | 0x0049d5c0 | 0x00743478 / 0x00743500 / 0x00743588 / 0x00743610 | emitter, by its `update` string: `Fountain`, `Explosion`, `Single`, anything else (a 0x290-byte object from 0x0049d1d0) |
| 0x009 | 0x00447c80 | 0x00740eb0 | camera node |
| 0x011 | 0x00447ce0 | 0x00740f30 | reference |
| 0x021 | 0x00447d60 (0x00445840) | 0x00740b68 | trimesh |
| 0x061 | 0x00487510 | 0x00740e10 | skin |
| 0x0a1 | 0x00447dd0 | 0x00740fb0 | animated-UV mesh |
| 0x121 | 0x00447e90 (0x00447980) | 0x00740d78 | dangly mesh (keeps its own copy of the vertex positions) |
| 0x221 | 0x00447e30 | 0x00741048 | AABB walkmesh |
| 0x401 | 0x0063e7c0 | | none: a stub that returns 0 |
| 0x821 | 0x004480c0 (0x004478d0) | 0x00740ce0 | lightsaber |

The flag values agree with [mdl.md](../formats/mdl.md) (dangly 0x121, AABB 0x221). (high)

Part vtable slot 23 (+0x5c) is the stencil shadow-volume pass, not the colour draw. Trimesh, saber,
dangly, animmesh and AABB share `CAurPartTriMesh::RenderShadowVolume` 0x00474220: it finds the silhouette edges
against the light and draws the extruded volume with `GL_DrawShadowVolume`, or draws the mesh twice
with front faces CW/CCW and stencil INCR/DECR. Skin has its own `CAurPartSkin::RenderShadowVolume` 0x00477b90, which does the same in a
vertex program after loading the bone matrices into program parameters. 0x00474710 (from 0x0044ff50)
walks the part tree calling this slot. (high) Slot 24 (+0x60) is material setup (0x00473900, using
glMaterialfv; all six mesh kinds share it) and slot 25 (+0x64) is the draw. The scene's mesh loops
(0x00455710, 0x00455a40, 0x00455b60) bind the material's diffuse (0x0047adf0), apply layer 0's
blend (0x0047af70), then call slot 24 and slot 25. Slot 25 is 0x00477830 for a trimesh (it picks
the draw path, see [Environment maps](#environment-maps)), 0x00477b60 for a dangly mesh (the same
draw, behind the flag 0x0078e844, which is 1), 0x0048d6c0 for skin, 0x00471500 for an animated-UV
mesh, 0x00471860 for a saber (immediate mode), and 0x00471560 for an AABB walkmesh. That last one
draws only a debug wireframe, behind the flag 0x007fbf5c, which is 0 and never written, so walkmeshes
are never drawn. (high)

The leaf draw is `CAurPartTriMesh::DrawIndexed` (0x0046f900, 22 callers, one per
material/shader variant). It does nothing when 0x0078e614 is 0. It calls `GL_DrawElements`
(0x00425ab0, which binds the element VBO when VBOs are on) once per index list. It adds one draw
call per mesh to 0x00827fb4 and each list's index count / 3 to the triangle count 0x00827fb0.
`Render_ResetFrameStats` 0x0046ee00 zeroes those counters.

Vertex streams go through small VBO-aware helpers: `GL_SetVertexPointer` 0x00425900,
`GL_SetColorPointer` 0x00425970, `GL_SetNormalPointer` 0x004259e0, `GL_SetTexCoordPointer`
0x00425a40, `GL_SetClientActiveTexture` 0x00425250, and `GL_SetMeshArrays` 0x00425520 for a whole
layout. glDrawArrays is used only for quads (particles and the GUI quad batch, 0x00431cc0 /
0x00431eb0 from `AurGui_FlushQuadBatch` 0x0045a170, and 0x00426230), lines (a line loop in
0x00426000) and debug drawing (0x00431bb0-0x00431f70). `GL_DrawShadowVolume` 0x00426660 draws
stencil shadow volumes. `GL_SetProgramEnvParam` 0x0044f820 writes vertex-program constants
(17 callers).

### Textures

- Requests: `AurTexture_Request` (0x00423a60, 12 callers) goes to `AurTexture_FindOrCreate`
  (0x00423490) and returns a 0x18-byte reference to the texture. `AurTexture_FindOrCreate` searches
  resident textures by name (`AurTexture_Find` 0x00420ac0, case-insensitive, over
  `g_apAurTextures` 0x007a4798). If the name is missing it creates a `CAurTexture` (0x00423150,
  0xec bytes, vtable 0x0073f160 on base 0x0073f0a8) and queues it on `g_apAurPendingTextures`
  0x007a4770. "NormCubeMap" is built in: 0x004233e0 creates it, and `FinishLoad` generates its
  faces (0x00420c20) instead of loading an image.
- `AurTextures_Update` (0x00421ee0, called from `Render_BeginFrame`, `CAurScene::Render`, the GUI
  quad draws and `CSWCArea::LoadArea`) runs `AurTextures_ProcessPending` (0x004217f0) when the queue
  is not empty. That drains the queue, newest first. `CAurTexture::FinishLoad` (0x004216a0) calls
  `CAurTexture::LoadImage` (0x0041fa30) and then `CreateGLTextures` (0x00420970).
- Image data comes through a renderer callback table at 0x0078d404. Its defaults read loose files
  ("%s.tga" 0x0045e350, "%s.dds" 0x0045f4a0, "%s.plt" 0x0045e510).
  `Render_InstallResourceCallbacks` (0x0070d9c0, called from client init) replaces them with
  resource-manager readers: 0x0070c790 (TGA, slot 0x0078d404), 0x0070d380 (DDS, 0x0078d40c),
  0x0070c6e0 (PLT, 0x0078d41c), 0x0070d510 (TPC, 0x0078d420, see [resman.md](resman.md)) and
  others. It also sets the texture quality (`AurTextures_SetQuality` 0x00421d90). The TPC/TGA
  formats themselves belong to the resources agent.
- Upload: `CAurTexture::CreateGLTextures` (0x00420970) generates one GL name per tile and
  dispatches, choosing between each pair of paths by the texture's vtable slot 12 (+0x30). 2D
  textures go to `Upload2D` 0x00424980: DXT through `glCompressedTexImage2DARB` (the format comes
  from a table at 0x0073f36c: index 7 is DXT1, 8 is DXT5), otherwise glTexImage2D/SubImage2D per
  level, or gluBuild2DMipmaps, or SGIS auto-mipmap. It also sets wrap/clamp and filtering.
  0x00424dd0 is an alternative 2D path. Cube maps go to 0x00423f90 (plain) and 0x00424230 (can
  take compressed faces). The other callers of gluBuild2DMipmaps are a computed 256x256
  luminance-alpha lookup texture (0x00423d80: luminance is the column, alpha a power curve of the
  row; used by the NV and ATI texture-shader setups) and a cube mip builder (0x00425ea0, used for
  NormCubeMap). 0x004260a0 uploads BGRA dynamic textures. 0x00420ea0 fits sizes to a power of two
  before calling it: a size of 2^n + 1 is trimmed to 2^n, and any other size that is not a power
  of two is refused.
- Binding: `GL_SetActiveTextureUnit` 0x0041fe80 (unit in 0x007a6898), and `GL_BindTextureCached`
  0x00420440 / `CAurTexture::Bind` 0x004204f0, which record the binding in the six-entry cache
  0x007a683c and apply anisotropy (0x007a685c).

### Materials: blending and alpha test

A mesh's material object (constructor `0x0047b290`, our `CAurMaterial`) is built by `0x0047b560`
from up to four texture names. A name equal to `NULL` counts as none. Only the first (diffuse)
texture's TXI is read, through `0x0047b110`. Per texture layer the material holds a source and a
destination blend factor, as indices into the table at `0x0073f270`:
0 `GL_SRC_ALPHA`, 1 `GL_ONE_MINUS_SRC_ALPHA`, 2 `GL_ONE`, 3 `GL_ZERO`, 4 `GL_SRC_COLOR`, 5
`GL_DST_COLOR`, 6 `GL_ONE_MINUS_DST_ALPHA`, 7 `GL_DST_ALPHA`. (high)

- The constructor's default is one layer with (0, 1): **ordinary alpha blending** (`SRC_ALPHA,
  ONE_MINUS_SRC_ALPHA`). (high)
- The TXI keyword reader (`0x0047abd0`) matches keywords without regard to case. Besides
  `blending` it takes `bumpmaptexture`, `bumpyshinytexture` and `envmaptexture` (names kept at
  +0x1c/+0x20/+0x24 until `0x0047b560` requests them), `decal` (+0x40), `renderbmlmtype` (+0x44)
  and `wateralpha` (+0x48). It sets layer 0 to (0, 2) `SRC_ALPHA, ONE` for `blending additive` and
  to (2, 3) `ONE, ZERO` for `blending punchthrough`. The value must match exactly, and any other
  value leaves the default. (high)
- Applying a layer (`0x0047af70`, from `CAurPartTriMesh::ApplyMaterial` 0x00473900, the scene's
  mesh loops and the particle draws, 11 callers in all) calls glBlendFunc with the pair. It turns
  depth writes **off only for (0, 2)** (additive). It sets the alpha test to `GREATER 0.35`
  (`0x00798a90`) for (2, 3) and to `GREATER 0` otherwise. The flag `0x00798a8c` that enables the
  alpha test is 1 in .data and never written. The GUI quads use `0x0047b000`, which applies layer 0
  the same way but leaves depth writes alone. (high)

So a texture's alpha is transparency by default: blended, depth-written, only alpha 0 discarded;
punch-through cuts at 0.35. The env-map and bump-map paths (register combiners / ARB programs,
not traced) evidently don't use the diffuse alpha as opacity: env-mapped droids and the
bump-mapped rancor (`c_rancor01`, AlphaMean 0.76) are solid in the game. (inferred)

### Environment maps

How a mesh with an environment map is drawn (all *high* from the code, the unnamed functions are
ours). The material (`0x0047b290`, texture names read by `0x0047abd0`) holds the bump map at
+0x10 and the environment map at +0x14 (`bumpyshinytexture`, then `envmaptexture`, which wins when
both are given). A creature's appearance.2da `envmap` is the part's own override (part +0x40 →
+0x1a8) and wins over the texture's. The draw path is chosen per mesh by `0x00470d30` (the switch
in `0x00477830`). It depends on several things:

- the mesh's lightmap, dropped when the lightmap texture did not load;
- whether it has a bump or environment map;
- the material's `renderbmlmtype` and `wateralpha`;
- the GL capability bits (NV register combiners, ATI fragment shader, ARB vertex programs).

The environment map is sampled with texgen `REFLECTION_MAP` (`SPHERE_MAP` for a 2D texture). For a
cube map, the texture matrix is made from the camera's orientation (`0x0046f780`), so the lookup
uses the reflection vector in world space. `0x0046ff70` and `0x004703f0` have a check that would
draw a diffuse that is neither DXT1 nor DXT5 without the reflection. That check runs only when
0x0078e63c is 0 or 0x007a46d4 is set, and both are constants (1 and 0) that nothing writes. So the
reflection is drawn whatever the diffuse format.

What the combination is, by path (the diffuse's alpha is `a`):

| Path | Used for | Colour |
|---|---|---|
| lightmapped, fixed function (`0x0046fb10`): lighting off, colour 1. The diffuse is drawn with `ONE, ZERO`, the lightmap with `DST_COLOR, ZERO` (which also multiplies the destination alpha by the lightmap's alpha), then the environment map with `ONE_MINUS_DST_ALPHA, ONE` | rooms with a lightmap and an environment map (on cards without the combiner path) | `diffuse * lightmap + env * (1 - a)` |
| lightmapped, combiners (`0x00470590`): the diffuse times the lightmap (texture shader 0x1a, `ONE, ZERO`), then the environment map drawn with `ONE, ONE` (texture shader 0x15; its mask was not decoded). Both go through the texture-shader hook (`g_pfnSetupTextureShader`), and the ATI hook does nothing for 0x15 | the same on NV hardware | the same sum (*inferred*) |
| unlightmapped, NV register combiners (`0x0046ff70`, shader 0x13, `0x0042e600`) | creatures and placeables on NVIDIA | `diffuse * light + env * (1 - a)` |
| unlightmapped, ATI fragment shader (`0x0046ff70`, shader 0x13 in `0x0047a2f0`; the program is built by `0x004794e0`) | the same on old Radeons | `lerp(a, diffuse * light, env)`, i.e. `a * diffuse * light + (1 - a) * env` |
| unlightmapped, plain multipass (`0x0046ff70` without a texture shader) | everything else (Intel, current AMD) | the environment map (lit), then the diffuse over it by `SRC_ALPHA, ONE_MINUS_SRC_ALPHA`: `light * (a * diffuse + (1 - a) * env)` |

So the two hardware-specific paths of the original disagree on a creature (the NV sum shows the
diffuse in full plus the reflection, the other two blend by alpha); the data is made for blending
by alpha, where a low alpha means a mirror: the Sith soldier's `N_SithSoldier03` has AlphaMean 0.55
and a mid-grey diffuse, which is dark gunmetal that way and silver chrome as a sum. We follow the
blend (unlit reflection, as the ATI shader): `lib/render_gl/shaders.ctx`, lightmapped meshes keep
the sum. The part's opacity (part `+0x84`, the alpha controller; it is multiplied by the owner's
+0xd8 when the part has an owner at +0x40) goes to the texture shader's constant colour alpha
(through `0x007a6820`), not into the blend.

### Lightmaps: black texels, missing lightmaps

A lightmapped mesh is drawn as diffuse times lightmap and nothing else: the plain paths
`0x0046fa40` (case 0xc of the switch in `0x00477830`, texture shader 0x1a, diffuse x lightmap) and
`0x0046fb10` (case 0xe, fixed function: lighting off, the lightmap pass `DST_COLOR, ZERO`) add
nothing after the lightmap's multiply. So a texel the level designers baked black draws black in
the original, whatever lights are near. (high, from the code and the data)

The Endar Spire has such places: in `m01aa_03a` the blocked-off corridor ends are closed by
`Plane01` (two quads, `LHR_wall07` with `M01aa_03a_lm0`, self-illumination 0), whose lightmap
charts (u 0..0.25, v 0.88..1) are the black block of `m01aa_03a_lm0` (texels 1/255), and the parts
of the room's big meshes inside those dead ends (`Object2723`, `Object96`, `Object75`, `Object26`,
`Object2715`: lightmaps `lm0`/`lm3`) sample black texels too. The pitch-black side passage with
smoke and the black far end seen from room `M01aa_03a` (leader near x 45, y 17..33, after the
first cutscene) are that data, not a renderer fault; drawing lightmap only (diffuse off, lighting
off) shows the same black areas. No other mesh of that lightmap uses its v 0.88..1 band, which
confirms our V orientation for TGA lightmaps. Our enhanced renderer's Lifted lightmaps (ours, the default) lift
such texels to a dark floor ([../design/enhanced-render.md](../design/enhanced-render.md), "Lifted lightmaps").

When the lightmap texture fails to load, `0x00470d30` clears the mesh's lightmapped flag (mesh
+0x184; the material's lightmap at +4 is checked by `0x00420bf0`) and the mesh takes the
unlightmapped, lit path. Two such references exist on the Endar Spire and resolve to nothing in
the install: `m01aa_04a_a0002t` (`m01aa_04a`'s `Object5044`) and `DOR_LHR02_a00004` (the door
`dor_lhr02`'s `Object02`). Ours does the same: with no lightmap a lit mesh takes ambient plus the
frame's lights (`lib/render_gl/shaders.ctx`, `fx_shaders.ctx`).

### Shadows, grass, frame-buffer effects, options

The client options loader (0x0061dbe0, which reads `[Graphics Options]`) calls small setters:
- Shadows: 0x0044ee20 / 0x0044f080 (flag 0x0078e3a8; turning shadows off also clears soft shadows).
- AllowSoftShadows = 1: 0x0044ef90 (sets 0x007bb860 and clears soft shadows).
- Soft Shadows: 0x0044ee50 / 0x0044ee60 (flag 0x0078e420; turning them on also sets shadows).
- Grass: 0x0044ee30 / 0x0044ee40 (flag 0x0078e3ac).
- Texture Quality: kept at options +0x3c and passed to 0x005ed8f0.
- Frame Buffer effects: 0x0044ee70 / 0x0044ee80 (flag 0x0078d98c), through 0x0061d750. That also
  switches every party member that has client effect 8000 or 8002 to the other one. (med)
- V-Sync: `Render_SetVSync` 0x0044ee90 (only when the swap-control extension is present).
- Brightness: kept at options +0x18. After the loader, 0x005f4710 passes the brightness value
  (0x0061d590) to display slot 9.

Anti-aliasing is not read by this loader. 0x0061d710 (options +0x44, called from
`CClientExoAppInternal::Initialize` and the graphics-options panels) calls `Render_SetAntiAliasing`
0x0044f2f0. That checks that a multisample pixel format with that sample count exists, then stores
the count in 0x007a6888 (the previous one in 0x0078d440).

Frame-buffer effects copy the screen into a 512x512 pbuffer target bound as a texture rectangle or
a 2D texture (0x00426cc0). They then run passes in pbuffers of 64, 128, 256 and 512 square
(0x00427c90), in 0x0042b370-0x0042d9a0, 0x00432780-0x00433970 and 0x00435bd0. Each pass makes the
pbuffer current, draws, calls glFlush, then switches back. Stage setup is a switch in 0x004299c0.

### Engine-coded visual effects (the ProgFX columns of visualeffects.2da)

A visualeffects.2da row names models to hang on an object (the `imp_*_node` columns), and three
numbers for effects the engine draws in code: `progfx_impact`, `progfx_duration`,
`progfx_cessation` (the energy shields, 2040-2048, have only a duration code, 1413-1421). All of
this is the client's visual effect record, `CSWCVisualEffect` in our words: a 0xf8-byte plain
struct (no vtable) made by `FUN_0063d970` (the add method, slot 45, of the client object that owns
the list of effects at +0x6c; that object is the effect's target, and a row-1020 record is not
added while the list holds one) and filled by `FUN_006a1880` (`0x006a1880`-`0x006a2aed`), which
returns 0, and the record is freed, when the target object no longer exists. (high)

**Reading the row.** `FUN_006a1880` keeps the row (+0xc4), the target (+0x40), a source object
(+0x44) and a third object (+0x48), and reads `Type_FD`, the three node-model columns, and
**only when no root model was found** the three ProgFX columns (`0x006a2133`-`0x006a2227`, the
strings at `0x007554f0`, `0x007554e0`, `0x007554cc`). The models: `Imp_HeadCon_Node`,
`Imp_Impact_Node` and one of `Imp_Root_H_Node`, `Imp_Root_L_Node`, `Imp_Root_M_Node` by the
target's size category (appearance.2da `SIZECATEGORY`, read for a creature; any other object
counts as 3): 5 or more tries H, then 4 or more L, then 1 or more M, each only while no root
model was found, so an empty H cell falls through to L and M; 0 or less gets none
(`Imp_Root_S_Node` is never read). On a low quality setting (bit 7 of the first client-options
byte clear; med) a non-empty `LowQuality` cell replaces each model; with the violence option
(options +0x72) below 2 a `LowViolence` cell replaces the head model directly but, for the impact
and root models, names another row whose `Imp_Impact_Node` / `Imp_Root_*_Node` is taken (no stock
row fills either column). The models are loaded as `fxhead` (+0x7c), `fximpact` (+0x78) and
`fxground` (+0x74), and hung (`FUN_006a5a40`, again by `FUN_006a5000`) on the target's nodes:
for a placeable `<name>_head_hit`, `<name>_impact`, `<name>_ground` (name at +0x144), for a door
`<name>hhit`, `<name>impc`, `<name>grnd` (+0x130), for any other object, creatures included,
`talkdummy`, `impact` and `root` (creature models have those nodes); a row with `OrientationOff`
set hangs them unrotated. Two node names are kept for the coded effects, chosen by two selector
bytes from the caller: the source's (+0x24: for a creature or other plain object 0
`handconjure`, 1 `impact`, 2 `headconjure`, 3 `lhand`, 4 `rhand`, else `root`; placeables and
doors use their suffixed forms) and the target's (+0x2c: 0 or 1 `impact`, else `root`), each
replaced by `root` when the object's model has no such node. The codes go into the record as
16-bit values: impact at +0xa0, duration at +0xa2, cessation at +0xa4, 0xffff for a column that
is `****`. The duration and cessation codes are kept only when the caller's second argument is 0
(the effect is applied as a lasting one; +0xc8 records it); the impact code always. (high; rows
that have a root model and a code do not exist, so the condition cannot be told from "no model
at all" in the data)

**Starting.** `FUN_006a5fc0` (called right after the record is queued) plays `impact` on each of
the three models (a model without one loops `duration` for a lasting effect, else lasts 1000 ms)
and picks the state (+0xc6): 1 if there is an impact code, else 2 if a duration code, else 3 for
a cessation code. It runs the code's *prepare* (`FUN_006a5890`: the models of 300-399, 600-699,
1200-1299 and 1700-1799, a 0.5 at +0xd0 for 400, 402 and 403), sets the kind byte, and gives
state 1 the length of the `impact` animation of its prepared model (`FUN_006a0620`; code 1201
only) or **1000 ms**, state 3 1000 ms, state 2 no time. Its call of the *start* (`FUN_006a54d0`)
does nothing on a new record (the attached flag +0xa8 is still 0): the code starts in
`FUN_006a5a40`, called next, which hangs the models and sets +0xa8. `FUN_006a5fc0` also starts
the row's camera shake (`ShakeType` 1 or 2, `ShakeDelay`, `ShakeDuration`) while the record's
priority byte is 0. The object's per-frame update (`FUN_0063f490`, through `FUN_006a6a50`)
counts +0x9c down: at 0 a state-1 effect stops its impact code and, if lasting, starts its
duration code (state 2), else ends; a state-3 effect stops and ends. A state-2 effect has no end
of its own: the object's remove method (`FUN_0063f400`, slot 46, takes the first record of that
row not already ending) ends it when the server's effect leaves, through the record's end
`FUN_006a6590` (the list walker `FUN_0063daa0`, slot 50, ends every effect with it), which plays
`cessation` on the models, stops the duration code through the *stop* dispatcher `FUN_006a56f0`
and, if there is a cessation code, starts it for 1000 ms (state 3). Sounds: `SoundImpact` is
played once through the voice-stream player (when the target exists) and `SoundDuration` as a
sound source tied to the record (+0xec, moved with the target every frame), stopped and freed by
the end. The end also asks for `SoundCessation`, but the 2DA spells that column
`soundcessastion`, and the column lookup (`C2DA::GetColumnIndex`, exact apart from case) does not
find it, so no cessation sound plays (static reading; needs a runtime check). (high for the
structure, med for the sounds)

**The code is a bucket of a hundred.** `FUN_006a54d0` (start) and `FUN_006a56f0` (stop) are
ladders of range tests on the code's hundred, both skipped until the record is attached (+0xa8)
and guarded by a started flag (+0xf4); the stop ladder has no entry for several buckets:

| Codes | Start / stop | What | In the 2DA | Conf. |
|---|---|---|---|---|
| 0-199 | `0x006a3660` / `0x006a47b0` (100-199 only) | an environment map `vdu_envmap%03u` (the code minus 100) on the target's model | none | low |
| 200-299 | `0x006a3740` / `0x006a47f0` | a colour tint on the target's model: 200 red, 201 green, 202 blue, 203 magenta, 204 yellow, 205 white; priority 0x14 | none | med |
| 300-399 | prepare `0x006a4fa0`, start `0x006a38e0` / stop `0x006a4830` | a light: the model `fx_light_clr` on the target plays the animation the code names: 300-327 `White`, `Blue`, `Yello`, `Red`, `Orng`, `Purp`, `Gren`, each `_5m`, `_10m`, `_15m`, `_20m` (priority 0x14); 328 `Dark_Vision`, 329 `Blind_Vision`, 330 `Low_Light_Vision`, 331 `Ultra_Vision`, 332 `darkness` (priorities 0x31-0x35); 333 the player's own `Blind_Vision`; 350-382 the same at speed -0.31 | none | med |
| 400-499 | `0x006a3e80` / `0x006a4920` | 400, 402, 403: a call on the target's appearance (`0x0063cb50`, with the 0.5 the prepare left), and a tint for 402 (0.25, 0.25, 1) and 403 (0.5, 0, 1); 401 and 404 only clear +0xc7; priority 1. The stop removes the tint and calls `0x0063cb50` | none | low |
| 500-599 | `0x006a04c0` / `0x006a47f0` | 500 and 501 store two colours in the record; the stop clears a tint | none | low |
| 600-699 | prepare `0x006a0680`, start `0x006a3fd0` / stop `0x006a05b0` | a beam model (loaded as `fxbeam`), hung on the source's node (+0x24), its far end on the target's (+0x2c), playing `cast01`: 608 `v_lightns_dur`, 609 `v_lightnx_dur`, 610 `v_drddisab_dur`, 611 `v_drdkill_dur`, 612 `v_deathfld_dur`, 613 `v_drain_dur`, 614 `v_flame_dur`, 615 `v_stunray_dur`, 616 `v_coldray_dur`, 617 `v_ionray01_dur`, 618 `v_ionray02_dur`, 619 `v_fstorm_dur`, 620 `v_drdstun_dur`, 621 `v_fshock_dur` | 2026-2029, 2037, 2038, 2049-2053, 2061, 2065, 2066 (the beam, lightning, ray and drain durations; 608-621) | high |
| 700-799 | `0x006a4000` / none | with the violence option above 1, a call on the target's model (gore) | none | low |
| 800-899 | `0x006a4060` / none | with the violence option above 1, reads the creature's `bloodcolr` and its `impact` node; nothing drawn was found | none | low |
| 900-999 | `0x006a4240` / none | a projectile from the source's `handconjure` node to the target: 900 `vpr_magmisl`, 901 `vpr_arofire`, 902 `vpr_aroacid` | none | med |
| 1000-1099 | `0x006a34b0` / `0x006a4720` | creature texture swaps (`vdu_tex_stone`, `_grstone`, `_bark`, `_shade`), also on the head-slot item | none | med |
| 1100-1199 | `0x006a2af0` / none | 1100: a `vpr_kngpow` projectile from 4 m in front of the source to the target, with the sound `c_cow_atk1` (voice-stream player) | none | med |
| 1200-1299 | prepare `0x006a0800`, start `0x006a2e10` / none | 1200 and 1201 `v_fizzle_imp` ("fxfail"), 1202 `v_fresist_imp` ("fxresist"), hung on the target's `headconjure` (1200), `handconjure` (1201) or `impact` (1202, turned to face the source), playing `impact`: a power failing / being resisted | 4036-4038 | high |
| 1300-1399 | `0x006a30e0` / none | a projectile carrying the model of the right-hand weapon (equipment slot 0x10) of the third object (+0x48, the thrower), from its `rhand` when it is the source, else from the source's `impact` node, to the target (to its `rhand` when the target is the thrower): the thrown lightsaber (`VFX_IMP_MIRV`) | 6000, 6001 | low |
| **1400-1499** | **start and stop `0x006a1220` / `0x006a1470`** | **a texture layer over the creature**: 1401-1412 `fx_tex_01`..`fx_tex_12`, **1413-1425 `fx_tex_14`..`fx_tex_26`** (there is no 13 in the switch), 1426 `fx_tex_stealth`; priority 0x14 | impact 1401-1403, 1405-1407, 1409-1412, 1423; duration 1401, 1404, **1413-1421 (the shields)**, 1422, 1424, 1426 | high |
| 1500-1599 | `0x006a4580` / `0x006a49a0` | 1500, on the player only: keeps the camera's value (slot 18) and calls it with (135.0, 0.75, 0); the record lasts 4750 ms (+0x9c = 0x128e); the stop restores the value: knight speed's camera push | 1020, 1022 | med |
| 1600-1699 | `0x006a14e0` / `0x006a1570` | 1601 and 1602 count their records in a global (`0x00833bcc`, any creature); the first, when it is on the player, turns the speed blur on with ratio 0.75 (`FUN_0044f130`, `FUN_0044f0a0`; see minigames-swoop-turret.md); every stop turns it off (`FUN_0044f0b0`) | 2004 | med |
| 1700-1799 | prepare `0x006a0860`, start `0x006a4680` / none | 1700 `v_medal_dur` on `medalhook`, 1701 `v_revmask1_dur` on `revmask1hook`, 1702 `v_revmask2_dur` on `revmask2hook`: a model on a hook the row cannot name | 7000-7002 | high |
| 1800-1899 | `0x006a15d0` / `0x006a1610` | 1800 sets model +0x17c (`0x00449af0`; `0x00449b00` clears it), with which the mesh draw (`0x0049b680`) writes the model into the stencil with colour writes off: the model vanishes, its shape marked for another pass | 8000, 8001 | low |
| 1900 and up | none | the ladder ends at 1899: 2000 and 2001 do nothing | 2000, 2001 | high |

(The `progfx_impact` codes the table uses: 1201 and 1202, 1300 (6000, 6001), 1401-1412 and 1423
(8001) as above, 1500 (1020, 1022); row 1003 has 1401 as both its impact and its duration code;
there are no cessation codes.)

**1400-1499, the texture layer** (what the shields are). `FUN_006a1220` chooses a texture name
from the code, puts `0x14` in the record's priority byte (+0xd8), and calls `FUN_0063d440` twice
with it: on the target's appearance and, when the target is a creature (its slot 11), on the
item in its head slot (equipment slot 1, creature +0x220: a mask or helmet; med). That is
`appearance->vtable[10]` (`0x0069dd90`, lower-cases the name) and then the **model's** slot 84
(`0x00448130`) with two arguments, the texture name and a float, **0.02** (`push 0x3ca3d70a` at
`0x006a1371`). What `0x00448130` does, for every mesh part with a material: requests the
texture, reads its TXI for `blending additive` (SRC_ALPHA, ONE) or `punchthrough`, puts the
texture in the material's second texture slot (+0xc, the lightmap's) with the blend of a **second
layer** (arrays at +0x28 and +0x34, entry 1), and stores the 0.02 at **model +0x11c**. Slot 85
(`0x004485c0`) undoes it, which is the stop (`0x006a1470` calls it through `FUN_0063d460`, on the
same two objects). (high for the effect, med for "the model's slot 84" naming)

The draw: after the normal draw of a mesh (`0x00477830`, the switch over the draw paths), if the
card can run vertex programs and the owning model's +0x11c is not 0, the mesh is **drawn a second
time** with the vertex program `DAT_00828014` ("the bumped-out program", ARB text at
`0x00797488`, the NV one at `0x007a0b10`), the second texture bound, the second layer's blend
applied (`0x0047af70`, entry 1, when the material has more than one layer: additive, depth writes
off), all index lists of the mesh. The program moves each vertex along its normal by
`program.env[12].x` (the 0.02 from +0x11c, set with `GL_SetProgramEnvParam(12, x, 0, 0, 1)`),
passes uv0 and uv1 through, outputs the fog distance and colour **(1, 1, 1, 1)**: no lighting. So
an energy shield is a second, unlit, 2 cm fatter copy of the creature's meshes (its model and a
head-slot item's, not the weapons), textured with an additive flipbook.
(high; the program's text and the draw call are read; which UV set the layer-1 texture is
sampled with is the program's `texcoord[0]` and the bind of unit 0: uv0, med)

The textures are TPC flipbooks, 32 by 512 (16 frames of 32 by 32; `fx_tex_22` is 128 by 512, 4 of
128 by 128), TXI `proceduretype cycle`, `numx 1`, `numy 16` (4), `fps 16` (`fx_tex_19` and
`fx_tex_22`: 8), `blending additive`. All are dim, deliberately (the brightest pixel of
`fx_tex_14` is 44 of 255): a shimmer over the body, not a glow. By shield row:

| Rows | Code | Texture | Colour (mean RGB of its frames) |
|---|---|---|---|
| 2040 | 1413 | `fx_tex_14` | blue (0, 0, 21) |
| 2044 | 1414 | `fx_tex_15` | green (4, 16, 8) |
| 2045 | 1415 | `fx_tex_16` | red (13, 0, 0) |
| 2041 | 1416 | `fx_tex_17` | blue (0, 2, 40) |
| 2047 | 1417 | `fx_tex_18` | purple (14, 0, 26) |
| 2048 | 1418 | `fx_tex_19` | purple (31, 0, 36), 8 fps |
| 2042 | 1419 | `fx_tex_20` | blue (0, 2, 41) |
| 2043 | 1420 | `fx_tex_21` | blue (1, 0, 27) |
| 2046 | 1421 | `fx_tex_22` | orange (39, 15, 0), 8 fps, a circuit-like pattern |

Several texture effects on one creature do not add up. Each record has a *kind* byte (+0xd9,
`FUN_006a0930` from the code's hundred; its last tests compare with 0x72 and 0x74, not with
1400 and 1700, so every code from 1300 to 1599 is kind 0xf and every code from 1600 up is
kind 0) and the object's list manager `FUN_0063db90(kind)` (slot 55) runs after every effect
is added and, from the per-frame update `FUN_0063f490`, for every record every frame: of the
records of that kind that have a nonzero priority byte and are not ending it keeps only the
lowest one running (the newest on a tie) and turns the others off (`FUN_006a0c70`: unhooks their
models, without stopping their code). So a 1 s impact flash (1401-1412, priority 0x14 as the
shield's) replaces the shield's layer texture while it runs; its stop removes the layer, and the
shield, turned back on (`FUN_006a5000`, which re-applies the code), puts its own back. Sound: the
row's `soundimpact` once, `soundduration` (`v_dur_shldblue` / `v_dur_shldred`) while the effect
lasts; the off sound in the misspelled `soundcessastion` column is not played (above). (med)

Our version: `lib/vfx/aura.ctx` and docs/design/vfx.md, "Texture auras".

### Console overlay

A Quake-style console is built into the renderer library. `Console_ExecFile` 0x0044c980 runs
config.txt and startup.txt at start-up, and `Console_Execute` 0x0044c1f0 runs one command line.
`Console_Print` 0x0044d490 queues a 0x434-byte fading line, `Console_Render` 0x0044d6a0 draws it,
and `Console_DrawText` 0x0044ce50 draws at a character cell. The console font is either glBitmap
display lists (0x0044cb10 build, 0x0044cb90 draw, 0x00432040 call lists, 0x0044cc60 free) or a
textured font (0x0044cca0). While the console is open (0x007a3a40) WinMain prints the ">" prompt
and the input buffer (0x007a3a4c) through `Console_Print` every frame, runs the line through
`Console_Execute` on Enter and prints the result, and draws the cursor with `Console_DrawText`.
`Render_TakeScreenshot` 0x004211a0 writes snapN.tga with glReadPixels.

### OpenGL importers by role

95 OPENGL32 imports, called from 212 distinct functions. Caller counts per group overlap.

| role | imports | distinct callers | main users |
|---|---|---|---|
| WGL context | 7 (wglCreateContext, wglMakeCurrent, wglShareLists, wglDeleteContext, wglGetProcAddress, wglGetCurrentContext/DC) | 15 | display slots 2/4/8, pbuffer setup 0x00425af0/0x00426cc0/0x00427c90, effect passes |
| Raster state | 13 (glEnable/Disable, BlendFunc, DepthFunc, AlphaFunc, Stencil*, FrontFace, PolygonMode, Push/PopAttrib, LineWidth, PointSize) | 127 | everywhere: scene passes, part render variants, GUI |
| Textures | 13 (Bind, Gen/Delete/IsTexture, TexImage1D/2D, TexSubImage2D, CopyTex(Sub)Image2D, TexParameteri, TexEnvi, TexGeni, PixelStorei) | 53 | uploads 0x00423f90-0x004260a0, shader hooks, render targets |
| Immediate mode | 13 (Begin/End, Vertex*, Color*, Normal*, TexCoord2f, ColorMaterial) | 54 | GUI quads, debug lines, effect passes, shadow quad |
| Matrices / viewport | 10 (MatrixMode, LoadIdentity, Push/PopMatrix, Ortho, Viewport, Translate/Rotate/Scale, MultMatrixf) | 51 | camera, 2D pass, effects |
| Frame / buffers | 10 (Clear, ClearColor, ClearStencil, Flush, Finish, ReadPixels, DrawBuffer, Color/Depth/StencilMask) | 48 | main loop, scene passes, pbuffer passes |
| Vertex arrays / draw | 10 (Vertex/Normal/Color/TexCoordPointer, En/DisableClientState, DrawArrays, DrawElements, Push/PopClientAttrib) | 47 | pointer helpers 0x00425900-0x00425a40, DrawElements 0x00425ab0/0x00426660 |
| Queries | 5 (GetIntegerv, GetFloatv, GetString, GetError, IsEnabled) | 27 | caps, viewport save |
| Lighting / fog | 6 (Lightfv, LightModelfv, Materialfv, Fogf/fv/i) | 13 | scene slots 46/61/73, materials |
| Display lists / bitmap text | 8 (New/EndList, Gen/DeleteLists, CallLists, ListBase, Bitmap, RasterPos2f) | 4 | console font only |

GLU32 provides gluPerspective (camera), gluBuild2DMipmaps (4 texture paths) and gluErrorString
(`GL_CheckError` 0x0044eee0, and 0x004794e0). GDI32 provides ChoosePixelFormat, SetPixelFormat and
DescribePixelFormat (0x0042e040, 0x0044dab0, 0x0044e3b0), SwapBuffers (WinMain, 0x00401c10) and
SetDeviceGammaRamp (display slot 9).

### Open points

- What the real classes were called: there is no RTTI and there are no log strings in this
  library. The `CAur*` names are ours.
- Scene vtable slots other than 6, 46, 47, 70 and 73 are unnamed. The order of the opaque and
  transparent passes inside 0x004514f0 is inferred from the state changes, not proven.
- Node type 0x401: `CAurPart::CreateFromMdlNode` (0x00448a70) tail-jumps to 0x0063e7c0, a
  5-byte stub that returns 0 (shared by unrelated callers, folded by the linker), so such a node
  makes no part; what the type was meant for is unknown.
- The resource-backed image callbacks (installed by 0x0070d9c0) are identified by the resource
  type their reader asks for, not by their callers: 0x0070c790 TGA, 0x0070c6e0 PLT (type 6, med),
  and the loaders 0x0070d510 TPC, 0x0070d380 DDS, 0x0070d6b0 4PC, each of which loads only when
  its type is found in a table ranked at least as high as every later type's (TPC, DDS, 4PC,
  TGA; resman.md); 0x0070cc60, 0x0070cd10, 0x0070cdd0 and 0x0070ce80 read a TGA, TPC, DDS and 4PC
  through the same helpers and return its header fields (med). Which texture-library call uses
  which slot is not traced.

## GUI

The GUI is a retained tree of panels and controls owned by one manager. Panels are
filled from `.gui` resources (GFF, restype 0x7ff, signature `GUI `); the code
creates each control object itself and then binds it to a GFF struct by its `TAG`.
Every class name below is ours unless a confidence says otherwise; the binary has
no RTTI for these classes. Names follow the Aurora `CSWGui*` style.

### Ownership and per-frame flow

| What | Where | Confidence |
|---|---|---|
| `g_pGuiManager` (CSWGuiManager*) | global 0x007a39f4, set by the manager's constructor, cleared by its destructor | high |
| owner of the manager | `CClientExoAppInternal` +0x274 (created in the client's Initialize, 0x005f8550, size 0xa8; then `SetResolution`, the cursor model when the input layer wants one, `LoadGuiSounds`) | high |
| `CClientExoApp::GetGuiManager` | 0x005eda40 (returns internal+0x274) | high |
| in-game panel owner (`CGuiInGame`, our name) | `CClientExoAppInternal` +0x40, 0xc24 bytes, ctor 0x0062fed0, created right after the manager | high |
| main menu panel | created by 0x005fca30 via `CSWGuiMainMenu` ctor 0x0067c4c0 | high |

Each client frame (client main loop 0x00602eb0) runs, among its other steps and in
this order (gameloop.md 1.2, steps 8 and 23):

1. `CClientExoAppInternal::ProcessInput` 0x006227e0: drains mapped input events
   from `CExoInput` (one 16-byte record per event: value at +0, key-map entry
   pointer at +0xc; the action code sits in the key-map entry at +0x10). An event
   whose code is outside 0x27..0x40 goes to `HandleInputAction` 0x00621210 unless it
   is one of the GUI-only codes (0xb4..0xbb, 0xce, 0xdf, 0xf3, 0xf4, 0xfe..0x106)
   and the in-game GUI flag (+0x34) is clear; everything else goes to
   `CSWGuiManager::HandleInputEvent` 0x0040c8e0, but only while the in-game GUI
   flag is set or the input class (client +0x9c) is 2 or 3. While a GUI has input,
   only the first press-type event of a frame (1, 2, 0xa, 0xb, 0x27..0x2e, 0x35,
   0x36) is kept. After each event the cursor position (client +0x3c8/+0x3cc) goes
   to `CSWGuiManager::HandleMouseMove` 0x0040c1e0, unless mouse-look is active
   outside class 2, or the class is 4 (app.md, ProcessInput).
2. `CSWGuiManager::Update(dt)` 0x0040ce70 on the world delta (0 while paused):
   the Update slot (14) of every active (flag bit2) panel not on the modal stack,
   then of every active modal panel, then panels flagged for removal are reaped
   (unless flag bit8 is set).
3. `CSWGuiManager::Render(dt)` 0x0040cc50 on the interface clock (+0x2c delta,
   which no pause stops), after the 3D scene: the 2D pass (see below).

Mouse buttons arrive as mapped actions handled by `HandleInputAction`: action 0x43
is the left button (`OnLeftMouseDown` 0x0061f880 with value nonzero, value -1
meaning a double-click; `OnLeftMouseUp` 0x00620530 with value 0); these reach the
GUI only when mouse-look is off or the input class is 2/3. Action 0x44 is the
right button (0x0061f940 / 0x0061f960, which also set / clear the look-about flag
0x008338f0 before calling the manager's right-button handlers), action 0x46 the
wheel (`CSWGuiManager::HandleMouseWheel` 0x0040c650). Typed characters come from
the window-message path (0x00402240) into `CSWGuiManager::HandleCharacter`
0x0040b2a0, which forwards them to the edit box that holds keyboard focus (while
a modal panel is up, only if that edit box is the top modal panel's active
control). All med.

### CSWGuiManager (no vtable)

Constructor 0x0040bad0, destructor 0x0040aaa0. Field map (med unless noted):

| Offset | Meaning |
|---|---|
| +0x00/+0x04 | last cursor x, y |
| +0x08 | control under the cursor (hover) |
| +0x0c / +0x10 | mouse-capture button (1 left, 4 right) / capturing control |
| +0x18 | edit box with keyboard focus |
| +0x1c | flags: bit0 the current left press is a double-click (set from the button event's value -1, cleared on release), bit2 cursor model in its "center" pose, bit3 tooltip showing |
| +0x20 | software-cursor scene object (`CSWGui3DScene`, drawn last) |
| +0x24 | cursor model inside that scene, used by `SetMouseCursor` |
| +0x28 | cursor texture resref |
| +0x38 | current cursor id (index into the name table at 0x0078d240; a pressed odd id uses id+1), initially 1 |
| +0x3c | tooltip panel (`CSWGuiToolTip`, ctor 0x006277c0, 0x1a4 bytes) |
| +0x40 | control whose tooltip is due |
| +0x44/+0x48 | tooltip delay timer (-1 = stopped) / threshold (client options +0xc) |
| +0x54 | dragged object drawn on top; the only setter found is the pazaak card control (0x0067d060, vtable 0x007531c0, used by the pazaak panels) |
| +0x58/+0x5c | saved cursor position (-1 when none; `RestoreMousePosition` 0x0040c7d0) |
| +0x64, +0x72 | time (GetTickCount ms) and code of the last single-step direction event (0x2f..0x32), see the event table |
| +0x68 | last event code passed to `HandleInputEvent` |
| +0x6c/+0x6e | screen width/height (shorts) (high) |
| +0x70 | number of panels with flag bit3; while nonzero `Render` first draws the backdrop (0x0040ae80) |
| +0x71 | number of panels without flag bit4; read by the client main loop when it takes a screenshot |
| +0x74 | backdrop texture name: resolution name plus a suffix from the table at 0x007a3d50 ("back", "store", "pazaak", "map", "comp", filled by 0x0073ad80); initially "800x600back", then the tag (slot 25) of the topmost flag-bit3 panel |
| +0x7c | backdrop label, built lazily by 0x0040ae80 and dropped on a resolution change |
| +0x88 | panel list (CExoArrayList) (high) |
| +0x94 | modal panel stack (CExoArrayList) (high) |
| +0xa0/+0xa4 | GUI sound array / count (byte), from guisounds.2da (high) |

Key methods (full list in the proposals): `AddPanel(panel, flags, bPlaySound)`
0x0040bc70 (134 callers: flags 1 also pushes it as modal, 2 sets panel bit3, 4
sets panel bit4; plays the panel's sound byte +0x60; re-adding a panel only
cancels a pending removal), `RemovePanel` 0x0040c830, `PushModalPanel` 0x0040bd90,
`PopModalPanel` 0x0040be00, `BringPanelToFront` 0x0040bd20, `UpdateTopPanel`
0x0040acc0, `PlayGuiSound` 0x0040a140, `LoadGuiSounds` 0x00409f00,
`SetResolution` 0x0040be70, `SetMouseCursor` 0x0040a270, `GetPanelAndControlAt`
0x0040abe0 (only the top modal panel while one is up), mouse capture 0x0040a1c0 /
0x0040a200.

Render (0x0040cc50) draws, in order: the backdrop while +0x70 is nonzero, every
non-modal panel that is active (flag 4) and not on the modal stack, then the modal
stack bottom to top, then the dragged object, then the tooltip panel while it is
showing (+0x1c bit3); the tooltip timer advances here and, once past the
threshold, records the hovered control at +0x40 if it has a tooltip (both skipped
while 0x005ee230 holds); then the software cursor. A panel draws only with flag
bit7 set and its extent inside the screen; its draw (0x0040b760) is bracketed by
the renderer's 2D begin / viewport push (extent, colour +0x50, alpha +0x4c) /
viewport pop / 2D end (0x004591b0 / 0x004592f0 / 0x00459580 / 0x004592b0) and
draws the border, then each visible control (control flag bit1). Panels whose
flags (bits 9..10) ask for removal (1 or 3) or deletion (2) are reaped after
drawing. While 0x007a3d4c is set it also draws an overlay built by 0x0040bec0;
nothing in the code sets that global (its only reference is this read), so the
overlay never shows.

### Input event codes (the `nEvent` passed to HandleInputEvent)

Derived from the dispatch code; meanings are med unless noted.

| Code | Meaning |
|---|---|
| 0 / 1 | gain / lose hilight (focus) (high) |
| 0x27 | activate: click (sent by a control on left-button release) or Enter (an edit box sends it to its panel); panels attach their button callbacks to it (high) |
| 0x28 | cancel: Escape in an edit box, and the remapped 0xb4 / 0xdf |
| 0x29..0x2b | further button codes; the panel slots 20..24 send 0x27..0x2b to the panel itself |
| 0x2d | second activate code, registered next to 0x27 by most panels (63 handlers, the main menu buttons among them) |
| 0x2f..0x32 | single-step left, right, up, down (an edit box makes them from characters 0x1c..0x1f); the manager drops one that arrives on the other axis within 150 ms of the last (+0x72/+0x64) |
| 0x33/0x34, 0x37/0x38 | axes: value +1/-1 turns 0x33 into 0x3e/0x3d, 0x34 into 0x40/0x3f, 0x37 into 0x3a/0x39, 0x38 into 0x3c/0x3b |
| 0x39..0x3c | second-stick directions; panels such as the inventory and the message box resend 0x39/0x3a to their list box as 0x31/0x32 (scroll) |
| 0x3d..0x40 | up, down, left, right: MOVETO navigation (with 0x31, 0x32, 0x2f, 0x30), list-box selection, slider steps |
| 0x44 | right click (fired by the control's OnRightMouseUp) |
| 500 / 501 | wheel forward / back, one per 120 units (500 scrolls a list box up and raises a slider) |
| 0x1f9 | double-click: sent to the control before 0x27 when the release ends a double-click, and to every panel on the press in input class 3 |
| 0xb4..0xbb | GUI-only codes remapped: 0xb5 and 0xbb to 0x27, 0xb4 to 0x28, 0xb6..0xb9 to 0x3d..0x40; 0xba passes unchanged |

With no modal panel the manager sends the event to every panel in the list;
otherwise only to the top of the modal stack. It then reaps panels flagged for
removal and drops the `RIMS:MAINMENU` / `RIMS:CHARGEN` images when the resource
manager asks for it. A panel forwards the event to its active control
(0x00409e60). A control first handles 0/1 itself, then looks up its handler table
(+0x38, count +0x3c, entries {owner, callback, event}), stores the event and value
at +0x48/+0x4c and calls the callback on the owner with the control as argument;
the entry is set by `CSWGuiControl::SetEventHandler` 0x0041ab20 (82 callers; a null
callback removes it). This is how every panel wires its buttons. Navigation runs in
`CSWGuiSelectable::HandleInputEvent` 0x0041a9d0: it follows the MOVETO link for
the direction, skipping controls without flag bit3, and makes the result the
panel's active control (slot 2).

### Panels

`CSWGuiPanel` vtable 0x0073e010, ctor 0x0040b570 (takes the manager), dtor
0x0040cf70. Layout: +0x04..+0x10 extent, +0x18 manager, +0x1c active control,
+0x20/+0x24 control array, +0x2c open `.gui` GFF during load, +0x30 its CONTROLS
list, +0x44 flags, +0x48 resolution-suffix index (into the backdrop suffix table),
+0x4c alpha, +0x50 colour (3 floats), +0x5c border, +0x60 sound played when added
(0xff none). The constructor sets bits 2 and 7. Flags: bit0 placed in screen
pixels (set by `CenterOnScreen` 0x0040a600; while clear, hit-testing shifts the
cursor by the 640x480 centring offset), bit1 GFF loaded, bit2 active, bit3
full-screen (`AddPanel` flag 2): `GetScreenExtent` 0x0040aa00 centres it on the
screen, it turns on the backdrop, and `UpdateTopPanel` hides every panel below the
topmost one, bit4 (`AddPanel` flag 4, only counted in manager +0x71), bit5/bit6
shift x / y by the 640x480 centring offset, bit7 visible (`UpdateTopPanel` sets it
on active panels from the top of the modal stack down to and including the first bit3 panel, and
clears it below), bit8 defers reaping in `Update`, bits 9..10 removal request. High
for the structure, med for individual flag meanings.

| Slot | Function | Role |
|---|---|---|
| 0 | 0x0040d010 | scalar deleting destructor |
| 1 | 0x0040a5a0 | SetExtent (also resizes the border) |
| 2 | 0x0040a630 | SetActiveControl (sends 1 to the old control, 0 to the new one) |
| 10 | shared `return this` stub 0x00641db0 | "as panel" query used by controls to find their panel |
| 13 | 0x0040b760 | Render |
| 14 | stub | Update |
| 15 | 0x00409e60 | HandleInputEvent |
| 16 | 0x0040b690 | HitTest(x, y) |
| 17 | 0x0040b630 | GetActiveControl |
| 18 | 0x0040b870 | OnPanelAdded |
| 19 | 0x0040c170 | OnPanelRemoved |
| 20..24 | 0x0040b640..0x0040b680 | send events 0x27..0x2b to itself |
| 25 | 0x0040a900 | resolution tag |
| 26 | 0x0040a9c0 | OnResize |

All panels and controls share the 13-slot base vtable 0x0073df20 (our
`CSWGuiObject`; slot 1 `SetExtent` 0x00409e90).

#### Loading a .gui

1. The derived constructor calls the base ctor, constructs its member controls
   in place (each a full object inside the panel), then calls
   `CSWGuiPanel::LoadGui` 0x0040a680 with the resref (e.g. "mainmenu"). Unless
   the panel is already loaded (bit1), that opens the GFF and reads the root
   EXTENT (LEFT, TOP, WIDTH, HEIGHT), COLOR (default -1,-1,-1), the BORDER struct
   (or, without one, BACKGROUND as the border's fill), ALPHA (default 1.0) and
   keeps the CONTROLS list; the root CONTROLTYPE, TAG and Obj_* fields are not read.
2. For each member it calls `CSWGuiPanel::InitControl` 0x0040b930 with the tag
   ("BTN_NEWGAME"...) and an add-to-panel flag. That scans CONTROLS for the
   matching TAG (0x00418840) and calls the control's LoadFromGFF slot (vtable
   +0x48). The base loader 0x0041b8e0 reads EXTENT (and applies it through slot
   1), ID (default -1) and Obj_ParentID; a parent id other than -1 makes the
   control a child of the panel's control with that id. Derived loaders add their
   parts. With the flag set and an ID of 0 or more, the control is stored in the
   panel array at index ID (the array is padded with nulls).
3. `CSWGuiPanel::FinishLoading` 0x0040b8f0 releases the GFF, clears bit1 and
   resolves the MOVETO navigation links (0x0040a890: each of the four ids becomes
   the control at that index, or none).
4. The ctor registers event callbacks with `SetEventHandler`, and the panel is
   shown with `CSWGuiManager::AddPanel`.

Only list boxes create controls from the GFF: `CSWGuiListBox::LoadProtoItem`
0x0041d3e0 reads PROTOITEM and switches on its CONTROLTYPE to build the row
template. That switch is the authoritative type map (high):

| CONTROLTYPE | Class (our name) | Ctor | Size | Vtable | Loader | GFF fields |
|---|---|---|---|---|---|---|
| 4 | CSWGuiLabel | 0x0041acd0 | 0x140 | 0x0073e5b8 | 0x0041b960 | BORDER, TEXT |
| 5 | CSWGuiProtoItem | 0x0041b5c0 | 0x1b4 | 0x0073e8e8 | 0x0041ba20 | + HILIGHT |
| 6 | CSWGuiButton | 0x0041c0f0 | 0x1c4 | 0x0073e658 | 0x0041c930 | BORDER, HILIGHT, TEXT, MOVETO |
| 7 | CSWGuiCheckBox | 0x0041ca30 | 0x2b4 | 0x0073eb88 | 0x0041cb40 | + SELECTED, HILIGHTSELECTED, ISSELECTED |
| 8 | CSWGuiSlider | 0x0041baa0 | 0x1b8 | 0x0073e9d0 | 0x0041cc30 | BORDER, HILIGHT, THUMB, CURVALUE, MAXVALUE |
| 9 | CSWGuiScrollBar | 0x0041afe0 | - | 0x0073e6f8 | 0x0041bcd0 | BORDER, DRAWMODE, VISIBLEVALUE, THUMB, CURVALUE, MAXVALUE |
| 10 | CSWGuiProgressBar | 0x0041aed0 | - | 0x0073e7a0 | 0x0041bbc0 | BORDER, PROGRESS, STARTFROMLEFT, CURVALUE, MAXVALUE |
| 11 | CSWGuiListBox | 0x0041be40 | - | 0x0073e840 | 0x0041d5b0 | BORDER, COLOR, PADDING, LOOPING, LEFTSCROLLBAR, SCROLLBAR, PROTOITEM |
| - | CSWGuiEditBox | 0x0041c6b0 | - | 0x0073eac8 | 0x0041c7d0 | BORDER, TEXT (save name, character name) |

Types 4..8 are confirmed by the switch; 9..11 by the GFF fields their loaders
read (high). Buttons, sliders, list boxes and edit boxes derive from an
intermediate class (vtable 0x0073e520, ctor 0x0041b8b0, our `CSWGuiSelectable`)
that adds MOVETO (UP, DOWN, LEFT, RIGHT ids, loader 0x0041c890); the edit box's
loader skips it and calls the base loader directly, so an edit box reads no
MOVETO. The scroll bar and progress bar derive from the control base directly. The
check box derives from the button, the proto item from the label. No loader reads
the scroll bar's DIR struct (the string is not in the binary).

#### Control vtable (38..42 slots, base 0x0073e488, ctor 0x0041aa80, dtor 0x00419a20)

The base table has 38 slots (0..37); label, button, scroll bar, progress bar, slider and edit box
have 40, list box, proto item and check box 42. Slot 0 is the scalar deleting destructor
(0x00419cc0).

| Slot | Base function | Role | Confidence |
|---|---|---|---|
| 1 | 0x00409e90 | SetExtent | high |
| 3 | 0x004189a0 / 0x0041a980 | hover on/off. Base: on restarts the tooltip timer, off drops a shown tooltip (flag bit6). Selectable classes (0x0041a980): on, if not already hilighted, sends event 0 through slot 15 and plays GUI sound 1; off sends event 1; both then run the base | high |
| 4 | stub (slider 0x00419250, list 0x0041b670) | OnMouseDrag(x, y): the manager's mouse move calls it on the capturing control | high |
| 5 | nop | capture lost (called when the manager releases or replaces the capture) | med |
| 6 / 7 | 0x0041ab90 / 0x0041abd0 | left button down / up. Down: a non-selectable control with a selectable ancestor passes it to that ancestor, otherwise captures the mouse (button 1). Up, if this control (or its selectable parent) is still under the cursor: event 0x1f9 when the manager's left-button bit is set, then 0x27 if the control is selectable (bit3); then releases the capture | high |
| 9 / 33 | 0x0041ac70 / 0x0041ac30 | right button up (fires 0x44 if still under the cursor and selectable) / down (captures with button 4, or defers to the selectable ancestor) | high |
| 14 | stub; label 0x00417750, button 0x00417ab0 | Render | high |
| 15 | 0x00418750 | HandleInputEvent | high |
| 16 | 0x004181d0 | SetHilighted (flag bit0) | high |
| 17 | 0x004187c0 | HitTest: this when visible (bit1), not bit5, and the point is inside the extent | high |
| 18 | 0x0041b8e0 | LoadFromGFF | high |
| 31 | 0x00418960 | SetFocus: makes the control the owning panel's active control (panel slot 2), with sound 1 if it was not hilighted | med |
| 32 | 0x004189d0 | IsSelectable: bit3 set and slot 19 non-zero; when the owner (+0x34) is itself a control (owner slot 11), the owner's bit3 is tested instead | med |
| 34 | 0x004176a0 | SetSelectable (flag bit3); label 0x00418d00 and button 0x00418db0 also grey the text (disabled colour) when off | high |
| 35 | nop; label 0x00418d40, button 0x00418df0 | relayout after resize (called by the panel's OnResize 0x0040a9c0); label and button re-apply the font size suffix | med |
| 36 | 0x00418a90 | tooltip: text from strref +0x24, else string +0x28, else the parent's tooltip; appends " : " and the bound key's name (`KeyNameStrRef`) when +0x30 names an input action; shows it and sets flag bit6 | med |
| 39 | edit box 0x004184f0 | HandleCharacter | high |

Control fields: +0x04 extent, +0x14 parent control (Obj_Parent), +0x18 children,
+0x24 / +0x28 tooltip strref / tooltip string, +0x30 input action whose key name the tooltip
shows, +0x34 owning panel, +0x38/+0x3c event handler table (12-byte entries) and count, +0x44
flags (bit0 hilighted, bit1 visible, bit3 selectable, bit5 skipped by hit-testing, bit6 tooltip
shown; the ctor sets bits 1 and 3), +0x48/+0x4c last event and value, +0x50 ID (-1),
+0x54 click-sound index (0; check box 3; played by the button on activate), +0x55 hover-sound
index (1; played by `CSWGuiPanel::SetActiveControl`) (med).

The edit box's HandleCharacter: backspace (8, 0x7f) deletes, Enter (10, 13) sends 0x27 and Esc
(0x1b) sends 0x28 to the owning panel, codes 0x1c..0x1f become events 0x2f, 0x31, 0x30, 0x32 on
the box, and any other character from 0x20 up except `_`, `/` and `\` is appended (high).

#### Drawables inside controls

| Class (our name) | Vtable | Ctor | Loader | Draw | Notes |
|---|---|---|---|---|---|
| CSWGuiBorder | 0x0073e338 | 0x004167f0 | 0x004153e0 | 0x004168c0 | CORNER, EDGE, FILL, FILLSTYLE, DIMENSION, INNEROFFSET, COLOR, PULSING |
| CSWGuiText | 0x0073e3a4 | 0x00417280 | 0x00416050 | 0x00416240 | FONT (default `dialogfont16x16`), COLOR (default 1,1,1), TEXT, STRREF (default -1), ALIGNMENT (default 9), PULSING; then builds the render string |
| CSWGuiImage | 0x0073e390 | 0x00415a30 | 0x00416ec0 | 0x00415c90 | IMAGE, ALIGNMENT, DRAWSTYLE, FLIPSTYLE, ROTATE, ROTATESTYLE (thumbs, arrows, map) |
| CSWGui3DScene | 0x0073e3f0 | 0x004174b0 | - | - | scene with a camera: software cursor (0x0040b060), main-menu 3D view, galaxy map, character sheet, upgrade bench, class selection, chargen and level-up main panels, portrait step |
| editable text | 0x0073e444 | 0x004173d0 | text's | text's | buffer +0x78, max length +0x70 (-1 = none), backspace 0x004162e0, append 0x004163a0 (refused at the max length); with +0x74 bit0 it displays the buffer followed by `_` |

### Fonts and text

Text settings (our `CSWGuiTextInfo`, ctor 0x00417050) hold the string, a TLK
strref, the font resref (default `dialogfont16x16`), colour and alignment.
`SetText` 0x00415e00 (136 callers) and `SetStrRef` 0x00415e50 (TLK lookup; -1 only
stores the strref) push the string into a render-side string object made by
0x0045bdf0 (0x48 bytes, vtable 0x00741878, ctor 0x0045b990): a font texture plus
the text, drawn by the renderer. A font is a texture whose TXI carries the glyph table; the TXI
font keys (numchars, fontheight, baselineheight, texturewidth, spacingR/B,
upperleftcoords, lowerrightcoords) are parsed by 0x00422210 under the TXI parser
0x00422390 (renderer side). Before a font is loaded, 0x0040b360 (called by
0x00415d60 when the font is set or a control re-lays out) appends `a` or `b` to
every font name except `fnt_console`: `a` when client option +0x80 is 1 ("Use Small
Fonts" on), `b` when it is 2 (off), and for any other value `a` below 1280 pixels
wide, else `b`. The option is read from swkotor.ini by 0x0061dbe0 (which then calls
`CSWGuiManager::OnResolutionChanged` to re-lay out) and written by 0x0061b780; see
gui.md for the font files this selects. `fnt_d16x16` is named by several panels.
Med overall; the render-string class is for the renderer notes.

### Notable panels

| Panel (our name) | .gui | Ctor | Vtable | Notes |
|---|---|---|---|---|
| CSWGuiMainMenu | mainmenu | 0x0067c4c0 (InitPanel 0x0067ace0) | 0x00752f70 | LB_MODULES, BTN_NEWGAME/LOADGAME/MOVIES/OPTIONS/EXIT/WARP, LBL_3DVIEW, LBL_MENUBG, LBL_GAMELOGO, LBL_NEWCONTENT; each button's callback is registered for both 0x27 and 0x2d: NewGame 0x0067afb0, LoadGame 0x0067b1a0, Movies 0x0067b250, Options 0x0067b2f0, Warp 0x0067c4b0, Exit 0x0067b4a0; events 0 / 1 go to hilight 0x0067b450 / 0x0067b470. When 0x0078d1e4 is set it loads `gui3D_room` with the `mainmenu` model on `camerahook`. The ctor also empties GAMEINPROGRESS:, CURRENTGAME: and REBOOTDATA: and sets sound mode 0 (high) |
| CSWGuiMainInterface (HUD) | mipc28x6, mipc210x7, mipc212x9, mipc212x10, mipc216x12 | 0x0068c100 | 0x00753f50 | file by screen size: 1024 wide mipc210x7, 1280x960 mipc212x9, 1280x1024 mipc212x10, 1600 wide mipc216x12, any other width mipc28x6; a 1280-wide mode of another height loads none (med, needs a runtime check). BTN_MSG, BTN_OPT, BTN_JOU, BTN_ABI, BTN_MAP, BTN_CHAR, BTN_INV, BTN_EQU, TB_PAUSE/SOLO/STEALTH, minimap (BTN_MINIMAP, LBL_MAP...), action queue (LBL_QUEUE%d, BTN_CLEARONE/CLEARALL), combat bars; Render 0x0068b4a0, Update 0x00686ba0 (high) |
| CSWGuiLoadScreen | loadscreen | 0x0067a710 | 0x00752dc0 | LBL_LOADING, LBL_LOGO, LBL_HINT, PB_PROGRESS; full-screen fill named after the resolution plus `load` (high) |
| CSWGuiDialog (base) | - | 0x006a85b0 | 0x007559e0 | base of the three conversation panels (its only callers are their ctors) (high) |
| conversation | dialog | 0x006a8b40 | 0x00755800 | LB_REPLIES, LBL_MESSAGE (high) |
| computer conversation | computer | 0x006a8eb0 | 0x00755888 | LB_MESSAGE, LB_REPLIES, spike/repair counters and skill labels, LBL_STATIC%d, LBL_OBSCURE (high) |
| computer camera | computercamera | 0x006a95f0 | 0x00755958 | LBL_RETURN (high) |
| message box | confirm | 0x00626df0 | 0x0074fdb0 | LB_MESSAGE, BTN_OK, BTN_CANCEL (high) |
| tooltip | tooltipWxH | 0x006277c0 | 0x00750030 | created by the manager's ctor 0x0040bad0, re-created by 0x0040a350 (from the resolution options' OK); file by resolution (tooltip16X12, tooltip12X9, tooltip12x10, tooltip10X8, tooltip8X6, else tooltip6X4); one label `tooltip` (high) |
| message log | messages | 0x00626400 | 0x0074fd18 | LB_MESSAGES, LB_DIALOG, LBL_MESSAGES, BTN_SHOW, BTN_EXIT (high) |
| top bar | top | 0x00627980 | 0x00750148 | BTN_MSG..BTN_EQU and their LBLH_ highlight labels (high) |
| fade | fade | 0x00624810 | 0x0074fc60 | LBL_MSG (high) |
| options | optionsmain, optgraphics, optsound, optmouse, ... | 0x006e3e80 ... | 0x00758838 ... | (high for optionsmain) |

Other panels found by their `.gui` names (ctor / vtable): statussummary
0x006272a0 / 0x0074ff68, journal 0x00644a40 / 0x00751960, pazaakwager
0x0067f000, pazaakgame 0x006808a0, pazaaksetup 0x00681a90, credits 0x0068f8d0,
map 0x00694d50, galaxymap 0x00695180, barkbubble 0x006a9770, optionsingame
0x006ab2f0, abilities 0x006adda0, character 0x006b0e40, inventory 0x006b34c0,
container 0x006b6dc0, equip 0x006ba980, partyselection 0x006bfa40, pause
0x006c03b0, store 0x006c1c00, upgrade 0x006c6b60, upgradeitems 0x006c7630,
upgradesel 0x006c78d0, areatransition 0x006c7d50, savename 0x006cae70,
saveload 0x006cc680, skillinfo 0x006ce7c0, classsel 0x006dc3c0, titlemovie
0x006dd910, optresolution 0x006e0710, optgraphicsadv 0x006e16e0, optsoundadv
0x006e20a0, optmouse 0x006e2600, optfeedback 0x006e2a70, optgraphics 0x006e2e70,
optsound 0x006e3550, optgameplay 0x006e69a0, optautopause 0x006e76a0, aiscripts
0x006ea000, pwrlvlup 0x006f2180. The character-generation and level-up panels pass
upper-case literals: leveluppnl 0x006ee7d0, custpnl 0x006ef730, quickpnl 0x006f0390,
qorcpnl 0x006f09f0, ftchrgen 0x006f3d60, skchrgen 0x006f51d0, abchrgen 0x006f7600,
name 0x006f9e70 (NAME_BOX_EDIT); maincg and portcust are in chargen.md section 0.
All high: the `.gui` name is the literal passed to `LoadGui`.

The in-game panels are created together by `CGuiInGame::CreatePanels`
0x00632860 (with loading-bar updates through 0x00401c10). After a resolution
change 0x0062f5f0 deletes and rebuilds only the HUD, the conversation panel and the
message box (their files depend on the resolution) and re-centres the debug panels,
the container, the skill info and the tutorial box. The HUD lives at `CGuiInGame`
+0x90, the conversation panel at +0x40, the computer panel at +0x44, the computer
camera at +0x48, the message box at +0x98, the GUI manager pointer at +0x38 (high).

### Open questions

- True class names: none are confirmed; `CSWGuiSelectable`, `CSWGuiObject`,
  `CSWGuiTextInfo`, `CSWGuiImage`, `CSWGui3DScene`, `CGuiInGame` and the dialog
  subclass names are descriptive.
- Events 0x29..0x2b and 0x2d: which inputs produce them needs a run-time check (0x28 is
  cancel: Esc in an edit box sends it). `AddPanel` flag 2 becomes panel flag 0x08 (centre the
  panel on screen, and draw the backdrop while any such panel is up); flag 4 becomes panel flag
  0x10, whose only effect found is to leave the panel out of the manager's +0x71 counter, which
  nothing reads.
