# The "does not return" bug in the first analysis (fixed 2026-10-04)

Ghidra's analysis marked returning functions as never returning, and stopped disassembling after
every call to them. The decompile of each caller ends at the call, or carries "Removing
unreachable block" and loses the tail of a branch (the case that exposed it: `CSWGuiActionSlot::SetState`,
`0x00689280`, whose last lines sat behind a `CExoString::~CExoString` call). The damage was larger
than truncated decompiles: a quarter of `.text` was never disassembled.

The project and the exports were rebuilt without the bug. This page says what was wrong, what
changed, and which earlier conclusions to recheck.

## The functions marked "does not return"

Eleven in the old project (`rex.py noreturn` lists them with the evidence: a RET in the function's
own body, and what follows each call to it).

| Address | Name | Verdict | Evidence |
|---|---|---|---|
| `0x005e5c20` | `CExoString::~CExoString` | **wrong** | 33 bytes: frees the buffer, `RET` at `0x005e5c40`. 2,347 call sites; the code after 2,126 of them was never disassembled and 217 more were reached only by other paths |
| `0x0059ea30`, `0x00727453`, `0x00736363` | thunks of it | **wrong** | `jmp 0x005e5c20` |
| `0x004ee440` | `CSWSCreature::GetUseRange` | **wrong** | nine `RET 0x10` in its body; 29 call sites in 21 functions (about 20 action handlers), 28 with undisassembled code after the call |
| `0x006fb223` | `__exit` | right | `_exit(code)` runs `doexit(code, 1, 0)`, which ends in `ExitProcess`; the `RET` after that call is the compiler's dead epilogue |
| `0x006fd90d` | `_abort` | right | `raise(SIGABRT)`, then `__exit(3)` |
| `0x006fee5f` | `terminate` | right | calls the terminate handler, then abort. The code after two call sites is the SEH filter and handler laid out behind it |
| `0x006fcbcb` | `__CxxThrowException@8` | right | `RaiseException` with the non-continuable flag (exception `0xe06d7363`); the code after three call sites is another branch's block |
| `0x0072614d`, `0x0072746c` | `__break` | right | a lone `int3` between unwind funclets, no callers |

So five functions were wrong (two real ones and three thunks of the first). The wrong flags
came from Ghidra's "Non-Returning Functions - Discovered" analyzer (with it on, a re-analysis
set the flag on `~CExoString` and `GetUseRange` again; with it off from the import, neither is
ever flagged). We did not chase why it concluded this; its threshold is three suspicious call
sites. `terminate` and the C++ throw evidently came from it too (a clean import without it does
not flag them), rightly.

## Why the old project was rebuilt, not patched

Clearing the flags and re-disassembling after the call sites (2,347 + 29 of them) is the obvious
fix, and it does not hold:

- With the analyzer still on, the re-analysis of the uncovered code flags `~CExoString` **again**
  and "repairs the flow damage" by clearing the code after its calls: 116,508 instructions
  (901,902 → 785,394) vanished in that one step, correct code included. The analysis manager reads
  its options when the program is opened, so a script cannot switch the analyzer off for itself;
  it has to be off from the start (`SetAnalysisOptions.java` as a pre-script).
- With it off, the patched project still had 96 names.tsv functions without a function at their
  address (`MainWndProc`, `CSWCCreature::DefaultActionTalk`, ...) and 276 switch-case and
  fragment "functions" that a clean analysis folds into their parents (switch tables and
  function boundaries are settled during the first analysis, which in the old project never saw
  the code after the destructor calls; a later re-disassembly does not redo them).

So `setup` now imports with the analyzer off (`SetAnalysisOptions.java`), and the live pipeline
was replaced by a fresh one (`KOTOR_RE=dir rex.py setup`, then `rex.py adopt dir`). `terminate`
and `__CxxThrowException@8` carry `__noreturn` in their names.tsv prototypes, which is what keeps
them flagged. Flagged now: those two, `__exit`, `_abort` and the two `__break` bytes (the
decompiler also treats the imports `ExitProcess` and `ExitThread` as not returning).

