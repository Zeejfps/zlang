# 2DA catalog: every table in the install

This file lists every 2DA table KOTOR ships, what each column holds, and which other tables,
resources and strings each column points at. The container format (how a `2DA V2.b` file is laid out)
is in [2da.md](2da.md); this file is about the tables' contents.

Everything here was produced and checked by `kotor/tools/py/twoda_catalog.py` (see
[Checked](#checked)). Its raw output, with a value profile and samples for every column of every
table, is in `kotor/extract/2da-inventory.txt` and `.json` (git-ignored; regenerate with the probe).

## Conventions

**Status of each meaning.** Every column meaning carries one of these marks:

| Mark | Meaning |
|---|---|
| **C:BW** | Stated by BioWare's published Aurora documents for *Neverwinter Nights* (the same engine family), and the KOTOR data agrees with it. |
| **C:DS** | Stated by the Deadly Stream 2DA reference written by KOTOR modders. |
| **C:nss** | Stated or implied by `nwscript.nss` from the install (comments, or constants whose values land on the matching row). |
| **C:data** | Shown by the data itself: a probe check in [Checked](#checked) (strrefs resolve to matching text, resrefs exist as the expected resource type, indices land in range and on rows with matching names). |
| *I* | Inferred from the column name and the values. Treat as a hypothesis until RE or play confirms it. |
| unused | Empty (`****`) in every row, or points at nothing that exists in the install. |

Sources:

- [BW-CRE] BioWare, *Aurora Engine Creature Format* (appearance, racialtypes, classes, cls_*, feat, masterfeats, skills, spells, domains, portraits, gender, ranges, creaturespeed, creaturesize, footstepsounds, phenotype, fractionalcr, hen_*): <https://nwn.wiki/download/attachments/327727/Bioware_Aurora_Creature_Format.pdf>
- [BW-ITM] BioWare, *Item Format* (baseitems, itempropdef, itemprops, iprp_* subtype/cost/param tables, item icon and model naming): <https://nwn.wiki/download/attachments/327727/Bioware_Aurora_Item_Format.pdf>
- [BW-DP] BioWare, *Door/Placeable GFF* (placeables, placeableobjsnds, bodybag, doortypes, genericdoors): <https://nwn.wiki/download/attachments/327727/Bioware_Aurora_DoorPlaceableGFF.pdf>
- [BW-ARE] BioWare, *Area File Format* (environment, loadscreens, pvpsettings, lightcolor, ambientsound, ambientmusic, soundeax): <https://nwn.wiki/download/attachments/327727/Bioware_Aurora_AreaFile_Format.pdf>
- [BW-ENC] *Encounter Format* (encdifficulty), [BW-TRG] *Trigger Format* (cursors, traps, placeabletypes), [BW-FAC] *Faction Format* (repute, repadjust), [BW-WP] *Waypoint Format* (waypoint): same site, `Bioware_Aurora_Encounter_Format.pdf`, `..._Trigger_Format.pdf`, `..._Faction_Format.pdf`, `..._Waypoint_Format.pdf`.
- [DS] Deadly Stream, *Detailed information of 2da files*: <https://deadlystream.com/topic/4725-detailed-information-of-2da-files/>
- [NSS] `nwscript.nss` in `data/scripts.bif`.

**Cells.** A cell is a string. `****` (and an empty string) means "no value". Numbers are decimal
integers, decimal floats (`1.5`, `2.0`), or hex with a `0x` prefix (`baseitems.equipableslots`,
`feat.category`, `spells.category`, `classes.alignrestrict`). One table mixes them in a column:
`exptable.xp` ends with `0xFFFFFFFF`. A reader should parse numbers on demand and treat `****` as
absent. `keymap` also uses `*****` (five stars) for "no strref".

**Row index or row label.** Most tables are indexed by row position (GFF fields and other tables
store the row number). A few are keyed by the **row label** instead, and the reader must offer
lookup by label:

| Table | Row labels | Who looks them up |
|---|---|---|
| visualeffects | VFX ids 1001..8002 | `VFX_*` constants in nwscript.nss equal the labels (C:nss, 115/118); appearance.deathvfx and forceshields.visualeffect* hold labels (C:data) |
| weapondischarge | `<anim>` or `<appearance>_<anim>`, e.g. `217`, `3_217`, `56_288` | animation row (animations.2da) optionally prefixed with an appearance row (C:data, *I* for the lookup) |
| combatanimations | animations.2da rows of attack animations (87, 88, 94, ...) | C:data 58/58 |
| droiddischarge | model names (`c_drdassassin`, ...) = appearance.race | C:data 15/15 |
| loadscreens, modulesave | module resrefs (`default`, `classsel`, `danm13`, ...) | *I*: lookup by destination module name |
| movies | movie names (`01a`, `08`, `live_11`, ...) = `movies/*.bik` | C:data 55/107 exist |
| plot | plot ids (`kor33_shaardan`, ...) | `GivePlotXP(sPlotName, ...)` in nwscript (*I*) |
| keymap, bindablekeys | `action200`.., `key0`.. | *I* |
| swingsounds, dialogtokens | names / `<abutton>`-style tokens | *I* |

Some numeric labels are not `0..n-1`, so index and label lookups give different rows:
ambientsound (label 17 missing; rows 17+ are labelled one higher), environment (21 missing),
effecticon (rows 56..61 labelled 57, 59, 61, 63, 63, 63), iprp_resistcost (two rows labelled `0`),
categories, stringtokens, visemes and iprp_spellcost (labels start at 1). Which lookup the engine
uses for these is not established; every GFF value seen fits row indexing (see the GFF checks).

## Where the tables live

| Container | 2DA entries | Notes |
|---|---|---|
| `data/2da.bif` (via chitin.key) | 209 | every table |
| `rims/global.rim` | 153 | same cells as the BIF copy; 13 of them (appearance, appearancesndset, baseitems, bodybag, doortypes, genericdoors, heads, inventorysnds, placeableobjsnds, placeables, portraits, soundset, traps) end every column and row label with NUL instead of tab, see [2da.md](2da.md) |
| `rims/miniglobal.rim` | 153 | identical to global.rim's copies, byte for byte |
| `patch.erf` | 4 | newer versions of bindablekeys, keymap, skills, weapondischarge (below) |
| `Override/` | 0 | empty in this install |
| saves | 0 | no 2DA inside any save |

519 entries, 209 distinct tables. The exe names both extra sources: the strings `RIMS:GLOBAL` and
`HD0:patch` appear in `swkotor.exe`, so both are loaded (*I* from the strings; the search order
between BIF, global.rim and patch.erf is not established here; patch.erf presumably wins, being the
post-release update). Note that `kres.Game.entries()`/`get()` do not include `patch.erf`; probes
that want the patched tables must use `every_entry()` (as `twoda_catalog.py` does).

What patch.erf changes (C:data):

- **skills**: row 3 (Awareness) description strref 250 -> 49138.
- **weapondischarge**: row `363` (animation b6a4) fires 2 shots instead of 1 (`shots`, `hits`,
  `switchmask` `01`, `shot2` 900).
- **keymap**: adds an `eventtype` column (23 columns instead of 22), one row (80 instead of 79),
  and 134 changed cells (strrefs, `icpcgui` flags, ...).
- **bindablekeys**: 103 rows instead of 85, and 7 `bindable` flags turned on.

56 tables are only in the BIF (not in global.rim). They are mostly NWN leftovers; see
[the index](#index-of-all-tables), column "rim".

## Cross-reference map

What points where. "row" = row index, "label" = row label, "col" = names a column. Hit rates are
distinct values that resolve over distinct values (details in [Checked](#checked)).

### Table to table

| From | To | How | Check |
|---|---|---|---|
| appearance.normalhead, .backuphead | heads | row | 107/107, 13/13 |
| appearance.moverate | creaturespeed.2daname | value match | 9/9 |
| appearance.footsteptype | footstepsounds | row | 9/9 |
| appearance.soundapptype | appearancesndset | row | 14/14 |
| appearance.body_bag | bodybag | row | 9/9 |
| appearance.sizecategory | creaturesize | row | 3/3 |
| appearance.freelookeffect | videoeffects | row | 2/2 |
| appearance.deathvfx | visualeffects | label | 3/3 |
| appearance.racialtype | racialtypes | row (NWN meaning) | 0/1: always 20, out of range: unused |
| portraits.appearancenumber, .appearance_s, .appearance_l | appearance | row | 37/37, 32/32, 30/30 |
| portraits.race | racialtypes | row | 2/2 |
| portraits.sex | gender | row | 3/3 |
| placeables.soundapptype | placeableobjsnds | row | 28/28 |
| placeables.bodybag | bodybag | row | 1/1 |
| genericdoors.soundapptype, doortypes.soundapptype | placeableobjsnds | row | 37/37, 12/12 |
| placeableobjsnds.armortype, appearancesndset.armortype, baseitems.armortype | weaponsounds | col `<value>0` | 5/5, 2/2, 2/2 |
| bodybag.appearance | placeables | row | 9/9 |
| racialtypes.appearance | appearance | row | 2/2 |
| classes.attackbonustable, .savingthrowtable | cls_atk_*, cls_st_* | 2DA name | 2/2, 9/9 |
| classes.featstable | feat | col `<code>_list`, `_granted`, `_recom` | 8/8 |
| classes.skillstable | skills | col `<code>_class`, `_reco` | 8/8 |
| classes.featgain | featgain | col `<code>_reg`, `_bon` | 8/8 |
| classes.armorclasscolumn | acbonus | col | 6/6 |
| classes.spellgaintable | classpowergain | col | 3/3 |
| feat.prereqfeat1, .prereqfeat2, .successor | feat | row | 35/35, 33/33, 66/66 |
| feat.masterfeat | masterfeats | row | 3/3 |
| spells.prerequisites | spells | row list joined by `_` | 28/28 |
| baseitems.invsoundtype | inventorysnds | row | 27/27 |
| baseitems.weaponmattype, appearancesndset.weapon | weaponsounds | row | 4/4, 2/2 |
| baseitems.ammunitiontype | ammunitiontypes | row | 5/5 |
| baseitems.reqfeat0..2, .specfeat, .focfeat | feat | row | 12/12, 1/1, 1/1, 7/7, 6/6 |
| baseitems.propcolumn | itemprops | col whose label starts `<n>_` | 15/15 |
| baseitems.bodyvar | appearance | col `model<letter>` / `tex<letter>` | 9/9 |
| itemprops rows | itempropdef rows | one to one: same strref on the same row | 59/60 (itemprops row 48 empty) |
| itempropdef.subtyperesref | iprp_* or other tables | 2DA name | 20/20 |
| itempropdef.costtableresref | iprp_costtable | row | 15/15 |
| itempropdef.param1resref, iprp_onhit/iprp_monsterhit.param1resref | iprp_paramtable | row | 2/2, 5/5, 2/2 |
| iprp_costtable.name, iprp_paramtable.tableresref | iprp_* | 2DA name | 26/26, 11/11 |
| iprp_ammotype.ammotype | baseitems | row (NWN arrows/bolts/bullets) | 3/3 in range, meaningless in KOTOR |
| upgrade.upgradetype | upgradetypes | row | 10/10 |
| forceshields.visualeffectdef, .visualeffect_0N | visualeffects | label | 10/10, 2/2, 2/2, 2/2, 4/4 |
| forceshields.appearance_0N | appearance | row | 1/1 each |
| surfacemat.name | footstepsounds | col `<name>0..2` (lower case) | 9/9 |
| WOK/PWK/DWK face material | surfacemat | row | 191,329 faces, 0 out of range |
| combatanimations (labels and parry/dodge/damage 0..8) | animations | row | 58/58 and all |
| weapondischarge (labels) | animations, appearance | row | see the table |
| droiddischarge (labels / columns) | appearance.race / animations | value / row | 15/15 |
| iprp_spells.spellindex, iprp_spellcost.spellindex | spells | row (NWN) | 120/211, 78/115: NWN leftovers |

### Table to resource

| Column | Resource | Check |
|---|---|---|
| appearance.race, .modela..modelj | MDL | 128/128, 60/61, 38/38, 29/29 ..., 6/6 |
| appearance.texa..texj, .texaevil | TPC, named `<value>` + 2-digit variation (`01`, `02`, ...) | 79/83, 46/46, 28/28 ..., 6/6 with `01` |
| appearance.racetex, .envmap | TPC | 113/115, 3/4 (`DEFAULT` is a keyword) |
| heads.head | MDL | 106/107 |
| heads.headtexe, .headtexve, .headtexvve, .headtexvvve | TPC | 30/30 each |
| portraits.baseresref, .baseresrefe/ve/vve/vvve | TPC | 40/40, 30/31 each |
| placeables.modelname, genericdoors.modelname | MDL | 215/221, 52/63 |
| doortypes.model, .templateresref | MDL, UTD | 0/66, 0/30: NWN tileset doors, unused |
| placeableobjsnds.* | WAV | 58/58, 57/58, 6/7, 6/6, 9/10 |
| waypoint.resref | MDL | 4/4 |
| baseitems.defaultmodel | MDL | 37/38 |
| baseitems.itemclass | item icon `i<itemclass>_<nnn>` TPC, model `<itemclass>_<nnn>` MDL | 83/87 for `_001` |
| baseitems.defaulticon | TPC | 1/17: unused |
| baseitems.powerupsnd/powerdownsnd/poweredsnd | WAV | 1/1 each |
| classes.icon | TPC | 0/8: unused |
| feat.icon, skills.icon, spells.iconresref, effecticon.iconresref | TPC | 119/119, 8/8, 55/55, 61/61 |
| spells.impactscript | NCS | 11/14 |
| spells.casthandvisual, .projmodel | MDL | 2/3, 9/9 |
| spells.castsound | WAV | 3/3 |
| upgrade.template, upcrystals.template/shortmdlvar/longmdlvar/doublemdlvar | UTI | 25/25, 7/7 each |
| traps.resref / .model / .trapscript / .explosionsound | UTI / MDL / NCS / WAV | 12/12, 6/6, 1/3, 5/5 |
| footstepsounds.* | WAV | all columns full hits except force1 3/4 |
| appearancesndset.fall* | WAV | 7/7, 7/7, 7/7, 2/2 |
| weaponsounds.* | WAV | 4/4 per column |
| ammunitiontypes.model/model0/model1/muzzleflash | MDL | 5/5, 5/5, 5/5, 1/1 |
| ammunitiontypes.shotsound*/impactsound* | WAV | 4/4, 2/2, 3/4, 3/4 |
| grenadesnd.sound, guisounds.soundresref | WAV | 1/1, 17/17 |
| ambientmusic.resource, .stinger1 | WAV in `streammusic/` | 43/45, 17/18 |
| ambientsound.resource | WAV in `streamsounds/` | 44/44 |
| aliensound.filename | WAV | 180/299 |
| soundset.resref | SSF | 89/89 |
| visualeffects.imp_*_node | MDL | 9/9, 43/51, 36/36 |
| visualeffects.sound* | WAV | 42/43, 10/10, 2/3 |
| loadscreens.bmpresref / .musicresref | TPC / WAV | 4/4, 1/1 |
| movies (row labels) | BIK in `movies/` | 55/107 |
| modulesave, loadscreens (row labels), minglobalrim.moduleresref | module (`modules/<name>.rim/.mod`) | 116/123, 4/12, 3/3 |
| planetary.icon / .model | TPC / MDL | 10/15, 8/13 (Xbox Live planets missing) |
| texpacks.texture, .gui | ERF in `TexturePacks/` | 3/3, 1/1 |
| tutorial.icon, cursors.resref, comptypes.computerbackground | TPC | 13/13, 3/10, 2/2 |
| statescripts.scriptname | NCS | 2/18 (NWN scripts) |

### Table to dialog.tlk

Columns whose values are strrefs that resolve to matching text (C:data, all distinct values
resolve unless noted): appearance.string_ref, placeables.strref, genericdoors.strref,
doortypes.stringrefgame, bodybag.name, classes.name, classes.description, feat.name,
feat.description, masterfeats.strref, spells.name, spells.spelldesc, skills.name,
skills.description (the patched copy), racialtypes.name, gender.name, baseitems.name,
itempropdef.name, itemprops.stringref, iprp_*.name (where filled), iprp_paramtable.name,
traps.trapname, traps.name, poison.name, encdifficulty.strref, difficultyopt.name,
feedbacktext.strref, aiscripts.name_strref, aiscripts.description_strref, stringtokens.strref1/2,
ambientmusic.description, ambientsound.description, soundset.strref, loadscreenhints.gameplayhint,
loadscreenhints.storyhint, modulesave.areaname, movies.strrefname (67/107), credits.name,
tutorial.message0..2, planetary.name/description (12/17, 9/14), texpacks.strrefname,
bindablekeys.keynamestrref, keymap.actionstrref, keymap.descstrref.

Columns that *look* like strrefs but are not: times and amounts in milliseconds or points
(weapondischarge.shot*, combatanimations.hit1, prioritygroups.fadetime, sounddefaultstim.interval,
xptable.c*, plot.xp, ...). Numbers in the 1000..50000 range happen to resolve to random TLK lines;
judge by the column, not by whether the number resolves.

### GFF fields to tables

Values of these fields over every blueprint, area and dialogue file in the install, checked against
the table's rows (C:BW for the NWN meaning where noted, C:data for the range check; counts are
uses, sentinels excluded):

| GFF field | Table | In range | Notes |
|---|---|---|---|
| UTC Appearance_Type | appearance | 1958/1958 | BW-CRE |
| UTC PortraitId | portraits | 1955/1955 | BW-CRE |
| UTC SoundSetFile | soundset | 1424/1424 | 65535 = none (531 uses) |
| UTC BodyBag | bodybag | 1955/1955 | always 0 |
| UTC FactionID | repute | 1958/1958 | |
| UTC Race | racialtypes | 1957/1958 | one creature has 8 (RACIAL_TYPE_INVALID) |
| UTC Gender | gender | 1958/1958 | |
| UTC WalkRate | creaturespeed | 1958/1958 | BW-CRE |
| UTC PerceptionRange | ranges | 1956/1956 | values 8..11 = PercepRng* rows |
| UTC SubraceIndex | subrace | 1824/1824 | |
| UTC ClassList/Class | classes | 1968/1968 | |
| UTC FeatList/Feat | feat | 8106/8106 | |
| UTC ClassList/KnownList0/Spell, SpecAbilityList/Spell | spells | 1540/1540, 718/719 | one 299 |
| UTP Appearance | placeables | 1784/1784 | BW-DP |
| UTP BodyBag, Faction, TrapType | bodybag, repute, traps | all | Faction 0xFFFFFFFF on 4 |
| UTD GenericType | genericdoors | 575/575 | BW-DP |
| UTD Appearance | doortypes | 575/575 | always 0: KOTOR doors are all generic |
| UTD LoadScreenID, PortraitId | loadscreens, portraits | 525/525, 523/525 | LoadScreenID always 0; PortraitId 558 on 2 |
| UTI BaseItem | baseitems | 1055/1055 | BW-ITM |
| UTI PropertiesList/PropertyName | itempropdef | 2088/2088 | BW-ITM |
| UTI PropertiesList/CostTable | iprp_costtable | 2088/2088 | BW-ITM |
| UTI PropertiesList/Param1 | iprp_paramtable | 206/206 | 255 = none |
| UTI PropertiesList/UpgradeType | upgradetypes? | 470/922 | values up to 24: **not** an upgradetypes index; meaning open |
| UTT TrapType, Cursor, Faction | traps, cursors, repute | all | BW-TRG |
| UTE DifficultyIndex | encdifficulty | 133/133 | BW-ENC |
| UTE CreatureList/Appearance | appearance | 302/302 | |
| UTW Appearance, GIT WaypointList/Appearance | waypoint | 2054/2054, 4064/4064 | BW-WP |
| ARE CameraStyle | camerastyle | 117/117 | values 0..1 |
| ARE LoadScreenID | loadscreens | 117/117 | always 0 |
| ARE PlayerVsPlayer | pvpsettings | 117/117 | |
| ARE Rooms/EnvAudio, GIT AreaProperties/EnvAudio | soundeax? | 1298/1308, 98/117 | values up to 92: not (only) soundeax rows; meaning open |
| GIT AreaProperties/AmbientSndDay, AmbientSndNight | ambientsound | 117/117 | BW-ARE |
| GIT AreaProperties/MusicDay, MusicNight, MusicBattle | ambientmusic | 117/117 | BW-ARE |
| DLG EntryList/ReplyList AnimList/Animation | dialoganimations | 2667/2710, 289/293 | value = 10000 + row; the rest name unlabelled rows 1 and 48; values below 10000 (1200..1274, 2000, 35..70) are other animation ids |

### nwscript.nss constants to rows

Constant groups whose value is the row index (or label) of a table, and whose name matches the
name stored on that row (C:nss, C:data): BASE_ITEM_* -> baseitems (85/86), FEAT_* -> feat
(91/92), FORCE_POWER_* -> spells (48/52), SKILL_* -> skills (8/9), CLASS_TYPE_* -> classes (9/10),
GENDER_* -> gender (5/5), STANDARD_FACTION_* -> repute (17/17), POISON_* -> poison (6/6),
TRAP_BASE_TYPE_* -> traps (12/12), VFX_* -> visualeffects **by label** (115/118), SHIELD_* ->
forceshields (18/18), VIDEO_EFFECT_* -> videoeffects (3/4, the 4th is NONE = -1), PLANET_* ->
planetary (16/16), ENCOUNTER_DIFFICULTY_* -> encdifficulty (5/5), CREATURE_SIZE_* ->
creaturesize (6/6), ITEM_PROPERTY_* -> itemprops/itempropdef (58/59), DISGUISE_TYPE_* ->
appearance (298/305; the rest are spelling variants), NPC_* -> npc (7/9; Cand/Canderous, T3M3/T3_M4).
The unmatched ones are sentinels (`*_INVALID`, `*_NONE = -1`, `SKILL_MAX_SKILLS`) or spelling
differences. RACIAL_TYPE_* keeps NWN's numbering: rows 0..4 of racialtypes are empty, 5 = Droid,
6 = Human. POLYMORPH_TYPE_* (38) and AOE_* (36) are NWN constants with no KOTOR rows.

## Appearance and models

### appearance (509 rows x 80 columns)

One row per creature look: the model(s), textures, head, sounds, movement speeds and body
dimensions. Indexed by UTC `Appearance_Type`, UTE `CreatureList/Appearance`,
portraits.appearance*, racialtypes.appearance, forceshields.appearance_0N, DISGUISE_TYPE_*
(`EffectDisguise`), and the `<appearance>_` prefix of weapondischarge labels.

Model types (`modeltype`): **B** 312 rows (humanoids: body model + separate head), **F** 107,
**S** 56, **L** 34. A B-type creature is drawn as the body model `model<letter>` with texture
`tex<letter>` + two-digit variation, plus the head model from heads.2da (row `normalhead`).
The letter is the body variation: baseitems.bodyvar of the item in the body slot (B..J; C:data
for the columns), and *I* `A` when nothing is worn. For a PC, the three appearance rows `P_FEM_A_SML_01`/`MED`/`LRG` are the
small/medium/large builds that portraits.2da ties to one portrait.

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| string_ref | strref | name of the appearance (toolset); only row 0 has one | C:BW, C:data |
| race | resref MDL | default model; for S/F/L types the creature's model | C:BW, C:data 128/128 |
| walkdist | float | metres covered by one cycle of the walk animation | C:BW |
| rundist | float | metres covered by one cycle of the run animation | C:BW |
| driveanimwalk | float | walk distance used when the engine drives the creature (scripted moves) | C:DS |
| driveanimrun | float | same for running | C:DS |
| racetex | resref TPC | texture for the `race` model | C:DS, C:data 113/115 |
| modeltype | B/F/S/L | S simple (no weapons shown), F weapons shown, L large (right hand only), B body+head | C:BW (S/F/L), C:DS (B) |
| normalhead | int | heads.2da row of the head model | C:DS, C:data 107/107 |
| backuphead | int | heads.2da row used instead when the PC already uses `normalhead` | C:DS, C:data 13/13 |
| modela .. modelj | resref MDL | body model for body variation A..J | C:DS, C:data |
| texa .. texj | texture base | body texture; the engine appends a two-digit variation (`01`..) | C:DS, C:data (79/83 ... with `01`) |
| texaevil | texture base | dark-side variant of `texa` (6 values, all PC bodies) | C:DS, C:data 6/6 |
| skin | - | | unused |
| headtexve, headtexe, headtexg, headtexvg | - | | unused (heads.2da has these) |
| envmap | resref TPC or `DEFAULT` | environment map; `DEFAULT` = the default one | C:BW, C:data 3/4 |
| bloodcolr | R/S/G | blood colour (R red, G green, S sparks for droids) | C:BW (R/G), *I* (S) |
| weaponscale | - | | unused |
| wing_tail_scale | float | always 1; NWN wings/tails | unused |
| moverate | string | creaturespeed.2daname of the default speed | C:BW, C:data 9/9 |
| driveaccl | int | acceleration for driven movement | C:DS |
| drivemaxspeed | float | top speed for driven movement | C:DS |
| hitradius | float | collision radius | C:DS |
| perspace | float | personal space (fits through openings) | C:BW |
| creperspace | float | personal space in combat | C:BW |
| cameraspace | float | camera offset for tall creatures (3 rows) | C:DS |
| height | float | creature height | C:BW |
| targetheight | string | always `l` | C:BW (meaning), unused in practice |
| abortonparry | 0/1 | attack animation aborts when the target parries | C:BW |
| racialtype | int | always 20 (out of range for KOTOR's racialtypes) | unused |
| haslegs, hasarms | 0/1 | | C:BW |
| portrait | resref | `po_default` on 6 rows; texture absent | unused |
| footstepsound | - | | unused |
| footstepvolume | int | always 1 | unused |
| sizecategory | int | creaturesize.2da row | C:BW, C:data |
| armor_sound, combat_sound, helmet_scale_m, helmet_scale_f | - | | unused |
| perceptiondist | int | always 9; NWN: perception range | C:BW (meaning), *I* |
| footsteptype | int | footstepsounds.2da row; `****` = silent | C:BW, C:data 9/9 |
| soundapptype | int | appearancesndset.2da row | C:BW, C:data 14/14 |
| headtrack | 0/1 | head turns to look at things | C:BW |
| head_arc_h, head_arc_v | int | head turn limits in degrees | C:BW |
| headbone | - | head node name | unused |
| hitdist | float | subtracted from the distance to the target before comparing with prefatckdist | C:BW |
| prefatckdist | float | preferred attack distance | C:BW |
| groundtilt | 0/1 | model tilts to the ground slope | C:DS |
| body_bag | int | bodybag.2da row left behind on death | C:BW, C:data 9/9 |
| freelookeffect | int | videoeffects.2da row applied in free-look (T3-M4 and HK-47) | C:DS, C:data 2/2 |
| cameraheightoffset | float | camera offset (2 rows) | C:DS |
| deathvfx | int | visualeffects.2da **label** played on death (droid explosions) | C:DS, C:data 3/3 |
| deathvfxnode | string | model node for deathvfx (`impact`, `root`) | *I* |
| fadedelayondeath, destroyobjectdelay | int | seconds before the corpse fades / is destroyed (3 rows) | C:DS |
| disableinjuredanim | 0/1 | no injured animations (3 rows) | C:DS |

### heads (107 x 7)

Head models for B-type appearances. Indexed by appearance.normalhead/backuphead.

| Column | Type | Meaning | Status |
|---|---|---|---|
| head | resref MDL | head model (its own texture is in the model) | C:DS, C:data 106/107 |
| headtexe | resref TPC | dark-side stage 1 texture (`..D1`) | C:DS, C:data 30/30 |
| headtexve | resref TPC | stage 2 (`..D2`) | C:DS, C:data 30/30 |
| headtexvve | resref TPC | stage 3 (`..D3`) | C:DS, C:data 30/30 |
| headtexvvve | resref TPC | stage 4, fully dark (`..D`) | C:DS, C:data 30/30 |
| headtexg, headtexvg | - | *I*: light-side variants (g = good) | unused |

Only the 30 PC heads have dark-side textures.

### portraits (41 x 14)

Portrait textures. Indexed by UTC/UTD/UTT `PortraitId`. Row 0 is empty.

| Column | Type | Meaning | Status |
|---|---|---|---|
| baseresref | resref TPC | the portrait texture (full name, unlike NWN's `po_` + size letter) | C:BW (role), C:data 40/40 |
| sex | int | gender.2da row (0 male, 1 female, 4 none) | C:BW, C:data |
| appearancenumber | int | appearance.2da row the portrait belongs to (medium build for PCs) | C:DS, C:data 37/37 |
| race | int | racialtypes.2da row (5 droid, 6 human) | C:BW, C:data |
| inanimatetype | - | | unused |
| plot | 0/1 | always 0 | C:BW (meaning) |
| lowgore | - | | unused |
| appearance_s | int | appearance row of the small build | C:DS, C:data 32/32 |
| appearance_l | int | appearance row of the large build | C:DS, C:data 30/30 |
| forpc | 0/1 | selectable in character creation | C:DS |
| baseresrefe, baseresrefve, baseresrefvve, baseresrefvvve | resref TPC | dark-side stages 1..4 (`D1`, `D2`, `D3`, `D`) | C:DS, C:data 30/31 each (T3-M4's missing) |

### placeables (232 x 17)

Placeable object looks. Indexed by UTP `Appearance` (C:BW, C:data 1784/1784); bodybag.appearance
also points here.

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| strref | strref | name (toolset) | C:BW, C:data 227/227 |
| modelname | resref MDL | model; its PWK walkmesh has the same name (196/221 exist) | C:BW, C:data 215/221 |
| lightcolor, lightoffsetx/y/z | - | NWN attached light | unused |
| soundapptype | int | placeableobjsnds.2da row | C:BW, C:data 28/28 |
| shadowsize | int | always 1 | C:BW |
| bodybag | int | always 0 | C:BW |
| lowgore | - | | unused |
| preciseuse | 0/1 | always 0; *I*: use from the exact hook point | *I* |
| hitcheck | 0/1 | *I*: included in hit/line-of-fire tests | *I* |
| canseeheight | float | *I*: height used for line-of-sight checks (1.5 or 0.5) | *I* |
| hostile | 0/1 | *I*: can be attacked | *I* |
| noncull | 0/1 | *I*: never culled by the visibility system | *I* |
| ignorestatichitcheck | 0/1 | *I* | *I* |

### genericdoors (65 x 10)

Door looks. Indexed by UTD `GenericType` (C:BW, C:data 575/575; every KOTOR door uses this, since
UTD `Appearance` is always 0).

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| strref | strref | door name in game | C:BW, C:data 54/54 |
| modelname | resref MDL | door model; its walkmeshes are `<model>0/1/2.dwk` (*I*: closed, open one way, open the other; 52/63 exist) | C:BW, C:data 52/63 |
| blocksight | 0/1 | blocks line of sight | C:BW |
| visiblemodel | 0/1 | model visible (invisible doors are always open) | C:BW |
| soundapptype | int | placeableobjsnds.2da row | C:BW, C:data 37/37 |
| name | - | toolset name | unused |
| preciseuse | 0/1 | *I* (as placeables) | *I* |
| nobin | 0/1 | *I*: door has no "bin" (no use hook?) | *I* |
| staticanim | - | | unused |

### doortypes (69 x 8)

NWN tileset doors, indexed by UTD `Appearance` when it is non-zero (C:BW). KOTOR never uses it:
every UTD has `Appearance` 0, no `model` exists as an MDL (0/66) and no `templateresref` as a UTD
(0/30). Columns (C:BW): label, model, tileset, templateresref, stringrefgame (strref), blocksight,
visiblemodel, soundapptype (placeableobjsnds row). **unused**.

### placeableobjsnds (70 x 7)

Sounds of placeables and doors. Indexed by placeables/genericdoors/doortypes.soundapptype.
Columns (C:BW): label; armortype (`metal`, `stone`, `wood`, `armor`, `cloth`: picks the
`<armortype>0/1` columns of weaponsounds for hit sounds, C:data 5/5); opened, closed, destroyed,
used, locked (WAV resrefs, C:data 58/58, 57/58, 6/7, 6/6, 9/10).

### bodybag (10 x 4)

What is left behind when a creature dies. Indexed by appearance.body_bag (and UTC/UTP `BodyBag`,
always 0). Columns: label (C:BW); name, strref "Remains" (C:BW, C:data); appearance, placeables.2da
row of the container placeable (C:BW, C:data 9/9); corpse 0/1, *I*: leave the corpse itself
rather than a bag (C:DS lists it without meaning).

### waypoint (5 x 3)

Waypoint markers (toolset view). Indexed by UTW/GIT `Appearance` (C:BW, C:data). Columns: label,
resref (MDL, C:data 4/4), strref (empty).

### Other appearance tables

| Table | Size | Purpose | Status |
|---|---|---|---|
| appearancesndset | 16 x 9 | creature sound classes, see [World, audio and video](#world-audio-and-video) | |
| creaturespeed | 12 x 5 | see [Rules: creatures](#rules-creatures-races-and-progression) | |
| creaturesize | 6 x 3 | see there | |
| soundset | 90 x 5 | see [World, audio and video](#world-audio-and-video) | |
| placeabletypes | 9 x 2 | NWN toolset placeable categories (label, strref empty) | C:BW, unused |
| phenotype | 3 x 2 | NWN body phenotypes Normal/Skinny/Large (label, name empty); UTC Phenotype is always 0 | C:BW, unused |
| capart | 18 x 3 | NWN creature armour parts: name (0), mdlname (FOOTR, ...), nodename (rfoot_g, ...) | unused |
| caarmorclass | 8 x 2 | NWN creature armour classes (NK, CL, FP, ...) | unused |
| catype | 5 x 2 | NWN creature appearance types (P, H, GIHE, C, A) | unused |
| replacetexture | 2 x 1 | `T_Flag02`, `T_flag02`; *I*: textures to swap at run time (NWN flags) | *I*, unused |
| tilecolor | 16 x 3 | NWN tile colours (red, green, blue) | unused |
| lightcolor | 32 x 7 | light colour presets: red, green, blue (0..2), label, toolset colours | C:BW |

## Animation and combat presentation

### animations (394 x 15)

The engine's animation list: row = animation id, `name` = the animation's name in the model. Some
names repeat (die/dead at 80/81, 306/307, 329/330), *I*: separate sections for different model
skeletons. combatanimations, weapondischarge and droiddischarge refer to these rows (C:data).

| Column | Type | Meaning | Status |
|---|---|---|---|
| name | string | animation name inside the MDL | C:DS |
| stationary | 0/1 | creature does not move during it | C:DS |
| pause | 0/1 | can be interrupted by a new command | C:DS |
| walking, running | 0/1 | counts as a walk / run animation | C:DS |
| looping | 0/1 | loops | C:DS |
| fireforget | 0/1 | plays once and ends | C:DS |
| overlay | 0/1 | plays on top of others | C:DS |
| playoutofplace | 0/1 | always 0 | C:DS |
| dialog | 0/1 | a conversation animation | C:DS |
| damage, parry, dodge, attack | 0/1 | a damage reaction / parry / dodge / attack animation | C:DS (*I* for parry) |
| hideequippeditems | 0/1 | hide weapons while playing | C:DS |

### combatanimations (58 x 31)

Keyed by row **label** = animations.2da row of an attack animation (87 = g1a1, ...; C:data 58/58).
For each attack: `hits` (0/1), `hit1` (*I*: time of the hit in ms, 500..1267), `hit2`, `hit3`
(empty), and `parry0..8`, `dodge0..8`, `damage0..8` = animations.2da rows of the defender's
reaction (C:data, all in range; *I*: the digit selects the defender's weapon/stance class).

### weapondischarge (64 x 16)

Shot timing for ranged attack animations. Row **label** = animations.2da row (`217` = b5a1, `288`
= b0a1, ...) optionally prefixed by an appearance row (`3_217` = HK-47, `56_288` = Droid_Assassin)
for creature-specific timing (C:data for the references, *I* for the lookup rule). Columns
(*I* from names and values): droid (0/1), shots (number of bolts), hits (how many can hit),
switchmask (digit string, *I*: which hand fires each shot), shot1..shot12 (ms from animation start
to each shot). patch.erf changes row `363`.

### droiddischarge (15 x 3)

Row **label** = droid model name (= appearance.race, C:data 15/15); the columns are labelled
`288`, `289`, `351` = animations rows b0a1, b0a2, b0a3; cells *I*: ms at which the droid's shot
leaves for that attack animation.

### dialoganimations (227 x 6)

Conversation animations. DLG `AnimList/Animation` = 10000 + row (C:data: 2667 of 2710 entry uses
land on a named row). Columns: name (31 rows named: Talk_Normal, Taunt, ...), looping, fireforget,
dialog, overlay (0/1, as animations), cu_pb_range (*I*: close-up camera range).

### Weapon and impact sounds

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| weaponsounds | 4 x 29 | rows Unarmed, Lightsaber, Blade, Large_Blade; cloth0/1, leather0/1, armor0/1, forcefield0/1, metal0/1, wood0/1, stone0/1 (hit sounds by target material), parry0/1, swingshort0..2, swinglong0..2, swingtwirl0..2, clash0/1 (WAV); pitchoffset empty. Indexed by baseitems.weaponmattype, appearancesndset.weapon | C:BW (role), C:data (WAV 4/4) |
| ammunitiontypes | 6 x 10 | ranged ammo: label; model (unused per DS), model0 (normal bolt), model1 (power blast) MDL; shotsound0/1, impactsound0/1 WAV; muzzleflash MDL; shieldhit 0/1 (bolt hits energy shields). Indexed by baseitems.ammunitiontype | C:DS, C:data |
| damagehitvisual | 13 x 3 | rows in DAMAGE_TYPE bit order (Bludgeoning .. Blaster); visualeffect (empty), rangedeffect (visualeffects label, only Blaster = 4024 VFX_COM_BLASTER_IMPACT) | C:nss (order), C:data |
| grenadesnd | 31 x 2 | one row per surfacemat row (same labels); sound WAV (only `fs_metal_droid1`) | *I* |
| swingsounds | 9 x 3 | rows swingshort, swinglong, ..., metal; sound1..3 `ls_*` | unused (no `ls_*` WAV exists) |
| inventorysnds | 33 x 2 | label, inventorysound `it_*`; indexed by baseitems.invsoundtype (C:data 27/27) | only 1/33 WAV exists: *I* the engine builds the real name, or unused |

### Others

| Table | Size | Purpose | Status |
|---|---|---|---|
| formations | 3 x 21 | party formations WEDGE/LINE/ZULU: angle_N (degrees) and distance_N (metres) of follower N | *I* |
| visemes | 16 x 3 | lip-sync visemes: viseme name, animname (empty), visemeid 0..15; labels 1..16 | *I* (LIP files hold viseme ids) |
| rumble | 22 x 32 | controller rumble patterns: looping, lsamples/rsamples, l/r magnitude and time 1..7; referenced by footstepsounds/visualeffects.rumblepattern | *I* |

## Rules: creatures, races and progression

### classes (9 x 49)

Rows 0..8 = CLASS_TYPE_* (C:nss 9/9): Soldier, Scout, Scoundrel, JediGuardian, JediConsular,
JediSentinel, CombatDroid, ExpertDroid, Minion. Indexed by UTC `ClassList/Class`.

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| name | strref | class name | C:BW, C:data 9/9 |
| plural, lower | - | | unused |
| description | strref | class description | C:BW, C:data 8/8 |
| icon | resref | `IR_*`; no such texture | C:BW (role), unused |
| hitdie | int | hit die (6..12) | C:BW |
| attackbonustable | 2DA name | `CLS_ATK_1`/`2` | C:BW, C:data |
| featstable | code | 3-letter code: feat.2da columns `<code>_list/_granted/_recom` (KOTOR has no cls_feat_* tables) | C:DS, C:data 8/8 |
| savingthrowtable | 2DA name | `CLS_ST_*` | C:BW, C:data 9/9 |
| skillstable | code | skills.2da columns `<code>_class/_reco` | C:DS, C:data 8/8 |
| skillpointbase | int | skill points per level | C:BW |
| spellgaintable | code | classpowergain.2da column (Jedi only) | C:DS, C:data 3/3 |
| spellknowntable | - | | unused |
| playerclass | 0/1 | selectable by the player | C:BW |
| spellcaster | 0/1 | uses the Force | C:BW |
| str, dex, con, wis, int, cha | int | recommended/default ability scores | C:BW |
| primaryabil | STR/DEX/... | ability auto-levelling raises | C:BW |
| alignrestrict, alignrstrcttype | hex | 0 | C:BW, unused |
| constant | string | `CCLASS_SOLDIER` on every row | unused |
| effcrlvl01..20 | int | always 1 (NWN CR weighting) | unused |
| forcedie | int | Force points per level die (0, 4, 6, 8) | C:DS |
| armorclasscolumn | code | acbonus.2da column for the class defense bonus | C:DS, C:data 6/6 |
| featgain | code | featgain.2da columns `<code>_reg/_bon` | C:DS, C:data 8/8 |

### cls_atk_1, cls_atk_2, cls_atk_3 (20, 20, 60 x 1)

Base attack bonus per level, row = level - 1: column `bab` (C:BW). classes uses 1 (full: soldier,
Jedi Guardian ...) and 2 (three-quarter). cls_atk_3 (60 rows, BIF only) is not named by any class:
unused.

### cls_st_* (9 tables, 20 x 4 each)

Saving throws per level: level, fortsave, refsave, willsave (C:BW, BW calls them cls_savthr_*).
Tables: cls_st_soldier, cls_st_scout, cls_st_scndrl, cls_st_jedi_g, cls_st_jedi_c, cls_st_jedi_s,
cls_st_cm_drd, cls_st_ex_drd, cls_st_minion; named by classes.savingthrowtable (C:data 9/9).

### cls_spgn_jedi (20 x 9)

Jedi spell-gain table in NWN shape: level, numspelllevels (1), spelllevel0 (2..21), spelllevel1..6
empty (C:BW for the shape). No class names it (classes.spellgaintable holds codes for
classpowergain instead); the name is in the exe. *I*: Force power slots by level.

### classpowergain (20 x 4)

Force powers gained per level: label (= level), jcn, jsn, jgd (powers gained at that level, 1 or 2).
Columns named by classes.spellgaintable (C:data). *I* for the meaning.

### featgain (20 x 17)

Feats gained per level: label (= level), `<code>_reg` (0/1 normal feat this level) and
`<code>_bon` (always 0, bonus feats) for sol, sct, scd, jcn, jsn, jgd, drx, drc (C:DS for the
role, C:data for the columns).

### acbonus (21 x 6)

Class defense bonus by level: scd, sol, sct, jdc, jds, jdg (C:DS; 21 rows, so whether row 0 is level
0 or 1 is open). Selected by classes.armorclasscolumn.

### racialtypes (7 x 22)

Rows 0..4 are empty (NWN races removed but numbering kept), 5 = Droid, 6 = Human (C:nss).
Indexed by UTC `Race`, portraits.race.

| Column | Meaning | Status |
|---|---|---|
| label, abrev | programmer label, abbreviation | C:BW |
| name | strref of the race name | C:BW, C:data 2/2 |
| convername, convernamelower, nameplural, description | | unused |
| appearance | default appearance.2da row (2, 6) | C:BW, C:data |
| stradjust .. conadjust | racial ability modifiers (all 0) | C:BW |
| endurance | 30 | C:BW: obsolete |
| favored, featstable, biography | | unused |
| playerrace | 1 | C:BW |
| constant | RACIAL_TYPE_DROID / _HUMAN | C:BW, C:nss |
| age | 18 | C:BW |
| toolsetdefaultclass | 4 | C:BW |

### Progression and XP

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| exptable | 21 x 2 | level, xp: XP needed to reach level (0, 1000, 3000, ...); row 20 = 0xFFFFFFFF cap | *I* (the values are the d20 XP curve) |
| xptable | 20 x 22 | level, c0..c20: *I*: XP awarded for a kill, by party level (row) and challenge rating (column) | *I* |
| xpbaseconst | 17 x 3 | leveldiff (-8..8), balance (multiplier), bonus; BIF only, not referenced | *I*, likely unused |
| fractionalcr | 5 x 4 | label (1/2..1/8), displaystrref (empty), denominator, min (CR cut-off) | C:BW |
| npc | 11 x 2 | rows 0..8 = party members (NPC_* constants, C:nss): tag, percentxp (share of XP they get, 80); rows 9 GAME_XP_General (100), 10 PER_NPC_Bonus (0) | C:nss (rows), *I* (percentxp) |
| creaturespeed | 12 x 5 | label, name (empty), 2daname (key used by appearance.moverate), walkrate, runrate (m/s). Indexed by UTC `WalkRate` | C:BW, C:data |
| creaturesize | 6 x 3 | label (INVALID..HUGE, = CREATURE_SIZE_*), acattackmod (+2..-2), strref (empty) | C:BW, C:nss |
| subrace | 3 x 1 | None, Wookie, Beast; indexed by UTC `SubraceIndex` (C:data) | *I* (baseitems.denysubrace masks it) |
| gender | 5 x 4 | name (strref), gender letter (M F B O N), graphic (empty), constant (GENDER_*) | C:BW, C:nss, C:data |
| forceadjust | 11 x 2 | goodcost, evilcost: Force point cost multipliers for light/dark powers by alignment band (row 0 = most evil .. 10 = most good) | *I* |
| regeneration | 2 x 3 | InCombat / OutOfCombat: healthregen, forceregen (per second?) | C:DS (names), *I* (units) |

## Rules: feats, Force powers and skills

### feat (125 x 60)

Rows = FEAT_* constants (C:nss 91/92). Indexed by UTC `FeatList/Feat`, baseitems.reqfeat*/specfeat/
focfeat, feat.prereqfeat*/successor, and the Subtype of UTI properties whose itempropdef subtype
table is `FEAT` (BonusFeats, Use_Limitation_Feat).

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| name | strref | feat name | C:BW, C:data 122/122 |
| description | strref | feat description | C:BW, C:data 121/121 |
| icon | resref TPC | icon | C:BW, C:data 119/119 |
| mincharlevel | int | minimum character level (0, 4, 8) | *I* |
| minattackbonus, minstr, mindex, minint, minwis, minspelllvl | - | | unused |
| prereqfeat1, prereqfeat2 | int | feat rows required first | C:BW, C:data |
| gainmultiple, effectsstack | 0 | | C:BW |
| allclassescanuse | 0/1 | | C:BW |
| category | hex | 0x1104 / 0x1111 / 0x1808 on 24 rows: talent category for the AI | *I* (BW: categories.2da, unused there) |
| maxcr | int | talent CR cap | C:BW |
| spellid | - | | unused |
| successor | int | feat row that upgrades this one (rank 2, 3) | C:BW, C:data 66/66 |
| crvalue, usesperday | - | | unused |
| masterfeat | int | masterfeats.2da row | C:BW, C:data |
| targetself | 1 | the feat targets the user | C:BW |
| orreqfeat0..4, reqskill | - | | unused |
| constant | string | FEAT_* name | C:BW, C:nss |
| toolscategories | 1..6 | toolset filter category | C:BW |
| hostilefeat | 0 | | C:BW |
| `<cls>_list` (scd, sol, sct, jcn, jgd, jsn, drx, drc) | 0/1/3/4 | availability for the class: 3 = granted at `_granted` level (always paired), 0/1 = selectable (*I*: 1 also as bonus feat), 4 = not available | *I* (shape follows BW's cls_feat List) |
| `<cls>_granted` | int | class level at which the feat is granted, -1 never | *I* |
| `<cls>_recom` | int | recommendation order for auto-levelling | *I* |
| exclusion | hex | always 0x00 | unused |
| usetype | 0/1 | *I*: 1 = activated combat feat | *I* |
| pips | 1..3 | rank shown as pips in the GUI | *I* |

### masterfeats (3 x 4)

WeaponProficency, WeaponFocus, WeaponSpecialization: label, strref (C:BW, C:data), description,
icon (empty).

### spells (132 x 53): Force powers and special abilities

Rows = FORCE_POWER_* constants (C:nss 48/52; the 4 misses are name changes). Also items' abilities
(`ITEM_ABILITY_*`, `DROID_ITEM_*`, `SPECIAL_ABILITY_*`, `MONSTER_ABILITY_*`). Indexed by UTC
`KnownList0/Spell`, `SpecAbilityList/Spell`, itempropdef `CastSpell` subtypes, `GetLastForcePowerUsed`.

| Column | Type | Meaning | Status |
|---|---|---|---|
| label | string | programmer label | C:BW |
| name | strref | power name | C:BW, C:data 119/119 |
| spelldesc | strref | description | C:BW, C:data 56/56 |
| forcepoints | int | Force point cost (0..25) | *I* |
| goodevil | G/E/- | light / dark / neutral power | *I* |
| usertype | 1/2/4/-2 | 1 Force power, 2 special ability, 4 item ability (BW numbering), -2 disabled `_XXX` rows | C:BW (1/2/4), *I* (-2) |
| prerequisites | `n` or `n_m` | spells rows required first | C:data 28/28 |
| masterspell | - | | unused |
| guardian, consular, sentinel | int | class level at which the power can be learned (0 = no) | *I* (BW: per-class spell level) |
| inate | int | innate level when used as an ability | C:BW |
| maxcr | int | talent CR | C:BW |
| category | hex | talent category (0x1101 ...) for the AI | C:BW (role) |
| range | T/M/P/S/L/W | touch, medium, personal, short, long, W (*I*: weapon/throw) | C:BW |
| iconresref | resref TPC | icon | C:BW, C:data 55/55 |
| impactscript | resref NCS | script run on impact | C:BW, C:data 11/14 |
| conjtime | int | conjure duration (ms) | C:BW |
| conjanim | hand/throw/dark/up | conjure animation | C:BW |
| conjheadvisual .. conjsoundfemale | - | | unused |
| castanim | self/throw/dark/up/jump/monster | cast animation | C:BW |
| casttime | int | cast duration (ms) | C:BW |
| castheadvisual, castgrndvisual | - | | unused |
| casthandvisual | resref MDL | hand effect during the cast | C:BW, C:data 2/3 |
| castsound | resref WAV | | C:BW, C:data 3/3 |
| catchtime, catchanim | int, string | *I*: lightsaber-throw catch timing (one row, `CATCH`) | *I* |
| proj | 0/1 | has a projectile | C:BW |
| projmodel | resref MDL | grenade models | C:BW, C:data 9/9 |
| projtype | grenade/linked | | C:BW |
| projspwnpoint | throw/hand | node the projectile starts at | C:BW |
| projsound | - | | unused |
| projorientation | path | | C:BW |
| immunitytype | Electricity/Fire | | C:BW: not used by the game |
| itemimmunity | 0/1 | | C:BW: not used |
| forcehostile, forcefriendly, forcepassive, forcepriority | int | *I*: AI choice weights | *I* |
| dark_recom, light_recom | int | recommendation order for auto-levelling | *I* |
| exclusion | hex | 0x00/0x01/0x02 | *I* |
| requireitemmask, forbiditemmask | hex | *I*: item kinds required / forbidden while using (0x40, 0x3f) | *I* |
| pips | 1..3 | rank shown as pips | *I* |
| itemtargeting | 1/2 | *I*: targets an item (medpacs, ...) | *I* |
| hostilesetting | 0/1 | hostile act | C:BW |

### skills (8 x 30)

Rows = SKILL_* (C:nss 8/8). patch.erf's copy wins (Awareness description changed).

| Column | Meaning | Status |
|---|---|---|
| label | programmer label | C:BW |
| name, description | strrefs | C:BW, C:data |
| icon | resref TPC | C:BW, C:data 8/8 |
| untrained | usable without ranks | C:BW |
| keyability | INT/WIS/DEX/CHA | C:BW |
| armorcheckpenalty | 0/1 | C:BW |
| allclassescanuse | 1 | C:BW |
| category, maxcr | empty | C:BW |
| constant | SKILL_* | C:BW, C:nss |
| hostileskill | 0 | C:BW |
| `<cls>_class` (scd, sol, sct, jcn, jgd, jsn, drx, drc) | 1 = class skill | C:DS, C:data |
| `<cls>_reco` | recommendation order | *I* |
| droidcanuse, npccanuse | 0/1 | *I* |

### Others

| Table | Size | Purpose | Status |
|---|---|---|---|
| categories | 15 x 1 | talent categories (Harmful_AOE_Discriminant, ...), labels 1..15; *I*: names for the hard-coded talent categories in feat/spells.category | C:BW (role) |
| combatmodes | 4 x 1 | Attack, Power_Attack, Parry, Counter_Spell (NWN) | unused |
| metamagic | 7 x 4 | NWN metamagic | unused |
| domains | 22 x 15 | NWN cleric domains (`ID_*` icons missing) | unused |

## Rules: items

### baseitems (92 x 61)

Item types. Rows = BASE_ITEM_* (C:nss 85/86). Indexed by UTI `BaseItem` (1055/1055).

| Column | Type | Meaning | Status |
|---|---|---|---|
| name | strref | type name ("Quarter Staff") | C:BW, C:data 89/89 (DS calls it an id; it is a strref) |
| label | string | programmer label | C:BW |
| equipableslots | hex | bit n = INVENTORY_SLOT n (0x1 head, 0x2 body, 0x8 hands, 0x10 right weapon, 0x20 left weapon, 0x80/0x100 arms, 0x200 implant, 0x400 belt, 0x4000..0x10000 creature weapons, 0x20000 creature armour) | C:BW (role), C:nss + C:data (bits) |
| canrotateicon | - | | unused |
| modeltype | 0/1 | 0 = own model (`<itemclass>_<nnn>`), 1 = body armour (changes the appearance's body) | C:DS, *I* |
| itemclass | string | base name for the model `<itemclass>_<nnn>.mdl` and icon `i<itemclass>_<nnn>`, nnn = UTI ModelVariation (armour: TextureVar) | C:BW, C:data (icons 921/963 UTIs, `_001` 83/87) |
| genderspecific | 0 | | C:BW |
| partenvmap | 0/1 | environment-map the model | C:BW |
| defaultmodel | resref MDL | model when the variation is missing | C:BW, C:data 37/38 |
| defaulticon | resref | `ia_armor` ...; none exist | unused |
| container | 0 | | C:BW |
| weaponwield | 1..6 | wield style | C:BW (NWN values differ) |
| weapontype | 1/3/4 | *I*: 1 melee, 4 ranged (DS), 3 = ? | C:DS |
| damageflags | int | DAMAGE_TYPE_* bit mask (1 bludgeon, 2 pierce, 4 slash, 1024 sonic, 2048 ion, 4096 blaster) | C:nss + C:data |
| weaponsize | 1..4 | | C:BW |
| rangedweapon | 1 | ranged weapon | C:BW |
| maxattackrange | int | maximum range of ranged attacks | C:DS |
| prefattackdist | float | preferred attack distance | C:BW |
| minrange, maxrange | int | NWN toolset part range | C:BW |
| bloodcolr | S | | C:DS |
| numdice, dietoroll | int | damage dice | C:BW |
| critthreat, crithitmult | int | critical threat range and multiplier | C:BW |
| basecost | float | base price | C:BW |
| stacking | int | max stack size | C:BW |
| itemmultiplier | int | price multiplier | C:BW |
| description | - | | unused |
| invsoundtype | int | inventorysnds.2da row | C:BW, C:data 27/27 |
| maxprops, minprops | 8, 0 | | C:BW |
| propcolumn | int | itemprops.2da column `<n>_*` listing allowed properties | C:BW, C:data 15/15 |
| reqfeat0..4 | int | feat rows required to use the item | C:BW, C:data |
| ac_enchant | 0 | AC bonus type | C:BW |
| baseac | int | armour AC (0..9) | C:BW |
| dexbonus | int | maximum Dexterity bonus allowed by armour (0..8; -1 on non-armour items) | C:DS, C:data |
| accheck, armorcheckpen, baseitemstatref, chargesstarting | | | C:DS: unused |
| rotateonground | 0/1 | | C:BW |
| tenthlbs | int | weight in tenths of a pound | C:BW |
| weaponmattype | int | weaponsounds.2da row | C:BW, C:data 4/4 |
| ammunitiontype | int | ammunitiontypes.2da row | C:DS, C:data 5/5 |
| powereditem | 0/1 | can be switched on (lightsabers) | C:DS |
| powerupsnd, powerdownsnd, poweredsnd | resref WAV | | C:DS, C:data |
| itemtype | int | item category (0..47; 41 lightsaber, 38 robe, ...) for the GUI/AI | C:DS, *I* |
| bodyvar | letter | appearance body column (`model<x>`/`tex<x>`) used when worn | C:DS, C:data 9/9 |
| specfeat, focfeat | int | weapon specialization / focus feat rows | C:DS, C:data |
| droidorhuman | 0/1/2 | usable by both / humans / droids | C:DS |
| denysubrace | hex | subrace bit mask that cannot use it (0x2 = Wookie) | C:DS, *I* |
| armortype | leather/armor | material for hit sounds (weaponsounds columns) | C:DS, C:data |
| storepanelsort | int | sort order in stores | C:BW |

### itempropdef (60 x 8) and itemprops (60 x 27)

Item properties, one row each; rows = ITEM_PROPERTY_* (C:nss 58/59). Indexed by UTI
`PropertiesList/PropertyName`. How a property's text and numbers are found (C:BW, BW-ITM 4.3):
PropertyName -> itempropdef row; `subtyperesref` names the subtype table and UTI `Subtype` is a row
in it; UTI `CostTable` = itempropdef.costtableresref = iprp_costtable row, whose `name` names the
cost table, and UTI `CostValue` is a row in that; UTI `Param1` is an iprp_paramtable row whose
`tableresref` names the param table, and `Param1Value` is a row in that (255 = none).

itempropdef columns: name (strref, C:data 60/60), label, subtyperesref (2DA name: IPRP_*,
racialtypes, FEAT, SPELLS, Skills, Classes, TRAPS, Appearance, ...; C:data 20/20), cost (price
factor), costtableresref (iprp_costtable row, C:data 15/15), param1resref (iprp_paramtable row),
gamestrref and description (empty). All C:BW.

itemprops columns: `0_melee` .. `24_droidrepair` (1 = allowed for baseitems with that
propcolumn), stringref (= itempropdef.name of the same row, C:data), label. C:BW.

### iprp_* tables (41 tables)

Subtype, cost and param tables of item properties. Common columns (C:BW): `name` (strref of the
value text, often empty in KOTOR), `label`, `cost` (price factor), `value` (the number the property
applies). Extra columns are listed. Named by itempropdef.subtyperesref (S), iprp_costtable.name (C)
or iprp_paramtable.tableresref (P); "none" = not named by anything.

| Table | Size | Role | Extra columns / notes |
|---|---|---|---|
| iprp_costtable | 26 x 3 | list of cost tables (row = UTI CostTable) | name (2DA), label, clientload |
| iprp_paramtable | 12 x 3 | list of param tables (row = UTI Param1) | name (strref), label, tableresref (2DA) |
| iprp_abilities | 6 x 2 | S, P: the six abilities | |
| iprp_acmodtype | 5 x 2 | S: AC types | |
| iprp_aligngrp | 4 x 2 | S, P: All/Neutral/Light/Dark | |
| iprp_alignment | 9 x 2 | P: NWN alignments | name empty |
| iprp_ammocost | 16 x 6 | C | arrow, bolt, bullet (NWN UTI resrefs) |
| iprp_ammotype | 3 x 3 | S | ammotype = baseitems row (NWN arrows/bolts/bullets) |
| iprp_amount | 5 x 2 | P | |
| iprp_base1 | 0 x 3 | C | empty |
| iprp_bladecost | 6 x 3 | C | |
| iprp_bonuscost | 11 x 4 | C: +1..+10 | value |
| iprp_chargecost | 19 x 5 | C | potioncost, wandcost |
| iprp_color | 7 x 2 | P | |
| iprp_combatdam | 3 x 2 | S: bludgeon/pierce/slash | |
| iprp_damagecost | 11 x 7 | C | numdice, die, rank, gamestring |
| iprp_damagetype | 13 x 3 | S, P: in DAMAGE_TYPE bit order | cost |
| iprp_damvulcost | 8 x 4 | C | value (%), cost |
| iprp_feats | 21 x 4 | none: NWN feats | featindex empty |
| iprp_immuncost | 8 x 4 | C | value (%), cost |
| iprp_immunity | 10 x 3 | S | |
| iprp_lightcost | 5 x 3 | C | |
| iprp_meleecost | 6 x 4 | C | value, cost |
| iprp_monstcost | 58 x 5 | C | numdice, die |
| iprp_monsterhit | 9 x 5 | S | param1resref, param2resref (iprp_paramtable rows) |
| iprp_neg5cost, iprp_neg10cost | 6 x 4, 11 x 4 | C: penalties | value (negative) |
| iprp_onhit | 11 x 4 | S | param1resref (iprp_paramtable row, C:data 5/5) |
| iprp_onhitcost | 7 x 4 | C: save DCs | value |
| iprp_onhitdc | 5 x 3 | C | value |
| iprp_onhitdur | 9 x 5 | P | effectchance (%), durationrounds |
| iprp_poison | 6 x 2 | none (BIF only) | |
| iprp_protection | 5 x 3 | S | |
| iprp_redcost | 6 x 4 | C | value (fraction) |
| iprp_resistcost | 7 x 4 | C | amount; two rows labelled 0 |
| iprp_saveelement | 19 x 3 | S | namestring instead of label |
| iprp_savingthrow | 4 x 2 | S | namestring |
| iprp_slotscost | 0 x 2 | C | empty |
| iprp_soakcost | 7 x 4 | C | amount |
| iprp_spellcost | 188 x 4 | C | spellindex (NWN spell rows; 78/115 in range), labels from 1 |
| iprp_spelllvcost | 10 x 3 | C | |
| iprp_spelllvlimm | 10 x 3 | C | |
| iprp_spells | 336 x 10 | none (BIF only): NWN cast-spell list | casterlvl, innatelvl, cost, spellindex, potionuse, wanduse, generaluse, icon (no icons exist) |
| iprp_spellshl | 8 x 4 | none: NWN spell schools | letter |
| iprp_srcost | 12 x 4 | C | value |
| iprp_staminacost | 0 x 3 | C | empty |
| iprp_terraintype | 0 x 2 | none | empty |
| iprp_trapcost | 12 x 3 | none | |
| iprp_traps | 4 x 3 | none | |
| iprp_walk | 2 x 2 | S | |
| iprp_weightcost | 6 x 4 | C | value |
| iprp_weightinc | 6 x 3 | P | `lable` (sic), value |

### Upgrades and crystals

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| upgrade | 25 x 3 | label, template (UTI of the upgrade item, C:data 25/25), upgradetype (upgradetypes row, C:data 10/10) | C:data, *I* (role: list of workbench upgrades) |
| upgradetypes | 10 x 1 | Lightsaber_Upgrade, Vibration_Cell, Durasteel_Alloy, Energy_Projector, Scope, Imp_Energy_Cell, Beam_Splitter, Hair_Trigger, Armor_Reinforcement, Mesh_Underlay: the upgrade slot kinds | *I* |
| upcrystals | 7 x 5 | lightsaber colour crystals: label (BLUE, GOLD, ...), template (crystal UTI), shortmdlvar, longmdlvar, doublemdlvar (UTI of the short/normal/double lightsaber that shows this colour; all exist as UTI) | C:DS, C:data 7/7 each |

### Others

| Table | Size | Purpose | Status |
|---|---|---|---|
| itemvalue | 60 x 4 | NWN: level -> max item value (BW-ITM 4.5); every value 13500000, i.e. no limit | C:BW (role) |
| skillvsitemcost | 50 x 4 | NWN Lore check by item cost | C:BW, unused (BIF only) |
| treasurescale | 5 x 3 | NWN treasure scaling | unused |
| encumbrance | 51 x 2 | strength -> normal / heavy load (NWN) | unused (BIF only) |
| chargenclothes | 8 x 1 | NWN starting clothes (`NW_CLOTH00n`, none exist) | unused |
| defaultacsounds | 9 x 2 | NWN AC -> armour sound type | unused |
| comptypes | 2 x 2 | computer GUI backgrounds: label (Standard, Rakata), computerbackground (TPC) | C:DS, C:data |

## Rules: effects, combat, AI and factions

### visualeffects (144 x 29)

Visual effects keyed by row **label** = VFX id (C:nss: VFX_* constants equal the labels and their
names match the label column, 115/118). `type_fd`: F (fire and forget) 92, D (duration) 52.

| Column | Meaning | Status |
|---|---|---|
| label | VFX_* name | C:nss |
| type_fd | F = one-shot, D = lasts while the effect does | *I* |
| orientwithground, orientationoff | 0 / one row 1 | *I* |
| imp_headcon_node, imp_impact_node, imp_root_m_node | MDL attached to the head / impact / root node on impact | C:data 9/9, 43/51, 36/36 (NWN naming) |
| imp_root_s_node, imp_root_l_node, imp_root_h_node | | unused |
| progfx_impact, progfx_duration | *I*: id of an engine-programmed effect (1201..2001) | *I* |
| soundimpact, soundduration, soundcessastion (sic) | WAV on impact / while active / on end | C:data 42/43, 10/10, 2/3 |
| progfx_cessation, ces_*_node | | unused |
| shaketype, shakedelay, shakeduration | camera shake (2 rows) | *I* |
| lowviolence, lowquality | | unused |
| rumblepattern, rumblecutoff | rumble.2da row and cut-off distance | *I* |

### Effects and states

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| effecticon | 62 x 5 | effect icons shown on portraits: label, iconresref (TPC, C:data 61/61), good (1 beneficial), description (empty), priority (sort order). `SetEffectIcon(effect, nIcon)` takes the row (C:nss) | C:nss, C:data |
| effecticons | 107 x 3 | NWN effect icons (`ief_*`, none exist) | unused |
| gameeffects | 25 x 34 | one row per effect type (ENTANGLE, POISON, ..., CHOKE, STUN): flags per immunity category (all, mind, poison, ..., death): *I* which immunities block the effect | *I* |
| forceshields | 19 x 20 | rows = SHIELD_* (C:nss 18/18, `EffectForceShield(n)`): visualeffectdef (VFX label), defaultradius (-1), damageflags / vulnerflags (DAMAGE_TYPE masks), resistance, amount (points absorbed), permanent, then appearance_0N / visualeffect_0N / radius_0N: per-appearance override of the shield VFX for 4 droid appearances | C:nss, C:data, *I* |
| poison | 6 x 14 | rows = POISON_* (C:nss): label, dc_save, duration, period, dam_hp, dam_fp, dam_str..dam_chr (0/1 which ability drops), name (strref), abil_dur | C:nss, *I* |
| disease | 17 x 17 | NWN diseases (scripts missing) | unused |
| traps | 14 x 11 | rows = TRAP_BASE_TYPE_* (C:nss 12/12); indexed by UTT/UTP/UTD TrapType: label, trapscript (NCS), setdc, detectdcmod, disarmdcmod, trapname (strref), resref (trap kit UTI), iconresref (empty), name (strref), model (mine MDL), explosionsound (WAV) | C:BW, C:data |
| vfx_persistent | 3 x 30 | persistent area effects (Korriban heat/cold/electricity): label, shape (R), width, length, rest empty | C:BW-shape, *I* |
| areaeffects | 3 x 9 | NWN area effects (scripts missing) | unused |
| effectanim | 1 x 2 | id, radius | unused |
| removefxondeath | 2 x 2 | effects removed on death: label, effecttype (EFFECT_TYPE_* value: 62 disguise, 21 beam; C:nss) | C:nss, *I* |
| statescripts | 36 x 2 | state name -> heartbeat script (k_sup_static, k_sup_fear; most NWN ones missing) | *I* |
| excitedduration | 3 x 2 | None/Damage/SpellCast -> duration (ms, *I*: how long a creature stays "excited") | *I* |
| damagehitvisual | 13 x 3 | see [Animation](#weapon-and-impact-sounds) | |
| polymorph | 1 x 16 | one row POLYMORPH_TYPE_SITHSOLDIER: appearancetype 28, racialtype, portraitid, str/con/dex, naturalacbonus, hpbonus | *I* |
| crtemplates | 10 x 2 | NWN creature templates | unused |

### Combat and difficulty

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| ranges | 21 x 4 | label, primaryrange, secondaryrange (m), name (empty): spell ranges (Pers, Touch, Shrt, Med, Lng), weapon ranges, perception ranges (UTC PerceptionRange = row 8..11), party follow / escape / combat distances, trap radius | C:BW, C:data |
| encdifficulty | 5 x 3 | rows = ENCOUNTER_DIFFICULTY_* (C:nss): label, strref, value (added to the encounter level); UTE DifficultyIndex | C:BW, C:nss |
| difficultyopt | 4 x 3 | game difficulty options: name (strref), desc, multiplier | *I* |
| diffsettings | 6 x 6 | rules per difficulty: NoCriticalOnPC, NoAoOWithRanged, NoAoOWithPotion, MinPCDamagePercent, MaxNPCDamagePercent, MinHP1 by column dmeasy/easy/normal/hardcore/dmplayers | *I* |
| repute | 21 x 21 | faction standings 0..100: rows = factions (row = faction id, STANDARD_FACTION_*: C:nss 17/17), each column = how that faction feels about the row's faction | C:BW, C:nss |
| repadjust | 4 x 12 | Attack, Theft, Kill, Help: reputation changes and witness adjustments (all 0) | C:BW |
| aiscripts | 3 x 4 | party AI styles: label, name_strref, description_strref, aistate | C:DS, C:data |
| hen_companion, hen_familiar | 8 x 4 each | NWN animal companions / familiars (UTCs missing) | unused |

## World, audio and video

### surfacemat (31 x 7)

Walkmesh face materials: the material number stored for each face of a WOK/PWK/DWK walkmesh is a
row of this table (C:data: all 191,329 faces of 1554 walkmeshes use rows 1..19; area WOKs use
Dirt, Obscuring, Grass, Stone, Wood, Water, Nonwalk, Transparent, Carpet, Metal, Puddles, Mud,
DeepWater, NonWalkGrass; placeable and door walkmeshes only Dirt, Obscuring and Nonwalk). Rows:
NotDefined, Dirt, Obscuring, Grass, Stone, Wood, Water, Nonwalk, Transparent, Carpet, Metal,
Puddles, Swamp, Mud, Leaves, Lava, BottomlessPit, DeepWater, Door, NonWalkGrass, ten `CRAP`
placeholders (20..29), Trigger (30).

| Column | Meaning | Status |
|---|---|---|
| label | material name | *I* |
| walk | 1 = creatures may walk on it (Dirt, Grass, ..., Door, Trigger) | *I* |
| walkcheck | 1 = the face takes part in walkmesh tests (0 only for NotDefined, Obscuring, CRAP) | *I* |
| lineofsight | 1 = the face blocks line of sight (0 for Transparent, Door, Trigger) | *I* |
| grass | 1 = grass is drawn on it (Grass, NonWalkGrass) | *I* |
| sound | 2-letter surface code (DT dirt, GR grass, ST stone, WD wood, WT water, CP carpet, MT metal, LV leaves) | *I* |
| name | footstepsounds column group for steps on it (`dirt`, `grass`, ... lower-cased; Mud uses `puddles`) | C:data 9/9 |

### footstepsounds (11 x 35)

Footstep sounds by creature footstep type (row, from appearance.footsteptype) and surface
(column group, from surfacemat.name). label; rumblepattern, rumblecutoff (rumble.2da, 2 rows);
pitchoffset; rolling (continuous sound for wheeled/floating droids); dirt0..2, grass0..2, stone0..2,
wood0..2, water0..2, carpet0..2, metal0..2, puddles0..2, leaves0..2 (three variants picked at
random, C:BW); force1..3 (*I*: Force-speed steps). All WAV (C:data).

### appearancesndset (16 x 9)

Creature sound classes (appearance.soundapptype): label, armortype (`leather`/`armor`: weaponsounds
column used when the creature is hit, C:data), weapon (weaponsounds row for unarmed, C:data),
missindex, looping (empty), falldirt, fallhard, fallmetal, fallwater (body-fall WAVs, C:DS, C:data).

### Music and ambient sound

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| ambientmusic | 49 x 5 | description (strref), resource (WAV/MP3 in `streammusic/`), stinger1 (played when battle music ends), stinger2, stinger3 (empty). GIT MusicDay/MusicNight/MusicBattle; `MusicBackgroundChangeDay/Night` | C:BW, C:data 43/45 |
| ambientsound | 48 x 10 | description (strref), resource (looping WAV in `streamsounds/`), presetinstance0..7 (empty). GIT AmbientSndDay/Night | C:BW, C:data 44/44 |
| guisounds | 17 x 2 | GUI events -> WAV (Clicked_Default, Entered_Default, Error_Default, Checkbox_Check, panel added/removed, ...) | C:data |
| aliensound | 299 x 2 | alien VO lines: filename (WAV, 180/299 exist), comment; *I*: alien barks for conversations | *I* |
| soundset | 90 x 5 | label, resref (SSF, 89/89), strref (name), gender, type (empty). UTC SoundSetFile (65535 none) | C:BW, C:data |
| soundsettype | 5 x 2 | Player, Henchman, NPC-full, NPC-part, Monster | *I* |
| prioritygroups | 27 x 9 | sound priority classes (Unmaskable_Sound, Music_Stingers, ..., Bark_Bubbles): priority, volume (0..127), maxplaying, interrupt, fadetime (ms), maxvolumedist, minvolumedist, playbackvariance | *I* |
| soundgain | 15 x 4 | volume and min/max distance per sound category (footsteps, music, swing, ...) | *I*, BIF only |
| soundeax | 24 x 2 | EAX environment preset names (GENERIC, PADDEDCELL, ROOM, ...) | C:BW (role); EnvAudio values exceed it |
| soundprovider | 5 x 4 | Miles 3D providers: provider, eax level, hardware, 2d3dbias | *I* |
| soundcatfilters, sounddefaultspos, sounddefaultstim, soundtypes, rrf_wav | | toolset helpers (BIF only) | unused |

### Lighting, environment and camera

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| camerastyle | 9 x 16 | ARE CameraStyle (C:data): name, distance (m behind), pitch (deg), height (m), speed, tiltup, tiltdown, tiltspeed, rotation (rotation limit), viewangle (vertical FOV), maxturnrate, minturnrate, fl_tiltspeed, fl_rotatespeed, fl_lookup, fl_lookdown (free-look). Row 0 DEFAULT, 1 EbonHawk, 8 Combat | C:DS |
| environment | 24 x 42 | NWN lighting schemes (ambient/diffuse/fog colours day and night, weather) | C:BW (role); ARE LightingScheme always 0, BIF only: unused |
| videoeffects | 3 x 7 | rows = VIDEO_EFFECT_* (C:nss, `EnableVideoEffect`): label, enablesaturation, modulationred/green/blue (colour multipliers), saturation, enablescannoise (scan lines) | C:DS, C:nss |
| lightcolor | 32 x 7 | light presets (see Appearance) | C:BW |
| gamma | 3 x 4 | PAL/NTSC/HDTV gamma range: minimum, maximum, default | *I* |

## Game: globals, modules, saves, story

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| globalcat | 1185 x 2 | every global variable: name, type (Boolean 809, Number 369, Location 5, String 2). `GetGlobalBoolean/Number` take the name; saves store them (GLOBALVARS) | C:DS |
| plot | 75 x 2 | plot ids for `GivePlotXP(sPlotName, nPercentage)`: row label = plot id, xp, label | *I* |
| modulesave | 123 x 6 | per module (row label): modulename, includeinsave (0/1), autosaveonenter (yes/no/force), areaname (strref, C:data 87/87), savegroup, deletesavegrouponenter (*I*: drop older modules' state when entering a new planet group) | *I* |
| minglobalrim | 3 x 1 | modules that use rims/miniglobal.rim: stunt_57, ebo_m12aa, danm13 (all exist) | C:data, *I* |
| npc | 11 x 2 | party members, see [Progression](#progression-and-xp) | |
| planetary | 17 x 6 | galaxy map, rows = PLANET_* (C:nss 16/16): label, name, description (strrefs), icon (TPC), model (planet MDL), guitag (GUI control). Rows 11..16 are Xbox Live planets (assets missing) | C:nss, C:data |
| movies | 107 x 4 | row label = BIK name: strrefname (title in the movies menu), strrefdesc (empty), alwaysshow, order. 55/107 BIKs exist (Xbox Live and cut entries missing) | C:data, *I* |
| credits | 16 x 2 | label, name (strref with the credit text) | C:data |
| loadscreens | 12 x 2 | row label = module name (`default`, `classsel`, minigame modules): bmpresref (TPC), musicresref (WAV). ARE/UTD LoadScreenID are always 0 | C:data, *I* (lookup by module) |
| loadscreenhints | 91 x 2 | gameplayhint, storyhint (strrefs shown on loading screens) | C:data |
| loadhints | 28 x 3 | NWN | unused |
| stringtokens | 127 x 8 | dialogue tokens (`<Boy/Girl>`, `<Alignment>`, ...): token, actioncode (what it reads), default, strref1..4 (text variants; -1 none), category | *I* |
| dialogtokens | 6 x 1 | Xbox button tokens `<abutton>`.. -> fontcode | *I* |
| namefilter | 3 x 1 | forbidden names | *I* |
| feedbacktext | 3 x 2 | Resisted/Immune/Saved -> strref; `DisplayFeedBackText` | C:nss |
| tutorial | 43 x 5 | tutorial pop-ups: label, message0..2 (strrefs), icon (TPC) | C:data |
| tutorial_old | 42 x 5 | older copy | unused |
| cursors | 11 x 3 | label, resref (`gui_mp_*` texture, 3/10 exist under that name; the game has `..u`/`..d` pairs), cursorid. UTT Cursor | C:BW |

## GUI and options

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| keymap | 80 x 23 (patch) | key bindings, row label `action200`..: disabled, actionstrref, descstrref (strrefs, `*****` none), language0 (*I*: default key code), character (key name), page (options page 0..2), sortpos, name (action), remappable, forcedisplay, icpc, icminigame, icpcgui, icdialog, icfreelook, icmovie (*I*: active in that input context), repeatable, repeatwait, repeatrate (ms), scale, scalemag, scaleexp, eventtype (patch only) | *I*, C:data (strrefs) |
| bindablekeys | 103 x 3 (patch) | keys that can be bound: row label `key0`..: keynamestrref (strref), keyname (`KEYBOARD_*`), bindable | C:DS, C:data |
| texpacks | 3 x 6 | texture quality options: desc, texture (TexturePacks ERF: tpc/tpb/tpa), gui (swpc_tex_gui), strrefname, dynmemratio, mem (bytes) | C:data |
| videoquality | 9 x 5 | swkotor.ini graphics settings per preset: inilabel, fast, low, good, best (BIF only) | *I* |
| gamma | 3 x 4 | see above | |
| difficultyopt | 4 x 3 | see [Combat and difficulty](#combat-and-difficulty) | |
| guisounds | 17 x 2 | see [World, audio and video](#music-and-ambient-sound) | |

GUI layouts themselves are GFF `.gui` files, not 2DAs.

## Minigames

| Table | Size | Columns and meaning | Status |
|---|---|---|---|
| pazaakdecks | 4 x 11 | opponent side decks for `PlayPazaak(nOpponentPazaakDeck, ...)`: card0..card9 (`+n`, `-n`, `*n` = flip card, ...), deckname | C:nss (index), *I* (card notation) |

Swoop racing and the turret minigames have no 2DA of their own: their data is the ARE `MiniGame`
struct (track, enemies, gun banks, models, sounds) plus MGT/MGO models; loadscreens has rows for
their modules and keymap an `icminigame` flag.

## Probably unused (NWN and tool leftovers)

The 54 tables whose name is not a string in the exe and that no other table names (column
"Named" `-` in the index). Most hold NWN content that points at nothing in KOTOR:
actions, aliensound (180 of its 299 WAVs exist; may be read by scripts or the dialogue system),
areaeffects, caarmorclass, capart, catype, chargenclothes, cls_atk_3, combatmodes, crtemplates,
defaultacsounds, dialogtokens, domains, effectanim, effecticons, encumbrance, environment,
gamespyrooms (GameSpy rooms), hen_companion, hen_familiar, iprp_feats, iprp_poison, iprp_spells,
iprp_spellshl, iprp_terraintype, iprp_traps, loadhints, metamagic, minglobalrim, nwconfig and
nwconfig2 (NWN launcher system checks), placeabletypes, polymorph, pregen (NWN pre-made
characters), pvpsettings, replacetexture, rrf_nss, rrf_wav (toolset resource filters), rumble,
skillvsitemcost, soundcatfilters, sounddefaultspos, sounddefaultstim, soundeax, soundgain,
soundtypes, swingsounds, tilecolor, treasurescale, tutorial_old, upgradetypes, videoquality,
visemes, xpbaseconst. "Not named" is evidence, not proof: the exe may build a name at run time
(upgradetypes, rumble, minglobalrim and visemes all look live), so confirm with RE before
dropping one.

## Checked

Probe: `python kotor/tools/py/twoda_catalog.py` (about 4 s; writes `kotor/extract/2da-inventory.json`
and `.txt`; prints the summary quoted here). Readers: `twodapy.py` (V2.b, and V2.0 text, which the install
does not use; the text path was checked by rendering all 209 tables as text and parsing them back
to identical cells), `tlkpy.py` (dialog.tlk: 49265 strings), `gffpy.py` for the GFF checks.

- **Entries:** 519 2DA entries read from every source `kres.Game.every_entry()` sees (2da.bif,
  rims/*.rim, patch.erf, Override, modules, saves): 209 distinct tables, 7769 rows in total.
- **Parse failures: 0.** All 519 are `2DA V2.b`. 26 copies (13 tables x global.rim and
  miniglobal.rim) use NUL label terminators; their cells equal the BIF copy's.
- **Copies:** 155 tables have more than one copy. 276 copies are byte-identical to the profiled
  one, 26 differ only in label terminators, 8 differ in content (the 4 patch.erf tables against the
  BIF and RIM copies, listed under [Where the tables live](#where-the-tables-live)).
- **Table -> resource checks** (distinct values found as a resource of the expected type among every
  container plus `streammusic/`, `streamsounds/`, `streamwaves/`, `movies/`, `modules/`,
  `TexturePacks/`, `lips/`): the hit rates in the [cross-reference map](#table-to-resource).
  Highlights: appearance.race 128/128 MDL, modela 60/61, texa 79/83 as `<value>01`, heads.head
  106/107, heads.headtex* 30/30, portraits.baseresref 40/40, placeables.modelname 215/221,
  genericdoors.modelname 52/63, feat.icon 119/119, spells.iconresref 55/55, ambientsound.resource
  44/44, ambientmusic.resource 43/45, footstepsounds 100% but force1 3/4, soundset.resref 89/89,
  upcrystals 7/7 UTI per column, baseitems.itemclass 83/87 icons `i<class>_001`. Misses that mark
  unused data: doortypes.model 0/66, classes.icon 0/8, baseitems.defaulticon 1/17,
  effecticons.icon 0/69, iprp_spells.icon 0/203, NWN script and blueprint columns 0/n.
- **Table -> table checks:** every row/label/column reference in the [map](#table-to-table) resolves
  (100%) except appearance.racialtype (always 20) and the NWN spell indices in iprp_spells (120/211)
  and iprp_spellcost (78/115).
- **Strref checks:** every listed strref column resolves 100% except movies.strrefname 67/107,
  planetary.name 12/17 and .description 9/14 (Xbox Live rows) and keymap's `*****` placeholder.
- **GFF -> table checks:** 1958 UTC, 1784 UTP, 575 UTD, 1055 UTI, 1121 UTT, 133 UTE, 2058 UTW, 117
  ARE, 117 GIT, 1167 DLG (every copy in the default resource view). All listed fields are in range
  except: UTC Race 8 (1 use), UTC SpecAbilityList spell 299 (1), UTD PortraitId 558 (2), UTI
  UpgradeType (452 of 922 above upgradetypes' 10 rows: not that table), ARE/GIT EnvAudio (values up
  to 92, soundeax has 24 rows: not that table), DLG animations 10001 and 10048 (unnamed rows).
- **Walkmesh materials:** the face material of every WOK (1202 files, 189,588 faces), PWK (196,
  765) and DWK (156, 976) is a surfacemat row (1..19); 0 out of range. The probe reads the face
  count and material-array offset from bytes 80 and 88 of the `BWM V1.0` header.
- **nwscript.nss constants:** see [the section above](#nwscriptnss-constants-to-rows).
- **Exe strings:** 108 of the 209 names appear as strings in the unpacked `swkotor.exe`
  (`kotor/re/bin/swkotor_unpacked.exe`); 47 more are named by another table (cls_atk_*, cls_st_*,
  iprp_* via itempropdef/iprp_costtable/iprp_paramtable). The remaining 54 are the [probably unused](#probably-unused-nwn-and-tool-leftovers) list.

Open questions (for RE): index vs label lookup for ambientsound/environment/effecticon; the search
order of BIF, global.rim and patch.erf; what UTI `UpgradeType` and ARE `EnvAudio` index;
surfacemat's `sound`/`walkcheck`/`lineofsight` semantics; the `<cls>_list` codes in feat.2da.

## Index of all tables

rim: the table is also in rims/global.rim (and miniglobal.rim); patch: also in patch.erf.
named: `exe` = the name is a string in swkotor.exe, `table` = named by another table, `-` = neither.
labels: row labels are not `0..n-1`.

| Table | Rows | Cols | Where | Named | Labels | Section |
|---|---|---|---|---|---|---|
| acbonus | 21 | 6 | bif, rim | exe |  | Creatures |
| actions | 39 | 3 | bif | - |  | Leftovers |
| aiscripts | 3 | 4 | bif, rim | exe |  | Effects/combat |
| aliensound | 299 | 2 | bif | - |  | World/audio |
| ambientmusic | 49 | 5 | bif, rim | exe |  | World/audio |
| ambientsound | 48 | 10 | bif, rim | exe | yes | World/audio |
| ammunitiontypes | 6 | 10 | bif, rim | exe |  | Animation |
| animations | 394 | 15 | bif, rim | exe |  | Animation |
| appearance | 509 | 80 | bif, rim | exe |  | Appearance |
| appearancesndset | 16 | 9 | bif, rim | exe |  | World/audio |
| areaeffects | 3 | 9 | bif | - |  | Effects/combat |
| baseitems | 92 | 61 | bif, rim | exe |  | Items |
| bindablekeys | 103 | 3 | bif, patch | exe | yes | GUI |
| bodybag | 10 | 4 | bif, rim | exe |  | Appearance |
| caarmorclass | 8 | 2 | bif | - |  | Appearance |
| camerastyle | 9 | 16 | bif, rim | exe |  | World/audio |
| capart | 18 | 3 | bif | - |  | Appearance |
| categories | 15 | 1 | bif | exe | yes | Feats/powers |
| catype | 5 | 2 | bif | - |  | Appearance |
| chargenclothes | 8 | 1 | bif | - |  | Items |
| classes | 9 | 49 | bif, rim | exe |  | Creatures |
| classpowergain | 20 | 4 | bif, rim | exe |  | Creatures |
| cls_atk_1 | 20 | 1 | bif, rim | table |  | Creatures |
| cls_atk_2 | 20 | 1 | bif, rim | table |  | Creatures |
| cls_atk_3 | 60 | 1 | bif | - |  | Creatures |
| cls_spgn_jedi | 20 | 9 | bif, rim | exe |  | Creatures |
| cls_st_cm_drd | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_ex_drd | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_jedi_c | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_jedi_g | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_jedi_s | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_minion | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_scndrl | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_scout | 20 | 4 | bif, rim | table |  | Creatures |
| cls_st_soldier | 20 | 4 | bif, rim | table |  | Creatures |
| combatanimations | 58 | 31 | bif, rim | exe | yes | Animation |
| combatmodes | 4 | 1 | bif | - |  | Feats/powers |
| comptypes | 2 | 2 | bif, rim | exe |  | Items |
| creaturesize | 6 | 3 | bif | exe |  | Creatures |
| creaturespeed | 12 | 5 | bif, rim | exe |  | Creatures |
| credits | 16 | 2 | bif, rim | exe |  | Game |
| crtemplates | 10 | 2 | bif | - |  | Effects/combat |
| cursors | 11 | 3 | bif, rim | exe |  | Game |
| damagehitvisual | 13 | 3 | bif, rim | exe |  | Animation |
| defaultacsounds | 9 | 2 | bif | - |  | Items |
| dialoganimations | 227 | 6 | bif, rim | exe |  | Animation |
| dialogtokens | 6 | 1 | bif | - | yes | Game |
| difficultyopt | 4 | 3 | bif, rim | exe |  | Effects/combat |
| diffsettings | 6 | 6 | bif, rim | exe |  | Effects/combat |
| disease | 17 | 17 | bif, rim | exe |  | Effects/combat |
| domains | 22 | 15 | bif | - |  | Feats/powers |
| doortypes | 69 | 8 | bif, rim | exe |  | Appearance |
| droiddischarge | 15 | 3 | bif, rim | exe | yes | Animation |
| effectanim | 1 | 2 | bif | - |  | Effects/combat |
| effecticon | 62 | 5 | bif, rim | exe | yes | Effects/combat |
| effecticons | 107 | 3 | bif | - |  | Effects/combat |
| encdifficulty | 5 | 3 | bif, rim | exe |  | Effects/combat |
| encumbrance | 51 | 2 | bif | - |  | Items |
| environment | 24 | 42 | bif | - | yes | World/audio |
| excitedduration | 3 | 2 | bif, rim | exe |  | Effects/combat |
| exptable | 21 | 2 | bif, rim | exe |  | Creatures |
| feat | 125 | 60 | bif, rim | exe |  | Feats/powers |
| featgain | 20 | 17 | bif, rim | exe |  | Creatures |
| feedbacktext | 3 | 2 | bif, rim | exe |  | Game |
| footstepsounds | 11 | 35 | bif, rim | exe |  | World/audio |
| forceadjust | 11 | 2 | bif, rim | exe |  | Creatures |
| forceshields | 19 | 20 | bif, rim | exe |  | Effects/combat |
| formations | 3 | 21 | bif, rim | exe |  | Animation |
| fractionalcr | 5 | 4 | bif, rim | exe |  | Creatures |
| gameeffects | 25 | 34 | bif, rim | exe |  | Effects/combat |
| gamespyrooms | 12 | 3 | bif | - |  | Leftovers |
| gamma | 3 | 4 | bif, rim | exe |  | World/audio |
| gender | 5 | 4 | bif, rim | exe |  | Creatures |
| genericdoors | 65 | 10 | bif, rim | exe |  | Appearance |
| globalcat | 1185 | 2 | bif, rim | exe |  | Game |
| grenadesnd | 31 | 2 | bif, rim | exe |  | Animation |
| guisounds | 17 | 2 | bif, rim | exe |  | World/audio |
| heads | 107 | 7 | bif, rim | exe |  | Appearance |
| hen_companion | 8 | 4 | bif, rim | - |  | Effects/combat |
| hen_familiar | 8 | 4 | bif, rim | - |  | Effects/combat |
| inventorysnds | 33 | 2 | bif, rim | exe |  | Animation |
| iprp_abilities | 6 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_acmodtype | 5 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_aligngrp | 4 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_alignment | 9 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_ammocost | 16 | 6 | bif, rim | table |  | Items (iprp) |
| iprp_ammotype | 3 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_amount | 5 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_base1 | 0 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_bladecost | 6 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_bonuscost | 11 | 4 | bif, rim | exe |  | Items (iprp) |
| iprp_chargecost | 19 | 5 | bif, rim | table |  | Items (iprp) |
| iprp_color | 7 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_combatdam | 3 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_costtable | 26 | 3 | bif, rim | exe |  | Items (iprp) |
| iprp_damagecost | 11 | 7 | bif, rim | exe |  | Items (iprp) |
| iprp_damagetype | 13 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_damvulcost | 8 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_feats | 21 | 4 | bif, rim | - |  | Items (iprp) |
| iprp_immuncost | 8 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_immunity | 10 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_lightcost | 5 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_meleecost | 6 | 4 | bif, rim | exe |  | Items (iprp) |
| iprp_monstcost | 58 | 5 | bif, rim | exe |  | Items (iprp) |
| iprp_monsterhit | 9 | 5 | bif, rim | table |  | Items (iprp) |
| iprp_neg10cost | 11 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_neg5cost | 6 | 4 | bif, rim | exe |  | Items (iprp) |
| iprp_onhit | 11 | 4 | bif, rim | exe |  | Items (iprp) |
| iprp_onhitcost | 7 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_onhitdc | 5 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_onhitdur | 9 | 5 | bif, rim | exe |  | Items (iprp) |
| iprp_paramtable | 12 | 3 | bif, rim | exe |  | Items (iprp) |
| iprp_poison | 6 | 2 | bif | - |  | Items (iprp) |
| iprp_protection | 5 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_redcost | 6 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_resistcost | 7 | 4 | bif, rim | table | yes | Items (iprp) |
| iprp_saveelement | 19 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_savingthrow | 4 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_slotscost | 0 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_soakcost | 7 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_spellcost | 188 | 4 | bif, rim | table | yes | Items (iprp) |
| iprp_spelllvcost | 10 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_spelllvlimm | 10 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_spells | 336 | 10 | bif | - |  | Items (iprp) |
| iprp_spellshl | 8 | 4 | bif | - |  | Items (iprp) |
| iprp_srcost | 12 | 4 | bif, rim | exe |  | Items (iprp) |
| iprp_staminacost | 0 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_terraintype | 0 | 2 | bif | - |  | Items (iprp) |
| iprp_trapcost | 12 | 3 | bif, rim | table |  | Items (iprp) |
| iprp_traps | 4 | 3 | bif | - |  | Items (iprp) |
| iprp_walk | 2 | 2 | bif, rim | table |  | Items (iprp) |
| iprp_weightcost | 6 | 4 | bif, rim | table |  | Items (iprp) |
| iprp_weightinc | 6 | 3 | bif, rim | table |  | Items (iprp) |
| itempropdef | 60 | 8 | bif, rim | exe |  | Items |
| itemprops | 60 | 27 | bif, rim | exe |  | Items |
| itemvalue | 60 | 4 | bif, rim | exe |  | Items |
| keymap | 80 | 23 | bif, patch | exe | yes | GUI |
| lightcolor | 32 | 7 | bif, rim | exe |  | Appearance |
| loadhints | 28 | 3 | bif | - |  | Game |
| loadscreenhints | 91 | 2 | bif, rim | exe |  | Game |
| loadscreens | 12 | 2 | bif, rim | exe | yes | Game |
| masterfeats | 3 | 4 | bif, rim | exe |  | Feats/powers |
| metamagic | 7 | 4 | bif | - |  | Feats/powers |
| minglobalrim | 3 | 1 | bif, rim | - |  | Game |
| modulesave | 123 | 6 | bif, rim | exe | yes | Game |
| movies | 107 | 4 | bif, rim | exe | yes | Game |
| namefilter | 3 | 1 | bif, rim | exe |  | Game |
| npc | 11 | 2 | bif, rim | exe |  | Creatures |
| nwconfig | 7 | 13 | bif, rim | - |  | Leftovers |
| nwconfig2 | 7 | 4 | bif, rim | - |  | Leftovers |
| pazaakdecks | 4 | 11 | bif, rim | exe |  | Minigames |
| phenotype | 3 | 2 | bif | exe |  | Appearance |
| placeableobjsnds | 70 | 7 | bif, rim | exe |  | Appearance |
| placeables | 232 | 17 | bif, rim | exe |  | Appearance |
| placeabletypes | 9 | 2 | bif | - |  | Appearance |
| planetary | 17 | 6 | bif, rim | exe |  | Game |
| plot | 75 | 2 | bif, rim | exe | yes | Game |
| poison | 6 | 14 | bif, rim | exe |  | Effects/combat |
| polymorph | 1 | 16 | bif | - |  | Effects/combat |
| portraits | 41 | 14 | bif, rim | exe |  | Appearance |
| pregen | 23 | 2 | bif | - |  | Leftovers |
| prioritygroups | 27 | 9 | bif, rim | exe |  | World/audio |
| pvpsettings | 4 | 3 | bif | - |  | Leftovers |
| racialtypes | 7 | 22 | bif, rim | exe |  | Creatures |
| ranges | 21 | 4 | bif, rim | exe |  | Effects/combat |
| regeneration | 2 | 3 | bif, rim | exe |  | Creatures |
| removefxondeath | 2 | 2 | bif, rim | exe |  | Effects/combat |
| repadjust | 4 | 12 | bif, rim | exe |  | Effects/combat |
| replacetexture | 2 | 1 | bif | - |  | Appearance |
| repute | 21 | 21 | bif, rim | exe |  | Effects/combat |
| rrf_nss | 15 | 3 | bif | - |  | Leftovers |
| rrf_wav | 19 | 3 | bif | - |  | World/audio |
| rumble | 22 | 32 | bif, rim | - |  | Animation |
| skills | 8 | 30 | bif, rim, patch | exe |  | Feats/powers |
| skillvsitemcost | 50 | 4 | bif | - |  | Items |
| soundcatfilters | 14 | 2 | bif | - |  | World/audio |
| sounddefaultspos | 3 | 6 | bif | - |  | World/audio |
| sounddefaultstim | 5 | 8 | bif | - |  | World/audio |
| soundeax | 24 | 2 | bif | - |  | World/audio |
| soundgain | 15 | 4 | bif | - |  | World/audio |
| soundprovider | 5 | 4 | bif | exe |  | World/audio |
| soundset | 90 | 5 | bif, rim | exe |  | World/audio |
| soundsettype | 5 | 2 | bif, rim | exe |  | World/audio |
| soundtypes | 2 | 2 | bif | - |  | World/audio |
| spells | 132 | 53 | bif, rim | exe |  | Feats/powers |
| statescripts | 36 | 2 | bif, rim | exe |  | Effects/combat |
| stringtokens | 127 | 8 | bif | exe | yes | Game |
| subrace | 3 | 1 | bif | exe |  | Creatures |
| surfacemat | 31 | 7 | bif, rim | exe |  | World/audio |
| swingsounds | 9 | 3 | bif | - | yes | Animation |
| texpacks | 3 | 6 | bif | exe |  | GUI |
| tilecolor | 16 | 3 | bif | - |  | Appearance |
| traps | 14 | 11 | bif, rim | exe |  | Effects/combat |
| treasurescale | 5 | 3 | bif | - |  | Items |
| tutorial | 43 | 5 | bif, rim | exe |  | Game |
| tutorial_old | 42 | 5 | bif | - |  | Game |
| upcrystals | 7 | 5 | bif, rim | exe |  | Items |
| upgrade | 25 | 3 | bif, rim | exe |  | Items |
| upgradetypes | 10 | 1 | bif, rim | - |  | Items |
| vfx_persistent | 3 | 30 | bif, rim | exe |  | Effects/combat |
| videoeffects | 3 | 7 | bif, rim | exe |  | World/audio |
| videoquality | 9 | 5 | bif | - |  | GUI |
| visemes | 16 | 3 | bif | - | yes | Animation |
| visualeffects | 144 | 29 | bif, rim | exe | yes | Effects/combat |
| waypoint | 5 | 3 | bif | exe |  | Appearance |
| weapondischarge | 64 | 16 | bif, rim, patch | exe | yes | Animation |
| weaponsounds | 4 | 29 | bif, rim | exe |  | Animation |
| xpbaseconst | 17 | 3 | bif | - |  | Creatures |
| xptable | 20 | 22 | bif, rim | exe |  | Creatures |
