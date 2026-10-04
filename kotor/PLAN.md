# KOTOR in ctxlang: plan

The orchestrator keeps this file current. Rules and layout are in [AGENTS.md](AGENTS.md).

## Status

| Stage | What | State |
|---|---|---|
| 0 | [Foundations](#0-foundations): multi-directory builds, RE pipeline, format docs, SDL+GL spike | done |
| 1 | [Data layer](#1-data-layer): resources, GFF and tables, textures, models, walkmeshes, audio, NCS VM, Bink | done |
| 2 | [Rendering](#2-rendering): the render seam, GL 4.1 backend, viewers | done |
| 3 | [Engine core](#3-engine-core): modules, objects, scene, camera, movement, scripting runtime | done; open items below |
| 4 | [GUI and presentation](#4-gui-and-presentation): GUI system, menus, HUD, dialogue, movies | done; open items below |
| 5 | [Rules](#5-rules): d20 combat, feats, powers, effects, items, party, AI | done (docs/mechanics/*.md) |
| 6 | [Persistence](#6-persistence): saves and loads | done |
| 7 | [Minigames](#7-minigames): pazaak, swoop racing, turrets | done |
| 8 | [Playthrough](#8-playthrough): the game start to finish, performance, polish | main story played in segments from crafted states, both endings; side quests and one continuous run open |
| 9 | Enhanced rendering (docs/design/enhanced-render.md): 11 optional modern effects | done |

## 0. Foundations

1. **Multi-directory programs** (ctxlang driver). A build program can make an executable from
   several directories (`kotor/lib/*`, `kotor/game`), so subsystems live apart and tools share
   them. Concurrent builds of different programs don't share scratch files. Unchanged builds skip
   the C compiler.
2. **RE pipeline.** Ghidra headless analysis of `swkotor.exe`, exports that agents can grep
   (decompiled functions, strings, RTTI classes, imports), the NWScript routine table located,
   `docs/re/README.md`.
3. **Format docs and inventory.** `docs/formats/*.md` for every file format the game reads, each
   checked against the install with a probe. An inventory of the install: resource types and
   counts, modules, what lives where.
4. **SDL2 + OpenGL 4.1 core spike** from ctxlang: a window, a core context, a textured triangle,
   offscreen capture to PNG (the screenshot path every rendering agent uses to check its work).
5. **Language for a big program** (in progress): C output split into files compiled in parallel
   (one 96K-line C file takes ~60 s in gcc at -O1), namespaces spanning files, integer `match`,
   multi-line strings, std math and formatted printing, `@offset_of`.

Done: 1 (driver, `e16a186`), 2 (`8f14e74`; behaviour RE continues for stage 3), 3 (`e99e33c`,
`d0549e0`, `a1e642d`), 4 (`6524ca8`).

## 1. Data layer

Each reader comes with a corpus tool that runs it over every resource of its kind.

*Done:* all eight, each checked over the whole install (`fmtcheck`, `texcheck`, `mdlcheck`,
`animcheck`, `walkcheck`, `sndcheck`, `ncsrun`/`ncsdis`, `binkcheck`). Designs in `docs/design/`.

1. `res`: resource types, KEY/BIF, ERF/MOD/SAV, RIM, Override, TexturePacks, the resource manager
   and its search order.
2. `gff` (read and write), `twoda`, `tlk`, LYT, VIS, SSF, LIP, TXI, LTR, PTH.
3. `tex`: TPC (DXT1/DXT5, RGB/RGBA/grey, mipmaps, cube maps), TGA, TXI-driven properties.
4. `mdl`: MDL/MDX: node tree, trimesh, skin, dangly, AABB, emitter, light, reference, lightsaber;
   controllers and animations; supermodel chains.
5. `bwm`: WOK/PWK/DWK walkmeshes, AABB trees, materials from `surfacemat.2da`.
6. `snd`: WAV (PCM, IMA-ADPCM, and the MP3-in-WAV the game ships), MP3, a mixer, SDL output.
7. `nwvm`: the NCS bytecode VM, stack frames, `STORE_STATE`/actions, engine-routine dispatch from
   `nwscript.nss`.
8. `bink`: Bink video and audio for `movies/*.bik`.

## 2. Rendering

1. The `render` interface: handles for textures, meshes and render targets; a frame described as
   data (views, draw items, materials, lights, 2D quads and text); designed so a second backend
   needs no game changes.
2. The GL 4.1 backend: shaders for KOTOR's materials (diffuse, lightmap, envmap, bump, additive and
   blended transparency, self-illumination, fog), GPU skinning, dangly meshes, particles, 2D.
3. Viewers: a model viewer and an area viewer that write PNGs, then interactive ones.

## 3. Engine core

Module loading (IFO, ARE, GIT, LYT, VIS), the object model (creatures, placeables, doors,
triggers, waypoints, sounds, encounters, stores), scene graph and animation playback, character
assembly (body, head, equipment), the camera, input, walking on walkmeshes, pathfinding, the
script runtime (events, action queues, `DelayCommand`, `AssignCommand`) and the engine routines,
area transitions, the game loop and time.

## 4. GUI and presentation

GUI files and fonts, the main menu, character creation, the HUD, dialogue (camera, VO, lip sync,
replies), inventory, equipment, character sheet, abilities, map, journal, messages, options,
loading screens, Bink movies, music and ambient sound.

## 5. Rules

The d20 rules as KOTOR has them: attack and damage, feats, Force powers, effects, saving throws,
skills, items and properties, classes and level-up, XP, party selection and NPC AI, stores,
stealth, mines, workbenches, combat round timing and animations.

## 6. Persistence

Save and load (SAV ERF: `savenfo`, `partytable`, `globalvars`, each module's state), autosave,
module state across transitions.

## 7. Minigames

Pazaak, swoop racing, turret sequences.

## 8. Playthrough

Play from the Endar Spire to the end. Fix what breaks, profile, polish.

## Backlog

Open items, by area. Remove an item when it lands. Bugs the user reports while playing go to fix
agents first. The checks every merge runs: `sh kotor/out/orch_build.sh ci` (a clean build from
committed kotor), the Endar Spire replay (`FAST=1`, 0 faults to tar_m02af),
`kotor/tools/combat/companions.sh`, `kotor/tools/combat/corpses.sh` and `kotor/tools/camcheck/run.sh`
(the last needs a Python with numpy first on PATH).

**Story QA** (docs/playthrough-*.md; each planet's log says where it stopped and how to resume):
- One continuous playthrough from New Game to an ending, with real input and no crafted states.
- Side quests on every planet: Taris (the Sith uniform route, side quests), Dantooine (the
  Sandral/Matale feud, the Mandalorian raiders), Tatooine (the swoop track, the war branch, Bandon's
  ambush, the mines/lair dragon fight), Kashyyyk (Chuundar's side), Manaan (Sunry's trial), Korriban
  (the tomb puzzles, Dustil, Yuthura's redemption, Jorak/Kel/the holocron), the Unknown World (the
  Temple's shield droids and turrets, the floor panels, the cave's pillar puzzle; chains use cheats there),
  the Hawk's turret fight before the Unknown World.
- The Dantooine ruins' Guardian Droids' shield (30 off every hit): check against the original's data.
- k_sup_galaxymap names film "5_9", which doesn't exist (05_9.bik does): find what the original does.
- The commoner AI runaway in k_ai_master (BioWare's own loop) shows as script faults in some fights.

**Effects** (docs/re/particles.md, docs/design/vfx.md): the world scene never simulates emitters on
placeables or area models, so fire, smoke and steam placeables draw nothing in game; `fx model plc_*`
and cast models without emitters (v_fpush_cas) show nothing; chunk-model debris, `bounce`, wind,
world-space particles, Linked and Lightning emitters; bolts' streak length is ours (2.4x).

**Enhanced rendering** (docs/design/enhanced-render.md): depth of field blurs the whole of a cutscene's
wide shot on Manaan's sea floor (`kotor/out/dof_blur_m12b.png`); shadows come from creatures only;
Frame Buffer Effects lack the original's lens flares and film noise; tessellation is off (hairline gaps
between body pieces).

**Displays** (docs/mechanics/graphics.md): exclusive fullscreen, macOS Retina and Windows display
scaling were never tested on real hardware.

**Controls and HUD** (docs/mechanics/controls.md, items-skills.md): auto-target's off-screen arrows, its
1.5 s hold on a dead target and the post-auto-pause timer; mine entries dimmed when the leader is dead;
the equip list ignores "Hide Unequippable" and lacks the hexagonal icon frames; followers' feet may
slide about 20% while catching up (the speed cap in UpdateFollowLeader is an assumption); T tooltips on
hold, X flourish, the bench's 3D item models, arrow-key planet cycling.
- `kotor/tools/items/check.sh` has 6 stale patterns (items-skills.md, "Known failing checks"): the
  security scripts click BTN_TARGET0 where Security is now BTN_TARGET1, and two expect the old `ui fx` line.

**Force** (docs/mechanics/force.md): the look of programmed effects (the hold cage), the thrown
saber's missing blade, the saber throw range (10 m vs RE's 15 m), companions' power choices beyond one
checked cast.

**Audio:** the sound-object scheduler, `prioritygroups.2da` limits, EAX-style reverb.

**RE:** the exports were rebuilt without false noreturn functions (docs/re/noreturn-fix.md); 740 cited
functions changed, so recheck an older note before relying on it (noreturn-fix-recheck.tsv).
`kotor/re/noreturn/` holds ~600 MB of scratch from that rebuild (the user decides whether to delete it).

**Rendering backends** (discussed, not started): a GL 4.6 tier for Linux/Windows, Metal (needs a Mac
to verify), Direct3D 11; each is a new backend behind the render contract.

**Language:** posix `mem::pages` still clears all of its memory up front; a read-only borrow for
context fields (readers take `*World` today so they can return views and never copy it).
