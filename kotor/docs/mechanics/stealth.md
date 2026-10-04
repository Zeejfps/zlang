# Stealth in play: the original's behaviour and where we stand

What the original does when a creature hides, is looked for, is found and stops hiding, one line per
behaviour, with the evidence and our status. The status is **matches** (checked by a run that goes
through the mouse and keys, named in the last column), **open** (with the reason), or **script** (the
original's own scripts do it; we run them). Evidence is the RE notes ([rules.md](../re/rules.md) 5.3,
[actions.md](../re/actions.md) 1.4, [gui.md](../re/gui.md) `TB_STEALTH` and the solo-mode box,
[party-items-saves.md](../re/party-items-saves.md) 3.7, [movement.md](../re/movement.md) 3.1-3.2) and the
decompiled functions named in the lines (`python kotor/tools/py/rex.py fn ADDR`; names in
[names.tsv](../re/names.tsv)).

The code: [lib/engine/stealth.ctx](../../lib/engine/stealth.ctx) (the mode, the two contests, stealth XP),
[lib/hud/stealth.ctx](../../lib/hud/stealth.ctx) (the toggle), [lib/ingame/stealth_ui.ctx](../../lib/ingame/stealth_ui.ctx)
and `ask_solo` in [lib/ingame/ingame.ctx](../../lib/ingame/ingame.ctx) (the clicks, G, V and the solo-mode box),
[lib/scene/stealth_look.ctx](../../lib/scene/stealth_look.ctx) (the shimmer).

## How these were tested

