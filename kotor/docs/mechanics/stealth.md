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

`sh kotor/tools/stealth/check.sh` runs them all and checks the lines each must (or must not) log. Pictures
(`run.sh ... FRAME:SHOT`): `walk_past_walk.png` (frame 150) and `key_unequip_walk.png` (100) show the shimmer.

## 1. Hiding and stopping

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| UseSkill(Stealth), the HUD's toggle and G run one toggle on the creature (`SetActivityMode` mode 1; the HUD and G send the leader's request as server input 6/7, use skill 2, which UseSkill turns into it): nothing for a dead or dying creature or one without the skill; out if in; in combat refused with feedback 0x3c, 1452; otherwise in, except that nothing happens while the creature is in a conversation (activity 4) or has activity 8 set; an activity locked in `+0xa00` is never changed | `0x004f2a50` mode 1, UseSkill `0x004fbe40`, the request `0x0060ee00`, feedback formatter `0x005fcd10` | matches; open: ours does not refuse entering during a conversation (activity 4 or 8; only a script can ask then) | `walk_past`, `key_unequip`, `combat_refused` |
| "Without the skill" means no bought Stealth ranks (skills.2da `untrained` 0 for Stealth, so `0x005af880` asks for ranks above 0): a stealth unit's bonus alone does not make a creature able to hide | `0x005af880` | matches | `solo_box` (ranks set first) |
| Scripts may hide a creature without a stealth unit: UseSkill does not ask for one (only the HUD and G do) | `0x004fbe40` | matches (`ActionUseSkill`, and a skill talent) | (the Leviathan's `k_plev_jucs0` does this: ActionUseSkill(SKILL_STEALTH, OBJECT_SELF)) |
| Entering: the sound set's "begin stealth" line (slot 21); a walk-only limit (LIMIT_MOVEMENT_SPEED, innate, int0 1, tagged as stealth's) | `0x00613930`, `0x004f6d70` | matches (the limit is read from the flag: no effect object) | `walk_past` |
| Leaving: the stealth field (8002, or 8000) comes off and the cloak-removal visual effect plays (VFX_DUR_CLOAK_REMOVAL 8001: its sound `v_dur_cloakoff`; its picture is programmed effects 1423, a texture effect, and 1800, the distortion; which of them draws was not read) | `0x00613930` | matches (the sound; we draw no 8001 picture) | `attack_out` |
| Walking: a hider walks (keyboard and clicks). Its pace in stealth is the appearance's DriveAnimWalk read as m/s (the client movement block `+0x21c` `+0x60`, filled from appearance.2da by `0x00698b10`, 2.0 when the column is 0): the server's walk rate in stealth for a creature with a client twin, not scaled by speed effects, and the client's cap on the driven leader (1.6 to 1.9 m/s for the humanoid rows; needs a runtime check). Its walk and run animations become the stealth walk (10133) | GetWalkRate `0x004f1b20`, SetAnimation `0x004f0d70`, GetMaxSpeed `0x00679510`, movement.md 3.1, 3.6 | open: ours walks at the creature's walk rate (speed effects included) with the ordinary walk animation | `key_unequip` |
| Ended by the combat round's next scheduled action (anything but an item use: an attack, a cast, an equip, a move), by being in combat as the attacked (`AIUpdate`, combat reason 1, every update), by casting one's own power, by using an item whose spell is hostile (spells.2da HostileSetting: ITEMCASTSPELL and the round's item use; other item abilities keep it), by SPEAK actions, by Rest (`0x004eb1b0` with 0xf, at `0x004fd2ba`); a stealth locked in `+0xa00` stays | `0x005b6210`, `0x004fe210`, ITEMCASTSPELL `0x0050f170`, ClearActivities `0x004f87d0` callers (actions.md 1.4), Rest `0x004fd1e0` | matches (attack, combat, power; ActionSpeakString and ActionSpeakStringByStrRef, which speak at once in ours); open: a hostile item ability ends ours only when it puts the user in combat with a hostile creature it targets (one used at a point keeps it); Rest (no party rest yet) | `attack_out` |
| Not ended by moving, opening doors and locks, using placeables, picking up, equipping, item abilities whose spell is not hostile, traps (laying a mine removes only invisibility and sanctuary effects, `0x004f5f70`), healing (their actions clear only the combat modes) | ClearActivities(2) callers, AIActionSetTrap `0x00519e30`, Stealth's description (248) | matches, except: open: laying a mine takes ours out of stealth (traps.ctx clears the flag) | `walk_past` (walks), by reading |
| Being seen does not end it: a creature that finds the hider reacts through its scripts; stealth ends when the fight reaches the hider | `0x00502ac0`, `0x004fe210` | matches | `walk_past` (heard, still hidden) |
| Taking the stealth unit off (ItemType 44) while hiding ends it | UnequipItem `0x004faa70` | matches | `key_unequip` |
| A conversation in the letterbox panel (any ConversationType but 1) takes the player's creature and every party member out of stealth; a computer's does not | LoadDialog `0x005a2ae0`, SetPartyStealthMode `0x00563c60` (it only ever turns stealth off, whatever it is passed) | matches | `walk_past` (the comm call before stealth; by reading) |
| A transition: the party arrives out of stealth and out of solo mode; a loaded save keeps both | PlacePartyAroundLeader `0x00565b00` | matches | `load_hiding` (kept); transitions by reading |
| SetPlayerRestrictMode(TRUE) on an unrestricted area takes the party out of stealth; the area loaders do the same when they read a RestrictMode that is set and differs (the ARE, a save's GIT AreaProperties) | `0x00506b90`, LoadAreaHeader `0x00508c50`, LoadProperties `0x00507490` | matches for the routine; open: ours does not read a save's RestrictMode back | by reading |

## 2. The HUD and solo mode

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| `TB_STEALTH` shows while the player's creature (the one it controls, the leader) can hide: area not restricted, Stealth ranks, a stealth unit (ItemType 44) on the belt or as the creature hide (baseitems row 88's EquipableSlots 0x20400); checked while the leader hides; tooltip 247 "Stealth" | `0x00610ac0`, CSWGuiMainInterface Update `0x00686ba0` | matches | `solo_box`, `key_unequip` |
| G (keymap action 264) does what a click does, but only when the toggle would show | HandleInputAction case 0x108 | matches | `key_unequip` |
| With a companion in the party and solo mode off, the toggle asks first: 37890 "To use Stealth, you must turn Solo Mode on..."; OK turns solo mode on, then sends the same stealth request for the player's creature | `0x0060f4b0`, SetMode `0x006c24a0`, the box's OK `0x006c2400` | matches | `solo_box` |
| `TB_SOLO` and V ask 37889 (on), 37891 (off) or 37892 (off while the leader hides: "...will take you out of Stealth Mode"); OK turns solo mode over and runs `k_sup_solo` (not shipped); turning it off takes the party out of stealth | SetMode, `0x005f2a20`, SetSoloMode `0x00565500` | matches | `solo_box` |
| The box only with a companion, no conversation, no load or pending area transition, the leader on its feet (else the refusal sound); the game pauses while it is up (unless the player had paused); it closes itself if a conversation starts, a load or transition begins, or the leader falls | ShowSoloModeConfirm `0x0062e550`, the box's Render | matches (pause by the player pause, as the original's TogglePlayerPause) | `solo_box` (`solo_box_off.png` shows the pause) |
| In solo mode companions stay where they are: k_ai_master's heartbeat does not send them after the leader and stops one that follows | k_ai_master (GetSoloMode), party-items-saves.md 3.7 | script (GetSoloMode now answers the flag; the follow action's steps answer FOLLOWLEADER to GetCurrentAction, which the script asks) | `solo_box` vs `solo_control` |
| Tab still changes the leader in solo mode; the straggler teleport is off | `0x005f7960`, gameloop.md 6.7 | matches (Tab unchanged); the teleport is not built | by reading |
| The first companion to join a hiding player turns solo mode on; the last to leave turns it off (directly: stealth stays) | AddPartyMember `0x00565620`, RemovePartyMember `0x00565560` | matches | by reading |
| Stealth is per creature: only the leader is toggled by the HUD, and with companions only in solo mode | `0x0060f4b0`, `0x004f2a50` | matches | `solo_box` |

