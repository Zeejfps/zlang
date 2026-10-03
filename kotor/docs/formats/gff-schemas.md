# GFF schemas: what is inside KOTOR's GFF files

[gff.md](gff.md) describes the binary GFF V3.2 container (structs, fields, labels, lists). This
file and its companions describe what the game stores in it: every field label of every GFF
resource type in the install, its type, how many files have it, the values seen, and what it
means.

| File | Types |
|---|---|
| [gff-templates.md](gff-templates.md) | UTC creature, UTD door, UTP placeable, UTI item, UTE encounter, UTS sound, UTT trigger, UTW waypoint, UTM store; BIC/BTC/BTI leftovers |
| [gff-module.md](gff-module.md) | IFO module info, ARE area, GIT area instances, PTH path graph |
| [gff-dialog.md](gff-dialog.md) | DLG conversation, JRL journal |
| [gff-gui.md](gff-gui.md) | GUI screen layouts |
| [gff-save.md](gff-save.md) | save games: NFO, PT, GVT, INV, saved UTC, saved IFO/ARE/GIT |
| this file | conventions, FAC factions, ITP palettes, the checks |

## What the install holds

Every resource whose first 8 bytes are `XXXXV3.2` was parsed, in every container (BIFs via
`chitin.key`, the module RIMs, `rims/`, `lips/`, `patch.erf`, Override, which is empty). Note that
`kres.Game` does not load `patch.erf`; the GFF probes add it themselves. "Distinct" counts
files by content (a template shipped unchanged in a BIF and in several module RIMs counts once).
The resource extension always matches the GFF type in the header.

| GFF type | Distinct | Entries | Field paths | Where |
|---|---|---|---|---|
| UTC | 1942 | 1958 | 104 | module `_s.rim`s (1753), `templates.bif` (205) |
| UTW | 1896 | 2058 | 12 | module `_s.rim`s (2049), `templates.bif` (9) |
| UTP | 1569 | 1784 | 61 | module `_s.rim`s (1467), `templates.bif` (317) |
| DLG | 1145 | 1167 | 88 | module `_s.rim`s (1135), `templates.bif` (32: party and global dialogues) |
| UTT | 968 | 1121 | 32 | module `_s.rim`s (1100), `templates.bif` (21) |
| UTI | 873 | 1055 | 30 | `templates.bif` (557), module `_s.rim`s (436), `rims/global.rim` and `miniglobal.rim` (31 each) |
| UTS | 592 | 635 | 26 | module `_s.rim`s |
| UTD | 551 | 575 | 54 | module `_s.rim`s (525), `templates.bif` (50) |
| UTE | 132 | 133 | 26 | module `_s.rim`s (68), `templates.bif` (65) |
| ARE, GIT, IFO | 117 each | 117 each | 201, 109, 44 | module `.rim`s (one area per module) |
| PTH | 95 | 132 | 7 | module `_s.rim`s |
| GUI | 91 | 91 | 197 | `gui.bif` (84), `patch.erf` (7) |
| UTM | 38 | 38 | 14 | module `_s.rim`s |
| ITP | 16 | 16 | 18 | `templates.bif` |
| JRL | 4 | 4 | 14 | `_newbif.bif` (`global.jrl`), 3 module `_s.rim`s |
| FAC | 2 | 20 | 8 | 20 module `_s.rim`s (`repute.fac`) |
| BTC, BIC, BTI | 3, 1, 1 | 3, 1, 1 | 71, 89, 11 | `templates.bif` |
| **Install total** | **10270** | **11143** | | |
| save GFFs | 9 | 9 | | `Saves/000002 - Game1` (NFO, PT, GVT, INV, FAC, UTC, IFO, ARE, GIT) |

There is no GIC (toolset comments), no BIC in a player vault, and no UTG/UTA/BTD type in KOTOR's
data.

## Conventions used in the tables

- **Field paths.** `Field` is a field of the top-level struct; `List/Field` a field of the
  structs in a list; `Struct.Field` a field of a struct-valued field. Paths nest:
  `Categories/EntryList/Text`. Labels are case-sensitive and kept exactly as stored, including
  misspellings (`Paramaters`, `Path_Conections`, `ScriptEndDialogu`).
