# TLK talk table (`TLK V3.0`)

The talk table holds every piece of player-visible text in the game's language, plus, per string,
the voice-over sound to play with it. Everything else refers to text by **StrRef**, an index into
this table: 2DA cells, GFF `CExoLocString`s ([gff.md](gff.md)), SSF sound sets ([ssf.md](ssf.md)),
scripts (`GetStringByStrRef`). Translating the game means swapping this one file.

All integers are little-endian.

## Where

| What | Value |
|---|---|
| Resource type | `tlk`, id 2018 ([resource-types.md](resource-types.md)) |
| File | `dialog.tlk` in the install root, 5 394 446 bytes. Not in any BIF, ERF or RIM; opened by path (`HD0:dialog`, HD0 = the install directory) |
| Feminine table | `dialogf.tlk` beside it, if present. The English install has none |
| Other copies | none (`Override/` is empty, no container holds a `tlk`) |

## Layout

```
0                     header (20 bytes)
20                    entry table: StringCount x 40 bytes
StringEntriesOffset   string data: the texts, back to back, no terminators
```

### Header (20 bytes)

| Offset | Size | Type | Field | Value in `dialog.tlk` |
|---|---|---|---|---|
| 0 | 4 | char[4] | file type | `TLK ` |
| 4 | 4 | char[4] | version | `V3.0` |
| 8 | 4 | u32 | LanguageID | 0 (English); table below |
| 12 | 4 | u32 | StringCount | 49 265 |
| 16 | 4 | u32 | StringEntriesOffset | 1 970 620 = 20 + 40 x StringCount |

### Entry (40 bytes; entry i is StrRef i, at 20 + 40·i)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | Flags | bits below |
| 4 | 16 | char[16] | SoundResRef | voice-over WAV resref, NUL-padded; a 16-character name has **no NUL** (26 912 entries) |
| 20 | 4 | u32 | VolumeVariance | unused; 0 everywhere |
| 24 | 4 | u32 | PitchVariance | unused; 0 everywhere |
| 28 | 4 | u32 | OffsetToString | from StringEntriesOffset |
| 32 | 4 | u32 | StringSize | bytes, no terminator stored |
| 36 | 4 | f32 | SoundLength | seconds; **0.0 in every entry** of `dialog.tlk` |

### Flags

| Bit | Name | Meaning |
|---|---|---|
| 0x0001 | TEXT_PRESENT | the entry has text at OffsetToString/StringSize; clear means the text is `""` |
| 0x0002 | SND_PRESENT | SoundResRef is meaningful; clear means no sound |
| 0x0004 | SNDLENGTH_PRESENT | SoundLength is meaningful; clear means 0.0 |
| 0x8000 | (absent) | KOTOR: the engine treats the entry as **not in this table** (see Lookup) |

Combinations in `dialog.tlk`:

| Flags | Entries | What they are |
|---|---|---|
| 0x0007 | 48 560 | text; SoundResRef set in 32 494, empty in 16 066 (so the sound bit says nothing: test the resref) |
| 0x0006 | 398 | no text; 359 with a SoundResRef (VO with no subtitle), 39 with none |
| 0x8000 | 307 | everything else zero: holes in the numbering (StrRef 369, 374, ... up to 49 248) |

Bits 0x0002 and 0x0004 are set on every non-hole entry regardless of content, and SoundLength is
never filled in, so a reader takes "has sound" from a non-empty resref and gets sound lengths from
the WAV files. (Probably `GetStrRefSoundDuration` therefore returns 0.0 for every StrRef in the
original game; whoever implements that routine should confirm against the engine.)

### String data

The texts are stored back to back in StrRef order with no gaps, no overlaps, no sharing and no
padding; the last one ends exactly at the end of the file. Entries without text have offset 0 and
size 0. Readers use the offset and size and need none of this.

## Text

