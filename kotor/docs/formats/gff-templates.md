# GFF schemas: blueprints (UTC, UTD, UTP, UTI, UTE, UTS, UTT, UTW, UTM, BIC/BTC/BTI)

Blueprints ("templates") are the GFF files a module's GIT instances are made from: the GIT lists
an instance's position and its `TemplateResRef`, and the engine loads the blueprint of that name
for everything else (KOTOR's GITs set `UseTemplates` = 1 and carry only the instance-specific
fields; see [gff-module.md](gff-module.md)). Conventions, field-path notation, and the meaning of
the columns are in [gff-schemas.md](gff-schemas.md). Meanings follow BioWare's published NWN
documents (Creature, Situated Object, Item, Encounter, Sound Object, Trigger, Waypoint, Store) where
the field exists there; KOTOR-only fields are explained from the data and marked *(inferred)*.

Field order in the files is not significant for reading, but the toolset wrote the fields in the
order the tables list them (first-seen order of the inventory), which a writer may reproduce.

## Shared field groups

- **Identity.** `TemplateResRef` (the blueprint's own resref; equals the file name), `Tag` (the
  scripting name, not unique), `LocName`/`LocalizedName`/`FirstName` (display name, a
  CExoLocString whose strref resolves in `dialog.tlk`; a few blueprints carry inline English
  text instead, language/gender id 0), `Comment` (designer note; the game ignores it),
  `PaletteID` (toolset palette node; ignored by the game).
- **Script hooks.** Every `On*`/`Script*` ResRef names an NCS run on that event, with the object
  as `OBJECT_SELF`; empty means no script. The cross-check found every non-empty hook as an NCS in
  the install except a handful of NWN defaults (`nw_e0_default*`, `nw_c2_default*`, `nw_o0_*`)
  and a few dead names: the engine must treat a missing script as "no script".
- **Locks and traps** (doors, placeables, triggers): `Locked`, `Lockable`, `KeyRequired`,
  `KeyName` (tag of the key item), `AutoRemoveKey`, `OpenLockDC`, `CloseLockDC`, `TrapFlag`,
  `TrapType` (row in `traps.2da`), `TrapDetectable`, `TrapDetectDC`, `TrapDisarmable`,
  `DisarmDC`, `TrapOneShot`.
- **Inventory** (creatures, placeables, stores): `ItemList` of structs with `InventoryRes` (UTI
  resref) and `Repos_PosX`/`Repos_Posy` (grid position in the NWN-style inventory; KOTOR's
  inventory is a list, so these only order the items). Struct id = list index.
- **Faction**: `FactionID` (creatures, WORD) / `Faction` (others, DWORD) is a row of
  `repute.2da`, which KOTOR uses as the module faction table (the cross-check found every value a
  valid row); `repute.fac` in a module or save holds the live standings (see
  [gff-schemas.md](gff-schemas.md), FAC).

## UTC: creature

`Equip_ItemList` struct ids are the inventory-slot bit `1 << INVENTORY_SLOT_*` (nwscript.nss):
HEAD 0x1, BODY 0x2, HANDS 0x8, RIGHTWEAPON 0x10, LEFTWEAPON 0x20, LEFTARM 0x80, RIGHTARM 0x100,
IMPLANT 0x200, BELT 0x400, CWEAPON_L 0x4000, CWEAPON_R 0x8000, CWEAPON_B 0x10000, CARMOUR 0x20000
(creature weapons and creature hide). Every id seen matches. `SkillList` has one struct per row of
`skills.2da` (8 in KOTOR; 3 old files, `c_drdg`, `c_sebulba` and `nw_badger`, have 20).

