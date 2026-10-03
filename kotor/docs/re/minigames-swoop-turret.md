# Swoop racing and the Ebon Hawk turret: survey for implementers

What the original game does for its two action minigames, found by reading the install's data
(ARE, LYT, MDL, NCS, UTS, 2DA) and the minigame code of `swkotor.exe` (the client side,
`0x0066b000`-`0x00675000` plus a few hooks). Everything is in our words; names starting `CSWMini`
are ours (the exe has only log strings such as `CSWTrackFollower:`), addresses are the Steam exe
after unpacking (see [README.md](README.md)). Confidence: **high** = read in code or data and
checked, **med** = read but a link is inferred, **low** = guess. Pazaak is a separate minigame
([pazaak.md](pazaak.md)); this page is the swoop races and the turret only.

Short version: both are "on rails". A **track** is an MDL whose `track` animation moves a
`modelhook` node; the player vehicle follows it, the player only steers a small **offset** from
the rail (lateral for the swoop, aim angles for the turret). Enemies are objects on their own
rails, pads and fighters alike. The module's NWScripts do the game design (gears, timer, HUD,
win/lose) through 97 `SWMG_*` routines; the engine does the rails, the steering, collisions,
bullets and the camera. The HUD is not a GUI panel: it is 3D models attached to the camera.

## 1. Which modules have a minigame

### 1.1 The four live modules (high)

Only four ARE files in the install carry a `MiniGame` struct (format: [gff-module.md](../formats/gff-module.md)).
Their module files hold just ARE/GIT/IFO (`*.rim`) and scripts, sound templates and PTH (`*_s.rim`);
all models, textures, LYT, VIS, WOK come from the BIFs and texture packs.

| Module (area) | Files in `modules/` | Kind | Started by | Ends by |
|---|---|---|---|---|
| `tar_m03mg` (`m03mg`) | `tar_m03mg.rim`, `_s` | swoop race, Taris | `k_ptar_swooprun` in `tar_m03af` | `heartbeat` -> `StartNewModule("tar_m03af", wp "tar03_wpmechanic")` |
| `tat_m17mg` (`m17mg`) | `tat_m17mg.rim`, `_s` | swoop race, Tatooine | `k_ptat_swoop04` in `tat_m17ae` | `heartbeat` -> `tat_m17ae`, wp `tat17ae_swoop_return` |
| `manm26mg` (`m26mg`) | `manm26mg.rim`, `_s` | swoop race, Manaan | `k_pman_swoop42`, `k_pman_swoop44` in `manm26ab` | `heartbeat` -> `manm26ab`, wp `from26mg` |
| `M12ab` (`m12ab`) | `M12ab.rim`, `_s` (no prefix) | Ebon Hawk gunner turret | see 1.2 | `k_pebo_sthdeath*` / `k_pebo_hawkhit` -> `ebo_m12aa` etc. |

`ARE.MiniGame.Type`: 1 = swoop, 2 = turret (only values). Each module has one area. No saving: `modulesave.2da`
rows have `includeinsave 0`, `autosaveonenter no`; `loadscreens.2da` rows use images `LOAD_SWOOP` / `LOAD_TURRET`.
The server loads these areas like any other (rooms, GIT sounds, scripts); the GIT lists are almost
empty: swoop GIT = 17-18 sound objects (tags below); `m26mg` also 3 `n_repoff` creatures; `m12ab` has 10
`plc_invisible` placeables (anchors for explosion effects) and 1 sound (`Alarm01`). The area-load
message carries a "has minigame" byte (`FUN_0050aaa0` writes area `+0x234`, the client reads it in
`CSWCArea::LoadArea` `0x00607610`) (high).

### 1.2 Entry, exit and the globals around them (high unless marked)

- **Swoop**: story scripts call `StartNewModule("<mgmodule>")` with no waypoint or movie. `tar_m03mg` gets
  `TAR_SWOOP_ACCEL` first (a tuning number, see 2.3). On finishing, the heartbeat stores the time in
  `<TAR|TAT|MAN>_SWOOP_MIN/SEC/MSEC` (Taris also `..._BEAT`, `Tar_SwoopRaceCounter`, `TAR_RACEMOVIE` and
  plays a movie with `PlayMovie`), fades out with `SetGlobalFadeOut` and returns to the home module (table above).
  Dialogues around the races exist (`man26_swoop*`, `tat17_04swoop_01`, `pebn_swoopdrd`) and presumably read those globals (not
  checked). Manaan's `k_pman_swoop42` sets `MAN_OFFICIAL_RACE` first.
- **Turret**: `StartNewModule("m12ab", wp "", movie1 "11a")` from `k_ren_taris03` (sets `K_TURRET_SKYBOX` 5),
  `k_ren_levescape` (10, second movie `17a`), `k_ren_unkturret` (15), `k_ren_turretload`, `k_ren_turretld02`
  (skybox left as is) and `k_act_hk47simul` (sets `K_HK47_SIMULATION`; no movie). `k_pebo_mgload` (module
  load) zeroes `ebo_num_fighters`, `ebo_turret_done`, `M12AB_END_SYNC`, `M12AB_START_SYNC`, `K_LAST_LOCATION`;
  `k_pebo_skybox` (area OnEnter) plays room animation 1 / 2 / 3 / 4 of room `m12ab_01a` for `K_TURRET_SKYBOX` 5 / 10 / 15 /
  other (the sky of that planet) and, except for 5, barks strref 37107 "Incoming fighters!" after 1.5 s. When all six fighters are dead (or the Hawk is "critically damaged") the
  script `ST_PlayPostTurret` logic (inlined in `k_pebo_sthdeath2..7`, also script `k_ren_turret`) picks the next
  module by `K_FUTURE_PLANET` / `K_CURRENT_PLANET`: `StartNewModule("ebo_m12aa", movie "11b")`, `ebo_m40ad`, ...
  The Hawk can be lost: `k_pebo_hawkhit` ends the real sequence with `EndGame(TRUE)` when its HP falls below 2000
  (it starts at 3000, so 100 fighter bullets of 10); in the HK-47 simulation the same event only runs `k_ren_turret`.

