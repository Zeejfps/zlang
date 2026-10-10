# Traps and mines: the original's behaviour and where we stand

What the original does with mines (trap triggers), one line per behaviour, with the evidence and our status.
The status is **matches** (checked by a run that goes through the pointer, the keys and the HUD, named in the
last column), **ours** (a choice of ours where the original differs or was not read, with the reason), or
**open** (with the reason). Evidence: [actions.md](../re/actions.md) 3.14, [rules.md](../re/rules.md) 5.2,
[movement.md](../re/movement.md) 5.1, 5.2, 7.1, 7.4, [gui.md](../re/gui.md) "Action menus" and the decompiled
functions named in the lines (`python kotor/tools/py/rex.py fn ADDR`). The code is `lib/engine/traps.ctx`, the
HUD's side `lib/hud/target.ctx`, `block.ctx`, `lib/ingame/mine_watch.ctx` and `selfslots.ctx` (slot 3).

## How these were tested

`EXE=kotor/out/kotor_trp.exe LOG=actions,events sh kotor/tools/items/run.sh NAME module:tar_m04aa
kotor/tools/traps/scripts/SCRIPT FRAMES [FRAME:SHOT]` (the items owner's runner; logs and pictures under
`kotor/out/items/`). Each script's header says what it shows and its length. Setup uses test commands only
(`warpxy`, `ui stat awareness|demolitions N`, `ui stat hp`, `ui giveitem`); what is tested goes through the
platform's pointer and key events: `ui clickobj ID` / `ui moveobj ID` put the pointer on the centre of an
object's box on the screen and press there, so the world's own pick decides what is hit (as `ui clickctl` does
for controls); `ui key`, `ui clickctl BTN_TARGET1`, `ui clickctl BTN_ACTION3`. `ui mines` prints every trap
(found, flagged, who laid it, distance, box on the screen). Headless runs leave the auto-pause off unless the
script says `ui autopause on`.

| Script | What it runs |
|---|---|
| `detect_disarm.txt` | found at 2.7 m, made the target, MINE SIGHTED pause, Space, one click on the mine = Disable, 4.5 s kneel, OnDisarm, gone |
| `keys.txt` | E and Q step through targets that include found mines; R disables the target |
| `recover_lay.txt` | the middle slot Recover gives the kit back; the HUD's fourth self slot lays it at the leader's feet |
| `step_on.txt` | the leader walks over a hostile mine: "You triggered a Mine!", 18 damage, explosion, gone |
| `enemy_mine.txt` | a mine laid by the party is set off by a rakghoul chasing the leader |

Save and load: disarm 148 in `detect_disarm.txt`'s way, `save NAME`, then `--load` the save and `ui mines`:
148 stays gone, the others keep "found" (checked by hand runs; not a script yet).

## 1. What a trap is

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A trap is a trigger of Type 2 (`+0x2bc`); doors and placeables can be trapped too, but no shipped door or placeable blueprint sets TrapFlag (all 37 trapped blueprint copies, 23 resrefs, are UTTs), so only triggers carry traps here | LoadTrigger 0x0058da80; a scan of every UTD/UTP/UTT | matches (doors and placeables: not needed) | `ui mines` |
| A trigger reads TrapType (BYTE, 0xff none), TrapOneShot (default 1), TrapDetectable and TrapDisarmable (default 0 when the field is missing), CreatorId, SetByPlayerParty, KeyName, AutoRemoveKey; its detect and disarm DCs are traps.2da DetectDCMod and DisarmDCMod of the type: the blueprint's TrapDetectDC, DisarmDC and TrapFlag are not read for triggers; the save writes KeyName and AutoRemoveKey back | LoadTrigger 0x0058da80, SaveTrigger 0x0058e660 | matches (only `newtrap`, in templates.bif, lacks TrapDetectable) | `ui mines` |
| An empty or `default` OnTrapTriggered is the type's TrapScript (k_trp_generic, k_kor_rocks01/02) | LoadTrigger | matches | `step_on.txt` |
| A trap's KeyName: a creature that would set it off but carries an item of that tag (in its bag, else worn) disarms it instead: with AutoRemoveKey the key is destroyed, the creature becomes the trap's last disarmer, OnDisarm runs as the trap, the trap is destroyed (event 11) | OnTrapEntered 0x0058d570 | matches by reading (no shipped trap has a KeyName); ours: an empty KeyName matches nothing (the original may match an item with an empty tag, medium) | |

