# KOTOR in ctxlang: guide for agents

Every agent working on this project reads this file first, then [PLAN.md](PLAN.md) for where its
task sits.

## The goal

A from-scratch reimplementation of *Star Wars: Knights of the Old Republic* (2003, BioWare's
Odyssey engine), written in **ctxlang**, that runs the original game's data from a purchased
install. The target is the whole game: GUIs, d20 rules and combat, dialogue, scripting, party,
saves, minigames, music and movies.

- Game install (**read-only, never write to it**): `F:\Steam\steamapps\common\swkotor`
  (`chitin.key`, `data/*.bif`, `modules/*.rim|*.mod`, `lips/`, `TexturePacks/*.erf`,
  `streammusic/`, `streamsounds/`, `streamwaves/`, `movies/*.bik`, `dialog.tlk`, `Override/`,
  `swkotor.exe`).
- Repository: `G:\Dev\zlang` (git), branch `kotor`. The game lives in `kotor/`, the language in
  `ctxlang/`.

## Rules

1. **Language.** Everything the game runs is ctxlang. Start with ctxlang's
   [quick reference](../ctxlang/docs/quickref.md), then "ctxlang in this game" below and the
   existing code in `kotor/lib/`; read `ctxlang/docs/spec.md` sections when you need the exact rule
   (the quick reference names them), and `ctxlang/std/*.ctx` for std's APIs. The compiler is young: when it gets in your way, log it in [ctxlang/docs/todo/friction.md](../ctxlang/docs/todo/friction.md)
   (what you wrote, what you had to write instead, how often). Changing the language (ctxc, std,
   runtime) is allowed when it is a must or greatly helps; follow `ctxlang/docs/internals.md`, "Changing the
   language" (new feature first, used only after `./ctxc0 run tools/fixpoint.ctx -- --update` refreshes the
   bootstraps), keep the suite passing (`kotor/tools/ctxc run ctxlang/tools/suite`), and add a
   case for every language change (a `.ctx` file under `ctxlang/tests/cases` that states what it
   prints or which error it has: [ctxlang/tests/README.md](../ctxlang/tests/README.md)). Language work happens on its own branch or worktree, never
   mixed into game commits.
2. **Native libraries:** SDL2 (window, input, GL context, audio queue, timing) and OpenGL **4.1
   core profile** (the newest macOS supports) plus the C library and libm, which every program
   links. Nothing else: every decoder (TPC/DXT, TGA, WAV/IMA-ADPCM, MP3, Bink video and audio) is
   ctxlang. Keep platform-specific code behind the platform layer so macOS and Linux can follow.
3. **The rendering seam is above OpenGL.** Game code describes what to draw (meshes, materials,
   lights, GUI quads, text, particles) through the backend-neutral `render` interface. Only the
   GL backend calls GL. A Metal, Vulkan or D3D backend must be addable without touching game code.
4. **Sources.** Allowed: public format documentation (BioWare's published Aurora docs, modding
   wikis and forums, xoreos-docs, write-ups), the game's own data (including `nwscript.nss`), and
   reverse engineering `swkotor.exe` with Ghidra (see Reverse engineering, below). Open-source
   reimplementations (reone, xoreos, KotOR.js, PyKotor and others, mostly GPL) may be **read to
   understand** a format or behaviour, but **never copied, ported line by line, or closely
   translated**. Write our code and docs in our own words.
5. **Nothing copyrighted in git.** No game files, extracted assets, decompiled code or Ghidra
   projects in commits. `kotor/re/`, `kotor/extract/` and `kotor/out/` are git-ignored: put such
   things there. Notes describing formats and behaviour in our own words belong in `kotor/docs/`.
