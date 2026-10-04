#!/bin/sh
# Replays one part of the Korriban playthrough (docs/playthrough-korriban.md) fast and headless.
#
#   sh kotor/tools/playthrough/korriban/run.sh NAME PART FRAMES [FRAME:SHOT]...
#
# PART is the script's number ("01", "02", ...): kotor/tools/playthrough/korriban/PART_*.txt (or a path to a script). Part 1
# starts in korr_m33aa; the others load the checkpoint a part before it left (kotor/out/pt/kor_ckpt/CKPT,
# see the comment at the top of each script) given as CKPT=name. The log is kotor/out/pt/NAME.log, the
# pictures kotor/out/pt/NAME_SHOT.png. Environment: LOG (default dialog), EXE (default
# kotor/out/kotor_kor.exe), SAVES (default kotor/out/pt/saves_kor).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
part=$2
frames=$3
shift 3
if [ -f "$part" ]; then script=$part; else script=$(ls kotor/tools/playthrough/korriban/${part}_*.txt | head -1); fi
export EXE=${EXE:-kotor/out/kotor_kor.exe}
export LOG=${LOG:-dialog}
export SAVES=${SAVES:-kotor/out/pt/saves_kor}
export FAST=1
if [ -n "$CKPT" ]; then
  export LOAD=kotor/out/pt/kor_ckpt/$CKPT
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@"
else
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- --module ${MODULE:-korr_m33aa}
fi
