# GFF schemas: modules and areas (IFO, ARE, GIT, PTH)

A KOTOR module is a pair of RIMs in `modules/`: `<module>.rim` holds exactly `module.ifo` and the
area's `.are` and `.git`; `<module>_s.rim` holds the `.pth`, the blueprints, dialogues, scripts
and, for some modules, `repute.fac` and `module.jrl` (the area's `.lyt`, `.vis`, models and
walkmeshes are in the BIFs). Every KOTOR module has exactly one area (`Mod_Area_list` has one entry), whose resref
is the module name without the planet prefix (module `end_m01aa` -> area `m01aa`). Conventions,
path notation and columns: [gff-schemas.md](gff-schemas.md). Meanings follow BioWare's NWN "IFO"
and "Area File" documents where they apply; KOTOR-only fields are explained from the data and
marked *(inferred)*.

Colours stored as DWORD (`SunFogColor`, `DynAmbientColor`, ...) are `0x00BBGGRR` per BioWare's
doc: the bytes on disk are R, G, B, 0.

## IFO: module information (`module.ifo`)

<!-- gff-table IFO -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Mod_ID` | VOID | all | sizes 16 | 16 bytes generated when the toolset created the module; meaningless to the game. |
| `Mod_Creator_ID` | INT | all | 2 | Deprecated; always 2. |
| `Mod_Version` | DWORD | all | 3 | Always 3. |
| `Mod_VO_ID` | CExoString | all | 19 empty; e.g. `m12aa`, `m01aa`, `m40ad` | Name of the module's voice-over folder under `streamwaves/` (86 of the 98 distinct values exist as folders) *(inferred)*. |
| `Expansion_Pack` | WORD | all | 0 | Required expansion bits; always 0. |
| `Mod_Name` | CExoLocString | all | inline text in 116 (ids 0); 1 empty | Module name (inline text, English). |
| `Mod_Tag` | CExoString | all | 60 empty; e.g. `MODULE`, `ImTraskUlgoensign…`, `I'm Trask Ulgo, e…` | Module tag (some modules carry leftover text here). |
| `Mod_Hak` | CExoString | all | always empty | NWN hak pak; always empty. |
| `Mod_Description` | CExoLocString | all | 117 empty | Always empty. |
| `Mod_IsSaveGame` | BYTE | all | 0 | 0 in a module, 1 in a save. |
| `Mod_Entry_Area` | ResRef | all | e.g. `stunt_endbridge`, `m12aa`, `stunt_levbridge` | Area the player starts in (the only area). |
| `Mod_Entry_X` | FLOAT | all | -86.8195..427.966 | Start position x when entering the module without a named waypoint. |
| `Mod_Entry_Y` | FLOAT | all | -193.002..388.458 | Start position y. |
| `Mod_Entry_Z` | FLOAT | all | -3.38657..85.8748 | Start position z. |
| `Mod_Entry_Dir_X` | FLOAT | all | -1..1 (29 values) | Start facing: x of a unit direction vector (cos of the bearing). |
| `Mod_Entry_Dir_Y` | FLOAT | all | -1..1 (26 values) | Start facing: y of the direction vector (sin of the bearing). |
| `Mod_Expan_List` | List | all | 0 entries | Deprecated; always empty. |
| `Mod_DawnHour` | BYTE | all | 0, 6 | Hour dawn begins. |
| `Mod_DuskHour` | BYTE | all | 0, 18 | Hour dusk begins. |
| `Mod_MinPerHour` | BYTE | all | 0, 1, 2 | Real minutes per game hour (0 in some modules). |
| `Mod_StartMonth` | BYTE | all | 6 | Starting month of the game calendar. |
| `Mod_StartDay` | BYTE | all | 1 | Starting day. |
| `Mod_StartHour` | BYTE | all | 13 | Starting hour. |
| `Mod_StartYear` | DWORD | all | 0, 1372 | Starting year. |
| `Mod_XPScale` | BYTE | all | 10 | Percentage applied to kill XP; always 10. |
| `Mod_OnHeartbeat` | ResRef | all | 115 empty; e.g. `k_pebo_mgheart`, `k_ptat17af_heart` | Module OnHeartbeat script. |
| `Mod_OnModLoad` | ResRef | all | 104 empty; e.g. `k_pebn_pophawk`, `k_pebo_mgload`, `k_pdan_13_load` | OnModuleLoad script. |
| `Mod_OnModStart` | ResRef | all | always empty | OnModuleStart script; always empty. |
| `Mod_OnClientEntr` | ResRef | all | 110 empty; e.g. `k_pebo_skybox`, `stunt12_enter`, `stunt14_enter` | OnClientEnter script (the player entered the module). |
| `Mod_OnClientLeav` | ResRef | all | 116 empty; e.g. `k_pebn_hawkgo` | OnClientLeave script. |
| `Mod_OnActvtItem` | ResRef | all | 115 empty; e.g. `k_pend_activate`, `k_ptar_m02ad_aci` | OnActivateItem script. |
| `Mod_OnAcquirItem` | ResRef | all | 106 empty; e.g. `k_pdan_itemacq`, `k_pdan_14b_itmaq`, `k_pebn_acquire` | OnAcquireItem script. |
| `Mod_OnUsrDefined` | ResRef | all | always empty | OnUserDefined script; always empty. |
| `Mod_OnUnAqreItem` | ResRef | all | always empty | OnUnacquireItem script; always empty. |
| `Mod_OnPlrDeath` | ResRef | all | 52 empty; e.g. `nw_o0_death`, `k_dan_death`, `k_pkor_pcdeath` | OnPlayerDeath script (`nw_o0_death` in many modules: an NWN script that does not exist in KOTOR). |
| `Mod_OnPlrDying` | ResRef | all | 54 empty; e.g. `nw_o0_dying` | OnPlayerDying script (`nw_o0_dying`, also absent). |
| `Mod_OnPlrLvlUp` | ResRef | all | always empty | OnPlayerLevelUp script; always empty. |
| `Mod_OnSpawnBtnDn` | ResRef | all | 54 empty; e.g. `nw_o0_respawn` | OnPlayerRespawn script (`nw_o0_respawn`, absent). |
| `Mod_OnPlrRest` | ResRef | all | always empty | OnPlayerRest script; always empty. |
| `Mod_StartMovie` | ResRef | all | always empty | Movie to play on start; always empty. |
| `Mod_CutSceneList` | List | all | 0 entries | Deprecated; always empty. |
| `Mod_GVar_List` | List | all | 0 entries | Deprecated; always empty. |
| `Mod_Area_list` | List | all | 1 entries; struct id 6 | The module's areas: one entry in KOTOR (struct id 6). |
| `Mod_Area_list/Area_Name` | ResRef | all | e.g. `stunt_endbridge`, `m12aa`, `stunt_levbridge` | Area resref (the ARE/GIT name). |
<!-- /gff-table -->

