# Swoop racing and the Ebon Hawk turret: survey for implementers

What the original game does for its two action minigames, found by reading the install's data
(ARE, LYT, MDL, NCS, UTS, 2DA) and the minigame code of `swkotor.exe` (the client side,
`0x0066b000`-`0x00675000` plus a few hooks). Everything is in our words; names starting `CSWMini`
are ours (the exe has only log strings such as `CSWTrackFollower:`), addresses are the Steam exe
after unpacking (see [README.md](README.md)). Confidence: **high** = read in code or data and
checked, **med** = read but a link is inferred, **low** = guess. Pazaak is a separate minigame
([pazaak.md](pazaak.md)); this page is the swoop races and the turret only.
The whole page was rechecked claim by claim on 2026-10-08 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check"
rests on static reading alone and is surprising enough to test before relying on it.

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
| `M12ab` (`m12ab`) | `M12ab.rim`, `_s` (no prefix) | Ebon Hawk gunner turret | see 1.2 | `k_pebo_sthdeath*` / `k_pebo_mgheart` -> `ebo_m12aa` etc.; `k_pebo_hawkhit` -> `EndGame` |

`ARE.MiniGame.Type`: 1 = swoop, 2 = turret (only values). Each module has one area. No saving: `modulesave.2da`
rows have `includeinsave 0`, `autosaveonenter no`; `loadscreens.2da` rows use images `LOAD_SWOOP` / `LOAD_TURRET`.
The server loads these areas like any other (rooms, GIT sounds, scripts); the GIT lists are almost
empty: swoop GIT = 17-18 sound objects (tags below); `m26mg` also 3 `n_repoff` creatures; `m12ab` has 10
`plc_invisible` placeables (anchors for explosion effects) and 1 sound (`Alarm01`). The area-load
message carries a "has minigame" byte (`CSWSArea::LoadAreaHeader` `0x00508c50` sets server area `+0x234` when
the ARE has a `MiniGame` struct; `FUN_0050aaa0` writes it into the message; the client reads it in
`CSWCArea::LoadArea` `0x00607610` and, when set, builds the 0xf0-byte minigame object (`0x00671c40`) at client
area `+0x264`) (high).

### 1.2 Entry, exit and the globals around them (high unless marked)

- **Swoop**: story scripts call `StartNewModule("<mgmodule>")` with no waypoint or movie (`k_pman_swoop42`/`44`
  first call `SetGlobalFadeOut(0, 0)`). Taris's `k_ptar_swooprun` adds 1 to `TAR_SWOOP_ACCEL` (a tuning number, see
  2.3) and starts the module from a 0.1 s `DelayCommand`. While the race runs, the heartbeat writes the running time
  every frame to `<TAR|TAT|MAN>_SWOOP_MIN/SEC/MSEC` (MSEC in hundredths), so they hold the time at the finish line;
  at the finish it fades out with `SetGlobalFadeOut` and returns to the home module (table above). Taris's heartbeat
  also sets `TAR_SWOOP_RUN` at the finish, and while racing compares the running time with `TAR_SWOOP_*_BEAT`: on race
  `Tar_SwoopRaceCounter` 5, once the running time is past the time to beat and `TAR_RACEMOVIE` is unset, it sets
  `TAR_RACEMOVIE`, fades out, plays movie `01g` and calls `EndGame(FALSE)` (2.3). The times are read back by
  `k_ptar_postswoop`, `k_ptar_racefirst` (Taris), `k_ptat_17ae_area` (Tatooine) and `k_pman_26b_area` (Manaan); what
  those do with them is not traced here. Manaan's `k_pman_swoop42` sets `MAN_OFFICIAL_RACE` first.
- **Turret**: `StartNewModule("m12ab", wp "", movie1 "11a")` from `k_ren_taris03` (sets `K_TURRET_SKYBOX` 5),
  `k_ren_unkturret` (15), `k_ren_turretload`, `k_ren_turretld02` (skybox left as is); `k_ren_levescape` sets 10 and
  plays movie1 `17a`, movie2 `11a`; `k_act_hk47simul` sets `K_HK47_SIMULATION` and starts it with no movie after a
  0.5 s `DelayCommand`. The galaxy map (`k_sup_galaxymap`, `ST_PlayPlanetToPlanet`) also starts it as a random
  ambush: on a plain planet-to-planet trip (vision already played) with `d100() > 50` it sets `K_RANDOM_MINI_GAME` and
  calls `StartNewModule("m12ab", "", <take-off movie>, "11a")`. `k_pebo_mgload` (module
  load) zeroes `ebo_num_fighters`, `ebo_turret_done`, `M12AB_END_SYNC`, `M12AB_START_SYNC`, `K_LAST_LOCATION`, and in
  the HK-47 simulation calls `EnableVideoEffect(1)`;
  `k_pebo_skybox` (area OnEnter) plays room animation 1 / 2 / 3 / 4 of room `m12ab_01a` for `K_TURRET_SKYBOX` 5 / 10 / 15 /
  other (the sky of that planet) after 0.2 s and barks strref 37107 "Incoming fighters!" after 1.5 s for 10 and 15,
  and for "other" unless `K_HK47_SIMULATION` is set (never for 5). When all six fighters are dead the
  script `ST_PlayPostTurret` logic (inlined in `k_pebo_sthdeath2..7` and `k_pebo_mgheart`, also script `k_ren_turret`)
  sets `K_TURRET_SKYBOX` -1 and picks the next module, first match wins: `K_HK47_SIMULATION` -> clear it,
  `StartNewModule("ebo_m12aa", wp "K_MINI_GAME")`; `K_RANDOM_MINI_GAME` -> clear it, `ebo_m12aa` with movies `11b` +
  a landing movie chosen by `K_FUTURE_PLANET` (15 `05_2a`, 20 `05_4a`, 25 `05_5a`, 30 `05_7a`, 35 `05_3a`, 55..80
  `LIVE_1a..6a`, else `NULL`), then `K_CURRENT_PLANET = K_FUTURE_PLANET`; `K_STAR_MAP` 0 and `K_KOTOR_MASTER` 10 ->
  set `K_SPACE_SKYBOX_ON`, `ebo_m12aa` wp `K_TARIS_DESTROYED`, movie `11b`; `K_STAR_MAP` 40 and `K_KOTOR_MASTER` 20 ->
  `ebo_m40ad`, movie `11b`; `K_STAR_MAP` 50 and `K_KOTOR_MASTER` 40 -> `STUNT_35`, movie `07_2`.
  The Hawk can be lost: `k_pebo_hawkhit` applies hits while its HP is still >= 2000 (it starts at 3000; fighter
  bullets do 10, so the 101st hit takes it to 1990) and ends the real sequence with `EndGame(TRUE)` on the next hit;
  in the HK-47 simulation that hit runs `k_ren_turret` instead.

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
| Music | none (empty) | none (a single space) | none (empty) | `mus_bat_sithbs` |
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
| Player gun banks | 1: `mgg_null`, bullet `mgb_null`, dmg 0, rate 0.01, target 3 | same | bullet `mgg_null`, rate 0, target 1 | 2: `mgg_turret`, bullet `mgb_ebonleft`, dmg 30, rate 0.3, speed 300, life 3, target 2, fire sound `mgs_ebon_fire` (bank 0), hit sound `mgs_sith_hit` |
| Enemies / Obstacles | 29 pads / 22 | 30 pads / 22 | 30 pads / 22 | 6 fighters / 1 |

