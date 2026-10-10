# Minigames: pazaak, swoop racing, turrets

Pazaak is built and plays through (rules, the original's opponent, the three screens, the engine
hooks). The three swoop races run with the original's own scripts (rails, steering, pads and
obstacles, the HUD, the camera, the start and the finish), and so does the Ebon Hawk turret (aim,
guns, fighters, hits, the HUD, winning and losing: "The turret", last section). What the original
does is in [re/pazaak.md](../re/pazaak.md) and [re/minigames-swoop-turret.md](../re/minigames-swoop-turret.md).

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
| `lib/minigame/area.ctx` | `mg` | the ARE's `MiniGame` struct read into plain structs (`mg::Area`, `Follower`, `Bank`) |
| `lib/minigame/rail.ctx` | `mg` | a track model's `track` animation sampled into a `Rail` |
| `lib/minigame/run.ctx` | `mg` | `Run`: the objects of a race or the turret, the player's speed and steering, collisions, script events |
| `lib/minigame/turret.ctx` | `mg` | the turret: the aim, gun mounts read from the models, shots, bullets, enemy fire, hits, the gunner bot |
| `lib/engine/routines/swmg.ctx` | `rt_swmg` | the 97 `SWMG_*` routines over `w.minigame` |
| `game/minigame*.ctx` | `mg_game` | the run's scripts, the scene (models, guns, bullets, particles, animation layers, camera, sounds) and the minigame frame |
| `tools/mgdump`, `tools/mgrun` | | the four areas' setup dumped; the physics alone (a race, or `--gunner` on `M12ab`), without scripts or window |

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
  (`--headless`, `--engine-only`) `visit_auto` lets the AI play both sides with the default deck, so
  a script that asks for pazaak completes in tests: `kotor --module end_m01aa --engine-only --frames
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
  guard low totals as the original's do. Dragging a hand card onto one of the player's table slots
  plays it too, and a right-click on a hand flip card flips it, as in the original.
- **The player always starts a set**, as in the original; ties score nothing.
- **A blocking visit** in the loop rather than a screen layered into the frame: the minigame
  takes the whole frame, the world is not ticked meanwhile, and a script's end script runs when it
  returns. The sound is the loop's mixer.
- **Hover-repeat of the wager buttons** and the plus-minus sign (byte 0xB1 of the fonts) are the only
  additions to the original's controls.
- **Headless runs let the AI play** the player's side: a deterministic pass for tests.

### Open

- Music during the game (the original switches the sound mode to 4; unexplored).
- The card hover highlight (`lbl_cardhilite`), key shortcuts, dragging cards in the setup screen.
- Dimming the hand cards outside the player's turn (the original tints them 0.67 grey; ours keeps
  them enabled, as the original does, so a right-click flips one at any time, but draws them
  undimmed).
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
5. The turret: aim and mouse, bullets, enemy tracks and fire, damage, the HUD animations (done: "The turret" below).
6. Polish: blur, distortion, particles, pause, the Manaan wake.

### Status

Hooks 1 and 2 were agreed with the engine lead and are in: `obj::Area.minigame` is filled by
`read_are`, `w.minigame` holds the run, the loop calls `mg_game::frame` instead of its own step
while the area has a run. Minigame object ids are in `mg::ID_BASE` (0x7E000000) + slot, so the
world's generic routines answer "no such object" for them.

**Done (the swoop slice, steps 1-4 and part of 6):**

- The setup of all four areas is read and dumped (`mgdump`); the ARE's numbers equal the survey's.
- The player rides its rail at `speed/100` playback rate, accelerates toward `MaxSpeed` at the
  script's rate and steers with the original's lateral model (exact solution of its Runge-Kutta
  equation), clamped to the tunnel; pads (spheres) and obstacles (boxes of their models) raise
  `OnHitFollower` and `OnHitObstacle` (`mgrun`: at speed 200 on Taris the pads and obstacles are
  hit where the layout puts them).
- The unmodified `oncreate`, `heartbeat`, `onfire`, `accelpad` and `obstacle` scripts of all three
  races run against the routines with no fault: the start lights, gear shifts, the timer, the speed
  gauge and the finish (a fade, the time into the `*_SWOOP_*` globals and `StartNewModule` back
  home) all happen. Headless (`--engine-only`) the fire key is pressed twice a second; windowed it is
  Space, steering is A/D or the arrows.
- The picture: the bike, pads and obstacles as scene parts, the camera on the camera model's
  `camerahook` (so the shake animations move it), the HUD models with their animations layered
  per model (`game/minigame_anim.ctx`), screenshots with `--screenshot-at` and scripted keys:
  `kotor --module tar_m03mg --headless --frames 700 --input FILE --screenshot-at 690:out.png`.

**Not done (the swoop's):**

- The bike's lean (`BankL_01..10`) and the speed blur and heat distortion (`blur_on` is recorded,
  nothing draws it); particle emitters in the models; the gear sounds on the bike's own models.
- The pause menu (Escape pauses and resumes, nothing more).
- The Tatooine ground near the bike is black in `tat_m17mg` (the far desert is right): a room
  material, not the minigame; the missing engine routines the race scripts call
  (`SoundObjectSetVolume`, `SoundObjectSetFixedVariance`, `ShowTutorialWindow`) are the engine
  lead's: with them missing the engine sounds do not follow the gears.
- Obstacle hit geometry is the model's bounding box (the original tests its AABB tree), the
  invulnerability after a bump is `Invince_Period`: both ours.

## The turret

`M12ab` (the Ebon Hawk's gunner turret, entered from `k_ren_taris03`, `k_ren_levescape`,
`k_ren_unkturret`, `k_ren_turretload`, `k_ren_turretld02` and `k_act_hk47simul`) plays from the
original's unmodified scripts: `k_pebo_mgload`, `k_pebo_skybox` (the sky of the planet), the six
fighters' `k_pebo_sthcreate` and `k_pebo_sthdeath2..7`, the player's `k_heartbeat` (compass and
radar) and `k_pebo_hawkhit` (the health gauge, losing the Hawk), and the module heartbeat
`k_pebo_mgheart`, which leaves for `ebo_m12aa` (or the next story module) two seconds after the
sixth fighter dies. A whole sequence runs with no script fault, won and lost.

### The view and the aim

The player does not move: its track `m12ab_mgt01` is a point, and the offset is two angles in
degrees, `x` the pitch (clamped to 2..45 by the tunnel, starting at 7) and `z` the yaw (infinite:
it wraps at 360). Every model flagged `RotatingModel` (`mgf_turret` with its crosshair mesh
`target`, `mgf_turretwk`, the HUD models `mgf_hud01` radar and compass and `mgf_hud02` health
gauge, and the camera model `m12ab_camera`, which is the ARE's `Camera` field and not in
`Models`) is turned by `Rz(yaw) Rx(pitch)` about the track's hook; `mgf_ebonhawk` is not. The camera
is the camera model's node `camerahook` (`mg::part_matrix` gives every model's place, the swoop's
included). Keys turn at `MovementPerSec` (100 degrees a second) with the lateral model's inertia
(W/S or up/down tilt, A/D or left/right turn); the mouse is held in the window (SDL relative mode)
and adds its counts per frame divided by 20 and clamped to 1, of a full-speed turn (the original's
rule), on the axes the ARE's `Mouse` struct names (x for yaw, y for pitch). Our choices: moving the
mouse right turns right and up aims up (the original's sign is not in the survey); `Reverse
Minigame YAxis` is not read.

### Guns, bullets and hits

A bank's gun model hangs on the vehicle's node `gunbank<BankID>` (the turret's two banks sit at
x = +-1.3, tilted 5 degrees down and 0.5 degrees in, so the shots cross at 149 units); the muzzle is
the gun model's `bullethook` node and a shot leaves along its +Y. Both banks fire together: the
trigger (Space, the left mouse button, or the keys of a script) starts the gun's `fire` animation
and the bullet leaves when the animation reaches its `fire<N>` event, 0.3 s apart
(`Rate_Of_Fire`); a held trigger repeats at that rate (the original wants one press per shot; ours
is easier on the hand). Bullets travel `Speed` units a second for `Lifespan` seconds and are tested
each step as a segment against the target's `hitbullet` mesh (its box, grown by 1 unit; the
original tests the mesh's AABB tree): the player's against the live fighters (`Target_Type` bit 2),
the fighters' against the Hawk's hit mesh (bit 1). A hit bursts the bullet (its `explode`
animation, 2.3 s of particles), plays the bank's hit sound and runs the target's `OnHitBullet`
script or the default, `damage_object`: the `OnDamage` script (`k_pebo_hawkhit`) or the default,
`SWMG_OnDamage`, which at zero hit points raises `OnDeath` and otherwise plays `damage` then
`Ready_01` on the models. A fighter's `OnDeath` script calls `SWMG_OnDeath`: the death sound
(`mgs_sith_expl`), `die` on its models (the explosion, parts and smoke are the models' emitters),
and the object leaves after the animation (2.3 s).

Fighters follow their rails for ever (the `mgt02..07` Bezier tracks, 43 to 84 seconds, facing along
the path, 15 to 380 units from the turret). A bank fires when the Hawk is within `Sensing_Radius`
(200) of the gun mount and inside `Horiz_Spread` and `Vert_Spread` (70 degrees) of the way the mount
points; the bullet goes at the middle of the Hawk's hit mesh with an error of `Inaccuracy` (0.01)
times the distance. Left alone, the fighters take the Hawk from 3000 to the 2000 that ends the
sequence in about 36 seconds; the gunner bot clears all six in 16.

### The stage

`mg_game` builds one scene part per model of every object (a race's bike and HUD, the turret's
cockpit, each fighter), the gun models on their banks' nodes, and a part per bullet slot and model
the first time a shot of it is seen (96 slots). Every part with emitters keeps its particles (the
main menu's `gui3d` simulation): this is also what gives the swoop's bikes their exhaust and the
turret its explosions and bullet plumes. The HUD is the models' one-frame and looping animations
the scripts ask for (`HudRot_NNN`, `SithLoopNN`, `Health<n>`), layered as the swoop's.
Sounds (`mgs_ebon_fire`, `mgs_sith_fire` at the fighter, the hits, the explosions) go to the
mixer through the ambience's wave cache; the ARE's music (`mus_bat_sithbs`) loops. The fade of
`SetGlobalFadeOut` is drawn by the dialogue view's overlay. The creature the engine places in the
area is not drawn.

### Engine hooks this needed (small, marked `HOOK(minigames)`)

- A minigame object's `DelayCommand` runs (`lib/engine/routines/commands.ctx`,
  `lib/engine/events.ctx`): losing the Hawk delays `EndGame` on the player object, which is not a
  world object.
- `game/play.ctx`: the mouse, Escape (pause) and the other keys go straight to the game's keys in a
  minigame (no HUD shortcuts or quick saves), and `FRAME gunner`, `FRAME mouse DX DY` and
  `FRAME pause` are input script lines.
- `EndGame` ends the loop (there is no start screen to return to yet).

### Checking it

```
kotor/tools/ctxc run kotor/tools/mgrun -- --module M12ab --area m12ab --seconds 60 --gunner
echo "5 gunner" > kotor/out/turret.in
kotor --module end_m01aa --run-script k_act_hk47simul --headless --frames 1500 --input kotor/out/turret.in
kotor --module m12ab --headless --frames 2400 --input kotor/out/empty.in      # nobody plays: the Hawk falls
```

The first is the physics alone. The second is the whole sequence from the story's entry: the bot
kills the six fighters in 16 s, the module leaves two seconds later (`StartNewModule ebo_m12aa at
K_MINI_GAME`) and the Hawk's hold loads, 0 faults. The third loses it: at 36.5 s the script fades
out and at 40.5 s calls `EndGame`. `FRAME mouse` and `down left` / `down w` / `down space` lines aim
and fire by hand, `FRAME pause` pauses (the picture holds).

### Not done

- The original's bark text during the sequence (the HUD is hidden in a minigame, so "Incoming
  fighters!" shows nowhere), the `Alarm01` sound's positioning, `Reverse Minigame YAxis`.
- The hit tests are boxes, not the mesh's AABB tree; a held trigger repeats; the turn rate of the
  mouse has no setting.
- A start screen for `EndGame`.