### 1.3 Leftovers that exist in the data but nothing starts (high)

`m45mg` (full swoop track: LYT, 3 rooms, `m45mg_camera`, 31 tracks, 22 obstacles, `modulesave` row, no
ARE/GIT), `m12ac`..`m12ah` (turret variants: LYT, `_mgt01..07`, `_mgo01`, `loadscreens` rows, no ARE),
`mgf_ebonhawk.lyt`, models `mgf_gear01..05`, `mgf_carthturret`, `mgf_turlights`, `mgb_ebonright`, `m03mg_camera`,
`m26mg_se2` is a room of `m26mg` (used). Sounds `mgs_basethrust03`, `mgs_bigship`, `mgs_colenthrst`,
`mgs_drawmain`, `mgs_hover_*`, `mgs_lowhvr_*` are referenced by nothing.

### 1.4 `ARE.MiniGame` values per module (high; field meanings in gff-module.md)

| Field | m03mg | m17mg | m26mg | m12ab (turret) |
|---|---|---|---|---|
| Type / Near / Far clip / FOV | 1 / 0.1 / 40000 / 65 | same | same | 2 / 0.1 / 2000 / 65 |
| MovementPerSec / LateralAccel | 100 / 300 | 100 / 300 | 100 / 300 | 100 / 1200 |
| UseInertia / DoBumping / Bump_Plane / DOF | 1 / 0 / 3 / 1 | same | same | 0 / 0 / 3 / 5 |
| Music | none (a space) | none | none | `mus_bat_sithbs` |
| Mouse | absent | absent | absent | AxisX 3, AxisY 1, no flips |
| Player.Track (length of `track` anim) | `m03mg_tr01` 48 s | `m17mg_mgt01` 48 s | `m26mg_mgt01` 48 s | `m12ab_mgt01` 0 s |
| Player.Num_Loops | 1 | 1 | -1 | -1 |
| Sphere_Radius / Invince_Period | 3 / 0.3 | 3 / 0.3 | 3 / 0.3 | 40 / 0 |
| Hit_Points = Max_HPs | 999 | 9999 | 9999 | 3000 |
| Accel_Secs / Min,Max_Speed | 25 / 0,0 | same | same | 0.01 / 0,0 |
| Start_Offset_X / Target_Offset_Z | 0 / 0 | 0 / 0 | 0 / 0 | 7 / -5 |
| Tunnel Pos, Neg, Infinite | all 0 (scripts set them) | all 0 | all 0 | X +45 / +2, Z +-9999 and Infinite z |
| Camera model, CameraRotate | none, 0 | none, 1 | none, 1 | `m12ab_camera`, 1 |
| Player.Models (RotatingModel) | `v_superbike`, `m17mg_camera`, `v_damagetat`, `lmg_distort` (all 1) | same four, other order | `v_damageman` instead of `v_damagetat`, plus `v_sbikewake` | `mgf_turret`, `mgf_turretwk`, `mgf_ebonhawk` (0), `mgf_hud01`, `mgf_hud02` |
| Player scripts | OnCreate `oncreate`, OnHeartbeat `heartbeat`, OnFire `onfire`, OnHitFollower `accelpad`, OnHitObstacle `obstacle` | same | same | OnHeartbeat `k_heartbeat`, OnDamage `k_pebo_hawkhit` |
| Player gun banks | 1: `mgg_null`, bullet `mgb_null`, dmg 0, rate 0.01, target 3 | same | bullet `mgg_null`, target 1 | 2: `mgg_turret`, bullet `mgb_ebonleft`, dmg 30, rate 0.3, speed 300, life 3, target 2, fire sound `mgs_ebon_fire` (bank 0), hit sound `mgs_sith_hit` |
| Enemies / Obstacles | 29 pads / 22 | 30 pads / 22 | 30 pads / 22 | 6 fighters / 1 |

