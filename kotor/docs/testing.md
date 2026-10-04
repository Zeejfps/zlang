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
| Does the story still play from here to there? | the playthrough replay, from a checkpoint if it can start in the middle ([playthrough.md](playthrough.md)) | 30 s for the Endar Spire, 1-2 min to the Undercity from the apartment |
| Does it look right? | a screenshot (`--screenshot-at FRAME:PNG`), read with the Read tool | one run |
| Does an item, a skill or a panel work when clicked like a player does? | `sh kotor/tools/items/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...` with `ui clickctl TAG [ROW]` / `ui movectl` in the script ([mechanics/items-skills.md](mechanics/items-skills.md)) | seconds |
| Does stealth (the toggle, G, the solo-mode box, hiding past enemies) work as a player meets it? | `sh kotor/tools/stealth/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...` with the scripts in `kotor/tools/stealth/scripts/`; `ui stealth [TAG]` prints the state ([mechanics/stealth.md](mechanics/stealth.md)) | seconds |

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

`my_test.txt` counts its frames from the load (frame 1 is the first tick). To go on with the story instead, give the
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
