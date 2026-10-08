# Modules and areas in swkotor.exe

How the original engine goes from "load module X" to a playable area: which files it mounts, what
it reads from the IFO, ARE, GIT, LYT, VIS and PTH files, and how the client builds the rooms.
Addresses are for the Steam `swkotor.exe` after SteamStub removal. Names are ours (Aurora/NWN
vocabulary: `CSWSModule`, `CSWSArea` on the server/game side, `CSWCModule`, `CSWCArea` on the
client/presentation side), kept in [names.tsv](names.tsv). Confidence: **high** = read in the code;
**med** = behaviour clear, name or detail inferred; **low** = a guess. The whole page was rechecked
claim by claim on 2026-10-07 against the exports rebuilt after the noreturn fix
([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check" rests on static
reading alone and is surprising enough to test before relying on it.

Related pages: [resources.md](resources.md) (resource manager, GFF/2DA/TLK readers),
[resman.md](resman.md) (mount order at start-up), [objects.md](objects.md) (the objects a GIT
creates, the module/area class layouts and event handlers), [app.md](app.md) (main loops),
[gameloop.md](gameloop.md) 5 (transitions, the load ticks and the arrival order), and the
format pages [../formats/gff-module.md](../formats/gff-module.md),
[../formats/lyt.md](../formats/lyt.md), [../formats/vis.md](../formats/vis.md),
[../formats/pth.md](../formats/pth.md), [../formats/gff-save.md](../formats/gff-save.md).

KOTOR keeps NWN's client/server split even in single player: the server object
(`CServerExoAppInternal`) owns the game state (`CSWSModule`, `CSWSArea`, objects); the client
(`CClientExoAppInternal`) owns the presentation (`CSWCModule`, `CSWCArea`, the scene graph) and is
told about the area through an internal message.

## The sequence

| Step | Address | Name | What happens | Conf. |
|---|---|---|---|---|
| 1 | `0x004b95b0` | `CServerExoAppInternal::LoadModule(name, player)` | sets "load in progress" (`+0x100b4`), unloads the running module if any (`UnloadModule` `0x004b9240`, which removes `CURRENTGAME:`), then creates `CURRENTGAME:` and empties it (files and subfolders) when it already exists. Finds the module's main file: when `modulesave.2da` `IncludeInSave` allows it (`0x004b20e0`), `GAMEINPROGRESS:<m>` as type 3009 (`rsv`) or `.sav` (a module saved in the current game); else `NWMFILES:<m>.nwm`, else `MODULES:<m>.mod`, else `MODULES:<m>.rim`, else `LIVE1..6:MODULES\<m>` (`.mod`, then `.rim`). Each test mounts that folder as a directory and asks `Exists`, which searches every mounted source ([resources.md](resources.md) 1). Then, when the free space of `CURRENTGAME:` can be read, checks it against the file size. On success it stores the module name, the resolved source path, the target `CURRENTGAME:<m>.<ext>` and the resource type in the module-transition block at `g_pAppManager+0x14` ([gameloop.md](gameloop.md) 5.4) and sets load mode 3 when the file comes from `GAMEINPROGRESS:` (a save load or a module re-entered after a transition), else 1; busy and "skip one client frame" = 1, counters and error 0; also sets the save-space minimum (`0x004b5f90`). Fails (returns 0) with code 3 when no file is found and 1 when the disk is too full; the code goes to the `player` argument (the player who asked through an admin message), and `BeginLoadModule` passes 0, so on a transition nobody is told | high |
| 2 | `0x004babb0` | `CServerExoAppInternal::MainLoop` | runs the transition as a small state machine over several ticks, using the transition block's step and area counters (only while its error code is 0 and its mode is 1 or 3): step 0 copies the module file (`CopyModuleFile` `0x004b1680`: `CopyFileA` from the resolved source path to `CURRENTGAME:<m>.<ext>`, overwriting, clearing read-only; failure = error 5), creates `new CSWSModule(name, 0)` (0x224 bytes; for a type-3009 file it sets `Mod_IsNWMFile` +0x200 = 1 and `Mod_NWMResName` +0x204 = the name) and calls `LoadModuleStart(name, client +0x33c)`; the following steps call `ClearNPCObjectIds` (`0x005639c0`) and `LoadModuleInProgress(loaded)`, and when the counters meet, `LoadModuleFinish`. A non-zero result from any of them goes to `FailModuleLoad` (`0x004ba5b0`) as the error code | high |
| 3 | `0x004c84a0` | `CSWSModule::CSWSModule(name, bRequest)` | stores `"CURRENTGAME:" + name` at +0x5c, calls `AddModuleResources` with that string, sets defaults (time 0x53c = year 1340, month and day 1, `Mod_MinPerHour` 5, XP scale 10...), points its IFO helper at resref `MODULE` (`CSWSModule::SetResRef` `0x004c4cc0`, type 2014; `bRequest` starts an asynchronous request, and `MainLoop` passes 0), registers itself in the object array and records the world time at +0x1c0/+0x1c4 | high |
| 4 | `0x004c4150` | `CSWSModule::AddModuleResources(name)` | see [Mounting](#mounting-a-modules-files); runs the resman loader thread while drawing the load-screen progress bar | high |
| 5 | `0x004c9050` | `CSWSModule::LoadModuleStart(name, bResetTime)` | frees spare resman memory (`FreeChunk`), re-mounts if the name differs from the stored one (never, when called from `MainLoop`), demands `module.ifo` and reads it ([IFO](#the-ifo)), then the factions and the IFO's `Creature List`; sets the transition block's area count to the number of `Mod_Area_list` entries and tells the client. Returns 0, 1 when the IFO cannot be demanded, 3 when an allocation fails. The IFO stays demanded until `LoadModuleFinish` | high |
| 6 | `0x004c5720` | `CSWSModule::LoadModuleInProgress(n)` | `new CSWSArea(Area_Name, 0, id)` (`0x0050cf80`; a new id, or the saved `ObjectId` when loading a save) and `CSWSArea::LoadArea` (`0x0050e190`); on success sets "areas loaded" = n + 1, records a new area's id at module +0x40 and tells the client the progress; on failure releases the IFO and unmounts the module (result 3 when the area cannot be allocated, 4 when `LoadArea` fails, which also deletes the area) | high |
| 7 | `0x004c5880` | `CSWSModule::LoadModuleFinish` | sets "areas loaded" = count and tells the client the progress, queues **MODULE_LOAD** (script event 17, event 10 with no delay, the module as caller and target: OnModLoad), releases the IFO, marks the module loaded (+0x1d8 = 1; the constructor sets 1 and `LoadModuleStart` clears it); always returns 0. The "module loaded" status to the client is sent by `MainLoop` ([gameloop.md](gameloop.md) 5.4) | high |
| 8 | `0x0064bab0` | client: `CSWCMessage::HandleServerToPlayerAreaLoad` (server→client message major 4 "Area", minor 1, built by `0x0056cd20` and sent by `PrepareAreaForPlayer` `0x004b3a90`) | shows the load screen: the message's row byte picks it, 1 = a picture name carried in the message, 0 = a random `loadscreens.2da` row from 2 to the last, else that row's `BMPResRef`; renders a loading frame, then `CSWCArea::LoadArea` (`0x00607610`) on the client module's area (+0x48) and places the player creature at the position and facing carried in the message | high |
| — | `0x004c44d0` | `CSWSModule::RemoveModuleResources(name)` | the reverse of step 4 and of the loader thread, called by the module destructor (`0x004c68a0`), by `LoadModuleInProgress` on failure and by `LoadModuleStart` before a re-mount | high |

Only the **first** entry of `Mod_Area_list` is used: `LoadModuleInProgress` always builds
`Mod_Area_list[0]`, although the area count is the length of the list, so an IFO listing two
areas would build the first one twice (static reading). Every shipped KOTOR module has exactly
one area.

## Mounting a module's files

`CSWSModule::AddModuleResources(name)` (`0x004c4150`, high), with `<m>` the name without any
`alias:` prefix:

1. mounts `HD0:players` as an ERF in group 2 (an Xbox file; absent on PC);
2. temporarily mounts the directory `CURRENTGAME:` to test whether `<m>.sav` exists (the test
   searches every mounted source); if so the module comes from a save game (module+0x1c8);
   unmounts it;
3. mounts `LIPS:<m>_loc` and `LIPS:localization` as ERFs in group 2 (lip-sync archives; the
   Steam install has both kinds, `localization.mod` included);
4. starts the resman loader thread (`CExoResMan::StartModuleLoad` `0x004064f0`) with (name, is a
   module, from save) and polls its state every 10 ms, advancing the progress bar about once a
   second, until it is done; the result bits go to the client. The loader's success or failure
   is not checked here: a module whose files did not mount fails later, when `LoadModuleStart`
   cannot demand the IFO.

The loader thread body `CExoResMan::LoadModuleResources` (`0x004094a0`, high) then mounts, recording
each success in the bits at resman+0x5c:

| Order | Source | Kind | Condition | Bit |
|---|---|---|---|---|
| 1 | `RIMS:<m>_a` | RIM | `<m>_a.rim` exists (Xbox area add-on; none on PC) | 0x10 |
| 2 | `RIMS:<m>_adx` | RIM | `<m>_adx.rim` exists (none on PC) | 0x20 |
| 3 | `MODULES:<m>` | ERF group 2 | `<m>.mod` exists in any mounted source, `MODULES:` being mounted as a directory for the test (a mod or patch) | 0x02 |
| 3' | `MODULES:<m>_s` | RIM | otherwise, if `<m>_s.rim` exists (the module's dialogs, scripts and blueprints) | 0x08 |
| 4 | `CURRENTGAME:<m>` | RIM | not from a save, and `<m>` exists as type 3009 or `.rim`, `CURRENTGAME:` being mounted as a directory for the test (the copy `CopyModuleFile` made at step 2 of the sequence: the module's IFO, ARE, GIT and other per-area files); when it is in neither form the load still counts as successful | 0x01 |
| 4' | `CURRENTGAME:<m>` | ERF group 2 | from a save: the module's `.sav`; also tried in place of step 4 when any RIM or `.mod` mount of steps 1-3' fails, the remaining steps being skipped (med: static reading only, needs a runtime check) | 0x04 |

The existence tests search every mounted source ([resources.md](resources.md) 1), so a `<m>.mod`
or `<m>_s.rim` found elsewhere (an override directory, say) also takes that branch; the mount then
still opens the file in `MODULES:`. The loader's state ends as 2 when `<m>_s.rim` was mounted, 3
otherwise, 4 when the last mount it tried failed. `MODULES:` and `CURRENTGAME:` are mounted as
directories only for the existence tests and unmounted again. Combined with the lookup order
(directories, ERF group 1, RIMs newest first, ERF group 2 newest first, KEY) this gives, for a
module on PC without a `.mod`: `Override` > `patch.erf` > `<m>.rim` (the copy in `CURRENTGAME`) >
`<m>_s.rim` > `global.rim` and the other RIMs > lips ERFs > texture packs > chitin.key. When
`<m>.mod` exists, `LoadModule` copies the `.mod` instead of the `.rim` and the loader mounts
`MODULES:<m>.mod` in place of both RIMs; being an ERF of group 2 it then ranks below every RIM
(`global.rim` included) but above the lips and texture-pack ERFs, which were mounted earlier. A
save-game module (`.sav`) takes the same place as a `.mod` (newer, so above it), with `<m>_s.rim`
(or the `.mod`) still mounted for the static resources (med: inferred from the code paths, not
observed in a running game).

## The IFO

`LoadModuleStart` reads `module.ifo` (type 2014, GFF `"IFO "`) through `CResIFO` and stores into
`CSWSModule` (high unless marked):

| Field(s) | Stored at | Notes |
|---|---|---|
| `Mod_IsSaveGame`, `Mod_IsNWMFile`, `Mod_NWMResName` | +0x1c8, +0x200, +0x204 | defaults from the mount step (`IsSaveGame`) and from `MainLoop` (`IsNWMFile` = 1 for a type-3009 main file); `Mod_NWMResName` is read only when `IsNWMFile` is 1 |
| `Mod_ID` (up to 32 bytes), `Mod_Creator_ID`, `Mod_Version` | block at +0x54 (`Mod_Creator_ID` at +0x20, `Mod_Version` at +0x24 in it) | |
| `Mod_Name`, `Mod_Description` | +0x64, +0x4c | `CExoLocString` |
| `Mod_StartMovie` | +0x7c | resref |
| `Mod_Tag` | +0x1f8 (set through `0x004c3060`, lower-cased) | |
| `Mod_Entry_Area`, `Mod_Entry_X/Y/Z`, `Mod_Entry_Dir_X/Y` | block at +0x58 (resref, then floats at +0x10..+0x20) | direction defaults to (1, 0) when `Mod_Entry_Dir_Y` is missing |
| `Mod_MinPerHour`, `Mod_DawnHour`, `Mod_DuskHour` | bytes +0x1a0..+0x1a2 | default 0 |
| `Mod_StartYear/Month/Day/Hour`, `Mod_StartMinute/Second/MiliSec`, `Mod_Transition`, `Mod_PauseTime`, `Mod_PauseDay` | year +0x1a8; month, day, hour bytes +0x1a3..+0x1a5 (copied to +0x1ac, +0x1b0, +0x1b4); `Mod_Transition` +0x1b8; minute, second, ms and the pause pair go to the world timer | read only when `bResetTime`; otherwise the stored transition time is used ([gameloop.md](gameloop.md) 7.2). Defaults 1340 / 6 / 1 / 23 |
| `Mod_XPScale` | byte +0x1a6 | default 10 |
| `Mod_Expan_List` (`Expansion_Name`, `Expansion_ID`) | list at +0x28 | |
| `Mod_CutSceneList` (`CutScene_Name`, `CutScene_ID`) | list at +0x2c | |
| `Mod_OnHeartbeat`, `Mod_OnUsrDefined`, `Mod_OnClientEntr`, `Mod_OnClientLeav`, `Mod_OnActvtItem`, `Mod_OnAcquirItem`, `Mod_OnUnAqreItem`, `Mod_OnModLoad`, `Mod_OnModStart`, `Mod_OnPlrDeath`, `Mod_OnPlrDying`, `Mod_OnSpawnBtnDn`, `Mod_OnPlrRest`, `Mod_OnPlrLvlUp`, `Mod_OnEquipItem` | 15 `CExoString`s from +0xb0, 8 bytes apart, in the order heartbeat, user-defined, mod load (+0xc0), mod start (+0xc8), client enter (+0xd0), client leave, activate, acquire, unacquire, death (+0xf8), dying, spawn button, rest, level up, equip (+0x120) | script resrefs |
| `Mod_Area_list[0].Area_Name` | +0x30 | resref of the one area |
| `Mod_Area_list[0].ObjectId`, `Mod_Effect_NxtId`, `Mod_NextCharId0/1`, `Mod_NextObjId0/1` | +0x40, the next effect id and the object array's id counters | only for a save game |
| `Mod_PlayerList` (`Mod_CommntyName`, `Mod_FirstName`, `Mod_LastName`, `Mod_IsPrimaryPlr`) | list at +0x48 | only for a save game |
| `Mod_Tokens` (`Mod_TokensNumber`, `Mod_TokensValue`) | `CTlkTable::SetCustomToken` | only for a save game |
| `VarTable`, `SWVarTable` | +0x8c, +0x9c (`0x0059aa80`, `0x0059b0f0`) | module locals; only for a save game |
| the event queue | `CServerAIMaster::LoadEventQueue` (`0x004b0a00`) | only for a save game |

After the IFO it loads the faction table: it mounts `GAMEINPROGRESS:` as a directory
(`0x005638d0`, reference-counted) and, when `REPUTE.fac` exists in a directory source, reads it
as a `CResGFF` of type 2038 / `"FAC "` (`FactionList` through `0x0052b5c0`, then `RepList`
through `0x0052bbe0`), then unmounts it (`0x00563950`). When the file is missing or its
`FactionList` is missing or does not load, it builds the default factions from `repute.2da`
(the rules' 2DA cache +0xe0): one faction per row (`LABEL`) through `0x0052b490`, which always
returns 1, then the reputation matrix from the row values clamped to 0..100 (`0x0052b9e0`); the
other branch (`0x0052bce0`) is never taken from here.
Finally it reads the IFO's `Creature List` (`0x004c8c70`): each element with struct id 4 becomes a
full `CSWSCreature` with its saved `ObjectId` (`LoadCreature`; one that fails to load is deleted),
marked as having fired its spawn script (+0x34c), turned to `X/Y/ZOrientation` and listed in the
module (+0x1dc, count +0x1e0); its `XPosition`/`YPosition`/`ZPosition` are read and discarded. The
save writer stores this list back (`0x004c5bb0`: `ObjectId` and `SaveCreature` for each listed
creature).
Not read anywhere: `Mod_Hak` (the writer stores it, the reader ignores it), `Mod_VO_ID`,
`Mod_GVar_*` (neither name is in the exe).

`CSWSModule::SaveModuleIFOStart` (`0x004c7050`) and `SaveModuleIFO` (`0x004c8960`, which sets
"is a save" +0x1c8, deletes the old file, creates an ERF written as `"MOD V1.0"` with three
entries and an `"IFO "` `"V2.0"` GFF in it, then calls `SaveModuleIFOStart` and writes the
repute file) are the save-game writers of the same fields, except `Mod_StartMovie` and
`Mod_OnEquipItem`, which are not written, plus `Mod_Hak`, the event queue, the locals and the
`Creature List` ([party-items-saves.md](party-items-saves.md) 1.2) (high).

## The area (server side)

`CSWSArea` (0x2d4 bytes; constructor `0x0050cf80(resref, bRequest, object id)`, where `bRequest`
is the ARE helper's request flag and id 0x7f000000 asks for a new id; destructor `0x0050d370`)
embeds a resource helper for its ARE at +0x100 (`CSWSArea::SetResRef` `0x00506c30`, type 2012,
`CResARE`) and a `CGameObject` at +0x11c (see [objects.md](objects.md)). `CSWSArea::LoadArea(bFromSave)`
(`0x0050e190`, high) demands the ARE (returns 0 when it cannot), then:

| Step | Address | Name | Reads |
|---|---|---|---|
| a | `0x00508c50` | `LoadAreaHeader(top struct)` | the ARE: `ID`, `Creator_ID`, `Version`, `Comments`, `Expansion_List`, scripts `OnHeartbeat` / `OnUserDefined` / `OnEnter` / `OnExit`, `Name`, `Tag`, `Flags`, `CameraStyle`, `DefaultEnvMap`, `Unescapable`, `RestrictMode`, weather chances and `WindPower` (all zeroed when `Flags` bit 0 is set), moon and sun lighting/fog/shadow fields, `DayNightCycle`, `IsNight`, `DynAmbientColor`, `NoRest`, `ShadowOpacity`, `LightingScheme`, `ModSpotCheck`, `ModListenCheck`, `MiniGame` (only whether the struct is present, area +0x234; see [minigames-swoop-turret.md](minigames-swoop-turret.md)), `LoadScreenID`, the `Grass_*` fields (`Grass_TexName` defaults to `grass`), `AlphaTest` (default 0.2), the `Rooms` list (`RoomName`, `EnvAudio`, `AmbientScale`, `PartSounds` with `Looping`/`ModelPart`/`OmenEvent`/`Sound`), the `Map` struct (`MapResX`, `NorthAxis`, `MapZoom`, `MapPt1/2`, `WorldPt1/2`; read only when the map texture `lbl_map<area>` exists as TGA or TPC and `MapResX` is not 0; float `MapPt*` values are fractions scaled to 440 × 256, integer ones are taken as they are; handed to the module's map object at module +0x218 through `0x00578c60`), the stealth-XP fields and `TransPending*`. Side effects on the party table: `ResetFollowState` when party table +0xe8 is 1, and a `RestrictMode` that is set and differs from the area's current value turns party stealth on (`SetPartyStealthMode(1)`; med, needs a runtime check, since `PlacePartyAroundLeader` turns stealth off again on arrival after a transition, [party-items-saves.md](party-items-saves.md) 1.8) |
| b | `0x005073d0` | `LoadLayout` | sets the area's size fields +8/+0xc to the constants 40 and 40 (`0x007a1b48`); `<area>.lyt` through a temporary `CLayout`: room count at +0x22c and a room array at +0x230 (`0x00504870`: one 0x4c-byte `CSWSRoom` per LYT room, named and placed from the LYT, whose walkmesh `<room>.wok` is loaded at once by `CSWSRoom::LoadWalkmesh` `0x00579520`; then every pair of rooms is linked, `0x005796d0` with a 0.01 tolerance and `0x00579740`, med: presumably shared walkmesh edges; [movement.md](movement.md) 3.5) |
| c | `0x0050dd80` | `LoadGIT(bFromSave)` | `<area>.git` (type 2023, `"GIT "`; nothing when the file does not exist): with a save first the area's `VarTable`/`SWVarTable`, `CurrentWeather`, `WeatherStarted`; then `UseTemplates`; then the lists in this order: `Creature List` `0x00504a70`, `List` (items) `0x00504de0`, `Door List` `0x0050a0e0`, `TriggerList` `0x0050a350`, `Encounter List` `0x00505060`, `WaypointList` `0x00505360`, `SoundList` `0x00505560`, `Placeable List` `0x0050a7b0`, `StoreList` `0x005057a0`, `AreaEffectList` `0x00505af0`; then `AreaProperties` `0x00507490` (save state: `Unescapable`, `RestrictMode`, stealth XP, `TransPending*`, `SunFogColor`), `AreaMap` `0x00505da0` (explored-map bitmap: `AreaMapResX/Y`, `AreaMapDataSize`, `AreaMapData`), `CameraList` `0x00505eb0` (`CameraID`, `Position`, `Orientation`, `Height`, `Pitch`, `FieldOfView`, `MicRange`). The per-list loaders and the objects they build are in [objects.md](objects.md#3-building-objects-templates-git-entries-saves) |
| d | `0x00508400` | `LoadPathPoints` | `<area>.pth` (type 3003, GFF `"PTH "`): `Path_Points` (`X`, `Y`, `Conections`, `First_Conection`) and `Path_Conections` (`Destination`); spelling as in the files |

Then it releases the ARE, registers the area's tag (+0x158) with the module's tag table
(`AddObjectToLookupTable` `0x004c7de0`) and sets the byte +0x223 to ceil(width × height / 8) from
the +8/+0xc fields, which step b always sets to 40 × 40, so it is always 200 (what reads it is not
traced). `LoadArea` ignores the results of the header, layout, GIT and path steps and returns 1:
an area without a GIT simply has no objects.

## Layout, rooms and visibility (client side)

**`CLayout`** (0x60 bytes, constructor `0x005de770`; a `CResHelper<CResLYT,3000>` plus arrays) is the
engine's LYT reader, used by both the server (step b above) and the client:

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005df140` | `CLayout::LoadLayout(resref)` | converts the resref and calls `ParseLayout` | high |
| `0x005de900` | `CLayout::ParseLayout(name)` | demands the LYT (returns 0 when it cannot, else 1) and copies it to a NUL-terminated buffer; skips lines until one that is exactly `beginlayout` (a file without it is not handled: the scan runs past the buffer, static reading); then up to four sections, each a `<keyword> <count>` line followed by `count` lines `name x y z` (rooms, tracks, obstacles) or `name room hookId x y z qx qy qz qw` (door hooks: count at +0x30, names +0x4c, rooms +0x50, positions +0x54, orientations +0x58, ids +0x5c), until a line that is exactly `donelayout`. The keyword itself is not checked: the sections are taken in the fixed order rooms, tracks, obstacles, door hooks | high |
| `0x005de470` / `0x005de4a0` | `GetRoomName` / `GetRoomPosition` | +0x34 resrefs, +0x40 vectors, count +0x24 (`0x005a4c50`) | high |
| `0x005de4d0` / `0x005de500` | `GetTrackName` / `GetTrackPosition` | +0x38, +0x44, count +0x28 (`0x005d64f0`) | high |
| `0x005de530` / `0x005de560` | `GetObstacleName` / `GetObstaclePosition` | +0x3c, +0x48, count +0x2c | high |
| `0x005de450` | `CLayout::UnloadLayout` | releases the LYT | high |

The client module itself is built by `CSWCModule::LoadFromMessage` (`0x0063f660`, which creates the
area object at module +0x48 and the camera at +0x40) when the server's module message 3/1 arrives
(`HandleServerToPlayerModule` `0x006684f0`); the area is filled later by the area message (step 8
of the sequence; arrival order in [gameloop.md](gameloop.md) 5.5) (high).

**`CSWCArea::LoadArea`** (`0x00607610`, high) builds the client area from the server's area message
rather than from the ARE: the area resref (+0x10c), lighting, fog and colour values, the grass
settings (registered for each of the first 32 `surfacemat.2da` rows whose `Grass` column is set),
the room list with its ambient and env-audio values and the room sound entries, the area size.
When the message's "has minigame" byte is set it creates the minigame object (0xf0 bytes,
`0x00671c40`) at area+0x264. It then:

1. creates the scene `mainscene` (`CAurScene::Create` `0x00458e70`, area+0x184);
2. loads `<area>.lyt` with a `CLayout` and creates one 0x48-byte room object per LYT room (array at
   area+0x260, count +0x25c): the room model (named after the room) placed at the LYT position,
   looping `animloop1`..`animloop3` started on it, and per-room sound emitters (`MGB_null` /
   `sounddummy` helper models) for the ARE's `Rooms` sound entries whose `ModelPart` node exists
   in the room model; the load-screen bar advances every fifth room and at the last;
3. only when the area has a minigame: hands the LYT tracks (swoop-race track pieces) and obstacles
   to the minigame object (`0x006720c0`, `0x00672240`) and initialises it (`0x006723d0`); if that
   fails the load stops and returns failure;
4. asks the scene to load visibility: `CAurScene::LoadVisibility(<area>)` (scene vtable slot 37,
   `0x004568d0`) reads `<area>.vis`. Without a VIS file it calls scene slot 35, with one slots 31
   and 34 (presumably "all rooms visible" versus "apply the room-to-room table"; low);
5. reads the rest of the message (two lists of 0x110-byte objects, a list of 0x16c-byte objects and
   two lists handled by `0x00606e30` and `0x006072d0`; not traced), creates the sun model `gidy_sun`,
   applies sun or moon lighting by `IsNight` (`ApplySunLighting` `0x006058c0` /
   `ApplyMoonLighting` `0x006059c0`) and sets the module's day phase (`CSWCModule::SetDayPhase`);
   returns 1, or 0 when the message runs short (med for this step's details).

The renderer also has its own LYT reader (`CAurScene::LoadLayout`, slot 27, `0x0044f8d0`:
`roomcount` / `trackcount` sections only, rooms added through slot 28, then `LoadVisibility`) and a
VIS writer (`CAurScene::SaveVisibility`, slot 36, `0x00452b70`, `%s/%s.VIS`), apparently for tools
and the console; the game's area loading goes through `CLayout` (med).

The VIS format as read by `0x004568d0` (high): first every room's visibility is cleared; then each
line `<room> <n>` (read with `%s%d`, indentation ignored) is followed by `n` lines naming the rooms
visible from it, linked with `0x00454940`. Rooms are looked up by name through scene slot 29; when
the parent room is unknown or `n` is 0, its child lines are not consumed and get read as headers.
The function returns 0 only when the file does not exist.

## Saves and the CURRENTGAME / GAMEINPROGRESS folders

- `GAMEINPROGRESS:` holds the state of every module visited in the current game (`<m>.sav` ERFs,
  `REPUTE.fac`, `INVENTORY.res`, `AVAILNPC<n>.utc`, `PC.utc` while an NPC is the player
  character...; [party-items-saves.md](party-items-saves.md) 1.1-1.2). Loading a normal save
  extracts `SAVEGAME.sav` into `FUTUREGAME:` (`0x006c9a90`, `CERFFile::ExtractAll` `0x005dd710`)
  and renames that folder to `GAMEINPROGRESS:` (`0x006caaf0`); loading a transition autosave
  extracts it straight into `GAMEINPROGRESS:` (`LoadTransitionAutoSave` `0x006ca250`). Saving
  (`DoSaveGame` `0x004b3110`, and the transition autosave `WriteTransitionAutoSave` `0x004b8300`)
  writes `savenfo.res` (GFF `"NFO "`, `AREANAME`, `LASTMODULE`, `TIMEPLAYED`, `CHEATUSED`,
  `PORTRAIT*`, hints...; the autosave adds `PCAUTOSAVE`, `SCREENSHOT` and `AUTOSAVEPARAMS`) and
  packs `GAMEINPROGRESS:` into `SAVES:<nnnnnn> - <name>\SAVEGAME.sav` (`CERFFile`, `"MOD V1.0"`);
  only the transition autosave also copies `TEMP:pifo` into the save folder
  ([party-items-saves.md](party-items-saves.md) 1.3-1.7) (high).
- `CURRENTGAME:` holds the working copy of the current module's main file (`<m>.rim`, `.mod`,
  `.sav`...), made by `CopyModuleFile` at the start of every module load and mounted from there.
  `UnloadModule` removes it and `LoadModule` re-creates it (emptying it if it still exists) on
  every module load; `ShutDownServer` (`0x004b7c60`) removes it too (high).

## Open questions

- Paths are resolved by `CExoAliasList::ResolveFileName` (`0x005e68a0` → `0x005eb6b0`: alias
  directory + name + `.` + the type's extension, no case folding); on a case-sensitive file system
  a port needs its own case-insensitive lookup.
- What reads the area byte +0x223 (always 200) and what the scene's visibility slots 31, 34 and 35
  do exactly.