Enemy entries: **pads** (swoops) = model `mgf_accelpad01`, `Trigger` 1, track `<mod>_mgt02..31`, Num_Loops -1, sphere
3 (m03) or 2, Hit_Points 1 (m17: 80, except the pad on `m17mg_mgt18`, 1), death sound `mgs_accelpad`, no scripts, no guns. **Fighters** (turret) =
`mgf_sithfighter`, tracks `m12ab_mgt02..07`, sphere 20, HP 100, OnCreate `k_pebo_sthcreate`, OnDeath `k_pebo_sthdeath2..7`,
death sound `mgs_sith_expl`, one bank: `mgg_null`, bullet `mgb_sithfighter`, dmg 10, life 2, rate 0.4, speed 200, target 1,
fire `mgs_sith_fire`, hit `mgs_ebon_hit`, Inaccuracy 0.01, Sensing_Radius 200, Horiz/Vert_Spread 70/70. **Obstacles** list model
names `<mod>_mgo01..22` (swoop; no scripts) or `m12ab_mgo01` (two emitters, `OmenEmitter03/04`). Obstacle entries
carry only 5 script slots (0-4, see 2.2). The LYT lists tracks under `trackcount` and obstacles under
`obstaclecount` (`lib/formats/lyt.ctx` parses both); the renderer's `CAurScene::LoadLayout` `0x0044f8d0` loads
each `trackcount` model at its LYT position, but the exe has no `obstaclecount` string, so that section is never
read; where obstacles get their placement is not traced here (med).

## 2. The script side

### 2.1 The 97 routines (`SWMG_*`; 520-521, 563, 583-668, 683-688, 717-718) (high for numbers, signatures and handlers)

Handlers: `CSWVirtualMachineCommands::ExecuteCommandSWMG_*` `0x005cb480`-`0x005cd280`, filled by
`InitializeMiniGameCommands` `0x005cd2c0` (41 handlers for 96 routines); `SetSpeedBlurEffect` `0x00543550` is filled
by `InitializeCommands` ([nwscript-routines.md](nwscript-routines.md)). Most share handlers that switch on the
command number. The player, camera, count and enemy/obstacle-by-index handlers reach the minigame object through
`0x005edb00` (client module `+0x48` area, then area `+0x264`); the per-object ones look the id up in the object
registry (`0x005edaf0` returns it, `0x0066bf30` indexes it); `SetSpeedBlurEffect` uses neither. Numbers in () =
unique shipped scripts using the routine (0 = unused by the game).

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
registry, `0xff` invalid: the lookup `0x0066bf30` rejects ids >= 0xff), `CONSTO 0` (OBJECT_SELF) is the object
whose script runs (every runner passes the object's id to `RunScript` with the valid flag 1), so a player script
playing "gear1" on OBJECT_SELF plays it on the player's models (high). `AdjustFollowerHitPoints` (`0x005cb990`) pops
only (object, int) and pushes no result; the 3rd argument `nAbsolute` is never read, so HP is always changed
relatively (high; the pad script passes -100 and kills 1-80 HP pads). The script still expects the declared int
result and discards one cell after the call, which is the unread `nAbsolute`, so the stack stays balanced; a
reimplementation that pops all three arguments must push a result. `GetPlayer/GetEnemy/GetObstacle` push `0xff`
(not OBJECT_INVALID) when there is no such object; `GetEnemy(i)` and `GetObstacle(i)` are 0-based (`0x00671570` /
`0x00671630`; `k_pebo_hawkhit` loops 1..count, so fighter 0 is skipped). `GetLastEvent` returns the string stored
at object `+0x10` by the last `custom_<x>` event (2.2); no shipped script calls it. `DelayCommand` queues only if
OBJECT_SELF exists in the server object array ([vm.md](vm.md)), and here OBJECT_SELF is a minigame id below 255;
whether the delayed calls in `k_pebo_sthdeathN` and `k_pebo_hawkhit` run therefore depends on some server object
happening to have that id (med, needs a runtime check). The swoop exit goes through `AssignCommand(GetFirstPC())`
and the turret exit is repeated by the module heartbeat, so both leave anyway.

### 2.2 Script slots and the "script replaces default" rule (high)

Each follower has 10 script resrefs, read from the ARE `Scripts` struct by `0x0066c740` (slots 5-9), which first
calls `0x0066c420` (slots 0-4); obstacles use `0x0066c420` alone (vtable `0x0075287c`), matching their 5-field
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
| 2 OnHitFollower `0x0066c2d0`, 4 OnHeartbeat `0x0066c0a0`, 0 OnCreate, 3, 9 | | script only; **OnHeartbeat runs every rendered frame** (it is called from the follower's per-frame update `0x0066e130`, which also counts down the invulnerability timer and moves the engine sound; the minigame update `0x006735d0` calls that for the player, every enemy and every obstacle, once per area render from `0x006097f0` under `CSWCModule::Render`) |

`OnFire` (7) is not run on the key press: pressing fire starts the gun model's `fire` animation (rate-limited by
`Rate_Of_Fire`), and the animation system's automatic **`startfire`** event runs the script (`FireGunCallback` `0x00673a40`,
branch for events starting "start"+"fire"); the same callback spawns a bullet on the MDL event `fire<N>` (med: no model
has a `startfire` event, so it must come from the animation system, the same way `donedie`, `starttrack` and `loop` do).
OnAnimEvent runs for events named `custom_<x>` (`0x0066fe50` stores `<x>` at object `+0x10`, then runs slot 3);
`GetLastEvent` then returns `<x>`. `loop...` events (same function) decrement `Num_Loops` unless it is -1 (forever),
restart the track speed and run OnTrackLoop on every loop event.

