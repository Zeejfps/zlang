# Renderer and GUI of swkotor.exe

The OpenGL renderer (context, extensions, frame, models, textures) and the GUI system (manager,
panels, controls, `.gui` loading, fonts, input routing). Addresses are for the Steam
`swkotor.exe` after SteamStub removal (`kotor/re/bin/swkotor_unpacked.exe`). All class and
function names here are ours; the binary has no RTTI or log strings for these classes, so they
follow the NWN Aurora vocabulary (`CAur*` for the rendering library, `CSWGui*` for the GUI) and
are proposed in `kotor/re/proposals/app.tsv`. Confidence: **high** = read in the code and
consistent with strings/imports; **med** = role clear, name a guess; **low** = plausible only.

Start-up, the main loop, input, audio and movies are in [app.md](app.md).

## How a frame is drawn

`WinMain` clears the buffers and calls the client main loop. Inside it,
`CClientExoAppInternal::UpdateObjectsAndRender` (0x006048c0) updates the client objects and
renders the 3D world through the module's camera and scene (`CSWCModule::Render` 0x00644650 →
`CAurCamera::Render` 0x0045c540 → `CAurScene::Render` 0x004512d0 → passes 0x004514f0); later in
the same loop `CSWGuiManager::Render` (0x0040cc50) draws every active panel, tooltip and the
software cursor in 2D on top. Back in `WinMain` the console overlay (0x0044d6a0) is drawn and
`SwapBuffers` presents. During long loads `RenderLoadingFrame` (0x00401c10) draws a GUI-only frame
instead (the load screen panel, `CSWGuiLoadScreen` 0x0067a710).

## Renderer

KOTOR draws with fixed-function OpenGL 1.x plus extensions (ARB/NV vertex programs, NV register
combiners or ATI_fragment_shader, VBOs, pbuffers). The rendering library sits roughly between
0x0041d000 and 0x004ab000 and keeps the NWN "Aurora" shape: a refcounted display object,
named scenes, cameras, and "parts" built from MDL nodes. The game hooks resource loading into it
through a callback table. No class names survive in the binary, so the `CAur*` names below are
descriptive (they follow the NWN Aurora layer), and so are the `GL_*` / `Render_*` helper names.

Defaults in .data: render size 800x600, 60 Hz, 32 bpp (`g_nScreenWidth` 0x0078d1d4, `g_nScreenHeight`
0x0078d1d8, refresh 0x0078d1dc, bpp 0x0078d1e0). The window code keeps these in step with the client
area through display slot 5.

### Display object and context creation

The display is a singleton of 0xb8 bytes with vtable 0x00741518. Its abstract base vtable 0x007414f0
is all pure-virtual. `CAurGLDisplay::GetInstance` (0x0044ecd0) creates it and counts references
(`g_pAurGLDisplay` 0x007b921c, count 0x007b9218), and `ReleaseInstance` (0x0044d940) frees it.
Client init (0x005f8550) stores the pointer in the app global `g_pDisplay` 0x007a39f8. The
video-mode function 0x00403800 and the window procedure then call it only through these slots:

| slot | addr | name | what it does | conf |
|---|---|---|---|---|
| 0 | 0x0044ed40 | DeletingDestructor | destructor 0x0044ec60, then free | high |
| 1 | 0x0044d6d0 | IsFullscreen | returns the flag at +0xac | med |
| 2 | 0x0044dab0 | CreateContext | the real context setup (below) | high |
| 3 | 0x0044d6e0 | FindBestDisplayMode | clamps the requested w/h/bpp/Hz to an enumerated mode | med |
| 4 | 0x0044e3b0 | CreateContextBasic | older path: plain ChoosePixelFormat, no multisample | med |
| 5 | 0x0044e9e0 | SetViewportSize | stores the client size in the screen globals, glViewport | med |
| 6 | 0x0044d8d0 | RestoreDesktop | gamma 1.0 and the desktop display mode (on deactivate) | med |
| 7 | 0x0044d900 | ReapplyDisplayMode | puts back the stored gamma and the fullscreen DEVMODE (on activate) | med |
| 8 | 0x0044ea30 | DestroyContext | frees vertex programs and pbuffers (0x00432180), deletes the context, can restore the mode and destroy the window | med |
| 9 | 0x0044d990 | SetGamma | builds a 3x256 ramp from the brightness value and calls SetDeviceGammaRamp | high |
| 10 | 0x0044d970 | GetGLContext | returns the HGLRC at +0xb4 | med |
| 11 | 0x0044d980 | wglMakeCurrent thunk | | high |

Steps inside `CreateContext` (0x0044dab0), with arguments main HWND, render HWND, width, height, bpp,
refresh, fullscreen, colour bits and samples:
1. The first time through, `GL_ProbeMultisampleSupport` (0x0042e040) makes a hidden "Test GL
   Window" with a throwaway context. It looks up `wglGetExtensionsStringARB` and
   `wglChoosePixelFormatARB` and sets the WGL_ARB_multisample bit. ATI drivers get that bit only on
   Windows newer than 4.x.
2. Fullscreen: it looks for an exact DEVMODE match and applies it with ChangeDisplaySettings (test
   first, then fullscreen). The window gets the popup style and is sized with AdjustWindowRect.
3. Pixel format: when anti-aliasing is set (0x007a6888 > 0) and `GL_IsMultisampleFormatAvailable`
   (0x0044f140) agrees, it uses wglChoosePixelFormatARB with N samples. Otherwise it uses a classic
   PFD: double-buffered RGBA, 32-bit colour, 8 alpha, 24 depth, 8 stencil.