Enemy entries: **pads** (swoops) = model `mgf_accelpad01`, `Trigger` 1, track `<mod>_mgt02..31`, Num_Loops -1, sphere
3 (m03) or 2, Hit_Points 1 (m17: 80, except #18), death sound `mgs_accelpad`, no scripts, no guns. **Fighters** (turret) =
`mgf_sithfighter`, tracks `m12ab_mgt02..07`, sphere 20, HP 100, OnCreate `k_pebo_sthcreate`, OnDeath `k_pebo_sthdeath2..7`,
death sound `mgs_sith_expl`, one bank: `mgg_null`, bullet `mgb_sithfighter`, dmg 10, life 2, rate 0.4, speed 200, target 1,
fire `mgs_sith_fire`, hit `mgs_ebon_hit`, Inaccuracy 0.01, Sensing_Radius 200, Horiz/Vert_Spread 70/70. **Obstacles** list model
names `<mod>_mgo01..22` (swoop; no scripts) or `m12ab_mgo01` (asteroid emitters). Both lists are placed from the LYT
`trackcount`/`obstaclecount` sections (positions; `lib/formats/lyt.ctx` already parses them).

## 2. The script side

### 2.1 The 97 routines (`SWMG_*`; 520-521, 563, 583-668, 683-688, 717-718) (high for numbers, signatures and handlers)

Handlers: `CSWVirtualMachineCommands::ExecuteCommandSWMG_*` `0x005cb480`-`0x005cd280`, filled by
`InitializeMiniGameCommands` `0x005cd2c0`; `SetSpeedBlurEffect` `0x00543550`. Most share handlers that switch on the
command number. All go through `0x005edb00` (the area's minigame object, `CSWCArea+0x264`) and the object
registry `0x005edaf0`. Numbers in () = unique shipped scripts using the routine (0 = unused by the game).

| Group | Routines |
|---|---|
| Objects (12) | GetPlayer 611 (9), GetEnemyCount 612 (1), GetEnemy 613 (2), GetObstacleCount 614, GetObstacle 615, GetObjectByName 585, GetObjectName 597, IsFollower 599, IsPlayer 600, IsEnemy 601, IsTrigger 602, IsObstacle 603 |
| Animation (2) | PlayAnimation 586 (18), RemoveAnimation 607 (3) |
| Events and defaults (15) | GetLastEvent 583, GetLastEventModelName 584, GetLastBulletHit{Damage 587, Target 588, Shooter 589, Part 639}, GetLastBulletFired{Damage 595, Target 596}, GetLastFollowerHit 593 (2), GetLastObstacleHit 594, GetLastHPChange 606, **OnBulletHit 591, OnObstacleHit 592, OnDamage 605 (1), OnDeath 598 (6)** |
| Any follower (12) | AdjustFollowerHitPoints 590 (2), SetFollowerHitPoints 604 (1), GetHitPoints 616 (1), Get/SetMaxHitPoints 617/618, Get/SetSphereRadius 619/620, Get/SetNumLoops 621/622, GetPosition 623 (4), GetIsInvulnerable 665 (2), StartInvulnerability 666 (2) |
| Player movement (22) | Get/SetPlayerSpeed 643/649 (8/5), Min 644/650 (0/5), Max 667/668 (0/5), AccelerationPerSecond 645/651 (2/7), Get/SetPlayerOffset 641/647 (1/0), Get/SetPlayerOrigin 655/656, Get/SetPlayerTunnelPos 646/652 (0/5), TunnelNeg 653/654 (0/5), TunnelInfinite 717/718, Get/SetPlayerInvincibility 642/648, Get/SetLateralAccelerationPerSecond 521/520 (0/3) |
| Gun banks (24) | GetGunBankCount 624, IsGunBankTargetting 640, Get/Set{BulletModel, GunModel, Damage, TimeBetweenShots, Lifespan, Speed, Target} 625-631 / 632-638, Get/Set{HorizontalSpread, VerticalSpread, SensingRadius, Inaccuracy} 657-660 / 661-664 (none used) |
| Camera and screen (4) | SetSpeedBlurEffect 563 (3), Get/SetCameraNearClip/Far 608-610 (none used) |
| Sound per object (6) | Get/Set SoundFrequency, SoundFrequencyIsRandom, SoundVolume 683-688 (none used) |

Only 25 of the 97 are used by shipped scripts; the other 72 can be correct-but-simple (they read or write one field).
Facts for the VM: object arguments are **minigame object ids** (small integers below 255 from a 255-slot
registry, `0xff` invalid), `CONSTO 0` (OBJECT_SELF) is the object whose script runs, so a player script
playing "gear1" on OBJECT_SELF plays it on the player's models (med). `AdjustFollowerHitPoints` pops only
(object, int); the 3rd argument `nAbsolute` is never read, so HP is always changed relatively (high; the pad
script passes -100 and kills 1-80 HP pads). `GetPlayer/GetEnemy/GetObstacle` push `0xff` (not OBJECT_INVALID) when there
is no such object; `GetEnemy(i)` and `GetObstacle(i)` are 0-based (`k_pebo_hawkhit` loops 1..count, a harmless off-by-one).
`GetLastEvent` returns the last animation event string stored on the calling object; no shipped script calls it.

### 2.2 Script slots and the "script replaces default" rule (high)

Each follower or obstacle has 10 script resrefs, read by `0x0066c420` and `0x0066c740` from the ARE
`Scripts` struct. Slot numbers: 0 OnCreate, 1 OnHitBullet, 2 OnHitFollower, 3 OnAnimEvent, 4 OnHeartbeat,
5 OnDamage, 6 OnDeath, 7 OnFire, 8 OnHitObstacle, 9 OnTrackLoop. Scripts run with `CVirtualMachine::RunScript(name,
objectId, 1)`. When a slot has a script the engine runs it **instead of** the built-in behaviour; the script
calls `SWMG_OnDamage/OnDeath/OnBulletHit/OnObstacleHit()` to get the default as well:

| Slot | Runner | Default behaviour (when no script, or the script calls SWMG_On...) |
|---|---|---|
| 5 OnDamage `0x0066e7a0` | via AdjustFollowerHitPoints (`0x0066e8e0`) | add the pending HP change (healing clamps to max HP); a hit with HP still > 0 plays `damage` then `Ready_01`; HP <= 0 sets the dead flag and runs slot 6 |
| 6 OnDeath `0x0066e2a0` | | play the death sound (`mgs_accelpad` at volume 127, others 100), play `die` on every model, free them on the `donedie` event, remove the object |
| 1 OnHitBullet `0x0066c190` | bullet hit | apply `-bullet damage` if the bullet's target mask matches the object's class bit, play the collision sound |
| 8 OnHitObstacle `0x0066e5c0` | obstacle hit | clear the models' controllers and die (set the dead flag, run slot 6); the swoop scripts replace this, so a swoop never dies |
| 2 OnHitFollower `0x0066c2d0`, 4 OnHeartbeat `0x0066c0a0`, 0 OnCreate, 3, 9 | | script only; **OnHeartbeat runs every rendered frame** (it is called from the follower's per-frame update `0x0066e130`, which also counts down the invulnerability timer and moves the engine sound) |

`OnFire` (7) is not run on the key press: pressing fire starts the gun model's `fire` animation (rate-limited by
`Rate_Of_Fire`), and the animation system's automatic **`startfire`** event runs the script (`FireGunCallback` `0x00673a40`,
branch for events starting "start"+"fire"); the same callback spawns a bullet on the MDL event `fire<N>` (med: no model
has a `startfire` event, so it must come from the animation system, the same way `donedie`, `starttrack` and `loop` do).
OnAnimEvent runs for events named `custom_<x>`; `GetLastEvent` then returns `<x>`. `loop...` events (`0x0066fe50`)
decrement `Num_Loops` (-1 = forever), restart the track speed and run OnTrackLoop.

### 2.3 What the shipped scripts do (disassembled with `ncsdis.py`; 18 unique scripts) (high unless marked)

Swoop (`oncreate`, `heartbeat`, `onfire`, `obstacle`, `accelpad`; `heartbeat` differs per module only in the
globals and the exit; `ggg`, `reflux` are stubs that play a sound):

- `oncreate`: `MIN_RACE_GEAR` = 5 (the "countdown" state), `SoundObjectPlay("Wind")`, `SetPlayerSpeed(0)`, plays `camshake1`
  (looping, overlay) and `gear0` on the player.
- `heartbeat` (**every frame**): `MIN_RACE_GEAR` is the state: 5 = waiting (records the start time, becomes 4), then on elapsed
  time > 0.1 / 3 / 4 / 5 s it plays the HUD lights `S3`, `S2`, `S1`, `SGo` with sounds `PowerUp`+`Idle`, `S1`, `S1`, `Go` and steps
  4, 3, 2, 1; after the last the gear is 0 and the player may shift (`onfire`). It measures the race time (game clock:
  `GetTimeHour*120 + Minute*60 + Second + Millisecond/1000`, valid because our minute is a real minute, see
  `lib/engine/routines/time.ctx`), writes `MIN_TIME_*` and shows it on the HUD with `MilSecOne/Ten`, `SecOne/Ten`,
  `MinOne/Ten` + digit (animation names like `SecOne7`); shows speed as `meter0..9`; sets the `Wind` volume to speed/4 and the
  `Engine01..05` loops by gear; calls `SetLateralAccelerationPerSecond` with a value between 50 and 300 derived from speed
  (formula not decoded, low speed = sluggish steering) and `SetSpeedBlurEffect` on/off around speed 149 (med); plays `camshake<n>`;
  reads `SWMG_GetPosition(player)` and plays `cDistL5..0` (distance left);
  when the position passes 3800 it starts the finish: `PowerDown01` sound, min=max=0, accel 3, tunnel pos/neg opened to
  (100,0,0), HUD `downthrust` + `endloop`, engines faded, then `SetGlobalFadeOut`, time to `*_SWOOP_*` globals and
  `StartNewModule` back (3 s `DelayCommand`). Gear thresholds 35 / 60 / 100 / 150 / 210 appear as constants.
- `onfire` (the gear shift, Space): gears 1..5; shifting to gear g+1 is allowed when the speed has reached threshold
  {35, 60, 100, 150, 210}[g]; it then sets MinSpeed = that threshold, MaxSpeed = threshold x {2, 2, 1.9, 1.5, 2}, acceleration
  = {20, 8, 6, 3, 2} x (`TAR_SWOOP_ACCEL`/10, or 1 when unset) and tunnel bounds to +-20 on x; plays `Shift<g>`, swaps
  `Engine0<g>` loops and plays `gear<g>`/`gear<g>l`; a wrong shift plays sound `Penalty` (`gui_error`) (med on exact conditions).
- `obstacle` (OnHitObstacle): if `MIN_RACE_GEAR > 0`: sound `Damage`, speed x 0.7, play `damage` (overlay).
- `accelpad` (OnHitFollower): if the player is not invulnerable: acceleration x 1.1, speed x 1.05; play `boost`;
  `StartInvulnerability(player)`; kill the pad with `AdjustFollowerHitPoints(pad, -100)`.

Turret (`M12ab_s`): `k_heartbeat` (player OnHeartbeat) turns `GetPlayerOffset` into a 0..360 index and plays the HUD
compass animation `HudRot_NNN` on the player; on the first beat starts the six `SithLoopNN` radar animations;
`k_pebo_sthcreate` increments `ebo_num_fighters`; `k_pebo_sthdeathN` calls `SWMG_OnDeath()`, plays `SithLoopNNd` (blip off), decrements the
counter and at 0 sets `ebo_turret_done`, delays 2 s and leaves (1.2); `k_pebo_hawkhit` (OnDamage, high): while
`M12AB_END_SYNC` is unset and HP >= 2000 it calls `SWMG_OnDamage()` (applies the damage), plays HUD animation `Health<n>`
(`n = (HP-2000)*12/1000 + 1`, `Health0n` below 10) and starts sound `Alarm01` when n is 3; below 2000 it sets `M12AB_END_SYNC`, sets every
fighter's HP to 2000, stops the alarm, plays `Health00`, applies visual effect 3003 at the `Invisible` anchor and at the Hawk, fades out
(`SetGlobalFadeOut`), `DisableVideoEffect`, then barks strref 38465 and calls `EndGame(TRUE)` after 4 s, or in the HK-47 simulation runs
`k_ren_turret`; `k_pebo_mgheart` (module heartbeat) re-checks `ebo_turret_done` and runs the same leave logic.

## 3. Data the engine needs

- **2DA**: none of its own. Touched: `loadscreens` (`LOAD_SWOOP`/`LOAD_TURRET`), `modulesave`, `globalcat` (`M12AB_START_SYNC`
  number, `M12AB_END_SYNC` boolean), `keymap` input class `ICMiniGame` (rows `MGshoot` Space action 217, `PauseMinigame` Esc
  253, `Pause` 224, `ToolTips` 225, `MGActionUp/Down` W/S = event 282, `MGActionLeft/Right` A/D = 283, arrows = 285/286).
- **Models** (all in `models.bif`; high): player tracks `m03mg_tr01`, `m17mg_mgt01`, `m26mg_mgt01` (a root dummy + `modelhook`, m03 also
  `Camera01`, m17 a mesh; one `track` animation: **a straight 2-key translation of `modelhook` along +Y** from 0 to 4980 (m03) or
  4699.8 (m17, m26) over 48 s, identity rotation; the node's static offset is (5,0,2) / (100,100,2.66)) and pad tracks `_mgt02..31` (static `modelhook` only); the turret fighters' tracks `m12ab_mgt02..07` are Bezier splines
  (54 keys in `mgt02`) of 43.03 / 48.80 / 51.30 / 61.70 / 84.10 / 54.60 s; the HUD radar animations `SithLoop02..07` of `mgf_hud01` have the same
  lengths, so the blips replay the fighters' paths. Obstacles `m03mg_mgo01..22`: dummy + `aabb` + trimesh, animations `Ready` (4 s) and
  `hit`. Pad `mgf_accelpad01`: aabb + 2 meshes, animations `Ready_01`, `hit`, `die` (7.63 s).
- **Node and animation names the engine or scripts look up** (high): `modelhook` (anchor of every rail, attach point of the
  vehicle models), `camerahook` (the camera is attached to this node of the player's camera/HUD model), `gunbankN` (where gun
  models of bank N are attached; also `hitbullet`), `bullethookN` (bullet spawn on the gun model), `hitbullet` (bullet hit test node
  of a target), `track`, `Ready_01`/`ready`, `fire`, `damage`, `die`, `explode`, `hit`, `boost`, `Bank{L,R}_01..10` (bike lean, below).
  Event names: `fire<N>`, `detonate` (emitters), automatic `start<anim>`, `done<anim>`, `loop...`, `custom_<x>`.
- **Player models** `v_superbike` (83 nodes: 64 meshes, 13 emitters; 35 animations: `Gear0..5`, `Gear1l..5l`, `BankL_01..10`,
  `BankR_01..10`, `damage`, `downthrust`, `endloop`, `boost`), `v_sbikewake` (`WakeSpeed00..09`, Manaan), `v_damagetat`/`v_damageman`
  (emitters, `damage` with `detonate` events), `lmg_distort` (heat distortion: `Gear0..5`). **HUD = camera model** `m17mg_camera`
  (104 nodes, 105 animations: `gear0..5(l)`, `meter0..9`, `MilSecOne0..9`, `MilSecTen..`, `SecOne..`, `SecTen..`, `MinOne..`, `MinTen..`,
  `camshake1..5`, `S1..S3`, `SGo`, `cDist1..5`, `boost`, `die`, `damage`; one-frame animations select digits), node `camerahook`.
  Turret: `mgf_turret` (35 nodes, `gunbank0/1`, anims `Ready_01`, `damage`, `die`, `fire`), `mgg_turret` (gun: node `bullethook0`, `fire` 0.23 s with
  event `fire0`, 2 lights), `mgb_ebonleft` (bullet: `ready`, `explode` 2.3 s, 3 emitters), `mgf_turretwk` (aabb only), `mgf_ebonhawk` (`hitbullet`
  target; used as player collision mesh), `mgf_hud01` (372 animations: `HudRot_000..359`, `SithLoop02..07` + `d`), `mgf_hud02` (`Health00..12`), `m12ab_camera`
  (`camerahook`, anims `hud1..7`), `mgf_sithfighter` (13 emitters, `gunbank0`, `hitbullet`, `Parts_01..09`, `die` 2.3 s with `detonate` events),
  `mgb_sithfighter`, `mgg_null`/`mgb_null` (empty gun and bullet).
- **Textures**: 59 `lmg_*.tpc` (HUD, effects, island/buoy/crate props) plus the models' own textures (`v_suprbike01`, ...), the room
  lightmaps (`m03mg_01a_lm*`, `m17mg_01c_a0001*`, `m26mg_01a_lm*`) and the loading images `load_swoop`, `load_turret`.
- **No `.gui` file** belongs to the minigames; the HUD mode is `CGuiInGame::SetHudMode(2)` (the normal HUD hidden). `pause.gui` is shared.
- **Audio** (`sounds.bif`, `streamsounds`, high): `mgs_*` one-shots (engine `mgs_engine_01l..05l` loops and `mgs_bike_idle`/`mgs_alarm` in `streamsounds`,
  `mgs_shift_01`, `mgs_pwrup/pwrdown`, `mgs_go`, `mgs_s1`, `mgs_bike_dmg`, `mgs_accelpad`, `mgs_ebon_fire/hit`, `mgs_sith_fire/hit/expl`, `gui_error`), music
  `streammusic/mus_bat_sithbs` for the turret. Swoop sounds are positioned UTS objects looked up by tag from the script (`Engine01..05`,
  `Shift1..5`, `Idle`, `Damage`, `PowerUp`, `PowerDown01`, `Go`, `S1`, `Penalty`; `Wind`, `S2`, `S3`, `Reflux` have no template, calls are no-ops).

## 4. The engine side

### 4.1 Objects (client side only; med for names, high for addresses)

The minigame lives in the **client** (`CSWC*`): `CSWCArea` (`+0x264`) owns it; the server knows only the flag. Created in
`CSWCArea::LoadArea` `0x00607610`: `FUN_00671c40` builds the minigame object (ours: `CSWMiniGame`, 0xf0 bytes, vtable `0x00752914`, one slot =
destructor); then every LYT track is registered (`0x006720c0`: name + position), every LYT obstacle is instantiated (`0x00672240`: its model placed at the LYT
position, animation `ready`, an obstacle object `0x00670640`, vtable `0x0075287c`, 0xb4 bytes); then `FUN_006723d0` reads `ARE.MiniGame`
(clip planes `0x00670b50`, FOV `+0x70`, `Type` `+0x80`, `MovementPerSec` `+0x74` default 6/90 for type 1/2, `LateralAccel` `+0xbc` default 60, `Bump_Plane` `+0x78`
0..3, `DOF` `+0x7c` 0..7, `UseInertia` `+0x94`, `DoBumping` `+0x95`, `Music` `+0x96`, mouse axes `+0x84/+0x88` 0..3 with sign = flip), creates the
player (`0x00671820` swoop, `0x006719d0` turret with camera model) and each enemy (`0x00671e40`), and matches obstacle scripts by model name.
Class tree (all objects take a slot in the 255-slot registry; vtable, constructor):

| Class (ours) | Ctor / vtable | Notes |
|---|---|---|
| `CSWMiniObject` | `0x0066c540` / `0x00752424` (purecall) | base: id (`+8`), name, 10 script slots, `As{Follower,Player,Enemy,Obstacle}` slots (5-8) |
| `CSWTrackFollower` | `0x0066dee0` / `0x007524c8` | rail follower: models list (`+0x68/6c`, 8-byte entries ptr+rotates), gun banks (`+0x74`), HP `+0x8c`/max `+0x90`, speed `+0x98`, invulnerability `+0x9c/a0`, loop count `+0x80` (Num_Loops, default 1), target-class bit from vtable slot 15 (player 1, enemy 2), last follower hit `+0x50` |
| `CSWMiniPlayer` | `0x0066eb50` / `0x007525f0` | 0x250 bytes: offset vector `+0x1c4`, bank level `+0x1d0`, min/max/accel `+0x1d8/dc/e0`, tunnel `+0x1e4..0x204`, origin `+0x208`, target offset `+0x214` |
| `CSWMiniEnemy` | built in `0x00671e40` / `0x007528a8` | fighters and pads; `Trigger` flag byte at `+0x1a0` (read by `0x006705f0`) |
| gun bank / bullet | `0x006743b0`, `0x00674530` / `0x00752ae4`, `0x00752af0`; bullet controllers `0x006dadf0`, `0x006db590` | |

### 4.2 Per-frame flow (high)

`CClientExoAppInternal::ProcessInput` `0x006227e0` (only when the client has no controlled creature and the area has a minigame): reads the
input events, calls `0x00670fb0` (steering integrator), for the turret `0x00671020` (mouse), then `0x006710e0` (player step + bank level). The 3D
frame (`CSWCModule::Render` -> `FUN_006097f0` -> `0x006735d0`) updates every follower and obstacle through vtable slot 9 (which runs OnHeartbeat), frees dead objects, then runs the
collision step `0x006732f0` once with up to **3 iterations** of player-vs-follower resolution. Time step = frame `dt` (no fixed step).
`SetInputClass(1)` (minigame) attaches the camera (`0x00671670`), starts the music (`0x006714e0`, looping streaming source) and switches HUD mode 2.

### 4.3 Movement model (high unless marked)

- **Along the rail**: the vehicle is parented to node `modelhook` of the track model; the engine plays the `track` animation of the track model with
  playback rate `speed * 0.01` (`0x0066c870`; speed 100 = real time). So distance along the track = `speed/100 * 103.75 u/s` on m03mg (4980/48), 97.9 u/s on m17/m26.
  Speed ramps linearly toward `MaxSpeed` at `Accel` per second (`0x0066d640` start); `Accel = (Max-Min)/Accel_Secs` from the ARE (0 here, scripts set it);
  `SetPlayerSpeed/Min/Max/Accel` ignore negative values. The default player (before the ARE) has speed/min/max 100, accel 0, HP 100.
- **Steering** (`0x00670fb0`, `0x00670a90`): input `u` per axis in [-1, 1] (keyboard events sum clamped; swoop: `u = (axis, 0, 0)` then y,z negated;
  turret: raw `(left/right, 0, up/down)` becomes `(-up/down, 0, -left/right)`, option "Reverse Minigame YAxis" negates the vertical axis). With `UseInertia` mode (the
  default `+0xac = 1`) the lateral state is integrated with a 4th-order Runge-Kutta step per frame, state `(v, x)` per axis:
  `dv/dt = L * u - (L / M) * v`, `dx/dt = v` with `L` = LateralAccel, `M` = MovementPerSec (stage inputs: previous, mean, mean, current).
  Terminal speed `M*u`, time constant `M/L` (swoop 0.33 s at 300; the script lowers `L` at low speed). The alternative mode (`+0xac = 0`) is `x += M*u*dt`.
  Turret mouse (`0x00671020`): events 0x17/0x18 (the vertical one negated) divided by 20 (global `0x007a232c`), clamped to +-1, `x[axis] -= value * M * dt` on the axis named by
  `Mouse.AxisX/Y` (1..3 = x,y,z; a negative stored value = flipped), applied to the new position state directly, then the pointer is recentred each frame.
- **Offset and bounds** (`0x0066d640` end, `0x0066cb40`): new offset = old + (new x - old x); each axis is clamped to
  `[Neg + origin, Pos + origin]` unless its `TunnelInfinite` flag is set, in which case turret (type 2) angles wrap at 360. The offset is written into the node-follow
  controller (types 0x3ea/0x3eb, fields `+0x3c..+0x44`) of every model flagged `RotatingModel` (and of the turret camera model), so those models are displaced (swoop) or rotated
  (turret, degrees) relative to `modelhook`; the Hawk model (flag 0) stays put (med; the controller code itself was not read). "Walls" are only these bounds; there is no
  track-mesh collision.
- **Bank animation** (`0x006710e0`, `0x0066ce60`, swoop only): a second smoothed value `s` follows the horizontal input (rises by `dt*u` up to about 0.255, decays to zero by
  detents at 0.235 / 0.175 / 0.105 / 0.042 when released); level = 0 if |s| < 0.021 and 1..10 by thresholds 0.021, 0.042, 0.071, 0.1, 0.135, 0.17, 0.2, 0.23, 0.24, 0.25;
  the engine plays `Ready_01` for 0 and `Bank<L|R>_<NN>` otherwise (sign to letter not checked, low) on the player's models.
- **UseInertia in `0x0066d640`** (low): when set the engine also reads the per-frame position and orientation key deltas of the track (two merged key lists) and rotates the
  lateral velocity along curved tracks (`Bump_Plane` 1..3 picks the model axis used as plane normal, `0x00670bb0`); on the shipped straight swoop tracks it has no visible effect.

### 4.4 Collisions and damage (high for structure, low for the tests' exact geometry)

- Player vs followers (`0x0066eda0`): for every follower that is a **trigger** (pad) or when `DoBumping` (all data: 0), a swept sphere test (`FUN_004abdd0`) with radius
  `follower sphere + player sphere`. Non-trigger hit: push-out along the contact (averaged over the hits, then clamped by the tunnel bounds), the follower loses the player's
  `Bump_Damage` (0 in all data), `OnHitFollower` of both. Pad hit: only the two scripts run (`0x0066c2d0`), after recording the pad as `GetLastFollowerHit`.
  After a non-trigger bump with the player's invulnerability timer at 0 the engine resets speed to MinSpeed, plays `damage`/`Ready_01`, starts the timer from `Invince_Period`.
- Player vs obstacles (`0x0066e6b0`): the obstacle's AABB tree (the MDL `aabb` node) is tested against the player's `modelhook` position; hit -> `hitbump`, OnHitObstacle
  script (slot 8). The shipped script slows the bike; there is no engine-side bounce.
- Bullets vs followers (`0x0066d4e0` -> `0x006730a0`): each bullet's segment is tested against the target's `hitbullet` node/mesh; on a hit the bullet plays `explode`,
  the target runs OnHitBullet (damage = bullet damage, only if `Target_Type` bit matches the target class: 1 = player side, 2 = enemies, 3 = both; bits 0x11111110 are invalid).
- `SWMG_StartInvulnerability`, `GetIsInvulnerable`: one timer per follower; `Invince_Period` is its length.

### 4.5 Guns, bullets, enemy aim (med)

Gun banks are `Gun_Banks` entries; the gun model is attached to node `gunbank<BankID>` of the vehicle model (`0x0066e490`). Fire pressed (`HandleInputAction` case 0xd9, once per
key press: the `MGshoot` row is not repeatable; ignored while paused -> `0x0066dc50` -> controller `0x006daec0`): if the bank's cooldown is 0, cooldown = `Rate_Of_Fire`, play `fire`
then `ready` on the gun model and the fire sound. The `fire<N>`
event spawns the bullet model at `bullethook<N>` (`FireGunCallback`), with direction from the gun orientation (player: straight; enemy: toward the player with a random error
`normalize(rand) * Inaccuracy * distance`), speed `Speed`, lifespan `Lifespan`. Enemy gun controller (`0x006db180`, `0x006db3d0`, each frame): if the player is within
`Sensing_Radius` it turns the gun toward it, limited to +-`Horiz_Spread` / +-`Vert_Spread` degrees; it may fire only while inside both limits and cooldown is 0. Player's
bullets with damage 0 (swoop) are harmless dummies that only trigger the `fire` animation and OnFire.

### 4.6 Camera and view (med)

The area camera (FOV, near, far from the ARE) gets a controller (`FUN_0049fb10`, 0x3c bytes) that makes it follow the world transform of node `camerahook` in the first of the
player's models that has one (swoop `m17mg_camera`; searched in list order, then the track model), or, for the turret, of the dedicated camera model `Player.Camera`
(`m12ab_camera`, kept at player `+0x220`). There is no smoothing. `CameraRotate` says whether
the camera model turns with the player's rotating models. The speed blur (`0x0044f0a0..0x0044f130`: enable/disable and a ratio, default 0.75) and the heat distortion model are
renderer features. The HUD models are children of the camera model, so they follow it.

### 4.7 Open questions (nothing below was resolved)

- Exact obstacle and bullet hit geometry (`FUN_004abdd0`, the model vtable `+0x88` test); whether the obstacle test uses a radius.
- `DOF`, `Bump_Plane`, the `+0xac` mode switch (nothing in the exe writes 0), `Mouse` flags are read but their only visible effect is above.
- How the server omits the party in minigame areas (no controlled creature) and how `GetFirstPC` behaves there; whether a mouse button also fires the turret (only Space is bound).
- Lateral axis sign for `Bank<L|R>`; the per-vehicle sound `Sounds.Engine` (empty in all data) path `0x0066e130`.
- Whether `OnTrackLoop` ever fires (`Num_Loops` 1 on Taris/Tatooine): the finish is script-driven by position, not by the loop event.

## 5. Recommended implementation plan (ctxlang)

**Engine hooks needed** (all small, none exist yet; `lib/formats/lyt.ctx` already parses tracks/obstacles, `lib/mdl/anim.ctx` has animation players with events):
1. Area load: read `ARE.MiniGame`; when present, run with no controlled creature in the area (as the original does, 4.7), load the area normally (rooms, GIT sounds, scripts),
   then build the minigame object, set the input class to "minigame", hide the normal HUD, start `Music`, save nothing (`modulesave`).
2. Script VM: object arguments that are minigame ids (0..254) distinct from world objects, RunScript with `self` = a minigame object, `GetObjectByTag` for UTS sound objects (exists),
   `StartNewModule`, `SetGlobalFadeOut`, `PlayMovie`, `PlayRoomAnimation`, `BarkString`, `EffectVisualEffect` at a location (turret). Pop all arguments per prototype even where the
   original ignores them (`nAbsolute`).
3. Scene: named animations on a model with once / queued / overlay flags, the automatic `start/done/loop` events plus MDL events (`fire<N>`, `detonate`, `custom_`), node lookup by
   name, parenting of models to nodes (`modelhook`, `gunbankN`, `bullethookN`, `camerahook`), per-node world transforms every frame, AABB (`aabb` node) ray/point queries, particle emitters
   and lights inside models, a camera that follows a node, speed-blur and distortion post effects (render seam additions).
4. Input: an "MG" action set (keymap rows with `icminigame` = 1), analog axis events, mouse deltas with recentring (SDL relative mode).
5. Audio: positioned one-shots by resref (voice-stream style), looping stream music, the existing sound objects.

**Order of work**
1. `lib/minigame` data layer: ARE struct, followers/obstacles/gun banks as plain structs; a dump tool that prints all four areas (checks the tables in 1.4).
2. Swoop vertical slice on `m03mg`: rail following (speed -> playback rate), steering integrator + tunnel clamp, camera on `camerahook`, bank/gear animations, sound objects; run the
   original `heartbeat`/`onfire`/`oncreate` scripts to test the VM routines (about 25 routines).
3. Pads and obstacles: sphere sweep, AABB test, script callbacks, invulnerability, death default (`die`, sound, free); finish and return to the home module with globals.
4. Remaining routines (the other 72): straight field accessors, written against the structs; unit tests with small scripts.
5. Turret: aim integrator + mouse, rotating-model controllers, gun banks and bullets, enemy tracks (Bezier), enemy aim/fire, player damage and the HUD animation scripts, post-turret transitions.
6. Polish: speed blur, distortion, particles, pause menu, option "Reverse Minigame YAxis", Manaan wake model, saved-game rules.

**Rough size** (ctxlang lines, to be refined): minigame data + loaders 600; objects and per-frame step 1,000; steering, rail, bounds 300; collisions and damage 500; guns, bullets,
enemy aim 600; the 97 routines 800; input/camera/HUD glue 400; tools and tests 500. About 4,500 lines; the swoop slice (steps 1-4) is about 60% of it and playable on its own.
The riskiest parts are the renderer needs of step 3 of the hooks (emitters, node-attached cameras, animation events) and the exact hit geometry (4.7).
