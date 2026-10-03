#!/bin/sh
# Replays an input script headless and keeps the log and the pictures under kotor/out/pt/.
#
#   sh kotor/tools/playthrough/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]... [-- EXTRA KOTOR ARGS]
#
# Writes kotor/out/pt/NAME.log and kotor/out/pt/NAME_SHOT.png. Run from the repository root.
# LOG (default scripts) is the --log list; EXTRA goes to the executable (e.g. --seed 3).
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
timeout ${TIMEOUT:-240} kotor/out/kotor.exe --headless --frames $frames --input $script $shots --log ${LOG:-scripts} "$@" > kotor/out/pt/$name.log 2>&1
echo "exit $? lines $(wc -l < kotor/out/pt/$name.log)"
