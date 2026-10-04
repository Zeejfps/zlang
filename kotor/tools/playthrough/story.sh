#!/bin/sh
# The story-relevant lines of a run's log (run it with LOG=dialog,combat,routines,...):
# conversations, replies, combat, and the routines that change the game (globals, journal, XP,
# modules, party, objects, doors, items, movies, fades).
#
#   sh kotor/tools/playthrough/story.sh kotor/out/pt/NAME.log [FIRST_FRAME]
log=$1
first=${2:-0}
grep -E "^\[[0-9]+ [0-9.]+\] (dialog (start|entry [0-9]|reply|replies|end|condition|  )|combat|routine (SetGlobal(Number|Boolean|String)|AddJournal|RemoveJournal|GiveXP|StartNewModule|ActionStartConversation|AddAvailableNPC|AddPartyMember|RemovePartyMember|SetPartyLeader|ActionJump|PlayMovie|CreateObject|DestroyObject|SetLocked|ActionOpenDoor|ActionUseObject|SetPlayerRestrict|ActionEquip|ActionPickUp|ActionTakeItem|ChangeToStandard|SetCommandable|SetAreaUnescapable|SurrenderToEnemies|ActionUnlock|ActionLock|AddMultiClass|PlayRumble|ShowLevelUpGUI|AdjustReputation|ActionGiveItem|CreateItemOnObject|SetXP|ActionBarkString|NoClicksFor|BarkString|StartCreditSequence|SetGlobalFade|FadeFromBlack|FadeToBlack|CutsceneMov|ActionMoveAwayFrom|SetFacing|ActionForceMove|SetPlotFlag|SetImmortal|SetMinOneHP|DoSinglePlayerAutoSave))|kotor:|module |^dialog   \[" "$log" | awk -v f="$first" 'substr($1,1,1) == "[" { split($1, a, "["); if (a[2] + 0 < f) next } { print }' | cut -c1-${WIDTH:-200}