4. wglCreateContext / wglMakeCurrent, then `GL_LoadExtensions` (0x00436490).
5. `GL_CaptureMainContext` (0x00425c30) remembers the main HGLRC/HDC (0x007a6854 / 0x007a47e4) and
   clears the bound-texture cache. 0x00422360 rebuilds the console font and texture-quality state.
   `GL_CreateFrameBufferTargets` (0x00426cc0) and `GL_CreateEffectTargets` (0x00427c90) build the
   pbuffers and screen-copy textures for soft shadows and frame-buffer effects.
6. If vertex programs are in use, it builds about ten `CAurVertexProgram` objects (0x004a27d0: 0x201c
   bytes holding source text, bound via 0x004a24d0). These are the standard, skinned,
   bumpy-shiny and bumped-out programs, written as `!!ARBvp1.0` source with `!!VP1.0` (NV) as the
   fallback.
7. It enables GL_MULTISAMPLE when it got a multisample format, and applies v-sync through
   `wglSwapIntervalEXT`.

The app-side video-mode function `SetVideoMode` (0x00403800, see [app.md](app.md)) wraps all of this. It reads "Disable
Vertex Buffer Objects" and "Disable Write-Only VBO" from `[Graphics Options]`, which call
`Render_DisableVBO` 0x0044ef60 and `Render_Disable/EnableWriteOnlyVBO` 0x0044ef70/0x0044ef80. It
recreates the "Render Window", then calls `GL_SetDefaultState` (0x00401bb0): black clear colour, and
cull face, depth test, lighting, texture 2D, blend (src-alpha / one-minus-src-alpha) and alpha test
all enabled.

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
- It resolves 202 entry points with wglGetProcAddress into globals 0x007bb528-0x007bb854. The
  important ones are proposed by role: `g_glActiveTextureARB` 0x007bb80c,
  `g_glClientActiveTextureARB` 0x007bb6b0, `g_glCompressedTexImage2DARB` 0x007bb774, the VBO set
  (Bind 0x007bb7b4, Data 0x007bb544, Gen 0x007bb5b4, Map 0x007bb634, Delete 0x007bb7bc), the ARB
  program set (Bind 0x007bb788, String 0x007bb580, EnvParameter4f 0x007bb850), the pbuffer set
  (Create 0x007bb530, GetDC 0x007bb6b8), and `wglSwapIntervalEXT` 0x007bb538.
- If the renderer string contains "GeForce3", write-only VBOs are turned off.
- It reads the maximum anisotropy, builds a 64x64 noise texture (`GL_CreateNoiseTexture`
  0x004263c0), and picks the texture-shader backend. With ATI_fragment_shader the hook is
  0x0047a2f0, which also builds programs through 0x004794e0. Otherwise it is the NV register
  combiner / texture-env switch 0x0042e600. The hook pointer is `g_pfnSetupTextureShader`
  0x007a47e0; two sibling hooks sit at 0x007a6820 and 0x007a47dc.
- It creates the vertex-buffer manager `g_pAurVertexBufferManager` (0x007a68a4): the VBO flavour
  (0x00436400, vtable 0x0073f4fc) when `GL_UseVBO` (0x0045fc90) agrees, else plain client memory
  (0x00436390, vtable 0x0073f4b8). Both share base vtable 0x0073f488.

Cached capability tests, which return -1 until first asked: `GL_UseVertexPrograms` 0x0045f770,
`GL_HasMultitexture` 0x0045f710, `GL_HasAnisotropy` 0x0045f8e0, `GL_GetStencilBits` 0x0045fd00, and
0x0045f580 (swap control). There are also several combined path tests (0x0045f640, 0x0045f680,
0x0045f7b0, 0x0045f7e0, 0x0045f820, 0x0045f860, 0x0045f8b0, 0x0045fbd0). The .data flag 0x0078e5ec
is never written and is 1, so the ARB vertex-program path is always used, with NV as the fallback.

### Per-frame render chain

| step | addr | name | notes | conf |
|---|---|---|---|---|
| 1 | 0x004041f0 | WinMain loop | glClear, GL_LIGHT0 on/off by flag (0x0044da60/0x0044da80, cached in 0x0078e388), then client MainLoop | high |
| 2 | 0x00602eb0 | CClientExoAppInternal::MainLoop | see app.md; the render work happens in the next two calls | high |
| 3 | 0x006048c0 | CClientExoAppInternal::UpdateObjectsAndRender | runs client object updates (vtable +0x74) under a timer, then the module render | med |
| 4 | 0x00644650 | CSWCModule::Render | updates the area (0x006097f0); unless the GUI manager's fullscreen flag (+0x70) is set, calls camera slot 2 | med |
| 5 | 0x0045c540 | CAurCamera::Render | viewport, gluPerspective (0x0045c300) or ortho (0x00404b60), six frustum planes, view matrix (0x00425ca0), sets `g_pAurCurrentCamera` 0x007bb4e8, calls scene slot 6 | high |
| 6 | 0x004512d0 | CAurScene::Render | timing (`Render_GetMicroseconds` 0x0044f320), stats, sets `g_pAurCurrentScene` 0x007b92a0, depth func LEQUAL, vertex/normal/texcoord arrays on, alpha test GREATER, lighting on; ticks the scene clock; slot 46 | high |
| 7 | 0x004514f0 | CAurScene::RenderPasses | fog (slot 73, 0x00450de0), light model ambient, opaque objects, stencil clear plus shadow volumes (slots 69/70, 0x00456300), soft shadows (slot 47, 0x00451a50), transparent/sorted pass, screen effects (0x00437520, 0x004361f0), then a state reset | med |
| 8 | 0x0040cc50 | GUI manager render | 2D pass over the 3D frame; see the GUI section | high |
| 9 | 0x0044d6a0 | Console_Render | console lines and watches on top | med |
| 10 | 0x004041f0 | SwapBuffers | through GetDC on the render window, skipped while the client query 0x005edb40 is set (it also skips glClear) or while a mode change is pending | high |

