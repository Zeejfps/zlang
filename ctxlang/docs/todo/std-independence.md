# The compiler knowing nothing of std: what is left

The checker, lowering and runtime should never name a std declaration. Still naming std:
- `c::String`'s C layout: a `?c::String` is a nullable pointer, and an extern fn passes it as a
  `const char *` (`cstr_decl`).
- `c::symbol` and `c::callback` are attributes std declares (std/c.ctx) and the compiler acts on.
  They move beside `#convert` and `#write`, among the attributes the compiler declares itself.
- `main`'s `args` is checked against std's `Args` (check.ctx, `std_type{ .., name = "Args" }`);
  it can be checked as `[][]u8`. Only `fn build` may take std's `Build`.
