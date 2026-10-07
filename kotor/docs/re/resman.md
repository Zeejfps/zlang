# The resource manager in swkotor.exe

How the engine registers resource sources and searches them. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (`kotor/re/bin/swkotor_unpacked.exe`, decompiled in
`kotor/re/export/functions/`). Names in the tables are ours, after NWN's `CExoResMan` /
`CExoKeyTable` vocabulary; Ghidra still shows them as `FUN_...`. The format-level summary is in
[../formats/resources.md](../formats/resources.md).

The global resource manager object is `DAT_007a39e8`.

## Key tables

| Address | Our name | What it does |
|---|---|---|
| 0x00406e20 | `CExoResMan::AddKeyTable(name, kind, group)` | `kind` 1 = KEY, 2 = directory, 3 = ERF, 4 = RIM. Picks the list for the kind (object offsets +0x10, +0x14, +0x18, +0x1c), when a table of the same name is already there rebuilds it instead and returns success (`RebuildTable` `0x00410260`, keeping the old group; for a RIM it logs "Table being rebuilt, this RIM is being leaked"; [resources.md](resources.md) 1), otherwise gives the table a free id 1..63 tagged with the kind (0, 0x80000000, 0x40000000, 0x20000000), stores `group` at table+8, inserts it at the **head** of the list and opens it. |
| 0x004087e0 | `AddKeyFile(name)` | AddKeyTable(name, 1, 0) |
| 0x00408800 | `AddDirectory(name)` | AddKeyTable(name, 2, 0) |
| 0x004087a0 | `AddEncapsulated(name, group)` | AddKeyTable(name, 3, group) |
| 0x004087c0 | `AddRim(name)` | AddKeyTable(name, 4, 0) |
| 0x00407830 | `RemoveKeyTable(name, kind)` | finds by name in the kind's list, destroys it |
| 0x00408820 / 0x004088d0 | `RemoveEncapsulated` / `RemoveDirectory` | RemoveKeyTable(name, 3) / (name, 2) |
| 0x00408830 | `RemoveRim(name)` | the same for the RIM list |
| 0x005e9d70 | linked list add-head | new node becomes the head, so lists run newest first |
| 0x00410190 | `CExoKeyTable::Initialize(kind, name, id)` | dispatches to the per-kind opener |
| 0x0040f3c0 | ERF opener | tries `name` with resource types 2062 (`.nwm`), 2011 (`.mod`), 2057 (`.sav`), 9997 (`.erf`), 2061 (`.hak`) in that order |
| 0x0040f990 | RIM opener | builds the key list; each key's id is `(table id & 0x3ff \| 0x400) << 20 \| ResID`, the entry's own stored ResID (the files number entries 0, 1, 2…, so it equals the index) |
| 0x0040f200 | directory opener | lists the directory (no recursion); for each file: type from 0x00406650, resref from 0x004065a0; skips unknown types and empty resrefs; adds the key |
| 0x00406650 | file name to type | the 3 characters after the first `.`, looked up in the type table; 0xFFFF if none |
| 0x004065a0 | file name to resref | the characters before the first `.`, cut to 16 |
| 0x005e6d20 | type table | builds the 88-entry table of (id, extension): every type in [../formats/resource-types.md](../formats/resource-types.md) and 0xFFFF / `""` last |
| 0x005e7a40 | extension to id | linear search, ASCII case-insensitive (0x005e6450); returns the last entry (0xFFFF) when nothing matches |

## Lookup

| Address | Our name | What it does |
|---|---|---|
| 0x00407230 | `CExoResMan::GetKeyEntry(resref, type, &table, &entry)` | searches, first hit wins: directories; ERFs with group 1; RIMs; ERFs with group 2; KEY files |
| 0x004071a0 | search one list | walks a list from its head (newest), skipping disabled tables (table+4 != 0) and, when a group is given, tables of another group; asks each table for the key (0x0040ec50) |
| 0x00408bc0 | `Exists(resref, type, &kind)` | GetKeyEntry; optionally returns the kind (1..4) of the table that has it |

## Who mounts what

