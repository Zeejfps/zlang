# Playthrough log: the Star Forge and the endings

The end of the story played headless, step by step, checked against the original with logs and screenshots, from a crafted arrival
after the Unknown World: a Jedi of level 20 (Soldier 7 and Jedi Guardian 13), the party, the plot globals. The method is
[playthrough.md](playthrough.md)'s and [playthrough-korriban.md](playthrough-korriban.md)'s; the scripts are in
`kotor/tools/playthrough/starforge/`.

**Played:** the light side from the Hawk's galaxy map to the credits and the main menu: the take-off (STUNT_42, Admiral Dodonna's comm),
the landing, the docking bay (the Jedi, Malak's scene, the assault droids, the dark Jedi killing the Jedi captives), level 1 (Malak and
his apprentice, the turret computer), level 2 (Malak summoning Bastila, the three frozen Sith, Bastila's door, stasis and duel with
her three fight talks, her redemption **or** her death, the six droid generators, Malak's draining of a Jedi), Malak's chamber (his talk,
the fight, seven captive Jedi drained, his last speech), the escape (Carth and Bastila in the docking bay), the fleet breaking through
(STUNT_56a, film 56), the Jedi ceremony (STUNT_57, film 56b, Yoda, Dodonna), the credits and the main menu. The dark side from the Hawk to
the dark ending: the temple summit (Bastila, Jolee and Juhani killed), the take-off (STUNT_44), the docking bay with Zaalbar gone mad,
level 2 (Malak's choice of three Sith successors, Bastila's goodbye, STUNT_51a), the generators, Malak's chamber, "the apprentice has
learned his final lesson", the Republic's end (STUNT_54a, film 51), the Sith ceremony (STUNT_55a, films 54b and 55) and the credits.
0 script faults in every part of both chains.

**Stopped** at the main menu after the credits; a `newgame` there starts the next session in the same window
(`FRAME newgame` in a hidden `--cinema` run). To resume anywhere: `CKPT=NAME sh kotor/tools/playthrough/starforge/run.sh sN PART FRAMES`
(the checkpoints are in the table below).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_sf.exe
sh kotor/tools/playthrough/starforge/all.sh [FIRST_PART]       # the light side, about 15 minutes: each part loads the checkpoint the one before saved
sh kotor/tools/playthrough/starforge/dark.sh [FIRST_PART]      # the dark side from the Hawk (saves in saves_dk, checkpoints d...), about 15 minutes
sh kotor/tools/playthrough/starforge/kill.sh                   # the light side with Bastila killed (needs the checkpoint "freeze")
MODULE=unk_m44ac SAVES=kotor/out/pt/saves_dk sh kotor/tools/playthrough/starforge/run.sh d20 20 12000    # the temple summit
CKPT=NAME [ARGS=--cinema] sh kotor/tools/playthrough/starforge/run.sh NAME PART FRAMES [FRAME:SHOT]...    # one part from its checkpoint
sh kotor/tools/playthrough/starforge/sum.sh kotor/out/pt/sN.log [FIRST_FRAME]                            # the story lines of a log
```

Logs are `kotor/out/pt/sN.log` (light), `dN.log` (dark), checkpoints `kotor/out/pt/sf_ckpt/NAME`, pictures `NAME_SHOT.png` (`all.sh` takes
one 30 frames before the end of each part). Everything runs with `FAST=1` and `LOG=dialog,combat`. The last part of each chain runs with
`--cinema` (docs/testing.md): the hidden run decodes the films with their sound, scrolls the credits to credits.wav and comes up at the
main menu. Without `--cinema` the log says `movie NAME (not shown: hidden run)` for each film, which is how a replay shows which beat
calls which film.

### The crafted state

- `--module ebo_m41aa`, the Hawk on the Unknown World (its entry point). The player is made by `ui jedi 3 20` (a pure Guardian), then
  `ui stat class 0 / level 7 / class2 3 / level2 13` gives it the **Soldier 7 / Guardian 13** of a real game. This matters: the
  take-off cut scenes branch on the player's first class and gender (`k_tall`, `k_medium`, `k_small`, `k_tiny` read `GetLevelByClass(0..2)`),
  and a player with no soldier, scout or scoundrel level takes none of the branches: STUNT_44's talk (`m12aa_c06`) ended after 18 of 50 nodes
  and the Hawk never landed. Hit points 260, Strength 18; the companions are `ui jedi 4/5 18`.
- Light: Jolee and Juhani with the player (`k_punk_bastatt05` puts them in the party for Bastila's talk), Carth, Canderous, HK-47,
  Mission, T3-M4 and Zaalbar available, Bastila not; `G_FINALCHOICE 2`, `K_KOTOR_MASTER 50`, `K_STAR_MAP 50`, `K_SWG_CARTH 16`
  (set by `k_punk_carthadd`: the dark ending goes by it), `UNK_DISRUPT_OFF` and `EBO_HYPER_FIXED` (the galaxy map's own dialogue refuses
  without them). Dark (`21_dhawk.txt`, alignment 12, `ui jedi 3 20 dark`): Bastila in NPC slot 0, Zaalbar insane
  (`Unk_ZaalbarInsane`), Jolee, Juhani and Mission gone, `G_FINALCHOICE 1`, `K_SWG_BASTILA 13`.
- Replies are a queue (`ui replies ~words ... default 1`), as in the Korriban log. The party screens are clicked: `BTN_NPCn` toggles a
  slot (Bastila is forced on the dark Hawk: "This character must be a member of your party at this time."), `BTN_DONE` applies.
- Test cheats used for setup only: `ui jedi`, `ui stat`, `ui avail`, `ui giveitem` (Computer spikes: `g_i_progspike01`), `ui global`,
  `ui gbool`, `ui planet`, `ui bot on/god on/route/party` (the fights of the hall, the guards, Malak), `ui heal`, `ui goto`, `warp`,
  `warpxy` into the strips the long walks would end in, `save` / `savewhen`.

## The steps (light side)

State: **works** (checked, 0 faults), **fixed** (a commit of this branch), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | The Hawk on the Unknown World, the crafted state; the party is taken off the ship on entering (`k_pebn_remove`) | works | `01_hawk.txt` |
| 2 | The galaxy map (`ebo41_galaxymap`: its one-liner sets `K_KOTOR_MASTER` 50 and shows the map), the Star Forge picked: `k_sup_galaxymap` runs `ST_PlayUnknownWorldTakeOff`: STUNT_42 with films 05_8C and "5_9" (the install has no `5_9`: the file is `05_9`; the original's loses it too), Dodonna's comm talk (`m12aa_c05`, 24 entries: Carth, Dodonna, Vandar, Yoda), `k_ren_starland` lands the Hawk on planet 50 (`ebo_m12aa`, film 43). **No turret battle here**: the fighters come on the way *to* the Unknown World (`ebo_starforge.dlg`, then `m12ab`), which is the Unknown World's leg, not this one | works | `02_takeoff.txt` |
| 3 | Out of the Hawk: the ramp strip `ebn12_ebonexit` runs `k_pebn_leavhawk` (party screen: two companions, `BTN_DONE`), module change to `sta_m45aa`, the Jedi's talk at the Hawk (`k_sta_jedifem`, 12 entries: "You made it! Several Jedi have already gone ahead"); the Sith at the elevator turn on the Jedi (`k_psta_sthattack`) | works | `03_exit.txt` |
| 4 | The docking bay: Malak's scene seen from afar (`k_sta_malak1`, strip `sta_trgcutscene1`, Malak 121 m away by design), the Sith apprentice orders the droids, the doors blow (`k_psta_explode1`), four assault droids fought by the bot | works | `04_hall.txt` |
| 5 | The east wing: the strips `sta_trg_lockwest/east` shut the other wing's door, the dark Jedi kill the three Jedi captives (`k_sta_jedidark`, a cut scene of type 2 started by `sta_trgcutscene3`), the door to level 1 (`sta45a_east_45b`) | works; the leader keeps walking through the cut scene (see Observations) | `05_east.txt` |
| 6 | Level 1 (`sta_m45ab`): Malak and his apprentice (`k_sta45_malak2`, started by `sta_trg_cutscne2`), the turret computer (`sta45_turretcomp`: "Slice the computer", "Deactivate sentry guns", "Log out."), the door to level 2 | works | `06_turrets.txt` |
| 7 | Level 2 (`sta_m45ac`): on arrival Malak summons Bastila (`k_sta_lightcut`, 16 entries: "You must kill Revan to prove yourself worthy of being my apprentice"), the strip `sta_freezer` freezes the three Sith (`k_sta_freezeconv`), killed by the bot, which opens the freeze door (`k_sta_door_ud`) | works | `07_guards.txt` |
| 8 | Bastila: the leader walks into the door `k45_door_bast1` (it opens by itself, `k_psta_bast_wor` starts `k_sta_bastila`), her stasis on the party, the duel with her three fight talks, then `k_sta_bastlast`: the persuasion path (conviction `k_sta_bastcon+N` must reach 100) ends "You won't, Bastila. I know you still serve the light side.", journal `sta_confront` 10, `Sta_BastConversion` 15, `K_PSTA_BASTSAVE`; `k_psta_bastopen` plays STUNT_50a with film 50b and returns with film 50. The other replies end in "You're right. Don't worry, you won't feel a thing." (`k_sta_bastexe`: the same cut scene, Bastila dead, `STA_BASTILA_DEAD`) | fixed (the door never blocked: see below) | `08_bastila.txt`, `08k_bastila_kill.txt` |
| 9 | The east end of level 2: the strip `k45_strt_malak` starts Malak's scene (`k_sta_darthmalak`: he drains two Jedi), locks his door and starts the six droid generators (`k_psta_genstart`); each shut down with "Disable generator." (Computer, spikes), the sixth sets `STA_GENERATORS` 6 and opens the door | works | `09_generators.txt` |
| 10 | Malak's chamber (`sta_m45ad`): the elevator door, `sta_malanim`, the strip `k45_init_malak`, his talk (the light replies), the fight begins | works | `10_chamber.txt` |
| 11 | The fight: `sta_firstjedi_co` (his speech about the Jedi of the Academy), seven times the eight captives' force fields and `k_sta_jedi` (he drains one when low: his hit points climb back to 327 of 307), his last speech, `sta_walkaway`, the docking bay again at `STA45A_WAY_45D` (`k_sta_carth`: Carth's "There you are! What happened?" and Bastila's thanks, or "With Bastila dead, the Republic has broken through"), STUNT_56a (film 56, Dodonna's report), STUNT_57 (film 56b, the ceremony `m41ad_c01`: Yoda, Dodonna, the Jedi), `k_creditsplay`, the credits, `k_endgame`'s EndGame, the main menu | works | `11_fight.txt` |

Checkpoints: `hawk`, `landed`, `bay`, `hall`, `lvl1`, `lvl2`, `freeze`, `bastsaved` (`bastdead`), `gens`, `fight`.

## The steps (dark side)

| # | Step | State | Script |
|---|---|---|---|
| 20 | The temple's summit (`unk_m44ac`) from the module itself: the strip `unk44_bastcs` (84.9..86.9 x 65.9..76.2) starts Bastila's talk (`unk44_evilbast`, 172 entries); the dark replies: "A pawn of the Jedi Council?", "I always knew you were weak!", "I am Revan, the Dark Lord! Bow down to me, Bastila!"; the fight with her (bot, Jolee and Juhani helping); at half her hit points `k_punk_bast_ud2` throws the party back and starts the second talk ("Now you see the power of the true Dark Lord!", "Yes! Together we can rule the galaxy!", "I am the Lord of the Sith!", "Death to the Jedi!"): `k_punk_evilfinal`, `k_punk_bastjoin` (`G_FinalChoice` 1, Jolee and Juhani leave the party and the roster, Bastila joins), journal `unk_trapped` 98, and the fight against Jolee and Juhani, who die. The talk after the duel waited for a party member lying where it was thrown: fixed (see below) | fixed | `20_summit.txt` |
| 21 to 23 | The Hawk, the galaxy map (STUNT_44 and `m12aa_c06`, 50 nodes), the party screen (Bastila forced, Zaalbar added), the docking bay | works | `21_dhawk.txt` to `23_dexit.txt` |
| 24 | The docking bay: Zaalbar's rage (`k_sta_zaalbar`, "You tricked me, Revan! ... made me kill Mission!") and his death by the player | works | `24_dhall.txt` |
| 25, 26 | East wing and level 1 are the light side's own scripts (`05`, `06`); on level 2 the Sith summoned are Malak's new successors (`k_sta_darkcut`, `nm45aadark99000..7`: "Bastila has betrayed me. I must select a new successor") | works | `05`, `06` |
| 27, 28 | The freeze guards; the strip `k45_init_sith` starts `k_sta_darkjedi` and the three apprentices fight (`k_psta_sithhosti`); the chamber's east door (`k_psta_initbas2x` needs `STA_SITH_DEAD`) starts Bastila's goodbye (she stays to meditate), STUNT_51a with film 54 (`cut51a_diag`) and back with film 51b | works | `28_dsith.txt` |
| 29 to 31 | The generators, Malak's chamber (the dark replies: "I was always stronger than you, Malak!"), the fight, his speech ("No, Malak. I am the true Sith Master!", "The apprentice has learned his final lesson."), `k_psta_mlkend`: with `G_FinalChoice` 1 and `K_SWG_CARTH` not 16 it goes straight to STUNT_54a (film 51: the Republic's end, `m01aa_c04`), STUNT_55a (film 54b, the Sith ceremony `end_55a`), `k_stunt_end`: QueueMovie 55, PlayMovieQueue, the credits, EndGame. With `K_SWG_CARTH` 16 it walks away to the docking bay, where Carth waits for Revan (`k_sta_carth` E0: "So you killed Darth Malak ...", his love, the choice to spare or kill him) | works (both) | `dark.sh` |

## Movies, credits and the end of the game

Nothing consumed the outbox's film notes before this branch: `PlayMovie`, `QueueMovie` / `PlayMovieQueue`, StartNewModule's `sMovie1..6`,
`StartCreditSequence` and `EndGame` were routines that posted a note, and the game went on without a film, without credits, and closed the
window at its end. `game/cine.ctx` shows them (docs/testing.md, `--cinema`):

- A film is a Bink movie from `movies/` decoded by `lib/video` with its sound in the mixer's movie group (music, voice-over and effects
  are hushed meanwhile, as the original's movie sound mode does). Escape, Enter, Space or a click skips a skippable one; a skip ends the
  rest of the queue unless PlayMovieQueue allowed separate skips. A module change plays its films **before** the module is loaded
  (`StartModuleTransition`'s `PlayQueuedMovies`, gameloop.md 5.3), a `PlayMovie` plays between two frames of the world.
- The credits are `credits.2da`'s fifteen title cards (a role and its names, fading in and out for 5 s each) and its long list scrolling
  up the black screen in `fnt_credits`, the whole to the length of `credits.wav` (273.5 s); Escape or a click ends them.
  `IsCreditSequenceInProgress` answers false afterwards, which is what `k_endgame` waits for.
- `EndGame(bShowEndGameGui)` ends the session: the main menu comes up after 5 s (the death box's wait) or at once with `FALSE`. The same
  way back now serves the party wipe and the options menu's Exit Game: the world is made again and the front end runs again in the same
  window (`play::run` is a loop of sessions).

Checked mid-film with screenshots (hidden run, `--cinema`, `--screenshot-at`; and a window run for the sound device): StartNewModule's films
(05_8C in the Hawk's take-off: the Rakata ship on the beach; 54b), PlayMovie (the `movie` input word and `k_punk_bastesc`'s `05_8E`
on the summit), the queue (`k_stunt_end`'s 55), all nine ending films (50, 50b, 51, 51b, 54, 54b, 55, 56, 56b: 640x272 or 640x360, 354 to
2,035 frames, sound, none dropped), a skip by Escape (38 pictures shown of 354, the next film of the queue skipped with it), the credits
(cards and list) and the main menu after EndGame.

Which story beat uses which call (found by scanning every script of the install for the routines' ids):

| Call | Story beats |
|---|---|
| `PlayMovie` | `k_pend_area01`: the opening film 01A after New Game; `k_ptar_playmovie` 03 (Davik's estate); the visions of Bastila on the Hawk, `k_hbas_playtat/man/kash/korr` 0A..0D; `k_pman_28d_cmp01/02` 26a, 26b (the Manaan prison ship); the swoop races' 01g (`tar_m03mg`); `k_punk_bastesc` 05_8E (Bastila escapes on the temple's summit) |
| `QueueMovie` + `PlayMovieQueue` | only `k_stunt_end` (STUNT_55a, the dark ending): film 55, then the credits |
| `StartNewModule` with films | the Endar Spire pod 01c; Taris: `k_ptar_godaviks` 03, `k_ptar_bastpart` 02, `k_ptar_tarisover` 05, `k_ren_taris01/02/03` (05, 05_1C and 06a, 11a); the planet-to-planet flights (`k_sup_galaxymap`, `k_ren_nextplanet*`, `k_ren_visionland`: the take-off films 05_xC, hyperspace 08, the landing films 05_xA, the visions 01f/09); Dantooine `k_ebn12_dantrans` 05_2A; Kashyyyk's baskets 22A, 22B; Manaan's submarine 23a, 23b; the Leviathan (`k_ren_levcapture` 17, `k_ren_levescape` 11a and 17a, `k_plev_gostunt` 31a, `k_stu_jumplev` 05r); the turret (`k_ren_turret*` 11a/11b, `k_pebo_mgheart`); the Unknown World (`k_ren_unkcrash` 05_8A, `k_ren_unkturret` 11a, the take-off 05_8C and the data's "5_9"); the Star Forge: the approach 33 (`k_ren_starforge`), the landing 43 (`k_ren_starland`), Bastila's death or the fleet's help 50b (`k_psta_bastopen`, `k_psta_ud_bastil`, `k_sta_bastexe`) and 50 (the return, `k_pstu_startmod`, `k_psta_carthlove`), the dark Bastila 54 (`k_psta_bastopen2`, `k_psta_bastfade`, `k_psta_ud_malak`) and 51b, the Republic's end 51 (`k_psta_mlkend`, `k_swg_bastmovie`), the ceremonies 54b and 56b (`k_pstu_modend`), the fleet 56 (`k_psta_carthend`, `k_psta_bastleav2`) |
| `StartCreditSequence` | `k_creditsplay` (the last reply of STUNT_57's ceremony, light) and `k_stunt_end` (STUNT_55a, dark) |
| `EndGame` | `k_endgame` (the heartbeat of STUNT_55a and STUNT_57, `EndGame(0)` once the credits are over); the story's failures with the death box (`EndGame(TRUE)`): `k_dan_death`, `k_plev_slicebad`, `k_pman_arrest16`, `k_pman_fish04`, `k_ptat_kraytkill`, `k_pkor_endgame`, `k_punk_rakatk3`, `k_pebo_hawkhit`, `k_pebo_death*` |

(A minigame's own frame still discards the notes it finds in the outbox, so a `PlayMovie` called from inside the swoop or turret area is
not shown; the module changes that leave them are.)

## Bugs found and fixed

1. **A closed door whose walkmesh is a box let everyone through** (629e923). `walkmap::over_blocking_face` tested each face of a door's or
   placeable's walkmesh against the walker's height; the Star Forge doors' closed DWK is a box from 1.8 m below the floor to 6.7 m
   above it with no flat face within a head's height of the floor, so the party walked through all of them and skipped the scripts the
   doors run when they open (Bastila's scene, `k_psta_bast_wor`, never began). The original sweeps these walkmeshes through all heights
   (`TestSegmentAgainstObjects`, movement.md 4.4): the faces now count by where they stand on the floor plan, the mesh by its heights.
2. **No film, no credits, no way back to the menu** (6128da6; see above).
3. **The talk after the temple duel never began** (0d7c542). `k_punk_bast_ud2` throws the party back with EffectForcePushTargeted and starts the
   conversation on a fixed delay; our thrown creature lies 2.55 s and the delay fell one frame short, and a talk whose target is not
   commandable fails. A `DIALOGOBJECT` whose target lies where it was thrown now waits for it to stand.
4. **A game saved while the leader lay thrown kept it frozen for ever** (df75a33). The save wrote `Commandable` false, which the fall (not saved)
   would have restored. It writes true for a creature that is knocked down.
5. **A stunned leader never woke up** (820cd92). Dark Jedi's "Improved Critical Strike" stuns for 6 s; when it ended, 73 other effects
   (visuals, icons) ended in the same update and the 48-slot event list of `rules::effects` was full before the state change was
   reported, so the "commandable again" event was lost: the leader stayed frozen, every click and every `DIALOGOBJECT` aimed at it
   ("talk refused (not commandable)") failed, and a checkpoint saved then loaded frozen. The last six slots now take only the events that
   free a creature (found by the Bastila step of the light chain, which could not start her talk).
6. Test tools: `ui locks` prints a door's state, static flag and walk index; `ExecuteScript` of a missing script and a refused
   `DIALOGOBJECT` say so in the `scripts` and `actions` logs.

## Observations and open items

- **A creature made hostile by a conversation's last script does not start the fight when its first AI action is a self-buff**
  (Bastila's duel on level 2, the dark Sith apprentices, the temple's Bastila). `k_psta_bastatt` / `k_psta_sithhosti` run BioWare's
  `GN_DetermineCombatRound` inline, which picks Energy Shield or Force Immunity on the caster itself; no round starts, the round-end
  script (`k_def_combend01`) never runs, and the creature stands still until something attacks it. The bot's attack (a person clicking on her)
  starts the duel. In the original the next decision comes from an event; which one is not known (combat.md 3.5 says a spell round runs
  no OnEndRound). Left to the combat/perception owners: the workaround is the bot (`ui bot on` once the hostile is within its 16 m).
- **A cut scene of type 2 does not stop the leader** (`k_sta_jedidark`, started by a strip while the bot walks): the queued walk goes
  on under the cut scene (the leader left the hall during the talk and changed module before it ended).
- Bastila casts Force Lightning twice within one combat round and also attacks (3 attacks) in the same round (`--log combat`, 962 in
  s8): the original gives a spell round the whole round. Not checked against the original.
- Malak's hit points climb to 327 after a drain though his maximum is 307 (`k_psta_ud_mal7`'s EffectHeal): not checked.
- Companions: `k_psta_door` removes the whole party for Bastila's duel and `k_psta_pc_j`, `k_psta_mlkparty` for Malak; the party does
  not come back, so Malak is fought alone (probably as in the original; the walkthroughs say so).
- A loaded checkpoint re-runs `k_psta_areaenter` and the OnEnter of the strips the party stands in (noted in the Korriban log).
- **Staging audit** (`stage_audit.py` on the ending's log): only cut-scene setups are far: Malak and the Jedi captives 13 m apart,
  `sta_invis_camera2` 50 m from the player, the fleet officers of STUNT_56a 23 m away.
- The test bot cannot pass a door that its walk has not opened (`ui goto` ends beside it; `use` opens it, as a click would).
- **Not played**: the west wings of the docking bay and level 1 (the other half of the split: the strips `sta_trg_lockwest/east`
  decide it, the scripts are mirror images), the Hawk's turret fight on the way to the Unknown World, the armour and robe computers, the
  Mark II/IV droid bins, `sta_captive_conv` (freeing a captive Jedi), Carth's romance scenes (`k_psta_carthrom1..6`), the dark Carth
  confrontation's two endings (kill or spare), the temple's light-side route (`k_punk_bastesc`, Bastila escapes), the "easter egg"
  (`k_psta_egg`).
