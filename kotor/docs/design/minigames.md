# Minigames: pazaak, swoop racing, turrets

Pazaak is built and plays through (rules, the original's opponent, the three screens, the engine
hooks). Swoop racing and the turret sequences are surveyed and planned (the last section); nothing
of them is implemented. What the original does is in [re/pazaak.md](../re/pazaak.md) and
[re/minigames-swoop-turret.md](../re/minigames-swoop-turret.md).

| Directory | Namespace | What |
|---|---|---|
| `lib/pazaak/core/cards.ctx` | `pazaak` | card ids, values, texts and textures |
| `lib/pazaak/core/rules.ctx` | `pazaak` | `Game`, `Side`, the main deck, hands, tables, judging a set; the original's `rand()` |
| `lib/pazaak/core/ai.ctx` | `pazaak` | the opponent |
| `lib/pazaak/core/match.ctx` | `pazaak` | `Match`: the game panel's state machine without the panel |
| `lib/pazaak/core/data.ctx` | `pazaak` | the opponent's deck from `pazaakdecks.2da` |
| `lib/pazaak/ui/screens.ctx`, `game.ctx` | `pazaak` | `Session`: wager, side-deck and game screens over lib/gui |
| `lib/engine/routines/minigames.ctx` | `rt_mg` | `PlayPazaak`, `GetLastPazaakResult`, `take_card` |
| `game/pazaak.ctx` | `pz_game` | the loop's side: a visit to the table, the outcome into the party |
| `tools/pazaakplay` | | a visit headless from a script (or a bot), with PNGs; `--interactive` plays it |
| `tools/pazaaksim` | | thousands of AI-vs-AI matches; `--selftest` |

`lib/pazaak/core` needs `base res formats` only (the engine and the simulation take it alone);
`lib/pazaak` as a whole adds the GUI libraries (`tex material platform render render_gl audio gui`).

## Pazaak

### The rules library (`core`)

Cards are the original's ids (0..5 plus, 6..11 minus, 12..17 flip, 18..27 main-deck 1..10), so the
party table's counts, `pazaakdecks.2da`'s notation (`+3`, `-3`, `*3`) and the card items map onto them
directly. A `Card` is an id and a `flipped` flag; `card_value` gives what it adds.

```
let mut g = pazaak::new_game{ seed, wager }
pazaak::deal_hand{ rng = &g.rng, side = &g.player, deck = pazaak::deck_cards{ ids = side_deck } }   // 4 of the 10
pazaak::draw_card{ g = &g, who = pazaak::Who::player }          // main deck -> table; 20 or a ninth card stands
pazaak::play_hand_card{ s = &g.player, i } / flip_hand_card{ ... }
match pazaak::judge_set{ g = &g } { undecided | player | opponent | tie }
```

`Rng` is the C runtime's `rand()` (the original shuffles with `rand() % n`), seeded by the caller:
the same seed repeats a match. The AI is `pazaak::ai_step{ g, who }`, one step of the original's state
machine (docs/re/pazaak.md); it can play either side, which is how the simulation and `auto_player`
work.

`Match` is the panel's flow with the timers and messages but no screen: `step_match{ m, dt }`,
the player's choices `end_turn`, `stand_up`, `play_card`, `flip_card` (each returns whether it was
allowed), `forfeit_match`, and the outputs: `take_cue` (sounds to play: `mgs_*` plus the GUI click), and
a **prompt** (`has_prompt`, `prompt_text`, `answer_prompt`) that blocks the match until answered: the
set-result message, the tutorial's pages and its confirmations. `m.finished`, `m.won`, `m.forfeited`
at the end. With `auto_player` the AI plays the player's side too (headless games and tests).

### The session (`ui`)

```
var s = try pazaak::begin{ g = &gui, fs = &fs, dev = &dev, mixer, params, owned, side_deck }
each frame, while not s.done:   gui::handle_event ... ; try pazaak::update{ s = &s, g = &gui, fs = &fs, dev = &dev, dt }
pazaak::end_session{ s = &s, g = &gui }          // frees the sounds, closes the panels
s.result: { won, forfeited, wager, side_deck }
```

