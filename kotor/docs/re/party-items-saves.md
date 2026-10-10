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
The whole page was rechecked claim by claim on 2026-10-07 against the exports rebuilt after the
noreturn fix ([noreturn-fix.md](noreturn-fix.md)) and against the four saves now in the install; a
med claim that says "needs a runtime check" rests on static reading alone and is surprising enough
to test before relying on it.

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
| `GAMEINPROGRESS:` | the live state of the current game: every visited module's `<module>.sav`, `AVAILNPC<n>.utc`, `INVENTORY.res`, `REPUTE.fac`, `PC.utc` while an NPC is the player character | deleted with the server (`ShutDownServer` `0x004b7c60`, run by `DestroyServer` and by `CreateServer` before it builds a new one) and re-created empty by the server's `Initialize` `0x004b63e0`, so a new game starts empty; **replaced** by a load; packed whole into `SAVEGAME.sav` by a save |
| `FUTUREGAME:` | scratch: a save is extracted here first, then swapped in (1.6) | per load |
| `CURRENTGAME:` | the working copy of the current module's main file ([modules.md](modules.md)) | per module; deleted with the server |
| `TEMP:` | `pifo` (the player characters in transit between modules) and character-creation leftovers | per transition; emptied each time the save list is built (1.5), deleted with the server |

**Save folders and numbers.** The folder is `SAVES:` + `%06d - %s`. Slot 0 is the quick save
(folder `000000 - QUICKSAVE`, typed name also `QUICKSAVE`, `CClientExoAppInternal::QuickSave`
`0x005f4b50`); slot 1 is the autosave (`000001 - AUTOSAVE`, used both by the module-transition
autosave and by the scripted `DoSinglePlayerAutoSave`). Manual saves come from the save panel
(`CSWGuiSaveLoad::DoSave` `0x006c8790`) with the folder name `Game%d` of their number minus 1 (`000002 - Game1`):
overwriting a listed save reuses its number; the "new save" row carries the highest listed number
+ 1, at least 2 (1.5); if that reaches 1000 the first free number found by the list scan
(`CSWGuiSaveLoad` `+0x68`) is used instead, and if that is 1000 or more too a message (strref
42490) refuses the save. The install currently holds `000000 - QUICKSAVE`, `000001 - AUTOSAVE`,
`000002 - Game1` and `000003 - Game2`. The name the player types is not part of the folder: it
goes into `savenfo.res` `SAVEGAMENAME`. (high)

### 1.2 What a save contains

Loose files in the save folder (every GFF here is written as V3.2: the writers pass `"V2.0"`, but
`CResGFF::CreateGFFFile` `0x00411260` ignores that argument and stamps `g_pszGFFVersion`):

| File | Format | Written by | Read by | Conf. |
|---|---|---|---|---|
| `savenfo.res` | GFF `NFO ` V3.2 | `DoSaveGame` `0x004b3110` / `WriteTransitionAutoSave` `0x004b8300` | the save list (`CSWGuiSaveLoadEntry::ReadSaveInfo` `0x006c8e50`); `AUTOSAVEPARAMS` by `LoadTransitionAutoSave` `0x006ca250` | high |
| `PARTYTABLE.res` | GFF `PT  ` V3.2 | `CSWPartyTable::SavePartyTable` `0x005648c0` | `CSWPartyTable::LoadPartyTable` `0x00565d20` | high |
| `GLOBALVARS.res` | GFF `GVT ` V3.2 | `CSWGlobalVariableTable::SaveToDirectory` `0x0052ad10` | `LoadFromSaveDirectory` `0x0052ade0` | high |
| `SAVEGAME.sav` | ERF `MOD V1.0` holding every file of `GAMEINPROGRESS:` | `CERFFile::AddDirectory` in the two writers | `CERFFile::ExtractAll` in the loaders (1.6, 1.7) | high |
| `Screen.tga` | TGA, 256 × 256, 24 bit, uncompressed | the renderer's screenshot writer (`0x00420f20`, through `0x00401080`) called from `RequestSaveGame` `0x004b58a0`, before the save itself | the save list's row-selection handler `0x006c89d0` (mounts the folder and shows resource `screen`, for rows without `PCAUTOSAVE`/`REBOOTAUTOSAVE`) | high |
| `pifo.ifo` | GFF `IFO ` with only `Mod_PlayerList` | transition autosaves only: a copy of `TEMP:pifo` (resource type 2014, so the file is `pifo.ifo`) | copied back to `TEMP:pifo` by `LoadTransitionAutoSave` | high |
| `CORRUPT` | 7-byte text "CORRUPT" | never in this build: the writers (`PrepareGameInProgress` `0x006caaf0` and its in-game twin `0x006323a0`) only run it when the extractor reports failure, and both extractors (`0x006c9a90`, `0x0062fbe0`) always return 1 (1.6) | the save list marks the row corrupt and does not read `savenfo` | high |

Inside `SAVEGAME.sav` (= the files of `GAMEINPROGRESS:`; ERF keys keep the case the files were
written with: `AVAILNPC0`/2027, `INVENTORY`/0, `REPUTE`/2038, and each module save under the name
its module was loaded by, e.g. `danm13`/2057, `ebo_m12aa`/2057 in the install's saves):

| Entry | What | Written by | Conf. |
|---|---|---|---|
| `<MODULE>.sav` | nested ERF `MOD V1.0` with exactly three entries: `module.ifo` (all IFO fields, the event queue, the module's locals, `Mod_PlayerList` = the player creature), `<area>.git` (every object of the area except player-controlled creatures, i.e. **without the PC and the party members**: `CSWSArea::SaveCreatures` `0x00507680` skips creatures whose `+0xa88` is set), `<area>.are` | `SaveCurrentModuleToGameInProgress` `0x004b2e70` → `CSWSModule::SaveModuleIFO` `0x004c8960` (deletes the old file, creates the ERF with 3 entries, sets the module's "is a save" flag `+0x1c8`), the GIT step `0x004c3b10`, the ARE copy and close `0x004ca680` | high |
| `REPUTE.fac` | GFF `FAC `: `FactionList`, `RepList` of the faction manager (server `+0x10054`) | `0x004c3960`, at the end of every module IFO save | high |
| `AVAILNPC<n>.utc` | the full saved creature of NPC slot *n* (0..8) | `CSWPartyTable::SaveNPCState` `0x00563e80`; also `AddAvailableNPC*` | high |
| `INVENTORY.res` | GFF `INV `: `ItemList` of full item structs = the party's shared inventory | `CSWPartyTable::SaveInventory` `0x00564030` | high |
| `PC.utc` | the real player character while `SwitchPlayerCharacter` has put an NPC in its place (3.5) | `CSWPartyTable::SwitchPlayerCharacter` `0x005667c0` | high |

There is one `<MODULE>.sav` per module visited in the current game whose `modulesave.2da`
`IncludeInSave` is 1 (`0x004b20e0`; 0 for the cutscene `STUNT_*` modules, the swoop and turret
minigames; a module without a row, or a table that fails to load, counts as 1). A transition into a module whose row has `DeleteSaveGroupOnEnter` deletes the `.sav`
of every module of that save group ([gameloop.md](gameloop.md) 5.3). (high)

### 1.3 Saving (quick save, manual save, scripted autosave)

Two halves, one frame apart. (high unless marked)

**Request** — `CServerExoAppInternal::RequestSaveGame(nSaveNumber, sFolderName, nPlayer)`
(`0x004b58a0`; reached from the client message 3/4, which carries number, folder name and the typed
name — the typed name goes to server `+0x1b93c` through `0x004af0e0` — and from the server main loop
for `DoSinglePlayerAutoSave` with number 1 and `"AUTOSAVE"`: the script sets the pending flag
`+0x100b8`, and the loop acts on it once the transition block is idle, the PC is in an area and the
client is not loading; it requests the save only if `HasDiskSpaceForSave` passes and the server is
running (state 2), otherwise it just fades back in, and clears the flag either way):

1. Sound mode 3 (muted while saving); make `SAVES:`; build `SAVES:%06d - %s`.
2. **Disk space**: if free space plus the size of an existing folder of that name is below the
   server's minimum (`+0x100c8`, set at each module load by `0x004b5f90`: the total size of the
   files in `GAMEINPROGRESS:` (2.5 MB for one that will not open), plus 2.5 MB unless the module
   comes from a save file, times 10/9; 3,750,000 bytes while `GAMEINPROGRESS:` is empty), send the
   client an out-of-space message and stop (returns 0).
3. Create the folder, or empty it if it exists (`CleanDirectory`: old files, including a
   `CORRUPT` marker, are removed); if neither works, stop (returns 0).
4. Fill the transition block (`g_pAppManager+0x14`, see [gameloop.md](gameloop.md) 5.4): busy = 1,
   **mode = 2 (save)**, "skip one client frame" = 1, error = 0, `+0x18` = the folder, `+0x20` =
   `<folder>\SAVEGAME`, counters 0. Tell the client.
5. Take the **screenshot** now (only when the `SAVES` alias resolves): object 0x106a of the client
   area (the chase camera, med) is first turned to face its target (`0x00638e80`); then the
   screenshot writer (`0x00401080` → `0x00420f20(path, 256, 1, 1)`) clears the frame buffer,
   renders the scene once more through the `camera` scene object (the GUI is not drawn, med), reads
   the pixels back, scales them to 256 × 256 and writes `<SAVES path><%06d> - <name>\Screen.tga`.
