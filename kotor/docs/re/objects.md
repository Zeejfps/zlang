# Server-side game objects in swkotor.exe

How the original engine represents the things that live in a module: the id → object lookup,
the class hierarchy and its vtables, how objects are built from templates (`UT?`) and the area's
`GIT`, the creature stats block, and the machinery that makes objects act: the event queue, script
slots, the action queue and the combat round. Addresses are for the Steam `swkotor.exe` after
SteamStub removal (see [README.md](README.md)). Every claim ends with a confidence (high / med /
low); names are ours, in the engine family's style (most of them NWN-derived), unless a log string
gives the real one. Proposed names for all addresses below are in
`kotor/re/proposals/objects.tsv` (git-ignored scratch, merged into [names.tsv](names.tsv)).

Offsets are from the start of the object as the object array stores it (the `CGameObject`
pointer), unless a table says otherwise.

## 1. Object ids and the lookup

### The path from a global to an object

| Step | Where | What |
|---|---|---|
| `g_pAppManager` | global `0x007a39fc` | `+4` client app, `+8` server app (`CServerExoApp`) (high) |
| `CServerExoApp` | `app+8` | a thin wrapper: almost every method forwards to the internal object at `+4` (high) |
| `CServerExoAppInternal` | `server+4` | `+0x10044` AI master, `+0x10048` world timer, `+0x1005c` object array, `+0x10060` current module id, `+0x10064` player list, `+0x1b918/+0x1b91c` cached module, `+0x1b920/+0x1b924` cached area (high) |
| `CGameObjectArray` | `internal+0x1005c` | the id → object hash table (high) |

The pattern every script command uses: `GetObjectArray()` (`0x004aed70`), then
`CGameObjectArray::GetGameObject(id, &obj)` (`0x004d8230`), then a check of the type byte at
`obj+8` or a virtual `As*` cast. `CServerExoApp::GetGameObject` (`0x004ae750` →
`0x004b1700`) does the first two in one call and returns null on failure. (high)

### CGameObjectArray

| Offset | Meaning |
|---|---|
| `+0x00` | bucket array: `0x1000` server buckets followed by `0x1000` client buckets (`0x2000` pointers) |
| `+0x04` | next low server id (counts up from 0) |
| `+0x08` | next low client id |
| `+0x0c` | next high server id (counts down from `0x7fffffff`) |
| `+0x10` | next high client id |
| `+0x14` | "has a client half" flag passed to the constructor (always 1 in practice) |

Each bucket is a singly linked chain of 12-byte nodes `{id without bit 31, object, next}`, kept
in descending id order. The bucket index is `id & 0xfff`, plus `0x1000` when bit 31 of the id is
set. A lookup returns 0 on success and 1 when the id is absent (and nulls the out pointer). (high)

| Address | Name | What it does | Conf. |
|---|---|---|---|
| `0x004d7d80` | `CGameObjectArray::CGameObjectArray` | allocates the buckets, sets the counters | high |
| `0x004d7e10` | `~CGameObjectArray` | deletes every object still registered | med |
| `0x004d80e0` | `AddInternalObject(&id, obj, bCharacter)` | allocates a fresh server id: low counter for ordinary objects, high counter (`0x7fffffff` downward) for character objects | high |
| `0x004d7e90` | `AddObjectAtPos(id, obj)` | registers under a caller-chosen id (loading saves/GITs) and moves the counters past it | med |
| `0x004d7ff0` | `AddExternalObject(&id, obj)` | registers in the client half and sets bit 31 of the id | med |
| `0x004d8230` | `GetGameObject(id, &obj)` | the lookup | high |
| `0x004d81a0` | `Remove(id, &obj)` | unlinks and returns the object | high |
| `0x004d8290` | `Delete(id)` | unlinks without returning it | high |

**Ids.** `OBJECT_INVALID` is `0x7f000000`. Server objects get ids from the low counter
(0, 1, 2 …); character objects (player creatures, `bCharacterObject` in the constructor) count down
from `0x7fffffff`. Client-side objects (`CSWC*`) are registered in the second half of the same
table with bit 31 set, and `0x004b1f70` (forwarded by `0x004aea30`) turns such an id back into the
server id by clearing bit 31. The server creates its array in `CServerExoAppInternal::Initialize`
(`0x004b63e0`); the client initialiser `0x005f8290` creates its own at client `+0x14`. (high for
the server side, med for the client)

### Typed getters

`CServerExoApp` forwards each to `CServerExoAppInternal`; each checks the type byte and returns
the matching `As*` cast, or null.

| Type | `CServerExoApp` | `CServerExoAppInternal` |
|---|---|---|
| any | `0x004ae750` GetGameObject | `0x004b1700` |
| item (6) | `0x004ae760` | `0x004b1740` |
| creature (5) | `0x004ae770` | `0x004b1790` |
| area (4, cached) | `0x004ae780` | `0x004b17e0` |
| trigger (7) | `0x004ae790` | `0x004b1880` |
| placeable (9) | `0x004ae7a0` | `0x004b18d0` |
| store (14) | `0x004ae7b0` | `0x004b1ab0` |
| door (10) | `0x004ae7c0` | `0x004b1920` |
| area of effect (11) | `0x004ae7d0` | `0x004b1970` |
| waypoint (12) | `0x004ae7e0` | `0x004b19c0` |
| encounter (13) | `0x004ae7f0` | `0x004b1a10` |
| sound (16) | `0x004ae800` | `0x004b1a60` |
| module (current) | `0x004ae6b0` GetModule | `0x004b14f0` |

Also: `0x004ae910` → `0x004b2a50` finds the player (`CSWSPlayer`) controlling a creature id;
`0x004aea40` → `0x004b4cb0` returns the first player's creature id; `0x004aed80` returns the AI
master, `0x004aede0` the world timer, `0x004aed90` the player list. (high/med)

