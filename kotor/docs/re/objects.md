# Server-side game objects in swkotor.exe

How the original engine represents the things that live in a module: the id → object lookup,
the class hierarchy and its vtables, how objects are built from templates (`UT?`) and the area's
`GIT`, the creature stats block, and the machinery that makes objects act: the event queue, script
slots, the action queue and the combat round. Addresses are for the Steam `swkotor.exe` after
SteamStub removal (see [README.md](README.md)). Every claim ends with a confidence (high / med /
low); names are ours, in the engine family's style (most of them NWN-derived), unless a log string
gives the real one. Proposed names for all addresses below are in
`kotor/re/proposals/objects.tsv` (git-ignored scratch, merged into [names.tsv](names.tsv)).
The whole page was rechecked claim by claim on 2026-10-07 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)), vtable slots from the raw tables; a med claim
that says "needs a runtime check" rests on static reading alone and is surprising enough to test
before relying on it.

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

The most common pattern in the script commands: `GetObjectArray()` (`0x004aed70`), then
`CGameObjectArray::GetGameObject(id, &obj)` (`0x004d8230`), then a check of the type byte at
`obj+8` or a virtual `As*` cast; many commands use the typed getters below instead.
`CServerExoApp::GetGameObject` (`0x004ae750` → `0x004b1700`) does the first two in one call and
returns null on failure. (high)

### CGameObjectArray

The server and the client each own one (`0x18` bytes); both are built with the two-halves flag
set, so each has `0x2000` buckets.

| Offset | Meaning |
|---|---|
| `+0x00` | bucket array: `0x1000` buckets for plain ids, then (when `+0x14` is set) `0x1000` for ids with bit 31 set (`0x2000` pointers) |
| `+0x04` | next low id of the first half (counts up from 0) |
| `+0x08` | next low id of the bit-31 half |
| `+0x0c` | next high id of the first half (counts down from `0x7fffffff`) |
| `+0x10` | next high id of the bit-31 half (from `0x7fffffff`) |
| `+0x14` | "two halves" flag passed to the constructor (1 at every construction site) |

Each bucket is a singly linked chain of 12-byte nodes `{id without bit 31, object, next}`, kept
in descending id order. The bucket index is `id & 0xfff`, plus `0x1000` when bit 31 of the id is
set. A lookup returns 0 on success and 1 when the id is absent (and nulls the out pointer); the
add functions return 0 on success, 1 for an id outside the valid ranges and 4 for a null object.
(high)

| Address | Name | What it does | Conf. |
|---|---|---|---|
| `0x004d7d80` | `CGameObjectArray::CGameObjectArray` | allocates the buckets, sets the counters | high |
| `0x004d7e10` | `~CGameObjectArray` | calls the deleting destructor (slot 0) of every object still registered, then frees the buckets | high |
| `0x004d80e0` | `AddInternalObject(&id, obj, bCharacter)` | allocates a fresh id in the first half: low counter for ordinary objects, high counter (`0x7fffffff` downward) for character objects | high |
| `0x004d7e90` | `AddObjectAtPos(id, obj)` | registers under a caller-chosen id (either half) and moves that half's counter past it; accepts low ids below `0x01000000` and high ids `0x7f000001`–`0x7fffffff`, rejects the rest (1). If the id is already taken it does not replace the entry: it registers the *existing* object again under the next counter id and drops the new one (needs a runtime check) | med |
| `0x004d7ff0` | `AddExternalObject(&id, obj)` | registers under the caller's id in the bit-31 half, moves that half's counter past it and sets bit 31 of `*id` | high |
| `0x004d8230` | `GetGameObject(id, &obj)` | the lookup | high |
| `0x004d81a0` | `Remove(id, &obj)` | unlinks and returns the object | high |
| `0x004d8290` | `Delete(id)` | unlinks without returning it | high |

**Ids.** `OBJECT_INVALID` is `0x7f000000`. Server objects get ids from the low counter
(0, 1, 2 …); character objects (`bCharacterObject` in the constructor: the player and party
character creatures built by the player loaders such as `CSWSPlayer::LoadCharacter`
`0x00561e30`) count down from `0x7fffffff`. The client keeps its own array at client internal
`+0x14` (reached through `g_pAppManager+4`), created in `CClientExoAppInternal::Initialize`
(`0x005f8550`) and rebuilt by `0x005f8290`. Client copies of server objects (`CSWC*`) are
registered there by `AddExternalObject` under the server id with bit 31 set; client-only objects
(e.g. the type-8 class of `0x006d57b0`) take fresh ids from the client array's first half.
`0x004b1f70` (forwarded by `0x004aea30`) turns a bit-31 id back into the server id by clearing
bit 31. The server creates its array in `CServerExoAppInternal::Initialize` (`0x004b63e0`) and
builds a fresh one in `UnloadModule` (`0x004b9240`). (high for the server side, med for the
client)

### Typed getters

`CServerExoApp` forwards each to `CServerExoAppInternal`; each checks the type byte and returns
the matching `As*` cast, or null. `GetGameObject` does no type check, and `GetModule` looks up
the current module id (`+0x10060`) and casts with `AsSWSModule` without checking the byte.

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
`0x004aea40` → `0x004b4cb0` returns the creature id of the player whose player id is 0
(`OBJECT_INVALID` if none); `0x004aed80` returns the AI
master, `0x004aede0` the world timer, `0x004aed90` the player list. (high/med)

## 2. The class hierarchy

### Object types

The byte at `+8` of every game object. The script-visible constants come from
`GetObjectType` (`0x0053c610`), which maps internal → `OBJECT_TYPE_*`; it returns 0 for an
unknown id or a type ≤ 4 and `0x7fff` (`OBJECT_TYPE_INVALID`) for any other unlisted type.
Anything ≤ 4 is not a "real" object for most script commands. (high)

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

0–2, 8 and 15 never appear in a server constructor. 8 is used by a client-only class (constructor
`0x006d57b0`, vtable `0x00757cc8`); by analogy with NWN 0–2 would be GUI, tile and (unused), 8
the projectile and 15 player-TURD/portal. (low)

### CGameObject (`vftable 0x007457a0`, 28 slots)

`CGameObject::CGameObject(type, id)` (`0x004d7d60`) stores id at `+4` and the type byte at `+8`;
destructor `0x004c3030`, deleting destructor `0x004c3040`. Its vtable is the shared header of every
game object, server and client:

