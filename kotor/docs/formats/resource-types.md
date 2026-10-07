# Resource types

Every resource is named by a resref and a 16-bit **type id**. Containers store the id (KEY/BIF,
ERF, RIM); directories (`Override/`, the stream folders, saves) store an extension, which the engine
maps to the same id. A lookup is always by resref **and** type: `p_bastila.utc` and `p_bastila.ssf`
are unrelated.

The ids are BioWare's Aurora numbering (0-2999 and 9000-9999 reserved by BioWare, 0xFFFF invalid)
plus Odyssey's own 3000-3011. The table below is exactly the engine's own: `swkotor.exe` builds an
88-entry id/extension table at start-up (function 0x005e6d20 in the unpacked exe; see
[../re/resman.md](../re/resman.md)): the 87 types below plus 0xFFFF with an empty extension, which
is what an unknown extension maps to. The NWN types `ndb` (2064), `ptm` (2065), `ptt` (2066) and
`bak` (2067), listed by BioWare and by community tools, are **not** in it. Nothing in the install
uses an id outside it.

## Table

"Install" counts every copy in every container (chitin BIFs, the four texture packs, `modules/`,
`lips/`, `rims/`, `patch.erf`, the save), as found by `restypes_probe.py`. "Loose" marks types that
exist as plain files outside any container. Content: **GFF** = BioWare Generic File Format
([gff.md](gff.md)), with the 4-character GFF file type shown.

