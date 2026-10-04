#!/bin/sh
# Replays the Korriban playthrough part after part, each from the checkpoint the one before saved:
#
#   sh kotor/tools/playthrough/korriban/all.sh [FIRST_PART]        (run from the repository root; about 35 minutes)
#
# After each part the run's log is searched for the line that says the part did what it was written to do (a conversation that
# ended, a journal state, a global); a part that did not stops the chain, because the next one would start from a wrong state.
# The dice move with anything that changes how many rolls the game makes: the Sith Code test's last question is the only reply
# that depends on them (part 12 tries the other answer when the first fails).
# Needs kotor/out/kotor_kor.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_kor.exe). Logs: kotor/out/pt/kNN.log, checkpoints
# kotor/out/pt/kor_ckpt/NAME, pictures kotor/out/pt/kNN_SHOT.png (one 30 frames before the end of each part: a black world after a
# conversation would show there). docs/playthrough-korriban.md says what each part does and what it shows.
d=kotor/tools/playthrough/korriban
first=${1:-1}
export LOG=${LOG:-dialog,combat}

# step PART FRAMES CKPT_IN CKPT_OUT EXPECT   (EXPECT is a fixed string that must be in the log)
step() {
  part=$1; frames=$2; from=$3; to=$4; expect=$5
  if [ "$part" -lt "$first" ]; then return; fi
  n=$(printf '%02d' $part)
  echo "== part $part ($n) from '$from' to '$to'"
  if [ -n "$from" ]; then
    CKPT=$from sh $d/run.sh k$part $n $frames $((frames - 30)):end
  else
    sh $d/run.sh k$part $n $frames $((frames - 30)):end
  fi
  grep -a "^run:" kotor/out/pt/k$part.log
  if ! grep -a -F -q "$expect" kotor/out/pt/k$part.log; then
    echo "FAIL part $part: no '$expect' in kotor/out/pt/k$part.log"
    return 1
  fi
  echo "ok   part $part: $expect"
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_kor; fi
step 1 120 "" dock "global K_STAR_MAP 30" || exit 1
step 2 3600 dock port "dialog end kor33_portauth (normal)" || exit 1
step 3 4800 port shaardan "dialog end kor33_shaardan" || exit 1
step 4 6100 shaardan guard "journal: kor33_enteracademy state 25" || exit 1
step 5 600 guard back "module korr_m33aa: area m33aa" || exit 1
step 6 4100 back thugs "global KOR_THUG_DEATH 4" || exit 1
step 7 4000 thugs murder "global KOR_MURDER_DEAD 1" || exit 1
step 8 4100 murder lashowe "dialog end kor33_lashowe (normal)" || exit 1
step 9 3700 lashowe guard2 "journal: kor33_enteracademy state 46" || exit 1
step 10 9700 guard2 academy "journal: kor35_waysith state 10" || exit 1
step 11 9400 academy yuthura "global KOR_SITH_CODE 1" || exit 1
if [ "$first" -le 12 ]; then
  if ! step 12 1700 yuthura code "global KOR_SITH_PRESTIGE 1"; then
    # The last question of the Code test is picked by Random: "False." answers the one the replay gets, "True." the others.
    sed 's/~False/~True/' $d/12_code.txt > kotor/out/pt/12_code_alt.txt
    CKPT=yuthura sh $d/run.sh k12 kotor/out/pt/12_code_alt.txt 1700 1670:end
    grep -a -F -q "global KOR_SITH_PRESTIGE 1" kotor/out/pt/k12.log || { echo "FAIL part 12 with both answers"; exit 1; }
    sh $d/ckpt.sh code
  fi
fi
step 13 5300 code mando "journal: kor35_mandalorian state 40" || exit 1
step 14 1200 mando report1 "global KOR_SITH_PRESTIGE 2" || exit 1
step 15 800 report1 valley "module korr_m36aa: area m36aa" || exit 1
step 17 9100 valley droid "journal: kor38_roguedroid state 30" || exit 1
step 18 5100 droid thalia "dialog end kor34_thaliamay (normal)" || exit 1
step 19 4500 thalia beast "(kor34_monster) dies" || exit 1
step 20 2700 beast freed "journal: kor35_renegadesith state 40" || exit 1
step 21 2500 freed report2 "global KOR_SITH_PRESTIGE 4" || exit 1
step 22 8400 report2 ajunta "journal: kor37_ajuntapall state 10" || exit 1
step 23 2400 ajunta sword "journal: kor37_ajuntapall state 30" || exit 1
step 24 4500 sword night "global KOR_SITH_PRESTIGE 5" || exit 1
step 25 4100 night tomb "dialog end kor39_utharwynn (normal)" || exit 1
step 26 9600 tomb acid "Special Cold Grenade" || exit 1
step 27 1200 acid map "global K_STAR_MAP 40" || exit 1
step 28 8200 map finale "journal: kor35_waysith state 56" || exit 1
step 31 2200 finale hawk "module ebo_m12aa: area m12aa" || exit 1
step 32 2500 hawk "" "module ebo_m40aa" || exit 1
echo "the Korriban chain is done"