| Slot (offset) | Meaning |
|---|---|
| 0 (`0x00`) | scalar deleting destructor |
| 1 (`0x04`) | SetId(id): empty (`0x0060e760`) in the base and every server class but the creature, whose `0x004eb160` stores the new id at `+4` (with bookkeeping calls around it); every client object overrides it with `0x00616fa0` (store at `+4`) |
| 2 (`0x08`) | ResetUpdateTimes(day, time): empty (`0x005b5e90`) except the server creature, whose `0x004eb6b0` writes the pair to `+0x350`, `+0x388` and `+0xa8` (NWN names; med) |
| 3 / 4 (`0x0c` / `0x10`) | AsSWCObject / **AsSWSObject** |
| 5 / 6 (`0x14` / `0x18`) | AsSWCDoor / **AsSWSDoor** |
| 7 / 8 (`0x1c` / `0x20`) | AsSWCModule / **AsSWSModule** |
| 9 / 10 (`0x24` / `0x28`) | AsSWCArea / **AsSWSArea** |
| 11 / 12 (`0x2c` / `0x30`) | AsSWCCreature / **AsSWSCreature** |
| 13 / 14 (`0x34` / `0x38`) | AsSWCItem / **AsSWSItem** |
| 15 / 16 (`0x3c` / `0x40`) | AsSWCTrigger / **AsSWSTrigger** |
| 17 (`0x44`) | client only: the type-8 client class (`0x006d57b0`, vtable `0x00757cc8`), likely AsSWCProjectile |
| 18 / 19 (`0x48` / `0x4c`) | **AsSWSPlaceable** / AsSWCPlaceable |
| 20 / 21 (`0x50` / `0x54`) | **AsSWSAreaOfEffectObject** / AsSWCAreaOfEffectObject |
| 22 (`0x58`) | **AsSWSWaypoint** |
| 23 (`0x5c`) | **AsSWSEncounter** |
| 24 (`0x60`) | no game-object vtable overrides it, server or client (no client class has type 14; likely AsSWCStore) |
| 25 (`0x64`) | **AsSWSStore** |
| 26 / 27 (`0x68` / `0x6c`) | **AsSWSSoundObject** / AsSWCSoundObject |

The server rows are high (each typed getter pairs a type byte with one slot); the client column is
high as well: each client vtable overrides exactly the slot named, and its constructor passes the
matching type byte (creature `0x0074f5f8`/5, item `0x00751a58`/6, trigger `0x00754440`/7,
placeable `0x007537d0`/9, door `0x00753960`/10, AoE `0x00757e28`/11, sound `0x007522a8`/16,
module `0x00751848`/3, area `0x0074ee80`/4). The client waypoint (`0x00754598`/12) and a second
type-11 client class (`0x00754278`) override only slot 3. Bodies are folded: "return null" is
`0x0063e7f0` and "return this" is `0x00641db0` everywhere, so the cast slots can't be named per
class; the three classes that use multiple inheritance have real thunks instead: item
`0x00646380` (`this-0x10`, shared with the client item), module `0x004c6bb0` (`this-0x1c`),
area `0x0050d340` (`this-0x11c`); the client area's slot 9 is `0x00606470` (`this-0x100`). (high)

### Per-type table

All the "object" classes (everything but module and area) derive from `CSWSObject`, whose
constructor `0x004cfcb0(type, id, bCharacter)` calls `CGameObject::CGameObject` and then
registers the object: `AddObjectAtPos` when an id is given, `AddInternalObject` when the id is
`OBJECT_INVALID`. Area and module constructors register themselves the same way (the module is
always built with `OBJECT_INVALID` and gets a fresh id). (high)

| Class | Type | vtable (slots) | Constructor | Destructor | Deleting dtor | Conf. |
|---|---|---|---|---|---|---|
| `CGameObject` | — | `0x007457a0` (28) | `0x004d7d60` | `0x004c3030` | `0x004c3040` | high |
| `CSWSObject` | — | `0x00745f18` (56) | `0x004cfcb0` | `0x004d0220` | `0x004d09c0` | high |
| `CSWSCreature` | 5 | `0x007470c8` (57) | `0x004f7a10` | `0x004f8410` | `0x004fde20` | high |
| `CSWSItem` | 6 | `0x00748da0` primary (1), `0x00748cc0` (56) for the `CSWSObject` at `+0x10` | `0x005530a0` | `0x0055ec70` | `0x0055fcb0` | high |
| `CSWSTrigger` | 7 | `0x00749a38` (56) | `0x0058eae0` | `0x0058eef0` | `0x0058f690` | high |
| `CSWSPlaceable` | 9 | `0x007494d0` (56) | `0x005877e0` | `0x005854b0` | `0x00587a50` | high |
| `CSWSDoor` | 10 | `0x007498b0` (56) | `0x00589ee0` | `0x0058b550` | `0x0058c810` | high |
| `CSWSAreaOfEffectObject` | 11 | `0x00749ea8` (56) | `0x00594480` | `0x005963d0` | `0x005965b0` | high |
| `CSWSWaypoint` | 12 | `0x0074bf80` (56) | `0x005c7e70` | `0x005c84e0` | `0x005c8630` | high |
| `CSWSEncounter` | 13 | `0x00749d98` (56) | `0x00593c70` | `0x00593380` | `0x00593f90` | high |
| `CSWSStore` | 14 | `0x0074bdb8` (56) | `0x005c6ab0` | `0x005c6bf0` | `0x005c7160` | high |
| `CSWSSoundObject` | 16 | `0x0074c0b8` (56) | `0x005c8f30` | `0x005c8660` | `0x005c9020` | high |
| `CSWSArea` | 4 | `0x00747bfc` primary (7), `0x00747bf8` (1) for the resource helper at `+0x100`, `0x00747b88` (28) for the `CGameObject` at `+0x11c` | `0x0050cf80` | `0x0050d370` | `0x0050dfb0` | high |
| `CSWSModule` | 3 | `0x00745960` primary (1), `0x007458f0` (28) for the `CGameObject` at `+0x1c` | `0x004c84a0` | `0x004c68a0` | `0x004c8940` | high |

Notes:
- **Item**: the object array holds the address of the `CSWSObject` sub-object (`item+0x10`); the
  primary base (`CSWItem`, ctor `0x005b4660`, one-slot vtable `0x0074b2a0`) is the shared item
  data; the `CSWSObject` vtable's slot 0 is the `this-0x10` thunk `0x00555710`. Field
  offsets in the item loaders are relative to the `CSWItem` start, so `CSWSObject` fields appear
  shifted by `0x10` there (plot flag at `+0x108`, not `+0xf8`). (high)
- **Area / module** don't derive from `CSWSObject`: they embed a bare `CGameObject` at `+0x11c` /
  `+0x1c`. The module's primary base is a resource helper (vtable `0x007458d4`, resref at `+0xc`).
  The area's primary base at `+0` is another class (ctor `0x0058f6b0`) and its resource helper sits
  at `+0x100` (resref at `+0x10c`; its vtable becomes the `this-0x100` destructor thunk
  `0x00747bf8`). Their tags are at area `+0x158` and module `+0x1f8`, their locals at area `+0x1f4` and
  module `+0x9c` (from `GetTag` and `GetLocalBoolean`). (high)
- Every `CSWSObject` class except the waypoint and the sound joins the AI master at level 0 in its
  constructor (`CServerAIMaster::AddObject` `0x004b0850`, keyed by id; the level is kept at
  `+0x78`): creature, item, placeable, door, trigger, encounter, AoE and store. (high)

### CSWSObject virtual functions (slots 28–55)

