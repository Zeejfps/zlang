# Generator: what is missing

What build programs that generate code (spec §19) still need, found while asking whether one could
derive JSON serialization. For JSON, 1 and 5 are the ones that matter; 2, 4, 6 and 7 are small, and
3 only matters for renaming enum values. Separately, JSON needs a real library for the generated
code to call: `examples/json` is a sample program, not a library.

- [ ] **1. Types are text.** `build::declarations` gives a field's type as a string
  (`"?game::Pos"`), so a generator can't tell what it names: a struct, an enum, or an alias of
  something else. lib/ecs_gen (on the `ecs` branch) looks names up itself in text.ctx and matches
  types by spelling. *Build:* `declarations` resolves names itself (from the declaration's
  namespace outward, through `type` aliases, as spec §10 says) and gives a structured type: a
  named one with its full path and arguments, a slice (and whether it's `mut`), an array, an
  optional, a pointer, a fn. It keeps the written text beside it, and marks a name that resolves
  to nothing, such as a type a generator writes.
- [ ] **2. std's types aren't seen.** An alias of `utf8::String` or `list::List` isn't seen
  through, since `declarations` reads only the executable's files. *Build:* `declarations` reads
  std's declarations too, for 1 to resolve into.
- [ ] **3. Variants have no attributes.** An enum's or a union's variants can't carry one, so
  there is no `#json::rename` on a variant. *Build:* attributes on variants in the parser and the
  checker, and `attrs` on `build::Variant`.
- [ ] **4. Fields have no position.** `build::Field` has no line or column, so an error about a
  field can only point at its declaration. *Build:* `line` and `col` on `build::Field`.
- [ ] **5. A generator can't report errors.** It prints `FILE:LINE:COL: error: ...` to stderr
  and fails the build by returning 1, which ctxc and tools/toolchain.py treat as a crash.
  *Build:* `build::error{ &b, file, line, col, msg }`, which ctxc reports as its own errors, and
  then fails the build.
- [ ] **6. A generator can't live inside its library.** `add_sources` takes every
  subdirectory, so a generator in `lib/json/gen` would be compiled into every executable that
  adds `lib/json`, and those can't build it. *Build:* `add_sources{ ..., deep = false }`, or a
  rule that a directory a build program takes with `#build::sources` is no executable's.
- [ ] **7. A generator can't add the library its code calls.** Only build.ctx's `fn build` names
  directories, with paths relative to build.ctx, so every build.ctx must add `lib/json` itself
  beside the generator. *Build:* a way for a generator library to add its own directories to an
  executable, by paths relative to the library.
- [ ] **8. `@fmt` doubles every brace.** Generated ctxlang is full of `{` and `}`, so formats
  that write it are full of `{{` and `}}`: lib/ecs_gen has 58 in 24 of its 40 formats. *Build:* a
  string literal or format that writes code without doubling them. Convenience, not a blocker.
