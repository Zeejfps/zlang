# Pazaak in swkotor.exe

What the original does, found by reverse engineering (confidence high unless marked). The
reimplementation is `kotor/lib/pazaak` ([../design/minigames.md](../design/minigames.md)). Addresses
are for the unpacked Steam exe; the functions have no names in the binary, ours are below.

## Where it lives

| Address | Our name | What |
|---|---|---|
| `0x00540fd0` | `ExecuteCommandPlayPazaak` | routine 364: pops deck, end script, max wager, tutorial (if 4+ args), opponent (if 5) |
| `0x0053b1e0` | `ExecuteCommandGetLastPazaakResult` | routine 365: pushes client `+0x80` (1 = the player won the last match, 0 = lost or quit) |
| `0x005f3810` | start-pazaak (client) | clamps the wager, stores the end script, opens the setup panel (gui sound 4, sound mode 4) |
| `0x005f3950` | pazaak-finished (client) | stores the result, settles the gold, runs the end script |
| `0x00681a90` | `CSWGuiPazaakSetup` ctor | opens the wager panel (when the wager is above 0), loads the opponent's deck |
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

A card on a table or in a hand is a pair `(id, flag)`; `id` -1 is an empty slot. The flag matters only
for flip cards (1 = played as negative). `pazaakdecks.2da` and the script notation use `+n`, `-n`
and `*n` (the flip card of value n): `+d` is id d-1, `-d` is d+5, `*d` is d+11. Items: a pazaak card is
base item 86 (`g_i_pazcard_001..018`), whose ModelVariation maps to id `(variation + 11) mod 18`
(party-items-saves.md 5.9); the party table keeps one count per id (`PT_PAZAAKCARDS`, new game: two each
of ids 0..4) and the last chosen side deck (10 ids, `-1` = empty).

Textures (`swpc_tex_gui.erf`): plus `lbl_cardmpos`, minus `lbl_cardmneg`, flip `lbl_cardrarem` (flag 0)
and `lbl_cardraref` (flag 1), main deck `lbl_cardstand`, face-down `lbl_cardback`, win mark
`lbl_winmark02`. The card's text is a label over the button: `+n`, `-n`, `±n` (a flip card shows `+n`
or `-n` by its flag), `1`..`10`.

## A game

State (`0x230` bytes): the wager, the opponent's object id, two players' blocks of `0x70` bytes
(4 hand slots, 9 table slots, a stand flag, sets won), the 40-card main deck with its read index
(`0x228`, -1 = shuffle first) and the AI's state (`0x22c`).

- **Main deck**: 40 cards, four of each 1..10. A shuffle picks a random remaining card 40 times (`rand() %
  remaining`, the last remaining card fills the gap). Cards are drawn from the end; when the deck runs
  out in the middle of a match it is shuffled anew. It is not reshuffled between sets.
- **Hands**: before the match each player's 10-card side deck gives 4 random distinct cards the same way.
  Hand cards are never dealt again: what is played is gone for the rest of the match.
- **Total**: the sum of the table's cards up to the first empty slot (flip cards by their flag).
- **Adding a card to a table** (draw or play): the first empty slot; if that is the ninth slot, or the
  total is now exactly 20, the player **stands** automatically. A ninth card is not an automatic win in
  this game: both totals are compared as usual.
