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
  no traits. A generic fn may use `==`, `@hash` and `<` (`<=`, `>`, `>=`) on values of its `T`,
  and every use of the fn must then give a type that has them (§9, rule 6): only numbers have
  an order. For another type the fn takes functions (`hash`, `eq`, `less`).
- **A keyword can't be a name** (§1, rule 4), and the error says which word it is: name the
  field `kind`, not `type`, and the local `found`, not `match`. `is`, `in`, `at`, `error`,
  `distinct` and `static` are keywords only in their own place, and names everywhere else.

## Types (§12)

`i8..i64 u8..u64 usize f32 f64 bool`, `*T`/`*mut T` (never null), `?T` (optional; `?*T` is a
nullable pointer), `[N]T` arrays (values, bounds-checked), `[]T`/`[]mut T` slices (`s.len`,
`s.ptr`, `s[a..b]`), `!T` (value or error), `strlit`, `fn{C} -> R`, `&fn{C} -> R` (bound
function: can't be stored in a struct or returned), `extern fn{C} -> R` (C function pointer).

- Integer `+ - * <<` panic on overflow (`a << n` is `a * 2^n`); use `+%`, `-%`, `*%` and
  `<<%` for hashes, CRCs and RNGs (`x ^ (x <<% 13)`: the bits shifted out are dropped; a count
  at or above the width still panics). `/` by zero panics.
- `~x` flips an integer's bits: `flags & ~F_VISIBLE` clears a flag.
- `e ifoverflow x` gives x where the integer arithmetic and `@as` or `@round` to an integer written in e
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
- `==` and `!=` compare structs, unions, arrays, slices (by contents: two `[]u8` with the same
  bytes are equal) and optionals of these, part by part, with nothing written; `@hash(x)` is a
  `u64` that equal values share. Not for a type with a pointer, a function or an extern union
  inside (the error names the field), and no `@hash` of a float. `map::make(Key, V){ realloc =
  arena::alloc, &heap }` keys a map by any type that has both; `map::new` takes `hash` and `eq`.
- `@min(a, b)`, `@max(a, b)` and `@clamp(x, lo, hi)` for integers and floats of one type after
  widening (a literal takes the other's type): never `if a < b { a } else { b }` by hand. A NaN
  operand gives NaN; `@clamp` panics if `lo > hi`. For a type of your own, `cmp::min_by{ a, b,
  less }` and `max_by` (std/cmp.ctx) take the order as a fn. (`math::min`, `max` and `clamp` in
  lib/base are KOTOR's own f32 fns, which give the second operand for a NaN: use them for f32
  game math as before.)
- Float to integer: `@as(T, x)` rounds toward zero and panics out of range; `@round(T, x)`
  rounds to nearest (a half to even) and panics out of range; `@saturate(T, x)` and
  `@round_saturate(T, x)` clamp to `T`'s range instead (NaN is 0), for pixels and samples:
  `@round_saturate(i16, s * 32768.0)`. `@saturate` clamps an integer too: `@saturate(u8, v)`.
- Same bits, other type: `@trunc` between integers of one size (`@trunc(u32, -1)` is
  `0xFFFFFFFF`, where `@as` panics); `math::f32_from_bits`, `f32_to_bits` and the `f64` pair for floats.
- Integer literals take their type from use; float literals default to `f64`. Hex `0x1F`. A
  float literal too big for its type is an error (`let y: f32 = 1e300`). std's infinities and
  NaNs are `math::INF`, `math::NAN`, `math::INF_F32` and `math::NAN_F32`; game code, whose own
  `math` hides std's, writes `@as(f32, 1e300)` for `inf`.
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
let s = match kind { byte => "byte", char => "char", else => return null }   // arms without braces
if r is int{ v } { use{ v } }                     // test one variant and bind (§8 Is)
let n = map::get{ m, key } ifnull { return null } // ?T: default or leave
let x = parse{ ... } iferr err{ error } { return 1 }   // !T: handle the error
let ok{ value = d } = r else err{ error } { return error }
defer list::free{ list = &xs }                    // runs at block exit
defer if c { f{} }                                // any statement but let/return/break/continue
{ let tmp = load{ ... }; use{ tmp } }             // a block of its own: a scope, with its defers
let x = try parse{ ... }.x                        // (try parse{ ... }).x
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
`main` (and a build program's `build`) may return `!` or `!i32` and `try` its way out: an error
ends the program with exit code 1 after `error: gff::truncated{ at = 12 }` on standard error
(§15, Entry point, rule 4). An error in an `@fmt` hole prints the same way; a payload field
without a writer (a struct, a union, an enum, an optional, an array) prints from its parts,
`Point{ x = 1, y = 2 }`, `Kind::char`, `null`, `[1, 2]` (§13, Formatting, rule 10).
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
is an error. libm functions are in `kotor/lib/base/math.ctx`, `#pure` (std's `math` has them all, but the game's `math` namespace hides it); they are the only extern fns a const may call (`const T: [8]f32 = make_table{}` with `math::cos` in `make_table`), and the const has the bits the same call gives at run time. SDL is `kotor/lib/platform/sdl.ctx`; only `lib/render_gl` touches GL.

## Printing and text

`io::println{ &io, s = "text" }`, `io::print_i64{ &io, n }`. `_ = @fmt(&io, "x = {} y = {}\n",
x, y)` (§13) prints formatted text; `let mut err = io::to_stderr{ &io }`, then `@fmt(&err, ...)`,
goes to standard error. Into a `utf8::Builder`: `try @fmt(&b, ...)`, then `utf8::view{ b }`;
`[]u8` holes are written as text. A hole takes a spec after a colon,
`{:[<>^][0][width][.precision][x|X|b|o]}`: `{:<16}` and `{:>8}` pad a string or a number to a
width, `{:08x}` is hex with zeros, `{:.3}` a float with three digits after the point; no wrapper
type or writer for these. Floats print plainly where short (`100.0`, not `1e+02`). A tool's own
`#write` fns for a type replace std's; a sink of its own takes specs with writers of
`fmt::Int`, `fmt::Uint`, `fmt::F64`, `fmt::F32` and `fmt::Text` (std/fmt.ctx shows them). String
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

`kotor/tools/ctxc check DIR` reports every compile error and builds nothing (spec §21): each
executable of the `build.ctx`, the `#test` fns included, all the errors rather than the first
100. The last line is `check: no errors` or `check: N errors`, and names the checks that the
errors shown hold back (the order of a call's fields, what tasks borrow, consts computed by
running code): fix, and check again until it says `no errors`.

An error about two places has the other one as a note, indented under it
(`  file:line:col: note: ...`): where the local is declared, the other argument, the earlier
declaration. `--json` on `check`, `run`, `exe` and `test` writes one JSON object for each
error on a line of standard error (`file`, `line`, `column`, `end_line`, `end_column`,
`message`, `notes`), then a `summary` record; `ctxc test DIR --json` writes a record for
each test and one for the run on standard output (spec §21, rules 8 to 11; §20, rule 15).

A panic prints its line as before, `file:line:col: panic: message`, and under it its call path
(spec §15, Call paths), innermost first: `  at nwarg::param (lib/script/nwarg.ctx:41:17)`,
then `  at routines::get_tag (...)` for the function that called it, at the call, up to `main`
or the test fn. Read it from the top: the first line is where it broke, the next ones how it
got there. A long recursion shows its first 16 and last 8 frames; `  at C code (no position)`
is a C library calling back; a task on a worker ends with `  started at ...`. Programs at
`-O0` and `-O1` and every `ctxc test` build keep the path; one with `build::optimize{ level = 2
}` prints only the first line, the function the panic is in, unless its build.ctx says
`build::trace_calls{ &b, exe, on = true }` (a few percent slower: for tools that test, not for
the game or the decoders' timing tools).

`kotor/tools/ctxc check --fix DIR` makes the edits an error spells out exactly (`m = &movie`
for a pun, `_ = ` for an unused result, `..` for missing fields, `(q + i).*`, a missing `,`,
`0..n`, and others: spec §21, rule 12), prints each with the line before and after, and
checks again; `--fix --dry-run` only prints them. Errors with more than one way to go on
keep their message and carry the alternatives as suggestions in `--json` (`fixes` with
`"safe":false`), which `--fix` doesn't apply.

## Tests (§20)

A test is a fn beside the code it tests, in a file of its own (`twoda_test.ctx` next to
`twoda.ctx`), not a tool with a `Tally`:

```
namespace twoda_tests {
    #test
    fn a_short_row_takes_the_default { mut t: Test, mut mem: Mem } -> ! {
        let pages = mem::pages{ &mem, size = 1048576 } ifnull { return alloc::out_of_memory }
        let mut heap = arena::new{ buf = pages }
        let table = try twoda::parse{ data = TEXT, realloc = arena::alloc, &heap }
        @require(&t, table.columns.len == 3)
        @expect(&t, table.columns[1] == "value")
        @expect(&t, twoda::get_string{ t = table, row = 2, column = "hex" } == "7")
    }
}
```

- `kotor/tools/ctxc test kotor/tools/fmttest` runs every `#test` fn of that tool's files, its
  libraries' included; `... test kotor/tools/fmttest twoda` those whose names contain `twoda`;
  `--list` lists them. The program's `main` isn't run. Exit code 1 if a test failed or none ran.
- A test takes `mut t: Test` and the capabilities it needs (`mut fs: Fs`, `mut mem: Mem`), as
  `main` does, and returns nothing or a `!`, so it can `try`.
- `@expect(&t, a == b)` checks and goes on. A failure is one line with both sides:
  `lib/formats/twoda_test.ctx:40: fail: twoda_tests::a_text_tables_cells: twoda::get_string{ ... } == "8": 7 == 8`.
  Write the comparison inside the `@expect` (`==`, `!=`, `<`, `<=`, `>`, `>=`) to get the values:
  a struct, an enum, an optional and a slice print too. `x == null` and `r is ok` work as
  conditions.
- `@require(&t, c)` is the same check, and the test ends there if `c` doesn't hold: use it
  where the next lines need what was checked, as `@require(&t, rows.len > 0)` before `rows[0]`,
  which would otherwise panic. Its line says so:
  `...: fail: twoda_tests::a_text_table_has_its_columns_and_rows: required: table.columns.len == 3: 2 == 3`,
  after the test's earlier failures. It is a statement, with no value (don't write
  `if not @expect(&t, c) { return }`). After `@require(&t, row != null)` a `let row: ?Row` is its
  `Row`. It works in a helper that holds the `Test` too. No `defer` runs when it ends the test.
- The summary's last number is the checks the tests made, every `@expect` and `@require`
  evaluated: a tool that printed `49 checks, 0 failed` keeps its count as `#test` fns. A test
  that panics or times out adds none of its own.
- A test that returns an error, panics, runs over 60 s, exits by itself or makes no check fails.
  `#test{ panics = "out of bounds" }` passes by panicking with that text.
- `test::skip{ &t, why = "no game install" }` ends the test there as skipped, when it finds
  that what it needs isn't on this machine; `#test{ skip = "why" }` on a test keeps it from
  running at all. Each prints `FILE:LINE: skip: NAME: WHY` and is counted in the summary
  (`tests: 5 run, 4 passed, 0 failed, 1 skipped, 0 not selected, 31 checks`); the exit code stays 0, or
  1 with `--no-skips`. `skip` never returns, but the checker doesn't know: in an `ifnull`
  block write `return` after it. Never filter tests out with a `#test_main` of your own.
- A file a test reads is kept beside the test, and found with `test::dir{ &t }`, the absolute
  path of the directory of the test's own `.ctx` file (no `/` at its end), so the test runs
  from any working directory: `try @fmt(&path, "{}/rows.2da", test::dir{ &t })` into a
  `utf8::builder`, then `fs::read_all{ ..., path = utf8::view{ b = path }.bytes }`. Never a
  path from the repository's root. A helper in another file gets the calling test's directory.
- Pass `&t` down to helpers that check (`fn same_rows { mut t: Test, a: Table, b: Table }`).
  A check that fails in a helper has the calls that led to it under its line,
  `  called from twoda_tests::reads_rows (lib/formats/twoda_test.ctx:31:5)`, up to the test fn,
  so one helper called for several cases says which call it was; a test's panic has its path
  the same way (`  at ...`). In `--json` they are the failure's `called_from` and `path`.
- Each test runs in its own process, several at once: don't rely on another test's files or
  state.
- A test that needs the game install takes its directory as an argument and skips without it:
  `kotor/tools/ctxc test kotor/tools/fmttest -- F:/Steam/steamapps/common/swkotor` gives every
  test what follows the `--`, and the test starts with
  `let args = test::args{ &t }` and
  `if args.len == 0 { test::skip{ &t, why = "no game install: give its directory after --" } }`,
  then reads `args[0]`. Filters and options (`-v`, `--list`, `--no-skips`) come before the
  `--`. Don't hard-code the install's path in a test, and don't read it from the environment.
