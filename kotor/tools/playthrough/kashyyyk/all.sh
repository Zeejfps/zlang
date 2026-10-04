#!/bin/sh
# Replays the Kashyyyk playthrough part after part, each from the checkpoint the one before wrote:
#
#   sh kotor/tools/playthrough/kashyyyk/all.sh [FIRST_PART]        (run from the repository root; about 15 minutes)
#
# Needs kotor/out/kotor_kas.exe (kotor/tools/ctxc exe kotor -o kotor/out/kotor_kas.exe). The logs are
# kotor/out/pt/kNN.log, the checkpoints kotor/out/pt/kas_ckpt/NAME. Starting at a later part reuses the
# checkpoints already there. docs/playthrough-kashyyyk.md says what each part does and what it shows.
d=kotor/tools/playthrough/kashyyyk
first=${1:-1}
export LOG=${LOG:-dialog,combat}

step() {   # PART FRAMES CKPT_IN CKPT_OUT [EXTRA RUN.SH ARGS]
  part=$1; frames=$2; from=$3; to=$4; shift 4
  if [ "$part" -lt "$first" ]; then return; fi
  if [ -n "$from" ]; then
    CKPT=$from sh $d/run.sh k$part $(printf '%02d' $part) $frames "$@"
  else
    sh $d/run.sh k$part $(printf '%02d' $part) $frames "$@"
  fi
  if [ -n "$to" ]; then sh $d/ckpt.sh $to; fi
}

if [ "$first" -le 1 ]; then rm -rf kotor/out/pt/saves_kas; fi
step 1 6600 ""      pad1
step 2 4200 pad1    walk1
step 3 6300 walk1   walk2
step 4 2600 walk2   gate1
step 5 10300 gate1  king1
step 6 2000 king1   walk3
step 7 3000 walk3   shadow1
step 8 9200 shadow1 camp
step 9 3500 camp    poached
step 10 2900 poached jolee
step 11 1500 jolee  lower1
step 12 10100 lower1 freyyr -- --seed 3
step 13 6700 freyyr beast
step 14 5100 beast  blade
step 15 8400 blade  droids
step 16 2800 droids mapped
step 17 3000 mapped ""