## 2. The class hierarchy

### Object types

The byte at `+8` of every game object. The script-visible constants come from
`GetObjectType` (`0x0053c610`), which maps internal → `OBJECT_TYPE_*`; anything ≤ 4 is not a
"real" object for most script commands. (high)

| Internal | Class | `OBJECT_TYPE_*` |
|---|---|---|
| 3 | `CSWSModule` | — |
| 4 | `CSWSArea` | — |
| 5 | `CSWSCreature` | 1 |
| 6 | `CSWSItem` | 2 |
| 7 | `CSWSTrigger` | 4 |
| 9 | `CSWSPlaceable` | 64 |
| 10 | `CSWSDoor` | 8 |
| 11 | `CSWSAreaOfEffectObject` | 16 |
| 12 | `CSWSWaypoint` | 32 |
| 13 | `CSWSEncounter` | 256 |
| 14 | `CSWSStore` | 128 |
| 16 | `CSWSSoundObject` | 512 |

0–2, 8 and 15 never appear in a server constructor; by analogy with NWN they would be GUI, tile,
(unused), projectile and player-TURD/portal. (low)

### CGameObject (`vftable 0x007457a0`, 28 slots)

`CGameObject::CGameObject(type, id)` (`0x004d7d60`) stores id at `+4` and the type byte at `+8`;
destructor `0x004c3030`, deleting destructor `0x004c3040`. Its vtable is the shared header of every
game object, server and client:

| Slot (offset) | Meaning |
|---|---|
| 0 (`0x00`) | scalar deleting destructor |
| 1–2 (`0x04`, `0x08`) | empty hooks in every class seen (NWN: SetId, ResetUpdateTimes) |
| 3 / 4 (`0x0c` / `0x10`) | AsSWCObject / **AsSWSObject** |
| 5 / 6 (`0x14` / `0x18`) | AsSWCDoor / **AsSWSDoor** |
| 7 / 8 (`0x1c` / `0x20`) | AsSWCModule / **AsSWSModule** |
| 9 / 10 (`0x24` / `0x28`) | AsSWCArea / **AsSWSArea** |
| 11 / 12 (`0x2c` / `0x30`) | AsSWCCreature / **AsSWSCreature** |
| 13 / 14 (`0x34` / `0x38`) | AsSWCItem / **AsSWSItem** |
| 15 / 16 (`0x3c` / `0x40`) | AsSWCTrigger / **AsSWSTrigger** |
| 17 (`0x44`) | client only (a `0x6d57b0` client class; likely AsSWCProjectile) |
| 18 / 19 (`0x48` / `0x4c`) | **AsSWSPlaceable** / AsSWCPlaceable |
| 20 / 21 (`0x50` / `0x54`) | **AsSWSAreaOfEffectObject** / AsSWCAreaOfEffectObject |
| 22 (`0x58`) | **AsSWSWaypoint** |
| 23 (`0x5c`) | **AsSWSEncounter** |
| 24 (`0x60`) | unused by the classes seen (likely AsSWCStore) |
| 25 (`0x64`) | **AsSWSStore** |
| 26 / 27 (`0x68` / `0x6c`) | **AsSWSSoundObject** / AsSWCSoundObject |

The server rows are high (each typed getter pairs a type byte with one slot); the client column is
med (from which slot each client vtable overrides). Bodies are folded: "return null" is
`0x0063e7f0` and "return this" is `0x00641db0` everywhere, so the cast slots can't be named per
class; the three classes that use multiple inheritance have real thunks instead: item
`0x00646380` (`this-0x10`, shared with the client item), module `0x004c6bb0` (`this-0x1c`),
area `0x0050d340` (`this-0x11c`). (high)

### Per-type table

All the "object" classes (everything but module and area) derive from `CSWSObject`, whose
constructor `0x004cfcb0(type, id, bCharacter)` calls `CGameObject::CGameObject` and then
registers the object: `AddObjectAtPos` when an id is given, `AddInternalObject` when the id is
`OBJECT_INVALID`. (high)

| Class | Type | vtable (slots) | Constructor | Destructor | Deleting dtor | Conf. |
|---|---|---|---|---|---|---|
| `CGameObject` | — | `0x007457a0` (28) | `0x004d7d60` | `0x004c3030` | `0x004c3040` | high |
| `CSWSObject` | — | `0x00745f18` (56) | `0x004cfcb0` | `0x004d0220` | `0x004d09c0` | high |
| `CSWSCreature` | 5 | `0x007470c8` (57) | `0x004f7a10` | `0x004f8410` | `0x004fde20` | high |
| `CSWSItem` | 6 | `0x00748da0` primary, `0x00748cc0` for the `CSWSObject` at `+0x10` | `0x005530a0` | `0x0055ec70` | `0x0055fcb0` | high |
| `CSWSTrigger` | 7 | `0x00749a38` (56) | `0x0058eae0` | `0x0058eef0` | `0x0058f690` | high |
| `CSWSPlaceable` | 9 | `0x007494d0` (56) | `0x005877e0` | `0x005854b0` | `0x00587a50` | high |
| `CSWSDoor` | 10 | `0x007498b0` (56) | `0x00589ee0` | `0x0058b550` | `0x0058c810` | high |
| `CSWSAreaOfEffectObject` | 11 | `0x00749ea8` (56) | `0x00594480` | `0x005963d0` | `0x005965b0` | high |
| `CSWSWaypoint` | 12 | `0x0074bf80` (56) | `0x005c7e70` | `0x005c84e0` | `0x005c8630` | high |
| `CSWSEncounter` | 13 | `0x00749d98` (56) | `0x00593c70` | `0x00593380` | `0x00593f90` | high |
| `CSWSStore` | 14 | `0x0074bdb8` (56) | `0x005c6ab0` | `0x005c6bf0` | `0x005c7160` | high |
| `CSWSSoundObject` | 16 | `0x0074c0b8` (56) | `0x005c8f30` | `0x005c8660` | `0x005c9020` | high |
| `CSWSArea` | 4 | `0x00747bfc` primary (7), `0x00747b88` for the `CGameObject` at `+0x11c` | `0x0050cf80` | `0x0050d370` | `0x0050dfb0` | high |
| `CSWSModule` | 3 | `0x00745960` primary, `0x007458f0` for the `CGameObject` at `+0x1c` | `0x004c84a0` | `0x004c68a0` | `0x004c8940` | high |

