# Playthrough log: the Leviathan

The capture of the Ebon Hawk by Saul Karath's Leviathan, the prison break, the bridge, the hangar and Malak, the escape and the talk with the
party, played headless, step by step, checked against the original with logs and screenshots, from a crafted arrival after Korriban: a
Jedi of level 14 (a soldier of 7 who became a Jedi Guardian of 7), Bastila and Carth with the player, the fourth Star Map found. The method is
[playthrough.md](playthrough.md)'s and [playthrough-korriban.md](playthrough-korriban.md)'s; the scripts are in
`kotor/tools/playthrough/leviathan/`.

**Played:** the galaxy map's flight from Korriban and the take-off movies, the capture (`stunt_16`, `ebo_m40aa`), Carth's talk about Saul
Karath and the choice of who escapes (Mission), the Sith commander and Saul Karath's interrogation of Bastila (`lev40_saul403`), the cell, Mission
(the player's body for a while) slicing out and opening the cells at the detention computer, the party freed (`lev40_bast400`), the equipment locker,
the elevator, the command deck (Sith troopers, Dark Jedi, an assault droid), the bridge corridor with five Sith Elite Troopers, the bridge, Saul
Karath's two scenes (`lev40_saul402`: the surrender offer and the dying whisper to Carth), the bridge computer that opens the docking bay doors,
the elevator to the hangar, the hangar (Dark Jedi, Malak's talk and the Revan revelation, the flashback movie, Bastila's stand against Malak),
the Hawk's turret escape (`m12ab`), and aboard the Hawk the talk with Mission, Zaalbar, Canderous, Jolee, HK-47, T3-M4 and Carth; the Hawk
lands again and the galaxy map offers Manaan. 0 script faults in the 9 parts.

**Stopped** on the Hawk after the Leviathan (`ebo_m12aa`, the checkpoint `hawkpost`): the galaxy map is open and the next planet is Manaan (the
fifth Star Map). The Unknown World starts from it: [playthrough-unknown-world.md](playthrough-unknown-world.md). To resume:
`CKPT=hawkpost sh kotor/tools/playthrough/leviathan/run.sh NAME 10 2000` opens the map (part 10 is a look, not part of the chain).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_lev.exe
sh kotor/tools/playthrough/leviathan/all.sh [FIRST_PART]      # the chain, about 3 minutes; each part loads the checkpoint the one before saved
CKPT=deck sh kotor/tools/playthrough/leviathan/run.sh NAME 04 FRAMES [FRAME:SHOT]...      # one part from its checkpoint
sh kotor/tools/playthrough/korriban/sum.sh kotor/out/pt/NAME.log [FIRST_FRAME]             # the story lines of a log
python kotor/tools/py/stage_audit.py kotor/out/pt/lN.log                                   # the staging audit
```

Logs are `kotor/out/pt/lN.log`, checkpoints `kotor/out/pt/lev_ckpt/NAME` (a part's `save` or `savewhen` line and `ckpt.sh`), pictures
`kotor/out/pt/lN_end.png` (30 frames before the end of each part). Everything runs with `FAST=1`, `LOG=dialog,combat`, the options file
`leviathan/play.ini` ("Auto Level Up NPCs" on, so a companion made by `SpawnAvailableNPC` takes the levels the party's XP pool gives it, as
a player's would have taken them) and `all.sh` checks after each part that the log holds the line the part was written to produce and that it
saved. The helpers: `sh kotor/tools/playthrough/objs.sh MODULE [CKPT_DIR]` (the creatures, doors, triggers and placeables of a module), `nss.sh`
(the NWScript sources the install ships), `python kotor/tools/py/dlgtree.py --module M RESREF` (a conversation as a tree; `--module` picks
the copy a module's rim holds: `lev40_carth` is three different talks) and `ncsgrep.sh`/`ncsinfo.sh` for the scripts.

### The crafted state (part 1)

- `--module korr_m33aa`, the setup of `korriban/01_arrival.txt` and the end of the Korriban chain: a Jedi of level 14, 104,970 XP (`ui xp` first, so the
  party's pool holds it and a companion made later catches up), alignment 97, Bastila a Sentinel and Carth a soldier of level 14, every companion
  available. **The player is a soldier of 7 and a Jedi Guardian of 7** (`ui stat class 0 / level 7 / class2 3 / level2 7`, then the hit points set again):
  the scripts of the take-offs read `GetLevelByClass(CLASS_SOLDIER)` for the player's body (`k_tall`, `k_medium`, `k_small`: the cut scene `stunt_00`
  has no starting entry for a pure Jedi and the story hung in it).
- The fourth Star Map and its consequences as `UT_StarMap1VariableSet` leaves them: `K_STAR_MAP 40`, `K_CAPTURED_LEV 5`, `K_SWG_BASTILA 99`,
  `K_KOTOR_MASTER 20`, `K_CURRENT_PLANET 30`, the planets of the map (`ui planet`).
- The party boards the Hawk through the strip `k33_trg_ebonhawk` (`warpxy 107,183 party`); `k_pebn_pophawk` takes the companions off the party and puts
  them in the ship, as the original does, so the player walks to the galaxy map alone (`ui goto GalaxyMap`, `use GalaxyMap`, then the clicks on
  `LBL_Planet_Manaan` and `BTN_ACCEPT`).
- Replies are a queue (`ui replies ~words ... default 1`); the chain's choices are listed below. Walks across a module are the bot's (`ui bot route
  TAG... / @TAG / on / god on`); the fights, the doors, the triggers, the elevator consoles and the conversations are the game's.

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | The galaxy map on the Hawk, Manaan picked, "Travel": the take-off movies (`05_7c`, `08`), `stunt_16` (the Leviathan pulls the Hawk out of hyperspace: Bastila and Carth on the bridge, "It's the Leviathan. Saul Karath's vessel. My old mentor."), movie `17`, the Hawk held in `ebo_m40aa` | works | `01_capture.txt` |
| 2 | Carth (`lev40_carth`, 38 entries): his hatred of Saul, Bastila's "Talk of an escape is somewhat premature", "who has the best chance to avoid capture": the player's replies pick **Mission** (journal `lev_captured` 1: "Your only hope of escape rests on Mission's slender shoulders"; Zaalbar objects; "This could work, and it's not like we have much choice"). The other replies (T3-M4, Jolee, Canderous, Juhani, HK-47) lead to entries 2-6 and the same jump | works (Mission only) | `01_capture.txt` |
| 3 | The prison block (`lev_m40aa`): the Sith commander and the troopers report (`lev40_sithcomman`) | works | `01_capture.txt` |
| 4 | Saul Karath (`lev40_saul403`, 122 entries): Carth's oath, Bastila's defiance, "History? What are you talking about?" (the hint of Revan), the torture of Bastila over three questions (the replies take the first answer: "Don't hurt her, I beg you.", "Jedi Academy? I have no idea...", "No, you're lying!", "I won't betray the Jedi."), "Dantooine is an empty graveyard now", the cells and Bastila's and Carth's talk in the dark (the cut scene's voices, the lip sync, the wide shots at 10 m) | works | `01_capture.txt` |
| 5 | **SwitchPlayerCharacter**: after the interrogation the guard takes Mission to her cell (`lev40_mission`: "Come on, girlie. Into the cell."): the player is now **Mission** (the HUD, the camera, the sheet, `GetFirstPC`), the Jedi parked, Carth and Bastila put away; Mission's quips ("Who designed those Sith uniforms anyway? A blind Rodian with a sick sense of humor?"), the stolen keycard, the picked lock; the insane Rodians in the next cells attack the doors and Mission (unarmed: her gear is in the locker). The routine was a stub that logged "not implemented": the guard talked alone and the one-line talk ended | fixed 0919a56 | `01_capture.txt` |
| 6 | The detention computer (`lev40_detcompdlg`, "Unlock aft holding cells and equipment storage", +5% plot XP): `k_plev_freeparty` switches back to the Jedi (`SwitchPlayerCharacter(-1)`, the character made again from the file it was put in, equipment and all), the cells open, Carth and Bastila come out and talk (`lev40_bast400`: "Good job, Mission!", the plan: Carth and Bastila come with the player, the others go to the Hawk, Canderous's call), journal `lev_captured` 10 | works | `02_cell.txt` |
| 7 | The equipment room: the locker (`lev40_ptylocker`: the Jedi Robe, the lightsaber, vibroblades, medpacs) taken with the clicks of a player (hover, two clicks, Get Items); Canderous's comm call on the way (`lev40_cand_dlg`: "We're at the Ebon Hawk... under heavy guard"); the elevator console (`plev_elev_dlg`) asks the party to be within 15 m (`k_plev_chkprox`) before "Bridge" | works | `03_gear.txt` |
| 8 | The command deck (`lev_m40ab`, 27 rooms): Sith troopers, Dark Jedi Masters (Flurry, Force Choke), an assault droid, the armoury and its doors, the bot in god mode: 130 m to the bridge door (`lev40_bridgedoor`, a module change to `lev_m40ad`) | works | `04_deck.txt` |
| 9 | The bridge corridor: five Sith Elite Troopers (140 hit points) at the door, killed by the party; the trigger `lev40_bdgunlock`, the bridge door | works | `04_deck.txt` |
| 10 | Saul Karath's first scene (`lev40_saul402` entry 19: the party jumps to `lev_jump_wp_*`, walks to `lev40_party0-2`; "Very resourceful...", "The only thing you taught me was betrayal and death, Saul.", the surrender offer and Carth's "I've seen enough of Sith mercy!") 19-22 m from the speaker: the bridge is long, the shots are wide | works (the staging is the cut scene's) | `05_saul.txt` |
| 11 | The fight (his guards, two Dark Jedi, `k_plev_bridgeatk`), Saul dying ("Carth... Carth....", "It's time to finish this.", the reply "No, Carth, don't give in to your hatred!" or the dark one, "Take your time, Carth. Make him suffer": `k_act_lightsml` / `k_act_darksml`), his whisper to Carth (the revelation: Carth cannot repeat it), his death (`k_plev_killsaul`), Carth to Bastila ("it is true, isn't it? And... you knew!"), `K_SWG_CARTHTALK` journal, `LEV_SAULDEAD` | works | `05_saul.txt` |
| 12 | The bridge computer (`lev40_comp25`): "Open docking bay doors." (journal `lev_captured` 66: "you can feel Darth Malak's presence drawing ever closer"), the refused reprogramming (10 spikes); back through the door to the deck | works | `06_baydoors.txt` |
| 13 | The elevator to the hangar (`lev_m40ac`): the "Hangar" reply, the 15 m rule | works | `07_elevator.txt` |
| 14 | The hangar (31 rooms): Dark Jedi Masters, troopers, turrets; the cut scene at `lev40_malacs`: Malak and Bastila's "Reunion?", the Revan revelation in two parts: `lev40_darthmala2` (22 nodes, then movie `31a`, the 95 s flashback of Revan's capture, `stunt_31b`, and the 58-node talk: "Do you mean I'm really... your Master?", Bastila's confession, "Why not just let me die?", "But why program me with another identity?", "Your power is no match for the light!") | works | `08_hangar.txt` |
| 15 | Bastila's stand: Malak throws the party down (`k_plev_throwdown`), Bastila fights him by cut scene (`k_plev_bastatk`, `CutsceneAttack`), "I'll hold Malak off. You two get out of here! Find the Star Forge!", Carth's "NO!!", the sealed door, "Bastila sacrificed herself so we could get away", `lev_captured` stays at 66 until the Hawk | works | `08_hangar.txt` |
| 16 | The Hawk (`lev40_hangardlg`), the turret `m12ab` (movies `17a`, `11a`; the gunner bot clears the fighters in 9 s), the arrival in `ebo_m40ad` (movie `11b`) | works | `08_hangar.txt` |
| 17 | The talk aboard (`ebo_carth`, 82 entries: Mission's "Hey, where's Bastila?", Carth's "You're Darth Revan?", the party's views: Mission and Zaalbar stay, Canderous "I'm your man", HK-47's deleted memory core, T3-M4, Carth stays "as long as this mission stays on course"), journal `lev_captured` 99, `k_swg_hk47talk` 60; the flight `stunt_00` (movie `07_1`) and the landing in `ebo_m12aa` (movies `0b`, `05_5a`): the Hawk after the Leviathan | works | `09_hawk.txt` |
| 18 | The galaxy map afterwards (`galaxymap.gui`): Manaan (where the flight was bound) is the current planet and the one the map offers; the Unknown World's dot is hidden until the fifth Star Map | works | `10_galaxy.txt` |

(The numbers are the frames of the chain: the capture at 3,200, the interrogation at 8,150-20,260, Mission's scene to 23,300, the party freed at 3,300 of
part 2, the bridge at about 3,000 of part 5, Malak's talk at 6,500 and 9,200 of part 8, the Hawk's talk 8,500 frames long.)

## The movies (every one played to its end once, with `CINEMA=1`: `movie NAME end: finished after S s, N pictures shown, 0 dropped`)

`05_7c` (Korriban's take-off, 517 frames), `08` (hyperspace, 489), `17` (the Leviathan takes the Hawk, 717), `31a` (the Revan flashback: Bastila
and the Council's judgement of the captured prisoner, 2,856 frames = 95 s), `05r` (the return to the hangar, 615), `17a` (the Leviathan's hull as the Hawk
escapes, 701), `11a` (the turret's cover, 633), `11b` (after the turret, 771), `07_1` (the flight, 112), `0b` (284), `05_5a` (the landing, 810). A still of
one is `kotor/out/bink2png.exe NAME --from N --to N` (frames 300 of `17`, 100 of `17a`, 200 of `31a` were looked at: the colours and the
letterbox are right; the game draws them through the same player). They played into nothing before this branch: see Bugs.

## Experience, alignment, journal

The player: 104,970 XP at the start, 106,885 after the deck, 109,200 after Saul, 114,110 on the Hawk (the Leviathan gives about 9,000: Saul's
fight, the Dark Jedi, Malak's hangar). Alignment 97 to 98 (the reply "Take your time, Carth. Make him suffer for what he's done to you!" is dark
(`k_act_darksml`); the run takes the light one). Journal: `k_pebo_stowaway` 99 (Zaalbar's talk about the stowaway on the Hawk, `ebo_zal`, the first thing played),
`lev_captured` 1 (Mission), 10 (the cells open), 66 (the bay doors), 99 (the Hawk), `k_swg_carthtalk` 99, `k_swg_bastilatalk` 1,
`k_swg_hk47talk` 60. Globals: `Lev_Escape` 1 (Mission), `Lev_Rescue`, `LEV_ELEVATOR`, `LEV_LEVEL` 2, `LEV_SAULDEAD`, `K_CAPTURED_LEV` 10,
`K_KOTOR_MASTER` 20, Bastila taken out of the available companions.

## Bugs found and fixed

1. **`SwitchPlayerCharacter` was a stub** (0919a56). The Leviathan's prison break is played in the body of the companion the player chose; the
   cell scene's speaker "Mission" did not exist, so the talk ended after one line and the story went on with the Jedi in front of the guards,
   unarmed, killed in seconds. The routine now follows `CSWPartyTable::SwitchPlayerCharacter` (re/party-items-saves.md 3.5): the player's character is
   written to the game in progress as `pc`, the NPC is taken or made at its place and is the player (`GetFirstPC`, the HUD, the dialogues), the
   rest of the party is kept and despawned, `AddPartyMember` refuses meanwhile, `pc_rules` is off for the companion, `PT_CONTROLLED_NPC` is saved
   and read (a module change and a save between the switches work); back (-1) the character is made again from the file.
2. **A Min1HP party member was "down"** (a5b1662). Malak's Force Choke took the god-mode player to 0 hit points for a moment inside a tick and the
   rules copy kept `down = true`: "Your entire party has been killed." with the player at 1 hit point.
3. **No movie ever played in the game** (found here; the player that now plays them is the Star Forge QA's `game/cine.ctx`, 6128da6, which this
   branch's own `game/movies.ctx` (0079e39) was folded into and dropped for). `PlayMovie`, the movie arguments of `StartNewModule` and
   `QueueMovie`/`PlayMovieQueue` posted outbox notes that nothing took; the cut scenes between modules were black. A hidden run logs
   `movie NAME (not shown: hidden run)`; with `CINEMA=1` (the `--cinema` flag) the chain's run.sh plays each film through the player and the log says
   `movie NAME start: WxH, N frames, sound true` and `movie NAME end: finished after S s, N pictures shown, 0 dropped` once per film (the films then take
   loop frames, so the chain runs without it). Checked this way: `05_7c`, `08`, `17` (part 1), `31a`, `05r`, `17a`, `11a`, `11b` (part 8) each play once.
4. **The test bot stood still after the merge of the path work** (the commit of this log's last change). Since a closed door no longer lets the planner walk
   through it, a hostile in another room (the deck's 13 guards in their rooms, 15 m off behind doors) became unreachable: the bot attacks the nearest
   hostile in sight before it follows its route, the approach failed at once, and the party stood 5 m before a closed door for ever. The bot now opens the
   closest closed door within 6 m when it gets no nearer (as it did for a stop), and leaves a foe farther than 8 m that it has not got nearer to
   in 12 decisions (`bot: cannot get at foe N, leaves it`). Real fights (a foe within 8 m) are not left.
5. Test tools: `savewhen MODULE NAME soon` (a save 5 ticks after a module is entered, for places where a conversation starts at once), `dlgtree.py
   --module`, `nss.sh`, `objs.sh`.

## Observations and open items

- **Crafted-state traps** (not game bugs): a pure Jedi has no starting entry in `stunt_00` (above); the party members are not in the party after boarding
  the Hawk (the original's `k_pebn_pophawk`); `ui stat` acts on the leader, so the order of the setup lines matters (the hit points after the classes);
  a mid-cut-scene checkpoint (a save while Malak and Bastila fight) loads without the scripted state and the player is killed: the chain saves
  before the hangar and plays the whole of it in one part.
- **OPEN: door `Hardness` and `CurrentHP`.** The insane Rodians in the next cells break their doors in three hits (20 hit points, no hardness): the template
  says `CurrentHP` 60 and `Hardness` 5 (`lev_cell010.utd`; gff-templates.md: damage reduction against physical attacks); the engine reads `HP` only for a door
  and ignores `Hardness` (`fight::damage_object`). Not fixed (door damage is the combat lead's); in the original they do not get out (they bang on the
  force fields), here Mission fights them through the opened cell door.
- **Staging audit**: the audit (`stage_audit.py`) lists only cut-scene staging (Saul 10.7 m from the player in
  the torture room, the bridge talk 22 m, Bastila 31 m from Carth in the hangar finale, Mission 9 m and Canderous 12 m in the Hawk's hold): the data's.
- **The light** of the deck and the hangar is the red emergency light of the data; not compared with the original.
- **The fade at the start of the hangar finale** is 40 frames of black (the script's fade), then the wide shot.
- **Not played**: the other four escapees' prison blocks (T3-M4 in the droid maintenance, HK-47 in the junk heap, Jolee's cell, Juhani, Canderous; the
  scripts `k_plev_t3cs*`, `hkcs*`, `jucs*`, `jedics*`), the optional rescues of the rest of the party before the elevator, the gas vent on the aft
  barracks (the detention computer's second option), the armoury, the hangar's turret shortcuts, the droid maintenance's upgrades, the Sith party
  of the deck (`lev40_sithstay`), the cell block's Rodian prisoner talk (`lev40_rodpris2`); the dark reply at Saul's death and the other replies of the Malak
  talk (the chain takes the first reply of each list: 20 choices that change only the words).
