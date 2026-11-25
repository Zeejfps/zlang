# The compiler knowing nothing of std: what is left

The checker, lowering and runtime should never name a std declaration. Still naming std:
- [x] `c::String`'s C layout: a `?c::String` was a nullable pointer, an extern fn passed it as a
  `const char *`, and making one from a pointer was unchecked (`cstr_decl`). C's string is the
  language's `cstr` now, a `*u8` whose bytes a NUL ends, made from a pointer by `@cast`.
- [x] `c::symbol`, `c::callback` and `c::export` were attributes std declared (std/c.ctx) and the
  compiler acted on. They are the compiler's own now, `#c_symbol`, `#c_callback` and `#c_export`,
  beside `#convert` and `#write`.
- [ ] `build::sources` is an attribute std declares (std/build) that ctxc's driver reads on a
  build program's `fn build` before compiling it (spec §19, rule 12).
- [x] `main`'s `args` was checked against std's `Args`; it is checked as `[][]u8` now, as a start
  fn's and `test_main`'s are. std's `Args` is an alias of it.
- [ ] Only `fn build` may take std's `Build` (check.ctx, `std_decl_top{ .., name = "Build" }`).
- [ ] Tests: the checker names std's `Test` (no fn but a `test` fn and `test_main` may take one,
  and `@expect`/`@require` need it) and `test::Case` (the type a `case` fn returns), and checks
  that `test::check`, `test::require` and `test::stop` exist. Lowering calls `test::check`,
  `test::require`, `test::stop` and `test::write_callers` for `@expect` and `@require`.
- [ ] `io::Stderr`: an entry point or a `#test` fn that returns a `!` writes its error through
  std's `io::Stderr` (`exit_site`), as do `@expect` and `@require` when they fail.
- [ ] `@fmt`: a piece is wrapped in std's `fmt::Text`, `fmt::Int`, `fmt::Uint`, `fmt::F32` or
  `fmt::F64`, and a `utf8::String` argument is taken as text, as a string literal is.
- [x] `atomic::Order` was the order an `@atomic_*` builtin took, std's type. The order is the
  builtin's name now, `@atomic_load_acquire`, and one without a suffix is sequentially consistent.
- [ ] Tasks: the checker follows a task handle through std's `task::start`, `start_concurrent`,
  `start_blocking`, `wait`, `wait_for`, `cancel`, `end`, `wait_all` and `cancel_all`. Lowering
  ends a `task::Task` with `task::end` and a `task::Group` with `task::cancel_all`, and a program
  is threaded when main or the start fn takes std's `Threads`.
- [x] `list::List`: a `for` over a List said, in its error, to go over `list::items` instead. It
  says what a `for` over any struct does now.
