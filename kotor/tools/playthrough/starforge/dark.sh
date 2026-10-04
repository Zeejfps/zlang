#!/bin/sh
# The dark side (docs/playthrough-star-forge.md): from the Hawk on the Unknown World after the temple's dark choice to the dark ending
# movie, the credits and the main menu. Part 20 (the temple summit, Bastila and the fight with Jolee and Juhani) is a separate run from
# the module itself (it is not part of this chain: run it with `MODULE=unk_m44ac sh kotor/tools/playthrough/starforge/run.sh d20 20 12000`).
#
#   sh kotor/tools/playthrough/starforge/dark.sh [FIRST_PART]        (run from the repository root; about 15 minutes)
#
# The chain has its own saves (kotor/out/pt/saves_dk) and checkpoints (names with a d in front: dhawk, dlanded, ...) in
# kotor/out/pt/sf_ckpt, so it can be run next to the light side's. Parts 5 to 7 are the light chain's own scripts (the docking bay's
# east wing, level 1 and level 2's guards are the same for both sides); 21 to 24 and 28 are the dark ones.
d=kotor/tools/playthrough/starforge
first=${1:-21}
export LOG=${LOG:-dialog,combat}
export SAVES=kotor/out/pt/saves_dk

# step PART FRAMES CKPT_IN CKPT_OUT EXPECT [SCRIPT]
step() {
  part=$1; frames=$2; from=$3; to=$4; expect=$5; script=${6:-$part}
  if [ "$part" -lt "$first" ] 2>/dev/null; then return; fi
  echo "== part $part from '$from' to '$to'"
  if [ -n "$from" ]; then
    CKPT=$from TIMEOUT=${TIMEOUT:-900} sh $d/run.sh d$part $script $frames $((frames - 30)):end
  else
    TIMEOUT=${TIMEOUT:-900} sh $d/run.sh d$part $script $frames $((frames - 30)):end
  fi
  grep -a "^run:" kotor/out/pt/d$part.log
  if ! grep -a -F -q "$expect" kotor/out/pt/d$part.log; then
    echo "FAIL part $part: no '$expect' in kotor/out/pt/d$part.log"
    return 1
  fi
  echo "ok   part $part: $expect"
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 21 ]; then rm -rf kotor/out/pt/saves_dk; fi
step 21 160 "" dhawk "saved " 21 || exit 1
step 22 6500 dhawk dlanded "StartNewModule ebo_m12aa" 22 || exit 1
step 23 1100 dlanded dbay "module sta_m45aa: area m45aa" 23 || exit 1
step 24 6400 dbay dhall "(sta45_droid_cut1) dies" 24 || exit 1
step 25 8000 dhall dlvl1 "module sta_m45ab: area m45ab" 05 || exit 1
step 26 12000 dlvl1 dlvl2 "dialog end k_sta_darkcut (normal)" 06 || exit 1
step 27 9000 dlvl2 dfreeze "(k_sta_sithfreeze) dies" 07 || exit 1
step 28 9000 dfreeze dsith "StartNewModule STUNT_51a" 28 || exit 1
step 29 10100 dsith dgens "global STA_GENERATORS 6" 09 || exit 1
step 30 4000 dgens dfight "dialog end k_sta_darthmalak (normal)" 10 || exit 1
export ARGS=--cinema
step 31 60000 dfight "" "to the main menu" 11 || exit 1
echo "the dark side chain is done"