`Render_BeginFrame` (0x0044ed90) is called from the GUI render and the client loop. It does an
optional throttle, records free physical memory, and calls `AurTextures_Update` (0x00421ee0),
which finishes queued texture loads. `RenderLoadingFrame` (0x00401c10, see app.md) is the stand-in frame
used during long loads (module load and the like, 17 callers). It clears, draws the GUI (load screen
and progress), swaps, pumps messages, and can run one server tick.

Scenes are named objects (vtable 0x00741708, 75 slots; constructor 0x00458790; factory 0x00458e70)
kept in `g_apAurScenes` 0x007b9398 / `g_nAurScenes` 0x007b939c and found with
`CAurScene::FindByName` 0x0044fd60. Each area makes one "mainscene" when it loads (0x00607610 stores
it at area+0x184). GUI 3D views (character models in menus, 0x004174b0) make their own "scene" plus
"camera". Cameras are 0x234-byte objects (`CAurCamera::Create` 0x0045d930, vtable 0x00741b20,
multiple inheritance with a secondary vtable at +4). The module camera lives at module+0x40 and is
created in 0x0063f660.

### 2D / GUI pass helpers

| addr | name | what | conf |
|---|---|---|---|
| 0x004591b0 | Render_Begin2D | saves the viewport, disables lighting and depth test, unit ortho projection, alpha blend | high |
| 0x004592b0 | Render_End2D | restores the projection, re-enables lighting and depth | high |
| 0x004592f0 | Render_PushViewport | pushes a sub-rectangle viewport, optional clear (used for GUI 3D views and clipping) | med |
| 0x00459580 | Render_PopViewport | pops it | med |

These have 9 to 12 callers, all in the GUI manager (0x0040ae80, 0x0040b760, 0x0040cc50) and in
GUI controls (0x0067ab00, 0x00685330, ...).

### Models: parts and draw calls

`CAurPart::CreateFromMdlNode` (0x00448a70) builds the render object for each MDL node by switching
on the node-type flags:

| flags | constructor | vtable | kind |
|---|---|---|---|
| 0x001 | 0x00447b20 (0x004457a0) | 0x00740ae8 | dummy / base part |
| 0x003 | 0x00447b90 (0x00445a40) | 0x00740c08 | light |
| 0x005 | 0x0049d5c0 | 0x00743478 / 0x00743500 / 0x00743588 | emitter (three variants) |
| 0x009 | 0x00447c80 | | camera node |
| 0x011 | 0x00447ce0 | 0x00740f30 | reference |
| 0x021 | 0x00447d60 (0x00445840) | 0x00740b68 | trimesh |
| 0x061 | 0x00487510 | 0x00740e10 | skin |
| 0x0a1 | 0x00447dd0 | 0x00740fb0 | animated-UV mesh |
| 0x121 | 0x00447e90 (0x00447980) | 0x00740d78 | AABB walkmesh |
| 0x221 | 0x00447e30 | 0x00741048 | dangly mesh |
| 0x401 | 0x0063e7c0 | | game-side type (unresolved) |
| 0x821 | 0x004480c0 (0x004478d0) | 0x00740ce0 | lightsaber |

Part vtable slot 23 is the draw call. Trimesh, saber, aabb, animmesh and dangly share
`CAurPartTriMesh::Render` 0x00474220, while skin has its own `CAurPartSkin::Render` 0x00477b90,
which loads bone matrices into program parameters. Slot 24 is material setup (0x00473900, using
glMaterialfv). The leaf draw is `CAurPartTriMesh::DrawIndexed` (0x0046f900, 22 callers, one per
material/shader variant). It calls `GL_DrawElements` (0x00425ab0, which binds the element VBO when
VBOs are on) once per index list, and counts triangles and draw calls into 0x00827fb0 / 0x00827fb4;
`Render_ResetFrameStats` 0x0046ee00 zeroes those counters.

Vertex streams go through small VBO-aware helpers: `GL_SetVertexPointer` 0x00425900,
`GL_SetColorPointer` 0x00425970, `GL_SetNormalPointer` 0x004259e0, `GL_SetTexCoordPointer`
0x00425a40, `GL_SetClientActiveTexture` 0x00425250, and `GL_SetMeshArrays` 0x00425520 for a whole
layout. glDrawArrays is used only for particles, lines and debug drawing (0x00426000, 0x00426230,
0x00431bb0-0x00431f70). `GL_DrawShadowVolume` 0x00426660 draws stencil shadow volumes.
`GL_SetProgramEnvParam` 0x0044f820 writes vertex-program constants (17 callers).

### Textures