6. **Verify against the real data.** Every parser has a tool that runs it over *every* resource of
   its type in the install and reports what failed. What can be checked on inputs made by hand
   (a parser's edge cases, a table's lookups) is a `#test` fn beside the code, in
   `NAME_test.ctx`, run with `kotor/tools/ctxc test kotor/tools/<a tool that adds the library>`
   (quick reference, Tests; `lib/formats/twoda_test.ctx` is the model; a test that needs the
   install is given its directory after `--`, and skips without it: "ctxlang in this game",
   below): write those first. Every renderer feature is checked by rendering
   offscreen to a PNG under `kotor/out/` and looking at it with the Read tool. Don't report
   something as working that you haven't run.
7. **Git.** Commit only on the branch or worktree you were given, with messages in the repository's
   style (imperative subject, a body that says why). Never push, never rewrite history, never
   touch other branches. Don't commit to `kotor` directly unless your brief says so: the
   orchestrator merges.
8. **Python** is for throwaway exploration and dev tooling only (`kotor/tools/py/`). Nothing the
   game needs at run time.
9. **Spend tokens carefully.** Usage is limited. Read the parts of files you need (grep first),
   keep command output short (`| tail -20`, `| grep`), don't re-read files you've already read,
   and don't paste large outputs into reports. Prefer one decisive verification over many.

## Building

```
kotor/tools/ctxc run PROGRAM_DIR -- ARGS...     # build and run (a dir with build.ctx, or a dir of .ctx files)
kotor/tools/ctxc exe PROGRAM_DIR -o OUT.exe     # build only
kotor/tools/ctxc check PROGRAM_DIR              # every compile error, nothing built
```

**Check before you build.** `ctxc check` runs the compiler's front end alone and reports every
error in the program, not the first 100, for every executable of a `build.ctx` and for its
`#test` fns too. Its last line counts them (`check: no errors`), and says when checks are still
held back by the errors shown, so run it again after fixing them. Use `run` or `exe` once it is
clean.

**Read errors as data when a tool reads them.** `--json` on `check`, `run`, `exe` and `test`
writes each error as one JSON object on a line of standard error: `file`, `line`, `column`,
`end_line`, `end_column`, `message` and `notes`, the other places involved (where the local
whose address escapes is declared, the two arguments that overlap, the earlier declaration),
then `{"type":"summary","errors":N,...}`. The text form has the same notes, indented under
their error. `ctxc test DIR --json` gives a record for each test and one for the run on
standard output (ctxlang/docs/spec.md §20, rule 15; §21, rules 8 to 11).

**Let the compiler make the edits it is sure of.** `ctxc check --fix DIR` applies every fix
that an error's message spells out and that leaves no choice (a pun that needs its field's
name, `_ = ` before an unused result, `..` for missing fields, `(q + i).*`, a missing comma,
and the rest of spec §21, rule 12), prints each as the lines before and after, and checks
again; `--fix --dry-run` prints them and writes nothing. It never touches std or generated
files, and it leaves the errors that need a choice: those carry suggestions in `--json`'s
`fixes`, with `"safe":false`. Read what it printed before going on: the edits are yours.

`kotor/tools/ctxc` builds ctxc from `ctxlang/bootstrap/ctxc.windows.c` when needed and sets
`CTX_HOME`. In Git Bash, MSYS2's gcc fails silently unless `/g/Dev/msys64/mingw64/bin` comes first
on `PATH`; the wrapper does that, so do the same for any other gcc call. PowerShell needs nothing.
SDL2 is installed in MSYS2 (`-lSDL2`, `SDL2.dll` on PATH from `/g/Dev/msys64/mingw64/bin`).

A program is a directory with a `build.ctx` that names its source directories. Template for a
tool (see `kotor/tools/glspike/build.ctx`):

```
fn build { mut b: Build } {
    let exe = build::exe{ &b, name = "gffdump", root = "." }        // this directory's own .ctx files
    build::add_sources{ &b, exe, dir = "../../lib/base" }           // a directory and all below it
    build::add_sources{ &b, exe, dir = "../../lib/formats" }
    build::link{ &b, exe, lib = "SDL2" }                            // only if it uses lib/platform
    build::optimize{ &b, exe, level = 2 }                           // optional: -O2
    build::trace_calls{ &b, exe, on = true }                        // optional, with -O2: panics keep their call path
}
```

