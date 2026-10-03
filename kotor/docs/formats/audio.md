# Audio: WAV (PCM, IMA ADPCM), MP3, and the two KOTOR wrappers

Every sound KOTOR plays is named `.wav` (resource type 4), but the bytes come in five kinds. Two
of them are KOTOR-specific wrappers around ordinary formats:

| Class (probe name) | What the bytes are | Count | Where |
|---|---|---|---|
| `riffstub/mp3` | a fixed 58-byte RIFF/WAVE header that claims an empty 8-bit PCM file, followed by an MPEG-1 Layer III stream | 13,867 | all of `streamwaves/` (13,799), 68 of `streammusic/` |
| `none/pcm` | an ordinary RIFF/WAVE file, PCM | 2,295 | WAV resources in `data/sounds.bif` (1,924), `rims/global.rim` (242), `rims/miniglobal.rim` (129) |
| `mp3pad/pcm` | 470 bytes of silent MPEG-2 frames, then an ordinary RIFF/WAVE PCM file | 976 | all of `streamsounds/` (970), 4 of `streammusic/`, `launcher/` (2) |
| `mp3pad/ima-adpcm` | the same 470 bytes, then a RIFF/WAVE IMA ADPCM file | 47 | 47 of `streammusic/` |
| `none/ima-adpcm` | an ordinary RIFF/WAVE file, IMA ADPCM | 8 | 4 blaster shots in `data/sounds.bif`, copied in `rims/global.rim` |

Nothing else occurs: no raw MP3 without a wrapper, no MP3 inside RIFF (format tag 0x55), no
Microsoft ADPCM (tag 0x02), no `.mp3` file, no WAV in `modules/`, `lips/`, the texture packs,
`patch.erf`, `Override/` or the saves. Movies carry their own Bink audio (see the Bink doc).

So the decoders the game needs are exactly: **PCM** (16-bit, plus one 8-bit file), **IMA ADPCM**
(Microsoft's block layout), and **MPEG-1 Layer III** (mono 32 kHz and joint-stereo 44.1 kHz,
CBR). All integers in RIFF are little-endian; all MPEG fields are big-endian bit fields.

## Detecting the kind

Apply these tests in this order to the whole file or resource (`d`, length `n`). Every input in
the install lands in exactly one of them; the probe checks this (0 unclassified).

1. **mp3pad.** `n >= 482` and `d[0..4] == FF F3 60 C4` and `d[470..474] == "RIFF"` and
   `d[478..482] == "WAVE"` → drop the first 470 bytes and continue at step 2 with `d[470..]`.
   (Must come before step 4: the file starts with a valid MPEG sync.) A more general form that
   accepts any such prefix: walk MPEG frame headers from offset 0 by their frame lengths; if a
   frame boundary lands on `RIFF....WAVE`, the RIFF file starts there. In KOTOR that boundary is
   always 470, after 3 frames.
2. **RIFF.** `d[0..4] == "RIFF"` and `d[8..12] == "WAVE"`. Walk the chunks (below) and find `fmt `
   and `data`.
   - **riffstub:** the `data` chunk's size is 0 **and** bytes follow it (the RIFF size field + 8
     is less than `n`) **and** those bytes start with an MPEG sync (`FF`, then a byte with its top
     three bits set) or `ID3` → an MP3 stream runs from the end of the `data` chunk header
     (always offset 58) to the end of the file. Ignore everything the header's `fmt ` says.
     (Fast form for KOTOR: the first 58 bytes equal the stub below; equivalently RIFF size == 50
     and `d[50..58] == "data" 00 00 00 00`.)
   - otherwise dispatch on the `fmt ` format tag: 1 → PCM, 0x11 → IMA ADPCM. Anything else is an
     error (never occurs).
3. (Never reached in KOTOR.) Bytes that are not RIFF after an mp3pad prefix → error.
4. **Raw MP3** (never occurs, cheap to allow for Override files): `d[0..3] == "ID3"`, or an MPEG
   sync at 0 whose frame is followed by another valid header → MP3 from offset 0.
5. Anything else → error value, not a panic.

## The 58-byte RIFF stub (`riffstub`)

