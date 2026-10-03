# Character generation in swkotor.exe

Only the 3D parts so far; the panels' logic is in the other pages of this directory as it is
written. Addresses are for the Steam `swkotor.exe` after SteamStub removal (README.md); each claim
has a confidence (high = read in the code or the data, med = role clear and detail inferred,
low = plausible). Names are ours.

## 3D previews

Three screens show a creature (a player's body, and head) inside a GUI rectangle. All three use
the machinery of the main menu's 3D scene (gui3d.md, "How the panel builds it"): a `CSWGui3DScene`
inside a custom 3D control (vtable `0x00752e30`) at label `+0x5c`, a camera at scene `+0x18`, and
the same sequence: the room `gui3D_room` (scene slot `+0x70`), a **light model** added with
`FUN_00417620(scene, name, -1)`, the camera attached to a node of that light model (camera slot
`+0x74`) and its field of view set (camera slot `+0x44`) to **22.70** degrees, vertical, in
every one of them (`0x41b5ced9`). All of it is skipped if the global `DAT_0078d1e4` is 0, the
switch every GUI 3D user tests. The creature is a `CSWCCreature` (ctor `0x00616a20`, 0x44c bytes)
that is attached to the scene's `CAurScene` (creature slot `+0x94`) and put at the origin (slot
`+0x8c`). The light model is what lights and frames the creature; it has no mesh. (high)

| Screen | Ctor | Label (640 x 480 units) | Light model | Camera hook | Animation of the light model |
|---|---|---|---|---|---|
| class selection (`classsel.gui`) | `0x006dc3c0` | `3D_MODEL1`..`6`: (58,121) 89x207, the others 69x187 at (155,131), (242,131), (328,131), (416,131), (503,131) | `cgbody_light` | `camerahook` | none (its `default` is one dummy) |
| main panel (`maincg.gui`) | `0x006eb420` | `MODEL_LBL`: (155,89) 162x186 | `charrec_light` | `camerahook` (`camerahookt` for T3-M4, `camerahookh` HK-47, `camerahookz` Zaalbar) | by alignment, below |
| portrait step (`portcust.gui`) | `0x006f9430` | `LBL_HEAD`: (54,141) 532x190 | `cghead_light` | `camerahook%c`, `m` for sex 0, else `f` | `default` (`DAT_0073df6c`) |

The class selection has **six scenes**, one per label, each with its own light model and its own
creature. The main panel's scene is made by `FUN_006100f0(creature, control, 0, 0, 0)` (below),
which the character sheet (`CSWGuiCharacter`) and the level-up panel (`CSWGuiLevelUpMain`) also
call with the same light model `charrec_light`. `cgmain_light` is in the install but no string
of that name is in the executable: unused (med).

### Where the camera is

The light models have these hook nodes (position; orientation w,x,y,z), in the light model's
space, which is the creature's: the creature stands at the origin and faces **+X** (a creature's
orientation vector starts as (1, 0, 0), `+0x1c4`; a model's front is its +Y, so the model is
yawed by -90 degrees). The camera looks along its local -Z, as in gui3d.md. (high)

| Model, node | Position | Orientation | Looks along |
|---|---|---|---|
| `cgbody_light`, `camerahook` | (4.873, -0.088, 1.068) | (0.512, 0.492, 0.487, 0.507) | about -X, Z up |
| `charrec_light`, `camerahook` | (4.873, 0, -0.732) | (0.5, 0.5, 0.5, 0.5) | -X |
| `charrec_light`, `camerahookt` / `h` / `z` | (4.873, 0, -0.169) / (5.23, 0, -0.9) / (5.799, 0, -0.9) | the same | -X |
| `cgmain_light`, `camerahook` | (4.873, 0, -0.73) | the same | -X |
| `cghead_light`, `camerahookm` | (1.01, -0.443, 0.097) | (0.588, 0.519, 0.417, 0.46) | (-0.968, 0.227, -0.113) |
| `cghead_light`, `camerahookf` | (0.988, -0.569, 0.039) | the same | the same |

So the selection camera is 4.87 m from the creature at 1.07 m height, where 22.70 degrees see
1.95 m: a whole standing figure fills the rectangle's height. The main panel's hook is at z =
-0.732 and the portrait's at 0.1: both are **raised by the creature's camera height** at run
time.

