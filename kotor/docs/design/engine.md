# The engine core: game state, objects, the frame, scripts, the scene

How the game runs a module: the state it keeps (`World`), the objects in it, one frame in the
order the original runs it, how events and actions reach the NWScript VM, how many agents add the
772 engine routines without stepping on each other, how the scene mirrors objects into draws, and
where the GUI, dialogue, rules and saves plug in. Behaviour comes from the RE notes
([gameloop.md](../re/gameloop.md), [objects.md](../re/objects.md), [actions.md](../re/actions.md),
[movement.md](../re/movement.md), [modules.md](../re/modules.md)); this page is our design on top
of them. Decisions that aren't the original's are marked *ours*.

## Directories

The engine is two layers, as the original is (server and client halves in one process):

| Directory | Namespaces | What | Depends on |
|---|---|---|---|
| `lib/engine` | `world`, `obj`, `clock`, `modload`, `tmpl`, `walkmap`, `events`, `scripts`, `values`, `actions`, `doors`, `ai`, `movement`, `paths`, `perception`, `party`, `globals`, `animname`, `outbox`, `elog`, `report` | the game state and its rules of change: objects, time, events, actions, scripts, walking. **No render, SDL or audio device**: it runs headless, in tests and tools | base, formats, res, script, walk, mdl (animation lengths, hooks) |
| `lib/engine/routines` | `routines` (dispatch) + one `rt_*` namespace per category file | the engine routines scripts call | lib/engine |
| `lib/scene` | `scene`, `visual`, `cam`, `ctl`, `ambience` | the presentation: rooms and VIS, a visual per object (models, animation), the camera, keyboard control, area music and sound objects | lib/engine, render, mdl_cache, mdl_render, material, audio |
| `game/` | top level, `options`, `play` | `fn main`, options, the front end and the game loop (live and headless) | everything |
| `tools/enginetest` | top level | lib/engine alone, headless, for routine and script work: `--module M --frames N --log LIST --report` | lib/engine |
| `build.ctx` | | the `kotor` executable (-O2) | |

Other leads add their own directories beside these (below, "Plugging in"): `lib/rules` (`rules`),
`lib/dialog` (`dlg`), `lib/gui` (`gui`), `lib/frontend` (`frontend`), `lib/save` (`save`), the
minigames. `lib/engine` may name their namespaces once they are merged (ctxlang compiles the whole
program, so directories can refer to each other); until then a `// HOOK(name)` comment marks
where each plugs in.

## The World

`world::World` is the whole game state: one value, allocated once in the session heap and passed
as `mut w: world::World` (never read-only: read-only structs are copied). It holds `fs: Fs` and
`io: Io` itself, so code that has the world can read resources and log (a capability in a struct
works: `fs::size{ fs = &w.fs, ... }`).

```
struct World {
    fs: Fs, io: Io,
    heap: *mut heap::Heap,          // session memory: objects, lists, strings
    rm: *res::Manager,               // the resource manager (module mounted by modload)
    mod_arena: *mut arena::Arena,    // module memory: parsed LYT/VIS/WOK/PTH, programs; reset on leaving
    clock: clock::Clock,             // world time (µs), calendar, pause
    objects: obj::Table,             // id → *mut Object, creation order, next ids
    module: u32, area: u32,          // the module's and its one area's object ids
    pc: u32,                         // the player's creature (keyboard control moves it)
    party: party::Party,             // members in the area (leader first), NPC slots, the purse
    target: u32, hover: u32,         // the HUD's selected and hovered objects (it picks them)
    repute: [32][32]u8,              // repute.2da standings; world::standing{ w, from, toward }
    paths: ?pth::Graph,              // the area's path points (module memory)
    queue: events::Queue,            // timed events (DelayCommand, AssignCommand, SignalEvent, ...)
    scripts: scripts::Cache,         // programs by resref, for this module
    values: values::Store,           // engine values (effect, event, location, talent) by handle
    walk: walkmap::Map,              // the area's walkable surface
    tables: world::Tables,           // the 2DAs the engine itself reads (appearance, genericdoors, ...)
    globals: world::Globals,         // globalcat.2da: global booleans, numbers, strings, locations
    out: outbox::Outbox,             // server → client notes (sounds, music, fades, conversations, ...)
    transition: ?world::Transition,  // a pending module change (module, waypoint, movies)
    rng: world::Rng,                 // MSVC rand(), seeded; deterministic headless
    stats: world::Stats,             // routine call counts, unimplemented calls, faults
    log: elog::Log,                  // which logs are on (scripts, routines, events, actions)
    rules: *mut rules::Tables, dice: rules::Rng, fx_ids: rules::EffectIds, rev: rules::Events
    gip: save::Store                 // GAMEINPROGRESS (lib/save)
    // HOOK(dialog): conversation: dlg::State
    // HOOK(party): party table
}
```

The `nwvm::Vm` is **not** in the World: routines get both (`mut w`, `mut vm`), and a Vm inside the
World would alias. `game/main` owns the Vm and binds the engine once (Scripts, below).

**Memory.** Three lifetimes: the session heap (`heap::Heap`, malloc: the World, objects, their
lists and strings, freed one by one); the module arena (reset when the module is left: parsed
layout, walkmeshes, path points, NCS programs, template bytes); the frame (a scratch arena reset
every frame, for temporary text). Everything an object owns is freed by `obj::free_object`, so a
destroyed object gives its memory back; `w.heap.live` must return to the same number after a
module is left (as fmtcheck checks for res).