<!-- gff-table UTC -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `TemplateResRef` | ResRef | all | e.g. `c_bantha`, `c_brith`, `c_dewback` | Blueprint resref (equals the file name). |
| `Race` | BYTE | all | 2, 5, 6, 8 | Row in `racialtypes.2da` (KOTOR: 5 droid, 6 human; 2, 8 only in NWN leftovers). |
| `SubraceIndex` | BYTE | 1809 | 0, 1, 2 | Row in `subrace.2da`: 0 none, 1 Wookiee, 2 beast. |
| `FirstName` | CExoLocString | all | strref in 1942 | Display name; strref into `dialog.tlk`. |
| `LastName` | CExoLocString | all | strref in 75; 1867 empty | Second name part, mostly empty. |
| `Appearance_Type` | WORD | all | 1..503 | Row in `appearance.2da`: model, textures, sizes, sounds of the body. |
| `Gender` | BYTE | all | 0, 1, 2, 3, 4 | Row in `gender.2da` (0 male, 1 female, 2 both, 3 other, 4 none). |
| `Phenotype` | INT | all | 0 | NWN body shape; always 0. |
| `PortraitId` | WORD | 1939 | 0..40 (25 values) | Row in `portraits.2da`, the GUI portrait. |
| `Description` | CExoLocString | all | strref in 9; 1933 empty | Examine text; almost always empty. |
| `Tag` | CExoString | all | e.g. `Bantha`, `Brith`, `Dewback` | Scripting tag (`GetObjectByTag`). |
| `Conversation` | ResRef | all | 1023 empty; e.g. `m41ad_c01`, `k_hbas_dialog`, `k_hcar_dialog` | DLG started by `ActionStartConversation` or clicking the creature. |
| `IsPC` | BYTE | all | 0 | 1 for a player character; 0 in every blueprint. |
| `FactionID` | WORD | all | 1..16 (11 values) | Faction: row in `repute.2da` / entry in the module's `repute.fac`. |
| `Disarmable` | BYTE | all | 0, 1 | 1 if the creature can be disarmed. |
| `Subrace` | CExoString | 1940 | always empty | NWN subrace text; always empty. |
| `Deity` | CExoString | all | always empty | NWN deity text; always empty. |
| `SoundSetFile` | WORD | 1939 | 1..65535 | Row in `soundset.2da` (the creature's barks: battle cries, pain, death); 65535 = none. |
| `Plot` | BYTE | 1940 | 0, 1 | 1 if plot: cannot be killed or damaged. |
| `Interruptable` | BYTE | 1940 | 0, 1 | 1 if its conversations can be interrupted. |
| `NoPermDeath` | BYTE | 1939 | 0, 1 | NWN: no explosive death. Kept by KOTOR; effect unverified. |
| `BodyBag` | BYTE | 1939 | 0 | Row in `bodybag.2da` for the container left on death; always 0 (none). |
| `BodyVariation` | BYTE | 1939 | 0, 1 | Body model variation for appearances whose model depends on armour *(inferred)*. |
| `TextureVar` | BYTE | 1939 | 0, 1 | Texture variation of the body model *(inferred)*. |
| `Min1HP` | BYTE | 1935 | 0, 1 | 1 if damage never takes the creature below 1 HP (scripted fights) *(inferred from name and use)*. |
| `PartyInteract` | BYTE | 1910 | 0, 1 | 1 if the creature shows the party-interaction icon / party members can initiate with it *(inferred)*. |
| `Str` | BYTE | all | 3..60 (24 values) | Strength score before bonuses. |
| `Dex` | BYTE | all | 3..28 (18 values) | Dexterity score before bonuses. |
| `Con` | BYTE | all | 3..32 (18 values) | Constitution score before bonuses. |
| `Int` | BYTE | all | 3..22 (17 values) | Intelligence score before bonuses. |
| `Wis` | BYTE | all | 3..18 (15 values) | Wisdom score before bonuses. |
| `Cha` | BYTE | all | 3..20 (16 values) | Charisma score before bonuses. |
| `WalkRate` | INT | all | 1..9 (8 values) | Row in `creaturespeed.2da` (walk and run rates). |
| `NaturalAC` | BYTE | all | 0..23 (20 values) | Natural armour class bonus. |
| `HitPoints` | SHORT | all | 1..1000 | Base maximum hit points, before bonuses. |
| `CurrentHitPoints` | SHORT | 1940 | 1..1000 | Current hit points. |
| `MaxHitPoints` | SHORT | 1939 | 1..1000 | Maximum hit points after bonuses. |
| `ForcePoints` | SHORT | 1939 | 0..1000 (36 values) | Base maximum Force points *(KOTOR; inferred by analogy with HitPoints)*. |
| `CurrentForce` | SHORT | 1939 | 0..1000 (36 values) | Current Force points *(inferred)*. |
| `refbonus` | SHORT | 1886 | 0..99 (18 values) | Bonus to Reflex saves. |
| `willbonus` | SHORT | 1886 | 0..99 (18 values) | Bonus to Will saves. |
| `fortbonus` | SHORT | 1886 | 0..99 (19 values) | Bonus to Fortitude saves. |
| `GoodEvil` | BYTE | all | 0..100 (12 values) | Alignment, 0 = dark side ... 100 = light side. |
| `LawfulChaotic` | BYTE | all | 0, 50 | NWN law/chaos axis; unused by KOTOR. |
| `ChallengeRating` | FLOAT | all | 0.13..75 (27 values) | Challenge rating, for XP awards. |
| `PerceptionRange` | BYTE | 1940 | 8, 10, 11 | Row in `ranges.2da` (sight/hearing distances). |
| `ScriptHeartbeat` | ResRef | all | 311 empty; e.g. `k_def_heartbt01`, `k_hen_heartbt01`, `nw_e0_default1` | OnHeartbeat script (every 6 s). |
| `ScriptOnNotice` | ResRef | all | 324 empty; e.g. `k_def_percept01`, `k_hen_percept01`, `k_def_heartbt01` | OnPerception script. |
| `ScriptSpellAt` | ResRef | all | 370 empty; e.g. `k_def_spellat01`, `nw_e0_defaultb` | OnSpellCastAt script (a Force power was used on it). |
| `ScriptAttacked` | ResRef | all | 321 empty; e.g. `k_def_attacked01`, `k_hen_attacked01`, `throw` | OnPhysicalAttacked script. |
| `ScriptDamaged` | ResRef | all | 324 empty; e.g. `k_def_damage01`, `k_hen_damage01`, `nw_e0_default6` | OnDamaged script. |
| `ScriptDisturbed` | ResRef | all | 384 empty; e.g. `k_def_disturb01`, `k_def_dialogue01`, `nw_e0_default8` | OnInventoryDisturbed script. |
| `ScriptEndRound` | ResRef | all | 324 empty; e.g. `k_def_combend01`, `k_hen_combend01`, `nw_e0_default3` | OnEndCombatRound script. |
| `ScriptEndDialogu` | ResRef | 1937 | 1028 empty; e.g. `k_def_endconv`, `k_def_rependd`, `k_ptar_dance_ed` | OnEndDialogue script *(KOTOR; label truncated to 16 chars)*. |
| `ScriptDialogue` | ResRef | all | 321 empty; e.g. `k_def_dialogue01`, `k_hen_dialogue01`, `k_ptat_banthdlg` | OnConversation script (also fires on shouts it hears). |
| `ScriptSpawn` | ResRef | all | 214 empty; e.g. `k_def_spawn01`, `k_def_ambmob`, `k_hen_spawn01` | OnSpawn script. |
| `ScriptRested` | ResRef | all | 1940 empty; e.g. `nw_e0_defaulta`, `k_def_endconv` | OnRested script; unused by KOTOR. |
| `ScriptDeath` | ResRef | all | 361 empty; e.g. `k_def_death01`, `k_def_damage01`, `nw_e0_default7` | OnDeath script. |
| `ScriptUserDefine` | ResRef | all | 349 empty; e.g. `k_def_userdef01`, `k_pdan_kath02`, `k_pdan_kath_d` | OnUserDefined script (`SignalEvent` with user events). |
| `ScriptOnBlocked` | ResRef | 1940 | 341 empty; e.g. `k_def_blocked01`, `k_hen_blocked01`, `nw_c2_defaulte` | OnBlocked script (path blocked by a door or creature). |
| `SkillList` | List | all | 8..20 entries; struct id 0 | One struct per `skills.2da` row, in row order. |
| `SkillList/Rank` | BYTE | all | 0..100 (28 values) | Ranks in that skill. |
| `FeatList` | List | all | 0..45 entries; struct id 1 | Feats the creature has (struct id 1). |
| `FeatList/Feat` | WORD | 1134 | 1..124 | Row in `feat.2da`. |
| `TemplateList` | List | 1939 | 0 entries | NWN creature templates; always empty. |
| `SpecAbilityList` | List | all | 0..99 entries; struct id 4 | Special abilities, usable as powers (struct id 4). |
| `SpecAbilityList/Spell` | WORD | 22 | 52, 63, 83, 299 | Row in `spells.2da`. |
| `SpecAbilityList/SpellFlags` | BYTE | 22 | 1 | Bit flags: 0x1 readied, 0x2 spontaneous, 0x4 unlimited uses. |
| `SpecAbilityList/SpellCasterLevel` | BYTE | 22 | 0, 1, 3 | Caster level the ability is used at. |
| `ClassList` | List | all | 1..3 entries; struct id 2 | Classes, 1 to 3 (struct id 2). |
| `ClassList/Class` | INT | all | 0..8 (9 values) | Row in `classes.2da`. |
| `ClassList/ClassLevel` | SHORT | all | 0..20 (21 values) | Levels in that class. |
| `ClassList/KnownList0` | List | 1939 | 0..51 entries; struct id 3 | Force powers known (struct id 3); KOTOR keeps all powers in list 0. |
| `ClassList/KnownList0/Spell` | WORD | 146 | 0..63 | Row in `spells.2da`. |
| `ClassList/KnownList0/SpellMetaMagic` | BYTE | 146 | 0 | NWN metamagic; always 0. |
| `ClassList/KnownList0/SpellFlags` | BYTE | 146 | 1 | 0x1 readied. |
| `ClassList/MemorizedList0` | List | 2 | 0 entries | NWN prepared spells; empty when present. |
| `Equip_ItemList` | List | all | 0..8 entries; struct ids vary (0/2399 = index) | Equipped items; struct id = slot bit (see above). |
| `Equip_ItemList/EquippedRes` | ResRef | 1332 | e.g. `g_i_crhide008`, `g_w_crslash001`, `g_w_null001` | UTI resref of the equipped item. |
| `Equip_ItemList/Dropable` | BYTE | 86 | 1 | 1 if the item drops on death *(inferred)*. |
| `PaletteID` | BYTE | all | 2, 3, 4, 5, 6, 9 | Toolset palette node; ignored by the game. |
| `Comment` | CExoString | all | 1827 empty; e.g. `Vibroblade`, `Lite`, `Basic insane Selk…` | Designer comment; ignored by the game. |
| `NotReorienting` | BYTE | 1629 | 0, 1 | 1 if the creature does not turn to face whoever talks to it *(inferred)*. |
| `ItemList` | List | 547 | 1..34 entries; struct id = index | Backpack items; struct id = index. |
| `ItemList/InventoryRes` | ResRef | 547 | e.g. `g_w_fraggren01`, `g_w_vbroshort01`, `g_w_vbroswrd01` | UTI resref. |
| `ItemList/Repos_PosX` | WORD | 547 | 0..9 (10 values) | NWN inventory grid x; only orders the items. |
| `ItemList/Repos_Posy` | WORD | 547 | 0, 1, 2, 3 | NWN inventory grid y. |
| `ItemList/Dropable` | BYTE | 178 | 1 | 1 if the item drops on death *(inferred)*. |
| `Portrait` | ResRef | 3 | e.g. `po_mark1_`, `george` | NWN portrait resref; only in leftovers (KOTOR uses `PortraitId`). |
| `SaveReflex` | BYTE | 3 | 0 | NWN leftover (3 files). |
| `Wings` | BYTE | 3 | 0 | NWN wing model; leftover. |
| `MoraleRecovery` | BYTE | 2 | 1 | NWN morale; leftover. |
| `Morale` | BYTE | 2 | 10 | NWN morale; leftover. |
| `MoraleBreakpoint` | BYTE | 2 | 5 | NWN morale; leftover. |
| `Tail` | BYTE | 3 | 0 | NWN tail model; leftover. |
| `SaveWill` | BYTE | 3 | 0, 2 | NWN leftover. |
| `SaveFortitude` | BYTE | 3 | 2 | NWN leftover. |
| `SubRace` | CExoString | 2 | always empty | NWN leftover spelling of `Subrace`. |
| `CRAdjust` | INT | 8 | 0 | Adjustment added to `ChallengeRating`; always 0. |
| `SoundSet` | DWORD | 1 | 4294967295 | NWN leftover (DWORD); KOTOR uses `SoundSetFile`. |
| `Appearance_Head` | BYTE | 1 | 1 | Head variation; in blueprints only in 1 file. Saves use it for the PC (see gff-save.md). |
| `RefBonus` | SHORT | 53 | 0 | Same as `refbonus` with different capitals; never in the same file as it. A reader should accept both. |
| `WillBonus` | SHORT | 53 | 0 | Same as `willbonus` (see `RefBonus`). |
| `FortBonus` | SHORT | 53 | 0 | Same as `fortbonus` (see `RefBonus`). |
<!-- /gff-table -->

## UTD: door

KOTOR picks a door's model through `GenericType` (row of `genericdoors.2da`, whose `modelname`
names the MDL); `Appearance` (`doortypes.2da` in NWN) is 0 in every door. `AnimationState` is 0
(closed) in every blueprint; a save stores the open state in `OpenState` (see gff-save.md).

