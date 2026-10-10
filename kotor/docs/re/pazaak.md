# Pazaak in swkotor.exe

What the original does, found by reverse engineering (confidence high unless marked). The
reimplementation is `kotor/lib/pazaak` ([../design/minigames.md](../design/minigames.md)). Addresses
are for the unpacked Steam exe; the functions have no names in the binary, ours are below.
The whole page was rechecked claim by claim on 2026-10-08 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)); a med claim that says "needs a runtime check"
rests on static reading alone and is surprising enough to test before relying on it.

## Where it lives

| Address | Our name | What |
|---|---|---|
| `0x00540fd0` | `ExecuteCommandPlayPazaak` | routine 364: pops deck, end script, max wager, tutorial (if 4+ args), opponent (if 5) |
| `0x0053b1e0` | `ExecuteCommandGetLastPazaakResult` | routine 365: pushes client `+0x80` (1 = the player won the last match, 0 = lost or quit) |
| `0x005f3810` | start-pazaak (client) | does nothing while a game runs (client `+0x70`, then set to 1); caps a wager above 0 at the leader's gold, resets the result `+0x80` to 0, stores the wager `+0x7c`, end script `+0x74` and deck `+0x84`, opens the setup panel (gui sound 4, sound mode 4) |
| `0x005f3950` | pazaak-finished (client) | stores the result `+0x80` and the wager, clears `+0x70`, settles the gold, runs the end script (gui sound 5, sound mode 0); a third argument, when non-zero, would instead restart pazaak with the same deck, wager 0 and the tutorial on, but every caller passes 0 |
| `0x00681a90` | `CSWGuiPazaakSetup` ctor | creates the game state (wager, opponent), builds the wager panel when the maximum wager is above 0 (the setup panel's OnPanelAdded `0x0067f750` puts it on top), loads the opponent's side deck (`pazaakdecks.2da` row, a random row if negative) and deals its hand |
| `0x0067f000` | `CSWGuiPazaakWager` ctor | `pazaakwager.gui` |
| `0x006808a0` | `CSWGuiPazaakGame` ctor | `pazaakgame.gui`; its state machine is `0x00680030` |
| `0x006e4360`..`0x006e4c60` | the rules | total, hand dealing, table, main deck, set result, side-deck loading, the AI |

## Cards

Ids 0..27, one table of values (`0x007a26b8`):

| Ids | Card | Value |
|---|---|---|
| 0..5 | plus cards `+1`..`+6` | +1..+6 |
| 6..11 | minus cards `-1`..`-6` | -1..-6 |
| 12..17 | flip cards `±1`..`±6` | +n, or -n when the card's flag is set |
| 18..27 | main-deck cards 1..10 | 1..10 |

A card on a table or in a hand is a pair `(id, flag)`; `id` -1 is an empty slot (the total stops
there; any other negative id counts 0, and the game panel draws the opponent's face-down hand cards as
id -2). The flag matters only for flip cards (1 = played as negative). `pazaakdecks.2da` and the script notation use `+n`, `-n`
and `*n` (the flip card of value n): `+d` is id d-1, `-d` is d+5, `*d` is d+11 (the loader `0x006e4a40`
reads only the sign and the second character, so values are single digits). Items: a pazaak card is
base item 86 (`g_i_pazcard_001..018`), whose ModelVariation maps to id `(variation + 11) mod 18`
(party-items-saves.md 5.9); the party table keeps one count per id (`PT_PAZAAKCARDS`, new game: two each
of ids 0..4) and the last chosen side deck (10 ids, `-1` = empty).

Textures (`swpc_tex_gui.erf`): plus `lbl_cardmpos`, minus `lbl_cardmneg`, flip `lbl_cardrarem` (flag 0)
and `lbl_cardraref` (flag 1), main deck `lbl_cardstand`, face-down `lbl_cardback`, win mark
`lbl_winmark02`; an empty slot (-1) draws nothing and any other id (such as -2) `lbl_cardback`. The card's text is a
label over the button, set by `0x0067cd30` (used by the setup and game panels): `+n`, `-n`, `1`..`10`,
and a flip card shows `+n` or `-n` by its flag. The text table `0x007a2600` also holds `±n` strings for
ids 12..17, but `0x0067cd30` never picks them.

## A game

State (`0x230` bytes): the wager, the opponent's object id, two players' blocks of `0x70` bytes
(4 hand slots, 9 table slots, a stand flag, sets won), the 40-card main deck with its read index
(`0x228`, -1 = shuffle first) and the AI's state (`0x22c`).

- **Main deck**: 40 cards, four of each 1..10. A shuffle picks a random remaining card 40 times (`rand() %
  remaining`, the last remaining card fills the gap). Cards are drawn from the end; when the deck runs
  out in the middle of a match it is shuffled anew. It is not reshuffled between sets.
- **Hands**: before the match each player's 10-card side deck gives 4 cards from 4 different random
  positions the same way (`0x006e4580`, `rand() % remaining` over 10, 9, 8, 7). The opponent's hand is
  dealt in the setup panel's constructor, the player's when the chosen side deck is confirmed
  (`0x00681890`, which also saves it to the party table). Hand cards are never dealt again: what is
  played is gone for the rest of the match.
- **Total**: the sum of the table's cards up to the first empty slot (flip cards by their flag).
- **Adding a card to a table** (draw or play): the first empty slot; if that is the ninth slot, or the
  total is now exactly 20, the player **stands** automatically. A ninth card is not an automatic win in
  this game: both totals are compared as usual.
- **A set**: tables are cleared (stand flags too; sets won and hands stay). The player always begins,
  then the turns alternate (a new set, `0x0067e770`, puts the game panel back in state 0). A turn begins
  with a draw from the main deck (automatic), then the player may play at most one hand card (a hand
  card is accepted only in panel state 3, and playing one moves it to state 4), then ends the turn or
  stands. The AI likewise plays at most one hand card per turn. A player who stands is skipped (the
  other goes on alone). After every turn the set is judged:
  - if either total is over 20, both are marked as standing;
  - when both stand, a bust counts as the worst possible total; the higher total wins the set, equal
    totals are a **tie** (nobody scores; in the original's words "the set is tied").
  - A match is the first to 3 sets. Messages (dialog.tlk): 32334 you win the set, 32335 the opponent
    wins the set, 32336 you have defeated your opponent, 32337 you have been defeated, 32338 tied;
    with the tutorial on, the tutorial helper adds 38648 (the match continues to 3 sets) after a set
    and 38649 the match is over after the last one.
- A busted player can still play a hand card in the same turn to come back to 20 or below; the bust
  is decided when the turn ends.
- **Flip** buttons (`BTN_FLIP0..3`, one per hand card) toggle a flip card's flag (`0x0067dcf0`); once
  played the card keeps its sign. Neither the toggle nor the button's enabling in the panel refresh
  (`0x0067d4b0`: enabled when the slot holds a flip card) checks whose turn it is, so flipping seems
  possible during the opponent's turn too (med, needs a runtime check); the flag counts only once the
  card is played.
- **Quit** (Escape in the game panel, 42425 "are you sure you want to forfeit the match?", `0x0067db50`):
  a loss with the wager. Quitting from the wager or setup panel (42424), before the game, costs nothing
  (`0x0067d3d0`; result: lost, wager 0).

## The opponent's AI (`0x006e4c60`, helper `0x006e4910`)

The AI is a small state machine called once per tick during the opponent's turn (game panel state 7,
through `0x0067cb10`, which stores the return value as the next state at `+0x22c`): state 0 draws a
card and returns 1 (if the AI already stands it returns 0 without drawing; the panel never calls it
then, since it skips a standing opponent); states 1 and 2 decide; 3 and 4 return 0 (any other state
returns 4). A return of 0 ends the turn (the panel judges the set) and leaves the state at 0 for the
next turn. The other results (1 drew, 2 played a hand card, 3 stands, 4 ends the turn) are the next
state and pick the panel's sound and animation. Let *mine* and *theirs* be the totals (a total over 20
counts as -1,000,000; on every call, in any state, the AI first marks the player as standing when
theirs is over 20), *best-up* the highest total at most 20 that playing one hand card can reach (for a
flip card, either sign; a result over 20 counts as -1,000,000; it starts at *mine*, or -1,000,000 when
the table is over 20, and no card is chosen if nothing beats that) and the card that reaches it,
*best-down* the lowest total below *mine* that one card can reach without going over 20 (it may be
negative; *mine* if none, and -1,000,000 when the table is over 20):

