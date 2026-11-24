# ctxlang quick reference

Enough ctxlang to write code that compiles on the first or second try, without reading all of
[spec.md](spec.md) first. Each rule names its spec section (§11 is spec.md's section 11): read
that section when you reach an edge (the escape check, exclusivity, literal inference,
generics). [Common mistakes](#common-mistakes), at the end, lists what a first draft gets wrong,
with what to write instead. Code to imitate: std ([std/](../std)), [examples/](../examples), and the
test cases ([tests/cases/](../tests/cases)), each a program that compiles or names its error.

In this repository the compiler is `kotor/tools/ctxc`, which builds ctxc from its bootstrap when
needed; it is `ctxc` below.

## Shape of code

```ctx
namespace wav {                                       // a namespace may span files (§10)
    error truncated{ at: usize }                      // errors are values (§8, Errors)
    error not_wave

    struct Format { channels: u16, rate: u32, bits: u16 = 16 }       // `= 16`: a default (§7)
    union Chunk { format{ f: Format }, data{ bytes: []u8 }, other }  // tagged union (§8)
    enum Codec: u16 { pcm = 1, float = 3 }                           // integer enum (§12, Enums)

    // A function's whole input is its context: named fields, read-only unless `mut` (§2).
    fn u16_at { b: []u8, at: usize } -> !u16 {
        if at + 2 > b.len { return truncated{ at } }
        return @as(u16, b[at]) | (@as(u16, b[at + 1]) << 8)
    }

    fn read_format { b: []u8 } -> !Format {
        if b.len < 12 or b[0..4] != "RIFF" or b[8..12] != "WAVE" { return not_wave }
        let channels = try u16_at{ b, at = 22 }       // `try` passes an error up (§8, Errors)
        let lo = try u16_at{ b, at = 24 }
        let hi = try u16_at{ b, at = 26 }
        return Format{ channels, rate = @as(u32, lo) | (@as(u32, hi) << 16), .. }   // `..`: defaults
    }

    // Generic over the allocator's state S (§9): the caller picks the allocator.
    fn copy_bytes(S) { realloc: alloc::Fn(S), mut heap: S, b: []u8 } -> ![]mut u8 {
        let out = try alloc::make(u8, S){ realloc, &heap, count = b.len }
        slice::copy(u8){ dst = out, src = b }
        return out
    }
}

fn main { mut io: Io, mut mem: Mem } -> !i32 {        // capabilities come in through main (§15)
    let pages = mem::pages{ &mem, size = 65536 } ifnull { return 1 }
    let mut heap = arena::new{ buf = pages }
    let bytes: []u8 = "RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xAC\x00\x00"
    let f = try wav::read_format{ b = bytes }
    let copy = try wav::copy_bytes{ realloc = arena::alloc, &heap, b = bytes }
    _ = @fmt(&io, "{} channels at {} Hz, {} bits; {} bytes\n", f.channels, f.rate, f.bits, copy.len)
    return 0
}
```

## Calls (§3)

- **Calls name every field,** in any order: `wav::u16_at{ b = bytes, at = 22 }`. `x` alone means
  `x = x`; `&x` passes `x` to a `mut` field. A place's last name puns too: `&g.rng` is
  `rng = &g.rng` and `w.heap` is `heap = w.heap`, in calls, binds and literals (§3, rule 6).
  What doesn't end in a field's name (`xs[i]`, `p.*`, `f{}`, `a.n + 1`, `gl::LINEAR`) needs
  `name =`. A trailing `..` fills the rest from same-named locals (§3, rule 7).
- **Struct literals name every field** (§7), but a field may declare a default, and a literal
  ending in `..` takes the fields it leaves out from theirs: `Stats{ str = 10, .. }` for
  `struct Stats { str: i32, speed: f32 = 1.0, target: ?*T = null }`. Without `..` every field is
  named, defaults or not. A default is a const: numbers, bools, `null`, enum values, unions,
  strings, empty slices (`slice::empty(T){}`), consts, compile-time calls, and structs and
  arrays of those; not a pointer or a function. Give a new field a default where one makes
  sense, so the literals that end in `..` keep compiling. Attributes take `..` too.
- **`mut` fields** are pointers to the caller's place; inside, use them as values (§2, rule 6).
  Pass `&local` (needs `let mut local`). Two `&` of overlapping places in one call are allowed
  where the callee uses them apart (§3.1, rule 8): `free{ &w, d = &w.conversation.d }` is fine if
  `free` doesn't touch `w.conversation.d` through `w`. So pass a part as a `mut` field, not as a
  `*mut` pointer. The callee must be a named function with a body (not a function value or an
  extern fn), and the error says which access of the callee's, where, uses the part both ways.
- **Binding:** `f{ a = 1, _ }` is a bound function (`&fn`) of the fields left (§4, §6). A bound
  function beside a `&` of what it holds is an error (`tick{ &w, engine }` with `engine` bound to
  `&w`): bind where the function is called, in a call that isn't given the place,
  `run{ &vm, engine = call{ &w, _ } }`. A bind beside a `&` of what it doesn't hold is fine, if
  the callee leaves what it holds alone.
- **Argument order:** no argument may change a place that another argument of the same call
  reads or changes (§3, rule 10): `show{ n = s.n, z = bump{ &s } }` is an error. Compute one in a `let` first.
- **Big read-only arguments are passed by reference** (§14, rule 6): a struct, union or array
  over 32 bytes isn't copied, unless a `&` of the same local, or a later argument that calls a
  function, is in the same call. So a big read-only field is cheap.
- **Results must be used** (§11, rule 6): `_ = f{}` to discard. A bare call statement must
  return nothing.
- **No methods,** operator overloading or traits: `list::push{ list = &xs, item }`, not
  `xs.push`. A generic fn may use `==`, `@hash` and `<` (`<=`, `>`, `>=`) on values of its `T`,
  and every use of the fn must then give a type that has them (§9, rule 6): only numbers have
  an order. For another type the fn takes functions (`hash`, `eq`, `less`).
- **A keyword can't be a name** (§1, rule 4), and the error says which word it is: name the
  field `kind`, not `type`, and the local `found`, not `match`. `is`, `in`, `at`, `error`,
  `distinct` and `static` are keywords only in their own place, and names everywhere else.

## Types (§12)

`i8..i64 u8..u64 usize f32 f64 bool`, `*T`/`*mut T` (never null), `?T` (optional; `?*T` is a
nullable pointer), `[N]T` arrays (values, bounds-checked), `[]T`/`[]mut T` slices (`s.len`,
`s.ptr`, `s[a..b]`), `!T` (value or error), `strlit`, `fn{C} -> R`, `&fn{C} -> R` (bound
function: can't be stored in a struct or returned), `extern fn{C} -> R` (C function pointer),
`enum E: u8 { ... }` (always with its integer type), `type Meters = distinct f64` (§12, Distinct
types). Through a pointer, `p.x` is the field and `p.*` the value: no `->`, no `*p`.

- Integer `+ - * <<` panic on overflow (`a << n` is `a * 2^n`); use `+%`, `-%`, `*%` and
  `<<%` for hashes, CRCs and RNGs (`x ^ (x <<% 13)`: the bits shifted out are dropped; a count
  at or above the width still panics). `/` by zero panics (§11, Overflow).
- `~x` flips an integer's bits: `flags & ~VISIBLE` clears a flag.
- `e ifoverflow x` gives `x` where the integer arithmetic and `@as` or `@round` to an integer
  written in `e` overflow, for counts from a file: `count * 16 ifoverflow { return truncated }`.
  A call's arguments in `e` aren't covered.
- No implicit int→float or signed↔unsigned (§11, Widening): `@as(u32, n)` (to an integer:
  panics if the value doesn't fit), `@as(f32, x)` (to a float: never panics, rounds, and an
  `f64` too big for `f32` gives `inf`), `@trunc(u8, n)` (low bits), `@cast(*T, p)` for
  pointers. `@as(_, x)` takes the type from the context. A `bool` isn't a number:
  `if b { 1 } else { 0 }`.
- An index is any integer type (§12, Arrays): `a[i]` and `s[lo..hi]` take an `i32`, a `u8` or
  an `i64` as it is, and panic below 0 as past the end (`index -1 out of bounds for length 3`).
  Don't write `a[@as(usize, i)]`. An enum or a distinct type still converts with `@as`.
- A const's name converts to another integer type where its value fits (§11, Widening, rule 7):
  `param = gl::LINEAR` for an `i32` field, with `LINEAR` a `u32`. Not an expression of consts,
  and not a local.
- Only arrays and slices are indexed, and `[i]` is always bounds-checked. `q[i]` on a pointer is
  an error: the element without a check is `(q + i).*` (`(q + i).f` for a field), and
  `(s.ptr + i).*` skips a slice's check. Keep these to hot loops whose bounds are checked once.
- The **unchecked operations** (§13, Unchecked operations) are `@cast`, `@slice`, pointer
  arithmetic (`q + n`, so `(q + i).*` too), a `c::String` from a pointer, and declaring an
  `extern fn`, an `extern union`, a C variable or a `#c::callback` fn. A build can make them
  errors outside the directories it names (`build::deny_unchecked`, §19); the error names the
  checked form: `s[i]` and `a[lo..hi]`, `alloc::free` for one object from `alloc::new`, std's
  `math` for libm, a string literal for a `c::String`.
- `==` and `!=` compare structs, unions, arrays, slices (by contents: two `[]u8` with the same
  bytes are equal) and optionals of these, part by part, with nothing written; `@hash(x)` is a
  `u64` that equal values share (§13, Hashing). Not for a type with a pointer, a function or an
  extern union inside (the error names the field), and no `@hash` of a float.
  `map::make(K, V){ realloc, &heap }` keys a map by any type that has both; `map::new` takes
  `hash` and `eq`.
- `@min(a, b)`, `@max(a, b)` and `@clamp(x, lo, hi)` for integers and floats of one type after
  widening (a literal takes the other's type): never `if a < b { a } else { b }` by hand (§13,
  Smallest, largest and clamped). A NaN operand gives NaN; `@clamp` panics if `lo > hi`. For a
  type of your own, `cmp::min_by{ a, b, less }` and `max_by` take the order as a fn.
- Float to integer (§13, Rounding and saturating conversions): `@as(T, x)` rounds toward zero
  and panics out of range; `@round(T, x)` rounds to nearest (a half to even) and panics out of
  range; `@saturate(T, x)` and `@round_saturate(T, x)` clamp to `T`'s range instead (NaN is 0),
  for pixels and samples: `@round_saturate(i16, s * 32768.0)`. `@saturate` clamps an integer
  too: `@saturate(u8, v)`.
- Same bits, other type: `@trunc` between integers of one size (`@trunc(u32, -1)` is
  `0xFFFFFFFF`, where `@as` panics); `math::f32_from_bits`, `f32_to_bits` and the `f64` pair for
  floats.
- Integer literals take their type from use; float literals default to `f64` (§11, Literals).
  Hex `0x1F`, binary `0b101`, and `_` between digits (`1_000_000`). A float literal too big for
  its type is an error (`let y: f32 = 1e300`); infinities and NaNs are `math::INF`,
  `math::NAN`, `math::INF_F32` and `math::NAN_F32`.
- Structs, unions and arrays are values: assignment copies (§14, rule 5). `let mut x: T`
  zero-initialises if every field has a zero value; field defaults don't apply there, only in
  literals. Everything has one but pointers, functions and capabilities (so not a `list::List`
  or a `map::Map`, which hold pointers): an enum's is its variant 0, a union's its first variant
  (§11, Initialization).

## Control flow (§11)

<!-- context:
union Value { int{ v: i64 }, text{ s: []u8 }, none }
enum Kind: u8 { byte, char, word }
struct P { x: i32 }
error bad
fn parse { s: []u8 } -> !P {
    if s.len == 0 { return bad }
    return P{ x = 1 }
}
fn use { v: i64 } {}
fn load { s: []u8 } -> i64 { return 1 }
fn f {} {}
fn sample { a: bool, c: bool, n: usize, xs: []mut i32, value: Value, kind: Kind, r: Value, m: map::Map(u32, i32, arena::Arena), key: u32, s: []u8, mut words: list::List(u32, arena::Arena) } -> !?i32 {
    let mut i: usize = 0
    ...
    return v
}
fn main {} {}
-->
```ctx
let v = if a { 1 } else { 2 }                     // if/match are expressions too
for i in 0..n {}                                  // i = 0 .. n - 1, of n's type; lo..hi leaves hi out
for x in xs {}                                    // each element of a slice or an array, copied
for &x in xs { x = 0 }                            // each element's place: changes it, copies nothing
for x at i in xs {}                               // with its index (usize); `for &x at i` too
while i < n { i = i + 1 }                         // any other loop (`while true` for ever); `label:`, break/continue on both
match value { int{ v } => {} text{ s } => {} none => {} }      // exhaustive
match kind { byte | char => {} else => {} }                     // enums too
let name = match kind { byte => "byte", char => "char", else => return null }   // arms without braces
if r is int{ v } { use{ v } }                     // test one variant and bind (§8, Is)
let k = map::get{ m, key } ifnull { return null } // ?T: default or leave
let p = parse{ s } iferr err{ error } { return 1 }     // !T: handle the error
let ok{ value = d } = parse{ s } else err{ error } { return error }
defer list::free{ list = &words }                 // runs at block exit
defer if c { f{} }                                // any statement but let/return/break/continue
{ let tmp = load{ s }; use{ v = tmp } }           // a block of its own: a scope, with its defers
let x = try parse{ s }.x                          // (try parse{ s }).x
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
- Optionals narrow (§8, Optional): after `if p == null { return }`, `p` is the payload type
  (`let` locals only; copy a `let mut` first).
- Handlers (§11, Expressions, rule 7): `let v = f{} iferr { return } ifnull { return }` takes a
  `!?T` apart, its error first. Beside `==`, `<`, `is`, `and` or `or`, put the handler in
  parentheses, `x == (f{} ifnull y)` and `(m ifnull 0) > 3`, and after arithmetic too:
  `a + (f{} ifnull 0)`. The compiler's error shows the spelling.
- A long condition, like any expression, goes on to a next line that starts with `and`, `or`,
  a comparison, `is`, a handler, `.` or a binary operator: `if a{ x }` then `or b {`. Not
  with `-` or `&`, which could begin a statement: end the line before with those (§11, rule 3).
- Statements end at a newline or a `;`. Logic is `and`, `or`, `not`; there is no `? :`
  (an `if` is an expression), no `+=` or `++`, and no `loop`.

## Errors (§8, Errors)

`error name{ field: T }` declares one. A function returning `!T` infers its error set from
what it returns and `try`s; `try` needs a function that returns `!T` itself. `try! e` panics on
error (for out-of-memory and invariants).
`match r { ok{ value } => {} wav::truncated{ at } => {} err{ error } => {} }`. Short forms:
`_ = f{} iferr err{ error } { log{ error } }` (drop the value, handle the error, any `!T`),
`if f{} is ok`, `r is fs::not_found | fs::exists` (test, payloads bind as in a match), and
`return try f{}` in a function returning a bare `!`. Parsers return errors on bad data, never
panic.

A fallible function is a value of a function type whose `!T` has the same T (§5):
`let run: fn{ s: []u8 } -> !u64 = parse_number`, in a struct field, an array, a `?fn`, or an
argument. Calling through it fails with any error, so a `match` on the error needs `else`; its
errors keep their payloads (`parse::bad_digit{ at } => ...`). A local inferred from a function
(`let f = parse_number`) keeps the function's own set and takes no other function. A table of
them replaces a chain of calls:

<!-- context:
struct State { n: i32 }
namespace core { fn run { mut st: State, op: u16 } -> !bool { return op == 1 } }
namespace vars { fn run { mut st: State, op: u16 } -> !bool { return op == 2 } }
namespace bits { fn run { mut st: State, op: u16 } -> !bool { return op == 3 } }
fn main {} {}
-->
```ctx
type Step = fn{ mut st: State, op: u16 } -> !bool

fn dispatch { mut st: State, op: u16 } -> ! {
    let steps: [3]Step = [core::run, vars::run, bits::run]
    for step in steps { if try step{ &st, op } { return } }
}
```

`main` (and a build program's `build`) may return `!` or `!i32` and `try` its way out: an error
ends the program with exit code 1 after `error: wav::truncated{ at = 12 }` on standard error
(§15, Entry point, rule 4). An error in an `@fmt` hole prints the same way; a payload field
without a writer (a struct, a union, an enum, an optional, an array) prints from its parts,
`Point{ x = 1, y = 2 }`, `Kind::char`, `null`, `[1, 2]` (§13, Formatting, rule 10).

## Memory (§14; std alloc, arena, list, map)

<!-- context:
struct Point { x: i32, y: i32 }
fn memory { mut mem: Mem } -> ! {
    ...
}
fn main {} {}
-->
```ctx
let pages = mem::pages{ &mem, size = 1 << 20 } ifnull { return alloc::out_of_memory }
let mut heap = arena::new{ buf = pages }
let mut xs = list::new(u32){ realloc = arena::alloc, &heap }
try list::push{ list = &xs, item = 7 }                        // fails with alloc::out_of_memory
let items = list::items{ list = xs }                          // []mut u32 view
let owned = try list::take{ list = &xs }                      // []mut u32 that frees as one
let counts = try alloc::make(u32, arena::Arena){ realloc = arena::alloc, &heap, count = 64 }   // zeroed
let mut m = map::make([]u8, u32){ realloc = arena::alloc, &heap }
try map::put{ &m, key = "one", value = 1 }
let p = try alloc::new(Point, arena::Arena){ realloc = arena::alloc, &heap, value = Point{ x = 1, y = 2 } }
```

- An allocator is a function, `alloc::Fn(S)`, over state `S` the caller holds (§14, rule 3).
  std's is the arena; a general heap is a program's own `alloc::Fn` over C's `realloc`.
- Lists and maps keep a pointer to their allocator state: the state must outlive them.
- New memory is zero: every allocator hands out zeros past what a resize keeps, an arena after a
  `reset` or `restore` too.
- **Escape check** (§14, Escape check): you can't return or store the address of a local (or
  anything derived from it) where it outlives the local. Put long-lived data in heap memory and
  keep pointers to it.
- Arenas (`arena::new{ buf }`) for scratch, with `let m = arena::mark{ heap }` and
  `arena::restore{ &heap, to = m }` around each item; a heap for everything with a lifetime of
  its own. For a big arena's buffer, `mem::reserve{ &mem, size }` commits only what the arena
  reaches (Windows commits all of `mem::pages` at once); nothing but an arena may use it.
- There is no state at top level (§1, rule 2): what lives for the whole program is a local of
  `main`, passed down.

## Capabilities and C (§15, §18)

`main { mut io: Io, mut fs: Fs, mut mem: Mem, args: Args } -> i32` receives the capabilities;
pass them down to what needs them (`&fs`): a function that prints takes `mut io: Io`. Code
without capabilities is pure. C functions are `extern fn name { ... } -> R` with
`#c::symbol{ name = "..." }`. Each takes a capability field for what it touches, or is `#pure`
(it touches only its arguments and what they point to), or it is an error. std's `math` has
libm's functions, `#pure`; they are the only extern fns a const may call
(`const T: [8]f32 = make_table{}` with `math::cos` in `make_table`), and the const has the bits
the same call gives at run time. A program's own namespace of the same name (a `math` of its own) hides std's
whole (§10, rule 4).

## Printing and text

`io::println{ &io, s = "text" }`, `io::print_i64{ &io, n }`. `_ = @fmt(&io, "x = {} y = {}\n",
x, y)` (§13, Formatting) prints formatted text; `let mut err = io::to_stderr{ &io }`, then
`@fmt(&err, ...)`, goes to standard error. Into a `utf8::Builder`
(`utf8::builder{ realloc, &heap }`): `try @fmt(&b, ...)`, then `utf8::view{ b }`; `[]u8` holes
are written as text. Strings don't concatenate with `+`: build them so. A hole takes a spec
after a colon, `{:[<>^][0][width][.precision][x|X|b|o]}`: `{:<16}` and `{:>8}` pad a string or
a number to a width, `{:08x}` is hex with zeros, `{:.3}` a float with three digits after the
point; no wrapper type or writer for these. Floats print plainly where short (`100.0`, not
`1e+02`). A program's own `#write` fns for a type replace std's; a sink of its own takes specs
with writers of `fmt::Int`, `fmt::Uint`, `fmt::F64`, `fmt::F32` and `fmt::Text`
([std/fmt.ctx](../std/fmt.ctx)).

String literals convert to `[]u8`, `utf8::String` or `c::String` as the context expects; a
literal is read-only, so it is no `[]mut u8` (compare a `[]mut u8` with one after
`let s: []u8 = bytes`). A multi-line literal (GLSL) is lines that each start with `\\`, raw,
joined with `\n` (§11, Literals, rule 9):

<!-- context:
fn main {} {}
-->
```ctx
const MESH_VS: c::String =
    \\#version 410 core
    \\void main() { gl_Position = vec4(0.0); }
```

## Building and checking (§19, §21)

`ctxc run DIR -- ARGS` builds DIR's `build.ctx` program (or DIR's `.ctx` files, if it has none)
and runs it; `ctxc exe DIR -o OUT.exe` only builds. Big programs compile as parallel C units;
unchanged units are cached. A build program names its sources:

<!-- context:
// file: gffdump/build.ctx
...
// file: gffdump/main.ctx
fn main {} { _ = lib::answer{} }
// file: lib/lib.ctx
namespace lib { fn answer {} -> i32 { return 42 } }
-->
```ctx
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "gffdump", root = "." }   // this directory's own .ctx files
    build::add_sources{ &b, exe, dir = "../lib" }             // a directory and all below it
    build::link{ &b, exe, lib = "SDL2" }                      // a C library
    build::optimize{ &b, exe, level = 2 }                     // optional: -O2
}
```

**Check before you build.** `ctxc check DIR` reports every compile error, of each executable
and its `#test` fns, and builds nothing (§21). Its last line is `check: no errors` or
`check: N errors`, with the checks those errors still hold back: fix, and check until it says
`no errors`. An error about two places has the other as a note indented under it (where the
local is declared, the other argument). `--json` on `check`, `run`, `exe` and `test` writes each
error as a JSON object on a line of standard error (`file`, `line`, `column`, `end_line`,
`end_column`, `message`, `notes`), then a `summary` (§21, rules 8 to 11; §20, rule 15).

`ctxc check --fix DIR` makes the edits an error spells out exactly (`m = &movie` for a pun,
`_ = ` for an unused result, `..` for missing fields, `(q + i).*`, a missing `,`, `0..n`: §21,
rule 12), prints each, and checks again; `--fix --dry-run` only prints them. Errors with more
than one way out carry the choices in `--json`'s `fixes` (`"safe":false`), which `--fix` leaves.

A panic prints `file:line:col: panic: message`, and under it its call path, innermost first,
`  at wav::u16_at (wav.ctx:41:17)`, up to `main` or the test fn (§15, Call paths). Builds at
`-O0` and `-O1` and every `ctxc test` build keep the path; at `build::optimize{ level = 2 }` it
needs `build::trace_calls{ &b, exe, on = true }` (a few percent slower).

## Tests (§20)

A test is a fn beside the code it tests, in a file of its own (`wav_test.ctx` next to
`wav.ctx`):

<!-- context:
const HEADER: []u8 = "RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xAC\x00\x00"
namespace wav {
    error truncated{ at: usize }
    error not_wave
    struct Format { channels: u16, rate: u32, bits: u16 = 16 }
    fn u16_at { b: []u8, at: usize } -> !u16 {
        if at + 2 > b.len { return truncated{ at } }
        return @as(u16, b[at]) | (@as(u16, b[at + 1]) << 8)
    }
    fn read_format { b: []u8 } -> !Format {
        if b.len < 12 or b[0..4] != "RIFF" or b[8..12] != "WAVE" { return not_wave }
        let channels = try u16_at{ b, at = 22 }
        let lo = try u16_at{ b, at = 24 }
        let hi = try u16_at{ b, at = 26 }
        return Format{ channels, rate = @as(u32, lo) | (@as(u32, hi) << 16), .. }
    }
}
-->
```ctx
namespace wav_tests {
    #test
    fn a_short_header_is_truncated { mut t: Test, mut mem: Mem } -> ! {
        let pages = mem::pages{ &mem, size = 65536 } ifnull { return alloc::out_of_memory }
        let mut heap = arena::new{ buf = pages }
        let f = try wav::read_format{ b = HEADER }
        @require(&t, f.channels == 2)
        @expect(&t, f.rate == 44100)
        @expect(&t, wav::read_format{ b = HEADER[0..20] } is wav::truncated)
    }
}
```

- `ctxc test DIR` runs every `#test` fn of the program's files, its libraries' included;
  `ctxc test DIR wav` those whose names contain `wav`; `--list` lists them. `main` isn't run.
  A test takes `mut t: Test` and the capabilities it needs, as `main` does, and returns nothing
  or a `!`, so it can `try`.
- `@expect(&t, a == b)` checks and goes on; a failure is one line with both sides,
  `wav_test.ctx:40: fail: wav_tests::reads_the_rate: f.rate == 44100: 22050 == 44100`. Write the
  comparison inside it (`==`, `!=`, `<`, `<=`, `>`, `>=`) to get the values. `@require(&t, c)`
  ends the test there if `c` fails: put it before what needs `c`, as `@require(&t, rows.len > 0)`
  before `rows[0]`. Both are statements, with no value. After `@require(&t, row != null)` a
  `let row: ?Row` is its `Row`. No `defer` runs when `@require` ends a test.
- A test fails if it returns an error, panics, runs over 60 s, exits by itself or makes no
  check. `#test{ panics = "out of bounds" }` passes by panicking with that text.
- `test::skip{ &t, why = "..." }` ends a test as skipped where what it needs isn't on this
  machine (write `return` after it in an `ifnull` block: the checker doesn't know it never
  returns); `#test{ skip = "why" }` keeps one from running. Skips count in the summary, and fail
  the run only with `--no-skips`. Never filter tests with a `#test_main` of your own.
- A file a test reads lives beside it, found from `test::dir{ &t }`, the test's own directory
  (absolute, no `/` at the end): never a path from the repository's root. Data that isn't in the
  repository comes after `--` (`ctxc test DIR -- PATH`, read with `test::args{ &t }`), and the
  test skips without it; never from the environment or a hard-coded path.
- Pass `&t` down to helpers that check: a failure in one lists the calls that led to it
  (`  called from wav_tests::reads_rows (wav_test.ctx:31:5)`).
- Each test runs in its own process, several at once: don't rely on another test's state.

## Common mistakes

What a first draft gets wrong, from the agents' write-ups ([friction.md](todo/friction.md)) and from
habits of other languages.

From other languages. ctxc says what to write for each, in one error (§21, rule 7), and
`ctxc check --fix` writes the first eight; the rest need a choice it leaves to you:

| Written | Write |
|---|---|
| `!b`, `a && b`, `a \|\| b` | `not b`, `a and b`, `a or b` |
| `x += 1`, `x++` | `x = x + 1` |
| `c ? a : b` | `if c { a } else { b }` |
| `x as i32`, `(i32)x` | `@as(i32, x)` (§13) |
| `p->x`, `*p` | `p.x`, `p.*` (§12, Pointers) |
| `s.len()` | `s.len`, a field |
| `fn main()`, `fn add(a: i32)`, `fn two -> i32` | `fn main {}`, `fn add { a: i32 }`, `fn two {} -> i32` (§2) |
| `var x = 0`, `loop { }` | `let mut x = 0`, `while true { }` |
| `add(1, 2)`, `two()` | `add{ a = 1, b = 2 }`, `two{}`: a call names its fields (§3) |
| `Point(1, 2)` | `Point{ x = 1, y = 2 }` (§7) |
| `enum K { a, b }` | `enum K: u8 { a, b }`, or `union K { a, b }` if the values don't matter (§12, Enums) |
| `println("hi")` | `io::println{ &io, s = "hi" }`, with `mut io: Io` among the fn's fields (§15) |
| `xs.push(7)` | `list::push{ list = &xs, item = 7 }`: there are no methods |
| `io::println{ &io, ... }` where the fn has no `io` | add `mut io: Io` to the fn's fields and pass `&io` down (§15) |

Where ctxc's error doesn't name the fix yet:

| Written | ctxc says | Write |
|---|---|---|
| `P{ x: 1, y: 2 }` | expected '}', found ':' | `P{ x = 1, y = 2 }` |
| `K.a` for an enum's value | `K` is a type, not a value | `K::a` (§12, Enums) |
| `"a" + b` | `+` needs numbers | `@fmt` into a `utf8::Builder` |
| `string`, `str` | unknown type or namespace | `[]u8` or `utf8::String` |
| `let mut` at top level | expected a declaration | a local of `main`, passed down: no globals (§1, rule 2) |

ctxlang's own rules (the error says what to write, and `ctxc check --fix` writes the
first four):

| Written | Write |
|---|---|
| `bump{ &count }` for a field `n` | `bump{ n = &count }`: a pun needs the field's name (§3, rule 6) |
| `two{}` as a statement, `@fmt(&io, ...)` | `_ = two{}`, `_ = @fmt(&io, ...)` (§11, rule 6) |
| `for i in range(n)`, `for i in 0..=n` | `for i in 0..n`, `for i in 0..n + 1` (§11, For) |
| `q[i]` on a pointer | `(q + i).*`, unchecked; better, keep a slice (§12, Pointers) |
| `x == f{} ifnull 0` | `x == (f{} ifnull 0)` (§11, Expressions, rule 7) |
| `for i, x in xs` | `for x at i in xs` |
| a field or local named `type`, `match`, `fn` | `kind`, `found`, `f` (§1, rule 4) |
| `match c { 0 => ..., 1 => ... }` on an integer | add `else => ...` (§8, Match on integers) |
| `try f{}` in a fn that returns `i32` | return `!i32`, or `f{} iferr { ... }` (§8, Errors) |

Type errors, where the fix is a choice:

| Written | ctxc says | Write |
|---|---|---|
| `a + b` with a `u32` and an `i32`, `n * 2.0` with an `i32` | incompatible types: u32 and i32 | `@as(i32, a) + b`, `@as(f64, n) * 2.0` (§11, Widening) |
| `@as(i32, flag)` with a `bool` | @as converts numbers only | `if flag { 1 } else { 0 }` |
| `let x = f{}` then `x + 1`, `f` returning `!i32` or `?i32` | incompatible types: !i32 and {integer} | `try f{}`, `f{} iferr { ... }`, `f{} ifnull 0` (§8) |
| `next: *Node = null` | expected *Node, got null | `next: ?*Node` (§12) |
| `let n = 0` then `n = 1` or `&n` | cannot assign to `n`: it is read-only | `let mut n = 0` |
| `bump{ n = g{} }`, `bump{ n }` for a `mut n` | expected *mut i32, got i32 | `let mut v = g{}` then `bump{ n = &v }` (F#27) |
| `let mut bs = list::items{ list = xs }` then `bs = view` | expected []mut u8, got []u8 | `let mut bs: []u8 = ...`: say the read-only type (F#22) |
| `got == "hello"` with `got` a `[]mut u8` | a string literal is read-only | `let s: []u8 = got`, then `s == "hello"` (F#22) |
| `return a[..]` with `a` a local array | returned value holds the address of local `a` | allocate it (`alloc::make`) or have the caller pass the buffer (§14, Escape check) |
| `h = h * 16777619` in a hash | (compiles, then panics: integer overflow) | `h = h *% 16777619`: wrapping operators (§11, Overflow) |
| `while i < xs.len { ... }` without `i = i + 1` | (compiles, then hangs) | `for x in xs { ... }` (§11, For) |
