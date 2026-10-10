#!/bin/sh
# A target clicked while the game is auto-paused stays (docs/re/movement.md 7.1, "While paused"):
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/autotarget/paused_click.sh
#
# Runs scripts/es_paused_click.txt from `bunk` (240 frames, a few seconds; no bot, so no route timing): the
# Endar Spire's end_cut2_sith1 is made hostile, the leader jumps in front of end_door10_cut2 and walks by the
# keys until the Sith comes into sight, the game auto-pauses, he selects the door, then `ui clickon` clicks the
# Sith at its box on the screen. PASS when the Sith is the target right after the click and still is 2.9 s
# later with nothing changing it. Before the fix the walking drop ran on the real frame time and dropped the
# Sith half a second after each click. Exit 1 on a FAIL, 2 when the set-up drifted (no auto-pause while the W
# key was down, the click found the Sith off the screen, or it selected something else).
name=es_paused_click
EXE=${EXE} sh kotor/tools/autotarget/run.sh $name bunk kotor/tools/autotarget/scripts/$name.txt 240 > /dev/null
raw=kotor/out/autotarget/$name.raw
grep -a 'auto-pause\|^target \|target:\|^clickon\|^click ' $raw | awk '
    /auto-pause:/ { enemy = $NF; sub(/\)/, "", enemy); f = $1; sub(/\[/, "", f); frame = f + 0; n = 0; changed = 0; next }
    /^clickon/ { missed = $0; next }
    /^click / { clicked = 1; next }
    /^target / { n++; id[n] = $2; next }
    /target:/ { if (n >= 1) { changed++; line = $0 } }
    END {
        # The script holds W from frame 30 to 130 and clicks at 142: the pause must fall while W is down.
        if (!enemy || frame < 30 || frame > 130) { printf "SETUP no auto-pause while the leader walked by the keys (frames 30 to 130): %s at %d\n", enemy, frame; exit 2 }
        if (missed || !clicked) { printf "SETUP the click did not happen: %s\n", missed; exit 2 }
        if (n < 1 || id[1] != enemy) { printf "SETUP the click did not select the sighted enemy %s: %s\n", enemy, id[1]; exit 2 }
        if (changed || n < 2 || id[2] != enemy) { printf "FAIL the clicked enemy %s did not hold while paused: %s\n", enemy, line; exit 1 }
        printf "PASS the clicked enemy %s held through the pause (sighted at frame %d)\n", enemy, frame
    }'
