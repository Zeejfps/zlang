#!/bin/sh
# Is a target that died kept 1.5 s in combat mode? From `uppercity` (kotor/tools/checkpoints/make.sh), with keep1.txt:
# two Sith troopers, the near one wounded; the leader attacks it and Carth kills it while the other is still about.
# The original (UpdateSelectableObjects 0x005fa5a0, client +0x378) keeps the dead target as the HUD target for 1.5 s
# while a hostile creature is in the selectable list and the leader is in combat mode, and the leader's combat mode is
# held while that runs (0x005f3ad0). FAIL and exit status 1 unless the target leaves the corpse 1.3 to 2.2 s after the
# death (the corpse must first leave the list: the death animation) and the leader's combat mode does not end before,
# or unless the kept corpse's target block offers nothing (`ui fight` at tick 190, its last fight line: the name and
# the bar only; ours drops the hostile actions the original still lists then, docs/re/gui.md "What the target block
# offers"). For pictures: --screenshot-at 163 (alive, Attack) and 170 (dead, name and bar), without --speed.
#
#   sh kotor/tools/combat/keep.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 4 seconds)
#
# The log is kotor/out/combat/keep1.log. docs/re/movement.md 7.1, docs/mechanics/combat.md row 44.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out/saves_keep1
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_keep1 --input kotor/tools/combat/keep1.txt --frames 400 --log combat,objects > $out/keep1.log 2>&1
log=$out/keep1.log
fail=0
died=$(grep -a -E '^\[[0-9]+ [0-9.]+\] [0-9]+ \(g_sithtroop01\) dies' $log | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
left=$(grep -a -E '^\[[0-9]+ [0-9.]+\] target: g_sithtroop01 -> ' $log | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
off=$(grep -a -E '^\[[0-9]+ [0-9.]+\] combat mode off: 2147483647' $log | head -1 | sed -E 's/^\[([0-9]+) .*/\1/')
if [ -z "$died" ] || [ -z "$left" ]; then
  echo "FAIL the trooper did not die or the target never left it (see $log)"; fail=1
else
  gap=$((left - died))
  if [ $gap -lt 39 ] || [ $gap -gt 66 ]; then echo "FAIL the dead target was kept $gap ticks (want 39-66: 1.5 s after it leaves the list)"; fail=1; fi
  if [ -n "$off" ] && [ "$off" -lt "$left" ]; then echo "FAIL the leader left combat mode at tick $off, before the keep ended at $left"; fail=1; fi
fi
kept=$(grep -a '^fight leader' $log | tail -1)
case "$kept" in
  *" target 633 "*"block [] [] []") ;;
  *) echo "FAIL the kept corpse's block is not empty: ${kept##* block }"; fail=1 ;;
esac
if [ $fail = 0 ]; then echo "ok   keep: died at tick $died, kept as the target until $left with an empty block, combat mode until ${off:-the end}"; fi
exit $fail
