# Playthrough log: Kashyyyk

The main storyline of Kashyyyk played headless, step by step, checked against the original with logs and screenshots, from a
crafted arrival after Dantooine (a Jedi, Bastila and Zaalbar in the party). The method is [playthrough.md](playthrough.md)'s
and [playthrough-dantooine.md](playthrough-dantooine.md)'s; the scripts are in `kotor/tools/playthrough/kashyyyk/`.

**Stopped (paused for the rendering work).** Played: the Czerka landing pad to the Star Map (parts 1 to 16, 0 script faults) and the
climb back to the village (part 17). Not played: the end of Chuundar's plot (Freyyr's or Chuundar's side, the duel) and the leave-taking.
To resume: `CKPT=mapped` (the Star Map given, the party at the computer in the Lower Shadowlands, journal `kas22_starmap` 70,
`kas23_mainwookplot` 95) and `sh kotor/tools/playthrough/kashyyyk/run.sh NAME 17 3000` replay part 17, which ends at the guard of
Chuundar's hall (`kas23_wookgua_01`, village door `kas23ad_door` 95 67). The next step is to find out how the hall opens now that
Freyyr has gone to rally the Wookiees (`kas_HelpedFreyyr`): the guard keeps saying "return when the task is complete"
(`k_pkas_chuundone` false) and the village's enter script destroys him only if `kas_ChuundarDead`. The scripts that start the
hall (`k_pkas_backking`, `k_pkas_meetking2`, StartNewModule `kas_m23ad` at `kas23_MeetKing`) are named by a conversation of the Walkway:
`kas22_chorraw_02` (Chorrawl, near the trigger `kas22_chorratrig` 210 75), so walk there first (`warp kas22_chorraw_01 party`), read
`python kotor/tools/py/dlgtree.py kas22_chorraw_02`, then the hall's Chuundar conversation (`kas23_chuunda_01`, start branch E122,
`k_pkas_freyyhelp`): Zaalbar returns, the side is chosen (journal 110/150 Freyyr's, 120/130 Chuundar's), then `k_pkas_chuundatk` or
`k_pkas_freyyratk` starts the duel, then the credits of the story: `kas_ChuundReward`, `kas_FreyyrDead`, `kas_ChuundarDead`.

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_kas.exe
sh kotor/tools/playthrough/kashyyyk/all.sh [FIRST_PART]       # the chain, about 25 minutes; each part loads the checkpoint the one before saved
CKPT=mapped sh kotor/tools/playthrough/kashyyyk/run.sh NAME 17 FRAMES [FRAME:SHOT]...   # one part from its checkpoint
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
| 17 | The Exit trigger to the Upper Shadowlands, the basket (a placeable, `kas24_baskettalk`, the enter script destroys the trigger), the Walkway, the village, the hall's door: the guard refuses | works up to the guard; open | `17_return.txt` |

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

## Notes and open items

- **Journal XP.** `AddJournalQuestEntry` awards no quest XP here and the string `XP_Percentage` has no code reference in swkotor.exe, so the
  original most likely does not either; XP comes from `GivePlotXP`, the conversation nodes and kills.
- **Companions joining** come from the blueprint at level 1 to 4 with XP 0; the crafted state sets level and XP by hand. The original's rule is not known.
- **Dark areas.** The Lower Shadowlands (and the Upper at night) are very dark away from the lanterns; the area data has no sun and a dim ambient.
- **The test player's god mode** lowers the maximum hit points by each hit it absorbs (130 to 60 over a long fight).
- **Dialogue shots**: a speaker 15 m away (the Dark Jedi at the ambush) and over-the-shoulder shots with two companions in the foreground
  (Freyyr's talk) are as the data gives them; there is no obstruction test.
- **Not played:** the Wookiee rebels and Czerka captain cut scenes on the pad, Eli and Dasol, Jaarak and Woorwill, Worrroz, the
  Mandalorian hunters (`kas25_mandcut_01` plays; their fights were skipped), Mandalore's swoop bikes, the tach hunt, the sonic emitters
  solution of the poacher camp, Zaalbar's conversations as a party member (he is a hostage in this branch), the choice of sides and the duel.
