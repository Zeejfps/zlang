# LYT: area layout

A LYT file lists the pieces an area is built from: the **room** models and where each sits, plus,
in minigame areas, **track** and **obstacle** models, and the **door hooks** exported from the
level designer's 3ds Max scene. The text comes from BioWare's Max exporter (`#MAXLAYOUT ASCII`).

Resource type **3000** (`lyt`), ASCII text. Type ids are in [resource-types.md](resource-types.md).
Visibility between the rooms is in the companion [VIS](vis.md) file.

## Where the game keeps them

- 124 LYT files, one copy each, all in chitin's `data/layouts.bif`. None in modules, Override or
  the save.
- The resref is the **area** name, shared with the area's ARE, GIT and VIS (`m01aa.lyt` is area
  `m01aa`, in module `end_m01aa`; see [gff-module.md](gff-module.md)). All 106 areas used by a
  module have one. 18 more are leftovers no module uses (`m09zz`, `m12ac` .. `m12ah`, `m19aa`,
  `m21aa`, `m25ab`, `m41az`, `m45mg`, `m47aa`, `mgf_ebonhawk`, `mqatester`, `plcaa`,
  `stunt_ebobridge`, `stuntroom41ad`).

## Grammar

Every one of the 124 files has this shape, sections in this order, all four always present:

```
#MAXLAYOUT ASCII
filedependancy <scene>.max
beginlayout
   roomcount <n>
      <model> <x> <y> <z>                                        n lines
   trackcount <n>
      <model> <x> <y> <z>                                        n lines
   obstaclecount <n>
      <model> <x> <y> <z>                                        n lines
   doorhookcount <n>
      <room> <door> <flag> <x> <y> <z> <qw> <qx> <qy> <qz>       n lines
donelayout
```

Lexical rules, as found in the data:

- **Lines** end in CRLF in all files. One file (`m12aa.lyt`) has no CRLF after its last line.
- **Fields** are separated by single spaces. Section lines are indented by 3 spaces, entries by 6;
  in six files (`m12ac` .. `m12ah`) the single room line is indented by a tab instead. Split on any
  run of spaces and tabs and ignore indentation.