**The camera offset.** Camera attach (`FUN_00443820`, camera slot `+0x74`) takes a third argument,
a mode 0 to 3, and makes a controller for the camera of that kind (`FUN_0049fb10`, `0x0049fdc0`,
`0x0049fe00`, `0x0049fe40`). Mode 0, which the selection screen uses, follows the node. Mode 1,
which the main and portrait panels use, is a follower with an offset (vtable `0x007438b8`; the
controller's type id, slot 4, is `0x3ea`; its properties are `m_vTranslation` at `+0x3c..0x44` and
`diewithoutparent`; a flag at `+0x48`). Each frame (`FUN_0049f4f0`) the camera is put at the node's
place plus the offset: **flag 1: the offset is in world axes, flag 0: in the camera's own**. The
panels fetch it with `camera->GetController(0x3ea)` and set it: (high)

- main panel (`FUN_006100f0`, also on re-attach in `FUN_006eb340`): flag 1, offset (0, 0, H);
- portrait step (`FUN_006f8ad0` when a portrait is chosen, `FUN_006f8c60` on re-attach): flag 0,
  offset (0, H, 0): the camera's up is world Z here, so it too goes up by H.

H is `CSWCCreature::GetCameraTargetHeight` (creature slot `+0xd8`) = `GetCameraHookHeight`
(`0x006974d0`): the z of the node `CAMERAHOOK` of the creature's body model, else `GetHeadHeight`
(`0x006973b0`), the z of `HEAD_G` minus the creature's z. The player bodies (`pmbam` and the
others) have `camerahook` at (0, 0.021, 1.634), so H is about 1.63 to 1.68 and the main panel's
camera ends at z = 0.95, the portrait's at 1.78. (high for the structure; the float read was lost
in the decompiler's output, the value 1.63 is the node's in the model)

### Lights

Each light model has two or three point lights and one ambient-only light. Colour is the
controller value, the light's brightness the multiplier, radius the controller's (`cgbody_light`:
`AuroraLight01` white 0.87 x50, radius 20, shadow flag; `AuroraLight03` grey 0.66 x2, radius 15;
`AuroraLight04` ambient 0.15 x0.5. `cghead_light`: `AuroraLight01` white 0.99 x1, radius 7.5;
`AuroraLight04` ambient (0.50, 0.51, 0.55) x1. `charrec_light`: `AuroraLight03` blue-grey
(0.63, 0.73, 0.80) x2; `AuroraLight01` (0.85, 0.18, 0) x50 as stored, animated by the alignment
animations; `AuroraLight04` ambient (0.23, 0.20, 0.12).) The multipliers of 50 saturate the lit side
in the way GL's per-vertex clamp does; the result looks like the pictures we remember, so the
seam's `colour x multiplier` is kept as gui3d has it. (med)

The light models also hold the mist (`Mist02`, `Mist03`) and, in `charrec_light`, the alignment
effects: emitters `gas_evil`, `gas_neut`, `gas_good`, `Evil_stream`, `Good_stream`, `Sparks`,
`Sparkles`, `Fx_PuffySand*`. Their animations turn them on and change the lights: `evil`,
`align1`..`align19`, `good` (`evil` red clouds and sparks, `good` blue clouds). (high for the
names, med for what each does: seen in our pictures)

### The main panel and alignment (`FUN_006100f0`)

The alignment is the creature's stats `+0x80` (a short; global `DAT_007a22f8`, when not -1,
overrides it). It picks two names:

- the **creature's pose**, played on its body (part 0xff) and head (0xfe) with speed 1.0, flags
  2: `evil` below 40, `neutral` below 60, `good` above; T3-M4 and HK-47 play `pause1`;
- the **light model's animation**: `evil` at 0, `good` at 100, else `align<N>`, N = alignment / 5
  + 1 (1 to 20; the model has `align1` to `align19`).

`evil`, `neutral`, `good` and `pause1`, `pause2` are animations of the skeleton `S_Male02`, found
through the supermodel chain of every player body and head (`pmbam` -> `S_Female02` -> `S_Female01`
-> `S_Male02` -> `S_Male01`): `good` 3.3 s, `neutral` 6 s, `evil` 2.7 s, `pause1` 6.7 s. The
pose is a stance, not a one-shot; the whole thing loops. (high)

