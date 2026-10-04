# Language friction: rendering (math, render, render_gl, tex, rendertest)

Where ctxlang got in the way while writing the render seam and the GL backend. Each entry: what
we wanted, what we wrote instead, how often. See also kotor/FRICTION.md (the spike's list, which
this extends).

- **An error that may hold a pointer poisons `try` on calls given a local's address.** The
  escape check takes a call's result, its error included, as derived from every read-only
  argument; once any error in the program carries a slice (`gpu::shader_failed{ log: []u8 }`),
  `try f{ vertex = &local_array }` is "try would return an error that may hold the address of
  local". Hit three times: linking shaders from const arrays copied to locals (rewritten as
  `try_link`, which returns 0 and a log length through a `mut` field instead of an error),
  passing a stack array of fonts down (moved to arena memory), and lib/material's loader, where
  a texture's name came from `resref::bytes{ r = &key }` of a local key (the caller's own name
  slice is passed down beside the key instead). The errors never held those addresses; a
  per-error-set analysis of which payloads can come from which arguments would let these
  through.
- **GLSL without multi-line literals** (as in the spike): 8 shaders, about 320 lines of
  `"...\n",` elements, with array lengths kept right by a throwaway script after each edit.
- **No float bit cast.** Sorting transparent draws by depth wants an f32's bits as a u32:
  written `@cast(*u32, &dist).*` through a local; lib/tex reads the TPC header's float the same
  way (`@cast(*f32, &bits).*`). A `@bits(u32, x)` builtin (and back) would say it.
- **`is` is a keyword**, so a natural helper name (`fonttxi::is{ a, b }` for a keyword match)
  was a parse error far from its cause: "expected an expression, found 'is'". Renamed
  `same_word`.
- **Writers by exact type**: `tools/common/out.ctx` has no `c::String` writer, and error
  payloads with `c::String` (gl, sdl, gpu errors) need one to print with `@fmt`; rendertest
  declares its own one-function namespace for it.
- **Big structs by value.** `gpu::Device` (tables are slices, but still ~1 KB of fields) is passed
  as `mut dev` everywhere, which is a pointer, fine; read-only `dev: Device` fields copy or not
  at the compiler's choice. No friction yet, noted because a `[4096]u8` log inside it was moved
  to a slice to be safe.
- **`try f{}.x`** parses as `try (f{}.x)`, against the spec's own example; lib/tex wrote
  `(try f{}).x` (once).
- **No integer min/max in std**: written as `if a < b { a } else { b }` about six times in
  lib/tex alone (math has f32 ones).
- **Array literals of slices need their type**: `let names: [3][]u8 = ["a", "bb", "ccc"]`
  (literals of different lengths are otherwise arrays of different types): about five times.
- **No arena mark/restore**: lib/tex's corpus tool sets `work.used` back by hand (once);
  lib/material resets its scratch arena per texture, which works because nothing outlives one.
- **`defer if c { ... }`** is a parse error: `defer` takes a call, an assignment, a discard or a
  block, so it is `defer { if c { ... } }` (once).
- **`@fmt` to standard output** still needs a writer namespace per tool for types
  tools/common/out.ctx lacks (`c::String`); the texture sub-agent copied glspike's 14 writers
  before tools/common existed.