- **Type** is the GFF field type. A type such as `BYTE/INT` means different files store the field
  with different types; only three paths do (save-game stack and action values, which are typed
  by a sibling field, and `PT_PAZAAKCOUNT`): a reader must convert by the stored type, never
  assume it.
- **Files** is how many distinct files contain the path at least once, or `all`.
- **Values**: numeric range, or every value when there are few; string examples with the number
  of empty values; for CExoLocString how many carry a strref (resolves in `dialog.tlk`) and how
  many carry inline text (substring ids; id = language x 2 + gender, and only id 0, English
  male/neutral, occurs); for lists the entry counts and the struct ids of the elements
  (`struct id = index` when every element's id equals its position).
- **Meaning** comes from BioWare's published Aurora (NWN) documents where KOTOR keeps the NWN
  field, otherwise it is read from the data and marked *(inferred)*; "always X" means every file
  in the install has X. Where a field refers to a 2DA row, a resource or a strref, the
  cross-check below tested it.

## Things every reader needs

- **Missing fields are normal.** Many fields exist only in files written by later toolset
  versions (e.g. `UTC.PartyInteract` in 1910 of 1942 creatures, `UTD.Static` in 490 of 551):
  every field must have a default, and the defaults should be what the bulk of the files
  store (usually 0 / empty).
- **Label variants.** A few fields appear under two spellings in different files (`refbonus` and
  `RefBonus`, never both in one file). Match exactly first, then case-insensitively.
- **Blueprint vs instance vs saved object.** A blueprint (UTx) holds an object's full template.
  A module's GIT instance holds only placement and per-instance overrides (`UseTemplates` = 1),
  and the engine merges the blueprint in. A saved GIT holds every object whole (template fields
  plus runtime state), so loading a save must not re-read blueprints for objects already in the
  saved GIT.
- **Struct ids** usually do not matter to the reader, but a writer must reproduce them: they are
  given per list in the tables (e.g. GIT creature 4, door 8; `Equip_ItemList` = slot bit; DLG
  lists = index).
- **Resrefs** are at most 16 characters and compared case-insensitively (the data mixes case:
  `M12aa_C02_cam`); empty means none. `Tag`s are free strings compared case-insensitively by
  `GetObjectByTag` in NWN; KOTOR's behaviour is unverified.

## FAC: factions (`repute.fac`)

KOTOR ships `repute.fac` in 20 module `_s.rim`s (two distinct files); other modules have none and
the game then uses `repute.2da` *(inferred)*. A save has one `repute.fac` for the whole game (21
factions, every pair: 21 x 21 - 36 = 405 entries; below as `save:FAC`). Standing 0..10 hostile,
11..89 neutral, 90..100 friendly (BioWare).

<!-- gff-table FAC -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `FactionList` | List | all | 5 entries; struct id = index | Factions; struct id = index; the index is the faction id. |
| `FactionList/FactionParentID` | DWORD | all | 4294967295 | Parent faction; 0xFFFFFFFF for the base factions. |
| `FactionList/FactionName` | CExoString | all | e.g. `PC`, `Hostile`, `Commoner` | Faction name. |
| `FactionList/FactionGlobal` | WORD | 1 | 1 | 1 if a change of standing with one member applies to all. |
| `RepList` | List | all | 0..20 entries; struct id = index | How each faction regards each other; struct id = index. |
| `RepList/FactionID1` | DWORD | 1 | 0, 1, 2, 3, 4 | The faction being regarded. |
| `RepList/FactionID2` | DWORD | 1 | 1, 2, 3, 4 | The faction doing the regarding. |
| `RepList/FactionRep` | DWORD | 1 | 0, 50, 100 | Standing of FactionID2 toward FactionID1, 0..100. |
<!-- /gff-table -->

<!-- gff-table save:FAC -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `FactionList` | List | all | 21 entries; struct id = index | Factions (21 in KOTOR); the index is the faction id used by `FactionID`. |
| `FactionList/FactionName` | CExoString | all | e.g. `Player`, `Hostile_1`, `Friendly_1` | Faction name (`Player`, `Hostile_1`, `Friendly_1`, ...: the rows of `repute.2da`). |
| `FactionList/FactionParentID` | DWORD | all | 4294967295 | 0xFFFFFFFF. |
| `FactionList/FactionGlobal` | WORD | all | 1 | 1 for all. |
| `RepList` | List | all | 405 entries; struct id = index | Standings between every pair; struct id = index. |
| `RepList/FactionID1` | DWORD | all | 0..20 (21 values) | The faction being regarded. |
| `RepList/FactionID2` | DWORD | all | 0..20 (21 values) | The faction doing the regarding. |
| `RepList/FactionRep` | DWORD | all | 0, 50 | Standing 0..100. |
<!-- /gff-table -->

## ITP: toolset palettes

The 16 `*pal.itp` / `*palstd.itp` files in `templates.bif` are the toolset's blueprint palettes
(creature, door, encounter, item, placeable, sound, store, trigger, waypoint). The game does not
read them; they are listed so that a GFF corpus tool can parse them.

<!-- gff-table ITP -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `MAIN` | List | all | 2..11 entries; struct ids 0, 1 | Top-level palette categories. |
| `MAIN/ID` | BYTE | all | 0..20 (15 values) | Category id (matches blueprints' `PaletteID`). |
| `MAIN/DELETE_ME` | CExoString | all | e.g. `ASSIGN TO NEW CAT…`, `Special`, `Miscellaneous` | Category name (toolset text). |
| `MAIN/LIST` | List | all | 1..157 entries; struct ids 0, 1 | Sub-categories or blueprints. |
| `MAIN/LIST/ID` | BYTE | 13 | 0..19 (20 values) | Sub-category id. |
| `MAIN/LIST/DELETE_ME` | CExoString | 13 | e.g. `Custom 1`, `Custom 2`, `Custom 3` | Sub-category name. |
| `MAIN/LIST/LIST` | List | 4 | 1..98 entries; struct id 0 | Blueprints in the sub-category. |
| `MAIN/LIST/LIST/NAME` | CExoString | 4 | 1 empty; e.g. `Bantha`, `Brith`, `Dewback` | Display name. |
| `MAIN/LIST/LIST/RESREF` | ResRef | 4 | e.g. `c_bantha`, `g_bantha01`, `c_brith` | Blueprint resref. |
| `MAIN/LIST/LIST/CR` | FLOAT | 1 | 1..20 (13 values) | Challenge rating (creatures). |
| `MAIN/LIST/NAME` | CExoString | 6 | 1 empty; e.g. `Commoner`, `Dark Jedi`, `Assassin Droid` | Display name of a blueprint at this level. |
| `MAIN/LIST/RESREF` | ResRef | 6 | e.g. `c_drdassassin`, `g_assassindrd01`, `c_drdmkone` | Blueprint resref. |
| `MAIN/LIST/CR` | FLOAT | 1 | 1..20 (14 values) | Challenge rating. |
| `MAIN/LIST/Type` | BYTE | 1 | 0 | Node type. |
| `MAIN/TYPE` | BYTE | 7 | 0, 2 | Node type. |
| `MAIN/Type` | BYTE | 1 | 0 | Node type (other capitalisation). |
| `NEXT_USEABLE_ID` | BYTE | 9 | 6..21 (7 values) | Next free category id. |
| `RESTYPE` | WORD | 9 | 2025..2058 (9 values) | Resource type id of the palette's blueprints (2025 UTI ... 2058 UTW). |
<!-- /gff-table -->

## Checked

Probes, all in `kotor/tools/py/`:

- `gffpy.py`: a minimal GFF V3.2 reader (validates every offset, count and CExoLocString size;
  any inconsistency is an error).
- `gffschema.py scan`: parses every GFF in the install and the save (including the module state
  nested in `SAVEGAME.sav`), and writes the field inventory to `kotor/extract/gff-inventory.json`.
  `gffschema.py tables` regenerates the tables in `gff-*.md` from it, keeping the hand-written
  Meaning column (a row without a meaning is reported).
- `gffxref.py`: checks fields that point elsewhere: 2DA row in range, resource exists, strref
  resolves to non-empty text in `dialog.tlk`. Output in `kotor/extract/gffxref.txt`.

Results (2026-10-03, Steam install):

- **Parse:** 11 143 GFF entries (10 270 distinct) plus 9 save GFFs: **0 failures**. 0 field paths
  with inconsistent types except the three typed-by-sibling or quirk cases noted above.
- **Struct ids:** all as stated in the tables (GIT list ids match BioWare's table; `Equip_ItemList`
  ids are the `INVENTORY_SLOT_*` bits; DLG, JRL, FAC and save stack lists use id = index).
- **Cross-references** (values checked / misses):
  - 2DA rows, no misses: UTC `Appearance_Type` -> appearance (1942/0), `PortraitId` -> portraits,
    `SoundSetFile` -> soundset, `Gender`, `FactionID` -> repute, `WalkRate` -> creaturespeed,
    `PerceptionRange` -> ranges, `ClassList/Class` -> classes, `FeatList/Feat` -> feat (8088/0),
    known powers -> spells; UTD `GenericType` -> genericdoors; UTP `Appearance` -> placeables
    (1569/0); UTI `BaseItem` -> baseitems, `PropertyName` -> itempropdef, `CostTable` ->
    iprp_costtable, `UpgradeType` -> upgrade; UTE `DifficultyIndex`; UTS `Priority` ->
    prioritygroups; UTT `TrapType` -> traps, `Cursor` -> cursors; UTW `Appearance` -> waypoint;
    ARE `CameraStyle` -> camerastyle; GIT ambient sound and music -> ambientsound/ambientmusic;
    DLG `PlotIndex` -> plot, `CamVidEffect` -> videoeffects; JRL `PlotIndex`, `PlanetID` ->
    planetary.
  - 2DA rows with misses: `Race` (1 NWN leftover, value 8), `SpecAbilityList/Spell` (1, value
    299), UTD `PortraitId` (558 in 2 doors), UTI `Param1` (255 = none, by design),
    `EnvAudio` in ARE rooms (10 of 1308) and GIT (19 of 117) above `soundeax.2da`'s 24 rows.
  - Resources: every GIT `TemplateResRef` exists as its blueprint type (creatures 1619/0, doors
    724/0, placeables 3214/0, triggers 996/0, waypoints 4064/0, sounds 1103/0, encounters 51/0,
    stores 36/0, items 50/0); `LinkedToModule` values all name modules; blueprint `ItemList`
    resrefs all exist; DLG `CameraModel`, `StuntModel`, `AmbientTrack` all exist; ARE
    `RoomName` misses only the 15 `****` placeholders; script hooks miss only NWN default
    scripts and ~40 dead names out of ~45 000 references; UTS waves 2076/2 missing.
  - Strrefs: every non-empty CExoLocString strref checked resolves to text except one UTI
    description and two DLG replies (34 000+ checked).
  - DLG `VO_ResRef`: 13 942 of 20 357 entry references exist as WAVs under `streamwaves/`;
    reply VO never exists (the PC is not voiced).
- **Other checks:** PTH edges are stored contiguously per point (`First_Conection` = running
  sum of `Conections`) in all 95 files (7014 points); ARE room names equal the LYT's room set in
  all 117 areas (order differs in 61); saved script situations' `Code` equals the named NCS file
  minus its 13-byte header, and its resume offset and BP/SP match the creating
  STORE_STATE (2 of 2).

## Open questions

- Bit order of `GLOBALVARS.res` `ValBoolean` and of `SWVarTable.BitArray` (the only save has no
  true booleans): settle with a later save or the executable.
- `EnvAudio` values above 23; `ConversationType` 2; `FadeType` 1; DLG `CameraAngle` 1, 2, 3, 5
  framings; `MapResX`; `AreaMapData` packing.
- Whether `Tag` comparison is case-insensitive in KOTOR.
