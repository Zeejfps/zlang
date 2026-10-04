# Testing: which tool for which question

Every check starts from the same executable (`kotor/tools/ctxc exe kotor -o kotor/out/kotor.exe`) or one of the
tools under `kotor/tools/`. Pick the cheapest tool that can answer; the table says which that is. Times are for
the 24-core development machine.

| Question | Tool | Time |
|---|---|---|
| Does this parser read every resource of its type? | the corpus tool for the format (`dlgcheck`, `fmtcheck`, `texcheck`, `mdlcheck`, `walkcheck`, ...) | seconds to a minute |
| Does a script, routine or the VM do the right thing in a module? | `kotor.exe --engine-only --module M --frames N --log routines --report routines`, or `tools/enginetest` | well under a second |
| Does any module fault, hang, crash or lack a routine, with a party that walks it? | the module smoke test, `sh kotor/tools/smoke/run.sh` → [smoke.md](smoke.md) | 4 minutes for all 117 |
| Does every conversation's graph and scripts run? | the conversation sweep, `sh kotor/tools/dlgsweep/run.sh` → [dlgsweep.md](dlgsweep.md) | 45 s for all 1,262 |
| Does the story still play from here to there? | the playthrough replay, from a checkpoint if it can start in the middle ([playthrough.md](playthrough.md)) | 30 s for the Endar Spire, 1-2 min to the Undercity from the apartment; Dantooine (`sh kotor/tools/playthrough/dantooine/all.sh`, [playthrough-dantooine.md](playthrough-dantooine.md)) 8 min |
| Does it look right? | a screenshot (`--screenshot-at FRAME:PNG`), read with the Read tool | one run |
| Does a graphics option, a window size or the GUI scale work? | `FRAME gfx KEY VALUE` input lines (`--gfx --settings FILE` to read an options file headless), `sh kotor/tools/gfx/sizes.sh EXE` for four scenes at five sizes, the scripts in `kotor/tools/gfx/scripts/` ([mechanics/graphics.md](mechanics/graphics.md)) | seconds |
| Do the GUI's borders look even at this window size and GUI scale? | `python kotor/tools/py/gui_scales.py OUT.png EXE [BASE_EXE] 1440x1080:1.5 3840x2160:0 ...` (two buttons per size, a base build beside it) | seconds |
| Is Windows' pointer hidden over the game's real window, through mode switches, minimise and focus moves? | `python kotor/tools/py/pointer_probe.py EXE SETTINGS INPUT SECONDS` with `FRAME gfx mode ...` lines in INPUT (Windows, a real window) | 10 s |
| Does an item, a skill or a panel work when clicked like a player does? | `sh kotor/tools/items/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...` with `ui clickctl TAG [ROW]` / `ui movectl` in the script ([mechanics/items-skills.md](mechanics/items-skills.md)) | seconds |
| Does the reticle and target block follow a walking player (the nearest thing in front, no click), and do hover, click and Q / E work? | `sh kotor/tools/autotarget/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...` with `keydown w` / `mouse` lines in the scripts of `kotor/tools/autotarget/scripts/`; the log has one `target: OLD -> NEW (m, degrees)` line per change ([mechanics/controls.md](mechanics/controls.md)) | seconds |
| Does stealth (the toggle, G, the solo-mode box, hiding past enemies) work as a player meets it? | `sh kotor/tools/stealth/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...` with the scripts in `kotor/tools/stealth/scripts/`; `ui stealth [TAG]` prints the state ([mechanics/stealth.md](mechanics/stealth.md)) | seconds |
| Do the companions fight (Trask in the Endar Spire's room 3 and before the bridge, Carth in the Upper City), and does a line of sight block one who should? | `sh kotor/tools/combat/companions.sh`, FAIL and exit 1 when a party member made no attack in its fight; `ui los TAG TAG` / `ui losaudit` say what blocks a line; every run ends with `party attack rounds:` and a `companion idle:` line (below) | about a minute |

## The game headless, fast

`kotor.exe` takes the same input script (`--input FILE`, commands in [playthrough.md](playthrough.md)) in every mode
([engine.md](design/engine.md), "Headless and logs").

| Flags | What it does | Same log as `--headless`? |
|---|---|---|
| `--headless` | hidden window, fixed 1/30 s step, seeded rng; draws every frame | (the reference) |
| `--no-render` | the whole loop, but draws only on a screenshot or a save | yes, byte for byte; 2x faster |
| `--no-render --speed 8` | the scene sync, camera, UI and mixer step once per 8 ticks (at once when a conversation or menu needs them) | yes, except the `sounds started` count and a heap-bytes figure; 3x faster |
| `--no-render --speed 8 --mute` | also leaves music and effects out of the mixer | no: a voice-over mixed alone ends up to 2 ticks sooner; 6x faster. For smoke runs, not for replays whose clicks are timed |
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
- **`sh kotor/tools/combat/companions.sh`** (checkpoints made by `kotor/tools/checkpoints/make.sh`; about a minute) plays three
  fights and prints `ok` or `FAIL` for each:
  `room3` (from `bunk`, the bot leads: Trask must make an attack round before frame 3,000: the cut scene's `k_pend_cut1_end`
  clears his queue, orders him about 2 frames later and to attack 3 s on; a FOLLOWLEADER queued in between, which never ends,
  kept him in the corridor from the day the line of sight stopped letting him "see" the Sith through the walls);
  `bridge` (the same run, the bot off at frame 7,690: Trask must attack the reinforcements before the bridge in 7,600-8,500; the
  bot's leader would kill them in a few rounds on its own); `carth` (from `uppercity`, `retarget1.txt`: three troopers 4 to 5 m
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
