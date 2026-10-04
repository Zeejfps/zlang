# Playthrough log: Tatooine

The main storyline of Tatooine played headless, step by step, with logs and screenshots. The method is
[playthrough.md](playthrough.md)'s and [playthrough-dantooine.md](playthrough-dantooine.md)'s: a crafted arrival state, then real
input (the bot walks, conversations are answered by a queue of words, menus are clicked). The scripts are in
`kotor/tools/playthrough/tatooine/`.

**Played to the end of the planet** (parts 1 to 20, 0 script faults): the Krayt dragon (Komad's plan), the Star Map, Calo Nord's ambush, Czerka's reward, and the
Ebon Hawk to the galaxy map and on to Kashyyyk. Not played: the mines-and-cave way to the dragon (the fight in the lair), Darth Bandon's ambush (K_KALO_BANDON 30, see
"Calo Nord or Darth Bandon"), the side quests listed at the end. The chain starts from the crafted arrival and keeps its checkpoints in `kotor/out/tat_cp` (ignored by
the repository: `all.sh` rebuilds them, about 15 minutes; the last part, `20_travel.txt`, saves `kas_arrival`).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_tat.exe
sh kotor/tools/playthrough/tatooine/all.sh [FIRST_PART]       # the whole chain, each part loads the checkpoint the one before kept
LOAD=kotor/out/tat_cp/fodder sh kotor/tools/playthrough/tatooine/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]...   # one part
```

`run.sh` is fast (`--no-render --speed 8`) with its own saves directory (`kotor/out/saves_tat`); logs `kotor/out/pt/NAME.log`,
pictures `kotor/out/pt/NAME_SHOT.png`, checkpoints `kotor/out/tat_cp/NAME` (a part's `save` line, `keep.sh NAME` copies the newest).
Helpers: `nss.sh` (the install ships the NWScript sources of about 120 Tatooine scripts: extracted to `kotor/out/nss`), `findres.sh WORD`
(which resources of the Tatooine modules mention it), `factions.sh`, `pthroute.py` (a route along an area's path graph), `areas.sh`, `dlgs.sh`.

### The crafted state

The module `tat_m17ab` (the docking bay the Ebon Hawk lands in) with the state Dantooine leaves: Carth and Bastila join at frame 5 (joined
earlier they are left at 0,0 until the module places them), Canderous, Juhani, Mission and Zaalbar are available; the player is made a
Soldier 8 / Jedi Guardian 1 (37,500 XP) by the rules' own auto level-up (`ui xp`, `ui addclass 3`, `ui autolevel`), Carth a Soldier 8 and
Bastila a Jedi Sentinel 8 the same way (`ui leader`, `ui autolevel`); the player and Bastila get a lightsaber and a Jedi robe; 3,000 credits.
Other cheats, all for setup: `ui gold` (5,000 for HK-47, 100 more for the vaporators), `ui heal` and `ui stat hp 127` at the start of a part,
`warpxy` to cut the dunes' hidden path (part 12), `ui loot` (the loot panel without the walk). Everything else is the game's.

The Eastern Dune Sea (`tat_m18ac`) has one safe way through the dunes: `tat18_duneedgetr` triggers fire the "lost in the dunes" talk and a jump
back for any step over the edge bands. The path graph (`.pth`) has shortcuts that cross the bands, so the bot must follow explicit `X,Y`
stops (computed in the scratchpad from the graph with the bands cut out; the list is in part 11).

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch).

| # | Step | State | Script |
|---|---|---|---|
| 1 | Docking bay: the customs trigger starts the officer's conversation, the 100 credit fee (Persuade fails at skill 0, pays), Jorul Kurax, out to Anchorhead | works | `01_dock.txt` |
| 2 | Czerka office `tat_m17ag`: the conservationist, the Protocol Officer, "no way to get a license?", the bounty on the Sand People: Hunter's License, `tat17ag_sandbounty` | works | `02_office.txt` |
| 3 | Across Anchorhead (the conservationist's talk, the Dark Jedi ambush, banter) to Yuka Laka's shop `tat_m17ac`: HK-47 for 5,000, the party screen (HK-47, Bastila) | fixed (HK-47's XP catch-up, party screen) | `03_hk47.txt` |
| 4 | Iziz the Jawa (the Star Map question, the rescued tribe), the gate guard: license shown, the Dune Sea `tat_m18aa` | works | `04_gate.txt` |
| 5 | The Dune Sea to the strip of the Sand People Territory; wraids and raiders fought by the bot | works | `05_dune.txt` |
| 6 | The fallen raiders looted; the Sand People Clothing put on from the equip screen (OK, then the heartbeat sets `tat_TuskenSuit` and the party is drawn as Sand People) | fixed (equip OK on a stack; save keeps standings; disguise appearance) | `06_loot.txt` |
| 7 | The Territory and the Enclave `tat_m20aa` in disguise: the warrior, the Chieftain through HK-47, "a peaceful solution", the price: two moisture vaporators; the clothing is taken off the party | works | `07_chief.txt` |
| 8 | Back to Anchorhead: the gaffi sticks redeemed, the vaporators bought from the Czerka store manager (400) | fixed (bot talk stops) | `08_vapor.txt` |
| 9 | To the Chieftain with the vaporators: peace, the Chieftain's Gaffi Stick, the Map of the Eastern Dune Sea (`tat_KraytMap`), `tat17_starmap` 40, what a krayt dragon is | fixed (GetItemPossessedBy) | `09_peace.txt` |
| 10 | Out through the Territory and the Dune Sea to the Eastern Dune Sea `tat_m18ac` (the strip lets the map through) | works | `10_krayt.txt` |
| 11 | The dunes' safe path to the hunters' camp; the hunter, Komad Fortuna's offer (the mines, the banthas, the fodder), `tat18ac_dragonhunt` 20 | works | `11_komad.txt` |
| 12 | Back to the Enclave (the hidden path cut with a warp) for the Bantha Fodder (the ragpile `tat20_ragpile`) | works | `12_fodder.txt` |
| 13 | Back to Komad with the fodder (the route of parts 10 and 11 in one go): "Look, I have your fodder", the banthas spawn (`k_ptat_spwnbanth`), `tat18ac_dragonhunt` 30 | works | `13_bantha.txt` |
| 14 | The herd: the first bantha (`tat18_bantha1`, 203 167): the fodder in the bag makes the herd fall in step (`k_ptat_banthcut1`, journal 50), the deep desert's Elite Warriors ambush (four, 120 hit points, 200 XP each; the fight lasts 4,000 to 8,000 frames, so the save waits for the leader to stop fighting: `savewhen`) | works | `14_herd.txt` |
| 15 | Talking to a bantha again (`k_ptat_ambushed`, `k_ptat_banthcut2`) puts herd and party at the camp; Komad: the banthas are in position (`k_ptat_banthabmp`, 60), the krayt dragon comes out of its lair (`k_ptat_spwnkrayt`, nine cut scenes: Komad, the dragon, the banthas, the mines) and dies in the cut scene; Komad thanks the party, gives a Krayt Dragon Pearl (`k_ptat_give1pear`) and leaves (`k_ptat_komadgone`); `tat18ac_dragonhunt` 70, `tat17_starmap` 80 | works | `15_lead.txt` |
| 16 | The lair: along the dunes' path; the trigger at 370 348 (`k_trg_calonord2`) arms Calo Nord's ambush (K_KALO_BANDON 10 becomes 20); the Star Map (`K_TAT_STAR_MAP`, `k_tat_pla_actmap`, then `tat18_starspeak`): the hologram sphere, HK-47's and Bastila's lines; `tat17_starmap` 90, `k_starforge` 20, K_STAR_MAP 10, K_STAR_MAP_TATOOINE | works | `16_cave.txt` |
| 17 | Out of the lair: `tat_test` (319 312) starts Calo Nord's talk with the invisible talker (`ambush_test`: "You got lucky on Taris; the Sith attack saved you..."); he and his four thugs fight the party (900 XP for Calo, 50 to 500 for the thugs) | works | `17_calo.txt` |
| 18 | Home: the dunes' safe path, the Dune Sea, Anchorhead (Sennivek's "you dropped something" talk, journal `Genoharadan` 1), the Czerka office: "I have gaffi sticks to redeem", the Chieftain's Gaffi ("Yes, here it is."): `tat17ag_sandbounty` 150 (end), 500 credits | works | `18_back.txt` |
| 19 | The docking bay and the Ebon Hawk's ramp (`EbonHawk`, to `ebo_m12aa` at `K_EBN_RAMP_ENTRANCE`); the player is alone at the ramp (`k_pebn_pophawk` puts the companions at their places in the Hawk) | works | `19_hawk.txt` |
| 20 | The galaxy map and the landing: see "Travel" below | works; open items there | `20_travel.txt` |

Experience: the player 37,500 at the start, 38,850 after HK-47 (quest awards), 43,350 with the Chieftain (peace), 44,150 after the herd's ambush, 46,150 after Calo Nord and his thugs.
The journal entries (the Star Map, the hunt, the Czerka bounty) award nothing; XP comes from the conversation nodes and kills, as on the other planets.
The license (`k_ptat_bountyset`) and the bounty gave none at level 9: the script's level ladder has no branch for it, as on Dantooine.

## Bugs found and fixed

1. **`ui xp N` printed zeros** (c52c096): the report helper added for `ui xp` (no argument) took the word first.
2. **The test bot never entered a trigger** (86bd1ef, dfb95fa, ab7c2d5, 28ef0b0, 372d6f9): a stop that is a trigger is walked to the middle of its polygon,
   from the polygon's own height (the Dune Sea's hills); a crossed transition trigger counts as reached; plot creatures are not attacked; `@TAG`
   talks once within eight metres and ends when the talk is over; `X,Y` stops.
3. **A recruit joined with 0 XP** (cf9baa1): the rules had `JoiningXP` and the catch-up but nothing called them; HK-47 at level 6 into a party at
   38,000 XP now takes his share when spawned (re/party-items-saves.md 3.4).
4. **The equip screen's OK did nothing for a stack** (a6b83d0): the preview puts one of the stack on (a new item), OK compared ids, failed
   silently, and Escape took the preview back; the Sand People Clothing (x7) could not be put on with OK.
5. **A save held no faction standings** (9ee4d51): `AdjustReputation` changes were lost on load while `tat_TuskenSuit` stayed set, so every Sand
   Person attacked a party the scripts took for disguised. `repute.fac` is in SAVEGAME.sav now.
6. **EffectDisguise changed nothing on screen** (cf80e35): the rules' APPEARANCE event had no consumer; creatures carry the
   appearance row of their disguise and the scene draws it (also after a load: it follows the effects).
7. **`GetItemPossessedBy` ignored worn and wielded items** (bc316ae; the original asks the inventory, then the 18 equipment
   slots, 0x0053a390): the Chieftain keeps his gaffi stick in his hand, so `k_ptat_givegaffi` gave nothing and the Czerka bounty could not be paid.
8. Test tools: `ui clickctl LB_ITEMS ~some_words` (a row by its text, scrolled into view), `ui where` prints the faction, `ui hostiles` the standing.

9. **The chain drifted** (the engine moved under the scripts since the first run; found by rebuilding every checkpoint). Part 6: a `Get Items` click on a body whose panel
   did not open landed on Bastila and started her conversation, which blocked the equip screen (`hush`, `ui close` added): without the Sand People Clothing on, the ambush at
   the Territory's edge turned into a war and the Chieftain died (journal 126). Part 8: the party's purse is 350 after the bounty on the sticks and the vaporators cost 400
   (`ui gold 200`). Part 14: the ambush takes 4,000 to 8,000 frames, so its checkpoint is a `savewhen` that now also waits for the leader to leave combat (game/play.ctx).
10. **A save in the middle of the ambush** is what `savewhen` without that wait gave: the bot walked out through the dune edge and the "lost in the dunes" talk jumped it back.
11. **The planner ran into Calo Nord's landspeeders** (fixed in this branch). His vehicles (`ambush_speeder2`, a 3 x 8.75 m footprint each, plc_lndspdr3.pwk) stand on the camp
    road, and the path graph's shortest edge (point 220 to 215 of the area's PTH) runs through them: the graph was authored without them. The planner searched the graph
    without asking whether an edge was walkable and string pulling pushed the next graph point untested, so the leader walked into the footprint and stood at its edge for ever
    ("move: blocked"). The search now skips an edge that an active placeable's walkmesh stands on (`walkmap::meets_placeable`, a door's does not count: it is opened on arrival),
    which sends the route round them (219, 218, 212). Part 18 no longer warps the party past them.

## Notes and open items

- **Not a bug:** the Dark Jedi trio in Anchorhead's plaza and the Dune Sea entry bounty hunters (`k_genoharadan`) fight the party; the bot's god mode
  keeps the leader at 1 hit point, so a part's checkpoint can have everyone at 1 HP (`ui heal` + `ui stat hp 127` at the next part's frame 4; the
  leader is not set before frame 4).
- The player's portrait (the default test player has none) is not set, so the equip screen's change-member buttons show the previous member's
  picture after a switch (a real player has a chargen portrait).
- Reply words with an apostrophe do not match (`~such_an_honor`, not `~If_it_s_such`).
- `bot: no nearer ... opens door N` and `stuck` lines are the bot's, not the game's.
- Long moves in the open (the Dune Sea) fail at the planner when the goal is not near a path point: routes name waypoints near doors
  (`tat17ag_tat17aa` before the office door), not the door.

- **Calo Nord or Darth Bandon** is one counter, K_KALO_BANDON. `k_sup_galaxymap` makes it 10 when the Hawk takes off from Dantooine (K_KOTOR_MASTER 15, counter 0: part 1 sets it by hand);
  the trigger at the Star Map (370 348, `k_trg_calonord2`) spawns Calo's gang at the camp when it is 10 (and makes it 20) and Bandon's (`tat_bandon_thug*`, `wp_tat_bandon`) when it is 30 (and
  makes it 40); `tat_test` at the cave mouth starts the talk for either. The map script makes 20 into 30 at a takeoff when K_STAR_MAP is 30, so Calo meets the party at the first Star Map planet
  and Bandon after the third map. The Kashyyyk (`k_pkas_ambush`, in `kas_m24aa` by the camp fire), Korriban (`k_pkor_ambush`) and Manaan (`k_pman_enemy01`) scripts read the same counter.
  Nothing fired early in this branch: Kashyyyk's trigger sees 20.
- **Travel** (part 20; from the Hawk checkpoint of part 19). The Hawk module `ebo_m12aa` fills with the companions (`k_pebn_pophawk`); the first walk to the console
  `GalaxyMap` (51 73) starts `ebo_galcam` and Bastila's vision (`ebo_bast_vision`); `use GalaxyMap` runs `k_pebn_galaxy`, which sets the planets from K_KOTOR_MASTER (20: Dantooine is on the map
  but cannot be picked, Tatooine, Kashyyyk, Manaan and Korriban can) and opens the map (`galaxymap.gui`: five dots over the galaxy, the picked planet's name, description and model; Travel is
  dimmed until a planet is picked). A click on `LBL_Planet_Kashyyyk` and on `BTN_ACCEPT` runs `k_sup_galaxymap`: the vision has not been played, so the flight cut scene `stunt_00` (`cut00_convers`)
  comes first and the party is back in the Hawk with the vision, K_CURRENT_PLANET 20; the exit trigger `ebn12_ebonexit` (`k_pebn_leavhawk`) opens the party screen (two free places: Bastila and
  HK-47 by two clicks, OK) and `k_pebn_exithawk` starts `kas_m22aa` at `k_kas_ebon_hawk_transition`, where Janos Mercer's docking talk begins. Not fired in this trip, as the script's conditions
  say: the Calo stunt (K_STAR_MAP 30), the Leviathan capture (K_STAR_MAP 40 with K_CAPTURED_LEV 5), the random attack on the way (`m12ab`, the turret minigame: a d100 in
  `ST_PlayPlanetToPlanet`, which this trip never reached). K_KOTOR_MASTER 20 and K_CURRENT_PLANET 35 are set by hand in part 20: in part 1 they make the companions ask to be talked to
  (`k_hbas_dialog` "Bastila seems to have something on her mind") and move the reply queues of the whole chain. Bastila's vision plays twice (before the takeoff and after the flight); the first
  is the one the console's first visit triggers, the second the flight's; the original's count was not checked.
- The HK-47 and Bastila XP lag the player's (38,650 and 37,300 against 46,150 at the end): they joined with the catch-up of their level at the time.

## Not played

The mines-and-cave way to the dragon (take Komad's mines or fight the dragon in the lair: `k_ptat_kraytuser`, `tat18_kraytdrag` at 367 335), Darth Bandon's ambush (set K_KALO_BANDON 30 before the
trigger at the Star Map), the swoop track, the cantina and Komad's lodge, Fazza, Jawa rescue (`tat17aa_jawarescue`) and the war with the Sand People (take the bounty, do not wear the clothing,
kill the Chieftain), Marlena Venn and Tanis (`tat18aa_tanistrapped`), the Ithorian, Jawa traders, the random attack on a flight.
