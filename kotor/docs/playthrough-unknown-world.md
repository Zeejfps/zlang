# Playthrough log: the Unknown World

The crash of the Ebon Hawk on Rakata Prime, the beach, the Elders' compound and the One's village, the ritual at the Temple shield, the
Temple of the Ancients (the catacombs and their floor puzzle, the Rakata database, the hall, the summit and the dark Bastila), the disruptor
field shut down, the way back to the Hawk and its repair, and the galaxy map's flight to the Star Forge, played headless, step by step,
checked against the original with logs and screenshots, from the Hawk after the Leviathan ([playthrough-leviathan.md](playthrough-leviathan.md)'s
checkpoint `hawkpost`). The method is [playthrough.md](playthrough.md)'s and [playthrough-korriban.md](playthrough-korriban.md)'s; the scripts are
in `kotor/tools/playthrough/unknown/`.

**Played:** the galaxy map with the fifth Star Map (Bastila's torture in the Star Forge vision, `stunt_18`, films `05_5c` and `08`; the hyperspace
scene `stunt_34`, film `33`; the Sith fighters and the turret, `m12ab`, film `11a`; `stunt_35`, film `07_2`; the crash, film `05_8a`;
Carth's talk `unk41_carth`), the party screen on the ramp (Carth and T3-M4), the beach (the ambush on the Duros, `newfight`; the Duros survivors,
`unk41_ithor01`), the Temple approach and the gizka cave (the hologram, the wreck's ship parts), the Elders' compound (`unk42_redelder`, 111
entries: the Council recognises Revan, the offer to free their scout), the One's village (the Black Rakata camp, the One and his warriors killed,
the scout in the cage, `unk43_redpris`), the Elders again (the ritual offered), the way back to the Hawk to leave the companions aboard, the
ritual at the shield (`unk41_guide_dlg`; Jolee and Juhani follow against the tradition, a [Persuade] reply; `stunt_19`: Malak and the Star
Forge), the Temple's vestibule and hall (shield droids, sentry droids, turrets), the catacombs (guard droids; `unk44_sparty`: the player alone;
the nine floor panels; the Rakata database `unk44_lib_dlg`), the summit (`unk44_evilbast`: the dark Bastila's talk, the duel, her escape; the
computer `unk44_comp`: the disruptor field and the energy shield shut down), the way out through the Temple to the beach (`unk41_carth`:
"Bastila has fallen to the dark side"), the Hawk repaired with the ship parts (`ebo41_hyper`), the galaxy map (`ebn12_galaxymap`) and the
take-off (films `05_8c`, `43`; `stunt_42`: Admiral Dodonna's comm). 0 script faults in the 21 parts.

**Stopped** at the start of `stunt_42` on the Hawk's bridge, the flight to the Star Forge: [playthrough-star-forge.md](playthrough-star-forge.md)
takes it from there (from a crafted arrival of its own: a Jedi of level 20, the party, the plot globals). To resume anywhere:
`CKPT=NAME sh kotor/tools/playthrough/unknown/run.sh NAME PART FRAMES` (the checkpoints are in the table below).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_lev.exe
sh kotor/tools/playthrough/leviathan/all.sh                   # first: the checkpoint "hawkpost" that part 1 starts from (about 3 minutes)
sh kotor/tools/playthrough/unknown/all.sh [FIRST_PART]        # the chain, about 2 minutes (parts 1-3, 5-22: part 4 is a look); each part loads the checkpoint the one before saved
CKPT=temple sh kotor/tools/playthrough/unknown/run.sh NAME 16 FRAMES [FRAME:SHOT]...      # one part from its checkpoint (CINEMA=1 plays the films)
sh kotor/tools/playthrough/korriban/sum.sh kotor/out/pt/NAME.log [FIRST_FRAME]             # the story lines of a log
python kotor/tools/py/stage_audit.py kotor/out/pt/uN.log                                   # the staging audit
sh kotor/tools/playthrough/unknown/xp.sh crash duros ...       # each member's XP and the leader's alignment at checkpoints
sh kotor/tools/playthrough/unknown/ncsall.sh                   # then ncsact.sh NAME...: the disassembled scripts of the planet (routine calls and strings)
```

Logs are `kotor/out/pt/uN.log`, checkpoints `kotor/out/pt/unk_ckpt/NAME` (a part's `save` or `savewhen` line and `ckpt.sh`; `CKPT=lev:NAME` is the
Leviathan chain's), pictures `kotor/out/pt/uN_SHOT.png` (`all.sh` takes one 30 frames before the end of each part). Everything runs with `FAST=1`,
`LOG=dialog,combat` and the options file `unknown/play.ini` ("Auto Level Up NPCs" on); `all.sh` checks after each part that the log holds the line
the part was written to produce and that it saved. The helpers are the Leviathan log's (`dlgtree.py --module`, `nss.sh`, `objs.sh`) and
`dlgs.sh` (the conversations of every module of the planet), `ncsact.sh`.

### The crafted state (part 1)

From the Leviathan chain's `hawkpost` (a Jedi of level 14, 114,110 XP, Carth in the party): the fifth Star Map as `UT_StarMap1VariableSet` leaves
it: `K_STAR_MAP 50`, `K_KOTOR_MASTER 30`, `K_STAR_MAP_MANAAN`, `K_CURRENT_PLANET 25`. With them `k_pebn_galaxy` offers the Unknown World, the map
(`ui goto GalaxyMap`, `use GalaxyMap`) is clicked as a player does it (`LBL_Planet_UnknownWorld`, `BTN_ACCEPT`) and `k_sup_galaxymap` plays the torture
scene on the way. Bastila is gone from the party (the Leviathan), so the ramp's party screen has two free places.

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch), **cheat** (played with a test helper, named), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | The galaxy map, the Unknown World picked, "Travel": `stunt_18` (Bastila tortured by Malak in the Star Forge, films `05_5c`, `08`), `stunt_34` (film `33`), the Sith fighters (`m12ab`, film `11a`, the gunner bot), `stunt_35` (film `07_2`), the crash in `ebo_m41aa` (film `05_8a`), Carth's talk (`unk41_carth`: "We've flown into some kind of disruptor field", the Hawk will not fly) | works | `01_galaxy.txt` |
| 2 | The ramp: the exit trigger `ebn12_ebonexit` opens the party screen (clicks on Carth and T3-M4, OK), `k_pebn_exithawk` starts `unk_m41aa` | works | `02_ramp.txt` |
| 3 | The beach: the cut scene `newfight` (savages attack the stranded Duros), the Duros survivors (`unk41_ithor01`: the Mandalorians by the Temple, the savages) | works | `03_beach.txt` |
| 4 | North along the shore to `unk_m41ac` (a look, not in the chain) | works | `04_north.txt` |
| 5 | The east end of the beach to the Temple approach (`unk_m41ad`, trigger `unk41_goto41ada`) | works | `05_approach.txt` |
| 6 | The approach to the gizka cave (`unk_m41ab`) and its hologram (`unk41_holo`) | works | `06_cave.txt` |
| 7 | The cave: the wreck's parts (`punk_shipparts`, "Ship Parts", taken with the clicks of a player: hover, two clicks); the pillars and barriers (not played: the party is moved to the door, `warpxy 52,95 party`); the door into the Elders' compound (a bot route to `rakatadoor2#1`: a hover click picked T3-M4 instead) | works / cheat (warp) | `07_cave2.txt` |
| 8 | The Elders (`unk42_redelder`, 111 entries, 12,800 frames): the Council recognises Revan; with the first reply of every list it ends with the offer to free their scout (journal `unk_trapped` 15) | works | `08_elders.txt` |
| 9 | To the One's village (the cave, the Temple approach, the beach, the north shore; the gate `unk41_blkdoor`, `unk_m43aa`) | works | `09_toone.txt` |
| 10 | The Black Rakata camp: the One attacks at his trigger (`unk43_battle`) and dies by the party's hands (journal 32; 1,350 XP), 31 Black Rakata killed (25 at 150 XP, 4 at 850, 2 at 750); the scout in the cage talks only with the leader out of combat (`k_punk_pris02`), so the bot is stopped at 14,000 frames and `use unk43_redpris` follows ("I was sent by the Council to save you": journal 33) | works | `10_prisoner.txt` |
| 11 | Back to the Elders with the scout (the gate, the shore, the beach, the approach, the cave; the barrier puzzle again moved past) | works / cheat (warp) | `11_back.txt` |
| 12 | The Elders again: the Council keeps its word and offers the ritual (journal 37) | works | `12_elders2.txt` |
| 13 | Out of the compound to the Temple approach and on to the beach and the Hawk (`unk41_goebon`, `ebo_m41aa`): the guide refuses a ritual with companions (`unk41_templecs` entry E31), so the party is left aboard | works | `13_temple.txt` |
| 14 | The Hawk's ramp again with nobody chosen on the party screen (Jolee and Juhani are aboard), the beach alone | works | `14_alone.txt` |
| 15 | The ritual at the shield (`unk41_guide_dlg`, 42 nodes shown): the guide begins it when the player nears him; Jolee and Juhani follow from the Hawk against the Rakata's tradition (journal 45; a [Persuade] reply); `stunt_19` (Malak and the Star Forge, 14 nodes); the shield is down and the walk to the Temple door starts only after it (9,000 frames: the bot's stall rule would open the shield door itself) | works | `15_ritual.txt` |
| 16 | The Temple of the Ancients (`unk_m44aa`): from the vestibule the walk round the Temple's outer ring (east side, the north corridor, the hall's left corridor: 240 m, the star door being sealed) to the door down to the catacombs (`unk_m44ab`, `unk44_basedoor`); guard droids (800 XP each); the strip `switchparty` (`unk44_sparty`, `SetSoloMode`): the player alone, Jolee and Juhani wait at their waypoints; the floor puzzle (a lights-out board: the nine panels `k_punk_floor01..09` toggle a panel and its neighbours, all nine lit sets `UNK_TILES` and opens `unk44_massdoor`; the solution is the corners and the middle, 1-3-5-7-9, entered by warps); the Rakata database (`unk44_lib_dlg`: "How can I get to the upper levels of the temple?", `k_punk_givestar` sets `Punk_stargem`) | works / cheat (shield droids made friendly; warps on the panels) | `16_cata.txt` |
| 17 | Back out through the door (the transition puts the party together), the whole loop of the outer ring again (the left corridor of the hall does not meet the room behind the star door; 6,000 frames), through the star door and up the right corridor to the stair and the summit door `unk44_basedoor#1` (`unk_m44ac`): the shield droids, turrets and patrols made friendly (`ui faction`, all the creatures with the tag) | works / cheat (factions) | `17_stair.txt` |
| 18 | The summit: the strip `unk44_bastcs` starts the dark Bastila's talk (`unk44_evilbast`, 172 entries): "Revan - I knew you'd come for me", Juhani's plea, the replies "No, Bastila! Don't go over to the dark side!", "Don't be lured in by these Sith lies, Bastila!"; the duel (Bastila 354 hit points); at 150 lost `k_punk_bast_ud2` ends it: the party is thrown back, Jolee and Juhani are taken out of the party, the talk goes on (the replies "I draw my power from the light now" ...), Bastila escapes (her scripted walk and fade, `k_punk_bastesc`; journal 99) and the party is whole again | fixed (1) | `18_summit.txt` |
| 19 | The Rakata computer on the summit (`unk44_comp`): "Shut down planetary disruptor field.", "Shut down Temple energy shield.", "Log out." (`UNK_DISRUPT_OFF`, `UNK_SHIELD_OFF`; `k_starforge` 75) | works | `19_field.txt` |
| 20 | Out of the summit and through the Temple (the doors, the hall, the vestibule's `unk44_exitdoor`) to the approach (`unk_m41ad`) | works / cheat (factions) | `20_out.txt` |
| 21 | Down to the beach: Carth's talk (`unk41_carth`, "Bastila has fallen to the dark side. She fled to the Star Forge.", Jolee's counsel), the Hawk (`ebo41_tell`: the ship parts) | works | `21_hawk.txt` |
| 22 | The hyperdrive (`ebo41_hyper`, `k_pebn_hyper01`: the part is used, `EBO_HYPER_FIXED`), the galaxy map (`ebn12_galaxymap`, `k_pebn_starf`): the Star Forge picked, films `05_8c` and `43`, `stunt_42`; the leader walks to the hyperdrive and on to the bridge, no warps | works | `22_takeoff.txt` |

