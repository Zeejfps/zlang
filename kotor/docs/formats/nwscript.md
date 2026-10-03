# NWScript: the engine routines, types and constants

NWScript is the C-like language KOTOR's scripts are written in. Scripts are compiled to NCS
bytecode ([ncs.md](ncs.md)); the bytecode calls into the engine with `ACTION routine argc`,
where `routine` is an index into a table of engine routines. That table, the language's types
and the predefined constants are declared in one source file the game ships: `nwscript.nss`.

## Where it lives

`nwscript.nss` is resource `nwscript`, type `nss` (2009), in **`data/scripts.bif`**. It is the
only copy: `Override/` is empty in a stock install and no module carries one. It is 5172 lines
of plain ASCII text with CRLF line ends, in this order: `#define`s naming the engine structures, the
constants, then one prototype per engine routine, each preceded by a comment.

Our extraction: `kotor/tools/py/nwscript.py` (reads it through `kres`, so an Override copy would
win) writes

- [`nwscript-routines.tsv`](nwscript-routines.tsv): `index`, `return`, `name`, `params` (as
  declared, `type name=default`, whitespace normalised), `ncs_files` (unique (resref, content)
  NCS files calling it) and `ncs_sites` (call sites in those files);
- [`nwscript-constants.tsv`](nwscript-constants.tsv): `name`, `type`, `value` (references to
  other constants resolved: `PLAYER_CHAR_IS_PC = TRUE` is written as 1; float suffixes dropped).

Only names, types, defaults and values are extracted; the comments are not.

## Routines

**772 routines, indices 0..771**, numbered by the declaration order of the prototypes from 0.
Checked: BioWare's comment above each prototype starts with its number (`// 27: ...`), and all
772 agree with our declaration-order index. Index 0 is `Random`, 771 is `YavinHackCloseDoor`.
The executable agrees: its routine dispatch table has exactly 772 slots, all filled (see
[../re/nwscript-routines.md](../re/nwscript-routines.md) for routine number → handler).

| Returns | Count | | Parameter type | Count |
|---|---|---|---|---|
| void | 254 | | int | 451 |
| int | 236 | | object | 389 |
| object | 95 | | string | 83 |
| effect | 87 | | float | 81 |
| float | 48 | | location | 26 |
| string | 26 | | effect | 19 |
| vector | 11 | | vector | 16 |
| location | 6 | | talent | 7 |
| talent | 5 | | action | 3 |
| event | 4 | | event | 1 |

Parameters may have defaults (35 distinct ones): integer and float literals, strings (`""`,
`"World Entry"`), constants (`FALSE`, `TRUE`, `OBJECT_SELF`, `OBJECT_INVALID`,
`TALKVOLUME_TALK`, `OBJECT_TYPE_CREATURE`, ...) and one vector literal (`[0.0,0.0,0.0]`).
The compiler pushes defaults explicitly (see ncs.md, ACTION), so the engine only needs them for
the old scripts that pass fewer arguments.

One prototype spells its types oddly: `void SetAvailableNPCId(INT nNPC, OBJECT_ID oidNPC)`
(767). We read `INT` as `int` and `OBJECT_ID` as `object`.

The three routines that take an `action` are `AssignCommand` (6), `DelayCommand` (7) and
`ActionDoCommand` (294).

## Types and their stack representation

| Type | Cells | On the VM stack | Bytecode |
|---|---|---|---|
| `void` | 0 | nothing (return type only) | |
| `int` | 1 | signed 32-bit | `CONSTI`, `RSADDI`, type 0x03 |
| `float` | 1 | IEEE single | `CONSTF`, `RSADDF`, type 0x04 |
| `string` | 1 | reference to a string | `CONSTS`, `RSADDS`, type 0x05 |
| `object` | 1 | object id; constants `OBJECT_SELF` = 0, `OBJECT_INVALID` = 1 | `CONSTO`, `RSADDO`, type 0x06 |
| `vector` | 3 | x, y, z floats, z on top | no type byte: a 12-byte structure (`EQUALTT 12`, `DESTRUCT 12 k 4`) |
| `effect` | 1 | engine handle | type 0x10 (engine structure 0) |
| `event` | 1 | engine handle | type 0x11 (engine structure 1) |
| `location` | 1 | engine handle (position, facing, area live engine-side) | type 0x12 (engine structure 2) |
| `talent` | 1 | engine handle | type 0x13 (engine structure 3) |
| `action` | 0 | the VM's saved state from the last `STORE_STATE` | see ncs.md |

