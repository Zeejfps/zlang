# Playthrough log: the game played headless, step by step

What happens when the game is played from New Game, checked with logs and screenshots against what the
original does. Each step says whether it works, what fixed it (commit), or who has it. The input scripts
are in `kotor/tools/playthrough/`; replay any of them to see the step again.

Planets after Taris have their own logs: [playthrough-dantooine.md](playthrough-dantooine.md) (the arrival, the Council, the trials, Juhani, the ruins and the Star Map). [playthrough-tatooine.md](playthrough-tatooine.md) (the docks to the Krayt hunt, the Star Map, Calo Nord, Czerka's reward, and the Ebon Hawk's galaxy map to Kashyyyk). [playthrough-kashyyyk.md](playthrough-kashyyyk.md) (the Czerka pad to the Star Map in the Shadowlands, Chuundar's hall and the duel on Freyyr's side, the way out to the Hawk). [playthrough-korriban.md](playthrough-korriban.md) (Dreshdae, the Sith Academy under Uthar Wynn and Yuthura Ban, the tombs, Naga Sadow's Star Map and the Leviathan).

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
| `FRAME use TAG`, `attack TAG`, `warp TAG [party]`, `warpxy X,Y [party]` (`party`: the followers stand beside the leader), `talk RESREF [TAG]`, `hush` | the leader's default action on an object, attack, test teleports, start a conversation, end it |
| `FRAME ui replies 1 2 ~hunting_licenses...` | queues conversation replies (256 at most): each list that opens takes the next entry, a number (1 is the first reply) or `~words` (underscores are spaces: the first reply whose text contains them, ignoring case; the first reply, with a log line, if none does). Words survive a change of the player's state that a number does not (a new reply appears when the player has the credits); the queue outlives conversations |
| `FRAME key NAME`, `keydown NAME`, `keyup NAME` (`down`/`up`), `mouse move X Y`, `mouse down|up|click [left|right] [X Y]`, `mouse wheel DY` (also `ui click X Y`, `ui move X Y`, `ui key NAME`, `ui type TEXT`) | the keyboard and mouse as the player has them: each is an SDL event put on SDL's own queue (`game/inject.ctx`) and read back by the loop with every other event, so it goes through the conversation panels, the HUD and menus and then the world's keys (the panel is 640x480 centred in the 1280x720 window). NAME: a letter or digit, up down left right space tab escape return backspace f1..f12 ctrl shift caps |
| `FRAME ui menu NAME`, `close` | open or close a menu directly (not the key) |
| `FRAME ui target TAG` then `ui key 1` | select an object and run the first action of the target block (the game picks a target itself every frame, [controls.md](mechanics/controls.md); this one holds while it stays in view) |
| `FRAME ui los TAG TAG` | whether the first object has a clear line to the second (`perception::clear_line`, the server's, and `is_sight_clear`, the client's), whether it perceives it, and whether the leader may target it |
| `FRAME ui goto TAG`, `where [PART]` (with each object's facing), `pos` (with the leader's facing), `party`, `inv`, `locals TAG` | walk the leader to an object; print objects by tag part, the leader's place and health, the party, the bag, an object's local variables |
| `FRAME ui bot route STOP... / tour / on / off / god / unlock / status` | the test player (`lib/ingame/bot.ctx`): fights what is hostile in sight, walks the route of stops (`TAG`, `TAG#N` the Nth object of that tag, `@TAG` talk to it, `X,Y` a place on the floor), opens its doors; a stop that is a transition trigger is done when the area changes; `god` keeps the leader at 1 hit point, `unlock` opens locked doors on the route; `tour` makes the route from the area itself (waypoints, triggers, doors, placeables, talkers: `bot_tour.ctx`, what the smoke test uses). Never on in a real game. |
| `FRAME cam duel TAGA TAGB [DIST]`, `cam at X,Y,Z X,Y,Z`, `cam off` | the camera at the side of two objects (`pc` for the player) or at a point, for pictures of a fight |
| `FRAME fx visual ROW TAG`, `fx at ROW X,Y,Z`, `fx model MODEL TAG [HOOK]`, `fx cast SPELL TAG` | plays a visualeffects.2da row, an effect model or a power's cast visuals on the spot (docs/design/vfx.md); `--log trace` lists what fights and effects do |
| `FRAME save NAME`, `load FOLDER` | saves go to `kotor/out/saves/00000N - GameK`; `load 000002 - Game1` |
| `FRAME ui giveitem RESREF [N] [equip]`, `unlock TAG`, `global NAME N`, `autolevel`, `ui clickctl TAG ~some_words` (the list row with those words) | cheats for tests (not used by the real-flow scripts): `autolevel` takes every level the leader's XP allows (the bot never spends XP; the story's fights need a level 7 player) |
| `FRAME hoveron TAG [N]` (or `hoveron =NAME`: by the name the HUD shows, for objects without a tag such as "Remains") | the pointer moves onto a point of the object that the HUD's pick gives to it; `mouse click` a frame later selects it, a second click runs its default action (the leader walks up, talks, opens): a player's click on a creature, door, container or the ramp. `use TAG` skips the walk and starts where the leader stands |
| `FRAME ui globals PART`, `ui journal list` | the number and boolean globals whose name has PART and are not zero; every journal quest with its entry (the state of the story) |
| `FRAME racer`, `gunner` | the swoop racer bot (shifts, steers between the obstacles, takes the pads) and the turret's gunner bot play the minigame (`lib/minigame/racer.ctx`); they make the same `Input` the keys do |
| `FRAME ui bot route TAG#N`, `bot tour off` | a route stop may name the Nth object of a tag (the Lower City has two `tar04_elevdoor`); a route takes over from a tour with `tour off` |

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
| 46 | The swoop race from the `swoop` checkpoint (`tar_m03af`, the party left outside by `k_ptar_03af_en`, as in the original): the announcer by a click on him (the first click selects, the second walks the leader up and talks), the lights, the heats ridden by the racer bot (`racer`: 26.7 s against the 38.4 s to beat; the first win counts double, so the second heat is the third win), the mechanic's talk after each heat, the finale (`tar03_brejik031`: Brejik refuses Bastila, she breaks the cage), the fight (Redros, Brejik and guards; Bastila fights beside the player; the player needs `ui autolevel`: XP is not spent by the bot, a level 1 soldier cannot hurt Brejik), journal `tar_bastsearch` 60/99, Bastila's conversation `tar03_bastila` | works | `46_race.txt` |
| 47 | Bastila never joined: `k_ptar_bastpart` puts her in NPC slot 0, which still held the Endar Spire's Trask (AVAILNPC0), so the apartment got Trask and the Carth and Bastila reunion (`tar02_carbast`, started by AssignCommand to the object tagged "bastila") never began | fixed f06c5b1 (the AddAvailableNPC routines forget the slot's old file); with it: the reunion, `tar02_bastvision`, the party screen (clicks on the portraits add and remove; the right panel's 3D model is not drawn: open) | `46_race.txt`, `47_canderous.txt` |
| 48 | The Rodian messenger (`tar02_messenger`, journal `tar_escape` 10), the Lower City cantina, Canderous (`tar03_cand031`: a trigger starts it with Canderous 7 m away; journal `tar_escape` 20, `tar_buydroid` 50), Janice Nall in the Upper City North (the T3-M4 droid: "I can't afford that", then the Persuade reply gets it free, `tar_buydroid` 99), the party screen (T3-M4 and Carth) | works | `47_canderous.txt`, `48_t3.txt` |
| 49 | The Sith base `tar_m09aa`: the door in the Upper City North, troopers, turrets and droids fought by the party in god mode (the doors unlocked by the bot's cheat, T3-M4's skill and the terminals not played), the elevator to `tar_m09ab`, the Dark Jedi (`tar09_darkjedi91`, 148 hit points, killed by Carth), his remains (opened with clicks: `hoveron =Remains`) hold the Taris Launch Codes: journal `tar_escape` 25; the strongboxes hold 500 credits and armour and spikes | works | `49_sithbase.txt` |
| 50 | Back to Canderous with the codes (`tar03_cand031` again: reply 2 "let's join up"), `[CANDEROUS has joined your party.]`, `k_ptar_davikest` opens the party screen with Canderous forced: it opened with Canderous, Carth and T3-M4 selected for two places, the party table refused the third and Canderous stayed out, so Davik's conversation lost its "Cand" speaker and ended after two lines | fixed 3b948f5 (the forced one is picked first); Malak's scene `m40ab_c01` (stunt_03a) then `tar_m08aa` | `50_codes.txt` |
| 51 | Davik's estate: the tour (the party is moved to the hangar and the guest rooms while the conversation goes on). Davik's guards are hostile by their template; they fell on Carth in the middle of the conversation and Carth killed the guest wing's guards | fixed 991c32c: FreezeHostiles (re/dialogue.md 4.9) was not built; an ordinary conversation now stops its hostiles | `50_codes.txt` |
| 52 | The estate: Hudrow's conversation gives the codes (`tar_escape` 50), the terminal (use access card / "Disable hangar security", free with the codes, `k_ptar_openhang`), the hangar door (locked, DC 100: only the terminal opens it), Davik and Calo Nord (`tar08_davik082`, the Sith bombing; Calo's grenade dialogue never ended: a hit in flight ran his OnAttacked and the AI's ClearAllActions took the queued resume), the ramp (`tar08_ramp`: `tar_escape` 99, `tar_planetinfo` 99) | works; the Calo hang fixed in 991c32c (ClearAllActions keeps a paused conversation's resume) | `51_davik.txt` |
| 53 | The escape: Malak's scene `stunt_06`, `stunt_07` (the Hawk over Taris), the turret `m12ab` (the gunner bot clears the six fighters in 16 s), `ebo_m12aa` (Bastila's vision `ebo_bast_vision`), the landing on Dantooine (`danm13`: Bastila's conversation, Carth and Bastila walk to the Council). Leaving the turret's area wiped the kept party (a minigame's area spawns none, `keep_party` saved an empty one) | fixed fbf0799; `k_pebn_pophawk` destroys the NPC objects present on the Hawk and spawns every available one at its waypoint, and `k_pdan_13_load` takes Bastila and Carth out of the party at Dantooine: the player arrives alone, as the scripts say | `51_davik.txt` |


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

## Taris after the swoop race: checkpoints and how to play on

`sh kotor/tools/checkpoints/make.sh` makes the checkpoints up to `sithbase`; `sh kotor/tools/checkpoints/chain.sh` (about
10 minutes) plays the story scripts from there and keeps `vulkar`, `garage`, `kandon`, `swoop` (40, 43, 44, 45), `apt`
(46: Bastila and Carth reunited), `cand` (47: Canderous's offer), `t3` (48: the droid bought, T3-M4 and Carth in the
party), `codes` (49: the launch codes in the bag) and `davik` (50: Davik's tour over, the guest wing fought). Each of
`46_race.txt` to `51_davik.txt` starts from the checkpoint before it; the header of each says the command. Things a
script has to know: the reply queue is consumed only by lists with a choice (a line that continues takes none), so set
`ui replies` just before the conversation it is meant for; the lines of a script must be in frame order (a later line
with an earlier frame waits for the lines before it); the camera of Calo Nord's last conversation is a low tilted shot
(the data's, not a bug that was found).

## The Taris chain after the merges (what broke, and how to resume)

The story was played from the swoop race to the Dantooine landing (steps 46-53 above) with the engine of commit 6036766.
After merging `kotor` at 75e8167 `chain.sh` stopped at `cand`: the bot walked to the Lower City cantina but Canderous's
conversation (`tar03_cand031`) never started. It was not a game bug and not one of the Dantooine, Tatooine or Kashyyyk
fixes: the bot's change to stand "in the middle of a trigger" (86bd1ef) took the mean of the polygon's corners, and
`tar02_candtlk` is an L-shaped strip about a metre wide whose mean lies outside it, so the bot finished its route beside the
trigger and the OnEnter never ran (a player crossing the strip starts the talk; the old bot walked to the trigger's origin,
which is one of its corners). The bot now stands on a point that is inside the polygon (`bot::polygon_middle`) and counts a
trigger stop done only when the leader is inside it; `ui where TAG` prints a trigger's corners to check such a thing.

State of the chain with the merged engine: `vulkar`, `garage`, `kandon`, `swoop`, `apt`, `cand`, `t3`, `codes` and `davik`
are all good (`chain.sh` checks the module and, for `cand`, `t3`, `codes` and `davik`, a companion that must be in the party:
Bastila, T3-M4, T3-M4, Canderous). Each of `46_race.txt` to `51_davik.txt` starts from the checkpoint before it; the header of
each says the command. What each needed after the merges: `48_t3.txt`'s party screen opens with Bastila and Carth selected:
click Carth `598 271` and T3-M4 `507 447`, then OK; the click frames follow the end of Janice's conversation (5346 in the
last run, clicks at 5790), so if `t3` comes out with the wrong party, move them. `49_sithbase.txt`: the party needs about
15,500 frames to reach the Dark Jedi and 17,800 to kill him, so the remains are tried every 1500 frames from 19000 (the bot
stays on) and the run is 30,000 frames; `savewhen tar_m09ab codes tar_escape 25` saves when the codes are in the bag.
`50_codes.txt` saves `davik` with `savewhen tar_m08aa davik tar_escape 40`. `51_davik.txt` (from `davik`, to the Dantooine
landing) was not played again after the merges. The dice and the timing of the fights move the frames of these scripts
whenever the engine changes; `savewhen MODULE NAME [QUEST ENTRY]` (play.ctx) saves when the story is quiet in MODULE (no conversation, transition or loading for 2 s, and the leader out of combat) and the
journal quest has reached ENTRY, so a checkpoint does not depend on a frame. The Sith base camp's rancor (`tar05_stampy`, 90
hit points) is only killed by the party when `40_sithbase.txt` lowers its hit points (`ui sethp tar05_stampy 8`): the level 7
player and the companions hit it once in 2,000 frames.

## Open items (not blocking)

- The party screen's right panel (the 3D model of the highlighted companion) is empty.
- The player arrives on Dantooine alone, as in the original: `k_pdan_13_load` removes Bastila and Carth from the party
  and spawns them at the landing (`dan13_wp_bast_halk`, `dan13_wp_carth_halk`), and `k_pdan_bastila11` walks them to
  the Council.
- The Sith base was played with the bot's door cheat and a god-mode party: T3-M4's use on the doors and the terminals'
  turret, droid and gas options (`tar09_aacompdlg`), the Sith uniform route and the base's gas rooms are not played.
- The estate's guards stay hostile and the guest wing's fight starts when the tour's conversation ends (the guards hear
  the party at 20 m); the original's mechanism (if guests are safe in their rooms) is not known.

- `end_carth001` and the other cutscene dialogues end "aborted" when the next module starts from their own
  script (`cut00_convers`). Harmless so far; the original runs the end script before the change.
- The Sith soldiers' armour renders as mirror-like chrome; the original's is dark grey with a faint
  sheen (the envmap strength; render/models item).
- The minimap of the bridge area shows only the arrow on black (its map texture does not cover y > 140?).
- The yellow arrow over the leader's portrait after the Security tutorial: looks like the switch-leader
  hint; check against the original.
- Dialogue reply texts begin with the tutorial's "[Left-click this answer...]" line as the data has it.
- The bot cannot do a conversation-driven quest chain on its own (it walks, fights and opens doors; a story step that needs a particular reply needs its own `ui replies` line, as Mission's and Canderous's do). The story is played with it from New Game to the Dantooine landing; the optional Taris quests (the duel ring, the bounties, the outcasts' Promised Land, the Sith party) and the Sith uniform route are not.
- Wide dialogue shots (angle 3) for a speaker and listener 9 m apart look down at the floor; that is the RE'd formula (camera 0.3 d up, target 0.2 d down), kept. In the Undercity base the listener of Zaalbar's lines is the invisible placeable that owns the door talk, so every such shot is of that kind.
- 0 to 3 textures per module are missing (the count is in the `scene:` line; the names are not logged: a `--log` word that lists them would say which).
- The test player of `--module X` runs has a dead second companion slot in some modules (a red cross on the HUD); `god on` now keeps a real party alive.

## Known and benign

- Scripts that run out of instructions: at the end of a conversation in the Upper City, 14 creatures' `k_def_endconv` -> `k_ai_master` hit the VM's 131,072-instruction budget (`fault: k_ai_master ... the instruction budget ran out`). The loop in `k_ai_master` ("Commoner AI": nearest enemy by reputation, `GetStandardFaction` hostile, `GetDistanceBetween <= 20`) never advances when the nearest enemy is farther than 20 m; the original has the same budget (vm.md) and the same script, so this is BioWare's bug and the original aborts the script the same way. Counted in the run's "faults".
- The conversation reply queue holds 128 numbers; `ui replies default N` answers every list after it.
