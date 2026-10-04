#!/bin/sh
# Runs an input script from a milestone save instead of from New Game:
#
#   sh kotor/tools/playthrough/from.sh MILESTONE NAME SCRIPT FRAMES [FRAME:SHOT]... [-- EXTRA KOTOR ARGS]
#
# The game starts in end_m01aa for a moment, then `load kotor/out/ms/MILESTONE` at frame 2 replaces it with the saved
# game (milestones.sh makes the saves); a second load at frame 8 clears what the first left of end_m01aa's objects
# (a load right after the start leaks them: reported). Use `-- --module end_m01aa`. SCRIPT's own frames count from the load (the first frames are the load and the
# fade-in). NAME, FRAMES and the shots are run.sh's.
ms=$1
shift
name=$1
script=$2
shift 2
{
  echo "2 load kotor/out/ms/$ms"
  echo "8 load kotor/out/ms/$ms"
  grep -v '^#' "$script"
} > kotor/out/pt/from_$name.txt
sh kotor/tools/playthrough/run.sh "$name" kotor/out/pt/from_$name.txt "$@"
