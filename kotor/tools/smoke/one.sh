#!/bin/sh
# One module of the smoke test: runs the game headless straight into the module and keeps the log.
#
#   sh kotor/tools/smoke/one.sh MODULE          (run from the repository root; run.sh calls it)
#
# Writes $OUT/MODULE.log (the run) and $OUT/MODULE.probe (the same run 10 s of world time longer, only
# for its `stuck` lines), and $OUT/MODULE.meta (the exit code and wall time). Environment: OUT (default
# kotor/out/smoke), FRAMES (ticks of 1/30 s, default 18000 = 600 s of world time), EXE, TIMEOUT (seconds).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
m=$1
out=${OUT:-kotor/out/smoke}
frames=${FRAMES:-18000}
exe=${EXE:-kotor/out/kotor.exe}
limit=${TIMEOUT:-180}
here=$(dirname "$0")
mkdir -p "$out" "$out/saves/$m"
start=$(date +%s)
# A hidden window, no drawing, 8 ticks per loop pass, music and effects not mixed; the default party is
# the player with Carth and Bastila, and the test bot (god mode) tours the area (waypoints, doors,
# placeables, triggers, talkers) and fights what is hostile in sight.
# Each run keeps its own saves directory: the game-in-progress file lives there.
timeout $limit "$exe" --module "$m" --no-render --speed 8 --mute --frames $frames --input "$here/input.txt" \
  --saves "$out/saves/$m" --report routines --log none > "$out/$m.log" 2>&1
rc=$?
end=$(date +%s)
echo "$rc $((end - start))" > "$out/$m.meta"
if [ $rc -eq 0 ]; then
  timeout $limit "$exe" --module "$m" --no-render --speed 8 --mute --frames $((frames + 300)) --input "$here/input.txt" \
    --saves "$out/saves/$m" --report routines --log none 2>&1 | grep -a '^stuck ' > "$out/$m.probe"
fi
rm -rf "$out/saves/$m"
