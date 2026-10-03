# The platform layer and OpenGL loading

How the game reaches the OS and the GPU: SDL2 for windows, input, time and audio out, and OpenGL
4.1 core for drawing. Both were proved by the spike in `kotor/tools/glspike` (stage 0.4), whose
files are written to move unchanged into the libraries:

| Spike file | Namespace | Goes to | What |
|---|---|---|---|
| `sdl.ctx` | `sdl` | `lib/platform` | SDL2's functions and structs, ctxlang-shaped wrappers, the tagged `Event` |
| `gl.ctx` | `gl` | `lib/render_gl` | GL 4.1 core as a capability, optional KHR_debug, helpers, enums |
| `png.ctx` | `png` | `lib/base` | the PNG encoder for screenshots |
| `main.ctx` | (top level) | stays a tool | the spike: scene, screenshot, event and audio checks |

`png` goes to `lib/base` rather than `lib/tex` so that every tool that renders can write a
screenshot without depending on the texture decoders.

Run it: `kotor/tools/ctxc run kotor/tools/glspike -- --headless` writes `kotor/out/glspike.png`
(paths are from the working directory, the repository root). Without `--headless` the window
stays for `--seconds N` (3) and prints the input events it gets; Escape closes it.

## Capabilities

- **`sdl::Sdl`** (no fields) is permission to call SDL. `main` receives it from the runtime
  (spec §15) and passes it down. Every SDL extern fn takes it.
- **`gl::Gl`** (fields) holds GL's functions, one field each, looked up at run time; holding one is
  the permission to call GL. Only `gl::load` makes one, from a lookup function: SDL's, bound as
  `sdl::gl_proc{ &sdl, _ }`. So the GL backend names no windowing library, and a function that
  draws says so with `mut gl: gl::Gl`.

  ```
  let win = try sdl::open_gl_window{ &sdl, title = "kotor", width, height, major = 4, minor = 1,
      hidden = false, resizable = true, debug = false }
  let mut gl = try gl::load{ get_proc = sdl::gl_proc{ &sdl, _ } }
  gl.clear{ mask = gl::COLOR_BUFFER_BIT }
  ```

  `load` fails with `gl::too_old{ major, minor }` for a context before 4.1, or
  `gl::missing{ name }` for a function the driver didn't give.
- **`gl::Debug`** (fields) holds KHR_debug's functions. `gl::load_debug` gives it, or null where
  the context lacks KHR_debug, as macOS does: debug output is optional everywhere.

A capability with fields is a struct of function pointers passed by pointer, so a GL call is one
load and an indirect call, as C's own loaders do (`gl.clear{ mask }` becomes
`gl->m_clear(mask)`).

## SDL: what `sdl.ctx` covers

- **Init and errors:** `init`/`quit` (`SDL_Init`, `SDL_InitSubSystem` for audio),
  `last_error` (`SDL_GetError`), `SDL_SetHint`, `SDL_GetVersion`, `SDL_ShowSimpleMessageBox`.
- **Window and context:** `open_gl_window` sets the attributes macOS needs and the game wants (4.1,
  core profile, forward-compatible, 8-bit RGBA, 24-bit depth, 8-bit stencil, double-buffered,
  optionally the debug flag), creates the window (`hidden` for offscreen runs, `resizable`,
  always `ALLOW_HIGHDPI`) and the context, and makes it current. `close_gl_window`, `swap`,
  `set_swap_interval` (vsync), `drawable_size` (pixels) and `window_size` (window units),
  `gl_attribute` (what the context got), `SDL_SetWindowFullscreen` and friends.
