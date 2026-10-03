# TGA (Truevision Targa) as KOTOR uses it

KOTOR reads plain Truevision TGA files wherever it reads textures. The shipped data uses them for
area lightmaps, fourteen animated water bump maps and one old environment map; save games add a
screenshot. Everything else is TPC ([tpc.md](tpc.md)). A TGA texture usually comes with a TXI of
the same name ([txi-render.md](txi-render.md)).

All integers are little-endian. Sources are marked: *data* = checked on every TGA in the install by
`tools/py/tgaprobe.py` (see [Checked](#checked)); *spec* = the published Truevision TGA 2.0
specification; *community* = modding documentation; *inferred* = our reading.

## Where

Resource type 3, extension `tga`.

| Where | TGAs | What | Variant |
|---|---|---|---|
| `data/lightmaps.bif`, `lightmaps2.bif` .. `lightmaps13.bif` | 5,586 | area lightmaps, each with a same-name TXI in the same BIF | 32-bit BGRA |
| `data/textures.bif` | 14 | water bump flipbooks (`lda_water01b`, `lma_oceanbmp`, ...), each with a TXI | 8-bit grey |
| `data/legacy.bif` | 1 | `chrome1`, a 256x256 environment-style image, no TXI | 24-bit BGR |
| `Saves/<slot>/Screen.tga` | 1 per save | the save's 256x256 screenshot (loose file, not a resource) | 24-bit BGR |

Total 5,602 in this install (*data*). None in the texture packs, modules, `rims/` or `patch.erf`;
`Override/` is empty here, and it is where mods put TGA textures (a TGA in Override replaces a
packed TPC, [resources.md](resources.md#textures-tpc-tga-txi)). No font is a TGA: all 18 fonts
are TPCs in the GUI pack ([txi-render.md](txi-render.md#fonts)); mods commonly supply fonts as
TGA + TXI in Override (*community*), which this reader supports.

## Layout

```
0              header, 18 bytes
18             image ID, IdLength bytes (0 in every shipped file)
18 + IdLength  colour map, ColorMapLength entries (absent in every shipped file)
...            pixel data, raw or run-length encoded
...            optional TGA 2.0 extension area and 26-byte footer (ignored)
```

### Header (18 bytes)

| Offset | Size | Type | Field | Meaning | In the install |
|---|---|---|---|---|---|
| 0 | 1 | u8 | IdLength | bytes of image ID after the header | 0 |
| 1 | 1 | u8 | ColorMapType | 0 = none, 1 = present | 0 |
| 2 | 1 | u8 | ImageType | 1 colour-mapped, 2 true-colour, 3 grey; +8 (9, 10, 11) = run-length encoded | 2 (5,588), 3 (14) |
| 3 | 2 | u16 | ColorMapFirst | index of the first colour map entry | 0 |
| 5 | 2 | u16 | ColorMapLength | number of colour map entries | 0 |
| 7 | 1 | u8 | ColorMapBits | bits per colour map entry (15, 16, 24, 32) | 0 |
| 8 | 2 | u16 | XOrigin | screen placement; ignore | 0 |
| 10 | 2 | u16 | YOrigin | screen placement; ignore | 0 |
| 12 | 2 | u16 | Width | texels | 2 .. 512 |
| 14 | 2 | u16 | Height | texels | 2 .. 512 |
| 16 | 1 | u8 | PixelBits | 8, 15, 16, 24 or 32 | 32 (5,586), 8 (14), 24 (2) |
| 17 | 1 | u8 | Descriptor | bits 0-3: alpha bits per pixel; bit 4: right-to-left; bit 5: top-to-bottom; bits 6-7: interleaving (must be 0) | 0x00 (5,476), 0x08 (126) |

### Pixel data

- **Order**: rows bottom to top when Descriptor bit 5 is clear, top to bottom when set; texels left
  to right when bit 4 is clear, right to left when set (*spec*). Every shipped TGA has both bits
  clear: **bottom row first, left to right** (*data*), the same order as TPC.
- **Texel layout** (*spec*): 32-bit = B, G, R, A bytes; 24-bit = B, G, R; 16/15-bit = one u16
  `A RRRRR GGGGG BBBBB` (A only for 16-bit with alpha bits 1); grey 8-bit = luminance (16-bit grey =
  luminance, alpha). Colour-mapped: indices of PixelBits/8 bytes into the colour map, minus
  ColorMapFirst; map entries use the same layouts.
- **Run-length encoding** (types 9, 10, 11; *spec*, none shipped): a stream of packets. Header byte
  h; count = (h & 0x7F) + 1. If h & 0x80, one texel value follows and repeats count times; otherwise
  count literal texels follow. Packets may run across row ends. Stop after Width x Height texels.
- **Alpha**: in 32-bit files take alpha from the fourth byte whatever Descriptor's alpha-bit count
  says: 5,474 lightmaps declare 0 alpha bits yet hold alpha values (below).

Normalising to "row 0 = bottom" (reverse rows when bit 5 is set, columns when bit 4 is set) gives
exactly what a GL upload wants, matching TPC. A top-down image for viewing reverses the rows.

### Trailing data

127 files end with the TGA 2.0 footer: a u32 extension-area offset, a u32 developer-directory offset
and `TRUEVISION-XFILE.\0` (26 bytes) (*data*). 107 of them (the `m09zz_*` lightmaps) also hold a
495-byte extension area between pixels and footer, whose size field says 494 and whose text fields
are uninitialised memory; 20 (the 14 water maps, `chrome1`, five `m17mg_01c_*` lightmaps) have only
the footer. The game needs none of it: stop reading after the pixels.

### Variants in the install (*data*)

| Count | ImageType | Bits | Descriptor | Trailing | Files |
|---|---|---|---|---|---|
| 5,474 | 2 | 32 | 0x00 | none | lightmaps |
| 107 | 2 | 32 | 0x08 | extension area + footer | `m09zz_*` lightmaps (`lightmaps4.bif`) |
| 5 | 2 | 32 | 0x08 | footer | `m17mg_01c_*` lightmaps (`lightmaps6.bif`) |
| 14 | 3 | 8 | 0x08 | footer | water flipbooks (`textures.bif`) |
| 1 | 2 | 24 | 0x00 | footer | `chrome1` (`legacy.bif`) |
| 1 | 2 | 24 | 0x00 | none | `Saves/000002 - Game1/Screen.tga` |

No colour maps, no RLE, no image IDs, no top-down or right-to-left files, no 15/16-bit files.

## Lightmaps

5,586 TGAs in `lightmaps*.bif`, all 32-bit, from 2x2 to 512x512 (64x64 1,355, 32x32 1,247,
16x16 1,122, 128x128 718, 8x8 675, 4x4 293, 256x256 119, 2x2 63, 512x512 10) (*data*). Names are
`<module>_<room>_lm<N>` (`m01aa_01a_lm0`, N up to 15), `<module>_<room>_lm000`.. (`m09zz_*`) or
`<module>_<room>_a0001l` (`m17mg_01c_*`); the room's model names its lightmap (*inferred*, see the
MDL doc). Each has a TXI of the same name in the same BIF:

| TXI text | Files |
|---|---|
| `islightmap 1` / `compresstexture 0` / `mipmap 0` / `downsamplemax 0` | 5,474 |
| `mipmap 0` / `downsamplemax 0` | 112 (the `m09zz_*` and `m17mg_01c_*` files) |

Lightmaps are atlases of baked light for room geometry, multiplied with the diffuse texture
([txi-render.md](txi-render.md#lightmaps)). Their alpha channel is 255 throughout in 3,221 files;
in the other 2,365 it is almost only 0 or 255 (11% of texels 0), a coverage mask of the atlas, which
the renderer ignores (*data* for the values, *inferred* for the meaning). `mipmap 0`: use the one
level, generate no mips (*inferred*). 99 further lightmaps (placeables, `3dgui_*`) are TPCs
([tpc.md](tpc.md#quirks)).

## Flipbooks

The 14 water TGAs are 256x256 grey height maps holding an 8x8 grid of 32x32 frames; their TXI is
`isbumpmap 1`, `bumpmapscaling <s>`, `proceduretype cycle`, `numx 8`, `numy 8`, `fps 30` (*data*).
Unlike a TPC flipbook, the frames are one image: frame i is the cell at column `i mod numx` and row
`i div numx`, **rows counted from the first stored row** (the bottom of the picture, v = 0), left to
right. *Data*: in all 14 maps this order gives the smallest mean difference between consecutive
frames, wrap-around included (in the ten maps that score identically, apparently sharing frames:
3.1, against 6.6 with rows counted from the top of the picture and 21.5 column-major). These grey
maps are bump height maps, converted to normals as [txi-render.md](txi-render.md#bump-maps)
describes.

## Reading a TGA (summary)

1. Read the header; reject ImageType other than 1, 2, 3, 9, 10, 11, interleaved files, colour-mapped
   files without a map, and PixelBits outside 8/15/16/24/32.
2. Skip IdLength bytes; read the colour map if ColorMapType = 1.
3. Read Width x Height texels, raw or RLE; fail if the data runs out.
4. Convert to RGBA (B, G, R(, A) to R, G, B, A; grey to R = G = B; no alpha means 255).
5. Reverse rows if Descriptor bit 5 is set, columns if bit 4 is set, so row 0 is the bottom.
6. Ignore anything after the pixels.

## Checked

`kotor/tools/py/tgaprobe.py` decodes every TGA in the install (`kres.Game().every_entry('tga')`:
all BIFs, every container, Override and the loose files in `Saves/`):

```
python kotor/tools/py/tgaprobe.py            # decode all, tally variants, trailing data, alpha, TXI pairs
python kotor/tools/py/tgaprobe.py frames     # frame-order test on the 8x8 water flipbooks
python kotor/tools/py/tgaprobe.py samples    # PNGs of a few lightmaps, a water map and chrome1 in kotor/out/tga/
```

**5,602 files, 0 failures.** The decoder handles every type in the table above, including RLE and
colour maps, though only types 2 and 3 occur. Looked at: lightmaps `m01aa_01a_lm0`,
`m01aa_02a_lm0`, `m09zz_01a_lm000`, `m17mg_01c_a0001l` (atlases of blue-grey room light),
`lda_water01b` (8x8 grid of noise frames) and `chrome1`. Lightmaps have no inherent "up", so their orientation rests on the descriptor bit and the TPC/GL convention; the
water frame order is the data check of row order.