- A panic prints the calls that led to it, a line each under its own (`  at fn (file:line:col)`),
  in every `ctxc test` build and in programs built without `build::optimize`. At `-O2` it names
  only the function it is in, unless the build.ctx says `build::trace_calls{ &b, exe, on = true
  }`, which costs a few percent (4% on ncsrun's VM, 8% on binkcheck's decode): enginetest
  has it, the game and the timing tools don't.

- Each program builds in its own directory under `ctxlang/build/run/`, so agents can build
  different programs at the same time. An unchanged program rebuilds in ~50 ms.
- A namespace may span files: `namespace gff { ... }` in `gff_read.ctx` and `gff_write.ctx` is
  one namespace (spec §10, rule 4), and each file's items see the other's unqualified. Keep
  files to a few thousand lines: a file is the unit of recompiling.
- A big program's C is split into units of about 256 KiB, grouped by source file and compiled in
  parallel, each cached by its hash: ~100K lines build in ~8 s from scratch (63 s as one C file),
  and an edit to one function rebuilds in ~3 s. Inserting lines recompiles every unit of that
  file. Tools that include only the libraries they need still build faster than the whole game.
- `@size_of` and `@offset_of(T, field)` check bindings' structs against C's layouts.

Testing the game (fast headless runs, checkpoints, the module smoke test, the conversation sweep): [docs/testing.md](docs/testing.md).
Gaps in the shell, the test tools and the game's framework that cost time: [docs/tooling-gaps.md](docs/tooling-gaps.md).

## ctxlang in this game

What the quick reference leaves to the program, as the game does it.

- **Code to imitate:** `lib/formats/`, `lib/res/`, `lib/mdl/`, `tools/resls/main.ctx`.
- **Memory:** the game's general heap is `lib/base`'s, over C's allocator:
  `let mut h = heap::new{ &mem }`, then `realloc = heap::alloc, heap = &h` wherever std takes an
  allocator (`list::new(u32){ realloc = heap::alloc, heap = &h }`). Arenas as std has them.
- **`math` is the game's** (`lib/base/math.ctx`: vectors, matrices, quaternions), and hides std's
  `math` whole. It declares libm's functions again, `#pure`, and the float-bits fns.
  `math::min`, `max` and `clamp` there are f32 fns that give the second operand for a NaN: use
  them for f32 game math as before, and `@min`, `@max` and `@clamp` elsewhere. Std's
  `math::INF` is out of reach: write `@as(f32, 1e300)` for `inf`.