## ARE: static area properties

The room list names the same set of room models as the area's LYT file (checked: all 117 areas;
the order matches in only 56, so match rooms by name), and gives each its environmental audio and
ambient-sound scale. `Map` places the area map image
`lbl_map<area>` (a 512x256 TPC, present for 95 of the 117 areas): `MapPt1`/`MapPt2` are normalised
image coordinates of the world points `WorldPt1`/`WorldPt2`, which defines the linear world-to-map
mapping, and `NorthAxis` says which world direction is up on the map *(inferred: 0 +Y, 1 -Y,
2 +X, 3 -X)*. `MiniGame` is present only in the four minigame areas: `m03mg`, `m17mg`, `m26mg`
(swoop races, `Type` 1) and `m12ab` (the Ebon Hawk turret, `Type` 2).

<!-- gff-table ARE -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `ID` | INT | all | 0, 1163018542 | Leftover id; 0 or a constant. |
| `Creator_ID` | INT | all | 0, 256 | Deprecated. |
| `Version` | DWORD | all | 8..16296 | Toolset save count. |
| `Tag` | CExoString | all | e.g. `Untitled`, `Area001`, `m40ad` | Area tag. |
| `Name` | CExoLocString | all | strref in 117 | Area name (strref), shown on the map and load screens. |
| `Comments` | CExoString | all | 116 empty; e.g. `Global Booleans  …` | Designer comment. |
| `Map` | Struct | all | struct id 0, 14 | Area-map placement (see above). |
| `Map.MapResX` | INT | all | 0..50 (14 values) | Map resolution setting from the toolset *(inferred; use not established)*. |
| `Map.NorthAxis` | INT | all | 0, 1, 2, 3 | Which world axis points up on the map *(inferred)*. |
| `Map.WorldPt1X` | FLOAT | all | -64.8..340.3 | World x of reference point 1. |
| `Map.WorldPt1Y` | FLOAT | all | -83..434.9 | World y of reference point 1. |
| `Map.WorldPt2X` | FLOAT | all | -7.9..562.7 | World x of reference point 2. |
| `Map.WorldPt2Y` | FLOAT | all | -201..376.3 | World y of reference point 2. |
| `Map.MapPt1X` | FLOAT | all | 0..0.8955 | Map-image x (0..1) of reference point 1. |
| `Map.MapPt1Y` | FLOAT | all | 0..0.9889 | Map-image y (0..1) of reference point 1. |
| `Map.MapPt2X` | FLOAT | all | 0..0.9432 | Map-image x (0..1) of reference point 2. |
| `Map.MapPt2Y` | FLOAT | all | 0..0.9667 | Map-image y (0..1) of reference point 2. |
| `Map.MapZoom` | INT | all | 1 | Always 1. |
| `Expansion_List` | List | all | 0 entries | Deprecated; always empty. |
| `Flags` | DWORD | all | 0..7 (7 values) | Bits: 0x1 interior, 0x2 underground, 0x4 natural (BioWare); KOTOR's use unverified. |
| `ModSpotCheck` | INT | all | 0 | Modifier to Spot checks; always 0. |
| `ModListenCheck` | INT | all | 0 | Modifier to Listen checks; always 0. |
| `AlphaTest` | FLOAT | all | 0, 0.2 | Alpha-test threshold for the area's textures *(inferred)*. |
| `CameraStyle` | INT | all | 0, 1 | Row in `camerastyle.2da` (0 default, 1 Ebon Hawk interior): follow-camera distance, pitch, height. |
| `DefaultEnvMap` | ResRef | all | 114 empty; e.g. `cm_unwsand`, `cm_unwgrass` | Environment map for room materials that ask for the default one *(inferred)*. |
| `Grass_TexName` | ResRef | all | 100 empty; e.g. `lda_grass2`, `lun_pgrss01`, `lma_grass` | Grass texture; grass grows on walkmesh faces whose surface material is grass. |
| `Grass_Density` | FLOAT | all | 0, 1.4, 3, 4, 5, 7 | Grass blades per square metre *(inferred)*. |
| `Grass_QuadSize` | FLOAT | all | 0, 0.7, 0.75, 0.8, 1 | Size of one grass quad (m) *(inferred)*. |
| `Grass_Ambient` | DWORD | all | 0 | Grass ambient colour; always 0. |
| `Grass_Diffuse` | DWORD | all | 0 | Grass diffuse colour; always 0. |
| `Grass_Prob_LL` | FLOAT | all | 0.02, 0.25 | Probability of the texture's lower-left quarter for a grass quad *(inferred: the four probabilities choose among four sub-images)*. |
| `Grass_Prob_LR` | FLOAT | all | 0.25, 0.45 | Probability of the lower-right quarter *(inferred)*. |
| `Grass_Prob_UL` | FLOAT | all | 0.08, 0.25 | Probability of the upper-left quarter *(inferred)*. |
| `Grass_Prob_UR` | FLOAT | all | 0.25, 0.45 | Probability of the upper-right quarter *(inferred)*. |
| `MoonAmbientColor` | DWORD | all | 0 | Night ambient colour; unused (no area is night). |
| `MoonDiffuseColor` | DWORD | all | 0 | Night diffuse colour; unused. |
| `MoonFogOn` | BYTE | all | 0, 1 | Night fog on. |
| `MoonFogNear` | FLOAT | all | 0, 99 | Night fog start distance. |
| `MoonFogFar` | FLOAT | all | 0.1, 35, 100 | Night fog end distance. |
| `MoonFogColor` | DWORD | all | 0, 1510925 | Night fog colour. |
| `MoonShadows` | BYTE | all | 0 | Night shadows; always 0. |
| `SunAmbientColor` | DWORD | all | 0, 334367 | Day ambient light colour. |
| `SunDiffuseColor` | DWORD | all | 0 | Day diffuse light colour; always 0. |
| `SunFogOn` | BYTE | all | 0, 1 | 1 if distance fog is on. |
| `SunFogNear` | FLOAT | all | 0..1000 (11 values) | Fog start distance (m). |
| `SunFogFar` | FLOAT | all | 0.1..4000 (35 values) | Fog end distance (m). |
| `SunFogColor` | DWORD | all | 0..16570309 (40 values) | Fog colour (0x00BBGGRR). |
| `SunShadows` | BYTE | all | 0 | Day shadows; always 0. |
| `DynAmbientColor` | DWORD | all | 0..15180637 | Ambient colour applied to dynamic objects (creatures, placeables) *(inferred)*. |
| `IsNight` | BYTE | all | 0 | 1 if always night; always 0. |
| `LightingScheme` | BYTE | all | 0 | Toolset lighting preset; always 0. |
| `ShadowOpacity` | BYTE | all | 50, 205 | Opacity of creature shadows. |
| `DayNightCycle` | BYTE | all | 0, 1 | 1 if day and night alternate. |
| `ChanceRain` | INT | all | 0 | Percent chance of rain; always 0. |
| `ChanceSnow` | INT | all | 0 | Percent chance of snow; always 0. |
| `ChanceLightning` | INT | all | 0 | Percent chance of lightning; always 0. |
| `WindPower` | INT | all | 0, 1, 2 | Wind strength 0 none, 1 weak, 2 strong (grass and dangly meshes) *(inferred for KOTOR)*. |
| `LoadScreenID` | WORD | all | 0 | Row in `loadscreens.2da`; always 0 (the load screen comes from elsewhere). |
| `PlayerVsPlayer` | BYTE | all | 0, 3 | NWN PvP setting; ignored. |
| `NoRest` | BYTE | all | 0 | 1 if resting is not allowed; always 0. |
| `NoHangBack` | BYTE | all | 0 | Always 0 *(KOTOR; presumably forbids leaving party members behind)*. |
| `PlayerOnly` | BYTE | all | 0 | Always 0 *(KOTOR; presumably solo-mode area)*. |
| `Unescapable` | BYTE | all | 0, 1 | 1 if the party cannot leave the area (no travel to the Ebon Hawk). |
| `StealthXPEnabled` | BYTE | all | 0, 1 | 1 if the area awards stealth XP. |
| `StealthXPLoss` | DWORD | all | 0..1250 (8 values) | Stealth XP lost when the party is detected *(inferred)*. |
| `StealthXPMax` | DWORD | all | 0..5000 (9 values) | Maximum stealth XP the area awards *(inferred)*. |
| `Rooms` | List | all | 1..53 entries; struct id 0 | The area's rooms (struct id 0). |
| `Rooms/RoomName` | CExoString | all | e.g. `****`, `m12aa_01o`, `m40ad_25a` | Room model (MDL) resref, as in the LYT; `****` in 15 placeholder rows. |
| `Rooms/EnvAudio` | INT | all | 0..88 (26 values) | EAX environment for sounds in this room: row of `soundeax.2da` (0..23); values above 23 occur and their meaning is unknown. |
| `Rooms/AmbientScale` | FLOAT | all | 0..1 (37 values) | Scale of the area ambient sound in this room (0..1). |
| `Rooms/PartSounds` | List | 1 | 4..5 entries; struct id 0 | Sounds attached to model parts (one area, swoop track) *(inferred)*. |
| `Rooms/PartSounds/ModelPart` | CExoString | 1 | e.g. `SWBk_Main02`, `SWBk_Main01`, `SWBk_Main03` | Node name in the room model. |
| `Rooms/PartSounds/OmenEvent` | CExoString | 1 | e.g. `Omenevent01`, `Omenevent02` | Animation event name that triggers the sound *(inferred)*. |
| `Rooms/PartSounds/Sound` | ResRef | 1 | e.g. `al_me_swoopbike` | WAV resref. |
| `Rooms/PartSounds/Looping` | BYTE | 1 | 1 | 1 if the sound loops. |
| `OnEnter` | ResRef | all | 20 empty; e.g. `k_scene_start`, `k_psta_areaenter`, `k_pebo_skybox` | OnEnter script (a creature entered the area). |
| `OnExit` | ResRef | all | 108 empty; e.g. `k_pdan_13_exit`, `k_pdan_14b_exit`, `k_pman_27_areae` | OnExit script. |
| `OnHeartbeat` | ResRef | all | 104 empty; e.g. `k_endgame`, `k_pkas23ab_enter`, `k_plev_40ac_hb` | OnHeartbeat script. |
| `OnUserDefined` | ResRef | all | 108 empty; e.g. `k_pdan_14b_aread`, `k_pdan_14c_area2`, `k_pdan_16_aread` | OnUserDefined script. |
| `MiniGame` | Struct | 4 | struct id 0 | Minigame setup (swoop race or turret); see above. |
| `MiniGame.Type` | DWORD | 4 | 1, 2 | 1 swoop race, 2 turret shooter. |
| `MiniGame.Near_Clip` | FLOAT | 4 | 0.1 | Camera near clip distance. |
| `MiniGame.Far_Clip` | FLOAT | 4 | 2000, 40000 | Camera far clip distance. |
| `MiniGame.CameraViewAngle` | FLOAT | 4 | 65 | Camera field of view (degrees). |
| `MiniGame.Bump_Plane` | DWORD | 4 | 3 | Collision plane setting *(inferred)*. |
| `MiniGame.UseInertia` | BYTE | 4 | 0, 1 | 1 if the player vehicle has inertia. |
| `MiniGame.DoBumping` | BYTE | 4 | 0 | Always 0. |
| `MiniGame.DOF` | DWORD | 4 | 1, 5 | Degrees-of-freedom mode of the player *(inferred)*. |
| `MiniGame.MovementPerSec` | FLOAT | 4 | 100 | Lateral movement speed. |
| `MiniGame.LateralAccel` | FLOAT | 4 | 300, 1200 | Lateral acceleration. |
| `MiniGame.Music` | ResRef | 4 | 2 empty; e.g. `mus_bat_sithbs`, ` ` | Music track (`streammusic/`); a single space when none. |
| `MiniGame.Mouse` | Struct | 1 | struct id 0 | Mouse axis mapping (turret). |
| `MiniGame.Mouse.AxisX` | DWORD | 1 | 3 | Axis driven by mouse x. |
| `MiniGame.Mouse.AxisY` | DWORD | 1 | 1 | Axis driven by mouse y. |
| `MiniGame.Mouse.FlipAxisX` | BYTE | 1 | 0 | Invert mouse x. |
| `MiniGame.Mouse.FlipAxisY` | BYTE | 1 | 0 | Invert mouse y. |
| `MiniGame.Player` | Struct | 4 | struct id 0 | The player's vehicle or turret. |
| `MiniGame.Player.Track` | ResRef | 4 | e.g. `m12ab_mgt01`, `m26mg_mgt01`, `m03mg_tr01` | Model whose animation is the path the object follows. |
| `MiniGame.Player.Num_Loops` | INT | 4 | -1, 1 | Times to run the track; -1 forever. |
| `MiniGame.Player.Sphere_Radius` | FLOAT | 4 | 3, 40 | Collision sphere radius. |
| `MiniGame.Player.Invince_Period` | FLOAT | 4 | 0, 0.3 | Seconds of invulnerability after a hit. |
| `MiniGame.Player.Hit_Points` | DWORD | 4 | 999, 3000, 9999 | Hit points. |
| `MiniGame.Player.Max_HPs` | DWORD | 4 | 999, 3000, 9999 | Maximum hit points. |
| `MiniGame.Player.Bump_Damage` | INT | 4 | 0 | Damage taken from bumping; always 0. |
| `MiniGame.Player.Sounds` | Struct | 4 | struct id 0 | Sound hooks. |
| `MiniGame.Player.Sounds.Death` | ResRef | 4 | always empty | Death sound; empty. |
| `MiniGame.Player.Sounds.Engine` | ResRef | 4 | always empty | Engine sound; empty. |
| `MiniGame.Player.Models` | List | 4 | 4..5 entries; struct id 0 | Models making up the object. |
| `MiniGame.Player.Models/Model` | ResRef | 4 | e.g. `v_superbike`, `m17mg_camera`, `lmg_distort` | MDL resref. |
| `MiniGame.Player.Models/RotatingModel` | BYTE | 4 | 0, 1 | 1 if this model turns with the aim. |
| `MiniGame.Player.Scripts` | Struct | 4 | struct id 0 | Script hooks (run with the minigame object as caller). |
| `MiniGame.Player.Scripts.OnCreate` | ResRef | 4 | 1 empty; e.g. `oncreate` | Run when created. |
| `MiniGame.Player.Scripts.OnHeartbeat` | ResRef | 4 | e.g. `heartbeat`, `k_heartbeat` | Run every heartbeat. |
| `MiniGame.Player.Scripts.OnDamage` | ResRef | 4 | 3 empty; e.g. `k_pebo_hawkhit` | Run when damaged. |
| `MiniGame.Player.Scripts.OnDeath` | ResRef | 4 | always empty | Run on death. |
| `MiniGame.Player.Scripts.OnFire` | ResRef | 4 | 1 empty; e.g. `onfire` | Run when firing. |
| `MiniGame.Player.Scripts.OnHitBullet` | ResRef | 4 | always empty | Run when hit by a bullet. |
| `MiniGame.Player.Scripts.OnHitFollower` | ResRef | 4 | 1 empty; e.g. `accelpad` | Run when touching a follower (enemy/pad). |
| `MiniGame.Player.Scripts.OnHitObstacle` | ResRef | 4 | 1 empty; e.g. `obstacle` | Run when hitting an obstacle. |
| `MiniGame.Player.Scripts.OnTrackLoop` | ResRef | 4 | always empty | Run at the end of each track loop. |
| `MiniGame.Player.Scripts.OnAnimEvent` | ResRef | 4 | always empty | Run on model animation events. |
| `MiniGame.Player.Camera` | ResRef | 4 | 3 empty; e.g. `m12ab_camera` | Camera model (turret); empty for swoops. |
| `MiniGame.Player.CameraRotate` | BYTE | 4 | 0, 1 | 1 if the camera turns with the player. |
| `MiniGame.Player.Minimum_Speed` | FLOAT | 4 | 0 | Minimum speed; 0. |
| `MiniGame.Player.Maximum_Speed` | FLOAT | 4 | 0 | Maximum speed; 0. |
| `MiniGame.Player.Accel_Secs` | FLOAT | 4 | 0.01, 25 | Seconds to reach full speed. |
| `MiniGame.Player.Start_Offset_X` | FLOAT | 4 | 0, 7 | Start offset from the track. |
| `MiniGame.Player.Start_Offset_Y` | FLOAT | 4 | 0 | Start offset y. |
| `MiniGame.Player.Start_Offset_Z` | FLOAT | 4 | 0 | Start offset z. |
| `MiniGame.Player.TunnelInfinite` | Vector | 4 | ('0', '0', '0'); ('0', '0', '1') | Per axis, 1 if movement is unbounded *(inferred)*. |
| `MiniGame.Player.TunnelXPos` | FLOAT | 4 | 0, 45 | Movement bound +x around the track. |
| `MiniGame.Player.TunnelYPos` | FLOAT | 4 | 0 | Bound +y. |
| `MiniGame.Player.TunnelZPos` | FLOAT | 4 | 0, 9999 | Bound +z. |
| `MiniGame.Player.TunnelXNeg` | FLOAT | 4 | 0, 2 | Bound -x. |
| `MiniGame.Player.TunnelYNeg` | FLOAT | 4 | 0 | Bound -y. |
| `MiniGame.Player.TunnelZNeg` | FLOAT | 4 | -9999, 0 | Bound -z. |
| `MiniGame.Player.Target_Offset_X` | FLOAT | 4 | 0 | Aim target offset. |
| `MiniGame.Player.Target_Offset_Y` | FLOAT | 4 | 0 | Aim target offset y. |
| `MiniGame.Player.Target_Offset_Z` | FLOAT | 4 | -5, 0 | Aim target offset z. |
| `MiniGame.Player.Gun_Banks` | List | 4 | 1..2 entries; struct id 0 | Weapons. |
| `MiniGame.Player.Gun_Banks/BankID` | DWORD | 4 | 0, 1 | Bank number. |
| `MiniGame.Player.Gun_Banks/Gun_Model` | ResRef | 4 | e.g. `mgg_null`, `mgg_turret` | Gun model. |
| `MiniGame.Player.Gun_Banks/Fire_Sound` | ResRef | 4 | 4 empty; e.g. `mgs_ebon_fire` | Firing sound. |
| `MiniGame.Player.Gun_Banks/Bullet` | Struct | 4 | struct id 0 | Projectile. |
| `MiniGame.Player.Gun_Banks/Bullet.Damage` | DWORD | 4 | 0, 30 | Damage per hit. |
| `MiniGame.Player.Gun_Banks/Bullet.Lifespan` | FLOAT | 4 | 0.01, 3 | Seconds the bullet lives. |
| `MiniGame.Player.Gun_Banks/Bullet.Bullet_Model` | ResRef | 4 | e.g. `mgb_ebonleft`, `mgb_null`, `mgg_null` | Bullet model. |
| `MiniGame.Player.Gun_Banks/Bullet.Rate_Of_Fire` | FLOAT | 4 | 0, 0.01, 0.3 | Seconds between shots *(inferred)*. |
| `MiniGame.Player.Gun_Banks/Bullet.Collision_Sound` | ResRef | 4 | 3 empty; e.g. `mgs_sith_hit` | Impact sound. |
| `MiniGame.Player.Gun_Banks/Bullet.Speed` | FLOAT | 4 | 0, 300 | Bullet speed. |
| `MiniGame.Player.Gun_Banks/Bullet.Target_Type` | DWORD | 4 | 1, 2, 3 | Which objects it can hit *(inferred)*. |
| `MiniGame.Enemies` | List | 4 | 6..30 entries; struct id 0 | Enemies and track objects (followers). |
| `MiniGame.Enemies/Track` | ResRef | 4 | e.g. `m12ab_mgt02`, `m12ab_mgt03`, `m12ab_mgt04` | Path model. |
| `MiniGame.Enemies/Num_Loops` | INT | 4 | -1 | Track loops; -1 forever. |
| `MiniGame.Enemies/Sphere_Radius` | FLOAT | 4 | 2, 3, 20 | Collision radius. |
| `MiniGame.Enemies/Invince_Period` | FLOAT | 4 | 0 | Invulnerability after a hit. |
| `MiniGame.Enemies/Hit_Points` | DWORD | 4 | 1, 80, 100 | Hit points. |
| `MiniGame.Enemies/Max_HPs` | DWORD | 4 | 1, 80, 100 | Maximum hit points. |
| `MiniGame.Enemies/Bump_Damage` | INT | 4 | 0 | Bump damage; 0. |
| `MiniGame.Enemies/Sounds` | Struct | 4 | struct id 0 | Sound hooks. |
| `MiniGame.Enemies/Sounds.Death` | ResRef | 4 | e.g. `mgs_accelpad`, `mgs_sith_expl` | Death sound. |
| `MiniGame.Enemies/Sounds.Engine` | ResRef | 4 | always empty | Engine sound; empty. |
| `MiniGame.Enemies/Models` | List | 4 | 1 entries; struct id 0 | Models. |
| `MiniGame.Enemies/Models/Model` | ResRef | 4 | e.g. `mgf_accelpad01`, `mgf_sithfighter` | MDL resref (accelerator pads, Sith fighters). |
| `MiniGame.Enemies/Models/RotatingModel` | BYTE | 4 | 1 | 1 if the model turns to aim. |
| `MiniGame.Enemies/Scripts` | Struct | 4 | struct id 0 | Script hooks, as for the player. |
| `MiniGame.Enemies/Scripts.OnCreate` | ResRef | 4 | 89 empty; e.g. `k_pebo_sthcreate` | Run when created. |
| `MiniGame.Enemies/Scripts.OnHeartbeat` | ResRef | 4 | always empty | Run every heartbeat. |
| `MiniGame.Enemies/Scripts.OnDamage` | ResRef | 4 | always empty | Run when damaged. |
| `MiniGame.Enemies/Scripts.OnDeath` | ResRef | 4 | 89 empty; e.g. `k_pebo_sthdeath2`, `k_pebo_sthdeath3`, `k_pebo_sthdeath4` | Run on death. |
| `MiniGame.Enemies/Scripts.OnFire` | ResRef | 4 | always empty | Run when firing. |
| `MiniGame.Enemies/Scripts.OnHitBullet` | ResRef | 4 | always empty | Run when hit by a bullet. |
| `MiniGame.Enemies/Scripts.OnHitFollower` | ResRef | 4 | always empty | Run when touching another follower. |
| `MiniGame.Enemies/Scripts.OnHitObstacle` | ResRef | 4 | always empty | Run when hitting an obstacle. |
| `MiniGame.Enemies/Scripts.OnTrackLoop` | ResRef | 4 | always empty | Run at each track loop. |
| `MiniGame.Enemies/Scripts.OnAnimEvent` | ResRef | 4 | always empty | Run on animation events. |
| `MiniGame.Enemies/Trigger` | BYTE | 4 | 0, 1 | 1 if it is a trigger object (pad) rather than an enemy *(inferred)*. |
| `MiniGame.Enemies/Gun_Banks` | List | 4 | 0..1 entries; struct id 0 | Weapons. |
| `MiniGame.Enemies/Gun_Banks/BankID` | DWORD | 1 | 0 | Bank number. |
| `MiniGame.Enemies/Gun_Banks/Gun_Model` | ResRef | 1 | e.g. `mgg_null` | Gun model. |
| `MiniGame.Enemies/Gun_Banks/Fire_Sound` | ResRef | 1 | e.g. `mgs_sith_fire` | Firing sound. |
| `MiniGame.Enemies/Gun_Banks/Bullet` | Struct | 1 | struct id 0 | Projectile. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Damage` | DWORD | 1 | 10 | Damage per hit. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Lifespan` | FLOAT | 1 | 2 | Seconds the bullet lives. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Bullet_Model` | ResRef | 1 | e.g. `mgb_sithfighter` | Bullet model. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Rate_Of_Fire` | FLOAT | 1 | 0.4 | Seconds between shots *(inferred)*. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Collision_Sound` | ResRef | 1 | e.g. `mgs_ebon_hit` | Impact sound. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Speed` | FLOAT | 1 | 200 | Bullet speed. |
| `MiniGame.Enemies/Gun_Banks/Bullet.Target_Type` | DWORD | 1 | 1 | Which objects it can hit *(inferred)*. |
| `MiniGame.Enemies/Gun_Banks/Inaccuracy` | FLOAT | 1 | 0.01 | Aim error. |
| `MiniGame.Enemies/Gun_Banks/Sensing_Radius` | FLOAT | 1 | 200 | Distance at which it starts firing. |
| `MiniGame.Enemies/Gun_Banks/Horiz_Spread` | FLOAT | 1 | 70 | Horizontal firing arc (degrees). |
| `MiniGame.Enemies/Gun_Banks/Vert_Spread` | FLOAT | 1 | 70 | Vertical firing arc (degrees). |
| `MiniGame.Obstacles` | List | 4 | 1..22 entries; struct id 0 | Static obstacles. |
| `MiniGame.Obstacles/Name` | ResRef | 4 | e.g. `m12ab_mgo01`, `m26mg_mgo01`, `m26mg_mgo02` | Obstacle model. |
| `MiniGame.Obstacles/Scripts` | Struct | 4 | struct id 0 | Script hooks; all empty. |
| `MiniGame.Obstacles/Scripts.OnAnimEvent` | ResRef | 4 | always empty | Run on animation events. |
| `MiniGame.Obstacles/Scripts.OnCreate` | ResRef | 4 | always empty | Run when created. |
| `MiniGame.Obstacles/Scripts.OnHeartbeat` | ResRef | 4 | always empty | Run every heartbeat. |
| `MiniGame.Obstacles/Scripts.OnHitFollower` | ResRef | 4 | always empty | Run when a follower hits it. |
| `MiniGame.Obstacles/Scripts.OnHitBullet` | ResRef | 4 | always empty | Run when a bullet hits it. |
<!-- /gff-table -->

