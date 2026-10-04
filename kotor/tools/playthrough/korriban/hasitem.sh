#!/bin/sh
# Which templates of a module hold an item (in their inventory or equipment) or name a script / string: sh hasitem.sh MODULE WORD [utc|utp|utd|utt|utm|dlg]
# (kotor/out/resls.exe and gffdump.exe built; run from the repository root)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
word=$2
kind=${3:-utc}
for n in $(kotor/out/resls.exe --module "$module" --type "$kind" | cut -d. -f1 | cut -d' ' -f1 | cut -f1); do
  if kotor/out/gffdump.exe --module "$module" "$n.$kind" 2>/dev/null | grep -q -i "$word"; then echo "$n"; fi
done
