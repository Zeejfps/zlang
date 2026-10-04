# Playthrough log: the game played headless, step by step

What happens when the game is played from New Game, checked with logs and screenshots against what the
original does. Each step says whether it works, what fixed it (commit), or who has it. The input scripts
are in `kotor/tools/playthrough/`; replay any of them to see the step again.

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
uppercity and cantina, each with `NAME.txt`, the rest of the replay counted from the load):

```
FAST=1 LOAD=kotor/out/checkpoints/apartment SAVES=kotor/out/pt/saves_x sh kotor/tools/playthrough/run.sh upper kotor/out/checkpoints/apartment.txt 30000
```

The input script knows (play.ctx, lib/ingame/script.ctx, lib/dialog/view/view_notes.ctx):

| Line | Does |
|---|---|
| `FRAME newgame [FILE]` | New Game from the front end (a created player's UTC from FILE, else the default soldier) |
| `FRAME ui replies 1 2 1...` | queues conversation replies: each list that opens takes the next number (1 is the first reply); the queue outlives conversations |
| `FRAME use TAG`, `attack TAG`, `warp TAG`, `warpxy X,Y`, `talk RESREF [TAG]`, `hush` | the leader's default action on an object, attack, test teleports, start a conversation, end it |
| `FRAME ui click X Y`, `move X Y`, `key NAME`, `menu NAME`, `close` | the pointer and keys as the player has them (the panel is 640x480 centred in the 1280x720 window) |
| `FRAME ui target TAG` then `ui key 1` | select an object and run the first action of the target block |
| `FRAME ui goto TAG`, `where [PART]` (with each object's facing), `pos` (with the leader's facing), `party`, `inv`, `locals TAG` | walk the leader to an object; print objects by tag part, the leader's place and health, the party, the bag, an object's local variables |
| `FRAME cam duel TAGA TAGB [DIST]`, `cam at X,Y,Z X,Y,Z`, `cam off` | the camera at the side of two objects (`pc` for the player) or at a point, for pictures of a fight |
| `FRAME fx visual ROW TAG`, `fx at ROW X,Y,Z`, `fx model MODEL TAG [HOOK]`, `fx cast SPELL TAG` | plays a visualeffects.2da row, an effect model or a power's cast visuals on the spot (docs/design/vfx.md); `--log trace` lists what fights and effects do |
| `FRAME ui bot route TAG... / on / off / god / unlock / status` | the test player (`lib/ingame/bot.ctx`): fights what is hostile in sight, walks the route of tagged stops, opens its doors; `god` keeps the leader at 1 hit point, `unlock` opens locked doors on the route. Never on in a real game. |
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
| 10 | The locked bridge door: Trask's Security tutorial, the target block offers Security first on a locked door, OPENLOCK walks up, kneels 1.5 s, rolls, opens | fixed 8fee1c6 (target block) + engine (OPENLOCK) | `10_endar_spire.txt` |
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
| 30 | Every Taris module loads headless with 0 script faults (`smoke.sh tar_m02aa ... tar_m11ab`) | works | `smoke.sh` |
| 31 | Trask's entry: after the dream cutscene he opens the bunk room door himself, runs in and stops 1 m from the player, facing him, before "We've been ambushed..." (the user found him speaking through the closed door: `GetObjectByTag("")` is the player, k_pend_traskdl40) | engine (7ab46dc); checked by `13_trask_entry.txt` + `kotor/tools/py/check_trask_entry.py` | `13_trask_entry.txt` |
| 32 | Staging audit of every conversation of the route (`dialog stage:` log lines per line, `kotor/tools/py/stage_audit.py LOG`): who stands how far from whom, in which rooms; remote comm conversations (Carth) and cutscene scene objects are far by design | works (nothing else far or behind walls in the ordinary conversations) | `10_endar_spire.txt` with LOG=dialog |
| 33 | The fights are seen: room 3 (soldier and Sith with blasters), room 5, the Jedi duel. Bolts fly from the weapon's `bullethook` and a miss flies on to the wall, muzzle flashes, impact sparks, lit lightsabers with clashes and sparks, swing/shot/hit sounds, grunts and death cries; ranged damage lands when the bolt arrives (the user: "I didn't see any combat" past the locked door) | fixed (lib/vfx, docs/design/vfx.md); checked with `--log trace`, `cam duel` and `fx` test input | `10_endar_spire.txt` (replay: 0 faults, tar_m02af) |

The whole Endar Spire plays from New Game to the Taris apartment with `10_endar_spire.txt` (34000 frames,
about 5 minutes of wall time), with 0 script faults.

## Open items (not blocking)

- `end_carth001` and the other cutscene dialogues end "aborted" when the next module starts from their own
  script (`cut00_convers`). Harmless so far; the original runs the end script before the change.
- The Sith soldiers' armour renders as mirror-like chrome; the original's is dark grey with a faint
  sheen (the envmap strength; render/models item).
- The minimap of the bridge area shows only the arrow on black (its map texture does not cover y > 140?).
- The yellow arrow over the leader's portrait after the Security tutorial: looks like the switch-leader
  hint; check against the original.
- Dialogue reply texts begin with the tutorial's "[Left-click this answer...]" line as the data has it.
