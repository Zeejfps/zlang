# How the game assembles models

What ends up on screen is built from several models and tables. This note covers how they fit
together: rooms, supermodels, bodies, heads, weapons, textures, lightmaps and animation names.
The file formats themselves are in [mdl.md](mdl.md), [tpc.md](tpc.md), [tga.md](tga.md),
[txi-render.md](txi-render.md) and [bwm.md](bwm.md).

Each statement is tagged:

| Tag | Basis |
|---|---|
| **confirmed** | Seen in the data or in a render (`kotor/tools/py/mdlrender.py`, PNGs under `kotor/out/mdl/`) |
| **RE** | Read in the decompiled `swkotor.exe` (`kotor/re/export/functions/`) |
| **inferred** | Our reading, still unproven |

## Coordinate frame

Z is up. Creatures face +Y (confirmed: in `pmhc01_front.png` the camera sits on +Y and sees the
face). Units are metres: a standing human is 1.6–1.8 high, and `rootdummy` sits at about 1.06.

## Areas: room models from the LYT

An area's `<module>.lyt` (ASCII, in `data/layouts.bif`) lists its rooms:

```
beginlayout
   roomcount 15
      M01aa_08c 39.4685 130.475 0.0          room model resref, then x y z
      ...
   doorhookcount 15
      M01aa_08c Door_02 0 39.5591 135.621 -0.0407561 0.0 0.0 0.0 1.0
donelayout
```

* Each room is the MDL with that resref, drawn at the listed position. Rooms are only
  translated, never rotated (confirmed: placing all 15 rooms of `m01aa` this way joins every
  corridor seamlessly, `lyt_m01aa_top.png`). The room's WOK walkmesh uses the same frame; its
  vertices are already in area space (see bwm.md).
* A doorhook line gives the room, the hook name, an unknown 0, a position, then a quaternion
  **w, x, y, z** (confirmed: `Door_15`'s line equals the room's offset plus the `Door_15` dummy
  in `m01aa_02a`, position (10.023, 0.006, −1.316) and orientation w 0.707, z −0.707). Read that
  way, `1 0 0 0` is identity; read as x, y, z, w the doors would tip over.
* Room models are classification 0. They carry a lightmapped mesh set, light nodes
  (`AuroraLight*`), emitters, and one AABB mesh, which is the walkmesh copy and is not drawn.
  Some are sky domes or space backdrops, hundreds of metres wide with fog disabled (`M01aa_07b`,
  a starfield).
* VIS files (another doc) say which rooms are visible from which.

## Supermodels: shared skeletons and animations

A model's header names a supermodel (`NULL` if none). 413 models have one, and chains run deep:
`pfbcm → S_Female03 → S_Female02 → S_Female01 → S_Male02 → S_Male01` (confirmed).

* **Animations** are looked up by name: first in the model, then in its supermodel, and so on up
  the chain. They drive the model's nodes by name (confirmed: `p_bastilabb`, which has no
  animations of its own, plays `S_Female03`'s `run` and `pause1` correctly in
  `bastila_skinned.png`). Animation keys are expressed for the supermodel's skeleton, but body
  models copy that skeleton's node positions exactly (`p_bastilabb` and `S_Female03` have the
  same leg and pelvis positions; confirmed). Position keys are offsets from each node's own
  geometry position (see mdl.md).
* The model header's animation scale (for example 1.06 on large male bodies, `pmb?l`) probably
  scales those position offsets (inferred).
* The `s_*` supermodels contain a full default body (63 meshes). The engine draws the
  creature's own model, never its supermodels' meshes (inferred).
* In supermodels, `rootdummy` carries the walk and run bob, and `cutscenedummy` the cut-scene
  offsets (inferred from the key data).

## Creatures: `appearance.2da`

A creature's `Appearance_Type` (in its UTC) is a row of `appearance.2da` (509 rows). The columns
that pick models and textures:

| Column | Meaning |
|---|---|
| `modeltype` | `B` 312, `F` 107, `S` 56, `L` 34 (below) |
| `race` | Model resref for `S`, `L` and most `F` rows (`C_Rancor`, `N_Selkath`) |
| `racetex` | Optional texture replacing the race model's (118 rows, e.g. `c_hutt02`) |
| `modela`..`modelj` | Body model per body variation A..J (`B` rows); `modela` is the whole model for `F` rows that set it |
| `texa`..`texj` | Body texture base names per variation |
| `texaevil` | Dark-side body texture (90 rows, e.g. `PFBASD`) (inferred) |
| `normalhead`, `backuphead` | Rows of `heads.2da` |
| `envmap` | Environment map for the model's meshes: `DEFAULT` (449 rows), `CM_Baremetal` (45), and others (RE: read in `CreateBTypeBody`) |
| `height`, `hitradius`, `perspace`, `creperspace`, `cameraspace`, `targetheight`, `headtrack`, `head_arc_h/v`, `hitdist`, `prefatckdist`, ... | Gameplay and camera values, not graphics |
| `headbone`, `weaponscale`, `headtexe`, `headtexg`, `headtexve`, `headtexvg`, `skin` | Empty in every row |

Model types:

* **F (full)**: a single model, either `modela` (with texture `texa`) or `race`. Examples:
  Zaalbar, HK-47, Bith.
* **S (simple)** and **L**: the `race` model, retextured with `racetex` when that is set. `S`
  rows are creatures (rancor, bantha) and `L` rows are mostly droids, turrets and the Selkath.
  The difference between S and L is unknown.
* **B (body + head)**: humanoids that wear armour. Their bodies and heads are described in the
  next two sections.

## B-type bodies

The body model comes from `model<L>` and its texture from `tex<L>`, where `<L>` is a letter
(RE: `FUN_00697610`, called from `CSWCCreatureAppearance::CreateBTypeBody`):

* The equipped armour's base item has a `bodyvar` column in `baseitems.2da` (B..J, or I for
  robes). Its UTI body variation picks the letter: 1 is A, 2 is B, ..., clamped to 10 (J). With no
  armour the letter is A.
* The texture is the base name followed by a two-digit texture variation: `PMBC` becomes
  `PMBC01`. The engine checks that the result exists as a TGA (type 3) or TPC (3007) and falls
  back to a default otherwise (RE).
* The body models' meshes already name the `…01` texture (`pmbcm` uses `PMBC01`, `p_bastilabb`
  uses `P_BastilaBB01`; confirmed). We infer that the engine swaps in the computed name for other
  variations.
* The body model is posed and animated through its supermodel chain (`S_Female0x` / `S_Male0x`).

## Heads

* For B-type creatures the head row is `normalhead` (or `backuphead`), and the head model is that
  `heads.2da` row's `head` column (107 rows, e.g. `P_BastilaH`) (RE: `FUN_006964c0` reads
  `HEAD`). Player characters build the head name from gender, race and a number instead, the
  `P…`, `_HEAD` and `%03u` pieces in the same function. That exact rule needs more RE.
* The head model is attached at the body's **`headhook`** node (RE: `CreateBTypeBody` re-attaches
  the head to `"HeadHook"` after loading a body; confirmed by render, where the head sits on the
  neck exactly). 237 character models have a `headhook`.
* The head has its own supermodel, which is the body (`p_bastilah → P_BastilaBB`), and it plays
  its own animations (`pause1`, `talk`, `tlknorm`, `listen`, `pause2`, plus face and lip work),
  never the body's. Applying the body's animation to the head scrambles its facial bones
  (confirmed by a wrong render; inferred that the engine keeps them apart).
* Masks and goggles attach to the head's **`gogglehook`** (RE: `"GoggleHook"` in
  `FUN_006964c0`). `maskhook`, `revmask1hook` and `revmask2hook` also exist (85 and 81 models).
