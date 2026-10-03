# Inventory of the install

What the Steam install at `F:\Steam\steamapps\common\swkotor` contains, as measured by
`inventory_probe.py` (see [Checked](#checked)). How resources are found is in
[resources.md](resources.md); type ids in [resource-types.md](resource-types.md).

## Top level

| Path | Files | Size | What |
|---|---:|---:|---|
| `chitin.key` | 1 | 0.6 MB | index of the BIFs ([key-bif.md](key-bif.md)) |
| `data/*.bif` | 26 | 1,316 MB | the bulk of the game: 25,836 resources |
| `TexturePacks/*.erf` | 4 | 672 MB | textures at three qualities + GUI textures ([erf.md](erf.md)) |
| `modules/*.rim` | 234 | 73 MB | 117 modules, two RIMs each ([rim.md](rim.md)) |
| `lips/*.mod` | 123 | 6 MB | lip-sync files per module ([lip.md](lip.md)) |
| `rims/*.rim` | 12 | 39 MB | `global`, `mainmenu`, `chargen` mounted on PC, the rest Xbox leftovers; all duplicated in chitin |
| `patch.erf` | 1 | 7 MB | 97 patched resources |
| `dialog.tlk` | 1 | 5 MB | all game text ([tlk.md](tlk.md)) |
| `streamwaves/` | 13,799 | 548 MB | voice-over |
| `streamsounds/` | 970 | 118 MB | barks and ambient sounds |
| `streammusic/` | 119 | 200 MB | music |
| `movies/*.bik` | 61 | 606 MB | Bink videos |
| `Override/` | 0 | | empty: no mods installed |
| `Saves/` | 1 save | 0.8 MB | see [Saves](#saves) |
| `swkotor.exe` | 1 | 4.4 MB | the game; its `.text` section is encrypted by Steam's DRM wrapper (SteamStub, a `.bind` section); the RE pipeline works on an unpacked copy in `kotor/re/bin/` |
| `swkotor.ini` | 1 | | settings, see [swkotor.ini](#swkotorini) |
| `swconfig.exe`, `swupdate.exe`, `launcher/`, `utils/` | | | configuration tool, updater, launcher (bitmaps, `launcher.ini` with TLK strrefs 48269-48460) |
| `Mss32.dll`, `miles/`, `binkw32.dll`, `Patchw32.dll` | | | Miles Sound System and its providers (incl. `mssmp3.asi`), Bink, patch DLL |
| `logs/` | 0 | | empty |
| `32370_install.vdf` | 1 | | Steam metadata |

There is no `dialogf.tlk`, no `hak/`, no `currentgame/` or `temp/` directory (the engine creates
those it needs), and no `modules/*.mod`.

## Resources by container

78,114 copies of 58,138 distinct resref + type pairs (every copy in every container, the save
included).

| Container | Entries | Types |
|---|---:|---|
| `data/models.bif` | 6,444 | mdl 2,445, mdx 2,445, wok 1,202, pwk 196, dwk 156 |
| `data/scripts.bif` | 3,558 | ncs 1,784, nss 1,774 (incl. `nwscript.nss`) |
| `data/sounds.bif` | 1,928 | wav 1,928 |
| `data/templates.bif` | 1,387 | uti 557, utp 317, utc 205, ssf 106, ute 65, utd 50, dlg 32, utt 21, itp 16, utw 9, ltr 3, btc 3, txi 1, bti 1, bic 1 |
| `data/lightmaps*.bif` (13) | 11,284 | tga 5,586, txi 5,586, vis 112 |
| `data/items.bif` | 610 | mdl 305, mdx 305 |
| `data/2da.bif` | 209 | 2da 209 |
| `data/player.bif` | 126 | mdl 63, mdx 63 |
| `data/layouts.bif` | 124 | lyt 124 |
| `data/gui.bif` | 84 | gui 84 |
| `data/textures.bif` | 42 | txi 28, tga 14 |
| `data/party.bif` | 38 | mdl 19, mdx 19 |
| `data/legacy.bif`, `data/_newbif.bif` | 1 + 1 | `chrome1.tga`; `global.jrl` |
| `TexturePacks/swpc_tex_tpa.erf`, `_tpb`, `_tpc` | 3,294 each | tpc |
| `TexturePacks/swpc_tex_gui.erf` | 1,571 | tpc 1,570, txi 1 |
| `modules/<m>.rim` (117) | 351 | are, git, ifo: one each |
| `modules/<m>_s.rim` (117) | 20,224 | ncs 10,863, utw 2,049, utc 1,753, utp 1,467, dlg 1,135, utt 1,100, uts 635, utd 525, uti 436, pth 132, ute 68, utm 38, fac 20, jrl 3 |
| `lips/<m>_loc.mod` (117) | 15,610 | lip |
| `lips/localization.mod` | 2,596 | lip |
| `lips/global, legal, mainmenu, miniglobal, subglobal .mod` | 0 | empty |
| `rims/global.rim` | 949 | ncs 246, wav 246, mdl 168, 2da 153, ssf 105, uti 31 |
| `rims/miniglobal.rim` | 704 | ncs 246, 2da 153, wav 129, ssf 105, mdl 40, uti 31 |
| `rims/globaldx`, `miniglobaldx`, `chargen(dx)`, `mainmenu(dx)` | 283 | mdl in the plain RIM, mdx in its `dx` twin |
| `rims/legal(dx)`, `subglobal(dx)` | 0 | empty |
| `patch.erf` | 97 | tpc 84, gui 7, 2da 4, mdl 1, mdx 1 |
| the save | 11 | see [Saves](#saves) |

By type (every copy): lip 18,206; ncs 13,139; tpc 11,536; txi 5,616; tga 5,602; mdx 3,085; mdl
3,072; wav 2,303; utw 2,058; utc 1,959; utp 1,784; nss 1,774; wok 1,202; dlg 1,167; utt 1,121; uti
1,055; uts 635; utd 575; 2da 519; ssf 316; pwk 196; dwk 156; ute 133; pth 132; lyt 124; are 118;
git 118; ifo 118; vis 112; gui 91; utm 38; fac 21; itp 16; jrl 4; res 4; ltr 3; btc 3; bti 1;
bic 1; sav 1.

Where things are **not**: area room models, walkmeshes, `.lyt` and `.vis` are in chitin
(`models.bif`, `layouts.bif`, `lightmaps*.bif`) keyed by the *area* resref, not in the module RIMs.
All non-lightmap textures are TPCs in the texture packs; chitin holds no TPC at all.

## Modules

117 modules. Each one is exactly three files:

- `modules/<m>.rim`: `<area>.are`, `<area>.git`, `module.ifo` (`Mod_Entry_Area` = `<area>` in all
  117);
- `modules/<m>_s.rim`: the module's scripts, blueprints, dialogues, factions (`repute.fac`, 20
  modules), journal (3 modules) and path graphs: `<area>.pth` in 107 modules, plus extra PTHs of
  other areas in 10 (`danm14ab_s.rim` carries `m14ab`, `m14aa` and `e3_m21aa`; `sta_m45ac_s.rim`
  carries `m01aa`, `m45ac`, `m45gen`), 132 in all; the engine needs the one named after the area;
- `lips/<m>_loc.mod`: its lip files (empty for 9 modules).

File names are mixed case (`M12ab`, `STUNT_00`, `danm13`). Module name and area resref differ, and
**several modules share an area**: the Ebon Hawk (`ebo_m12aa`, `ebo_m40aa`, `ebo_m40ad`,
`ebo_m41aa` all use area `m12aa`), the cutscene `STUNT_*` modules, `tat_m17ag` (Czerka Office) uses
`m17ae`, and `korr_m38aa`/`korr_m38ab` use `m38ab`/`m38aa` (crossed). Prefixes are planets:
`end` Endar Spire, `tar` Taris, `danm` Dantooine, `ebo` Ebon Hawk, `kas` Kashyyyk, `tat` Tatooine,
`manm` Manaan, `korr` Korriban, `lev` Leviathan, `unk` Unknown World, `sta` Star Forge, `liv` Yavin
Station (Xbox Live content shipped on PC), `STUNT` cutscenes, `M12ab` Ebon Hawk turret minigame,
`*mg` swoop tracks.

| Module | Area | Name (ARE `Name`) | `_s.rim` entries | lips |
|---|---|---|---:|---:|
| danm13 | m13aa | Dantooine - Jedi Enclave | 461 | 946 |
| danm14aa | m14aa | Dantooine - Courtyard | 221 | 270 |
| danm14ab | m14ab | Dantooine - Matale Grounds | 177 | 63 |
| danm14ac | m14ac | Dantooine - Grove | 209 | 201 |
| danm14ad | m14ad | Dantooine - Sandral Grounds | 183 | 217 |
| danm14ae | m14ae | Dantooine - Crystal Cave | 56 | 0 |
| danm15 | m15aa | Dantooine - Ruins | 111 | 39 |
| danm16 | m16aa | Dantooine - Sandral Estate | 216 | 99 |
| ebo_m12aa | m12aa | Ebon Hawk | 318 | 77 |
| ebo_m40aa | m12aa | Ebon Hawk | 30 | 39 |
| ebo_m40ad | m12aa | Ebon Hawk | 116 | 99 |
| ebo_m41aa | m12aa | Ebon Hawk | 217 | 37 |
| ebo_m46ab | m46aa | Prison | 31 | 24 |
| end_m01aa | m01aa | Endar Spire - Command Module | 368 | 81 |
| end_m01ab | m01ab | Endar Spire - Starboard Section | 150 | 12 |
| kas_m22aa | m22aa | Kashyyyk - Czerka Landing Port | 287 | 471 |
| kas_m22ab | m22ab | Kashyyyk - The Great Walkway | 236 | 119 |
| kas_m23aa | m23aa | Kashyyyk - Village of Rwookrrorro | 57 | 31 |
| kas_m23ab | m23ab | Kashyyyk - Woorwill's Home | 25 | 33 |
| kas_m23ac | m23ac | Kashyyyk - Worrroznor's Home | 23 | 35 |
| kas_m23ad | m23ad | Kashyyyk - Hall of the Chieftain | 77 | 79 |
| kas_m24aa | m24aa | Kashyyyk - Upper Shadowlands | 351 | 263 |
| kas_m25aa | m25aa | Kashyyyk - Lower Shadowlands | 220 | 222 |
| korr_m33aa | m33aa | Korriban - Dreshdae | 422 | 764 |
| korr_m33ab | m33ab | Korriban - Sith Academy Entrance | 86 | 103 |
| korr_m34aa | m34aa | Korriban - Shyrack Caves | 184 | 27 |
| korr_m35aa | m35aa | Korriban - Sith Academy | 513 | 706 |
| korr_m36aa | m36aa | Korriban - Valley of Dark Lords | 217 | 161 |
| korr_m37aa | m37aa | Korriban - Tomb of Ajunta Pall | 179 | 86 |
| korr_m38aa | m38ab | Korriban - Tomb of Marka Ragnos | 97 | 69 |
| korr_m38ab | m38aa | Korriban - Tomb of Tulak Hord | 154 | 102 |
| korr_m39aa | m39aa | Korriban - Tomb of Naga Sadow | 313 | 157 |
| lev_m40aa | m40aa | Leviathan - Prison Block | 382 | 236 |
| lev_m40ab | m40ab | Leviathan - Command Deck | 245 | 24 |
| lev_m40ac | m40ac | Leviathan - Hangar | 193 | 57 |
| lev_m40ad | m40ad | Leviathan - Bridge | 93 | 24 |
| liv_m99aa | m50aa | Yavin Station | 187 | 27 |
| M12ab | m12ab | Ebon Hawk - Turret | 14 | 0 |
| manm26aa | m26aa | Manaan - Ahto West | 250 | 515 |
| manm26ab | m26ab | Manaan - Ahto East | 233 | 300 |
| manm26ac | m26ac | Manaan - West Central | 195 | 110 |
| manm26ad | m26ad | Manaan - Docking Bay | 245 | 289 |
| manm26ae | m26ae | Manaan - East Central | 359 | 384 |
| manm26mg | m26mg | Manaan - Swoop Track | 23 | 0 |
| manm27aa | m27aa | Manaan - Sith Base | 398 | 46 |
| manm28aa | m28aa | Manaan - Hrakert Station | 270 | 60 |
| manm28ab | m28ab | Manaan - Sea Floor | 86 | 85 |
| manm28ac | m28ac | Manaan - Kolto Control | 91 | 129 |
| manm28ad | m28ad | Manaan - Hrakert Rift | 87 | 0 |
| sta_m45aa | m45aa | Star Forge - Deck 1 | 263 | 71 |
| sta_m45ab | m45ab | Star Forge - Deck 2 | 123 | 10 |
| sta_m45ac | m45ac | Star Forge - Command Center | 366 | 102 |
| sta_m45ad | m45ad | Star Forge - Viewing Platform | 170 | 35 |
| STUNT_00 | stunt_eboqrts | Untitled | 13 | 0 |
| STUNT_03a | stunt_levbridge | m40ad | 14 | 7 |
| STUNT_06 | stunt_levbridge | m40ad | 21 | 2 |
| STUNT_07 | stunt_ebodant | Untitled | 6 | 347 |
| STUNT_12 | m40ad | Untitled | 51 | 15 |
| STUNT_14 | m40ad | Untitled | 46 | 7 |
| STUNT_16 | stunt_ebolev | Untitled | 7 | 399 |
| STUNT_18 | stunt_unkhall | Untitled | 9 | 353 |
| STUNT_19 | stunt_starforge | Untitled | 25 | 3 |
| STUNT_31b | m44ad | Untitled | 10 | 0 |
| STUNT_34 | stunt_ebosf | Untitled | 8 | 4 |
| STUNT_35 | stunt_ebocrash | Untitled | 5 | 2 |
| STUNT_42 | stunt_ebocom | M12aa | 7 | 361 |
| STUNT_44 | stunt_ebocom | M12aa | 12 | 21 |
| STUNT_50a | stunt_endbridge | Untitled | 10 | 2 |
| STUNT_51a | stunt_endbridge | Untitled | 19 | 7 |
| STUNT_54a | stunt_endbridge | Untitled | 16 | 3 |
| STUNT_55a | stunt_unktemp | Untitled | 21 | 398 |
| STUNT_56a | stunt_endbridge | Untitled | 23 | 4 |
| STUNT_57 | stunt_unkramp | Untitled | 45 | 348 |
| tar_m02aa | m02aa | Taris - South Apartments | 256 | 197 |
| tar_m02ab | m02ab | Taris - Upper City North | 308 | 190 |
| tar_m02ac | m02ac | Taris - Upper City South | 267 | 225 |
| tar_m02ad | m02ad | Taris - North Apartments | 206 | 189 |
| tar_m02ae | m02ae | Taris - Upper City Cantina | 427 | 538 |
| tar_m02af | m02af | Taris - Hideout | 41 | 84 |
| tar_m03aa | m03aa | Taris - Lower City | 473 | 113 |
| tar_m03ab | m03ab | Taris - Lower City Apartments | 401 | 37 |
| tar_m03ad | m03ad | Taris - Lower City Apartments | 395 | 45 |
| tar_m03ae | m03ae | Taris - Javyar's Cantina | 237 | 254 |
| tar_m03af | m03af | Taris - Swoop Platform | 96 | 63 |
| tar_m03mg | m03mg | Taris - Swoop Track | 25 | 0 |
| tar_m04aa | m04aa | Taris - Undercity | 426 | 368 |
| tar_m05aa | m05aa | Taris - Lower Sewers | 171 | 46 |
| tar_m05ab | m05ab | Taris - Upper Sewers | 89 | 0 |
| tar_m08aa | m08aa | Taris - Davik's Estate | 231 | 132 |
| tar_m09aa | m09aa | Taris - Sith Base | 182 | 21 |
| tar_m09ab | m09ab | Taris - Sith Base | 16 | 6 |
| tar_m10aa | m10aa | Taris - Black Vulkar Base | 464 | 30 |
| tar_m10ab | m10ab | Taris - Black Vulkar Base | 410 | 53 |
| tar_m10ac | m10ac | Taris - Black Vulkar Base | 450 | 28 |
| tar_m11aa | m11aa | Taris - Hidden Bek Base | 120 | 130 |
| tar_m11ab | m11ab | Taris - Hidden Bek Base | 18 | 6 |
| tat_m17aa | m17aa | Tatooine - Anchorhead | 207 | 484 |
| tat_m17ab | m17ab | Tatooine - Docking Bay | 104 | 342 |
| tat_m17ac | m17ac | Tatooine - Droid Shop | 55 | 67 |
| tat_m17ad | m17ad | Tatooine - Hunting Lodge | 99 | 159 |
| tat_m17ae | m17ae | Tatooine - Swoop Registration | 163 | 214 |
| tat_m17af | m17af | Tatooine - Cantina | 83 | 248 |
| tat_m17ag | m17ae | Tatooine - Czerka Office | 63 | 144 |
| tat_m17mg | m17mg | Tatooine - Swoop Track | 25 | 0 |
| tat_m18aa | m18aa | Tatooine - Dune Sea | 363 | 219 |
| tat_m18ab | m18ab | Tatooine - Sand People Territory | 171 | 13 |
| tat_m18ac | m18ac | Tatooine - Eastern Dune Sea | 267 | 55 |
| tat_m20aa | m20aa | Tatooine - Sand People Enclave | 175 | 208 |
| unk_m41aa | m41aa | Unknown World - Central Beach | 264 | 102 |
| unk_m41ab | m41ab | Unknown World - South Beach | 154 | 4 |
| unk_m41ac | m41ac | Unknown World - North Beach | 158 | 21 |
| unk_m41ad | m41ad | Unknown World - Temple Exterior | 246 | 25 |
| unk_m42aa | m42aa | Unknown World - Elder Settlement | 235 | 25 |
| unk_m43aa | m43aa | Unknown World - Rakatan Settlement | 193 | 24 |
| unk_m44aa | m44aa | Unknown World - Temple Main Floor | 317 | 9 |
| unk_m44ab | m44ab | Unknown World - Temple Catacombs | 95 | 8 |
| unk_m44ac | m44ac | Unknown World - Temple Summit | 132 | 65 |

The main menu and character generation are not modules in `modules/`; their models are in chitin
(and in `rims/mainmenu.rim`, `rims/chargen.rim`).

## Texture packs

`TexturePacks/` holds `swpc_tex_tpa.erf` (400 MB), `swpc_tex_tpb.erf` (116 MB) and
`swpc_tex_tpc.erf` (45 MB), the same 3,294 TPC names at decreasing quality (2,724 of them differ
between packs; 570 are byte-identical small textures), and `swpc_tex_gui.erf` (112 MB, 1,570 GUI
TPCs + one TXI) used at every quality. `texpacks.2da` row = `Texture Quality` picks the pack
([resources.md](resources.md#texture-packs)). `patch.erf` replaces 75 of the pack textures
(the 15 female player heads `pfha01`..`pfhc05`, each with its `d`, `d1`-`d3` variants) and adds 9
new TPCs (seven 1280x1024 GUI backgrounds, two cycle arrows).

## patch.erf

97 resources, built 2004 (day 47): newer `keymap.2da`, `bindablekeys.2da`, `skills.2da`,
`weapondischarge.2da`; GUIs `abilities`, `character`, `equip`, `inventory`, `mainmenu` plus new
`mipc212x10` and `tooltip12x10`; `w_lghtsbr_008.mdl/.mdx`; 84 TPCs (above). Every non-texture
resource in it except `mipc212x10.gui` and `tooltip12x10.gui` replaces a chitin resource.

## Audio

| Where | Files | Encoding |
|---|---:|---|
| `sounds.bif`, `rims/` (`.wav` resources) | 2,303 | genuine RIFF WAVE: 16-bit PCM mono 22,050 Hz (2,192), 44,100 Hz (84), 11,025 Hz (9), stereo (9), 8-bit (1), IMA-ADPCM mono 44,100 Hz (8); 112 have extra chunks after `data` |
| `streamwaves/` | 13,799 | MP3 behind a **58-byte stub RIFF header** (`fmt` says 8-bit PCM mono 22,050 Hz, a 4-byte `fact`, then a `data` chunk of size 0); the MP3 stream (frame sync `FF FB`, 3 files start with `ID3`) follows to the end of the file |
| `streammusic/` | 119 | 68 with the same 58-byte stub then MP3; 51 raw MP3 (`FF F3`, MPEG-2 layer III) with a `.wav` name |
| `streamsounds/` | 970 | all raw MP3 with a `.wav` name |

So a WAV reader must sniff: `RIFF` with a zero-size `data` chunk followed by MP3 bytes is MP3;
no `RIFF` at all is MP3. Details for the audio agent: the stub's RIFF size field is 50 (= the
header minus 8), so the RIFF size does not cover the MP3.

Naming:

- `streamwaves/<area>/<conv>/N<area><conv><nnn>_.wav` (13,310 files, 81 area folders such as
  `m13aa`, `globe`, `stn12`): conversation VO, path derived from the 16-character resref
  ([resources.md](resources.md#streams)). The VO folder is the *dialogue's* area code, which need
  not be the module's area.
- `streamwaves/*.wav` (489 files): cutscene VO (`BA02CS001`, `MA18CS006A`, `MI41CS001`), generic
  NPC lines (`N_GDUROS_COML1`, `n_...`), and one stray `_m40acdart03999_.wav`.
- `streamsounds/`: party and NPC combat barks (`P_CARTH_ATK1`, `N_BITH_DEAD`, `c_...`), ambient
  loops (`al_*`), stingers (`mu*`), minigame sounds (`mg*`).
- `streammusic/`: cutscene music by movie number (`01b`, `03a`, ...), ambient beds (`al_*`), area,
  battle and theme music (`mus_area_*`, `mus_bat_*`, `mus_theme_*`), `mus_loadscreen`, `credits`,
  `evil_ending`.

## Movies

`movies/`: 61 Bink files (606 MB): `biologo`, `leclogo`, `legal`, numbered cutscenes `01a` ..
`56b`, `LIVE_1a`, `Live_1c` (Yavin Station). Decoding is stage 1 ([PLAN.md](../../PLAN.md)).

## Lips

`lips/`: 117 `<m>_loc.mod` (15,610 LIPs), `localization.mod` (2,596 LIPs shared across modules:
`globe` lines and lines from `m35aa`, `m13aa`, `m33ab`, ...; 1,062 of them also sit, identical, in a
module `_loc.mod`), and five empty MODs (`global`, `legal`, `mainmenu`, `miniglobal`,
`subglobal`). 9 module `_loc.mod` files are empty. LIP resrefs equal VO resrefs ([lip.md](lip.md)).

## rims/

Twelve RIMs, all content duplicated in chitin. The PC engine mounts `global.rim` always and
`mainmenu.rim` / `chargen.rim` during the menu and character generation; `miniglobal.rim` and the
`*dx.rim` files (the MDX halves of the models in their plain twins) are Xbox leftovers it never
mounts. See [resources.md](resources.md#rims).

## Saves

`Saves/` holds one slot, `000002 - Game1/` (the folder name is `%06d - <name>`), and Steam's
`steam_autocloud.vdf`. The slot, read-only here:

| File | Size | Format | Contents |
|---|---:|---|---|
| `savenfo.res` | 677 | GFF `NFO ` | load-menu info: `AREANAME`, `LASTMODULE`, `TIMEPLAYED`, `SAVEGAMENAME`, `CHEATUSED`, hints, `PORTRAIT0..`, `LIVE1..6`, `LIVECONTENT` |
| `GLOBALVARS.res` | 57,656 | GFF `GVT ` | script globals: `CatBoolean`/`ValBoolean`, `CatNumber`/`ValNumber`, `CatLocation`/`ValLocation`, `CatString`/`ValString` |
| `PARTYTABLE.res` | 18,152 | GFF `PT  ` | party: `PT_GOLD`, `PT_XP_POOL`, `PT_MEMBERS`, `PT_AVAIL_NPCS`, pazaak cards, galaxy map, journal entries, message logs, ... |
| `SAVEGAME.sav` | 532,862 | ERF `MOD V1.0` | `AVAILNPC0.utc`, `END_M01AA.sav` (nested ERF: `m01aa.git`, `m01aa.are`, `Module.ifo`), `INVENTORY.res` (GFF `INV `: `ItemList`), `REPUTE.fac` |
| `Screen.tga` | 196,626 | TGA | 256 x 256, 24-bit, uncompressed, bottom-up: the load-menu thumbnail |

The save is from the start of the game (Endar Spire); file dates are 2023. ERF details are in
[erf.md](erf.md#saved-games), GFF in [gff.md](gff.md).

## swkotor.ini

Keys that matter to a reimplementation (this install's values):

- `[Graphics Options]`: `Texture Quality=2` (texpacks.2da row: tpa), `FullScreen=1`,
  `Anti Aliasing=0`, `Anisotropy=1`, `Shadows=1`, `Soft Shadows=0`, `Grass=1`, `Emitters=1`,
  `Brightness=57`, `V-Sync=0`, `Frame Buffer=1`, `EnableHardwareMouse=1`,
  `Disable Vertex Buffer Objects=1`. No resolution keys are present (defaults apply).
- `[Sound Options]`: `Music/Voiceover/Sound Effects Volume=85`, `Movie Volume=100`, EAX and
  environment-effect settings, voice counts (`Number 3D Voices=16`, `Number 2D Voices=24`).
- `[Game Options]`: `Difficulty Level=1`, `Subtitles=1`, `AutoSave=1`, `Mouse Sensitivity=33`,
  `Mini Map=1`, `Tutorial Popups=1`, `Combat Movement=1`, `Hide InGame GUI=0`, keyboard camera
  speeds, autopause settings in `[Autopause Options]`.
- `[Alias]`: logical drives for the resource system: `HD0=.\`, `OVERRIDE=.\Override`,
  `MODULES=.\Modules`, `SAVES=.\saves`, `STREAMMUSIC`, `STREAMWAVES`, `TEXTUREPACKS`, `TEMP`,
  `CURRENTGAME=.\currentgame`, `LOGS`, plus NWN leftovers (`LOCALVAULT`, `DMVAULT`,
  `SERVERVAULT`, `TEMPCLIENT`). The exe has built-in defaults for these and more (`LIPS`, `RIMS`,
  `MOVIES`, `STREAMSOUNDS`, `PATCH`, `HAK`, `ERRORTEX`, `PORTRAITS`, ...).
- `[Movies Shown]`: `Movie 0..10`, which intro movies were already watched.
- `[Keymapping]`: `ActionNNN[A|B]=scancode`, indexes into `keymap.2da`/`bindablekeys.2da`.

## Surprising things

- The shipped exe's code is encrypted (SteamStub); RE works on an unpacked copy.
- Stream `.wav` files are MP3, behind a fake 58-byte RIFF header or with none at all.
- The engine writes saves with the `MOD ` signature, and an ERF nested inside an ERF.
- ERF headers' `DescriptionStrRef` is garbage in shipped files.
- `rims/` duplicates chitin, the engine still mounts `global.rim` above chitin, and 13 of its 2DAs
  have NULs where tabs belong (the engine's parser copes).
- Modules share areas, and two Korriban modules use each other's area numbers.
- Lightmaps are TGA in BIFs while every other texture is TPC in the packs.
- A texture literally named `lma_tech01 copy` ships in all three packs.

## Checked

`python kotor/tools/py/inventory_probe.py` (read-only) produces every number in this file: counts
by container and type over all 78,114 copies (via `kres.Game().every_entry()`), directory sizes,
WAV encodings of all 14,888 stream files and 2,303 WAV resources, the root and save files, and the
module table (area from each module RIM, name from the ARE's `Name` via `dialog.tlk`,
`Mod_Entry_Area` checked equal to the area resref for all 117).
