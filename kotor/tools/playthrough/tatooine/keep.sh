#!/bin/sh
# Keeps the newest manual save of the Tatooine runs as a checkpoint: kotor/out/tat_cp/NAME, to start a later leg
# from (LOAD=kotor/out/tat_cp/NAME sh kotor/tools/playthrough/tatooine/run.sh ...). A leg writes it with a `save`
# line at its end. Run from the repository root.
#
#   sh kotor/tools/playthrough/tatooine/keep.sh NAME
saves=${SAVES:-kotor/out/saves_tat}
last=$(ls "$saves" | grep ' - Game' | sort | tail -1)
if [ -z "$last" ]; then echo "no manual save in $saves"; exit 1; fi
mkdir -p kotor/out/tat_cp
rm -rf "kotor/out/tat_cp/$1"
cp -r "$saves/$last" "kotor/out/tat_cp/$1"
echo "kept $last as kotor/out/tat_cp/$1"
