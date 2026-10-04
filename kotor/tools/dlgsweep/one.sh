#!/bin/sh
# One process of the sweep (run.sh calls it, from the repository root):
#   sh kotor/tools/dlgsweep/one.sh MODULE          lists the dialogues to sweep in MODULE:   $OUT/modules/MODULE.log
#   sh kotor/tools/dlgsweep/one.sh MODULE DLG      sweeps DLG in a fresh MODULE:             $OUT/pairs/MODULE__DLG.log
# Environment: OUT (kotor/out/dlgsweep), EXE (kotor/out/dlgsweep.exe), TIMEOUT (seconds, 300).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
out=${OUT:-kotor/out/dlgsweep}
exe=${EXE:-kotor/out/dlgsweep.exe}
limit=${TIMEOUT:-300}
if [ -z "$2" ]; then
  mkdir -p "$out/modules"
  timeout $limit "$exe" --module "$1" --list > "$out/modules/$1.log" 2>&1
  echo $? > "$out/modules/$1.rc"
else
  mkdir -p "$out/pairs"
  timeout $limit "$exe" --module "$1" --dlg "$2" > "$out/pairs/$1__$2.log" 2>&1
  echo $? > "$out/pairs/$1__$2.rc"
fi
