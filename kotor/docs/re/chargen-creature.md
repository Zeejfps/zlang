# What character generation produces: the new player creature

How "Play" on the last character-generation screen becomes the player creature that the first module
(`END_M01AA`) starts with, field by field, so a re-implementation can build the same creature.
Everything here is ours: addresses and descriptions in our words; confidence per claim (high, med,
low). Companion pages: [gui.md](gui.md) 10.2 (the screens), [rules.md](rules.md) (level-up, hit
points), [objects.md](objects.md) (creature layout), [gameloop.md](gameloop.md) 5.5 (arrival),
[party-items-saves.md](party-items-saves.md) (party table, saves), and the format side
[../formats/gff-save.md](../formats/gff-save.md). Checked against the install's only save
(`Saves/000002 - Game1`, a male Soldier one hour into the Endar Spire) and the module's own data.

## 1. The short version

- The finished character is **serialised as a BioWare character file (GFF type `BIC `, version
  string `V2.0`)** named `TEMP:temp` (resource type 0x7df). It is a *client* object's data: the
  six class/gender "slot" creatures made by the class-selection screen are `CSWCCreature`s
  (0x44c bytes) whose stats block lives at `+0x2f8`. (high)
- The client creates the server, asks it to load the start module, and on the server's request
  sends the bytes of `temp.bic` in a login message (major 2, minor 1). The server writes them to
  `TEMP:temp_char`, makes a new `CSWSCreature` (object id from the character counter, so the
  first player is `0x7fffffff`), loads the file into it with the *same* loader a UTC/Mod_PlayerList
  uses (`CSWSCreatureStats::ReadStatsFromGff`) and runs `PostProcess`. (high)
- The exe gives the player **no items, no Force powers, no gold, no XP** and sets no flag beyond
  "is a player". The first items (a class kit) come from the module's area script, into a
  footlocker. Min1HP, the opening conversation and the movie are module scripts. (high)
- Level-1 hit points are **not rolled**: the history record stores the class's full hit die.
  Maximum HP is recomputed by the server from the history (hit die + CON modifier per level,
  + Toughness). New characters start at full HP. (high; checked against the save)

## 2. The chain from Play to the running game