`location` being one cell is checked: the stack check in ncs.md counts every location argument
and result as one cell and agrees with all 8666 unique scripts. The engine-structure numbering
comes from `nwscript.nss` itself (`ENGINE_NUM_STRUCTURES 4`, `ENGINE_STRUCTURE_0..3` = effect,
event, location, talent).

`OBJECT_SELF` and `OBJECT_INVALID` are compiler built-ins, not declared in nwscript.nss (`TRUE`
and `FALSE` are, as int constants). User `struct`s exist only in scripts: on the stack they are
their fields in order, like a vector.

## Constants

**1490 constants**: 1478 `int`, 11 `float` (the four `DIRECTION_*`, `PI`, six `RADIUS_SIZE_*`)
and 1 `string` (`sLanguage = "nwscript"`). The compiler inlines them: a script's `TRUE` is
`CONSTI 1`, never a global. Largest groups by prefix:

| Prefix | Count | | Prefix | Count |
|---|---|---|---|---|
| `DISGUISE_TYPE_` | 305 | | `ANIMATION_` | 88 |
| `VFX_` | 118 | | `BASE_ITEM_` | 86 |
| `FEAT_` | 92 | | `AREA_TRANSITION_` | 72 |
| `EFFECT_TYPE_` | 70 | | `ITEM_PROPERTY_` | 59 |
| `FORCE_POWER_` | 52 | | `POLYMORPH_TYPE_` | 38 |
| `AOE_` | 36 | | `IMMUNITY_TYPE_` | 33 |
| `DAMAGE_` | 30 | | `ACTION_` | 29 |
| `SAVING_THROW_` | 24 | | `STANDARD_FACTION_` | 17 |
| `INVENTORY_SLOT_` | 13 (`NUM_INVENTORY_SLOTS` = 18) | | `PLANET_`, `NPC_` | 16 each |

Most are row numbers into 2DA tables (`appearance`, `visualeffects`, `feat`, `baseitems`,
`spells`, ...) or engine enums; the engine side must agree with them.

## Script libraries shipped as source

The install ships 1774 NSS sources, all in `data/scripts.bif`: `nwscript.nss`, 23 include-only
libraries (no `main` or `StartingConditional`), and 1750 scripts, all but one of which
(`fightback`) also exist compiled. The libraries, with how many shipped scripts `#include` each:

| Library | Lines | Included by | Includes |
|---|---|---|---|
| `k_inc_debug` | 105 | 614 | |
| `k_inc_man` | 946 | 161 | generic, utility |
| `k_inc_utility` | 3011 | 155 | |
| `k_inc_tat` | 2757 | 89 | utility, generic |
| `k_inc_generic` | 2360 | 50 | gensupport, walkways, drop |
| `k_inc_dan` | 389 | 23 | generic, utility |
| `k_inc_switch` | 43 | 21 | |
| `k_inc_cheat` | 135 | 20 | debug |
| `k_inc_stunt` | 774 | 17 | |
| `k_inc_treasure` | 835 | 15 | |
| `k_inc_kas` | 1755 | 10 | utility, generic |
| `k_inc_end` | 293 | 7 | utility, generic |
| `k_inc_ebonhawk` | 884 | 5 | |
| `k_inc_force` | 2395 | 3 | |
| `k_inc_zone` | 177 | 2 | generic |
| `k_inc_gensupport` | 3163 | 1 (and via generic) | |
| `k_inc_walkways` | 657 | 1 (and via generic) | |
| `k_inc_drop` | 277 | 1 (and via generic) | |
| `k_inc_tar` | 595 | 1 | debug, utility |
| `k_inc_lev` | 182 | 0 | debug, utility |
| `k_inc_unk` | 339 | 0 | debug, utility, generic |
| `k_inc_endgame` | 111 | 0 | |
| `e3_scripts` | 304 | 0 | (an early demo AI, unused) |

`k_inc_generic` (with its support library `k_inc_gensupport`) is the creature AI; `k_inc_force`
the Force powers; `k_inc_utility` plot flags, alignment and skill helpers; the planet libraries
(`k_inc_tat`, `k_inc_man`, `k_inc_kas`, ...) hold per-planet helpers. Five libraries also exist
as NCS in scripts.bif (`k_inc_generic`, `k_inc_gensupport`, `k_inc_switch`, `k_inc_unk`,
`k_inc_walkways`); they look like accidental compiles (two are the 23-byte empty program) and
nothing is known to run them.

