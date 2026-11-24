# Compile-time consts and literal conversions: what is left

- **Consts and converted literals in a program with errors.** Both run only in a program without
  errors, so their errors come after the others', and the language server would miss them.
  - *Tried:* marking the declaration that holds each error, and having lowering refuse to enter a
    marked one. Not enough: the checker stays quiet about anything that involves the error type,
    so a declaration with no error of its own can still hold types without a layout from another's
    signature. A const that only calls a clean fn crashed lowering (`lower: a type that isn't
    concrete`, `a struct without a layout`), and lowering has about 45 panics that assume checked
    code.
  - *Direction:* the checker decides, so lowering only ever sees clean code. While it checks a
    declaration, it records what that declaration depends on: each name use, each recorded type,
    inferred error sets, the conversions its literals use, and the writers its `@fmt`s use. A
    declaration is blocked if it holds an error, if a type it records contains the error type, or
    if something it depends on is blocked. At `evaluate`, a const or literal whose root or
    conversion is blocked is skipped, with no error of its own. `lower::alone` keeps a cheap check
    that treats meeting a blocked declaration as a bug.
  - *The risk* is completeness: the dependencies must cover everything lowering can reach, or the
    crashes come back. It needs its own design pass, with the recovery test running consts in
    damaged programs.
- Array lengths, enum values and attributes take only folded consts, since they are needed while
  declarations are resolved. Checking bodies on demand would lift this; nothing has needed it yet.
  For the same reason an attribute can't hold a converted literal.
- No extern fn runs while compiling but the C library's math functions (eval.ctx, `libm`). Float
  formatting and parsing are ctxc's own runtime's, so ctxc could call its copies too.
- `intlit` (a number literal, as its digits, for a big-integer type) and `arraylit` (an array
  literal's elements, for a list) follow `strlit` when something needs them; neither is designed.
- Each literal's conversion runs in a fresh interpreter, which costs ctxc's own build about 30 ms
  of its 450. A machine kept per conversion, between runs, would save most of it.
