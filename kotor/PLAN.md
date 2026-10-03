# KOTOR in ctxlang: plan

The orchestrator keeps this file current. Rules and layout are in [AGENTS.md](AGENTS.md).

## Status

| Stage | What | State |
|---|---|---|
| 0 | [Foundations](#0-foundations): multi-directory builds, RE pipeline, format docs, SDL+GL spike | done but 0.5 |
| 1 | [Data layer](#1-data-layer): resources, GFF and tables, textures, models, walkmeshes, audio, NCS VM, Bink | in progress |
| 2 | [Rendering](#2-rendering): the render seam, GL 4.1 backend, viewers | in progress |
| 3 | [Engine core](#3-engine-core): modules, objects, scene, camera, movement, scripting runtime | planned |
| 4 | [GUI and presentation](#4-gui-and-presentation): GUI system, menus, HUD, dialogue, movies | planned |
| 5 | [Rules](#5-rules): d20 combat, feats, powers, effects, items, party, AI | planned |
| 6 | [Persistence](#6-persistence): saves and loads | planned |
| 7 | [Minigames](#7-minigames): pazaak, swoop racing, turrets | planned |
| 8 | [Playthrough](#8-playthrough): the game start to finish, performance, polish | planned |

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