6. Unless it is slot 0 (quick save), draw one loading frame. Restart the 15-minute autosave timer
   (`UpdateAutoSaveTimer` `0x004b1ee0`: clear its elapsed milliseconds `+0x1b930` and its "due" flag
   `+0x1b938`).

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
| 6 | 20 | **`savenfo.res`** into the save folder: `AREANAME` = the player's area `Name` (in the language of the player's client, med), `LASTMODULE` = the module name, `TIMEPLAYED` (3.10), `CHEATUSED` (party table `+0x194`), `SAVEGAMENAME` (server `+0x1b93c`), `GAMEPLAYHINT` / `STORYHINT` (the load-screen hint indices kept by the client), `LIVE1`..`LIVE6` (client strings) and `LIVECONTENT` (bit *i*−1 set when the alias `LIVE<i>` resolves to a non-empty path), `PORTRAIT<i>` for each member of the client party table in order (index 0 = the leader; a member without a server creature is skipped, leaving a gap): the creature's portrait resref. |
| 7 | 25 → 60 | **`SAVEGAME.sav`**: create `<folder>\SAVEGAME`, type `MOD V1.0`, add every file of `GAMEINPROGRESS:` (progress 30..60 as files are added), finish, then read the header and key list back once. |
| 8 | 100 | Sound mode 0; end the load screen; fade back in unless a dialogue or similar takes over (in-game GUI `+0x30` set: nothing; else `+0xb4` set: only `+0xb98` = 1; else a 0.5 s global fade from black); then, unless the transition block is already marked done: mark it done (when the global `0x007a39dc` is 2 the block's busy, mode and done words are cleared instead; low: what that global selects) and tell the client the save ended (`0x0056c850(1)`, `0x0056c980(2, 0)`). |

Nothing in this sequence pauses or clears the game: after the save the game continues where it
was. The party inventory and NPC objects stay as they are (step 3 does not clear them). (high)

### 1.4 The transition autosave

`CServerExoAppInternal::WriteTransitionAutoSave(sTargetModule, pModuleSave2DA)` (`0x004b8300`) is
called by `StartModuleTransition` when the target's `AutoSaveOnEnter` asks for it
([gameloop.md](gameloop.md) 5.7), after the save-group deletion; if `modulesave.2da` cannot be
loaded the question is skipped and the autosave is always written. At that point the module being left has already been saved to
`GAMEINPROGRESS:`, the player characters are in `TEMP:pifo` and the party's NPCs and inventory have
been written and cleared (1.8). It produces a save that **re-enters the target module**:
(high unless marked)

1. Show the target's load screen; folder `SAVES:000001 - AUTOSAVE` (created or emptied).
2. `PARTYTABLE.res` alone (`SavePartyTable`, not `SaveGame`: the NPCs and inventory were written
   by the transition already) (progress 5 % of the bar's share), `GLOBALVARS.res` (10 %).
3. `savenfo.res`: `AREANAME` = the TLK string of `modulesave.2da` `AreaName` for the target (empty
   without one), `LASTMODULE` = the target, `TIMEPLAYED`, `CHEATUSED`, **`PCAUTOSAVE` = 1**,
   **`SCREENSHOT`** = the `BMPResRef` of the target's own row in `loadscreens.2da` when it has one
   (only the swoop and turret minigames do), else `load_<target>` if such a TGA or TPC exists, else
   the `BMPResRef` of the `DEFAULT` row (there is no `Screen.tga`), `GAMEPLAYHINT`, `STORYHINT`, an
   **`AUTOSAVEPARAMS`** struct (the pending transition, written by `CAutoSaveParams::Save`
   `0x004b28e0`, read back by `0x006c9de0`): `LOADMUSIC` (the target's load-screen music, chosen
   like `SCREENSHOT` from the `MusicResRef` column), `STARTWAYPOINT` (the server's move-to-module
   waypoint), `MOVIE1`..`MOVIE6` (the client's queued movies, empty when fewer), the module calendar
   as `TIME_YEAR`, `TIME_MONTH`, `TIME_DAY`, `TIME_HOUR`, `TIME_MINUTE`, `TIME_SECOND`,
   `TIME_MILLISECOND`, the world timer's current day and time of day as `TIME_PAUSEDAY` /
   `TIME_PAUSETIME`, and a `STATUSSUMMARY` struct (the in-game GUI's six words of pending
   notifications: `DISPLAYSPENDING`, `ITEMRECEIVED`, `ITEMLOST`, `JOURNAL`, `LIGHTSHIFT`,
   `DARKSHIFT`, `CREDITS`, `CREDITSNET`, `XP`, `STEALTHXP`, `SOUNDPENDING`, `LEVELUPSOUND`,
   `NEWQUESTSOUND`, `COMPLETESOUND`, `SUPPRESSED`); then `PORTRAIT<i>` as in 1.3. No
   `SAVEGAMENAME`, no `LIVE*`.
4. `SAVEGAME.sav` from `GAMEINPROGRESS:` as in 1.3, then copy `TEMP:pifo` to `<folder>\pifo.ifo`.

### 1.5 The save list

`CSWGuiSaveLoad::PopulateList` (`0x006cc160`, gui.md) first empties `TEMP:`, then builds one row per
folder, in the order of `CExoBase::GetDirectoryList(SAVES:, 0xffff, directories, 1)` (`0x005e6640` →
`0x005e8cf0`): with the last argument 1 each directory name is inserted before the first listed one
that is not smaller (`0x005e5580` is `>=` on the lower-cased names' bytes, called with the listed
name as `this`; the insert `0x005e8c60` shifts the rest down), so the rows run by folder name,
ascending: the quick save, the autosave, then the manual saves oldest number first (a last argument
of 2 orders files, not directories, by write time; not used here). The list box keeps that order
(`SetItems` `0x0041c1d0` appends the rows in turn; `UpdateLayout` `0x0041b140` lays them out top
down from the first visible one). Rechecked on the new decompile: nothing reverses it. **Ours
differs**: the player, who knows the game, expects the manual saves newest first, so
`lib/frontend/saves.ctx` lists the quick save, the autosave, then the manual saves by number,
highest first. Each row reads its folder with `0x006c8e50`: number = the integer before `" - "`, folder
name = the rest; if a file `CORRUPT` exists the row is flagged corrupt (flags `|= 3`) and nothing
else is read; otherwise, with the folder mounted, from `savenfo.res`: `AREANAME`, `LASTMODULE`,
`TIMEPLAYED`, `SAVEGAMENAME` ("Old Save Game" when missing), `CHEATUSED` (flag 0x80),
`REBOOTAUTOSAVE` (0x08, Xbox only), `PCAUTOSAVE` (0x10), `SCREENSHOT`, `GAMEPLAYHINT`, `STORYHINT`,
`LIVECONTENT` + `LIVE<i>` (a row needing live content whose alias is missing gets flag 0x21 and the
content name, and reading stops there), `PORTRAIT0..2`; a fully read row gets flag 0x01. In the
save panel the rows of slots 0 and 1 are dropped (the quick save and autosave cannot be
overwritten from it) and a "new save" row (strref 1590, flags `|= 0x44`) is put first, numbered the
highest listed number + 1, at least 2; `+0x68` keeps the first free number the scan found (1.1).
In the load panel an empty list closes the panel and shows strref 42491. Hilighting a row (event 0)
runs `0x006c89d0`: a row not fully read (flag 0x01 clear: the New Slot row) or corrupt (0x02) clears
the planet and area labels, the portraits and the picture, puts "New Slot" (1590) in
`LBL_SCREENSHOT` as text and disables `BTN_DELETE`; any other enables Delete, splits `AREANAME` at its
first `-` (planet = what is before it less one character, area = what is after it less one; no `-`:
all of it is the planet), sets the three portraits, and shows `Screen.tga` from the mounted folder,
or the `SCREENSHOT` resource for autosave rows (flags 0x18), with the label's text empty or "Cheat
Used" in the menu hilight colour for flag 0x80. In the load panel the Load button's text goes grey
for a row needing missing live content (flag 0x20). (high)

### 1.6 Loading a normal save

`CSWGuiSaveLoad::LoadSelectedGame` (`0x006cb0e0`) first refuses a row that needs missing live
content (flag 0x20: a message naming the content), resets the session clock (3.10), then picks a
path by the row's flags: `REBOOTAUTOSAVE` rows do nothing, `PCAUTOSAVE` rows go to 1.7, the rest
take the normal path: (high unless marked)

1. **Load screen** for the row's `LASTMODULE`, with the row's `GAMEPLAYHINT` / `STORYHINT`.
2. **Extract into a scratch directory**: `ExtractSaveToFutureGame` (`0x006c9a90`) creates and
   empties `FUTUREGAME:` and extracts `SAVEGAME.sav` into it. It returns 1 whatever `ExtractAll`
   did (single exit, constant 1; the in-game twin `0x0062fbe0` used by `QuickLoad` is the same).
3. **Swap**: `PrepareGameInProgress` (`0x006caaf0`) then deletes the `GAMEINPROGRESS:` directory
   and renames `FUTUREGAME:` to it (one `MoveFile`). Its failure branch (write the `CORRUPT` marker
   into the save folder and stop, leaving the current game untouched) is unreachable, so a damaged
   `SAVEGAME.sav` still replaces `GAMEINPROGRESS:` with whatever was extracted (static reading;
   what `ExtractAll` leaves behind on a damaged file needs a runtime check).
4. From the main menu: close the panel, create the server (`CAppManager::CreateServer`), pause both
   world timers. In game: pop every modal panel and hide the in-game menu (the running server is
   kept; `LoadModule` unloads its module in step 6). Then, in both cases, server `+0x100c4` = 1
   (**`GetLoadFromSaveGame`** returns this; `PlacePlayerInModule` `0x004b3d10` clears it on
   arrival) and the client sends message 3/5 (number, folder name, `LASTMODULE`).
5. The server handler (`HandlePlayerToServerModuleMessage` `0x00524800`, minor 5, refused while a
   module load is in progress) sets the module-load-in-progress flag `+0x100b4` and calls
   **`CServerExoAppInternal::LoadGame`** (`0x004ba640`): sets the load-progress phases, mounts the
   save folder as a resource directory, **`LoadPartyTable`** (`PARTYTABLE`, 3.9),
   **`LoadFromSaveDirectory`** (`GLOBALVARS`, section 2), unmounts it, sets party table `+0x10c` = 1
   ("party positions come from the save", 1.8), restarts the autosave timer (`+0x1b930`/`+0x1b938`), and calls
   **`LoadModule(LASTMODULE)`**.
6. `LoadModule` ([modules.md](modules.md)) first **unloads** the running module (every object,
   the event queue, the party's per-module state — 1.8), finds `GAMEINPROGRESS:<m>.sav` and loads in
   mode 3: the IFO (including the module's saved event queue, time and locals), `REPUTE.fac`, the
   area, then the GIT objects with their saved object ids. Before the GIT objects are created the
   nine NPC-slot object links are reset to `OBJECT_INVALID` (`0x005639c0`, server loop tick 2).
7. `StartModuleRunning` (`0x004b6270`): the module comes from a save (module `+0x1c8`) and it is
   not a transition, so
   **the player is restored from the IFO's `Mod_PlayerList`** (`RestorePlayerFromSave`
   `0x004b5f50` → `CSWSPlayer::LoadCharacter(index, …)` `0x00561e30`: a new creature with the saved
   `ObjectId` as a character object, stats, items, effects, actions, scripts, position, area id) and
   **the party is restored** (`CSWPartyTable::RestoreParty` `0x00565760`, 1.8). `OnClientEnter` is
   queued (`SignalPlayerEnterModule` `0x004b5c50`, which also does the `LoadCharacter` call).
8. The arrival handshake of [gameloop.md](gameloop.md) 5.5 places the PC at its saved position and
   adds it to the area; the party members keep their saved positions (`+0x10c` skips the formation
   placement in `PlacePartyAroundLeader` `0x00565b00`, which then clears the flag).

### 1.7 Loading a transition autosave

For rows with `PCAUTOSAVE`, `LoadSelectedGame` pops the panel, hides the in-game menu, shows the
row's load screen, destroys the server when called in game (which deletes `GAMEINPROGRESS:`,
`CURRENTGAME:` and `TEMP:`, 1.1), creates a new one, pauses both world timers and calls
`CSWGuiSaveLoad::LoadTransitionAutoSave(LASTMODULE)` (`0x006ca250`): (high)

1. Unload the module (`UnloadModule` through `0x004ae8a0`), set the module-load-in-progress flag
   (`+0x100b4`).
2. The folder is always `SAVES:000001 - AUTOSAVE` (built from 1 and `"AUTOSAVE"`, not taken from
   the row). Make `GAMEINPROGRESS:` (empty it if it exists) and **extract `SAVEGAME.sav` straight
   into it** (no `FUTUREGAME:` swap, no `CORRUPT` marker); copy `<folder>\pifo.ifo` to `TEMP:pifo`.
3. Mount the save folder; `LoadPartyTable`; globals; read `savenfo.res` `AUTOSAVEPARAMS` and
   restore: the start waypoint (`SetMoveToModuleWaypoint`; `"*"` = none), the calendar
   (`StoreGameTime`), `TIME_PAUSETIME` / `TIME_PAUSEDAY` into the stored pause time and day
   (`+0x100ac`/`+0x100b0`), the six movies queued on the client, the status summary into the
   in-game GUI, `LOADMUSIC` to the client; unmount.
4. Set the load-progress phases, set "this is a transition" (`+0x1007c` = 1) and start loading
   `LASTMODULE` (`BeginLoadModule` `0x004ba820`, through `0x004aebf0`).

The arrival then runs exactly like a transition: `StartModuleRunning` sees `+0x1007c` and does not
restore from the IFO; the client answers with login 0xf and `PlayerLoginToModule` re-creates the
PC from `TEMP:pifo` and calls `RestoreParty`; `PlacePlayerInModule` moves the PC to the waypoint and
the party into formation (1.8). `GetLoadFromSaveGame` is **not** set on this path. (high)

### 1.8 What a module transition does to the party

[gameloop.md](gameloop.md) 5.3–5.5 has the order of the whole transition; the party steps are:
(high unless marked)

**Leaving** (`SavePlayerCharacters` `0x004b2ba0`, step 5 of `StartModuleTransition`; the main loop
has already run `SaveAllNPCStates(0)` just before calling `StartModuleTransition`):

1. Every player: `+0x80` = −1; if it has a creature, an element (struct id 0xBEAD) is added to the
   `Mod_PlayerList` of an `IFO ` GFF, the creature gets `ClearAllActions(1)` and is written into it,
   and the player remembers its index (`+0x80`). The GFF is saved as `TEMP:pifo` only when at least
   one creature was written.
2. `SaveAllNPCStates(1)` (`0x00565530`): `SaveNPCState(n, bClearActions = 1)` for slots 0–8; a slot
   whose link (`+0xc + 4n`) names a creature in the world is written to
   `GAMEINPROGRESS:AVAILNPC<n>.utc`.
3. `SaveInventory(1)` (when the party repository exists) → `GAMEINPROGRESS:INVENTORY`, then the
   party repository is emptied (`CItemRepository::Clear` resets its counts only; the item objects
   die with the module).

`UnloadModule` then destroys the players' creatures and the module with everything in it, and
clears the party table's per-module state: the inventory list (`0x00563600`, also clears "party
restored" `+0x110`) and, when the next module loads, the nine slot→object links
(`ClearNPCObjectIds` `0x005639c0`, from the main loop just before `LoadModuleInProgress`). The
persistent table (members, available flags, gold, XP pool, solo mode, leader, galaxy map, pazaak)
is untouched. (high)

**Arriving** — `CSWPartyTable::RestoreParty` (`0x00565760`, once per module: guarded by `+0x110`),
called from `PlayerLoginToModule` (transitions) or `StartModuleRunning` (saves):

1. Mount `GAMEINPROGRESS:` as a directory.
2. If no NPC is the player character (`+0xf0` = −1): for each party member in list order,
   `SpawnAvailableNPC(slot, bUseLocation = 0, …, bRevive = !GetLoadFromSaveGame)` — the creature is
   re-created from `AVAILNPC<n>.utc` at the position saved in that file, snapped to a safe spot
   within 20 m, with the XP catch-up (3.4); its client twin is marked a party member and added to
   the client party (`0x0060ef50` sets client `+0x3a4`, then `0x006364c0` takes a free place,
   gives a follower FOLLOWLEADER and the perception ranges, [actions.md](actions.md) 1.7); and it
   becomes player-controlled (`SetPlayerControlled(1, 1)`). If an NPC is the player character, no
   member is spawned: that slot's link is set to the player's creature instead.
3. Load `INVENTORY` (GFF `INV `) into the party repository (created if needed, else emptied first;
   nothing happens when the file is missing): each `ItemList` struct becomes a new `CSWSItem`
   (`CSWSItem::LoadItem`; one that fails to load is deleted), is added with stacking and gets the
   player as possessor.
4. Unmount. Merge the PC's own repository and gold into the party's, then each slot creature's
   (`MergeCreatureIntoParty` `0x005641e0`, 3.6).
5. For the PC and each slot creature: `EquipDefaultClothes` (`0x00501c40`): a creature whose saved
   body armour could not be re-equipped when it was loaded (flag `+0xab8`, 4.8) gets
   `g_a_clothes01` from the party inventory, or a new one, in the body slot.
6. `+0x110` = 1.

**Placing** — `CSWPartyTable::PlacePartyAroundLeader` (`0x00565b00`), from `PlacePlayerInModule`
after the PC has its final position: restart the client party trail at the PC's position and facing
(movement.md 6). Then, only when `+0x10c` (set by `LoadGame`) is clear: each member *i* goes to its
formation point (the client party table's formation offset for its slot, rotated by the PC's
facing, added to the PC's position), snapped to a free walkmesh spot within 10 m (`0x004aeb60`),
facing the PC's direction; stealth is turned off for the whole party (`SetPartyStealthMode(0)`
`0x00563c60`) and **solo mode is switched off** (`+0x190` = 0). After a save load (`+0x10c` set)
none of this happens: members keep their saved positions and solo mode stays as saved. `+0x10c` is
cleared either way. (high for the steps, med for the formation geometry, which belongs to
movement.md)

Dead members: after a transition `bRevive` is set, so a member whose saved current HP (temporary HP
included) is below 1 gets, when spawned (`GetNPCObject` `0x00564700`), its `+0xf0` flag set and
then a RESURRECTION effect (type 4, instant, `ApplyEffect`), which only works because the flag is
set first ([rules.md](rules.md) 1.3); after a save load dead members stay dead. (high)

### 1.9 Corrections to gff-save.md

The format page was written from the one save before the code was read. Where the code says
otherwise or more: (high unless marked)

- **GVT numbers are signed**: one byte each, written as the low byte of the script value and read
  back sign-extended: −128..127, as `nwscript.nss` says, not 0..255.
- **GVT boolean bit order** is settled: boolean *k* of `CatBoolean` is bit `0x80 >> (k & 7)` of byte
  `k >> 3` of `ValBoolean` (most significant bit first). `ValBoolean` is `count/8 + 1` bytes.
- **GVT name order** is the order of the engine's hash table, not arbitrary (section 2); readers
  must map by name, which the engine itself does. `ValLocation` is always 2400 bytes (100 slots of
  position x, y, z + orientation x, y, z; the slots after the last location are zero); `ValString`
  has one struct per string global.
- **PT labels longer than 16 characters**: the code writes `PT_CONTROLLED_NPC`, `PT_COST_MULT_LIST`
  and `PT_COST_MULT_VALUE`; the GFF writer truncates labels to 16 (`CResGFF::AddLabel` `0x00410e20`),
  hence `PT_CONTROLLED_NP`, `PT_COST_MULT_LIS`, `PT_COST_MULT_VAL` in the file. The engine's reader
  truncates the same way (`GetFieldByLabel` `0x00411630`); a reader must compare the first 16
  characters.
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
- **GlxyMapPlntMsk**: bits 0–15 = planet *n* available (`+0x60`), bits 16–31 = planet *n*
  selectable (`+0xa0`); `GlxyMapNumPnts` must be 16 or the mask is ignored on load. The loader only
  sets flags from the mask; a clear bit leaves the flag as it was.
- **PT_TUT_WND_SHOWN** (6 bytes) and **PT_LAST_GUI_PNL** are the in-game GUI's tutorial-shown
  flags (`+0xba8`) and last panel (`+0x2c`); the message lists are the GUI's feedback and dialogue
  logs (a missing `PT_FB_MSG_TYPE` defaults to 0x10000000).
- **PT_AVAIL_NPCS/PT_NPC_AVAIL** is the slot's "available" flag; `RemoveAvailableNPC` clears it but
  leaves `AVAILNPC<n>.utc` on disk. Slots are not fixed people: scripts reuse them (the Endar Spire
  save gff-save.md was written from has Trask in slot 0, `NPC_BASTILA`; med, that save is no longer
  in the install).
- **savenfo** extra fields: `PCAUTOSAVE`, `SCREENSHOT` and `AUTOSAVEPARAMS` exist only in
  transition autosaves (which lack `SAVEGAMENAME` and `LIVE*`); `REBOOTAUTOSAVE` is read but never
  written on PC. `PORTRAIT<i>` follows the client party order (leader first), up to 3.
- **SAVEGAME.sav** may also hold `PC.utc` (written to `GAMEINPROGRESS:` while an NPC is the player
  character, `SwitchPlayerCharacter`); transition autosaves have a loose `pifo` next to it. The
  nested module ERF has exactly three entries and its key type is 2057 (`sav`).
- **availnpcN.utc** is written when the NPC becomes available, and again at every save and
  transition while its creature exists. A party member's own `ItemList` and `Gold` are empty: both
  live in the party (3.6). A slot creature that is in the world but not in the party keeps what it
  was given there (the install's saves have Bastila's `availnpc0.utc` with `g_w_dblsbr004` in its
  `ItemList`).
- **The GIT of a saved area does not contain the PC or the party members** (player-controlled
  creatures are skipped, `CSWSArea::SaveCreatures` `0x00507680`); spawned NPCs that are not in the
  party *are* in the GIT.
- **INVENTORY.res** is in the party inventory's order: sorted by base item, then by localized name
  (5.2). Each `Equip_ItemList` element's **struct id is the slot mask** (0x2 body, 0x10 right
  weapon …, 4.1).
- **FollowInfo** of a saved party member is always the default record (3.6); a creature without a
  follow record (not a party follower) has no `FollowInfo` at all.

## 2. Global variables

`CSWGlobalVariableTable` lives at server internal `+0x100fc` (`CServerExoApp::GetGlobalVariableTable`
`0x004aee60`; constructor `0x0052b170` from the server constructor). (high)

### 2.1 The catalogue

At start-up (`CAppManager::CreateServer` → `0x004b1650`) `LoadCatalogue` (`0x0052ae50`) reads
`globalcat.2da`: for each row, `Name` (must be shorter than 22 characters, i.e. at most 21) and
`Type` (`Boolean`, `Number`, `Location`, `String`, compared without case). A row without a `Name`
or `Type` cell is skipped silently; a name too long, a duplicate name, an unknown type or a full
category builds a message ("… longer than 21 letters!", "… duplicated in catalogue!", "… has bad
type in catalogue!", "… won't fit in table!") that is thrown away, and the row is skipped. Each
name gets the next index of its type. Capacities: **900 booleans, 500 numbers, 100 locations,
5 strings** (the shipped catalogue uses 809, 369, 5, 2). Nothing ever removes a name. (high)

Names live in an open-addressing hash table of **1775** entries of 0x18 bytes at `+0`: the name (up
to 22 bytes with its NUL) and at `+0x16` a 16-bit word = type in bits 14–15 (0 boolean, 1 number,
2 location, 3 string) and index in bits 0–13. The hash is a CRC-32 (reflected polynomial
0xEDB88320, table at `+0xb268`, initial value 0, no final inversion) over the **upper-cased** name
(`toupper`), modulo 1775; collisions probe linearly to the next slot. Lookups compare names without
case. (high; the name order of all four saves in the install reproduces exactly when the shipped
catalogue is inserted in row order this way, checked with a probe)

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

A name that is not in the catalogue, or has another type, only builds "Script var … not in
catalogue!" / "… is not BOOLEAN!" and the like (the message is thrown away) and returns
(`GetValue*`/`SetValue*` `0x00529110`–`0x005298a0`): the getters return 0, a zero location or an
empty string, the setters change nothing. An implementation should treat unknown names as reads of
0 and ignored writes. (high)

### 2.3 Saving and loading

`SaveToDirectory(folder)` (`0x0052ad10`, from `DoSaveGame` and `WriteTransitionAutoSave`) writes
`<folder>\GLOBALVARS` (`WriteTable` `0x005299b0`, GFF `GVT `, version `V2.0`, with catalogue): it
walks the hash table from slot 0 to 1774 and appends each name (struct id 0, field `Name`) to
`CatBoolean`/`CatNumber`/`CatLocation`/`CatString` and its value to the packed array of its type,
so the file order is hash order. Fields: `ValBoolean` (VOID, `count/8 + 1` bytes), `ValNumber`
(VOID, one byte per number), `ValLocation` (VOID, always 2400 bytes), `ValString` (list of
`String`). (high)

`LoadFromSaveDirectory` (`0x0052ade0`, from `LoadGame`) reads `GLOBALVARS` through the resource
manager (the save folder is mounted at that moment; `ReadTable` `0x0052abe0`). When there is no
such file nothing changes: the values of the previous game stay. With a `CatBoolean` list it uses
`ReadTableWithCat` (`0x0052a280`): **all values are cleared first**, then, per type and only when
that type's `Val*` field is present (at most 113 / 500 / 2400 bytes are read), every saved name is
looked up and its value copied; a saved name missing from the catalogue is **added** (if its type
has room), so globals of a mod survive a round trip. Edge cases (med, never met with the shipped
catalogue): a saved name is not length-checked; a name found under another type is written into
this type's store at that entry's index; with no room left the message is thrown away and the
value is written through slot −1 (an index read from the two bytes before the table). Without the
catalogue lists `ReadTableNoCat` (`0x00529ef0`) reads the four `Val*` fields positionally, in the
current hash-table order, without clearing first; its string cursor starts after the strings it
read, so string globals get empty values (med). Strings: at most 5 in both readers. (high)
## 3. The party

### 3.1 The party table

`CSWPartyTable` is embedded in `CServerExoAppInternal` at `+0x1b770`
(`CServerExoApp::GetPartyTable` `0x004aee70`); `PARTYTABLE.res` is its image. Constructor
`0x00563d20` (nulls the inventory and journal pointers, then resets), reset `0x00563200`. The
reset runs from the constructor, so for New Game and for every load (both create a fresh server,
`CAppManager::CreateServer` `0x00401380`), and again in `LoadPartyTable` before the file is read.
(high)

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
| `+0xf4` | nesting count of `GAMEINPROGRESS:` mounts (`MountGameInProgress`, 3.3) | 0 | — |
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
| `+0x194` | cheat used | 0 | `PT_CHEAT_USED` (and a 19th `PT_PAZAAKCARDS` element, 3.9), savenfo `CHEATUSED` |

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
| 694 `AddAvailableNPCByObject(n, creature)` | `0x0052dc40` → `0x00564300` | refuses an available slot or a missing creature. Sets available; merges the creature's gold and items into the party (3.6); computes `JoiningXP` (3.4); adds it to the PC's faction (`0x005bfa70`); sets its movement rate to creaturespeed row 0, `PC_Movement` (`SetMovementRate(0)` `0x005a5680`, movement.md 3.1); writes `GAMEINPROGRESS:AVAILNPC<n>` (type 2027) and returns the write's result (the slot stays available even if it fails). The creature is **not** linked to the slot | high |
| 695 `RemoveAvailableNPC(n)` | `0x00541b40` → `0x005646d0` | clears the available flag; nothing else (file, membership and creature untouched) | high |
| 696 `IsAvailableCreature(n)` / 709 `GetNPCSelectability(n)` | `0x0053ed70` → `0x005636b0` / `0x005637c0` | the flags (selectability only for available slots: an unavailable one reads 255) | high |
| 708 `SetNPCSelectability(n, b)` | `0x00543300` → `0x005637f0` | only for available slots | high |
| 698 `SpawnAvailableNPC(n, location)` | `0x00543ed0` → `0x00565130` | 3.4 | high |
| 767 `SetAvailableNPCId(n, creature)` | `0x00548180` → `0x005636f0` | links a creature id to an available slot, unchecked (used to re-link NPCs that live in a GIT, e.g. on the Ebon Hawk after a load) | high |
| 734 `SaveNPCState(n)` | `0x005421a0` → `0x00563e80` | writes the slot's linked creature (if any) to `GAMEINPROGRESS:AVAILNPC<n>` now, without clearing its actions | high |
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
| 739–744 galaxy map | `0x005467b0`…`0x00546970` → `0x00563ae0`…`0x00563b60` | planet flags (indices 0..15); 739 opens the galaxy map GUI; selecting a planet (`0x00563b60`, by the galaxy map GUI) needs it available and selectable; 744 reads `+0xe0` | high |
| 418 `GetGold`, 322 `GiveGoldToCreature`, 444 `TakeGoldFromCreature` | `0x00539030`, `0x0053e690`, `0x00544970` | 3.6, 5.5 | high |
| 393 `GiveXPToCreature`, 714 `GivePlotXP` | rules.md 4.2 | the pool, 3.4 | high |

Internal helpers: `IsCreaturePartyMember` `0x00563740`, `IsCreatureAvailableNPC` `0x00563790`,
`GetNPCIndex` `0x005638a0` (−1 if none), `IsCreatureLeader` `0x00563a00`,
`SetLeaderByCreature` `0x00563a40` (called by the client when the leader changes),
`ClearNPCObjectId` `0x005639e0` (by `DestroyObject` on an NPC creature), `DespawnNPC(n, bFade)`
`0x00563810` (unless n is a member: unlink, client fade-out, delete the creature),
`MountGameInProgress` / `UnmountGameInProgress` `0x005638d0` / `0x00563950` (add the
`GAMEINPROGRESS:` resource directory on the first mount and remove it on the last, counted at
`+0xf4`). (high)

### 3.4 Getting an NPC's creature, spawning, XP catch-up

`GetNPCObject(n, bSpawn, bRevive)` (`0x00564700`; 33 callers, many in the GUI): for an available
slot, return its linked creature; if none and `bSpawn`, create a creature, mount `GAMEINPROGRESS:`,
`LoadFromTemplate("AVAILNPC<n>")` (the full saved creature, including position, effects, items),
unmount, revive it if `bRevive` and its current HP < 1 (sets `IsRaiseable` `+0xf0` = 1, then applies
a resurrection effect, type 4; 1.8), link it and return its id; else `OBJECT_INVALID` (a failed
load deletes the creature but leaves the mount count raised). (high)

Such a creature has **not fired its OnSpawn**: the constructor (`0x004f7a10`) clears the spawn flag
`+0x34c`, and `LoadFromTemplate` (`0x005026d0`) reads neither `CreatnScrptFird` nor the listen
patterns (`Listening`, `ExpressionList`), which only `LoadCreature` (`0x00500350`, a GIT creature
of a save) reads. So the member's OnSpawn runs on its first `AIUpdate` (gameloop.md 2.4) every time
the party table makes it: after the selection screen, `SpawnAvailableNPC`, and each `RestoreParty`
(module entry, save load). That OnSpawn (`k_hen_spawn01`, Trask's `k_pdan_trask_9`,
`k_hen_candspwn`) is what sets the listen patterns, without which the member hears no
`GEN_I_WAS_ATTACKED` and joins no fight it is not ordered into. A member already linked to a creature
in the world is not made again and keeps its flag. (high)

`SpawnAvailableNPC(n, bUseLocation, position, orientation, bRevive)` (`0x00565130`; routine 698
passes bUseLocation = 1 and bRevive = 1, `RestoreParty` bUseLocation = 0): (high)

1. `GetNPCObject(n, 1, bRevive)`; `ClearAllActions` (forcing it through even if not commandable).
2. Position: the location's, or (bUseLocation = 0) the creature's own. If the point lies on a room
   of the area (`GetRoomAtPoint` `0x004bb600`), take the nearest safe, straight-line reachable spot
   within 20 m (`FindNearestSafePosition` `0x004be860`, the creature's pathfinding info; the point
   itself if none is found). If it lies on no room, the result stays at the area origin (0, 0, 0)
   (med, needs a runtime check).
3. `AddToArea` there, then set the orientation (the location's, or the creature's own).
4. **XP catch-up**: *p* = `npc.2da` `PercentXP` of the slot × 0.01 (1.0 when the cell is missing or
   0); *earned* = XP − `JoiningXP` (creature `+0x22c`). If *earned* < trunc(pool × *p*), give
   `CSWSCreature::AddExperience(pool − trunc(earned × 100 / PercentXP))`, which itself scales by
   `PercentXP` (rules.md 4.2), so the NPC ends near `JoiningXP` + *p* × pool; then, with the
   client's auto-level-up option (client options `+8` & 1) and `CanLevelUp`, `AutoLevelUp(1)`. The
   division uses the raw cell value, not *p*: it differs only when the cell is missing or 0, which no
   companion row is (all are 80). This runs on every spawn, also of a creature that was already
   linked.

`JoiningXP` (when the NPC becomes available, `0x00564300`): with *L* the creature's level and
*need* = 1000 × *L*(*L*−1)/2 (the d20 threshold of its level, computed, not read from
`exptable.2da`), `JoiningXP` = *need* − trunc(pool × *p*) if positive, else 0 (stored at creature
`+0x22c`, saved as `JoiningXP`). So a recruit whose level threshold exceeds the pool share at
joining is credited with that share and is later topped up only with its share of XP the party earns
afterwards (less any XP it holds above *need*); a recruit below the share is topped up to it on its
first spawn. (high)

**The XP pool** (`+0xf8`, `PT_XP_POOL`) is the sum of all party XP ever awarded
(`CSWPartyTable::AddExperience` `0x005653a0`, rules.md 4.2): active members and the PC get the XP
at once, inactive available NPCs only through the catch-up above when they are next spawned.
(high)

### 3.5 Membership, leader, player character

**AddPartyMember(n, creature)** (`0x00565620`) succeeds only if no NPC is the player character
(`+0xf0` = −1), the party does not already hold **2** NPCs (party = PC + 2), slot n is available
and not already a member, the creature exists and is not linked to another slot. Then: append n to
the member list, link the creature to slot n, tell the client to fade it in,
`SetPlayerControlled(1, 1)` (`+0xa88` = 1, AI level 4, a 0x3c-byte follow record at `+0x4c0`),
merge its gold and items into the party (3.6), put default clothes on if pending
(`EquipDefaultClothes` `0x00501c40`). If the party had no NPC before and the player's creature is
in stealth mode (creature `+0x4d1`, saved as `StealthMode`), solo mode is
set. Adding an existing member fails (returns 0) without change. The routine handler, on success,
also tells the client and re-applies `SetPlayerControlled`. (high)

**RemovePartyMember(n)** (`0x00565560`) needs `+0xf0` = −1, a non-empty party and an available
slot: removes **all effects except equipped (duration type 3), innate (4) and `SETSTATE_INTERNAL`
(0x09)** from the slot's linked creature and makes it commandable (`CSWSObject::RemoveAllEffects(0)`
`0x004d0940`), removes n from the list (the others shift down) and turns solo mode off when the
party becomes empty. The effects are stripped before the membership test, so the call on an
available non-member strips its linked creature and returns 0. The creature stays in the world and
stays linked; on success the handler releases it from player control (`SetPlayerControlled(0, 1)`:
AI level 2) and tells the client to fade it out. (high)

**SetPartyLeader(n)** (routine 13, `0x00545a70`): for n ≥ 0, find the slot's creature
(`GetNPCObject(n, 0, 1)`) in the client party table and make that entry the leader
(`CSWCParty::SetLeader` `0x00635480`); returns 0 if it is not in the party. For n = −1 (the PC):
every client party member that is player-controlled, flagged `+0x9d4`, and dead or dying first gets
a resurrection effect (type 4), and only then `IsRaiseable` (`+0xf0`) = 1; since the resurrection
handler acts only when `+0xf0` is already set (rules.md, effect 0x04) and effects apply at once, a
member whose flag was clear is not revived by this call (med, needs a runtime check). Then the
client party's `SetLeader(−3)` makes leader the member whose stats have `IsPC` (`+0x6c`) set, i.e.
the current player character; returns 1. `CSWCParty::SetLeader` does nothing when the client party
has fewer than 2 entries or the target is already entry 0; otherwise it rotates the entries until the
target is first, rebinds the player to it (`0x00561c40`) and records the new leader's slot at `+0xec`
(`SetLeaderByCreature`; −1 for a creature in no slot), the server half only when client party
`+0x8` is set. (high for the steps, low for why revival is tied to this case)

**SwitchPlayerCharacter(n)** (routine 11, `0x005667c0`) replaces the player's creature by an NPC (or
back): (high)

- To an NPC (n available; n already the current one returns 1 and does nothing): if the real PC
  is the current character it is written to `GAMEINPROGRESS:PC.utc` (if that write fails, return 0
  with nothing changed); if another NPC is, that one loses `IsPC` (stats `+0x6c`) and `+0x9d4` and is
  saved to its `AVAILNPC` file. The target's linked creature is taken, or spawned
  (`GetNPCObject(n, 1, 1)`) at the current character's position and orientation. The current
  character's creature is removed (fade-out and delete; for an NPC through `DespawnNPC`).
- Back to the PC (n = −1): with no NPC current it returns 1 and does nothing. Otherwise the NPC is
  saved and despawned the same way and a new creature is loaded from `GAMEINPROGRESS:PC` at the
  NPC's position and orientation (if the load fails, return 0; the NPC has then already been saved
  but not despawned).
