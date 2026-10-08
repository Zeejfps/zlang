# NWScript engine routines in swkotor.exe

How an NCS `ACTION` instruction's routine number reaches the engine code that implements it, and
how to get the number → handler table for every routine. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (see [README.md](README.md)); rechecked on 2026-10-07
against the rebuilt decompile and the raw stores in the binary. Confidence is high for everything
here unless marked.

## The table

The engine keeps one object that implements the script commands (our name:
`CSWVirtualMachineCommands`, vtable `0x007450e4`, 11 slots). Its second virtual function (slot 1),
`InitializeCommands` (`0x0054c960`), allocates `0xc10` bytes (772 four-byte slots), zeroes them,
stores the pointer at offset `+0x0c` of the commands object, and then fills the slots one by one:
each store writes a handler's address to `table + 4*N`, reloading the table pointer from
`[this+0x0c]` before each store. Slot `N` is routine `N`, and routine numbers are the order of
the prototypes in the game's own `nwscript.nss` (the prototypes without a body, counted from 0 to
771; 713 of them carry a `// N:` comment, which always matches the position, and 59 have none,
among them 124, 188, 582 and most of 679–771). KOTOR 1 has exactly 772, which matches the
allocation.

`InitializeCommands` makes 677 stores into 675 slots. Two slots are stored twice: slot 709 gets
the same handler both times, and slot 156 (`EffectTemporaryForcePoints`) first gets `0x00535100`
(pops an int, builds an effect of type `0x5b`) and then `0x00534340`. The later store wins, so
`0x00535100` is never reached through the table (nothing else takes its address).

`InitializeCommands` ends with a tail jump to a second filler (`0x005cd2c0`, our name
`InitializeMiniGameCommands`) that fills the other 97 slots: 520–521, 582–668, 683–688 and
717–718. These are the swoop/turret minigame routines (`SWMG_*`) plus `AurPostString` (582);
one `SWMG_*` routine, 563 `SWMG_SetSpeedBlurEffect`, is filled by `InitializeCommands` instead.
The two fillers write disjoint slots, and every one of the 772 slots ends up non-null.

`nwscript.nss` comes from the game data: `python kotor/tools/py/kres.py get nwscript.nss`.

## Dispatch

`RunCommand` (`0x0052c0d0`, vtable slot 2) receives `(nCommand, nParameters)`: when
`nCommand < 0x304` (772) and the slot is non-null it calls the handler with the same two
arguments and the commands object still in `ECX`, and returns the handler's result; otherwise it
returns `-2002`. The bound check is a signed compare (`JGE`), so a negative `nCommand` is not
rejected and would read before the table; since every slot is filled, `-2002` only happens for
`nCommand >= 772`. The VM calls it for the `ACTION` opcode (`0x05`: a 16-bit big-endian routine
number and an 8-bit argument count, which become `nCommand` and `nParameters`); a negative result
aborts the script (see [vm.md](vm.md) for the interpreter side).

Handlers are `__thiscall` member functions: `int ExecuteCommandX(int nCommand, int nParameters)`,
`ret 8`. They pop their arguments from the VM stack through the global VM object
(`g_pVirtualMachine`, `0x007a3a00`, e.g. `CVirtualMachine::StackPopInteger` `0x005d1000`) in
declaration order, do the work, push the result (`StackPushInteger` `0x005d1010` and siblings) and
return 0, or `-2001` when a pop fails (stack empty or wrong type) and `-2000` when a push fails.
`nParameters` is the argument count carried by the `ACTION` instruction. The compiler pushes
defaults for omitted optional parameters, but many shipped scripts were compiled against an older
`nwscript.nss` and pass fewer arguments than the shipped prototype declares (1093 call sites, e.g.
`ActionStartConversation` with 11 of 12; [../formats/nwscript.md](../formats/nwscript.md), "Calls
that don't match the shipped prototypes"). Handlers with trailing optional parameters pop each
one only when `nParameters` is larger than its position and otherwise use their own default
(77 handlers test `nParameters`; e.g. `ActionStartConversation` `0x0052d5b0`, `ExecuteScript`
`0x00535b70`), so a reimplementation must honour the count rather than the prototype.

Three routines are no-ops: 321 `GetLastAssociateCommand`, 327 `SetAssociateListenPatterns` and
403 `ExploreAreaForPlayer` all point at `0x00409eb0`, a linker-folded stub that returns 0 without
popping or pushing anything (so 321 leaves no int on the stack for its caller; the VM does not
check how many cells a handler consumed, [vm.md](vm.md)).

## Shared handlers

There are 565 distinct handlers for 772 routines: 93 handlers serve more than one routine (300
routines in all); 92 of them switch on `nCommand`, the 93rd is the no-op stub above. The groups
follow the script API's families, which doubles as a check that the numbering is right: `d2`..`d100`
share one handler, the trigonometry and `fabs`/`abs`/`log`/`sqrt`/`pow` family another (routines
67–77), 21 `Effect*` constructors share one, the ten `GetTrap*` queries share one with
`SetTrapDetectedBy` and `SetTrapDisabled`, the six `AmbientSound*` routines share one, as do five
`MusicBackground*` routines (`Play`, `Stop`, `SetDelay`, `ChangeDay`, `ChangeNight`; the three
`MusicBackgroundGet*Track` have their own), and each `GetFirst*`/`GetNext*` iterator pair.

## Getting the table

```
python kotor/tools/py/nwscript_table.py            # writes kotor/re/export/nwscript_routines.tsv
python kotor/tools/py/nwscript_table.py --names    # also names every handler in names.tsv
python kotor/tools/py/rex.py routine 7             # one routine: signature and handler
python kotor/tools/py/rex.py routine 'Effect.*'    # by regex on the name
python kotor/tools/py/rex.py fn ExecuteCommandDelayCommand
```

The script does not use decompiled text: it replays the stores in Ghidra's disassembly listing of
the filler (tracking which registers hold the table pointer, loaded from `[this+0x0c]`, and which
hold handler addresses, then following the tail jump), so it keeps working after renames; a slot
stored twice keeps the last store, as in the game. Its output columns:
`number, name, handler, handler_name, shared_with, signature`.

Handlers are named `CSWVirtualMachineCommands::ExecuteCommand<Routine>` after the lowest-numbered
routine they serve; the plate comment (shown as `// note:` in the exported function) lists every
routine a shared handler serves. The exception is the folded stub `0x00409eb0`, which is also used
outside the script commands and is named `FoldedStub_00409eb0`. These names are ours.