### 2.3 What the shipped scripts do (disassembled with `ncsdis.py`; 18 unique scripts) (high unless marked)

The module rims hold 24 unique NCS; the 18 counted here are the ones that call `SWMG_*` (the other six are `ggg`,
`reflux`, `k_pebo_mgload`, `k_pebo_skybox`, `k_pebo_sthcreate`, `k_pebo_mgheart`, described in 1.2 and below).

Swoop (`oncreate`, `heartbeat`, `onfire`, `obstacle`, `accelpad`). `heartbeat` differs per module in the globals and
the exit, and also: Taris has an extra countdown step and the `TAR_SWOOP_*_BEAT` / movie branch (1.2), Manaan plays
the bike-wake animations. `ggg` and `reflux` are attached to no slot: `ggg` reads `SoundObjectGetPitchVariance` of
the sound tagged `Wind`, `reflux` plays the one tagged `Reflux`; no swoop GIT has either tag (the sound tags are
`Engine01..05`, `Shift1..5`, `Penalty`, `Damage`, `Idle`, `PowerUp`, `PowerDown01`, `S1`, `Go`, Tatooine also
`sndpplwalla`), so every `Wind` call below acts on OBJECT_INVALID.

- `oncreate`: `MIN_RACE_GEAR` = -5 (m17mg, m26mg) or -6 (m03mg), the first countdown state; `SoundObjectPlay("Wind")`,
  `SetPlayerSpeed(0)`, plays `camshake1` (looping, overlay) and `gear0` (looping) on the player.
- `heartbeat` (**every frame**): `MIN_RACE_GEAR` is the state. At -5 it records the start time in
  `MIN_TIME_MIL/SEC/MIN/HOUR` and becomes -4; then, with the time elapsed since that record: > 0.1 s at -4: HUD `S3`,
  sounds `PowerUp` + `Idle`, -> -3; > 3 s at -3: sound `S1`, HUD `S2`, -> -2; > 4 s at -2: sound `S1`, HUD `S1`, -> -1;
  > 5 s at -1: sound `Go`, HUD `SGo`, the start time is recorded again (the race clock starts at Go), -> 0, and the
  player may shift (`onfire`). Taris starts at -6 (records the time, -> -5; `S3` at -5 -> -4) and adds a step: > 1 s
  at -4 -> -3 with `ShowTutorialWindow(0)`. Elapsed time is game-clock time: `GetTimeHour*120 + Minute*60 + Second +
  (Millisecond/10)/100`, plus 24 hours when the hour wrapped (valid because these modules have `Mod_MinPerHour` 2 and
  our minute is a real minute, see `lib/engine/routines/time.ctx`).
  Every frame the `Wind` volume is set to speed/4; while racing (state > -1) and `GetPosition(OBJECT_SELF).y` <= 3800
  it is set again to speed*127/200, the running time goes to `<X>_SWOOP_MIN/SEC/MSEC` and to the HUD as
  `MilSecOne/Ten`, `SecOne/Ten`, `MinOne/Ten` + digit (looping overlays such as `SecOne7`), and the speedometer plays
  `meter<n>`: n = progress through the current gear's band x 8, rounded and clamped 0..9 (gear 1 speed/60, 2
  (speed-60)/40, 3 (speed-100)/50, 4 (speed-150)/60, 5 (speed-210)/105), so 8 means the next shift is allowed; the
  current gear's `Engine0<g>` gets `SoundObjectSetFixedVariance(n/3 + 1)` and n is kept in `MIN_TENTH_GEAR`. Manaan
  also plays `WakeSpeed0<k>` (k = speed/70*10; `WakeSpeed09` from speed 70).
  Every frame, countdown included: `SetLateralAccelerationPerSecond(min(speed, 300))` (sluggish steering at low speed,
  none when stopped); `SetSpeedBlurEffect(FALSE)` below speed 150, else `SetSpeedBlurEffect(TRUE, (speed-149)/300)`;
  with k = clamp((speed-50)/150*5, 1, 5) rounded, it plays `camshake<k>` (looping) and, while y < 3800, `cDistL<k>`
  (looping overlay; a camera-distance level that follows speed, not a distance gauge).
  Finish: while racing with y > 3800 it removes `cDistL1..5` and plays `cDistL0`; the first time (state < 6):
  `PowerDown01` sound, min = max speed 0, acceleration = speed/3, tunnel pos and neg both set to
  (`GetPosition(OBJECT_SELF).x` - 100, 0, 0), HUD `downthrust` + `endloop` (looping), state 6, `meter0`, `Engine02..05`
  faded out over 0.5 s, `Idle` played, `SetGlobalFadeOut` (1.5 s wait, 1 s fade; Taris also sets `TAR_SWOOP_RUN`),
  then `AssignCommand(GetFirstPC(), DelayCommand(3.0, StartNewModule(<home>, <wp>)))`. Gear thresholds
  35 / 60 / 100 / 150 / 210 appear as constants.