| Slot (offset) | Name | Base | Overrides | Conf. |
|---|---|---|---|---|
| 28 (`0x70`) | AIUpdate (called by `CServerAIMaster::UpdateState`) | purecall | creature `0x004fe210`, item `0x0055cb60`, placeable `0x005849d0`, door `0x005889c0`, trigger `0x0058d760`, encounter `0x00593fb0`, AoE `0x00595d10`; store/waypoint/sound: empty | high |
| 29 (`0x74`) | ClearAction(node, bForce) | `0x004cc390` | creature `0x004fab00` | med |
| 30 (`0x78`) | EventHandler(event, caller, data, day, time) | purecall | creature `0x004fece0`, item `0x0055ee10`, placeable `0x00587ba0`, door `0x0058b850`, trigger `0x0058f140`, encounter `0x00594220`, AoE `0x005964e0`, store `0x005c6ee0`, waypoint `0x005c7f10`, sound `0x005c8650` | high |
| 31 (`0x7c`) | SetAnimation(n) | `0x004ccf60` | creature `0x004f0d70` | high |
| 32 (`0x80`) | GetDialogResRef | `0x004d0170` (empty resref) | creature `0x004f8290` (stats `+0x44`), placeable `0x00585620` (`+0x240`), door `0x0058a1b0` (`+0x2a2`) | med |
| 33 (`0x84`) | GetInterruptable | folded "1" (`0x0063e7a0`) | creature `0x004f82e0` (stats `+0x54`, 0 without stats) | med |
| 34 (`0x88`) | GetGender | `0x004cb190` (returns 0) | creature `0x004f82f0` (stats byte `+0x64`) | med |
| 35 / 36 (`0x8c` / `0x90`) | GetFirstName / GetLastName | both `0x004d0190` (`+0xc`) | 35: creature `0x004f8310` (stats `+0x34`), item `0x00553200` (`+0x270` of the `CSWSObject`), trigger/placeable `0x0058ed60` (`+0x228`), door `0x0058a1e0` (`+0x39c`), waypoint `0x005c7f00` (`+0x238`), encounter `0x00593510` (`+0x230`) — each class's own name field; 36: creature only, `0x004f8330` (stats `+0x3c`) | high |
| 37 (`0x94`) | GetDead | `0x004cb810` | creature `0x004ef820`, placeable/door `0x00588ab0` | high |
| 38 (`0x98`) | GetMaxHitPoints(bIncludeBonus) | `0x004d01a0` | creature `0x004ed310` | high |
| 39 (`0x9c`) | GetCurrentHitPoints(bExcludeTemp) | `0x004caec0` | — | high |
| 40 (`0xa0`) | DoDamage(n) | `0x004ccf80` | placeable/door `0x00589190` | med |
| 41–43 (`0xa4`–`0xac`) | DoDamageReduction / DoDamageResistance / DoDamageImmunity (see combat.md) | `0x004d09e0`, `0x004d0e40`, `0x004cf160` | — | high |
| 44 (`0xb0`) | GetDamageImmunity(type) | `0x004caee0` | — | med |
| 45 (`0xb4`) | GetDamageImmunityByFlags(flags) | `0x004caf70` | — | med |
| 46 / 47 (`0xb8` / `0xbc`) | Get/SetLastSpellId: the creature's event handler sets it from the spell event around the impact script and resets it to -1; `CGameEffect::SetCreator` (`0x00503a00`) copies the creator's value into the effect | `0x00406490` ("-1") / empty | creature `0x004f8350`/`0x004f8360` (`+0x8f0`), placeable `0x00585650`/`0x00585660` (`+0x388`), AoE `0x005945d0`/`0x005945e0` (`+0x234`) | med |
| 48 / 49 (`0xc0` / `0xc4`) | SetInteractTarget / GetInteractTarget; RunActions calls 48 with `OBJECT_INVALID` when a finished action other than ATTACKOBJECT leaves 49 set | 48: empty `0x0060e760` for every class, creature included (so that RunActions reset does nothing); 49: `0x004d01b0` (`OBJECT_INVALID`) | 49: creature `0x004f8280` (`+0x944`, the interact target, which `ClearAction` clears through the non-virtual `SetInteractTarget` `0x004f34a0`) | med |
| 50 / 51 (`0xc8` / `0xcc`) | GetPortrait / SetPortrait (resref) | `0x004d01c0` / `0x004d01f0` | creature `0x004f8370` / `0x004f83c0` | med |
| 52 / 53 (`0xd0` / `0xd4`) | GetPortraitId / SetPortraitId (id at `+0x30`; Set looks up `portraits.2da` BaseResRef and calls slot 51) | `0x004d0210` / `0x004cad20` (prefixes `po_` to BaseResRef, whose values already start with `po_`) | 53: creature `0x004ed4c0` (uses BaseResRef unchanged) | high |
| 54, 55 (`0xd8`, `0xdc`) | UpdateEffectPtrs / UpdateAttributesOnEffect(effect) (see rules.md) | empty (`0x004015a0` / `0x0060e760`) | creature `0x004f14f0`, `0x004ffaf0` | high |
| 56 (`0xe0`) | creature only: sends a server message (minor `0xb`) carrying its argument to every player whose creature is a faction member in the same area within 30 m | — | `0x004ec610` | med |

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
| `+0x100` | named script variables (GFF `VarTable`) | `0x0059aa80` | high |
| `+0x110` | KOTOR local booleans/numbers (GFF `SWVarTable`): 96 bits + 8 bytes | GetLocalBoolean | high |
| `+0x124` / `+0x128` | effect list (array of effect pointers / count) | `SaveEffectList` `0x004cc9d0`, EffectList | high |
| `+0x1ac` | pointer to a 15-byte table of per-damage-type immunity percentages (signed, read clamped to −100..100), allocated and zeroed by the constructor | slot 44 | high |
| `+0x1e4` | action node currently executing | RunActions | high |
| `+0x1fc` | dirty flags (1 animation, 2 position, 4 orientation) | setters | high |
| `+0x200` | Min1HP | GetMinOneHP, "Min1HP" | high |
| `+0x218` | PartyInteract | placeable loader | med |

`CSWSObject` itself is about `0x228` bytes: every derived class starts its own fields there
(waypoint map note at `+0x228`, store `OnOpenStore` at `+0x228` …): the constructor's last
field is `+0x224`. (high)

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
| waypoint | `0x005c83b0` (UTW; used only by `CreateObject`) | `0x005c7f30` | `0x00505360` "WaypointList" | `0x005c8230` | `0x00507a50` |
| sound | `0x005c94e0` (UTS) | `0x005c9040` | `0x00505560` "SoundList" | `0x005c86d0` | `0x00507b10` |
| encounter | `0x00593a90` (UTE) | `0x00592430`, scripts `0x00590820`; full GIT struct `0x00593830` | `0x00505060` "Encounter List" | `0x00591350` | `0x00507990` |
| store | `0x005c7760` (UTM) | `0x005c7180` | `0x005057a0` "StoreList" | `0x005c6cd0` | `0x00507ca0` |
| area of effect | — (shape from `vfx_persistent.2da`, `0x005947b0`) | `0x00594b00` | `0x00505af0` "AreaEffectList" | `0x00594d80` | `0x00507d60` |

All high. The whole GIT is read by `CSWSArea::LoadGIT` (`0x0050dd80`), which honours the
`UseTemplates` byte (default 0). Without it every list entry is the full struct. With it an entry
is `TemplateResRef` plus placement for creatures, items, sounds and placeables; stores name the
template `ResRef`; doors also take `TransitionDestination`, `LinkedTo`, `LinkedToFlags` and
`LinkedToModule` from the entry (`0x0058c5f0`), triggers the same plus `Geometry`, encounters
position plus `Geometry`. Doors and placeables are placed by `X`/`Y`/`Z` + `Bearing`, the rest by
`X/Y/ZPosition` (+ orientation). Waypoints and areas of effect have no template path: their
entries are always full structs. When loading a save, LoadGIT also reads the area's `VarTable`,
`SWVarTable` and weather, and the list loaders call `LoadObjectState` per object. (high)

