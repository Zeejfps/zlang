# Reverse engineering swkotor.exe

What we know about the original engine, and the tools for finding out more. Everything here is
ours: addresses, names and descriptions in our own words. Nothing derived from the binary
(decompiled code, the Ghidra project, the exports) goes into git; it lives in `kotor/re/`, which
is ignored.

| File | What |
|---|---|
| [names.tsv](names.tsv) | the shared names database: address, name, prototype, comment |
| [nwscript-routines.md](nwscript-routines.md) | NWScript routine number → handler: where the table is, how to rebuild it |
| [vm.md](vm.md) | the NCS virtual machine: loader, interpreter loop, stack |
| [resources.md](resources.md) | resource manager, type registry, GFF, 2DA, TLK readers |
| [resman.md](resman.md) | resource manager search order, short version (written before the names existed) |
| [modules.md](modules.md) | module and area loading |
| [objects.md](objects.md) | server-side game objects: classes, vtables, templates, events, actions |
| [app.md](app.md) | start-up, main loop, input, audio, movies |
| [render-gui.md](render-gui.md) | the OpenGL renderer and the GUI system |
| [noreturn-fix.md](noreturn-fix.md) | the "does not return" bug of the first analysis: what it cut, what the rebuild changed, earlier conclusions to recheck ([every function that changed](noreturn-fix-functions.tsv), [per doc](noreturn-fix-recheck.tsv)) |

The file formats themselves are described in [../formats/](../formats/); these pages are about
the engine's code.

## Map of the engine

The engine is the Aurora/Odyssey family's: a client and a server in one process (`CAppManager`
holds `CClientExoApp` and `CServerExoApp`), the `CExo*` base library, the `CRes*` resource
system, the `CAur*` renderer, `CSWGui*` GUI panels, `CSWS*` game objects and rules on the server
side, `CSWC*` presentation objects on the client side, and the NWScript VM. MSVC laid functions
out in source-file order, so subsystems occupy ranges of `.text`. `rex.py map` prints this
table from the current names; ranges are approximate.

| `.text` range | What lives there |
|---|---|
| `0x401000`–`0x40ffff` | start-up (`WinMain`, window procedure, `CAppManager`), the movie player's internals, the resource manager (`CExoResMan`, `CExoKeyTable`, `CRes`), the GUI manager and panels |
| `0x410000`–`0x41ffff` | GFF (`CResGFF`), 2DA (`C2DA`), TLK (`CTlkTable`), GUI controls |
| `0x420000`–`0x49ffff` | the renderer (`CAur*`): textures, GL extensions, display and context, console, scene and camera, models and meshes, triangle stripifier; `0x480000`–`0x49ffff` unexplored, renderer by its imports |
| `0x4a0000`–`0x4bffff` | the server application (`CServerExoApp[Internal]`), world timer, AI master (event delivery), module loading |
| `0x4c0000`–`0x4dffff` | `CGameObject`/`CSWSObject` base, `CSWSModule`, script engine structures (effects, events, locations, talents), the object id table, the combat round |
| `0x4e0000`–`0x51ffff` | `CSWSCreature` (constructor, template loading), `CSWSArea` (ARE, GIT, PTH), game effects |
| `0x520000`–`0x54ffff` | the 772 NWScript command handlers (`CSWVirtualMachineCommands`) and their table |
| `0x550000`–`0x59ffff` | items, the per-frame action queue, placeables, doors, triggers, encounters, areas of effect, script variable tables |
| `0x5a0000`–`0x5cffff` | creature stats, classes and races, the 2DA cache (`C2DAs`), stores, waypoints, sound objects, the minigame command handlers |
| `0x5d0000`–`0x5dffff` | the NWScript VM, ERF reading, sound (Miles), layout (LYT) |
| `0x5e0000`–`0x5effff` | the `CExo*` base library: strings, localised strings, files, lists, input (DirectInput), resource type registry, key bindings |
| `0x5f0000`–`0x64ffff` | the client application (`CClientExoAppInternal`): initialisation, main loop, update and render, client areas, in-game GUI, `CSWCModule` |
| `0x650000`–`0x6effff` | GUI panels (main menu, HUD, load screen, dialogue), client creatures, animation and visual effects, minigames — mostly unexplored |
| `0x6f0000`–`0x73c1d0` | the C runtime and STL (`0x6fa000` on: `operator new`, `free`, `rand`, the entry point), Bink/movie wrappers, resource helper templates, compiler exception-unwind funclets (`0x71e000`–`0x73a000`) |

