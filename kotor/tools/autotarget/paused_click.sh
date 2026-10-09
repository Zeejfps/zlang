#!/bin/sh
# A target clicked while the game is auto-paused stays (docs/re/movement.md 7.1, "While paused"):
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/autotarget/paused_click.sh
#
# Runs scripts/es_paused_click.txt from `bunk` (about 3,800 frames at real speed): the player walks by the
# keys into the Endar Spire's end_cut2_sith1 sighting, the game auto-pauses, he clicks Trask then the Sith.
# PASS when the Sith is the target right after the click and still is 1.4 s later with nothing changing it.
# Before the fix the walking drop ran on the real frame time and dropped the Sith half a second after each
# click. Exit 1 on a FAIL, 2 when the set-up drifted (no auto-pause, or the click missed: the checkpoint was
# remade and the frames or the Sith's screen box moved; a `ui info` line while paused prints the box).
name=es_paused_click
EXE=${EXE} sh kotor/tools/autotarget/run.sh $name bunk kotor/tools/autotarget/scripts/$name.txt 3800 > /dev/null
raw=kotor/out/autotarget/$name.raw
grep -a 'auto-pause\|^target \|target:' $raw | awk '
    /auto-pause:/ { enemy = $NF; sub(/\)/, "", enemy); n = 0; changed = 0; next }
    /^target / { n++; id[n] = $2; next }
    /target:/ { if (n >= 1) { changed++; line = $0 } }
    END {
        if (!enemy || n < 1 || id[1] != enemy) { printf "SETUP no auto-pause, or the click did not select the sighted enemy (%s): %s\n", enemy, id[1]; exit 2 }
        if (changed || n < 2 || id[2] != enemy) { printf "FAIL the clicked enemy %s did not hold while paused: %s\n", enemy, line; exit 1 }
        printf "PASS the clicked enemy %s held through the pause\n", enemy
    }'
