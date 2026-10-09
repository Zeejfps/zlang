#!/bin/sh
# The tutorial pop-ups (docs/re/gui.md "Tutorial pop-ups"), from the uppercity checkpoint
# (kotor/tools/checkpoints/make.sh) with tutorials.txt: the pause's, the hostile sighting's, the attack's two pages and the order
# its close gives, the second attack's within 3 s, and none again after a save and its load. Pictures of
# the pause's box and the attack's first page in kotor/out/tut/. FAIL (exit 1) when the log differs.
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/ingame/tutorials.sh      (from the repository root; about 20 s)
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
ck=kotor/out/checkpoints
out=kotor/out/tut
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out/saves
$exe --load $ck/uppercity --headless --saves $out/saves --input kotor/tools/ingame/scripts/tutorials.txt --frames 112 --log objects \
  --screenshot-at 14:$out/pause.png --screenshot-at 44:$out/attack1.png --screenshot-at 48:$out/attack2.png > $out/tutorials.log 2>&1
log=$out/tutorials.log
shown=$(grep -a -E '^\[[0-9]+ [0-9.]+\] tutorial shown:' $log | awk '{ print $5 }' | xargs)
queue=$(grep -a '^fight leader' $log | head -1 | sed -E 's/.* queue (.*) waiting .*/\1/')
case "$queue" in *12:*) ordered=1 ;; *) ordered=0 ;; esac
if [ "$shown" != "6 21 34 35" ] || [ $ordered = 0 ]; then
  echo "FAIL tutorials: shown [$shown] (want 6 21 34 35, and no second 6 after the load), the leader's queue after the attack's box '$queue' (want an attack, 12; see $log)"
  exit 1
fi
echo "ok   tutorials: 6 21 34 35 shown once each, the attack's box gave the order ($queue); pictures in $out"