Notes:
- **Item**: the object array holds the address of the `CSWSObject` sub-object (`item+0x10`); the
  primary base (`CSWItem`, ctor `0x005b4660`, one-slot vtable) is the shared item data. Field
  offsets in the item loaders are relative to the `CSWItem` start, so `CSWSObject` fields appear
  shifted by `0x10` there (plot flag at `+0x108`, not `+0xf8`). (high)
- **Area / module** don't derive from `CSWSObject`: they embed a bare `CGameObject` at `+0x11c` /
  `+0x1c` after a resource-helper base (module primary base vtable `0x007458d4` holds a resref at
  `+0xc`). Their tags are at area `+0x158` and module `+0x1f8`, their locals at area `+0x1f4` and
  module `+0x9c` (from `GetTag` and `GetLocalBoolean`). (high)
- Creatures and items join the AI master at level 0 in their constructors. (high)

### CSWSObject virtual functions (slots 28–55)

| Slot (offset) | Name | Base | Overrides | Conf. |
|---|---|---|---|---|
| 28 (`0x70`) | AIUpdate | purecall | creature `0x004fe210`, item `0x0055cb60`, placeable `0x005849d0`, door `0x005889c0`, trigger `0x0058d760`, encounter `0x00593fb0`, AoE `0x00595d10`; store/waypoint/sound: empty | high |
| 29 (`0x74`) | ClearAction(node, bForce) | `0x004cc390` | creature `0x004fab00` | med |
| 30 (`0x78`) | EventHandler(event, caller, data, day, time) | purecall | creature `0x004fece0`, item `0x0055ee10`, placeable `0x00587ba0`, door `0x0058b850`, trigger `0x0058f140`, encounter `0x00594220`, AoE `0x005964e0`, store `0x005c6ee0`, waypoint `0x005c7f10`, sound `0x005c8650` | high |
| 31 (`0x7c`) | SetAnimation(n) | `0x004ccf60` | creature `0x004f0d70` | high |
| 32 (`0x80`) | GetDialogResRef | `0x004d0170` (empty) | creature, placeable, door | med |
| 33 (`0x84`) | GetInterruptable | folded "1" | creature `0x004f82e0` | med |
| 34 (`0x88`) | GetGender | folded "0" | creature `0x004f82f0` | med |
| 35 / 36 (`0x8c` / `0x90`) | GetFirstName / GetLastName | both `0x004d0190` (`+0xc`) | creature `0x004f8310` / `0x004f8330` (stats names) | high |
| 37 (`0x94`) | GetDead | `0x004cb810` | creature `0x004ef820`, placeable/door `0x00588ab0` | high |
| 38 (`0x98`) | GetMaxHitPoints(bIncludeBonus) | `0x004d01a0` | creature `0x004ed310` | high |
| 39 (`0x9c`) | GetCurrentHitPoints(bExcludeTemp) | `0x004caec0` | — | high |
| 40 (`0xa0`) | DoDamage(n) | `0x004ccf80` | placeable/door `0x00589190` | med |
| 41–43 (`0xa4`–`0xac`) | unknown, many arguments (saving throws?) | `0x004d09e0`, `0x004d0e40`, `0x004cf160` | — | low |
| 44 (`0xb0`) | GetDamageImmunity(type) | `0x004caee0` | — | med |
| 45 (`0xb4`) | GetDamageImmunityByFlags(flags) | `0x004caf70` | — | med |
| 46 / 47 (`0xb8` / `0xbc`) | Get/SetLastSpellId | folded "-1" / empty | creature `+0x8f0`, placeable `+0x388`, AoE `+0x234` | low |
| 48 / 49 (`0xc0` / `0xc4`) | a target id pair (Set/Get); RunActions resets it when the finished action wasn't an attack | empty / "OBJECT_INVALID" | creature `0x004f8280` (`+0x944`) | low |
| 50 / 51 (`0xc8` / `0xcc`) | GetPortrait / SetPortrait (resref) | `0x004d01c0` / `0x004d01f0` | creature `0x004f8370` / `0x004f83c0` | med |
| 52 / 53 (`0xd0` / `0xd4`) | GetPortraitId / SetPortraitId | `0x004d0210` / `0x004cad20` | creature `0x004ed4c0` | high |
| 54, 55 (`0xd8`, `0xdc`) | creature-only behaviour | empty | creature `0x004f14f0`, `0x004ffaf0` | low |
| 56 (`0xe0`) | creature-only extra slot | — | `0x004ec610` | low |

### CSWSObject members