Key places (names are ours; confidence high unless noted; details in the linked pages):

| What | Address | Name |
|---|---|---|
| program entry, WinMain | `0x006fb38d`, `0x004041f0` | `entry`, `WinMain` (holds the main loop) |
| main loop, per frame | `0x00602eb0`, `0x004ae860` | `CClientExoAppInternal::MainLoop`, `CServerExoApp::MainLoop` |
| app globals | `0x007a39fc`, `0x007a39e0` | `g_pAppManager` (+4 client, +8 server), `g_pExoBase` |
| 3D frame | `0x006048c0` → `0x00644650` → `0x004512d0` | `UpdateObjectsAndRender` → `CSWCModule::Render` → `CAurScene::Render` |
| GL context, extensions, texture upload | `0x0044dab0`, `0x00436490`, `0x00424980` | `CAurGLDisplay::CreateContext`, `GL_LoadExtensions`, `CAurTexture::Upload2D` |
| GUI | `0x007a39f4`, `0x0040cc50`, `0x0040a680` | `g_pGuiManager`, `CSWGuiManager::Render`, `CSWGuiPanel::LoadGui` |
| input, sound, movies | `0x005e24e0`, `0x005da8a0`, `0x00405b30` | `CExoInputInternal::GetEvents`, `CExoSoundInternal::Initialize`, `CExoMoviePlayerInternal::MovieThreadProc` |
| resource manager | `0x007a39e8`, `0x00406e20`, `0x00407230`, `0x004089f0` | `g_pExoResMan`, `AddKeyTable`, `GetKeyEntry` (lookup), `Demand` |
| resource type registry | `0x005e6d20`, `0x005e7a00` | `CExoResTypes::InitResourceTypes`, `GetResourceExtension` |
| GFF | `0x00410740`, `0x00411a60`…, `0x00413030` | `CResGFF` header check, `ReadField*` getters, `WriteGFFFile` |
| 2DA | `0x004143b0`, `0x005c4c20` | `C2DA::Load2DArray`, `C2DAs::Load2DArrays` (the ~74 cached tables) |
| TLK | `0x007a3a08`, `0x0041e1a0` | `g_pTlkTable`, `CTlkTable::FetchInternal` |
| module and area loading | `0x004b95b0`, `0x004c9050`, `0x0050e190`, `0x0050dd80`, `0x005de900` | `LoadModule`, `CSWSModule::LoadModuleStart` (IFO), `CSWSArea::LoadArea`, `LoadGIT`, `CLayout::ParseLayout` (LYT) |
| NWScript VM | `0x007a3a00`, `0x005d2bd0`, `0x005d2260`, `0x005d45d0` | `g_pVirtualMachine`, `ExecuteCode` (interpreter loop), `ReadScriptFile` (NCS loader), `RunScript` |
| routine table | `0x0054c960`, `0x0052c0d0` | `InitializeCommands` (fills 772 slots at commands+0xc), `RunCommand` (dispatch) |
| objects | `0x004d8230`, `0x004cea20`, `0x0057f4a0`, `0x004b0b70` | `CGameObjectArray::GetGameObject`, `CSWSObject::AddAction`, `RunActions`, `CServerAIMaster::UpdateState` (events) |
| creatures | `0x004f7a10`, `0x005026d0`, `0x005afce0` | `CSWSCreature` constructor, `LoadFromTemplate` (UTC), `CSWSCreatureStats::ReadStatsFromGff` |

## The binary

- Steam `swkotor.exe` (4,395,008 bytes, SHA-256 `34e6d971…f34c88`), linked 2004-02-12 by MSVC
  7.x, 32-bit, image base `0x400000`, entry `0x006fb38d` (CRT start-up).
