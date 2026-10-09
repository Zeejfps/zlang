# GFF schemas: save games

Conventions, path notation and columns: [gff-schemas.md](gff-schemas.md). Only one save exists
in the install (`Saves/000002 - Game1`, made on the Endar Spire), so every "Files" count below is
1 and value ranges are single samples: the shapes are certain, the value ranges are not. Meanings
follow BioWare's NWN documents (IFO, Area, Creature, "Common GFF Structs": VarTable, EffectList,
EventQueue, ActionList, ScriptSituation) where they apply; the rest is *(inferred)*.

## Layout of a save

A save is a directory `Saves/NNNNNN - <name>/` holding:

| File | What |
|---|---|
| `savenfo.res` | GFF `NFO `: what the load screen shows (name, area, time played, portraits) |
| `PARTYTABLE.res` | GFF `PT  `: party, gold, XP pool, journal states, pazaak deck, message logs |
| `GLOBALVARS.res` | GFF `GVT `: every global boolean, number, location and string |
| `SAVEGAME.sav` | ERF (signature `MOD V1.0`, not `SAV`) with the rest, below |
| `Screen.tga` | 256x256 24-bit uncompressed TGA thumbnail |

`SAVEGAME.sav` holds, for this save: `availnpc0.utc` (the stored state of party NPC slot 0; one
`availnpcN.utc` per NPC that has joined), `inventory.res` (GFF `INV `: the party inventory),
`repute.fac` (faction standings, same schema as a module's FAC) and one nested ERF per visited
module, `<module>.sav` (also `MOD V1.0`), with that module's `module.ifo`, `<area>.are` and
`<area>.git` in their saved form. Loading a module that has a nested `.sav` reads these instead of
the module's own IFO/ARE/GIT; the blueprints still come from the module RIMs.

## Shared save-time structs

These appear on every saved object (creatures, doors, placeables, triggers, waypoints, sounds,
the module and the area); they are described once, in the `availnpc0.utc` table below.

- **ObjectId**: the object's runtime id. Ids are DWORDs allocated from `Mod_NextObjId0` (module
  IFO); 0x7F000000 is OBJECT_INVALID and the player is 0x7FFFFFFF in this save. References
  between saved objects (`CreatorId`, `PerceptionList/ObjectId`, `AreaId`, `ReactObject`, stack
  values of type object) use these ids.
- **SWVarTable** (KOTOR's local variables): `BitArray` is 3 DWORDs of local booleans and
  `ByteArray` 8 bytes of local numbers (`GetLocalBoolean`/`GetLocalNumber`; nwscript.nss documents
  indexes 0..63 and 0 only). Which bit of which DWORD is boolean *i* is not settled by this save
  *(unverified; LSB-first in DWORD i/32 is the natural guess)*. `VarTable` (NWN's named locals)
  is always empty.
- **EffectList**: active effects: `Type`/`SubType` (engine effect ids, not nwscript constants),
  `Duration`, expiry `ExpireDay`/`ExpireTime`, `CreatorId`, `SpellId` (0xFFFFFFFF none) and the
  effect's parameters as four typed lists (8 ints, 4 floats, 6 strings, 4 objects in every
  effect here).
- **ActionList**: the object's queued actions: `ActionId` (engine action type), `GroupActionId`,
  `NumParams` and `Paramaters` (misspelt in the data, as BioWare notes), each a `Type` and a
  `Value`: 1 INT, 2 FLOAT, 3 DWORD object id, 4 CExoString, 5 a script situation struct.
- **Script situation** (`ActionList/Paramaters/Value` for `ActionDoCommand`-style actions, and
  `EventQueue/EventData` for `DelayCommand`): the suspended NCS state. Checked against the NCS
  files: `Code` is the entire code of the script named by `Name` (its NCS file without the
  13-byte header, so `CodeSize` = file size - 13), `InstructionPtr` is the offset in that code
  of the deferred block's first instruction (the `STORE_STATE`'s file offset + 16 - 13), and
  `Stack` holds exactly what that `STORE_STATE` saved: `BasePointer` = its `bp_bytes` / 4 (the
  globals) and `StackPointer` = (`bp_bytes` + `sp_bytes`) / 4 (checked: 760 + 16 bytes -> 190
  and 194 cells; 0 + 0 -> an empty stack). The stack is a list of `StackPointer` cells,
  each a struct (id = index) with `Type` and `Value`: 3 int, 4 float, 5 string, 6 object id, and
  0x10 + n for engine types (16 effect, 17 event, 18 location, 19 talent: the NCS type codes),
  stored as a `GameDefinedStrct` sub-struct (an effect here, with the EffectList fields).
  `BasePointer` and `StackPointer` are in cells. A VM that saves its state must write exactly
  this; see [ncs.md](ncs.md) for `STORE_STATE`.
