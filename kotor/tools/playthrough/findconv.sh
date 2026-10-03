#!/bin/sh
# Which templates of a module name conversation CONV: sh kotor/tools/playthrough/findconv.sh MODULE CONV [utp|utc|utd]
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
conv=$2
kind=${3:-utp}
for n in $(kotor/out/resls.exe --module "$module" --type "$kind" | cut -d. -f1 | cut -d' ' -f1 | cut -f1); do
  if kotor/out/gffdump.exe --module "$module" "$n.$kind" 2>/dev/null | grep -q "Conversation: CResRef = \"$conv\""; then echo "$n"; fi
done
