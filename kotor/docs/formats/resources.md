# Resources: names, sources and lookup order

How the engine turns a resref + type into bytes: what a name is, which sources it searches, and in
what order. Container formats are in [key-bif.md](key-bif.md), [erf.md](erf.md) and
[rim.md](rim.md); type ids in [resource-types.md](resource-types.md); what the install holds in
[inventory.md](inventory.md); the engine functions behind this in
[../re/resman.md](../re/resman.md).

**Evidence** is marked: *RE* = read in the decompiled `swkotor.exe` (Steam build, unpacked; function
addresses in [../re/resman.md](../re/resman.md)); *data* = measured on the install by a probe;
*community* = KOTOR modding knowledge, cited. Everything about the lookup order below is *RE*, and
agrees with the data and with the community's rules.

## Names

- A **resref** is 1 to 16 bytes. In archives it is a 16-byte field, NUL-padded, with no NUL when
  all 16 bytes are used (26,299 of 78,103 copies do). For a file in a directory source such as
  `Override/`, the engine takes the name up to the first `.`, **truncated to 16 characters**, and the
  three characters after that `.` as the extension (*RE*; details in
  [resource-types.md](resource-types.md#extensions-in-directories)).
- **Case-insensitive.** chitin.key stores lower case; ERFs and RIMs keep the packer's case
  (`Gui_atmoss_1`, `PFHA01`, the save's `END_M01AA`, `Module`). Fold to ASCII lower case when
  indexing. No source in the install has two names that differ only in case. Module and folder
  names on disk are mixed case too (`M12ab.rim`, `STUNT_00.rim`, `NM13AABAST01059_.wav` in
  `streamwaves/m13aa/bast01/`): on a case-sensitive file system, open files through a
  case-insensitive directory lookup.
- Names are bytes, not identifiers: the install has `-`, `+`, `!` and one space
  (`lma_tech01 copy.tpc`). Don't validate them.
- A lookup key is **(resref, type id)**. Files in directories map their extension to a type id
  through the table in [resource-types.md](resource-types.md).

## The resource manager

The engine keeps every source ("key table") in one of four classes, each a list with the most
recently added source at its head (*RE*):

| Class | What | Added with |
|---|---|---|
| DIR | a directory, every file in it (not subfolders) | logical name such as `OVERRIDE:` |
| ERF | an ERF-family file; the engine tries the name with `.nwm`, `.mod`, `.sav`, `.erf`, `.hak`, first that opens | a name and a **group number, 1 or 2** |
| RIM | a `.rim` file | a name |
| KEY | a KEY file and its BIFs | `HD0:CHITIN` |

A lookup of (resref, type) walks, and returns the first source that has it:

1. **DIR** sources, newest first;
2. **ERF** sources of group 1, newest first;
3. **RIM** sources, newest first;
4. **ERF** sources of group 2, newest first;
5. **KEY** sources.

The logical names (`HD0:`, `OVERRIDE:`, `MODULES:`, ...) resolve through `swkotor.ini`'s `[Alias]`
section, with built-in defaults for those the ini lacks (`LIPS=.\lips`, `RIMS=.\rims`,
`TEXTUREPACKS=.\texturepacks`, `MOVIES=.\movies`, `PATCH=.\patch`, ...).

## What is mounted

At start-up, in this order (*RE*; "absent" = not in a PC install):

| Order | Source | Class | Note |
|---|---|---|---|
| 1 | `TEMPCLIENT:` | DIR | absent |
| 2 | `OVERRIDE:` = `Override/` | DIR | |
| 3 | `ERRORTEX:` | DIR | absent |
| 4 | `HD0:CHITIN` = `chitin.key` | KEY | |
| 5 | `RIMS:` = `rims/` | DIR | makes `global.rim` etc. findable as resources of type `rim` |
| 6 | `SERVERVAULT:`, `PORTRAITS:` | DIR | absent |
| 7 | `OVERRIDE:textures` | ERF group 1 | an ERF named `textures` inside `Override/`, if one exists |
| 8 | `HD0:patch` = `patch.erf` | ERF group 1 | |
| 9 | `HD0:MOVIES`, `HD0:STREAMWAVES`, `HD0:STREAMMUSIC` | DIR | top level of each folder only |
| 10 | `RIMS:GLOBAL` = `rims/global.rim` | RIM | only if `global.rim` exists in `rims/` |
| 11 | `TEXTUREPACKS:<texture>`, then `TEXTUREPACKS:<gui>` | ERF group 2 | names from `texpacks.2da`, see [Texture packs](#texture-packs) |

`RIMS:MAINMENU` (`rims/mainmenu.rim`) and `RIMS:CHARGEN` (`rims/chargen.rim`) are mounted as RIMs
while the main menu and character generation run, and removed after. The `*dx.rim` files and
`miniglobal.rim` are never mounted on PC (the `dx` RIMs are reached only through Xbox paths).

For a module `<m>` (*RE*), on entering it:

1. the module's main file is copied into `CURRENTGAME:` (`.\currentgame`): from a game in progress
   (`GAMEINPROGRESS:<m>.sav`, the module's saved state), else `modules/<m>.mod`, else
   `modules/<m>.rim`;
2. `LIPS:<m>_loc` (ERF group 2), then `LIPS:localization` (ERF group 2);
3. if `modules/<m>.mod` exists: `MODULES:<m>` as ERF group 2, and **no `_s.rim`**; otherwise
   `MODULES:<m>_s` (`<m>_s.rim`) as a RIM;
4. the copy in `CURRENTGAME:`: a `.sav` as ERF group 2; otherwise a `.rim` as a RIM. When a `.mod`
   was copied, nothing is mounted here (the `.mod` from step 3 already holds the ARE/GIT/IFO).

All of these are removed when the module is left. Only one module is mounted at a time, which the
data requires: every module has a `module.ifo`, and 2,060 names recur across modules' `_s.rim`
files, with different bytes in 1,223 of them (`backpack001.utp`, `c_drdastro001.utc`, ...)
(*data*).

## The resulting order

For a vanilla PC install inside a module, highest priority first:

| # | Source | Class |
|---|---|---|
| 1 | `streammusic/`, `streamwaves/` (top level), `movies/`, `rims/` (as files), `Override/` | DIR, in that order |
| 2 | `patch.erf`, then `Override/textures.*` if present | ERF group 1 |
| 3 | the module's `.rim` (are, git, ifo), then its `_s.rim`, then `rims/global.rim` | RIM |
| 4 | the saved module `.sav` or the module `.mod`; `lips/localization.mod`; `lips/<m>_loc.mod`; `swpc_tex_gui.erf`; the chosen `swpc_tex_tp?.erf` | ERF group 2 |
| 5 | `chitin.key` BIFs | KEY |

Consequences, each consistent with the data:

- **Override beats everything** (the community's rule [1][2]), except a same-named file in the
  top level of `streammusic/`, `streamwaves/` or `movies/`, which are newer DIR sources.
- **`patch.erf` beats the module and the packs.** Its 75 player-head TPCs replace the packs', its
  `skills.2da` and `weapondischarge.2da` replace chitin's and `global.rim`'s (*data*: they differ).
- **A module beats chitin**: 133 names exist in both a `_s.rim` and chitin, 80 with different
  bytes, such as `test.ncs` (4,669 bytes in `danm13_s.rim`, 72,025 in `scripts.bif`) (*data*).
  It also beats `global.rim`, being a newer RIM (3 of the 9 shared scripts differ).
- **`global.rim` beats chitin**, so the game reads its 13 2DAs whose tabs are NULs; its 2DA
  parser accepts NUL separators and the tables decode to the same content ([2da.md](2da.md)).
- **A `.mod` replaces both RIMs** (*community* [3] says the `.mod` must contain both RIMs' files;
  *RE* shows why: with a `.mod`, neither `<m>.rim` nor `<m>_s.rim` is mounted).
- **A saved module's ARE/GIT/IFO come from the save**: when continuing a game the copied `.sav`
  replaces `<m>.rim`, which is then not mounted. Being in ERF group 2 it ranks below the RIMs, but
  `_s.rim` holds no ARE/GIT/IFO. A `.git` in `Override/` still wins, which is why modders see an
  area reset on load when they leave one there [1].
- `lips/localization.mod` and a module's `_loc.mod` share 1,062 names, all byte-identical
  (*data*); their order doesn't matter.

### Our engine

Mount the same sources in the same classes and order. Two simplifications give identical results
on this data and are our decision: skip the absent Xbox and NWN sources (`TEMPCLIENT:`,
`ERRORTEX:`, `SERVERVAULT:`, `PORTRAITS:`, `HD0:players`, `_a`/`_adx` RIMs, `LIVE*`), and skip
`rims/` entirely (everything in `global.rim`, `mainmenu.rim` and `chargen.rim` is in chitin, the
13 NUL-separated 2DAs decoding to the same tables). The VO subfolders of `streamwaves/` are found
by path, below, not by search.

```
find(resref, type):
    key = (ascii_lower(resref), type); reject len(resref) > 16
    for class in [DIR, ERF group 1, RIM, ERF group 2, KEY]:
        for source in class, newest first:
            if source has key: return source.read(key)
```

## Texture packs

`texpacks.2da` (in `2da.bif`) lists the packs, one row per quality level:

| Row | desc | texture | gui | strrefname | dynmemratio | mem |
|---|---|---|---|---|---|---|
| 0 | 32MB_32BIT | swpc_tex_tpc | swpc_tex_gui | 48003 | 0.750 | 31457280 |
| 1 | 64MB_32BIT | swpc_tex_tpb | swpc_tex_gui | 48004 | 0.750 | 62900000 |
| 2 | 128MB_32BIT | swpc_tex_tpa | swpc_tex_gui | 48005 | 0.750 | 134217728 |

The row is `swkotor.ini` `[Graphics Options] Texture Quality=`; a missing key or a value above 3
means 0, and a value of 3 passes that check but has no row, so no pack is mounted (*RE*). This install has 2, so `tpa`, the largest. The engine reads the `Texture`, `Gui`,
`DynMemRatio` and `Mem` columns, mounts `TEXTUREPACKS:<texture>` and `TEXTUREPACKS:<gui>` as ERF
group 2 into two fixed slots, and on a quality change unmounts the old slot first (*RE*). The three
packs hold the same 3,294 names (`tpa`/`tpb` differ in 2,724 of them, i.e. 570 are byte-identical);
the GUI pack's 1,570 names overlap none of them (*data*).

## Textures: TPC, TGA, TXI

A texture is requested by resref alone. The engine asks the resource manager which **class** of
source holds the name as `tpc`, `dds` (2033), `4pc` (2059) and `tga` (each answer is the class of
the best source for that type), and loads the **TPC** when its class ranks at least as high as the
best of the others, with the classes ranked **DIR > RIM > ERF > KEY**; otherwise it takes the
other path (TGA in practice) (*RE*). So:

- a TGA in `Override/` beats a TPC in a texture pack (DIR over ERF), the usual way texture mods
  are installed [1];
- within one class a TPC wins over a TGA (the community's "TPC shadows TGA in Override" [4]);
- this ranking is by class only, not by the full search order: it puts RIM above ERF even for
  `patch.erf`'s group 1, which the plain lookup searches first. No texture in the install is
  affected.

In the shipped data no texture name has both forms: area lightmaps are TGA + TXI in the
`lightmaps*.bif` archives (5,586 names), everything else is TPC in the packs (*data*). A `.txi`
resource of the same name supplies texture options; TPCs may also carry TXI text after their pixel
data ([txi.md](txi.md)).

## Streams

- **Voice-over** (*RE*, *data*): a VO resref that starts with `n` or `N`, is exactly 16
  characters and whose second character is not `_` (e.g. `NM13AABAST01059_`) lives at
  `streamwaves/<chars 2-6>/<chars 7-12>/<resref>.wav` (here `streamwaves/m13aa/bast01/`). Any other
  VO resref is `streamwaves/<resref>.wav` (format strings `HD0:STREAMWAVES\%s\%s\%s` and
  `HD0:STREAMWAVES\%s`). All 13,310 files in subfolders follow the rule; the 489 at the top level
  are cutscene VO and generic lines (`BA02CS001`, `N_GDUROS_COML1`) and one `_m40acdart03999_`.
  The lip file has the same resref, in `lips/<m>_loc.mod` or `lips/localization.mod`
  ([lip.md](lip.md)).
- **Music**: `streammusic/<name>.wav` (119 files), both a DIR source and opened by path
  (`HD0:STREAMMUSIC\%s`).
- **Ambient and creature sounds**: `streamsounds/<name>.wav` (970 files), opened by path
  (`HD0:STREAMSOUNDS\%s`); not a DIR source.
- **Movies**: `movies/<name>.bik` (61 files), `MOVIES:%s`.

These `.wav` files are MP3 data, with or without a 58-byte stub RIFF header
([inventory.md](inventory.md#audio)).

## rims/

`rims/` (12 files) mixes PC and Xbox leftovers. On PC the engine mounts `global.rim` always, and
`mainmenu.rim` / `chargen.rim` during the menu and character generation; it never mounts the
`*dx.rim` files or `miniglobal.rim`, and `legal.rim` / `subglobal.rim` are empty. Every entry is
also in chitin, byte-identical except the 13 NUL-separated 2DAs in `global.rim`/`miniglobal.rim`
(*data*). Our engine skips the folder (decision above).

## Open questions

- Whether a TGA found by the texture ranking above is loaded through the same resource search
  (it should be) and how `dds`/`4pc` are treated: no such files exist; RE of the TGA path when
  textures are implemented.
- How the engine writes `CURRENTGAME:` and `GAMEINPROGRESS:` when saving (stage 6).
- Type 3009 (`rsv`) is accepted as a RIM-form module save in `CURRENTGAME:`; no file uses it.

## Checked

`python kotor/tools/py/resources_probe.py` reads all 78,103 resource copies outside the save and
reports: name lengths (1-16, none longer) and characters; every resref + type present in two source
classes, with whether the bytes agree; names shared between modules; texture names by type and
source; the texture packs' name sets; and the streamwaves path rule. All *data* numbers above come
from it. Result: 78,103 resources, **0 name-rule failures**; 13,310 of 13,310 streamwaves files in
subfolders follow the path rule. The *RE* statements were read in the functions listed in
[../re/resman.md](../re/resman.md).

## Sources

1. Kexikus, *Folder priorities: Where to put your mod's files*, Deadly Stream, 2017:
   <https://deadlystream.com/topic/5329-folder-priorities-where-to-put-your-mods-files/>.
2. *.utc files*, LucasForums archive: <https://lucasforumsarchive.com/thread/178545-utc-files>.
3. *Creating a .mod file*, Deadly Stream: <https://deadlystream.com/topic/5648-creating-a-mod-file/>.
4. *Mod Installation Order and TGA vs. TPC files*, Deadly Stream:
   <https://deadlystream.com/topic/11056-mod-installation-order-and-tga-vs-tpc-files/>.
5. BioWare, *Key and BIF File Formats*, section 1.2 (the Aurora resource manager's source kinds):
   <https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/KeyBIF_Format.pdf>.
6. `swkotor.exe`, decompiled in `kotor/re/export` ([../re/resman.md](../re/resman.md)).