- **Unchecked operations** (`@cast`, `@slice`, pointer arithmetic, C's declarations: spec §13)
  are compile errors outside the directories `kotor/build.ctx` lists in
  `build::deny_unchecked`'s `except`, each with its reason: lib/platform, lib/render_gl,
  lib/base, lib/script, lib/video, lib/audio and ui/core. Elsewhere write the checked form the
  error names, or call a function of one of those directories; calling an extern fn or using a
  slice that such a directory made is allowed everywhere. Add a directory to `except` only with
  its reason on its line. The tools (`kotor/tools/*`) don't deny them.
- **C:** SDL is `lib/platform/sdl.ctx`; only `lib/render_gl` touches GL.
- **Bound functions:** the script VM's engine is bound where the VM runs, in a call that isn't
  given the world: `nwvm::run{ &vm, program, self, engine = routines::call{ &w, _ } }`, as
  `scripts::run` does; don't pass a bound function down beside what it holds. Routine
  categories are a table of fallible fn values (`lib/engine/routines/dispatch.ctx`).
- **Tests that need the install** take its directory as an argument and skip without it:
  `kotor/tools/ctxc test kotor/tools/fmttest -- F:/Steam/steamapps/common/swkotor`, and the
  test starts with `let args = test::args{ &t }` and
  `if args.len == 0 { test::skip{ &t, why = "no game install: give its directory after --" } }`,
  then reads `args[0]`. `kotor/tools/ctxc test kotor/tools/fmttest twoda` runs those whose
  names contain `twoda`.

## Layout

```
kotor/
  AGENTS.md PLAN.md README.md
  build.ctx          the game executable
  game/              fn main and the top-level loop
  lib/<area>/        one directory per subsystem, normally one namespace each (below)
  tools/<name>/      dev tools and corpus tests in ctxlang (gffdump, resls, mdlview, ...)
  tools/py/          throwaway Python exploration
  docs/formats/      file formats, in our words, checked against the data
  docs/re/           what RE found: engine behaviour, addresses, structures
  docs/design/       our architecture: the render seam, object model, scripting
  re/                (ignored) Ghidra install/project, decompiled exports
  out/               (ignored) screenshots, logs, built executables
```

Planned subsystems (namespace in brackets):

| Directory | What |
|---|---|
| `lib/base` | math (`math`: vectors, matrices, quaternions), a general allocator, small helpers |
| `lib/res` | resource types, KEY/BIF, ERF/MOD/SAV, RIM, Override, the resource manager (`res`) |
| `lib/formats` | GFF read/write (`gff`), 2DA (`twoda`), TLK (`tlk`), LYT, VIS, SSF, LIP, TXI, LTR, PTH |
| `lib/tex` | TPC, TGA, DXT and cube maps to images (`tex`) |
| `lib/mdl` | MDL/MDX models, node trees, animations, supermodels (`mdl`) |
| `lib/walk` | BWM walkmeshes (WOK/PWK/DWK), ray and point queries (`bwm`) |
| `lib/audio` | WAV, IMA-ADPCM, MP3 decoding, mixing, 3D sound (`snd`) |
| `lib/video` | Bink decoding (`bink`) |
| `lib/script` | NWScript: the NCS virtual machine and engine-routine dispatch (`nwvm`) |
| `lib/platform` | SDL2 binding and the platform layer: window, input, time, audio out (`sdl`, `plat`) |
| `lib/render` | the backend-neutral rendering interface (`render`) |
| `lib/render_gl` | the OpenGL 4.1 core backend (`gl`, `glr`) |
| `lib/engine` ... | scene, objects, modules, camera, GUI, dialogue, rules: see PLAN.md |

## Style

- Follow ctxlang's own style (see `ctxlang/ctxc/*.ctx` and `std/`): function names are verbs or
  verb phrases (`read_header`, `from_literal`), comments explain why, not what.
- Name things after the game's own vocabulary where it has one (resref, GFF struct/field/label,
  2DA row, appearance, baseitem, module, area, GIT instance).
- Parsers never trust the data: a malformed file is an error value (`!T`), never a panic.
- Prefer arenas with clear lifetimes (per program, per module, per frame) over many small frees.

## Reverse engineering

**Never run `git clean` (or delete ignored files) in the main checkout**: `G:\Dev\zlang\kotor\re`
holds the Ghidra install, project and exports, which git doesn't track and can't restore. In a
worktree, `rex.py` finds the main checkout's `kotor/re` by itself; don't rebuild it elsewhere.

The exports were rebuilt after Ghidra had wrongly marked `CExoString::~CExoString` non-returning and
cut off the code after its 2,347 calls (`docs/re/noreturn-fix.md`). Before relying on an older RE
note about a function listed in `docs/re/noreturn-fix-recheck.tsv`, recheck it against the new
decompile, and correct the note if it no longer holds.

`kotor/re/` (git-ignored) holds the Ghidra install, the analyzed project for `swkotor.exe` and text
exports (decompiled functions, strings, RTTI class names, the NWScript routine table). See
`kotor/docs/re/README.md` for how to search them. When you learn something from the binary, write
it in `kotor/docs/re/` in your own words (function address, what it does, structure layouts), so
the next agent needn't rediscover it.
