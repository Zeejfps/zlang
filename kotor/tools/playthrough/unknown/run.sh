#!/bin/sh
# Replays one part of the Unknown World playthrough (docs/playthrough-unknown.md) fast and headless.
#
#   sh kotor/tools/playthrough/unknown/run.sh NAME PART FRAMES [FRAME:SHOT]...
#
# PART is the script's number ("01", "02", ...): kotor/tools/playthrough/unknown/PART_*.txt (or a path to a script). Part 1
# starts from the Leviathan chain's checkpoint (CKPT=lev:hawkpost); the others load the checkpoint a part before it left (kotor/out/pt/unk_ckpt/CKPT,
# see the comment at the top of each script) given as CKPT=name. The log is kotor/out/pt/NAME.log, the
# pictures kotor/out/pt/NAME_SHOT.png. Environment: LOG (default dialog), EXE (default
# kotor/out/kotor_lev.exe), SAVES (default kotor/out/pt/saves_unk).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
part=$2
frames=$3
shift 3
if [ -f "$part" ]; then script=$part; else script=$(ls kotor/tools/playthrough/unknown/${part}_*.txt | head -1); fi
export EXE=${EXE:-kotor/out/kotor_lev.exe}
export LOG=${LOG:-dialog}
export SAVES=${SAVES:-kotor/out/pt/saves_unk}
export FAST=1
if [ -n "$CKPT" ]; then
  # CKPT=lev:NAME is a checkpoint of the Leviathan chain (kotor/out/pt/lev_ckpt/NAME): part 1 starts from "lev:hawkpost".
  case "$CKPT" in lev:*) dir=lev_ckpt; ck=${CKPT#lev:};; *) dir=unk_ckpt; ck=$CKPT;; esac
  export LOAD=kotor/out/pt/$dir/$ck
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- --settings kotor/tools/playthrough/unknown/play.ini ${CINEMA:+--cinema}
else
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- --module ${MODULE:-ebo_m12aa} --settings kotor/tools/playthrough/unknown/play.ini ${CINEMA:+--cinema}
fi
