# Playthrough log: Manaan

The main storyline of Manaan played headless, step by step, checked against the original with logs and screenshots, from a crafted
arrival after Dantooine (a level 12 Jedi, Bastila and Carth, one Star Map found): the docking bay, Roland Wann and the three ways into
the Sith base, the prisoner's interrogation, the Sith Embassy and its base, the Selkath arrest and the player's own trial, the
submersible, the Hrakert Station, the environment suit and the walk on the sea floor, Kolto Control, the Hrakert Rift and the Star Map.
The method is [playthrough.md](playthrough.md)'s and [playthrough-dantooine.md](playthrough-dantooine.md)'s; the scripts are in
`kotor/tools/playthrough/manaan/`.

**Where it stops, and how to resume.** Played: everything above, 0 script faults, to Wann's debrief on the surface (the quest `man_planet`
ends, journal 70) with the Star Map in the bag. Not played: leaving Manaan (the Ebon Hawk's trigger `man26ad_to12aa` in the docking bay),
the galaxy map, and the optional quests (below). `CKPT=surface sh kotor/tools/playthrough/manaan/run.sh NAME SCRIPT FRAMES` starts at Wann's
door in `manm26ae`, the party Bastila and Carth with the player, the Star Map in the bag, K_STAR_MAP 20, K_STAR_MAP_MANAAN 1; the next
step is the walk to the bay (`man26ae_to26ac`, `man26ac_to26ad`) and the trigger to the Hawk. The overload ending and the Selkath's law have their own
branches from checkpoints of the chain (14 and 15).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_man.exe
sh kotor/tools/playthrough/manaan/all.sh [FIRST_PART]       # the chain (parts 1 to 13), about 15 minutes; each part loads the checkpoint the one before saved
sh kotor/tools/playthrough/manaan/all.sh 14                 # the other ending of the Rift (from the checkpoint "sci")
sh kotor/tools/playthrough/manaan/all.sh 15                 # the Selkath's law (from "prisoner")
CKPT=wann sh kotor/tools/playthrough/manaan/run.sh NAME 03 FRAMES [FRAME:SHOT]...   # one part from its checkpoint
```

Logs are `kotor/out/pt/mN.log`, the checkpoints `kotor/out/pt/man_ckpt/NAME` (the part's `save` line and `ckpt.sh`), the pictures
`kotor/out/pt/mN_SHOT.png` (`all.sh` takes `mN_end.png` 30 frames before the end of each part). Everything runs `FAST=1` with `LOG=dialog,combat`.
Helpers: `lg.sh NAME [FROM_FRAME]` (a log without the idle scripts and the stage dumps), `ncsall.sh` + `ncssum.py SCRIPT...` (every
script of the Manaan modules disassembled, and one script's routines and strings in one line), `whoscript.py NAME...` (which resources of the
Manaan modules name a script or a conversation), `layout.py m26ae [creatures|doors|triggers|waypoints|placeables]` (an area's instances with their
conversations and links), `python kotor/tools/py/dlgtree.py RESREF`, `python kotor/tools/py/stage_audit.py LOG`.

### The crafted state

- `--module manm26ad` (the Docking Bay, the Ebon Hawk's door) with what Dantooine leaves, read from a checkpoint of that chain with `ui globals _`:
  `K_STAR_MAP` 10, `K_KOTOR_MASTER` 15, `DAN_STARMAP_DONE`; Bastila and Carth in the party (`join`), Canderous, Juhani, Mission and Zaalbar available
  (`ui avail`). **One Star Map** was chosen (the order of the planets is free; the Dantooine map is the one every route has). The Manaan scripts
  read none of it but `K_STAR_MAP` when the map is taken.
- The player is a Jedi Guardian of level 12 (`ui jedi 3 12`, a lightsaber and a robe, Str 16, Dex 14, Con 14), Bastila a Sentinel of level 12 (`ui jedi 5 12`),
  Carth a soldier set to level 12 (`ui stat level 12`: his 52 hit points are those of the level he really has; the cheat does not give hit points).
- No plot global of Manaan is set by hand. The module scripts set `MAN_*`: the ones that matter are `MAN_PLANET_PLOT` (2 Wann has told, 3 harvester
  overloaded, 4 toxin fed), `MAN_SITHPASS_DONE`, `MAN_SITHBASE_SEALED`, `MAN_STARMAP_FOUND`, `K_STAR_MAP_MANAAN`.
- Conversation replies are a queue (`ui replies ~words ... default 1`): a word is matched in the reply text, a list with none of them takes the
  first reply and still uses up the word, so every part writes the words in the order the lists open. Walks across a whole area are cut with
  `warp`; doors are opened with `use` (a closed door stops a `goto`: the planner finds no route through it) or by a click when it is on the screen
  (`hoveron TAG [N]`, two `mouse click`); `goto X,Y` ends inside a trigger's outline.
- Test cheats used for setup only: `ui jedi`, `ui stat` (level, strength, `persuade 30` for the interrogation, `hp`), `ui giveitem`, `ui credits`, `ui bot god on`
  (the leader is never left dead; without it the party is wiped in the Sith base's second room, below), `ui bot route`, `warp`. A `ui stat hpmax` that the rules
  do not have makes a save write the current hit points relative to a base that differs: the loaded character came back at -5 (the part scripts do not set it).

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | The landing: the Hawk's door, the bay, a Sith and a Republic soldier arguing at the first corner (`man26_sitharg`, started by itself; its last script removes the Sith soldier), the Republic soldier's talk: "see Roland Wann" (`man26_starmap` 15, `man_emb` 1), the exit door to West Central (`manm26ac`) | works | `01_dock.txt` |
| 2 | West Central to East Central through the door, Roland Wann (`man26_repdip`): the mission, the Star Map, the data recording the Sith took from the Republic probe droid, the three ways into the Sith Embassy (the prisoner, the passcard, the landing bay); `man26_starmap` 20, `man_planet` 10 | works | `02_wann.txt` |
| 3 | The Republic enclave: the door to the Republic Enclave Key ("You used a key."), the Intelligence Officer (`man26_repint`), the Sith prisoner's interrogation: a counter (`MAN_THRESHOLD`) that must reach exactly 9 on a successful Persuade (Relax +1, "We know about your companion" +2, three Persuade/Lie lines +2 each); the passcode "Zeta 245698 Alpha" | works | `03_prisoner.txt` |
| 4 | Ahto East: the Sith Diplomat accepts the passcode ("I know the pass code", `k_pman_door12` unlocks the gate), the trigger to the Sith base; the Security Officer and Commander Grann find the party out whatever it says (all replies end in `k_pman_sith02`) and the lobby fight with four War Droids | works | `04_embassy.txt` |
| 5 | The Sith base (`manm27aa`): the second room's troopers and war droids, the Broken Droid with the Data Module (the loot panel), two Assault Droids' flame throwers | works (the party dies without god mode, below) | `05_base.txt` |
| 6 | Out of the base: the Selkath arrest (`man26_selarrest`, the constable, the companions kept at the ship), the cell in `manm26aa`, the Arbiter Bwa'lass (`man26_selarb`, 187 entries, 12,000 frames), the player's own trial: [Interrupt.], dismiss the Arbiter, "Not guilty", "The Sith lured me inside" / "I was there for diplomatic negotiations": not enough evidence, the Embassy is closed to the city (`MAN_SITHBASE_SEALED`). The first reply of every list ends in "You will be executed immediately" and `EndGame` | works | `06_trial.txt` |
| 7 | Wann takes the Data Module ("did not appear to have been tampered with"), the secret kolto station, the lost contact; he gives the Submersible Bay Key; `man_planet` 30, `man26_starmap` 30 | works | `07_return.txt` |
| 8 | The door behind the packing room (the key), the submersible (`man26_sub`), the Hrakert Station (`manm28aa`): the mercenary, the insane Selkath and the droids, the Environmental suit (`EnvrSuit`, an item in the bag); `man_planet` 40 | works | `08_hrakert.txt` |
| 9 | The airlock (`28aw`, `man28_airlock`: "You only have one envirosuit available ... all party members will have to stay behind"), the player alone in the suit (EffectDisguise, appearance 181) on the sea floor (`manm28ab`): the survivor Sur2 and the firaxa that takes him (`m28ab_c01`), four firaxa on the route, the north door into Kolto Control (`manm28ac`) and its insane Selkath | fixed 4f62798 (the suit's speed), works | `09_seafloor.txt` |
| 10 | Kolto Control: Kono Nolan and Sami behind the force door: the panic (the countdown barks, "60 seconds to complete depressurization"), the persuasion, the door opens (`k_pman_sur02`), what happened, the toxin (a Chemical Cannister; `man_planet` 50) or the overloaded tanks | fixed 9ae54b1 (the door), works | `10_scientists.txt` |
| 11 | The airlock `28c` to the Hrakert Rift (`manm28ad`), two firaxa, the Kolto Control Panel: "Feed toxin into vents." (`MAN_PLANET_PLOT` 4, the movie `26b`) | works | `11_rift.txt` |
| 12 | The great firaxan is dead; the walk to the Star Map pad, the trigger starts the conversation, the hologram dome grows; `man26_starmap` 40 (2,000 XP), `man_planet` 60 (1,200), `k_starforge` 40, the item Star Map: Manaan, `K_STAR_MAP` 20 | fixed 72f22f0 (the XP), works | `12_starmap.txt` |
| 13 | Back through the Rift's door to the station (the companions come back with the module's load script), the submersible up, Wann's report; `man_planet` 70 (the quest ends), a Cardio Power System | fixed b65b4ce (the companions), works | `13_surface.txt` |
| 14 | The other ending: the two-pod pressure puzzle at the panel (fill the container, transfer to the injector, dump the injector, transfer, fill, transfer: 4 million sangen); the harvester destroys itself (`man_planet` 65: 1,500 XP, `MAN_PLANET_PLOT` 3, the movie `26a`), the great firaxan "allows you to pass" (`man28_safe`) | works | `14_overload.txt` |
| 15 | The Selkath's law (below): a threat spoken to a Sith soldier makes her call a constable; "Your laws are nothing to me!": a 500 credit fine, the cell, deportation to the Ebon Hawk | works | `15_law.txt` |

Experience through the chain (the player; Bastila's is the same, Carth's starts lower by the cheat): 66,000 at the start (level 12, set); 67,695 after the lobby
fight (six kills); 69,140 after the Sith base; the trial and Wann's second talk add nothing (no plot XP on those nodes, no XP on the entries `man26_starmap` 20/30,
`man_planet` 10/30); the Hrakert Station's kills and the sea floor's firaxa bring it to 76,345 by the Rift; the Star Map pays 2,000 and 1,200 (79,545), Wann's report
900 (`man_planet` 70, 0.3 of 3,000: 80,445). The overload ending pays `man_planet` 65: 1,500 instead of 1,200 + 900. The player's portrait shows the level-up arrow
at the Star Map (78,000 is level 13).

## Staging and cameras

`stage_audit.py` over the chain: the conversations of the route are at 1.5 to 2 m in one room (Wann 1.5 m, the Republic soldier 2 m, the Intelligence Officer
1.0 m and the prisoner 1.4 m in the cell room, the Sith Diplomat 1.0 m), the trial's judges 3 to 9 m in the courtroom (a court), the Sith Security Officer in the base's lobby 3.8 to 10.9 m (he walks up and calls Commander Grann), the arrest scene's constable 4 to 8 m
(a cut scene), the scientists 4.4 and 5.3 m across the opened force door, the sea floor survivor 7.9 m. Remote or cut-scene by design: the soldiers'
argument (the Republic soldier's lines are addressed to a player who is 6 m away in the next room), the survivor's death scene (32.8 m: a camera cut), the
mercenary at the station (4.2 m, rooms 0/27: he is behind the door he says he shut).

## Bugs found and fixed

1. **The GUI's clocks ran 8x slow under `--speed`** (e6d041e). `ingame::update` took one tick's dt while the scene and camera got the skipped ticks too:
   the HUD's feedback text ("You used a key.") stayed on the screen 1,000 frames in every fast screenshot and the message log aged slowly. The fast
   run now matches the drawn one.
2. **A door told to open itself stayed locked** (9ae54b1). Kolto Control's force field has no key; once Kono is persuaded `k_pman_sur02` runs
   `AssignCommand(door, ActionOpenDoor(door))`. OPENDOOR (0x0057d490) tests the lock only for a creature and sends OPEN_OBJECT at once for anything else, which is how the
   door's OnOpen (`k_pman_press06`: SetLocked(0), the scientists' conversation, started by Kono) runs. Ours asked the door for a key, ran OnFailToOpen and
   started the door's conversation again: the door stayed shut and Kono spoke through it with the door as the speaker.
3. **The Envirosuit did not slow the walk** (4f62798). The airlocks put only `EffectDisguise(181)` on the player; the leader moves with the keys, and the original's
   controller takes its top speed and push from the shown appearance's `DriveMaxSpeed` and `DriveAccl` (`CSWCPlayerControl::GetMaxSpeed` 0x00679510; both columns are
   read by the exe). Every humanoid row says 5.4 and 50, row 181 says 1.5 and 5. Ours used the creature's run rate. The suited leader now walks at 1.4 m/s.
   (The server-side rate, the one the actions use, is the creature's `creaturespeed` row and stays 5.4 in the original too; `goto` and the bot are not slowed.)
4. **The companions did not come back from the station** (b65b4ce). Manaan's airlock leaves the party in the station with `RemovePartyMember` and `DestroyObject`; the
   module's saved state keeps both companions as ordinary creatures and the pending destroy events. On the way back (the sea floor's doors, the Rift's door) the load script makes them
   again with `SpawnAvailableNPC`; the destroy events fire first and flag the old Bastila (316) and Carth (318) destroyed, which still own their ids until the frame's sweep;
   the AVAILNPC file's object id looked free (`world::object` hides destroyed objects), so the new companions took the same ids, replaced the table entries and the sweep
   removed them. The party came back as the player alone. The freshness of a saved id is now asked of the table (`world::id_taken`), and `DestroyObject` clears the party slot
   at once (ClearNPCObjectId 0x0052ff20), as the original does.
5. **A quest step paid no experience** (72f22f0). `AddJournalQuestEntry` (0x005483f0) reads the entry's XP back from the journal after setting the state and gives it to the party:
   global.jrl's category names a plot.2da row (`PlotIndex`) and the entry a share of it (`XP_Percentage`). Ours only kept the state. The Manaan Star Map (2,000 XP, the row
   `tat_starmap`) and the end of Wann's quest came to nothing. One function (`rt_misc::set_quest_state`) now serves the routine and the conversations' journal updates
   ([re/journal.md](re/journal.md), "Quest steps pay experience"). The Endar Spire replay is unchanged (its entries are worth 0), but the other planets'
   XP in their logs moves up by the quest steps they walked.

## Notes and open items

- **The Selkath's rule about weapons** is not a rule about weapons. Nothing in the install's scripts, the area flags or the engine's routines punishes drawing one: the party walks Ahto
  City armed, and a blow struck at a Sith soldier or a Selkath guard (8 hit points each) kills them and nobody comes. What the Selkath punish is violence spoken or done in
  conversation, and the conversations do it (step 15): a Sith soldier's goading, the constable's questions, the fine, the cell, the deportation; and the arrest after the Sith Embassy
  (step 6). The visitor's guide text says only that "the Selkath Security Forces ... prevent the needless interruption of commerce by violence". Left as the data has it.
- **The Broken Droid's `OnUsed` never runs** (`k_pman_droidq`, `man_planet` 20, 300 XP). An unlocked placeable with an inventory opens its container (OnOpen) and sends no OnUsed
  (USEOBJECT 0x0057e8c0, `OpenInventory` 0x00587420 posts the OPEN script event; `GetHasInventory` reads the flag at 0x324), and our engine does the same. The entry the
  designers meant for taking the module is therefore never set in the original either; Wann's talk does not need it.
- **The sea floor and the Rift are dark, and that is the data.** `m28ab`/`m28ad`: DynAmbientColor (23, 56, 66), fog 9, 26, 30 to 70-80 m, no sun, three lights; the engine's ambient
  is the same 0.09, 0.22, 0.26. The pictures read well beside the lamps and the sea grass (`m12_sheet`, the Rift) and are murky in the airlock corridor. The first frames
  after an airlock are a fade-in.
- **The suit's walk animation** uses the walk cycle at 1.4 m/s (the engine chooses the gait by the midpoint of the walk and run rates, 4.3 m/s); the original picks the run
  cycle above 0.37 of RUNDIST (0.85 m/s for row 181).
- **Insane Selkath's bite** (`man28_inssel`) lowers the maximum hit points in steps for a while (144 to 72); the engine keeps the deficit (the current points drop with the
  maximum). A dying-but-god-moded leader sits at 1 hit point.
- **The Sith base without god mode.** Two Assault Droids' flame throwers (`DROID_ITEM_FLAME_THROWER_2`, 15 a hit, with a stun) and the Sith troopers wipe a level 12 party (Carth with 52 hit
  points) led by the test bot in 40 seconds; with a player who heals and uses powers it would be fought otherwise. The fights were checked in god mode for their numbers and animations.
- **Sunry's murder trial** (`man_murder`, Elora, the hotel witnesses, `man26_trial`) is Jolee's quest: Elora approaches only when Jolee is available (`G_JoleeJoined`); a joined
  Jolee does not fit the crafted three-person party. Not played; neither is the missing Selkath youths (Shaelas, Shasa in the Sith base, `man_missing`), the swoop races (Queedle, Hukta
  Jax), the mercenaries' Nilko quest, Calo Nord and Bandon at the station (`man_k_h_calo`), the pazaak players, the shops.
- **Journal text for the Wann return**: the entries `man_planet` 30 and 70 are those of the toxin ending; the overload ending sets 65.
- The `hoveron` input needs the object on the screen: a door behind the camera cannot be clicked; the part scripts `use` it.