- **EventQueue** (module IFO): pending timed events: `Day`/`Time` when it fires (game calendar
  day and milliseconds), `ObjectId` target, `CallerId`, `EventId` (1 = timed event, i.e. a
  `DelayCommand`, per BioWare's table) and `EventData` (struct id 0x7777 = script situation).

## savenfo.res (NFO)

<!-- gff-table save:NFO -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `AREANAME` | CExoString | all | e.g. `Endar Spire - Com…` | Area name shown in the load list. |
| `LASTMODULE` | CExoString | all | e.g. `END_M01AA` | Module to load (upper case resref). |
| `TIMEPLAYED` | DWORD | all | 883 | Seconds played. |
| `CHEATUSED` | BYTE | all | 0 | 1 if cheats were used. |
| `SAVEGAMENAME` | CExoString | all | e.g. `wadsd` | Name the player typed. |
| `GAMEPLAYHINT` | BYTE | all | 2 | The loading screen's next `loadscreenhints.2da` gameplay row: the client's round-robin counter (`PickLoadScreenHint` `0x005f4760`, client `+0x490`), written by `DoSaveGame` and put back by `LoadSelectedGame` (`0x006cb0e0`) and `QuickLoad`. |
| `STORYHINT` | BYTE | all | 2 | The same for the story column (client `+0x491`). |
| `LIVE1` | CExoString | all | always empty | Xbox Live content slot; empty on PC. |
| `LIVE2` | CExoString | all | always empty | Xbox Live content slot. |
| `LIVE3` | CExoString | all | always empty | Xbox Live content slot. |
| `LIVE4` | CExoString | all | always empty | Xbox Live content slot. |
| `LIVE5` | CExoString | all | always empty | Xbox Live content slot. |
| `LIVE6` | CExoString | all | always empty | Xbox Live content slot. |
| `LIVECONTENT` | BYTE | all | 0 | Xbox Live content bits; 0. |
| `PORTRAIT0` | ResRef | all | e.g. `po_pmhc4` | Portrait texture of party member 0 (the PC) for the load screen. |
| `PORTRAIT1` | ResRef | all | e.g. `po_ptrask` | Portrait of party member 1 (PORTRAIT2 when there are three). |
<!-- /gff-table -->

## PARTYTABLE.res (PT)

NPC slots are the rows of `npc.2da` (0 Bastila, 1 Canderous, 2 Carth, 3 HK-47, 4 Jolee, 5 Juhani,
6 Mission, 7 T3-M4, 8 Zaalbar); a member id of -1 is the PC *(inferred)*.

<!-- gff-table save:PT -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `PT_GOLD` | DWORD | all | 63 | Party credits. |
| `PT_XP_POOL` | INT | all | 450 | Shared party XP. |
| `PT_PLAYEDSECONDS` | DWORD | all | 883 | Seconds played. |
| `PT_CONTROLLED_NP` | INT | all | -1 | NPC slot that `SwitchPlayerCharacter` made the player character; -1 normally. Not the Tab-selected leader (that is `PT_IS_LEADER`). Written as `PT_CONTROLLED_NPC`, truncated to 16 characters by the GFF writer ([re/party-items-saves.md](../re/party-items-saves.md) 1.9). |
| `PT_SOLOMODE` | BYTE | all | 0 | 1 in solo mode. |
| `PT_CHEAT_USED` | BYTE | all | 0 | 1 if cheats were used. |
| `PT_NUM_MEMBERS` | BYTE | all | 1 | Members in the active party besides the PC *(inferred; 1 = Trask here)*. |
| `PT_MEMBERS` | List | all | 1 entries; struct id 0 | Active party members. |
| `PT_MEMBERS/PT_MEMBER_ID` | INT | all | 0 | NPC slot (row of `npc.2da`). |
| `PT_MEMBERS/PT_IS_LEADER` | BYTE | all | 0 | 1 if the party leader. |
| `PT_AVAIL_NPCS` | List | all | 9 entries; struct id 0 | One struct per NPC slot (9). |
| `PT_AVAIL_NPCS/PT_NPC_AVAIL` | BYTE | all | 0, 1 | The slot's "available" flag. `RemoveAvailableNPC` clears it but leaves `AVAILNPCn.utc` on disk, so a 0 can sit next to an existing file. |
| `PT_AVAIL_NPCS/PT_NPC_SELECT` | BYTE | all | 1 | 1 if selectable in the party screen. |
| `PT_AISTATE` | INT | all | 0 | Party AI setting *(inferred)*. |
| `PT_FOLLOWSTATE` | INT | all | 0 | Party follow setting *(inferred)*. |
| `GlxyMap` | Struct | all | struct id 0 | Galaxy map state. |
| `GlxyMap.GlxyMapNumPnts` | DWORD | all | 16 | Number of planets on the map (16). |
| `GlxyMap.GlxyMapPlntMsk` | DWORD | all | 0 | Bits 0–15: planet *n* available; bits 16–31: planet *n* selectable. Ignored on load unless `GlxyMapNumPnts` is 16; loading only sets flags, a clear bit leaves the flag as it was. |
| `GlxyMap.GlxyMapSelPnt` | INT | all | -1 | Selected planet; -1 none. |
| `PT_PAZAAKCARDS` | List | all | 19 entries; struct id 0 | Pazaak side cards owned: 18 INT counts, one per card type, then a stray 19th BYTE that repeats `PT_CHEAT_USED` (a writer slip; the engine reads only 18). Write the same to match. |
| `PT_PAZAAKCARDS/PT_PAZAAKCOUNT` | BYTE/INT | all | 0, 2 | Number owned. |
| `PT_PAZSIDELIST` | List | all | 10 entries; struct id 0 | The 10 slots of the chosen side deck. |
| `PT_PAZSIDELIST/PT_PAZSIDECARD` | INT | all | -1 | Card type in the slot; -1 empty. |
| `PT_TUT_WND_SHOWN` | VOID | all | sizes 6 | Bit set of tutorial pop-ups already shown (6 bytes): the in-game GUI's tutorial-shown flags. |
| `PT_LAST_GUI_PNL` | INT | all | 7 | The in-game GUI's current menu number (`CGuiInGame` `+0x2c`, 0 equipment .. 7 options; it stays when the menu closes, 0 before any opens): 7 for a save from the options menu, the last menu seen for a quick save (6 in one of the install's). |
| `PT_FB_MSG_LIST` | List | all | 64 entries; struct id 0 | Feedback (combat) message log. |
| `PT_FB_MSG_LIST/PT_FB_MSG_MSG` | CExoString | all | e.g. `Defense Breakdown…`, `Defense Breakdown…`, `Damage Breakdown:…` | Message text. |
| `PT_FB_MSG_LIST/PT_FB_MSG_TYPE` | DWORD | all | 128 | Message category. |
| `PT_FB_MSG_LIST/PT_FB_MSG_COLOR` | BYTE | all | 0, 1 | Colour index. |
| `PT_DLG_MSG_LIST` | List | all | 35 entries; struct id 0 | Dialogue log. |
| `PT_DLG_MSG_LIST/PT_DLG_MSG_SPKR` | CExoString | all | 2 empty; e.g. `Trask`, `Dunta Mothma`, `Carth` | Speaker name. |
| `PT_DLG_MSG_LIST/PT_DLG_MSG_MSG` | CExoString | all | e.g. `  `, `Okay.`, `Combat is real ti…` | Line text. |
| `PT_COST_MULT_LIS` | List | all | 92 entries; struct id 0 | Per-base-item price multipliers, one float per `baseitems.2da` row, set by `ChangeItemCost` (routine 747); 1.0 when absent. Written as `PT_COST_MULT_LIST`, truncated to 16 characters. |
| `PT_COST_MULT_LIS/PT_COST_MULT_VAL` | FLOAT | all | 1 | Multiplier. |
| `JNL_SortOrder` | INT | all | 0 | Journal sort setting. |
| `JNL_Entries` | List | all | 1 entries; struct id 0 | Current state of every started quest. |
| `JNL_Entries/JNL_PlotID` | CExoString | all | e.g. `end_attack` | Quest tag (`Categories/Tag` in global.jrl). |
| `JNL_Entries/JNL_State` | INT | all | 20 | Current entry `ID`. |
| `JNL_Entries/JNL_Date` | DWORD | all | 450438 | Game day the state was set. |
| `JNL_Entries/JNL_Time` | DWORD | all | 777199 | Game time (ms) the state was set. |
<!-- /gff-table -->