- `onfire` (the gear shift, Space) reads the state g and the speed. g = -1 (the last second of the countdown): sound
  `Penalty` (`gui_error`), nothing else. g = 0: shifts to 1 with no speed check: MinSpeed 35, MaxSpeed 70,
  acceleration 20, tunnel pos (20,0,0) and neg (-20,0,0) (the only tunnel change). g = 1..4: shifts to g+1 only if
  speed > {60, 100, 150, 210}[g-1], then MinSpeed = that threshold, MaxSpeed = threshold x {2, 1.9, 1.5, 2},
  acceleration {8, 6, 3, 2}; a shift tried too early does nothing. g = 5 and the other countdown states: nothing.
  Taris multiplies each acceleration by `TAR_SWOOP_ACCEL`/10 (by 1 when the global is <= 0). On a shift it stores the
  gear, fades the previous loop (`Idle` for gear 1, else `Engine0<g-1>`) over 0.5 s, plays `Shift<g>`, starts
  `Engine0<g>` and plays HUD `gear<g>` (overlay, once) and `gear<g>l` (overlay, looping).
- `obstacle` (OnHitObstacle): if `MIN_RACE_GEAR > 0`: sound `Damage`, speed x 0.7, play `damage` (overlay). It never
  calls `SWMG_OnObstacleHit`, so the default death never happens.
- `accelpad` (OnHitFollower): if the player is not invulnerable (Taris: and not in gear 5): acceleration x 1.1, speed
  x 1.05. Then in every case: play `boost` (overlay on Taris), `StartInvulnerability(player)`, and kill the pad with
  `AdjustFollowerHitPoints(GetLastFollowerHit(), -100, -100)`.

Turret (`M12ab_s`): `k_heartbeat` (player OnHeartbeat) takes the z of `GetPlayerOffset()` as an int, wraps it into
0..359 and plays the HUD compass animation `HudRot_NNN` (zero-padded, looping) on the player. It also watches fighter 0:
each beat it stores `GetPosition(GetEnemy(0))` in `K_LAST_LOCATION`; once that is non-zero and the fighter has moved
since the previous beat, `M12AB_START_SYNC` becomes 1, and the next beat starts the six looping `SithLoop02..07`
radar animations on the player and sets it to 2.
`k_pebo_sthcreate` increments `ebo_num_fighters`; `k_pebo_sthdeathN` calls `SWMG_OnDeath()`, plays `SithLoopNNd`
(looping; blip off), decrements the counter and at <= 0 sets `ebo_turret_done` and runs the leave logic (1.2) from a
2 s `DelayCommand` (see 2.1). `k_pebo_hawkhit` (OnDamage, high): while `M12AB_END_SYNC` is unset and the HP before the
hit is >= 2000 it calls `SWMG_OnDamage()` (applies the damage), plays HUD animation `Health<n>` (looping;
`n = (HP-2000)*12/1000 + 1` after the hit, `Health0n` below 10) and starts sound `Alarm01` when n is 3. A hit that
arrives with HP already below 2000 is not applied: it sets `M12AB_END_SYNC` (later hits are ignored), sets the HP of
`GetEnemy(1..count)` to 2000, stops the alarm, plays `Health00`, applies visual effect 3003 at the `Invisible` anchor
(0 s delay) and at its own location (2 s), `SetGlobalFadeOut` (3 s wait, 1 s fade), `DisableVideoEffect`, then
barks strref 38465 "We're hit! Damage is critical! The Hawk won't hold!" and calls `EndGame(TRUE)` after 4 s, or in
the HK-47 simulation runs `k_ren_turret` (`ExecuteScript`). `k_pebo_mgheart` (module heartbeat): when
`ebo_turret_done` is set it runs the leave logic after 1 s, calls `DisableVideoEffect` and clears `ebo_num_fighters`
and `ebo_turret_done`.

## 3. Data the engine needs

- **2DA**: none of its own. Touched: `loadscreens` (`LOAD_SWOOP`/`LOAD_TURRET`), `modulesave`, `globalcat` (`M12AB_START_SYNC`
  number, `M12AB_END_SYNC` boolean), `keymap` input class `ICMiniGame` (rows `MGshoot` Space action 217, `PauseMinigame` Esc
  253, `Pause` 224, `ToolTips` 225, `MGActionUp/Down` W/S = event 282, `MGActionLeft/Right` A/D = 283, arrows = 285/286).
