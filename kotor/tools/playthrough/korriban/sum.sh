#!/bin/sh
# The story lines of a Korriban run's log (LOG=dialog,routines), without the facing and walking spam:
#
#   sh kotor/tools/playthrough/korriban/sum.sh kotor/out/pt/NAME.log [FIRST_FRAME] [EXTRA_REGEX]
#
# Conversations (start, the replies the player took, the lines said, end), the journal, globals, XP, alignment, party and
# module changes, items, doors, combat, deaths. WIDTH (default 170) cuts the lines.
log=$1
first=${2:-0}
extra=${3:-NOTHING_MATCHES_THIS}
grep -a -E "^\[[0-9]+ [0-9.]+\] (dialog (start|end|entry [0-9]+ speaker|reply [0-9]+ \"[^\"]+\" \(chosen|replies [0-9]+:)|combat|routine (SetGlobal(Number|Boolean|String)|AddJournal|RemoveJournal|GiveXP|StartNewModule|ActionStartConversation|AddAvailableNPC|AddPartyMember|RemovePartyMember|SetPartyLeader|ActionJumpToObject|PlayMovie|CreateObject|CreateItemOnObject|DestroyObject|SetLocked|ActionOpenDoor|ActionUnlock|ActionGiveItem|ActionTakeItem|ActionPickUp|ChangeToStandardFaction|AdjustAlignment|SetXP|ShowLevelUpGUI|AdjustReputation|SurrenderToEnemies|SetAreaUnescapable|SetPlotFlag|SetImmortal|SetCommandable|AddMultiClass|DoSinglePlayerAutoSave|StartCreditSequence|ActionAttack|ActionCastSpell|SetPlayerRestrict)|kotor:|module |fault|journal|xp|alignment)|$extra" "$log" | awk -v f="$first" 'substr($1,1,1) == "[" { split($1, a, "["); if (a[2] + 0 < f) next } { print }' | cut -c1-${WIDTH:-170}
