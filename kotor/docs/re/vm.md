# The NWScript virtual machine in swkotor.exe

How the engine loads and runs compiled NWScript (`.ncs`, resource type 2010). Addresses are for
the Steam `swkotor.exe` after SteamStub removal. Names are ours, in the Aurora/NWN vocabulary
(`CVirtualMachine`, `CVirtualMachineStack`, `CVirtualMachineScript`,
`CVirtualMachineCmdImplementer`); Ghidra still shows most of them as `FUN_...` until the
proposals in `kotor/re/proposals/vm.tsv` are merged. Confidence: **high** = read in the code and
consistent everywhere it is used; **med** = behaviour clear, name or a detail inferred; **low** =
a guess.

The short version for an implementer: KOTOR's VM is the NWN 1.x VM almost unchanged. The opcode
set and encodings are the ones documented for NWN/KOTOR NCS; the differences that matter are
listed under [Quirks](#quirks-a-compatible-vm-must-reproduce).

## Objects

| Object | Size | Where | What |
|---|---|---|---|
| `CVirtualMachine` | 4 | `g_pVirtualMachine` 0x007a3a00 | a facade: its only field is a pointer to the internal object. Every public method is a 7-byte thunk that loads that pointer and jumps to the internal method (high) |
| `CVirtualMachineInternal` | 0x3d8 | created by 0x005d0f40 | the real VM: return value, counters, 8 script slots, per-level OBJECT_SELF, the runtime stack, the return-address stack, the saved-state registers, the command implementer. Derives from `CResHelper<CResNCS,2010>` at offset 0, which is how it loads NCS files (high) |
| `CVirtualMachineStack` | 0x18 | embedded at VM+0x1ac; also heap copies inside saved situations | the value stack: parallel arrays of type bytes and 32-bit values (high) |
| `CVirtualMachineScript` | 0x28 | 8 slots at VM+0x2c; also heap objects = "script situations" | one loaded script (code, name) or one saved continuation (code or name, IP, stack copy) (high) |
| `CSWVirtualMachineCommands` | 0x10 | created next to the VM in 0x004b63e0, vtable 0x007450e4 | the command implementer: routine table, OBJECT_SELF for handlers, engine-structure hooks (high) |
| `CResNCS` | 0x34 | vtable 0x0074c508 | the NCS resource (`CRes` subclass); +0x28 loaded flag, +0x2c size, +0x30 data (high) |

Start-up (0x004b63e0, med: the app's server initialisation) does: `g_pVirtualMachine = new
CVirtualMachine` (0x005d0f40, which allocates the 0x3d8-byte internal object and runs its
constructor 0x005d4900), then `new CSWVirtualMachineCommands` (vtable only), then
`SetCommandImplementer` (0x005d0ff0 → 0x005d1a40), which stores the pointer at VM+0x3d4 and calls
the implementer's virtual `InitializeCommands` (slot 1, 0x0054c960) to fill the 772-entry routine
table. Shutdown (0x004b7c60) deletes the VM through 0x005d0fb0 (virtual destructor of the internal
object, 0x005d4c10 → 0x005d49b0).

## Loading an NCS file

| Address | Name | What it does | Conf. |
|---|---|---|---|
| 0x005d2260 | `CVirtualMachineInternal::ReadScriptFile(CExoString* name)` | Opens a new script level and loads `name.ncs` into it. Steps: recursion level +1, refusing (−94) if that would exceed 7 (8 levels, 0..7); points the CResHelper at the name (0x005d1ac0); demands the resource (0x00409b10); if that fails, level −1 and −95. Stores the name in the slot. Checks the header: bytes 0..4 `"NCS V"`, byte 6 `'.'`, version = digits 5 and 7 (each counted only if `'1'..'9'`) must give 10, byte 8 must be `'B'` (0x42); otherwise level −1, resource released, −96. On success copies bytes 13..end into a fresh buffer owned by the slot (0x005d16f0), releases the resource and resets the resref to `""`. Returns 0. | high |
| 0x005d16f0 | `CVirtualMachineInternal::InitializeScript(slot, code, size)` | fills a script slot: no stack, IP field 13, secondary IP 0, new copy of the code, size, loaded-from-save 0, CRC 0 | high |
| 0x005d1ac0 | `CResHelperNCS::SetResRef(resref, bAutoRequest)` | `CResHelper<CResNCS,2010>::SetResRef`: if the resref changes, drops the old `CResNCS` (release, delete when unreferenced), finds or creates the `CResNCS` for (resref, 2010) in the resource manager (0x004074d0 get, `new CResNCS` 0x005d4c30, 0x00407680 register), optionally requests it | high |
| 0x005d1a60 / 0x005d1c20 | `CResHelperNCS` destructor / deleting destructor | vtable 0x0074c490 | high |
| 0x005d4c30 / 0x005d4c50 / 0x005d4c90 | `CResNCS` constructor / destructor / deleting destructor | vtable 0x0074c508; the "resource serviced" slot 0x005d4c60 is a folded function shared with other `CRes` types (copies the data pointer and size to +0x30/+0x2c, sets +0x28) | high |

Consequences:

- The 4-byte big-endian size at bytes 9..12 is **never read**. The code length is the resource
  size minus 13.
- Code addresses inside the VM are offsets into the code buffer, i.e. file offset − 13. They show
  up in save games (`InstructionPtr`), so a compatible VM must use the same origin.
- There is no script cache in the VM: every `RunScript` demands the resource again and copies the
  code (the resource manager may keep its own copy).

## Running a script

| Address | Name | What it does | Conf. |
|---|---|---|---|
| 0x005d0fc0 → 0x005d45d0 | `RunScript(CExoString* name, OBJECT_ID oid, BOOL bOidValid)` | see below; returns 1 on success, 0 on any failure | high |
| 0x005d4270 | `CVirtualMachineInternal::RunScriptFile(int ip)` | runs the code of the current level from `ip`: clears the return value (+0x1c, +0x20), pushes −1 on the return-address stack, calls `ExecuteCode`. If the result is negative or the return-address stack did not come back to its entry depth, it calls the implementer's `ReportError(name, −result)` (slot 4) and cuts the value stack back to its entry SP and the return stack to its entry depth. Returns the `ExecuteCode` result (0 = ok) | high |
| 0x005d2bd0 | `CVirtualMachineInternal::ExecuteCode(int* pIP, char* code, int size)` | the interpreter loop, [below](#the-interpreter-loop) | high |
| 0x005d0fe0 → 0x005d1820 | `GetRunScriptReturnValue(int* type, int* value)` | succeeds only if the last run left an int: type 3 and the value | high |

`RunScript` step by step:

1. Fails if the name is null or empty (0x005e58a0).
2. If no script is running (level == −1): clears the runtime stack, zeroes the instruction counter
   (+0x24) and the return-stack depth (+0x1c4). Nested calls (`ExecuteScript` from a running
   script) keep all three, so nested scripts share the caller's stack, return stack and
   **instruction budget**.
3. `ReadScriptFile` (level + 1). On failure returns 0.
4. Stores `bOidValid` / `oid` in the per-level arrays (+0x16c / +0x18c), clears the slot's CRC
   field, calls the implementer's `RunScriptCallback(name)` (slot 3) and copies the level's
   `bOidValid` / `oid` into the implementer (+4 / +8), which is where every routine handler reads
   OBJECT_SELF.
5. Remembers SP, runs `RunScriptFile(0)` (code offset 0 = file offset 13).
6. Frees the slot (0x005d44f0), level − 1, and if a level is still running, restores the
   implementer's OBJECT_SELF to that level's values.
7. On success: if exactly one cell was left above the remembered SP, and it is an int, that is the
   script's return value (type 3 at +0x1c, value at +0x20; this is how `StartingConditional`
   scripts report, e.g. the dialog condition check 0x0059ec90: empty script name = true, else
   `RunScript` and `GetRunScriptReturnValue` != 0). Leftover cells are popped. If the stack
   did not come back to the remembered SP or SP + 1, `RunScript` returns 0. When the outermost
   script ends, the stack is cleared.

OBJECT_SELF: the `CONST object` instruction with value 0 pushes the current level's `oid` if its
`bOidValid` is exactly 1, otherwise OBJECT_INVALID (0x7f000000); any other constant value
(normally 1) pushes OBJECT_INVALID (high).

Limits (high):

| Limit | Value | Error |
|---|---|---|
| nested scripts (recursion levels) | 8 (levels 0..7) | −94 |
| instructions per outermost run (counter at +0x24, shared by nested scripts, reset by `RunScriptSituation`) | the 131,072nd instruction fails (counter ≥ 0x20000) | −93 |
| return addresses (JSR depth), shared by nested scripts, one entry used by the −1 sentinel of each run | 128-entry array; the JSR that would fill the last entry fails, so 127 entries usable | −99 |
| value stack | none (grows by 256 cells as needed) | — |

Errors and logging: KOTOR's `ReportError` (implementer slot 4) is the folded empty stub 0x005b5e90
(`ret 8`), so script errors are **silent**: no log strings exist for the VM. A failing script just
stops; its effects up to that point stay. Handler errors are the same: a routine handler returning
a negative value (−2001 when a pop fails, −2002 for an unknown routine from `RunCommand`) aborts the
script with that code.

### Error codes (returned by `ExecuteCode` / `ReadScriptFile`)

| Code | Meaning | Conf. |
|---|---|---|
| −93 | instruction limit reached | high |
| −94 | more than 8 nested scripts | high |
| −95 | script resource not found (demand failed) | high |
| −96 | bad NCS header (magic, version, `'B'`) | high |
| −97 | invalid type qualifier for the opcode | high |
| −99 | push failed (engine-structure push without implementer) or JSR depth exhausted | high |
| −100 | stack underflow / wrong type on a pop / copy offset below 0 / RETN with no return address | high |
| −101 | unknown opcode (0x00, 0x2D NOP, ≥ 0x2E) | high |
| −105 | division or modulo by zero (int, float, vector / float) | high |
| −107 | instruction pointer past the end of the code | high |
| −108 | no command implementer (ACTION, engine-structure compare) | high |
| −109 | EQUAL/NEQUAL met a cell type it cannot compare | high |
| −2001 / −2002 | from routine handlers: argument pop failed / no such routine | high |

## The interpreter loop

`ExecuteCode` (0x005d2bd0) loops while `*pIP != −1`. Before each instruction it fails with −107 if
`IP + 1 >= size` and with −93 when the incremented instruction counter reaches 0x20000. It reads
the opcode byte and the type byte (`code[IP+1]`) and dispatches through a jump table for opcodes
1..0x2C (0x005d41b4); anything else is −101. All multi-byte operands are **big-endian**; stack
offsets and sizes in the bytecode are in bytes and the VM divides them by 4 to get cells. Unless
noted, an instruction is 2 bytes (opcode + type).

Cell types (the type byte stored per stack cell, and the unary type qualifier): 3 int, 4 float,
5 string, 6 object, 0x10+n engine structure n (n = 0 effect, 1 event, 2 location, 3 talent; up to
0x19 accepted). Binary qualifiers: 0x20 int,int; 0x21 float,float; 0x22 object,object;
0x23 string,string; 0x24 struct,struct; 0x25 int,float; 0x26 float,int; 0x30..0x39 engine
structure n,n; 0x3a vector,vector; 0x3b vector,float; 0x3c float,vector. For binary operators the
right operand is on top; "a op b" below means a = lower cell, b = top cell.

| Op | Mnemonic | Operands after opcode+type | Behaviour in KOTOR | Conf. |
|---|---|---|---|---|
| 0x01 | CPDOWNSP | int32 offset, int16 size | copies the top size/4 cells to SP + offset/4 (cell by cell, deep copies, see `AssignLocationToLocation`); −100 if the destination index < 0. 8 bytes | high |
| 0x02 | RSADD | — | pushes a default cell: int 0, float 0.0, string "", object OBJECT_INVALID, engine structure = `CopyGameDefinedStructure(n, NULL)` (a default-constructed one). Other types −97 | high |
| 0x03 | CPTOPSP | int32 offset, int16 size | pushes copies of size/4 cells starting at SP + offset/4. 8 bytes | high |
| 0x04 | CONST | int: int32; float: 32-bit IEEE; string: int16 length + bytes; object: int32 | int/float/object 6 bytes, string 4 + length bytes. The string length is read as a **signed** 16-bit value and the text goes through a `"%s"` format, so it stops at an embedded NUL. Object: 0 = OBJECT_SELF (see above), anything else OBJECT_INVALID. Other types −97 | high |
| 0x05 | ACTION | uint16 routine, uint8 argc | calls the implementer's `RunCommand(routine, argc)` (vtable slot 2, 0x0052c0d0); a negative result aborts the script with that code; −108 without implementer. 5 bytes. The VM does not check how many cells the handler consumed | high |
| 0x06 | LOGAND | 0x20 only | pops b, a; pushes (a && b) | high |
| 0x07 | LOGOR | 0x20 | pushes (a \|\| b) | high |
| 0x08 | INCOR | 0x20 | bitwise or | high |
| 0x09 | EXCOR | 0x20 | bitwise xor | high |
| 0x0A | BOOLAND | 0x20 | bitwise and | high |
| 0x0B / 0x0C | EQUAL / NEQUAL | 0x20..0x23, 0x30..0x39; 0x24 adds int16 size (bytes) | compares n cells pairwise (n = 1, or size/4 for 0x24; cell k of the top block with cell k of the block below), pops 2n cells, pushes 1/0. Per cell, by the cell's type: int, float and object compare the raw 32 bits (so float 0.0 ≠ −0.0); strings compare **ASCII case-insensitively** (0x005e6450; a null string equals only a null string); engine structures through `GetEqualGameDefinedStructure`; anything else −109. −100 if fewer than 2n cells. 2 bytes, 4 with 0x24 | high |
| 0x0D | GEQ | 0x20, 0x21 | a >= b | high |
| 0x0E | GT | 0x20, 0x21 | a > b | high |
| 0x0F | LT | 0x20, 0x21 | a < b | high |
| 0x10 | LEQ | 0x20, 0x21 | a <= b | high |
| 0x11 | SHLEFT | 0x20 | a << (b & 31) | high |
| 0x12 | SHRIGHT | 0x20 | a >= 0: a >> b; a < 0: −((−a) >> b) (rounds toward zero) | high |
| 0x13 | USHRIGHT | 0x20 | **arithmetic** (sign-extending) shift, not logical — same as NWN | high |
| 0x14..0x17 | ADD, SUB, MUL, DIV | 0x20, 0x21, 0x25, 0x26 (result float when either side is float); 0x23 ADD only (concatenation a + b); 0x3a ADD/SUB only; 0x3b vector*/÷float; 0x3c float*vector | int DIV uses x86 `idiv` (division by 0 → −105; INT_MIN / −1 would fault). Float and vector/float DIV by 0.0 → −105. With a qualifier that is accepted but meaningless for the opcode (e.g. SUB 0x23, MUL 0x3a, ADD 0x3b) the operands are popped and nothing is pushed | high |
| 0x18 | MOD | 0x20 | a % b (C remainder); b = 0 → −105 | high |
| 0x19 | NEG | 3, 4 | −a | high |
| 0x1A | COMP | 3 | ~a | high |
| 0x1B | MOVSP | int32 offset | SP += offset/4 (only shrinks; freed cells are destroyed). 6 bytes | high |
| 0x1C | STORE_STATEALL | type byte = resume offset | saved IP = IP + type byte, both saved sizes 0 (= "whole stack"). 2 bytes | high |
| 0x1D | JMP | int32 offset | IP += offset | high |
| 0x1E | JSR | int32 offset | pushes IP + 6 on the return-address stack (−99 if it is full), IP += offset | high |
| 0x1F | JZ | int32 offset | pops an int; jumps if it is 0, else IP += 6 | high |
| 0x20 | RETN | — | pops a return address into IP (−100 if none); −1 ends `ExecuteCode` with 0 | high |
| 0x21 | DESTRUCT | int16 size, int16 keep-offset, int16 keep-size | removes size/4 cells from the top but keeps the keep-size/4 cells that start keep-offset/4 cells into that block (they slide down). 8 bytes | high |
| 0x22 | NOT | 3 | !a | high |
| 0x23 / 0x24 | DECISP / INCISP | type 3, int32 offset | ±1 on the int cell at SP + offset/4 (only if that cell is an int; any other type byte in the instruction is silently skipped). 6 bytes | high |
| 0x25 | JNZ | int32 offset | pops an int; jumps if non-zero | high |
| 0x26 | CPDOWNBP | as 0x01, relative to BP | | high |
| 0x27 | CPTOPBP | as 0x03, relative to BP | | high |
| 0x28 / 0x29 | DECIBP / INCIBP | as 0x23/0x24, relative to BP | | high |
| 0x2A | SAVEBP | — | pushes BP as an int, then BP = index of that cell (the SP before the push) | high |
| 0x2B | RESTOREBP | — | pops an int into BP (−100 if the top is not an int) | high |
| 0x2C | STORE_STATE | type byte = resume offset (0x10); int32 base size; int32 stack size (bytes) | saved IP (+0x3c8) = IP + type byte; base size → +0x3d0; stack size → +0x3cc. 10 bytes | high |
| 0x2D | NOP | — | **not implemented**: −101 | high |

Helpers called by the loop:

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x005d17f0 | `PushInstructionPtr(int)` | stores at +0x1c8[depth], depth + 1; false once depth reaches 128 | high |
| 0x005d17b0 | `PopInstructionPtr(int*)` | depth − 1; false (depth back to 0) if it went negative | high |
| 0x005d16c0 | `CVirtualMachineStack::ModifyIntegerAtLocation(idx, delta)` | INC/DEC on an int cell | high |
| 0x005d1c40 | `CVirtualMachineStack::AssignLocationToLocation(src, dst)` | copies one cell: grows the stack first if dst == SP; strings are duplicated (the old dst string is freed); engine structures: destroy old dst (slot 6), `CopyGameDefinedStructure` (slot 8); other types copy the 32 bits; dst type = src type | high |

## The value stack

`CVirtualMachineStack` (0x18 bytes):

| Offset | Field | Conf. |
|---|---|---|
| +0x00 | `m_nStackPointer`: number of cells in use (next free index) | high |
| +0x04 | `m_nBasePointer`: cell index | high |
| +0x08 | `m_nTotalSize`: capacity in cells | high |
| +0x0c | `char* m_pchStackTypes`: one type byte per cell | high |
| +0x10 | `int* m_pStackNodes`: one 32-bit value per cell (int, float bits, object id, or a pointer to a heap `CExoString` / engine structure) | high |
| +0x14 | `CVirtualMachineInternal* m_pVMachine`: used to reach the implementer's structure hooks | high |

| Address | Name | What | Conf. |
|---|---|---|---|
| 0x005d15a0 | `AddToTopOfStack(int type)` | grows by 256 cells when full (reallocates both arrays), writes the type and a default value (0; object 0x7f000000; an engine-structure cell is only added if `m_pVMachine` is set) | high |
| 0x005d21f0 | `SetStackPointer(int sp)` | lowers SP to `sp`, destroying freed cells from the top down: strings deleted, engine structures via `DestroyGameDefinedStructure` (slot 6). Never raises SP | high |
| 0x005d2140 | `ClearStack()` | destroys every cell, frees both arrays, zeroes SP/BP/size | high |
| 0x005d28f0 | `CopyFromStack(src, stackBytes, baseBytes)` | rebuilds this stack from part of `src`: `baseBytes/4` cells taken from just below `src.BP` become cells 0.. (new BP = that count), then `stackBytes/4` cells taken from just below `src.SP` follow; both clamped to 0..65536 cells and the base part to at most `src.BP`. Both 0 = whole stack (base = src.BP cells, rest = SP − BP). Deep copies strings and engine structures. Capacity = cells + 16 | high |
| 0x005d1d80 | `SaveStack(CResGFF*, CResStruct*)` | GFF, see [Saved situations](#save-games) | high |
| 0x005d1ef0 | `LoadStack(CResGFF*, CResStruct*)` | GFF reader | high |

Push and pop (facade thunk → internal implementation; every pop fails, returning 0 and leaving
the stack alone, if the stack is empty or the top cell has the wrong type; pushes return 1, except
an engine-structure push without a command implementer, which returns 0):

| Facade | Internal | Name | Notes | Conf. |
|---|---|---|---|---|
| 0x005d1000 | 0x005d24c0 | `StackPopInteger(int*)` | | high |
| 0x005d1010 | 0x005d1850 | `StackPushInteger(int)` | | high |
| 0x005d1020 | 0x005d2510 | `StackPopFloat(float*)` | | high |
| 0x005d1030 | 0x005d1880 | `StackPushFloat(float)` | | high |
| 0x005d1040 | 0x005d2560 | `StackPopVector(Vector*)` | pops z, y, x (three float cells; z is on top) | high |
| 0x005d1050 | 0x005d18b0 | `StackPushVector(Vector)` | pushes x, y, z | high |
| 0x005d1080 | 0x005d25e0 | `StackPopString(CExoString*)` | assigns into the caller's string, then frees the cell | high |
| 0x005d1090 | 0x005d1930 | `StackPushString(CExoString const&)` | pushes a new heap copy | high |
| 0x005d10a0 | 0x005d2630 | `StackPopEngineStructure(int n, void** out)` | top must be type 0x10+n; returns a **copy** (slot 8) and destroys the stack's own object | high |
| 0x005d10b0 | 0x005d19c0 | `StackPushEngineStructure(int n, void* p)` | pushes a **copy** (slot 8); the caller keeps and must free `p` | high |
| 0x005d10c0 | 0x005d26a0 | `StackPopObject(OBJECT_ID*)` | | high |
| 0x005d10d0 | 0x005d1a10 | `StackPushObject(OBJECT_ID)` | | high |
| 0x005d10e0 | 0x005d4380 | `StackPopCommand(CVirtualMachineScript**)` | captures the last STORE_STATE as a script situation, [below](#script-situations-action-arguments) | high (name med) |

## Engine structures and the command implementer

`CVirtualMachineCmdImplementer` is abstract (base vtable 0x007450ac: deleting destructor 0x004b1340
and ten `_purecall` slots). `CSWVirtualMachineCommands` (vtable 0x007450e4) fills them:

| Slot | Address | Name | What | Conf. |
|---|---|---|---|---|
| 0 | 0x004b16e0 | deleting destructor | destructor 0x0052c070 frees the routine table | high |
| 1 | 0x0054c960 | `InitializeCommands()` | allocates and fills the 772-entry table at +0xc | high |
| 2 | 0x0052c0d0 | `RunCommand(routine, argc)` | | high |
| 3 | 0x0052c100 | `RunScriptCallback(CExoString* name)` | called by `RunScript` for every script; for a non-empty name, appends `name` + `","` to a `CExoString` at +0x60 of the object returned by 0x004aed80 (server getter, the same object `AddEventDeltaTime` is called on). Purpose unknown (a debug trace?) | med |
| 4 | 0x005b5e90 | `ReportError(CExoString* name, int err)` | folded empty stub: errors are dropped | high |
| 5 | 0x0052c580 | `CreateGameDefinedStructure(n)` | `new` of the type's class; not called by the VM itself | high |
| 6 | 0x00548360 | `DestroyGameDefinedStructure(n, p)` | | high |
| 7 | 0x0052c510 | `GetEqualGameDefinedStructure(n, a, b)` | used by EQUAL/NEQUAL | high |
| 8 | 0x0052c140 | `CopyGameDefinedStructure(n, p)` | new object copied from `p`; `p` may be NULL (gives a default object; RSADD relies on this) | high |
| 9 | 0x0052c2d0 | `SaveGameDefinedStructure(n, p, CResGFF*, CResStruct*)` | writes a child struct `GameDefinedStrct` (struct id n) | high |
| 10 | 0x0052c360 | `LoadGameDefinedStructure(n, void** out, CResGFF*, CResStruct*)` | reads it back | high |

Implementer fields: +0 vtable, +4 `bValidObjectRunScript` and +8 `oidObjectRunScript` (the current
level's OBJECT_SELF, copied in by the VM), +0xc the routine table (high).

The four engine structures (n is `ENGINE_STRUCTURE_n` in nwscript.nss):

| n | Script type | Class (size) | Constructor / copy / equality / save / load | Equality means | Conf. |
|---|---|---|---|---|---|
| 0 | effect | `CGameEffect` (0x8c) | 0x00503e40 (arg: create a new 64-bit id from the counter at 0x007a1b40) / 0x00504090 / inline / 0x00503790 / 0x005043a0; destructor 0x00503590 | same 64-bit effect id | high (class name med) |
| 1 | event | `CScriptEvent` (0x34) | 0x004d7540 / 0x004d77f0 / 0x004d7270 / 0x004d73a0 / 0x004d79b0; destructor 0x004d7590 | same event type and equal int, float, string and object lists | high (name med) |
| 2 | location | `CScriptLocation` (0x18) | 0x004ca7a0 / 0x004ca7c0 / 0x0052bf80 / 0x004ca8e0 / 0x004ca800 | same position and orientation vectors (0x004aa980) | high |
| 3 | talent | `CScriptTalent` (0x18) | 0x004ca9e0 / 0x004caa10 / 0x004cabb0 / 0x004caa50 / 0x004caaf0 | all fields equal | high |

A KOTOR location is position (+0, three floats) and orientation (+0xc, three floats; GFF
`PositionX..Z`, `OrientationX..Z`): **no area**. A talent is type (+0, default −1), id (+4, −1),
multiclass byte (+8), item (+0xc, OBJECT_INVALID), item property index (+0x10, −1), caster level
byte (+0x14, 0xff), meta type byte (+0x15, 0xff); GFF `Type`, `ID`, `MultiClass`, `Item`,
`ItemPropertyIndex`, `CasterLevel`, `MetaType`. An event is an event type (word) plus int, float,
string and object parameter lists (`EventType`, `IntList`, `FloatList`, `StringList`,
`ObjectList`, each element `Parameter`).

## Script situations (action arguments)

An `action` argument is never on the stack. The compiler emits `STORE_STATE 0x10, base, stack`
followed by a JMP over the action's code (which ends in RETN), then pushes the routine's other
arguments and calls ACTION. STORE_STATE only records registers; the handler turns them into a
`CVirtualMachineScript` ("situation") with `StackPopCommand` (0x005d4380, high):

- a new 0x28-byte script object; the code is copied only if the running slot's
  loaded-from-save flag (+0x20) is set (otherwise the situation carries just the script name and
  the code is re-read from the resource when it runs); CRC and the flag are copied;
- `InstructionPtr` = the saved IP (STORE_STATE address + 0x10 = first byte of the action block),
  `SecondaryPtr` = 0, `StackSize` = the current SP;
- a new stack built by `CopyFromStack(runtime stack, stackBytes(+0x3cc), baseBytes(+0x3d0))`:
  the globals below BP and the top locals the block needs;
- the script name.

Running one: `RunScriptSituation(situation, oid, bOidValid)` (0x005d0fd0 → 0x005d4ad0, high)
**wipes the runtime stack** and replaces it with a copy of the situation's stack, frees the
situation's stack, zeroes the return-stack depth and the instruction counter, then
`SetUpScriptSituation` (0x005d23e0) opens a new level: if the situation has no code it calls
`ReadScriptFile(name)` (code from the resource, flag 0), otherwise it adopts the situation's code
and flag; it copies name, IP, CRC. If the slot's CRC is non-zero the code is not run. Otherwise it
sets the level's OBJECT_SELF, `RunScriptFile(InstructionPtr)`, frees the slot, level − 1, deletes
the situation and returns true on success. It assumes no other script is running (it does not
preserve the stack); the engine only calls it from event and action processing.

`DeleteScriptSituation` (0x005d1110 → 0x005d48e0) frees a situation that will not run.

### The handlers

| Routine | Handler | Behaviour | Conf. |
|---|---|---|---|
| 6 `AssignCommand(object, action)` | 0x0052e720 | pops the object, then the situation. If the object exists (object array 0x004aed70, lookup 0x004d8230), queues an AI event: delay 0 days 0 ms, caller = OBJECT_SELF (or OBJECT_INVALID if not valid), target = the object, event id 1, data = the situation (0x004b08d0). Otherwise frees the situation. Returns 0 either way | high |
| 7 `DelayCommand(float, action)` | 0x0052fe30 | pops the float, then the situation. Only if OBJECT_SELF is valid and exists: queues event id 1 with delay `(int)(seconds * 1000.0)` ms (constant at 0x0073d6fc), caller = target = OBJECT_SELF. Otherwise the situation is freed | high |
| 294 `ActionDoCommand(action)` | 0x0052c740 | pops the situation; if OBJECT_SELF exists, 0x0057cb10 adds action 0x25 (37, the do-command action; med) with one parameter of type 5 (situation) to its queue, or deletes the situation if the object is not commandable (+0xe8 == 0). If OBJECT_SELF does not exist the situation is leaked, not freed. When the action executes (0x0057b530, called from 0x0057f4a0, the action dispatcher; med) it runs `RunScriptSituation(situation, self, TRUE)` | high |
| 8 `ExecuteScript(string, object, int = −1)` | 0x00535b70 | pops the name, the target and (when argc > 2) `nScriptVar` into the global 0x00832828 (read by `GetRunScriptVar`, never reset). Runs `RunScript(name, target, bValid)` **immediately and nested** (one recursion level deeper), where bValid is the caller's OBJECT_SELF validity and the target becomes OBJECT_INVALID if the caller's OBJECT_SELF is not valid. The result is ignored | high |

Event id 1 is delivered by the AI master's update (0x004b0b70) to the target object's
`EventHandler`, which calls `RunScriptSituation(situation, its own id, TRUE)` (for example
0x004c5120 for one object type). So OBJECT_SELF inside a delayed or assigned action is the event's
target.

### Save games

Situations are saved in two places: the AI event queue (0x004afea0 / 0x004b0290; an event with
`EventId` 1 has an `EventData` struct, id 0x7777, holding the situation) and object action lists
(0x004cc7e0 / 0x004cecb0; a `Paramaters` element of `Type` 5 has a `Value` struct, id 2).

`SaveScriptSituation` (0x005d10f0 → 0x005d47a0) always embeds code: if the situation has none it
loads the script by name just to copy its code. `LoadScriptSituation` (0x005d1100 → 0x005d26f0)
sets the loaded-from-save flag, so a reloaded situation (and any situation captured from it later)
runs the saved code, not the current resource.

| Field | GFF type | Meaning | Conf. |
|---|---|---|---|
| `CodeSize` | INT | code length (0 if the script could not be loaded) | high |
| `Code` | VOID | code bytes (file offset 13 onward) | high |
| `CRC` | DWORD | written as 0; on load, a non-zero value prevents the situation from running | high |
| `InstructionPtr` | INT | resume address (code offset) | high |
| `SecondaryPtr` | INT | 0 in practice | high |
| `Name` | CExoString | script resref | high |
| `StackSize` | INT | SP at capture | high |
| `Stack` | struct (id 0) | `BasePointer` INT, `StackPointer` INT, `TotalSize` INT (capacity), and if `TotalSize` > 0 a list `Stack` of SP elements (struct id = index) with `Type` CHAR and `Value`: INT (int), FLOAT (float), CExoString (string), DWORD (object), or for engine structures a child struct `GameDefinedStrct` (id = n) written by slot 9 | high |

## Data structure offsets

`CVirtualMachineInternal` (0x3d8 bytes):

| Offset | Field | Conf. |
|---|---|---|
| +0x000 | vtable (0x0074c4fc, one slot: deleting destructor 0x005d4c10); base `CResHelper<CResNCS,2010>` (vtable 0x0074c490) | high |
| +0x004 | CResHelper auto-request flag | high |
| +0x008 | CResHelper `CResNCS*` | high |
| +0x00c | CResHelper resref (16 bytes) | high |
| +0x01c | return value type (3 = int, else 0) | high |
| +0x020 | return value | high |
| +0x024 | instructions executed | high |
| +0x028 | recursion level (−1 = idle, 0..7) | high |
| +0x02c | `CVirtualMachineScript` slots [8], 0x28 each | high |
| +0x16c | `bValidObjectRunScript` [8] | high |
| +0x18c | `oidObjectRunScript` [8] | high |
| +0x1ac | runtime `CVirtualMachineStack` (SP +0x1ac, BP +0x1b0, size +0x1b4, types +0x1b8, values +0x1bc, VM +0x1c0) | high |
| +0x1c4 | return-address stack depth | high |
| +0x1c8 | return addresses [128] | high |
| +0x3c8 | saved IP from STORE_STATE | high |
| +0x3cc | STORE_STATE stack (locals) size, bytes | high |
| +0x3d0 | STORE_STATE base (globals) size, bytes | high |
| +0x3d4 | `CVirtualMachineCmdImplementer*` | high |

`CVirtualMachineScript` (0x28 bytes; constructor 0x005d1740, destructor 0x005d4550, reset 0x005d44f0):

| Offset | Field | Conf. |
|---|---|---|
| +0x00 | `CVirtualMachineStack*` (saved stack; null in a running slot) | high |
| +0x04 | stack size (SP at capture) | high |
| +0x08 | instruction pointer (resume address; initialised to 13 but unused for fresh scripts, which start at 0) | high |
| +0x0c | secondary instruction pointer | high |
| +0x10 | code buffer | high |
| +0x14 | code size | high |
| +0x18 | script name (`CExoString`) | high |
| +0x20 | loaded-from-save flag (code is embedded) | high |
| +0x24 | CRC (must be 0 to run) | high |

## Quirks a compatible VM must reproduce

- String `==` / `!=` are ASCII case-insensitive.
- Float `==` compares bit patterns.
- `USHRIGHT` sign-extends; `SHRIGHT` of a negative number rounds toward zero.
- `NOP` (0x2D) is an invalid opcode.
- The NCS size field is ignored; code offsets exclude the 13-byte header.
- Errors are silent; a script that fails keeps the effects it already had.
- Nested `ExecuteScript` runs share the instruction budget (131,071 per outermost run) and the
  128-entry return stack; at most 8 levels.
- `ExecuteScript` runs synchronously; `AssignCommand` always goes through the event queue (it runs
  on the next AI update, never inline); `DelayCommand` and `AssignCommand` drop the action if
  their object is gone.
- `RunScriptFile` clears the return value at every run, including nested ones, and `RunScript`
  only overwrites it when its own script leaves an int; a void script that ran a nested
  int-returning script therefore still reports the nested value (med).
- After an error in a nested script, SP is restored but BP is not (med: no code restores it).

## Unresolved

- Purpose of the comma-separated script-name list written by `RunScriptCallback` (+0x60 of the
  object from 0x004aed80).
- The global 0x007a3a04 is deleted at shutdown (0x004b7c60 → 0x005d1120 → 0x005d14d0) but never
  created; its destructor (16 include-stack entries of 0x34 bytes holding a `CResHelper`, arrays
  of 0x7c-byte records, 32 strings at +0x8a8) looks like NWN's script compiler. Probably a
  compiled-out compiler (low).
- The other `CResHelper` vtable at 0x0074c480 (destructor 0x005d11e0) is used by that object only.
- Names of the object classes whose `EventHandler` receives event id 1 (0x004c5120 and the vtable
  slot +0x78 of game objects) belong in [objects.md](objects.md).
