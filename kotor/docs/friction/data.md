# Language friction: the data layer (lib/base, lib/res, lib/formats, the data tools)

What ctxlang made awkward while writing the resource manager, the format readers and their corpus
tools. Each entry: what we wanted to write, what we wrote instead, how often. Counts are from
lib/base, lib/res, lib/formats and tools/{resls,gffdump,fmtcheck,fmttest,basetest} (about 7,600
lines). Remove an entry when a language change fixes it, and say which commit did.

## The escape check and calls

- **A call's result counts as derived from its read-only arguments, so memory a callee allocates
  can't be returned if an argument was a view of a stack buffer.** `find_in{ dir, name =
  concat{ a = stem, b = ".mod", into = buf[..] } }` returns a path from the heap, but passing
  `buf[..]` makes the result "hold the address of local `buf`", and `return p` is an error. The
  same with `fs::read_all{ path = p }` where `p` was joined into a stack buffer, and
  `path::join{ name = buf[..n] }`. Written instead: the temporary name or path is allocated from
  the heap and freed after (res::read, res::find_archive, res::voice_path, res::stream_file,
  corpus). 5 places. A way for a function to say its result doesn't come from an argument (or
  inference that an allocator's result never does) would fix it.
- **Freeing needs `[]mut`, and there's no way back from `*T`.** `@cast(*mut U, q)` refuses a `*T`,
  so a slice that will be freed must be `[]mut` from the allocation to the free: 2DA tables, KEY
  arrays, ERF/RIM member lists, Source fields, `twoda::Table` all hold `[]mut` fields only so
  `free` can hand them back, though nothing writes through them. 8 struct fields, 6 return types.

## Errors and cleanup

- **No error-path cleanup (`errdefer`).** Partial construction that must be undone on failure is
  written `let mut ok = false; defer { if not ok { cleanup } } ... ok = true` (res::open,
  mount_dir, mount_key, mount_module, gff::parse, gffw::finish, corpus::list_dir, pth::read):
  9 times. An `errdefer` or `defer if err` would remove the flag.
- **`is` can't test a `!T`.** `if fs::size{ &fs, path } is ok { ... }` is an error; written
  `let is_file = match fs::size{ ... } { ok => { true } err => { false } }`. 5 times.
- **Discarding a failing value-returning call is long.** `_ = gffw::add_value{ ... } iferr {}` is an
  error ("this branch must end in a value"); written `iferr { return }` or `iferr 0`. 24 times in
  fmttest alone.
- **`return try f{}` in a function returning a bare `!`** is "expression has no value"; written
  `try f{}` then `return`. 1 time.

## Calls and places

- **Punning `&x` needs the field to be called `x`.** Passing `&heap.mem` or `&fi` to fields named
  `mem` and `out` needs `mem = &heap.mem`, `out = &fi`. Very common (about 40 calls), cheap each
  time, but the first compile of every file trips on it.
- **`e iferr { ... } ifnull { ... }` groups right to left**, so `f{} iferr { return } ifnull
  { return }` on a `!?T` parses as `f{} iferr ({ return } ifnull ...)`; written as two
  statements or with parentheses around the left side. 3 times (lib/formats small readers).
- **A `let mut` optional doesn't narrow.** gffdump's lazily opened `let mut rm: ?res::Manager`
  needed `match rm { some{ value } => ... }` to get the manager out. 2 times.
- **Enums compare only for equality.** Keeping sources sorted by class needed
  `@as(u8, items[j - 1].class) >= @as(u8, s.class)`. 1 time.

## The standard library

- **A list handed out as a slice can't be freed as one.** `list::items` is the first `len` of a
  `cap`-sized allocation; freeing that slice gives the allocator the wrong size (heap::Heap's live
  count drifts). Every list that becomes a returned slice is first resized to its length
  (`alloc::resize(T, S){ mem = out.items, count = out.len }` in erf, gffw, twoda, list_type, and
  `lists::take` in lib/base, which the resource manager and the lyt, vis and txi readers use,
  after three copies of it had been written): 14 times. std's `list` could have `take`.
- **std's float writer prints 100.0 as `1e+02`**, which reads badly in tool output (the TXI
  check's font sizes).
- **`fs::list`'s result can't be freed.** It is two allocations whose name block's start isn't
  kept, so a caller with a general-purpose allocator leaks it. The data layer lists directories
  with `os::dir_open`/`dir_next` directly (res::find_in, mount_dir, corpus::list_dir). 3 places.
- **No `fs::seek`/`read_at`.** Added to std in its own commit (c0b8b45), with a test.
- **No `@fmt` to standard output** (kotor/FRICTION.md has it): the data tools share
  `kotor/tools/common/out.ctx`, writers over `Io` for every hole type they print, a ResRef and a
  corpus::Copy. And an `if` of two literals still can't be a hole (`let late: []u8 = if ...`):
  1 time.
- **No bit casts.** f32/f64/i32/i64 from their bits go through a local and a pointer cast,
  `let b = bits; return @cast(*f32, &b).*` (lib/base/le.ctx, once for each pair).

## Multi-line conditions

- A condition that continues on the next line must break after `or`, not before it: a call's `}`
  at the end of a line starts the block. 1 time (corpus.ctx), caught by the compiler with a clear
  enough error.
