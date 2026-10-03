# Resources in swkotor.exe: resource manager, type registry, GFF, 2DA, TLK

How the original engine finds, loads and parses resource files. Addresses are for the Steam
`swkotor.exe` after SteamStub removal (image base `0x400000`). Names are ours, in the Aurora/NWN
vocabulary (`CExoResMan`, `CExoKeyTable`, `CRes`, `CResGFF`, `C2DA`, `CTlkTable`); until the
proposals in `kotor/re/proposals/res.tsv` are merged Ghidra shows most of them as `FUN_...`.
Confidence: **high** = read in the code and consistent with every caller; **med** = behaviour clear,
name or a detail inferred; **low** = a guess.

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
| `CExoKeyTable` | 0x34 bytes, `0x0040d030` | one mounted source (a KEY file and its BIFs, a directory, an ERF-family file, or a RIM): a hash table of 0x1c-byte key entries plus the file object(s) that hold the bytes | high |
| `CRes` | 0x28 bytes and up, vtable `0x0073d86c`, `0x00406460` | one resource's in-memory state: demand/request counts, resource id, data pointer, size. Every typed resource (`CResGFF`, `CRes2DA`, `CResTPC`...) derives from it | high |
| `CExoResFile` / `CExoEncapsulatedFile` / `CExoResourceImageFile` | vtables `0x0073e1b0` / `0x0073e1f8` / `0x0073e240`, common base vtable `0x0073e128` | reader for one BIF / one ERF-MOD-SAV / one RIM | high |
| CRC-32 table | `0x007a3d78` (256 dwords) | polynomial 0xEDB88320, used by the key hash; rebuilt by every `CExoKeyTable` constructor | high |

`CExoResMan` layout (all high unless marked):

| Offset | Field |
|---|---|
| +0x00 | total physical memory (GlobalMemoryStatus) |
| +0x04 | memory budget: half of physical memory, at least 16 MB |
| +0x08 | bytes still available in the budget (resident resource data is charged to it) |
| +0x10 | list of KEY tables (kind 1) |
| +0x14 | list of directory tables (kind 2) |
| +0x18 | list of ERF tables (kind 3) |
| +0x1c | list of RIM tables (kind 4) |
| +0x20 | released resources: undemanded `CRes` that still hold data, freed when memory is needed |
| +0x24 | async request queue (FIFO, appended at the tail) |
| +0x28 / +0x2c | `CRes` being read asynchronously / its open file |
| +0x30 | async servicing paused when non-zero (med) |
| +0x34 | flags byte; per [resman.md](resman.md) the main-menu and chargen RIMs are tracked here (med) |
| +0x38 / +0x3c | loader thread handle / id |
| +0x40 | critical section around the loader |
| +0x44 | loader state: 1 busy, 2 or 3 finished, 4 failed |
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
   live `CRes` objects onto the new entries) and returns;
2. finds a free table id 1..63 among the tables of that list and tags it with the kind
   (0 KEY, 0x80000000 directory, 0x40000000 ERF, 0x20000000 RIM);
3. creates a `CExoKeyTable`, pushes it at the head of the list, calls
   `CExoKeyTable::Initialize(kind, name, id)` (`0x00410190`), stores `group` at table+8; on failure
   unlinks and deletes it.

The matching removals are `RemoveKeyTable(name, kind)` `0x00407830` and its wrappers
(`RemoveKeyTableFile` `0x004088c0`, `RemoveResourceDirectory` `0x004088d0`,
`RemoveEncapsulatedResourceFile` `0x00408820`, `RemoveResourceImageFile` `0x00408830`).
`UpdateKeyTable(name, kind)` `0x00407fe0` (wrapper `UpdateResourceDirectory` `0x004088e0`) re-reads
a mounted source in place. Who mounts what, and in which order, is in [resman.md](resman.md) and
[modules.md](modules.md).

`Initialize` dispatches by kind (all high):

