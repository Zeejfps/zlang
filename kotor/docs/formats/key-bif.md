# KEY and BIF (`KEY V1  `, `BIFFV1  `)

The game's bulk data lives in 26 BIF archives under `data/`. A BIF holds resources by number only;
the names live in a single index, `chitin.key`, which maps every resref + type to "entry *n* of BIF
*b*". Together they are the lowest-priority resource source (see [resources.md](resources.md)).

All integers are little-endian. "resref" is the 16-byte resource name described in
[resources.md](resources.md#names).

## Where

| File | Count | Notes |
|---|---|---|
| `chitin.key` (install root) | 1 | 569,239 bytes, indexes 25,836 resources in 26 BIFs |
| `data/*.bif` | 26 | 2da, gui, items, layouts, legacy, lightmaps, lightmaps2..13, models, party, player, scripts, sounds, templates, textures, `_newbif` |

KEY and BIF have resource type ids 9999 and 9998 ([resource-types.md](resource-types.md)), but they
are never found inside another container; the engine opens `HD0:chitin` (`chitin.key`) by name.
What each BIF holds is listed in [inventory.md](inventory.md).

## KEY layout

```
0      header (64 bytes)
64     file table: BIFCount x 12 bytes
376    BIF filename strings, packed, in file-table order
847    key table: KeyCount x 22 bytes, to end of file
```

(The offsets on the left are this install's; always use the header's.)

### Header (64 bytes)

| Offset | Size | Type | Field | Value in the install |
|---|---|---|---|---|
| 0 | 4 | char[4] | file type | `KEY ` |
| 4 | 4 | char[4] | version | `V1  ` (two spaces) |
| 8 | 4 | u32 | BIFCount | 26 |
| 12 | 4 | u32 | KeyCount | 25,836 |
| 16 | 4 | u32 | OffsetToFileTable | 64 |
| 20 | 4 | u32 | OffsetToKeyTable | 847 |
| 24 | 4 | u32 | BuildYear, years since 1900 | 103 (2003) |
| 28 | 4 | u32 | BuildDay, days since 1 January (0-based) | 309 |
| 32 | 32 | bytes | reserved | all zero |

### File table entry (12 bytes, one per BIF)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | FileSize | size of the BIF in bytes; matches the file on disk for all 26 |
| 4 | 4 | u32 | FilenameOffset | absolute offset of the BIF's name in this file |
| 8 | 2 | u16 | FilenameSize | length of the name **including** its terminating NUL |
| 10 | 2 | u16 | Drives | bit mask of where the BIF lives; bit 0 = `HD0` (the install directory). Always 1 |

The name is a path relative to the drive, with a backslash: `data\2da.bif`. BioWare's NWN document
calls it non-terminated, but in KOTOR every name ends in exactly one NUL that is counted in
FilenameSize. Read `FilenameSize` bytes and cut at the first NUL. On a case-sensitive file system,
match the name case-insensitively (the files are lower case in this install, and so are the names).

The file-table index of a BIF (0..25) is the BIF index used by the ResIDs below.

### Key entry (22 bytes, one per resource)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 16 | char[16] | ResRef | resource name, NUL-padded; 16-character names have no NUL |
| 16 | 2 | u16 | ResourceType | type id ([resource-types.md](resource-types.md)) |
| 18 | 4 | u32 | ResID | where the resource is, see below |

Note the entry is 22 bytes, so the u32 is not 4-aligned; read it bytewise.

### ResID

```
bits 31..20   BIF index (into the file table)          ResID >> 20
bits 19..0    index into that BIF's variable table     ResID & 0xFFFFF
```

BioWare's document reserves bits 19..14 for a *fixed*-resource index (fixed ID = `(bif << 20) +
(index << 14)`), but fixed resources were never implemented: every ResID in the install has bits
19..14 zero and every BIF has zero fixed resources. Treat the low 20 bits as the variable index.

### Properties of chitin.key (all checked)

- All 25,836 resrefs are lower case. Characters are `a-z 0-9 _` plus `-` (e.g. `p_hk-47_atk1`) and
  `+` (`k_hmis_talk0+`). 1,807 names use all 16 bytes.
- No resref + type appears twice. Every key points at a distinct BIF entry, and every BIF entry has
  exactly one key: there are no unnamed resources.
- Keys are sorted by (BIF index, variable index), i.e. in BIF order. Nothing depends on this.
- The same resref may exist with several types (`p_bastila.utc`, `p_bastila.ssf`, ...); a lookup
  is always by resref **and** type.

## BIF layout

```
0                header (20 bytes)
20               variable resource table: VariableCount x 16 bytes
20 + 16*count    resource data, packed back to back in table order, to end of file
```

### Header (20 bytes)

| Offset | Size | Type | Field | Value in the install |
|---|---|---|---|---|
| 0 | 4 | char[4] | file type | `BIFF` |
| 4 | 4 | char[4] | version | `V1  ` (two spaces) |
| 8 | 4 | u32 | VariableResourceCount | 1 (`_newbif`, `legacy`) .. 6,444 (`models`) |
| 12 | 4 | u32 | FixedResourceCount | 0 in every BIF |
| 16 | 4 | u32 | OffsetToVariableTable | 20 in every BIF |

### Variable resource entry (16 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | ID | equals the KEY's ResID for this resource: `(bif << 20) \| index` |
| 4 | 4 | u32 | Offset | absolute offset of the data in the BIF |
| 8 | 4 | u32 | FileSize | size of the data |
| 12 | 4 | u32 | ResourceType | same type id as the key (all 25,836 agree); upper 16 bits zero |

The ID's low 20 bits equal the entry's own index. BioWare notes that patch BIFs may store a different
BIF number in the high bits and that the engine ignores them; in KOTOR they always match. A reader
should not rely on the ID at all: index the table by the KEY's variable index.

A fixed-resource table (20-byte entries: ID, Offset, PartCount, FileSize, ResourceType) would follow
the variable table; it never occurs, and a reader may reject `FixedResourceCount != 0`.

### Data

Resource data starts immediately after the table and is packed with no padding, in table order;
offsets are not aligned (18,515 of 25,836 are not even 4-aligned). The last resource ends exactly at
the end of the file. There is no compression.

## Reading a resource

1. Look up `(lowercase(resref), type)` in a hash map built from the key table.
2. `bif = ResID >> 20`, `index = ResID & 0xFFFFF`.
3. Open `data\<name>.bif` (case-insensitively), read entry `index` of its variable table, seek to
   `Offset`, read `FileSize` bytes.

Keep the BIF file handles open; the engine streams from them (models.bif alone is 954 MB). Reading
just the variable table of every BIF at start-up is cheap (25,836 x 16 bytes).

## Quirks

- The 12 files in `rims/` hold 1,936 entries (1,192 distinct resref + type), every one of which is
  also in chitin; see [rim.md](rim.md) and [resources.md](resources.md#rims).
- `data/_newbif.bif` holds a single resource, `global.jrl`, and `data/legacy.bif` a single
  `chrome1.tga`: late additions to the build.
- All 112 `.vis` files live in the `lightmaps*.bif` archives next to the area lightmaps, while the
  `.lyt` files are in `layouts.bif` ([inventory.md](inventory.md)).

## Checked

`python kotor/tools/py/containers_probe.py` (independent of `kres.py`) parses `chitin.key` and all
26 BIFs and checks: magic and versions; reserved bytes zero; BIF sizes against the file table;
FilenameSize including exactly one NUL; every key's BIF index and variable index in range; key and
BIF entry types equal; BIF entry IDs equal the full ResID; no fixed resources and no fixed bits; no
duplicate resref + type; every BIF entry referenced exactly once; BIF regions (header, table, every
resource) non-overlapping, gap-free and ending at end of file. Result: 25,836 keys, 26 BIFs,
**0 failures**.

## Sources

- BioWare, *Key and BIF File Formats* (Aurora engine), in xoreos-docs:
  <https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/KeyBIF_Format.pdf>.
  KOTOR deviates from it in the NUL-terminated BIF names; everything else matches.
- The install's own `chitin.key` and BIFs (the probe above).