State 1:
1. If the player stands, *theirs* is less than *mine* and *mine* is at most 20: stand.
2. Play the best-up card (state becomes 2) when a card was chosen, *theirs* is at most best-up,
   best-up >= 18, and one of: best-up == 20; best-up == 19 and best-down >= 12; best-down >= 14.
3. Otherwise, if *mine* is over 20: when the player has fewer than 2 sets won and *theirs* >= 18 and best-up
   is below *theirs*, end the turn (give the set up, keeping cards); else play the best-up card if
   there is one.
4. Otherwise decide as in state 2.

State 2 (also the tail of 1): recompute *mine* (over 20 counts as bust). If the player stands and *mine* < *theirs*:
end the turn (draw again next turn). If *mine* < 18 and best-down < 16: end the turn. Otherwise stand.

Ties between hand cards (both searches): strictly better totals replace the choice; an equal total
replaces a chosen *flip* card only (it prefers to keep flip cards). Evaluating a flip card writes its
flag into the hand slot (negative first, then positive), and the search finally writes the chosen
card's sign back: after a search every flip card in the AI's hand is positive except the chosen one.
The card played carries the sign the best-up search chose.

## Panels

- `pazaaksetup.gui` (ctor `0x00681a90`; contents filled when it is added, `0x0067f750`): `LBL_TITLE`
  ("Choose Sidedeck" 32323), `LBL_LTEXT`/`LBL_RTEXT` ("Available cards" 32326 / "Chosen cards" 32327),
  18 available cards `BTN_AVAILxy` (x = column 0..2: plus, minus, flip; y = row 0..5, the value minus
  1; card id 6x + y) with `LBL_AVAILxy` (the card text) and `LBL_AVAILNUMxy` (how many are left), 10
  chosen slots `BTN_CHOSEN0..9`/`LBL_CHOSEN0..9`, `BTN_ATEXT` (Play 32325, enabled only with 10 cards
  chosen). The `.gui` also has a `BTN_YTEXT` (Add card 38601), but the constructor never binds it, so
  it never shows (the tag `BTN_YTEXT` is bound only by the game panel, as Stand); the setup's button
  object (+0x6f34) is driven only by pad events (its text switches between Add card / Remove card
  38601/38602 by which column has the focus, and the Y command 0x2a acts on the focused card).
  Clicking an available card moves it to the first free chosen slot, clicking a chosen one returns it
  (`0x006807e0`); cards can also be dragged: an available card dropped on a chosen slot replaces that
  slot's card, a chosen card dropped on another chosen slot swaps the two, and dropped on the
  available cards it returns. A card whose copies are all chosen shows 0, is dimmed and cannot be
  dragged; a card the player does not own is an empty slot with no number. The previous side deck
  (party table `+0x168`) is preloaded card by card while the player still owns a copy. Play asks "Are
  you sure you want to use this sidedeck?" (32322; Yes `0x00681890` opens the game); Escape asks to
  forfeit (42424).
