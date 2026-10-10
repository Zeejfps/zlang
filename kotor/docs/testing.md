# Testing: which tool for which question

Every check starts from the same executable (`kotor/tools/ctxc exe kotor -o kotor/out/kotor.exe`) or one of the
tools under `kotor/tools/`. Pick the cheapest tool that can answer; the table says which that is. Times are for
the 24-core development machine.

| Question | Tool | Time |
|---|---|---|
| Does this parser read every resource of its type? | the corpus tool for the format (`dlgcheck`, `fmtcheck`, `texcheck`, `mdlcheck`, `walkcheck`, ...) | seconds to a minute |
| Does a script, routine or the VM do the right thing in a module? | `kotor.exe --engine-only --module M --frames N --log routines --report routines`, or `tools/enginetest` | well under a second |
| Does any module fault, hang, crash or lack a routine, with a party that walks it? | the module smoke test, `sh kotor/tools/smoke/run.sh` → [smoke.md](smoke.md) | 4 minutes for all 117 |
| Does a conversation shot show something (not a black or empty frame: Trask on the Endar Spire, Carth in the Taris apartment, the Dantooine Council)? | `sh kotor/tools/camcheck/run.sh` → [Conversation shots](#conversation-shots) | 20 s |
| Do our `savenfo.res`, `GLOBALVARS.res` and `PARTYTABLE.res` read an original save and write it back byte for byte (names in the engine's hash order, the load-screen hint counters, the message logs with their speakers), and does our own save round-trip? | `kotor/tools/ctxc run kotor/tools/savetest -- [--save DIR] --out kotor/out/savetest` (default: the install's `000002 - Game1`). The expected values come from the files, since the install's saves are the player's and change as they play; any manual save, the original's or ours, passes. A transition autosave fails on `SCREENSHOT` and `AUTOSAVEPARAMS`, which we don't write yet | seconds |
| Do our rules give the original's numbers (worked examples, class tables, templates, and the totals every creature in the install's saves carries: saves, HP, FP, armour class, CombatInfo)? | `kotor/tools/ctxc exe kotor/tools/rulescheck -o kotor/out/rulescheck.exe`, then run it: no failures | seconds |
| Does every conversation's graph and scripts run? | the conversation sweep, `sh kotor/tools/dlgsweep/run.sh` → [dlgsweep.md](dlgsweep.md) | 45 s for all 1,262 |
| Does the story still play from here to there? | the playthrough replay, from a checkpoint if it can start in the middle ([playthrough.md](playthrough.md)) | 30 s for the Endar Spire, 1-2 min to the Undercity from the apartment; Dantooine (`sh kotor/tools/playthrough/dantooine/all.sh`, [playthrough-dantooine.md](playthrough-dantooine.md)) 8 min |
| Does it look right? | a screenshot (`--screenshot-at FRAME:PNG`), read with the Read tool | one run |
| Does the sound play without stutters, stolen voices or clipping (a fight, the Endar Spire's loops, at real pace)? | `EXE=... sh kotor/tools/sndrun/run.sh`: headless with `--sound-device` and SDL's `disk` driver (no speakers), FAIL on a stolen voice, more than 5 underruns, a dropout after the first second or 100 clipped samples; `STALL=250` adds `--stall 250` (every 15th frame sleeps 250 ms more) and then FAILs on any underrun past the first second, which the mixer's thread must play through; also FAIL when the Endar Spire run plays no footlocker or door open sound, or `kotor/tools/sndrun/doors.sh` (alone: 30 s; from the uppercity checkpoint a locked door is tried, then bashed: its `Locked` sound with feedback 1437 and the text 1439, metal hit sounds, `Opened`; a second door killed by `fx death TAG N` is destroyed, not opened, and gone 60 frames later; a trooper given an item with `ui carry` is killed and its body bag, opened with `ui loot bag` and closed, sounds as the corpse, `pl_corpse_close`; all from `--log sound,objects`) fails; `OUT=DIR` keeps one run's logs apart; `--log sound` and `python kotor/tools/py/sndscan.py OUT.raw` for one run of your own ([design/audio.md](design/audio.md), "Checked") | 5 min |
| Do the sound modes follow the screen and the window (the window's activation lost and back, 5 / 6, with a menu opened and closed meanwhile; a save written, 3)? | `EXE=... sh kotor/tools/sndrun/modes.sh` (from `uppercity`, `kotor/tools/sndrun/modes.txt`; the scripted `focus lost|gained` stands for the window's activation; `--log sound` prints `sound mode N: K sounds held`), FAIL and exit 1 unless the modes run 5 6 4 5 0 6 3 0 with sounds stopped at the first 5 and the save's 3; the mixer's part is `kotor/tools/ctxc run kotor/tools/mixtest` ([design/audio.md](design/audio.md) "Sound modes") | 10 s |
| Does a graphics option, a window size or the GUI scale work? | `FRAME gfx KEY VALUE` input lines (`--gfx --settings FILE` to read an options file headless), `sh kotor/tools/gfx/sizes.sh EXE` for four scenes at five sizes, the scripts in `kotor/tools/gfx/scripts/` ([mechanics/graphics.md](mechanics/graphics.md)) | seconds |
| Do the rooms' and objects' particle emitters (smoke, sparks, fire) run, and does the Emitters option drop them? | `sh kotor/tools/gfx/world_emitters.sh EXE`: PASS when the Endar Spire corridor's smoke is drawn with the option on and nothing with it off (the screenshot log's `world emitters:` line; [design/vfx.md](design/vfx.md), "World emitters") | 10 s |
| Do effect particles fall and bounce in the world (gravity world -Z, not the emitter's), so the Endar Spire duel's clash sparks stay behind its closed door? | `sh kotor/tools/gfx/duel_sparks.sh EXE` (the `bunk` checkpoint): PASS when three shots beside the duel at clashes have at least 100 bright spark pixels each (the sparks draw) and five shots in front of the door, during the clashes and after, at most 40 spark-yellow pixels each ([design/vfx.md](design/vfx.md), "Particles in the world") | 1 min |
| Do beams (Force lightning, shock, drain life, the death field) draw their Lightning emitters as jagged Linked ribbons from the caster's hand to the target? | `python kotor/tools/py/force_run.py --powers 35 --target g_sithtroop01 --dist 6 --frames 92 --shots 72,82 --exe EXE` (EXE an absolute path; 35 lightning; 43 shock, 15 drain life, 11 death field): look at `kotor/out/frc/pw_35_72.png`, a chain with branches from the hand to the trooper, which dies at frame 66 and ends the beam soon after ([design/vfx.md](design/vfx.md), "Force powers' presentation") | 20 s |
| Do particles stay in the world when their emitter moves, unless its `inherit` flags carry it (a walking character's Cure sparkles left behind, bolts and room sprites unchanged)? | `python kotor/tools/py/force_run.py --powers 10 --dist 12 --cast-at 500 --post '64 mouse click 1113 688;72 down w;111 up w' --shots 86,102 --exe EXE` (Cure from the first self slot, then a run): `kotor/out/frc/*_102.png` shows the sparkles left along the 5 m he ran, not gathered on his body as when they moved with him ([design/vfx.md](design/vfx.md), "Particles in the world") | 15 s |
| Do point-to-point emitters pour their particles into their target (Fear's red streaks into the victim's head)? | `python kotor/tools/py/force_run.py --powers 16 --target g_sithtroop01 --dist 6 --frames 100 --shots 70,78,86 --exe EXE`: `kotor/out/frc/pw_16_86.png` shows thin red streaks converging on the trooper's head, which the build without `p2p` did not draw ([design/vfx.md](design/vfx.md), "Particles in the world") | 15 s |
| Does a thrown lightsaber fly lit and spinning (code 1300 plays the model's `throwout`)? | `python kotor/tools/py/force_run.py --powers 49 --target g_sithtroop01 --dist 10 --pre '6 ui giveitem g_w_lghtsbr01 equip' --frames 130 --shots 84,88,92,106 --exe EXE`: `kotor/out/frc/pw_49_88.png` shows the flying saber with its blade lit, at another angle in each picture ([design/vfx.md](design/vfx.md), "Force powers' presentation") | 10 s |
| Do Burst of Speed's VFX_DUR_SPEED (code 1601) turn the speed blur on, and a fizzle and a resisted power show their flashes (1201, 1202)? | `python kotor/tools/py/force_run.py --powers 8 --dist 12 --cast-at 500 --post '64 mouse click 1113 688' --frames 112 --shots $(seq -s, 90 111) --log combat,trace --exe EXE` (each frame a picture, so the blur eases in): the log says `vfx speed blur record on ... blur true` and `kotor/out/frc/pw_8_105.png` is blurred toward the edges; `--powers 9 --target g_sithtroop01 --dist 6 --level 1 --wis 8 --cha 8 --shots 70,78 --log combat,trace`: the trooper saves, the log has `vfx v_fresist_imp` and `vfx v_fizzle_imp`, the pictures a burst on the trooper and a glow at the leader's hand ([design/vfx.md](design/vfx.md)) | 20 s |
| Do the GUI 3D scenes' emitters start 10 s along (the main menu's mist in its first picture)? | `kotor/tools/ctxc run kotor/tools/gui3dview -- --at 0 --size 800x600`: `kotor/out/gui/menu3d_0.png` shows the low mist across the floor at t = 0 ([re/gui3d.md](re/gui3d.md)) | 5 s |
| Do the GUI's borders look even at this window size and GUI scale? | `python kotor/tools/py/gui_scales.py OUT.png EXE [BASE_EXE] 1440x1080:1.5 3840x2160:0 ...` (two buttons per size, a base build beside it) | seconds |
| Is Windows' pointer hidden over the game's real window, through mode switches, minimise and focus moves? | `python kotor/tools/py/pointer_probe.py EXE SETTINGS INPUT SECONDS` with `FRAME gfx mode ...` lines in INPUT (Windows, a real window) | 10 s |
| Does an item, a skill or a panel work when clicked like a player does? | `sh kotor/tools/items/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...` with `ui clickctl TAG [ROW]` / `ui movectl` in the script ([mechanics/items-skills.md](mechanics/items-skills.md)); `sh kotor/tools/items/check.sh` runs them all. run.sh draws nothing (`--no-render`), so a picture of a 3D view (the upgrade bench's turning item, logged as `upgrade bench: item view MODEL on HOOK`) needs the executable run by hand, e.g. `EXE --module ebo_m12aa --speed 8 --frames 300 --input kotor/tools/items/scripts/bench_saber.txt --screenshot-at 165:PNG` | seconds |
| Does the inventory allow one item a round in combat after being attacked, and does a weapon change in the equipment screen cost the creature 1.5 s? | `one_item_round3.txt` is in `kotor/tools/items/check.sh` (a HUD medpac, then two inventory clicks: the second gets the 42409 box, found by `ui ctl LB_MESSAGE ~one_item_per_round`); `ALL=1 EXE=... sh kotor/tools/items/run.sh equip_combat bunk kotor/tools/items/scripts/equip_combat.txt 140` logs `equip: ID spends 1.5 s of its round on slot 4` ([mechanics/items-skills.md](mechanics/items-skills.md)) | seconds |
| Do the key bindings come from the options file, and does the remapping screen work (a click waits for a key, the key is taken from rows sharing an input class, Accept writes `[Keymapping]`, Default restores)? | `EXE=... sh kotor/tools/ingame/keymap.sh` (the `cantina` checkpoint, `--settings` of a file of its own; pictures of the screen in `kotor/out/keymap/`), FAIL and exit 1 per step. A hidden run without `--settings` always has the default keys, whatever `kotor/out/kotor-settings.ini` binds, so input scripts keep working ([mechanics/controls.md](mechanics/controls.md)) | 15 s |
| Does the X key flourish the leader's weapon? | `EXE=... LOG=combat,trace PAT='flourish|g2w1' sh kotor/tools/combat/run.sh uppercity flourish1 160`: one `flourishes its weapon (stance 2, still)` and the `g2w1` animation for the long sword, nothing for the rifle ([mechanics/controls.md](mechanics/controls.md)) | seconds |
| Does a target clicked while the game is auto-paused stay (the auto-target's timers stop while paused)? | `EXE=... sh kotor/tools/autotarget/paused_click.sh` (the `bunk` checkpoint, no bot: the Endar Spire's end_cut2_sith1 made hostile, the leader jumped in front of end_door10_cut2 and walking by the keys until it comes into sight and the game auto-pauses, then `ui clickon` clicks the Sith's box on the screen): PASS when the Sith is still the target 2.9 s into the pause, exit 2 when the set-up drifted ([mechanics/controls.md](mechanics/controls.md)) | 10 s |
| Does the reticle and target block follow a walking player (the nearest thing in front, no click), and do hover, click and Q / E work? | `sh kotor/tools/autotarget/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...` with `keydown w` / `mouse` lines in the scripts of `kotor/tools/autotarget/scripts/`; the log has one `target: OLD -> NEW (m, degrees)` line per change ([mechanics/controls.md](mechanics/controls.md)) | seconds |
| Does stealth (the toggle, G, the solo-mode box, hiding past enemies) work as a player meets it? | `sh kotor/tools/stealth/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...` with the scripts in `kotor/tools/stealth/scripts/`; `ui stealth [TAG]` prints the state ([mechanics/stealth.md](mechanics/stealth.md)) | seconds |
| Do the companions fight (Trask in the Endar Spire's room 3 and before the bridge, Carth in the Upper City), and does a line of sight block one who should? | `sh kotor/tools/combat/companions.sh`, FAIL and exit 1 when a party member made no attack in its fight; `ui los TAG TAG` / `ui losaudit` say what blocks a line; every run ends with `party attack rounds:` and a `companion idle:` line (below) | about a minute |
| Does a container's lid open before its loot panel and close after it, and does an emptied one stay open (after a load too) and stay silent, and does the panel come up as soon as the (double-speed) lid is open? | `sh kotor/tools/containers/locker.sh` (the Endar Spire footlocker from a new game, `--log objects,sound`: `placeable ID TAG plays close2open then open` lines from lib/scene/visual.ctx and the `sound play pl_footlkr_*` lines; `placeable ID TAG opens its inventory` when the panel comes up), FAIL and exit 1 when the sequence differs or the panel waits outside 0.2 to 0.5 s ([re/actions.md](re/actions.md) 3.5, [mechanics/items-skills.md](mechanics/items-skills.md) 4) | 5 s |
| Do creatures that die in a cut scene or a conversation stay down (the Endar Spire's room 3 and room 5 scenes, the Taris raid), and do the area's latest three bodies stay after their objects go (five troopers killed in Upper City, `corpses2.txt`)? | `sh kotor/tools/combat/corpses.sh`, FAIL and exit 1 when a dead creature's trace line shows an animation but a die or dead one ([re/dialogue.md](re/dialogue.md) 8.1); `--screenshot-range` with `cam duel TAGA TAGB` on the bodies shows it | 20 s |
| Does an order to fight put the leader in combat mode at once (the combat bar, Disengage, the attack's icon in the queue), paused after an enemy is sighted and far from it; do key 1, F and R queue, disengage and re-engage; does the bar stay up on the walk and go after the kill; do the combat message bar ("COMBAT MODE engaged", "Closing to attack range." for 2.5 s) and the pause banner ("Action added to queue.") say what the original's would? | `sh kotor/tools/combat/engage.sh` (from `uppercity`, the input `kotor/tools/combat/engage1.txt`), FAIL and exit 1 when a control's visibility, the leader's combat mode or a message is not what the original's would be at each step (`--log combat` prints `combat message: STRREF`, `--log objects` `pause banner: STRREF`); `ui fight` prints `combat_mode` and `bar` beside the server's `in_combat` ([re/movement.md](re/movement.md) 2.1 "Combat mode") | 5 s |
| Is a target that died kept 1.5 s in combat mode (the HUD target and the leader's combat mode), with another foe about? | `sh kotor/tools/combat/keep.sh` (from `uppercity`, the input `kotor/tools/combat/keep1.txt`), FAIL and exit 1 unless the target leaves the corpse 1.3 to 2.2 s after the death and combat mode lasts as long ([re/movement.md](re/movement.md) 7.1) | 4 s |
| Does a melee hit on a creature behind an energy shield sound the weapon's `forcefield` column? | `sh kotor/tools/combat/hitsound.sh` (from `uppercity`, the input `kotor/tools/combat/shield1.txt`: `ui shield` puts a forceshields.2da row 1 shield on a Sith trooper the leader attacks), FAIL and exit 1 unless every hit of the leader's plays a `cb_ht_*frce*` sound ([re/actions.md](re/actions.md) 3.15) | 4 s |
| Does the leader's clicked target (`+0x510`) keep an old foe unpaired while the leader goes for another, and does a self slot used in combat mode during an auto-pause turn the banner to "Action added to queue." and wait behind the queued attack? | `sh kotor/tools/combat/clicked.sh` (from `uppercity`, the inputs `clicked1.txt` and `selfq1.txt`), FAIL and exit 1 unless the refusal (`not paired ... clicked target`) is logged and the banner 48423 follows the slot's click with the use (15) queued behind the attack (12) ([re/combat.md](re/combat.md) `+0x510`, [re/gui.md](re/gui.md) UseSelfAction) | 10 s |
| Do the tutorial pop-ups show once each with their pages and icon, pause the game, and give the order that offered them when they close (pause 6, hostile sighting 21, attack 34, second attack within 3 s 35; none again after a save and load), and do the other call sites offer theirs (the menu key 7, the abilities menu 36, an equipment slot 11, the scripts 10, the map 13 and its party selection 41, a target slot's arrow 5, a party member falling 15, the level-up's skills 17)? | `EXE=... sh kotor/tools/ingame/tutorials.sh` (from `uppercity`, the inputs `kotor/tools/ingame/scripts/tutorials.txt` and `tutorials2.txt`, `ui tutorial on/allow/reset`; `--log objects` prints `tutorial offered/shown/closed`), FAIL and exit 1 unless 6 21 34 35 are shown once each and the attack's box leaves an attack in the queue, and the second run shows 7 36 11 10 13 41 21 5 15 17 in turn; pictures `kotor/out/tut/pause.png`, `attack1.png`, `attack2.png`, `menukey.png`, `falls.png`, `levelup.png`. Character generation's (16, 17, 18): the `tutorials` run of `kotor/tools/chargentest/selftest.sh` (`chargentest --tutorials`; pictures `kotor/out/chargen/menu_t_*.png`) ([re/gui.md](re/gui.md) "Tutorial pop-ups") | 40 s |
| Does party selection pick, put back, refuse and apply as the original (the map's screen applies Done and Cancel at once; a script's screen asks 38329 / 38328 before applying, refuses Escape and Back with 42405, and applies with both places forced)? | From the `uppercity` checkpoint, `EXE --load kotor/out/checkpoints/uppercity --headless --saves DIR --frames 48 --input kotor/tools/ingame/scripts/partysel.txt` (then `partysel2.txt`, `partysel3.txt`, `partysel4.txt`; `ui psel F1 F2` opens a script's screen, `lib/ingame/test_map.ctx`): the `party` lines each script's header expects (partysel: Player, Carth, slot 0's companion; partysel2: Player, Canderous twice; partysel3: Player, Carth; partysel4: Player, Carth, Canderous twice), and pictures of the boxes by `--screenshot-at` (partysel4: 11 the 42405 box, 16 the 38329 box, 26 the 38328 box) ([re/gui.md](re/gui.md) "CSWGuiPartySelection") | 10 s |
| Does the target block keep the hostile actions (attack, powers, grenades) off a party member, and does a thrown grenade fly and land after its flight? | `sh kotor/tools/combat/grenade.sh` (from `uppercity`, the input `kotor/tools/combat/gren1.txt`), FAIL and exit 1 when Carth's block lists anything, the trooper's lacks the grenade, or the trooper is hit at another tick than the release plus the `throws ... lands in N ms` flight; then plays it again with `kotor/tools/combat/gren_save.txt` (a `save` 10 ticks after the release and a `load` of it) and fails when the grenade never lands after the load; last `kotor/tools/combat/gren2.txt`, Carth as a grenadier (AI style 4) with two troopers engaging, fails unless he throws one on his own, its path has its four legs with the bounce points on the troopers' floor (`--log combat` prints `grenade path: N legs, ground Z1 Z2 Z3, target z Z`) and it hurts them when its flight is up ([re/gui.md](re/gui.md) "What the target block offers, by target", [re/render-gui.md](re/render-gui.md) "Spell projectiles"). For pictures of the throw run `gren1.txt` with `--screenshot-range 52:114:DIR` (no `--speed`) | 8 s |
| Do the combat feats (special attacks) work: each rank of Critical Strike, Flurry, Power Attack, Sniper Shot, Rapid Shot and Power Blast, used from the target block, with their attack count, animation, to-hit, damage bonus, threat range, defense penalty and stun, for each weapon style? | `sh kotor/tools/combat/feats.sh [CASE...]` (from `uppercity`; inputs and logs in `kotor/out/combat/feats/`; `ui slotpick 0 FEAT` picks the feat as the slot's arrows do, `ui giveitem RESREF 1 left` arms the left hand; `SHOTS="FRAME..."` takes pictures mid-swing), FAIL and exit 1 on any round that differs from [re/combat.md](re/combat.md) 4.5; the `--log combat` line `attack N: ... feat F threat T special S bonus B stun TRIED SAVE` and `feat F on ID: defense -P for 3 s` carry what it checks | 15 s |
| Does a click on a foe, R and the block's slots queue attacks as the original does (four waiting at most, the bar's four icons, Disengage, replace out of combat mode)? | `sh kotor/tools/combat/queue.sh` (`kotor/tools/combat/queue1.txt` from `uppercity`; `ui fight` prints `waiting N icons M`), FAIL and exit 1 per step that differs ([re/actions.md](re/actions.md) 3.13 "The player's attack orders and the queue") | 5 s |
| Do the leader and the party followers walk and run at the right gait and cycle rate, and do their feet keep up with the ground? | `EXE=kotor/out/kotor_gait.exe sh kotor/tools/gait/run.sh NAME CHECKPOINT SCRIPT FRAMES [--screenshot-range FROM:TO:DIR]` with the keys of `kotor/tools/gait/scripts/` (`--log gait`: one `gait` line per walking creature per frame: speed, rate, place, the leader's speed and distance), then `python kotor/tools/py/gait_check.py kotor/out/gait/NAME.log FROM TO STEP TAG...` tabulates it; `gait_cam.py` adds a camera that follows one creature to a script for the pictures ([re/movement.md](re/movement.md) 3.6 and 6.2) | seconds |

## The game headless, fast

`kotor.exe` takes the same input script (`--input FILE`, commands in [playthrough.md](playthrough.md)) in every mode
([engine.md](design/engine.md), "Headless and logs").

| Flags | What it does | Same log as `--headless`? |
|---|---|---|
| `--headless` | hidden window, fixed 1/30 s step, seeded rng; draws every frame | (the reference) |
| `--no-render` | the whole loop, but draws only on a screenshot or a save | yes, byte for byte; 2x faster |
| `--no-render --speed 8` | the scene sync, camera, UI and mixer step once per 8 ticks (at once when a conversation or menu needs them) | yes, except the `sounds started` count and a heap-bytes figure; 3x faster |
| `--no-render --speed 8 --mute` | also leaves music and effects out of the mixer | no: a voice-over mixed alone ends up to 2 ticks sooner; 6x faster. For smoke runs, not for replays whose clicks are timed |
| `--headless --sound-device` | also opens the sound device (with `SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=OUT.raw` it writes what the speakers would get, at their pace, and plays nothing) and holds every pass to the 1/30 s step, so sounds start at the pace they play; `--log sound` names stolen and refused voices, underruns with the frame time behind them, and sums up the mixer at the end | the story yes, but each pass takes at least 33 ms of wall time |
| `--engine-only` | lib/engine's loop alone: no scene, no conversation view, no input script | n/a: the quickest way to run scripts |

A hidden run (`--headless`, `--no-render`) does not show the story's films and credits, and ends where a window would go back to the main menu (EndGame,
the party's fall, Exit Game); its log says what was asked (`movie NAME (not shown: hidden run)`). `--cinema` makes it show them: each film is decoded
with its sound into the mixer at the run's fixed step (`movie NAME start/end` lines with the pictures shown and dropped), `--screenshot-at` frames count
through a film or the credits, a scripted `key escape` or `mouse click` skips one as a person's Escape or click does, the credits run to the length of
credits.wav, and the main menu comes up after an EndGame (a `newgame` line then starts the next session). The input script also has `FRAME movie NAME...`
and `FRAME credits` to show one on its own.

Use `--no-render --speed 8` for anything you would run `--headless` for, unless you are looking at the pictures
(then `--screenshot-at` still draws that frame). `FAST=1` does it in `run.sh`. Things that bite:

- `--screenshot-range FROM:TO:DIR` writes every frame from FROM to TO as `DIR/fNNNNN.png` (with `--no-render` those frames
  are drawn, the others are not; `--size 480x270` keeps them small, but not under 640 wide when the window is real). For
  finding a flash between two cuts: `python kotor/tools/py/framediff.py DIR [THRESHOLD]` lists the frame steps whose picture
  changes by more than the threshold and marks a frame that differs from two equal neighbours (BLIP) or a few
  (FLASH); `kotor/tools/py/contact_sheet.py OUT.png FRAMES...` lays frames out to look at.
- `--screenshot-loading DIR` writes every frame of the loading screen as `DIR/lNNNNN.png` (the stages of the load, then
  one per tick behind it); `--no-render` draws the screen only for this. Menu clicks in the input script work in the
  front end too (`mouse click 725 353` on a 1280x720 window is New Game).
- Standard output is written in 64 KB blocks: a log that looks stuck is usually a run still going. To see how far a
  run got, give it fewer `--frames` (or `--screenshot-at`) instead of killing it and reading the file.
- Processes that run at the same time need a `--saves DIR` each (`SAVES=` in `run.sh`): the game in progress is a file there.
- A run that hangs in `world::tick` is a loop in the engine: `--frames N` bisects the tick it happens in, a
  `--log actions,scripts,events` run to the tick before it says what was going on.

## Checkpoints

`sh kotor/tools/checkpoints/make.sh` replays the Endar Spire (a minute) and writes saves where the story passes
`bunk`, `bridge`, `pod`, `apartment`, `uppercity` and `cantina` to `kotor/out/checkpoints/NAME/`, each with
`NAME.txt`, the rest of the replay counted from the load (the reply queue, the bot's cheats and its remaining route
are restored). To test something at the cantina:

```
kotor/out/kotor.exe --load kotor/out/checkpoints/cantina --no-render --speed 8 --saves kotor/out/pt/saves_mine \
  --input my_test.txt --frames 3000 --screenshot-at 2900:kotor/out/pt/cantina.png --log dialog
```

`sh kotor/tools/checkpoints/chain.sh` goes on from `sithbase` with the story scripts (`40_` to `50_`, [playthrough.md](playthrough.md)):
`vulkar`, `garage`, `kandon`, `swoop`, `apt`, `cand`, `t3`, `codes`, `davik`, each with no resume script (the script that
starts from it is the next `NN_`). `my_test.txt` counts its frames from the load (frame 1 is the first tick). To go on with the story instead, give the
resume script: `FAST=1 LOAD=kotor/out/checkpoints/apartment SAVES=kotor/out/pt/saves_x sh kotor/tools/playthrough/run.sh
upper kotor/out/checkpoints/apartment.txt 30000`. Make them again after the engine's timing changes (they are
saves of this build; the frames in `make.sh` are the replay's).

## The smoke test

`sh kotor/tools/smoke/run.sh [-j JOBS] [MODULE...]` starts every module straight in, with the player, Carth and
Bastila, a bot in god mode that tours the area (walks to its waypoints, opens its doors, uses its placeables, walks
into its triggers, talks to whoever has something to say, fights what is hostile) and runs it for 10 minutes of world time. One
process per core, the logs in `kotor/out/smoke/`, the table in [smoke.md](smoke.md), worst first: crashes and
timeouts, VM faults, script faults, load errors, missing routines, stuck actions, missing textures, frame time.
With module names it runs those and writes `kotor/out/smoke/smoke.md`. `-r` rebuilds the table from the last run's logs.
`FRAMES=` changes the length. A hang shows as a timeout in 180 s: bisect it as above. To see one module's story:
`kotor.exe --module M --no-render --speed 8 --mute --input kotor/tools/smoke/input.txt --report routines --log scripts`.

A run prints the loop pass time by tenth of its length (`frame tenths (ms each): ...`, for `--frames` of 1000 or more), and the
table bolds a module whose last tenth is over twice its first (and over 0.1 ms). The frame time of a healthy module is flat, so a
rising one is something piling up per tick: a creature that cannot move and plans afresh every frame, a list that only grows.
Find out which by timing `ai::update` per object (a stuck mover tops that list) before suspecting a global list; in the case
that prompted the check `w.objects`, the event queue, the outbox and the heap's live bytes were all flat. Stuck movers pile up
and then level off (a few creatures get stuck, not all), so a flat tail proves nothing; and a module also warms up as the bot
reaches its fights, so some runs are flagged that are not leaking (`kas_m25aa` and `unk_m41ac` go from 0.3 to 0.8 ms in the first
quarter of the run and stay there; `kas_m25aa` without the bot is flat at 0.2 ms). Look at what the slowest objects and the
loop's sections cost, not only at the curve.

## Companions in a fight

A companion who watches a fight is a bug the leader's own fights never show: the leader attacks by orders, the companions only by
their AI (k_ai_master, joined by the leader's shout or by seeing an enemy), and anything between a script's `ClearAllActions` and
its next order can keep one out. Three checks, from cheapest:

- **Every run ends with the party's attack rounds**: `party attack rounds: player 122, carth 3` (the party at the end of the
  run, counted by NPC slot so a module change that makes the companions again keeps the count), and for each member who made
  none while the rest made 10 or more since it joined, `companion idle: carth made no attack round while the rest of the party
  made 128 since it joined`. The replays, the smoke test and any `--log`-less run print it; grep for `companion idle`. A leader
  that fights alone in a log that has that line is the case to look at.
- **`sh kotor/tools/combat/companions.sh`** (checkpoints made by `kotor/tools/checkpoints/make.sh`; about a minute) plays
  these fights and prints `ok` or `FAIL` for each:
  `room3` (from `bunk`, the bot leads: Trask must make an attack round before frame 3,000: the cut scene's `k_pend_cut1_end`
  clears his queue, orders him about 2 frames later and to attack 3 s on; a FOLLOWLEADER queued in between, which never ends,
  kept him in the corridor from the day the line of sight stopped letting him "see" the Sith through the walls);
  `bridge` (the same run, the bot off at frame 4,500, before the reinforcements: Trask must attack them in 4,500-6,500; the
  bot's leader would kill them in a few rounds on its own, and how soon depends on the run's dice: with the bot off at 7,690 the
  reinforcements were already dead in the run after the followers' gait change, and once Trask fought the fights in between
  they came at 5,111 instead of 7,131, so the bot-off frame moved from 6,900); `shout` (the same run: Trask must attack in
  2,000-4,500, the bot's fights between room 3 and the bridge, where nothing orders him and the Sith shoot at the leader, so
  only the leader's `GEN_I_WAS_ATTACKED` brings him in; he made none there while he heard no shout, because the party table
  made him without running his OnSpawn, which sets the listen patterns: mechanics/combat.md, QA reports); `joined` (the same
  fights from New Game, frames 6,000-8,400: a checkpoint carries the Trask of the build that made it, listen patterns and
  all, so only a run from New Game checks the Trask that the selection screen makes); `carth` (from `uppercity`, `retarget1.txt`: three troopers 4 to 5 m
  ahead, Carth must attack in 900 frames); `provoke` (from `uppercity`, `provoke1.txt`, not a companion: a dark Jedi turned
  hostile with a buff on itself as its first order must go for its enemy when the buff is cast, as the Star Forge's dark Sith
  after `k_psta_sithhosti` must). A FAIL means a companion made no attack where the original's does; read
  `kotor/out/combat/companions_NAME.log` (`--log combat`), then `ui los` / `ui losaudit` below.
- **`ui los TAG1 TAG2`** prints whether the first object has a clear line to the second (`perception::clear_line`, the line
  perception, the AI's target choice and a ranged attack use), and what stops it: `blocked by room N face F material M at X m` or
  `blocked by the mesh of TAG (closed)`. **`ui losaudit [METRES]`** does it for every companion against every living hostile
  within METRES (12): distance, clear, perceived, and the blocker. A companion 5 m from an enemy with a clear line that has not
  perceived it is a lag of the perception pass; one with a blocker that is not a wall or a closed door is a line of sight that
  stops too much.
- **A companion who hears nothing**: with `--log events,scripts`, each `script k_hen_attacked01 self=LEADER` (the leader shot
  at) should be followed by `event 7 to ID` and `script k_hen_dialogue01 self=ID` for every member that listens. None at all
  for a member means no listen patterns: its OnSpawn (`script k_hen_spawn01 self=ID`, or its own spawn script) never ran
  after the party table made it.

When the engine's timing changes (the checkpoints are rebuilt, the frames shift) the windows of `companions.sh` may need to move:
the replay is `kotor/tools/playthrough/10_endar_spire.txt`, whose reply queue (`4 ui replies ...`) assumes the conversations that
the story has: Trask's talk after the room 3 fight (`k_pend_room3_01`, "I've got a feeling that won't be our last battle with the
Sith") only comes when the player is hurt, and with Trask fighting the player no longer is, so the queue lost one `1`.

## The conversation sweep

`sh kotor/tools/dlgsweep/run.sh` (or `kotor/tools/ctxc run kotor/tools/dlgsweep -- --module M [--dlg NAME]` for one
module or one dialogue) walks every DLG of the install in a freshly entered module with the object that names it as
the owner, and writes [dlgsweep.md](dlgsweep.md): faults, routines nothing implements, scripts the install lacks,
speakers not found, dialogues that do not load. It does not play a conversation (no voice, camera or panels); that
is what the replay and `talk` in an input script are for. Use it after changing a routine that scripts call, the
VM, or `lib/dialog/core`.

## Conversation shots

`sh kotor/tools/camcheck/run.sh` (`EXE=PATH` for another executable; about 20 s) takes pictures of 17 conversation
shots and fails, with a `FAIL` line each and exit 1, when one is mostly black or empty: Trask's first talk on the
Endar Spire (close-ups and a shoulder shot), the wake-up cuts and framed shots of the talk with Carth in the Taris
apartment (`tar02_carth022`, frames 32,700 to 34,100 of the replay), Bastila's shots at the landing court on
Dantooine and the Council's static cameras (part 1 of the Dantooine playthrough). It plays the Endar Spire replay and
the Dantooine part 1 headless and fast in parallel, with `--screenshot-at` at a frame in the middle of a line each,
and `python kotor/tools/py/frame_check.py PNG...` measures each picture over its middle (rows 18% to 82%, columns 5%
to 95%, outside the letterbox bars and the subtitle): the mean luminance (fail under 10 of 255), the share of pixels of
luminance 6 or more (fail under 0.5) and the contrast (fail under 6). The Taris black screen measured mean 7.2 and lit
0.12 (the check fails three of its shots on the build that had the bug: the wide shots and the shoulder shot); the
darkest healthy picture, the wake-up cut from the bed, mean 13.8 and lit 0.80. The pictures are
`kotor/out/pt/cc_es_*.png` and `cc_dan_*.png`, the logs `cc_es.log` and `cc_dan.log`; each shot has a
`dialog camera:` line in them (mode, angle, eye, where it looks, the room under it, and the speaker's and listener's
eye points it was built from): an eye hundreds of metres from the participants, or one of the eye points at the area's
origin (0, 0), is the first thing to look for when a picture is black. A camera that goes through a wall or stands
outside the rooms is not a black frame, so look at the pictures too (Read them). The frames are those of the replay at
this build: when a conversation's timing moves they shift, and a frame that falls in a fade or between two lines needs
moving. Run it after changing the dialogue view (`lib/dialog/view`), the camera (`lib/scene/camera.ctx`), the scene's
visibility or the animation of a cutscene's actors.

`sh kotor/tools/camcheck/computer.sh` (`EXE=PATH`; about 10 s) plays the Endar Spire's security terminal from
`--module end_m01ab` (`kotor/tools/items/scripts/computer_camera.txt`: view the starboard transport module, then
overload the power conduit) and fails when the camera view does not show the 3D picture blue-grey under the security
camera's video effect (the left eighth of `kotor/out/items/cc_view.png`, black beside the computer panel), when the log
lacks `dialog video effect 0` for the Carth call and the three camera nodes, or when the message log lacks the plot XP's
"Experience Points (XP) Received: 100" (docs/re/dialogue.md 9.6, 9.7, 4.8). Run it after changing the computer panel,
the video effects or the XP feedback.

`sh kotor/tools/camcheck/summary.sh` (`EXE=PATH`; about 20 s) plays the same terminal twice
(`kotor/tools/items/scripts/status_summary.txt`) and fails when, with the option on, the status summary panel does
not come up after the conversation with the 120 XP and the used-up spikes (`status summary: flags 9 credits 0 xp 120`
in the `scripts` log) or its OK cannot be clicked, or when, with `ui summary off`, anything but the HUD's icons comes
of it (docs/re/gui.md "CSWGuiStatusSummary"). Headless runs never stop for the panel unless a script says
`ui summary panel`. Pictures: `kotor/out/items/sum_panel.png`, `sum_after.png`, `sumoff_icons.png`. Run it after
changing the status summary, the routines that give or take items, credits, XP or alignment, or the HUD's icons.

## Adding a check

A new subsystem gets a corpus tool that runs it over every resource of its type (AGENTS.md rule 6). A new input-script
command: see below, then its row in the table in [playthrough.md](playthrough.md). A new report
line for the smoke test starts with a word its `report.sh` can match (`stuck`, `fault:`); keep it out of the default log.

## Adding a scripted command

A script line is `FRAME WORD ARGS...`, kept as `play::Scripted { frame, word, rest }`: the word and the rest of the
line as text. Nothing central lists the words (no enum, no parser chain). Each owner file has one function that is
asked in turn and answers whether the word was its own:

```
// in your file: its namespace may be new; the fields besides word and rest are what your commands need
fn handle_scripted { mut w: world::World, word: []u8, rest: []u8 } -> bool {
    if ci::eq{ a = word, b = "mycmd" } {
        let tag = text::first_word{ s = rest }                       // or text::words/next_word, text::rest, text::scan_*
        ...
    } else if ci::eq{ a = word, b = "other" } { ... }
    else { return false }
    return true
}
```

The one place to add the call is the `let handled = ... or ...` chain in `play::run` (`game/play.ctx`, "One call per
owner"): add `or yourns::handle_scripted{ &w, word = s.word, rest = s.rest } or` as a line of its own (the order does
not matter; on a merge conflict there, keep both lines). Pass what you need from `run`'s locals by `&local`. More words for an owner
that has a function (play's keys and moves, `mg_game` minigames, `handle_scripted_vfx` cam/fx, `ingame` `ui`) go in that function. A
new `ui` subcommand needs no call: add a branch to `ingame::run_command` (`lib/ingame/script.ctx`). A word no owner
takes stops the run with `kotor: input script: no command 'WORD' in the line '...'` (exit 1).

## Known runaways in the original's own scripts

These run out of the VM's instruction budget in the original game too (same 131,072-instruction
limit, VM error -93), so the smoke and sweep tables list them but they are not our bugs:

- `k_ai_master` ("Commoner AI", reached from `k_def_endconv` after `tar02_drunk021`,
  `tar02_preraid`, `tar02_bountyh022`, `tar02_scaredm021`, and in the smoke row of `tar_m02ad`):
  its loop over `GetNearestCreature(REPUTATION, NEUTRAL, self, n)` only advances `n` for creatures
  outside the hostile standard factions, so a Hostile_1 creature over 20 m away keeps it spinning.
- `k_ptat_tuskenmad` (`tat_m20aa`): `GetFirstObjectInArea` with an empty `while` body and no
  `GetNext`.

And one faithful load failure: `end_carth001` is named by `end_m01aa`'s copy of `p_carth001` but
ships only in `end_m01ab_s.rim`.