| Offset | Meaning | Source | Conf. |
|---|---|---|---|
| `+0x04` | object id | CGameObject | high |
| `+0x08` | type byte | CGameObject | high |
| `+0x0c` | localized name (`CExoLocString`) | GetFirstName | med |
| `+0x14` / `+0x16` | next / last action group id | AddAction | high |
| `+0x18` | tag (`CExoString`, lower-cased by SetTag `0x00553040`) | GetTag | high |
| `+0x20` | portrait resref (16 bytes) | slots 50/51 | med |
| `+0x30` | portrait id (ushort) | slots 52/53 | high |
| `+0x78` | AI level (−1 = not in the AI master) | AI master | high |
| `+0x80` | id of the action being executed (`0xffff` when idle) | RunActions | high |
| `+0x8c` | area id | GetArea `0x004cb120` | high |
| `+0x90..+0x98` | position (x, y, z) | GetPosition, SetPosition `0x004cd1a0` | high |
| `+0x9c..+0xa4` | orientation vector; GetFacing is `atan2(y, x)` in degrees | GetFacing, SetOrientation `0x004cd170` | high |
| `+0xd4` | current animation (default 10000) | SetAnimation | high |
| `+0xdc` | current hit points | GetCurrentHitPoints | high |
| `+0xe0` | maximum hit points (base) | GetMaxHitPoints, "HP" | high |
| `+0xe4` | temporary/bonus hit points | GetCurrentHitPoints | med |
| `+0xe8` | commandable flag (`ClearAllActions` does nothing when 0) | "Commandable" | high |
| `+0xf8` | plot / invulnerable | GetPlotFlag, "Plot" | high |
| `+0xfc` | action queue (`CExoLinkedList` of action nodes) | AddAction | high |
| `+0x100` | named script variables (GFF `VarTable`) | `0x0059aa80` | med |
| `+0x110` | KOTOR local booleans/numbers (GFF `SWVarTable`): 96 bits + 8 bytes | GetLocalBoolean | high |
| `+0x124` / `+0x128` | effect list (pointer / count) | RunActions warnings, EffectList | med |
| `+0x1ac` | 15-byte damage immunity table | slot 44 | med |
| `+0x1e4` | action node currently executing | RunActions | high |
| `+0x1fc` | dirty flags (1 animation, 2 position, 4 orientation) | setters | med |
| `+0x200` | Min1HP | GetMinOneHP, "Min1HP" | high |
| `+0x218` | PartyInteract | loaders | med |

`CSWSObject` itself is about `0x228` bytes: every derived class starts its own fields there
(waypoint map note at `+0x228`, store `OnOpenStore` at `+0x228` …). (med)

## 3. Building objects: templates, GIT entries, saves

Each object type has three readers and a writer, all taking `(CResGFF*, CResStruct*)` except
the template loaders, which take a resref and open the file themselves (`CResGFF` constructor
`0x00410630` with the resource type and four-character signature). (high)

| Type | Template loader (file) | Field reader | GIT-list loader (`CSWSArea`) | Writer | GIT-list writer |
|---|---|---|---|---|---|
| creature | `0x005026d0` (UTC, falls back to `NW_BADGER`) | stats `0x005afce0`, scripts `0x004ebf20`, items `0x004ffda0`, spells `0x005aeb30`; saved state `0x00500350` | `0x00504a70` "Creature List" | `0x00500610` (+ stats `0x005b1b90`) | `0x00507680` |
| item | `0x005608b0` (UTI) | `0x0055fcd0`; inventory entry `0x00560970` | `0x00504de0` "List" | `0x0055ccd0` | `0x00507750` |
| placeable | `0x00587a70` (UTP) | `0x00585670` | `0x0050a7b0` "Placeable List" | `0x00586a70` | `0x00507bd0` |
| door | `0x0058b3d0` (UTD) | `0x0058a1f0`; GIT entry `0x0058c5f0` | `0x0050a0e0` "Door List" | `0x00588ad0` | `0x00507810` |
| trigger | `0x0058ed70` (UTT) | `0x0058da80` | `0x0050a350` "TriggerList" | `0x0058e660` | `0x005078d0` |
| waypoint | `0x005c83b0` (UTW) | `0x005c7f30` | `0x00505360` "WaypointList" | `0x005c8230` | `0x00507a50` |
| sound | `0x005c94e0` (UTS) | `0x005c9040` | `0x00505560` "SoundList" | `0x005c86d0` | `0x00507b10` |
| encounter | `0x00593a90` (UTE) | `0x00592430`, scripts `0x00590820`; GIT entry `0x00593830` | `0x00505060` "Encounter List" | `0x00591350` | `0x00507990` |
| store | `0x005c7760` (UTM) | `0x005c7180` | `0x005057a0` "StoreList" | `0x005c6cd0` | `0x00507ca0` |
| area of effect | — (shape from `vfx_persistent.2da`, `0x005947b0`) | `0x00594b00` | `0x00505af0` "AreaEffectList" | `0x00594d80` | `0x00507d60` |

All high, except the GIT-entry helpers and `0x005947b0` (med). The whole GIT is read by
`CSWSArea::LoadGIT` (`0x0050dd80`, which honours the `UseTemplates` flag: with templates a list
entry is "TemplateResRef + position/orientation", without it the full struct) and written by
`0x0050ba00`. The ARE reader and module/IFO loading belong to [modules.md](modules.md). The
placeable template loader's error message says "Item template %s doesn't exist" — a copy-paste
slip in the original.

**Common object state.** `CSWSObject::LoadObjectState` (`0x004d1cf0`) reads what every saved
object carries: `EffectList` (`0x004d1be0`), `VarTable` (`0x0059aa80`), `SWVarTable`
(`0x0059b0f0`), `ActionList` (`0x004cecb0`) and `Commandable`; the writers are `0x004cec50`,
`0x004cc9d0`, `0x0059adb0`, `0x0059b250`, `0x004cc7e0`. (high/med)

**Creature template load, in order** (`0x005026d0`): open UTC → stats (`ReadStatsFromGff`, which
also fills names, appearance, faction, HP/FP) → the 14 script resrefs → inventory → known spells
→ `PM_IsDisguised`/`PM_Appearance` → `StealthMode` → object state → position/orientation →
`JoiningXP` → post-load fix-ups (`0x004f1c40`, which validates the faction). (high)