## Objects

### Ids

Object ids are the engine's 32-bit ids, as scripts and saves see them (objects.md, Ids):
`obj::INVALID = 0x7F000000`; ordinary objects count up from 1 (*ours*: the original starts at 0;
0 stays unused so a zeroed field is never a live object); player characters count down from
`0x7FFFFFFF`; a save restores its ids and moves the counters past them. The module and its area
are objects too (ids, tag, locals, scripts), so `GetModule`, `GetArea`, `SignalEvent` to them and
their locals work like any other object's.

`obj::Table` maps id → `*mut obj::Object` (std map) and keeps every live object in creation
order (`all`): tag searches, `GetFirstObjectInArea` and the AI master walk it. Objects are
allocated one by one in the heap, so a `*mut Object` stays valid until the object is destroyed;
code that holds one across a script run must look the id up again (scripts destroy things).

```
let o = world::object{ w = &w, id } ifnull { ... }              // ?*mut obj::Object
let c = obj::creature{ o } ifnull { ... }                        // ?*mut obj::Creature (kind check)
let found = world::object_by_tag{ w = &w, tag, nth = 0 }        // ci compare, creation order
```

**Destruction is deferred**: `DestroyObject` (and the engine) mark `o.destroyed` and queue the id;
`world::sweep` removes them at the end of the server frame (events for them are dropped, their
situations freed). A marked object is invalid to `world::object` from the moment it is marked.

### Kinds

`obj::Kind` (`module`, `area`, `creature`, `item`, `trigger`, `placeable`, `door`, `aoe`,
`waypoint`, `encounter`, `store`, `sound`); `obj::object_type{ kind }` gives the script's
`OBJECT_TYPE_*` (creature 1, item 2, trigger 4, door 8, AoE 16, waypoint 32, placeable 64,
store 128, encounter 256, sound 512).

### The common header

Everything every kind has, as `CSWSObject` has it (objects.md, CSWSObject members):

```
struct Object {
    id: u32, kind: Kind,
    tag: []u8,                       // lower-cased as SetTag does; heap
    template: resref::ResRef,        // the blueprint it came from
    name: Name,                      // { strref, text }: LocName/FirstName
    area: u32,
    position: math::Vec3,
    orientation: math::Vec3,         // unit facing vector, z = 0; GetFacing = atan2(y, x)
    scripts: Scripts,                // [SLOT_COUNT]resref::ResRef by obj::Slot
    locals: Locals,                  // KOTOR's SWVarTable: 96 booleans, 8 numbers
    effects: ...                     // HOOK(rules): the effect list lives in rules::Creature for creatures
    actions: actions::Queue,         // the action queue (below)
    commandable: bool,
    hp: i32, hp_max: i32, hp_temp: i32, plot: bool, min_one_hp: bool,
    animation: u32,                  // the internal animation id (10000 = stand) the client plays
    anim_speed: f32,
    dirty: u32,                      // DIRTY_ANIMATION 1, DIRTY_POSITION 2, DIRTY_ORIENTATION 4 (for the scene)
    ai_level: i32,                   // 0..4, -1 not updated (waypoints, sounds)
    conversation: resref::ResRef,
    faction: u32,
    ctx: Context,                    // what event scripts ask about: entering, user event number, last opener, ...
    destroyed: bool,
    ext: Ext,                        // the kind's own data
}
union Ext { none, module{ m: *mut Module }, area{ a: *mut Area }, creature{ c: *mut Creature },
            item{ i: *mut Item }, trigger{ t: *mut Trigger }, placeable{ p: *mut Placeable },
            door{ d: *mut Door }, waypoint{ w: *mut Waypoint }, sound{ s: *mut Sound },
            encounter{ e: *mut Encounter }, store{ s: *mut Store }, aoe{ a: *mut Aoe } }
```

- **Facing.** The header keeps the facing vector, as the original does. GIT creatures, waypoints
  and items give it (`XOrientation`, `YOrientation`); doors and placeables give `Bearing` (radians
  counter-clockwise from +Y), stored as the vector `(-sin b, cos b)`. Models face +Y, so the scene
  turns a model by `atan2(y, x) - pi/2` about Z, which is `b` for doors and placeables.
- **Script slots** are one enum over every kind's events (`obj::Slot`: `heartbeat`, `on_notice`,
  `spell_at`, `attacked`, `damaged`, `disturbed`, `end_round`, `dialogue`, `spawn`, `rested`,
  `death`, `user_defined`, `blocked`, `end_dialogue`, `on_open`, `on_closed`, `on_lock`,
  `on_unlock`, `on_used`, `on_click`, `on_fail_to_open`, `on_enter`, `on_exit`, `on_trap`,
  `on_disarm`, `on_inv_disturbed`, `on_melee_attacked`, the module's 15, ...), each a resref
  (empty: none). Loaders fill the ones their kind has from the GFF labels in objects.md's table.
