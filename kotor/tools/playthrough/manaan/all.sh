#!/bin/sh
# Replays the Manaan playthrough part after part, each from the checkpoint the one before wrote:
#
#   sh kotor/tools/playthrough/manaan/all.sh [FIRST_PART]        (run from the repository root; about 15 minutes)
#
# Each part takes a picture 30 frames before its end (kotor/out/pt/mN_end.png). Needs kotor/out/kotor_man.exe
# (kotor/tools/ctxc exe kotor -o kotor/out/kotor_man.exe). The logs are kotor/out/pt/mNN.log, the checkpoints
# kotor/out/pt/man_ckpt/NAME. Starting at a later part reuses the checkpoints already there. Parts 14 to 16 are the
# branches (the overloaded harvester instead of the toxin, the Selkath's law, the way out) and are not part of the chain: run them
# with `all.sh 14`, `all.sh 15` and `all.sh 16`. docs/playthrough-manaan.md says what each part does and what it shows.
d=kotor/tools/playthrough/manaan
first=${1:-1}
export LOG=${LOG:-dialog,combat}

step() {   # PART FRAMES CKPT_IN CKPT_OUT
  part=$1; frames=$2; from=$3; to=$4
  if [ "$part" -lt "$first" ]; then return; fi
  if [ -n "$from" ]; then
    CKPT=$from sh $d/run.sh m$part $(printf '%02d' $part) $frames $((frames - 30)):end
  else
    sh $d/run.sh m$part $(printf '%02d' $part) $frames $((frames - 30)):end
  fi
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_man; fi
if [ "$first" -le 13 ]; then
  step 1 4850 ""         dock
  step 2 5750 dock       wann
  step 3 6150 wann       prisoner
  step 4 4400 prisoner   lobby
  step 5 3650 lobby      droid
  step 6 17400 droid     trial
  step 7 5700 trial      wann2
  step 8 9900 wann2      suit
  step 9 14050 suit      kolto
  step 10 12250 kolto    sci
  step 11 4600 sci       rift
  step 12 1100 rift      starmap
  step 13 3400 starmap   surface
fi
if [ "$first" -eq 14 ]; then step 14 10500 sci overload; fi
if [ "$first" -eq 15 ]; then step 15 4100 prisoner ""; fi
if [ "$first" -eq 16 ]; then step 16 2400 surface ""; fi