### The selection screen's creatures

Slot data, `g_aClassSelSlots` at `0x007a2684`, six records of 8 bytes: class (u8), sex (u8), a
short (0x55 for the male slots, 0x53 for the female) handed to `FUN_0060b7c0`, which stores it at
creature `+0x2fc` and builds a small object from a resref it looks up (probably the sound set;
low), and a strref (u16: 32109, 32110, 32111, 32111, 32110, 32109, the three classes'
descriptions). The class and sex bytes in the file are zero: a static initialiser
(`FUN_0073b690`) writes the classes, so the slots are **Scoundrel, Scout, Soldier male, then
Soldier, Scout, Scoundrel female**: classes 2, 1, 0, 0, 1, 2 and sexes 0, 0, 0, 1, 1, 1. (high)

For each slot the constructor takes a **random** `portraits.2da` row among those with `ForPC`
1 and the slot's `Sex`, removing it from the list so two slots of a sex differ, and reads the
appearance from the column by class: class 0 (Soldier) `Appearance_L`, class 1 (Scout)
`AppearanceNumber`, class 2 (Scoundrel) `Appearance_S` (appearance.2da rows 91 to 135 female,
136 to 180 male; the S, M, L rows are the small, medium and large builds of a head: e.g. male
rows 136, 137, 138). The portrait step builds its list of heads the same way (`FUN_006f90f0`,
class from the creature's stats), and changing the portrait re-applies the appearance
(`FUN_006134c0`) with the new row, which also changes the head: heads.2da row `normalhead` of
appearance.2da. (high)

The appearance is not equipped: a B-type body is `modela` with the texture `texa` + `01`, no
armour, which for a player is a grey-and-orange jumpsuit (male `pmbam`, `pmbal`, `pmbas`; female
`pfbam`...), and the head model (heads.2da `head`, e.g. `pmha01`) sits at the body's `headhook`.
(high; lib/scene/visual.ctx builds the same with `armor == null`)

### Idle (`FUN_0060f7c0`)

`FUN_0060f7c0(creature, dt, initial)` is the idle: with `initial` it picks `pause1` or `pause2`
at random, starts it at a random fraction (0 to 99 %) of its length and loops (flags 2) on body
and head; the panels' per-frame update (`FUN_006dc030`, `FUN_006eb340`, `FUN_006f8c60`; creature
re-attached to the panel's scene if it is not, then this) counts 10 to 30 s down and then plays one
of `greeting`, `hturnl`, `hturnr`, `pausebrd`, `pausesh`, `pause3` once and goes back to the
pause. (med: the flag values 0x21 and 0x60 were not decoded.) Nothing turns the creature: no
mouse rotation, no constant spin in the three constructors, the update functions or the portrait
handlers. (med)

### What lib/chargen/preview.ctx does

`preview3d::Preview`: a `gui3d::Scene` for the light model (its lights, mist, camera node) and the
creature's body and head as two parts drawn into the same view that `gui3d::add_to_frame` returns.
The camera offset is applied by moving the camera node's world matrix for the call and putting it
back. The creature starts yawed -90 degrees (facing the camera); `turn` adds to that.
The head is drawn at the body's `headhook` transform and its copies of the hook's ancestors are held at bind
(`mdl_anim::hold_shared`, models.md, Attachments): without that the head's own idle moves them again and it
floats off the neck by the body's root offset, worst on the female bodies.

Not done: the idle's random start and fidgets (we loop `pause1`, the main panel's `evil` /
`neutral` / `good`), the dark side's head textures (heads.2da `headtexe` and friends, which depend
on alignment), the lights' shadow flag, the room model, T3-M4 / HK-47 / Zaalbar special hooks (a
generic creature can pass a model with a `camerahookX` node; the preview uses `camerahook`).

Checked with `kotor/tools/ctxc run kotor/tools/chargenview` (pictures in `kotor/out/chargen/`):
class selection shows a lit full-length figure, centred, head and shoes inside the frame; the main
panel adds white mist (neutral), red clouds and sparks (evil) or blue clouds (good) around the
feet, with the pose changing; the portrait step shows the head and the top of the shoulders, the
head to the right of the middle, seen from the creature's front right as the hook's orientation
says.
