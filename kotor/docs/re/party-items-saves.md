# Party, items and saves in swkotor.exe

How the original engine keeps the state that outlives a module: the save game (what is written,
in which order, and how it is read back), the global script variables, the party table (the nine
NPC slots, the active party, gold, the XP pool, solo mode, switching the player character), the
creatures' equipment and how items change stats, and inventories, containers and stores.
Addresses are for the Steam `swkotor.exe` after SteamStub removal (see [README.md](README.md)).
Every claim carries a confidence: **high** = read in the code, **med** = role clear, detail
inferred, **low** = plausible. Names are ours, in the Aurora/NWN vocabulary; the proposals for
every address below are in `kotor/re/proposals/party.tsv` (git-ignored scratch, merged into
[names.tsv](names.tsv) by the lead).

Related pages, and where the boundary is:

- [objects.md](objects.md): object classes, `CItemRepository` at creature `+0xa30`, the item and
  creature loaders and writers this page calls.
- [modules.md](modules.md): `LoadModule`, mounting `CURRENTGAME:` and a module's `.sav`, the IFO
  fields. This page covers what puts the `.sav` there and what is read around it.
- [gameloop.md](gameloop.md): the module-transition state machine (5.3–5.7: `StartModuleTransition`,
  `SavePlayerCharacters`, the arrival handshake, the autosave rules), time and pause. This page adds
  the party and save steps it names.
- [actions.md](actions.md): the PICKUPITEM / DROPITEM / EQUIPITEM / UNEQUIPITEM / GIVEITEM actions;
  here only what equipping changes.
- [combat.md](combat.md) and [rules.md](rules.md): what the effects created by items do; XP
  awarding and level-up (rules.md 4). [movement.md](movement.md): the client party table used for
  following and formation (section 6). [gui.md](gui.md): the save/load, party selection,
  inventory, equip, container, store and upgrade panels themselves.
- File formats: [../formats/gff-save.md](../formats/gff-save.md) (save GFFs; section 1.9 lists
  where it is wrong or incomplete), [../formats/gff-templates.md](../formats/gff-templates.md)
  (UTC/UTI/UTP/UTM), [../formats/erf.md](../formats/erf.md).

## 1. Save and load

### 1.1 The directories

The engine works on directories named by aliases (resolved by `CExoAliasList`; defaults in the
exe, overridable in `swkotor.ini` `[Alias]`, see [../formats/inventory.md](../formats/inventory.md)). (high)

| Alias | Holds | Life time |
|---|---|---|
| `SAVES:` | one folder per save, `%06d - %s` (number, folder name) | permanent |
| `GAMEINPROGRESS:` | the live state of the current game: every visited module's `<module>.sav`, `AVAILNPC<n>.utc`, `INVENTORY.res`, `REPUTE.fac`, `PC.utc` while an NPC is the player character | emptied at New Game; **replaced** by a load; packed whole into `SAVEGAME.sav` by a save |
| `FUTUREGAME:` | scratch: a save is extracted here first, then swapped in (1.6) | per load |
| `CURRENTGAME:` | the working copy of the current module's main file ([modules.md](modules.md)) | per module |
| `TEMP:` | `pifo` (the player characters in transit between modules) and character-creation leftovers | per transition |

