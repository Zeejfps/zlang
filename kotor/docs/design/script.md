# Scripting: the NWScript VM and its engine interface

How the game runs compiled NWScript (NCS): `kotor/lib/script`. The bytecode is described in
[../formats/ncs.md](../formats/ncs.md), the routines and types in
[../formats/nwscript.md](../formats/nwscript.md), what swkotor.exe's own VM does in
[../re/vm.md](../re/vm.md), and how saves keep pending actions in
[../formats/gff-save.md](../formats/gff-save.md). The VM reproduces the original's semantics
(including its quirks) and gives the engine one narrow seam.

## Files

| File | Namespace | What |
|---|---|---|
| `lib/script/ncs.ctx` | `ncs` | the NCS header and one instruction at a time, as the file has it; opcode and type-byte names |
| `lib/script/nwvm.ctx` | `nwvm` | programs (decoded scripts), the VM, the engine interface, routine accessors, situations, faults |
| `lib/script/nwarg.ctx` | `nwarg` | a routine's arguments with the prototype's defaults filled in |
| `lib/script/nwstub.ctx` | `nwstub` | a stand-in engine for tests and tools; `fallback` for routines an engine hasn't written |
| `lib/script/routines.ctx` | `nwscript` | generated: the 772 routines (name, result, parameters with defaults), `const Name: u16` ids |
| `lib/script/constants.ctx` | `nwconst` | generated: nwscript.nss's 1,490 constants |
| `tools/ncsdis` | | the disassembler (byte for byte `tools/py/ncsdis.py`'s output) |
| `tools/ncsrun` | | runs every script in the game, or given files, on the stub engine; resumes saved actions |

`kotor/tools/py/nwscript_ctx.py` regenerates the two tables from the game's `nwscript.nss`;
`ncsvmtest.py` (semantic tests), `ncsbench.py` (a benchmark), `ncsasm.py` (a small assembler),
`ncssituations.py` (a save's actions) and `ncsextract.py` serve the tools.

## Programs

```
let program = try nwvm::load(S){ realloc, &heap, name = "k_ai_master", bytes }
```

`load` checks the header (magic and the `B` byte; the size field is ignored, as the engine ignores
it), decodes every instruction, and checks that every jump target and STORE_STATE resume point is
an instruction. A file that fails is an error value, never a crash. The result is a
`Program { name, code, ins, at }`: `ins` holds one `Ins { op, a, b, c }` per instruction with the
opcode and type byte folded into one `Op` (`add_ii`, `add_if`, `equal`, ...), sizes in cells,
SP-relative offsets as distances below SP, and jump targets as instruction indexes, plus a final
`end` that faults if the code runs off its end; `at` holds each instruction's file offset (for
fault messages and save games). The program views `name` and `bytes` (CONSTS strings point into
them): both must outlive it. Memory comes from the allocator given; `free_program` returns it.

The engine should keep one Program per script for the session (a cache by resref, filled through
`res::load`), since situations point at their program (below), and decoding is cheap but not free.

## The VM

```
let mut vm = try nwvm::new(S){ realloc, &heap, limits = nwvm::LIMITS }
let answer = nwvm::run{ &vm, program = &program, self = creature_id, engine }   // !?i32
```

One `Vm` serves the whole game: it is idle between runs, and a run leaves nothing behind. Its
state is the cell stack (`types`, `vals`, `sp`, `bp`), the return-address stack (128 entries),
the levels of nested scripts (program and OBJECT_SELF of each, at most 8), the instruction count,
the last STORE_STATE (`saved`), string memory, the last result and the last fault.

- **Cells** are 4 bytes plus a type tag, numbered as the engine and its saves number them: 3 int,
  4 float, 5 string, 6 object, 0x10 + n for engine structure n (effect, event, location,
  talent). Every SP/BP offset and size in the bytecode is in bytes and becomes cells. A vector is
  three float cells, z on top; a script struct is its fields' cells.
- **`run`** runs a program from its first instruction with OBJECT_SELF `self` (OBJECT_INVALID for
  none) until its outermost RETN, and returns the int it left (a StartingConditional's answer) or
  null. Called while a script is running (a routine running another, as ExecuteScript does) it
  runs nested: on the same stack, budget and return stack, one level deeper, and a nested fault
  leaves the caller's stack as it was. As in the game, the value returned is the last int any
  script left in the run: a void script that ExecuteScripts a conditional reports the
  conditional's answer.
- **Limits** (`nwvm::Limits`, the game's where it has one): the instruction budget (the 131,072nd
  instruction of an outermost run fails; nested runs share it), 8 nested scripts, 127 return
  addresses, and ours: 65,536 stack cells, 16,384 live strings, 1 MiB of strings made per run.
- **Faults.** A run that goes wrong stops where it is, keeps the effects it already had (as in the
  game, whose VM drops errors silently), and fails with `nwvm::faulted`; `vm.fault` holds the
  `FaultKind`, the script, the instruction's file offset (as the disassembler shows it), its
  opcode, the routine and argument count for an ACTION, and the types involved.
  `nwvm::describe` writes it as one line:
  `k_ai_master @ 000001a4 ACTION 7 2 (DelayCommand): wrong type: wanted float, found string`.
  The engine should log faults; the game itself never did.

What follows the engine exactly, with tests in `ncsvmtest.py` (docs/re/vm.md has the addresses):
int arithmetic wraps; division and modulo by zero fault (int, float and vector), and so does
INT_MIN / -1 (the engine would crash); SHLEFT and the shifts mask their count by 31, SHRIGHT
rounds toward zero, USHRIGHT sign-extends; EQUAL/NEQUAL compare cell by cell by the top operand's
cell type, so ints, floats (0.0 is not -0.0) and objects compare their 32 bits, strings ignore
ASCII case, and engine values go to the engine; CONSTS text ends at a NUL; CONSTO 0 is the
running level's OBJECT_SELF and anything else OBJECT_INVALID; RSADD pushes 0, 0.0, "",
OBJECT_INVALID or engine handle 0; INC/DEC skip a cell that isn't an int; a positive MOVSP does
nothing; NOP is an invalid opcode; STORE_STATEALL is supported. Where the engine reads outside the
stack or through a wrong pointer (a copy above SP, a DESTRUCT whose kept part reaches past its
block, a string compared with an int), the VM faults instead.

Speed: a loop of the compiler's commonest instructions runs at about 450 million instructions a
second at -O2 (`ncsbench.py`, then `ncsrun kotor/out/ncsbench.ncs --budget 4000000000 --repeat
5`); a run of every script in the game with its actions, where most time goes to the stub's
routines, at about 95 million.

## The engine interface

The VM reaches the engine through one bound function, passed to every `run` and `resume`:

```
type Engine = &fn{ mut vm: Vm, call: Call } -> Reply

union Call {
    action{ routine: u16, argc: u8 },              // ACTION: run engine routine `routine`
    equal{ kind: EngineType, a: u32, b: u32 },     // EQUAL/NEQUAL on two engine values
}
union Reply { done, failed, equal{ same: bool } }
```

The engine binds it to its own state once (`world::script_call{ &world, _ }`) and passes it down;
binding per run would leak a record each time, since ctxlang never frees bind records. The VM is
not part of that state: `vm` is passed to the call (keep the `Vm` out of the struct the bind
holds, or the two `&` overlap).

**A routine** pops its arguments in declaration order (the first is on top) with the typed
accessors and pushes its result, then replies `done`; on any failure it replies `failed` and the
script stops, as the game's handlers make it (their -2001):

| Accessor | What |
|---|---|
| `pop_int`, `pop_float`, `pop_object`, `pop_vector` | the top cell(s), which must be of that type |
| `pop_string` | a view of the bytes, valid until the outermost run ends: copy it to keep it |
| `pop_engine{ kind }` | an engine value's handle |
| `pop_situation(S)` | the action argument (below) |
| `push_int`, `push_float`, `push_object`, `push_vector`, `push_string` (copies), `push_engine` | the result |
| `self_object{ vm }` | OBJECT_SELF of the running script (it changes with ExecuteScript's nesting) |
| `fail{ &vm, why }` | the routine's own reason, before it replies `failed` |
| `nwarg::int/float/string/object/vector/engine{ &vm, routine, argc, i }` | argument `i`: popped if the script passed it, else the prototype's default |

Every accessor fails (and records why in `vm.fault`) on an empty stack, a cell of another type
or a full stack; handlers write `try` and let the wrapper reply `failed`. `argc` is what the
script passed: old scripts pass fewer arguments than the shipped prototypes have (1,093 call
sites), which `nwarg` fills with the defaults; four scripts pass more, and a handler that pops only
its own leaves the rest, as the game's do.

**Dispatch.** Because a ctxlang function that uses `try` can't be a function value, routines
can't sit in a table of handlers; the engine's dispatcher is a chain of direct calls, which gcc
turns into a jump table:

```
fn script_call { mut world: World, mut vm: nwvm::Vm, call: nwvm::Call } -> nwvm::Reply {
    match call {
        action{ routine, argc } => {
            dispatch{ &world, &vm, routine, argc } iferr { return nwvm::Reply::failed }
            return nwvm::Reply::done
        }
        equal{ kind, a, b } => { return nwvm::Reply::equal{ same = values::equal{ world, kind, a, b } } }
    }
}

fn dispatch { mut world: World, mut vm: nwvm::Vm, routine: u16, argc: u8 } -> ! {
    if routine == nwscript::GetObjectByTag { return get_object_by_tag{ &world, &vm, argc } }
    if routine == nwscript::DelayCommand { return delay_command{ &world, &vm, argc } }
    ...
    return nwstub::fallback{ &vm, routine, argc }      // not written yet: pop, push a zero result
}
```

`nwscript::ROUTINES[routine]` gives the prototype; routines are numbered as `nwscript.nss`
declares them and as `ACTION` names them. `nwstub::fallback` lets the engine grow one routine at
a time: it pops whatever arguments the script passed and pushes the result type's zero value.

**ExecuteScript** runs the named script at once, nested, as `oTarget` (OBJECT_INVALID if the
caller's OBJECT_SELF isn't valid): `nwvm::run` from inside the handler, with the same engine
bound again (once per call). Its result and faults don't concern the caller; `nScriptVar` goes
where GetRunScriptVar reads it.

## Objects, strings and engine values

- **Objects** are the engine's 32-bit object ids, the same ids save games use. OBJECT_INVALID is
  0x7F000000; the bytecode's only object constants are 0 (OBJECT_SELF) and 1 (OBJECT_INVALID),
  which CONSTO resolves when it runs. The VM never looks inside an id.
- **Strings** are immutable. A string cell holds a slot in the VM; a slot holds a view of bytes in
  a program's code (CONSTS), in the VM's per-run text memory (ADDSS, `push_string`), or in a
  situation being resumed. Copying a cell shares the slot; slots no cell holds are found again
  when they run out, and text memory is reset when the outermost run ends. So a string a routine
  pops is valid until then, and one it keeps must be copied.
- **Engine values** (effect, event, location, talent) are handles the engine gives out and owns:
  the VM copies them as plain 32-bit cells and never frees them. Handle 0 is each type's default
  value (an empty effect, a location at the origin, ...), which RSADD pushes; the engine must
  accept it. Scripts never change an engine value in place (every Effect*, EventUserDefined,
  Location, ... makes a new one), so sharing a handle between cells is safe. The engine decides
  how long values live: the natural rule is that values made during a run die when the outermost
  run returns, unless something keeps them: an effect applied to an object or a location stored
  in a global is copied into the engine's own state, and a situation keeps the values in its
  cells (below). EQUAL/NEQUAL on two engine values asks the engine (`Call::equal`): an effect by
  its id, a location by position and orientation, an event by type and parameter lists, a talent
  by all fields, as the game compares them.

## Actions: STORE_STATE, situations, delayed commands

An `action` argument (AssignCommand 6, DelayCommand 7, ActionDoCommand 294) is code to run later.
The compiler emits `STORE_STATE globals frame; JMP over; <the action>; RETN`, and the VM records
the resume point and the two sizes. The routine that takes the action calls

```
let situation = try nwvm::pop_situation(S){ &vm, realloc, &heap }
```

which copies what the action needs out of the stack, as the engine's CopyFromStack does: the
`globals` bytes below BP become the first cells (and the new BP), the `frame` bytes below SP
follow; both 0 keeps the whole stack. A `Situation` holds its program (a pointer: the engine's
script cache must outlive it), the resume instruction, BP, the cells, and copies of their strings,
in memory from the allocator given; `free_situation` returns it. Engine values in it are handles:
the engine must keep each value alive while it keeps the situation (walk the cells whose type is
0x10..0x13 when taking one, and release them when freeing it).

Running one: `nwvm::resume{ &vm, situation, self, engine }` replaces the (idle) stack with the
situation's cells and runs from the resume point to the action's RETN, with a fresh budget, as
OBJECT_SELF `self`. It refuses (`busy`) while a script runs: the engine runs actions from its
event and action queues, between scripts. The situation must outlive the call; the engine frees
it after (or keeps it to run again).

What the engine does with each, as the game does (docs/re/vm.md, "The handlers"):

| Routine | Takes | Keeps the situation as | Runs it |
|---|---|---|---|
| AssignCommand(oActionSubject, aAction) | the object, then the action | an AI event (id 1) with no delay, caller = OBJECT_SELF, target = the object; dropped if the object doesn't exist | on the next AI update, never inline, as the target |
| DelayCommand(fSeconds, aAction) | the delay, then the action | an AI event (id 1) due in `(int)(fSeconds * 1000)` ms, caller = target = OBJECT_SELF; dropped unless OBJECT_SELF exists | when due, as OBJECT_SELF |
| ActionDoCommand(aAction) | the action | an action (type 37, "do command") at the end of OBJECT_SELF's queue, its one parameter of type 5; dropped if the object isn't commandable | when it reaches the head of the queue, as that object |

Actions nest: running one may hand on others (`DelayCommand(1.0, AssignCommand(o, ...))`), each
a new situation.

## Saving and loading situations

A save stores each pending situation as gff-save.md's "script situation": in the module IFO's
`EventQueue` (an event with `EventId` 1, `EventData` struct 0x7777) and in objects'
`ActionList/Paramaters` (type 5). Field by field:

| GFF field | From a Situation | Into one (`make_situation`) |
|---|---|---|
| `Name` | `program.name` | the script cache's key |
| `Code`, `CodeSize` | `program.code[13..]`, its length | decode `NCS V1.0B` + size + `Code` with `nwvm::load` |
| `InstructionPtr` | `nwvm::instruction_ptr{ situation }` (file offset - 13) | `instruction_ptr` |
| `SecondaryPtr`, `CRC` | 0, 0 | skip a situation whose CRC isn't 0, as the game does |
| `StackSize` | `situation.stack_size` (SP when it was taken) | `stack_size` |
| `Stack.BasePointer` | `situation.bp` | `base_pointer` |
| `Stack.StackPointer` | the cell count | the cells' count |
| `Stack.TotalSize` | the cell count + 16, as the engine sizes it | (ignored) |
| `Stack.Stack[i]` (`Type`, `Value`) | `nwvm::saved_cell{ situation, i }`: int, float, string, object id, or engine value | `cells[i]`: a `nwvm::SavedCell` |
| `...GameDefinedStrct` | the engine writes the value behind the handle | the engine reads it and makes a handle |

The game embeds the code in every saved situation and runs the saved code after a load, not the
resource's, which may differ; the engine should key loaded programs by name and content. Both of
the install's save's situations (`k_pend_area02` with 194 cells, globals and an effect, and
`k_pend_weld01`) rebuild and resume to their end through `make_situation` (`ncssituations.py`,
then `ncsrun FILE.sit`).

## How it was checked

- `ncsdis` disassembles all 8,666 distinct scripts identically to `ncsdis.py` (5,147,813 lines,
  compared with `cmp`): `ncsdis --corpus kotor/extract/ncs -o kotor/out/ncsdis-ctx.txt` and
  `python kotor/tools/py/ncsdis_corpus.py`.
- `ncsrun` (no arguments) loads every NCS the game's search finds, global and in each module,
  through lib/res (12,647 found, 8,666 distinct), runs each with every action it hands on, and
  sorts the ends: no VM faults; 4 routine faults, the four scripts compiled against older
  prototypes (ncs.md, "Checked"); 151 runs out of budget, loops that wait on routine results the
  stub doesn't give.
- `python kotor/tools/py/ncsvmtest.py`: 125 programs that pin down the semantics above, nested
  ExecuteScript, actions with globals and frames, and the save's situations.

## Left for the engine stage

The routines themselves (772; `nwscript-routines.tsv` ranks them by use), the engine-value store
with its lifetimes and comparisons, the event and action queues that keep and run situations,
reading and writing them in saves, the script cache, and logging faults. The VM side is complete:
an engine replaces `nwstub` with its own `Engine`.