- **Keywords** are lower case in the data (`filedependancy` is BioWare's spelling); match them
  case-insensitively.
- **Comments**: a line whose first word starts with `#`. Only the first line is one.
- **Numbers**: `<n>` and `<flag>` are decimal integers. Coordinates are C floats as `printf %g`
  writes them: `39.4685`, `-0.0407561`, `0.0`, `14.0`, and exponents with three digits
  (`-1.26441e-007`, 119 of them, in door-hook quaternions). Use a full float parser.
- **Names** are model resrefs: ASCII letters, digits and `_`, at most 14 characters here, mixed case
  (100 files use upper case: `M01aa_08c`). Resrefs are case-insensitive.
- **`****`** in place of a room model (134 entries in 11 `stunt_*` cutscene layouts) means "no room
  here": these layouts copy an area's room list and blank out the rooms the cutscene does not need.
  Skip such entries but keep counting them.
- **After `donelayout`** the reader stops. `m12aa.lyt` has a stray `M12aa_01m` (no CRLF) after it.
- `filedependancy` names the source scene; it is informational (111 name the area itself, 13 name
  another scene, e.g. the seven `stunt_*` layouts built from `M12aa.max`).

Reader rule: read lines; skip blank lines and `#` lines; before `beginlayout` accept only
`filedependancy`; inside, a `...count <n>` line opens a section and the next `n` non-blank lines are
its entries; `donelayout` ends the file. A count that runs past `donelayout` or the end of the file,
a wrong number of fields, or an unknown keyword is an error. All 124 files pass.

The exe's own strings agree on the shapes: `beginlayout`, `donelayout`, `roomcount`, `trackcount`,
`%*s%d` (skip a keyword, read a count), `%s %f%f%f` (model and position) and
`%s%s%d%f%f%f%f%f%f%f` (two names, an integer and seven floats: the door-hook line).
`obstaclecount` and `doorhookcount` do not appear as literals in the exe, so how it reads those two
sections is not known yet; the `%*s%d` pattern would read any count line.

## Fields and meaning

**Coordinates** are the area's world space: metres, Z up, the same frame as the GIT's object
positions ([gff-module.md](gff-module.md)). Evidence: door-hook positions coincide with GIT door
positions (below).

**Room models are drawn at the LYT position; room walkmeshes are already in area coordinates.**
A room's MDL is in its own model space and must be translated by (x, y, z); its WOK's vertices
already include that offset, so do not translate them. Example, `m03aa_02a` at (130, 300): its
mesh nodes sit at about (124..135, -84..-74) in the model, (254..265, 216..226) after adding the
position, and its WOK spans x 252..266, y 218..225. In `m01aa`, `M01aa_08c` at (39.5, 130.5) has
mesh nodes near the model origin and a WOK spanning x 35.0..44.1, y 125.0..136.1. Over all room
lines whose WOK has vertices (237 more have an empty WOK), the mesh nodes land on the WOK only after
adding the LYT position in 954, only without it in 2, inconclusively in 41, and 15 rooms sit at the
origin. The room model itself is never rotated. (Mesh-node positions are a coarse proxy for the
geometry; the MDL work should repeat this with vertices.)

| Section | Fields | Meaning |
|---|---|---|
| rooms | model, x, y, z | Room model `model.mdl`/`.mdx`, translated to (x, y, z), no rotation; its walkmesh is not translated (above). The model name is also the room's name in [VIS](vis.md) and the name of its walkmesh `model.wok`. 0 to 53 rooms per file (1,401 lines, 1,267 real). |
| tracks | model, x, y, z | Minigame models: swoop-race track pieces and enemy paths (`m03mg_MGT02`), turret-game paths (`M12ab_MGT01`). Placed like rooms. |
| obstacles | model, x, y, z | Minigame obstacle models (`m03mg_MGO01`), placed like rooms. |
| door hooks | room, door, flag, x, y, z, qw, qx, qy, qz | A door position in the designer's scene: the room it belongs to, the hook's name (`Door_02`, `door_01`), an integer that is 0 in all 897 lines, the position, and the orientation as a unit quaternion **in the order w, x, y, z**. |

- **Tracks and obstacles** appear only in minigame areas: the swoop races `m03mg`, `m17mg`,
  `m26mg` (and the unused `m45mg`; 30 or 31 tracks, 22 obstacles each), the turret sequence
  `m12ab` and its unused copies `m12ac` .. `m12ah` (7 tracks, 1 obstacle, all at the origin) and
  the unused `mgf_ebonhawk` (`MGF_turretcam`). The area's ARE `MiniGame` struct names them: its
  `Obstacles` list names the obstacle models (`m03mg_mgo01`) and each `Enemies` entry names a
  `Track` (`m03mg_mgt02`). The minigame code owns their meaning.
- **Door hooks are not where doors come from.** Doors are GIT objects with their own position and
  `Bearing`. Of 818 door hooks in areas with a GIT, 661 sit exactly (within 1 cm, all three axes)
  on a GIT door, and for those the yaw `2 * atan2(qz, qw)` equals the door's `Bearing` (652) or
  differs by exactly 180 degrees (9: symmetric doors). The other 157 have no door there (doors
  moved or removed after export). All 897 quaternions are unit length with qx and qy zero (to
  1e-4), i.e. pure rotations about Z when read as w, x, y, z; read as x, y, z, w they would tip
  doors over, so the order is settled. 59 hooks in `stunt_*` layouts name a room that was blanked
  to `****`. Keep door hooks in the parsed result; nothing needs them to place doors.
- **Rooms without a walkmesh**: 18 room lines name a model with no WOK anywhere (`M09zz_01a` ..
  `_01c`, `M12ad_01a` .. `M12ah_01a` in the unused turret copies, and the `StuntRoom*` cutscene
  rooms). Nothing can stand in them.

## Checked

`python kotor/tools/py/lyt_probe.py` runs over every LYT copy (`kres.Game().every_entry('lyt')`)
with the reader rule above, and also reads every MDL, MDX and WOK name in the install and every
module GIT (with `gffpy.py`):

- 124 files parsed, 0 failures; section order and counts as above.
- Every room, track and obstacle model that is not `****` exists as an MDL and an MDX somewhere in
  the install (1,267 + 173 + 95 lines, 0 missing).
- Door hooks against GIT doors, and room placement against the walkmeshes, as above.

## Sources

- Deadly Stream, ".lyt and .vis files" (what the files are for, coordinates relative to the scene
  origin): https://deadlystream.com/topic/4805-lyt-and-vis-files/
- xoreos, `src/aurora/lytfile.cpp` (read to compare: it keeps rooms and door hooks, skips tracks and
  obstacles, and leaves the door-hook numbers unnamed):
  https://github.com/xoreos/xoreos/blob/master/src/aurora/lytfile.cpp
- Strings in `swkotor.exe` and the game data, via the probe above.