| # | Step | Address | Conf. |
|---|---|---|---|
| 1 | `OnNewGame` builds `CSWGuiClassSelection(startModule)`. Its constructor makes six `CSWCCreature`s, one per slot (table below), each with a stats object (`0x0064b2d0`), a random portrait of the slot's gender among the `ForPC` portraits, the sound set and a body appearance (below). | `0x0067afb0`, `0x006dc3c0`, `0x00616a20` | high |
| 2 | Picking a slot stores that creature at `classsel+0x68` and opens `CSWGuiCharGenMain(creature)`; every later screen edits `creature+0x2f8` (stats) in place. `Quick` applies the class's recommended build the moment its panel is shown (`0x006f0260` → `0x006effd0`), `Custom` lets the player do each step. | `0x006db9b0`, `0x006eb420`, `0x006f0260` | high |
| 3 | Play (`OnPlay` of the quick or custom panel; quick needs more than one step done, custom the first five) → `CSWGuiCharGenMain::Finish`: `Close` pops and deletes the step panels, then `StartGame`. | `0x006efd60`/`0x006ef220`, `0x006eb320`, `0x006ea830` | high |
| 4 | `StartGame`: sets the stats' current Force points to 0; `CAppManager::CreateServer`; **`0x006123e0` writes the BIC** to `TEMP:temp`; joins the local server; sends the admin text `s` + `Module.Load <start module>` (format `%c%s.%s %s`, target −3 = the server); remembers the character file name `temp` (`0x005edaa0`); picks the load-screen picture and a story hint; shows the loading screen. | `0x006dbdf0` | high for the order, med for the join arguments |
| 5 | Server loads the module (IFO, area, GIT objects; [modules.md](modules.md)). The client's server-status handler (`0x0064f280`, minor 3) reads `TEMP:temp.bic` (`0x00678080`, falls back to `LOCALVAULT:` only for the name `test`) and sends it as Login 2/1 (`0x00677fa0`; 2/0x13 when the second argument is set, use unknown). | `0x0064f280`, `0x00678080` | high |
| 6 | `HandlePlayerToServerLoginMessage` → `PlayerLoginToModule` minor 1: writes the bytes to `TEMP:temp_char` (type 0x7df), mounts `TEMP:`, calls `0x00561d70`, unmounts, empties the directory, `CSWPartyTable::RestoreParty`, then `SignalPlayerEnterModule`. | `0x005244e0`, `0x004b7470`, `0x00565760`, `0x004b5c50` | high |
| 7 | `0x00561d70`: `new CSWSCreature(0x7f000000 = allocate, player = 1)`; binds it to the `CSWSPlayer` (`0x00561c40`); `0x00560e60` loads the BIC (section 4); `SetPlayerControlled(1, 1)` afterwards. | `0x00561d70`, `0x00560e60`, `0x004fdb20` | high |
| 8 | `SignalPlayerEnterModule` queues OnClientEnter (script event 0xe; the module's slot is empty in `end_m01aa`) and sends module info; the rest (area message, placement at `Mod_Entry_*`, area OnEnter) is [gameloop.md](gameloop.md) 5.5. | | high |

The six slots (static table `g_aClassSelSlots`, `0x007a2684`; **filled at start-up** by the
initialiser `0x0073b690`, the file image only holds the sound sets and strings):

| Slot | Class (classes.2da row) | Gender | Sound set (soundset.2da) | Description strref |
|---|---|---|---|---|
| 0 | 2 Scoundrel | 0 male | 85 `p_playermw` | 32109 |
| 1 | 1 Scout | 0 male | 85 | 32110 |
| 2 | 0 Soldier | 0 male | 85 | 32111 |
| 3 | 0 Soldier | 1 female | 83 `p_playerfw` | 32111 |
| 4 | 1 Scout | 1 female | 83 | 32110 |
| 5 | 2 Scoundrel | 1 female | 83 | 32109 |

The sound set depends on gender only (the save's male Soldier has 85). (high)

## 3. What the chargen creature holds (client stats, `creature+0x2f8`)

The stats block (0x134 bytes, base ctor `0x0064afc0`, derived `0x0064b2d0`) starts with these
values; the screens change the rest. Offsets are in the stats block. (high unless noted)

| Offset | Meaning | Start value | Changed by |
|---|---|---|---|
| `+0x14` / `+0x1c` | first / last name | empty | name screen (`0x006f9cd0` → `0x0060d600`: the typed text, trailing spaces cut, goes whole into the first name; last name is set to empty) |
| `+0x24` | race (racialtypes.2da row) | 6 Human | never (the only player race) |
| `+0x28`, `+0x30` | subrace text, index | empty, 0 | never |
| `+0x31` | gender | slot | never |
| `+0x32` | number of class slots in use | 1 | — (the BIC writes it minus 1 as `MClassLevUpIn`) |
| `+0x33` | starting package | 0 | never seen set (med) |
| `+0x34..+0x39` | STR, DEX, CON, INT, WIS, CHA, each = base + race adjustment | 8 + 0 | abilities screen (30 points; costs 1 per point up to 14, 2 for 14 and 15, 3 from 16; range 8..18); recommended = `classes.2da` `str dex con wis int cha` of the class |
| `+0x48` | base hit points ("HitPoints") | 0 (never set in chargen) | — |
| `+0x4c`, `+0x4e` | current, maximum HP written to the file | recomputed on every CON change: max(1, `+0x48` + CON modifier) | CON setter `0x006496d0`; the file's copies are ignored by the game (4.3) |
| `+0x50` | armour class shown | 10 + DEX modifier (+ the class's AC bonus when the summary is refreshed, `0x006eac30`) | DEX setter `0x0064a100` |
| `+0x58` | experience | 0 | — |
| `+0x5c/+0x5d/+0x5e` | Fort / Will / Reflex shown | class table + ability modifier | recomputed |
| `+0x80` | good-evil | 50 (0x32) | — |
| `+0x8c` | appearance type | slot's (below) | portrait screen |
| `+0x8e..+0x91` | skin, hair, two tattoo colours | 0 | — |
| `+0x92`, `+0x93`, `+0x94`, `+0x98` | phenotype, head, duplicating head, use-backup-head | 0, 0, 0xff, 0 | — |
| `+0x9c`, `+0x9d` | tail, wings | 0 | — |
| `+0xa0` | description | empty | — |
| `+0xa8` | age | 0 | — |
| `+0xae` | unspent skill points | 0 | skills screen |
| `+0x84/+0x88` | skill ranks / ranks bought this session (8 each) | 0 | skills screen |
| `+0xb0/+0xb4` | feat list (ushorts) / count | class and racial grants (`0x00649950`) | feats screen |
| `+0xd4`.. | per-class spell (power) lists | empty | never used (no Force class) |
| `+0xf0 + 0x20*i`, `+0xf1 + 0x20*i` | class id and level of slot i | slot's class, 1 | — |
| `+0x11c` | portrait id (portraits.2da row) | random of the gender | portrait screen |
| `+0x11e`, `+0x120`, `+0x122`, `+0x124` | Force points: maximum, base (`ForcePoints`), bonus, temporary | 0 | `StartGame` zeroes `+0x120` again |
| `+0x128` / `+0x12c` | starting item resrefs (16 bytes each) / count | empty | never filled in the shipped flow (med) |
| creature `+0x2fc` | sound set (ushort), on the `CSWCCreature`, not the stats | slot (85 or 83) | — |
| creature `+0x144` | gold, on the `CSWCCreature` | 0 | — |

**Body appearance** (high): the slot's class picks the `portraits.2da` column that gives the
`appearance.2da` row: Soldier → `Appearance_L` (large body), Scout → `AppearanceNumber` (medium),
Scoundrel → `Appearance_S` (small body). The portrait screen (`0x006f90f0`) lists the `ForPC = 1`
portraits of the chosen gender (30 rows: ids 1..12 and 15..17 female, 18..32 male) and uses the same
column choice. Check: the save's Soldier has portrait 26 (`po_pmhc4`) and Appearance_Type 177 =
that row's `Appearance_L`. All 90 appearances reachable have size category 3 and body type `B`;
the head model comes from the appearance row's `normalhead` (heads.2da), not from `Appearance_Head`.

**Class grants and quick build** (med): `0x00649950` adds every feat the race grants at level 1 and
every feat the class's `featstable` grants at its level, called on every reset and when the
class changes. The quick build (`0x006effd0`) sets the six abilities from the class row, adds the
recommended feats along the class's feat priority list (`0x0064a770`), then buys skills along the
class's `*_reco` order (`0x00648a00`) until the points are gone. This is what
`rules::take_first_level` (the auto-leveller's record) is meant to equal; abilities are the
extra input. Skill points at level 1 = max(1, `skillpointbase`/2 + INT modifier) × 4, class
skills cost 1 per rank, others 2 (checked below: the save's Soldier INT 18 → 20 points,
ranks 2 computer use, 4 awareness, 2 repair, 2 security, 4 treat injury = 4+4+4+4+4 = 20).

## 4. The file `0x006123e0` writes, and what the server does with it

### 4.1 Written fields (top level, in file order; the types are the GFF types used)

| Label | Type | Value | Read by the server? |
|---|---|---|---|
| `FirstName`, `LastName`, `Description` | CExoLocString (string id 0) | stats `+0x14`, `+0x1c`, `+0xa0` | yes |
| `Gold` | DWORD | creature `+0x144` (0) | yes (only while the creature is not yet player-controlled, which it isn't) |
| `Conversation` | ResRef | empty | yes |
| `Age` | INT | 0 | yes |
| `Gender`, `Race` | BYTE | | yes (race must be below the race table size) |
| `Subrace` (CExoString), `SubraceIndex` (BYTE), `StartingPackage` (BYTE), `Deity` (CExoString) | | empty, 0, 0, empty | yes |
| `ArmorClass` SHORT, `FortSaveThrow`, `RefSaveThrow`, `WillSaveThrow` CHAR | | the screen's numbers | **no** (recomputed) |
| `MClassLevUpIn` | BYTE | `+0x32` − 1 = 0 | no |
| `SoundSetFile` | WORD | creature `+0x2fc` | yes (creature `+0x9d8`) |
| `ClassList[0]` | List, one element | `ClassLevel` SHORT = 1, `Class` INT; if the class has powers a `KnownList0` of `Spell` WORDs (none for the three classes) | yes |
| `SkillPoints` WORD, `SkillList` (8 × `Rank` BYTE) | | unspent points; ranks | yes |
| `FeatList` | List of `Feat` WORD | the whole feat list | yes (`AddFeat` each) |
| `Str Dex Con Int Wis Cha` | BYTE | score **minus the race adjustment** (0 for humans) | yes |
| `HitPoints`, `MaxHitPoints`, `PregameCurrent`, `CurrentHitPoints` SHORT | | `+0x48`, `+0x4e`, `+0x4c`, `+0x4c + +0x48 − +0x4e` | `HitPoints`, `CurrentHitPoints` yes; see 4.3 |
| `ForcePoints`, `MaxForcePoints`, `CurrentForce` SHORT | | all 0 | `ForcePoints`, `CurrentForce` yes |
| `LvlStatList[0]` | List, one element | `LvlStatHitDie` BYTE = the class's `hitdie` (classes.2da, full die: Soldier 10, Scout 8, Scoundrel 6), `LvlStatClass` BYTE, (`KnownList0` if any), `SkillPoints` WORD, `SkillList`, `FeatList` — the same skills and feats as the top level. **No** `LvlStatForce` or `LvlStatAbility` (the loader's defaults: 0 and "none") | yes (PCs only) |
| `Experience` | DWORD | 0 | yes |
| `PortraitId` WORD, `Portrait` ResRef | | portrait row; the portrait's resref | `PortraitId` yes (`Portrait` only if the id is ≥ 0xfffe) |
| `GoodEvil` | BYTE | 50 | yes (clamped to 100) |
| `Color_Skin/Hair/Tattoo1/Tattoo2` | BYTE | 0 | yes |
| `Phenotype` INT, `Appearance_Type` WORD, `Appearance_Head` BYTE, `DuplicatingHead` BYTE, `UseBackupHead` BYTE, `Tail`, `Wings` BYTE | | 0, row, 0, 255, 0, 0, 0 | yes; the loader raises a head of 0 to 1 |
| `ItemList` | List | one `InventoryRes` ResRef per entry of the item array (none) | yes, but see 4.4 |
| 14 script ResRefs | | `ScriptHeartbeat k_hen_heartbt01`, `ScriptOnNotice k_hen_percept01`, `ScriptSpellAt k_def_spellat01`, `ScriptAttacked k_hen_attacked01`, `ScriptDamaged k_def_damage01`, `ScriptDisturbed ""`, `ScriptEndRound k_hen_combend01`, `ScriptDialogue k_hen_dialogue01`, `ScriptSpawn k_hen_spawn01`, `ScriptRested ""`, `ScriptDeath ""`, `ScriptUserDefine k_def_userdef01`, `ScriptOnBlocked k_def_blocked01`, `ScriptEndDialogue ""` | yes |

GFF labels are cut to 16 characters when written, so the last script label is `ScriptEndDialogu`
(the save and the toolset's UTCs have it that way too). (high)

### 4.2 Not written, so the server's defaults apply (high; confirmed by the save)

`IsPC` = 1 (the stats constructor `0x005aca80`; the loader keeps it), `Tag` empty,
`Interruptable` 1, `Plot` 0, `Min1HP` 0, `Disarmable` 1, `PartyInteract` 0, `NaturalAC` 0,
`FactionID` −1 (replaced by `PostProcess`, below), `ChallengeRating` 0, `willbonus/fortbonus/refbonus` 0,
`MovementRate` 0, `CreatureSize` 3 (a default of the BIC loader, not looked up), `BodyBag` 0,
`DetectMode` (the loader switches detect mode on, med), `StealthMode` 0, `PM_IsDisguised` 0,
no `Equip_ItemList`, no `EffectList`, no `PerceptionList`, no position (the player is placed
from the module's entry point).

### 4.3 Hit and Force points on load (high)

`ReadStatsFromGff` stores `HitPoints` as the creature's base maximum (`+0xe0`). For a **player**
it then sets current HP to `CurrentHitPoints + (computed maximum − base)`: the file stores
HP *relative to the base*, never absolute. The consequence is that `HitPoints` /
`CurrentHitPoints` / `MaxHitPoints` in the chargen file do not matter: the loader
(`0x00560e60`) then sets current HP to `GetMaxHitPoints(1)`, i.e. **a new player starts at full
HP**. The same relative rule applies to Force points. For non-players the file value is raised by
level × CON modifier, minimum 1 per level.

`GetMaxHitPoints` for a player (rules.md 4.5) sums, over the history, max(1, record HP + CON
modifier) and adds 1 per level with Toughness (feat 84). Examples at level 1:

| Class | Hit die | CON 14 (+2) | CON 14 + Toughness | CON 8 (−1) + Toughness |
|---|---|---|---|---|
| Soldier | 10 | 12 | 13 | **10** (the save: `MaxHitPoints` 10, `LvlStatHitDie` 10, feats include 84) |
| Scout | 8 | 10 | 11 | 8 |
| Scoundrel | 6 | 8 | 9 | 6 |

Force points at level 1 are 0 for all three classes (`LvlStatForce` 0, `MaxForcePoints` 0).
The chargen summary's "VIT" is hit die + CON modifier (`0x006eac30` adds the class record's hit
die to the CON modifier and `+0x48`, which stays 0), i.e. the game's level-1 maximum without
Toughness and without the minimum of 1. The file's own `MaxHitPoints` / `PregameCurrent`
(max(1, 0 + CON modifier)) are leftovers of the level-up code and are ignored. (med for the
screen, high for the game)

### 4.4 The rest of the load (high unless noted)

1. `CSWSCreature(0x7f000000, 1)`: a character-class object id (first player: `0x7fffffff`).
2. `ReadStatsFromGff` (`0x005afce0`): names, ability scores (modifier = floor((score − 10)/2),
   stored beside each score), classes, `LvlStatList` (one record per
   level, so one here), skills, feats (`AddFeat`), HP/FP as above, appearance block copied into
   the creature's `+0xa50` (type, gender, phenotype, head, colours), sound set, gold.
3. HP set to `GetMaxHitPoints(1)`; detect mode on; stealth off; `CreatureSize` 3.
4. `ReadScriptsFromGff` (the 14 scripts above), `ReadItemsFromGff` with "not a save": it asks
   `CSWSItem::LoadItem` for a full item struct, so a chargen `ItemList` of bare `InventoryRes`
   entries would not produce items — irrelevant because the list is empty (med). With no
   `Equip_ItemList` the "body item refused" flag (`+0xab8`) stays 0, so `EquipDefaultClothes`
   (`0x00501c40`, called from `RestoreParty` and `AddPartyMember`) **does nothing for a new player**.
5. `ReadSpellsFromGff` (none), `PostProcess` (`0x004f1c40`): AI level 4; marks equipped and
   inventory items (flag 8 of item `+0x288`; none yet); registers the tag (empty) in the module
   lookup; joins the **player faction** (faction object 0 of the faction manager, `FactionID` 0);
   applies one effect of internal type 0x44 (68), subtype 4, `ints[0]` = race (6) with the player
   as creator — it is in the save as the only `EffectList` entry; a flag at creature `+0xf0` is set
for players (med).
6. `SetPlayerControlled(1, 1)` (AI level 4, a 0x3c-byte player-control block at `+0x4c0`).
7. `RestoreParty` merges the player's repository and gold into the party table: with nothing
   in either, party gold and inventory start at 0 and the XP pool at 0. (party-items-saves.md 3)

## 5. Starting equipment and items

**The exe gives none.** Verified: no class-dependent code path creates items; `EquipDefaultClothes`
is conditional (above); the chargen item array is empty; Force powers are never given (`KnownList0`
absent). (high)

**The module does, through the area's OnEnter `k_pend_area01`** (module IFO `Mod_OnModLoad` and
`Mod_OnClientEntr` are empty; only `Mod_OnActvtItem = k_pend_activate`). On the PC's entry, the
first time, the script (script-VM behaviour, not exe):

1. fades out and plays movie `01A` (`movies/01a.bik`), sets global `K_CURRENT_PLANET` = 5,
2. creates the class kit **inside the footlocker tagged `end_locker01`** (placeable template
   `footlker001`, which already holds 2 × Medpac `g_i_medeqpmnt01`, Clothing `g_a_clothes01` and
   a Short Sword `g_w_shortswrd01`) — the player takes the gear from there; nothing is in the
   player's own inventory or worn at the start,
3. fades in, calls `SetMinOneHP(GetFirstPC(), TRUE)` immediately, and 0.1 s later Trask (tag
   `end_trask`) starts the opening conversation `m01aa_c01` with the player.

Class kits (`GetClassByPosition(1, PC)` of the player; ids from classes.2da):

| Class | Items created in the locker |
|---|---|
| 0 Soldier | `g_w_blstrrfl001` Blaster Rifle, `g_i_adrnaline003` Adrenal Stamina (third slot is the empty string, creates nothing) |
| 1 Scout | `g_w_blstrpstl001` Blaster Pistol, `g_i_adrnaline002` Adrenal Alacrity, `g_i_implant101` Cardio Package |
| 2 Scoundrel | `g_w_blstrpstl001` Blaster Pistol, `g_i_secspike01` Security Spike, `g_i_progspike01` Computer Spike |
| any | if `GetHasSkill(SKILL_STEALTH)` (the player has ranks in Stealth): `g_i_belt010` Stealth Field Generator |

The save's Combat Suit (`g_a_class4001`) and Short Sword come from other footlockers
(`footlker003`: also a Long Sword and 2 Fragmentation Grenades) and were equipped by the player in
play; they are not start state. Money: the party gold in the save (63) was picked up in play. (high
for the script, the path to `end_locker01` follows from the tag lookup, high)

## 6. A real player, one level deep (`Mod_PlayerList[0]` of the module `.sav`)

117 fields, struct id 48813. "New" = a freshly made character already has it when control
starts (from the BIC plus the loader's defaults); "play" = set by play, scripts or the save writer.

| Field(s) | Type | New | Notes |
|---|---|---|---|
| `Mod_CommntyName` 'Bad StrRef', `Mod_IsPrimaryPlr` 1, `Mod_FirstName`, `Mod_LastName` | CExoString, BYTE, CExoLocString ×2 | save writer | module-level copies of the login name data |
| `ObjectId` | DWORD | yes | 0x7fffffff |
| `FirstName`, `LastName`, `Description` | CExoLocString | yes | first name holds the whole typed name |
| `IsPC` 1, `Tag` '', `Conversation` '', `Interruptable` 1, `Age`, `Gender`, `Race` 6, `Subrace`, `SubraceIndex`, `StartingPackage`, `Deity`, `MClassLevUpIn` | | yes | |
| `willbonus fortbonus refbonus` | SHORT | yes (0) | |
| `Gold` | DWORD | yes (0) | the purse is in `PARTYTABLE` (`PT_GOLD`) |
| `RefSaveThrow WillSaveThrow FortSaveThrow` CHAR, `ArmorClass` SHORT | | derived at save time | |
| `Str Dex Int Wis Con Cha` BYTE, `NaturalAC` | | yes | raw scores, no race adjustment |
| `SoundSetFile` WORD, `Plot`, `Disarmable` 1, `PartyInteract`, `NotReorienting`, `BodyBag` | | yes | |
| `Min1HP` | BYTE | **play** | `k_pend_area01` sets it |
| `HitPoints` 0, `CurrentHitPoints`, `MaxHitPoints`, `PregameCurrent` (= current HP), `ForcePoints`, `CurrentForce`, `MaxForcePoints` | SHORT | `HitPoints` 0 as in the save; the others derived | `CurrentHitPoints` = `PregameCurrent` − `MaxHitPoints` + `HitPoints` (−6 = 4 − 10 + 0); the save's PC had 4/10 HP |
| `Experience` | DWORD | 0 | 450 in the save = also `PT_XP_POOL` |
| `MovementRate` 0, `PortraitId`, `GoodEvil` 50, `Color_*` ×4, `Phenotype`, `Appearance_Type`, `Appearance_Head` 1, `DuplicatingHead` 255, `UseBackupHead`, `Tail`, `Wings`, `FactionID` 0, `ChallengeRating` 0, `AIState` 0 | | yes | |
| `ClassList` | List[1], struct id 2: `Class` INT, `ClassLevel` SHORT | yes | |
| `LvlStatList` | List[1], struct id 0: `LvlStatHitDie`, `LvlStatForce`, `LvlStatClass` BYTE; `SkillPoints` WORD; `SkillList` List[8] of `Rank`; `FeatList` List of `Feat` WORD | yes (record 1) | grows by one record per level-up; the save writer adds `LvlStatForce` |
| `SkillPoints`, `SkillList`, `FeatList` | | yes | the top-level `FeatList` carries struct id 1, not 0 |
| `CombatInfo` | Struct id 51882: attack/damage modifiers, crit data, `LeftEquip`/`RightEquip` ids and names, damage dice | play | derived from equipment |
| `DetectMode` 1, `StealthMode`, `CreatureSize` 3, `IsDestroyable` 1, `IsRaiseable` 1, `DeadSelectable` 1 | BYTE, INT | loader defaults | |
| 14 `Script*` ResRefs | | yes | |
| `Equip_ItemList` | List, struct id = 1 << slot (body 2, right hand 16) of full item structs | **play** | empty at the start |
| `ItemList` | List of item structs | **play** | empty |
| `PerceptionList`, `CombatRoundData` | List, Struct | play | |
| `AreaId`, `XPosition..ZOrientation` | DWORD, FLOAT | placed by the arrival code | start position is the IFO's `Mod_Entry_*`: (15.4248, 20.1215, −1.275), facing (0, 1) |
| `AmbientAnimState`, `Animation` 10000, `CreatnScrptFird` 1, `Listening` 1, `ExpressionList` List[6] (`ExpressionId`, `ExpressionString`) | | play | the henchman spawn script `k_hen_spawn01` runs once for the player and sets the listen patterns (`GEN_I_WAS_ATTACKED`, `GEN_I_AM_DEAD`, `GEN_CALL_TO_ARMS`, …) |
| `PM_IsDisguised` 0, `JoiningXP` 0 | BYTE, INT | yes | |
| `FollowInfo` | Struct | play | |
| `EffectList` | List[1], struct id 2 | yes | the race effect from `PostProcess` (type 68, subtype 4, `ints[0]` 6); more from play |
| `VarTable` (empty), `SWVarTable`, `ActionList`, `Commandable` | | play | |

## 7. Mapping to `lib/rules` and `lib/engine`

`rules::read_creature` (`kotor/lib/rules/read.ctx`) reads: `Race`, `SubraceIndex`, `Gender`,
`Appearance_Type`, `FactionID`, the six scores, `NaturalAC`, `HitPoints`, `CurrentHitPoints`,
`ForcePoints`, the three bonuses, `GoodEvil`, `ChallengeRating`, `Experience`, `SkillPoints`,
`IsPC`, `Plot`, `Min1HP`, `ClassList` (`Class`, `ClassLevel`, `KnownList0/Spell`), `SkillList`,
`FeatList`, `SpecAbilityList`, `LvlStatList` (`LvlStatClass`, `LvlStatHitDie`, `LvlStatForce`,
`LvlStatAbility`, `SkillPoints`, `SkillList`, `FeatList`), `CurrentForce`.
`obj::Creature` (`kotor/lib/engine/object.ctx`) keeps `appearance gender race subrace portrait
soundset is_pc good_evil xp gold abilities classes class_levels`, the object header keeps `tag
name scripts hp hp_max plot min_one_hp faction conversation`; the UTC reader is
`templates.ctx` `read_creature`.

| Chargen/save data | `rules::Creature` | `obj::Creature` / `Object` | Gap |
|---|---|---|---|
| names | — | `Object.name` (one `Name`) | **no last name**; the chargen sets it empty so harmless; no `Description` |
| `IsPC` (absent in the BIC) | `is_pc` default 0 | `is_pc` default false | **must be forced to true** (and `pc_rules`); exe default is 1 |
| `Min1HP`, `Plot` | `min1hp`, `plot` | `Object.min_one_hp`, `plot` | none; the module script sets it |
| scores, classes, skills, feats | yes | placeholders `abilities classes class_levels` | to be replaced by the `rules::Creature` hook |
| `LvlStatList[0]` | `history[0]` | — | `LevelRecord.feats` is `[8]i32` and the reader stops at 8, but the first record of a Soldier has 10 feats (7 class grants + 3 chosen): two are dropped from the history (the top-level `FeatList` is complete) |
| `HitPoints` | `hp_base` (default 1 if absent) | `hp_max` | For a player the base is irrelevant; use `stats.max_hp` from the history |
| `CurrentHitPoints` | `loaded_hp` | `templates.ctx` takes it as **absolute** HP | wrong for players and saves: it is relative (4.3). For a new player set `hp = hp_max`; for a saved one use `PregameCurrent` (absolute) or add `max − HitPoints` |
| `MaxHitPoints` | — (recomputed) | `templates.ctx` reads it as `hp_max` | for a chargen file it is the wrong figure (4.3); recompute |
| `ForcePoints`, `CurrentForce` | `fp_base`, `fp` | — | relative like HP; all 0 at the start |
| `FactionID` | `faction` | `Object.faction` | BIC has none: use 0 (player faction) |
| `SoundSetFile`, `PortraitId`, `Gender`, `Race`, `Appearance_Type` | | yes | |
| `Color_*`, `Phenotype`, `Appearance_Head`, `DuplicatingHead`, `UseBackupHead`, `Tail`, `Wings` | — | **missing** (only `body_variation`, `texture_variation` exist, which are not these) | needed by the creature renderer (head via appearance.2da `normalhead`; raise head 0 to 1) |
| `Deity`, `Age`, `Interruptable`, `Disarmable`, `NotReorienting`, `BodyBag`, `PartyInteract`, `StartingPackage`, `MClassLevUpIn` | — | **missing** | not needed for play except `Interruptable` (dialogue) |
| `DetectMode`, `StealthMode`, `CreatureSize` | — | missing (size = appearance sizecategory in the rules decision; all player appearances are 3) | |
| 14 scripts | — | `Object.scripts` | the UTC reader already handles the 14 labels incl. `ScriptEndDialogu` |
| `Gold` | — | `Creature.gold` | party purse is the party table's |
| `EffectList` race effect | racial handling in `recompute` | — | the exe applies an internal race effect; if our rules derive race bonuses directly, nothing to add |

**Recipe for a builder** (what the exe's two halves amount to, without the TEMP file):

1. Take class, gender from the slot; portrait row from the portrait screen (gender-matching
   `ForPC` rows); `Appearance_Type` from that row by class (L / number / S); sound set 85 male,
   83 female; human race 6, no subrace; name; good-evil 50; XP 0; gold 0.
2. Abilities: custom (30 points) or the class row of classes.2da; stored without race adjustment.
3. Skills and feats: player's choices, or `rules::take_first_level{ class }` for the quick
   build. The first-level record has `LvlStatHitDie` = classes.2da `hitdie`, `LvlStatForce` 0, the
   class, the unspent skill points, the ranks after the level and **all** feats the character has.
4. Force points 0; powers none; items none; effects: the race effect only.
5. Flags: `IsPC` 1, `Interruptable` 1, `Disarmable` 1, `Plot` 0, `Min1HP` 0 (the module sets it),
   player faction (0), tag empty, the 14 henchman scripts above.
6. Place it at `Mod_Entry_*` of the start module's IFO after the module is loaded, current HP =
   maximum (from the history).

## 8. At the first arrival (only what the creation touches)

`PlacePlayerInModule` gives the new player the IFO entry position (no stored position exists), the
area OnEnter then runs once per GIT creature and once for the player (`GetIsPC`). In
`end_m01aa` that script does the movie, the locker kit, `SetMinOneHP` and the delayed Trask
conversation (section 5); the module's OnModLoad and OnClientEnter scripts are empty. The player's
spawn script `k_hen_spawn01` runs on its first AI update. (high for what the module does, the exact
interleaving with the other OnEnter scripts is gameloop.md's)

## 9. Open

- The initial portrait of each slot is random (`_rand` over the gender's `ForPC` rows, no
  repeats among slots of one gender); the portrait screen cycles through the gender's rows. The
  exact virtual call that sets it (`CSWCCreature` slot 61, `+0xf4`) is read as "set portrait id"
  (med).
- The ability pool of 30 and the point costs are derived from the cost rule and the six classes'
  recommended rows (each sums to 30); not read from a constant. (med)
- `DetectMode` is on for every loaded player in the save and in the decompilation, but the
  loader's treatment of the stored byte was unclear in the decompiler (med).
- `StartingPackage` and the chargen item array are never set in the shipped flow as far as
  traced; if a mod or a hidden option fills them, `ReadItemsFromGff`'s "not a save" mode would
  drop bare `InventoryRes` entries (med).
- Only one real save (a male Soldier) exists: the Scout and Scoundrel numbers (hit dice 8 and 6,
  their kits) follow from classes.2da and the script; they are not checked against a real
  save. Soldier HP at CON 14 (12, 13 with Toughness) is computed, not seen.
- The exact join arguments of `StartGame`'s connect call (`0x005d5040`: 0, address, "", 10, 16) and
  the meaning of the story hint and load-screen picture are not decoded here (gui.md 10.2 has the
  load-screen part).
- The order of OnEnter work between the creature's OnEnter, `k_pend_area01`'s fade-in and the
  conversation start is the generic arrival order; the 0.1 s delay is a script constant.
- Quick-build feat choices (`0x0064a770`) and skill buying (`0x00648a00`) were identified, not
  re-derived; `rules::take_first_level` should be compared with them on all three classes
  before it is called equal.
