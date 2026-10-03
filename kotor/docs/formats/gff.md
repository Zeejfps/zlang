# GFF: BioWare's Generic File Format, V3.2

GFF is KOTOR's general container for structured data: a tree of **structs** whose members are
labelled, typed **fields**, where a field can hold a scalar, a string, a struct or a **list** of
structs. Blueprints, areas, module info, dialogues, GUIs, palettes, faction tables, path graphs and
every save-game record are GFFs. Readers look fields up by label, so a file can gain or lose fields
without breaking older readers. The meaning of each file type's fields (its schema) is documented
separately: [gff-templates.md](gff-templates.md) (blueprints), [gff-module.md](gff-module.md) (IFO,
ARE, GIT, PTH), [gff-dialog.md](gff-dialog.md) (DLG, JRL), [gff-gui.md](gff-gui.md) (GUI) and
[pth.md](pth.md). This document covers the container: the bytes, the rules, and how to write a file
the way the game does.

Everything below was measured on the Steam install (11152 GFF files, every copy of every resource,
including one save) unless marked otherwise. Tools: `kotor/tools/py/gff.py` (reader and writer),
`kotor/tools/py/gff_probe.py` (corpus check), see [Checked](#checked).

## Where the game keeps GFFs

A resource is a GFF when bytes 4..8 are `V3.2`; bytes 0..4 are the **file type** tag (three
letters and a space by convention). In this install every resource whose extension is a GFF type
is a GFF, and no resource with any other extension is, except `.res` (type 0), which saves use for
four GFF kinds. No other GFF version (V3.3, V4.0) occurs. Type ids are in
[resource-types.md](resource-types.md); containers in [key-bif.md](key-bif.md), [rim.md](rim.md) and
[erf.md](erf.md); the lookup order in [resources.md](resources.md).

| Tag | Ext (type id) | Content | Copies | Where (container: copies) |
|---|---|---|---|---|
| `UTW ` | utw (2058) | waypoint blueprint | 2058 | `modules/*_s.rim` 2049, `templates.bif` 9 |
| `UTC ` | utc (2027) | creature blueprint | 1959 | `_s.rim` 1753, `templates.bif` 205, save 1 |
| `UTP ` | utp (2044) | placeable blueprint | 1784 | `_s.rim` 1467, `templates.bif` 317 |
| `DLG ` | dlg (2029) | conversation | 1167 | `_s.rim` 1135, `templates.bif` 32 |
| `UTT ` | utt (2032) | trigger blueprint | 1121 | `_s.rim` 1100, `templates.bif` 21 |
| `UTI ` | uti (2025) | item blueprint | 1055 | `templates.bif` 557, `_s.rim` 436, `rims/global.rim` 31, `rims/miniglobal.rim` 31 |
| `UTS ` | uts (2035) | sound blueprint | 635 | `_s.rim` 635 |
| `UTD ` | utd (2042) | door blueprint | 575 | `_s.rim` 525, `templates.bif` 50 |
| `UTE ` | ute (2040) | encounter blueprint | 133 | `_s.rim` 68, `templates.bif` 65 |
| `PTH ` | pth (3003) | area path graph | 132 | `_s.rim` 132 |
| `ARE ` | are (2012) | area static properties | 118 | `modules/*.rim` 117, save 1 |
| `GIT ` | git (2023) | area instances / dynamic state | 118 | `modules/*.rim` 117, save 1 |
| `IFO ` | ifo (2014) | module info (`module.ifo`) | 118 | `modules/*.rim` 117, save 1 |
| `GUI ` | gui (2047) | GUI layout | 91 | `gui.bif` 84, `patch.erf` 7 |
| `UTM ` | utm (2051) | store blueprint | 38 | `_s.rim` 38 |
| `FAC ` | fac (2038) | faction table (`repute.fac`) | 21 | `_s.rim` 20, save 1 |
| `ITP ` | itp (2030) | toolset palette | 16 | `templates.bif` 16 |
| `JRL ` | jrl (2056) | journal | 4 | `_s.rim` 3, `_newbif.bif` 1 |
| `BTC ` | btc (2026) | creature blueprint (old form) | 3 | `templates.bif` 3 |
| `BIC ` | bic (2015) | player character | 1 | `templates.bif` 1 (`temp_char`) |
| `BTI ` | bti (2024) | item blueprint (old form) | 1 | `templates.bif` 1 |
| `GVT ` | res (0) | global variables | 1 | save: `GLOBALVARS.res` (loose) |
| `PT  ` | res (0) | party table | 1 | save: `PARTYTABLE.res` (loose) |
| `NFO ` | res (0) | save summary for the load screen | 1 | save: `savenfo.res` (loose) |
| `INV ` | res (0) | party inventory | 1 | save: `inventory.res` in `SAVEGAME.sav` |

The save (`Saves/000002 - Game1/`) holds `GLOBALVARS.res`, `PARTYTABLE.res`, `savenfo.res` loose,
and `SAVEGAME.sav` (an ERF) holding `availnpc0.utc`, `inventory.res`, `repute.fac` and one nested
module save `end_m01aa.sav` (itself an ERF) with `m01aa.git`, `m01aa.are` and `module.ifo`. The
save's `m01aa.are` is byte-identical to the shipped one in `end_m01aa.rim` (copied, not
rewritten); the other eight are written by the engine.