**Tags.** Loaders call `SetTag` and then register `(tag, id)` with the module's sorted lookup
table (`CSWSModule::AddObjectToLookupTable`, `0x004c7de0`, 0x28-byte entries at module
`+0x130`), which is what tag searches use. (med)

### Script slots

Creature (`ReadScriptsFromGff`, `0x004ebf20`): 14 `CExoString`s, 8 bytes apart, initialised to
"default" by the constructor. (high)

| Offset | GFF label | Fired by |
|---|---|---|
| `+0x230` | ScriptHeartbeat | `RunHeartbeat` (`0x004eb6e0`) on a 3000–4199 ms timer randomised per creature (med) |
| `+0x238` | ScriptOnNotice | script event 1 (perception) |
| `+0x240` | ScriptSpellAt | script event 2 |
| `+0x248` | ScriptAttacked | creature event handler (melee attacked) |
| `+0x250` | ScriptDamaged | script event 4 |
| `+0x258` | ScriptDisturbed | script event 0x1b (inventory disturbed) |
| `+0x260` | ScriptEndRound | end of combat round |
| `+0x268` | ScriptDialogue | script event 7 (defaults to `k_hen_dialogue01` when empty) |
| `+0x270` | ScriptSpawn | `RunHeartbeat`, once (`+0x34c` "CreatnScrptFird" flag) |
| `+0x278` | ScriptRested | — |
| `+0x280` | ScriptDeath | — |
| `+0x288` | ScriptUserDefine | script event 0xb (user defined; event number kept at `+0x150`) |
| `+0x290` | ScriptOnBlocked | script event 0x1f (path blocked) |
| `+0x298` | ScriptEndDialogue | — |

Other types, as the field readers store them (med; read from the loaders, not yet from the
firing side):

- **Placeable** (`0x00585670`): OnClosed `+0x294`, OnDamaged `+0x29c`, OnDeath `+0x2a4`,
  OnDisarm `+0x2ac`, OnHeartbeat `+0x2b4`, OnInvDisturbed `+0x2bc`, OnLock `+0x2c4`,
  OnMeleeAttacked `+0x2cc`, OnOpen `+0x2d4`, OnSpellCastAt `+0x2dc`, OnTrapTriggered `+0x2e4`,
  OnUnlock `+0x2ec`, OnUsed `+0x2f4`, OnUserDefined `+0x2fc`, OnDialog `+0x304`, OnEndDialogue
  `+0x30c`.
- **Door** (`0x0058a1f0`): OnOpen `+0x228`, OnClosed `+0x230`, OnDamaged `+0x238`, OnDeath
  `+0x240`, OnDisarm `+0x248`, OnHeartbeat `+0x250`, OnLock `+0x258`, OnMeleeAttacked `+0x260`,
  OnSpellCastAt `+0x268`, OnTrapTriggered `+0x270`, OnUnlock `+0x278`, OnUserDefined `+0x280`,
  OnClick `+0x288`, OnDialog `+0x290`, OnFailToOpen `+0x298`. LinkedTo `+0x388`,
  TransitionDestination `+0x3c8`.
- **Trigger** (`0x0058da80`): ScriptHeartbeat `+0x244`, ScriptOnEnter `+0x24c`, ScriptOnExit
  `+0x254`, ScriptUserDefine `+0x25c`, OnTrapTriggered `+0x264`, OnDisarm `+0x26c`, OnClick
  `+0x274`; Geometry follows.
- **Encounter** (`0x00590820`): OnEntered `+0x2e8`, OnExit `+0x2f0`, OnHeartbeat `+0x2f8`,
  OnExhausted `+0x300`, OnUserDefined `+0x308`.
- **Store**: OnOpenStore `+0x228`. **Waypoint**: HasMapNote `+0x228`, MapNoteEnabled `+0x22c`,
  MapNote `+0x230`, LocalizedName `+0x238`.

## 4. Creatures and their stats

### CSWSCreature members

| Offset | Meaning | Conf. |
|---|---|---|
| `+0x22c` | JoiningXP | med |
| `+0x230..+0x298` | the 14 script names (above) | high |
| `+0x340` | path/movement state (0x278 bytes, ctor `0x005d0ce0`; target id at `+0x254` inside) | med |
| `+0x34c` | spawn script already fired | high |
| `+0x350/+0x354`, `+0x358` | last heartbeat time, heartbeat interval (3000 + rand % 1200 ms) | high |
| `+0x4f8` | creature size | med |
| `+0x9c8` | `CSWSCombatRound*` (0x9d8 bytes) | high |
| `+0x9d8` | sound set (ushort) | med |
| `+0x9fc`/`+0xa00` | stealth / detect mode bits | med |
| `+0xa2c` | a 0x4c-byte helper (ctor `0x005a4930`, unknown) | low |
| `+0xa30` | `CItemRepository*` (inventory; ctor `0x0055d290`) | med |
| `+0xa48`/`+0xa4c` | PM_IsDisguised / PM_Appearance | high |
| `+0xa50..` | equipped-item ids (9 slots, `OBJECT_INVALID` initially) | med |
| `+0xa74` | `CSWSCreatureStats*` | high |
| `+0xa88` | player-controlled flag (party member under the player) | med |
| `+0xa8c` | movement/AI state (2 while a move-to-point action is queued) | low |

### CSWSCreatureStats (0x1b8 bytes, ctor `0x005aca80`)

From `ReadStatsFromGff` (`0x005afce0`) and the script getters. (high unless marked)

