#!/bin/sh
# Creatures keep out of each other's way (docs/re/movement.md 4.9, lib/engine/crowd.ctx). From the `uppercity` checkpoint:
#
#   block1  the leader runs by the keys into a neutral Sith trooper that may not be pushed aside and on past it, while
#           Carth, following, meets another in his way: PASS when no two creatures' circles overlap at any check (every
#           3 frames), the leader ends up past the first trooper (he slid round it) and Carth walked round the second
#           (a `crowd: CARTH walks round TROOPER` detour);
#   pair1   two hostile Sith troopers come for the leader and Carth: PASS when no circles overlap and both troopers
#           attacked (the attackers stand apart, each at its target's circle, none on the other's spot).
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/crowd/check.sh        (from the repository root; a few seconds)
#
# Exit 1 and a FAIL line per failed case; the logs are kotor/out/crowd/NAME.log. `ui gaps` prints the closest pair of
# creatures within 12 m of the leader (their distance less both CREPERSPACEs) and an `overlap` line for each pair under
# -0.02 m.
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/crowd
mkdir -p $out
fail=0

run() {
  name=$1
  frames=$2
  { grep -v '^#' kotor/tools/crowd/$name.txt; i=10; while [ $i -le $frames ]; do echo "$i ui gaps"; i=$((i + 3)); done; } | sort -s -n -k1,1 > $out/$name.in
  $exe --load kotor/out/checkpoints/uppercity --no-render --frames $((frames + 2)) --input $out/$name.in --log actions,combat \
    --saves $out/saves_$name > $out/$name.log 2>&1
}

closest_of() { grep -a '^gaps' $out/$1.log | awk '{ print $4 }' | sort -g | head -1; }

run block1 260
overlaps=$(grep -a -c '^  overlap' $out/block1.log)
first=$(grep -a '^spawn g_sithtroop01' $out/block1.log | awk '{ print $3 }')
second=$(grep -a '^spawn g_sithtroop02' $out/block1.log | awk '{ print $3 }')
carth=$(grep -a '^where [0-9]* k2 carth ' $out/block1.log | awk '{ print $2 }' | head -1)
detours=$(grep -a -c -E "crowd: $carth walks round ($first|$second) " $out/block1.log)
# How far along his first facing the leader got, against the first trooper's place (from the first `pos` line).
past=$(awk -v t="$first" '
  /^pos / { n++; if (n == 1) { sx = $2; sy = $3; fx = $(NF - 1); fy = $NF } else { ex = $2; ey = $3 } }
  /^spawn g_sithtroop01 / { tx = $7; ty = $8 }
  END { a = (ex - sx) * fx + (ey - sy) * fy; b = (tx - sx) * fx + (ty - sy) * fy; ok = (a > b + 0.5) ? 1 : 0; printf "%d %.2f %.2f", ok, a, b }' $out/block1.log)
if [ "$overlaps" -eq 0 ] && [ "$detours" -gt 0 ] && [ "${past%% *}" -eq 1 ]; then
  echo "ok   block1: no overlap (closest $(closest_of block1) m), leader past the trooper (${past#* } m along), Carth walked round a trooper ($detours detour(s))"
else
  echo "FAIL block1: $overlaps overlap(s) (closest $(closest_of block1) m), leader along/trooper ${past#* }, $detours detour(s) by Carth ($carth) round a trooper"
  fail=1
fi

run pair1 400
overlaps=$(grep -a -c '^  overlap' $out/pair1.log)
attackers=0
for id in $(grep -a '^spawn g_sithtroop0' $out/pair1.log | awk '{ print $3 }'); do
  if grep -a -q "action 12 on $id: " $out/pair1.log && grep -a -q "attack [0-9]*: .*$id\| $id attacks\|attacker $id" $out/pair1.log; then attackers=$((attackers + 1)); fi
done
if [ "$overlaps" -eq 0 ] && [ "$attackers" -eq 2 ]; then
  echo "ok   pair1: no overlap (closest $(closest_of pair1) m), both troopers attacked"
else
  echo "FAIL pair1: $overlaps overlap(s) (closest $(closest_of pair1) m), $attackers of 2 troopers attacked"
  fail=1
fi
exit $fail