`CSWSArea::SaveGIT` (`0x0050ba00`) builds a new "GIT " V2.0 GFF: the area's `VarTable` and
`SWVarTable`, `CurrentWeather`, `WeatherStarted`, `TransPending`/`TransPendNextID`/
`TransPendCurrID`, then the ten lists (each element `ObjectId` + the full struct, so a saved GIT
has no `UseTemplates` and loads as full structs), the area properties, area map and cameras, and
adds it to the save's ERF as resource type `0x7e7` under the area's resref. Creatures whose stats
`+0x6c` (IsPC) is set are not written here but handed back to the caller in a list, and
`SaveCreatures` also skips creatures with `+0xa88` set. (high)

The ARE reader and module/IFO loading belong to [modules.md](modules.md). The placeable template
loader's error message says "Item template %s doesn't exist" — a copy-paste slip in the original.

**Common object state.** `CSWSObject::LoadObjectState` (`0x004d1cf0`) reads what every saved
object carries: `EffectList` (`0x004d1be0`), `VarTable` (`0x0059aa80`), `SWVarTable`
(`0x0059b0f0`), `ActionList` (`0x004cecb0`) and `Commandable`; the writers are `0x004cec50`,
`0x004cc9d0`, `0x0059adb0`, `0x0059b250`, `0x004cc7e0`, called in that order by
`SaveObjectState` (`0x004cec50`), which then writes `Commandable`. (high)

**Creature template load, in order** (`0x005026d0`): open UTC → stats (`ReadStatsFromGff`, which
also fills names, appearance, faction, HP/FP) → the 14 script resrefs → inventory → known spells
→ `PM_IsDisguised`/`PM_Appearance` → `StealthMode` → object state → position/orientation and
`JoiningXP` (`+0x22c`) read, then position set (orientation only when non-zero) → `PostProcess`
(`0x004f1c40`). A non-zero return from `ReadStatsFromGff` aborts the load. `PostProcess` puts a
PC (stats `+0x6c`) at AI level 4 and flags its items (`+0x288 | 8`), registers the tag, copies
IsPC to `+0x9d4`, puts the creature in its faction (an unknown faction id gives faction 1, logged),
updates pathfinding sizes, applies a permanent effect of type 0x44, and handles a creature loaded
with HP below 1 (animation 10008, not commandable). (high)

**Tags.** Loaders call `SetTag` and register `(tag, id)` with the module's sorted lookup table
(`CSWSModule::AddObjectToLookupTable`, `0x004c7de0`: 0x28-byte entries at module `+0x130`, count
`+0x134`, the lower-cased tag then the id at `+0x24`, inserted after any equal tags at the
position found by binary search `0x004c5e60`), which is what tag searches use. Items, placeables,
triggers, encounters, stores and waypoints register in their field readers; creatures in
`PostProcess`, doors in `0x0058c5f0`, sounds when added to an area (`0x005c8950`), areas of
effect in `0x005947b0` (the save reader `0x00594b00` sets the tag only). (high)

### Script slots

Creature (`ReadScriptsFromGff`, `0x004ebf20`): 14 `CExoString`s, 8 bytes apart, initialised to
"default" by the constructor. "Script event n" rows run from the creature's event handler
(`0x004fece0`) when that queued event arrives; the other rows are direct `RunScript` calls, not
queued. (high)

| Offset | GFF label | Fired by |
|---|---|---|
| `+0x230` | ScriptHeartbeat | `RunHeartbeat` (`0x004eb6e0`) on a 3000–4199 ms timer re-rolled after each heartbeat; at AI level 0 only every (interval / 64)-th due tick fires ([gameloop.md](gameloop.md) 2.4) |
| `+0x238` | ScriptOnNotice | script event 1 (perception) |
| `+0x240` | ScriptSpellAt | script event 2 |
| `+0x248` | ScriptAttacked | creature event handler, AI event 15 ON_MELEE_ATTACKED, unless dead or dying ([combat.md](combat.md) 9) |
| `+0x250` | ScriptDamaged | run directly by `OnApplyDamage` (`0x004dfa40`), except for the PC, the dead or downed and the party leader ([combat.md](combat.md) 6.6 step 5); the creature handler has no case for script event 4 |
| `+0x258` | ScriptDisturbed | script event 0x1b (inventory disturbed) |
| `+0x260` | ScriptEndRound | end of combat round (`EndCombatRound` `0x004d4620`, [combat.md](combat.md) 3.5); also when a SETSTATE_INTERNAL effect of state 1 or 3–10 is removed (`0x004da870`, [rules.md](rules.md)) |
| `+0x268` | ScriptDialogue | script event 7 (when empty or "default" the slot is set to `k_hen_dialogue01`) |
| `+0x270` | ScriptSpawn | `RunHeartbeat`, once (`+0x34c` "CreatnScrptFird" flag, set at the end of the first `RunHeartbeat`); a summoned creature's is run directly by `OnApplySummonInternal` (`0x004d8a40`), which sets the flag first |
| `+0x278` | ScriptRested | — (no code found that runs it) |
| `+0x280` | ScriptDeath | `OnApplyDeath` (`0x004e0ac0`, [combat.md](combat.md) 8.2) |
| `+0x288` | ScriptUserDefine | script event 0xb (user defined; event number kept at `+0x150`) |
| `+0x290` | ScriptOnBlocked | script event 0x1f (path blocked; not for a creature a player controls; caller kept at `+0x33c`) |
| `+0x298` | ScriptEndDialogue | `EndConversation` (`0x005a0a40`) through `0x004ef910`, for every creature in the area at a normal conversation end ([dialogue.md](dialogue.md)) |

Other types, as the field readers store them (med; read from the loaders, not yet from the
firing side):

- **Placeable** (`0x00585670`): OnClosed `+0x294`, OnDamaged `+0x29c`, OnDeath `+0x2a4`,
  OnDisarm `+0x2ac`, OnHeartbeat `+0x2b4`, OnInvDisturbed `+0x2bc`, OnLock `+0x2c4`,
  OnMeleeAttacked `+0x2cc`, OnOpen `+0x2d4`, OnSpellCastAt `+0x2dc`, OnTrapTriggered `+0x2e4`,
  OnUnlock `+0x2ec`, OnUsed `+0x2f4`, OnUserDefined `+0x2fc`, OnDialog `+0x304`, OnEndDialogue
  `+0x30c`. An empty or "default" OnTrapTriggered is replaced by the `traps.2da` "MineScript" entry
  of TrapType; `traps.2da` has no such column, so it ends up empty (needs a runtime check).
- **Door** (`0x0058a1f0`): OnOpen `+0x228`, OnClosed `+0x230`, OnDamaged `+0x238`, OnDeath
  `+0x240`, OnDisarm `+0x248`, OnHeartbeat `+0x250`, OnLock `+0x258`, OnMeleeAttacked `+0x260`,
  OnSpellCastAt `+0x268`, OnTrapTriggered `+0x270`, OnUnlock `+0x278`, OnUserDefined `+0x280`,
  OnClick `+0x288`, OnDialog `+0x290`, OnFailToOpen `+0x298` (same "MineScript" fallback for
  OnTrapTriggered as placeables). LinkedTo `+0x388`, TransitionDestination `+0x3c8`.