- **Models** (all in `models.bif`; high): player tracks `m03mg_tr01`, `m17mg_mgt01`, `m26mg_mgt01` (a root dummy + `modelhook`, m03 also
  `Camera01`, m17 a mesh; one `track` animation: **a straight 2-key translation of `modelhook` along +Y** from 0 to 4980 (m03) or
  4699.8 (m17, m26) over 48 s, identity rotation; the node's static offset is (5,0,2) / (100,100,2.66)) and pad tracks `_mgt02..31` (static `modelhook` only); the turret fighters' tracks `m12ab_mgt02..07` are Bezier splines
  (54 keys in `mgt02`) of 43.03 / 48.80 / 51.30 / 61.70 / 84.10 / 54.60 s; the HUD radar animations `SithLoop02..07` of `mgf_hud01` have the same
  lengths, so the blips replay the fighters' paths. Obstacles `m03mg_mgo01..22`: dummy + aabb node `hitbump` + trimesh, animations `Ready` (4 s) and
  `hit` (`m17mg_mgo*` have only the `hitbump` aabb; the turret's `m12ab_mgo01` is two emitters with no hit node, so nothing collides with it).
  Pad `mgf_accelpad01`: aabb (`hitbump`, unused for pads) + 2 meshes, animations `Ready_01`, `hit`, `die` (7.63 s).
- **Node and animation names the engine or scripts look up** (high): `modelhook` (anchor of every rail, attach point of the
  vehicle models), `camerahook` (the camera is attached to this node of the player's camera/HUD model), `gunbankN` (where gun
  models of bank N are attached), `bullethookN` (bullet spawn on the gun model), `hitbullet` (aabb node a bullet is tested
  against: `v_superbike`, `mgf_ebonhawk`, `mgf_sithfighter`), `hitbump` (aabb node of an obstacle the player is tested against),
  `track`, `Ready_01`/`ready`, `fire`, `damage`, `die`, `explode`, `hit`, `boost`, `Bank{L,R}_01..10` (bike lean, below).
  Event names: `fire<N>`, `detonate` (emitters), automatic `start<anim>`, `done<anim>`, `loop...`, `custom_<x>`.
- **Player models** `v_superbike` (83 nodes: 64 meshes, 13 emitters, `gunbank0`, a `hitbullet` aabb; 35 animations: `Gear0..5`, `Gear1l..5l`, `BankL_01..10`,
  `BankR_01..10`, `damage`, `downthrust`, `endloop`, `boost`), `v_sbikewake` (`WakeSpeed00..09`, Manaan), `v_damagetat`/`v_damageman`
  (emitters, `damage` with `detonate` events), `lmg_distort` (heat distortion: `Gear0..5`, `Gear1l..5l`). **HUD = camera model** `m17mg_camera`
  (104 nodes, 105 animations: `gear0..5(l)`, `meter0..9`, `MilSecOne0..9`, `MilSecTen..`, `SecOne..`, `SecTen..`, `MinOne..`, `MinTen..`,
  `camshake1..5`, `S1..S3`, `SGo`, `cDist1..5`, `cDistL0..5`, `boost`, `die`, `damage`; one-frame animations select digits), node `camerahook`.
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

The minigame lives in the **client** (`CSWC*`): `CSWCArea` (`+0x264`) owns it; the server knows only the flag (the area-load message's
"has minigame" byte, modules.md). Created in `CSWCArea::LoadArea` `0x00607610`: `FUN_00671c40` builds the minigame object (ours: `CSWMiniGame`,
0xf0 bytes, vtable `0x00752914`, one slot = destructor; it holds the area's ARE as its own resource, a looping streaming source for the music at
`+0x1c`, defaults FOV 65, near 0.1, far 100, integrator mode `+0xac` = 1); then every LYT track is registered (`0x006720c0`: name + position,
a repeated name is kept once), every LYT obstacle is instantiated (`0x00672240`: its model placed at the LYT position, animation `ready`, an
obstacle object `0x00670640`, vtable `0x0075287c`, 0xb4 bytes); then `FUN_006723d0` reads `ARE.MiniGame`
(clip planes `0x00670b50`, FOV `+0x70`, `Type` `+0x80` (only 1 or 2 is stored), `MovementPerSec` `+0x74` default 6/90 for type 1/2, `LateralAccel` `+0xbc` default 60, `Bump_Plane` `+0x78`
0..3, `DOF` `+0x7c` 0..7, `UseInertia` `+0x94`, `DoBumping` `+0x95`, `Music` `+0x96`, mouse axes `+0x84/+0x88` 0..3 with sign = flip), creates the
player (`0x00671820` swoop, `0x006719d0` turret with camera model; any type other than 2 takes the swoop path) and each enemy (`0x00671e40`), and matches the
`Obstacles` entries to obstacle objects by `Name` (a search of the 255-slot registry by object name) to read their scripts. A missing `Player`
struct, `Models` list or `Track` (or, for type 2, `Camera`) makes `0x006723d0` return 0 and the area load fail. A second path, `0x00605e50`, rebuilds the
minigame from scratch on an existing area (new object, the tracks and obstacles copied over, the ARE read again, camera attached, race restarted; reached
only through the callback `0x0060aa40`, caller not traced; med).
Class tree (all objects take a slot in the 255-slot registry; vtable, constructor):

| Class (ours) | Ctor / vtable | Notes |
|---|---|---|
| `CSWMiniObject` | `0x0066c540` / `0x00752424` (purecall) | base: kind `+4` (1 player, 2 enemy, 3 obstacle), id (`+8`), dead flag byte `+0xc` (freed at the start of the next frame), name, script slots 0-4 read by `0x0066c420` (OnCreate, OnHitBullet, OnHitFollower, OnAnimEvent, OnHeartbeat; stored in the subclasses), last bullet hit `+0x1c..+0x34` (damage, target mask `+0x2c`, collision sound `+0x34`), shooter of that bullet `+0x4c`, last follower hit `+0x50` (both 0xff = none), `As{Follower,Player,Enemy,Obstacle}` slots (5-8), per-frame update slot 9 |
| `CSWMiniObstacle` | `0x00670640` / `0x0075287c` | 0xb4 bytes: model `+0x60`, 5 script slots at `+0x64`; update = OnHeartbeat only (`0x0066c0a0`) |
| `CSWTrackFollower` | `0x0066dee0` / `0x007524c8` | rail follower: track model `+0x64`, models list (`+0x68/6c`, 8-byte entries ptr+rotates), gun banks (`+0x74`), 10 script slots at `+0xa4` (5-9 read by `0x0066c740`), flags `+0x88` (bit 0 started, bit 1 dead), sphere radius `+0x84`, HP `+0x8c`/max `+0x90`, `Bump_Damage` `+0x94`, speed `+0x98`, invulnerability `+0x9c/a0`, loop count `+0x80` (Num_Loops, default 1), engine sound `+0x144`, last obstacle hit `+0x170`, pending HP change `+0x19c`, target-class bit from vtable slot 15 (player 1, enemy 2); update slot 9 = `0x0066e130` |
| `CSWMiniPlayer` | `0x0066eb50` / `0x007525f0` | 0x250 bytes: offset vector `+0x1c4`, bank level `+0x1d0`, bumped-this-frame flag `+0x1d4`, min/max/accel `+0x1d8/dc/e0`, tunnel `+0x1e4..0x204` (Pos, Neg, Infinite), origin `+0x208` (= `Start_Offset`), target offset `+0x214`, camera model `+0x220` (turret) |
| `CSWMiniEnemy` | built in `0x00671e40` / `0x007528a8` | 0x1a4 bytes; fighters and pads; `Trigger` flag byte at `+0x1a0` (read by `0x006705f0`) |
| gun bank, player | `0x006746d0` / `0x00752ae4` | slot 0 `0x006743b0` makes the gun model with a fixed gun controller (`0x006dadf0`, type 0xaaad, 0x54 bytes, vtable `0x00757f70`, fire `0x006daec0`) |
| gun bank, enemy (aiming) | `0x00674860` / `0x00752af0` | slot 0 `0x00674530` makes the gun model with an aiming controller (`0x006db590`, type 0xaaaa, 0x7c bytes, vtable `0x00757fdc`, update `0x006db3d0` over `0x006db180`) aimed at the player |
| bullet controller | `0x006dafe0` / `0x00757f98` | type 0xaaab, 0x40 bytes (the export calls it `CSWCTurretCamera::CSWCTurretCamera`, a wrong name): bullet data `+0x14..+0x3b`, shooter `+0x3c`; update `0x006db090` moves the bullet along its +Y at `Speed` and frees it when `Lifespan` runs out |

### 4.2 Per-frame flow (high)

`CClientExoAppInternal::ProcessInput` `0x006227e0`, when the area has a minigame: only when the client has no controlled creature it reads the
input events and calls `0x00670fb0` (steering integrator), for the turret also `0x00671020` (mouse); with or without one it then calls `0x006710e0`
(player step + bank level). The 3D frame (`CSWCModule::Render` -> `FUN_006097f0` -> `0x006735d0`) first frees the objects whose dead flag is set,
then updates the player, every enemy and every obstacle through vtable slot 9 (followers: `0x0066e130`, which runs OnHeartbeat, counts the
invulnerability timer down and moves the engine sound; obstacles: OnHeartbeat only), places the pending bullet explosions, and then, **only once the
race has started** (player flag `+0x88` bit 0), runs the collision step `0x006732f0`: bullets, the player against obstacles, then up to **3 passes**
of player-vs-follower resolution. Last it finds the room the player is in for the scene. Time step = frame `dt` (no fixed step).
`SetInputClass(1)` (minigame) attaches the camera (`0x00671670`), switches HUD mode 2, and **starts the race** (`0x006714e0`): for the player and each
enemy `0x006701c0` hooks the event callback `0x0066fe50` on every model, plays `Ready_01`, plays `track` on the track model at `speed * 0.01`
(the player also gets the `ReportKey` callback, below), sets flag bit 0 and starts the engine sound; then it starts the music (looping streaming
source).

### 4.3 Movement model (high unless marked)

- **Along the rail**: the vehicle is parented to node `modelhook` of the track model; the engine plays the `track` animation of the track model with
  playback rate `speed * 0.01` (`0x0066c870`; speed 100 = real time). So distance along the track = `speed/100 * 103.75 u/s` on m03mg (4980/48), 97.9 u/s on m17/m26.
  Speed moves linearly toward `MaxSpeed` (up or down) at `Accel` per second (`0x0066d640` start), skipped in the frame after a bump (`+0x1d4`); it is
  not held above `MinSpeed`. `Accel = (Max-Min)/Accel_Secs` from the ARE (`Accel_Secs` 0 gives `Max-Min`, a negative or absent one leaves accel at 0;
  the data's Min = Max = 0 gives 0, scripts set it); `Minimum_Speed`/`Maximum_Speed` are taken only when >= 0. `SetPlayerMinSpeed/MaxSpeed/Accel`
  ignore negative values; `SetPlayerSpeed` takes any value and goes straight to `0x0066c870`. The default player (before the ARE) has speed/min/max 100, accel 0, HP 100.
- **Steering** (`0x00670fb0`, `0x00670a90`): input `u` per axis in [-1, 1] (keyboard events sum clamped: horizontal = events 283 + 286, vertical = 282 + 285;
  swoop: `u = (horizontal, 0, 0)` then y,z negated; turret: raw `(horizontal, 0, vertical)` becomes `(-vertical, 0, -horizontal)`, option "Reverse
  Minigame YAxis" (client options `+8` bit 3) negates the vertical axis first). The integrator mode is the minigame's `+0xac`, set to 1 by the constructor
  and never changed (it is **not** the ARE's `UseInertia`): in mode 1 the lateral state is integrated with a 4th-order Runge-Kutta step per frame, state `(v, x)` per axis:
  `dv/dt = L * u - (L / M) * v`, `dx/dt = v` with `L` = LateralAccel, `M` = MovementPerSec (stage inputs: previous, mean, mean, current).
  Terminal speed `M*u`, time constant `M/L` (swoop 0.33 s at 300; the script lowers `L` at low speed). The alternative mode (`+0xac = 0`) is `x += M*u*dt`.
  Turret mouse (`0x00671020`): events 0x17/0x18 (the vertical one negated, and negated again by the YAxis option) divided by 20 (global `0x007a232c`), clamped to +-1, `x[axis] -= value * M * dt` on the axis named by
  `Mouse.AxisX/Y` (1..3 = x,y,z; a negative stored value = flipped), applied to the new position state directly, then the pointer is recentred each frame unless the game is paused.
- **Offset and bounds** (`0x0066d640` end, `0x0066cb40`): new offset = old + (new x - old x); each axis of the offset is clamped to
  `[Neg + origin, Pos + origin]` unless its `TunnelInfinite` flag is set, in which case turret (type 2) angles wrap (above 359 subtract 360, below 0 add 360)
  and swoop axes are left free. Only the offset is clamped: the integrator's own `x` and `v` keep running, so input against a wall builds velocity
  that has to decay before the vehicle moves back (med, needs a runtime check). The offset is written into the node-follow
  controller (types 0x3ea/0x3eb, fields `+0x3c..+0x44`) of every model flagged `RotatingModel` (and of the turret camera model when its controller is 0x3eb), so those models are displaced (swoop) or rotated
  (turret, degrees) relative to `modelhook`; the Hawk model (flag 0) stays put (med; the controller code itself was not read). "Walls" are only these bounds; there is no
  track-mesh collision.
- **Bank animation** (`0x006710e0`, `0x0066ce60`, swoop only): a second smoothed value `s` (minigame `+0x8c`) follows the horizontal input: while the input
  pushes the same way as `s` and |s| < 0.25, `s += dt*u`, capped at +-0.255; input the other way (or `s` at 0) restarts it at `dt*u`. On release, on the
  first frame only, an |s| in [0.23, 0.235), [0.17, 0.175), [0.1, 0.105) or [0.042, 0.047) snaps to 0.235 / 0.175 / 0.105 / 0.042; then |s| falls by
  `dt` a second to 0. Level = 0 if |s| < 0.021 and 1..10 by thresholds 0.021, 0.042, 0.071, 0.1, 0.135, 0.17, 0.2, 0.23, 0.24, 0.25, signed like `s`;
  when the level changes the engine plays `Ready_01` for 0 and `Bank<L|R>_<NN>` otherwise on the player's models: **R for a positive level, L for a negative one**
  (which key gives a positive `s` was not settled, low).
- **UseInertia in `0x0066d640`** (low): when the ARE's `UseInertia` is set and the race has started, the track's `ReportKey` callback (`0x0066dd60`) collects the
  position and orientation keys the `track` animation passes (two lists); each frame the engine merges them by time, drives `modelhook` from them, and for
  each time slice adds to the lateral **velocity** the change of the rail's own velocity (previous minus new, `0x0066cd30`), with its component along the
  `Bump_Plane` axis of the rail's orientation removed (`0x00670bb0`: 1..3 = the x/y/z axis, 0 = none), turned into the rail's frame and scaled by 1.0
  (`0x007a2488`). On the shipped straight swoop tracks the rail velocity is constant, so only the first slice (rail velocity 0 -> 103.75) adds anything,
  along the track axis, where the tunnel clamp absorbs it (needs a runtime check). A global at `0x007a2490` (100.0, never written) forces the speed when
  it differs from `0x007a2494`; it never fires.

### 4.4 Collisions and damage (high for structure, low for the tests' exact geometry)

- Order in `0x006732f0`: every live bullet against the player, then each enemy, then each obstacle (the first hit removes the bullet); then, while the
  player is not dead (flag bit 1), the player against every obstacle (`0x0066e6b0`), then player against followers (`0x0066eda0`) up to 3 times, stopping
  at the first pass with no non-trigger hit. Only the **first** pass runs scripts, damage and animations; later passes only push out.
- Player vs followers (`0x0066eda0`): for every follower that is a **trigger** (pad) or when `DoBumping` (all data: 0), a swept test (`FUN_004abdd0`): the
  segment of the two models' relative position over the frame (model slots `+0x6c` -> `+0x64`) must pass within `follower sphere + player sphere` of zero; with no
  relative motion there is no hit. A follower without models ends the loop. Non-trigger hit: push-out to the radius sum + 0.1 away from the follower's position
  projected onto the plane through the player normal to the `Bump_Plane` axis (averaged over the hits, then clamped by the tunnel bounds and applied to the models).
  On the first pass, a follower that is not invulnerable plays `damage`/`Ready_01` (its guns `damage`/`ready`), loses the player's `Bump_Damage` (0 in all data)
  through OnDamage and starts its own invulnerability; both get each other as `GetLastFollowerHit` and run OnHitFollower. Pad hit: on the first pass only the two
  OnHitFollower scripts run (`0x0066c2d0`), after recording each as the other's last follower hit; no push-out.
  After a non-trigger bump with the player's invulnerability timer at 0 the engine resets speed to MinSpeed (restarting `track` at that rate), starts the timer
  from `Invince_Period`, and on the first pass plays `damage`/`Ready_01` (guns `damage`/`ready`), applies **minus the largest `Bump_Damage` of the bumped
  followers** to the player through OnDamage and sets the bumped flag `+0x1d4`.
- Player vs obstacles (`0x0066e6b0`): the obstacle model's aabb node `hitbump` is tested (model vtable `+0x88`, the test the bullets use) against the
  segment the player's first model moved along this frame; there is no invulnerability check. Hit -> the obstacle becomes the player's last obstacle hit
  (`+0x170`), the player's OnHitObstacle (slot 8; default: die) runs, then the obstacle gets the player as its last follower hit and its own OnHitFollower runs.
  The shipped script slows the bike; there is no engine-side bounce.
- Bullets (`0x0066d4e0` for followers, over each of their models -> `0x006730a0`; obstacles directly): a bullet never hits the follower that fired it; the
  bullet's segment over the frame is tested against the target model's `hitbullet` node. On a hit the target records the bullet's data (damage, target mask,
  collision sound) and its shooter (`+0x4c`), and `0x0066c190` runs its OnHitBullet (slot 1); without a script the default subtracts the bullet damage if the
  bullet's `Target_Type` bit matches the target's class (1 = player side, 2 = enemies, 3 = both; values with any bit of 0x11111110 are refused when set,
  `0x006746d0`, `0x00673880`), so obstacles never lose HP, and plays the collision sound. The bullet plays `explode` (placed at the hit point, freed on
  `doneexplode`) or, without that animation, is deleted at once.
- `SWMG_StartInvulnerability`, `GetIsInvulnerable`: one timer per follower (`+0x9c`, invulnerable while > 0, counted down in `0x0066e130`); `Invince_Period` is its length.

### 4.5 Guns, bullets, enemy aim (med)

Gun banks are `Gun_Banks` entries; the gun model is attached to node `gunbank<BankID>` of the vehicle model (`0x0066e490`). The player's banks are fixed guns, every
enemy bank is an aiming gun (4.1). Fire pressed (`HandleInputAction` case 0xd9, once per
key press: the `MGshoot` row is not repeatable; ignored while paused -> `0x0066dc50` -> controller `0x006daec0` on every gun model of every player bank): if the gun's cooldown is 0, cooldown = `Rate_Of_Fire`, play `fire`
then `ready` on the gun model and the fire sound. The `fire<N>`
event spawns the bullet model at `bullethook<N>` (`FireGunCallback` `0x00673a40`), with direction from the gun orientation (player: straight along the hook; enemy: toward the
player's first model plus its `Target_Offset`, with a random error when `Inaccuracy` > 0: a random unit vector times `Inaccuracy` times the **player's `Sphere_Radius`**
(not the distance), its component along the line of fire removed; 0.01 x 40 = 0.4 units for the fighters), speed `Speed`, lifespan `Lifespan`; the `startfire` event
runs the owner's OnFire (`0x006738d0`). Enemy gun controller (`0x006db180`, `0x006db3d0`, each frame): if the player is within
`Sensing_Radius` it turns the gun toward it, limited to +-`Horiz_Spread` / +-`Vert_Spread` degrees; it fires by itself (`fire`, `ready`, fire sound) only while inside both limits and cooldown is 0. Player's
bullets with damage 0 (swoop) are harmless dummies that only trigger the `fire` animation and OnFire.

### 4.6 Camera and view (med)

The area camera (FOV, near, far from the ARE) gets a controller (`FUN_0049fb10`, 0x3c bytes) that makes it follow the world transform of node `camerahook` in the first of the
player's models that has one (swoop `m17mg_camera`; searched in list order, then the track model), or, for the turret, is attached directly (camera vtable `+0x74`) to node
`camerahook` of the dedicated camera model `Player.Camera` (`m12ab_camera`, kept at player `+0x220`) (`0x00671670`). Whether that controller smooths was not checked. `CameraRotate` says whether
the camera model turns with the player's rotating models (it is hooked to `modelhook` with the turret's rotation mode, else with none; `0x0066d030`). The speed blur
(`0x0044f0a0` on, `0x0044f0b0` off, `0x0044f130` ratio in `0x0078d43c`, 0.98 at start; `SWMG_SetSpeedBlurEffect` passes 0.75 when the script gives no ratio) and the heat distortion model are
renderer features. The HUD models are children of the camera model, so they follow it.

### 4.7 Open questions

- Exact bullet and obstacle hit geometry: both call the model's vtable `+0x88` test with the named aabb node, the segment between the moving model's positions from
  slots `+0x6c` and `+0x64`, a 0 argument (perhaps a radius) and an output point; what `+0x88` computes was not read. The follower test is settled (4.4).
- `DOF` is read (`+0x7c`) but no use was found; the integrator mode `+0xac` is never set to 0 (static search), so its `x += M*u*dt` branch is dead.
- How the server omits the party in minigame areas (no controlled creature) and how `GetFirstPC` behaves there; whether a mouse button also fires the turret (only Space is bound,
  and `HandleInputAction` 0xd9 is the only fire path found).
- Which key gives a positive lateral value (`BankR`); the per-vehicle sound `Sounds.Engine` (empty in all data) is started with the race (`0x006701c0`) and kept at the first
  model's position by `0x0066e130`.
- Whether `OnTrackLoop` ever fires: `0x0066fe50` runs it (and decrements `Num_Loops` unless -1) for any model event named `loop...`; the `track` animations carry no events,
  so it depends on whether the animation system raises one automatically (`Num_Loops` 1 on Taris/Tatooine). The finish is script-driven by position, not by the loop event.

## 5. Recommended implementation plan (ctxlang)

**Status**: most of the original plan exists. `lib/minigame`: `area.ctx` (the ARE struct), `rail.ctx` (the `track` animation sampled into transforms),
`run.ctx` (objects, speed, steering, pads and obstacles, script events), `turret.ctx` (aim, guns, bullets, enemy fire, hits), `racer.ctx` (a test bot);
`game/minigame*.ctx` (scene, camera on `camerahook`, `gunbank<id>` attachment, animations, music, pause); `lib/engine/routines/swmg.ctx` (the `SWMG_*` routines);
`lib/formats/lyt.ctx` parses tracks/obstacles, `lib/mdl/anim.ctx` plays animations with events.

**Where ours differs from the original** (from this check; change only after a runtime comparison):
1. Steering: the swoop uses the closed-form integrator only when the ARE's `UseInertia` is set, the original always (its switch is `+0xac`); at a tunnel wall ours
   zeroes the velocity, the original clamps only the offset (4.3). Speed is held at `MinSpeed` by ours, not by the original. No bike lean (`Bank<L|R>_NN`, 4.3).
2. Pads: ours tests the distance between the two positions each frame; the original sweeps the relative motion over the frame (no motion, no hit) and also runs the
   pad's own OnHitFollower (4.4). With `DoBumping` ours only runs the scripts: no push-out, damage or speed reset (no shipped area sets it).
3. Obstacles: ours tests the player's position against the model's bounding box, skips the test while the player is invulnerable and starts invulnerability on a hit;
   the original tests the `hitbump` node against the player's motion, never checks or starts invulnerability, and also runs the obstacle's OnHitFollower (4.4).
4. Enemy aim error: ours scales it by the distance (`Inaccuracy * distance * random`); the original by the player's `Sphere_Radius` (4.5).
5. Obstacles' OnHeartbeat is not run (the swoop obstacles have no scripts).

**Still open**: the pause menu (Escape toggles pause, `pause.gui` is not shown); the speed blur (`SWMG_SetSpeedBlurEffect` is recorded in the run, the view
does not draw it); the hit geometry of 4.7.
