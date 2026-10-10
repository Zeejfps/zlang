# Character generation in swkotor.exe

Only the 3D parts so far; the panels' logic is in the other pages of this directory as it is
written. Addresses are for the Steam `swkotor.exe` after SteamStub removal (README.md); each claim
has a confidence (high = read in the code or the data, med = role clear and detail inferred,
low = plausible). Names are ours. The whole page was rechecked claim by claim on 2026-10-07
against the exports rebuilt after the noreturn fix ([noreturn-fix.md](noreturn-fix.md)), vtable
slots from the raw tables and model data from the install; a med claim that says "needs a runtime
check" rests on static reading alone and is surprising enough to test before relying on it.

## 3D previews

Three screens show a creature (a player's body, and head) inside a GUI rectangle. All three use
the machinery of the main menu's 3D scene (gui3d.md, "How the panel builds it"): a `CSWGui3DScene`
inside a custom 3D control (vtable `0x00752e30`) at label `+0x5c`, a camera at scene `+0x18`, and
the same sequence: the room `gui3D_room` (scene slot `+0x70`), a **light model** added with
`FUN_00417620(scene, name, -1)`, the camera attached to a node of that light model (camera slot
`+0x74`) and its field of view set (camera slot `+0x44`) to **22.70** degrees, vertical, in
every one of them (`0x41b5ced9`). All of it is skipped if the global `DAT_0078d1e4` is 0, the
switch every GUI 3D user tests. The creature is a `CSWCCreature` (ctor `0x00616a20`, 0x44c bytes)
that is attached to the scene's `CAurScene` (creature slot `+0x94`, `0x0060fb40`, which hands the
scene to the creature's model holder at `+0x68`) and put at the origin (slot `+0x8c`,
`0x0060b9b0`, position at creature `+0x24..0x2c`; the class selection and main panel do this, the
portrait step only re-attaches). The light model is what lights and frames the creature: its
nodes are dummies, lights and emitters, no mesh. (high)

| Screen | Ctor | Label (640 x 480 units) | Light model | Camera hook | Animation of the light model |
|---|---|---|---|---|---|
| class selection (`classsel.gui`) | `0x006dc3c0` | `3D_MODEL1`..`6`: (58,121) 89x207, the others 69x187 at (155,131), (242,131), (328,131), (416,131), (503,131) | `cgbody_light` | `camerahook` | none (its `default` is one dummy) |
| main panel (`maincg.gui`) | `0x006eb420` | `MODEL_LBL`: (155,89) 162x186 | `charrec_light` | `camerahook` (`camerahookt` for T3-M4, `camerahookh` HK-47, `camerahookz` Zaalbar; `camerahook` if the light model lacks the node) | by alignment, below |
| portrait step (`portcust.gui`) | `0x006f9430` | `LBL_HEAD`: (54,141) 532x190 | `cghead_light` | `camerahook%c`, `m` for sex 0, else `f` | `default` (`DAT_0073df6c`), speed 1.0, flags 0 (loop) |

The class selection has **six scenes**, one per label, each with its own light model and its own
creature; the camera is attached in mode 0 (below). The main panel's constructor adds the room
and `charrec_light` itself, then calls `FUN_006100f0(creature, control, 0, 0, 0)` (below), which
plays the light model's animation, attaches the camera (mode 1), sets the field of view and the
camera offset; the constructor then attaches the creature, puts it at the origin and sets the
offset again. The character sheet (`CSWGuiCharacter`, from `UpdateStats`) and the level-up panel
(`CSWGuiLevelUpMain`) call `FUN_006100f0` too, with the same light model `charrec_light` and the
last argument 1; the sheet's creature is the viewed one's appearance record applied body and head
only, so dressed but unarmed, with the dark side's head and body textures (re/gui.md,
"CSWGuiCharacter", "The 3D character"). `cgmain_light` is in the install but no string of that name is in the
executable: unused (med).

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

- main panel (`FUN_006100f0`, again in the constructor after the creature is attached, and on
  re-attach in `FUN_006eb340`): flag 1, offset (0, 0, H);
- portrait step (`FUN_006f8ad0` when a portrait is chosen, `FUN_006f8c60` on re-attach): flag 0,
  offset (0, H, 0): the camera's up is world Z here, so it too goes up by H.