`kotor/re/export_prev` is the export before the swap, and `kotor/re/ghidra/*.prev` the old project
files; neither is deleted. `kotor/re/ghidra_pre_noreturn` is a second copy of the old project
directory, and `kotor/re/noreturn/` holds this investigation's scratch (about 600 MB: the patched
attempts' exports and projects and the audit reports). All of it can go when nobody needs the
old state.

## What changed in the exports

| | before | after |
|---|---|---|
| functions in the export | 11,633 | 12,675 |
| instructions in the listing | 760,204 | 932,025 |
| `.text` bytes that are no code, data or padding | 797,193 (24%) | 157,314 (4.6%); 140,551 of them in the unwind-funclet zone `0x710000`–`0x73ffff` |
| names.tsv code rows with no function at their address | 420 of 3,977 | 0 |
| decompiles with "Subroutine does not return" | 1,251 | 27 (calls to exit, abort, terminate, the throw, `ExitThread`, `ExitProcess`) |
| decompiles with "Removing unreachable block" | 43 | 30 (all after a jump; none after a call) |

Per function (`noreturn-fix-functions.tsv`, columns `kind addr name lines_before lines_after
cited_in note`; `lines` counts the decompiled body without its comment header):

- **1,249 changed decompiles** (of 11,633): 1,046 longer (236 by more than 50 lines), 78 shorter,
  125 the same length. The longest growths: `CClientExoApp::FormatCombatFeedback` 2,490 → 5,896 lines,
  `CSWSCreatureStats::ReadStatsFromGff` 63 → 1,093, `CSWSpellArray::Load` 64 → 868,
  `CClientExoAppInternal::SetupKeymapping` 148 → 888, `CSWSModule::LoadModuleStart` 37 → 661,
  `CSWSArea::LoadAreaHeader` 37 → 589, `CSWBaseItemArray::Load` 63 → 546.
  Some of the shorter ones lost their "does not return" warning lines, some are re-structured
  (`CVirtualMachineInternal::ExecuteCode` 801 → 797: same logic, a cleaner loop head).
- **1,312 new functions**, 420 of them named in names.tsv (so the names exist in the export now) and
  506 cited by a doc. Earlier agents could not have read their decompile.
- **270 functions gone**: 253 `switchD_…::caseD_N` and 17 `FUN_` fragments, now inside their parent
  function; none was named, 9 are cited by a doc (the `note` column says where they went).

## Earlier conclusions to recheck

740 of the changed functions and 506 of the new ones are named in names.tsv or cited by a doc
(`cited_in`); 610 of the changed ones are cited by an `.md` page, 130 only by a names.tsv row
(its name, prototype and comment). `noreturn-fix-recheck.tsv` has one row per (doc, function),
the largest changes first. Functions per doc (changed + new + gone):

`re/` pages: gui 342, party-items-saves 148, render-gui 126, objects 112, resources 108, app 88,
gameloop 73, combat 58, rules 57, actions 57, chargen 56, dialogue 44, movement 41, modules 30,
resman 27, vm 26, chargen-creature 23, README 23, minigames-swoop-turret 12, journal 8, pazaak 4,
chargen-3d 3, gui3d 1. `mechanics/` pages: stealth 22, traps 20, controls 8, combat 7,
items-skills 7, force 5, graphics 3. names.tsv: 1,089 functions.

Where to start:

