# Module smoke test

Every module of the install (117), started headless straight into the module with a default party (the player, Carth and Bastila, the test bot in god mode touring the area and fighting what is hostile in sight) and left running for 600 s of world time. Run by `kotor/tools/smoke/run.sh` (2026-10-03, commit 1059cc0); `--no-render --speed 8 --mute`, one process per core. Read the table as a list of things to look at: the engine has nothing to say about a module that is clean.

- **117** modules run, **0** crashed or timed out, **0** VM faults and **27** script faults, **0** load errors, **0** distinct routines missing (**0** calls, summed over modules), **0** stuck actions, **71** missing textures, **1** runs that slow down (a last tenth of the run over twice the first).
- Wall time summed over the runs: 1590 s; the slowest loop was 1.9081303 ms per tick on average (tar_m04aa).

Columns: **VM** faults are the VM's own invariants broken (stack underflow or overflow, bad offsets, unbalanced scripts, STORE_STATE misuse, an engine reply of the wrong kind); **script** faults are what a script (or a routine given bad arguments) did: a runaway loop, a wrong type, a routine that failed, a division by zero. **Missing** counts the routines called that no category implements (names and calls). **Stuck** is an action of a kind that should end soon (a walk, a door, a pick-up) that had run over 20 s and stood in the same place 10 s of world time later. **Load** counts error lines (`kotor:`, `visual`, panels); **Tex** the textures not found. **Tour** is the bot's stops reached of the stops it picked (waypoints, doors, placeables, triggers, talkers); **World s** the world time that passed (less than the run's length means the clock stopped: a screen or a pause held it). **ms** is the average and slowest wall time of a loop pass, with the world's ticks inside it; **ms 1st / last tenth** the average of the run's first and last tenth, in bold when the last is over twice the first (and over 0.1 ms): something piles up per tick (a mover that re-plans every frame, a list that only grows), which no module should do.

| Module | Status | VM | Script | Missing | Stuck | Load | Tex | Tour | Went on to | World s | ms avg | ms max | ms 1st / last tenth | Wall s |
|---|---|--:|--:|---|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|
| tar_m02ad | ok | - | 15 | - | - | - | - | 45/45 | tar_m02ab | 599 | 0.79 | 1643 | 0.92 / 0.59 | 16 |
| tar_m02aa | ok | - | 12 | - | - | - | 3 | 7/42 | - | 599 | 0.99 | 294 | 1.03 / 1.04 | 19 |
| tat_m17af | ok | - | - | - | - | - | 17 | 5/17 | - | 599 | 0.87 | 642 | 1.23 / 0.65 | 18 |
| STUNT_06 | ok | - | - | - | - | - | 4 | - | stunt_07, m12ab | 86 | 0.75 | 231 | - | 5 |
| STUNT_34 | ok | - | - | - | - | - | 4 | - | m12ab | 74 | 0.64 | 509 | - | 2 |
| M12ab | ok | - | - | - | - | - | 4 | - | - | 40 | 0.61 | 198 | - | 3 |
| STUNT_07 | ok | - | - | - | - | - | 4 | - | m12ab | 59 | 0.53 | 147 | - | 3 |
| STUNT_18 | ok | - | - | - | - | - | 4 | - | stunt_34, m12ab | 146 | 0.50 | 282 | - | 3 |
| STUNT_57 | ok | - | - | - | - | - | 3 | 4/17 | - | 599 | 0.71 | 148 | 0.78 / 0.67 | 14 |
| STUNT_56a | ok | - | - | - | - | - | 3 | 6/6 | stunt_57 | 599 | 0.35 | 422 | 1.23 / 0.21 | 8 |
| tar_m10aa | ok | - | - | - | - | - | 2 | 6/40 | - | 599 | 0.93 | 300 | 0.93 / 1.20 | 22 |
| end_m01aa | ok | - | - | - | - | - | 2 | 32/47 | - | 599 | 0.83 | 154 | 1.45 / 0.54 | 16 |
| tar_m10ab | ok | - | - | - | - | - | 2 | 36/36 | tar_m10aa | 599 | 0.45 | 283 | 1.06 / 0.35 | 10 |
| korr_m36aa | ok | - | - | - | - | - | 2 | 45/45 | - | 599 | 0.38 | 344 | 0.58 / 0.33 | 9 |
| manm28ab | ok | - | - | - | - | - | 2 | 14/23 | - | 599 | 0.33 | 125 | 0.70 / 0.23 | 10 |
| korr_m39aa | ok | - | - | - | - | - | 2 | 45/45 | korr_m36aa | 599 | 0.29 | 304 | 0.61 / 0.29 | 7 |
| tar_m04aa | ok | - | - | - | - | - | 1 | 10/48 | - | 599 | 1.91 | 2768 | 2.71 / 1.69 | 38 |
| tar_m08aa | ok | - | - | - | - | - | 1 | 26/58 | - | 599 | 0.98 | 265 | 1.76 / 0.78 | 20 |
| manm26ad | ok | - | - | - | - | - | 1 | 2/58 | - | 599 | 0.97 | 128 | 1.14 / 0.94 | 19 |
| end_m01ab | ok | - | - | - | - | - | 1 | 10/27 | - | 599 | 0.92 | 70 | 0.75 / 0.96 | 17 |
| STUNT_03a | ok | - | - | - | - | - | 1 | 2/2 | tar_m08aa | 599 | 0.76 | 1591 | 1.02 / 0.60 | 15 |
| tat_m17ae | ok | - | - | - | - | - | 1 | 6/18 | - | 599 | 0.71 | 175 | 0.80 / 0.69 | 14 |
| tar_m05aa | ok | - | - | - | - | - | 1 | 48/48 | tar_m04aa | 599 | 0.65 | 1202 | 1.62 / 0.54 | 14 |
| tar_m03aa | ok | - | - | - | - | - | 1 | 40/40 | tar_m03ab | 599 | 0.58 | 860 | 2.03 / 0.16 | 12 |
| tat_m17ag | ok | - | - | - | - | - | 1 | 10/10 | - | 138 | 0.56 | 407 | 1.03 / 0.39 | 13 |
| tar_m10ac | ok | - | - | - | - | - | 1 | 24/43 | - | 599 | 0.51 | 139 | 0.63 / 0.52 | 12 |
| korr_m38aa | ok | - | - | - | - | - | 1 | 12/29 | - | 599 | 0.39 | 131 | 0.60 / 0.29 | 8 |
| tar_m03ab | ok | - | - | - | - | - | 1 | 46/46 | - | 599 | 0.39 | 205 | 1.22 / 0.12 | 12 |
| kas_m23ac | ok | - | - | - | - | - | 1 | 4/6 | - | 599 | 0.38 | 87 | 0.41 / 0.37 | 9 |
| unk_m41ac | ok | - | - | - | - | - | - | 12/24 | unk_m43aa | 599 | 1.11 | 396 | **0.48 / 1.02** | 22 |
| manm27aa | ok | - | - | - | - | - | - | 0/76 | - | 599 | 1.85 | 159 | 1.89 / 1.83 | 35 |
| korr_m35aa | ok | - | - | - | - | - | - | 0/47 | - | 599 | 1.85 | 585 | 3.09 / 1.41 | 35 |
| tar_m02ac | ok | - | - | - | - | - | - | 6/45 | - | 599 | 1.71 | 1202 | 2.20 / 1.66 | 33 |
| tat_m18ac | ok | - | - | - | - | - | - | 35/55 | - | 599 | 1.62 | 299 | 0.92 / 1.37 | 31 |
| tat_m17aa | ok | - | - | - | - | - | - | 8/51 | - | 599 | 1.58 | 173 | 1.41 / 1.55 | 30 |
| tar_m02ab | ok | - | - | - | - | - | - | 5/49 | - | 599 | 1.54 | 170 | 1.32 / 1.51 | 29 |
| kas_m23aa | ok | - | - | - | - | - | - | 18/36 | - | 599 | 1.42 | 84 | 0.88 / 1.47 | 27 |
| unk_m42aa | ok | - | - | - | - | - | - | 8/57 | - | 599 | 1.37 | 860 | 2.19 / 1.00 | 27 |
| manm26aa | ok | - | - | - | - | - | - | 0/45 | - | 599 | 1.37 | 395 | 1.62 / 1.34 | 27 |
| manm26ab | ok | - | - | - | - | - | - | 6/48 | - | 599 | 1.34 | 222 | 1.45 / 1.33 | 25 |
| tat_m18ab | ok | - | - | - | - | - | - | 26/51 | - | 599 | 1.32 | 1548 | 3.03 / 0.85 | 27 |
| manm26ae | ok | - | - | - | - | - | - | 4/59 | - | 599 | 1.23 | 342 | 1.36 / 1.22 | 29 |
| tar_m11aa | ok | - | - | - | - | - | - | 37/50 | - | 599 | 1.23 | 372 | 1.32 / 1.51 | 23 |
| unk_m44aa | ok | - | - | - | - | - | - | 1/49 | - | 599 | 1.20 | 333 | 1.73 / 0.87 | 23 |
| korr_m33aa | ok | - | - | - | - | - | - | 20/47 | - | 599 | 1.17 | 247 | 1.01 / 1.27 | 23 |
| unk_m43aa | ok | - | - | - | - | - | - | 9/51 | - | 599 | 1.17 | 520 | 1.84 / 0.80 | 24 |
| lev_m40ad | ok | - | - | - | - | - | - | 28/28 | lev_m40ab | 599 | 1.03 | 1513 | 2.22 / 0.94 | 20 |
| lev_m40aa | ok | - | - | - | - | - | - | 3/57 | - | 599 | 0.99 | 1230 | 2.05 / 0.44 | 20 |
| danm13 | ok | - | - | - | - | - | - | 60/60 | stunt_00 | 360 | 0.98 | 887 | 0.82 / 0.84 | 18 |
| STUNT_19 | ok | - | - | - | - | - | - | 8/8 | unk_m44aa | 599 | 0.97 | 746 | 1.68 / 0.96 | 19 |
| lev_m40ab | ok | - | - | - | - | - | - | 15/61 | - | 599 | 0.94 | 225 | 0.93 / 1.04 | 18 |
| danm14aa | ok | - | - | - | - | - | - | 42/42 | - | 92 | 0.91 | 94 | 1.06 / 0.86 | 18 |
| kas_m25aa | ok | - | - | - | - | - | - | 23/42 | - | 599 | 0.90 | 242 | 0.84 / 1.47 | 17 |
| tar_m03ae | ok | - | - | - | - | - | - | 33/33 | tar_m03aa | 599 | 0.87 | 462 | 1.72 / 0.28 | 18 |
| tat_m18aa | ok | - | - | - | - | - | - | 29/63 | - | 599 | 0.81 | 822 | 2.11 / 0.46 | 17 |
| tat_m20aa | ok | - | - | - | - | - | - | 7/33 | - | 599 | 0.80 | 261 | 0.93 / 0.95 | 16 |
| tat_m17ad | ok | - | - | - | - | - | - | 5/15 | - | 599 | 0.80 | 453 | 1.11 / 0.78 | 17 |
| tat_m17ab | ok | - | - | - | - | - | - | 3/22 | - | 599 | 0.77 | 458 | 0.99 / 0.70 | 17 |
| korr_m38ab | ok | - | - | - | - | - | - | 6/38 | - | 599 | 0.70 | 238 | 0.60 / 0.72 | 15 |
| sta_m45aa | ok | - | - | - | - | - | - | 37/53 | - | 599 | 0.70 | 572 | 1.89 / 0.64 | 14 |
| lev_m40ac | ok | - | - | - | - | - | - | 8/41 | - | 599 | 0.69 | 556 | 0.92 / 0.73 | 15 |
| tar_m02ae | ok | - | - | - | - | - | - | 49/49 | tar_m02ac | 599 | 0.69 | 1103 | 1.21 / 0.53 | 14 |
| tar_m09aa | ok | - | - | - | - | - | - | 17/57 | - | 599 | 0.69 | 151 | 1.17 / 0.36 | 14 |
| manm26ac | ok | - | - | - | - | - | - | 46/46 | - | 599 | 0.68 | 1000 | 1.85 / 0.43 | 16 |
| sta_m45ab | ok | - | - | - | - | - | - | 14/39 | - | 599 | 0.67 | 158 | 0.84 / 0.57 | 16 |
| korr_m33ab | ok | - | - | - | - | - | - | 32/32 | korr_m33aa | 599 | 0.65 | 1726 | 0.34 / 0.52 | 13 |
| danm16 | ok | - | - | - | - | - | - | 16/48 | - | 599 | 0.65 | 78 | 1.06 / 0.33 | 13 |
| tat_m17ac | ok | - | - | - | - | - | - | 4/7 | - | 599 | 0.64 | 1529 | 1.45 / 0.52 | 15 |
| tar_m03ad | ok | - | - | - | - | - | - | 36/36 | tar_m03aa | 599 | 0.63 | 953 | 1.27 / 0.41 | 13 |
| tar_m03af | ok | - | - | - | - | - | - | 15/34 | tar_m03mg | 599 | 0.62 | 469 | 1.04 / 0.25 | 13 |
| kas_m22ab | ok | - | - | - | - | - | - | 18/50 | - | 599 | 0.59 | 311 | 0.73 / 0.47 | 12 |
| sta_m45ac | ok | - | - | - | - | - | - | 33/47 | - | 599 | 0.56 | 724 | 1.35 / 0.37 | 15 |
| manm28ac | ok | - | - | - | - | - | - | 21/27 | - | 599 | 0.55 | 282 | 0.52 / 0.26 | 12 |
| liv_m99aa | ok | - | - | - | - | - | - | 19/31 | - | 599 | 0.55 | 219 | 0.59 / 0.58 | 11 |
| kas_m24aa | ok | - | - | - | - | - | - | 55/55 | kas_m22ab | 599 | 0.51 | 711 | 1.49 / 0.40 | 10 |
| kas_m23ad | ok | - | - | - | - | - | - | 13/13 | kas_m23aa | 599 | 0.49 | 302 | 0.87 / 0.32 | 11 |
| manm28aa | ok | - | - | - | - | - | - | 48/48 | manm26ae | 599 | 0.48 | 786 | 1.22 / 0.42 | 11 |
| danm14ac | ok | - | - | - | - | - | - | 12/37 | - | 599 | 0.48 | 69 | 0.53 / 0.42 | 10 |
| sta_m45ad | ok | - | - | - | - | - | - | 39/39 | - | 599 | 0.48 | 106 | 0.87 / 0.25 | 12 |
| danm15 | ok | - | - | - | - | - | - | 7/23 | - | 599 | 0.47 | 60 | 0.46 / 0.48 | 10 |
| tar_m05ab | ok | - | - | - | - | - | - | 33/44 | - | 599 | 0.46 | 1007 | 1.19 / 0.28 | 13 |
| unk_m41ad | ok | - | - | - | - | - | - | 28/28 | - | 599 | 0.45 | 84 | 0.66 / 0.37 | 9 |
| manm28ad | ok | - | - | - | - | - | - | 10/23 | - | 599 | 0.44 | 52 | 0.33 / 0.49 | 9 |
| tar_m02af | ok | - | - | - | - | - | - | 0/15 | - | 599 | 0.44 | 42 | 0.40 / 0.58 | 9 |
| kas_m23ab | ok | - | - | - | - | - | - | 3/5 | - | 599 | 0.41 | 91 | 0.47 / 0.40 | 9 |
| ebo_m41aa | ok | - | - | - | - | - | - | 30/30 | - | 30 | 0.39 | 67 | 0.33 / 0.41 | 8 |
| ebo_m12aa | ok | - | - | - | - | - | - | 39/39 | - | 3 | 0.38 | 40 | 0.40 / 0.37 | 9 |
| danm14ad | ok | - | - | - | - | - | - | 17/27 | - | 599 | 0.36 | 49 | 0.44 / 0.40 | 8 |
| unk_m44ab | ok | - | - | - | - | - | - | 28/30 | - | 599 | 0.36 | 241 | 0.56 / 0.34 | 12 |
| danm14ab | ok | - | - | - | - | - | - | 20/33 | - | 599 | 0.35 | 68 | 0.50 / 0.29 | 8 |
| tar_m03mg | ok | - | - | - | - | - | - | - | - | 599 | 0.34 | 337 | 0.64 / 0.28 | 8 |
| korr_m37aa | ok | - | - | - | - | - | - | 38/38 | - | 599 | 0.32 | 77 | 0.44 / 0.28 | 9 |
| korr_m34aa | ok | - | - | - | - | - | - | 20/28 | - | 599 | 0.31 | 250 | 0.53 / 0.30 | 7 |
| STUNT_12 | ok | - | - | - | - | - | - | 12/12 | ebo_m12aa | 599 | 0.31 | 631 | 1.13 / 0.12 | 8 |
| STUNT_31b | ok | - | - | - | - | - | - | 2/2 | lev_m40ac | 599 | 0.30 | 428 | 0.69 / 0.26 | 7 |
| manm26mg | ok | - | - | - | - | - | - | - | - | 599 | 0.30 | 115 | 0.36 / 0.29 | 6 |
| STUNT_51a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.30 | 426 | 0.73 / 0.21 | 7 |
| unk_m41ab | ok | - | - | - | - | - | - | 30/30 | - | 599 | 0.30 | 177 | 1.34 / 0.20 | 8 |
| STUNT_14 | ok | - | - | - | - | - | - | 8/8 | ebo_m12aa | 599 | 0.27 | 1146 | 0.92 / 0.12 | 6 |
| kas_m22aa | ok | - | - | - | - | - | - | 53/53 | ebo_m12aa | 599 | 0.27 | 534 | 1.28 / 0.09 | 6 |
| STUNT_50a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.26 | 203 | 0.53 / 0.27 | 6 |
| tar_m09ab | ok | - | - | - | - | - | - | 5/5 | - | 599 | 0.25 | 926 | 1.26 / 0.19 | 9 |
| danm14ae | ok | - | - | - | - | - | - | 11/41 | - | 599 | 0.24 | 40 | 0.23 / 0.26 | 6 |
| tat_m17mg | ok | - | - | - | - | - | - | - | - | 599 | 0.24 | 48 | 0.28 / 0.22 | 6 |
| unk_m41aa | ok | - | - | - | - | - | - | 30/30 | ebo_m41aa | 599 | 0.24 | 1672 | 1.33 / 0.12 | 6 |
| STUNT_44 | ok | - | - | - | - | - | - | 2/2 | ebo_m12aa | 599 | 0.22 | 596 | 0.45 / 0.12 | 6 |
| STUNT_42 | ok | - | - | - | - | - | - | 3/3 | ebo_m12aa | 599 | 0.22 | 353 | 0.47 / 0.13 | 5 |
| unk_m44ac | ok | - | - | - | - | - | - | 25/25 | - | 599 | 0.22 | 77 | 0.29 / 0.12 | 6 |
| STUNT_16 | ok | - | - | - | - | - | - | 2/2 | ebo_m40aa | 599 | 0.21 | 325 | 0.79 / 0.11 | 6 |
| STUNT_54a | ok | - | - | - | - | - | - | 4/4 | stunt_55a | 599 | 0.16 | 310 | 0.83 / 0.09 | 5 |
| ebo_m46ab | ok | - | - | - | - | - | - | 7/7 | - | 599 | 0.16 | 38 | 0.22 / 0.05 | 4 |
| STUNT_35 | ok | - | - | - | - | - | - | 2/2 | ebo_m41aa | 599 | 0.16 | 550 | 0.74 / 0.09 | 4 |
| tar_m11ab | ok | - | - | - | - | - | - | 6/6 | - | 599 | 0.14 | 60 | 0.30 / 0.08 | 4 |
| STUNT_55a | ok | - | - | - | - | - | - | 3/3 | - | 599 | 0.12 | 70 | 0.34 / 0.10 | 3 |
| ebo_m40aa | ok | - | - | - | - | - | - | 10/10 | - | 599 | 0.09 | 42 | 0.11 / 0.08 | 4 |
| ebo_m40ad | ok | - | - | - | - | - | - | 13/13 | - | 599 | 0.08 | 44 | 0.13 / 0.07 | 2 |
| STUNT_00 | ok | - | - | - | - | - | - | 1/1 | - | 599 | 0.08 | 169 | 0.19 / 0.05 | 4 |

## Faults and load errors

| Module | Script / error | Kind | Count |
|---|---|---|--:|
| tar_m02aa | k_ai_master | the instruction budget ran out | 6 |
| tar_m02aa | k_def_endconv | the instruction budget ran out | 6 |
| tar_m02ad | k_ai_master | the instruction budget ran out | 8 |
| tar_m02ad | k_def_endconv | the instruction budget ran out | 7 |

## Slowest modules

| Module | ms per loop pass | slowest pass ms | wall s |
|---|--:|--:|--:|
| tar_m04aa | 1.91 | 2768 | 38 |
| manm27aa | 1.85 | 159 | 35 |
| korr_m35aa | 1.85 | 585 | 35 |
| tar_m02ac | 1.71 | 1202 | 33 |
| tat_m18ac | 1.62 | 299 | 31 |
| tat_m17aa | 1.58 | 173 | 30 |
| tar_m02ab | 1.54 | 170 | 29 |
| kas_m23aa | 1.42 | 84 | 27 |

## Missing textures

None of these is a lookup bug: `resls --module M --texture NAME` finds no TPC or TGA of the name in any container the module sees, and the whole texture extraction (the three quality packs, the GUI pack, patch, every BIF) holds no file of that name either. They are references the data makes to textures it does not ship, and the original skips them the same way (nothing is drawn with it). A mesh flagged lightmapped whose lightmap is missing is drawn lit by the dynamic lights, as the original's draw-path choice does (0x00470d30 drops the lightmap path when the lightmap texture is not usable).

- **lightmap**: stale lightmap names of the form `mNNxx_NN_aNNNNN` on a few meshes of room and door models (the neighbouring meshes of the same room name `..._lm0`); `dor_lhr02_a00004` is a mesh of the Endar Spire's door model.
- **diffuse**: typos in cutscene stunt models (`m13aa_c01_char*` of danm13, `m41ad_c01_char*` of unk_m41ad, reused by STUNT_56a and STUNT_57): `p_BastillaH01` (the real head is `p_bastilah04`), `PHeyea`, `h_f_lo01headtest` (a TXI without an image), `w_Vbroswrd01` (the real texture is `w_vbroswrd_001`).
- **environment map**: `mycubemap`, named by `mgf_glass01`'s TXI (its sibling `lts_win01` names the existing `CM_mycubemap`).
- **particle texture**: `fxp_aurabesh01`, an emitter of the Ebon Hawk turret minigame (M12ab) and the cutscenes that lead to it.

| Texture | Asked for as | Modules |
|---|---|---|
| `dor_lhr02_a00004` | lightmap | end_m01aa, end_m01ab |
| `fxp_aurabesh01` | an emitter | M12ab, STUNT_06, STUNT_07, STUNT_18, STUNT_34 |
| `h_f_lo01headtest` | diffuse | STUNT_56a, STUNT_57 |
| `m01aa_04a_a0002t` | lightmap | end_m01aa |
| `m02aa_01a_a0005a` | lightmap | tar_m02aa |
| `m02aa_02a_a0004o` | lightmap | tar_m02aa |
| `m02aa_03a_a00060` | lightmap | tar_m02aa |
| `m03ab_02a_a00074` | lightmap | tar_m03aa, tar_m03ab |
| `m04aa_04a_a0002i` | lightmap | tar_m04aa, tar_m05aa |
| `m08aa_10a_a0005j` | lightmap | STUNT_03a, tar_m08aa |
| `m10aa_06a_a0000p` | lightmap | tar_m10aa, tar_m10ab |
| `m10aa_06a_a0001g` | lightmap | tar_m10aa, tar_m10ab |
| `m10ac_33a_a0009b` | lightmap | tar_m10ac |
| `m12ab_01a_a00000` | lightmap | M12ab, STUNT_06, STUNT_07, STUNT_18, STUNT_34 |
| `m12ab_01a_a00001` | lightmap | M12ab, STUNT_06, STUNT_07, STUNT_18, STUNT_34 |
| `m17ae_00a_a001lv` | lightmap | tat_m17ae, tat_m17ag |
| `m17af_00a_a002ik` | lightmap | tat_m17af |
| `m17af_00a_a002j1` | lightmap | tat_m17af |
| `m17af_00a_a002jh` | lightmap | tat_m17af |
| `m17af_00a_a002jw` | lightmap | tat_m17af |
| `m17af_00a_a002ka` | lightmap | tat_m17af |
| `m17af_00a_a002kn` | lightmap | tat_m17af |
| `m17af_00a_a002kz` | lightmap | tat_m17af |
| `m17af_00a_a002la` | lightmap | tat_m17af |
| `m17af_00a_a002lk` | lightmap | tat_m17af |
| `m17af_00a_a002lt` | lightmap | tat_m17af |
| `m17af_00a_a002m1` | lightmap | tat_m17af |
| `m17af_00a_a002m8` | lightmap | tat_m17af |
| `m17af_00a_a002me` | lightmap | tat_m17af |
| `m17af_00a_a002mj` | lightmap | tat_m17af |
| `m17af_00a_a002mn` | lightmap | tat_m17af |
| `m17af_00a_a002mq` | lightmap | tat_m17af |
| `m17af_00a_a002ms` | lightmap | tat_m17af |
| `m23ac_01a_a00042` | lightmap | kas_m23ac |
| `m26ad_grz_a0000y` | lightmap | manm26ad |
| `m28ab_13a_a000r1` | lightmap | manm28ab |
| `m28ab_13a_a000r2` | lightmap | manm28ab |
| `m36aa_01_a000pj` | lightmap | korr_m36aa, korr_m39aa |
| `m36aa_01_a000pk` | lightmap | korr_m36aa, korr_m39aa |
| `m38ab_08_a00049` | lightmap | korr_m38aa |
| `mycubemap` | environment map | M12ab, STUNT_06, STUNT_07, STUNT_18, STUNT_34 |
| `p_bastillah01` | diffuse | STUNT_56a, STUNT_57 |
| `pheyea` | diffuse | STUNT_56a, STUNT_57 |