H is `CSWCCreature::GetCameraTargetHeight` (creature slot `+0xd8`) = `GetCameraHookHeight`
(`0x006974d0`) of the creature's appearance (`+0x21c`): on the body part (`0xff`), if it has a
node `CAMERAHOOK`, the z of that node's stored position (object slot `+0xa0`, `0x0043f540`: the
node's own translation, relative to its parent; `camerahook` is a child of the model's root, so
this is model space); else `GetHeadHeight` (`0x006973b0`): the world z of `HEAD_G` (slot `+0x98`)
minus the z of the creature's model object (appearance `+0x3c`, `+0x2c`), falling back to the
float at appearance `+0x28` when `HEAD_G`'s z is 0 or the difference is negative; 0 with no body
part. The player bodies have `camerahook` at z 1.587 / 1.634 / 1.68 (male `pmb?s` / `m` / `l`,
e.g. `pmbam` (0, 0.021, 1.634)) and 1.538 / 1.593 / 1.648 (female `pfb*`), so H is 1.54 to 1.68:
the main panel's camera ends at z = 0.81 to 0.95, the portrait's at 1.58 to 1.69 (female hook)
or 1.68 to 1.78 (male hook). (high)

### Lights

Each light model has one or two point lights and one ambient-only light. Colour is the
controller value, the light's brightness the multiplier, radius the controller's (`cgbody_light`:
`AuroraLight01` white 0.87 x50, radius 20, shadow flag; `AuroraLight03` grey 0.66 x2, radius 15;
`AuroraLight04` ambient 0.15 x0.5. `cghead_light`: `AuroraLight01` white 0.99 x1, radius 7.5,
shadow flag; `AuroraLight04` ambient (0.50, 0.51, 0.55) x1. `charrec_light`: `AuroraLight03`
blue-grey (0.63, 0.73, 0.80) x2, radius 20; `AuroraLight01` (0.85, 0.18, 0) x50, radius 20,
shadow flag, as stored, its colour and position animated by the alignment animations;
`AuroraLight04` ambient (0.23, 0.20, 0.12) x1.) The multipliers of 50 saturate the lit side
in the way GL's per-vertex clamp does; the result looks like the pictures we remember, so the
seam's `colour x multiplier` is kept as gui3d has it. (med)

The light models also hold the mist (`Mist02`, `Mist03`) and, in `charrec_light`, the alignment
effects: emitters `gas_evil`, `gas_neut`, `gas_good`, `Evil_stream`, `Good_stream`, `Sparks`,
`Sparkles`, `Fx_PuffySand*`. Their animations turn them on and change the lights: `evil`,
`align1`..`align19`, `good` (`evil` red clouds and sparks, `good` blue clouds). (high for the
names, med for what each does: seen in our pictures)

### The main panel and alignment (`FUN_006100f0`)

`FUN_006100f0(creature, control, other, named, play_pose)`. The alignment is the stats `+0x80`
(a short) of `other` if given, else of the creature; the global `DAT_007a22f8`, when not -1,
overrides it. It picks two names:

- the **creature's pose**: `evil` below 40, `neutral` below 60, `good` from 60; T3-M4 and HK-47
  (the `named` object's name at `+0x18` is `t3m4` or `hk47`; without `named`, and when the app
  has a server side, the object comes from the creature through `FUN_0063d4b0`, slot `+0x30`)
  play `pause1`. It is played on the body (part 0xff) and head (0xfe) with speed 1.0, flags 2
  (loop), **only when `play_pose` is nonzero**: the character sheet and the level-up panel pass 1,
  the character generation main panel passes 0, so in character generation the creature keeps
  its idle (below) and only the light model shows the alignment;
- the **light model's animation** (the scene's first model, `FUN_00416750(scene, 0)`): `evil` at
  0, `good` at 100, else `align<N>`, N = alignment / 5 + 1 (1 to 20). The function asks the model
  for the animation's length (object slot `+0x1c`, `0x00484d20`, -1.0 when the model has no such
  animation) and, when it is missing, plays the pose name instead: `charrec_light` has `align1`
  to `align19` only, so alignments 95 to 99 play `good`. Speed 1.0, flags 2 (loop).

`evil`, `neutral`, `good` and `pause1`, `pause2` are animations of the skeleton `S_Male02`, found
through the supermodel chain of every player body and head (`pmbam` -> `S_Female02` -> `S_Female01`
-> `S_Male02` -> `S_Male01`): `good` 3.3 s, `neutral` 6 s, `evil` 2.7 s, `pause1` 6.7 s. The female
bodies and heads (`pfb*`, `pfha*`) go through `S_Female03` first, which has its own `good` 2.7 s,
`pause1` 10 s, `pause2`, `pause3`, `greeting`, `hturnl`, `hturnr` and `listen`. The pose is a
stance, not a one-shot; the whole thing loops. (high)

### The selection screen's creatures

