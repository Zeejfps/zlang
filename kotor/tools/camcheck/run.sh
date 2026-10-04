#!/bin/sh
# Conversation shots must show something: takes pictures of a set of conversation shots (Trask's first talk
# on the Endar Spire, the wake-up talk with Carth in the Taris apartment, Bastila and the Council on
# Dantooine) and fails when one is mostly black or empty (kotor/tools/py/frame_check.py: mean luminance,
# share of lit pixels, contrast).
#
#   sh kotor/tools/camcheck/run.sh          (from the repository root; EXE=PATH for another executable)
#
# Two fast headless runs in parallel (the Endar Spire replay to frame 34,200, the first part of the Dantooine
# playthrough to frame 3,600), about half a minute; the pictures are kotor/out/pt/cc_*.png and the logs
# kotor/out/pt/cc_es.log and cc_dan.log (the `dialog camera:` lines say where each shot's eye was). Exit 1 and
# a FAIL line per bad picture. The frames are those of the 1/30 s headless run: when the engine's timing of a
# conversation changes they shift, and a frame that falls in a fade or between two lines may need moving
# (docs/testing.md, "Conversation shots").
py=$(command -v python)    # before the PATH change below: the MSYS2 python has no numpy
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
export EXE=${EXE:-kotor/out/kotor.exe}
export FAST=1
export LOG=dialog

# FRAME:NAME, each in the middle of a line: Trask (close-ups and a shoulder shot), the cuts and the framed
# shots of Carth's talk (close-up, wide, shoulder, close-up, wide).
es="700:trask1 1100:trask2 1700:trask3 2200:trask4 32700:carth_cut1 32950:carth_cut2 33050:carth_close 33260:carth_wide 33450:carth_shoulder 33700:carth_close2 34100:carth_wide2"
# Bastila's shots at the landing court, then the Council's static cameras.
dan="400:bastila_wide 750:bastila_close 2300:council1 2700:council2 3000:council3 3560:council4"

mkdir -p kotor/out/pt
rm -f kotor/out/pt/cc_es_*.png kotor/out/pt/cc_dan_*.png    # a run that fails leaves no picture, so no old one passes for it
SAVES=kotor/out/camcheck/saves_es sh kotor/tools/playthrough/run.sh cc_es kotor/tools/playthrough/10_endar_spire.txt 34200 $es > kotor/out/camcheck_es.txt &
SAVES=kotor/out/camcheck/saves_dan sh kotor/tools/playthrough/run.sh cc_dan kotor/tools/playthrough/dantooine/01_arrival_council.txt 3600 $dan -- --module danm13 > kotor/out/camcheck_dan.txt &
wait
cat kotor/out/camcheck_es.txt kotor/out/camcheck_dan.txt

pics=""
for s in $es; do pics="$pics kotor/out/pt/cc_es_${s#*:}.png"; done
for s in $dan; do pics="$pics kotor/out/pt/cc_dan_${s#*:}.png"; done
"$py" kotor/tools/py/frame_check.py $pics
