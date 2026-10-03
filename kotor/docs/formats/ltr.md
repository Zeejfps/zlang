# LTR letter tables (`LTR V1.0`)

An LTR file is a third-order Markov model of names: for every one-, two- and three-letter context
it gives the cumulative probabilities of the next letter at the start, in the middle and at the
end of a name. The game uses it for the random-name button in character creation: one table for
male first names, one for female first names, one for last names.

All numbers are little-endian; probabilities are IEEE f32.

## Where

| What | Value |
|---|---|
| Resource type | `ltr`, id 2036 ([resource-types.md](resource-types.md)) |
| `data/templates.bif` | `humanm.ltr` (male first names), `humanf.ltr` (female first names), `humanl.ltr` (last names); 273 177 bytes each |
| anywhere else | nothing |

The engine builds the resref as race name + `m`/`f`/`l` (`human`, and NWN's `dwarf`, `elf`,
`gnome`, `halfling`, `halforc`, `animal`, which KOTOR doesn't ship).

## Layout

```
0     "LTR V1.0"            8 bytes
8     N                     u8, letter count: 28
9     singles               1 block
      doubles               N blocks, for first letter a = 0..N-1
      triples               N x N blocks, for letters a, b (b varies fastest)
```

A **block** is three arrays of N f32, in this order:

| Offset in block | Size | Array | Meaning |
|---|---|---|---|
| 0 | 4·N | start | cumulative probability of the next letter when it begins a name |
| 4·N | 4·N | middle | ... when it is inside a name |
| 8·N | 4·N | end | ... when it ends the name |

So the block for context `x` starts at 9 + 12·N·k with k = 0 for singles, 1 + a for doubles `a`,
1 + N + a·N + b for triples `ab`. File size = 9 + 12·N·(1 + N + N²) = 273 177 for N = 28.

**Alphabet** (index to character): 0-25 = `a`-`z`, 26 = `'`, 27 = `-`. The engine allocates its
arrays from N, so other counts are legal, but every KOTOR file has 28.

**Values.** Within an array, entry i holds the running total of the probabilities of letters
0..i, but a letter that never occurs holds **0.0** rather than repeating the running total. Picking
a letter with a uniform roll `p` in [0, 1]: the first i with `p < value[i]`. Zeros never match
(p >= 0), so this is a correct inverse-CDF draw. An array of all zeros (a context never seen in the
training names) matches nothing: a dead end. The last non-zero value of a used array is 1.0 (within
float rounding).

## The generator

What the engine does (address 0x711390), with `roll()` = `rand() / 32767.0` (MSVC `rand`, 15 bits)
and "pick(array)" as above:

1. a = pick(singles.start); b = pick(doubles[a].start); c = pick(triples[a][b].start). If any
   pick fails, start this step again (no limit). The name is now `abc`.
2. Loop, with x, y = the last two letters:
   - p = roll(); r = rand() % 12.
   - If r <= length of the name (or the caller's maximum length minus one is reached): try to
     end: k = pick(triples[x][y].end) with p. If found, append k and finish. If not, count a
     failure and restart from step 1.
   - Otherwise: k = pick(triples[x][y].middle) with the same p. If found, append k and loop. If
     not and the name has more than 3 letters, drop the last letter and loop; with 3 letters,
     count a failure and restart from step 1.
   - After 5 failures, give up and return an empty name.
3. Upper-case the first letter (`toupper`; `'` and `-` stay).
4. Compare the whole name, ignoring case, with every row of `namefilter.2da` column `name`
   (`anal`, `cock`, `urine`); on a match generate a new name from scratch.

Names therefore have at least 4 letters; from 11 letters on an end is tried on every step. A full
name is a first name (`humanm`/`humanf`) and a last name (`humanl`) joined by a space, generated
separately.

The generator reads only singles.start, doubles[*].start and triples[*][*].start/middle/end.
**singles.middle, singles.end and the doubles' middle and end arrays are never read**, which
matters because of the first quirk below.

## Quirks

- **singles.middle and singles.end are not cumulative** in all three files: after each zero entry
  the running total restarts (BioWare's builder reset its accumulator on letters with no
  occurrences, as the `nwnltr` tool notes for NWN's files). Harmless, since the engine never reads
  them; a tool that prints or rebuilds LTRs must not "fix" anything else.
- Used arrays per file (start / middle / end, out of 813 blocks): `humanf` 67 / 86 / 64,
  `humanl` 53 / 90 / 49, `humanm` 72 / 77 / 76; the rest are all zero.
- Every value is in [0, 1]; no NaN.

## Engine notes

`swkotor.exe` (Steam, unpacked):

| Address | What |
|---|---|
| 0x712410 | LTR load: checks `LTR ` and `V1.0`, reads N from byte 8, copies the arrays |
| 0x711390 | generate one name (above); argument: maximum length, 0 = none |
| 0x7118c0 | random full name: race index to `human`/`elf`/... (NWN racial types; -1 = `animal`), flags 1/2/4 = `m`/`f`/`l`, first + " " + last |

## Checked

`kotor/tools/py/tables_probe.py ltr` reads every LTR copy, checks magic, letter count and exact
size, that every value is in [0, 1], and for each array whether it is all zero, cumulative and ends
at 1.0. With `--names N` it also runs the generator above (Python, seeded) and prints N names per
file.

```
python kotor/tools/py/tables_probe.py ltr [--names 12]
```

Result (2026-10-03): 3 files, **0 failures**; in each, exactly two arrays are not cumulative
(singles.middle, singles.end), every other used array is cumulative and ends at 1.0. Sample
output includes `Gabai, Ahsana, Vila, Liah, Polli` (humanf), `Dando, Quich, Dendon, Brogus, Kale`
(humanm), `Bailum, Tantra, Organa, Mothma, Kast` (humanl).

## Sources

- nwn.wiki, "LTR" (NWN community page; the generator as described by Lord Nightmare: three start
  letters, 1-in-12 end roll, name filter): https://nwn.wiki/spaces/NWN1/pages/38176121/LTR
- mtijanic, `nwnltr.c` (WTFPL; NWN LTR tool documenting the layout and the singles bug; read,
  not copied): https://github.com/mtijanic/nwn-misc/blob/master/nwnltr.c
- `swkotor.exe` disassembly (addresses above), `namefilter.2da`, the three LTR files.
