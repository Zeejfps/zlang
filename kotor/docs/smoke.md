# Module smoke test

Every module of the install (117), started headless straight into the module with a default party (the player, Carth and Bastila, the test bot in god mode fighting what is hostile in sight) and left running for 60 s of world time. Run by `kotor/tools/smoke/run.sh` (2026-10-03, commit aa55f11); `--no-render --speed 8 --mute`, one process per core. Read the table as a list of things to look at: the engine has nothing to say about a module that is clean.

- **117** modules run, **0** crashed or timed out, **0** VM faults and **1** script faults, **0** load errors, **0** distinct routines missing (**0** calls, summed over modules), **0** stuck actions, **70** missing textures.
- Wall time summed over the runs: 312 s; the slowest loop was 2.7806487 ms per tick on average (korr_m35aa).

Columns: **VM** faults are the VM's own invariants broken (stack underflow or overflow, bad offsets, unbalanced scripts, STORE_STATE misuse, an engine reply of the wrong kind); **script** faults are what a script (or a routine given bad arguments) did: a runaway loop, a wrong type, a routine that failed, a division by zero. **Missing** counts the routines called that no category implements (names and calls). **Stuck** is an action of a kind that should end soon (a walk, a door, a pick-up) that had run over 20 s and stood in the same place 10 s of world time later. **Load** counts error lines (`kotor:`, `visual`, panels); **Tex** the textures not found. **ms** is the average and slowest wall time of a loop pass, with the world's ticks inside it.