| Id | Ext | Content | Install | Where / notes |
|---:|---|---|---:|---|
| 0 | res | GFF (`INV `, `GVT `, `PT  `, `NFO `) | 4 | save data: `INVENTORY` inside SAVEGAME.sav; loose `GLOBALVARS.res`, `PARTYTABLE.res`, `savenfo.res` |
| 1 | bmp | Windows BMP | 0 | loose only in `launcher/`, not a game resource |
| 2 | mve | movie (unused) | 0 | |
| 3 | tga | Truevision TGA image | 5,602 | lightmaps (`lightmaps*.bif`), `textures.bif`, `legacy.bif`; a save's `Screen.tga` (loose) |
| 4 | wav | RIFF WAVE (PCM, IMA-ADPCM) | 2,303 | `sounds.bif`, `rims/global.rim`; loose in `streamwaves/`, `streamsounds/`, `streammusic/` (MP3 inside, see [inventory.md](inventory.md#audio)) |
| 6 | plt | NWN layered texture | 0 | |
| 7 | ini | INI text | 0 | loose `swkotor.ini` |
| 8 | mp3 | MP3 | 0 | (stream MP3s are named `.wav`) |
| 9 | mpg | MPEG video | 0 | |
| 10 | txt | text | 0 | |
| 11 | wma | Windows Media audio | 0 | |
| 12 | wmv | Windows Media video | 0 | |
| 13 | xmv | Xbox movie | 0 | |
| 14 | log | log file (in the engine's table only) | 0 | |
| 2000 | plh | (NWN, unused) | 0 | |
| 2001 | tex | (NWN, unused) | 0 | |
| 2002 | mdl | binary model | 3,072 | `models.bif`, `items.bif`, `party.bif`, `player.bif`; `rims/`; `patch.erf` |
| 2003 | thg | (unused) | 0 | |
| 2005 | fnt | font (unused; fonts are TPC + TXI) | 0 | |
| 2007 | lua | (unused) | 0 | |
| 2008 | slt | (unused) | 0 | |
| 2009 | nss | NWScript source, cp1252 text | 1,774 | `scripts.bif`, incl. `nwscript.nss` |
| 2010 | ncs | compiled NWScript (`NCS V1.0`) | 13,139 | `scripts.bif`, every `_s.rim`, `rims/` |
| 2011 | mod | ERF module archive ([erf.md](erf.md)) | — | the `.mod` files themselves |
| 2012 | are | GFF `ARE ` (static area) | 118 | every module `.rim`; the save |
| 2013 | set | NWN tileset (unused) | 0 | |
| 2014 | ifo | GFF `IFO ` (module info) | 118 | every module `.rim` (always `module.ifo`); the save |
| 2015 | bic | GFF `BIC ` (character) | 1 | `templates.bif` (`temp_char`) |
| 2016 | wok | walkmesh `BWM V1.0` (area room) | 1,202 | `models.bif` |
| 2017 | 2da | 2D table `2DA V2.b` ([2da.md](2da.md)) | 519 | `2da.bif`, `rims/`, `patch.erf` |
| 2018 | tlk | talk table `TLK V3.0` ([tlk.md](tlk.md)) | — | loose `dialog.tlk` |
| 2022 | txi | texture info, text ([txi.md](txi.md)) | 5,616 | next to every lightmap TGA; `textures.bif`; one in `templates.bif`, one in `swpc_tex_gui.erf` |
| 2023 | git | GFF `GIT ` (area instances) | 118 | every module `.rim`; the save |
| 2024 | bti | GFF `BTI ` (item blueprint, toolset) | 1 | `templates.bif` |
| 2025 | uti | GFF `UTI ` (item blueprint) | 1,055 | `templates.bif`, `_s.rim`, `rims/` |
| 2026 | btc | GFF `BTC ` (creature blueprint, toolset) | 3 | `templates.bif` |
| 2027 | utc | GFF `UTC ` (creature blueprint) | 1,959 | `templates.bif`, `_s.rim`, the save |
| 2029 | dlg | GFF `DLG ` (dialogue) | 1,167 | `_s.rim`, `templates.bif` |
| 2030 | itp | GFF `ITP ` (toolset palette) | 16 | `templates.bif` |
| 2031 | btt | GFF (trigger blueprint, toolset) | 0 | |
| 2032 | utt | GFF `UTT ` (trigger blueprint) | 1,121 | `_s.rim`, `templates.bif` |
| 2033 | dds | DirectDraw surface | 0 | |
| 2034 | bts | GFF (sound blueprint, toolset) | 0 | |
| 2035 | uts | GFF `UTS ` (sound blueprint) | 635 | `_s.rim` only |
| 2036 | ltr | name-generator letters `LTR V1.0` ([ltr.md](ltr.md)) | 3 | `templates.bif` |
| 2037 | gff | GFF, generic | 0 | |
| 2038 | fac | GFF `FAC ` (factions) | 21 | `_s.rim` (`repute.fac`); the save |
| 2039 | bte | GFF (encounter blueprint, toolset) | 0 | |
| 2040 | ute | GFF `UTE ` (encounter blueprint) | 133 | `_s.rim`, `templates.bif` |
| 2041 | btd | GFF (door blueprint, toolset) | 0 | |
| 2042 | utd | GFF `UTD ` (door blueprint) | 575 | `_s.rim`, `templates.bif` |
| 2043 | btp | GFF (placeable blueprint, toolset) | 0 | |
| 2044 | utp | GFF `UTP ` (placeable blueprint) | 1,784 | `_s.rim`, `templates.bif` |
| 2045 | dft | GFF (toolset defaults) | 0 | |
| 2046 | gic | GFF (toolset instance comments) | 0 | |
| 2047 | gui | GFF `GUI ` (GUI layout) | 91 | `gui.bif`, `patch.erf` |
| 2048 | css | (unused) | 0 | |
| 2049 | ccs | (unused) | 0 | |
| 2050 | btm | GFF (store blueprint, toolset) | 0 | |
| 2051 | utm | GFF `UTM ` (store blueprint) | 38 | `_s.rim` only |
| 2052 | dwk | walkmesh `BWM V1.0` (door) | 156 | `models.bif` |
| 2053 | pwk | walkmesh `BWM V1.0` (placeable) | 196 | `models.bif` |
| 2054 | btg | GFF (unused) | 0 | |
| 2055 | utg | GFF (unused) | 0 | |
| 2056 | jrl | GFF `JRL ` (journal) | 4 | `_newbif.bif` (`global.jrl`); `module.jrl` in three `_s.rim` |
| 2057 | sav | ERF, a module's saved state ([erf.md](erf.md)) | 1 | inside SAVEGAME.sav |
| 2058 | utw | GFF `UTW ` (waypoint blueprint) | 2,058 | `_s.rim`, `templates.bif` |
| 2059 | 4pc | (unused) | 0 | |
| 2060 | ssf | sound set `SSF V1.1` ([ssf.md](ssf.md)) | 316 | `templates.bif`, `rims/` |
| 2061 | hak | ERF hak pak (unused in KOTOR) | 0 | |
| 2062 | nwm | NWN module (unused) | 0 | |
| 2063 | bik | Bink video | — | loose `movies/*.bik` (61) |
| 3000 | lyt | area room layout, text ([lyt.md](lyt.md)) | 124 | `layouts.bif` |
| 3001 | vis | room visibility, text ([vis.md](vis.md)) | 112 | `lightmaps*.bif` |
| 3002 | rim | RIM archive ([rim.md](rim.md)) | — | the `.rim` files themselves |
| 3003 | pth | GFF `PTH ` (path graph, [pth.md](pth.md)) | 132 | `_s.rim` only |
| 3004 | lip | lip sync `LIP V1.0` ([lip.md](lip.md)) | 18,206 | `lips/*.mod` only |
| 3005 | bwm | walkmesh, generic (unused; files use wok/dwk/pwk) | 0 | |
| 3006 | txb | (Xbox texture, unused) | 0 | |
| 3007 | tpc | texture (no magic; 128-byte header, TXI appended) | 11,536 | the four texture packs, `patch.erf` |
| 3008 | mdx | model vertex data, no magic | 3,085 | beside every MDL |
| 3009 | rsv | module state kept by the loader (`<module>.rsv` is looked for before `.sav` and copied from GAMEINPROGRESS: to CURRENTGAME:; `SaveModuleIFO` deletes a stale one) | 0 | none in the install |
| 3010 | sig | (unused) | 0 | |
| 3011 | xbx | (Xbox, unused) | 0 | |
| 9997 | erf | ERF archive ([erf.md](erf.md)) | — | the `.erf` files themselves |
| 9998 | bif | BIF archive ([key-bif.md](key-bif.md)) | — | `data/*.bif` |
| 9999 | key | KEY index ([key-bif.md](key-bif.md)) | — | `chitin.key` |
| 0xFFFF | — | invalid | — | |

Not in the engine's table (so not resources to KOTOR): 2064 `ndb`, 2065 `ptm`, 2066 `ptt` (NWN
toolset files), 2067 `bak`.

## Ids that occur in the install (40)

0, 3, 4, 2002, 2009, 2010, 2012, 2014, 2015, 2016, 2017, 2022, 2023, 2024, 2025, 2026, 2027, 2029,
2030, 2032, 2035, 2036, 2038, 2040, 2042, 2044, 2047, 2051, 2052, 2053, 2056, 2057, 2058, 2060,
3000, 3001, 3003, 3004, 3007, 3008. Each was checked against its content (below).

Plus, as loose files only: `tlk` (`dialog.tlk`), `bik` (`movies/`), `key`, `bif`, `erf`, `mod`,
`rim`, `sav`, `res`, `tga`, `ini`.

## Content signatures

How to recognise each type from its bytes, as the probe does:

| Types | First bytes |
|---|---|
| all GFF types | 4-character file type (e.g. `UTC `) then `V3.2` |
| nss, txi, vis | printable text (nss is cp1252: seven scripts contain `©` or `’`) |
| lyt | text starting with a `#MAXLAYOUT` comment line, then `beginlayout` |
| ncs | `NCS V1.0` |
| wok, dwk, pwk | `BWM V1.0` |
| 2da | `2DA V2.b` |
| ltr | `LTR V1.0` |
| ssf | `SSF V1.1` |
| lip | `LIP V1.0` |
| sav | `MOD V1.0` (an ERF) |
| wav | `RIFF` |
| mdl | u32 0, then sizes (binary MDL) |
| tga, tpc, mdx | no magic |

## Extensions in directories

For `Override/` and the other directory sources the engine derives (resref, type) from each file
name when it mounts the directory (0x0040f200, 0x00406650, 0x004065a0):

- the resref is everything before the **first** `.`, cut to 16 characters (a longer stem is
  truncated, not rejected); a name with no `.` or starting with `.` is skipped;
- the type is the **three characters after the first `.`**, matched ASCII case-insensitively
  against the table above; an unknown extension maps to 0xFFFF and the file is skipped. So
  `foo.tga.bak` registers as `foo.tga`, and `a.b.tpc` as `a` with the unknown extension `b.t`;
- subfolders are not scanned.

## Checked

`python kotor/tools/py/restypes_probe.py` classifies all 78,114 resource copies in the install by
their leading bytes and checks each against the expected content of its type id (table above).
Result: 40 type ids, 78,114 resources, **0 mismatches**. When `kotor/re` holds the decompiled
export, the probe also reads the engine's table out of function 0x005e6d20 and compares it with
`kres.TYPES` (this document's table): all 87 engine types agree; the only differences are the four
NWN ids `kres` keeps and the engine lacks.

## Sources

- BioWare, *Key and BIF File Formats*, table 1.3.1 (ids 1-2066):
  <https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/KeyBIF_Format.pdf>.
- Odyssey ids 3000-3011 and 9997-9999: common to the KOTOR modding community's tools and
  documentation, and confirmed here by the exe's table and by the data.
- `swkotor.exe` (unpacked): the type table built at 0x005e6d20, and the directory scan above.