**Save folders and numbers.** The folder is `SAVES:` + `%06d - %s`. Slot 0 is the quick save
(folder `000000 - QUICKSAVE`, `CClientExoAppInternal::QuickSave` `0x005f4b50`); slot 1 is the
autosave (`000001 - AUTOSAVE`, used both by the module-transition autosave and by the scripted
`DoSinglePlayerAutoSave`); manual saves get a number ≥ 2 from the save panel and the folder name
`Game%d` (`0x006c8790`; the install's only save is `000002 - Game1`), numbers stay below 1000. The
name the player types is not part of the folder: it goes into `savenfo.res` `SAVEGAMENAME`. (high
for slots 0 and 1 and the formats, med for the manual numbering)

### 1.2 What a save contains

Loose files in the save folder:

| File | Format | Written by | Read by | Conf. |
|---|---|---|---|---|
| `savenfo.res` | GFF `NFO ` V2.0 | `DoSaveGame` `0x004b3110` / `WriteTransitionAutoSave` `0x004b8300` | the save list (`CSWGuiSaveLoadEntry::ReadSaveInfo` `0x006c8e50`); `AUTOSAVEPARAMS` by `LoadTransitionAutoSave` `0x006ca250` | high |
| `PARTYTABLE.res` | GFF `PT  ` V2.0 | `CSWPartyTable::SavePartyTable` `0x005648c0` | `CSWPartyTable::LoadPartyTable` `0x00565d20` | high |
| `GLOBALVARS.res` | GFF `GVT ` V2.0 | `CSWGlobalVariableTable::SaveToDirectory` `0x0052ad10` | `LoadFromSaveDirectory` `0x0052ade0` | high |
| `SAVEGAME.sav` | ERF `MOD V1.0` holding every file of `GAMEINPROGRESS:` | `CERFFile::AddDirectory` in the two writers | `CERFFile::ExtractAll` in the two loaders | high |
| `Screen.tga` | TGA, 256 × 256, 24 bit | the renderer's screenshot writer (`0x00420f20`) called from `RequestSaveGame` `0x004b58a0`, before the save itself | the save list (screenshot label) | high |
| `pifo` | GFF `IFO ` with only `Mod_PlayerList` | transition autosaves only: a copy of `TEMP:pifo` | copied back to `TEMP:pifo` by `LoadTransitionAutoSave` | high |
| `CORRUPT` | 7-byte text "CORRUPT" | only when extracting `SAVEGAME.sav` failed (`0x006caaf0`) | the save list marks the row corrupt and does not read `savenfo` | high |

Inside `SAVEGAME.sav` (= the files of `GAMEINPROGRESS:`; ERF keys are upper case, e.g.
`AVAILNPC0`/2027, `END_M01AA`/2057, `INVENTORY`/0, `REPUTE`/2038 in the install's save):

| Entry | What | Written by | Conf. |
|---|---|---|---|
| `<MODULE>.sav` | nested ERF `MOD V1.0` with exactly three entries: `module.ifo` (all IFO fields, the event queue, the module's locals, `Mod_PlayerList` = the player creature), `<area>.git` (every object of the area except player-controlled creatures, i.e. **without the PC and the party members**: `CSWSArea::SaveCreatures` `0x00507680` skips creatures whose `+0xa88` is set), `<area>.are` | `SaveCurrentModuleToGameInProgress` `0x004b2e70` → `CSWSModule::SaveModuleIFO` `0x004c8960` (deletes the old file, creates the ERF with 3 entries, sets the module's "is a save" flag `+0x1c8`), the GIT step `0x004c3b10`, the ARE copy and close `0x004ca680` | high |
| `REPUTE.fac` | GFF `FAC `: `FactionList`, `RepList` of the faction manager (server `+0x10054`) | `0x004c3960`, at the end of every module IFO save | high |
| `AVAILNPC<n>.utc` | the full saved creature of NPC slot *n* (0..8) | `CSWPartyTable::SaveNPCState` `0x00563e80`; also `AddAvailableNPC*` | high |
| `INVENTORY.res` | GFF `INV `: `ItemList` of full item structs = the party's shared inventory | `CSWPartyTable::SaveInventory` `0x00564030` | high |
| `PC.utc` | the real player character while `SwitchPlayerCharacter` has put an NPC in its place (3.5) | `CSWPartyTable::SwitchPlayerCharacter` `0x005667c0` | high |

There is one `<MODULE>.sav` per module visited in the current game whose `modulesave.2da`
`IncludeInSave` is 1 (`0x004b20e0`; 0 for the cutscene `STUNT_*` modules, the swoop and turret
minigames). A transition into a module whose row has `DeleteSaveGroupOnEnter` deletes the `.sav`
of every module of that save group ([gameloop.md](gameloop.md) 5.3). (high)

### 1.3 Saving (quick save, manual save, scripted autosave)

Two halves, one frame apart. (high unless marked)

**Request** — `CServerExoAppInternal::RequestSaveGame(nSaveNumber, sFolderName, nPlayer)`
(`0x004b58a0`; reached from the client message 3/4, which carries number, folder name and the typed
name — the typed name goes to server `+0x1b93c` through `0x004af0e0` — and from the server main loop
for `DoSinglePlayerAutoSave` with number 1 and `"AUTOSAVE"`):

1. Sound mode 3 (muted while saving); make `SAVES:`; build `SAVES:%06d - %s`.
2. **Disk space**: if free space plus the size of an existing folder of that name is below the
   server's minimum (`+0x100c8`), send the client an out-of-space message and stop (returns 0).
3. Create the folder, or empty it if it exists (`CleanDirectory`: old files, including a
   `CORRUPT` marker, are removed).
4. Fill the transition block (`g_pAppManager+0x14`, see [gameloop.md](gameloop.md) 5.4): busy = 1,
   **mode = 2 (save)**, "skip one client frame" = 1, error = 0, `+0x18` = the folder, `+0x20` =
   `<folder>\SAVEGAME`, counters 0. Tell the client.
5. Take the **screenshot** now, from the last rendered frame: the camera is first nudged by
   `0x00638e80` on GUI object 0x106a (low: role), then `<SAVES path><%06d> - <name>\Screen` is
   written as a 256-pixel TGA (`0x00401080` → `0x00420f20(path, 256, 1, 1)`).
6. Unless it is slot 0 (quick save), draw one loading frame. Clear `+0x1b930`, `+0x1b938`.

**Write** — on the next server frame the main loop sees mode 2 and calls
`CServerExoAppInternal::DoSaveGame` (`0x004b3110`), which runs to completion in that frame,
drawing load-screen frames with a progress bar between steps:

| Step | Progress | What |
|---|---|---|
| 1 | 0 | Module name = the module's `CURRENTGAME:<m>` without the alias. Show the module's load screen (`loadscreens.2da` through the client), render a loading frame. Tell the client a save started (`0x0056c850(0)`). |
| 2 | — | **Save the current module** into `GAMEINPROGRESS:<m>.sav` (`0x004b2e70`, the table in 1.2; skipped when `IncludeInSave` is 0). The player creature is written into the IFO's `Mod_PlayerList`. |
| 3 | 5 | **Party table** (`CSWPartyTable::SaveGame(folder, 1)` `0x005665c0`): `SaveNPCState(n, 0)` for n = 0..8 (only slots whose creature exists in the world: party members and spawned available NPCs), `SaveInventory(0)` → `GAMEINPROGRESS:INVENTORY`, then `PARTYTABLE.res` into the save folder (3.9). |
| 4 | 10 | **Globals**: `GLOBALVARS.res` into the save folder (section 2). |
| 5 | 15 | (A NWN leftover writes the PC as `<folder>\Player.bic` when the global `0x00831fe0` is set; nothing ever sets it.) |
| 6 | 20 | **`savenfo.res`** into the save folder: `AREANAME` = the player's area `Name` (in the language of the player's client, med), `LASTMODULE` = the module name, `TIMEPLAYED` (3.10), `CHEATUSED` (party table `+0x194`), `SAVEGAMENAME` (server `+0x1b93c`), `GAMEPLAYHINT` / `STORYHINT` (the load-screen hint indices kept by the client), `LIVE1`..`LIVE6` (client strings) and `LIVECONTENT` (bit *i*−1 set when the alias `LIVE<i>` resolves to a non-empty path), `PORTRAIT<i>` for each member of the client party table in order (index 0 = the leader): the creature's portrait resref. |
| 7 | 25 → 60 | **`SAVEGAME.sav`**: create `<folder>\SAVEGAME`, type `MOD V1.0`, add every file of `GAMEINPROGRESS:` (progress 30..60 as files are added), finish, then read the header and key list back once. |
| 8 | 100 | Sound mode 0; end the load screen; fade back in unless a dialogue or similar takes over (in-game GUI `+0x30`/`+0xb4`); mark the transition block done (when the global `0x007a39dc` is 2 the block is reset instead; low: what that global selects); tell the client the save ended (`0x0056c850(1)`, `0x0056c980(2, 0)`). |

Nothing in this sequence pauses or clears the game: after the save the game continues where it
was. The party inventory and NPC objects stay as they are (step 3 does not clear them). (high)

### 1.4 The transition autosave

`CServerExoAppInternal::WriteTransitionAutoSave(sTargetModule, pModuleSave2DA)` (`0x004b8300`) is
called by `StartModuleTransition` when the target's `AutoSaveOnEnter` asks for it
([gameloop.md](gameloop.md) 5.7). At that point the module being left has already been saved to
`GAMEINPROGRESS:`, the player characters are in `TEMP:pifo` and the party's NPCs and inventory have
been written and cleared (1.8). It produces a save that **re-enters the target module**:
(high unless marked)

1. Show the target's load screen; folder `SAVES:000001 - AUTOSAVE` (created or emptied).
2. `PARTYTABLE.res` (progress 5 % of the bar's share), `GLOBALVARS.res` (10 %).
3. `savenfo.res`: `AREANAME` = the TLK string of `modulesave.2da` `AreaName` for the target,
   `LASTMODULE` = the target, `TIMEPLAYED`, `CHEATUSED`, **`PCAUTOSAVE` = 1**, **`SCREENSHOT`** =
   `load_<target>` if such a TGA or TPC exists, else the `BMPResRef` of the `DEFAULT` row of the
   load-screen table (there is no `Screen.tga`), `GAMEPLAYHINT`, `STORYHINT`, an
   **`AUTOSAVEPARAMS`** struct (the pending transition: start waypoint tag, the calendar and the
   pause snapshot, up to six queued movies, six words of in-game GUI state; filled by
   `0x004b2840`/`0x004b28e0`, read back by `0x006c9de0`; field names not listed here, low), and
   `PORTRAIT<i>`. No `SAVEGAMENAME`, no `LIVE*`.
4. `SAVEGAME.sav` from `GAMEINPROGRESS:` as in 1.3, then copy `TEMP:pifo` to `<folder>\pifo`.

### 1.5 The save list

`CSWGuiSaveLoad::PopulateList` (`0x006cc160`, gui.md) builds one row per folder; each row reads its
folder with `0x006c8e50`: number = the integer before `" - "`, folder name = the rest; if a file
`CORRUPT` exists the row is flagged corrupt (flags `|= 3`) and nothing else is read; otherwise from
`savenfo.res`: `AREANAME`, `LASTMODULE`, `TIMEPLAYED`, `SAVEGAMENAME` ("Old Save Game" when
missing), `CHEATUSED` (flag 0x80), `REBOOTAUTOSAVE` (0x08, Xbox only), `PCAUTOSAVE` (0x10),
`SCREENSHOT`, `GAMEPLAYHINT`, `STORYHINT`, `LIVECONTENT` + `LIVE<i>` (a row needing live content
whose alias is missing gets flag 0x21 and the content name), `PORTRAIT0..2`. (high)

### 1.6 Loading a normal save

`CSWGuiSaveLoad::LoadSelectedGame` (`0x006cb0e0`) picks one of two paths by the row's
`PCAUTOSAVE` flag. The normal path: (high unless marked)

1. **Extract into a scratch directory**: `ExtractSaveToFutureGame` (`0x006c9a90`) creates and
   empties `FUTUREGAME:` and extracts `SAVEGAME.sav` into it.
2. **Swap**: on success `PrepareGameInProgress` (`0x006caaf0`) deletes the `GAMEINPROGRESS:`
   directory and renames `FUTUREGAME:` to it (one `MoveFile`). On failure it writes the `CORRUPT`
   marker into the save folder and the load stops — the current game is untouched.
3. From the main menu the server is created (`CAppManager::CreateServer`) and both world timers are
   paused; in game, all modal panels are popped (med: the decompiled panel code blurs the two
   cases). Then server `+0x100c4` = 1
   (**`GetLoadFromSaveGame`** returns this) and the client sends message 3/5 (number, folder name,
   `LASTMODULE`).
4. The server handler calls **`CServerExoAppInternal::LoadGame`** (`0x004ba640`): sets the load
   screen, mounts the save folder as a resource directory, **`LoadPartyTable`** (`PARTYTABLE`, 3.9),
   **`LoadFromSaveDirectory`** (`GLOBALVARS`, section 2), unmounts it, sets party table `+0x10c` = 1
   ("party positions come from the save", 1.8), clears `+0x1b930`/`+0x1b938`, and calls
   **`LoadModule(LASTMODULE)`**.
5. `LoadModule` ([modules.md](modules.md)) first **unloads** the running module (every object,
   the event queue, the party's per-module state — 1.8), finds `GAMEINPROGRESS:<m>.sav` and loads in
   mode 3: the IFO (including the module's saved event queue, time and locals), `REPUTE.fac`, the
   area, then the GIT objects with their saved object ids. Before the GIT objects are created the
   nine NPC-slot object links are reset to `OBJECT_INVALID` (`0x005639c0`, server loop tick 2).
6. `StartModuleRunning` (`0x004b6270`): the module comes from a save and it is not a transition, so
   **the player is restored from the IFO's `Mod_PlayerList`** (`RestorePlayerFromSave`
   `0x004b5f50` → `CSWSPlayer::LoadCharacter(index, …)` `0x00561e30`: a new creature with the saved
   `ObjectId` as a character object, stats, items, effects, actions, scripts, position, area id) and
   **the party is restored** (`CSWPartyTable::RestoreParty` `0x00565760`, 1.8). `OnClientEnter` is
   queued.
7. The arrival handshake of [gameloop.md](gameloop.md) 5.5 places the PC at its saved position and
   adds it to the area; the party members keep their saved positions (`+0x10c` skips the formation
   placement, then clears the flag).

### 1.7 Loading a transition autosave

`CSWGuiSaveLoad::LoadTransitionAutoSave` (`0x006ca250`), for rows with `PCAUTOSAVE`: (high)

1. Unload the module (from in game the server is destroyed and re-created first), set the
   transition-in-progress flag (`+0x100b4`).
2. Make `GAMEINPROGRESS:` (empty it if it exists) and **extract `SAVEGAME.sav` straight into it**
   (no `FUTUREGAME:` swap, no `CORRUPT` marker); copy `<folder>\pifo` to `TEMP:pifo`.
3. Mount the save folder; `LoadPartyTable`; globals; read `savenfo.res` `AUTOSAVEPARAMS` and
   restore: the start waypoint (`SetMoveToModuleWaypoint`; `"*"` = none), the calendar, the pause
   snapshot (`+0x100ac`/`+0x100b0`), six queued movies, the in-game GUI words; unmount.
4. Set "this is a transition" (`+0x1007c` = 1) and start loading `LASTMODULE`
   (`BeginLoadModule` `0x004ba820`).

The arrival then runs exactly like a transition: `StartModuleRunning` sees `+0x1007c` and does not
restore from the IFO; the client answers with login 0xf and `PlayerLoginToModule` re-creates the
PC from `TEMP:pifo` and calls `RestoreParty`; `PlacePlayerInModule` moves the PC to the waypoint and
the party into formation (1.8). `GetLoadFromSaveGame` is **not** set on this path. (high)

### 1.8 What a module transition does to the party

[gameloop.md](gameloop.md) 5.3–5.5 has the order of the whole transition; the party steps are:
(high unless marked)

**Leaving** (`SavePlayerCharacters` `0x004b2ba0`, step 5 of `StartModuleTransition`):

1. Every player creature: `ClearAllActions`, then written into a `Mod_PlayerList` (struct id
   0xBEAD) of an `IFO ` GFF saved as `TEMP:pifo`; each player remembers its index (`+0x80`).
2. `SaveAllNPCStates(1)` (`0x00565530`): `SaveNPCState(n, bClearActions = 1)` for every slot with a
   creature in the world → `GAMEINPROGRESS:AVAILNPC<n>.utc`.
3. `SaveInventory(1)` → `GAMEINPROGRESS:INVENTORY`, then the party repository is emptied (its item
   list count is reset; the item objects die with the module).

`UnloadModule` then destroys all creatures and clears the party table's per-module state: the
inventory list (`0x00563600`, also clears "party restored" `+0x110`) and, when the next module loads,
the nine slot→object links. The persistent table (members, available flags, gold, XP pool, solo
mode, leader, galaxy map, pazaak) is untouched. (high)

**Arriving** — `CSWPartyTable::RestoreParty` (`0x00565760`, once per module: guarded by `+0x110`),
called from `PlayerLoginToModule` (transitions) or `StartModuleRunning` (saves):

1. Mount `GAMEINPROGRESS:` as a directory.
2. If no NPC is the player character (`+0xf0` = −1): for each party member in list order,
   `SpawnAvailableNPC(slot, bUseLocation = 0, …, bRevive = !GetLoadFromSaveGame)` — the creature is
   re-created from `AVAILNPC<n>.utc` at the position saved in that file (3.4), the client is told to
   fade it in, and it becomes player-controlled (`SetPlayerControlled(1, 1)`). If an NPC is the
   player character, that slot's link is set to the player's creature instead.
3. Load `INVENTORY` (GFF `INV `) into the party repository (created if needed, else emptied first):
   each `ItemList` struct becomes a new `CSWSItem` (`CSWSItem::LoadItem`), is added with stacking
   and gets the player as possessor.
4. Unmount. Merge the PC's own repository and gold into the party's, then each slot creature's
   (`MergeCreatureIntoParty` `0x005641e0`, 3.6).
5. For the PC and each slot creature: `EquipDefaultClothes` (`0x00501c40`): a creature whose saved
   body armour could not be re-equipped when it was loaded (flag `+0xab8`, 4.8) gets
   `g_a_clothes01` from the party inventory, or a new one, in the body slot.
6. `+0x110` = 1.

**Placing** — `CSWPartyTable::PlacePartyAroundLeader` (`0x00565b00`), from `PlacePlayerInModule`
after the PC has its final position: restart the client party trail at the PC's position and facing
(movement.md 6); unless `+0x10c` (set by `LoadGame`) is set, each member *i* goes to its formation
point (the client party table's formation offset for its slot, rotated by the PC's facing, added to
the PC's position), snapped to a free walkmesh spot within 10 m (`0x004aeb60`), facing the PC's
direction; stealth is turned off for the whole party (`SetPartyStealthMode(0)` `0x00563c60`) and
**solo mode is switched off**. `+0x10c` is cleared either way. (high for the steps, med for the
formation geometry, which belongs to movement.md)

Dead members: after a transition `bRevive` is set, so a member whose saved current HP is below 1
gets a resurrection effect (type 4, `ApplyEffect`) and its `+0xf0` flag set when spawned; after a
save load dead members stay dead. (high for the code path, med for "type 4 = resurrection", which
follows NWN's numbering)

### 1.9 Corrections to gff-save.md

The format page was written from the one save before the code was read. Where the code says
otherwise or more: (high unless marked)

- **GVT numbers are signed**: one byte each, written as the low byte of the script value and read
  back sign-extended: −128..127, as `nwscript.nss` says, not 0..255.
- **GVT boolean bit order** is settled: boolean *k* of `CatBoolean` is bit `0x80 >> (k & 7)` of byte
  `k >> 3` of `ValBoolean` (most significant bit first). `ValBoolean` is `count/8 + 1` bytes.
- **GVT name order** is the order of the engine's hash table, not arbitrary (section 2); readers
  must map by name, which the engine itself does. `ValLocation` is always 2400 bytes (100 slots of
  position x, y, z + orientation x, y, z); `ValString` has one struct per string global.
- **PT labels longer than 16 characters**: the code writes `PT_CONTROLLED_NPC`, `PT_COST_MULT_LIST`
  and `PT_COST_MULT_VALUE`; the GFF writer truncates labels to 16, hence `PT_CONTROLLED_NP`,
  `PT_COST_MULT_LIS`, `PT_COST_MULT_VAL` in the file. A reader must compare the first 16 characters.
- **PT_PAZAAKCARDS** has 18 card counts (INT); the 19th entry, a BYTE, is a writer slip that stores
  `PT_CHEAT_USED`'s value again. The reader reads only 18. Write 18 INTs plus that BYTE to match.
- **PT_IS_LEADER** is 1 for the member whose slot equals the table's leader slot (`+0xec`, −1 = the
  PC leads). **PT_CONTROLLED_NP(C)** is the NPC slot that `SwitchPlayerCharacter` made the player
  character, −1 normally (it is not the Tab-selected leader).
- **PT_COST_MULT_LIS(T)** is not inferred: one float per `baseitems.2da` row, the per-base-item price
  multiplier set by `ChangeItemCost` (routine 747), read back into the base-item table (`+0xc4` of
  each row) — 1.0 when absent.
- **PT_PLAYEDSECONDS**: a save without it is read through `PT_PLAYEDMINUTES` × 60. `TIMEPLAYED` in
  `savenfo` is the same total.
- **GlxyMapPlntMsk**: bits 0–15 = planet *n* available, bits 16–31 = planet *n* selectable;
  `GlxyMapNumPnts` must be 16 or the mask is ignored on load.
- **PT_TUT_WND_SHOWN** (6 bytes) and **PT_LAST_GUI_PNL** are the in-game GUI's tutorial-shown
  flags (`+0xba8`) and last panel (`+0x2c`); the message lists are the GUI's feedback and dialogue
  logs (a missing `PT_FB_MSG_TYPE` defaults to 0x10000000).
- **PT_AVAIL_NPCS/PT_NPC_AVAIL** is the slot's "available" flag; `RemoveAvailableNPC` clears it but
  leaves `AVAILNPC<n>.utc` on disk. Slots are not fixed people: scripts reuse them (the install's
  save has Trask in slot 0, `NPC_BASTILA`).
- **savenfo** extra fields: `PCAUTOSAVE`, `SCREENSHOT` and `AUTOSAVEPARAMS` exist only in
  transition autosaves (which lack `SAVEGAMENAME` and `LIVE*`); `REBOOTAUTOSAVE` is read but never
  written on PC. `PORTRAIT<i>` follows the client party order (leader first), up to 3.
- **SAVEGAME.sav** may also hold `PC.utc`; transition autosaves have a loose `pifo` next to it. The
  nested module ERF has exactly three entries and its key type is 2057 (`sav`).
- **availnpcN.utc** is written when the NPC becomes available, and again at every save and
  transition while its creature exists. Party members' own `ItemList` and `Gold` are always empty:
  both live in the party (3.6).
- **The GIT of a saved area does not contain the PC or the party members** (player-controlled
  creatures are skipped); spawned NPCs that are not in the party *are* in the GIT.
- **INVENTORY.res** is in the party inventory's order: sorted by base item, then by localized name
  (5.2). Each `Equip_ItemList` element's **struct id is the slot mask** (0x2 body, 0x10 right
  weapon …, 4.1).
- **FollowInfo** of a saved party member is always the default record (3.6).

## 2. Global variables

`CSWGlobalVariableTable` lives at server internal `+0x100fc` (`CServerExoApp::GetGlobalVariableTable`
`0x004aee60`; constructor `0x0052b170` from the server constructor). (high)

### 2.1 The catalogue

At start-up `0x004b1650` loads `globalcat.2da` (`LoadCatalogue` `0x0052ae50`): for each row, `Name`
(must be shorter than 22 characters, i.e. at most 21) and `Type` (`Boolean`, `Number`, `Location`,
`String`, compared without case); a duplicate name or a full category is logged and the row
skipped; an unknown type is logged and the row then added as a string (med: read from the control
flow; the shipped table has no such row). Each name gets the next index of its type. Capacities: **900 booleans, 500 numbers,
100 locations, 5 strings** (the shipped catalogue uses 809, 369, 5, 2). (high)

Names live in an open-addressing hash table of **1775** entries of 0x18 bytes: the name (up to 22
bytes with its NUL) and a 16-bit word = type in bits 14–15 (0 boolean, 1 number, 2 location,
3 string) and index in bits 0–13. The hash is a CRC-32 (reflected polynomial 0xEDB88320, initial
value 0, no final inversion) over the **upper-cased** name, modulo 1775; collisions probe linearly
to the next slot. Lookups compare names without case. (high; the save's name order reproduces
exactly when the shipped catalogue is inserted in row order this way, checked with a probe)

### 2.2 Values and the script routines

| Store | Offset | Size |
|---|---|---|
| booleans | `+0xa668` | bit array, 113 bytes; index *i* = bit `0x80 >> (i & 7)` of byte `i >> 3` |
| numbers | `+0xa6d9` | 500 bytes |
| locations | `+0xa8d0` | 100 × 0x18 (`CScriptLocation`: position, orientation; no area) |
| strings | `+0xb230` | 5 `CExoString` |
| counts per type | `+0xb258`..`+0xb264` | |

| Routine | Handler | Behaviour | Conf. |
|---|---|---|---|
| 578 `GetGlobalBoolean` / 580 `GetGlobalNumber` | `0x00538dc0` | look up by name; boolean → 0/1; number → the byte **sign-extended** (−128..127) | high |
| 579 `SetGlobalBoolean` / 581 `SetGlobalNumber` | `0x00542b60` | boolean stores `value != 0`; number stores the low byte of the value (no clamping: 200 reads back as −56) | high |
| 692 / 693 `Get/SetGlobalLocation` | `0x00538cd0` / `0x00542a50` | copies the 6 floats | high |
| 194 / 160 `Get/SetGlobalString` | `0x00538ed0` / `0x00542c60` | | high |

A name that is not in the catalogue, or has another type, only logs "Script var … not in
catalogue!" / "… is not BOOLEAN!" and the like (the message is built and thrown away); the
getters then return 0 / empty. An implementation should treat unknown names as reads of 0 and ignored
writes. (med for the result after the error: the code continues with an invalid index)

### 2.3 Saving and loading

`SaveToDirectory(folder)` (`0x0052ad10`) writes `<folder>\GLOBALVARS` (`WriteTable` `0x005299b0`,
GFF `GVT ` with catalogue): it walks the hash table from slot 0 to 1774 and appends each name to
`CatBoolean`/`CatNumber`/`CatLocation`/`CatString` and its value to the packed array of its type, so
the file order is hash order. Fields: `ValBoolean` (VOID, `count/8 + 1` bytes), `ValNumber` (VOID,
one byte per number), `ValLocation` (VOID, always 2400 bytes), `ValString` (list of `String`).
(high)

`LoadFromSaveDirectory` (`0x0052ade0`) reads `GLOBALVARS` through the resource manager (the save
folder is mounted at that moment). With a `CatBoolean` list it uses `ReadTableWithCat`
(`0x0052a280`): **all values are cleared first**, then every saved name is looked up and its value
copied; a saved name missing from the catalogue is **added** (if its type has room), so globals of a
mod survive a round trip. Without the catalogue lists an older layout is read positionally
(`0x00529ef0`, low). Strings: at most 5. (high)

## 3. The party

### 3.1 The party table

`CSWPartyTable` is embedded in `CServerExoAppInternal` at `+0x1b770`
(`CServerExoApp::GetPartyTable` `0x004aee70`); `PARTYTABLE.res` is its image. Constructor
`0x00563d20`, reset `0x00563200` (New Game and before loading a `PARTYTABLE`). (high)

| Offset | Field | Reset value | Saved as |
|---|---|---|---|
| `+0x00` | number of NPCs in the active party (0..2) | 0 | `PT_NUM_MEMBERS` |
| `+0x04`, `+0x08` | their NPC slots, in join order | — | `PT_MEMBERS/PT_MEMBER_ID` |
| `+0x0c` + 4·n | object id of slot n's creature in the current module | `OBJECT_INVALID` | not saved |
| `+0x30` + 4·n | slot n available | 0 | `PT_NPC_AVAIL` |
| `+0x54` + n | slot n selectable in party selection | 1 | `PT_NPC_SELECT` |
| `+0x60` + 4·p | planet p (0..15) available | 0 | `GlxyMapPlntMsk` bits 0–15 |
| `+0xa0` + 4·p | planet p selectable | 0 | bits 16–31 |
| `+0xe0` | selected planet | −1 | `GlxyMapSelPnt` |
| `+0xe4` | party AI style (`PARTY_AISTYLE_*`) | 0 | `PT_AISTATE` |
| `+0xe8` | follow state | 0 | `PT_FOLLOWSTATE` |
| `+0xec` | leader slot (−1 = the PC) | −1 | `PT_IS_LEADER` |
| `+0xf0` | slot made player character by `SwitchPlayerCharacter` (−1 = none) | −1 | `PT_CONTROLLED_NPC` |
| `+0xf8` | XP pool | 0 | `PT_XP_POOL` |
| `+0xfc` | credits | 0 | `PT_GOLD` |
| `+0x100`/`+0x104`/`+0x108` | "Return" button shown / its strref / question strref (`SetReturnStrref` `0x00563ab0`) | 1 / 32179 / 42120 | not saved |
| `+0x10c` | "keep positions" flag for the next placement (1.6) | 0 | — |
| `+0x110` | party restored in this module | 0 | — |
| `+0x114` | seconds played before this session | 0 | `PT_PLAYEDSECONDS` |
| `+0x118` | the party's `CItemRepository` (created lazily, owner = the player creature, `GetPartyInventory` `0x00563340`) | null | `INVENTORY.res` |
| `+0x11c` | the journal (12-byte object, `GetJournal` `0x005633c0`) | null | `JNL_*` |
| `+0x120` + 4·c | pazaak side cards owned, c = 0..17 | 2 for c = 0..4, else 0 | `PT_PAZAAKCARDS` |
| `+0x168` + 4·k | the 10-card side deck | −1 | `PT_PAZSIDELIST` |
| `+0x190` | solo mode | 0 | `PT_SOLOMODE` |
| `+0x194` | cheat used | 0 | `PT_CHEAT_USED`, savenfo `CHEATUSED` |

### 3.2 NPC slots

There are **nine slots, 0..8**, the rows of `npc.2da` and the `NPC_*` constants (0 Bastila,
1 Canderous, 2 Carth, 3 HK-47, 4 Jolee, 5 Juhani, 6 Mission, 7 T3-M4, 8 Zaalbar; `NPC_PLAYER` = −1
means the PC). `npc.2da` also has row 9 `GAME_XP_General` and row 10 `PER_NPC_Bonus` (rules.md 4.2).
A slot is a container, not an identity: `AddAvailableNPCByTemplate(NPC_BASTILA, "end_trask")` puts
Trask in slot 0 on the Endar Spire. (high)

Three states per slot:

- **not available** (`+0x30` = 0): unknown to the party. Most routines refuse such a slot.
- **available**: has joined; its creature state is `GAMEINPROGRESS:AVAILNPC<n>.utc`. It may or may
  not have a creature in the current module (`+0x0c`); without one it exists only as that file.
- **in the party**: available, listed in `+0x04..`, its creature is in the world and
  player-controlled (`+0xa88`), follows the leader and can be controlled with Tab.

### 3.3 Routines and internal operations

| Routine | Handler → table method | Behaviour | Conf. |
|---|---|---|---|
| 697 `AddAvailableNPCByTemplate(n, resref)` | `0x0052dcd0` → `0x005645f0` | refuses an available slot; creates a temporary creature, `LoadFromTemplate(resref)`, `AddAvailableNPCByObject`, deletes the temporary creature. Returns success | high |
| 694 `AddAvailableNPCByObject(n, creature)` | `0x0052dc40` → `0x00564300` | refuses an available slot or a missing creature. Sets available; merges the creature's gold and items into the party (3.6); computes `JoiningXP` (3.4); adds it to the PC's faction; resets something in its stats (`0x005a5680(0)`, low); writes `GAMEINPROGRESS:AVAILNPC<n>` (type 2027). The creature is **not** linked to the slot | high |
| 695 `RemoveAvailableNPC(n)` | `0x00541b40` → `0x005646d0` | clears the available flag; nothing else (file, membership and creature untouched) | high |
| 696 `IsAvailableCreature(n)` / 709 `GetNPCSelectability(n)` | `0x0053ed70` → `0x005636b0` / `0x005637c0` | the flags (selectability only for available slots) | high |
| 708 `SetNPCSelectability(n, b)` | `0x00543300` → `0x005637f0` | only for available slots | high |
| 698 `SpawnAvailableNPC(n, location)` | `0x00543ed0` → `0x00565130` | 3.4 | high |
| 767 `SetAvailableNPCId(n, creature)` | `0x00548180` → `0x005636f0` | links an existing creature to an available slot (used to re-link NPCs that live in a GIT, e.g. on the Ebon Hawk after a load) | high |
| 734 `SaveNPCState(n)` | `0x005421a0` → `0x00563e80` | writes the slot's creature to `AVAILNPC<n>` now, without clearing its actions | high |
| 574 `AddPartyMember(n, creature)` | `0x0052de70` → `0x00565620` | 3.5 | high |
| 575 `RemovePartyMember(n)` | `0x00541c00` → `0x00565560` | 3.5 | high |
| 699 `IsNPCPartyMember(n)` | `0x0053f100` → `0x00563710` | n in `+0x04..` | high |
| 576 `IsObjectPartyMember(o)` | `0x0053f160` | the creature's `+0xa88` (player-controlled), so also true for the PC | high |
| 126 `GetPartyMemberCount()` / 577 `GetPartyMemberByIndex(i)` | `0x0053c8f0` / `0x0053c870` | the **client** party table (movement.md 6.1): count including the PC, index 0 = the current leader | high |
| 13 `SetPartyLeader(n)` | `0x00545a70` | 3.5 | high |
| 11 `SwitchPlayerCharacter(n)` | `0x00544910` → `0x005667c0` | 3.5 | high |
| 462 / 753 `GetSoloMode` / `SetSoloMode(b)` | `0x00546af0` / `0x00547ce0` → `0x00565500` | 3.7 | high |
| 704 / 706 `GetPartyAIStyle` / `SetPartyAIStyle` | `0x005459a0` / `0x00545c50` | `+0xe4` | high |
| 712 `ShowPartySelectionGUI(script, force1, force2)` | `0x005438b0` → `CGuiInGame::ShowPartySelection` `0x0062dd20` | 3.8 | high |
| 739–744 galaxy map | `0x005467b0`…`0x00546970` → `0x00563ae0`…`0x00563b60` | planet flags; selecting needs available and selectable | high |
| 418 `GetGold`, 322 `GiveGoldToCreature`, 444 `TakeGoldFromCreature` | `0x00539030`, `0x0053e690`, `0x00544970` | 3.6, 5.5 | high |
| 393 `GiveXPToCreature`, 714 `GivePlotXP` | rules.md 4.2 | the pool, 3.4 | high |

Internal helpers: `IsCreaturePartyMember` `0x00563740`, `IsCreatureAvailableNPC` `0x00563790`,
`GetNPCIndex` `0x005638a0` (−1 if none), `IsCreatureLeader` `0x00563a00`,
`SetLeaderByCreature` `0x00563a40` (called by the client when the leader changes),
`ClearNPCObjectId` `0x005639e0` (by `DestroyObject` on an NPC creature), `DespawnNPC(n, bFade)`
`0x00563810` (unless n is a member: unlink, client fade-out, delete the creature),
`MountGameInProgress` / `UnmountGameInProgress` `0x005638d0` / `0x00563950`. (high/med)

### 3.4 Getting an NPC's creature, spawning, XP catch-up

`GetNPCObject(n, bSpawn, bRevive)` (`0x00564700`; 33 callers, many in the GUI): for an available
slot, return its linked creature; if none and `bSpawn`, create a creature, mount `GAMEINPROGRESS:`,
`LoadFromTemplate("AVAILNPC<n>")` (the full saved creature, including position, effects, items),
unmount, revive it if `bRevive` and its current HP < 1 (1.8), link it and return its id; else
`OBJECT_INVALID`. (high)

`SpawnAvailableNPC(n, bUseLocation, position, orientation, bRevive)` (`0x00565130`): (high)

1. `GetNPCObject(n, 1, bRevive)`; `ClearAllActions` (forcing it through even if not commandable).
2. Position: the location's, or (bUseLocation = 0) the creature's own. If the area finds a problem
   with that point (`0x004bb600`), take the nearest free walkmesh spot within 20 m (`0x004be860`,
   using the creature's radius).
3. `AddToArea` there, then set the orientation.
4. **XP catch-up**: *p* = `npc.2da` `PercentXP` of the slot × 0.01 (1.0 when the cell is missing or
   0); *earned* = XP − `JoiningXP` (creature `+0x22c`). If *earned* < trunc(pool × *p*), give
   `AddExperience(pool − trunc(earned × 100 / PercentXP))`, which itself scales by `PercentXP`
   (rules.md 4.2), so the NPC ends at *p* × pool earned XP; then, with the client's auto-level-up
   option (client options `+8` & 1) and `CanLevelUp`, `AutoLevelUp(1)`.

`JoiningXP` (when the NPC becomes available, `0x00564300`): with *L* the creature's level and
*need* = 1000 × *L*(*L*−1)/2 (the d20 threshold of its level, computed, not read from
`exptable.2da`), `JoiningXP` = *need* − trunc(pool × *p*) if positive, else 0. So a recruit is not
caught up until the pool share passes what its level already implies. (high)

**The XP pool** (`+0xf8`, `PT_XP_POOL`) is the sum of all party XP ever awarded
(`CSWPartyTable::AddExperience` `0x005653a0`, rules.md 4.2): active members and the PC get the XP
at once, inactive available NPCs only through the catch-up above when they are next spawned.
(high)

### 3.5 Membership, leader, player character

**AddPartyMember(n, creature)** (`0x00565620`) succeeds only if no NPC is the player character
(`+0xf0` = −1), the party has fewer than **2** NPCs (party = PC + 2), slot n is available, the
creature exists and is not linked to another slot. Then: append n to the member list, link the
creature to slot n, tell the client to fade it in, `SetPlayerControlled(1, 1)` (`+0xa88` = 1, AI
level 4, a 0x3c-byte follow record at `+0x4c0`), merge its gold and items into the party (3.6),
put default clothes on if pending (`EquipDefaultClothes` `0x00501c40`). If the party had no NPC
before and the PC is in stealth mode (creature `+0x4d1`, saved as `StealthMode`), solo mode is
set. Adding an existing member succeeds without change. The routine handler also tells the client
and re-applies `SetPlayerControlled`. (high)

**RemovePartyMember(n)** (`0x00565560`) needs `+0xf0` = −1, a non-empty party and an available
slot: removes **all effects except equipment, innate and one internal type** from the NPC
(`CSWSObject::RemoveAllEffects(0)` `0x004d0940`), removes n from the list (the others shift down)
and turns solo mode off when the party becomes empty. The creature stays in the world and stays
linked; the handler releases it from player control (`SetPlayerControlled(0, 1)`: AI level 2) and
tells the client. (high)

**SetPartyLeader(n)** (routine 13, `0x00545a70`): for n ≥ 0, find the slot's creature
(`GetNPCObject(n, 0, 1)`) in the client party table and make that entry the leader
(`CSWCParty::SetLeader` `0x00635480`, which also records the slot at `+0xec`); returns 0 if it is not
in the party. For n = −1 (the PC): every client party member that is player-controlled, flagged
`+0x9d4`, and dead or dying first gets a resurrection effect (type 4) and `+0xf0` = 1; then the
client party's `SetLeader(−3)` makes the PC the leader (med: −3 read as "the player"); returns 1. (high for the steps, low for why revival is tied to this case)

**SwitchPlayerCharacter(n)** (routine 11, `0x005667c0`) replaces the player's creature by an NPC (or
back): (high)

- To an NPC (n available, not already the one): if the real PC is the current character it is
  written to `GAMEINPROGRESS:PC.utc`; if another NPC is, that one loses `IsPC` (stats `+0x6c`) and
  `+0x9d4` and is saved to its `AVAILNPC` file. The target's creature is taken or spawned (spawned at
  the current character's position). The current character's creature is removed (fade-out and
  delete; for an NPC through `DespawnNPC`).
- Back to the PC (n = −1, an NPC is current): the NPC is saved and despawned the same way and a new
  creature is loaded from `GAMEINPROGRESS:PC` at the NPC's position.
- Common tail: reset the client party table; the new creature becomes player-controlled with
  `IsPC` = 1 and `+0x9d4` = 1; the party inventory's possessor becomes it; it is added to the area
  (when newly created) and becomes the player's creature (`CSWSPlayer +0x38`, client rebinding
  `0x00561c40`); **every party member is removed** (`RemovePartyMember` from the last, and the
  creatures of former members despawned); `+0xf0` = n.

While `+0xf0` ≠ −1 `AddPartyMember` and `RemovePartyMember` refuse; a save in this state keeps
`PT_CONTROLLED_NPC` and `PC.utc`, and `RestoreParty` links the slot to the player creature.

### 3.6 Shared gold and inventory

The party has **one purse** (`+0xfc`, `PT_GOLD`, capped at 999,999,999) and **one inventory**
(`+0x118`, `CSWPartyTable::GetPartyInventory` `0x00563340`, created on first use, kept sorted):
every routine that asks a player-controlled creature for its gold or its item list
(`CSWSCreature::GetGold` `0x004edd60`, `GetItemRepository(1)` `0x004ef770`) gets the party's; a
creature outside the party uses its own (`+0x9d0`, `+0xa30`). Section 5.5 has the details (gold
routines, script iteration), 5.9 the credits items and pazaak cards. Equipped items are not in any
list (section 4). (high)

**Joining** — `MergeCreatureIntoParty(creature)` (`0x005641e0`), when an NPC becomes available,
joins the party, and for everyone in `RestoreParty`: with the creature temporarily not
player-controlled, its own gold is added to the purse and every item of its own repository is moved
into the party inventory (`AddItem` with merging and the "new" flag, possessor = the player, no
events); its own list is emptied. The creature's own gold field is not reset here (open question).
(high)

**Saving a party creature** (`CSWSCreature::SaveCreature` `0x00500610`) temporarily turns player
control off (`SetPlayerControlled(0, 1)`) so that `Gold` and `ItemList` come from the creature's
own (empty) purse and list, then turns it back on. A side effect: turning control off frees the
follow record (`+0x4c0`) and turning it on allocates a fresh one, so the saved `FollowInfo` is
always the default and the live follower's state restarts after every save or `SaveNPCState`.
(high for the calls, med for the consequence)

### 3.7 Solo mode, AI style, follow state

- **Solo mode** (`+0x190`): `SetSoloMode(b)` (`0x00565500`) stores it; turning it off from a script
  also turns stealth off for the PC and every member (`SetPartyStealthMode(0)` `0x00563c60`).
  Loading a party table with solo mode 0 does the same. It is switched off automatically when the
  last member is removed and whenever the party is placed after a transition (1.8); `AddPartyMember`
  may switch it on (3.5). What solo mode changes in play (followers stay, Tab disabled) is
  movement.md's and the GUI's. (high for the writes)
- **AI style** (`+0xe4`) is only stored and read by scripts here (`PT_AISTATE`). (high)
- **Follow state** (`+0xe8`) is reset to 0, and the client party table reset, when an area header
  is loaded (`0x00563a80`). (med)

### 3.8 Party selection

`ShowPartySelectionGUI(sExitScript, nForce1, nForce2)` opens `CSWGuiPartySelection` (gui.md: the
panel, its checks and messages). The panel reads, per slot, available / selectable / member from
the table and the NPC's name and level from `GetNPCObject` (spawning hidden creatures when needed).
**Apply** (`CSWGuiPartySelection::ApplyAndClose` `0x006be560`): (high unless marked)

1. Every slot that was a member and is no longer selected: client fade-out,
   `SetPlayerControlled(0, 1)`, `RemovePartyMember(n)` (the creature stays where it is).
2. Every newly selected slot: compute its formation point next to the leader (client party
   formation offset by the leader's facing, or `0x006348c0` when the leader's reference point is
   unset), `SpawnAvailableNPC(n, 1, …, bRevive = 1)`, snap to a free spot within 5 m; if the leader
   cannot reach that point by a straight walk (`0x004bcb70`), use the plain formation point instead
   and snap again; set position and the leader's facing; `AddPartyMember(n, creature)`;
   `ClearAllActions`, reset its path state, `SetPlayerControlled(1, 1)`, one `AIUpdate`; make the
   PC perceive it if it does not; client fade-in.
3. Re-send party state to the players (`0x004b6950`), close the panel and **run the exit script**
   (with no caller object) if one was given. (med for 3)

### 3.9 PARTYTABLE.res

`SavePartyTable(folder)` (`0x005648c0`) writes, in this order: `PT_GOLD` (DWORD), `PT_XP_POOL`
(INT), `PT_PLAYEDSECONDS` (DWORD, the total, 3.10), `PT_CONTROLLED_NPC` (INT), `PT_SOLOMODE`,
`PT_CHEAT_USED`, `PT_NUM_MEMBERS` (BYTEs), `PT_MEMBERS` (`PT_MEMBER_ID` INT, `PT_IS_LEADER` BYTE),
`PT_AVAIL_NPCS` (9 × `PT_NPC_AVAIL`, `PT_NPC_SELECT` BYTEs), `PT_AISTATE`, `PT_FOLLOWSTATE` (INT),
`GlxyMap` (`GlxyMapNumPnts` = 16, `GlxyMapPlntMsk`, `GlxyMapSelPnt`), `PT_PAZAAKCARDS` (1.9),
`PT_PAZSIDELIST` (10 INT), `PT_TUT_WND_SHOWN` (VOID 6), `PT_LAST_GUI_PNL`, `PT_FB_MSG_LIST`
(`PT_FB_MSG_MSG`, `_TYPE` DWORD, `_COLOR` BYTE), `PT_DLG_MSG_LIST` (`PT_DLG_MSG_SPKR`, `_MSG`),
`PT_COST_MULT_LIST` (one FLOAT per base item), then the journal (`SaveJournal` `0x00563d90`:
`JNL_SortOrder`, `JNL_Entries`), as `<folder>\PARTYTABLE`. (high)

`LoadPartyTable` (`0x00565d20`) resets the table, then reads the same fields with these
defaults: controlled NPC −1, member list truncated to the list's real length, at most 9 avail
entries, side cards 0, cost multipliers 1.0; the GUI logs are re-added through the in-game GUI. It
does **not** spawn anyone: membership is only data until `RestoreParty`. (high)

### 3.10 Time played

`TIMEPLAYED` / `PT_PLAYEDSECONDS` = `+0x114` + (now − session start) rounded to whole seconds
(`GetPlayedSeconds` `0x00563bf0`, wall clock via `GetSystemTimeAsFileTime`). Saving the party table
folds the session into `+0x114` and restarts the session clock (`0x007a3a20`/`0x007a3a24`); New Game
and loading also restart it (`0x00563cf0`). Pause and menus count: it is real time. (high)

## 4. Equipment

What happens when a creature puts an item on or takes it off: the 18 slots and where the
creature keeps them, the checks that decide whether an item fits (proficiency feats, race and
droid restrictions, use-limitation properties, the weapon-hand rules), the equip and unequip
sequences, and how an equipped item changes the creature: armour base defense, and the item
property → effect table. Boundaries: queueing the EQUIPITEM / UNEQUIPITEM actions (and the
combat-round variant) is [actions.md](actions.md); the equip *panel* (slot buttons, candidate
list, live preview) is [gui.md](gui.md) (`CSWGuiEquip`); what the effects then do, and how
bonuses of one item stack, is [rules.md](rules.md) (1.7, 1.12); the defense formula and the
properties read only at attack time (Keen, OnHit, Massive Criticals, Monster damage, DamageNone)
are [combat.md](combat.md) (4.3, 5, 6.1). Item offsets below are from the start of `CSWSItem`
(the `CSWSObject` part sits at `+0x10`, so the item's object id is `+0x14`).

### 4.1 Slots

**Slot numbers and masks.** Script slot *n* (`INVENTORY_SLOT_*`, 0..17, `NUM_INVENTORY_SLOTS`
= 18) is the mask `1 << n`; `GetItemInSlot` (routine 155, `0x0053a2c0`) and `ActionEquipItem`
(routine 32, `0x005355f0`, rejects n outside 0..17) convert with a floating `2^n`. Everything
inside the engine (the equip code, `baseitems.2da EquipableSlots`, the save file) uses the mask.
(high)

| n | Mask | Script name | Storage index in `CSWInventory` | Who uses it (baseitems `EquipableSlots`) |
|---|---|---|---|---|
| 0 | `0x00001` | HEAD | 0 (`+0x04`) | masks, droid sensors |
| 1 | `0x00002` | BODY | 1 (`+0x08`) | armour, robes, clothing, droid plating, Revan armour, disguises |
| 2 | `0x00004` | — | 2 (`+0x0c`) | nothing (NWN boots) |
| 3 | `0x00008` | HANDS | 3 (`+0x10`) | gauntlets; droid spike mounts (`0x208`) |
| 4 | `0x00010` | RIGHTWEAPON | 4 (`+0x14`) | every weapon |
| 5 | `0x00020` | LEFTWEAPON | 5 (`+0x18`) | one-handed weapons (`0x30`) |
| 6 | `0x00040` | — | 6 (`+0x1c`) | nothing (NWN cloak) |
| 7 | `0x00080` | LEFTARM | 7 (`+0x20`) | forearm bands, droid utility (`0x180`) |
| 8 | `0x00100` | RIGHTARM | 8 (`+0x24`) | same |
| 9 | `0x00200` | IMPLANT | 9 (`+0x28`) | implants; droid spike mounts |
| 10 | `0x00400` | BELT | 10 (`+0x2c`) | belts, droid shields, stealth units (`0x20400`) |
| 11–13 | `0x00800`–`0x02000` | — | **none** (lookup returns null) | nothing (NWN ammunition) |
| 14 | `0x04000` | CWEAPON_L | 11 (`+0x30`) | creature weapons (`0x1C030`) |
| 15 | `0x08000` | CWEAPON_R | 12 (`+0x34`) | creature weapons |
| 16 | `0x10000` | CWEAPON_B | 13 (`+0x38`) | creature weapons |
| 17 | `0x20000` | CARMOUR | 14 (`+0x3c`) | creature hide; stealth unit |

(high for the mask → storage mapping, read from the disassembly of `0x005a49c0`; high for the
2DA column, `baseitems.2da` probe)

**`CSWInventory`** (the equipped-items holder, NWN's `CNWSInventory`; 0x4c bytes at creature
`+0xa2c`, constructor `0x005a4930`, one-slot vtable `0x0074a824` holding the deleting destructor
`0x005a4c00`): a vtable and 18 dwords of item **object ids** from `+0x04`, all 0 after
construction; only indices 0–14 are reachable. (high)

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005a49c0` | `CSWInventory::GetSlotPointer(mask)` | mask → address of its id cell (table above); any other mask, 0x800–0x2000 included, → null | high |
| `0x005a4c20` | `CSWInventory::GetItemInSlot(mask)` | id cell → `CSWSItem*` (null when empty or the id is stale) | high |
| `0x005a4be0` | `CSWInventory::PutItemInSlot(mask, item)` | stores the item's id in the cell | high |
| `0x005a4950` | `CSWInventory::GetIsEquipped(item)` | 1 if the item's id is in any of the 18 cells | high |
| `0x005a4980` | `CSWInventory::GetSlotFromItem(item)` | `1 << index` of the cell holding the item, else 0 | high |
| `0x005a4ba0` | `CSWInventory::RemoveItem(item)` | sets the item's cell to `OBJECT_INVALID` | high |

Quirk: `GetSlotFromItem` returns `1 << storage index`, which is the true mask only for slots
0–10; a creature weapon in slot 14 comes back as 0x800, and so on. The engine only compares
its result with 0x10 / 0x20 and passes it to the property-removal handlers, where the
catch-all removal by creator (below) hides the error, so a reimplementation can return the true
mask. (high for the arithmetic, med for "harmless")

Correction to [objects.md](objects.md): creature `+0xa50` is **not** a list of equipped item ids;
it is the appearance block filled by `ReadStatsFromGff` (`0x005afce0`, which receives `+0xa50`
as an out parameter: appearance type at `+0xa60`, phenotype `+0xa62`, gender `+0xa63`, colours
`+0xa64..+0xa67`, head `+0xa68` ...); its first four dwords start as `OBJECT_INVALID` (meaning
not established). The equipment is the `CSWInventory` at `+0xa2c`. (high for "not equipment",
med for the field names)

**In saves.** `CSWSCreature::SaveCreature` (`0x00500610`) walks the masks 1, 2, 4 … 0x20000 and
writes one `Equip_ItemList` element per occupied slot whose **struct id is the slot mask**,
holding `ObjectId` and the full item. `ReadItemsFromGff` (`0x004ffda0`) takes the struct id
back as the slot. Checked in the shipped save: the PC's and Carth's armour are struct 0x2, their
blasters struct 0x10. (high)

**The equip panel** has nine slot buttons (`g_aEquipSlots` `0x00756560`: masks 0x20, 0x10, 0x1,
0x80, 0x100, 0x2, 0x8, 0x200, 0x400, with droid names Sensor / Special Weapon / Plating /
Utility / Shield); creature slots 14–17 are never shown. Details in [gui.md](gui.md). (high)

### 4.2 Equipping: `CSWSCreature::RunEquip(itemId, slotMask, bInstant)` (`0x00501de0`)

Called by the EQUIPITEM action handler (`0x00510fd0`) and the combat-round dispatcher
(`0x005b6210`, equips scheduled in a round). In order (high unless marked):

1. Find the item; fail if it doesn't exist. Find the **repository it comes from**: if the item's
   possessor (`+0x268`) is this creature, its inventory (`GetItemRepository(1)` `0x004ef770`,
   which is the party's shared repository for a player-controlled party member, 3.6 and 5.5); if
   the possessor is a container item held by this creature, that container's repository
   (`+0x26c`); otherwise the item must belong to another party member (or to a
   container one of them holds) and is taken from there; anything else fails. (med for the
   party-member branch)
2. **Validate** with `CanEquipItem(item, &slot, bFromPlayer = 1, bSkipLevel = 0, bFeedback = 1)`
   (below). The check may rewrite the slot (a left-hand request becomes right-hand). Its result
   selects the branch: 0 fail, 1 the slot is free, 2 swap with the occupant, 3 clear both hands.
3. Result **2**: take the occupant of the slot. If the new item's base item stacks
   (`Stacking` ≥ 2, which is every equipable base item except the creature items) and the
   occupant is identical (`CSWSItem::CompareItem` `0x00553cf0`: same base item, upgrades,
   property lists, plot flag, charges, stolen flag, model/body/texture variation, tag and name),
   fail: nothing would change. Otherwise unequip the occupant (`UnequipItem`, below) and put it in
   the creature's repository; if that repository refuses it (full), remove it from the creature
   (`RemoveItem` `0x00510ef0`) and drop it in the area at the creature's position, z + 0.2
   (`0x00555720`).
   Result **3**: do the same for the right-hand item and then the left-hand item (each only if
   present), then equip in the right hand.
4. If the item is a stack (`+0x28c` > 1), split one off (`SplitItem` `0x0055f280`) and equip
   that copy; the rest stays in the repository.
5. Remove the item from its repository if it is listed there; make this creature its possessor
   (`0x00553210`).
6. `EquipItem(slot, item, bApplyProperties = 1, bLoading = 0, …)` (next section).
7. Remember the instant flag per hand: `+0xaac` for 0x10, `+0xaa8` for 0x20 (`0x004efe00`;
   meaning not traced, low).
8. **Combat mode check** (`+0x4d2`, the attack-mode byte also written by the counter action):
   mode 5 survives only with both hands empty; mode 6 only with a ranged right-hand weapon;
   modes 1, 2 and 3 only with an empty or melee right hand; other modes are not checked. A mode
   that no longer fits is reset to 0 (`SetCombatMode` `0x0050ee80`). (high for the tests, low
   for what the numbered modes are)
9. On any failure the client is told to drop its "pending equip" icon (`0x0056fbd0`).

### 4.3 Validation: `CSWSCreature::CanEquipItem(item, &slot, bFromPlayer, bSkipLevel, bFeedback)` (`0x0051aa60`)

Callers: `RunEquip` (1, 0, 1), `ReadItemsFromGff` when loading (1, 1, 1), the
`ActionEquipMost*` helpers (`0x00500e50`, `0x00501250`, `0x004f3a60`), the level-up code
(`0x005ab1e0`) and the GUI (`CSWGuiEquip::OnSlotHilighted` `0x006b9470` with 0, 0, 0, and two
upgrade-screen functions `0x006c5e90`, `0x006c6500`). The checks, in order; a failure returns 0
and, when the flags allow, sends a numbered feedback message (`SendFeedbackMessage` `0x004ede10`;
strrefs from the client formatter `0x005fcd10`): (high)

| # | Check | Address | Fails when | Feedback |
|---|---|---|---|---|
| 1 | item level | `GetItemLevel` `0x00554080` | bFromPlayer, the creature is a PC (stats `+0x6c`), not bSkipLevel, the server option "item level restriction" (server options `+0xc8`, set to 1 by `0x004b1b00`) is on, and the creature's total level < the item's level | 0x62 → 1470 "You have not achieved the required level to equip this item." |
| 2 | NonEquippable | item flags `+0x288` bit 0x40 | set (UTI `NonEquippable`, `SetItemNonEquippable` routine 266) | none |
| 3 | proficiency | `CheckProficiencies` `0x00510e30` | the base item has `EquipableSlots` 0, or the creature lacks any of the base item's `ReqFeat0..4` (unless it has feat 93 PROFICIENCY_ALL) | none here (the GUI marks the row) |
| 4 | alignment limit | `CheckUseLimitationAlignment` `0x005145a0` | the item has an active property 43 and its subtype ≠ the creature's alignment group (`GetAlignmentGroup` `0x005a5110`: GoodEvil ≤ 40 → 3 dark, ≥ 60 → 2 light, else 1 neutral); feat 93 bypasses | 0xcf → 1512 "…required alignment…" |
| 5 | class limit | `CheckUseLimitationClass` `0x00518210` | the item has property 44 and none of the creature's classes equals a property subtype; feat 93 bypasses | 0xd0 → 1513 "…required class…" |
| 6 | race / droid | `CheckUseLimitationRace` `0x005182f0` | `DroidOrHuman` 1 and race ≠ 6 (Human), or 2 and race ≠ 5 (Droid) — skipped when the item has a cast-spell property with spell 129 (`ITEM_ABILITY_RECOVERY_STIM`); **or** the creature's subrace bit (`1 << SubraceIndex`) is set in `DenySubrace`; **or** the item has property 45 and no 45 subtype equals the creature's race | 0xd1 → 1514 "You are not the correct race…" |
| 7 | feat limit | `CheckUseLimitationFeat` `0x00514650` | the item has property 57 and the creature lacks one of the named feats; feat 93 bypasses | 0x6b (empty string) |
| 8 | slot | weapon slots: `CanEquipWeapon` `0x00510cd0`; others: `CanEquipInSlot` `0x00515860` | see below | 0x7b → 1478 "Equipped item swapped out." (when the slot is occupied, as information) |
| 9 | slot fits the item | base item `EquipableSlots & slot` | zero for the (possibly rewritten) slot | none |

"The item has property *p*" means a property of that type that is active under the upgrade rule
(below); use-limitation properties live in the passive list. The subtype of property 43 is an
`iprp_aligngrp` row (1 Neutral, 2 Light Side, 3 Dark Side). (high)

What this means with the shipped `baseitems.2da` (data, high): melee weapons need feat 44
(melee proficiency), lightsabers 43, pistols 39, rifles 40, heavy weapons 42; armour classes 4–5
need 5 (light), 6–7 need 6 and 5, 8–9 need 4, 5 and 6; Jedi robes need 55 (Jedi Defense);
implants need 14 / 15 / 16; masks, gauntlets, bands, belts and droid items need nothing.
`DroidOrHuman` is 1 for melee weapons, armour, clothing and humanoid accessories, 2 for droid
items, 0 for blasters, so droids can use blasters but no melee weapon or armour; every armour,
robe, clothing and disguise row has `DenySubrace` 0x2, so a Wookiee (subrace 1) can wear none.
Shipped clothing (`g_a_clothes01` …) also carries property 45 subtype 6 (Human only).

**Weapon hands** (`CanEquipWeapon`, slot 0x10 or 0x20; R = right-hand item, L = left-hand item,
N = new item; "two-handed" = `WeaponWield` 3, 5 or 6 (`IsTwoHanded` `0x005b3150`), "one-handed"
= 1, 2 or 4 (`IsOneHanded` `0x005b3170`); "ranged" = `RangedWeapon`): (high)

| State | New item | Result |
|---|---|---|
| R empty, L empty | any | 1; a 0x20 request becomes 0x10 (a weapon always goes to the right hand first) |
| R empty, L held | any | 0 (not reachable in normal play) |
| R held, L empty | N two-handed | 3, slot 0x10: both hands are cleared, N goes right |
| R held, L empty | N not two-handed, R one-handed and R/N both ranged or both melee | 2 for a 0x10 request (swap R), 1 for a 0x20 request (dual wield) |
| R held, L empty | otherwise | 2, slot 0x10 (swap R) |
| R held, L held | N two-handed, or R/N differ in ranged-ness | 3, slot 0x10 |
| R held, L held | otherwise | 2 on the requested hand |

So dual wielding needs a one-handed right weapon and a left weapon of the same family (both
melee or both ranged); nothing checks the left item's own wield type beyond "not two-handed",
and no feat is required (two-weapon feats only change the penalties, [combat.md](combat.md)).
The GUI uses a different rule for the left slot (it refuses while the right weapon has
`WeaponSize` 4, which also catches the one-handed Gamorrean battleaxe) — see
[gui.md](gui.md). (high for both rules; the mismatch is a fact of the original)

**Other slots** (`CanEquipInSlot`): proficiency again (feedback 0x77 → 1475 "You do not have the
proficiencies required to equip that item." — unreachable through `CanEquipItem`, which already
failed silently at step 3), then 2 if the slot is occupied (swap), else 1. (high)

**The level check is dead in practice**: `GetItemLevel` returns 1 + the first row of
`itemvalue.2da` whose `MAXSINGLEITEMVALUE` is ≥ the item's cost (plot items: level 1), and
every row of the shipped table is 13,500,000. (high for the code, high for the data)

**`CSWSCreature::CanUseItem(item)` (`0x0051b440`)**, used by the inventory screen's filters
(`0x006b2c90`), item use (`0x0056ee40`) and the party code (`0x00566f20`): checks 4–7 and the
level check as above, plus a size rule absent from `CanEquipItem` (a weapon whose `WeaponSize`
exceeds the creature's size, `+0x4f8`, by more than 1 is unusable; never true for medium
creatures with the shipped sizes ≤ 4), and the proficiency check only for items that fit some
slot. (high)

**Armour in combat**: `AddEquipItemActions` (`0x004f0420`) and `AddUnequipActions`
(`0x004f06d0`) refuse a **body-slot** (0x2) change while the creature is in combat because it is
being attacked (`+0x4e0` = 1 and `+0xac0` = 1): feedback 0xc1 → 1506 "You cannot equip or
unequip armor during combat!" and 0xc2 → 1507 "You cannot unequip armor during combat!". (These
are armour-only; [actions.md](actions.md) describes 0xc1 as a weapon-slot message, which it is
not.) An equip request for an item already equipped in slot 0x1, 0x2, 0x10 or 0x20 is ignored.
(high)

### 4.4 `CSWSCreature::EquipItem(slot, item, bApplyProperties, bLoading, bQuiet)` (`0x004feb90`) and `UnequipItem(item)` (`0x004faa70`)

The low-level pair every path goes through (`RunEquip`, `RunUnequip`, loading, the default
clothes, the GUI preview). **EquipItem**, in order (high):

1. If the item is already in some slot, `UnequipItem` it first.
2. If bApplyProperties: `CSWSItem::ApplyItemProperties(creature, slot, bLoading)` (`0x00553bb0`,
   below).
3. Store the item's id in the slot.
4. `UpdateBaseArmorAC` (`0x004ece80`): stats `+0xf6` (the armour base of the defense formula,
   [combat.md](combat.md) 5) = `BaseAC` of the body-slot item's base item, or 0 when the body
   slot is empty. This runs on every equip and unequip, whatever the slot.
5. `CSWSCreatureStats::UpdateCombatInformation` (`0x005addc0`): rebuilds the character-sheet
   combat block (stats `+0x118`, saved as `CombatInfo`: attacks, per-hand attack and damage
   modifiers, weapon names and dice, crit ranges). (med)
6. For a weapon slot (0x10 / 0x20), unless bLoading or bQuiet or the in-game menus are open
   (in-game GUI `+0xb4`): put the creature in combat state (`SetCombatState(1, 2)` `0x004f2610`),
   i.e. a script that hands a weapon to a creature makes it combat-ready. (med for the reading)
7. Add the item's weight (`GetWeight` `0x005562a0`: weight × stack size, or own weight plus
   contents for a container) to the creature's equipped weight `+0xa3c`.
8. Signal script event 38 (EQUIP_ITEM) to the **module**, object 0 = the item, caller = the
   creature: the module's `Mod_OnEquipItem` script runs next frame; `GetLastItemEquipped`
   (routine 52, `0x0053f800`) reads it. This happens on load too.

**UnequipItem**, in order (high): `RemoveItemProperties(creature)` (`0x00553c30`: the removal
handler of every active passive property, then `RemoveEffectsByCreator(item id)` `0x004d0820`,
which drops every remaining effect whose creator is the item); clear the slot cell;
`UpdateBaseArmorAC`; set the creature's "recompute" flag `+0x344`; subtract the weight from
`+0xa3c`; if the base item's `ItemType` is 44 (stealth unit) and the creature is in stealth
mode (`+0x4d1` = 1), leave stealth (`0x004f2a50`). Note that `UnequipItem` does **not** call
`UpdateCombatInformation` and sends no event; the next equip or the recompute flag does. (high
for the steps, med for the recompute flag's effect)

### 4.5 Unequipping: `CSWSCreature::RunUnequip(itemId, containerId, nAddFlags, ppItem, bInstant)` (`0x005023a0`)

Called by the UNEQUIPITEM action (`0x00513ec0`), the round dispatcher and `RemoveItem`
(`0x00510ef0`). (high unless marked)

1. Fail unless the item exists, this creature possesses it and it is equipped.
2. Target repository: the creature's (`GetItemRepository(1)`, the party repository for party
   members) when containerId is `OBJECT_INVALID`, else that container item's repository (the
   container must also belong to the creature).
3. `CanUnequipWeapon` (`0x00513e30`): 2 when the item is the right-hand weapon and a left-hand
   weapon is held (whose `WeaponType` ≠ 0); else 1.
4. Store the instant flag (as in equip), `UnequipItem`, add the item to the target repository;
   if refused, drop it at the creature's feet (z + 0.2).
5. Result 2 only: **the left-hand weapon moves to the right hand** (unequip it, `EquipItem(0x10,
   left, 1, 0, 0)`).
6. Make the target the possessor; tell the client (`0x0056fd10`, once per moved item); return
   the item through ppItem.

### 4.6 Item properties → effects

**Storage** (`CSWSItem::LoadDataFromGff` `0x0055fcd0`). Each UTI `PropertiesList` entry becomes a
0x1c-byte record: `+0x00` PropertyName (word), `+0x02` Subtype (word), `+0x04` CostTable (byte),
`+0x06` CostValue (word), `+0x08` Param1, `+0x09` Param1Value, `+0x0a` ChanceAppear (bytes),
`+0x0c` Useable (dword), `+0x10` UsesPerDay (byte, default 0xff), `+0x11` UpgradeType (byte,
default 0xff). The records are split into two arrays (high):

- **usable** ("active"; `+0x248` count, `+0x250` array; `GetActiveProperty` `0x00553960`): property types
  10 CastSpell (activate item), 37 security spike (ThievesTools), 46 Trap, 53 Computer spike —
  the "use this item" properties (`IsUsablePropertyType` `0x00553900`). They are never applied on
  equip. On load, a cast-spell property whose UsesPerDay is unset gets uses from its CostValue
  (`iprp_chargecost` rows 8–12 → 1–5 uses per day, `0x00555bf0`).
- **passive** (`+0x24c` count, `+0x254` array; `GetPassiveProperty` `0x00553990`): everything
  else; these are what equipping applies.

An item with no property at all is marked identified (`+0x288` bit 0). The item's own AC
(`+0x244`) is its base item's `BaseAC` when `ModelType` is 1 (armour), else 0 (used only by
`GetItemACValue`, routine 401 `0x0053a130`, which adds the CostValue of every passive property 1).

**Upgrade gating.** A property whose UpgradeType is not 0xff counts only while bit
`1 << UpgradeType` is set in the item's `Upgrades` mask (`+0x294`). This rule is applied by
`ApplyItemProperties`, `RemoveItemProperties`, `HasProperty` (`0x00555c90`) and
`GetPropertyByType` (`0x005539c0`). Shipped data: 61 of 1,055 UTIs carry gated properties
(upgrade types 0–24); the Endar Spire Jedi's lightsaber in the save has 29 properties, all gated,
and `Upgrades` 0, so none applies. How upgrades set the bits: 5.11. (high)

**Apply.** `ApplyItemProperties(creature, slot, bLoading)` (`0x00553bb0`) sends every passive property
that passes the upgrade rule to the AI master's item property handler (`CServerAIMaster+0x5c`,
`CSWSItemPropertyHandler`, vtable `0x00744284`): `OnItemPropertyApplied(item, property, creature,
slot, bLoading)` (`0x004e5410`) indexes a 60-entry apply table (and `OnItemPropertyRemoved`
`0x004e5450` a remove table), both filled by `InitializeItemProperties` (`0x004ea9f0`); a type
≥ 60 or an empty entry does nothing. Every handler builds ordinary `CGameEffect`s (rules.md 1.1)
with (high):

- duration type **3** ("equipped") in the low bits of the subtype word, the other subtype bits
  left at 0 as the constructor (`0x00503e40`) set them;
- creator = the item (`SetCreator` `0x00503a00`);
- `ApplyEffect(creature, effect, bLoading)` (`0x004d14f0`).

The value usually comes from a cost table: column `Value` (or `Amount`) of an `iprp_*` table at
row CostValue. "Bonus table" below is `iprp_bonuscost` (cost table row 1: value = row 1..10),
"melee table" `iprp_meleecost` (row 2: 1..5), "neg5" `iprp_neg5cost` (row 20: −1..−5, negated
by the handler), "neg10" `iprp_neg10cost` (row 21). The handlers pick the table themselves; the
property's own CostTable byte is used only by DamageImmunity.

**Hand.** Attack and damage effects carry the hand the slot implies (attack: int1, damage:
int5): 0x10 → 1 (on-hand), 0x20 → 2 (off-hand), 0x4000 / 0x8000 / 0x10000 → 3 / 4 / 5
(creature weapons), 0x8 (gauntlets) → 7 (unarmed); any other slot leaves 0, "misc", which
applies to every attack ([rules.md](rules.md) 1.7). When the item's base item has `WeaponWield`
3 (double-bladed weapons and staves), the attack/damage handlers apply a **second copy with hand
2**, so both ends get the bonus. "Race any" below is the rules' "invalid racial type" byte
(`g_pRules+0xaa`). (high)

| Prop | Name | Apply / remove | Effect(s) created | Conf. |
|---|---|---|---|---|
| 0 | Ability | `0x004e6390` / `0x004e8db0` | 0x24 ability increase: int0 = ability (subtype 0–5, STR..CHA), int1 = bonus table | high |
| 1–4 | Armor (+ vs alignment group / damage type / race) | `0x004e6510` / `0x004e8f70` | 0x30 AC increase: int0 = base item `AC_Enchant` (0 dodge for every shipped row), int1 = bonus table, int2 = race any, int5 = 0x4007 (all damage); prop 2: int4 = alignment group (subtype 1–3); prop 3: int5 = subtype; prop 4: int2 = subtype | high |
| 5–7 | Enhancement (+ vs alignment group / race) | `0x004e5490` / `0x004e7f40` | 0x0a attack increase (int0 = melee table, int1 = hand, int2 = race any) **and** 0x0d damage increase (int0 = same value, int1 = base item `DamageFlags` (8 when 0), int5 = hand, int2 = race any); vs alignment: subtype 1 → int3 = 1, 2/3 → int4 = 2/3; vs race: int2 = subtype | high |
| 8 | AttackPenalty | `0x004e60c0` / `0x004e8bc0` | 0x0b attack decrease: int0 = −neg5, int1 = hand, int2 = race any | high |
| 9 | BonusFeats | `0x004e6d50` / `0x004e9700` | 0x53 (bonus feat): int0 = feat (subtype); only on creatures with stats | high |
| 11–13 | Damage (+ vs alignment group / race) | `0x004e5c60` / `0x004e86f0` | 0x0d damage increase: int0 = **CostValue itself** (an `iprp_damagecost` row: 1–5 flat, 6+ dice, the script `DAMAGE_BONUS_*` numbering), int1 = `1 << subtype` (prop 11) or `1 << Param1Value` (12, 13), int5 = hand; alignment / race as for enhancement | high |
| 14 | DamageImmunity | `0x004e6e20` / `0x004e97a0` | 0x10 damage immunity increase: int0 = `1 << subtype`, int1 = the property's own cost table (`iprp_immuncost`: 5–100 %) | high |
| 15 | DamagePenalty | `0x004e6f60` / `0x004e9990` | 0x0e damage decrease: int0 = −neg5, int1 = weapon damage flags, int5 = hand | high |
| 16 | DamageReduced | `0x004e7190` / `0x004e9bb0` | 0x0c damage reduction: int0 = `iprp_soakcost Amount`, int1 = subtype + 1 (the "+N" it ignores) | high |
| 17 | DamageResist | `0x004e72b0` / `0x004e9cf0` | 0x02 damage resistance: int0 = `1 << subtype`, int1 = `iprp_resistcost Amount` | high |
| 18 | Damage_Vulnerability | `0x004e73d0` / `0x004e9e30` | 0x11 damage immunity decrease: int0 = `1 << subtype`, int1 = `iprp_damvulcost Value` | high |
| 19 | DecreaseAbilityScore | `0x004e74f0` / `0x004e9f60` | 0x25 ability decrease: int0 = ability, int1 = −neg10 | high |
| 20 | DecreaseAC | `0x004e7670` / `0x004ea130` | 0x31 AC decrease: int0 = subtype (AC type, `iprp_acmodtype`), int1 = −neg5, int2 = race any, int5 = 0x4007 | high |
| 21 | DecreasedSkill | `0x004e77c0` / `0x004ea290` | 0x38 skill decrease: int0 = skill, int1 = −neg10, int2 = race any | high |
| 24 | Immunity | `0x004e7900` / `0x004ea3f0` | 0x16 immunity: int0 from the subtype (`iprp_immunity` → `IMMUNITY_TYPE_*`): 0 backstab → 30 sneak attack, 1 level/ability drain → 29 negative level **and** 19 ability decrease (two effects), 2 mind → 1, 3 poison → 2, 4 disease → 3, 5 fear → 4, 6 knockdown → 28, 7 paralysis → 6, 8 critical hits → 31, 9 death → 32; int1 = race any | high |
| 25 | ImprovedMagicResist | `0x004e66b0` / `0x004e9110` | 0x21 Force resistance increase: int0 = `iprp_srcost Value` (10–40) | high |
| 26, 27 | ImprovedSavingThrows (vs element) / Specific | `0x004e9230` / `0x004ea890` | through `ApplySavingThrowEffect` (`0x004e67d0`): 0x1a save increase (0x1b decrease if the value is negative, with its absolute value): int0 = bonus table, int1 = subtype 1/2/3 → Fort/Reflex/Will (else 0 = all), int2 = 0, int3 = race any | high |
| 29 | Light | `0x004e62d0` / (empty) | 0x36 light: int0 = 5000 | med |
| 33, 34 | ReducedSavingThrows / Specific | `0x004e92e0` / `0x004ea940` | as 26/27 with the neg5 value (→ 0x1b decrease) | high |
| 35 | Regeneration | `0x004e7c00` / `0x004ea650` | 0x07 regenerate: int0 = CostValue (HP per tick), int1 = 6000 ms, int4 = 35 | high |
| 36 | Skill | `0x004e7b10` / `0x004ea580` | 0x37 skill increase: int0 = skill (subtype), int1 = CostValue, int2 = race any | high |
| 38–40 | AttackBonus (+ vs alignment group / race) | `0x004e5e80` / `0x004e8950` | 0x0a attack increase: int0 = melee table, int1 = hand, int2 = race any; alignment / race as for enhancement | high |
| 47 | True_Seeing | `0x004e6a30` / `0x004e95a0` | 0x48 true seeing | high |
| 50 | Freedom_of_Movement | `0x004e6ad0` / `0x004e9620` | four 0x16 immunities: 6 paralysis, 9 slow, 10 entangle, 24 movement speed decrease | high |
| 52 | Special_Walk | `0x004e68e0` / `0x004e94b0` | 0x3a walk animation (int0 = subtype, `iprp_walk`) and 0x3b limit movement speed | high |
| 54 | Regeneration_Force_Points | `0x004e7c00` / `0x004ea650` | as 35 with int4 = 54 (Force points) | high |
| 55, 56 | Blaster bolt deflect increase / decrease | `0x004e7ce0` / `0x004ea6e0`, `0x004e7db0` / `0x004ea770` | 0x5c / 0x5d: int0 = subtype, int1 = CostValue | high |
| 59 | Disguise | `0x004e7e80` / `0x004ea800` | 0x3e disguise: int0 = subtype (appearance row), int1 = 0 | high |

**No handler** (equipping does nothing for them): 10, 37, 46, 53 (usable); 22, 23 (extra melee /
ranged damage type), 28 Keen, 30 Mighty, 31 DamageNone, 32 OnHit, 42 UnlimitedAmmo, 48
OnMonsterHit, 49 Massive_Criticals, 51 Monster_damage (the ones combat reads off the weapon at
attack time, [combat.md](combat.md)); 41 ToHitPenalty; 43–45, 57 (use limitations, checked at
equip); 58 Droid_Repair_Kit. Shipped usage of the unhandled ones: 28 ×47, 32 ×107, 49 ×36, 51
×33, 22 ×1, 31 ×5; 41 is never used. (high for the table, high for the counts from a probe of all
UTIs)

Quirks a faithful port keeps or decides about (all high, read in the handlers):

- The table entry for 8 is filled twice: first with `0x004e58c0` / `0x004e83a0` (attack **and**
  damage decrease, an "enhancement penalty"), then overwritten with the attack-only pair; the
  first pair is unreachable.
- "Versus Neutral" (alignment subtype 1) on enhancement, damage and attack properties is stored
  in int3, not int4, so the filter of [rules.md](rules.md) 1.7 (which reads int4) never applies
  it: such a bonus counts against everyone. The AC variant uses int4 for all three groups.
- ImprovedSavingThrows (26) has an `iprp_saveelement` subtype (vs acid, cold …) but the shared
  handler reads it as a save type: subtypes 1–3 become Fortitude/Reflex/Will, others "all saves".
  One shipped item uses 26 (`g_band`, subtype 15: all saves).
- The Damage family (11–13) passes CostValue straight through as the damage-bonus constant;
  the effect resolves it against `iprp_damagecost` (1–5 flat, 6 = 1d4, 7 = 1d6, 8 = 1d8,
  9 = 1d10, 10 = 2d6 …).

**Remove.** The remove handlers (two read in detail: `0x004e8f70`, `0x004e7f40`) look for the
creature's equipped-duration effect of the matching type whose creator is the item and whose
parameters match, and remove it by id (`RemoveEffectById` `0x004d06c0`); afterwards
`RemoveItemProperties` removes every leftover effect created by the item. A reimplementation
can simply **remove every effect whose creator is the item** on unequip. (high)

**Loading.** Equipped-duration effects are not restored from a save: `CSWSObject::LoadEffectList`
(`0x004d1be0`) discards every saved effect with `SkipOnLoad` = 1 or duration type 3, and the
equip during `ReadItemsFromGff` (bApplyProperties = 1, bLoading = 1) re-creates them. The shipped
save stores them anyway (16 such effects on the Endar Spire GIT's Sith, `SkipOnLoad` 0). (high)

### 4.7 Armour and weapons, summarised

- **Armour defense**: stats `+0xf6` = body item's base item `BaseAC` (`UpdateBaseArmorAC`); the
  DEX cap is the body armour's `DEXBONUS` read by the defense code; Armor properties add dodge AC
  effects (capped with other dodge at 10 by the defense formula); all in
  [combat.md](combat.md) 5. Shield base `+0xf7` is not written by the equip code (low: no
  writer found here).
- **Weapon damage** is the base item's `NumDice`d`DieToRoll`; enhancement and attack-bonus
  properties become attack/damage effects for that hand; everything else about the roll is
  [combat.md](combat.md) 4–6.
- `UpdateCombatInformation` keeps the sheet numbers in step; the equip panel shows them
  ([gui.md](gui.md)).
- Encumbrance: `+0xa3c` sums the equipped items' weight (`TenthLBS`); no reader that limits
  movement was found (low).

### 4.8 Loading equipment and the default clothes

`ReadItemsFromGff` (`0x004ffda0`), for each `Equip_ItemList` element: create or find the item
(full struct in a save, `EquippedRes` template plus `Dropable` from a blueprint), make the
creature its possessor, run `CanEquipItem(item, &mask, 1, 1, 1)` (level check skipped), and if
it passes `EquipItem(mask, item, 1, 1, 0)`; if it fails the item goes into the creature's
repository instead, and when the failed slot was the body, flag `+0xab8`. Later, when the party
is restored (`0x00565620`, `0x00565760`), `EquipDefaultClothes` (`0x00501c40`) sees the flag
and equips `g_a_clothes01` (from the repository, or a new one marked droppable) in the body
slot, so a character who can no longer wear the saved armour isn't left bare. (high)

### 4.9 On the client

The server tells the client about each change (`0x0056fbd0` refused equip, `0x0056fd10` /
`0x0056fd80` unequip done / refused). The client rebuilds the body from `appearance.2da` of the
creature's appearance row: model column `model<L>` and texture column `tex<L>` where L is
`'A' + BodyVar − 1` (base item `BodyVar`, letters A–J, clamped to 1–10, A without armour),
and the texture name gets the item's `TextureVar` as two digits, falling back when that
texture doesn't exist (`CSWCCreatureAppearance::CreateBTypeBody` → `0x00697610`). Item models
and icons are named from the base item's `ItemClass` and the item's `ModelVariation`:
`<ItemClass>_<nnn>` and `i<ItemClass>_<nnn>`, with a gender letter inserted when
`GenderSpecific` is set (`0x005b30e0`, `0x005b3050`). (med; the client side was not traced
beyond these functions)

## 5. Inventory, stores and containers

Where items live (a creature's own inventory, the party's shared inventory, placeable containers,
stores), how they move between holders, how stacks merge and split, what a store charges, and how
the upgrade bench changes a weapon or armour. Boundaries: the PICKUPITEM / DROPITEM / GIVEITEM /
TAKEITEM / EQUIP / UNEQUIP *actions* (walking into range, queuing) are [actions.md](actions.md)'s;
the panels' layouts are [gui.md](gui.md)'s; what an item property does once equipped (the effects)
is rules.md's, and equipping is section 4. Offsets on items are
from the start of the `CSWSItem` object (the pointer `GetItemByGameObjectID` returns, which is the
`CSWItem` base; the `CSWSObject` sub-object sits at `+0x10`, see [objects.md](objects.md)).

### 5.1 The item object, inventory-relevant fields

From `CSWSItem::LoadDataFromGff` (`0x0055fcd0`), `SaveItem` (`0x0055ccd0`) and the constructor
(`0x005530a0`). (high unless marked)

| Offset | Field | GFF label / source | Default |
|---|---|---|---|
| `+0x0c` | base item (row of `baseitems.2da`) | `BaseItem` | |
| `+0x14` | object id (`CSWSObject` `+4`) | | |
| `+0x28` | tag, stored lower-case | `Tag` | |
| `+0x108` | plot flag (`CSWSObject` `+0xf8`) | `Plot` | 0 |
| `+0x238..+0x240` | per-usable-property "uses left" cache sent to the client (`0x0055d040`) | — | 0 |
| `+0x244` | base AC: `baseitems.BaseAC` when the row's `ModelType` is 1, else 0 | — | 0 |
| `+0x248` / `+0x250` | count / array of **usable** properties (0x1c bytes each) | `PropertiesList` | none |
| `+0x24c` / `+0x254` | count / array of **passive** properties | `PropertiesList` | none |
| `+0x258` | charges | `Charges` | 50 |
| `+0x25c` | maximum charges | `MaxCharges` (default: the charges read) | |
| `+0x260` | **value** used for prices | `AddCost` | 0 |
| `+0x264` / `+0x265` / `+0x266` | model variation / body variation / texture variation | `ModelVariation` (falls back to `ModelPart1`, 0 → 1), `BodyVariation` (from `baseitems.BodyVar` for `ModelType` 1), `TextureVar` | 1 / 0 / 0 |
| `+0x268` | possessor id (`OBJECT_INVALID` on the ground) | — | invalid |
| `+0x26c` | the item's own `CItemRepository*` when `baseitems.Container` ≠ 0 (no KOTOR row sets it: dead path) | `ItemList` | null |
| `+0x270` / `+0x278` / `+0x280` | identified description / description / name | `DescIdentified` / `Description` / `LocalizedName` | |
| `+0x288` | flag bits: 0 identified, 2 infinite (store stock), 3 droppable, 4 pickpocketable, 5 stolen, 6 non-equippable, 7 new (unseen), 8 deleting | `Identified`, `Infinite` (store lists), `Dropable`, `Pickpocketable`, `Stolen`, `NonEquippable`, `NewItem`, `DELETING` | 3 and 4 set |
| `+0x28c` | stack size | `StackSize` | 1 |
| `+0x290` | weight, tenths of a pound (`baseitems.TenthLBS`) | — | |
| `+0x294` | **installed upgrades**: bit *n* = row *n* of `upgrade.2da` | `Upgrades` | 0 |
| `+0x298` | inventory-iteration cursor (container items) | — | |

Property record (0x1c bytes): `+0` PropertyName (u16), `+2` Subtype (u16), `+4` CostTable (u8),
`+6` CostValue (u16), `+8` Param1, `+9` Param1Value, `+0xa` ChanceAppear (u8 each), `+0xc` Useable
(default 1 in the usable list, 0 in the passive list), `+0x10` UsesPerDay (default 255 = unset),
`+0x11` **UpgradeType** (default 255 = a native property). (high)

The loader splits `PropertiesList` in two by `PropertyName` (`IsUsablePropertyType` `0x00553900`):
**10 CastSpell, 37 ThievesTools, 46 Trap, 53 Computer_Spike** go to the usable list, everything
else to the passive list, each list keeping file order. (high)

Load quirks an implementer must copy (high):

- The item's value is `AddCost`. The UTI's `Cost` field is **never read**; the writer stores the
  computed value (below) under `Cost` and the raw `AddCost` separately. In the shipped UTIs
  `Cost` = `AddCost` in 681 of 810 files and 303 have `AddCost` 0.
- An item with no properties at all is marked identified. The writer always writes
  `Identified` = 1. Identification plays no role in KOTOR.
- For CastSpell properties whose `UsesPerDay` is unset (255), `CostValue` 8..12
  (`iprp_chargecost` "1..5 Uses/Day") sets `UsesPerDay` to 1..5 and `Useable` to 1
  (`CSWSItem::InitUsesPerDay` `0x00555bf0`). (high)
- The tag is registered in the module's tag table, like every object.

Copy and split: `CSWSItem::CopyItem(src)` (`0x0055d950`) copies names, tag, possessor, both
property arrays, value, charges, base AC, infinite and identified bits, stack, weight, upgrades,
variations, non-equippable, base item and the six bytes at `+4..+9`; it refuses a container item
that holds anything. `CSWSItem::SplitItem(n)` (`0x0055f280`), for 0 < n < stack: a new item copied
from this one with stack n, this stack reduced by n. (high)

### 5.2 CItemRepository: the item list of a holder

`CItemRepository` (0x18 bytes, constructor `0x0055d290(parent id, sorted flag)`) is a growable
array of **item object ids**: (high)

| Offset | Meaning |
|---|---|
| `+0x00` | parent object id (the holder; for the party inventory, the PC's id) |
| `+0x04` | number of items carrying the "new" flag (bit 7) |
| `+0x08` | bit 0: keep the list **sorted** |
| `+0x0c` / `+0x10` / `+0x14` | id array / count / capacity (capacity grows 16, then doubles) |

Owners: creature `+0xa30` (unsorted), placeable `+0x36c` (unsorted), store `+0x230` (unsorted),
container item `+0x26c` (unsorted), and the party table `+0x118` (**sorted**, created on first use
by `CSWPartyTable::GetPartyInventory` `0x00563340`). There is **no capacity limit and no weight
limit** anywhere in the add path. (high)

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x0055d330` | `AddItem(ppItem, bMerge, bSignal, bMarkNew)` | the add algorithm below; `*ppItem` may change (merged into an existing stack) or become null (credits, pazaak cards) | high |
| `0x0055d2c0` | `InsertItemAt(item, i)` | unsorted lists only: insert at i, or append when i is out of range | high |
| `0x00555fd0` | `RemoveItem(item)` | removes the id (shifting the rest down); clears the item's "new" flag and the counter | high |
| `0x005560b0` / `0x005560e0` | `GetItemAt(i)` / `GetItemIdAt(i)` | indexed access | high |
| `0x00555ed0` | `FindItemWithTag(tag)` | first item whose tag equals, searching container items recursively; id or invalid | high |
| `0x00555e00` | `FindItemWithItemType(type, n)` | the n-th item whose `baseitems.ItemType` matches, recursively | high |
| `0x00555f40` | `ContainsItem(item, bRecurse)` | | high |
| `0x0055f330` | `Clear` | count and new-count to 0, items untouched | high |
| `0x00555de0` | `FreeList` | frees the id array (destructors) | high |
| `0x00556150` | `SetParent(id)` | re-points every item's possessor, no events | high |
| `0x00556100` | `GetContentsWeight` | sum of item weights × stack | med |

**`AddItem`, in order** (`0x0055d330`, high):

1. **Special item types**, when the holder is a creature (or a container item held by a
   creature): `baseitems.ItemType` 23 (credits, base item 57) → the creature gains gold equal to
   the stack size (`AddGold(n, feedback)`), the item object is deleted and `*ppItem` becomes null;
   `ItemType` 42 (pazaak card, base item 86) → `AddPazaakCard` (below), item deleted.
2. **Insert position** (sorted lists only): the first index whose item has a larger base item
   number, or the same base item and a name that sorts after the new item's name (localized name
   in the current language). The real save's `INVENTORY.res` is in this order (base items 2, 4,
   25, 26, 53, 55, 77, 85).
3. **Stack merging** when `bMerge`: every existing item with the same base item, the same model
   variation and `CompareItem` true (next section) is offered the new item's stack
   (`CSWSItem::MergeItem` `0x00553f90`): if `existing + new ≤ baseitems.Stacking`, the existing
   stack absorbs everything, the new object is deleted, `*ppItem` becomes the existing stack, the
   client is told the stack changed, the existing stack gets `SetPossessor(its holder, bSignal)`
   (which for an unchanged holder just signals ACQUIRE_ITEM again, see below), and `bMarkNew` sets
   its "new" flag; done. Otherwise the existing stack is filled to the maximum, the remainder
   stays in the new item and the scan continues.
4. **Insert the remainder**: sorted list → at the position from step 2 (or appended), and its
   possessor is set to the first player's creature; unsorted list → **at index 0** (newest
   first). `bMarkNew` sets the "new" flag; every item carrying it bumps the counter at `+4`.

