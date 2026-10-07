# 2DA (`2DA V2.b`, `2DA V2.0`)

A 2DA ("two-dimensional array") is a table of strings: named columns, labelled rows, one string
per cell. The rules data of the game lives in them: appearances, base items, classes, feats,
spells, sounds, visual effects, GUI and key settings, and so on (209 tables). Other formats and
scripts refer to a table's rows by number (a UTC's `Appearance_Type` is a row of
`appearance.2da`) and to its columns by name.

KOTOR ships every table in BioWare's **binary** form, `2DA V2.b`. The engine also accepts the
older **text** form, `2DA V2.0`, but no file in the install uses it.

This file is about the container format. What each table's columns mean and what they point at is
in [2da-catalog.md](2da-catalog.md).

All integers are little-endian.

## Where

| What | Value |
|---|---|
| Resource type | `2da`, id 2017 ([resource-types.md](resource-types.md)) |
| `data/2da.bif` (via `chitin.key`) | 209 tables, one copy of every name |
| `patch.erf` | 4 newer copies: `bindablekeys`, `keymap`, `skills`, `weapondischarge` |
| `rims/global.rim`, `rims/miniglobal.rim` | 153 tables each, all also in the BIF (Xbox leftovers; 13 of them in an altered byte form, see Quirks) |
| `Override/`, saves, modules | none |

519 copies in all. Which copy wins is the resource manager's business
([resources.md](resources.md)); in practice the `patch.erf` copy must win over the BIF's (it is
the shipped update), and the `rims/` copies never matter. A table is found by resref (at most 16
characters, case-insensitive) and type.

## Binary layout (`2DA V2.b`)

```
0     "2DA V2.b"                         8 bytes, no NUL
8     "\n"                               1 byte
9     column names                       name TAB name TAB ... name TAB NUL
      row count                          u32
      row labels                         label TAB label TAB ... label TAB   (row count of them)
      cell offsets                       u16 x (rows x columns), row-major
      data size                          u16
      string pool                        NUL-terminated strings, to the end of the file
```

Nothing is aligned; each part starts right after the previous one, so the only way to find the
offset table is to walk the names and labels.

| Part | Size | Type | Meaning |
|---|---|---|---|
| magic | 8 | char[8] | `2DA V2.b` |
| newline | 1 | char | `\n` (0x0A) in every file |
| column names | variable | text | each name followed by one TAB (0x09); after the last name's TAB, one NUL (0x00) |
| row count | 4 | u32 | number of rows, R (0 in four tables) |
| row labels | variable | text | R labels, each followed by one TAB; no terminator after the last TAB |
| cell offsets | 2·R·C | u16[R][C] | for row r, column c: the entry at index r·C + c is the byte offset of that cell's string from the start of the string pool |
| data size | 2 | u16 | length of the string pool in bytes |
| string pool | data size | bytes | NUL-terminated strings; ends exactly at the end of the file |

C is the number of column names.

### Column names

