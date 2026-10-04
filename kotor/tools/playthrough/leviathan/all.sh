#!/bin/sh
# Replays the Leviathan playthrough part after part, each from the checkpoint the one before saved:
#
#   sh kotor/tools/playthrough/leviathan/all.sh [FIRST_PART]        (run from the repository root; about 10 minutes)
#
# After each part the run's log is searched for the line that says the part did what it was written to do (a conversation that
# ended, a journal state, a module); a part that did not stops the chain, because the next one would start from a wrong state.
# Needs kotor/out/kotor_lev.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_lev.exe). Logs: kotor/out/pt/lNN.log, checkpoints
# kotor/out/pt/lev_ckpt/NAME, pictures kotor/out/pt/lNN_SHOT.png (one 30 frames before the end of each part).
# docs/playthrough-leviathan.md says what each part does and what it shows.
d=kotor/tools/playthrough/leviathan
first=${1:-1}
export LOG=${LOG:-dialog,combat}

# step PART FRAMES CKPT_IN CKPT_OUT EXPECT   (EXPECT is a fixed string that must be in the log)
step() {
  part=$1; frames=$2; from=$3; to=$4; expect=$5
  if [ "$part" -lt "$first" ]; then return; fi
  n=$(printf '%02d' $part)
  echo "== part $part ($n) from '$from' to '$to'"
  if [ -n "$from" ]; then
    CKPT=$from sh $d/run.sh l$part $n $frames $((frames - 30)):end
  else
    sh $d/run.sh l$part $n $frames $((frames - 30)):end
  fi
  grep -a "^run:" kotor/out/pt/l$part.log
  if ! grep -a -F -q "$expect" kotor/out/pt/l$part.log; then
    echo "FAIL part $part: no '$expect' in kotor/out/pt/l$part.log"
    return 1
  fi
  echo "ok   part $part: $expect"
  if [ -n "$to" ]; then
    if ! grep -a -q "\] saved " kotor/out/pt/l$part.log; then echo "FAIL part $part: no save in the log"; return 1; fi
    sh $d/ckpt.sh $to
  fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_lev; fi
step 1 23400 "" cell "journal: lev_captured state 1 " || exit 1
step 2 3400 cell freed "journal: lev_captured state 10 " || exit 1
step 3 4500 freed deck "module lev_m40ab: area m40ab" || exit 1
step 4 40000 deck bridgearr "module lev_m40ad: area m40ad" || exit 1
step 5 12800 bridgearr saulend "global LEV_SAULDEAD 1" || exit 1
step 6 6000 saulend backdeck "journal: lev_captured state 66 " || exit 1
step 7 4700 backdeck hangar "module lev_m40ac: area m40ac" || exit 1
step 8 26000 hangar hawkarr "module ebo_m40ad: area m12aa" || exit 1
step 9 14000 hawkarr hawkpost "dialog end ebo_carth (normal)" || exit 1
echo "the Leviathan chain is done"