Note that only `AddItem` merges; nothing ever caps an existing stack except the merge itself
(`SetItemStackSize` clamps, see below).

### 5.3 Stacking rules

Two items stack when `CSWSItem::CompareItem` (`0x00553cf0`) holds, i.e. all of these are equal
(high): upgrades bit set, the counts of both property lists, plot flag, charges, base item, stolen
bit, model / body / texture variation, **tag**, localized name, and for every property in both lists
PropertyName, Subtype, CostTable, CostValue, Param1, Param1Value, UsesPerDay and UpgradeType.
The maximum stack is `baseitems.Stacking` (99 for most rows, 15000 for credits, 9999 for
programming spikes, 1 for the creature-weapon rows). With a maximum of 1 the merge never takes.

Stack size elsewhere (high):

- `GetItemStackSize` (138, `0x005465d0`) and `GetNumStackedItems` (475, `0x0053c220`) both read
  `+0x28c`.
- `SetItemStackSize(o, n)` (150, `0x00546630`): n clamped to 1..`Stacking`; when it changes, the
  possessing creature gets feedback 50 (gained) or 51 (lost) and the HUD notice 7 / 8.
- **DECREMENT_STACKSIZE** (event 16, item `EventHandler` `0x0055ee10`): stack > 1 → minus one;
  stack 1 → queue DESTROY_OBJECT (11) to the item. If the possessor has it equipped, the
  creature's carried-weight total `+0xa3c` drops by the base item's `TenthLBS`.

