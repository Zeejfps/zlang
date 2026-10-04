#!/bin/sh
# Runs a Force test script headless and keeps the log under kotor/out/frc/ (run from the repository root).
#
#   sh kotor/tools/force/run.sh NAME SCRIPT FRAMES [FRAME:SHOT]...        MODULE=tar_m02ab LOG=combat,actions
#
# Writes kotor/out/frc/NAME.log and kotor/out/frc/NAME_SHOT.png. EXE defaults to the Force owner's build.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
name=$1
script=$2
frames=$3
shift 3
shots=""
while [ $# -gt 0 ]; do
  shots="$shots --screenshot-at ${1%%:*}:kotor/out/frc/${name}_${1#*:}.png"
  shift
done
mkdir -p kotor/out/frc/saves_$name
timeout ${TIMEOUT:-240} ${EXE:-kotor/out/kotor_frc.exe} --module ${MODULE:-tar_m02ab} --no-render --speed ${SPEED:-8} --mute \
  --frames $frames --input $script $shots --log ${LOG:-combat} --saves kotor/out/frc/saves_$name ${SEED:+--seed $SEED} > kotor/out/frc/$name.log 2>&1
echo "exit $? lines $(wc -l < kotor/out/frc/$name.log)"
