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

    struct Field { label: []u8, kind: u32, value: u64 }
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
  `x = x`; `&x` passes `x` to a `mut` field (§3). Order doesn't matter. A trailing `..` fills
  the rest from same-named locals.
- **`mut` fields** are pointers to the caller's place; inside, use them as values. Pass `&local`
  (needs `let mut local`). Two `&` of overlapping places in one call is an error (§3.1).
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

- Integer `+ - *` panic on overflow; use `@wrap_add/sub/mul` for hashes and CRCs. Shifts never
  overflow. `/` by zero panics.
- No implicit int→float or signed↔unsigned: `@as(f32, n)` (checked), `@trunc(u8, n)` (low
  bits), `@cast(*T, p)` for pointers. `@as(_, x)` takes the type from the context.
- Integer literals take their type from use; float literals default to `f64`. Hex `0x1F`.
- Structs/unions/arrays are values: assignment copies. `let mut x: T` zero-initialises if
  every field has a zero value.

## Control flow (§11)

```
let v = if a { 1 } else { 2 }                     // if/match are expressions too
while i < n { i = i + 1 }                         // the only loop; `label: while`, break/continue
match value { int{ v } => { ... } text{ s } => { ... } none => {} }      // exhaustive
match kind { byte | char => { ... } else => { ... } }                     // enums too
if r is int{ v } { use{ v } }                     // test one variant and bind (§8 Is)
let n = map::get{ m, key } ifnull { return null } // ?T: default or leave
let x = parse{ ... } iferr err{ error } { return 1 }   // !T: handle the error
let ok{ value = d } = r else err{ error } { return error }
defer list::free{ list = &xs }                    // runs at block exit
```

- `match` does **not** take integers yet: use `if` chains (or an enum via `@as(E, n)`, which
  panics on unknown values).
- Optionals narrow: after `if p == null { return }`, `p` is the payload type (`let` locals only;
  copy a `let mut` first).
- A `{` after an expression in a condition is a call only if the line continues after its `}`.
  Break long conditions after an operator, not after a call's `}`.

## Errors (§8 Errors)

`error name{ field: T }` declares one. A function returning `!T` infers its error set from
what it returns and `try`s. `try! e` panics on error (for out-of-memory and invariants).
`match r { ok{ value } => {} gff::truncated{ at } => {} err{ error } => {} }`. Parsers return
errors on bad data, never panic. A function whose error set is inferred **can't be used as a
function value**, so dispatch tables of fallible functions don't work: dispatch with a chain of
direct calls.

## Memory (§14, std alloc/list/map/arena)

```
let mut h = heap::new{ &mem }                                    // kotor/lib/base: malloc-backed
let mut xs = list::new(u32){ realloc = heap::alloc, heap = &h }
try list::push{ list = &xs, item = 7 }                           // fails with alloc::out_of_memory
let items = list::items{ list = xs }                             // []u32 view
let mut m = map::new(resref::ResRef, u32){ realloc = heap::alloc, heap = &h, hash = resref::hash, eq = resref::eq }
let p = try alloc::new(Thing, heap::Heap){ realloc = heap::alloc, heap = &h, value = Thing{ ... } }
```

- Lists and maps keep a pointer to their allocator state: the state must outlive them.
- **Escape check:** you can't return or store the address of a local (or anything derived from
  it) where it outlives the local. Put long-lived data in heap memory and keep pointers to it.
- Arenas (`arena::new{ buf }`) for scratch; the heap for everything with a lifetime.

## Capabilities and C (§15, §18)

`main { mut io: Io, mut fs: Fs, mut mem: Mem, args: Args } -> i32` receives the capabilities;
pass them down to what needs them (`&fs`). Code without capabilities is pure. C functions are
`extern fn name { ... } -> R` with `#c::symbol{ name = "..." }`; libm functions are in
`kotor/lib/base/math.ctx`. SDL is `kotor/lib/platform/sdl.ctx`; only `lib/render_gl` touches GL.

## Printing and text

`io::println{ &io, s = "text" }`, `io::print_i64{ &io, n }`. Formatted text goes into a
`utf8::Builder` with `@fmt(&b, "x = {} y = {}", x, y)` (§13), then `io::println{ &io, s =
utf8::view{ b } }`. See existing tools for a small `@fmt`-to-stdout helper. String literals
convert to `[]u8`, `utf8::String` or `c::String` as the context expects.

## Building and checking

`kotor/tools/ctxc run DIR -- ARGS` builds DIR's `build.ctx` program and runs it (see AGENTS.md
for the template). Big programs compile as parallel C units; unchanged units are cached.
Compile errors name `file:line:col`. Keep tool output short (`| tail`, `| grep`).