- **Events:** `poll` returns the next event as the tagged union `sdl::Event` (quit, close,
  resized, focus, minimized, restored, exposed, key with scancode, keycode, modifiers and repeat,
  text, mouse motion with relative motion and buttons, mouse button with clicks, wheel with the
  OS's flip undone, and `other{ kind }`), so game code `match`es instead of reading a C union.
  The C union is `sdl::RawEvent`, an `extern union` with each member SDL2 has on 64-bit targets,
  field for field. Drop events' strings are freed in `decode`.
- **Input state:** `keyboard` (SDL's held-key array by scancode), `SDL_GetModState`,
  `SDL_GetMouseState`, `SDL_GetRelativeMouseState`, `set_relative_mouse` (mouse look),
  `set_text_input`, key and scancode names. `sdl::scan::*` and `sdl::key::*` name the keys the
  game binds.
- **Time:** `counter`/`counter_frequency` (`SDL_GetPerformanceCounter`/`Frequency`), `ticks`,
  `delay`.
- **Audio out:** `open_audio` opens the default device for interleaved signed 16-bit frames
  (SDL may change only the rate; the result says which), `queue_audio`, `queued_audio`,
  `clear_audio`, `pause_audio`, `close_audio`. ctxlang has no threads, so there is no callback
  (it would run on SDL's audio thread): the mixer tops the queue up each frame to a target
  latency, say 50-100 ms of frames, measured with `queued_audio`.

Not covered yet: game controllers, cursors, clipboard, display modes, IME composition
(`TEXTEDITING` arrives as `other`), audio device hot-plug.

### Layouts

The structs are SDL2 2.0.18+'s (built against 2.32.8), the same on every 64-bit target, Windows
included. `sdl::check_layout` compares their sizes with SDL's at start (ctxlang has no
`@offset_of`); their offsets were checked once against SDL's headers with a C program. The
spike's `check_events` also resizes the window and reads back the resize SDL itself reports, and
round-trips a key, text, button and wheel event through SDL's queue. ctxc lays a struct out as C
does (field order, natural alignment), so copying SDL's field list, padding fields included, is
the whole method. `SDL_bool` and C enums are `i32` parameters; SDL_GLattr is a ctxlang `enum`
(an extern fn passes it as its base type).

## GL: what `gl.ctx` covers

Everything is 4.1 core, so it runs on macOS as on Windows and Linux:

- state: enable/disable, viewport, scissor, clears, blending (separate too), depth, stencil
  (separate faces too), culling, polygon offset and mode, colour mask, pixel store, finish/flush,
  `get_error`, `get_string(i)`, `get_integerv`/`floatv`;
- shaders and programs: create, source, compile, link, info logs, uniform and block locations,
  `uniform_block_binding`, `uniform{1i,1f,2f,3f,4f}`, the `v` forms, `uniform_matrix{3,4}fv`;
- buffers (VBO, IBO, UBO, `bind_buffer_base/range`, `map_buffer_range`), vertex arrays, float and
  integer attributes, divisors, `draw_arrays`, `draw_elements`, `draw_elements_base_vertex`,
  instanced draws;
- textures: 2D and cube maps, `tex_image_2d`, `tex_sub_image_2d`, `compressed_tex_image_2d` and
  `sub` (DXT1/3/5 through EXT_texture_compression_s3tc's enums), parameters, `generate_mipmap`,
  `get_tex_image`; sampler objects;
- framebuffers and renderbuffers (multisampled too), blits, draw and read buffers, `read_pixels`;
- timer queries (`TIME_ELAPSED`, `query_counter`).

Field and parameter names are GL's in snake case (`glTexImage2D` is `tex_image_2d`, `type` is
`kind`); types map as GLenum/GLuint/GLbitfield `u32`, GLint/GLsizei `i32`,
GLsizeiptr/GLintptr `i64`, GLboolean `u8` (`gl::TRUE`, `gl::FALSE`), data GL reads `?*u8` or
`*T`, and buffer offsets GL takes as pointers `usize` (64-bit ABIs pass the two alike, and
ctxlang can't make a pointer from an integer).

Helpers: `compile` and `link` (shader source as lines, `[]c::String`; the info log goes into a
caller's buffer and the error says how long it is), `has_extension`, `get_int`, `string`,
`check` (glGetError as a `gl::failed{ code, what }`), `error_name`, one-name `gen_*` and
`delete_*`, `make_buffer`, `bytes_of(T)` (any slice as bytes for GL), and the offscreen target:
`make_target`, `free_target`, `read_rgba`, `present` (blit to the window, scaled to its drawable
size).

### GLSL 410 rules the backend must keep

- `#version 410 core`. No `layout(binding = N)` (4.2): set a sampler's unit with `uniform1i`
  and a block's binding with `uniform_block_binding`, after linking.
- `layout(location = N)` on vertex inputs and fragment outputs is fine.
- Uniform blocks are `layout(std140)`: a `vec3` takes 16 bytes, a `mat4` 64. Buffer offsets for
  `bind_buffer_range` are multiples of `UNIFORM_BUFFER_OFFSET_ALIGNMENT` (256 on the spike's
  NVIDIA).
- Not in 4.1, so not on macOS: `glTexStorage*` and image load/store (4.2), SSBOs, compute and
  multi-draw indirect (4.3), KHR_debug (4.3), direct state access and `glClipControl` (4.5).

### Debug output

Where KHR_debug exists, `gl::start_debug{ &gl, &debug, log = &debug_log }` turns it on,
synchronous, with notifications off. The driver calls `gl::on_debug_message` (a `#c::callback`)
during the GL call that caused a message. A callback can't take a capability with fields, and
taking `Io` would promise that GL is only called where `Io` is held, so the callback only appends
to a `gl::DebugLog` reached through `userParam`, and the program prints the log where it holds
`Io` (the spike's `print_debug`). The log must outlive the context.

## The screenshot path

Every renderer feature is checked by rendering offscreen and reading the PNG (AGENTS.md, rule 6).
The path, as the spike runs it:

```
let target = try gl::make_target{ &gl, width = 640, height = 480 }    // RGBA8 + depth24/stencil8
// draw with target.framebuffer bound and viewport 0, 0, width, height
gl::read_rgba{ &gl, t = target, into = pixels }                         // width * height * 4 bytes
let image = png::Image{ width = 640, height = 480, rgba = pixels }
try png::save{ &fs, realloc = arena::alloc, &heap, path = "kotor/out/x.png", image, alpha = false, bottom_up = true }
```

`bottom_up = true` because GL's rows start at the bottom. `alpha = false` writes RGB: a
framebuffer's alpha after blending isn't meant to be seen, and viewers would show it as
transparency. The PNG holds stored (uncompressed) deflate blocks, about 0.9 MB for 640x480;
it was checked byte for byte with Python's zlib on RGB and RGBA, flipped and not, from 1x1 to a
three-block 20000x2 image.

`--headless` uses a hidden window: SDL makes a GL context only for a window, and a hidden one
works. Drawing goes to the target, never the default framebuffer, whose pixels a hidden window
doesn't own.

## What the spike saw

Windows 11, NVIDIA GeForce RTX 4090, driver 616.92: `GL_VERSION 4.1.0 NVIDIA 616.92`, core
profile, forward-compatible and debug flags set, 24-bit depth and 8-bit stencil default
framebuffer, 404 extensions, S3TC and anisotropic filtering present, KHR_debug on. The frame took
40 us on the GPU; the window ran at the display's 144 Hz with vsync. SDL 2.32.8; audio through
WASAPI at 44.1 kHz.

## Porting to macOS and Linux

- **Build:** `build.ctx` already links SDL2 on all three; macOS adds Homebrew's
  `/opt/homebrew/lib` (Intel Homebrew uses `/usr/local/lib`). Nothing links OpenGL: SDL loads it,
  and every GL function comes through `SDL_GL_GetProcAddress`.
- **High DPI:** windows are created with `ALLOW_HIGHDPI`. On a Retina display the drawable is
  larger than the window: size the viewport and targets by `drawable_size`, and scale mouse
  coordinates (window units) by drawable / window. A macOS app bundle also needs
  `NSHighResolutionCapable` in its Info.plist. On Windows, SDL stays DPI-unaware unless the hint
  `SDL_WINDOWS_DPI_AWARENESS` is set (not set yet; Windows then scales the window).
- **Context:** macOS gives exactly 4.1 for a 4.1 core forward-compatible request; Windows and
  Linux drivers may give a later version, which is fine. Keep to 4.1 features (above) so nothing
  works on one platform only. KHR_debug is absent on macOS: `load_debug` gives null.
- **S3TC:** check it on Apple Silicon (its GL runs over Metal and reports the extension); the game
  should stop with a clear message where `has_extension("GL_EXT_texture_compression_s3tc")` is
  false rather than decode DXT on the CPU.
- **Headless on Linux:** a hidden window needs an X11 or Wayland display; without one, SDL's
  `offscreen` video driver (`SDL_VIDEODRIVER=offscreen`, EGL) may serve. Untested.
- **Layouts and ABI:** the SDL structs and the `usize`-for-offset trick hold on every 64-bit
  target (System V and Win64 alike); `check_layout` stops the program if a struct is off. 32-bit
  targets aren't supported (layouts, offsets as pointers, and Win32's `__stdcall` APIENTRY).
- **Threads:** none, which suits macOS's rule that events and windows belong to the main thread.
- **Audio:** queued audio works the same on every SDL backend (WASAPI, CoreAudio, PulseAudio or
  PipeWire).
