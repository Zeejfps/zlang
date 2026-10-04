#!/bin/sh
# Which resources of a module name a script in one of their fields (an event slot, a conversation node):
#
#   sh kotor/tools/playthrough/kashyyyk/whoscript.sh MODULE SCRIPT
#
# Walks the module's UTC, UTP, UTD, UTT, UTE, UTS, UTW and DLG files with gffdump (build kotor/tools/gffdump to
# kotor/out/gffdump.exe, and resls). The scripts of an NCS are found with `grep -l` over kotor/out/ncs instead (ncsgrep.sh).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
script=$2
for kind in utc utp utd utt ute dlg are; do
  for n in $(kotor/out/resls.exe --module "$module" --type $kind | cut -f1 | cut -d. -f1 | sort -u); do
    if kotor/out/gffdump.exe --module "$module" "$n.$kind" 2>/dev/null | grep -qi "\"$script\""; then echo "$n.$kind"; fi
  done
done