## GLOBALVARS.res (GVT)

Global variables are the rows of `globalcat.2da` (809 booleans, 369 numbers, 5 locations,
2 strings). The save stores its own name lists (`Cat*`) and packed values (`Val*`), indexed by
position in its own list: the save's boolean names are the same set as `globalcat.2da`'s but in a
different order, so map by name, never by 2DA row. Numbers are one byte each, signed
(−128..127: written as the low byte of the script value, read back sign-extended). Locations are 6 floats (position x, y, z, orientation x, y, z) each, in a block
always 2400 bytes (100 slots; those after the last location are zero). Booleans are packed 8 per byte, most significant bit
first: boolean *k* of `CatBoolean` is bit `0x80 >> (k & 7)` of byte `k >> 3` of `ValBoolean`, which
is `count/8 + 1` bytes (809 bits in 102 bytes). The name order is the engine's hash-table order
([re/party-items-saves.md](../re/party-items-saves.md) 2), which our writer reproduces. A location's
orientation is stored as given: one set with facing 0 saves as (1, 0, 0) (the install's
`K_LAST_LOCATION` at the origin), one never set as zeros, so a reader has to keep the difference to
write the file back as it was.

<!-- gff-table save:GVT -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `CatBoolean` | List | all | 809 entries; struct id 0 | Names of the boolean globals. |
| `CatBoolean/Name` | CExoString | all | e.g. `Tar_GortonAl`, `Dan_Blaster`, `UNK_GUARD_DOWN` | Global name. |
| `CatNumber` | List | all | 369 entries; struct id 0 | Names of the number globals. |
| `CatNumber/Name` | CExoString | all | e.g. `G_Party_Init_Trig`, `KOR_KNOW_EXCAV`, `MIN_TIME_MIN` | Global name. |
| `CatLocation` | List | all | 5 entries; struct id 0 | Names of the location globals. |
| `CatLocation/Name` | CExoString | all | e.g. `TAR_DUELCUT_START2`, `K_LAST_LOCATION`, `TAR_DUELCUT_START1` | Global name. |
| `CatString` | List | all | 2 entries; struct id 0 | Names of the string globals. |
| `CatString/Name` | CExoString | all | e.g. `K_STUNT_MODULE`, `K_LAST_MODULE` | Global name. |
| `ValBoolean` | VOID | all | sizes 102 | Packed booleans, one bit per `CatBoolean` entry. |
| `ValNumber` | VOID | all | sizes 369 | One byte per `CatNumber` entry. |
| `ValLocation` | VOID | all | sizes 2400 | 24 bytes (6 floats) per `CatLocation` entry. |
| `ValString` | List | all | 2 entries; struct id 0 | One struct per `CatString` entry. |
| `ValString/String` | CExoString | all | always empty | The value. |
<!-- /gff-table -->

## inventory.res (INV)

The party inventory: `ItemList` of full item structs (all UTI fields, plus those below; struct id
0). Only the fields a UTI blueprint does not have are listed.

<!-- gff-table save:INV ~UTI@ItemList -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `ItemList` | List | all | 8 entries; struct id 0 | Items; struct id 0. |
| `ItemList/Upgrades` | DWORD | all | 0 | Installed upgrades, a bit set *(inferred)*. |
| `ItemList/Dropable` | BYTE | all | 1 | 1 if it drops on death. |
| `ItemList/Pickpocketable` | BYTE | all | 1 | 1 if it can be stolen. |
| `ItemList/MaxCharges` | BYTE | all | 0 | Maximum charges. |
| `ItemList/PropertiesList/UsesPerDay` | BYTE | all | 255 | Uses per day; 255 = unlimited. |
| `ItemList/PropertiesList/Useable` | BYTE | all | 0, 1 | 1 if the property can be activated. |
| `ItemList/XPosition` | FLOAT | all | 0 | Position when on the ground; 0 in an inventory. |
| `ItemList/YPosition` | FLOAT | all | 0 | Position y. |
| `ItemList/ZPosition` | FLOAT | all | 0 | Position z. |
| `ItemList/XOrientation` | FLOAT | all | 1 | Facing x. |
| `ItemList/YOrientation` | FLOAT | all | 0 | Facing y. |
| `ItemList/ZOrientation` | FLOAT | all | 0 | Facing z. |
| `ItemList/NonEquippable` | BYTE | all | 0 | 1 if it cannot be equipped *(inferred)*. |
| `ItemList/NewItem` | BYTE | all | 0, 1 | 1 if not yet viewed (the "new item" marker). |
| `ItemList/DELETING` | BYTE | all | 0 | Internal flag; 0. |
<!-- /gff-table -->

## availnpcN.utc: stored party member

A full creature as the game saves it. Only fields a UTC blueprint lacks are listed; equipped
items carry the INV item fields above. The same creature struct is used for creatures in a saved
GIT and for the player in `Mod_PlayerList`.