Plain ASCII; in the shipped files every name is lower case and matches `[a-z0-9_]+`, and no table
repeats a name. There is always at least one column. The list must end with TAB NUL (the engine
counts columns by tokens and would read the row count's bytes as another name otherwise).

### Row labels

One label per row, in row order. A label is any text without TAB or NUL. Labels are normally the
row index in decimal (`0`, `1`, ...), but they don't have to be (Quirks): rows are addressed by
**index**, and labels are a second key some engine code uses (`weapondischarge.2da` is read by
label; `visualeffects.2da`'s labels are the `VFX_*` constants of `nwscript.nss`, `1001`, `1002`,
..., not row numbers).

### Cells and the string pool

Each cell is an offset into the pool; its value is the bytes from there to the next NUL. In the
shipped files:

- every distinct value is stored **once**, and all cells with that value share its offset
  (`appearance.2da` has 40 720 cells, 1 065 distinct values and a 14 429-byte pool);
- the pool lists the values in the order of their first use, scanning cells row-major;
- offsets always point at the start of a string (no suffix sharing), and every pool string is
  used;
- the **empty string is an ordinary value**: an empty cell points at a pool entry that is just a
  NUL. `****`, the text form's blank marker, never appears in a binary file;
- data size always equals the remaining file length.

A writer should do the same (dedupe, first-use order, empty string as a value) to reproduce
BioWare's files byte for byte. A reader must not depend on any of it except "offset < pool size,
NUL before the end of the pool". The u16 offsets cap the pool at 64 KB; the biggest in the game is
17 629 bytes (`globalcat.2da`).

Cell bytes in the shipped files are printable ASCII (no byte >= 0x80, no control characters, no
double quotes). One table has spaces inside cells (`soundprovider.2da`: `Creative Labs EAX (TM)`),
which the binary form allows.

## Reading it

What the engine does, which is also the rule to follow (addresses in Engine notes):

1. Check the 8-byte magic `2DA V2.b` (or `2DA V2.0`, then go to Text 2DA below).
2. Skip any run of LF, CR, space and TAB after the magic (in practice the single `\n`).
3. Column names: from here, repeatedly take bytes up to the next TAB or NUL as a name and step
   past that terminator; stop when the next byte is a NUL (the list's final NUL), and step past
   it. Accepting NUL as well as TAB as the name terminator is required (the `rims/` copies in
   Quirks), and costs nothing.
4. Row count: u32 at the current position.
5. Row labels: R times, take bytes up to the next TAB or NUL and step past the terminator.
6. Cell offsets: R·C u16 values. Then skip the u16 data size; the engine never reads it.
7. The pool is the rest of the file.

A reader that never trusts the data also checks that every offset is inside the pool and finds a
NUL before the pool's end; the probe below does, and every shipped file passes.

## Semantics

### Values

A 2DA stores strings only; the reader of a column decides whether it holds an integer, a float, a
resref, a strref or text. The engine's getters (by row index or row label, by column index or
column name) all return the value **and a "found" flag**:

| Getter | Cell is non-empty | Cell is empty (`""`) | Row or column out of range / unknown name |
|---|---|---|---|
| string | the text, found | `""`, not found | the table's default (below), not found |
| integer | `sscanf(cell, "%i")`, found | 0, not found | default as integer, not found |
| float | `sscanf(cell, "%f")`, found | 0.0, not found | default as float, not found |

- `%i` is C's integer conversion with base detection: `0x1f` is hexadecimal (the tables use
  `0x...` masks in `baseitems`, `classes`, `exptable`, `feat` and `spells`), a **leading `0`
  means octal** (`010` is 8), anything else decimal; it stops at the first character that
  doesn't fit and leaves 0 if nothing converts. The only cells with a leading zero are
  `weapondischarge.2da`'s `switchmask` (`01`, `0101`, `000111`, ...), and the engine reads that
  column as a string of per-shot digits, not as an integer. `exptable.2da` has `0xFFFFFFFF`, which
  reads as the 32-bit pattern 0xFFFFFFFF (-1 when signed).
- A non-numeric cell read as a number gives 0 but still reports "found".
- The default: binary tables have none, so it is `""` / 0 / 0.0.