- **Trigger** (`0x0058da80`): ScriptHeartbeat `+0x244`, ScriptOnEnter `+0x24c`, ScriptOnExit
  `+0x254`, ScriptUserDefine `+0x25c`, OnTrapTriggered `+0x264`, OnDisarm `+0x26c`, OnClick
  `+0x274`; Geometry follows. An empty or "default" OnTrapTriggered becomes the `traps.2da`
  TrapScript of TrapType. A missing OnClick field defaults to the OnEnter script (the reader
  passes `+0x24c` as the default).
- **Encounter** (`0x00590820`): OnEntered `+0x2e8`, OnExit `+0x2f0`, OnHeartbeat `+0x2f8`,
  OnExhausted `+0x300`, OnUserDefined `+0x308`.
- **Store**: OnOpenStore `+0x228`. **Waypoint**: HasMapNote `+0x228`, MapNoteEnabled `+0x22c`,
  MapNote `+0x230` (stored only when HasMapNote is present and non-zero), LocalizedName
  `+0x238`.

## 4. Creatures and their stats

### CSWSCreature members

Constructor `0x004f7a10`.

| Offset | Meaning | Conf. |
|---|---|---|
| `+0x22c` | JoiningXP (read by `LoadFromTemplate`, written by `SaveCreature` `0x00500610`) | high |
| `+0x230..+0x298` | the 14 script names (above); a second array of 14 strings follows at `+0x2a0` (use not traced) | high |
| `+0x340` | `CPathfindInformation*` (0x278 bytes, ctor `0x005d0ce0`); `+0x254` inside is the blocking creature (`GetBlockingCreature` `0x00546e00` returns it) | med |
| `+0x34c` | spawn script already fired (GFF `CreatnScrptFird`; `RunHeartbeat` runs ScriptSpawn `+0x270` while it is 0) | high |
| `+0x350/+0x354`, `+0x358` | last heartbeat time (world day, time of day), heartbeat interval (3000 + rand % 1200 ms, redrawn after each heartbeat) | high |
| `+0x35c` | interval of the frequent perception update in `RunHeartbeat` (300 + rand % 400 ms) | med |
| `+0x4d0` / `+0x4d1` | DetectMode / StealthMode (GFF bytes, `SaveCreature`) | high |
| `+0x4f8` | creature size (GFF `CreatureSize`, default 3) | high |
| `+0x914` / `+0x918` | perception ranges, primary / secondary (set by the stats loader, below) | high |
| `+0x9c8` | `CSWSCombatRound*` (0x9d8 bytes) | high |
| `+0x9d4` | the creature is the player character ([combat.md](combat.md), creature members used by combat) | med |
| `+0x9d8` | sound set (ushort, GFF `SoundSetFile`, default 0xffff) | high |
| `+0x9da` | BodyBag (byte) | high |
| `+0x9fc`/`+0xa00` | activity bits (stealth 1, combat/Force modes `0x100..0x2000`) / lock and state bits (a mode whose bit is set here is not turned off by `ClearActivities`) ([actions.md](actions.md) 1.4) | med |
| `+0xa2c` | `CSWInventory*` (0x4c bytes, ctor `0x005a4930`): the equipped items, `GetItemInSlot(slotMask)` `0x005a4c20` | high |
| `+0xa30` | `CItemRepository*` (inventory, 0x18 bytes; ctor `0x0055d290`) | med |
| `+0xa48`/`+0xa4c` | PM_IsDisguised / PM_Appearance (read only when disguised) | high |
| `+0xa50..+0xa73` | visible-appearance record, the third argument of the stats loader: item ids in equipment slots 0x20, 0x10, 0x2, 0x1 (left weapon, right weapon, body armour, head) at `+0xa50..+0xa5c` (`OBJECT_INVALID` initially, refreshed by `0x004ed620`), then copies of Appearance_Type `+0xa60`, Phenotype `+0xa62`, Gender `+0xa63`, the four colours `+0xa64..+0xa67`, Appearance_Head `+0xa68`, Tail `+0xa69`, Wings `+0xa6a`, UseBackupHead `+0xa6c`, DuplicatingHead `+0xa70` | high |
| `+0xa74` | `CSWSCreatureStats*` | high |
| `+0xa88` | player-controlled flag (party member under the player; written only by `SetPlayerControlled` `0x004fdb20`) | med |
| `+0xa8c` | forced/ordered movement kind: −1 none, 1 stopped, 2 move-to-point queued, 3 follow leader, 4 Force Push, 5/6 Force Jump | med |

### CSWSCreatureStats (0x1b8 bytes, ctor `0x005aca80`)

From `ReadStatsFromGff` (`0x005afce0`), `SaveStats`/`SaveClassInfo`, the constructor and the script
getters. (high unless marked)