| Module | Status | VM | Script | Missing | Stuck | Load | Tex | ms avg | ms max | Wall s |
|---|---|--:|--:|---|--:|--:|--:|--:|--:|--:|
| lev_m40aa | ok | - | 1 | - | - | - | - | 0.61 | 89 | 2 |
| tat_m17af | ok | - | - | - | - | - | 17 | 0.26 | 78 | 2 |
| STUNT_06 | ok | - | - | - | - | - | 4 | 0.91 | 100 | 4 |
| STUNT_07 | ok | - | - | - | - | - | 4 | 0.42 | 74 | 3 |
| STUNT_34 | ok | - | - | - | - | - | 4 | 0.38 | 52 | 2 |
| M12ab | ok | - | - | - | - | - | 4 | 0.31 | 28 | 2 |
| STUNT_56a | ok | - | - | - | - | - | 3 | 1.05 | 274 | 4 |
| STUNT_57 | ok | - | - | - | - | - | 3 | 0.82 | 103 | 3 |
| tar_m02ae | ok | - | - | - | - | - | 3 | 0.65 | 189 | 2 |
| tar_m02aa | ok | - | - | - | - | - | 3 | 0.50 | 177 | 3 |
| end_m01aa | ok | - | - | - | - | - | 2 | 1.09 | 126 | 5 |
| tar_m10aa | ok | - | - | - | - | - | 2 | 0.71 | 133 | 2 |
| tar_m10ab | ok | - | - | - | - | - | 2 | 0.62 | 155 | 2 |
| STUNT_44 | ok | - | - | - | - | - | 2 | 0.57 | 70 | 3 |
| korr_m36aa | ok | - | - | - | - | - | 2 | 0.28 | 71 | 2 |
| manm28ab | ok | - | - | - | - | - | 2 | 0.21 | 52 | 2 |
| tar_m04aa | ok | - | - | - | - | - | 1 | 1.54 | 211 | 5 |
| tar_m08aa | ok | - | - | - | - | - | 1 | 0.89 | 116 | 4 |
| manm26ad | ok | - | - | - | - | - | 1 | 0.73 | 132 | 3 |
| kas_m24aa | ok | - | - | - | - | - | 1 | 0.70 | 168 | 3 |
| tar_m10ac | ok | - | - | - | - | - | 1 | 0.65 | 140 | 3 |
| STUNT_42 | ok | - | - | - | - | - | 1 | 0.54 | 54 | 2 |
| tat_m17ag | ok | - | - | - | - | - | 1 | 0.52 | 53 | 3 |
| end_m01ab | ok | - | - | - | - | - | 1 | 0.48 | 61 | 3 |
| korr_m38aa | ok | - | - | - | - | - | 1 | 0.47 | 47 | 2 |
| tar_m03ae | ok | - | - | - | - | - | 1 | 0.38 | 118 | 2 |
| tar_m03ab | ok | - | - | - | - | - | 1 | 0.34 | 78 | 2 |
| tat_m17ae | ok | - | - | - | - | - | 1 | 0.26 | 56 | 2 |
| kas_m23ac | ok | - | - | - | - | - | 1 | 0.11 | 38 | 2 |
| korr_m35aa | ok | - | - | - | - | - | - | 2.78 | 214 | 7 |
| unk_m42aa | ok | - | - | - | - | - | - | 1.74 | 151 | 4 |
| danm13 | ok | - | - | - | - | - | - | 1.64 | 308 | 6 |
| sta_m45aa | ok | - | - | - | - | - | - | 1.61 | 95 | 5 |
| manm28aa | ok | - | - | - | - | - | - | 1.50 | 168 | 4 |
| danm16 | ok | - | - | - | - | - | - | 1.18 | 213 | 4 |
| unk_m44aa | ok | - | - | - | - | - | - | 1.12 | 91 | 3 |
| STUNT_19 | ok | - | - | - | - | - | - | 1.11 | 220 | 3 |
| manm27aa | ok | - | - | - | - | - | - | 1.05 | 150 | 4 |
| STUNT_03a | ok | - | - | - | - | - | - | 1.04 | 89 | 4 |
| unk_m43aa | ok | - | - | - | - | - | - | 1.04 | 140 | 3 |
| kas_m22aa | ok | - | - | - | - | - | - | 1.01 | 88 | 4 |
| lev_m40ab | ok | - | - | - | - | - | - | 1.00 | 133 | 3 |
| STUNT_14 | ok | - | - | - | - | - | - | 1.00 | 202 | 4 |
| manm26ac | ok | - | - | - | - | - | - | 0.93 | 96 | 4 |
| tar_m09aa | ok | - | - | - | - | - | - | 0.93 | 164 | 4 |
| STUNT_12 | ok | - | - | - | - | - | - | 0.91 | 88 | 3 |
| tar_m02ac | ok | - | - | - | - | - | - | 0.89 | 238 | 3 |
| tar_m02ab | ok | - | - | - | - | - | - | 0.88 | 219 | 3 |
| tar_m05aa | ok | - | - | - | - | - | - | 0.80 | 68 | 2 |
| STUNT_51a | ok | - | - | - | - | - | - | 0.74 | 77 | 3 |
| STUNT_16 | ok | - | - | - | - | - | - | 0.70 | 267 | 3 |
| manm26ab | ok | - | - | - | - | - | - | 0.66 | 150 | 3 |
| tat_m18ab | ok | - | - | - | - | - | - | 0.65 | 57 | 3 |
| tar_m03af | ok | - | - | - | - | - | - | 0.63 | 70 | 3 |
| manm26ae | ok | - | - | - | - | - | - | 0.63 | 115 | 3 |
| STUNT_54a | ok | - | - | - | - | - | - | 0.61 | 180 | 3 |
| tat_m17aa | ok | - | - | - | - | - | - | 0.58 | 144 | 2 |
| manm26aa | ok | - | - | - | - | - | - | 0.57 | 161 | 3 |
| STUNT_50a | ok | - | - | - | - | - | - | 0.56 | 290 | 3 |
| kas_m23ad | ok | - | - | - | - | - | - | 0.55 | 59 | 3 |
| tat_m20aa | ok | - | - | - | - | - | - | 0.54 | 87 | 3 |
| kas_m22ab | ok | - | - | - | - | - | - | 0.53 | 100 | 3 |
| danm14aa | ok | - | - | - | - | - | - | 0.51 | 160 | 4 |
| korr_m33aa | ok | - | - | - | - | - | - | 0.49 | 154 | 3 |
| tat_m18aa | ok | - | - | - | - | - | - | 0.47 | 77 | 2 |
| tat_m18ac | ok | - | - | - | - | - | - | 0.45 | 89 | 3 |
| tar_m03aa | ok | - | - | - | - | - | - | 0.45 | 88 | 2 |
| STUNT_35 | ok | - | - | - | - | - | - | 0.44 | 187 | 3 |
| kas_m25aa | ok | - | - | - | - | - | - | 0.44 | 69 | 3 |
| STUNT_18 | ok | - | - | - | - | - | - | 0.40 | 42 | 2 |
| STUNT_31b | ok | - | - | - | - | - | - | 0.40 | 186 | 2 |
| danm14ac | ok | - | - | - | - | - | - | 0.37 | 98 | 3 |
| tar_m03mg | ok | - | - | - | - | - | - | 0.37 | 48 | 2 |
| tar_m05ab | ok | - | - | - | - | - | - | 0.37 | 69 | 2 |
| STUNT_55a | ok | - | - | - | - | - | - | 0.36 | 45 | 2 |
| tar_m02af | ok | - | - | - | - | - | - | 0.35 | 40 | 2 |
| tar_m02ad | ok | - | - | - | - | - | - | 0.34 | 84 | 2 |
| danm14ad | ok | - | - | - | - | - | - | 0.34 | 73 | 3 |
| manm28ac | ok | - | - | - | - | - | - | 0.33 | 96 | 2 |
| manm26mg | ok | - | - | - | - | - | - | 0.33 | 85 | 2 |
| tar_m11aa | ok | - | - | - | - | - | - | 0.32 | 91 | 2 |
| lev_m40ad | ok | - | - | - | - | - | - | 0.31 | 89 | 2 |
| tar_m11ab | ok | - | - | - | - | - | - | 0.31 | 50 | 1 |
| kas_m23aa | ok | - | - | - | - | - | - | 0.30 | 39 | 2 |
| danm14ab | ok | - | - | - | - | - | - | 0.30 | 81 | 3 |
| lev_m40ac | ok | - | - | - | - | - | - | 0.28 | 60 | 2 |
| sta_m45ac | ok | - | - | - | - | - | - | 0.27 | 60 | 2 |
| unk_m41ad | ok | - | - | - | - | - | - | 0.26 | 44 | 2 |
| korr_m38ab | ok | - | - | - | - | - | - | 0.25 | 64 | 1 |
| korr_m33ab | ok | - | - | - | - | - | - | 0.24 | 74 | 1 |
| tat_m17mg | ok | - | - | - | - | - | - | 0.23 | 29 | 2 |
| tat_m17ad | ok | - | - | - | - | - | - | 0.23 | 45 | 1 |
| sta_m45ab | ok | - | - | - | - | - | - | 0.23 | 32 | 2 |
| tat_m17ab | ok | - | - | - | - | - | - | 0.22 | 70 | 2 |
| tar_m03ad | ok | - | - | - | - | - | - | 0.21 | 58 | 2 |
| liv_m99aa | ok | - | - | - | - | - | - | 0.21 | 57 | 2 |
| unk_m41ab | ok | - | - | - | - | - | - | 0.20 | 38 | 2 |
| tat_m17ac | ok | - | - | - | - | - | - | 0.20 | 63 | 2 |
| danm14ae | ok | - | - | - | - | - | - | 0.19 | 49 | 3 |
| korr_m39aa | ok | - | - | - | - | - | - | 0.19 | 41 | 1 |
| unk_m44ab | ok | - | - | - | - | - | - | 0.19 | 51 | 2 |
| unk_m41aa | ok | - | - | - | - | - | - | 0.18 | 36 | 2 |
| korr_m34aa | ok | - | - | - | - | - | - | 0.18 | 65 | 2 |
| sta_m45ad | ok | - | - | - | - | - | - | 0.18 | 41 | 1 |
| korr_m37aa | ok | - | - | - | - | - | - | 0.18 | 48 | 2 |
| ebo_m46ab | ok | - | - | - | - | - | - | 0.18 | 80 | 3 |
| ebo_m12aa | ok | - | - | - | - | - | - | 0.18 | 86 | 3 |
| danm15 | ok | - | - | - | - | - | - | 0.16 | 60 | 2 |
| ebo_m40ad | ok | - | - | - | - | - | - | 0.16 | 59 | 3 |
| ebo_m40aa | ok | - | - | - | - | - | - | 0.16 | 99 | 3 |
| manm28ad | ok | - | - | - | - | - | - | 0.15 | 34 | 2 |
| unk_m44ac | ok | - | - | - | - | - | - | 0.13 | 40 | 2 |
| unk_m41ac | ok | - | - | - | - | - | - | 0.13 | 35 | 1 |
| kas_m23ab | ok | - | - | - | - | - | - | 0.12 | 41 | 2 |
| STUNT_00 | ok | - | - | - | - | - | - | 0.12 | 45 | 2 |
| ebo_m41aa | ok | - | - | - | - | - | - | 0.11 | 45 | 3 |
| tar_m09ab | ok | - | - | - | - | - | - | 0.11 | 37 | 2 |

## Faults and load errors

| Module | Script / error | Kind | Count |
|---|---|---|--:|
| lev_m40aa | k_plev_escsetup | the instruction budget ran out | 1 |

## Slowest modules

| Module | ms per loop pass | slowest pass ms | wall s |
|---|--:|--:|--:|
| korr_m35aa | 2.78 | 214 | 7 |
| unk_m42aa | 1.74 | 151 | 4 |
| danm13 | 1.64 | 308 | 6 |
| sta_m45aa | 1.61 | 95 | 5 |
| tar_m04aa | 1.54 | 211 | 5 |
| manm28aa | 1.50 | 168 | 4 |
| danm16 | 1.18 | 213 | 4 |
| unk_m44aa | 1.12 | 91 | 3 |
