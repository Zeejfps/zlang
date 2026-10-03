# Language friction: GUI and front end (`lib/gui`, `lib/frontend`, their tools)

Where ctxlang got in the way. Each entry: what we wanted, what we wrote instead, how often.

## movie player (`lib/frontend/movie`, `tools/movietest`)

- **A call's result derives from every read-only argument, so a stack buffer can't be a path.**
  `bink::open{ ..., path = buf[..] }` with `let mut buf: [1024]u8` makes the returned `Movie` "derived
  from `buf`" (the checker can't know `open` doesn't keep `path`), and `movie::open` could then not
  return its `Player`. Wrote the path into allocator memory instead (`movie_path`, `path::join`) and
  freed it with a `defer` after the open. Twice (movie file, binkw32.dll). A path-taking function
  that copies its path is indistinguishable from one that keeps it.
- **`&local` for a read-only pointer field poisons the callee's `try`.** `try play{ ..., tables =
  &tables }` (tables a local `Tables`, the field `*Tables`) failed with "`try` would return an error
  that may hold the address of local `tables`", because gpu's `shader_failed{ log }` makes any error
  set pointer-holding. Made the field a `mut` one (`&tables`: not counted) in `play`, and moved the
  audio device behind `alloc::new` for `adev`. Three call sites, two fixes; the same shape as the
  entry in video.md.
- **String literals in `if` branches and `let` have array types.** `let ext = if c { ".bik" } else { "" }`
  fails ("branches have different types: [4]u8 and [0]u8") and `let dir = "movies/"` then
  `slice::copy{ src = dir }` fails ("expected []u8, got [7]u8"). Annotated `: []u8` (3 times); a
  literal bound to a plain `let` would be friendlier as a `[]u8`.
- **`@fmt` of a `c::String` needs a writer per program** (`sdl::last_error`): copied rendertest's
  `put_cstring` namespace into movietest (second tool to do so; belongs in tools/common/out.ctx).

## lib/frontend/gui3d and tools/gui3dview

- **`&name` is shorthand only for a plain local, and only for a field of that name.** The callees'
  `mut` fields are called `heap`, `cache`, `player`, `s`, so `alloc::resize{ ..., &keep }`,
  `mdl_cache::get{ &fs, &models }` and `advance{ &scene.player }` all failed ("has no field `keep`",
  "expected '}', found '.'"). Wrote `heap = &heap` (renamed my parameter), `cache = &models`,
  `player = &scene.player`, `s = &em.rng`: about 25 sites in the first compile, one pass to fix.
  The messages are clear; it only costs when the caller's local has a different name than the
  callee's field, which the std/lib naming makes common.
- **String literals of different lengths in `if` branches** (`if c { "menu3d" } else { opts.model }`:
  "branches have different types: [7]u8 and [9]u8"); annotated `let prefix: []u8 = ...`. Twice.
- **`try gpu::submit{ &dev, frame = &frame }` with `frame` a local of the function** is "`try` would
  return an error that may hold the address of local `frame`" (the entry in render.md). Moved the
  picture-taking into `shoot { mut frame: ... }`, where `frame` is a `mut` parameter and the same call
  compiles. Once.
- No other trouble: the library (about 500 lines, `try`, `ifnull`, slices of `mut` structs,
  `&scene.emitting[i]` as a `mut` argument) compiled and ran at the second attempt.

## lib/gui and lib/frontend (the GUI lead)

About 5,000 lines of ctxlang; it compiled in a handful of passes. What cost something:

- **No bitwise not.** Clearing a flag is `f & ~F_X` in C; there is no `~`. Wrote
  `clear_bits{ f, bits }` as `f & (4294967295 ^ bits)` and used it 8 times.
- **A struct literal must name every field, and a struct is zero-initialised only if every field has a
  zero value** (no enums, pointers, functions, lists). `Control` (about 90 fields) is built with
  `let mut c: Control` and field assignments, which works because its kind is a `u8` constant and its
  rows a slice with a count, not a `list::List`. The price: `K_*` constants and `kind == K_LIST` chains
  instead of an enum and `match`; and `Event` (an enum field) can't be a zero array element, so the
  event queue is a `list::List` that is cleared instead of a `[N]Event`. Once each decided the design.
- **`ifnull`/`iferr` bind tighter than comparison**, so `x == f{} ifnull y` reads as `x == (f{} ifnull y)`;
  `a != null and b` needs care too. Always put the `ifnull` call in a `let` first. Twice.
- **`is` is a keyword**, so `let is = gff::get_struct{...}` (an "image struct") is a syntax error with
  an unhelpful message ("expected a name, found 'is'"). Once.
- **The escape check follows every read-only argument into the result.** `font::load{ name = buf[..] }`
  with a local `buf` made the returned font "hold" `buf` (declare `buf` before the local that receives
  it); a `try` whose error "may hold the address of local `pb`" because `pb` was a path buffer (kept the
  path in the owning struct instead, `Front.saves_dir`). Three sites.
- **`fs::list` returns `[][]u8`, read-only**, so its outer slice can't be passed back to
  `alloc::resize(..., count = 0)` (`*T` doesn't convert to `*mut T`); the front end leaks that one small
  allocation per Load Game opening. A `list_free` beside `list` would fix it.
- **`&p.*` doesn't parse**; for a `mut` field and a `*mut T` local, pass the pointer itself
  (`movie::skip{ p }`). The error was "expected '}', found '.'". Four sites.
- **Everything takes `mut g: Gui`**, even readers, because a read-only `Gui` argument is copied (6 KB).
  Harmless, but every call site then writes `&g` and every function needs `mut`.
- **String literals as array values**: `let pre = "gui_mp_"` is a `[7]u8`, so `slice::copy{ src = pre }`
  fails; annotated `: []u8` six times (the same entry as the other leads').