| Offset | Field |
|---|---|
| `+0x00` | feats (`FeatList`): ushort array, pointer / count `+0x04` / capacity `+0x08` |
| `+0x0c` | feat uses: array (pointer, count `+0x10`) of pointers to {feat id, uses spent}, one per feat with a uses-per-day limit (`CSWFeat` `+0x33`), added by `AddFeat` `0x005aa810` |
| `+0x18` | second feat list (pointer, count `+0x1c`), searched by `HasFeatInLists` and the base Fortitude save; not saved, writer not identified (med) |
| `+0x24` | owning creature |
| `+0x28/+0x2c/+0x30` | level-up history (`LvlStatList`): array of 0x30-byte `CSWSLevelStats*` (ctor `0x005cb1b0`), pointer / count / capacity. The constructor creates record 0; the loader reads one record per total level, PCs only; `SaveClassInfo` writes it only for a PC while no party NPC is being played (party table `+0xf0` = −1). Record: `KnownList0` / `KnownRemoveList0` power lists `+0x00` / `+0x0c`, feats `+0x18`, SkillPoints `+0x28`, ability raised `+0x2a`, hit die `+0x2b`, class `+0x2c`, Force die `+0x2d` (med for the record layout) |
| `+0x34` / `+0x3c` | FirstName / LastName (`CExoLocString`) |
| `+0x44` | Conversation resref |
| `+0x54` | Interruptable (default 1) |
| `+0x58` | Description |
| `+0x60` / `+0x64` | Age (int) / Gender (byte, clamped to 4) |
| `+0x68` | Experience (GetXP); set through `SetExperience` `0x005af480`, which refuses a value below the current one |
| `+0x6c` | IsPC (constructor default 1, kept when the GFF has no `IsPC` field) |
| `+0x78` | FactionID as read (default −1); `PostProcess` moves a non-PC's value to `+0x7c` and sets this to −1 ([chargen-creature.md](chargen-creature.md)) |
| `+0x7c` | current faction id |
| `+0x84` | ChallengeRating (float) |
| `+0x88` | StartingPackage |
| `+0x89` | number of classes (at most 2, the two slots that exist; the constructor starts with one: class 0, level 1) |
| `+0x8c` + 0x28·i | class slot i (ctor `0x005ac9f0`): known Force powers `+0x00` (`KnownList0`, read by `ReadSpellsFromGff` `0x005aeb30`), a second list `+0x0c`, spells left / per day `+0x19`/`+0x1a` (`NumSpellsLeft` of the first `SpellsPerDayList` entry; refreshed by `0x005a6d80`), class id `+0x1b`, level `+0x1c`, negative levels `+0x1d` (zeroed on load) (med for the lists and spell counts) |
| `+0xdc` | race (ushort, default 6; indexes the race table at `g_pRules+0xb0`, 0x34-byte rows; a value ≥ the race count `g_pRules+0xaa` fails the load) |
| `+0xe0` | Subrace (string), `+0xe8` SubraceIndex |
| `+0xe9`/`+0xea` | STR / STR modifier |
| `+0xeb`/`+0xec` | DEX / modifier |
| `+0xed`/`+0xee` | CON / modifier |
| `+0xef`/`+0xf0` | INT / modifier |
| `+0xf1`/`+0xf2` | WIS / modifier |
| `+0xf3`/`+0xf4` | CHA / modifier |
| `+0xf5` | NaturalAC |
| `+0x118` | combat information (0x48 bytes, ctor `0x00552280`, `UpdateCombatInformation` `0x005addc0`); its attack/damage fields (`OnHandAttackMod`, `AttackList` …) are loaded and saved with the stats (`0x00552350` / `0x00550f30`) (med) |
| `+0x122` / `+0x124` / `+0x126` | base maximum / current / temporary Force points (`GetCurrentForcePoints` adds the last two; `CSWSCreature::GetMaxForcePoints` `0x004fd490` builds the maximum, [rules.md](rules.md) 3.8: `+0x122` + level × (WIS + CHA modifiers) for everyone but the PC, the level-up history's Force dice for the PC, 0 for droids) |
| `+0x128` | special abilities (`SpecAbilityList`): pointer to an array (pointer, count, capacity) of 0xc-byte {Spell, SpellFlags, SpellCasterLevel} entries |
| `+0x13a` | AIState (ushort) |
| `+0x164` / `+0x168` | SkillPoints (unspent) / pointer to the skill-rank bytes (one per skill, count `g_pRules+0xab`; the loader reads up to 8 `SkillList` entries) |
| `+0x16e` | Portrait resref (read only when `PortraitId` is absent or ≥ 0xfffe; the id itself goes to the creature through `SetPortraitId`, slot 53) |
| `+0x17e` | GoodEvil (ushort, clamped to 100) |
| `+0x182..+0x185` | Color_Skin, Color_Hair, Color_Tattoo1, Color_Tattoo2 |
| `+0x186` | Appearance_Type, `+0x188` Phenotype, `+0x189` Appearance_Head (0 is read as 1) |
| `+0x18a` / `+0x18c` | DuplicatingHead (default 0xff) / UseBackupHead |
| `+0x190` / `+0x191` | Tail / Wings (zeroed by the loader, written by `SaveStats`) |
| `+0x194` | MovementRate (BYTE), or WalkRate (INT) when absent, through `SetMovementRate` `0x005a5680` (rate 7 looks up appearance.2da `MOVERATE`) |
| `+0x1a0..+0x1a2` | fort / will / reflex bonus |
| `+0x1a4` | Deity |
| `+0x1ac` / `+0x1b0` | fractional HP / FP regeneration stores ([rules.md](rules.md) 3.8) |

Hit points and the plot/Min1HP flags live on the creature (`CSWSObject` fields `+0xdc/+0xe0/+0xf8/+0x200`), not in the stats.

**The loader** (`ReadStatsFromGff`, called by `LoadCreature`, `LoadFromTemplate`,
`CSWSPlayer::LoadCharacter` and two others) defaults every field to the value already held and
returns 0, or an error: 0x5f4 race out of range, 0x5f5 a ranges.2da lookup failed, 0x5f6 empty
`ClassList`, 0x5f7 a class id ≥ the class count (`g_pRules+0xa9`) or both slots holding the same
class, 0x5f8 no `ClassList` and no class level already set. It reads the abilities in the order
STR, DEX, INT, WIS, CON, CHA and after each stores the modifier floor((score − 10) / 2) of the
*effective* score (the accessor below: base + race + effects). Besides the stats it sets on the
creature: the tag (`SetTag`), `SoundSetFile`, `Gold` (only while `+0xa88` is clear), `+0xf8` from
`Invulnerable` if present else `Plot`, `Min1HP`, `PartyInteract` `+0x218`, `+0x21c` = not
`NotReorienting`, `Disarmable` `+0x4f4`, `BodyBag`, `HitPoints` `+0xe0`, the perception ranges
`+0x914/+0x918` (ranges.2da `PrimaryRange`/`SecondaryRange` of row 12 for a PC; otherwise of the
`PerceptionRange` field, default 11, where 11 means appearance.2da `PERCEPTIONDIST` of the
creature's appearance), the remembered perceptions (`PerceptionList`: `ObjectId` + four bit flags,
`0x0051b370`) and the combat round (`CombatRoundData`, `LoadCombatRound`). (high)

**Hit and Force points.** `HitPoints` and `ForcePoints` are base maxima (creature `+0xe0`, stats
`+0x122`); `CurrentHitPoints`/`CurrentForce` (default: the base) are stored relative to them. On
load, current = file current + (maximum − base). For a PC the maximum is `GetMaxHitPoints(1)`
(slot 38) / `GetMaxForcePoints`; for anyone else the loader computes it inline as max(level, base +
level × CON modifier) and max(level, base + level × (WIS + CHA modifiers)), and when that floor
applies and the file current is ≥ the base, current = level (med: static reading, needs a runtime
check). The top-level `FeatList` is applied after this (`AddFeat`), and any change it makes to
either maximum is added to the current value. `SaveStats` writes the inverse (`CurrentHitPoints`
= current + base − max, `CurrentForce` likewise) plus derived fields for the toolset:
`MaxHitPoints`, `PregameCurrent`, `MaxForcePoints`, `ArmorClass`, `RefSaveThrow`/`WillSaveThrow`/
`FortSaveThrow` and `MClassLevUpIn` (class count − 1). (high)

Accessors (high): ability scores `GetSTRStat` `0x005a6190`, `GetDEXStat` `0x005a6550`,
`GetCONStat` `0x005a6250`, `GetINTStat` `0x005a6310`, `GetWISStat` `0x005a63d0`, `GetCHAStat`
`0x005a6490` — each is base + race adjustment (race row bytes `+0x18..+0x1d` = STR, DEX, INT, CHA,
WIS, CON) + ability effects, floored at 3 (the order matches `GetAbilityScore`'s 0..5 = STR, DEX,
CON, INT, WIS, CHA); `GetClass(slot)` `0x005a4e90`; `GetClassLevel(slot, bNegative)` `0x005a5090`
and `GetLevel(bNegative)` `0x005a5fd0` (sum of the slots), which subtract the negative levels
`+0x1d` when the flag is set, floor 0; `HasFeatInLists` `0x005a6630` (has the feat: lists `+0x00`
and `+0x18`); `HasFeat` `0x005a6680`, which returns the uses left: 0 without the feat or with its
uses spent, 100 for an unlimited feat; `GetSkillRank` `0x005aa570`.
Writers: `SaveStats` `0x005b1b90`, `SaveClassInfo` `0x005aec90`.

What the routine handlers taught: `GetCurrentHitPoints`/`GetMaxHitPoints` (`0x00539610`) use
virtual slots 39/38 on the creature cast if present, else on the `CSWSObject` cast;
`GetTag` (`0x0053df00`) special-cases module and area; `GetPosition` (`0x0053cae0`) reads
`+0x90`; `GetFacing` (`0x00537fe0`) turns `+0x9c/+0xa0` into degrees; `GetLocalBoolean/Number`
(`0x0053b760`) go to the `SWVarTable` (`GetBoolean` `0x0059b000`, index < 96; `GetNumber`
`0x0059b0b0`, index < 8, byte values); `GetPlotFlag` reads `+0xf8`, `GetMinOneHP` `+0x200`, `GetXP` stats
`+0x68`. (high)
## 5. Making objects act

### The AI master: event queue and per-frame updates

`CServerAIMaster` (internal `+0x10044`, ctor `0x004b0780`) holds five object lists, one per AI
level (0x10 bytes each from `+4`: id array, count, capacity, round-robin cursor; the object
remembers its level at `+0x78`, −1 when not listed), and the event queue at `+0x54`, a
time-ordered `CExoLinkedList` of 0x18-byte nodes `{day, time, caller id, target id, event id,
event data}`. The levels, who sits on which and the frame budget are
[gameloop.md](gameloop.md) 2.1–2.2; the queue's timing rules are gameloop.md 4. (high)

| Address | Name | What it does | Conf. |
|---|---|---|---|
| `0x004b0850` | AddObject(obj, level) | puts an object in a level's list (removing it from its old one) | high |
| `0x004b08a0` | SetAILevel | moves it; nothing when the level is unchanged | high |
| `0x004af3d0` | RemoveObject | takes it out, `+0x78` = −1 | high |
| `0x004b08d0` | AddEventDeltaTime(days, ms, caller, target, event, data) | world-timer time now + delta; an invalid delta frees the payload and queues nothing | high |
| `0x004afdb0` | AddEventAbsoluteTime | sorted insert before the first node with a later time (FIFO among equal times); calls the debug printer `0x004af630` when the flag `0x00831fd8` is set | high |
| `0x004b0ab0` | ClearEventData(event, data) | frees a payload by event type (1 script situation; 8, 0x13 spell-impact data; 10, 0x18, 0x1a `CScriptEvent`; 0x15 attack data; 0x16 `CSWCCMessageData`); other payloads are left alone | high |
| `0x004b0b70` | UpdateState | the per-frame step, called from the server main loop `0x004babb0` | high |
| `0x004b0970` / `0x004b0a00` | Save/LoadEventQueue | GFF `EventQueue` (one struct 0xabcd per node, in queue order) | high |

`UpdateState` works level by level, 4 down to 0, within a 10,000 µs budget (levels 4..1 get 60 %
of what is left, level 0 the rest). Each level's loop moves walking creatures first, then pops
every event whose time has come and dispatches it: objects with type > 4 get virtual slot 30
`EventHandler(event, caller, data, day, time)`, areas go to `CSWSArea::EventHandler`
(`0x0050d6c0`), the module to `CSWSModule::EventHandler` (`0x004c5120`); an event for a vanished
id just has its payload freed. Then the level's next object (round-robin, the cursor kept across
frames) gets virtual slot 28 `AIUpdate()`; the level ends when the budget is used up, when it
comes back to the first object it updated this frame, or when an event has become due. An
`AIUpdate` of 75,000 µs or more is logged (warning 0xa3). Every level gets at least one
`AIUpdate` per frame. Pseudo-code and consequences: gameloop.md 2.2. (high)