All 13,867 stubs are byte-identical:

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | `52 49 46 46` | `RIFF` |
| 4 | `32 00 00 00` | RIFF size 50: the RIFF "file" ends at byte 58 |
| 8 | `57 41 56 45` | `WAVE` |
| 12 | `66 6D 74 20` `12 00 00 00` | `fmt ` chunk, 18 bytes |
| 20 | `01 00` | format tag 1 (PCM) -- a lie |
| 22 | `01 00` | 1 channel -- a lie for the 68 stereo music files |
| 24 | `22 56 00 00` | 22,050 Hz -- a lie (the MPEG data is 32 or 44.1 kHz) |
| 28 | `22 56 00 00` | 22,050 bytes/s |
| 32 | `01 00` | block align 1 |
| 34 | `08 00` | 8 bits per sample |
| 36 | `00 00` | cbSize 0 |
| 38 | `66 61 63 74` `04 00 00 00` `00 00 00 00` | `fact` chunk, 4 bytes, value 0 |
| 50 | `64 61 74 61` `00 00 00 00` | `data` chunk, size 0 |
| 58 | ... | the MPEG stream, to the end of the file |

A RIFF reader that trusts the header plays nothing (0 bytes of 8-bit PCM) and finds the MP3 as
trailing junk after the RIFF's declared end. The real format is in the MPEG frame headers.

## The 470-byte MPEG prefix (`mp3pad`)

All 1,023 prefixes are byte-identical. They are three complete, silent MPEG frames:

| Offset | Length | Header | Contents |
|---|---|---|---|
| 0 | 156 | `FF F3 60 C4` | MPEG-2 Layer III, no CRC, 48 kbit/s, 22,050 Hz, no padding, mono, original |
| 156 | 157 | `FF F3 62 C4` | the same with the padding bit set |
| 313 | 157 | `FF F3 62 C4` | the same with the padding bit set |
| 470 | rest | `RIFF` | an ordinary RIFF/WAVE file whose RIFF size + 8 is exactly `n - 470` |

Their side information says every granule is empty (part2_3_length 0, big_values 0, global_gain
210); main_data_begin is 0, 143 and 255. The frame bodies are LAME's ancillary filler: the text
`LAME3.93` and bytes `0x55`. Decoded, the prefix would be 3 × 576 = 1,728 samples (78 ms) of
silence at 22,050 Hz; skip it instead. Why BioWare prepended it is unknown (see Open questions).

## RIFF/WAVE

```
0   "RIFF"
4   u32 RIFF size = byte length of everything after this field
8   "WAVE"
12  chunks, to RIFF size + 8:
      4 bytes  chunk id (ASCII)
      u32      chunk body size (not counting this 8-byte chunk header)
      body
      one pad byte if the body size is odd
```

Observed in every real RIFF (3,326 of them: PCM, IMA, and the RIFFs after an mp3pad prefix):
RIFF size + 8 equals the file length exactly; `fmt ` is always the first chunk; no chunk has an
odd size (so no pad bytes occur, but a reader should still honour them). Chunk orders seen:

| Chunks | Count |
|---|---|
| `fmt`, `data` | 3,117 |
| `fmt`, `data`, `LIST` | 132 |
| `fmt`, `fact`, `data` | 63 (53 IMA, 10 PCM) |
| `fmt`, `data`, `LIST`, `cue`, `LIST` | 5 |
| `fmt`, `fact`, `data`, `LIST` | 2 |
| `fmt`, `data`, `smpl` | 2 |
| `fmt`, `data`, `LIST`, `acid` | 2 |
| `fmt`, `data`, `LIST`, `smpl` | 2 |
| `fmt`, `data`, `cue`, `LIST` | 1 |

(`fact` appears in all 55 IMA files and in 10 PCM files inside `streamsounds/`.) Chunks after
`data` are editor metadata (LIST/INFO, cue points, sampler loops, Acidizer); a reader takes `fmt `
and `data` and skips every other chunk by its size. Whether the engine honours `smpl`/`cue` loop
points is unknown; nothing suggests it.

### `fmt ` (WAVEFORMATEX)

| Offset | Size | Field |
|---|---|---|
| 0 | u16 | format tag: 1 PCM, 0x11 IMA ADPCM |
| 2 | u16 | channels |
| 4 | u32 | sample rate (Hz) |
| 8 | u32 | average bytes per second (informational) |
| 12 | u16 | block align: bytes per sample frame (PCM) or per ADPCM block |
| 14 | u16 | bits per sample (4 for IMA ADPCM) |
| 16 | u16 | cbSize: bytes of extra format data that follow (absent when the chunk is 16 bytes) |
| 18 | ... | extra data; for IMA ADPCM a u16 samples-per-block |

PCM `fmt ` chunks are 16 bytes (3,261) or 18 bytes with cbSize 0 (10, in `streamsounds/`). IMA
`fmt ` chunks are 20 bytes with cbSize 2.

## PCM

