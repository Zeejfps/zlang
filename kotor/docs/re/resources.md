# Resources in swkotor.exe: resource manager, type registry, GFF, 2DA, TLK

How the original engine finds, loads and parses resource files. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (image base `0x400000`). Names are ours, in the Aurora/NWN
vocabulary (`CExoResMan`, `CExoKeyTable`, `CRes`, `CResGFF`, `C2DA`, `CTlkTable`), kept in
[names.tsv](names.tsv).
Confidence: **high** = read in the code and consistent with every caller; **med** = behaviour clear,
name or a detail inferred; **low** = a guess. The whole page was rechecked claim by claim on 2026-10-07 against the exports
rebuilt after the noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a
runtime check" rests on static reading alone and is surprising enough to test before relying on it.

Related pages: [resman.md](resman.md) (what is mounted when, texture and stream lookups),
[modules.md](modules.md) (module and area loading), and the format pages in
[../formats/](../formats/) (`resources.md`, `key-bif.md`, `erf.md`, `rim.md`, `gff.md`, `2da.md`,
`tlk.md`, `resource-types.md`). This page is about the engine code; the byte layouts there were
measured on the install and agree with what the readers below expect.

Contents: [1. Resource manager](#1-the-resource-manager-cexoresman) ·
[2. Type registry and CRes classes](#2-the-type-registry-and-the-cres-classes) ·
[3. GFF](#3-gff-cresgff) · [4. 2DA](#4-2da-c2da-and-the-2da-cache) ·
[5. TLK and CExoLocString](#5-tlk-ctlktable-and-cexolocstring) ·
[6. Helpers](#6-helpers-cresref-cexofile-cexostring)

## 1. The resource manager (`CExoResMan`)

### Objects and globals

| Object | Where | What | Conf. |
|---|---|---|---|
| `CExoResMan` | `g_pExoResMan` `0x007a39e8`, 0x60 bytes, built by `0x00409bf0` | owns four lists of key tables (one per container kind), the list of released resources, the async request queue and the module loader thread | high |
| `CExoKeyTable` | 0x34 bytes, `0x0040d030` | one mounted source (a KEY file and its BIFs, a directory, an ERF-family file, or a RIM): a hash table of 0x1c-byte key entries plus the file object(s) that hold the bytes. Fields: +4 disabled, +8 group, +0xc slot count, +0x10 entry array, +0x1c kind 1..4, +0x20 name, +0x28 tagged table id, +0x2c / +0x30 file-object count / array | high |
| `CRes` | 0x28 bytes and up, vtable `0x0073d86c`, `0x00406460` | one resource's in-memory state: demand/request counts, resource id, data pointer, size. Every typed resource (`CResGFF`, `CRes2DA`, `CResTPC`...) derives from it | high |
| `CExoResFile` / `CExoEncapsulatedFile` / `CExoResourceImageFile` | vtables `0x0073e1b0` / `0x0073e1f8` / `0x0073e240`, common base vtable `0x0073e128` | reader for one BIF / one ERF-MOD-SAV / one RIM | high |
| CRC-32 table | `0x007a3d78` (256 dwords) | polynomial 0xEDB88320, used by the key hash; rebuilt by every `CExoKeyTable` constructor | high |

`CExoResMan` layout (all high unless marked):

| Offset | Field |
|---|---|
| +0x00 | total physical memory (GlobalMemoryStatus) |
| +0x04 | memory budget: half of physical memory, at least 16 MB. The halving is a signed shift and a signed compare, so a reported total of 0x80000000 or more gives the 16 MB floor (med: what `GlobalMemoryStatus` reports to the game on a large-memory machine needs a runtime check) |
| +0x08 | bytes still available in the budget (resident resource data is charged to it) |
| +0x10 | list of KEY tables (kind 1) |
| +0x14 | list of directory tables (kind 2) |
| +0x18 | list of ERF tables (kind 3) |
| +0x1c | list of RIM tables (kind 4) |
| +0x20 | released resources: undemanded `CRes` that still hold data, freed when memory is needed |
| +0x24 | async request queue (FIFO, appended at the tail) |
| +0x28 / +0x2c | `CRes` being read asynchronously / its open file |
| +0x30 | `Update` does nothing while it is non-zero; only the constructor writes it (clears it) in the code we have (med) |
| +0x34 | RIMs to unmount: 0x2 `RIMS:MAINMENU` (set by `0x0067b500` on the main menu's way out), 0x1 `RIMS:CHARGEN` (set by `0x006db720`); `0x0040c8e0` and `0x004165e0` remove the flagged RIMs and clear the bits (med) |
| +0x38 / +0x3c | loader thread handle / id |
| +0x40 | critical section around the loader |
| +0x44 | loader state (byte): 0 idle, 1 busy, 2 finished with `<m>_s.rim` mounted, 3 finished otherwise, 4 failed. The only caller waits for "not 1" and does not tell 2, 3 and 4 apart |
| +0x48 | set to make the loader thread exit |
| +0x4c / +0x54 / +0x58 | loader request: module name, "is a module", "comes from a save" |
| +0x5c | loader result bits (see [modules.md](modules.md#mounting-a-modules-files)) |

The lists are `CExoLinkedList`s (head, tail, count; nodes prev/next/data). Tables are added with
`AddHead` (`0x005e9d70`), so **each list runs newest first**.

### Registering sources

`CExoResMan::AddKeyTable(name, kind, group)` (`0x00406e20`, high) is the single entry point; thin
wrappers fix the kind: `AddKeyTableFile` `0x004087e0` (KEY), `AddResourceDirectory` `0x00408800`,
`AddEncapsulatedResourceFile(name, group)` `0x004087a0` (ERF family), `AddResourceImageFile`
`0x004087c0` (RIM). It:

1. picks the kind's list; if a table of the same name is already there it rebuilds that table
   instead (`CExoKeyTable::RebuildTable` `0x00410260`, which reloads the contents and moves any
   live `CRes` objects onto the new entries; one whose resource is gone moves to the entry
   `GetKeyEntry` now finds, or is dumped, or is flagged 0x200 if still demanded; a new entry can
   also take over the `CRes` of the entry `GetKeyEntry` finds when that table's tagged id is lower
   (med on these hand-over rules)) and returns 1; the existing table keeps its group;
2. finds the lowest table id 1..63 not used by another table of that list (0 if all are taken)
   and tags it with the kind (0 KEY, 0x80000000 directory, 0x40000000 ERF, 0x20000000 RIM);
3. creates a `CExoKeyTable`, pushes it at the head of the list, calls
   `CExoKeyTable::Initialize(kind, name, id)` (`0x00410190`), stores `group` at table+8; on failure
   unlinks and deletes it.

The matching removals are `RemoveKeyTable(name, kind)` `0x00407830` and its wrappers
(`RemoveKeyTableFile` `0x004088c0`, `RemoveResourceDirectory` `0x004088d0`,
`RemoveEncapsulatedResourceFile` `0x00408820`, and `RemoveResourceImageFile` `0x00408830`, which
carries an inlined copy for kind 4); removal moves live `CRes` objects to the next table that has
their resource, dumps the undemanded rest and flags demanded orphans 0x200.
`UpdateKeyTable(name, kind)` `0x00407fe0` (wrapper `UpdateResourceDirectory` `0x004088e0`) re-reads
a mounted source in place. Who mounts what, and in which order, is in [resman.md](resman.md) and
[modules.md](modules.md).

`Initialize` dispatches by kind (all high):

| Kind | Loader | What it builds |
|---|---|---|
| 1 KEY | `AddKeyTableContents` `0x0040fb80` | opens `<name>.key` (type 9999), reads the 0x18-byte header: `"KEY V1  "`, BIF count, key count (not both 0), file-table offset, key-table offset. Reads the file table and file names (the bytes between the two offsets) in one block. The table name must carry an alias (`HD0:CHITIN`), else it fails. One `CExoResFile` (0x38 bytes) per 12-byte BIF entry (size, name offset, name length, drive flags u16), named `<alias>:<BIF path up to its first .>` (a BIF name without a `.` fails the whole load); when the drive flags are not 1 and the BIF does not open from there (`LocateBifFile` `0x0040d200`, type 9998), the alias becomes `CD0:`. Each BIF's header is loaded at once (`LoadHeader`, which leaves the BIF open, see [File objects](#file-objects)). Then the 22-byte keys (resref 16, type 2, id 4); the id's top two bits are cleared. Hash table size `1023 + keys / 0.85` (truncated) |
| 2 directory | `AddDirectoryContents` `0x0040f200` | lists the directory (no subfolders); each file whose extension is a known type becomes a key (`GetResRefFromFile` `0x004065a0`: name up to the first `.`, cut to 16; `GetResTypeFromFile` `0x00406650`: the 3 characters after it). Table size `2n + 1` (n = files listed, known type or not) |
| 3 ERF | `AddEncapsulatedContents` `0x0040f3c0` | tries `<name>` as `.nwm`, `.mod`, `.sav`, `.erf`, `.hak` (first that opens); reads the 0xA0 header; the signature must be `"ERF "` for `.erf`, `"HAK "` for `.hak`, `"MOD "` otherwise, version `"V1.0"`, and the entry count non-zero (an empty ERF does not mount); adds the 24-byte keys (resref 16, id 4, type 2, unused 2); one `CExoEncapsulatedFile` (0x44 bytes) serves all reads, its header loaded at once with the extension that opened. Table size `1.2n` (truncated) |
| 4 RIM | `AddResourceImageContents` `0x0040f990` | one `CExoResourceImageFile` (0x34 bytes) which reads the **whole file into memory** (type 3009 tried before `.rim`); keys come from the 32-byte entries (resref 16, type 4, id 4, offset 4, size 4) found at the offset in header+0x10, count at header+0xc (a RIM with no entries does not mount). Table size `1.2n` (truncated) |

### Key entries and resource ids

A key entry is 0x1c bytes: resref (16, lower-cased), `CRes*` (+0x10, null until something asks
for the resource), resource id (+0x14), type (u16 at +0x1a). Empty slots have type 0xFFFF and an
empty resref. `CExoKeyTable::Hash` (`0x0040d500`) runs a CRC-32 (start value 0, no final
inversion, table `0x007a3d78`) over the lower-cased resref bytes up to the first NUL or 16 bytes,
with the type added to each byte before it is mixed in, modulo the table size; `FindKey`
(`0x0040ec50`) probes linearly from there and gives up at the first empty slot or after a full
wrap; `AddKey` (`0x0040e990`) inserts the same way, ignoring an empty resref and a duplicate
(resref, type) within one table (the log message is built but not printed). `AddKey` also writes
the table id into bits 19..14 of the id it is given.

The 32-bit resource id encodes where the bytes are (high):

| Bits | Meaning |
|---|---|
| 31..30 | container kind of the owning table: 0 KEY, 1 RIM, 2 ERF, 3 directory |
| 29..20 | KEY: index of the BIF in the key file (as stored in chitin.key); other kinds: a copy of the table id |
| 19..14 | table id (1..63), used by `GetTable` (`0x004076e0`) to find the owning `CExoKeyTable` |
| 13..0 | index of the resource inside its BIF / ERF / RIM; 0 for a directory |

KEY ids are chitin.key's own with bits 31..30 cleared; ERF and RIM ids keep the low 20 bits of the
entry's own resource-id field (ERF key +0x10, RIM entry +0x14) and put the kind and the table id
above them; directory ids are just kind and table id. So for ERFs and RIMs the index is the
stored resource id, not the key's position; the readers use it to index the resource list, which
works because the files number their entries 0, 1, 2... (high, from the code; the files' side is
in [../formats/erf.md](../formats/erf.md) and [../formats/rim.md](../formats/rim.md)).

Because the engine overwrites bits 31..30 and 19..14 of the ids it reads from chitin.key, a BIF
can hold at most 16,384 resources and a key file at most 1,024 BIFs; ERFs and RIMs are limited to
16,384 entries the same way (high, from the masks).

### Lookup

`CExoResMan::GetKeyEntry(resref, type, &table, &entry)` (`0x00407230`, high) searches, first hit
wins:

1. directories, newest first;
2. ERFs mounted with group 1, newest first;
3. RIMs, newest first;
4. ERFs mounted with group 2, newest first;
5. KEY tables.

Each step is `FindKeyInTableList` (`0x004071a0`): it walks a list from its head, skips tables that
are disabled (table+4, set while a table is being destroyed or rebuilt) and, for the ERF steps,
tables of the other group. An ERF mounted with group 0 is never found by `GetKeyEntry`. Built on
this: `Exists(resref, type, &kind)` (`0x00408bc0`, also reports the kind 1..4 of the container
that has it), `ExistsInTableKind(resref, type, kind)` (`0x00408c00`, one kind only, and for ERFs
any group, 0 included), `GetResObject(resref, type)` (`0x004074d0`, the `CRes` already attached
to the entry, if any) and `SetResObject(resref, type, res)` (`0x00407680`, attaches the `CRes` to
the entry only if the entry has none yet, and gives it the entry's id). The listing helpers
`ListResourcesOfType(type, bErfOnly)` (`0x00407390`: ERFs of every group, then, unless `bErfOnly`,
RIMs, directories and KEY tables, merged) and `ListTableResourcesOfType` (`0x00408c60`, the table
that holds a given `CRes`, e.g. "every `.git` in this module") return resref lists.

### CRes and the demand / release protocol

`CRes` layout (high unless marked):

| Offset | Field |
|---|---|
| +0x00 | vtable: 0 destructor, 1 `GetFixedResourceSize` (-1), 2 `GetFixedResourceDataOffset` (0), 3 `OnResourceFreed`, 4 `OnResourceServiced` (both return 1 in the base). Slots 1 and 2 are named after NWN; every class listed below keeps the base bodies (med) |
| +0x04 | u16 demand count |
| +0x06 | u16 async request count |
| +0x08 | resource id (-1 = not attached) |
| +0x0c | status bits: 0x4 serviced (data valid), 0x10 async read in flight, 0x100 on the released list / free on last release, 0x200 its table went away while it was demanded |
| +0x10 | data pointer |
| +0x14 | key entry pointer |
| +0x18 | size in bytes |
| +0x1c | number of resource helpers sharing this object (set to 1 by `SetResObject`, +1 by every `GetResObject`) |
| +0x20 / +0x24 | allocation variants used by `Malloc`: reserve 6 bytes in front of the data / 10 bytes after it. +0x20 is set by the constructors of MDL (`0x005cea50`), MDX, VIS, TXI, DDS and 4PC; +0x24 by PLT, TGA and TPC. Why they need the space is not known |
| +0x28.. | the subclass's parsed view (section pointers, loaded flag ...) |

The protocol (all high):

- **Demand** (`CRes::Demand` `0x00409b10` → `CExoResMan::Demand` `0x004089f0`): a `CRes` with id
  -1 (no key entry) gives null. If serviced, take it off the released list if it is there, count
  the demand, return the data. Otherwise read it now by container kind: `ServiceFromResFile`
  `0x00407e00` (KEY/BIF; BIF = id bits 29..20, entry = bits 13..0), `ServiceFromImage` `0x00407d50`
  (RIM: the data pointer points **into the resident image**, nothing is copied),
  `ServiceFromEncapsulated` `0x00407bd0` (ERF), `ServiceFromDirectory` `0x004078f0`
  (`<dir>\<resref>.<ext>`, read whole; an empty file fails). The BIF, ERF and directory readers
  size the resource, allocate through `Malloc` `0x004077b0`, read (a short read fails), and call
  the `OnResourceServiced` slot, whose result decides whether the resource counts as serviced;
  the RIM reader sets the serviced bit first and returns the slot's result without clearing it.
  On success the resource is also taken out of the async queue and the demand counted. A resource
  with an async read in flight is finished first (`FinishAsyncRequest` `0x00408530`, spinning with
  `Sleep(5)` until the read completes); if no async file is open it just returns the data pointer
  without counting a demand. Returns the data or null.
- **Malloc** (`0x004077b0`): while the size exceeds the budget left (+0x08) it calls `FreeChunk`;
  when nothing more can be freed it allocates anyway and the budget goes negative.
- **Release** (`CRes::Release` `0x00409b80` → `CExoResMan::Release` `0x00408c90`): one demand
  less. At zero the resource is not freed: it goes to the head of the released list (+0x20), gets
  status 0x100 and keeps its data; if it was already flagged 0x100 (a `Dump` while demanded) it is
  freed instead. `Release` is the only function that adds to that list; `Demand`, `Free` and
  `FreeChunk` remove from it. `FreeChunk` (`0x004070a0`) walks it from the head, so the most
  recently released resource goes first: it skips entries with an async read in flight (0x10),
  unlinks re-demanded ones (clearing 0x100), and for the rest calls `OnResourceFreed`, frees the
  data (never RIM image memory, as `FreeResourceData` `0x00406540`) and unlinks them, until at
  least 0x100000 bytes are freed or the list ends; it returns whether anything was freed.
- **Request** (`CRes::Request` `0x00408620`): the asynchronous variant; refused (0) for a
  serviced resource. The first request appends the resource to the queue at +0x24;
  `CExoResMan::Update` (`0x00408d40`) works on the head one step per call: it drops it if its id is
  -1 or it is serviced, else starts the read (BIF, ERF and directory reads go through
  `ReadResourceAsync`, status 0x10; a RIM resource is serviced at once), else, once the async read
  is complete, calls `FinishAsyncRequest`. `CancelRequest` (`0x004088f0`) drops one request; at
  zero it closes an in-flight read and leaves the queue.
- **Dump** (`0x00408b90`; `CRes::Dump` `0x00409b40`): if demanded, flag 0x100 so the last release
  frees it; otherwise, if it is serviced or being read, call `Free`. `Free` (`0x00407020`) only acts
  on a resource that is on the released list: it calls `OnResourceFreed`, then (unless an async
  read is in flight) unlinks it and frees its data. So a resource that was serviced but never
  demanded and released is not freed by `Dump`.
- **ReadRaw** (`0x00408e30` → per-kind `0x00408080`/`0x004082d0`/`0x00408390`/`0x00408450`):
  copy a resource's bytes into a caller's buffer without keeping them (med). Callers are four
  texture helpers (`0x0070ece0`, `0x0070f590`, `0x00710430`, `0x00710810`). The RIM variant
  (`0x00408390`) calls `Malloc` for the `CRes` and then the RIM `ReadResource`, which is broken
  (see [File objects](#file-objects)), so it cannot work as written (med).

#### Resource helpers (`CResHelper<T, type>`)

Engine objects do not talk to `CExoResMan` directly; they embed a 0x1c-byte helper (vtable,
"requested" flag +4, `T*` +8, resref +0xc) whose `SetResRef(resref, bRequest)` method is
instantiated per type. Every instance has the same body (high): if the resref changes, cancel the
old request, drop the old object with `ReleaseResObject` (`0x00409cf0`; deletes it when no other
helper shares it), then `GetResObject(resref, type)` or `new T` + `SetResObject`, and optionally
`Request`. The owner later calls `Demand`/`Release` on the `T*`. Instances found:

| Type | `SetResRef` | `T` ctor | `T` vtable |
|---|---|---|---|
| 2da (2017) | `0x00413b40` (base of `C2DA`) | `CRes2DA` `0x0041d730` | `0x0073ec9c` |
| ifo (2014) | `0x004c4cc0` (base of `CSWSModule`) | `CResIFO` `0x004c30c0` | `0x00745810` |
| are (2012) | `0x00506c30` (base of `CSWSArea`, at +0x100) | `CResARE` `0x00504830` | `0x0074745c` |
| lyt (3000) | `0x005de5f0` (base of `CLayout`) | `CResLYT` `0x005df3a0` | `0x0074d3b0` |
| ncs (2010) | `0x005d1ac0` (base of the VM, see [vm.md](vm.md)) | `CResNCS` `0x005d4c30` | `0x0074c508` |
| mdl (2002) | `0x00710180` | `CResMDL` `0x005cea50` | `0x0074c404` |
| mdx (3008) | `0x0070fe60` | `CResMDX` `0x00710e10` | `0x0075fbd0` |
| tpc (3007) | `0x0070f800` | `CResTPC` `0x00712ea0` | `0x0075fc5c` |
| tga (3) | `0x0070ee30` | `CResTGA` `0x007129a0` | `0x0075fc48` |
| dds (2033) | `0x00710530` | `CResDDS` `0x00710ea0` | `0x0075fbe4` |
| 4pc (2059) | `0x00710910` | `CRes4PC` `0x00710f90` | `0x0075fbf8` |
| txi (2022) | `0x0070fb90` | `CResTXI` `0x00710db0` | `0x0075fbbc` |
| plt (6) | `0x0070dbf0` | `CResPLT` `0x00710b50` | `0x0075fb94` |
| vis (3001) | `0x0070f0f0` | `CResVIS` `0x00710d50` | `0x0075fba8` |
| lip (3004) | `0x0070c350` | `CResLIP` `0x0070c690` | `0x0075fb20` |
| ltr (2036) | `0x00711110` | `CResLTR` `0x007121b0` | `0x0075fc34` |
| ssf (2060) | `0x006789a0` | `CResSSF` `0x006db650` | `0x00758000` |
| wav (4) | `0x005d5e90` | `CResWAV` `0x005df1b0` | `0x0074d398` |
| wok/dwk/pwk | built directly by `0x00596670` (types from the caller) | `CResBWM` `0x005ceab0` | `0x0074c418` |

`CResGFF` (`0x00410630`) does not use a helper: its constructor calls `SetResObject` and `Demand`
itself. Several text-like types (MDL, NCS, LYT, LIP, VIS, TXI, MDX) share one folded
`OnResourceServiced` (`0x005d4c60`: data at +0x30, size at +0x2c, flag +0x28) and
`OnResourceFreed` (`0x00710e60`). `CResBWM::OnResourceServiced` (`0x005ceae0`) also notes whether
the data starts with `"BWM V1.0"` (binary walkmesh) or is ASCII.

### File objects

All three share a 17-slot interface (vtable order, med): destructor, `AddRefCount`,
`AddAsyncRefCount`, `CloseFile`, `CloseAsyncFile`, `DelRefCount`, `DelAsyncRefCount`, two getters,
`GetResourceSize(id)`, `Initialize`, `OpenFile`, `OpenAsyncFile`, `ReadResource(id, buf, size)`,
`ReadResourceAsync`, `LoadHeader`, `UnloadHeader`; the RIM class adds `GetResourcePointer` as
slot 17. The reference counts open the file on first use and close it on last use. An ERF is
only held open while one of its resources is being read (its `LoadHeader` opens and closes a file
of its own). A BIF is different: `LoadHeader` takes a reference and keeps it on success, so every
BIF whose header loaded at mount time stays open until `UnloadHeader` drops that reference (high).

| Class | Header read | Per-resource lookup | Conf. |
|---|---|---|---|
| `CExoResFile` (BIF) | `LoadHeader` `0x0040d910`: 0x14 bytes, `"BIFFV1  "`, then `count` (header+8) 16-byte variable entries (id, offset, size, type) from the offset at header+0x10 | entry = id bits 13..0 (the entry's own id field is not checked); `ReadResource` `0x0040da20` seeks and reads min(size, entry size) | high |
| `CExoEncapsulatedFile` (ERF/MOD/SAV/HAK/NWM) | `LoadHeader(kind)` `0x0040e1f0`: reopens the file with the type that mounted it, the 0xA0 header (same signature and version checks), the localized-string list, the 8-byte resource list (offset, size) | entry = id bits 13..0 into the resource list; `ReadResource` `0x0040e640` seeks and reads min(size, entry size) | high |
| `CExoResourceImageFile` (RIM) | `OpenFile` `0x0040e790` reads the whole file; there is no separate header step | `GetResourcePointer` `0x0040f160` returns an address inside the image (what `Demand` uses). `ReadResource` `0x0040f1a0` is broken: it indexes the 32-byte entry table with a 4-byte stride and uses the dword it finds as a pointer to the entry, so it cannot copy the right bytes (only `ReadRaw` reaches it) | high |

### Module loader thread

`CExoResMan` owns one worker thread (`LoaderThreadProc` `0x00409b90`, created suspended by the
constructor with a 64 KB stack). `StartModuleLoad(name, bModule, bFromSave)` (`0x004064f0`) spins
while the state is 1, then under the critical section stores the request, sets the state to 1,
clears the result bits and resumes the thread. The thread loops until +0x48 is set: it runs
`LoadModuleResources` (`0x004094a0`) under the critical section (which that function enters
again), and suspends itself. `LoadModuleResources` sets the state byte and the result bits. Its
only caller, `CSWSModule::AddModuleResources`, polls the state every 10 ms while advancing the
load screen. (high)

What it mounts is in [modules.md](modules.md#mounting-a-modules-files). Details that page leaves
out (high unless marked):

- not a module (`bModule` 0): it mounts `RIMS:<name>` as a RIM; state 3, or 4 if that fails;
- the existence tests are `GetKeyEntry` over every mounted source (with `MODULES:` or
  `CURRENTGAME:` mounted as a directory just for the test), so a `<m>.mod` or `<m>_s.rim` found
  elsewhere (an override directory, say) also takes that branch, and the mount then still opens
  `MODULES:<m>`;
- when any RIM or `.mod` mount in the chain fails, the remaining steps are skipped and it tries the
  save-game branch instead: `CURRENTGAME:<m>` as an ERF in group 2 (bit 0x04), whose result then
  decides between state 2/3 and 4 (med: static reading only, needs a runtime check);
- in the not-from-save branch the load counts as successful when `<m>` is in neither form in
  `CURRENTGAME:`; it fails only if that RIM exists and does not mount.

### File-system helpers

`CreateDirectory` `0x004068c0`, `RemoveFile(name, type)` `0x00406b20`, `CopyFile` `0x00406990`,
`GetFreeDiskSpace` `0x004067b0`, `CleanDirectory(dir, bAll, bRecurse)` `0x00409460` and
`RemoveDirectory(dir, bFiles, bAll)` `0x00409480`, both on `0x00408e90`. That one deletes the
folder's files whose extension is a known resource type (others are never deleted, so the folder
cannot then be removed if any remain), stopping at the first failure; with `bAll` it also empties
and removes every subfolder, with `bRecurse` (and not `bAll`) it empties subfolders but keeps
them; `RemoveDirectory` then removes the folder itself (`CleanDirectory` keeps it). `RemoveFile`
refuses a directory and clears a read-only flag before deleting. All take alias paths (`CURRENTGAME:`, `GAMEINPROGRESS:`,
`SAVES:`...) that `CExoBase` resolves through the `[Alias]` section of `swkotor.ini` and built-in
defaults (`0x005e6680`, see [app.md](app.md)). (med)

## 2. The type registry and the CRes classes

`CExoBase` (`g_pExoBase` `0x007a39e0`) holds at +0x14 a small type table object (0xC bytes:
count, array of u16 ids, array of 8-byte `CExoString` extensions), allocated by
`CExoBase::CExoBase` `0x005e6500` and filled by `0x005e8ba0` → `0x005e6d20` (high). It has 88
entries; unknown lookups return the last one (id 0xFFFF, extension `""`).
`CExoBase::GetResourceExtension(type)` `0x005e6660` → `0x005e7a00` (linear search by id, first
match) and `CExoBase::GetResTypeFromExtension(ext)` `0x005e6670` → `0x005e7a40` (case-insensitive
linear search, first match) are the only two queries. The table, in registration order:

```
    0 res      1 bmp      2 mve      3 tga      4 wav      7 ini     10 txt   2022 txi
 9999 key   9998 bif   9997 erf   2000 plh   2001 tex   2002 mdl   2007 lua   2003 thg
 2008 slt   2009 nss   2010 ncs   2011 mod   2012 are   2013 set   2014 ifo   2015 bic
 2016 wok      6 plt   2005 fnt   2017 2da   2018 tlk      8 mp3      9 mpg   2024 bti
 2025 uti   2026 btc   2027 utc   2031 btt   2032 utt   2023 git   2029 dlg   2030 itp
 2033 dds   2034 bts   2035 uts   2036 ltr   2037 gff   2038 fac   2039 bte   2040 ute
 2041 btd   2042 utd   2043 btp   2044 utp   2045 dft   2046 gic   2047 gui   2048 css
 2049 ccs   2050 btm   2051 utm   2052 dwk   2053 pwk   2054 btg   2055 utg   2056 jrl
 2057 sav   2058 utw   2059 4pc   2060 ssf   2061 hak   3000 lyt   3001 vis   3002 rim
   11 wma   3003 pth   3005 bwm     12 wmv   3004 lip   2062 nwm   2063 bik   3006 txb
 3007 tpc   3008 mdx   3009 rsv   3010 sig     13 xmv   3011 xbx     14 log  65535 ""
```

Type 3009 (`rsv`) is used for RIM-like module files: the RIM reader
(`CExoResourceImageFile::OpenFile` `0x0040e790`) tries it before `.rim`; the module code checks
for `<module>.rsv` before `<module>.sav` among the save files (`0x004b51a0`,
`CServerExoAppInternal::LoadModule` `0x004b95b0`), and when found copies it from
`GAMEINPROGRESS:` to `CURRENTGAME:` under the same type; `CSWSModule::SaveModuleIFO`
`0x004c8960` deletes a stale `.rsv` before writing the module's `.sav` (med; no such file in the
PC install). The `CRes` subclasses and the types they serve are in the helper table above; the
GFF-based ones are `CResGFF` (generic, vtable `0x0073e2d0`), `CResIFO` (`0x004c30c0`) and
`CResARE` (`0x00504830`) (subclasses that only preset the 4-character file type; their vtables
differ from `CResGFF`'s only in the destructor slot).

## 3. GFF (`CResGFF`)

`CResGFF` (0xA0 bytes, vtable `0x0073e2d0`) is both the reader and the writer.

| Offset | Field |
|---|---|
| +0x28..+0x3c | growth steps for the six arrays when writing (110 structs, 646 fields, 98 labels, 1836 data bytes, 4052 field-index bytes, 4052 list-index bytes); each step doubles after use |
| +0x40 | header (0x38 bytes: type, version, then offset/count pairs for structs, fields, labels, field data, field indices, list indices; the two index counts are in bytes) |
| +0x44 / +0x48 | struct array (12-byte entries: id, data-or-offset, field count) / capacity |
| +0x4c / +0x50 | field array (12-byte entries: type, label index, data-or-offset) / capacity |
| +0x54 / +0x58 | label array (16-byte names) / capacity |
| +0x5c / +0x60 | field data block / capacity |
| +0x64 / +0x68 / +0x6c | field-index block / capacity / bytes wasted by moves |
| +0x70 / +0x74 / +0x78 | list-index block / capacity / bytes wasted |
| +0x8d | expected 4-character file type (`"UTC "`, `"ARE "`, `"IFO "`...) |
| +0x94 | loaded flag (set by `OnResourceServiced`, cleared by `OnResourceFreed` `0x00410880`) |
| +0x98 | the arrays point into the resource's bytes (read-only) rather than owned heap blocks |
| +0x9c | the resource is demanded |

Loading (high): `CResGFF(type, fileType, resref)` (`0x00410630`) attaches a `CResGFF` to the key
entry and demands it (sets `+0x9c` only if data came back, else releases the binding).
`OnResourceServiced` (`0x00410740`) accepts the data only if the first four bytes equal the
expected file type and the next four equal `"V3.2"` (`g_pszGFFVersion` `0x0078d3cc`); it then
points the six arrays straight into the loaded bytes (a section whose count is 0 stays null; no
copy, no validation beyond that). Callers check `+0x94` after constructing (e.g.
`CSWSArea::LoadGIT` `0x0050dd80`, `CSWSCreature::LoadFromTemplate` `0x005026d0`).
`ReleaseResource` (`0x004108c0`) gives the resource back and clears all array pointers.

Handles: a `CResStruct` is a struct index (`GetTopLevelStruct` `0x00411240` sets it to 0). A
`CResList` is the owning struct index followed by the 16-byte label; every list access looks the
field up again by label.

Field access (high): `GetFieldByLabel(struct, label)` (`0x00411630`) cuts the label to 16 bytes
and compares it (exact, case-sensitive) with the 16-byte label of each of the struct's fields in
order, returning the first match (no hashing); `GetField(struct, n)` (`0x00410990`) takes the
struct's data as the field index itself when it has one field, else as a byte offset into the
field-index block. Simple values (types 0-5, 8) live in the field entry's data word; others are at
`field data + data word` (`GetFieldData` `0x00410a20`), lists at `list indices + data word`
(`GetListData` `0x00410a60`).

The readers all have the shape `Read<Type>(struct, label, &bSuccess, default)`: they set
`bSuccess` and return the value, or return the default and clear `bSuccess` when the label is
missing, the type differs, or the data would run past its block. Types follow the Aurora
numbering:

| Type | Reader | Writer | Storage |
|---|---|---|---|
| 0 BYTE | `0x00411a60` | `0x00412620` | data word (zero-extended) |
| 1 CHAR | `0x00411ad0` | `0x00412670` | data word (sign-extended) |
| 2 WORD | `0x00411b40` | `0x004126c0` | data word (zero-extended) |
| 3 SHORT | `0x00411bb0` | `0x00412710` | data word (sign-extended) |
| 4 DWORD | `0x00411c20` | `0x00412760` | data word |
| 5 INT | `0x00411c90` | `0x004127b0` | data word |
| 6 DWORD64 | `0x00411d70` | `0x00412800` | 8 bytes in field data |
| 7 INT64, 9 DOUBLE | none in this build | none | — |
| 8 FLOAT | `0x00411d00` | `0x00412870` | data word |
| 10 CExoString | `0x00411ec0` | `0x00412970` | u32 length + chars |
| 11 CResRef | `0x00411e10` | `0x004128c0` (lower-cases A-Z) | u8 length + chars |
| 12 CExoLocString | `0x00411fd0` | `0x00412a10` | u32 size of what follows, u32 strref, u32 count, then per string u32 id (language*2 + gender), u32 length, chars; the reader rejects it unless the sizes add up exactly |
| 13 VOID | `0x00412380` | `0x00412c10` | u32 length + bytes (the reader copies at most the caller's buffer size) |
| 14 Struct | `GetStructFromStruct` `0x00411a10` | `AddStruct` `0x004125b0` | struct index in the data word |
| 15 List | `GetList` `0x004118c0`, `GetListCount` `0x00411940`, `GetListElement` `0x00411990` | `AddList` `0x00412450`, `AddListElement` `0x004124e0` | u32 count + struct indices in the list-index block |
| 16 Orientation | `0x004121b0` | `0x00412ca0` | four floats |
| 17 Vector | `0x004122a0` | `0x00412d30` | three floats |

Writing (high): `CreateGFFFile(&topStruct, fileType, version)` (`0x00411260`) on an empty
`CResGFF` (`0x004105a0`; a loaded one is released first) writes the header type and a top struct
with id -1. The version argument is only checked to be at least 4 characters long and is otherwise
ignored: the header always gets `"V3.2"` (so callers that pass `"V2.0"` still write V3.2, as
[party-items-saves.md](party-items-saves.md) 1.2 notes; labels are cut to 16 characters, 1.9).
The first write to a loaded GFF copies
its sections into owned heap arrays (`InitializeForWriting` `0x00410aa0`). `AddField`
(`0x00411730`) appends a field (data word preset to 0xFFFFFFFF) and its label: `AddLabel`
(`0x00410e20`) cuts the label to 16 bytes and reuses an existing identical label, so each label is
stored once. A struct's first field index sits in its data word; at its second field both indices
go to a new 8-byte block at the end of the field-index block; each later field grows that block in
place when it is the last one, otherwise copies it to the end and counts the old bytes as wasted
(`+0x6c`). Lists behave the same way in the list-index block: `AddList` appends a count of 0, and
`AddListElement` grows the list in place or moves it to the end (`+0x78`). Arrays that fill up are
reallocated to the current size plus their growth step, and the step then doubles.
`WriteGFFFile(name, type)` (`0x00413030`) opens the alias path for writing, calls `Pack(0, 0)`
(`0x00412db0`) and `WriteGFFData` (`0x004113d0`), which writes the 0x38-byte header followed by
structs, fields, labels, field data, field indices and list indices, in that order, packed from
offset 0x38. `Pack` compacts only when there is wasted space and it is at least 1% of the total
size (`waste * 100 / total > 0`); it then rebuilds the field-index block in struct-array order and
the list-index block in field-array order of the List fields. Below that threshold the dead bytes
are written to the file (med; needs a runtime check). Saves put GFFs straight into an ERF with
`CERFFile::AddResource` (below), which also calls `Pack(0, 0)` and `WriteGFFData`.
## 4. 2DA (`C2DA`) and the 2DA cache

`C2DA` (0x54 bytes, vtable `0x0073e2f8`) is a resource helper over `CRes2DA` plus the parsed table.

| Offset | Field |
|---|---|
| +0x00..+0x1b | `CResHelper<CRes2DA,2017>` (vtable, requested flag, `CRes2DA*`, resref) |
| +0x1c | default value (`CExoString`), returned when the row or column is out of range |
| +0x24 / +0x28 | row count / column count |
| +0x2c | loaded (set by `Load2DArray`, cleared by `Unload2DArray` `0x004139e0`) |
| +0x30 / +0x34 / +0x38 | text format: row labels, column labels, rows (each an array of `CExoString`) |
| +0x3c | binary format flag (copied from `CRes2DA`+0x38) |
| +0x40 / +0x44 | binary: cell string base / u16 cell offsets (row-major) |
| +0x48 / +0x4c / +0x50 | binary: label string base / row-label offsets / column-label offsets |

`CRes2DA::OnResourceServiced` (`0x0041d790`, high) accepts `"2DA V2.b"` (sets the binary flag) and
`"2DA V2.0"` and rejects anything else; its data pointer and size (`0x00404dd0`, `0x00710e50`,
folded getters) skip the 8-byte header.

`C2DA::C2DA(resref, bRequest)` (`0x00413cc0`) binds the helper (`SetResRef` `0x00413b40` finds or
creates the `CRes2DA` in the resource manager and, when `bRequest` is non-zero, queues an
asynchronous request; the cache loaders pass 0). Nothing is parsed until `Load2DArray`
(`0x004143b0`, high), which unloads any previous contents, demands the resource (returning 0 if
that fails), copies the binary flag, skips leading whitespace, then:

- looks at the first token of the first line, upper-cased: if it is exactly `DEFAULT:`, the next
  token is the default value and parsing resumes right after it; if it is exactly `DEFAULT`, the next token
  (minus a leading `:`; a lone `:` takes the token after it) is the default value, but the parse
  cursor is not advanced past that line (only the remaining size shrinks by its length), so the
  column labels are then read from the `DEFAULT` line itself (asm `0x004144c5`..`0x00414546`; med,
  text tables only, needs a runtime check). Without a `DEFAULT` token the first line is the
  column-label line. The column count is the number of tokens on that line (`GetNextToken`
  `0x004137e0`: tokens end at space, TAB, CR, LF or NUL; an empty token ends the count);
- **binary**: works in place in the resource bytes (which stay demanded): the column labels (each
  followed by a TAB, the list closed by a NUL) are NUL-terminated where they stand and their
  offsets recorded, then the u32 row count, the tab-separated row labels, the rows x columns u16
  cell offsets, a u16 data size (skipped, never read), and the cell strings;
- **text**: builds `CExoString` arrays: lower-cased column labels; one row per remaining non-blank
  line, its first token the lower-cased row label, then one string per cell (a token starting with
  `"` runs to the next `"`; missing trailing cells take the default value, `****` becomes `""`),
  then releases the resource.

Lookups (all high; the four overload families take row as index or label and column as index or
label; labels compare case-insensitively with a linear scan, `GetColumnIndex` `0x00413100`,
`GetRowIndex` `0x004138b0`):

| Value | (row index, column label) | (row index, column index) | (row label, column label) | (row label, column index) |
|---|---|---|---|---|
| `CExoString` | `0x00413270` | `0x00413190` | `0x00413de0` | `0x00413ec0` |
| float (`sscanf "%f"` / atof) | `0x00413430` | `0x00413350` | `0x00413fa0` | `0x00414080` |
| int (`sscanf "%i"`; text `atol`, or `%x` for a `0x`/`0X` cell longer than 2 characters) | `0x00413660` | `0x00413510` | `0x00414110` | `0x00414260` |

Every getter returns false with the default value (as string, or `atof`/`atol` of it) when the row
or column is out of range or a label is not found, and false with `""` / 0.0 / 0 (not the default)
when the cell is empty; a non-empty cell returns true. A binary table has no `DEFAULT` line, so its
default is `""` and the two cases give the same value. The text format stores every cell as text; binary cells
are parsed on every call. No getter checks the loaded flag.

### The global cache (`C2DAs`)

`CSWRules` (`g_pRules` `0x007a3a28`, 0xdc bytes, constructor `0x00552c50`; created by
`CClientExoAppInternal::PostInitialize` `0x005f51c0` when `g_pRules` is null, or, when the role
byte below is 2, by `CServerExoAppInternal::Initialize` as a subclass via `0x0057a1f0`) keeps at
+0xb8 a 0x12c-byte `C2DAs` object (`0x005bfb60`). The constructor ignores the result of
`C2DAs::Load2DArrays` (`0x005c4c20`, high), which runs:

1. the IPRP lists, whose results are ignored: `0x005c4730` loads `iprp_costtable.2da` and one `C2DA`
   per row named by its `Name` column (array at C2DAs+0x00, count byte at +0x08; when the role
   byte is 1, rows whose `ClientLoad` is 0 or blank are left null); `0x005c49c0` does the same for
   `iprp_paramtable.2da` with `TableResRef` (array +0x04, count byte +0x09). A row whose table
   fails to load stops that list; the master table is freed. `0x005c49a0` / `0x005c4c00` return
   the cost / param table for an index (null when out of range);
2. the single tables, stopping (returning 0) at the first one that does not load, in this order:
   appearance, gender, surfacemat, visualeffects, vfx_persistent, creaturespeed, doortypes,
   genericdoors, placeables, loadscreens, iprp_meleecost, itempropdef, portraits,
   iprp_damagecost, traps, lightcolor; then, unless the role byte is 2, the *client* group
   (cursors, ambientmusic, ambientsound, footstepsounds, appearancesndset, weaponsounds,
   ammunitiontypes, keymap, bindablekeys, placeableobjsnds, camerastyle, tutorial, difficultyopt,
   gamma); then, unless the role byte is 1 (which returns 1 here), the *game* group (statescripts,
   poison, disease, repadjust, fractionalcr, encdifficulty, excitedduration, regeneration,
   xptable, iprp_monstcost, iprp_bonuscost, iprp_srcost, iprp_neg5cost, ranges, iprp_onhit,
   iprp_onhitdur, damagehitvisual, animations, bodybag, forceadjust, gameeffects, repute,
   weapondischarge, droiddischarge, plot, combatanimations, dialoganimations, npc, spells, feat,
   formations, grenadesnd, planetary, feedbacktext, forceshields, heads, itemvalue, videoeffects,
   movies, effecticon, removefxondeath, texpacks). `gameeffects` is loaded twice in a row; the
   first `C2DA` is overwritten without being freed.

The role byte `0x007a39dc` is only ever read (seven compare sites) and is 0 in the image, so the
single-player game loads every group (high); that 1 means "client only" and 2 "server only" is
inferred from the two guards (med). A loader whose table fails leaves its half-built `C2DA` in the
slot, except effecticon, removefxondeath and texpacks, which delete it and clear the slot.

| Offset | 2DA | Loader | | Offset | 2DA | Loader |
|---|---|---|---|---|---|---|
| +0x0c | appearance | `0x005c0270` | | +0x84 | statescripts (*game*) | `0x005c27c0` |
| +0x10 | gender | `0x005c0ae0` | | +0x88 | visualeffects | `0x005c0c80` |
| +0x14 | surfacemat | `0x005c0bb0` | | +0x8c | traps | `0x005c1e60` |
| +0x18 | loadscreens | `0x005c1b40` | | +0x90 | poison (*game*) | `0x005c2860` |
| +0x1c | vfx_persistent | `0x005c1010` | | +0x94 | disease (*game*) | `0x005c2900` |
| +0x20 | creaturespeed | `0x005c1580` | | +0x98 | repadjust (*game*) | `0x005c29a0` |
| +0x24 | doortypes | `0x005c1690` | | +0x9c | fractionalcr (*game*) | `0x005c2a40` |
| +0x28 | genericdoors | `0x005c1760` | | +0xa0 | excitedduration (*game*) | `0x005c2b80` |
| +0x2c | placeables | `0x005c1830` | | +0xa4 | regeneration (*game*) | `0x005c2c20` |
| +0x30 | iprp_meleecost | `0x005c1be0` | | +0xa8 | encdifficulty (*game*) | `0x005c2ae0` |
| +0x34 | itempropdef | `0x005c1c80` | | +0xac | iprp_monstcost (*game*) | `0x005c2de0` |
| +0x38 | portraits | `0x005c1d20` | | +0xb0 | iprp_damagecost | `0x005c1dc0` |
| +0x3c | animations (*game*) | `0x005c32e0` | | +0xb4 | iprp_bonuscost (*game*) | `0x005c2e80` |
| +0x40 | dialoganimations (*game*) | `0x005c3bf0` | | +0xb8 | iprp_srcost (*game*) | `0x005c2f20` |
| +0x44 | heads (*game*) | `0x005c4270` | | +0xbc | iprp_neg5cost (*game*) | `0x005c2fc0` |
| +0x48 | lightcolor | `0x005c1f00` | | +0xc0 | xptable (*game*) | `0x005c2d40` |
| +0x4c | cursors (*client*) | `0x005c1fa0` | | +0xc4 | ranges (*game*) | `0x005c3060` |
| +0x50 | ambientmusic (*client*) | `0x005c2040` | | +0xc8 | iprp_onhit (*game*) | `0x005c3100` |
| +0x54 | ambientsound (*client*) | `0x005c20e0` | | +0xcc | iprp_onhitdur (*game*) | `0x005c31a0` |
| +0x58 | footstepsounds (*client*) | `0x005c2180` | | +0xd0 | damagehitvisual (*game*) | `0x005c3240` |
| +0x5c | appearancesndset (*client*) | `0x005c08f0` | | +0xd4 | bodybag (*game*) | `0x005c3670` |
| +0x60 | weaponsounds (*client*) | `0x005c2290` | | +0xd8 | forceadjust (*game*) | `0x005c3710` |
| +0x64 | ammunitiontypes (*client*) | `0x005c2360` | | +0xdc | gameeffects (*game*) | `0x005c3830` |
| +0x68 | keymap (*client*) | `0x005c2400` | | +0xe0 | repute (*game*) | `0x005c38d0` |
| +0x6c | bindablekeys (*client*) | `0x005c24a0` | | +0xe4 | weapondischarge (*game*) | `0x005c3970` |
| +0x70 | placeableobjsnds (*client*) | `0x005c1980` | | +0xe8 | droiddischarge (*game*) | `0x005c3a10` |
| +0x74 | camerastyle (*client*) | `0x005c2540` | | +0xec | plot (*game*) | `0x005c3ab0` |
| +0x78 | combatanimations (*game*) | `0x005c3b50` | | +0xf0 | npc (*game*) | `0x005c3d70` |
| +0x7c | difficultyopt (*client*) | `0x005c2680` | | +0xf4 | spells (*game*) | `0x005c3e10` |
| +0x80 | gamma (*client*) | `0x005c2720` | | +0xf8 | feat (*game*) | `0x005c3eb0` |
| +0x118 | tutorial (*client*) | `0x005c25e0` | | +0xfc | formations (*game*) | `0x005c3f50` |
| +0x11c | movies (*game*) | `0x005c4450` | | +0x100 | grenadesnd (*game*) | `0x005c3ff0` |
| +0x120 | effecticon (*game*) | `0x005c44f0` | | +0x104 | planetary (*game*) | `0x005c4090` |
| +0x124 | removefxondeath (*game*) | `0x005c45b0` | | +0x108 | feedbacktext (*game*) | `0x005c4130` |
| +0x128 | texpacks (*game*) | `0x005c4670` | | +0x10c | forceshields (*game*) | `0x005c41d0` |
| | | | | +0x110 | videoeffects (*game*) | `0x005c43b0` |
| | | | | +0x114 | itemvalue (*game*) | `0x005c4310` |

Seventeen loaders also cache column indices in globals right after loading (`GetColumnIndex`,
stored unchecked, so -1 if the column is missing); the other loaders only load the table (high):

| 2DA | Columns (globals) |
|---|---|
| appearance | 28 columns, `0x007a20c0`..`0x007a212c`: `ABORTONPARRY`, `BACKUPHEAD`, `CameraHeightOffset`, `CAMERASPACE`, `CREPERSPACE`, `DisableInjuredAnim`, `DRIVEACCl`, `DriveAnimRun`, `DriveAnimWalk`, `DriveMaxSpeed`, `ENVMAP`, `FootstepType`, `GROUNDTILT`, `HEAD_ARC_H`, `HEAD_ARC_V`, `HEADBONE`, `HEADTRACK`, `HEIGHT`, `hitdist`, `HITRADIUS`, `MODELTYPE`, `NORMALHEAD`, `PERSPACE`, `RACE`, `RUNDIST`, `SIZECATEGORY`, `SoundAppType`, `WALKDIST` |
| appearancesndset | `0x007a2130`..`0x007a2144`: `FallDirt`, `FallMetal`, `FallHard`, `FallWater`, `Weapon`, `ArmorType` |
| gender | `GENDER` `0x007a2148` |
| animations | 14 columns, `0x007a214c`..`0x007a2180`: `FireForget`, `Overlay`, `Looping`, `Stationary`, `Pause`, `Walking`, `Running`, `Damage`, `Parry`, `Dialog`, `Name`, `Dodge`, `Attack`, `HideEquippedItems` |
| forceadjust | `GoodCost` `0x007a2184`, `EvilCost` `0x007a2188` |
| dialoganimations | `0x007a218c`..`0x007a2198`: `FireForget`, `Dialog`, `Looping`, `Overlay` |
| footstepsounds | `Rolling` `0x007a219c`, `PitchOffset` `0x007a21a0` |
| weaponsounds | `PitchOffset` `0x007a21a4` |
| regeneration | `HealthRegen` `0x007a21a8`, `ForceRegen` `0x007a21ac` |
| surfacemat | `Name` `0x007a21b0` |
| visualeffects | 13 columns, `0x007a21b4`..`0x007a21e4`: `Imp_HeadCon_Node`, `Imp_Impact_Node`, `Imp_Root_M_Node`, `Imp_Root_S_Node`, `Imp_Root_L_Node`, `Imp_Root_H_Node`, `LowQuality`, `OrientWithGround`, `ShakeType`, `ShakeDuration`, `ShakeDelay`, `SoundImpact`, `SoundDuration` |
| vfx_persistent | 23 columns, `0x007a21e8`..`0x007a2240`: `DurationVFX`, `OrientWithGround`, `SHAPE`, `RADIUS`, `WIDTH`, `LENGTH`, `MODELMIN01`, `MODEL01`, `MODELMIN02`, `MODEL02`, `MODELMIN03`, `MODEL03`, `NUMACT01`..`03`, `DURATION01`..`03`, `EDGEWGHT01`..`03`, `SoundOneShot`, `SoundOneShotPercentage` |
| creaturespeed | `RUNRATE` `0x007a2244`, `WALKRATE` `0x007a2248` |
| doortypes / genericdoors | `SoundAppType` `0x007a224c` / `0x007a2250` |
| placeables | `SoundAppType` `0x007a2254`, `StrRef` `0x007a2258`, `IgnoreStaticHitcheck` `0x007a225c` |
| placeableobjsnds | `0x007a2260`..`0x007a2270`: `ArmorType`, `Locked`, `Opened`, `Closed`, `Destroyed` |

The `CSWRules` constructor loads the rest itself, in this order (high):

| Step | 2DA | Loader | Stored in `CSWRules` |
|---|---|---|---|
| 1 | ranges (temporary) | inline | `PrimaryRange` / `SecondaryRange` floats of rows 0–4 and row 19 at +0x04..+0x18 / +0x1c..+0x30 |
| 2 | the `C2DAs` cache | `0x005c4c20` | +0xb8 |
| 3 | spells | `CSWSpellArray::Load` `0x0059ba20` | +0x8c ([rules.md](rules.md) 3.1) |
| 4 | feat, masterfeats | `0x005515e0` | 0x48-byte feat records at +0x90 (u16 count +0xa4); master feats at +0x94/+0x98/+0x9c (count byte +0xa8) |
| 5 | baseitems | `CSWBaseItemArray::Load` `0x005b31d0` | +0x34 ([combat.md](combat.md) 2) |
| 6 | exptable (temporary) | inline | `XP` of rows 0–20 at +0x38..+0x88 ([rules.md](rules.md) 4.1) |
| 7 | skills | `0x00550590` | 0x20-byte records at +0xb4 (count byte +0xab) |
| 8 | classes | `0x0054f2c0` | 0x1a0-byte records at +0xac (count byte +0xa9), plus each class's own tables (`CSWClass::Load*`, `0x005bcda0`..`0x005be4c0`) |
| 9 | racialtypes | `0x0054fec0` | 0x34-byte records at +0xb0 (count byte +0xaa) |
| 10 | diffsettings (temporary) | `CSWRules::LoadDiffSettings` `0x00550c50` | columns 1–5 of rows 0–5 as bytes at +0xbc..+0xd9 (blank = 0) |

Many other 2DAs are opened ad hoc with a temporary `C2DA` (the constructor has 119 calling
functions, the loaders above among them), e.g. `stringtokens.2da` by the TLK code and
`texpacks.2da` at start-up.

## 5. TLK (`CTlkTable`) and `CExoLocString`

`CTlkTable` (0x58 bytes, constructor `0x0041d8d0`; the client builds a 100-byte subclass with vtable
`0x0074e700`), global `g_pTlkTable` `0x007a3a08`. The client's `Initialize` (`0x005f8550`, run from
`WinMain`) always builds the subclass, stores it in `g_pTlkTable` (and `0x007a3a0c`), calls
`SetTlkFile("HD0:DIALOG")` and then opens the Xbox Live slots (`0x005f4180`). The server's
`Initialize` (`0x004b63e0`) builds a base table and calls `SetTlkFile("HD0:dialog")` only when
`g_pTlkTable` is still null, which never happens in the normal game (the server is created later,
when a game starts). Layout (high unless marked):

| Offset | Field |
|---|---|
| +0x00 | vtable `0x0073ecdc`, one slot: resolve a named token (entry, out text). Empty in the base class (`0x005b5e90`); the client override `0x00674b90` dispatches on the token's action code (player name, class, gendered strrefs ...) (med for what each action does) |
| +0x04..+0x3b | seven slots of (male file, female file) `CTlkFile*` pairs: male at +0x04 + 8·n, female at +0x08 + 8·n |
| +0x3c | byte: gender of the current fetch (0 male/neutral, 1 female) |
| +0x40 / +0x44 | named tokens from `stringtokens.2da` (0x24-byte entries, see `SetTlkFile`), sorted by hash / count |
| +0x48 / +0x4c | custom tokens: 0xC-byte entries (number, `CExoString`), sorted by number / count |
| +0x50 | suppress flag: while set, `ParseStr` drops the literal text between tokens; cleared at the start of every `ParseStr`, set and cleared by the client's handler for conditional tokens (med) |
| +0x54 | debug flag: `Fetch` and `GetSimpleString` prefix the text with `[strref]` (`"[%d]%s"`) |

`SetTlkFile(path)` (`0x0041e5a0`, high) opens `path` into slot 0 (`OpenFile`) and returns 0 if that
fails. Otherwise it frees the old named-token table and loads the `StringTokens` 2DA; if that fails
it returns 0 with +0x40 still pointing at the freed table (harmless for the single call the game
makes). Each row becomes a 0x24-byte entry: +0x00 hash of the token (`ComputeCRC32` `0x00410560`:
the reflected CRC-32 table of polynomial 0xEDB88320, but starting from 0, without the final
inversion, and stopping at a NUL), +0x04 the token text (column 0 `token`), +0x0c `actioncode`
(column 1), +0x10..+0x1c `strref1`..`strref4` (columns 3-6), +0x20 `default` (column 2); `category`
(column 7) is not read. Rows are insertion-sorted by hash as they are read; the count is the row
count. Returns 1.

`OpenFile(path, slot)` (`0x0041d920`) accepts slot 0..7 (slot 7 would overlap +0x3c..+0x43; only
0..6 are used) and fails on an empty path. It closes the slot's files, opens `<path>.tlk` through
`CTlkFile` (`0x0041d810`, 0x18 bytes: a `CExoFile` opened `"rb"` as type 2018 plus a copy of the
20-byte header, read and checked for `"TLK "` by `0x0041d890`), then `<path>F.tlk` (the female
table). Without a female file the female slot points at the male one; a female file whose header
fails the check closes both and fails the slot. Callers: `SetTlkFile` (slot 0) and `0x005f4180`
(`LIVEn:liven` into slots 1-6).

`FetchInternal(strref, result, bParse)` (`0x0041e1a0`, high) does **no caching**: every call seeks
and reads. Strref 0xFFFFFFFF, or a gender byte above 1, gives an empty text and sound and returns 1.
Otherwise it masks the strref to 24 bits and tries the seven slots in order with the current
gender, skipping a slot without a file, one whose string count is not above the strref, one where
the entry would start past the end of the file, and one whose read fails. The entry is read at
`20 + strref * size`, where size is 40 for version `"V3.0"` (`g_pszTLKVersion` `0x0078d3ec`,
compared per file) and 36 otherwise: flags, sound resref (16), volume and pitch variance, text
offset, text length, sound length (V3.0; 0 for a 36-byte entry). An entry with flag 0x8000 counts
as missing (next slot). Flag 0x4 = sound length valid (else 0), 0x2 = sound resref valid (else
empty), 0x1 = text present: `text length` bytes are read from `strings offset + text offset`;
without 0x1 the result's text is left as the caller passed it (both wrappers pass an empty one).
Only the start of the text is checked: if it lies past the end of the file the text becomes the
strref in decimal, the sound resref is cleared and the call returns 0 at once; a failed seek gives
empty text and sound and returns 0. With the female gender and no hit it sets the gender byte to
male and retries; with no hit otherwise the result is empty and it returns 0; a hit returns 1.
`bParse` runs `ParseStr` on the text, but both callers pass 0, so the talk table never replaces
tokens itself: the GUI calls `ParseStr` on the fetched text (19 functions: dialogue entries,
message boxes, barks, load-screen hints, tutorial boxes ...). The result block (0x1c bytes) is a
`CExoString` text (+0x00), a `CResRef` sound (+0x08) and a float length (+0x18).

- `Fetch(strref, result, gender)` `0x0041e550` — sets the gender byte, no token parsing; 35 callers;
- `GetSimpleString(strref)` `0x0041e8f0` — text only, male/neutral; 42 callers;
- `ParseStr(text)` `0x0041dd30` — scans for `<`: `<<` is a literal `<`; `<CUSTOMn>` (case-sensitive
  `CUSTOM`, then decimal digits) is replaced by custom token n (`SetCustomToken` `0x0041db50`:
  sorted insert or replace, negative numbers ignored; `ClearCustomTokens` `0x0041dcf0`, called only
  by `CServerExoAppInternal::UnloadModule`; restored from the module IFO's `Mod_Tokens` list
  (`Mod_TokensNumber`, `Mod_TokensValue`) by `CSWSModule::LoadModuleStart`); any other `<name>` is
  looked up by hash (binary search), then by an exact, case-sensitive compare, and resolved through
  vtable slot 0. An unknown or unset token, a name whose hash matches a different token, `<>`, a
  non-digit after `CUSTOM` and a `<` with no closing `>` all become `<UNRECOGNIZED TOKEN>`, and on the
  base class (empty slot 0) so does every named token. A text with neither a token nor `<<` is left
  untouched;
- `GetLanguageID` `0x0041e0f0` — `LanguageID` from the slot-0 male file's header, 0 without a file;
  read once by the client's `Initialize` (5 selects the Polish code page, see
  [../formats/tlk.md](../formats/tlk.md)).

`CExoLocString` (8 bytes, constructor `0x005e9e10`: a pointer to an internal 0xC-byte object, which
holds a linked list of (id, `CExoString`) entries, their count and a flag set once TLK text has been
cached in it, and the strref at +4, -1 when empty) is the localized string of GFF type 12. Ids are
`language * 2 + gender`, and the gender is forced to 0 for language 0 (English), for the TLK fetch
too, so an English string always comes from the male table. `GetString(language, out, gender)`
(`0x005ea130`, high) returns the embedded string for that id if there is one; else, if
`g_pTlkTable` exists, it fetches the strref with that gender (`Fetch`, no token parsing), returns
it, and if it is not empty stores it in the list under that id and sets the cached flag. There is
no fallback to other languages' embedded strings. Because the GFF writer (`0x00412a10`) writes
every entry of the list, a localized string read through `GetString` before saving carries its TLK
text as an embedded substring in the saved GFF (med; it matches the save's LocStrings that have
both a StrRef and a substring, [../formats/gff.md](../formats/gff.md)).
`GetStringNoCache` (`0x005ea050`) does the same without storing; `GetEmbeddedString`
(`0x005ea240`) never touches the TLK; `AddString` (`0x005ea340`) removes any entry with that id,
then stores the value unless it equals what `GetString` now returns (the TLK text, which
`GetString` itself caches when it is not empty); `operator==` (`0x005e9f10`) compares only the
strrefs when either side holds cached text (med); the enumeration helpers are `GetStringCount`
`0x005e9ef0`, `GetStringByIndex` `0x005e9eb0` (splits the id into language and gender),
`GetStringLength` `0x005e9f00` (length of the n-th entry).

## 6. Helpers: CResRef, CExoFile, CExoString

- **`CResRef`** (16 bytes, NUL-padded, not necessarily NUL-terminated): every assignment and every
  constructor but one lower-cases (`0x00406d80` from C string via `SetFromCStr` `0x00406290`,
  `0x00406d60` from `CExoString` via `0x004061f0`, `0x00406da0` / `0x00406170` from a raw 16-byte
  archive field, `0x00406120` copy). The exception is `CResRefFromChars` (`0x00405ef0`, n bytes),
  whose only caller is `CResGFF::ReadFieldCResRef` (`0x00411e10`): GFF resrefs are read with their
  case kept (every ResRef in the shipped data is already lower-case). Comparisons: `0x004060b0`
  (16-byte equality, so case-sensitive), `0x004060d0` (case-insensitive against a C string, at most
  16 characters), `0x00406dc0` (not equal). Conversions: `GetResRefStr` `0x00405f70` (to
  `CExoString`), `CopyToString` `0x00405fb0` (char[17]), `GetResRefCStr` `0x00405fe0` (one of four
  rotating 17-byte static buffers at `0x007a3d00`). (high)
- **`CExoFile`** (`0x005e68d0`, a pointer to a 0x14-byte internal object): resolves `alias:path`
  with the extension of a resource type (`CExoAliasList::ResolveFileName`) and opens it with a
  `fopen` mode; `Read` `0x005e6960`, `Write` `0x005e69a0`, `Seek` `0x005e6aa0`, `GetSize`
  `0x005e6950`, `IsOpened` `0x005e6a10`, async read `0x005e6980` / `0x005e6990` (on a worker
  thread). (high)
- **`CERFFile`** (`0x005dd9c0`, 0xD0 bytes, med): the ERF writer. `Create` (`0x005dcfc0`) always
  opens a `sav` file (type 2057, `"wb"`), and every caller sets the signature with
  `SetFileType("MOD V1.0")` `0x005dce30` and writes the 160-byte header with `WriteHeader`
  `0x005dd080` (build year and day from the clock). Two uses: the save game (`SAVEGAME.sav`, by
  `DoSaveGame` `0x004b3110` and `WriteTransitionAutoSave` `0x004b8300`): `AddDirectory`
  `0x005de1a0` (the whole `GAMEINPROGRESS:` folder: `SetNumEntries` to the file count, then
  `AddFile` `0x005ddbc0` per file, its type taken from the extension), then `Finish` `0x005dd0e0`;
  and a module's own state archive (`CSWSModule::SaveModuleIFO` `0x004c8960`: `SetNumEntries(3)`
  `0x005dda50`, entries added by `AddResource` `0x005ddf30` from `SaveGIT` and others, which packs
  GFFs and writes them straight into the archive; closed by `CSWSModule::FinishModuleSave`).
  `SetNumEntries` reserves the key list and the resource list (0xBAADF00D placeholders) that each
  added file fills in. Reading, to load a save: `ReadHeader` `0x005dce50`, `ReadLists` `0x005dd3c0`
  (expects the localized-string, key and resource lists back to back from offset 0xA0) and
  `ExtractAll` `0x005dd710` (every entry to a folder as `resref.ext`); `DoSaveGame` also reads the
  new file's header and lists back after writing it.
- **`CExoString`** (pointer + allocated size; `GetLength` `0x005e5790` counts to the NUL, 0 for a
  null pointer): the constructors, `CStr` (`0x005e5670`, never null: an empty static string stands
  in for a null pointer), `GetLength`, `Find`, `SubString`, `Format` and comparison helpers used
  above are listed in `names.tsv`.

## Open questions

- Why some resource types reserve 6 bytes in front of the data (`CRes`+0x20, set by the
  constructors of MDL, MDX, VIS, TXI, DDS and 4PC) and others 10 bytes after it (+0x24: PLT, TGA,
  TPC), and what sets status bit 0x8 (read by `ReleaseResObject` `0x00409cf0`; no setter found)
  (low).