| Offset | Field |
|---|---|
| `+0x24` | owning creature |
| `+0x28/+0x2c/+0x30` | level-up history list (`LvlStatList`, PCs only) (med) |
| `+0x34` / `+0x3c` | FirstName / LastName (`CExoLocString`) |
| `+0x44` | Conversation resref |
| `+0x54` | Interruptable |
| `+0x58` | Description |
| `+0x60` / `+0x64` | Age / Gender |
| `+0x68` | Experience (GetXP) |
| `+0x6c` | IsPC |
| `+0x78` | FactionID |
| `+0x84` | ChallengeRating (float) |
| `+0x88` | StartingPackage |
| `+0x89` | number of classes (at most 2) |
| `+0x8c` + 0x28·i | class slot i: class id at `+0x1b`, level at `+0x1c`, spells left at `+0x19`/`+0x1a` (med) |
| `+0xdc` | race (indexes the race table in `g_pRules`, 0x34-byte rows) |
| `+0xe0` | Subrace (string), `+0xe8` SubraceIndex |
| `+0xe9`/`+0xea` | STR / STR modifier |
| `+0xeb`/`+0xec` | DEX / modifier |
| `+0xed`/`+0xee` | CON / modifier |
| `+0xef`/`+0xf0` | INT / modifier |
| `+0xf1`/`+0xf2` | WIS / modifier |
| `+0xf3`/`+0xf4` | CHA / modifier |
| `+0xf5` | NaturalAC |
| `+0x122` / `+0x124` / `+0x126` | base maximum / current / temporary Force points (`GetCurrentForcePoints` adds the last two; `CSWSCreature::GetMaxForcePoints` `0x004fd490` adds level × (WIS + CHA modifiers) and feats to the first, droids get 0) |
| `+0x128` | special abilities list (med) |
| `+0x13a` | AIState |
| `+0x164` / `+0x168` | SkillPoints / skill rank array |
| `+0x16e` | Portrait resref |
| `+0x17e` | GoodEvil |
| `+0x182..+0x185` | skin, hair, tattoo colours |
| `+0x186` | Appearance_Type, `+0x188` Phenotype, `+0x189` Appearance_Head |
| `+0x194` | MovementRate / WalkRate |
| `+0x1a0..+0x1a2` | fort / will / reflex bonus |
| `+0x1a4` | Deity |

Hit points and the plot/Min1HP flags live on the creature (`CSWSObject` fields `+0xdc/+0xe0/+0xf8/+0x200`), not in the stats.

Accessors (high): ability scores `GetSTRStat` `0x005a6190`, `GetDEXStat` `0x005a6550`,
`GetCONStat` `0x005a6250`, `GetINTStat` `0x005a6310`, `GetWISStat` `0x005a63d0`, `GetCHAStat`
`0x005a6490` — each is base + race adjustment + ability effects, floored at 3 (the order matches
`GetAbilityScore`'s 0..5 = STR, DEX, CON, INT, WIS, CHA); `GetClass(slot)` `0x005a4e90`;
`GetClassLevel(slot)` `0x005a5090`; `HasFeat` `0x005a6680`; `GetSkillRank` `0x005aa570`.
Writers: `SaveStats` `0x005b1b90`, `SaveClassInfo` `0x005aec90`.

What the routine handlers taught: `GetCurrentHitPoints`/`GetMaxHitPoints` (`0x00539610`) use
virtual slots 39/38 on the creature cast if present, else on the `CSWSObject` cast;
`GetTag` (`0x0053df00`) special-cases module and area; `GetPosition` (`0x0053cae0`) reads
`+0x90`; `GetFacing` (`0x00537fe0`) turns `+0x9c/+0xa0` into degrees; `GetLocalBoolean/Number`
(`0x0053b760`) go to the `SWVarTable` (`GetBoolean` `0x0059b000`, index < 96; `GetNumber`
`0x0059b0b0`, index < 8); `GetPlotFlag` reads `+0xf8`, `GetMinOneHP` `+0x200`, `GetXP` stats
`+0x68`. (high)

## 5. Making objects act

### The AI master: event queue and per-frame updates

`CServerAIMaster` (internal `+0x10044`, ctor `0x004b0780`) holds five object lists, one per AI
level (0x10 bytes each from `+4`; the object remembers its level at `+0x78`), and the event
queue at `+0x54`, a time-ordered `CExoLinkedList` of 0x18-byte nodes
`{day, time, caller id, target id, event id, event data}`. (high)

| Address | Name | What it does | Conf. |
|---|---|---|---|
| `0x004b0850` | AddObject(obj, level) | puts an object in a level's list | high |
| `0x004b08a0` | SetAILevel | moves it | high |
| `0x004af3d0` | RemoveObject | | high |
| `0x004b08d0` | AddEventDeltaTime(days, ms, caller, target, event, data) | world time now + delta | high |
| `0x004afdb0` | AddEventAbsoluteTime | sorted insert; logs through `0x004af630` when a debug flag is set | high |
| `0x004b0ab0` | ClearEventData(event, data) | frees a payload by event type | high |
| `0x004b0b70` | UpdateState | the per-frame step, called from the server main loop `0x004babb0` | high |
| `0x004b0970` / `0x004b0a00` | Save/LoadEventQueue | GFF `EventQueue` | high |

`UpdateState` first pops every event whose time has come and dispatches it: objects with type
> 4 get virtual slot 30 `EventHandler(event, caller, data, day, time)`, areas go to
`CSWSArea::EventHandler` (`0x0050d6c0`), the module to `CSWSModule::EventHandler`
(`0x004c5120`); an event for a vanished id just has its payload freed. Then it walks the AI lists
round-robin calling virtual slot 28 `AIUpdate()` until the frame's budget (10 ms of
microsecond clock) is used up, logging objects that take more than 75 ms. (high)