| Kind | Loader | What it builds |
|---|---|---|
| 1 KEY | `AddKeyTableContents` `0x0040fb80` | opens `<name>.key` (type 9999), checks `"KEY V1  "`; one `CExoResFile` per BIF entry, named `<alias>:<path without extension>` from the key's own alias (`HD0:`), falling back to `CD0:` when the BIF is not on disk and its drive flags are not 1 (`LocateBifFile` `0x0040d200`); each BIF's header is loaded at once. Then the 22-byte keys (resref 16, type 2, id 4); the id's top two bits are cleared. Hash table size `1023 + 1.18 * keys` |
| 2 directory | `AddDirectoryContents` `0x0040f200` | lists the directory (no subfolders); each file whose extension is a known type becomes a key (`GetResRefFromFile` `0x004065a0`: name up to the first `.`, cut to 16; `GetResTypeFromFile` `0x00406650`: the 3 characters after it). Table size `2n + 1` |
| 3 ERF | `AddEncapsulatedContents` `0x0040f3c0` | tries `<name>` as `.nwm`, `.mod`, `.sav`, `.erf`, `.hak` (first that opens); reads the 0xA0 header; the signature must be `"ERF "` for `.erf`, `"HAK "` for `.hak`, `"MOD "` otherwise, version `"V1.0"`; adds the 24-byte keys (resref 16, id 4, type 2, unused 2); one `CExoEncapsulatedFile` serves all reads. Table size `1.2n` |
| 4 RIM | `AddResourceImageContents` `0x0040f990` | one `CExoResourceImageFile` which reads the **whole file into memory** (type 3009 tried before `.rim`); keys come from the 32-byte entries (resref 16, type 4, id 4, offset 4, size 4) found at the offset in header+0x10, count at header+0xc. Table size `1.2n` |

### Key entries and resource ids

A key entry is 0x1c bytes: resref (16, lower-cased), `CRes*` (+0x10, null until something asks
for the resource), resource id (+0x14), type (u16 at +0x1a). Empty slots have type 0xFFFF and an
empty resref. `CExoKeyTable::Hash` (`0x0040d500`) runs a CRC-32 over the lower-cased resref bytes
with the type added to each byte, modulo the table size; `FindKey` (`0x0040ec50`) probes linearly
from there and gives up at the first empty slot or after a full wrap; `AddKey` (`0x0040e990`)
inserts the same way, ignoring a duplicate (resref, type) within one table (the log message is
built but not printed).

The 32-bit resource id encodes where the bytes are (high):

