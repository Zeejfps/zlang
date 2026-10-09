#!/bin/sh
# Do the dead stay down? Two cut scenes from checkpoints (kotor/tools/checkpoints/make.sh) with creatures that die in
# them, checked from the fight trace (--log trace: one line per fighting or dead creature every 6 frames, with the
# animation the world asks for); FAIL and exit status 1 when a creature that is dead shows anything but a die or dead
# animation, or when the run had no corpse to look at:
#
#   sh kotor/tools/combat/corpses.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 20 seconds)
#
#   endar   bunk       the Endar Spire's room 3 and room 5 cut scenes: soldiers killed by CutsceneAttack while the
#                      conversation goes on (the conversation's back-to-standing reset stood them up again, and after the
#                      die animation's 3 s timer the dead animation made them fall a second time)
#   taris   apartment  tar02_preraid: the trooper kills the bith in the middle of the conversation (the corpse stood
#                      upright for the rest of the visit)
#   ring    uppercity  corpses2.txt: five Sith troopers killed one by one; their bodies stay after their objects go,
#                      the latest three of them (--log objects: five "corpse ... kept",, the first two "corpse ... fades"
#                      when the fourth and fifth come; docs/re/actions.md 3.15); the first leaves a bag, hidden behind
#                      its body, which the pointer on the body picks (`ui bodypick`)
#
# The logs are kotor/out/combat/corpses_NAME.log. docs/re/dialogue.md 8.1 says what the original does.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
fail=0

for need in bunk apartment uppercity; do
  if [ ! -d $ck/$need ]; then echo "no checkpoint $ck/$need: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
done

# check NAME: the trace lines of dead creatures in corpses_NAME.log, and those that do not lie down
check() {
  name=$1
  log=$out/corpses_$name.log
  dead=$(grep -a -E '^\[[0-9]+ [0-9.]+\] trace .* dead( cutscene)?$' $log | wc -l)
  bad=$(grep -a -E '^\[[0-9]+ [0-9.]+\] trace .* dead( cutscene)?$' $log | grep -a -v -E ' anim [0-9]+ \((die|die1|dead|dead1|cdie|cdead)\) ')
  if [ "$dead" -lt 20 ]; then
    echo "FAIL $name: only $dead trace lines of dead creatures in $log: the scene did not play"
    fail=1
  elif [ -n "$bad" ]; then
    echo "FAIL $name: a dead creature shows another animation ($(echo "$bad" | wc -l) of $dead trace lines, first below; see $log)"
    echo "$bad" | head -2
    fail=1
  else
    echo "ok   $name: $dead trace lines of dead creatures, all lying down"
  fi
}

rm -rf $out/saves_corpses
$exe --load $ck/bunk --no-render --speed 8 --saves $out/saves_corpses --input $ck/bunk.txt --frames 4000 --log trace > $out/corpses_endar.log 2>&1
check endar
$exe --load $ck/apartment --no-render --speed 8 --saves $out/saves_corpses --input $ck/apartment.txt --frames 1700 --log trace > $out/corpses_taris.log 2>&1
check taris
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_corpses --input kotor/tools/combat/corpses2.txt --frames 900 --log objects,combat > $out/corpses_ring.log 2>&1
kept=$(grep -a -c -E '^\[[0-9]+ [0-9.]+\] corpse [0-9]+ g_sithtroop01 kept' $out/corpses_ring.log)
faded=$(grep -a -E '^\[[0-9]+ [0-9.]+\] corpse [0-9]+ fades' $out/corpses_ring.log | awk '{ print $4 }' | xargs)
first=$(grep -a -E '^\[[0-9]+ [0-9.]+\] corpse [0-9]+ g_sithtroop01 kept' $out/corpses_ring.log | head -2 | awk '{ print $4 }' | xargs)
if [ "$kept" -ne 5 ] || [ "$faded" != "$first" ]; then
  echo "FAIL ring: $kept bodies kept (want 5), faded [$faded] (want the first two kept, [$first]; see $out/corpses_ring.log)"
  fail=1
else
  echo "ok   ring: 5 bodies kept, the first two ($first) faded when the fourth and fifth came"
fi
# The first trooper carries a spike, so its body leaves a bag, hidden behind the body: the pointer on the body is
# on the bag (ProcessInput's ray hands a hit body to its bag, client +0x3dc).
picked=$(grep -a '^bodypick bag' $out/corpses_ring.log | head -1)
case "$picked" in *"hidden true: 4 of 4"*) echo "ok   bag: the hidden bag picked through its body ($picked)" ;;
  *) echo "FAIL bag: the pointer on the body does not pick its hidden bag ('$picked'; see $out/corpses_ring.log)"; fail=1 ;; esac
exit $fail