Only part of the compiled corpus has source: 1754 of 8926 NCS resrefs. The NCS of the others
(most module scripts) are the only form we have, which is fine: the VM runs bytecode.

## Usage by the compiled scripts

Counted over the 9714 unique (resref, content) NCS files, with `ncsdis.py`. **466 routines are
called; 306 are never called by any shipped script** (`ncs_files` = 0 in the TSV), including 72
of the 97 `SWMG_` minigame routines, most `GetFaction*`, trap and lock queries, the trig and
`Print*` helpers, and NWN leftovers. 71 routines are called from exactly one file. 86 routines
account for 90% of all 314,074 call sites, 199 for 99%.

Call counts are dominated by the include libraries: a script that calls into the AI carries
`k_inc_generic`'s helpers, so `GetHasSpell` (377) has 20,086 sites in 682 files. Both columns are
in the TSV; "files" is the better measure of how much of the game needs a routine.

Top 60 by number of files (this is the order to implement them in):

| # | Index | Routine | Files | Sites |
|---|---|---|---|---|
| 1 | 200 | `object GetObjectByTag` | 3387 | 9005 |
| 2 | 42 | `int GetIsObjectValid` | 3045 | 22530 |
| 3 | 580 | `int GetGlobalNumber` | 2386 | 3871 |
| 4 | 548 | `object GetFirstPC` | 2358 | 5780 |
| 5 | 6 | `void AssignCommand` | 1853 | 6481 |
| 6 | 680 | `void SetLocalBoolean` | 1759 | 2031 |
| 7 | 679 | `int GetLocalBoolean` | 1721 | 1970 |
| 8 | 7 | `void DelayCommand` | 1638 | 5563 |
| 9 | 166 | `int GetHitDice` | 1515 | 1797 |
| 10 | 578 | `int GetGlobalBoolean` | 1457 | 2275 |
| 11 | 294 | `void ActionDoCommand` | 1358 | 4848 |
| 12 | 581 | `void SetGlobalNumber` | 1322 | 1900 |
| 13 | 202 | `void ActionWait` | 1242 | 1418 |
| 14 | 40 | `void ActionPlayAnimation` | 1156 | 6696 |
| 15 | 579 | `void SetGlobalBoolean` | 1125 | 1584 |
| 16 | 92 | `string IntToString` | 1023 | 10380 |
| 17 | 168 | `string GetTag` | 1009 | 4145 |
| 18 | 9 | `void ClearAllActions` | 1002 | 5807 |
| 19 | 577 | `object GetPartyMemberByIndex` | 993 | 5295 |
| 20 | 0 | `int Random` | 972 | 9636 |
| 21 | 205 | `void ActionPauseConversation` | 947 | 949 |
| 22 | 197 | `object GetWaypointByTag` | 934 | 5399 |
| 23 | 206 | `void ActionResumeConversation` | 926 | 928 |
| 24 | 213 | `location GetLocation` | 885 | 3314 |
| 25 | 230 | `float IntToFloat` | 837 | 2531 |
| 26 | 383 | `void ActionForceMoveToObject` | 822 | 869 |
| 27 | 239 | `string GetStringByStrRef` | 815 | 815 |
| 28 | 393 | `void GiveXPToCreature` | 807 | 2403 |
| 29 | 151 | `float GetDistanceBetween` | 805 | 2158 |
| 30 | 217 | `int GetIsPC` | 796 | 804 |
| 31 | 204 | `void ActionStartConversation` | 787 | 1139 |
| 32 | 241 | `void DestroyObject` | 785 | 1308 |
| 33 | 220 | `void ApplyEffectToObject` | 757 | 1938 |
| 34 | 99 | `int d8` | 736 | 738 |
| 35 | 358 | `int GetGender` | 726 | 1406 |
| 36 | 681 | `int GetLocalNumber` | 716 | 3348 |
| 37 | 107 | `int GetRacialType` | 715 | 5432 |
| 38 | 682 | `void SetLocalNumber` | 713 | 3486 |
| 39 | 59 | `int GetStringLength` | 701 | 718 |
| 40 | 22 | `void ActionMoveToObject` | 699 | 1144 |
| 41 | 713 | `int GetStandardFaction` | 688 | 1124 |
| 42 | 63 | `string GetStringLeft` | 687 | 688 |
| 43 | 377 | `int GetHasSpell` | 682 | 20086 |
| 44 | 98 | `int d6` | 680 | 1714 |
| 45 | 96 | `int d3` | 680 | 884 |
| 46 | 101 | `int d12` | 674 | 674 |
| 47 | 319 | `float GetDistanceBetween2D` | 672 | 672 |
| 48 | 335 | `float GetDistanceToObject2D` | 672 | 672 |
| 49 | 31 | `object CreateItemOnObject` | 663 | 2254 |
| 50 | 25 | `object GetEnteringObject` | 646 | 662 |
| 51 | 54 | `void CancelCombat` | 608 | 951 |
| 52 | 761 | `int ShipBuild` | 593 | 846 |
| 53 | 229 | `object GetNearestObjectByTag` | 545 | 1077 |
| 54 | 582 | `void AurPostString` | 540 | 676 |
| 55 | 49 | `int GetCurrentHitPoints` | 517 | 2488 |
| 56 | 162 | `void SetCommandable` | 515 | 904 |
| 57 | 238 | `object GetPCSpeaker` | 492 | 631 |
| 58 | 232 | `int StringToInt` | 473 | 473 |
| 59 | 27 | `vector GetPosition` | 471 | 778 |
| 60 | 62 | `string GetStringRight` | 464 | 469 |