Interleaved sample frames (left then right for stereo), `block align = channels × bits / 8`,
byte rate = rate × block align (both hold in every file). 16-bit samples are signed
little-endian; 8-bit samples are unsigned with 128 as silence. Duration = data size / block
align / rate. Data sizes are always whole sample frames and never 0.

| Channels | Rate | Bits | Count | Where |
|---|---|---|---|---|
| 1 | 22,050 | 16 | 2,192 + 949 | most BIF/RIM effects; `streamsounds/` |
| 1 | 44,100 | 16 | 84 + 4 | BIF/RIM; `streamsounds/` |
| 1 | 11,025 | 16 | 9 | `fs_dirt_hard1..3` (BIF and both RIMs) |
| 2 | 44,100 | 16 | 8 + 3 | `mgs_*` swoop-race sounds in the BIF; beds `streammusic/al_en_rmmtar{lrg,med,sml}` |
| 2 | 22,050 | 16 | 1 + 20 | `mgs_drawmain`; `streamsounds/` (18), `streammusic/mus_loadscreen`, one launcher file |
| 1 | 11,025 | **8** | 1 | `mgs_sith_hit` in `sounds.bif` |

(First number: plain RIFF in containers; second: RIFF after an mp3pad prefix in the stream
folders.)

## IMA ADPCM (format tag 0x11)

Two shapes occur, both with 2,041 samples per block per channel:

| Channels | Rate | Block align | Samples per block | Count | Where |
|---|---|---|---|---|---|
| 2 | 44,100 | 2,048 | 2,041 | 47 | ambient beds `streammusic/al_*.wav` (after the mp3pad prefix) |
| 1 | 44,100 | 1,024 | 2,041 | 8 | `cb_sh_blast1`, `cb_sh_hvybl1`, `cb_sh_medbl1`, ... in `sounds.bif` and `global.rim` |

`fmt ` extra data: cbSize 2, then u16 samples per block = `(block align − 4 × channels) × 2 /
channels + 1` (holds for all 55). The byte rate field is `floor(rate × block align / samples per
block)` (44,251 and 22,125). The `fact` chunk holds a u32: the true number of sample frames per
channel. The `data` chunk is always a whole number of blocks; the last block is padded, so
`blocks × 2,041 − fact` is 103 to 2,023 samples. **Stop decoding at the `fact` count.**

### Block layout

A block is `block align` bytes:

1. One 4-byte header per channel (left first):
   - s16 the channel's first sample, output as-is;
   - u8 the step index to start with, 0..88 (never more in 41,998 blocks);
   - u8 reserved, 0 (always 0).
2. The rest: 4-bit codes, two per byte, **low nibble first**. With one channel the codes simply
   follow in order. With two channels they come in **4-byte groups that alternate channels**:
   4 bytes (8 codes) for the left channel, 4 bytes for the right, 4 for the left, and so on.

So a 2,048-byte stereo block holds, per channel, 1 header sample + 2,040 coded samples = 2,041.

### Decoding one code

Each channel keeps a predicted sample `p` (from the header) and a step index `i` (from the
header). For each 4-bit code `c`, in stream order:

1. `step = STEP[i]`.
2. `diff = step >> 3`; add `step` if bit 2 of `c` is set, `step >> 1` if bit 1 is set, `step >> 2`
   if bit 0 is set. (This is the integer form of `(magnitude + 0.5) × step / 4` the IMA spec
   uses; decode with these shifts to match the encoder bit for bit.)
3. If bit 3 of `c` is set, `p -= diff`, else `p += diff`. Clamp `p` to −32,768..32,767.
4. `i += INDEX[c & 7]`, clamp `i` to 0..88.
5. Output `p`.

