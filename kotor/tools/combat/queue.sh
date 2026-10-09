#!/bin/sh
# The leader's combat queue from clicks (docs/re/actions.md 3.13 "Scheduled versus direct", docs/re/gui.md
# "Combat mode, queue, clear buttons"):
#
#   EXE=kotor/out/kotor.exe sh kotor/tools/combat/queue.sh
#
# Runs kotor/tools/combat/queue1.txt from `uppercity`: six clicks on a targeted Sith trooper while the leader
# walks up to it, Disengage, two clicks on the block's first slot and R. As in the original
# (DefaultActionAttack 0x00616800 and the input message's AddAttackActions 0x004fde40, InsertScheduledAction
# 0x004d3660): each click adds an attack behind the one under way, four wait at most (the sixth click is
# dropped) and the bar shows four icons; Disengage empties the queue; the slot out of combat mode replaces,
# in combat mode it queues, and so does R. Exit 1 on a FAIL.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
EXE=${EXE} PAT='^fight' sh kotor/tools/combat/run.sh uppercity queue1 120 59:q59 73:q73 > /dev/null
log=kotor/out/combat/queue1.log
grep -a '^fight' $log | awk '
    {
        n++
        w = $0; sub(/.* waiting /, "", w); split(w, x, " ")
        waiting[n] = x[1]; icons[n] = x[3]
        q = $0; sub(/.* queue/, "", q); sub(/ waiting.*/, "", q)
        fights[n] = gsub(/ 12:/, "", q)
        mode[n] = ($0 ~ /combat_mode true/)
    }
    function want(i, wt, ft, what) {
        if (waiting[i] != wt || fights[i] != ft) { printf "FAIL step %d (%s): waiting %s attacks %s, want %d and %d\n", i, what, waiting[i], fights[i], wt, ft; bad++ }
        else printf "ok   step %d (%s): waiting %s attacks %s icons %s\n", i, what, waiting[i], fights[i], icons[i]
    }
    END {
        want(1, 0, 1, "first click: the attack walks up")
        want(2, 1, 2, "second click queues")
        want(3, 2, 3, "third click queues")
        want(4, 3, 4, "fourth click queues")
        want(5, 4, 5, "fifth click queues")
        want(6, 4, 5, "sixth click dropped: four wait at most")
        if (icons[6] != 4) { print "FAIL four icons on the bar, got " icons[6]; bad++ }
        want(7, 0, 0, "Disengage")
        if (mode[7]) { print "FAIL combat mode still on after Disengage"; bad++ }
        want(8, 0, 1, "slot out of combat mode replaces")
        want(9, 1, 2, "slot in combat mode queues")
        want(10, 2, 3, "R queues")
        if (n != 10) { print "FAIL " n " status lines, want 10"; bad++ }
        print "queue: " (bad + 0) " failed"
        exit(bad > 0)
    }'
