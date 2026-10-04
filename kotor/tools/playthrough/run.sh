#!/bin/sh
# Replays an input script headless and keeps the log and the pictures under kotor/out/pt/.
#
#   sh kotor/tools/playthrough/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]... [-- EXTRA KOTOR ARGS]
#
# Writes kotor/out/pt/NAME.log and kotor/out/pt/NAME_SHOT.png. Run from the repository root.
# LOG (default scripts) is the --log list; EXTRA goes to the executable (e.g. --seed 3).
#   FAST=1       --no-render --speed 8 instead of --headless: the same log in a third of the time (SPEED=N)
#   LOAD=SAVE    start from a save, e.g. LOAD=kotor/out/checkpoints/pod (docs/testing.md, "Checkpoints");
#                SCRIPT is then the resume script kotor/out/checkpoints/pod.txt, or one of your own
#   EXE=PATH     another executable (default kotor/out/kotor.exe)
#   SAVES=DIR    the saves directory (default kotor/out/saves); runs in parallel need one each
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
script=$2
frames=$3
shift 3
shots=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  shots="$shots --screenshot-at ${1%%:*}:kotor/out/pt/${name}_${1#*:}.png"
  shift
done
if [ "$1" = "--" ]; then shift; fi
mkdir -p kotor/out/pt
mode="--headless"
if [ -n "$FAST" ]; then mode="--no-render --speed ${SPEED:-8}"; fi
timeout ${TIMEOUT:-240} ${EXE:-kotor/out/kotor.exe} $mode --frames $frames --input $script $shots --log ${LOG:-scripts} ${LOAD:+--load "$LOAD"} ${SAVES:+--saves "$SAVES"} "$@" > kotor/out/pt/$name.log 2>&1
echo "exit $? lines $(wc -l < kotor/out/pt/$name.log)"