Callers use the "found" flag to tell a blank (`****` in the designers' text) from a real `0`; our
reader must expose it (for example `?i32` / `?f32`, or an `is_blank` test).

### Lookups

- **Columns by name: ASCII case-insensitive**, first match wins. The files store lower-case
  names, but the engine asks for `Imp_HeadCon_Node` (visualeffects), `Name` (namefilter),
  `SwitchMask` (weapondischarge), `RESREF` and so on.
- **Rows by index**: 0 .. R-1, the normal case.
- **Rows by label**: ASCII case-insensitive comparison against the stored labels, first match
  wins (labels can repeat, see Quirks). The engine has a full set of getters keyed by row label
  (Engine notes); `weapondischarge.2da` is read that way (its `SwitchMask` by label and column
  name). Tables whose labels are names or ids (`droiddischarge`, `keymap`, `movies`,
  `visualeffects`, ...) are the candidates; which code uses which key is for the subsystem that
  reads the table to establish.
- Row and column indices out of range give the default with "not found", never an error.

### Maintenance rules (BioWare's)

Columns are only ever appended, rows only appended, and a dead row is filled with blanks rather
than removed, because rows are referenced by index from other data. `patch.erf` follows this:
`keymap.2da` gains column `eventtype` at the end and row `action265`; `bindablekeys.2da` grows
from 85 to 103 rows.

## Text 2DA (`2DA V2.0`)

No text 2DA exists anywhere in the install (all 519 copies are `2DA V2.b`; `Override/` is empty).
The engine still accepts one: the resource check takes `V2.b` or `V2.0` after `2DA `, and the
loader has a full text path. A player's `Override` may hold one, so **we support both**, the
text form as a lower-priority task (decision). BioWare's "2DA Format" document describes the text form;
what the engine actually does:

1. Line 1 is `2DA V2.0` (only the first 8 bytes are checked); skip it and any following blank
   lines (runs of CR, LF, space, TAB).
2. If the first token of the next line, upper-cased, is `DEFAULT:`, the next token is the
   table's default value; skip that line and blank lines. `DEFAULT` followed by `:value` or by a
   separate `:` and a value also sets the default, but the engine then does not move past that
   line, so it reads the column names from the `DEFAULT` line itself (a parser slip,
   [re/resources.md](../re/resources.md) 4; med, needs a runtime check). Without a `DEFAULT` token
   the line is the column-name line.
3. The next line holds the column names: whitespace-separated tokens (space or TAB), **lowered**
   to lower case.
4. Every following non-blank line is a row. Its first token is the row label (lowered to lower
   case; it is not checked against the row number). Then one token per column:
   - a token starting with `"` runs to the next `"` (so it can contain spaces; it cannot contain
     a quote);
   - `****` becomes the empty string (the blank);
   - if the line runs out of tokens, the remaining cells take the default value (or `""`);
   - extra tokens after the last column are ignored.
5. Lines end at LF or CR; tokens end at space, TAB, CR, LF or NUL.

Two differences from binary tables follow: text tables can have a default, and the integer getter
reads text cells with `atol` (decimal only, no octal) unless the cell starts with `0x`/`0X` and is
longer than 2 characters, in which case it is read as hex. Floats use `atof`. A text-table reader
should store blanks and missing cells the same way as binary empty cells so that the getters above
behave identically.

## Quirks in the shipped data

Counts are of copies (one table can appear three times: BIF and the two `rims/` RIMs).

- **NUL separators in `rims/` copies.** 13 tables in `rims/global.rim` and the same 13 in
  `rims/miniglobal.rim` (`appearance`, `appearancesndset`, `baseitems`, `bodybag`, `doortypes`,
  `genericdoors`, `heads`, `inventorysnds`, `placeableobjsnds`, `placeables`, `portraits`,
  `soundset`, `traps`) have every TAB after a column name and after a row label replaced by NUL;
  so the column list ends `name NUL NUL`. They are the same size as the BIF copies and, read with
  NUL accepted as a terminator (step 3 and 5 above), give exactly the same columns, labels and
  cells. They are images of the engine's own buffer after loading: the loader writes a NUL over
  each terminator in place (to use the names as C strings), and someone saved the result. The
  other 140 tables in those RIMs are byte-identical to the BIF's. The engine's own parser accepts
  both forms; so does ours, and the probe reports them as a quirk, not a failure.
- **Row labels that are not the row index** (20 tables in the BIF): numbered from 1
  (`categories`, `iprp_spellcost`, `stringtokens`, `visemes`), numbered by an id
  (`visualeffects`: 1001 ...; `combatanimations`: 87, 88, 94, ...; `weapondischarge`: 217, 218,
  ...), skipping or repeating a number part way (`ambientsound` skips `17`, `environment` skips
  `21`, `effecticon` skips `56` and later numbers, `iprp_resistcost` repeats `0`), or names
  (`bindablekeys`, `dialogtokens`, `droiddischarge`, `keymap`, `loadscreens`, `modulesave`,
  `movies`, `plot`, `swingsounds`).
- **Duplicate row labels**: `effecticon.2da` (label `63` three times) and `iprp_resistcost.2da`
  (`0` twice). Index lookups are unaffected; a label lookup finds the first.
- **Empty tables**: `iprp_base1`, `iprp_slotscost`, `iprp_staminacost`, `iprp_terraintype` have
  columns and 0 rows (the file is the column list, a zero count, no labels, no offsets, a zero
  data size and an empty pool: 27 or 32 bytes).
- **One-column and one-row tables** are common (`categories`, `namefilter`, `polymorph`, ...).
- **`patch.erf` copies differ in content**: `skills` (one description strref), `weapondischarge`
  (row 7 gets two shots), `keymap` (new column and row, changed bindings), `bindablekeys` (18 new
  rows, changed flags).
- **Mixed-case values that are resrefs** (`soundset.2da` has `c_KhoundA`, `n_jediMalek`):
  resref comparisons must ignore case.
- **Asterisks that are values.** `keymap.2da`'s `actionstrref` and `descstrref` hold `*****`
  (five asterisks) in 26 rows: a real, non-empty string, so the integer getter returns 0 *with*
  "found". `pazaakdecks.2da` cards like `*3` are pazaak card codes, and `doortypes.2da` labels
  contain `*` (`MineDoor1*MD`). Only the empty string is a blank in a binary 2DA.
- No table has duplicate column names, upper-case column names, `****` cells, bytes >= 0x80,
  trailing bytes after the pool, or a data-size field that disagrees with the file.

## Engine notes

From `swkotor.exe` (Steam build, unpacked; addresses as in `kotor/re/export`):

| Address | What |
|---|---|
| 0x41d790 | 2DA resource check: `2DA ` then `V2.b` (sets "binary") or `V2.0`; data passed on starts at byte 8 |
| 0x4143b0 | C2DA load: both forms; for binary, NULs over each name/label terminator, records u16 start offsets, pool = after offsets + 2 |
| 0x4137e0 | tokenizer: skips one leading NUL, then spaces/TABs; quoted tokens; stops at space, TAB, CR, LF, NUL |
| 0x413940 | skip runs of CR/LF/space/TAB |
| 0x413100 | column index by name: `_stricmp` (binary), case-insensitive compare (text); -1 if absent |
| 0x4138b0 | row index by label, same comparisons |
| 0x413190 / 0x413270 | string getter by (row, column index / name) |
| 0x413510 / 0x413660 | integer getter: binary `sscanf "%i"`; text `atol`, or `"%x"` after `0x` |
| 0x413350 / 0x413430 | float getter: binary `sscanf "%f"`; text `atof` |
| 0x413de0, 0x413ec0, 0x414110, 0x414260, 0x413fa0, 0x414080 | the same getters keyed by row label |

## Checked

`kotor/tools/py/tables_probe.py 2da` parses every 2DA copy that `kres.Game().every_entry('2da')`
yields (BIF, `patch.erf`, both `rims/` RIMs, Override and saves, which hold none) with the
reading rules above, checks every offset and string, compares the copies of each table, and
counts the quirks listed here.

```
python kotor/tools/py/tables_probe.py 2da            # summary, quirks, copy differences
python kotor/tools/py/tables_probe.py 2da --list     # plus a rows x columns table of every 2DA
python kotor/tools/py/tables_probe.py show NAME [N]  # print a table (copy N, default the BIF's)
```

Result (2026-10-03): 519 copies of 209 tables, **519 parsed, 0 failures**; 317 162 cells checked.
26 copies use NUL separators (the 13 `rims/` tables twice), and they decode to the same tables as
the BIF; the 4 `patch.erf` copies differ in content as listed.

## Sources

- BioWare, "2DA File Format" (Aurora engine documentation, text form, `****`, `DEFAULT:`, the
  maintenance rules): https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/2DA_Format.pdf
- Deadly Stream, "Editing offsets in binary 2DAs" (community description of `V2.b`):
  https://deadlystream.com/topic/5981-editing-offsets-in-binary-2das/
- `swkotor.exe` disassembly (addresses above) and the install's data.

## Appendix: every 2DA

Rows x columns of the BIF copy. `*` marks the 56 tables that exist only in `data/2da.bif` (not in
`rims/`). Regenerate with `tables_probe.py 2da --list`.

| Table | Rows x cols | Table | Rows x cols | Table | Rows x cols |
|---|---|---|---|---|---|
| acbonus | 21x6 | gamespyrooms * | 12x3 | loadscreens | 12x2 |
| actions * | 39x3 | gamma | 3x4 | masterfeats | 3x4 |
| aiscripts | 3x4 | gender | 5x4 | metamagic * | 7x4 |
| aliensound * | 299x2 | genericdoors | 65x10 | minglobalrim | 3x1 |
| ambientmusic | 49x5 | globalcat | 1185x2 | modulesave | 123x6 |
| ambientsound | 48x10 | grenadesnd | 31x2 | movies | 107x4 |
| ammunitiontypes | 6x10 | guisounds | 17x2 | namefilter | 3x1 |
| animations | 394x15 | heads | 107x7 | npc | 11x2 |
| appearance | 509x80 | hen_companion | 8x4 | nwconfig | 7x13 |
| appearancesndset | 16x9 | hen_familiar | 8x4 | nwconfig2 | 7x4 |
| areaeffects * | 3x9 | inventorysnds | 33x2 | pazaakdecks | 4x11 |
| baseitems | 92x61 | iprp_abilities | 6x2 | phenotype * | 3x2 |
| bindablekeys * | 85x3 (patch: 103x3) | iprp_acmodtype | 5x2 | placeableobjsnds | 70x7 |
| bodybag | 10x4 | iprp_aligngrp | 4x2 | placeables | 232x17 |
| caarmorclass * | 8x2 | iprp_alignment | 9x2 | placeabletypes * | 9x2 |
| camerastyle | 9x16 | iprp_ammocost | 16x6 | planetary | 17x6 |
| capart * | 18x3 | iprp_ammotype | 3x3 | plot | 75x2 |
| categories * | 15x1 | iprp_amount | 5x2 | poison | 6x14 |
| catype * | 5x2 | iprp_base1 | 0x3 | polymorph * | 1x16 |
| chargenclothes * | 8x1 | iprp_bladecost | 6x3 | portraits | 41x14 |
| classes | 9x49 | iprp_bonuscost | 11x4 | pregen * | 23x2 |
| classpowergain | 20x4 | iprp_chargecost | 19x5 | prioritygroups | 27x9 |
| cls_atk_1 | 20x1 | iprp_color | 7x2 | pvpsettings * | 4x3 |
| cls_atk_2 | 20x1 | iprp_combatdam | 3x2 | racialtypes | 7x22 |
| cls_atk_3 * | 60x1 | iprp_costtable | 26x3 | ranges | 21x4 |
| cls_spgn_jedi | 20x9 | iprp_damagecost | 11x7 | regeneration | 2x3 |
| cls_st_cm_drd | 20x4 | iprp_damagetype | 13x3 | removefxondeath | 2x2 |
| cls_st_ex_drd | 20x4 | iprp_damvulcost | 8x4 | repadjust | 4x12 |
| cls_st_jedi_c | 20x4 | iprp_feats | 21x4 | replacetexture * | 2x1 |
| cls_st_jedi_g | 20x4 | iprp_immuncost | 8x4 | repute | 21x21 |
| cls_st_jedi_s | 20x4 | iprp_immunity | 10x3 | rrf_nss * | 15x3 |
| cls_st_minion | 20x4 | iprp_lightcost | 5x3 | rrf_wav * | 19x3 |
| cls_st_scndrl | 20x4 | iprp_meleecost | 6x4 | rumble | 22x32 |
| cls_st_scout | 20x4 | iprp_monstcost | 58x5 | skills | 8x30 (patch: 8x30) |
| cls_st_soldier | 20x4 | iprp_monsterhit | 9x5 | skillvsitemcost * | 50x4 |
| combatanimations | 58x31 | iprp_neg10cost | 11x4 | soundcatfilters * | 14x2 |
| combatmodes * | 4x1 | iprp_neg5cost | 6x4 | sounddefaultspos * | 3x6 |
| comptypes | 2x2 | iprp_onhit | 11x4 | sounddefaultstim * | 5x8 |
| creaturesize * | 6x3 | iprp_onhitcost | 7x4 | soundeax * | 24x2 |
| creaturespeed | 12x5 | iprp_onhitdc | 5x3 | soundgain * | 15x4 |
| credits | 16x2 | iprp_onhitdur | 9x5 | soundprovider * | 5x4 |
| crtemplates * | 10x2 | iprp_paramtable | 12x3 | soundset | 90x5 |
| cursors | 11x3 | iprp_poison * | 6x2 | soundsettype | 5x2 |
| damagehitvisual | 13x3 | iprp_protection | 5x3 | soundtypes * | 2x2 |
| defaultacsounds * | 9x2 | iprp_redcost | 6x4 | spells | 132x53 |
| dialoganimations | 227x6 | iprp_resistcost | 7x4 | statescripts | 36x2 |
| dialogtokens * | 6x1 | iprp_saveelement | 19x3 | stringtokens * | 127x8 |
| difficultyopt | 4x3 | iprp_savingthrow | 4x2 | subrace * | 3x1 |
| diffsettings | 6x6 | iprp_slotscost | 0x2 | surfacemat | 31x7 |
| disease | 17x17 | iprp_soakcost | 7x4 | swingsounds * | 9x3 |
| domains * | 22x15 | iprp_spellcost | 188x4 | texpacks * | 3x6 |
| doortypes | 69x8 | iprp_spelllvcost | 10x3 | tilecolor * | 16x3 |
| droiddischarge | 15x3 | iprp_spelllvlimm | 10x3 | traps | 14x11 |
| effectanim * | 1x2 | iprp_spells * | 336x10 | treasurescale * | 5x3 |
| effecticon | 62x5 | iprp_spellshl * | 8x4 | tutorial | 43x5 |
| effecticons * | 107x3 | iprp_srcost | 12x4 | tutorial_old * | 42x5 |
| encdifficulty | 5x3 | iprp_staminacost | 0x3 | upcrystals | 7x5 |
| encumbrance * | 51x2 | iprp_terraintype * | 0x2 | upgrade | 25x3 |
| environment * | 24x42 | iprp_trapcost | 12x3 | upgradetypes | 10x1 |
| excitedduration | 3x2 | iprp_traps * | 4x3 | vfx_persistent | 3x30 |
| exptable | 21x2 | iprp_walk | 2x2 | videoeffects | 3x7 |
| feat | 125x60 | iprp_weightcost | 6x4 | videoquality * | 9x5 |
| featgain | 20x17 | iprp_weightinc | 6x3 | visemes * | 16x3 |
| feedbacktext | 3x2 | itempropdef | 60x8 | visualeffects | 144x29 |
| footstepsounds | 11x35 | itemprops | 60x27 | waypoint * | 5x3 |
| forceadjust | 11x2 | itemvalue | 60x4 | weapondischarge | 64x16 (patch: 64x16) |
| forceshields | 19x20 | keymap * | 79x22 (patch: 80x23) | weaponsounds | 4x29 |
| formations | 3x21 | lightcolor | 32x7 | xpbaseconst * | 17x3 |
| fractionalcr | 5x4 | loadhints * | 28x3 | xptable | 20x22 |
| gameeffects | 25x34 | loadscreenhints | 91x2 |  |  |
