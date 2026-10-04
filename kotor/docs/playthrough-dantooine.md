# Playthrough log: Dantooine

The main storyline of Dantooine played headless, step by step, checked against the original with logs and
screenshots: the arrival, the Jedi Council, becoming a Jedi, the three trials, Juhani, the ruins and the Star Map,
and the return to the Council. The method is [playthrough.md](playthrough.md)'s; the scripts are in
`kotor/tools/playthrough/dantooine/`.

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_dan.exe
sh kotor/tools/playthrough/dantooine/all.sh [FIRST_PART]       # the whole chain, about 8 minutes; each part loads the checkpoint the one before saved
CKPT=wake sh kotor/tools/playthrough/dantooine/run.sh NAME 02 FRAMES [FRAME:SHOT]...   # one part from its checkpoint
```

Logs are `kotor/out/pt/dNN.log`, the checkpoints `kotor/out/pt/dan_ckpt/NAME` (made by the part's `save` line and
`ckpt.sh`), the pictures `kotor/out/pt/NAME_SHOT.png`. `run.sh` takes a part number or a path to any input script, so a
one-off check starts from a checkpoint the same way. Everything runs with `FAST=1` (`--no-render --speed 8`), the
dialogue log on; `LOG=dialog,combat,routines,actions,scripts` adds the rest.

### The crafted state

Taris is not played: the game starts in `danm13` (the Ebon Hawk's landing court) with the state Taris leaves.

- The party: Carth and Bastila join (`join p_carth 2`, `join p_bastilla 0`), Canderous, Mission and Zaalbar are made
  available (`ui avail 0 1 2 6 8`). The module's load script takes Carth and Bastila out of the party again and stands
  them at the landing court, as in the original.
- The player is a level 8 soldier (`ui stat class 0 / level 8 / xp 29000 / str 16 / dex 14 / con 14 / hpmax 80`) in
  armour with a weapon (`ui stock`); the default player has no stats at all. Part 12 makes Carth a level 8 soldier
  and Bastila a level 8 Jedi Sentinel with a lightsaber and a robe (the blueprint `p_bastilla` has only clothes, the
  Taris scripts that arm her are not run), so the ruins' fights are not played by level 3 companions.
- No plot global is set by hand: the module's own scripts set `DAN_*` as the story goes. The globals that matter are
  `DAN_JEDI_PLOT` (1 the Council met, 7 the trials done), `DAN_JUHANI_PLOT` (3 redeemed), `DAN_LIFE_DONE` and
  `DAN_DEATH_DONE` (the two seals), `DAN_STARMAP_DONE` and `K_STAR_MAP` (the map).
- The conversation replies are a queue (`ui replies 1 1 3 ...`, `default 1` for the rest), each list that opens takes the
  next number. Walks across a whole module are cut with `warp` next to the door or waypoint (the transition doors, the
  triggers and the conversations are the game's); anything shorter walks (`ui goto`, `use`, `ui target` + `ui key 1`).
- Test cheats used for setup only: `ui stat`, `ui giveitem`, `ui bot god on` (the leader never dies), `cutatk` (a forced
  hit, to remove the Guardian Droids), `ui leader`, `warp`.

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch).

| # | Step | State | Script |
|---|---|---|---|
| 1 | Arrival on `danm13`: Bastila's conversation at the landing court ("they request an audience"), Carth's reply, the party leaves for the Council chamber; the Council (Zhar, Vrook, Vandar, the Chronicler Dorak) and its first meeting, `dan_council` 10 | works | `01_arrival_council.txt` |
| 2 | The night on the Ebon Hawk, Carth wakes the player, the party screen (Carth and Mission picked) | works | `01` |
| 3 | The second Council meeting (Vandar: the visions, the ruins, "training first"), the training montage (`k_player_dialog`), Zhar's first talk, `dan_trials` 10 | works | `02_vandar.txt` |
| 4 | The first test: the Jedi Code (the five precepts), `dan_trials` 20 | works | `03_code.txt` |
| 5 | The second test, Master Dorak: the lightsaber colours, the three questions, "Blue. The path of the Jedi Guardian", the blue crystal, `dan_trials` 25; `ShowLevelUpGUI`: Jedi Guardian, level 9, with skills, feats and powers taken by Recommended (Force Push, Stun; Force 46) | works (the sheet reads Soldier 8 / Jedi Guardian 1) | `04_dorak.txt` |
| 6 | Zhar and the player build the lightsaber at the upgrade bench (crystal in, Assemble); the saber is worn | works | `05_saber.txt` |
| 7 | The third trial named: the meditation grove, `dan_trials` 30 | works | `06_third.txt` |
| 8 | Out of the Enclave (`dan13_door03`), the courtyard, the Matale grounds, the grove (three module transitions by the game's doors) | works | `07_courtyard.txt` |
| 9 | The grove: Bolook's greeting (the murder case, cut short), the kath hounds (2,000 XP for the party), the cut scene `dan14_cutjuh` and the duel with Juhani; she asks for the talk when below 50 hit points and the fight stops | fixed 523f4a3 | `08_grove.txt` |
| 10 | Juhani's conversation (`dan14_juhani`, 40 nodes, the light-side replies), `dan_trials` 45, she is redeemed | works | `09_juhani.txt` |
| 11 | Back through the grounds and the courtyard to Zhar: "the grove is purified", `dan_trials` 46 and 50, `dan_council` 20 | works | `10_return.txt` |
| 12 | The Council (Vandar, started by the chamber's trigger): Juhani redeemed, "your training is complete", the ruins, `dan_ruins` 10; the party screen with Bastila forced; Ahlan Matale bursts in (`dan_romance` 10) | fixed 26f9bc0 | `11_council.txt` |
| 13 | Out to the courtyard, the ruins door `man14aa_door04` to `danm15`; the ancient droid (the Overseer): its languages, Revan and Malak, the proving grounds, `dan_ruins` 15 | works | `12_ruins.txt` |
| 14 | The proving grounds: the west computer (the datapad learns the script, then the three life-giving seed worlds) and the east one (the three death-giving ones); a wrong answer wakes a Guardian Droid | fixed 9077676 (the walk through the proving ground's door) | `13_proving.txt` |
| 15 | The trigger in front of the sealed door unlocks it and destroys the Guardian Droids; the Star Map room: the activation, Bastila's talk, `dan_ruins` 20, `K_STAR_MAP` 10 | fixed 9077676 (the map's dome) | `14_overseer.txt` |
| 16 | Out of the ruins to the Enclave, the Council on the Star Map (the four worlds, the Star Forge, `k_starforge` 1), Juhani becomes available, the Council sends the party to the ship | works | `15_council2.txt` |

Experience through the chain (the player; Carth and Mission/Bastila next): 29,000 at the start (set), 37,000 for the
first Jedi level (set, held back as the original's players are advised), 39,000 after the grove (the hounds; the
companions 2,000), 39,850 after the ruins (the Guardian Droid 25 and the computers' plot awards; the Star Map gives none
at level 9: the script's level ladder, which gives 10 to 20 points, has no branch that matches). The dialogue nodes of the
trials and of Juhani's redemption award nothing either (no plot XP on them).

## Bugs found and fixed

1. **Temporary effects never expired in modules with 0 or 1 minutes per hour** (523f4a3). `Mod_MinPerHour` is 0 or 1 for
   `danm14aa` to `danm14ad` (the courtyard, the Matale grounds, the grove, the Sandral grounds), 2 elsewhere. The clock runs
   the module's day (0 counts as 5 minutes, 7.2 million ms), but the rules library carried expiry times into the next day at
   its fixed 2 minute day (2.88 million ms), so an effect made after 2.88 million ms of the day expired a day later.
   Juhani's Improved Flurry makes a 3 second Defense penalty on every round: they piled up to a Defense of -32 and she could
   not be fought as in the original; the player's own Force effects had the same fault. `module.ctx` now sets
   `rules.settings.ms_per_day` from the clock.
2. **A script's party screen opened with the party as it was** (26f9bc0). `OnPanelAdded` (0x006beeb0) selects the current
   members only when the screen was not asked for by a script. Vandar forces Bastila with Carth and Mission already in the
   party: all three came out selected, OK brought Bastila in as a fourth who stood beside the party and was not in it. A
   script's screen now starts with the forced members only (`from_script` on `partysel_panel::open_modal`).
3. **An order that walks up to its target ran from afar when the walk failed** (9077676). Use, open, talk, lock and the
   rest queue a move, a turn and a copy of themselves; the copy skipped the range test. A walk stopped by a closed door
   (PATH_BLOCKED, the door opens in the next frame) ended with the order carried out from 40 m away: the click on the
   proving ground's computer started its conversation across the hall. The copy now checks the range again, as
   CHECKINRANGEOFOBJECT does, walks on once the door is open and is dropped after six tries.
4. **ActionPlayAnimation on a placeable showed nothing** (9077676). The action set the object's animation but not the state
   the scene plays, and `animloop01` to `animloop10` (ANIMATION_PLACEABLE_ANIMLOOP, constants 204 to 213) had no names, so
   the Star Map's dome (`animloop01` of `plc_starmap`) never appeared, nor any other computer or console animation a script
   starts. Both are in now; the dome shows during Bastila's talk.
5. Test tools: `ui stat` pushed the object's XP (0 after a load) over the rules creature's, so every cheat after a load wiped
   the player's experience; `cutatk` queued behind a follower's endless follow order and never ran.

## Notes and open items

- **The Guardian Droid** (the ruins' `dan15_guarda`/`guardb`, 224 hit points, Defense 26) is hostile on sight in the proving
  grounds, casts an energy shield on itself (`DROID_ITEM_ENERGY_SHIELD_2`: `forceshields.2da` row 1, 30 off every energy hit
  up to 300 absorbed, 200 s) and a flame thrower (30 a hit, with a short stun). A level 8 party with a level 8 Jedi does about
  nothing for the first 300 points, loses Bastila in 20 seconds and does not kill it in 100: that follows from the data (the
  shield, the three hits a round). The original ends the encounter with the door trigger, which kills both droids with 1,000
  damage once both seals are broken; the scripts do that here. The force shield and the droid's two spells are the combat
  agents' area; nothing was found wrong.
- **Force Push** from the target block (the real click on the block's icon) is cast (10 Force points, "conjures 23"), the
  Guardian Droid answers "Immune" (the shield).
- **Dark ruins.** `danm15` has no sun, no area ambient (DynAmbientColor 44,44,50) and a fog from 8 to 50 m: the pictures are
  very dark away from the lightmaps, as the data says. The Star Map hologram is bright.
- **Dialogue shots** over a crowd can have the speaker behind a party member (the Star Map talk: Bastila behind Carth);
  the camera has no obstruction test, the original's is not known.
- **The player's walk to the Council** is not played: Bastila leads the party through the Enclave (about 2,100 frames) and the
  script warps the player to the chamber's waypoint; the chamber's triggers do the rest (Vandar's talk starts by itself when
  the player steps in, which is why a script that warps in and also orders the talk collides with it).
- **Not played:** the Sandral/Matale feud beyond Ahlan's demand (`dan_romance` 10; Ahlan Matale appears in the Sandral grounds
  `danm14ad`, Nurik, Rahasia and Shen in the grounds and in `danm16`), the Mandalorian raiders (`dan_raiders`), Elise's droid
  (`dan_companion`), Bolook's murder case (`dan_murder`), the Kinrath, Sherruk; leaving Dantooine on the Ebon Hawk and the
  galaxy map with the four new worlds.
- **Crafted-state limits:** the party members are at level 8 by cheat; the player's armour and weapon are `ui stock`'s;
  Mission and Zaalbar never join in this chain.