## 2. Finding mines (DoTrapDetection 0x004fa390)

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Every creature's detect mode is on from creation and nothing clears it, so the search always runs at the fast pace: every 100 ms, traps within 20 m of their **outline**, Awareness + d10 + 10 against the detect DC (the 3 s / 3 m / d10 pace is never reached) | DoTrapDetection, activity bit 2 (0x0050ee30), LoadCreature | matches | `detect_disarm.txt` |
| Candidates: TrapDetectable, reputation toward the searcher below 90, another faction, not yet found by it; a flagged trap is found without a roll | DoTrapDetection | matches | `detect_disarm.txt` |
| A player-controlled finder finds it for the whole party, anyone else for itself; a find by roll (not a flagged one) gives two feedback lines: 42132 "X successfully detects Y: awareness N vs. DC M" and 42123 "X Awareness Breakdown: N = roll R + awareness skill rank K"; no sound, no script event | DoTrapDetection, combat message 0x13 (0x004ec840: the clients of the finder's faction in its area) | matches | screenshot `sighted` |
| Who searches | DoTrapDetection runs for every creature | ours: only party members search (what an NPC finds shows nowhere and no shipped script asks) | |
| GetLastTrapDetected always answers OBJECT_INVALID (creature `+0x370` is only set by the constructor) | 0x0053b480 | matches (no shipped script calls it) | |

## 3. Seeing and picking a mine

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Every trap trigger has its type's mine model (traps.2da `model`, v_mnfrag when blank) at its position; it plays `default` (the marks at alpha 0) until the party knows of it, then `detect` (the red dome fades in) | client add message 0x0064f4b0, CSWSTrigger::AIUpdate 0x0058d760 (animations 10143 / 10144), 0x006e6100 | matches | screenshot `sighted` |
| The party knows of it when it is flagged, found by the party, of the leader's faction, or friendly to it (90 or more: its own mines) | AIUpdate, GetIsSelectableTarget 0x004f2c30 | matches | `recover_lay.txt` (own mine shown at once) |
| Only a known mine can be picked or targeted; it is a target kind 2, named by its LocalizedName (laid mines: traps.2da TrapName) | ProcessInput 0x006227e0, GetTargetKind 0x0060fcc0 | matches | `detect_disarm.txt`, `keys.txt` |
| A hostile mine coming into the selectable set (within 30 m, past the leader's visibility ray) while nothing is paused (and the latch is clear) becomes the target; out of combat mode, with "Mine Sighted" on, the game pauses with 49118 "MINE SIGHTED!"; the latch clears after 10 s without a mine in sight | UpdateSelectableObjects 0x005fa5a0 (0x005fa83a), CSWGuiPause reason 11 | matches (through `autopause::request`; on the screen or not) | `detect_disarm.txt` |
| E and Q step through found mines with the other targets (not in combat mode, which takes hostile creatures only) | CycleTarget 0x005fb050 | matches | `keys.txt` |
| The pointer over the targeted mine is `dismine` (Disable) or `recmine` (Recover); over a mine that is not the target, `select` | GetCursorForAction 0x0061faa0 | matches | screenshot `disarming` (by hand) |
| The target block's health bar: the original draws its default 1/1 for a trigger (low-med) | Render | ours: hidden (a trigger has no hit points here) | |

## 4. The target block and the trap actions

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Left slot Disable (370, `i_disablemine`) on a mine hostile to the leader (another faction, reputation below 90); middle slot Recover (1531, `i_recovermine`) on any mine; nothing without Demolitions; the default action (second click, R) is Disable, or Recover on the party's own mine | 0x00691f00, BuildDefaultActions 0x00620620 kind 2, 0x006477e0 | matches | `detect_disarm.txt`, `recover_lay.txt`, `keys.txt` |
| The slots and ActionUseSkill(Demolitions) go through UseSkill: subskill 100 FLAGTRAP, 101 RECOVERTRAP, 102 EXAMINETRAP, else DISABLETRAP; disable and recover refuse a trap that is not disarmable; found or not is not checked. The target block's callbacks (0x00691900 Disable, subskill 0; 0x00691950 Recover, 101) send player input (6,7) | UseSkill 0x004fbe40 (asm: each AddTrapActions branch returns), AddTrapActions 0x004f9da0, 0x00677b10 | matches | (script routine; `ActionUseSkill`) |
| The worker walks up (to the nearest point of the mine's outline: use range + 0.25 for disable and recover, the use range itself for flag and examine), faces the mine and works 4.5 s: disable and recover kneel (10132 / 10141: `disablemine`), flag and examine pick (10059); the player's side hears `gui_minedisarm` 750 ms in (disable, recover) | DISABLETRAP 0x00519570, RECOVERTRAP 0x00518c40, FLAGTRAP 0x0050e400, EXAMINETRAP 0x0050e900, GetUseRange ([actions.md](../re/actions.md) 1.4), PLAYANIMATION | matches (`doors::use_point` takes the outline's nearest point at the radius + 0.5; `traps::work_on_trap` adds 0.25 for disable and recover) | `detect_disarm.txt` (screenshot) |
| No action timer is shown: the server's StartActionProgress (types 1 to 5, 4.5 s / 2 s) sends message 0x30/1, and the client's handler reads its fields and drops them | 0x004ef480, client 0x00665590 → 0x00654a30 | matches (none drawn; `detect_disarm.txt` still disables mine 148 through the click) | `detect_disarm.txt` |
| The roll: Demolitions + 20 out of combat, d20 in it, against the disarm DC (disable; a DC above 35 cannot be beaten), + 10 (recover, no cap), - 5 (flag), - 7 (examine), at least 1; its creator needs no roll, nor, to disable or recover, a party member (or the PC) on a trap whose creator is of the party | the four handlers | matches (flag and examine: no shipped caller) | `detect_disarm.txt` (29 vs 20), `recover_lay.txt` (33 vs 30) |
| Disable: OnDisarm (event 24 from the worker), then the trap is destroyed and its mine plays `deactivate`; a miss by more than 10 sets it off under the worker (OBJECT_ENTER, so OnTrapEntered's tests apply); a miss plays the worker's sound set entry 0x18 | DISABLETRAP, delete reason 2 (0x004ce8a0) | matches | `detect_disarm.txt` |
| Recover: the trap's kit (traps.2da ResRef) goes to the party's bag, the trap is destroyed (no OnDisarm); a miss by more than 5 sets it off | RECOVERTRAP | matches | `recover_lay.txt` |
| Flag: the trap is flagged (found without a roll from then on, always shown); examine changes nothing and tells the client a difficulty band (0..4) | FLAGTRAP, EXAMINETRAP (0x0056f160) | matches for flag; open for examine's band (what the client shows was not traced) | |
| The combat log line "X success Disable Mine: 28 (roll 20 + Demolitions 8) vs. DC 20": 1408 "<CUSTOM0> <CUSTOM1> <CUSTOM2>: <CUSTOM3> (roll <CUSTOM4> <CUSTOM5> <CUSTOM6> <CUSTOM7>) vs. DC <CUSTOM8>" with the actor, "success" (1392, results 1 and 4) or "failure" (1393, results 0, 2, 3), the action (1529 / 1531 / 1530 / 1532; none for flag), the total, the roll, the rank's sign, "Demolitions" (324), the rank and the DC; no target and no "Take 20" | combat message 9 (0x004ec700), client 0x0065b4a0 (asm: the total shown is the client's roll + rank; a negative rank shows "-" and its size) | matches (`doors::say_skill_roll`: "Player success Recover Mine: 33 (roll 20 + Demolitions 13) vs. DC 30", "Player success Set Mine: 35 (roll 20 + Demolitions 15) vs. DC 15") | `recover_lay.txt` with `ui log 6` |
| XP for a disarmed mine | none on the engine side | matches (scripts give it where they want) | |

## 5. Going off (CSWSTrigger::OnTrapEntered 0x0058d570)

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A creature is on a trap within 1.0 m of its position, in 3D (not inside its outline); but a step that crosses the trap's outline also sends it OBJECT_ENTER (then OBJECT_EXIT) when the creature is inside some volume before or after the step (needs a runtime check) | InTrigger 0x0058ce40, g_fTrapTriggerRadius, GetVolumesCrossed 0x004bf2c0 (SegmentCrossesGeometry 0x0058cd80), UpdateVolumesAfterMove 0x0051b7b0 ([movement.md](../re/movement.md) 5.1) | matches for the 1.0 m; open for the crossing: ours tests only the 1.0 m (`movement::cross_volumes`) | `step_on.txt` |
| It goes off for a creature not immune to traps, not of the trap's faction, whose reputation toward the creator (the trap itself when nobody laid it) is 10 or less (or whose creator has no faction); found or not does not matter, and a party mine spares the party | OnTrapEntered, 0x0058d4a0 | matches | `step_on.txt`, `enemy_mine.txt` |
| It goes off: feedback 0x52 "You triggered a Mine!" (1461) to the victim, OnTrapTriggered runs at once as the trap (GetEnteringObject is the victim), then OnEnter; a one-shot trap is destroyed (event 11 at once) with its explosion: the mine's `activate` and traps.2da ExplosionSound | OnTrapEntered, EventHandler 0x0058f140, client delete 0x0064f960 | matches | `step_on.txt` (screenshot `boom`) |
| The damage, saves and visuals are the script's (k_trp_generic: a 3.3 m sphere around the mine, everyone not neutral to it; frag 18/30/54 Reflex DC 15/20/25, plasma, gas poison, stun), through the rules' effects | k_trp_generic.ncs | script | `step_on.txt` (hp 200 -> 182) |
| Triggers do not handle script event 26 (MINE_TRIGGERED): only trapped doors and placeables do | EventHandler | matches (no trapped door or placeable ships) | |

## 6. Laying mines (UseItem 0x004fc210, SETTRAP 0x00519e30)

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| The HUD's fourth self slot ("Activate Mine", 48295) lists the bag's trap kits (itemtype 28 passing CanUseItem; a kit with a Trap property also needs it usable and a leader who can use Demolitions; non-plot kits are dropped where the area's RestrictMode is set), named "<kit> (self)" (38005), the item's own icon; the entry's usable flag is never cleared (no refusal reason), but its icon is drawn at 0.25 while the leader is dead or dying | 0x00619db0, 0x006197d0, 0x00616520, 0x006193a0, UpdateActionMenus 0x00689d80 | matches (ours never dimmed it and ignored RestrictMode; the worn items the original also scans are never kits; every shipped kit has a Trap property) | `recover_lay.txt` |
| A click lays the kit at the leader's feet: SETTRAP with the leader as the target and no point, in place of its queue; refused with 15 of the party's mines in the area or without Demolitions | 0x0060f590, UseItem property 46 branch, 0x005089d0 | matches | `recover_lay.txt`, `enemy_mine.txt` |
| 2 s of `setmine` (10140), `gui_minearm` 750 ms in; Demolitions (+2 with more than 4 base ranks) + 20 or d20 against traps.2da SetDC: success lays it; a miss by 10 or less (or any miss taking 20) lays nothing and keeps the kit; a worse miss (in combat) still lays it | SETTRAP | matches | `recover_lay.txt` (35 vs 15), `enemy_mine.txt` (19 vs 15, in combat) |
| The new mine: a 4 x 4 m trigger at the setter's feet, the setter's faction, CreatorId and SetByPlayerParty, the type's TrapName and TrapScript, detect and disarm DCs = the roll's total + the type's mods, detectable, disarmable, one-shot; the kit is spent (one off the stack, only from the party's bag); sound set 0x13 on success, 0x18 on a failure (also a worse miss that laid it) | SETTRAP | matches | `recover_lay.txt` |
| Stealth stays: every attempt (laid or not) ends the setter's activities 4 and 8 (not stealth, 1) and removes its Invisibility (type 1) and Sanctuary effects; stealth's own effect (0x3b) is left | SETTRAP, 0x004eb1b0 (mask 0xe), 0x004f5f70, ApplyStealthEffects 0x004f6d70 | matches for stealth and the effects (`rules::remove_invisibility_and_sanctuary`: invisibility of type 1, sanctuary, each with its link); activities 4 and 8 are not modelled | by reading (`recover_lay.txt` starts unhidden) |

## 7. Saves

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A disarmed or spent trap stays gone (its trigger is not saved) | SaveTrigger 0x0058e660 | matches | save/load by hand (above) |
| The save keeps TrapType, TrapOneShot, CreatorId, SetByPlayerParty, TrapDisarmable, TrapDetectable; the DCs come back from traps.2da on load (a laid mine loses its skill-based DCs) | SaveTrigger 0x0058e660 | matches | |
| Which traps the party had found, and flagged | not saved by the original (the detected list `+0x2a8` and `+0x2c8`) | ours: kept (PartyDetected, TrapFlagged), so a found mine stays shown after a load as the brief asked | save/load by hand |

## 8. Script routines

GetTrapBaseType (531) is the only trap routine a shipped script calls (k_trp_generic). The others read the
fields above (handler 0x0054c0e0 for most) and are built in `routines/objects.ctx`, unexercised (no shipped
script calls them): GetTrapDisarmable, GetTrapDetectable, GetTrapFlagged, GetTrapOneShot, GetTrapDisarmDC,
GetTrapDetectDC, GetIsTrapped (0x0053a000, the trap's armed flag), GetTrapCreator, GetTrapKeyTag;
GetTrapDetectedBy and SetTrapDetectedBy (ours keeps one party-wide flag, not the original's list of finders: a
party member answers and sets it, an NPC's find is kept nowhere); SetTrapDisabled (an armed trap gets DISARM from
the caller, then goes); GetLastDisarmed (0x0053adb0: a trap trigger's last disarmer, a DISARM event's caller or
the key's carrier); GetLastTrapDetected (always OBJECT_INVALID). GetNearestTrapToObject is not built.

## Known gaps

- No action-timer bar: the original's client drops the message too (0x00654a30).
- Crossing a trap's outline does not set it off here (section 5).
- `kotor` has a pace problem of its own: in tar_m04aa and tar_m05aa the smoke run's frame time grows with the
  world time (1.8 ms at 6000 ticks before the merge of `kotor`, 4 ms after, also on `kotor` alone) and the
  18000-tick run times out; not caused by traps (the same on the `kotor` build without them).
