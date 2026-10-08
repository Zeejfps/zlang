# The journal and message log panels: what the original does

What `CSWGuiJournal` (`journal.gui`) and `CSWGuiMessages` (`messages.gui`) show and how they sort and
mark it, read from the binary (addresses are `swkotor.exe`'s; rechecked on 2026-10-07 against the
rebuilt decompile). Complements [gui.md](gui.md) sections
"CSWGuiMessages" and "CSWGuiJournal", which have the controls and events; our code is
`lib/ingame/journal_*.ctx`, `journal_panel.ctx` and `messages_panel.ctx`. Confidence is high unless
marked.

## The client journal

`CClientExoApp` keeps two lists of quests, one active and one completed (`GetJournal` `0x005ed320`,
active at +0x20, completed at +0; each list is a record array, its count at +4, and an array of
record indices at +0xc that the sort permutes), each with its own sort order (+0x38 and +0x18, values
0..3) and a "changed" flag (+0x3c, +0x1c) that makes the open panel rebuild the rows of the list it
shows in `Render` (`0x00645670`; `RebuildQuestList` clears that flag). The server's journal (the
party table's +0x11c, [party-items-saves.md](party-items-saves.md) 3.1, saved as `JNL_Entries` per 3.9) is one list of the same
records; it sends each change to the client (journal message minor 9, `0x00652380`), which files the
record by its End bit, moving it between the lists, and re-sorts both. A quest is a 0x3c-byte record:

| Offset | What |
|---|---|
| +0x00 | title (CExoLocString, from the JRL category's `Name`) |
| +0x08 | the text of the quest's current entry (CExoLocString, the entry's `Text`) |
| +0x10, +0x14 | game day and time the state was set (`JNL_Date`, `JNL_Time`) |
| +0x18 | the category tag (`JNL_PlotID`, stored lower-cased, matched without case) |
| +0x20 | the state, the entry `ID` (`JNL_State`) |
| +0x24 | priority (the category's `Priority`, a DWORD, 0 first) |
| +0x28 | the category's `Picture` (WORD; `global.jrl` has none, so 0) |
| +0x2c | flags: bit 0 the entry's `End` (completed), bit 2 "new" (set whenever the state is set outside a load; the tab bar's journal tab pulses while any quest of the active list has it, `0x00676470`) |
| +0x30 | the category's `PlotIndex`, a `plot.2da` row |
| +0x34 | the category's `PlanetID`, a `planetary.2da` row, -1 none |
| +0x38 | the experience the current step pays (see the last section) |