<!-- gff-table UTD -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `KeyRequired` | BYTE | all | 0, 1 | 1 if opening needs the key item `KeyName`. |
| `TrapFlag` | BYTE | all | 0 | 1 if trapped; always 0. |
| `TrapOneShot` | BYTE | all | 1 | 1 if the trap disappears after firing. |
| `DisarmDC` | BYTE | all | 0, 28 | DC to disarm the trap. |
| `Description` | CExoLocString | all | 551 empty | Examine text; always empty for doors. |
| `OnTrapTriggered` | ResRef | all | always empty | OnTrapTriggered script; always empty. |
| `Comment` | CExoString | all | 2 empty; e.g. `Czerka Door 1`, `Dantooine Door 1`, `Dantooine Door 2` | Designer comment. |
| `OnFailToOpen` | ResRef | all | 434 empty; e.g. `k_pman_door08`, `k_pkor_faildoor2`, `k_pkor_faildoor1` | Script run when a creature fails to open it (locked). |
| `OpenLockDC` | BYTE | all | 0..200 (17 values) | Security DC to unlock. |
| `Locked` | BYTE | all | 0, 1 | 1 if locked. |
| `Conversation` | ResRef | all | 459 empty; e.g. `end_door01`, `kor39_doors`, `man26c_door01` | DLG used when the door is "talked to" (locked-door barks, computer panels). |
| `OnMeleeAttacked` | ResRef | all | always empty | OnPhysicalAttacked script; always empty. |
| `Portrait` | ResRef | 50 | always empty | NWN portrait resref; always empty. |
| `Interruptable` | BYTE | all | 1 | 1 if its conversation can be interrupted. |
| `TemplateResRef` | ResRef | all | e.g. `sw_door_czerka1`, `sw_door_dan1`, `sw_door_dan2` | Blueprint resref. |
| `TrapDisarmable` | BYTE | all | 1 | 1 if the trap can be disarmed. |
| `OnHeartbeat` | ResRef | all | 546 empty; e.g. `k_ptar_autoclose`, `k_ptar_rggate_hb` | OnHeartbeat script. |
| `OnSpellCastAt` | ResRef | all | always empty | OnSpellCastAt script; always empty. |
| `OnDamaged` | ResRef | all | always empty | OnDamaged script; always empty. |
| `OnOpen` | ResRef | all | 420 empty; e.g. `k_pman_door04`, `k_plev_ffsndoff`, `k_plev_airinopen` | OnOpen script. |
| `Hardness` | BYTE | all | 0, 2, 5, 10, 25 | Damage reduction against physical attacks. |
| `AnimationState` | BYTE | all | 0 | 0 closed, 1 open one way, 2 open the other way; 0 in every blueprint. |
| `OnLock` | ResRef | all | always empty | OnLock script; always empty. |
| `GenericType` | BYTE | all | 0..64 | Row in `genericdoors.2da`: the door's model and sounds. |
| `OnUnlock` | ResRef | all | always empty | OnUnlock script; always empty. |
| `Will` | BYTE | all | 0 | Will save. |
| `TrapDetectable` | BYTE | all | 1 | 1 if the trap can be detected. |
| `LinkedToFlags` | BYTE | 50 | 0 | Transition target kind (1 door, 2 waypoint); 0 in blueprints (set on GIT instances). |
| `TrapType` | BYTE | all | 0, 2 | Row in `traps.2da`. |
| `Lockable` | BYTE | all | 0, 1 | 1 if it can be re-locked. |
| `HP` | SHORT | all | 1, 20, 30, 100 | Maximum hit points. |
| `OnUserDefined` | ResRef | all | 465 empty; e.g. `k_pman_door05`, `k_pman_door04`, `k_pend_cut25` | OnUserDefined script. |
| `Faction` | DWORD | all | 1, 5 | Faction (row in `repute.2da`). |
| `PaletteID` | BYTE | all | 0, 6 | Toolset palette node. |
| `Plot` | BYTE | all | 0, 1 | 1 if it cannot be damaged or destroyed. |
| `LinkedTo` | CExoString | 50 | always empty | Transition target tag; empty in blueprints. |
| `TrapDetectDC` | BYTE | all | 0 | DC to detect the trap. |
| `LocName` | CExoLocString | all | strref in 550; 1 empty | Display name (strref). |
| `Appearance` | DWORD | all | 0 | NWN `doortypes.2da` row; always 0 in KOTOR (use `GenericType`). |
| `KeyName` | CExoString | all | 532 empty; e.g. `lev09_starcellkey`, `w_repkey`, `w_repkey2` | Tag of the key item that opens it. |
| `OnClosed` | ResRef | all | always empty | OnClosed script; always empty. |
| `CurrentHP` | SHORT | all | 1..300 (8 values) | Current hit points. |
| `AutoRemoveKey` | BYTE | all | 0, 1 | 1 if the key is taken from the opener's inventory. |
| `OnDisarm` | ResRef | all | always empty | OnDisarm script; always empty. |
| `Fort` | BYTE | all | 0, 5, 28 | Fortitude save. |
| `OnDeath` | ResRef | all | 550 empty; e.g. `k_pend_door18` | OnDeath script (destroyed). |
| `Tag` | CExoString | all | e.g. `Czerka Door 1`, `Dantooine Door 1`, `Dantooine Door 2` | Scripting tag. |
| `OnClick` | ResRef | all | 550 empty; e.g. `k_ptar_lockdoor2` | OnAreaTransitionClick script. |
| `CloseLockDC` | BYTE | all | 0 | DC to lock; always 0. |
| `Min1HP` | BYTE | 499 | 0, 1 | 1 if damage never takes it below 1 HP *(inferred)*. |
| `PortraitId` | WORD | 501 | 0, 558 | Row in `portraits.2da`; 0 or 558 (out of range, i.e. none). |
| `Ref` | BYTE | 501 | 0 | Reflex save; always 0. |
| `LoadScreenID` | WORD | 501 | 0 | Row in `loadscreens.2da` for its transition; always 0 (use the destination's). |
| `Static` | BYTE | 490 | 0, 1 | 1 if the door is static scenery that cannot be used *(inferred)*. |
<!-- /gff-table -->

## UTP: placeable

<!-- gff-table UTP -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Tag` | CExoString | all | e.g. `CivilFootLker`, `CivilBagStrap`, `LowBroknDrd` | Scripting tag. |
| `LocName` | CExoLocString | all | strref in 1569 | Display name (strref). |
| `Description` | CExoLocString | all | strref in 1; 1568 empty | Examine text; almost always empty. |
| `TemplateResRef` | ResRef | all | e.g. `g_trescivil001`, `g_trescivil002`, `g_tresdrd001` | Blueprint resref. |
| `AutoRemoveKey` | BYTE | all | 0 | 1 if the key is taken from the opener. |
| `CloseLockDC` | BYTE | all | 0 | DC to lock; always 0. |
| `Conversation` | ResRef | all | 1291 empty; e.g. `dan_crystal01`, `dan_egg01`, `dan14_cutjuh` | DLG used when the placeable is used for talk (computers, holograms, corpses with barks). |
| `Interruptable` | BYTE | all | 1 | 1 if its conversation can be interrupted. |
| `Faction` | DWORD | all | 1, 2, 5, 7, 19, 4294967295 | Faction (row in `repute.2da`); 4294967295 = none. |
| `Plot` | BYTE | all | 0, 1 | 1 if it cannot be damaged or destroyed. |
| `Min1HP` | BYTE | 1329 | 0, 1 | 1 if damage never takes it below 1 HP *(inferred)*. |
| `KeyRequired` | BYTE | all | 0, 1 | 1 if opening needs the key item `KeyName`. |
| `Lockable` | BYTE | all | 0, 1 | 1 if it can be re-locked. |
| `Locked` | BYTE | all | 0, 1 | 1 if locked. |
| `OpenLockDC` | BYTE | all | 0..100 (15 values) | Security DC to unlock. |
| `PortraitId` | WORD | 1331 | 0 | Row in `portraits.2da`; always 0. |
| `TrapDetectable` | BYTE | all | 1 | 1 if the trap can be detected. |
| `TrapDetectDC` | BYTE | all | 0 | DC to detect the trap. |
| `TrapDisarmable` | BYTE | all | 1 | 1 if the trap can be disarmed. |
| `DisarmDC` | BYTE | all | 0, 15 | DC to disarm the trap. |
| `TrapFlag` | BYTE | all | 0 | 1 if trapped; always 0. |
| `TrapOneShot` | BYTE | all | 1 | 1 if the trap disappears after firing. |
| `TrapType` | BYTE | all | 0, 7 | Row in `traps.2da`. |
| `KeyName` | CExoString | all | always empty | Tag of the key item; always empty. |
| `AnimationState` | BYTE | all | 0, 1, 2, 3, 4, 5 | Initial state: 0 default, 1 open, 2 closed, 3 destroyed, 4 activated, 5 deactivated (animations default/open/close/dead/on/off on the model). |
| `Appearance` | DWORD | all | 0..231 | Row in `placeables.2da`: model, light, sounds. |
| `HP` | SHORT | all | 1..100 (8 values) | Maximum hit points. |
| `CurrentHP` | SHORT | all | 1..100 (8 values) | Current hit points. |
| `Hardness` | BYTE | all | 0, 5, 10, 20 | Damage reduction against physical attacks. |
| `Fort` | BYTE | all | 5, 16 | Fortitude save. |
| `Ref` | BYTE | all | 0 | Reflex save; always 0. |
| `Will` | BYTE | all | 0 | Will save; always 0. |
| `OnClosed` | ResRef | all | 1560 empty; e.g. `k_psta_binclear`, `_false`, `k_psta_binopen` | OnClosed script. |
| `OnDamaged` | ResRef | all | always empty | OnDamaged script; always empty. |
| `OnDeath` | ResRef | all | 1563 empty; e.g. `k_pkas_swoopdeth`, `k_pdan_dark02`, `k_ptar_tranfr_od` | OnDeath script. |
| `OnDisarm` | ResRef | all | always empty | OnDisarm script; always empty. |
| `OnHeartbeat` | ResRef | all | 1390 empty; e.g. `k_zon_control`, `k_plc_tresmilhig`, `k_plc_trescorlow` | OnHeartbeat script. |
| `OnLock` | ResRef | all | always empty | OnLock script; always empty. |
| `OnMeleeAttacked` | ResRef | all | 1561 empty; e.g. `k_psta_atkplace` | OnPhysicalAttacked script. |
| `OnOpen` | ResRef | all | 1557 empty; e.g. `k_pend_chest01`, `k_plc_tresmillow`, `k_plc_tresmilmid` | OnOpen script. |
| `OnSpellCastAt` | ResRef | all | 1561 empty; e.g. `k_psta_castat` | OnSpellCastAt script. |
| `OnTrapTriggered` | ResRef | all | always empty | OnTrapTriggered script; always empty. |
| `OnUnlock` | ResRef | all | always empty | OnUnlock script; always empty. |
| `OnUserDefined` | ResRef | all | 1532 empty; e.g. `k_pend_resume`, `k_ptar_talker_ud`, `k_pdan_cort07` | OnUserDefined script. |
| `HasInventory` | BYTE | all | 0, 1 | 1 if it is a container the player can open. |
| `PartyInteract` | BYTE | 1260 | 0, 1 | 1 if party members can be chosen to interact with it *(inferred)*. |
| `BodyBag` | BYTE | 1331 | 0 | Row in `bodybag.2da`; always 0. |
| `Static` | BYTE | 1331 | 0, 1 | 1 if pure scenery: never interactive, needs no game object *(BioWare: static objects are not scriptable)*. |
| `Type` | BYTE | all | 0 | Obsolete; always 0. |
| `Useable` | BYTE | all | 0, 1 | 1 if the player can use (click) it. |
| `OnEndDialogue` | ResRef | 1329 | 1326 empty; e.g. `k_plev_resspikes` | Script run when its conversation ends *(KOTOR)*. |
| `OnInvDisturbed` | ResRef | all | 1556 empty; e.g. `k_pdan_destself`, `k_pend_chest02`, `k_pkas_morph1` | OnInventoryDisturbed script (items taken or added). |
| `OnUsed` | ResRef | all | 1347 empty; e.g. `k_pla_actmap`, `k_pdan_egg02`, `k_pkas_usebike` | OnUsed script. |
| `PaletteID` | BYTE | all | 0..12 (10 values) | Toolset palette node. |
| `Comment` | CExoString | all | 56 empty; e.g. `Civilian Footlock…`, `Civilian Bag & St…`, `Low Broken droid` | Designer comment. |
| `IsComputer` | BYTE | 69 | 0 | Always 0 *(KOTOR; presumably marks computer panels)*. |
| `Portrait` | ResRef | 238 | always empty | NWN portrait resref; always empty. |
| `ItemList` | List | 355 | 1..50 entries; struct id = index | Container contents (when `HasInventory`); struct id = index. |
| `ItemList/InventoryRes` | ResRef | 355 | e.g. `g_i_progspike01`, `g_i_medeqpmnt01`, `g_i_drdrepeqp001` | UTI resref. |
| `ItemList/Repos_PosX` | WORD | 355 | 0..6 (7 values) | NWN grid position; orders items only. |
| `ItemList/Repos_Posy` | WORD | 355 | 0..7 (8 values) | NWN grid position. |
<!-- /gff-table -->

## UTI: item

`BaseItem` (row of `baseitems.2da`) decides the item's class, slots, model type, stacking and
damage; `ModelVariation` picks the model (`<baseitems.defaultmodel>_<NNN>` for weapons and
gear), and armour (`BodyVariation`, `TextureVar`) picks the body model letter and texture
variant used when worn *(inferred from the data: every armour UTI has them, nothing else does)*.

<!-- gff-table UTI -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `TemplateResRef` | ResRef | all | e.g. `g1_a_class5001`, `g1_a_class5002`, `g1_a_class6001` | Blueprint resref. |
| `BaseItem` | INT | all | 0..91 | Row in `baseitems.2da`. |
| `LocalizedName` | CExoLocString | all | strref in 873 | Name once identified (strref). |
| `Description` | CExoLocString | all | strref in 88; 785 empty | Description before identification; mostly empty. |
| `DescIdentified` | CExoLocString | all | strref in 728; 145 empty | Description once identified (strref). |
| `Tag` | CExoString | all | e.g. `G1_A_CLASS5001`, `G1_A_CLASS5002`, `G1_A_CLASS6001` | Scripting tag (normally the resref in capitals). |
| `Charges` | BYTE | all | 0, 3, 5, 10, 50 | Charges left (for usable items with charges). |
| `Cost` | DWORD | all | 0..25000 | Base value in credits. |
| `Stolen` | BYTE | all | 0, 1 | 1 if stolen; always 0 in practice. |
| `StackSize` | WORD | all | 0..5000 (21 values) | Items in the stack (0 or 1 for unstackable ones). |
| `Plot` | BYTE | all | 0, 1 | 1 if a plot item: cannot be sold or dropped. |
| `AddCost` | DWORD | all | 0..25000 | Extra value added to `Cost`. |
| `Identified` | BYTE | all | 0, 1 | 1 if identified. |
| `BodyVariation` | BYTE | 103 | 1..10 (10 values) | Armour: body model variation when worn *(inferred)*. |
| `TextureVar` | BYTE | 103 | 1..8 (8 values) | Armour: texture variation when worn *(inferred)*. |
| `PropertiesList` | List | all | 0..35 entries; struct id 0 | Item properties (struct id 0). |
| `PropertiesList/PropertyName` | WORD | 530 | 0..59 | Row in `itempropdef.2da` (the property kind). |
| `PropertiesList/Subtype` | WORD | 530 | 0..129 | Row in the subtype table named by `itempropdef.subtyperesref`. |
| `PropertiesList/CostTable` | BYTE | 530 | 0..25 (14 values) | Row in `iprp_costtable.2da`, naming the cost table for `CostValue`. |
| `PropertiesList/CostValue` | WORD | 530 | 0..39 (20 values) | Row in that cost table (the property's amount). |
| `PropertiesList/Param1` | BYTE | 530 | 0, 1, 2, 9, 10, 255 | Row in `iprp_paramtable.2da`; 255 = no parameter. |
| `PropertiesList/Param1Value` | BYTE | 530 | 0..255 (11 values) | Row in the param table named by `Param1`. |
| `PropertiesList/ChanceAppear` | BYTE | 530 | 100 | Obsolete; always 100. |
| `PropertiesList/UpgradeType` | BYTE | 59 | 0..24 (25 values) | Row in `upgrade.2da` the property belongs to: set on properties a built-in upgrade or crystal provides, absent for native ones *(inferred; saves write 255 for native)*. |
| `PaletteID` | BYTE | all | 1..20 (16 values) | Toolset palette node. |
| `Comment` | CExoString | all | 504 empty; e.g. `Blue`, `clothing type 1`, `Brown` | Designer comment. |
| `ModelVariation` | BYTE | 766 | 1..70 | Model number for the item's model. |
| `ModelPart3` | BYTE | 4 | 1 | NWN composite model part; leftover. |
| `ModelPart2` | BYTE | 4 | 1 | NWN composite model part; leftover. |
| `ModelPart1` | BYTE | 4 | 1 | NWN composite model part; leftover. |
<!-- /gff-table -->

## UTE: encounter

A GIT encounter instance adds its polygon and spawn points (gff-module.md).

<!-- gff-table UTE -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Tag` | CExoString | all | e.g. `g_bandon`, `G_BLCKVULGROUP01`, `g_calonord` | Scripting tag. |
| `LocalizedName` | CExoLocString | all | strref in 132 | Name (toolset only). |
| `TemplateResRef` | ResRef | all | e.g. `g_bandon`, `g_blckvulgroup01`, `g_calonord` | Blueprint resref. |
| `Active` | BYTE | all | 0, 1 | 1 if it can spawn; inactive ones must be activated by script. |
| `Difficulty` | INT | all | 0, 1, 2, 5, 9 | Obsolete copy of `encdifficulty.2da` VALUE for `DifficultyIndex`. |
| `DifficultyIndex` | INT | all | 1, 2, 3, 4 | Row in `encdifficulty.2da`. |
| `Faction` | DWORD | all | 1, 5, 7 | Faction; spawns only for creatures hostile to it. |
| `MaxCreatures` | INT | all | 1..8 (7 values) | Most creatures alive at once. |
| `PlayerOnly` | BYTE | all | 0, 1 | 1 if only the player's party triggers it. |
| `RecCreatures` | INT | all | 1, 2, 3, 4, 5 | Recommended creature count ("min creatures"). |
| `Reset` | BYTE | all | 0, 1 | 1 if it respawns. |
| `ResetTime` | INT | all | 30, 60, 120 | Seconds before it can respawn. |
| `Respawns` | INT | all | -1, 0 | How many times it respawns; -1 = infinitely. |
| `SpawnOption` | INT | all | 1 | 0 continuous, 1 single shot; always 1. |
| `OnEntered` | ResRef | all | 118 empty; e.g. `k_trg_bandon`, `k_trg_calonord`, `k_tat_calonord` | OnEnter script. |
| `OnExit` | ResRef | all | always empty | OnExit script; always empty. |
| `OnExhausted` | ResRef | all | always empty | OnExhausted script; always empty. |
| `OnHeartbeat` | ResRef | all | always empty | OnHeartbeat script; always empty. |
| `OnUserDefined` | ResRef | all | always empty | OnUserDefined script; always empty. |
| `CreatureList` | List | all | 0..14 entries; struct id 0 | Creatures it can spawn (struct id 0). |
| `CreatureList/Appearance` | INT | 125 | 2..441 | Copy of the creature's `Appearance_Type` (row in `appearance.2da`). |
| `CreatureList/CR` | FLOAT | 125 | 0.5..20 (15 values) | Copy of the creature's challenge rating. |
| `CreatureList/ResRef` | ResRef | 125 | e.g. `c_drdmkone`, `g_darkjedi01`, `g_darkjedi02` | UTC resref to spawn. |
| `CreatureList/SingleSpawn` | BYTE | 125 | 0, 1 | 1 if only one of this creature may exist at a time. |
| `PaletteID` | BYTE | all | 0, 5, 6, 7, 9 | Toolset palette node. |
| `Comment` | CExoString | all | 65 empty; e.g. `Manaan - Sith base`, `Star Forge`, `Manaan - Hrakert …` | Designer comment. |
<!-- /gff-table -->

## UTS: sound object

Looping/Random combine as in BioWare's doc: random+looping picks a new random wave after each
interval forever; random only plays one random wave then deactivates; looping only plays the list
in order forever; neither plays the list once. `Continuous` sounds loop a single wave seamlessly
and ignore the interval and variation fields. Wave resrefs resolve to WAV resources or to files
in `streamsounds/` (see [audio.md](audio.md)).

<!-- gff-table UTS -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Tag` | CExoString | all | e.g. `birdsdantext110`, `swoopidle`, `dantroof` | Scripting tag. |
| `LocName` | CExoLocString | all | strref in 584; inline text in 8 (ids 0) | Name (toolset only). |
| `TemplateResRef` | ResRef | all | e.g. `swoopidle`, `dantroof`, `dantext110` | Blueprint resref. |
| `Active` | BYTE | all | 0, 1 | 1 if playing at start; else started by `SoundObjectPlay`. |
| `Continuous` | BYTE | all | 0, 1 | 1 for a seamless loop of one wave. |
| `Looping` | BYTE | all | 0, 1 | 1 to keep playing; 0 to play the list (or one random wave) once. |
| `Positional` | BYTE | all | 0, 1 | 1 if 3D-positioned; 0 if area-wide. |
| `RandomPosition` | BYTE | all | 0, 1 | 1 to play each wave at a random offset within `RandomRangeX`/`Y`. |
| `Random` | BYTE | all | 0, 1 | 1 to pick waves at random; 0 in list order. |
| `Elevation` | FLOAT | all | -8..5.5 (13 values) | Height offset of the emitter above its position. |
| `MaxDistance` | FLOAT | all | 5..300 (29 values) | Distance beyond which it is inaudible (m). |
| `MinDistance` | FLOAT | all | 1..60 (22 values) | Distance within which it plays at full volume (m). |
| `RandomRangeX` | FLOAT | all | 0..120 (13 values) | Random position range along x (m). |
| `RandomRangeY` | FLOAT | all | 0..100 (15 values) | Random position range along y (m). |
| `Interval` | DWORD | all | 0..25000 (22 values) | Milliseconds between waves. |
| `IntervalVrtn` | DWORD | all | 0..10000 (16 values) | Random +/- variation of the interval (ms). |
| `PitchVariation` | FLOAT | all | 0..1 (34 values) | Random pitch variation in octaves (0 to 1). |
| `Priority` | BYTE | all | 4, 5, 21, 22 | Row in `prioritygroups.2da`. |
| `Hours` | DWORD | all | 0 | Bit per hour of day it plays in (with `Times` = 0); always 0. |
| `Times` | BYTE | all | 3 | 0 specific hours, 1 day, 2 night, 3 always; always 3. |
| `Volume` | BYTE | all | 14..127 | Volume 0 to 127. |
| `VolumeVrtn` | BYTE | all | 0..74 | Random +/- volume variation. |
| `Sounds` | List | all | 1..22 entries; struct id 0 | Waves to play (struct id 0). |
| `Sounds/Sound` | ResRef | all | e.g. `as_an_dantext_01`, `as_an_dantext_02`, `as_an_dantext_03` | WAV resref. |
| `PaletteID` | BYTE | all | 0, 5, 6, 7 | Toolset palette node. |
| `Comment` | CExoString | all | always empty | Designer comment; always empty. |
<!-- /gff-table -->

## UTT: trigger

`Type` 0 generic, 1 area transition, 2 trap. Transitions use `LinkedTo` (tag of the destination
waypoint or door), `LinkedToFlags` (1 door, 2 waypoint) and, in KOTOR, `LinkedToModule` (the
destination module); in the shipped data these are set on GIT instances, not blueprints.

<!-- gff-table UTT -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Tag` | CExoString | all | e.g. `G_PARTYINIT001`, `G_T_TRAP001`, `G_T_TRAP002` | Scripting tag. |
| `TemplateResRef` | ResRef | all | e.g. `g_partyinit001`, `g_t_trap001`, `g_t_trap002` | Blueprint resref. |
| `LocalizedName` | CExoLocString | all | strref in 967; inline text in 1 (ids 0) | Name (toolset only). |
| `AutoRemoveKey` | BYTE | all | 0 | Unused. |
| `Faction` | DWORD | all | 1, 2, 5, 13, 19 | Faction; traps fire only for hostile creatures. |
| `Cursor` | BYTE | all | 0, 1 | Row in `cursors.2da` shown on mouse-over (only with an OnClick script); 1 for transitions. |
| `HighlightHeight` | FLOAT | all | 0, 0.1, 3 | Height of the in-game highlight volume (m). |
| `KeyName` | CExoString | all | 966 empty; e.g. `tar02_spngan`, `wraid` | Unused key tag. |
| `LoadScreenID` | WORD | 925 | 0 | Row in `loadscreens.2da`; always 0. |
| `PortraitId` | WORD | 925 | 0 | Row in `portraits.2da`; always 0. |
| `Type` | INT | all | 0, 1, 2 | 0 generic, 1 area transition, 2 trap. |
| `TrapDetectable` | BYTE | 965 | 0, 1 | 1 if the trap can be detected. |
| `TrapDetectDC` | BYTE | all | 0, 10, 20 | DC to detect the trap. |
| `TrapDisarmable` | BYTE | all | 0, 1 | 1 if the trap can be disarmed. |
| `DisarmDC` | BYTE | all | 0, 10, 20, 22, 30 | DC to disarm the trap. |
| `TrapFlag` | BYTE | all | 0, 1 | 1 if it is a trap. |
| `TrapOneShot` | BYTE | all | 1 | 1 if the trap disappears after firing. |
| `TrapType` | BYTE | all | 0..13 (14 values) | Row in `traps.2da` (mine type and strength). |
| `OnDisarm` | ResRef | all | always empty | OnDisarm script; always empty. |
| `OnTrapTriggered` | ResRef | all | always empty | OnTrapTriggered script; empty (the trap's script comes from `traps.2da`). |
| `OnClick` | ResRef | all | 967 empty; e.g. `temp_transition1` | OnClick script. |
| `ScriptHeartbeat` | ResRef | all | 878 empty; e.g. `k_zon_catalog`, `k_pman_steam02`, `k_pman_steam03` | OnHeartbeat script. |
| `ScriptOnEnter` | ResRef | all | 280 empty; e.g. `k_trg_partyinit`, `k_pdan_init14`, `k_bant_trig` | OnEnter script. |
| `ScriptOnExit` | ResRef | all | 936 empty; e.g. `k_amb_enemyflee`, `k_pdan_comp17`, `k_ptar_homint_ex` | OnExit script. |
| `ScriptUserDefine` | ResRef | all | always empty | OnUserDefined script; always empty. |
| `PaletteID` | BYTE | all | 0, 5, 6, 7, 8, 10 | Toolset palette node. |
| `Comment` | CExoString | all | 903 empty; e.g. `This is the Zone …`, `If the player or …`, `K_EBN_RAMP_ENTRAN…` | Designer comment. |
| `Portrait` | ResRef | 43 | always empty | NWN portrait resref; always empty. |
| `LinkedTo` | CExoString | 72 | always empty | Transition target tag; empty in blueprints. |
| `PartyRequired` | BYTE | 3 | 0 | Always 0 *(KOTOR; presumably: the whole party must be present to transition)*. |
| `LinkedToFlags` | BYTE | 72 | 0 | Transition target kind; 0 in blueprints. |
| `LinkedToModule` | ResRef | 69 | always empty | Destination module of a transition; empty in blueprints. |
<!-- /gff-table -->

## UTW: waypoint

Waypoints mark positions for scripts (patrol routes `WP_<tag>_NN`, spawn points, transition
destinations) and carry map notes.

<!-- gff-table UTW -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Appearance` | BYTE | 1892 | 1, 2, 3, 4 | Row in `waypoint.2da`: toolset model only, no effect in game. |
| `LinkedTo` | CExoString | all | always empty | Unused; always empty. |
| `TemplateResRef` | ResRef | all | e.g. `sw_waypoint003`, `sw_waypoint002`, `sw_waypoint004` | Blueprint resref. |
| `Tag` | CExoString | all | e.g. `WP03`, `WP04`, `WP06` | Scripting tag. |
| `LocalizedName` | CExoLocString | all | strref in 1896; inline text in 23 (ids 0) | Name (strref or inline text). |
| `Description` | CExoLocString | all | 1896 empty | Toolset description; always empty. |
| `HasMapNote` | BYTE | all | 0, 1 | 1 if it has a map note. |
| `MapNote` | CExoLocString | 1862 | strref in 105; 1757 empty | Map note text shown on the area map (strref). |
| `MapNoteEnabled` | BYTE | 1862 | 0, 1 | 1 if the map note is visible. |
| `PaletteID` | BYTE | all | 0, 1, 2, 3, 5 | Toolset palette node. |
| `Comment` | CExoString | all | 888 empty; e.g. `This is the defau…`, `This is a startin…`, `On the Advanced t…` | Designer comment. |
| `LinkedToModule` | ResRef | 32 | always empty | Always empty. |
<!-- /gff-table -->

## UTM: store

KOTOR's store is simpler than NWN's: one flat `ItemList` instead of NWN's per-panel
`StoreList`, and percentages `MarkUp`/`MarkDown` for selling to and buying from the player.

<!-- gff-table UTM -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `ResRef` | ResRef | all | e.g. `dan_droid`, `dan_general`, `dan_generalk` | Blueprint resref (UTM uses `ResRef`, not `TemplateResRef`). |
| `LocName` | CExoLocString | all | strref in 38; inline text in 2 (ids 0) | Store name (strref). |
| `Tag` | CExoString | all | e.g. `dan_droid`, `dan_general`, `dan_generalk` | Scripting tag. |
| `MarkUp` | INT | all | 75, 80, 100, 110, 140, 150 | Percentage of an item's value the store charges when selling *(inferred from BioWare's MarkUp/MarkDown with KOTOR's values 75..150)*. |
| `MarkDown` | INT | all | 20, 25, 40, 65 | Percentage of value the store pays when buying from the player *(inferred; 20..65)*. |
| `OnOpenStore` | ResRef | all | always empty | Script run when the store opens; always empty. |
| `BuySellFlag` | BYTE | all | 1, 3 | Bit 0: store sells; bit 1: store buys from the player *(inferred; values 1 and 3)*. |
| `ItemList` | List | 37 | 6..125 entries; struct id = index | Stock; struct id = index. |
| `ItemList/InventoryRes` | ResRef | 37 | e.g. `g_i_drdrepeqp002`, `g_i_medeqpmnt02`, `g_i_medeqpmnt04` | UTI resref. |
| `ItemList/Repos_PosX` | WORD | 37 | 0..9 (10 values) | NWN grid position; orders items only. |
| `ItemList/Repos_Posy` | WORD | 37 | 0..12 (13 values) | NWN grid position. |
| `ItemList/Infinite` | BYTE | 29 | 1 | 1 if never runs out. |
| `ID` | BYTE | all | 5 | Toolset palette node (store palette); always 5. |
| `Comment` | CExoString | all | 33 empty; e.g. `If player sold Ze…`, `If player sold Za…`, `discount version` | Designer comment. |
<!-- /gff-table -->

## BIC, BTC, BTI: NWN leftovers

`templates.bif` holds four GFFs the game never loads by name: `temp_char.bic` (an NWN-style
character file, tag `aWizard`), `nw_drmark1.btc`, `partymember.btc`, `sw_krayt.btc` (creature
blueprints in an older layout) and `nw_wblhvy001.bti` (an item). BTC/BTI use the UTC/UTI fields;
BIC adds NWN's body-part and colour fields, listed here for completeness (fields it shares with
UTC are omitted). None of this is needed to run the game.

<!-- gff-table BIC ~UTC -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `BodyPart_LBicep` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_LShoul` | BYTE | all | 0 | NWN part-based body: model part number per limb. |
| `ClassList/MemorizedList0/Spell` | WORD | all | 58, 101, 102, 107, 172, 175 | NWN memorised spells. |
| `ClassList/MemorizedList0/SpellMetaMagic` | BYTE | all | 0 | NWN memorised spells. |
| `ClassList/MemorizedList0/SpellFlags` | BYTE | all | 1 | NWN memorised spells. |
| `ArmorPart_RFoot` | BYTE | all | 1 | NWN armour part number. |
| `BodyPart_LFArm` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `Color_Skin` | BYTE | all | 1 | NWN skin, hair, tattoo palette row. |
| `BodyPart_LShin` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RShoul` | BYTE | all | 0 | NWN part-based body: model part number per limb. |
| `BodyPart_Torso` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_LHand` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_LFoot` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_Neck` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RShin` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RFArm` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_LThigh` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RBicep` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_Pelvis` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RHand` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `BodyPart_RThigh` | BYTE | all | 1 | NWN part-based body: model part number per limb. |
| `Color_Tattoo2` | BYTE | all | 1 | NWN skin, hair, tattoo palette row. |
| `Color_Hair` | BYTE | all | 1 | NWN skin, hair, tattoo palette row. |
| `Color_Tattoo1` | BYTE | all | 1 | NWN skin, hair, tattoo palette row. |
| `BodyPart_Belt` | BYTE | all | 0 | NWN part-based body: model part number per limb. |
<!-- /gff-table -->
