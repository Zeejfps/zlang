#!/bin/sh
# The scripts, conversation and flags of placeable (or door, creature, trigger) templates: sh kotor/tools/playthrough/korriban/utpinfo.sh MODULE KIND TEMPLATE...
# (KIND: utp, utd, utc, utt; the template's resref is usually its tag)
module=$1
kind=$2
shift 2
for t in "$@"; do
  echo "== $t: $(kotor/out/gffdump.exe --module $module $t.$kind 2>/dev/null | grep -i 'OnUsed\|OnHeart\|OnEnter\|Conversation\|OnOpen\|OnClose\|OnInvDist\|OnDeath\|OnMeleeAtt\|OnSpellCast\|OnDamaged\|OnUnlock\|OnLock\|OnFailToOpen\|OnTrapTriggered\|Script\|Locked\|Plot\|Useable\|HasInventory' | grep -v '""' | sed 's/CResRef = //; s/BYTE = //' | tr -s ' ' | tr '\n' ';' | cut -c1-400)"
done