### 5.4 Possession and the inventory events

`CSWSItem::SetPossessor(newHolder, bSignal, bFeedback, oldHolderOverride)` (`0x00553210`, high) is
the single place that fires the item scripts. "Creature" below means the holder itself if it is a
creature, or the creature holding the container item that holds it.

1. New holder = current holder: queue script event 19 ON_ACQUIRE_ITEM (objects: item, holder) to
   the **module** and stop (no bSignal test).
2. If the creature changes: the old creature, if any, gets script event 20 ON_LOSE_ITEM (item) to
   the module when bSignal, and feedback 51 when bFeedback. The new creature, if it is a PC
   (stats `IsPC`), turns the item droppable and pickpocketable; feedback 50 when bFeedback.
3. A new creature with bSignal: ON_ACQUIRE_ITEM (item, creature) to the module.
4. Old holder a placeable with `DieWhenEmpty` = 0: with bSignal, script event 27
   ON_INVENTORY_DISTURBED to it, disturb type 1 (removed), caller = the new holder.
5. New holder a placeable with `DieWhenEmpty` = 0: with bSignal, the same event with disturb type 0
   (added), caller = the old holder.
6. Store the new holder at `+0x268`.

So the module's `OnAcquireItem` / `OnUnAcquireItem` run for every transfer to or from a creature,
and a container's `OnInvDisturbed` runs for every item put in or taken out — **except** for body
bags and ground piles (`DieWhenEmpty` set). All events go through the event queue (0 ms), so the
scripts run on the next `UpdateState`. The disturb type constants match nwscript's
`INVENTORY_DISTURB_TYPE_ADDED` 0 / `REMOVED` 1.