Tables (from the IMA ADPCM recommended practice, the same values Microsoft's codec uses):

```
INDEX[0..7] = -1, -1, -1, -1, 2, 4, 6, 8
STEP[0..88] =
      7,     8,     9,    10,    11,    12,    13,    14,    16,    17,
     19,    21,    23,    25,    28,    31,    34,    37,    41,    45,
     50,    55,    60,    66,    73,    80,    88,    97,   107,   118,
    130,   143,   157,   173,   190,   209,   230,   253,   279,   307,
    337,   371,   408,   449,   494,   544,   598,   658,   724,   796,
    876,   963,  1060,  1166,  1282,  1411,  1552,  1707,  1878,  2066,
   2272,  2499,  2749,  3024,  3327,  3660,  4026,  4428,  4871,  5358,
   5894,  6484,  7132,  7845,  8630,  9493, 10442, 11487, 12635, 13899,
  15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
```

State does not carry across blocks: every block restarts from its header.

The nibble order and the interleave are confirmed from the data, not just the spec: decoding a
block and comparing its last sample with the next block's header sample gives a mean gap of 295
(the same as the gap between two neighbouring samples, 295) with low-nibble-first and 4-byte
groups, against 2,034 with high-nibble-first and 17,020 with 1-byte interleave.

## MP3 (MPEG-1 Layer III)

### What the data uses

Every frame of every MPEG stream was walked (2,759,904 frames, sync to sync, to the end of each
file) and the side information of each was parsed.

| | Voice-over (`streamwaves/`, 13,799) | Music (`streammusic/`, 68) |
|---|---|---|
| MPEG version, layer | 1, III | 1, III |
| Sample rate | 32,000 Hz | 44,100 Hz |
| Bitrate | 48 kbit/s, CBR (every frame) | 128 kbit/s, CBR (every frame) |
| Frame header bytes | `FF FB 38 C4` | `FF FB 90 40` / `92 40` / `92 60` / ... |
| Frame size | 216 bytes always (no padding needed) | 417 or 418 bytes (padding bit in 96 % of frames) |
| Channel mode | mono | joint stereo, every frame |
| Mode extension | -- | MS stereo on in 212,171 frames, off in 13,778; **intensity stereo never** |
| CRC (protection bit 0) | never | never |
| Free-format bitrate | never | never |
| Emphasis, private, copyright | all 0 | all 0 |
| Block types (granule × channel) | long 3,073,735; short 1,027,921; start 463,520; stop 475,136 | long 890,472; short 7,124; start 3,100; stop 3,100 |
| Mixed blocks | **never** | **never** |
| scfsi (scalefactor reuse in granule 1) | used (1,147,993 frame × channel) | never |
| preflag | never | 798,873 granules |
| scalefac_scale = 1 | 145,963 granules | 421,410 granules |
| subblock_gain ≠ 0 | never | 740 granules |
| In MS frames, both channels same block type | -- | always (0 granules differ) |
| Huffman tables used (big_values) | every valid table: 0–31 except 4 and 14, which do not exist | the same except 23 |
| count1 tables | A and B | A and B |
| main_data_begin | up to 511 (the full bit reservoir) | up to 511 |
| big_values | at most 261 (limit 288) | |
| First frame | a LAME `Info` frame (CBR "Xing" header), flags 15, encoder `LAME3.93`, delay 576 | an audio frame |
| ID3v2 tag at the start | 3 files | 51 files (all 54: v2.3.0, no flags, 256–1,024 bytes) |
| ID3v1 tag (last 128 bytes) | the same 3 files | the same 51 files |
| Junk between frames, lost sync, truncated last frame, bytes after the last frame | none | none |
| Frames per stream | 7 .. 17,980 (all streams) | |
| Duration | 0.25 s .. 26.0 s, median 6.5 s, 25.3 h in all | 11.8 s .. 469.7 s, median 81.8 s, 1.6 h |

Bit-reservoir consistency was checked frame by frame: no frame's main_data_begin reaches before
the stream start, no frame's main data overlaps the previous frame's, and no frame's
part2_3_length total runs past the end of its own main data. The `Info` header's frame count
(audio frames after it) and byte count (the stream from the `Info` frame to the end) match the
walk in all 13,799 VO files.

### What our decoder must support

- MPEG-1 Layer III only, sample rates 32,000 and 44,100 (scalefactor band tables for these two;
  48,000 never occurs).
- Mono and joint stereo with **MS stereo**; plain L/R joint-stereo frames (mode extension 0).
- All four block types (long, start, short, stop) with their IMDCT windows, short-block reordering,
  and alias reduction on long blocks.
- scfsi, preflag (the pretab boost), scalefac_scale, subblock_gain, global_gain.
- All 30 Huffman tables (1–3, 5–13, 15, 16–23 sharing one code set with different linbits, 24–31
  sharing another) plus count1 tables A and B; table 0 means "all zero".
- The bit reservoir (keep at least the last 511 bytes of main data).
- The padding bit in the frame length.
- Skipping an ID3v2 tag before the first frame (10-byte header, `ID3`, version, flags, then a
  4-byte size with 7 bits per byte; skip 10 + size, plus 10 more if flag 0x10 says there is a
  footer, which never happens here) and an ID3v1 tag (`TAG`) in the last 128 bytes.
- Recognising the `Info`/`Xing` frame (below) and not playing it.

### What it can skip (absent from every file)

Layers I and II; MPEG-2 and MPEG-2.5 (lower sampling frequencies, LSF scalefactor coding) --
the only LSF frames in the install are the 470-byte prefixes, which detection drops; intensity
stereo (MPEG-1 and LSF); mixed blocks; CRC; free format; dual-channel and plain stereo modes;
VBR (every stream is CBR, but nothing in a frame-by-frame decoder depends on that); the 48 kHz
tables. A decoder that meets one of these should return an error value, so modded files fail
loudly rather than play noise.

### Frame header (4 bytes)

Bits from the most significant bit of byte 0:

| Bits | Field | KOTOR |
|---|---|---|
| 11 | sync, all ones | `FF`, then top 3 bits of byte 1 set |
| 2 | version: 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5, 1 reserved | 3 |
| 2 | layer: 1 = III, 2 = II, 3 = I, 0 reserved | 1 |
| 1 | protection: **0** means a 16-bit CRC follows the header | 1 (no CRC) |
| 4 | bitrate index; MPEG-1 Layer III: 1..14 = 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320 kbit/s; 0 free format, 15 invalid | 3 (48), 9 (128) |
| 2 | sample rate index; MPEG-1: 0 = 44,100, 1 = 48,000, 2 = 32,000, 3 reserved | 2, 0 |
| 1 | padding: the frame has one extra byte | |
| 1 | private | 0 |
| 2 | channel mode: 0 stereo, 1 joint stereo, 2 dual channel, 3 mono | 3, 1 |
| 2 | mode extension (joint stereo, Layer III): value 2 = MS stereo, value 1 = intensity stereo | 0 or 2 |
| 1 | copyright | 0 |
| 1 | original | VO 1, music 0 |
| 2 | emphasis | 0 |

Frame length in bytes (MPEG-1 Layer III, header included) = `floor(144 × bitrate / rate) +
padding`. The next header starts right after. Each frame decodes to 1,152 samples per channel
(two granules of 576).

### Side information (MPEG-1: 17 bytes mono, 32 bytes stereo)

Right after the header (and the CRC, if there were one), read as a bit string, most significant
bit first:

```
main_data_begin        9   bytes back from this frame's main data where its data starts
private bits           5 (mono) / 3 (stereo)
scfsi[ch][4]           1 each, per channel: scalefactor bands 0-5, 6-10, 11-15, 16-20 reuse granule 0's
for granule 0, 1:
  for each channel:
    part2_3_length     12  bits of scalefactors + Huffman data
    big_values          9  pairs in the big-values region
    global_gain         8
    scalefac_compress   4  index into the (slen1, slen2) table
    window_switching    1
    if window_switching:
      block_type        2  1 start, 2 short, 3 stop (0 is invalid here)
      mixed_block       1  (always 0 in KOTOR)
      table_select[2]   5 each
      subblock_gain[3]  3 each
      (region boundaries are implied)
    else:
      table_select[3]   5 each
      region0_count     4
      region1_count     3
    preflag             1
    scalefac_scale      1
    count1table_select  1
```

The main data (scalefactors and Huffman codes) follows the side information and may begin in
earlier frames (the bit reservoir): treat the main-data bytes of all frames as one stream, and a
frame's data starts `main_data_begin` bytes before the end of what earlier frames contributed.
Bytes in that stream not claimed by any granule are ancillary data (LAME's filler) and are skipped.

The decode stages after that are the standard ones (ISO 11172-3, clause 2.4.3.4 and annex tables):
scalefactor decoding, Huffman decoding, requantisation, short-block reordering, MS stereo, alias
reduction, IMDCT with overlap-add, frequency inversion, and the 32-band polyphase synthesis
filterbank. Implement them from the standard and public write-ups, not from an open-source
decoder.

### The `Info` frame and LAME tag (VO only)

The first frame of every VO stream is a valid, silent MPEG frame whose bytes at offset
`4 + side info size` (21 for MPEG-1 mono) read `Info` (LAME's name for the Xing header of a CBR
file; VBR files would say `Xing`). Layout after the 4-byte tag, big-endian:

| Field | Size | KOTOR |
|---|---|---|
| flags | u32 | 15: the next four fields are all present |
| frames | u32 | audio frames after this one (checked) |
| bytes | u32 | bytes from this frame to the end of the stream (checked) |
| TOC | 100 bytes | seek table (useless for CBR) |
| quality | u32 | |
| encoder | 9 bytes | `LAME3.93` |
| ... | 12 bytes | LAME revision, lowpass, replay gain, flags, bitrate |
| delay, padding | 3 bytes | 12 bits encoder delay (576 in every file), 12 bits end padding (1,152..2,546) |

Detect it in the first frame only: if the 4 bytes at `4 + side info size` are `Info` or `Xing`
(or `VBRI` at offset 36, never seen), skip the frame. Playing it would only add 36 ms of silence
at the start of each line, since its side information is all zero. Gapless trimming with the
delay and padding values (drop delay + decoder delay samples at the start, padding at the end) is
optional: VO lines are not looped. The music streams have no such frame and no gapless data.

## Where each kind is used

Resolved with `audioprobe.py --refs`: `dialog.tlk` sound resrefs, the `.ssf` soundsets (lists of
strrefs into `dialog.tlk`), `ambientmusic.2da`, `ambientsound.2da`, `loadscreens.2da`, and the
ResRefs inside `.dlg`, `.uts`, `.git`, `.utp` and `.utc` files (found by a raw byte scan for GFF's
length-prefixed ResRefs, then kept only if an audio file of that name exists):

| Pool | Names | Kind | Used for |
|---|---|---|---|
| `streamwaves/<a>/<b>/` | 13,310 resrefs of 16 characters: `n`, module (5, e.g. `m01aa` or `globe`), dialogue (6), line (3, digits in all but one), then `_` (or a letter in 12) | riffstub MP3, 32 kHz mono | dialogue voice-over: 12,715 are named in `.dlg` files, 13,035 by `dialog.tlk` entries. The two directories are the 5 characters after the leading `n` and the 6 after those: `nm01aac02001000_.wav` lives in `streamwaves/m01aa/c02001/` (all 13,310 follow the rule) |
| `streamwaves/` (top level) | 489: generic alien barks `n_g<species>_<kind>` (`n_gmtwilek_coms`), `n_m...` lines, cutscene lines (`BA02CS001`, `MA18CS006A`, ...) | riffstub MP3 | 394 named in `.dlg` files, 414 by `dialog.tlk` |
| `streamsounds/` | 970: party soundsets `p_<member>_<event>` (419), NPC soundsets `n_` (256), creatures `c_` (181), ambient loops `al_` (69), battle stingers `mus_sbat_*` (18), placeables `pl_` (14), swoop race `mgs_` (7), cutscene `cs_` (5), `as_el_alert` | mp3pad + PCM | 672 (`p_`, `n_`, `c_`) named by `dialog.tlk`, 610 of them reached through the 316 `.ssf` soundsets; 84 (mostly `al_`, `pl_`, `mgs_`) named by `.uts` sound objects; 17 stingers named in `ambientmusic.2da`'s `stinger1` column (the 18th is misspelt there, below) |
| `streammusic/al_*` | 50 | mp3pad + IMA ADPCM (47) or PCM (3) | ambient beds: all 44 names in `ambientsound.2da` |
| `streammusic/mus_*` | 44 | riffstub MP3 (43) / mp3pad PCM (`mus_loadscreen`) | area, battle and theme music: the 43 MP3s are all named in `ambientmusic.2da`; `mus_loadscreen` is the only name in `loadscreens.2da` |
| `streammusic/` numbered | 23 (`01b`, `03a`, `04`, ... `57`) | riffstub MP3 | cutscene music: 17 are named in `.dlg` files, and those share their number with a `STUNT_<n>` cutscene module (`STUNT_03a`, `STUNT_31b`, ...) |
| `streammusic/credits`, `evil_ending` | 2 | riffstub MP3 | end credits and the dark-side ending; named in no data file (`evil_ending` is a string in `swkotor.exe`) |
| WAV resources in `data/sounds.bif` | 1,928: ambient one-shots `as_` (593), party `p_` (419), NPC `n_` (246), creature `c_` (181), combat `cb_` (92), doors `dr_` (77), footsteps `fs_` (67), swoop race `mgs_` (65), placeables `pl_` (59), visual effects `v_pro_`/`v_imp_`/`v_dur_`/`v_bem_` (46), cutscene `cs_` (42), GUI `gui_` (22), body falls `bf_` (13), shields `gen_` (4), `al_ot_shiprise`, `it_pistol` | PCM (1,924), IMA (4) | sound effects: 557 named by `.uts` sound objects, 624 by `dialog.tlk` (soundsets); the rest presumably by the sound 2DAs (`footstepsounds`, `weaponsounds`, `guisounds`, ...), scripts and model events (not checked here) |
| `rims/global.rim`, `rims/miniglobal.rim` | 246 and 129 | PCM, IMA | byte-identical copies of `sounds.bif` entries (combat, footsteps, GUI, effects) |

`.git`, `.utp` and `.utc` files name no audio directly (one `.utc` match is a stray short
string), so placed sound objects reach their waves only through their `.uts` blueprints.

Duplicates across pools: 797 `streamsounds/` names also exist in `sounds.bif`; for 785 the RIFF
after the prefix is byte-identical to the BIF resource, for 12 it differs (`c_drdmk1_atk1`,
`_bat1`, `_dead`, `_hit1`, `_slct`, `mgs_engine_01l`..`05l`, `n_rodian_dead`, `p_carth_bat1`).
Which copy the engine plays depends on its search order (see [resources.md](resources.md)).

`dialog.tlk` names 26,212 distinct sound resrefs; 12,088 of them exist nowhere in the install
(cut content and placeholders such as `__m1anpop094008_`). `ambientmusic.2da` names three files
that do not exist: `mus_gui_start` (row 1), `mus_bat_sforge` (the file is missing) and
`mus_sbat_slehey` (the file is spelt `mus_sbat_sleyhey.wav`). The engine must treat a missing
sound as silence.

`swkotor.ini`'s `[Alias]` section defines `STREAMMUSIC=.\StreamMusic` and
`STREAMWAVES=.\StreamWaves` (no `STREAMSOUNDS`), and `swkotor.exe` holds the format strings
`HD0:STREAMWAVES\%s`, `HD0:STREAMWAVES\%s\%s\%s`, `HD0:STREAMSOUNDS\%s` and `HD0:STREAMMUSIC\%s`:
the three folders are looked up by name, the VO folder also by the two-level path above.

### Rates the mixer must convert

Output devices run at 44,100 or 48,000 Hz; the sources are 11,025, 22,050, 32,000 and 44,100 Hz,
mono or stereo, 8- or 16-bit. Music and ambient beds are long (up to 7.8 minutes) and must be
streamed (decode a few frames or blocks ahead), not decoded whole.

## Open questions (for RE)

- How `swkotor.exe` hands each kind to Miles (`Mss32.dll` with `mssmp3.asi`, Miles' "MSS MPEG
  Layer 3 Audio Decoder", which rejects Layers I and II). The exe has no copy of the `FF F3 60
  C4` constant, so the prefix is probably skipped by Miles' own file-type detection or by a
  generic "find RIFF" scan. `.rdata` around VA `0x74D300` holds `?.wav`, `.mp3`, a
  `\\\\%d,%d` format (possibly a name for an in-memory file), `RIFF`, `wav` and `evil_ending`
  side by side, which suggests the exe sniffs for `RIFF` and names the data `.wav` or `.mp3`
  for Miles. Our reimplementation does not depend on the answer: the detection rules above are
  proven on the data.
- Why the 470-byte prefix exists (a build tool's marker? a workaround for Miles' type sniffing?).
- Whether `smpl`/`cue` loop points in 10 files matter (probably not; looping sounds are flagged in
  UTS/2DA data instead).

## Checked

```
python kotor/tools/py/audioprobe.py            # ~7 s on 24 cores (multiprocessing)
python kotor/tools/py/audioprobe.py --refs     # the "Where each kind is used" numbers, ~30 s
python kotor/tools/py/audioprobe.py --list riffstub/mp3   # names of one class
```

The probe reads every `.wav`/`.mp3` file anywhere under the install and every WAV/MP3 resource in
every container (`kres.Game.every_entry`: chitin's BIFs, modules, rims, lips, texture packs,
`patch.erf`, saves): **17,193 inputs** (`streamwaves` 13,799, `data\sounds.bif` 1,928,
`streamsounds` 970, `rims\global.rim` 246, `rims\miniglobal.rim` 129, `streammusic` 119,
`launcher` 2). **0 unclassified, 0 crashed, 0 with issues.**

| Class | Count | Per place |
|---|---|---|
| riffstub/mp3 | 13,867 | streammusic 68, streamwaves 13,799 |
| none/pcm | 2,295 | sounds.bif 1,924, global.rim 242, miniglobal.rim 129 |
| mp3pad/pcm | 976 | launcher 2, streammusic 4, streamsounds 970 |
| mp3pad/ima-adpcm | 47 | streammusic 47 |
| none/ima-adpcm | 8 | sounds.bif 4, global.rim 4 |

For each input it checks: the wrapper (prefix length and bytes, stub length and bytes; one
distinct byte string each), the RIFF chunk walk (RIFF size against the file, chunks running past
the end, odd sizes, `fmt `/`data` present), PCM block align and byte rate, IMA samples-per-block
formula, every block header (step index ≤ 88, reserved byte 0, 41,998 blocks), `fact` against
the block count, the nibble-order/interleave continuity test; and for every MPEG stream: every
frame header, frame lengths followed to the end of the file, resyncs and junk, ID3v1/ID3v2/APE/
Lyrics3 tags, Xing/Info/VBRI/LAME tags and their frame and byte counts, the side information of
every frame (block types, mixed flag, table selects of non-empty regions, count1 table, scfsi,
preflag, scalefac_scale, subblock gain, big_values ≤ 288), MS frames with differing block types,
LSF intensity stereo, and the bit reservoir (begins before the stream, overlaps, overruns).

MPEG histograms (all 13,867 streams; frames 2,759,904):

```
version 1: 2759904            layer 3: 2759904            crc False: 2759904
rate 32000: 2533955, 44100: 225949
bitrate 48: 2520156, 128: 225949 (+ 48: 13799 Info frames)
mode mono: 2533955, joint: 225949            mode_ext MS: 212171, none: 13778
padding 0: 2543184, 1: 216720               frame bytes 216: 2533955, 418: 216720, 417: 9229
emphasis 0, private 0, copyright 0 everywhere; free-format frames 0
stream.tag Info: 13799, none: 68 (Info flags 15; LAME3.93; delay 576; end padding 1152..2546)
stream.bitrate CBR: 13867          id3v2 54 (v2.3.0, 256..1024 bytes), id3v1 54, ape 0, lyrics3 0
junk 0, trailing bytes 0, truncated last frame 0, Info frame/byte count mismatches 0
blocks long 3964207, short 1035045, stop 478236, start 466620, mixed 0
huffman tables (non-empty regions) 15: 2528478, 24: 1821398, 3: 1551376, 9: 1394629,
  12: 1286446, 2: 1147357, 6: 1141728, 25: 852410, 8: 670743, 5: 641954, 26: 552153, 1: 370824,
  11: 346162, 13: 344338, 7: 291908, 27: 230783, 10: 164595, 16: 71883, 18: 68267, 0: 61598,
  28: 60114, 17: 58476, 19: 56864, 20: 38368, 29: 10992, 21: 3194, 30: 1416, 23: 1063, 31: 658,
  22: 192
count1 A: 4091721, B: 1827060
scfsi zero: 1824061, used: 1147993      preflag 0: 5145235, 1: 798873
scalefac_scale 0: 5376735, 1: 567373    subblock_gain nonzero: 740 granules (max 7)
empty granules (part2_3_length 0): 25327   big_values > 288: 0 (max 261)
main_data_begin max 511; part2_3_length max 3139; global_gain 0..221
MS frames with differing block types between channels: 0; LSF intensity stereo: 0
bit reservoir: begins before stream 0, overlaps previous frame 0, overruns frame 0
```

IMA ADPCM (55 files): bits 4, cbSize 2, samples-per-block formula holds 55/55, no partial last
block, `fact` smaller than blocks × 2,041 by 103..2,023 in 55/55, block headers bad 0/41,998;
continuity: low nibble + 4-byte groups 294.7, baseline 295.4, high nibble 2,034.4, 1-byte
groups 17,019.6.

Durations: VO 0.25–26.0 s (25.3 h total); MP3 music 11.8–469.7 s (1.6 h); IMA beds 14.3–141.4 s
(0.54 h); `streamsounds` PCM 0.14–63.6 s (0.69 h); BIF PCM 0.003–21.9 s (1.17 h).

## Sources

- Microsoft, *Multimedia Programming Interface and Data Specifications 1.0* (1991): RIFF and the
  WAVE `fmt `/`data`/`fact` chunks; Microsoft's WAVEFORMATEX and WAVE_FORMAT_IMA_ADPCM (0x11)
  documentation for the IMA block header and the 4-byte channel interleave.
- IMA Digital Audio Technical Working Group, *Recommended Practices for Enhancing Digital Audio
  Compatibility in Multimedia Systems* (1992): the IMA ADPCM step and index tables.
- ISO/IEC 11172-3 (MPEG-1 audio) and ISO/IEC 13818-3 (MPEG-2 LSF): frame header, side
  information, Layer III decoding; public write-ups of the MPEG audio frame header.
- The LAME project's description of the Xing/Info and LAME tag; id3.org's ID3v1 and ID3v2.3.0
  documents.
- The KOTOR modding community's knowledge that streamed WAVs hide MP3 data behind a fake header;
  every byte-level fact here comes from the probe, not from a reimplementation.
- `swkotor.exe` strings and `swkotor.ini` (read, not modified).
