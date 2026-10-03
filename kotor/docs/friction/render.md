# Language friction: rendering (math, render, render_gl, tex, rendertest)

Where ctxlang got in the way while writing the render seam and the GL backend. Each entry: what
we wanted, what we wrote instead, how often. See also kotor/FRICTION.md (the spike's list, which
this extends).

- **An error that may hold a pointer poisons `try` on calls given a local's address.** The
  escape check takes a call's result, its error included, as derived from every read-only
  argument; once any error in the program carries a slice (`gpu::shader_failed{ log: []u8 }`),
  `try f{ vertex = &local_array }` is "try would return an error that may hold the address of
  local". Hit twice: linking shaders from const arrays copied to locals (rewritten as
  `try_link`, which returns 0 and a log length through a `mut` field instead of an error), and
  passing a stack array of fonts down (moved to arena memory). The error never held that
  address; a per-error-set analysis of which payloads can come from which arguments would let
  these through.
- **GLSL without multi-line literals** (as in the spike): 8 shaders, about 320 lines of
  `"...\n",` elements, with array lengths kept right by a throwaway script after each edit.
- **No float bit cast.** Sorting transparent draws by depth wants an f32's bits as a u32:
  written `@cast(*u32, &dist).*` through a local. A `@bits(u32, x)` builtin (and back) would say
  it.
- **A function with an inferred error set can't be a function value** (spec §8 rule 12), so the
  backend contract (lib/render/contract.ctx) can't be a table of function types; it is a never
  called function that calls each `gpu` function with typed `let`s. It works, but it checks
  "callable like this", not the exact signature.
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
