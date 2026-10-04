#!/bin/sh
# Replays the Star Forge playthrough (the light side) part after part, each from the checkpoint the one before saved:
#
#   sh kotor/tools/playthrough/starforge/all.sh [FIRST_PART]        (run from the repository root; about 15 minutes)
#
# After each part the run's log is searched for the line that says the part did what it was written to do (a conversation that
# ended, a module entered, a boss dead); a part that did not stops the chain, because the next one would start from a wrong state.
# Needs kotor/out/kotor_sf.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_sf.exe). Logs: kotor/out/pt/sN.log, checkpoints
# kotor/out/pt/sf_ckpt/NAME, pictures kotor/out/pt/sN_end.png (one 30 frames before the end of each part). The last part runs with
# --cinema: the films, the credits and the main menu are shown in the hidden run (docs/playthrough-star-forge.md says what each
# part does and what it shows).
d=kotor/tools/playthrough/starforge
first=${1:-1}
export LOG=${LOG:-dialog,combat}

# step PART FRAMES CKPT_IN CKPT_OUT EXPECT   (EXPECT is a fixed string that must be in the log)
step() {
  part=$1; frames=$2; from=$3; to=$4; expect=$5
  if [ "$part" -lt "$first" ]; then return; fi
  n=$(printf '%02d' $part)
  echo "== part $part ($n) from '$from' to '$to'"
  if [ -n "$from" ]; then
    CKPT=$from TIMEOUT=${TIMEOUT:-900} sh $d/run.sh s$part $n $frames $((frames - 30)):end
  else
    TIMEOUT=${TIMEOUT:-900} sh $d/run.sh s$part $n $frames $((frames - 30)):end
  fi
  grep -a "^run:" kotor/out/pt/s$part.log
  if ! grep -a -F -q "$expect" kotor/out/pt/s$part.log; then
    echo "FAIL part $part: no '$expect' in kotor/out/pt/s$part.log"
    return 1
  fi
  echo "ok   part $part: $expect"
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_sf; fi
step 1 160 "" hawk "saved " || exit 1
step 2 5400 hawk landed "movie 5_9" || exit 1
step 3 1100 landed bay "module sta_m45aa: area m45aa" || exit 1
step 4 5700 bay hall "(sta45_droid_cut1) dies" || exit 1
step 5 7600 hall lvl1 "module sta_m45ab: area m45ab" || exit 1
step 6 9000 lvl1 lvl2 "dialog end k_sta_lightcut (normal)" || exit 1
step 7 7400 lvl2 freeze "(k_sta_sithfreeze) dies" || exit 1
step 8 12500 freeze bastsaved "dialog end k_sta_bastlast (normal)" || exit 1
step 9 10100 bastsaved gens "global STA_GENERATORS 6" || exit 1
step 10 4000 gens fight "dialog end k_sta_darthmalak (normal)" || exit 1
export ARGS=--cinema
step 11 40000 fight "" "to the main menu" || exit 1
echo "the Star Forge chain is done"
