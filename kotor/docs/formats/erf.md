# ERF family: ERF, MOD, SAV, HAK (`V1.0`)

An ERF ("encapsulated resource file") is a named archive: a table of resref + type keys, a table
of offsets and sizes, then the data. KOTOR uses it for the texture packs, `patch.erf`, the per-module
lip-sync archives, and saved games (including a module's saved state nested inside the save). The
same layout carries four signatures; only the first four bytes differ.

All integers are little-endian.

## Where

| Files | Signature | Count | Holds |
|---|---|---|---|
| `TexturePacks/swpc_tex_tpa.erf`, `_tpb`, `_tpc` | `ERF ` | 3 | 3,294 TPC textures each, at three quality levels |
| `TexturePacks/swpc_tex_gui.erf` | `ERF ` | 1 | 1,570 GUI TPC textures and one TXI |
| `patch.erf` (install root) | `ERF ` | 1 | 97 patched resources (TPC, GUI, 2DA, one MDL/MDX) |
| `lips/<module>_loc.mod` | `MOD ` | 117 | the module's LIP files |
| `lips/localization.mod` | `MOD ` | 1 | 2,596 LIP files for global voice-over |
| `lips/global.mod`, `legal.mod`, `mainmenu.mod`, `miniglobal.mod`, `subglobal.mod` | `MOD ` | 5 | nothing (0 entries) |
| `Saves/<slot>/SAVEGAME.sav` | `MOD ` | 1 per save | the save; see [Saved games](#saved-games) |
| `<module>.sav` inside SAVEGAME.sav (type 2057) | `MOD ` | 1 per visited module | the module's saved GIT, ARE, IFO |
| `modules/<module>.mod` | `MOD ` | none in this install | a module packed as one ERF; mods ship these ([resources.md](resources.md#what-is-mounted)) |

`HAK ` (NWN's "hak pak") and `SAV ` are valid signatures of the format, and the engine still knows the
`hak` type and a `HAK:` directory alias, but no file in the install uses them. Note that the engine
writes saves with the `MOD ` signature, not `SAV `. A reader should accept all four and otherwise
treat them identically. When the engine mounts an ERF by name it tries the extensions `.nwm`,
`.mod`, `.sav`, `.erf`, `.hak` in that order ([../re/resman.md](../re/resman.md)). Resource type ids: `erf` 9997, `mod` 2011, `sav` 2057, `hak` 2061
([resource-types.md](resource-types.md)).

## Layout

```
0                          header (160 bytes)
OffsetToLocalizedString    localized string list (LocalizedStringSize bytes; empty in every file here)
OffsetToKeyList            key list: EntryCount x 24 bytes
OffsetToResourceList       resource list: EntryCount x 8 bytes
...                        resource data
```

In every file in the install the four blocks are contiguous and in this order: the string list (if
any) at 160, keys right after it, the resource list right after the keys, the data right after the
resource list, packed back to back **in key order** with no padding, ending exactly at the end of
the file. Data offsets are not aligned (21,540 of 29,763 are not 4-aligned). A reader must still use
the offsets, not assume this.

### Header (160 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | char[4] | FileType | `ERF `, `MOD `, `SAV ` or `HAK ` |
| 4 | 4 | char[4] | Version | `V1.0` |
| 8 | 4 | u32 | LanguageCount | number of localized strings; **0 in every file here** |
| 12 | 4 | u32 | LocalizedStringSize | total bytes of the string list; 0 in every file here |
| 16 | 4 | u32 | EntryCount | number of resources |
| 20 | 4 | u32 | OffsetToLocalizedString | absolute; 160 in every file |
| 24 | 4 | u32 | OffsetToKeyList | absolute; 160 in every file |
| 28 | 4 | u32 | OffsetToResourceList | absolute; `OffsetToKeyList + 24 * EntryCount` in every file |
| 32 | 4 | u32 | BuildYear | years since 1900 |
| 36 | 4 | u32 | BuildDay | days since 1 January, 0-based (1 Jan = 0) |
| 40 | 4 | u32 | DescriptionStrRef | TLK string for a description; **unreliable**, see below |
| 44 | 116 | bytes | reserved | zero in every file |

Offsets inside a nested ERF (a module `.sav` inside SAVEGAME.sav) are relative to the start of the
nested ERF, not to the outer file.

**DescriptionStrRef.** In the shipped files this field is uninitialised memory from BioWare's packer:
0 in 32 files, but also `0xCDCDCDCD` (MSVC's debug-heap fill, in `localization.mod`) and fragments of
ASCII text (`0x70756b63` = "ckup", `0x705f7773` = "sw_p", ...) in the rest. The engine cannot use it
for anything; ignore it on read and write 0 (the save has 0).

**Build date.** Shipped files: 2003 day 309 (114 files), 2003 day 145 (13 older lips MODs),
2004 day 47 (`patch.erf`). The save's ERFs carry the date the game was saved (2023 day 344).

### Localized string list

Present in the format, absent from every file here (NWN shows a module's description from it). For
completeness, `LanguageCount` elements follow one another:

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | LanguageID | `language * 2 + gender` (gender 0 = masculine/neutral, 1 = feminine); language ids in [tlk.md](tlk.md) |
| 4 | 4 | u32 | StringSize | bytes of text that follow |
| 8 | StringSize | char[] | String | text; BioWare says NUL-terminated in `.erf`/`.hak` but not in `.mod`, so trust StringSize and strip a trailing NUL |

### Key entry (24 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 16 | char[16] | ResRef | NUL-padded; a 16-character name has no NUL |
| 16 | 4 | u32 | ResID | the entry's own index (0, 1, 2, ...) in every file |
| 20 | 2 | u16 | ResType | type id |
| 22 | 2 | u16 | unused | 0 in every file |

Entry *i* of the key list pairs with entry *i* of the resource list.

### Resource list entry (8 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | OffsetToResource | from the start of the ERF |
| 4 | 4 | u32 | ResourceSize | bytes |

## Names

- Resrefs keep whatever case the packer had: texture packs are mixed (`Gui_atmoss_1`,
  `SCR_DEF_NC`, `1024x768back`), lips MODs lower case, the save's top level upper case (`AVAILNPC0`,
  `END_M01AA`), its nested module save mixed (`m01aa`, `Module`). Compare case-insensitively
  ([resources.md](resources.md#names)).
- 18,110 of 29,763 ERF resrefs use all 16 bytes (almost every lip name, e.g. `nm13aabast01059_`).
- `lma_tech01 copy` (with a space) occurs in all three texture packs: a stray file from an artist's
  folder. Names are arbitrary bytes, not identifiers; don't validate them.
- No file has the same resref + type twice.
- Key order means nothing: 28 MODs happen to be alphabetical, the other 102 files are not.

## Saved games

A save slot is a directory `Saves/NNNNNN - Name/` (format string `SAVES:%06d - %s` in the exe)
holding loose files and one ERF; see [inventory.md](inventory.md#saves). The one save in the
install, `000002 - Game1/SAVEGAME.sav`, is a `MOD V1.0` ERF:

| # | ResRef | Type | Size | What |
|---|---|---|---|---|
| 0 | `AVAILNPC0` | utc 2027 | 10,941 | party-member 0's creature, saved |
| 1 | `END_M01AA` | sav 2057 | 487,755 | the module `end_m01aa`'s saved state, itself a `MOD V1.0` ERF |
| 2 | `INVENTORY` | res 0 | 6,120 | the party inventory, a GFF (`INV `) |
| 3 | `REPUTE` | fac 2038 | 27,758 | faction standings, a GFF (`FAC `) |

The nested `END_M01AA` holds `m01aa` (git 2023, 453,984 bytes), `m01aa` (are 2012) and `Module`
(ifo 2014), in that order. Every GFF in it is described in [gff.md](gff.md).

To write a save ERF the way the engine does (all of this is what the one save shows; more saves are
needed to tell rules from coincidence, e.g. whether top-level entries are always alphabetical):

- signature `MOD V1.0`, LanguageCount 0, LocalizedStringSize 0;
- OffsetToLocalizedString = OffsetToKeyList = 160; OffsetToResourceList = 160 + 24n;
- BuildYear = year - 1900, BuildDay = 0-based day of the year, of the time of saving;
- DescriptionStrRef 0, reserved bytes 0;
- keys with ResID = index and unused = 0; resrefs in upper case at the top level and in the
  engine's own spelling inside a module save;
- data at 160 + 32n, each resource immediately after the previous one, in key order;
- the nested module ERF is written whole as the data of its `sav` entry, its own offsets relative
  to itself.

## Reading

1. Read 160 bytes; check the signature and `V1.0`.
2. Read `EntryCount` keys at `OffsetToKeyList` and `EntryCount` resource entries at
   `OffsetToResourceList`; for a nested ERF, add the nested ERF's start to every offset.
3. Index by `(lowercase(resref), type)`.

## Checked

`python kotor/tools/py/containers_probe.py` (independent of `kres.py`) parses all 130 ERF-family
files (4 texture packs, `patch.erf`, 123 lips MODs, `SAVEGAME.sav`, and the module save nested in
it) and checks: signature and version; reserved bytes; the string list consuming exactly
LocalizedStringSize; block order; ResID = index; unused = 0; no duplicate resref + type; all regions
(header, string list, keys, resource list, every resource) non-overlapping, gap-free and ending at
the end of the file. It also tallies build dates, description strrefs, key order and name case.
Result: 130 files, 29,763 entries, **0 failures**.

## Sources

- BioWare, *Encapsulated Resource File Format* (Aurora engine), in xoreos-docs:
  <https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/ERF_Format.pdf>, and
  *Localized Strings* (same directory) for the language/gender id.
- The install's ERF/MOD files and its one save (the probe above).