- Common tail: reset the client party table; the new creature becomes player-controlled with
  `IsPC` = 1 and `+0x9d4` = 1; the party inventory's possessor becomes it; it is added to the area
  (when newly created) and becomes the player's creature (`CSWSPlayer +0x38`, client rebinding
  `0x00561c40`); **every party member is removed** (`RemovePartyMember` from the last; each former
  member's creature is then unlinked, faded out and deleted, without saving its state first);
  `+0xf0` = n; returns 1. The removal runs while `+0xf0` still holds the old value, so it only
  happens on a switch away from the PC (the party is always empty otherwise); a target that is itself
  a party member would have its creature deleted by this step (med: static reading, the shipped
  scripts are not checked for it).

While `+0xf0` ≠ −1 `AddPartyMember` and `RemovePartyMember` refuse; a save in this state keeps
`PT_CONTROLLED_NPC` and `PC.utc`, and `RestoreParty` links the slot to the player creature.

### 3.6 Shared gold and inventory

The party has **one purse** (`+0xfc`, `PT_GOLD`, capped at 999,999,999 by `SetGold` `0x004edd90`
and `AddGold` `0x004f3db0`, not by the merge below) and **one inventory**
(`+0x118`, `CSWPartyTable::GetPartyInventory` `0x00563340`, created on first use, kept sorted):
every routine that asks a player-controlled creature for its gold or its item list
(`CSWSCreature::GetGold` `0x004edd60`, `GetItemRepository(1)` `0x004ef770`) gets the party's; a
creature outside the party uses its own (`+0x9d0`, `+0xa30`), except that `GetItemRepository(1)` also
gives an available NPC outside the party the party's list while the server flag and in-game GUI
panel of gui.md's character-viewing mode are active (`0x0062b4d0`; med). Section 5.5 has the details (gold
routines, script iteration), 5.9 the credits items and pazaak cards. Equipped items are not in any
list (section 4). (high)