- Requests: `AurTexture_Request` (0x00423a60, 12 callers) goes to `AurTexture_FindOrCreate`
  (0x00423490). That searches resident textures by name (`AurTexture_Find` 0x00420ac0 over
  `g_apAurTextures` 0x007a4798). If the name is missing it creates a `CAurTexture` (0x00423150,
  0xec bytes, vtable 0x0073f160 on base 0x0073f0a8) and queues it on `g_apAurPendingTextures`
  0x007a4770. "NormCubeMap" is a built-in special case.
- Each frame `AurTextures_ProcessPending` (0x004217f0) drains the queue. `CAurTexture::FinishLoad`
  (0x004216a0) calls `CAurTexture::LoadImage` (0x0041fa30) and then `CreateGLTextures` (0x00420970).
- Image data comes through a renderer callback table at 0x0078d404. Its defaults read loose files
  ("%s.tga" 0x0045e350, "%s.dds" 0x0045f4a0, "%s.plt" 0x0045e510).
  `Render_InstallResourceCallbacks` (0x0070d9c0, called from client init) replaces them with
  resource-manager readers (0x0070c790 TGA, 0x0070d380, 0x0070c6e0, ...) and sets the texture
  quality (`AurTextures_SetQuality` 0x00421d90). The TPC/TGA formats themselves belong to the
  resources agent.
- Upload: `CAurTexture::CreateGLTextures` (0x00420970) generates one GL name per tile and
  dispatches. 2D textures go to `Upload2D` 0x00424980: DXT through `glCompressedTexImage2DARB`
  (the format comes from a table at 0x0073f36c), otherwise glTexImage2D/SubImage2D per level, or
  gluBuild2DMipmaps, or SGIS auto-mipmap. It also sets wrap/clamp and filtering. 0x00424dd0 is an
  alternative 2D path. Cube maps go to 0x00423f90 (plain) and 0x00424230 (can take compressed
  faces). Other callers of gluBuild2DMipmaps are a 256x256 noise texture (0x00423d80) and a cube
  mip builder (0x00425ea0). 0x004260a0 uploads BGRA dynamic textures, and 0x00420ea0 fits sizes to
  a power of two.
- Binding: `GL_SetActiveTextureUnit` 0x0041fe80 (unit in 0x007a6898), and `GL_BindTextureCached`
  0x00420440 / `CAurTexture::Bind` 0x004204f0, which record the binding in the six-entry cache
  0x007a683c and apply anisotropy (0x007a685c).

### Materials: blending and alpha test

A mesh's material object (constructor `0x0047b290`, our `CAurMaterial`; built by `0x0047b560` from
up to four texture names, which reads each texture's TXI through `0x0047b110`) holds per texture
layer a source and a destination blend factor, as indices into the table at `0x0073f270`:
0 `GL_SRC_ALPHA`, 1 `GL_ONE_MINUS_SRC_ALPHA`, 2 `GL_ONE`, 3 `GL_ZERO`, 4 `GL_SRC_COLOR`, 5
`GL_DST_COLOR`, 6 `GL_ONE_MINUS_DST_ALPHA`, 7 `GL_DST_ALPHA`. (high)