## 3. Being found

The arithmetic is [rules.md](../re/rules.md) 5.3 (our own words, with the addresses). In short: a hiding
creature with Stealth ranks is seen when the viewer's Awareness plus its d20 look roll, minus the hider's
Stealth and its d10 + 10 hide roll, minus 5 behind the viewer's back, minus 10 in combat, minus 5 while the
hider stands still, plus 5 while the viewer does, minus a point per 3 m beyond 6 m, comes to 1 or more; heard
the same way with a listen roll, a wall term (indoors -2, outdoors -5 a metre), the area's ModListenCheck (0
in every shipped area), no facing term, no 6 m grace and the hider's size. Each creature rolls again every 20 s.

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| The two contests, their terms, the 20 s rolls | `0x004f1fd0`, `0x004fb4b0`, `0x00502ac0` | matches; ours: the rolls come from a hash of the creature and the time, not the world's dice, so hiding changes no other roll of the game (the original uses rand()) | `walk_past` |
| A creature without Stealth ranks, or not in stealth mode, is perceived as usual | both contests | matches | `walk_control` |
| Party members always perceive each other | `0x00502ac0` | partly: in stealth they do; their ranges and line still apply otherwise (unchanged from before) | by reading |
| True seeing (vision bit 4, set by TRUE_SEEING) sees a hider; see invisible (bit 1) does not | `0x004f1fd0`, `0x004e35b0`, `0x004dcd00` | open: ours tests bit 4, which our effects set for see invisible (true seeing sets 2), so in ours see invisible sees a hider and true seeing does not | by reading |
| A hidden attacker's first swing finds the defender flat-footed (no dodge) | the defender has no perception of it (combat.md 5) | matches | `attack_out` |
| The spot line in the combat log (feedback type 0x10 with the terms) | `0x004ec7a0` | open: the client's text for it was not read | |