**Event ids** (from the debug printer `0x004af630`, which names them all): 1 TIMED_EVENT (payload:
a script situation — DelayCommand/AssignCommand), 2 ENTERED_TRIGGER, 3 LEFT_TRIGGER,
4 REMOVE_FROM_AREA, 5 APPLY_EFFECT, 6 CLOSE_OBJECT, 7 OPEN_OBJECT, 8 SPELL_IMPACT,
9 PLAY_ANIMATION, 10 SIGNAL_EVENT (payload: `CScriptEvent`), 11 DESTROY_OBJECT, 12 UNLOCK_OBJECT,
13 LOCK_OBJECT, 14 REMOVE_EFFECT, 15 ON_MELEE_ATTACKED, 16 DECREMENT_STACKSIZE,
17 SPAWN_BODY_BAG, 18 FORCED_ACTION, 19 ITEM_ON_HIT_SPELL_IMPACT, 20 BROADCAST_AOO,
21 BROADCAST_SAFE_PROJECTILE, 22 FEEDBACK_MESSAGE, 23 ABILITY_EFFECT_APPLIED,
24 SUMMON_CREATURE, 25 ACQUIRE_ITEM, 26 AREA_TRANSITION, 27 CONTROLLER_RUMBLE. (high)

**Script event types** (`CSWSSCRIPTEVENT_EVENTTYPE_ON_*`, the `CScriptEvent` type, a ushort at
`+0`): 0 HEARTBEAT, 1 PERCEPTION, 2 SPELLCASTAT, 4 DAMAGED, 5 DISTURBED, 7 DIALOGUE, 8 SPAWN_IN,
9 RESTED, 10 DEATH, 11 USER_DEFINED_EVENT, 12 OBJECT_ENTER, 13 OBJECT_EXIT, 14 PLAYER_ENTER,
15 PLAYER_EXIT, 16 MODULE_START, 17 MODULE_LOAD, 18 ACTIVATE_ITEM, 19 ACQUIRE_ITEM, 20 LOSE_ITEM,
21 ENCOUNTER_EXHAUSTED, 22 OPEN, 23 CLOSE, 24 DISARM, 25 USED, 26 MINE_TRIGGERED,
27 INVENTORY_DISTURBED, 28 LOCKED, 29 UNLOCKED, 30 CLICKED, 31 PATH_BLOCKED, 32 PLAYER_DYING,
33 RESPAWN_BUTTON_PRESSED, 34 FAIL_TO_OPEN, 35 PLAYER_REST, 36 DESTROYPLAYERCREATURE,
37 PLAYER_LEVEL_UP, 38 EQUIP_ITEM. 3 and 6 have no debug name (NWN: melee attacked, end of
combat round), no event handler has a case for them and no code was found that builds one: in
KOTOR melee-attacked is engine event 15 and the end of the round runs OnEndRound directly
(below). (high for the names and the handlers; med that nothing builds 3 or 6, from a search of
the `CScriptEvent` constructions)

`CScriptEvent` (0x34 bytes; ctor `0x004d7540`, dtor `0x004d7590`, save/load
`0x004d73a0`/`0x004d79b0`): type at `+0`, then four growable lists `{pointer, count, capacity}` —
ints `+4`, floats `+0x10`, strings `+0x1c` (8-byte `CExoString`s), object ids `+0x28`
(`GetInteger` `0x004d6480`, 0 past the end; `GetObjectID` `0x004d64c0`, `OBJECT_INVALID` past the
end; `GetString` `0x004d7360`, "" past the end; `SetObjectID` `0x004d7780` grows the list). The
feedback-message payload `CSWCCMessageData` (ctor/dtor `0x004d69f0`/`0x004d6a40`) has the same
layout with a type byte at `+0` and shares the accessors (`FormatFeedbackMessage` `0x005fcd10`
reads it through them). (high)