### 5.5 The party inventory versus a creature's own

`CSWSCreature::GetItemRepository(bParty)` (`0x004ef770`, high): with bParty and the creature in the
player's party (`+0xa88` set) → the party table's shared repository; also the shared one when a
server flag (`internal +0x104` bit 0) is set, the creature is one of the party table's NPC ids and
the in-game GUI agrees (`0x0062b4d0`; low: probably while a menu shows a non-member); otherwise the
creature's own `+0xa30`. Every caller found (about 80 sites, including the UTC item loader) passes
bParty = 1, so **party members never use their own repository**: what they pick up, buy or get
from scripts lands in the shared, sorted party inventory. Equipped items are not in any repository
(equipment slots, section 4).

Gold works the same way (high): `GetGold` (`0x004edd60`) is the party table's `PT_GOLD` (`+0xfc`)
for party members, else the creature's own `+0x9d0` (UTC `Gold`). `SetGold` (`0x004edd90`),
`AddGold(n, bFeedback)` (`0x004f3db0`, feedback 148 with the amount gained) and
`RemoveGold(n, bFeedback)` (`0x004f3ed0`, floor 0, feedback 149) clamp to **999,999,999**.
`GiveGoldToCreature` (322) and `TakeGoldFromCreature` (444) add the HUD credits notice (type 1,
± amount) for party members; `TakeGoldFromCreature(n, o, bDestroy)` clamps n to what o has and,
unless bDestroy, gives it to the caller: as gold to a creature, as a `g_i_credits001` item of
stack n to a placeable with an inventory or to a container item. `GetGold` on a placeable returns
the stack of its first credits item (ItemType 23).

