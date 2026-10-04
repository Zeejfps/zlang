# Conversation sweep

Every dialogue of the install (1261 of them, a module's own copy of a name counting once per module that names it), walked node by node by `kotor/tools/dlgsweep/run.sh` (2026-10-03, commit eab5e3f). Each runs in a freshly entered module (30 frames of the world first) with the object that names it as the owner, a stand-in creature when none does, and the player as the other side. From the starting list the walk visits every entry and reply reachable by links; at each link it runs the Active script and counts the answer but goes on through the link whatever it was (**forced true**); at each node it runs the action script; at the end the abort script, then the normal end (the end script and every creature's and placeable's end-of-dialogue script in the area), then 30 more frames for what the scripts delayed. Scripts run as in the game: with the owner as OBJECT_SELF, the PC speaker the player.

- **1261** dialogues swept: **845** with the object that names them as owner, **390** with a stand-in creature, **26** with the player (no creature in the module).
- **29613** entries and **34746** replies; **29613** entries and **34746** replies reached; **0** dialogues with a node no link leads to.
- **21612** scripts run, **3623** Active scripts answered true and **10568** false (every link was taken regardless).
- **68** script faults in **10** dialogues; **0** dialogues called routines nothing implements; **50** dialogues name **48** distinct scripts the install does not have; **269** have an entry whose speaker is not in the module (169 with a real owner); **0** have a link past the end of its list.
- Dialogues that failed to load: **1**; processes that crashed or timed out: **0**.

A dialogue gets a row in the sections below only for something to look at. Faults in a dialogue's scripts are listed with the script that faulted and what the VM said; a fault in a script the dialogue does not name (`k_def_endconv`, `k_ai_master`) came from the area's end-of-dialogue handlers or the world frames after it.

## Script faults

| Dialogue | Module | Owner | Faults | Script: what happened |
|---|---|---|--:|---|
| tar02_drunk021 | tar_m02ab | drunk021 | 28 | k_def_endconv: the instruction budget ran out x14; k_ai_master: the instruction budget ran out x14 |
| tar02_preraid | tar_m02aa | trooper1_invis | 12 | k_def_endconv: the instruction budget ran out x6; k_ai_master: the instruction budget ran out x6 |
| tar02_bountyh022 | tar_m02ac | bountyhunt022 | 10 | k_def_endconv: the instruction budget ran out x5; k_ai_master: the instruction budget ran out x5 |
| tar02_scaredm021 | tar_m02ad | scaredmerc021 | 6 | k_def_endconv: the instruction budget ran out x3; k_ai_master: the instruction budget ran out x3 |
| tat20_09chief_01 | tat_m20aa | tat20_09chief_01 | 6 | k_ptat_tuskenmad: the instruction budget ran out x6 |
| tat20_09first_01 | tat_m20aa | tat20_09first_01 | 2 | k_ptat_tuskenmad: the instruction budget ran out x2 |
| tat20_06jawa_01 | tat_m20aa | tat20_06jawa_01 | 1 | k_ptat_tuskenmad: the instruction budget ran out x1 |
| tat20_griff | tat_m20aa | tat20_bantha | 1 | k_ptat_tuskenmad: the instruction budget ran out x1 |
| tat20_xstory_01 | tat_m20aa | tat20_bantha | 1 | k_ptat_tuskenmad: the instruction budget ran out x1 |
| tat20_xstuff_01 | tat_m20aa | tressndpplbin | 1 | k_ptat_tuskenmad: the instruction budget ran out x1 |

By script and kind:

| Script | What happened | Faults | Dialogues |
|---|---|--:|--:|
| `k_ai_master` | the instruction budget ran out | 28 | 4 |
| `k_def_endconv` | the instruction budget ran out | 28 | 4 |
| `k_ptat_tuskenmad` | the instruction budget ran out | 12 | 6 |

## Routines called that nothing implements

None: every routine the dialogues' scripts called is implemented.

## Dialogues that failed to load

| Dialogue | Process | Error |
|---|---|---|
| end_carth001 | end_m01aa__end_carth001 | dlg::no_such_dialog |

## Scripts the dialogues name that the install does not have

The engine treats a missing Active script as false and a missing action script as nothing, as the game does; the list is the data's own.

| Script | Dialogues |
|---|---|
| `0` | dan14_nemo, kas23_worrroz_01, lev40_aacompdlg, plev_elev_dlg, man26_gonto, man26_trial, tar02_janice021, tar02_zelka021 |
| `false` | k_hcan_dialog |
| `gendtalkcheck` | tar04_gendar041 |
| `hasserum` | tar04_infect041, tar04_infectf041 |
| `k_act_1000cred` | tar02_sarna021, tar02_yungenda21 |
| `k_ebn12_ckash01` | pebn_swoopdrd |
| `k_ebn12_ctat01` | pebn_swoopdrd |
| `k_ebn12_ctat02` | pebn_swoopdrd |
| `k_ebn12_ctat03` | pebn_swoopdrd |
| `k_ebn12_ctat04` | pebn_swoopdrd |
| `k_ebn12_ctat05` | pebn_swoopdrd |
| `k_ebn12_ctat06` | pebn_swoopdrd |
| `k_ebn12_ctat07` | pebn_swoopdrd |
| `k_ebn_bast1` | k_hbas_dialog |
| `k_ebn_bast2` | k_hbas_dialog |
| `k_ebn_bast3` | k_hbas_dialog |
| `k_ebn_bast4` | k_hbas_dialog |
| `k_ebn_bast5` | k_hbas_dialog |
| `k_ebn_bast6` | k_hbas_dialog |
| `k_ebn_bast7` | k_hbas_dialog |
| `k_pdan_cort01` | dan13_cort |
| `k_pdan_cort02` | dan13_cort |
| `k_pdan_cort08` | dan13_cort |
| `k_pdan_cort09` | dan13_cort |
| `k_pdan_taree01` | dan13_tareelok |
| `k_pdan_taree02` | dan13_tareelok |
| `k_pdan_taree03` | dan13_tareelok |
| `k_pdan_taree04` | dan13_tareelok |
| `k_pdan_taree05` | dan13_tareelok |
| `k_pend_carth11` | end_trask01 |
| `k_pend_comp09` | end_comp01 |
| `k_pend_comp10` | end_comp01 |
| `k_pend_comp13` | end_comp01 |
| `k_pend_repair07` | end_comp01 |
| `k_pkas_drandom09` | kas22_wookfht_01 |
| `k_pkas_drandom10` | kas22_wookfht_01 |
| `k_pkas_wookcut_b` | kas22_wookcut_01 |
| `k_pkas_wookcut_c` | kas22_wookcut_01 |
| `k_ptar_gurneytal` | tar02_gurney021 |
| `k_ptat_jagidie` | k_hjagi_dialog |
| `k_ptat_jagienemy` | k_hjagi_dialog |
| `k_ptat_jagimove` | k_hjagi_dialog |
| `k_swg_dust_pad` | k_hcar_dialog |
| `k_swg_gizka01` | k_hbas_dialog, k_hcar_dialog, k_hcan_dialog, k_hjol_dialog, k_hmis_dialog, k_hhkd_dialog, k_hjuh_dialog, k_hzaa_dialog |
| `talktest` | tar02_kebla021 |
| `talktimesreset` | tar10_bartender |
| `talktoincrement` | tar03_mission031 |
| `test003` | throw |

## Speakers that are not in the module

An entry whose Speaker tag is neither the owner nor an object in the owner's area is skipped by the flow (the conversation ends if it was the one to play). Many are spawned or placed by earlier scripts or are in another module's copy, so this is a list to read, not a list of bugs. Dialogues swept with a stand-in owner are left out (the tags are meant for their own owner's module).

| Dialogue | Module | Entries | Tags (first three) |
|---|---|--:|---|
| ambush_test | tat_m18ac | 7 | bp_calo_ambush_2,bp_calo_ambush_2,bp_calo_ambush_2 |
| dan13_cort | danm13 | 9 | dan13_garrum,dan13_tareelok,dan13_garrum |
| dan13_crattis | danm13 | 5 | Cand,Juhani,Zaalbar |
| dan13_vandar | danm13 | 4 | Mission,Juhani,Cand |
| dan14_bolook | danm14ac | 27 | Bastila,Juhani,dan14_handon |
| dan14_cutscene | danm14ad | 166 | dan14_nurik,dan14_ahlan,dan14_nurik |
| dan14_elise | danm14aa | 17 | T3M4,Carth,Bastila |
| dan14_jon | danm14aa | 11 | Juhani,Carth,Bastila |
| dan14_mdroid | danm14ab | 20 | Bastila,T3M4,T3M4 |
| dan14_nemo | danm14aa | 3 | Cand,Bastila,Bastila |
| dan14_settlerm | danm14aa | 3 | Cand,Juhani,Cand |
| dan15_ancientdrd | danm15 | 14 | Bastila,Bastila,Bastila |
| dan15_bastila | danm15 | 13 | Bastila,Bastila,Bastila |
| dan16_nurik | danm16 | 43 | dan16_rahasia,dan16_rahasia,Cand |
| dan16_rahasia | danm16 | 7 | Juhani,Bastila,Carth |
| k33_academyguard | korr_m33ab | 13 | HK47,Jolee,HK47 |
| k38a_assassindrd | korr_m38aa | 7 | T3M4,Bastila,HK47 |
| k_hcar_dialog | STUNT_34 | 1 | Bastila |
| k_hcar_dialog | STUNT_35 | 1 | Bastila |
| k_hcar_dialog | STUNT_42 | 1 | Bastila |
| k_hcar_dialog | tar_m02af | 1 | Bastila |
| k_hmis_dialog | STUNT_57 | 1 | Zaalbar |
| k_pkas_rulan2 | kas_m24aa | 14 | Rulan,Rulan,Rulan |
| k_sta_bastila | sta_m45ac | 9 | sta_bastila,sta_bastila,sta_bastila |
| k_sta_bastlast | sta_m45ac | 51 | sta_bastila,sta_bastila,sta_bastila |
| k_sta_carth | sta_m45aa | 17 | sta_carth,sta_carth,sta_carth |
| k_sta_darkcut | sta_m45ac | 8 | sta_sith1,sta_sith2,sta_sith3 |
| k_sta_lightcut | sta_m45ac | 6 | sta_bastila,sta_bastila,sta_bastila |
| kas22_chorraw_01 | kas_m22ab | 4 | Jolee,Mission,Juhani |
| kas22_czerkag_01 | kas_m22aa | 3 | Bastila,Mission,Zaalbar |
| kas22_czerkas_01 | kas_m22aa | 8 | Zaalbar,Zaalbar,Zaalbar |
| kas22_dasol_01 | kas_m22aa | 5 | Bastila,Juhani,Cand |
| kas22_dehno_01 | kas_m22ab | 18 | HK47,Cand,Carth |
| kas22_eli_01 | kas_m22aa | 7 | Juhani,Carth,Mission |
| kas22_janos_01 | kas_m22aa | 21 | Zaalbar,Zaalbar,Zaalbar |
| kas22_wookg1_01 | kas_m22ab | 2 | Zaalbar,Zaalbar |
| kas22_wookg2_01 | kas_m22ab | 3 | Zaalbar,Zaalbar,Zaalbar |
| kas23_chuunda_01 | kas_m23ad | 31 | Mission,Mission,Jolee |
| kas23_jaarak_01 | kas_m23ab | 5 | Mission,Zaalbar,Bastila |
| kas23_wookfem_01 | kas_m23aa | 7 | Jolee,Zaalbar,Zaalbar |
| kas23_woorwil_01 | kas_m23ab | 3 | Bastila,HK47,Jolee |
| kas23_worrroz_01 | kas_m23ac | 29 | kas23_jaarak_01,kas23_jaarak_01,kas23_woorwil_01 |
| kas24_gorwook_01 | kas_m24aa | 1 | Cand |
| kas24_jolee_02 | kas_m24aa | 3 | Bastila,Juhani,Mission |
| kas24_pgener_01 | kas_m24aa | 6 | HK47,Mission,Carth |
| kas24_poffice_01 | kas_m24aa | 1 | Cand |
| kas25_bike_conv | kas_m25aa | 2 | Cand,Zaalbar |
| kas25_comp_01 | kas_m25aa | 14 | Mission,Carth,Cand |
| kas25_freyyr_01 | kas_m25aa | 17 | Mission,Jolee,Jolee |
| kas25_hurt_01 | kas_m25aa | 12 | Zaalbar,Zaalbar,Zaalbar |
| kas25_ritualmark | kas_m25aa | 4 | Zaalbar,Zaalbar,Zaalbar |
| kas_k_h_bandon | kas_m24aa | 5 | kas_bandon,kas_bandon,kas_bandon |
| kas_k_h_calo | kas_m24aa | 7 | kas_calo,kas_calo,kas_calo |
| kas_xor_dialog | kas_m22aa | 42 | kas_xor1,kas_xor1,Juhani |
| kas_xor_dialog | korr_m33aa | 42 | kas_xor1,kas_xor1,Juhani |
| kas_xor_dialog | manm26ad | 42 | kas_xor1,kas_xor1,Juhani |
| kor33_czerkarep | korr_m33aa | 6 | Mission,Zaalbar,T3M4 |
| kor33_lashowe | korr_m33aa | 30 | Cand,HK47,Bastila |
| kor33_mechanic | korr_m33aa | 1 | Mission |
| kor33_mekel | korr_m33ab | 12 | Jolee,HK47,Jolee |
| kor33_mekfight1 | korr_m33ab | 12 | Jolee,Bastila,Zaalbar |
| kor33_portauth | korr_m33aa | 2 | Mission,Zaalbar |
| kor33_prospectf | korr_m33aa | 5 | Juhani,Jolee,Bastila |
| kor33_prospectm | korr_m33aa | 6 | Juhani,Jolee,Bastila |
| kor33_shaardan | korr_m33aa | 5 | Juhani,Bastila,Carth |
| kor35_kelal | korr_m35aa | 1 | Zaalbar |
| kor35_lashowe | korr_m35aa | 10 | Bastila,Carth,Bastila |
| kor35_tariga | korr_m35aa | 1 | Zaalbar |
| kor35_utharwynn | korr_m35aa | 12 | Jolee,Bastila,Carth |
| kor35_yuthuraban | korr_m35aa | 5 | Jolee,Bastila,Carth |
| kor36_dakvesser | korr_m36aa | 7 | Juhani,Juhani,Juhani |
| kor38b_mekel | korr_m38ab | 10 | HK47,T3M4,HK47 |
| kor39_starspeak | korr_m39aa | 16 | T3M4,T3M4,T3M4 |
| kor_k_h_bandon | korr_m36aa | 5 | kor_bandon,kor_bandon,kor_bandon |
| kor_k_h_calo | korr_m36aa | 7 | kor_calo,kor_calo,kor_calo |
| lev40_darthmala2 | lev_m40ac | 15 | Bastila,Bastila,Bastila |
| lev40_hangardlg | lev_m40ac | 1 | Carth |
| lev40_jolee | lev_m40aa | 10 | Jolee,LevGuard403,Jolee |
| lev40_saul402 | lev_m40ad | 16 | Bastila,Carth,Bastila |
| man26_ignus | manm26ae | 5 | Carth,Juhani,Bastila |
| man26_irimerc | manm26aa | 7 | Bastila,Mission,Jolee |
| man26_manmerc | manm26aa | 1 | Cand |
| man26_nilko | manm26aa | 10 | Jolee,Juhani,Bastila |
| man26_selambush | manm26ae | 8 | man26_cutsel01,man26_cutsel01,man26_cutsel01 |
| man26_selarrest | manm26ab | 9 | man26_selcut03,man26_selcut03,man26_selcut03 |
| man26_seljud1 | manm26aa | 7 | Jolee,Carth,Bastila |
| man26_seljud2 | manm26aa | 2 | Carth,Bastila |
| man26_seljud5 | manm26aa | 6 | Carth,Bastila,Carth |
| man26_selport | manm26ac | 8 | Bastila,Juhani,Jolee |
| man26_shaelas | manm26aa | 14 | Juhani,Carth,Mission |
| man26_sunry | manm26aa | 13 | Jolee,Jolee,Carth |
| man26_trial | manm26aa | 48 | man26_elora,Jolee,Jolee |
| man27_shasa | manm27aa | 13 | Carth,Carth,Bastila |
| man27_sithmas | manm27aa | 3 | Jolee,HK47,Jolee |
| man28_merc | manm28aa | 6 | Cand,Mission,HK47 |
| man28_sur2 | manm28ab | 5 | Cand,Jolee,Cand |
| man28_sur3 | manm28ac | 2 | Carth,Bastila |
| man_ithordead | manm26ad | 5 | Vekdroid,Vekdroid,Vekdroid |
| man_k_h_bandon | manm28aa | 5 | g_bandon,g_bandon,g_bandon |
| man_k_h_calo | manm28aa | 7 | CaloNord,CaloNord,CaloNord |
| man_lorgal | manm26ae | 7 | Lorgal,Lorgal,Lorgal |
| missdoor_dlg | tar_m05aa | 19 | Mission,Mission,Mission |
| tar02_alienpris | tar_m02ad | 1 | Carth |
| tar02_bountyh022 | tar_m02ac | 1 | Carth |
| tar02_bullmerc21 | tar_m02ac | 2 | Carth,Carth |
| tar02_dia022 | tar_m02aa | 1 | Carth |
| tar02_drunk021 | tar_m02ab | 2 | Carth,Carth |
| tar02_duelorg021 | tar_m02ae | 2 | Carth,Carth |
| tar02_gana021 | tar_m02ae | 1 | Carth |
| tar02_gorton21 | tar_m02ab | 9 | Mission,Bastila,Carth |
| tar02_gurney021 | tar_m02ac | 6 | Carth,Bastila,Carth |
| tar02_janice021 | tar_m02ab | 1 | Carth |
| tar02_janitor | tar_m02aa | 1 | Carth |
| tar02_kebla021 | tar_m02ac | 2 | Carth,Carth |
| tar02_larrim | tar_m02aa | 2 | Carth,Carth |
| tar02_niklos021 | tar_m02ae | 1 | Mission |
| tar02_sarna021 | tar_m02ad | 6 | Carth,Carth,Sarna021 |
| tar02_scaredm021 | tar_m02ad | 2 | Carth,Carth |
| tar02_sithguard | tar_m02ab | 1 | Carth |
| tar02_sithintero | tar_m02ad | 1 | Carth |
| tar02_yungenda21 | tar_m02ad | 5 | Carth,YunGenda021,YunGenda021 |
| tar02_zelka021 | tar_m02ac | 10 | Bastila,Carth,Bastila |
| tar03_brejik031 | tar_m03af | 11 | Brejik031,Brejik031,Brejik031 |
| tar03_holdan031 | tar_m03ae | 5 | Bastila,Carth,Mission |
| tar03_matrik031 | tar_m03ad | 2 | Carth,Bastila |
| tar03_mission031 | tar_m03ae | 3 | Carth,Carth,Carth |
| tar03_zax031 | tar_m03ae | 7 | Carth,Carth,Bastila |
| tar04_gendar041 | tar_m04aa | 1 | Carth |
| tar04_igear | tar_m04aa | 2 | Carth,Carth |
| tar04_outman041 | tar_m04aa | 2 | Carth,Carth |
| tar04_outwom044 | tar_m04aa | 1 | Carth |
| tar04_rukil | tar_m04aa | 6 | Carth,Mission,Carth |
| tar08_davik081 | tar_m08aa | 4 | Cand,Cand,Cand |
| tar08_davslav82 | tar_m08aa | 4 | Carth,Carth,Bastila |
| tar08_davslav84 | tar_m08aa | 2 | Carth,Mission |
| tar08_ramp | tar_m08aa | 1 | Cand |
| tar10_kandon01 | tar_m10ac | 11 | Carth,Mission,Mission |
| tar10_vulkmech04 | tar_m10ab | 1 | Carth |
| tar10_waitress | tar_m10aa | 2 | Carth,Carth |
| tar11_gadon112 | tar_m11aa | 5 | Carth,Zaalbar,Carth |
| tar11_hidbek111 | tar_m11aa | 4 | HiddenBekCompGuard,HiddenBekCompGuard,HiddenBekCompGuard |
| tar11_zaerdra111 | tar_m11aa | 3 | Carth,Mission,Mission |
| tat17_01cust_01 | tat_m17ab | 3 | Cand,Mission,Jolee |
| tat17_03gurke_01 | tat_m17ad | 9 | Mission,Bastila,HK47 |
| tat17_03shari_01 | tat_m17aa | 24 | Zaalbar,Mission,Carth |
| tat17_03tanis_01 | tat_m17ad | 9 | Jolee,Bastila,Bastila |
| tat17_04celis_01 | tat_m17ae | 20 | Carth,Bastila,Jolee |
| tat17_04garm_01 | tat_m17ae | 4 | Juhani,Bastila,Carth |
| tat17_04nico_01 | tat_m17ae | 8 | Cand,Carth,Mission |
| tat17_04yuka_01 | tat_m17ae | 4 | Carth,Juhani,Bastila |
| tat17_04zorii_01 | tat_m17ae | 2 | Jolee,Mission |
| tat17_05mecha_01 | tat_m17aa | 6 | Carth,Jolee,Bastila |
| tat17_07jawag_01 | tat_m17af | 10 | HK47,Carth,Bastila |
| tat17_07offic_01 | tat_m17af | 1 | Zaalbar |
| tat17_08hk47_01 | tat_m17ac | 4 | T3M4,Carth,T3M4 |
| tat17_08yuka_01 | tat_m17ac | 19 | HK47,HK47,HK47 |
| tat17_10czerk_01 | tat_m17ag | 4 | Carth,Juhani,Bastila |
| tat17_10greet_01 | tat_m17ag | 2 | Mission,Mission |
| tat17_11iziz_01 | tat_m17aa | 24 | Bastila,Carth,Bastila |
| tat18_10tanis_01 | tat_m18aa | 11 | T3M4,T3M4,HK47 |
| tat18_11komad_01 | tat_m18ac | 10 | HK47,Jolee,HK47 |
| tat18_starspeak | tat_m18ac | 22 | T3M4,T3M4,T3M4 |
| tat18_vorndroid2 | tat_m18ab | 1 | vornsdroid2 |
| tat20_09chief_01 | tat_m20aa | 102 | HK47,HK47,HK47 |
| tat20_09first_01 | tat_m20aa | 10 | HK47,HK47,HK47 |
| tat_k_h_bandon | tat_m18ac | 5 | tat_bandon,tat_bandon,tat_bandon |
| unk41_fight | unk_m41aa | 6 | unk41_blackrak4,unk41_redrak1,unk41_blackrak4 |
| unk44_evilbast | unk_m44ac | 22 | Jolee,Juhani,Juhani |
| unk44_exittrig | unk_m44ac | 4 | Jolee,Jolee,Bastila |

## Processes that crashed or timed out

None.