## Binary layout

All integers are little-endian. The file is a 56-byte header followed by six sections. Every
reference between sections is an offset or index stored in the file, so a reader must follow them
and never assume positions. In every file in the install the sections are contiguous, in the order
below, with no padding and nothing after the last one; the struct array always starts at 56.

| Order | Section | Element | Header fields |
|---|---|---|---|
| 1 | struct array | 12-byte struct record | StructOffset, StructCount (records) |
| 2 | field array | 12-byte field record | FieldOffset, FieldCount (records) |
| 3 | label array | 16-byte label | LabelOffset, LabelCount (labels) |
| 4 | field data | bytes of complex values | FieldDataOffset, FieldDataCount (bytes) |
| 5 | field indices | uint32 field indices | FieldIndicesOffset, FieldIndicesCount (**bytes**) |
| 6 | list indices | uint32 counts and struct indices | ListIndicesOffset, ListIndicesCount (**bytes**) |

### Header (56 bytes)

| Offset | Size | Name | Meaning |
|---|---|---|---|
| 0 | 4 | FileType | Tag, e.g. `UTC ` (see the table above). |
| 4 | 4 | FileVersion | `V3.2`. Reject anything else. |
| 8 | 4 | StructOffset | Byte offset of the struct array (56 in every file). |
| 12 | 4 | StructCount | Number of struct records; at least 1 (record 0 is the top-level struct). |
| 16 | 4 | FieldOffset | Byte offset of the field array. |
| 20 | 4 | FieldCount | Number of field records. |
| 24 | 4 | LabelOffset | Byte offset of the label array. |
| 28 | 4 | LabelCount | Number of labels. |
| 32 | 4 | FieldDataOffset | Byte offset of the field data block. |
| 36 | 4 | FieldDataCount | Size of the field data block in bytes. |
| 40 | 4 | FieldIndicesOffset | Byte offset of the field-indices array. |
| 44 | 4 | FieldIndicesCount | Size of the field-indices array in bytes (4 per entry). |
| 48 | 4 | ListIndicesOffset | Byte offset of the list-indices array. |
| 52 | 4 | ListIndicesCount | Size of the list-indices array in bytes (4 per entry). |

### Struct record (12 bytes)

