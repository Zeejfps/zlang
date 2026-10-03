# GFF schemas: dialogue and journal (DLG, JRL)

Conventions, path notation and columns: [gff-schemas.md](gff-schemas.md). Meanings follow
BioWare's NWN "Conversation" and "Journal" documents where they apply; KOTOR additions
(cinematic cameras, VO, stunt models, fades, plot XP) are explained from the data and marked
*(inferred)* unless the cross-check probe (`gffxref.py`) confirmed them.

## DLG: conversation

### The graph

A DLG is a bipartite graph. `EntryList` holds NPC lines ("entries"), `ReplyList` holds player
lines ("replies"); struct id = list index in both. Links point across:

- `StartingList`: links to entries; the conversation starts at the first whose `Active` script
  returns TRUE (or that has no `Active` script).
- `EntryList/RepliesList`: links from an entry to replies. The player is offered every reply
  whose `Active` passes, in list order. No replies: the conversation ends after the entry.
- `ReplyList/EntriesList`: links from a reply to entries; the NPC says the first that passes.
  None: the conversation ends.

A link's `Index` is the target's position in the other list. `IsChild` = 1 marks a link that
reuses a node shown elsewhere (the toolset's grey "link"); the node and its subtree are the same
either way. In KOTOR the action script is on the node (`Script`), and the only condition is the
link's `Active` (a `StartingConditional` NCS returning an int).

A node's text is `Text` (strref; nodes with an empty text and no replies end the conversation;
an entry with empty text is a silent pass-through used to run scripts or branch). `Speaker` and
`Listener` are tags; empty speaker = the conversation owner, `PLAYER` = the PC, `OWNER` = owner.

### Speech, cameras and animation (KOTOR)

- **Voice.** An entry's VO is `streamwaves/.../<VO_ResRef>.wav`, found by name in the
  `streamwaves` tree: module VO lives in `streamwaves/<Mod_VO_ID>/...`, shared VO in
  `streamwaves/globe/<6-char set>/` (e.g. `nglobebant00102_` is
  `globe/bant00/NGLOBEBANT00102_.wav`). 14 k of 20 k entry VO names exist; replies (the PC) are
  never voiced in KOTOR, though their `VO_ResRef` is filled. `Sound` is an alternative non-VO WAV
  (resource or `streamsounds/`). Lip sync comes from `lips/*.mod` LIP files named like the VO.
- **Cameras.** `CameraAngle` selects the shot. Cross-checked against the data: 6 always comes
  with `CameraID` (a static camera from the GIT `CameraList`), 4 always with `CameraAnimation`
  and the DLG's `CameraModel` (an animated cutscene camera), 0 is the default framing. 1, 2, 3, 5
  are other built-in framings *(inferred: speaker close-up, over-the-shoulder, wide, unchanged)*.
- **Animated cutscenes** (`CameraModel` set; 24 DLGs). The camera model's animations are named
  `CUT001W`, `CUT002W`, ... and `CameraAnimation` N plays `CUT<N-1199>W` (1200 -> `CUT001W`).
  `StuntList` replaces each participant's model by a stunt model for the scene; stunt models
  carry the same `CUTnnnW` animations, played by `AnimList` entries with the same numbering.
- **AnimList/Animation** encodes three ranges: 10000 + N plays row N of `dialoganimations.2da`
  (e.g. 10042 = Talk_Sad; 30 of the 32 values used hit named rows), 1200 + N plays cutscene
  animation `CUT<N+1:03>W` on the participant's model, and small values (35, 40, 41, 44, 70) are
  NWN-style animation constants that equal `dialoganimations.2da` rows directly *(inferred)*.
- **Fades.** `FadeType` 3 fade in, 4 fade out (with `FadeLength`, `FadeDelay`, `FadeColor`
  present exactly when the type is 3 or 4); 1 occurs 17 times without parameters *(unknown)*.
