# Modules and areas in swkotor.exe

How the original engine goes from "load module X" to a playable area: which files it mounts, what
it reads from the IFO, ARE, GIT, LYT, VIS and PTH files, and how the client builds the rooms.
Addresses are for the Steam `swkotor.exe` after SteamStub removal. Names are ours (Aurora/NWN
vocabulary: `CSWSModule`, `CSWSArea` on the server/game side, `CSWCModule`, `CSWCArea` on the
client/presentation side); until `kotor/re/proposals/res.tsv` (and `objects.tsv`, `app.tsv`) are
merged Ghidra shows most of them as `FUN_...`. Confidence: **high** = read in the code;
**med** = behaviour clear, name or detail inferred; **low** = a guess.

Related pages: [resources.md](resources.md) (resource manager, GFF/2DA/TLK readers),
[resman.md](resman.md) (mount order at start-up), [objects.md](objects.md) (the objects a GIT
creates, the module/area class layouts and event handlers), [app.md](app.md) (main loops), and the
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
| 1 | `0x004b95b0` | `CServerExoAppInternal::LoadModule(name, ...)` | creates `CURRENTGAME:` (and empties it when starting over), then finds the module's main file: `GAMEINPROGRESS:<m>` as type 3009 or `.sav` (a module saved in the current game), else `NWMFILES:<m>.nwm`, else `MODULES:<m>.mod`, else `MODULES:<m>.rim`, else `LIVE1..n:MODULES\<m>`. Checks free space in `CURRENTGAME:` against the file size, and stores the module name, the source path and the target `CURRENTGAME:<m>.<ext>` in the module-transition block at `g_pAppManager+0x14` (see [app.md](app.md)), and sets a load mode (3 when the source is a save, else 1) | med |
| 2 | `0x004babb0` | `CServerExoAppInternal::MainLoop` | runs the transition as a small state machine over several ticks, using the transition block's step and area counters: step 0 copies the module file (`CopyModuleFile` `0x004b1680`: `CopyFileA` from the resolved source path to `CURRENTGAME:<m>.<ext>`, clearing read-only; failure = error 5), creates `new CSWSModule(name)` and calls `LoadModuleStart`; the following steps call `LoadModuleInProgress(n)`, and when the counters meet, `LoadModuleFinish` | high |
| 3 | `0x004c84a0` | `CSWSModule::CSWSModule(name, bRequest)` | stores `"CURRENTGAME:" + name` at +0x5c, calls `AddModuleResources`, sets defaults (time 0x53c = year 1340, XP scale 10...), points its IFO helper at resref `MODULE` (`CSWSModule::SetResRef` `0x004c4cc0`, type 2014) | high |
| 4 | `0x004c4150` | `CSWSModule::AddModuleResources(name)` | see [Mounting](#mounting-a-modules-files); runs the resman loader thread while drawing the load-screen progress bar | high |
| 5 | `0x004c9050` | `CSWSModule::LoadModuleStart(name, bResetTime)` | frees spare resman memory (`FreeChunk`), re-mounts if the name changed, demands `module.ifo` and reads it ([IFO](#the-ifo)) | high |
| 6 | `0x004c5720` | `CSWSModule::LoadModuleInProgress(n)` | `new CSWSArea(Area_Name, 0, id)` (`0x0050cf80`; the saved `ObjectId` when loading a save) and `CSWSArea::LoadArea` (`0x0050e190`); on failure releases the IFO and unmounts the module (results 3 / 4) | med |
| 7 | `0x004c5880` | `CSWSModule::LoadModuleFinish` | releases the IFO, marks the module loaded (+0x1d8), tells the client | med |
| 8 | `0x0064bab0` | client: area message handler | shows the load screen (`loadscreens.2da` column `BMPResRef`, row from the message or random), renders a loading frame, then `CSWCArea::LoadArea` (`0x00607610`) and places the player | low (name) / med (behaviour) |
| — | `0x004c44d0` | `CSWSModule::RemoveModuleResources(name)` | the reverse of step 4 and of the loader thread, called by the module destructor (`0x004c68a0`) and on load failures | high |

Only the **first** entry of `Mod_Area_list` is used: a KOTOR module has exactly one area.

## Mounting a module's files

`CSWSModule::AddModuleResources(name)` (`0x004c4150`, high), with `<m>` the name without any
`alias:` prefix:

1. mounts `HD0:players` as an ERF in group 2 (an Xbox file; absent on PC);
2. temporarily mounts the directory `CURRENTGAME:` to test whether `<m>.sav` exists there; if so the
   module comes from a save game (module+0x1c8); unmounts it;
3. mounts `LIPS:<m>_loc` and `LIPS:localization` as ERFs in group 2 (lip-sync archives; the second
   is absent on PC);
4. starts the resman loader thread (`CExoResMan::StartModuleLoad` `0x004064f0`) with (name, is a
   module, from save) and polls its state every 10 ms, advancing the progress bar, until it is done;
   the result bits go to the client.

The loader thread body `CExoResMan::LoadModuleResources` (`0x004094a0`, high) then mounts, recording
each success in the bits at resman+0x5c:

| Order | Source | Kind | Condition | Bit |
|---|---|---|---|---|
| 1 | `RIMS:<m>_a` | RIM | `<m>_a.rim` exists (Xbox area add-on; none on PC) | 0x10 |
| 2 | `RIMS:<m>_adx` | RIM | `<m>_adx.rim` exists | 0x20 |
| 3 | `MODULES:<m>` | ERF group 2 | `<m>.mod` exists in `MODULES:` (a mod or patch) | 0x02 |
| 3' | `MODULES:<m>_s` | RIM | otherwise, if `<m>_s.rim` exists (the module's dialogs, scripts and blueprints) | 0x08 |
| 4 | `CURRENTGAME:<m>` | RIM | not from a save, and `<m>` exists in `CURRENTGAME:` as type 3009 or `.rim` (the copy `CopyModuleFile` made at step 2 of the sequence: the module's IFO, ARE, GIT and other per-area files) | 0x01 |
| 4' | `CURRENTGAME:<m>` | ERF group 2 | from a save: the module's `.sav` | 0x04 |

`MODULES:` and `CURRENTGAME:` are mounted as directories only for the existence tests and unmounted
again. Combined with the lookup order (directories, ERF group 1, RIMs newest first, ERF group 2
newest first, KEY) this gives, for a module on PC without a `.mod`: `Override` > `patch.erf` >
`<m>.rim` (the copy in `CURRENTGAME`) > `<m>_s.rim` > `global.rim` and the other RIMs > lips ERFs >
texture packs > chitin.key. When `<m>.mod` exists, `LoadModule` copies the `.mod` instead of the
`.rim` and the loader mounts `MODULES:<m>.mod` in place of both RIMs; being an ERF of group 2 it
then ranks below every RIM (`global.rim` included) but above the lips and texture-pack ERFs, which
were mounted earlier. A save-game module (`.sav`) takes the same place as a `.mod`, with `<m>_s.rim`
(or the `.mod`) still mounted for the static resources (med: inferred from the code paths, not
observed in a running game).

## The IFO

`LoadModuleStart` reads `module.ifo` (type 2014, GFF `"IFO "`) through `CResIFO` and stores into
`CSWSModule` (high unless marked):

| Field(s) | Stored at | Notes |
|---|---|---|
| `Mod_IsSaveGame`, `Mod_IsNWMFile`, `Mod_NWMResName` | +0x1c8, +0x200, +0x204 | defaults from the mount step |
| `Mod_ID` (up to 32 bytes), `Mod_Creator_ID`, `Mod_Version` | block at +0x54 | |
| `Mod_Name`, `Mod_Description` | +0x64, +0x4c | `CExoLocString` |
| `Mod_StartMovie` | +0x7c | resref |
| `Mod_Tag` | +0x1f8 (set through `0x004c3060`) | |
| `Mod_Entry_Area`, `Mod_Entry_X/Y/Z`, `Mod_Entry_Dir_X/Y` | block at +0x58 (resref, then floats at +0x10..+0x20) | direction defaults to (1, 0) when missing |
| `Mod_MinPerHour`, `Mod_DawnHour`, `Mod_DuskHour` | bytes +0x1a0..+0x1a2 | |
| `Mod_StartYear/Month/Day/Hour`, `Mod_StartMinute/Second/MiliSec`, `Mod_Transition`, `Mod_PauseTime`, `Mod_PauseDay` | +0x1a3..+0x1b8, world timer | read only when `bResetTime`; otherwise the running game time is kept. Defaults 1340 / 6 / 1 / 23 |
| `Mod_XPScale` | byte +0x1a6 | default 10 |
| `Mod_Expan_List` (`Expansion_Name`, `Expansion_ID`) | list at +0x28 | |
| `Mod_CutSceneList` (`CutScene_Name`, `CutScene_ID`) | list at +0x2c | |
| `Mod_OnHeartbeat`, `Mod_OnUsrDefined`, `Mod_OnClientEntr`, `Mod_OnClientLeav`, `Mod_OnActvtItem`, `Mod_OnAcquirItem`, `Mod_OnUnAqreItem`, `Mod_OnModLoad`, `Mod_OnModStart`, `Mod_OnPlrDeath`, `Mod_OnPlrDying`, `Mod_OnSpawnBtnDn`, `Mod_OnPlrRest`, `Mod_OnPlrLvlUp`, `Mod_OnEquipItem` | 15 `CExoString`s from +0xb0 | script resrefs |
| `Mod_Area_list[0].Area_Name` | +0x30 | resref of the one area |
| `Mod_Area_list[0].ObjectId`, `Mod_Effect_NxtId`, `Mod_NextCharId0/1`, `Mod_NextObjId0/1` | +0x40 and the object-id counters | only for a save game |
| `Mod_PlayerList` (`Mod_CommntyName`, `Mod_FirstName`, `Mod_LastName`, `Mod_IsPrimaryPlr`) | list at +0x48 | only for a save game |
| `Mod_Tokens` (`Mod_TokensNumber`, `Mod_TokensValue`) | `CTlkTable::SetCustomToken` | only for a save game |
| `VarTable`, `SWVarTable` | +0x8c, +0x9c (`0x0059aa80`, `0x0059b0f0`) | module locals; only for a save game |

After the IFO it loads the faction table: it mounts `GAMEINPROGRESS:` as a directory for the
duration (`0x005638d0` / `0x00563950`) and, when `REPUTE.fac` exists in a directory source, reads it
as a `CResGFF` of type 2038 / `"FAC "` (`FactionList`, then `RepList`); otherwise it builds the
default factions (`0x0052b490` / `0x0052bce0` / `0x0052b9e0`, presumably from `repute.2da`, med).
Finally it reads the IFO's `CreatureList` (`0x004c8c70`: `ObjectId`, position, orientation) (med).
Not read here: `Mod_Hak`, `Mod_VO_ID`, `Mod_GVar_*` (ignored by this function if present).

`CSWSModule::SaveModuleIFOStart` (`0x004c7050`) and `SaveModuleIFO` (`0x004c8960`, which creates an
`"IFO "` `"V2.0"` GFF and stores it in an ERF written as `"MOD V1.0"`) are the save-game writers of
the same fields (med).

## The area (server side)

`CSWSArea` (0x2d4 bytes; constructor `0x0050cf80(resref, ?, object id)`, destructor `0x0050d370`)
embeds a resource helper for its ARE at +0x100 (`CSWSArea::SetResRef` `0x00506c30`, type 2012,
`CResARE`) and a `CGameObject` at +0x11c (see [objects.md](objects.md)). `CSWSArea::LoadArea(bFromSave)`
(`0x0050e190`, high) demands the ARE, then:

| Step | Address | Name | Reads |
|---|---|---|---|
| a | `0x00508c50` | `LoadAreaHeader(top struct)` | the ARE: `ID`, `Creator_ID`, `Version`, `Comments`, `Expansion_List`, scripts `OnHeartbeat` / `OnUserDefined` / `OnEnter` / `OnExit`, `Name`, `Tag`, `Flags`, `CameraStyle`, `DefaultEnvMap`, `Unescapable`, `RestrictMode`, weather chances and `WindPower`, moon and sun lighting/fog/shadow fields, `DayNightCycle`, `IsNight`, `DynAmbientColor`, `NoRest`, `ShadowOpacity`, `LightingScheme`, `ModSpotCheck`, `ModListenCheck`, `MiniGame` (a struct handed to the minigame code), `LoadScreenID`, the `Grass_*` fields, `AlphaTest`, the `Rooms` list (`RoomName`, `EnvAudio`, `AmbientScale`, `PartSounds` with `Looping`/`ModelPart`/`OmenEvent`/`Sound`), the `Map` struct (`MapResX`, `NorthAxis`, `MapZoom`, `MapPt1/2`, `WorldPt1/2`; the map texture is `lbl_map<area>`), the stealth-XP fields and `TransPending*` |
| b | `0x005073d0` | `LoadLayout` | `<area>.lyt` through a temporary `CLayout`: room count at +0x22c and a room array at +0x230 (`0x00504870`, one server room per LYT room, which later carries the room's walkmesh) |
| c | `0x0050dd80` | `LoadGIT(bFromSave)` | `<area>.git` (type 2023, `"GIT "`): with a save first the area's `VarTable`/`SWVarTable`, `CurrentWeather`, `WeatherStarted`; then `UseTemplates`; then the lists in this order: `Creature List` `0x00504a70`, `List` (items) `0x00504de0`, `Door List` `0x0050a0e0`, `TriggerList` `0x0050a350`, `Encounter List` `0x00505060`, `WaypointList` `0x00505360`, `SoundList` `0x00505560`, `Placeable List` `0x0050a7b0`, `StoreList` `0x005057a0`, `AreaEffectList` `0x00505af0`; then `AreaProperties` `0x00507490` (save state: `Unescapable`, `RestrictMode`, stealth XP, `TransPending*`, `SunFogColor`), `AreaMap` `0x00505da0` (explored-map bitmap: `AreaMapResX/Y`, `AreaMapDataSize`, `AreaMapData`), `CameraList` `0x00505eb0` (`CameraID`, `Position`, `Orientation`, `Height`, `Pitch`, `FieldOfView`, `MicRange`). The per-list loaders and the objects they build are in [objects.md](objects.md#3-building-objects-templates-git-entries-saves) |
| d | `0x00508400` | `LoadPathPoints` | `<area>.pth` (GFF `"PTH "`): `Path_Points` (`X`, `Y`, `Conections`, `First_Conection`) and `Path_Conections` (`Destination`); spelling as in the files |

Then it releases the ARE, registers the area's tag with the module (`0x004c7de0`) and derives a
small size value from the area's extent (+0x223) (med). `LoadArea` ignores the results of the
layout, GIT and path steps: an area without a GIT simply has no objects.

## Layout, rooms and visibility (client side)

**`CLayout`** (0x60 bytes, constructor `0x005de770`; a `CResHelper<CResLYT,3000>` plus arrays) is the
engine's LYT reader, used by both the server (step b above) and the client:

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005df140` | `CLayout::LoadLayout(resref)` | converts the resref and calls `ParseLayout` | high |
| `0x005de900` | `CLayout::ParseLayout(name)` | demands the LYT and copies it to a NUL-terminated buffer; skips lines until `beginlayout`; then up to four sections, each a `<keyword> <count>` line followed by `count` lines `name x y z` (rooms, tracks, obstacles) or `name room hookId x y z qx qy qz qw` (door hooks; count at +0x30, arrays at +0x4c/+0x50), until `donelayout`. The keyword itself is not checked: the sections are taken in the fixed order rooms, tracks, obstacles, door hooks | high |
| `0x005de470` / `0x005de4a0` | `GetRoomName` / `GetRoomPosition` | +0x34 resrefs, +0x40 vectors, count +0x24 (`0x005a4c50`) | high |
| `0x005de4d0` / `0x005de500` | `GetTrackName` / `GetTrackPosition` | +0x38, +0x44, count +0x28 (`0x005d64f0`) | high |
| `0x005de530` / `0x005de560` | `GetObstacleName` / `GetObstaclePosition` | +0x3c, +0x48, count +0x2c | high |
| `0x005de450` | `CLayout::UnloadLayout` | releases the LYT | high |

**`CSWCArea::LoadArea`** (`0x00607610`, med) builds the client area from the server's area message
rather than from the ARE: the area resref (+0x10c), lighting, fog and colour values, the grass
settings (with `grass` row data from a 2DA), the room list with its ambient and env-audio values.
It then:

1. creates the scene `mainscene` (`CAurScene::Create` `0x00458e70`);
2. loads `<area>.lyt` with a `CLayout` and creates one 0x48-byte room object per LYT room (array at
   area+0x260): the room model (named after the room) placed at the LYT position, looping
   `animloop1`..`animloop3` started on it, and per-room sound emitters (`MGB_null` / `sounddummy`
   helper models) for the ARE's `Rooms` sound entries; the load-screen bar advances per room;
3. adds the LYT tracks (swoop-race track pieces) and obstacles to their managers (area+0x264...);
4. asks the scene to load visibility: `CAurScene::LoadVisibility(<area>)` (scene vtable slot 37,
   `0x004568d0`) reads `<area>.vis`. Without a VIS file it calls scene slot 35, with one slots 31
   and 34 (presumably "all rooms visible" versus "apply the room-to-room table"; low).

The renderer also has its own LYT reader (`CAurScene::LoadLayout`, slot 27, `0x0044f8d0`:
`roomcount` / `trackcount` sections only, rooms added through slot 28, then `LoadVisibility`) and a
VIS writer (`0x00452b70`, `%s/%s.VIS`), apparently for tools and the console; the game's area
loading goes through `CLayout` (med).

The VIS format as read by `0x004568d0` (high): first every room's visibility is cleared; then each
line `<room> <n>` (read with `%s%d`, indentation ignored) is followed by `n` lines naming the rooms
visible from it, linked with `0x00454940`. Rooms are looked up by name through scene slot 29; when
the parent room is unknown or `n` is 0, its child lines are not consumed and get read as headers.
The function returns 0 only when the file does not exist.

## Saves and the CURRENTGAME / GAMEINPROGRESS folders

- `GAMEINPROGRESS:` holds the state of every module visited in the current game (`<m>.sav` ERFs,
  `REPUTE.fac`, `INVENTORY`, `PC`, `pifo`...). Loading a save extracts `SAVEGAME.sav` into it
  (`0x006ca250` with `CERFFile::ExtractAll` `0x005dd710`); saving (`0x004b8300`) writes
  `savenfo.res` (GFF `"NFO "`, `AREANAME`, `LASTMODULE`, `TIMEPLAYED`, `CHEATUSED`, `PORTRAIT*`,
  hints, `SCREENSHOT`...), packs `GAMEINPROGRESS:` into `SAVES:<nnnnnn> - <name>\SAVEGAME.sav`
  (`CERFFile`, `"MOD V1.0"`) and copies `pifo` (med).
- `CURRENTGAME:` holds the working copy of the current module's main file (`<m>.rim`, `.mod`,
  `.sav`...), made by `CopyModuleFile` at the start of every module transition and mounted from
  there. It is emptied when a new game starts and removed at shutdown (`0x004b7c60`).

## Open questions

- The second argument of `LoadModule` (`0x004b95b0`) and of the `CSWSModule` constructor (the
  latter is passed on as the IFO helper's request flag) (low).
- Paths are resolved by `CExoAliasList::ResolveFileName` (`0x005e68a0`: alias directory + name +
  `.` + the type's extension, no case folding); on a case-sensitive file system a port needs its
  own case-insensitive lookup.
- How `CSWCModule` itself is created and which message carries the area data to
  `CSWCArea::LoadArea` were not traced in detail (see [app.md](app.md) for the client main loop).