`Params` is what the script asked for plus names and a seed: `opponent_deck` (ten card ids,
`load_opponent_deck{ fs, heap, rm, row, seed }` reads the row, or a random one for a negative row),
`max_wager` (already clamped to the gold; 0 or less means no wager), `tutorial`, `seed`, the two
names. `owned` is the count of each card id the player has, `side_deck` the deck chosen last time.
A session shows, in this order: the side-deck screen (`pazaaksetup.gui`) with the wager question
(`pazaakwager.gui`) over it when there is a stake, then the game (`pazaakgame.gui`). All three are
the original's files over the `pazaak` backdrop; the code only sets their controls by tag
(docs/re/pazaak.md lists them). It owns no gold, items or scripts: the host applies `result`.
`update` polls and clears the GUI's events itself, so while a session is open nothing else may take
them; its panels are modal and full-screen (`gui::is_modal_open`).

Behaviour kept from the original: the wager starts at the maximum, +/-1 per click (held buttons
repeat: ours, 20 a second after 0.4 s); the side deck starts as last time if the cards are still owned;
Play asks "are you sure"; Escape asks to forfeit (before the game it costs nothing, in the game
it loses the wager); the opponent's hand is face down; the tutorial's pages and confirmations
appear only when the script asks for them.

### Engine and loop (what the hooks are)

- **Party** (`party::Party`): `pazaak_cards: [18]i32` (two each of ids 0..4 at the start),
  `pazaak_deck: [10]i32` (last side deck, -1 none, not saved), `pazaak_won: bool`.
- **`PlayPazaak`** (routine 364) posts `outbox::Note::pazaak{ deck, end_script, max_wager, tutorial,
  opponent }`. The wager limit is clamped as the original does (`gold <= limit` makes the gold the
  limit). **`GetLastPazaakResult`** (365) is `pazaak_won`.
- **The loop** (`game/play.ctx`, after the outbox is drained): `pz_game::visit` takes over the
  frame with a session over the in-game GUI (`ui.gui`) until it is done. `conclude` then adds or
  takes the wager from `party.gold` (not below 0), keeps the side deck if complete, sets
  `pazaak_won` and runs the end script with OBJECT_INVALID as owner, as the original does. Headless
  (`--headless`, `--no-render`) `visit_auto` lets the AI play both sides with the default deck, so
  a script that asks for pazaak completes in tests: `kotor --module end_m01aa --no-render --frames
  60 --run-script k_act_mispaz --log routines`.
- **Cards found**: `rt_mg::take_card{ w, base, variation, stack }`; an item of ItemType 42
  entering the party's inventory is counted at `(variation + 11) mod 18` instead of kept (the item
  code calls it where credits become gold).
- **Not done**: reading and writing `PT_PAZAAKCARDS` in the save (the engine's save library), the
  pazaak card items' icons in the inventory, stores that sell cards (`dan_pazaak`, UTM).

### The opponent

A faithful port of the original's decisions (`ai.ctx`, docs/re/pazaak.md): it draws, then plays a
hand card only to reach at least 18 under conditions on its table, ends its turn below 16-18,
stands from 18 (16 and 17 depending on its hand), gives up a busted set when the player is not
close to the match, and keeps flip cards. It reads only the totals, its hand and the player's sets;
the player's hand is never looked at. Decks: `pazaakdecks.2da` rows 1, 2 and 3 are used by the
game's 27 scripts (0 is the player's starter); a negative row is random.

`pazaaksim --games 10000` plays the four decks against each other, the AI on both sides. Win rates
of the first column's deck (as the player, who always moves first) against the row's: 42/32/27/22 %
for deck 0 (two each of +1..+5) against decks 0..3, 56/45/40/33 for deck 1, 59/48/44/37 for deck 2,
65/55/49/43 for deck 3 (the all-flip-card deck), about a third of sets tied, 6 sets and 40 turns
a match, the longest ~115 turns. The mirror matches favour the second player (42-45 %: it sees
whether the other has stood), the flip-card deck beats the starter deck 3 to 1 as the data says.
No match hung or broke a rule in over 160,000.

### Decisions