- **Waiting.** `WaitFlags` bit 0 occurs only with `CameraAngle` 4: hold the node until the camera
  animation ends; 9 = bits 0 and 3 *(inferred: also wait for the participants' animations)*.
- **Delay** is seconds before the node advances; 0xFFFFFFFF (23 010 of 24 234 entries) = default
  (until the VO or a text-length timer ends) *(inferred)*.

<!-- gff-table DLG -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `DelayEntry` | DWORD | all | 0 | Seconds to wait before each entry; always 0. |
| `DelayReply` | DWORD | all | 0 | Seconds to wait before each reply; always 0. |
| `NumWords` | DWORD | all | 0..12285 | Word count (toolset statistics only). |
| `EndConversation` | ResRef | all | 1044 empty; e.g. `k_pman_ambient06`, `k_pman_ambient04`, `k_pman_ww` | Script run when the conversation ends normally. |
| `EndConverAbort` | ResRef | all | 1055 empty; e.g. `k_pman_ambient06`, `k_pman_ambient04`, `k_pman_ww` | Script run when it is aborted (combat, Esc, ...). |
| `Skippable` | BYTE | all | 0, 1 | 1 if the player may skip lines. |
| `StuntList` | List | all | 0..15 entries; struct id 0 | Model substitutions for an animated cutscene. |
| `StuntList/Participant` | CExoString | 24 | e.g. `PLAYER`, `Carth`, `Yoda` | Tag of the participant (`PLAYER` for the PC). |
| `StuntList/StuntModel` | ResRef | 24 | 1 empty; e.g. `c_holovandar`, `m12aa_c01_char01`, `m40ad_c01_char01` | Model used for that participant during the scene. |
| `CameraModel` | ResRef | all | 1121 empty; e.g. `m12aa_c02_cam`, `m02af_c10_cam`, `m12aa_c01_cam` | Animated camera model for a cutscene conversation. |
| `VO_ID` | CExoString | 1144 | 254 empty; e.g. `c01001`, `c03001`, `c02001` | Voice-over session id from BioWare's pipeline *(inferred; not needed to find files)*. |
| `ConversationType` | INT | 983 | 0, 1, 2 | 0 normal cinematic, 1 computer terminal; 2 occurs in party-member and some plot DLGs *(meaning unknown)*. |
| `ComputerType` | BYTE | 794 | 0, 1 | For computer conversations: 0 modern, 1 ancient (Rakatan) skin *(inferred; 1 only on Dantooine ruins and Star Forge terminals)*. |
| `OldHitCheck` | BYTE | 770 | 0, 1 | *(Unknown; presumably an older line-of-sight check for starting the conversation.)* |
| `AmbientTrack` | ResRef | 959 | 942 empty; e.g. `03a`, `06`, `07` | Music played during the conversation: a file in `streammusic/` (all 17 exist). |
| `UnequipItems` | BYTE | 959 | 0, 1 | 1 to hide participants' equipped items during the conversation *(inferred)*. |
| `AnimatedCut` | BYTE | 849 | 0, 1 | 1 if the conversation is an animated cutscene *(inferred)*. |
| `UnequipHItem` | BYTE | 829 | 0, 1 | 1 to hide held (weapon) items *(inferred)*. |
| `EntryList` | List | all | 1..540 entries; struct id = index | NPC lines; struct id = index. |
| `EntryList/Speaker` | CExoString | all | 18770 empty; e.g. `Bastila`, `Carth`, `Cand` | Tag of the speaker; empty = owner. |
| `EntryList/AnimList` | List | all | 0..15 entries; struct id 0 | Animations to play on participants during this line. |
| `EntryList/AnimList/Participant` | CExoString | 342 | e.g. `OWNER`, `PLAYER`, `Bastila` | Tag of the animated participant (`OWNER`, `PLAYER`, or a tag). |
| `EntryList/AnimList/Animation` | WORD | 342 | 35..10164 | Animation number (see above). |
| `EntryList/Text` | CExoLocString | all | strref in 22707; 1527 empty | Line text (strref). |
| `EntryList/VO_ResRef` | ResRef | 1144 | 3875 empty; e.g. `nglobebant00102_`, `nglobebant00103_`, `nglobebant00104_` | Voice-over WAV under `streamwaves/` (and its LIP). |
| `EntryList/Script` | ResRef | all | 20174 empty; e.g. `k_swg_bastila27x`, `k_hbanter11x`, `k_hbanter10x` | Script run when the line is shown. |
| `EntryList/Delay` | DWORD | all | 0..4294967295 (15 values) | Seconds before advancing; 0xFFFFFFFF = default. |
| `EntryList/Comment` | CExoString | all | 21810 empty; e.g. `// unknown world  `, `// korriban  `, `// tatooine  ` | Writer's comment. |
| `EntryList/Sound` | ResRef | all | 17356 empty; e.g. `n_gwwook_comm1`, `n_gwwook_angm`, `n_gftwilek_coml1` | Non-VO sound to play with the line. |
| `EntryList/Quest` | CExoString | all | 23605 empty; e.g. `dan_murder`, `dan_trials`, `k_swg_juhani` | Journal category tag to update. |
| `EntryList/PlotIndex` | INT | 1144 | -1..55 (27 values) | Row in `plot.2da` whose XP is awarded; -1 none. |
| `EntryList/PlotXPPercentage` | FLOAT | 1144 | 0..5 (13 values) | Fraction of that plot XP to award. |
| `EntryList/Listener` | CExoString | all | 21506 empty; e.g. `PLAYER`, `Bastila`, `Carth` | Tag of the listener (who the speaker faces). |
| `EntryList/WaitFlags` | DWORD | all | 0, 1, 9 | Wait bits (see above). |
| `EntryList/CameraAngle` | DWORD | all | 0..6 (7 values) | Camera shot (see above). |
| `EntryList/FadeType` | BYTE | all | 0, 1, 3, 4 | 0 none, 3 fade in, 4 fade out. |
| `EntryList/RepliesList` | List | all | 0..22 entries; struct id = index | Links to player replies. |
| `EntryList/RepliesList/Index` | DWORD | 1042 | 0..731 | Index in `ReplyList`. |
| `EntryList/RepliesList/Active` | ResRef | 1042 | 35000 empty; e.g. `k_con_comver42`, `k_con_comver43`, `k_con_comver44` | Condition script (`StartingConditional`); empty = always. |
| `EntryList/RepliesList/IsChild` | BYTE | 1042 | 0, 1 | 1 if this is a link to a node shown elsewhere. |
| `EntryList/RepliesList/LinkComment` | CExoString | 480 | 11967 empty; e.g. `default is 8`, `default is 3`, `default is 5` | Writer's comment on the link. |
| `EntryList/SoundExists` | BYTE | 989 | 0, 1, 2, 3 | Non-zero when the line has VO or a sound (values 1..3) *(inferred)*. |
| `EntryList/CamHeightOffset` | FLOAT | 257 | -1, -0.5, 0, 0.8, 1 | Camera height offset for the shot *(inferred)*. |
| `EntryList/TarHeightOffset` | FLOAT | 257 | -0.15, 0, 1 | Height offset of the camera target *(inferred)*. |
| `EntryList/CameraID` | INT | 374 | 1..778 | Static camera id in the GIT `CameraList` (with `CameraAngle` 6). |
| `EntryList/CamVidEffect` | INT | 323 | -1, 0 | Row in `videoeffects.2da` applied to the shot; -1 none. |
| `EntryList/FadeLength` | FLOAT | 180 | 0..6 (20 values) | Fade duration (s). |
| `EntryList/FadeDelay` | FLOAT | 180 | 0..9 (31 values) | Delay before the fade (s). |
| `EntryList/FadeColor` | Vector | 180 | ('0', '0', '0'); ('0.9961', '0.9961', '0.9961') | Fade colour (RGB 0..1). |
| `EntryList/QuestEntry` | DWORD | 235 | 1..150 | Journal entry id to set in category `Quest`. |
| `EntryList/CamFieldOfView` | FLOAT | 25 | -1..70.881 | Camera field of view (degrees); -1 default. |
| `EntryList/CameraAnimation` | WORD | 25 | 1200..10098 (35 values) | Camera animation number (with `CameraAngle` 4; see above). |
| `ReplyList` | List | all | 0..732 entries; struct id = index | Player lines; struct id = index. |
| `ReplyList/AnimList` | List | 1042 | 0..3 entries; struct id 0 | Animations during this line. |
| `ReplyList/AnimList/Participant` | CExoString | 82 | e.g. `PLAYER`, `OWNER`, `SaulKarath402` | Tag of the animated participant. |
| `ReplyList/AnimList/Animation` | WORD | 82 | 70..10164 (23 values) | Animation number (see above). |
| `ReplyList/Text` | CExoLocString | 1042 | strref in 11286; 16080 empty | Line text (strref); empty = "[Continue]" or silent. |
| `ReplyList/VO_ResRef` | ResRef | 1041 | 7808 empty; e.g. `_globebant00112_`, `_globebant00111_`, `_globebant00106_` | Filled in but never voiced (no files). |
| `ReplyList/Script` | ResRef | 1042 | 24902 empty; e.g. `k_swg_bastila20`, `k_swg_bastila99`, `k_swg_bastila20x` | Script run when the reply is chosen. |
| `ReplyList/Delay` | DWORD | 1042 | 0, 1, 2, 5, 6, 4294967295 | Seconds before advancing; 0xFFFFFFFF = default. |
| `ReplyList/Comment` | CExoString | 1042 | 26358 empty; e.g. `romance over`, `default is 8`, `available after t…` | Writer's comment. |
| `ReplyList/Sound` | ResRef | 1042 | 27365 empty; e.g. `nm28acsur303017_` | Sound to play with the reply. |
| `ReplyList/Quest` | CExoString | 1042 | 27156 empty; e.g. `k_swg_bastilatalk`, `k_swg_carthtalk`, `lev_captured` | Journal category tag to update. |
| `ReplyList/PlotIndex` | INT | 803 | -1, 48, 54 | Row in `plot.2da` for XP. |
| `ReplyList/PlotXPPercentage` | FLOAT | 803 | 0..1.4 (7 values) | Fraction of that plot XP. |
| `ReplyList/Listener` | CExoString | 1042 | 27077 empty; e.g. `HK47`, `Bastila`, `Juhani` | Tag of the listener. |
| `ReplyList/WaitFlags` | DWORD | 1042 | 0, 1, 8 | Wait bits. |
| `ReplyList/CameraAngle` | DWORD | 1042 | 0..6 (7 values) | Camera shot. |
| `ReplyList/FadeType` | BYTE | 1042 | 0, 1, 3, 4 | 0 none, 3 fade in, 4 fade out. |
| `ReplyList/EntriesList` | List | 1042 | 0..19 entries; struct id = index | Links to NPC entries. |
| `ReplyList/EntriesList/Index` | DWORD | 821 | 0..539 | Index in `EntryList`. |
| `ReplyList/EntriesList/Active` | ResRef | 821 | 23670 empty; e.g. `k_con_dark`, `k_con_ismale`, `k_con_light` | Condition script; the first entry that passes is spoken. |
| `ReplyList/EntriesList/IsChild` | BYTE | 821 | 0, 1 | 1 if a link to a node shown elsewhere. |
| `ReplyList/EntriesList/LinkComment` | CExoString | 553 | 6738 empty; e.g. `Zaalbar is not wi…`, `Zaalbar is with t…`, `If patrol mode is…` | Writer's comment on the link. |
| `ReplyList/SoundExists` | BYTE | 730 | 0, 1 | 0/1 sound flag *(inferred)*. |
| `ReplyList/CamHeightOffset` | FLOAT | 50 | 0, 2 | Camera height offset *(inferred)*. |
| `ReplyList/TarHeightOffset` | FLOAT | 50 | 0 | Target height offset *(inferred)*. |
| `ReplyList/QuestEntry` | DWORD | 67 | 1..140 (30 values) | Journal entry id. |
| `ReplyList/FadeDelay` | FLOAT | 32 | 0 | Delay before the fade. |
| `ReplyList/FadeColor` | Vector | 32 | ('0', '0', '0') | Fade colour. |
| `ReplyList/CamFieldOfView` | FLOAT | 1 | -1 | Field of view; -1 default. |
| `ReplyList/CameraAnimation` | WORD | 1 | 10098 | Camera animation number. |
| `ReplyList/CameraID` | INT | 55 | 1..778 (24 values) | Static camera id. |
| `ReplyList/CamVidEffect` | INT | 48 | -1 | Row in `videoeffects.2da`; -1 none. |
| `ReplyList/FadeLength` | FLOAT | 6 | 0, 3, 12 | Fade duration. |
| `StartingList` | List | all | 1..28 entries; struct id = index | Candidate first entries, in priority order. |
| `StartingList/Index` | DWORD | all | 0..538 | Index in `EntryList`. |
| `StartingList/Active` | ResRef | all | 1118 empty; e.g. `k_act_foeinsight`, `k_con_npctalk`, `k_con_tokens` | Condition script; empty = always. |
<!-- /gff-table -->

The cross-check found condition and action scripts present as NCS for all but 38 of ~19 000
references (dead names such as `k_pdan_taree01`, and a few links whose `Active` is the string
`0`): a missing script must count as "no script" (a missing condition as TRUE is the safe
reading, but this is unverified against the engine).

## JRL: journal

The game's quest journal is `global.jrl` (in `_newbif.bif`). Three Taris modules also carry an
older, unused `module.jrl` (NWN layout: `XP`, `Picture`, no plot index). Scripts and DLG nodes
refer to a category by `Tag` and to an entry by `ID` (`AddJournalQuestEntry`, DLG
`Quest`/`QuestEntry`); the save keeps the current state per category (gff-save.md, `JNL_Entries`).

<!-- gff-table JRL -->
| Field | Type | Files | Values | Meaning |
|---|---|---|---|---|
| `Categories` | List | all | 0..101 entries; struct id = index | Quests; struct id = index. |
| `Categories/Name` | CExoLocString | 3 | strref in 103 | Quest title (strref). |
| `Categories/Priority` | DWORD | 3 | 0, 1, 2, 3, 4 | Sort priority 0 highest .. 4 lowest. |
| `Categories/Comment` | CExoString | 3 | 81 empty; e.g. `Dragon hunt with …`, `Plot around Rorwo…`, `the main Kashyyyk…` | Writer's comment. |
| `Categories/Tag` | CExoString | 3 | e.g. `tat18ac_dragonhunt`, `kor25_doubtsith`, `k_starforge` | Tag scripts use for the quest. |
| `Categories/PlotIndex` | INT | 1 | -1..74 (37 values) | Row in `plot.2da` (quest XP); -1 none. |
| `Categories/PlanetID` | INT | 1 | -1..10 (12 values) | Row in `planetary.2da`: the planet the quest is filed under; -1 none. |
| `Categories/EntryList` | List | 3 | 1..24 entries; struct id = index | Quest states; struct id = index. |
| `Categories/EntryList/ID` | DWORD | 3 | 1..150 | State id (unique within the quest, not contiguous). |
| `Categories/EntryList/End` | WORD | 3 | 0, 1 | 1 if this state completes the quest. |
| `Categories/EntryList/Text` | CExoLocString | 3 | strref in 649 | Journal text for the state (strref). |
| `Categories/EntryList/XP_Percentage` | FLOAT | 1 | 0..1.2 (19 values) | Fraction of the plot XP awarded on reaching the state *(inferred)*. |
| `Categories/XP` | DWORD | 2 | 0 | NWN completion XP; only in the old `module.jrl` (0). |
| `Categories/Picture` | WORD | 2 | 65535 | Unused; 0xFFFF. |
<!-- /gff-table -->
