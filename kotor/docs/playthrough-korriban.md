# Playthrough log: Korriban

The main storyline of Korriban played headless, step by step, checked against the original with logs and screenshots, from a
crafted arrival after Dantooine: a Jedi Guardian of level 14, Bastila and Carth with the player, three Star Maps found. The method
is [playthrough.md](playthrough.md)'s and [playthrough-dantooine.md](playthrough-dantooine.md)'s; the scripts are in
`kotor/tools/playthrough/korriban/`.

**Played:** Dreshdae (the Port Authority, Shaardan and the hopefuls, the Sith thugs, the murderer, Lashowe, the medallion, Yuthura Ban),
the Academy (Master Uthar Wynn's welcome, Yuthura's plot and the Code of the Sith, the Code test, the Mandalorian prisoner, the rogue
assassin droid, the renegades in the shyrack caves, Ajunta Pall's sword), five prestige and the night, Naga Sadow's tomb (the cold
grenade, the Star Map, the sword's sarcophagus, the end of the test: Uthar killed, Yuthura spared), the way out through Dreshdae to the
Ebon Hawk, the galaxy map and the Leviathan's capture of the Hawk (the fourth Star Map). 0 script faults in the 29 parts.

**Stopped** at the capture cut scene (`ebo_m40aa`, Carth's talk about Saul Karath), where the story leaves Korriban. To resume:
`CKPT=hawk sh kotor/tools/playthrough/korriban/run.sh NAME 32 2500` replays the take-off from the Hawk's galaxy map; `CKPT=finale`
is the tomb just after the test (Uthar dead, Yuthura spared, `kor35_waysith` 56).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_kor.exe
sh kotor/tools/playthrough/korriban/all.sh [FIRST_PART]       # the chain, about 25 minutes; each part loads the checkpoint the one before saved
CKPT=academy sh kotor/tools/playthrough/korriban/run.sh NAME 11 FRAMES [FRAME:SHOT]...   # one part from its checkpoint
sh kotor/tools/playthrough/korriban/sum.sh kotor/out/pt/NAME.log [FIRST_FRAME]            # the story lines of a log
sh kotor/tools/playthrough/korriban/audit.sh [PART...]                                    # the staging audit of the chain's logs
```

Logs are `kotor/out/pt/kNN.log`, checkpoints `kotor/out/pt/kor_ckpt/NAME` (the part's `save` line and `ckpt.sh`), pictures
`kotor/out/pt/kNN_SHOT.png` (`all.sh` takes one 30 frames before the end of each part). Everything runs with `FAST=1` and
`LOG=dialog,combat`. `all.sh` checks after each part that the log holds the line the part was written to produce (a conversation that
ended, a journal state, a global) and stops at the first that does not; part 12 retries with the other answer when the Code test's
random question was the other one. The helpers: `hasitem.sh MODULE WORD [utc|utp|dlg]` (which templates of a module name an item or a
script), `trigs.sh MODULE TAG...` (a trigger's outline in world coordinates and its enter script), `sum.sh`, `audit.sh`;
`python kotor/tools/py/dlgtree.py RESREF` prints a conversation as a tree, which is how the `ui replies` lines were written.

### The crafted state

- `--module korr_m33aa` (the module's entry point is the Hawk's landing spot). The player is a Jedi Guardian of level 14 made by
  `ui jedi 3 14` (alignment 85, light), robe and lightsaber worn, Persuade 17, Computer 10, Awareness 10; Bastila a Sentinel and Carth
  a soldier of level 14; Canderous, HK-47, Jolee, Juhani, Mission, T3-M4 and Zaalbar available. 2,000 credits.
- Three Star Maps: `K_STAR_MAP 30`, `DAN_STARMAP_DONE`, `K_STAR_MAP_TATOOINE`, `K_STAR_MAP_KASHYYYK`. `ui planet 3..7` puts the five
  worlds on the galaxy map, as the story's scripts would have (a new test command: nothing else in a crafted start does).
- No Korriban global is set by hand. The ones that matter: `KOR33_MEDALLION` (set by the Academy Entrance guard: until then the
  thugs, the murderer and Yuthura are not in Dreshdae), `KOR_THUG_DEATH` (the murderer's scene waits for four dead thugs),
  `KOR_SITH_PRESTIGE` (5 are needed: `k35_uth_presfini` is `> 4`), `KOR_SITH_CODE`, `K_STAR_MAP_KORRIBAN`.
- Replies are a queue (`ui replies ~words ... default 1`): `~` takes the first reply whose text has the words (underscores are
  spaces). A list that has no such reply takes its first and says so in the log, so a queue is checked against the log's
  `dialog reply N "..." (chosen)` lines. Walks across a module are cut with `warp TAG party` / `warpxy X,Y party` next to a door or
  into a trigger strip; the doors, the area changes, the triggers and the conversations are the game's.
- Test cheats used for setup only: `ui jedi`, `ui stat`, `ui giveitem`, `ui credits`, `ui gbool`, `ui global`, `ui planet`,
  `ui bot on/god on/route` (the fights of the thugs, the murderer, the droid tomb, the cave beast and Uthar), `ui heal` (the bot's
  god mode leaves Min1HP set and it is saved: a part after a god-mode fight heals first), `ui unlock`.

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | Arrival at Dreshdae's docking bay (a dark steel hall), the crafted party, the HUD | works | `01_arrival.txt` |
| 2 | The Port Authority (`kor33_portauth`, trigger `k33_trg_initport`): the Twi'lek official knows a Jedi by the saber and the robe, "How do you know I'm a Jedi?", the 25 credit fee (`K_KOR_PORT_FEE`, the door opens), the Star Map question. Without robe and saber (`disguise.txt`) he greets "the owner of the Ebon Hawk" instead | works | `02_port.txt` |
| 3 | Shaardan and three hopefuls (`kor33_shaardan`): 3,900 frames of lines, then "Why? What did they do?", "Let them go.", "[Persuade] They aren't worth your time." (mercy; three `AdjustAlignment`: 85 to 90). The other way, "Kill them, I don't care." (Bastila and Juhani object, `k_act_darkmed`): 85 to 77 (`dark_shaardan.txt`) | works; the talk ends "aborted" (see Observations) | `03_shaardan.txt` |
| 4 | Through the gate to the Academy Entrance (`korr_m33ab`): the guard turns the Jedi away, "What's this medallion you mention?", "How do I become a Sith, then?" (`KOR33_MEDALLION`, journal `kor33_enteracademy` 25); Mekel lets hopefuls die at the door | works | `04_gate.txt` |
| 5 | Back in Dreshdae the arrival waypoint lies in the strips `k33b_trg_spwnthg` and `k33b_trg_spwnmrd`: four thugs, the murderer and his victims, and Yuthura Ban are made | works | `05_return.txt` |
| 6 | Four Sith thugs (`kor33_siththug1`, strip at 198,188): "Are you sure you want to die?", "Take another step and I'll show you.", the fight (Force effects, sabers, 270 XP), the leader's remains hold a Sith medallion, taken with clicks (hover, click, click, Get Items). Two bugs here: a loaded game's creatures left no loot, and the emptied bag stayed | fixed b1ffae3, 4eb3918 | `06_thugs.txt` |
| 7 | With four thugs dead the murder strip starts its scene (`kor33_murderer`): "Sorry, but I'm not going to let you kill that woman.", the fight, the second medallion in his bag | works | `07_murder.txt` |
| 8 | Lashowe and her friends in the market (`kor33_lashowe`): "no need for hostilities", the Mandalorian joke by [Persuade] (she likes the Jedi, `k33_las_like`) | works | `08_lashowe.txt` |
| 9 | The guard with the medallion (`k33_acg_medalion`): "Yes. Today, in fact.", "They are my slaves." (Carth and Bastila answer), journal 46 | works | `09_guard.txt` |
| 10 | Yuthura in the cantina: "I took it from another student", "Yes, that's exactly why I'm here", she sees the Jedi ("Obviously you are a Jedi"), the Jedi denies it and lies ("[Lie] Yes, it does."), "They are slaves.", "Yes, I am." (`k_pkor_start35`); the Academy: Uthar's welcome to the five hopefuls (Lashowe, Mekel, Shaardan, the player), "I am ready to learn more.", journal `kor35_waysith` 10, the passcard, +1,000 XP | works | `10_yuthura.txt` |
| 11 | Yuthura in the Academy (`kor35_yuthuraban`, 9,000 frames): the favourite prospect, her plot against Uthar ("Very well. I agree.": `kor35_doublecross` 10, `kor33_findstarmap` 30), the Code of the Sith line by line | works | `11_yuthura.txt` |
| 12 | Uthar's Code test (`k35_uth_prescode`): Passion, Strength, Power, Victory, "...my chains are broken.", then a true/false question picked by `Random` (in the replay "there is nothing worse than love": False); prestige 1, XP | works; the question depends on the dice | `12_code.txt` |
| 13 | The Mandalorian prisoner (`kor35_torturer`, `kor35_victim`, the serum console): whisper, [Persuade], then [Computer Skill] to put him into a catatonic state (journal `kor35_mandalorian` 40, the cache told: a trap door in his ship). High dosage twice shocks him (journal 60, `k_pkor_tortdark`, alignment 91 to 85: `dark_torture.txt`) | works | `13_mandalorian.txt` |
| 14 | First report to Uthar (`k_pkor_cacheplot`): prestige 2 | works | `14_report1.txt` |
| 15 | Out of the Academy to the Valley of the Dark Lords (`korr_m36aa`) | works | `15_valley.txt` |
| 17 | The rogue droid's tomb (`korr_m38aa`, a corridor of 164 m with mines, rockfalls and Mark IV war droids): the bot walks it in god mode; the assassin droid ("Too much audio input! Audio systems overloading!": the party's noise makes it hostile), journal `kor38_roguedroid` 30. Not in god mode the three die in about 6,000 frames and the "entire party has been killed" box shows | works | `17_droid.txt` |
| 18 | The shyrack caves (`korr_m34aa`, strip `k36_trg_k34`): Thalia May and the renegades, "Slow down and tell me what you're doing here", "Maybe I can help you", [Persuade], "I can try." (journal `kor35_renegadesith` 20) | works | `18_caves.txt` |
| 19 | The beast at the passage (`kor34_monster`) is killed by the bot in god mode | works (the camera: see Observations) | `19_beast.txt` |
| 20 | Thalia again: "It's clear. You're free to go." needed `k_pkor_webclear` = `GetIsDead(GetObjectByTag("kor34_monster"))` of a body that is gone: the renegades attacked instead. Journal 40, +1,950 XP with the beast, alignment 92 to 94 | fixed e2a06c8 | `20_free.txt` |
| 21 | Second report: the droid ("I dealt with the rogue droid in the tombs.": 40) and the renegades ("[Lie] It's done. They are... gone.": 60): prestige 4 | works | `21_report2.txt` |
| 22 | Ajunta Pall's tomb (`korr_m37aa`), the burial chamber (the way in is not played): the sarcophagus opened with clicks (the world fades out for the loot panel; closing it shows the spirit standing at the door), the strip `k37_trg_ajunta` starts his talk, his riddle of the sword, journal `kor37_ajuntapall` 10 | works | `22_sword.txt` |
| 23 | The three swords (Get Items), the statue (`k37_statue`: "[The notched steel sword.]"), the spirit's thanks: the Jedi urges him back to the light ("[Persuade] I don't believe the light side would turn you away"), alignment 94 to 96, journal 30, +1,000 XP; Ajunta Pall's Blade in the bag | works | `23_statue.txt` |
| 24 | Third report ("I have the sword of Ajunta Pall."): prestige 5, Uthar declares the final test (journal `kor35_waysith` 30); `k_pkor_nightcut`: the fade, the party in the hopefuls' room | works | `24_report3.txt` |
| 25 | "I am ready to go." The Hawk's companions are not permitted ("[A day passes in preparation...]"): Naga Sadow's tomb (`korr_m39aa`) alone with Uthar and Yuthura, the test explained, "Find the Star Map. Return with the lightsaber." | works | `25_final.txt` |
| 26 | The tomb, alone (9,600 frames): the bot walks the northern branch in god mode (wraids, the Terentatek's cut scene `kor39_cut_terent`, two rancors), the lever `k_kor_openlever` opens the door `k39_door_trap4`, the Pillar of Ice holds the cold grenade (clicks, Get Items); the acid room (`k39_plc_acidpool`): "[Launch the special cold grenade at it.]" freezes the pool. The pillar puzzle in the south and the fire pillar are not played | works (the acid talk ends "aborted": the last script destroys the wall that owns it; the camera: see Observations) | `26_tomb.txt` |
| 27 | The Star Map room (strip `k_kor_star_map`): the hologram sphere over the pedestal (a picture), `K_STAR_MAP 40`, `K_STAR_MAP_KORRIBAN`, journal `kor33_findstarmap` 40 and `k_starforge` 10, +250 XP | works | `27_starmap.txt` |
| 28 | The Sith lightsaber from the sarcophagus beyond (`k39_itm_cersaber`); passing the strip `k_kor_uthar_move` brings Uthar and Yuthura to 89,106-109 (`k_pkor_utharmove`), the strip `k_kor_utharcut` starts the end of the test (`kor39_utharwynn`: "I'm with Yuthura on this one"), Uthar's fight (bot, god mode; a solo level 14 Jedi without god mode is down in 400 frames), Yuthura turns, yields, "Go on. Get out of here." (journal `kor35_waysith` 56, alignment 97, XP 104,970) | works | `28_saber.txt` |
| 31 | Leaving: tomb door, the Valley (the party waits at the Academy's exit and rejoins), the Academy, the Entrance, Dreshdae, the strip `k33_trg_ebonhawk`: aboard the Ebon Hawk (`ebo_m12aa`) | works | `31_hawk.txt` |
| 32 | The galaxy map on the Hawk (`galaxymap`): five worlds, Manaan picked, "Travel": with `K_STAR_MAP` 40 the take-off is the Leviathan's capture (`stunt_16`, `ebo_m40aa`, Carth's talk about Saul Karath) | works | `32_galaxy.txt` |

(Parts 16, 29 and 30 were scouting runs and are not in the chain.)
**Asides** (each from a checkpoint of the chain, not part of `all.sh`; run with `CKPT=NAME sh .../run.sh NAME2 PATH-TO-SCRIPT FRAMES`):
`26p_pillars.txt` (from `tomb`) the pillar puzzle in the tomb's southern branch: the computer `k39_plc_pillcomp` and `kor39_pillar`, four
systems on three pillars, the 15 moves of the Tower of Hanoi as `ui replies ~from_the_left_pillar ~The_middle_pillar ...`; the read-out's
`<CUSTOM10..12>` come out as "Active systems - left pillar: Base System, Mid-Lower System, ...", the rings move from pillar to pillar, no
overload, and the talk ends normally after the last move (18,700 frames of lines). `28b_redeem.txt` (from `map`) the redemption ending below.
`dark_shaardan.txt` (from `port`), `dark_torture.txt` and `dark_kel.txt` (from `code`) the dark replies (Kel's "You're no Sith" is guarded by `k_con_dark`: a light Jedi is not offered it). `disguise.txt` (from `dock`) the Jedi without
robe and saber. `dustil.txt` (from `valley`) the attempt to spawn Carth's son.

Experience and alignment through the chain (the player; Carth and Bastila hold the same XP from the party pool): 91,000 at the start
(level 14), 91,270 after the thugs, 92,420 on joining, 93,545 after Yuthura's lessons, 93,670 the Code, 98,920 after the droid tomb and
the caves' fights, 100,870 the renegades freed, 102,070 the spirit, 102,370 prestige 5, 104,565 the Star Map, 106,215 the end of the
test (the quest steps' own XP is paid since the merge of 72f22f0; before it the same points were 101,570, 102,770, 103,070, 103,320 and
104,970). Alignment (0 dark, 100 light): 85 at the start, 90 Shaardan's mercy, 91 the murderer, 92 the cache, 94 the renegades, 96 the spirit,
97 the end. The dark choices checked: Shaardan "Kill them" 85 to 77; the serum console twice at a high dose 91 to 85. `ui rules` now prints
the alignment (the rules' value and the engine's copy, which always agree here) and XP.

## Bugs found and fixed

1. **A loaded game's creatures dropped nothing** (b1ffae3). The save writer left `Dropable` out of the items of a creature's `ItemList`
   and `Equip_ItemList`; the reader gives a saved item `droppable` from that field, so after any load every creature died without a body
   bag. The Dreshdae thug leader's Sith medallion, which the story needs, never came out of the replay's checkpoint.
2. **A looted body bag stayed forever** (4eb3918). `DieWhenEmpty` is `not corpse` for a bag (party-items-saves.md 5.7); `spawn_body_bag`
   never set it, so every "Remains" stayed in the world, empty, and the pick of the next one (`hoveron =Remains`) took the empty one.
   The flag is saved as well. Checked with clicks: after Get Items the bag is gone from the selectable objects.
3. **`GetIsDead` of an object that is not there is TRUE** (e2a06c8). The original's handler (`0x0053ecb0`) starts from 1; ours gave 0
   for a missing object. `k_pkor_webclear` asks that of the cave beast, whose body is destroyed after its death: the renegades never
   believed the passage clear and attacked.
4. **Under `--speed 8` a script's fade after a conversation ran 8 times too slowly** (play.ctx). The dialogue layer's fade, bars and bark
   clocks stepped by one tick's time per presentation step instead of the skipped ticks' as well: the 2 s fade-in after joining the Sith
   was still black 15 s later in the pictures (`k10_end.png` was black; at `--speed 1` it is clear 50 ticks after the conversation). The log
   was the same, only the pictures lied. Fixed: the owed time goes to `dlgview::pre_sync`; the Endar Spire replay is unchanged.
5. Test tools: `ui rules` prints the alignment and XP; `ui planet N [0|1]` puts a world on the galaxy map in a crafted start.

## Observations and open items

- **The conversation is "aborted" when its last node destroys the owner** (Shaardan's last reply destroys him and the hopefuls, the acid
  wall's `k_pkor_destacid`): `dialog aborted: owner N valid false` and the end-of-dialogue scripts of the area's creatures are not run.
  The original's `DestroyObject` is a queued event; whether the conversation there ends normally is not known. Harmless so far.
- **A loaded save re-runs the OnEnter of the strips the party stands in** (`k33_sha_initconv` three times at frame 3, `k33b_murder_init`
  at frame 1 after loading a checkpoint saved inside them). The scripts that guard themselves with a local flag are unaffected; the
  original restores the occupant lists with the save (not verified).
- **The camera inside big creatures**: in the caves' beast fight and in the tomb's rancor fights the creature's body fills the picture (the camera has
  no obstruction test by creatures, as in the Dantooine log).
- **Naga Sadow's tomb and the Valley's lit rooms**: the player reads as a nearly black silhouette against the lit door (room light
  0.07 to 0.16 and ambient 0.13/0.13/0.22 on him). Not compared with the original.
- **Data, not ours**: `kor33_murderer`'s entry 8 names `kor33_czerkagrd` as the listener (a typo for the victim): the shot looks
  across Dreshdae at a guard 54 m away.
- **The test bot**: its tour in Ajunta Pall's tomb stops at 88,24 (it keeps targeting the bridge droids across the chasm); with `bot on`
  after Yuthura leaves it starts her conversation again and again (0 nodes, "aborted"); `ui bot god on` is saved as Min1HP.
  `warp TAG party` can put the leader outside every room (`rooms 9/-1` in the Mandalorian room's audit).
- **Staging audit** (`audit.sh`): only the strip-started talks are far (Shaardan's group 9 to 13 m from the player who enters the
  strip's corner, the murder scene's victims 9 m); the Mandalorian room's `rooms -1` is the warp's; the Star Map speaks to the trigger
  that owns it; the Leviathan scene is a cut scene.
- **The other ending, played** (`28b_redeem.txt`, from `map`): with `KOR_YUTHURA2 3` set by hand (`k_pkor_knyuth02`; her personal talks in
  the Academy would set it over several visits) the yielding Yuthura offers the friendship branch: "You ask for mercy? You, a Sith?", "I can't
  talk about that.", "Tell me why you tried to kill me, first.", "[Persuade] Maybe you *should* think about it.", "There's still time to change
  that." (`k39_yth_redeem`, journal `kor35_waysith` 60, alignment 98). The Valley's guards (`kor36_endsith1..3`, strip `k_kor_endacademy`) are only
  made for `KOR_FINAL_TEST` 4 or 7 (the chain's ending leaves it at 5): nobody waits at the Academy's exit.
- **Not played**: the way into Ajunta Pall's tomb (mines, the heat and cold plates, the bridge droids, the lever) and the first
  Shaardan scene at its door; Naga Sadow's tomb's fire pillar and the room the pillar puzzle unseals; the rogue droid's peaceful repair puzzle; Jorak Uln's tomb and Mekel there; Kel Algwinn; Lashowe's holocron and the tuk'ata
  queen; the Mandalorian's weapon cache; the two endings where Yuthura dies; the poison plots (Yuthura's device and Adrenas, Uthar's
  datapad); the Academy after the test; Dustil, Carth's son (the Academy's enter script makes him when `KOR_DUSTIL_SPAWN` is set, and
  nothing in this chain sets it: it belongs to Carth's Hawk talk, `K_SWG_DUSTIL1`/`KOR_DANEL`; setting it by hand, `dustil.txt`, did not
  make him); Belaya (needs a Juhani who died on Dantooine); the Xor ambush; shops; the swoop point.
