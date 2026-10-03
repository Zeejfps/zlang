# VIS: room visibility

A VIS file says, for each room of an area, which other rooms can be seen from it: a hand-made
potentially-visible set. While the camera is in room R, the engine draws R and the rooms listed
under R, and skips the rest. Rooms are the ones of the area's layout ([lyt.md](lyt.md)).

Resource type **3001** (`vis`), ASCII text. Type ids are in [resource-types.md](resource-types.md).

## Where the game keeps them

- 112 VIS files, one copy each, all in chitin's `data/lightmaps*.bif` (`lightmaps13.bif` holds 31,
  the rest are spread over `lightmaps.bif` .. `lightmaps12.bif`). None in modules, Override or the
  save.
- The resref is the **area** name, the same as the area's ARE, GIT and LYT (`m01aa.vis` goes with
  `m01aa.lyt` and `m01aa.are` in module `end_m01aa`). See [gff-module.md](gff-module.md) for areas.
- Every one of the 106 areas that a module uses (an ARE exists) has a VIS and a LYT.
- Leftovers no module uses: `m19aa`, `m21aa`, `m25ab`, `m41az`, `m47ac`, `stunt_ebobridge`.
  `m47ac.vis` has no LYT of its own (its two rooms, `m47ac_01x` and `m47ac_01a`, are the rooms of
  the unused `m47aa.lyt`).

## Grammar

What the 112 files look like (the count is missing once, see below):

```
file   = { entry } ;
entry  = room [ SP count ] CRLF { "  " room CRLF } ;   (the entry line starts in column 0)
room   = 1*( letter | digit | "_" ) ;                   (a room model name, see lyt.md)
count  = 1*digit ;                                      (decimal, number of lines that follow)
```

- **Line endings** are CRLF in every file. 13 files have no CRLF after the last line.
- **Indentation**: entry lines start in column 0; visible-room lines start with exactly two
  spaces (8,905 lines, no exceptions). No tabs, no blank lines, no comments.
- **Case varies**: 3,888 of 10,155 names have upper case letters (`M01aa_10` next to `m01aa_09`);
  4 files spell one room two ways (`m01aa_06b` and `M01aa_06b`; `M22AA_04A` and `M22aa_04a`).
  Compare names case-insensitively, as everywhere else (the LYT spells rooms its own way too).
- **The count is not reliable** (4 entries in 3 files):
  - `m38ab.vis` line 1: `m38ab_08 6` is followed by 5 names; line 55: `m38ab_06 8` by 7.
  - `m39aa.vis` line 72: `m39aa_15 7` is followed by 8 names.
  - `m17aa.vis` line 509: `m17aa_09w` has no count at all (and no names).

  A reader that trusts the count misreads the rest of `m38ab.vis` and `m39aa.vis`. Decision: the
  **indentation decides**. An unindented line starts a new entry (its first word is the room; a
  second word, if present, is the count, which is only checked and warned about); an indented
  line adds one name to the current entry. An indented line before any entry, more than two words
  on an entry line, or more than one word on an indented line is an error. With this rule all 112
  files parse. (xoreos parses VIS the same way and also warns on bad counts.)

## Meaning

- **Directed, not symmetric.** 666 of the 8,894 "A lists B" pairs have no "B lists A". Use only the
  current room's own entry.
- **A room does not list itself** (1,245 of 1,250 entries; 5 do). The current room is always drawn.
- **Entries may be empty**: 65 entries have no names (count 0, or once no count); draw just the
  room.
- **Duplicates**: 6 entries name a room twice; harmless, keep a set.
- **A room may appear twice as an entry head**: never in the shipped files.
- **Names that are not rooms of the area**: ignore them. In areas modules use:
  - `m17aa`: `m17aa11b` (missing underscore), `m17aa_09w`;
  - `m17ab`: `m17ab_00e`, `m17ab_00f`;
  - `m17af`: its only entry is `m17aa_00a 0`, but the area's one room is `M17af_00a`;
  - `m22ab`: `m22ab_13a`;
  - `m33aa`: `M33aa_01a`, `M33aa_02l`, `M33aa_03l`, `M33aa_04l`, `M33aa_05l` (rooms dropped from
    the layout);
  - `m39aa`: `m38aa_07` (another area's room);
  - `stunt_ebodant`: `StuntRoom12aa2`; `stunt_unkramp`: `StuntRoom41az`.

  In unused areas: `m25ab` (`m25ab_12a`, `m25ab_13a`), `m41az` (all six names are `M41ad_*`, the
  layout's rooms are `m41az_*`).
- **Rooms of the layout with no entry of their own** (12 files): `m17ab` (`_00b`, `_00c`, `_00d`),
  `m17ac`, `m17ad`, `m17ae` (`_00b` each), `m17af` (`_00a`, see above), `m22aa` (`_05a`, `_06a`),
  `m23aa` (`_11a`), `m28ad` (`_04a`), `m34aa` (`_09`), `stunt_ebodant` (`stuntroom12aa3`),
  `stunt_unkramp` (`stuntroom41ad`), and the unused `m41az` (six rooms). Several of these rooms
  have walkmesh faces (`m17af_00a`'s WOK has 1,147, `m17ac_00b`'s 171), so the player can be in
  them. What swkotor.exe does then is not known yet. Decision: **when the current room has no
  entry, draw every room** of the area. Drawing too much only costs time; drawing too little makes
  the world vanish. When the current room is unknown (camera outside every room), do the same.
- **No VIS for an area** does not happen in the shipped data; treat it as "everything visible".

Which room the camera is "in" is not part of this format (the engine has to locate the camera or
player against the rooms' walkmeshes or bounds; see [lyt.md](lyt.md)).

## Checked

`python kotor/tools/py/vis_probe.py` runs over every VIS copy (`kres.Game().every_entry('vis')`),
parses each with the rule above and compares every name with the rooms of the same-resref LYT
(parsed by `lyt_probe.py`) and with the module areas (ARE resources):

- 112 files parsed, 0 failures; 1,250 entries, 8,905 visible-room lines.
- 4 count mismatches, the names-not-in-LYT and rooms-without-entry lists above, symmetry and
  self-listing counts as above.

## Sources

- xoreos, `src/aurora/visfile.cpp` (read to compare parsing rules, nothing copied):
  https://github.com/xoreos/xoreos/blob/master/src/aurora/visfile.cpp
- Deadly Stream, ".lyt and .vis files" (what VIS is for, and that new rooms must be added to it):
  https://deadlystream.com/topic/4805-lyt-and-vis-files/
- Strings in `swkotor.exe` (`.vis`, `%s/%s.VIS`, `%s %d`, `  %s`) and the game data, via the probe
  above.