- **One match per visit**, no rematch, as the original's calls end the visit.
- **A hand card is played with one click** (the original wants a double-click or a drag; a click on
  the GUI's hover-focus model would be easy to misfire either way). The tutorial's confirmations
  guard low totals as the original's do.
- **The player always starts a set**, as in the original; ties score nothing.
- **A blocking visit** in the loop rather than a screen layered into the frame: the minigame
  takes the whole frame, the world is not ticked meanwhile, and a script's end script runs when it
  returns. The sound is the loop's mixer.
- **Hover-repeat of the wager buttons** and the plus-minus sign (byte 0xB1 of the fonts) are the only
  additions to the original's controls.
- **Headless runs let the AI play** the player's side: a deterministic pass for tests.

### Open

- Music during the game (the original switches the sound mode to 4; unexplored).
- The card hover highlight (`lbl_cardhilite`), dragging a hand card onto the table, key shortcuts.
- Saving the cards and a rematch screen if the real game turns out to have one.

## Swoop racing and the turret: the plan

The survey is [re/minigames-swoop-turret.md](../re/minigames-swoop-turret.md) (read it before
starting). The shape of what we found:

- Four areas carry an `ARE.MiniGame` struct: three swoop races (Taris `tar_m03mg`, Tatooine
  `tat_m17mg`, Manaan `manm26mg`) and the Ebon Hawk's gunner turret (`M12ab`). Story scripts enter
  them with `StartNewModule`; their own scripts leave (the race writes its time into globals; the
  turret can end the game when the Hawk is destroyed in the real sequence).
- Both are **on rails**. A track is an MDL whose `track` animation moves the node `modelhook`; the
  player's vehicle models hang on it and the player only steers a small offset (a lateral
  offset for the bike, two aim angles for the turret). Enemies (accelerator pads, Sith fighters)
  follow rails of their own. Everything else is scripts: 97 `SWMG_*` routines let the module's
  NWScripts run the gears, the timer, the HUD and the win condition. The engine does the rails,
  the steering integrator, collisions, bullets and the camera on node `camerahook`.
- The HUD is not a GUI: it is models attached to the camera (digits are one-frame animations).
- No new 2DA, no `.gui`; models, sounds and textures are in the BIFs. About 4,500 lines of ctxlang
  by the survey's estimate; the swoop slice (data, rail, steering, pads and obstacles, the routines)
  is 60% of it and playable alone.

### What the engine and renderer must give (hooks, in order of need)

1. **The area's minigame data.** `modload`/`read_are` should keep the `MiniGame` struct on the area
   (our proposal: `obj::Area.minigame: ?*mg::Area`, filled by `mg::read_are{ doc, s, ... }` from
   `lib/minigame`, which owns the struct and its LYT track/obstacle lists), and the module's
   party should not be spawned in such an area.
2. **A minigame step in the loop**, taking the frame between world step and render like pazaak's
   visit, but over several frames: `mg::update{ &m, &w, &vm, engine, input, dt }` and a scene for
   it; the world's clock keeps running (the scripts use `DelayCommand`, heartbeat and the time of
   day).
3. **Script routines** `SWMG_*` as a new category file (`rt_mg` already exists for pazaak and is
   the home): their arguments are minigame object ids (0..254), distinct from the world's, and
   `OBJECT_SELF` is the minigame object whose script runs.
4. **Render and scene needs** (listed by the survey): named animations with events, nodes by
   name and their world transforms each frame, models parented to nodes, an AABB query on a model,
   emitters in models, a camera that follows a node, speed blur.
5. **Input**: an action set with analog axes (keyboard sums, mouse deltas for the turret with
   recentring).

### Steps (each testable alone)

1. `lib/minigame` data layer (reads the ARE, LYT tracks and obstacles, gun banks, scripts) and a
   dump tool over the four areas. No engine hook needed: **done first** (below).
2. Swoop slice on `m03mg`: rail following, steering integrator and tunnel bounds, camera,
   bank and gear animations; the original `oncreate`, `heartbeat` and `onfire` scripts run
   against the routines.
3. Pads and obstacles: collisions, `OnHitFollower`/`OnHitObstacle`, invulnerability, death;
   finishing and returning to the home module.
4. The other routines (field accessors), written against the structs.
5. The turret: aim and mouse, bullets, enemy tracks and fire, damage, the HUD animations.
6. Polish: blur, distortion, particles, pause, the Manaan wake.

### Status

Hooks 1 and 2 are not in the engine yet (the engine lead confirmed `read_are` does not read the
struct), so **only step 1 is implemented**; the rest waits for the engine lead's agreement on the
hook above.