- **Context** holds what the original records on the object before running a slot, which
  routines read back: `entering`, `exiting` (area, trigger), `user_event` (GetUserDefinedEventNumber),
  `last_opened_by`, `last_closed_by`, `last_used_by`, `last_perceived` (+ seen/heard/vanished),
  `last_attacker`, `last_damager`, `last_speaker`, `run_script_var`. Add fields as routines need
  them; one owner sets each (the event delivery code), routines only read.

Kind data, in `lib/engine/object.ctx` (fields are added by whoever needs them, with a comment
naming the GFF label or the RE address):

| Kind | Holds |
|---|---|
| `Creature` | appearance row, gender, race, subrace, body/texture variation, portrait, soundset, walk/run rates and sizes (creaturespeed, appearance PERSPACE...), equipped item ids by slot, inventory ids, faction, perception range and lists, spawn-fired flag, heartbeat and perception timers, movement state and path, combat state; `stats: rules::Creature` (HOOK(rules)) |
| `Door` | genericdoors row, open state (closed, open1, open2), locked, lockable, key tag, DCs, linked-to module/tag/flags, transition destination, static, the three DWKs placed |
| `Placeable` | placeables row, open/on state, useable, has inventory, inventory ids, static, locked..., the PWK placed |
| `Trigger` | polygon (area space), type (generic, transition, trap), linked-to, the objects inside |
| `Waypoint` | map note (has, enabled, text) |
| `Sound` | the UTS fields (sounds, interval, volume, positional, looping, active) |
| `Item` | base item, model variation, stack, charges, possessor; `rules::Item` (HOOK(rules)) |
| `Module`, `Area` | IFO and ARE fields that change at run time: entry point, time settings, music and ambient rows, camera style, restrict mode, stealth XP, transition-pending token |

### Making objects

`tmpl` reads blueprints into objects: `tmpl::creature{ &w, doc: *gff::Doc, s: u32 }` and the same
for each kind, from a struct (the UTC root for a template, a full GIT or save struct otherwise),
so one reader serves templates, `UseTemplates = 0` GITs and saved games. `world::spawn{ &w,
kind, template, position, orientation } -> !u32` loads the template through res and registers the
object (used by GIT loading and `CreateObject`); GIT per-instance fields (door `Tag`, `LinkedTo`,
trigger geometry, ...) are applied after the template. A missing template is logged and skipped,
never fatal. Order of GIT lists as modules.md says (creatures, items, doors, triggers, encounters,
waypoints, sounds, placeables, stores). Creatures join AI level 0, become 1 when the PC enters.

## Time

`clock::Clock` is the world timer (gameloop.md 1.6): `now_us: u64` advanced by `dt × speed`
unless paused, the calendar origin (year, month, day, hour from the IFO), `min_per_hour`
(`Mod_MinPerHour`, 2 in KOTOR), and `world_ms` = `now_us / 1000`. Event times are absolute world
milliseconds (*ours*; the original keeps (day, ms) pairs, which saves convert to and from).
Pause (gameloop.md 6) freezes it: `clock::set_pause{ c = &w.clock, bit, on }` with
`PAUSE_PLAYER`, `PAUSE_MENU`, `PAUSE_ENGINE`; any bit set stops the clock, but `world::tick` still
runs, so zero-delay events go through (6.2). The GUI and camera use real time. The delta every system reads
is `clock.dt` (seconds, 0 while paused), clamped to 0.25 s (*ours*: the original never clamps).

## The frame

`game/main` runs one loop for live and headless play; the order follows the original's client
frame then server frame (gameloop.md 1.2, 1.3), so input in frame N acts in frame N and shows in
N+1:

| # | Step | Where |
|---|---|---|
| 1 | events: SDL (or the headless script) → `gui::handle_event` → game input (held keys, mouse look) | game/main, HOOK(gui) |
| 2 | front end, when no module runs: `frontend::step` → start a module, load, quit | HOOK(frontend) |
| 3 | advance the clock (unless paused or loading) | `clock::advance` |
| 4 | player control: keyboard → the leader moves on the walkmesh, triggers crossed (movement.md 1.2, 1.3) | `ctl::update` |
| 5 | **server frame**: deliver due events; AI master: per object by level 4 → 0, `ai::update` (creature: OnSpawn once, OnHeartbeat, perception, combat HOOK(rules), effects HOOK(rules), `actions::run`; doors/placeables/triggers: heartbeat, actions); module and area heartbeats; sweep destroyed objects | `world::tick` |
| 6 | a pending transition: leave, load the next module, place the party | `world::transition`, `modload` |
| 7 | dialogue and GUI that react to the world | HOOK(dialog), HOOK(gui) |
| 8 | the outbox: sounds, music, fades, movies, barks, feedback to the presentation | `ambience::take`, HOOK(gui) |
| 9 | scene sync: visuals for new/destroyed objects, transforms, animation changes; advance animations by dt | `scene::sync` |
| 10 | camera: chase camera from the leader (movement.md 2.3) | `cam::update` |
| 11 | audio: listener at the camera, music/ambient/sound objects, `audio::update` | `ambience::update` |
| 12 | render: `scene::draw` (rooms visible per VIS, objects, lights) into the frame, then `gui::draw`, `gpu::submit`, present or screenshot | game/main |