## GIT: area instances

Each list holds the instances of one object type; the struct ids are BioWare's (creature 4,
door 8, encounter 7, item 0, placeable 9, sound 6, store 11, trigger 1, waypoint 5), plus
KOTOR's camera list (14). With `UseTemplates` = 1, instances carry only position, orientation,
`TemplateResRef` and the few per-instance overrides listed here; everything else comes from the
blueprint. Creatures, waypoints, stores and items face along the unit vector
(`XOrientation`, `YOrientation`); doors and placeables use `Bearing`, radians counter-clockwise
from +Y per BioWare (the GIT values are -pi..pi). Trigger and encounter geometry points are
relative to the object's position. Camera `Orientation` is a quaternion stored w, x, y, z (the
data has x = y = 0 and (w, z) a rotation about the vertical axis).

<!-- gff-table GIT -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `UseTemplates` | BYTE | all | 1 | 1: instances are filled from their blueprints. |
| `AreaProperties` | Struct | all | struct id 14, 100 | Area properties a script can change (struct id 100). |
| `AreaProperties.AmbientSndDay` | INT | all | 0..46 (37 values) | Row in `ambientsound.2da` for the daytime ambient loop. |
| `AreaProperties.AmbientSndNight` | INT | all | 0..46 (37 values) | Row in `ambientsound.2da` at night. |
| `AreaProperties.AmbientSndDayVol` | INT | all | 0..127 | Day ambient volume (0..127). |
| `AreaProperties.AmbientSndNitVol` | INT | all | 0..127 | Night ambient volume (0..127). |
| `AreaProperties.EnvAudio` | INT | all | 0..92 (24 values) | EAX environment for the area: row of `soundeax.2da` (0..23); values 54..92 also occur (meaning unknown). |
| `AreaProperties.MusicBattle` | INT | all | 0..47 (17 values) | Row in `ambientmusic.2da` for combat music. |
| `AreaProperties.MusicDay` | INT | all | 0..43 (31 values) | Row in `ambientmusic.2da` for daytime music. |
| `AreaProperties.MusicNight` | INT | all | 0..43 (31 values) | Row in `ambientmusic.2da` for night music. |
| `AreaProperties.MusicDelay` | INT | all | 0, 5000, 20000, 30000, 60000, 120000 | Milliseconds of silence between music repeats *(inferred)*. |
| `Creature List` | List | all | 0..51 entries; struct id 4 | Creature instances (struct id 4). |
| `Creature List/XPosition` | FLOAT | 104 | -102.265..556.117 | Position x. |
| `Creature List/YPosition` | FLOAT | 104 | -222.14..437.954 | Position y. |
| `Creature List/ZPosition` | FLOAT | 104 | -1.27503..92.6901 | Position z. |
| `Creature List/XOrientation` | FLOAT | 104 | -1..1 | Facing vector x. |
| `Creature List/YOrientation` | FLOAT | 104 | -1..1 | Facing vector y. |
| `Creature List/TemplateResRef` | ResRef | 104 | e.g. `g_sithcomm002`, `g_sithcomm003`, `n_darthmalak001` | UTC blueprint. |
| `Door List` | List | all | 0..46 entries; struct id 8 | Door instances (struct id 8). |
| `Door List/TemplateResRef` | ResRef | 88 | e.g. `sw_door_hhead1`, `dan16_door002`, `dan16_door01` | UTD blueprint. |
| `Door List/Tag` | CExoString | 88 | e.g. `dan16_door01`, `dan13_door01`, `Hammerhead 1` | Instance tag (overrides the blueprint's). |
| `Door List/LinkedToModule` | ResRef | 88 | 608 empty; e.g. `korr_m36aa`, `kas_m23aa`, `manm26ac` | Destination module of the door's transition. |
| `Door List/LinkedTo` | CExoString | 88 | 610 empty; e.g. `from26c`, `from14a`, `from13` | Tag of the destination waypoint/door in that module. |
| `Door List/LinkedToFlags` | BYTE | 88 | 0, 1, 2 | 0 none, 1 door, 2 waypoint. |
| `Door List/TransitionDestin` | CExoLocString | 88 | strref in 112; 612 empty | Destination name shown on the transition (strref). |
| `Door List/X` | FLOAT | 88 | -112.37..471.461 | Position x. |
| `Door List/Y` | FLOAT | 88 | -201.108..401.804 | Position y. |
| `Door List/Z` | FLOAT | 88 | -5.18935..92.6546 | Position z. |
| `Door List/Bearing` | FLOAT | 88 | -3.14159..3.14156 | Facing, radians. |
| `Encounter List` | List | all | 0..7 entries; struct id 7 | Encounter instances (struct id 7). |
| `Encounter List/TemplateResRef` | ResRef | 23 | e.g. `g_blckvulgrou001`, `vulkarencounter`, `g_messenger001` | UTE blueprint. |
| `Encounter List/XPosition` | FLOAT | 23 | -17.5217..498.75 | Position x. |
| `Encounter List/YPosition` | FLOAT | 23 | -197.388..224.884 | Position y. |
| `Encounter List/ZPosition` | FLOAT | 23 | 0..64.3911 (30 values) | Position z. |
| `Encounter List/Geometry` | List | 23 | 4..8 entries; struct id 1 | Polygon vertices, relative to the position (struct id 1). |
| `Encounter List/Geometry/X` | FLOAT | 23 | -14.0624..88.3596 | Vertex x. |
| `Encounter List/Geometry/Y` | FLOAT | 23 | -61.9328..96.8062 | Vertex y. |
| `Encounter List/Geometry/Z` | FLOAT | 23 | -0.834425..61.945 | Vertex z. |
| `Encounter List/SpawnPointList` | List | 23 | 0..2 entries; struct id 2 | Where creatures appear (struct id 2); absolute coordinates. |
| `Encounter List/SpawnPointList/X` | FLOAT | 18 | -16.1172..539.22 | Spawn x. |
| `Encounter List/SpawnPointList/Y` | FLOAT | 18 | -177.089..220.467 | Spawn y. |
| `Encounter List/SpawnPointList/Z` | FLOAT | 18 | -4e-06..57.4448 (40 values) | Spawn z. |
| `Encounter List/SpawnPointList/Orientation` | FLOAT | 18 | 0, 0.589049, 2.55254, 2.94524 | Spawn facing, radians. |
| `List` | List | all | 0..49 entries; struct id 0 | Item instances lying in the area (struct id 0). |
| `List/XPosition` | FLOAT | 2 | -0.664896..114.125 | Position x. |
| `List/YPosition` | FLOAT | 2 | 81.5504..191.63 | Position y. |
| `List/ZPosition` | FLOAT | 2 | 8.1258, 8.13222, 8.15275, 8.56571 | Position z. |
| `List/XOrientation` | FLOAT | 2 | -0.980787..1 (23 values) | Facing vector x. |
| `List/YOrientation` | FLOAT | 2 | -0.923877..1 (18 values) | Facing vector y. |
| `List/TemplateResRef` | ResRef | 2 | e.g. `g_w_stungren01`, `g_w_poisngren01`, `g_w_cryobgren001` | UTI blueprint. |
| `SoundList` | List | all | 0..50 entries; struct id 6 | Sound instances (struct id 6). |
| `SoundList/TemplateResRef` | ResRef | 97 | e.g. `birdsdantext111`, `steamloop`, `positionalvents` | UTS blueprint. |
| `SoundList/GeneratedType` | DWORD | 97 | 0 | 1 if generated from the area's ambient preset; always 0. |
| `SoundList/XPosition` | FLOAT | 97 | -88.6158..527.891 | Position x. |
| `SoundList/YPosition` | FLOAT | 97 | -218.653..439.992 | Position y. |
| `SoundList/ZPosition` | FLOAT | 97 | -7.13853..97.0011 | Position z. |
| `StoreList` | List | all | 0..7 entries; struct id 11 | Store instances (struct id 11). |
| `StoreList/XPosition` | FLOAT | 20 | -16.031..284.104 (36 values) | Position x. |
| `StoreList/YPosition` | FLOAT | 20 | -39.7227..268.927 (36 values) | Position y. |
| `StoreList/ZPosition` | FLOAT | 20 | -0.182243..62.8761 (29 values) | Position z. |
| `StoreList/XOrientation` | FLOAT | 20 | -0.980787..1 (8 values) | Facing vector x. |
| `StoreList/YOrientation` | FLOAT | 20 | -0.98078..1 (8 values) | Facing vector y. |
| `StoreList/ResRef` | ResRef | 20 | e.g. `dan_droid`, `dan_pazaak`, `dan_general` | UTM blueprint (stores use `ResRef`). |
| `TriggerList` | List | all | 0..36 entries; struct id 1 | Trigger instances (struct id 1). |
| `TriggerList/TemplateResRef` | ResRef | 88 | e.g. `k_flee_trigger`, `g_zoncata001`, `g_zoncata002` | UTT blueprint. |
| `TriggerList/XPosition` | FLOAT | 88 | -87.4147..562.388 | Position x. |
| `TriggerList/YPosition` | FLOAT | 88 | -205.218..443.06 | Position y. |
| `TriggerList/ZPosition` | FLOAT | 88 | -2.12063..95.3826 | Position z. |
| `TriggerList/XOrientation` | FLOAT | 88 | 0 | Always 0; ignored. |
| `TriggerList/YOrientation` | FLOAT | 88 | 0 | Always 0; ignored. |
| `TriggerList/ZOrientation` | FLOAT | 88 | 0 | Always 0; ignored. |
| `TriggerList/Geometry` | List | 88 | 1..24 entries; struct id 3 | Polygon vertices relative to the position (struct id 3). |
| `TriggerList/Geometry/PointX` | FLOAT | 88 | -180.503..269.938 | Vertex x. |
| `TriggerList/Geometry/PointY` | FLOAT | 88 | -325.87..149.02 | Vertex y. |
| `TriggerList/Geometry/PointZ` | FLOAT | 88 | -20.8552..35.6227 | Vertex z. |
| `TriggerList/Tag` | CExoString | 26 | e.g. `AreaTransition`, `to14bw`, `to14be` | Instance tag (overrides the blueprint's). |
| `TriggerList/TransitionDestin` | CExoLocString | 26 | strref in 43 | Destination name shown on the transition (strref). |
| `TriggerList/LinkedToModule` | ResRef | 26 | 3 empty; e.g. `ebo_m12aa`, `danm14ab`, `danm14ac` | Destination module of the transition. |
| `TriggerList/LinkedTo` | CExoString | 26 | 3 empty; e.g. `K_EBN_RAMP_ENTRAN…`, `from14be`, `from14bw` | Tag of the destination waypoint/door. |
| `TriggerList/LinkedToFlags` | BYTE | 26 | 1, 2 | 1 door, 2 waypoint. |
| `WaypointList` | List | all | 0..157 entries; struct id 5 | Waypoint instances (struct id 5); carry all UTW fields. |
| `WaypointList/Appearance` | BYTE | 109 | 1, 2, 3, 4 | Toolset model; no effect. |
| `WaypointList/LinkedTo` | CExoString | 109 | always empty | Unused. |
| `WaypointList/TemplateResRef` | ResRef | 109 | e.g. `sw_waypoint001`, `sw_waypoint003`, `sw_waypoint002` | UTW blueprint. |
| `WaypointList/Tag` | CExoString | 109 | e.g. `WP01`, `WP02`, `WP03` | Tag (patrol and spawn scripts find waypoints by tag). |
| `WaypointList/LocalizedName` | CExoLocString | 109 | strref in 4064; inline text in 20 (ids 0) | Name. |
| `WaypointList/Description` | CExoLocString | 109 | strref in 2; 4062 empty | Toolset description. |
| `WaypointList/HasMapNote` | BYTE | 109 | 0, 1 | 1 if it has a map note. |
| `WaypointList/MapNote` | CExoLocString | 109 | strref in 366; 3698 empty | Map note text (strref). |
| `WaypointList/MapNoteEnabled` | BYTE | 109 | 0, 1 | 1 if the note is shown. |
| `WaypointList/XPosition` | FLOAT | 109 | -106.057..562.57 | Position x. |
| `WaypointList/YPosition` | FLOAT | 109 | -223.891..440.897 | Position y. |
| `WaypointList/ZPosition` | FLOAT | 109 | -10..97.0754 | Position z. |
| `WaypointList/XOrientation` | FLOAT | 109 | -1..1 | Facing vector x. |
| `WaypointList/YOrientation` | FLOAT | 109 | -1..1 | Facing vector y. |
| `Placeable List` | List | all | 0..169 entries; struct id 9 | Placeable instances (struct id 9). |
| `Placeable List/TemplateResRef` | ResRef | 111 | e.g. `invisible001`, `k_trans_abort`, `plc_rubble` | UTP blueprint. |
| `Placeable List/X` | FLOAT | 111 | -109.555..564.776 | Position x. |
| `Placeable List/Y` | FLOAT | 111 | -227.419..441.532 | Position y. |
| `Placeable List/Z` | FLOAT | 111 | -8..97.8518 | Position z. |
| `Placeable List/Bearing` | FLOAT | 111 | -3.14159..3.14159 | Facing, radians. |
| `CameraList` | List | all | 0..50 entries; struct id 14 | Static cameras for dialogue (struct id 14), chosen by a DLG node's `CameraID` *(KOTOR)*. |
| `CameraList/CameraID` | INT | 85 | 1..778 | Id the DLG refers to. |
| `CameraList/Position` | Vector | 85 | varies | Camera base position. |
| `CameraList/Pitch` | FLOAT | 85 | 10.4..144.7 | Pitch in degrees (90 = level) *(inferred)*. |
| `CameraList/MicRange` | FLOAT | 82 | 0..30 (25 values) | Audio listener range *(inferred)*. |
| `CameraList/Orientation` | Orientation | 85 | varies | Quaternion (w, x, y, z): yaw about the vertical axis. |
| `CameraList/Height` | FLOAT | 85 | -1.95..22.9 | Height above `Position` *(inferred)*. |
| `CameraList/FieldOfView` | FLOAT | 85 | 8..95 | Field of view, degrees. |
<!-- /gff-table -->

## PTH: area path graph

`<area>.pth` is the coarse navigation graph used for long paths across an area: points on the
walkmesh and the connections between them, stored as an adjacency list.

<!-- gff-table PTH -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Path_Points` | List | all | 0..345 entries; struct id 2 | Graph nodes (struct id 2). |
| `Path_Points/Conections` | DWORD | 94 | 0..8 (9 values) | Number of edges leaving this point (label misspelt in the data). |
| `Path_Points/First_Conection` | DWORD | 94 | 0..788 | Index of its first edge in `Path_Conections`; its edges are the next `Conections` entries. |
| `Path_Points/X` | FLOAT | 94 | -109.334..565.121 | Point x. |
| `Path_Points/Y` | FLOAT | 94 | -222.461..439.446 | Point y (no z: the walkmesh gives the height). |
| `Path_Conections` | List | all | 0..790 entries; struct id 3 | Edges (struct id 3). |
| `Path_Conections/Destination` | DWORD | 94 | 0..344 | Index of the point the edge leads to. |
<!-- /gff-table -->