- The constructor's default is (0, 1): **ordinary alpha blending** (`SRC_ALPHA,
  ONE_MINUS_SRC_ALPHA`). (high)
- The TXI keyword reader (`0x0047abd0`, which also takes `bumpmaptexture`, `bumpyshinytexture`,
  `envmaptexture`, `decal`, `renderbmlmtype` and `wateralpha`) sets `blending additive` to (0, 2)
  `SRC_ALPHA, ONE` and `blending punchthrough` to (2, 3) `ONE, ZERO`; any other value leaves the
  default. (high)
- Applying a layer (`0x0047af70`, from `CAurPartTriMesh::ApplyMaterial` 0x00473900 and ten
  other draw paths; `0x0047b000` for layer 0) calls glBlendFunc with the pair, turns depth writes
  **off only for (0, 2)** (additive), and sets the alpha test to `GREATER 0.35` (`0x00798a90`)
  for (2, 3) and `GREATER 0` otherwise (the flag `0x00798a8c` that enables this is 1 in .data and
  never written). (high)

So a texture's alpha is transparency by default: blended, depth-written, only alpha 0 discarded;
punch-through cuts at 0.35. The env-map and bump-map paths (register combiners / ARB programs,
not traced) evidently don't use the diffuse alpha as opacity: env-mapped droids and the
bump-mapped rancor (`c_rancor01`, AlphaMean 0.76) are solid in the game. (inferred)

### Environment maps

How a mesh with an environment map is drawn (all *high* from the code, the unnamed functions are
ours). The material (`0x0047b290`, texture names read by `0x0047abd0`) holds the bump map at
+0x10 and the environment map at +0x14 (`envmaptexture`, or `bumpyshinytexture` for a bump-mapped
one); a creature's appearance.2da `envmap` is the part's own override (part +0x40 → +0x1a8) and wins
over the texture's. The draw path is chosen per mesh by `0x00470d30` (the switch in `0x00477830`);
it depends on the mesh's lightmap (dropped when the lightmap texture did not load), whether it has a
bump or environment map, and the GL capability bits (NV register combiners, ATI fragment shader,
ARB vertex programs). The environment map is sampled with texgen `REFLECTION_MAP` (`SPHERE_MAP`
for a 2D texture) through a texture matrix made of the camera's orientation (`0x0046f780`), i.e. by
the reflection vector in world space. A diffuse texture that is neither RGBA nor DXT5 has no
alpha to mask with, and `0x0046ff70` draws it without the reflection.

What the combination is, by path (the diffuse's alpha is `a`):

| Path | Used for | Colour |
|---|---|---|
| lightmapped, fixed function (`0x0046fb10`): the diffuse lit with `ONE, ZERO`, the lightmap with `DST_COLOR, ZERO`, then the environment map with `ONE_MINUS_DST_ALPHA, ONE` | rooms with a lightmap and an environment map (on cards without the combiner path) | `diffuse * lightmap + env * (1 - a)` |
| lightmapped, combiners (`0x00470590`): the diffuse times the lightmap, then the environment map drawn with `ONE, ONE` (combiner shader 0x15; its mask was not decoded) | the same on NV hardware | the same sum (*inferred*) |
| unlightmapped, NV register combiners (`0x0046ff70`, shader 0x13, `0x0042e600`) | creatures and placeables on NVIDIA | `diffuse * light + env * (1 - a)` |
| unlightmapped, ATI fragment shader (`0x0047a2f0`, `0x004794e0`) | the same on old Radeons | `lerp(a, diffuse * light, env)`, i.e. `a * diffuse * light + (1 - a) * env` |
| unlightmapped, plain multipass (`0x0046ff70` without a texture shader) | everything else (Intel, current AMD) | the environment map (lit), then the diffuse over it by `SRC_ALPHA, ONE_MINUS_SRC_ALPHA`: `light * (a * diffuse + (1 - a) * env)` |

So the two hardware-specific paths of the original disagree on a creature (the NV sum shows the
diffuse in full plus the reflection, the other two blend by alpha); the data is made for blending
by alpha, where a low alpha means a mirror: the Sith soldier's `N_SithSoldier03` has AlphaMean 0.55
and a mid-grey diffuse, which is dark gunmetal that way and silver chrome as a sum. We follow the
blend (unlit reflection, as the ATI shader): `lib/render_gl/shaders.ctx`, lightmapped meshes keep
the sum. The material's opacity (`+0x84`, the alpha controller) goes to the combiner's constant
colour alpha, not into the blend.

### Shadows, grass, frame-buffer effects, options

The client options loader (0x0061dbe0, which reads `[Graphics Options]`) calls small setters:
- Shadows: 0x0044ee20 / 0x0044f080 (flag 0x0078e3a8).
- Soft Shadows: 0x0044ee50 / 0x0044ee60 (flag 0x0078e420).
- Grass: 0x0044ee30 / 0x0044ee40 (flag 0x0078e3ac).
- Frame Buffer effects: 0x0044ee70 / 0x0044ee80 (flag 0x0078d98c), through 0x0061d750.
- V-Sync: `Render_SetVSync` 0x0044ee90.
- Anti-aliasing: `Render_SetAntiAliasing` 0x0044f2f0 (sample count 0x007a6888).
- Brightness goes to display slot 9.

Frame-buffer effects copy the screen into a rectangle or 2D texture and run 256x256 pbuffer passes
(0x0042b370-0x0042d9a0, 0x00432780-0x00435bd0; each makes the pbuffer current, draws, glFlush, then
switches back). Stage setup is a switch in 0x004299c0.

### Console overlay

A Quake-style console is built into the renderer library. `Console_ExecFile` 0x0044c980 runs
config.txt and startup.txt at start-up, and `Console_Execute` 0x0044c1f0 runs one command line.
`Console_Print` 0x0044d490 queues a 0x434-byte fading line, `Console_Render` 0x0044d6a0 draws it,
and `Console_DrawText` 0x0044ce50 draws at a character cell. The console font is either glBitmap
display lists (0x0044cb10 build, 0x0044cb90 draw, 0x00432040 call lists, 0x0044cc60 free) or a
textured font (0x0044cca0). WinMain draws the ">" prompt and input buffer (0x007a3a4c) while the
console is open (0x007a3a40). `Render_TakeScreenshot` 0x004211a0 writes snapN.tga with glReadPixels.

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
(`GL_CheckError` 0x0044eee0). GDI32 provides ChoosePixelFormat, SetPixelFormat and
DescribePixelFormat (0x0042e040, 0x0044dab0, 0x0044e3b0), SwapBuffers (WinMain, 0x00401c10) and
SetDeviceGammaRamp (display slot 9).

### Open points

- What the real classes were called: there is no RTTI and there are no log strings in this
  library. The `CAur*` names are ours.
- Scene vtable slots other than 6, 46, 47, 70 and 73 are unnamed. The order of the opaque and
  transparent passes inside 0x004514f0 is inferred from the state changes, not proven.
- Node type 0x401 goes to game code (0x0063e7c0); it may be a grass or other game-side part.
- The resource-backed image callbacks 0x0070c6e0, 0x0070cc60, 0x0070cd10, 0x0070cdd0, 0x0070ce80,
  0x0070d380, 0x0070d510 and 0x0070d6b0 are only partly identified (TGA confirmed; PLT and DDS by
  slot position).

## GUI

The GUI is a retained tree of panels and controls owned by one manager. Panels are
filled from `.gui` resources (GFF, restype 0x7ff, signature `GUI `); the code
creates each control object itself and then binds it to a GFF struct by its `TAG`.
Every class name below is ours unless a confidence says otherwise; the binary has
no RTTI for these classes. Names follow the Aurora `CSWGui*` style.

### Ownership and per-frame flow

| What | Where | Confidence |
|---|---|---|
| `g_pGuiManager` (CSWGuiManager*) | global 0x007a39f4 | high |
| owner of the manager | `CClientExoAppInternal` +0x274 (created in the client's Initialize, 0x005f8550, size 0xa8) | high |
| `CClientExoApp::GetGuiManager` | 0x005eda40 (returns internal+0x274) | high |
| in-game panel owner (`CGuiInGame`, our name) | `CClientExoAppInternal` +0x40, 0xc24 bytes, ctor 0x0062fed0 | med |
| main menu panel | created by 0x005fca30 via `CSWGuiMainMenu` ctor 0x0067c4c0 | high |

Each client frame (client main loop 0x00602eb0) runs, in order:

1. `CClientExoAppInternal::ProcessInput` 0x006227e0: drains mapped input events
   from `CExoInput` (one 16-byte record per event; the action code sits in the
   key-map entry at +0x10). Game actions go to `HandleInputAction` 0x00621210;
   GUI actions (codes 0x27..0x40 and the dpad codes 0xb4..0xbb, while a GUI is up)
   go to `CSWGuiManager::HandleInputEvent` 0x0040c8e0. Afterwards the cursor
   position (client +0x3c8/+0x3cc) goes to `CSWGuiManager::HandleMouseMove`
   0x0040c1e0.
2. `CSWGuiManager::Update(dt)` 0x0040ce70: each active panel's Update slot.
3. `CSWGuiManager::Render(dt)` 0x0040cc50: the 2D pass (see below).

Mouse buttons arrive as mapped actions: action 0x43 is the left button
(`OnLeftMouseDown` 0x0061f880 with value nonzero, `OnLeftMouseUp` 0x00620530 with
value 0); the right button and wheel go through `HandleInputAction` to
0x0061f940 / 0x0061f960 / `CSWGuiManager::HandleMouseWheel` 0x0040c650. Typed
characters come from the window-message path (0x00402240) into
`CSWGuiManager::HandleCharacter` 0x0040b2a0, which forwards them to the edit
box that holds keyboard focus. All med.

### CSWGuiManager (no vtable)

Constructor 0x0040bad0, destructor 0x0040aaa0. Field map (med unless noted):

| Offset | Meaning |
|---|---|
| +0x00/+0x04 | last cursor x, y |
| +0x08 | control under the cursor (hover) |
| +0x0c / +0x10 | mouse-capture button (1 left, 4 right) / capturing control |
| +0x18 | edit box with keyboard focus |
| +0x1c | flags: bit0 left button down, bit2 cursor centred, bit3 tooltip showing |
| +0x20 | software-cursor scene object (drawn last) |
| +0x24 | cursor model used by `SetMouseCursor` |
| +0x38 | current cursor id (index into the name table at 0x0078d240) |
| +0x3c | tooltip panel (`CSWGuiToolTip`, ctor 0x006277c0) |
| +0x44/+0x48 | tooltip delay timer / threshold |
| +0x54 | dragged object drawn on top (inventory drag) |
| +0x58/+0x5c | saved cursor position (-1 when none) |
| +0x6c/+0x6e | screen width/height (shorts) (high) |
| +0x70/+0x71 | counters of panels by type flags |
| +0x72, +0x64 | last mouse-button event and its time (150 ms double-click window) |
| +0x74 | resolution tag string, e.g. "800x600" |
| +0x88 | panel list (CExoArrayList) (high) |
| +0x94 | modal panel stack (CExoArrayList) (high) |
| +0xa0/+0xa4 | GUI sound array / count, from guisounds.2da (high) |

Key methods (full list in the proposals): `AddPanel` 0x0040bc70 (134 callers),
`RemovePanel` 0x0040c830, `PushModalPanel` 0x0040bd90, `PopModalPanel`
0x0040be00, `BringPanelToFront` 0x0040bd20, `PlayGuiSound` 0x0040a140,
`LoadGuiSounds` 0x00409f00, `SetResolution` 0x0040be70, `SetMouseCursor`
0x0040a270, `GetPanelAndControlAt` 0x0040abe0, mouse capture 0x0040a1c0 /
0x0040a200.

Render (0x0040cc50) draws, in order: every non-modal panel that is active (flag 4)
and not on the modal stack, then the modal stack bottom to top, then the dragged
object, then the tooltip once its timer passes, then the software cursor. Each
panel draw is bracketed by a GUI render-state push/pop from the renderer
(0x004591b0 / 0x004592f0 / 0x00459580 / 0x004592b0, renderer side). Panels whose
flags (bits 9..10) ask for removal or deletion are reaped after drawing. While
0x007a3d4c is set it also draws an overlay built by 0x0040bec0 (purpose unknown).

### Input event codes (the `nEvent` passed to HandleInputEvent)

Derived from the dispatch code; meanings are med unless noted.

| Code | Meaning |
|---|---|
| 0 / 1 | gain / lose hilight (focus) (high) |
| 0x27 | activate: click or Enter; panels attach their button callbacks to it (high) |
| 0x28..0x2b | other accept/cancel-style buttons; the panel slots 20..24 resend them to themselves |
| 0x2d | second activate code (gamepad), wired like 0x27 in the main menu |
| 0x2f..0x32 | raw mouse-button codes used for double-click timing |
| 0x33/0x34, 0x37/0x38 | axes, folded into 0x39..0x40 by sign |
| 0x39..0x40 | directional navigation (MOVETO) |
| 0x44 | right click (fired by OnRightMouseUp) |
| 500 / 501 | wheel down / up |
| 0x1f9 | left-press notification sent to controls |
| 0xb4..0xbb | dpad/keyboard codes remapped to 0x27, 0x28, 0x3d..0x40 |

With no modal panel the manager sends the event to every panel; otherwise only
to the top of the modal stack. A panel forwards it to its active control
(0x00409e60). A control first handles 0/1 itself, then looks up its handler table
(+0x38, entries {owner, callback, event}) and calls the callback registered with
`CSWGuiControl::SetEventHandler` 0x0041ab20 (82 callers). This is how every
panel wires its buttons.

### Panels

`CSWGuiPanel` vtable 0x0073e010, ctor 0x0040b570 (takes the manager), dtor
0x0040cf70. Layout: +0x04..+0x10 extent, +0x18 manager, +0x1c active control,
+0x20/+0x24 control array, +0x2c open `.gui` GFF during load, +0x30 its CONTROLS
list, +0x44 flags (bit0 already placed, bit1 GFF loaded, bit2 active, bit3 centre,
bit7 top modal), +0x48 resolution-suffix index, +0x4c alpha, +0x50 colour,
+0x5c border. High for the structure, med for individual flag meanings.

| Slot | Function | Role |
|---|---|---|
| 0 | 0x0040d010 | scalar deleting destructor |
| 1 | 0x0040a5a0 | SetExtent (also resizes the border) |
| 2 | 0x0040a630 | SetActiveControl |
| 10 | shared `return this` stub | "as panel" query used by controls to find their panel |
| 13 | 0x0040b760 | Render |
| 14 | stub | Update |
| 15 | 0x00409e60 | HandleInputEvent |
| 16 | 0x0040b690 | HitTest(x, y) |
| 17 | 0x0040b630 | GetActiveControl |
| 18 | 0x0040b870 | OnPanelAdded |
| 19 | 0x0040c170 | OnPanelRemoved |
| 20..24 | 0x0040b640..0x0040b680 | resend events 0x27..0x2b to itself |
| 25 | 0x0040a900 | resolution tag |
| 26 | 0x0040a9c0 | OnResize |

All panels and controls share the 13-slot base vtable 0x0073df20 (our
`CSWGuiObject`; slot 1 `SetExtent` 0x00409e90).

#### Loading a .gui

1. The derived constructor calls the base ctor, constructs its member controls
   in place (each a full object inside the panel), then calls
   `CSWGuiPanel::LoadGui` 0x0040a680 with the resref (e.g. "mainmenu"). That opens
   the GFF and reads the root EXTENT, COLOR, BORDER (or BACKGROUND), ALPHA and
   keeps the CONTROLS list.
2. For each member it calls `CSWGuiPanel::InitControl` 0x0040b930 with the tag
   ("BTN_NEWGAME"...). That scans CONTROLS for the matching TAG
   (0x00418840) and calls the control's LoadFromGFF slot (vtable +0x48). The base
   loader 0x0041b8e0 reads EXTENT, ID and Obj_ParentID; derived loaders add their
   parts. The control is stored in the panel array by ID.
3. `CSWGuiPanel::FinishLoading` 0x0040b8f0 releases the GFF and resolves the
   MOVETO navigation links (0x0040a890).
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
that adds MOVETO (UP, DOWN, LEFT, RIGHT ids, loader 0x0041c890). The check box
derives from the button, the proto item from the label.

#### Control vtable (38..42 slots, base 0x0073e488, ctor 0x0041aa80, dtor 0x00419a20)

| Slot | Base function | Role | Confidence |
|---|---|---|---|
| 1 | 0x00409e90 | SetExtent | high |
| 3 | 0x004189a0 / 0x0041a980 | set hilight with sound (selectable classes) | med |
| 4 | stub (slider 0x00419250, list 0x0041b670) | OnMouseDrag while captured | med |
| 5 | nop | capture lost | low |
| 6 / 7 | 0x0041ab90 / 0x0041abd0 | left button down / up (up fires 0x27) | med |
| 9 / 33 | 0x0041ac70 / 0x0041ac30 | right button up (fires 0x44) / down | med |
| 14 | label 0x00417750, button 0x00417ab0 | Render | high |
| 15 | 0x00418750 | HandleInputEvent | high |
| 16 | 0x004181d0 | SetHilighted (flag bit0) | med |
| 17 | 0x004187c0 | HitTest | high |
| 18 | 0x0041b8e0 | LoadFromGFF | high |
| 31 | 0x00418960 | SetFocus | med |
| 32 | 0x004189d0 | IsSelectable | med |
| 34 | 0x004176a0 | SetSelectable (flag bit3) | med |
| 35 | per class | relayout after resize | low |
| 36 | 0x00418a90 | tooltip text (adds the bound key's name) | low |
| 39 | edit box 0x004184f0 | HandleCharacter | med |

Control fields: +0x04 extent, +0x14 parent control (Obj_Parent), +0x18 children,
+0x28 tag string, +0x34 owning panel, +0x38/+0x3c event handler table, +0x44
flags (bit0 hilighted, bit1 visible, bit3 selectable), +0x48/+0x4c last event and
value, +0x50 ID, +0x54 click-sound index, +0x55 hover-sound index (med).

#### Drawables inside controls

| Class (our name) | Vtable | Ctor | Loader | Draw | Notes |
|---|---|---|---|---|---|
| CSWGuiBorder | 0x0073e338 | 0x004167f0 | 0x004153e0 | 0x004168c0 | CORNER, EDGE, FILL, FILLSTYLE, DIMENSION, INNEROFFSET, COLOR, PULSING |
| CSWGuiText | 0x0073e3a4 | 0x00417280 | 0x00416050 | 0x00416240 | TEXT, STRREF, FONT, ALIGNMENT, COLOR, PULSING |
| CSWGuiImage | 0x0073e390 | 0x00415a30 | 0x00416ec0 | 0x00415c90 | IMAGE, ALIGNMENT, DRAWSTYLE, FLIPSTYLE, ROTATE (thumbs, arrows) |
| CSWGui3DScene | 0x0073e3f0 | 0x004174b0 | - | - | scene with a camera; main-menu 3D view, software cursor |
| editable text | 0x0073e444 | 0x004173d0 | text's | text's | backspace 0x004162e0, append 0x004163a0 |

### Fonts and text

Text settings (our `CSWGuiTextInfo`, ctor 0x00417050) hold the string, a TLK
strref, the font resref (default `dialogfont16x16`), colour and alignment.
`SetText` 0x00415e00 (136 callers) and `SetStrRef` 0x00415e50 (TLK lookup) push
the string into a render-side string object made by 0x0045bdf0 (0x48 bytes,
vtable 0x00741878, ctor 0x0045b990): a font texture plus the text, drawn by
the renderer. A font is a texture whose TXI carries the glyph table; the TXI
font keys (numchars, fontheight, baselineheight, texturewidth, spacingR/B,
upperleftcoords, lowerrightcoords) are parsed by 0x00422210 under the TXI parser
0x00422390 (renderer side). Other fonts named in code: `fnt_console`
(0x0040b360), `fnt_d16x16` (several panels); the "Use Small Fonts" option is
read at 0x0061b780 / 0x0061dbe0. Med overall; the render-string class is for
the renderer notes.

### Notable panels

| Panel (our name) | .gui | Ctor | Vtable | Notes |
|---|---|---|---|---|
| CSWGuiMainMenu | mainmenu | 0x0067c4c0 (InitPanel 0x0067ace0) | 0x00752f70 | LB_MODULES, BTN_NEWGAME/LOADGAME/MOVIES/OPTIONS/EXIT/WARP, LBL_3DVIEW; callbacks: NewGame 0x0067afb0, LoadGame 0x0067b1a0, Movies 0x0067b250, Options 0x0067b2f0, Exit 0x0067b4a0, hilight 0x0067b450/0x0067b470 (high) |
| CSWGuiMainInterface (HUD) | mipc28x6, mipc210x7, mipc212x9, mipc212x10, mipc216x12 | 0x0068c100 | 0x00753f50 | BTN_MSG, BTN_OPT, BTN_JOU, BTN_ABI, BTN_MAP, BTN_CHAR, BTN_INV, BTN_EQU, TB_PAUSE/SOLO/STEALTH, minimap, action queue; Render 0x0068b4a0, Update 0x00686ba0 (high) |
| CSWGuiLoadScreen | loadscreen | 0x0067a710 | 0x00752dc0 | LBL_LOADING, LBL_LOGO, LBL_HINT, PB_PROGRESS (high) |
| CSWGuiDialog (base) | - | 0x006a85b0 | 0x007559e0 | base of the three conversation panels (med) |
| conversation | dialog | 0x006a8b40 | 0x00755800 | LB_REPLIES, LBL_MESSAGE (high) |
| computer conversation | computer | 0x006a8eb0 | 0x00755888 | LB_MESSAGE, LB_REPLIES, spike/repair counters (high) |
| computer camera | computercamera | 0x006a95f0 | 0x00755958 | (med) |
| message box | confirm | 0x00626df0 | 0x0074fdb0 | LB_MESSAGE, BTN_OK, BTN_CANCEL (med) |
| tooltip | tooltipWxH | 0x006277c0 | 0x00750030 | owned by the manager (med) |
| message log | messages | 0x00626400 | 0x0074fd18 | LB_MESSAGES, LB_DIALOG (med) |
| top bar | top | 0x00627980 | 0x00750148 | (med) |
| fade | fade | 0x00624810 | 0x0074fc60 | LBL_MSG (med) |
| options | optionsmain, optgraphics, optsound, optmouse, ... | 0x006e3e80 ... | 0x00758838 ... | (med) |

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
0x006ea000, pwrlvlup 0x006f2180; character-generation steps 0x006ee7d0,
0x006ef730, 0x006f0390, 0x006f09f0, 0x006f3d60, 0x006f51d0, 0x006f7600 and the
name entry 0x006f9e70 (NAME_BOX_EDIT) build their names at run time. All med:
the `.gui` name is read straight from the string passed to `LoadGui`.

The in-game panels are created together by `CGuiInGame::CreatePanels`
0x00632860 (with loading-bar updates through 0x00401c10) and re-created after a
resolution change by 0x0062f5f0. The HUD lives at `CGuiInGame` +0x90, the
conversation panel at +0x40, the message box at +0x98, the GUI manager pointer
at +0x38 (med).

### Open questions

- True class names: none are confirmed; `CSWGuiSelectable`, `CSWGuiObject`,
  `CSWGuiTextInfo`, `CSWGuiImage`, `CSWGui3DScene`, `CGuiInGame` and the dialog
  subclass names are descriptive.
- The meaning of events 0x28..0x2b and 0x2d (likely cancel and gamepad buttons)
  and of panel flags 0x08/0x10 given to `AddPanel` needs a run-time check.
- The overlay drawn by 0x0040bec0 when 0x007a3d4c is set is unidentified.
- How `DAT_007a3d50` (resolution-suffix strings) is filled was not traced.