`world::tick{ &w, &vm, engine }` does step 5 in the original's order (gameloop.md 2.2): events due
at the frame's world time are delivered first (an event queued during the frame with no delay is
delivered in the same frame, at the next delivery point), then each AI level's objects. There is
no 10 ms budget yet (*ours*: KOTOR's object counts let every object update every frame); the
level order, the "a due event ends the level" rule and the delivery points are kept.

## Scripts

### Running one

```
let engine = routines::call{ w = world_ptr, _ }          // once, in game/main: nwvm::Engine
_ = scripts::run_slot{ w = world_ptr, &vm, engine, object = id, slot = obj::Slot::heartbeat }
_ = scripts::run{ w, &vm, engine, name = "k_pend_area01", self = area_id }   // -> ?i32
```

- `scripts::Cache` loads each NCS once per module (`nwvm::load` into the module arena), keyed by
  resref; a missing script is remembered as missing and is "no script" (gff-templates.md: a few
  hooks name scripts that don't exist).
- A run is `nwvm::run{ &vm, program, self, engine }`. Faults are logged as one line
  (`nwvm::describe`) and counted in `w.stats.faults`; the game goes on, as the original does.
- **The bind.** `nwvm::Engine` is `&fn{ mut vm, call } -> Reply`, bound once to the world:
  `routines::call{ w = world_ptr, _ }` with `world_ptr: *mut World` (a raw pointer, so passing
  `w = world_ptr` beside the bind isn't an exclusivity error). Every function that may run a script
  takes `mut w: world::World, mut vm: nwvm::Vm, engine: nwvm::Engine` (a `&fn` can't be a struct
  field). ExecuteScript inside a routine has no engine at hand and binds a new one for its nested
  run (`let wp: *mut World = &w`, `routines::call{ w = wp, _ }`): one small leaked bind record per
  call (friction/engine.md).
- **OBJECT_SELF** is the object whose slot runs (the area for area scripts, the module for module
  scripts, the target of an AssignCommand, the owner of a DelayCommand).

### Events

`events::Queue` is a list sorted by due time (world ms), FIFO among equal times (gameloop.md 4.1):

```
struct Event { due: u64, caller: u32, target: u32, payload: Payload }
union Payload {
    situation{ s: nwvm::Situation },                 // 1 TIMED_EVENT: DelayCommand, AssignCommand
    script{ e: values::ScriptEvent },                // 10 SIGNAL_EVENT: SignalEvent, the engine's own
    destroy, open, close, lock, unlock, ...          // engine events (objects.md, Event ids)
}
```

`events::post{ &w, delay_ms, caller, target, payload }`. Delivery (`events::deliver`) by target:
a situation runs with `nwvm::resume` as the target, then is freed; a script event sets the
target's `ctx` (entering object, user event number, ...) and runs the slot its type names
(objects.md, "How a script slot gets run"; the module and area handlers of gameloop.md 4.4); an
event for a vanished id is dropped and its payload freed. The engine's own signals go through the
same queue: an object entering the area posts `script{ OBJECT_ENTER }` to the area, so the order
of scripts on arrival is the original's (gameloop.md 5.5).

### Engine values

`values::Store` owns every effect, event, location and talent a script makes; scripts hold
handles (script.md, Engine values). Two spaces (*ours*):

- **transient** handles (bit 31 clear, from 1; 0 is each type's default value): made during a run,
  all forgotten when the outermost run ends (`values::end_run`);
- **kept** handles (bit 31 set): a copy that lives until released. A situation taken by
  DelayCommand/AssignCommand/ActionDoCommand has each engine cell replaced by a kept copy of its own
  (`values::keep_cells{ &w.values, situation }`), released when the situation is freed
  (`values::release_cells`). A global location or an applied effect is copied into its owner's own
  state, not kept by handle.

Values: `ScriptEvent { type, ints, floats, strings, objects }` (EventUserDefined, EventSpellCastAt,
...), `Location { position, facing, area }`, `Talent { type, id, ... }`, and effects
(`rules::Effect` once lib/rules is in; HOOK(rules)). `Call::equal` compares by the rules in
script.md.

### Actions

`actions::Queue` is the object's action list (actions.md 1): nodes `Action { kind: actions::Kind,
group: u16, params: [13]Param, started: u64, first: bool }` where `union Param { none, int, float,
object, string, situation }`, `Kind` the original's internal ids (MOVETOPOINT 1, PLAYANIMATION 6,
OPENDOOR 0x14, WAIT 0x1e, DOCOMMAND 0x25, USEOBJECT 0x28, ...). `actions::add{ &w, id, action }`
appends (dropped when the object isn't commandable), `actions::clear_all{ &w, id }` is
ClearAllActions. `actions::run{ &w, &vm, engine, id }` runs the head as RunActions does
(actions.md 1.3): a handler returns `running` (stays at the head, stop for this frame), `retry`
(to the tail), `done` or `failed` (removed, next one in the same frame up to a small count; a move
ends the frame's run). One function per action kind in `lib/engine/actions*.ctx`; a new action is
a new `Kind` value, a handler, and a line in `actions::step`'s chain.

## Routines: many hands, one dispatcher

The 772 routines are numbered as `nwscript.nss` declares them (`nwscript::ROUTINES`, constants
`nwscript::GetObjectByTag`). They live in `lib/engine/routines/`, **one file per category, one
namespace per file**, each file owned by one agent at a time:

| File | Namespace | Routines (by nwscript-routines.tsv's ranking) |
|---|---|---|
| `dispatch.ctx` | `routines` | the Engine function, the dispatch chain, counts; nobody else edits it except to add a category line |
| `core.ctx` | `rt_core` | Random, d2..d100, Print*, IntToString, FloatToString, StringToInt, string functions, math |
| `vars.ctx` | `rt_vars` | Get/SetLocalBoolean/Number, Get/SetGlobalBoolean/Number/String/Location |
| `objects.ctx` | `rt_obj` | GetObjectByTag, GetWaypointByTag, GetIsObjectValid, GetTag, GetPosition, GetFacing, GetArea, GetModule, GetDistance*, GetNearest*, GetFirst/NextObjectInArea/Shape, GetObjectType, GetName, CreateObject, DestroyObject, Location functions |
| `commands.ctx` | `rt_cmd` | AssignCommand, DelayCommand, ExecuteScript, SignalEvent, EventUserDefined, GetUserDefinedEventNumber, GetEnteringObject, GetExitingObject, GetLastUsedBy, ..., SetCommandable, GetCommandable |
| `actions.ctx` | `rt_act` | Action* that queue actions, ClearAllActions, ActionDoCommand, ActionWait, ActionPlayAnimation, PlayAnimation, SetFacing, JumpTo* |
| `party.ctx` | `rt_party` | GetFirstPC, GetPCSpeaker, GetIsPC, party membership and leader, solo mode |
| `creature.ctx` | `rt_crea` | hit points, hit dice, class, race, gender, abilities, skills, feats, factions (HOOK(rules)) |
| `effects.ctx` | `rt_fx` | Effect*, ApplyEffect*, GetFirst/NextEffect (HOOK(rules)) |
| `items.ctx` | `rt_item` | CreateItemOnObject, GetItemInSlot, inventory, gold |
| `dialog.ctx` | `rt_dlg` | ActionStartConversation, Action/Pause/ResumeConversation, GetIsInConversation, BarkString (HOOK(dialog)) |
| `doors.ctx` | `rt_door` | locks, door and placeable state, SetLocked, GetLocked, GetIsOpen |
| `presentation.ctx` | `rt_pres` | SetGlobalFadeIn/Out, PlayMovie, music, PlaySound, SoundObject*, SetDialogPlaceableCamera, NoClicksFor, AurPostString (through the outbox) |
| `time.ctx` | `rt_time` | GetTimeHour..., SetTime, calendar |
| `module.ctx` | `rt_mod` | StartNewModule, GetLoadFromSaveGame, journal, map, SetReturnStrref, XP |
| `misc.ctx` | `rt_misc` | map pins, area unescapable and stealth XP, encounters, persistent-zone residents, custom tokens (`w.tokens`, tokens.ctx), reputation and factions, plot XP, item hand-overs, lock/unlock, GetCurrentAction, the event-script queries, CutsceneAttack and fake spells, OpenStore/ShowUpgradeScreen notes |
| (more) | `rt_*` | combat, talents, AI styles, minigames, ... added as files by their owners |

**A category file:**

```
namespace rt_vars {
    // The routines this file implements, in its chain below.
    fn run { mut w: world::World, mut vm: nwvm::Vm, routine: u16, argc: u8 } -> !bool {
        if routine == nwscript::GetGlobalNumber { try get_global_number{ &w, &vm, argc } }
        else if routine == nwscript::SetGlobalNumber { try set_global_number{ &w, &vm, argc } }
        else { return false }
        return true
    }

    // int GetGlobalNumber(string sIdentifier)
    fn get_global_number { mut w: world::World, mut vm: nwvm::Vm, argc: u8 } -> ! {
        let name = try nwarg::string{ &vm, routine = nwscript::GetGlobalNumber, argc, i = 0 }
        try nwvm::push_int{ &vm, v = world::global_number{ w = &w, name } }
    }
}
```

and `routines::dispatch` asks each category in turn (`if try rt_vars::run{ &w, &vm, routine,
argc } { return }`), and when none takes it, counts it in `w.stats.missing[routine]` and lets
`nwstub::fallback` pop the arguments and push a zero result, so a script goes on. A function with
an inferred error set can't be a function value, so this is a chain of direct calls, not a table;
an `if` chain (or an integer `match routine { nwscript::GetHitDice => {...} else => { return false } }`)
costs nothing next to a script's run. **The dispatcher checks every call's stack balance**: the
arguments the script passed must be gone and the result pushed, as the prototype says; a handler
that slips is reported once as `BUG: routine X left N stack cells, wanted M` (one such slip,
PlayRumblePattern's missing int, made a later DelayCommand fault in another script).

**Adding a routine** (any agent):

1. Find its category above (or make a new `rt_*.ctx` file and add one line to `routines::dispatch`).
2. Write the handler: pop arguments **in declaration order** with `nwarg::*` (fills defaults for
   old scripts that pass fewer), do the work through `world::`/`obj::`/`actions::`/`events::`,
   push the result. Fail (`try`) only for a VM error; a bad object id is not a failure: return
   the nwscript.nss default (0, "", OBJECT_INVALID).
3. Add its line to the category's `run` chain.
4. Run `python kotor/tools/py/routine_registry.py`: it reads every chain and writes
   `kotor/docs/design/routines.tsv` (id, name, file, uses), failing on an id claimed twice.
5. Check it on the scripts that use it: `kotor --module M --headless --frames N --log routines`
   prints each call with its arguments and result; the end-of-run report lists unimplemented
   routines by calls made (`--report routines`).

Handlers never run scripts directly except ExecuteScript; anything that should run "later" posts
an event or queues an action, as the original does.

## Walking

`walkmap::Map` is the area's walkable surface: one entry per LYT room (in LYT order, as
`GetRoomAtPoint` tries them) with its WOK (`bwm::Walkmesh`, area space), plus each door's and
placeable's placed walkmeshes (DWK for the door's state, PWK). Queries (movement.md 3.5):
`walkmap::floor{ map, x, y, z } -> ?Floor { room, face, z }` (walkable faces only, nearest below
`z + step`), `walkmap::height`, `walkmap::room_at`, and `walkmap::test_line{ map, from, to,
radius } -> LineResult` (blocked by a non-walkable face, the edge of the walkmesh, or a closed
door's or a placeable's walkmesh; the edge it hit, for sliding). Creature-against-creature tests
use the creatures' PERSPACE circles.

**Player control** (`ctl`, movement.md 1.2): the forward and strafe axes (W/S, Z/C, and arrows
*ours*), rotated by the camera's yaw, integrated with the original's velocity law, the leader
turning at the camerastyle rates, moved by `ctl::move_leader` with up to six slide attempts; the
leader's new position goes straight into the world object (as the original writes the server
creature) with the trigger bookkeeping (`movement::cross_volumes`). The leader's animation is set
from its speed (10000 stand, 10002 walk, 10004 run). **NPC movement** is server side: MOVETOPOINT
and its relatives in `movement`, with the acceleration and braking of movement.md 3.3, along a
path from `paths::plan` (the straight walk if clear, else A* over the area's PTH points, string
pulled, else the farthest clear point; movement.md 4). FOLLOW, FOLLOWLEADER and RANDOMWALK push a
move, a wait and themselves in front, as actions.md 3.3 has it.

**Perception** (`perception`, gameloop.md 2.4): each creature checks the party every update and
everyone in its area every 4 s (0.2 s in combat); seen = within ranges.2da's sight range with a
clear line at eye height through the rooms' walkmeshes (LineOfSight materials), heard = within
the hearing range. Changes post script event 1 (PERCEPTION) with what changed in `ints[0]`
(1 seen, 2 heard, 4 vanished, 8 inaudible); the object's `ctx` keeps them for
GetLastPerception*. Stealth and the rules' checks are HOOK(rules).

## The scene

`scene::Scene` mirrors the world into draws; nothing in it is game state (a save never needs it,
and it can be rebuilt from the world at any time):

- **Rooms**: the LYT's room models, each with its pose (animloop1..3 when the model has them) and
  lights; the VIS table. Each frame the camera's room is the room whose walkmesh is under the
  leader (else the camera); rooms not visible from it per VIS are skipped (a room without a VIS
  entry sees everything, vis.md). Room lights go into the frame for dynamic objects.
- **Visuals**, one per object that has a model, keyed by object id (`scene.visuals`): created when
  a new id appears in `w.objects.all`, dropped when it's gone. A visual is a set of parts, each a
  model with its own animation player and pose, attached to a parent part's hook:
  - creature (models-usage.md, Creatures): `appearance.2da` MODELTYPE B → body `model<L>` +
    texture `tex<L>NN` + head (`heads.2da` row from NORMALHEAD) at `headhook`; F → `modela` or
    `race`; S/L → `race` (retextured with `racetex`); the right-hand weapon (`baseitems.2da`
    itemclass + `_` + model variation) at `rhand`, the left at `lhand`; `envmap` from appearance;
  - placeable: `placeables.2da` modelname; door: `genericdoors.2da` modelname, animated
    `opening1`/`opened1`/`closing1`/`closed` from the door's open state;
  - waypoints, triggers and sounds have none.
- **Animation**: the object's `animation` (an internal id, objects.md `+0xd4`) is mapped to model
  animation names by `animname` (10000 → `pause1`, 10002 → `walk`, 10004 → `run`, 10006 → `dead`,
  10038 → `tlknorm`, ...; *ours*, the client's own mapping in `0x0069f650` hasn't been read), with
  the `c` prefix for S/L creatures (`cpause1`, `cwalk`) and the looping flag from animations.2da.
  The head part plays its own (`pause1` while the body idles, `talk` while talking).
- Each frame `scene::sync{ &scene, w, dt }` updates visuals (transform from position and facing,
  animation changes, advance players by `clock.dt`), and `scene::draw{ &scene, &frame, view }`
  adds rooms, objects (`mdl_render::add_draws`), lights and the leader's planar shadow.
- **Camera** (`cam`, movement.md 2.3): the chase camera from camerastyle.2da's row for the area's
  CameraStyle (DEFAULT: distance 3.2, pitch 83, height 0.45, FOV 55), the look-at point the
  leader's position + head height + CameraHeightOffset, yaw from A/D (the rate integrator) and
  mouse look, collision against the walkmesh by four rays. Dialogue and combat cameras are their
  leads' (HOOK(dialog), HOOK(rules)).
- **Sound** (`ambience`): area music (`ambientmusic.2da` from the area's MusicDay, repeated after
  MusicDelay ms), the ambient bed (`ambientsound.2da`), placed sound objects (audio.md, "Placed
  sound objects"), and the outbox's sound notes; the listener is the camera.

## The outbox: server to client

Routines and world code never call the scene, GUI, audio or dialogue directly: they append a
note to `w.out` (`outbox::Note`), which the game loop drains each frame (step 8) to whoever
presents it. This is the original's server → client message ring, and it keeps lib/engine free
of the presentation libraries.

```
union Note {
    play_sound{ name: resref::ResRef, object: u32, position: math::Vec3, positional: bool },
    sound_object{ id: u32, play: bool },
    music{ kind: Music, row: i32, play: bool },
    fade{ out: bool, wait: f32, length: f32, color: math::Vec3 },
    movie{ name: resref::ResRef },
    bark{ speaker: u32, strref: u32, text: []u8 },
    feedback{ strref: u32, text: []u8 },
    camera_shake{ ... }, no_clicks{ seconds: f32 }, ...
}
```

Text in notes is copied into the outbox's own buffer (reset when drained). Add a variant when a
routine needs a new kind of client effect.

## Plugging in

The loop in `game/play.ctx`, with the hooks the leads agreed (each lead adds its own lines, in a
marked block):

```
front end (lib/frontend) until New Game        -> modload::enter
each frame:
  events: ingame::handle_event (HUD lead) / dlgview input when it wants it (dialogue lead) / ctl keys
  clock::advance; ctl::update; world::tick
  a pending transition: modload::take_transition, scene and ambience rebuilt
  dlg::update (dialogue pump), ingame::update (HUD)
  outbox notes -> ambience::take, ingame::take, ...
  scene::sync; cam::update; dlgview::apply_camera; dlgview::update; ambience::update; audio
  render: scene::draw, ingame::draw / gui::draw, gpu::submit, screenshots, present
```

- **GUI and front end** (lib/gui, lib/frontend; docs/design/gui.md). Without `--module`,
  `play::front_end` runs `frontend::handle_event`/`step`/`draw` until New Game (`end_m01aa`;
  Load Game also starts a new game until saves exist), then `frontend::leave`. In game, the
  in-game UI lead's `ingame` (lib/hud, lib/ingame) owns its `gui::Gui` (HUD, panels) and
  `gui::handle_event`'s `true` means the event isn't a game key or a world click. `gui::is_modal_open` pauses the world. In-game panels
  are poll-style (`gui::clicked`) so engine code dispatches with plain calls. The GUI never reads
  SDL or the clock itself: headless runs feed it scripted events and a fixed dt. The HUD reads the
  world (`w`) read-only for portraits, health and the party.
- **Rules and combat** (lib/rules; lib/engine/fight.ctx, namespace `fight`): the world holds
  `rules: *rules::Tables`, `dice: rules::Rng`, `fx_ids: rules::EffectIds` and `rev:
  rules::Events`. Every creature has a heap `fighter: ?*mut fight::Fighter` (the
  `rules::Creature`, its combat round, combat timer, dying timer); every item a `rules:
  ?*mut rules::Item`. `tmpl::read` calls `fight::read_creature` on any struct with a ClassList
  (UTC, saved creature, player entry; plus the saved EffectList) and `fight::equip_loaded` after
  the items (the worn ones equipped "while loading", max HP from the rules); a default player
  gets `fight::default_stats`. Current HP stay on the object header. Every rules call fills
  `w.rev`; `fight::drain{ &w, id }` turns its events into the world: HP, OnDamaged, the death
  effect and `fight::died` (OnDeath, die/dead animations, kill XP, destroy after the appearance's
  delay; a party member only goes down and gets up when no enemy is in combat), crowd control.
  Effects from scripts go through `fight::apply_group` (routines/effects.ctx).
  ATTACKOBJECT (`fight::attack_object`) walks into reach and starts a 3 s round
  (`fight::start_round`): all attacks are resolved by `rules::resolve_attack` at the start and
  land at their hit times (combatanimations.2da hit1..3; weapondischarge.2da shots for ranged)
  with OnAttacked, the DAMAGE effects (`rules::make_damage_effects`), the other effects and the
  defender's reaction animation; OnEndRound at the end (the AI's next move); the player's own
  creature attacks on while its target lives. Doors and placeables are targets too (an AC 10
  stand-in defender; bashed doors open, placeables die). CASTSPELL (`fight::cast_spell`):
  approach to the power's range, `rules::begin_cast`, conjure and cast animations for the
  spells.2da times, the impact script as the caster with `ctx.spell_*` set, the catch time, then
  OnEndRound. Combat animations are animations.2da rows (`animname::ROW_BASE + row`; the scene
  plays the row's name). The combat camera is camerastyle row 8 while the leader is in combat.
- **Dialogue** (lib/dialog: `dlg`, `dlgview`, routines `rt_dlg`; agreed with the dialogue lead):
  DIALOGOBJECT posts script event 7 (DIALOGUE) to the target with the resref; `events` calls
  `dlg::note_event` before the slot runs, and an empty OnDialogue runs `k_hen_dialogue01`, which
  calls BeginConversation. The state is `w.conversation: dlg::State`; `dlg::update` pumps it after
  the transition step; `dlgview` takes input while it wants it, overrides the camera after
  `cam::update` (shots), and drives VO, lip sync and animations after `scene::sync`. Dialogue
  animations (dialoganimations.2da ids) are looked up by `animname::name_in`.
- **Saves** (lib/save, namespace `save`): `w.gip: save::Store` is GAMEINPROGRESS: in memory,
  written to `<saves>/gameinprogress.sav` (our saves directory, `--saves`, default
  kotor/out/saves; never the install's) when a module is mounted from it. Leaving a module
  (`modload::leave`) puts `<module>.sav` in it (`save::save_module_state`: the IFO with the
  calendar, counters, locals, the event queue as VM situations and Mod_PlayerList; the area's GIT
  with every object whole, ObjectIds, locals, action queues, items, rules state; the ARE) and the
  companions as AVAILNPC<n>.utc (`save::keep_party`). Entering a module that has one mounts it
  and reads the saved IFO/GIT (`UseTemplates` 0: no blueprints, no OnEnter for its creatures),
  then `save::restore_party` brings the members back next to the player. `save::save_game{ &w,
  slot, folder_name, save_name, screen }` writes `%06d - <name>/` (SAVEGAME.sav, GLOBALVARS.res,
  PARTYTABLE.res, savenfo.res, Screen.tga; 0 QUICKSAVE, 1 AUTOSAVE, 2+ manual);
  `save::load_game{ &w, &vm, engine, folder }` replaces the game in progress, reads globals and
  the party table, and enters LASTMODULE with `w.restoring` (the player and the companions where
  the save says). `save::find_save` looks in our directory, then the install's Saves/. Play:
  F4 quick save, F5 quick load, the front end's Load Game; headless `save NAME`, `load FOLDER`.
  A new game clears the store; character creation hands its player over with
  `modload::set_player_blueprint{ &w, bytes }` (UTC GFF bytes).
- **Minigames** take over the frame between steps 4 and 9 (their own scene and input) while the
  world's clock keeps running or not, as they need.

## Headless and logs

`kotor [--module end_m01aa] [--game DIR] [--headless] [--no-render] [--frames N] [--dt S]
[--input FILE] [--screenshot-at FRAME:PATH]... [--log scripts,routines,events,actions,objects]
[--report routines] [--seed N] [--size WxH]` (no `--module`: the front end first):

- `--headless`: a hidden window (the GL backend renders the same pixels offscreen), a fixed time
  step (`--dt`, default 1/30 s), the rng seeded (`--seed`, default 1), so a run is reproducible.
- `--input FILE`: one command per line, applied at the start of that frame: `FRAME down KEY` /
  `FRAME up KEY` (a letter, `up`, `down`, `left`, `right`, `space`, `escape`), and for tests
  `FRAME warp TAG` (the leader 1.5 m in front of the object), `FRAME use TAG` (the leader's default
  action on it), `FRAME attack TAG` (the leader attacks the nearest live one), `FRAME save NAME`,
  `FRAME load FOLDER`, `FRAME newgame` (the front end's New Game). Keys: W/S or arrows forward and back,
  Z/C strafe, A/D or arrows turn the camera, R or Space the default action (the nearest door,
  useable placeable or creature with a conversation in front, within 3 m).
- `--screenshot-at F:PATH` (repeatable) reads the screen after frame F's render and writes a PNG.
- Logs go to stdout, one line each, prefixed with the frame and world time: `[12 0.400] script
  k_pend_area01 self=2 -> 0`, `[12 0.400] routine GetObjectByTag("end_trask", 0) -> 7`.

## Decisions (ours) and open questions

- Ids from 1, not 0; event times as world ms; no AI time budget; delta clamped to 0.25 s; the
  internal animation id → name table; arrows also move the leader.
- A door's `trans` plane is never drawn; PLAYANIMATION's fire-and-forget length is 1.5 s until
  the server reads model animation lengths; perception has no stealth yet; the player faces its
  input from standstill at once; camera collision is one ray against the walkmeshes.
- Combat (ours where combat.md leaves it open): the attack animation by stance (the digit of the
  names: 0 creature, 1 stun baton, 2 one melee weapon, 3 two-handed, 4 two weapons, 5 pistol,
  6 two pistols, 7 rifle/heavy, 8 unarmed; duel `c` sets when both fight in melee, `g` sets
  otherwise, `b` sets for ranged); the round is not paused by the animation (the impacts run on
  the round timer); no master/slave pairing yet; the leader re-attacks its live target each
  round; downed party members get up with 1 HP when no enemy is in combat; cast animations
  hand/self → castout1, dark → castout2, up → castout3, throw → throwsab; spell ranges from the
  range letter's ranges.2da row; GetObjectByTag("") is OBJECT_INVALID.
- Saves (ours): the effects of a saved creature are restored into its rules list without being
  applied again; equipped and innate effects are not saved (equip while loading remakes them);
  companions arrive 1.5 m behind the player, one to each side.
- Open: the client's animation id → name mapping (`0x0069f650`), the exact TestWalkLine sliding
  and creature collision, the grid planner, door DWK use while opening, the 10 ms budget if a big
  module needs it, body bags, the death camera and game over, attack pairing (GetCanEngage).
