# The compiler knowing nothing of std: what is left

The checker, lowering and runtime should never name a std declaration. Still naming std:
- [ ] `c::String`'s C layout: a `?c::String` is a nullable pointer, and an extern fn passes it as a
  `const char *` (`cstr_decl`).
- [x] `c::symbol`, `c::callback` and `c::export` were attributes std declared (std/c.ctx) and the
  compiler acted on. They are the compiler's own now, `#c_symbol`, `#c_callback` and `#c_export`,
  beside `#convert` and `#write`.
- [ ] `build::sources` is an attribute std declares (std/build) that ctxc's driver reads on a
  build program's `fn build` before compiling it (spec §19, rule 12).
- [ ] `main`'s `args` is checked against std's `Args` (check.ctx, `std_type{ .., name = "Args" }`);
  it can be checked as `[][]u8`. Only `fn build` may take std's `Build`.
- [ ] Tests: the checker names std's `Test` (no fn but a `test` fn and `test_main` may take one,
  and `@expect`/`@require` need it) and `test::Case` (the type a `case` fn returns), and checks
  that `test::check`, `test::require` and `test::stop` exist. Lowering calls `test::check`,
  `test::require`, `test::stop` and `test::write_callers` for `@expect` and `@require`.
- [ ] `io::Stderr`: an entry point or a `#test` fn that returns a `!` writes its error through
  std's `io::Stderr` (`exit_site`), as do `@expect` and `@require` when they fail.
- [ ] `@fmt`: a piece is wrapped in std's `fmt::Text`, `fmt::Int`, `fmt::Uint`, `fmt::F32` or
  `fmt::F64`, and a `utf8::String` argument is taken as text, as a string literal is.
- [ ] `atomic::Order`: the order an `@atomic_*` builtin takes is std's type.
- [ ] Tasks: the checker follows a task handle through std's `task::start`, `start_concurrent`,
  `start_blocking`, `wait`, `wait_for`, `cancel`, `end`, `wait_all` and `cancel_all`. Lowering
  ends a `task::Task` with `task::end` and a `task::Group` with `task::cancel_all`, and a program
  is threaded when main or the start fn takes std's `Threads`.
- [ ] `list::List`: a `for` over a List says, in its error, to go over `list::items` instead.