**Joining the party** is 3.6 (`MergeCreatureIntoParty` `0x005641e0`): the joiner's own gold
and items move into the party; the party restore after a module load runs it for the PC and every
linked NPC, then `EquipDefaultClothes` (4.8). (high)

**Saving.** The party inventory is written by `CSWPartyTable::SaveInventory(bClear)`
(`0x00564030`) to `GAMEINPROGRESS:INVENTORY` (GFF `INV ` V2.0, one `ItemList` of full item
structs), at module transitions and in a save; loaded by the party restore (`0x00565760`) with
`AddItem(merge, no events, not new)` and possessor = PC. (high)

**Scripts see the party inventory**: `GetFirstItemInInventory` / `GetNextItemInInventory` (339/340,
`0x00549b50`) and `GetItemPossessedBy` (30, `0x0053a390`) on a creature use
`GetItemRepository(1)`; the iteration also steps one level into container items (cursor on the
creature `+0xa34` index, `+0xa36` sub-index, `+0xa38` current container; on placeables `+0x370`,
`+0x372`, `+0x374`). On a store the iterator returns nothing. `GetHasInventory` (570,
`0x005392d0`): creatures and stores 1, placeables their `HasInventory`, items 1 only for
containers. (high)

### 5.6 Moving items

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005158e0` | `CSWSCreature::AcquireItem(ppItem, fromId, intoContainerId, bFeedback)` | the item must be held by `fromId` (or by a container item `fromId` holds), else fail; target list = `GetItemRepository(1)` or the given container item's; take it from the old holder (creature `RemoveItem`, placeable `RemoveItem`, or a container item's list; a container into a container fails); `AddItem(merge, bFeedback, new)`; an item that was on the ground leaves the area; `SetPossessor(this creature or the container, signal, bFeedback)` | high |
| `0x00510ef0` | `CSWSCreature::RemoveItem(item, ?, bFeedback, ppOut)` | unequips it first if equipped (`0x005023a0`), takes it out of `GetItemRepository(1)` or the container item, `SetPossessor(invalid, signal, bFeedback)` | high |
| `0x00584b10` | `CSWSPlaceable::AcquireItem(ppItem, fromId, bFeedback)` | takes it from the old holder (or off the ground), `AddItem(merge, signal, new)`, `SetPossessor(placeable)` | high |
| `0x00584ac0` | `CSWSPlaceable::RemoveItem(item)` | out of `+0x36c`, `SetPossessor(invalid, signal, feedback)` | high |
| `0x0055dca0` | `CSWSItem::AcquireItem` | the container-item version (unused by KOTOR data) | med |
| `0x005538a0` | `CSWSItem::RemoveFromArea` | removes a ground item from its area, position to 0 | high |
| `0x00555720` | `CSWSItem::AddToArea(area, x, y, z, ...)` | puts an item on the ground (drop, `CreateItemOnFloor`, GIT items) | med |

Script routines (high):

- **`CreateItemOnObject(sTemplate, oTarget, nStack = 1)`** (31, `0x0052f570`): load the UTI
  (failure → `OBJECT_INVALID`), mark it droppable, clamp nStack to `baseitems.Stacking`, < 1 →
  invalid; creature → `AcquireItem(from invalid, feedback)` and, for a party member, the HUD
  "item gained" notice (type 7); placeable → `CSWSPlaceable::AcquireItem`; store →
  `CSWSStore::AcquireItem`; anything else → invalid. The returned object is the **resulting
  stack**, which after a merge is the pre-existing item, and credits return `OBJECT_INVALID`
  (they became gold).
- **`GiveItem(oItem, oTo)`** (271, `0x0053e830`, instant): creature → `AcquireItem` without
  feedback; placeable → its `AcquireItem`; container item → its `AcquireItem`.
- `ActionGiveItem` / `ActionTakeItem` (135/136, `0x0052c8b0`) queue actions 0x22 / 0x23
  ([actions.md](actions.md)). Note the GIVEITEM action removes a pazaak card through
  `0x004efc30`, which indexes the deck with `ModelVariation − 1` while acquiring uses
  `(ModelVariation + 11) mod 18` (below): the two disagree for every card (high; a bug of the
  original — use the acquire formula for both).
- **Destroying an item** (`DestroyObject`, event 11 DESTROY_OBJECT in the item `EventHandler`): only
  when the `CSWSObject` flag at `+0xec` is set (med: a "destroyable" flag); closes it if it is an
  open container; held by a creature → `RemoveItem` (unequips) and, for a party member and when
  the event data is 1, the HUD "item lost" notice (type 8); held by a container item, a placeable
  with an inventory or a store → removed from that list and `SetPossessor(invalid, signal,
  feedback)`; then off the ground and deleted. (high)
- `CServerExoAppInternal::GiveItemFromTemplate(creatureId, resref)` (`0x004b1fe0`): template →
  `AcquireItem` with feedback, clearing the infinite bit (debug/cheat path; med).

### 5.7 Containers (placeables with an inventory) and body bags

Placeable fields (`CSWSPlaceable::LoadPlaceable` `0x00585670`, high): `+0x324` `HasInventory`,
`+0x328` `Useable`, `+0x334` `DieWhenEmpty`, `+0x338` `Open`, `+0x36c` the repository (UTP/GIT
`ItemList`), `+0x2bc` `OnInvDisturbed`, `+0x394` `BodyBag` (row of `bodybag.2da`), `+0x440`
`IsBodyBag`, `+0x44c` `IsCorpse`, `+0x448` the body's former owner id. `GroundPile` is read but
the field `+0x254` is always forced to 1.

Opening is the USEOBJECT action's ([actions.md](actions.md) 3.5), which ends in
**`CSWSPlaceable::OpenInventory(user, bAnimate)`** (`0x00587420`, high): only when closed and
`HasInventory`; during a conversation (GUI `+0xb4`) it just plays the close animation (10076) and
stops; otherwise the user's client opens the container panel (told whether the list is empty),
script event 22 ON_OPEN is queued to the placeable (caller = user), the open animation 10075
plays when asked, `Open` = 1.

The container panel (`CSWGuiContainer`, `container.gui`, `0x006b6dc0`) answers with GuiContainer
message 0x19/2 {placeable id, take-all flag} (`0x005232a0`) → **`CSWSPlaceable::CloseInventory(user,
bTakeAll)`** (`0x00587560`, high), only if open:

1. With bTakeAll and a player user: take items **from the last to the first**; each is removed
   from the placeable and given to the user's `GetItemRepository(1)` with `AddItem(merge,
   signal, new)` and `SetPossessor(user, signal, feedback)` — so ON_ACQUIRE_ITEM fires per item and
   the placeable's `OnInvDisturbed` fires per item (type 1) unless `DieWhenEmpty`.
2. Queue script event 23 ON_CLOSE (caller = user), play animation 10076, `Open` = 0.
3. `HasInventory` and `DieWhenEmpty` and now empty → `Useable` = 0 and DESTROY_OBJECT queued to
   itself (the bag vanishes).

Single items are taken with the PICKUPITEM action (Inventory message 0xc/5 →
`AddPickUpItemAction`), and the panel's `BTN_GIVEITEMS` puts items in with GIVEITEM (input 0x24);
both are actions.md's. (med for the panel side, which was not traced button by button)

**Body bags.** `CSWSObject::SpawnBodyBag` (`0x004ce220`, called from the creature and placeable
event handlers on death; high for the steps):

1. Creatures and placeables only, in a valid area. The bag row is the creature's `BodyBag` byte
   (`+0x9da`); 0 → `appearance.2da` column `BODY_BAG` of its appearance. A placeable uses its own
   `BodyBag` and needs at least one item (`0x00587710`).
2. `bodybag.2da` `Corpse` = 1 (rancor, krayt) makes a corpse container. A non-corpse bag is only
   made when the creature has droppable items or gold (else no bag, `OBJECT_INVALID`).
3. A new placeable is set up from the `bodybag.2da` row (`0x005864b0`: appearance from its
   `appearance` column) and filled by `CSWSPlaceable::TakeItemsFromObject(source, bDroppableOnly =
   1)` (`0x00588690`): the source's equipped items in slots 0..13 and its inventory items, those
   flagged droppable, are moved in with `AcquireItem`; the source's gold becomes a
   `g_i_credits001` item of that stack and the source's gold is set to 0.
4. Bag fields: `IsBodyBag` 1, owner id, `IsCorpse` from the 2DA, `DieWhenEmpty` = not corpse
   (a corpse without items gets `HasInventory` 0), plot = not corpse, name = `bodybag.2da` `Name`
   strref (38151 "Remains" for every row), position and facing of the dead object, `PartyInteract` 1.
5. Event 17 SPAWN_BODY_BAG is queued to the **area** with a **500 ms** delay carrying the bag id
   and position; the area adds it then.

### 5.8 Stores

`CSWSStore` (UTM; `LoadStore` `0x005c7180`, `SaveStore` `0x005c6cd0`; high):

| Offset | Field |
|---|---|
| `+0x228` | `OnOpenStore` script |
| `+0x230` | the stock (`CItemRepository`, unsorted) |
| `+0x234` | `LocName` |
| `+0x23c` | last opener (set when the store's script event 22 arrives) |
| `+0x244` | `MarkDown` (percent paid when the player sells) |
| `+0x248` | `MarkUp` (percent charged when the player buys) |
| `+0x24c` / `+0x250` | bonus mark-down / bonus mark-up from `OpenStore` |
| `+0x256` | `BuySellFlag` (constructor default 3) |

**Stock loading.** Each `ItemList` entry is a template (`InventoryRes`, from a UTM) or a full item
(from a save GIT), plus `Infinite` (item flag bit 2). Entries are first collected in descending
value order, then added from the cheapest up through `CSWSStore::InsertItemByCost` (`0x005c70c0`),
so a freshly loaded store holds its stock in ascending value. Later additions are appended (via
`AddItem` with merging) unless cheaper than the first entry, in which case a backwards scan inserts
them at the last index whose value is higher (it does not keep a strict order; high for what the
code does). The panel re-sorts anyway (below). The 38 shipped UTMs: `MarkUp` 75..150 (mostly
100), `MarkDown` 20..65 (mostly 25), `BuySellFlag` 3 in 36, 1 in 2; 158 infinite entries.

**`OpenStore(oStore, oPC, nBonusMarkUp = 0, nBonusMarkDown = 0)`** (378, `0x00540300`): both
bonuses clamped to −100..100 and stored; the in-game GUI opens the store panel
(`CGuiInGame::OpenStore` `0x0062e310`, `CSWGuiStore` `0x006c1c00`); script event 22 is queued to the
store with the PC's controlled creature as caller, and the store's `EventHandler` (`0x005c6ee0`)
records the caller and runs `OnOpenStore`. (high)

**Item value** (`CSWSItem::GetCost` `0x00554000`, high, from the disassembly):

```
value(item) = 0                                   if the item is plot
            = max(1, trunc(AddCost × costMult[base item]))   otherwise
