# SSF sound set (`SSF V1.1`)

A sound set lists the barks a creature makes on fixed occasions: battle cries, "selected"
acknowledgements, attack and pain grunts, death, low health, mine, stealth, lock and party
remarks. KOTOR's SSF is a plain array of **StrRefs**; the sound itself is the voice-over resref
that `dialog.tlk` stores with each StrRef, and the text is that StrRef's text ([tlk.md](tlk.md)).
NWN's `SSF V1.0` paired each entry with its own WAV resref; KOTOR's `V1.1` drops that.

All integers are little-endian.

## Where

| What | Value |
|---|---|
| Resource type | `ssf`, id 2060 ([resource-types.md](resource-types.md)) |
| `data/templates.bif` | 106 sound sets |
| `rims/global.rim`, `rims/miniglobal.rim` | 105 each, byte-identical to the BIF copies |
| `Override/`, modules, saves | none |

How a creature gets one: its UTC field `SoundSetFile` is a row of `soundset.2da`, whose `resref`
column names the SSF (see [gff-templates.md](gff-templates.md)). `soundset.2da` has 90 rows (row 0
`None` is blank) naming 89 SSFs, all present. 17 SSFs are named by no row: `c_ithorian`,
`c_sebulba`, `n_darth_revan`, `n_drdmk4`, `n_drdprotocol`, `n_drdturt`, `n_drdwar`,
`p_malesoldier`, `p_trask`, and the eight NWN-layout files below.

## Layout

| Offset | Size | Type | Field | Value in the install |
|---|---|---|---|---|
| 0 | 4 | char[4] | file type | `SSF ` |
| 4 | 4 | char[4] | version | `V1.1` |
| 8 | 4 | u32 | offset of the StrRef table | 12 in every file |
| 12 | 4·N | u32[N] | StrRefs, one per slot | 0xFFFFFFFF = nothing |

There is no count: N = (file size - table offset) / 4. 98 files (292 copies) have **N = 40**
(172 bytes); 8 files (24 copies) have N = 49 (208 bytes, see Quirks).

## Slots

The engine reads a slot by a 1-based index `k` from 1 to 28, as `u32` at `table offset + 4·(k-1)`,
rejects `k = 0` and `k >= 29`, treats 0xFFFFFFFF as "no bark", and otherwise fetches the StrRef
from the talk table for the current gender (text, and the sound resref to play). It never checks
the magic, the version or the file size. So only the first 28 entries mean anything; entries
28-39 (0-based) are padding, all 0xFFFFFFFF except entry 33 in `c_terantank` and `n_ithorian`
(a stray "select" StrRef, never read).

The slot meanings below are not written down in the game's scripts (KOTOR's `nwscript.nss` has no
soundset constants). They come from the data: for each slot, the voice-over resrefs `dialog.tlk`
gives its StrRefs end in the same suffix in almost every sound set (`p_bastila_bat1`,
`p_bastila_slct1`, `p_bastila_atk1`, `p_bastila_hit1`, `p_bastila_low`, `p_bastila_dead`, ...;
986 of the 1 061 filled slots in `templates.bif` agree), and the texts match (Bastila, slot 17:
"I am doing no damage!").

| Entry (0-based) | Engine k | Slot | VO suffix |
|---|---|---|---|
| 0-5 | 1-6 | battle cry 1-6 | `bat1`..`bat6` |
| 6-8 | 7-9 | selected 1-3 | `slct1`..`slct3` |
| 9-11 | 10-12 | attack grunt 1-3 | `atk1`..`atk3` |
| 12-13 | 13-14 | pain grunt 1-2 | `hit1`, `hit2` |
| 14 | 15 | low health | `low` |
| 15 | 16 | dead | `dead` |
| 16 | 17 | critical hit | `crit` |
| 17 | 18 | target immune | `tia` |
| 18 | 19 | lay mine | `lmin` |
| 19 | 20 | disarm mine | `dmin` |
| 20 | 21 | begin stealth | `stlh` |
| 21 | 22 | begin search | `srch` |
| 22 | 23 | begin unlock | `block` |
| 23 | 24 | unlock failed | `flock` |
| 24 | 25 | unlock success | `slock` |
| 25 | 26 | separated from party | `sprty` |
| 26 | 27 | rejoined party | `rprty` |
| 27 | 28 | poisoned | `pois` |
| 28-39 | - | unused | |

Which of these the engine plays when (and how it picks among battle cries 1-6 or grunts 1-3) is
for the combat and party code to work out from the executable; the call site found so far passes
the slot through from its caller (Engine notes).

Monsters fill only some slots (a `c_` creature typically has battle cries 1-3, attack and pain
grunts and `dead`); party members and the player sets fill all or nearly all 28.

## Quirks

- **NWN-layout files.** `darkjedi`, `drdassassin`, `drdmkone`, `drdprobe`, `katarn`, `kinrath`,
  `player`, `sithtroop` have 49 entries, all 0xFFFFFFFF except entry 18, whose StrRef is a
  "... Death Sound" text (`DarkJedi_die`). 49 entries with "Death" 19th is NWN's sound-set layout.
  No `soundset.2da` row names them; read as KOTOR sets they are silent.
- **Shifted or mismatched slots** (shipped data, to be reproduced as-is): `p_playermb` and
  `p_zaalbar` are off by one from slot 5 or so (Zaalbar's "dead" slot plays `p_zaalbar_crit`);
  `c_gammorean` has three slots swapped; `n_ithorian`, `n_commm`, `n_commkidm` reuse one StrRef
  for several slots; `p_t3m4`'s slot 25 StrRef carries `p_t3m3_slock`.
- **Text without sound.** `n_trandoshan` and `p_trask` have StrRefs whose `dialog.tlk` entries
  have no sound resref, so they would show text only.
- Every StrRef in every file is either 0xFFFFFFFF or below `dialog.tlk`'s 49 265.

## Engine notes

`swkotor.exe` (Steam, unpacked):

| Address | What |
|---|---|
| 0x6db650 | SSF resource object constructor; its "loaded" check (0x6db690) only tests for data |
| 0x6789a0 | load a sound set by resref (type 2060) into a holder |
| 0x678820 | read slot k (1..28): StrRef at `[data + 8] + 4(k-1)`; -1 means none; fetch from the talk table with the current gender |
| 0x60b8a0 | creature wrapper: if the creature has a sound set, read slot k (k from the caller) |

## Checked

`kotor/tools/py/tables_probe.py ssf` reads every SSF copy (`every_entry('ssf')`: BIF, both `rims/`
RIMs, Override and saves), checks magic, version, table offset, that the table fills the rest of
the file, and that every StrRef is 0xFFFFFFFF or a valid `dialog.tlk` index; counts filled slots;
compares copies; checks the slot meanings against the `dialog.tlk` voice-over suffixes; and
compares the set of SSFs with `soundset.2da`.

```
python kotor/tools/py/tables_probe.py ssf [-v]
```

Result (2026-10-03): 316 copies of 106 sound sets, **0 failures**; all copies of a name identical;
1 061 filled KOTOR slots in `templates.bif`, 986 matching the suffix table above, the 75 others in
the sets listed under Quirks.

## Sources

- BioWare, "Sound Set File (SSF) Format" (NWN's `V1.0`: header with count and table offset,
  16-char resref + StrRef per entry, 49 slots):
  https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/SSF_Format.pdf
- `swkotor.exe` disassembly (addresses above), `soundset.2da`, `dialog.tlk`, the SSFs themselves.
