#!/bin/sh
# The FactionID of creature blueprints of a Tatooine module: sh factions.sh MODULE BLUEPRINT...  (run from the repository root)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
m=$1
shift
for n in "$@"; do
  echo "$n: $(kotor/out/gffdump.exe --module $m $n.utc 2>&1 | grep -i 'FactionID' | head -1)"
done
