# Language friction from the KOTOR port

Points where ctxlang got in the way while writing the game. Each entry: what you wanted to write,
what you wrote instead, how often it comes up, and which subsystem hit it. Entries are evidence
for language changes (`ctxlang/FRICTION.md` and `ctxlang/PLAN.md` hold the language's own list).
Remove an entry once a language change fixes it, and say which commit did.

## Platform and GL spike (`kotor/tools/glspike`)

Counts are from the spike's sources (sdl.ctx, gl.ctx, png.ctx, main.ctx, about 2,650 lines).

- **No multi-line string literal, and no way to join literals.** GLSL source wanted to be one
  literal per shader. Written instead as `const MESH_VS: [17]c::String = [ "#version 410 core\n",
  ... ]`, one element per line, passed to `glShaderSource` as `count` strings. The length is
  counted by hand (a wrong count is caught: `expected [18]c::String, got [17]c::String`), and a
  const isn't a place, so each array is copied to a local (`let mesh_vs = MESH_VS`) to take
  `&mesh_vs`. 4 shaders, 54 lines here; the GL backend will have dozens. A raw or multi-line
  literal, or `[_]T` for a const's length, would do.
- **An `if` of literals as an `@fmt` hole** (ctxlang FRICTION #11): `@fmt(&io, "{}", if on {
  "on" } else { "absent" })` is "branches have different types: [2]u8 and [6]u8". Each needed a
  typed `let s: []u8 = if ...` first: 5 times in main.ctx.

- **Every `@fmt` onto the console needs `_ =`** even though its writers can't fail (35 times in
  the spike). std's `io` now has the writers onto an `Io` (and `io::to_stderr`) that the spike
  wrote itself in `namespace out`, and `utf8::push_bytes` writes bytes into a Builder.
- **A GL function is written three times.** Each is a capability field with its C type, then
  `name = @cast(_, try proc{ get_proc, name = "glName" })` in the loader, where the C name is the
  field's in another case: 132 loader lines for 132 fields. An attribute on a capability field
  (`#c::symbol{ name = "glClear" }`) plus a builtin or std loader that fills a capability from a
  lookup function by its fields' symbols would make a binding one line per function. (Stage 3
  reflection could do it in a build program instead.)
- **Typed integer consts need `@as` where C converts.** GL passes the same enum values as GLenum
  (`u32`) and GLint (`i32`): `tex_parameteri{ ..., param = @as(i32, gl::LINEAR) }`,
  `internal_format = @as(i32, gl::RGBA8)`, 11 times. A const whose value fits the target could
  convert as a literal does.
- **An out-pointer makes the result "derived from" the local.** `SDL_GetKeyboardState{ &sdl,
  numkeys = &n }` with `numkeys: ?*mut i32` returns SDL's static array, but the escape check
  (spec §14) takes the result as derived from every read-only argument: "returned value holds the
  address of local `n`". Declared `mut numkeys: i32` instead, whose arguments don't count, giving
  up passing null. The rule is right for a C function that returns into its argument (`strchr`);
  bindings just have to use `mut` fields for out-parameters.
- **No `@offset_of`.** A binding's structs can be checked against C's only by size
  (`sdl::check_layout` compares `@size_of`/`@align_of` with SDL's); a field out of place inside
  a struct of the right size goes unseen. The offsets were checked with a C program against
  SDL's headers instead, and a real resize event from SDL is read back at run time.
- **No pointer from an integer.** GL takes buffer offsets as `const void *`
  (`glVertexAttribPointer`, `glDrawElements`). Nothing makes a pointer from a `usize`, so the
  binding declares those parameters `offset: usize`, which works because 64-bit ABIs pass the two
  alike. Fine for 64-bit targets only; noted in docs/design/platform.md.

- **Spec gap, not friction:** hex literals (`0x2FFF0000`) and `_` separators work (the lexer has
  them) but spec §11 Literals doesn't mention them.
