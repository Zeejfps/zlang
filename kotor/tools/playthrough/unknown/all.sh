#!/bin/sh
# Replays the Unknown World playthrough part after part, each from the checkpoint the one before saved:
#
#   sh kotor/tools/playthrough/unknown/all.sh [FIRST_PART]        (run from the repository root; needs the Leviathan chain's checkpoint "hawkpost":
#                                                                   sh kotor/tools/playthrough/leviathan/all.sh first; about 6 minutes)
#
# After each part the run's log is searched for the line that says the part did what it was written to do (a conversation that
# ended, a journal state, a module); a part that did not stops the chain, because the next one would start from a wrong state.
# Needs kotor/out/kotor_lev.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_lev.exe). Logs: kotor/out/pt/uN.log, checkpoints
# kotor/out/pt/unk_ckpt/NAME, pictures kotor/out/pt/uN_SHOT.png (one 30 frames before the end of each part).
# docs/playthrough-unknown-world.md says what each part does and what it shows.
d=kotor/tools/playthrough/unknown
first=${1:-1}
export LOG=${LOG:-dialog,combat}

# step PART FRAMES CKPT_IN CKPT_OUT EXPECT   (EXPECT is a fixed string that must be in the log)
step() {
  part=$1; frames=$2; from=$3; to=$4; expect=$5
  if [ "$part" -lt "$first" ]; then return; fi
  n=$(printf '%02d' $part)
  echo "== part $part ($n) from '$from' to '$to'"
  CKPT=$from sh $d/run.sh u$part $n $frames $((frames - 30)):end
  grep -a "^run:" kotor/out/pt/u$part.log
  if ! grep -a -F -q "$expect" kotor/out/pt/u$part.log; then
    echo "FAIL part $part: no '$expect' in kotor/out/pt/u$part.log"
    return 1
  fi
  echo "ok   part $part: $expect"
  if [ -n "$to" ]; then
    if ! grep -a -q "\] saved " kotor/out/pt/u$part.log; then echo "FAIL part $part: no save in the log"; return 1; fi
    sh $d/ckpt.sh $to
  fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_unk; fi
step 1 11000 lev:hawkpost crash "dialog end unk41_carth (normal)" || exit 1
step 2 4500 crash beach "module unk_m41aa: area m41aa" || exit 1
step 3 8000 beach duros "dialog end unk41_ithor01 (normal)" || exit 1
step 5 3500 duros approach "module unk_m41ad: area m41ad" || exit 1
step 6 4500 approach cave "module unk_m41ab: area m41ab" || exit 1
step 7 2400 cave door "module unk_m42aa: area m42aa" || exit 1
step 8 12800 door eldertalk "journal: unk_trapped state 15" || exit 1
step 9 16000 eldertalk onecamp "module unk_m43aa: area m43aa" || exit 1
step 10 17500 onecamp scout "journal: unk_trapped state 33" || exit 1
step 11 12400 scout elders2 "module unk_m41ab: area m41ab" || exit 1
step 12 17000 elders2 eldersok "journal: unk_trapped state 37" || exit 1
step 13 9000 eldersok alone1 "module ebo_m41aa: area m12aa" || exit 1
step 14 3500 alone1 alone2 "module unk_m41aa: area m41aa" || exit 1
step 15 16000 alone2 temple "dialog end unk41_guide_dlg (normal)" || exit 1
step 16 6100 temple library "dialog end unk44_lib_dlg (normal)" || exit 1
step 17 3100 library summit "module unk_m44ac: area m44ac" || exit 1
step 18 11050 summit bastdone "journal: unk_trapped state 99" || exit 1
step 19 3100 bastdone fieldoff "journal: k_starforge state 75" || exit 1
step 20 2700 fieldoff templeout "module unk_m41ad: area m41ad" || exit 1
step 21 6100 templeout hawkback "dialog end unk41_carth (normal)" || exit 1
step 22 4500 hawkback "" "module stunt_42: area stunt_ebocom" || exit 1
echo "the Unknown World chain is done"
