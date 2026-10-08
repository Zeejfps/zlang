# LIP: lip-sync keyframes

A LIP file drives a talking head's mouth while one line of voice-over plays: a list of times, each
with one of 16 mouth shapes. One LIP belongs to one VO sound, by name.

Resource type **3004** (`lip`), binary, little-endian, magic `LIP V1.0`. Type ids are in
[resource-types.md](resource-types.md); how containers are mounted is in
[resources.md](resources.md).

## Where the game keeps them

- Only in `lips/*.mod` (ERF containers, [erf.md](erf.md)): 18,206 copies, 12,910 distinct resrefs,
  in 109 files. No LIP in chitin, the texture packs, `modules/`, `rims/`, `patch.erf`, Override or
  the save.
- `lips/<module>_loc.mod` holds the LIPs for the lines spoken in module `<module>` (same name as
  `modules/<module>.rim`, e.g. `lips/tar_m02ae_loc.mod`). The exe mounts it with the module
  (string `LIPS:%s_loc`).
- `lips/localization.mod` (2,596 LIPs) is mounted globally (string `LIPS:localization`). It holds the
  LIPs for conversations that are not inside a module: the 2,548 + 118 references from DLGs in
  `templates.bif` (party and global conversations) resolve there.
- `lips/global.mod`, `legal.mod`, `mainmenu.mod`, `miniglobal.mod` and `subglobal.mod` exist but are
  empty ERFs.
- 1,647 resrefs sit in more than one container; every such pair is byte-identical, so the order in
  which `localization.mod` and `<module>_loc.mod` are searched does not matter for the shipped data.

## Layout

All little-endian. The header is 16 bytes; keyframes follow with **no padding**, 5 bytes each, so
the float of keyframe *i* sits at the unaligned offset `16 + 5*i`. Read it byte-wise.

| Offset | Size | Type | Meaning |
|---|---|---|---|
| 0 | 4 | char[4] | `LIP ` (with the trailing space) |
| 4 | 4 | char[4] | `V1.0` |
| 8 | 4 | float32 | length of the line in seconds |
| 12 | 4 | u32 | keyframe count *n* |
| 16 | 5*n* | keyframe[*n*] | see below |

Keyframe (5 bytes):

| Offset | Size | Type | Meaning |
|---|---|---|---|
| 0 | 4 | float32 | time in seconds from the start of the line |
| 4 | 1 | u8 | mouth shape id, 0..15 (table below) |

The file size is exactly `16 + 5*n`; there is nothing after the last keyframe.

A reader should reject: a size under 16, a wrong magic, a size other than `16 + 5*n`, a length
that is negative or NaN, a shape id above 15, times that decrease, and times outside
`[0, length]`. None of the shipped files does any of these.

## Mouth shapes

| Id | Name | Share of all keys |
|---|---|---|
| 0 | EE (also the rest pose, see below) | 12.7% |
| 1 | EH | 5.0% |
| 2 | SCHWA | 22.9% |
| 3 | AH | 3.1% |
| 4 | OH | 6.7% |
| 5 | OOH | 3.2% |
| 6 | Y | 7.8% |
| 7 | S, TS | 3.2% |
| 8 | F, V | 4.0% |
| 9 | N, NG | 3.5% |
| 10 | TH | 9.6% |
| 11 | M, P, B | 8.1% |
| 12 | T, D | 4.5% |
| 13 | J, SH | 2.1% |
| 14 | L, R | 1.8% |
| 15 | K, G | 2.0% |

The names are the community's (the KOTOR modding wiki's LIP page). Evidence that they are right,
and of what an id means to the renderer:

- **An id is a frame of the head's `talk` animation.** The `talk` animation of a head model
  (usually rooted at the node `talkdummy`) keys the face bones (`f_jaw_g`; `f_um_g` upper mouth;
  `f_lmc_g`/`f_rmc_g` mouth corners; `f_Rlm_g`/`f_Llm_g` lower lip; `f_tonguetip_g`; other names
  on a few models such as `jaw_g`, `lipupper_g`) only at multiples of 1/30 s, from 0 to 15/30 s,
  and the animation is 0.5 s long (0.467 s on `c_female`, `n_admrlsaulkar`, `n_selkath`,
  `n_selkathcr`, `p_carthbbh`; 0.333 s on `c_holorakata`). The main bones of the human heads have
  all 16 keys; other bones and creatures have fewer and rely on ordinary key interpolation. So
  shape id *s* is the pose at time *s*/30 s. Models carrying a `talk` animation (25): the
  supermodels `s_male02` and `s_female03` (human heads reach them through their supermodel chain:
  `pmha01` -> `S_Female02` -> `S_Female01` -> `S_Male02`, `pfha01` -> `S_Female03`), party heads
  (`p_bastilah`, `p_candh`, `p_juhanih`, `p_missionh`, `p_carthbbh`, `p_hk47`) and creatures
  (`c_hutt`, `c_gammorean`, `n_yoda`, ...).