| Address | What |
|---|---|
| 0x005f8550 | start-up (reads `swkotor.ini`): directories `TEMPCLIENT:`, `OVERRIDE:`, `ERRORTEX:`; Xbox `HD0:DATAXBOX\*` paths; `HD0:CHITIN` (KEY); directories `RIMS:`, `SERVERVAULT:`, `PORTRAITS:`; ERFs `OVERRIDE:textures` and `HD0:patch` in group 1; directories `HD0:MOVIES`, `HD0:STREAMWAVES`, `HD0:STREAMMUSIC`; RIM `RIMS:GLOBAL` if `GLOBAL.rim` exists; later `Texture Quality` to 0x005f14a0 |
| 0x005f14a0 | texture packs: row `Texture Quality` (0 if missing or > 3) of `texpacks.2da`; columns `Texture`, `Gui`, `DynMemRatio`, `Mem`; mounts `TEXTUREPACKS:<Texture>` in slot 1 and `TEXTUREPACKS:<Gui>` in slot 2 |
| 0x0070d800, 0x0070cf80, 0x0070cf30 | pack slots 0..3 (names kept at 0x00834098): unmount the slot's old ERF, mount the new one as ERF group 2 |
| 0x0067c4c0, 0x006dc3c0 | main menu and character generation: `RIMS:MAINMENU` / `RIMS:CHARGEN` as RIMs if present; 0x0040c8e0 and 0x004165e0 remove them (flags in resman+0x34) |
| 0x004b95b0 | before a module loads: copies its main file into `CURRENTGAME:` from, in order, `GAMEINPROGRESS:` (type 3009 or `.sav`), `NWMFILES:` (`.nwm`), `MODULES:` (`.mod`, else `.rim`), `LIVE1..6:MODULES` |
| 0x004c4150 | module resources: ERF `HD0:players` (Xbox) group 2; checks `CURRENTGAME:` for `<m>.sav`; ERFs `LIPS:<m>_loc` and `LIPS:localization` group 2; then starts the loader thread (0x004064f0) |
| 0x004064f0 | hands (name, is-module, has-save) to the loader thread and resumes it; the caller spins until it finishes |
| 0x004094a0 | loader thread body. Not a module: RIM `RIMS:<name>`. A module: Xbox `RIMS:<m>_a` / `_adx` if present; temporary directory `MODULES:`; if `<m>.mod` exists ERF `MODULES:<m>` group 2, else RIM `MODULES:<m>_s` if `<m>_s.rim` exists; then from `CURRENTGAME:`: without a save, RIM `CURRENTGAME:<m>` if `<m>` exists there as type 3009 or `.rim`; with a save, ERF `CURRENTGAME:<m>` group 2. If any of the RIM or `.mod` mounts fails, the remaining steps are skipped and the save-game ERF `CURRENTGAME:<m>` (group 2) is tried instead, which then decides success (med, [resources.md](resources.md) 1). The existence tests search every mounted source, not only `MODULES:`. Sets status bits in resman+0x5c |
| 0x004c44d0 | module unload: removes all of the above |

## Textures

| Address | What |
|---|---|
| 0x0070d510 | TPC hook (installed by 0x0070d9c0 into the texture library's callback table): asks `Exists` for the name as `tpc` (3007), `dds` (2033), `4pc` (2059) and `tga` (3), each giving the kind of the table that holds it; loads the TPC if its kind ranks at least as high as every other type's, ranking directory > RIM > ERF > KEY; otherwise returns 0 so another loader is used |
| 0x0067a6d0 | "has texture" test: `tga` or `tpc` exists |

## Streams

| Address | What |
|---|---|
| 0x005a4010 | voice-over path: a resref starting `n`/`N`, 16 long, second character not `_`, opens `HD0:STREAMWAVES\<chars 1-5>\<chars 6-11>\<resref>.wav` (0-based), anything else `HD0:STREAMWAVES\<resref>.wav` |
| 0x005dca30 | sound playback paths: `HD0:STREAMWAVES\%s`, `HD0:STREAMMUSIC\%s`, `HD0:STREAMSOUNDS\%s` |