**Joining** — `MergeCreatureIntoParty(creature)` (`0x005641e0`), when an NPC becomes available,
joins the party, and for everyone in `RestoreParty`: with the creature temporarily not
player-controlled (`SetPlayerControlled(0, 0)`, then the old value back, AI level untouched), its
own gold is added to the purse (no cap) and every item of its own repository is moved into the
party inventory (`AddItem` with merging and the "new" flag, possessor = the player, no events); its
own list is emptied. The creature's own gold field is not reset, so it is saved again as `Gold`
(`AddAvailableNPCByObject` saves right after merging) and would be added again by every later merge
(`AddPartyMember`, each `RestoreParty`); this only matters if a companion template carries gold
(open question, needs a runtime check). (high)

**Saving a party creature** (`CSWSCreature::SaveCreature` `0x00500610`) temporarily turns player
control off (`SetPlayerControlled(0, 1)`) so that `Gold` and `ItemList` come from the creature's
own purse and (emptied) list, then restores the old value before writing `FollowInfo`. A side
effect: turning control off frees the follow record (`+0x4c0`) and turning it on allocates a fresh
one, so the saved `FollowInfo` is always the default (and absent for a creature not under player
control) and the live follower's state restarts after every save or `SaveNPCState`. (high for the
calls, med for the consequence)

### 3.7 Solo mode, AI style, follow state

- **Solo mode** (`+0x190`): `SetSoloMode(b, bFromScript)` (`0x00565500`) stores it; turning it off
  with bFromScript also turns stealth off for the player's creature and every member
  (`SetPartyStealthMode(0)` `0x00563c60`). Both callers (routine 753 and the HUD toggle
  `0x005f2a20`) pass bFromScript = 1, so turning it off always does. Loading a party table with solo
  mode 0 does the same. It is switched off automatically when the last member is removed and when
  the party is placed after a transition without the keep-positions flag (`+0x10c` = 0;
  `PlacePartyAroundLeader` `0x00565b00`, which also turns stealth off, 1.8); `AddPartyMember`
  may switch it on (3.5). What solo mode changes in play is the party's own scripts': k_ai_master's
  companion heartbeat queues `ActionFollowLeader` only while `GetSoloMode` is false, and clears a
  companion's actions while it is true and the companion's current action is FOLLOWLEADER, so
  companions stay where they are; the leader is still changed with Tab (`0x005f7960` and
  `SetPartyLeader` do not read the flag), and the straggler teleport is off (gameloop.md 6.7). The
  HUD's solo toggle runs `k_sup_solo` after the change, a script the game does not ship. (high for
  the code paths read)
- **AI style** (`+0xe4`) is only stored and read by scripts here (`PT_AISTATE`). (high)
- **Follow state** (`+0xe8`) is reset to 0, and the client party table reset, when an area header
  is loaded (`0x00563a80`, called only from `CSWSArea::LoadAreaHeader` `0x00508c50`). (high)

### 3.8 Party selection

`ShowPartySelectionGUI(sExitScript, nForce1, nForce2)` opens `CSWGuiPartySelection` (gui.md: the
panel, its checks and messages). The panel reads, per slot, available / selectable / member from
the table and the NPC's name and level from `GetNPCObject` (spawning hidden creatures when needed).
**Apply** (`CSWGuiPartySelection::ApplyAndClose` `0x006be560`): (high unless marked)

1. Every slot that was a member and is no longer selected: client fade-out,
   `SetPlayerControlled(0, 1)`, `RemovePartyMember(n)` (the creature stays where it is).
2. Every newly selected slot: compute its formation point next to the leader (client party
   formation offset by the leader's facing, or `0x006348c0` when the leader's reference point is
   unset), `SpawnAvailableNPC(n, 1, origin, …, bRevive = 1)`, snap the point to a free spot within
   5 m (`0x004aeb60`); if a straight walk from that point to the leader fails (`TestWalkLine`
   `0x004bcb70`, any result but 1 or −3), use the plain formation point instead and snap again; set
   position and the leader's facing; `AddPartyMember(n, creature)`; `ClearAllActions`, reset its
   path state, `SetPlayerControlled(1, 1)`, one `AIUpdate`; make the leader perceive it if it does
   not; client fade-in.
3. Re-send party state to the players (`UpdateClientsForPlayers` `0x004b6950`), close the panel and
   **run the exit script** (caller object id 0, not `OBJECT_INVALID`) if one was given, then unpause
   and restore input.

### 3.9 PARTYTABLE.res

`SavePartyTable(folder)` (`0x005648c0`) writes a GFF of type `PT  ` (V2.0), in this order:
`PT_GOLD` (DWORD), `PT_XP_POOL`
(INT), `PT_PLAYEDSECONDS` (DWORD, the total, 3.10), `PT_CONTROLLED_NPC` (INT), `PT_SOLOMODE`,
`PT_CHEAT_USED`, `PT_NUM_MEMBERS` (BYTEs), `PT_MEMBERS` (`PT_MEMBER_ID` INT, `PT_IS_LEADER` BYTE),
`PT_AVAIL_NPCS` (9 × `PT_NPC_AVAIL`, `PT_NPC_SELECT` BYTEs), `PT_AISTATE`, `PT_FOLLOWSTATE` (INT),
`GlxyMap` struct (`GlxyMapNumPnts` DWORD = 16, `GlxyMapPlntMsk` DWORD, `GlxyMapSelPnt` INT),
`PT_PAZAAKCARDS` (18 × `PT_PAZAAKCOUNT` INT, 1.9, then a 19th element whose `PT_PAZAAKCOUNT` is a
BYTE holding the cheat flag `+0x194`), `PT_PAZSIDELIST` (10 × `PT_PAZSIDECARD` INT),
`PT_TUT_WND_SHOWN` (VOID 6, in-game GUI `+0xba8`), `PT_LAST_GUI_PNL` (INT, in-game GUI `+0x2c`),
`PT_FB_MSG_LIST` (`PT_FB_MSG_MSG`, `_TYPE` DWORD, `_COLOR` BYTE), `PT_DLG_MSG_LIST`
(`PT_DLG_MSG_SPKR`, `_MSG`; combat.md 10.1), `PT_COST_MULT_LIST` (one `PT_COST_MULT_VALUE` FLOAT per
base item, base item `+0xc4`), then the journal (`SaveJournal` `0x00563d90`: `JNL_SortOrder` from a
global, `JNL_Entries` with `JNL_PlotID`, `JNL_State`, `JNL_Date`, `JNL_Time`), as
`<folder>\PARTYTABLE`. Before writing it folds the session into the played seconds (3.10). (high)