- `pazaakwager.gui` (ctor `0x0067f000`, input `0x0067e150`): `LBL_TITLE` (32320), `LBL_WAGERVAL`,
  `LBL_MAXIMUM` (two lines: "Maximum wager:" 32321 and the maximum, then "Credits:" 38600 and the
  leader's gold), `BTN_LESS`/`BTN_MORE` (the wager changes by 1 between 1 and the maximum; held
  buttons repeat, gui.md 10.5). The panel's own value (`+0xc94`, shown in `LBL_WAGERVAL`) starts at
  the maximum, which is what the player sees first; the game state's wager, set to 1 by the setup
  constructor when it builds this panel, is replaced by `BTN_WAGER` (Wager 42393: stores the shown
  value in the game state and closes the panel, `0x0067d3b0`), `BTN_QUIT` (Quit 42172; it and Escape
  ask to forfeit, 42424, with the setup panel's answer `0x0067d3d0`). Shown first, on top of the setup
  panel, only if the maximum is above 0 (the opener caps the maximum at the leader's gold: if gold <=
  maximum the maximum is the gold).
- `pazaakgame.gui` (ctor `0x006808a0`, refresh `0x0067d4b0`): `BTN_PLR0..8`/`BTN_NPC0..8` the table (a
  button's fill is the card, the label `LBL_PLRn`/`LBL_NPCn` its text; a standing player's table is
  dimmed), `BTN_PLRSIDE0..3`/`BTN_NPCSIDE0..3` the hands with labels `LBL_PLRSIDEn`/`LBL_NPCSIDEn`
  (the opponent's face down), `LBL_PLRSIDEDECK`/`LBL_NPCSIDEDECK` ("Player Hand"/"Opponent Hand"),
  `BTN_FLIP0..3` (each enabled only over a flip card), `LBL_FLIPICON`/`LBL_FLIPLEGEND` ("Flip Hand
  Card" 32331; shown when a flip card is in the hand), `LBL_PLRTOTAL`/`LBL_NPCTOTAL`,
  `LBL_PLRSCORE0..2`/`LBL_NPCSCORE0..2` (a set won gets `lbl_winmark02` while the result message is
  up), `LBL_PLRTURN`/`LBL_NPCTURN` (shown during that side's turn), `LBL_PLRNAME`/`LBL_NPCNAME` (the
  player creature's name, set when the panel is added `0x0067ffa0`; the opponent creature's name if
  the script gave one, else the `.gui`'s "Opponent" 32340, which every shipped script gets),
  `BTN_XTEXT` End Turn (32332), `BTN_YTEXT` Stand (32333). A hand card is played by double-clicking it
  (0x1f9) or dragging it onto one of the player's table slots (`0x0067ef00`), only in state 3; a plain
  click does nothing (its handler `0x00680790` acts only when a pending mode `+0x86e4` is 1, play, or
  2, flip, set by two controls at `+0x6ff4`/`+0x71c8` that no `.gui` tag binds). Right-clicking a hand flip card (0x44) toggles its sign like its `BTN_FLIPn`
  (`0x0067dcf0`: the panel's active control must be a hand card holding a flip card, ids 12..17;
  it plays click sound 0 and refreshes; no state check, and the refresh never disables the hand cards,
  only tinted 0.67 grey outside state 3, so it works on either side's turn).
  The drag is the card control's own (vtable `0x007531c0`, every card of both panels): a left press
  stores the pointer (`0x0067d040`); a move with the left capture held, while the card has a fill
  and has not yet been dragged, makes it the manager's dragged object (+0x54) once the pointer is
  more than 12 pixels from the press in x or y (`0x0067d060`, which answers 0, so the hover keeps
  following the pointer); the manager draws the dragged object after the modal panels, centred on
  the pointer and not hilighted, with its number label moved as much (`0x0067cf00`); letting go
  clears it and sends the card event 0x17feb instead of 0x27 (`0x0067d0d0`). Only the player's hand
  cards handle 0x17feb (`0x0067ef00`, set by the constructor at `0x00681501`): in state 3, with the
  hovered control one of `BTN_PLR0..8` (or the unbound play control `+0x6ff4`), the card is played
  (`0x0067ede0`); over the unbound flip control `+0x71c8` it is flipped.

## The flow (the game panel's state machine, `0x00680030`)

The panel's Render (`0x00680710`) counts the delay (`+0x86d8`, seconds) down; once it is negative it
runs steps while they return 1 and the game panel is the top panel (`0x0040adf0`), so the game
waits while any message box or tutorial page is up. States: 0 begin; 1 the player's turn starts (a
player who stands skips to 5; else `LBL_PLRTURN`, `mgs_startturn`, 0.4 s); 2 the automatic draw
(`mgs_drawmain`; if the draw made the player stand, a ninth card or 20, the Stand button flashes and
0.4 s; `mgs_warnbust` if the total is now over 20), then 3; 3 waiting for the player (a hand card may
still be played; a player who stands goes to 5); 4 waiting after a hand card was played
(`mgs_playside`, 0.4 s; end turn or stand only); End Turn or Stand (states 3/4 only) go to 5 after
0.4 s, Stand setting the stand flag; 5 the player's turn is over: the set is judged (`0x006e48a0`), a
result goes to 8, otherwise the opponent's turn: 6 (an opponent who stands is skipped to 8, else
`LBL_NPCTURN`, `mgs_startturn`, 0.4 s); 7 one AI step each time the delay runs out: a draw
(`mgs_drawmain`, `mgs_warnbust` over 20) or a played card (`mgs_playside`) waits 0.8 s; a stand or an
ended turn flashes that button with the click sound and the next step comes on the next frame; the
AI's 0 sets 0.4 s and judges at once (8); 8 judge the set (nobody has won: back to 1); a won set adds
to that side's sets and picks the message: 32334 / 32336 with `mgs_winset` / `mgs_winmatch`, 32335 /
32337 with `mgs_loseset` / `mgs_losematch`, a tie 32338 with no sound; 9/10 the result message, its
sound and its OK (`0x0067e9a0`: neither side at 3 sets: 0xb, else 0xc); 0xb a new set (`0x0067e770`:
tables and stand flags cleared, back to 0); 0xc the match is over: the result goes to the client
(below), won = the player has more sets.

Sets are judged only after a turn (5, 8). Totals are shown at once; the opponent's cards are face
down until played.

## Result and gold (`0x005f3950`)

Stores `won` (1/0) and the wager (client `+0x80`, `+0x7c`), clears the pazaak-running flag (`+0x70`)
and returns the input class to 0; if the wager is above 0 and the leader exists: won adds the wager to
the leader's gold, lost subtracts it (not below 0), with a status-summary line when the gold changed.
Then it runs the end script (if it is not empty) with OBJECT_INVALID as owner, plays gui sound 5 and
sets sound mode 0. The routine GetLastPazaakResult reads the stored `won`. The wager is 0 for a free
game and for a quit from the wager or setup panel; a forfeit in the game panel passes the wager.
The original never offers a second game after a match: a "play again" argument would skip the end
script and reopen the setup panel (same deck and end script, no wager, tutorial on), but all four
callers pass 0.

## Tutorial (script argument `bShowTutorial`)

Pages of text (dialog.tlk 38627..38649) shown in the panels' own message box (`0x0067def0`, paging
`0x0067d260`): one page has Continue (38623); a sequence has Continue and Back (38624; Back on the
first page closes it); a confirmation has the action's name and Cancel (38626). The setup panel shows
38627..38629 when it opens. In the game: 38631, 38632 at the start of the first set; 38633 after the
player's first draw, and when that is closed, 38634..38636, 38643, 38644 (flip cards), then
38637..38639 after Continue on the last of those; 38645 at the opponent's first turn; 38646 the first
time in a set a total is exactly 20 (the player's at the end of a turn, or the opponent's after an AI
draw or card); 38647 each time the player ends a turn over 20; 38648 after each set result while the
match goes on, 38649 at its end. The 38648 page has End Tutorial (38625): closing it that way (or with
Escape) ends the match at once and scores it by the sets won so far (`0x0067ea10`; med, needs a
runtime check). With the tutorial on, End Turn above 15 asks to confirm (38641), Stand below 14 asks
(38640), playing a hand card below 13 asks (38642, button "Play Hand Card" 32330).

## Scripts

28 scripts call PlayPazaak (33 calls in 32 compiled versions): Taris (three modules), Dantooine,
Kashyyyk, Manaan, Korriban, Tatooine, Yavin station, and `k_act_mispaz` in `scripts.bif`. Decks used:
1 (average), 2 and 3 (strong); wagers 0 (free) to 750; the tutorial in the `*_paztutor` scripts and
`yav47_suvam11`; no call passes an opponent (all give OBJECT_INVALID or leave it out).
`G_Paz_JustPlayed` is set to TRUE before the call by 17 of the 32 (the Dantooine, Manaan, Korriban,
Taris and Yavin ones, except the Taris tutorial and the `manm26aa` tutorial; none on Kashyyyk or
Tatooine, nor `k_act_mispaz`).