## 4. How it looks

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| A hiding creature is drawn with `fx_tex_stealth` over its model and over the item in its head slot: an additive 2x2 flipbook at 8 frames a second (its TXI), so it shows as a moving shimmer with the room through it | VFX_DUR_STEALTH_FIELD 8002, programmed effect 1426 (`0x006a5000`, `0x006a1220`) | matches (we draw the texture in place of the model's own, the weapons included; how the original blends it with the model, and whether its weapons take it with the model, was not read) | `walk_past_walk.png` |
| With the "frame buffer effects" option the original takes VFX_DUR_DISTORTION (8000) instead, a screen-space ripple | `0x00613930`, `0x0061d750` | open: no frame-buffer effects yet | |
| VFX_DUR_STEALTH_PULSE (2000) is a script's effect; its programmed effect 2000 is outside the ranges the client's dispatcher draws | `0x006a5000` | matches (nothing drawn) | |

## 5. Stealth XP

| Behaviour | Evidence | Status | Test |
|---|---|---|---|
| Each area has a pool: ARE StealthXPEnabled, StealthXPMax, StealthXPLoss; the current amount starts full and is saved (GIT AreaProperties StealthXPCurrent and the rest) | LoadProperties `0x00507490` | matches (16 AREs enable it, e.g. end_m01ab 300/300, tar_m09aa 800/200) | `walk_past`, `load_hiding` |
| A creature newly seeing the player's character or the leader costs the loss 6 s later, at once if it attacks one of them meanwhile; never below 0; the countdown runs only while the area pays stealth XP, and is dropped otherwise | `0x00502ac0`, AIUpdate `0x004fe210`, ResolveAttack `0x005bba80` | matches; ours: a companion's first sight of the leader in a new area costs it too, as the code reads (not seen in play); open: ours keeps a countdown while the pool is off and charges it if the pool comes back on | `walk_control`, `attack_out` |
| AwardStealthXP pays the pool to the party, lights the stealth XP icon (LBL_STEALTHXP, the status summary's kind 3), empties and disables it; the setters keep current at most max | `0x00508770`, `0x00506a80`, `0x00506aa0` | matches by reading: of the award triggers only end_m01ab's GIT places one (`k_stlthawrd`, OnEnter `k_trg_stealth`: AwardStealthXP(GetFirstPC()) on a party member's first entry; `ptar_stealthxp` and the others are templates no GIT uses); no run has walked into it yet | |

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
- The stealth rolls come from a hash of the creature and the 20 s period, not `rand()`.
- The 8000 frame-buffer picture and 8001's picture are not drawn; 8001's sound is played.

## Open items

- The stealth pace (appearance DriveAnimWalk, not the walk rate) and the stealth walk animation (10133).
- True seeing, not see invisible, sees a hider (our vision bits differ from the original's).
- Laying a mine ends stealth in ours; it does not in the original.
- A hostile item ability used at a point ends stealth in the original, not in ours.
- Entering stealth during a conversation (activity 4 or 8) is refused in the original.
- A stealth-XP countdown is dropped while the area's pool is off.
- A save's RestrictMode is not read back.
- Frame-buffer effects (VFX 8000 distortion, 8001's picture).
- The combat log's spot line (feedback type 0x10).
- Rest ending stealth (no party rest yet).
- The straggler teleport that solo mode turns off (not built).