Slot data, `g_aClassSelSlots` at `0x007a2684`, six records of 8 bytes: class (u8), sex (u8), a
`soundset.2da` row (u8, zero-extended; 85 `Player_Male_W` for the male slots, 83
`Player_Female_W` for the female) handed to `FUN_0060b7c0`, which stores it at creature `+0x2fc`
and, when it changed, looks the row's resref up in a table of resrefs and makes a
`CResHelperSSF` from it (the sound set file), then a pad byte and a strref (u16: 32109, 32110,
32111, 32111, 32110, 32109, the three classes' descriptions). The file holds the sex bytes
(0, 0, 0, 1, 1, 1), the sound sets and the strrefs; the class bytes are zero there and a static
initialiser (`FUN_0073b690`) writes them, so the slots are **Scoundrel, Scout, Soldier male, then
Soldier, Scout, Scoundrel female**: classes 2, 1, 0, 0, 1, 2. The constructor writes the sex to
the stats `+0x31` and the class with `FUN_00647770(stats, 0, class)` (class slot 0, stats
`+0xf0`). (high)

For each slot the constructor takes a **random** `portraits.2da` row among those with `ForPC`
nonzero and the slot's `Sex` (`rand() % count`), removing it from the list so two slots of a sex
differ, sets it as the creature's portrait (creature slot `+0xf4`, `0x0060d5c0`: stats `+0x11c`)
and reads the appearance from the column by class: class 0 (Soldier) `Appearance_L`, class 1
(Scout) `AppearanceNumber`, class 2 (Scoundrel) `Appearance_S`, any other `AppearanceNumber`
(appearance.2da rows 91 to 135 female, 136 to 180 male; the S, M, L rows are the small, medium
and large builds of a head: e.g. male rows 136, 137, 138); the row also goes to the stats
`+0x8c`. The portrait step builds its list of heads the same way (`FUN_006f90f0`: every row with
`ForPC` 1 and the creature's sex, in file order, column by the creature's class), and changing
the portrait (`FUN_006f8ad0`) sets the new portrait, re-applies the appearance (`FUN_006134c0`
with mask 2, the head part only: `FUN_00697a20`) with the new row and writes the row into the
creature's appearance record; the head is heads.2da row `normalhead` of appearance.2da. The body
is not rebuilt; the rows of one sex and build share their body models. (high)

No item is equipped, but the body is **not the unarmoured one**. The constructor builds, in a stack
local, the 15-dword appearance record that `FUN_006134c0` takes by pointer (mask 3, body and head), with its first byte (the body variation) 2,
its second (the texture variation) 1 and the dword at `+0x14` (the "armoured" flag) 1, then the
appearance row at `+0x18` (the record is a copy of the first 15 dwords of the creature's own
appearance object at `+0x21c`, four fields changed).
`CSWCCreatureAppearance::CreateBTypeBody` (`0x00697ce0`) asks `FUN_00697610` for the column names:
with the flag set they are `Model` and `TEX` plus the letter `'@' + variation` (variation 0 reads as 1, above
10 as 10), without it always `ModelA` / `TEXA`; the texture name is the cell plus the texture
variation as `%s%02d` (0 reads as 1), falling back to variation 01 when no TGA or TPC of that name
exists. So the chargen body is **letter B**, the one the basic
clothing (`baseitems` row 85, `BodyVar` B) gives: `modelb` with `texb` + `01`, e.g. `pmbbm` and `pmbbm01`
(vest, shirt, trousers and boots; small, medium and large builds `pmbbs`, `pmbbm`, `pmbbl`; female `pfbb*`), and
the head model (heads.2da `head`, e.g. `pmha01`) sits at the body's `headhook`. The underwear body (`modela`
with `texa`, bare arms and legs) is only what a creature with no armour shows in play. The same
creature stays for the whole of character generation: the main panel takes it from the class selection
(`classsel+0x68`), and the portrait step (`FUN_006f8ad0`) copies its record and changes only the appearance
row, so the variation and flag carry over. The three builds are why the six figures look like three outfits:
Scoundrel (small) a red jacket, Scout (medium) the vest, Soldier (large) blue-grey and orange armour. (high)

### Idle (`FUN_0060f7c0`)