1. **Claims the docs themselves flag as read from the disassembly because the decompile was cut**:
   `actions.md` (the warning at the top, MOVETOPOINT steps 2–6 "reconstructed from a damaged
   decompilation", CHECKMOVETOOBJECT, DIALOGOBJECT's second phase, HEAL, the trap handlers),
   `rules.md` (`OnApplyForceShield`), `mechanics/traps.md` (`LoadTrigger`), `gui.md` (the
   constructor cut at `0x006ea0fd`), `render-gui.md` (`FUN_006a1880`).
2. **Anything built on a loader or a big function that grew a lot**: the top of
   `noreturn-fix-recheck.tsv` for each doc. A doc that read a "complete" fields list off a 60-line
   `ReadStatsFromGff` had only the head of it.
3. **names.tsv comments with confidence low or med** on a function that grew: the note was a guess
   from a stump (`SetState` below was `low`).

## Spot checks

Five cited functions, doc claim against the new decompile:

| Function | Doc | Result |
|---|---|---|
| `CSWGuiActionSlot::SetState` `0x00689280` (43 → 52 lines) | names.tsv: clears the icon when empty, arrows when more than one entry (low) | holds, and can be `high`: the empty branch clears both fills, empty dims the slot to alpha 0.5, `bHasMore` sets bit 2 of the two arrow flag words (`+0x3cc`, `+0x590`). The old stump ended after the destructor call |
| `CSWSCreature::AIActionSetTrap` `0x00519e30` (175 → 455) | actions.md SETTRAP, mechanics/traps.md §6, rules.md | holds: zero point refused, 15-mine limit via `0x005089d0`, stand spot and 1.5 m (the `2.25` is the square), 2000 ms / type 5 timer, SetDC from the item's first property's subtype (min 1), Demolitions +2 above 4 base ranks, take-20 or d20, a miss by 10 or less (or any take-20 miss) lays nothing, the trigger fields, one item off the stack. One thing the docs omit: for a door or placeable target the first-pass animation is 10060, not 10140 |
| `CSWSEffectListHandler::OnApplyForceShield` `0x004df540` (72 → 187) | rules.md §1.13, mechanics/combat.md | holds in every step: creatures only, old shield removed by effect id when the helper returns non-zero, the row read by label with the four Appearance/VisualEffect pairs, `Permanent` read and unused, two `CGameEffectFromParent` children (VISUALEFFECT with the aura, DAMAGE_RESISTANCE forced to magical with DamageFlags/Resistance/Amount/VulnerFlags), returns 0 |
| `CSWSTrigger::LoadTrigger` `0x0058da80` (120 → 343) | mechanics/traps.md rows 39–40 | holds: TrapType, TrapOneShot, TrapDetectable, TrapDisarmable, CreatorId, SetByPlayerParty, KeyName, AutoRemoveKey are read; DetectDCMod and DisarmDCMod come from traps.2da by TrapType (set only if the lookup succeeds); an empty or `default` OnTrapTriggered becomes the type's TrapScript; the blueprint's own DCs and TrapFlag are never read |
| `CSWSCreatureStats::ReadStatsFromGff` `0x005afce0` (63 → 1,093) | chargen-creature.md (HP) | holds: `HitPoints` goes into `+0xe0`, `CurrentHitPoints` is read relative to it and then raised by level × a per-level byte (`this+0xee`); also floored at the level, which the doc does not say. Not checked beyond the HP block |

None contradicted its doc. The two additions (animation 10060, the HP floor) are details the docs
left out.

## Keeping it fixed

- `python kotor/tools/py/rex.py noreturn` lists the functions flagged now, per call site what
  follows it, and how much of `.text` is not code. After a re-import, expect the six above and
  about 157 KB of gaps, nearly all in `0x710000`–`0x73ffff`.
- `KotorRE.java noreturn-report` also writes `*.sites` (call sites to flagged functions with code
  after them) and `*.overrides` (every instruction with a flow override).
- To compare two exports and see which docs cite the differences:
  `python kotor/tools/py/export_diff.py kotor/re/export_prev kotor/re/export`.
- A decompile that ends right after a call, or shows "Removing unreachable block", needs a look at
  the asm: see the first caveat in [README.md](README.md).
