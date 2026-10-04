# Module smoke test

Every module of the install (117), started headless straight into the module with a default party (the player, Carth and Bastila, the test bot in god mode touring the area and fighting what is hostile in sight) and left running for 600 s of world time. Run by `kotor/tools/smoke/run.sh` (2026-10-03, commit b2da588); `--no-render --speed 8 --mute`, one process per core. Read the table as a list of things to look at: the engine has nothing to say about a module that is clean.

- **117** modules run, **1** crashed or timed out, **0** VM faults and **17** script faults, **0** load errors, **0** distinct routines missing (**0** calls, summed over modules), **0** stuck actions, **72** missing textures.
- Wall time summed over the runs: 1794 s; the slowest loop was 5.5125203 ms per tick on average (tar_m05aa).

Columns: **VM** faults are the VM's own invariants broken (stack underflow or overflow, bad offsets, unbalanced scripts, STORE_STATE misuse, an engine reply of the wrong kind); **script** faults are what a script (or a routine given bad arguments) did: a runaway loop, a wrong type, a routine that failed, a division by zero. **Missing** counts the routines called that no category implements (names and calls). **Stuck** is an action of a kind that should end soon (a walk, a door, a pick-up) that had run over 20 s and stood in the same place 10 s of world time later. **Load** counts error lines (`kotor:`, `visual`, panels); **Tex** the textures not found. **Tour** is the bot's stops reached of the stops it picked (waypoints, doors, placeables, triggers, talkers); **World s** the world time that passed (less than the run's length means the clock stopped: a screen or a pause held it). **ms** is the average and slowest wall time of a loop pass, with the world's ticks inside it.

| Module | Status | VM | Script | Missing | Stuck | Load | Tex | Tour | Went on to | World s | ms avg | ms max | Wall s |
|---|---|--:|--:|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| korr_m37aa | **timeout** | - | - | - | - | - | - | - | - |  | 0.00 | 0 | 180 |
| tar_m02ad | ok | - | 16 | - | - | - | - | 2/45 | - | 599 | 0.78 | 274 | 16 |
| lev_m40aa | ok | - | 1 | - | - | - | - | 16/57 | - | 599 | 1.70 | 209 | 32 |
| tat_m17af | ok | - | - | - | - | - | 17 | 5/17 | - | 599 | 0.68 | 166 | 14 |
| STUNT_06 | ok | - | - | - | - | - | 4 | - | stunt_07, m12ab | 86 | 0.83 | 185 | 3 |
| STUNT_34 | ok | - | - | - | - | - | 4 | - | m12ab | 74 | 0.41 | 81 | 2 |
| STUNT_07 | ok | - | - | - | - | - | 4 | - | m12ab | 59 | 0.41 | 63 | 2 |
| STUNT_18 | ok | - | - | - | - | - | 4 | - | stunt_34, m12ab | 146 | 0.37 | 119 | 3 |
| M12ab | ok | - | - | - | - | - | 4 | - | - | 40 | 0.35 | 68 | 2 |
| tar_m02aa | ok | - | - | - | - | - | 3 | 7/42 | - | 599 | 1.16 | 741 | 23 |
| STUNT_57 | ok | - | - | - | - | - | 3 | 4/17 | - | 599 | 0.69 | 184 | 13 |
| tar_m02ae | ok | - | - | - | - | - | 3 | 49/49 | - | 599 | 0.55 | 272 | 14 |
| STUNT_56a | ok | - | - | - | - | - | 3 | 6/6 | stunt_57 | 599 | 0.25 | 145 | 6 |
| tar_m10aa | ok | - | - | - | - | - | 2 | 6/40 | - | 599 | 0.84 | 393 | 16 |
| end_m01aa | ok | - | - | - | - | - | 2 | 30/47 | - | 599 | 0.75 | 108 | 15 |
| tar_m10ab | ok | - | - | - | - | - | 2 | 36/36 | - | 599 | 0.53 | 134 | 12 |
| korr_m36aa | ok | - | - | - | - | - | 2 | 28/45 | - | 599 | 0.34 | 69 | 7 |
| manm28ab | ok | - | - | - | - | - | 2 | 17/23 | - | 599 | 0.31 | 241 | 7 |
| tar_m05aa | ok | - | - | - | - | - | 1 | 48/48 | tar_m04aa | 599 | 5.51 | 1093 | 100 |
| tar_m04aa | ok | - | - | - | - | - | 1 | 10/48 | - | 599 | 4.46 | 320 | 82 |
| manm26ad | ok | - | - | - | - | - | 1 | 2/58 | - | 599 | 1.10 | 339 | 21 |
| STUNT_03a | ok | - | - | - | - | - | 1 | 2/2 | tar_m08aa | 599 | 0.71 | 391 | 13 |
| tar_m03ae | ok | - | - | - | - | - | 1 | 33/33 | - | 599 | 0.69 | 236 | 14 |
| tat_m17ae | ok | - | - | - | - | - | 1 | 6/18 | - | 599 | 0.69 | 417 | 13 |
| tar_m08aa | ok | - | - | - | - | - | 1 | 58/58 | - | 599 | 0.69 | 211 | 14 |
| tar_m10ac | ok | - | - | - | - | - | 1 | 43/43 | - | 340 | 0.58 | 179 | 12 |
| korr_m38aa | ok | - | - | - | - | - | 1 | 11/29 | - | 599 | 0.50 | 350 | 11 |
| tat_m17ag | ok | - | - | - | - | - | 1 | 10/10 | - | 138 | 0.44 | 82 | 10 |
| tar_m03ab | ok | - | - | - | - | - | 1 | 46/46 | - | 599 | 0.37 | 331 | 9 |
| end_m01ab | ok | - | - | - | - | - | 1 | 27/27 | - | 599 | 0.36 | 123 | 8 |
| kas_m23ac | ok | - | - | - | - | - | 1 | 4/6 | - | 599 | 0.32 | 81 | 7 |
| tar_m02ac | ok | - | - | - | - | - | - | 6/45 | - | 599 | 2.34 | 674 | 45 |
| tar_m02ab | ok | - | - | - | - | - | - | 5/49 | - | 599 | 2.08 | 1141 | 39 |
| korr_m35aa | ok | - | - | - | - | - | - | 0/47 | - | 599 | 1.97 | 608 | 37 |
| manm27aa | ok | - | - | - | - | - | - | 0/76 | - | 599 | 1.84 | 203 | 36 |
| unk_m42aa | ok | - | - | - | - | - | - | 8/57 | - | 599 | 1.79 | 254 | 34 |
| tat_m18ac | ok | - | - | - | - | - | - | 35/55 | - | 599 | 1.62 | 573 | 31 |
| tat_m17aa | ok | - | - | - | - | - | - | 8/51 | - | 599 | 1.56 | 290 | 30 |
| unk_m43aa | ok | - | - | - | - | - | - | 9/51 | - | 599 | 1.50 | 460 | 29 |
| danm13 | ok | - | - | - | - | - | - | 26/60 | stunt_00 | 599 | 1.48 | 495 | 27 |
| unk_m41ac | ok | - | - | - | - | - | - | 12/24 | unk_m43aa | 599 | 1.42 | 759 | 27 |
| manm26ab | ok | - | - | - | - | - | - | 6/48 | - | 599 | 1.39 | 277 | 26 |
| manm26ae | ok | - | - | - | - | - | - | 4/59 | - | 599 | 1.38 | 134 | 27 |
| kas_m23aa | ok | - | - | - | - | - | - | 18/36 | - | 599 | 1.35 | 45 | 26 |
| manm26aa | ok | - | - | - | - | - | - | 0/45 | - | 599 | 1.32 | 308 | 25 |
| manm26ac | ok | - | - | - | - | - | - | 46/46 | - | 599 | 1.29 | 175 | 25 |
| korr_m33aa | ok | - | - | - | - | - | - | 9/47 | - | 599 | 1.14 | 205 | 22 |
| lev_m40ab | ok | - | - | - | - | - | - | 43/61 | - | 599 | 1.13 | 149 | 22 |
| tat_m17ab | ok | - | - | - | - | - | - | 3/22 | - | 599 | 0.99 | 171 | 19 |
| danm16 | ok | - | - | - | - | - | - | 0/48 | - | 599 | 0.91 | 101 | 18 |
| danm14aa | ok | - | - | - | - | - | - | 42/42 | - | 92 | 0.90 | 71 | 17 |
| STUNT_19 | ok | - | - | - | - | - | - | 8/8 | unk_m44aa | 599 | 0.88 | 646 | 17 |
| unk_m41ab | ok | - | - | - | - | - | - | 30/30 | - | 599 | 0.84 | 149 | 17 |
| kas_m25aa | ok | - | - | - | - | - | - | 23/42 | - | 599 | 0.82 | 88 | 16 |
| tar_m09aa | ok | - | - | - | - | - | - | 39/57 | - | 599 | 0.74 | 324 | 15 |
| tat_m18ab | ok | - | - | - | - | - | - | 25/51 | - | 599 | 0.74 | 83 | 14 |
| manm28aa | ok | - | - | - | - | - | - | 48/48 | manm26ae | 599 | 0.72 | 609 | 14 |
| unk_m44aa | ok | - | - | - | - | - | - | 49/49 | - | 599 | 0.71 | 233 | 15 |
| tat_m18aa | ok | - | - | - | - | - | - | 29/63 | - | 599 | 0.69 | 438 | 15 |
| tat_m17ad | ok | - | - | - | - | - | - | 5/15 | - | 599 | 0.69 | 151 | 13 |
| korr_m38ab | ok | - | - | - | - | - | - | 6/38 | - | 599 | 0.68 | 103 | 13 |
| sta_m45aa | ok | - | - | - | - | - | - | 37/53 | - | 599 | 0.65 | 165 | 13 |
| tar_m03af | ok | - | - | - | - | - | - | 15/34 | tar_m03mg | 599 | 0.63 | 766 | 14 |
| kas_m22ab | ok | - | - | - | - | - | - | 19/50 | - | 599 | 0.61 | 124 | 13 |
| tat_m20aa | ok | - | - | - | - | - | - | 8/33 | - | 599 | 0.59 | 115 | 12 |
| tar_m03aa | ok | - | - | - | - | - | - | 40/40 | - | 599 | 0.57 | 187 | 11 |
| liv_m99aa | ok | - | - | - | - | - | - | 19/31 | - | 599 | 0.56 | 48 | 12 |
| tat_m17ac | ok | - | - | - | - | - | - | 4/7 | - | 599 | 0.56 | 71 | 12 |
| tar_m11aa | ok | - | - | - | - | - | - | 50/50 | - | 599 | 0.50 | 213 | 11 |
| kas_m24aa | ok | - | - | - | - | - | - | 55/55 | kas_m22ab | 599 | 0.50 | 302 | 10 |
| danm15 | ok | - | - | - | - | - | - | 7/23 | - | 599 | 0.49 | 42 | 10 |
| manm28ad | ok | - | - | - | - | - | - | 10/23 | - | 599 | 0.47 | 49 | 10 |
| lev_m40ac | ok | - | - | - | - | - | - | 18/41 | - | 599 | 0.46 | 83 | 10 |
| kas_m23ad | ok | - | - | - | - | - | - | 13/13 | kas_m23aa | 599 | 0.44 | 262 | 9 |
| danm14ac | ok | - | - | - | - | - | - | 24/37 | - | 599 | 0.42 | 95 | 9 |
| sta_m45ab | ok | - | - | - | - | - | - | 14/39 | - | 599 | 0.40 | 192 | 8 |
| ebo_m12aa | ok | - | - | - | - | - | - | 39/39 | - | 3 | 0.40 | 73 | 9 |
| sta_m45ac | ok | - | - | - | - | - | - | 20/47 | - | 599 | 0.38 | 137 | 10 |
| tar_m02af | ok | - | - | - | - | - | - | 0/15 | - | 599 | 0.38 | 39 | 8 |
| korr_m33ab | ok | - | - | - | - | - | - | 32/32 | - | 599 | 0.38 | 86 | 8 |
| manm28ac | ok | - | - | - | - | - | - | 27/27 | - | 599 | 0.37 | 176 | 8 |
| kas_m23ab | ok | - | - | - | - | - | - | 3/5 | - | 599 | 0.36 | 35 | 7 |
| ebo_m41aa | ok | - | - | - | - | - | - | 30/30 | - | 30 | 0.36 | 38 | 8 |
| unk_m41ad | ok | - | - | - | - | - | - | 11/28 | - | 599 | 0.34 | 335 | 8 |
| STUNT_12 | ok | - | - | - | - | - | - | 12/12 | ebo_m12aa | 599 | 0.33 | 600 | 7 |
| lev_m40ad | ok | - | - | - | - | - | - | 28/28 | - | 599 | 0.33 | 86 | 7 |
| STUNT_51a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.32 | 397 | 7 |
| tar_m05ab | ok | - | - | - | - | - | - | 44/44 | - | 599 | 0.32 | 66 | 7 |
| tar_m03mg | ok | - | - | - | - | - | - | - | - | 599 | 0.31 | 154 | 7 |
| danm14ab | ok | - | - | - | - | - | - | 20/33 | - | 599 | 0.31 | 42 | 6 |
| STUNT_31b | ok | - | - | - | - | - | - | 2/2 | lev_m40ac | 599 | 0.29 | 380 | 7 |
| manm26mg | ok | - | - | - | - | - | - | - | - | 599 | 0.28 | 121 | 7 |
| danm14ad | ok | - | - | - | - | - | - | 16/27 | - | 599 | 0.28 | 42 | 6 |
| sta_m45ad | ok | - | - | - | - | - | - | 39/39 | - | 599 | 0.28 | 55 | 6 |
| tar_m03ad | ok | - | - | - | - | - | - | 36/36 | - | 599 | 0.28 | 513 | 7 |
| STUNT_50a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.27 | 407 | 6 |
| kas_m22aa | ok | - | - | - | - | - | - | 53/53 | ebo_m12aa | 599 | 0.27 | 511 | 7 |
| korr_m34aa | ok | - | - | - | - | - | - | 18/28 | - | 599 | 0.24 | 113 | 5 |
| tat_m17mg | ok | - | - | - | - | - | - | - | - | 599 | 0.24 | 42 | 6 |
| korr_m39aa | ok | - | - | - | - | - | - | 45/45 | - | 599 | 0.23 | 56 | 6 |
| STUNT_14 | ok | - | - | - | - | - | - | 8/8 | ebo_m12aa | 599 | 0.23 | 300 | 6 |
| STUNT_42 | ok | - | - | - | - | - | - | 3/3 | ebo_m12aa | 599 | 0.21 | 662 | 5 |
| STUNT_44 | ok | - | - | - | - | - | - | 2/2 | ebo_m12aa | 599 | 0.21 | 218 | 5 |
| unk_m44ac | ok | - | - | - | - | - | - | 25/25 | - | 599 | 0.20 | 112 | 6 |
| unk_m44ab | ok | - | - | - | - | - | - | 30/30 | - | 599 | 0.19 | 122 | 5 |
| danm14ae | ok | - | - | - | - | - | - | 12/41 | - | 599 | 0.18 | 43 | 4 |
| STUNT_16 | ok | - | - | - | - | - | - | 2/2 | ebo_m40aa | 599 | 0.17 | 263 | 4 |
| unk_m41aa | ok | - | - | - | - | - | - | 30/30 | ebo_m41aa | 599 | 0.16 | 800 | 5 |
| tar_m11ab | ok | - | - | - | - | - | - | 6/6 | - | 599 | 0.14 | 93 | 4 |
| STUNT_54a | ok | - | - | - | - | - | - | 4/4 | stunt_55a | 599 | 0.14 | 232 | 4 |
| STUNT_35 | ok | - | - | - | - | - | - | 2/2 | ebo_m41aa | 599 | 0.14 | 343 | 4 |
| STUNT_55a | ok | - | - | - | - | - | - | 3/3 | - | 599 | 0.13 | 111 | 3 |
| tar_m09ab | ok | - | - | - | - | - | - | 5/5 | - | 599 | 0.13 | 74 | 3 |
| ebo_m40aa | ok | - | - | - | - | - | - | 10/10 | - | 599 | 0.09 | 54 | 3 |
| ebo_m40ad | ok | - | - | - | - | - | - | 13/13 | - | 599 | 0.09 | 36 | 3 |
| STUNT_00 | ok | - | - | - | - | - | - | 1/1 | - | 599 | 0.07 | 128 | 2 |
| ebo_m46ab | ok | - | - | - | - | - | - | 7/7 | - | 599 | 0.05 | 36 | 2 |

## Faults and load errors

| Module | Script / error | Kind | Count |
|---|---|---|--:|
| lev_m40aa | k_plev_escsetup | the instruction budget ran out | 1 |
| tar_m02ad | k_ai_master | the instruction budget ran out | 8 |
| tar_m02ad | k_def_endconv | the instruction budget ran out | 8 |

## Crashes and timeouts

- `korr_m37aa`: timeout 

## Slowest modules

| Module | ms per loop pass | slowest pass ms | wall s |
|---|--:|--:|--:|
| tar_m05aa | 5.51 | 1093 | 100 |
| tar_m04aa | 4.46 | 320 | 82 |
| tar_m02ac | 2.34 | 674 | 45 |
| tar_m02ab | 2.08 | 1141 | 39 |
| korr_m35aa | 1.97 | 608 | 37 |
| manm27aa | 1.84 | 203 | 36 |
| unk_m42aa | 1.79 | 254 | 34 |
| lev_m40aa | 1.70 | 209 | 32 |