`FUN_0060f7c0(creature, dt, initial)` is the idle; it does nothing unless the creature's model
holder (`+0x68`) exists and its byte `+0xc6` is 1. With `initial` (only the class selection's
constructor) it picks `pause1` or `pause2` at random, starts it at a random fraction (0 to 99 %)
of the body's animation length, the head at the same time, and loops (speed 1.0, flags 2) on body
and head, and sets the countdown (creature `+0x394`) to 10 000 to 30 000 ms
(`(rand() % 201 + 100) * 100`). Without it, it adds `dt * 1000` ms to `+0x390`; when that reaches
`+0x394` it picks a new `pause1` or `pause2` and one of `greeting`, `hturnl`, `hturnr`,
`pausebrd`, `pausesh`, `pause3` (`rand() % 6`), and on body and head calls slot `+0x128` with 1,
plays the fidget (flags 0x21) and then the pause (flags 0x60), then zeroes `+0x390` and draws a new
10 to 30 s. `pausebrd` and `pausesh` are not in the player skeletons (only `p_juhani` and `pmbh02`
have them), so two draws in six find no fidget. The class selection's and main panel's per-frame
updates (`FUN_006dc030` for each of the six slots, `FUN_006eb340`; both only while the panel's
byte `+0x44` has bit 7 set) re-attach the creature to the panel's scene if its body is not in it,
then call this. (high for the control flow; med for the flags: 0x21 has bit 0, one-shot per
gui3d.md, and 0x60 presumably queues the loop after it, not decoded.)

The portrait step does not use it. `FUN_006f8ad0` plays `pause1` (flags 2) on body and head when
the portrait changes, and its per-frame update `FUN_006f8c60` (re-attach as above, with its own
offset) counts a float (`+0x1230`, 0 after the constructor, so the first comes at once) down by
`dt`; at 0 or below it plays `pause2` or `listen` at random (flags 0x21) and then `pause1` (flags
0x60) on body and head, and draws the next wait as 1.00 to 3.99 s (`rand() % 300 * 0.01 + 1`).
(high)

Nothing turns the creature: no mouse rotation, no constant spin in the three constructors, the
update functions or the portrait handlers (next `FUN_006f8fc0`, back-out `FUN_006f8f40` which
restores the original portrait, and the key handler `FUN_006f8ff0` all end in `FUN_006f8ad0`).
(med)

### What lib/chargen/preview.ctx does

`preview3d::Preview`: a `gui3d::Scene` for the light model (its lights, mist, camera node) and the
creature's body and head as two parts drawn into the same view that `gui3d::add_to_frame` returns.
The camera offset is applied by moving the camera node's world matrix for the call and putting it
back. The creature starts yawed -90 degrees (facing the camera); `turn` adds to that.
The head is drawn at the body's `headhook` transform and its copies of the hook's ancestors are held at bind
(`mdl_anim::hold_shared`, models.md, Attachments): without that the head's own idle moves them again and it
floats off the neck by the body's root offset, worst on the female bodies.

`preview3d::make` builds chargen's creature from an appearance row; `make_with` takes a `Look` (body
and head models, texture replacements, pose) and a camera node, which is how the in-game character
sheet and the level-up panel (lib/screens/lvl_view.ctx) show a creature as dressed, with the dark
side's textures (re/gui.md, "CSWGuiCharacter", `FUN_00698150`) and the T3-M4 / HK-47 / Zaalbar hooks
and droid `pause1`; those loop the alignment's pose (`play_pose` 1). A pose the model lacks loops
`pause1` (ours: what the original's creature does then is not traced). Alignments 95 to 99 play
`good` on the light model, as the original's fallback does.

`make` is character generation's (`play_pose` 0): its creature plays no pose but the idle above.
The selection's and main panel's creature starts `pause1` or `pause2` at a random 0 to 99 % of the
body's length and every 10 to 30 s plays one of the six fidgets once, then the new pause looping;
the portrait step's plays `pause1` and, from its first update on, `pause2` or `listen` once and then
`pause1` every 1.00 to 3.99 s. The draws are MSVC's `rand()` (`ltr::Rng`) seeded per preview from
the run's seed. The idle's animations are bound once per creature (`Part.idles`) and the loop after a
one-shot waits in `Part.queued` until the one-shot ends, which is our reading of flags 0x21 then 0x60.
A fidget the model lacks (`pausebrd`, `pausesh` on the player skeletons) changes nothing (ours). The
main panel's creature is built anew where the original keeps the selection's, so it starts the idle
afresh. The lights carry their
shadow flag (gui3d), and the room model is not drawn: neither changes the picture, since a GUI scene
has no current room, so the original draws no shadows in it, and the room is a black box like the
clear (re/gui3d.md, "What lib/frontend/gui3d does").

Checked with `kotor/tools/ctxc run kotor/tools/chargenview` (pictures in `kotor/out/chargen/`):
class selection shows a lit full-length figure, centred, head and shoes inside the frame; the main
panel adds white mist (neutral), red clouds and sparks (evil) or blue clouds (good) around the
feet, the creature keeping its idle; the portrait step shows the head and the top of the shoulders, the
head to the right of the middle, seen from the creature's front right as the hook's orientation
says.
