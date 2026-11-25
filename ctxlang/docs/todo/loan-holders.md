# Loan holders: what is left

A value that holds borrows until a call ends them is a language feature now (spec §15, Tasks,
rules 3, 4, 6 and 7; §14, Escape check, rule 9; §13's table), with std's `task::Task(R)` and
`task::Group` its first users. The compiler names none of std's task fns: `#loan_holder` marks
the holders, `x: T into h` lends into one, `mut h: H ends` ends its loans, and `#scope_end` marks
the fn a holder's scope end calls.

Built as designed, but for one simplification: a written `into` a holder, or `ends`, is always an
unchecked declaration, not only where the body doesn't bear it out. A fn whose body does is left
to rule 10's inferred summary, which needs nothing written.

Open:
- **Names.** `#loan_holder`, `ends` and `#scope_end` were placeholders in the design and are
  what the spec says now; they can still change.
- **Explicit ends instead of `#scope_end`.** A holder that may still hold a loan where its scope
  ends could be an error, so code writes `defer task::end{ &threads, task = &t }` itself: more
  explicit, no hook, every task-starting function a line longer.
- **Messages.** A loan's errors still say a place "is held by the task started at ... until it is
  waited for or cancelled", which is std's words for a Task; for a holder of a program's own
  (tests/cases/TaskLanguage/own_holder.ctx) "until its holder is ended" would be more exact.
- **Other holders.** Asynchronous I/O that borrows a buffer until it completes (an overlapped
  `ReadFile`, an io_uring read) is the next user the design had in mind:
  `fn read_async { mut io: Io, mut op: Pending, buf: []mut u8 into op }`.
