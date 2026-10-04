#!/bin/sh
# Runs a stealth test script (kotor/tools/stealth/scripts/) headless and fast, keeping the log and the
# pictures under kotor/out/stealth/. Run it from the repository root. docs/mechanics/stealth.md says
# what each script shows.
#
#   sh kotor/tools/stealth/run.sh NAME START SCRIPT FRAMES [FRAME:SHOT]...
#
# START is a checkpoint name (bunk, bridge, pod, apartment, uppercity, cantina: docs/testing.md),
# `module:MODULE`, or `save:FOLDER` (a save folder, e.g. one a script wrote to kotor/out/stealth/saves_NAME).
# Writes kotor/out/stealth/NAME.log (the game's lines without the `[frame]` noise, and the `stealth:` lines
# with it, unless ALL=1) and NAME_SHOT.png. EXE (default kotor/out/kotor_stl.exe) is the build to run,
# LOG (default actions,combat) the --log list.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
start=$2
script=$3
frames=$4
shift 4
shots=""
for s in "$@"; do
  shots="$shots --screenshot-at ${s%%:*}:kotor/out/stealth/${name}_${s#*:}.png"
done
mkdir -p kotor/out/stealth
case "$start" in
  module:*) flag=--module; from=${start#module:} ;;
  save:*) flag=--load; from=${start#save:} ;;
  *) flag=--load; from=kotor/out/checkpoints/$start ;;
esac
${EXE:-kotor/out/kotor_stl.exe} $flag "$from" --no-render --speed 8 --frames $frames --input "$script" $shots \
  --log ${LOG:-actions,combat} --saves kotor/out/stealth/saves_$name > kotor/out/stealth/$name.raw 2>&1
code=$?
if [ -n "$ALL" ]; then cp kotor/out/stealth/$name.raw kotor/out/stealth/$name.log
else grep -a -v '^\[' kotor/out/stealth/$name.raw > kotor/out/stealth/$name.log; grep -a '^\[.*stealth' kotor/out/stealth/$name.raw >> kotor/out/stealth/$name.log; fi
echo "exit $code, $(grep -a -c '^fault' kotor/out/stealth/$name.raw) faults, $(wc -l < kotor/out/stealth/$name.log) lines"
