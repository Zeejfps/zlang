# Playthrough log: Kashyyyk

The main storyline of Kashyyyk played headless, step by step, checked against the original with logs and screenshots, from a
crafted arrival after Dantooine (a Jedi, Bastila and Zaalbar in the party). The method is [playthrough.md](playthrough.md)'s
and [playthrough-dantooine.md](playthrough-dantooine.md)'s; the scripts are in `kotor/tools/playthrough/kashyyyk/`.

**Played to the end of the planet** (parts 1 to 19, 0 script faults): the Czerka landing pad to the Star Map (parts 1 to 16), Chorrawl and the throne room, the party on
Freyyr's side, the duel, Freyyr's thanks and Zaalbar's return to the party (parts 17 and 18), and the way out to the Ebon Hawk (part 19). Not played: Chuundar's side (the
journal's 120/130: Freyyr is killed, Zaalbar sides with his brother), the Bandon/Calo ambush of the Upper Shadowlands, the side quests at the end. The checkpoints are
in `kotor/out/pt/kas_ckpt` (ignored by the repository: `all.sh` rebuilds them, about 15 minutes); the Hawk and the trip to the next planet are played from the Tatooine side
(`playthrough-tatooine.md`, "Travel").

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_kas.exe
sh kotor/tools/playthrough/kashyyyk/all.sh [FIRST_PART]       # the chain, about 25 minutes; each part loads the checkpoint the one before saved
CKPT=mapped sh kotor/tools/playthrough/kashyyyk/run.sh NAME 17 FRAMES [FRAME:SHOT]...   # one part from its checkpoint (the script's header says which)
```

Logs are `kotor/out/pt/kNN.log`, checkpoints `kotor/out/pt/kas_ckpt/NAME` (the part's `save` line and `ckpt.sh`), pictures
`kotor/out/pt/NAME_SHOT.png`. Everything runs `FAST=1` with `LOG=dialog,combat`. Helpers: `trig.sh MODULE TAG` (a trigger's outline in world
coordinates and its enter script: the triggers are thin strips and a walk must end inside one, `goto X,Y`), `whoscript.sh MODULE SCRIPT`
(which resources name a script), `python kotor/tools/py/dlgtree.py RESREF` (a conversation as a tree), `python kotor/tools/py/stage_audit.py LOG`.

### The crafted state

- `--module kas_m22aa` with the state Dantooine leaves: `join p_zaalbar 8`, `join p_bastilla 0` (after the player is placed, frame 4: a
  join at frame 1 leaves them at the origin), `ui avail 0 1 2 5 6 8`, a Jedi Guardian of level 10 (`ui jedi 3 10`), a lightsaber and a robe,
  300 credits for the docking fee. Part 2 makes Bastila a Sentinel and Zaalbar level 10 (`ui leader`, `ui jedi`, `ui stat`). New party
  members (Canderous, Carth, Jolee) are given the player's XP and level by hand.
- No plot global is set by hand but one: nothing. The module scripts set `kas_*`. The globals that matter: `kas_TalkChuundar`, `kas_ZaalbarParty`,
  `kas_HelpedFreyyr`, `kas_ComputerDown`, `K_STAR_MAP_KASHYYYK`; journal categories `kas23_mainwookplot` ("Chieftain in Need"),
  `kas22_starmap`, `kas24_removepoachers`.
- Conversation replies are a queue (`ui replies 1 3 ... default 1`): a hub keeps offering questions, so the part scripts pick the exit
  by position. Long walks are cut with `warp TAG party` / `warpxy X,Y party`; triggers, conversations, module changes are the game's.
- Test cheats used for setup only: `ui jedi`, `ui stat`, `ui giveitem`, `ui credits`, `ui faction`, `ui bot god on` (the leader never
  dies), `ui bot on` for a fight, `--seed 3` for Freyyr (below).

## The steps

State: **works** (checked), **fixed** (a commit of this branch), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | Arrival on the Czerka pad (`kas_m22aa`): Janos Mercer's conversation starts by itself (docking fee: pay, Force Persuade, refuse; the Wookiee line only when Zaalbar is within 10 m), he walks to the information center; Zaalbar's talk at the trigger | fixed (party table blueprints, `ui credits`, `warp party`) | `01_landing.txt` |
| 2 | The Czerka gate guard's talk, the door `KashyyykDoor3` to the Great Walkway (`kas_m22ab`) | works | `02_center.txt` |
| 3 | The Walkway opens in a fight (Wookiee warriors and turrets against Forest Kinrath: 150 XP each); Zaalbar's second talk, Patrol Captain Dehno and two guards (the threatening replies end in their fight) | works | `02`, `03_walkway.txt` |
| 4 | The Dark Jedi ambush (trigger `kas22_sithattk`, three Dark Jedi with Force Stun and sabers, 350 XP each) | works | `04_gate.txt` |
| 5 | The Wookiee guards at the village door: with Zaalbar they take him before Chuundar; the party screen opens (a script's screen starts with the forced members only) | works | `05_gate.txt` |
| 6 | Chuundar's hall (`kas_m23ad`, `kas23_chuunda_01`, 155 entries): the order to kill the mad Wookiee, Zaalbar kept as hostage, journal `kas23_mainwookplot` 10 and `kas22_starmap` 20 | works | `05_gate.txt` |
| 7 | Rwookrrorro (`kas_m23aa`), the village door back to the Walkway, the long walk to the elevator basket, Gorwooken's talk, the descent (`kas_m24aa`) | works | `06_village.txt`, `07_basket.txt` |
| 8 | The Upper Shadowlands: Jolee Bindo (trigger `kas24_joleetrig`: the cut scene fades to black while he kills four katarn, a node's fade), his camp talk and the poachers' task | works | `08_jolee.txt` |
| 9 | The Czerka poachers (`kas24_poffice_01`): the threat that makes them hostile, the fight, journal `kas24_removepoachers` 40 | works | `09_poachers.txt` |
| 10 | Jolee joins (his forced slot on the party screen), `kas22_starmap` 50 | works | `10_jolee_joins.txt` |
| 11 | The repulsor field (`kas24_force_01`): "Just shut it down", the Lower Shadowlands (`kas_m25aa`), `kas23_mainwookplot` 50 | works | `11_field.txt` |
| 12 | Freyyr (`kas25_freyyr_01`): the first talk ends in his fight, he surrenders below a quarter of his hit points and talks again (journal 70, then 75: Bacca's blade) | fixed (`SurrenderToEnemies` as the original: see Bugs found, 4); works with any `--seed` | `12_freyyr.txt` |
| 13 | The viper kinrath, the ritual vine (`kas25_ritualvine`), the Great Beast (`kas25_wraid`, 550 XP), the blade in its hide: `kas23_mainwookplot` 85, 87, 90 | fixed (OnAcquireItem for `CreateItemOnObject`); the corpse is given by hand | `13_ritual.txt` |
| 14 | Bacca's blade back to Freyyr, `kas23_mainwookplot` 95, he leaves (fade, `kas_HelpedFreyyr`) | works | `14_blade.txt` |
| 15 | The ancient computer (`kas24_computer`, `kas25_comp_01`): the evaluation (a failed one: "purge the subject"), two Mark IV droids (750 XP each) | works | `15_starmap.txt` |
| 16 | After the droids the computer gives the Star Map: `kas22_starmap` 70, `k_starforge` 30, `K_STAR_MAP` 10, `K_STAR_MAP_KASHYYYK` 1, the hologram cut scene, Jolee's remark | works (the droids' corpses must be gone first: the computer answers "no longer responds" otherwise, by timing) | `16_mapgiven.txt` |
| 17 | Back up (the Exit trigger, the basket `kas24_baskettalk`, the Walkway). The village door's guard keeps the hall shut while Freyyr rallies the Wookiees, so the way is Chorrawl (`kas22_chorraw_02`, his trigger `kas22_chorratrig` at 210 75: "Lead on. We should hurry."), who takes the party to the throne room behind the guards (`k_pkas_backking`, the module change to `kas_m23ad`). Chuundar's conversation (`kas23_chuunda_01`, start branch `k_pkas_freyyhelp`): Freyyr, Zaalbar and the party face him; Zaalbar asks what to do; "Side with Freyyr" and "Without doubt! Chuundar is a slaver!" (light side points `k_act_lightmed`), journal `kas23_mainwookplot` 110, `k_pkas_chuundatk` starts the duel | works | `17_return.txt` |
| 18 | The duel: Freyyr, Zaalbar and the party (Jolee, Canderous) against Chuundar, his Wookiee guards and the Czerka mercenaries (the test player fights on its own; Chuundar falls to the party in about 1,200 frames, 1,790 XP in all). Freyyr talks (`kas23_freyyr_01`, `k_pkas_fightdone`, journal 150, END): Zaalbar keeps his life-debt, asks for Bacca's Sword and gets it (`k_pkas_givesword`: `G_w_Vbroswrd05` into the bag, Zaalbar selectable again); the party screen opens at the end of the talk (Zaalbar and Jolee by two clicks, OK). XP 53,780 | works | `18_duel.txt` |
| 19 | Leaving: the hall's `KashyyykDoor2` into Rwookrrorro, its `KashyyykDoor3` to the Walkway, the Walkway's `KashyyykDoor3` to the pad; the pad's cut scenes on the way (the Wookiee rebels `kas22_rebelcut_1` and `_2`, Davin K's conversation `k_hdavin_dialog`, 34 nodes) and the trigger `EbonHawk` to `ebo_m12aa` (the party stays on the pad: only the player is in the Hawk) | works | `19_leave.txt` |

Experience through the chain (the player; the party gets the same): 45,000 at the start (level 10), 45,450 after the first kinrath, 47,650 after
the Walkway and the Dark Jedi, 49,490 after the poachers, 50,490 with the Great Beast, 51,990 after the droids. The journal entries award nothing
(see the open items); the Star Map awards nothing.

## Bugs found and fixed

1. **A companion available but never spawned was lost by a save** (a2e8c81). `AVAILNPC<n>.utc` exists only for spawned companions and the
   party table kept the available and selectable flags and nothing else, so after a load the party screen listed Carth, Canderous or
   Juhani (after her redemption) and silently failed to make the creature when picked. The table now carries the blueprint
   (`PT_NPC_TEMPLATE`, an extra field of ours).
2. **CreateItemOnObject did not tell the module** (0f26527). The original reaches the creature through `AcquireItem`, which posts the module's
   OnAcquireItem for every transfer (party-items-saves.md 5.4); only the HUD notice was sent. Kashyyyk's journal for Bacca's blade is
   moved by `k_pkas25aa_acqui`: it stayed at "search the remains".
3. Test tools: `ui credits` wrote the creature's gold, not the party purse that `GetGold` reads, so the docking fee could not be paid (488d5ee);
   `warp TAG party` and `warpxy X,Y party` stand the followers beside the leader (18671af; a plain warp left them 200 m away).
4. **`SurrenderToEnemies` only stopped the fight** (this branch). The original (`CSWSCreature::SurrenderToEnemies`, 0x00518990, re/combat.md 8.5)
   cancels combat and clears the effects of the caller and of every creature within 250 m that the caller counts an
   enemy (standing below 11), which also makes them commandable again, and then moves the caller into a faction everybody is
   neutral to (repute.2da's Surrender_1, all 50). Ours cleared actions within 10 m and left Freyyr in Hostile_1: the party went
   on beating the one-hit-point immortal after the talk (part 13 made him neutral by hand), and a player knocked down by his
   weapon stayed non-commandable (`ActionStartConversation(PC)` refuses such a target, which lost the talk in an earlier run). Freyyr's "Now die!" reply
   (`k_pkas_freyyrfin`) sends him back to Hostile_1 itself. Part 13 no longer touches him: his faction is 9 and nobody hits him.

5. **The chain drifted** (found by rebuilding every checkpoint): the Great Beast (`kas25_wraid`) no longer charges (see the notes: part 13 walks the party up to it), part 13 and the
   chain's frame counts moved with it (7,500 frames for the Beast and the conversation that follows its death), and the `savewhen` of part 14 of Tatooine now waits for the leader
   to leave combat.

## Notes and open items

- **The Great Beast does not charge.** `k_pkas_wraidattk` (the last reply of the ritual talk) queues a run to `kas25_wp_wraid3` for the Beast and makes it hostile; FreezeHostiles
  (`CSWSDialog::FreezeHostiles`, run by every `UpdateDialog` before the talk can end: re/dialogue.md 4.9, read again this time with the decompilation) clears the actions of every non-party
  creature whose standing toward the player is 10 or less, and the Beast is that from the moment the script runs. It stands 29 m from the vine, outside its 20 m perception
  (ranges.2da PercepRngDefault) and fights only when the party is within about 12 m. The order of the calls is the original's, as far as it was read; how the original's Beast gets
  out of it is not known. Part 13 puts the party 9 m from it.
- **The test bot's route stops** are looked up in the area it is in when it reaches them: a stop named for a door of another area is skipped ("bot: no object"), and a tag has
  three y's (`KashyyykDoor2`). Part 19 uses warps and the bot only on the pad.
- **Journal XP.** `AddJournalQuestEntry` awards no quest XP here and the string `XP_Percentage` has no code reference in swkotor.exe, so the
  original most likely does not either; XP comes from `GivePlotXP`, the conversation nodes and kills.
- **Companions joining** come from the blueprint at level 1 to 4 with XP 0; the crafted state sets level and XP by hand. The original's rule is not known.
- **Dark areas.** The Lower Shadowlands (and the Upper at night) are very dark away from the lanterns; the area data has no sun and a dim ambient.
- **The test player's god mode** lowers the maximum hit points by each hit it absorbs (130 to 60 over a long fight).
- **Dialogue shots**: a speaker 15 m away (the Dark Jedi at the ambush) and over-the-shoulder shots with two companions in the foreground
  (Freyyr's talk) are as the data gives them; there is no obstruction test.
- **Not played:** the Mandalorian hunters' fights, Eli and Dasol, Jaarak and Woorwill, Worrroz, the
  Mandalorian hunters (`kas25_mandcut_01` plays; their fights were skipped), Mandalore's swoop bikes, the tach hunt, the sonic emitters
  solution of the poacher camp, Zaalbar's conversations as a party member (he is a hostage in this branch), the choice of sides and the duel.