- **The poses match the phonemes.** In `s_male02`, `s_female03`, `p_bastilah` and `p_missionh`
  the jaw (`f_jaw_g`, rotation about x, negative opens) is closed at frame 0, opens wide around
  frames 3 to 5 (AH, OH, OOH; `p_bastilah` opens wider still at 14, L/R), and opens only a little
  at frame 11 (M/P/B) and, on three of the four heads, frame 8 (F/V). In `s_male02` the upper lip
  (`f_um_g`) turns furthest at frame 11 (lips pressed), the lower lip moves up at frames 8 and 11
  (lip to teeth, lips together), and the mouth corners move furthest at frames 4, 13 and 5 (OH,
  SH, OOH: the rounded-lip sounds). `python kotor/tools/py/lip_probe.py talk` prints these keys.
- **Shape 0 is the rest pose.** Frame 0 of `talk` is (close to) the bind pose: in `s_male02` every
  key at t = 0 is a zero offset and an identity rotation. And every one of the 18,206 files begins
  with a key at t = 0 with shape 0 and ends with a key at t = length with shape 0. No other shape
  ever starts or ends a file.

Treat 0 as "mouth closed / neutral" in practice, whatever its name.

## Pairing with the voice-over

A LIP has the same resref as the VO it animates.

- **Which line uses it.** A dialogue node (DLG `EntryList`/`ReplyList` struct, see
  [gff-dialog.md](gff-dialog.md)) names its sound in `VO_ResRef` (12,354 LIP resrefs), or for
  alien barks in `Sound` (409), or both (147). Every one of the 12,910 LIP resrefs is named by some
  DLG node.
