# RIM (`RIM V1.0`)

A RIM is KOTOR's read-only resource archive: a simpler ERF with no localized strings and each key
carrying its own offset and size. Every module ships as two RIMs, and `rims/` holds twelve more
from the Xbox build. The engine never writes RIMs.

All integers are little-endian.

## Where

| Files | Count | Holds |
|---|---|---|
| `modules/<module>.rim` | 117 | exactly three resources: the area's `.are` and `.git` (same resref, e.g. `m13aa`) and `module.ifo` |
| `modules/<module>_s.rim` | 117 | everything else module-specific: scripts (ncs), blueprints (utc, utd, ute, uti, utm, utp, uts, utt, utw), dialogues (dlg), `.pth`, `.fac`, `.jrl` |
| `rims/global.rim`, `miniglobal.rim`, `chargen.rim`, `mainmenu.rim` | 4 | 2DAs, scripts, sounds, models, SSFs, a few UTIs, all also in chitin |
| `rims/globaldx.rim`, `miniglobaldx.rim`, `chargendx.rim`, `mainmenudx.rim` | 4 | the MDX companions of the models in the RIM above, all also in chitin |
| `rims/legal.rim`, `legaldx.rim`, `subglobal.rim`, `subglobaldx.rim` | 4 | nothing (0 entries, 120 bytes) |

Module file names come in mixed case (`M12ab.rim`, `STUNT_00.rim`, `danm13.rim`). Which RIMs the
engine mounts, and in what order, is in [resources.md](resources.md). The `rim` resource type id is
3002 ([resource-types.md](resource-types.md)); no RIM is stored inside another container.

## Layout

```
0      header (120 bytes)
120    key table: EntryCount x 32 bytes
...    resource data (padded, see below)
```

### Header (120 bytes)

| Offset | Size | Type | Field | Value in the install |
|---|---|---|---|---|
| 0 | 4 | char[4] | file type | `RIM ` |
| 4 | 4 | char[4] | version | `V1.0` |
| 8 | 4 | u32 | reserved | 0 in all 246 files |
| 12 | 4 | u32 | EntryCount | 0 .. 949 |
| 16 | 4 | u32 | OffsetToKeyTable | 120 in all 246 files |
| 20 | 4 | u32 | flag, meaning unknown | 1 in the six `rims/*dx.rim` files, 0 in the other 240 |
| 24 | 96 | bytes | reserved | zero in all files |

The flag at 20 marks the "dx" companion RIMs (whose data is 128-aligned, below). A reader ignores
it. Some community descriptions give the header as 124 bytes; the key table starts at 120 in every
file, so use `OffsetToKeyTable`.

### Key entry (32 bytes)

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 16 | char[16] | ResRef | NUL-padded; 16-character names have no NUL |
| 16 | 4 | u32 | ResType | type id; upper 16 bits always 0 |
| 20 | 4 | u32 | ResID | the entry's own index in every file |
| 24 | 4 | u32 | Offset | absolute offset of the data |
| 28 | 4 | u32 | Size | bytes |

### Data placement

Readers only need Offset and Size. For the record (nothing to rely on), BioWare's packer laid data
out in key order with zero padding:

- ordinary RIMs (240 files): the first resource at the next 16-byte boundary after the key table
  (key-table end + 8, since `120 + 32n` is always 8 mod 16); each following resource at
  `align4(previous end) + 16`;
- `*dx.rim` (flag 1): every resource at a multiple of 128, the next one at
  `align128(previous end + 16)`;
- every non-empty RIM ends with 10 zero bytes after its last resource.

## Names

- Module RIMs use lower-case resrefs; `rims/` mixes cases (`FX_droid01`, `PFHA01`). Compare
  case-insensitively ([resources.md](resources.md#names)).
- Script names use `!`, `+` and `-` (`k_pkor_!knexcav`, `k_pkas_morph++`, `k_con_cred50-`).
- No RIM contains the same resref + type twice. 115 RIMs list their keys alphabetically and 131 do
  not; order carries no meaning.
- Within a module the `.rim` and `_s.rim` never share a resref + type. The same name in two
  modules' `_s.rim` is common (2,060 names) and the bytes differ in 1,223 of them: blueprints such
  as `backpack001.utp` are per module, which is why only one module's RIMs may be mounted at a time.

## Quirks

- `rims/global.rim` and `rims/miniglobal.rim` carry 13 2DAs (`appearance`, `baseitems`,
  `placeables`, ...) whose header tabs have been replaced by NULs, apparently dumped from memory
  after parsing; see [2da.md](2da.md). Chitin has the same tables intact.
- On PC the engine mounts `rims/global.rim` at start-up and `mainmenu.rim` / `chargen.rim` while
  the main menu and character generation run; it never mounts `miniglobal.rim` or any `*dx.rim`
  (Xbox leftovers). Everything in them is also in chitin, so our engine skips the folder; see
  [resources.md](resources.md#rims).

## Checked

`python kotor/tools/py/containers_probe.py` (independent of `kres.py`) parses all 246 RIMs (234 in
`modules/`, 12 in `rims/`) and checks: magic; reserved fields; key table offset; ResID = index;
type ids fit 16 bits; no duplicate resref + type; regions (header, keys, every resource)
non-overlapping and inside the file; padding bytes zero. It also tallies the flag at 20, key order,
name case and the placement rules above: all 22,511 resource starts and all 242 trailers follow
them (of the 22,269 non-first starts, 22,021 follow the ordinary rule and 248 the dx rule). Result: 246
files, 22,511 entries, **0 failures**.

## Sources

- KOTOR modding wiki, *RIM Format*: <https://kotor-modding.fandom.com/wiki/RIM_Format> (header and
  key fields; its 124-byte header size disagrees with the data).
- The install's RIM files (the probe above).
