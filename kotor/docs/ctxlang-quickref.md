# ctxlang quick reference for game code

Enough ctxlang to write KOTOR code without reading all of `ctxlang/spec.md` first. When something
here is unclear or you hit an edge (escape check, exclusivity, literal inference, generics),
read that spec section; section numbers are given. Real code to imitate: `kotor/lib/formats/`,
`kotor/lib/res/`, `kotor/lib/mdl/`, `kotor/tools/resls/main.ctx`.

## Shape of code

```
namespace gff {                                   // namespaces may span files (§10)
    error truncated{ at: usize }                  // errors are values (§8 Errors)
    error bad_type{ kind: u32 }

    struct Field { label: []u8, kind: u32, value: u64 = 0 }   // `= 0`: a default (§7)
    union Value { int{ v: i64 }, text{ s: []u8 }, none }      // tagged union (§8)
    enum Kind: u32 { byte, char, word = 2 }                    // integer enum (§12)

    // A function's whole input is its context: named fields, read-only unless `mut`.
    fn field_count { doc: Doc } -> usize { return doc.fields.len }

    fn parse(S) { realloc: alloc::Fn(S), mut heap: S, bytes: []u8 } -> !Doc {   // generic over S (§9)
        let n = try le::u32{ b = bytes, at = 8 }   // `try` passes an error up (§8)
        ...
    }
}
```

- **Calls name every field:** `gff::parse{ realloc, &heap, bytes = data }`. `x` alone means
  `x = x`; `&x` passes `x` to a `mut` field (§3). A place's last name puns too: `&g.rng` is
  `rng = &g.rng` and `w.heap` is `heap = w.heap`, in calls, binds and literals. What doesn't end
  in a field's name (`xs[i]`, `p.*`, `f{}`, `a.n + 1`, `gl::LINEAR`) needs `name =`. Order
  doesn't matter. A trailing `..` fills the rest from same-named locals (in a struct literal it
  means defaults instead, below).
- **Struct literals name every field** (§7), but a field may declare a default and a literal
  ending in `..` takes the fields it leaves out from theirs: `Stats{ str = 10, .. }` for
  `struct Stats { str: i32, speed: f32 = 1.0, class: Class = Class::soldier, target: ?*T = null }`.
  Without `..` every field is named, defaults or not. A default is a const: numbers, bools,
  `null`, enum values, unions, strings, empty slices (`slice::empty(T){}`), consts, compile-time
  calls, and structs and arrays of those; not a pointer or a function. Give a new field a default
  where one makes sense, so the literals that end in `..` keep compiling. Attributes take `..` too.
  Don't write a `no_x{}` helper that spells out constants: give the fields those defaults and
  write `X{ .. }`.
- **`mut` fields** are pointers to the caller's place; inside, use them as values. Pass `&local`
  (needs `let mut local`). Two `&` of overlapping places in one call are allowed where the
  callee uses them apart (§3.1, rule 8): `free{ &w, d = &w.conversation.d }` is fine because
  `free` doesn't touch `w.conversation.d` through `w`. So pass a part as a `mut` field, not as a
  `*mut` pointer. The callee must be a named function with a body (not a function value or an
  extern fn), and the error says which access of the callee's, where, uses the part both ways.
- **A bound function beside a `&` of what it holds is an error** (`tick{ &w, engine }` with
  `engine` bound to `&w`). Bind where the function is called, in a call that isn't given the
  place: `nwvm::run{ &vm, program, self, engine = routines::call{ &w, _ } }`, as `scripts::run`
  does; don't pass a bound function down beside what it holds. A bind beside a `&` of what it
  doesn't hold is fine, if the callee leaves what it holds alone.
- **Big read-only arguments are passed by reference** (§14.6): a struct, union or array over
  32 bytes isn't copied, unless a `&` of the same local, or a later argument that calls a
  function, is in the same call. So a read-only `mixer: Mixer` field is cheap.
