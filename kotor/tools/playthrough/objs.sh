#!/bin/sh
# The objects of a module, by kind and tag (count, first place): creatures (k2), doors (k6), triggers (k4), placeables (k5):
#   sh kotor/tools/playthrough/objs.sh MODULE [CHECKPOINT_DIR]        (run from the repository root; MODULE alone starts it fresh)
# With a checkpoint directory the game is loaded from it instead (the module is then the checkpoint's). Needs kotor/out/kotor_lev.exe.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
module=$1
mkdir -p kotor/out/pt
echo "5 ui where" > kotor/out/pt/objs_in.txt
if [ -n "$2" ]; then
  kotor/out/kotor_lev.exe --no-render --speed 8 --frames 20 --input kotor/out/pt/objs_in.txt --load "$2" --saves kotor/out/pt/saves_objs --log dialog > kotor/out/pt/objs.log 2>&1
else
  kotor/out/kotor_lev.exe --no-render --speed 8 --frames 20 --input kotor/out/pt/objs_in.txt --module "$module" --saves kotor/out/pt/saves_objs --log dialog > kotor/out/pt/objs.log 2>&1
fi
grep -a "^where" kotor/out/pt/objs.log | awk '$3=="k2"||$3=="k6"||$3=="k4"||$3=="k5" {printf "%s %s %s %.0f,%.0f\n", $3, $2, $4, $6, $7}' | awk '{c[$1" "$3]++; if (!($1" "$3 in p)) p[$1" "$3]=$4} END {for (k in c) print k, c[k], p[k]}' | sort
