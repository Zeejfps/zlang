# Playthrough log: Tatooine

The main storyline of Tatooine played headless, step by step, with logs and screenshots. The method is
[playthrough.md](playthrough.md)'s and [playthrough-dantooine.md](playthrough-dantooine.md)'s: a crafted arrival state, then real
input (the bot walks, conversations are answered by a queue of words, menus are clicked). The scripts are in
`kotor/tools/playthrough/tatooine/`.

**Stopped (paused by the coordinator) in the middle of the Krayt dragon hunt.** The chain below is complete and replays up to the
checkpoint `fodder`; the rest is not played. To resume, load `kotor/out/tat_cp/fodder` (made by part 12, in the Sand People Enclave,
the Bantha Fodder in the bag, Komad's hunt at `tat18ac_dragonhunt` 20) and write part 13 (see "Next steps").

## How to replay

```
kotor/tools/ctxc exe kotor -o kotor/out/kotor_tat.exe
sh kotor/tools/playthrough/tatooine/all.sh [FIRST_PART]       # the whole chain, each part loads the checkpoint the one before kept
LOAD=kotor/out/tat_cp/fodder sh kotor/tools/playthrough/tatooine/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]...   # one part
```

`run.sh` is fast (`--no-render --speed 8`) with its own saves directory (`kotor/out/saves_tat`); logs `kotor/out/pt/NAME.log`,
pictures `kotor/out/pt/NAME_SHOT.png`, checkpoints `kotor/out/tat_cp/NAME` (a part's `save` line, `keep.sh NAME` copies the newest).
Helpers: `nss.sh` (the install ships the NWScript sources of about 120 Tatooine scripts: extracted to `kotor/out/nss`), `findres.sh WORD`
(which resources of the Tatooine modules mention it), `factions.sh`, `pthroute.py` (a route along an area's path graph), `areas.sh`, `dlgs.sh`.

### The crafted state

The module `tat_m17ab` (the docking bay the Ebon Hawk lands in) with the state Dantooine leaves: Carth and Bastila join at frame 5 (joined
earlier they are left at 0,0 until the module places them), Canderous, Juhani, Mission and Zaalbar are available; the player is made a
Soldier 8 / Jedi Guardian 1 (37,500 XP) by the rules' own auto level-up (`ui xp`, `ui addclass 3`, `ui autolevel`), Carth a Soldier 8 and
Bastila a Jedi Sentinel 8 the same way (`ui leader`, `ui autolevel`); the player and Bastila get a lightsaber and a Jedi robe; 3,000 credits.
Other cheats, all for setup: `ui gold` (5,000 for HK-47, 100 more for the vaporators), `ui heal` and `ui stat hp 127` at the start of a part,
`warpxy` to cut the dunes' hidden path (part 12), `ui loot` (the loot panel without the walk). Everything else is the game's.

The Eastern Dune Sea (`tat_m18ac`) has one safe way through the dunes: `tat18_duneedgetr` triggers fire the "lost in the dunes" talk and a jump
back for any step over the edge bands. The path graph (`.pth`) has shortcuts that cross the bands, so the bot must follow explicit `X,Y`
stops (computed in the scratchpad from the graph with the bands cut out; the list is in part 11).

## The steps

State: **works** (checked, 0 faults), **fixed** (a commit of this branch).

| # | Step | State | Script |
|---|---|---|---|
| 1 | Docking bay: the customs trigger starts the officer's conversation, the 100 credit fee (Persuade fails at skill 0, pays), Jorul Kurax, out to Anchorhead | works | `01_dock.txt` |
| 2 | Czerka office `tat_m17ag`: the conservationist, the Protocol Officer, "no way to get a license?", the bounty on the Sand People: Hunter's License, `tat17ag_sandbounty` | works | `02_office.txt` |
| 3 | Across Anchorhead (the conservationist's talk, the Dark Jedi ambush, banter) to Yuka Laka's shop `tat_m17ac`: HK-47 for 5,000, the party screen (HK-47, Bastila) | fixed (HK-47's XP catch-up, party screen) | `03_hk47.txt` |
| 4 | Iziz the Jawa (the Star Map question, the rescued tribe), the gate guard: license shown, the Dune Sea `tat_m18aa` | works | `04_gate.txt` |
| 5 | The Dune Sea to the strip of the Sand People Territory; wraids and raiders fought by the bot | works | `05_dune.txt` |
| 6 | The fallen raiders looted; the Sand People Clothing put on from the equip screen (OK, then the heartbeat sets `tat_TuskenSuit` and the party is drawn as Sand People) | fixed (equip OK on a stack; save keeps standings; disguise appearance) | `06_loot.txt` |
| 7 | The Territory and the Enclave `tat_m20aa` in disguise: the warrior, the Chieftain through HK-47, "a peaceful solution", the price: two moisture vaporators; the clothing is taken off the party | works | `07_chief.txt` |
| 8 | Back to Anchorhead: the gaffi sticks redeemed, the vaporators bought from the Czerka store manager (400) | fixed (bot talk stops) | `08_vapor.txt` |
| 9 | To the Chieftain with the vaporators: peace, the Chieftain's Gaffi Stick, the Map of the Eastern Dune Sea (`tat_KraytMap`), `tat17_starmap` 40, what a krayt dragon is | fixed (GetItemPossessedBy) | `09_peace.txt` |
| 10 | Out through the Territory and the Dune Sea to the Eastern Dune Sea `tat_m18ac` (the strip lets the map through) | works | `10_krayt.txt` |
| 11 | The dunes' safe path to the hunters' camp; the hunter, Komad Fortuna's offer (the mines, the banthas, the fodder), `tat18ac_dragonhunt` 20 | works | `11_komad.txt` |
| 12 | Back to the Enclave (the hidden path cut with a warp) for the Bantha Fodder (the ragpile `tat20_ragpile`) | works | `12_fodder.txt` |

Experience: the player 37,500 at the start, 38,850 after HK-47 (quest awards), 43,650 after the Dune Sea fights, 44,050 after the Chieftain.
The license (`k_ptat_bountyset`) and the bounty gave none at level 9: the script's level ladder has no branch for it, as on Dantooine.

## Bugs found and fixed

1. **`ui xp N` printed zeros** (c52c096): the report helper added for `ui xp` (no argument) took the word first.
2. **The test bot never entered a trigger** (86bd1ef, dfb95fa, ab7c2d5, 28ef0b0, 372d6f9): a stop that is a trigger is walked to the middle of its polygon,
   from the polygon's own height (the Dune Sea's hills); a crossed transition trigger counts as reached; plot creatures are not attacked; `@TAG`
   talks once within eight metres and ends when the talk is over; `X,Y` stops.
3. **A recruit joined with 0 XP** (cf9baa1): the rules had `JoiningXP` and the catch-up but nothing called them; HK-47 at level 6 into a party at
   38,000 XP now takes his share when spawned (re/party-items-saves.md 3.4).
4. **The equip screen's OK did nothing for a stack** (a6b83d0): the preview puts one of the stack on (a new item), OK compared ids, failed
   silently, and Escape took the preview back; the Sand People Clothing (x7) could not be put on with OK.
5. **A save held no faction standings** (9ee4d51): `AdjustReputation` changes were lost on load while `tat_TuskenSuit` stayed set, so every Sand
   Person attacked a party the scripts took for disguised. `repute.fac` is in SAVEGAME.sav now.
6. **EffectDisguise changed nothing on screen** (cf80e35): the rules' APPEARANCE event had no consumer; creatures carry the
   appearance row of their disguise and the scene draws it (also after a load: it follows the effects).
7. **`GetItemPossessedBy` ignored worn and wielded items** (bc316ae; the original asks the inventory, then the 18 equipment
   slots, 0x0053a390): the Chieftain keeps his gaffi stick in his hand, so `k_ptat_givegaffi` gave nothing and the Czerka bounty could not be paid.
8. Test tools: `ui clickctl LB_ITEMS ~some_words` (a row by its text, scrolled into view), `ui where` prints the faction, `ui hostiles` the standing.

## Notes and open items

- **Not a bug:** the Dark Jedi trio in Anchorhead's plaza and the Dune Sea entry bounty hunters (`k_genoharadan`) fight the party; the bot's god mode
  keeps the leader at 1 hit point, so a part's checkpoint can have everyone at 1 HP (`ui heal` + `ui stat hp 127` at the next part's frame 4; the
  leader is not set before frame 4).
- The player's portrait (the default test player has none) is not set, so the equip screen's change-member buttons show the previous member's
  picture after a switch (a real player has a chargen portrait).
- Reply words with an apostrophe do not match (`~such_an_honor`, not `~If_it_s_such`).
- `bot: no nearer ... opens door N` and `stuck` lines are the bot's, not the game's.
- Long moves in the open (the Dune Sea) fail at the planner when the goal is not near a path point: routes name waypoints near doors
  (`tat17ag_tat17aa` before the office door), not the door.

## Next steps (from the checkpoint `fodder`)

1. Komad (`@tat18_11komad_01`): "Look, I have your fodder", then the banthas (`tat18_bantha*` spawn once the quest is at `huntche_y`; `tat18_banthspeak`,
   `k_ptat_banthalur` leads them to the camp with the fodder, quest 50), "I have led the bantha back", the mines, the dragon (`k_ptat_spwnkrayt`,
   `tat_KraytDead`), the dragon pearl. Walk with the safe `X,Y` stops (part 11), never the path graph.
2. The Krayt cave `tat18_kraytcave` (334,300) and the Star Map (`k_tat_star_map` 376.8,340.4; `tat18_starspeak`): the hologram, `K_STAR_MAP`.
3. The Calo Nord / Darth Bandon ambush (`ambush_*` waypoints at the camp, `tat_ambush_spawns` 370,348, `tat_test` 320,312, `K_KALO_BANDON`).
4. Back to Czerka: the Chieftain's Gaffi Stick for the bounty (`tat17ag_sandbounty` 150); the Dune Sea exit.
5. Not played: the swoop track, the cantina and Komad's lodge, Fazza, Jawa rescue (`tat17aa_jawarescue`) and the war with the Sand People
   (take the bounty, do not wear the clothing, kill the Chieftain), Marlena Venn and Tanis (`tat18aa_tanistrapped`), the Ithorian, Jawa traders.