Checkpoints (`kotor/out/pt/unk_ckpt`): `crash` (1), `beach` (2), `duros` (3), `approach` (5), `cave` (6), `door` (7), `eldertalk` (8), `onecamp` (9), `scout` (10), `elders2` (11),
`eldersok` (12), `alone1` (13), `alone2` (14), `temple` (15), `library` (16), `summit` (17), `bastdone` (18), `fieldoff` (19), `templeout` (20), `hawkback` (21).

(Frames of the chain: the crash at 6,100 of part 1, the Elders' talk 12,800 frames long, the One's death at about 9,000 of part 10, the ritual's talk at 1,300 to
5,600 of part 15, the library's talk 2,200 to 5,800 of part 16, the Bastila talk 260 to 4,500 and 5,900 to 10,400 of part 18.)

## The movies (every one played to its end once, with `CINEMA=1`: `movie NAME end: finished after S s, N pictures shown, 0 dropped`)

Part 1: `05_5c` (25.7 s), `08` (16.3 s), `33` (41.6 s), `11a` (21.1 s), `07_2` (3.2 s), `05_8a` (35.2 s). Part 22: `05_8c` (13.3 s), then `5_9`
(see open items) and `43` (39.8 s) once each. 0 pictures dropped.

## Experience, alignment, journal

The player: 114,260 XP on the crashed Hawk, 115,260 after the Duros, 120,860 at the cave, 127,060 at the One's camp, 139,060 with the scout saved (the One,
his warriors and the Black Rakata: about 12,000), 139,660 with the Elders' word, 141,360 after the ritual, 142,960 after the catacombs (two guard droids at 800),
144,560 at the summit, 148,560 after the duel (4,000). Carth and T3-M4 follow about 21,000 and 29,000 behind (the pool); Jolee and Juhani are made at 87,976.
Alignment 99; 100 after the replies to Bastila. Journal `unk_trapped`: 1/5 (crashed), 15 (the Elders' offer), 25 (the datapad, not played), 32 (the One
dead), 33 (the scout), 37 (the Elders agree), 45 (Jolee and Juhani join the ritual), 99 (Bastila gone); `k_starforge` 60 (the crash), 75 (the
field shut down). Globals: `Unk_One_Dead`, `UNK_TEMPLEREADY`, `UNK_TILES`, `Punk_stargem`, `UNK_BASTILA_CS`, `UNK_DISRUPT_OFF`, `UNK_SHIELD_OFF`,
`EBO_HYPER_FIXED`, `K_KOTOR_MASTER` 50 then 60 (the take-off).