- **Results must be used:** `_ = f{}` to discard. A bare call statement must return nothing.
- **No methods:** `list::push{ list = &xs, item }`, not `xs.push`. No operator overloading,
  no traits; a generic `T` can't be compared or hashed unless you pass functions for it.

## Types (§12)

`i8..i64 u8..u64 usize f32 f64 bool`, `*T`/`*mut T` (never null), `?T` (optional; `?*T` is a
nullable pointer), `[N]T` arrays (values, bounds-checked), `[]T`/`[]mut T` slices (`s.len`,
`s.ptr`, `s[a..b]`), `!T` (value or error), `strlit`, `fn{C} -> R`, `&fn{C} -> R` (bound
function: can't be stored in a struct or returned), `extern fn{C} -> R` (C function pointer).

- Integer `+ - * <<` panic on overflow (`a << n` is `a * 2^n`); use `+%`, `-%`, `*%` and
  `@wrap_shl` for hashes, CRCs and RNGs. `/` by zero panics.
- `~x` flips an integer's bits: `flags & ~F_VISIBLE` clears a flag.
- `e ifoverflow x` gives x where the integer arithmetic and `@as` to an integer written in e
  overflow, for counts from a file: `count * 16 ifoverflow { return truncated }`. A call's
  arguments in e aren't covered.
- No implicit int→float or signed↔unsigned (but for an index and a const's name, below):
  `@as(u32, n)` (to an integer: panics if the value
  doesn't fit), `@as(f32, x)` (to a float: never panics, rounds, and an `f64` too big for `f32`
  gives `inf`), `@trunc(u8, n)` (low bits), `@cast(*T, p)` for pointers. `@as(_, x)` takes the
  type from the context.
- An index is any integer type: `a[i]` and `s[lo..hi]` take an `i32`, a `u8` or an `i64` as it
  is, and panic below 0 as past the end (`index -1 out of bounds for length 3`). Don't write
  `a[@as(usize, i)]`. An enum or a distinct type still converts with `@as`.
- A const's name converts to another integer type where its value fits: `param = gl::LINEAR`
  for an `i32` field, `x == gl::LINEAR` for an `i32` `x`, with `LINEAR` a `u32`. Not an
  expression of consts, and not a local.
- Only arrays and slices are indexed, and `[i]` is always bounds-checked. `q[i]` on a pointer is
  an error: the element without a check is `(q + i).*` (`(q + i).f` for a field), and
  `(s.ptr + i).*` skips a slice's check. Keep these to hot loops whose bounds are checked once.
- The **unchecked operations** (spec §13) are `@cast`, `@slice`, pointer arithmetic (`q + n`, so
  `(q + i).*` too), a `c::String` from a pointer, and declaring an `extern fn`, an
  `extern union`, a C variable or a `#c::callback` fn. The game's build makes them compile
  errors (`build::deny_unchecked` in kotor/build.ctx) outside the directories its `except`
  lists, each with its reason: lib/platform, lib/render_gl, lib/base, lib/script, lib/video
  and lib/audio. Elsewhere write the checked form the error names:
  `s[i]` and `a[lo..hi]`, `alloc::free` for one object from `alloc::new`, `math::` (lib/base) for
  libm, a string literal for a `c::String`; or call a function of one of those directories.
  Calling an extern fn or using a slice that such a directory made is allowed everywhere. Add a
  directory to `except` only with its reason on its line. The tools (kotor/tools/*) don't deny
  them.
- Same bits, other type: `@trunc` between integers of one size (`@trunc(u32, -1)` is
  `0xFFFFFFFF`, where `@as` panics); `math::f32_from_bits`, `f32_to_bits` and the `f64` pair for floats.
- Integer literals take their type from use; float literals default to `f64`. Hex `0x1F`. A
  float literal too big for its type is an error (`let y: f32 = 1e300`); `@as(f32, 1e300)` is
  `inf`.
- Structs/unions/arrays are values: assignment copies. `let mut x: T` zero-initialises if
  every field has a zero value; field defaults don't apply there, only in literals. Everything
  has one but pointers, functions and capabilities (so not a `list::List` or a `map::Map`,
  which hold pointers): an enum's is its variant 0, a union's its first variant (§11).

## Control flow (§11)

```
let v = if a { 1 } else { 2 }                     // if/match are expressions too
for i in 0..n { }                                 // i = 0 .. n - 1, of n's type; lo..hi leaves hi out
for x in xs { }                                   // each element of a slice or an array, copied
for &x in xs { x = 0 }                            // each element's place: changes it, copies nothing
for x at i in xs { }                              // with its index (usize); `for &x at i` too
while i < n { i = i + 1 }                         // any other loop; `label:`, break/continue on both
match value { int{ v } => { ... } text{ s } => { ... } none => {} }      // exhaustive
match kind { byte | char => { ... } else => { ... } }                     // enums too
if r is int{ v } { use{ v } }                     // test one variant and bind (§8 Is)
let n = map::get{ m, key } ifnull { return null } // ?T: default or leave
let x = parse{ ... } iferr err{ error } { return 1 }   // !T: handle the error
let ok{ value = d } = r else err{ error } { return error }
defer list::free{ list = &xs }                    // runs at block exit
```

- **Write a `for`, not a counter** (§11, For): a `while` that forgets `i = i + 1` hangs. The
  range's bounds and the slice are read once, before the loop. `i`, `x` and the index can't be
  assigned. A range never counts down (`5..2` is empty), `lo..=hi` is an error (`lo..hi + 1`),
  and two names are spelled `for x at i in xs`, never `for i, x`. Go over a list with
  `for x in list::items{ list = xs }`; if the body grows the list, count instead:
  `for i in 0..xs.len`. `for _ in 0..n` repeats.
- `match` takes integers (§8, Match on integers): literals, folded consts (`gl::TRIANGLES`) and
  ranges `'a'..='z'` (both ends included), joined with `|`; `else` is required. `c is '0'..='9'`
  tests one.
- Optionals narrow: after `if p == null { return }`, `p` is the payload type (`let` locals only;
  copy a `let mut` first).
- Handlers (§11, Expressions, rule 7): `let v = f{} iferr { return } ifnull { return }` takes a
  `!?T` apart, its error first. Beside `==`, `<`, `is`, `and` or `or`, put the handler in
  parentheses, `x == (f{} ifnull y)` and `(m ifnull 0) > 3`, and after arithmetic too:
  `a + (f{} ifnull 0)`. The compiler's error shows the spelling.
- A long condition, like any expression, goes on to a next line that starts with `and`, `or`,
  a comparison, `is`, a handler, `.` or a binary operator: `if a{ x }` then `or b {`. Not
  with `-` or `&`, which could begin a statement: end the line before with those (§11, rule 3).

## Errors (§8 Errors)

`error name{ field: T }` declares one. A function returning `!T` infers its error set from
what it returns and `try`s. `try! e` panics on error (for out-of-memory and invariants).
`match r { ok{ value } => {} gff::truncated{ at } => {} err{ error } => {} }`. Short forms:
`_ = f{} iferr err{ error } { log{ error } }` (drop the value, handle the error, any `!T`),
`if f{} is ok`, `r is fs::not_found | fs::exists` (test, payloads bind as in a match), and
`return try f{}` in a function returning a bare `!`. Parsers return
errors on bad data, never panic. A fallible function is a value of a function type whose `!T` has
the same T (§5): `let run: fn{ s: []u8 } -> !u64 = parse_number`, in a struct field, an array, a
`?fn`, or an argument. Calling through it fails with any error, so a `match` on the error needs
`else`; its errors keep their payloads (`parse::bad_digit{ at } => ...`). A local inferred from a
function (`let f = parse_number`) keeps the function's own set and takes no other function.
```
// before: a chain of direct calls
if try rt_core::run{ &w, &vm, routine, argc } { return true }
if try rt_vars::run{ &w, &vm, routine, argc } { return true }
// after: function values (lib/engine/routines/dispatch.ctx)
type Category = fn{ mut w: world::World, mut vm: nwvm::Vm, routine: u16, argc: u8 } -> !bool
let all: [21]Category = [rt_core::run, rt_vars::run, ...]
if try all[i]{ &w, &vm, routine, argc } { w.routes[r] = all[i] }
```

## Memory (§14, std alloc/list/map/arena)

```
let mut h = heap::new{ &mem }                                    // kotor/lib/base: malloc-backed
let mut xs = list::new(u32){ realloc = heap::alloc, heap = &h }
try list::push{ list = &xs, item = 7 }                           // fails with alloc::out_of_memory
let items = list::items{ list = xs }                             // []u32 view
let owned = try list::take{ list = &xs }                         // []mut u32 that frees as one
let counts = try alloc::make(u32, heap::Heap){ realloc = heap::alloc, heap = &h, count = 64 }   // zeroed
let mut m = map::new(resref::ResRef, u32){ realloc = heap::alloc, heap = &h, hash = resref::hash, eq = resref::eq }
let p = try alloc::new(Thing, heap::Heap){ realloc = heap::alloc, heap = &h, value = Thing{ ... } }
```

- Lists and maps keep a pointer to their allocator state: the state must outlive them.
- New memory is zero: every allocator hands out zeros past what a resize keeps, an arena after a
  `reset` or `restore` too.
- **Escape check:** you can't return or store the address of a local (or anything derived from
  it) where it outlives the local. Put long-lived data in heap memory and keep pointers to it.
- Arenas (`arena::new{ buf }`) for scratch, with `let m = arena::mark{ heap }` and
  `arena::restore{ &heap, to = m }` around each item; the heap for everything with a lifetime. For a big
  arena's buffer, `mem::reserve{ &mem, size }` commits only what the arena reaches (Windows
  commits all of `mem::pages` at once); nothing but an arena may use it.

## Capabilities and C (§15, §18)

`main { mut io: Io, mut fs: Fs, mut mem: Mem, args: Args } -> i32` receives the capabilities;
pass them down to what needs them (`&fs`). Code without capabilities is pure. C functions are
`extern fn name { ... } -> R` with `#c::symbol{ name = "..." }`. Each takes a capability field
for what it touches, or is `#pure` (it touches only its arguments and what they point to), or it
is an error. libm functions are in `kotor/lib/base/math.ctx`, `#pure`. SDL is `kotor/lib/platform/sdl.ctx`; only `lib/render_gl` touches GL.

## Printing and text

`io::println{ &io, s = "text" }`, `io::print_i64{ &io, n }`. `_ = @fmt(&io, "x = {} y = {}\n",
x, y)` (§13) prints formatted text; `let mut err = io::to_stderr{ &io }`, then `@fmt(&err, ...)`,
goes to standard error. Into a `utf8::Builder`: `try @fmt(&b, ...)`, then `utf8::view{ b }`;
`[]u8` holes are written as text. A tool's own `#write` fns for a type replace std's. String
literals convert to `[]u8`, `utf8::String` or `c::String` as the context expects. A multi-line
literal (GLSL) is lines that each start with `\\`, raw, joined with `\n` (§11, Literals, rule 9):

```
const MESH_VS: c::String =
    \\#version 410 core
    \\void main() { gl_Position = vec4(0.0); }
```

## Building and checking

`kotor/tools/ctxc run DIR -- ARGS` builds DIR's `build.ctx` program and runs it (see AGENTS.md
for the template). Big programs compile as parallel C units; unchanged units are cached.
Compile errors name `file:line:col`. Keep tool output short (`| tail`, `| grep`).
