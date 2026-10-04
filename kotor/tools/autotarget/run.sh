#!/bin/sh
# Walks the leader by the keys from a checkpoint and keeps the log of every change of the auto-target
# (the objects log's `target: OLD -> NEW (distance, angle ccw of the facing)` lines) and any pictures,
# under kotor/out/autotarget/. Run it from the repository root. docs/mechanics/controls.md ("Mouse:
# hover, click, target block") says what the original does and what the scripts show.
#
#   sh kotor/tools/autotarget/run.sh NAME CHECKPOINT SCRIPT FRAMES [FRAME:SHOT]...
#
# CHECKPOINT is a name from docs/testing.md (bunk, uppercity, ...). A script holds the keys of a walk:
# `FRAME keydown w` (never before frame 8: nothing is typed behind the loading screen), `keyup`, `ui pos`,
# `mouse move X Y`, `mouse click left X Y`, `key e`. EXE (default kotor/out/kotor.exe) is the build to run.
# Not --speed: the camera and the HUD step every tick, so the half-second walk timer is the real one.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
start=$2
script=$3
frames=$4
shift 4
shots=""
for s in "$@"; do
  shots="$shots --screenshot-at ${s%%:*}:kotor/out/autotarget/${name}_${s#*:}.png"
done
mkdir -p kotor/out/autotarget
${EXE:-kotor/out/kotor.exe} --load kotor/out/checkpoints/$start --no-render --frames $frames --input "$script" $shots \
  --log objects --saves kotor/out/autotarget/saves_$name > kotor/out/autotarget/$name.raw 2>&1
code=$?
grep -a 'target:\|enemy sighted\|^pos \|^target \|^pick ' kotor/out/autotarget/$name.raw > kotor/out/autotarget/$name.log
echo "exit $code, $(grep -a -c '^fault' kotor/out/autotarget/$name.raw) faults, $(grep -a -c 'target:' kotor/out/autotarget/$name.log) target changes"