- It is wrapped in **SteamStub 2.1** (a `.bind` section holding the entry point, `.text`
  encrypted). We work on the copy unpacked by Steamless (`kotor/re/bin/swkotor_unpacked.exe`,
  4,042,752 bytes, SHA-256 `0290889e…4437e6`); `.bind` is removed, everything else keeps its
  address, so addresses are the same as in the running game.
- Sections: `.text` `0x401000`–`0x73c1d0`, `.rdata` `0x73d000`–`0x78cbfe`, `.data`
  `0x78d000`–`0x835498` (only the first `0x17000` bytes are initialised; the rest is bss), `.rsrc`.
- **No symbols and almost no RTTI**: the only type descriptors are five CRT/STL exception classes.
  Class names come from us, from a few dozen log strings of the form `CSWClass::LoadFeatTable: ...`,
  and from what code does. The naming follows the Aurora engine family's conventions (`CExo*`
  base library, `CSWS*` server/game side, `CSWC*` client/presentation side, `CSWGui*`).
- The linker **folded identical functions**: one tiny body (say "return 0") can serve as a script
  command and as a slot in many unrelated vtables. Such functions get neutral names
  (`FoldedStub_<addr>`); don't infer a class from a folded function.
- Ghidra finds ~12,700 functions (after our fix-up pass, which adds ~4,000 that are only reached
  through pointers: virtual functions and script command handlers).

## Layout

```
kotor/re/                     (git-ignored)
  bin/swkotor.exe             copy of the Steam exe; swkotor_unpacked.exe is what we analyze
  bin/*.dll                   binkw32, mss32, patchw32 from the install (not analyzed yet)
  tools/                      ghidra_12.1.4_PUBLIC, jdk-21 (Temurin, portable), steamless
  ghidra/                     the Ghidra project (swkotor.gpr/.rep), run logs, names_applied.tsv
  export/                     plain-text exports (below)
  data/nwscript.nss           the game's script header, extracted with kres.py
  proposals/                  scratch name proposals before they are merged into names.tsv
kotor/tools/py/rex.py         query the exports; drive Ghidra; maintain names.tsv
kotor/tools/py/nwscript_table.py   rebuild the NWScript routine → handler table
kotor/tools/re/KotorRE.java   the Ghidra script behind rex.py (exports, decompile, names, fix-up)
kotor/tools/re/SetAnalysisOptions.java   pre-script for the first analysis
```

## Querying

All commands run from the repository root (`python kotor/tools/py/rex.py -h` lists them).
Addresses are hex with or without `0x`; a name works wherever an address does (exact, then the
part after `::`, then a unique substring).

```
rex.py fn 0x5419d0                 # decompiled C with a header: callers, callees, strings, globals
rex.py fn ExecuteCommandRandom     # same, by name
rex.py find 'CSWClass::'           # functions by name regex, with size and signature
rex.py grep 'glBindTexture' --max 20   # regex over all decompiled code (~2 s)
rex.py callers StackPopInteger     # call sites, plus vtable slots that hold the function
rex.py callees 0x54c960
rex.py strings 'Mod_Entry' -i      # strings with the functions that use them
rex.py xrefs 0x7a3a00              # everything that refers to an address
rex.py class CSWClass              # functions, vtables and log strings of a class
rex.py imports SwapBuffers         # imported API and its callers
rex.py tables --min 20             # pointer tables in data (vtables, handler/string/record tables)
rex.py vtables                     # vtable candidates and the functions that install them
rex.py globals 'g_p' -v            # referenced globals and who uses them
rex.py routine 7 | 'Effect.*'      # NWScript routine: prototype and handler
rex.py dword 0x7450e4 11           # raw dwords from the image (names resolved)
rex.py bytes 0x73d790 64           # hex dump
rex.py asm 0x52c0d0                # Ghidra disassembly listing with resolved references (~10 s)
rex.py stats                       # sizes and counts of the exports
rex.py noreturn                    # audit: functions marked "does not return" with evidence; how much of .text is code
```

Plain `grep`/`rg` over `kotor/re/export/` works too: every file is UTF-8 text, TSVs have a
header row, and backslash, tab and newline inside strings are escaped as `\\`, `\t`, `\n`.

