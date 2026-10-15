# Tooling gaps

What cost time around the port that isn't the language: the agents' shell, the engine's test
tools and the game's own framework. Language friction goes in
[ctxlang/FRICTION.md](../../ctxlang/FRICTION.md). Remove an entry once it's fixed.

- **The agents' shell refuses compound commands.** In a worktree-isolated agent, a command that
  mixes `cd`, `&&`, globs, heredocs, `;` chains or a variable in command position is "too complex
  to verify" or "cannot be shown not to be git": every repeated build or run needs a script file
  written with the Write tool. Two tool calls in one block run at once, so a build and a run of
  its output raced. Hit writing the HUD (3 times), the rules and the screens.
- **Shell and Python edits turn `\n` in a ctxlang string into a real newline** ("unterminated
  literal"), which looks like a language problem and isn't; use the Edit and Write tools. Python
  also writes CRLF. Hit writing the engine (5 times), dialogue (2), the screens (2) and
  the rules.
- **Testing the engine takes a program of its own.** No `--override DIR` on enginetest for a
  hand-assembled script, no `--call Routine(args)` (pushing arguments by hand is
  last-parameter-first, and three of the first calls were wrong), no tool for "which scripts call
  this routine", and a panic in `nwarg::param` names no routine. Hit writing the engine's
  routines (4 times).
- **The game's framework:** a panel's events don't reach the menu that opened it, a panel can't
  hide without closing, a menu under a conversation gets no clicks, `tools/ingame/go.sh` drops
  log lines that start with `[`, a routine moved between files needs the dispatcher and registry
  edited by hand, `--screenshot-at` with a `/c/Users/...` path fails with no path in the message,
  and `kotor/tools/savetest` lacks lib/rules. Hit writing the HUD (5) and the engine (2).