### How a script slot gets run

Three routes, all ending in `CVirtualMachine::RunScript(script name, self id, 1)` (`0x005d0fc0`,
see [vm.md](vm.md)):

1. **Signalled.** `SignalEvent` (`0x005439d0`, caller = `OBJECT_SELF` when it exists, queued only
   when the target exists) and the engine itself (e.g. `CSWSArea::AddObjectToArea`, `0x0050dfd0`,
   sends ON_OBJECT_ENTER to the area) queue `AddEventDeltaTime(0, 0, caller, target, 10,
   scriptEvent)`. When it is delivered the target's `EventHandler` switches on the script event
   type, records the context it needs (last perceived, last speaker, user-defined number …) and
   runs the matching slot; in the creature handler (`0x004fece0`): 1 → `+0x238`, 2 → `+0x240`
   (not when dead or dying), 7 → `+0x268` (an empty or "default" name becomes `k_hen_dialogue01`),
   0xb → `+0x288`, 0x1b → `+0x258`, 0x1f → `+0x290` (only without a client object). The same
   function handles the other engine events: 1 runs the script situation with
   `RunScriptSituation` (`0x005d0fd0`); 8 / 0x13 (spell impact) run the payload's impact script
   with the spell id set through slot 47 and reset afterwards; 15 ON_MELEE_ATTACKED records the
   attacker and runs `+0x248` unless dead or dying. A creature whose OnSpawn has not fired yet
   (`+0x34c` = 0) runs `RunHeartbeat(0)` first, so OnSpawn precedes any event. (high)
2. **Timed by the object.** `CSWSCreature::AIUpdate` (`0x004fe210`) calls `RunHeartbeat`
   (`0x004eb6e0`), which runs OnSpawn once and OnHeartbeat on its own timer (gameloop.md 2.4).
   Placeables, doors, triggers and areas of effect run their OnHeartbeat directly from their own
   `AIUpdate` every 6000 ms; the encounter signals script event 0 to itself instead
   (gameloop.md 2.5). (high)
3. **Called where it happens.** Several slots are run directly, not through the queue: OnDamaged
   (`+0x250`) from `OnApplyDamage` (`0x004dfa40`; not for the party leader), OnDeath (`+0x280`)
   from `OnApplyDeath` (`0x004e0ac0`), OnEndRound (`+0x260`) from `EndCombatRound` (`0x004d4620`)
   and from the removal of some states (`0x004da870`), OnSpawn of a summoned creature from
   `0x004d8a40`, the end-of-dialogue script (`+0x298`) from `CSWSDialog::EndConversation`
   (`0x005a0a40` → `0x004ef910`) ([combat.md](combat.md), [rules.md](rules.md)). (high)

### The action queue

[actions.md](actions.md) is the detailed page; this is the outline. (high)

`CSWSObject::AddAction` (`0x004cea20`) appends, and `AddActionToFront` (`0x004ccb00`) prepends, a
0x74-byte node to the `CExoLinkedList` at `+0xfc`: internal action id `+0x00`, 13 parameter
types `+0x04` (1 int, 2 float, 3 object id, 4 string, 5 script situation) and 13 values `+0x38`
(`SetParameter`, `0x004cac30`), group id `+0x6c` (passing `0xffff` starts a new group from the
counter at `+0x14`, `0xfffe` joins the last group created, `+0x16`), parameter count `+0x6e`, and
a may-be-cleared flag `+0x70` (1 when created). Layout and groups: actions.md 1.1–1.2.

Script commands and player orders go through per-class helpers that call these, e.g.
`CSWSCreature::AddMoveToPointAction` (`0x004f8b60`), `AddAttackActions` (`0x004fde40`),
`AddCastSpellActions` (`0x004f9460`), `CSWSObject::AddDoCommandAction` (`0x0057cb10`) and the
door/lock helpers `AddOpenDoorAction` `0x004cfac0`, `AddCloseDoorAction` `0x004cfb20`,
`AddUnlockObjectAction` `0x004cfb80`, `AddLockObjectAction` `0x004cfc20` (actions.md 2).
`ClearAllActions(bClearCombat)` (`0x004ccd80`) does nothing unless the object is commandable
(`+0xe8`); otherwise it asks virtual slot 29 `ClearAction` about every node and frees those it
agrees to, stops a creature's path and, with `bClearCombat`, resets the combat round's attack
records (actions.md 1.5).

**Per frame**, the `AIUpdate` of creatures, placeables, doors, triggers, encounters and AoEs calls
`CSWSObject::RunActions` (`0x0057f4a0`): pop the head, remember it at `+0x1e4` and its id at
`+0x80`, and switch on the id to a handler that returns a status — 1 "still running" (the node
goes back to the head and the loop stops), 4 "retry later" (re-queued at the tail), 2 done or
3 failed (treated alike: the node is freed). Creature-only handlers fail at once for other object
types. The loop goes on while actions finish, until 1000 µs have passed since the `AIUpdate`
began (`CExoTimers::GetHighResolutionTimer`), and always stops after ids 1, 5, 0x30 and 0x33
(move, jump, jump to object, drive). Queues over 75 nodes are reported, over 500 trimmed from the
head while the nodes are clearable, over 1000 emptied. Order of operations: actions.md 1.3.

`GetScriptActionId` (`0x0057a2b0`) maps internal ids to the script `ACTION_*` constants; the full
table of ids, handlers and who queues them is actions.md 1.9, and what each action does is
actions.md 3.

### The combat round

[combat.md](combat.md) 2–3 is the detailed page; this is the outline. (high)

`CSWSCombatRound` (0x9d8 bytes on the heap, pointed to by creature `+0x9c8`, ctor `0x004d5cb0`) holds the attack records
from `+4` (`CSWSCombatAttackData`, 0x14c bytes; the constructor builds 7, but resets, saves and
loads touch only the first 5; `Reinitialize` `0x004d3010`, `SaveData`/`LoadData`
`0x004d2210`/`0x004d2450`), the scheduled combat actions at `+0x9b0` (run by action 0x3f), the
owner at `+0x9b4`, and the round timer: `StartCombatRound` (`0x004d5f70`) sets a 3000 ms round
(`RoundLength`, `+0x94c`) and wires up KOTOR's paired animations — a round can be *engaged*
(`+0x9b8`) with another creature's, this side being the master when `+0x9bc` is set; the pair's
master id is at `+0x9c0` and the slave's at `+0x9c4`, copied into both rounds. The attack,
cast-spell and item-cast-spell action handlers start rounds; `CSWSCreature::UpdateCombat`
(`0x004faf20`, from `AIUpdate`) drives `IncrementTimer` (`0x004d4c10`), `DecrementPauseTimer`
(`0x004d4e80`) and `EndCombatRound` (`0x004d4620`, which runs OnEndRound for every creature but the client party's
leader, combat.md 3.5). Saved as
`CombatRoundData` (`0x004d3ec0` / `0x004d5120`).

## 6. Open questions

- Internal object types 0–2, 8 and 15, and the exact role of the client half of the object table
  when the client and server run in one process.
- Slot 56 (creature `0x004ec610`, sends a message built from its argument to the clients of
  faction members within 30 m) and who calls it.
- The full creature member map beyond what the loaders, getters and the detailed pages touch
  (perception lists).
