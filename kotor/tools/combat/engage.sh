#!/bin/sh
# Does an order to fight put the leader in combat mode at once? From `uppercity` (kotor/tools/checkpoints/make.sh), with
# the auto-pause on, a Sith trooper appears 12 m ahead and the game pauses (enemy sighted); then, still paused, the
# target block's first slot is clicked (engage1.txt), key 1 queues a second attack, F disengages, R attacks again, and
# Space lets the leader walk up and fight. FAIL and exit status 1 unless, in that order:
#
#   - after the click, paused and 12 m away: combat mode on, the combat bar up (BTN_CLEARALL, BTN_CLEARONE shown) and
#     the attack's icon in LBL_QUEUE0;
#   - after key 1: a second icon in LBL_QUEUE1;
#   - after F: the bar down, the queue empty;
#   - after R: the bar and LBL_QUEUE0 up again;
#   - unpaused: the bar stays up while the leader closes in, and combat mode goes once the trooper is dead.
#
#   sh kotor/tools/combat/engage.sh            (EXE=kotor/out/kotor.exe; run from the repository root; about 5 seconds)
#
# The log is kotor/out/combat/engage1.log. Combat mode is the client creature's flag, not the server's combat state:
# docs/re/movement.md 2.1 "Combat mode", docs/mechanics/combat.md row 44.
export PATH=/g/Dev/msys64/mingw64/bin:$PATH
exe=${EXE:-kotor/out/kotor.exe}
out=kotor/out/combat
ck=kotor/out/checkpoints
mkdir -p $out
if [ ! -d $ck/uppercity ]; then echo "no checkpoint $ck/uppercity: run sh kotor/tools/checkpoints/make.sh first"; exit 2; fi
rm -rf $out/saves_engage
$exe --load $ck/uppercity --no-render --speed 8 --saves $out/saves_engage --input kotor/tools/combat/engage1.txt --frames 620 --log combat,objects > $out/engage1.log 2>&1
log=$out/engage1.log
fail=0

# The controls' visibility, in the order the script asks: after the click, after 1, after F, after R.
got=$(grep -a '^ctl: ' $log | sed -E 's/^ctl: ([A-Z_0-9]+) .* visible ([a-z]+) .*/\1=\2/' | tr '\n' ' ')
want="BTN_CLEARALL=true BTN_CLEARONE=true LBL_QUEUE0=true LBL_QUEUE1=false LBL_QUEUE1=true BTN_CLEARALL=false LBL_QUEUE0=false BTN_CLEARALL=true LBL_QUEUE0=true "
if ! grep -a -q 'auto-pause: 48212' $log; then
  echo "FAIL the enemy-sighted auto-pause did not come (see $log)"; fail=1
fi
if [ "$got" != "$want" ]; then
  echo "FAIL the combat bar: got   $got"
  echo "                    wanted $want"
  fail=1
fi
# The fight lines (ui fight): 2 at frame 60 (paused, far), 6 at frame 130 (walking), the last at 600 (the trooper dead).
fights=$(grep -a '^fight leader' $log)
far=$(echo "$fights" | sed -n 2p | sed -E 's/.* combat_mode ([a-z]+) bar ([a-z]+) .* dist ([0-9.]+) .*/\1 \2 \3/')
walk=$(echo "$fights" | sed -n 6p | sed -E 's/.* combat_mode ([a-z]+) bar ([a-z]+) .* dist ([0-9.]+) .*/\1 \2 \3/')
last=$(echo "$fights" | tail -1 | sed -E 's/.* combat_mode ([a-z]+) bar ([a-z]+) .*/\1 \2/')
case "$far" in
  "true true "1[0-9].*) ;;
  *) echo "FAIL after the paused click: combat mode, bar, distance '$far' (want 'true true' at 10 m or more)"; fail=1 ;;
esac
case "$walk" in
  "true true "*) ;;
  *) echo "FAIL while walking up: combat mode, bar, distance '$walk' (want 'true true')"; fail=1 ;;
esac
if ! grep -a -q 'g_sithtroop01) dies' $log; then
  echo "FAIL the trooper did not die (see $log)"; fail=1
elif [ "$last" != "false false" ]; then
  echo "FAIL after the kill: combat mode, bar '$last' (want 'false false')"; fail=1
fi
if [ $fail = 0 ]; then echo "ok   engage: paused click at ${far##* } m put the bar up with the attack queued; 1, F, R as the original; bar up on the walk (${walk##* } m), down after the kill"; fi
exit $fail