`sh kotor/tools/stealth/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...` runs an input script with
`--no-render --speed 8` from a checkpoint (`uppercity`: Carth in the party), a module (`module:end_m01ab`:
the player alone, Sith standing guard ahead) or a save (`save:FOLDER`), and keeps the log and the pictures
under `kotor/out/stealth/`. The scripts are in `kotor/tools/stealth/scripts/`; each says what it expects.
Stealth is switched on and off only by clicking `TB_STEALTH` (`ui clickctl`), pressing G or V (`ui key`),
answering the solo-mode box (`ui clickctl BTN_OK`), taking the belt off in the equipment screen (U, the
belt slot, the None row, Equip), attacking from the target block (`ui target` + key 1), or walking (W held:
`down w` / `up w`, or `ui goto`, the move a floor click makes). Test-only commands are setup: `ui stat
stealth N` (ranks), `ui giveitem g_i_belt010 1 equip` (the chargen Stealth Field Generator), `hush` (ends
Carth's comm call that opens end_m01ab). `ui stealth [TAG]` only prints: the mode, whether the toggle
shows, solo mode, combat, the area's stealth XP, and who sees or hears the creature.

| Script | Start | What it showed |
|---|---|---|
| `walk_past.txt` | module:end_m01ab | the click hides the leader; it walks up to 13 m from the Sith soldiers: nobody attacks, end_sith03 hears it but never sees it, the area's stealth XP stays 300/300 |
| `walk_control.txt` | module:end_m01ab | the same walk without stealth: end_sith03 attacks at frame 237, the soldiers after; stealth XP 300 to 0 |
| `attack_out.txt` | module:end_m01ab | target block, key 1: stealth ends as the swing starts (frame 584), the soldier has no perception of the attacker for it (no dodge), it then sees the leader and attacks, stealth XP 300 to 0 at once |
| `key_unequip.txt` | module:end_m01ab | G hides; W for 2 s moves 5.8 m (9.1 m running without stealth); the belt taken off in the equipment screen ends stealth and hides the toggle; G then does nothing |
| `combat_refused.txt` | module:end_m01ab | G in combat: "You cannot enter stealth mode while in combat." on the HUD (`combat_refused_refused.png`) |
| `solo_box.txt` | uppercity | the toggle without a belt does nothing; with it the click asks 37890 and pauses, OK: solo mode on and hidden; Carth stays 14 m behind as the leader walks off (`solo_control.txt`: he follows to 3 m); TB_SOLO asks 37892, OK ends both; V asks 37889, Cancel changes nothing (`solo_box_box.png`, `solo_box_off.png`) |
| `save_hiding.txt`, `load_hiding.txt` | module:end_m01ab, then the save | a save made while hiding loads hiding, with the area's stealth XP pool |

Pictures: `walk_past_walk.png` and `key_unequip_walk.png` show the shimmer.

## 1. Hiding and stopping

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| UseSkill(Stealth), the HUD's toggle and G run one toggle on the leader: out if in; refused when dead, down or without the skill; in combat refused with feedback 0x3c, 1452; otherwise in | `0x004f2a50` mode 1, UseSkill `0x004fbe40`, feedback formatter `0x005fcd10` | matches | `walk_past`, `key_unequip`, `combat_refused` |
| "Without the skill" means no bought Stealth ranks (trained-only skill, `0x005af880`): a stealth unit's bonus alone does not make a creature able to hide | `0x005af880` | matches | `solo_box` (ranks set first) |
| Scripts may hide a creature without a stealth unit: UseSkill does not ask for one (only the HUD and G do) | `0x004fbe40` | matches (`ActionUseSkill`, and a skill talent) | (the Leviathan's `k_plev_jucs0` does this) |
| Entering: the sound set's "begin stealth" line (slot 21); a walk-only limit (LIMIT_MOVEMENT_SPEED tagged as stealth's) | `0x00613930`, `0x004f6d70` | matches (the limit is read from the flag: no effect object) | `walk_past` |
| Leaving: the cloak-removal visual effect (8001: its sound `v_dur_cloakoff`) | `0x00613930` | matches (the sound; the 8001 picture is a frame-buffer distortion we do not draw) | `attack_out` |
| Walking: stealth moves at the walk rate (keyboard and clicks); the walk animation | GetWalkRate `0x004f1b20`, MoveToPoint run flag, GetMaxSpeed | matches with the walk rate; open: the client's own stealth speed field (`+0x21c` block `+0x60`) was never seen written | `key_unequip` |
| Ended by an attack (the combat round's next action), by entering combat as the attacked (`AIUpdate`, reason 1), by casting one's own power (an item's ability keeps it), by SPEAK actions, by Rest | `0x005b6210`, `0x004fe210`, ClearActivities callers (actions.md 1.4) | matches (attack, combat, power; ActionSpeakString and ActionSpeakStringByStrRef, which speak at once in ours); open: Rest (no party rest yet) | `attack_out` |
| Not ended by moving, opening doors and locks, using placeables, picking up, equipping, item abilities, traps, healing (their actions clear only the combat modes) | ClearActivities(2) callers, Stealth's description (248) | matches (nothing of ours ends it there) | `walk_past` (walks), by reading |
| Being seen does not end it: a creature that finds the hider reacts through its scripts; stealth ends when the fight reaches the hider | `0x00502ac0`, `0x004fe210` | matches | `walk_past` (heard, still hidden) |
| Taking the stealth unit off (ItemType 44) while hiding ends it | UnequipItem `0x004faa70` | matches | `key_unequip` |
| A conversation in the letterbox panel takes the player's character and every party member out of stealth; a computer's does not | LoadDialog `0x005a2ae0`, SetPartyStealthMode `0x00563c60` | matches | `walk_past` (the comm call before stealth; by reading) |
| A transition: the party arrives out of stealth and out of solo mode; a loaded save keeps both | PlacePartyAroundLeader `0x00565b00` | matches | `load_hiding` (kept); transitions by reading |
| SetPlayerRestrictMode(TRUE) on an unrestricted area takes the party out of stealth | `0x00506b90` | matches | by reading |

## 2. The HUD and solo mode

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| `TB_STEALTH` shows while the leader can hide: area not restricted, Stealth ranks, a stealth unit (ItemType 44) on the belt or as the creature hide (baseitems row 88's EquipableSlots 0x20400); checked while the leader hides; tooltip 247 "Stealth" | `0x00610ac0`, CSWGuiMainInterface Update `0x00686ba0` | matches | `solo_box`, `key_unequip` |
| G (keymap action 264) does what a click does, but only when the toggle would show | HandleInputAction case 0x108 | matches | `key_unequip` |
| With a companion in the party and solo mode off, the toggle asks first: 37890 "To use Stealth, you must turn Solo Mode on..."; OK turns solo mode on, then the leader hides | `0x0060f4b0`, SetMode `0x006c24a0`, the box's OK `0x006c2400` | matches | `solo_box` |
| `TB_SOLO` and V ask 37889 (on), 37891 (off) or 37892 (off while the leader hides: "...will take you out of Stealth Mode"); OK turns solo mode over and runs `k_sup_solo` (not shipped); turning it off takes the party out of stealth | SetMode, `0x005f2a20`, SetSoloMode `0x00565500` | matches | `solo_box` |
| The box only with a companion, no conversation, the leader on its feet (else the refusal sound); the game pauses while it is up; it closes itself if a conversation starts or the leader falls | ShowSoloModeConfirm `0x0062e550`, the box's Render | matches (pause by the player pause, as the original's TogglePlayerPause) | `solo_box` (`solo_box_off.png` shows the pause) |
| In solo mode companions stay where they are: k_ai_master's heartbeat does not send them after the leader and stops one that follows | k_ai_master (GetSoloMode), party-items-saves.md 3.7 | script (GetSoloMode now answers the flag; the follow action's steps answer FOLLOWLEADER to GetCurrentAction, which the script asks) | `solo_box` vs `solo_control` |
| Tab still changes the leader in solo mode; the straggler teleport is off | `0x005f7960`, gameloop.md 6.7 | matches (Tab unchanged); the teleport is not built | by reading |
| The first companion to join a hiding player turns solo mode on; the last to leave turns it off | AddPartyMember `0x00565620`, RemovePartyMember `0x00565560` | matches | by reading |
| Stealth is per creature: only the leader is toggled by the HUD, and with companions only in solo mode | `0x0060f4b0`, `0x004f2a50` | matches | `solo_box` |

## 3. Being found

The arithmetic is [rules.md](../re/rules.md) 5.3 (our own words, with the addresses). In short: a hiding
creature with Stealth ranks is seen when the viewer's Awareness plus its d20 look roll, minus the hider's
Stealth and its d10 + 10 hide roll, minus 5 behind the viewer's back, minus 10 in combat, minus 5 while the
hider stands still, plus 5 while the viewer does, minus a point per 3 m beyond 6 m, comes to 1 or more; heard
the same way with a listen roll, a wall term (indoors -2, outdoors -5 a metre), no 6 m grace and the hider's
size. Each creature rolls again every 20 s.

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| The two contests, their terms, the 20 s rolls | `0x004f1fd0`, `0x004fb4b0`, `0x00502ac0` | matches; ours: the rolls come from a hash of the creature and the time, not the world's dice, so hiding changes no other roll of the game (the original uses rand()) | `walk_past` |
| A creature without Stealth ranks, or not in stealth mode, is perceived as usual | both contests | matches | `walk_control` |
| Party members always perceive each other | `0x00502ac0` | partly: in stealth they do; their ranges and line still apply otherwise (unchanged from before) | by reading |
| See-invisible (vision bit 4) sees a hider | `0x004f1fd0` | matches | by reading |
| A hidden attacker's first swing finds the defender flat-footed (no dodge) | the defender has no perception of it (combat.md 5) | matches | `attack_out` |
| The spot line in the combat log (feedback type 0x10 with the terms) | `0x004ec7a0` | open: the client's text for it was not read | |

## 4. How it looks

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A hiding creature (body, head, weapons) is drawn with `fx_tex_stealth` over its model: an additive 2x2 flipbook at 8 frames a second (its TXI), so it shows as a moving shimmer with the room through it | VFX_DUR_STEALTH_FIELD 8002, programmed effect 1426 (`0x006a5000`, `0x006a1220`) | matches (we draw the texture in place of the model's own; how the original blends it with the model was not read) | `walk_past_walk.png` |
| With the "frame buffer effects" option the original takes VFX_DUR_DISTORTION (8000) instead, a screen-space ripple | `0x00613930`, `0x0061d750` | open: no frame-buffer effects yet | |
| VFX_DUR_STEALTH_PULSE (2000) is a script's effect; its programmed effect 2000 is outside the ranges the client's dispatcher draws | `0x006a5000` | matches (nothing drawn) | |

## 5. Stealth XP

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Each area has a pool: ARE StealthXPEnabled, StealthXPMax, StealthXPLoss; the current amount starts full and is saved (GIT AreaProperties StealthXPCurrent and the rest) | LoadProperties `0x00507490` | matches (16 AREs enable it, e.g. end_m01ab 300/300, tar_m09aa 800/200) | `walk_past`, `load_hiding` |
| A creature newly seeing the player's character or the leader costs the loss 6 s later, at once if it attacks one of them meanwhile; never below 0 | `0x00502ac0`, AIUpdate `0x004fe210`, ResolveAttack `0x005bba80` | matches; ours: a companion's first sight of the leader in a new area costs it too, as the code reads (not seen in play) | `walk_control`, `attack_out` |
| AwardStealthXP pays the pool to the party, lights the stealth XP icon (LBL_STEALTHXP, the status summary's kind 3), empties and disables it; the setters keep current at most max | `0x00508770`, `0x00506a80`, `0x00506aa0` | matches by reading: no shipped area places one of the award triggers (`ptar_stealthxp` is never in a GIT), so no run reaches it | |

## 6. Script routines

| Routine | Status |
|---|---|
| ActionUseSkill(SKILL_STEALTH, ...), ActionUseTalentOnObject(TalentSkill(SKILL_STEALTH)) | toggle stealth (1) |
| GetSoloMode, SetSoloMode | the party's flag; off ends the party's stealth (2) |
| SetPlayerRestrictMode | restricting ends the party's stealth (1) |
| Get/SetMaxStealthXP, Get/SetCurrentStealthXP, Get/SetStealthXPEnabled, Get/SetStealthXPDecrement, AwardStealthXP | the area's pool (5) |

There is no routine that asks whether a creature hides (KOTOR's nwscript has none).

## 7. Saves

`StealthMode` (BYTE) is written for every creature and read back by the creature loader, so a saved
hider loads hiding (LoadCreature `0x00500350`); `PT_SOLOMODE` keeps solo mode; the GIT's AreaProperties
keep the stealth XP pool. Matches (`save_hiding` / `load_hiding`).

## Decisions (ours)

- The walk-only limit and the shimmer are read from the creature's stealth flag instead of an effect and a
  visual effect on the creature: the same behaviour, nothing for scripts to see in either case.
- Stealth speed is the walk rate (the original's client field was not traced to its source).
- The stealth rolls come from a hash of the creature and the 20 s period, not `rand()`.
- The 8000/8001 frame-buffer pictures are not drawn; 8001's sound is played.

## Open items

- The client's stealth speed (`+0x21c` block `+0x60`).
- Frame-buffer effects (VFX 8000 distortion, 8001's picture).
- The combat log's spot line (feedback type 0x10).
- Rest ending stealth (no party rest yet).
- The straggler teleport that solo mode turns off (not built).
