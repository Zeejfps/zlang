# TPC (compiled texture)

A TPC is KOTOR's compiled texture: a 128-byte header, then the pixel data of one image (or six cube
faces, or a flipbook's frames) with its mip chain, in DXT1, DXT5 or uncompressed grey/RGB/RGBA,
then optionally the texture's TXI text. Every texture the game ships is a TPC except the area
lightmaps, fourteen water bump maps and one legacy image, which are TGA ([tga.md](tga.md)). What the TXI keywords do
when rendering is in [txi-render.md](txi-render.md); the TXI syntax is in [txi.md](txi.md).

All integers are little-endian. Sources are marked: *data* = checked on every TPC in the install by
`tools/py/tpcprobe.py` (see [Checked](#checked)); *exe* = strings in `swkotor.exe`; *community* =
public modding documentation; *inferred* = our reading, not verified.

## Where

Resource type 3007, extension `tpc`. No magic number.

| Container | TPCs | Holds |
|---|---|---|
| `TexturePacks/swpc_tex_tpa.erf` | 3,294 | world, creature, item and effect textures, full quality |
| `TexturePacks/swpc_tex_tpb.erf` | 3,294 | the same names at half size ([below](#the-three-quality-packs)) |
| `TexturePacks/swpc_tex_tpc.erf` | 3,294 | the same names at quarter size |
| `TexturePacks/swpc_tex_gui.erf` | 1,570 | GUI art, icons, portraits, fonts, loading screens; no name shared with the packs |
| `patch.erf` | 84 | 1280x1024 GUI backgrounds, `cyclearrow1/2`, 75 female player heads (`pfha01`..`pfhc05` with suffixes `d`, `d1`..`d3`) |

Total 11,536 (*data*). There are none in the BIFs, modules, `rims/` or saves; `Override/` is empty
in this install. Only one of tpa/tpb/tpc is mounted, chosen by the Texture Quality setting through
`texpacks.2da` ([resources.md](resources.md)).

| Format | Files | Kind | Files |
|---|---|---|---|
| DXT1 | 5,311 | plain (one image) | 11,226 |
| DXT5 | 4,511 | cube map | 189 (all DXT5) |
| RGBA, uncompressed | 1,495 | flipbook (`proceduretype cycle`) | 121 (105 DXT1, 16 DXT5) |
| RGB, uncompressed | 207 | | |
| grey, uncompressed | 12 | | |

Sizes run from 2x2 to 2048x1024; the commonest are 64x64 (2,616), 128x128 (2,584), 256x256
(2,219), 32x32 (1,385) and 512x512 (1,157). Every dimension is a power of two except cube maps
(width x 6·width) (*data*).

## Layout

```
0        header, 128 bytes
128      pixel data: image 0 (its mip levels, largest first), then image 1, ... (images = 1, 6 faces, or N frames)
128 + P  TXI text, optional, to the end of the file (no length field, no terminator)
```

### Header (128 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 4 | u32 | DataSize | 0 = uncompressed. Non-zero = DXT-compressed; normally the byte size of one image's top level, but see [quirks](#quirks) |
| 4 | 4 | f32 | AlphaMean | mean alpha of image 0's top level, 0.0 .. 1.0 (1.0 when there is no alpha) |
| 8 | 2 | u16 | Width | width of one image; cube map: face size; flipbook: the whole grid |
| 10 | 2 | u16 | Height | height of one image; cube map: 6 x face size; flipbook: the whole grid |
| 12 | 1 | u8 | Encoding | 1 = grey, 2 = RGB, 4 = RGBA (no other value occurs) |
| 13 | 1 | u8 | MipCount | levels per image, at least 1; always 1 for flipbooks |
| 14 | 114 | bytes | padding | zero in all 11,536 files |

**AlphaMean.** Community descriptions call the float at 4 an "alpha test" value. In the data it is
the mean alpha of the top level: it equals the mean of the decoded alpha channel within 0.005 in
4,847 and within 0.02 in all of the 4,948 TPCs in tpa, gui and `patch.erf` (*data*). The tpb and tpc
copies carry tpa's value unchanged, so in 104 of them (all bump/normal maps) it no longer matches
their own pixels. The TXI keyword `alphamean` overrides it (the one user, `lda_gobo1`, has 0.365 in the header
and `alphamean 0.01`). What the engine does with it is not known; most likely it decides whether a
texture is treated as transparent (*inferred*).

### Pixel format

| DataSize | Encoding | Format | Bytes per level of w x h |
|---|---|---|---|
| 0 | 1 | grey, 1 byte per texel | w·h |
| 0 | 2 | RGB, bytes R, G, B | 3·w·h |
| 0 | 4 | RGBA, bytes R, G, B, A | 4·w·h |
| non-zero | 2 | DXT1 (BC1), 8 bytes per 4x4 block | max(1, ⌈w/4⌉) · max(1, ⌈h/4⌉) · 8 |
| non-zero | 4 | DXT5 (BC3), 16 bytes per 4x4 block | max(1, ⌈w/4⌉) · max(1, ⌈h/4⌉) · 16 |
| non-zero | 1 | does not occur; reject | |

The encoding byte, not DataSize, picks DXT1 or DXT5 (*data*). The rule some readers use instead
("DataSize = w·h/2 means DXT1, = w·h means DXT5") misreads the 23 small DXT1 files whose DataSize
is 16, every flipbook and every cube map. Uncompressed data is R, G, B(, A) in that order, not
TGA's B, G, R (*data*: portraits decode with natural skin tones, normal maps decode to the flat
(128, 128, 255)).

### Mip chains

Level k of a w x h image is max(1, w >> k) x max(1, h >> k), largest first. A DXT level smaller
than 4x4 still takes one whole block (8 or 16 bytes), so the 2x2 and 1x1 levels of a DXT5 texture
are 16 bytes each (*data*). MipCount is either 1 or the full chain down to 1x1,
⌊log2(max(w, h))⌋ + 1 levels (512x64 has 10); no file has a partial chain (*data*: 8,375 plain
textures with a full chain, 2,851 with one level, 189 cube maps with full chains, 121 flipbooks
with MipCount 1).

### Which kind of image, and where the TXI starts

Decide in this order; it accounts for every byte of every TPC in the install (*data*):

1. **Cube map** if `Height == 6 * Width`. Six square faces of Width x Width, face-major: face 0's
   MipCount levels, then face 1's, and so on. `P = 6 * chain(Width, Width, MipCount)`.
2. **Flipbook** if `DataSize != 0`, `MipCount == 1` and `DataSize` is larger than one
   Width x Height level. The pixel data is exactly `P = DataSize` bytes. Read `numx` and `numy`
   from the TXI text at `128 + DataSize`; the data holds `numx * numy` frames of
   (Width / numx) x (Height / numy), frame-major, **each with its own full mip chain** down to 1x1.
3. Otherwise **plain**: one image, `P = chain(Width, Height, MipCount)`.

`chain(w, h, n)` is the sum of the n level sizes above. Compute level sizes from the dimensions;
never step through levels with DataSize. The TXI is the bytes from `128 + P` to the end of the
file.

Checks that hold on every file (*data*): every file with Height = 6·Width has TXI `cube 1` and
every `cube 1` file has Height = 6·Width; every file rule 2 picks has `proceduretype cycle` with
`numx`/`numy`, and every TPC with `proceduretype cycle` is picked by rule 2; for those 121,
DataSize equals numx·numy·chain(frame) exactly; the bytes after P are always printable text;
no file is short. Face-major and frame-major order (rather than all top levels first) is confirmed
by content: each image's second level matches a 2x downsample of its own first level in all 63
cube maps and 40 flipbooks of tpa.

### TXI text

6,180 TPCs carry TXI text after the pixels, 5,356 end exactly at `128 + P` (*data*). The text has
CRLF line ends; 5,343 end with CRLF and the rest stop mid-line with no newline. There is no NUL
terminator. Keywords and values: [txi-render.md](txi-render.md). In the shipped data no TPC also
has a standalone `.txi` of the same name with content (the one shared name, `grass`, has no
embedded text), so which source wins cannot be seen in the data ([txi.md](txi.md)).

## Orientation

**Rows are stored bottom row first; columns left to right** (*data*). Drawn with row 0 at the top,
the font sheets, the BioWare logo (`biowarelogo`), `lmg_numbers` and every portrait come out upside
down; with the rows reversed they read correctly and are not mirrored. This is the same order as a
TGA with a bottom-left origin (all shipped TGAs, [tga.md](tga.md)) and as OpenGL's: upload the rows
in file order and texture coordinate v = 0 is the first stored row, the bottom of the picture. The
font glyph tables agree: character 0's upper-left corner is at v = 1.0
([txi-render.md](txi-render.md#fonts)). It holds for every level, cube face and flipbook frame.

A loader that wants a top-down image (to write a PNG, say) reverses the rows; a GL backend uploads
as stored.

## DXT decoding

Standard S3TC: DXT1 = BC1, DXT5 = BC3. Each block is 4x4 texels, blocks in rows left to right, block
rows in file order (bottom first, as above). Two facts from the data make the usual ambiguities
irrelevant:

- **DXT1** blocks with color0 <= color1 (the three-colour mode, whose index 3 is transparent black)
  occur, but no texel inside an image uses the transparent index: it appears only in the padding
  texels of 2x2 and 1x1 levels (*data*: 1,688 such levels, 0 transparent texels in bounds). So DXT1
  can be treated as opaque, as Encoding 2 = RGB says: upload as `GL_COMPRESSED_RGB_S3TC_DXT1_EXT`,
  or decode with alpha 255.
- **DXT5** colour blocks never have color0 == color1, and the 1,191,840 top-level blocks with
  color0 < color1 (of 13.3 million) use only indices 0 and 1 (*data*). Decode DXT5 colour in
  four-colour mode always (the S3TC rule); a decoder that switches modes on endpoint order gives the
  same result here. Alpha uses the usual two modes (alpha0 > alpha1: 8 values; otherwise 6 values
  plus 0 and 255).

`swkotor.exe` asks for `GL_EXT_texture_compression_s3tc` and `GL_ARB_texture_compression` (*exe*),
so the original engine uploads DXT data compressed. For our GL 4.1 core backend S3TC is an
extension, not core; desktop drivers on Windows, Linux and macOS expose it, but keep a CPU decoder
for a backend that lacks it.

## Cube maps

189 files: 63 names (`cm_*`, `mycube`, `window`, `lte_cubemap`) in each quality pack; all DXT5 with
full mip chains, faces of 8 to 256 texels (tpa: 32 x15, 64 x35, 128 x9, 256 x3, 8 x1), alpha 255
everywhere, TXI `cube 1` (*data*). `envmaptexture` and `bumpyshinytexture` name them
([txi-render.md](txi-render.md)).

- **Face order** is OpenGL's (`GL_TEXTURE_CUBE_MAP_POSITIVE_X + i`): +X, -X, +Y, -Y, +Z, -Z.
- **Lookups use world-space directions with Z up**, KOTOR's up axis: in outdoor maps the +Z face is
  sky and -Z ground (e.g. `cm_tat`), and faces 0..3 show the horizon (*data*).
- **Faces 0 to 4 are stored exactly as OpenGL expects** when rows are uploaded in file order.
- **Face 5 (-Z) is stored upside down: reverse its rows** (at every level) before uploading.

Evidence (*data*, `tpcprobe.py cubeseams` and `pano`): we sampled each tpa cube map the way GL does
and measured the colour difference across all 24 cube edges. Turning or mirroring any of faces 0..3
raises the mean edge difference by 6 to 8 levels (of 255), face 4 by 1 to 2. Reversing face 5's
rows lowers it clearly in 17 of 63 maps (`cm_m02abb` 55 to 7.6 on face 5's edges, `cm_m17ac` 44 to
11, `cm_raktempb` 39 to 6.6, `cm_spacetarisa` 39 to 10), leaves 44 unchanged (uniform floors and
skies) and raises it in 2 maps that are discontinuous everywhere (`cm_wintaris`, `cm_awintaris`).
Equirectangular views with the fix show continuous rooms and skylines; without it the floor is
upside down. How the engine applies the fix is not yet located in the binary; the exe uses
`GL_EXT_texture_cube_map` and builds a `NormCubeMap` (a normalisation cube map for bump mapping)
(*exe*).

Reversing the rows of DXT data without decoding: reverse the order of the block rows; inside each
block reverse the four 8-bit rows of colour indices (bytes 4..7 of a DXT1 block, 12..15 of a DXT5
block) and, for DXT5, the four 12-bit rows of the 48-bit alpha index field (bytes 2..7). For a level
less than 4 texels high the image sits in the block's first rows, so swap rows 0 and 1 of a 2-high
level and leave a 1-high level alone. Decoding to RGBA and flipping is simpler and equally fine.

## Flipbooks

121 files: 40 names in each quality pack plus `lbl_static` in the GUI pack (*data*). TXI:
`proceduretype cycle`, `numx`, `numy`, `fps` (and often `blending additive`). Grids in tpa and
gui: 2x2 (18), 1x16 (12), 4x4 (10), 1x4 (1); frames of 8x8 to 256x256 texels (2x2 to 256x256
counting the smaller packs); fps 8 to 32, mostly 16.

- Header Width x Height is the whole grid; MipCount is 1; DataSize counts every frame.
- Frame i is the i-th block of data: (Width/numx) x (Height/numy) texels with a full mip chain.
- **Playback order is storage order** (*inferred* from the data: consecutive stored frames differ
  least, e.g. the 1x16 strips show 2 to 5 times less change between neighbours than in a shuffled
  order, and the 4x4 sprite sheets `mgf_sithsheet01`, `lqa_birdsheet` are smoother row-major than
  column-major).
- The frame shown at time t is `floor(t * fps) mod (numx * numy)` (*inferred*).

Where each frame sat in the artist's original grid is not stored and not needed. A renderer can
upload the frames as layers of a 2D array texture, or reassemble an atlas the way TGA flipbooks are
laid out (frame i at column `i mod numx`, row `i div numx` counted from v = 0, see
[tga.md](tga.md#flipbooks)).

## The three quality packs

tpa, tpb and tpc hold the same 3,294 names (*data*):

| tpa texture | in tpb | in tpc |
|---|---|---|
| TXI has `downsamplemax 0` (570; no other texture has it) | byte-identical copy | byte-identical copy |
| other mip-mapped textures (2,594 plain, 63 cube) | top level dropped (of every face): half size, MipCount - 1, the remaining levels and the TXI **byte-identical** to tpa's | top two levels dropped: quarter size, MipCount - 2, byte-identical tail (8 at 4x4 lose only one level, below) |
| other single-level textures (67: 40 flipbooks, 27 others) | resampled to half size, still one level (flipbook frames get new, shorter chains) | quarter size (4 at 4x4: half) |
| smallest (12 at 4x4) | 2x2 | 2x2: no texture shrinks below 2x2 |

The header float at 4 is copied from tpa. Our engine can simply always mount tpa.

## Quirks

- DataSize is 16 in 23 DXT1 files whose top level is 8 bytes (4x4 and 2x2 textures with mip
  chains: `lko_outside`, `lza_sttic`, `script_c`, `script_h`, ...). Their sizes follow the
  dimensions; a reader that took DataSize as the level size would overrun.
- For cube maps DataSize is one face's top level (e.g. `cm_anchorhead` 32x192 DXT5: 1,024).
- The 12 grey textures (4 names x 3 packs: `lmg_water01b`, `lqa_waterbmp`, `lun_noiseb`,
  `plc_water01b`) are all procedural water height maps (`proceduretype water`).
- 99 TPCs in tpa are lightmaps (`islightmap 1` in the TXI): uncompressed RGBA, one level, e.g.
  `3dgui_a00001`, `plc_acd_a00005`, `m50aa_01a_a000ap` (*data*).
- Bump maps (`isbumpmap 1`) are stored ready to use as tangent-space normal maps (RGBA, RGB =
  normal·0.5 + 0.5, flat = (128, 128, 255), alpha 255) except the grey height maps
  ([txi-render.md](txi-render.md#bump-maps)).
- GUI backgrounds are padded to power-of-two textures (`1600x1200back` is 2048x1024).
- Several font textures share pixels; `fnt_d16x16` and `fnt_d10x10b` carry a glyph table that does
  not match their pixels ([txi-render.md](txi-render.md#fonts)).

## Checked

`kotor/tools/py/tpcprobe.py` (Python + numpy, its own DXT1/DXT5 decoder):

```
python kotor/tools/py/tpcprobe.py              # every TPC, every level of every face and frame (about 90 s)
python kotor/tools/py/tpcprobe.py samples      # upright PNGs and a contact sheet in kotor/out/tpc/
python kotor/tools/py/tpcprobe.py cubeseams    # per-face orientation search on every tpa cube map
python kotor/tools/py/tpcprobe.py pano cm_m17ac                  # panorama with the -Z fix
python kotor/tools/py/tpcprobe.py pano --t=000000 cm_m17ac       # faces as stored
```

It reads every TPC through `kres.Game().every_entry('tpc')` (the four TexturePacks ERFs,
`patch.erf`, BIFs, modules, `rims/`, Override, saves): **11,536 files, 83,218 images decoded, 0
failures.** For each file it parses the header with the rules above, requires the bytes after the
pixel data to be plain text, cross-checks cube maps and flipbooks against their TXI, decodes every
level, and tallies formats, sizes, mip counts, header floats, TXI presence, DXT block modes and the
pack relationships. The 23 DataSize quirks are reported as notes, not failures.

What was looked at (PNG via the Read tool): the font sheets (`fnt_d16x16`, `dialogfont16x16`,
upside down until the rows are reversed), portraits `po_pbastila` and `po_pcarth`, head `pfha01`,
`biowarelogo`, `lmg_numbers`, the hologram flipbook `c_holododonna`, `gui_atmoss_1` (DXT5 alpha),
a contact sheet of 123 textures (every 40th of tpa and gui) (colours natural, alpha over a checkerboard), the normal maps, and
cube map panoramas of `cm_tat`, `cm_m17ac`, `cm_m02abb`, `cm_raktempb`.

Open questions for RE: what the engine does with AlphaMean; where it flips the -Z face; whether it
reads the TXI at `128 + DataSize` the way rule 2 does.
