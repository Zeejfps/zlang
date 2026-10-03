# Bink (`.bik`): KOTOR's movies

KOTOR plays its cutscenes, logos and the legal screen from Bink 1 files (RAD Game Tools) in
`movies/*.bik`. This note describes the container as checked against all 61 files, then the video
and audio bitstreams in enough detail to know exactly what to implement and where to read more.

Status markers used below:

- **[verified]**: checked against the install by `tools/py/bikprobe.py`, by comparing with
  FFmpeg's decoder run as a black-box oracle (see [Checking a decoder](#checking-a-decoder)), or
  by our ctxlang decoder (`lib/video`), which matches FFmpeg on every frame and sample of the 61
  movies.
- **[docs]**: taken from public descriptions (listed in [Sources](#sources)) and from reading
  FFmpeg's decoder; not checked by us (only revisions other than `i` now).

The decoder's design, API and the game's playback are in
[docs/design/video.md](../design/video.md).

## What KOTOR uses (and what to skip)

**[verified]** for every file:

| Feature | KOTOR | Implement? |
|---|---|---|
| Signature / revision | `BIKi` in all 61 files | only `i` (reject others with an error) |
| Size | 640 x 272 (53 files), 640 x 360 (5), 640 x 480 (3) | any size, but these are what's tested |
| Frame rate | 2997/100 = 29.97 fps in every file | numerator/denominator from the header |
| Video flags | 0 everywhere: no alpha plane, no grayscale, no scaling | ignore alpha/gray/scaling (reject if set) |
| Keyframes | exactly one per file, frame 0 | no seeking needed: play from frame 0 |
| Audio tracks | 1 track in 60 files, none in `legal.bik` | 0 or 1 tracks (play track 0) |
| Audio codec | flags `0x7000`: DCT variant, stereo, 16-bit | DCT only; skip the RDFT variant |
| Audio rate | 44100 Hz (59 tracks), 48000 Hz (`56b.bik`) | any rate >= 44100 uses the same block size |
| Track id | 0 | ignore |

There are no Bink resources inside BIFs, modules or Override
(`python kotor/tools/py/kres.py ls --type bik` lists nothing): movies are loose files in
`movies/`, 61 of them, 606 MB, 27.1 minutes in all. The install's `binkw32.dll` is RAD's
**version 1.5v** ("Bink and Smacker", copyright 1994-2003, FileVersion resource). It holds the
codec's constant tables, see [Tables](#tables-where-to-get-them).

## Container

All numbers are little-endian. The layout below is our reading of the public descriptions,
**[verified]** field by field on all 61 files.

### Header (44 bytes, then the audio track tables)

| Offset | Type | Field | KOTOR |
|---|---|---|---|
| 0 | char[3] | `BIK` | |
| 3 | u8 | revision letter: `b`, `d`, `f`, `g`, `h`, `i` (and `k` in later SDKs) | `i` |
| 4 | u32 | file size minus 8 | always matches |
| 8 | u32 | frame count | 96 to 3606 |
| 12 | u32 | largest frame, in bytes (index distance) | always equals the real maximum |
| 16 | u32 | frame count again | always equal to offset 8 |
| 20 | u32 | width in pixels | 640 |
| 24 | u32 | height in pixels | 272, 360, 480 |
| 28 | u32 | frame rate numerator | 2997 |
| 32 | u32 | frame rate denominator | 100 |
| 36 | u32 | video flags: bit 20 alpha plane, bit 17 grayscale, bits 28-31 scaling mode | 0 |
| 40 | u32 | audio track count *T* | 0 or 1 |

Then three tables of *T* entries each, one after the other (revision `k` adds an unknown u32
before them; KOTOR has none):

1. *T* x u32: the largest decoded audio packet, in bytes of 16-bit interleaved PCM.
   **[verified]**: it always equals the decoded size of the track's first packet, which is also
   the largest (138240 for 44.1 kHz, 145920 for 48 kHz). MultimediaWiki reads it as
   "u16 unknown, u16 channels"; that is wrong (the high half just happens to be 2 here).
2. *T* x (u16 sample rate, u16 flags). Flags: `0x1000` DCT variant (else RDFT), `0x2000` stereo,
   `0x4000` 16-bit output, `0x8000` unknown.
3. *T* x u32 track id.

### Frame index

Right after the track tables: *frames* + 1 u32 entries. Entry *n* is the absolute file offset of
frame *n* with bit 0 set when the frame is a keyframe; the extra last entry is the file size, so
frame *n* spans `[entry n & ~1, entry n+1 & ~1)`. **[verified]**: offsets strictly increase, the
first one is the end of the index, the last equals the file size, frame 0 is the only keyframe.

### A frame

```
for each audio track t (in header order):
    u32 size                 bytes that follow for this track; 0 = no audio in this frame
    if size > 0:
        u32 decoded          bytes of 16-bit interleaved PCM this packet decodes to
        size - 4 bytes       audio blocks (below)
video packet                 the rest of the frame
```

**[verified]** for every frame of every file: sizes add up exactly; audio packets are whole
32-bit words; the audio bitstream inside each packet ends exactly at its end.

Audio packing in KOTOR **[verified]**:

- The first packet of a track carries 18 blocks (19 in `56b.bik`): about 0.78 s of audio up
  front, so a player has a buffer before frame 1.
- Every other non-empty packet carries exactly one block (1920 samples per channel). At 29.97 fps a
  frame lasts 1471.5 samples at 44.1 kHz, so about one frame in four has no audio (12257 empty
  packets, 36285 one-block packets).
- The sum of the `decoded` fields, divided by 4 bytes and the rate, equals the video duration
  (frames x 100 / 2997) to within a millisecond in every file. The last packet's `decoded` is
  smaller than its block (by 16 to 7600 bytes): drop the excess samples. Audio starts at time 0,
  with frame 0.

## Video bitstream (Bink 1)

This section summarizes how a `BIKi` video packet decodes, in our words. It follows the public
write-ups and our reading of FFmpeg's decoder (LGPL, read only), and is now **[verified]**
throughout: `lib/video/bink_video.ctx`, written from this description, decodes every frame of
all 61 movies byte for byte as FFmpeg does (`binkcheck --ref`, see [Checked](#checked)). Only the
[revision differences](#revision-differences) other than `i` remain **[docs]**.

### Bits, planes, buffers

- Bits are read least-significant first from 32-bit little-endian words (as for audio, which we
  verified bit-exactly).
- Pixels are YUV 4:2:0, 8 bits per sample, BT.601 limited range ("tv" in FFmpeg): black is
  Y=16, U=V=128. **[verified]** with the oracle: frame 0 of 4 of the 5 movies checked is uniform
  (16, 128, 128).
- A `BIKi` packet without alpha is: one u32, then the luma plane, then the two chroma planes, each
  plane ending on a 32-bit boundary. If the alpha flag were set, a u32 and the alpha plane (full
  size) would come first.
- The leading u32 is not needed to decode: FFmpeg and ScummVM skip it. MultimediaWiki calls it the
  plane's data size. **[verified]**: it is always a multiple of 4, at least 4 and at most the
  video packet size, consistent with the byte offset where the chroma data starts (luma takes 85%
  of a packet on average).
- **Chroma order.** For revisions `h` and `i` the first chroma plane coded is **V (Cr)**, then
  **U (Cb)**; for `f` and `g` it is U then V. **[verified]** for `i`: FFmpeg's output (which
  follows this order) shows Bastila's yellow lightsaber and normal skin in `02.bik` frame 120,
  and swapping the planes turns both blue (`kotor/out/bink/02_120*.png`, regenerable with the
  oracle). MultimediaWiki's "Bink Container" page states the order the other way round; it is
  wrong for `i`.
- A plane is decoded as 8x8 blocks: luma `bw = ceil(W/8)` by `bh = ceil(H/8)`, chroma
  `ceil(W/16)` by `ceil(H/16)`. KOTOR: luma 80x34, 80x45, 80x60; chroma 40x17, 40x23, 40x30.
  A 16x16 block starting on the last row of an odd row count writes 8 rows past the plane, so
  allocate every plane with its block rows and columns rounded up to even (luma 640 x 368 for the
  360-line movies, chroma 320 x 144 / 192 / 240) and crop when presenting.
- Two frame buffers: blocks that copy (skip, motion, residue, inter) read the **previous** decoded
  frame; everything is written to the **current** one; after the frame the two swap. Initialize
  the previous frame to black before frame 0. (Revision `b` used a single buffer.)
- If the packet's bits run out after a plane, the remaining planes are not coded (FFmpeg stops);
  KOTOR's packets always contain all three planes **[verified]**: chroma data is never empty.

### Per-plane setup: Huffman trees and bundles

Most per-block values do not sit next to their block. They come from nine **bundles**, streams of
values that are refilled one row of blocks at a time (Kostya's "Bink bitstream bundling" explains
why). In order:

| # | Bundle | Values | Element-count field width (bits) |
|---|---|---|---|
| 1 | block types | 0-9 per 8x8 block | `floor(log2(w/8 + 511)) + 1` |
| 2 | sub-block types | type of a 16x16 block's content | `floor(log2(w/16 + 511)) + 1` |
| 3 | colors | pixel values (bytes) | `floor(log2(bw*64 + 511)) + 1` |
| 4 | patterns | bytes, one bit per pixel of a row | `floor(log2(bw*8 + 511)) + 1` |
| 5 | x motion | signed, -15..15 pixels | as 1 |
| 6 | y motion | signed, -15..15 pixels | as 1 |
| 7 | intra DC | 16-bit DC of intra DCT blocks | as 1 |
| 8 | inter DC | signed 16-bit DC of inter DCT blocks | as 1 |
| 9 | runs | run lengths minus 1 for run blocks | `floor(log2(bw*48 + 511)) + 1` |

Here `w` is the plane width rounded up to a multiple of 8 (at least 8) and `bw` the plane's width
in blocks. For 640-wide luma the widths are 10, 10, 13, 11, 10, 10, 10, 10, 13; for 320-wide
chroma 10, 10, 12, 10, 10, 10, 10, 10, 12 (our arithmetic).

At the start of each plane the decoder reads, for bundles 1 to 9 in order, the Huffman tree the
bundle uses: one tree each, except that colors first read 16 extra trees (one per possible value
of the previous high nibble, then the low-nibble tree) and the two DC bundles read none. The
"previous high nibble" context starts at 0 for each plane.

**Huffman trees.** Bink has 16 fixed prefix codes over 16 symbols; tree 0 is plain 4-bit values.
Each code's lengths and bit patterns come from the tables (below); a code is matched least
significant bit first (bit 0 of the table's code is the first bit read). **[verified]** that the
DLL's tables form 16 complete prefix codes read that way. A stream only says which tree to use
and how to map the 16 code indices to symbols:

```
4 bits   tree number t
if t == 0: identity mapping, nothing else
else 1 bit:
  1 -> 3 bits n, then n+1 symbols of 4 bits each: the first entries of the mapping;
       the remaining entries are the unused symbols in increasing order
  0 -> 2 bits d; start from 0..15 and, for level i = 0..d, merge each pair of neighbouring
       runs of length 2^i: repeatedly take the next element of the first run (bit 0) or
       of the second (bit 1) until one run is used up, then append the rest of the other
```

MultimediaWiki's "Bink Video" page describes both forms with examples.

**Refilling a bundle** (at the start of every row of blocks, for bundles 1 to 9 in order). A
bundle that has been closed, or still has unconsumed values, reads nothing. Otherwise read a count
*n* (field width from the table); *n* = 0 closes the bundle for the rest of the plane. Then:

- block types, sub-block types: 1 bit; if set, a 4-bit value repeated *n* times. Otherwise *n*
  values: a Huffman symbol *v*; *v* < 12 is a value; *v* >= 12 repeats the last value
  4, 8, 12 or 32 times (*v* = 12..15), the repeat counting toward *n*. "Last value" starts at 0
  on each refill.
- colors: 1 bit; if set, one color repeated *n* times, else *n* colors. A color is a high nibble
  (Huffman, with the tree selected by the previous high nibble, which then becomes this one) and
  a low nibble (the low-nibble tree): `high << 4 | low`. Revisions before `i` code a sign and
  magnitude around 128 instead (bit 7 set means `128 - (v & 127)`, else `128 + v`); `i` uses the
  byte as is.
- patterns: *n* bytes, each a low then a high nibble (Huffman). No repeat flag.
- x and y motion: 1 bit; if set, a 4-bit magnitude (followed by a sign bit if non-zero, 1 =
  negative) repeated *n* times; otherwise *n* values, each a Huffman magnitude plus a sign bit when
  non-zero.
- intra DC: an 11-bit start value; inter DC: a 10-bit magnitude plus a sign bit when non-zero.
  The remaining *n* - 1 values come in groups of up to 8: 4 bits width *k*; if *k* = 0 the group
  repeats the current value, else each value adds a *k*-bit magnitude (with a sign bit when
  non-zero) to the running value.
- runs: 1 bit; if set, a 4-bit value repeated *n* times, else *n* Huffman symbols.

### Blocks

Each row of the plane: refill the bundles, then for each block position take the next block type.
Some block data is read from the bitstream directly at that point, interleaved with nothing else:
run-block pattern indices and flags, residue masks, DCT coefficients and quantizers.

| Type | Name | Decoding |
|---|---|---|
| 0 | skip | copy the 8x8 block at the same place in the previous frame |
| 1 | scaled | a 16x16 block: take a sub-type from bundle 2, decode that 8x8 content (types 3, 5, 6, 8, 9 only) and double every pixel to 2x2 (type 6 just fills the 16x16 area). Covers this and the next column, and the row below |
| 2 | motion | x, y from bundles 5/6; copy the 8x8 block at (x, y) pixels from here in the previous frame |
| 3 | run | 4 bits: one of 16 scan patterns over the 64 pixels. Then until 63 or more pixels are set: run = next runs value + 1; 1 bit: set = one color for all of the run, clear = a color per pixel. If exactly 63 were set, the last pixel takes one more color |
| 4 | residue | motion copy as type 2, then 7 bits mask count and the residue (below) added to the pixels |
| 5 | intra | DC from bundle 7, coefficients and a 4-bit quantizer from the bitstream (below), dequantize with the intra matrix, inverse DCT, store |
| 6 | fill | one color for all 64 pixels |
| 7 | inter | motion copy as type 2, DC from bundle 8, coefficients and quantizer, inter matrix, inverse DCT added to the pixels |
| 8 | pattern | two colors, then 8 pattern bytes, one per row top to bottom; bit *j* of a byte (LSB first) picks the color of column *j* |
| 9 | raw | 64 colors in raster order |

A block-type 1 met at a position where the column or the row is odd is a placeholder for the area
of a 16x16 block decoded earlier: skip it and the next column. Motion vectors are whole pixels in
the plane being decoded (chroma vectors are not halved). The source block's top-left pixel, taken
as an offset into the plane's rows laid end to end (`(y0 + dy) * stride + x0 + dx`), must lie
between the first block's (0) and the last block's; anything else is an error, in FFmpeg and in
ours. So a vector may reach left of column 0 into the previous row's end; KOTOR's movies
never trip the check.

Kostya's 2009 posts "pattern-run blocks" and "a bunch of peculiarities" describe the block types;
MultimediaWiki's "Bink Video" lists them.

### DCT coefficients (types 5, 7, and 5 inside 1)

The 63 AC coefficients are indexed in **Bink scan order** (a table mapping index to raster
position, designed around pairs of coefficients). They are sent bit-plane by bit-plane over a
work list of groups, a little like progressive JPEG:

- 4 bits: the number of bit-planes *m*. Work through planes *b* = *m*-1 down to 0.
- The list starts as: a 20-coefficient group at 4, at 24 and at 44 (covering 4..63), then the
  single coefficients 1, 2, 3.
- Each pass walks the list from its front to its current end; entries appended during the pass
  are visited in the same pass, entries put at the front are not. A dead entry is passed over
  without reading anything. Every other entry reads 1 bit; 0 leaves it for a later plane. On 1:
  - a 20-group at *c*: its first four coefficients *c*..*c*+3 are resolved now (below) and the
    entry becomes a 16-group at *c*+4, which is examined again at once (another bit);
  - a 16-group at *c*: becomes the 4-group at *c* (examined again at once) and appends 4-groups at
    *c*+4, *c*+8, *c*+12 to the end of the list;
  - a 4-group at *c*: dies after resolving *c*..*c*+3;
  - a single coefficient: takes its value now and dies.
- Resolving four coefficients: per coefficient 1 bit; 1 puts it at the front of the list as a
  single (it gets its value in a later plane), 0 gives it its value now.
- A value at plane *b*: if *b* = 0, magnitude 1 and a sign bit; else magnitude `2^b + (b bits)`
  and a sign bit. Sign bit 1 = negative.
- After the last plane: 4 bits quantizer index *q* (0..15).

Dequantize: every coefficient (the DC from its bundle included) becomes
`(value * Q[q][position]) >> 11` with a 32-bit product and an arithmetic shift, using the intra
or inter matrix. The matrices are 16 x 64 integers, the 16 quantizer steps being the base matrix
times 1, 4/3, 5/3, 2, 8/3, 7/2, 4, 5, 6, 8, 12, 17, 22, 28, 34, 44 (Kostya lists these) with the
inverse DCT's scale factors folded in (**[verified]**: the ratios between the DLL's 16 matrices
are these steps, to within rounding). Take the matrices from the DLL rather than rebuilding them: our attempt
to rebuild them from a base matrix and the IDCT scale factors came out one too low in about 4% of
the entries.

Inverse DCT: an 8x8 integer version of the Arai-Agui-Nakajima fast IDCT (the same butterfly as
IJG's `jidctfst.c`) with Q11 constants 2896 (sqrt 2), 2217, 3784 and -5352, products shifted right
by 11; columns first without rounding, then rows with the result `(x + 127) >> 8`. Results are
stored (or, for inter blocks, added) as the low 8 bits, without clamping, which is what FFmpeg
does. FFmpeg's `binkdsp.c` is the reference to read; Kostya's "Bink encoder: doing DCT" discusses
the transform's precision.

Kostya's "Bink: 'lossless' block coding" and "Bink encoder: coefficients coding" describe this
coding.

### Residue (type 4)

Pixel differences, no transform, coded with the same kind of list:

- 7 bits: mask count *M*. 3 bits: *s*; the mask starts at `1 << s` and halves each pass down to 1.
- The list starts as the three 20-groups (4, 24, 44) followed by the 4-group at 0 (the "DC"
  position is a residue like any other here).
- Each pass first walks the coefficients already non-zero, in the order they became non-zero:
  1 bit each; set adds the mask to the magnitude (away from zero). Then it walks the list as for
  DCT coefficients, except that a value is just plus or minus the mask (a sign bit), and each newly
  non-zero coefficient joins the non-zero list.
- Every applied mask (an addition or a new value) counts; decoding stops at once, mid-pass, after
  *M* + 1 of them.

The 64 values land at raster positions through the Bink scan table and are added to the
motion-compensated pixels (low 8 bits). Kostya's "Bink: 'lossy' coefficients reading" describes
exactly this.

### Revision differences

KOTOR needs only `i`. For the record **[docs]**:

- `i`: adds the u32 before the alpha and luma planes; colors are plain bytes.
- `h`, `i`: chroma coded V then U; `f`, `g`: U then V.
- `f`, `g`, `h`: colors in sign-and-magnitude around 128 (above).
- `k` (later SDKs): an extra header field, the block-type count XORed with 0xBB, a per-plane
  "fill with one value" flag, full-range color.
- `d`: no known samples; integer DCT, no 16x16 blocks, its own block numbering.
- `b` (Heroes of Might and Magic III era): a different codec in the same spirit: no Huffman
  coding (fixed-width bundle values), floating-point DCT, other block types and quantizers, one
  frame buffer for both reference and output. See Kostya's posts on old Bink.

## Audio bitstream (Bink audio, DCT variant)

**[verified]** bit-exactly: `bikprobe.py` walks every block of every packet in all 60 tracks
(37366 blocks, ending exactly at each packet's end), and its reference decoder
(`--decode-audio`) matches FFmpeg's output for `01c.bik` (44.1 kHz) and `56b.bik` (48 kHz) to
within 0.02 of an int16 step before rounding.

### Parameters

- Block length *N* (coefficients per channel): 2048 for rates >= 44100, 1024 for rates >= 22050,
  512 below. KOTOR: 2048. Overlap *L* = *N*/16 = 128. Each block yields *N* - *L* = 1920 samples
  per channel.
- Band edges: with *H* = (rate + 1) / 2 (integer division) and the critical frequencies
  *F* = 100, 200, 300, 400, 510, 630, 770, 920, 1080, 1270, 1480, 1720, 2000, 2320, 2700, 3150,
  3700, 4400, 5300, 6400, 7700, 9500, 12000, 15500 Hz (MultimediaWiki lists them, plus a 24500
  that the band count never consults): the band count *B* is 1 plus the number of leading *F*
  below *H*, at most 25; KOTOR's rates give *B* = 25. Band *i* starts at coefficient
  `start[0] = 2`, `start[i] = (F[i-1] * N / H)` rounded down to even (i = 1..*B*-1), and
  `start[B] = N`.

### A packet

After the u32 decoded size: blocks until the packet ends, each starting on a 32-bit boundary
(counted from the packet start). A DCT block:

```
2 bits                   unknown; always 0 in KOTOR (37366 blocks)
for each channel (left, then right):
    X[0], X[1]           two 29-bit floats: 5-bit exponent e, 23-bit mantissa m, sign bit;
                         value m * 2^(e - 23), negated if the sign bit is 1
    B x 8 bits           band quantizer indices
    coefficients 2..N-1 in groups:
        1 bit            1: 4 bits r, group length 8 * {2,3,4,5,6,8,9,10,11,12,13,14,15,16,32,64}[r]
                         0: group length 8
                         (a group stops at N)
        4 bits width w   0: the group is all zero
                         else per coefficient: w bits magnitude, then a sign bit if non-zero
pad to 32 bits
```

### Reconstruction

1. Dequantize: `X[k] = magnitude * sign * 10^(0.0664 * min(qi, 95))` where *qi* is the quantizer
   index of the band containing *k* (`start[i] <= k < start[i+1]`). `X[0]`, `X[1]` are used as
   read.
2. Transform each channel:
   `y[t] = (2 / sqrt(N)) * sum over k = 0..N-1 of X[k] * cos(pi * k * (t + 1/2) / N)`,
   t = 0..N-1. This is a DCT-III in which `X[0]` has the same weight as the others. The result is
   already in int16 units.
3. Overlap: the block outputs `y[0 .. N-L-1]`. For every block after the first of the track,
   first cross-fade `y[0 .. L-1]` with the previous block's `y[N-L .. N-1]` (kept from before):
   `out = prev * (1 - w) + cur * w` with `w = (t * C + c) / (L * C)` for channel *c* of *C*. The
   ramp runs over the interleaved sample index, so the right channel's weights are slightly
   ahead; a plain per-channel ramp differs from FFmpeg by up to 64 steps.
4. Round and clamp to int16: values do exceed the range (peaks of 33394 in `01c.bik` and 38881
   in `56b.bik`).
5. Trim: keep only as many samples as the `decoded` fields add up to (only the last packet's
   block is cut short).

The RDFT variant (flag `0x1000` clear, not in KOTOR) interleaves the channels into one signal of
twice the block length, codes one set of coefficients and uses an inverse real FFT; revision `b`
writes the first two coefficients as 32-bit floats and groups coefficients by 16. Bink Audio 2
(later) codes 7-bit quantizer indices and sign planes. None of this is needed here.

## Tables: where to get them

The video decoder needs the 16 Huffman trees, the scan order, the 16 run-block scan patterns and
the intra and inter quantizer matrices. Their only public text form is FFmpeg's
`libavcodec/binkdata.h` (LGPL, also mirrored in ScummVM and xoreos under the GPL), which we must
not copy. The same tables ship with the game in `binkw32.dll`, and the install is the project's
data source.

**Decision:** the ctxlang decoder reads them from `<install>/binkw32.dll` at startup
(`lib/video/bink_tables.ctx`). It doesn't rely on the offsets below: it looks for each table by
its shape (sixteen 4s for the code lengths, 0..15 for the codes, a permutation of 0..63 starting
at 0 for the scan, ...) and accepts a region only if its CRC-32 is the one below, so any DLL build
holding the tables works; without them the game skips its movies rather than crash
([docs/design/video.md](../design/video.md#the-tables-read-from-the-installs-binkw32dll)).
`bikprobe.py --dll` checks the same CRCs at the fixed offsets. Offsets are file offsets into
binkw32.dll 1.5v (they sit in its `.rdata` and `BINKDATA` sections):

| Table | File offset | Bytes | Layout | CRC-32 |
|---|---|---|---|---|
| Huffman code lengths | 0x39A48 | 256 | 16 trees x 16 u8, code index order | f2c3ec57 |
| Huffman codes | 0x39B50 | 256 | 16 trees x 16 u8, read LSB first | a2739da1 |
| DCT scan | 0x39C60 | 64 | u8 raster position of scan index 0..63 | 8fbdd9f2 |
| run-block patterns | 0x39CA8 | 1024 | 16 x 64 u8 raster positions in fill order | f9e3218a |
| intra quantizers | 0x3A0C0 | 4096 | 16 x 64 i32, **raster** order | d53c4639 |
| inter quantizers | 0x3C100 | 4096 | 16 x 64 i32, **raster** order | c4f4dcd3 |
| block-type repeats | 0x3E648 | 4 | u8: 4, 8, 12, 32 | 37ee7637 |
| audio group lengths | 0x44840 | 16 | u8: 2, 3, 4, 5, 6, 8, ..., 16, 32, 64 | 7c59d03f |
| audio band edges | 0x44850 | 104 | u32: 0, 100, 200, ..., 15500, then 0 | 67e0ebbd |

**[verified]**: every region matches FFmpeg's tables value for value. The quantizer matrices are
stored by raster position in the DLL (FFmpeg stores them by scan index), so a coefficient at
raster position *p* uses `Q[q][p]`. The small audio tables and the critical frequencies are also
printed on MultimediaWiki, so the audio decoder may simply embed them.

## Checking a decoder

FFmpeg's Bink decoders make a convenient oracle, run as a program (its code is not copied). The
`imageio-ffmpeg` wheel bundles a static FFmpeg 7.1 build with `binkvideo` and `binkaudio_dct`:

```
python -m pip download imageio-ffmpeg --no-deps -d <dir>
python -m zipfile -e <dir>/imageio_ffmpeg-*.whl <dir>/ff        # ffmpeg-win-x86_64-v7.1.exe inside
ffmpeg -i 02.bik -frames:v 30 -f rawvideo -pix_fmt yuv420p 02.yuv      # exact planes, frames 0-29
ffmpeg -i 02.bik -vf "select=eq(n\,120)" -frames:v 1 02_120.png        # one frame as a picture
ffmpeg -i 01c.bik -map 0:a -f f32le -c:a pcm_f32le 01c.f32             # audio, float, x32768 = int16
```

Already done with it **[verified]**: FFmpeg decodes all 61 movies without an error and with the
header's frame count; `kotor/out/bink/*.png` holds frame 120 of `01a`, `02`, `biologo` and
`leclogo` (and `02` with the chroma planes swapped). FFmpeg's audio output keeps the whole last
block (it ignores the `decoded` field), so compare all but the final block.

## Sources

Public prose descriptions (read freely):

- MultimediaWiki, [Bink Container](https://wiki.multimedia.cx/index.php/Bink_Container): header,
  track tables, frame index, frame layout. Two errors noted above (track buffer field, chroma
  order).
- MultimediaWiki, [Bink Video](https://wiki.multimedia.cx/index.php/Bink_Video): planes, the
  Huffman tree description with examples, the bundle formats, the block types. Incomplete (the
  coefficient sections are empty) and its pseudo-code has slips; use it for the overall shape.
- MultimediaWiki, [Bink Audio](https://wiki.multimedia.cx/index.php/Bink_Audio): block sizes,
  bands, float format, quantizers, overlap, the critical-frequency and run tables. Its block sizes
  and band formula are in different units from the ones above (which are verified).
- Kostya Shishkov's blog (he reverse-engineered Bink video for FFmpeg):
  - [Bink: 'lossy' coefficients reading](https://codecs.multimedia.cx/2009/08/bink-lossy-coefficients-reading/)
    (2009): the residue mask list, step by step.
  - [Bink: 'lossless' block coding](https://codecs.multimedia.cx/2009/09/bink-lossless-block-coding/)
    (2009): how DCT coefficient coding differs from it.
  - [Bink: a bunch of peculiarities](https://codecs.multimedia.cx/2009/09/bink-a-bunch-of-peculiarities/)
    (2009): bundles, 16x16 blocks, the 16 quantizer steps.
  - [Bink: pattern-run blocks](https://codecs.multimedia.cx/2009/09/bink-pattern-run-blocks/)
    (2009): run blocks and their 16 scan patterns.
  - [A bit about old Bink](https://codecs.multimedia.cx/2010/03/a-bit-about-old-bink/),
    [Maybe the last word about Bink version b](https://codecs.multimedia.cx/2010/11/maybe-the-last-word-about-bink-version-b/),
    [Nonexistent beast: Bink-d](https://codecs.multimedia.cx/2011/03/nonexistent-beast-bink-d/):
    revisions `b` and `d`.
  - The 2023 encoder series, the best overview of the design:
    [format and encoder designs](https://codecs.multimedia.cx/2023/10/bink-encoding-format-and-encoder-designs/),
    [bitstream bundling](https://codecs.multimedia.cx/2023/10/bink-bitstream-bundling/),
    [doing DCT](https://codecs.multimedia.cx/2023/10/bink-encoder-doing-dct/),
    [coefficients coding](https://codecs.multimedia.cx/2023/10/bink-encoder-coefficients-coding/),
    [Encoding Bink Audio](https://codecs.multimedia.cx/2023/10/encoding-bink-audio/).
  - The [Bink category](https://codecs.multimedia.cx/category/game-video/bink/) lists the rest
    (mostly Bink 2, which KOTOR doesn't use).
- Mike Melanson, [Description of the Bink File Format](http://multimedia.cx/bink-format.txt)
  (2003): the first header notes; superseded by the wiki.

Implementations (read to understand only; never copy, port or closely translate):

- FFmpeg (LGPL 2.1+): [libavformat/bink.c](https://github.com/FFmpeg/FFmpeg/blob/master/libavformat/bink.c)
  (demuxer), [libavcodec/bink.c](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/bink.c)
  (video: bundles, trees, blocks, coefficient lists),
  [binkdsp.c](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/binkdsp.c) (IDCT, 2x
  scaling, residue add), [binkdata.h](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/binkdata.h)
  (tables: use the DLL instead),
  [binkaudio.c](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/binkaudio.c) (audio).
- ScummVM (GPL): [video/bink_decoder.cpp](https://github.com/scummvm/scummvm/blob/master/video/bink_decoder.cpp),
  a readable single-file decoder of `f` to `i` (video and both audio variants).
- xoreos (GPL): [src/video/bink.cpp](https://github.com/xoreos/xoreos/blob/master/src/video/bink.cpp),
  derived from the above, used for BioWare games.
- NihAV ([nihav.org](https://nihav.org/)): Kostya's own Rust implementation (`nihav-rad`).

## Checked

```
python kotor/tools/py/bikprobe.py            # every movies/*.bik: header, index, frames, audio bitstream
python kotor/tools/py/bikprobe.py --dll      # the codec tables in binkw32.dll
python kotor/tools/py/bikprobe.py --decode-audio F:/.../movies/01c.bik kotor/extract/bink/01c.wav
```

Results (2026-10-03, Steam install): **61 files, 0 failures**; `--dll`: all 9 tables match.

The ctxlang decoder, against FFmpeg 7.1 as the oracle (needs `ffmpeg` on PATH):

```
kotor/tools/ctxc run kotor/tools/binkcheck -- --ref              # every movie, video and audio
kotor/tools/ctxc run kotor/tools/bink2png -- 02 --from 120 --to 120   # kotor/out/bink/02_0120.png
```

Results (2026-10-03): **61 movies, 0 failures; 48752 of 48752 frames byte for byte FFmpeg's**;
143378834 audio samples compared, 113172 (0.08%) differ, all by 1 (float32 against float64
rounding); 0.93 ms per frame on average, 3.7 ms at most (Ryzen 9 5900X, -O2).

- All `BIKi`; 640 x 272 (53), 640 x 360 (5), 640 x 480 (3); all 2997/100 fps; video flags 0.
- 48752 frames, 1626.7 s (27.1 min); 61 keyframes (frame 0 of each file); 584 MB video,
  21.8 MB audio (2872 + 107 kbit/s on average).
- 60 audio tracks, all flags `0x7000` (DCT, stereo, 16-bit), id 0; 59 at 44100 Hz, 1 at
  48000 Hz; buffer fields 138240 / 145920 = first packet's decoded size.
- Audio packets: 36345 non-empty (36285 with one block, 59 with 18, 1 with 19) and 12257 empty;
  37366 blocks walked, all ending exactly at their packet's end, all leading bit pairs 0; every
  track's audio length equals its video length.
- Video: the leading u32 always lies in the packet and is 32-bit aligned.
- FFmpeg (oracle) decodes all 61 files without errors.

| File | Rev | W x H | fps | Frames | Seconds | Audio | Audio packets (empty) | Blocks | MB |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| 01a.bik | BIKi | 640 x 272 | 29.970 | 3606 | 120.32 | 44100 Hz 2ch DCT | 2747 (859) | 2764 | 42.10 |
| 01c.bik | BIKi | 640 x 272 | 29.970 | 499 | 16.65 | 44100 Hz 2ch DCT | 366 (133) | 383 | 6.67 |
| 01f.bik | BIKi | 640 x 272 | 29.970 | 275 | 9.18 | 44100 Hz 2ch DCT | 194 (81) | 211 | 3.66 |
| 01g.bik | BIKi | 640 x 272 | 29.970 | 324 | 10.81 | 44100 Hz 2ch DCT | 232 (92) | 249 | 3.76 |
| 02.bik | BIKi | 640 x 360 | 29.970 | 1128 | 37.64 | 44100 Hz 2ch DCT | 848 (280) | 865 | 14.60 |
| 03.bik | BIKi | 640 x 272 | 29.970 | 1258 | 41.98 | 44100 Hz 2ch DCT | 948 (310) | 965 | 11.63 |
| 05.bik | BIKi | 640 x 272 | 29.970 | 613 | 20.45 | 44100 Hz 2ch DCT | 453 (160) | 470 | 7.54 |
| 05_1c.bik | BIKi | 640 x 272 | 29.970 | 777 | 25.93 | 44100 Hz 2ch DCT | 579 (198) | 596 | 10.01 |
| 05_2a.bik | BIKi | 640 x 272 | 29.970 | 801 | 26.73 | 44100 Hz 2ch DCT | 597 (204) | 614 | 10.44 |
| 05_2c.bik | BIKi | 640 x 272 | 29.970 | 579 | 19.32 | 44100 Hz 2ch DCT | 427 (152) | 444 | 7.74 |
| 05_3a.bik | BIKi | 640 x 272 | 29.970 | 974 | 32.50 | 44100 Hz 2ch DCT | 730 (244) | 747 | 12.67 |
| 05_3c.bik | BIKi | 640 x 272 | 29.970 | 740 | 24.69 | 44100 Hz 2ch DCT | 551 (189) | 568 | 9.30 |
| 05_4a.bik | BIKi | 640 x 272 | 29.970 | 1078 | 35.97 | 44100 Hz 2ch DCT | 810 (268) | 827 | 12.16 |
| 05_4c.bik | BIKi | 640 x 272 | 29.970 | 740 | 24.69 | 44100 Hz 2ch DCT | 551 (189) | 568 | 9.75 |
| 05_5a.bik | BIKi | 640 x 272 | 29.970 | 810 | 27.03 | 44100 Hz 2ch DCT | 604 (206) | 621 | 10.77 |
| 05_5c.bik | BIKi | 640 x 272 | 29.970 | 771 | 25.73 | 44100 Hz 2ch DCT | 574 (197) | 591 | 10.19 |
| 05_7a.bik | BIKi | 640 x 272 | 29.970 | 862 | 28.76 | 44100 Hz 2ch DCT | 644 (218) | 661 | 10.96 |
| 05_7c.bik | BIKi | 640 x 272 | 29.970 | 517 | 17.25 | 44100 Hz 2ch DCT | 380 (137) | 397 | 6.78 |
| 05_8a.bik | BIKi | 640 x 272 | 29.970 | 1053 | 35.14 | 44100 Hz 2ch DCT | 791 (262) | 808 | 13.68 |
| 05_8c.bik | BIKi | 640 x 272 | 29.970 | 397 | 13.25 | 44100 Hz 2ch DCT | 288 (109) | 305 | 4.71 |
| 05_8e.bik | BIKi | 640 x 272 | 29.970 | 453 | 15.12 | 44100 Hz 2ch DCT | 331 (122) | 348 | 5.69 |
| 05_9.bik | BIKi | 640 x 272 | 29.970 | 466 | 15.55 | 44100 Hz 2ch DCT | 341 (125) | 358 | 5.81 |
| 05r.bik | BIKi | 640 x 272 | 29.970 | 615 | 20.52 | 44100 Hz 2ch DCT | 455 (160) | 472 | 7.52 |
| 06a.bik | BIKi | 640 x 272 | 29.970 | 917 | 30.60 | 44100 Hz 2ch DCT | 686 (231) | 703 | 11.05 |
| 07_1.bik | BIKi | 640 x 272 | 29.970 | 112 | 3.74 | 44100 Hz 2ch DCT | 69 (43) | 86 | 1.20 |
| 07_2.bik | BIKi | 640 x 272 | 29.970 | 96 | 3.20 | 44100 Hz 2ch DCT | 57 (39) | 74 | 0.89 |
| 07_3.bik | BIKi | 640 x 272 | 29.970 | 117 | 3.90 | 44100 Hz 2ch DCT | 73 (44) | 90 | 1.28 |
| 07_4.bik | BIKi | 640 x 272 | 29.970 | 156 | 5.21 | 44100 Hz 2ch DCT | 103 (53) | 120 | 1.50 |
| 08.bik | BIKi | 640 x 272 | 29.970 | 489 | 16.32 | 44100 Hz 2ch DCT | 358 (131) | 375 | 5.20 |
| 09.bik | BIKi | 640 x 360 | 29.970 | 1837 | 61.29 | 44100 Hz 2ch DCT | 1391 (446) | 1408 | 23.82 |
| 0a.bik | BIKi | 640 x 272 | 29.970 | 284 | 9.48 | 44100 Hz 2ch DCT | 201 (83) | 218 | 3.73 |
| 0b.bik | BIKi | 640 x 272 | 29.970 | 284 | 9.48 | 44100 Hz 2ch DCT | 201 (83) | 218 | 3.75 |
| 0c.bik | BIKi | 640 x 272 | 29.970 | 284 | 9.48 | 44100 Hz 2ch DCT | 201 (83) | 218 | 3.73 |
| 0d.bik | BIKi | 640 x 272 | 29.970 | 284 | 9.48 | 44100 Hz 2ch DCT | 201 (83) | 218 | 3.75 |
| 11a.bik | BIKi | 640 x 272 | 29.970 | 633 | 21.12 | 44100 Hz 2ch DCT | 469 (164) | 486 | 7.99 |
| 11b.bik | BIKi | 640 x 272 | 29.970 | 771 | 25.73 | 44100 Hz 2ch DCT | 574 (197) | 591 | 9.72 |
| 17.bik | BIKi | 640 x 272 | 29.970 | 717 | 23.92 | 44100 Hz 2ch DCT | 533 (184) | 550 | 9.35 |
| 17a.bik | BIKi | 640 x 272 | 29.970 | 701 | 23.39 | 44100 Hz 2ch DCT | 521 (180) | 538 | 7.90 |
| 22a.bik | BIKi | 640 x 272 | 29.970 | 541 | 18.05 | 44100 Hz 2ch DCT | 398 (143) | 415 | 6.07 |
| 22b.bik | BIKi | 640 x 272 | 29.970 | 438 | 14.61 | 44100 Hz 2ch DCT | 319 (119) | 336 | 5.58 |
| 23a.bik | BIKi | 640 x 272 | 29.970 | 860 | 28.70 | 44100 Hz 2ch DCT | 643 (217) | 660 | 10.87 |
| 23b.bik | BIKi | 640 x 272 | 29.970 | 425 | 14.18 | 44100 Hz 2ch DCT | 309 (116) | 326 | 4.69 |
| 26a.bik | BIKi | 640 x 272 | 29.970 | 280 | 9.34 | 44100 Hz 2ch DCT | 198 (82) | 215 | 3.44 |
| 26b.bik | BIKi | 640 x 272 | 29.970 | 976 | 32.57 | 44100 Hz 2ch DCT | 731 (245) | 748 | 11.53 |
| 31a.bik | BIKi | 640 x 360 | 29.970 | 2856 | 95.30 | 44100 Hz 2ch DCT | 2172 (684) | 2189 | 37.70 |
| 33.bik | BIKi | 640 x 272 | 29.970 | 1246 | 41.57 | 44100 Hz 2ch DCT | 938 (308) | 955 | 16.48 |
| 43.bik | BIKi | 640 x 272 | 29.970 | 1193 | 39.81 | 44100 Hz 2ch DCT | 898 (295) | 915 | 14.34 |
| 50.bik | BIKi | 640 x 360 | 29.970 | 2035 | 67.90 | 44100 Hz 2ch DCT | 1543 (492) | 1560 | 25.99 |
| 50b.bik | BIKi | 640 x 272 | 29.970 | 464 | 15.48 | 44100 Hz 2ch DCT | 339 (125) | 356 | 6.04 |
| 51.bik | BIKi | 640 x 272 | 29.970 | 1068 | 35.64 | 44100 Hz 2ch DCT | 802 (266) | 819 | 12.99 |
| 51b.bik | BIKi | 640 x 272 | 29.970 | 463 | 15.45 | 44100 Hz 2ch DCT | 338 (125) | 355 | 6.00 |
| 54.bik | BIKi | 640 x 272 | 29.970 | 1834 | 61.19 | 44100 Hz 2ch DCT | 1389 (445) | 1406 | 24.21 |
| 54b.bik | BIKi | 640 x 272 | 29.970 | 354 | 11.81 | 44100 Hz 2ch DCT | 255 (99) | 272 | 4.57 |
| 55.bik | BIKi | 640 x 272 | 29.970 | 1250 | 41.71 | 44100 Hz 2ch DCT | 941 (309) | 958 | 16.40 |
| 56.bik | BIKi | 640 x 272 | 29.970 | 1671 | 55.76 | 44100 Hz 2ch DCT | 1264 (407) | 1281 | 21.35 |
| 56b.bik | BIKi | 640 x 360 | 29.970 | 1329 | 44.34 | 48000 Hz 2ch DCT | 1091 (238) | 1109 | 16.63 |
| biologo.bik | BIKi | 640 x 480 | 29.970 | 260 | 8.68 | 44100 Hz 2ch DCT | 183 (77) | 200 | 3.37 |
| leclogo.bik | BIKi | 640 x 480 | 29.970 | 264 | 8.81 | 44100 Hz 2ch DCT | 186 (78) | 203 | 3.27 |
| legal.bik | BIKi | 640 x 480 | 29.970 | 150 | 5.01 | none | 0 (0) | 0 | 0.86 |
| LIVE_1a.bik | BIKi | 640 x 272 | 29.970 | 1021 | 34.07 | 44100 Hz 2ch DCT | 766 (255) | 783 | 11.87 |
| Live_1c.bik | BIKi | 640 x 272 | 29.970 | 756 | 25.23 | 44100 Hz 2ch DCT | 563 (193) | 580 | 8.82 |
