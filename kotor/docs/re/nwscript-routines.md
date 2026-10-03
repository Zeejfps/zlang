# NWScript engine routines in swkotor.exe

How an NCS `ACTION` instruction's routine number reaches the engine code that implements it, and
how to get the number → handler table for every routine. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (see [README.md](README.md)); confidence is high for
everything here unless marked.

## The table

The engine keeps one object that implements the script commands (our name:
`CSWVirtualMachineCommands`, vtable `0x007450e4`, 11 slots). Its second virtual function,
`InitializeCommands` (`0x0054c960`), allocates `0xc10` bytes (772 four-byte slots), zeroes them,
stores the pointer at offset `+0x0c` of the commands object, and then fills the slots one by one:
each store writes a handler's address to `table + 4*N`. Slot `N` is routine `N`, and routine
numbers are the order of the prototypes in the game's own `nwscript.nss` (the prototypes without
a body, numbered 0 to 771 by the comments above them). KOTOR 1 has exactly 772, which matches the
allocation.

`InitializeCommands` ends with a tail jump to a second filler (`0x005cd2c0`, our name
`InitializeMiniGameCommands`) that stores the 97 swoop/turret minigame routines (`SWMG_*`):
slots 520–521, 582–668, 683–688 and 717–718. Every one of the 772 slots ends up non-null.

`nwscript.nss` comes from the game data: `python kotor/tools/py/kres.py get nwscript.nss`.

## Dispatch

`RunCommand` (`0x0052c0d0`, vtable slot 2) receives `(nCommand, nParameters)`: when
`nCommand < 0x304` (772) and the slot is non-null it calls the handler with the same two
arguments and the commands object in `ECX`, otherwise it returns `-2002`. The VM calls it for the
`ACTION` opcode (see [vm.md](vm.md) once written for the interpreter side).

Handlers are `__thiscall` member functions: `int ExecuteCommandX(int nCommand, int nParameters)`,
`ret 8`. They pop their arguments from the VM stack through the global VM object
(`g_pVirtualMachine`, `0x007a3a00`, e.g. `CVirtualMachine::StackPopInteger` `0x005d1000`) in
declaration order, do the work, push the result (`StackPushInteger` `0x005d1010` and siblings) and
return 0, or `-2001` when a pop fails (stack empty or wrong type) and `-2000` when a push fails.
`nParameters` is the argument count carried by the `ACTION` instruction (the compiler pushes
defaults for omitted optional parameters, so it normally equals the prototype's parameter count).

## Shared handlers

There are 565 distinct handlers for 772 routines: 93 handlers serve more than one routine (300
routines in all) and switch on `nCommand`. The groups follow the script API's families, which
doubles as a check that the numbering is right: `d2`..`d100` share one handler, the trigonometry
and `fabs`/`abs`/`log`/`sqrt`/`pow` family another (routines 67–77), 21 `Effect*` constructors
share one, `GetTrap*` queries share one, `AmbientSound*` and `MusicBackground*`
each share one, as do `GetFirst*`/`GetNext*` iterator pairs.

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
hold handler addresses, then following the tail jump), so it keeps working after renames. Its
output columns: `number, name, handler, handler_name, shared_with, signature`.

Handlers are named `CSWVirtualMachineCommands::ExecuteCommand<Routine>` after the lowest-numbered
routine they serve; the plate comment (shown as `// note:` in the exported function) lists every
routine a shared handler serves. These names are ours.