- **The WAV.** Every LIP resref has a WAV of the same name under `streamwaves/` (the stream
  folders are found by path, not through the resource search; see
  [resources.md](resources.md#streams)). For a 16-character VO resref `n` + area(5) + speaker(6) +
  line(3) + `_` the path is `streamwaves/<r[1:6]>/<r[6:12]>/<r>.wav` (exe format
  `HD0:STREAMWAVES\%s\%s\%s`; all 13,310 nested files follow it); shorter names sit directly in
  `streamwaves/` (489 files, `HD0:STREAMWAVES\%s`). Names are case-insensitive (`NM13AABAST01059_.wav`
  in `streamwaves/m13aa/bast01/`). 889 streamwaves WAVs have no LIP; for those the mouth
  presumably stays at rest.
- **The LIP container.** For a DLG inside module *m* (in `modules/<m>_s.rim`), the LIP is in
  `lips/<m>_loc.mod`: 11,284 `VO_ResRef` and 6,744 `Sound` references resolve that way, and one does
  not (`unk41_blackrak.dlg` in `unk_m41ac` names `nm41aablac01011_`, which exists only in
  `lips/unk_m41aa_loc.mod`; that line plays without lip sync unless the engine searches further).
  For global DLGs (`templates.bif`) the LIP is in `lips/localization.mod`.
- **Length.** The header length equals the last key's time in every file, and is 0.031 to 0.067 s
  *shorter* than the MP3 audio in the WAV, counted in whole MP3 frames (median 0.049 s over all
  12,910 pairs; the WAVs are MP3 inside a RIFF header, and MP3 encoders pad the end). Nothing in the
  LIP refers to the audio sample rate.

## Times

- Times are float32 seconds and are always whole milliseconds (as close as float32 allows: two
  LIPs have keys near 16 s that are off by one or two float steps).
- They never decrease, but they are not strictly increasing: 228 places in 227 files repeat a time
  exactly (181 with the same shape, 47 with a different shape) and 156 places differ by one float
  step (same millisecond, same shape). Treat a repeated time as an instant change to the later key,
  and never divide by the gap between two keys without checking it.
- Distinct key times are at least 1 ms apart, typically 0.116 s, at most 3.9 s.
- 2 to 182 keys per file.

## Playback (best known)

How to play it (step 2 follows swkotor.exe, see the engine notes below):

1. Start the LIP when the VO starts. At time *t*, find the last key *k* with `time_k <= t`.
2. The pose for shape *s* is the head's `talk` animation sampled at `(s + 1) / 16` of the
   animation's length (the engine's rule, below; *s*/30 s is close but not what it does).
3. Between key *k* and key *k+1*, blend the two poses by `(t - time_k) / (time_k+1 - time_k)`. The
   first and last keys are shape 0, so lines start and end at rest.
4. After the last key, hold shape 0 until the audio ends.

Linear blending is our choice until RE says otherwise; the keys are about 0.1 s apart, so the
difference between linear and smoother blending is small.

## Playback (verified)

Supersedes step 2 of "best known" above (steps 1, 3 and 4 hold). Read from `swkotor.exe`, not
guessed: `CSWCCreature::PlayLipSync` (0x00616310) turns every key into a normalised time (time /
LIP length) and a pose value `(shape + 1) / 16`; `CSWCCreatureModel::PlayLip` (0x006994a0) hands
them to `PlayLipAnimation("talk", ...)` of the head and of the body; the lip instance's constructor
(0x004818c0) multiplies each pose value by the `talk` animation's length; and `CAurObject::Update`
(0x00486670, flag 0x200 branch) takes the two keys around `elapsed / duration` and samples every
controller of `talk` at the two stored times, blended linearly by the fraction between the keys.

- **Shape *s* is the `talk` pose at `(s + 1) / 16` of the animation's length**, not at *s*/30 s:
  1/32 s for shape 0 (a hair off the bind pose: the jaw 0.4 to 1.4 degrees open on `pmha01`,
  `pfha01`, `p_bastilah`) up to the last key (0.5 s) for shape 15. The two readings differ by
  under one 1/30 s key and look alike in renders (`kotor/out/lipcheck/mapping_*.png`, made by
  `kotor/tools/lipcheck`): M/P/B presses the lips and AH/OH open the jaw in both; at *s*/30 shape 0
  is the bind pose with sealed lips and OOH purses the lips, which pictures alone would favour.
  The exe's code is unambiguous and it is what the game ran.
- **A model without `talk` just keeps its mouth still.** Survey of `appearance.2da`: all 106 head
  models (heads.2da) have `talk` through their supermodel chain; of 90 whole-creature models, 45
  have it and 45 don't: the animals and monsters (bantha, dewback, rancor, krayt dragon, kath hounds,
  ...), every droid (including the lite ones) and the turrets, some aliens (brith, iriaz, ithorian,
  jawa, gizka), `P_T3M3` and `N_DarthMalak`.
- **Implemented** by `lib/dialog/lipsync` (`lipsync::apply`: the head's own pose with only the face
  bones `talk` drives replaced; `tools/lipcheck` checks it).

## Checked

`python kotor/tools/py/lip_probe.py` (about 10 s) runs over every LIP copy in the install
(`kres.Game().every_entry('lip')`) and every WAV under `streamwaves/`, and, when `gffpy.py` is
present, over every DLG:

- 18,206 copies parsed, 0 failures: magic, size `16 + 5*n`, times sorted and inside
  `[0, length]`, shape ids 0..15.
- first key at t = 0 with shape 0 and last key at t = length with shape 0: 18,206 of 18,206.
- 12,910 of 12,910 resrefs have a `streamwaves/` WAV; LIP length minus MP3 duration lies in
  [-0.067 s, -0.031 s] for all.
- 12,910 of 12,910 resrefs are named by a DLG `VO_ResRef` or `Sound`; container rule as above.

`python kotor/tools/py/lip_probe.py talk [MODEL...]` prints the `talk` keys of head models (by
default `s_male02`, `s_female03`, `p_bastilah`, `p_missionh`), the evidence for the shape table.

## Sources

- KOTOR modding wiki, "LIP Format" (header, keyframe and shape table):
  https://kotor-modding.fandom.com/wiki/LIP_Format
- xoreos-docs, KotOR MDL notes (enough of the binary model layout to read the `talk` animation):
  https://github.com/xoreos/xoreos-docs/blob/master/specs/kotor_mdl.html
- Strings in `swkotor.exe` (`LIP V1.0`, `LIPS:localization`, `LIPS:%s_loc`,
  `HD0:STREAMWAVES\%s\%s\%s`), and the game data, via the probe above.
