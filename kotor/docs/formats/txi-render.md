# TXI keywords: what they mean for loading and rendering

A TXI is a small text file of texture options: how to sample a texture, how to blend it, which
environment or bump map goes with it, whether it is a cube map, a flipbook, a procedural texture or
a font. This page covers what each keyword means for a texture loader and a renderer. The line
syntax and which TXI wins when a texture has two are in [txi.md](txi.md); the texture formats are
[tpc.md](tpc.md) and [tga.md](tga.md).

Sources are marked: *data* = checked on every TXI in the install by `tools/py/txiprobe.py`
(see [Checked](#checked)); *exe* = the keyword appears in `swkotor.exe`'s strings; *community* =
modding documentation, chiefly Deadly Stream's "TXI parameters and what they do" thread [1];
*inferred* = our reading, not verified. Much of the rendering behaviour below is *community* or
*inferred* and wants confirming by reverse engineering before a renderer depends on details.

## Where TXI text comes from

| Source | Texts | What |
|---|---|---|
| standalone `.txi` (type 2022) in `lightmaps*.bif` | 5,586 | one per lightmap TGA |
| standalone in `textures.bif` | 28 | 14 water TGAs, 2 engine procedural textures, 12 orphans (no texture of that name in the install) |
| standalone in `templates.bif` | 1 | `grass` (`downsamplemax 0`, `downsamplemin 0`) |
| standalone in `swpc_tex_gui.erf` | 1 | `lbl_menudarr` (orphan) |
| appended to TPCs ([tpc.md](tpc.md#txi-text)) | 6,180 | tpa/tpb/tpc 1,567 each (identical), gui 1,470, `patch.erf` 9 |

11,796 texts in all (*data*). `grassinfo` in `textures.bif` is typed TXI but holds one line of grass
parameters (`3 grass 5.0 1.5 0.5 0.6 0.3 0.5 0.6 0.3`), not keywords. In the shipped data no
texture has both a standalone TXI and embedded text (the one shared name, `grass`, has no embedded
text), so precedence never matters for vanilla data.

## Reading keywords

Each non-blank line is a keyword followed by values separated by spaces or tabs. Facts from the
data that a reader must handle (*data*):

- **Case**: keywords are matched without regard to case. The data spells `spacingR`, `spacingB`,
  `Bumpmaptexture` (16 textures), `Bumpyshinytexture` (16), `Decal` (1), `Type` (1).
- **Blocks**: `upperleftcoords N`, `lowerrightcoords N`, `channelscale N` and `channeltranslate N`
  are followed by N lines of numbers (three per line for the coordinates, one for the channels). All
  18 fonts have exactly `numchars` lines in both coordinate blocks. One texture, `lma_caus01`, writes
  `channelscale 1` and `channeltranslate 1` followed by four lines each; a reader taking N lines
  leaves three stray number lines, which it must skip.
- **Whitespace**: blank lines anywhere, trailing spaces and tabs (`arturowidth 64\t`), double spaces
  (`isdiffusebumpmap  1`), a last line without a newline.
- **Repeats**: a keyword can appear twice in one text (`mipmap 0` twice, `bumpyshinytexture CM_LSF`
  twice, `downsamplemax 0` twice); the values are the same each time.
- **Not engine keywords**: `islightmap`, `compresstexture`, `caretindent`, `bumpmapscale`, `Type`,
  and the typos `compress texture 0` and `compresstexure` do not occur among the exe's strings,
  which hold every other keyword in this list together in a few tables (*exe*). They are authoring
  hints the engine ignores (*inferred*). Unknown blending values (`default`, `addititive`) likewise
  fall back to normal behaviour (*inferred*).

## Keyword reference

Counts are textures using the keyword, counting tpa (not its tpb/tpc copies), the GUI pack,
`patch.erf` and the standalone files (*data*).

### Sampling and upload

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `mipmap` | 7,516 | `0` | Do not use or generate mip levels: sample the top level only. Every TPC that says it has exactly one level (1,923 in tpa, gui and `patch.erf`, and all tpb/tpc copies) (*data*); lightmaps and GUI textures say it. |
| `filter` | 18 | `0` (17 fonts), `1` (`distortiontex`) | `0` = nearest-texel sampling, `1` = bilinear (*inferred*; fonts are pixel art). |
| `clamp` | 156 | `3` | Clamp texture coordinates to the edge instead of repeating. Only on head textures (`pfh*`, `pmh*`, a few `p_*`). Read as bit flags, 1 = u and 2 = v (*inferred*; only 3 occurs). |
| `downsamplemax`, `downsamplemin` | 6,178 / 168 | `0` | Never shrink this texture for lower texture quality. *Data*: exactly the 570 textures whose TXI has `downsamplemax 0` are byte-identical in tpa, tpb and tpc. No effect when the engine always uses tpa. |
| `cube` | 63 | `1` | The texture is a cube map; TPC Height = 6 x Width, six faces ([tpc.md](tpc.md#cube-maps)) (*data*). |
| `compresstexture` | 5,594 | `0` | Authoring hint: keep uncompressed. All 119 TPCs that say it are uncompressed RGB/RGBA (*data*); lightmap TGAs say it too. Not an engine keyword. |
| `islightmap` | 5,573 | `1` | Authoring hint marking lightmaps (5,474 TGAs, 99 RGBA TPCs). Not an engine keyword; the model marks lightmapped meshes instead (exe `lightmapped`, MDL doc). |

### Transparency and blending

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `blending` | 230 | `additive` 172, `punchthrough` 56, `default` 1, `addititive` 1 | How the texture's surface combines with what is behind it, below. |
| `decal` | 44 | `1` 41, `0` 3 | Draw on top of coplanar geometry it lies flush with (*community*), i.e. with a depth bias; probably also without depth writes (*inferred*). Used on lightsaber blades, force fields, light beams, flares, bird sprite sheets, ship lights, mostly with `blending additive`. |
| `alphamean` | 1 | `0.01` | Overrides the TPC header's mean-alpha field (`lda_gobo1`: header 0.365) (*data* for the values; purpose *inferred*: tells the engine how transparent to consider the texture). |

**`blending additive`**: the surface's colour is added to the framebuffer (*community*), drawn
without depth writes after opaque geometry (*inferred*). Of the 168 users with an image, 125 are
opaque (DXT1, RGB, or alpha 255 throughout) and 43 have varying alpha (*data*). Whether the source is weighted by its alpha is
not known; `GL_SRC_ALPHA, GL_ONE` is the safe choice, identical to `GL_ONE, GL_ONE` for the opaque
majority.

**`blending punchthrough`**: alpha-tested cut-outs (grass, leaves, grates, hair) (*community*):
texels with alpha 0.35 or less are discarded, the rest drawn opaque (`ONE, ZERO`) with depth writes
(*exe*). All 56 users have varying alpha (55 DXT5, 1 RGBA) (*data*).

**No `blending` keyword**: the engine's default blend is ordinary alpha blending with depth writes
and an alpha test of `> 0` (*exe*: [re/render-gui.md](../re/render-gui.md#materials-blending-and-alpha-test)),
so alpha is transparency: scorch marks (`LHR_blst02`) and Dantooine's bushes and leaves
(`LDA_bush*`, `LDA_leaf*`) are see-through without a keyword. In env-mapped, bumpy-shiny and
bump-mapped textures the alpha is a mask for that effect instead (below), and those surfaces are
solid in the game (*inferred*: the rancor's `c_rancor01` has AlphaMean 0.76 and a bump map).
630 DXT5/RGBA textures in tpa have varying alpha and no blending, environment, bump or lightmap
keyword (*data*). `punchthrough` cuts at alpha 0.35 (*exe*).

### Environment maps

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `envmaptexture` | 338 | 49 names; `CM_Baremetal` (208 in any case) | Reflect this environment map on the surface. |
| `bumpyshinytexture` | 110 | 43 names; `CM_SpecMap` 11 | As `envmaptexture`, but the reflection is perturbed by the texture's bump map (`bumpmaptexture`) (*community*). 105 users also name a bump map. |

The named texture is a cube map in 960 of 1,014 references (all copies) and every
`bumpyshinytexture` reference that resolves (*data*); sample it with the world-space reflection
vector, Z up ([tpc.md](tpc.md#cube-maps)). Five 2D textures are named by `envmaptexture` as well
(`gunmetal` x11, `fx_reflectmap`, `fx_flare02`, `lte_spheremap`, `plc_starmapshiny`); by the name
`lte_spheremap` these are sphere maps (*inferred*). Names are case-insensitive resrefs, and some do
not exist in the install (`CM_QATEST`, `CM_m33aa`, `CM_spacetaris`, `mycubemap`): draw such surfaces
without the reflection.

**The diffuse texture's alpha is the reflection mask**, not transparency: more black (lower alpha)
means more reflection (*community* [1]). *Data* backs the "not transparency" half: 318 of the 338
`envmaptexture` users and 98 of 107 `bumpyshinytexture` users are DXT5 with varying alpha and no
`blending` keyword, on plainly opaque things such as droids (`c_drdastro01`, mean alpha 0.90). A
reasonable shader is `colour = lit diffuse + reflection * (1 - alpha)` (*inferred*; the exact blend
needs RE). A texture cannot be both transparent and reflective (*community*).

### Bump maps

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `bumpmaptexture` | 120 | 86 names | The bump map to use with this (diffuse) texture. |
| `isbumpmap` | 159 | `1` | This texture is a bump map. |
| `bumpmapscaling` | 150 | 0.1 .. 10 (22 values; `1` 52, `2` 29) | Strength of the bump effect: scales heights (*community*: "increases the intensity of the bump map"). |
| `isdiffusebumpmap` | 35 | `1` | The bump map perturbs diffuse lighting (*inferred* from the name). All 35 are also `isbumpmap 1`. |
| `isspecularbumpmap` | 35 | `1` 34, `0` 1 | The bump map perturbs specular lighting (*inferred*). |
| `specularcolor` | 3 | `.5 .5 .5`, `.1 .1 .1` | Specular colour for a specular bump map (*inferred*). |
| `bumpmapscale` | 8 | `1`, `1.2`, `1.3` | A misspelling of `bumpmapscaling`, not an engine keyword: ignored, so these use the default. |

What a bump map holds (*data*): of the 142 `isbumpmap` TPCs in tpa, 137 are RGBA **tangent-space
normal maps** (RGB = normal x 0.5 + 0.5, flat = (128, 128, 255), alpha 255); 4 are grey **height
maps** (the procedural water textures) and one (`lrk_antibump`, 4x4) is an odd RGBA gradient. The
14 water TGAs are grey height maps too. In tpa, `bumpmaptexture` names 98 normal maps, 4 grey TPCs,
17 water TGAs and one missing texture. So a loader converts height maps to normal maps (slopes
of the height times `bumpmapscaling`) and uses normal maps as they are (*inferred*; the exe's
`Invalid bumpmap: %s.tga` and `NormCubeMap` show load-time bump processing and dot3 lighting).
Whether `bumpmapscaling` also scales ready-made normal maps is unknown. Missing bump map names:
`LDA_flr04bmp` (draw without bumps).

### Water

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `wateralpha` | 22 | 0.2 .. 1 | Opacity of a water surface (*inferred*); always with `bumpyshinytexture` or `envmaptexture` and usually `bumpmaptexture` naming an animated water bump map. |

### Flipbooks (`proceduretype cycle`)

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `proceduretype cycle` | 57 | | Animate through a grid of frames (*data*, *community*). |
| `numx`, `numy` | 57 | 1, 2, 4, 8 / 2, 4, 8, 16 | Frames across and down. |
| `fps` | 57 | 8 .. 32 (`16` 23, `30` 14) | Frames per second. |

Frame f at time t is `floor(t * fps) mod (numx * numy)` (*inferred*). In a TPC the frames are stored
one after another, each a complete texture with its own mip chain, and play in storage order
([tpc.md](tpc.md#flipbooks)); in a TGA they are cells of one image, row-major from the bottom-left
cell ([tga.md](tga.md#flipbooks)). The flipbooks are effect sprites (holograms, fire, static,
force fields, bird sheets) and the water bump maps.

### Other procedural textures

| Keyword | Uses | Values | Meaning |
|---|---|---|---|
| `proceduretype` | 15 | `arturo` 7, `water` 6, `random` 1, `ringtexdistort` 1 | A texture the engine animates or generates (*exe*: the procedure names `ringtexdistort`, `random`, `cycle`, `wave`, `arturo`, `perlin`, `life`, `water`; only the first five occur). |
| `channelscale N` + N lines | 12 | 4 lines: R, G, B, A | Per-channel multiplier of the generated value (*inferred*). |
| `channeltranslate N` + N lines | 13 | 4 lines: R, G, B, A | Per-channel offset added after scaling (*inferred*: `filmnoisetex` scales R, G, B by 0.02 and A by 0, then adds 1 to A, giving faint noise with alpha exactly 1). |
| `distort` | 13 | 0.1 .. 4 | Distortion strength or mode (unknown). |
| `distortionamplitude` | 13 | 0.2 .. 20 | Distortion amplitude (unknown units). |
| `speed` | 13 | 0.7 .. 100 | Animation speed (unknown units). |
| `arturowidth`, `arturoheight` | 9 | 15 .. 64 | Size of the `arturo` generator's grid or output (unknown). |
| `waterwidth`, `waterheight` | 2 | 32 | Size of the `water` generator's grid or output (unknown). |
| `defaultwidth`, `defaultheight` | 14 | 14 .. 32 | Size of the generated texture when no image exists (*inferred*: the two image-less ones, `distortiontex` and `filmnoisetex`, say 32x32). |

The users: `arturo` on caustics, waterfalls and light beams (`lma_caus01`, `lda_wfall01`,
`lts_lbeam01`, ...), which have an image (RGB/RGBA, one level, no `mipmap 0`); `water` on four grey
height maps (`lmg_water01b`, `lqa_waterbmp`, `lun_noiseb`, `plc_water01b`) and two colour textures;
`random` and `ringtexdistort` on `filmnoisetex` and `distortiontex`, standalone TXIs with no image,
which the engine creates by name (*exe*: both names sit next to `c_focusgob` in the strings), for
screen effects. How each generator works is not known; it needs RE of `swkotor.exe`. Until then a
renderer can show the stored image unanimated (`arturo`, `water`) and a static noise texture for the
two image-less ones.

### Keywords the engine knows that no shipped TXI uses

`anglecyclespeed`, `bumpintensity`, `diffusebumpintensity`, `distortangle`, `envmapalpha`,
`filerange`, `forcecyclespeed`, `gamma`, `isenvironmentmapped`, `maptexelstopixels`,
`renderbmlmtype`, `specularbumpintensity`, `temporary`, `useglobalalpha` (*exe*, *data*). A renderer
for the shipped data can ignore them.

## Lightmaps

Area lightmaps are 32-bit TGAs with a TXI of `islightmap 1`, `compresstexture 0`, `mipmap 0`,
`downsamplemax 0` ([tga.md](tga.md#lightmaps)); placeable lightmaps are RGBA TPCs with the same
TXI. For rendering, only `mipmap 0` matters: one level, no mips. The model's lightmapped meshes
multiply the diffuse texture by the lightmap through a second UV set (MDL doc) (*inferred*).

## Fonts

A font is a texture whose TXI has `numchars`. All 18 are TPCs in `swpc_tex_gui.erf` (*data*).

| Keyword | Values | Meaning |
|---|---|---|
| `numchars` | 127, 255, 256 | Number of glyphs. Glyph c is for byte value c of the text (ASCII checked by rendering; Windows-1252 above 127 *inferred*); bytes >= numchars have no glyph. |
| `upperleftcoords N` + N lines `u v 0` | | Upper-left corner of glyph c (line c) in normalised texture coordinates. |
| `lowerrightcoords N` + N lines `u v 0` | | Lower-right corner of glyph c. |
| `fontheight` | 0.10 .. 0.32 | Glyph cell height in units of 100 texels (0.16 = 16 texels). |
| `baselineheight` | 0.08 .. 0.21 | Distance from the cell top down to the baseline, same units (*inferred*: always <= fontheight). |
| `texturewidth` | 1.28, 2.56, 5.12 | Texture width in the same units (= Width / 100). |
| `spacingR` | 0, 0.02 (`fnt_console`) | Extra space after each glyph, same units (*inferred*). |
| `spacingB` | 0 | Extra space between lines (*inferred*). |
| `caretindent` | -0.01 | Not an engine keyword; ignore. |

Coordinates (*data*): **v counts up from the first stored row**, the bottom of the picture, so a
glyph's upper-left v is larger than its lower-right v (true for every glyph of every font). Text
drawn from these rectangles reads correctly (`txiprobe.py font dialogfont16x16 ...`,
`fnt_galahad14`, `fnt_d16x16b`). The third number on each line is always 0. Every glyph cell is
`fontheight x 100` texels high ((upper v - lower v) x Height; e.g. 19 for `fnt_d16x16b`, 16 for
`fnt_console`, 32 for `dialogfont32x32`); widths vary per glyph (0 for empty glyphs, up to 31
texels), so the fonts are proportional. A few coordinates reach 1.002: clamp. In our reading the metrics' unit, 100 texels per
1.0, makes one texel one screen pixel at the GUI's design resolution (*inferred*).

| Font | Texture | numchars | fontheight / baseline | Glyph height | Same pixels as |
|---|---|---|---|---|---|
| `dialogfont10x10` | 256x256 RGBA | 256 | 0.10 / 0.08 | 10 | `dialogfont10x10a`, `dialogfont16x16a` (same TXI too) |
| `dialogfont10x10b` | 256x256 DXT5 | 256 | 0.16 / 0.16 | 16 | |
| `dialogfont12x16` | 256x256 DXT5 | 256 | 0.12 / 0.12 | 12 | |
| `dialogfont16x16` | 256x256 RGBA | 256 | 0.16 / 0.16 | 16 | `dialogfont16x16b` (same TXI too) |
| `dialogfont32x32` | 512x512 RGBA | 255 | 0.32 / 0.21 | 32 | |
| `fnt_console` | 128x128 RGBA | 127 | 0.16 / 0.14 | 16 | |
| `fnt_credits` | 512x512 DXT5 | 256 | 0.19 / 0.15 | 19 | |
| `fnt_creditsa` | 256x256 RGBA | 255 | 0.14 / 0.11 | 14 | `fnt_d16x16a`, `fnt_dialog16x16` (their TXI differs slightly) |
| `fnt_creditsb` | 512x512 DXT5 | 256 | 0.19 / 0.15 | 19 | |
| `fnt_d16x16b` | 512x512 DXT5 | 256 | 0.19 / 0.15 | 19 | `fnt_d16x16`, `fnt_d10x10b` |
| `fnt_d16x16`, `fnt_d10x10b` | 512x512 DXT5 | 256 | 0.10 / 0.10 | 10 | `fnt_d16x16b` (**TXI does not match the pixels**) |
| `fnt_galahad14` | 256x256 RGBA | 256 | 0.17 / 0.14 | 17 | |

**The `fnt_d16x16` mismatch** (*data*): `fnt_d16x16` and `fnt_d10x10b` are identical files whose
glyph table describes 32 glyphs per row of 16-texel cells, 10 texels high, in the top 122 rows of
the picture, while their pixels hold 16 glyphs per row in 32x19 cells over the top 304 rows: the
pixels of `fnt_d16x16b`, whose own table fits them. Text drawn with `fnt_d16x16`'s own table is garbage.
Yet 39 GUI files name `fnt_d16x16` (with 84 naming `dialogfont16x16`, 47 `fnt_console`, 10
`dialogfont10x10`), and the exe names `fnt_d16x16`, `dialogfont16x16`, `fnt_console` and
`fnt_credits`. Modders report that editing `fnt_d16x16b` changes subtitles and dialogue text
(*community* [2]), and `swkotor.ini` has `Use Small Fonts` (*exe*, *data*). So the engine evidently
loads a suffixed variant (`b`, and probably `a` for small fonts) of the name a GUI gives
(*inferred*); the rule, and whether it depends on resolution, needs RE. Until then: for a font
name F, use `Fb` if it exists, else F.

## Checked

`kotor/tools/py/txiprobe.py` gathers every TXI text: every standalone `.txi` from
`kres.Game().every_entry('txi')` and the text after the pixels of every TPC, located by
`tpcprobe.parse` ([tpc.md](tpc.md#which-kind-of-image-and-where-the-txi-starts)).

```
python kotor/tools/py/txiprobe.py                          # tally keywords, check blocks, fonts, references
python kotor/tools/py/txiprobe.py font dialogfont16x16 Hello, Taris!   # render text to kotor/out/txi/
```

**11,796 texts.** It reports every keyword with counts, spellings, values and sources; compares the
set with the keywords found in the exe's strings; checks each block's line count against its N; for
each font checks `numchars` against both coordinate blocks (18 of 18 match), the coordinate ranges,
the v order and the glyph sizes; and resolves every `envmaptexture`, `bumpyshinytexture` and
`bumpmaptexture` name. Problems reported (each three times, once per quality pack): the
`lma_caus01` block counts, and the missing names `CM_QATEST` (3 users), `CM_m33aa` (2),
`CM_spacetaris`, `mycubemap` and `LDA_flr04bmp`. Text rendered and looked at: `dialogfont16x16`,
`fnt_galahad14` and `fnt_d16x16b` read correctly; `fnt_d16x16` gives fragments.

Rendering semantics marked *community* or *inferred* above have not been checked against the
engine; the RE work that would settle them: blending and alpha-test state per keyword, the
env-map/alpha combination, bump map conversion, `decal`, the procedural generators, and font
variant selection.

[1] Deadly Stream, ".txi Parameters and What They Do",
https://deadlystream.com/topic/6243-txi-parameters-and-what-they-do/
[2] Deadly Stream, "KOTOR Font Tool (NWN Font Maker)",
https://deadlystream.com/topic/3708-toolkotor-font-tool-nwn-font-maker/
