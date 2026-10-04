#!/bin/sh
# Walks the leader with the real keys and clicks of an input script from a checkpoint and keeps the gait log:
# one `gait TAG anim A speed S rate R ...` line per walking or running creature per frame (lib/scene/visual.ctx
# trace_gait). Run it from the repository root. docs/re/movement.md 3.6 and 6.2 say what the original does;
# `python kotor/tools/py/gait_check.py kotor/out/gait/NAME.log` tabulates the log.
#
#   sh kotor/tools/gait/run.sh NAME CHECKPOINT SCRIPT FRAMES [extra kotor.exe arguments...]
#
# EXE (default kotor/out/kotor.exe) is the build to run; pictures: `--screenshot-range FROM:TO:DIR` as extra
# arguments (docs/testing.md). Not --speed: the camera and the keys step every tick.
name=$1
start=$2
script=$3
frames=$4
shift 4
mkdir -p kotor/out/gait
${EXE:-kotor/out/kotor.exe} --load kotor/out/checkpoints/$start --no-render --frames $frames --input "$script" "$@" \
  --log gait,actions --saves kotor/out/gait/saves_$name > kotor/out/gait/$name.raw 2>&1
code=$?
grep -a '^\[[0-9]* [0-9.]*\] gait \|^pos \|^party ' kotor/out/gait/$name.raw > kotor/out/gait/$name.log
echo "exit $code, $(grep -a -c '^fault' kotor/out/gait/$name.raw) faults, $(grep -a -c ' gait ' kotor/out/gait/$name.log) gait lines"
