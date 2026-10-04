#!/bin/sh
# Replays a Tatooine input script headless (fast) and keeps the log and the pictures under kotor/out/pt/.
#
#   sh kotor/tools/playthrough/tatooine/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]... [-- EXTRA KOTOR ARGS]
#
# Run from the repository root. Like playthrough/run.sh, but with its own executable (EXE, default
# kotor/out/kotor_tat.exe) and its own saves directory (SAVES, default kotor/out/saves_tat), so it can run
# beside other agents' runs. LOG is the --log list (default scripts); LOAD=DIR starts from a checkpoint.
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
mkdir -p kotor/out/pt "${SAVES:-kotor/out/saves_tat}"
timeout ${TIMEOUT:-300} ${EXE:-kotor/out/kotor_tat.exe} --no-render --speed ${SPEED:-8} --frames $frames --input $script $shots --log ${LOG:-scripts} ${LOAD:+--load "$LOAD"} --saves "${SAVES:-kotor/out/saves_tat}" "$@" > kotor/out/pt/$name.log 2>&1
echo "exit $? lines $(wc -l < kotor/out/pt/$name.log)"