* Model header offset 168 (head root) names `neck_g` in 136 models, the full bodies whose head is
  built in (`ad_saul`). We infer it marks the head subtree for head turning and look-at.
* `heads.2da` also has `headtexe`, `headtexve`, `headtexvve` and `headtexvvve` (30 rows each:
  `PFHA01D1`, `…D2`, `…D3`, `…D`). These are dark-side stages of the player's head texture
  (inferred; the textures are in `patch.erf`).

## Weapons and items

* An item's model is `<ItemClass>_<ModelVariation:03d>` from `baseitems.2da`, for example
  `w_Lghtsbr_001`. Gender-specific base items use `<ItemClass>_<gender letter>_<variation:03d>`
  (RE: `FUN_005b30e0`, format strings `"%s_%03d"` and `"%s_%c_%03d"`). `baseitems.defaultmodel`
  gives the fallback model.
* A weapon's model root goes at the creature's **`rhand`** (main hand) or **`lhand`** node (RE:
  the strings are used by the weapon code; confirmed by render, which puts a lightsaber in the
  right hand and a pistol in the left, `p_bastilabb_front_pause10.5.png`).
* Other hooks seen on character models: `impact` (where hits land), `lightsaberhook` (holster),
  `deflecthook`, `camerahook`, `freelookhook`, `medalhook`, `lookathook` (placeables and doors),
  and `bullethook` / `muzzlehook` on blasters (projectile origin) (inferred from the names).
* The lightsaber blade is a saber mesh plus two glow planes; `powerup` and `powerdown` (0.4 s)
  ignite and retract it (see mdl.md).

## Placeables and doors

* A placeable's model is `placeables.2da` `modelname` for its UTP `Appearance` row. Its walkmesh
  is `<model>.pwk` (see bwm.md).
* A door's model is `genericdoors.2da` `modelname`. Its walkmeshes are `<model>0/1/2.dwk` for
  the closed, open1 and open2 states (see bwm.md). Doors animate `opening1`, `opened1`,
  `closing1`, `closed`, `opening2`, `opened2`, `closing2` and `trans` (54 door models; confirmed
  by render: `dor_lda03` slides its panels apart).

## Textures and lightmaps on meshes

* **Texture 0** is the diffuse texture. The resref resolves to TPC, or TGA if there is no TPC
  (58,557 resolve to TPC, 5 to TGA, 219 are missing). Missing ones are mostly on unused models.
* **Texture 1** is the lightmap, set exactly when the mesh's `lightmapped` byte is 1 (41,555
  meshes). It is sampled with **uv1** and multiplied with texture 0 (confirmed: renders are smooth
  and plausible; `lm_compare.png` shows that flipping v breaks them).
  * Lightmaps are named after the model: `<model>_lm<n>` (`M01aa_02a_lm0`) in most areas, or
    `<model>_a<5 characters>` (`m01aa_04a_a0002t`, all of `m31aa`, doors such as
    `dor_lhr02_a00004`, placeables). They are mostly TGAs in `data/lightmaps*.bif`, each with a
    TXI. 309 references resolve to TPCs instead (`m50aa`, the Ebon Hawk). 2,357 references,
    mostly from unused test rooms like `crossgob`, have no lightmap at all.
  * Lightmapped meshes still carry vertex normals. The room's light nodes are presumably for
    dynamic objects (inferred).
* Both textures use the convention "v counts texel rows in storage order" (see mdl.md, UVs).
* Texture properties such as environment maps, bump maps and blending come from each texture's
  TXI ([txi-render.md](txi-render.md)). For creatures, the `appearance.2da` `envmap` column also
  sets an environment map (RE).

## Animation names

Animations are looked up by name along the supermodel chain. The engine refers to them through
`animations.2da` (rows 0–N with a `name` and flags: `stationary`, `pause`, `walking`, `running`,
`looping`, `fireforget`, `overlay`, `dialog`, `damage`, `parry`, `dodge`, `attack`,
`hideequippeditems`). We infer that scripts' `ANIMATION_*` constants reach these rows through
an engine table. The naming, as seen in the data:

| Kind | Names |
|---|---|
| Humanoid movement and idle | `walk`, `walkinj`, `run`, `runinj`, `runds`, `stealth`, `pause1`, `pause2`, `pause3`, `pauseinj`, `pausestl`, `pausetrd`, `pausepsn`, `hturnl`, `hturnr`, `turnleft`, `turnright` |
| Humanoid social | `talk`, `tlknorm`, `tlkforce`, `tlkplead`, `tlksad`, `tlklaugh`, `listen`, `greeting`, `salute`, `bow`, `victory`, `taunt`, `flirt`, `dance`, `dance1`, `kneel`, `meditate`, `sit`, `sitdown`, `standup`, `good`, `neutral`, `evil` |
| Humanoid use | `activate`, `equip`, `getfromgnd`, `getfromtbl`, `getfromcntr`, `usecomp`, `usecomplp`, `unlockdr`, `opencntr`, `opswitch`, `setmine`, `disablemine`, `throwgren`, `inject`, `drink`, `cardplay`, `treatinj` |
| Force powers | `castout1..3`, `castoutlp1..3`, `throwsab`, `catchsab`, `choke`, `fear`, `horror`, `whirlwind`, `persuade` |
| States | `die`, `dead`, `die1`, `dead1`, `getupdead`, `sleep`, `spasm`, `paralyzed`, `prone` |
| Combat | `<set><wield><action><n>`, for example `c2a1`, `g1w1`, `f3p2`, `m2g1`, `b7a1` |
| Creatures (S/L types) | A `c` prefix on the same ideas: `cwalk`, `crun`, `cpause1`, `cpause2`, `creadyr`, `chturnl`, `chturnr`, `ctaunt`, `cvictory`, `cdamages`, `cdie`, `cdead`, `cdodgeg`, `cspasm`, ... |
| Doors | `opening1`, `opened1`, `closing1`, `closed`, `opening2`, `opened2`, `closing2`, `trans` |
| Placeables and areas | `default`, `on`, `off`, `on2off`, `off2on`, `animloop1..n`, `open`, `close`, `dead`, `die`, `damage` |
| Effects | `impact` (236 models), `travel01`, `detonate`; minigame models use `ready`, `track`, `hit`, `die`, `gear*` |
| Cut-scene puppets | `cut001w`, `cut002w`, ... (`c_holododonna` and the `m*_c*_char*` models) |

Combat names (inferred, from `animations.2da` and `combatanimations.2da`):

* The first letter is the set: `c` and `f` hold attack, parry and damage variants of melee
  styles, `g` general ready, walk and run, `m` misc, and `b` the extended sets in `S_Female03`.
* The digit is the weapon wield type from `baseitems.weaponwield`: 1 stun baton, 2 one-handed,
  3 two-handed or double, 4 pistol, 5 rifle, 6 heavy. Digits 7–9 (`b7a1`, `g9d1`) are not wield
  values; their meaning is unknown.
* Then comes the action: `a` attack, `p` parry, `d` damage, `n`, `f`, `g` ready, `w` walk, `r`
  run, `x`, `y`, `z`.
* The last digit is the variant.

`combatanimations.2da` lists, for each attack row, the matching hit, parry, dodge and damage rows
by `animations.2da` index.

Every model's events (see mdl.md) carry its sound and gameplay hooks: `snd_footstep` on walk and
run cycles, `hit` and `contact` on attacks, `detonate` on projectiles, `draw_weapon`, `cast`.

## What's still open

* The rule for the player's head model name, and the S vs L difference (RE).
* Whether the engine scales supermodel position keys by the model's animation scale.
* Which lights affect which objects, and the light `priority`, `dynamic_type` and
  `affect_dynamic` fields.
* The exact bezier interpolation, the dangly spring model and the particle simulation (mdl.md).
