#!/bin/sh
# Replays one part of the Dantooine playthrough (docs/playthrough-dantooine.md) fast and headless.
#
#   sh kotor/tools/playthrough/dantooine/run.sh NAME PART FRAMES [FRAME:SHOT]...
#
# PART is the script's number ("01", "02", ...): kotor/tools/playthrough/dantooine/PART_*.txt. Part 1
# starts in danm13; the others load the checkpoint a part before it left (kotor/out/pt/dan_ckpt/CKPT,
# see the comment at the top of each script) given as CKPT=name. The log is kotor/out/pt/NAME.log, the
# pictures kotor/out/pt/NAME_SHOT.png. Environment: LOG (default dialog), EXE (default
# kotor/out/kotor_dan.exe), SAVES (default kotor/out/pt/saves_dan).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
part=$2
frames=$3
shift 3
script=$(ls kotor/tools/playthrough/dantooine/${part}_*.txt | head -1)
export EXE=${EXE:-kotor/out/kotor_dan.exe}
export LOG=${LOG:-dialog}
export SAVES=${SAVES:-kotor/out/pt/saves_dan}
export FAST=1
if [ -n "$CKPT" ]; then
  export LOAD=kotor/out/pt/dan_ckpt/$CKPT
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@"
else
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- --module ${MODULE:-danm13}
fi
