#!/bin/sh
# Runs an input script from a checkpoint (or a module) headless and fast, keeping the log and the
# pictures under kotor/out/items/. Run it from the repository root.
#
#   sh kotor/tools/items/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...
#
# START is a checkpoint name (bunk, bridge, pod, apartment, uppercity, cantina: docs/testing.md) or
# `module:MODULE`. Writes kotor/out/items/NAME.log (the game's lines without the `[frame]` noise
# unless ALL=1) and NAME_SHOT.png. EXE (default kotor/out/kotor_itm.exe) is the build to run, LOG
# (default actions,scripts) the --log list. Needs the checkpoints made with the same build
# (`EXE=... sh kotor/tools/checkpoints/make.sh`).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
start=$2
script=$3
frames=$4
shift 4
shots=""
for s in "$@"; do
  shots="$shots --screenshot-at ${s%%:*}:kotor/out/items/${name}_${s#*:}.png"
done
mkdir -p kotor/out/items
case "$start" in
  module:*) from="--module ${start#module:}" ;;
  *) from="--load kotor/out/checkpoints/$start" ;;
esac
${EXE:-kotor/out/kotor_itm.exe} $from --no-render --speed 8 --frames $frames --input "$script" $shots \
  --log ${LOG:-actions,scripts} --saves kotor/out/items/saves_$name > kotor/out/items/$name.raw 2>&1
code=$?
if [ -n "$ALL" ]; then cp kotor/out/items/$name.raw kotor/out/items/$name.log; else grep -a -v '^\[' kotor/out/items/$name.raw > kotor/out/items/$name.log; fi
echo "exit $code, $(grep -a -c '^fault' kotor/out/items/$name.raw) faults, $(wc -l < kotor/out/items/$name.log) lines"
