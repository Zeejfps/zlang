#!/bin/sh
# Replays one part of the Star Forge playthrough (docs/playthrough-star-forge.md) fast and headless.
#
#   sh kotor/tools/playthrough/starforge/run.sh NAME PART FRAMES [FRAME:SHOT]...
#
# PART is the script's number ("01", "02", ...): kotor/tools/playthrough/starforge/PART_*.txt (or a path to a script). Part 1
# starts in ebo_m41aa (the Hawk on the Unknown World); the others load the checkpoint a part before it left
# (kotor/out/pt/sf_ckpt/CKPT, see the comment at the top of each script) given as CKPT=name. The log is kotor/out/pt/NAME.log,
# the pictures kotor/out/pt/NAME_SHOT.png. Environment: LOG (default dialog), EXE (default kotor/out/kotor_sf.exe), SAVES (default
# kotor/out/pt/saves_sf), MODULE (start in that module instead of ebo_m41aa), ARGS (more arguments for kotor.exe, e.g. ARGS=--cinema
# to show the films and the credits in this hidden run).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
part=$2
frames=$3
shift 3
if [ -f "$part" ]; then script=$part; else script=$(ls kotor/tools/playthrough/starforge/${part}_*.txt | head -1); fi
export EXE=${EXE:-kotor/out/kotor_sf.exe}
export LOG=${LOG:-dialog}
export SAVES=${SAVES:-kotor/out/pt/saves_sf}
export FAST=1
if [ -n "$CKPT" ]; then
  export LOAD=kotor/out/pt/sf_ckpt/$CKPT
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- $ARGS
else
  sh kotor/tools/playthrough/run.sh $name $script $frames "$@" -- --module ${MODULE:-ebo_m41aa} $ARGS
fi