`LoadPartyTable` (`0x00565d20`) opens `PARTYTABLE` (`PT  `) and returns 0, leaving the table as it
is, when there is none; otherwise it resets the table and reads the same fields with these
defaults: played seconds from `PT_PLAYEDMINUTES` × 60 when `PT_PLAYEDSECONDS` is missing,
controlled NPC −1, solo mode 0 (and solo 0 turns stealth off, 3.7), member list truncated to the
list's real length (`PT_IS_LEADER` sets `+0xec`), at most 9 avail entries, selected planet −1, the
planet mask applied only when `GlxyMapNumPnts` is 16, 18 pazaak counts (the 19th element is
ignored), side deck entries 0 when missing (not the reset's −1), cost multipliers 1.0, then
`LoadJournal` `0x00563430`; the GUI logs are re-added through the in-game GUI (`0x0062b5c0`,
`0x0062b680`). It does **not** spawn anyone: membership is only data until `RestoreParty`. (high)

### 3.10 Time played

`TIMEPLAYED` / `PT_PLAYEDSECONDS` = `+0x114` + (now − session start) rounded to whole seconds
(`GetPlayedSeconds` `0x00563bf0`, wall clock via `GetSystemTimeAsFileTime`; a negative
difference counts as 0). Saving the party table folds the session into `+0x114` and restarts the
session clock (`0x007a3a20`/`0x007a3a24`); New Game and loading also restart it (`0x00563cf0`).
Pause and menus count: it is real time. (high)

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

**`CSWInventory`** (the equipped-items holder, NWN's `CNWSInventory`; a 0x4c-byte heap object
whose **pointer** is at creature `+0xa2c`, allocated by the creature constructor `0x004f7a10`;
constructor `0x005a4930`, one-slot vtable `0x0074a824` holding the deleting destructor
`0x005a4c00`): a vtable and 18 dwords of item **object ids** from `+0x04`, all 0 after
construction (a removal writes `OBJECT_INVALID`); only indices 0–14 are reachable. (high)

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005a49c0` | `CSWInventory::GetSlotPointer(mask)` | mask → address of its id cell (table above); any other mask, 0x800–0x2000 included, → null | high |
| `0x005a4c20` | `CSWInventory::GetItemInSlot(mask)` | id cell → `CSWSItem*` (null when empty or the id is stale) | high |
| `0x005a4be0` | `CSWInventory::PutItemInSlot(mask, item)` | stores the item's id in the cell (nothing for a mask without a cell) | high |
| `0x005a4950` | `CSWInventory::GetIsEquipped(item)` | 1 if the item's id is in any of the 18 cells | high |
| `0x005a4980` | `CSWInventory::GetSlotFromItem(item)` | `1 << index` of the cell holding the item, else 0 | high |
| `0x005a4ba0` | `CSWInventory::RemoveItem(item)` | sets the item's cell to `OBJECT_INVALID` | high |

Quirk: `GetSlotFromItem` returns `1 << storage index`, which is the true mask only for slots
0–10; a creature weapon in slot 14 comes back as 0x800, and so on. The engine compares its
result with 0x10 / 0x20 (`RunEquip`, `RunUnequip`, the instant flags), passes it to the
property-removal handlers (`UnequipItem`), where the catch-all removal by creator (below) hides
the error, and uses it in two player-facing places that only ever see slots 0–10: the inventory
message handler (`0x00523c20`, compares it with masks 1..0x2000) and the upgrade screen
(`CSWGuiUpgradeItems::OnPanelAdded` `0x006c6330`). So a reimplementation can return the true
mask. (high for the arithmetic, med for "harmless")

Correction to [objects.md](objects.md): creature `+0xa50` is **not** a list of equipped item ids;
it is the appearance block filled by `ReadStatsFromGff` (`0x005afce0`, which receives `+0xa50`
as an out parameter: appearance type at `+0xa60`, phenotype `+0xa62`, gender `+0xa63`, colours
`+0xa64..+0xa67`, head `+0xa68` ...); its first four dwords start as `OBJECT_INVALID` (meaning
not established). The equipment is the `CSWInventory` pointed to by `+0xa2c`. (high for "not equipment",
med for the field names)

**In saves.** `CSWSCreature::SaveCreature` (`0x00500610`) walks the masks 1, 2, 4 … 0x20000 and
writes one `Equip_ItemList` element per occupied slot whose **struct id is the slot mask**,
holding `ObjectId` and the full item. `ReadItemsFromGff` (`0x004ffda0`) takes the struct id
back as the slot. Checked in saves: in `kotor/extract/save-end_m01aa.sav` the PC's armour is
struct 0x2 and its short sword 0x10; in an installed save Carth (`availnpc2`) has pistols in 0x10
and 0x20 and Canderous (`availnpc1`) a creature hide in 0x20000 (the true mask, since the save
walks masks, not cells). (high)

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
   (`+0x26c`). Otherwise this creature must itself be in the party (the client party's member
   list, `0x00634620`, or an available NPC, `IsCreatureAvailableNPC` `0x00563790`), else fail;
   then if the item's possessor is in the party the same way, the source is **this** creature's
   `GetItemRepository(1)` (the shared party repository), and if the possessor is a container
   item held by an available NPC, that container's repository; anything else fails. (med for the
   party-member branch)
2. **Validate** with `CanEquipItem(item, &slot, bFromPlayer = 1, bSkipLevel = 0, bFeedback = 1)`
   (below). The check may rewrite the slot (a left-hand request becomes right-hand). Its result
   selects the branch: 0 fail, 1 the slot is free, 2 swap with the occupant, 3 clear both hands.
3. Result **2**: take the occupant of the slot. If the new item's base item stacks
   (`Stacking` ≥ 2, which is every equipable base item except the creature items) and the
   occupant is identical (`CSWSItem::CompareItem` `0x00553cf0`: same base item, upgrades,
   property lists, plot flag, charges, stolen flag, model/body/texture variation, tag and name),
   fail: nothing would change. Otherwise unequip the occupant (`UnequipItem`, below) and put it in
   the creature's `GetItemRepository(1)` (not the source repository); if that repository refuses
   it (full), remove it from the creature (`RemoveItem` `0x00510ef0`) and drop it in the area at
   the creature's position, z + 0.2 (`AddToArea` `0x00555720`). No occupant ⇒ fail.
   Result **3**: do the same for the right-hand item and then the left-hand item (each only if
   present; both absent ⇒ fail, which `CanEquipWeapon` never allows), then equip in the
   right hand.
4. If the item is a stack (`+0x28c` > 1), split one off (`SplitItem` `0x0055f280`) and equip
   that copy; the rest stays in the repository.
5. Remove the item from the source repository if it is listed there; if this creature is not
   already its possessor, make it so (`SetPossessor` `0x00553210`, no signal, no feedback).
6. `EquipItem(slot, item, bApplyProperties = 1, bLoading = 0, bQuiet)` (next section). bQuiet is
   the **instant flag** when the slot was free (result 1) and 0 after a swap (results 2 and 3),
   so an instant equip into a free weapon slot does not put the creature in combat state while
   the same equip as a swap does. (high for the arguments, from the disassembly; med for the
   effect, needs a runtime check)
7. Remember the instant flag per hand, keyed by the slot the item ended in (`GetSlotFromItem`):
   `+0xaac` for 0x10, `+0xaa8` for 0x20 (inline for result 1, `SetWeaponInstantFlag`
   `0x004efe00` for 2 and 3; meaning not traced, low).
8. **Combat mode check** (`+0x4d2`, the attack-mode byte also written by the counter action):
   mode 5 survives only with both hands empty; mode 6 only with a ranged right-hand weapon;
   modes 1, 2 and 3 only with an empty or melee right hand; other modes are not checked. A mode
   that no longer fits is reset to 0 (`SetCombatMode(0, 1)` `0x0050ee80`). Returns 1. (high for
   the tests, low for what the numbered modes are)
9. On any failure, returns 0, and when the creature has a client object (the player's controlled
   creature) the client is told to drop its "pending equip" icon (`0x0056fbd0`).

### 4.3 Validation: `CSWSCreature::CanEquipItem(item, &slot, bFromPlayer, bSkipLevel, bFeedback)` (`0x0051aa60`)

Callers: `RunEquip` (1, 0, 1), `ReadItemsFromGff` when loading (1, 1, 1), the
`ActionEquipMost*` helpers (`0x00500e50`, `0x00501250`, `0x004f3a60`; 0, 0, 1), the
level-change code under `SetExperience` (`0x005ab1e0`; 0, 0, 1: it re-checks every slot and
calls only `UnequipItem` on an item that no longer passes, so the item is not put back in a
repository — med, needs a runtime check) and the GUI (`CSWGuiEquip::OnSlotHilighted`
`0x006b9470`, `CSWGuiUpgradeItems::ReturnItem` `0x006c5e90` and `CSWGuiUpgrade::OnSlotClicked`
`0x006c6500`, all 0, 0, 0). The checks, in order; a failure returns 0 and sends a numbered
feedback message (`SendFeedbackMessage` `0x004ede10`; strrefs from the client formatter
`0x005fcd10`) when bFeedback is 1 and, except for the level message, bFromPlayer is 1: (high)

| # | Check | Address | Fails when | Feedback |
|---|---|---|---|---|
| 1 | item level | `GetItemLevel` `0x00554080` | bFromPlayer, the creature is a PC (stats `+0x6c`), not bSkipLevel, the server option "item level restriction" (server options `+0xc8`, set to 1 by `0x004b1b00`) is on, and the creature's total level < the item's level | 0x62 → 1470 "You have not achieved the required level to equip this item." |
| 2 | NonEquippable | item flags `+0x288` bit 0x40 | set (UTI `NonEquippable`, `SetItemNonEquippable` routine 266) | none |
| 3 | proficiency | `CheckProficiencies` `0x00510e30` | the base item has `EquipableSlots` 0, or the creature lacks any of the base item's `ReqFeat0..4` (unless it has feat 93 PROFICIENCY_ALL) | none here (the GUI marks the row) |
| 4 | alignment limit | `CheckUseLimitationAlignment` `0x005145a0` | the item has an active property 43 and its subtype ≠ the creature's alignment group (`GetAlignmentGroup` `0x005a5110`: GoodEvil ≤ 40 → 3 dark, ≥ 60 → 2 light, else 1 neutral); feat 93 bypasses | 0xcf → 1512 "…required alignment…" |
| 5 | class limit | `CheckUseLimitationClass` `0x00518210` | the item has property 44 and none of the creature's classes equals a property subtype; feat 93 bypasses | 0xd0 → 1513 "…required class…" |
| 6 | race / droid | `CheckUseLimitationRace` `0x005182f0` | `DroidOrHuman` 1 and race ≠ 6 (Human), or 2 and race ≠ 5 (Droid) — skipped when the item has a cast-spell property with spell 129 (`ITEM_ABILITY_RECOVERY_STIM`); **or** the creature's subrace bit (`1 << SubraceIndex`) is set in `DenySubrace`; **or** the item has property 45 and no 45 subtype equals the creature's race | 0xd1 → 1514 "You are not the correct race…" |
| 7 | feat limit | `CheckUseLimitationFeat` `0x00514650` | the item has property 57 and the creature lacks one of the named feats; feat 93 bypasses | 0x6b → strref 0 ("Bad StrRef": no real message) |
| 8 | slot | weapon slots: `CanEquipWeapon` `0x00510cd0`; others: `CanEquipInSlot` `0x00515860` | see below | non-weapon slots only: 0x7b → 1478 "Equipped item swapped out." (when the slot is occupied, as information) |
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
robe, clothing and disguise row except `Revan_Armor` (and the `Mask` row too) has `DenySubrace`
0x2, so a Wookiee (subrace 1) can wear none of them.
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
(`0x006b2c90`) and row builder (`0x00616520`), `CSWSCreature::UseItem` (`0x004fc210`), the
player's input handler (`0x0056ee40`) and the party code (`0x00566f20`): checks 4–7 as above;
the level check, gated here on the creature's PC flag `+0x9d4` instead of bFromPlayer; a size
rule absent from `CanEquipItem` (a base item with `WeaponType` ≠ 0 and `WeaponWield` ≠ 8 whose
`WeaponSize` exceeds the creature's size, `+0x4f8`, by more than 1 is unusable; never true for
medium creatures with the shipped sizes ≤ 4); and the proficiency check only for items whose
`EquipableSlots` has a bit in 0..17. (high)

**Armour in combat**: `AddEquipItemActions` (`0x004f0420`) and `AddUnequipActions`
(`0x004f06d0`) refuse a **body-slot** (0x2) change while the creature is in combat because it is
being attacked (`+0x4e0` = 1 and `+0xac0` = 1, [combat.md](combat.md) `SetCombatState`):
equipping into slot 0x2 gets feedback 0xc1 → 1506 "You cannot equip or unequip armor during
combat!" (pending icon removed, `0x0056fbd0`), unequipping the item that is in slot 0x2 gets
0xc2 → 1507 "You cannot unequip armor during combat!" (client told through `0x0056fd80`).
Weapon and other slots are not refused; in that state the change becomes a combat-round entry
instead, as [actions.md](actions.md) 3.8 describes. An EQUIP request for slot 0x1, 0x2, 0x10 or
0x20 of an item that is already equipped (in any slot) is ignored. (high)

### 4.4 `CSWSCreature::EquipItem(slot, item, bApplyProperties, bLoading, bQuiet)` (`0x004feb90`) and `UnequipItem(item)` (`0x004faa70`)

The low-level pair every path goes through (`RunEquip`, `RunUnequip`, loading, the default
clothes `0x00501c40`, the `ActionEquipMost*` helpers `0x00500e50` / `0x00501250`, the upgrade
screen `0x006c5e90` / `0x006c2df0` / `0x006c6330`, and for `UnequipItem` also the level-change
re-check `0x005ab1e0`). **EquipItem**, in order (high):

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
   (in-game GUI `+0xb4`): put the creature in combat state (`SetCombatState(1, 2)` `0x004f2610`,
   reason 2), i.e. a script that hands a weapon to a creature makes it combat-ready. (med for
   the reading)
7. Add the item's weight (`GetWeight` `0x005562a0`: weight `+0x290` × stack size, or own weight
   plus contents for a container) to the creature's equipped weight `+0xa3c`.
8. Signal script event 38 (EQUIP_ITEM) to the **module** (AI-master event 10, delay 0), object 0
   = the item, caller = the creature: the module's event handler stores the item at module
   `+0x19c` and runs `Mod_OnEquipItem` with the module as `OBJECT_SELF`; `GetLastItemEquipped`
   (routine 52, `0x0053f800`) reads `+0x19c`. This happens on load too. Returns 1.

**UnequipItem**, in order (high): `RemoveItemProperties(creature, slot)` (`0x00553c30`, slot
from `GetSlotFromItem`: the removal handler of every active passive property, then
`RemoveEffectsByCreator(item id)` `0x004d0820`, which drops every remaining effect whose creator
is the item); clear the slot cell (`OBJECT_INVALID`); `UpdateBaseArmorAC`; set the creature's
"recompute" flag `+0x344`; subtract the weight from `+0xa3c`; if the base item's `ItemType` is
44 (stealth unit) and the creature is in stealth mode (`+0x4d1` = 1), leave stealth through the
player's stealth toggle (`SetActivityMode(1)` `0x004f2a50`, so its guards apply: nothing
happens for a dead or dying creature, one that can't use the Stealth skill, or one with
`+0xa00` bit 0 set; med for the guards). Returns 1. `UnequipItem` does **not** call
`UpdateCombatInformation` and sends no event; `AIUpdate` (`0x004fe210`) sees `+0x344`, rebuilds
the combat information and clears the flag on the creature's next update. (high)

### 4.5 Unequipping: `CSWSCreature::RunUnequip(itemId, containerId, nAddFlags, ppItem, bInstant)` (`0x005023a0`)

Called by the UNEQUIPITEM action (`0x00513ec0`), the round dispatcher and `RemoveItem`
(`0x00510ef0`). (high unless marked)

1. Fail unless the item exists, this creature possesses it and it is equipped.
2. Target repository: the creature's (`GetItemRepository(1)`, the party repository for party
   members) when containerId is `OBJECT_INVALID`, else that container item's repository (the
   container must also belong to the creature); no repository ⇒ fail.
3. `CanUnequipWeapon` (`0x00513e30`): 2 when the item is the right-hand weapon and a left-hand
   weapon is held (whose `WeaponType` ≠ 0; it also resets two object ids in the controlling
   client's data, `+0x54` → `+0x10` / `+0x14`, to `OBJECT_INVALID`, meaning not traced); else 1.
4. Store the instant flag (as in equip), `UnequipItem`, add the item to the target repository
   (with nAddFlags); if refused, drop it at the creature's feet (z + 0.2).
5. Result 2 only: **the left-hand weapon moves to the right hand** (unequip it, `EquipItem(0x10,
   left, 1, 0, 0)`; bQuiet 0, so this also puts the creature in combat state unless the menus
   are open; the left hand's instant flag `+0xaa8` is not moved).
6. Return the item through ppItem; make the target (the container, or the creature) the
   possessor (`SetPossessor`).
7. Only when the creature has a client object (it is the player's controlled creature) and the
   server message object exists: tell the client (`0x0056fd10`, once per moved item, the
   promoted left weapon first) and **return 1**. For any other creature the unequip has been
   done but the function **returns 0**, so the UNEQUIPITEM action (`0x00513ec0`) ends as failed
   rather than done. (high for the code, from the disassembly; med for the consequence, needs a
   runtime check)

A failure in steps 1–2 returns 0 and, for the controlled creature, sends the "unequip failed"
notice `0x0056fd80`. `RemoveItem` (`0x00510ef0`) ignores the return value.

### 4.6 Item properties → effects

**Storage** (`CSWSItem::LoadDataFromGff` `0x0055fcd0`). Each UTI `PropertiesList` entry becomes a
0x1c-byte record: `+0x00` PropertyName (word), `+0x02` Subtype (word), `+0x04` CostTable (byte),
`+0x06` CostValue (word), `+0x08` Param1, `+0x09` Param1Value, `+0x0a` ChanceAppear (bytes),
`+0x0c` Useable (dword; default 1 for a usable property, 0 for a passive one), `+0x10` UsesPerDay
(byte, default 0xff), `+0x11` UpgradeType (byte, default 0xff). The records are split into two
arrays (high):

- **usable** ("active"; `+0x248` count, `+0x250` array; `GetActiveProperty` `0x00553960`): property types
  10 CastSpell (activate item), 37 security spike (ThievesTools), 46 Trap, 53 Computer spike —
  the "use this item" properties (`IsUsablePropertyType` `0x00553900`). They are never applied on
  equip. On load (`InitUsesPerDay(item, bOnlyUnset = 1)` `0x00555bf0`), every cast-spell property
  whose UsesPerDay is unset gets Useable = 1, and uses from its CostValue when that is an
  `iprp_chargecost` per-day row (rows 8–12 → 1–5 uses per day; any other CostValue leaves 0xff).
- **passive** (`+0x24c` count, `+0x254` array; `GetPassiveProperty` `0x00553990`): everything
  else; these are what equipping applies.

An item with no property at all is marked identified (`+0x288` bit 0). The item's own AC
(`+0x244`) is its base item's `BaseAC` when `ModelType` is 1 (armour), else 0 (so droid plating,
ModelType 0, has 0 here). Readers: `GetItemACValue` (routine 401, `0x0053a130`) adds the CostValue
of every passive property 1, **without** the upgrade rule below; `ActionEquipMostEffectiveArmor`
(`0x004f3a60`) ranks body armour by the same sum **with** the upgrade rule; and the item message
to the client (`0x00566f20`) carries it for armour items. (high)

**Upgrade gating.** A property whose UpgradeType is not 0xff counts only while bit
`1 << UpgradeType` is set in the item's `Upgrades` mask (`+0x294`). This rule is applied by
`ApplyItemProperties`, `RemoveItemProperties`, `HasProperty` (`0x00555c90`) and
`GetPropertyByType` (`0x005539c0`), and by the armour ranking above. Shipped data: 61 of the 1,055
UTI copies in the install (59 of 810 distinct resrefs) carry gated properties (upgrade types
0–24); the Endar Spire Jedi's lightsabers in the save (`g_w_lghtsbr01` / `02`) have 29 properties
each, all gated, and `Upgrades` 0, so none applies. How upgrades set the bits: 5.11. (high)

**Apply.** `ApplyItemProperties(creature, slot, bLoading)` (`0x00553bb0`) sends every passive property
that passes the upgrade rule to the AI master's item property handler (`CServerAIMaster+0x5c`,
`CSWSItemPropertyHandler`, vtable `0x00744284`): `OnItemPropertyApplied(item, property, creature,
slot, bLoading)` (`0x004e5410`) indexes a 60-entry apply table (and `OnItemPropertyRemoved`
`0x004e5450` a remove table), both filled by `InitializeItemProperties` (`0x004ea9f0`); a type
≥ 60 or an empty entry does nothing ([rules.md](rules.md) 1.12 gives the same mechanism and
`ApplyEnhancementBonus`). Every handler builds ordinary `CGameEffect`s (rules.md 1.1) with
(high):

- duration type **3** ("equipped") in the low bits of the subtype word, the other subtype bits
  left at 0 as the constructor (`0x00503e40`) set them (except Special_Walk, whose two effects
  are marked magical, subtype bit 8);
- creator = the item (`SetCreator` `0x00503a00`);
- `ApplyEffect(creature, effect, bLoading)` (`0x004d14f0`).

The value usually comes from a cost table: column `Value` (or `Amount`) of an `iprp_*` table at
row CostValue. "Bonus table" below is `iprp_bonuscost` (cost table row 1: value = row 1..10),
"melee table" `iprp_meleecost` (row 2: 1..5; the handlers read it from its own slot in the rules'
2DA set, `C2DAs+0x30`), "neg5" `iprp_neg5cost` (row 20: −1..−5, negated by the handler), "neg10"
`iprp_neg10cost` (row 21: −1..−10). The handlers pick the table themselves; the property's own
CostTable byte is used only by DamageImmunity. A handler whose value comes out 0 (cost-table value,
or CostValue where that is the value) creates nothing; the exceptions are the ones without a value
(BonusFeat, Immunity, True_Seeing, Freedom_of_Movement, Special_Walk, Light, Disguise) and
DamageImmunity, DamageReduced, DamageResist and Damage_Vulnerability, which apply even with 0.

**Hand.** Attack and damage effects carry the hand the slot implies (attack: int1, damage:
int5): 0x10 → 1 (on-hand), 0x20 → 2 (off-hand), 0x4000 / 0x8000 / 0x10000 → 3 / 4 / 5
(creature weapons), 0x8 (gauntlets) → 7 (unarmed); any other slot leaves 0, "misc", which
applies to every attack ([rules.md](rules.md) 1.7). When the item's base item has `WeaponWield`
3 (base item `+0x08`; the shipped rows are the quarterstaff, double-bladed sword, vibro
double-blade, double-bladed lightsaber, Gaffi stick and Wookiee warblade), the attack/damage
handlers (5–8, 11–13, 15, 38–40) apply a **second copy with hand 2** (applied first), so both
ends get the bonus. The copy is made with `CopyEffect` (`0x00504090`) into an effect without an
id, so it takes the original's effect id. "Race any" below is the rules' "invalid racial type"
byte (`g_pRules+0xaa`). (high)

| Prop | Name | Apply / remove | Effect(s) created | Conf. |
|---|---|---|---|---|
| 0 | Ability | `0x004e6390` / `0x004e8db0` | 0x24 ability increase: int0 = ability (subtype 0–5, STR..CHA; any other subtype leaves int0 = 0, STR), int1 = bonus table | high |
| 1–4 | Armor (+ vs alignment group / damage type / race) | `0x004e6510` / `0x004e8f70` | 0x30 AC increase: int0 = base item `AC_Enchant` (0 dodge for every shipped row), int1 = bonus table, int2 = race any, int5 = 0x4007 (all damage); prop 2: int4 = alignment group (subtype 1–3); prop 3: int5 = subtype; prop 4: int2 = subtype | high |
| 5–7 | Enhancement (+ vs alignment group / race) | `0x004e5490` / `0x004e7f40` | 0x0a attack increase (int0 = melee table, int1 = hand, int2 = race any) **and** 0x0d damage increase (int0 = same value, int1 = base item `DamageFlags` (8 when 0), int5 = hand, int2 = race any); vs alignment: subtype 1 → int3 = 1, 2/3 → int4 = 2/3; vs race: int2 = subtype | high |
| 8 | AttackPenalty | `0x004e60c0` / `0x004e8bc0` | 0x0b attack decrease: int0 = −neg5, int1 = hand, int2 = race any | high |
| 9 | BonusFeats | `0x004e6d50` / `0x004e9700` | 0x53 (bonus feat): int0 = feat (subtype); only on creatures with stats | high |
| 11–13 | Damage (+ vs alignment group / race) | `0x004e5c60` / `0x004e86f0` | 0x0d damage increase: int0 = **CostValue itself** (an `iprp_damagecost` row: 1–5 flat, 6+ dice, the script `DAMAGE_BONUS_*` numbering), int1 = `1 << subtype` (prop 11) or `1 << Param1Value` (12, 13), int5 = hand; alignment / race as for enhancement | high |
| 14 | DamageImmunity | `0x004e6e20` / `0x004e97a0` | 0x10 damage immunity increase: int0 = `1 << subtype`, int1 = the property's own cost table (`iprp_immuncost`: 5–100 %) | high |
| 15 | DamagePenalty | `0x004e6f60` / `0x004e9990` | 0x0e damage decrease: int0 = −neg5, int1 = weapon damage flags (`GetDamageFlags` `0x00554050`: base item `DamageFlags`, 8 when 0), int2 = race any, int5 = hand | high |
| 16 | DamageReduced | `0x004e7190` / `0x004e9bb0` | 0x0c damage reduction: int0 = `iprp_soakcost Amount`, int1 = subtype + 1 (the "+N" it ignores) | high |
| 17 | DamageResist | `0x004e72b0` / `0x004e9cf0` | 0x02 damage resistance: int0 = `1 << subtype`, int1 = `iprp_resistcost Amount` | high |
| 18 | Damage_Vulnerability | `0x004e73d0` / `0x004e9e30` | 0x11 damage immunity decrease: int0 = `1 << subtype`, int1 = `iprp_damvulcost Value` | high |
| 19 | DecreaseAbilityScore | `0x004e74f0` / `0x004e9f60` | 0x25 ability decrease: int0 = ability, int1 = −neg10 | high |
| 20 | DecreaseAC | `0x004e7670` / `0x004ea130` | 0x31 AC decrease: int0 = subtype (AC type, `iprp_acmodtype`), int1 = −neg5, int2 = race any, int5 = 0x4007 | high |
| 21 | DecreasedSkill | `0x004e77c0` / `0x004ea290` | 0x38 skill decrease: int0 = skill, int1 = −neg10, int2 = race any | high |
| 24 | Immunity | `0x004e7900` / `0x004ea3f0` | 0x16 immunity: int0 from the subtype (`iprp_immunity` → `IMMUNITY_TYPE_*`): 0 backstab → 30 sneak attack, 1 level/ability drain → 29 negative level **and** 19 ability decrease (two effects), 2 mind → 1, 3 poison → 2, 4 disease → 3, 5 fear → 4, 6 knockdown → 28, 7 paralysis → 6, 8 critical hits → 31, 9 death → 32; int1 = race any | high |
| 25 | ImprovedMagicResist | `0x004e66b0` / `0x004e9110` | 0x21 Force resistance increase: int0 = `iprp_srcost Value` (cost table row 11; 10–32) | high |
| 26, 27 | ImprovedSavingThrows (vs element) / Specific | `0x004e9230` / `0x004ea890` | through `ApplySavingThrowEffect` (`0x004e67d0`): 0x1a save increase (0x1b decrease if the value is negative, with its absolute value): int0 = bonus table, int1 = subtype 1/2/3 → Fort/Reflex/Will (else 0 = all), int2 = 0, int3 = race any | high |
| 29 | Light | `0x004e62d0` / (empty, `0x00401590`) | 0x36 light: int0 = 5000 (applied only while `HasProperty(29)`, which the call itself guarantees) | high |
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
equip); 58 Droid_Repair_Kit. Shipped usage of the unhandled ones, counted over all 1,055 UTI
copies: 28 ×47, 32 ×107, 49 ×36, 51 ×33, 22 ×1, 31 ×5; 41 is never used. (high for the table,
high for the counts from a probe of all UTIs)

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

**Remove.** `UnequipItem` (`0x004faa70`) calls `RemoveItemProperties(creature, slot)`
(`0x00553c30`) with the slot from `CSWInventory::GetSlotFromItem` (`0x005a4980`); it runs the
remove handler (`OnItemPropertyRemoved(item, property, creature, slot)`) of every passive
property that passes the upgrade rule, then `RemoveEffectsByCreator(item)` (`0x004d0820`). The remove handlers look for the creature's equipped-duration effects of the
matching type whose creator is the item and whose parameters match (value, hand, damage flags,
race / alignment filter), and remove each by id (`RemoveEffectById` `0x004d06c0`, which also takes
the double-weapon copy, since it shares the id). Not every handler compares the right field (the
blaster-deflection one compares int0, the subtype, with the CostValue), so some effects are left to
the final sweep. That sweep advances its index even after a removal, so an item effect directly
behind a removed one is skipped ([rules.md](rules.md) 1.9). A reimplementation that **removes
every effect whose creator is the item** on unequip does what the code means to do; whether a
skipped effect really survives an unequip in play needs a runtime check. (high for the code, med
for the consequence)

**Loading.** Equipped-duration effects are not restored from a save: `CSWSObject::LoadEffectList`
(`0x004d1be0`) discards every saved effect with `SkipOnLoad` = 1 or duration type 3, and the
equip during `ReadItemsFromGff` (`EquipItem` with bApplyProperties = 1, bLoading = 1) re-creates
them. The shipped save stores them anyway (16 such effects, two each on eight creatures of the
Endar Spire GIT — six Sith and the two `end_bridgerep` Republic soldiers — all `SkipOnLoad` 0).
(high)

### 4.7 Armour and weapons, summarised

- **Armour defense**: stats `+0xf6` = the body-slot item's base item `BaseAC`, 0 with nothing in
  the body slot (`UpdateBaseArmorAC` `0x004ece80`, run by every `EquipItem`; it does not check
  ModelType, so droid plating counts); the DEX cap is the body armour's `DEXBONUS`, applied by
  the defense code only when that armour has ModelType 1 and BaseAC > 0; Armor properties add
  dodge AC effects: the unconditioned ones (property 1, and 3 whose damage-type filter the apply
  handler ignores) go into the dodge total, capped with other dodge at 10, the versus-alignment /
  race ones (2, 4) are matched per attack; all in [combat.md](combat.md) 5. Shield base `+0xf7`
  has no writer but the stats constructor (`0x005aca80`, 0), so it is always 0, and natural base
  `+0xf5` is the GFF's `NaturalAC` (`ReadStatsFromGff` `0x005afce0`); neither changes with
  equipment (med: no other writer in the decompile).
- **Weapon damage** is the base item's `NumDice`d`DieToRoll` (creature weapons: property 51
  instead); enhancement and attack-bonus properties become attack/damage effects for that hand;
  everything else about the roll is [combat.md](combat.md) 4–6.
- `UpdateCombatInformation` keeps the sheet numbers in step; the equip panel shows them
  ([gui.md](gui.md)).
- Encumbrance: `+0xa3c` sums the equipped items' weight (`EquipItem` adds `GetWeight`
  `0x005562a0`: the item's weight from `TenthLBS` times the stack, or plus its contents for a
  container; unequipping and the item's event handler `0x0055ee10` subtract); nothing reads it to
  limit movement (med).

### 4.8 Loading equipment and the default clothes

`ReadItemsFromGff` (`0x004ffda0`) first clears `+0xab8`, then for each `Equip_ItemList` element
(its struct id is the slot mask):

- **New item** (no object with the element's `ObjectId` exists; without ObjectIds, always):
  create it and load it with `CSWSItem::LoadItem` (`0x00560970`: an `EquippedRes` or
  `InventoryRes` template plus `Dropable` / `Pickpocketable` when the element names one, as a
  UTC does, else the full item struct, as a save has); a caller flag (`LoadFromTemplate`'s
  nFlags) takes only the `EquippedRes` template plus `Dropable` instead. An item that fails to
  load is deleted. Then make the creature its possessor and run `CanEquipItem(item, &mask,
  bFromPlayer 1, bSkipLevelCheck 1, bFeedback 1)`. If it passes, `EquipItem(mask, item,
  bApplyProperties 1, bLoadingGame 1, bQuiet 0)`; if it fails, flag `+0xab8` when the slot was
  the body (2), and put the item in `GetItemRepository(bParty)` with bParty = "party restored in
  this module" (party table `+0x110`), so a party member's item goes to the party inventory only
  after the party has been restored.
- **Existing item** (the object exists and its possessor is this creature; else the element is
  skipped): the same check and equip; on failure it goes to `GetItemRepository(1)`, and the body
  flag is **not** set.

`EquipDefaultClothes` (`0x00501c40`) runs when a creature joins the party (`AddPartyMember`
`0x00565620`) and when the party is restored on arriving in a module (`RestoreParty`
`0x00565760`, the player character and then each party member). With the flag set it equips
`g_a_clothes01` in the body slot (`EquipItem(2, item, 1, 0, 0)`): the one found by tag in
`GetItemRepository(1)` (taken out of it), else a new one from the template, marked droppable;
then it clears the flag. So a character who can no longer wear the saved armour isn't left
bare; a creature that never passes through the party code keeps the flag and gets no clothes.
(high)

### 4.9 On the client

The server tells the client about each change (server message 0x0c, minor 2 from `0x0056fbd0`
refused equip, minor 7 from `0x0056fd10` unequip done, minor 8 from `0x0056fd80` unequip
refused). The client rebuilds the body from `appearance.2da` of the creature's appearance row:
model column `model<L>` and texture column `tex<L>` where L is `'A' + BodyVar − 1` (base item
`BodyVar` `+0xaf`, letters A–J, clamped to 1–10, A without armour), and the texture name gets
the item's `TextureVar` as two digits (`%s%02d`, 0 read as 1); when neither a TGA nor a TPC of
that name exists it falls back to variation `01` (`0x00697610`, called from the body builders
`0x00697c80` and `0x00698150`). Item models and icons are named from the base item's
`ItemClass` and the item's `ModelVariation`: `<ItemClass>_<nnn>` and `i<ItemClass>_<nnn>`, or
`<ItemClass>_<g>_<nnn>` / `i<ItemClass>_<g>_<nnn>` with a gender letter when `GenderSpecific`
(base item `+0x74`) is set and a gender is given (`0x005b30e0`, `0x005b3050`). (med; the client
side was not traced beyond these functions)

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
| `+0x264` / `+0x265` / `+0x266` | model variation / body variation / texture variation | `ModelVariation`; when that field is absent, `ModelPart1` (default 1) with 0 → 1. Body variation is always `baseitems.BodyVar` (letter A..J → 1..10, else 1) for `ModelType` 1 rows: the saved `BodyVariation` is never read back. `TextureVar` is read only for `ModelType` 1 rows (default 1) | 1 / 0 / 0 |
| `+0x268` | possessor id (`OBJECT_INVALID` on the ground) | — | invalid |
| `+0x26c` | the item's own `CItemRepository*` when `baseitems.Container` ≠ 0 (no KOTOR row sets it: dead path) | `ItemList` | null |
| `+0x270` / `+0x278` / `+0x280` | identified description / description / name | `DescIdentified` / `Description` / `LocalizedName` | |
| `+0x288` | flag bits: 0 identified, 2 infinite (store stock), 3 droppable, 4 pickpocketable, 5 stolen, 6 non-equippable, 7 new (unseen), 8 deleting | `Identified` (default 1), `Infinite` (store lists), `Dropable` and `Pickpocketable` (default **0**), `Stolen`, `NonEquippable`, `NewItem`, `DELETING` | constructor: 3 and 4 set; after a UTI load: 3 and 4 clear (below) |
| `+0x28c` | stack size | `StackSize` | 1 |
| `+0x290` | weight of one item, tenths of a pound (`baseitems.TenthLBS`); `GetWeight` (`0x005562a0`) multiplies by the stack, or adds a container's contents | — | |
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
  `Cost` = `AddCost` in 681 of 810 files and 303 have `AddCost` 0 (the `templates.bif` copies).
- `Dropable` and `Pickpocketable` are read with default 0, overriding the constructor's set bits,
  and no shipped UTI has either field: an item loaded from a template is neither droppable nor
  pickpocketable until `CreateItemOnObject` marks it droppable or `SetPossessor` hands it to a PC
  (5.4). A saved item keeps whatever was written.
- An item with no properties at all is marked identified. The writer always writes
  `Identified` = 1. Identification plays no role in KOTOR.
- For every CastSpell property whose `UsesPerDay` is unset (255), `Useable` becomes 1 and
  `CostValue` 8..12 (`iprp_chargecost` "1..5 Uses/Day") sets `UsesPerDay` to 1..5 (other cost
  values leave it 255) (`CSWSItem::InitUsesPerDay` `0x00555bf0`). (high)
- The tag is registered in the module's tag table, like every object.

Copy and split: `CSWSItem::CopyItem(src)` (`0x0055d950`) copies names, tag (and registers it),
possessor, both property arrays, value, charges, maximum charges, base AC, infinite and identified
bits, stack, weight, upgrades, model / body / texture variation, non-equippable, base item and the
six bytes at `+4..+9`; a source with a container list gets a new empty one. It does **not** copy
the plot, stolen, droppable, pickpocketable or new bits, so the copy keeps the constructor's
(droppable and pickpocketable set, the rest clear). It refuses a container item that holds
anything. `CSWSItem::SplitItem(n)` (`0x0055f280`), for 0 < n < stack: a new item copied from this
one with stack n, this stack reduced by n; otherwise null. (high)

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
| `0x00555fd0` | `RemoveItem(item)` | removes the id (shifting the rest down); if the item carries the "new" flag, clears it and decrements the counter; the possessor is not touched | high |
| `0x005560b0` / `0x005560e0` | `GetItemAt(i)` / `GetItemIdAt(i)` | indexed access | high |
| `0x00555ed0` | `FindItemWithTag(tag)` | first item whose tag equals, searching container items recursively; id or invalid | high |
| `0x00555e00` | `FindItemWithItemType(type, n)` | the n-th item whose `baseitems.ItemType` matches, recursively | high |
| `0x00555f40` | `ContainsItem(item, bRecurse)` | | high |
| `0x0055f330` | `Clear` | count and new-count to 0, items untouched | high |
| `0x00555de0` | `FreeList` | frees the id array (destructors) | high |
| `0x00556150` | `SetParent(id)` | stores the new parent and calls `SetPossessor(parent, no signal, no feedback)` on every item: no signalled events, but an item the parent already held gets the unconditional ON_ACQUIRE_ITEM of 5.4 step 1 | high |
| `0x00556100` | `GetContentsWeight` | sum of `GetWeight` (weight × stack, plus nested contents) | high |

**`AddItem`, in order** (`0x0055d330`, high):

1. **Special item types**, when the holder is a creature (or a container item held by a
   creature): `baseitems.ItemType` 23 (credits, base item 57) → the creature gains gold equal to
   the stack size (`AddGold(n, feedback on)` whatever `bSignal` says), the item object is deleted
   and `*ppItem` becomes null; `ItemType` 42 (pazaak card, base item 86) → `AddPazaakCard`
   (below), item deleted. `AddItem` returns 1 in every case.
2. **Insert position** (sorted lists only): with `bMerge`, the first index whose item has a larger
   base item number, or the same base item and a name that sorts after the new item's name
   (localized name in the current language, byte-wise compare). The real save's `INVENTORY.res`
   is in this order (base items 2, 4, 25, 26, 53, 55, 77, 85). Without `bMerge` the base item is
   ignored: the first index whose name sorts after the new name.
3. **Stack merging** when `bMerge`: every existing item with the same base item, the same model
   variation and `CompareItem` true (next section) is offered the new item's stack
   (`CSWSItem::MergeItem` `0x00553f90`): if `existing + new ≤ baseitems.Stacking`, the existing
   stack absorbs everything, the new object is deleted, `*ppItem` becomes the existing stack, the
   holding creature's client is told the stack changed, the existing stack gets
   `SetPossessor(its holder, bSignal, bSignal)` (an unchanged holder, so it queues ACQUIRE_ITEM
   again **even when bSignal is 0**, 5.4 step 1), and `bMarkNew` sets its "new" flag and bumps
   the counter (even if it was already new); done. Otherwise the existing stack is filled to the
   maximum, the remainder stays in the new item and the scan continues.
4. **Insert the remainder**: sorted list → its possessor is first set to the player's creature
   (`CSWSPlayer +0x38`, which `SwitchPlayerCharacter` re-points) with
   `SetPossessor(…, bSignal, bSignal)`, then it goes at the position from step 2 (or is
   appended); unsorted list → **at index 0** (newest first), possessor untouched (the caller sets
   it). `bMarkNew` sets the "new" flag; an item carrying it bumps the counter at `+4`.

Note that only `AddItem` merges; nothing ever caps an existing stack except the merge itself
(`SetItemStackSize` clamps, see below).

### 5.3 Stacking rules

Two items stack when `CSWSItem::CompareItem` (`0x00553cf0`) holds, i.e. all of these are equal
(high): upgrades bit set, the counts of both property lists, plot flag, charges, base item, stolen
bit, model / body / texture variation, **tag**, localized name, and for every property in both lists
PropertyName, Subtype, CostTable, CostValue, Param1, Param1Value, UsesPerDay and UpgradeType.
The maximum stack is `baseitems.Stacking` (99 for most rows, 15000 for credits, 9999 for
programming spikes, 1 for the creature-weapon rows). With a maximum of 1 the merge never takes.
Not compared: value (`AddCost`), maximum charges, the droppable / pickpocketable / new bits,
ChanceAppear and Useable; a merged stack keeps the existing item's.

Stack size elsewhere (high):

- `GetItemStackSize` (138, `0x005465d0`) and `GetNumStackedItems` (475, `0x0053c220`) both read
  `+0x28c`.
- `SetItemStackSize(o, n)` (150, `0x00546630`): n clamped to 1..`Stacking`; when it changes, the
  possessing creature gets feedback 50 (gained) or 51 (lost), and the HUD notice 7 / 8 is added
  whoever holds the item (no party test).
- **DECREMENT_STACKSIZE** (event 16, item `EventHandler` `0x0055ee10`): stack > 1 → minus one;
  stack 1 → queue DESTROY_OBJECT (11) to the item. If the possessor has it equipped, the
  creature's carried-weight total `+0xa3c` drops by the base item's `TenthLBS`.

### 5.4 Possession and the inventory events

`CSWSItem::SetPossessor(newHolder, bSignal, bFeedback, oldHolderOverride)` (`0x00553210`, high) is
the single place that fires the item scripts. "Creature" below means the holder itself if it is a
creature, or the creature holding the container item that holds it; "placeable" means the holder
itself only.

1. New holder = current holder (`+0x268`, before any override): queue script event 19
   ON_ACQUIRE_ITEM (objects: item, holder) to the **module** and stop (no bSignal test).
2. A valid `oldHolderOverride` is stored as the current holder first: callers that have already
   taken the item out (and so cleared its holder) pass the real source this way. If the creature
   changes, and no override was given or it equals the stored holder: the old creature, if any,
   gets script event 20 ON_LOSE_ITEM (item) to the module when bSignal, and feedback 51 when
   bFeedback. The new creature, if it is a PC (stats `IsPC`), turns the item droppable and
   pickpocketable; feedback 50 when bFeedback.
3. A new creature with bSignal: ON_ACQUIRE_ITEM (item, creature) to the module.
4. Old holder a placeable with `DieWhenEmpty` = 0: with bSignal, script event 27
   ON_INVENTORY_DISTURBED to it, disturb type 1 (removed), caller = the new creature, else the new
   placeable; with neither (the item leaves to nowhere) **no event**.
5. New holder a placeable with `DieWhenEmpty` = 0: with bSignal, the same event with disturb type 0
   (added), caller = the old creature, else the old placeable; with neither, no event.
6. Store the new holder at `+0x268`.

All events go through the event queue (0 ms), so the scripts run on the next `UpdateState`. The
disturb type constants match nwscript's `INVENTORY_DISTURB_TYPE_ADDED` 0 / `REMOVED` 1.

So the module's `OnAcquireItem` / `OnUnAcquireItem` run for signalled transfers to or from a
creature, and step 1 makes `OnAcquireItem` run once more whenever an item is re-assigned to the
holder it already has. Read statically, that gives (med, needs a runtime check):

- An item a PC acquires into the party inventory with feedback (`CSWSCreature::AcquireItem` with
  bFeedback, Take All) fires `OnAcquireItem` **twice**: once from `AddItem`'s own
  `SetPossessor` (step 4 of `AddItem`), once from the caller's second one (unchanged holder).
  Acquired by a party NPC, the second call moves the holder from the PC to the NPC: ON_LOSE_ITEM
  for the PC, then ON_ACQUIRE_ITEM for the NPC, and the item's possessor is the NPC.
- Every item the party restore loads, and every stack merge (5.2), fires `OnAcquireItem` even
  though the caller asked for no events.
- A container's `OnInvDisturbed` fires for each item of Take All (removed) and for items put into
  it by `GiveItem` / GIVEITEM (added, caller = the previous holder), but **not** for an item
  created in it (`CreateItemOnObject`), destroyed in it, or pulled out of it by a creature's
  `AcquireItem` (`GiveItem` to a creature, TAKEITEM): `CSWSPlaceable::RemoveItem` clears the
  holder first, so step 4 has no caller. Never for body bags (`DieWhenEmpty` set).

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
± amount) when the creature given to / taken from is a party member;
`TakeGoldFromCreature(n, o, bDestroy)` clamps n to what o has and,
unless bDestroy, gives it to the caller: as gold to a creature, as a `g_i_credits001` item of
stack n to a placeable with an inventory or to a container item. `GetGold` on a placeable returns
the stack of its first credits item (ItemType 23).

**Joining the party** is 3.6 (`MergeCreatureIntoParty` `0x005641e0`): the joiner's own gold
and items move into the party; the party restore after a module load runs it for the PC and every
linked NPC, then `EquipDefaultClothes` (4.8). (high)

**Saving.** The party inventory is written by `CSWPartyTable::SaveInventory(bClear)`
(`0x00564030`) to `GAMEINPROGRESS:INVENTORY` (GFF `INV ` V2.0, one `ItemList` of full item
structs), at module transitions and in a save; with bClear the list is then emptied (`Clear`,
items untouched). Loaded by the party restore (`0x00565760`) with `AddItem(merge, no events, not
new)` and then `SetPossessor(PC, no signal, no feedback)` (which still queues ON_ACQUIRE_ITEM,
5.4). (high)

**Scripts see the party inventory**: `GetFirstItemInInventory` / `GetNextItemInInventory` (339/340,
`0x00549b50`) and `GetItemPossessedBy` (30, `0x0053a390`) on a creature use
`GetItemRepository(1)`; `GetItemPossessedBy` (lower-cased tag) then falls back to the creature's
**own equipped slots** (all 18), so it finds equipped items too; on a placeable it needs
`HasInventory`, on a container item its list, anything else → invalid. The iteration also steps
one level into container items (cursor on the
creature `+0xa34` index, `+0xa36` sub-index, `+0xa38` current container; on placeables `+0x370`,
`+0x372`, `+0x374`). On a store the iterator returns nothing. `GetHasInventory` (570,
`0x005392d0`): creatures and stores 1, placeables their `HasInventory`, items 1 only for
containers. (high)

### 5.6 Moving items

| Address | Name | What | Conf. |
|---|---|---|---|
| `0x005158e0` | `CSWSCreature::AcquireItem(ppItem, fromId, intoContainerId, bFeedback)` | the item must be held by `fromId` (or by a container item `fromId` holds), else fail; target list = `GetItemRepository(1)` or the given container item's; take it from the old holder (creature `RemoveItem` with feedback always on, placeable `RemoveItem`, or a container item's list; a container into a container fails); `AddItem(merge, bSignal = bFeedback, new)`; an item that was on the ground leaves the area; `SetPossessor(this creature or the container, signal, bFeedback)` (5.4 for the events this pair queues) | high |
| `0x00510ef0` | `CSWSCreature::RemoveItem(item, unequipFlag, bFeedback, ppOut)` | unequips it first if equipped (`RunUnequip` `0x005023a0`, given the flag), takes it out of `GetItemRepository(1)` (when held by this creature) or the container item it holds, `SetPossessor(invalid, signal, bFeedback)`; an item held by neither → returns 0, nothing done | high |
| `0x00584b10` | `CSWSPlaceable::AcquireItem(ppItem, fromId, bFeedback)` | the item must be held by `fromId`, else fail; takes it from the old holder (creature `RemoveItem` with bFeedback, placeable `RemoveItem`, container item's list) or off the ground, `AddItem(merge, no signal, new)`, `SetPossessor(placeable, signal, feedback, override = old holder)`; bFeedback reaches only the creature removal | high |
| `0x00584ac0` | `CSWSPlaceable::RemoveItem(item)` | only if `+0x36c` holds it: out of the list, `SetPossessor(invalid, signal, feedback)` | high |
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
`IsBodyBag`, `+0x44c` `IsCorpse`, `+0x448` the body's former owner id (set only by
`SpawnBodyBag`), `+0xf8` plot (`Invulnerable`, else `Plot`; forced 1 by `Static`), `+0x218`
`PartyInteract`. `GroundPile` is read but the field `+0x254` is always forced to 1. `Open` and
`AnimationState` are separate fields: `+0x338` is read from `Open`, the animation from `AnimationState` (1 →
10075, 2 → 10076, ...), so a lid shown open is not open to USEOBJECT's already-open test.

Opening is the USEOBJECT action's ([actions.md](actions.md) 3.5), which ends in
**`CSWSPlaceable::OpenInventory(user, bAnimate)`** (`0x00587420`, high): only when closed and
`HasInventory`; during a conversation (GUI `+0xb4`) it just plays the close animation (10076) and
stops; otherwise the user's client opens the container panel (told whether the list is non-empty;
`CGuiInGame::OpenContainer` `0x0062d4b0` pauses the game while it is up), script event 22
ON_OPEN is queued to the placeable (caller = user), the open animation 10075 plays when asked,
`Open` = 1.

The container panel (`CSWGuiContainer`, `container.gui`, `0x006b6dc0`) answers with GuiContainer
message 0x19/2 {object id, take-all flag} (`0x005232a0`; an item container, object type 6, goes to
`CSWSItem::CloseInventory` instead) → **`CSWSPlaceable::CloseInventory(user, bTakeAll)`**
(`0x00587560`, high), only if open:

1. With bTakeAll and a player user: take items **from the last to the first**; each is removed
   from the placeable and given to the user's `GetItemRepository(1)` with `AddItem(merge,
   signal, new)` and `SetPossessor(user, signal, feedback)` — so ON_ACQUIRE_ITEM fires per item and
   the placeable's `OnInvDisturbed` fires per item (type 1) unless `DieWhenEmpty`.
2. Queue script event 23 ON_CLOSE (caller = user), play animation 10076, `Open` = 0.
3. `HasInventory` and `DieWhenEmpty` and now empty → `Useable` = 0 and DESTROY_OBJECT queued to
   itself (the bag vanishes).

The panel side (`CSWGuiContainer::HandleInputEvent` `0x006b92f0`, med for which button sends
which input): in the container view, accept (input 0x27, also 0x2d) sends the close message with
take-all set when the container was non-empty on opening; cancel (0x28 / 0x2e) sends it with
take-all 0; 0x29 (`BTN_GIVEITEMS`) switches to the give view (`ShowGiveItems` `0x006b8410`, the
party inventory), where clicking a row (`0x006b7170`) sends GIVEITEM (input message 6/0x24) for
the party leader with a count of 1, or while the alternate-action key is held the row's name read as a number
(0x006b4fe0: 0 for any item name; there is no count dialog)
(GIVEITEM is actions.md's). **There is no taking of a single item**: the container view's rows get
no click handler (`ShowContainerItems` `0x006b8130`), so the panel only takes everything; PICKUPITEM
(Inventory message 0xc/5 → `AddPickUpItemAction`) is not a way round it, since
`AIActionPickUpItem` (`0x00517410`) fails for an item that has a possessor, i.e. it picks up only
items lying on the ground.

**Body bags.** `CSWSObject::SpawnBodyBag` (`0x004ce220`, high for the steps). It runs at
DESTROY_OBJECT (event 11): the creature handler calls it only for a dead creature
([combat.md](combat.md) 8.4), the placeable handler (`0x00587ba0`) every time, after closing its
inventory. Returns the bag id or `OBJECT_INVALID`.

1. Creatures and placeables only, in a valid area. The bag row is the creature's `BodyBag` byte
   (`+0x9da`); 0 → `appearance.2da` column `BODY_BAG` of its appearance. A placeable uses its own
   `BodyBag` and needs at least one item of any kind (`GetItemCount(0)` `0x00587710`, 0 without
   `HasInventory`).
2. `bodybag.2da` `Corpse` = 1 (rancor, krayt) makes a corpse container; only a creature's row is
   looked up, so a placeable's bag is never a corpse. A non-corpse bag for a creature is only made
   when it has droppable items (equipped slots 0..13 or inventory, item flag bit 3; `0x004f3770`)
   or gold (else no bag, `OBJECT_INVALID`).
3. The bag's placeable appearance (`GetBodyBagAppearance`, creature `0x004ef2e0`, placeable
   `0x005851e0`): `bodybag.2da` `Appearance` of the `BodyBag` row (row 0 "default" has none),
   else the `Appearance` of the `bodybag.2da` row named by `appearance.2da` `Body_Bag`, else 3.
   The placeable version looks up a `BodyBag` column in that same appearance table, which has
   none (`placeables.2da` is the table with that column), so a placeable with `BodyBag` 0 (every
   shipped UTP) gets appearance 3, the backpack (med: needs a runtime check).
   A new placeable is set up with that appearance by `CSWSPlaceable::InitBodyBag(appearance)`
   (`0x005864b0`): tag `Body Bag`, name from `placeables.2da` `StrRef`, description strref 38612,
   portrait `PO_PLC_B04_`, HP 15, hardness 5 (1 for appearance 217, the rancor corpse), Fort 16,
   faction 1, `Useable` and `HasInventory` 1, not lockable, no scripts, plot 0, animation 10000.
   It is filled by `CSWSPlaceable::TakeItemsFromObject(source, bDroppableOnly = 1)` (`0x00588690`):
   the source's equipped items in slots 0..13 and its inventory items, those flagged droppable,
   are moved in with `AcquireItem`; the source's gold becomes a `g_i_credits001` item of that
   stack and the source's gold is set to 0. From a placeable source every item is moved
   (the droppable filter is dropped).
4. Bag fields: `IsBodyBag` 1; for a creature source the owner id (`+0x448`, and `+0x444` = 0);
   `IsCorpse` from the 2DA, `DieWhenEmpty` = not corpse (a corpse without items gets
   `HasInventory` 0), plot (`+0xf8`) = not corpse; name = `bodybag.2da` `Name` strref (38151
   "Remains" for every row; read from the creature's own `BodyBag` byte, without the
   `appearance.2da` fallback); facing of the dead object; `PartyInteract` 1. This matches
   [combat.md](combat.md) 8.4.
5. Event 17 SPAWN_BODY_BAG is queued to the **area** with a **500 ms** delay carrying the bag id
   and the dead object's position; the area handler (`0x0050d6c0`) adds the bag there (a corpse
   bag also goes through `0x00508180` with its bounds).

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
(from a save GIT), plus `Infinite` (item flag bit 2); an entry whose `ObjectId` already names a
live object is skipped. Entries are first collected in descending value order, then added from the
cheapest up through `CSWSStore::InsertItemByCost` (`0x005c70c0`), each getting the store as
possessor, so a freshly loaded store holds its stock in ascending value. Later additions are
appended (via `AddItem` with merging) unless cheaper than the first entry, in which case a
backwards scan inserts them at the last index whose value is higher (it does not keep a strict
order; high for what the code does). The panel re-sorts anyway (below). The 38 shipped UTMs:
`MarkUp` 75..150 (mostly 100), `MarkDown` 20..65 (mostly 25), `BuySellFlag` 3 in 36, 1 in 2; 158
infinite entries.

**`OpenStore(oStore, oPC, nBonusMarkUp = 0, nBonusMarkDown = 0)`** (378, `0x00540300`): both
bonuses clamped to −100..100 and stored; the in-game GUI opens the store panel
(`CGuiInGame::OpenStore` `0x0062e310`, `CSWGuiStore` `0x006c1c00`; it pauses the game, and does
nothing while the in-game GUI's `+0xb4` (conversation) or `+0x30` is set, med for what `+0x30`
means); script event 22
is queued to the store either way, with the PC's controlled creature as caller, and the store's
`EventHandler` (`0x005c6ee0`) records the caller and runs `OnOpenStore`. (high)

**Item value** (`CSWSItem::GetCost` `0x00554000`, high, from the disassembly):

```
value(item) = 0                                   if the item is plot
            = max(1, trunc(AddCost × costMult[base item]))   otherwise
```

`costMult` is a float per `baseitems.2da` row (row `+0xc4`, 1.0 at load), changed only by
**`ChangeItemCost(sTemplate, fMult)`** (747, `0x00547970`: loads the template to learn its base item
and sets that row's multiplier, so it affects **every item of that base item**) and saved in the
party table as `PT_COST_MULT_LIST` (one `PT_COST_MULT_VALUE` float per base item row; both labels
are cut to 16 characters in the file, `PT_COST_MULT_LIS` / `PT_COST_MULT_VAL`). The value is
**per unit**: stacks are bought and sold one at a time. `GetGoldPieceValue` (311, `0x005390e0`)
returns the same value (0 for a non-item).

**Prices** (`CSWGuiStore::GetBuyPrice` `0x006c0790` / `GetSellPrice` `0x006c07f0`, high), integer
arithmetic, unsigned divide (a negative percentage sum would wrap to a huge price):

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
item costs more than <CUSTOM0> credits…", token 0 = that threshold; yes → `0x006c0d20` buys);
then: click sound 9, gold −= price written to the PC with `SetGold` (so the party's `PT_GOLD`),
and `CSWSStore::SellItemTo(item, PC)` (`0x005c6f70`): an **infinite** item is copied (copy keeps
the stock item, infinite bit cleared, stack 1); a stack > 1 is split by one; a single item leaves
the stock; the result goes to the PC with `AcquireItem(from the store, feedback)` — into the party
inventory.

**Selling** (`OnSell` `0x006c0f40` → `DoSell` `0x006c0d80`, high): price > **min(50 ×
level, 250)** → confirmation 41985 ("This item is worth more than <CUSTOM0> credits…"); then sound
11, gold += price via `SetGold`, one unit leaves the party inventory (split when stacked) and goes
to `CSWSStore::AcquireItem` (`0x005c7610`): **plot items are refused**; the item is marked
identified and removed from its creature holder (or from the creature holding its container); the
first stock item with the same tag (`FindItemWithTag`) is compared with `CompareItem`: if it
accepts, an infinite stock item absorbs the sold one (the sold object is deleted) and a finite one
gets **+1 on its stack, whatever the item's stack was and ignoring `Stacking`**; otherwise (no item
with that tag, or the first one differs) the item gets the store as possessor and joins the stock
through `InsertItemByCost`.

**Lists and modes** (high): the store list (`FillStoreItems` `0x006c1840`) and the player list
(`FillPlayerItems` `0x006c0850`, from the PC's `GetItemRepository(1)`, i.e. the party inventory;
equipped items are not offered) show **only non-plot items**, grouped by `baseitems.StorePanelSort`
(base item `+0x30`) ascending and in list order inside a group. The group loop runs until it has
added as many rows as there are items; the player list counts only non-plot items first, the store
list compares with the whole stock, so a store stocking plot items lists its last group again until
the count is reached (two shipped stores stock one: `kas_twostore` `tat20_banthafod`, `keblastore`
`ptar_permacrete`; med: needs a runtime check). Selecting an entry shows the buy or sell price (by
mode) and either the stack count or 41951 "Infinite" (`OnItemHilighted` `0x006c0aa0`).
`BuySellFlag` (`SetupForStoreMode` `0x006c1b50`): 1 → buy page only, 2 → sell page only, 3 → both
with a toggle.

### 5.9 Credits and pazaak cards

- **Credits** are base item 57 (`ItemType` 23, `Stacking` 15000, template `g_i_credits001`). In a
  creature's or the party's inventory they never exist as items: `CItemRepository::AddItem`
  (`0x0055d330`) turns them into gold (also when added to a container item a creature holds) and
  deletes the item. They exist as items in placeables, body bags and on the ground.
- **Pazaak cards** are base item 86 (`ItemType` 42, `g_i_pazcard_001`..`018`, `ModelVariation`
  7..18 then 1..6). `AddItem` routes them to `CSWSCreature::AddPazaakCard(item)` (`0x004efb40`,
  high): the party table's card count at `+0x120 + 4 × ((ModelVariation + 11) mod 18)` (= card
  number − 1) grows by the stack size, and if the party inventory holds no item of `ItemType` 43,
  a `g_I_PazSidebd001` (pazaak side deck, base item 87) is created and added; `AddItem` then
  deletes the card item. The counts are `PT_PAZAAKCARDS`.

### 5.10 Charges and uses

Only the usable CastSpell properties (PropertyName 10, property `Useable` byte set) consume
anything; their `CostValue` is a row of `iprp_chargecost.2da`. Uses left
(`CSWSItem::GetPropertyUsesLeft(i)` `0x00555a60`, high; 0 for a property that is not a usable
CastSpell):

| CostValue | Meaning | Uses left |
|---|---|---|
| 1 Single_Use | consumed item | the **stack size** (its low byte) (medpacs, grenades, stims) |
| 2..6 | 5, 4, 3, 2, 1 charges per use | `Charges / (7 − CostValue)` (integer) |
| 7, 13 | 0 charges per use, unlimited | not counted (0) |
| 8..12 | 1..5 uses per day | the property's `UsesPerDay` byte |
| 14..18 | 1..5 per minute | 1 while the property is `Useable` |

`CSWSItem::UpdateUsesForClient` (`0x0055d040`) packs these for the first 8 properties into a cache
(`+0x238` a bit per property that can be used, `+0x239..+0x240` one uses-left byte each) and
sends the possessing client the changed bytes when anything changed.

Spending a use is **`CSWSItem::ConsumePropertyUse(i, user)`** (`0x0055de20`, high for the
arithmetic, med for the destroy rule), called at impact by the item-cast-spell action
([actions.md](actions.md) 0x2e, `0x0050f170`) and by the inventory screen's instant use
(`0x004efe30`); a client option (`+0x8c`, unidentified) skips it entirely:

- Single_Use: stack > 1 → stack − 1; the last unit makes the property unusable and the item is
  destroyed (item flag `0x100`, the client told, DESTROY_OBJECT queued to the item at once).
- Charges: the cost is taken only when `Charges` covers it (the spell has already been cast);
  every CastSpell charge property the rest cannot pay becomes unusable. Then, if the item's
  **last** property is unusable (the code tests the loop's last property, not the one spent; the
  same thing for a one-property item): stims, medical equipment and squad recovery kits
  (`ItemType` 25 / 45 / 47) are destroyed as above, other items only when no CastSpell charge
  property is left usable.
- Uses per day: `UsesPerDay` − 1, unusable at 0. Per minute: the world time of the use is stored
  in the property and it becomes unusable. Neither destroys the item.
- Otherwise the cache above is refreshed.

### 5.11 Upgrades (the workbench)

**The mechanism** (high, from the code and confirmed on the data): an upgradeable weapon or armour
blueprint **already contains every property any upgrade could give it**, each tagged with
`UpgradeType` = a row of `upgrade.2da`; native properties have 255. A property counts only when
its tag is 255 or its bit is set in the item's `Upgrades` word (`+0x294`): the property readers
apply this filter — the property lookup `0x005539c0`, applying the passive properties on equip
`0x00553bb0`, removing them on unequip `0x00553c30`, the use-limitation checks, on-hit effects,
`GetItemHasItemProperty` and the description helpers of `CSWSItem::GetDescription` (`0x0055f340`),
so an inactive upgrade property is neither applied nor described. Installing an upgrade sets bit
*row*; removing it clears the bit. Nothing is copied from the upgrade item; the upgrade item object
is consumed (deleted when the bench closes, below). Example: `g_a_class5007` carries an Armor
property tagged 20 (Armor_Reinforcement) and DamageResist/Immunity properties tagged 21
(Mesh_Underlay) beside its native ones; `g_w_lghtsbr01` carries properties tagged with every crystal
row (0..12, 22..24). 59 of 810 UTIs carry tagged properties. `CompareItem` sees every property
active or not: it requires equal `Upgrades` words and equal tags property by property, so items with
different upgrades never stack.

`upgrade.2da` (`label`, `template`, `upgradetype`): rows 0..12 and 22..24 are lightsaber power
crystals (type 0), 13..15 melee (types 1..3: vibration cell, durasteel alloy, energy projector),
16..19 ranged (types 4..7: scope, improved energy cell, beam splitter, hair trigger), 20..21 armour
(types 8..9). `upcrystals.2da` (7 rows: the five colours, Heart, Mantle) lists the lightsaber colour
crystals with the crystal's `Template` and, per row, the template of the saber of each kind
(`ShortMdlVar`, `LongMdlVar`, `DoubleMdlVar`).

**Category** (`CSWSItem::GetUpgradeCategory(upgrade2DA)` `0x005541c0`, high): over the item's
properties with a tag (both property lists; the last tagged one decides), `upgradetype` 0 → 1
lightsaber, 1..3 → 3 melee, 4..7 → 2 ranged, 8..9 → 4 armour; 0 = not upgradeable.

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

1. `ShowUpgradeScreen(oItem = invalid)` (354) → `CGuiInGame::ShowUpgradeScreen` (`0x0062e760`,
   pauses the game). With an item it goes straight to it; otherwise the four category buttons are
   enabled for each category that has an upgradeable item among the player's creature's and the
   available, selectable party members' equipped items (slots 0..17) and the party inventory
   (`CSWGuiUpgradeSelect::OnPanelAdded` `0x006c4520`).
2. The item list of a category (`0x006c5b90`): equipped items of the player's creature and of each
   available, selectable NPC, then party-inventory items of that category.
3. Picking an item takes it out of play (`CSWGuiUpgradeItems::OnUpgradeItem` `0x006c2df0` from the
   list, `CSWGuiUpgradeItems::OnPanelAdded` `0x006c6330` for an item passed to
   `ShowUpgradeScreen`): equipped → unequipped (its properties come off) and the slot remembered;
   when it is one of two wielded weapons (slots 0x10 / 0x20), the other weapon is unequipped too
   and remembered; in the inventory → removed (one split off a stack). The bench keeps a backup
   copy (`CopyItem`, in `CSWGuiUpgrade::OnPanelAdded`) for cancelling.
4. Setting up the slots (`CSWGuiUpgrade::OnPanelAdded` `0x006c4d70`): for each `upgrade.2da` row,
   the first empty slot of this category whose type matches takes the row; if the item's
   `Upgrades` has that bit, an item is created from the row's template and shown installed (the
   slot is then full; an empty one is offered to the next row of the same type, which only matters
   for the two power-crystal slots); otherwise, except for lightsabers, if the party inventory has
   no item whose tag equals the template (lower-cased), the slot icon is dimmed (alpha 0.25). For a
   lightsaber the colour slot's crystal is the `upcrystals.2da` row whose column for this saber
   kind (`ItemType` 39 double, 40 short, 41 long) equals the saber's **tag**; a saber of another
   `ItemType`, or one no row names, closes the panel.
5. Clicking a slot (`OnSlotClicked` `0x006c6500`): installed → clear the bit, the upgrade item goes
   back to the party inventory (`AddItem` with merge); empty → find the template in the party
   inventory (nothing happens without one), set the bit, and if the item was taken from a
   creature's equipment, re-check `CanEquipItem` (`0x0051aa60`) on the upgraded item: failure shows
   message 42489 ("Adding this upgrade will prevent the character who was previously using this
   item from reequipping it because they do not have the appropriate feat.") as a yes/no box
   (`0x006c6120`: yes installs; no clears the bit on the *upgrade* item, the callback's argument,
   not on the bench item, so the bench item keeps the bit without the upgrade being taken: med,
   needs a runtime check; see [gui.md](gui.md) "Slots"); else the upgrade item is moved out of the
   party inventory (one unit, `TakeUpgradeItem` `0x006c59a0`). Lightsaber slots open a list
   instead: power crystals from the party inventory other than those in either power slot; colour
   crystals in the party inventory other than the current one.
6. Choosing a **colour crystal** (`OnUpgradeChosen` `0x006c5510`) **replaces the saber object**: a
   new item is created from the chosen `upcrystals.2da` row's template for this saber kind, given
   to the player's creature as possessor, identified, takes over the old saber's `Upgrades` word
   and stolen bit, and the old object is deleted; the old crystal returns to the party inventory
   and the chosen one leaves it (one unit). Power crystals set or clear their bit like the other
   slots.
7. `BTN_ASSEMBLE` (`CSWGuiUpgrade::OnAssemble` `0x006c6190`) puts the item back through
   `CSWGuiUpgradeItems::ReturnItem` (`0x006c5e90`): re-equipped in its slot when `CanEquipItem`
   still allows it, else into the party inventory; a second weapon unequipped in step 3 is always
   re-equipped (an off-hand weapon moves to slot 0x10 when the upgraded main-hand one cannot
   return). Opened with an item, the upgrade screen then closes; otherwise the item list is
   refreshed. Back/cancel (BTN_BACK or the
   cancel key, `HandleInputEvent` `0x006c6a80`) first closes an open crystal list; otherwise
   `OnCancel` (`0x006c61f0`) deletes the edited item, restores the backup copy, gives back the
   upgrade items taken this session and takes back those returned, then calls `ReturnItem` the
   same way. Closing the panel (`CSWGuiUpgrade::OnPanelRemoved` `0x006c25f0`) deletes the backup
   copy and every object still in a slot, so accepted upgrade items are destroyed and nothing
   leaks.

## 6. Open questions

Party:

- After a load the leader slot `+0xec` (from `PT_IS_LEADER`) reaches the client party only through
  the client's add-member routine `0x006364c0`, which asks `IsCreatureLeader` (`0x00563a00`): outside
  loading it makes a matching member the leader (`CSWCParty::SetLeader`); while loading it only
  stores the id at client `+0x338` (`0x005ede00`), whose consumer was not traced (med: the decompile
  of `0x006364c0` has unresolved register arguments).
- `GetItemRepository(1)`'s extra case: when bit 0 of `+0x104` of the server object at `+0x10004` is
  set, an available NPC outside the party also gets the party inventory while one of the in-game GUI
  panels at `+0xc` / `+0x10` is open (`0x0062b4d0`); the same bit makes the character, equipment,
  inventory and abilities panels browse available NPCs by slot instead of cycling the party leader.
  No writer of the bit was found (probably a debug or Xbox mode; low).
- The formation geometry used by `PlacePartyAroundLeader` and party selection is movement.md's
  client party table; the exact slot offsets were not tabulated.

Equipment:

- The combat modes at `+0x4d2` follow NWN's numbering by every test the code makes (1 parry,
  2 power attack, 3 improved power attack, 4 counterspell, 5 flurry of blows, 6 rapid shot: the
  setter `0x0050ee80` refuses 5 with a right-hand weapon, 6 without a ranged one, 1–3 with a ranged
  one, and `GetDamageBonus` gives modes 2 and 3 +5 and +10, combat.md 2 and 6); whether KOTOR's
  GUI ever selects them (`SetActivityMode` `0x004f2a50` maps activity modes 2..7 to 1..6) needs a
  runtime check (med).
- The per-hand "instant" flags `+0xaac` / `+0xaa8` are sent with the weapon slot's equip or unequip
  record in the creature's client update (`0x00572070`, which then clears both); what the client
  does with them (skip the draw animation?) was not traced.
- The remove handlers other than AC, enhancement and attack bonus (`0x004e8950`: type 10, creator
  = the item, int0 = the bonus, int1 = the hand of the slot, alignment / race parameters; it removes
  the first match) were not read one by one. They matter: the `RemoveEffectsByCreator` sweep that
  follows skips the effect after each one it removes (rules.md 1.9), so it does not reliably clean
  up what a handler misses.
- The light property (29, `0x004e62d0`) ignores its `Subtype` and `CostValue` (`iprp_lightcost`):
  every lit item (`g_i_collarlgt001`, `g_i_glowrod01`, `g_i_torch01`) gets the same 0x36 effect with
  int0 = 5000, a VISUALEFFECT child; how the client renders visual 5000 (colour, radius) was not
  traced.
- The GUI's two-handed test (`WeaponSize` 4) and the server's (`WeaponWield` 3/5/6) disagree for
  the Gamorrean battleaxe; which one players actually hit was not tested in the game.