**Event ids** (from the debug printer `0x004af630`, which names them all): 1 TIMED_EVENT (payload:
a script situation — DelayCommand/AssignCommand), 2 ENTERED_TRIGGER, 3 LEFT_TRIGGER,
4 REMOVE_FROM_AREA, 5 APPLY_EFFECT, 6 CLOSE_OBJECT, 7 OPEN_OBJECT, 8 SPELL_IMPACT,
9 PLAY_ANIMATION, 10 SIGNAL_EVENT (payload: `CScriptEvent`), 11 DESTROY_OBJECT, 12 UNLOCK_OBJECT,
13 LOCK_OBJECT, 14 REMOVE_EFFECT, 15 ON_MELEE_ATTACKED, 16 DECREMENT_STACKSIZE,
17 SPAWN_BODY_BAG, 18 FORCED_ACTION, 19 ITEM_ON_HIT_SPELL_IMPACT, 20 BROADCAST_AOO,
21 BROADCAST_SAFE_PROJECTILE, 22 FEEDBACK_MESSAGE, 23 ABILITY_EFFECT_APPLIED,
24 SUMMON_CREATURE, 25 ACQUIRE_ITEM, 26 AREA_TRANSITION, 27 CONTROLLER_RUMBLE. (high)

**Script event types** (`CSWSSCRIPTEVENT_EVENTTYPE_ON_*`, the `CScriptEvent` type at `+0`):
0 HEARTBEAT, 1 PERCEPTION, 2 SPELLCASTAT, 4 DAMAGED, 5 DISTURBED, 7 DIALOGUE, 8 SPAWN_IN,
9 RESTED, 10 DEATH, 11 USER_DEFINED_EVENT, 12 OBJECT_ENTER, 13 OBJECT_EXIT, 14 PLAYER_ENTER,
15 PLAYER_EXIT, 16 MODULE_START, 17 MODULE_LOAD, 18 ACTIVATE_ITEM, 19 ACQUIRE_ITEM, 20 LOSE_ITEM,
21 ENCOUNTER_EXHAUSTED, 22 OPEN, 23 CLOSE, 24 DISARM, 25 USED, 26 MINE_TRIGGERED,
27 INVENTORY_DISTURBED, 28 LOCKED, 29 UNLOCKED, 30 CLICKED, 31 PATH_BLOCKED, 32 PLAYER_DYING,
33 RESPAWN_BUTTON_PRESSED, 34 FAIL_TO_OPEN, 35 PLAYER_REST, 36 DESTROYPLAYERCREATURE,
37 PLAYER_LEVEL_UP, 38 EQUIP_ITEM. 3 and 6 have no debug name (NWN: melee attacked, end of
combat round). (high)

`CScriptEvent` (0x34 bytes; ctor `0x004d7540`, dtor `0x004d7590`, save/load
`0x004d73a0`/`0x004d79b0`): type at `+0`, then four growable lists — ints `+4`, floats `+0x10`,
strings `+0x1c`, object ids `+0x28` (`GetInteger` `0x004d6480`, `GetObjectID` `0x004d64c0`,
`GetString` `0x004d7360`, `SetObjectID` `0x004d7780`). The feedback-message payload
(`0x004d69f0`/`0x004d6a40`) has the same layout and shares the folded accessors. (med)

### How a script slot gets run

Two routes, both ending in `CVirtualMachine::RunScript(script name, self id, 1)` (`0x005d0fc0`,
see [vm.md](vm.md)):

1. **Signalled.** `SignalEvent` (`0x005439d0`) and the engine itself (e.g.
   `CSWSArea::AddObjectToArea`, `0x0050dfd0`, sends ON_OBJECT_ENTER to the area) queue
   `AddEventDeltaTime(0, 0, caller, target, 10, scriptEvent)`. Next frame the target's
   `EventHandler` switches on the script event type, records the context it needs (last
   perceived, last speaker, user-defined number …) and runs the matching slot; e.g. in the
   creature handler (`0x004fece0`): 1 → `+0x238`, 2 → `+0x240`, 7 → `+0x268`, 0xb → `+0x288`,
   0x1b → `+0x258`, 0x1f → `+0x290`. Other event ids are handled in the same function
   (8 spell impact runs the impact script with the spell id set through slot 47; 1 runs a script
   situation with `RunScriptSituation` `0x005d0fd0`). (high)
2. **Timed by the object.** `CSWSCreature::AIUpdate` (`0x004fe210`) calls `RunHeartbeat`
   (`0x004eb6e0`), which runs OnSpawn once and OnHeartbeat on its own timer. Other types follow
   the same idea from their own `AIUpdate`. (high for creatures)

### The action queue

`CSWSObject::AddAction` (`0x004cea20`) appends a 0x74-byte node to the list at `+0xfc`:

| Node offset | Meaning |
|---|---|
| `+0x00` | internal action id |
| `+0x04..+0x34` | 13 parameter types: 1 int, 2 float, 3 object id, 4 string, 5 script situation |
| `+0x38..+0x6c` | 13 parameter values (`SetParameter`, `0x004cac30`) |
| `+0x6c` | group id (ushort): `0xffff` = start a new group, `0xfffe` = same group as the last action |
| `+0x70` | 1 |

Script commands call per-class helpers that call AddAction, e.g.
`CSWSCreature::AddMoveToPointAction` (`0x004f8b60`), `AddAttackActions` (`0x004fde40`),
`AddCastSpellActions` (`0x004f9460`), `CSWSObject::AddDoCommandAction` (`0x0057cb10`), and the
door/lock helpers `0x004cfac0`–`0x004cfc20`. `ClearAllActions` (`0x004ccd80`) asks virtual slot 29
`ClearAction` about every node (only when the object is commandable) and stops pathing and,
optionally, combat. (high)