| Offset | Size | Name | Meaning |
|---|---|---|---|
| 0 | 4 | Type | The struct id (see [Struct ids](#struct-ids)). 0xFFFFFFFF for struct 0. |
| 4 | 4 | DataOrDataOffset | FieldCount 0: 0xFFFFFFFF. FieldCount 1: the **index** of its one field in the field array. FieldCount >= 2: a **byte offset** into the field-indices array, where FieldCount consecutive uint32 field indices list its fields in order. |
| 8 | 4 | FieldCount | Number of fields in the struct. |

Struct 0 is the top-level struct (the root of the tree); it has no label. Every other struct is
reached from exactly one Struct field or one List element (in every file in the install: no struct
or field is referenced twice, nothing is unreachable, and children always have higher struct
indices than their parent).

### Field record (12 bytes)

| Offset | Size | Name | Meaning |
|---|---|---|---|
| 0 | 4 | Type | Field type id, 0..17 (table below). |
| 4 | 4 | LabelIndex | Index into the label array. |
| 8 | 4 | DataOrDataOffset | Inline types: the value itself. Complex types: byte offset into the field data block. Struct: index into the struct array. List: byte offset into the list-indices array. |

### Label (16 bytes)

The label's characters, padded with NULs to 16 bytes; a 16-character label has no terminator
(10729 such labels occur, e.g. `PT_COST_MULT_LIS`, `CreatnScrptFird`). Read up to the first NUL.
In the install the padding is always NUL, the characters are letters, digits, `_` and space (GIT's
`Creature List`, `Door List`), 1 to 16 long.

### Field data block

The bytes of complex values (DWORD64, INT64, DOUBLE, CExoString, CResRef, CExoLocString, VOID,
Orientation, Vector), packed back to back with no alignment. Each value's layout is in
[Field types](#field-types).

### Field-indices array

uint32 field indices. A struct with two or more fields owns a block of FieldCount consecutive
entries, starting at its DataOrDataOffset (a byte offset, always a multiple of 4).

### List-indices array

A sequence of lists. A List field's DataOrDataOffset is a byte offset to its list: a uint32 element
count N, then N uint32 **struct indices** (not offsets), the list's elements in order. An empty list
still has its 4-byte count of 0.

BioWare's published GFF document has two slips here: it calls the list elements "offsets into the
Struct Array" (they are indices) and, in its section 4.9, says a list lives in the "Field Indices
Array" (it lives in the list-indices array).

## Field types

"Inline" values sit in the field record's 4-byte DataOrDataOffset; "data" values are in the field
data block at that offset. Counts are fields in the 11152 files.

| Id | Name | Stored | Bytes | Encoding | Fields | Files |
|---|---|---|---|---|---|---|
| 0 | BYTE | inline | 1 | uint8 in the low byte; the other three bytes 0 | 402744 | 10994 |
| 1 | CHAR | inline | 1 | int8, **sign-extended** to 32 bits (-1 is FF FF FF FF) | 357 | 3 |
| 2 | WORD | inline | 2 | uint16 in the low half; high half 0 | 45007 | 6825 |
| 3 | SHORT | inline | 2 | int16, **sign-extended** to 32 bits | 22892 | 4324 |
| 4 | DWORD | inline | 4 | uint32 | 282383 | 7019 |
| 5 | INT | inline | 4 | int32 | 110567 | 5925 |
| 6 | DWORD64 | data | 8 | uint64 | 114 | 3 |
| 7 | INT64 | data | 8 | int64 | 0 | 0 |
| 8 | FLOAT | inline | 4 | IEEE 754 single | 161056 | 5553 |
| 9 | DOUBLE | data | 8 | IEEE 754 double | 0 | 0 |
| 10 | CExoString | data | 4+n | uint32 length n, then n bytes; no terminator | 256710 | 11014 |
| 11 | CResRef | data | 1+n | uint8 length n (at most 16), then n bytes; no terminator | 360281 | 10983 |
| 12 | CExoLocString | data | 4+size | see below | 88162 | 10883 |
| 13 | VOID | data | 4+n | uint32 length n, then n raw bytes | 125 | 121 |
| 14 | Struct | struct array | | DataOrDataOffset = struct index | 10746 | 330 |
| 15 | List | list indices | | DataOrDataOffset = byte offset of the list | 130303 | 5974 |
| 16 | Orientation | data | 16 | four float32: a quaternion **w, x, y, z** | 1177 | 86 |
| 17 | Vector | data | 12 | three float32: x, y, z | 7869 | 367 |

Ids 16 and 17 are Odyssey additions to BioWare's Aurora list (0..15). Ids 7 and 9 are legal but
unused. No id above 17 occurs; a reader should treat one as a malformed file. CHAR and DWORD64
appear only in the engine-written save files (CHAR: saving-throw and attack modifiers in creature
state, effect `Modifier`s; DWORD64: effect `Id`s and `Mod_Effect_NxtId`). Orientation appears only
as GIT `CameraList/Orientation`; identity is stored as (1, 0, 0, 0), so w comes first. Vector
appears as colours (GUI `COLOR`, DLG `FadeColor`), positions (GIT camera `Position`, follow
locations in saves) and ARE `TunnelInfinite`.

Inline small types: BYTE and WORD always have zero upper bytes. Negative CHAR and SHORT values (all
in the save: 17 CHAR, 151 SHORT) are stored sign-extended; non-negative ones have zero upper
bytes. Read by taking the low 1 or 2 bytes and sign-extending; write the value as a sign-extended
int32.

FLOATs in the data include -0.0 (2180 fields) and no NaN or infinity; copy the 32 bits, don't
normalise.

### CExoString

Byte strings in Windows-1252 (the only non-ASCII bytes in the install are `±` 0xB1 in
`pazaaksetup.gui` and `·` 0xB7 in a placeable comment); line breaks are CR LF. No string contains a
NUL. 208217 are empty. BioWare's documents suggest a 1024-character maximum; 21 shipped strings
are longer, so don't enforce it.

### CResRef

A resource name: at most 16 characters, compared case-insensitively. Every ResRef in the install
is already lower-case and at most 16 long; 231170 are empty (length 0). Two are a single space
(`yav47_denied.dlg` `Sound`, `m17mg.are` `Music`), which should be treated as "no resource".

### CExoLocString

Localized text: a dialog.tlk string reference plus optional embedded strings.

| Offset | Size | Name | Meaning |
|---|---|---|---|
| 0 | 4 | TotalSize | Bytes that follow this field (8 + all substrings). |
| 4 | 4 | StrRef | int32 index into the talk table ([tlk.md](tlk.md)); -1 (0xFFFFFFFF) = none. |
| 8 | 4 | StringCount | Number of substrings that follow. |
| 12 | | substrings | StringCount times the substring below, back to back. |

Substring:

| Offset | Size | Name | Meaning |
|---|---|---|---|
| 0 | 4 | StringID | language id * 2 + gender (0 masculine/neutral, 1 feminine). |
| 4 | 4 | Length | n, byte count of the text. |
| 8 | n | Text | Windows-1252 bytes (for the English release), no terminator. |

Language ids per BioWare: English 0, French 1, German 2, Italian 3, Spanish 4, Polish 5, Korean 128,
Chinese Traditional 129, Chinese Simplified 130, Japanese 131 (KOTOR's own list and how
dialog.tlk declares its language: [tlk.md](tlk.md)). In this install: 50314 LocStrings have a valid
StrRef (all below dialog.tlk's 49265 entries), 37848 have -1; 87940 have no substring, 222 have
one, none has more; every substring id is 0 (English, masculine). 86 have both a StrRef and a
substring (41 of them in the save). TotalSize always matches the substrings.

BioWare's documented lookup, which a reader should follow: prefer the embedded substring for the
user's language and the wanted gender; otherwise fetch the StrRef from the talk table; otherwise
optionally fall back to embedded strings in other languages (English, French, German, Italian,
Spanish). Whether KOTOR's engine does exactly this is not yet confirmed from the executable.

### VOID

Opaque bytes whose meaning is the schema's: in the install `Mod_ID` (16 bytes in shipped IFOs, 32
in the save's), GLOBALVARS' packed `ValBoolean`/`ValNumber`/`ValLocation`, `PT_TUT_WND_SHOWN`, and
saved script state (`Code`, `AreaMapData`).

## Struct ids

The top-level struct's id is always 0xFFFFFFFF (all 11152 files). Other ids are chosen by whoever
wrote the struct; a reader identifies structs by where they sit, not by id, but a writer must
reproduce the ids the engine expects. Patterns found:

(Counted on lists of two or more elements, where the two patterns can be told apart.)

- **Element index**: the element's position in its list (0, 1, 2, ...): DLG `EntryList`,
  `ReplyList`, `StartingList`, `RepliesList`, `EntriesList`; FAC `FactionList`, `RepList`; JRL
  `EntryList`; UTM/UTP/UTC `ItemList`; item `PropertiesList` in the engine-written save files.
- **A constant per list**: PTH points 2, connections 3; UTC `ClassList` 2, `FeatList` 1,
  `SkillList` 0, `KnownList0` 3, `SpecAbilityList` 4; GIT `Creature List` 4, `Door List` 8,
  `Placeable List` 9, `WaypointList` 5, `TriggerList` 1, `SoundList` 6, `StoreList` 11,
  `Encounter List` 7, `CameraList` 14, trigger/encounter `Geometry` 3 (1 in 51 lists); IFO
  `Mod_Area_list` 6; 0 for ARE `Rooms`, DLG `AnimList`, UTS `Sounds`, UTE `CreatureList`, shipped
  UTI `PropertiesList`, GUI `CONTROLS`, and the save's `ItemList`s.
- **Equipment slot bits**: `Equip_ItemList` element ids are the slot's bit (0x2, 0x10, 0x4000,
  0x10000, 0x20000, ...).
- **Engine magic numbers in saves**: `CombatInfo` 0xCAAA, `CombatRoundData` 0xCADA, `EventQueue`
  elements 0xABCD, `EventData` 0x7777, `Mod_PlayerList` 0xBEAD, `AttackList` 0xAAEE,
  `DamageList` 0xDAEE/0xDDEE, `SpellsPerDayList` 0x4567.
- **Struct fields**: mostly 0; ARE `Map` is 14 (85 files) or 0 (33), GIT `AreaProperties` 14 (85)
  or 100 (33); the save GIT's `AreaMap` 101.

The schema documents give the id of each struct.

## Semantics and lookup rules

- **The tree.** Struct 0 is the root. A Struct field owns one child struct; a List field owns an
  ordered list of structs. Fields are looked up by label within one struct.
- **Field order within a struct** is the order of its field-indices block (or the single field).
  It doesn't matter for reading; it does for writing identical bytes (see below). In every file a
  struct's field indices are ascending.
- **Labels** are at most 16 bytes and case-sensitive: the engine-written save GIT, IFO and UTC
  each contain both `SubType` and `Subtype` as separate labels, and the corpus has 14 pairs that
  differ only in case (`Tag`/`TAG`, `RefBonus`/`refbonus`, ...). Match labels exactly.
- **The label array** holds each distinct label once (no file repeats one) and fields of any
  struct share it.
- **Duplicate labels in one struct do occur**, against BioWare's rule: 29 shipped DLG files have
  5464 node structs each carrying **six** `SoundExists` BYTE fields with the same value (it looks
  like a tool pass that appended the field each time it ran). A reader must not reject this; take
  the first match.
- **Zero-field structs** occur only in the save (19, all with DataOrDataOffset 0xFFFFFFFF): the
  `CombatRoundData` struct of creatures not in combat. Shipped files have none.
- **Empty lists** are common (they keep their 4-byte count).
- **Dead bytes.** 34 shipped files contain unreferenced entries in the field-indices array (3560
  bytes in all: 16 UTM, 11 GIT, 2 DLG, 1 BIC) or list-indices array (2068 bytes: 11 GIT, 4 ITP).
  They are old copies of blocks that were moved (see [Writing](#writing-files-the-way-the-game-does)).
  The game loads these files, so its reader follows offsets and ignores unreferenced bytes; ours
  must too. Field and struct records and field data never contain dead entries.

### Validating while reading

A reader that never trusts the data checks: the version; every section inside the file; struct 0
exists; field-indices and list-indices offsets are multiples of 4 and their blocks fit; every
field, label and struct index is in range; complex data (including each LocString substring and
the TotalSize) fits in the field data block; each struct is reached at most once (this also stops
cycles); field type ids are 0..17. `gff.read` does all of these and raises `GffError`.

## Writing files the way the game does

Any layout that satisfies the rules above can be read back by the engine (the shipped files use
several, some with dead bytes). Byte-identical output still matters for us: reading a save and
writing it back unchanged should give the original bytes, which makes the writer testable against
real saves. The layouts below were derived from the data and reproduce **all 11152 files byte for
byte** (with the right setting per file).

### The model: an incremental builder

Every file in the install is consistent with a writer that builds the arrays as it goes:

1. Creating a struct appends a struct record. A child struct or list element is created when the
   writer reaches it, so **the struct array is in creation order**.
2. Adding a field appends a field record, so **the field array is in creation order**.
3. A label is appended to the label array the first time a field uses it: **labels are in order
   of first use in the field array** (all files).
4. A complex value is appended to the field data block when its field is added: **field data is in
   field-array order, packed, never shared** (all files).
5. Field indices and list indices are kept in per-struct and per-list blocks whose placement
   follows one of the strategies below.

So a file is determined by (a) the **creation order** of structs and fields, (b) the
**field-indices strategy** and (c) the **list-indices strategy**.

### Creation orders

- **dfs** (depth-first): starting with struct 0, visit each struct's fields in order; adding a
  Struct field creates its child struct immediately and fills it; adding a List field creates its
  first element, fills it completely (recursively), then the next element, and so on. Struct 0 is
  record 0, then structs in pre-order; the field array is the pre-order walk where a Struct/List
  field is followed immediately by its children's fields.
- **elements**: as dfs, but all of a list's element structs are created before the first one is
  filled (only the ITP palettes).
- Other orders, all toolset quirks that a tree alone cannot predict (reproduce them by keeping the
  order the file was read in, `order='keep'`):
  - **DLG** (1011 of 1167 files): node fields are written in passes; `SoundExists` is appended to
    nodes in later passes (sometimes six times, see above), and `ReplyList`/`StartingList` are
    often created before the earlier lists are finished.
  - **GUI** (89 of 91): a panel's `CONTROLS` list field is created first but its elements are
    created and filled only after the panel's other fields.
  - **PTH** (all 94 non-empty files): points and connections are created interleaved
    ([pth.md](pth.md#writing)).
  - **GVT** (the save's `GLOBALVARS.res`): the four `Cat*` lists are created first, then one struct
    per global variable is appended to its category's list in the engine's internal variable order
    (not `globalcat.2da` order), then the `Val*` fields.

### Field-indices strategies

- **second** (in place): a struct gets its block when it receives its **second** field, at the end
  of the array as it is then; later fields are inserted into the block in place, shifting the
  blocks after it. Result: blocks ordered by the field-array index of each struct's second field,
  each block holding all the struct's fields, packed, no dead bytes. This is the engine's save
  behaviour. In most files it gives the same bytes as `struct`; the save's `repute.fac` tells them
  apart: its top struct's first field is `FactionList`, so the top struct gets its block only at
  `RepList`, after the faction structs got theirs.
- **struct**: blocks in struct-array order, packed (82 DLG and 2 GUI need this).
- **move**: the block is placed at the second field as above, but when it must grow and is not the
  last block, it is copied to the end with the new field, and the old copy stays as dead bytes
  (16 UTM, 11 GIT, `temp_char.bic`).

### List-indices strategies

- **field** (in place): a list gets its block (`count` = 0) when the List field is created, at the
  end of the array; elements are inserted in place. Result: blocks in field-array order of the List
  fields, packed. Used by every file except the 15 below, including the save's GLOBALVARS, whose
  four category lists receive elements interleaved and still come out packed.
- **move**: as `field`, but a list that must grow and is not last is copied to the end and the old
  copy left behind (11 GIT, 4 ITP).

### Fields added to an already-built file

Two DLGs (`m41ad_c01.dlg` in `STUNT_57_s.rim`, `unk_comp.dlg` in `unk_m44aa_s.rim`) are a built
file plus 4 and 7 `SoundExists` fields appended afterwards by an in-place editor: each new field
record is appended, and its struct's field-indices block is copied to the end of the array with
the new field (the old copy left as dead bytes). `gff_probe.py` reproduces them that way.

### The engine's save layout (what our writer should produce)

Seven of the eight engine-written save files (UTC, INV, FAC, GIT, IFO, PT, NFO) are reproduced
exactly by **dfs + second + field**; the eighth, GVT, has the same strategies but its own creation
order (above). The same setting reproduces 9905 of the 11143 shipped files. With one save in the
install, this is the best evidence available; re-run the probe when more saves exist. As a
recipe, from a tree whose structs list their fields in the order the engine writes them (the
schema documents give that order per object):

```
structs = [root]; fields = []                  # creation order
visit(s):
    for f in s.fields:                          # in the struct's own order
        fields.append(f)                        # record its owner too
        if f is Struct: structs.append(f.child); visit(f.child)
        if f is List:   for e in f.elements: structs.append(e); visit(e)
visit(root)

labels      = distinct labels in order of first use in `fields`
field data  = complex values of `fields`, in order, packed
field index = for each struct with >= 2 fields, ordered by the position in `fields` of its
              2nd field: its field indices, ascending
list index  = for each List field in `fields` order: count, then element struct indices
struct rec  = (id, 0xFFFFFFFF | sole field index | byte offset of its field-index block, count)
field rec   = (type, label index, inline value | data offset | struct index | list offset)
file        = header (offsets from 56, sections in the order struct, field, label, field data,
              field indices, list indices; counts of indices sections in bytes) + sections
```

Inline values: BYTE/WORD zero-extended, CHAR/SHORT/INT sign-extended to 32 bits, DWORD as is,
FLOAT as its bits.

`gff.write(g)` is this recipe; `gff.write(g, order, fi, li)` selects the others.

### Worked example: an empty PTH

`m12ab.pth` (140 bytes) is the smallest GFF in the install: a top struct with two empty lists.

```
0000  50 54 48 20 56 33 2E 32                      "PTH " "V3.2"
0008  38 00 00 00  01 00 00 00                     structs at 0x38, 1
0010  44 00 00 00  02 00 00 00                     fields at 0x44, 2
0018  5C 00 00 00  02 00 00 00                     labels at 0x5C, 2
0020  7C 00 00 00  00 00 00 00                     field data at 0x7C, 0 bytes
0028  7C 00 00 00  08 00 00 00                     field indices at 0x7C, 8 bytes
0030  84 00 00 00  08 00 00 00                     list indices at 0x84, 8 bytes
0038  FF FF FF FF  00 00 00 00  02 00 00 00        struct 0: id -1, field indices at +0, 2 fields
0044  0F 00 00 00  00 00 00 00  00 00 00 00        field 0: List, label 0, list at +0
0050  0F 00 00 00  01 00 00 00  04 00 00 00        field 1: List, label 1, list at +4
005C  "Path_Points" + 5 NULs                       label 0
006C  "Path_Conections" + 1 NUL                    label 1
007C  00 00 00 00  01 00 00 00                     field indices: [0, 1]
0084  00 00 00 00  00 00 00 00                     list at +0: 0 elements; list at +4: 0 elements
```

## Quirks found in real data

- Duplicate labels inside a struct (DLG `SoundExists` x6, 29 files).
- Dead bytes in the field-indices / list-indices arrays (34 shipped files).
- Labels that differ only in case, sometimes in the same file (`SubType`/`Subtype`).
- Labels misspelt by BioWare and therefore part of the format: PTH `Path_Conections`,
  `Conections`, `First_Conection`; GIT `Paramaters`.
- Negative CHAR/SHORT sign-extended into the whole 32-bit slot (engine-written saves).
- 16-character labels without terminator; labels with spaces (`Creature List`).
- Strings longer than BioWare's suggested 1024 (21); a ResRef that is a single space (2).
- `.res` files in saves are GFFs whose tag (GVT, PT, NFO, INV) tells them apart.
- PTH files with no field data at all (FieldDataCount 0, its offset equal to the field-indices
  offset).

## Checked

`kotor/tools/py/gff_probe.py` (run from `G:\Dev\zlang`):

```
python kotor/tools/py/gff_probe.py            # summary
python kotor/tools/py/gff_probe.py --files    # plus every file not in the engine layout
python kotor/tools/py/gff_probe.py --census   # plus per-tag top-level labels
```

It reads every resource whose header says `V3.2` (every copy, any extension: BIFs, all texture
packs, modules, lips, rims, patch.erf, Override, the save including the nested module save),
writes it back in the engine layout and re-reads it, then searches the writer settings for one that
reproduces the original bytes. Result on the Steam install:

| | Files |
|---|---|
| GFF files checked | 11152 |
| parse failures | 0 |
| semantic round-trip failures (tree written in engine layout and re-read differs) | 0 |
| byte-identical in the engine save layout (dfs/second/field) | 9913 |
| byte-identical with some setting | 11152 |

By setting:

| Source | Order / FI / LI | Files | Tags |
|---|---|---|---|
| save | dfs / second / field | 8 | PT, UTC, INV, FAC, GIT, ARE (shipped copy), IFO, NFO |
| save | keep / second / field | 1 | GVT |
| shipped | dfs / second / field | 9905 | UTW 2058, UTC 1958, UTP 1784, UTT 1121, UTI 1055, UTS 635, UTD 575, DLG 153, UTE 133, ARE 117, IFO 117, GIT 106, PTH 38 (empty), UTM 22, FAC 20, ITP 4, JRL 4, BTC 3, GUI 1, BTI 1 |
| shipped | keep / second / field | 1112 | DLG 930, PTH 94, GUI 88 |
| shipped | keep / struct / field | 79 | DLG |
| shipped | dfs / move / field | 17 | UTM 16, BIC 1 |
| shipped | dfs / move / move | 11 | GIT |
| shipped | elements / second / field | 8 | ITP |
| shipped | dfs / second / move | 4 | ITP |
| shipped | dfs / struct / field | 3 | DLG |
| shipped | elements / struct / field | 2 | GUI |
| shipped | keep / second / field + fields appended later | 2 | DLG |

The probe takes about 45 seconds. `python kotor/tools/py/gff.py dump RESREF.EXT` prints any GFF as
a tree; `python kotor/tools/py/gff.py roundtrip RESREF.EXT` names the setting that reproduces it.

## Sources

- BioWare, *BioWare Aurora Engine Generic File Format (GFF)*:
  https://nwn.wiki/download/attachments/327727/Bioware_Aurora_GFF_Format.pdf (also in xoreos-docs,
  `specs/bioware/GFF_Format.pdf`, https://github.com/xoreos/xoreos-docs).
- BioWare, *BioWare Aurora Engine Localized Strings*: xoreos-docs
  `specs/bioware/LocalizedStrings_Format.pdf`.
- BioWare, *Common GFF Structs* and the per-type documents in the same xoreos-docs folder (struct
  ids and schemas of the NWN ancestors of KOTOR's types).
- Everything about layouts, quirks and counts: measured on the install with the probes above.