These fields are filled by `0x005c5a40` (set a quest's state: find or append the record by tag, then
copy the category's fields and the fields of the entry whose `ID` is the state from `global.jrl`).
Only the **current** entry's text is kept: the journal shows one text per quest, not the history. A
quest is on the completed list when the entry its state names has the End flag (data from `global.jrl`,
see [../formats/gff-dialog.md](../formats/gff-dialog.md)). A state that names no entry changes only
+0x20: the text, the End bit and the step's experience stay those of the previous entry.

## Sorting (`0x00676530`, selection sort; comparators `0x00675ed0`..`0x006760a0`)

The mode names are strrefs 32173..32176 (`0x007a2474`). A comparator returns negative when the later
element should replace the best so far, so the list ends up with:

| Mode | Order | Ties |
|---|---|---|
| 0 by Order Received | newest first: later (day, time) first (`CWorldTimer::CompareWorldTimes`) | not replaced |
| 1 by Name | ascending by the displayed title, compared byte by byte (`CExoString` `<`/`>`) | not replaced |
| 2 by Priority | ascending priority number (0 first, compared unsigned) | order received |
| 3 by Planet | **descending** `PlanetID` (as a signed number, so -1 comes last) | order received |

Each pass swaps the best element into place, so the sort is not stable: two quests that compare equal
can change places.

## The panel

- **Title** `LBL_TITLE`: "<list> - <sort>", the list being strref 32178 "Active Quests" or 32177
  "Completed Quests". **BTN_SWAPTEXT** names the other list. **BTN_SORT** reads "Sort <next mode's
  name>" (strref 42566 "Sort" + a space + the name), so it offers the mode a press would switch to
  (`OnPanelAdded` `0x00645e00`, events in `HandleInputEvent` `0x006456e0`). A sort press takes the
  shown list's mode + 1 (wrapping 3 to 0), stores it in the global, sets it on the shown list only,
  and resets both labels. A swap press stores the mode of the list it leaves in the global, flips the
  view and rebuilds, and retitles with that stored mode; the newly shown list keeps its own order and
  `BTN_SORT` keeps its text, so the title can name a mode the list is not sorted by (med: needs a
  runtime check).
- **Rows** (`RebuildQuestList` `0x00645330`): one button per quest with the title; a "new" quest gets the
  colour (0.95, 0.00, 0.85) for both its text and its hilight text (`0x00644790`; the normal colours are
  the menu blue and hilight yellow). A rebuilt list selects its first quest (also after a sort).
- **Text** of the selected quest (`0x00645100`): when `PlanetID` is not -1, `planetary.2da`'s `Name`
  strref, then ":\n", then the entry's text. Selecting a quest records its row in a list of "seen"
  rows; `ClearQuestRows` (`0x00645610`, run when the list is swapped and when the panel is removed)
  clears the new flag of those quests (the client's copy only).
- The sort order is one number saved in the party table (`JNL_SortOrder`, global `0x00833a90`,
  written only when the journal holds a quest; `OnPanelAdded` applies it to the shown list only). When a global flag (`0x00833a94`) is set, the next
  opening uses mode 0 instead and clears the flag; the flag is set by `0x00676c20` when the client
  receives the server's journal notice (journal message minor 0x0c, `0x006526e0`), which also posts
  the status-summary event. That opening does not write 0 to the saved global, so a later opening
  without a press goes back to the old mode (med: needs a runtime check).
- Up and down scroll the text while the quest list keeps the focus.

## The message log (`0x00626920` feedback, `0x00626b10` dialogue)

- The panel starts on the **dialogue** log: the remembered view byte (`CGuiInGame+0xbc8`) is 0 when the
  game starts and the two `Show*Log` functions set it (0 dialogue, 1 feedback). Titles are strref 1563
  "Messages" + " - " + strref 371 "Dialog" or 42167 "Feedback".
- A dialogue row reads "<speaker>: <line>" when the line has a speaker, else just the line. A feedback
  row is the menu blue unless its kind byte (saved as `PT_FB_MSG_COLOR`, [combat.md](combat.md) 10)
  is 1; then it is (0.74, 0.11, 0), a red. The combat formatter passes kind 1 for the attack summary
  and a few other lines (e.g. `PUSH 1` before the call at `0x0066036b`; [combat.md](combat.md) 10.1
  lists them), and the save restore passes the saved byte. (high)
- Each row is sized to its wrapped text (height from the text plus the border), and the list selects the
  last row, so the newest line shows.

## Quest steps pay experience (`AddJournalQuestEntry` `0x005483f0`)

Setting a quest to a higher state (or any state with the script's `bAllowOverrideHigher`; a negative
state is taken as its absolute value) records the date and time, sets the state (`0x005c5a40`), then
reads the quest's experience back out of the journal (`0x005c5850`, the field +0x38) and, when it is
not 0, gives it to the party (`CSWPartyTable::AddExperience(xp, 1)`). `0x005c5a40` fills +0x38 from
global.jrl while setting the state: the category's `PlotIndex` names a plot.2da row and the entry's
`XP_Percentage` is the share of that row's XP the step pays, rounded to the nearest (it adds 0.5
and truncates, `0x005c605b`). A conversation node's `Quest`/`QuestEntry` (`CSWSDialog::UpdateJournal`
`0x0059ef00`) does the same for higher states only, and also posts status-summary event 2 with the
amount. `GetJournalQuestExperience` (`0x0053a680`) does **not** ask the same question: it returns the
category's `XP` DWORD from global.jrl (tag compared with case), a field the game's global.jrl does not
have, so it returns 0 for every quest. The Manaan Star Map (`man26_starmap` 40, `PlotIndex` 64, the row
`tat_starmap`, 2,000 XP at 1.0) and a step of the planet's quest (`man_planet` 60: 0.4 of 3,000) are
paid this way; no script or dialogue node names them. Categories with `PlotIndex` -1 (`k_starforge`)
pay nothing. `rt_misc::set_quest_state` does it for the routine and for a conversation node's
`Quest`/`QuestEntry`, but rounds the share up (as plot XP does) where the original rounds to nearest.