| Bits | Meaning |
|---|---|
| 31..30 | container kind of the owning table: 0 KEY, 1 RIM, 2 ERF, 3 directory |
| 29..20 | KEY: index of the BIF in the key file (as stored in chitin.key); other kinds: a copy of the table id |
| 19..14 | table id (1..63), used by `GetTable` (`0x004076e0`) to find the owning `CExoKeyTable` |
| 13..0 | index of the resource inside its BIF / ERF / RIM |

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
tables of the other group. An ERF mounted with group 0 is never found by name. Built on this:
`Exists(resref, type, &kind)` (`0x00408bc0`, also reports the kind 1..4 of the container that
has it), `ExistsInTableKind(resref, type, kind)` (`0x00408c00`, one kind only),
`GetResObject(resref, type)` (`0x004074d0`, the `CRes` already attached to the entry, if any) and
`SetResObject(resref, type, res)` (`0x00407680`, attaches a new `CRes` to the entry and gives it
the entry's id). The listing helpers `ListResourcesOfType` (`0x00407390`) and
`ListTableResourcesOfType` (`0x00408c60`, the table that holds a given `CRes`, e.g. "every `.git`
in this module") return resref lists.

### CRes and the demand / release protocol

`CRes` layout (high unless marked):

| Offset | Field |
|---|---|
| +0x00 | vtable: 0 destructor, 1 `GetFixedResourceSize` (-1), 2 `GetFixedResourceDataOffset`, 3 `OnResourceFreed`, 4 `OnResourceServiced` |
| +0x04 | u16 demand count |
| +0x06 | u16 async request count |
| +0x08 | resource id (-1 = not attached) |
| +0x0c | status bits: 0x4 serviced (data valid), 0x10 async read in flight, 0x100 on the released list / free on last release, 0x200 its table went away while it was demanded |
| +0x10 | data pointer |
| +0x14 | key entry pointer |
| +0x18 | size in bytes |
| +0x1c | number of resource helpers sharing this object (set to 1 by `SetResObject`, +1 by every `GetResObject`) |
| +0x20 / +0x24 | allocation variants: reserve 6 bytes in front of the data / 10 bytes after it (med) |
| +0x28.. | the subclass's parsed view (section pointers, loaded flag ...) |

The protocol (all high):

- **Demand** (`CRes::Demand` `0x00409b10` → `CExoResMan::Demand` `0x004089f0`): if serviced, take
  it off the released list if it is there, count the demand, return the data. Otherwise read it
  now by container kind: `ServiceFromResFile` `0x00407e00` (KEY/BIF; BIF = id bits 29..20, entry =
  bits 13..0), `ServiceFromImage` `0x00407d50` (RIM: the data pointer points **into the resident
  image**, nothing is copied), `ServiceFromEncapsulated` `0x00407bd0` (ERF), `ServiceFromDirectory`
  `0x004078f0` (`<dir>\<resref>.<ext>`, read whole). Each one sizes the resource, allocates through
  `Malloc` `0x004077b0` (which first frees released resources until the budget allows), reads, and
  calls the `OnResourceServiced` slot, whose result decides whether the resource counts as
  serviced. A resource with an async read in flight is finished first (`FinishAsyncRequest`
  `0x00408530`, spinning with `Sleep(5)` until the read completes). Returns the data or null.
- **Release** (`CRes::Release` `0x00409b80` → `CExoResMan::Release` `0x00408c90`): one demand
  less. At zero the resource is not freed: it goes to the head of the released list (+0x20) and
  keeps its data. `FreeChunk` (`0x004070a0`) and `Malloc` free released resources from that list's
  head when memory is short, calling `OnResourceFreed` and `FreeResourceData` (`0x00406540`, which
  never frees RIM image memory).
- **Request** (`CRes::Request` `0x00408620`): the asynchronous variant. The first request appends
  the resource to the queue at +0x24; `CExoResMan::Update` (`0x00408d40`) starts or completes the
  head request one step per call (async reads go through `ReadResourceAsync`); `CancelRequest`
  (`0x004088f0`) undoes a request.
- **Dump** (`0x00408b90`; `CRes::Dump` `0x00409b40`): free now if nobody demands it, else free on
  the last release. `Free` (`0x00407020`) is the forced variant.
- **ReadRaw** (`0x00408e30` → per-kind `0x00408080`/`0x004082d0`/`0x00408390`/`0x00408450`):
  copy a resource's bytes into a caller's buffer without keeping them (med).

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
slot 17. The reference counts open the file on first use and close it on last use, so a BIF or
ERF is only held open while one of its resources is being read.

| Class | Header read | Per-resource lookup | Conf. |
|---|---|---|---|
| `CExoResFile` (BIF) | `LoadHeader` `0x0040d910`: 0x14 bytes, `"BIFFV1  "`, then `count` 16-byte variable entries (id, offset, size, type) | entry = id bits 13..0; `ReadResource` `0x0040da20` seeks and reads min(size, entry size) | high |
| `CExoEncapsulatedFile` (ERF/MOD/SAV/HAK/NWM) | `LoadHeader(kind)` `0x0040e1f0`: the 0xA0 header, the localized-string list, the 8-byte resource list (offset, size) | `ReadResource` `0x0040e640` | high |
| `CExoResourceImageFile` (RIM) | `OpenFile` `0x0040e790` reads the whole file; there is no separate header step | `GetResourcePointer` `0x0040f160` returns an address inside the image; `ReadResource` `0x0040f1a0` copies from it | high |

### Module loader thread

`CExoResMan` owns one worker thread (`LoaderThreadProc` `0x00409b90`, created suspended by the
constructor). `StartModuleLoad(name, bModule, bFromSave)` (`0x004064f0`) stores the request and
resumes it; the thread runs `LoadModuleResources` (`0x004094a0`) under the critical section, sets
the state byte and suspends itself again. The caller (`CSWSModule::AddModuleResources`) polls the
state while animating the load screen. What it mounts is in
[modules.md](modules.md#mounting-a-modules-files). (high)

### File-system helpers

`CreateDirectory` `0x004068c0`, `RemoveFile(name, type)` `0x00406b20`, `CopyFile` `0x00406990`,
`GetFreeDiskSpace` `0x004067b0`, `CleanDirectory` `0x00409460` and `RemoveDirectory` `0x00409480`
(both on `0x00408e90`, which deletes files of known types, optionally everything, optionally
recursing and removing the folder). All take alias paths (`CURRENTGAME:`, `GAMEINPROGRESS:`,
`SAVES:`...) that `CExoBase` resolves through the `[Alias]` section of `swkotor.ini` and built-in
defaults (`0x005e6680`, see [app.md](app.md)). (med)

## 2. The type registry and the CRes classes

`CExoBase` (`g_pExoBase` `0x007a39e0`) holds at +0x14 a small type table object (0xC bytes:
count, array of u16 ids, array of `CExoString` extensions), built by `0x005e8ba0` /
`0x005e6d20` (high). It has 88 entries; unknown lookups return the last one (id 0xFFFF, extension
`""`). `CExoBase::GetResourceExtension(type)` `0x005e6660` → `0x005e7a00` (linear search by id) and
`CExoBase::GetResTypeFromExtension(ext)` `0x005e6670` → `0x005e7a40` (case-insensitive linear
search) are the only two queries. The table, in registration order:

```
0 res      1 bmp      2 mve      3 tga      4 wav      7 ini     10 txt   2022 txi
9999 key 9998 bif   9997 erf   2000 plh   2001 tex   2002 mdl   2007 lua   2003 thg
2008 slt 2009 nss   2010 ncs   2011 mod   2012 are   2013 set   2014 ifo   2015 bic
2016 wok    6 plt   2005 fnt   2017 2da   2018 tlk      8 mp3      9 mpg   2024 bti
2025 uti 2026 btc   2027 utc   2031 btt   2032 utt   2023 git   2029 dlg   2030 itp
2033 dds 2034 bts   2035 uts   2036 ltr   2037 gff   2038 fac   2039 bte   2040 ute
2041 btd 2042 utd   2043 btp   2044 utp   2045 dft   2046 gic   2047 gui   2048 css
2049 ccs 2050 btm   2051 utm   2052 dwk   2053 pwk   2054 btg   2055 utg   2056 jrl
2057 sav 2058 utw   2059 4pc   2060 ssf   2061 hak   3000 lyt   3001 vis   3002 rim
  11 wma 3003 pth     12 wmv   3004 lip   2062 nwm   2063 bik   3006 txb   3007 tpc
3008 mdx 3009 rsv   3010 sig     13 xmv   3011 xbx     14 log  65535 ""
```

Type 3009 (`rsv`) is used for RIM-like module files: the RIM reader tries it before `.rim`, and
the module code looks for it in `CURRENTGAME:` and `GAMEINPROGRESS:` (med; no such file in the
PC install). The `CRes` subclasses and the types they serve are in the helper table above; the
GFF-based ones are `CResGFF` (generic, vtable `0x0073e2d0`), `CResIFO` and `CResARE` (subclasses
that only preset the 4-character file type).

## 3. GFF (`CResGFF`)

`CResGFF` (0xA0 bytes, vtable `0x0073e2d0`) is both the reader and the writer.

| Offset | Field |
|---|---|
| +0x28..+0x3c | growth steps for the six arrays when writing (110 structs, 646 fields, 98 labels, 1836 data bytes, 4052 field-index bytes, 4052 list-index bytes) |
| +0x40 | header (0x38 bytes: type, version, then offset/count pairs for structs, fields, labels, field data, field indices, list indices) |
| +0x44 / +0x48 | struct array (12-byte entries: id, data-or-offset, field count) / capacity |
| +0x4c / +0x50 | field array (12-byte entries: type, label index, data-or-offset) / capacity |
| +0x54 / +0x58 | label array (16-byte names) / capacity |
| +0x5c / +0x60 | field data block / capacity |
| +0x64 / +0x68 / +0x6c | field-index block / capacity / bytes wasted by moves |
| +0x70 / +0x74 / +0x78 | list-index block / capacity / bytes wasted |
| +0x8d | expected 4-character file type (`"UTC "`, `"ARE "`, `"IFO "`...) |
| +0x94 | loaded flag |
| +0x98 | the arrays point into the resource's bytes (read-only) rather than owned heap blocks |
| +0x9c | the resource is demanded |

Loading (high): `CResGFF(type, fileType, resref)` (`0x00410630`) attaches a `CResGFF` to the key
entry and demands it. `OnResourceServiced` (`0x00410740`) accepts the data only if the first four
bytes equal the expected file type and the next four equal `"V3.2"` (`g_pszGFFVersion`
`0x0078d3cc`); it then points the six arrays straight into the loaded bytes (no copy, no
validation beyond that). Callers check `+0x94` / the demand result. `ReleaseResource`
(`0x004108c0`) gives the resource back.

Handles: a `CResStruct` is a struct index (`GetTopLevelStruct` `0x00411240` sets it to 0). A
`CResList` is the owning struct index followed by the 16-byte label; every list access looks the
field up again by label.

Field access (high): `GetFieldByLabel(struct, label)` (`0x00411630`) compares the 16-byte label of
each of the struct's fields in order (no hashing); `GetField(struct, n)` (`0x00410990`) takes the
struct's data as the field index itself when it has one field, else as a byte offset into the
field-index block. Simple values (types 0-5, 8) live in the field entry's data word; others are at
`field data + data word` (`GetFieldData` `0x00410a20`), lists at `list indices + data word`
(`GetListData` `0x00410a60`).

The readers all have the shape `Read<Type>(struct, label, &bSuccess, default)`: they return the
default and clear `bSuccess` when the label is missing, the type differs, or the data would run
past its block. Types follow the Aurora numbering:

| Type | Reader | Writer | Storage |
|---|---|---|---|
| 0 BYTE | `0x00411a60` | `0x00412620` | data word |
| 1 CHAR | `0x00411ad0` | `0x00412670` | data word |
| 2 WORD | `0x00411b40` | `0x004126c0` | data word |
| 3 SHORT | `0x00411bb0` | `0x00412710` | data word |
| 4 DWORD | `0x00411c20` | `0x00412760` | data word |
| 5 INT | `0x00411c90` | `0x004127b0` | data word |
| 6 DWORD64 | `0x00411d70` | `0x00412800` | 8 bytes in field data |
| 7 INT64, 9 DOUBLE | none in this build | none | — |
| 8 FLOAT | `0x00411d00` | `0x00412870` | data word |
| 10 CExoString | `0x00411ec0` | `0x00412970` | u32 length + chars |
| 11 CResRef | `0x00411e10` | `0x004128c0` (lower-cases) | u8 length + chars |
| 12 CExoLocString | `0x00411fd0` | `0x00412a10` | u32 total size, u32 strref, u32 count, then per string u32 id (language*2 + gender), u32 length, chars; the reader rejects it unless the sizes add up exactly |
| 13 VOID | `0x00412380` | `0x00412c10` | u32 length + bytes |
| 14 Struct | `GetStructFromStruct` `0x00411a10` | `AddStruct` `0x004125b0` | struct index in the data word |
| 15 List | `GetList` `0x004118c0`, `GetListCount` `0x00411940`, `GetListElement` `0x00411990` | `AddList` `0x00412450`, `AddListElement` `0x004124e0` | u32 count + struct indices in the list-index block |
| 16 Orientation | `0x004121b0` | `0x00412ca0` | four floats |
| 17 Vector | `0x004122a0` | `0x00412d30` | three floats |

Writing (high): `CreateGFFFile(&topStruct, fileType, version)` (`0x00411260`) on an empty
`CResGFF` (`0x004105a0`) writes the header type/version and a top struct with id -1. The first
write to a loaded GFF copies its sections into owned heap arrays (`InitializeForWriting`
`0x00410aa0`). `AddField` (`0x00411730`) appends a field and, when a struct gains its second
field, moves it to the field-index block; arrays grow by the steps above, doubled each time.
`WriteGFFFile(name, type)` (`0x00413030`) opens the alias path for writing, `Pack`s
(`0x00412db0`: drops the dead space that moved index lists leave behind, when it exceeds a
threshold) and `WriteGFFData` (`0x004113d0`) writes the 0x38-byte header followed by structs,
fields, labels, field data, field indices and list indices, in that order. Saves put GFFs straight
into an ERF with `CERFFile::AddResource` (below).

## 4. 2DA (`C2DA`) and the 2DA cache

`C2DA` (0x54 bytes, vtable `0x0073e2f8`) is a resource helper over `CRes2DA` plus the parsed table.

| Offset | Field |
|---|---|
| +0x00..+0x1b | `CResHelper<CRes2DA,2017>` (vtable, requested flag, `CRes2DA*`, resref) |
| +0x1c | default value (`CExoString`), returned when a lookup fails |
| +0x24 / +0x28 | row count / column count |
| +0x2c | loaded |
| +0x30 / +0x34 / +0x38 | text format: row labels, column labels, rows (each an array of `CExoString`) |
| +0x3c | binary format flag (copied from `CRes2DA`+0x38) |
| +0x40 / +0x44 | binary: cell string base / u16 cell offsets (row-major) |
| +0x48 / +0x4c / +0x50 | binary: label string base / row-label offsets / column-label offsets |

`CRes2DA::OnResourceServiced` (`0x0041d790`, high) accepts `"2DA V2.b"` (sets the binary flag) and
`"2DA V2.0"`; its data pointer and size (`0x00404dd0`, `0x00710e50`, folded getters) skip the
8-byte header.

`C2DA::C2DA(resref, bRequest)` (`0x00413cc0`) only binds the helper; nothing is parsed until
`Load2DArray` (`0x004143b0`, high), which demands the resource, then:

- reads the first line: `DEFAULT: <value>` (or `DEFAULT` followed by `:<value>`) sets the default
  value; then counts the column labels on the next line;
- **binary**: works in place in the resource bytes (which stay demanded): the tab-separated column
  labels are NUL-terminated where they stand and their offsets recorded, then the u32 row count,
  the tab-separated row labels, the rows x columns u16 cell offsets, a u16 data size, and the cell
  strings;
- **text**: builds `CExoString` arrays: lower-cased column and row labels, one string per cell
  (missing trailing cells take the default value, `****` becomes `""`), then releases the resource.

Lookups (all high; the four overload families take row as index or label and column as index or
label; labels compare case-insensitively with a linear scan, `GetColumnIndex` `0x00413100`,
`GetRowIndex` `0x004138b0`):

| Value | (row index, column label) | (row index, column index) | (row label, column label) | (row label, column index) |
|---|---|---|---|---|
| `CExoString` | `0x00413270` | `0x00413190` | `0x00413de0` | `0x00413ec0` |
| float (`sscanf "%f"` / atof) | `0x00413430` | `0x00413350` | `0x00413fa0` | `0x00414080` |
| int (`sscanf "%i"`; text also `0x` hex) | `0x00413660` | `0x00413510` | `0x00414110` | `0x00414260` |

Every getter returns false and the default value (as string, float or int) when the row or column
is out of range or the cell is empty. The text format stores every cell as text; binary cells are
parsed on every call.

### The global cache (`C2DAs`)

`CSWRules` (`g_pRules` `0x007a3a28`, built by `0x00552c50`) keeps at +0xb8 a 0x12c-byte `C2DAs`
object (`0x005bfb60`). `C2DAs::Load2DArrays` (`0x005c4c20`, high) loads, in this order and failing
on the first table that does not load: the IPRP cost and param table lists (`0x005c4730`,
`0x005c49c0`, one `C2DA` per row of `iprp_costtable.2da` / `iprp_paramtable.2da`), then the tables
below. The process role byte `0x007a39dc` filters two groups: tables marked *client* are skipped
when it is 2 (server only), tables marked *game* are skipped when it is 1 (client only); the
single-player game loads all of them.

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

Some loaders also cache column indices in globals right after loading (e.g. creaturespeed's
`RUNRATE`/`WALKRATE` at `0x007a2244`/`0x007a2248`). Classes, races, skills, feats, spells, base
items and the XP table are loaded by `CSWRules` itself (`0x0054f2c0`, `0x0054fec0`, `0x00550590`,
`0x005515e0`, `0x005b31d0`...; see [objects.md](objects.md)). Many other 2DAs are opened ad hoc
with a temporary `C2DA` (119 call sites of the constructor), e.g. `stringtokens.2da` by the TLK
code and `texpacks.2da` at start-up.

## 5. TLK (`CTlkTable`) and `CExoLocString`

`CTlkTable` (0x58 bytes; the client builds a 100-byte subclass with vtable `0x0074e700`), global
`g_pTlkTable` `0x007a3a08`, created by both the client and server initialisation with
`SetTlkFile("HD0:dialog")` (`0x0041e5a0`). Layout (high unless marked):

| Offset | Field |
|---|---|
| +0x00 | vtable `0x0073ecdc`; slot 0 resolves a named token (empty in the base; the client override `0x00674b90` supplies player name, class etc.) (med) |
| +0x04..+0x3b | seven slots of (male file, female file) `CTlkFile*` pairs |
| +0x3c | gender of the current fetch (0 male/neutral, 1 female) |
| +0x40 / +0x44 | named tokens from `stringtokens.2da`: 0x24-byte entries (CRC-32 of the name by `ComputeCRC32` `0x00410560`, the name, then the table's integer columns), sorted by CRC / count |
| +0x48 / +0x4c | custom tokens: 0xC-byte entries (number, `CExoString`), sorted / count |
| +0x54 | debug flag: prefix every fetched string with `[strref]` |

`OpenFile(path, slot)` (`0x0041d920`) opens `<path>.tlk` and `<path>F.tlk` (the female table)
through `CTlkFile` (`0x0041d810`, a `CExoFile` of type 2018 with a copy of the 20-byte header,
checked for `"TLK "` by `0x0041d890`); without a female file the female slot points at the male
one.

`FetchInternal(strref, result, bParse)` (`0x0041e1a0`, high) does **no caching**: every call seeks
and reads. It masks the strref to 24 bits, tries the seven slots in order with the current gender,
and in each skips files whose string count is not above the strref. The entry is read at
`20 + strref * size`, where size is 40 for version `"V3.0"` (`g_pszTLKVersion` `0x0078d3ec`) and 36
otherwise: flags, sound resref (16), volume and pitch variance, text offset, text length, sound
length (V3.0). Flags 0x1 = text present (read from `strings offset + text offset`), 0x2 = sound
resref valid, 0x4 = sound length valid; an entry with flag 0x8000 set counts as missing (med).
With the female gender and no hit it retries male.
`bParse` runs `ParseStr`. The result block is a `CExoString` text, a `CResRef` sound and a float
length.

- `Fetch(strref, result, gender)` `0x0041e550` — sets the gender, no token parsing;
- `GetSimpleString(strref)` `0x0041e8f0` — text only, male/neutral; 42 callers;
- `ParseStr(text)` `0x0041dd30` — replaces `<CUSTOMn>` with custom tokens (`SetCustomToken`
  `0x0041db50`, `ClearCustomTokens` `0x0041dcf0`, also restored from the module IFO's
  `Mod_Tokens`) and other `<name>` tokens (binary search by CRC-32, then an exact compare) through
  vtable slot 0; `<<` is a literal `<`; unknown tokens become `<UNRECOGNIZED TOKEN>`;
- `GetLanguageID` `0x0041e0f0` — language field of the slot-0 header (med).

`CExoLocString` (8 bytes: pointer to an internal list of (id, `CExoString`), strref at +4,
`0x005e9e10`) is the localized string of GFF type 12. Ids are `language * 2 + gender`, and the
gender bit is dropped for language 0 (English). `GetString(language, out, gender)` (`0x005ea130`,
high) returns the embedded string for that id if there is one, else fetches the strref from
`g_pTlkTable` with that gender and caches the text into the internal list.
`GetStringNoCache` (`0x005ea050`) does the same without caching; `GetEmbeddedString`
(`0x005ea240`) never touches the TLK; `AddString` (`0x005ea340`) adds or replaces; the
enumeration helpers are `GetStringCount` `0x005e9ef0`, `GetStringByIndex` `0x005e9eb0`,
`GetStringLength` `0x005e9f00`.

## 6. Helpers: CResRef, CExoFile, CExoString

- **`CResRef`** (16 bytes, NUL-padded, not necessarily NUL-terminated): every constructor and
  assignment lower-cases (`0x00406d80` from C string, `0x00406d60` from `CExoString`, `0x00406da0` /
  `0x00406170` from a raw 16-byte archive field, `0x00406120` copy). Comparisons: `0x004060b0`
  (16-byte equality), `0x004060d0` (case-insensitive against a C string), `0x00406dc0` (not equal).
  Conversions: `GetResRefStr` `0x00405f70` (to `CExoString`), `CopyToString` `0x00405fb0` (char[17]),
  `GetResRefCStr` `0x00405fe0` (one of four rotating static buffers). (high)
- **`CExoFile`** (`0x005e68d0`): opens `alias:path` with the extension of a resource type and a
  `fopen` mode; `Read` `0x005e6960`, `Write` `0x005e69a0`, `Seek` `0x005e6aa0`, `GetSize`
  `0x005e6950`, `IsOpened` `0x005e6a10`, async read `0x005e6980` / `0x005e6990`. (high)
- **`CERFFile`** (`0x005dd9c0`, med): the ERF writer used for save games (`SAVEGAME.sav`, signature
  set with `SetFileType("MOD V1.0")` `0x005dce30`): `Create` `0x005dcfc0`, `SetNumEntries`
  `0x005dda50`, `AddFile` `0x005ddbc0`, `AddResource` `0x005ddf30` (GFFs are written straight into
  the archive), `AddDirectory` `0x005de1a0` (the whole `GAMEINPROGRESS:` folder), `WriteHeader`
  `0x005dd080`, `Finish` `0x005dd0e0`; and for loading a save, `ReadHeader` `0x005dce50`,
  `ReadLists` `0x005dd3c0` and `ExtractAll` `0x005dd710` (every entry to a folder).
- **`CExoString`** (pointer + buffer length): the constructors, `CStr` (`0x005e5670`, never null),
  `GetLength`, `Find`, `SubString`, `Format` and comparison helpers used above are listed in
  `res.tsv`.

## Open questions

- The meaning of the 6-byte prefix / 10-byte tail allocation flags in `CRes` (+0x20/+0x24) and of
  status bit 0x8 (low).
- `FreeChunk` frees from the head of the released list, i.e. the most recently released resource
  first; whether that is intended LRU-in-reverse or the list is maintained elsewhere was not
  checked against a running game (med).
- How `C2DA::Load2DArray` counts the columns of a binary 2DA from the "first line" (the label
  block has no line break) was not traced byte by byte; the binary layout itself is confirmed by
  the offsets it records (med).
- No caller was found for INT64/DOUBLE GFF fields; the readers and writers are absent from the
  binary (high that they are absent, low on whether any KOTOR file uses those types).