- **A set**: tables are cleared (stand flags too; sets won and hands stay). The player always begins,
  then the turns alternate. A turn begins with a draw from the main deck (automatic), then the player
  may play at most one hand card, then ends the turn or stands. A player who stands is skipped (the
  other goes on alone). After every turn the set is judged:
  - if either total is over 20, both are marked as standing;
  - when both stand, a bust counts as the worst possible total; the higher total wins the set, equal
    totals are a **tie** (nobody scores; in the original's words "the set is tied").
  - A match is the first to 3 sets. Messages (dialog.tlk): 32334 you win the set, 32335 the opponent
    wins the set, 32336 you have defeated your opponent, 32337 you have been defeated, 32338 tied,
    38649 the match is over.
- A busted player can still play a hand card in the same turn to come back to 20 or below; the bust
  is decided when the turn ends.
- **Flip** buttons (one per hand card) toggle a flip card's flag at any time in the player's turn;
  once played the card keeps its sign.
- **Quit** (Escape in the game panel, "are you sure you want to forfeit"): a loss with the wager.
  Quitting from the wager or setup panel, before the game, costs nothing (result: lost, wager 0).

## The opponent's AI (`0x006e4c60`, helper `0x006e4910`)

The AI is a small state machine called repeatedly during the opponent's turn: state 0 draws a card
(nothing if it already stands) and returns 1; states 1 and 2 decide; 3 and 4 return 0, which ends the
turn and resets the state to 0. The results (1 drew, 2 played a hand card, 3 stands, 4 ends the turn)
only drive the animation. Let *mine* and *theirs* be the totals (a total over 20 counts as -1,000,000,
and when theirs is over 20 the AI marks them as standing), *best-up* the highest total at most 20 that
playing one hand card can reach (for a flip card, either sign; -1,000,000 when nothing is playable and
the table is over 20, else *mine* if no card improves it) and the card that reaches it, *best-down*
the lowest total below *mine* one card can reach (or *mine*):

State 1:
1. If the player stands, *theirs* is less than *mine* and *mine* is at most 20: stand.
2. Play the best-up card (state becomes 2) when *theirs* is at most best-up, best-up >= 18, and one of:
   best-up == 20; best-up == 19 and best-down >= 12; best-down >= 14.
3. Otherwise, if *mine* is over 20: when the player has fewer than 2 sets won and *theirs* >= 18 and best-up
   is below *theirs*, end the turn (give the set up, keeping cards); else play the best-up card if
   there is one.
4. Otherwise decide as in state 2.

State 2 (also the tail of 1): recompute *mine* (over 20 counts as bust). If the player stands and *mine* < *theirs*:
end the turn (draw again next turn). If *mine* < 18 and best-down < 16: end the turn. Otherwise stand.

Ties between hand cards: strictly better totals replace the choice; an equal total replaces a chosen
*flip* card only (it prefers to keep flip cards). Evaluating a flip card sets its flag in the hand
slot (so unplayed flip cards in the AI's hand end up positive).

## Panels

- `pazaaksetup.gui`: 18 available cards `BTN_AVAILxy` (x = column: plus, minus, flip; y = value 1..6)
  with `LBL_AVAILxy` (the card text) and `LBL_AVAILNUMxy` (how many are left), 10 chosen slots
  `BTN_CHOSENn`/`LBL_CHOSENn`, `BTN_YTEXT` (Add card / Remove card, strrefs 38601/38602, by what has the
  focus), `BTN_ATEXT` (Play, enabled with 10 cards chosen), `LBL_TITLE`. Clicking an available card
  moves it to the first free chosen slot, clicking a chosen one returns it. Counts of 0 are dim. The
  previous side deck is preloaded if the player still owns the cards. Play asks "Are you sure you want
  to use this sidedeck?" (32322); Escape asks to forfeit (42424).
- `pazaakwager.gui`: `LBL_TITLE` (32320), `LBL_WAGERVAL`, `LBL_MAXIMUM` ("Maximum wager:" 32321 and the
  number), `BTN_LESS`/`BTN_MORE` (the wager changes by 1 and starts at the maximum; held buttons repeat),
  `BTN_WAGER`, `BTN_QUIT`. Shown first, only if the maximum is above 0 (the maximum is clamped to
  the party's gold: if gold <= maximum the maximum is the gold).
- `pazaakgame.gui`: `BTN_PLR0..8`/`BTN_NPC0..8` the table (a button's fill is the card, the label
  `LBL_PLRn` its text), `BTN_PLRSIDE0..3`/`BTN_NPCSIDE0..3` the hands (the opponent's face down),
  `BTN_FLIP0..3`, `LBL_FLIPICON`/`LBL_FLIPLEGEND` (shown when a flip card is in the hand),
  `LBL_PLRTOTAL`/`LBL_NPCTOTAL`, `LBL_PLRSCORE0..2`/`LBL_NPCSCORE0..2` (a set won gets
  `lbl_winmark02`), `LBL_PLRTURN`/`LBL_NPCTURN`, `LBL_PLRNAME`/`LBL_NPCNAME` (the player's name; the
  opponent creature's name if the script gave one), `BTN_XTEXT` End Turn (32332), `BTN_YTEXT` Stand (32333).
  Played hand cards are clicked (or double-clicked).

## The flow (the game panel's state machine, `0x00680030`)

States and timers (seconds): 0 begin; 1 the player's turn starts (a player who stands skips to 5),
turn-start sound `mgs_startturn`, 0.4 s; 2 the automatic draw (`mgs_drawmain`; `mgs_warnbust` if the
total is now over 20), then the player may act; 3 waiting for the player (a hand card may still be
played); 4 waiting after a hand card was played (`mgs_playside`; end turn or stand only); 5 the
player's turn is over: the set is judged, otherwise the opponent's turn: 6 (an opponent who stands
is skipped to 8, else `mgs_startturn`, 0.4 s); 7 one AI step per tick (0.8 s after a draw or a played
card, 0.4 s otherwise); 8 judge the set (nobody has won: back to 1); 9/10 the result message
(`mgs_winset`, `mgs_loseset`, `mgs_winmatch`, `mgs_losematch`) and its OK; 0xb a new set; 0xc the
match is over: the result goes to the client (below).

Sets are judged only after a turn (5, 8). Totals are shown at once; the opponent's cards are face
down until played.

## Result and gold (`0x005f3950`)

Stores `won` (1/0) and the wager; if the wager is above 0 and the leader exists: won adds the wager to
the party's gold, lost subtracts it (not below 0), with a status-summary line. Then it runs the end
script (if it is not empty) with OBJECT_INVALID as owner, and plays gui sound 5. The routine
GetLastPazaakResult reads the stored `won`. The wager is 0 for a free game; the original never
offers a second game after a match (a "play again" path exists in the code but nothing uses it).

## Tutorial (script argument `bShowTutorial`)

Pages of text (dialog.tlk 38624..38649) shown in a message box with Continue/Back/End Tutorial:
set start 38631, 38632; the first draw 38633 and then 38634..38636, 38642, 38643; after the first draw
38637..38639; the opponent's first turn 38645; exactly 20 (once) 38646; a bust 38647; the match end 38648.
The setup panel shows 38627..38629. With the tutorial on, End Turn above 15 asks to confirm
(38641), Stand below 14 asks (38640), playing a hand card below 13 asks (38642).

## Scripts

27 scripts call PlayPazaak (taris cantina, Dantooine, Kashyyyk, Manaan, Korriban, Tatooine, Yavin
station...). Decks used: 1 (average), 2 and 3 (strong); wagers 0 (free) to 750; the tutorial in the
`*_paztutor` scripts; `G_Paz_JustPlayed` is set by the scripts before the call.