## The exports (`kotor/re/export/`)

| File | Rows | Columns |
|---|---|---|
| `functions.tsv` | one per function | `addr name size n_callers n_callees class source decomp signature`; `source` is `DEFAULT` (Ghidra's `FUN_` name), `ANALYSIS` (library function identified by Ghidra), `USER_DEFINED` (from names.tsv) |
| `functions/<addr>_<name>.c` | one per function | a comment header (address, name, size, signature, our note, callers, places that take its address — vtables, tables —, callees, imports, strings, globals, function pointers it takes) and Ghidra's decompiled C; `::` in names becomes `__` in file names |
| `calls.tsv` | one per reference to a function | `caller callee kind site`; kind `call`, `jump` (tail call) or `ref` (address taken) |
| `strings.tsv` | one per defined string | `addr len type ref_functions ref_data text` |
| `imports.tsv` | one per imported function | `dll function iat n_callers callers` |
| `vtables.tsv` | one per vtable candidate | `addr name slots ref_functions entries` (a run of code pointers in `.rdata` whose start code stores, i.e. constructors/destructors) |
| `tables.tsv` | one per pointer run in data | `addr dwords period pattern kind …`: `pattern` is one period of entry classes (`F` function, `C` code, `S` string, `D` data pointer, `0` zero, `i` small integer); `kind` is `fn_table`, `string_table`, `records`, `mixed` or `eh_unwind` (compiler exception tables, hidden by `rex.py tables` unless `--all`) |
| `globals.tsv` | one per data address code refers to | `addr name type section n_ref_functions ref_functions` |
| `segments.tsv` | sections | `name start end size perms initialized` |
| `rtti.tsv` | RTTI found by Ghidra | (empty apart from the CRT classes) |
| `nwscript_routines.tsv` | 772 routines | `number name handler handler_name shared_with signature` |
| `asm/<addr>_<name>.s` | on demand | disassembly listings written by `rex.py asm` |

## Improving the names

`names.tsv` is the source of truth for every name we give: rebuilding the project from scratch
re-applies it. Rows are `addr<TAB>name<TAB>prototype<TAB>comment`:

- **name**: `Class::Method` for member functions (the class becomes a Ghidra class, so `this`
  gets its type), plain names for free functions, `g_pName` style for globals,
  `Class::vftable` for vtables. Use the engine's vocabulary where it has one.
- **prototype** (optional): a C declaration, e.g. `int __thiscall F(int nCommand, int nParameters)`.
  The name inside it is ignored. For `__thiscall` leave `this` out; Ghidra adds it from the
  class. Unknown types used through a pointer (`CExoString *`) are created as empty structures.
  For a data address it is a type (`int[772]`, `char *`).
- **comment** (optional): our description, shown as `// note:` in the exported function. End it
  with a confidence: high, med or low.

```
rex.py name 0x5d1010 CVirtualMachine::StackPushInteger --proto 'int __thiscall F(int nValue)' --comment 'pushes an int (high)'
rex.py apply                       # ~25 s: applies new/changed rows, re-exports what shows them
rex.py merge kotor/re/proposals/x.tsv   # bulk: checks addresses, keeps existing names on conflict
rex.py autoname --write            # names from "Class::Method" log strings (done once already)
rex.py decompile ADDR...           # re-export functions after changing something by hand
```

`apply` only applies rows that are new or changed since the last run (it keeps the applied rows
in `kotor/re/ghidra/names_applied.tsv`; `apply --all` re-applies everything). It re-exports the
renamed functions, their callers and callees and the readers of renamed globals, then the
tables. Rows that fail (bad address, prototype that doesn't parse) are reported and retried next
time. Removing a row from names.tsv does not unname anything in the project.

Several agents may use the tools at once. Read-only queries need nothing. Everything that starts
Ghidra (`apply`, `decompile`, `asm`, `export`, `setup`) waits for a lock
(`kotor/re/ghidra/.rex.lock`), because Ghidra can open a project only once. Agents working in a
git worktree use the main checkout's `kotor/re` automatically (set `KOTOR_RE` to override), but
their own `kotor/docs/re/names.tsv`. When two agents name things in parallel, prefer each
writing a proposals file and one of them merging it.

## Timings (24-core machine)

| Step | Time |
|---|---|
| `rex.py install` (Ghidra 570 MB, JDK 200 MB, Steamless) | ~1 min |
| Steamless unpack | 2 s |
| import + auto-analysis (with Decompiler Parameter ID) | 3.4 min |
| fix-up pass (functions behind pointers, short strings) | 35 s |
| `export` (all 12,700 functions decompiled in parallel, plus tables) | 80 s |
| `export --tables` | 15 s |
| `apply` | 20–30 s |
| `decompile` / `asm` of a few functions | ~10 s (mostly Ghidra start-up) |
| `setup` from nothing to exports | ~7 min |
| read-only queries | < 1 s |

## Rebuilding from scratch

```
python kotor/tools/py/rex.py install        # Ghidra 12.1.4, Temurin JDK 21, Steamless 3.1.0.5 into kotor/re/tools
python kotor/tools/py/rex.py setup          # copy + unpack the exe, analyze, fix up, apply names.tsv, export
```

`setup --force` throws away the project and starts again. `KOTOR_RE=some/dir rex.py setup`
builds a second, independent pipeline elsewhere (tools are still taken from `kotor/re/tools`).

The pipeline: Steamless removes SteamStub; Ghidra imports with its default Windows PE analyzers
plus Decompiler Parameter ID; `KotorRE.java fixup` creates functions at every address that is
taken but not yet a function (vtable slots, handlers stored by init routines, callbacks) and
defines short strings that code references (GFF labels, 2DA column names), then re-runs analysis
on the changes; names.tsv is applied; everything is exported. The import turns Ghidra's
"Non-Returning Functions - Discovered" analyzer off (`SetAnalysisOptions.java`): left on, it marks
returning functions as non-returning and then clears the code after their calls
([noreturn-fix.md](noreturn-fix.md)). The few functions that really never return carry
`__noreturn` in their names.tsv prototype.

To replace a live pipeline with one rebuilt elsewhere (what fixed the above), build it with
`KOTOR_RE=some/dir rex.py setup` and run `rex.py adopt some/dir`: it swaps the project files and
the export under the Ghidra lock and keeps the old ones as `*.prev` and `kotor/re/export_prev`.

## Caveats

- **A decompile that ends right after a call, or has "Removing unreachable block" in its header
  comment, may be cut short: check the asm** (`rex.py asm ADDR`). Ghidra drops the code after a
  call to a function it thinks never returns, and a wrong "does not return" flag on a small
  helper (a string destructor) did that to the callers of 2,300 call sites. If the bytes after
  the call are real code, not `int3` padding or the next function, the callee is flagged wrongly:
  `rex.py noreturn` lists what is flagged and how much of `.text` is still not code. A
  "Removing unreachable block" after a conditional jump is a branch the decompiler proved dead,
  not this bug.
- Coverage: names.tsv holds ~2,100 rows (~1,950 of the 12,700 functions, 15%, plus globals and
  vtables). The 772 script handlers, the VM, resources, GFF/2DA/TLK, start-up, the main loop and
  the object model are well covered; client-side objects, animation, most GUI panels, combat
  rules and the minigames are mostly `FUN_` still.
- Tiny getters (`return this->field`) are often shared by unrelated classes after folding; the
  name of such a function describes one of its uses, and its note says so.
- Decompiled C is Ghidra's guess. Parameter counts, `__thiscall` vs `__fastcall`, and types are
  often wrong until someone gives a prototype; check the disassembly (`rex.py asm`) when it
  matters.
- Strings shorter than two characters, and strings reached only through computed pointers, are
  not defined, so `rex.py strings` misses them. File signatures are often compared as integers
  (`"GFF "` as `0x20464647`), so search for the constant too.
- Function sizes count every byte of the body, which may be split into several chunks.
- Vtable candidates are runs of code pointers whose first slot code references. Adjacent vtables
  are split where code references a slot, which can occasionally cut one in two or join two.
