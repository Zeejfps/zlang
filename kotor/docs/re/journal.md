# The journal and message log panels: what the original does

What `CSWGuiJournal` (`journal.gui`) and `CSWGuiMessages` (`messages.gui`) show and how they sort and
mark it, read from the binary (addresses are `swkotor.exe`'s). Complements [gui.md](gui.md) sections
"CSWGuiMessages" and "CSWGuiJournal", which have the controls and events; our code is
`lib/ingame/journal_*.ctx`, `journal_panel.ctx` and `messages_panel.ctx`. Confidence is high unless
marked.

## The client journal

`CClientExoApp` keeps two lists of quests, one active and one completed (`GetJournal` `0x005ed320`,
active at +0x20, completed at +0), each with its own sort order (+0x38 and +0x18, values 0..3) and a
"changed" flag (+0x3c, +0x1c) that makes the open panel rebuild its rows in `Render` (`0x00645670`). A quest
is a 0x3c-byte record:

| Offset | What |
|---|---|
| +0x00 | title (CExoLocString, from the JRL category's `Name`) |
| +0x08 | the text of the quest's current entry (CExoLocString, the entry's `Text`) |
| +0x10, +0x14 | game day and time the state was set (`JNL_Date`, `JNL_Time`) |
| +0x18 | the category tag (`JNL_PlotID`) |
| +0x24 | priority (the category's `Priority`, 0 first) |
| +0x2c | flags: bit 2 "new" (the tab bar's journal tab pulses while any quest of the active list has it, `0x00676470`) |
| +0x34 | the category's `PlanetID`, a `planetary.2da` row, -1 none |

Only the **current** entry's text is kept: the journal shows one text per quest, not the history. A
quest is on the completed list when the entry its state names has the End flag (data from `global.jrl`,
see [../formats/gff-dialog.md](../formats/gff-dialog.md)).

## Sorting (`0x00676530`, selection sort; comparators `0x00675ed0`..`0x006760a0`)

The mode names are strrefs 32173..32176 (`0x007a2474`). A comparator returns negative when the later
element should replace the best so far, so the list ends up with:

| Mode | Order | Ties |
|---|---|---|
| 0 by Order Received | newest first: later (day, time) first (`CWorldTimer::CompareWorldTimes`) | stay in place |
| 1 by Name | ascending by the displayed title, compared byte by byte (`CExoString` `<`/`>`) | stay in place |
| 2 by Priority | ascending priority number (0 first) | order received |
| 3 by Planet | **descending** `PlanetID` (as a signed number, so -1 comes last) | order received |

## The panel

- **Title** `LBL_TITLE`: "<list> - <sort>", the list being strref 32178 "Active Quests" or 32177
  "Completed Quests". **BTN_SWAPTEXT** names the other list. **BTN_SORT** reads "Sort <next mode's
  name>" (strref 42566 "Sort" + a space + the name), so it offers the mode a press would switch to
  (`OnPanelAdded` `0x00645e00`, events in `HandleInputEvent` `0x006456e0`).
- **Rows** (`RebuildQuestList` `0x00645330`): one button per quest with the title; a "new" quest gets the
  colour (0.95, 0.00, 0.85) for both its text and its hilight text (`0x00644790`; the normal colours are
  the menu blue and hilight yellow). A rebuilt list selects its first quest (also after a sort).
- **Text** of the selected quest (`0x00645100`): when `PlanetID` is not -1, `planetary.2da`'s `Name`
  strref, then ":\n", then the entry's text. Selecting a quest records its row in a list of "seen"
  rows; `ClearQuestRows` (`0x00645610`, run when the list is swapped and when the panel is removed)
  clears the new flag of those quests.
- The sort order is one number saved in the party table (`JNL_SortOrder`); when a global flag
  (`0x00833a94`) is set the next opening resets it to 0 and clears the flag (med: who sets it was not
  traced, likely a game start or load).
- Up and down scroll the text while the quest list keeps the focus.

## The message log (`0x00626920` feedback, `0x00626b10` dialogue)

- The panel starts on the **dialogue** log: the remembered view byte (`CGuiInGame+0xbc8`) is 0 when the
  game starts and the two `Show*Log` functions set it (0 dialogue, 1 feedback). Titles are strref 1563
  "Messages" + " - " + strref 371 "Dialog" or 42167 "Feedback".
- A dialogue row reads "<speaker>: <line>" when the line has a speaker, else just the line. A feedback
  row is the menu blue unless its saved colour byte (`PT_FB_MSG_COLOR`) is 1; then it is (0.74, 0.11, 0),
  a red used for combat results.
- Each row is sized to its wrapped text (height from the text plus the border), and the list selects the
  last row, so the newest line shows.