<!-- gff-table save:UTC ~UTC;~UTI@Equip_ItemList;~save:INV>ItemList@Equip_ItemList -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Age` | INT | all | 0 | NWN age; 0. |
| `StartingPackage` | BYTE | all | 0 | NWN level-up package; 0. |
| `MClassLevUpIn` | BYTE | all | 0 | Class the next level goes into *(inferred)*. |
| `Gold` | DWORD | all | 0 | Gold carried by the creature (party gold is in PT). |
| `RefSaveThrow` | CHAR | all | 4 | Total Reflex save. |
| `WillSaveThrow` | CHAR | all | 4 | Total Will save. |
| `FortSaveThrow` | CHAR | all | 5 | Total Fortitude save. |
| `ArmorClass` | SHORT | all | 13 | Current armour class. |
| `PregameCurrent` | SHORT | all | 33 | Hit points kept across a module transition *(inferred)*. |
| `MaxForcePoints` | SHORT | all | 0 | Maximum Force points. |
| `Experience` | DWORD | all | 3321 | XP. |
| `MovementRate` | BYTE | all | 0 | Movement rate override; 0. |
| `Color_Skin` | BYTE | all | 0 | NWN colour; 0. |
| `Color_Hair` | BYTE | all | 0 | NWN colour; 0. |
| `Color_Tattoo1` | BYTE | all | 0 | NWN colour; 0. |
| `Color_Tattoo2` | BYTE | all | 0 | NWN colour; 0. |
| `DuplicatingHead` | BYTE | all | 255 | Head being duplicated; 255 none *(inferred)*. |
| `UseBackupHead` | BYTE | all | 0 | 1 to use the backup head model *(inferred)*. |
| `AIState` | INT | all | 0 | AI state bits. |
| `SkillPoints` | WORD | all | 0 | Unspent skill points. |
| `CombatInfo` | Struct | all | struct id 51882 | Derived combat numbers (struct id 51882). |
| `CombatInfo.NumAttacks` | BYTE | all | 1 | Attacks per round. |
| `CombatInfo.OnHandAttackMod` | CHAR | all | 3 | Main-hand attack modifier. |
| `CombatInfo.OnHandDamageMod` | CHAR | all | 0 | Main-hand damage modifier. |
| `CombatInfo.OffHandAttackMod` | CHAR | all | 0 | Off-hand attack modifier. |
| `CombatInfo.OffHandDamageMod` | CHAR | all | 0 | Off-hand damage modifier. |
| `CombatInfo.ForceResistance` | BYTE | all | 0 | Force resistance. |
| `CombatInfo.ArcaneSpellFail` | BYTE | all | 0 | NWN spell failure; 0. |
| `CombatInfo.ArmorCheckPen` | BYTE | all | 0 | Armour check penalty. |
| `CombatInfo.UnarmedDamDice` | BYTE | all | 1 | Unarmed damage dice count. |
| `CombatInfo.UnarmedDamDie` | BYTE | all | 1 | Unarmed damage die size. |
| `CombatInfo.OnHandCritRng` | BYTE | all | 1 | Main-hand critical threat range. |
| `CombatInfo.OnHandCritMult` | BYTE | all | 2 | Main-hand critical multiplier. |
| `CombatInfo.OffHandWeaponEq` | BYTE | all | 0 | 1 if an off-hand weapon is equipped. |
| `CombatInfo.OffHandCritRng` | BYTE | all | 1 | Off-hand threat range. |
| `CombatInfo.OffHandCritMult` | BYTE | all | 2 | Off-hand multiplier. |
| `CombatInfo.LeftEquip` | DWORD | all | 2130706432 | Object id of the off-hand weapon; 0x7F000000 none. |
| `CombatInfo.RightEquip` | DWORD | all | 300 | Object id of the main-hand weapon. |
| `CombatInfo.LeftString` | CExoString | all | always empty | Off-hand weapon name. |
| `CombatInfo.RightString` | CExoString | all | e.g. `Blaster Pistol` | Main-hand weapon name. |
| `CombatInfo.DamageDice` | BYTE | all | 1 | Weapon damage dice count. |
| `CombatInfo.DamageDie` | BYTE | all | 6 | Weapon damage die size. |
| `CombatInfo.AttackList` | List | all | 0 entries | Conditional attack bonuses (see the GIT table). |
| `CombatInfo.DamageList` | List | all | 0 entries | Conditional damage bonuses. |
| `DetectMode` | BYTE | all | 1 | 1 in detect mode. |
| `StealthMode` | BYTE | all | 0 | 1 in stealth mode. |
| `CreatureSize` | INT | all | 3 | Row in `creaturesize.2da`. |
| `IsDestroyable` | BYTE | all | 1 | 1 if the corpse may fade. |
| `IsRaiseable` | BYTE | all | 0 | 1 if it can be raised. |
| `DeadSelectable` | BYTE | all | 0 | 1 if selectable when dead. |
| `Equip_ItemList/ObjectId` | DWORD | all | 299, 300 | Runtime id of the equipped item. |
| `PerceptionList` | List | all | 3 entries; struct id 0 | What it perceives. |
| `PerceptionList/ObjectId` | DWORD | all | 30, 32, 2147483647 | Perceived object. |
| `PerceptionList/PerceptionData` | BYTE | all | 2, 3 | Perception bits (seen, heard) *(inferred)*. |
| `CombatRoundData` | Struct | all | struct id 51930 | Combat round state (struct id 51930); see the GIT table. |
| `AreaId` | DWORD | all | 1 | Object id of the area it is in. |
| `AmbientAnimState` | BYTE | all | 0 | Ambient animation state. |
| `Animation` | INT | all | 10000 | Current animation id (10000 = default idle *(inferred)*). |
| `CreatnScrptFird` | BYTE | all | 1 | 1 once its OnSpawn script has run. |
| `PM_IsDisguised` | BYTE | all | 0 | 1 while disguised. |
| `Listening` | BYTE | all | 1 | 1 if it listens for shouts. |
| `ExpressionList` | List | all | 6 entries; struct id 5 | Listen patterns: shouts it reacts to. |
| `ExpressionList/ExpressionId` | INT | all | 1, 3, 6, 12, 14, 15 | Pattern number passed to its OnConversation script. |
| `ExpressionList/ExpressionString` | CExoString | all | e.g. `gen_i_was_attacked`, `gen_i_am_dead`, `gen_call_to_arms` | Shout text matched. |
| `XPosition` | FLOAT | all | 46.3221 | Position x. |
| `YPosition` | FLOAT | all | 63.5798 | Position y. |
| `ZPosition` | FLOAT | all | -1.275 | Position z. |
| `XOrientation` | FLOAT | all | -0.225518 | Facing x. |
| `YOrientation` | FLOAT | all | 0.974239 | Facing y. |
| `ZOrientation` | FLOAT | all | 0 | Facing z. |
| `JoiningXP` | INT | all | 2961 | XP the NPC had when it joined *(inferred)*. |
| `FollowInfo` | Struct | all | struct id 0 | Party-follow state. |
| `FollowInfo.FollowObject` | DWORD | all | 2130706432 | Object followed. |
| `FollowInfo.FollowLocation` | Vector | all | ('0', '0', '0') | Target position. |
| `FollowInfo.LastLeaderPos` | Vector | all | ('0', '0', '0') | Leader's last position. |
| `FollowInfo.LastFollowerPos` | Vector | all | ('0', '0', '0') | Own last position. |
| `FollowInfo.MaxSpeed` | FLOAT | all | 0 | Speed limit. |
| `FollowInfo.StickToPos` | BYTE | all | 0 | 1 to stay at the follow location. |
| `FollowInfo.Result` | DWORD | all | 2 | Last follow result. |
| `FollowInfo.TimeElapsed` | DWORD | all | 0 | Time since the last update. |
| `FollowInfo.InSafetyRange` | BYTE | all | 1 | 1 if close enough to the leader. |
| `EffectList` | List | all | 2 entries; struct id 2 | Active effects (struct id 2). |
| `EffectList/Id` | DWORD64 | all | 313, 766 | Effect id, unique per module (`Mod_Effect_NxtId`). |
| `EffectList/Type` | WORD | all | 68, 101 | Engine effect type. |
| `EffectList/SubType` | WORD | all | 4, 10 | Engine effect subtype (magical / supernatural / extraordinary bits and duration kind) *(inferred)*. |
| `EffectList/Duration` | FLOAT | all | 0 | Duration in seconds. |
| `EffectList/SkipOnLoad` | BYTE | all | 0, 1 | 1 if not re-applied on load. |
| `EffectList/ExpireDay` | DWORD | all | 0 | Game day it expires. |
| `EffectList/ExpireTime` | DWORD | all | 0 | Game time it expires. |
| `EffectList/CreatorId` | DWORD | all | 292, 298 | Object id of its creator. |
| `EffectList/SpellId` | DWORD | all | 4294967295 | Power that created it; 0xFFFFFFFF none. |
| `EffectList/IsExposed` | INT | all | 1 | 1 if visible to scripts (`GetFirstEffect`). |
| `EffectList/NumIntegers` | INT | all | 8 | Number of integer parameters. |
| `EffectList/IntList` | List | all | 8 entries; struct id 3 | Integer parameters (struct id 3). |
| `EffectList/IntList/Value` | INT | all | 0, 6 | Parameter. |
| `EffectList/FloatList` | List | all | 4 entries; struct id 4 | Float parameters (struct id 4). |
| `EffectList/FloatList/Value` | FLOAT | all | 0 | Parameter. |
| `EffectList/StringList` | List | all | 6 entries; struct id 5 | String parameters (struct id 5). |
| `EffectList/StringList/Value` | CExoString | all | always empty | Parameter. |
| `EffectList/ObjectList` | List | all | 4 entries; struct id 6 | Object parameters (struct id 6). |
| `EffectList/ObjectList/Value` | DWORD | all | 2130706432 | Parameter. |
| `VarTable` | List | all | 0 entries | NWN named locals; empty. |
| `SWVarTable` | Struct | all | struct id 0 | KOTOR locals (see above). |
| `SWVarTable.BitArray` | List | all | 3 entries; struct id 0 | Local booleans: 3 DWORDs. |
| `SWVarTable.BitArray/Variable` | DWORD | all | 0, 136314880 | 32 booleans. |
| `SWVarTable.ByteArray` | List | all | 8 entries; struct id 0 | Local numbers: 8 bytes. |
| `SWVarTable.ByteArray/Variable` | BYTE | all | 0, 2, 3 | One local number. |
| `ActionList` | List | all | 1 entries; struct id 0 | Queued actions (see above). |
| `ActionList/ActionId` | DWORD | all | 61 | Engine action type. |
| `ActionList/GroupActionId` | WORD | all | 3 | Group id (actions queued together). |
| `ActionList/NumParams` | WORD | all | 0 | Number of parameters. |
| `Commandable` | BYTE | all | 1 | 1 if new actions may be queued (`SetCommandable`). |
<!-- /gff-table -->

## The saved module (`<module>.sav`)

### module.ifo

All the module IFO fields, plus the ones below. The player character is the single entry of
`Mod_PlayerList` (a saved creature, as above, plus the `Mod_*` names and the level history).

<!-- gff-table savemod:IFO ~IFO;~UTC@Mod_PlayerList;~save:UTC@Mod_PlayerList;~UTI@Mod_PlayerList/Equip_ItemList;~save:INV>ItemList@Mod_PlayerList/Equip_ItemList -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Mod_IsNWMFile` | BYTE | all | 0 | 0 (NWN premium module flag). |
| `Mod_Effect_NxtId` | DWORD64 | all | 855 | Next effect id to assign. |
| `Mod_NextCharId0` | DWORD | all | 2147483646 | Next character id (counter pair) *(inferred)*. |
| `Mod_NextCharId1` | DWORD | all | 2147483647 | Next character id, second counter. |
| `Mod_NextObjId0` | DWORD | all | 311 | Next object id to assign. |
| `Mod_NextObjId1` | DWORD | all | 0 | Second object id counter. |
| `Mod_Transition` | DWORD | all | 0 | Pending transition *(inferred)*. |
| `Mod_StartMinute` | WORD | all | 1 | Calendar minute at save time *(inferred)*. |
| `Mod_StartSecond` | WORD | all | 35 | Calendar second. |
| `Mod_StartMiliSec` | WORD | all | 507 | Calendar millisecond. |
| `Mod_PauseDay` | DWORD | all | 450438 | Game day at save time. |
| `Mod_PauseTime` | DWORD | all | 935507 | Game time (ms) at save time. |
| `Creature List` | List | all | 0 entries | Deprecated; empty. |
| `Mod_Area_list/ObjectId` | DWORD | all | 1 | Runtime id of the area. |
| `Mod_Tokens` | List | all | 0 entries | Custom tokens set by `SetCustomToken`; empty here. |
| `VarTable` | List | all | 0 entries | NWN named module locals; empty. |
| `SWVarTable` | Struct | all | struct id 0 | Module locals (see above). |
| `SWVarTable.BitArray` | List | all | 3 entries; struct id 0 | Module local booleans. |
| `SWVarTable.BitArray/Variable` | DWORD | all | 0 | Module local booleans. |
| `SWVarTable.ByteArray` | List | all | 8 entries; struct id 0 | Module local numbers. |
| `SWVarTable.ByteArray/Variable` | BYTE | all | 0 | Module local numbers. |
| `EventQueue` | List | all | 1 entries; struct id 43981 | Pending events (struct id 0xABCD). |
| `EventQueue/Day` | DWORD | all | 450438 | Game day it fires. |
| `EventQueue/Time` | DWORD | all | 957111 | Game time (ms) it fires. |
| `EventQueue/ObjectId` | DWORD | all | 1 | Target object. |
| `EventQueue/CallerId` | DWORD | all | 1 | Object that queued it. |
| `EventQueue/EventId` | DWORD | all | 1 | 1 = timed event (`DelayCommand`). |
| `EventQueue/EventData` | Struct | all | struct id 30583 | Script situation (struct id 0x7777; see above). |
| `EventQueue/EventData.CodeSize` | INT | all | 4752 | Bytes of `Code` (NCS file size - 13). |
| `EventQueue/EventData.Code` | VOID | all | sizes 4752 | The script's whole code, without the NCS header. |
| `EventQueue/EventData.CRC` | DWORD | all | 0 | Always 0. |
| `EventQueue/EventData.InstructionPtr` | INT | all | 4404 | Offset in `Code` where execution resumes. |
| `EventQueue/EventData.SecondaryPtr` | INT | all | 0 | Always 0 *(unknown)*. |
| `EventQueue/EventData.Name` | CExoString | all | e.g. `k_pend_area02` | Script resref. |
| `EventQueue/EventData.StackSize` | INT | all | 195 | Saved stack size in cells *(inferred)*. |
| `EventQueue/EventData.Stack` | Struct | all | struct id 0 | Saved VM stack. |
| `EventQueue/EventData.Stack.BasePointer` | INT | all | 190 | BP, in cells. |
| `EventQueue/EventData.Stack.StackPointer` | INT | all | 194 | SP, in cells (= number of cell structs). |
| `EventQueue/EventData.Stack.TotalSize` | INT | all | 210 | Allocated stack size, cells *(inferred)*. |
| `EventQueue/EventData.Stack.Stack` | List | all | 194 entries; struct id = index | Saved VM stack. |
| `EventQueue/EventData.Stack.Stack/Type` | CHAR | all | 3, 4, 5, 6, 16 | 3 int, 4 float, 5 string, 6 object, 0x10+n engine type. |
| `EventQueue/EventData.Stack.Stack/Value` | DWORD/INT/FLOAT/CExoString | all | -6..2130706432 | The cell value (INT, FLOAT, CExoString or DWORD by `Type`). |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct` | Struct | all | struct id 0 | Engine-type value (here an effect, with EffectList fields). |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.Id` | DWORD64 | all | 838 | Effect id. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.Type` | WORD | all | 30 | Effect type. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.SubType` | WORD | all | 8 | Effect subtype. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.Duration` | FLOAT | all | 0 | Duration. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.SkipOnLoad` | BYTE | all | 0 | Skip on load. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.ExpireDay` | DWORD | all | 0 | Expiry day. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.ExpireTime` | DWORD | all | 0 | Expiry time. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.CreatorId` | DWORD | all | 1 | Creator. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.SpellId` | DWORD | all | 4294967295 | Power; 0xFFFFFFFF none. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.IsExposed` | INT | all | 1 | Visible to scripts. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.NumIntegers` | INT | all | 8 | Integer count. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.IntList` | List | all | 8 entries; struct id 3 | Typed parameter list. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.IntList/Value` | INT | all | 0, 6002 | Parameter. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.FloatList` | List | all | 4 entries; struct id 4 | Typed parameter list. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.FloatList/Value` | FLOAT | all | 0 | Parameter. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.StringList` | List | all | 6 entries; struct id 5 | Typed parameter list. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.StringList/Value` | CExoString | all | always empty | Parameter. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.ObjectList` | List | all | 4 entries; struct id 6 | Typed parameter list. |
| `EventQueue/EventData.Stack.Stack/GameDefinedStrct.ObjectList/Value` | DWORD | all | 2130706432 | Parameter. |
| `Mod_PlayerList` | List | all | 1 entries; struct id 48813 | The player (struct id 48813). |
| `Mod_PlayerList/Mod_CommntyName` | CExoString | all | e.g. `Bad StrRef` | NWN player login name (`Bad StrRef`). |
| `Mod_PlayerList/Mod_IsPrimaryPlr` | BYTE | all | 1 | 1. |
| `Mod_PlayerList/Mod_FirstName` | CExoLocString | all | inline text in 1 (ids 0) | Character first name. |
| `Mod_PlayerList/Mod_LastName` | CExoLocString | all | 1 empty | Character last name. |
| `Mod_PlayerList/ObjectId` | DWORD | all | 2147483647 | The player's object id (0x7FFFFFFF). |
| `Mod_PlayerList/LvlStatList` | List | all | 1 entries; struct id 0 | One entry per level gained: what was chosen. |
| `Mod_PlayerList/LvlStatList/LvlStatHitDie` | BYTE | all | 10 | Hit points gained. |
| `Mod_PlayerList/LvlStatList/LvlStatForce` | BYTE | all | 0 | Force points gained. |
| `Mod_PlayerList/LvlStatList/LvlStatClass` | BYTE | all | 0 | Class levelled. |
| `Mod_PlayerList/LvlStatList/SkillPoints` | WORD | all | 0 | Skill points left over. |
| `Mod_PlayerList/LvlStatList/SkillList` | List | all | 8 entries; struct id 0 | Skill ranks after the level. |
| `Mod_PlayerList/LvlStatList/SkillList/Rank` | BYTE | all | 0, 2, 4 | Rank. |
| `Mod_PlayerList/LvlStatList/FeatList` | List | all | 10 entries; struct id 0 | Feats taken. |
| `Mod_PlayerList/LvlStatList/FeatList/Feat` | WORD | all | 4..84 (10 values) | Row in `feat.2da`. |
<!-- /gff-table -->

### `<area>.are`

Identical in schema to the module's ARE (the probe found no extra field).

### `<area>.git`

Every instance is saved whole: a creature has all UTC fields plus the saved-creature fields
above, a door all UTD fields, and so on. Listed here: only what neither the blueprint, the module
GIT nor the saved creature already has.

<!-- gff-table savemod:GIT ~GIT;~UTC@Creature List;~save:UTC@Creature List;~UTI@Creature List/Equip_ItemList;~UTI@Creature List/ItemList;~save:INV@Creature List;~save:INV>ItemList@Creature List/Equip_ItemList;~UTD@Door List;~UTP@Placeable List;~UTI@Placeable List/ItemList;~save:INV@Placeable List;~UTT@TriggerList;~UTW@WaypointList;~UTS@SoundList;~save:UTC@Door List;~save:UTC@Placeable List;~save:UTC@TriggerList;~save:UTC@WaypointList;~save:UTC@SoundList -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `VarTable` | List | all | 0 entries | NWN named locals of the area; empty. |
| `SWVarTable` | Struct | all | struct id 0 | Area locals. |
| `SWVarTable.BitArray` | List | all | 3 entries; struct id 0 | Area local booleans. |
| `SWVarTable.BitArray/Variable` | DWORD | all | 0, 512 | 32 booleans. |
| `SWVarTable.ByteArray` | List | all | 8 entries; struct id 0 | Area local numbers. |
| `SWVarTable.ByteArray/Variable` | BYTE | all | 0 | One number. |
| `CurrentWeather` | BYTE | all | 255 | 255 = none. |
| `WeatherStarted` | BYTE | all | 0 | 0. |
| `TransPending` | BYTE | all | 0 | Area transition pending *(inferred)*. |
| `TransPendNextID` | BYTE | all | 0 | Pending transition target *(inferred)*. |
| `TransPendCurrID` | BYTE | all | 0 | Pending transition source *(inferred)*. |
| `Creature List/ObjectId` | DWORD | all | 2..64 (19 values) | Runtime object id. |
| `Creature List/ClassList/SpellsPerDayList` | List | all | 1 entries; struct id 17767 | Uses left per power level (struct id 17767). |
| `Creature List/ClassList/SpellsPerDayList/NumSpellsLeft` | BYTE | all | 0 | Uses left. |
| `Creature List/CombatInfo.AttackList/Modifier` | CHAR | all | -5 | Conditional attack bonus: amount, hand, versus alignment/race. |
| `Creature List/CombatInfo.AttackList/WeaponWield` | BYTE | all | 1 | Conditional attack bonus: amount, hand, versus alignment/race. |
| `Creature List/CombatInfo.AttackList/VersusGoodEvil` | BYTE | all | 0 | Conditional attack bonus: amount, hand, versus alignment/race. |
| `Creature List/CombatInfo.AttackList/VersusRace` | BYTE | all | 7 | Conditional attack bonus: amount, hand, versus alignment/race. |
| `Creature List/CombatInfo.DamageList/Modifier` | CHAR | all | 1 | Conditional damage bonus: amount, damage type, hand, versus. |
| `Creature List/CombatInfo.DamageList/ModifierType` | BYTE | all | 2, 12 | Conditional damage bonus: amount, damage type, hand, versus. |
| `Creature List/CombatInfo.DamageList/WeaponWield` | BYTE | all | 1 | Conditional damage bonus: amount, damage type, hand, versus. |
| `Creature List/CombatInfo.DamageList/VersusGoodEvil` | BYTE | all | 0 | Conditional damage bonus: amount, damage type, hand, versus. |
| `Creature List/CombatInfo.DamageList/VersusRace` | BYTE | all | 7 | Conditional damage bonus: amount, damage type, hand, versus. |
| `Creature List/ItemList/ObjectId` | DWORD | all | 12..277 (12 values) | Runtime object id. |
| `Creature List/CombatRoundData.RoundStarted` | BYTE | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.SpellCastRound` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.DeflectArrow` | BYTE | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.WeaponSucks` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.DodgeTarget` | DWORD | all | 7, 9 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.NewAttackTarget` | DWORD | all | 2130706432 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.Engaged` | INT | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.Master` | INT | all | 0, 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.MasterID` | DWORD | all | 9 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.RoundPaused` | BYTE | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.RoundPausedBy` | DWORD | all | 7 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.InfinitePause` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.PauseTimer` | INT | all | 1311 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.Timer` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.RoundLength` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.OverlapAmount` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.BleedTimer` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.CurrentAttack` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackID` | WORD | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackGroup` | BYTE | all | 255 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.ParryIndex` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.NumAOOs` | INT | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.NumCleaves` | INT | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.OnHandAttacks` | INT | all | 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.OffHandAttacks` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AdditAttacks` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.EffectAttacks` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.ParryActions` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.OffHandTaken` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.ExtraTaken` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList` | List | all | 5 entries; struct id 43758 | The round's attacks (struct id 43758). |
| `Creature List/CombatRoundData.AttackList/AttackGroup` | BYTE | all | 255 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AnimationLength` | WORD | all | 0, 1500 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/MissedBy` | DWORD | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AttackResult` | BYTE | all | 0, 1, 4 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/ReactObject` | DWORD | all | 7, 9, 2130706432 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/ReaxnDelay` | WORD | all | 0, 100 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/ReaxnAnimation` | WORD | all | 10001, 10011, 10014 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/ReaxnAnimLength` | WORD | all | 0, 1500 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/Concealment` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AttackType` | WORD | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AttackMode` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/RangedAttack` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/SneakAttack` | INT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/WeaponAttackType` | BYTE | all | 0, 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/RangedTargetX` | FLOAT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/RangedTargetY` | FLOAT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/RangedTargetZ` | FLOAT | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/DamageList` | List | all | 15 entries; struct id 56046 | Damage per damage type (struct id 56046). |
| `Creature List/CombatRoundData.AttackList/DamageList/DamageValue` | SHORT | all | -1 | Damage; -1 none. |
| `Creature List/CombatRoundData.AttackList/KillingBlow` | BYTE | all | 0, 1 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/CoupDeGrace` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/CriticalThreat` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AttackDeflected` | BYTE | all | 0 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AmmoItem` | DWORD | all | 2130706432 | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/AttackDebugText` | CExoString | all | always empty | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.AttackList/DamageDebugText` | CExoString | all | always empty | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.SpecAttackList` | List | all | 0 entries | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.SpecAttackIdList` | List | all | 0 entries | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/CombatRoundData.SchedActionList` | List | all | 0 entries | Combat-round bookkeeping: timers, attack counts, pause state, targets (internal; write back as read). |
| `Creature List/ActionList/Paramaters` | List | all | 1..4 entries; struct id 1 | Action parameters (struct id 1). |
| `Creature List/ActionList/Paramaters/Type` | DWORD | all | 1, 2, 5 | 1 int, 2 float, 3 object, 4 string, 5 script situation. |
| `Creature List/ActionList/Paramaters/Value` | INT/FLOAT/Struct | all | 0, 1, 10152 | The parameter; a struct for type 5. |
| `Creature List/ActionList/Paramaters/Value.CodeSize` | INT | all | 78 | Bytes of `Code`. |
| `Creature List/ActionList/Paramaters/Value.Code` | VOID | all | sizes 78 | The script's whole code, without the NCS header. |
| `Creature List/ActionList/Paramaters/Value.CRC` | DWORD | all | 0 | Always 0. |
| `Creature List/ActionList/Paramaters/Value.InstructionPtr` | INT | all | 47 | Resume offset in `Code`. |
| `Creature List/ActionList/Paramaters/Value.SecondaryPtr` | INT | all | 0 | Always 0. |
| `Creature List/ActionList/Paramaters/Value.Name` | CExoString | all | e.g. `k_pend_weld01` | Script resref. |
| `Creature List/ActionList/Paramaters/Value.StackSize` | INT | all | 0 | Saved stack size, cells. |
| `Creature List/ActionList/Paramaters/Value.Stack` | Struct | all | struct id 0 | Saved VM stack (empty here: no cells). |
| `Creature List/ActionList/Paramaters/Value.Stack.BasePointer` | INT | all | 0 | BP, cells. |
| `Creature List/ActionList/Paramaters/Value.Stack.StackPointer` | INT | all | 0 | SP, cells. |
| `Creature List/ActionList/Paramaters/Value.Stack.TotalSize` | INT | all | 0 | Allocated size. |
| `Door List/ObjectId` | DWORD | all | 66..80 (15 values) | Runtime object id. |
| `Door List/OpenState` | BYTE | all | 0, 1, 2 | 0 closed, 1 open one way, 2 open the other way *(inferred, as AnimationState)*. |
| `Door List/SecretDoorDC` | BYTE | all | 0 | Obsolete; 0. |
| `Door List/OnDialog` | ResRef | all | e.g. `default` | Conversation script slot *(inferred)*. |
| `TriggerList/ObjectId` | DWORD | all | 81..94 (14 values) | Runtime object id. |
| `TriggerList/CreatorId` | DWORD | all | 2130706432 | Creator (for traps set by a creature). |
| `TriggerList/SetByPlayerParty` | BYTE | all | 0 | 1 if a mine laid by the party. |
| `WaypointList/ObjectId` | DWORD | all | 95..152 | Runtime object id. |
| `SoundList/ObjectId` | DWORD | all | 153..197 | Runtime object id. |
| `SoundList/FixedVariance` | FLOAT | all | 1 | Variance setting *(unknown)*. |
| `Placeable List/ObjectId` | DWORD | all | 198..271 | Runtime object id. |
| `Placeable List/GroundPile` | BYTE | all | 1 | 1 if it is a pile of dropped items *(inferred)*. |
| `Placeable List/Open` | BYTE | all | 0 | 1 if open. |
| `Placeable List/DieWhenEmpty` | BYTE | all | 0 | 1 if it disappears once emptied (body bags). |
| `Placeable List/LightState` | BYTE | all | 0 | Light on/off. |
| `Placeable List/OnDialog` | ResRef | all | always empty | Conversation script slot; empty. |
| `Placeable List/IsBodyBag` | BYTE | all | 0 | 1 if it is a body bag. |
| `Placeable List/IsBodyBagVisible` | BYTE | all | 1 | 1 if the body bag is shown. |
| `Placeable List/IsCorpse` | BYTE | all | 0 | 1 if it is a corpse container. |
| `Placeable List/ItemList/ObjectId` | DWORD | all | 219, 223, 286, 287, 288 | Runtime object id. |
| `AreaEffectList` | List | all | 0 entries | Persistent area effects; empty. |
| `AreaProperties.Unescapable` | BYTE | all | 1 | Live copy of the ARE flag. |
| `AreaProperties.RestrictMode` | BYTE | all | 0 | Restricted (no party change / no menus) mode *(inferred)*. |
| `AreaProperties.StealthXPMax` | DWORD | all | 0 | Live stealth XP maximum. |
| `AreaProperties.StealthXPCurrent` | DWORD | all | 0 | Stealth XP awarded so far. |
| `AreaProperties.StealthXPLoss` | DWORD | all | 0 | Live stealth XP loss. |
| `AreaProperties.StealthXPEnabled` | BYTE | all | 0 | Live stealth XP flag. |
| `AreaProperties.TransPending` | BYTE | all | 0 | Transition pending. |
| `AreaProperties.TransPendNextID` | BYTE | all | 0 | Pending transition target. |
| `AreaProperties.TransPendCurrID` | BYTE | all | 0 | Pending transition source. |
| `AreaProperties.SunFogColor` | DWORD | all | 0 | Live fog colour. |
| `AreaMap` | Struct | all | struct id 101 | Explored part of the area map. |
| `AreaMap.AreaMapResX` | INT | all | 15 | Exploration grid width. |
| `AreaMap.AreaMapResY` | INT | all | 8 | Exploration grid height. |
| `AreaMap.AreaMapDataSize` | DWORD | all | 20 | Bytes of `AreaMapData`. |
| `AreaMap.AreaMapData` | VOID | all | sizes 20 | Explored-cell bit grid *(inferred; the packing of 15x8 cells into 20 bytes is not established)*. |
<!-- /gff-table -->
