#!/bin/sh
# The world's emitters run (docs/design/vfx.md, "World emitters"): a fresh Endar Spire, the camera on the south dead
# end of the corridor outside the starting room (room m01aa_03a's smoke044, 40 particles a second for 6 s, run 10 s
# ahead when first seen), then the same with the Emitters option off. Reads the screenshot log's
# `world emitters: N drawn, M particles` line; no checkpoint needed.
#
#   sh kotor/tools/gfx/world_emitters.sh [EXE]       (from the repository root; EXE defaults to kotor/out/kotor.exe)
#
# PASS: with the option on, the smoke is drawn with at least 100 particles; with it off, no world emitter is drawn.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${1:-kotor/out/kotor.exe}
out=kotor/out/gfx/world_emitters
mkdir -p $out/saves
printf '70 cam at 46.4,14,1.6 46.4,6.9,1.2\n' > $out/on.txt
printf '70 cam at 46.4,14,1.6 46.4,6.9,1.2\n80 gfx emitters 0\n' > $out/off.txt
fail=0
for run in on off; do
  $exe --module end_m01aa --no-render --mute --saves $out/saves --input $out/$run.txt --frames 92 \
    --screenshot-at 90:$out/$run.png > $out/$run.log 2>&1
  line=$(grep "world emitters:" $out/$run.log | tail -1)
  drawn=$(echo "$line" | sed -n 's/.*world emitters: \([0-9]*\) drawn, \([0-9]*\) particles.*/\1/p')
  parts=$(echo "$line" | sed -n 's/.*world emitters: \([0-9]*\) drawn, \([0-9]*\) particles.*/\2/p')
  if [ -z "$drawn" ]; then echo "FAIL $run: no 'world emitters' line in $out/$run.log"; fail=1; continue; fi
  if [ $run = on ] && { [ "$drawn" -lt 1 ] || [ "$parts" -lt 100 ]; }; then echo "FAIL on: $drawn drawn, $parts particles"; fail=1; continue; fi
  if [ $run = off ] && [ "$drawn" -ne 0 ]; then echo "FAIL off: $drawn drawn"; fail=1; continue; fi
  echo "ok $run: $drawn drawn, $parts particles ($out/$run.png)"
done
[ $fail = 0 ] && echo PASS
exit $fail
