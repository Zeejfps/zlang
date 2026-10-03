#!/bin/sh
# Builds the game and runs it headless over a scripted input, with screenshots.
#
#   sh kotor/tools/ingame/go.sh                                  build only
#   sh kotor/tools/ingame/go.sh SCRIPT FRAMES FRAME:NAME...      build, run SCRIPT for FRAMES frames,
#                                                                write kotor/out/NAME.png after frame FRAME
#
# SCRIPT is an input file (docs/design/engine.md "Headless and logs", plus the `ui` lines of
# lib/ingame/script.ctx); see kotor/tools/ingame/scripts/. Environment: MODULE (default end_m01aa),
# TAILN (lines of output kept, default 8). Run it from the repository root (the directory with kotor/).
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
mkdir -p kotor/out
kotor/tools/ctxc exe kotor -o kotor/out/kotor.exe 2>&1 | head -40
if [ -n "$1" ]; then
  input=$1
  frames=$2
  shift 2
  shots=""
  for s in "$@"; do
    shots="$shots --screenshot-at ${s%%:*}:kotor/out/${s#*:}.png"
  done
  kotor/out/kotor.exe --module ${MODULE:-end_m01aa} --headless --frames $frames --input $input $shots 2>&1 | grep -v '^\[' | tail -${TAILN:-8}
fi