```

`costMult` is a float per `baseitems.2da` row (row `+0xc4`, 1.0 at load), changed only by
**`ChangeItemCost(sTemplate, fMult)`** (747, `0x00547970`: loads the template to learn its base item
and sets that row's multiplier, so it affects **every item of that base item**) and saved in the
party table as `PT_COST_MULT_LIST` (one float per base item row, label truncated to 16 characters
in the file). The value is **per unit**: stacks are bought and sold one at a time. `GetGoldPieceValue`
(311) returns the same value.

**Prices** (`CSWGuiStore::GetBuyPrice` `0x006c0790` / `GetSellPrice` `0x006c07f0`, high), integer
arithmetic, unsigned divide:

```
buy  (player pays)     = value × (MarkUp   + BonusMarkUp)   / 100
sell (player receives) = value × (MarkDown + BonusMarkDown) / 100
```

**No skill or ability enters the price**: no Persuade, no Charisma; the panel code reads only
these fields. Persuade discounts exist only where a script passes bonuses to `OpenStore` (outside
knowledge about the scripts, low).

**Buying** (`CSWGuiStore::OnBuy` `0x006c1130` → `DoBuy` `0x006c0be0`, high): price > the
panel's copy of the gold → message 41950 "You do not have enough credits to purchase this item.";
price > **50 × the PC's level** (`CSWSCreatureStats::GetLevel`) → confirmation box 42020 ("This
item costs more than <CUSTOM0> credits…", token 0 = that threshold); then: click sound 9, gold −= price written to the
PC with `SetGold` (so the party's `PT_GOLD`), and `CSWSStore::SellItemTo(item, PC)` (`0x005c6f70`):
an **infinite** item is copied (copy keeps the stock item, infinite bit cleared, stack 1); a stack
> 1 is split by one; a single item leaves the stock; the result goes to the PC with
`AcquireItem(from the store, feedback)` — into the party inventory.

**Selling** (`OnSell` `0x006c0f40` → `DoSell` `0x006c0d80`, high): price > **min(50 ×
level, 250)** → confirmation 41985 ("This item is worth more than <CUSTOM0> credits…"); then sound
11, gold += price via `SetGold`, one unit leaves the party inventory (split when stacked) and goes
to `CSWSStore::AcquireItem` (`0x005c7610`): **plot items are refused**; the item is marked
identified and removed from its creature holder; if the stock already has an item with the same
tag that `CompareItem` accepts, an infinite stock item absorbs it (the sold object is deleted) and
a finite one gets **+1 on its stack, whatever the item's stack was and ignoring `Stacking`**;
otherwise it joins the stock through `InsertItemByCost`.

**Lists and modes** (high): the store list (`FillStoreItems` `0x006c1840`) and the player list
(`FillPlayerItems` `0x006c0850`, from the PC's `GetItemRepository(1)`, i.e. the party inventory;
equipped items are not offered) show **only non-plot items**, grouped by `baseitems.StorePanelSort`
ascending and in list order inside a group. Selecting an entry shows the buy or sell price (by
mode) and either the stack count or 41951 "Infinite" (`OnItemHilighted` `0x006c0aa0`).
`BuySellFlag` (`0x006c1b50`): 1 → buy page only, 2 → sell page only, 3 → both with a toggle.

### 5.9 Credits and pazaak cards

- **Credits** are base item 57 (`ItemType` 23, `Stacking` 15000, template `g_i_credits001`). In a
  creature's or the party's inventory they never exist as items: `AddItem` turns them into gold.
  They exist as items in placeables, body bags and on the ground.
- **Pazaak cards** are base item 86 (`ItemType` 42, `g_i_pazcard_001`..`018`, `ModelVariation`
  7..18 then 1..6). `CSWSCreature::AddPazaakCard(item)` (`0x004efb40`, high): the party table's
  card count at `+0x120 + 4 × ((ModelVariation + 11) mod 18)` (= card number − 1) grows by the
  stack size, the item is deleted, and if the party inventory holds no item of `ItemType` 43, a
  `g_I_PazSidebd001` (pazaak side deck) is created and added. The counts are `PT_PAZAAKCARDS`.

### 5.10 Charges and uses

Only the usable CastSpell properties (PropertyName 10) consume anything; their `CostValue` is a row
of `iprp_chargecost.2da`. Uses left (`CSWSItem::GetPropertyUsesLeft(i)` `0x00555a60`, high):

| CostValue | Meaning | Uses left |
|---|---|---|
| 1 Single_Use | consumed item | the **stack size** (medpacs, grenades, stims) |
| 2..6 | 5, 4, 3, 2, 1 charges per use | `Charges / (7 − CostValue)` (integer) |
| 7, 13 | 0 charges per use, unlimited | not counted |
| 8..12 | 1..5 uses per day | the property's `UsesPerDay` byte |
| 14..18 | 1..5 per minute | 1 while `Useable` |

`CSWSItem::UpdateUsesForClient` (`0x0055d040`) packs these into the `+0x238..+0x240` cache and
tells the possessing client when they change. Spending a use is the item-cast-spell action's
(actions.md 0x2e); a single-use item is used up through DECREMENT_STACKSIZE. (med for the link)

### 5.11 Upgrades (the workbench)

**The mechanism** (high, from the code and confirmed on the data): an upgradeable weapon or armour
blueprint **already contains every property any upgrade could give it**, each tagged with
`UpgradeType` = a row of `upgrade.2da`; native properties have 255. A property counts only when
its tag is 255 or its bit is set in the item's `Upgrades` word: every property reader applies this
filter — the property lookup `0x005539c0`, applying the passive properties on equip `0x00553bb0`
and removing them on unequip `0x00553c30`. Installing an upgrade sets bit *row*; removing it clears
the bit. Nothing is copied from the upgrade item; the upgrade item object is consumed. Example:
`g_a_class5001` carries Ability/Armor properties tagged 20 (Armor_Reinforcement) and 21
(Mesh_Underlay); `g_w_lghtsbr01` carries properties tagged with every crystal row (0..12, 22..24).
58 of 810 UTIs carry tagged properties. A tagged property still counts toward `CompareItem` and
item-description text whether or not it is active.

`upgrade.2da` (`label`, `template`, `upgradetype`): rows 0..12 and 22..24 are lightsaber power
crystals (type 0), 13..15 melee (types 1..3: vibration cell, durasteel alloy, energy projector),
16..19 ranged (types 4..7: scope, improved energy cell, beam splitter, hair trigger), 20..21 armour
(types 8..9). `upcrystals.2da` lists the lightsaber colour crystals with, per row, the template of
the saber of each kind (`ShortMdlVar`, `LongMdlVar`, `DoubleMdlVar`).

**Category** (`CSWSItem::GetUpgradeCategory(upgrade2DA)` `0x005541c0`, high): over the item's
properties with a tag, `upgradetype` 0 → 1 lightsaber, 1..3 → 3 melee, 4..7 → 2 ranged, 8..9 → 4
armour; 0 = not upgradeable.

**Slots** (table `g_aUpgradeSlots` at `0x00756fb0`, 16 records of {upgradetype, icon, label
strref}, indexed `(category − 1) × 4 + slot`; high):

| Category | Slot 0 | Slot 1 | Slot 2 | Slot 3 |
|---|---|---|---|---|
| 1 lightsaber | power crystal (type 0, `i_powerc`, 36977) | colour crystal (`i_colorc`, 36978) | power crystal (type 0) | — |
| 2 ranged | scope (4) | improved energy cell (5) | beam splitter (6) | hair trigger (7) |
| 3 melee | vibration cell (1) | durasteel alloy (2) | energy projector (3) | — |
| 4 armour | — | armour reinforcement (8) | mesh underlay (9) | — |

**The flow** (high for each step; the panels are `CSWGuiUpgrade` `upgrade.gui` `0x006c6b60`,
`CSWGuiUpgradeItems` `upgradeitems.gui` `0x006c7630`, `CSWGuiUpgradeSelect` `upgradesel.gui`
`0x006c78d0`):

1. `ShowUpgradeScreen(oItem = invalid)` (354) → `CGuiInGame::ShowUpgradeScreen` (`0x0062e760`).
   With an item it goes straight to it; otherwise the four category buttons are enabled for each
   category that has an upgradeable item among the PC's and the selectable party members'
   equipped items and the party inventory (`0x006c4520`).
2. The item list of a category (`0x006c5b90`): equipped items of the PC and of each available,
   selectable NPC, then party-inventory items of that category.
3. Picking an item takes it out of play: equipped → unequipped (its properties come off) and the
   slot remembered; in the inventory → removed (one split off a stack) (`0x006c6330`). The bench
   keeps a backup copy (`CopyItem`) for cancelling.
4. Setting up the slots (`CSWGuiUpgrade::OnPanelAdded` `0x006c4d70`): for each `upgrade.2da` row,
   the first empty slot of this category whose type matches gets the row; if the item's
   `Upgrades` has that bit, an item is created from the row's template and shown installed;
   otherwise, if the party inventory has no item whose tag equals the template (lower-cased), the
   slot icon is dimmed (alpha 0.25). For a lightsaber the colour slot's crystal is the
   `upcrystals.2da` row whose column for this saber kind (`ItemType` 39 double, 40 short, 41 long)
   equals the saber's **tag**.
5. Clicking a slot (`OnSlotClicked` `0x006c6500`): installed → clear the bit, the upgrade item goes
   back to the party inventory (`AddItem` with merge); empty → find the template in the party
   inventory, set the bit, and if the item belongs to an equipping creature, re-check
   `CanEquipItem` (`0x0051aa60`): failure shows message 42489 ("Adding this upgrade will prevent the
   character who was previously using this item from reequipping it because they do not have the
   appropriate feat.") and asks; else the upgrade item is
   moved out of the party inventory (one unit). Lightsaber slots open a list instead: power crystals
   from the party inventory not already in the other power slot; colour crystals other than the
   current one.
6. Choosing a **colour crystal** (`0x006c5510`) **replaces the saber object**: a new item is created
   from the chosen `upcrystals.2da` row's template for this saber kind, takes over the old saber's
   `Upgrades` word and stolen bit, and the old object is deleted; the old crystal returns to the
   party inventory. Power crystals set or clear their bit like the other slots.
7. `BTN_ASSEMBLE` (`CSWGuiUpgrade::OnAssemble` `0x006c6190`) and closing (`0x006c5e90`) put the
   item back: re-equipped in its slot when `CanEquipItem` still allows it (two-weapon slots 0x10 / 0x20 handled), else into the
   party inventory. Back/cancel (`0x006c61f0`) restores the backup copy and undoes the inventory
   moves of the session before doing the same.

## 6. Open questions

Saves and globals:

- The fields of `AUTOSAVEPARAMS` (written by `0x004b28e0`, read by `0x006c9de0`) were not listed
  one by one; a port that writes its own transition autosaves needs them (low).
- The server's minimum free space for a save (`+0x100c8`), the flags `+0x1b930` / `+0x1b938`
  cleared by save and load, and when `+0x100c4` (`GetLoadFromSaveGame`) is cleared again.
- The argument of `Game%d` in a manual save's folder name (the install's slot 2 is `Game1`), and how
  the save panel picks a new number.
- The positional global-variable reader `0x00529ef0` (saves without `Cat*` lists) was not read;
  what happens when a save brings more globals of a type than the table holds.

Party:

- Whether the leader slot `+0xec` restored from `PT_IS_LEADER` is re-applied to the client party
  table after a load (no caller found that does it).
- `SetPartyLeader(-1)` resurrects dead or dying members before giving the PC the lead: why, and
  what the creature flags `+0x9d4` (set with `IsPC` by `SwitchPlayerCharacter`) and `+0xf0` (set
  before a resurrection) mean.
- `0x005a5680(0)` on the stats of an NPC that becomes available; the follow state `+0xe8` beyond its
  reset; what `GetItemRepository`'s extra case (server `+0x104` bit 0, GUI `0x0062b4d0`) is for.
- A joiner's own gold is added to `PT_GOLD` without resetting the creature's field: whether a later
  leave-and-rejoin can duplicate gold.
- The formation geometry used by `PlacePartyAroundLeader` and party selection is movement.md's
  client party table; the exact slot offsets were not tabulated.

Equipment:

- What the numbered combat modes at `+0x4d2` are (1–3 melee, 5 empty-handed, 6 ranged, 4
  counter): probably the attack-mode feats or stances; the setter `0x0050ee80` and its callers
  were not read in full.
- The meaning of the per-hand "instant" flags `+0xaac` / `+0xaa8`, and what `+0x344` triggers.
- The exact arguments of `RemoveItemProperties` (`0x00553c30`) and the remove dispatcher (the
  decompiler lost them; the slot is believed to be the `GetSlotFromItem` result).
- The remove handlers other than AC and enhancement were not read one by one (assumed symmetric:
  match type, creator and parameters).
- The 0x36 light effect's int0 = 5000 and the light property's 2DA (`iprp_lightcost`) are not
  connected in the handler; how the light colour is chosen was not traced.
- Whether the shield base `+0xf7` and natural base `+0xf5` ever change with equipment (no writer
  in the equip code).
- The GUI's two-handed test (`WeaponSize` 4) and the server's (`WeaponWield` 3/5/6) disagree for
  the Gamorrean battleaxe; which one players actually hit was not tested in the game.

Inventory, stores, containers:

- The weight bookkeeping (`+0x290`, creature `+0xa3c`, `GetContentsWeight`) has no consumer found
  yet; KOTOR shows no encumbrance, so it can likely be skipped (low).
- Item flag bit 1 and the `CSWSObject` `+0xec` flag tested before destroying an item are unnamed.
- The container panel's per-button wiring (take one, take all, give) was read from the server
  side only; the panel code (`0x006b5890`..`0x006b7270`) is gui.md's.
- The accept path of the upgrade bench leaks the backup copy and the installed upgrade objects in
  the original; a reimplementation should delete them (low: inferred from the absence of a delete).
- The GIVEITEM action's pazaak-card index disagrees with the acquire formula (5.6); which one the
  shipped scripts rely on was not checked.
