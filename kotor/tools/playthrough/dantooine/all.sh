#!/bin/sh
# Replays the Dantooine playthrough part after part, each from the checkpoint the one before wrote:
#
#   sh kotor/tools/playthrough/dantooine/all.sh [FIRST_PART]        (run from the repository root; about 6 minutes)
#
# Each part takes a picture 30 frames before its end (kotor/out/pt/dN_end.png): a black world after a conversation shows there.
# Needs kotor/out/kotor_dan.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_dan.exe). The logs are
# kotor/out/pt/dNN.log, the checkpoints kotor/out/pt/dan_ckpt/NAME. Starting at a later part reuses the
# checkpoints already there. docs/playthrough-dantooine.md says what each part does and what it shows.
d=kotor/tools/playthrough/dantooine
first=${1:-1}
export LOG=${LOG:-dialog}

step() {   # PART FRAMES CKPT_IN CKPT_OUT [EXTRA RUN.SH ARGS]
  part=$1; frames=$2; from=$3; to=$4; shift 4
  if [ "$part" -lt "$first" ]; then return; fi
  if [ -n "$from" ]; then
    CKPT=$from sh $d/run.sh d$part $(printf '%02d' $part) $frames $((frames - 30)):end "$@"
  else
    sh $d/run.sh d$part $(printf '%02d' $part) $frames $((frames - 30)):end "$@"
  fi
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_dan; fi
step 1 7400 ""      wake
step 2 10000 wake   trial1
step 3 3800 trial1  code
step 4 4200 code    dorak
step 5 1100 dorak   saber
step 6 4200 saber   third
step 7 600 third    grove
step 8 7360 grove   fight
step 9 4200 fight   redeemed
step 10 2800 redeemed return
step 11 6100 return ruins1
step 12 11350 ruins1 ruins2
step 13 7100 ruins2 proved
step 14 5100 proved starmap
step 15 7200 starmap council2
