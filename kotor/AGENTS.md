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

1. **Language.** Everything the game runs is ctxlang. Start with
   [docs/ctxlang-quickref.md](docs/ctxlang-quickref.md) and the existing code in `kotor/lib/`;
   read `ctxlang/spec.md` sections when you need the exact rule (the quick reference names
   them), and `ctxlang/std/*.ctx` for std's APIs. The compiler is young: when it gets in your way, log it in [FRICTION.md](FRICTION.md)
   (what you wrote, what you had to write instead, how often). Changing the language (ctxc, std,
   runtime) is allowed when it is a must or greatly helps; follow `ctxlang/PLAN.md`, "Changing the
   language" (new feature first, used only after `python tools/fixpoint.py --update` refreshes the
   bootstraps), keep `python -m unittest discover tests` passing (run from `ctxlang/`), and add a
   test for every language change. Language work happens on its own branch or worktree, never
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
   its type in the install and reports what failed. Every renderer feature is checked by rendering
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
```

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
}
```

- Each program builds in its own directory under `ctxlang/build/run/`, so agents can build
  different programs at the same time. An unchanged program rebuilds in ~50 ms.
- A namespace may span files: `namespace gff { ... }` in `gff_read.ctx` and `gff_write.ctx` is
  one namespace (spec §10, rule 4), and each file's items see the other's unqualified. Keep
  files to a few thousand lines: a file is the unit of recompiling.
- A big program's C is split into units of about 256 KiB, grouped by source file and compiled in
  parallel, each cached by its hash: ~100K lines build in ~8 s from scratch (63 s as one C file),
  and an edit to one function rebuilds in ~3 s. Inserting lines recompiles every unit of that
  file. Tools that include only the libraries they need still build faster than the whole game.
- `@size_of` checks are your friend for C structs; there's no `@offset_of` yet.

## Layout

```
kotor/
  AGENTS.md PLAN.md FRICTION.md README.md
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

`kotor/re/` (git-ignored) holds the Ghidra install, the analyzed project for `swkotor.exe` and text
exports (decompiled functions, strings, RTTI class names, the NWScript routine table). See
`kotor/docs/re/README.md` for how to search them. When you learn something from the binary, write
it in `kotor/docs/re/` in your own words (function address, what it does, structure layouts), so
the next agent needn't rediscover it.