## Calls that don't match the shipped prototypes

Some shipped NCS were compiled against older versions of `nwscript.nss`.

**Fewer arguments than declared** (1093 call sites in 8 routines, plus `AddPartyMember`'s 2,
which are a different case; the engine must apply the defaults of the missing trailing
parameters):

| Routine | argc used / declared | Sites |
|---|---|---|
| 204 `ActionStartConversation` | 11 / 12 (no `bUseLeader`) | 1026 |
| 204 `ActionStartConversation` | 5 / 12 (no `sNameObjectToIgnore1..6`, `bUseLeader`) | 15 |
| 509 `StartNewModule` | 4 / 8 (no `sMovie3..6`) | 38 |
| 712 `ShowPartySelectionGUI` | 1 / 3 | 9 |
| 564 `EndGame` | 0 / 1 | 2 |
| 241 `DestroyObject` | 2 / 4 | 1 |
| 255 `BeginConversation` | 0 / 2 | 1 |
| 364 `PlayPazaak` | 4 / 5 | 1 |
| 574 `AddPartyMember` | 1 / 2 (see below) | 2 |

**Calls the shipped prototypes can't explain** (4 routines, 5 sites):

- 574 `AddPartyMember(int nNPC, object oCreature)` called with **one object** by
  `k_act_carthjoin` (in the Taris `tar_m02*`, `tar_m03*`, `tar_m10*` modules) and
  `k_ptar_missjoin` (`tar_m04aa`): written for an older `AddPartyMember(object)`. The required
  `oCreature` is missing, so this is not a defaults case. Handlers pop typed values and fail
  when the type is wrong (../re/nwscript-routines.md), so popping an int from the object cell
  most likely makes the call fail; what the VM does then is for RE.
- 518 `StartCreditSequence(int)` called with 2 arguments (`k_creditsplay`, STUNT_57; an int on
  top, so the current handler gets a valid first argument and a string is left over), and 700
  `ActionBarkString(int strRef)` called with 2 (`k_plev_corpse1`, lev_m40aa; an object on top,
  then strref 1075, so the older prototype took the object first): older two-parameter
  versions.
- 469 called with 2 arguments by `nw_s0_lghtnbolt` (scripts.bif): its shipped source calls
  `GetIsReactionTypeFriendly(oTarget)` (2 parameters, the second defaulted), a routine the
  shipped `nwscript.nss` no longer has; 469 is now `EffectBlasterDeflectionIncrease`. A leftover
  test spell script that nothing should run.

## Checked

```
python kotor/tools/py/nwscript.py      # writes the two TSVs, cross-checks against the NCS corpus
```

- Source: `nwscript.nss` from `data/scripts.bif` (the only copy). Parsed: 772 routines and 1490
  constants; every statement in the file parses (comments and `#define`s aside).
- Numbering: all 772 numbered comments agree with the declaration-order index.
- Corpus: every NCS copy in the install (13139), deduplicated to 9714 unique (resref, content)
  files. Max ACTION index used: 771 < 772. Every ACTION's `argc` lies between the routine's
  required and total parameter counts except the 4 explained routine/argc pairs above
  (**cross-check problems: 0, explained: 4**). `ncsdis.py --corpus` additionally checks every
  call's stack effect against these prototypes over all 8666 unique scripts (see ncs.md).
- Usage: 466 routines called, 306 never.
