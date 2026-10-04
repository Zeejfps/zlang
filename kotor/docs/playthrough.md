# Playthrough log: the game played headless, step by step

What happens when the game is played from New Game, checked with logs and screenshots against what the
original does. Each step says whether it works, what fixed it (commit), or who has it. The input scripts
are in `kotor/tools/playthrough/`; replay any of them to see the step again.

Planets after Taris have their own logs: [playthrough-dantooine.md](playthrough-dantooine.md) (the arrival, the Council, the trials, Juhani, the ruins and the Star Map); [playthrough-kashyyyk.md](playthrough-kashyyyk.md) (the Czerka pad to the Star Map in the Shadowlands).

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor.exe
sh kotor/tools/playthrough/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]...       # log in kotor/out/pt/NAME.log, pictures NAME_SHOT.png
LOG=dialog,combat,routines sh kotor/tools/playthrough/run.sh ...           # the log lists (engine.md "Headless and logs")
sh kotor/tools/playthrough/story.sh kotor/out/pt/NAME.log [FROM_FRAME]     # the story-relevant lines of a log
```

`run.sh` stops a hung run after `TIMEOUT` seconds (default 240); `frames.sh SCRIPT N...` says which frame
counts hang. A script's lines must be in frame order.

`FAST=1 sh kotor/tools/playthrough/run.sh ...` plays with `--no-render --speed 8` (same log, a third of the time:
the 34,000-frame Endar Spire takes 30 s, not 98 s). To start in the middle, load a checkpoint made from this replay
(`sh kotor/tools/checkpoints/make.sh` writes `kotor/out/checkpoints/NAME/` for bunk, bridge, pod, apartment,
uppercity, cantina, lowercity, undercity, mission, gate and sithbase, each with `NAME.txt`, the rest of the replay counted from the load):

```
FAST=1 LOAD=kotor/out/checkpoints/apartment SAVES=kotor/out/pt/saves_x sh kotor/tools/playthrough/run.sh upper kotor/out/checkpoints/apartment.txt 30000
```

The input script knows (play.ctx, lib/ingame/script.ctx, lib/dialog/view/view_notes.ctx):

| Line | Does |
|---|---|
| `FRAME newgame [FILE]` | New Game from the front end (a created player's UTC from FILE, else the default soldier) |
| `FRAME ui replies 1 2 1...` | queues conversation replies: each list that opens takes the next number (1 is the first reply); the queue outlives conversations |
| `FRAME use TAG`, `attack TAG`, `warp TAG [party]`, `warpxy X,Y [party]` (`party`: the followers stand beside the leader), `talk RESREF [TAG]`, `hush` | the leader's default action on an object, attack, test teleports, start a conversation, end it |
| `FRAME key NAME`, `keydown NAME`, `keyup NAME` (`down`/`up`), `mouse move X Y`, `mouse down|up|click [left|right] [X Y]`, `mouse wheel DY` (also `ui click X Y`, `ui move X Y`, `ui key NAME`, `ui type TEXT`) | the keyboard and mouse as the player has them: each is an SDL event put on SDL's own queue (`game/inject.ctx`) and read back by the loop with every other event, so it goes through the conversation panels, the HUD and menus and then the world's keys (the panel is 640x480 centred in the 1280x720 window). NAME: a letter or digit, up down left right space tab escape return backspace f1..f12 ctrl shift caps |
| `FRAME ui menu NAME`, `close` | open or close a menu directly (not the key) |
| `FRAME ui target TAG` then `ui key 1` | select an object and run the first action of the target block |
| `FRAME ui goto TAG`, `where [PART]` (with each object's facing), `pos` (with the leader's facing), `party`, `inv`, `locals TAG` | walk the leader to an object; print objects by tag part, the leader's place and health, the party, the bag, an object's local variables |
| `FRAME ui bot route TAG... / tour / on / off / god / unlock / status` | the test player (`lib/ingame/bot.ctx`): fights what is hostile in sight, walks the route of tagged stops, opens its doors; `god` keeps the leader at 1 hit point, `unlock` opens locked doors on the route; `tour` makes the route from the area itself (waypoints, triggers, doors, placeables, talkers: `bot_tour.ctx`, what the smoke test uses). Never on in a real game. |
| `FRAME cam duel TAGA TAGB [DIST]`, `cam at X,Y,Z X,Y,Z`, `cam off` | the camera at the side of two objects (`pc` for the player) or at a point, for pictures of a fight |
| `FRAME fx visual ROW TAG`, `fx at ROW X,Y,Z`, `fx model MODEL TAG [HOOK]`, `fx cast SPELL TAG` | plays a visualeffects.2da row, an effect model or a power's cast visuals on the spot (docs/design/vfx.md); `--log trace` lists what fights and effects do |
| `FRAME save NAME`, `load FOLDER` | saves go to `kotor/out/saves/00000N - GameK`; `load 000002 - Game1` |
| `FRAME ui giveitem RESREF [N] [equip]`, `unlock TAG`, `global NAME N` | cheats for tests (not used by the real-flow scripts) |

Helper scripts: `dump.sh MODULE NAME EXT` (a resource as a GFF tree), `res.sh WORD [--module M --type EXT]` (the
install's resources by name part), `ncsgrep.sh MODULE` (every script of a module disassembled into
`kotor/out/ncs/NAME.txt`, so `grep -l ROUTINE kotor/out/ncs/*.txt` says who calls what).

## The steps

State: **works** (checked), **fixed** (a commit of this branch), **engine** (reported to and fixed by the
engine lead, merged), **open**.

| # | Step | State | Script |
|---|---|---|---|
| 1 | New Game: the front end, the default player, end_m01aa loads (15 rooms, 258 objects, music, HUD) | works | `01_start.txt` |
| 2 | Opening cutscene `m01aa_c01` (animated dialogue, cameras, Trask's entrance) then Trask's conversation `end_trask01` with replies, VO, subtitles, lip sync, the tutorial reply texts | works | `02_trask.txt` |
| 3 | The conversation's scripts: SetLocked on the first door, the hint timer (`k_pend_time01`), Trask's repeated hints while the player idles | works | `03_locker.txt` |
| 4 | The footlocker: walk up, the loot panel, taking an item fires OnInvDisturbed (`k_pend_chest02`: 50 plot XP, more gear appears), Get Items | engine (containers by the screens lead) | `03_locker.txt` |
| 5 | Equipment screen: clothing and short sword, damage and to-hit numbers | works | `03_locker.txt` |
| 6 | Trask asks to move out; `[TRASK has joined your party.]`; `ShowPartySelectionGUI` opens the party screen with Trask forced, OK spawns him next to the player, two portraits | fixed 497aaec (ingame side), engine (note, `bring_member`) | `03_locker.txt` |
| 7 | Door 1 opens for the party, Carth's comm message (trigger), journal entry "Attack on the Endar Spire" and its text in the journal screen | fixed 6a68036 (journal and plot XP of dialogue nodes: lib/dialog) | `10_endar_spire.txt` |
| 8 | Room 3: the Sith kill the Republic soldiers in a cutscene (Pause, CutsceneAttack, death-driven resume), then the fight; kill XP | engine (CutsceneAttack was a stub: it applied no hit, so the cutscene never ended) | `10_endar_spire.txt` |
| 9 | The long corridors: room 5 cutscene (soldiers and Sith kill each other), reinforcements, the Jedi duel cutscene `end_cut04`, combat with Trask beside the player, doors opened by the route | works | `10_endar_spire.txt` |
| 10 | The locked bridge door: Trask's Security tutorial, the target block offers Security first on a locked door, OPENLOCK walks up, kneels 1.5 s, rolls, opens | fixed 8fee1c6 (target block) + engine (OPENLOCK); the player's own path (click the icon, kneel, the roll line, keys, containers, the messages) was broken in several places and is fixed: see Lock picking below | `10_endar_spire.txt` |
| 11 | The bridge: Carth, dead crew, Taris through the viewport | works (minimap of the bridge area is black: see open items) | `10_endar_spire.txt` |
| 12 | Door 15 and 19: Trask holds off the Dark Jedi (`end_cut01`), the door to end_m01ab | works | `10_endar_spire.txt` |
| 13 | Module change to end_m01ab, Carth's comm `end_carth001`, Sith and assault droid, the pod room, journal and XP (1,975 at the pod) | works | `10_endar_spire.txt` |
| 14 | The escape pod: `end_pod` dialogue, `stunt_00` cutscene module, `cut00_convers`, module change to `tar_m02af` | works | `10_endar_spire.txt` |
| 15 | Taris apartment: Carth's conversation `tar02_carth022` ("Good to see you up...") | works (reached; see Taris below) | `10_endar_spire.txt` |
| 16 | Save and load with Trask in the party and a stocked bag: place, party, worn and carried items back | engine (a load dropped the bag's stacks: stale ids) | `12_saveload.txt` |
| 17 | Carth's conversation in the apartment (56 nodes; the wide shots frame the player on the bed once the stunt body returns to the creature's place), journal entry `tar_bastsearch` | fixed (dialogue cameras follow a stunt body only while a scene animation runs on it, 319006f) | `10_endar_spire.txt` |
| 18 | Leaving the apartment: `tar02_doordlg` ("you will have to take Carth"), the party screen with Carth forced, OK spawns him; module change to `tar_m02aa` (Upper City South: Sith troopers, civilians, shop droids) | works | `10_endar_spire.txt` |
| 19 | Larrim's conversation and shop: a store panel with buy list, prices, descriptions | works (the screens lead's panel) | `10_endar_spire.txt` |
| 20 | `tar_m02aa` to `tar_m02ac` (the exit door), Carth's "something seems to be bothering Carth" banter, the cantina door to `tar_m02ae` | works | `10_endar_spire.txt` |
| 21 | Arrival in the cantina: black screen (no fade-in after the door transition) | reported to engine (fade-in after a transition) | `10_endar_spire.txt` |
| 22 | The cantina on its own (`--module tar_m02ae`): the duel announcement conversation, the NPCs, the arena door | works | `20_cantina.txt` |
| 23 | A character made by chargentest (a female scoundrel) through the opening: head and body in the cutscene, footlocker contents by class (blaster pistol), 9 hit points, party screen | works | `11_created.txt` |
| 24 | A computer panel (`end_comp02` in end_m01ab): the computer skin, replies as terminal lines, `<CUSTOM32>` spike count substituted, the skill and spike counters | works | `--module end_m01ab`, `warp end_comp02`, `use end_comp02` |
| 25 | After the engine's fade-in fix: the cantina renders, the bot walks it with Carth; save (QUICKSAVE) and load in the cantina keep position, party and bag, and the picture fades in after the load | engine (fade-in after a transition or a load) | `10_endar_spire.txt` |
| 26 | Upper City: the bounty hunters fight (dialogue, Carth and the player kill both, the bullied merchant's conversation), journal: "Rapid Transit System", "The Search for Bastila" (end: investigate the Undercity) | works | `10_endar_spire.txt` |
| 27 | Upper City North (`tar_m02ab`): the Sith guard's conversation at the lower city door; Lower City (`tar_m03aa`): the Black Vulkar fight, Canderous's conversation `tar03_cand032`, a Sith patrol; the door to the Undercity | works | `10_endar_spire.txt` |
| 28 | The Undercity (`tar_m04aa`, 466 objects): arrival at the elevator, the outcast woman's gate conversation | works up to the panic below | `10_endar_spire.txt` |
| 29 | About 30 minutes in: `actions.ctx:102 panic: integer overflow` (a u16 action group wrapped by a polling script) | reported to engine | `10_endar_spire.txt` |
| 30 | Every module of the install (115: Endar Spire, Taris, Dantooine, Kashyyyk, Tatooine, Manaan, Korriban, Lehon, the Ebon Hawk, the Star Forge, the stunt cutscene modules) loads headless for 100 frames with 0 script faults, 0 missing routines and a picture (`smoke.sh MODULE...`, pictures `kotor/out/pt/smoke_MODULE.png`); the default player alone in a hostile module can die in seconds (`tar_m09aa`) | works | `smoke.sh` |
| 31 | Trask's entry: after the dream cutscene he opens the bunk room door himself, runs in and stops 1 m from the player, facing him, before "We've been ambushed..." (the user found him speaking through the closed door: `GetObjectByTag("")` is the player, k_pend_traskdl40) | engine (7ab46dc); checked by `13_trask_entry.txt` + `kotor/tools/py/check_trask_entry.py` | `13_trask_entry.txt` |
| 32 | Staging audit of every conversation of the route (`dialog stage:` log lines per line, `kotor/tools/py/stage_audit.py LOG`): who stands how far from whom, in which rooms; remote comm conversations (Carth) and cutscene scene objects are far by design | works (nothing else far or behind walls in the ordinary conversations) | `10_endar_spire.txt` with LOG=dialog |
| 33 | The fights are seen: room 3 (soldier and Sith with blasters), room 5, the Jedi duel. Bolts fly from the weapon's `bullethook` and a miss flies on to the wall, muzzle flashes, impact sparks, lit lightsabers with clashes and sparks, swing/shot/hit sounds, grunts and death cries; ranged damage lands when the bolt arrives (the user: "I didn't see any combat" past the locked door) | fixed (lib/vfx, docs/design/vfx.md); checked with `--log trace`, `cam duel` and `fx` test input | `10_endar_spire.txt` (replay: 0 faults, tar_m02af) |
| 34 | The test bot grew up: it opens the closed door that stalls a walk (8 decisions without getting a metre nearer; the lock first with `unlock on`), clicks an area-transition door once in two seconds (every click restarts the transition token, so a click every decision never let one finish) and passes the stop it took through a transition once the area changed (the door of the same tag on the other side sent it back), and `god` keeps every companion at 1 HP (a downed companion is a red cross on the HUD for the rest of the test) | works | `lib/ingame/bot.ctx` |
| 35 | Lower City to the Undercity (`tar03_underdoor`, `tar04_elevdoor`), the outcast woman, Mission (`tar04_mission`: she runs to the player, asks for Zaalbar; the reply queue `1 1 2 1 1 1` makes her join, `[MISSION has joined your party.]`, then the party screen, whose portrait slot showed Carth's face for Mission because it found the Undercity's placed Mission by tag: fixed, the panel uses the party table's creature, else the blueprint), the Republic soldier (`tar04_republicso`), the main gate to the Sith base `tar_m05aa` | works | `10_endar_spire.txt`, `42_mission.txt` |
| 36 | Sith base camp (`tar_m05aa`): Gamorrean guards, the cell door trigger. Mission and Zaalbar's "door talk" (`missdoor_dlg`, 54 nodes) is started by a script on a placeable with no OnDialog script, which got no conversation | engine (stock dialogue script for placeables and doors, fixed on the engine branch eb4cf75); with it: Mission examines the lock, Zaalbar answers from the cell, the door opens, `[ZAALBAR joined]`, the party screen offers him (a confirmation box asks "Are you sure..." when a free companion is left out) | `40_sithbase.txt` |
| 37 | Walking into a closed unlocked door never sent PATH_BLOCKED, so followers could not pass doors and the bot's moves hung | engine (d80cf7d on the engine branch); the bot's stall detector works around it | `40_sithbase.txt` |
| 38 | The force field to `tar_m05ab` (rakghouls, kath hounds, Gamorrean guards), the long walk to the elevator, `tar05_elevator` to the Vulkar base `tar_m10aa` (Vulkar thugs and droids fight in the bar, the surrendering Vulkar's conversation `tar10_vulksur2`), the elevator `tar10_elev02` to the garage `tar_m10ac` (swoop bikes, Kandon Ark) | works | `43_elevator.txt` |
| 39 | Every fight showed a bark box with the raw text "GEN_I_WAS_ATTACKED": `SpeakString` with a silent talk volume (3, 4) posted a bark | engine (fixed on the engine branch, with the listening side) | any fight |
| 40 | Davik's estate (`tar_m08aa`): the arrival conversation `tar08_davik081` (Davik, Calo), camera, fade-in | works (the staging is the cutscene's: Davik 4.6 m from the player) | `50_davik.txt` |
| 41 | Sweep of all 24 Taris modules (`sweep.sh`, one picture each after 400 frames): the Upper City, apartments, cantina, Lower City, Javyar's cantina (a Hutt), the swoop garage, the swoop minigame `tar_m03mg` (cockpit, timer, radar), the Undercity, the Sith base, the Vulkar base, the Beks base, Davik's estate | all load and render with 0 faults; 0-3 textures missing per module (names are not logged) | `sweep.sh` |
| 42 | An area-transition door that an NPC opened (the bullied merchant, through PATH_BLOCKED) was never taken by the leader again: `open_door` returned before CLICKED | engine (fixed on the engine branch 13cedce: the leader's click always runs the transition, and walking through an open one does); the bot shuts an open transition door before clicking it | `cantina` checkpoint |
| 43 | The Undercity door talk, Zaalbar, the force field, the elevator into the Vulkar base, its fights, the garage elevator: one chain from the sithbase checkpoint (`40_sithbase.txt`, `43_elevator.txt`), the party screens accepted by `ui bot party on` | works | `40_sithbase.txt`, `43_elevator.txt` |
| 44 | Kandon Ark in the garage (`tar10_kandon01`, 46 entries): the reply queue `2 2 3` refuses his offer, `k_ptar_karkatk` turns him and his guards hostile, the fight, the Swoop Accelerator is picked up from `tar10_accelerator` | works | `44_kandon.txt` |
| 45 | The Beks base (`tar_m11aa`) from the Lower City: Zaerdra's challenge, the assault droid that fights the Beks (the bot kills it first: left alone it kills Gadon, 8 hit points, during his conversation and the dialogue aborts), Gadon's conversation: with `Tar_GadonMission` set (`ui gbool`) the second visit takes the accelerator, `tar_bastsearch` entry 50, `k_ptar_bekrace` starts `tar_m03af`, the mechanic's conversation, `Tar_SwoopStatus` | works up to the race | `45_gadon.txt` |
| 46 | The race itself, Davik's estate beyond the arrival conversation, Bastila's cage and the Leviathan escape | not played: story QA was paused (the swoop checkpoint is in `kotor/out/checkpoints/swoop`, `tar_m03af` with the mechanic done: the trigger `tar03_racefirst` starts the race) | |


The whole Endar Spire plays from New Game to the Taris apartment with `10_endar_spire.txt` (34000 frames,
about 5 minutes of wall time), with 0 script faults. The whole route to the Sith base (`10_endar_spire.txt`, 80,000
frames, about 12 minutes with `FAST=1`) makes the checkpoints; each of `40_` to `50_` starts from one:

```
FAST=1 LOAD=kotor/out/checkpoints/sithbase SAVES=kotor/out/pt/saves_x sh kotor/tools/playthrough/run.sh sb kotor/tools/playthrough/40_sithbase.txt 30000
sh kotor/tools/playthrough/sweep.sh sweep.png tar_m02aa tar_m03aa ...     # a picture of each module, side by side
sh kotor/tools/playthrough/wheremod.sh mission                             # which modules hold an object, and where
```

`--module X` plus `warp TAG` and `ui global NAME N` is the way to test what needs no story state (the surrendering
Vulkar, Davik's hall, the elevator): seconds, not minutes.

## Lock picking by the player

Checked through the real input path (hover, click, the target block, the 1-2-3 and R keys) with scripted input and
the test commands `ui stat security N` (ranks), `ui relock TAG DC [KEYTAG|required]`, `ui locks [PART]`,
`ui target TAG` + `ui key 1`, `ui click X Y` on the block's icon (the block hangs over the door: about (600, 68) from
the Endar Spire door02 checkpoint). What was broken: the icon label took the click, so the block's Security slot did
nothing by mouse; the unlock animation was reset by the fighter one frame in (no kneel); a container's OpenLockDC,
KeyRequired and KeyName were never read (every locked container opened at DC 1); the failure and key messages were
sound-set placeholders ("Attack Grunt - not actual text to be translated"); keys did nothing; the block kept a stale
Security icon once the lock was open. Now: a Security character walks up, works the lock for 1.5 s with the lockpick
sound, the roll is on the feedback log ("Leia Tana attempts Security on Footlocker : *success* : (Take 20 + 5 = 25
vs. DC 8)", a d20 in combat), the door opens or the container shows its loot; a failed roll leaves it locked with the
roll as the only message; a key-only lock says so; a 0-rank character is not offered Security and hears "Locked";
a key in the bag opens the lock. The engine's own log line (`--log actions`) has the parts (ranks, key ability, feat,
roll, DC). Not modelled: the sound-set barks (unlock success and failure, "locked"), AutoRemoveKey, XP (the engine gives none;
scripts do), DoDoorAction's unlock is still instant.

## Open items (not blocking)

- `end_carth001` and the other cutscene dialogues end "aborted" when the next module starts from their own
  script (`cut00_convers`). Harmless so far; the original runs the end script before the change.
- The Sith soldiers' armour renders as mirror-like chrome; the original's is dark grey with a faint
  sheen (the envmap strength; render/models item).
- The minimap of the bridge area shows only the arrow on black (its map texture does not cover y > 140?).
- The yellow arrow over the leader's portrait after the Security tutorial: looks like the switch-leader
  hint; check against the original.
- Dialogue reply texts begin with the tutorial's "[Left-click this answer...]" line as the data has it.
- Not played through by the story (only loaded and looked at): the swoop race itself (`tar_m03mg` renders; its input is the minigame lead's), Davik's estate beyond the arrival conversation, Bastila's rescue and the Leviathan escape. The bot cannot yet do a conversation-driven quest chain (it walks, fights and opens doors; a story step that needs a particular reply needs its own `ui replies` line, as Mission's does).
- Wide dialogue shots (angle 3) for a speaker and listener 9 m apart look down at the floor; that is the RE'd formula (camera 0.3 d up, target 0.2 d down), kept. In the Undercity base the listener of Zaalbar's lines is the invisible placeable that owns the door talk, so every such shot is of that kind.
- 0 to 3 textures per module are missing (the count is in the `scene:` line; the names are not logged: a `--log` word that lists them would say which).
- The test player of `--module X` runs has a dead second companion slot in some modules (a red cross on the HUD); `god on` now keeps a real party alive.

## Known and benign

- Scripts that run out of instructions: at the end of a conversation in the Upper City, 14 creatures' `k_def_endconv` -> `k_ai_master` hit the VM's 131,072-instruction budget (`fault: k_ai_master ... the instruction budget ran out`). The loop in `k_ai_master` ("Commoner AI": nearest enemy by reputation, `GetStandardFaction` hostile, `GetDistanceBetween <= 20`) never advances when the nearest enemy is farther than 20 m; the original has the same budget (vm.md) and the same script, so this is BioWare's bug and the original aborts the script the same way. Counted in the run's "faults".
- The conversation reply queue holds 128 numbers; `ui replies default N` answers every list after it.