## Bugs found and fixed

1. **`CancelCombat` left the creature's round running** (the commit of this log). The duel with the dark Bastila ends by script at 150 hit points lost
   (`k_punk_bast_ud2`): the party is thrown back, Bastila becomes neutral, `CancelCombat` on everyone, then `ActionStartConversation` for the second
   half of the talk. The engine's `CancelCombat` cleared the queue but not the round; Bastila's round ended a moment later, ran her end-of-round AI
   (`k_def_combend01`, `ClearAllActions`) and wiped the queued conversation: the summit stood silent for ever with Bastila neutral at the door.
   `CancelCombat` now calls `fight::stop_fighting` (the round ends without `OnEndRound`, as the routine's own comment said), and the talk starts
   when the party has got up (the wait of 0d7c542).
2. **A film played twice** (the commit of this log). `StartNewModule` posted a film note on every call; the dialog `m12aa_c05` runs `k_ren_starland` as the last reply's script *and* as its
   end script (the data does), so the Star Forge landing (film `43`) played twice. A second call for a module change that is pending no longer
   posts a film the outbox holds already (`rt_mod::film_posted`).
3. Test tools: `ui faction TAG N` set only the first creature with the tag (now all of them); `savewhen MODULE NAME soon` (the Leviathan log), `ncsact.sh`, `xp.sh`.

## Observations and open items

- **Cheats of the Temple** (parts 16, 17 and 20; part 16 walks the real way round the star door): the shield droids (`unk44_shielddrd`, plot-shielded until their computers `templecomp` are used), the sentry droids and the
  turrets of the hall fight the party for as long as the bot's rule (nearest hostile first) lets them: the chain makes them friendly (`ui faction TAG 2`)
  instead of playing the computers (`unk_comp`, `unk_comp2` conversations), the Dark Jedi and the armory; the bot cannot walk the 0.5 m gaps between the
  floor panels, so the panels are entered by warps (`warpxy`, which fires `OnEnter` as a step does).
- **Fixed (1): the way from the vestibule into the hall.** The ritual leaves the party in the vestibule of `unk_m44aa` (`unk44_sw44aa01`, 95.3 39.2) between the locked plot
  `unk44_exitdoor` (south) and `unk44_stardoor` (north; UTD `Locked`, `KeyRequired`, key `punk_stargem`, `OnFailToOpen` `k_punk_stardoor`: its conversation `unk44_strdoor`, "sealed
  ... no visible means of unlocking it"). `k_punk_44enter` (the area's OnEnter) unlocks the star door once `Punk_stargem` is set, and that global is set by the Rakata database
  below (`k_punk_givestar`) and by `unk44_tmpgem` in the catacombs, both past the door: a player gets to the catacombs' door (`unk44_basedoor`, 89.9 59.3, in the hall's left
  corridor) the long way, along the Temple's outer ring (four of the wing doors `unk44_templedoor` are locked at DC 35; a search of the path graph with the locked doors removed finds this one way from the vestibule to the stair) and down the hall's left corridor, past the shield droids at its north end (their security computers `templecomp1..3` in the wings are a puzzle of their own, `unk_comp`: spikes, camera feeds, power conduits; not played). The path graph
  does not know that a door is locked, so a click on the hall sends the leader at the star door; it stands there, as a player's would.
  **The leak** was not in a walkmesh or a trigger: the bot (`nearest_foe`, 16 m through walls) ordered an attack on a guard behind the door, the attack's approach move carries a 6 s timeout
  (`fight.ctx`), and `move_to_point` took every timeout for a Force move's and placed the mover at its goal (`movement.md` 3.2 step 4: only ActionForceMoveTo* does): the leader
  stood 8.7 m on, the door still shut and locked. (Leviathan part 7, parts 10 and 17 of this log and the Endar Spire's bridge door had leaned on the same jump:
  the bot's stall check, which opens a door between it and a foe, counted only foes past 8 m; it now counts a foe out of sight too, and those parts have their real lengths.) Now only a script's force move (param 5) jumps; any other move whose timeout runs out fails. And the party arrives with the
  companions on the exit door's footprint (formation 1.5 m behind the leader in a shallow vestibule), from where no walk could start; a step now walks out of a footprint it
  starts in (`walkmap::walk_segment`). Part 16 takes the real route with the bot (`ui bot sight on`, the companions following and fighting, 3,700 frames) and drops its warps into the
  hall; the shield droids stay friendly (`ui faction`, their computers are not played).
- **Fixed (2): the Hawk's hyperdrive.** A click or `use hyperdrive` logged `route: no clear path point near the goal 49.4 12.2` because the engine walked to the
  placeable's *centre*: `PLC_Hyper` fills the neck of the engine room, its centre is 2.5 m beyond the last floor a creature can stand on, and no path point
  has a clear walk to anything inside the footprint. The original walks to the nearer of the PWK's two *use hooks* (`GetUseRange`, `0x004ee440` /
  `0x00584c20`, actions.md 1.4): here (48.5, 14.9) and (48.5, 15.4), just north of the footprint. `doors::use_point` now does that for a placeable
  (hook = the PWK's relative hook + its position, placed with the object; range radius + 0.75; no hook: the centre, as before). The part now walks the leader to
  the hook and on to the galaxy map by itself. PreciseUse (range 0.1 at the hook) is not done.
- **OPEN: the film `5_9`** (`k_sup_galaxymap` names `5_9` as the second film of the take-off, `05_8C` the first): the install's file is `05_9.bik`, the log says
  `movie 5_9 (not shown: fs::not_found)`. The original's lookup most likely fails the same way (a typo in the script); not checked against it.
- **The Elders' and the One's choice**: only the Elders' side is played (the light path). The One's deal (`unk_trapped` 10: kill the Elders for the Black Rakata), the Mandalorians'
  side quest (`unk_invis`), the genetic data (`unk_research`: the database offers it once the datapad is taken), the pillar and barrier puzzles in the cave and the Rakata
  prisoner are not played; neither is the dark side of the summit (Bastila killed or joined; the Star Forge log has the dark ending).
- **Solo mode**: `SetSoloMode(TRUE)` in the catacombs keeps Jolee and Juhani where they stand (the engine only stops them following; the original also takes them out of
  sight); the strip `switchparty` ends it on the way back, and `k_punk_sparty04` is never called in this log (the party is whole again without it).
- **Staging audit** (`stage_audit.py` on the 21 logs): the speaker is far in the Elders' talk (`unk42_redelder`, 7 to 15 m for 36 lines: the Council stays seated
  while the player stands at the door), the Duros after the ambush (4.6 to 18 m), the ritual guide (4 to 17 m: he walks up), Carth on the beach (35 m at
  the first, empty lines, 19 m at the first spoken one, 2.9 m at the third: he runs up), the cut scenes of other places (Malak and Saul Karath 80 m off in `stunt_19`,
  Dodonna and Yoda on the bridge, 15 m, in the take-off's stunt): the data's, none looks wrong in the screenshots.
- **The Sith patrols** (`unk44_sithptl*`, `darkjedim`, `drdmktwo` far from the route) are never met; the three of the hall that are in the way die from the party.
