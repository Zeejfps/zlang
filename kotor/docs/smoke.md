# Module smoke test

Every module of the install (117), started headless straight into the module with a default party (the player, Carth and Bastila, the test bot in god mode touring the area and fighting what is hostile in sight) and left running for 600 s of world time. Run by `kotor/tools/smoke/run.sh` (2026-10-04, commit 4b83f99); `--no-render --speed 8 --mute`, one process per core. Read the table as a list of things to look at: the engine has nothing to say about a module that is clean.

- **117** modules run, **0** crashed or timed out, **0** VM faults and **20** script faults, **0** load errors, **0** distinct routines missing (**0** calls, summed over modules), **0** stuck actions, **71** missing textures, **5** runs that slow down (a last tenth of the run over twice the first).
- Wall time summed over the runs: 1799 s; the slowest loop was 3.6402593 ms per tick on average (tat_m17aa).

Columns: **VM** faults are the VM's own invariants broken (stack underflow or overflow, bad offsets, unbalanced scripts, STORE_STATE misuse, an engine reply of the wrong kind); **script** faults are what a script (or a routine given bad arguments) did: a runaway loop, a wrong type, a routine that failed, a division by zero. **Missing** counts the routines called that no category implements (names and calls). **Stuck** is an action of a kind that should end soon (a walk, a door, a pick-up) that had run over 20 s and stood in the same place 10 s of world time later. **Load** counts error lines (`kotor:`, `visual`, panels); **Tex** the textures not found. **Tour** is the bot's stops reached of the stops it picked (waypoints, doors, placeables, triggers, talkers); **World s** the world time that passed (less than the run's length means the clock stopped: a screen or a pause held it). **ms** is the average and slowest wall time of a loop pass, with the world's ticks inside it; **ms 1st / last tenth** the average of the run's first and last tenth, in bold when the last is over twice the first (and over 0.1 ms): something piles up per tick (a mover that re-plans every frame, a list that only grows), which no module should do.

| Module | Status | VM | Script | Missing | Stuck | Load | Tex | Tour | Went on to | World s | ms avg | ms max | ms 1st / last tenth | Wall s |
|---|---|--:|--:|---|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|
| tar_m02aa | ok | - | 12 | - | - | - | 3 | 7/42 | - | 599 | 0.95 | 164 | 0.82 / 1.05 | 19 |
| tar_m02ad | ok | - | 8 | - | - | - | - | 2/45 | - | 599 | 2.40 | 139 | **0.91 / 3.18** | 46 |
| tat_m17af | ok | - | - | - | - | - | 17 | 5/17 | - | 599 | 2.66 | 144 | 2.85 / 2.27 | 49 |
| STUNT_06 | ok | - | - | - | - | - | 4 | - | stunt_07, m12ab | 86 | 0.77 | 130 | - | 5 |
| STUNT_07 | ok | - | - | - | - | - | 4 | - | m12ab | 59 | 0.70 | 56 | - | 4 |
| M12ab | ok | - | - | - | - | - | 4 | - | - | 40 | 0.34 | 34 | - | 2 |
| STUNT_18 | ok | - | - | - | - | - | 4 | - | stunt_34, m12ab | 146 | 0.33 | 41 | - | 4 |
| STUNT_34 | ok | - | - | - | - | - | 4 | - | m12ab | 74 | 0.30 | 47 | - | 3 |
| STUNT_57 | ok | - | - | - | - | - | 3 | 4/17 | - | 599 | 0.45 | 95 | 0.55 / 0.46 | 10 |
| STUNT_56a | ok | - | - | - | - | - | 3 | 6/6 | stunt_57 | 599 | 0.22 | 113 | 0.70 / 0.16 | 7 |
| korr_m36aa | ok | - | - | - | - | - | 2 | 17/45 | - | 599 | 0.78 | 109 | **0.43 / 0.97** | 15 |
| tar_m10aa | ok | - | - | - | - | - | 2 | 14/40 | - | 599 | 0.72 | 147 | 0.89 / 0.59 | 15 |
| manm28ab | ok | - | - | - | - | - | 2 | 17/23 | - | 599 | 0.72 | 83 | 1.95 / 0.31 | 15 |
| end_m01aa | ok | - | - | - | - | - | 2 | 36/47 | - | 599 | 0.62 | 216 | 1.21 / 0.46 | 14 |
| tar_m10ab | ok | - | - | - | - | - | 2 | 36/36 | tar_m10aa | 599 | 0.43 | 248 | 0.62 / 0.36 | 9 |
| korr_m39aa | ok | - | - | - | - | - | 2 | 45/45 | korr_m36aa | 599 | 0.27 | 283 | 0.63 / 0.22 | 7 |
| tat_m17ae | ok | - | - | - | - | - | 1 | 6/18 | - | 599 | 2.42 | 160 | 2.65 / 2.07 | 44 |
| tar_m04aa | ok | - | - | - | - | - | 1 | 10/48 | - | 599 | 2.04 | 161 | 1.42 / 2.09 | 38 |
| manm26ad | ok | - | - | - | - | - | 1 | 1/58 | - | 599 | 1.07 | 165 | 1.09 / 1.01 | 21 |
| tar_m03ab | ok | - | - | - | - | - | 1 | 46/46 | - | 599 | 1.03 | 107 | 4.87 / 0.65 | 21 |
| tar_m08aa | ok | - | - | - | - | - | 1 | 25/58 | - | 599 | 0.79 | 170 | 1.20 / 0.63 | 16 |
| tar_m05aa | ok | - | - | - | - | - | 1 | 48/48 | tar_m04aa | 599 | 0.75 | 394 | 1.09 / 0.80 | 15 |
| tat_m17ag | ok | - | - | - | - | - | 1 | 10/10 | - | 138 | 0.73 | 37 | 2.15 / 0.41 | 15 |
| STUNT_03a | ok | - | - | - | - | - | 1 | 2/2 | tar_m08aa | 599 | 0.64 | 385 | 0.91 / 0.59 | 14 |
| tar_m10ac | ok | - | - | - | - | - | 1 | 24/43 | - | 599 | 0.63 | 187 | 0.74 / 0.57 | 14 |
| end_m01ab | ok | - | - | - | - | - | 1 | 10/27 | - | 599 | 0.51 | 182 | 1.00 / 0.45 | 12 |
| korr_m38aa | ok | - | - | - | - | - | 1 | 14/29 | - | 599 | 0.50 | 104 | 0.62 / 0.28 | 10 |
| tar_m03aa | ok | - | - | - | - | - | 1 | 40/40 | tar_m03ab | 599 | 0.38 | 152 | 0.84 / 0.18 | 10 |
| kas_m23ac | ok | - | - | - | - | - | 1 | 4/6 | - | 599 | 0.29 | 113 | 0.36 / 0.28 | 8 |
| unk_m41ac | ok | - | - | - | - | - | - | 12/24 | unk_m43aa | 599 | 1.17 | 178 | **0.44 / 1.27** | 23 |
| kas_m23aa | ok | - | - | - | - | - | - | 18/36 | - | 599 | 1.07 | 73 | **0.61 / 1.89** | 23 |
| korr_m33ab | ok | - | - | - | - | - | - | 32/32 | korr_m33aa | 599 | 0.52 | 218 | **0.28 / 0.60** | 11 |
| tat_m17aa | ok | - | - | - | - | - | - | 8/51 | - | 599 | 3.64 | 347 | 2.87 / 3.29 | 68 |
| manm26ae | ok | - | - | - | - | - | - | 4/59 | - | 599 | 3.13 | 217 | 2.66 / 3.51 | 59 |
| tat_m17ac | ok | - | - | - | - | - | - | 4/7 | - | 599 | 2.04 | 44 | 2.07 / 1.82 | 38 |
| manm27aa | ok | - | - | - | - | - | - | 0/76 | - | 599 | 2.01 | 226 | 1.99 / 2.03 | 39 |
| lev_m40aa | ok | - | - | - | - | - | - | 3/57 | - | 599 | 1.69 | 193 | 2.28 / 0.64 | 32 |
| tar_m02ab | ok | - | - | - | - | - | - | 5/49 | - | 599 | 1.63 | 123 | 1.20 / 1.66 | 32 |
| manm26ab | ok | - | - | - | - | - | - | 6/48 | - | 599 | 1.59 | 162 | 1.58 / 1.62 | 31 |
| manm28ac | ok | - | - | - | - | - | - | 17/27 | - | 599 | 1.53 | 146 | 1.64 / 0.27 | 29 |
| tar_m02ac | ok | - | - | - | - | - | - | 6/45 | - | 599 | 1.50 | 144 | 1.17 / 1.60 | 30 |
| manm26aa | ok | - | - | - | - | - | - | 0/45 | - | 599 | 1.36 | 156 | 1.31 / 1.33 | 26 |
| korr_m35aa | ok | - | - | - | - | - | - | 0/47 | - | 599 | 1.34 | 162 | 1.51 / 1.34 | 26 |
| unk_m42aa | ok | - | - | - | - | - | - | 8/57 | - | 599 | 1.28 | 312 | 1.53 / 1.13 | 25 |
| tar_m03ae | ok | - | - | - | - | - | - | 33/33 | tar_m03aa | 599 | 1.24 | 347 | 1.40 / 0.24 | 24 |
| unk_m43aa | ok | - | - | - | - | - | - | 9/51 | - | 599 | 1.24 | 142 | 1.67 / 1.10 | 24 |
| korr_m33aa | ok | - | - | - | - | - | - | 20/47 | - | 599 | 1.23 | 236 | 1.09 / 1.21 | 25 |
| danm16 | ok | - | - | - | - | - | - | 19/48 | - | 599 | 1.17 | 118 | 2.56 / 0.62 | 23 |
| danm14aa | ok | - | - | - | - | - | - | 42/42 | - | 92 | 1.02 | 66 | 0.87 / 0.97 | 21 |
| STUNT_19 | ok | - | - | - | - | - | - | 8/8 | unk_m44aa | 599 | 0.99 | 225 | 1.00 / 1.02 | 20 |
| unk_m44aa | ok | - | - | - | - | - | - | 14/49 | - | 599 | 0.97 | 127 | 1.43 / 0.93 | 19 |
| danm15 | ok | - | - | - | - | - | - | 7/23 | - | 599 | 0.96 | 79 | 1.20 / 0.86 | 21 |
| tat_m20aa | ok | - | - | - | - | - | - | 8/33 | - | 599 | 0.96 | 98 | 0.67 / 1.07 | 18 |
| lev_m40ab | ok | - | - | - | - | - | - | 15/61 | - | 599 | 0.93 | 258 | 1.08 / 0.96 | 18 |
| tar_m02af | ok | - | - | - | - | - | - | 0/15 | - | 599 | 0.92 | 48 | 0.85 / 0.92 | 18 |
| kas_m23ab | ok | - | - | - | - | - | - | 3/5 | - | 599 | 0.90 | 108 | 0.97 / 0.96 | 21 |
| manm26ac | ok | - | - | - | - | - | - | 46/46 | - | 599 | 0.88 | 150 | 3.91 / 0.65 | 17 |
| tar_m09aa | ok | - | - | - | - | - | - | 44/57 | - | 599 | 0.83 | 234 | 1.18 / 0.57 | 17 |
| danm13 | ok | - | - | - | - | - | - | 60/60 | stunt_00 | 353 | 0.78 | 263 | 0.98 / 0.69 | 16 |
| lev_m40ad | ok | - | - | - | - | - | - | 28/28 | lev_m40ab | 599 | 0.78 | 285 | 1.10 / 0.76 | 16 |
| tat_m17ab | ok | - | - | - | - | - | - | 3/22 | - | 599 | 0.72 | 167 | 0.69 / 0.73 | 14 |
| tar_m11aa | ok | - | - | - | - | - | - | 39/50 | - | 599 | 0.69 | 134 | 0.81 / 0.34 | 14 |
| tat_m17ad | ok | - | - | - | - | - | - | 5/15 | - | 599 | 0.68 | 69 | 0.62 / 0.71 | 13 |
| kas_m22ab | ok | - | - | - | - | - | - | 17/50 | - | 599 | 0.67 | 433 | 0.93 / 0.52 | 17 |
| sta_m45ab | ok | - | - | - | - | - | - | 12/39 | - | 599 | 0.66 | 184 | 0.81 / 0.62 | 14 |
| kas_m25aa | ok | - | - | - | - | - | - | 23/42 | - | 599 | 0.64 | 110 | 0.77 / 1.09 | 16 |
| lev_m40ac | ok | - | - | - | - | - | - | 7/41 | - | 599 | 0.64 | 496 | 0.90 / 0.57 | 13 |
| sta_m45aa | ok | - | - | - | - | - | - | 36/53 | - | 599 | 0.62 | 171 | 1.05 / 0.74 | 13 |
| korr_m38ab | ok | - | - | - | - | - | - | 6/38 | - | 599 | 0.60 | 119 | 0.61 / 0.61 | 12 |
| sta_m45ac | ok | - | - | - | - | - | - | 47/47 | - | 599 | 0.59 | 99 | 0.52 / 0.75 | 12 |
| tar_m02ae | ok | - | - | - | - | - | - | 49/49 | tar_m02ac | 599 | 0.58 | 326 | 1.05 / 0.48 | 14 |
| kas_m24aa | ok | - | - | - | - | - | - | 55/55 | kas_m22ab | 599 | 0.58 | 651 | 1.98 / 0.39 | 15 |
| ebo_m41aa | ok | - | - | - | - | - | - | 30/30 | - | 37 | 0.51 | 83 | 0.62 / 0.50 | 13 |
| unk_m44ab | ok | - | - | - | - | - | - | 28/30 | - | 599 | 0.50 | 43 | 0.30 / 0.55 | 10 |
| tat_m18ac | ok | - | - | - | - | - | - | 35/55 | - | 599 | 0.50 | 173 | 0.38 / 0.44 | 10 |
| manm28ad | ok | - | - | - | - | - | - | 10/23 | - | 599 | 0.49 | 100 | 0.45 / 0.51 | 11 |
| tat_m18aa | ok | - | - | - | - | - | - | 31/63 | - | 599 | 0.49 | 387 | 1.38 / 0.47 | 11 |
| tar_m03af | ok | - | - | - | - | - | - | 15/34 | tar_m03mg | 599 | 0.49 | 77 | 0.59 / 0.22 | 11 |
| manm28aa | ok | - | - | - | - | - | - | 48/48 | manm26ae | 599 | 0.49 | 301 | 0.82 / 0.40 | 10 |
| kas_m23ad | ok | - | - | - | - | - | - | 13/13 | kas_m23aa | 599 | 0.48 | 133 | 0.74 / 0.26 | 13 |
| unk_m44ac | ok | - | - | - | - | - | - | 25/25 | - | 599 | 0.48 | 91 | 0.36 / 0.50 | 10 |
| tar_m03ad | ok | - | - | - | - | - | - | 36/36 | tar_m03aa | 599 | 0.48 | 308 | 0.96 / 0.31 | 12 |
| unk_m41ad | ok | - | - | - | - | - | - | 12/28 | - | 599 | 0.47 | 62 | 0.62 / 0.44 | 10 |
| korr_m37aa | ok | - | - | - | - | - | - | 38/38 | - | 599 | 0.47 | 104 | 0.35 / 0.58 | 11 |
| danm14ac | ok | - | - | - | - | - | - | 7/37 | - | 599 | 0.44 | 94 | 0.50 / 0.41 | 10 |
| danm14ad | ok | - | - | - | - | - | - | 16/27 | - | 599 | 0.39 | 52 | 0.44 / 0.31 | 10 |
| sta_m45ad | ok | - | - | - | - | - | - | 39/39 | - | 599 | 0.38 | 99 | 0.80 / 0.23 | 9 |
| ebo_m12aa | ok | - | - | - | - | - | - | 39/39 | - | 3 | 0.38 | 59 | 0.41 / 0.37 | 9 |
| tar_m05ab | ok | - | - | - | - | - | - | 44/44 | - | 599 | 0.37 | 85 | 0.40 / 0.22 | 8 |
| tat_m18ab | ok | - | - | - | - | - | - | 51/51 | - | 599 | 0.36 | 117 | 0.45 / 0.22 | 8 |
| manm26mg | ok | - | - | - | - | - | - | - | - | 599 | 0.32 | 75 | 0.37 / 0.39 | 8 |
| danm14ab | ok | - | - | - | - | - | - | 20/33 | - | 599 | 0.31 | 69 | 0.41 / 0.32 | 8 |
| STUNT_12 | ok | - | - | - | - | - | - | 12/12 | ebo_m12aa | 599 | 0.31 | 141 | 1.27 / 0.10 | 8 |
| unk_m41ab | ok | - | - | - | - | - | - | 30/30 | - | 599 | 0.30 | 72 | 1.11 / 0.11 | 7 |
| danm14ae | ok | - | - | - | - | - | - | 14/41 | - | 599 | 0.30 | 58 | 0.27 / 0.33 | 8 |
| STUNT_31b | ok | - | - | - | - | - | - | 2/2 | lev_m40ac | 599 | 0.30 | 137 | 0.78 / 0.25 | 8 |
| STUNT_51a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.29 | 260 | 0.67 / 0.21 | 8 |
| korr_m34aa | ok | - | - | - | - | - | - | 20/28 | - | 599 | 0.28 | 142 | 0.45 / 0.26 | 6 |
| tar_m03mg | ok | - | - | - | - | - | - | - | - | 599 | 0.27 | 36 | 0.31 / 0.26 | 7 |
| STUNT_14 | ok | - | - | - | - | - | - | 8/8 | ebo_m12aa | 599 | 0.27 | 185 | 1.28 / 0.12 | 7 |
| STUNT_50a | ok | - | - | - | - | - | - | 4/4 | sta_m45ac | 599 | 0.27 | 193 | 0.49 / 0.21 | 8 |
| STUNT_44 | ok | - | - | - | - | - | - | 2/2 | ebo_m12aa | 599 | 0.24 | 166 | 0.61 / 0.11 | 7 |
| STUNT_16 | ok | - | - | - | - | - | - | 2/2 | ebo_m40aa | 599 | 0.24 | 467 | 0.90 / 0.13 | 7 |
| tat_m17mg | ok | - | - | - | - | - | - | - | - | 599 | 0.24 | 55 | 0.32 / 0.23 | 6 |
| ebo_m40ad | ok | - | - | - | - | - | - | 13/13 | - | 599 | 0.21 | 72 | 0.27 / 0.21 | 7 |
| ebo_m46ab | ok | - | - | - | - | - | - | 7/7 | - | 599 | 0.20 | 58 | 0.26 / 0.13 | 7 |
| STUNT_42 | ok | - | - | - | - | - | - | 3/3 | ebo_m12aa | 599 | 0.20 | 102 | 0.51 / 0.09 | 6 |
| kas_m22aa | ok | - | - | - | - | - | - | 53/53 | ebo_m12aa | 599 | 0.20 | 171 | 0.85 / 0.10 | 7 |
| tar_m11ab | ok | - | - | - | - | - | - | 6/6 | - | 599 | 0.19 | 81 | 0.47 / 0.13 | 5 |
| liv_m99aa | ok | - | - | - | - | - | - | 31/31 | - | 599 | 0.19 | 62 | 0.27 / 0.17 | 5 |
| unk_m41aa | ok | - | - | - | - | - | - | 30/30 | ebo_m41aa | 599 | 0.16 | 141 | 0.40 / 0.12 | 4 |
| STUNT_54a | ok | - | - | - | - | - | - | 4/4 | stunt_55a | 599 | 0.16 | 118 | 0.63 / 0.10 | 6 |
| tar_m09ab | ok | - | - | - | - | - | - | 5/5 | - | 599 | 0.16 | 68 | 0.55 / 0.07 | 5 |
| STUNT_35 | ok | - | - | - | - | - | - | 2/2 | ebo_m41aa | 599 | 0.14 | 92 | 0.30 / 0.13 | 5 |
| STUNT_55a | ok | - | - | - | - | - | - | 3/3 | - | 599 | 0.13 | 42 | 0.41 / 0.10 | 6 |
| ebo_m40aa | ok | - | - | - | - | - | - | 10/10 | - | 599 | 0.11 | 52 | 0.17 / 0.08 | 5 |
| STUNT_00 | ok | - | - | - | - | - | - | 1/1 | - | 599 | 0.11 | 40 | 0.19 / 0.11 | 3 |

## Faults and load errors

| Module | Script / error | Kind | Count |
|---|---|---|--:|
| tar_m02aa | k_ai_master | the instruction budget ran out | 6 |
| tar_m02aa | k_def_endconv | the instruction budget ran out | 6 |
| tar_m02ad | k_ai_master | the instruction budget ran out | 4 |
| tar_m02ad | k_def_endconv | the instruction budget ran out | 4 |

## Slowest modules

| Module | ms per loop pass | slowest pass ms | wall s |
|---|--:|--:|--:|
| tat_m17aa | 3.64 | 347 | 68 |
| manm26ae | 3.13 | 217 | 59 |
| tat_m17af | 2.66 | 144 | 49 |
| tat_m17ae | 2.42 | 160 | 44 |
| tar_m02ad | 2.40 | 139 | 46 |
| tat_m17ac | 2.04 | 44 | 38 |
| tar_m04aa | 2.04 | 161 | 38 |
| manm27aa | 2.01 | 226 | 39 |

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