- **Encoding.** The engine handles text as single bytes and fetches no code page from the file.
  `dialog.tlk` (English) uses only LF (0x0A) and printable ASCII 0x20-0x7E. Other languages use
  their Windows code page: 1252 for English/French/German/Italian/Spanish, and 1250 for Polish
  (the engine calls `setlocale(LC_CTYPE, "Polish_Poland.1250")` when the table's language is 5).
  Decision: our reader returns raw bytes, and the text layer converts with the code page chosen by
  LanguageID (0-4: cp1252, 5: cp1250).
- **Line breaks** are a bare LF (2 017 strings have one); there is no CR in the file.
- **Tokens.** Text may contain `<...>` tokens that are replaced when the string is fetched for
  display: `<CUSTOMn>` (values set by scripts with `SetCustomToken`), named tokens from
  `stringtokens.2da` (`<FullName>`, `<FirstName>`, `<man/woman>`, `<sir/madam>`, `<Class>`, ...),
  and controller-button glyphs from `dialogtokens.2da` (`<abutton>`, ...). `<<` stands for a
  literal `<`, and an unknown token becomes the literal text `<UNRECOGNIZED TOKEN>`. 75 distinct
  tokens occur in `dialog.tlk`. Some are stage directions inside voice-over text (`<Sigh>`,
  `<snore>`, `<Pause>`). Token replacement belongs to the text layer, not the reader.
- StrRef 0 is the text `Bad StrRef`. Many low StrRefs are script-compiler error messages.

## Language IDs

LanguageID in the header says which language the table is in; the engine stores it as the game's
language. CExoLocString substrings carry a combined id = LanguageID x 2 + gender (0 masculine or
neutral, 1 feminine), see [gff.md](gff.md).

| ID | Language |
|---|---|
| 0 | English |
| 1 | French |
| 2 | German |
| 3 | Italian |
| 4 | Spanish |
| 5 | Polish |
| 128 | Korean |
| 129 | Chinese, Traditional |
| 130 | Chinese, Simplified |
| 131 | Japanese |

This is BioWare's Aurora table. KOTOR's executable special-cases 5 (Polish code page) and also
switches on an extra text subsystem when the id is 1000 or more (purpose not identified; perhaps an
Asian-language build). The 1xx ids are unconfirmed for KOTOR.

## Lookup (StrRef semantics)

The engine keeps a talk-table object with up to seven slots, each a masculine and a feminine
table. Slot 0 is `dialog.tlk` / `dialogf.tlk`; slots 1-6 are for Xbox Live content
(`LIVEn:liven.tlk`), which the PC install doesn't have. Opening a slot opens `NAME.tlk`, checks the 4-byte `TLK `, then opens
`NAMEf.tlk` (the name with `F` appended) for the feminine side; if that fails, the feminine side
is the masculine table. To fetch StrRef `s` for gender `g`:

1. `s = 0xFFFFFFFF`: the invalid StrRef. Result: empty text, no sound, success.
2. Otherwise `s &= 0x00FFFFFF`. KOTOR has **no** "alternate table" bit: unlike NWN's convention
   (0x01000000 selects a module's custom table), the top byte is simply dropped.
3. For each slot in order, take its table for gender `g`; skip it if absent. If `s < StringCount`
   and the entry's Flags lack 0x8000, this entry is the answer: text (if TEXT_PRESENT, else `""`),
   sound resref (if SND_PRESENT), length (if SNDLENGTH_PRESENT). Success.
4. If no slot had it and `g` is feminine, try again with `g` = masculine.
5. Otherwise: empty text, no sound, **not found**.

The answer's text is then token-replaced (Text, above) when the caller asks for it. With only
`dialog.tlk` this reduces to: valid if `s & 0xFFFFFF < 49 265` and the entry is not a 0x8000 hole.

Version: the engine checks only the 4-byte `TLK ` when opening and reads 40-byte entries if the
version is `V3.0`, 36-byte entries (no SoundLength) otherwise. Decision: our reader accepts `V3.0`
only and reports anything else as an error; no such file exists for KOTOR.

Robustness: the engine bounds-checks StrRef and the start of the text (a text starting past the end
of the file comes back as the StrRef's decimal number, and the fetch counts as **failed**, with no
retry in the next slot or with the masculine table) but not its end. When a slot's feminine file
opens but fails the `TLK ` check, both of the slot's files are closed and the slot fails
([re/resources.md](../re/resources.md) 5). Our reader checks both and
treats a bad entry as an error value.

## Engine notes

`swkotor.exe` (Steam, unpacked):

| Address | What |
|---|---|
| 0x41d8d0 | talk-table object constructor (0x58 bytes; global pointer at 0x7a3a08) |
| 0x41d920 | open slot (0..7): `NAME` and `NAME` + `F`, type 2018 |
| 0x41d890 | read the 20-byte header, require `TLK ` |
| 0x41e5a0 | open `HD0:dialog` into slot 0, then load `stringtokens.2da` into the token table |
| 0x41e1a0 | fetch: the lookup above; entry size 40 for `V3.0` else 36 |
| 0x41e550 | fetch for a gender; if a debug flag (+0x54) is set, prefixes `[strref]` to the text |
| 0x41dd30 | token replacement (`<<`, `<CUSTOMn>`, named tokens, `<UNRECOGNIZED TOKEN>`) |
| 0x41e0f0 | language id of slot 0's masculine table (used at 0x5f8550) |
| 0x5f4180 | Xbox Live content: `LIVEn:liven` tables into slots 1-6 |

## Checked

`kotor/tools/py/tables_probe.py tlk` reads every `.tlk` in the install root (and would report any
`tlk` resource in a container; there are none) and checks the header, that the entry table ends at
StringEntriesOffset, every entry's flags, resref, variances and length, that every text lies inside
the file and decodes as cp1252, and how the string data is laid out; it counts flag combinations,
line breaks, bytes >= 0x80 and `<tokens>`.

```
python kotor/tools/py/tables_probe.py tlk [PATH] [-v]
```

Result (2026-10-03): `dialog.tlk`, 49 265 entries, **0 failures**. 48 560 texts (3 423 826 bytes,
longest 7 531), all inside the file, ASCII only. Flag combinations, empty resrefs, the 307 holes and
the all-zero SoundLength as described above.

## Sources

- BioWare, "Talk Table (dialog.tlk) File Format" (header, entry, flags, language ids, StrRef
  rules, dialogf.tlk): https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/TalkTable_Format.pdf
- BioWare, "Localized Strings" (language ids, language x 2 + gender):
  https://github.com/xoreos/xoreos-docs/blob/master/specs/bioware/LocalizedStrings_Format.pdf
- `swkotor.exe` disassembly (addresses above) and `dialog.tlk` itself.
