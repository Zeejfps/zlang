#!/bin/sh
# Plays 30_milestones.txt (the whole route with a save at each milestone) and keeps the saves under
# kotor/out/ms/NAME (trask room3 hall bridge m01ab pod apartment uppersouth larrim uppernorth cantina
# lowercity undercity crashsite sithbase). About 15 minutes. Run it again after a change that moves the
# timeline (the frames in 30_milestones.txt are those of the day it was made).
#
# Start a check from a milestone (seconds instead of minutes):
#   sh kotor/tools/playthrough/from.sh NAME SCRIPT FRAMES [FRAME:SHOT]...
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
rm -rf kotor/out/saves kotor/out/ms
mkdir -p kotor/out/ms
TIMEOUT=${TIMEOUT:-2400} LOG=${LOG:-dialog} sh kotor/tools/playthrough/run.sh milestones kotor/tools/playthrough/30_milestones.txt ${FRAMES:-89500}
python kotor/tools/py/keep_milestones.py
