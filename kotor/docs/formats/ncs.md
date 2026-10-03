# NCS: compiled NWScript

An NCS file (resource type 2010, extension `ncs`) is one compiled NWScript program: a header
and a flat run of stack-machine instructions. Every script the game runs (creature and
placeable events, dialogue conditions and actions, triggers, module and area events, the AI) is
one. The source language and the engine routines it calls are described in
[nwscript.md](nwscript.md).

Where they live in the install: `data/scripts.bif` (1784, the shared scripts), every module's
`modules/*_s.rim` (10863, many of them copies of the same script), and `rims/global.rim` and
`rims/miniglobal.rim` (492). `Override/` is empty in a stock install.

Everything here was checked against all 13139 copies; see [Checked](#checked).

## File layout

| Offset | Size | What |
|---|---|---|
| 0 | 8 | `NCS V1.0` (ASCII) |
| 8 | 1 | `0x42` |
| 9 | 4 | file size in bytes, **big-endian** u32: equals the real size in every file |
| 13 | ... | instructions, back to back, up to the last byte of the file |

The 0x42 byte and the size are best read as a pseudo-instruction (the classic NWN write-ups
call it `T`) that states the program size. The first real instruction is at offset 13, and that is where
execution starts. Code offsets (jump targets, the disassembler's addresses) are byte offsets from
the start of the file, so the first instruction is at `0x0d`. There is no symbol table, no data
section and no trailer: strings live inside the instructions that push them.

The smallest file is 23 bytes (`JSR +8; RETN; RETN`: an empty `main`). The median is 299 bytes,
the largest 92832.

## Instruction encoding

```
opcode:u8  type:u8  operands...
```

All multi-byte operands are **big-endian**. The type byte says what the operands of the
operation are (for a binary operation, the left operand's type then the right one's); for
instructions that don't care it is 0x00 or 0x01. Instruction size is fixed by opcode and type,
except `CONSTS`, which carries its string. Jump offsets are signed and relative to the **start
of the jump instruction itself**.

Type byte values:

| Byte | Meaning | Byte | Meaning |
|---|---|---|---|
| 0x00 | none (control flow, ACTION, MOVSP, BP ops) | 0x20 | int, int (`II`) |
| 0x01 | none (stack copies, DESTRUCT) | 0x21 | float, float (`FF`) |
| 0x03 | int (`I`) | 0x22 | object, object (`OO`) |
| 0x04 | float (`F`) | 0x23 | string, string (`SS`) |
| 0x05 | string (`S`) | 0x24 | structure, structure (`TT`, takes a size) |
| 0x06 | object (`O`) | 0x25 | int, float (`IF`) |
| 0x10 | effect | 0x26 | float, int (`FI`) |
| 0x11 | event | 0x30..0x33 | effect/effect, event/event, location/location, talent/talent |
| 0x12 | location | 0x3A | vector, vector (`VV`) |
| 0x13 | talent | 0x3B / 0x3C | vector, float (`VF`) / float, vector (`FV`) |

The engine structures 0x10..0x13 are the four declared at the top of `nwscript.nss`
(`ENGINE_STRUCTURE_0..3` = effect, event, location, talent); there are no others in KOTOR.

## The machine

- **Stack of 4-byte cells**, growing upwards. SP is the byte offset of the first free cell, so
  the top cell is at SP-4. Every SP- or BP-relative operand in the corpus is a negative multiple
  of 4; sizes are multiples of 4.
- **Values.** int: a signed 32-bit cell. float: an IEEE-754 single in one cell. object: one cell
  holding an object id; in the bytecode the only object constants are **0 = `OBJECT_SELF`** and
  **1 = `OBJECT_INVALID`** (checked: `CONSTO` takes no other value in the corpus, a source's
  `return OBJECT_INVALID;` compiles to `CONSTO 1`, and `UT_GetPlotBooleanFlag(OBJECT_SELF, ...)`
  pushes `CONSTO 0`); the engine maps them to the running object and its own invalid id.
  string, effect, event, location, talent: **one cell each, holding a reference** (a handle to
  an engine-side value). vector: **three float cells**, x deepest, z on top. A user `struct` is
  its fields in declaration order, the first field deepest (checked against `k_inc_generic`'s
  `struct tLastRound`: field 3 is read with `DESTRUCT 40 12 4`).
  Because strings and engine structures are references, a VM has to know which cells hold them,
  so that copying a cell duplicates (or shares) the value and popping it releases it. The type
  of every cell is known when it is pushed (RSADD, CONST and ACTION all name it), so tagging
  cells with their type is enough.
- **BP**, the base pointer, addresses the **global variables**. Globals are pushed at the start
  of the run (see [Program layout](#program-layout)), then `SAVEBP` makes BP point just past the
  last of them: `BP-4` is the last global declared, `BP-4n` the first of n. Checked:
  `k_con_comactive` has 21 globals and reads the 11th (`SW_PLOT_HAS_TALKED_TO`, index 10) with
  `CPTOPBP -44`; with BP above the saved-BP cell it would be off by one.
- **Return addresses are not on the data stack.** `JSR` and `RETN` use a separate return stack.
  Checked: a callee's `CPDOWNSP -8 4` right after pushing one cell writes the caller's
  return-value slot directly below its first cell; the whole-corpus stack check (below) assumes
  this and agrees with every file.
- **The saved state.** `STORE_STATE` captures a resumable state into a VM register (not onto the
  stack) that the next ACTION taking an `action` argument consumes. See [Actions](#action-arguments-store_state).

## Instructions

Notation: `a` is the deeper operand, `b` the top one, so `SUBII` computes `a - b` and `LTII`
`a < b` (checked against sources: `GetMaxHitPoints(OBJECT_SELF) / 2.0` is `DIVIF`, int deeper,
float on top). Sizes are in bytes; "n" in a stack effect is a byte count.

| Op | Mnemonic | Type bytes | Operands (after op, type) | Size | Stack effect |
|---|---|---|---|---|---|
| 0x01 | CPDOWNSP | 01 | offset:i32, size:u16 | 8 | copy the top `size` bytes to SP+offset (overwrite, no pop): assignment to a local |
| 0x02 | RSADD | 03 04 05 06 10 11 12 13 | | 2 | push one default value of the type (a local or a return slot) |
| 0x03 | CPTOPSP | 01 | offset:i32, size:u16 | 8 | push a copy of `size` bytes from SP+offset: reading a local or argument |
| 0x04 | CONST | 03 04 05 06 | int: i32; float: f32; string: len:u16 + bytes (no terminator); object: i32 | 6, 6, 4+len, 6 | push the constant |
| 0x05 | ACTION | 00 | routine:u16, argc:u8 | 5 | call engine routine `routine`; see [ACTION](#action) |
| 0x06 | LOGAND | 20 | | 2 | pop b, a; push `a && b` (0/1) |
| 0x07 | LOGOR | 20 | | 2 | pop b, a; push `a \|\| b` |
| 0x08 | INCOR | 20 | | 2 | pop b, a; push `a \| b` (bitwise) |
| 0x09 | EXCOR | 20 | | 2 | pop b, a; push `a ^ b` |
| 0x0A | BOOLAND | 20 | | 2 | pop b, a; push `a & b` (bitwise) |
| 0x0B | EQUAL | 20 21 22 23 30..33; 24 | TT only: size:u16 | 2; 4 | pop two values (two `size`-byte blocks for TT), push int `a == b` |
| 0x0C | NEQUAL | as EQUAL | as EQUAL | 2; 4 | as EQUAL, `a != b` |
| 0x0D | GEQ | 20 21 | | 2 | pop b, a; push int `a >= b` |
| 0x0E | GT | 20 21 | | 2 | `a > b` |
| 0x0F | LT | 20 21 | | 2 | `a < b` |
| 0x10 | LEQ | 20 21 | | 2 | `a <= b` |
| 0x11 | SHLEFT | 20 | | 2 | `a << b` |
| 0x12 | SHRIGHT | 20 | | 2 | `a >> b` (signed; unused, so negative operands are unverified) |
| 0x13 | USHRIGHT | 20 | | 2 | `a >> b` (unsigned; unused) |
| 0x14 | ADD | 20 21 25 26 23 3A | | 2 | pop b, a; push `a + b`; SS concatenates strings; VV adds vectors (pops 6 cells, pushes 3) |
| 0x15 | SUB | 20 21 25 26 3A | | 2 | `a - b` |
| 0x16 | MUL | 20 21 25 26 3B 3C | | 2 | `a * b`; VF/FV scale a vector (pop 4 cells, push 3) |
| 0x17 | DIV | 20 21 25 26 3B | | 2 | `a / b`; VF divides a vector by a float |
| 0x18 | MOD | 20 | | 2 | `a % b` |
| 0x19 | NEG | 03 04 | | 2 | negate the top cell in place |
| 0x1A | COMP | 03 | | 2 | bitwise complement of the top cell |
| 0x1B | MOVSP | 00 | offset:i32 | 6 | SP += offset (always ≤ 0: pops `-offset` bytes, releasing what they held) |
| 0x1C | STORE_STATEALL | | | | obsolete; not emitted, not in the corpus |
| 0x1D | JMP | 00 | offset:i32 | 6 | jump to this instruction + offset |
| 0x1E | JSR | 00 | offset:i32 | 6 | push the return address (return stack) and jump |
| 0x1F | JZ | 00 | offset:i32 | 6 | pop an int; jump if it is 0 |
| 0x20 | RETN | 00 | | 2 | return to the caller; from the outermost frame, end the run |
| 0x21 | DESTRUCT | 01 | size:u16, keep_offset:i16, keep_size:u16 | 8 | remove the top `size` bytes except the `keep_size` bytes found `keep_offset` bytes into them, which stay on the stack (field access on a vector or struct) |
| 0x22 | NOT | 03 | | 2 | logical not of the top int, in place |
| 0x23 | DECISP | 03 | offset:i32 | 6 | decrement the int at SP+offset (no push or pop): `i--` on a local |
| 0x24 | INCISP | 03 | offset:i32 | 6 | increment it: `i++` |
| 0x25 | JNZ | 00 | offset:i32 | 6 | pop an int; jump if it is not 0 |
| 0x26 | CPDOWNBP | 01 | offset:i32, size:u16 | 8 | copy the top `size` bytes to BP+offset: assignment to a global |
| 0x27 | CPTOPBP | 01 | offset:i32, size:u16 | 8 | push a copy of `size` bytes from BP+offset: reading a global |
| 0x28 | DECIBP | 03 | offset:i32 | 6 | decrement the int at BP+offset |
| 0x29 | INCIBP | 03 | offset:i32 | 6 | increment it |
| 0x2A | SAVEBP | 00 | | 2 | BP := SP, then push the old BP (one cell) |
| 0x2B | RESTOREBP | 00 | | 2 | pop the saved cell back into BP |
| 0x2C | STORE_STATE | 10 | bp_bytes:i32, sp_bytes:i32 | 10 | save a resumable state; see [Actions](#action-arguments-store_state) |
| 0x2D | NOP | 00 | | 2 | nothing |

Notes:

- `EQUALTT`/`NEQUALTT` (0x24) compare two blocks of `size` bytes. The one use in the corpus is a
  vector comparison (`NEQUALTT 12`, `M12ab`'s `k_heartbeat`): **vectors compare as 12-byte
  structures**, not with a vector type byte. Locations compare with `NEQUALLOCLOC` (0x32).
- The naming is BioWare's: LOGAND/LOGOR are the logical `&&`/`||`, INCOR/EXCOR/BOOLAND the bitwise
  `|`/`^`/`&` (checked: `1 | 64` is `INCORII`, `GetGlobalNumber(..) & 1` is `BOOLANDII`).
- `RSADD` pushes "a default value". Scripts assign before reading; what the engine actually puts
  there (0, 0.0, "", OBJECT_INVALID, an empty effect) is for RE to confirm.
- The STORE_STATE type byte is not a type: it is the distance from the STORE_STATE to the
  first instruction of the deferred block (always 0x10 = the 10-byte STORE_STATE plus the 6-byte
  JMP that follows it).
- `CPTOPSP`/`CPDOWNSP` sizes are 4 or 12 (vectors); `CPTOPBP` also copies whole global structs
  (36 and 40 bytes) before a `DESTRUCT` picks the field.

## ACTION

`ACTION routine argc` calls engine routine number `routine` (the index of its prototype in
`nwscript.nss`, from 0) with `argc` arguments.

- **Arguments are pushed last first, so the first argument is on top.** `SetReturnStrref(TRUE,
  32228, 42465)` is `CONSTI 42465; CONSTI 32228; CONSTI 1; ACTION 152 3`. User functions are called
  the same way.
- **`argc` counts arguments, not cells**: a vector argument is one argument and three cells; an
  `action` argument is one argument and **no** cells (it is the saved state, see below).
- The routine pops its arguments and pushes its result: nothing for `void`, three cells for
  `vector`, one cell otherwise.
- **The compiler pushes default arguments explicitly**: `SetReturnStrref(FALSE, 38550)` passes 3.
  But `argc` can be **smaller** than the prototype's parameter count: 1093 call sites (in 8
  routines, e.g. `ActionStartConversation` with 11 of its 12 arguments, `StartNewModule` with 4 of
  8) come from scripts compiled before BioWare appended parameters to those prototypes. The
  engine must fill the missing trailing arguments with the prototype's defaults. Every other
  `argc` is between the required count and the total, except five sites in four scripts
  compiled against older prototypes (see Checked and nwscript.md): three pass one argument too
  many and two (`AddPartyMember`) one required argument too few. With too many, a handler that
  pops only its own parameters leaves the extra cells on the stack (harmless in `k_creditsplay`,
  whose `main` has no locals for later SP offsets to miss); where the top cell has the wrong type
  for the routine's first parameter, its pop fails (the other three cases).

## Action arguments: STORE_STATE

A parameter of type `action` (`AssignCommand`, `DelayCommand`, `ActionDoCommand`: the only three
routines that take one) is a piece of code to run later, in the context of the moment it was
created. The compiler emits it inline:

```
    STORE_STATE  bp_bytes sp_bytes      ; type byte 0x10: the deferred block starts 16 bytes on
    JMP          after                  ; skip the deferred block now
deferred:
    ...the action expression...         ; e.g. CONSTI 1; CPTOPSP -8 4; ACTION 385 2
    RETN
after:
    ...push the remaining arguments...  ; e.g. the delay for DelayCommand, the object for AssignCommand
    ACTION       7 2                    ; DelayCommand(fSeconds, <saved state>)
```

Because the action is the **last** parameter of all three routines, it is "pushed" first: the
STORE_STATE runs before the other arguments are pushed, and the ACTION that follows takes the
saved state from the VM's register instead of the stack.

- **What is saved**: `bp_bytes` is the size of the global variables (it equals the stack depth
  at `SAVEBP` in all 15688 STORE_STATEs of the unique scripts; 0 when there are no globals) and
  `sp_bytes` is the top of the stack that belongs to the current function: its return slot (if
  it returns a value), its arguments, its locals and any temporaries pushed so far. Checked: for
  every STORE_STATE, `sp_bytes` = current depth inside the function + its arguments' size + 4 if
  the function returns a value (1398 cases) or + 0 if `void` (16554 cases); inside a deferred
  block it equals the block's own depth.
- **How it resumes**: when the action is due (`AssignCommand` runs it as the target object,
  `DelayCommand` after the delay, `ActionDoCommand` when it reaches the head of OBJECT_SELF's
  action queue), the engine runs the same program again on a fresh stack: the saved `bp_bytes`
  of globals with BP just past them, then the saved `sp_bytes` of the frame, executing from the
  deferred block's first instruction to its `RETN`. That is what the bytecode requires: the
  deferred code addresses its locals with the same SP offsets as the function it came from and
  globals with the same BP offsets. Checked: every deferred block returns at exactly the depth
  it started at and never reads below the saved frame. The details on the engine side (the
  saved copies being private to the action, OBJECT_SELF being the saving object or
  `AssignCommand`'s target, scheduling) follow the routines' documented behaviour and are for RE
  to confirm.
- **Saved games confirm the model.** A save stores a pending action or `DelayCommand` as a
  "script situation" ([gff-save.md](gff-save.md)): the script's whole code, the resume offset
  (= the deferred block's first instruction) and the saved cells, with BP = `bp_bytes` / 4 and
  SP = (`bp_bytes` + `sp_bytes`) / 4 of the STORE_STATE that created it (checked on the two
  situations in the install's save).
- Deferred blocks nest: `DelayCommand(1.0, AssignCommand(o, ActionX()))` is a STORE_STATE whose
  deferred block contains another STORE_STATE + JMP + `ACTION 6 2` before its RETN.

Who consumes the saved state (the first ACTION with an `action` parameter after the JMP, at the
same nesting level): `AssignCommand` 6455, `DelayCommand` 5494, `ActionDoCommand` 3739, which
accounts for every STORE_STATE in the unique scripts. The commonest deferred bodies are
`JSR f; RETN` (a call to a user function), `CONSTI; CPTOPBP; JSR; RETN` and `ACTION 9 0; RETN`
(`ClearAllActions()`).

## Program layout

BioWare's compiler lays out every program the same way. There is no function table; the entry
point is the first instruction. The four shapes and how many unique scripts use each:

| Shape | Scripts | Entry |
|---|---|---|
| `void main()`, no globals | 2931 | `JSR main; RETN` |
| `void main()`, globals | 3032 | `JSR globals; RETN` |
| `int StartingConditional()`, no globals | 2012 | `RSADDI; JSR main; RETN` |
| `int StartingConditional()`, globals | 691 | `RSADDI; JSR globals; RETN` |

With globals, the `globals` subroutine pushes and initialises each global
(`RSADDI; CONSTI 5; CPDOWNSP -8 4; MOVSP -4` per variable, including every non-`const` global of
the included libraries), then:

```
    SAVEBP                     ; BP := just past the globals; old BP saved
    [RSADDI]                   ; StartingConditional only: main's return slot
    JSR main
    [CPDOWNSP -(G+12) 4]       ; StartingConditional only: copy main's result into the entry's slot
    [MOVSP -4]
    RESTOREBP
    MOVSP -G                   ; drop the G bytes of globals
    RETN
```

A **`StartingConditional`** script (a dialogue condition) leaves exactly one int on the stack at
the end of the run, in the slot the entry's `RSADDI` reserved; the engine reads that int as the
condition's result. A `void main()` script leaves the stack empty.

Inside functions:

- The caller reserves the return slot (`RSADD` of the return type) if the function returns a
  value, pushes the arguments last first, then `JSR`. The callee reads its arguments and writes
  its return slot with SP-relative copies reaching below its own frame, and before `RETN` pops
  its locals **and its arguments** (`MOVSP`), so a call's net effect is minus the arguments' size,
  leaving the return value where the caller reserved it.
- `return x;` copies x down into the return slot with `CPDOWNSP`, pops locals, then jumps to the
  function's final `RETN`. The compiler leaves unreachable cleanup (`MOVSP`, `JMP`) after such
  jumps all over the corpus: a VM must not assume every instruction is reachable.
- Locals are pushed where they are declared (`RSADDx`, then `CONST`/`CPDOWNSP`/`MOVSP` for an
  initialiser) and popped at the end of their block.
- `if`/`while`/`for` use forward `JZ` and backward `JMP`: every backward jump in the corpus is a
  `JMP` (5046) or a `JSR` to an earlier function; conditional jumps always go forward.
- `switch` keeps the value on the stack and tests it per case: `CPTOPSP -4 4; CONSTI k; EQUALII;
  JNZ case_k` (every `JNZ` in the corpus is one of these), then `MOVSP -4` at the end.
- `a && b` short-circuits: `a; CPTOPSP -4 4; JZ end; b; LOGANDII; end:`.
- `a || b` does **not** short-circuit: `a; CPTOPSP -4 4; JZ eval_b; CPTOPSP -4 4; JZ end;
  eval_b: b; end: LOGORII`. The second `JZ` tests a copy of a value already found non-zero, so it
  is never taken, and its target is one cell short; a static checker must prune it (ours does)
  and a VM simply never takes it. `b` is always evaluated, side effects included.
- Recursion exists (918 recursive subroutines across the unique scripts, mostly in the AI
  include `k_inc_generic`), so the return stack must grow as needed.
- Functions from `#include`d libraries are compiled into each script that calls them; uncalled
  ones are left out (a 851-byte condition that includes `k_inc_utility` contains only the one
  helper it calls). Their global variables, though, are all there, used or not, as the include
  stood when the script was compiled (many `k_inc_utility` users carry its 21 older globals, not
  the 27 of the shipped source).

## Open questions (for RE of swkotor.exe)

- What exactly `RSADD` pushes for each type, and how the engine represents `OBJECT_SELF` and
  `OBJECT_INVALID` (0 and 1 in the bytecode) internally.
- What the engine does when `argc` is larger than the routine's parameter count, or when the
  pushed types don't match (the four sites in Checked), and how it fills omitted trailing
  defaults. The routine handlers pop typed values and return an error on a type mismatch
  ([../re/nwscript-routines.md](../re/nwscript-routines.md)), so the VM's stack cells are typed;
  what the VM does with that error is open.
- Division and modulo by zero, and integer overflow.
- Instruction limits or recursion limits the engine enforces (NWN had an instruction cap).

## Checked

```
python kotor/tools/py/ncsdis.py --corpus          # writes kotor/extract/ncs-stats.txt
python kotor/tools/py/ncsdis.py k_con_comactive   # disassemble one, by resref or path
```

Files: every NCS copy in the install, `kres.Game().every_entry('ncs')`: **13139 copies**
(scripts.bif 1784, module `_s.rim`s 10863, `rims/` 492), **8666 unique by content**, 9714
unique by (resref, content), 8926 distinct resrefs.

Per file the probe checks the magic, the 0x42 byte, the big-endian size against the real size,
that every instruction decodes to an (opcode, type) pair from the table above with its operands
inside the file, that the code ends exactly at the end of the file, that every
`JMP`/`JSR`/`JZ`/`JNZ` target and every STORE_STATE resume point is an instruction start, and
that every STORE_STATE is followed by a `JMP`. **Failures: 0.** No opcode or type byte outside
the table occurs; 0x1C (STORE_STATEALL) never occurs.

It then runs a **stack-depth check** over each unique script: it walks the entry point, every
subroutine and every deferred block, tracking the depth with the stack effects above and each
ACTION's effect computed from its prototype in `nwscript.nss` (first `argc` parameters; vector 3
cells, action 0, others 1; result likewise), and requires that every path reaching an
instruction has the same depth, every RETN of a subroutine is at the same depth, a deferred
block returns at its starting depth and never reaches below its saved frame, and the entry
never reads below its start. It prunes the never-taken `||` branch (45343 of them) and solves
recursive subroutines by learning their effect from their non-recursive returns, then
re-walking. **8662 of 8666 pass; the other 4 are explained:**

| Script | Where | What |
|---|---|---|
| `nw_s0_lghtnbolt` | scripts.bif | A leftover test spell script. Its shipped source calls `GetIsReactionTypeFriendly(oTarget)`, which the shipped `nwscript.nss` no longer declares; the NCS was compiled against an older table in which routine 469 was that 2-parameter routine (now `EffectBlasterDeflectionIncrease`, 1 parameter). |
| `k_creditsplay` | STUNT_57 | `StartCreditSequence` (518) called with 2 arguments (int on top, then a string); the prototype now takes 1 int. |
| `k_plev_corpse1` | lev_m40aa | `ActionBarkString` (700) called with 2 arguments (an object on top, then strref 1075); the prototype now takes 1 int. |
| `k_ptar_drunk_ud` | tar_m02ab | A compiler bug: a `string` local declared inside a `switch` case is never popped (the case's `break` jumps over its `MOVSP`), so that path leaves the switch one cell deeper. Harmless at run time (nothing addresses that cell), but a VM must not assume path-independent depths. |

The other argument-count anomaly, `AddPartyMember` (574, `int nNPC, object oCreature`) called
with 1 argument by `k_act_carthjoin` (Taris modules) and `k_ptar_missjoin`, is consistent stack-wise
(it pushes one object) and comes from an older one-parameter prototype; see nwscript.md.

Opcode and type usage (instructions over all copies, over unique contents, and unique files using
it):

| Op type | Mnemonic | All copies | Unique | Files |
|---|---|---|---|---|
| `01 01` | CPDOWNSP | 715,093 | 566,245 | 6,798 |
| `02 03` | RSADDI | 555,371 | 441,436 | 6,060 |
| `02 04` | RSADDF | 5,056 | 3,959 | 846 |
| `02 05` | RSADDS | 26,734 | 19,911 | 1,673 |
| `02 06` | RSADDO | 26,788 | 23,191 | 4,166 |
| `02 10` | RSADDEFFECT | 1,099 | 817 | 465 |
| `02 11` | RSADDEVENT | 36 | 35 | 34 |
| `02 12` | RSADDLOCATION | 662 | 634 | 315 |
| `02 13` | RSADDTALENT | 15,163 | 13,973 | 214 |
| `03 01` | CPTOPSP | 621,372 | 496,074 | 6,265 |
| `04 03` | CONSTI | 896,463 | 718,476 | 8,359 |
| `04 04` | CONSTF | 53,942 | 43,389 | 3,610 |
| `04 05` | CONSTS | 134,928 | 99,508 | 7,853 |
| `04 06` | CONSTO | 104,334 | 86,080 | 2,860 |
| `05 00` | ACTION | 347,753 | 285,015 | 8,647 |
| `06 20` | LOGANDII | 69,149 | 55,232 | 2,796 |
| `07 20` | LOGORII | 49,045 | 42,973 | 1,933 |
| `08 20` | INCORII | 56 | 26 | 12 |
| `0A 20` | BOOLANDII | 12 | 12 | 9 |
| `0B 20` | EQUALII | 172,895 | 138,936 | 4,524 |
| `0B 21` | EQUALFF | 6 | 2 | 1 |
| `0B 22` | EQUALOO | 935 | 855 | 559 |
| `0B 23` | EQUALSS | 669 | 541 | 240 |
| `0C 20` | NEQUALII | 7,374 | 5,949 | 658 |
| `0C 22` | NEQUALOO | 561 | 490 | 240 |
| `0C 23` | NEQUALSS | 5,653 | 2,722 | 519 |
| `0C 24` | NEQUALTT (size 12) | 1 | 1 | 1 |
| `0C 32` | NEQUALLOCLOC | 1 | 1 | 1 |
| `0D 20` | GEQII | 3,078 | 2,370 | 1,491 |
| `0D 21` | GEQFF | 6 | 5 | 5 |
| `0E 20` | GTII | 19,881 | 15,757 | 1,851 |
| `0E 21` | GTFF | 1,535 | 1,421 | 298 |
| `0F 20` | LTII | 9,378 | 6,318 | 1,319 |
| `0F 21` | LTFF | 3,106 | 2,115 | 563 |
| `10 20` | LEQII | 4,704 | 3,559 | 1,644 |
| `10 21` | LEQFF | 1,370 | 1,005 | 538 |
| `11 20` | SHLEFTII | 1 | 1 | 1 |
| `14 20` | ADDII | 8,867 | 5,207 | 895 |
| `14 21` | ADDFF | 299 | 263 | 108 |
| `14 23` | ADDSS | 33,382 | 24,094 | 880 |
| `14 25` | ADDIF | 72 | 72 | 36 |
| `14 26` | ADDFI | 22 | 22 | 4 |
| `15 20` | SUBII | 2,233 | 1,532 | 769 |
| `15 21` | SUBFF | 42 | 40 | 9 |
| `15 26` | SUBFI | 12 | 12 | 3 |
| `16 20` | MULII | 2,744 | 2,292 | 774 |
| `16 21` | MULFF | 199 | 191 | 46 |
| `16 25` | MULIF | 161 | 161 | 50 |
| `16 26` | MULFI | 18 | 15 | 8 |
| `17 20` | DIVII | 139 | 79 | 31 |
| `17 21` | DIVFF | 1,931 | 1,496 | 620 |
| `17 25` | DIVIF | 10 | 10 | 7 |
| `18 20` | MODII | 3 | 1 | 1 |
| `19 03` | NEGI | 24,088 | 20,733 | 3,512 |
| `19 04` | NEGF | 42 | 35 | 34 |
| `1B 00` | MOVSP | 878,225 | 699,919 | 6,989 |
| `1D 00` | JMP | 313,943 | 252,465 | 6,855 |
| `1E 00` | JSR | 153,561 | 117,537 | 8,666 |
| `1F 00` | JZ | 365,678 | 302,865 | 4,673 |
| `20 00` | RETN | 81,841 | 62,906 | 8,666 |
| `21 01` | DESTRUCT | 2,520 | 2,341 | 246 |
| `22 03` | NOTI | 14,368 | 12,037 | 1,466 |
| `23 03` | DECISPI | 11,305 | 10,389 | 235 |
| `24 03` | INCISPI | 11,414 | 9,963 | 997 |
| `25 00` | JNZ | 23,527 | 11,896 | 624 |
| `26 01` | CPDOWNBP | 2,745 | 2,328 | 202 |
| `27 01` | CPTOPBP | 77,255 | 59,967 | 2,086 |
| `2A 00` | SAVEBP | 4,625 | 3,723 | 3,723 |
| `2B 00` | RESTOREBP | 4,625 | 3,723 | 3,723 |
| `2C 10` | STORE_STATE | 18,000 | 15,688 | 2,956 |

Defined but never used in the corpus: EXCORII, EQUALTT, all EQUAL/NEQUAL engine pairs except
NEQUALLOCLOC, NEQUALFF, SHRIGHTII, USHRIGHTII, the vector arithmetic forms (ADDVV, SUBVV, MULVF,
MULFV, DIVVF), SUBIF, DIVFI, COMPI, DECIBPI, INCIBPI, NOP and STORE_STATEALL. A VM should still
implement the defined ones (they are cheap), but nothing in the shipped game exercises them.

Full statistics, including ACTION usage per routine and the STORE_STATE operand distribution,
are in `kotor/extract/ncs-stats.txt` after a run (git-ignored). The routine usage is also in
[nwscript-routines.tsv](nwscript-routines.tsv).