**Per frame**, the `AIUpdate` of creatures, placeables, doors, triggers, encounters and AoEs calls
`CSWSObject::RunActions` (`0x0057f4a0`): pop the head, remember it at `+0x1e4` and its id at
`+0x80`, switch on the action id to a handler that returns a status — 1 "still running" (the
node goes back to the head and the loop stops for this frame), 4 "retry later" (re-queued at the
tail), anything else (2 done, 3 failed) frees the node. It keeps going while actions complete
instantly, for at most about 1 ms (the clock is `CExoTimers::GetHighResolutionTimer`, in
microseconds; move/jump actions always end the loop), and trims runaway queues (> 500 nodes). (high)

`GetCurrentAction` translates internal ids with `0x0057a2b0`. Internal ids and their handlers
(creature-only handlers are only called for type 5):

| Id | Action | Handler | Conf. |
|---|---|---|---|
| 1 | MOVETOPOINT | `CSWSCreature::AIActionMoveToPoint` `0x0051f4f0` | high |
| 2 | (check move to object) | `0x005101a0` | low |
| 3 | CheckMoveAwayFromObject | `0x005155b0` | med |
| 4 | (check interact object) | `0x0050ff20` | low |
| 5 | JumpToPoint | `0x0051d600` | high |
| 6 | PlayAnimation | `CSWSObject` `0x0057d080` | med |
| 7 | PICKUPITEM | `0x00517410` | high |
| 8 | EquipItem | `0x00510fd0` | med |
| 9 | DROPITEM | `0x00513830` | high |
| 0xa | (check move to point) | `0x00510670` | low |
| 0xb | UnequipItem | `0x00513ec0` | med |
| 0xc | ATTACKOBJECT | `0x005bbbf0` | high |
| 0xe | Speak (ActionSpeakString) | `CSWSObject` `0x0057b430` | med |
| 0xf | CASTSPELL | creature `0x00514af0`, placeable `0x00584ec0` | high |
| 0x14 / 0x15 | OPENDOOR / CLOSEDOOR | `CSWSObject` `0x0057d490` / `0x0057bbf0` | high |
| 0x17 | PlaySound | `CSWSObject` `0x0057cf00` | med |
| 0x18 | DIALOGOBJECT | `CSWSObject` `0x0057a470` | high |
| 0x19–0x1d | DISABLETRAP, RECOVERTRAP, FLAGTRAP, EXAMINETRAP, SETTRAP | `0x00519570`, `0x00518c40`, `0x0050e400`, `0x0050e900`, `0x00519e30` | high |
| 0x1e | WAIT | `CSWSObject` `0x0057b5b0` | med |
| 0x20 | ResumeConversation | `CSWSObject` `0x0057b320` | low |
| 0x25 | DoCommand (script situation) | `CSWSObject` `0x0057b530` | med |
| 0x26 / 0x27 / 0x28 | OPENLOCK / LOCK / USEOBJECT | `CSWSObject` `0x0057d9d0` / `0x0057bec0` / `0x0057e8c0` | high |
| 0x29 / 0x2a / 0x2b | ANIMALEMPATHY / REST / TAUNT | stubs (`0x005140d0` folded, `0x005140e0`) | med |
| 0x2c | MoveAwayFromLocation | `0x0050fd50` | med |
| 0x2d | RandomWalk | `0x00515ac0` | med |
| 0x2e | ITEMCASTSPELL | `0x0050f170` | med |
| 0x30 | JumpToObject | `0x0051d110` | med |
| 0x32 | COUNTERSPELL | `0x00514270` | med |
| 0x36 | PICKPOCKET | folded stub | med |
| 0x37 | FOLLOW (ActionForceFollowObject) | `0x005132e0` | med |
| 0x38 | HEAL | `0x00517a60` | med |
| 0x3d | FOLLOWLEADER | `0x00511130` | med |
| 0x3e | BarkString | `CSWSObject` `0x0057ce00` | med |
| 0x3f | an int-parameter step queued before attacks/spells (script id 39, no constant) | `0x005b6210` | low |
| 0x41 | SurrenderToEnemies | `0x0051b420` | med |

### The combat round

`CSWSCombatRound` (0x9d8 bytes at creature `+0x9c8`, ctor `0x004d5cb0`) holds five 0x14c-byte
attack records from `+4` (`CSWSCombatAttackData`, reset by `0x004d3010`, saved/loaded by
`0x004d2210`/`0x004d2450`), the owner at `+0x9b4`, and the round timer: `StartCombatRound`
(`0x004d5f70`) sets a 3000 ms round (`+0x94c`) and wires up KOTOR's paired animations — a round
can be a *master* (`+0x9b8`) or *slave* (`+0x9bc`) of another creature's round, with the ids at
`+0x9c0`/`+0x9c4`. The attack, cast-spell and item-cast-spell action handlers start rounds;
`CSWSCreature::UpdateCombat` (`0x004faf20`, from `AIUpdate`) drives `IncrementTimer`
(`0x004d4c10`), `DecrementPauseTimer` (`0x004d4e80`) and `EndCombatRound` (`0x004d4620`), whose
log strings name the class. Saved as `CombatRoundData` (`0x004d3ec0` / `0x004d5120`). (high for
structure and timers, med for the master/slave reading)

## 6. Open questions

- CSWSObject slots 41–43 (`0x004d09e0`, `0x004d0e40`, `0x004cf160`): large, many-argument,
  shared by every class; saving throws or spell resistance are the guesses.
- Slots 48/49 and 54–56, the creature helper at `+0xa2c`, and action ids 2, 4, 0xa, 0x10, 0x11,
  0x12, 0x1f, 0x21, 0x22, 0x31, 0x33–0x35, 0x3a, 0x3c, 0x40.
- Where non-creature heartbeats fire (placeable/door/trigger `AIUpdate` were not read in detail),
  and what event ids 3/6 do in the event handlers.
- Internal object types 0–2, 8 and 15, and the exact role of the client half of the object table
  when the client and server run in one process.
- The full creature member map beyond what the loaders and getters touch (perception lists,
  equipped items, party/dying state at `+0x9d4`).
